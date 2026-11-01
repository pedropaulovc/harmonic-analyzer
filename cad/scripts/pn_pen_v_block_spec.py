r"""Pen v-block dimensional contract -- the single source of truth shared by the
part build (``build_pn_pen_v_block.py``), its drawing (``draw_pn_pen_v_block.py``)
and the carriage layout/balance (``pn_pen_carriage_geom``).

PURE DATA, no SolidWorks/COM imports.

Part frame: length X 0..BLOCK_LENGTH (x 0 = the PAPER end face), height Y
0..BLOCK_HEIGHT (y 0 = the bottom face), depth Z with z 0 = the NECK's FRONT
face, away from the paper.  The block is a "simplified E" in plan: a neck
x 0..RELIEF_X0, z 0..NECK_DEPTH, that the stirrup straddles and that carries
the V, then a body x RELIEF_X0..BLOCK_LENGTH, BODY_Z0..BODY_Z1, wider by
BODY_SIDE_STEP each side, that carries the relief slot, the pivot bore and
the set screw (which enters from the body's front face, z BODY_Z0).

Re-derived from the engineerguy 4/4 video (9:15-10:34) and the 2026-10 design
brief (``balance_options.png`` panel C):

* The marker's grip (``pn_vn_pen_marker_spec.BARREL_DIA``, a regular-size
  Sharpie Fine Point) seats in a 90 degree V-groove along the bottom of the
  neck, pressed up by the stirrup's thumb screw; the V centres the barrel
  whatever its diameter tolerance.
* The marker's larger silver body runs out through a flat-roofed RELIEF slot
  along the body, so only the grip touches the block.  The body is wider
  than the neck so both slot walls hold the rule 17 .080 target at the
  title block's .XX band.
* The rod's turned pivot end drops into a reamed pivot bore just past the
  step; the rod's square shoulder rests on the block top, and a #4-40 set
  screw from the body's front face locks the pen's angle to the paper (book:
  "a small set screw that adjusts the angle of the pen").
* The block's length trims the carriage CG onto the rod axis
  (``pn_pen_carriage_geom`` solves and asserts).

Drawing contract: the pivot bore is a sketched, reamed cut (its toleranced
diameter is a marked sketch dimension, banded to the rod pivot); the set-screw
tap is a Hole Wizard feature whose size prints as a native hole callout and
whose station prints as its marked placement dimensions.
The bore's top-edge chamfer prints as a native single MIN limit: it must clear
the rod's shoulder-root fillet; a light break past that floor still leaves the
rod's seat flats (guard below).
No GD&T (drawing-simplicity-policy.md rule 5) and no roughness symbols: the
pivot is clamped by the set screw, nothing runs or slides on the block (rule 6).
Material and finish (bright brass) ride the title block, so the sheet carries
no general note.
"""

from __future__ import annotations

import math
from typing import NamedTuple

import _config
from _fit_ream_h7 import REAM_H7
from _hole_spec import HoleSpec, TAP_DRILL_MM, THREAD_MAJOR_MM
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import angular_band_deg, printed_deviations
import pn_pen_rod_spec as rod
import pn_vn_pen_marker_spec as marker
import pn_vn_pen_rod_set_screw_spec as rod_set_screw

# #290: the sheet prints decimal inch (``drawing_unit: in``).  Lengths stay
# millimetres, each the exact decimal of its printed inch value, except the
# carriage's closures, kept at their millimetre values and printed rounded:
# the block height (with pn_pen_rod_spec.SQUARE_LENGTH it sets the stud eye's
# height, pn_pen_carriage_geom.STUD_HEAD_TOP_REST_Y) and the V's 12.0 mouth
# width (it sets the marker axis, pn_pen_carriage_geom.MARKER_POS).  Every
# printed check below judges the PRINTED limits (printed_deviations).
UNIT = drawing_unit("parts/pn-pen-v-block", _config.parts("pn-pen-v-block"))

# X, along the marker: the CG solve (pn_pen_carriage_geom) puts the carriage's
# plan CG on the rod axis at this length, on the .XX grid.
BLOCK_LENGTH = 27.178  # 1.07
BLOCK_HEIGHT = 18.0  # Y; closure, prints .71
# --- Depth (Z): neck and body, both centred on DEPTH_MID_Z ---
# The stirrup's window passes the neck with 1.0 a side
# (pn_pen_carriage_geom), so the neck rounds down to .70, not up to .71.
NECK_DEPTH = 17.78  # .70; z 0..NECK_DEPTH
BODY_SIDE_STEP = 2.032  # .08; the body stands this proud of the neck each side
BODY_Z0 = -BODY_SIDE_STEP  # the body's front face: the depth datum
BODY_Z1 = NECK_DEPTH + BODY_SIDE_STEP
BODY_DEPTH = round(BODY_Z1 - BODY_Z0, 6)  # 21.844, .86
DEPTH_MID_Z = NECK_DEPTH / 2.0  # the V, the relief and the pivot bore centre here


def depth_station(z: float) -> float:
    """A part-frame z as the print's station from the body's front face."""
    return round(z - BODY_Z0, 6)


# --- V-groove (grip seat), x 0..RELIEF_X0 ---
# The print defines the V by what seats the grip: each flank's angle to the
# bottom face and both mouth edges on that face, each a baseline station from
# the body's front face (all four driving in VGrooveProfile), so each flank
# is fixed on its own (blind review: an included angle left them free to
# tilt together).  The mouth width and the theoretical apex height follow
# from them.  The apex is not cut sharp
# (drawing-guidelines.md rule 16): a flat across it, V_FLAT_WIDTH wide
# (driving, .XX), is the tip a 90 deg chamfer mill or a small end mill leaves.
# The flat's height is what the flanks and the width leave; it prints as a
# reference.
V_FLANK_ANGLE_DEG = 45.0  # each flank to the bottom face; prints "2X 45" deg
V_ANGLE_DEG = 180.0 - 2.0 * V_FLANK_ANGLE_DEG  # the included angle, 90
# The mouth's 12.0 width is a closure (module docstring): it prints as the
# two rounded mouth stations, centred on the neck.
V_MOUTH_WIDTH = 12.0
V_MOUTH_Z0 = round((NECK_DEPTH - V_MOUTH_WIDTH) / 2.0, 6)  # 2.89 (prints .19)
V_MOUTH_Z1 = round(V_MOUTH_Z0 + V_MOUTH_WIDTH, 6)  # 14.89 (prints .67)
_HALF = math.radians(V_ANGLE_DEG / 2.0)
V_APEX_Y = round(
    (V_MOUTH_WIDTH / 2.0) / math.tan(_HALF), 6
)  # 6.0: apex height above the bottom face, centred in Z
# A barrel of radius r in the V: axis r/sin(half-angle) below the apex, the two
# contact lines r*sin(half-angle) below it.
MARKER_AXIS_Y = V_APEX_Y - (marker.BARREL_DIA / 2.0) / math.sin(_HALF)
V_CONTACT_Y = V_APEX_Y - (marker.BARREL_DIA / 2.0) * math.sin(_HALF)
V_FLAT_WIDTH = 2.032  # .08
V_FLAT_Y = round(V_APEX_Y - (V_FLAT_WIDTH / 2.0) / math.tan(_HALF), 6)  # 4.984
# The groove's section: the V's triangle less the tip the flat leaves standing.
V_GROOVE_AREA = (
    V_APEX_Y * V_MOUTH_WIDTH / 2.0 - V_FLAT_WIDTH * (V_APEX_Y - V_FLAT_Y) / 2.0
)  # 35.0
# The flat meets each flank in an internal corner no cutter leaves sharp: each
# takes the tip radius of a chamfer mill or the corner of an end mill, up to
# V_APEX_FILLET_R.  It prints as the single limit "2X R.020 MAX"; swTolMAX
# prints the nominal, so the model carries the limit (pn_pen_rod_spec's
# shoulder root).
V_APEX_FILLET_R = 0.508  # .020
V_APEX_FILLET_BAND = (0.0, -V_APEX_FILLET_R)
V_APEX_FILLET_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "2X R.020 MAX"
V_APEX_FILLET_PLACES = 3
# Each round turns through 90 deg - half-angle (flat to flank) and fills
# r^2 (tan(turn/2) - turn/2) of its corner.
_APEX_TURN = math.pi / 2.0 - _HALF
V_APEX_FILLET_AREA = (
    2.0 * V_APEX_FILLET_R**2 * (math.tan(_APEX_TURN / 2.0) - _APEX_TURN / 2.0)
)  # 0.011
# The groove's finished section: the trapezoid less the rounds in its corners.
V_GROOVE_SECTION = V_GROOVE_AREA - V_APEX_FILLET_AREA

# --- Relief slot (body clearance), x RELIEF_X0..BLOCK_LENGTH ---
# The step stands far enough toward the paper end that the reamed pivot bore
# drops wholly into the slot at the printed limits (guard below): at 10.0 the
# bore's edge stood 0.5 off the step, and at the limits the ream broke into
# the step wall in a crescent (machinist review final4).  The V, and so the
# grip's seat, is this long.  The neck ends here too: the body's step faces
# stand in line with the slot's.
RELIEF_X0 = 8.89  # .35
RELIEF_Z0 = 1.016  # .04 near (front) wall; prints .12 from the datum
RELIEF_Z1 = round(NECK_DEPTH - RELIEF_Z0, 6)  # far (back) wall; prints .74
RELIEF_WIDTH = round(RELIEF_Z1 - RELIEF_Z0, 6)
RELIEF_HEIGHT = 6.604  # .26
# The slot's two internal corners at the step (x = RELIEF_X0) keep the end
# mill's radius, an .080 cutter .26 deep.  Modelled as plan arcs in the slot
# profile, not a fillet feature.
RELIEF_CORNER_R = 1.016  # .04
# The V is cut on one corner radius past the step, to where the corner arcs
# end.  Past the step its whole section lies inside the slot's (guard below),
# so the extra run removes no brass; the step face never ends in a sliver
# under a flank (machinist review final2).
V_CUT_LENGTH = RELIEF_X0 + RELIEF_CORNER_R
if not (RELIEF_Z0 < V_MOUTH_Z0 and V_MOUTH_Z1 < RELIEF_Z1 and V_APEX_Y < RELIEF_HEIGHT):
    raise AssertionError("past the step the V must lie inside the relief slot")

# --- Pivot bore (rod's turned end): a sketched cut from the top face down
# into the relief slot, reamed with the owned .1260 chucking reamer (#290
# owner ruling: the 4 mm pivot becomes .126) ---
PIVOT_BORE_DIA = 3.2004  # .126 reamed
PIVOT_BORE_BAND = REAM_H7  # +.0005/.0000
# Just past the step (guard below); the CG solve sets the length.
PIVOT_BORE_X = 12.446  # .49
# 45 deg chamfer on the bore's TOP edge, where the rod's square shoulder seats:
# it clears the rod's shoulder-root fillet (pn_pen_rod_spec.SHOULDER_FILLET_R
# MAX).  Printed as a native single MIN limit: a general band would let it
# shrink to nothing.
PIVOT_BORE_TOP_CHAMFER = 0.3048  # .012
# (upper, lower): the nominal IS the MIN limit (lower 0); the upper, which a
# MIN print does not show, is the native record of what still leaves the
# rod's seat flats (guard below).
PIVOT_CHAMFER_BAND = (0.1016, 0.0)  # +.004
PIVOT_CHAMFER_TOL_TYPE = 5  # swTolType_e.swTolMIN: prints ".012 MIN"
PIVOT_CHAMFER_PLACES = 3

# --- Rod set screw: #4-40 tapped from the body's front face into the pivot bore ---
SET_SCREW_TAP_SPEC = HoleSpec("tapped", rod_set_screw.THREAD, end="through_next")
SET_SCREW_Y = 11.938  # .47
SET_SCREW_TAP_LENGTH = round(
    DEPTH_MID_Z - BODY_Z0 - PIVOT_BORE_DIA / 2.0, 6
)  # 9.3218: body front face to bore wall

_WALL = WALL_FLOOR_MM  # drawing-guidelines.md rule 17 (walls and webs) floor
# The carriage hangs the marker on the block's mid-depth: the neck, the body,
# the V and the relief all centre on it (pn_pen_carriage_geom, its mass model).
for _name, _z0, _z1 in (
    ("neck", 0.0, NECK_DEPTH),
    ("body", BODY_Z0, BODY_Z1),
    ("V's mouth edges", V_MOUTH_Z0, V_MOUTH_Z1),
    ("relief's walls", RELIEF_Z0, RELIEF_Z1),
):
    if abs((_z0 + _z1) / 2.0 - DEPTH_MID_Z) > 1e-9:
        raise AssertionError(f"the {_name} must centre on the block's mid-depth")
if min(V_MOUTH_Z0, NECK_DEPTH - V_MOUTH_Z1) < WALL_TARGET_MM:
    raise AssertionError(
        "V-groove leaves under the .080 target lands on the bottom face"
    )
if not 1.0 <= V_CONTACT_Y < V_FLAT_Y:
    raise AssertionError("grip contact lines must lie on the V flanks, under the flat")
if min(RELIEF_Z0 - BODY_Z0, BODY_Z1 - RELIEF_Z1) < WALL_TARGET_MM:
    raise AssertionError("relief slot legs under the rule 17 .080 target")
_BODY_R = marker.BODY_FRONT_DIA / 2.0
_BODY_HALF_CHORD_AT_BOTTOM = math.sqrt(_BODY_R**2 - MARKER_AXIS_Y**2)
if RELIEF_WIDTH / 2.0 - _BODY_HALF_CHORD_AT_BOTTOM < 0.25:
    raise AssertionError("relief slot does not pass the marker body")
if RELIEF_HEIGHT - (MARKER_AXIS_Y + _BODY_R) < 0.25 or RELIEF_HEIGHT <= V_APEX_Y:
    raise AssertionError("relief roof must clear the body and swallow the V apex")
if PIVOT_BORE_X - PIVOT_BORE_DIA / 2.0 <= RELIEF_X0:
    raise AssertionError("pivot bore must drop wholly into the relief slot")
if BLOCK_LENGTH - (PIVOT_BORE_X + PIVOT_BORE_DIA / 2.0) < WALL_TARGET_MM:
    raise AssertionError(
        "the free end leaves under the .080 target past the pivot bore"
    )
if SET_SCREW_TAP_LENGTH < 1.5 * THREAD_MAJOR_MM[rod_set_screw.THREAD]:
    raise AssertionError(
        "rod set-screw tap is under drawing-guidelines.md rule 18 (1.5 D)"
    )
if rod_set_screw.LENGTH > SET_SCREW_TAP_LENGTH:
    raise AssertionError("rod set screw stands proud of the front face")
if BLOCK_HEIGHT - SET_SCREW_Y - TAP_DRILL_MM[rod_set_screw.THREAD] / 2.0 < _WALL:
    raise AssertionError("rod set-screw tap breaks the block top")
# The relief corners stand RELIEF_CORNER_R into the slot from each wall at the
# step.  The grip seats in the V and may run on past the step (the carriage
# places it 2.5 past); it is widest in the slot at the bottom face (its axis
# is below the block), so the corner must stand clear of it there wherever it
# ends.  The body (wider) must start past x = RELIEF_X0 + RELIEF_CORNER_R; the
# carriage layout owns where it starts.
_GRIP_R = marker.BARREL_DIA / 2.0
_GRIP_GAP_AT_BOTTOM = DEPTH_MID_Z - math.sqrt(_GRIP_R**2 - MARKER_AXIS_Y**2) - RELIEF_Z0
if _GRIP_GAP_AT_BOTTOM - RELIEF_CORNER_R < 0.25:
    raise AssertionError("relief corner radius reaches the marker grip")
if RELIEF_Z0 + RELIEF_CORNER_R >= DEPTH_MID_Z - PIVOT_BORE_DIA / 2.0 - _WALL:
    raise AssertionError("relief corner radius crowds the pivot bore")
# The rod's shoulder fillet (R MAX) is a quarter round on the pivot; with the
# pivot against the bore wall its arc stands at most R * (2 - sqrt 2) proud of
# a 45 deg chamfer's leg at the bore edge, so the chamfer's MIN leg must reach
# that with 0.1 to spare; the chamfered mouth must stay inside the square's
# seat flats.
if PIVOT_BORE_TOP_CHAMFER < rod.SHOULDER_FILLET_R * (2.0 - math.sqrt(2.0)) + 0.1:
    raise AssertionError("pivot-bore chamfer does not clear the rod shoulder fillet")
if (
    PIVOT_BORE_DIA + PIVOT_BORE_BAND[0]
) / 2.0 + PIVOT_BORE_TOP_CHAMFER + PIVOT_CHAMFER_BAND[0] >= (
    rod.ROD_SECTION + rod.SECTION_BAND[1]
) / 2.0:
    raise AssertionError("pivot-bore chamfer eats the rod shoulder's seat flats")


def _on_grid(value_mm: float, places: int) -> bool:
    """True when ``value_mm`` is an exact decimal-inch value at ``places``."""
    inches = value_mm / 25.4
    return math.isclose(round(inches, places), inches, abs_tol=1e-9)


if not _on_grid(PIVOT_BORE_TOP_CHAMFER, PIVOT_CHAMFER_PLACES):
    raise AssertionError("the pivot-bore chamfer must print exactly at its places")

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  ``build_pn_pen_v_block`` marks exactly these; ``draw_pn_pen_v_block``
# keeps exactly their union across its per-view ``keep`` maps.  The offline test
# enforces ``union(marks) == union(keeps)``. The set-screw tap is a Hole Wizard
# feature: its size prints as a native hole callout, its station as the marked
# placement dimensions (SetScrewX repeats the pivot station on the face the tap
# is drilled from).  The V's length and the neck's print as the relief's start
# station (ReliefX0, the same "ReliefX0" global): the body's step faces stand in
# line with the slot's, and the V runs into the slot (V_CUT_LENGTH), so the step
# is where its brass ends.  Every feature is located across the depth from ONE
# datum, the body's FRONT face (z BODY_Z0), never by the depth's symmetry and
# never chained: the neck's faces (NeckZ0 / NeckZ1), the body's back face
# (Depth), the V's two mouth edges (VMouthZ0 / VMouthZ1), the relief's two walls
# (ReliefZ0 / ReliefZ1) and the pivot bore (PivotZ) are each a baseline from it.
# The plan outline (OutlineProfile, Top plane) prints the length and, in one
# baseline row from the body's front face, the neck's two faces and the
# body's back face in the bottom view, where the neck's step from the body is
# an outline change on both long edges (blind review final8, the third time:
# printed in the paper-end view, the step's faces read as thin ribs between
# the neck's end face and the body's beyond it; final9: without the depth
# closing that row, the neck's back face read as the overall); the block's
# extrusion its height.  The V's sketch (Right plane, the paper end) carries
# a construction stub on the body's front face (the datum's foot), so the
# paper-end view prints the V's edges from the datum in one baseline row.
# Section A-A shows the relief and the pivot bore across the depth, but their
# sketches lie in the Top plane and project edge-on there.  ReliefReference
# and PivotReference lie IN section A-A's cutting plane (x = PIVOT_BORE_X,
# the bond cradle's recipe), each chord on an edge the section draws:
# ReliefReference runs a stub up the front face from its foot and both relief
# walls from the bottom face to the roof (ReliefHeight on the far wall, which
# section A-A draws on its right, outside the stations under it; the Relief
# cut's own depth vector stops in air), the near foot (ReliefZ0) and the far
# foot (ReliefZ1), each from the front face's foot; PivotReference holds stubs
# down the front face and the bore axis from the top face (PivotZ between
# their tops) and the bore's top chamfer leg on the far side: the chamfer
# feature's own dimension may attach on the near side, under PivotZ.  Both are
# saved hidden; the drawing shows them in section A-A
# (``_drawing_hidden_sketches``) while the part shows them at the cut. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "OutlineProfile": {"Length", "NeckZ0", "NeckZ1", "Depth"},
    "Block": {"Height"},
    "VGrooveProfile": {
        "VFlankAngle",
        "VFlatWidth",
        "VFlatY",
        "VMouthZ0",
        "VMouthZ1",
    },
    "VApexFillets": {"VApexFilletR"},
    "ReliefProfile": {"ReliefX0", "ReliefCornerR"},
    "ReliefReference": {"ReliefZ0", "ReliefZ1", "ReliefHeight"},
    "PivotBoreProfile": {"PivotX", "PivotDia"},
    "PivotReference": {"PivotZ", "PivotChamferSize"},
    "SetScrewHole": {"SetScrewX", "SetScrewY"},
}
REFERENCE_SKETCHES = ("ReliefReference", "PivotReference")
SECTION_REFERENCE_SKETCHES = REFERENCE_SKETCHES
# Places carry the title block's tolerance (drawing-guidelines.md rule 3).
# Every station and size a fit, wall or stack reads prints .XX (+/-.01): the
# outline, the neck faces (the stirrup's window must pass the neck at both
# parts' loosest limits, pn_pen_frame_spec), the V's mouth edges, the
# relief's walls, roof and step, the bore and tap stations.  The V prints
# each flank's angle to the bottom face (one "2X 45°" for both, whole degrees,
# the title block's +/-1); the flat's height the flanks leave is a reference,
# driven in the sketch, at the mouth stations' and flat's two places, so it
# reads what they close to.  The flat's two rounds and the bore chamfer print
# their single limits at three places, the reamed bore its +.0005 band at four.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "OutlineProfile": {"Length": 2, "NeckZ0": 2, "NeckZ1": 2, "Depth": 2},
    "Block": {"Height": 2},
    "VGrooveProfile": {
        "VFlankAngle": 0,
        "VFlatWidth": 2,
        "VFlatY": 2,
        "VMouthZ0": 2,
        "VMouthZ1": 2,
    },
    "VApexFillets": {"VApexFilletR": V_APEX_FILLET_PLACES},
    "ReliefProfile": {"ReliefX0": 2, "ReliefCornerR": 2},
    "ReliefReference": {"ReliefZ0": 2, "ReliefZ1": 2, "ReliefHeight": 2},
    "PivotBoreProfile": {"PivotX": 2, "PivotDia": 4},
    "PivotReference": {"PivotZ": 2, "PivotChamferSize": PIVOT_CHAMFER_PLACES},
    "SetScrewHole": {"SetScrewX": 2, "SetScrewY": 2},
}
# The one driven sketch dimension the print shows, parenthesised as a
# reference (no tolerance): the apex flat's height, which the flanks' angles,
# mouth edges and flat width fix.  It follows the closure apex (.196) and
# prints rounded, (.20): what the printed .19 / .67 mouth stations, .08 flat
# and 45° flanks close to (machinist review c03368c: at three places it
# disagreed with them).
REFERENCE_DIMENSIONS: tuple[tuple[str, str], ...] = (("VGrooveProfile", "VFlatY"),)
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if DRAWING_PRECISION.keys() != DRAWING_DIMENSIONS.keys() or any(
    set(DRAWING_PRECISION[feature]) != names
    for feature, names in DRAWING_DIMENSIONS.items()
):
    raise AssertionError("every marked pen v-block dimension needs authored places")


# The model value of every printed tolerance dimension the checks read, so a
# closure that prints rounded is judged at its printed limits.
_PRINTED_VALUES: dict[str, float] = {
    "Length": BLOCK_LENGTH,
    "NeckZ0": depth_station(0.0),
    "NeckZ1": depth_station(NECK_DEPTH),
    "Depth": BODY_DEPTH,
    "VFlatWidth": V_FLAT_WIDTH,
    "VMouthZ0": depth_station(V_MOUTH_Z0),
    "VMouthZ1": depth_station(V_MOUTH_Z1),
    "ReliefX0": RELIEF_X0,
    "ReliefZ0": depth_station(RELIEF_Z0),
    "ReliefZ1": depth_station(RELIEF_Z1),
    "ReliefHeight": RELIEF_HEIGHT,
    "PivotX": PIVOT_BORE_X,
    "PivotZ": depth_station(DEPTH_MID_Z),
    "Height": BLOCK_HEIGHT,
    "SetScrewY": SET_SCREW_Y,
}


def _dev(name: str) -> tuple[float, float]:
    """``(lower, upper)`` mm the named dimension may deviate from its model
    value at its printed limits (the title block's row at its places)."""
    return printed_deviations(
        _PRINTED_VALUES[name], DRAWING_PRECISION_BY_NAME[name], unit=UNIT
    )


# --- Printed worst case (every band at its limit at once) ---
# Every station across the depth is a baseline from the body's front face, so
# no band adds through another edge.  Rule 17: the near wall is ReliefZ0
# itself, the far wall Depth - ReliefZ1; the V's lands lie between a neck
# face and a mouth edge.
RELIEF_NEAR_WALL_PRINTED_MIN = depth_station(RELIEF_Z0) + _dev("ReliefZ0")[0]  # 2.794
RELIEF_FAR_WALL_PRINTED_MIN = (BODY_DEPTH + _dev("Depth")[0]) - (
    depth_station(RELIEF_Z1) + _dev("ReliefZ1")[1]
)  # 2.54
V_NEAR_LAND_PRINTED_MIN = (depth_station(V_MOUTH_Z0) + _dev("VMouthZ0")[0]) - (
    depth_station(0.0) + _dev("NeckZ0")[1]
)  # 2.286
V_FAR_LAND_PRINTED_MIN = (depth_station(NECK_DEPTH) + _dev("NeckZ1")[0]) - (
    depth_station(V_MOUTH_Z1) + _dev("VMouthZ1")[1]
)  # 2.286
# At the inch title block every wall and land clears the .080 target; compare
# at the micron.
if (
    round(
        min(
            RELIEF_NEAR_WALL_PRINTED_MIN,
            RELIEF_FAR_WALL_PRINTED_MIN,
            V_NEAR_LAND_PRINTED_MIN,
            V_FAR_LAND_PRINTED_MIN,
        ),
        6,
    )
    < WALL_TARGET_MM
):
    raise AssertionError("a printed wall or land falls under the rule 17 .080 target")
# The widest neck the print allows, for the stirrup's window.
NECK_WIDTH_PRINTED_MAX = NECK_DEPTH + _dev("NeckZ1")[1] - _dev("NeckZ0")[0]  # 18.288
# The pivot bore must leave the brass wholly into the slot: its paper-side
# edge (station and reamed diameter at their limits) stays past the step at
# its far limit, or the ream breaks into the step wall in a crescent.
PIVOT_BORE_STEP_CLEARANCE_PRINTED_MIN = (
    PIVOT_BORE_X
    + _dev("PivotX")[0]
    - (PIVOT_BORE_DIA + PIVOT_BORE_BAND[0]) / 2.0
    - (RELIEF_X0 + _dev("ReliefX0")[1])
)  # 1.441
if PIVOT_BORE_STEP_CLEARANCE_PRINTED_MIN < 0.0:
    raise AssertionError("at its printed limits the pivot bore breaks the step wall")


class SeatedV(NamedTuple):
    """The grip seated against both flanks of one V (part frame z, y)."""

    axis: tuple[float, float]  # the grip's (and the body's) axis
    flat_clearance: float  # the flat over the grip
    round_clearance: float  # the nearer apex round to the grip
    contact_margin: float  # each contact line inside its flank's straight run
    flat_straight: float  # the flat's straight run between its rounds
    body_half_chord: float  # the body's half-width at the bottom face


def _arc_distance(
    point: tuple[float, float],
    centre: tuple[float, float],
    radius: float,
    span: tuple[float, float],
) -> float:
    """Distance from ``point`` to the arc of ``radius`` about ``centre`` that
    runs between the two bearings in ``span`` (radians, the shorter way)."""
    lo, hi = sorted(span)
    bearing = math.atan2(point[1] - centre[1], point[0] - centre[0])
    ends = [
        math.hypot(
            point[0] - centre[0] - radius * math.cos(angle),
            point[1] - centre[1] - radius * math.sin(angle),
        )
        for angle in (lo, hi)
    ]
    if lo <= bearing <= hi:
        ends.append(math.hypot(point[0] - centre[0], point[1] - centre[1]) - radius)
    return min(ends)


def seated_v(
    mouth_z0: float,
    mouth_z1: float,
    front_deg: float,
    back_deg: float,
    flat_width: float,
    round_r: float,
) -> SeatedV:
    """The grip seated in a V cut to these sizes.  Each flank stands on its
    own mouth edge at its own angle to the bottom face, so the two tilt
    independently and the V may lean."""
    a0, a1 = math.radians(front_deg), math.radians(back_deg)
    s0, c0, s1, c1 = math.sin(a0), math.cos(a0), math.sin(a1), math.cos(a1)
    t0, t1 = s0 / c0, s1 / c1
    apex_z = (t0 * mouth_z0 + t1 * mouth_z1) / (t0 + t1)
    apex_y = t0 * (apex_z - mouth_z0)
    # The axis lies _GRIP_R inside each flank: n . (p - mouth) = _GRIP_R with
    # n the flank's normal into the groove, (s0, -c0) front and (-s1, -c1)
    # back.
    det = -(s0 * c1 + c0 * s1)
    front_rhs, back_rhs = _GRIP_R + s0 * mouth_z0, _GRIP_R - s1 * mouth_z1
    axis = (
        (c0 * back_rhs - c1 * front_rhs) / det,
        (s0 * back_rhs + s1 * front_rhs) / det,
    )
    contacts = (axis[1] + _GRIP_R * c0, axis[1] + _GRIP_R * c1)
    flat_y = apex_y - flat_width / (1.0 / t0 + 1.0 / t1)
    flat_ends = (
        apex_z - (apex_y - flat_y) / t0,
        apex_z + (apex_y - flat_y) / t1,
    )
    # Each round turns through its flank's angle: it meets the flat and the
    # flank r tan(angle / 2) from the corner; its arc runs from the flat's
    # normal (up) to the flank's, both into the brass.
    tangents = (round_r * math.tan(a0 / 2.0), round_r * math.tan(a1 / 2.0))
    rounds = (
        (
            (flat_ends[0] + tangents[0], flat_y - round_r),
            (math.pi / 2.0, math.pi / 2.0 + a0),
        ),
        (
            (flat_ends[1] - tangents[1], flat_y - round_r),
            (math.pi / 2.0 - a1, math.pi / 2.0),
        ),
    )
    flank_straight_tops = (
        flat_y - tangents[0] * s0,
        flat_y - tangents[1] * s1,
    )
    return SeatedV(
        axis=axis,
        flat_clearance=flat_y - (axis[1] + _GRIP_R),
        round_clearance=min(
            _arc_distance(axis, centre, round_r, span) for centre, span in rounds
        )
        - _GRIP_R,
        contact_margin=min(
            min(contacts),
            min(top - y for top, y in zip(flank_straight_tops, contacts)),
        ),
        flat_straight=flat_width - sum(tangents),
        body_half_chord=(
            math.sqrt(_BODY_R**2 - axis[1] ** 2) if axis[1] < 0.0 else _BODY_R
        ),
    )


# Every printed corner of the V at once: each mouth edge at its printed .XX
# limits, each flank at the title block's +/-1 deg on its own, the flat at its
# .XX, the rounds at their MAX (a smaller round only moves brass away from the
# grip).
V_PRINTED_CORNERS = [
    seated_v(z0, z1, front, back, width, V_APEX_FILLET_R)
    for z0 in (V_MOUTH_Z0 + dev for dev in _dev("VMouthZ0"))
    for z1 in (V_MOUTH_Z1 + dev for dev in _dev("VMouthZ1"))
    for front in (
        V_FLANK_ANGLE_DEG - angular_band_deg(unit=UNIT),
        V_FLANK_ANGLE_DEG + angular_band_deg(unit=UNIT),
    )
    for back in (
        V_FLANK_ANGLE_DEG - angular_band_deg(unit=UNIT),
        V_FLANK_ANGLE_DEG + angular_band_deg(unit=UNIT),
    )
    for width in (V_FLAT_WIDTH + dev for dev in _dev("VFlatWidth"))
]
# The body, coaxial with the grip, clears both relief walls at their limits
# (the V leaning toward that wall, its mouth shifted there).
BODY_NEAR_CLEARANCE_PRINTED_MIN = min(
    seat.axis[0] - seat.body_half_chord - (RELIEF_Z0 + _dev("ReliefZ0")[1])
    for seat in V_PRINTED_CORNERS
)
BODY_FAR_CLEARANCE_PRINTED_MIN = min(
    (RELIEF_Z1 + _dev("ReliefZ1")[0]) - (seat.axis[0] + seat.body_half_chord)
    for seat in V_PRINTED_CORNERS
)
if min(BODY_NEAR_CLEARANCE_PRINTED_MIN, BODY_FAR_CLEARANCE_PRINTED_MIN) <= 0.0:
    raise AssertionError("a printed relief wall may touch the marker body")
# The grip seats on both flanks, never on the flat or its rounds: under the
# flat, off the rounds, each contact line up its flank and under the round's
# tangent line, and the narrowest flat still runs straight between its rounds.
V_FLAT_GRIP_CLEARANCE_PRINTED_MIN = min(
    seat.flat_clearance for seat in V_PRINTED_CORNERS
)
V_APEX_FILLET_GRIP_CLEARANCE_PRINTED_MIN = min(
    seat.round_clearance for seat in V_PRINTED_CORNERS
)
V_CONTACT_MARGIN_PRINTED_MIN = min(seat.contact_margin for seat in V_PRINTED_CORNERS)
V_FLAT_STRAIGHT_PRINTED_MIN = min(seat.flat_straight for seat in V_PRINTED_CORNERS)
if V_FLAT_GRIP_CLEARANCE_PRINTED_MIN < 0.25:
    raise AssertionError("at its printed limits the apex flat may touch the grip")
if V_APEX_FILLET_GRIP_CLEARANCE_PRINTED_MIN < 0.25:
    raise AssertionError("at its printed limits an apex round may touch the grip")
if V_CONTACT_MARGIN_PRINTED_MIN <= 0.0:
    raise AssertionError("at its printed limits a grip contact leaves its flank")
if V_FLAT_STRAIGHT_PRINTED_MIN <= 0.0:
    raise AssertionError("at its printed limits the apex rounds meet across the flat")
# (feature, dimension) -> (upper, lower) native band.
DRAWING_BANDS: dict[tuple[str, str], tuple[float, float]] = {
    ("PivotBoreProfile", "PivotDia"): PIVOT_BORE_BAND,
}
# Every tight band or limit names its mate on the dimension it governs.  The
# chamfer reads ".012 MIN" over its angle; why it has a floor rides above it,
# clear of the extension lines below (draw_pn_pen_v_block's SECTION_KEEP).
# The reamed diameter's mate runs three short rows: its callout stands in the
# bottom view's corner, between the neck's depth dimensions and the title
# block (draw_pn_pen_v_block's BOTTOM_KEEP).
PEN_ROD_NUMBER = _config.parts("pn-pen-rod")["number"]
DIMENSION_CALLOUTS: dict[str, str] = {
    "PivotDia": f"REAM THRU\nSLIP FIT ON\nPEN ROD PIVOT\n{PEN_ROD_NUMBER}",
    "PivotChamferSize": "X 45°",
}
# One row: SolidWorks stores a line break in the above compartment but prints
# nothing of it, while the dimension line still runs under the unprinted text
# (farm 20261014T005925878Z: no rod callout, the chamfer's line out to the
# right border; draw_pd_transgear_pin ``_printable_above_callouts``).
DIMENSION_CALLOUTS_ABOVE: dict[str, str] = {
    "PivotChamferSize": f"CLEARS ROD {PEN_ROD_NUMBER} FILLET",
}
if any("\n" in text for text in DIMENSION_CALLOUTS_ABOVE.values()):
    raise AssertionError("an above-callout line break would not print")
# Both relief corners are one radius, both apex rounds one, and both flanks
# one angle to the bottom face; the printed one stands for the pair.  A
# custom radius prefix replaces SolidWorks' own "R", so it carries it
# (pn_pen_hanger_spec's slot corners).
DIMENSION_PREFIXES: dict[tuple[str, str], str] = {
    ("VGrooveProfile", "VFlankAngle"): "2X ",
    ("VApexFillets", "VApexFilletR"): "2X R",
    ("ReliefProfile", "ReliefCornerR"): "2X R",
}

# Material and finish ride the title block; nothing else needs saying.
DRAWING_NOTES = ""
# The pictorial runs 3:2: at 1:1 the 2.26 tap mouth and the reamed bore read as
# polygons (machinist review r5; pn_pen_frame_spec's 2:1 fix).  2:1 does not
# fit between section A-A and the title block (draw_pn_pen_v_block).
ISOMETRIC_VIEW_SCALE = (3, 2)
ISOMETRIC_VIEW_NOTE = (
    f"ISOMETRIC VIEW SCALE {ISOMETRIC_VIEW_SCALE[0]}:{ISOMETRIC_VIEW_SCALE[1]}"
)
