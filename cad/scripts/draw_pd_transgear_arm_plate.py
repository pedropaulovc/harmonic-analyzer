r"""Create the manufacturing drawing for the transgear arm plate (MHA-PD-19).

Two sheets.  Sheet 1 (REAR FACE): the plan is ``*Front``, labelled REAR VIEW,
looking at the rear face: the outline from the press-hole axis K (the end
radius, the top corners, the kink), the reamed press hole for the MHA-PD-28
bush, both screw holes, the locating holes, and the BASIC hole positions
from K, with the overall height as a reference.  One hole callout on the
drill Ø (leading to the -X hole from the upper left) carries the
countersink in symbol form; the press hole's callout carries its face-A
chamfer; the locating holes' callout points at the numbered sheet note
under the plan for their match-drilling.  The isometric stands upper right.

Sheet 2 (FACE A): the back view (``*Back``), labelled FRONT VIEW (FACE A),
looks at the mounting face A.  It carries the side edges from K and the
overall width as a reference, the locator heights, datums B and C and every
feature control frame, one frame for each 2X group.  Its side view
(``*Left``, third-angle to its right, K level in both) shows the flat
plate edge-on: the thickness with what it sets, and datum A on face A.
Every frame is plain (rule 26 bars the projected-zone modifier).

Every kept dimension's text point is a model point (mm) projected through
its view, so the placement holds whichever way SolidWorks orients the view.

The press hole is the plate origin; screw stations, top corners and kinks
come from ``pd_transgear_arm_plate_geometry`` at the current reducer
centre. The print imports those model dimensions rather than restating a
historical bore offset.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
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
from _drawing_attachment import _assert_attached_to
from _drawing_dimensions import (
    assert_imported_precision,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import scan_view_edges
from _drawing_gdt import PmiDrawingPlacement, project_part_pmi
import _drawing_hidden_sketches as hidden_sketches
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _feature_requirements import part_metadata, requirement
from _gtol_cone import ConeFace
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _paths import CAD_ROOT
from _printed_limits import drilled_limits, limits
from _part_properties import part_drawing_unit
from _session import run_build
import _telemetry
from pd_transgear_arm_plate_notes import (
    HOLE_COUNT_CALLOUT,
    LOCATOR_CALLOUT,
    LOCATOR_COUNT_CALLOUT,
    LOCATOR_NOTE,
    PRESS_HOLE_CALLOUT,
    SCREW_HOLE_CALLOUT,
)
from pd_transgear_arm_plate_geometry import (
    CSK_ANGLE_BAND_DEG,
    CSK_ANGLE_DEG,
    CSK_DIA,
    CSK_DIA_LIMITS_MM,
    LOCATOR_SITES_MM,
    LOCATOR_HOLE_BAND_MM,
    LOCATOR_HOLE_DIA_MM,
    EDGE_MINUS_X,
    EDGE_PLUS_X,
    END_R,
    KINK,
    KINK_RIGHT,
    KINK_TANGENT,
    PRESS_HOLE_CHAMFER,
    PRESS_HOLE_CHAMFER_LIMITS,
    PRESS_HOLE_CHAMFER_PLACES,
    PRESS_HOLE_DIA,
    REAR_FACE_Z,
    SCREW_HOLE_DIA,
    SCREW_HOLES,
    THICKNESS_OVER_ARM,
    TOP_LEFT,
    TOP_RIGHT,
    UNIT,
    arm_upper_edge_y,
)
from pd_transgear_arm_plate_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    FRONT_VIEW_LABEL,
    GEOMETRIC_CONTROLS,
    GEOMETRIC_TOLERANCES_MM,
    ISO_VIEW_SCALE,
    OVERALL_HEIGHT_MM,
    OVERALL_WIDTH_MM,
    PART_DATUMS,
    PRESS_HOLE_BAND,
    REAR_VIEW_LABEL,
    SHEET_NAMES,
    THICKNESS_CALLOUT,
)

# Machinist review gates this sheet: the build fails on a FIX verdict.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_transgear_arm_plate"]
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

# The plate is 56 x 38 in plan and .197 thick, drawn at 2:1 on two B sheets
# (the title block fills x > 0.216 below y 0.066).  Sheet 1: the plan on the
# left with its callouts above and beside it, the isometric upper right.
# Sheet 2: the face-A view on the left under its three rows of frames, its
# side view to its right.  A view's centre is its outline's; K stands
# (_TOP + _BOTTOM) / 2 below it in both face views.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
# 6 mm lower since #2034 (the plate 6.4 longer, 12.8 on the sheet): on the
# old centre the locating-hole callout's top line crossed the upper border
# (preview run 20261028T064655627Z).
PLAN_CENTER = (0.105, 0.126)
ISO_CENTER = (0.320, 0.200)
ISO_NOTE_XY = (0.285, 0.252)
REAR_LABEL_XY = (0.093, 0.032)

_TOP = TOP_LEFT[1]  # the plate's highest point (the top edge's -X corner)
_TOP_AT_K = arm_upper_edge_y(0.0)  # the top edge over K, lower than the corner
_BOTTOM = -END_R
# The face-A view stays where its frame rows and datum tags were tuned (it
# stood level with the old section A-A, centred 0.148 on the cut's height).
# Its side view (``*Left``, third-angle to its right) spans the same
# _BOTTOM.._TOP, so the same centre height keeps K level in both; it stands
# right of the face-A view's -X heights and frames, its thickness block in
# the open sheet beside it.
BACK_CENTER = (
    0.135,
    0.148 + (_TOP - _TOP_AT_K) / 2.0 * SHEET_SCALE[0] / 1000.0,
)
SIDE_CENTER = (0.262, BACK_CENTER[1])
_Z_PLAN = REAR_FACE_Z
_SCREW_Y = SCREW_HOLES[0][1]

# Per-view survivors of the marked-dimension import, each at the MODEL point
# (mm) its text stands on.  Plan: the locator and +X hole positions stack
# above the top edge, nearest first; the -X hole's stands above them all,
# over the reamed-hole callout's leader start, so that leader runs from the
# upper left to locator 1 with no dimension line or text in its way
# (machinist review, run 20261027T152452686Z: in the rows the leader passes,
# it struck the 10.875 text).  Rule 14 keeps it off the plate (codjiflo on
# 9704957a3: inside, between locator 2 and the boss, it read on the part);
# the leader then crosses only hole 1's witness line, which rule 14 calls
# conventional.  The heights from K stand
# outboard of each side, the hole height's wide toleranced text wholly
# right of the edge.  Rows 4 apart (8 mm on the sheet: 4.4 mm air between
# 3.6 mm texts) keep the locator's witness lines under the locator
# diameter's shoulder (at 5 apart a top row rose through it: farm run
# 20261009T224545531Z, shoulder-crosses-line).  The width stands under the
# face-A view instead: across the top it was the one dimension line the
# reamed-hole leader had to cross (machinist review of the r3 sheets).
PLAN_ROWS = tuple(_TOP_AT_K + 8.0 + 4.0 * row for row in range(3))
# Three rows over the top one: 7 mm over the leader's start (r18 sheet, run
# 20261027T192628995Z: its shelf ends 20.8 over the top edge at K).
_OVER_LEADER_ROW = _TOP_AT_K + 8.0 + 4.0 * 5
PLAN_KEEP: dict[str, tuple[float, float, float]] = {
    # Text outboard of hole 2's witness line: between it and K, the bore
    # axis's witness line struck the 4.125 (machinist review, run
    # 20261027T165127867Z).
    "ScrewHoleX2": (SCREW_HOLES[1][0] + 5.5, PLAN_ROWS[0], _Z_PLAN),
    "ScrewHoleX1": (SCREW_HOLES[0][0] / 2.0, _OVER_LEADER_ROW, _Z_PLAN),
    "KinkY": (EDGE_MINUS_X - 5.0, KINK[1] / 2.0, _Z_PLAN),
    "TopLeftY": (EDGE_MINUS_X - 11.0, TOP_LEFT[1] / 2.0, _Z_PLAN),
    "KinkRightY": (EDGE_PLUS_X + 5.0, KINK_RIGHT[1] / 2.0, _Z_PLAN),
    "ScrewHoleY": (EDGE_PLUS_X + 9.5, _SCREW_Y / 2.0, _Z_PLAN),
    "EndR": (0.7071 * END_R + 6.0, -0.7071 * END_R - 6.0, _Z_PLAN),
    # Low enough that its top line stands clear under the overall height's
    # lower witness line, which runs left from the end round's extreme.
    "PressHoleDia": (EDGE_MINUS_X - 4.0, _BOTTOM - 9.0, _Z_PLAN),
    # Its three short lines end left of hole 1's witness line (the .4281's:
    # at 24 characters a line from EDGE_MINUS_X - 6 that line ran through
    # the 82° and the screw's number, fan-out round 2), its shelf above the
    # overall height's upper witness line at the top corner.
    "ScrewHoleDia": (EDGE_MINUS_X - 7.45, _TOP + 11.0, _Z_PLAN),
    # Text right of K's witness line, which struck it between the two; the
    # reamed-hole leader runs on the left.
    "LocatorX1": (4.5, PLAN_ROWS[2], _Z_PLAN),
    # Under the border and high enough that its lines clear the screw-hole
    # callout; far enough left that its leader runs down to locator 1 left
    # of every location dimension line, with air to the left border (run
    # 20261027T165127867Z: its shelf met the border).  Its shelf, under the
    # whole block, ends left of hole 1's witness line (LOCATOR_SHELF_*
    # below; round 1 layout audit on 41ad5cf: the 27-character fit line's
    # shelf ran across that line, shoulder-crosses-line).
    "LocatorDia1": (EDGE_MINUS_X - 9.3, _TOP + 31.0, _Z_PLAN),
}
# Face-A view: the locator heights outboard, the +X top corner's height
# outside them, and both side edges from K below the end round.  The corner
# height stands here, not on the plan: there its witness line ran through
# section D-D's letter (run 20261027T130144223Z).
BACK_KEEP: dict[str, tuple[float, float, float]] = {
    # Low on its line: mid-height it would sit beside the raised 18.078.
    "TopRightY": (EDGE_PLUS_X + 15.0, 5.0, 0.0),
    "EdgeLeftX": (EDGE_MINUS_X / 2.0, _BOTTOM - 7.0, 0.0),
    "EdgeRightX": (EDGE_PLUS_X / 2.0, _BOTTOM - 7.0, 0.0),
    "LocatorY1": (EDGE_MINUS_X - 8.0, LOCATOR_SITES_MM[0][1] / 2.0, 0.0),
    "LocatorY2": (EDGE_PLUS_X + 8.0, LOCATOR_SITES_MM[1][1] / 2.0, 0.0),
}
# Side view (``*Left``: Z along the sheet, face A toward the face-A view):
# the thickness across the plate's top end, its value and two-line callout
# (16 characters, about 21 mm of model wide at 2:1) centred 16 mm right of
# the rear face in the open sheet, as on the old section, clear of the
# view; between the plate's own witness lines they would cross face A's.
SIDE_KEEP: dict[str, tuple[float, float, float]] = {
    "ThicknessOverArm": (0.0, _TOP + 6.0, REAR_FACE_Z + 16.0),
}

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, beside the keeps that print
# it, in the part frame (pd_transgear_arm_plate_geometry: origin on K on face
# A, +Z to the rear face, the long axis along -Y from the screws to the end
# round). Bands are the title block's rows at the places the part authors
# (DRAWING_PRECISION_BY_NAME), the press hole and the locating holes their
# set reamer's size with no printed band (their "dia" fields carry the
# spec's ANALYSIS bands, what each reamer is modelled to cut), the
# screw holes the DRILLED HOLES row, the hole positions BASIC with their
# frames' zones (GEOMETRIC_TOLERANCES_MM). The locating holes are reamed at
# assembly (note 1, MHA-PD-00 13A/13E: match-drilled with MHA-PD-18):
# ``made_at = "assembly"``. The declarations print nothing.
_P = DRAWING_PRECISION_BY_NAME
_SELF = "draw_pd_transgear_arm_plate"
_GEOM = "pd_transgear_arm_plate_geometry"
_NOTES = "pd_transgear_arm_plate_notes"
_FRAME = "__frame__"
_THICK = THICKNESS_OVER_ARM


def _plane(axis: str, value: float) -> dict[str, Any]:
    return {"frame": "model", "axis": axis, "value": value}


def _outward(start: tuple[float, float], end: tuple[float, float]) -> tuple[float, float, float]:
    """Unit normal of the edge ``start``->``end`` on its left: outward for an
    edge walked clockwise round the outline."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    return (-dy / length, dx / length, 0.0)


_TOP_NORMAL = _outward(TOP_LEFT, TOP_RIGHT)
_LEFT_TAPER_NORMAL = _outward(KINK_TANGENT, KINK)
_RIGHT_TAPER_NORMAL = (-_LEFT_TAPER_NORMAL[0], _LEFT_TAPER_NORMAL[1], 0.0)
_OUTLINE_SOURCES = ((_GEOM, "TOP_LEFT"), (_GEOM, "TOP_RIGHT"), (_GEOM, "KINK"), (_GEOM, "KINK_TANGENT"))

part_metadata(
    model_sources=(
        (_GEOM, "THICKNESS_OVER_ARM"),
        (_GEOM, "WIDTH"),
        (_GEOM, "END_R"),
        (_GEOM, "TOP_LEFT"),
    ),
    precision_sources=("DRAWING_PRECISION", "DRAWING_PRECISION_BY_NAME"),
)
# Face A, datum A: seats on MHA-PD-18's rear face; the thickness's origin.
requirement(
    "face_a",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("plane",),
    fields={"plane": (_plane("z", 0.0), (_FRAME, "PART_DATUMS"))},
)
# The rear face: .197 from face A at .XXX, SETS SCREW REACH IN ARM MHA-PD-18.
requirement(
    "rear_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), _THICK),),
    requirements=("thickness",),
    fields={
        "plane": (_plane("z", _THICK), ((_GEOM, "THICKNESS_OVER_ARM"),)),
        "thickness": (
            limits(_THICK, _P["ThicknessOverArm"], unit=UNIT),
            ((_GEOM, "THICKNESS_OVER_ARM"), (_GEOM, "UNIT"), (_SELF, "SIDE_KEEP")),
        ),
        "thickness_nominal": (_THICK, ((_GEOM, "THICKNESS_OVER_ARM"),)),
        "thickness_from": ("face_a", ((_SELF, "SIDE_KEEP"),)),
        "callout": (THICKNESS_CALLOUT, ("THICKNESS_CALLOUT",)),
    },
    precision={"thickness": _P["ThicknessOverArm"]},
)
# The outline, every edge .XX from K: the side edges .75 each side (datum C
# the +X edge), straight up from their kinks (.42 above K) to the top edge's
# corners (1.67 at -X, 1.61 at +X); below the kinks two tapers tangent to
# the R.49 end round about K.
requirement(
    "outline",
    kind="profile",
    faces=(
        PlanarFace((-1.0, 0.0, 0.0), -EDGE_MINUS_X, contains_z_mm=_THICK / 2.0),
        PlanarFace((1.0, 0.0, 0.0), EDGE_PLUS_X, contains_z_mm=_THICK / 2.0),
        PlanarFace(_TOP_NORMAL, _TOP_NORMAL[0] * TOP_LEFT[0] + _TOP_NORMAL[1] * TOP_LEFT[1]),
        PlanarFace(_LEFT_TAPER_NORMAL, END_R),
        PlanarFace(_RIGHT_TAPER_NORMAL, END_R),
        CylinderFace(2.0 * END_R),
    ),
    requirements=(
        "end_r", "edge_left_x", "edge_right_x", "top_left_y", "top_right_y",
        "kink_y", "kink_right_y",
    ),
    fields={
        "end_r": (
            limits(END_R, _P["EndR"], unit=UNIT),
            ((_GEOM, "END_R"), (_GEOM, "UNIT"), (_SELF, "PLAN_KEEP")),
        ),
        "end_r_nominal": (END_R, ((_GEOM, "END_R"),)),
        "edge_left_x": (
            limits(-EDGE_MINUS_X, _P["EdgeLeftX"], unit=UNIT),
            ((_GEOM, "EDGE_MINUS_X"), (_GEOM, "UNIT"), (_SELF, "BACK_KEEP")),
        ),
        "edge_left_x_nominal": (-EDGE_MINUS_X, ((_GEOM, "EDGE_MINUS_X"),)),
        "edge_right_x": (
            limits(EDGE_PLUS_X, _P["EdgeRightX"], unit=UNIT),
            ((_GEOM, "EDGE_PLUS_X"), (_GEOM, "UNIT"), (_SELF, "BACK_KEEP")),
        ),
        "edge_right_x_nominal": (EDGE_PLUS_X, ((_GEOM, "EDGE_PLUS_X"),)),
        "top_left_y": (
            limits(TOP_LEFT[1], _P["TopLeftY"], unit=UNIT),
            ((_GEOM, "TOP_LEFT"), (_GEOM, "UNIT"), (_SELF, "PLAN_KEEP")),
        ),
        "top_left_y_nominal": (TOP_LEFT[1], ((_GEOM, "TOP_LEFT"),)),
        "top_right_y": (
            limits(TOP_RIGHT[1], _P["TopRightY"], unit=UNIT),
            ((_GEOM, "TOP_RIGHT"), (_GEOM, "UNIT"), (_SELF, "BACK_KEEP")),
        ),
        "top_right_y_nominal": (TOP_RIGHT[1], ((_GEOM, "TOP_RIGHT"),)),
        "kink_y": (
            limits(KINK[1], _P["KinkY"], unit=UNIT),
            ((_GEOM, "KINK_Y"), (_GEOM, "UNIT"), (_SELF, "PLAN_KEEP")),
        ),
        "kink_y_nominal": (KINK[1], ((_GEOM, "KINK_Y"),)),
        "kink_right_y": (
            limits(KINK_RIGHT[1], _P["KinkRightY"], unit=UNIT),
            ((_GEOM, "KINK_Y"), (_GEOM, "UNIT"), (_SELF, "PLAN_KEEP")),
        ),
        "kink_right_y_nominal": (KINK_RIGHT[1], ((_GEOM, "KINK_Y"),)),
        "from": ("press_hole", ((_SELF, "PLAN_KEEP"), (_SELF, "BACK_KEEP"))),
        "tangent_left_at": ([KINK_TANGENT[0], KINK_TANGENT[1], 0.0], _OUTLINE_SOURCES),
        "tangent_right_at": ([-KINK_TANGENT[0], KINK_TANGENT[1], 0.0], _OUTLINE_SOURCES),
        "width_ref": (OVERALL_WIDTH_MM, ("OVERALL_WIDTH_MM", "DRAWING_REFERENCE_PRECISION")),
        "height_ref": (OVERALL_HEIGHT_MM, ("OVERALL_HEIGHT_MM", "DRAWING_REFERENCE_PRECISION")),
        "extent_x": ([EDGE_MINUS_X, EDGE_PLUS_X], ((_GEOM, "EDGE_MINUS_X"), (_GEOM, "EDGE_PLUS_X"))),
        "extent_y": ([-END_R, TOP_LEFT[1]], ((_GEOM, "END_R"), (_GEOM, "TOP_LEFT"))),
    },
    precision={
        "end_r": _P["EndR"],
        "edge_left_x": _P["EdgeLeftX"],
        "edge_right_x": _P["EdgeRightX"],
        "top_left_y": _P["TopLeftY"],
        "top_right_y": _P["TopRightY"],
        "kink_y": _P["KinkY"],
        "kink_right_y": _P["KinkRightY"],
    },
)
# Datum B, the press hole on K: REAM THRU Ø.4385, no printed band, the press
# for the MHA-PD-28 bush (turned to this hole as measured), its face-A mouth
# .015 X 45° (the bush's lead-in).
requirement(
    "press_hole",
    kind="hole",
    faces=(CylinderFace(PRESS_HOLE_DIA), ConeFace(45.0, contains_x_mm=0.0)),
    requirements=("dia", "thru", "process", "chamfer_leg"),
    fields={
        "at": ([0.0, 0.0, _THICK], (_FRAME, (_GEOM, "THICKNESS_OVER_ARM"))),
        "axis": ([0.0, 0.0, -1.0], (_FRAME, (_NOTES, "PRESS_HOLE_CALLOUT"))),
        "dia": (
            limits(PRESS_HOLE_DIA, _P["PressHoleDia"], PRESS_HOLE_BAND, unit=UNIT),
            ((_GEOM, "PRESS_HOLE_DIA"), "PRESS_HOLE_BAND", (_SELF, "PLAN_KEEP")),
        ),
        "nominal_dia": (PRESS_HOLE_DIA, ((_GEOM, "PRESS_HOLE_DIA"),)),
        "thru": (True, ((_NOTES, "PRESS_HOLE_CALLOUT"),)),
        "process": ("ream", ((_NOTES, "PRESS_HOLE_CALLOUT"),)),
        "chamfer_leg": (
            list(PRESS_HOLE_CHAMFER_LIMITS),
            ((_GEOM, "PRESS_HOLE_CHAMFER_LIMITS"), (_NOTES, "PRESS_HOLE_CALLOUT")),
        ),
        "chamfer_leg_nominal": (PRESS_HOLE_CHAMFER, ((_GEOM, "PRESS_HOLE_CHAMFER"),)),
        "chamfer_angle_deg": (45.0, ((_NOTES, "PRESS_HOLE_CALLOUT"),)),
        "chamfer_at": ("face_a", ((_NOTES, "PRESS_HOLE_CALLOUT"),)),
        "datum": ("B", ("PART_DATUMS",)),
        "fit": ("press", ((_NOTES, "PRESS_HOLE_CALLOUT"),)),
        "mates": ("MHA-PD-28", ("BUSH_NUMBER",)),
        "callout": (PRESS_HOLE_CALLOUT, ((_NOTES, "PRESS_HOLE_CALLOUT"),)),
    },
    precision={"dia": _P["PressHoleDia"], "chamfer_leg": PRESS_HOLE_CHAMFER_PLACES},
)
# The two screw holes: #1 drill (Ø.228) THRU from the rear face, each with
# its 82° countersink Ø.312 on the rear face for the MHA-PD-VN-56 heads;
# BASIC from K, in a Ø.014 zone to A|B|C (the arm's taps are spotted through
# them at assembly, MHA-PD-00 13L).
for _index, (_x, _y) in enumerate(SCREW_HOLES, 1):
    requirement(
        f"screw_hole_{_index}",
        kind="hole",
        faces=(
            CylinderFace(SCREW_HOLE_DIA, contains_x_mm=_x),
            ConeFace(CSK_ANGLE_DEG / 2.0, contains_x_mm=_x),
        ),
        requirements=(
            "dia", "thru", "x_basic", "y_basic", "position_dia", "csk_dia", "csk_angle_deg",
        ),
        fields={
            "at": ([_x, _y, _THICK], ((_GEOM, "SCREW_HOLES"), (_GEOM, "THICKNESS_OVER_ARM"))),
            "axis": ([0.0, 0.0, -1.0], (_FRAME, (_NOTES, "SCREW_HOLE_CALLOUT"))),
            "dia": (
                drilled_limits(SCREW_HOLE_DIA, _P["ScrewHoleDia"], unit=UNIT),
                ((_GEOM, "SCREW_HOLE_DIA"), (_GEOM, "UNIT"), (_SELF, "PLAN_KEEP")),
            ),
            "nominal_dia": (SCREW_HOLE_DIA, ((_GEOM, "SCREW_HOLE_DIA"),)),
            "thru": (True, ((_NOTES, "SCREW_HOLE_CALLOUT"),)),
            "process": ("drill", ((_NOTES, "SCREW_HOLE_CALLOUT"),)),
            "x_basic": (_x, ((_GEOM, "SCREW_HOLES"), "BASIC_REDUCER_DIMENSIONS")),
            "y_basic": (_y, ((_GEOM, "SCREW_HOLES"), "BASIC_REDUCER_DIMENSIONS")),
            "position_dia": (
                GEOMETRIC_TOLERANCES_MM["screw_position"],
                ("GEOMETRIC_TOLERANCES_MM", "GEOMETRIC_CONTROLS"),
            ),
            "position_datums": ("A|B|C", ("GEOMETRIC_CONTROLS",)),
            "csk_dia": (
                list(CSK_DIA_LIMITS_MM),
                ((_GEOM, "CSK_DIA_LIMITS_MM"), (_NOTES, "SCREW_HOLE_CALLOUT")),
            ),
            "csk_dia_nominal": (CSK_DIA, ((_GEOM, "CSK_DIA"),)),
            "csk_angle_deg": (
                [CSK_ANGLE_DEG - CSK_ANGLE_BAND_DEG, CSK_ANGLE_DEG + CSK_ANGLE_BAND_DEG],
                ((_GEOM, "CSK_ANGLE_DEG"), (_GEOM, "CSK_ANGLE_BAND_DEG")),
            ),
            "csk_angle_deg_nominal": (CSK_ANGLE_DEG, ((_GEOM, "CSK_ANGLE_DEG"),)),
            "csk_at": ("rear_face", ((_NOTES, "SCREW_HOLE_CALLOUT"),)),
            "mates": ("MHA-PD-VN-56", ("SCREW_NUMBER",)),
        },
        precision={"dia": _P["ScrewHoleDia"], "csk_dia": _P["CskDia"]},
    )
# The two locating holes Ø.1260 REAM THRU, no printed band, a slip on the
# MHA-PD-VN-64 dowels (the dowel slides in, no shake), BASIC from K in a
# Ø.004 zone: match-drilled with MHA-PD-18 and reamed at assembly (note 1;
# MHA-PD-00 13A pilots, 13E ream). No part traveler makes them.
for _index, (_x, _y) in enumerate(LOCATOR_SITES_MM, 1):
    requirement(
        f"locator_{_index}",
        kind="hole",
        faces=(CylinderFace(LOCATOR_HOLE_DIA_MM, contains_x_mm=_x, contains_y_mm=_y),),
        requirements=("dia", "thru", "x_basic", "y_basic", "position_dia"),
        fields={
            "at": ([_x, _y, 0.0], ((_GEOM, "LOCATOR_SITES_MM"),)),
            "axis": ([0.0, 0.0, 1.0], (_FRAME, (_NOTES, "LOCATOR_CALLOUT"))),
            "dia": (
                limits(LOCATOR_HOLE_DIA_MM, _P["LocatorDia1"], LOCATOR_HOLE_BAND_MM, unit=UNIT),
                ((_GEOM, "LOCATOR_HOLE_DIA_MM"), (_GEOM, "LOCATOR_HOLE_BAND_MM"), (_SELF, "PLAN_KEEP")),
            ),
            "nominal_dia": (LOCATOR_HOLE_DIA_MM, ((_GEOM, "LOCATOR_HOLE_DIA_MM"),)),
            "thru": (True, ((_NOTES, "LOCATOR_CALLOUT"),)),
            "process": ("ream", ((_NOTES, "LOCATOR_CALLOUT"),)),
            "made_at": ("assembly", ((_NOTES, "LOCATOR_NOTE"),)),
            "x_basic": (_x, ((_GEOM, "LOCATOR_SITES_MM"), "BASIC_REDUCER_DIMENSIONS")),
            "y_basic": (_y, ((_GEOM, "LOCATOR_SITES_MM"), "BASIC_REDUCER_DIMENSIONS")),
            "position_dia": (
                GEOMETRIC_TOLERANCES_MM["locator_position"],
                ("GEOMETRIC_TOLERANCES_MM", "GEOMETRIC_CONTROLS"),
            ),
            "mates": ("MHA-PD-VN-64", ("DOWEL_NUMBER",)),
        },
        precision={"dia": _P["LocatorDia1"]},
    )


_DIM_ARROWS_INSIDE = 0  # swDimensionArrowsSide_e.swDimArrowsInside
_DIM_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
# Outside, the -X hole's arrows ran 1.2 mm from the locator callout's line
# ends (run 20261028T000816580Z, layout audit arrow-near-text); its 21.8 mm
# span holds both arrows under its value.
PLAN_ARROW_SIDES = {"ScrewHoleX1": _DIM_ARROWS_INSIDE}
# Inside, the 18.078's upper arrowhead struck its boxed text (machinist
# review of 848ba5637, run 20261028T003904510Z, gating clarity); outside,
# the arrows point in at both witness lines and none crosses the box.
BACK_ARROW_SIDES = {"LocatorY2": _DIM_ARROWS_OUTSIDE}


def _set_arrow_sides(adapter: Any, annotations: list[Any], sides: dict[str, int]) -> None:
    """Draw each named dimension's arrows on its side of its witness lines
    (swDimensionArrowsSide_e), read back."""
    for name, side in sides.items():
        found = [
            annotation for annotation in annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(found) != 1:
            raise RuntimeError(f"expected one {name} to set its arrow side, found {len(found)}")
        display = _early_bound(
            _early_bound(found[0], "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension"
        )
        display.ArrowSide = side
        if int(display.ArrowSide) != side:
            raise RuntimeError(f"{name} did not keep its arrows on side {side}")


@_telemetry.traced("drawing.transgear_arm_plate.group_frames")
def _one_frame_per_group(adapter: Any, frames: dict[str, Any]) -> None:
    """One frame for each 2X group (``frame_groups``): the other holes'
    identical frames are hidden on the sheet (``IAnnotation::Visible`` =
    swAnnotationHidden, drawing-local), and the shown frame carries the
    count above it (``IGtol::SetText(swGTolTextCalloutAbove)``).  After one
    rebuild each is read back: hidden frames hidden, each shown frame
    visible with its count; anything else fails the build."""
    groups = []
    for shown_key, hidden_keys, count in frame_groups():
        hidden = {key: _early_bound(frames[key], "IAnnotation") for key in hidden_keys}
        for annotation in hidden.values():
            annotation.Visible = _ANNOTATION_HIDDEN
        shown = _early_bound(frames[shown_key], "IAnnotation")
        gtol = _early_bound(shown.GetSpecificAnnotation(), "IGtol")
        if not gtol.SetText(_GTOL_CALLOUT_ABOVE, count):
            raise RuntimeError(f"{shown_key}: the group's {count} was refused")
        groups.append((shown_key, shown, gtol, hidden, count))
    rebuild_drawing(adapter, label="2X group frames")
    for shown_key, shown, gtol, hidden, count in groups:
        for key, annotation in hidden.items():
            if int(annotation.Visible) != _ANNOTATION_HIDDEN:
                raise RuntimeError(f"{key}: the repeated frame did not stay hidden")
        above = str(gtol.GetText(_GTOL_CALLOUT_ABOVE) or "")
        if int(shown.Visible) != _ANNOTATION_VISIBLE or above != count:
            raise RuntimeError(
                f"{shown_key}: the group's frame reads visible={shown.Visible!r}, "
                f"above={above!r}, not {count!r}"
            )
        _telemetry.info(f"2X group: {shown_key} prints {count}; hidden {sorted(hidden)}")


@_telemetry.traced("drawing.transgear_arm_plate.overall_reference", label_param="label")
def _overall_reference(
    adapter: Any,
    view: Any,
    *,
    name: str,
    label: str,
    entities: tuple[Any, Any],
    entity_types: tuple[str, str],
    picks: tuple[tuple[float, float], tuple[float, float]],
    text_xy: tuple[float, float],
    orientation: str,
    expected_mm: float,
    to_arc_extreme: bool = False,
) -> None:
    """A native overall dimension across two named view entities, measured
    (attached entities and value, after any arc end moves to the round's
    extreme), then parenthesised as a reference at the spec's places."""
    dimension = add_edge_dimension(
        adapter, view, p0=picks[0], p1=picks[1], text_xy=text_xy, label=label,
        orientation=orientation, entities=entities, entity_types=entity_types,
    )
    if to_arc_extreme:
        set_arc_endpoints_to_max(adapter, dimension, label=label)
    display = _early_bound(dimension, "IDisplayDimension")
    assert_dimension_measures(
        adapter, display, expected_mm=expected_mm, label=label,
        entities=entities, entity_types=entity_types,
    )
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError(f"{label} has no native annotation")
    display = _early_bound(
        set_reference_dimension(adapter, annotation, label=label), "IDisplayDimension"
    )
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[name], -1, -1, -1)
    applied = int(display.GetPrimaryPrecision2())
    if applied != DRAWING_REFERENCE_PRECISION[name]:
        raise RuntimeError(
            f"{label} prints {applied} decimal places, not {DRAWING_REFERENCE_PRECISION[name]}"
        )



# Under the plan, right of the view label and the press-hole callout,
# left of the title block, above the border.
LOCATOR_NOTE_XY = (0.125, 0.045)

PLAN_CALLOUTS = {
    "PressHoleDia": PRESS_HOLE_CALLOUT,
    "ScrewHoleDia": SCREW_HOLE_CALLOUT,
    "LocatorDia1": LOCATOR_CALLOUT,
}
PLAN_CALLOUTS_ABOVE = {
    "ScrewHoleDia": HOLE_COUNT_CALLOUT,
    "LocatorDia1": LOCATOR_COUNT_CALLOUT,
}

SIDE_CALLOUTS = {"ThicknessOverArm": THICKNESS_CALLOUT}
DIMENSION_CALLOUTS = {**PLAN_CALLOUTS, **SIDE_CALLOUTS}
CALLOUTS_ABOVE = PLAN_CALLOUTS_ABOVE
# Position frames, sheet metres, offsets from the face-A view's K. A frame's
# xy is its top-left corner; a position frame is about 44 mm wide (59 mm it
# was with the projected zone, which rule 26 bars), and its leader leaves
# the end nearer the feature through a 6.3 mm shoulder (measured on run
# 20261009T214031408Z). The hole and locator frames stand in three rows
# above the view, which mirrors X, so its hole frames sit outboard of their
# own holes (no crossing) and the two through-bore locator leaders drop
# between the hole leaders; hole 2's frame keeps the row it took to pass
# left of the old A-A cutting line's top letter (run 20261027T125555391Z).
# The frames left of their features keep their right ends (and so their
# leaders) where the wider projected-zone frames had them: 15 mm right.
# K on the sheet: the view centres the outline, which spans _BOTTOM.._TOP
# about K (a fixed 0.1286 put K 6 mm off once #2034 lengthened the plate).
_BACK_K = (
    BACK_CENTER[0],
    BACK_CENTER[1] - (_TOP + _BOTTOM) / 2.0 * SHEET_SCALE[0] / 1000.0,
)
# Each 2X group prints one frame (``frame_groups``): the shown locator frame
# stands on the top row low enough that the count above it stays inside
# the upper border, the shown hole frame on the bottom row with its count
# under the locator frame.  The hidden frames keep their old rows: a
# projected frame needs a placement, and hidden it prints nothing.
FRAME_ROWS = (0.256, 0.247, 0.238)
_PROJECTED_CELL_WIDTH = 0.015
FRAME_XY = {
    "plate_hole_1_position": (_BACK_K[0] + 0.02875, FRAME_ROWS[2]),
    "plate_hole_2_position": (_BACK_K[0] - 0.10185 + _PROJECTED_CELL_WIDTH, FRAME_ROWS[2]),
    "plate_locator_1_position": (_BACK_K[0] + 0.01055, FRAME_ROWS[0]),
    "plate_locator_2_position": (_BACK_K[0] + 0.01905, FRAME_ROWS[1]),
}
# The overall references (pd_transgear_arm_plate_spec.OVERALL_*_MM).  The
# width stands under the face-A view's side widths, one 12 mm row lower,
# across the two side edges; the view's label under it.  The height stands
# on the plan left of the top corner's height (1.67), from the -X top
# corner to the end round's extreme below K, its text clear of the left
# border; its lower witness line runs over the press-hole callout's block.
OVERALL_WIDTH_TEXT_XY = (
    _BACK_K[0], _BACK_K[1] + (_BOTTOM - 13.0) * SHEET_SCALE[0] / 1000.0,
)
FRONT_LABEL_XY = (0.110, OVERALL_WIDTH_TEXT_XY[1] - 0.008)
# Model points on the face-A view's face A (z = 0): each side edge between
# the top corner and the kink (datum C's edge on +X).
OVERALL_WIDTH_EDGES_MODEL = (
    (EDGE_PLUS_X, (TOP_RIGHT[1] + KINK_RIGHT[1]) / 2.0, 0.0),
    (EDGE_MINUS_X, (TOP_LEFT[1] + KINK[1]) / 2.0, 0.0),
)
OVERALL_HEIGHT_TEXT_MODEL = (EDGE_MINUS_X - 21.0, (_TOP + _BOTTOM) / 2.0, _Z_PLAN)
# The plan looks at the rear face: its -X top corner and the end round.
OVERALL_HEIGHT_CORNER_MODEL = (EDGE_MINUS_X, _TOP, REAR_FACE_Z)
OVERALL_HEIGHT_ROUND_MODEL = ((0.0, 0.0, REAR_FACE_Z), END_R)


def frame_groups() -> tuple[tuple[str, tuple[str, ...], str], ...]:
    """Each 2X group's one printed frame: the key whose frame prints, the
    keys whose identical frames are hidden, and the count text above it.

    Machinist screen (clarity, fan-out round 2): identical frames were
    repeated on each dowel ream and each screw hole instead of given once
    for the 2X group.  Every member must be the same control at its own
    site, or one frame cannot speak for them all.
    """
    groups = []
    for prefix, sites in (
        ("plate_locator_", LOCATOR_SITES_MM),
        ("plate_hole_", SCREW_HOLES),
    ):
        group = [c for c in GEOMETRIC_CONTROLS if c.key.startswith(prefix)]
        if len(group) != len(sites) or len(group) < 2:
            raise AssertionError(f"MHA-PD-19's {prefix}* group is not one control per hole")
        shown, *hidden = group
        for other in hidden:
            if (
                other.characteristic, other.tolerance, other.datums, other.tolerance_zone,
                other.projected_zone_height_mm, other.face.diameter_mm,
            ) != (
                shown.characteristic, shown.tolerance, shown.datums, shown.tolerance_zone,
                shown.projected_zone_height_mm, shown.face.diameter_mm,
            ):
                raise AssertionError(f"{other.key} is not {shown.key}'s control at its own site")
        groups.append((shown.key, tuple(other.key for other in hidden), f"{len(group)}X"))
    return tuple(groups)


_ANNOTATION_VISIBLE = 1  # swAnnotationVisibilityState_e.swAnnotationVisible
_ANNOTATION_HIDDEN = 3  # swAnnotationVisibilityState_e.swAnnotationHidden
_GTOL_CALLOUT_ABOVE = 3  # swGTolTextParts_e.swGTolTextCalloutAbove
DATUM_B_XY = (_BACK_K[0] + 0.058, _BACK_K[1] - 0.014)
# C is the vertical +X side face (sheet left in the face-A view), square to
# the X hole coordinates.  The tag stands well below the top corner so its
# horizontal leader lands on that side face, not on the sloping top edge
# (machinist review 2026-10-11 read the corner landing as the sloped face),
# and above locator 2's height's witness line, level with the screw holes.
DATUM_C_MODEL_Y = _SCREW_Y
DATUM_C_XY = (_BACK_K[0] - 0.055, _BACK_K[1] + DATUM_C_MODEL_Y / 500.0)
# Datum A tags face A edge-on in the side view, its tag left of the face,
# between the face-A view's -X heights and the side view. Model mm.
DATUM_A_MODEL = (0.0, _SCREW_Y, -10.0)
_ModelPoint = tuple[float, float, float]
# A placed note reads back its own SetPosition point; a refused move leaves
# it at the default drop, centimetres away.
NOTE_POSITION_TOL_M = 1e-5


def _sheet_xy(
    adapter: Any, view: Any, point_mm: _ModelPoint, label: str
) -> tuple[float, float]:
    """Project a model point (mm) onto the sheet through ``view``."""
    return model_point_in_view(
        adapter, view, tuple(value / 1000.0 for value in point_mm), label=label
    )


def _sheet_keep(
    adapter: Any, view: Any, keep: dict[str, _ModelPoint], label: str
) -> dict[str, tuple[float, float]]:
    """Project each kept dimension's model text point onto the sheet."""
    return {
        name: _sheet_xy(adapter, view, point, f"{label} {name}")
        for name, point in keep.items()
    }


def _press_hole_landing(
    adapter: Any, view: Any, toward: tuple[float, float]
) -> tuple[float, float]:
    """The point on the press hole's circle in ``view`` facing ``toward``
    (sheet m).

    A datum tag on a circle keeps a radial leader through its pick: the
    tag only moves along that ray, so the pick must face the tag (run
    20261027T124743046Z: picked by entity, B's tag stayed at its default
    drop on the far side of the bore, 82 mm from its request).
    """
    centre = _sheet_xy(adapter, view, (0.0, 0.0, 0.0), "press hole centre")
    dx, dy = toward[0] - centre[0], toward[1] - centre[1]
    scale = PRESS_HOLE_DIA / 2.0 * SHEET_SCALE[0] / 1000.0 / math.hypot(dx, dy)
    return centre[0] + dx * scale, centre[1] + dy * scale


def _assert_datum_b_on_press_hole(
    adapter: Any, projected: dict[str, Any], press_hole_edge: Any
) -> None:
    """Datum B is picked at its landing point (``_press_hole_landing``), so
    the helper's own check only proves the tag sits on what that hit-test
    returned; prove that entity IS the hole's cylinder edge, not its face-A
    chamfer's outer rim .015 outside it within the pick aperture."""
    _assert_attached_to(
        adapter, projected["datum:B"], press_hole_edge, entity_type="EDGE",
        what="datum B", label="plate press hole", expected_leaders=0,
    )


def _activate_sheet(adapter: Any, name: str) -> None:
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not drawing.ActivateSheet(name):
        raise RuntimeError(f"failed to activate arm-plate sheet {name!r}")


def _curated(
    adapter: Any, views: tuple[tuple[Any, dict[str, _ModelPoint], str], ...]
) -> list[Any]:
    """Each view keeps exactly its marked dimensions, at their text points."""
    return [
        annotation
        for view, keep, label in views
        for annotation in hidden_sketches.curate_view_dimensions(
            adapter,
            view,
            keep=_sheet_keep(adapter, view, keep, label),
            view_label=label,
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    ]


def _require_note_in_view(
    note: Any, view: Any, xy: tuple[float, float], label: str
) -> None:
    """The note sits where it was placed and belongs to ``view``: a note
    inserts into whichever view is active, and a label owned by another
    view moves or disappears with it."""
    if note is None:
        raise RuntimeError(f"failed to add the plate's {label}")
    annotation = _early_bound(note, "INote").GetAnnotation()
    if not annotation:
        raise RuntimeError(f"the plate's {label} has no annotation")
    annotation = _early_bound(annotation, "IAnnotation")
    position = annotation.GetPosition()
    if not position or math.hypot(
        float(position[0]) - xy[0], float(position[1]) - xy[1]
    ) > NOTE_POSITION_TOL_M:
        raise RuntimeError(f"the plate's {label} is not at {xy}: reads {position}")
    owner = annotation.Owner
    wanted = str(_early_bound(view, "IView").GetName2())
    actual = str(_early_bound(owner, "IView").GetName2()) if owner else None
    if actual != wanted:
        raise RuntimeError(f"the plate's {label} belongs to {actual!r}, not {wanted!r}")


def _activate_view(adapter: Any, view: Any, label: str) -> None:
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate the view for the plate's {label}")


@_telemetry.traced("drawing.plate_note", label_param="label")
def _add_note(
    adapter: Any, view: Any, text: str, xy: tuple[float, float], label: str
) -> None:
    _activate_view(adapter, view, label)
    _require_note_in_view(add_note(adapter, text, *xy), view, xy, label)


@_telemetry.traced("drawing.plate_note", label_param="label")
def _add_linked_note(
    adapter: Any, view: Any, property_name: str, xy: tuple[float, float], label: str
) -> None:
    _activate_view(adapter, view, label)
    _require_note_in_view(
        add_property_linked_note(adapter, property_name, *xy), view, xy, label
    )


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-arm-plate source", adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Arm Plate Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear arm plate; machined steel bar",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="arm-plate sheets")

    # --- Sheet 1: the rear face and the isometric. ----------------------------
    _activate_sheet(adapter, SHEET_NAMES[0])
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    plan = place_view(adapter, str(SOURCE), "*Front", *PLAN_CENTER, scale=VIEW_SCALE)
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_VIEW_SCALE
    )
    for view in (plan, iso):
        set_hidden_lines_removed(adapter, view)
    plan_annotations = _curated(adapter, ((plan, PLAN_KEEP, "plan"),))
    # Decimal places and the explicit bands are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(
        adapter, plan_annotations,
        {name: DRAWING_PRECISION_BY_NAME[name] for name in PLAN_KEEP},
    )
    set_dimension_callouts(adapter, plan_annotations, PLAN_CALLOUTS)
    set_dimension_callouts(
        adapter, plan_annotations, PLAN_CALLOUTS_ABOVE, location="above"
    )
    _set_arrow_sides(adapter, plan_annotations, PLAN_ARROW_SIDES)
    if not auto_center_marks(adapter, plan, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME centre marks to the plan view")
    # The overall height, a reference: the -X top corner to the end round's
    # extreme below K, both on the rear face the plan looks at.
    plan_edges = scan_view_edges(plan, label="plate rear-face outline")
    round_centre, round_radius = OVERALL_HEIGHT_ROUND_MODEL
    height_entities = (
        plan_edges.exact_vertex_at(OVERALL_HEIGHT_CORNER_MODEL, label="plate -X top corner"),
        plan_edges.circle_at(
            round_centre, round_radius, axis=(0.0, 0.0, 1.0), label="plate end round",
        ).edge,
    )
    _overall_reference(
        adapter, plan, name="OverallHeight", label="overall height reference",
        entities=height_entities, entity_types=("VERTEX", "EDGE"),
        picks=(
            _sheet_xy(adapter, plan, OVERALL_HEIGHT_CORNER_MODEL, "plate -X top corner"),
            _sheet_xy(adapter, plan, (0.0, _BOTTOM, REAR_FACE_Z), "plate end round extreme"),
        ),
        text_xy=_sheet_xy(adapter, plan, OVERALL_HEIGHT_TEXT_MODEL, "overall height text"),
        orientation="vertical", expected_mm=OVERALL_HEIGHT_MM, to_arc_extreme=True,
    )
    _add_note(adapter, plan, LOCATOR_NOTE, LOCATOR_NOTE_XY, "locating-hole note")
    _add_note(adapter, plan, REAR_VIEW_LABEL, REAR_LABEL_XY, "rear view label")
    _add_linked_note(
        adapter, iso, "Isometric View Note", ISO_NOTE_XY, "isometric view note"
    )

    # --- Sheet 2: face A, its frames and datums, and its side view. ---------
    _activate_sheet(adapter, SHEET_NAMES[1])
    back = place_view(adapter, str(SOURCE), "*Back", *BACK_CENTER, scale=VIEW_SCALE)
    side = place_view(adapter, str(SOURCE), "*Left", *SIDE_CENTER, scale=VIEW_SCALE)
    for view in (back, side):
        set_hidden_lines_removed(adapter, view)
    face_annotations = _curated(
        adapter,
        (
            (back, BACK_KEEP, "face A view"),
            (side, SIDE_KEEP, "side view"),
        ),
    )
    assert_imported_precision(
        adapter, face_annotations,
        {name: DRAWING_PRECISION_BY_NAME[name] for name in (*BACK_KEEP, *SIDE_KEEP)},
    )
    set_dimension_callouts(adapter, face_annotations, SIDE_CALLOUTS)
    _set_arrow_sides(adapter, face_annotations, BACK_ARROW_SIDES)
    # These are the same native feature datums and circular zones authored
    # on the part, not +/- positions retyped on a drawing. The drill mouths,
    # the through locator bores' rims and the +X side face's edge on the
    # Front sketch (z = 0) are visible in *Back.
    back_edges = scan_view_edges(back, label="plate mounting-face PMI")
    # The press hole's cylinder edge, where it meets its face-A chamfer, from
    # the scan just taken (no second sweep).
    press_hole_edge = back_edges.circle_at(
        (0.0, 0.0, PRESS_HOLE_CHAMFER), PRESS_HOLE_DIA / 2.0, axis=(0.0, 0.0, 1.0),
        label="plate press hole edge",
    ).edge
    placements = {
        "datum:A": PmiDrawingPlacement(
            side,
            _sheet_xy(adapter, side, DATUM_A_MODEL, "plate mounting datum tag"),
            attachment_xy=_sheet_xy(
                adapter, side, (0.0, _SCREW_Y, 0.0), "plate mounting datum",
            ),
        ),
        "datum:B": PmiDrawingPlacement(
            back, DATUM_B_XY, attachment_xy=_press_hole_landing(adapter, back, DATUM_B_XY),
        ),
        "datum:C": PmiDrawingPlacement(
            back, DATUM_C_XY,
            edge_entity=back_edges.exact_line_through(
                (EDGE_PLUS_X, DATUM_C_MODEL_Y, 0.0), label="plate +X clock edge",
            ).edge,
        ),
        **{
            f"plate_hole_{index}_position": PmiDrawingPlacement(
                back, FRAME_XY[f"plate_hole_{index}_position"],
                edge_entity=back_edges.circle_at(
                    (x, y, 0.0), SCREW_HOLE_DIA / 2.0,
                    axis=(0.0, 0.0, 1.0), label=f"plate hole {index} position",
                ).edge,
            )
            for index, (x, y) in enumerate(SCREW_HOLES, 1)
        },
        **{
            f"plate_locator_{index}_position": PmiDrawingPlacement(
                back, FRAME_XY[f"plate_locator_{index}_position"],
                edge_entity=back_edges.circle_at(
                    (x, y, 0.0), LOCATOR_HOLE_DIA_MM / 2.0,
                    axis=(0.0, 0.0, 1.0), label=f"plate locator {index} position",
                ).edge,
            ) for index, (x, y) in enumerate(LOCATOR_SITES_MM, 1)
        },
    }
    projected = project_part_pmi(
        adapter, placements=placements, datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS, label="plate actual-press-hole locating frame",
    )
    _assert_datum_b_on_press_hole(adapter, projected, press_hole_edge)
    _one_frame_per_group(adapter, projected)
    # The overall width, a reference: across the side edges on face A.
    _overall_reference(
        adapter, back, name="OverallWidth", label="overall width reference",
        entities=tuple(
            back_edges.exact_line_through(point, label=f"plate side edge {index}").edge
            for index, point in enumerate(OVERALL_WIDTH_EDGES_MODEL, 1)
        ),
        entity_types=("EDGE", "EDGE"),
        picks=tuple(
            _sheet_xy(adapter, back, point, f"plate side edge {index}")
            for index, point in enumerate(OVERALL_WIDTH_EDGES_MODEL, 1)
        ),
        text_xy=OVERALL_WIDTH_TEXT_XY,
        orientation="horizontal", expected_mm=OVERALL_WIDTH_MM,
    )
    if not auto_center_marks(adapter, back, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME centre marks to the face A view")
    _add_note(adapter, back, FRONT_VIEW_LABEL, FRONT_LABEL_XY, "front view label")

    artefacts = finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Arm Plate Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_scales={name: SHEET_SCALE for name in SHEET_NAMES},
    )
    return artefacts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
