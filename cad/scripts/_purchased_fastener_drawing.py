"""Four-view purchased-fastener reference sheets, linked to the native source part."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Literal

import _config
import _telemetry
from _common import _early_bound, apply_custom_properties, check
from _drawing_common import (
    ASME_B_HEIGHT_M,
    ASME_B_WIDTH_M,
    TITLE_BLOCK_TOLERANCE_PROPERTIES,
    DrawingOutputs,
    add_property_linked_note,
    assert_asme_b_sheet,
    finalize_drawing,
    new_project_drawing,
    property_link,
    read_required_properties,
    set_hidden_lines_removed,
    sheet_drawable_region,
    stamp_drawing_summary,
)
from _drawing_registry import DrawingSpec
from _fastener_catalog import fastener
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    iter_views,
    place_view,
    view_name,
)

# Project-used scales, largest first. All four views share the largest scale
# fitting their actual native outlines; no catalogue dimension/axis heuristics.
_SCALES = ((8, 1), (5, 1), (4, 1), (2, 1), (1, 1), (1, 2), (1, 4), (1, 8))
# Front / Top / Right are in standard third-angle arrangement. The upper-right
# cell holds the additional pictorial view without stealing orthographic space.
_VIEW_CELLS = (
    ("*Front", (0.120, 0.125), (0.050, 0.0825, 0.190, 0.1675)),
    ("*Top", (0.120, 0.225), (0.050, 0.195, 0.190, 0.255)),
    ("*Right", (0.310, 0.125), (0.240, 0.0825, 0.380, 0.1675)),
    ("*Isometric", (0.310, 0.225), (0.240, 0.195, 0.380, 0.255)),
)
_PROPERTIES = (
    "Number",
    "Revision",
    "Title",
    "Material",
    "Stock Name",
    "Supplier",
    "Supplier SKUs",
    *TITLE_BLOCK_TOLERANCE_PROPERTIES,
)


def _box(
    values: Any, *, label: str, kind: Literal["view", "note"] = "view"
) -> tuple[float, float, float, float]:
    """Decode documented IView.GetOutline / INote.GetExtent sheet coordinates."""
    coordinates = tuple(float(value) for value in (values or ()))
    expected = 6 if kind == "note" else 4
    if len(coordinates) != expected or not all(map(math.isfinite, coordinates)):
        raise RuntimeError(f"{label}: invalid native extent {coordinates!r}")
    if kind == "note":
        coordinates = (coordinates[0], coordinates[1], coordinates[3], coordinates[4])
    if coordinates[0] >= coordinates[2] or coordinates[1] >= coordinates[3]:
        raise RuntimeError(f"{label}: empty or inverted native extent {coordinates!r}")
    return coordinates


def _inside(box: tuple[float, ...], container: tuple[float, ...]) -> bool:
    return (
        box[0] >= container[0]
        and box[1] >= container[1]
        and box[2] <= container[2]
        and box[3] <= container[3]
    )


def _rebuild(draw: Any, *, phase: str) -> None:
    if not draw.EditRebuild3():
        raise RuntimeError(f"purchased drawing rebuild failed: {phase}")


@_telemetry.traced("drawing.purchased_fit_views")
def _fit_views(draw: Any, views: list[Any]) -> tuple[int, int]:
    # The initial 1:1 outlines include SOLIDWORKS' native view padding. The
    # estimate only skips obviously oversized scales; actual regenerated bounds
    # decide the result, including any padding that does not scale linearly.
    _rebuild(draw, phase="initial view extents")
    extents = []
    for view, (name, _, _) in zip(views, _VIEW_CELLS, strict=True):
        ratio = tuple(float(value) for value in view.ScaleRatio)
        if len(ratio) != 2 or ratio != (1.0, 1.0):
            raise RuntimeError(
                f"{name}: initial 1:1 view scale did not persist: {ratio!r}"
            )
        extents.append(_box(view.GetOutline(), label=name))
    limit = min(
        min(
            (cell[2] - cell[0]) / (box[2] - box[0]),
            (cell[3] - cell[1]) / (box[3] - box[1]),
        )
        for box, (_, _, cell) in zip(extents, _VIEW_CELLS, strict=True)
    )
    for scale in _SCALES:
        if scale[0] / scale[1] > limit:
            continue
        with _telemetry.span(
            "drawing.purchased_scale_candidate", scale=f"{scale[0]}:{scale[1]}"
        ):
            for view in views:
                view.UseSheetScale = 0
                view.ScaleRatio = double_array([float(scale[0]), float(scale[1])])
            _rebuild(draw, phase="apply common view scale")
            for view, (name, center, _) in zip(views, _VIEW_CELLS, strict=True):
                box = _box(view.GetOutline(), label=name)
                position = tuple(float(value) for value in view.Position)
                if len(position) != 2 or not all(map(math.isfinite, position)):
                    raise RuntimeError(
                        f"{name}: invalid native view position {position!r}"
                    )
                # Center the actual outline, not a presumed model-origin/axis.
                target = [
                    position[0] + center[0] - (box[0] + box[2]) / 2,
                    position[1] + center[1] - (box[1] + box[3]) / 2,
                ]
                if not view.SetViewPosition(double_array(target), False):
                    raise RuntimeError(f"{name}: failed to position purchased view")
            _rebuild(draw, phase="center purchased views")
            fits = True
            for view, (name, center, cell) in zip(views, _VIEW_CELLS, strict=True):
                ratio = tuple(float(value) for value in view.ScaleRatio)
                if (
                    ratio != tuple(float(value) for value in scale)
                    or view.UseSheetScale != 0
                ):
                    raise RuntimeError(
                        f"{name}: independent view scale did not persist: {ratio!r}"
                    )
                box = _box(view.GetOutline(), label=name)
                if (
                    abs((box[0] + box[2]) / 2 - center[0]) > 1e-6
                    or abs((box[1] + box[3]) / 2 - center[1]) > 1e-6
                ):
                    raise RuntimeError(f"{name}: native view failed to center: {box!r}")
                fits = fits and _inside(box, cell)
            if fits:
                return scale
    raise RuntimeError(
        "purchased fastener has no project-standard scale fitting all four view cells"
    )


@_telemetry.traced("drawing.purchased_note")
def _literal_note(adapter: Any, text: str, x: float, y: float) -> Any:
    note = add_note(adapter, text, x, y)
    if note is None:
        raise RuntimeError(f"failed to insert purchased drawing note {text!r}")
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"purchased drawing note has no text format: {text!r}")
    text_format.CharHeight = 0.003
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError(f"failed to size purchased drawing note {text!r}")
    if not annotation.SetPosition(x, y, 0.0):
        raise RuntimeError(f"failed to position purchased drawing note {text!r}")
    return note


@_telemetry.traced("drawing.purchased_title_block")
def _purchased_title_block(
    adapter: Any, draw: Any, *, material: str, finish: str
) -> list[tuple[Any, str, str]]:
    """Retarget this drawing's material/finish cells, never the saved template."""
    apply_custom_properties(adapter, {"Finish": finish}, model=draw)
    ddoc = _early_bound(draw, "IDrawingDoc")
    sheet_view = ddoc.GetFirstView()
    if sheet_view is None:
        raise RuntimeError("purchased drawing template has no sheet view")
    sheet_view = _early_bound(sheet_view, "IView")
    replacements = {
        property_link("Material Specification"): (property_link("Material"), material),
        property_link("Finish"): ('$PRP:"Finish"', finish),
    }
    matched = {token: 0 for token in replacements}
    notes = []
    for annotation in sheet_view.GetAnnotations() or ():
        annotation = _early_bound(annotation, "IAnnotation")
        if annotation.GetType() != 6:  # swAnnotationType_e.swNote
            continue
        specific = annotation.GetSpecificAnnotation()
        if specific is None:
            raise RuntimeError("purchased title-block note has no INote")
        note = _early_bound(specific, "INote")
        raw = str(note.PropertyLinkedText)
        linked_text = raw
        resolved_text = raw
        for token, (replacement, value) in replacements.items():
            occurrences = raw.count(token)
            if occurrences:
                matched[token] += occurrences
                linked_text = linked_text.replace(token, replacement)
                resolved_text = resolved_text.replace(token, value)
        if linked_text == raw:
            continue
        # Preserve the existing note, annotation formatting and all surrounding
        # label text; only these exact property-link tokens change ownership.
        note.PropertyLinkedText = linked_text
        if note.PropertyLinkedText != linked_text:
            raise RuntimeError(f"purchased title-block link did not persist: {raw!r}")
        notes.append((note, linked_text, resolved_text))
    if any(count != 1 for count in matched.values()):
        raise RuntimeError(
            "purchased template must contain exactly one Material Specification "
            f"and one Finish property link: {matched!r}"
        )
    return notes


async def build_purchased_fastener_drawing(
    adapter: Any, spec: DrawingSpec
) -> dict[str, str]:
    """Export Front/Top/Right plus Isometric without fabrication dimensions or PMI."""
    stock = fastener(spec.artifact_stem)
    source = spec.source
    if spec.source_kind != "part" or source.stem != stock.part_name:
        raise ValueError(f"purchased drawing source identity mismatch: {spec!r}")
    if not source.is_file():
        raise FileNotFoundError(f"source purchased part is missing: {source}")

    with _telemetry.span("drawing.purchased_source", part=stock.part_name):
        check(f"open {stock.part_name} source", await adapter.open_model(str(source)))
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        if Path(model.GetPathName()).resolve() != source.resolve():
            raise RuntimeError(f"opened purchased part is not {source}")
        properties = read_required_properties(model, _PROPERTIES, required=_PROPERTIES)
        registry = _config.parts(stock.part_name)
        finish = registry["finish"]
        if not isinstance(finish, str) or not finish.strip():
            raise RuntimeError(
                f"{stock.part_name}: registered purchased finish is empty"
            )
        expected = {
            "Number": str(registry["number"]),
            "Title": str(registry["title"]),
            "Material": str(registry["material"]),
            "Stock Name": stock.stock_name,
            "Supplier": stock.supplier,
            "Supplier SKUs": ", ".join(stock.skus),
        }
        for name, value in expected.items():
            if properties[name] != value:
                raise RuntimeError(
                    f"{stock.part_name}: stale source {name} {properties[name]!r} != {value!r}"
                )

    draw, sheet = new_project_drawing(adapter)
    title_block_notes = _purchased_title_block(
        adapter, draw, material=properties["Material"], finish=finish
    )
    title = f"{properties['Title']} — Purchased Part Reference Drawing"
    with _telemetry.span("drawing.purchased_summary"):
        stamp_drawing_summary(
            adapter,
            draw,
            {
                0: title,
                1: "Harmonic Analyzer purchased-part identification; reference only",
                2: "Harmonic Analyzer Project",
                3: f"{stock.part_name}; {properties['Supplier']}; {properties['Supplier SKUs']}",
                4: "Front, Top, Right and Isometric; no fabrication dimensions or PMI",
            },
        )

    views = []
    with _telemetry.span("drawing.purchased_create_views"):
        for name, center, _ in _VIEW_CELLS:
            view = _early_bound(
                place_view(adapter, str(source), name, *center, scale=(1, 1)), "IView"
            )
            set_hidden_lines_removed(adapter, view)
            views.append(view)
        # Later insertions may auto-adjust the sheet scale. Pin all views only
        # after insertion so the measurement pass is genuinely at native 1:1.
        for view in views:
            view.UseSheetScale = 0
            view.ScaleRatio = double_array([1.0, 1.0])
    scale = _fit_views(draw, views)

    with _telemetry.span("drawing.purchased_property_link"):
        values = tuple(sheet.GetProperties2())
        if len(values) != 8:
            raise RuntimeError(
                f"purchased drawing has incomplete sheet properties: {values!r}"
            )
        # Preserve template dimensions/format while explicitly selecting third
        # angle and the first view's source for every title-block property link.
        sheet.SetProperties2(
            int(values[0]),
            int(values[1]),
            float(scale[0]),
            float(scale[1]),
            False,
            float(values[5]),
            float(values[6]),
            False,
        )
        first_name = view_name(adapter, views[0])
        if not first_name:
            raise RuntimeError("purchased front view has no native name")
        sheet.CustomPropertyView = first_name
        values = tuple(sheet.GetProperties2())
        if (
            len(values) != 8
            or bool(values[4])
            or bool(values[7])
            or sheet.CustomPropertyView != first_name
        ):
            raise RuntimeError(
                "purchased drawing third-angle/property-source settings did not persist"
            )
        assert_asme_b_sheet(adapter, sheet, phase="purchased layout", scale=scale)

    notes = []
    with _telemetry.span("drawing.purchased_annotations"):
        for name, center, cell in _VIEW_CELLS:
            label = f"{name[1:].upper()}  {scale[0]}:{scale[1]}"
            note = _literal_note(adapter, label, center[0] - 0.026, cell[1] - 0.006)
            notes.append(
                (
                    note,
                    label,
                    label,
                    (cell[0], cell[1] - 0.012, cell[2], cell[1] - 0.001),
                )
            )
        text = (
            "PURCHASED PART / REFERENCE ONLY\n"
            "ORDER BY SUPPLIER SKU. DO NOT FABRICATE FROM THIS SHEET.\n"
            "GENERAL TOLERANCES AND EDGE-BREAK NOTES DO NOT APPLY."
        )
        note = _literal_note(adapter, text, 0.018, 0.072)
        notes.append((note, text, text, (0.015, 0.057, 0.260, 0.073)))
        for name, y, label in (
            ("Stock Name", 0.050, "STOCK:"),
            ("Supplier", 0.038, "SUPPLIER:"),
            ("Supplier SKUs", 0.026, "SKU:"),
        ):
            label_note = _literal_note(adapter, label, 0.018, y)
            notes.append(
                (label_note, label, label, (0.015, y - 0.007, 0.050, y + 0.001))
            )
            note = add_property_linked_note(adapter, name, 0.052, y, char_height=0.003)
            notes.append(
                (
                    _early_bound(note, "INote"),
                    property_link(name),
                    properties[name],
                    (0.050, y - 0.007, 0.260, y + 0.001),
                )
            )

    with _telemetry.span("drawing.purchased_native_contract"):
        _rebuild(draw, phase="linked notes and final layout")
        for note, linked_text, resolved_text in title_block_notes:
            if (
                note.PropertyLinkedText != linked_text
                or note.GetText() != resolved_text
            ):
                raise RuntimeError(
                    "purchased title-block property did not resolve from its "
                    f"expected source: {linked_text!r}"
                )
        actual = list(iter_views(adapter))
        orientations = tuple(view.GetOrientationName() for view in actual)
        if len(actual) != 4 or set(orientations) != {
            name for name, _, _ in _VIEW_CELLS
        }:
            raise RuntimeError(
                f"purchased drawing must have exactly four native views: {orientations!r}"
            )
        views_by_orientation = dict(zip(orientations, actual, strict=True))
        region = sheet_drawable_region(
            adapter, sheet, width=ASME_B_WIDTH_M, height=ASME_B_HEIGHT_M
        )
        border = (region.xmin, region.ymin, region.xmax, region.ymax)
        for name, _, cell in _VIEW_CELLS:
            view = views_by_orientation[name]
            if Path(view.GetReferencedModelName()).resolve() != source.resolve():
                raise RuntimeError(f"{name}: purchased view references the wrong model")
            if tuple(view.ScaleRatio) != scale:
                raise RuntimeError(f"{name}: final purchased view scale changed")
            box = _box(view.GetOutline(), label=name)
            if not _inside(box, cell) or not _inside(box, border):
                raise RuntimeError(
                    f"{name}: purchased view leaves its cell/border: {box!r}"
                )
        for note, linked_text, resolved_text, cell in notes:
            if (
                note.PropertyLinkedText != linked_text
                or note.GetText() != resolved_text
            ):
                raise RuntimeError(
                    f"purchased note did not resolve from its expected source: {linked_text!r}"
                )
            box = _box(note.GetExtent(), label=linked_text, kind="note")
            if not _inside(box, cell) or not _inside(box, border):
                raise RuntimeError(
                    f"purchased note leaves its reserved space/border: {linked_text!r}: {box!r}"
                )

    paths = spec.outputs
    return await finalize_drawing(
        adapter,
        DrawingOutputs(slddrw=paths["slddrw"], pdf=paths["pdf"], png=paths["png"]),
        pdf_title=title,
        scale=scale,
    )
