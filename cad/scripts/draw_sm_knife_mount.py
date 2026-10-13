r"""Create the curated machinist drawing for the knife-mount bearing block.

A machined, heat-treated steel block (25.4 wide x ~29.6 tall x 14 deep) with a
single Ø12 bore.  The bore is the knife-edge bearing: the summing-lever
trunnion's top vertex rides its upper inner wall in line contact (ch18 p.42:
unpainted hardened steel, close bore -- 2026-09-02 user re-read).  Every face
and the bore are real edges, so
the block dimensions ride the auto-imported profile marks (block + bore) with the
depth added across the right-view section.  The two MHA-VN-051 dowel holes
print their 2X reamed Ø (with its band and press callout) and a position
frame under it, Ø0.13 to A, carrying the datum feature symbol B for the pair,
at their BASIC span in the top view, and their flat-floor depth in section
A-A, cut from the top view through the tap and dowel axes (drawing-guidelines.md rule 9 (show internal shape in solid lines): the
floor is hidden in the front view, so it is dimensioned where the cut shows
it).  The pattern is located on the block's +X side and front faces at
general tolerance in the top view; the tap axis, run on through the bore's
centre, stands BASIC 7.632 from the -X dowel axis in section A-A.  The reamed
bore carries a position frame to the top seat (datum A) and the dowel pattern
(B) with a perpendicularity frame to B stacked under it, its centre a BASIC
height under A; the #10-24 tap a position frame to the same A|B, its #25
pilot at three places with its own +0.10/0, its full thread at the general
.XXX, its drill depth banded, its drill point dimensioned (under the general
angular band) and its mating bolt named on its hole callout.
The bore carries Ra 1.6, the top seat Ra 3.2.  Every view is
hidden-lines-removed.

Run with SolidWorks open::

    uv run python cad\scripts\draw_sm_knife_mount.py sm-knife-mount
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    remove_notes_matching,
    view_name,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_arc_endpoints_to_center,
    set_basic_dimension,
    set_dimension_callouts,
)
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_finish import add_surface_finish
from _drawing_gdt import (
    add_datum_feature,
    add_feature_control_frame,
    add_frame_datum_feature,
    assert_frame_datums_defined,
)
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leaders import set_near_side_diameter
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from build_sm_knife_mount import BORE_CENTRE_DEPTH
from sm_knife_mount_spec import (
    BLK_BOT,
    BLK_HALF_X,
    BLK_TOP,
    BORE_CY,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    GEOMETRIC_TOLERANCES_MM,
    HOLE_ROW_FACE_DISTANCE,
    PIN_HOLE_CALLOUT,
    PIN_HOLE_DEPTH,
    PIN_HOLE_DIA,
    PIN_HOLE_PAIR_CALLOUT,
    PIN_HOLE_SIDE_DISTANCE,
    PIN_HOLE_SPAN,
    PIN_HOLE_X,
    R_BORE,
    STUD_TAP_DIA,
    STUD_TAP_DIA_BAND,
    STUD_TAP_DIA_PLACES,
    STUD_TAP_DRILL_DEPTH,
    STUD_TAP_DRILL_DEPTH_BAND,
    STUD_TAP_DRILL_DEPTH_PLACES,
    STUD_TAP_POINT_ANGLE_DEG,
    STUD_TAP_POINT_ANGLE_PLACES,
    STUD_TAP_THREAD_DEPTH,
    STUD_TAP_THREAD_DEPTH_PLACES,
    SUPPORT_Z_THICK,
    SURFACE_FINISHES,
    TAP_MATE_CALLOUT,
)


SPEC = DRAWINGS_BY_NAME["sm_knife_mount"]
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
# SolidWorks' own descriptive thread note; the tap's hole callout states the tap.
TAPPED_HOLE_NOTE = "Tapped Hole"
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym

SHEET_SCALE = (2.0, 1.0)
_BLOCK_CY = (BLK_TOP + BLK_BOT) / 2.0  # block centre height (model mm)

FRONT_CENTER = (0.115, 0.140)
RIGHT_CENTER = (0.220, 0.140)
TOP_CENTER = (0.115, 0.235)
ISO_CENTER = (0.345, 0.210)
# Section A-A stands right of the right view and under the isometric, clear
# of the title block (x > 0.216 below y 0.066): the block spans sheet y
# 0.0955..0.1545 at 2:1 and its label hangs under it.
SECTION_CENTER = (0.300, 0.125)
# The cutting line (model z = 0, through the tap and dowel axes) runs this
# far past each block face in the top view.
SECTION_LINE_OVERRUN_MM = 2.5
SECTION_LINE_MODEL_MM = (
    (-(BLK_HALF_X + SECTION_LINE_OVERRUN_MM), BLK_TOP, 0.0),
    (BLK_HALF_X + SECTION_LINE_OVERRUN_MM, BLK_TOP, 0.0),
)


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - _BLOCK_CY) * SHEET_SCALE[0] / 1000.0


def _section_y(model_y_mm: float) -> float:
    """Sheet y of a model y in section A-A (it looks along -Z, as the front)."""
    return SECTION_CENTER[1] + (model_y_mm - _BLOCK_CY) * SHEET_SCALE[0] / 1000.0


def _section_x(model_x_mm: float) -> float:
    """Sheet x of a model x in section A-A (+X right, as the front)."""
    return SECTION_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _sheet_x(model_x_mm: float) -> float:
    """Sheet x of a model x in the front and top views (shared column)."""
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


# The 29.6 height's dimension line stands at sheet x 0.050, 41 mm off the
# block's -X face, and the bore's Ø, its ream band and REAM THRU sit in the
# band between them: the 5ff8fba5d render ran the height line (then x 0.063)
# 3.62 mm through the Ø (text 58.5..75.3 mm).  BORE_DIA_TEXT_HALF_WIDTH is
# half the banded line: the 20261009T204136744Z render's Ø12.00 (16.2 mm)
# plus a stacked +0.03/0.00 at the dowel band's 2.05 mm a character.
BORE_DIA_TEXT_HALF_WIDTH = 0.0135
FRONT_KEEP = {
    "BlockWidth": (FRONT_CENTER[0], _front_y(BLK_BOT) - 0.016),
    "BlockHeight": (FRONT_CENTER[0] - 0.065, FRONT_CENTER[1]),
    "BoreDia": (FRONT_CENTER[0] - 0.044, _front_y(BORE_CY) + 0.026),
}
# The dowel hole's floor depth stands right of the section, level with the
# middle of the hole, its witness lines off the cut top seat and hole floor.
SECTION_KEEP = {
    "PinHoleDepth": (
        SECTION_CENTER[0] + (BLK_HALF_X + 8.0) * SHEET_SCALE[0] / 1000.0,
        _section_y(BLK_TOP - PIN_HOLE_DEPTH / 2.0),
    ),
}
# The tap and bore frames both reference B, the dowel pair, so the tap axis
# stands BASIC 7.632 from the -X dowel axis (blind machinist review,
# 2026-10-10: the implied centre left the tap and bore with no explicit
# horizontal location).  It is dimensioned in section A-A, the one view that
# cuts the tap, the bore and the dowel hole together, between two owned
# axes: the tap's, run on down through the bore's centre so one axis carries
# both, and the -X dowel's.  Each starts SECTION_AXIS_OVERRUN_MM above the
# top seat and ends SECTION_AXIS_TAIL_MM past its feature (the bore's bottom,
# the dowel hole's floor), inside the block.
SECTION_AXIS_OVERRUN_MM = 2.0
SECTION_AXIS_TAIL_MM = 1.0
# The dimension line stands 8 mm over the cut top seat, in the open band
# under the isometric's caption.  Its boxed value (~14 mm) all but fills the
# 15.3 mm between the axes, so it parks on a leader left of the -X axis
# (draw_fr_top_frame's F-F station precedent: text past the arrows
# otherwise rides the dimension line).
TAP_STATION_TEXT_XY = (_section_x(-PIN_HOLE_X / 2.0), _section_y(BLK_TOP) + 0.008)
TAP_STATION_OFFSET_XY = (_section_x(-PIN_HOLE_X) - 0.012, TAP_STATION_TEXT_XY[1])
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
TOP_HALF_Z = SUPPORT_Z_THICK / 2.0 * SHEET_SCALE[0] / 1000.0
# The dowel hole's Ø and its three callout lines park in the open band right
# of the top view (drawing-guidelines.md rule 14 (keep text off the part): callout text outside the silhouette, no text
# on a line).  SolidWorks hangs the block left of its text position by half
# the widest line plus the shoulder's overhang and runs the shoulder under the
# last line; both are measured on the dda9a33a8 farm render (3.5 mm text,
# "PRESS MHA-VN-05x DOWEL TO FLOOR" 84.5 wide, shoulder 1.6 past it and 12.86
# under the text position).  The shoulder's near end stands 6 mm right of the
# block's +X face and 10 mm below the hole centre, so the leader reaches the
# hole's lower-right rim at ~33 degrees, clear of its centre mark's arm.
PIN_CALLOUT_HALF_WIDTH = 0.04225
PIN_CALLOUT_SHOULDER_OVERHANG = 0.0016
PIN_CALLOUT_SHOULDER_DROP = 0.01286
PIN_CALLOUT_SHOULDER_START = (_sheet_x(BLK_HALF_X) + 0.006, TOP_CENTER[1] - 0.010)
# The pair's BASIC 15.264 span runs above the top view, between the hole axes,
# its box 3 mm left of centre so the side-face 5.07's left arrow (a row up)
# stands clear of it.
PIN_SPAN_TEXT_XY = (TOP_CENTER[0] - 0.003, TOP_CENTER[1] + TOP_HALF_Z + 0.0075)
# The pattern's face locations (blind machinist review, 2026-10-09), both in
# the top view: the +X hole's axis from the +X side face, a row above the
# BASIC span (under the view, the 20261010T001553082Z render ran the dowel
# frame's leader across its side-face extension line; on the span's own row,
# 20261010T002544960Z, the two dimensions' outside arrows met under the side
# face's 5.65 (the 24-wide block's) and its right arrow ran into the cutting
# line's "A", top 256.9 mm).  Its
# arrows clear that letter by ~2.8 mm and its text the border by ~2.8 mm;
# the span's arrows stand under the letters' tops, between them.
# The -X hole's axis from the front face (the view's lower edge), its line
# left of the block under the A-A cutting line's end.
PIN_SIDE_TEXT_XY = (
    _sheet_x(BLK_HALF_X - PIN_HOLE_SIDE_DISTANCE / 2.0),
    TOP_CENTER[1] + TOP_HALF_Z + 0.0135,
)
ROW_FACE_TEXT_XY = (
    _sheet_x(-BLK_HALF_X) - 0.012,
    TOP_CENTER[1] - TOP_HALF_Z + HOLE_ROW_FACE_DISTANCE * SHEET_SCALE[0] / 1000.0 / 2.0,
)
TOP_KEEP = {
    "PinHoleDia": (
        PIN_CALLOUT_SHOULDER_START[0]
        + PIN_CALLOUT_SHOULDER_OVERHANG
        + PIN_CALLOUT_HALF_WIDTH,
        PIN_CALLOUT_SHOULDER_START[1] + PIN_CALLOUT_SHOULDER_DROP,
    ),
}
# The knife bore is reamed (Ra 1.6, +0.03/0 band): the process is stated
# (blind machinist review, 2026-10-09: a bare THRU left drill or ream open).
DIMENSION_CALLOUTS = {
    "BoreDia": "REAM THRU",
    "PinHoleDia": PIN_HOLE_CALLOUT,
}
# The pair's count rides ABOVE its Ø (the pd-latch-hook-bracket PAIR_CALLOUT
# precedent), the process lines below it.
CALLOUTS_ABOVE = {"PinHoleDia": PIN_HOLE_PAIR_CALLOUT}
# The pair's position frame hangs under that callout's shoulder, its left
# edge on the shoulder's near end, on its own leader to the same hole; the
# bore's frame stands ~30 mm lower.  Printed: 29.4 x 7.0 mm, sheet x
# 146.6..176.0, y 212.0..219.0 (farm run 20261009T171439353Z).
PIN_FRAME_XY = (
    PIN_CALLOUT_SHOULDER_START[0] + PIN_CALLOUT_SHOULDER_OVERHANG,
    PIN_CALLOUT_SHOULDER_START[1] - 0.006,
)
PIN_FRAME_SIZE = (0.0294, 0.0070)
# Datum B's symbol hangs under that frame, at the middle of its width (Y14.5
# attaches a pattern's datum feature symbol to the frame under its nX
# callout), in the open band above the bore's stacked frames (top 188.6 mm).
# The position is the letter box's bottom middle (datum A printed its 7 mm
# box upward from it); 5 mm of stem stand between the box and the frame.
DATUM_TAG_BOX = 0.007
PIN_DATUM_B_XY = (
    PIN_FRAME_XY[0] + PIN_FRAME_SIZE[0] / 2.0,
    PIN_FRAME_XY[1] - PIN_FRAME_SIZE[1] - 0.005 - DATUM_TAG_BOX,
)
# The #10-24 bottoming tap is stated once, on its Hole Wizard callout in the
# top view (fr-top-frame's KEEPER TAP precedent), not in a note.  The
# process rides the thread row's prefix and names its depth the full thread
# (blind machinist review, 2026-10-09).  The #25 pilot prints at three
# places with its own native +0.10/0 (sm_knife_mount_spec.STUD_TAP_DIA_BAND),
# the full thread at the title block's .XXX, and the drill depth an explicit
# +/-0.05, the band the crown web and the tap's runout leave between them
# (sm_knife_mount_spec.STUD_TAP_DRILL_DEPTH_BAND).  The drill row also
# dimensions the drill's point -- SolidWorks' drill-angle variable after the
# drill depth, ``X 118°`` -- so the title block's angular band governs the
# point the crown web charges (sm_knife_mount_spec.STUD_TAP_POINT_ANGLE_MIN_DEG).
# A fourth row, the callout's native below text, names the bolt the full
# thread holds (sm_knife_mount_spec.TAP_MATE_CALLOUT).
# Four 4.3 mm rows.  The process (27 characters) measured ~76 mm at the
# 20261009T204136744Z render's 2.82 mm a character; the drill row is now the
# widest: its 27 glyphs (Ø3.797 ▽ 11.24 ±0.05 X 118°) at that pitch plus the
# pilot's stacked +0.10/0, taken as wide as the bore's measured +0.03/0.00
# (~10.8 mm, BORE_DIA_TEXT_HALF_WIDTH): ~87 mm, an estimate, unmeasured.  The
# block parks in the band between the top view and the front view's datum-A
# tag (its top at y 0.1951), its bottom where the three-row block's stood so
# the frame under it keeps its station, its left end 1.9 mm inside the
# 12.7 mm inner border (drawing-guidelines.md rule 13 (stay inside the
# border)).  That moves its right end, where the leader leaves, 9 mm right of
# the three-row block's (face + 0.004, the 20261009T164113078Z run's 0.0947
# root), so the leader climbs more steeply to the tap's lower rim and runs
# less of its length over the part.
TAP_CALLOUT_PROCESS = "BOTTOMING TAP - FULL THREAD\n"
TAP_CALLOUT_HALF_WIDTH = 0.044
TAP_CALLOUT_HALF_HEIGHT = 0.0086
TAP_CALLOUT_XY = (_sheet_x(-BLK_HALF_X) - 0.031, TOP_CENTER[1] - TOP_HALF_Z - 0.012)
# Each native length the callout prints and its own band, (upper, lower) mm;
# ``None``: the title block's .XXX governs (the full thread).  The pilot's
# band is bilateral, +0.10/0; the drill depth's symmetric, +/-0.05.
TAP_CALLOUT_BANDS: dict[str, tuple[float, tuple[float, float] | None]] = {
    "hw-tapdrldia": (STUD_TAP_DIA, STUD_TAP_DIA_BAND),
    "hw-threaddepth": (STUD_TAP_THREAD_DEPTH, None),
    "hw-tapdrldepth": (
        STUD_TAP_DRILL_DEPTH,
        (STUD_TAP_DRILL_DEPTH_BAND, -STUD_TAP_DRILL_DEPTH_BAND),
    ),
}
# Both bands print their deviations at two places, +0.10/0 and ±0.05.
TAP_CALLOUT_BAND_PLACES = 2
# swTolType_e: no band of its own, bilateral, symmetric.
_TOL_NONE = 0
_TOL_BILATERAL = 2
_TOL_SYMMETRIC = 4
# The callout's places, the spec's: the pilot at three (its band governs; at
# two, Ø3.80 +0.10/0 would reject the #25 drill), the full thread at three
# (the .XXX its general band needs), the drill depth at two (its explicit
# band).
TAP_CALLOUT_PLACES = {
    "hw-tapdrldia": STUD_TAP_DIA_PLACES,
    "hw-threaddepth": STUD_TAP_THREAD_DEPTH_PLACES,
    "hw-tapdrldepth": STUD_TAP_DRILL_DEPTH_PLACES,
}
# swDimensionTextParts_e: a hole callout's definitions (5-8: prefix, suffix,
# callout above, callout below) and the writable part each is set through
# (1-4), the draw_mg_output_fixture._reference_thread_depth precedent.  The
# mate rides the below definition, a row under the native thread row
# (draw_ch_rocker_arm_tl_profile_fixture._locate_pivot_tap_depths).
_CALLOUT_DEFINITION_PARTS = {5: 1, 6: 2, 7: 3, 8: 4}
_CALLOUT_BELOW_DEFINITION = 8
TAP_DRILL_DEPTH_TOKEN = "<hw-tapdrldepth>"
# SolidWorks' documented "Drill Angle" callout variable (calloutformat.txt;
# swCalloutVariable_e.swCalloutVariable_Drill_Angle, an angle variable).
TAP_POINT_ANGLE_VARIABLE = "hw-drlang"
TAP_POINT_ANGLE_TOKEN = f"<{TAP_POINT_ANGLE_VARIABLE}>"
_CALLOUT_ANGLE_VARIABLE = 2  # swCalloutVariableType_e.swCalloutVariableType_Angle
_DRILL_ANGLE_VARIABLE = 16  # swCalloutVariable_e.swCalloutVariable_Drill_Angle
# The tap's position frame hangs under its callout block, on its own leader
# to the tap.  The two leaders land on the tap's two lower rims (model x
# side): the callout's on the lower-left, nearer its block, the frame's on
# the lower-right, so the frame's leader, climbing from the frame's right
# end, stays right of the callout's.  Both on the lower-left rim, it crossed
# the callout's 2 mm short of the tip (leader-crosses-leader, farm run
# 20261009T164113078Z).  The frame keeps its station under the four-row
# block, its root right of the callout's, so its leader stays right of it.
TAP_FRAME_XY = (
    _sheet_x(-BLK_HALF_X) - 0.022,
    TAP_CALLOUT_XY[1] - TAP_CALLOUT_HALF_HEIGHT - 0.007,
)
TAP_CALLOUT_RIM_SIDE = -1.0
TAP_FRAME_RIM_SIDE = 1.0
# The bore's stacked frames stand above the block's upper-right corner,
# right of the datum-A tag; its BASIC height under A runs down the block's
# right side.
BORE_FRAME_XY = (FRONT_CENTER[0] + 0.035, _front_y(BLK_TOP) + 0.019)
BORE_BASIC_TEXT_XY = (
    _sheet_x(BLK_HALF_X) + 0.012,
    _front_y(BLK_TOP - BORE_CENTRE_DEPTH / 2.0),
)

RIGHT_HALF_Z = SUPPORT_Z_THICK / 2.0 * SHEET_SCALE[0] / 1000.0
RIGHT_HALF_Y = (BLK_TOP - BLK_BOT) / 2.0 * SHEET_SCALE[0] / 1000.0
# The top seat's Ra 3.2 lands left of the right view's top edge middle, its
# symbol a short leader up and right of it.
TOP_SEAT_FINISH_EDGE_XY = (RIGHT_CENTER[0] - 0.006, RIGHT_CENTER[1] + RIGHT_HALF_Y)
TOP_SEAT_FINISH_XY = (RIGHT_CENTER[0] + 0.004, RIGHT_CENTER[1] + RIGHT_HALF_Y + 0.010)
# The bore's Ra 1.6 lands on the rim 30 deg below the centre line: at 0 deg
# its leader left the rim on the 20.616's centre-height witness line and
# crossed it 0.6 mm out (layout audit leader-crosses-line, run
# 20261010T022724164Z).
BORE_FINISH_RIM_DEG = -30.0
BORE_FINISH_RIM_XY = (
    FRONT_CENTER[0]
    + R_BORE * math.cos(math.radians(BORE_FINISH_RIM_DEG)) * SHEET_SCALE[0] / 1000.0,
    _front_y(BORE_CY)
    + R_BORE * math.sin(math.radians(BORE_FINISH_RIM_DEG)) * SHEET_SCALE[0] / 1000.0,
)


def _set_sheet_precision(display: Any, *, label: str) -> None:
    """Give one sheet-added dimension the places the part's spec owns
    (``DRAWING_REFERENCE_PRECISION``, the draw_fr_top_frame precedent)."""
    places = DRAWING_REFERENCE_PRECISION[label]
    display = _early_bound(display, "IDisplayDimension")
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    applied = int(display.GetPrimaryPrecision2())
    if applied != places:
        raise RuntimeError(
            f"{label}: asked for {places} decimal places, dimension reads {applied}"
        )


def _sheet_dimension_mm(display: Any) -> float:
    """The value a sheet-added dimension measures, mm."""
    native = _early_bound(display, "IDisplayDimension")
    return (
        abs(float(_early_bound(native.GetDimension2(0), "IDimension").SystemValue))
        * 1000.0
    )


def _add_section_axes(
    adapter: Any,
    view: Any,
    axes: tuple[tuple[tuple[float, float, float], tuple[float, float, float]], ...],
) -> list[Any]:
    """Draw owned centerlines (model mm end to end) in ``view``'s own sketch.

    The draw_fr_top_frame ``_add_view_centerlines`` idiom: each end is the
    model point projected to the sheet and taken into the view's sketch
    frame, placed direct to the database (an inferred end snaps onto nearby
    ink) and read back.  Returns each ``ISketchSegment``, in order, for a
    dimension to pick (``"SKETCHSEGMENT"``).
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the view for its owned axes")
    draw.ClearSelection2(True)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    segments = []
    for start, end in axes:
        points = []
        for xyz in (start, end):
            x, y = model_point_in_view(
                adapter,
                view,
                tuple(value / 1000.0 for value in xyz),
                label="owned axis end",
            )
            point = _early_bound(
                utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
            )
            projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
            points.append(tuple(float(value) for value in projected.ArrayData))
        previous_add_to_db = bool(manager.AddToDB)
        manager.AddToDB = True
        try:
            segment = manager.CreateCenterLine(*points[0], *points[1])
        finally:
            manager.AddToDB = previous_add_to_db
        if segment is None:
            raise RuntimeError("failed to create an owned axis")
        line = _early_bound(segment, "ISketchLine")
        for expected, accessor in zip(points, ("GetStartPoint2", "GetEndPoint2")):
            placed = _early_bound(
                adapter._get_attr_or_call(line, accessor), "ISketchPoint"
            )
            actual = [
                float(adapter._get_attr_or_call(placed, axis))
                for axis in ("X", "Y", "Z")
            ]
            drift = max(abs(a - b) for a, b in zip(actual, expected))
            if drift > 1e-9:
                raise RuntimeError(
                    f"owned axis {accessor[3:-6].lower()} point sits "
                    f"{drift * 1000.0:.4g} mm from where it was authored"
                )
        segment = _early_bound(segment, "ISketchSegment")
        segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
        if int(segment.Color) != 0:
            raise RuntimeError("owned axis color did not persist")
        segments.append(segment)
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="section A-A owned axes")
    return segments


def _look_section_along_minus_z(adapter: Any, section: Any) -> None:
    """Point section A-A's sight line along -Z, so it reads as the front view.

    The direction is read from the section's own projection (the
    draw_dt_cone_swing_platform section C-C idiom): with screen-right r and
    screen-up u the sight line is u x r, which runs along -z exactly when
    model +x's sheet-x sign times model +y's sheet-y sign is positive.  Then
    the dowel hole stands right of the tap axis, beside SECTION_KEEP's depth.
    """
    cut = _early_bound(section.GetSection(), "IDrSection")

    def x_direction() -> float:
        base = model_point_in_view(
            adapter, section, (0.0, 0.0, 0.0), label="A-A origin"
        )
        east = model_point_in_view(adapter, section, (0.001, 0.0, 0.0), label="A-A +x")
        up = model_point_in_view(adapter, section, (0.0, 0.001, 0.0), label="A-A +y")
        return (east[0] - base[0]) * (up[1] - base[1])

    if x_direction() < 0.0:
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="section A-A looks along -Z")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("section A-A cut direction did not persist")
    direction = x_direction()
    if not direction > 0.0:
        raise RuntimeError(
            f"section A-A still looks along +Z (sign product {direction})"
        )


def tap_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """The callout's definitions with the drill's point dimensioned right
    after the drill depth, ``<hw-tapdrldepth> X <hw-drlang>``, and the bolt
    the full thread holds named on the last row (``TAP_MATE_CALLOUT``
    closing the below definition); every other character as it was.

    The drill depth must be defined exactly once, and neither the drill
    angle nor the mate yet.  The variable stays in the definition, so the
    printed angle is the Hole Wizard feature's own drill point.
    """
    joined = "\n".join(definitions.values())
    if (
        joined.count(TAP_DRILL_DEPTH_TOKEN) != 1
        or TAP_POINT_ANGLE_TOKEN in joined
        or TAP_MATE_CALLOUT in joined
    ):
        raise RuntimeError(
            f"expected one {TAP_DRILL_DEPTH_TOKEN}, no {TAP_POINT_ANGLE_TOKEN} and no "
            f"{TAP_MATE_CALLOUT!r} in the knife-hanger tap callout's definitions: "
            f"{definitions!r}"
        )
    wanted = {
        part: text.replace(
            TAP_DRILL_DEPTH_TOKEN, f"{TAP_DRILL_DEPTH_TOKEN} X {TAP_POINT_ANGLE_TOKEN}"
        )
        for part, text in definitions.items()
    }
    below = wanted[_CALLOUT_BELOW_DEFINITION].rstrip()
    wanted[_CALLOUT_BELOW_DEFINITION] = (
        f"{below}\n{TAP_MATE_CALLOUT}" if below else TAP_MATE_CALLOUT
    )
    return wanted


def _write_tap_callout_definitions(adapter: Any, callout: Any) -> None:
    """Write the drill's point and the mating bolt into the native callout.

    Only the definitions that change are written; the readback must hold
    all four, the process prefix included.
    """
    before = {
        part: str(callout.GetText(part) or "") for part in _CALLOUT_DEFINITION_PARTS
    }
    wanted = tap_callout_definitions(before)
    written = {part: text for part, text in wanted.items() if text != before[part]}
    for part, text in written.items():
        callout.SetText(_CALLOUT_DEFINITION_PARTS[part], text)
    after = {
        part: str(callout.GetText(part) or "") for part in _CALLOUT_DEFINITION_PARTS
    }
    if after != wanted:
        raise RuntimeError(
            "knife-hanger tap drill point and mate did not persist: wanted "
            f"{wanted!r}, read {after!r}"
        )
    rebuild_drawing(adapter, label="knife-hanger tap drill point and mate")
    _telemetry.info(f"knife-hanger tap callout definitions written: {written!r}")


def tap_callout_tolerance(band: tuple[float, float]) -> tuple[int, float, float]:
    """The swTolType_e and (lower, upper) deviations, mm, a callout band
    writes: symmetric when its limits mirror, else bilateral."""
    lower, upper = min(band), max(band)
    kind = _TOL_SYMMETRIC if math.isclose(lower, -upper) else _TOL_BILATERAL
    return kind, lower, upper


def _band_tap_callout(callout: Any) -> None:
    """Author the tap's bands on its hole callout -- the pilot's +0.10/0,
    the drill depth's +/-0.05 -- prove the full thread's depth carries none
    (``None``: the title block's .XXX), and the drill point its 118 deg.

    A hole callout variable carries its OWN tolerance (SW 2016+:
    ``ICalloutVariable.ToleranceType``), so each band is set and read back
    on the callout (the draw_sm_summing_lever bracket-tap and
    draw_fr_top_frame hanger-clearance precedents): three unbanded places
    on the pilot would claim the general .XXX, and the title block's band
    on the drill depth would leave under one pitch of drill past the
    deepest full thread, or break the crown web.
    """
    from win32com.client.dynamic import Dispatch as dynamic_dispatch

    required = dict(TAP_CALLOUT_BANDS)
    points: list[Any] = []
    for raw in callout.GetHoleCalloutVariables() or ():
        # Concrete callout interfaces alias the generic metadata DISPIDs.
        variable = dynamic_dispatch(raw._oleobj_)
        variable_name = str(variable.VariableName)
        if variable_name == TAP_POINT_ANGLE_VARIABLE:
            points.append(raw)
            continue
        if variable_name not in required:
            continue
        nominal, band = required.pop(variable_name)
        length = _early_bound(raw, "ICalloutLengthVariable")
        actual = float(length.Length) * 1000.0
        if variable_name == "hw-tapdrldia":
            # The wizard's #25 drill may carry its inch size's fourth place
            # (0.1495 in); the sheet's contract is the Ø it prints.
            places = TAP_CALLOUT_PLACES[variable_name]
            mismatch = round(actual, places) != round(nominal, places)
        else:
            mismatch = abs(actual - nominal) > 1e-5
        if mismatch:
            raise RuntimeError(
                f"knife-hanger tap callout {variable_name} reads "
                f"{actual:g}, expected {nominal:g} mm"
            )
        if band is None:
            variable.ToleranceType = _TOL_NONE
            if int(variable.ToleranceType) != _TOL_NONE:
                raise RuntimeError(
                    f"knife-hanger tap callout {variable_name} keeps a tolerance"
                )
            continue
        kind, lower, upper = tap_callout_tolerance(band)
        variable.ToleranceType = kind
        variable.ToleranceMin = lower / 1000.0
        variable.ToleranceMax = upper / 1000.0
        length.TolerancePrecision = TAP_CALLOUT_BAND_PLACES
        if (
            int(variable.ToleranceType) != kind
            or abs(float(variable.ToleranceMin) * 1000.0 - lower) > 1e-5
            or abs(float(variable.ToleranceMax) * 1000.0 - upper) > 1e-5
            or int(length.TolerancePrecision) != TAP_CALLOUT_BAND_PLACES
        ):
            raise RuntimeError(
                f"knife-hanger tap callout band for {variable_name} did not "
                f"persist: wanted swTolType_e {kind}, deviations {(lower, upper)} mm at "
                f"{TAP_CALLOUT_BAND_PLACES} places"
            )
    if required:
        raise RuntimeError(f"knife-hanger tap callout omits native lengths: {required}")
    if len(points) != 1:
        raise RuntimeError(
            f"knife-hanger tap callout carries {len(points)} native drill points, not one"
        )
    _prove_tap_point(points[0])


def _prove_tap_point(raw: Any) -> None:
    """The callout's drill point is SolidWorks' drill-angle variable reading
    the feature's 118 deg, printed in whole degrees with no band of its own,
    so the title block's angular tolerance governs it (the crown web charges
    its 117 deg limit, sm_knife_mount_spec.STUD_TAP_POINT_ANGLE_MIN_DEG)."""
    from win32com.client.dynamic import Dispatch as dynamic_dispatch

    variable = dynamic_dispatch(raw._oleobj_)
    kinds = (int(variable.Type), int(variable.VariableType))
    if kinds != (_CALLOUT_ANGLE_VARIABLE, _DRILL_ANGLE_VARIABLE):
        raise RuntimeError(
            f"knife-hanger tap callout {TAP_POINT_ANGLE_VARIABLE} is type {kinds}, "
            f"not the drill angle {(_CALLOUT_ANGLE_VARIABLE, _DRILL_ANGLE_VARIABLE)}"
        )
    angle = _early_bound(raw, "ICalloutAngleVariable")
    degrees = math.degrees(float(angle.Angle))
    if abs(degrees - STUD_TAP_POINT_ANGLE_DEG) > 1e-5:
        raise RuntimeError(
            f"knife-hanger tap drill point reads {degrees:g} deg, "
            f"expected {STUD_TAP_POINT_ANGLE_DEG:g}"
        )
    variable.ToleranceType = _TOL_NONE
    angle.Precision = STUD_TAP_POINT_ANGLE_PLACES
    if (
        int(variable.ToleranceType) != _TOL_NONE
        or int(angle.Precision) != STUD_TAP_POINT_ANGLE_PLACES
    ):
        raise RuntimeError(
            "knife-hanger tap drill point did not persist unbanded at "
            f"{STUD_TAP_POINT_ANGLE_PLACES} places"
        )


# Section A-A cuts the tap on its axis: SolidWorks' cosmetic-thread
# annotation printed its major Ø there dashed, as a hidden thread (blind
# machinist review, 2026-10-09).  It moves onto a visible thin continuous
# layer, the section's own thread line.  The front and right views are
# drawn hidden-lines-removed, which does not touch the annotation (the
# draw_fr_top_frame._hide_cosmetic_threads measurement), so their threads,
# hidden in both, move onto an invisible layer.
SECTION_THREAD_LAYER = "TAP-THREAD-SECTION"
HIDDEN_THREAD_LAYER = "TAP-THREAD-HIDDEN"
_COSMETIC_THREAD_ANNOTATION = 1  # swAnnotationType_e.swCosmeticThread


def _layer_cosmetic_threads(
    adapter: Any, view: Any, *, layer_name: str, visible: bool, label: str
) -> int:
    """Move one view's cosmetic-thread annotations onto ``layer_name``.

    The layer is created thin and continuous (``ILayerMgr::AddLayer``),
    shown or hidden by ``visible``, the draw_fr_top_frame precedent: both the
    layer state and every annotation's layer are read back.  Returns the
    count moved; the caller decides whether none is a failure.
    """
    draw = adapter.currentModel
    manager = _early_bound(draw.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(layer_name)
    if layer is None:
        # COLORREF black, swLineCONTINUOUS (0), swLW_THIN (0).
        if int(manager.AddLayer(layer_name, label, 0, 0, 0)) != 1:
            raise RuntimeError(f"{label}: failed to add layer {layer_name}")
        layer = manager.GetLayer(layer_name)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = visible
    if bool(layer.Visible) != visible or (not visible and bool(layer.Printable)):
        raise RuntimeError(
            f"{label}: layer {layer_name} reads visible={layer.Visible!r}, "
            f"printable={layer.Printable!r}; wanted visible={visible}"
        )
    if visible and (int(layer.Style) != 0 or int(layer.Width) != 0):
        raise RuntimeError(
            f"{label}: layer {layer_name} reads style {layer.Style!r}, width "
            f"{layer.Width!r}; wanted thin continuous"
        )
    moved = 0
    for raw_annotation in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != _COSMETIC_THREAD_ANNOTATION:
            continue
        annotation.Layer = layer_name
        if str(annotation.Layer or "") != layer_name:
            raise RuntimeError(f"{label}: a cosmetic thread refused layer {layer_name}")
        moved += 1
    rebuild_drawing(adapter, label=f"cosmetic threads to {layer_name}")
    _telemetry.info(f"{label}: moved {moved} cosmetic thread(s) to {layer_name}")
    return moved


def _tap_lower_rim(adapter: Any, top: Any, x_side: float) -> tuple[float, float]:
    """The #10-24 tap's drill rim at 45 deg on model ``x_side``, below its
    centre in the top view: picked on whichever side of the cutting line
    model -Z/+Z projects below it."""
    rim_mm = STUD_TAP_DIA / 2.0 / math.sqrt(2.0)
    return min(
        (
            model_point_in_view(
                adapter,
                top,
                (x_side * rim_mm / 1000.0, BLK_TOP / 1000.0, side * rim_mm / 1000.0),
                label=f"knife-hanger tap rim x{x_side:+.0f} z{side:+.0f}",
            )
            for side in (1.0, -1.0)
        ),
        key=lambda point: point[1],
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open knife-mount source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Knife-Mount Bearing Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "knife mount; hardened steel bearing block; knife-edge bore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    # Section A-A cuts the top view on z = 0 through the tap and dowel axes:
    # the blind dowel hole's floor is hidden in the front view (drawing-guidelines.md rule 9 (show internal shape in solid lines)),
    # so its depth is dimensioned on the cut.
    section_ends = [
        model_point_in_view(
            adapter,
            top,
            tuple(value / 1000.0 for value in point),
            label=f"section A-A line end {index}",
        )
        for index, point in enumerate(SECTION_LINE_MODEL_MM)
    ]
    section = create_section_view(
        adapter,
        top,
        line_start=section_ends[0],
        line_end=section_ends[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(2, 1),
        label="dowel and tap axis section",
    )
    _look_section_along_minus_z(adapter, section)
    set_hidden_lines_removed(adapter, section)
    # Every view is drawn hidden-lines-removed (2026-10-10 ruling): the top
    # view's dashed cross-bore restated the front view's bore, and the front
    # view's dashed tap and dowel holes restated their callouts and section
    # A-A, which cuts both on their axes (machinist reviews r3/r4); the right
    # view's dashed tap, dowel and bore restated all three (2026-10-09).
    for view in (iso, right, front, top):
        set_hidden_lines_removed(adapter, view)

    # The dowel hole's floor depth (section A-A) is imported before its
    # profile's Ø and station (top), the MHA-PD-018 section-before-end order.
    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            section,
            keep=SECTION_KEEP,
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            top,
            keep=TOP_KEEP,
            view_label="top",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Places and the ream band are authored on the part; the sheet only proves
    # the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    if not _layer_cosmetic_threads(
        adapter,
        section,
        layer_name=SECTION_THREAD_LAYER,
        visible=True,
        label="section A-A tap thread",
    ):
        raise RuntimeError("section A-A carries no cosmetic thread; the tap moved?")
    for view, view_label in ((front, "front"), (right, "right")):
        _layer_cosmetic_threads(
            adapter,
            view,
            layer_name=HIDDEN_THREAD_LAYER,
            visible=False,
            label=f"{view_label} view hidden tap thread",
        )
    # SolidWorks pins its own raw "#10-24 Tapped Hole" note to a view that
    # imports from the tapped part (the dda9a33a8 render put it on the top
    # view, through the dowel callout).  The tap is stated once, on its hole
    # callout below (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)), so every such note goes.  Which views receive
    # one is SolidWorks' choice (draw_fr_top_frame._auto_tapped_hole_notes),
    # so the count is logged, not gated; finalize_drawing then proves none is
    # left.
    removed_tap_notes = remove_notes_matching(adapter, TAPPED_HOLE_NOTE)
    _telemetry.info(f"removed {removed_tap_notes} automatic tapped-hole note(s)")
    tap_rim = _tap_lower_rim(adapter, top, TAP_CALLOUT_RIM_SIDE)
    tap_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=tap_rim,
        callout_xy=TAP_CALLOUT_XY,
        label="knife-hanger bolt bottoming tap",
        process=TAP_CALLOUT_PROCESS,
    )
    _write_tap_callout_definitions(adapter, tap_callout)
    _band_tap_callout(tap_callout)
    set_hole_callout_precision(
        tap_callout,
        TAP_CALLOUT_PLACES,
        label="knife-hanger tap pilot and depths",
    )
    # One arrow on the bore's near (upper-left) rim, its leader short from
    # the text on the left; native, the Ø line ran rim to rim through the
    # centre and across the view to a shoulder left of it.
    bore_dia = [a for a in annotations if dimension_name(adapter, a) == "BoreDia"]
    if len(bore_dia) != 1:
        raise RuntimeError(f"expected one BoreDia dimension, found {len(bore_dia)}")
    set_near_side_diameter(bore_dia[0], "knife-bore diameter")
    # The template centre-marks every hole as each view is placed (the top
    # view's two holes and section A-A carry marks no call asked for), so an
    # explicit AutoInsertCenterMarks2 on the front view printed the bore's
    # mark twice (DetailItem346/352 at one point; #913).  Prove the one mark.
    marks = (
        _early_bound(front, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )
    if len(marks) != 1:
        raise RuntimeError(f"expected one knife-bore centre mark, found {len(marks)}")

    # Block depth (14.0, .X like the width and height): dimension the right
    # view's flat front/back faces.
    depth = add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0] - RIGHT_HALF_Z, RIGHT_CENTER[1]),
        p1=(RIGHT_CENTER[0] + RIGHT_HALF_Z, RIGHT_CENTER[1]),
        text_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] - RIGHT_HALF_Y - 0.014),
        label="block-depth overall",
    )
    _set_sheet_precision(depth, label="block-depth overall")

    # The dowel pair's span: hole axis to hole axis, picked on each hole's
    # outer rim at 45 deg.
    pin_rim_mm = PIN_HOLE_DIA / 2.0 / math.sqrt(2.0)
    span_picks = [
        max(
            (
                model_point_in_view(
                    adapter,
                    top,
                    (
                        side * (PIN_HOLE_X + pin_rim_mm) / 1000.0,
                        BLK_TOP / 1000.0,
                        z_side * pin_rim_mm / 1000.0,
                    ),
                    label=f"dowel hole rim x{side:+.0f} z{z_side:+.0f}",
                )
                for z_side in (1.0, -1.0)
            ),
            key=lambda point: point[1],
        )
        for side in (-1.0, 1.0)
    ]
    span = add_edge_dimension(
        adapter,
        top,
        p0=span_picks[0],
        p1=span_picks[1],
        text_xy=PIN_SPAN_TEXT_XY,
        label="dowel hole span",
        orientation="horizontal",
    )
    set_arc_endpoints_to_center(adapter, span, label="dowel hole span")
    if abs(_sheet_dimension_mm(span) - PIN_HOLE_SPAN) > 1e-5:
        raise RuntimeError(
            f"dowel hole span measures {_sheet_dimension_mm(span):g}, "
            f"expected {PIN_HOLE_SPAN:g} mm"
        )
    _set_sheet_precision(span, label="dowel hole span")
    set_basic_dimension(adapter, span, label="dowel hole span")

    # The pattern on the block's outside faces at general tolerance (blind
    # machinist review, 2026-10-09: the span located the dowels only to each
    # other).  Across X, the +X hole's axis from the +X side face; across Z,
    # the -X hole's axis from the front face.  Each face is picked off the
    # cutting line, each hole on the rim the span took.
    side_face = model_point_in_view(
        adapter,
        top,
        (BLK_HALF_X / 1000.0, BLK_TOP / 1000.0, SUPPORT_Z_THICK / 4.0 / 1000.0),
        label="+X side face",
    )
    side = add_edge_dimension(
        adapter,
        top,
        p0=side_face,
        p1=span_picks[1],
        text_xy=PIN_SIDE_TEXT_XY,
        label="dowel hole from side face",
        orientation="horizontal",
    )
    set_arc_endpoints_to_center(adapter, side, label="dowel hole from side face")
    if abs(_sheet_dimension_mm(side) - PIN_HOLE_SIDE_DISTANCE) > 1e-5:
        raise RuntimeError(
            f"+X dowel hole measures {_sheet_dimension_mm(side):g} from the side "
            f"face, expected {PIN_HOLE_SIDE_DISTANCE:g} mm"
        )
    _set_sheet_precision(side, label="dowel hole from side face")
    front_face = model_point_in_view(
        adapter,
        top,
        (
            -(BLK_HALF_X + PIN_HOLE_X) / 2.0 / 1000.0,
            BLK_TOP / 1000.0,
            SUPPORT_Z_THICK / 2.0 / 1000.0,
        ),
        label="front face",
    )
    row_y = model_point_in_view(
        adapter,
        top,
        (-PIN_HOLE_X / 1000.0, BLK_TOP / 1000.0, 0.0),
        label="-X dowel axis",
    )[1]
    if not front_face[1] < row_y:
        raise RuntimeError(
            f"the front face projects at sheet y {front_face[1]:g}, not below the "
            f"hole row ({row_y:g}): ROW_FACE_TEXT_XY assumes the top view's lower edge"
        )
    row = add_edge_dimension(
        adapter,
        top,
        p0=front_face,
        p1=span_picks[0],
        text_xy=ROW_FACE_TEXT_XY,
        label="hole row from front face",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(adapter, row, label="hole row from front face")
    if abs(_sheet_dimension_mm(row) - HOLE_ROW_FACE_DISTANCE) > 1e-5:
        raise RuntimeError(
            f"-X dowel hole measures {_sheet_dimension_mm(row):g} from the front "
            f"face, expected {HOLE_ROW_FACE_DISTANCE:g} mm"
        )
    _set_sheet_precision(row, label="hole row from front face")

    # The tap axis BASIC from the -X dowel axis, in section A-A between owned
    # axes (TAP_STATION_TEXT_XY); the tap's axis runs on through the bore's
    # centre, so the one BASIC locates both from B.
    tap_axis_x = model_point_in_view(
        adapter, section, (0.0, BLK_TOP / 1000.0, 0.0), label="A-A tap axis"
    )[0]
    pin_axis_x = model_point_in_view(
        adapter,
        section,
        (-PIN_HOLE_X / 1000.0, BLK_TOP / 1000.0, 0.0),
        label="A-A -X dowel axis",
    )[0]
    if not pin_axis_x < tap_axis_x:
        raise RuntimeError(
            f"section A-A draws the -X dowel axis at sheet x {pin_axis_x:g}, not left "
            f"of the tap axis ({tap_axis_x:g}): TAP_STATION_OFFSET_XY assumes +X right"
        )
    axis_top = BLK_TOP + SECTION_AXIS_OVERRUN_MM
    tap_axis, pin_axis = _add_section_axes(
        adapter,
        section,
        (
            ((0.0, axis_top, 0.0), (0.0, BORE_CY - R_BORE - SECTION_AXIS_TAIL_MM, 0.0)),
            (
                (-PIN_HOLE_X, axis_top, 0.0),
                (-PIN_HOLE_X, BLK_TOP - PIN_HOLE_DEPTH - SECTION_AXIS_TAIL_MM, 0.0),
            ),
        ),
    )
    station_picks = [
        model_point_in_view(
            adapter,
            section,
            (x / 1000.0, (BLK_TOP + SECTION_AXIS_OVERRUN_MM / 2.0) / 1000.0, 0.0),
            label=f"A-A axis pick x{x:+g}",
        )
        for x in (0.0, -PIN_HOLE_X)
    ]
    station = add_edge_dimension(
        adapter,
        section,
        p0=station_picks[0],
        p1=station_picks[1],
        text_xy=TAP_STATION_TEXT_XY,
        label="dowel hole from tap axis",
        orientation="horizontal",
        entity_types=("SKETCHSEGMENT", "SKETCHSEGMENT"),
        entities=(tap_axis, pin_axis),
    )
    if abs(_sheet_dimension_mm(station) - PIN_HOLE_X) > 1e-5:
        raise RuntimeError(
            f"the -X dowel axis measures {_sheet_dimension_mm(station):g} from the "
            f"tap axis, expected {PIN_HOLE_X:g} mm"
        )
    _set_sheet_precision(station, label="dowel hole from tap axis")
    station_annotation = _early_bound(
        _early_bound(station, "IDisplayDimension").GetAnnotation(), "IAnnotation"
    )
    offset_dimension_text(
        adapter,
        [station_annotation],
        {dimension_name(adapter, station_annotation): TAP_STATION_OFFSET_XY},
    )
    set_basic_dimension(adapter, station, label="dowel hole from tap axis")

    # Datum A = the block top seat (clamped to the top-frame casting underside;
    # carries the #10-24 knife-hanger-bolt tap and the MHA-VN-051 dowel
    # holes); datum B = the dowel pair, its symbol on the position frame
    # under their 2X Ø (a tag on the dimension attaches to nothing, farm run
    # 20261009T155421516Z).  Ra 1.6
    # (MACHINED_UM) on the bore's working upper wall, tagged on the bore rim
    # (a real circular edge).
    add_datum_feature(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0], _front_y(BLK_TOP)),
        symbol_xy=(FRONT_CENTER[0], _front_y(BLK_TOP) + 0.018),
        datum="A",
        label="block top seat",
    )
    # The pair: ⌖Ø0.13 to A at their BASIC span, the frame on the +X hole's
    # lower outer rim, where the 2X Ø callout's own leader lands; datum B is
    # the symbol on that frame (add_frame_datum_feature: the frame's datum
    # identifier read "B" back and printed nothing, run 20261009T171439353Z).
    pin_frame_rim = min(
        (
            model_point_in_view(
                adapter,
                top,
                (
                    (PIN_HOLE_X + pin_rim_mm) / 1000.0,
                    BLK_TOP / 1000.0,
                    z_side * pin_rim_mm / 1000.0,
                ),
                label=f"dowel hole frame rim z{z_side:+.0f}",
            )
            for z_side in (1.0, -1.0)
        ),
        key=lambda point: point[1],
    )
    pin_frame = add_feature_control_frame(
        adapter,
        top,
        edge_xy=pin_frame_rim,
        frame_xy=PIN_FRAME_XY,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["dowel hole pattern position"],
        datums=("A",),
        diameter=True,
        label="dowel hole pattern position",
    )
    add_frame_datum_feature(
        adapter,
        top,
        pin_frame,
        datum="B",
        symbol_xy=PIN_DATUM_B_XY,
        label="dowel hole pattern datum B",
    )
    # The bore: Ø0.20 located to A|B; under it, ⊥Ø0.05 to B holds its axis
    # square to the dowel pattern, so the trunnion axis stands square to the
    # knife edge (sm_knife_mount_spec: one Ø zone bounds yaw and tilt).  Its
    # centre is BASIC under A; across, BASIC 7.632 from a dowel axis.
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0], _front_y(BORE_CY) + R_BORE * SHEET_SCALE[0] / 1000.0),
        frame_xy=BORE_FRAME_XY,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["knife-bore position"],
        datums=("A", "B"),
        diameter=True,
        label="knife-bore position",
        lower_frame=(
            "perpendicularity",
            GEOMETRIC_TOLERANCES_MM["knife-bore perpendicularity"],
            ("B",),
        ),
    )
    bore_basic = add_edge_dimension(
        adapter,
        front,
        p0=(_sheet_x(0.6 * BLK_HALF_X), _front_y(BLK_TOP)),
        p1=(_sheet_x(R_BORE), _front_y(BORE_CY)),
        text_xy=BORE_BASIC_TEXT_XY,
        label="knife-bore centre from top seat",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(
        adapter, bore_basic, label="knife-bore centre from top seat"
    )
    if abs(_sheet_dimension_mm(bore_basic) - BORE_CENTRE_DEPTH) > 1e-5:
        raise RuntimeError(
            f"knife-bore centre measures {_sheet_dimension_mm(bore_basic):g} under "
            f"the top seat, expected {BORE_CENTRE_DEPTH:g} mm"
        )
    _set_sheet_precision(bore_basic, label="knife-bore centre from top seat")
    set_basic_dimension(adapter, bore_basic, label="knife-bore centre from top seat")
    # The #10-24 tap: Ø0.10 to A|B, the bolt axis the crossbar's clearance
    # hole floats round (build_sm_summing_assembly's knife-hanger stack).
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=_tap_lower_rim(adapter, top, TAP_FRAME_RIM_SIDE),
        frame_xy=TAP_FRAME_XY,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["knife-hanger tap position"],
        datums=("A", "B"),
        diameter=True,
        label="knife-hanger tap position",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=BORE_FINISH_RIM_XY,
        symbol_xy=(FRONT_CENTER[0] + 0.052, _front_y(BORE_CY) - 0.020),
        control=surface_finish_by_key(SURFACE_FINISHES, "knife_bore"),
        label="knife bore finish",
        # The fleet's finish height (62 of 75 finishes): the document default
        # is the dimension height, and Ra 1.6 printed twice the sheet's notes.
        char_height=0.0025,
    )
    # The top seat, datum A (machinist review r3, 2026-10-10: the dowelled
    # seat the screw clamps had no finish).  Tagged on the right view's top
    # edge, the open band over that bare view, clear of the front view's
    # datum-A tag and the bore and tap frames.
    add_surface_finish(
        adapter,
        right,
        edge_xy=TOP_SEAT_FINISH_EDGE_XY,
        symbol_xy=TOP_SEAT_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "top_seat"),
        label="top seat finish",
        char_height=0.0025,
    )
    # Every datum a frame names is printed (A on the front view, B on the
    # pattern frame), so no frame references a datum the sheet never names.
    assert_frame_datums_defined(
        (front, right, top, section), label="sm-knife-mount frame datums"
    )

    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.175)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Knife-Mount Bearing Block Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=(TAPPED_HOLE_NOTE,),
        expected_redundant_notes=0,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
