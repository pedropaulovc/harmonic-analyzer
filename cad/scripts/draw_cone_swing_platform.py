r"""Create the curated machinist drawing for the cone swing platform.

The SLDPRT remains authoritative.  The plan imports the plate outline, lock
notch and corner radii; native Hole Wizard callouts define the pivot
clearance hole, the post-mount taps (transferred from MHA-016 at assembly)
and the post dowel pair (match-reamed with MHA-016, #917 S1); section A-A exposes the shallow pivot-head
relief and plate thickness in solid lines.  Display precision comes from the
model.

The platform is an asymmetric steel wedge with a 1/4-in close-clearance pivot
hole over the stock screw shoulder, paired 1/4-20 post-mount taps, an open
west-edge lock notch, four rounded plan corners and the counterbored slot
for the tip block's hold-down screw (I31).  The three plan views run 1:2
and pivot section A-A 2:1; the lock-notch plan also carries the slot's
station from the pivot.  Slot detail B enlarges a 12 mm radius around the
slot at 2:1, hidden lines dashed, at sheet (88, 44) mm, its slots named by
leadered notes; section C-C (1:1), cut on the plate-profile plan, runs
along the slot for the counterbore depth.  Notch detail D enlarges the
notch's closed end at 2:1: its width, its angle to the west edge at the
mouth and its full R.  The isometric runs 1:3.

Run with SolidWorks open::

    uv run python cad\scripts\draw_cone_swing_platform.py cone-swing-platform
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from collections.abc import Collection, Sequence
from typing import Any

import _drawing_leaders
import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_leader_note,
    add_native_hole_callout,
    add_property_linked_note,
    set_hole_callout_precision,
    add_surface_finish,
    assert_imported_precision,
    create_section_view,
    check_drawing_layout,
    curate_view_dimensions,
    finalize_drawing,
    rebuild_drawing,
    new_project_drawing,
    model_point_in_view,
    read_required_properties,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_dimension_callouts,
    set_reference_dimension,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
import build_cone_swing_platform as _part
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _surface_finish import surface_finish_by_key
from cone_post_dowel_spec import PLATE_DOWEL_CALLOUT, PLATE_DOWEL_REAM_DIA
from cone_swing_platform_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIVOT_BEARING_RELIEF_DIAMETER,
    PIVOT_HOLE_DIA,
    PLATE_STOCK_CALLOUT,
    PLATE_THICKNESS,
    POST_MOUNT_SPEC,
    SURFACE_FINISHES,
    TIP_CBORE_W,
    TIP_SCREW_HALF_TRAVEL,
    TIP_SCREW_LOCAL_Z,
    TIP_SLOT_W,
)
from diagnostics.drawing_layout_audit import collect_document, describe_sheet
from diagnostics import mha091_callout_probe  # diag, never merge


SPEC = DRAWINGS_BY_NAME["cone_swing_platform"]
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

SHEET_SCALE = (1.0, 2.0)  # title block states the principal (plan) scale; iso and section carry their own

# Sheet layout (meters).  Three 1:2 plan views separate the profile, hole
# pattern and lock-notch definitions instead of routing unrelated leaders
# through one narrow 224-mm wedge.  The section and pictorial occupy the
# right-hand field.
PROFILE_CENTER = (0.075, 0.190)
FEATURE_CENTER = (0.180, 0.190)
NOTCH_CENTER = (0.260, 0.190)
# x 0.370, not d382's 0.355: the notch plan's 205.81 dimension line runs at
# x 0.327 (NOTCH_KEEP) to give the run angle's leader room, and it must pass
# 2 mm left of this view (d382 box [0.316, 0.394] at 0.355) and of its
# "ISOMETRIC VIEW" label ([0.3147, 0.3748]); +15 mm leaves the box 9.9 mm
# inside the border.
ISO_CENTER = (0.370, 0.205)
# Its "ISOMETRIC VIEW SCALE 1:3" caption is a property-linked note at a
# fixed sheet point, not the view's own label: it does NOT follow the view.
# fix4b (2c406e963) left it at d382's (0.315, 0.158) and the 205.81 line ran
# through it.  Anchored on the view now: 40 mm left of its centre, as d382
# had it.  ISO_NOTE_EXTENT is its exact box about that anchor (d382
# INote.GetExtent, [0.3147, 0.3748] x [0.1536, 0.1585] at (0.315, 0.158)).
ISO_NOTE_UPPER_LEFT = (ISO_CENTER[0] - 0.040, 0.158)
ISO_NOTE_EXTENT = (-0.0003, -0.0044, 0.0598, 0.0005)
# The section group sits up and right in the open field below the isometric,
# clear of the lock-notch caption; every section annotation shares this shift.
# x 0.030, not 0.020: at 0.020 section C-C's 2.80 arrow line ran up through
# the "(6.35)" stock text left of A-A (aa9766da).  The group's right-hand ink
# then ends ~410 mm, inside the 419 mm border.
SECTION_SHIFT = (0.030, 0.015)


def _shifted(x: float, y: float) -> tuple[float, float]:
    return (x + SECTION_SHIFT[0], y + SECTION_SHIFT[1])


SECTION_CENTER = _shifted(0.335, 0.105)
# The layout audit boxes an Ra symbol 39 mm right of its anchor, so the
# base-slide finish keeps its aa9766da sheet x (box to 0.414) rather than
# taking SECTION_SHIFT's extra 10 mm past the border (0.4189).
BASE_SLIDE_FINISH_XY = (0.375, _shifted(0.355, 0.120)[1])

PROFILE_KEEP = {
    "PlateLenDim": (0.025, PROFILE_CENTER[1]),
    "NorthEastX": (0.045, 0.105),
    "NorthWestX": (0.100, 0.115),
    "SouthWestX": (0.104, 0.258),
    "SouthEastX": (0.045, 0.259),
    # Radial rays must meet actual trimmed corners, not circle extensions.
    # CornerNE/R10 is left and CornerNW/R8 is right in this view.  R10 and
    # R12 shelves sit just above horizontal enough to land inside their arcs
    # while clearing the 223.4 witness lines.
    "CornerNER": (0.045, 0.139),
    # By its corner, down-right of the arc (MHA-091 Fable review, 63fb3bd2d:
    # at (0.135, 0.118) the leader ran ~58 mm across the 11.0's field).  The
    # ray meets the fillet at ~-27 deg and passes 2.8 mm off the 11.0's
    # witness top (x 0.0773, y 0.1332); the text sits 12 mm over its value.
    "CornerNWR": (0.102, 0.130),
    "CornerSWR": (0.110, 0.249),
    "CornerSER": (0.040, 0.2435),
    # The top relief's width, over its U: the dimension line 3.6 mm above the
    # pivot (1 mm over the round end), the value outside the right witness,
    # past the plate's west edge -- 8 mm off the R8.0, above the 11.0's witness
    # top (0.1332) and 10 mm under the C-C line.  On the hole-location plan the
    # same line fenced the U on three sides, so no leader could name the
    # feature without crossing it (MHA-091 round 6, B1).
    "PivotBearingReliefDia": (0.090, 0.1413),
}
# #917 S1: the hole-location plan prints no station.  The post-mount taps
# transfer from MHA-016 at assembly and the dowel pair is match-drilled
# through the fitted post, so their native callouts carry everything.
FEATURE_KEEP: dict[str, tuple[float, float]] = {}
# The locating instruction ahead of the native tap callout, in the harmonic
# base's #837 form: the semicolon separates it from "1/4-20 UNC - 2B".
POST_MOUNT_TRANSFER_CALLOUT = "TRANSFER FROM MHA-016\nAT ASSEMBLY;"
# The dowel callout, in the band left of the plan's south half, between the
# profile's west-side dimensions and the plate's east edge (~x 0.165 there);
# its leader runs right to the north dowel's rim.  Provisional until a seat
# render: nothing was measured here.
PLATE_DOWEL_CALLOUT_XY = (0.117, 0.222)
# The three 1:2 plans centre on the plate's plan box; sheet +x is model +x
# (west), sheet +y model -z (south).
PLAN_SCALE = 0.0005
_PLAN_MID_X = (_part.WEST_HALF_S - _part.EAST_HALF_S) / 2.0
_PLAN_MID_Z = _part.NORTH_OVERHANG - _part.PLATE_LEN / 2.0


def plan_xy(center: tuple[float, float], x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point of plate-local (x, z) on the 1:2 plan centred at ``center``."""
    return (
        center[0] + (x_mm - _PLAN_MID_X) * PLAN_SCALE,
        center[1] - (z_mm - _PLAN_MID_Z) * PLAN_SCALE,
    )


def _plan_east_edge_x(z_mm: float) -> float:
    run = (_part.NORTH_OVERHANG - z_mm) / _part.PLATE_LEN
    return -(_part.HALF_WIDTH_N + (_part.EAST_HALF_S - _part.HALF_WIDTH_N) * run)


# I31 moved the tip slot 27.7 south of the pivot, out of reach of one detail
# circle, so its station prints here: on the plan's open east side, sharing
# nothing with the NorthEdgeZ/CapECz witnesses on the west.  The dimension
# line stands 9 mm (sheet) off the plate's east edge at the slot; its text
# sits inside the span, centred on the line (the 205.81's form).  d382 hung
# it left of the line just south of the span, on a shoulder that ended in a
# T on the hole-location plan's 189.26 line (x 0.225; Main's MHA-091 eye
# pass of fix4b).  The arrows are pinned inside: 4.1 mm of line each side of
# the text break carries a 3.4 mm head.
_NOTCH_SLOT_XY = plan_xy(NOTCH_CENTER, -TIP_SCREW_HALF_TRAVEL, TIP_SCREW_LOCAL_Z)
_NOTCH_PIVOT_XY = plan_xy(NOTCH_CENTER, 0.0, 0.0)
# The notch's cut direction out of the cap toward the mouth, on the sheet
# (sheet +x is model +x, sheet +y model -z).  Only the half of the cap circle
# away from the mouth is drawn.
CAP_MOUTH_AXIS = (_part.NOTCH_CUT_U[0], -_part.NOTCH_CUT_U[1])
TIP_SLOT_Z_LINE_X = plan_xy(NOTCH_CENTER, _plan_east_edge_x(TIP_SCREW_LOCAL_Z), 0.0)[0] - 0.009
NOTCH_KEEP = {
    # Pivot-to-north-edge lives here, sharing the 205.81 pivot witness: in the
    # profile the R8 corner ray has no path that clears this dimension.
    "NorthEdgeZ": (0.270, 0.150),
    # Text between its witnesses: outside, it read as spanning from the corner.
    "CapECx": (0.2652, 0.258),
    # 22 mm right of d382's 0.305: it made room for the notch run angle's
    # leader (tipslot-fix3/4), which moved to detail D as the mouth angle in
    # MHA-091 round 6; the layout the eye passes cleared stands.  The text
    # sits at y 0.170, 7.5 mm under the isometric's box.  The lower witness
    # (y 0.1377) passes 2.4 mm over A-A's "(6.35)" (top 0.1353) and the lower
    # arrowhead 2.9 mm right of it.
    "CapECz": (0.327, 0.170),
    "TipSlotZ": (TIP_SLOT_Z_LINE_X, (_NOTCH_SLOT_XY[1] + _NOTCH_PIVOT_XY[1]) / 2.0),
}
SECTION_KEEP = {
    # Outside its witnesses, the text hangs LEFT of the dimension line (away
    # from the plate), right edge on the line and centred on this y.  The
    # three lines (~26 x 15.3 mm) sit in x 0.3035..0.3295, y 0.1213..0.1366:
    # under the 205.81 witness (0.1379), right of C-C's 2.80 arrow line
    # (x 0.2993).  The flush widest line sits above the top witness, the
    # set-back last line beside the arrowhead (aa9766da: "AS SUPPLIED" there
    # ran its D into it).
    "PlateThk": _shifted(0.300, 0.114),
    "PivotBearingReliefDepth": _shifted(0.365, 0.115),
}

# I31 tip-block hold-down slot: too small to dimension at 1:2, so DETAIL B
# enlarges the slot on the hole-location plan to 2:1, with
# hidden lines shown so the underside counterbored slot reads dashed.  At
# 1:1 (run 7959e994) five dimensions and two cutter callouts crowded a 24 mm
# circle, texts over the outline and each other; 2:1 gives them the room.
# The counterbore depth is section C-C's imported dimension.
#
# The free band is x 0.0127..0.216 under the plan captions (y <= 0.0805)
# and above the bottom border (y >= 0.0127).  Run e86bf319 put the detail in
# its right half, where the title block (x >= 0.216, y <= 0.066) boxed its
# callouts in and its native label fell 8.9 mm through the bottom border.
# So the relief-fit note moves to the band's lower right and the detail to
# its left half: the wide callouts get the open field right of the circle.
# A vertical dimension's text hangs outward from its dimension line (the
# e86bf319 extents: left of a left-side line, right of a right-side one).
# Sheet +x is model +x (west) and sheet +y is model -z (south) in these plans.
# I31: centred on the slot.  Until then the circle took in the pivot as
# well; 27.7 south, the slot's station from it prints on the notch plan.
DETAIL_MODEL_Z = TIP_SCREW_LOCAL_Z
DETAIL_RADIUS_MM = 12.0
DETAIL_SCALE = (2, 1)
_DETAIL_S = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
# The layout audit boxes a detail view by its native outline, which run
# eaafbc73 measured at the circle plus 10.4 mm a side ([53.6, 9.6]..
# [122.4, 78.4] mm around a 48 mm circle): it crossed the 9.7 mm zone border
# by 0.1 and ran 3.5 into the relief note.  Centred here, the outline sits
# at [49.1, 10.6]..[117.9, 79.4]: right of the label, under the plan
# captions (80.5) and 2.1 short of the note.
DETAIL_CENTER = (0.0835, 0.045)
DETAIL_OUTLINE_PAD = 0.0104
# DETAIL D: the lock notch's closed end and mouth at 2:1.  The notch is a
# slot: its width (NotchW, 8.00 +0.10/0, the end mill's band), a full R at
# the closed end, located at that R's centre on the notch plan (32.70,
# 205.86 since #917 S1 ran the closed end 0.30 past the stud seat), and its
# run as the angle between the south rail and the plate's west edge at the
# mouth -- both legs real edges, the vertex the mouth's
# south corner, a protractor check (MHA-091 round 6; the old 9.11 deg ran
# from a hidden east-west ray on the notch plan).  The R is a leadered note:
# the width states the size once (the Ø8.00 restated it).
# Circled on the hole-location plan (cap at (193.25, 240.57) mm, its 3 mm
# circle 8.8 mm under the 2X Ø5.11 shoulder and 5.3 over the 189.26's
# witness), drawn in the open field over the isometric: the outline (circle
# + DETAIL_OUTLINE_PAD) tops out at 266.4 mm, the circle's foot 1.3 mm over
# the isometric's padded box (pictorial: the audit does not collide it; its
# part stands ~20 mm lower here).  In the detail the notch opens sheet-right
# (the plate's west edge runs nearly sheet-up through the mouth) and the
# plate's material lies left of that edge.
CAP_DETAIL_SCALE = (2, 1)
_CAP_DETAIL_S = CAP_DETAIL_SCALE[0] / CAP_DETAIL_SCALE[1] / 1000.0
CAP_DETAIL_RADIUS_MM = 6.0
CAP_DETAIL_CENTER = (0.357, 0.244)
CAP_DETAIL_SHEET_RADIUS = CAP_DETAIL_RADIUS_MM * _CAP_DETAIL_S
CAP_DETAIL_ARC_RADIUS = _part.SLOT_W / 2.0 * _CAP_DETAIL_S


def cap_detail_xy(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point of plate-local (x, z) in detail D (centred on the cap)."""
    return (
        CAP_DETAIL_CENTER[0] + (x_mm - _part.NOTCH_CAP_E_XZ[0]) * _CAP_DETAIL_S,
        CAP_DETAIL_CENTER[1] - (z_mm - _part.NOTCH_CAP_E_XZ[1]) * _CAP_DETAIL_S,
    )


# The mouth angle's vertex (the south rail meets the west edge) and a point
# along each leg: the rail back into the plate, the edge running south.
MOUTH_ANGLE_VERTEX_XY = cap_detail_xy(*_part.NOTCH_CUT_POINTS["mouth_s"])
MOUTH_ANGLE_RAIL_XY = cap_detail_xy(
    _part.NOTCH_CUT_POINTS["mouth_s"][0] - _part.NOTCH_CUT_U[0],
    _part.NOTCH_CUT_POINTS["mouth_s"][1] - _part.NOTCH_CUT_U[1],
)
MOUTH_ANGLE_EDGE_XY = cap_detail_xy(
    _part.NOTCH_CUT_POINTS["mouth_s"][0] + _part._EDGE_SX,
    _part.NOTCH_CUT_POINTS["mouth_s"][1] + _part._EDGE_SZ,
)
CAP_DETAIL_KEEP = {
    # Above the circle, in the material wedge (up-left of the south mouth
    # corner, between the rail running back and the edge running south): an
    # angular dimension prints the sector that holds its text, so here it is
    # the acute 87, not the 93 supplement.  The arc runs ~10.7 mm out, its
    # top 4.5 mm under the zone frame; the glyphs stand 2 mm off the circle.
    "NotchMouthAngle": (0.3575, 0.2600),
    # Right of the circle, above the width's span: its witnesses extend the
    # rails out through the mouth, and a near-vertical dimension's value hangs
    # outward (right) of its line, beside it, outside the span (detail B's
    # TipSlotW form) -- between the witnesses the line would run through it.
    "NotchW": (0.3865, 0.2560),
}
# "DETAIL D / SCALE 2 : 1", left of the outline (detail B's 1.2 mm gap
# plus 0.4): its box is 31.5 x 16.4 mm (d382 INote.GetExtent), in the field
# the Ø8.00 and the run angle's leader left, 5.4 mm over the 205.81's upper
# witness (y 0.2406) and above its dimension line (x 0.327).
CAP_DETAIL_LABEL_SIZE = (0.0315, 0.0164)
CAP_DETAIL_LABEL_LOWER_LEFT = (
    CAP_DETAIL_CENTER[0]
    - CAP_DETAIL_SHEET_RADIUS
    - DETAIL_OUTLINE_PAD
    - 0.0016
    - CAP_DETAIL_LABEL_SIZE[0],
    0.246,
)
DETAIL_SHEET_RADIUS = DETAIL_RADIUS_MM * _DETAIL_S
_SLOT_Y = DETAIL_CENTER[1] + (DETAIL_MODEL_Z - TIP_SCREW_LOCAL_Z) * _DETAIL_S
# Between its extension lines a vertical dimension's text is CENTRED on its
# dimension line, which then runs through it (81788ce9: "SLOT|THRU",
# "11.|00"); outside them the text hangs outward, one edge on the line,
# centred on the keep y.  So every vertical dimension here parks its text
# OUTSIDE its span.  The two width spans overlap (counterbore 38.7..51.3,
# slot 41..49), so the slot's dimension line runs up past the
# counterbore's upper extension line to its text (below the spans the
# detail's own label sits, since I31 centred the circle on the slot).  The slot sits nearest
# the part, the counterbore outboard (its extension lines then never cross
# the slot's dimension line inside the slot's span).  The slots are named
# by leadered notes, not dimension text.
DETAIL_KEEP = {
    # Above the circle, each 2.00 outside its own extension lines and under
    # the plan caption row (y >= 0.0805).  The west one sits in toward the
    # circle, left of the through-slot leader's path.
    "TipSlotEastCx": (
        DETAIL_CENTER[0] - 0.020,
        DETAIL_CENTER[1] + DETAIL_SHEET_RADIUS + 0.005,
    ),
    "TipSlotWestCx": (
        DETAIL_CENTER[0] + 0.0135,
        DETAIL_CENTER[1] + DETAIL_SHEET_RADIUS + 0.005,
    ),
    # Left, nearest the circle: the through slot, text above both spans
    # (over the counterbore's upper extension line).
    "TipSlotW": (DETAIL_CENTER[0] - 0.0275, _SLOT_Y + 0.0125),
    # Left, outboard: the counterbored slot, text above the slot's.
    "TipCboreW": (DETAIL_CENTER[0] - 0.0465, _SLOT_Y + 0.0225),
}
# Arrowheads inside the extension lines: outside, the slot's 8 mm span put
# an arrow tail across the counterbore's upper extension line (81788ce9).
DETAIL_ARROWS_INSIDE = ("TipSlotW", "TipCboreW")
# Each slot named by a leadered note (2.5 mm text, anchored upper-left) in
# the open field right of the circle.  Feature identification only: the
# banded 4.0 and 6.50 +0.1/0 dimensions own the widths, and a cutter is a
# method (MHA-091 Fable review, 63fb3bd2d: "Ø4 END MILL" restated the 4.0 in
# another spelling and band).
# Each leader tip lands on the WEST (sheet-right) end arc of its slot, at a
# sheet angle from that arc's centre.  A leadered note's INote.GetExtent --
# what the layout audit boxes -- runs from its leader tip to its text, so two
# notes whose texts sit on the same side of their tips nest (ec70186e: 65.5
# x 12.1 mm overlap).  The slot note therefore rises from the arc's upper
# quadrant to text above; the counterbore note drops from its lower quadrant
# to text below, its leader crossing pivot-to-slot's dimension line (the only
# path: below that line's foot sits the relief note).


def detail_xy(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point of plate-local (x, z) in detail C (centred on x = 0 at
    DETAIL_MODEL_Z, the slot's station)."""
    return (
        DETAIL_CENTER[0] + x_mm * _DETAIL_S,
        DETAIL_CENTER[1] - (z_mm - DETAIL_MODEL_Z) * _DETAIL_S,
    )


# The west end arc's centre is the model's: TIP_SCREW_HALF_TRAVEL (a literal
# 2.0 here outlived b1f7e824b's 2.0 -> 2.5 and put the slot note's tip 1 mm
# off its arc, S1 leaf 917-s1-5974).
_WEST_ARC_CENTER = detail_xy(TIP_SCREW_HALF_TRAVEL, TIP_SCREW_LOCAL_Z)
# The leader roots on the note's FIRST line, on the side toward its tip
# (d382 leaf log :519: the C'BORE note's text top at 44.5 mm, its leader at
# 43.1), and a 2.5 mm line pitches 3.35 mm (the same note: two lines,
# 37.8..44.5).
NOTE_LEADER_ROOT_DROP = 0.0014
NOTE_LINE_PITCH = 0.00335


@dataclass(frozen=True)
class ArcNote:
    """One leadered note: ``text`` at ``text_xy`` pointing at a circular edge.

    The edge is ``feature``'s circle of ``radius_mm`` about the plate-local
    ``arc_center_mm`` (x, z), drawn in a plan-oriented view whose image of
    that centre is ``sheet_center`` at ``sheet_scale`` sheet metres per model
    mm (sheet +x = +x, sheet +y = -z)."""

    key: str
    text: str
    text_xy: tuple[float, float]
    feature: str  # the native cut whose arc the leader names
    radius_mm: float
    tip_deg: float  # sheet angle of the tip on the arc
    model_y_mm: float | None  # the arc's face; None = either coincident arc
    arc_center_mm: tuple[float, float]
    sheet_center: tuple[float, float]
    sheet_scale: float


CUTTER_NOTES = (
    ArcNote(
        "slot",
        "SLOT THRU",
        (0.121, 0.0785),
        "TipScrewSlot",
        TIP_SLOT_W / 2.0,
        60.0,
        PLATE_THICKNESS,  # the visible top-face arc, not the hidden floor one
        (TIP_SCREW_HALF_TRAVEL, TIP_SCREW_LOCAL_Z),
        _WEST_ARC_CENTER,
        _DETAIL_S,
    ),
    ArcNote(
        "cbore",
        "C'BORE SLOT\nFROM UNDERSIDE",
        # I31: 2.5 mm lower than 0.047, so its extent stays 3 mm under the
        # slot note's, whose tip came down 10 mm with the re-centred slot.
        (0.121, 0.0445),
        "TipScrewCbore",
        TIP_CBORE_W / 2.0,
        -35.0,
        None,  # the dashed arc: underside outline and floor edge project as one
        (TIP_SCREW_HALF_TRAVEL, TIP_SCREW_LOCAL_Z),
        _WEST_ARC_CENTER,
        _DETAIL_S,
    ),
)
# Detail D's full R: "R" alone (ASME: a full radius is stated, its size is
# the width's), in the mouth right of the circle between the width's
# witnesses; its leader runs back along the notch, clear of the cap centre,
# to the drawn (closed) half of the cap arc up-left.
CAP_R_NOTE = ArcNote(
    "cap",
    "R",
    (0.3730, 0.2455),
    "LockNotchCapE",
    _part.SLOT_W / 2.0,
    150.0,
    PLATE_THICKNESS,
    _part.NOTCH_CAP_E_XZ,
    CAP_DETAIL_CENTER,
    _CAP_DETAIL_S,
)
# The top relief named on the hole-location plan (MHA-091 round 6, B1): a
# feature identification, not a size -- the profile's 10.50 is the width,
# the fit note its depth.  Named by features, not a compass: to a blind
# reader of 68565ace "OPEN TO NORTH EDGE" contradicted a relief opening
# toward the sheet's lower edge (sheet-down is model north; codex B2).  The
# block stands where the 10.50's callout stood, left of the plate between
# the 195.09 line (x 0.130) and the plate's east edge, its first line --
# where the leader roots -- at y 0.153, its last 4 mm over the 195.09's
# pivot witness (y 0.1377).  The leader drops right to the U's round end at
# 135 deg, clear of detail B's circle; nothing else fences the U here.
RELIEF_ID_NOTE = ArcNote(
    "relief",
    "TOP RELIEF\nFULL R ON PIVOT\nOPEN THRU\nPIVOT END",
    (0.1330, 0.1544),
    "PivotBearingRelief",
    PIVOT_BEARING_RELIEF_DIAMETER / 2.0,
    135.0,
    PLATE_THICKNESS,
    (0.0, 0.0),
    plan_xy(FEATURE_CENTER, 0.0, 0.0),
    PLAN_SCALE,
)
CUTTER_NOTE_CHAR_HEIGHT = 0.0025
# Physical-edge bound on a leader tip, model metres (the R8 proof's bound).
LEADER_TIP_BOUND_M = 0.00001


def arc_note_tip(note: ArcNote) -> tuple[float, float]:
    """The sheet point on ``note``'s arc its leader must touch."""
    angle = math.radians(note.tip_deg)
    r = note.radius_mm * note.sheet_scale
    return (
        note.sheet_center[0] + r * math.cos(angle),
        note.sheet_center[1] + r * math.sin(angle),
    )


def arc_note_model_tip(note: ArcNote) -> tuple[float, float, float]:
    """``arc_note_tip`` in part metres (sheet +x = +x, sheet +y = -z)."""
    angle = math.radians(note.tip_deg)
    cx, cz = note.arc_center_mm
    return (
        (cx + note.radius_mm * math.cos(angle)) / 1000.0,
        (note.model_y_mm if note.model_y_mm is not None else PLATE_THICKNESS) / 1000.0,
        (cz - note.radius_mm * math.sin(angle)) / 1000.0,
    )


def arc_note_leader(note: ArcNote, text_width: float) -> _drawing_leaders.Segment:
    """The leader as SolidWorks roots it: the first line's side toward the
    tip, ``NOTE_LEADER_ROOT_DROP`` under the text's top, to the tip."""
    tip = arc_note_tip(note)
    right = note.text_xy[0] + text_width
    x = note.text_xy[0] if abs(tip[0] - note.text_xy[0]) < abs(tip[0] - right) else right
    return ((x, note.text_xy[1] - NOTE_LEADER_ROOT_DROP), tip)


# The native "DETAIL B / SCALE 2:1" label, moved by its measured extent:
# lower left of its box, in the band's lower-left corner under the slot text.
DETAIL_LABEL_LOWER_LEFT = (0.016, 0.015)
# The pivot relief-fit note (2.5 mm text, ~0.095 x 0.018): anchored by its
# upper-left corner, lower right of the free band, left of the title block.
RELIEF_NOTE_XY = (0.120, 0.034)
# SECTION C-C cuts across the plate along the slot, so the counterbore's
# depth is an imported model dimension (drawing-simplicity rule 2: a typed
# "4.20 DEEP" was not).  Its cutting line lives on the 1:2 plate-profile
# plan, not in detail B: in the detail it lay ON the slot centreline, so
# pivot-to-slot's extension line ran along it and its arrows sat in every
# width extension's path.  On the plan the default arrows (looking north,
# sheet-down) ran beside the NorthWestX extension line and through the R8 leader,
# so the cut looks SOUTH (arrows sheet-up).
#
# The line runs PAST both plate edges (a full section across the slot
# station): as a +-9 mm partial cut its sheet-up arrows sat inside the
# plate, and the west letter, 31..44 mm south of the cut where the plate
# flares, landed on the sloped west edge (Main's eye-pass of 8783776d).
# Each end clears its edge at the letter's far station by the letter's half
# width (5.5 model mm at 1:2) plus 1.5 -- SLOT_SECTION_LINE_X_MM, derived
# below from the plate's edges.
CC_LETTER_TOP_SHEET = 0.022  # a letter's far side above the line (8783776d)
CC_LETTER_HALF_W_MM = 5.5
CC_LETTER_EDGE_CLEAR_MM = 1.5
# 1:1, full width: the strip is the plate edge-on x 6.35, in the
# pocket right of the drill callout RD1 (x <= 0.246), under the notch plan
# (y >= 0.1286) and its lifted caption (y >= 0.1207), with its native label
# centred directly under it, right of the plan caption row (x <= 0.2185)
# and above the title block (y 0.066): 8783776d printed the label 50 mm left
# of its strip.  5 mm lower than aa9766da, to make room for the caption.
SLOT_SECTION_CENTER = (0.279, 0.1059)
# Where the depth text hangs: beyond the strip's left end, or mirrored past
# its right end when SolidWorks attaches the depth at the right-hand
# counterbore edge (looking south mirrors the strip).
SLOT_SECTION_KEEP = {
    "TipCboreDepth": (SLOT_SECTION_CENTER[0] - 0.0205, SLOT_SECTION_CENTER[1]),
}
SLOT_SECTION_DEPTH_RIGHT = (SLOT_SECTION_CENTER[0] + 0.0205, SLOT_SECTION_CENTER[1])

# The view that owns each kept model dimension: it prints once, there.  A
# targeted import brings a feature's every marked dimension, so a view that
# shares a feature with another (the notch plan and detail B both import
# TipScrewSlotProfile) receives the other's dimensions and must delete them;
# the sheet-wide walk after curation proves the deletion held.
VIEW_KEEPS: dict[str, dict[str, tuple[float, float]]] = {
    "profile plan": PROFILE_KEEP,
    "feature plan": FEATURE_KEEP,
    "notch plan": NOTCH_KEEP,
    "pivot section": SECTION_KEEP,
    "tip screw slot detail": DETAIL_KEEP,
    "lock notch cap detail": CAP_DETAIL_KEEP,
    "tip screw slot section": SLOT_SECTION_KEEP,
}
DIMENSION_OWNER: dict[str, str] = {
    name: view for view, keep in VIEW_KEEPS.items() for name in keep
}
if len(DIMENSION_OWNER) != sum(len(keep) for keep in VIEW_KEEPS.values()):
    raise AssertionError("a kept dimension is kept by two views")


def dimension_placement_errors(seen: dict[str, Sequence[str]]) -> list[str]:
    """Kept dimensions not printed exactly once, on their owning view.

    ``seen`` maps each view label to the model-dimension names its
    annotations carry; names no view keeps (hole callouts) are ignored."""
    errors = []
    for name, owner in sorted(DIMENSION_OWNER.items()):
        places = [view for view, names in seen.items() for item in names if item == name]
        if places != [owner]:
            errors.append(f"{name}: expected once on {owner}, found on {places}")
    return errors
# The native label box measured 46.5 x 16.2 mm; centred under the strip.
SLOT_SECTION_LABEL_LOWER_LEFT = (SLOT_SECTION_CENTER[0] - 0.02325, 0.0815)
# The lock-notch caption sits directly under its own view, not on the plan
# caption row: there it printed right under "SECTION C-C / SCALE 1:1" and
# read as that section's caption (aa9766da).  Its 59.7 x 4.8 mm box,
# anchored upper-left and centred under the notch plan, clears the 7.0
# arrow tip (y 0.1276) above and the C-C strip (ink top ~0.1152) below.
NOTCH_CAPTION_UPPER_LEFT = (NOTCH_CENTER[0] - 0.02985, 0.1255)
# Its exact box about that anchor (d382 INote.GetExtent,
# [0.2298, 0.2899] x [0.1215, 0.1258]).
NOTCH_NOTE_EXTENT = (-0.00035, -0.0040, 0.05975, 0.0003)
# The pivot on the profile plan, as the farm measured it (plan_xy agrees to
# 0.05 mm; the corner stations below are projected, not read off a render).
PROFILE_PIVOT_XY = (0.0718, 0.1377)


def corner_station_model_m(label: str) -> tuple[float, float, float]:
    """Model point (m) of a corner fillet's centre on the plate top.

    The profile's radius proof matches each owned arc against this point
    projected into the view, so the station follows the outline whenever the
    part moves a corner."""
    x, z = _part.corner_fillet_center(label)
    return (x / 1000.0, PLATE_THICKNESS / 1000.0, z / 1000.0)


def plate_edge_mm(z_mm: float, side: int) -> float:
    """Model x of the plate's straight east (-1) / west (+1) edge at ``z_mm``."""
    run = (_part.NORTH_OVERHANG - z_mm) / _part.PLATE_LEN
    if side < 0:
        return -(_part.HALF_WIDTH_N + (_part.EAST_HALF_S - _part.HALF_WIDTH_N) * run)
    return _part.WEST_HALF_N + (_part.WEST_HALF_S - _part.WEST_HALF_N) * run


def plate_outline_x_mm(z_mm: float, side: int) -> float:
    """Model x of the finished outline, north corner rounds included, at ``z_mm``.

    North of where a north corner's round meets its side edge the outline is
    the round, not the straight edge ``plate_edge_mm`` gives: at the pivot
    station the NE R10 trims the east end to -15.89 (the straight edge would
    read -16.25)."""
    label = "NE" if side < 0 else "NW"
    labels = [corner[0] for corner in _part._CORNERS]
    index = labels.index(label)
    _label, x, z, radius = _part._CORNERS[index]
    south = _part._CORNERS[index - 1 if side < 0 else (index + 1) % 4]
    dx, dz = south[1] - x, south[2] - z
    length = math.hypot(dx, dz)
    cx, cz = _part.corner_fillet_center(label)
    # The round meets the side edge at the centre's foot on that edge.
    tangent_z = z + ((cx - x) * dx + (cz - z) * dz) / length * dz / length
    if z_mm <= tangent_z:
        return x + (z_mm - z) / dz * dx
    return cx + side * math.sqrt(radius * radius - (z_mm - cz) ** 2)


# Section A-A cuts across the plan at the pivot (model z 0) at 2:1 and shows
# only the cut face, so SolidWorks centres that strip on SECTION_CENTER.  The
# PlateThk witnesses stop PLATE_THK_WITNESS_SET_BACK short of the strip's
# east end.  I31's wider north-west lengthened the strip 2.9 mm west, which
# moves the pivot and the east end 2.9 mm (sheet) left; the witness origin
# (the plate's south-west extreme, x415 before I31) moves with them, so the
# gap holds and only the absolute end moves.  Before I31 the east end was
# x310.2 -- test_pivot_section_east_end_matches_the_pre_i31_measurement.
PIVOT_SECTION_SCALE = 2.0 / 1000.0
PLATE_THK_WITNESS_SET_BACK = 0.0012


def pivot_section_strip_mm() -> tuple[float, float]:
    """Model x of section A-A's east and west cut ends (the pivot station)."""
    return (plate_outline_x_mm(0.0, -1), plate_outline_x_mm(0.0, +1))


def pivot_section_pivot_x() -> float:
    """Sheet x of the pivot in section A-A (sheet +x is model +x, west)."""
    east, west = pivot_section_strip_mm()
    return SECTION_CENTER[0] - (east + west) / 2.0 * PIVOT_SECTION_SCALE


def plate_thk_witness_end_x(pivot_x: float) -> float:
    """Sheet x where the PlateThk witnesses should stop, given the pivot's."""
    east, _west = pivot_section_strip_mm()
    return pivot_x + east * PIVOT_SECTION_SCALE - PLATE_THK_WITNESS_SET_BACK


_CC_LETTER_FAR_Z = TIP_SCREW_LOCAL_Z - CC_LETTER_TOP_SHEET / PLAN_SCALE
SLOT_SECTION_LINE_X_MM = tuple(
    side
    * math.ceil(
        (
            abs(plate_edge_mm(_CC_LETTER_FAR_Z, side))
            + CC_LETTER_HALF_W_MM
            + CC_LETTER_EDGE_CLEAR_MM
        )
        * 10.0
        - 1e-6
    )
    / 10.0
    for side in (-1, 1)
)


def slot_section_line_model_points() -> tuple[tuple[float, float, float], ...]:
    """The C-C cutting line's ends, part metres, past both edges at the slot."""
    return tuple(
        (x / 1000.0, PLATE_THICKNESS / 1000.0, TIP_SCREW_LOCAL_Z / 1000.0)
        for x in SLOT_SECTION_LINE_X_MM
    )




_COSMETIC_THREAD_LAYER = "COSMETIC-THREADS-HIDDEN"


# --- the notch plan's ink, predicted -----------------------------------------
# Ink the d382 render (300 dpi) and the d382/fix3 leaf dumps measured, sheet
# metres: an arrowhead's length and half width, and a shouldered leader's
# shoulder under its value (the R8.0's).
DIMENSION_ARROW_LENGTH = 0.0034
DIMENSION_ARROW_HALF_WIDTH = 0.0004
LEADER_SHOULDER_DROP = 0.00278  # below the value's centre
LEADER_SHOULDER_HALF = 0.00675  # either side of it
CAP_EC_Z_WITNESS_START = 0.0010  # past the cap centre
CAP_EC_Z_WITNESS_PAST_LINE = 0.0010
CAP_EC_Z_TEXT_SIZE = (0.0120, 0.0035)
# A linear dimension's line stops this far either side of its text's
# anchor (d382 dump: 205.81 at 0.180 breaks at 0.1772 and 0.1828).
DIMENSION_TEXT_BREAK = 0.0028
# The pivot's witnesses start this far east of it (d382: 0.2607 at 0.25675).
PIVOT_WITNESS_START = 0.0040
# The 33.00 (CapECx) dimension line, 2.8 mm under its text like the
# 205.81's.  Its right arrow sits outside, on the cap-centre witness, tail
# running right.
CAP_E_CX_LINE_BELOW_TEXT = 0.0028
# An arrow tip lies on the drawn cap arc: this close to its circle, on the
# closed side of the diameter across the mouth.
CAP_ARC_TIP_TOLERANCE = 0.00025
# layoutcheck's gating rule: an outside arrow's tail counts as arrow ink
# for its first 6.35 mm.
OUTSIDE_ARROW_TAIL = 0.00635
# A line nearer a text block than this reads as touching it.
LINE_TEXT_CLEARANCE = 0.0005
ARROW_TEXT_CLEARANCE = _drawing_leaders.ARROW_TEXT_CLEARANCE
# A leader keeps this far off every stroke it does not cross or root on
# (Main's floor, tipslot-fix4).
LEADER_INK_CLEARANCE = 0.0020
# Tipslot ruling (b): another annotation's line may cross a moved value's
# dimension ink only farther than half the value's text height from it, and
# only as a named, expected crossing (reported, not gated).
DIMENSION_CROSSING_TEXT_FRACTION = 0.5
EXPECTED_DIMENSION_CROSSINGS: dict[frozenset[str], str] = {}


@dataclass(frozen=True)
class SheetInk:
    """One neighbourhood's ink, keyed by annotation, in sheet metres.

    ``lines`` are dimension and extension lines, ``arcs`` dimension arcs (as
    chords), ``arrows`` arrowheads along their axis, ``leaders`` offset-text
    leaders."""

    texts: dict[str, _drawing_leaders.Box]
    lines: dict[str, list[_drawing_leaders.Segment]]
    arcs: dict[str, list[_drawing_leaders.Segment]]
    arrows: dict[str, list[_drawing_leaders.Segment]]
    leaders: dict[str, list[_drawing_leaders.Segment]]


def _centred_box(
    xy: tuple[float, float], size: tuple[float, float]
) -> _drawing_leaders.Box:
    return (
        xy[0] - size[0] / 2.0,
        xy[1] - size[1] / 2.0,
        xy[0] + size[0] / 2.0,
        xy[1] + size[1] / 2.0,
    )


def _anchored_box(
    anchor: tuple[float, float], extent: tuple[float, float, float, float]
) -> _drawing_leaders.Box:
    return (
        anchor[0] + extent[0],
        anchor[1] + extent[1],
        anchor[0] + extent[2],
        anchor[1] + extent[3],
    )


def notch_plan_ink(
    cap_text_xy: tuple[float, float] | None = None,
    iso_note_xy: tuple[float, float] | None = None,
) -> SheetInk:
    """The notch plan's ink around the cap, predicted: the 205.81 (both legs
    and witnesses), the 33.00's outside tail, the 27.70 inside its span, and
    the lock-notch and isometric captions (property-linked notes, boxed from
    their measured extents).

    ``cap_text_xy`` places the 205.81 and ``iso_note_xy`` the isometric
    caption (the layout's by default).
    """
    cap = plan_xy(NOTCH_CENTER, *_part.NOTCH_CAP_E_XZ)
    cap_text = NOTCH_KEEP["CapECz"] if cap_text_xy is None else cap_text_xy
    cap_x = cap_text[0]
    witness = (
        (cap[0] + CAP_EC_Z_WITNESS_START, cap[1]),
        (cap_x + CAP_EC_Z_WITNESS_PAST_LINE, cap[1]),
    )
    # The dump's 205.81 line stops 2.8 mm either side of its text's anchor;
    # the lower leg runs on to the pivot's witness.
    pivot = _NOTCH_PIVOT_XY
    cap_line = ((cap_x, cap[1]), (cap_x, cap_text[1] + DIMENSION_TEXT_BREAK))
    cap_lower_leg = ((cap_x, cap_text[1] - DIMENSION_TEXT_BREAK), (cap_x, pivot[1]))
    cap_lower_witness = (
        (pivot[0] + PIVOT_WITNESS_START, pivot[1]),
        (cap_x + CAP_EC_Z_WITNESS_PAST_LINE, pivot[1]),
    )
    cap_arrow = ((cap_x, cap[1]), (cap_x, cap[1] - DIMENSION_ARROW_LENGTH))
    slot_z = NOTCH_KEEP["TipSlotZ"]
    slot_y = _NOTCH_SLOT_XY[1]
    slot_z_lines = [
        ((slot_z[0], pivot[1]), (slot_z[0], slot_z[1] - DIMENSION_TEXT_BREAK)),
        ((slot_z[0], slot_z[1] + DIMENSION_TEXT_BREAK), (slot_z[0], slot_y)),
    ]
    slot_z_arrows = [
        ((slot_z[0], pivot[1]), (slot_z[0], pivot[1] + DIMENSION_ARROW_LENGTH)),
        ((slot_z[0], slot_y), (slot_z[0], slot_y - DIMENSION_ARROW_LENGTH)),
    ]
    iso_note = ISO_NOTE_UPPER_LEFT if iso_note_xy is None else iso_note_xy
    cx_line_y = NOTCH_KEEP["CapECx"][1] - CAP_E_CX_LINE_BELOW_TEXT
    cx_tail = ((cap[0], cx_line_y), (cap[0] + OUTSIDE_ARROW_TAIL, cx_line_y))
    return SheetInk(
        texts={
            "CapECz": _centred_box(cap_text, CAP_EC_Z_TEXT_SIZE),
            "TipSlotZ": _centred_box(slot_z, CAP_EC_Z_TEXT_SIZE),
            "Notch View Note": _anchored_box(NOTCH_CAPTION_UPPER_LEFT, NOTCH_NOTE_EXTENT),
            "Isometric View Note": _anchored_box(iso_note, ISO_NOTE_EXTENT),
        },
        lines={
            "CapECz": [witness, cap_line, cap_lower_leg, cap_lower_witness],
            "TipSlotZ": slot_z_lines,
        },
        arcs={},
        arrows={
            "CapECz": [cap_arrow],
            "CapECx": [cx_tail],
            "TipSlotZ": slot_z_arrows,
        },
        leaders={},
    )


def on_drawn_cap_arc(
    tip: tuple[float, float],
    cap_xy: tuple[float, float],
    radius: float,
) -> bool:
    """Whether a leader tip lies on the drawn half of the cap circle, not
    out in the notch mouth."""
    dx, dy = tip[0] - cap_xy[0], tip[1] - cap_xy[1]
    if abs(math.hypot(dx, dy) - radius) > CAP_ARC_TIP_TOLERANCE:
        return False
    return dx * CAP_MOUTH_AXIS[0] + dy * CAP_MOUTH_AXIS[1] <= CAP_ARC_TIP_TOLERANCE


def in_acute_sector(
    point: tuple[float, float],
    vertex: tuple[float, float],
    first: tuple[float, float],
    second: tuple[float, float],
) -> bool:
    """Whether ``point`` lies strictly inside the sector from ``vertex``
    between the rays through ``first`` and ``second`` (under 180 deg)."""

    def cross(a: tuple[float, float], b: tuple[float, float]) -> float:
        return a[0] * b[1] - a[1] * b[0]

    ray = (first[0] - vertex[0], first[1] - vertex[1])
    other = (second[0] - vertex[0], second[1] - vertex[1])
    to_point = (point[0] - vertex[0], point[1] - vertex[1])
    turn = cross(ray, other)
    return cross(ray, to_point) * turn > 0.0 and cross(to_point, other) * turn > 0.0


def _grown(box: _drawing_leaders.Box, margin: float) -> _drawing_leaders.Box:
    return (box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin)


def _segment_gap(first: _drawing_leaders.Segment, second: _drawing_leaders.Segment) -> float:
    """Distance between two segments that do not cross: the nearest of each
    one's ends to the other."""
    return min(
        *(_drawing_leaders.distance_to_point(first, end) for end in second),
        *(_drawing_leaders.distance_to_point(second, end) for end in first),
    )


def _strokes(ink: SheetInk, owners: Collection[str]) -> list[tuple[str, _drawing_leaders.Segment]]:
    return [
        (f"{owner} {kind}", segment)
        for kind, strokes in (("lines", ink.lines), ("arcs", ink.arcs))
        for owner in sorted(owners)
        for segment in strokes.get(owner, ())
    ]


def dimension_crossings(ink: SheetInk) -> tuple[list[str], list[str]]:
    """(findings, reported): other annotations' lines across a moved value's
    dimension ink.

    Only annotations with an offset leader are checked.  A crossing within
    DIMENSION_CROSSING_TEXT_FRACTION of the value's text height of the value,
    or one not in EXPECTED_DIMENSION_CROSSINGS, is a finding; a named one
    farther out is reported.  The distance taken is the nearer of the two
    crossing segments' to the value's box -- never farther than the crossing
    point itself, so a pass is proven."""
    findings, reported = [], []
    for owner in sorted(name for name, leaders in ink.leaders.items() if leaders):
        box = ink.texts[owner]
        limit = DIMENSION_CROSSING_TEXT_FRACTION * (box[3] - box[1])
        others = {*ink.lines, *ink.arcs} - {owner}
        nearest: dict[tuple[str, str], float] = {}
        for mine, first in _strokes(ink, [owner]):
            for theirs, second in _strokes(ink, others):
                if not _drawing_leaders.segments_cross(first, second):
                    continue
                gap = min(
                    _drawing_leaders.distance_to_box(first, box),
                    _drawing_leaders.distance_to_box(second, box),
                )
                nearest[(mine, theirs)] = min(gap, nearest.get((mine, theirs), math.inf))
        for (mine, theirs), gap in sorted(nearest.items()):
            reason = EXPECTED_DIMENSION_CROSSINGS.get(frozenset((mine, theirs)))
            where = f"{mine} x {theirs}, at least {gap * 1000.0:.2f} mm from {owner!r}"
            if gap <= limit:
                findings.append(
                    f"dimension-crossing: {where}, within {limit * 1000.0:.2f} mm "
                    f"(half its text height)"
                )
            elif reason is None:
                findings.append(f"dimension-crossing: {where}, not an expected crossing")
            else:
                reported.append(f"{where}: {reason}")
    return findings, reported


def sheet_ink_collisions(ink: SheetInk) -> list[str]:
    """Text a line touches, arrows at text, leaders across or near ink,
    dimension ink crossed at a moved value.

    * text-on-line: any annotation's dimension, extension or arc line -- its
      own included -- within LINE_TEXT_CLEARANCE of a text block;
    * arrow-near-text: an arrowhead within ARROW_TEXT_CLEARANCE of another
      annotation's text (``_drawing_leaders.arrows_near_text``);
    * leader-on-ink: an offset leader crossing, or ending in a T on, any line
      or arc (``_drawing_leaders.leader_crossings``: a T is a crossing), or a
      foreign arrow, or running through foreign text.  One pair is declared
      touching: a leader and its own dimension arc, where SolidWorks roots it.
      Its own arrowheads stay out of the leader test -- their outside halves
      are the arc tails, which are in it;
    * leader-near-ink: a leader within LEADER_INK_CLEARANCE of any of those
      strokes it does not cross (its own arc excepted);
    * dimension-crossing: ``dimension_crossings``.
    """
    findings = []
    for name, box in sorted(ink.texts.items()):
        guard = _grown(box, LINE_TEXT_CLEARANCE)
        for kind, strokes in (("line", ink.lines), ("arc", ink.arcs)):
            for owner, segments in sorted(strokes.items()):
                if any(_drawing_leaders.distance_to_box(s, guard) == 0.0 for s in segments):
                    findings.append(f"text-on-line: {owner}'s {kind} runs through {name!r}")
    for owner, name, gap in _drawing_leaders.arrows_near_text(
        ink.arrows,
        ink.texts,
        clearance=ARROW_TEXT_CLEARANCE,
        half_width=DIMENSION_ARROW_HALF_WIDTH,
    ):
        findings.append(
            f"arrow-near-text: {owner}'s arrow stands {gap * 1000.0:.2f} mm from {name!r}"
        )
    for owner, leaders in sorted(ink.leaders.items()):
        if leaders:
            findings.extend(_leader_findings(ink, owner, leaders))
    findings.extend(dimension_crossings(ink)[0])
    return findings


def _leader_findings(
    ink: SheetInk, owner: str, leaders: list[_drawing_leaders.Segment]
) -> list[str]:
    leader = f"{owner} leader"
    groups = {leader: list(leaders)}
    for other in sorted({*ink.lines, *ink.arcs, *ink.arrows}):
        groups[f"{other} lines"] = list(ink.lines.get(other, ()))
        groups[f"{other} arcs"] = list(ink.arcs.get(other, ()))
        if other != owner:
            groups[f"{other} arrows"] = list(ink.arrows.get(other, ()))
    # The one declared touch: an offset leader roots on its own arc.
    own_arcs = f"{owner} arcs"
    findings = []
    crossed = set()
    for first, second in _drawing_leaders.leader_crossings(groups, {frozenset((leader, own_arcs))}):
        if leader in (first, second):
            other = second if first == leader else first
            crossed.add(other)
            findings.append(f"leader-on-ink: {owner}'s leader crosses {other}")
    for other, segments in groups.items():
        if other in (leader, own_arcs) or other in crossed or not segments:
            continue
        gap = min(_segment_gap(a, b) for a in leaders for b in segments)
        if gap < LEADER_INK_CLEARANCE:
            findings.append(
                f"leader-near-ink: {owner}'s leader passes {gap * 1000.0:.2f} mm from {other}"
            )
    for name, box in sorted(ink.texts.items()):
        if name != owner and any(_drawing_leaders.distance_to_box(s, box) == 0.0 for s in leaders):
            findings.append(f"leader-on-ink: {owner}'s leader runs through {name!r}")
    return findings


def assert_notch_plan_ink_clear() -> None:
    """Refuse the notch plan's layout before any COM work is spent."""
    findings = sheet_ink_collisions(notch_plan_ink())
    if findings:
        raise RuntimeError("notch plan ink collides: " + "; ".join(findings))


def _display_data(annotation: Any) -> Any:
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    return _early_bound(display.GetDisplayData(), "IDisplayData")


def _arcs(annotation: Any) -> list[tuple[_drawing_leaders.Segment, tuple[float, float]]]:
    """A dimension's arcs as (start->end chord, centre), sheet metres.

    ``GetArcAtIndex2`` -> [color, lineType, unused, unused, start[3], end[3],
    centre[3], normal[3], rotationDir]."""
    data = _display_data(annotation)
    arcs = []
    for index in range(int(data.GetArcCount())):
        values = [float(v) for v in (data.GetArcAtIndex2(index) or ())]
        if len(values) < 13:
            raise RuntimeError(f"display arc {index} is incomplete: {values}")
        arcs.append((((values[4], values[5]), (values[7], values[8])), (values[10], values[11])))
    return arcs


def _arc_chords(annotation: Any) -> list[_drawing_leaders.Segment]:
    return [chord for chord, _centre in _arcs(annotation)]


def _arrow_segments(annotation: Any) -> list[_drawing_leaders.Segment]:
    """Each arrowhead as a segment through its tip along its axis.

    ``GetArrowHeadAtIndex2`` -> [tip[3], dir[3], width, height, style,
    normal[3]], width measured along the direction.  Which way the head
    extends from its tip is not seat-proven here, so the segment spans the
    width both ways: stricter, never blind."""
    data = _display_data(annotation)
    arrows = []
    for index in range(int(data.GetArrowHeadCount())):
        values = [float(v) for v in (data.GetArrowHeadAtIndex2(index) or ())]
        if len(values) < 8:
            raise RuntimeError(f"arrowhead {index} is incomplete: {values}")
        (x, y), (dx, dy), width = values[0:2], values[3:5], values[6]
        length = math.hypot(dx, dy) or 1.0
        ux, uy = dx / length * width, dy / length * width
        arrows.append(((x - ux, y - uy), (x + ux, y + uy)))
    return arrows


def _notch_strokes(annotation: Any) -> list[_drawing_leaders.Segment]:
    """A dimension's display lines plus any API leader polyline."""
    return _drawing_leaders.dimension_segments(annotation) + _drawing_leaders.leader_segments(
        annotation
    )


def _pin_tip_slot_z_arrows_inside(adapter: Any, annotations: list[Any]) -> None:
    """The 27.70 prints inside its span; smart arrows could flip out and run
    ~6.3 mm tails past both witnesses, so pin them inside and read it back."""
    matches = [item for item in annotations if dimension_name(adapter, item) == "TipSlotZ"]
    if len(matches) != 1:
        raise RuntimeError(f"expected one TipSlotZ annotation, found {len(matches)}")
    annotation = _early_bound(matches[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    display.ArrowSide = 0  # swDimensionArrowsSide_e.swDimArrowsInside
    rebuild_drawing(adapter, label="tip slot z arrows inside")
    if int(display.ArrowSide) != 0:
        raise RuntimeError("TipSlotZ did not keep its arrows inside")
    position = tuple(float(v) for v in annotation.GetPosition())[:2]
    if math.dist(position, NOTCH_KEEP["TipSlotZ"]) > 0.0005:
        raise RuntimeError(f"TipSlotZ text at {position}, not {NOTCH_KEEP['TipSlotZ']}")
    shoulder = [
        segment
        for segment in _notch_strokes(annotation)
        # Its witnesses run 1.0 mm past the line; d382's shoulder ran 14 mm.
        if min(segment[0][0], segment[1][0]) < TIP_SLOT_Z_LINE_X - 0.002
    ]
    _telemetry.info(f"TipSlotZ inside its span: text={position} strokes_left_of_line={shoulder}")
    if shoulder:
        raise RuntimeError(f"TipSlotZ still draws ink left of its line: {shoulder}")


def _assert_notch_captions_clear(
    adapter: Any, annotations: list[Any], captions: dict[str, Any]
) -> None:
    """No notch-plan dimension line, arc or arrow on a caption.

    The captions are property-linked notes at fixed sheet points; fix4b's
    205.81 line ran through "ISOMETRIC VIEW SCALE 1:3" because no caption was
    in the audit's text set.  Their boxes are read off the seat
    (``INote.GetExtent``), after the rebuild that resolves their text."""
    rebuild_drawing(adapter, label="captions placed")
    texts = {}
    for name, note in captions.items():
        values = [float(v) for v in (_early_bound(note, "INote").GetExtent() or ())]
        if len(values) < 6:
            raise RuntimeError(f"{name} has no extent: {values}")
        texts[name] = (
            min(values[0], values[3]),
            min(values[1], values[4]),
            max(values[0], values[3]),
            max(values[1], values[4]),
        )
    by_name = {dimension_name(adapter, item): _early_bound(item, "IAnnotation") for item in annotations}
    ink = SheetInk(
        texts=texts,
        lines={name: _notch_strokes(item) for name, item in by_name.items()},
        arcs={name: _arc_chords(item) for name, item in by_name.items()},
        arrows={name: _arrow_segments(item) for name, item in by_name.items()},
        leaders={},
    )
    findings = sheet_ink_collisions(ink)
    _telemetry.info(f"notch captions: boxes={texts} findings={findings}")
    if findings:
        raise RuntimeError("notch plan ink collides with a caption: " + "; ".join(findings))


def _assert_mouth_angle_in_wedge(
    adapter: Any, view: Any, annotations: list[Any]
) -> None:
    """Prove the mouth angle's text sits in its acute 87 deg sector.

    An angular dimension draws the sector that holds its text, so a text
    point beside the wedge prints the 93 supplement or the vertically
    opposite sector's arc.  The sector is re-derived from the model through
    the placed view, not from the layout's own sheet figures.
    """
    matches = [
        item for item in annotations if dimension_name(adapter, item) == "NotchMouthAngle"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one NotchMouthAngle annotation, found {len(matches)}")
    annotation = _early_bound(matches[0], "IAnnotation")
    text = tuple(float(value) for value in annotation.GetPosition())[:2]
    vx, vz = _part.NOTCH_CUT_POINTS["mouth_s"]
    ux, uz = _part.NOTCH_CUT_U
    y = PLATE_THICKNESS / 1000.0

    def sheet(x_mm: float, z_mm: float, label: str) -> tuple[float, float]:
        return model_point_in_view(
            adapter, view, (x_mm / 1000.0, y, z_mm / 1000.0), label=label
        )[:2]

    vertex = sheet(vx, vz, "mouth angle vertex")
    rail = sheet(vx - 3.0 * ux, vz - 3.0 * uz, "mouth angle rail")
    edge = sheet(vx + 3.0 * _part._EDGE_SX, vz + 3.0 * _part._EDGE_SZ, "mouth angle edge")
    inside = in_acute_sector(text, vertex, rail, edge)
    _telemetry.info(
        f"NotchMouthAngle text={text} vertex={vertex} rail={rail} edge={edge} "
        f"inside_acute_sector={inside} predicted_vertex={MOUTH_ANGLE_VERTEX_XY}"
    )
    if not inside:
        raise RuntimeError(
            f"NotchMouthAngle text {text} is outside its acute sector at {vertex}; "
            "it would print the supplement or the opposite arc"
        )


def _hide_profile_cosmetic_threads(adapter: Any, view: Any) -> None:
    """Hide the redundant model cosmetic-thread callout in the profile view."""
    draw = adapter.currentModel
    manager = _early_bound(draw.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    if layer is None:
        if (
            int(
                manager.AddLayer(
                    _COSMETIC_THREAD_LAYER,
                    "cosmetic thread ink hidden in profile view",
                    0,
                    0,
                    0,
                )
            )
            != 1
        ):
            raise RuntimeError("failed to add hidden cosmetic-thread layer")
        layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError("cosmetic-thread layer did not remain hidden")

    hidden = 0
    hidden_callouts = 0
    for raw_annotation in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != 1:  # swCosmeticThread
            continue
        annotation.Layer = _COSMETIC_THREAD_LAYER
        if str(annotation.Layer or "") != _COSMETIC_THREAD_LAYER:
            raise RuntimeError("profile cosmetic thread refused the hidden layer")
        thread = _early_bound(annotation.GetSpecificAnnotation(), "ICThread")
        raw_callout = _read_member(thread, "ThreadCallout")
        if raw_callout is not None:
            callout = _early_bound(raw_callout, "INote")
            callout_annotation = _early_bound(
                _read_member(callout, "GetAnnotation"), "IAnnotation"
            )
            callout_annotation.Layer = _COSMETIC_THREAD_LAYER
            if str(callout_annotation.Layer or "") != _COSMETIC_THREAD_LAYER:
                raise RuntimeError("profile thread callout refused the hidden layer")
            hidden_callouts += 1
        hidden += 1
    if not hidden:
        raise RuntimeError("profile view has no cosmetic thread to hide")
    if not hidden_callouts:
        raise RuntimeError("profile cosmetic threads have no callout note to hide")
    rebuild_drawing(adapter, label="hide profile cosmetic threads")


def _position_section_label(adapter: Any, section: Any) -> None:
    """Keep the native section caption below, rather than inside, the section."""
    notes = tuple(_read_member(section, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native section label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    target = (*_shifted(0.335, 0.085), 0.0)
    if not annotation.SetPosition2(*target):
        raise RuntimeError("failed to position native section label")
    adapter.currentModel.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if max(abs(actual[i] - target[i]) for i in range(3)) > 1e-8:
        raise RuntimeError(
            f"native section label position did not persist: {actual}; "
            f"requested={target}"
        )


def _note_annotation_name(note: Any) -> str:
    annotation = _early_bound(_early_bound(note, "INote").GetAnnotation(), "IAnnotation")
    return str(annotation.GetName() or "")


def _position_view_label(
    adapter: Any,
    view: Any,
    lower_left: tuple[float, float],
    *,
    label: str,
    added_notes: Sequence[Any] = (),
) -> None:
    """Move a view's native label so its box's lower-left lands at ``lower_left``.

    The label's anchor is not its box corner, so the move is measured: read
    ``INote.GetExtent``, shift the anchor by the corner's error, read back.
    The sheet scale is pinned first; finalization re-applying it must not
    move a dynamic label after this readback.

    ``IView::GetNotes`` returns every note in the view, so notes this script
    added there (detail B's cutter notes: 498160d1 found 3) are excluded by
    their own annotation names, not by text; exactly one native label must
    remain.
    """
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError(f"cannot pin sheet scale before {label} placement")
    added = {_note_annotation_name(item) for item in added_notes}
    if "" in added or len(added) != len(added_notes):
        raise RuntimeError(f"{label}: added notes lack distinct annotation names")
    notes = tuple(_read_member(view, "GetNotes") or ())
    native = [item for item in notes if _note_annotation_name(item) not in added]
    if len(native) != 1 or len(notes) - len(native) != len(added):
        raise RuntimeError(
            f"expected one native {label} beside {len(added)} added notes, "
            f"found {len(notes)} notes ({len(native)} not added here)"
        )
    note = _early_bound(native[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    for _attempt in range(2):
        extent = tuple(float(v) for v in note.GetExtent())
        error = (lower_left[0] - extent[0], lower_left[1] - extent[1])
        if max(abs(error[0]), abs(error[1])) < 0.0002:
            break
        anchor = tuple(float(v) for v in _read_member(annotation, "GetPosition"))
        moved = (anchor[0] + error[0], anchor[1] + error[1], 0.0)
        if not annotation.SetPosition2(*moved):
            raise RuntimeError(f"failed to position native {label}")
        adapter.currentModel.EditRebuild3()
    extent = tuple(float(v) for v in note.GetExtent())
    print(f"{label}: requested lower-left={lower_left} extent={extent}")
    if max(abs(lower_left[0] - extent[0]), abs(lower_left[1] - extent[1])) > 0.0005:
        raise RuntimeError(
            f"native {label} landed at {extent[:2]}, requested {lower_left}"
        )


def _create_detail_view(
    adapter: Any,
    parent_view: Any,
    *,
    model_center_mm: tuple[float, float, float],
    radius_mm: float,
    view_xy: tuple[float, float],
    detail_label: str,
    scale: tuple[int, int],
    label: str,
) -> Any:
    """Create a circular detail view around one model point of ``parent_view``.

    The circle is sketched in the parent view's own sketch space: the model
    point is projected to the sheet, then through the sketch transform, the same
    path ``create_section_view`` uses for its cutting line.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    if not ddoc.ActivateView(view_name(adapter, parent_view)):
        raise RuntimeError(f"failed to activate detail parent view ({label})")
    draw.ClearSelection2(True)
    center_m = tuple(value / 1000.0 for value in model_center_mm)
    rim_m = (center_m[0] + radius_mm / 1000.0, center_m[1], center_m[2])
    sheet = [
        model_point_in_view(adapter, parent_view, point, label=f"{label} {name}")
        for name, point in (("centre", center_m), ("rim", rim_m))
    ]
    sketch = _early_bound(_early_bound(parent_view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in sheet:
        point = _early_bound(
            math_utility.CreatePoint(double_array([float(x), float(y), 0.0])),
            "IMathPoint",
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    previous_add_to_db = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        circle = sketch_manager.CreateCircle(*points[0], *points[1])
    finally:
        sketch_manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError(f"failed to sketch the detail circle ({label})")
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    selection_data = selection_manager.CreateSelectData()
    selection_data.View = parent_view
    selectable = _sw_type_info.early_bound_or_flag(circle, "ISketchSegment", "Select4")
    if not selectable.Select4(False, selection_data):
        raise RuntimeError(f"failed to select the detail circle ({label})")
    detail = ddoc.CreateDetailViewAt4(
        float(view_xy[0]),
        float(view_xy[1]),
        0.0,
        0,  # swDetViewSTANDARD
        float(scale[0]),
        float(scale[1]),
        detail_label,
        1,  # swDetCircleCIRCLE
        True,  # FullOutline
        False,  # JaggedOutline
        False,  # NoOutline
        5,
    )
    draw.ClearSelection2(True)
    if detail is None:
        raise RuntimeError(f"CreateDetailViewAt4 returned no view ({label})")
    detail = _sw_type_info.early_bound_or_flag(
        detail, "IView", "SetViewPosition", "Position"
    )
    rebuild_drawing(adapter, label=f"create detail view {detail_label}")
    # A detail view's Position is its model-origin anchor, not the circle
    # centre (run 2b643c17 placed the circle 99 mm below the request).  Move
    # the anchor until the circle's model centre lands on ``view_xy``.
    for attempt in range(2):
        landed = model_point_in_view(
            adapter, detail, center_m, label=f"{label} centre, pass {attempt}"
        )
        anchor = tuple(float(v) for v in detail.Position)
        if max(abs(landed[0] - view_xy[0]), abs(landed[1] - view_xy[1])) < 0.0002:
            break
        moved = (
            anchor[0] + view_xy[0] - landed[0],
            anchor[1] + view_xy[1] - landed[1],
        )
        if not detail.SetViewPosition(double_array(list(moved)), False):
            raise RuntimeError(f"failed to position the detail view ({label})")
        rebuild_drawing(adapter, label=f"place detail view {detail_label}")
    landed = model_point_in_view(adapter, detail, center_m, label=f"{label} centre")
    print(
        f"detail {detail_label}: parent_sheet_centre={sheet[0]} "
        f"sketch_centre={points[0]} requested={view_xy} landed={landed} "
        f"outline={tuple(float(v) for v in detail.GetOutline())}"
    )
    if max(abs(landed[0] - view_xy[0]), abs(landed[1] - view_xy[1])) > 0.0005:
        raise RuntimeError(
            f"detail {detail_label} centre landed at {landed}, requested {view_xy}"
        )
    return detail


def _look_slot_section_south(
    adapter: Any, parent: Any, section: Any, cut: Any
) -> None:
    """Point section C-C's arrows sheet-up (looking south) and prove the strip.

    The view direction is read from the section's own projection, not from
    arrow-array layouts: with screen-right r and screen-up u, the sight line
    is u x r, so it runs along -z (south) exactly when model +x's sheet-x sign
    times model +y's sheet-y sign is positive.  The strip must be the full
    width of the 6.35 plate at the slot station, at 1:1 -- the geometry section C-C
    had in detail B.
    """
    z = TIP_SCREW_LOCAL_Z / 1000.0

    def x_direction() -> float:
        base = model_point_in_view(adapter, section, (0.0, 0.003, z), label="C-C origin")
        east = model_point_in_view(adapter, section, (0.001, 0.003, z), label="C-C +x")
        up = model_point_in_view(adapter, section, (0.0, 0.004, z), label="C-C +y")
        return (east[0] - base[0]) * (up[1] - base[1])

    if x_direction() < 0.0:
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="section C-C looks south")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("section C-C cut direction did not persist")
    direction = x_direction()
    if not direction > 0.0:
        raise RuntimeError(f"section C-C still looks north (x/y sign product {direction})")
    east = plate_edge_mm(TIP_SCREW_LOCAL_Z, -1) / 1000.0
    west = plate_edge_mm(TIP_SCREW_LOCAL_Z, +1) / 1000.0
    low = model_point_in_view(
        adapter, section, (east, 0.0, z), label="C-C strip east underside"
    )
    high = model_point_in_view(
        adapter, section, (west, PLATE_THICKNESS / 1000.0, z), label="C-C strip west top"
    )
    span = (high[0] - low[0], high[1] - low[1])
    print(
        f"section C-C: reversed={bool(cut.GetReversedCutDirection())} "
        f"x_dir={direction} strip_span_m={span} "
        f"arrows={tuple(float(v) for v in (cut.GetArrowInfo() or ()))} "
        f"texts={tuple(float(v) for v in (cut.GetTextInfo() or ()))} "
        f"parent_line_info="
        f"{tuple(float(v) for v in (_early_bound(parent, 'IView').GetSectionLineInfo2() or ()))}"
    )
    expected = (west - east, PLATE_THICKNESS / 1000.0)
    if any(abs(abs(span[i]) - expected[i]) > 1e-6 for i in (0, 1)):
        raise RuntimeError(
            f"section C-C strip is {span}, expected the 1:1 {expected} full width"
        )


def _ink_segments(annotation: Any) -> list[tuple[float, float, float, float]]:
    """An annotation's straight ink runs, sheet metres (x0, y0, x1, y1).

    ``IDisplayData::GetLineAtIndex3`` ends with startPt[3], endPt[3]; the
    start index is read from the array length, as the layout audit does.
    """
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    runs = []
    for index in range(int(data.GetLineCount())):
        values = [float(v) for v in (data.GetLineAtIndex3(index) or ())]
        if len(values) < 10:
            continue
        start = len(values) - 6
        runs.append(
            (values[start], values[start + 1], values[start + 3], values[start + 4])
        )
    return runs


def _set_arrows_inside(
    adapter: Any, annotations: list[Any], names: tuple[str, ...]
) -> None:
    """Pin the named dimensions' arrowheads between their extension lines."""
    found = set()
    for item in annotations:
        name = dimension_name(adapter, item)
        if name not in names:
            continue
        display = _early_bound(item.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArrowSide = 0  # swDimensionArrowsSide_e.swDimArrowsInside
        if int(display.ArrowSide) != 0:
            raise RuntimeError(f"{name} did not keep its arrows inside")
        found.add(name)
    if found != set(names):
        raise RuntimeError(f"arrows-inside dimensions missing: {set(names) - found}")
    rebuild_drawing(adapter, label="detail B arrows inside")


def _keep_depth_on_its_attached_end(adapter: Any, annotations: list[Any]) -> None:
    """Park the C-C depth text beside the strip end its extension lines leave.

    Looking south mirrors the strip; SolidWorks attaches the imported depth to
    whichever end it picks.  Text on the far side would stretch both extension
    lines across the strip, so if the ink reaches past the strip centre the
    text moves to the mirrored keep.
    """
    matches = [
        item for item in annotations if dimension_name(adapter, item) == "TipCboreDepth"
    ]
    if len(matches) != 1:
        raise RuntimeError("expected one native counterbore depth in section C-C")
    annotation = _early_bound(matches[0], "IAnnotation")
    runs = _ink_segments(annotation)
    reach = max((max(run[0], run[2]) for run in runs), default=float("-inf"))
    print(f"TipCboreDepth ink: runs={runs} max_x={reach}")
    if reach <= SLOT_SECTION_CENTER[0]:
        return
    target = (*SLOT_SECTION_DEPTH_RIGHT, 0.0)
    if not annotation.SetPosition2(*target):
        raise RuntimeError("failed to move the C-C depth text to the strip's right end")
    rebuild_drawing(adapter, label="section C-C depth on its attached end")
    runs = _ink_segments(annotation)
    low = min((min(run[0], run[2]) for run in runs), default=float("inf"))
    print(f"TipCboreDepth ink after move: runs={runs} min_x={low}")
    if low < SLOT_SECTION_CENTER[0]:
        raise RuntimeError("C-C depth ink still crosses the strip after the move")


def _plan_basis_to_model(
    adapter: Any,
    view: Any,
    sheet_xy: tuple[float, float],
    origin: tuple[float, float, float],
    *,
    label: str,
) -> tuple[float, float, float]:
    """Invert a plan view's measured X/Z basis at ``origin``'s model Y.

    The R8 proof's inversion, shared by the cutter-note leader proof.
    """
    center = model_point_in_view(adapter, view, origin, label=f"{label} origin")
    px = model_point_in_view(
        adapter, view, (origin[0] + 0.001, origin[1], origin[2]), label=f"{label} X basis"
    )
    pz = model_point_in_view(
        adapter, view, (origin[0], origin[1], origin[2] + 0.001), label=f"{label} Z basis"
    )
    xx, xy = px[0] - center[0], px[1] - center[1]
    zx, zy = pz[0] - center[0], pz[1] - center[1]
    det = xx * zy - zx * xy
    if abs(det) < 1e-12:
        raise RuntimeError(f"{label} plan projection is singular")
    dx, dy = sheet_xy[0] - center[0], sheet_xy[1] - center[1]
    return (
        origin[0] + 0.001 * (dx * zy - zx * dy) / det,
        origin[1],
        origin[2] + 0.001 * (xx * dy - dx * xy) / det,
    )


def _add_arc_note(adapter: Any, view: Any, note: ArcNote) -> Any:
    """Place one leadered note, then prove its tip is on its arc.

    Same proof as the R8 radius: the leader tip read back off the sheet is
    inverted through the view's measured plan basis at each candidate edge's
    model Y, and the trimmed physical edge (``IEdge::GetClosestPointOn``) must
    lie within ``LEADER_TIP_BOUND_M`` of it.  Candidates are the named cut's
    own edges on the note's circle (radius and centre to 1e-6 m), limited
    to ``note.model_y_mm`` when the note names one face.
    """
    tip_xy = model_point_in_view(
        adapter, view, arc_note_model_tip(note), label=f"{note.key} note tip"
    )
    drift = math.dist(tip_xy[:2], arc_note_tip(note))
    # A detail's centre lands within 0.5 mm of its layout point (asserted by
    # _create_detail_view); the layout was checked against that point.
    if drift > 0.0006:
        raise RuntimeError(
            f"{note.key} note tip projects to {tip_xy[:2]}, layout expects "
            f"{arc_note_tip(note)} ({drift * 1000:.3f} mm off)"
        )
    created = add_leader_note(
        adapter,
        note.text,
        text_xy=note.text_xy,
        attach_xy=(tip_xy[0], tip_xy[1]),
        label=f"{note.key} note",
        view=view,
    )
    annotation = _early_bound(_early_bound(created, "INote").GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"{note.key} note has no text format")
    text_format.CharHeight = CUTTER_NOTE_CHAR_HEIGHT
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError(f"failed to size the {note.key} note")
    rebuild_drawing(adapter, label=f"{note.key} note text height")

    points = [float(v) for v in (annotation.GetLeaderPointsAtIndex(0) or ())]
    if len(points) < 6:
        raise RuntimeError(f"{note.key} note leader is unreadable")
    tip = (points[-3], points[-2])
    document = _early_bound(_early_bound(view, "IView").ReferencedDocument, "IModelDoc2")
    feature = _early_bound(
        _early_bound(document, "IPartDoc").FeatureByName(note.feature), "IFeature"
    )
    radius_m = note.radius_mm / 1000.0
    center_x = note.arc_center_mm[0] / 1000.0
    center_z = note.arc_center_mm[1] / 1000.0
    candidates: list[tuple[Any, tuple[float, ...]]] = []
    for raw_face in feature.GetFaces() or ():
        for raw_edge in _early_bound(raw_face, "IFace2").GetEdges() or ():
            edge = _early_bound(raw_edge, "IEdge")
            if any(int(adapter.swApp.IsSame(edge, item[0])) == 1 for item in candidates):
                continue
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            circle = tuple(float(value) for value in curve.CircleParams)
            if (
                abs(circle[6] - radius_m) > 1e-6
                or abs(circle[0] - center_x) > 1e-6
                or abs(circle[2] - center_z) > 1e-6
            ):
                continue
            if (
                note.model_y_mm is not None
                and abs(circle[1] - note.model_y_mm / 1000.0) > 1e-6
            ):
                continue
            candidates.append((edge, circle))
    if not candidates:
        raise RuntimeError(f"{note.feature} has no matching arc for the {note.key} note")
    distances = []
    for edge, circle in candidates:
        model_tip = _plan_basis_to_model(
            adapter, view, tip, circle[:3], label=f"{note.key} note arc"
        )
        closest = tuple(float(value) for value in edge.GetClosestPointOn(*model_tip))
        distance = math.dist(model_tip, closest[:3])
        distances.append(distance)
        print(
            f"{note.key} note: leader_sheet_m={points} arc_center_m={circle[:3]} "
            f"radius_m={circle[6]} tip_model_m={model_tip} "
            f"closest_model_m={closest[:3]} distance_m={distance}"
        )
    if not min(distances) <= LEADER_TIP_BOUND_M:
        raise RuntimeError(
            f"{note.key} note leader misses its {note.feature} arc "
            f"by {min(distances) * 1000:.4f} mm"
        )
    _telemetry.info(
        f"{note.key} note leader lands on {note.feature}'s arc "
        f"({len(candidates)} candidate edge(s), {min(distances) * 1e6:.2f} um)"
    )
    return created


# The Hole Wizard callout's countersink-DIAMETER variables, per side, exactly
# as the S1 leaf 917-s1-9094 read them on seat (swmaker000005): near-side
# "hw-nscsdia", far-side "hw-fscsdia".  Named, never matched by pattern: a
# guessed pattern missed both and reported a proven MAX as absent.
_CSK_DIA_VARIABLE_BY_SIDE = {"near": "hw-nscsdia", "far": "hw-fscsdia"}


def _require_countersink_max(display: Any, *, spec: HoleSpec, label: str) -> None:
    """Prove the native tap callout carries the part's MAX-banded countersink.

    The break is model-owned (cone_swing_platform_spec.POST_MOUNT_TAP_CSK):
    the part bands each countersink diameter swTolMAX and this sheet authors
    nothing.  The callout variable's own ToleranceType is what prints, so read
    back the diameter variable of every side ``spec`` countersinks and fail
    loud -- distinctly -- when none is there, when a side's is missing, or
    when a MAX-limited one does not print MAX.
    """
    from win32com.client.dynamic import Dispatch as dynamic_dispatch  # noqa: PLC0415

    seen: dict[str, int] = {}
    for raw in display.GetHoleCalloutVariables() or ():
        variable = dynamic_dispatch(raw._oleobj_)
        seen[str(variable.VariableName)] = int(variable.ToleranceType)
    wanted = {
        _CSK_DIA_VARIABLE_BY_SIDE[side]: csk
        for side, csk in (("near", spec.near_countersink), ("far", spec.far_countersink))
        if csk is not None
    }
    present = sorted(name for name in wanted if name in seen)
    if not present:
        raise RuntimeError(
            f"{label}: no countersink-diameter callout variables found; saw "
            f"{seen!r} (wanted {sorted(wanted)!r})"
        )
    missing = sorted(name for name in wanted if name not in seen)
    if missing:
        raise RuntimeError(
            f"{label}: countersink-diameter callout variable(s) missing "
            f"{missing!r}; saw {seen!r}"
        )
    not_max = {
        name: seen[name]
        for name, csk in wanted.items()
        if csk.max_limit and seen[name] != 6  # swTolType_e.swTolMAX
    }
    if not_max:
        raise RuntimeError(
            f"{label}: callout countersink diameter(s) {not_max!r} do not print MAX "
            f"(all variables and tolerance types: {seen!r})"
        )
    _telemetry.info(f"{label}: callout countersink diameter(s) {present} print MAX")


def _visible_plan_controls(adapter: Any, view: Any) -> tuple[Any, Any, Any]:
    """Return the pivot, post-mount and north post-dowel rims from the plan.

    The north-end and long-straight-side edges were dropped with the GD&T that
    referenced them (see ``build``) -- nothing else on this sheet attaches to
    them.  The dowel rim is the one nearest the pivot (the north dowel), so
    the callout's leader is the shorter of the two.
    """
    expected_radius_m = PIVOT_HOLE_DIA / 2000.0
    expected_mount_radius_m = blind_cut_dia_mm(POST_MOUNT_SPEC) / 2000.0
    expected_dowel_radius_m = PLATE_DOWEL_REAM_DIA / 2000.0
    pivot_edges: list[Any] = []
    mount_edges: list[Any] = []
    dowel_edges: list[tuple[float, Any]] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(c, 1), default=()
            )
            or ()
        )
        for raw_edge in edges:
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            values = tuple(float(value) for value in curve.CircleParams)
            if abs(values[6] - expected_radius_m) <= 1e-6:
                pivot_edges.append(edge)
            if abs(values[6] - expected_mount_radius_m) <= 1e-6:
                mount_edges.append(edge)
            if abs(values[6] - expected_dowel_radius_m) <= 1e-6:
                dowel_edges.append((math.hypot(values[0], values[2]), edge))
    if not pivot_edges or len(mount_edges) < 2 or len(dowel_edges) < 2:
        raise RuntimeError(
            "cone-platform plan view is missing pivot/mount/dowel controls: "
            f"{len(pivot_edges)} pivot, {len(mount_edges)} mount, {len(dowel_edges)} dowel"
        )
    return pivot_edges[0], mount_edges[0], min(dowel_edges, key=lambda item: item[0])[1]


def _horizontal_section_edge(
    view: Any, y_mm: float, *, label: str, prefer_right: bool = False
) -> Any:
    """Return a horizontal section edge on one broad-face station."""
    candidates: list[tuple[float, float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label=f"{label} section edges"):
        edge = _early_bound(raw_edge, "IEdge")
        start = edge.GetStartVertex()
        end = edge.GetEndVertex()
        if start is None or end is None:
            continue
        p0 = tuple(float(value) * 1000.0 for value in _early_bound(start, "IVertex").GetPoint())
        p1 = tuple(float(value) * 1000.0 for value in _early_bound(end, "IVertex").GetPoint())
        if abs(p0[1] - y_mm) <= 0.01 and abs(p1[1] - y_mm) <= 0.01:
            candidates.append((abs(p1[0] - p0[0]), 0.5 * (p0[0] + p1[0]), edge))
    if not candidates:
        raise RuntimeError(f"pivot section has no {label} edge at y={y_mm:.3f} mm")
    key_index = 1 if prefer_right else 0
    return max(candidates, key=lambda item: item[key_index])[2]


def _add_section_hole_axis(adapter: Any, section: Any) -> None:
    """Draw the pivot-hole axis between the two cut slices of section A-A.

    The cut-face-only section shows the hole as a bare gap; without its axis a
    reader takes the right slice for an unrelated fragment.
    """
    radius_mm = PIVOT_HOLE_DIA / 2.0
    walls: dict[int, Any] = {}
    for raw_edge in visible_view_entities(section, 1, label="pivot hole wall edges"):
        edge = _early_bound(raw_edge, "IEdge")
        start, end = edge.GetStartVertex(), edge.GetEndVertex()
        if start is None or end is None:
            continue
        p0 = tuple(float(v) * 1000.0 for v in _early_bound(start, "IVertex").GetPoint())
        p1 = tuple(float(v) * 1000.0 for v in _early_bound(end, "IVertex").GetPoint())
        if abs(p0[1] - p1[1]) < 1.0:
            continue
        for side in (-1, 1):
            if all(abs(p[0] - side * radius_mm) <= 0.01 for p in (p0, p1)):
                walls[side] = edge
                print(f"pivot hole wall {side:+d}: {p0} -> {p1}")
    if set(walls) != {-1, 1}:
        raise RuntimeError(f"section A-A shows {len(walls)} pivot hole walls, expected 2")
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, section)):
        raise RuntimeError("failed to activate section A-A for the hole axis")
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for index, side in enumerate((-1, 1)):
        data = selection_manager.CreateSelectData()
        data.View = section
        if not _early_bound(walls[side], "IEntity").Select4(index > 0, data):
            raise RuntimeError(f"failed to select pivot hole wall {side:+d}")
    if int(selection_manager.GetSelectedObjectCount2(-1)) != 2:
        raise RuntimeError("pivot hole axis needs exactly the two wall edges selected")
    centerline = ddoc.InsertCenterLine2()
    draw.ClearSelection2(True)
    if centerline is None:
        raise RuntimeError("failed to insert the pivot hole axis in section A-A")
    rebuild_drawing(adapter, label="section A-A pivot hole axis")
    lines = tuple(_read_member(section, "GetCenterLines") or ())
    if not lines:
        raise RuntimeError("section A-A lost its pivot hole axis")
    print(f"section A-A centerlines: {len(lines)}")


def _section_edge_midpoint(
    adapter: Any, view: Any, edge: Any, *, label: str
) -> tuple[float, float]:
    """Return the sheet point at the middle of one broad-face section edge."""
    points = [
        tuple(float(value) for value in _early_bound(vertex, "IVertex").GetPoint())
        for vertex in (edge.GetStartVertex(), edge.GetEndVertex())
    ]
    middle = tuple(0.5 * (points[0][i] + points[1][i]) for i in range(3))
    if abs(middle[0]) * 1000.0 <= PIVOT_HOLE_DIA / 2.0 + 0.5:
        raise RuntimeError(f"{label} edge midpoint falls in the pivot hole: {middle}")
    sheet = model_point_in_view(adapter, view, middle, label=f"{label} edge midpoint")
    print(
        f"{label} finish attach: edge_model_m={points} middle_model_m={middle} "
        f"sheet_m=({sheet[0]:.5f},{sheet[1]:.5f})"
    )
    return (sheet[0], sheet[1])


def expected_corner_arcs(feature_name: str) -> int:
    """Visible plan arcs a corner fillet leaves: 2 where the W18 relief crosses it.

    Derived from the same overlap the part build credits in its fillet volume
    gate (``_north_fillet_relief_overlap``), so the drawing and the model agree
    on where the open relief splits a fillet's top edge.
    """
    label = feature_name.removeprefix("Corner")
    radius = {corner[0]: corner[3] for corner in _part._CORNERS}[label]
    return 2 if _part._north_fillet_relief_overlap(label, radius) > 0.0 else 1


def check_corner_arc_plan(
    name: str, plan: list[tuple[float, float, float]], expected: int
) -> None:
    """Exactly the expected owned arcs, all on one plan circle (x, z, radius)."""
    if len(plan) != expected:
        raise RuntimeError(
            f"expected {expected} owned visible {name} arc(s) at corner station, "
            f"found {len(plan)}"
        )
    if any(math.dist(item, plan[0]) > 1e-8 for item in plan[1:]):
        raise RuntimeError(f"{name} owned arcs do not share one plan circle: {plan!r}")


def _assert_corner_radius_attachment(
    adapter: Any, view: Any, annotations: list[Any], *,
    name: str, feature_name: str, radius_m: float, station_xy: tuple[float, float],
) -> None:
    """Prove a native radius dimension's arrow lies on its owned visible arc."""
    matches = [item for item in annotations if dimension_name(adapter, item) == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one native {name} radius annotation")
    annotation = _early_bound(matches[0], "IAnnotation")
    # Imported fillet dimensions can return unsupported/null annotation entities.
    # Record that API honestly; model-dimension ownership below is authoritative.
    entities = annotation.GetAttachedEntities3()
    entity_types = annotation.GetAttachedEntityTypes()
    print(
        f"{name} annotation entities_none={entities is None} "
        f"entity_nulls={tuple(item is None for item in (entities or ()))} types={entity_types!r}"
    )
    dangling = annotation.IsDangling()
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    owner = _early_bound(dimension.GetFeatureOwner(), "IFeature")
    print(f"{name} native model dimension owner={owner.Name!r} dangling={dangling!r}")
    if dangling is not False or str(owner.Name) != feature_name:
        raise RuntimeError(f"{name} is dangling or is not owned by native {feature_name}")
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    arrows = [
        tuple(float(value) for value in data.GetArrowHeadAtIndex2(index))
        for index in range(int(data.GetArrowHeadCount()))
    ]
    if len(arrows) != 1 or len(arrows[0]) < 3:
        raise RuntimeError(f"expected one {name} arrow tip, found {arrows}")
    arrow = arrows[0]
    visible = visible_view_entities(view, 1, label=f"{name} visible corner edges")
    candidates = []
    for raw_face in owner.GetFaces() or ():
        face = _early_bound(raw_face, "IFace2")
        if str(_early_bound(face.GetFeature(), "IFeature").Name) != feature_name:
            continue
        for raw_edge in face.GetEdges() or ():
            edge = _early_bound(raw_edge, "IEdge")
            if not any(int(adapter.swApp.IsSame(edge, item)) == 1 for item in visible):
                continue
            if any(int(adapter.swApp.IsSame(edge, item[0])) == 1 for item in candidates):
                continue
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            circle = tuple(float(value) for value in curve.CircleParams)
            if abs(circle[6] - radius_m) > 1e-8:
                continue
            center = model_point_in_view(adapter, view, circle[:3], label=f"{name} owned circle")
            if all(abs(center[i] - station_xy[i]) <= 0.001 for i in (0, 1)):
                candidates.append((edge, circle, center))
    # W18 (5db29554, run d9711228): the open pivot relief crosses the NW
    # fillet, so its plan arc is two physical edges on one circle -- one on
    # the 6.35 top, one on the 6.10 relief floor.  Every owned visible arc
    # must share the plan centre and radius; the arrow must land on one.
    plan = [(circle[0], circle[2], circle[6]) for _edge, circle, _center in candidates]
    check_corner_arc_plan(name, plan, expected_corner_arcs(feature_name))
    distances = []
    for edge, circle, center in candidates:
        # Invert the measured plan-view X/Z basis at this owned edge's model Y.
        px = model_point_in_view(adapter, view, (circle[0] + 0.001, circle[1], circle[2]), label=f"{name} X basis")
        pz = model_point_in_view(adapter, view, (circle[0], circle[1], circle[2] + 0.001), label=f"{name} Z basis")
        xx, xy = px[0] - center[0], px[1] - center[1]
        zx, zy = pz[0] - center[0], pz[1] - center[1]
        det = xx * zy - zx * xy
        if abs(det) < 1e-12:
            raise RuntimeError(f"{name} plan projection is singular")
        dx, dy = arrow[0] - center[0], arrow[1] - center[1]
        model_tip = (
            circle[0] + 0.001 * (dx * zy - zx * dy) / det,
            circle[1],
            circle[2] + 0.001 * (xx * dy - dx * xy) / det,
        )
        # IEdge, not ICurve: the closest point is on the trimmed physical edge.
        closest = tuple(float(value) for value in edge.GetClosestPointOn(*model_tip))
        trim = _early_bound(edge.GetCurveParams3(), "ICurveParamData")
        distance = math.dist(model_tip, closest[:3])
        distances.append(distance)
        print(
            f"{name} owned visible trimmed edge: arrow_sheet_m={arrow[:3]} radius_m={circle[6]} "
            f"center_model_m={circle[:3]} trim_u=({trim.UMinValue},{trim.UMaxValue}) "
            f"closest_u={closest[3]} arrow_model_m={model_tip} "
            f"closest_model_m={closest[:3]} distance_m={distance}"
        )
    if not min(distances) <= 0.00002:  # 0.01 mm on this 1:2 sheet; unchanged physical-edge bound.
        raise RuntimeError(f"{name} arrow does not land on its owned physical corner arc")
    # Which face's arc the arrow names: a reader should see the radius on the
    # 6.35 top outline, not the 6.10 relief floor (Main, 2026-09-24).
    hit = candidates[distances.index(min(distances))][1]
    _telemetry.info(
        f"{name} arrow lands on the arc at model y={hit[1] * 1000.0:.3f} mm "
        f"({len(candidates)} owned arc(s); plate top {PLATE_THICKNESS:.2f})"
    )


def _assert_each_kept_dimension_once(adapter: Any, views: dict[str, Any]) -> None:
    """Walk every view's annotations: each kept dimension once, on its owner.

    ``curate_view_dimensions`` deletes a view's unrequested imports and drops
    them from the list it returns, so a deletion that did not hold would
    otherwise print a duplicate unseen."""
    seen: dict[str, list[str]] = {}
    for label, view in views.items():
        names = []
        for raw in _early_bound(view, "IView").GetAnnotations() or ():
            name = dimension_name(adapter, _early_bound(raw, "IAnnotation"))
            if name:
                names.append(name)
        seen[label] = sorted(names)
        print(f"{label} dimensions: {seen[label]}")
    errors = dimension_placement_errors(seen)
    if errors:
        raise RuntimeError("kept dimensions misplaced on the sheet: " + "; ".join(errors))


async def build(adapter: Any) -> dict[str, str]:
    assert_notch_plan_ink_clear()
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-swing-platform source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Profile View Note",
            "Feature View Note",
            "Notch View Note",
            "Isometric View Note",
            "Pivot Relief Fit",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Profile View Note",
            "Feature View Note",
            "Notch View Note",
            "Isometric View Note",
            "Pivot Relief Fit",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Swing Platform Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone swing platform; wedge plate; pivot; lock notch",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    profile = place_view(
        adapter, str(SOURCE), "*Top", *PROFILE_CENTER, scale=(1, 2)
    )
    feature = place_view(
        adapter, str(SOURCE), "*Top", *FEATURE_CENTER, scale=(1, 2)
    )
    notch = place_view(adapter, str(SOURCE), "*Top", *NOTCH_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 3))
    for view in (profile, feature, notch, iso):
        set_hidden_lines_removed(adapter, view)

    pivot_xy = model_point_in_view(
        adapter, feature, (0.0, 0.0, 0.0), label="pivot section station"
    )
    feature_outline = tuple(float(value) for value in feature.GetOutline())
    section = create_section_view(
        adapter,
        feature,
        line_start=(feature_outline[0] - 0.002, pivot_xy[1]),
        line_end=(feature_outline[2] + 0.002, pivot_xy[1]),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(2, 1),
        label="pivot bearing section",
    )
    cut = _early_bound(section.GetSection(), "IDrSection")
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="pivot section cut faces only")
    if cut.GetDisplayOnlySurfaceCut() is not True:
        raise RuntimeError("pivot section retained geometry beyond the cutting plane")
    _position_section_label(adapter, section)
    set_hidden_lines_removed(adapter, section)
    _add_section_hole_axis(adapter, section)

    detail = _create_detail_view(
        adapter,
        feature,
        model_center_mm=(0.0, PLATE_THICKNESS, DETAIL_MODEL_Z),
        radius_mm=DETAIL_RADIUS_MM,
        view_xy=DETAIL_CENTER,
        detail_label="B",
        scale=DETAIL_SCALE,
        label="tip screw slot detail",
    )
    # Hidden edges dashed, so the underside counterbored slot reads.
    set_hidden_lines_visible(adapter, detail)
    cap_detail = _create_detail_view(
        adapter,
        feature,
        model_center_mm=(
            _part.NOTCH_CAP_E_XZ[0], PLATE_THICKNESS, _part.NOTCH_CAP_E_XZ[1]
        ),
        radius_mm=CAP_DETAIL_RADIUS_MM,
        view_xy=CAP_DETAIL_CENTER,
        detail_label="D",
        scale=CAP_DETAIL_SCALE,
        label="lock notch cap detail",
    )
    set_hidden_lines_removed(adapter, cap_detail)
    profile_pivot = model_point_in_view(
        adapter, profile, (0.0, PLATE_THICKNESS / 1000.0, 0.0), label="profile pivot"
    )
    print(f"profile pivot: sheet_xy={profile_pivot[:2]} expected={PROFILE_PIVOT_XY}")
    if math.dist(profile_pivot[:2], PROFILE_PIVOT_XY) > 0.0005:
        # The C-C arrow clearances in the tests are laid out from it.
        _telemetry.warn(
            f"profile pivot landed at {profile_pivot[:2]}, layout assumes {PROFILE_PIVOT_XY}"
        )
    slot_ends = [
        model_point_in_view(adapter, profile, point, label=f"slot section end {index}")
        for index, point in enumerate(slot_section_line_model_points())
    ]
    slot_section = create_section_view(
        adapter,
        profile,
        line_start=slot_ends[0],
        line_end=slot_ends[1],
        view_xy=SLOT_SECTION_CENTER,
        section_label="C",
        scale=(1, 1),
        partial=False,
        label="tip screw slot section",
    )
    slot_cut = _early_bound(slot_section.GetSection(), "IDrSection")
    slot_cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="slot section cut faces only")
    _look_slot_section_south(adapter, profile, slot_section, slot_cut)
    set_hidden_lines_removed(adapter, slot_section)

    profile_annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="profile plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _hide_profile_cosmetic_threads(adapter, profile)
    feature_annotations = curate_view_dimensions(
        adapter,
        feature,
        keep=FEATURE_KEEP,
        view_label="feature plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    notch_annotations = curate_view_dimensions(
        adapter,
        notch,
        keep=NOTCH_KEEP,
        view_label="notch plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _pin_tip_slot_z_arrows_inside(adapter, notch_annotations)
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="pivot section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    for annotation in section_annotations:
        if dimension_name(adapter, annotation) == "PlateThk":
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            for witness_index in (0, 1):
                ok, _use_doc, old_gap = display.GetWitnessLineGap(witness_index, False, 0.0)
                if ok is not True:
                    raise RuntimeError("plate thickness witness gap could not be read")
                # Measured native witness origin is x415; the actual cut edge
                # was x310.2 (before I31). Leave a visible 1.2 mm gap short of
                # the cut edge, without changing the model dimension or hiding
                # either witness. Origin and cut end move together with the
                # strip (see PLATE_THK_WITNESS_SET_BACK), so the gap is fixed.
                gap = float(old_gap) + 0.106
                if display.SetWitnessLineGap(witness_index, False, gap) is not True:
                    raise RuntimeError("plate thickness witness gap was refused")
                ok, use_doc, actual_gap = display.GetWitnessLineGap(witness_index, False, 0.0)
                if ok is not True or use_doc or abs(float(actual_gap) - gap) > 1e-8:
                    raise RuntimeError("plate thickness witness gap did not persist")
                print(f"PlateThk witness {witness_index}: old_gap_m={old_gap} gap_m={actual_gap}")
            rebuild_drawing(adapter, label="plate thickness cut-edge witness gaps")
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="tip screw slot detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _set_arrows_inside(adapter, detail_annotations, DETAIL_ARROWS_INSIDE)
    # Detail D alone imports the notch sketch (NotchW and the mouth angle);
    # the notch plan keeps only the cap sketch's centre.
    cap_detail_annotations = curate_view_dimensions(
        adapter,
        cap_detail,
        keep=CAP_DETAIL_KEEP,
        view_label="lock notch cap detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _assert_mouth_angle_in_wedge(adapter, cap_detail, cap_detail_annotations)
    # U41: the thickness is the stock's, a reference with no band.
    thickness_annotations = [
        item for item in section_annotations
        if dimension_name(adapter, item) == "PlateThk"
    ]
    if len(thickness_annotations) != 1:
        raise RuntimeError("expected one native plate thickness")
    thickness_reference = set_reference_dimension(
        adapter, thickness_annotations[0], label="stock plate thickness reference"
    )
    set_dimension_callouts(
        adapter, thickness_annotations, {"PlateThk": PLATE_STOCK_CALLOUT}
    )
    slot_section_annotations = curate_view_dimensions(
        adapter,
        slot_section,
        keep=SLOT_SECTION_KEEP,
        view_label="tip screw slot section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _keep_depth_on_its_attached_end(adapter, slot_section_annotations)
    relief_annotations = [
        item for item in section_annotations
        if dimension_name(adapter, item) == "PivotBearingReliefDepth"
    ]
    if len(relief_annotations) != 1:
        raise RuntimeError("expected one native pivot relief depth")
    relief_reference = set_reference_dimension(
        adapter, relief_annotations[0], label="matched pivot relief reference depth"
    )
    annotations = [
        *profile_annotations,
        *feature_annotations,
        *notch_annotations,
        *section_annotations,
        *detail_annotations,
        *cap_detail_annotations,
        *slot_section_annotations,
    ]
    if not auto_center_marks(adapter, feature, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to feature plan")

    pivot_edge, mount_edge, dowel_edge = _visible_plan_controls(adapter, feature)
    # Below the section line, between the A arrows.
    add_native_hole_callout(
        adapter,
        feature,
        callout_xy=(0.215, 0.107),
        label="pivot close-clearance hole",
        edge=pivot_edge,
        process="DRILL",
    )
    tap_callout = add_native_hole_callout(
        adapter,
        feature,
        callout_xy=(0.200, 0.258),
        label="v2 post-mount tapped holes",
        edge=mount_edge,
        process=POST_MOUNT_TRANSFER_CALLOUT,
    )
    _require_countersink_max(
        tap_callout, spec=POST_MOUNT_SPEC, label="v2 post-mount tapped holes"
    )
    # The dowel pair's size, band and THRU stay native; the prefix names the
    # mating post and the reamer.  A reamed fit prints three places.
    dowel_callout = add_native_hole_callout(
        adapter,
        feature,
        callout_xy=PLATE_DOWEL_CALLOUT_XY,
        label="post dowel reamed holes",
        edge=dowel_edge,
        process=PLATE_DOWEL_CALLOUT,
    )
    set_hole_callout_precision(
        dowel_callout, {"hw-diam": 3}, label="post dowel ream diameter"
    )
    # The section shows the top seat at the bottom.  Arrows land mid-face so
    # neither symbol reads as controlling a corner, hole wall or outer edge.
    seat_edge = _horizontal_section_edge(section, 6.35, label="top seat")
    add_surface_finish(
        adapter,
        section,
        symbol_xy=_shifted(0.291, 0.087),
        control=surface_finish_by_key(SURFACE_FINISHES, "post_seat"),
        label="post and tip-block seat finish",
        char_height=0.0025,
        entity=seat_edge,
        leader_attach_xy=_section_edge_midpoint(adapter, section, seat_edge, label="top seat"),
    )
    slide_edge = _horizontal_section_edge(
        section, 0.0, label="base slide", prefer_right=True
    )
    add_surface_finish(
        adapter,
        section,
        symbol_xy=BASE_SLIDE_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "base_slide"),
        label="base sliding-face finish",
        char_height=0.0025,
        entity=slide_edge,
        leader_attach_xy=_section_edge_midpoint(adapter, section, slide_edge, label="base slide"),
    )

    add_property_linked_note(adapter, "Profile View Note", 0.045, 0.085)
    add_property_linked_note(adapter, "Feature View Note", 0.150, 0.085)
    notch_note = add_property_linked_note(adapter, "Notch View Note", *NOTCH_CAPTION_UPPER_LEFT)
    iso_note = add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_UPPER_LEFT)
    _assert_notch_captions_clear(
        adapter,
        notch_annotations,
        {"Notch View Note": notch_note, "Isometric View Note": iso_note},
    )
    add_property_linked_note(
        adapter, "Pivot Relief Fit", *RELIEF_NOTE_XY, char_height=0.0025
    )
    cutter_notes = [
        _add_arc_note(adapter, detail, cutter_note) for cutter_note in CUTTER_NOTES
    ]
    cap_r_note = _add_arc_note(adapter, cap_detail, CAP_R_NOTE)
    _add_arc_note(adapter, feature, RELIEF_ID_NOTE)

    # Annotation insertion can invalidate the exported display geometry.
    for view in (profile, feature, notch, section, slot_section, iso, cap_detail):
        set_hidden_lines_removed(adapter, view)
    # Re-assert after the dimensions attach: the shared helper passes through
    # HLR, so the dashed edge set is regenerated, not a same-mode no-op.
    set_hidden_lines_visible(adapter, detail)
    # Last, after every annotation and display-mode regen could re-lay it.
    _position_view_label(
        adapter,
        detail,
        DETAIL_LABEL_LOWER_LEFT,
        label="detail B label",
        added_notes=cutter_notes,
    )
    _position_view_label(
        adapter,
        slot_section,
        SLOT_SECTION_LABEL_LOWER_LEFT,
        label="section C-C label",
    )
    _position_view_label(
        adapter,
        cap_detail,
        CAP_DETAIL_LABEL_LOWER_LEFT,
        label="detail D label",
        added_notes=[cap_r_note],
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if (str(relief_reference.GetText(1)), str(relief_reference.GetText(2))) != ("(", ")"):
        raise RuntimeError("pivot relief reference state did not persist")
    if (
        str(thickness_reference.GetText(1)),
        str(thickness_reference.GetText(2)),
    ) != ("(", ")"):
        raise RuntimeError("stock plate thickness reference state did not persist")
    # Each corner's station is its fillet centre projected into the profile:
    # the sheet literals these replaced went stale when I31 widened the
    # north-west (the NW centre moved 1.39 mm on the sheet, past the 1 mm
    # match window: "expected 2 owned visible CornerNWR arc(s) ... found 0").
    for label, _x, _z, radius_mm in _part._CORNERS:
        model_center = corner_station_model_m(label)
        station_xy = model_point_in_view(
            adapter, profile, model_center, label=f"Corner{label} fillet centre"
        )[:2]
        print(
            f"Corner{label}R station: fillet_centre_model_m={model_center} "
            f"sheet_m=({station_xy[0]:.5f},{station_xy[1]:.5f})"
        )
        _assert_corner_radius_attachment(
            adapter, profile, profile_annotations,
            name=f"Corner{label}R", feature_name=f"Corner{label}",
            radius_m=radius_mm / 1000.0, station_xy=station_xy,
        )
    _assert_each_kept_dimension_once(
        adapter,
        {
            "profile plan": profile,
            "feature plan": feature,
            "notch plan": notch,
            "isometric": iso,
            "pivot section": section,
            "tip screw slot detail": detail,
            "lock notch cap detail": cap_detail,
            "tip screw slot section": slot_section,
        },
    )
    if cut.GetDisplayOnlySurfaceCut() is not True:
        raise RuntimeError("pivot section lost its cut-only display after annotation")
    for face_name, model_y in (
        ("post_seat", PLATE_THICKNESS / 1000.0),
        ("base_slide", 0.0),
    ):
        projected = model_point_in_view(
            adapter, section, (0.0, model_y, 0.0), label=f"{face_name} projection"
        )
        print(
            f"section face {face_name}: model_y_mm={model_y * 1000:.3f} "
            f"sheet_xy_mm=({projected[0] * 1000:.3f},{projected[1] * 1000:.3f})"
        )
    section_pivot_x = model_point_in_view(
        adapter, section, (0.0, 0.0, 0.0), label="pivot in section A-A"
    )[0]
    witness_end_x = plate_thk_witness_end_x(section_pivot_x)
    print(
        f"section A-A pivot sheet_x={section_pivot_x:.5f} "
        f"predicted={pivot_section_pivot_x():.5f} "
        f"strip_mm={pivot_section_strip_mm()} witness_end_x={witness_end_x:.5f}"
    )
    for sheet_geometry in collect_document(adapter):
        print(describe_sheet(sheet_geometry))
        thickness_geometry = [
            item for item in sheet_geometry.annotations if item.label == "PlateThk"
        ]
        if len(thickness_geometry) != 1:
            raise RuntimeError("expected one measured plate thickness annotation")
        witnesses = [
            segment for segment in thickness_geometry[0].segments
            if abs(segment.y0 - segment.y1) < 1e-8
            and any(
                abs(segment.y0 - SECTION_SHIFT[1] - level) < 0.0001
                for level in (0.09865, 0.11135)
            )
        ]
        if len(witnesses) != 2 or any(
            abs(max(segment.x0, segment.x1) - witness_end_x) > 0.0005
            or abs(min(segment.x0, segment.x1) - SECTION_SHIFT[0] - 0.299) > 0.0005
            for segment in witnesses
        ):
            raise RuntimeError(f"plate thickness witnesses did not shorten to the cut edge: {witnesses}")
    # diag (MHA-091 RD3 callout probe, never merge): before the layout audit the
    # ac4f leaf fails; discards every document unsaved, then always raises.
    mha091_callout_probe.run(
        adapter,
        source=SOURCE,
        slddrw=SLDDRW,
        dowel_callout=dowel_callout,
        process=PLATE_DOWEL_CALLOUT,
        out_dir=CAD_ROOT / "out" / "reports" / "mha091-probe",
    )
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Swing Platform Manufacturing Drawing",
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
