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
from _gtol_spec import ConeFace, CylinderFace, PlanarFace
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
# Pad tops above the plate top: the gauge stack under the granite. It prints
# at three places, and the model carries exactly the printed value (FixtureCAD
# one-fact ruling: a band qualifies the model nominal, so the nominal must be
# the printed one), which leaves the plate top within 0.0005 of Z-15.
PLATE_DROP = round(PAD_TOP_Z + 15.0, 3)
PLATE_TOP_Z = PAD_TOP_Z - PLATE_DROP
PLATE_THICK = 25.4  # 1 in plate, as rolled
PLATE_BOTTOM_Z = PLATE_TOP_Z - PLATE_THICK

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


def _part_length(pocket_length: float, pocket_width: float, length_band: float = _XXX) -> float:
    """``length_band``: the pocket length's printed band; a looser one than
    the .XXX the end gap was sized for shortens the part by the difference."""
    room = pocket_length - pocket_width - 2.0 * POCKET_END_GAP - (length_band - _XXX)
    return math.floor(room * 10.0 + 1e-9) / 10.0


def _end_gap_min(
    pocket_length: float, pocket_width: float, part_length: float, length_band: float = _XXX
) -> float:
    return round(
        ((pocket_length - length_band) - (pocket_width + _XXX) - (part_length + _X)) / 2.0, 9
    )


# Pads: inventory stations, +X side (tag, station west X, station length, pad
# south Y, pad width). B pads mirror them about the pivot axis. Each pocket is
# its station less an end wall at each end. A pocket's length locates nothing
# (each pad is centred in it), so it prints at one place (codex review of run
# 20261008T010334394Z: 17.500 was over-specified); the end walls are sized so
# neighbouring pockets keep a 2 mm web at the worst case of those .X lengths
# and their .XXX locations (rule 12 target), and each pad is shortened by the
# wider band so it still ends clear.
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
PAD_POCKET_LENGTH_PLACES = 1
_PAD_POCKET_LENGTH_BAND = printed_band_mm(PAD_POCKET_LENGTH_PLACES)
POCKET_END_WALL = 1.55
PAD_HEIGHT = 11.6
PAD_POCKET_DEPTH = 2.0
PAD_OUTLINE_MARGIN = 6.0

# (tag, centre X, centre Y, length X, width Y) per pocket and per pad, each at
# the places it prints (the model carries the printed nominal).
PAD_POCKETS: tuple[tuple[str, float, float, float, float], ...] = tuple(
    (
        f"{side}{tag}",
        round(sign * (x0 + length / 2.0), 3),
        round(y0 + width / 2.0, 3),
        round(length - 2.0 * POCKET_END_WALL, 3),
        round(width + 2.0 * POCKET_SIDE_CLEARANCE, 3),
    )
    for side, sign in (("A", 1.0), ("B", -1.0))
    for tag, x0, length, y0, width in _RIGHT_STATIONS
)
PADS: tuple[tuple[str, float, float, float, float], ...] = tuple(
    (
        tag,
        cx,
        cy,
        _part_length(length, width, _PAD_POCKET_LENGTH_BAND),
        round(width - 2.0 * POCKET_SIDE_CLEARANCE, 3),
    )
    for tag, cx, cy, length, width in PAD_POCKETS
)
if min(width for *_head, width in PADS) - _XXX < 2.0:
    raise AssertionError("a pad is under 2 mm wide at the .XXX band (rule 12 target)")
# Web between neighbouring pockets: half of each pocket's length band at the
# shared end, and both location bands.
if 2.0 * POCKET_END_WALL - _PAD_POCKET_LENGTH_BAND - 2.0 * _XXX < 2.0:
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
# The prechips freeze rows (review/compose-r5 examples/inventory/pedro-shop.toml
# rail-rest-{ru,lu,rl,ll}-slot; its fixture frame is frame A, so X and Y read
# across unchanged): C1/C2 the upper pair (ru/lu) under the narrow rail at
# X +-(20..40), C3/C4 the lower pair (rl/ll) under the wide rail at X
# +-(120..140), standing where the S4 op 25/27 collet nose clears the rail
# clamps by 3 mm (prechips afe9a14).
_REST_POCKETS = (
    ("C1", 20.0, 32.2, 20.0, 4.3),
    ("C2", -40.0, 32.2, 20.0, 4.3),
    ("C3", 120.0, -27.5, 20.0, 5.0),
    ("C4", -140.0, -27.5, 20.0, 5.0),
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
    (tag, round(x0 + length / 2.0, 3), round(y0 + width / 2.0, 3), length, width)
    for tag, x0, y0, length, width in _REST_POCKETS
)
# A rest pocket's length neither locates its centred rest nor neighbours a
# web, so it prints at one place (codex review of run
# 20261007T232215823Z: 20.000 was over-specified), as the pad pockets' do;
# its rest is shortened by the wider band so it still ends clear.
REST_POCKET_LENGTH_PLACES = PAD_POCKET_LENGTH_PLACES
_REST_POCKET_LENGTH_BAND = printed_band_mm(REST_POCKET_LENGTH_PLACES)
RESTS: tuple[tuple[str, float, float, float, float], ...] = tuple(
    (
        tag,
        cx,
        cy,
        _part_length(length, width, _REST_POCKET_LENGTH_BAND),
        round(width - 2.0 * REST_CLEARANCE, 3),
    )
    for tag, cx, cy, length, width in REST_POCKETS
)
PART_END_GAP_MIN = min(
    *(
        _end_gap_min(pocket[3], pocket[4], part[3], _PAD_POCKET_LENGTH_BAND)
        for pocket, part in zip(PAD_POCKETS, PADS, strict=True)
    ),
    *(
        _end_gap_min(pocket[3], pocket[4], part[3], _REST_POCKET_LENGTH_BAND)
        for pocket, part in zip(REST_POCKETS, RESTS, strict=True)
    ),
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
# The bore depth sets where the pivot screw's thread starts in the tap, so it
# prints at .XXX (FixtureCAD ruling B): at the .XX band the TL-06 pivot screw
# could not reach 1.5D full thread at worst case. The pivot screw's spec
# imports both names.
LOCATING_BORE_DEPTH_PLACES = 3
LOCATING_BORE_DEPTH_BAND = printed_band_mm(LOCATING_BORE_DEPTH_PLACES)
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
        LOCATING_BORE_DEPTH + LOCATING_BORE_DEPTH_BAND + PIVOT_TAP_DRILL_DEPTH + _XX,
        PIVOT_TAP_DRILL_DIA,
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
# The callout prints the clearance at two places, and the model cuts exactly
# that value (FixtureCAD one-fact ruling: the drilled band qualifies the model
# nominal), 0.002 over the 1/2 normal-fit table value.
HOLD_DOWN_CLEARANCE_DIA = round(CLEARANCE_MM[("1/2", "normal")], 2)
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

# Clamp-stud taps (inventory: 3/8-16 studs), the prechips freeze rows
# (review/compose-r5 pedro-shop.toml stud-tap-*, frame A): S1/S2 the lower S4
# rail clamps (ll/rl), S3/S4 the S3 hub straps (lu/ru), S5/S6 the upper S4 rail
# clamps (lu4/ru4, prechips 2a77dd9).
CLAMP_STUD_SPEC = HoleSpec(
    "tapped",
    "3/8-16",
    end="blind",
    depth_mm=19.5,
    overrides_mm={"ThreadDepth": 16.5},
)
CLAMP_STUD_POINTS = (
    (-130.0, -36.0),
    (130.0, -36.0),
    (-70.0, 45.0),
    (70.0, 45.0),
    (-30.0, 45.0),
    (30.0, 45.0),
)
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
    *((cx, cy, length + _XXX, width + _XXX) for _tag, cx, cy, length, width in PAD_POCKETS),
    *(
        (cx, cy, length + _REST_POCKET_LENGTH_BAND, width + _XXX)
        for _tag, cx, cy, length, width in REST_POCKETS
    ),
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
# Places that only the schedules state (policy rule 2: the model owns every
# scheduled driving dimension's places; cross-vendor review of PR 1252).
# The pin seats on its collar, not the hole floor: the depth only clears the
# shank, so it prints at one place. The hub stand bore is drilled: two places,
# the title block's DRILLED HOLES band.
ROD_PIN_HOLE_DEPTH_PLACES = 1
STAND_BORE_PLACES = 2
SCHEDULE_PLACES = 3


def pocket_dimension_names(tag: str) -> tuple[str, ...]:
    """Centre X, centre Y, length X and width Y of a scheduled pocket."""
    return tuple(f"{tag}Pocket{axis}" for axis in ("X", "Y", "Length", "Width"))


def part_dimension_names(tag: str, part: str) -> tuple[str, str]:
    """Length X and width Y of a bonded part (sketched by its corner)."""
    return (f"{tag}{part}Length", f"{tag}{part}Width")


HOLD_DOWN_NAMES = tuple(
    (f"HoldDown{index}X", f"HoldDown{index}Y") for index in range(1, len(HOLD_DOWN_POINTS) + 1)
)
CLAMP_STUD_NAMES = tuple(
    (f"ClampStud{index}X", f"ClampStud{index}Y") for index in range(1, len(CLAMP_STUD_POINTS) + 1)
)
_POCKET_PLACES = (SCHEDULE_PLACES, SCHEDULE_PLACES, PAD_POCKET_LENGTH_PLACES, SCHEDULE_PLACES)
_REST_POCKET_PLACES = (SCHEDULE_PLACES, SCHEDULE_PLACES, REST_POCKET_LENGTH_PLACES, SCHEDULE_PLACES)
_PART_PLACES = (PART_LENGTH_PLACES, SCHEDULE_PLACES)
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateProfile": {
        "PlateLength": 1,
        "PlateWidth": 1,
        "PlateWestX": 1,
        "PlateSouthY": 1,
    },
    "Plate": {"PlateThick": 1, "PlateDrop": 3},
    "StandProfile": {"StandOD": SCHEDULE_PLACES, "StandBore": STAND_BORE_PLACES},
    "Stand": {"StandHeight": SCHEDULE_PLACES, "StandDrop": 3},
    "Rests": {"RestHeight": SCHEDULE_PLACES, "RestTopHeight": 2},
    "StandPocketProfile": {"StandPocketDia": 3},
    "StandPocket": {"StandPocketDepth": 3},
    "LocatingBoreProfile": {"LocatingBoreDia": 3},
    "LocatingBore": {"LocatingBoreDepth": LOCATING_BORE_DEPTH_PLACES},
    "RodPinHoleProfile": {"RodPinHoleDia": 3, "RodPinHoleX": 3, "RodPinHoleY": 3},
    "RodPinHole": {"RodPinHoleDepth": ROD_PIN_HOLE_DEPTH_PLACES},
    "PadPocketProfile": {
        name: places
        for tag, *_size in PAD_POCKETS
        for name, places in zip(pocket_dimension_names(tag), _POCKET_PLACES, strict=True)
    },
    "PadPockets": {"PadPocketDepth": SCHEDULE_PLACES},
    "RestPocketProfile": {
        name: places
        for tag, *_size in REST_POCKETS
        for name, places in zip(pocket_dimension_names(tag), _REST_POCKET_PLACES, strict=True)
    },
    "RestPockets": {"RestPocketDepth": SCHEDULE_PLACES},
    "HoldDownHoles": {
        name: places
        for names in HOLD_DOWN_NAMES
        for name, places in zip(names, (HOLD_DOWN_X_PLACES, HOLD_DOWN_Y_PLACES), strict=True)
    },
    "ClampStudTaps": {name: CLAMP_STUD_PLACES for names in CLAMP_STUD_NAMES for name in names},
    "PadProfile": {
        name: places
        for tag, *_size in PADS
        for name, places in zip(part_dimension_names(tag, "Pad"), _PART_PLACES, strict=True)
    },
    "Pads": {"PadHeight": SCHEDULE_PLACES},
    "RestProfile": {
        name: places
        for tag, *_size in RESTS
        for name, places in zip(part_dimension_names(tag, "Rest"), _PART_PLACES, strict=True)
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(len(names) for names in DRAWING_PRECISION.values()):
    raise AssertionError("a profile-fixture dimension name is authored on two features")
_FEATURE_OF = {
    name: feature for feature, dimensions in DRAWING_PRECISION.items() for name in dimensions
}
_MARKED = set().union(*DRAWING_DIMENSIONS.values())
# What the sheet imports, and must read back at the authored places.
MARKED_PRECISION_BY_NAME: dict[str, int] = {
    name: places for name, places in DRAWING_PRECISION_BY_NAME.items() if name in _MARKED
}
if ROD_PIN_XY_BAND[1] != -ROD_PIN_XY_BAND[0]:
    raise AssertionError("the rod-pin coordinates print a symmetric band")
# The rod-pin coordinates carry their own band as a native model tolerance.
EXPLICIT_SYMMETRIC_TOLERANCES_MM: dict[tuple[str, str], float] = {
    ("RodPinHoleProfile", name): ROD_PIN_XY_BAND[0] for name in ("RodPinHoleX", "RodPinHoleY")
}
DIMENSION_CALLOUTS = {"LocatingBoreDia": "REAM", "RodPinHoleDia": "REAM"}

# Schedules (sheets two and three): every pocket and hole is tagged on the
# sheet-two plan and located here from the locating bore axis; every bonded part
# is sized. Every number in a schedule is a model dimension (policy rule 2):
# SCHEDULE_CELL_DIMENSIONS maps each (schedule, row tag, column) to the
# (feature, dimension) pairs that own it, and the cell prints their value at
# their authored places (a row of two mirrored parts has one owner in each
# part's sketch). The build reads every owner back and proves the printed cell
# is its value, places and band. A location prints signed, as the TAGS plan is
# drawn; its sketch dimension holds the distance, the sketch the side.
SECTION_LABEL = "D"
DETAIL_LABEL = "E"
SCHEDULE_CELL_DIMENSIONS: dict[tuple[str, str, str], tuple[tuple[str, str], ...]] = {
    ("FEATURE", "P", "CENTRE X"): (("RodPinHoleProfile", "RodPinHoleX"),),
    ("FEATURE", "P", "CENTRE Y"): (("RodPinHoleProfile", "RodPinHoleY"),),
}


def _cell(schedule: str, tag: str, column: str, value: float, *names: str) -> str:
    """Record ``names`` as the owners of one schedule cell and print ``value``
    at their authored places."""
    places = {DRAWING_PRECISION_BY_NAME[name] for name in names}
    if len(places) != 1:
        raise AssertionError(f"{tag} {column}: its owners author different places")
    SCHEDULE_CELL_DIMENSIONS[(schedule, tag, column)] = tuple(
        (_FEATURE_OF[name], name) for name in names
    )
    return f"{value:.{places.pop()}f}"


def _pocket_row(
    tag: str, feature: str, centre: tuple[float, float], size: tuple[float, float],
    depth: float, depth_name: str,
) -> tuple[str, ...]:
    x_name, y_name, length_name, width_name = pocket_dimension_names(tag)
    return (
        tag,
        feature,
        _cell("FEATURE", tag, "CENTRE X", centre[0], x_name),
        _cell("FEATURE", tag, "CENTRE Y", centre[1], y_name),
        _cell("FEATURE", tag, "LENGTH X", size[0], length_name),
        _cell("FEATURE", tag, "WIDTH Y", size[1], width_name),
        _cell("FEATURE", tag, "DEPTH", depth, depth_name),
    )


# Every row locates its feature's centre, and the axes read as the TAGS plan
# is drawn (codex review of run 20261007T204247920Z). Bore L is the origin
# itself, so its row prints no location.
FEATURE_SCHEDULE_TITLE = (
    "FEATURE SCHEDULE: CENTRES FROM BORE L AXIS, +X RIGHT AND +Y UP AS ON SHEET 2"
)
FEATURE_SCHEDULE_HEADER = (
    "TAG", "FEATURE", "CENTRE X", "CENTRE Y", "LENGTH X", "WIDTH Y", "DEPTH"
)
FEATURE_SCHEDULE: tuple[tuple[str, ...], ...] = (
    ("L", "LOCATING BORE", "-", "-", "-", "-", f"SEE {SECTION_LABEL}-{SECTION_LABEL}"),
    (
        "P",
        "ROD PIN HOLE",
        *ROD_PIN_XY_PRINTED,
        "-",
        "-",
        _cell("FEATURE", "P", "DEPTH", ROD_PIN_HOLE_DEPTH, "RodPinHoleDepth"),
    ),
    *(
        _pocket_row(tag, "PAD POCKET", (cx, cy), (length, width), PAD_POCKET_DEPTH, "PadPocketDepth")
        for tag, cx, cy, length, width in PAD_POCKETS
    ),
    *(
        _pocket_row(
            tag, "REST POCKET", (cx, cy), (length, width), REST_POCKET_DEPTH, "RestPocketDepth"
        )
        for tag, cx, cy, length, width in REST_POCKETS
    ),
    *(
        (
            f"H{index}",
            "HOLD-DOWN",
            _cell("FEATURE", f"H{index}", "CENTRE X", x, x_name),
            _cell("FEATURE", f"H{index}", "CENTRE Y", y, y_name),
            "-",
            "-",
            "THRU",
        )
        for index, ((x, y), (x_name, y_name)) in enumerate(
            zip(HOLD_DOWN_POINTS, HOLD_DOWN_NAMES, strict=True), start=1
        )
    ),
    *(
        (
            f"S{index}",
            "STUD TAP",
            _cell("FEATURE", f"S{index}", "CENTRE X", x, x_name),
            _cell("FEATURE", f"S{index}", "CENTRE Y", y, y_name),
            "-",
            "-",
            "-",
        )
        for index, ((x, y), (x_name, y_name)) in enumerate(
            zip(CLAMP_STUD_POINTS, CLAMP_STUD_NAMES, strict=True), start=1
        )
    ),
)
_PAD_STOCK = {3.3: "O1 FLAT 3/16 X 1/2"}
PART_SCHEDULE_TITLE = "BONDED PART SCHEDULE, SIZES BEFORE BONDING"
PART_SCHEDULE_HEADER = ("TAG", "PART", "STOCK", "LENGTH X", "WIDTH Y", "HEIGHT")


def _part_row(
    a: tuple, b: tuple, part: str, label: str, stock: str, height: float, height_name: str
) -> tuple[str, ...]:
    """One row for a mirrored pair of bonded parts: both sketches own its sizes."""
    tag = f"{a[0]}, {b[0]}"
    if a[3:] != b[3:]:
        raise AssertionError(f"{tag}: mirrored parts differ in size")
    a_length, a_width = part_dimension_names(a[0], part)
    b_length, b_width = part_dimension_names(b[0], part)
    return (
        tag,
        label,
        stock,
        _cell("PART", tag, "LENGTH X", a[3], a_length, b_length),
        _cell("PART", tag, "WIDTH Y", a[4], a_width, b_width),
        _cell("PART", tag, "HEIGHT", height, height_name),
    )


PART_SCHEDULE: tuple[tuple[str, ...], ...] = (
    *(
        _part_row(
            a, b, "Pad", "PAD", _PAD_STOCK.get(round(a[4], 3), "O1 FLAT 1/8 X 1/2"),
            PAD_HEIGHT, "PadHeight",
        )
        for a, b in zip(PADS[:6], PADS[6:], strict=True)
    ),
    *(
        _part_row(a, b, "Rest", "RAIL REST", "O1 FLAT 3/16 X 1", REST_HEIGHT, "RestHeight")
        for a, b in ((RESTS[0], RESTS[1]), (RESTS[2], RESTS[3]))
    ),
    (
        "L",
        "HUB STAND",
        "4140 HT BAR 1/2",
        f"OD {_cell('PART', 'L', 'LENGTH X', STAND_OD, 'StandOD')}",
        f"DRILL \u00d8{_cell('PART', 'L', 'WIDTH Y', STAND_BORE, 'StandBore')}",
        _cell("PART", "L", "HEIGHT", STAND_HEIGHT, "StandHeight"),
    ),
)
# Every number in a dimension column has its owners.
_DIMENSION_COLUMNS = {"CENTRE X", "CENTRE Y", "LENGTH X", "WIDTH Y", "DEPTH", "HEIGHT"}
for _schedule, _header, _rows in (
    ("FEATURE", FEATURE_SCHEDULE_HEADER, FEATURE_SCHEDULE),
    ("PART", PART_SCHEDULE_HEADER, PART_SCHEDULE),
):
    for _row in _rows:
        for _column, _text in zip(_header, _row, strict=True):
            _owned = (_schedule, _row[0], _column) in SCHEDULE_CELL_DIMENSIONS
            if _column in _DIMENSION_COLUMNS and any(c.isdigit() for c in _text) != _owned:
                raise AssertionError(f"{_schedule} {_row[0]} {_column}: {_text!r} has no model owner")
SCHEDULED_DIMENSIONS = {
    name for owners in SCHEDULE_CELL_DIMENSIONS.values() for _feature, name in owners
}
if set(DRAWING_PRECISION_BY_NAME) != _MARKED | SCHEDULED_DIMENSIONS:
    raise AssertionError(
        "every marked or scheduled profile-fixture dimension needs authored places"
    )
if _MARKED & SCHEDULED_DIMENSIONS:
    raise AssertionError("a profile-fixture dimension prints both marked and scheduled")

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
_FROM_BORE = ("locating_bore", ("LOCATING_BORE_DIA",))
DRILLED_BAND = (drilled_oversize_mm(), 0.0)  # the title block's DRILLED HOLES
_DRILL_POINT_HALF_ANGLE_DEG = math.degrees(_DRILL_POINT_HALF_ANGLE)


def _plan_location(
    x: float, y: float, x_places: int, y_places: int, sources: tuple[str, ...]
) -> dict:
    """A scheduled centre: X as ``station`` and Y as ``height``, both from the
    locating-bore axis, at their printed places."""
    return {
        "station": (limits(x, x_places), sources),
        "station_nominal": (x, sources),
        "height": (limits(y, y_places), sources),
        "height_nominal": (y, sources),
        "height_from": _FROM_BORE,
    }


def _pocket(
    row: tuple[str, float, float, float, float], rows: str, faces: tuple, depth: float,
    depth_source: str, length_places: int,
) -> ExportFeature:
    """One feature-schedule pocket row: its centre, size and depth."""
    _tag, cx, cy, length, width = row
    floor_z = PLATE_TOP_Z - depth
    return ExportFeature(
        kind="pocket",
        faces=faces,
        requirements=("station", "height", "length", "width", "depth"),
        fields={
            "at": ([cx, cy, PLATE_TOP_Z], (rows, "PLATE_TOP_Z")),
            "axis": _DOWN,
            **_plan_location(cx, cy, SCHEDULE_PLACES, SCHEDULE_PLACES, (rows,)),
            "length": (limits(length, length_places), (rows,)),
            "length_nominal": (length, (rows,)),
            "width": (limits(width, SCHEDULE_PLACES), (rows,)),
            "width_nominal": (width, (rows,)),
            "depth": (limits(depth, SCHEDULE_PLACES), (depth_source,)),
            "depth_ref": (depth, (depth_source,)),
            "plane": ({"frame": "model", "axis": "z", "value": floor_z}, ("PLATE_TOP_Z", depth_source)),
        },
        precision={
            "station": SCHEDULE_PLACES,
            "height": SCHEDULE_PLACES,
            "length": length_places,
            "width": SCHEDULE_PLACES,
            "depth": SCHEDULE_PLACES,
        },
    )


def _bonded_part(
    row: tuple[str, float, float, float, float], rows: str, top_z: float, height: float,
    height_source: str,
) -> ExportFeature:
    """One bonded part's sizes before bonding (part schedule), claiming its
    outward end face, which no other part or pocket shares."""
    _tag, cx, cy, length, width = row
    side = 1.0 if cx > 0.0 else -1.0
    return ExportFeature(
        kind="boss",
        faces=(PlanarFace((side, 0.0, 0.0), abs(cx) + length / 2.0, contains_z_mm=top_z - 1.0),),
        requirements=("length", "width", "height"),
        fields={
            "at": ([cx, cy, top_z], (rows, height_source)),
            "axis": _UP,
            "length": (limits(length, PART_LENGTH_PLACES), (rows, "PART_LENGTH_PLACES")),
            "length_nominal": (length, (rows,)),
            "width": (limits(width, SCHEDULE_PLACES), (rows,)),
            "width_nominal": (width, (rows,)),
            "height": (limits(height, SCHEDULE_PLACES), (height_source,)),
            "height_nominal": (height, (height_source,)),
        },
        precision={"length": PART_LENGTH_PLACES, "width": SCHEDULE_PLACES, "height": SCHEDULE_PLACES},
    )


def _plate_face(normal: tuple[float, float, float], offset: float, key: str, value: float,
                source: str) -> ExportFeature:
    """A plate end or side printed from the locating-bore axis."""
    return ExportFeature(
        kind="face",
        faces=(PlanarFace(normal, offset),),
        requirements=(key,),
        fields={
            "normal": (list(normal), ("__frame__",)),
            "plane": (
                {"frame": "model", "axis": "x" if normal[0] else "y", "value": value}, (source,)
            ),
            key: (limits(value, 1), (source,)),
            f"{key}_nominal": (value, (source,)),
            **({"height_from": _FROM_BORE} if key == "height" else {}),
        },
        precision={key: 1},
    )


def _hold_down(index: int, x: float, y: float) -> dict[str, ExportFeature]:
    """Hold-down row H<index>: the clearance hole at its scheduled centre and
    the counterbore the 4X callout prints over it."""
    name = f"hold_down_h{index}"
    spec = ("HOLD_DOWN_HOLE_SPEC",)
    return {
        name: ExportFeature(
            kind="hole",
            faces=(CylinderFace(HOLD_DOWN_CLEARANCE_DIA, contains_x_mm=x, contains_y_mm=y),),
            requirements=("station", "height", "dia", "thru"),
            fields={
                "at": ([x, y, PLATE_TOP_Z], ("HOLD_DOWN_POINTS", "PLATE_TOP_Z")),
                "axis": _DOWN,
                **_plan_location(
                    x, y, HOLD_DOWN_X_PLACES, HOLD_DOWN_Y_PLACES,
                    ("HOLD_DOWN_POINTS", "HOLD_DOWN_X_PLACES", "HOLD_DOWN_Y_PLACES"),
                ),
                "dia": (
                    limits(HOLD_DOWN_CLEARANCE_DIA, 2, DRILLED_BAND),
                    ("HOLD_DOWN_CLEARANCE_DIA", "DRILLED_BAND", *spec),
                ),
                "dia_nominal": (HOLD_DOWN_CLEARANCE_DIA, ("HOLD_DOWN_CLEARANCE_DIA",)),
                "thru": (True, spec),
                "hole_spec": ("1/2 SHCS COUNTERBORE", spec),
            },
            precision={"station": HOLD_DOWN_X_PLACES, "height": HOLD_DOWN_Y_PLACES, "dia": 2},
        ),
        f"{name}_counterbore": ExportFeature(
            kind="counterbore",
            faces=(CylinderFace(HOLD_DOWN_CBORE_DIA, contains_x_mm=x, contains_y_mm=y),),
            requirements=("dia", "depth"),
            fields={
                "parent": (name, spec),
                "dia": (limits(HOLD_DOWN_CBORE_DIA, 2), ("HOLD_DOWN_CBORE_DIA", *spec)),
                "dia_nominal": (HOLD_DOWN_CBORE_DIA, ("HOLD_DOWN_CBORE_DIA",)),
                "depth": (limits(HOLD_DOWN_CBORE_DEPTH, 2), ("HOLD_DOWN_CBORE_DEPTH", *spec)),
                "depth_ref": (HOLD_DOWN_CBORE_DEPTH, ("HOLD_DOWN_CBORE_DEPTH",)),
            },
            precision={"dia": 2, "depth": 2},
        ),
    }


def _drill_dia(drill_dia: float, spec_name: str) -> dict:
    """The tap drill Ø its callout prints (two places), banded by the title
    block's DRILLED HOLES row about that printed value."""
    printed = round(drill_dia, 2)
    return {
        "dia": (limits(printed, 2, DRILLED_BAND), (spec_name, "DRILLED_BAND")),
        "dia_nominal": (printed, (spec_name,)),
    }


def _tap(spec: HoleSpec, spec_name: str, drill_dia: float, at: list[float], places: tuple[int, int] | None,
         sources: tuple[str, ...]) -> ExportFeature:
    """A blind tapped hole on its drilled cylinder (matched at the true drill
    size, kept as ``tap_drill_mm``): the printed drill Ø (the bore that
    cylinder is), its thread and full-thread depth, all at two places as the
    callout prints."""
    thread_depth = spec.overrides_mm["ThreadDepth"]
    location = {} if places is None else _plan_location(at[0], at[1], *places, sources)
    return ExportFeature(
        kind="hole",
        faces=(CylinderFace(drill_dia, contains_x_mm=at[0], contains_y_mm=at[1]),),
        requirements=(*(("station", "height") if location else ()), "dia", "thread", "depth"),
        fields={
            "at": (at, (*sources, "PLATE_TOP_Z")),
            "axis": _DOWN,
            **location,
            **_drill_dia(drill_dia, spec_name),
            "thread": (f"{spec.size} UNC-{spec.thread_class}", (spec_name,)),
            "depth": (limits(thread_depth, 2), (spec_name,)),
            "depth_ref": (thread_depth, (spec_name,)),
            "tap_drill_mm": (drill_dia, (spec_name,)),
            "thru": (False, (spec_name,)),
        },
        precision={
            **({"station": places[0], "height": places[1]} if location else {}),
            "dia": 2,
            "depth": 2,
        },
    )


def _tap_drill(
    spec: HoleSpec, spec_name: str, stations: tuple[float, ...], *, parent: str | None
) -> ExportFeature:
    """The drill depth a tap callout prints (two places), on its drill-point
    cones; the drill Ø belongs to the tap's own cylinder."""
    return ExportFeature(
        kind="hole",
        faces=tuple(ConeFace(_DRILL_POINT_HALF_ANGLE_DEG, contains_x_mm=x) for x in stations),
        requirements=("depth",),
        fields={
            **({} if parent is None else {"parent": (parent, (spec_name,))}),
            "depth": (limits(spec.depth_mm, 2), (spec_name,)),
            "depth_ref": (spec.depth_mm, (spec_name,)),
            "thru": (False, (spec_name,)),
        },
        precision={"depth": 2},
    )


EXPORT_FEATURES: dict[str, ExportFeature] = {
    "locating_bore": ExportFeature(
        kind="hole",
        faces=(CylinderFace(LOCATING_BORE_DIA, contains_x_mm=0.0, contains_y_mm=0.0),),
        requirements=("dia", "depth"),
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
            "depth": (
                limits(LOCATING_BORE_DEPTH, LOCATING_BORE_DEPTH_PLACES),
                ("LOCATING_BORE_DEPTH", "LOCATING_BORE_DEPTH_PLACES"),
            ),
            "depth_ref": (LOCATING_BORE_DEPTH, ("LOCATING_BORE_DEPTH",)),
            "process": ("REAM", ("DIMENSION_CALLOUTS",)),
        },
        precision={"dia": 3, "depth": LOCATING_BORE_DEPTH_PLACES},
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
        requirements=("dia", "station", "height", "depth"),
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
            "depth": (
                limits(ROD_PIN_HOLE_DEPTH, ROD_PIN_HOLE_DEPTH_PLACES),
                ("ROD_PIN_HOLE_DEPTH", "ROD_PIN_HOLE_DEPTH_PLACES"),
            ),
            "depth_ref": (ROD_PIN_HOLE_DEPTH, ("ROD_PIN_HOLE_DEPTH",)),
            "process": ("REAM", ("DIMENSION_CALLOUTS",)),
        },
        precision={"dia": 3, "depth": ROD_PIN_HOLE_DEPTH_PLACES, "station": 3, "height": 3},
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
            "height_nominal": (PLATE_DROP, ("PLATE_DROP",)),
        },
        precision={"height": 3},
    ),
    "stand_top": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, 1.0), STAND_TOP_Z),),
        requirements=("height", "dia"),
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
            "height_nominal": (STAND_DROP, ("STAND_DROP",)),
            "dia": (limits(STAND_OD, SCHEDULE_PLACES), ("STAND_OD",)),
            "dia_nominal": (STAND_OD, ("STAND_OD",)),
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
            "height_nominal": (REST_TOP_HEIGHT, ("REST_TOP_HEIGHT",)),
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
            "thickness_nominal": (PLATE_THICK, ("PLATE_THICK",)),
        },
        precision={"thickness": 1},
    ),
    "plate_outline": ExportFeature(
        kind="face",
        faces=(PlanarFace((1.0, 0.0, 0.0), PLATE_EAST_X), PlanarFace((0.0, 1.0, 0.0), PLATE_NORTH_Y)),
        requirements=("length", "width"),
        fields={
            "length": (limits(PLATE_LENGTH, 1), ("PLATE_LENGTH",)),
            "length_nominal": (PLATE_LENGTH, ("PLATE_LENGTH",)),
            "width": (limits(PLATE_WIDTH, 1), ("PLATE_WIDTH",)),
            "width_nominal": (PLATE_WIDTH, ("PLATE_WIDTH",)),
        },
        precision={"length": 1, "width": 1},
    ),
    "plate_west_end": _plate_face((-1.0, 0.0, 0.0), -PLATE_WEST_X, "station", PLATE_WEST_X, "PLATE_WEST_X"),
    "plate_south_side": _plate_face(
        (0.0, -1.0, 0.0), -PLATE_SOUTH_Y, "height", PLATE_SOUTH_Y, "PLATE_SOUTH_Y"
    ),
    "stand_pocket": ExportFeature(
        kind="counterbore",
        faces=(CylinderFace(STAND_POCKET_DIA, contains_x_mm=0.0, contains_y_mm=0.0),),
        requirements=("dia", "depth"),
        fields={
            "at": ([0.0, 0.0, PLATE_TOP_Z], ("PLATE_TOP_Z",)),
            "axis": _DOWN,
            "dia": (limits(STAND_POCKET_DIA, 3), ("STAND_POCKET_DIA",)),
            "dia_nominal": (STAND_POCKET_DIA, ("STAND_POCKET_DIA",)),
            "depth": (limits(STAND_POCKET_DEPTH, 3), ("STAND_POCKET_DEPTH",)),
            "depth_ref": (STAND_POCKET_DEPTH, ("STAND_POCKET_DEPTH",)),
        },
        precision={"dia": 3, "depth": 3},
    ),
    # The hub stand's drilled bore and its overall height (part schedule),
    # the height measured down from its top.
    "stand_bore": ExportFeature(
        kind="hole",
        faces=(CylinderFace(STAND_BORE, contains_x_mm=0.0, contains_y_mm=0.0),),
        requirements=("dia", "thru"),
        fields={
            "at": ([0.0, 0.0, STAND_TOP_Z], ("STAND_TOP_Z",)),
            "axis": _DOWN,
            "dia": (limits(STAND_BORE, STAND_BORE_PLACES, DRILLED_BAND), ("STAND_BORE", "DRILLED_BAND")),
            "dia_nominal": (STAND_BORE, ("STAND_BORE",)),
            "thru": (True, ("STAND_BORE",)),
        },
        precision={"dia": STAND_BORE_PLACES},
    ),
    "stand_foot": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, -1.0), STAND_HEIGHT - STAND_TOP_Z, contains_x_mm=0.0),),
        requirements=("height",),
        fields={
            "normal": _DOWN,
            "plane": (
                {"frame": "model", "axis": "z", "value": STAND_TOP_Z - STAND_HEIGHT},
                ("STAND_TOP_Z", "STAND_HEIGHT"),
            ),
            "height": (limits(STAND_HEIGHT, SCHEDULE_PLACES), ("STAND_HEIGHT",)),
            "height_nominal": (STAND_HEIGHT, ("STAND_HEIGHT",)),
            "height_from": ("stand_top", ("STAND_HEIGHT",)),
        },
        precision={"height": SCHEDULE_PLACES},
    ),
    **{
        f"pad_pocket_{row[0].lower()}": _pocket(
            row, "PAD_POCKETS",
            (PlanarFace((0.0, 0.0, 1.0), PLATE_TOP_Z - PAD_POCKET_DEPTH, contains_x_mm=row[1]),),
            PAD_POCKET_DEPTH, "PAD_POCKET_DEPTH", PAD_POCKET_LENGTH_PLACES,
        )
        for row in PAD_POCKETS
    },
    # Each rest pocket claims its two long walls, which carry its centre Y and
    # width Y (C1/C2 span the X of pad pockets A1/A2 and B1/B2).
    **{
        f"rest_pocket_{row[0].lower()}": _pocket(
            row, "REST_POCKETS",
            (
                PlanarFace((0.0, -1.0, 0.0), -(row[2] + row[4] / 2.0), contains_x_mm=row[1]),
                PlanarFace((0.0, 1.0, 0.0), row[2] - row[4] / 2.0, contains_x_mm=row[1]),
            ),
            REST_POCKET_DEPTH, "REST_POCKET_DEPTH", REST_POCKET_LENGTH_PLACES,
        )
        for row in REST_POCKETS
    },
    **{f"pad_{row[0].lower()}": _bonded_part(row, "PADS", PAD_TOP_Z, PAD_HEIGHT, "PAD_HEIGHT") for row in PADS},
    **{
        f"rest_{row[0].lower()}": _bonded_part(row, "RESTS", REST_TOP_Z, REST_HEIGHT, "REST_HEIGHT")
        for row in RESTS
    },
    **{
        key: feature
        for index, (x, y) in enumerate(HOLD_DOWN_POINTS, start=1)
        for key, feature in _hold_down(index, x, y).items()
    },
    **{
        f"stud_tap_s{index}": _tap(
            CLAMP_STUD_SPEC, "CLAMP_STUD_SPEC", CLAMP_STUD_DRILL_DIA, [x, y, PLATE_TOP_Z],
            (CLAMP_STUD_PLACES, CLAMP_STUD_PLACES), ("CLAMP_STUD_POINTS", "CLAMP_STUD_PLACES"),
        )
        for index, (x, y) in enumerate(CLAMP_STUD_POINTS, start=1)
    },
    # A cone selector takes no Y, so one feature carries the drill-point cones
    # (one per stud station X) and the printed drill depth.
    "stud_tap_drills": _tap_drill(
        CLAMP_STUD_SPEC, "CLAMP_STUD_SPEC", tuple(sorted({x for x, _y in CLAMP_STUD_POINTS})),
        parent=None,
    ),
    # The pivot tap's depths run from the locating-bore floor, as printed.
    "pivot_tap": _tap(
        PIVOT_TAP_SPEC, "PIVOT_TAP_SPEC", PIVOT_TAP_DRILL_DIA, [0.0, 0.0, LOCATING_BORE_FLOOR_Z],
        None, ("LOCATING_BORE_FLOOR_Z",),
    ),
    "pivot_tap_drill": _tap_drill(PIVOT_TAP_SPEC, "PIVOT_TAP_SPEC", (0.0,), parent="pivot_tap"),
}
