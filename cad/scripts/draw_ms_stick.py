r"""Four-sheet manufacturing package for the unchanged graduated brass stick.

BAR gives the envelope and left-origin scale station. GRADUATIONS enlarges
the full/minor pitch; TICK LENGTHS gives groove width and each length a local
detail without cross-strip extension lines. ENGRAVING separates numeral
dimensions from the open-edge Top detail for the square-bottom groove depth.
The numeral detail and its dimensions leave air at the left border, with its
placement note below the detail title and scale. Section G-G cuts the whole
8 x 3 bar across both strokes of the zero numeral, so the true V grooves read
in profile, and imports NumeralDepth there; its callout names the V angle.
Native probes import TickDepth in Top but not in a removed cut-only section,
so G-G is a full section (with hidden lines removed only the cut face shows).
All sizes, bands and places come from the part; scale is never shrunk to fit.
Part-spec coordinates are millimetres; model-point projection takes metres.
Drawing-sheet positions and projected fence coordinates are also metres.

This replaces draw_ha_measuring_stick without a legacy entry point: its
split-common check, path and session imports live here, while ruled-face
orientation, source-linked notes and native dimensions retain the current
four-sheet manufacturing contract.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
import ms_stick_spec as part
from _check import check
from _com import _early_bound
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
    view_name,
)
from _drawing_dimensions import set_dimension_callouts
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_sections import create_section_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _drawing_hidden_sketches import curate_view_dimensions, part_sketches_shown
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _ms_drawing_contract import assert_manufacturing_dimensions
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import place_view

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ms_stick"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"])
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_NAMES = ("BAR", "GRADUATIONS", "TICK LENGTHS", "ENGRAVING")
SHEET_SCALE = (1.0, 1.0)
FRONT_CENTER = (0.155, 0.175)
TOP_CENTER = (FRONT_CENTER[0], 0.110)
# r2-r3 sheet 1: the 8.00 dimension line's tail touched the isometric at x 0.335.
ISO_CENTER = (0.355, 0.145)
DETAIL_PARENT_CENTER = (0.230, 0.245)
DETAIL_CENTER = (0.180, 0.140)
DETAIL_SCALE = (6.0, 1.0)
DETAIL_RADIUS_MM = 9.0
DEPTH_PARENT_CENTER = (0.330, 0.210)
# r1-r3 sheet 4: at 6:1 the 0.40 x 0.50 groove could not be read; 15:1 can.
DEPTH_CENTER = (0.375, 0.120)
DEPTH_SCALE = (15.0, 1.0)
DEPTH_RADIUS_MM = 1.6
NUMERAL_PARENT_CENTER = (0.130, 0.210)
# r4 sheet 4: full-tick-end callout starts 62 mm left of its placement.
# Shift the entire detail/dimension group right without changing its scale.
NUMERAL_CENTER = (0.165, 0.135)
# The fence includes the real full-tick endpoint and both numeral gap anchors.
NUMERAL_RADIUS_MM = 7.0
NUMERAL_NOTE_XY = (0.045, 0.068)
# A 1:1 parent spreads the across-the-bar cutting line (and its two arrows)
# over a readable 11 mm instead of a 1:2 nick.
NUMERAL_PROFILE_PARENT_CENTER = (0.200, 0.250)
NUMERAL_PROFILE_CENTER = (0.280, 0.125)
# The 0.40 mm V must read as a profile; 10:1 keeps the full 8 x 3 bar on sheet.
NUMERAL_PROFILE_SCALE = (10.0, 1.0)
# Mid-height of the zero numeral: the cut crosses both of its straight side
# strokes square, and no graduation (the nearest minor tick ends 0.18 short).
NUMERAL_SECTION_X = (part.SCALE_START_X + part.TICK_WIDTH / 2.0 + part.NUMERAL_GAP_MM
                     + part.NUMERAL_HEIGHT_MM / 2.0)
# r1-r3 sheet 4: at 1.5 mm the G letters sat on their arrows and the outline.
NUMERAL_SECTION_OVERSHOOT_MM = 4.0
STOP_REBATE_FIT = "SLIDES IN MS-STOP-BLOCK\nMHA-MS-02 REBATE"
AMPLITUDE_STATIONS = "SETS CH-AMPLITUDE-BAR\nMHA-CH-01 STATIONS"
ENAMEL = "HOLDS ENAMEL FILL"
FRONT_KEEP = {
    "BodyLength": (0.155, 0.205), "BodyWidth": (0.305, 0.215),
    "ScaleStartX": (0.180, 0.150),
}
TOP_KEEP = {"BodyThickness": (0.275, 0.130)}
DETAIL_KEEP = {
    "FullTickPitch": (0.180, 0.218),
    "MinorTickPitch": (0.075, 0.085),
}
# Local fences keep extension lines beside their tick; D excludes tick zero.
LENGTH_DETAILS = (
    ("C", (0.100, 0.245), (0.105, 0.155),
     (part.SCALE_START_X, part.BODY_WIDTH - part.TICK_LENGTH / 2.0),
     {"FullTickLength": (0.075, 0.180), "Tick0Width": (0.075, 0.215)}, 4.0),
    ("D", (0.215, 0.245), (0.220, 0.155),
     (part.SCALE_START_X + part.MINOR_SPACING, part.BODY_WIDTH - part.MINOR_TICK_LENGTH / 2.0),
     {"MinorTickLength": (0.190, 0.180)}, 2.2),
    ("E", (0.330, 0.245), (0.335, 0.155),
     (part.SCALE_START_X + part.DIVISION_SPACING / 2.0, part.BODY_WIDTH - part.HALF_TICK_LENGTH / 2.0),
     {"HalfTickLength": (0.300, 0.185)}, 4.0),
)
NUMERAL_KEEP = {
    "NumeralHeight": (0.215, 0.183),
    "NumeralXGap": (0.100, 0.170),
    "NumeralYGap": (0.100, 0.155),
}
DEPTH_KEEP = {"TickDepth": (0.380, 0.175)}
# Text centre: the block ends left of G-G, its underside dimension line at the V.
NUMERAL_DEPTH_KEEP = {"NumeralDepth": (0.231, 0.138)}
DIMENSION_CALLOUTS = {
    "BodyWidth": STOP_REBATE_FIT,
    "BodyThickness": STOP_REBATE_FIT,
    "ScaleStartX": f"SCALE ZERO CENTRELINE\n{AMPLITUDE_STATIONS}",
    "Tick0Width": f"ALL GRADUATIONS\n{ENAMEL}",
    "TickDepth": f"GRADUATIONS ONLY, SQUARE-BOTTOM\n{ENAMEL}\n{part.GRADUATION_FLOOR_CALLOUT}",
    "FullTickLength": "FULL TICKS",
    "MinorTickLength": "MINOR TICKS",
    "HalfTickLength": "HALF-DIVISION TICK",
    "FullTickPitch": f"FULL TICK CENTRELINES\nNONCUMULATIVE FROM SCALE ZERO\n{AMPLITUDE_STATIONS}",
    "MinorTickPitch": f"MINOR TICK CENTRELINES\nNONCUMULATIVE FROM SCALE ZERO\n{AMPLITUDE_STATIONS}",
    "NumeralHeight": "NUMERAL HEIGHT",
    "NumeralXGap": "NUMERAL TO TICK EDGE",
    "NumeralYGap": "NUMERAL TO FULL-TICK END",
    "NumeralDepth": f"NUMERAL DEPTH\n{part.NUMERAL_V_INCLUDED_ANGLE_DEG:g}° INCLUDED V\n{ENAMEL}",
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
    scale: tuple[float, float] = DETAIL_SCALE,
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
    detail = ddoc.CreateDetailViewAt4(*view_xy, 0.0, 0, *scale,
                                    detail_label, 1, True, False, False, 5)
    if detail is None:
        raise RuntimeError(f"failed to create engraving detail {detail_label}")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array(list(scale))
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


def _numeral_profile(adapter: Any, parent: Any) -> Any:
    """Whole-bar full section across both straight side strokes of the zero numeral."""
    endpoints = tuple(
        model_point_in_view(
            adapter, parent, (NUMERAL_SECTION_X / 1000.0, y / 1000.0, 0.0),
            label="numeral stroke section endpoint",
        )
        for y in (-NUMERAL_SECTION_OVERSHOOT_MM, part.BODY_WIDTH + NUMERAL_SECTION_OVERSHOOT_MM)
    )
    section = create_section_view(
        adapter, parent, line_start=endpoints[0], line_end=endpoints[1],
        view_xy=NUMERAL_PROFILE_CENTER, section_label="G", scale=NUMERAL_PROFILE_SCALE,
        label="numeral V G-G",
    )
    section = _early_bound(section, "IView")
    section.UseParentScale = False
    section.ScaleRatio = double_array(list(NUMERAL_PROFILE_SCALE))
    definition = _early_bound(section.GetSection(), "IDrSection")
    definition.SetDisplayOnlySurfaceCut(False)
    rebuild_drawing(adapter, label="numeral G-G full section")
    if bool(definition.GetDisplayOnlySurfaceCut()) or bool(definition.GetPartialSection()):
        raise RuntimeError("numeral G-G must be a full section of the whole bar")
    set_hidden_lines_removed(adapter, section)
    if bool(section.UseParentScale) or tuple(float(value) for value in section.ScaleRatio) != NUMERAL_PROFILE_SCALE:
        raise RuntimeError("numeral G-G must retain its independent 10:1 scale")
    model_center = (
        NUMERAL_SECTION_X / 1000.0, part.BODY_WIDTH / 2000.0, part.BODY_THICKNESS / 2000.0,
    )
    actual = model_point_in_view(adapter, section, model_center, label="numeral G-G profile centre")
    if math.dist(actual, NUMERAL_PROFILE_CENTER) > 1e-8:
        position = tuple(float(value) for value in section.Position)
        target = [position[index] + NUMERAL_PROFILE_CENTER[index] - actual[index] for index in range(2)]
        if not section.SetViewPosition(double_array(target), False):
            raise RuntimeError("numeral G-G profile could not be centred")
        rebuild_drawing(adapter, label="centre numeral G-G profile")
        actual = model_point_in_view(adapter, section, model_center, label="numeral G-G placed centre")
        if math.dist(actual, NUMERAL_PROFILE_CENTER) > 1e-6:
            raise RuntimeError(f"numeral G-G profile centre drifted: {actual}")
    return section


def _assert_numeral_depth_owner(annotation: Any) -> None:
    """The imported depth must attach to Numerals, never to a graduation."""
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    if str(dimension.FullName).split("@")[:2] != ["NumeralDepth", "Numerals"]:
        raise RuntimeError(f"numeral depth imported from wrong feature: {dimension.FullName}")
    if abs(float(dimension.SystemValue) * 1000.0 - part.NUMERAL_DEPTH) > 1e-6:
        raise RuntimeError("numeral depth import does not read its V-engraved cut")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source measuring stick missing: {SOURCE}")
    check("open measuring stick", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    properties = ("Number", "Revision", "Title", "Material Specification", "Finish",
                  "Quantity", "Manufacturing Notes", "Front View Note", "Isometric View Note",
                  "Numeral Placement Note")
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
    add_property_linked_note(adapter, "Manufacturing Notes", 0.045, 0.075)
    add_property_linked_note(adapter, "Front View Note", 0.055, 0.135)
    add_property_linked_note(adapter, "Isometric View Note", 0.285, 0.095)

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
    add_property_linked_note(adapter, "Numeral Placement Note", *NUMERAL_NOTE_XY)
    profile_parent = place_view(
        adapter, str(SOURCE), "*Back", *NUMERAL_PROFILE_PARENT_CENTER, scale=SHEET_SCALE)
    _rotate_ruled_face(adapter, profile_parent)
    set_hidden_lines_removed(adapter, profile_parent)
    profile = _numeral_profile(adapter, profile_parent)
    numeral_depth_annotations = curate_view_dimensions(
        adapter, profile, keep=NUMERAL_DEPTH_KEEP, view_label="numeral V section",
        dimensions_by_feature=part.DRAWING_DIMENSIONS,
    )
    if len(numeral_depth_annotations) != 1:
        raise RuntimeError("expected one own model-linked numeral depth")
    _assert_numeral_depth_owner(numeral_depth_annotations[0])
    annotations += numeral_depth_annotations
    depth_parent = place_view(
        adapter, str(SOURCE), "*Top", *DEPTH_PARENT_CENTER, scale=(1.0, 2.0))
    set_hidden_lines_removed(adapter, depth_parent)
    depth = _engraving_detail(
        adapter, depth_parent,
        model_center=(part.SCALE_START_X / 1000.0, part.BODY_WIDTH / 1000.0,
                      part.BODY_THICKNESS / 2000.0),
        view_xy=DEPTH_CENTER, radius_mm=DEPTH_RADIUS_MM, detail_label="B", scale=DEPTH_SCALE)
    set_hidden_lines_removed(adapter, depth)
    annotations += curate_view_dimensions(adapter, depth, keep=DEPTH_KEEP,
                                           view_label="engraving depth detail",
                                           dimensions_by_feature=part.DRAWING_DIMENSIONS)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_manufacturing_dimensions(
        adapter, annotations, part.DRAWING_VALUES_BY_NAME, part.DRAWING_PRECISION_BY_NAME,
        bands={**{name: (-tolerance, tolerance) for name, tolerance in part.DRAWING_TOLERANCES.items()},
               **part.MIN_LIMIT_DEVIATIONS_MM},
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
