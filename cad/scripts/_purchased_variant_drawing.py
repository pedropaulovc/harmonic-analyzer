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
from _drawing_types import DRAWING_TEMPLATES, DrawingSpec
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
    _open_supplier_source_read_only,
    _purchased_title_block,
    _source_file_sha256,
    add_purchased_footer,
)
from _purchased_title_fit import fit_purchased_title_block
from _rebuild import active_configuration_name
from _reference_source_lifecycle import (
    _activate_reference_document,
    _preserve_reference_source_file,
    _show_reference_configuration,
)


# Third-angle slots (column, row) in a member panel's 2 x 2 grid: Top above
# Front, Right beside it, the Isometric in the free corner.
_SLOTS = {"*Front": (0, 0), "*Top": (0, 1), "*Right": (1, 0), "*Isometric": (1, 1)}
_PANEL_ROWS = ((0.127, 0.179), (0.194, 0.244))


def _panel(index: int, count: int) -> tuple[float, float]:
    """One of two or three member panels' left and right edges."""
    if count not in (2, 3) or not 0 <= index < count:
        raise ValueError(f"invalid purchased-member panel {index} of {count}")
    width = (0.396 - 0.008 * (count - 1)) / count
    left = 0.018 + index * (width + 0.008)
    return left, left + width


def configuration_view_cells(index: int, count: int) -> tuple:
    """Four third-angle reference cells in one of two or three member panels.

    Returned in Front, Top, Right, Isometric order.
    """
    left, right = _panel(index, count)
    middle = (left + right) / 2.0
    columns = ((left, middle - 0.004), (middle + 0.004, right))
    return tuple(
        _cell(
            name,
            columns[_SLOTS[name][0]][0],
            _PANEL_ROWS[_SLOTS[name][1]][0],
            columns[_SLOTS[name][0]][1],
            _PANEL_ROWS[_SLOTS[name][1]][1],
        )
        for name in ("*Front", "*Top", "*Right", "*Isometric")
    )


def isometric_view_cells(index: int, count: int) -> tuple:
    """One Isometric cell over a whole member panel: a member whose own sheet
    carries its orthographic views."""
    left, right = _panel(index, count)
    return (_cell("*Isometric", left, _PANEL_ROWS[0][0], right, _PANEL_ROWS[1][1]),)


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
    additional_sheets_title: str = "Member Rework",
    notes: str = "",
    title_fit: bool = False,
    isometric_only: Mapping[str, int] | None = None,
    source_configuration: str | None = None,
    unit: str = "mm",
) -> dict[str, str]:
    """Draw purchased-member references, with separately scoped rework sheets.

    ``variants`` pairs exact native configuration names with short member labels.
    The reference sheet prints only sourcing facts (member, quantity, purchase
    unit, supplier and SKU); installation belongs to the assembly's steps.

    Member headers are centered by their measured native text extents inside
    their reserved band; an insertion point alone is not proof of containment.
    A caller may add member-specific native reference annotations after fitting;
    its returned readbacks run again after the final drawing rebuild.
    Additional sheets, when requested, are duplicated while the template is
    still blank and authored before the same single finalization. Their checks
    follow (and never replace) the complete purchased-reference sheet checks.
    ``general_text`` overrides only the footer's general line, retaining its
    native text/extent checks; None keeps the ``cut_to_suit``-selected default.
    ``notes`` prints a member note in the footer's notes lines (rule 7's
    budget); ``additional_sheets_title`` names what the appended sheets carry
    in the PDF title and summary. ``title_fit`` fits the reference sheet's
    Name, Material and DWG. NO. in their native cells
    (``fit_purchased_title_block``) and re-proves them settled.
    ``isometric_only`` names members whose own appended sheet carries their
    orthographic views, each with that sheet's number: such a member shows
    only its isometric, over its whole panel at the largest scale that fits,
    its header pointing at the sheet ("SEE SHEET n"). Other members keep
    their four views.
    ``source_configuration`` activates that member in the open source part,
    in memory, before the drawing exists. Supplier-reference attachment
    proofs (``_supplier_screw_dimensions``) read the source part's ACTIVE
    configuration, so a member that carries them must be the active one
    while it is annotated and settled.

    The source part is opened read-only and must be clean before the drawing
    exists. Its bytes are hashed before the open and must match at every
    finalization checkpoint, in the settled checks and on exit, failures
    included (``_preserve_reference_source_file``). Imported dimensions whose
    text the sheets set can write through to the part in memory; only the
    file is guarded. The one allowed state change is the declared
    ``source_configuration``: every check requires exactly that member
    active, and exit restores the saved one.
    """
    if (additional_sheet_scales is None) != (append_sheets is None):
        raise ValueError("additional sheets require both scales and an author")
    if additional_sheet_scales is not None and not additional_sheet_scales:
        raise ValueError("additional sheet scales must not be empty")
    configurations = tuple(configuration for configuration, _ in variants)
    if len(set(configurations)) != len(configurations):
        raise ValueError("purchased-member configurations must be unique")
    isometric_only = dict(isometric_only or {})
    if set(isometric_only) - set(configurations):
        raise ValueError("isometric-only members must be depicted configurations")
    last_sheet = 1 + len(additional_sheet_scales or {})
    if any(
        type(number) is not int or not 2 <= number <= last_sheet
        for number in isometric_only.values()
    ):
        raise ValueError("an isometric-only member must cite an appended sheet")
    cells_by_configuration = {
        configuration: (
            isometric_view_cells if configuration in isometric_only
            else configuration_view_cells
        )(index, len(variants))
        for index, (configuration, _) in enumerate(variants)
    }
    if source_configuration is not None and source_configuration not in configurations:
        raise ValueError("the active source configuration must be a depicted member")
    source = spec.source
    if spec.source_kind != "part" or not source.is_file():
        raise FileNotFoundError(
            f"source configured purchased part is missing: {source}"
        )
    row = _config.parts(source.stem)
    quantities = row["configuration_quantities"]
    if set(quantities) != set(configurations):
        raise ValueError("purchased sheet must depict every registered configuration")
    if sum(int(quantities[name]) for name in configurations) != int(row["quantity"]):
        raise ValueError(
            "configured installed quantities do not sum to the family quantity"
        )
    label = spec.artifact_stem
    source_sha256 = _source_file_sha256(source)
    with _preserve_reference_source_file(source, source_sha256, label=label):
        model = _open_supplier_source_read_only(
            adapter, source, label=f"open {label} source"
        )
        if model.GetSaveFlag() is not False:
            raise RuntimeError(f"{label}: source part must be clean before the drawing exists")
        saved = active_configuration_name(adapter, model)
        if not saved:
            raise RuntimeError(f"{label}: source part has no readable active configuration")
        active = source_configuration or saved

        def assert_source(stage: str) -> None:
            require_source_state(
                adapter, model, source, active, source_sha256, stage=stage, label=label
            )

        primary: BaseException | None = None
        try:
            if active != saved:
                # The just-opened part is the active document, as the transition requires.
                _show_reference_configuration(adapter, model, active, label=label)
            assert_source("before view creation")
            return await _draw_purchased_variants(
                adapter,
                spec,
                model,
                assert_source,
                variants=variants,
                configurations=configurations,
                row=row,
                cells_by_configuration=cells_by_configuration,
                isometric_only=isometric_only,
                item=item,
                purchase_unit=purchase_unit,
                cut_to_suit=cut_to_suit,
                general_text=general_text,
                annotate_member=annotate_member,
                additional_sheet_scales=additional_sheet_scales,
                append_sheets=append_sheets,
                additional_sheets_title=additional_sheets_title,
                notes=notes,
                title_fit=title_fit,
                unit=unit,
            )
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                if active != saved:
                    _activate_reference_document(adapter, model, label=label)
                    _show_reference_configuration(adapter, model, saved, label=label)
                require_source_state(
                    adapter,
                    model,
                    source,
                    saved,
                    source_sha256,
                    stage="drawing lifecycle exit",
                    label=label,
                )
            except BaseException as integrity_error:
                if primary is None:
                    raise
                primary.add_note(f"{label}: source integrity check also failed: {integrity_error}")


def require_source_state(
    adapter: Any,
    model: Any,
    source: Path,
    configuration: str,
    expected_sha256: str,
    *,
    stage: str,
    label: str,
) -> None:
    """The live source: same file, still read-only, the expected member, same bytes."""
    active = active_configuration_name(adapter, model)
    read_only = model.IsOpenedReadOnly()
    path = str(model.GetPathName())
    digest = _source_file_sha256(source)
    if (
        active != configuration
        or read_only is not True
        or Path(path).resolve() != Path(source).resolve()
        or digest != expected_sha256
    ):
        raise RuntimeError(
            f"{label} source {stage}: source state changed: "
            f"configuration={active!r}; expected={configuration!r}; "
            f"read_only={read_only!r}; path={path!r}; "
            f"bytes_unchanged={digest == expected_sha256}"
        )


async def _draw_purchased_variants(
    adapter: Any,
    spec: DrawingSpec,
    model: Any,
    assert_source: Callable[[str], None],
    *,
    variants: tuple[tuple[str, str], ...],
    configurations: tuple[str, ...],
    row: Mapping[str, Any],
    cells_by_configuration: Mapping[str, tuple],
    isometric_only: Mapping[str, int],
    item: str,
    purchase_unit: str,
    cut_to_suit: bool,
    general_text: str | None,
    annotate_member: Callable[
        [Any, str, tuple, list[Any]], tuple[Callable[[], None], ...]
    ] | None,
    additional_sheet_scales: Mapping[str, tuple[float, float]] | None,
    append_sheets: Callable[[Any], tuple[Callable[[], None], ...]] | None,
    additional_sheets_title: str,
    notes: str,
    title_fit: bool,
    unit: str,
) -> dict[str, str]:
    source = spec.source
    quantities = row["configuration_quantities"]
    total = sum(int(quantities[name]) for name in configurations)
    names = (*_PROPERTIES, "Material Specification", "Finish")
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

    draw, sheet = new_project_drawing(adapter, layout=spec.layout, unit=unit)
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
        f"{f' and {additional_sheets_title}' if append_sheets is not None else ''}"
        " Drawing"
    )
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: title,
            1: (
                "Harmonic Analyzer purchased-part identification and "
                f"{additional_sheets_title.lower()}"
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
    sheet_scale = None
    for configuration, label, cells, views in groups:
        scales = _fit_views(draw, views, cells)
        center_marks = _center_marks_without_lines(views, cells)
        # The sheet's scale is the first orthographic member's.
        if sheet_scale is None and "*Front" in scales:
            sheet_scale = scales["*Front"]
        if annotate_member is not None:
            member_checks.extend(annotate_member(adapter, configuration, cells, views))
        left = min(cell[0] for _, _, cell in cells)
        right = max(cell[2] for _, _, cell in cells)
        caption = f"{label}  QTY {int(quantities[configuration])} INSTALLED"
        if configuration in isometric_only:
            caption += f", SEE SHEET {isometric_only[configuration]}"
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
            caption = orientation[1:].upper()
            # ASME Y14.3: state a view's scale only when it differs from the
            # sheet's. The sheet takes the first member's FRONT scale.
            if sheet_scale is None or scale != sheet_scale:
                caption += f"  {scale[0]}:{scale[1]}"
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
    if sheet_scale is None:  # every member isometric-only: the first one's
        sheet_scale = configured_views[0][2]
    purchase_note = f"QTY {total} INSTALLED MEMBERS; PURCHASE UNIT: {purchase_unit}."
    note = _literal_note(adapter, purchase_note, 0.018, 0.113)
    placed.append((note, purchase_note, purchase_note, (0.015, 0.107, 0.415, 0.114)))
    placed.extend(
        add_purchased_footer(
            adapter,
            draw,
            properties,
            item=item,
            notes=notes,
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
    title_check = None
    if title_fit:
        # The title links resolve, and their extents are measurable, after rebuild.
        rebuild_drawing(adapter, label=f"{spec.artifact_stem} title-block fit")
        title_check = fit_purchased_title_block(adapter, spec=spec)

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
        if title_check is not None:
            title_check()

    additional_checks = ()
    if append_sheets is not None:
        package_sheet_scales = {
            reference_sheet_name: sheet_scale, **additional_sheet_scales,
        }
        additional_checks = append_sheets(adapter)

    def checkpoint(stage: str) -> None:
        # After an attempted close the drawing's handles are not dereferenced;
        # the lifecycle exit check still observes the source.
        if stage != "after_drawing_close":
            assert_source(stage)

    return await finalize_drawing(
        adapter,
        DrawingOutputs(**spec.outputs),
        layout=spec.layout,
        pdf_title=title,
        scale=sheet_scale,
        expected_sheet_names=package_sheet_names,
        sheet_scales=package_sheet_scales,
        settled_checks=(
            assert_reference_sheet,
            *member_checks,
            *additional_checks,
            lambda: assert_source("settled before drawing save"),
        ),
        checkpoint=checkpoint,
    )
