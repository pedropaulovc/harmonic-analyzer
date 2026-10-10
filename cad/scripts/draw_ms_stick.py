r"""Two-sheet manufacturing package for the unchanged graduated brass stick.

BAR gives the envelope and scale stations. GRADUATIONS enlarges a full
interval, its tenths, longer half tick and numeral. A Top-view detail shows
the square-bottom groove where it opens at the bar's long edge. Native probes
import TickDepth in Top but not in a removed cut-only section, even with the
same genuine, marked cut owner selected exactly once. All sizes, bands and
places come from the part.
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
    stamp_drawing_summary, view_name,
)
from _drawing_hidden_sketches import curate_view_dimensions, part_sketches_shown
from _drawing_registry import DRAWINGS_BY_NAME
from _ms_drawing_contract import assert_manufacturing_dimensions
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view

SPEC = DRAWINGS_BY_NAME["ms_stick"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"])
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_NAMES = ("BAR", "GRADUATIONS")
SHEET_SCALE = (1.0, 1.0)
FRONT_CENTER = (0.122, 0.215)
TOP_CENTER = (FRONT_CENTER[0], 0.155)
ISO_CENTER = (0.300, 0.130)
DETAIL_PARENT_CENTER = (0.230, 0.240)
DETAIL_CENTER = (0.180, 0.155)
DETAIL_SCALE = (6.0, 1.0)
DETAIL_RADIUS_MM = 13.0
DEPTH_PARENT_CENTER = (0.230, 0.080)
DEPTH_CENTER = (0.350, 0.160)
DEPTH_RADIUS_MM = 2.0
FRONT_KEEP = {
    "BodyLength": (0.122, 0.240), "BodyWidth": (0.250, 0.215),
    "ScaleStartX": (0.052, 0.190), "ScaleEndMargin": (0.240, 0.190),
}
TOP_KEEP = {"BodyThickness": (0.245, 0.155)}
DETAIL_KEEP = {
    "Tick0Width": (0.120, 0.108),
    "FullTickLength": (0.078, 0.156),
    "MinorTickLength": (0.057, 0.176),
    "HalfTickLength": (0.275, 0.160),
    "FullTickPitch": (0.180, 0.215),
    "MinorTickPitch": (0.145, 0.195),
    "NumeralHeight": (0.135, 0.095),
    "NumeralXGap": (0.102, 0.080),
    "NumeralYGap": (0.285, 0.125),
}
DEPTH_KEEP = {"TickDepth": (0.350, 0.215)}
DIMENSION_CALLOUTS = {
    "Tick0Width": "ALL GRADUATIONS",
    "TickDepth": "ALL ENGRAVING\nSQUARE BOTTOM",
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


@_telemetry.traced("drawing.ms_scale_labels")
def _add_scale_labels(adapter: Any, front: Any) -> None:
    """These are engraved scale values, not invented dimensional annotations."""
    for value in range(part.DIVISION_COUNT):
        x, y = model_point_in_view(
            adapter, front, ((part.SCALE_START_X + value * part.DIVISION_SPACING) / 1000.0,
                             part.BODY_WIDTH / 1000.0, 0.0), label="engraved scale value")
        if add_note(adapter, str(value), x, y - 0.010) is None:
            raise RuntimeError(f"failed to label engraved scale value {value}")


@_telemetry.traced("drawing.ms_engraving_detail", label_param="detail_label")
def _engraving_detail(
    adapter: Any, parent: Any, *, model_center: tuple[float, float, float],
    view_xy: tuple[float, float], radius_mm: float, detail_label: str,
) -> Any:
    """Fence A/B through their native view sketches; both parents are 1:2."""
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
    _add_scale_labels(adapter, front)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.025, 0.100)
    add_property_linked_note(adapter, "Front View Note", 0.040, 0.178)
    add_property_linked_note(adapter, "Isometric View Note", 0.250, 0.090)

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
