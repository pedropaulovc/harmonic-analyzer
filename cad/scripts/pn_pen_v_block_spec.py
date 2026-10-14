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

* The marker's grip (``vn_pen_marker_spec.BARREL_DIA``, a regular-size
  Sharpie Fine Point) seats in a 90 degree V-groove along the bottom of the
  neck, pressed up by the stirrup's thumb screw; the V centres the barrel
  whatever its diameter tolerance.
* The marker's larger silver body runs out through a flat-roofed RELIEF slot
  along the body, so only the grip touches the block.  The body is wider
  than the neck so both slot walls hold the rule 17 floor at the title
  block's .X band.
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

import _config
from _hole_spec import HoleSpec, TAP_DRILL_MM, THREAD_MAJOR_MM
from _printed_tolerance import angular_band_deg, printed_band_mm
import pn_pen_rod_spec as rod
import vn_pen_marker_spec as marker
import vn_pen_rod_set_screw_spec as rod_set_screw

# X, along the marker: the CG solve (pn_pen_carriage_geom) puts the carriage's
# plan CG 0.013 off the rod axis at 27.3, the .X step nearest it.
BLOCK_LENGTH = 27.3
BLOCK_HEIGHT = 18.0  # Y
# --- Depth (Z): neck and body, both centred on DEPTH_MID_Z ---
NECK_DEPTH = 18.0  # z 0..18: the stirrup's window passes it
BODY_SIDE_STEP = 2.1  # the body stands this proud of the neck each side
BODY_Z0 = -BODY_SIDE_STEP  # the body's front face: the depth datum
BODY_Z1 = NECK_DEPTH + BODY_SIDE_STEP
BODY_DEPTH = round(BODY_Z1 - BODY_Z0, 6)  # 22.2
DEPTH_MID_Z = NECK_DEPTH / 2.0  # the V, the relief and the pivot bore centre here


def depth_station(z: float) -> float:
    """A part-frame z as the print's station from the body's front face."""
    return round(z - BODY_Z0, 6)


# --- V-groove (grip seat), x 0..RELIEF_X0 ---
# The print defines the V by what seats the grip: its included angle and both
# mouth edges on the bottom face, each a baseline station from the body's
# front face (all three driving in VGrooveProfile).  The mouth width and the
# theoretical apex height follow from them.  The apex is not cut sharp
# (drawing-guidelines.md rule 16): a flat across it, V_FLAT_WIDTH wide
# (driving, .X), is the tip a 90 deg chamfer mill or a small end mill leaves.
# The flat's height is what the angle, the mouth and the width leave; it
# prints as a reference.
V_ANGLE_DEG = 90.0
V_MOUTH_Z0 = 3.0  # front mouth edge (part frame; prints 5.1 from the datum)
V_MOUTH_Z1 = 15.0  # back mouth edge (part frame; prints 17.1)
V_MOUTH_WIDTH = V_MOUTH_Z1 - V_MOUTH_Z0
_HALF = math.radians(V_ANGLE_DEG / 2.0)
V_APEX_Y = round(
    (V_MOUTH_WIDTH / 2.0) / math.tan(_HALF), 6
)  # 6.0: apex height above the bottom face, centred in Z
# A barrel of radius r in the V: axis r/sin(half-angle) below the apex, the two
# contact lines r*sin(half-angle) below it.
MARKER_AXIS_Y = V_APEX_Y - (marker.BARREL_DIA / 2.0) / math.sin(_HALF)
V_CONTACT_Y = V_APEX_Y - (marker.BARREL_DIA / 2.0) * math.sin(_HALF)
V_FLAT_WIDTH = 2.0
V_FLAT_Y = round(V_APEX_Y - (V_FLAT_WIDTH / 2.0) / math.tan(_HALF), 6)  # 5.0
# The groove's section: the V's triangle less the tip the flat leaves standing.
V_GROOVE_AREA = (
    V_APEX_Y * V_MOUTH_WIDTH / 2.0 - V_FLAT_WIDTH * (V_APEX_Y - V_FLAT_Y) / 2.0
)  # 35.0
# The flat meets each flank in an internal corner no cutter leaves sharp: each
# takes the tip radius of a chamfer mill or the corner of an end mill, up to
# V_APEX_FILLET_R.  It prints as the single limit "2X R0.5 MAX"; swTolMAX
# prints the nominal, so the model carries the limit (pn_pen_rod_spec's
# shoulder root).
V_APEX_FILLET_R = 0.5
V_APEX_FILLET_BAND = (0.0, -V_APEX_FILLET_R)
V_APEX_FILLET_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "2X R0.5 MAX"
V_APEX_FILLET_PLACES = 1
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
# grip's seat, is this long: 9 of the grip's 14.5.  The neck ends here too:
# the body's step faces stand in line with the slot's.
RELIEF_X0 = 9.0
RELIEF_Z0 = 1.0  # near (front) wall
RELIEF_Z1 = 17.0  # far (back) wall
RELIEF_WIDTH = RELIEF_Z1 - RELIEF_Z0
RELIEF_HEIGHT = 6.5
# The slot's two internal corners at the step (x = RELIEF_X0) keep the end
# mill's radius, a 2 mm cutter 6.5 deep.  Modelled as plan arcs in the slot
# profile, not a fillet feature.
RELIEF_CORNER_R = 1.0
# The V is cut on one corner radius past the step, to where the corner arcs
# end.  Past the step its whole section lies inside the slot's (guard below),
# so the extra run removes no brass; the step face never ends in a sliver
# under a flank (machinist review final2).
V_CUT_LENGTH = RELIEF_X0 + RELIEF_CORNER_R
if not (RELIEF_Z0 < V_MOUTH_Z0 and V_MOUTH_Z1 < RELIEF_Z1 and V_APEX_Y < RELIEF_HEIGHT):
    raise AssertionError("past the step the V must lie inside the relief slot")

# --- Pivot bore (rod's turned end): a sketched cut from the top face down
# into the relief slot, reamed to the band ---
PIVOT_BORE_DIA = 4.0  # reamed
PIVOT_BORE_BAND = (0.012, 0.0)  # H7
PIVOT_BORE_X = 12.5  # just past the step (guard below); the CG solve sets the length
# 45 deg chamfer on the bore's TOP edge, where the rod's square shoulder seats:
# it clears the rod's shoulder-root fillet (pn_pen_rod_spec.SHOULDER_FILLET_R
# MAX).  Printed as a native single MIN limit: the title block's .X band would
# let it shrink to nothing.
PIVOT_BORE_TOP_CHAMFER = 0.3
# (upper, lower): the nominal IS the MIN limit (lower 0); the upper, which a
# MIN print does not show, is the native record of what still leaves the
# rod's seat flats (guard below).
PIVOT_CHAMFER_BAND = (0.1, 0.0)
PIVOT_CHAMFER_TOL_TYPE = 5  # swTolType_e.swTolMIN: prints "0.3 MIN"
PIVOT_CHAMFER_PLACES = 1

# --- Rod set screw: #4-40 tapped from the body's front face into the pivot bore ---
SET_SCREW_TAP_SPEC = HoleSpec("tapped", rod_set_screw.THREAD, end="through_next")
SET_SCREW_Y = 12.0
SET_SCREW_TAP_LENGTH = round(
    DEPTH_MID_Z - BODY_Z0 - PIVOT_BORE_DIA / 2.0, 6
)  # 9.1: body front face to bore wall

_WALL = 1.5  # drawing-guidelines.md rule 17 (walls and webs) floor
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
if min(V_MOUTH_Z0, NECK_DEPTH - V_MOUTH_Z1) < 2.0:
    raise AssertionError("V-groove leaves under 2.0 lands on the bottom face")
if not 1.0 <= V_CONTACT_Y < V_FLAT_Y:
    raise AssertionError("grip contact lines must lie on the V flanks, under the flat")
if min(RELIEF_Z0 - BODY_Z0, BODY_Z1 - RELIEF_Z1) < 2.0:
    raise AssertionError("relief slot legs under the rule 17 2.0 target")
_BODY_R = marker.BODY_FRONT_DIA / 2.0
_BODY_HALF_CHORD_AT_BOTTOM = math.sqrt(_BODY_R**2 - MARKER_AXIS_Y**2)
if RELIEF_WIDTH / 2.0 - _BODY_HALF_CHORD_AT_BOTTOM < 0.25:
    raise AssertionError("relief slot does not pass the marker body")
if RELIEF_HEIGHT - (MARKER_AXIS_Y + _BODY_R) < 0.25 or RELIEF_HEIGHT <= V_APEX_Y:
    raise AssertionError("relief roof must clear the body and swallow the V apex")
if PIVOT_BORE_X - PIVOT_BORE_DIA / 2.0 <= RELIEF_X0:
    raise AssertionError("pivot bore must drop wholly into the relief slot")
if BLOCK_LENGTH - (PIVOT_BORE_X + PIVOT_BORE_DIA / 2.0) < 2.0:
    raise AssertionError("the free end leaves under 2.0 past the pivot bore")
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
if round(PIVOT_BORE_TOP_CHAMFER, PIVOT_CHAMFER_PLACES) != PIVOT_BORE_TOP_CHAMFER:
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
# The plan outline (OutlineProfile, Top plane) prints only the length, in the
# bottom view; the block's extrusion its height.  The V's sketch (Right plane,
# the paper end) carries construction stubs on the body's front face (the
# datum's foot) and on the neck's and the body's other faces, so the paper-end
# view, where the body's faces show beyond the neck's, prints the whole
# depth-wise stack from the datum in one baseline row: the neck's faces, the
# V's edges and the depth (the outline's own depth-wise dimensions, driven by
# the same globals, stay unprinted).
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
    "OutlineProfile": {"Length"},
    "Block": {"Height"},
    "VGrooveProfile": {
        "VAngle",
        "VFlatWidth",
        "VFlatY",
        "VMouthZ0",
        "VMouthZ1",
        "NeckZ0",
        "NeckZ1",
        "Depth",
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
# Places carry the title block's tolerance (drawing-guidelines.md rule 3),
# .X by default.  The V prints as its included angle (whole degrees, the
# title block's +/-1), its two mouth edges and its apex flat's width; the
# flat's height they leave is a reference, (5.0), driven in the sketch.  The
# flat's two rounds print their single limit, R0.5 MAX.  .XX,
# the title block's routine location row, where a mate needs it:
# * the tap's and the pivot bore's station from the paper end (SetScrewX,
#   PivotX): the tap must meet the bore it locks, and the bore must drop
#   wholly past the step (guard below);
# * the neck's two faces (NeckZ0, NeckZ1): the stirrup's window must pass
#   the neck at both parts' loosest limits (pn_pen_frame_spec), and the V
#   leaves its lands at the rule 17 floor between them.
# The pivot bore's depth station prints .X: no fit depends on it (the tap
# runs into the bore wherever it stands, and the set screw locks the pen's
# angle).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "OutlineProfile": {"Length": 1},
    "Block": {"Height": 1},
    "VGrooveProfile": {
        "VAngle": 0,
        "VFlatWidth": 1,
        "VFlatY": 1,
        "VMouthZ0": 1,
        "VMouthZ1": 1,
        "NeckZ0": 2,
        "NeckZ1": 2,
        "Depth": 1,
    },
    "VApexFillets": {"VApexFilletR": V_APEX_FILLET_PLACES},
    "ReliefProfile": {"ReliefX0": 1, "ReliefCornerR": 1},
    "ReliefReference": {"ReliefZ0": 1, "ReliefZ1": 1, "ReliefHeight": 1},
    "PivotBoreProfile": {"PivotX": 2, "PivotDia": 3},
    "PivotReference": {"PivotZ": 1, "PivotChamferSize": PIVOT_CHAMFER_PLACES},
    "SetScrewHole": {"SetScrewX": 2, "SetScrewY": 1},
}
# The one driven sketch dimension the print shows, parenthesised as a
# reference (no tolerance): the apex flat's height, which the V's angle, mouth
# edges and flat width fix.
REFERENCE_DIMENSIONS: tuple[tuple[str, str], ...] = (("VGrooveProfile", "VFlatY"),)
if round(V_FLAT_Y, DRAWING_PRECISION["VGrooveProfile"]["VFlatY"]) != V_FLAT_Y:
    raise AssertionError("the V flat's reference height must print exactly")
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


def _band(name: str) -> float:
    """The title-block +/- the named dimension prints at."""
    return printed_band_mm(DRAWING_PRECISION_BY_NAME[name])


# --- Printed worst case (every band at its limit at once) ---
# Every station across the depth is a baseline from the body's front face, so
# no band adds through another edge.  Rule 17: the near wall is ReliefZ0
# itself, the far wall Depth - ReliefZ1; the V's lands lie between a neck
# face and a mouth edge.
RELIEF_NEAR_WALL_PRINTED_MIN = depth_station(RELIEF_Z0) - _band("ReliefZ0")  # 2.3
RELIEF_FAR_WALL_PRINTED_MIN = (BODY_DEPTH - _band("Depth")) - (
    depth_station(RELIEF_Z1) + _band("ReliefZ1")
)  # 1.5
V_NEAR_LAND_PRINTED_MIN = (depth_station(V_MOUTH_Z0) - _band("VMouthZ0")) - (
    depth_station(0.0) + _band("NeckZ0")
)  # 1.69
V_FAR_LAND_PRINTED_MIN = (depth_station(NECK_DEPTH) - _band("NeckZ1")) - (
    depth_station(V_MOUTH_Z1) + _band("VMouthZ1")
)  # 1.69
# The far wall is the floor exactly, a few ulps under it in floats; compare at
# the micron.
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
    < _WALL
):
    raise AssertionError("a printed wall or land falls under the rule 17 1.5 floor")
# The widest neck the print allows, for the stirrup's window.
NECK_WIDTH_PRINTED_MAX = NECK_DEPTH + _band("NeckZ0") + _band("NeckZ1")  # 19.02
# The pivot bore must leave the brass wholly into the slot: its paper-side
# edge (station and reamed diameter at their limits) stays past the step at
# its far limit, or the ream breaks into the step wall in a crescent.
PIVOT_BORE_STEP_CLEARANCE_PRINTED_MIN = (
    PIVOT_BORE_X
    - _band("PivotX")
    - (PIVOT_BORE_DIA + PIVOT_BORE_BAND[0]) / 2.0
    - (RELIEF_X0 + _band("ReliefX0"))
)  # 0.18
if PIVOT_BORE_STEP_CLEARANCE_PRINTED_MIN < 0.0:
    raise AssertionError("at its printed limits the pivot bore breaks the step wall")


def _body_half_chord_at_bottom(angle_deg: float, mouth: float) -> float:
    """The marker body's half-width at the bottom face, its grip seated in a
    V of this included angle and mouth (both flanks touching the grip)."""
    half = math.radians(angle_deg / 2.0)
    apex_y = (mouth / 2.0) / math.tan(half)
    axis_y = apex_y - (marker.BARREL_DIA / 2.0) / math.sin(half)
    return math.sqrt(_BODY_R**2 - axis_y**2)


# The V's centre (the body's) is the mean of its two edge stations, +/- the
# mean of their bands; its mouth is their difference, +/- the sum.  Taken as
# independent (a bound: one edge cannot both widen the mouth and pull the
# centre toward the wall it does not move), the widest body chord at the
# bottom face is over the printed angle (the title block's +/-1 deg) and that
# mouth band: 6.116 at 89 deg and the widest mouth, 5.965 nominal.  The flat's
# height is their reference and adds no band of its own.
V_CENTRE_BAND = (_band("VMouthZ0") + _band("VMouthZ1")) / 2.0
V_MOUTH_BAND = _band("VMouthZ0") + _band("VMouthZ1")
BODY_HALF_CHORD_PRINTED_MAX = max(
    _body_half_chord_at_bottom(V_ANGLE_DEG + angle, V_MOUTH_WIDTH + mouth)
    for angle in (-angular_band_deg(), angular_band_deg())
    for mouth in (-V_MOUTH_BAND, V_MOUTH_BAND)
)
_V_CENTRE_STATION = depth_station((V_MOUTH_Z0 + V_MOUTH_Z1) / 2.0)
BODY_NEAR_CLEARANCE_PRINTED_MIN = (
    (_V_CENTRE_STATION - V_CENTRE_BAND)
    - BODY_HALF_CHORD_PRINTED_MAX
    - (depth_station(RELIEF_Z0) + _band("ReliefZ0"))
)  # 0.28
BODY_FAR_CLEARANCE_PRINTED_MIN = (
    (depth_station(RELIEF_Z1) - _band("ReliefZ1"))
    - (_V_CENTRE_STATION + V_CENTRE_BAND)
    - BODY_HALF_CHORD_PRINTED_MAX
)  # 0.28
if min(BODY_NEAR_CLEARANCE_PRINTED_MIN, BODY_FAR_CLEARANCE_PRINTED_MIN) <= 0.0:
    raise AssertionError("a printed relief wall may touch the marker body")


def _flat_grip_clearance(angle_deg: float, flat_width: float) -> float:
    """The flat's height over the seated grip's top: both hang from the V's
    theoretical apex, so the mouth does not enter."""
    half = math.radians(angle_deg / 2.0)
    grip_top_under_apex = _GRIP_R / math.sin(half) - _GRIP_R
    return grip_top_under_apex - (flat_width / 2.0) / math.tan(half)


# The grip seats on the flanks, never on the flat: at the widest flat and
# either printed angle it stays 0.75 under it (1.20 nominal); at the
# narrowest the flat is still 1.2 wide.
V_FLAT_GRIP_CLEARANCE_PRINTED_MIN = min(
    _flat_grip_clearance(V_ANGLE_DEG + angle, V_FLAT_WIDTH + _band("VFlatWidth"))
    for angle in (-angular_band_deg(), angular_band_deg())
)  # 0.75
if V_FLAT_GRIP_CLEARANCE_PRINTED_MIN < 0.25:
    raise AssertionError("at its printed limits the apex flat may touch the grip")
if V_FLAT_WIDTH - _band("VFlatWidth") <= 0.0:
    raise AssertionError("at its printed limits the apex flat vanishes")


def _apex_fillet_grip_clearance(
    angle_deg: float, flat_width: float, radius: float
) -> float:
    """The seated grip's clearance to one flat/flank round.  The round's arc
    faces its corner, away from the grip's axis below it, so its nearest point
    is a tangent point: on the flat or on the flank.  Frame: the theoretical
    apex at the origin, the V's axis along y."""
    half = math.radians(angle_deg / 2.0)
    tangent = radius * math.tan((math.pi / 2.0 - half) / 2.0)
    corner = (flat_width / 2.0, -(flat_width / 2.0) / math.tan(half))
    axis_y = -_GRIP_R / math.sin(half)
    on_flat = (corner[0] - tangent, corner[1])
    on_flank = (
        corner[0] + tangent * math.sin(half),
        corner[1] - tangent * math.cos(half),
    )
    return min(math.hypot(x, y - axis_y) for x, y in (on_flat, on_flank)) - _GRIP_R


# The rounds at their MAX, at either printed flat width and angle: the grip
# clears them by 0.81 (the widest flat, the widest angle), and the narrowest
# flat still runs straight between them.
_APEX_FILLET_LIMITS = [
    (V_ANGLE_DEG + angle, V_FLAT_WIDTH + width)
    for angle in (-angular_band_deg(), angular_band_deg())
    for width in (-_band("VFlatWidth"), _band("VFlatWidth"))
]
V_APEX_FILLET_GRIP_CLEARANCE_PRINTED_MIN = min(
    _apex_fillet_grip_clearance(angle, width, V_APEX_FILLET_R)
    for angle, width in _APEX_FILLET_LIMITS
)  # 0.81
if V_APEX_FILLET_GRIP_CLEARANCE_PRINTED_MIN < 0.25:
    raise AssertionError("at its printed limits an apex round may touch the grip")
if any(
    2.0 * V_APEX_FILLET_R * math.tan((math.pi / 2.0 - math.radians(angle / 2.0)) / 2.0)
    >= width
    for angle, width in _APEX_FILLET_LIMITS
):
    raise AssertionError("at its printed limits the apex rounds meet across the flat")
# (feature, dimension) -> (upper, lower) native band.
DRAWING_BANDS: dict[tuple[str, str], tuple[float, float]] = {
    ("PivotBoreProfile", "PivotDia"): PIVOT_BORE_BAND,
}
# Every tight band or limit names its mate on the dimension it governs.  The
# chamfer reads "0.3 MIN" over its angle; why it has a floor rides above it,
# clear of the extension lines below (draw_pn_pen_v_block's SECTION_KEEP).
PEN_ROD_NUMBER = _config.parts("pn-pen-rod")["number"]
DIMENSION_CALLOUTS: dict[str, str] = {
    "PivotDia": f"REAM THRU\nSLIP FIT ON PEN ROD PIVOT {PEN_ROD_NUMBER}",
    "PivotChamferSize": "X 45 DEG",
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
# Both relief corners are one radius, and both apex rounds one; the printed
# one stands for the pair.  A custom prefix replaces SolidWorks' own radius
# "R", so it carries it (pn_pen_hanger_spec's slot corners).
DIMENSION_PREFIXES: dict[tuple[str, str], str] = {
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
