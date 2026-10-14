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
from _printed_tolerance import printed_band_mm
import pn_pen_rod_spec as rod
import vn_pen_marker_spec as marker
import vn_pen_rod_set_screw_spec as rod_set_screw

BLOCK_LENGTH = 36.0  # X, along the marker (t00612: ~2.2x the end face)
BLOCK_HEIGHT = 18.0  # Y
BLOCK_DEPTH = 18.0  # Z: the relief slot passes the Ø12.3 body with 2.5 legs
CHAMFER = 6.0  # 45 deg top corners (the photo's bevelled top edges)

# --- V-groove (grip seat), x 0..RELIEF_X0 ---
V_ANGLE_DEG = 90.0
V_APEX_Y = 6.0  # apex height above the bottom face, centred in Z
V_MOUTH_WIDTH = round(
    2.0 * V_APEX_Y * math.tan(math.radians(V_ANGLE_DEG / 2.0)), 6
)  # 12.0
# A barrel of radius r in the V: axis r/sin(half-angle) below the apex, the two
# contact lines r*sin(half-angle) below it.
_HALF = math.radians(V_ANGLE_DEG / 2.0)
MARKER_AXIS_Y = V_APEX_Y - (marker.BARREL_DIA / 2.0) / math.sin(_HALF)
V_CONTACT_Y = V_APEX_Y - (marker.BARREL_DIA / 2.0) * math.sin(_HALF)

# --- Relief slot (body clearance), x RELIEF_X0..BLOCK_LENGTH ---
RELIEF_X0 = 10.0
RELIEF_WIDTH = 13.0
RELIEF_HEIGHT = 6.5
# The slot's two internal corners at the step (x = RELIEF_X0) keep the end
# mill's radius: the largest the grip allows (guard below), a 2 mm cutter
# 6.5 deep.  Modelled as plan arcs in the slot profile, not a fillet feature:
# at the bottom face the step is only (V mouth - relief) / 2 = 0.5 wide beside
# the V, so a rolling-ball fillet would run off it.
RELIEF_CORNER_R = 1.0

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
if V_MOUTH_WIDTH + 2.0 * 2.0 > BLOCK_DEPTH:
    raise AssertionError("V-groove leaves under 2.0 lands on the bottom face")
if not 1.0 <= V_CONTACT_Y < V_APEX_Y:
    raise AssertionError("grip contact lines must lie inside the V flanks")
if (BLOCK_DEPTH - RELIEF_WIDTH) / 2.0 < 2.0:
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
    BLOCK_DEPTH / 2.0
    - math.sqrt(_GRIP_R**2 - MARKER_AXIS_Y**2)
    - (BLOCK_DEPTH - RELIEF_WIDTH) / 2.0
)
if _GRIP_GAP_AT_BOTTOM - RELIEF_CORNER_R < 0.25:
    raise AssertionError("relief corner radius reaches the marker grip")
if (BLOCK_DEPTH - RELIEF_WIDTH) / 2.0 + RELIEF_CORNER_R >= (
    BLOCK_DEPTH - PIVOT_BORE_DIA
) / 2.0 - _WALL:
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
# the relief's start station (ReliefX0, the same "ReliefX0" global): the
# V-groove cut's own depth dimension projects off the paper end in the bottom
# view, away from the brass it measures.  Every feature is located across the
# depth from the FRONT face (z 0), never by the depth's symmetry: the V by its
# front mouth edge (VMouthZ).  Three features' own depth stations would print
# off real geometry, so hidden reference sketches own those values instead.
# Section A-A shows the relief and the pivot bore across the depth, but their
# sketches lie in the Top plane and project edge-on there.  ReliefReference
# and PivotReference lie IN section A-A's cutting plane (x = PIVOT_BORE_X,
# the bond cradle's recipe), each chord on an edge the section draws:
# ReliefReference runs both relief walls from the bottom face to the roof
# (ReliefHeight on the far wall, which section A-A draws on its right, outside
# the chain under it; the Relief cut's own depth vector stops in air), the
# near foot from the front face's foot (ReliefZ0) and the far foot from the
# near one (ReliefWidth); PivotReference holds stubs down the front face and the
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
    "VGrooveProfile": {"VApexY", "VMouth", "VMouthZ"},
    "ReliefProfile": {"ReliefX0", "ReliefCornerR"},
    "ReliefReference": {"ReliefZ0", "ReliefWidth", "ReliefHeight"},
    "PivotBoreProfile": {"PivotX", "PivotDia"},
    "PivotReference": {"PivotZ", "PivotChamferSize"},
    "SetScrewHole": {"SetScrewX", "SetScrewY"},
    "LighteningBore": {"LighteningX"},
    "LighteningReference": {"LighteningZ"},
}
REFERENCE_SKETCHES = ("ReliefReference", "PivotReference", "LighteningReference")
SECTION_REFERENCE_SKETCHES = ("ReliefReference", "PivotReference")
# Places carry the title block's tolerance (drawing-guidelines.md rule 3).
# .XX where a fit depends on it: the V's apex sets the marker axis, the pivot
# bore's depth station sits it on the V's axis, and the tap must meet the bore
# it locks (both stations from the paper end).  .XXX (+/-0.13) on the four
# across-the-depth stations that keep the marker body off both relief walls:
# the V's front mouth edge and mouth (the body's centre) and the relief's near
# wall and width; at .XX their bands alone (4 x 0.51) exceed the 0.53-a-side
# nominal clearance (guarded below).  The depth at .XX: at .X the far relief
# wall, left over from Depth - ReliefZ0 - ReliefWidth, falls under rule 17's
# 1.5 (guarded below); the depth is fixed by the frame window the block passes
# and the slot by the body, so geometry cannot buy the wall.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "OutlineProfile": {"Length": 1, "Height": 1, "Chamfer2dx": 1},
    "Block": {"Depth": 2},
    "VGrooveProfile": {"VApexY": 2, "VMouth": 3, "VMouthZ": 3},
    "ReliefProfile": {"ReliefX0": 1, "ReliefCornerR": 1},
    "ReliefReference": {"ReliefZ0": 3, "ReliefWidth": 3, "ReliefHeight": 1},
    "PivotBoreProfile": {"PivotX": 2, "PivotDia": 3},
    "PivotReference": {"PivotZ": 2, "PivotChamferSize": PIVOT_CHAMFER_PLACES},
    "SetScrewHole": {"SetScrewX": 2, "SetScrewY": 1},
    "LighteningBore": {"LighteningX": 1},
    "LighteningReference": {"LighteningZ": 1},
}
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
# The depth-wise stations as the print states them: each from the front face.
_V_MOUTH_Z = (BLOCK_DEPTH - V_MOUTH_WIDTH) / 2.0
_RELIEF_Z0 = (BLOCK_DEPTH - RELIEF_WIDTH) / 2.0
# Rule 17: the relief's near wall is ReliefZ0 itself; the far wall is what
# the print leaves of the depth.
RELIEF_NEAR_WALL_PRINTED_MIN = _RELIEF_Z0 - _band("ReliefZ0")
RELIEF_FAR_WALL_PRINTED_MIN = (
    (BLOCK_DEPTH - _band("Depth"))
    - (_RELIEF_Z0 + _band("ReliefZ0"))
    - (RELIEF_WIDTH + _band("ReliefWidth"))
)  # 1.73
if min(RELIEF_NEAR_WALL_PRINTED_MIN, RELIEF_FAR_WALL_PRINTED_MIN) < _WALL:
    raise AssertionError("a printed relief wall falls under the rule 17 1.5 floor")


def _body_half_chord_at_bottom(apex_y: float, mouth: float) -> float:
    """The marker body's half-width at the bottom face, its grip seated in a
    V of this apex height and mouth (both flanks touching the grip)."""
    half = math.atan2(mouth / 2.0, apex_y)
    axis_y = apex_y - (marker.BARREL_DIA / 2.0) / math.sin(half)
    return math.sqrt(_BODY_R**2 - axis_y**2)


# The V's apex and mouth at their printed limits move the seated axis; the
# widest body chord at the bottom face over the four corners (6.018 at .XX
# apex, 5.965 nominal).
BODY_HALF_CHORD_PRINTED_MAX = max(
    _body_half_chord_at_bottom(V_APEX_Y + apex, V_MOUTH_WIDTH + mouth)
    for apex in (-_band("VApexY"), _band("VApexY"))
    for mouth in (-_band("VMouth"), _band("VMouth"))
)
# The body's centre is the V's: VMouthZ + VMouth / 2 from the front face.
BODY_NEAR_CLEARANCE_PRINTED_MIN = (
    (_V_MOUTH_Z - _band("VMouthZ"))
    + (V_MOUTH_WIDTH - _band("VMouth")) / 2.0
    - BODY_HALF_CHORD_PRINTED_MAX
    - (_RELIEF_Z0 + _band("ReliefZ0"))
)  # 0.16 (0.21 on the nominal chord)
BODY_FAR_CLEARANCE_PRINTED_MIN = (
    (_RELIEF_Z0 - _band("ReliefZ0"))
    + (RELIEF_WIDTH - _band("ReliefWidth"))
    - (_V_MOUTH_Z + _band("VMouthZ"))
    - (V_MOUTH_WIDTH + _band("VMouth")) / 2.0
    - BODY_HALF_CHORD_PRINTED_MAX
)  # 0.03 (0.08 on the nominal chord)
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
# The relief's four .XXX stations share one function, stated once on the
# slot's width; two short rows stay between its extension lines.
DIMENSION_CALLOUTS: dict[str, str] = {
    "PivotDia": f"REAM THRU\nSLIP FIT ON PEN ROD PIVOT {PEN_ROD_NUMBER}",
    "Chamfer2dx": "X 45 DEG, 2 PLACES",
    "PivotChamferSize": "X 45 DEG",
    "ReliefWidth": f"CLEARS MARKER BODY\n{MARKER_NUMBER}",
}
# Two rows, so the callout stays inside the sheet's right border over the far
# rim (draw_pn_pen_v_block's SECTION_KEEP).
DIMENSION_CALLOUTS_ABOVE: dict[str, str] = {
    "PivotChamferSize": f"CLEARS ROD\n{PEN_ROD_NUMBER} FILLET",
}
# Both relief corners are one radius; the printed one stands for the pair.  A
# custom prefix replaces SolidWorks' own radius "R", so it carries it
# (pn_pen_hanger_spec's slot corners).
DIMENSION_PREFIXES: dict[tuple[str, str], str] = {
    ("ReliefProfile", "ReliefCornerR"): "2X R",
}

# Material and finish ride the title block; nothing else needs saying.
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
