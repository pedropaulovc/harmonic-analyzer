r"""Pure-data contract for the cone gears' dividing-head index plate (MHA-DT-03-TL-01).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md): a custom
index plate for the Precision Matthews BS-0 dividing head (40:1 worm), which
cuts the MHA-DT-03 cone gears. The stock BS-0 plates (A: 15-20; B: 21 23 27
29 31 33; C: 37 39 41 43 47 49) cannot index 96, 102 or 114 teeth. With a
40:1 worm the crank turns 40/N per tooth:

* 96T: 40/96 = 10/24, ten holes on the 24-hole circle;
* 102T: 40/102 = 20/51, twenty holes on the 51-hole circle;
* 114T: 40/114 = 20/57, twenty holes on the 57-hole circle.

MEASURED on the owner's stock BS-0 plate (owner fact 2026-11-24, verbatim:
"plate thickness 0.2770 dia 3.94; hole 0.8270; pin hpoles 0.120 dia blind
0.1635 deep; 3x screw holes thru 15/64 countersunk 0.3455 dia depth 0.1830")
and on its index pin (owner fact 2026-11-24, verbatim: "0.117 in dia dividing
head pin"): the plate's OD, its bore, the maker's own pin-hole size, the
screw holes' count, drill and countersink diameter. STILL GUESSES (#2157
tracks them): the hub the bore pilots on, the mounting screw's thread and
head form, its bolt circle and clocking, and the three hole-circle diameters
against the index arm's reach. Replace each ``# GUESS (#2157)`` value with
the measured one. The maker's manual (owner photographs 2026-11-24) gives the
1:40 worm and the stock circles and no plate dimension.

Thickness: the stock plate is .2770; this one is cut from the owned 1/4 in
plate, skimmed to .24, so it sits .037 lower under the pin. The stock pin
holes are blind, .1635 deep, so the pin reaches no deeper than that into a
plate; these holes are through.

Frame (the SolidWorks model): the plate's axis is model Z through the
origin. The back face (Z0) seats on the head; the front face (Z = THICKNESS)
faces the index arm and carries the mounting screws' counterbores. One hole of
every index circle lies on +Y (the vertical centreline); the mounting holes
sit at 150, 270 and 30 degrees, one on that centreline at -Y.

Precision: the three hole circles are BASIC and every index hole carries a
position frame to the bore, datum A (``INDEX_POSITION``), so neither the
title block's ±1° angle nor its three-place band governs the spacing. The
zone is what the shop holds on a drilled hole located from a datum bore
(drawing-guidelines "What the shop holds": ±.005, a Ø.014 zone); the 40:1
worm divides what is left.
The pin holes are drilled just over the head's index pin with the owned #31
drill and take the title block's DRILLED HOLES band (owner ruling 2026-11-23,
tool audit Q15, verbatim: "Wait for #2157 (pin measurement), then drill just
over the pin (+.004/0) with an owned drill, no reamer (revises the 2026-11-08
reamed-fit ruling)."). The pin is the gauge: it enters every hole. The play
of the pin in its hole and the position zone are an indexing error at the
crank, divided by the 40:1 worm at the gear (``INDEX_ERROR_*`` below). The
bore pilots the plate on the head's hub: never under the stock plate's
measured .8270 bore, +.003/0, until the hub itself is measured (#2157).

Rule 17 shortfall (stated on the sheet; owner ruling 2026-11-02, RV-01 in the
part's machinist_exceptions): #31 holes on the 57- and 51-hole circles leave
.060 to .062 in between neighbouring holes and between those two circles, at
the worst case of the drilled-hole band and the position zone: at the .060
floor, below the .080 target. The two circles stand .020 larger than they did
while the holes were reamed, which is what the wider drilled-hole zone costs;
the plate's 3.94 OD leaves no larger radius at the .080 edge target. The
24-hole circle stands at Ø2.700, not the brief's Ø2.800, so its web to the
51-hole circle meets the .080 target.

The head is shop equipment with no drawing number; the sheet names it once
(RV-03, delegated ruling 2026-11-07).
"""

from __future__ import annotations

import math

import _config
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import (
    drilled_oversize_mm,
    drilled_undersize_mm,
    printed_band_mm,
)

PART_NAME = "dt-cone-gear-tl-index-plate"
UNIT = drawing_unit(
    "parts/dt-cone-gear-tl-index-plate", _config.parts("dt-cone-gear-tl-index-plate")
)
assert UNIT == "in"
INCH = 25.4
TRACKING_ISSUE = "https://github.com/pedropaulovc/harmonic-analyzer/issues/2157"

# --- Plate envelope ------------------------------------------------------------
# Owner fact 2026-11-24 (stock plate): "dia 3.94".
PLATE_DIA = 3.94 * INCH
# Owner fact 2026-11-24 (stock plate): "hole 0.8270". The bore pilots on the
# head's plate hub (unmeasured, #2157): never under the stock plate's bore.
BORE_DIA = 0.827 * INCH
BORE_DEVIATIONS = (0.0, 0.003 * INCH)
# Owner fact 2026-11-24 (stock plate): "plate thickness 0.2770". The owned
# 1/4 in plate cannot make that: both faces skimmed, .24.
STOCK_PLATE_THICKNESS = 0.277 * INCH
THICKNESS = 0.24 * INCH
# Owner fact 2026-11-24 (stock plate): "pin hpoles 0.120 dia blind 0.1635
# deep": the maker runs the same pin in the same .120 hole, and the pin
# enters a plate no deeper than the blind depth.
STOCK_PIN_HOLE_DIA = 0.120 * INCH
STOCK_PIN_HOLE_DEPTH = 0.1635 * INCH
# A pin that reached the full blind depth of a stock plate still stops
# inside this thinner, lower plate's through hole, and keeps most of a pin
# diameter of engagement.
PIN_ENGAGEMENT_MAX = STOCK_PIN_HOLE_DEPTH - (STOCK_PLATE_THICKNESS - THICKNESS)
if not 0.0 < PIN_ENGAGEMENT_MAX < THICKNESS:
    raise AssertionError("the index pin leaves or passes through the plate")

# --- Worm and the gears this plate indexes ------------------------------------
WORM_RATIO = 40  # BS-0 dividing head
GEAR_TEETH = (96, 102, 114)  # dt-cone-gear family members no stock plate indexes


def holes_per_tooth(teeth: int, circle: int) -> float:
    """Holes the index pin advances on ``circle`` per tooth of ``teeth``."""
    return WORM_RATIO * circle / teeth


# --- Index-hole circles: hole count -> bolt-circle diameter -------------------
# The BS-0 head's index pin (owner fact 2026-11-24, verbatim: "0.117 in dia
# dividing head pin"; #2157).
INDEX_PIN_DIA = 0.117 * INCH
# The owned drill just over the pin (owner ruling 2026-11-23, tool audit Q15):
# #32 (.1160) is under the pin; #31 (.1200) is the next size of the owned
# 115-piece index (shop-equipment tools.drill-31). No reamer.
INDEX_HOLE_DRILL = "#31"
INDEX_HOLE_DIA = 0.120 * INCH
# The title block's DRILLED HOLES row: the model dimension carries no band.
INDEX_HOLE_DEVIATIONS = (
    -drilled_undersize_mm(unit=UNIT),
    drilled_oversize_mm(unit=UNIT),
)
INDEX_HOLE_PLACES = 3
# Diametral play of the pin in a hole, least and most; the pin always enters.
INDEX_PIN_CLEARANCE = (
    INDEX_HOLE_DIA + INDEX_HOLE_DEVIATIONS[0] - INDEX_PIN_DIA,
    INDEX_HOLE_DIA + INDEX_HOLE_DEVIATIONS[1] - INDEX_PIN_DIA,
)
if INDEX_PIN_CLEARANCE[0] <= 0.0:
    raise AssertionError("the BS-0 index pin does not enter a least-size hole")
RING_COUNTS = (57, 51, 24)
RING_PCDS = {
    57: 3.620 * INCH,  # GUESS (#2157): outermost at the .080 edge target
    51: 3.220 * INCH,  # GUESS (#2157)
    24: 2.700 * INCH,  # GUESS (#2157): web to the 51 circle at the .080 target
}
RING_TEETH = {57: 114, 51: 102, 24: 96}
for _circle, _teeth in RING_TEETH.items():
    _advance = holes_per_tooth(_teeth, _circle)
    if abs(_advance - round(_advance)) > 1e-9:
        raise AssertionError(f"{_circle}-hole circle does not index {_teeth}T")

# --- Three counterbored mounting holes ----------------------------------------
# Owner fact 2026-11-24 (stock plate): "3x screw holes thru 15/64 countersunk
# 0.3455 dia depth 0.1830", corrected the same day, verbatim: "not countersunk
# counterbored;". So the stock seat is a Ø.3455 counterbore .1830 deep in a
# .2770 plate: .094 of plate under the screw head. The screw itself (thread,
# head) is unmeasured (#2157).
MOUNT_COUNT = 3
MOUNT_PCD = 1.500 * INCH  # GUESS (#2157)
# The largest thread a 15/64 hole passes is the candidate's body: M5.
MOUNT_SCREW_BODY_DIA = 5.0
# 15/64 = .2344: printed on the three-place grid, drilled 15/64.
MOUNT_HOLE_DRILL = "15/64"
MOUNT_HOLE_DIA = 0.234 * INCH
STOCK_CBORE_DIA = 0.3455 * INCH
STOCK_CBORE_DEPTH = 0.183 * INCH
CBORE_DIA = 0.35 * INCH  # stock .3455 on the .XX grid
CBORE_PLACES = 2
# This plate is thinner than stock: the counterbore is shallower by the same
# amount, so the plate under the head (and the screw's reach into the head)
# stays the stock plate's. .145 rather than .146 keeps that seat at rule 17's
# .080 target with the thickness and depth bands both against it.
CBORE_DEPTH = 0.145 * INCH
CBORE_DEPTH_PLACES = 3
CBORE_SEAT = THICKNESS - CBORE_DEPTH  # .095; stock .2770 - .1830 = .094
# Seed hole at 150 degrees; the pattern adds 270 (on the vertical centreline)
# and 30. Its row plane is the Top plane offset by the seed's +Y.
MOUNT_SEED_DEG = 150.0
MOUNT_X_FACTOR = abs(math.cos(math.radians(MOUNT_SEED_DEG))) / 2.0  # x / PCD
MOUNT_Y_FACTOR = math.sin(math.radians(MOUNT_SEED_DEG)) / 2.0  # y / PCD
MOUNT_SEED = (
    -MOUNT_PCD * MOUNT_X_FACTOR,
    MOUNT_PCD * MOUNT_Y_FACTOR,
)

# --- Printed precision --------------------------------------------------------
# Places: OD, thickness and the counterbore at .XX; the bore (banded, the
# hub pilot), the bolt circles (index arm reach, head taps) and the drill
# sizes at .XXX (rule 3: drill diameters print three places).
_XX = printed_band_mm(2, unit=UNIT)
_XXX = printed_band_mm(3, unit=UNIT)

if not MOUNT_SCREW_BODY_DIA < MOUNT_HOLE_DIA <= 15.0 / 64.0 * INCH:
    raise AssertionError("mounting hole is not the stock plate's 15/64 drill")
if abs(CBORE_DIA - STOCK_CBORE_DIA) > _XX:
    raise AssertionError("counterbore is not the stock plate's Ø.3455")
if abs(CBORE_SEAT - (STOCK_PLATE_THICKNESS - STOCK_CBORE_DEPTH)) > 0.0015 * INCH:
    raise AssertionError("the plate under the screw head is not the stock plate's")
CBORE_SEAT_MIN = (THICKNESS - _XX) - (CBORE_DEPTH + _XXX)
if CBORE_SEAT_MIN < WALL_TARGET_MM - 1e-9:
    raise AssertionError("counterbore floor under rule 17's .080 target")


# --- Rule 17 at the worst case of the printed bands ---------------------------
# Each index hole's centre may stand anywhere in its Ø INDEX_POSITION zone about
# its BASIC true position, so two neighbours close by the zone's full width.
# The sheet's position frames print these inch zones (Ø, to datum A): the
# shop's drilled-hole location from a datum bore, ±.005 (a Ø.014 zone), not
# the reamed-pattern Ø.004 the holes carried while they were reamed.
GEOMETRIC_TOLERANCES_IN: dict[str, str] = {"index-hole position": ".014"}
INDEX_POSITION = float(GEOMETRIC_TOLERANCES_IN["index-hole position"]) * INCH
BORE_DATUM = "A"
BASIC_DIMENSIONS = frozenset(f"Ring{n}Pcd" for n in RING_COUNTS)


def _pitch(circle: int) -> float:
    """BASIC centre distance between neighbouring holes of ``circle``."""
    return RING_PCDS[circle] * math.sin(math.pi / circle)


_INDEX_R_MAX = (INDEX_HOLE_DIA + INDEX_HOLE_DEVIATIONS[1]) / 2.0
_CBORE_R_MAX = (CBORE_DIA + _XX) / 2.0
WEBS_MM: dict[str, float] = {
    **{
        f"{n}-hole circle, between holes": _pitch(n)
        - 2.0 * _INDEX_R_MAX
        - INDEX_POSITION
        for n in RING_COUNTS
    },
    "57-hole circle to plate edge": (PLATE_DIA - _XX) / 2.0
    - RING_PCDS[57] / 2.0
    - _INDEX_R_MAX
    - INDEX_POSITION / 2.0,
    "57- to 51-hole circle": (RING_PCDS[57] - RING_PCDS[51]) / 2.0
    - 2.0 * _INDEX_R_MAX
    - INDEX_POSITION,
    "51- to 24-hole circle": (RING_PCDS[51] - RING_PCDS[24]) / 2.0
    - 2.0 * _INDEX_R_MAX
    - INDEX_POSITION,
    "24-hole circle to counterbores": (RING_PCDS[24] - INDEX_POSITION) / 2.0
    - (MOUNT_PCD + _XXX) / 2.0
    - _INDEX_R_MAX
    - _CBORE_R_MAX,
    "counterbores to bore": (MOUNT_PCD - _XXX) / 2.0
    - _CBORE_R_MAX
    - (BORE_DIA + BORE_DEVIATIONS[1]) / 2.0,
}
# The two fine circles stand between rule 17's .060 floor and its .080 target
# (owner ruling RV-01); every other wall meets the target.
SHORT_WEBS = frozenset(
    {
        "57-hole circle, between holes",
        "51-hole circle, between holes",
        "57- to 51-hole circle",
    }
)
for _wall, _mm in WEBS_MM.items():
    if _wall in SHORT_WEBS:
        if not WALL_FLOOR_MM <= _mm < WALL_TARGET_MM:
            raise AssertionError(
                f"index plate {_wall} web {_mm:.3f} is not the stated shortfall"
            )
    elif _mm < WALL_TARGET_MM:
        raise AssertionError(f"index plate {_wall} wall {_mm:.3f} under rule 17")
WEB_MIN_MM = min(WEBS_MM.values())
WEB_MIN_PRINTED = math.floor(WEB_MIN_MM / INCH * 100.0) / 100.0  # .XX, rounded down
if WEB_MIN_PRINTED <= 0.0:
    raise AssertionError("index plate web shortfall prints as zero")
# RV-01 accepts webs down to .02 in, no thinner.
RULED_WEB_MIN_MM = 0.02 * INCH
if WEB_MIN_MM < RULED_WEB_MIN_MM:
    raise AssertionError("index plate web is thinner than owner ruling RV-01 accepts")

# --- Indexing error of a drilled pin hole -------------------------------------
# The pin may stand anywhere in its hole, half the diametral play either way
# along the circle, and the hole anywhere in its position zone, half the zone
# either way: a crank angle error of that sum over the circle's radius, which
# the worm divides at the gear. Worst case of both, per gear, in degrees at
# the gear and as a fraction of that gear's tooth pitch.
INDEX_ERROR_TANGENTIAL_MM = (INDEX_PIN_CLEARANCE[1] + INDEX_POSITION) / 2.0
INDEX_ERROR_GEAR_DEG: dict[int, float] = {
    teeth: math.degrees(INDEX_ERROR_TANGENTIAL_MM / (RING_PCDS[circle] / 2.0))
    / WORM_RATIO
    for circle, teeth in RING_TEETH.items()
}
INDEX_ERROR_TOOTH_FRACTION: dict[int, float] = {
    teeth: error / (360.0 / teeth) for teeth, error in INDEX_ERROR_GEAR_DEG.items()
}
# Either way of true position, each tooth space stands within half of one
# percent of its pitch; a reamed sliding fit bought nothing a cone gear
# needs.
INDEX_ERROR_TOOTH_FRACTION_MAX = 0.005
if max(INDEX_ERROR_TOOTH_FRACTION.values()) > INDEX_ERROR_TOOTH_FRACTION_MAX:
    raise AssertionError("drilled index holes misplace a tooth by over 0.5 % of pitch")

# --- Model globals: name -> value (mm); the build sets each and drives from it --
GLOBALS: dict[str, float] = {
    "PlateDia": PLATE_DIA,
    "BoreDia": BORE_DIA,
    "PlateThick": THICKNESS,
    "IndexHoleDia": INDEX_HOLE_DIA,
    **{f"Ring{n}Pcd": RING_PCDS[n] for n in RING_COUNTS},
    "MountPcd": MOUNT_PCD,
    "MountHoleDia": MOUNT_HOLE_DIA,
    "CboreDia": CBORE_DIA,
    "CboreDepth": CBORE_DEPTH,
}

# --- Drawing -------------------------------------------------------------------
# Each circle's seed hole sketch owns its circle diameter (a construction
# circle) and the hole size; the sheet prints the 57-hole seed's size once
# for all 132 holes.
PRINTED_HOLE = "Ring57HoleDia"
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateDia", "BoreDia"},
    "Plate": {"PlateThick"},
    "Ring57Profile": {"Ring57Pcd", PRINTED_HOLE},
    "Ring51Profile": {"Ring51Pcd"},
    "Ring24Profile": {"Ring24Pcd"},
    "MountHoleProfile": {"MountPcd", "MountHoleDia"},
}
_THREE_PLACE = frozenset(
    {
        "BoreDia",
        "MountHoleDia",
        "MountPcd",
        *(f"Ring{n}Pcd" for n in RING_COUNTS),
    }
)


def _places(name: str) -> int:
    if name == PRINTED_HOLE:
        return INDEX_HOLE_PLACES
    return 3 if name in _THREE_PLACE else 2


DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {name: _places(name) for name in names}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dims in DRAWING_PRECISION.values() for name, places in dims.items()
}
_PRINTED_VALUES = {
    "PlateDia": PLATE_DIA,
    "BoreDia": BORE_DIA,
    "PlateThick": THICKNESS,
    PRINTED_HOLE: INDEX_HOLE_DIA,
    **{f"Ring{n}Pcd": RING_PCDS[n] for n in RING_COUNTS},
    "MountPcd": MOUNT_PCD,
    "MountHoleDia": MOUNT_HOLE_DIA,
}
DRAWING_VALUES_BY_NAME = _PRINTED_VALUES
if set(_PRINTED_VALUES) != set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("every printed index plate dimension needs a value")
# Fabricated nominals sit on their printed inch grid (rule 3).
for _name, _value in _PRINTED_VALUES.items():
    _inches = _value / INCH
    _places = DRAWING_PRECISION_BY_NAME[_name]
    if abs(_inches - round(_inches, _places)) > 1e-9:
        raise AssertionError(
            f"index plate {_name} {_inches} in is off its .{'X' * _places} grid"
        )


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as the sheet prints it: decimal inch, no leading zero."""
    text = f"{value_mm / INCH:.{places}f}"
    return text[1:] if text.startswith("0.") else text


# The head is shop equipment with no drawing number: the sheet names it once,
# in full, and the callouts call it BS-0 HEAD (RV-03: Delegated ruling
# 2026-11-07 (Main), no precedent; owner review #2144).
HEAD = "BS-0 HEAD"
HEAD_NOTE = f"1. {HEAD}: PM BS-0 DIVIDING HEAD\n   (SHOP EQUIPMENT)."
CBORE_CALLOUT = (
    f"<HOLE-SPOT><MOD-DIAM>{inch_text(CBORE_DIA, CBORE_PLACES)}"
    f" <HOLE-DEPTH> {inch_text(CBORE_DEPTH, CBORE_DEPTH_PLACES)}"
)
HOLE_COUNT = sum(RING_COUNTS)
CALLOUTS_ABOVE: dict[str, str] = {
    PRINTED_HOLE: f"{HOLE_COUNT}X",
    **{f"Ring{n}Pcd": f"{n}X EQ SP ON" for n in RING_COUNTS},
    "MountHoleDia": f"{MOUNT_COUNT}X",
    "MountPcd": f"{MOUNT_COUNT}X EQ SP ON",
}
# Rule 20: the known web shortfall is stated as a plain fact at the holes; it
# emits the stated shortfall of owner ruling RV-01 (machinist_exceptions).
# Each callout is its size and process lines plus at most two lines of words
# (rule 7); the counterbore prints with its symbol (rule 26).  A location
# carries its value and band only (rule 7), so the mounting holes' bolt
# circle states its pattern as the index circles do, and the mate rides the
# holes' size callout (fan-out round 5).  The bottom hole stands on the
# centre mark's vertical line, so the pattern's clocking is the drawn 90
# degrees, as for the index circles.
WEB_CALLOUT = f"WEB {inch_text(WEB_MIN_PRINTED * INCH, 2)} MIN"
CALLOUTS_BELOW: dict[str, str] = {
    PRINTED_HOLE: (
        f"{INDEX_HOLE_DRILL} DRILL THRU\n{HEAD} INDEX PIN ENTERS\n{WEB_CALLOUT}"
    ),
    "BoreDia": f"BORE THRU\nLOCATING FIT ON\n{HEAD} PLATE HUB",
    "MountHoleDia": f"DRILL THRU\n{CBORE_CALLOUT}\nFOR {HEAD}\nPLATE SCREWS",
}
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
