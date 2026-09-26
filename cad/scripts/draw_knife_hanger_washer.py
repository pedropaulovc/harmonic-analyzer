"""Create the compact purchased reference drawing for the knife-hanger washer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import _config
import _telemetry
from _common import _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    assert_asme_b_sheet,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    property_link,
    read_required_properties,
    set_hidden_lines_removed,
    set_reference_dimension,
    sheet_drawable_region,
    stamp_drawing_summary,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import fastener
from _purchased_fastener_drawing import (
    _PROPERTIES,
    _box,
    _fit_views,
    _literal_note,
    _purchased_title_block,
    _rebuild,
    _inside,
)
from knife_hanger_washer_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    INNER_DIAMETER_DIM,
    OUTER_DIAMETER_DIM,
    THICKNESS_DIM,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    iter_views,
    place_view,
    view_name,
)


SPEC = DRAWINGS_BY_NAME["knife_hanger_washer"]
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)

# The washer has one useful circular view, one edge view that carries the
# thickness, and one pictorial.  The projected pair is deliberately aligned
# instead of paying for a redundant right view.
_VIEW_CELLS = (
    ("*Top", (0.125, 0.180), (0.055, 0.120, 0.195, 0.240)),
    ("*Front", (0.125, 0.115), (0.055, 0.075, 0.195, 0.145)),
    ("*Isometric", (0.260, 0.180), (0.190, 0.120, 0.350, 0.240)),
)

# These are native model dimensions imported into their useful receiving views.
# Their positions are sheet coordinates in metres and are parenthesized below.
_TOP_KEEP = {
    OUTER_DIAMETER_DIM: (0.125, 0.225),
    INNER_DIAMETER_DIM: (0.178, 0.180),
}
_FRONT_KEEP = {THICKNESS_DIM: (0.180, 0.115)}

_LEADER_LINE_NONE = 3  # swLeaderLineVisibility_e.swLeaderLineNone


def _short_diametric_reference(adapter: Any, annotation: Any, *, label: str) -> None:
    """Keep a native diameter callout as a short, one-sided leader."""
    display = adapter._attempt(lambda: annotation.GetSpecificAnnotation())
    if display is None:
        raise RuntimeError(f"{label} has no display annotation")
    display = _sw_type_info.early_bound_or_flag(
        display,
        "IDisplayDimension",
        "SetSecondArrow",
        "GetUseDocSecondArrow",
        "GetSecondArrow",
        "SetBrokenLeader2",
        "GetUseDocBrokenLeader",
        "GetBrokenLeader2",
    )
    adapter._attempt(lambda: setattr(display, "DisplayAsLinear", False))
    if bool(adapter._attempt(lambda: display.DisplayAsLinear)):
        raise RuntimeError(f"{label} became a linear dimension")
    adapter._attempt(lambda: setattr(display, "Diametric", True))
    if not bool(adapter._attempt(lambda: display.Diametric)):
        raise RuntimeError(f"{label} is not diametric")
    adapter._attempt(lambda: setattr(display, "ArrowSide", 1))
    if int(adapter._attempt(lambda: display.ArrowSide)) != 1:
        raise RuntimeError(f"{label} did not retain its outside arrow")
    display.SetSecondArrow(False, False)
    if bool(display.GetUseDocSecondArrow()) or bool(display.GetSecondArrow()):
        raise RuntimeError(f"{label} retained its opposite-side arrow")
    adapter._attempt(lambda: setattr(display, "SolidLeader", False))
    if display.SetBrokenLeader2(False, 2) != 0:
        raise RuntimeError(f"failed to apply {label} broken leader")
    display.LeaderVisibility = _LEADER_LINE_NONE
    if int(display.LeaderVisibility) != _LEADER_LINE_NONE:
        raise RuntimeError(f"{label} retained its dimension leader line")


def _center_caption(adapter: Any, text: str, x: float, y: float) -> Any:
    note = _literal_note(adapter, text, x, y)
    bounds = _box(note.GetExtent(), label=text, kind="note")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    centered_x = 2.0 * x - (bounds[0] + bounds[2]) / 2.0
    if not annotation.SetPosition(centered_x, y, 0.0):
        raise RuntimeError(f"failed to center washer view caption {text!r}")
    return note

_CAPTION_CLEARANCE_M = 0.010  # 10 mm of paper below each native view outline


def _caption_below_view(
    adapter: Any, text: str, view: Any, x: float
) -> Any:
    """Place a centered caption below the view's measured native outline."""
    outline = _box(view.GetOutline(), label=f"{text} view", kind="view")
    return _center_caption(adapter, text, x, outline[1] - _CAPTION_CLEARANCE_M)


async def build(adapter: Any) -> dict[str, str]:
    stock = fastener(SPEC.artifact_stem)
    source = SPEC.source
    if SPEC.source_kind != "part" or source.stem != stock.part_name:
        raise ValueError(f"purchased drawing source identity mismatch: {SPEC!r}")
    if not source.is_file():
        raise FileNotFoundError(f"source purchased part is missing: {source}")

    with _telemetry.span("drawing.purchased_source", part=stock.part_name):
        check(f"open {stock.part_name} source", await adapter.open_model(str(source)))
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        if Path(model.GetPathName()).resolve() != source.resolve():
            raise RuntimeError(f"opened purchased part is not {source}")
        properties = read_required_properties(model, _PROPERTIES, required=_PROPERTIES)
        registry = _config.parts(stock.part_name)
        finish = str(registry["finish"]).strip()
        if not finish:
            raise RuntimeError(f"{stock.part_name}: registered purchased finish is empty")
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
                    f"{stock.part_name}: stale source {name} "
                    f"{properties[name]!r} != {value!r}"
                )

    template = DRAWING_TEMPLATES[SPEC.layout]
    draw, sheet = new_project_drawing(adapter, layout=SPEC.layout)
    title_block_notes = _purchased_title_block(
        adapter,
        draw,
        material=properties["Material"],
        finish=finish,
    )
    title = f"{properties['Title']} — Purchased Part Reference Drawing"
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: title,
            1: "Purchased reference; TOP above FRONT; ISO pictorial",
            2: "Harmonic Analyzer Project",
            3: f"{SPEC.artifact_stem}; {properties['Supplier']}; "
            f"{properties['Supplier SKUs']}",
            4: "Native supplier ID / OD / thickness references; no PMI",
        },
    )

    views = []
    for name, center, _cell in _VIEW_CELLS:
        view = _early_bound(
            place_view(adapter, str(source), name, *center, scale=(1, 1)),
            "IView",
        )
        if name != "*Isometric":
            set_hidden_lines_removed(adapter, view)
        views.append(view)
        view.UseSheetScale = 0
        view.ScaleRatio = double_array([1.0, 1.0])

    scale = _fit_views(draw, views, _VIEW_CELLS)
    values = tuple(adapter._get_attr_or_call(sheet, "GetProperties2"))
    if len(values) != 8:
        raise RuntimeError(f"washer drawing has incomplete sheet properties: {values!r}")
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
        raise RuntimeError("washer top view has no native name")
    sheet.CustomPropertyView = first_name
    assert_asme_b_sheet(
        adapter,
        sheet,
        layout=SPEC.layout,
        phase="washer compact layout",
        scale=scale,
    )

    scale_text = f"{int(scale[0])}:{int(scale[1])}"
    top_view, front_view, iso_view = views
    notes: list[tuple[Any, str]] = []
    linked_notes: list[tuple[Any, str, str]] = []
    notes.append(
        (
            _caption_below_view(
                adapter, f"TOP  {scale_text}", top_view, _VIEW_CELLS[0][1][0]
            ),
            f"TOP  {scale_text}",
        )
    )
    notes.append(
        (
            _caption_below_view(
                adapter, f"FRONT  {scale_text}", front_view, _VIEW_CELLS[1][1][0]
            ),
            f"FRONT  {scale_text}",
        )
    )
    notes.append(
        (
            _caption_below_view(
                adapter,
                f"ISOMETRIC  {scale_text}  (PICTORIAL)",
                iso_view,
                _VIEW_CELLS[2][1][0],
            ),
            f"ISOMETRIC  {scale_text}  (PICTORIAL)",
        )
    )

    top_annotations = curate_view_dimensions(
        adapter,
        top_view,
        keep=_TOP_KEEP,
        view_label="washer top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    front_annotations = curate_view_dimensions(
        adapter,
        front_view,
        keep=_FRONT_KEEP,
        view_label="washer front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    imported = [*top_annotations, *front_annotations]
    for annotation in imported:
        name = dimension_name(adapter, annotation)
        if name in {OUTER_DIAMETER_DIM, INNER_DIAMETER_DIM}:
            set_reference_dimension(
                adapter,
                annotation,
                label=f"{name} reference",
                diameter=True,
            )
            _short_diametric_reference(
                adapter, annotation, label=f"{name} reference"
            )
        elif name == THICKNESS_DIM:
            set_reference_dimension(
                adapter,
                annotation,
                label="washer thickness reference",
                diameter=False,
            )
        else:
            raise RuntimeError(f"unexpected washer reference dimension {name!r}")
    assert_imported_precision(adapter, imported, DRAWING_PRECISION_BY_NAME)
    set_hidden_lines_removed(adapter, top_view)
    set_hidden_lines_removed(adapter, front_view)


    purchase_text = (
        "PURCHASED PART / REFERENCE GEOMETRY\n"
        "REFERENCE SIZES ARE SUPPLIER NOMINALS; VERIFY RECEIPT AGAINST SKU.\n"
        "GENERAL TOLERANCES AND EDGE-BREAK NOTES DO NOT APPLY."
    )
    purchase_note = _literal_note(adapter, purchase_text, 0.018, 0.072)
    notes.append((purchase_note, purchase_text))
    for name, y, label in (
        ("Stock Name", 0.050, "STOCK:"),
        ("Supplier", 0.038, "SUPPLIER:"),
        ("Supplier SKUs", 0.026, "SKU:"),
    ):
        label_note = _literal_note(adapter, label, 0.018, y)
        notes.append((label_note, label))
        linked = add_property_linked_note(adapter, name, 0.052, y, char_height=0.003)
        notes.append((linked, properties[name]))
        linked_notes.append((linked, property_link(name), properties[name]))

    _rebuild(draw, phase="washer linked notes and native references")
    for note, linked_text, resolved_text in title_block_notes:
        if note.PropertyLinkedText != linked_text or note.GetText() != resolved_text:
            raise RuntimeError(
                f"washer title-block property did not resolve: {linked_text!r}"
            )
    for note, linked_text, resolved_text in linked_notes:
        if (
            note.PropertyLinkedText != linked_text
            or note.GetText().replace("\r\n", "\n") != resolved_text
        ):
            raise RuntimeError(
                f"washer linked property did not resolve: {linked_text!r}"
            )

    actual_views = list(iter_views(adapter))
    orientations = tuple(view.GetOrientationName() for view in actual_views)
    expected_orientations = {name for name, _center, _cell in _VIEW_CELLS}
    if len(actual_views) != 3 or set(orientations) != expected_orientations:
        raise RuntimeError(f"washer drawing views are not the compact set: {orientations!r}")
    views_by_orientation = dict(zip(orientations, actual_views, strict=True))
    region = sheet_drawable_region(
        adapter,
        sheet,
        width=template.width_m,
        height=template.height_m,
    )
    border = (region.xmin, region.ymin, region.xmax, region.ymax)
    for name, _center, cell in _VIEW_CELLS:
        view = views_by_orientation[name]
        if Path(view.GetReferencedModelName()).resolve() != source.resolve():
            raise RuntimeError(f"{name}: washer view references the wrong model")
        if tuple(view.ScaleRatio) != scale:
            raise RuntimeError(f"{name}: washer view scale changed")
        box = _box(view.GetOutline(), label=name)
        if not _inside(box, cell) or not _inside(box, border):
            raise RuntimeError(f"{name}: washer view leaves its cell/border: {box!r}")
    for note, expected_text in notes:
        actual_text = note.GetText().replace("\r\n", "\n")
        if actual_text != expected_text:
            raise RuntimeError(
                f"washer note readback mismatch: {actual_text!r} != {expected_text!r}"
            )
        box = _box(note.GetExtent(), label=expected_text, kind="note")
        if not _inside(box, border):
            raise RuntimeError(
                f"washer note leaves the drawable border: {expected_text!r}: {box!r}"
            )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title=title,
        scale=scale,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
