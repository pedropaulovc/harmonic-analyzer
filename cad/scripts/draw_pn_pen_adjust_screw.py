r"""Create the curated machinist drawing for the pen-height adjuster stud.

One side view, the *Right view turned so the stud lies as it is turned
(drawing-guidelines.md rule 11): threaded end left, eye head right, the X
cross hole seen end-on as a circle with its center mark and native #54 DRILL
callout. Every marked dimension (pn_pen_adjust_screw_spec.DRAWING_DIMENSIONS)
lives in a Right-plane sketch and imports here: the thread's major diameter
(printed as its #0-80 UNF designation), its usable full-thread length to the
thread-limit split edge, the plain shank's diameter as a parenthesised
reference, the head's diameter and height, the overall length, the eye's
station from the head's faced end (the hidden EyeStationReference sketch,
shown in this view only) and the shoulder root's fillet as a single R MAX
limit at the title block's INSIDE CORNERS row. A shaded isometric at the
sheet scale completes the package (rule 8).
No datums, frames or roughness symbols: the stud is not on the GD&T allowlist
(rule 5) and nothing on it runs or locates (rule 6). No general note: the
title block says all the stud needs.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import import_cosmetic_threads
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_dimension_text,
    set_reference_dimension,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import drill_process
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from pn_pen_adjust_screw_spec import (
    DIMENSION_CALLOUTS,
    DIMENSION_TEXT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    EYE_DIA,
    EYE_SPEC,
    EYE_Y,
    FULL_THREAD_LENGTH,
    HEAD_DIA,
    OVERALL_LENGTH,
    PLAIN_SHANK,
    REFERENCE_DIMENSIONS,
    SHANK_LENGTH,
    SHOULDER_FILLET_R,
    SHOULDER_FILLET_TOL_TYPE,
    THREAD_CALLOUT,
    THREAD_MAJOR,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pn_pen_adjust_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

# Every view prints at the sheet scale, so none needs a caption. 6:1 lays the
# 26 mm stud 156 mm long, its Ø6 head 36 mm across and the #54 eye 8 mm.
SHEET_SCALE = (6.0, 1.0)
VIEW_SCALE = (6, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet metres per model mm
# The *Right view faces the Right-plane sketches (so their dimensions import)
# and sees the X cross hole end-on; a quarter turn clockwise sends model +Y
# (threaded end -> head) to paper right.
SIDE_CENTER = (0.150, 0.165)
SIDE_VIEW_ANGLE = -math.pi / 2.0
# 26 mm along model Y foreshortens to ~127 mm on the isometric; with the head
# ellipses it spans ~145 mm, so its centre sits 5 mm under the old 0.190 to
# keep ~10 mm from the top border (y 0.267) and clear of the title block
# (top y 0.065).
ISO_CENTER = (0.335, 0.185)
AXIS_Y = SIDE_CENTER[1]


def sheet_x(model_y_mm: float) -> float:
    """Sheet X of a model-Y station on the side view, as laid out (the view
    is centred on the stud's length)."""
    return SIDE_CENTER[0] + (model_y_mm - OVERALL_LENGTH / 2.0) * _S


THREAD_END_X = sheet_x(0.0)
FULL_THREAD_X = sheet_x(FULL_THREAD_LENGTH)
SHOULDER_X = sheet_x(SHANK_LENGTH)
EYE_X = sheet_x(EYE_Y)
TOP_X = sheet_x(OVERALL_LENGTH)
THREAD_HALF = THREAD_MAJOR / 2.0 * _S
HEAD_HALF = HEAD_DIA / 2.0 * _S
EYE_HALF = EYE_DIA / 2.0 * _S
PLAIN_MID_X = sheet_x(FULL_THREAD_LENGTH + PLAIN_SHANK / 2.0)

# Lengths (rules 10/11), all below the profile except the eye's station, so
# the profile's half-section dimensions (drawn on the sheet's lower half) send
# their extension lines down off the part:
# - row 1: the full thread from the faced threaded end to the thread-limit
#   edge, and the head from its shoulder to its faced end; 18 mm of clear
#   paper between the two runs' inner extension lines;
# - row 2, 18 mm lower so the FULL THREAD callout under row 1's line has
#   room: the overall, end to end. Its extension lines run collinear with row
#   1's outer ones, so no extension line crosses a dimension line.
# Above the head, the eye's station from the head's faced end: one extension
# line rises from the eye's centre (through its center mark), the other along
# the faced end. The thread's Ø line (printed as the thread designation)
# stands below the thread, short of row 1; the head's Ø right of the faced
# end, between its extension lines.
# The plain shank's reference Ø, (Ø1.52), stands ABOVE the plain shank on its
# mid-station: PlainDia hangs on the shoulder corner, so its extension lines
# run back along the two flank silhouettes from the shoulder to the
# dimension line, which rises from the flanks to the text. Below the shank
# the FullThreadLength extension line drops from the split edge to row 1 and
# would strike its text. 26 mm over the axis puts the text 8 mm above the
# head's top silhouette (AXIS_Y + 18 mm), left of the head (shoulder at
# PLAIN_MID_X + 9 mm) and 12 mm under the eye callout's text row; the eye
# leader leaves that text at EYE_X - 20 mm, 13 mm right of this line.
_ROW_1_Y = AXIS_Y - 0.032
_ROW_2_Y = AXIS_Y - 0.050
_ROW_ABOVE_Y = AXIS_Y + 0.035
SIDE_KEEP = {
    "FullThreadLength": ((THREAD_END_X + FULL_THREAD_X) / 2.0, _ROW_1_Y),
    "HeadHeight": ((SHOULDER_X + TOP_X) / 2.0, _ROW_1_Y),
    "OverallLength": ((THREAD_END_X + TOP_X) / 2.0, _ROW_2_Y),
    "EyeFromHeadEnd": ((EYE_X + TOP_X) / 2.0, _ROW_ABOVE_Y),
    "ThreadDia": (sheet_x(6.0), AXIS_Y - 0.016),
    "PlainDia": (PLAIN_MID_X, AXIS_Y + 0.026),
    "HeadDia": (TOP_X + 0.021, AXIS_Y),
    "ShoulderRadius": (SHOULDER_X - 0.015, AXIS_Y - 0.0435),
}
# The shoulder root's R MAX (rules 11 and 16). SolidWorks hangs the imported
# fillet radius on one of the two arcs the turned corner draws (upper or lower
# flank); which one is the seat's choice, so _dress_shoulder_radius reads the
# arrow back and lays out for that side.
# Lower arc (SIDE_KEEP): the ~18 mm "R.040 MAX" hangs UNDER row 1, centred
#   in the band between the head height's line and the overall length's text,
#   15 mm left of the shoulder; its leader leaves the text's right end and
#   climbs to the corner left of the head-height extension line.
# Upper arc (UPPER_ARC_KEEP): PlainDia's line (x PLAIN_MID_X, rising from the
#   flanks to its text) would cut that leader, so the two trade sides. The R
#   text stands up-left of the upper corner, 21 mm over the axis, its leader
#   running down-right into the corner over the bare flank; (Ø.060)'s line
#   drops between the two extension lines to its text in the band under row 1.
UPPER_ARC_KEEP = {
    "ShoulderRadius": (SHOULDER_X - 0.020, AXIS_Y + 0.021),
    "PlainDia": (PLAIN_MID_X, AXIS_Y - 0.045),
}
# An arrow on the fillet arc or its extension circle stands within
# (1 + sqrt 2) R of the sharp corner it rounds (14.7 mm at 6:1 for R.040);
# which flank it hangs on is the side of the axis the arrow lands.
_CORNER_REACH = (1.0 + math.sqrt(2.0)) * SHOULDER_FILLET_R * _S + 0.001
# The native Hole Wizard Ø variable of the #54 eye's drill callout.
EYE_CALLOUT_PRECISION = {"hw-diam": 3}
# The eye callout stands up and LEFT of the eye, above the bare thread (the
# old up-and-right place dropped its leader through the station dimension's
# line, rule 14). SolidWorks hangs the leader off the text end nearer the
# hole -- the right end, ~59 mm of "#54 DRILL Ø1.40 THRU ALL" (measured on the
# 20261013T222120 sheet) right of a centred text box -- so that end stands
# 20 mm left of the eye's center. The leader then runs down-right into the
# rim on the eye's centre line from the text end: it crosses only the head's
# top silhouette, left of the station dimension's extension line through the
# eye's centre, and stays under the station dimension's row.
_EYE_CALLOUT_TEXT_WIDTH = 0.059
EYE_CALLOUT_XY = (EYE_X - 0.020 - _EYE_CALLOUT_TEXT_WIDTH / 2.0, AXIS_Y + 0.038)
_EYE_LEADER_DX = (EYE_CALLOUT_XY[0] + _EYE_CALLOUT_TEXT_WIDTH / 2.0) - EYE_X
_EYE_LEADER_DY = EYE_CALLOUT_XY[1] - AXIS_Y
_EYE_LEADER_LEN = math.hypot(_EYE_LEADER_DX, _EYE_LEADER_DY)
EYE_RIM_PICK = (
    EYE_X + EYE_HALF * _EYE_LEADER_DX / _EYE_LEADER_LEN,
    AXIS_Y + EYE_HALF * _EYE_LEADER_DY / _EYE_LEADER_LEN,
)
# A point on the thread's face between the thread's Ø line and the
# thread-limit edge.
CENTERLINE_PICK = (sheet_x(10.0), AXIS_Y + THREAD_HALF / 2.0)


def _shift(
    points: dict[str, tuple[float, float]], dx: float, dy: float
) -> dict[str, tuple[float, float]]:
    return {name: (x + dx, y + dy) for name, (x, y) in points.items()}


def _arrow_tips(display: Any) -> list[tuple[float, float]]:
    """The rebuilt sheet points of a display dimension's arrow tips
    (draw_mg_output_fixture._prove_groove_radius's IDisplayData read)."""
    raw = display.GetDisplayData()
    if raw is None:
        raise RuntimeError("ShoulderRadius has no rebuilt display data")
    data = _early_bound(raw, "IDisplayData")
    tips = []
    for index in range(int(data.GetArrowHeadCount())):
        arrow = tuple(float(v) for v in data.GetArrowHeadAtIndex2(index))
        if len(arrow) != 12 or not all(math.isfinite(v) for v in arrow):
            raise RuntimeError("ShoulderRadius has incomplete arrow-head coordinates")
        tips.append((arrow[0], arrow[1]))
    if not tips:
        raise RuntimeError("ShoulderRadius draws no arrow")
    return tips


def _shoulder_arc_side(display: Any, corners: dict[str, tuple[float, float]]) -> str:
    """Which shoulder corner ("upper"/"lower") the radius's arrow lands on:
    the side of the turning axis (midway between the corners) it stands."""
    axis_y = (corners["upper"][1] + corners["lower"][1]) / 2.0
    tip = min(
        _arrow_tips(display),
        key=lambda t: min(math.dist(t, corner) for corner in corners.values()),
    )
    side = "upper" if tip[1] > axis_y else "lower"
    distance = math.dist(tip, corners[side])
    if distance > _CORNER_REACH:
        raise RuntimeError(
            f"ShoulderRadius arrow lands {distance * 1000.0:.1f} mm from the "
            f"{side} shoulder corner"
        )
    return side


def _dress_shoulder_radius(
    adapter: Any,
    drawing_model: Any,
    by_name: dict[str, Any],
    spt: Any,
) -> None:
    """Prove the side view's imported ShoulderRadius prints the part's R MAX,
    stop its leader at the corner and lay it out for the arc it landed on.

    Read back: radial (not a diameter), measuring SHOULDER_FILLET_R, the
    native swTolMAX the part set. The text stands outside the arc's own
    quadrant (the corner's material fills that ray), so
    ``ArcExtensionLineOrOppositeSide`` True carries the leader on to the
    drawn arc instead of stopping on its undrawn circle in empty paper (the
    19efce6a4 sheet's finding); the arc centre it passes stands in open paper
    off the shank and the head's face. SIDE_KEEP lays the text out for
    the lower arc; on the upper one UPPER_ARC_KEEP moves it and PlainDia, and
    the rebuilt arrow must still land on that corner.
    """
    annotation = _early_bound(by_name["ShoulderRadius"], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError("the imported shoulder radius is not radial")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(tolerance.Type) != SHOULDER_FILLET_TOL_TYPE:
        raise RuntimeError(
            f"ShoulderRadius lost its native MAX type: {int(tolerance.Type)}"
        )
    if not math.isclose(
        float(dimension.SystemValue), SHOULDER_FILLET_R / 1000.0, abs_tol=1e-9
    ):
        raise RuntimeError("ShoulderRadius does not measure the shoulder fillet")
    display.ArcExtensionLineOrOppositeSide = True
    if display.ArcExtensionLineOrOppositeSide is not True:
        raise RuntimeError("ShoulderRadius leader does not reach the drawn arc")
    drawing_model.EditRebuild3()
    corners = {
        "upper": spt(SHOULDER_X, AXIS_Y + THREAD_HALF),
        "lower": spt(SHOULDER_X, AXIS_Y - THREAD_HALF),
    }
    side = _shoulder_arc_side(display, corners)
    if side == "upper":
        for name, xy in UPPER_ARC_KEEP.items():
            moved = _early_bound(by_name[name], "IAnnotation")
            if not moved.SetPosition(*spt(*xy), 0.0):
                raise RuntimeError(f"{name} refused its upper-arc position")
        drawing_model.EditRebuild3()
        if _shoulder_arc_side(display, corners) != "upper":
            raise RuntimeError("ShoulderRadius left the upper corner when moved")
    _telemetry.info(
        f"shoulder radius: text {display.GetText(1)!r}, MAX type, {side} arc"
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open adjuster-stud source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen Adjuster Stud Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: f"pen adjuster stud; {THREAD_CALLOUT}; cross-drilled eye; brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    native = _early_bound(side, "IView")
    native.Angle = SIDE_VIEW_ANGLE
    if abs(math.remainder(float(native.Angle) - SIDE_VIEW_ANGLE, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to rotate the adjuster-stud side view")
    drawing_model.EditRebuild3()
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (side, iso):
        set_hidden_lines_removed(adapter, view)

    # Every layout constant is authored about the threaded end landing at
    # (THREAD_END_X, AXIS_Y); track wherever SolidWorks actually put it.
    origin = model_point_in_view(
        adapter, side, (0.0, 0.0, 0.0), label="adjuster-stud threaded end"
    )
    dx, dy = origin[0] - THREAD_END_X, origin[1] - AXIS_Y

    def spt(x: float, y: float) -> tuple[float, float]:
        return (x + dx, y + dy)

    annotations = curate_view_dimensions(
        adapter,
        side,
        keep=_shift(SIDE_KEEP, dx, dy),
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # The thread's major-diameter dimension reads as its designation (the
    # thread callout, associative to the profile), and the full-thread length
    # says what it bounds.
    set_dimension_text(adapter, annotations, DIMENSION_TEXT)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS, location="below")
    # The plain shank is the thread blank: its Ø prints once, parenthesised
    # as a reference with no band.
    by_name = {dimension_name(adapter, a): a for a in annotations}
    for name in sorted(REFERENCE_DIMENSIONS):
        set_reference_dimension(
            adapter, by_name[name], label=f"MHA-PN-07 {name}", diameter=True
        )
    _dress_shoulder_radius(adapter, drawing_model, by_name, spt)
    if not auto_center_marks(adapter, side, holes=True, size=0.0025):
        raise RuntimeError("failed to add the ASME center mark to the eye")
    add_view_centerline(
        adapter,
        side,
        face_xy=spt(*CENTERLINE_PICK),
        label="adjuster stud turning axis",
    )
    eye_callout = add_native_hole_callout(
        adapter,
        side,
        edge_xy=spt(*EYE_RIM_PICK),
        callout_xy=spt(*EYE_CALLOUT_XY),
        label="adjuster stud eye",
        process=drill_process(EYE_SPEC),
    )
    # The #54 drill's Ø prints .XXX (+.004/0 from the title block).
    set_hole_callout_precision(
        eye_callout, EYE_CALLOUT_PRECISION, label="adjuster stud eye"
    )

    # The shaded isometric shows the #0-80 the callout names; imported before
    # finalize's note cleanup, so its label is counted rather than first
    # appearing at the native save (draw_pn_pen_hanger).
    thread_seeds, thread_instances = import_cosmetic_threads(adapter, iso)
    if (thread_seeds, thread_instances) != (1, 1):
        raise RuntimeError(
            "adjuster-stud isometric cosmetic threads: "
            f"seeds/instances={(thread_seeds, thread_instances)!r}, expected (1, 1)"
        )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Adjuster Stud Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
