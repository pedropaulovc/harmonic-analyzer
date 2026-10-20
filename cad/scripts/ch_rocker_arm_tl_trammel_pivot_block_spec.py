r"""Pure-data contract for the rocker template trammel's pivot block (MHA-CH-06-TL-14).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md). One of
the two clamp-on blocks of the rocker outline-template trammel kit
(``ch_rocker_arm_tl_trammel_spec``, trial route ``rocker-template-route.md``
section 2.1). A 50 long piece of 1018 cold-rolled 3/4 x 1-1/2 in flat bar,
lying on its 38.1 face, slides onto the bought 1/4 in square trammel bar:

* the bar runs in a 6.45 +0.05/0 slot along the block's top face, 13.0 from
  edge A; two 10-24 cup-point set screws from edge A push it against the
  slot's edge-B wall, so the wall, not the screws, locates the block;
* the pivot point (MHA-CH-06-TL-18, 1/4 in O1 drill rod) stands in a hole
  reamed with the shop's 0.251 in reamer, 28.0 from edge A and 25 from the
  block's end, the end that sits flush with the bar's pivot-end face;
* a 1.0 slit on the point-hole axis runs from the near end face, through the
  point hole, into a 3.0 drilled relief 8 past it (the remaining 17 is the
  hinge), and one #8-32 socket head cap screw crossing under the slot floor
  pinches the slit shut on the point: head on edge B, clearance through the
  edge-B jaw, threaded in the slot-side jaw (Fx1cTrammel ruling: the 3/4 in
  stock stays, the screw runs below the slot floor).

The scriber block (``ch_rocker_arm_tl_trammel_scriber_block_spec``) is the
same block with two point holes; it imports this module's shared section.

Frame (one frame for both blocks, approved by Fx1cTrammel): origin on the
(inner) point hole's axis at the block's top face, in edge A's plane; +X along
the block (along the bar, toward the scribers), +Y up out of the top face,
+Z across the block from edge A toward edge B. The block occupies
X = -25..+25, Y = -19.05..0, Z = 0..38.1. The kit frame
(``ch_rocker_arm_tl_trammel_spec.PRECHIPS_SOLIDS``) maps as
kit (x, y, z) = (25 + X, Z - 13.0, Y). Every station along the block is
printed from the point-hole axis, so a feature's distance to the point hole
carries one band, not two.
"""

from __future__ import annotations

import math

import ch_rocker_arm_tl_trammel_spec as kit
from _hole_spec import (
    CLEARANCE_MM,
    TAP_DRILL_MM,
    THREAD_MAJOR_MM,
    HoleSpec,
    blind_cut_dia_mm,
)
from _gtol_planar import PlanarFace
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl

INCH = kit.INCH
_X = printed_band_mm(1)
_XX = printed_band_mm(2)
_XXX = printed_band_mm(3)
# drawing-guidelines.md rule 17 (walls and webs): 2.0 target, 1.5 floor.
WALL_TARGET = 2.0
WALL_FLOOR = 1.5

# --- Block (stock as supplied: 3/4 x 1-1/2 in cold-rolled flat) ---------------
BLOCK_LENGTH = kit.BLOCK_LENGTH
BLOCK_WIDTH = kit.BLOCK_WIDTH
BLOCK_HEIGHT = kit.BLOCK_HEIGHT
# The block height prints at two places: the pinch screw's walls below the
# slot floor are budgeted against its +/-0.51 band (rule 17: worst_walls'
# pinch-clearance-to-bottom web is 1.545 at .XX and would fall under the
# 1.5 floor at the one-place +/-0.8). The title block's material is any
# LOW-CARBON STEEL FLAT; the stock named in material_specification stays
# 1018 cold-rolled for the same reason: drawn flat holds its 3/4 in thickness
# well inside that .XX band as supplied, so the budgeted walls need no
# machining of the broad faces. The sheet says so: 19.05 STOCK (the pivot
# plate's convention).
BLOCK_HEIGHT_PLACES = 2
BLOCK_HEIGHT_CALLOUT = "STOCK"
HOLE_FROM_END = kit.PIVOT_HOLE_L  # 25.0: the end face to the point-hole axis
BLOCK_X0 = -HOLE_FROM_END
BLOCK_X1 = BLOCK_X0 + BLOCK_LENGTH
HOLE_X = (0.0,)

# --- Bar slot ------------------------------------------------------------------
SLOT_WIDTH = kit.SLOT_WIDTH
SLOT_FROM_EDGE_A = kit.SLOT_FROM_EDGE_A
SLOT_DEPTH = kit.SLOT_DEPTH
SLOT_DEPTH_PLACES = 2  # the pinch tap's wall under the floor is budgeted at +/-0.51
SLOT_Z0 = SLOT_FROM_EDGE_A - SLOT_WIDTH / 2.0  # edge-A wall
SLOT_Z1 = SLOT_FROM_EDGE_A + SLOT_WIDTH / 2.0  # edge-B wall, the bar's datum
SLOT_CUT_RISE = 1.0  # the slot sketch runs this far above the top face
# The bar must seat on the floor and against the edge-B wall, so the floor
# corners may carry no radius bigger than the bar's own corner break. Cold
# drawn square has small broken corners; R0.2 MAX is the conservative cap.
SLOT_CORNER_R_MAX = 0.2
SLOT_WIDTH_MAX = SLOT_WIDTH + kit.SLOT_WIDTH_BAND[0]
SLOT_WIDTH_MIN = SLOT_WIDTH + kit.SLOT_WIDTH_BAND[1]
SLOT_CLEARANCE_MIN = SLOT_WIDTH_MIN - kit.BAR_SIDE
SLOT_CLEARANCE_MAX = SLOT_WIDTH_MAX - kit.BAR_SIDE_MIN
if SLOT_CLEARANCE_MIN <= 0.0:
    raise AssertionError("the trammel bar does not enter the smallest slot")
# drawing-guidelines.md rule 4 (matched fits): the tight slot names its mate
# and its fit. The bar is bought stock with no part Number, so it is named by
# its stock. One line: the dimension's above-lane prints one line only, and
# the SLOT_CLEARANCE_MIN/MAX asserts above carry the fit's numbers.
SLOT_WIDTH_CALLOUT = "SLIDING FIT ON TRAMMEL BAR"
SLOT_CORNER_CALLOUT = f"FLOOR CORNERS R{SLOT_CORNER_R_MAX:.1f} MAX"

# --- Point hole ----------------------------------------------------------------
# Reamed with tools.reamers' 0.251 in over-size reamer; the model and the
# print carry the three-place size (one fact) with the reamed +0.013/0 band.
POINT_HOLE_DIA = round(kit.POINT_HOLE_DIA, 3)
POINT_HOLE_BAND = (0.013, 0.0)  # (upper, lower)
POINT_HOLE_DIA_MAX = POINT_HOLE_DIA + POINT_HOLE_BAND[0]
POINT_HOLE_R_MAX = POINT_HOLE_DIA_MAX / 2.0
POINT_FROM_EDGE_A = kit.POINT_FROM_EDGE_A
POINT_ROD_DIA_MAX = kit.POINT_ROD_DIA + kit.POINT_ROD_DIA_BAND[0]
POINT_ROD_DIA_MIN = kit.POINT_ROD_DIA + kit.POINT_ROD_DIA_BAND[1]
POINT_CLEARANCE_MIN = POINT_HOLE_DIA - POINT_ROD_DIA_MAX
POINT_CLEARANCE_MAX = POINT_HOLE_DIA_MAX - POINT_ROD_DIA_MIN
if POINT_CLEARANCE_MIN <= 0.0:
    raise AssertionError(
        "the largest trammel point does not enter the smallest reamed hole"
    )
POINT_MATE_NUMBER = "MHA-CH-06-TL-18"


def point_hole_callout(count: int, mate_number: str) -> str:
    """The reamed hole's rule-4 matched-fit callout, naming the point.

    Three short rows (<= 25 characters) so the stacked block stays inside the
    sheet beside the top view.
    """
    prefix = f"{count}X " if count > 1 else ""
    return (
        f"{prefix}REAM THRU ({POINT_CLEARANCE_MIN:.3f}-{POINT_CLEARANCE_MAX:.3f}\n"
        f"DIAMETRAL CLEARANCE ON\n{mate_number})"
    )


POINT_HOLE_CALLOUT = point_hole_callout(len(HOLE_X), POINT_MATE_NUMBER)

# --- Slit ------------------------------------------------------------------------
# On the point-hole axis, from the end face at X0 into the relief hole at
# SLIT_END_X; the pinch closes it on the point. Full block height. The slit's
# distance from edge A is the point hole's by equation, so one 28.0 prints.
SLIT_WIDTH = 1.0
SLIT_Z = POINT_FROM_EDGE_A
SLIT_END_X = 33.0 - HOLE_FROM_END  # L33: 8 past the point-hole axis
SLIT_Z0 = SLIT_Z - SLIT_WIDTH / 2.0  # slot-side jaw face
SLIT_Z1 = SLIT_Z + SLIT_WIDTH / 2.0  # edge-B jaw face
SLIT_START_X = BLOCK_X0 - 1.0  # the slit sketch starts beyond the end face
SLIT_CALLOUT = "SLIT THRU"
# The slit ends in a drilled relief hole through the height (Fx1cTrammel
# round 5, option b), centred on the slit's end station: the relief, not a
# saw's arc, ends the slit, so the end is one printed station on every face.
# The 1.0 slit is a hacksaw (tools.hacksaw-starrett-k145) or slitting cut run
# from the end face into the hole: the shop's 3 in slitting saws
# (tools.slitting-saws) on the R8 arbor's 45 flange reach (76.2 - 45) / 2 =
# 15.6 deep, short of the 19.05 stock, so no single pass cuts it THRU. The
# 3.0 drill is tools.drills-metric's; the title block's DRILLED HOLES row
# governs its size (DRILLED_BAND below).
SLIT_RELIEF_DIA = 3.0
SLIT_RELIEF_CALLOUT = "DRILL THRU"
if SLIT_RELIEF_DIA <= SLIT_WIDTH:
    raise AssertionError("the slit relief does not end the slit in a round hole")

# --- Set screws (kit: 10-24 UNC x 1/2 cup point, from edge A) ------------------
SET_SCREW_SIZE = "#10-24"
if abs(THREAD_MAJOR_MM[SET_SCREW_SIZE] - kit.SET_SCREW_MAJOR) > 1e-6:
    raise AssertionError("set screw size token does not match the kit's 10-24 thread")
# The tap opens into the slot: through to the next face, no blind depth.
SET_SCREW_SPEC = HoleSpec("tapped", SET_SCREW_SIZE, end="through_next")
SET_SCREW_TAP_DRILL = TAP_DRILL_MM[SET_SCREW_SIZE]
SET_SCREW_DEPTH = -kit.SET_SCREW_Z  # 5.4 below the top face, one place
SET_SCREW_X = tuple(station - HOLE_FROM_END for station in kit.SET_SCREW_L)

# --- Pinch screw (#8-32 SHCS, below the slot floor) ----------------------------
PINCH_THREAD = "#8-32"
PINCH_PITCH = INCH / 32.0
PINCH_MAJOR = THREAD_MAJOR_MM[PINCH_THREAD]
# Tapped through both jaws from edge B, then the edge-B jaw opened to a close
# #8 clearance up to the slit (draw/build of dt_cone_tip_block's pinch).
PINCH_TAP_SPEC = HoleSpec("tapped", PINCH_THREAD)
PINCH_TAP_DRILL = TAP_DRILL_MM[PINCH_THREAD]
EDGE_B_JAW = BLOCK_WIDTH - SLIT_Z1  # the clearance length, nominal
# Blind to the slit face, as dt_cone_tip_block's pinch clearance: a
# through_next end ran on through the slot-side jaw to edge A (farm round 1),
# stripping the thread. The drill point lies in the slit (_trammel_block
# asserts it cuts nothing past the jaw). No diameter override: the blind path
# cuts the pinned close-fit diameter directly.
PINCH_CLEARANCE_SPEC = HoleSpec(
    "clearance",
    "#8",
    end="blind",
    depth_mm=EDGE_B_JAW,
    fit="close",
)
# The model cuts the pinned #8 close diameter; the callout prints it at two
# places, and the requirement band and the walls use that printed size.
PINCH_CLEARANCE_DIA = blind_cut_dia_mm(PINCH_CLEARANCE_SPEC)
if abs(PINCH_CLEARANCE_DIA - CLEARANCE_MM[("#8", "close")]) > 1e-9:
    raise AssertionError("pinch clearance is not the #8 close fit")
PINCH_CLEARANCE_PRINTED_DIA = round(PINCH_CLEARANCE_DIA, 2)
# Title-block DRILLED HOLES: plus allowance, zero minus (_printed_tolerance).
DRILLED_BAND = (drilled_oversize_mm(), 0.0)
PINCH_CLEARANCE_R_MAX = (PINCH_CLEARANCE_PRINTED_DIA + DRILLED_BAND[0]) / 2.0
if PINCH_CLEARANCE_DIA > 2.0 * PINCH_CLEARANCE_R_MAX:
    raise AssertionError("the modelled pinch clearance lies outside its printed band")
# Below the top face, printed at two places. Chosen to balance the tap's wall
# under the slot floor against the clearance's wall over the block bottom.
PINCH_DEPTH = 14.15
PINCH_PLACES = 2
PINCH_X = (12.0 - HOLE_FROM_END,)  # L12, between the end face and the point
# ASME B18.3 #8 SHCS head 0.270 in; #8-32 x 1 in SHCS.
PINCH_HEAD_DIA = 0.270 * INCH
PINCH_SCREW_LENGTH = 1.0 * INCH
# The shop's drill index sizes (tools.drill-index-115), said on the callouts.
SET_SCREW_PROCESS = "#25 DRILL, THEN TAP"
PINCH_TAP_PROCESS = "#29 DRILL, THEN TAP"
PINCH_CLEARANCE_PROCESS = "#15 DRILL"
# Replaces the native blind depth on the callout (dt_cone_tip_block's r3 rule):
# the depth is "up to the slit", not a printed length.
PINCH_CLEARANCE_EXTENT_TEXT = "TO THE SLIT"

# --- Worst cases (rules 17, 18) at the printed bands ----------------------------
_BAND_BY_PLACES = {1: _X, 2: _XX, 3: _XXX}
_SLOT_FLOOR_MAX = SLOT_DEPTH + _BAND_BY_PLACES[SLOT_DEPTH_PLACES]
_HEIGHT_MIN = BLOCK_HEIGHT - _BAND_BY_PLACES[BLOCK_HEIGHT_PLACES]
_PINCH_HIGH = PINCH_DEPTH - _BAND_BY_PLACES[PINCH_PLACES]
_PINCH_LOW = PINCH_DEPTH + _BAND_BY_PLACES[PINCH_PLACES]
_SET_MAJOR_R = THREAD_MAJOR_MM[SET_SCREW_SIZE] / 2.0
_PINCH_MAJOR_R = PINCH_MAJOR / 2.0
_SLOT_FAR_WALL_MAX = SLOT_FROM_EDGE_A + _X + SLOT_WIDTH_MAX / 2.0
_SLOT_NEAR_WALL_MIN = SLOT_FROM_EDGE_A - _X - SLOT_WIDTH_MAX / 2.0
_SLIT_HALF_MAX = (SLIT_WIDTH + _X) / 2.0
_SLIT_FAR_FACE_MIN = SLIT_Z - _X - _SLIT_HALF_MAX  # slot-side jaw face, lowest Z
_EDGE_B_MIN = BLOCK_WIDTH - _X
_EDGE_B_MAX = BLOCK_WIDTH + _X
_SLIT_RELIEF_R_MAX = (SLIT_RELIEF_DIA + DRILLED_BAND[0]) / 2.0


def worst_walls(
    block_x0: float,
    hole_x: tuple[float, ...],
    hole_spacing_band: float,
    set_screw_x: tuple[float, ...],
    pinch_x: tuple[float, ...],
    slit_end_x: float,
) -> dict[str, float]:
    """Every wall/web of one block at the worst case of its printed bands.

    ``block_x0`` is the block's lower-X end face; ``hole_x`` are the
    point-hole stations (the first is the origin; a second one is held to
    ``hole_spacing_band``); every other station prints at one place from the
    first hole's axis, and the end faces at one place too, so a
    feature-to-end distance carries two one-place bands."""
    x0, x1 = block_x0, block_x0 + BLOCK_LENGTH
    walls = {
        # Set screw thread major under the top face (the kit's 5.4 axis).
        "set screw thread to top face": SET_SCREW_DEPTH - _X - _SET_MAJOR_R,
        # Pinch tap thread major over the slot floor.
        "pinch thread to slot floor": _PINCH_HIGH - _PINCH_MAJOR_R - _SLOT_FLOOR_MAX,
        # Pinch clearance (edge-B jaw) over the block bottom.
        "pinch clearance to block bottom": _HEIGHT_MIN
        - _PINCH_LOW
        - PINCH_CLEARANCE_R_MAX,
        # Pinch tap (slot-side jaw) over the block bottom.
        "pinch thread to block bottom": _HEIGHT_MIN - _PINCH_LOW - _PINCH_MAJOR_R,
        # Point hole to edge B and to the slot's edge-B wall.
        "point hole to edge B": _EDGE_B_MIN
        - (POINT_FROM_EDGE_A + _X)
        - POINT_HOLE_R_MAX,
        "point hole to slot wall": POINT_FROM_EDGE_A
        - _X
        - POINT_HOLE_R_MAX
        - _SLOT_FAR_WALL_MAX,
        # Slot-side jaw between the slot and the slit; the edge-B jaw.
        "slot to slit jaw": _SLIT_FAR_FACE_MIN - _SLOT_FAR_WALL_MAX,
        "edge B jaw": _EDGE_B_MIN - (SLIT_Z + _X + _SLIT_HALF_MAX),
        # The hinge ligament past the slit's relief hole.
        "slit hinge": (x1 - slit_end_x) - 2.0 * _X - _SLIT_RELIEF_R_MAX,
        # The edge-A wall the set screws thread through.
        "edge A wall": _SLOT_NEAR_WALL_MIN,
        # The slot floor web over the block bottom.
        "slot floor web": _HEIGHT_MIN - _SLOT_FLOOR_MAX,
    }
    first = hole_x[0]
    # The end faces print from the first hole: one one-place band.
    walls["point hole to end face"] = min(
        abs(x - end)
        - _X
        - (0.0 if x == first else hole_spacing_band)
        - POINT_HOLE_R_MAX
        for x in hole_x
        for end in (x0, x1)
    )
    walls["slit relief to point hole"] = min(
        slit_end_x
        - _X
        - (x + (0.0 if x == first else hole_spacing_band))
        - POINT_HOLE_R_MAX
        - _SLIT_RELIEF_R_MAX
        for x in hole_x
    )
    # The relief (on the slit, Z 28) to each pinch hole crossing that Z: the
    # edge-B jaw's clearance is the larger radius.
    walls["slit relief to pinch hole"] = min(
        abs(slit_end_x - p) - 2.0 * _X - _SLIT_RELIEF_R_MAX - PINCH_CLEARANCE_R_MAX
        for p in pinch_x
    )
    walls["set screw thread to end face"] = min(
        abs(x - end) - 2.0 * _X - _SET_MAJOR_R for x in set_screw_x for end in (x0, x1)
    )
    walls["pinch clearance to end face"] = min(
        abs(x - end) - 2.0 * _X - PINCH_CLEARANCE_R_MAX
        for x in pinch_x
        for end in (x0, x1)
    )
    # Pinch to each point hole: the clearance in the edge-B jaw (the larger
    # radius) governs; the thread in the slot-side jaw is reported too.
    for label, radius in (
        ("clearance", PINCH_CLEARANCE_R_MAX),
        ("thread", _PINCH_MAJOR_R),
    ):
        walls[f"pinch {label} to point hole"] = min(
            abs(p - h)
            - _X
            - (0.0 if h == first else hole_spacing_band)
            - POINT_HOLE_R_MAX
            - radius
            for p in pinch_x
            for h in hole_x
        )
    # Pinch thread to set screw thread: centre distance at worst stations
    # (X one place each) and heights (pinch two places, set screw one).
    vertical = _PINCH_HIGH - (SET_SCREW_DEPTH + _X)
    walls["pinch thread to set screw thread"] = min(
        math.hypot(max(abs(p - s) - 2.0 * _X, 0.0), vertical)
        - _PINCH_MAJOR_R
        - _SET_MAJOR_R
        for p in pinch_x
        for s in set_screw_x
    )
    return walls


WORST_WALLS = worst_walls(BLOCK_X0, HOLE_X, 0.0, SET_SCREW_X, PINCH_X, SLIT_END_X)
for _name, _wall in WORST_WALLS.items():
    if _wall < WALL_FLOOR:
        raise AssertionError(
            f"pivot block {_name} wall {_wall:.3f} under the rule 17 floor"
        )
# drawing-guidelines.md rule 20: walls between the floor and the target.
RULE_20_SHORTFALLS = {
    name: wall for name, wall in WORST_WALLS.items() if wall < WALL_TARGET
}

# The #8 head lands wholly on edge B at the lowest pinch and thinnest stock.
if _PINCH_LOW + PINCH_HEAD_DIA / 2.0 >= _HEIGHT_MIN:
    raise AssertionError("pinch screw head overhangs the block bottom")

# drawing-guidelines.md rule 18 (thread engagement): 1.5 D of full thread at
# the worst case, after one and a half pitches of incomplete lead thread.
FULL_THREAD_D = 1.5
_INCOMPLETE = 1.5 * PINCH_PITCH
# Pinch: the screw enters at edge B (widest stock) and threads only past the
# slit's slot-side face (lowest Z); its tip must stay inside the block.
_PINCH_TIP_Z = _EDGE_B_MAX - PINCH_SCREW_LENGTH
PINCH_FULL_THREAD = _SLIT_FAR_FACE_MIN - _PINCH_TIP_Z - _INCOMPLETE
if PINCH_FULL_THREAD < FULL_THREAD_D * PINCH_MAJOR:
    raise AssertionError("#8-32 x 1 pinch screw engages under 1.5 D of full thread")
if _EDGE_B_MIN - PINCH_SCREW_LENGTH <= 0.0:
    raise AssertionError("#8-32 x 1 pinch screw tip leaves edge A")
# Set screws: full thread through the thinnest edge-A wall.
SET_SCREW_FULL_THREAD = _SLOT_NEAR_WALL_MIN - 1.5 * kit.SET_SCREW_PITCH
if SET_SCREW_FULL_THREAD < FULL_THREAD_D * kit.SET_SCREW_MAJOR:
    raise AssertionError("10-24 set screws engage under 1.5 D of full thread in edge A")
# The 1/2 in set screw reaches the smallest bar pushed to the far wall
# across the thickest edge-A wall.
SET_SCREW_REACH_GAP = (SLOT_FROM_EDGE_A + _X + SLOT_WIDTH_MAX / 2.0) - kit.BAR_SIDE_MIN
if SET_SCREW_REACH_GAP >= kit.SET_SCREW_LENGTH:
    raise AssertionError("1/2 in set screw cannot reach the smallest trammel bar")

# --- Drawing ----------------------------------------------------------------------
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"BlockLength", "BlockWidth", "HoleFromEnd"},
    "Block": {"BlockHeight"},
    "SlotProfile": {"SlotWidth", "SlotFromEdgeA", "SlotDepth"},
    "SlitProfile": {"SlitWidth"},
    "SlitReliefProfile": {"SlitEnd", "SlitReliefDia"},
    "PointHoleProfile": {"PointHoleDia", "PointFromEdgeA"},
    "SetScrewTaps": {"SetScrewX1", "SetScrewX2", "SetScrewDepth"},
    "PinchTaps": {"PinchX", "PinchDepth"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {"BlockLength": 1, "BlockWidth": 1, "HoleFromEnd": 1},
    "Block": {"BlockHeight": BLOCK_HEIGHT_PLACES},
    "SlotProfile": {"SlotWidth": 2, "SlotFromEdgeA": 1, "SlotDepth": SLOT_DEPTH_PLACES},
    "SlitProfile": {"SlitWidth": 1},
    "SlitReliefProfile": {"SlitEnd": 1, "SlitReliefDia": 1},
    "PointHoleProfile": {"PointHoleDia": 3, "PointFromEdgeA": 1},
    "SetScrewTaps": {"SetScrewX1": 1, "SetScrewX2": 1, "SetScrewDepth": 1},
    "PinchTaps": {"PinchX": 1, "PinchDepth": PINCH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked pivot block dimension needs authored places")

# drawing-guidelines.md rule 6: Ra only where a surface slides or locates.
# The bar slides on the slot floor and is pushed against the edge-B wall,
# so the bar's two contact faces carry the machined Ra.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "slot_floor", MACHINED_UM, PlanarFace((0.0, 1.0, 0.0), -SLOT_DEPTH)
    ),
    SurfaceFinishControl(
        "slot_datum_wall", MACHINED_UM, PlanarFace((0.0, 0.0, -1.0), -SLOT_Z1)
    ),
)
# The bar's sliding fit is on the slot callout and the deburring is the title
# block's; only the pinch's function needs saying.
DRAWING_NOTES = "THE PINCH SCREW CLOSES THE SLIT ON THE PIVOT POINT."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
