r"""Pure-data contract for the rocker inspection box's C stop bar (MHA-CH-006-TL-09).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
rocker arm's off-machine A/B/C position check (prechips S4 op 50) the arm's
datum-B strap face seats on the inspection box front face and its datum-C tip
land rests on this bar's top: the bar simulates datum C. Route (shop-additions
section 4, binding): O1 ground flat 1/2 x 1/2 in, sawn and milled to length,
drilled and counterbored, torch-hardened in oil and tempered, then the top and
bottom lapped to 12.700 +-0.002 (the parallelism comes from the lap, printed as
the height band plus the LAPPED note; fixtures carry no GD&T). The bar sits on
the granite with the box, so its top is 12.70 above the box base by its own
height; two #8-32 socket head cap screws hold it to the box front wall, no
dowels (the inventory's M4 screws map to #8-32 under the fastener policy).

Frame: the inspection box's model frame (ch_rocker_arm_tl_inspection_box_spec),
so the bar's model coordinates are its installed box coordinates: origin at
the bar's left end, bottom and back (the face on the box front face), +X along
the bar, +Y up, +Z away from the box. The inventory's box frame (rocker-inv
fixtures.rocker-inspection-box) maps as inventory (x, y, z) = model (x, -z, y).
"""

from __future__ import annotations

import math

import ch_rocker_arm_spec as rocker
from _hole_spec import CLEARANCE_MM, THREAD_MAJOR_MM, HoleSpec
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

INCH = 25.4
# Abrams 102060: O1 precision-ground flat stock 1/2 x 1/2 in.
BAR_LENGTH = 40.0
BAR_HEIGHT = 12.7  # the datum-C simulator height above the base
BAR_WIDTH = 12.7  # as-bought stock, projection in front of the box
# Op 50 reads pin-height differences in one set-up (X = H1 - R1, Y = H3 - R3;
# rocker-plan op 50), so the bar's absolute height cancels; the tilt of its
# top does not. A tilt t over the bar length turns the op-50 hub-to-rod vector
# and moves the position reading by 2 * |v| * t / BAR_LENGTH on diameter. The
# chain budget is a quarter of the parent's position diameter. With no GD&T
# the size envelope carries parallelism: t is at most the total height band.
OP50_HUB_TO_ROD = math.hypot(132.391, 15.843)  # rocker-plan op-50 CAD nominals
PARENT_POSITION_DIA = float(rocker.GEOMETRIC_TOLERANCES_MM["rod-pin hole position"])
BAR_HEIGHT_BAND = (0.003, -0.003)  # (upper, lower) deviations
_TILT = BAR_HEIGHT_BAND[0] - BAR_HEIGHT_BAND[1]
if 2.0 * OP50_HUB_TO_ROD * _TILT / BAR_LENGTH > 0.25 * PARENT_POSITION_DIA:
    raise AssertionError("C stop bar height band spends over a quarter of the rod-hole position")
_X = printed_band_mm(1)

# The rocker's datum-C tip land rests wholly on the bar top: its strap
# thickness across the bar's projection, its tip face along the bar, at the
# op-50 station (inventory reading 1: C land x = 5.43..11.02).
C_LAND_X0 = 5.43
if rocker.ARM_THICKNESS >= BAR_WIDTH - _X:
    raise AssertionError("C stop bar projection does not carry the rocker strap")
if not (C_LAND_X0 > _X and C_LAND_X0 + rocker.TIP_FACE < BAR_LENGTH - _X):
    raise AssertionError("rocker datum-C tip land overhangs the C stop bar")

# Two #8-32 socket head cap screws (ASME B18.3: head 0.270 in dia x 0.164 in)
# through counterbored #8 normal clearance holes into the box front wall.
SCREW_THREAD = "#8-32"
SCREW_HEAD_DIA = 0.270 * INCH
SCREW_HEAD_H = 0.164 * INCH
SCREW_LENGTH = 0.625 * INCH  # #8-32 x 5/8 SHCS
SCREW_X = (10.0, 30.0)  # from the bar's left end (= the box left face)
SCREW_Y = BAR_HEIGHT / 2.0
# Model and export both use the printed two-place sizes (one fact).
CLEARANCE_DIA = round(CLEARANCE_MM[("#8", "normal")], 2)
CBORE_DIA = round(5.0 / 16.0 * INCH, 2)  # standard #8 SHCS counterbore
CBORE_DEPTH = 4.8
# Title-block DRILLED HOLES: plus allowance, zero minus (_printed_tolerance).
DRILLED_BAND = (drilled_oversize_mm(), 0.0)
# The native counterbore callout prints two places: the .XX general band.
_XX = printed_band_mm(2)
if CBORE_DIA - _XX <= SCREW_HEAD_DIA:
    raise AssertionError("C stop bar counterbore does not clear the #8 head")
if CBORE_DEPTH - _XX < SCREW_HEAD_H:
    raise AssertionError("#8 head stands proud of the C stop bar counterbore")
# Screw stations: the bar's clearance holes and the box's taps are drilled to
# the same numbers on two parts. Each part holds half the radial clearance on
# each axis, so the worst diagonal pair still passes the screw.
SCREW_RADIAL_CLEARANCE = (CLEARANCE_DIA - THREAD_MAJOR_MM[SCREW_THREAD]) / 2.0
SCREW_POSITION_BAND = (0.10, -0.10)  # (upper, lower), each part, each axis
if 2.0 * (2.0 * SCREW_POSITION_BAND[0] ** 2) ** 0.5 >= SCREW_RADIAL_CLEARANCE:
    raise AssertionError("C stop bar screw stations can bind the screws")
# drawing-guidelines.md rule 17 (walls and webs) walls at worst case: shortest bar, hole high or low in its band,
# largest counterbore.
_CBORE_R_MAX = (CBORE_DIA + _XX) / 2.0
if (BAR_HEIGHT + BAR_HEIGHT_BAND[1]) - (SCREW_Y + SCREW_POSITION_BAND[0]) - _CBORE_R_MAX < 2.0:
    raise AssertionError("counterbore wall to the bar top under drawing-guidelines.md rule 17 (walls and webs)")
if (SCREW_Y + SCREW_POSITION_BAND[1]) - _CBORE_R_MAX < 2.0:
    raise AssertionError("counterbore wall to the bar bottom under drawing-guidelines.md rule 17 (walls and webs)")
SCREW_HOLE_SPEC = HoleSpec(
    "counterbore_socket",
    "#8",
    overrides_mm={
        "HoleDiameter": CLEARANCE_DIA,
        "CounterBoreDiameter": CBORE_DIA,
        "CounterBoreDepth": CBORE_DEPTH,
    },
)
# Thread the screw reaches into the box wall past the bar's counterbore floor.
SCREW_ENGAGEMENT = SCREW_LENGTH - (BAR_WIDTH - CBORE_DEPTH)
if not 1.5 * THREAD_MAJOR_MM[SCREW_THREAD] <= SCREW_ENGAGEMENT:
    raise AssertionError("#8-32 x 5/8 screw engages under one and a half diameters")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {"BarLength", "BarHeight"},
    "Bar": {"BarWidth"},
    "ScrewHoles": {"HoleLeftX", "HoleRightX", "HoleY"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BarProfile": {"BarLength": 1, "BarHeight": 3},
    "Bar": {"BarWidth": 1},
    "ScrewHoles": {"HoleLeftX": 2, "HoleRightX": 2, "HoleY": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked C stop bar dimension needs authored places")
# (feature, dimension) -> (upper, lower) native band.
DRAWING_BANDS: dict[tuple[str, str], tuple[float, float]] = {
    ("BarProfile", "BarHeight"): BAR_HEIGHT_BAND,
    ("ScrewHoles", "HoleLeftX"): SCREW_POSITION_BAND,
    ("ScrewHoles", "HoleRightX"): SCREW_POSITION_BAND,
    ("ScrewHoles", "HoleY"): SCREW_POSITION_BAND,
}

SURFACE_FINISHES = ()
DRAWING_NOTES = "NO NICKS, BURRS OR STAMPING ON THE TOP FACE."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"

