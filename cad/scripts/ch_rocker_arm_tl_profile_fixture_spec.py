r"""Pure-data contract for the rocker arm profile fixture (MHA-CH-006-TL-02).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). The S3/S4
rocker-arm profile setups (prechips rocker plan) seat the arm's lower strap
face on twelve bonded pads, its lower hub face on a shim stack over a bonded
hub stand, its pivot bore on the pivot screw's shoulder (reamed locating bore)
and its rod hole on a bonded diamond pin (reamed pin hole). Four bonded rail
rests carry the raw rail undersides on per-blank shim stacks. One is made.

Construction (shop-additions r3 section 5): a milled steel plate; the pads and
the hub stand are lapped on top and bonded top-down on one granite reference
over gauge stacks, so their tops -- not the pocket floors -- set the heights.
The rail rests seat on their pocket floors. The print states only the results
(the route stays here and in the part's process); nothing is hardened and
nothing is ground (the shop has no surface grinder).

Frame: rocker frame A of the prechips rocker inventory -- the pivot axis (the
locating bore axis) at the origin, the arm's upper hub face at Z0, +X toward
the rod end, +Z up out of the plate. Model coordinates ARE frame A, so prechips
poses read straight off this part. Every plan location prints from the
locating bore axis.
"""

from __future__ import annotations

import math

from _printed_tolerance import drilled_oversize_mm, printed_band_mm
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_notes as rocker_notes
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace
from _hole_spec import CLEARANCE_MM, TAP_DRILL_MM, THREAD_MAJOR_MM, HoleSpec

_XXX = printed_band_mm(3)
_XX = printed_band_mm(2)
_X = printed_band_mm(1)
_DRILLED_PLUS = drilled_oversize_mm()

# --- Heights (frame A Z) ------------------------------------------------------
# The arm's lower strap face: the strap sits at the hub's mid-length, so its
# lower face is half a hub plus half a strap below the upper hub face. Every pad
# top lies on it, and every height below is built down from it.
PAD_TOP_Z = -(rocker.HUB_LENGTH / 2.0 + rocker.ARM_THICKNESS / 2.0)
PLATE_TOP_Z = -15.0
PLATE_THICK = 25.4  # 1 in plate, as rolled
PLATE_BOTTOM_Z = PLATE_TOP_Z - PLATE_THICK
# Pad tops above the plate top: the gauge stack under the granite.
PLATE_DROP = PAD_TOP_Z - PLATE_TOP_Z

# --- Plate outline ----------------------------------------------------------------
PLATE_WEST_X = -180.0
PLATE_EAST_X = 180.0
PLATE_SOUTH_Y = -70.0
PLATE_NORTH_Y = 75.0
PLATE_LENGTH = PLATE_EAST_X - PLATE_WEST_X
PLATE_WIDTH = PLATE_NORTH_Y - PLATE_SOUTH_Y

# --- Bonded-part fits -----------------------------------------------------------
# Every pocket size and every bonded part's width and height print at three
# places, so each moves by the title block's .XXX band (part lengths print at
# one place, below). Each part is centred in its pocket, so its bond line is
# half the pocket-less-part width: the largest part in the smallest pocket
# keeps BOND_LINE_MIN a side (the inventory's 0.05 a side cannot survive two
# .XXX bands; cross-vendor review of PR 1252: 0.14 left 0.010 a side).
POCKET_SIDE_CLEARANCE = 0.15
REST_CLEARANCE = 0.15
BOND_LINE_MIN = 0.02


def _side_bond_line_min(pocket: float, part: float) -> float:
    """Bond line a side for a part centred in its pocket, both at .XXX."""
    return round(((pocket - _XXX) - (part + _XXX)) / 2.0, 9)


# Pocket corners are left to the cutter (any radius up to a full-round end),
# so every bonded part ends short of its pocket's end radius. A part's length
# locates nothing (each part is centred in its pocket), so it prints at one
# place (codex review of run 20261007T205522920Z: .XXX lengths were
# over-specified): the pocket's straight run less this end gap at each end,
# rounded down to the tenth. The worst case is the longest part in the
# shortest pocket with the widest end radius, and it still ends clear.
POCKET_END_GAP = 0.55
PART_LENGTH_PLACES = 1


def _part_length(pocket_length: float, pocket_width: float) -> float:
    room = pocket_length - pocket_width - 2.0 * POCKET_END_GAP
    return math.floor(room * 10.0 + 1e-9) / 10.0


def _end_gap_min(pocket_length: float, pocket_width: float, part_length: float) -> float:
    return round(((pocket_length - _XXX) - (pocket_width + _XXX) - (part_length + _X)) / 2.0, 9)


# Pads: inventory stations, +X side (tag, station west X, station length, pad
# south Y, pad width). B pads mirror them about the pivot axis. Each pocket is
# its station less an end wall at each end, so neighbouring pockets keep a 2 mm
# web at the worst case of their .XXX sizes and locations (rule 12 target).
# Each pad stands at least PAD_OUTLINE_MARGIN inside the arm's finished outline
# (the inventory's "~6 mm inside, outside the end mills' swept bands") and is
# at least 2 mm wide at the .XXX band. The inventory's 20 mm pads lost width to
# the strap's curvature (A4/B4 1.9, A5/B5 1.4); the pads now end short of their
# pocket ends, so those two take the width the shorter span leaves.
_RIGHT_STATIONS = (
    ("1", 10.0, 20.0, -1.35, 3.3),
    ("2", 30.0, 20.0, -0.35, 2.8),
    ("3", 50.0, 20.0, 1.15, 2.3),
    ("4", 70.0, 20.0, 2.85, 2.3),
    ("5", 90.0, 20.0, 5.17, 2.15),
    ("6", 110.0, 12.0, 7.25, 2.3),
)
POCKET_END_WALL = 1.25
PAD_HEIGHT = 11.6
PAD_POCKET_DEPTH = 2.0
PAD_OUTLINE_MARGIN = 6.0

# (tag, centre X, centre Y, length X, width Y) per pocket and per pad.
PAD_POCKETS: tuple[tuple[str, float, float, float, float], ...] = tuple(
    (
        f"{side}{tag}",
        sign * (x0 + length / 2.0),
        y0 + width / 2.0,
        length - 2.0 * POCKET_END_WALL,
        width + 2.0 * POCKET_SIDE_CLEARANCE,
    )
    for side, sign in (("A", 1.0), ("B", -1.0))
    for tag, x0, length, y0, width in _RIGHT_STATIONS
)
PADS: tuple[tuple[str, float, float, float, float], ...] = tuple(
    (
        tag,
        cx,
        cy,
        _part_length(length, width),
        width - 2.0 * POCKET_SIDE_CLEARANCE,
    )
    for tag, cx, cy, length, width in PAD_POCKETS
)
if min(width for *_head, width in PADS) - _XXX < 2.0:
    raise AssertionError("a pad is under 2 mm wide at the .XXX band (rule 12 target)")
# Web between neighbouring pockets: both length bands and both location bands.
if 2.0 * POCKET_END_WALL - 3.0 * _XXX < 2.0:
    raise AssertionError("a web between pad pockets is under 2 mm at the worst case")


def _outline_margin(cx: float, cy: float, length: float, width: float) -> float:
    """Least radial distance from a pad's corners to the arm's two outline arcs
    (concentric about frame-A (0, CENTER_Y - PIVOT_MID_Y))."""
    centre_y = rocker.CENTER_Y - rocker.PIVOT_MID_Y
    radii = [
        math.hypot(cx + sx * length / 2.0, cy + sy * width / 2.0 - centre_y)
        for sx in (-1.0, 1.0)
        for sy in (-1.0, 1.0)
    ]
    return min(min(radii) - rocker.R_TOP, rocker.R_BOTTOM - max(radii))


PAD_OUTLINE_MARGIN_MIN = min(_outline_margin(*pad[1:]) for pad in PADS)
if PAD_OUTLINE_MARGIN_MIN < PAD_OUTLINE_MARGIN:
    raise AssertionError(
        f"a pad stands {PAD_OUTLINE_MARGIN_MIN:.3f} inside the arm outline, "
        f"under {PAD_OUTLINE_MARGIN}"
    )

# Pad bottoms float above the pocket floors (the tops set the height): the
# tallest pad in the shallowest pocket under the shortest printed PlateDrop
# keeps clear of the floor, and the shortest pad under the longest PlateDrop
# still stands well down into its pocket for the bond.
PAD_FLOOR_GAP_MIN = (PLATE_DROP - _XXX + PAD_POCKET_DEPTH - _XXX) - (PAD_HEIGHT + _XXX)
PAD_ENGAGEMENT_MIN = (PAD_HEIGHT - _XXX) - (PLATE_DROP + _XXX)
if PAD_FLOOR_GAP_MIN < 0.1:
    raise AssertionError(
        "a pad can bottom in its pocket before its top reaches the reference"
    )
if PAD_ENGAGEMENT_MIN < 1.0:
    raise AssertionError("a pad can stand too shallow in its pocket to bond")
# Every locating chain is held to a quarter of the rocker band it controls
# (FixtureCAD/Main: 25 % of the parent band, the share chosen here).
PARENT_BAND_SHARE = 0.25
# The pad tops' PlateDrop sets no rocker band in Z: the profile is cut in plan,
# and the strap's height over the plate is no rocker dimension. The rocker
# band it reaches is the top edge (ch_rocker_arm_spec.TOP_EDGE_BAND), through
# tilt: two neighbouring pads at opposite ends of the .XXX band tip the strap,
# and the rod tip's plan shortening stays under its share of that band.
_PAD_PITCH_MIN = min(
    math.hypot(a[1] - b[1], a[2] - b[2])
    for i, a in enumerate(PADS)
    for b in PADS[i + 1 :]
)
PAD_TILT_SWING_MAX = rocker.ROD_TIP_X * (
    1.0 - math.cos(math.atan(2.0 * _XXX / _PAD_PITCH_MIN))
)
if PAD_TILT_SWING_MAX > PARENT_BAND_SHARE * (
    rocker.TOP_EDGE_BAND[0] - rocker.TOP_EDGE_BAND[1]
):
    raise AssertionError("pad-top disagreement can tilt the rod tip off its band")

# Rail rests: inventory pockets (tag, west X, south Y, length X, width Y). Each
# rest seats on its pocket floor; the per-blank shim stacks on top are loose.
_REST_POCKETS = (
    ("C1", 60.0, 32.2, 20.0, 4.3),
    ("C2", -80.0, 32.2, 20.0, 4.3),
    ("C3", 60.0, -27.5, 20.0, 5.0),
    ("C4", -80.0, -27.5, 20.0, 5.0),
)
REST_HEIGHT = 4.0
REST_POCKET_DEPTH = 1.0
# The rest tops above the plate top print at two places: a rest seated on its
# floor stacks its .XXX height on its pocket's .XXX depth, and that stack sits
# inside the .XX band, so the three sizes never disagree.
REST_TOP_HEIGHT = REST_HEIGHT - REST_POCKET_DEPTH
REST_TOP_Z = PLATE_TOP_Z + REST_TOP_HEIGHT
if 2.0 * _XXX > _XX:
    raise AssertionError("a seated rail rest can miss its printed top height")
REST_POCKETS: tuple[tuple[str, float, float, float, float], ...] = tuple(
    (tag, x0 + length / 2.0, y0 + width / 2.0, length, width)
    for tag, x0, y0, length, width in _REST_POCKETS
)
RESTS: tuple[tuple[str, float, float, float, float], ...] = tuple(
    (tag, cx, cy, _part_length(length, width), width - 2.0 * REST_CLEARANCE)
    for tag, cx, cy, length, width in REST_POCKETS
)
PART_END_GAP_MIN = min(
    _end_gap_min(pocket[3], pocket[4], part[3])
    for pockets, parts in ((PAD_POCKETS, PADS), (REST_POCKETS, RESTS))
    for pocket, part in zip(pockets, parts, strict=True)
)
if PART_END_GAP_MIN < BOND_LINE_MIN:
    raise AssertionError("a bonded part can reach its pocket's end radius")
PART_BOND_LINE_MIN = min(
    _side_bond_line_min(pocket[4], part[4])
    for pockets, parts in ((PAD_POCKETS, PADS), (REST_POCKETS, RESTS))
    for pocket, part in zip(pockets, parts, strict=True)
)
if PART_BOND_LINE_MIN < BOND_LINE_MIN:
    raise AssertionError("a bonded part can bind in its pocket at the .XXX bands")

# --- Hub stand (FixtureCAD ruling B, revised) --------------------------------------
# A relieved tube: its annulus carries the lower hub face through the hub shim
# stack and its bore clears the pivot screw shoulder. It bonds top-down on a
# gauge stack STAND_DROP below the pad reference, in a counterbore round the
# locating bore. StandDrop prints directly from the pad tops (no chain through
# the plate) at the general .XXX band: the hub shim stack is cut to the
# measured stand and arm, so the stand's band reaches the hub only through that
# fit-up and takes no share of a rocker band (ruling B's +/-0.02 was a
# relaxation ceiling, not a functional need; FixtureCAD ruling after the codex
# review of run 20261007T205522920Z flagged the 0.04 band as over-specified).
# The strap rests on the pads, so the hub's lower face hangs below the pad
# plane by half the hub less half the strap. Both are the parent's printed
# bands: the hub length's own (upper, lower) and the strap's two-place general
# band (ch_rocker_arm_notes "STRAP 2.50 THICK"), the hub centred on the strap.
# The drop is set so the shim stack stays non-negative for every accepted arm
# (cross-vendor review of PR 1252: nominal-strap limits let a 1.99 strap on a
# long hub lift the arm off its pads); the shop's shim assortment covers
# HUB_SHIM_GAP_MAX.
_STRAP_BAND = printed_band_mm(rocker_notes.DEFAULT_DRAWING_PRECISION)
_HUB_STEP_MAX = (
    rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[0] - (rocker.ARM_THICKNESS - _STRAP_BAND)
) / 2.0
_HUB_STEP_MIN = (
    rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[1] - (rocker.ARM_THICKNESS + _STRAP_BAND)
) / 2.0
STAND_DROP = 2.700
STAND_DROP_BAND = (_XXX, -_XXX)  # the title block's .XXX, not printed explicitly
STAND_TOP_Z = PAD_TOP_Z - STAND_DROP
STAND_OD = 12.5
STAND_BORE = 8.0  # drilled: the title block's DRILLED HOLES band
# StandHeight loses what StandDrop gains, so the floor gap and the bond
# engagement below hold in the same counterbore.
STAND_HEIGHT = 9.0
STAND_POCKET_DIA = 12.8
STAND_POCKET_DEPTH = 2.2
# The hub shim stack never goes negative: the highest stand still sits below
# the lowest accepted hub face when the strap rests on the pads.
HUB_SHIM_GAP_MIN = STAND_DROP + STAND_DROP_BAND[1] - _HUB_STEP_MAX
HUB_SHIM_GAP_MAX = STAND_DROP + STAND_DROP_BAND[0] - _HUB_STEP_MIN
if HUB_SHIM_GAP_MIN < 0.0:
    raise AssertionError("the hub stand can lift the strap off the pads")
# Where the stand annulus reaches past the hub it keeps 2 mm of air under the
# strap's lower face (the pad plane).
STRAP_AIR_MIN = STAND_DROP + STAND_DROP_BAND[1]
if STRAP_AIR_MIN < 2.0:
    raise AssertionError("the hub stand comes within 2 mm of the strap")
if _side_bond_line_min(STAND_POCKET_DIA, STAND_OD) < BOND_LINE_MIN:
    raise AssertionError("the hub stand can bind in its counterbore")
STAND_WALL_MIN = ((STAND_OD - _XXX) - (STAND_BORE + _DRILLED_PLUS)) / 2.0
if STAND_WALL_MIN < 2.0:
    raise AssertionError("hub stand wall is below the rule-12 target")
if STAND_BORE + _DRILLED_PLUS >= rocker.HUB_DIA:
    raise AssertionError("the hub can drop into the stand bore")
# As the pads: clear of the counterbore floor at the worst printed PlateDrop,
# StandDrop, depth and height (codex review of run 20261007T202010454Z: at
# 9.5 high it could bottom by 0.016), and still well down into it for the bond.
STAND_FLOOR_GAP_MIN = (
    (PLATE_DROP - _XXX) - (STAND_DROP + STAND_DROP_BAND[0]) + STAND_POCKET_DEPTH - _XXX
) - (STAND_HEIGHT + _XXX)
STAND_ENGAGEMENT_MIN = (STAND_HEIGHT - _XXX) - (
    (PLATE_DROP + _XXX) - (STAND_DROP + STAND_DROP_BAND[1])
)
if STAND_FLOOR_GAP_MIN < 0.1:
    raise AssertionError("the hub stand can bottom in its counterbore")
if STAND_ENGAGEMENT_MIN < 1.0:
    raise AssertionError("the hub stand can stand too shallow in its counterbore to bond")

# --- Locating bore and pivot tap (agreed with the MHA-CH-006-TL pivot screw) ------
# Reamed H7 for the pivot screw's shoulder; the screw's #10-24 tail runs into
# the tap below the bore floor (the inventory's M5 maps to #10-24 UNC-2B).
LOCATING_BORE_DIA = rocker.PIVOT_HOLE_DIA
LOCATING_BORE_BAND = (0.012, 0.0)
LOCATING_BORE_DEPTH = 6.0  # from the plate top; floor at Z-21
LOCATING_BORE_FLOOR_Z = PLATE_TOP_Z - LOCATING_BORE_DEPTH
PIVOT_TAP_THREAD_DEPTH = 10.0  # full thread from the bore floor, to Z-31
PIVOT_TAP_DRILL_DEPTH = 13.0
PIVOT_TAP_SPEC = HoleSpec(
    "tapped",
    "#10-24",
    end="blind",
    depth_mm=PIVOT_TAP_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": PIVOT_TAP_THREAD_DEPTH},
)
PIVOT_TAP_DRILL_DIA = TAP_DRILL_MM[PIVOT_TAP_SPEC.size]
# The 118-degree point a blind drill leaves below its printed depth.
_DRILL_POINT_HALF_ANGLE = math.radians(59.0)


def _blind_drill_floor_wall(depth_max: float, drill_dia: float) -> float:
    """Steel left under a blind drill's point: the thinnest printed plate
    (.X) less the deepest printed depth and the point (codex review of run
    20261007T215120209Z: the stud guard ignored both)."""
    point = drill_dia / 2.0 / math.tan(_DRILL_POINT_HALF_ANGLE)
    return (PLATE_THICK - _X) - depth_max - point


if (
    _blind_drill_floor_wall(
        LOCATING_BORE_DEPTH + _XX + PIVOT_TAP_DRILL_DEPTH + _XX, PIVOT_TAP_DRILL_DIA
    )
    < 2.0
):
    raise AssertionError("pivot tap drill point leaves under the rule-12 floor wall")

# --- Rod-pin hole (agreed with the MHA-CH-006-TL diamond pin) ------------------------
ROD_PIN_HOLE_DIA = 3.0
ROD_PIN_HOLE_BAND = (0.010, 0.0)
ROD_PIN_HOLE_DEPTH = 7.0
# The rocker's rod hole from the pivot, at the schedule's three places: the
# model, the print and the export carry one value (the rounding moves it under
# 0.0005, against its +/-0.015 band).
ROD_PIN_HOLE_XY = tuple(
    round(value, 3) for value in (rocker.ROD_HOLE_X, rocker.ROD_HOLE_Y - rocker.PIVOT_MID_Y)
)
# The diamond pin turns the arm about the locating bore, so the ream's X and Y
# from the bore axis are its direct functional dimensions. At the schedule's
# .XXX (+/-0.13 a coordinate) it could wander over a circle of 0.37, wider than
# the rocker rod hole's own 0.20 position zone (ch_rocker_arm_spec
# GEOMETRIC_TOLERANCES_MM) that it locates. Each coordinate takes its own band:
# PARENT_BAND_SHARE (25 %) of the parent zone, so the band's worst corner stays
# inside a quarter of that zone's radius, and the arm's turn from it swings the
# rod tip under a quarter of the top-edge band. The features export carries X
# as `station` and Y as `height`, both measured from the locating-bore centre
# (`height_from = "locating_bore"`).
ROD_PIN_XY_BAND = (0.015, -0.015)
_ROD_HOLE_ZONE_RADIUS = (
    float(rocker.GEOMETRIC_TOLERANCES_MM["rod-pin hole position"]) / 2.0
)
ROD_PIN_POSITION_ERROR_MAX = math.hypot(ROD_PIN_XY_BAND[0], ROD_PIN_XY_BAND[0])
if ROD_PIN_POSITION_ERROR_MAX > PARENT_BAND_SHARE * _ROD_HOLE_ZONE_RADIUS:
    raise AssertionError("the rod-pin ream can wander past its share of the rod-hole zone")
ROD_PIN_TIP_SWING_MAX = (
    ROD_PIN_POSITION_ERROR_MAX * rocker.ROD_TIP_X / math.hypot(*ROD_PIN_HOLE_XY)
)
if ROD_PIN_TIP_SWING_MAX > PARENT_BAND_SHARE * (
    rocker.TOP_EDGE_BAND[0] - rocker.TOP_EDGE_BAND[1]
):
    raise AssertionError("the rod-pin ream can swing the rod tip off its band")
ROD_PIN_XY_PRINTED = tuple(
    f"{value:.3f} \u00b1{ROD_PIN_XY_BAND[0]:.3f}" for value in ROD_PIN_HOLE_XY
)

# --- Hold-down and clamp-stud holes ------------------------------------------------
# PM-30MV table: 14 mm T-slots on 63.5 centres. The 9/16 T-slot clamping kit's
# T-nuts are tapped 1/2-13 (vendor interface, kept), so the hold-downs are
# 1/2-13 socket head cap screws in counterbored clearance holes over the two
# outer slots, at each end of the plate.
HOLD_DOWN_SLOT_PITCH = 63.5
HOLD_DOWN_X = 165.0
_PLATE_MID_Y = (PLATE_NORTH_Y + PLATE_SOUTH_Y) / 2.0
HOLD_DOWN_YS = (
    _PLATE_MID_Y - HOLD_DOWN_SLOT_PITCH / 2.0,
    _PLATE_MID_Y + HOLD_DOWN_SLOT_PITCH / 2.0,
)
HOLD_DOWN_POINTS = tuple(
    (x, y) for y in HOLD_DOWN_YS for x in (-HOLD_DOWN_X, HOLD_DOWN_X)
)
# Locations (codex review of run 20261007T212104521Z: three places was
# over-specified). Along the slots (X) the T-nuts slide, so X prints at one
# place. Across them (Y) the table fixes the 63.5 pitch: opposite errors at
# the two holes' band must stay inside both screws' radial clearance, which
# rules out .X (1.6 against 1.59), so Y prints at two places.
HOLD_DOWN_X_PLACES = 1
HOLD_DOWN_Y_PLACES = 2
_HOLD_DOWN_SCREW_MAJOR = THREAD_MAJOR_MM["1/2-13"]
# 1/2-13 socket head cap screw, ASME B18.3: head 0.750 dia x 0.500 high.
HOLD_DOWN_SCREW_HEAD_DIA = 0.750 * 25.4
HOLD_DOWN_SCREW_HEAD_H = 0.500 * 25.4
HOLD_DOWN_CLEARANCE_DIA = CLEARANCE_MM[("1/2", "normal")]
HOLD_DOWN_CBORE_DIA = 20.64
HOLD_DOWN_CBORE_DEPTH = 13.5
HOLD_DOWN_HOLE_SPEC = HoleSpec(
    "counterbore_socket",
    "1/2",
    overrides_mm={
        "HoleDiameter": HOLD_DOWN_CLEARANCE_DIA,
        "CounterBoreDiameter": HOLD_DOWN_CBORE_DIA,
        "CounterBoreDepth": HOLD_DOWN_CBORE_DEPTH,
    },
)
if HOLD_DOWN_CBORE_DEPTH - _XX - HOLD_DOWN_SCREW_HEAD_H < 0.1:
    raise AssertionError("hold-down screw head can stand proud of the plate")
if HOLD_DOWN_CBORE_DIA - _XX - HOLD_DOWN_SCREW_HEAD_DIA < 0.5:
    raise AssertionError("hold-down counterbore does not clear the screw head")

# Strap-clamp studs either side of the S3 clamp toes (inventory: 3/8-16 studs).
CLAMP_STUD_SPEC = HoleSpec(
    "tapped",
    "3/8-16",
    end="blind",
    depth_mm=19.5,
    overrides_mm={"ThreadDepth": 16.5},
)
CLAMP_STUD_POINTS = ((-70.0, -36.0), (70.0, -36.0), (-70.0, 45.0), (70.0, 45.0))
CLAMP_STUD_DRILL_DIA = TAP_DRILL_MM[CLAMP_STUD_SPEC.size]
_CLAMP_STUD_PITCH = 25.4 / 16.0
# Full thread at least 1.5 diameters deep at the .XX band even if the shop
# counts one incomplete thread inside the printed depth (codex review of run
# 20261007T211013161Z: 15.00 left 0.2 over 1.5 D at the band), and the tap
# drill stops well inside the plate.
if (
    CLAMP_STUD_SPEC.overrides_mm["ThreadDepth"] - _XX - _CLAMP_STUD_PITCH
    < 1.5 * THREAD_MAJOR_MM[CLAMP_STUD_SPEC.size]
):
    raise AssertionError("clamp-stud thread engages under 1.5 diameters")
if 2.0 * _XX > HOLD_DOWN_CLEARANCE_DIA - _HOLD_DOWN_SCREW_MAJOR:
    raise AssertionError("hold-down screws can miss their T-slots at the Y band")
# The studs only anchor strap clamps, which slide to the arm: one place.
CLAMP_STUD_PLACES = 1
# Deeper would break the floor wall (run 20261007T215120209Z's 21.0 drill
# left about 0.7 under its point on the thinnest plate); 16.5 of thread still
# clears 1.5 D above, and the tap keeps 3.0 of lead.
if _blind_drill_floor_wall(CLAMP_STUD_SPEC.depth_mm + _XX, CLAMP_STUD_DRILL_DIA) < 2.0:
    raise AssertionError("clamp-stud drill point leaves under the rule-12 floor wall")


# --- Rule 12: every machined wall keeps the floor --------------------------------
def _rect_gap(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    dx = abs(a[0] - b[0]) - (a[2] + b[2]) / 2.0
    dy = abs(a[1] - b[1]) - (a[3] + b[3]) / 2.0
    if dx > 0.0 and dy > 0.0:
        return math.hypot(dx, dy)
    return max(dx, dy)


def _circle_rect_gap(
    cx: float, cy: float, r: float, rect: tuple[float, float, float, float]
) -> float:
    dx = max(abs(cx - rect[0]) - rect[2] / 2.0, 0.0)
    dy = max(abs(cy - rect[1]) - rect[3] / 2.0, 0.0)
    return math.hypot(dx, dy) - r


_RECTS = [
    (cx, cy, length + _XXX, width + _XXX)
    for _tag, cx, cy, length, width in (*PAD_POCKETS, *REST_POCKETS)
]
_ROUNDS = [
    (0.0, 0.0, (STAND_POCKET_DIA + _XXX) / 2.0),
    (*ROD_PIN_HOLE_XY, (ROD_PIN_HOLE_DIA + ROD_PIN_HOLE_BAND[0]) / 2.0),
    *(
        (x, y, (HOLD_DOWN_CBORE_DIA + _XX) / 2.0 + math.hypot(_X, _XX))
        for x, y in HOLD_DOWN_POINTS
    ),
    *(
        (x, y, THREAD_MAJOR_MM[CLAMP_STUD_SPEC.size] / 2.0 + math.hypot(_X, _X))
        for x, y in CLAMP_STUD_POINTS
    ),
]
_OUTLINE = (
    (PLATE_WEST_X + PLATE_EAST_X) / 2.0,
    _PLATE_MID_Y,
    PLATE_LENGTH,
    PLATE_WIDTH,
)
WALL_MIN = min(
    *(_rect_gap(a, b) for i, a in enumerate(_RECTS) for b in _RECTS[i + 1 :]),
    *(_circle_rect_gap(cx, cy, r, rect) for rect in _RECTS for cx, cy, r in _ROUNDS),
    *(
        math.hypot(a[0] - b[0], a[1] - b[1]) - a[2] - b[2]
        for i, a in enumerate(_ROUNDS)
        for b in _ROUNDS[i + 1 :]
    ),
    *(
        min(
            _OUTLINE[2] / 2.0 - abs(x - _OUTLINE[0]) - half,
            _OUTLINE[3] / 2.0 - abs(y - _OUTLINE[1]) - half_w,
        )
        for x, y, half, half_w in (
            *((cx, cy, length / 2.0, width / 2.0) for cx, cy, length, width in _RECTS),
            *((cx, cy, r, r) for cx, cy, r in _ROUNDS),
        )
    ),
)
if WALL_MIN < 2.0:
    raise AssertionError(f"a plate wall is {WALL_MIN:.2f} mm, below the rule-12 target")

# --- Drawing ----------------------------------------------------------------------
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateLength", "PlateWidth", "PlateWestX", "PlateSouthY"},
    "Plate": {"PlateThick", "PlateDrop"},
    "Stand": {"StandDrop"},
    "Rests": {"RestTopHeight"},
    "StandPocketProfile": {"StandPocketDia"},
    "StandPocket": {"StandPocketDepth"},
    "LocatingBoreProfile": {"LocatingBoreDia"},
    "LocatingBore": {"LocatingBoreDepth"},
    "RodPinHoleProfile": {"RodPinHoleDia"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateProfile": {
        "PlateLength": 1,
        "PlateWidth": 1,
        "PlateWestX": 1,
        "PlateSouthY": 1,
    },
    "Plate": {"PlateThick": 1, "PlateDrop": 3},
    "Stand": {"StandDrop": 3},
    "Rests": {"RestTopHeight": 2},
    "StandPocketProfile": {"StandPocketDia": 3},
    "StandPocket": {"StandPocketDepth": 3},
    "LocatingBoreProfile": {"LocatingBoreDia": 3},
    "LocatingBore": {"LocatingBoreDepth": 2},
    "RodPinHoleProfile": {"RodPinHoleDia": 3, "RodPinHoleX": 3, "RodPinHoleY": 3},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
_MARKED = set().union(*DRAWING_DIMENSIONS.values())
# What the sheet imports, and must read back at the authored places.
MARKED_PRECISION_BY_NAME: dict[str, int] = {
    name: places for name, places in DRAWING_PRECISION_BY_NAME.items() if name in _MARKED
}
# A schedule cell that carries its own band is a model dimension too (policy
# rule 2: the model owns the band and its places; cross-vendor review of PR
# 1252). The build tolerances it natively and proves the printed cell is the
# model's value, places and band; the sheet prints it in the schedule, not as
# a marked dimension. Row tag -> (X cell, Y cell) as (feature, dimension).
SCHEDULE_CELL_DIMENSIONS: dict[str, tuple[tuple[str, str], tuple[str, str]]] = {
    "P": (("RodPinHoleProfile", "RodPinHoleX"), ("RodPinHoleProfile", "RodPinHoleY")),
}
if ROD_PIN_XY_BAND[1] != -ROD_PIN_XY_BAND[0]:
    raise AssertionError("the rod-pin coordinates print a symmetric band")
EXPLICIT_SYMMETRIC_TOLERANCES_MM: dict[tuple[str, str], float] = {
    cell: ROD_PIN_XY_BAND[0] for cell in SCHEDULE_CELL_DIMENSIONS["P"]
}
if set(DRAWING_PRECISION_BY_NAME) != _MARKED | {
    name for cells in SCHEDULE_CELL_DIMENSIONS.values() for _feature, name in cells
}:
    raise AssertionError(
        "every marked or scheduled profile-fixture dimension needs authored places"
    )
DIMENSION_CALLOUTS = {"LocatingBoreDia": "REAM", "RodPinHoleDia": "REAM"}

# Schedules (sheets two and three): every pocket and hole is tagged on the
# sheet-two plan and located here from the locating bore axis; every bonded part
# is sized. Three places (the .XXX band) unless a row states its own places.
SCHEDULE_PLACES = 3
SECTION_LABEL = "D"
DETAIL_LABEL = "E"


def _mm(value: float, places: int = SCHEDULE_PLACES) -> str:
    return f"{value:.{places}f}"


# Every row locates its feature's centre, and the axes read as the TAGS plan
# is drawn (codex review of run 20261007T204247920Z).
FEATURE_SCHEDULE_TITLE = (
    "FEATURE SCHEDULE: CENTRES FROM BORE L AXIS, +X RIGHT AND +Y UP AS ON SHEET 2"
)
FEATURE_SCHEDULE_HEADER = (
    "TAG", "FEATURE", "CENTRE X", "CENTRE Y", "LENGTH X", "WIDTH Y", "DEPTH"
)
FEATURE_SCHEDULE: tuple[tuple[str, ...], ...] = (
    (
        "L",
        "LOCATING BORE",
        _mm(0.0),
        _mm(0.0),
        "-",
        "-",
        f"SEE {SECTION_LABEL}-{SECTION_LABEL}",
    ),
    (
        "P",
        "ROD PIN HOLE",
        *ROD_PIN_XY_PRINTED,
        "-",
        "-",
        # The pin seats on its collar, not the hole floor: the depth only
        # clears the shank, so it prints at one place (.X).
        _mm(ROD_PIN_HOLE_DEPTH, 1),
    ),
    *(
        (
            tag,
            "PAD POCKET",
            _mm(cx),
            _mm(cy),
            _mm(length),
            _mm(width),
            _mm(PAD_POCKET_DEPTH),
        )
        for tag, cx, cy, length, width in PAD_POCKETS
    ),
    *(
        (
            tag,
            "REST POCKET",
            _mm(cx),
            _mm(cy),
            _mm(length),
            _mm(width),
            _mm(REST_POCKET_DEPTH),
        )
        for tag, cx, cy, length, width in REST_POCKETS
    ),
    *(
        (
            f"H{index}",
            "HOLD-DOWN",
            _mm(x, HOLD_DOWN_X_PLACES),
            _mm(y, HOLD_DOWN_Y_PLACES),
            "-",
            "-",
            "THRU",
        )
        for index, (x, y) in enumerate(HOLD_DOWN_POINTS, start=1)
    ),
    *(
        (
            f"S{index}",
            "STUD TAP",
            _mm(x, CLAMP_STUD_PLACES),
            _mm(y, CLAMP_STUD_PLACES),
            "-",
            "-",
            "-",
        )
        for index, (x, y) in enumerate(CLAMP_STUD_POINTS, start=1)
    ),
)
_PAD_STOCK = {3.3: "O1 FLAT 3/16 X 1/2"}
PART_SCHEDULE_TITLE = "BONDED PART SCHEDULE, SIZES BEFORE BONDING"
PART_SCHEDULE_HEADER = ("TAG", "PART", "STOCK", "LENGTH X", "WIDTH Y", "HEIGHT")
PART_SCHEDULE: tuple[tuple[str, ...], ...] = (
    *(
        (
            f"{a_tag}, {b_tag}",
            "PAD",
            _PAD_STOCK.get(round(width, 3), "O1 FLAT 1/8 X 1/2"),
            _mm(length, PART_LENGTH_PLACES),
            _mm(width),
            _mm(PAD_HEIGHT),
        )
        for (a_tag, _ax, _ay, length, width), (b_tag, *_rest) in zip(
            PADS[:6], PADS[6:], strict=True
        )
    ),
    *(
        (
            f"{a[0]}, {b[0]}",
            "RAIL REST",
            "O1 FLAT 3/16 X 1",
            _mm(a[3], PART_LENGTH_PLACES),
            _mm(a[4]),
            _mm(REST_HEIGHT),
        )
        for a, b in ((RESTS[0], RESTS[1]), (RESTS[2], RESTS[3]))
    ),
    (
        "L",
        "HUB STAND",
        "4140 HT BAR 1/2",
        f"OD {_mm(STAND_OD)}",
        f"DRILL \u00d8{STAND_BORE:.2f}",
        _mm(STAND_HEIGHT),
    ),
)

SURFACE_FINISHES = ()
BUILT_UP_PERMISSION_NOTE = (
    "BUILT-UP PART: PADS, HUB STAND AND RAIL RESTS ARE BONDED INTO THEIR POCKETS."
)
DRAWING_NOTES = "\n".join(
    (
        BUILT_UP_PERMISSION_NOTE,
        "EACH PART CENTRED IN ITS POCKET; RAIL RESTS SEAT ON THEIR POCKET FLOORS.",
        "PAD AND HUB STAND TOPS AT THEIR PRINTED HEIGHTS; THEIR POCKET FLOORS CLEAR.",
        "PLAN LOCATIONS FROM BORE L AXIS: SEE TAGS AND SCHEDULES, SHEETS TWO AND THREE.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"

# --- Exported requirement features (prechips features.toml) ---------------------------
_DOWN = ([0.0, 0.0, -1.0], ("__frame__",))
_UP = ([0.0, 0.0, 1.0], ("__frame__",))
_PAD_PLANE_SOURCES = (
    "PAD_TOP_Z",
    ("ch_rocker_arm_spec", "HUB_LENGTH"),
    ("ch_rocker_arm_spec", "ARM_THICKNESS"),
)
EXPORT_FEATURES: dict[str, ExportFeature] = {
    "locating_bore": ExportFeature(
        kind="hole",
        faces=(CylinderFace(LOCATING_BORE_DIA, contains_x_mm=0.0, contains_y_mm=0.0),),
        requirements=("dia",),
        fields={
            "at": ([0.0, 0.0, PLATE_TOP_Z], ("PLATE_TOP_Z",)),
            "axis": _DOWN,
            "dia": (
                limits(LOCATING_BORE_DIA, 3, LOCATING_BORE_BAND),
                (
                    "LOCATING_BORE_DIA",
                    "LOCATING_BORE_BAND",
                    ("ch_rocker_arm_spec", "PIVOT_HOLE_DIA"),
                ),
            ),
            "dia_nominal": (LOCATING_BORE_DIA, ("LOCATING_BORE_DIA",)),
            "depth": (limits(LOCATING_BORE_DEPTH, 2), ("LOCATING_BORE_DEPTH",)),
            "process": ("REAM", ("DIMENSION_CALLOUTS",)),
        },
        precision={"dia": 3, "depth": 2},
    ),
    "rod_pin_hole": ExportFeature(
        kind="hole",
        faces=(
            CylinderFace(
                ROD_PIN_HOLE_DIA,
                contains_x_mm=ROD_PIN_HOLE_XY[0],
                contains_y_mm=ROD_PIN_HOLE_XY[1],
            ),
        ),
        requirements=("dia", "station", "height"),
        fields={
            "at": (
                [ROD_PIN_HOLE_XY[0], ROD_PIN_HOLE_XY[1], PLATE_TOP_Z],
                (
                    "ROD_PIN_HOLE_XY",
                    "PLATE_TOP_Z",
                    ("ch_rocker_arm_spec", "ROD_HOLE_X"),
                    ("ch_rocker_arm_spec", "ROD_HOLE_Y"),
                    ("ch_rocker_arm_spec", "PIVOT_MID_Y"),
                ),
            ),
            # X and Y of the ream from the locating-bore centre, as printed.
            "station": (
                limits(ROD_PIN_HOLE_XY[0], 3, ROD_PIN_XY_BAND),
                ("ROD_PIN_HOLE_XY", "ROD_PIN_XY_BAND", "PARENT_BAND_SHARE"),
            ),
            "station_nominal": (ROD_PIN_HOLE_XY[0], ("ROD_PIN_HOLE_XY",)),
            "height": (
                limits(ROD_PIN_HOLE_XY[1], 3, ROD_PIN_XY_BAND),
                ("ROD_PIN_HOLE_XY", "ROD_PIN_XY_BAND", "PARENT_BAND_SHARE"),
            ),
            "height_nominal": (ROD_PIN_HOLE_XY[1], ("ROD_PIN_HOLE_XY",)),
            "height_from": ("locating_bore", ("ROD_PIN_HOLE_XY",)),
            "axis": _DOWN,
            "dia": (
                limits(ROD_PIN_HOLE_DIA, 3, ROD_PIN_HOLE_BAND),
                ("ROD_PIN_HOLE_DIA", "ROD_PIN_HOLE_BAND"),
            ),
            "dia_nominal": (ROD_PIN_HOLE_DIA, ("ROD_PIN_HOLE_DIA",)),
            "depth": (limits(ROD_PIN_HOLE_DEPTH, 1), ("ROD_PIN_HOLE_DEPTH",)),
            "process": ("REAM", ("DIMENSION_CALLOUTS",)),
        },
        precision={"dia": 3, "depth": 1, "station": 3, "height": 3},
    ),
    "pad_tops": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, 1.0), PAD_TOP_Z),),
        requirements=("height",),
        fields={
            "normal": _UP,
            "plane": (
                {"frame": "model", "axis": "z", "value": PAD_TOP_Z},
                _PAD_PLANE_SOURCES,
            ),
            "height": (
                limits(PLATE_DROP, 3),
                ("PLATE_DROP", "PAD_TOP_Z", "PLATE_TOP_Z"),
            ),
            "height_from": ("plate_top", ("PLATE_DROP",)),
        },
        precision={"height": 3},
    ),
    "stand_top": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, 1.0), STAND_TOP_Z),),
        requirements=("height",),
        fields={
            "normal": _UP,
            "plane": (
                {"frame": "model", "axis": "z", "value": STAND_TOP_Z},
                ("STAND_TOP_Z",),
            ),
            "height": (
                limits(STAND_DROP, 3),
                (
                    "STAND_DROP",
                    ("ch_rocker_arm_spec", "HUB_LENGTH_BAND"),
                    ("ch_rocker_arm_spec", "ARM_THICKNESS"),
                    ("ch_rocker_arm_notes", "DEFAULT_DRAWING_PRECISION"),
                ),
            ),
            "height_from": ("pad_tops", ("STAND_DROP",)),
            "dia": (limits(STAND_OD, 3), ("STAND_OD",)),
        },
        precision={"height": 3, "dia": 3},
    ),
    "rail_rest_tops": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, 1.0), REST_TOP_Z),),
        requirements=("height",),
        fields={
            "normal": _UP,
            "plane": (
                {"frame": "model", "axis": "z", "value": REST_TOP_Z},
                ("REST_TOP_Z",),
            ),
            "height": (
                limits(REST_TOP_HEIGHT, 2),
                ("REST_TOP_HEIGHT", "REST_HEIGHT", "REST_POCKET_DEPTH"),
            ),
            "height_from": ("plate_top", ("REST_TOP_HEIGHT",)),
        },
        precision={"height": 2},
    ),
    "plate_top": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, 1.0), PLATE_TOP_Z),),
        requirements=("thickness",),
        fields={
            "normal": _UP,
            "plane": (
                {"frame": "model", "axis": "z", "value": PLATE_TOP_Z},
                ("PLATE_TOP_Z",),
            ),
            "thickness": (limits(PLATE_THICK, 1), ("PLATE_THICK",)),
        },
        precision={"thickness": 1},
    ),
}
