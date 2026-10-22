"""One purchased-reference sheet for distinct members of one supplier SKU.

Each configuration keeps its own four native views, caption and installed-member
quantity. Supplier identity and purchase units belong to the common footer; a
configuration's quantity is never interpreted as a number of chains or kits.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    iter_views,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
import _config
import _telemetry
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_notes import property_link
from _drawing_registry import DRAWING_TEMPLATES, DrawingSpec
from _drawing_sheet_region import sheet_drawable_region
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _purchased_fastener_drawing import (
    _CAPTION_BELOW,
    _CAPTION_TO_CELL,
    _PROPERTIES,
    _box,
    _cell,
    _center_marks_without_lines,
    _fit_views,
    _inside,
    _literal_note,
    _purchased_title_block,
    add_purchased_footer,
)


def configuration_view_cells(index: int, count: int) -> tuple:
    """Four third-angle reference cells in one of two or three member panels."""
    if count not in (2, 3) or not 0 <= index < count:
        raise ValueError(f"invalid purchased-member panel {index} of {count}")
    width = (0.396 - 0.008 * (count - 1)) / count
    left = 0.018 + index * (width + 0.008)
    middle = left + width / 2.0
    right = left + width
    return (
        _cell("*Front", left, 0.127, middle - 0.004, 0.179),
        _cell("*Top", left, 0.194, middle - 0.004, 0.244),
        _cell("*Right", middle + 0.004, 0.127, right, 0.179),
        _cell("*Isometric", middle + 0.004, 0.194, right, 0.244),
    )


def configure_reference_views(
    adapter: Any, configuration: str, views: list[Any]
) -> None:
    """Select the exact member before fitting or annotating its drawing views."""
    for view in views:
        view.ReferencedConfiguration = configuration
    rebuild_drawing(adapter, label=f"{configuration} reference views")
    for view in views:
        if str(view.ReferencedConfiguration) != configuration:
            raise RuntimeError(
                f"{configuration}: native view configuration did not persist"
            )


async def build_purchased_variant_drawing(
    adapter: Any,
    spec: DrawingSpec,
    *,
    variants: tuple[tuple[str, str], ...],
    item: str,
    purchase_unit: str,
    cut_to_suit: bool = False,
    general_text: str | None = None,
    annotate_member: Callable[
        [Any, str, tuple, list[Any]], tuple[Callable[[], None], ...]
    ] | None = None,
    additional_sheet_scales: Mapping[str, tuple[float, float]] | None = None,
    append_sheets: Callable[[Any], tuple[Callable[[], None], ...]] | None = None,
) -> dict[str, str]:
    """Draw purchased-member references, with separately scoped rework sheets.

    ``variants`` pairs exact native configuration names with short member labels.
    The source stamps ``<configuration> Manufacturing Notes`` at document scope,
    because every $PRPSHEET link on this single sheet follows its first view.

    Member headers are centered by their measured native text extents inside
    their reserved band; an insertion point alone is not proof of containment.
    A caller may add member-specific native reference annotations after fitting;
    its returned readbacks run again after the final drawing rebuild.
    Additional sheets, when requested, are duplicated while the template is
    still blank and authored before the same single finalization. Their checks
    follow (and never replace) the complete purchased-reference sheet checks.
    ``general_text`` overrides only the footer's general line, retaining its
    native text/extent checks; None keeps the ``cut_to_suit``-selected default.
    """
    if (additional_sheet_scales is None) != (append_sheets is None):
        raise ValueError("additional sheets require both scales and an author")
    if additional_sheet_scales is not None and not additional_sheet_scales:
        raise ValueError("additional sheet scales must not be empty")
    configurations = tuple(configuration for configuration, _ in variants)
    if len(set(configurations)) != len(configurations):
        raise ValueError("purchased-member configurations must be unique")
    cells_by_configuration = {
        configuration: configuration_view_cells(index, len(variants))
        for index, (configuration, _) in enumerate(variants)
    }
    source = spec.source
    if spec.source_kind != "part" or not source.is_file():
        raise FileNotFoundError(
            f"source configured purchased part is missing: {source}"
        )
    row = _config.parts(source.stem)
    quantities = row["configuration_quantities"]
    if set(quantities) != set(configurations):
        raise ValueError("purchased sheet must depict every registered configuration")
    total = sum(int(quantities[name]) for name in configurations)
    if total != int(row["quantity"]):
        raise ValueError(
            "configured installed quantities do not sum to the family quantity"
        )
    note_properties = tuple(f"{name} Manufacturing Notes" for name in configurations)
    names = (*_PROPERTIES, "Material Specification", "Finish", *note_properties)
    check(f"open {spec.artifact_stem} source", await adapter.open_model(str(source)))
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    if Path(model.GetPathName()).resolve() != source.resolve():
        raise RuntimeError(f"opened configured purchased part is not {source}")
    properties = read_required_properties(model, names, required=names)
    expected = {
        "Number": str(row["number"]),
        "Title": spec.artifact_stem,
        "Stock Name": str(row["stock_name"]),
        "Supplier": str(row["supplier"]),
        "Supplier SKUs": ", ".join(row["supplier_skus"]),
        "Material Specification": str(row["material_specification"]),
        "Finish": str(row["finish"]),
    }
    for name, value in expected.items():
        if properties[name] != value:
            raise RuntimeError(
                f"{spec.artifact_stem}: stale {name} {properties[name]!r} != {value!r}"
            )

    draw, sheet = new_project_drawing(adapter, layout=spec.layout)
    reference_sheet_name = None
    package_sheet_names = None
    package_sheet_scales = None
    if additional_sheet_scales is not None:
        reference_sheet_name = str(adapter._get_attr_or_call(sheet, "GetName"))
        package_sheet_names = (reference_sheet_name, *additional_sheet_scales)
        create_blank_drawing_sheets(
            adapter, package_sheet_names, label=f"{spec.artifact_stem} package"
        )
        if not _early_bound(draw, "IDrawingDoc").ActivateSheet(reference_sheet_name):
            raise RuntimeError("failed to restore purchased-reference sheet")
    title_notes = _purchased_title_block(
        adapter,
        draw,
        material=properties["Material Specification"],
        finish=properties["Finish"],
        material_property="Material Specification",
    )
    title = (
        f"{row['title']} — Configured Purchased Part Reference"
        f"{' and Member Rework' if append_sheets is not None else ''} Drawing"
    )
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: title,
            1: (
                "Harmonic Analyzer purchased-part identification and member rework"
                if append_sheets is not None
                else "Harmonic Analyzer purchased-part identification; reference only"
            ),
            2: "Harmonic Analyzer Project",
            3: (
                f"{spec.artifact_stem}; {properties['Supplier']}; "
                f"{properties['Supplier SKUs']}"
            ),
            4: "; ".join(configurations),
        },
    )
    groups = []
    for configuration, label in variants:
        cells = cells_by_configuration[configuration]
        views = [
            _early_bound(
                place_view(adapter, str(source), orientation, *center, scale=(1, 1)),
                "IView",
            )
            for orientation, center, _ in cells
        ]
        configure_reference_views(adapter, configuration, views)
        for view in views:
            set_hidden_lines_removed(adapter, view)
        groups.append((configuration, label, cells, views))
    # Insertion can drift the sheet scale; pin all views before native fitting.
    for _, _, _, views in groups:
        for view in views:
            view.UseSheetScale = 0
            view.ScaleRatio = double_array([1.0, 1.0])
    first_view_name = view_name(adapter, groups[0][3][0])
    if not first_view_name:
        raise RuntimeError("configured purchased sheet has no property-source view")
    sheet.CustomPropertyView = first_view_name

    placed = []
    configured_views = []
    member_checks = []
    sheet_scale = (1, 1)
    for index, (configuration, label, cells, views) in enumerate(groups):
        scales = _fit_views(draw, views, cells)
        center_marks = _center_marks_without_lines(views, cells)
        if index == 0:
            sheet_scale = scales["*Front"]
        if annotate_member is not None:
            member_checks.extend(annotate_member(adapter, configuration, cells, views))
        left, right = cells[0][2][0], cells[2][2][2]
        caption = f"{label}  QTY {int(quantities[configuration])} INSTALLED"
        caption_cell = (left, 0.255, right, 0.264)
        note = _literal_note(adapter, caption, left, 0.262)
        # The insertion point is not an extent edge. Seat the measured text box
        # inside its existing band, as the view captions do horizontally below.
        bounds = _box(note.GetExtent(), label=caption, kind="note")
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        position = tuple(
            float(value)
            for value in adapter._get_attr_or_call(annotation, "GetPosition")
        )
        target = (
            position[0] + (caption_cell[0] + caption_cell[2] - bounds[0] - bounds[2]) / 2,
            position[1] + (caption_cell[1] + caption_cell[3] - bounds[1] - bounds[3]) / 2,
            0.0,
        )
        if annotation.SetPosition(*target) is not True:
            raise RuntimeError(f"{configuration}: failed to position member caption")
        positioned = _box(note.GetExtent(), label=caption, kind="note")
        _telemetry.info(
            f"{configuration} member caption: position_m={position!r} -> {target!r}; "
            f"extent_m={bounds!r} -> {positioned!r}; reserved_m={caption_cell!r}",
            configuration=configuration,
        )
        placed.append((note, caption, caption, caption_cell))
        for view, (orientation, center, cell) in zip(views, cells, strict=True):
            scale = scales[orientation]
            caption = f"{orientation[1:].upper()}  {scale[0]}:{scale[1]}"
            floor = cell[1]
            if not center_marks[orientation]:
                floor = max(_box(view.GetOutline(), label=orientation)[1], floor)
            caption_y = floor - _CAPTION_TO_CELL
            note = _literal_note(adapter, caption, center[0], caption_y)
            bounds = _box(note.GetExtent(), label=caption, kind="note")
            annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
            x = 2 * center[0] - (bounds[0] + bounds[2]) / 2
            if not annotation.SetPosition(x, caption_y, 0.0):
                raise RuntimeError(f"{caption}: failed to center view caption")
            placed.append(
                (
                    note,
                    caption,
                    caption,
                    (
                        cell[0],
                        caption_y - _CAPTION_BELOW,
                        cell[2],
                        caption_y + 0.001,
                    ),
                )
            )
            configured_views.append((view, configuration, scale, cell))
        property_name = f"{configuration} Manufacturing Notes"
        linked = f"{label}: {property_link(property_name)}"
        resolved = f"{label}: {properties[property_name]}"
        note_y = 0.106 - index * 0.007
        note = _literal_note(adapter, linked, 0.018, note_y)
        placed.append(
            (
                note,
                linked,
                resolved,
                (0.015, note_y - 0.006, 0.415, note_y + 0.001),
            )
        )
    purchase_note = f"QTY {total} INSTALLED MEMBERS; PURCHASE UNIT: {purchase_unit}."
    note = _literal_note(adapter, purchase_note, 0.018, 0.113)
    placed.append((note, purchase_note, purchase_note, (0.015, 0.107, 0.415, 0.114)))
    placed.extend(
        add_purchased_footer(
            adapter,
            draw,
            properties,
            item=item,
            cut_to_suit=cut_to_suit,
            general_text=general_text,
            label=spec.artifact_stem,
        )
    )
    values = tuple(adapter._get_attr_or_call(sheet, "GetProperties2"))
    if len(values) != 8:
        raise RuntimeError(
            f"configured purchased sheet properties are incomplete: {values!r}"
        )
    sheet.SetProperties2(
        int(values[0]),
        int(values[1]),
        float(sheet_scale[0]),
        float(sheet_scale[1]),
        False,
        float(values[5]),
        float(values[6]),
        False,
    )
    sheet.CustomPropertyView = first_view_name

    def assert_reference_sheet() -> None:
        if reference_sheet_name is not None and not _early_bound(
            draw, "IDrawingDoc"
        ).ActivateSheet(reference_sheet_name):
            raise RuntimeError("failed to activate purchased-reference sheet for readback")
        values = tuple(adapter._get_attr_or_call(sheet, "GetProperties2"))
        if (
            len(values) != 8
            or bool(values[4])
            or bool(values[7])
            or sheet.CustomPropertyView != first_view_name
        ):
            raise RuntimeError(
                "configured purchased third-angle/property-source settings changed"
            )
        actual = tuple(iter_views(adapter))
        expected_members = {
            (configuration, orientation)
            for configuration, cells in cells_by_configuration.items()
            for orientation, _, _ in cells
        }
        actual_members = {
            (str(view.ReferencedConfiguration), view.GetOrientationName())
            for view in actual
        }
        if len(actual) != len(expected_members) or actual_members != expected_members:
            raise RuntimeError(
                "configured purchased sheet has missing or extra member views"
            )
        template = DRAWING_TEMPLATES[spec.layout]
        region = sheet_drawable_region(
            adapter, sheet, width=template.width_m, height=template.height_m
        )
        border = (region.xmin, region.ymin, region.xmax, region.ymax)
        for view, configuration, scale, cell in configured_views:
            if (
                str(view.ReferencedConfiguration) != configuration
                or Path(view.GetReferencedModelName()).resolve() != source.resolve()
                or tuple(view.ScaleRatio) != scale
            ):
                raise RuntimeError(f"{configuration}: configured source/scale changed")
            box = _box(view.GetOutline(), label=configuration)
            if not _inside(box, cell) or not _inside(box, border):
                raise RuntimeError(
                    f"{configuration}: reference view leaves its cell/border"
                )
        for note, linked, resolved in title_notes:
            if (
                note.PropertyLinkedText != linked
                or note.GetText().replace("\r\n", "\n") != resolved
            ):
                raise RuntimeError(
                    "configured purchased title-block link did not resolve"
                )
        for note, linked, resolved, cell in placed:
            if (
                note.PropertyLinkedText != linked
                or note.GetText().replace("\r\n", "\n") != resolved
            ):
                raise RuntimeError(
                    f"configured purchased note did not resolve: {linked!r}"
                )
            box = _box(note.GetExtent(), label=linked, kind="note")
            if not _inside(box, cell) or not _inside(box, border):
                raise RuntimeError(
                    f"configured purchased note leaves its reserved space: {linked!r}; "
                    f"extent_m={box!r}, reserved_m={cell!r}, border_m={border!r}"
                )

    additional_checks = ()
    if append_sheets is not None:
        package_sheet_scales = {
            reference_sheet_name: sheet_scale, **additional_sheet_scales,
        }
        additional_checks = append_sheets(adapter)

    return await finalize_drawing(
        adapter,
        DrawingOutputs(**spec.outputs),
        layout=spec.layout,
        pdf_title=title,
        scale=sheet_scale,
        expected_sheet_names=package_sheet_names,
        sheet_scales=package_sheet_scales,
        settled_checks=(assert_reference_sheet, *member_checks, *additional_checks),
    )
