r"""Pure-data contract for the oblique-trammel jig's pivot block (MHA-CH-006-TL-22).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md). Two are
made: one bolts on each rail's HIWIN HGH15CA carriage and carries, in two
6200-2RS bearings, the pivot pin (MHA-CH-006-TL-23) that the carrier plate
(MHA-CH-006-TL-21) turns on (``ch_rocker_arm_tl_oblique_trammel_spec``,
imported as ``trammel``; values read from it are marked ⚙).

Material and stock: 6061-T6 aluminium, a 70 x 40 x ``PIVOT_BLOCK_HEIGHT`` ⚙
(24) block machined from 1 x 2 in flat bar.

Frame: origin at the carriage centre (the centre of the carriage's 26 x 26
M4 pattern) on the block's bottom face, the carriage seat; +X along the rail
AWAY from the spindle, +Z up, +Y completing the right-handed set. The block
occupies X -50 .. +20, Y -20 .. +20, Z 0 .. 24. The origin is a modelling
frame only: every X station prints from the -X end face and every Y station
from the -Y side face (rule 10, from real faces), carried by construction
points in the top seat's profile sketch that the same knobs drive.

Bearing seats (rule 4, rule 16). The bore axis stands at X = ``PIN_OFFSET`` ⚙
(-32), Y = 0. From the top, a Ø30 N6 seat (29.976/29.989) ``BEARING_RECESS``
+ ``BEARING_WIDTH`` ⚙ = 10 deep; the same from the bottom. Between them a
``BEARING_SHOULDER`` ⚙ (4) shoulder with a Ø25 THRU hole: at its largest
printed size (25.8) it stays within the SKF 6200-2RSH's Da max of 25.8, so
each outer race keeps its full abutment on the shoulder, and its smallest
(24.2) clears the inner race's 15.07 shoulder (d2) by 4.6 a side: the web
is the puller cavity behind both inner races (rule 16, review r6). The
seats print at three places (+/-0.13) and the height at two, so the web
between the races, the cavity's length, is at least 3.23, over the 3 mm
an internal collet puller needs behind a 6200 (SKF TMIC C10-12). With the
first bearing out, the second has the emptied seat behind it. The seat is
a matched fit on the bought bearing's outer race (OD
30 0/-0.009, inventory ``fixtures.trammel-6200-2rs``): 0.002-0.024 diametral interference.
Sensitivity: the interference removes the outer race's float in its seat;
any clearance there would be pivot-axis error, which is trammel-radius error
1:1, so the seat carries the N6 band and nothing else on the block does.

Seat coaxiality. The seats are bored from opposite faces, so nothing in
their sizes ties them on one axis: the bottom seat is datum A and the top
seat carries a position frame of Ø``SEAT_POSITION_DIA`` (0.02) to it. Its
worst case tilts the pin by half the zone over the 13 between the
bearings' centres, 2.6 arcmin, inside the 2 .. 10 arcmin a deep-groove ball
bearing takes (SKF), so the pin turns free; it is no trammel-radius error,
the HUB axis following the pin at the carrier.

Carriage screws. Four Ø4.5 THRU with a Ø8 counterbore from the top on the
26 x 26 ``CARRIAGE_BOLT_SPAN`` ⚙ pattern about the origin, for M4 x 20 SHCS.
The counterbore floor is the functional face: it prints 15.600 from the
bottom (carriage) face at three places (+/-0.13), the block under the head,
so the nominal engagement in the HGH15CA's M4 x 5 tapped holes is 4.40;
with the screw's ISO 4762 js15 length (+/-0.42 at 20) the worst case is
3.85 .. 4.95, inside [0.95D, thread depth - 0.05] = [3.8, 4.95]
(``ENGAGEMENT_MIN`` / ``ENGAGEMENT_MAX``): the vendor's threads are only 5
deep. The 5 mm thread is the carriage maker's, so rule 18's 1.5D (6.0) is
out of reach in geometry: the floor callout states the worst case,
``ENGAGEMENT_MIN`` (shortest screw over the highest floor), as a plain fact
(rule 20), and ``RULE_20_SHORTFALLS`` records it. They are one native Hole
Wizard counterbore feature: the
repo's inch wizard has no M4 row, so an inch socket-head counterbore carries
the three metric sizes as overrides (the soft jaw's M10 precedent,
``dt_cone_pivot_post_tl_soft_jaw_spec``), and the sheet prints one native
callout, ``4X DRILL Ø4.50 THRU ALL / ⌴ Ø8.00 ↧ (8.40)``: the depth is the
floor's reference complement (24 - 15.6), not a second dimension of it.

Hole stations print at three places: the block floats on the carriage within
the screws' clearance, so what must hold is hole to hole. An M4 in a Ø4.5
hole floats 0.25 each side, 0.5 between two holes; two face-referenced
ordinates at +/-0.13 differ by at most 0.26 per axis (0.37 on the diagonal),
at +/-0.51 by 1.02. The bore stations print two: the carriages slide on
their rails, so the bore's place on the block sets no trammel radius.

Seat corner (rule 16): R0.4 MAX where each seat wall meets the shoulder, the
largest a standard 0.4 boring-insert nose leaves, under the 6200's 0.6
minimum outer-race chamfer so the race still seats on the shoulder.

Rule 17 walls (2.0 target, 1.5 floor), nominal, the TL-22 argument:

* bore to counterbore 4.02 and bore to Ø4.5 hole 5.77: the nearest hole
  centre is sqrt(19^2 + 13^2) = 23.02 from the bore axis, less the 15 bore
  radius and the 4 counterbore (2.25 hole) radius;
* counterbore to block side or +X end 3.0: hole centre 13 from the centre
  lines, 4 counterbore radius, block side at 20 and end at +20;
* bore to the -X end 3.0: axis at -32, radius 15, end at -50.

The bore offset is what makes these walls: coaxial with the carriage, the
bore would leave 1.13 to a Ø4.5 hole (``trammel`` docstring). ``WALLS_MM``
holds the nominal argument (each >= 2.0); ``WORST_WALLS`` re-derives every
wall at the printed bands' worst case, every station from its datum face,
against the 1.5 floor, and ``RULE_20_SHORTFALLS`` lists the ones between
floor and target.

The shoulder (LIP >= 1.5). The calculator fixes the block height (24), the
recess (1) and the shoulder (4), so the web between the seats is H - 2D.
It is also the puller's room behind the inner races, so the height prints
two places (+/-0.51) and both seat depths three (+/-0.13): the thinnest
block and the deepest seats leave 23.49 - 2 x 10.13 = 3.23
(``PULLER_GAP_MIN``), stated once on each seat depth as the web it sets
(rule 4; review r8: not on the 24.00, a general size). The web is named by
the Ø25's "THRU WEB" callout. The 70 and 40 print two
places for the counterbores' walls to the +X end and the +Y side, which
they set: 2.10 at two places, 1.81 at one (under the 2.0 target), stated on
both.

Side screws (PR C4). Two Ø4.98 THRU along Y with a Ø7.94 counterbore
4.40 deep from the +Y face, at (X, Z) = (+/-5, 9), for #8-32 x 1-7/8 SHCS
into the tapped holes of the leadscrew nut bracket (MHA-CH-006-TL-29) on
the -Y face. TL-22 owns the positions (``SIDE_SCREW_*``); the leadscrew spec
aliases them, so TL-29's tapped pattern follows them. The row is measured
from the bottom face, which stays on the carriage when the block grows
upward, so the 24 mm block leaves it where it was. One native Hole Wizard
counterbore, the base bar's #8 sizes (MHA-CH-006-TL-20) with the
counterbore depth cut to 4.40 so the head (0.164 in) sits 0.10 .. 0.36
below the face. Their walls run against the carriage holes, which stand
along Z at (+/-13, +13): the counterbore and both stations print three
places, and the pinch walls under the 2.0 target are rule-20 shortfalls
the side callout states (``SIDE_WALL_CALLOUT``). The stations print from
the -X end and the bottom face, carried by a hidden reference sketch the
same knobs drive; TL-29's taps are spotted through these holes at assembly
(TL-000), so the pair's spacing need only stay inside the screws' float,
and the callout names the mate.
"""

from __future__ import annotations

import math

import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _fit_deviations import deviations
from _hole_spec import CLEARANCE_MM, THREAD_MAJOR_MM, HoleSpec
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

# drawing-guidelines.md rule 17 (walls and webs): 2.0 target, 1.5 floor.
WALL_TARGET = 2.0
WALL_FLOOR = 1.5
_BAND = {places: printed_band_mm(places) for places in (1, 2, 3)}
# Title-block DRILLED HOLES: plus allowance, zero minus (_printed_tolerance).
DRILLED_BAND = (drilled_oversize_mm(), 0.0)

# --- Block -----------------------------------------------------------------
BLOCK_X0 = -50.0  # the -X end, toward the spindle
BLOCK_X1 = 20.0  # the +X end
BLOCK_LENGTH = BLOCK_X1 - BLOCK_X0
BLOCK_WIDTH = 40.0
BLOCK_HEIGHT = trammel.PIVOT_BLOCK_HEIGHT  # ⚙ 24
# The datums every printed station measures from: the -X end face and the
# -Y side face (rule 10). The model's knobs stay origin-relative.
DATUM_X = BLOCK_X0
DATUM_Y = -BLOCK_WIDTH / 2.0

# --- Bearing seats ---------------------------------------------------------
BORE_X = trammel.PIN_OFFSET  # ⚙ -32
BEARING_OD = trammel.BEARING_OD  # ⚙ 30
# The bought 6200-2RS outer-race OD deviation (inventory), (upper, lower).
BEARING_OD_BAND = (0.0, -0.009)
# ISO 286 N6 on Ø30 (over 18 to 30), (upper, lower).
N6_BAND = (-0.011, -0.024)
# The model and the sheet carry the seat at its low limit with a unilateral
# band (one fact: 29.976 +0.013/0 is 29.976/29.989).
_od_low, _od_high = deviations(BEARING_OD_BAND)
_n6_low, _n6_high = deviations(N6_BAND)
BORE_DIA = round(BEARING_OD + _n6_low, 3)
BORE_BAND = (round(_n6_high - _n6_low, 3), 0.0)
BORE_DIA_MAX = BORE_DIA + BORE_BAND[0]
BORE_DEPTH = trammel.BEARING_RECESS + trammel.BEARING_WIDTH  # ⚙ 10, each side
SHOULDER = trammel.BEARING_SHOULDER  # ⚙ 4
if abs(2.0 * BORE_DEPTH + SHOULDER - BLOCK_HEIGHT) > 1e-9:
    raise AssertionError("the two seats and the shoulder do not fill the block")
# The Ø25 web hole: the 6200s' abutment face and the puller cavity behind
# their inner races (docstring).
SHOULDER_HOLE_DIA = 25.0
# SKF 6200-2RSH product data, "Abutment dimensions" and "Dimensions" (Da max
# 25.8, d2 ~ 15.07; skf.com productid-6200-2RSH, read 2026-10-17).
BEARING_DA_MAX = 25.8
BEARING_INNER_SHOULDER_D2 = 15.07
# SKF TMIP/TMIC data sheet (PUB MP/P8 13072 EN): the TMIC C10-12 collet,
# listed for 6000-6301, needs 3 mm behind the bearing.
PULLER_SPACE_MIN = 3.0
INTERFERENCE_MIN = round(BEARING_OD + _od_low - BORE_DIA_MAX, 3)
INTERFERENCE_MAX = round(BEARING_OD + _od_high - BORE_DIA, 3)
if INTERFERENCE_MIN <= 0.0:
    raise AssertionError("the smallest bearing OD is loose in the largest seat")
# The mate in the two rows the callout prints it on.
BORE_MATE_ROWS = ("6200-2RS", "OUTER RACE")
BORE_MATE = " ".join(BORE_MATE_ROWS)
# Rule 4 matched-fit callout, in five narrow rows so the block (no wider
# than its value row and tolerance stack, ~35 mm on the 2:1 sheet) fits
# beside the plan view (the draw's layout notes, farm run jig-r2).
BORE_CALLOUT = "\n".join(
    (
        f"{INTERFERENCE_MIN:.3f}-{INTERFERENCE_MAX:.3f}",
        "DIAMETRAL",
        "INTERFERENCE",
        f"ON {BORE_MATE_ROWS[0]}",
        BORE_MATE_ROWS[1],
    )
)

# --- Carriage screws -------------------------------------------------------
BOLT_X = trammel.CARRIAGE_BOLT_SPAN[0] / 2.0  # ⚙ 13
BOLT_Y = trammel.CARRIAGE_BOLT_SPAN[1] / 2.0  # ⚙ 13
BOLT_POINTS = tuple((sx * BOLT_X, sy * BOLT_Y) for sx in (-1, 1) for sy in (-1, 1))
if trammel.CARRIAGE_BOLT != "M4":
    raise AssertionError("the carriage is no longer M4: revisit the counterbores")
HOLE_DIA = 4.5
CBORE_DIA = 8.0
SCREW_DIA = 4.0  # M4 nominal
SCREW_LENGTH = 20.0  # M4 x 20 ISO 4762 SHCS
SCREW_LENGTH_TOL = 0.42  # ISO 4762 js15 at 20, +/-
SCREW_HEAD_DIA = 7.0
SCREW_HEAD_HEIGHT = 4.0
CARRIAGE_THREAD_DEPTH = 5.0  # HGH15CA M4 x 5
# The counterbore floor stands CBORE_FLOOR above the carriage seat: the block
# under the head, so it alone sets the screw's engagement in the carriage.
# The sheet prints it from the bottom face at three places (section B-B);
# the native callout's depth is its reference complement.
CBORE_FLOOR = 15.6
CBORE_FLOOR_PLACES = 3
CBORE_FLOOR_REFERENCE = "CboreFloorReference"
CBORE_SECTION_PLANE = "CboreSectionPlane"
CBORE_DEPTH = round(BLOCK_HEIGHT - CBORE_FLOOR, 6)  # 8.4, printed (8.40) reference
UNDER_HEAD = CBORE_FLOOR
THREAD_IN_CARRIAGE = round(SCREW_LENGTH - UNDER_HEAD, 6)  # 4.4
# Worst-case engagement over the floor's printed band and the screw's length
# tolerance: at least 0.95 D, and short of the carriage thread's bottom.
ENGAGEMENT_MIN_REQUIRED = 0.95 * SCREW_DIA
# 0.05 short of the bottom: the vendor's HGH15CA M4 threads are only 5 deep.
ENGAGEMENT_MAX_ALLOWED = CARRIAGE_THREAD_DEPTH - 0.05
_FLOOR_BAND = printed_band_mm(CBORE_FLOOR_PLACES)
ENGAGEMENT_MIN = round(
    SCREW_LENGTH - SCREW_LENGTH_TOL - (CBORE_FLOOR + _FLOOR_BAND), 6
)  # 3.85
ENGAGEMENT_MAX = round(
    SCREW_LENGTH + SCREW_LENGTH_TOL - (CBORE_FLOOR - _FLOOR_BAND), 6
)  # 4.95
if ENGAGEMENT_MIN < round(ENGAGEMENT_MIN_REQUIRED, 6):
    raise AssertionError("the M4 x 20 engages under 0.95 D at the worst case")
if ENGAGEMENT_MAX > round(ENGAGEMENT_MAX_ALLOWED, 6):
    raise AssertionError("the M4 x 20 nears the carriage's M4 x 5 hole bottom")
# The shallowest counterbore: the thinnest block over the highest floor.
_CBORE_DEPTH_MIN = BLOCK_HEIGHT - printed_band_mm(2) - (CBORE_FLOOR + _FLOOR_BAND)
if SCREW_HEAD_HEIGHT > _CBORE_DEPTH_MIN or SCREW_HEAD_DIA >= CBORE_DIA:
    raise AssertionError("the M4 head does not sink in its counterbore")
SCREW_HOLE_SPEC = HoleSpec(
    "counterbore_socket",
    "#8",
    overrides_mm={
        "HoleDiameter": HOLE_DIA,
        "CounterBoreDiameter": CBORE_DIA,
        "CounterBoreDepth": CBORE_DEPTH,
    },
)
# The hole callout's mate row (rule 4): the three-place stations serve it.
SCREW_MATE_CALLOUT = "MATCHES HGH15CA\nCARRIAGE M4 HOLES"
# The floor's functional callout names the mate it sets (rule 4) and states
# the engagement shortfall the vendor's 5 deep thread leaves (rule 20): the
# same worst case as ENGAGEMENT_MIN, the shortest screw over the highest floor.
ENGAGEMENT_TARGET = 1.5 * SCREW_DIA  # drawing-guidelines.md rule 18
if ENGAGEMENT_MAX >= ENGAGEMENT_TARGET:
    raise AssertionError("the M4 engagement meets rule 18: drop the shortfall")
# One row over its value: review r8 found the three-row callout never
# printed (layout audit text-unmatched), while the one-row "2X" and 70's
# rows do; the HGH15CA mate is already the hole callout's. Both limits print
# (review r11 read the three places as rescuing the minimum alone): the
# floor's band holds the screw between that minimum and the thread's bottom.
CBORE_FLOOR_CALLOUT = (
    f"SETS M4 X 20 ENGAGEMENT {ENGAGEMENT_MIN:.2f}-{ENGAGEMENT_MAX:.2f}"
    f" IN {CARRIAGE_THREAD_DEPTH:.1f} DEEP THREAD"
)

# --- Side screws (PR C4): the TL-29 nut bracket ------------------------------
# 2 x #8-32 x 1-7/8 SHCS from the +Y face, through the block along Y, into the
# nut bracket's tapped holes on the -Y face. The leadscrew spec aliases these.
SIDE_SCREW = "#8-32"
SIDE_SCREW_X = (-5.0, 5.0)
SIDE_SCREW_Z = 9.0
SIDE_SCREW_HOLES: tuple[tuple[float, float], ...] = tuple(
    (x, SIDE_SCREW_Z) for x in SIDE_SCREW_X
)
SIDE_HOLE_DIA = CLEARANCE_MM[("#8", "normal")]  # 4.978
SIDE_SCREW_MAJOR = THREAD_MAJOR_MM[SIDE_SCREW]  # 4.166
SIDE_SCREW_HEAD_DIA = 0.270 * trammel.INCH  # ASME B18.3 #8 SHCS head, max
SIDE_SCREW_HEAD_HEIGHT = 0.164 * trammel.INCH
# The base bar's #8 counterbore diameter (TL-20); the depth is cut from its
# 4.80 to 4.40 for the walls to the carriage holes (docstring).
SIDE_CBORE_DIA = 7.94
SIDE_CBORE_DEPTH = 4.40
SIDE_UNDER_HEAD = BLOCK_WIDTH - SIDE_CBORE_DEPTH  # 35.6 of block under the head
SIDE_SCREW_HOLE_SPEC = HoleSpec(
    "counterbore_socket",
    "#8",
    fit="normal",
    overrides_mm={
        "HoleDiameter": SIDE_HOLE_DIA,
        "CounterBoreDiameter": SIDE_CBORE_DIA,
        "CounterBoreDepth": SIDE_CBORE_DEPTH,
    },
)
SIDE_SCREW_MATE = "MHA-CH-006-TL-29"
SIDE_SCREW_REFERENCE = "SideScrewReference"
# Stations and the counterbore print three places (walls, hole to hole); the
# THRU diameter prints the template's two (base bar BRACKET_CALLOUT_PRECISION).
SIDE_STATION_PLACES = 3
SIDE_CBORE_PLACES = 3
SIDE_THRU_PLACES = 2
SIDE_CALLOUT_PRECISION = {
    "hw-thruholedia": SIDE_THRU_PLACES,
    "hw-cbdia": SIDE_CBORE_PLACES,
    "hw-cbdepth": SIDE_CBORE_PLACES,
}
REFERENCE_SKETCHES = (CBORE_FLOOR_REFERENCE, SIDE_SCREW_REFERENCE)

# --- Seat corner (rule 16) ---------------------------------------------------
BEARING_OD_CHAMFER_MIN = 0.6  # 6200 outer ring r1,2 min
SEAT_FILLET_RADIUS = 0.4  # a standard boring-insert nose
if SEAT_FILLET_RADIUS >= BEARING_OD_CHAMFER_MIN:
    raise AssertionError("the seat corner fouls the 6200 outer-race chamfer")
RADIUS_TOL_TYPE = 6  # swTolType_e.swTolMAX

# --- Seat coaxiality (docstring "Seat coaxiality") ----------------------------
SEAT_DATUM = "A"  # the bottom seat
SEAT_POSITION_DIA = 0.02  # the top seat's axis to A, diametral zone
# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "top seat position to bottom seat": "0.02",
}
if (
    float(GEOMETRIC_TOLERANCES_MM["top seat position to bottom seat"])
    != SEAT_POSITION_DIA
):
    raise AssertionError("the top seat's position zone must print SEAT_POSITION_DIA")
SEAT_SPAN = BLOCK_HEIGHT - 2.0 * trammel.BEARING_RECESS - trammel.BEARING_WIDTH  # 13
SEAT_TILT_ARCMIN = math.degrees(SEAT_POSITION_DIA / 2.0 / SEAT_SPAN) * 60.0
BEARING_MISALIGNMENT_MAX_ARCMIN = 10.0  # SKF deep-groove ball bearing, 2 .. 10
if SEAT_TILT_ARCMIN > BEARING_MISALIGNMENT_MAX_ARCMIN:
    raise AssertionError("the seats' position zone tilts the pin past the 6200's limit")

# --- Printed stations, each from its datum face ------------------------------
BORE_STATION_X = BORE_X - DATUM_X  # 18
BORE_STATION_Y = 0.0 - DATUM_Y  # 20
HOLE_COLUMNS_X = (-BOLT_X - DATUM_X, BOLT_X - DATUM_X)  # 37, 63
HOLE_ROWS_Y = (-BOLT_Y - DATUM_Y, BOLT_Y - DATUM_Y)  # 7, 33
# The side screws: X from the -X end, Z from the bottom face (45, 55; 9).
SIDE_STATIONS_X = tuple(x - DATUM_X for x in SIDE_SCREW_X)
SIDE_ROW_Z = SIDE_SCREW_Z
# The model's origin-relative knobs (build globals), unprinted.
MODEL_KNOBS: dict[str, float] = {
    "BlockEndX": -BLOCK_X0,
    "BlockSideY": BLOCK_WIDTH / 2.0,
    "BoreX": abs(BORE_X),
    "BoltX": BOLT_X,
    "BoltY": BOLT_Y,
    "SideScrewX": abs(SIDE_SCREW_X[1]),
    "SideScrewZ": SIDE_SCREW_Z,
}

# --- Printed places ----------------------------------------------------------
# Hole stations three places (hole to hole, the docstring's carriage
# argument), the counterbore floor three (the screw engagement) and both
# seat depths three (the puller gap); bore stations, plan sizes and the
# height two (the counterbore walls and the puller gap); the web hole one;
# the seat corner a one-place MAX. The native hole callout prints the
# counterbore's sizes at the template's .XX (CALLOUT_PLACES), its depth as
# a reference.
HOLE_STATION_PLACES = 3
CALLOUT_PLACES = 2
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {"BlockLength": 2, "BlockWidth": 2},
    "Block": {"BlockHeight": 2},
    "TopBoreProfile": {
        "BoreStationX": 2,
        "BoreStationY": 2,
        "HoleColumn1X": HOLE_STATION_PLACES,
        "HoleColumn2X": HOLE_STATION_PLACES,
        "HoleRow1Y": HOLE_STATION_PLACES,
        "HoleRow2Y": HOLE_STATION_PLACES,
        "BoreDia": 3,
    },
    "TopBore": {"TopBoreDepth": 3},
    "BottomBore": {"BottomBoreDepth": 3},
    "ShoulderHoleProfile": {"ShoulderHoleDia": 1},
    "SeatFillets": {"SeatFilletR": 1},
    CBORE_FLOOR_REFERENCE: {"CboreFloor": CBORE_FLOOR_PLACES},
    SIDE_SCREW_REFERENCE: {
        "SideScrew1X": SIDE_STATION_PLACES,
        "SideScrew2X": SIDE_STATION_PLACES,
        "SideScrewRowZ": SIDE_STATION_PLACES,
    },
}
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    feature: set(names) for feature, names in DRAWING_PRECISION.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
DRAWING_VALUES: dict[str, float] = {
    "BlockLength": BLOCK_LENGTH,
    "BlockWidth": BLOCK_WIDTH,
    "BlockHeight": BLOCK_HEIGHT,
    "BoreStationX": BORE_STATION_X,
    "BoreStationY": BORE_STATION_Y,
    "HoleColumn1X": HOLE_COLUMNS_X[0],
    "HoleColumn2X": HOLE_COLUMNS_X[1],
    "HoleRow1Y": HOLE_ROWS_Y[0],
    "HoleRow2Y": HOLE_ROWS_Y[1],
    "BoreDia": BORE_DIA,
    "TopBoreDepth": BORE_DEPTH,
    "BottomBoreDepth": BORE_DEPTH,
    "ShoulderHoleDia": SHOULDER_HOLE_DIA,
    "SeatFilletR": SEAT_FILLET_RADIUS,
    "CboreFloor": CBORE_FLOOR,
    "SideScrew1X": SIDE_STATIONS_X[0],
    "SideScrew2X": SIDE_STATIONS_X[1],
    "SideScrewRowZ": SIDE_ROW_Z,
}
if set(DRAWING_VALUES) != set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("every marked pivot block dimension needs a value")
for _name, _value in DRAWING_VALUES.items():
    if abs(_value - round(_value, DRAWING_PRECISION_BY_NAME[_name])) > 1e-9:
        raise AssertionError(f"pivot block {_name} {_value} does not print as modelled")


def _band(name: str) -> float:
    return _BAND[DRAWING_PRECISION_BY_NAME[name]]


# Hole to hole: two stations' worst difference inside the screws' float.
SCREW_FLOAT = (HOLE_DIA - 4.0) / 2.0  # M4 in the Ø4.5 hole, each side
if (
    math.hypot(2.0 * _band("HoleColumn1X"), 2.0 * _band("HoleRow1Y"))
    > 2.0 * SCREW_FLOAT
):
    raise AssertionError("the hole stations' band exceeds the M4 screws' float")


# --- Side screws: head, float and walls ----------------------------------------
if SIDE_SCREW_X[0] != -SIDE_SCREW_X[1]:
    raise AssertionError("the side screws are no longer symmetric about X = 0")
_SIDE_BAND = _BAND[SIDE_STATION_PLACES]
_SIDE_CBORE_BAND = _BAND[SIDE_CBORE_PLACES]
# The head sinks at the shallowest counterbore, clears the smallest, and
# bears on the ring outside the largest drilled hole.
SIDE_HEAD_RECESS_MIN = SIDE_CBORE_DEPTH - _SIDE_CBORE_BAND - SIDE_SCREW_HEAD_HEIGHT
SIDE_HEAD_RECESS_MAX = SIDE_CBORE_DEPTH + _SIDE_CBORE_BAND - SIDE_SCREW_HEAD_HEIGHT
if SIDE_HEAD_RECESS_MIN < 0.1:
    raise AssertionError("the #8 head stands within 0.1 of the +Y face")
if SIDE_CBORE_DIA - _SIDE_CBORE_BAND <= SIDE_SCREW_HEAD_DIA:
    raise AssertionError("the #8 head does not clear its counterbore")
SIDE_HEAD_BEARING = (SIDE_SCREW_HEAD_DIA - SIDE_HOLE_DIA - DRILLED_BAND[0]) / 2.0
if SIDE_HEAD_BEARING < 0.5:
    raise AssertionError("the #8 head bears on too thin a ring")
# Hole to hole: TL-29's taps are spotted through these holes, so TL-22's two
# stations, held for their walls, still take at most half the pair's float.
SIDE_SCREW_FLOAT = (SIDE_HOLE_DIA - SIDE_SCREW_MAJOR) / 2.0  # each side
if 2.0 * _SIDE_BAND > SIDE_SCREW_FLOAT:
    raise AssertionError("the side stations' band exceeds half the #8 float")


def _rim_to_counterbore(
    x: float,
    z: float,
    r: float,
    dy: float,
    cbore_x: float,
    cbore_r: float,
    floor_z: float,
) -> float:
    """Least gap from a Y-axis circle (centre ``x``, ``z``, radius ``r``), ``dy``
    off the carriage hole's axis in Y, to that hole's counterbore (axis at
    ``cbore_x``, radius ``cbore_r``, open upward from ``floor_z``)."""
    gap = math.inf
    for step in range(3600):
        angle = math.tau * step / 3600
        px, pz = x + r * math.cos(angle), z + r * math.sin(angle)
        radial = max(0.0, math.hypot(px - cbore_x, dy) - cbore_r)
        gap = min(gap, math.hypot(radial, max(0.0, floor_z - pz)))
    return gap


def _side_walls(worst: bool) -> dict[str, float]:
    """The side holes' walls, nominal or at the printed bands' worst case.

    The +X side hole against the +X, +Y carriage hole (the -X pair mirrors
    it); stations from the -X end, Z from the bottom, Y from the -Y side. The
    carriage counterbore's floor prints from the bottom face (CBORE_FLOOR).
    """
    k = 1.0 if worst else 0.0
    band = k * _SIDE_BAND
    station = SIDE_STATIONS_X[1] + band
    column = HOLE_COLUMNS_X[1] - k * _band("HoleColumn1X")
    row = HOLE_ROWS_Y[1] + k * _band("HoleRow1Y")
    height = BLOCK_HEIGHT - k * _band("BlockHeight")
    floor_y = (
        BLOCK_WIDTH - k * _band("BlockWidth") - SIDE_CBORE_DEPTH - k * _SIDE_CBORE_BAND
    )
    cbore_r = (SIDE_CBORE_DIA + k * _SIDE_CBORE_BAND) / 2.0
    hole_r = (SIDE_HOLE_DIA + k * DRILLED_BAND[0]) / 2.0
    carriage_hole_r = (HOLE_DIA + k * DRILLED_BAND[0]) / 2.0
    carriage_cbore_r = (CBORE_DIA + k * _BAND[CALLOUT_PLACES]) / 2.0
    carriage_floor = CBORE_FLOOR - k * _band("CboreFloor")
    z_high, z_low = SIDE_ROW_Z + band, SIDE_ROW_Z - band
    bore_edge = (
        BORE_STATION_X + k * _band("BoreStationX") + (BORE_DIA + k * BORE_BAND[0]) / 2.0
    )
    cbore_dy = max(0.0, floor_y - row)
    return {
        "side counterbore to side counterbore": (
            SIDE_STATIONS_X[1] - SIDE_STATIONS_X[0] - 2.0 * band - 2.0 * cbore_r
        ),
        "side counterbore to carriage hole": math.hypot(
            max(0.0, column - station - cbore_r), cbore_dy
        )
        - carriage_hole_r,
        "side hole to carriage hole": column - station - hole_r - carriage_hole_r,
        "side counterbore to carriage counterbore": _rim_to_counterbore(
            station, z_high, cbore_r, cbore_dy, column, carriage_cbore_r, carriage_floor
        ),
        "side hole to carriage counterbore": _rim_to_counterbore(
            station, z_high, hole_r, 0.0, column, carriage_cbore_r, carriage_floor
        ),
        "side counterbore to bottom face": z_low - cbore_r,
        "side counterbore to top face": height - z_high - cbore_r,
        "side hole to bore": SIDE_STATIONS_X[0] - band - hole_r - bore_edge,
    }


# The outer race seats on the shoulder, so the web hole must stay within the
# 6200's Da max at its largest printed size, and clear the inner race's
# shoulder at its smallest so a puller can grip behind it.
if SHOULDER_HOLE_DIA + _band("ShoulderHoleDia") > BEARING_DA_MAX + 1e-9:
    raise AssertionError("the shoulder hole exceeds the 6200's Da max")
if SHOULDER_HOLE_DIA - _band("ShoulderHoleDia") <= BEARING_INNER_SHOULDER_D2:
    raise AssertionError("the shoulder hole does not clear the inner races")
# The web is the cavity behind the first inner race: thinnest block, deepest
# seats, against the collet puller's 3 mm.
PULLER_GAP_MIN = round(
    BLOCK_HEIGHT - _band("BlockHeight") - 2.0 * (BORE_DEPTH + _band("TopBoreDepth")),
    6,
)
if PULLER_GAP_MIN < PULLER_SPACE_MIN:
    raise AssertionError("the web leaves a puller under 3 mm behind a 6200")

# --- Rule 17: nominal argument (the TL-22 sheet's numbers) -------------------
_BORE_R = BEARING_OD / 2.0
_NEAR_HOLE = math.hypot(BORE_X + BOLT_X, BOLT_Y)  # 23.02, the (-13, +/-13) holes
WALLS_MM: dict[str, float] = {
    "bore to counterbore": _NEAR_HOLE - _BORE_R - CBORE_DIA / 2.0,
    "bore to hole": _NEAR_HOLE - _BORE_R - HOLE_DIA / 2.0,
    "counterbore to block side": BLOCK_WIDTH / 2.0 - BOLT_Y - CBORE_DIA / 2.0,
    "counterbore to +X end": BLOCK_X1 - BOLT_X - CBORE_DIA / 2.0,
    "bore to -X end": (BORE_X - _BORE_R) - BLOCK_X0,
    **_side_walls(worst=False),
}
for _wall, _mm in WALLS_MM.items():
    if _mm < WALL_TARGET:
        raise AssertionError(f"pivot block {_wall} wall {_mm:.3f} under the 2.0 target")

# --- Rule 17 at the printed bands' worst case --------------------------------
# Every station from its datum face: the -X end (X stations, and the +X end
# through BlockLength) and the -Y side (Y stations, and the +Y side through
# BlockWidth).
_BORE_R_MAX = BORE_DIA_MAX / 2.0
_HOLE_R_MAX = (HOLE_DIA + DRILLED_BAND[0]) / 2.0
_CBORE_R_MAX = (CBORE_DIA + _BAND[CALLOUT_PLACES]) / 2.0
_HOLE_BAND = _band("HoleColumn1X")
_NEAR_HOLE_MIN = math.hypot(
    HOLE_COLUMNS_X[0] - BORE_STATION_X - _band("BoreStationX") - _HOLE_BAND,
    BORE_STATION_Y - HOLE_ROWS_Y[0] - _band("BoreStationY") - _HOLE_BAND,
)
_LENGTH_MIN = BLOCK_LENGTH - _band("BlockLength")
_WIDTH_MIN = BLOCK_WIDTH - _band("BlockWidth")
WORST_WALLS: dict[str, float] = {
    "bore to counterbore": _NEAR_HOLE_MIN - _BORE_R_MAX - _CBORE_R_MAX,
    "bore to hole": _NEAR_HOLE_MIN - _BORE_R_MAX - _HOLE_R_MAX,
    "counterbore to block side": min(
        HOLE_ROWS_Y[0] - _HOLE_BAND,
        _WIDTH_MIN - (HOLE_ROWS_Y[1] + _HOLE_BAND),
    )
    - _CBORE_R_MAX,
    "counterbore to +X end": _LENGTH_MIN
    - (HOLE_COLUMNS_X[1] + _HOLE_BAND)
    - _CBORE_R_MAX,
    "bore to -X end": BORE_STATION_X - _band("BoreStationX") - _BORE_R_MAX,
    # The shoulder web between the two seats: thinnest block, deepest seats.
    "bearing shoulder": BLOCK_HEIGHT
    - _band("BlockHeight")
    - 2.0 * (BORE_DEPTH + _band("TopBoreDepth")),
    **_side_walls(worst=True),
}
for _wall, _mm in WORST_WALLS.items():
    if _mm < WALL_FLOOR:
        raise AssertionError(
            f"pivot block {_wall} wall {_mm:.3f} under the rule 17 floor"
        )
# drawing-guidelines.md rule 20: walls between the floor and the target, and
# the carriage screws' engagement under rule 18's 1.5D (the floor callout).
RULE_20_SHORTFALLS = {
    name: wall for name, wall in WORST_WALLS.items() if wall < WALL_TARGET
}
if "bearing shoulder" in RULE_20_SHORTFALLS:
    raise AssertionError("the bearing shoulder web is under the 2.0 target")
RULE_20_SHORTFALLS["M4 engagement in carriage"] = ENGAGEMENT_MIN
# The side counterbores' shortfall, stated in their callout (rule 20).
SIDE_WALL_MIN = min(
    wall for name, wall in RULE_20_SHORTFALLS.items() if name.startswith("side ")
)
# The three-place counterbore sizes set these walls (review c4r3: say so).
SIDE_WALL_CALLOUT = f"SETS C'BORE WALL {SIDE_WALL_MIN:.2f} MIN"

# Each bearing seats fully below its face at the shallowest printed seat.
if BORE_DEPTH - _band("TopBoreDepth") < trammel.BEARING_WIDTH:
    raise AssertionError("a bearing stands proud of the pivot block face")


# --- Sheet callouts -------------------------------------------------------------
def _min_text(mm: float) -> str:
    """A worst-case minimum at two places, never rounded up."""
    return f"{math.floor(mm * 100.0 + 1e-6) / 100.0:.2f}"


# The functions the two-place plan sizes and the height, and the
# three-place seat depths, serve (rule 4; docstring "The shoulder").
LENGTH_WALL_CALLOUT = (
    f"SETS C'BORE WALL {_min_text(WORST_WALLS['counterbore to +X end'])} MIN"
)
WIDTH_WALL_CALLOUT = (
    f"SETS C'BORE\nWALL {_min_text(WORST_WALLS['counterbore to block side'])} MIN"
)
# The web the seat depths set (review r8: named, once per depth, not on the
# 24.00) and the hole through it (review r6); review r11 took the web for a
# rule-17 wall, so the rows name the collet puller it serves, and review r12
# read the three places as over-specified, so they say what the puller needs
# (at two places the web would drop to 2.47). "PULLER" / "NEEDS 3.0" on two
# rows: the block hangs in the ~30 mm left of section A-A.
PULLER_GAP_CALLOUT = (
    f"SETS WEB\n{_min_text(PULLER_GAP_MIN)} MIN\nPULLER\nNEEDS {PULLER_SPACE_MIN:.1f}"
)
SHOULDER_HOLE_CALLOUT = "THRU WEB\nPULLER CLEARANCE\nBEHIND 6200\nINNER RACES"
# A horizontal dimension's line runs along its LAST row's baseline, so B-B's
# floor height carries its rows over the value (review r7: under it, its
# line, shorter than the rows, struck "(5 DEEP THREAD)"; draw_ch_rocker_arm_
# tl_filing_button EDGE_KEEP). The 70's one row stands under its value, on
# its own line, as the 40.00's does (close-c4-r5: over the value, it sat
# between the 63.000 and 70.00 lines and read as either's); the ~67 mm row
# runs inside the 140 mm line.
CALLOUTS_ABOVE = {
    "BoreDia": "2X",
    "SeatFilletR": "2X",
    "CboreFloor": CBORE_FLOOR_CALLOUT,
}
# The side row's 9.000 reads from the bottom face (c4 review), named by the
# carriage it seats on (close-c4 review). In A-A since close-c4-r4 (owner
# ruling: the section names its own top face), it hangs beyond its span, so
# narrow rows keep the block clear of the side view. Its three places serve
# the #8 float to the bracket (rule 4, close-c4-r5): the mate prints by its
# short number (owner ruling 2026-10-17), the full one too wide for the gap.
SIDE_ROW_MATE = SIDE_SCREW_MATE.removeprefix("MHA-CH-006-")
SIDE_ROW_CALLOUT = f"FROM\nCARRIAGE\nSEAT FACE;\nMATCHES\n{SIDE_ROW_MATE}"
CALLOUTS_BELOW = {
    "BlockLength": LENGTH_WALL_CALLOUT,
    "BlockWidth": WIDTH_WALL_CALLOUT,
    # No row on the 24.00 (review r8): the web's 3.23 is the depths'.
    "TopBoreDepth": PULLER_GAP_CALLOUT,
    "BottomBoreDepth": PULLER_GAP_CALLOUT,
    "BoreDia": BORE_CALLOUT,
    "ShoulderHoleDia": SHOULDER_HOLE_CALLOUT,
    "SideScrewRowZ": SIDE_ROW_CALLOUT,
}
SURFACE_FINISHES = ()
# The side screws' callout rows under the native hole callout: the mate the
# three-place stations serve (rule 4) and the counterbore walls' shortfall.
SIDE_CALLOUT_BELOW = f"MATCHES {SIDE_SCREW_MATE}\n{SIDE_WALL_CALLOUT}"
# The fit is on the seat callout; the burr line is the title block's.
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
