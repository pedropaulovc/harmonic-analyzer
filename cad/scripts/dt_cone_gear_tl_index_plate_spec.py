r"""Pure-data contract for the cone gears' dividing-head index plate (MHA-DT-03-TL-01).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md): a custom
index plate for the Precision Matthews BS-0 dividing head (40:1 worm), which
cuts the MHA-DT-03 cone gears. The stock BS-0 plates (A: 15-20; B: 21 23 27
29 31 33; C: 37 39 41 43 47 49) cannot index 96, 102 or 114 teeth. With a
40:1 worm the crank turns 40/N per tooth:

* 96T: 40/96 = 10/24, ten holes on the 24-hole circle;
* 102T: 40/102 = 20/51, twenty holes on the 51-hole circle;
* 114T: 40/114 = 20/57, twenty holes on the 57-hole circle.

BEST GUESSES, every one (#2157 tracks the measurement of the owner's BS-0
plate and head): the plate envelope comes from a Hobby-Machinist member's
measurement of a BS-0 plate, 3.938 OD x .829 ID x .218 thick with three
mounting holes (post #8, https://www.hobby-machinist.com/threads/
index-plate-size-used-on-bs-0-or-bs-1-import-dividing-head.46769/). The
mounting screw, its countersink and bolt circle, the index-pin hole size and
the three hole-circle diameters are guesses within that envelope. Replace
each ``# GUESS (#2157)`` value with the measured one.

Frame (the SolidWorks model): the plate's axis is model Z through the
origin. The back face (Z0) seats on the head; the front face (Z = THICKNESS)
faces the index arm and carries the mounting screws' countersinks. One hole of
every index circle lies on +Y (the vertical centreline); the mounting holes
sit at 150, 270 and 30 degrees, one on that centreline at -Y.

Precision: the three hole circles are BASIC and every index hole carries a
position frame to the bore, datum A (``INDEX_POSITION``), so neither the
title block's ±1° angle nor its three-place band governs the spacing; a DRO
bolt-circle drill holds the zone, and the 40:1 worm divides what is left.
The pin holes are reamed to a sliding fit on the head's index pin (delegated
ruling 2026-11-07, owner review #2144, pending owner confirmation): a drilled
hole holds only the drilled-hole row, not the Ø.004 zone. The bore pilots the
plate on the head's hub at the title block's .XXX (``HUB_DIA`` is its least
limit, the measured stock bore), so the hole circles stay concentric with the
crank; the 40:1 worm divides what eccentricity is left.

Rule 17 shortfall (stated on the sheet; owner ruling 2026-11-02, RV-01 in the
part's machinist_exceptions, provisional until #2157): Ø.1570
holes on the 57- and 51-hole circles leave about .035 in between neighbouring
holes and between those two circles, at the worst case of the ream band and
the position zone, below the .060 floor. The plate's
3.94 OD leaves no larger radius at the .080 edge target; a smaller measured
pin is the likely cure. The 24-hole circle stands at Ø2.700, not the brief's
Ø2.800, so its web to the 51-hole circle meets the .080 target.

The head is shop equipment with no drawing number; the sheet names it once
(RV-03, delegated ruling 2026-11-07).
"""

from __future__ import annotations

import math

import _config
from _hole_spec import CLEARANCE_MM
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm

PART_NAME = "dt-cone-gear-tl-index-plate"
UNIT = drawing_unit(
    "parts/dt-cone-gear-tl-index-plate", _config.parts("dt-cone-gear-tl-index-plate")
)
assert UNIT == "in"
INCH = 25.4
TRACKING_ISSUE = "https://github.com/pedropaulovc/harmonic-analyzer/issues/2157"

# --- Plate envelope ------------------------------------------------------------
PLATE_DIA = 3.94 * INCH  # GUESS (#2157): forum 3.938 OD on the .XX grid
HUB_DIA = 0.829 * INCH  # GUESS (#2157): forum .829 ID, the stock plate's bore
THICKNESS = 0.22 * INCH  # GUESS (#2157): forum .218 on the .XX grid
# The bore pilots on the head's plate hub at the title block's .XXX: its
# least limit is the stock plate's bore (asserted below).
BORE_DIA = 0.834 * INCH

# --- Worm and the gears this plate indexes ------------------------------------
WORM_RATIO = 40  # BS-0 dividing head
GEAR_TEETH = (96, 102, 114)  # dt-cone-gear family members no stock plate indexes


def holes_per_tooth(teeth: int, circle: int) -> float:
    """Holes the index pin advances on ``circle`` per tooth of ``teeth``."""
    return WORM_RATIO * circle / teeth


# --- Index-hole circles: hole count -> bolt-circle diameter -------------------
INDEX_HOLE_DIA = 0.157 * INCH  # GUESS (#2157): Ø4 mm index-pin class
# Reamed to a sliding fit on the head's index pin (Owner ruling 2026-11-08 (Pedro), #2144 item 9.4).
INDEX_HOLE_DEVIATIONS = (0.0, 0.0005 * INCH)
INDEX_HOLE_PLACES = 4
RING_COUNTS = (57, 51, 24)
RING_PCDS = {
    57: 3.600 * INCH,  # GUESS (#2157): outermost at the .080 edge target
    51: 3.200 * INCH,  # GUESS (#2157)
    24: 2.700 * INCH,  # GUESS (#2157): web to the 51 circle at the .080 target
}
RING_TEETH = {57: 114, 51: 102, 24: 96}
for _circle, _teeth in RING_TEETH.items():
    _advance = holes_per_tooth(_teeth, _circle)
    if abs(_advance - round(_advance)) > 1e-9:
        raise AssertionError(f"{_circle}-hole circle does not index {_teeth}T")

# --- Three countersunk mounting holes -----------------------------------------
MOUNT_COUNT = 3
MOUNT_PCD = 1.500 * INCH  # GUESS (#2157)
MOUNT_SCREW = "#8"  # GUESS (#2157): #8 82 degree flat head (M4 class)
MOUNT_SCREW_BODY_DIA = 0.164 * INCH
MOUNT_HEAD_DIA_MAX = 0.332 * INCH  # ASME B18.6.3 #8 flat head, theoretical sharp
# The repo's #8 normal-fit clearance (Hole Wizard table) prints as a #9 drill.
MOUNT_HOLE_DIA = 0.196 * INCH
CSK_DIA = 0.35 * INCH  # GUESS (#2157)
CSK_PLACES = 2
CSK_ANGLE = 82.0  # the flat head's own included angle
CSK_FLANK_ANGLE = 90.0 - CSK_ANGLE / 2.0  # face to flank, the sketch's
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
# Places: OD, thickness and the countersink at .XX; the bore (the hub pilot),
# the bolt circles (index arm reach, head taps) and the drill size at .XXX
# (rule 3: drill diameters print three places), every one at the title
# block's band; the reamed index holes at .XXXX with their band.
_XX = printed_band_mm(2, unit=UNIT)
_XXX = printed_band_mm(3, unit=UNIT)

if BORE_DIA - _XXX < HUB_DIA - 1e-9:
    raise AssertionError("the bore's least printed limit does not pass the head's hub")

# The three-place print rounds the wizard table's 4.978 mm.
if abs(CLEARANCE_MM[(MOUNT_SCREW, "normal")] - MOUNT_HOLE_DIA) > 0.0005 * INCH:
    raise AssertionError("the printed #8 clearance is not the repo's normal fit")
if MOUNT_HOLE_DIA <= MOUNT_SCREW_BODY_DIA:
    raise AssertionError("mounting hole does not clear the #8 body")
# The smallest printed countersink still sinks the largest head flush.
if (CSK_DIA - _XX) < MOUNT_HEAD_DIA_MAX:
    raise AssertionError("#8 head stands proud of the plate face")
CSK_DEPTH_MAX = (CSK_DIA + _XX) / 2.0 / math.tan(math.radians(CSK_ANGLE / 2.0))
if CSK_DEPTH_MAX >= THICKNESS - _XX:
    raise AssertionError("countersink cone breaks through the plate")


# --- Rule 17 at the worst case of the printed bands ---------------------------
# Each index hole's centre may stand anywhere in its Ø INDEX_POSITION zone about
# its BASIC true position, so two neighbours close by the zone's full width.
# The sheet's position frames print these inch zones (Ø, to datum A).
GEOMETRIC_TOLERANCES_IN: dict[str, str] = {"index-hole position": ".004"}
INDEX_POSITION = float(GEOMETRIC_TOLERANCES_IN["index-hole position"]) * INCH
BORE_DATUM = "A"
BASIC_DIMENSIONS = frozenset(f"Ring{n}Pcd" for n in RING_COUNTS)


def _pitch(circle: int) -> float:
    """BASIC centre distance between neighbouring holes of ``circle``."""
    return RING_PCDS[circle] * math.sin(math.pi / circle)


_INDEX_R_MAX = (INDEX_HOLE_DIA + INDEX_HOLE_DEVIATIONS[1]) / 2.0
_CSK_R_MAX = (CSK_DIA + _XX) / 2.0
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
    "24-hole circle to countersinks": (RING_PCDS[24] - INDEX_POSITION) / 2.0
    - (MOUNT_PCD + _XXX) / 2.0
    - _INDEX_R_MAX
    - _CSK_R_MAX,
    "countersinks to bore": (MOUNT_PCD - _XXX) / 2.0
    - _CSK_R_MAX
    - (BORE_DIA + _XXX) / 2.0,
}
# The two fine circles fall short of rule 17's floor (owner ruling RV-01);
# every other wall meets the .080 target.
SHORT_WEBS = frozenset(
    {
        "57-hole circle, between holes",
        "51-hole circle, between holes",
        "57- to 51-hole circle",
    }
)
for _wall, _mm in WEBS_MM.items():
    if _wall in SHORT_WEBS:
        if not 0.0 < _mm < WALL_FLOOR_MM:
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

# --- Model globals: name -> value (mm); the build sets each and drives from it --
GLOBALS: dict[str, float] = {
    "PlateDia": PLATE_DIA,
    "BoreDia": BORE_DIA,
    "PlateThick": THICKNESS,
    "IndexHoleDia": INDEX_HOLE_DIA,
    **{f"Ring{n}Pcd": RING_PCDS[n] for n in RING_COUNTS},
    "MountPcd": MOUNT_PCD,
    "MountHoleDia": MOUNT_HOLE_DIA,
    "CskDia": CSK_DIA,
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
CSK_CALLOUT = (
    f"<HOLE-SINK><MOD-DIAM>{inch_text(CSK_DIA, CSK_PLACES)} X {CSK_ANGLE:.0f}\u00b0"
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
# (rule 7); the countersink prints with its symbol (rule 26).  A location
# carries its value and band only (rule 7), so the mounting holes' bolt
# circle states its pattern as the index circles do, and the mate rides the
# holes' size callout (fan-out round 5).  The bottom hole stands on the
# centre mark's vertical line, so the pattern's clocking is the drawn 90
# degrees, as for the index circles.
WEB_CALLOUT = f"WEB {inch_text(WEB_MIN_PRINTED * INCH, 2)} MIN"
CALLOUTS_BELOW: dict[str, str] = {
    PRINTED_HOLE: f"REAM THRU\nSLIDING FIT ON {HEAD} INDEX PIN\n{WEB_CALLOUT}",
    "BoreDia": f"BORE THRU\nLOCATING FIT ON\n{HEAD} PLATE HUB",
    "MountHoleDia": f"DRILL THRU\n{CSK_CALLOUT}\nFOR {HEAD}\nPLATE SCREWS",
}
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
