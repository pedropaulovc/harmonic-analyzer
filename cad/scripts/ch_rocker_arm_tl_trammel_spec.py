r"""Pure-data contract for the rocker outline template's trammel kit.

Shop tooling, not a machine part (cad/docs/subsystem-identities.md). The
rocker arm's (MHA-CH-006) outline template is scribed in-house on blued O1
plate with a dedicated trammel (Pedro 2026-10-11; trial route
``rocker-template-route.md`` section 2.1, inventory ``tools.rocker-trammel``):
a bought 1018 cold-finished 1/4 in square bar, used uncut and undrilled,
carries two clamp-on 1018 blocks. The pivot block's 60 degree point runs in
the 60 degree centre-drilled cone of the pivot plate screwed to the MDF
scribing board; the scriber block's two 30 degree scriber points, 16.000
apart, scribe R800 and R816. The kit is set point to point in the setting
bar's H0/H800/H816 cones (MHA-CH-006-TL-17), so R comes from the point-hole
positions, not from the bar.

The kit is five shop-made parts, one single-body part per made piece as the
existing fixture kits are (each spec below imports this one):

* MHA-CH-006-TL-14 pivot block (``ch_rocker_arm_tl_trammel_pivot_block``);
* MHA-CH-006-TL-15 scriber block (``ch_rocker_arm_tl_trammel_scriber_block``);
* MHA-CH-006-TL-16 scriber point, two off
  (``ch_rocker_arm_tl_trammel_scriber_point``);
* MHA-CH-006-TL-18 pivot point (``ch_rocker_arm_tl_trammel_pivot_point``);
* MHA-CH-006-TL-19 pivot plate (``ch_rocker_arm_tl_trammel_pivot_plate``,
  its own inventory record).

The bar is bought stock used as supplied, so it is not modelled (bought
fixture hardware is not modelled); neither are the 10-24 set screws and the
#8-32 pinch screws.

Kit frame (the inventory record's ``PRECHIPS_SOLIDS`` frame): origin on the
bar's pivot-end face, +X along the bar toward the scribers, +Z up with Z0 on
the block tops (both blocks stand on the same flat), the bar's axis in the
plane Y0 and the points on the +Y side. Each block's "edge A" is its long
side face nearer the bar (the set screws enter there), "edge B" the opposite
face beyond the points (the pinch screws enter there).

Departures from the trial route, each forced by the drawing guidelines and
recorded as open decisions in the PR:

* the bar slot sits 13.0 (route 9.0) from edge A and 9.50 (route 6.35) deep,
  so the 10-24 set screws keep 1.5 D of full thread in edge A's wall and
  their thread clears the block top (rules 17 and 18): the bar rides 3.15
  below the block top instead of flush, which R does not see;
* the set screws are 1/2 in long (route 3/8 in): a 3/8 in screw cannot reach
  the bar across the thicker wall at the worst case;
* the point holes are reamed with the shop's 0.251 in over-size reamer so a
  point cannot shift in its hole by more than the reamed clearance;
* the pinch screws are #8-32 x 1 in socket-head cap screws (route 10-24 x
  3/4 in) crossing below the slot floor: a 10-24 thread cannot keep rule-17
  walls between the slit and the slot, or between the scriber holes, in the
  3/4 in stock.
"""

from __future__ import annotations

from typing import Any

from _printed_tolerance import printed_band_mm

INCH = 25.4


def _mm(inches: float) -> float:
    """Inches to millimetres, rounded clear of float noise (1.5 * 25.4 is 38.0999...)."""
    return round(inches * INCH, 9)


# --- Template radii and the stations along the bar ---------------------------
# From the bar's pivot-end face (route section 2.1 "Positions along the
# trammel bar"): pivot point 25, inner (R800) scriber 825, outer (R816) 841.
TEMPLATE_RADII = (800.0, 816.0)
PIVOT_POINT_X = 25.0
INNER_SCRIBER_X = 825.0
OUTER_SCRIBER_X = 841.0
if (INNER_SCRIBER_X - PIVOT_POINT_X, OUTER_SCRIBER_X - PIVOT_POINT_X) != TEMPLATE_RADII:
    raise AssertionError("trammel point stations do not give R800 and R816")

# --- Bought trammel bar (not modelled) ---------------------------------------
# Online Metals 7088, 1018 cold-finished 1/4 in square x 36 in (ASTM A108);
# inventory tools.rocker-trammel width/thickness/length. Cold-finished square
# is held at or under nominal; BAR_SIDE_MIN is the smallest bar the set screw
# must still reach (ASTM A108 cold-drawn 1/4 in square: +0 / -0.002 in).
BAR_SIDE = _mm(0.25)
BAR_SIDE_MIN = _mm(0.25 - 0.002)
BAR_LENGTH = _mm(36.0)

# --- The two clamp-on blocks (1018 cold-rolled 3/4 x 1-1/2 in bar) -----------
# Route 2.1: each block is 50 long, cut from the approved 3/4 x 1-1/2 bar
# (19.05 x 38.1 section), lying on its 38.1 face.
BLOCK_LENGTH = 50.0
BLOCK_WIDTH = _mm(1.5)
BLOCK_HEIGHT = _mm(0.75)
PIVOT_BLOCK_X = 0.0  # the pivot block's end flush with the bar's end face
SCRIBER_BLOCK_X = 808.0
# Point stations along each block from its end at the lower X.
PIVOT_HOLE_L = PIVOT_POINT_X - PIVOT_BLOCK_X  # 25, the block's middle
SCRIBER_HOLE_L = (INNER_SCRIBER_X - SCRIBER_BLOCK_X, OUTER_SCRIBER_X - SCRIBER_BLOCK_X)
SCRIBER_SPACING = SCRIBER_HOLE_L[1] - SCRIBER_HOLE_L[0]  # 16.000
# Route 2.1: the scriber holes are 16.000 +/-0.01 apart, drilled (here
# reamed) in one DRO setting; the setting bar's H800/H816 proves it.
SCRIBER_SPACING_BAND = (0.01, -0.01)
for _station in (PIVOT_HOLE_L, *SCRIBER_HOLE_L):
    if not 0.0 < _station < BLOCK_LENGTH:
        raise AssertionError("a trammel point hole falls outside its block")

# Bar slot, along the block's length in its top face. Width 6.45 +0.05/0
# (route 2.1) slides over the nominal bar with 0.10 MIN.
SLOT_WIDTH = 6.45
SLOT_WIDTH_BAND = (0.05, 0.0)  # (upper, lower)
SLOT_FROM_EDGE_A = 13.0
SLOT_DEPTH = 9.5
# Points 28.0 from edge A (route 2.1), so 15.0 off the bar axis.
POINT_FROM_EDGE_A = 28.0
POINT_OFFSET_Y = POINT_FROM_EDGE_A - SLOT_FROM_EDGE_A
EDGE_A_Y = -SLOT_FROM_EDGE_A
EDGE_B_Y = EDGE_A_Y + BLOCK_WIDTH
if not SLOT_WIDTH + SLOT_WIDTH_BAND[1] - BAR_SIDE > 0.0:
    raise AssertionError("the trammel bar does not slide into the smallest slot")

# --- Set screws: two per block from edge A, on the bar's mid-height ----------
# 10-24 UNC cup-point set screws (Bolt Depot 8474 is the 3/8 in length the
# route proposed; the 1/2 in length is the departure noted above).
SET_SCREW_THREAD = "10-24 UNC"
SET_SCREW_MAJOR = _mm(0.190)
SET_SCREW_PITCH = _mm(1.0 / 24.0)
SET_SCREW_LENGTH = _mm(0.5)
SET_SCREW_L = (12.0, 38.0)  # route 2.1, from the block's lower-X end
# The bar rests on the slot floor; the set screws push it against the slot's
# edge-B wall. Their axis prints at one place, 5.4 below the block top, so at
# +/-0.8 the 10-24 major diameter keeps a wall under the top face and clears
# the slot floor, and the axis stays below the smallest bar's top face.
SET_SCREW_Z = -5.4
# Worst cases at the one-place band on both the screw axis and the slot depth.
_ONE_PLACE = printed_band_mm(1)
if not (
    SET_SCREW_Z + _ONE_PLACE + SET_SCREW_MAJOR / 2.0 < 0.0
    and SET_SCREW_Z - _ONE_PLACE - SET_SCREW_MAJOR / 2.0 > -(SLOT_DEPTH - _ONE_PLACE)
    and SET_SCREW_Z + _ONE_PLACE < -(SLOT_DEPTH + _ONE_PLACE) + BAR_SIDE_MIN
):
    raise AssertionError("the trammel set screws miss the bar or break the block")

# --- Points: 1/4 in O1 drill rod, 60 long, hardened tips ---------------------
POINT_ROD_DIA = _mm(0.25)
# Precision-ground drill rod (Abrams O1 drill rod): +/-0.0005 in.
POINT_ROD_DIA_BAND = (_mm(0.0005), -_mm(0.0005))
POINT_LENGTH = 60.0
PIVOT_TIP_ANGLE = 60.0  # degrees included, runs in a 60 degree centre-drilled cone
SCRIBER_TIP_ANGLE = 30.0  # degrees included
HARDENED_TIP_LENGTH = 20.0  # route 2.4: heat the last 20 mm, quench, temper
# Route 2.1: the points stand 8-10 below the block so the blocks clear the
# blued plate; the solids pose them at 9.
POINT_PROJECTION = 9.0
TIP_Z = -BLOCK_HEIGHT - POINT_PROJECTION
# Point holes: reamed with tools.reamers' 0.251 in over-size reamer.
POINT_HOLE_DIA = _mm(0.251)

# --- Pivot plate seat (MHA-CH-006-TL-19) --------------------------------------
# No. 2 combined centre drill (tools.center-drills-lms-4859 member "2"):
# 5/64 in pilot, 60 degree countersink. The pivot point's 60 degree cone seats
# on that countersink.
CENTER_DRILL_PILOT_DIA = _mm(5.0 / 64.0)
CENTER_DRILL_ANGLE = 60.0
if CENTER_DRILL_ANGLE != PIVOT_TIP_ANGLE:
    raise AssertionError("the pivot point does not match its centre-drilled seat")


def _box(
    name: str,
    at: tuple[float, float, float],
    size: tuple[float, float, float],
    **extra: Any,
) -> dict[str, Any]:
    return {
        "name": name,
        "shape": "box",
        "at_mm": list(at),
        "size_mm": list(size),
        **extra,
    }


def _point(name: str, x: float, note: str) -> dict[str, Any]:
    return {
        "name": name,
        "shape": "cylinder",
        "at_mm": [x, POINT_OFFSET_Y, TIP_Z],
        "axis": [0.0, 0.0, 1.0],
        "dia_mm": POINT_ROD_DIA,
        "length_mm": POINT_LENGTH,
        "note": note,
    }


def _block_solids(
    name: str, x0: float, hole_ls: tuple[float, ...], note: str
) -> list[dict[str, Any]]:
    solids = [
        _box(
            name,
            (x0, EDGE_A_Y, -BLOCK_HEIGHT),
            (BLOCK_LENGTH, BLOCK_WIDTH, BLOCK_HEIGHT),
            note=note,
        ),
        _box(
            f"{name} slot",
            (x0, -SLOT_WIDTH / 2.0, -SLOT_DEPTH),
            (BLOCK_LENGTH, SLOT_WIDTH, SLOT_DEPTH),
            void=True,
            cuts=[name],
        ),
    ]
    solids += [
        {
            "name": f"{name} point hole {index}",
            "shape": "cylinder",
            "at_mm": [x0 + station, POINT_OFFSET_Y, -BLOCK_HEIGHT],
            "axis": [0.0, 0.0, 1.0],
            "dia_mm": POINT_HOLE_DIA,
            "length_mm": BLOCK_HEIGHT,
            "void": True,
            "cuts": [name],
        }
        for index, station in enumerate(hole_ls, start=1)
    ]
    return solids


# The assembled kit as set on the setting bar, in the kit frame above. The
# blocks and points are made here; the bar is bought stock.
PRECHIPS_SOLIDS: list[dict[str, Any]] = [
    _box(
        "bar",
        (0.0, -BAR_SIDE / 2.0, -SLOT_DEPTH),
        (BAR_LENGTH, BAR_SIDE, BAR_SIDE),
        supply="bought",
        note="1018 cold-finished 1/4 in square bar, used uncut and undrilled",
    ),
    *_block_solids(
        "pivot block",
        PIVOT_BLOCK_X,
        (PIVOT_HOLE_L,),
        "MHA-CH-006-TL-14, 1018 3/4 x 1-1/2 bar",
    ),
    *_block_solids(
        "scriber block",
        SCRIBER_BLOCK_X,
        SCRIBER_HOLE_L,
        "MHA-CH-006-TL-15, 1018 3/4 x 1-1/2 bar",
    ),
    _point(
        "pivot point",
        PIVOT_POINT_X,
        "MHA-CH-006-TL-18, 60 degree tip in the pivot plate's cone",
    ),
    _point(
        "inner scriber",
        INNER_SCRIBER_X,
        "MHA-CH-006-TL-16, 30 degree tip, scribes R800",
    ),
    _point(
        "outer scriber",
        OUTER_SCRIBER_X,
        "MHA-CH-006-TL-16, 30 degree tip, scribes R816",
    ),
]
