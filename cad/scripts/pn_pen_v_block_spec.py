r"""Pen v-block dimensional contract -- the single source of truth shared by the
part build (``build_pn_pen_v_block.py``), its drawing (``draw_pn_pen_v_block.py``)
and the carriage layout/balance (``pn_pen_carriage_geom``).

PURE DATA, no SolidWorks/COM imports.

Part frame: length X 0..BLOCK_LENGTH (x 0 = the PAPER end face), height Y
0..BLOCK_HEIGHT (y 0 = the bottom face), depth Z 0..BLOCK_DEPTH (z 0 = the
FRONT face, away from the paper; the set screw enters there).

Re-derived from the engineerguy 4/4 video (9:15-10:34) and the 2026-10 design
brief (``balance_options.png`` panel C):

* The Sharpie Mini's grip (``vn_pen_marker_spec.BARREL_DIA``) seats in a 90
  degree V-groove along the bottom of the paper-end section, pressed up by the
  stirrup's thumb screw; the V centres the barrel whatever its diameter tolerance.
* The marker's larger silver body runs out through a flat-roofed RELIEF slot
  over the rest of the length, so only the grip touches the block.
* The rod's turned pivot end drops into a reamed pivot bore near mid-block; the
  rod's square shoulder rests on the block top, and a #4-40 set screw from the
  front face locks the pen's angle to the paper (book: "a small set screw that
  adjusts the angle of the pen").
* A through lightening bore at the free end (the photo's open hole) trims the
  carriage CG onto the rod axis (``pn_pen_carriage_geom`` solves and asserts).

Drawing contract: the pivot bore is a sketched, reamed cut (its toleranced
diameter is a marked sketch dimension, banded to the rod pivot); the set-screw
tap and the lightening bore are Hole Wizard features whose sizes print as native
hole callouts and whose stations print as their marked placement dimensions.
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
from _hole_spec import FRACTIONAL_DRILL_MM, HoleSpec, TAP_DRILL_MM, THREAD_MAJOR_MM
from _printed_tolerance import angular_band_deg, printed_band_mm
import pn_pen_rod_spec as rod
import vn_pen_marker_spec as marker
import vn_pen_rod_set_screw_spec as rod_set_screw

BLOCK_LENGTH = 36.0  # X, along the marker (t00612: ~2.2x the end face)
BLOCK_HEIGHT = 18.0  # Y
BLOCK_DEPTH = 18.0  # Z: the relief slot passes the Ø12.3 body with 2.5 legs
CHAMFER = 6.0  # 45 deg top corners (the photo's bevelled top edges)

# --- V-groove (grip seat), x 0..RELIEF_X0 ---
# The print defines the V by what seats the grip: its included angle and both
# mouth edges on the bottom face, each a baseline station from the front face
# (all three driving in VGrooveProfile).  The mouth width and the apex height
# follow from them; the apex height prints as a reference.
V_ANGLE_DEG = 90.0
V_MOUTH_Z0 = 3.0  # front mouth edge from the front face
V_MOUTH_Z1 = 15.0  # back mouth edge from the front face
V_MOUTH_WIDTH = V_MOUTH_Z1 - V_MOUTH_Z0
_HALF = math.radians(V_ANGLE_DEG / 2.0)
V_APEX_Y = round(
    (V_MOUTH_WIDTH / 2.0) / math.tan(_HALF), 6
)  # 6.0: apex height above the bottom face, centred in Z
# A barrel of radius r in the V: axis r/sin(half-angle) below the apex, the two
# contact lines r*sin(half-angle) below it.
MARKER_AXIS_Y = V_APEX_Y - (marker.BARREL_DIA / 2.0) / math.sin(_HALF)
V_CONTACT_Y = V_APEX_Y - (marker.BARREL_DIA / 2.0) * math.sin(_HALF)

# --- Relief slot (body clearance), x RELIEF_X0..BLOCK_LENGTH ---
RELIEF_X0 = 10.0
# Both walls are baseline stations from the front face; the width follows.
RELIEF_Z0 = 2.5  # near (front) wall
RELIEF_Z1 = 15.5  # far (back) wall
RELIEF_WIDTH = RELIEF_Z1 - RELIEF_Z0
RELIEF_HEIGHT = 6.5
# The slot's two internal corners at the step (x = RELIEF_X0) keep the end
# mill's radius: the largest the grip allows (guard below), a 2 mm cutter
# 6.5 deep.  Modelled as plan arcs in the slot profile, not a fillet feature:
# at the bottom face the step is only (V mouth - relief) / 2 = 0.5 wide beside
# the V, so a rolling-ball fillet would run off it.
RELIEF_CORNER_R = 1.0
# The V is cut on one corner radius past the step, to where the corner arcs
# end.  Past the step its whole section lies inside the slot's (guard below),
# so it removes only what each corner arc leaves under a flank: stopped at
# the step, the cut left a knife edge there, 0.13 thick at most and 0.5 tall
# (machinist review final2: a closed triangle at each mouth lip in the
# paper-end view), a web far under the rule 17 floor.
V_CUT_LENGTH = RELIEF_X0 + RELIEF_CORNER_R
if not (RELIEF_Z0 < V_MOUTH_Z0 and V_MOUTH_Z1 < RELIEF_Z1 and V_APEX_Y < RELIEF_HEIGHT):
    raise AssertionError("past the step the V must lie inside the relief slot")

# --- Pivot bore (rod's turned end): a sketched cut from the top face down
# into the relief slot, reamed to the band ---
PIVOT_BORE_DIA = 4.0  # reamed
PIVOT_BORE_BAND = (0.012, 0.0)  # H7
PIVOT_BORE_X = 12.5  # chosen with LIGHTENING_X by the CG solve (pn_pen_carriage_geom)
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

# --- Rod set screw: #4-40 tapped from the front face into the pivot bore ---
SET_SCREW_TAP_SPEC = HoleSpec("tapped", rod_set_screw.THREAD, end="through_next")
SET_SCREW_Y = 12.0
SET_SCREW_TAP_LENGTH = (
    BLOCK_DEPTH / 2.0 - PIVOT_BORE_DIA / 2.0
)  # front face to bore wall

# --- Free-end lightening bore: 5/16 drill through into the relief slot ---
LIGHTENING_SPEC = HoleSpec("drilled_fractional", "5/16", end="through_all")
LIGHTENING_DIA = FRACTIONAL_DRILL_MM[LIGHTENING_SPEC.size]
LIGHTENING_X = 23.0

_WALL = 1.5  # drawing-guidelines.md rule 17 (walls and webs) floor
# The carriage hangs the marker on the block's mid-depth: the V and the relief
# both centre on it (pn_pen_carriage_geom, its mass model).
if (V_MOUTH_Z0 + V_MOUTH_Z1) / 2.0 != BLOCK_DEPTH / 2.0:
    raise AssertionError("the V's mouth edges must centre on the block's depth")
if (RELIEF_Z0 + RELIEF_Z1) / 2.0 != BLOCK_DEPTH / 2.0:
    raise AssertionError("the relief's walls must centre on the block's depth")
if min(V_MOUTH_Z0, BLOCK_DEPTH - V_MOUTH_Z1) < 2.0:
    raise AssertionError("V-groove leaves under 2.0 lands on the bottom face")
if not 1.0 <= V_CONTACT_Y < V_APEX_Y:
    raise AssertionError("grip contact lines must lie inside the V flanks")
if min(RELIEF_Z0, BLOCK_DEPTH - RELIEF_Z1) < 2.0:
    raise AssertionError("relief slot legs under the rule 17 2.0 target")
_BODY_R = marker.BODY_FRONT_DIA / 2.0
_BODY_HALF_CHORD_AT_BOTTOM = math.sqrt(_BODY_R**2 - MARKER_AXIS_Y**2)
if RELIEF_WIDTH / 2.0 - _BODY_HALF_CHORD_AT_BOTTOM < 0.25:
    raise AssertionError("relief slot does not pass the marker body")
if RELIEF_HEIGHT - (MARKER_AXIS_Y + _BODY_R) < 0.25 or RELIEF_HEIGHT <= V_APEX_Y:
    raise AssertionError("relief roof must clear the body and swallow the V apex")
if PIVOT_BORE_X - PIVOT_BORE_DIA / 2.0 <= RELIEF_X0:
    raise AssertionError("pivot bore must drop wholly into the relief slot")
if SET_SCREW_TAP_LENGTH < 1.5 * THREAD_MAJOR_MM[rod_set_screw.THREAD]:
    raise AssertionError(
        "rod set-screw tap is under drawing-guidelines.md rule 18 (1.5 D)"
    )
if rod_set_screw.LENGTH > SET_SCREW_TAP_LENGTH:
    raise AssertionError("rod set screw stands proud of the front face")
if BLOCK_HEIGHT - SET_SCREW_Y - TAP_DRILL_MM[rod_set_screw.THREAD] / 2.0 < _WALL:
    raise AssertionError("rod set-screw tap breaks the block top")
if LIGHTENING_X - LIGHTENING_DIA / 2.0 - (PIVOT_BORE_X + PIVOT_BORE_DIA / 2.0) < _WALL:
    raise AssertionError("lightening bore runs into the pivot bore")
# Free-end chamfer plane x + y = BLOCK_LENGTH + BLOCK_HEIGHT - CHAMFER.
if (
    BLOCK_LENGTH
    + BLOCK_HEIGHT
    - CHAMFER
    - BLOCK_HEIGHT
    - (LIGHTENING_X + LIGHTENING_DIA / 2.0)
) / math.sqrt(2.0) < _WALL:
    raise AssertionError("lightening bore breaks the free-end chamfer")
if (
    LIGHTENING_X - LIGHTENING_DIA / 2.0 <= RELIEF_X0
    or LIGHTENING_DIA > RELIEF_WIDTH - 2.0 * _WALL
):
    raise AssertionError("lightening bore must open wholly into the relief slot")
# The relief corners stand RELIEF_CORNER_R into the slot from each wall at the
# step.  The grip seats in the V and may run on past the step (the carriage
# places it 1.5 past); it is widest in the slot at the bottom face (its axis
# is below the block), so the corner must stand clear of it there wherever it
# ends.  The body (wider) must start past x = RELIEF_X0 + RELIEF_CORNER_R; the
# carriage layout owns where it starts.
_GRIP_R = marker.BARREL_DIA / 2.0
_GRIP_GAP_AT_BOTTOM = (
    BLOCK_DEPTH / 2.0 - math.sqrt(_GRIP_R**2 - MARKER_AXIS_Y**2) - RELIEF_Z0
)
if _GRIP_GAP_AT_BOTTOM - RELIEF_CORNER_R < 0.25:
    raise AssertionError("relief corner radius reaches the marker grip")
if RELIEF_Z0 + RELIEF_CORNER_R >= (BLOCK_DEPTH - PIVOT_BORE_DIA) / 2.0 - _WALL:
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
# enforces ``union(marks) == union(keeps)``. The set-screw tap and lightening
# bore are Hole Wizard features: their sizes print as native hole callouts,
# their stations as the marked placement dimensions (SetScrewX repeats the
# pivot station on the face the tap is drilled from).  The V's length prints as
# the relief's start station (ReliefX0, the same "ReliefX0" global): the V
# runs into the slot (V_CUT_LENGTH), so the step is where its brass ends, and
# the V-groove cut's own depth dimension would hang in the slot's air.  Every
# feature is located across the depth from the FRONT face (z 0), never by the
# depth's symmetry, and the V and
# the relief by both their edges as baselines from it (VMouthZ0 / VMouthZ1,
# ReliefZ0 / ReliefZ1): no edge is chained from another.  Three features' own
# depth stations would print off real geometry, so hidden reference sketches
# own those values instead.
# Section A-A shows the relief and the pivot bore across the depth, but their
# sketches lie in the Top plane and project edge-on there.  ReliefReference
# and PivotReference lie IN section A-A's cutting plane (x = PIVOT_BORE_X,
# the bond cradle's recipe), each chord on an edge the section draws:
# ReliefReference runs both relief walls from the bottom face to the roof
# (ReliefHeight on the far wall, which section A-A draws on its right, outside
# the stations under it; the Relief cut's own depth vector stops in air), the
# near foot (ReliefZ0) and the far foot (ReliefZ1), each from the front face's
# foot; PivotReference holds stubs down the front face and the
# bore axis from the top face (PivotZ between their tops) and the bore's top
# chamfer leg on the far (z 11) side: the chamfer feature's own dimension may
# attach on the near side, under PivotZ.  The lightening bore's placement
# dimension runs to the paper-end corner, whose extension line would lie along
# the bottom view's whole front edge; LighteningReference (Top plane) runs up
# the free end's edge from its front corner (LighteningZ) and along the bore's
# centreline to its centre.  All three are saved hidden; the drawing shows each
# in the view that dimensions it (``_drawing_hidden_sketches``), the section's
# two while the part shows them at the cut. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "OutlineProfile": {"Length", "Height", "Chamfer2dx"},
    "Block": {"Depth"},
    "VGrooveProfile": {"VAngle", "VApexY", "VMouthZ0", "VMouthZ1"},
    "ReliefProfile": {"ReliefX0", "ReliefCornerR"},
    "ReliefReference": {"ReliefZ0", "ReliefZ1", "ReliefHeight"},
    "PivotBoreProfile": {"PivotX", "PivotDia"},
    "PivotReference": {"PivotZ", "PivotChamferSize"},
    "SetScrewHole": {"SetScrewX", "SetScrewY"},
    "LighteningBore": {"LighteningX"},
    "LighteningReference": {"LighteningZ"},
}
REFERENCE_SKETCHES = ("ReliefReference", "PivotReference", "LighteningReference")
SECTION_REFERENCE_SKETCHES = ("ReliefReference", "PivotReference")
# Places carry the title block's tolerance (drawing-guidelines.md rule 3).
# The V prints as its included angle (whole degrees, the title block's +/-1)
# and its two mouth edges; the apex height they leave is a reference, (6.0),
# driven in the sketch.  .XX on the tap's station from the paper end: it must
# meet the pivot bore it locks (PivotX, SetScrewX).  The pivot bore's depth
# station prints .X: no fit depends on it (the tap runs into the bore wherever
# it stands, and the set screw locks the pen's angle).  .XXX (+/-0.13) on the
# four baseline stations that keep the marker body off both relief walls: the
# V's two mouth edges (whose mean is the body's centre and whose difference is
# the mouth that sets the body's height) and the relief's two walls; at .XX
# the body clearance goes negative (guarded below).  The depth prints .X: the
# far relief wall is Depth - ReliefZ1 alone, 1.57 at its worst.
# Named exception: MHA-PN-005 pn-pen-v-block, the four .XXX baseline stations
# across the depth (drawing-simplicity-policy.md, Named exceptions).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "OutlineProfile": {"Length": 1, "Height": 1, "Chamfer2dx": 1},
    "Block": {"Depth": 1},
    "VGrooveProfile": {"VAngle": 0, "VApexY": 1, "VMouthZ0": 3, "VMouthZ1": 3},
    "ReliefProfile": {"ReliefX0": 1, "ReliefCornerR": 1},
    "ReliefReference": {"ReliefZ0": 3, "ReliefZ1": 3, "ReliefHeight": 1},
    "PivotBoreProfile": {"PivotX": 2, "PivotDia": 3},
    "PivotReference": {"PivotZ": 1, "PivotChamferSize": PIVOT_CHAMFER_PLACES},
    "SetScrewHole": {"SetScrewX": 2, "SetScrewY": 1},
    "LighteningBore": {"LighteningX": 1},
    "LighteningReference": {"LighteningZ": 1},
}
# The one driven sketch dimension the print shows, parenthesised as a
# reference (no tolerance): the V's apex height, which its angle and mouth
# edges fix.
REFERENCE_DIMENSIONS: tuple[tuple[str, str], ...] = (("VGrooveProfile", "VApexY"),)
if round(V_APEX_Y, DRAWING_PRECISION["VGrooveProfile"]["VApexY"]) != V_APEX_Y:
    raise AssertionError("the V's reference apex height must print exactly")
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
# Every station across the depth is a baseline from the front face, so no band
# adds through another edge.  Rule 17: the near wall is ReliefZ0 itself, the
# far wall Depth - ReliefZ1.
RELIEF_NEAR_WALL_PRINTED_MIN = RELIEF_Z0 - _band("ReliefZ0")  # 2.37
RELIEF_FAR_WALL_PRINTED_MIN = (BLOCK_DEPTH - _band("Depth")) - (
    RELIEF_Z1 + _band("ReliefZ1")
)  # 1.57 with the depth at .X
if min(RELIEF_NEAR_WALL_PRINTED_MIN, RELIEF_FAR_WALL_PRINTED_MIN) < _WALL:
    raise AssertionError("a printed relief wall falls under the rule 17 1.5 floor")


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
# mouth band: 6.006 at 89 deg and the widest mouth, 5.965 nominal.  The apex
# height is their reference and adds no band of its own.
V_CENTRE_BAND = (_band("VMouthZ0") + _band("VMouthZ1")) / 2.0
V_MOUTH_BAND = _band("VMouthZ0") + _band("VMouthZ1")
BODY_HALF_CHORD_PRINTED_MAX = max(
    _body_half_chord_at_bottom(V_ANGLE_DEG + angle, V_MOUTH_WIDTH + mouth)
    for angle in (-angular_band_deg(), angular_band_deg())
    for mouth in (-V_MOUTH_BAND, V_MOUTH_BAND)
)
_V_CENTRE_Z = (V_MOUTH_Z0 + V_MOUTH_Z1) / 2.0
BODY_NEAR_CLEARANCE_PRINTED_MIN = (
    (_V_CENTRE_Z - V_CENTRE_BAND)
    - BODY_HALF_CHORD_PRINTED_MAX
    - (RELIEF_Z0 + _band("ReliefZ0"))
)  # 0.23
BODY_FAR_CLEARANCE_PRINTED_MIN = (
    (RELIEF_Z1 - _band("ReliefZ1"))
    - (_V_CENTRE_Z + V_CENTRE_BAND)
    - BODY_HALF_CHORD_PRINTED_MAX
)  # 0.23
if min(BODY_NEAR_CLEARANCE_PRINTED_MIN, BODY_FAR_CLEARANCE_PRINTED_MIN) <= 0.0:
    raise AssertionError("a printed relief wall may touch the marker body")
# (feature, dimension) -> (upper, lower) native band.
DRAWING_BANDS: dict[tuple[str, str], tuple[float, float]] = {
    ("PivotBoreProfile", "PivotDia"): PIVOT_BORE_BAND,
}
# Every tight band or limit names its mate on the dimension it governs.  The
# chamfer reads "0.3 MIN" over its angle; why it has a floor rides above it,
# clear of the extension lines below (draw_pn_pen_v_block's SECTION_KEEP).
PEN_ROD_NUMBER = _config.parts("pn-pen-rod")["number"]
MARKER_NUMBER = _config.parts("vn-pen-marker")["number"]
# Named exception: MHA-PN-005 pn-pen-v-block, the four .XXX baseline stations
# across the depth (drawing-simplicity-policy.md, Named exceptions).  Each
# states its function under its value: taken to .XX alone, a relief wall's
# station lets the body touch it (and ReliefZ1 takes the far wall under the
# floor), a V edge's leaves 0.005 (the body clearance stack above).  The V's
# two edges centre the marker's grip, the outer one naming it (the body runs
# on into the relief); the relief's two clear its body, the outer one naming
# it.  Rows stay short enough to sit beside the view or between extension
# lines they do not cross (draw_pn_pen_v_block's RIGHT_KEEP / SECTION_KEEP).
DIMENSION_CALLOUTS: dict[str, str] = {
    "PivotDia": f"REAM THRU\nSLIP FIT ON PEN ROD PIVOT {PEN_ROD_NUMBER}",
    "Chamfer2dx": "X 45 DEG, 2 PLACES",
    "PivotChamferSize": "X 45 DEG",
    "VMouthZ0": "CENTRES\nGRIP",
    "VMouthZ1": f"CENTRES\nMARKER GRIP\n{MARKER_NUMBER}",
    "ReliefZ0": "CLEARS\nMARKER BODY",
    "ReliefZ1": f"CLEARS MARKER\nBODY {MARKER_NUMBER}",
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
# Both relief corners are one radius; the printed one stands for the pair.  A
# custom prefix replaces SolidWorks' own radius "R", so it carries it
# (pn_pen_hanger_spec's slot corners).
DIMENSION_PREFIXES: dict[tuple[str, str], str] = {
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
