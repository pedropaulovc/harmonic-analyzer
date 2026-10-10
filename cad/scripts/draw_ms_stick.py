r"""Four-sheet manufacturing package for the unchanged graduated brass stick.

BAR gives the envelope and left-origin scale station. GRADUATIONS enlarges
the full/minor pitch; TICK LENGTHS gives groove width and each length a local
detail without cross-strip extension lines. ENGRAVING separates numeral
dimensions from the open-edge Top detail for the square-bottom groove depth.
Native probes import TickDepth in Top but not in a removed cut-only section.
All sizes, bands and places come from the part; scale is never shrunk to fit.
Part-spec coordinates are millimetres; model-point projection takes metres.
Drawing-sheet positions and projected fence coordinates are also metres.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
import ms_stick_spec as part
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs, add_property_linked_note, create_blank_drawing_sheets,
    finalize_drawing, model_point_in_view, new_project_drawing,
    read_required_properties, set_dimension_callouts, set_hidden_lines_removed,
    rebuild_drawing, stamp_drawing_summary, view_name,
)
from _drawing_hidden_sketches import curate_view_dimensions, part_sketches_shown
from _drawing_registry import DRAWINGS_BY_NAME
from _ms_drawing_contract import assert_manufacturing_dimensions
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import place_view

SPEC = DRAWINGS_BY_NAME["ms_stick"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"])
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_NAMES = ("BAR", "GRADUATIONS", "TICK LENGTHS", "ENGRAVING")
SHEET_SCALE = (1.0, 1.0)
FRONT_CENTER = (0.145, 0.190)
TOP_CENTER = (FRONT_CENTER[0], 0.125)
ISO_CENTER = (0.335, 0.160)
DETAIL_PARENT_CENTER = (0.230, 0.245)
DETAIL_CENTER = (0.180, 0.140)
DETAIL_SCALE = (6.0, 1.0)
DETAIL_RADIUS_MM = 9.0
DEPTH_PARENT_CENTER = (0.330, 0.245)
DEPTH_CENTER = (0.330, 0.160)
DEPTH_RADIUS_MM = 2.0
NUMERAL_PARENT_CENTER = (0.130, 0.245)
NUMERAL_CENTER = (0.140, 0.170)
NUMERAL_RADIUS_MM = 3.5
FRONT_KEEP = {
    "BodyLength": (0.145, 0.220), "BodyWidth": (0.265, 0.190),
    "ScaleStartX": (0.075, 0.165),
}
TOP_KEEP = {"BodyThickness": (0.265, 0.145)}
DETAIL_KEEP = {
    "FullTickPitch": (0.180, 0.218),
    "MinorTickPitch": (0.145, 0.085),
}
# Local fences keep extension lines beside their tick; D excludes tick zero.
LENGTH_DETAILS = (
    ("C", (0.100, 0.245), (0.105, 0.155),
     (part.SCALE_START_X, part.BODY_WIDTH - part.TICK_LENGTH / 2.0),
     {"FullTickLength": (0.075, 0.180), "Tick0Width": (0.075, 0.215)}, 4.0),
    ("D", (0.215, 0.245), (0.220, 0.155),
     (part.SCALE_START_X + part.MINOR_SPACING, part.BODY_WIDTH - part.MINOR_TICK_LENGTH / 2.0),
     {"MinorTickLength": (0.190, 0.180)}, 1.1),
    ("E", (0.330, 0.245), (0.335, 0.155),
     (part.SCALE_START_X + part.DIVISION_SPACING / 2.0, part.BODY_WIDTH - part.HALF_TICK_LENGTH / 2.0),
     {"HalfTickLength": (0.300, 0.185)}, 4.0),
)
NUMERAL_KEEP = {
    "NumeralHeight": (0.145, 0.218),
    "NumeralXGap": (0.095, 0.120),
    "NumeralYGap": (0.095, 0.190),
}
DEPTH_KEEP = {"TickDepth": (0.330, 0.215)}
DIMENSION_CALLOUTS = {
    "Tick0Width": "ALL GRADUATIONS",
    "TickDepth": "ALL ENGRAVING\nSQUARE-BOTTOM GROOVES",
    "FullTickLength": "FULL TICKS",
    "MinorTickLength": "MINOR TICKS",
    "HalfTickLength": "HALF-DIVISION TICK",
    "FullTickPitch": "FULL TICKS\nNONCUMULATIVE FROM SCALE ZERO",
    "MinorTickPitch": "MINOR TICKS\nNONCUMULATIVE FROM SCALE ZERO",
    "NumeralHeight": "NUMERAL HEIGHT",
    "NumeralXGap": "NUMERAL TO TICK EDGE",
    "NumeralYGap": "NUMERAL TO FULL-TICK END",
}


@_telemetry.traced("drawing.ms_ruled_face")
def _rotate_ruled_face(adapter: Any, view: Any) -> None:
    """Keep the existing -Z read: scale zero left, graduations at lower edge."""
    view = _early_bound(view, "IView")
    view.Angle = math.pi
    if abs(abs(float(view.Angle)) - math.pi) > 1e-9:
        raise RuntimeError("failed to rotate measuring-stick ruled face")
    adapter.currentModel.EditRebuild3()



@_telemetry.traced("drawing.ms_engraving_detail", label_param="detail_label")
def _engraving_detail(
    adapter: Any, parent: Any, *, model_center: tuple[float, float, float],
    view_xy: tuple[float, float], radius_mm: float, detail_label: str,
) -> Any:
    """Fence a useful-scale detail and move its parent letter off the strip."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(parent, "IView")
    if not ddoc.ActivateView(view_name(adapter, parent)):
        raise RuntimeError(f"cannot activate engraving detail {detail_label} parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter, parent, model_center, label=f"engraving detail {detail_label} centre")
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    radius = radius_mm * 0.5 / 1000.0
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError(f"failed to draw engraving detail {detail_label} fence")
    detail = ddoc.CreateDetailViewAt4(*view_xy, 0.0, 0, *DETAIL_SCALE,
                                    detail_label, 1, True, False, False, 5)
    if detail is None:
        raise RuntimeError(f"failed to create engraving detail {detail_label}")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array(list(DETAIL_SCALE))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    circles = tuple(parent.GetDetailCircles() or ())
    matching = [
        _early_bound(circle, "IDetailCircle") for circle in circles
        if _early_bound(circle, "IDetailCircle").GetLabel() == detail_label
    ]
    if len(matching) != 1:
        raise RuntimeError(f"detail {detail_label}: expected one matching parent circle")
    letter_xy = (center[0], center[1] + 0.015)
    matching[0].SetLabelPosition(*letter_xy)
    rebuild_drawing(adapter, label=f"place detail {detail_label} parent letter")
    actual = tuple(float(value) for value in matching[0].GetLabelPosition())
    if len(actual) != 2 or math.dist(actual, letter_xy) > 1e-8:
        raise RuntimeError(f"detail {detail_label}: parent letter placement rejected: {actual}")
    return detail


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source measuring stick missing: {SOURCE}")
    check("open measuring stick", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    properties = ("Number", "Revision", "Title", "Material Specification", "Finish",
                  "Quantity", "Manufacturing Notes", "Front View Note", "Isometric View Note")
    read_required_properties(source_model, properties, required=properties)
    drawing, _sheet = new_project_drawing(adapter, property_view=PART_STEM,
                                        scale=SHEET_SCALE, layout=SPEC.layout)
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="measuring stick manufacturing package")
    stamp_drawing_summary(adapter, drawing, {
        0: "Measuring Stick Manufacturing Drawing",
        1: "Harmonic Analyzer hobby-machinist book drawing",
        2: "Harmonic Analyzer Project", 3: "graduated brass gauge; envelope and engraving",
        4: "Generated from the project-owned ASME B drawing standard",
    })
    ddoc = _early_bound(drawing, "IDrawingDoc")
    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate stick envelope sheet")
    front = place_view(adapter, str(SOURCE), "*Back", *FRONT_CENTER, scale=SHEET_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1.0, 2.0))
    _rotate_ruled_face(adapter, front)
    for view in (front, top, iso):
        set_hidden_lines_removed(adapter, view)
    annotations = []
    for view, keep, label in ((front, FRONT_KEEP, "ruled bar"), (top, TOP_KEEP, "bar edge")):
        annotations += curate_view_dimensions(adapter, view, keep=keep, view_label=label,
                                               dimensions_by_feature=part.DRAWING_DIMENSIONS)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.045, 0.085)
    add_property_linked_note(adapter, "Front View Note", 0.045, 0.153)
    add_property_linked_note(adapter, "Isometric View Note", 0.285, 0.110)

    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate engraving sheet")
    parent = place_view(adapter, str(SOURCE), "*Back", *DETAIL_PARENT_CENTER, scale=(1.0, 2.0))
    _rotate_ruled_face(adapter, parent)
    set_hidden_lines_removed(adapter, parent)
    owners = tuple(feature for feature, names in part.DRAWING_DIMENSIONS.items()
                   if feature in part.REFERENCE_DIMENSIONS and names & set(DETAIL_KEEP))
    with part_sketches_shown(adapter, source_model, owners,
                            label="graduation dimensions", base_view=parent):
        detail = _engraving_detail(
            adapter, parent,
            model_center=((part.SCALE_START_X + part.DIVISION_SPACING / 2.0) / 1000.0,
                          part.BODY_WIDTH / 2000.0, 0.0),
            view_xy=DETAIL_CENTER, radius_mm=DETAIL_RADIUS_MM, detail_label="A")
        set_hidden_lines_removed(adapter, detail)
        annotations += curate_view_dimensions(adapter, detail, keep=DETAIL_KEEP,
                                               view_label="graduation detail",
                                               dimensions_by_feature=part.DRAWING_DIMENSIONS)

    if not ddoc.ActivateSheet(SHEET_NAMES[2]):
        raise RuntimeError("failed to activate tick lengths sheet")
    for label, parent_xy, detail_xy, model_xy, keep, radius_mm in LENGTH_DETAILS:
        length_parent = place_view(adapter, str(SOURCE), "*Back", *parent_xy, scale=(1.0, 2.0))
        _rotate_ruled_face(adapter, length_parent)
        set_hidden_lines_removed(adapter, length_parent)
        owners = tuple(feature for feature, names in part.DRAWING_DIMENSIONS.items()
                       if feature in part.REFERENCE_DIMENSIONS and names & set(keep))
        with part_sketches_shown(adapter, source_model, owners,
                                label=f"tick length {label}", base_view=length_parent):
            length_detail = _engraving_detail(
                adapter, length_parent,
                model_center=(model_xy[0] / 1000.0, model_xy[1] / 1000.0, 0.0),
                view_xy=detail_xy, radius_mm=radius_mm, detail_label=label)
            set_hidden_lines_removed(adapter, length_detail)
            annotations += curate_view_dimensions(
                adapter, length_detail, keep=keep, view_label=f"tick length {label}",
                dimensions_by_feature=part.DRAWING_DIMENSIONS)

    if not ddoc.ActivateSheet(SHEET_NAMES[3]):
        raise RuntimeError("failed to activate engraving sheet")
    numeral_parent = place_view(
        adapter, str(SOURCE), "*Back", *NUMERAL_PARENT_CENTER, scale=(1.0, 2.0))
    _rotate_ruled_face(adapter, numeral_parent)
    set_hidden_lines_removed(adapter, numeral_parent)
    owners = tuple(feature for feature, names in part.DRAWING_DIMENSIONS.items()
                   if feature in part.REFERENCE_DIMENSIONS and names & set(NUMERAL_KEEP))
    with part_sketches_shown(adapter, source_model, owners,
                            label="numeral dimensions", base_view=numeral_parent):
        numeral = _engraving_detail(
            adapter, numeral_parent,
            model_center=((part.SCALE_START_X + part.TICK_WIDTH / 2.0
                           + part.NUMERAL_GAP_MM + part.NUMERAL_HEIGHT_MM / 2.0) / 1000.0,
                          (part.BODY_WIDTH - part.TICK_LENGTH - part.NUMERAL_GAP_MM) / 1000.0, 0.0),
            view_xy=NUMERAL_CENTER, radius_mm=NUMERAL_RADIUS_MM, detail_label="F")
        set_hidden_lines_removed(adapter, numeral)
        annotations += curate_view_dimensions(
            adapter, numeral, keep=NUMERAL_KEEP, view_label="numeral detail",
            dimensions_by_feature=part.DRAWING_DIMENSIONS)
    depth_parent = place_view(
        adapter, str(SOURCE), "*Top", *DEPTH_PARENT_CENTER, scale=(1.0, 2.0))
    set_hidden_lines_removed(adapter, depth_parent)
    depth = _engraving_detail(
        adapter, depth_parent,
        model_center=(part.SCALE_START_X / 1000.0, part.BODY_WIDTH / 1000.0,
                      part.BODY_THICKNESS / 2000.0),
        view_xy=DEPTH_CENTER, radius_mm=DEPTH_RADIUS_MM, detail_label="B")
    set_hidden_lines_removed(adapter, depth)
    annotations += curate_view_dimensions(adapter, depth, keep=DEPTH_KEEP,
                                           view_label="engraving depth detail",
                                           dimensions_by_feature=part.DRAWING_DIMENSIONS)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_manufacturing_dimensions(
        adapter, annotations, part.DRAWING_VALUES_BY_NAME, part.DRAWING_PRECISION_BY_NAME,
        bands={name: (-tolerance, tolerance) for name, tolerance in part.DRAWING_TOLERANCES.items()},
    )
    for view in (parent, detail, depth_parent, depth):
        set_hidden_lines_removed(adapter, view)
    return await finalize_drawing(adapter, OUTPUTS, pdf_title="Measuring Stick Manufacturing Drawing",
                                  scale=SHEET_SCALE, layout=SPEC.layout,
                                  expected_sheet_names=SHEET_NAMES,
                                  sheet_layouts={name: SPEC.layout for name in SHEET_NAMES})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
