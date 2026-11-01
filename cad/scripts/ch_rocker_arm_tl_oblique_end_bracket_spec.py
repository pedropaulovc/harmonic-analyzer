r"""Pure-data contract for the oblique-trammel jig's end bracket (MHA-CH-06-TL-28).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). Two
identical brackets carry the leadscrew feed's two KP08 pillow blocks (bought,
shop inventory ``fixtures.trammel-kp08-blocks``) on base bar 1's top
(MHA-CH-06-TL-20). Each lifts its block's base off the bar by the plate's
thickness and stands wholly on the bar, its outer end flush with the bar's
column-side edge (the user's 2026-10-17 ruling A′: the bar widened, now 5.50
wide, so the bracket no longer cantilevers past it). The layout (axis, stations
and every bought dimension) belongs to
``ch_rocker_arm_tl_vn_oblique_leadscrew_spec``, imported as ``leadscrew``; this
module never retypes one of its numbers.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``). Lengths
stay physical millimetres, each fabricated nominal the exact millimetres of
its printed inch value; the KP08's 42 mm bolt span is a metric-only vendor
line (owner ruling 4, 2026-11-01, option B), so its two tap stations print
exact millimetres, labelled mm, with the millimetre title block's
three-place band stated on each (``13.925 ±0.13 mm``, ``55.925 ±0.13 mm``;
``METRIC_DIMENSIONS``), and their walls and float read those limits.

Material and stock: aluminium flat bar 1/2 x 1 in standing on edge, e.g.
6061-T6 (the owned OnlineMetals 1165 6061-T6511 bar): 1/2 along the screw,
1 high, sawn and faced to ``leadscrew.BRACKET_LENGTH`` 2.71. Width and
height stay as bought: each prints its stock fraction as a reference over
"STOCK", the supplier's band governing (``WIDTH_STOCK_BAND``). Only the taps
need the metal, so the title block names the flat-bar family, not a grade
(rule 2). The KP08 foot (13 mm wide, UNVERIFIED) overhangs the 1/2 top by
0.15 mm a side (``KP08_FOOT_OVERHANG``).

Frame (SolidWorks model, and the ``PRECHIPS_SOLIDS`` frame; the leadscrew
spec's): origin on the bottom face at the inner end (toward the rail),
mid-width; +X outward (machine +lateral), +Y along the screw, +Z up. Envelope
X 0 .. 2.71, Y -.25 .. .25, Z 0 .. 1.00.

Holes, all six on the mid-width row (Y 0), tapped THRU from the top face:

- Two #6-32 UNC tapped holes at X 13.925 and 55.925 mm: the KP08's two base
  screws at its 42 mm bolt spacing, about the screw axis. The bought block's
  holes are plain, so the screw is shop-chosen US-customary (fastener policy).
- Four #8-32 UNC tapped holes at X .285, .942, 1.808 and 2.465: the base-bar
  screws, #8-32 SHCS fitted up through the bar's counterbored clearance holes
  (``leadscrew.BASE_BAR_HOLE_SPEC``) into these taps; two pairs symmetric
  about the screw axis (ruling A′), the outer pair's half-span set by the
  rule-17 window in the leadscrew spec. A counterbore from the top would
  leave no wall to the #6-32 taps, so the screws come from underneath (JigAssembly
  ruling).

Bands. Both patterns are fixed-fastener fits, so every station and the row
print at three places: the bar taps and the row at the title block's ±.005,
the KP08 taps at ±0.13 mm. Each hole then sits in its band's half-side
square, ``POSITION_RADIUS`` from
nominal. A #6 (major Ø.138) floats in the KP08's Ø4.5 mm holes
(``leadscrew.KP08_HOLE_DIA``, UNVERIFIED), leaving ``KP08_PATTERN_ALLOWANCE``
for the block's own hole positions. A #8 (major Ø.164) floats in the bar's
Ø.196 normal-fit clearance, leaving ``BAR_PATTERN_ALLOWANCE`` for the bar's
pattern. At two places (±.01) this part's and the bar's position radii would
overrun the #8's float. Each station is a DRO absolute from the faced inner
end (rule 10) and names its own mate (rule 4); the row is .250 from the -Y
side face, a hidden reference-sketch dimension (base bar ``RailRowReference``),
and names both.

Rule 17 (walls, .080 target, .060 floor) at worst case: every station and the
row at its printed limits, the length at its .XX band, the stock width at its
supplier band, each thread at its major diameter (``WALLS_MM``). No rule-20
shortfall.

Rule 18 belongs to the screws' lengths (leadscrew spec): the #8 engagement is
``leadscrew.BAR_SCREW_ENGAGEMENT``; this part only proves its through thread
offers 1.5 D for both screws.
"""

from __future__ import annotations

import math
from typing import Any

import _config
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
from _hole_spec import CLEARANCE_MM, THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_band_mm, printed_deviations

UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-oblique-end-bracket",
    _config.parts("ch-rocker-arm-tl-oblique-end-bracket"),
)
# Title-block DRILLED HOLES: plus allowance, zero minus (_printed_tolerance).
DRILLED_BAND = (drilled_oversize_mm(unit=UNIT), 0.0)


def _limits(value: float, places: int) -> tuple[float, float]:
    """The printed value's (low, high) limits, mm: the title-block band about
    ``value`` rounded to ``places`` in the sheet's unit."""
    low, high = printed_deviations(value, places, unit=UNIT)
    return value + low, value + high


# --- Identity ---------------------------------------------------------------
NUMBER = leadscrew.END_BRACKET_NUMBER
QUANTITY = leadscrew.END_BRACKET_QUANTITY
KP08_ID = leadscrew.KP08_ID

# --- Bracket: 6061-T6511 1/2 x 1 in flat on edge, sawn and faced to length ---
BRACKET_LENGTH = round(leadscrew.BRACKET_LENGTH, 9)  # 2.71
BRACKET_WIDTH = round(leadscrew.BRACKET_WIDTH, 9)  # 1/2 stock
BRACKET_THICK = round(leadscrew.BRACKET_THICK, 9)  # 1 stock
HALF_WIDTH = round(BRACKET_WIDTH / 2.0, 9)
LENGTH_PLACES = 2
# Supplier bands, OnlineMetals 6061-T6511 extruded rectangle bar
# (https://www.onlinemetals.com/en/aluminum-tolerances): .500-.749 ±.009,
# 1.000-1.499 ±.012. Both sizes print as stock references.
WIDTH_STOCK_BAND = 0.2286  # .009
THICK_STOCK_BAND = 0.3048  # .012
STOCK_PLACES = 2
STOCK_FRACTION_DENOMINATORS = {"BracketWidth": 2, "BracketThick": 1}  # (1/2), (1)
STOCK_DIMENSIONS = {"BracketWidth", "BracketThick"}

# --- Holes: six taps THRU on the mid-width row ---------------------------------
HOLE_PLACES = 3  # fixed-fastener patterns (module docstring)
HOLE_ROW_Y = HALF_WIDTH  # .250 from the -Y side face to the row
BAR_SCREW = leadscrew.BAR_SCREW  # "#8-32"
BAR_TAP_X: tuple[float, ...] = tuple(round(x, 9) for x in leadscrew.BRACKET_BAR_HOLES_X)
BAR_TAP_SPEC = HoleSpec("tapped", BAR_SCREW, end="through_all")
BAR_TAP_DRILL = blind_cut_dia_mm(BAR_TAP_SPEC)  # #29, .136
# The KP08's base screws: #6-32 UNC through the block's plain holes.
KP08_THREAD = leadscrew.KP08_SCREW  # "#6-32"
KP08_TAP_X: tuple[float, ...] = tuple(
    round(x, 9) for x in leadscrew.BRACKET_KP08_HOLES_X
)
# The KP08 stations print exact millimetres (owner ruling 4) with the
# millimetre title block's three-place band.
METRIC_UNIT = "mm"
KP08_TAP_PLACES = 3
KP08_TAP_BAND = printed_band_mm(KP08_TAP_PLACES, unit=METRIC_UNIT)  # 0.13
KP08_TAP_SPEC = HoleSpec("tapped", KP08_THREAD, end="through_all")
KP08_TAP_DRILL = blind_cut_dia_mm(KP08_TAP_SPEC)  # #36, .1065
# Every tap callout's lengths print .XXX (.136, .107); a THRU tap's callout
# carries no hw-tapdrldia (farm r1), so the sheet sets every length it has.
TAP_CALLOUT_PLACES = 3

_LENGTH_LOW = _limits(BRACKET_LENGTH, LENGTH_PLACES)[0]
_BAR_R = THREAD_MAJOR_MM[BAR_SCREW] / 2.0
_KP08_R = THREAD_MAJOR_MM[KP08_THREAD] / 2.0


def _station_limits(value: float) -> tuple[float, float]:
    """A tap station's printed (low, high) limits, mm: a KP08 tap's exact
    millimetres with its own band, any other at .XXX."""
    if value in KP08_TAP_X:
        low, high = printed_deviations(
            value, KP08_TAP_PLACES, (-KP08_TAP_BAND, KP08_TAP_BAND), unit=METRIC_UNIT
        )
        return value + low, value + high
    return _limits(value, HOLE_PLACES)


def _deviation(value: float) -> float:
    """A station's widest excursion from its model value."""
    low, high = _station_limits(value)
    return max(value - low, high - value)


_ROW_DEVIATION = _deviation(HOLE_ROW_Y)

# --- The two fixed-fastener fits ------------------------------------------------
POSITION_RADIUS = max(
    math.hypot(_deviation(x), _ROW_DEVIATION) for x in (*BAR_TAP_X, *KP08_TAP_X)
)
KP08_SCREW_FLOAT = (leadscrew.KP08_HOLE_DIA - THREAD_MAJOR_MM[KP08_THREAD]) / 2.0
KP08_PATTERN_ALLOWANCE = KP08_SCREW_FLOAT - POSITION_RADIUS
BAR_HOLE_DIA = CLEARANCE_MM[
    (leadscrew.BASE_BAR_HOLE_SPEC.size, leadscrew.BASE_BAR_HOLE_SPEC.fit)
]  # .196
BAR_SCREW_FLOAT = (BAR_HOLE_DIA - THREAD_MAJOR_MM[BAR_SCREW]) / 2.0
BAR_PATTERN_ALLOWANCE = BAR_SCREW_FLOAT - POSITION_RADIUS
if not (KP08_PATTERN_ALLOWANCE > 0.0 and BAR_PATTERN_ALLOWANCE > 0.0):
    raise AssertionError("an end bracket hole pattern does not fit its mate")
# At two places this part's and TL-20's position radii together overrun the
# #8's float: the pair needs three places.
_TWO_PLACE_RADIUS = math.hypot(
    printed_band_mm(2, unit=UNIT), printed_band_mm(2, unit=UNIT)
)
if not 2.0 * _TWO_PLACE_RADIUS > BAR_SCREW_FLOAT:
    raise AssertionError("the end bracket stations no longer need three places")

# Every tight band names its mate (drawing-guidelines rule 4): each station
# and the row, which serves both patterns.
KP08_MATE_CALLOUT = "MATCHES KP08 BLOCK HOLES"
BAR_MATE_CALLOUT = "MATCHES MHA-CH-06-TL-20"
# One line naming both mates: the row's witnesses leave room for two text rows
# only (the value and this).
ROW_CALLOUT = "KP08 + MHA-CH-06-TL-20"

# --- The KP08 base lands on the bracket ------------------------------------------
# Its 13 mm foot (UNVERIFIED) overhangs the 1/2 stock 0.15 mm a side (contract).
KP08_FOOT_OVERHANG = max(0.0, (leadscrew.KP08_WIDTH - BRACKET_WIDTH) / 2.0)
_KP08_CENTRE_X = (KP08_TAP_X[0] + KP08_TAP_X[1]) / 2.0
if not (
    0.0 < _KP08_CENTRE_X - leadscrew.KP08_LENGTH / 2.0
    and _KP08_CENTRE_X + leadscrew.KP08_LENGTH / 2.0 < BRACKET_LENGTH
    and KP08_FOOT_OVERHANG <= 0.15 + 1e-9
):
    raise AssertionError("the KP08 base overhangs its end bracket")
if abs(KP08_TAP_X[1] - KP08_TAP_X[0] - leadscrew.KP08_BOLT_SPACING) > 1e-9:
    raise AssertionError("the KP08 taps are off the block's bolt spacing")

# --- Rule 18: the through thread offers 1.5 D to both screws --------------------
for _thread in (BAR_SCREW, KP08_THREAD):
    if BRACKET_THICK - THICK_STOCK_BAND < 1.5 * THREAD_MAJOR_MM[_thread]:
        raise AssertionError(f"end bracket {_thread} thread under 1.5 D")

# --- Rule 17: walls at the printed worst case ----------------------------------------
WALL_TARGET = WALL_TARGET_MM
WALL_FLOOR = WALL_FLOOR_MM
# Every tap to its row neighbours and the end taps to the ends, in row order
# (ruling A′'s six taps interleave #8 and #6).
_TAPS = sorted(
    [(x, "#8", _BAR_R) for x in BAR_TAP_X] + [(x, "#6", _KP08_R) for x in KP08_TAP_X]
)
_FIRST, _LAST = _TAPS[0], _TAPS[-1]


def _inch(value: float) -> str:
    return f"{value / 25.4:.3f}".lstrip("0")


WALLS_MM: dict[str, float] = {
    f"{_FIRST[1]} tap at {_inch(_FIRST[0])} to inner end": _station_limits(_FIRST[0])[0]
    - _FIRST[2],
    **{
        f"{kind} tap at {_inch(x)} to {next_kind} tap at {_inch(next_x)}": _station_limits(
            next_x
        )[0]
        - _station_limits(x)[1]
        - r
        - next_r
        for (x, kind, r), (next_x, next_kind, next_r) in zip(_TAPS, _TAPS[1:])
    },
    f"{_LAST[1]} tap at {_inch(_LAST[0])} to outer end": _LENGTH_LOW
    - _station_limits(_LAST[0])[1]
    - _LAST[2],
    "row to -Y side": HOLE_ROW_Y - _ROW_DEVIATION - _BAR_R,
    "row to +Y side": (BRACKET_WIDTH - WIDTH_STOCK_BAND)
    - (HOLE_ROW_Y + _ROW_DEVIATION)
    - _BAR_R,
}
for _wall, _mm in WALLS_MM.items():
    if _mm < WALL_TARGET:
        raise AssertionError(
            f"end bracket {_wall} wall {_mm:.3f} under drawing-guidelines.md rule 17"
        )
RULE_20_SHORTFALLS: tuple[str, ...] = ()

# --- Drawing -------------------------------------------------------------------------
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BracketProfile": {"BracketLength", "BracketWidth"},
    # The stock thickness: a reference sketch, not the extrusion's depth,
    # whose import has no drawing-view attachment (farm r1).
    "BracketThickReference": {"BracketThick"},
    "BarTaps": {f"BarTap{k}X" for k in range(1, len(BAR_TAP_X) + 1)},
    "KP08Taps": {"KP08Tap1X", "KP08Tap2X"},
    "HoleRowReference": {"HoleRowY"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BracketProfile": {"BracketLength": LENGTH_PLACES, "BracketWidth": STOCK_PLACES},
    "BracketThickReference": {"BracketThick": STOCK_PLACES},
    "BarTaps": dict.fromkeys(DRAWING_DIMENSIONS["BarTaps"], HOLE_PLACES),
    "KP08Taps": dict.fromkeys(DRAWING_DIMENSIONS["KP08Taps"], KP08_TAP_PLACES),
    "HoleRowReference": {"HoleRowY": HOLE_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked end bracket dimension needs authored places")
# Every fabricated value prints as modelled at its inch places; the KP08
# stations (the vendor span's) print exact millimetres (module docstring).
for _name, _value in (
    ("BracketLength", BRACKET_LENGTH),
    *((f"BarTap{k}X", x) for k, x in enumerate(BAR_TAP_X, start=1)),
    ("HoleRowY", HOLE_ROW_Y),
):
    _places = DRAWING_PRECISION_BY_NAME[_name]
    if abs(_value / 25.4 - round(_value / 25.4, _places)) > 1e-9:
        raise AssertionError(f"end bracket {_name} {_value} does not print as modelled")
# The metric vendor line's stations (owner ruling 4): (feature, dimension) ->
# (millimetre places, symmetric band mm).
METRIC_DIMENSIONS: dict[tuple[str, str], tuple[int, float]] = {
    ("KP08Taps", name): (KP08_TAP_PLACES, KP08_TAP_BAND)
    for name in sorted(DRAWING_DIMENSIONS["KP08Taps"])
}
for _x in KP08_TAP_X:
    if abs(_x - round(_x, KP08_TAP_PLACES)) > 1e-9:
        raise AssertionError(f"end bracket KP08 tap {_x} does not print exact in mm")

# Width and thickness are the bar as bought (their references carry STOCK);
# every station names its mate, and the row names what it buys.
CALLOUTS_BELOW = {
    "KP08Tap1X": KP08_MATE_CALLOUT,
    "KP08Tap2X": KP08_MATE_CALLOUT,
    **dict.fromkeys(sorted(DRAWING_DIMENSIONS["BarTaps"]), BAR_MATE_CALLOUT),
    "HoleRowY": ROW_CALLOUT,
}
# Rule 1 (units): an as-bought fraction is a REF with the supplier's
# tolerance (machinist review, final head), the band on its own row so the
# width's text stays as narrow as before (the bar's end runs beside it).
STOCK_CALLOUTS = {
    name: "STOCK\n±" + f"{band / 25.4:.3f}".lstrip("0")
    for name, band in (
        ("BracketWidth", WIDTH_STOCK_BAND),
        ("BracketThick", THICK_STOCK_BAND),
    )
}
SURFACE_FINISHES = ()
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"


_MEASURED = {
    "status": "measured",
    "by": "placeholder (realistic, remeasure: #1413)",
    "date": "2026-10-18",
    "instrument": (
        "digital calipers, height gauge and indicator; physical component sizes/fit only"
    ),
}


def _hole(name: str, x: float, dia: float) -> dict[str, Any]:
    return {
        "name": name,
        "shape": "cylinder",
        "at_mm": [x, 0.0, 0.0],
        "axis": [0.0, 0.0, 1.0],
        "dia_mm": dia,
        "length_mm": BRACKET_THICK,
        "void": True,
        "cuts": ["end bracket"],
        "measured": dict(_MEASURED),
    }


# The bracket as made, in the model frame above; each tap is its tap drill.
PRECHIPS_SOLIDS: list[dict[str, Any]] = [
    {
        "name": "end bracket",
        "shape": "box",
        "at_mm": [0.0, -HALF_WIDTH, 0.0],
        "size_mm": [BRACKET_LENGTH, BRACKET_WIDTH, BRACKET_THICK],
        "note": (
            f"{NUMBER}, 6061-T6511 1/2 x 1 flat on edge; carries a {KP08_ID} block on "
            "base bar MHA-CH-06-TL-20 by 4 x #8-32 SHCS"
        ),
        "measured": dict(_MEASURED),
    },
    *(
        _hole(f"bar tap {index}", x, BAR_TAP_DRILL)
        for index, x in enumerate(BAR_TAP_X, start=1)
    ),
    *(
        _hole(f"KP08 tap {index}", x, KP08_TAP_DRILL)
        for index, x in enumerate(KP08_TAP_X, start=1)
    ),
]
