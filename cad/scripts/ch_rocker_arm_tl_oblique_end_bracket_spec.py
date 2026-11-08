r"""Pure-data contract for the oblique-trammel jig's end bracket (MHA-CH-06-TL-28).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). Two
identical brackets carry the leadscrew feed's two KP08 pillow blocks (bought,
shop inventory ``fixtures.trammel-kp08-blocks``) on base bar 1's top
(MHA-CH-06-TL-20, its ``Bar1`` configuration). Each lifts its block's base off
the bar by the plate's thickness and stands wholly on the bar, its outer end
flush with the bar's column-side edge (the user's 2026-10-17 ruling A′: the
bar widened, now 5.50 wide, so the bracket no longer cantilevers past it). The
layout (axis, stations and every bought dimension) belongs to
``ch_rocker_arm_tl_vn_oblique_leadscrew_spec``, imported as ``leadscrew``; this
module never retypes one of its numbers.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``). Lengths
stay physical millimetres, each fabricated nominal the exact millimetres of
its printed inch value; the KP08's 42 mm bolt span is a metric-only vendor
line (owner ruling 4, 2026-11-01, option B), so the two hole stations print
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

Holes (owner ruling 2026-11-07, Main, A″): two #29 drills THRU at the
KP08's 42 mm span, X 13.925 and 55.925 mm. Both entries take #8-32 x 5/8
SHCS. Full thread is limited to .370–.496 from the bar face and .429–.555
from the KP08 face. Plug-start and bottoming-finish with the owned hand
taps. Neither screw may enter the opposed-phase cut, including its lead;
unused middle thread may be double-cut. The KP08 foot receipt band remains
.196–.292, UNVERIFIED (#2184).

Bands. Both patterns are fixed-fastener fits, so the stations print exact mm
at three places (±0.13 mm) and the row at the title block's ±.005. Each hole
then sits in its band's half-side square, ``POSITION_RADIUS`` from nominal.
A #8 (major Ø.164) floats in the KP08's Ø5 mm holes (``leadscrew.KP08_HOLE_DIA``,
UNVERIFIED, #2184), leaving ``KP08_PATTERN_ALLOWANCE`` for the block's own hole
positions, and in the bar's Ø.189 (#12) clearance. Each two-screw joint
may turn as well as slide before it is tightened, so a pair fits when its
float takes half the worst difference of the two patterns' centre spacings
(``BAR_PAIR_MISFIT`` against ``BAR_SCREW_FLOAT``; ``BAR_PATTERN_ALLOWANCE``
is what is left). Each station is a DRO
absolute from the faced inner end (rule 10) and names both mates (rule 4);
the row is .250 from the -Y side face, a hidden reference-sketch dimension
(base bar ``RailRowReference``), and names both.

Rule 17 (walls, .080 target, .060 floor) at worst case: every station and the
row at its printed limits, the length at its .XX band, the stock width at its
supplier band, each thread at its major diameter (``WALLS_MM``). No rule-20
shortfall.

Each screw retains 1.5D of full thread at the worst grip. The engagement
helper's 1.5-pitch loss is NOT guaranteed thread-free tip clearance.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

import _config
import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
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
THICK_MIN = BRACKET_THICK - THICK_STOCK_BAND  # 25.095

# --- Holes: #29 THRU, independently limited threads from both faces ----------
HOLE_ROW_Y = HALF_WIDTH  # .250 from the -Y side face to the row
ROW_PLACES = 3  # a fixed-fastener pattern's row (module docstring)
SCREW = leadscrew.BAR_SCREW  # "#8-32"
if leadscrew.KP08_SCREW != SCREW:
    raise AssertionError("both TL-28 entries take the one #8-32 thread")
HOLE_X: tuple[float, ...] = tuple(round(x, 9) for x in leadscrew.BRACKET_HOLES_X)
# The stations are the KP08's vendor span (owner ruling 4): exact millimetres
# with the millimetre title block's three-place band.
METRIC_UNIT = "mm"
HOLE_PLACES = 3
HOLE_BAND = printed_band_mm(HOLE_PLACES, unit=METRIC_UNIT)  # 0.13
_PITCH = 25.4 / float(SCREW.rsplit("-", 1)[1])  # 0.794
# The tap callout's drill prints .XXX (.136); the sheet sets every length
# the native callout carries.
TAP_CALLOUT_PLACES = 3

THICK_MAX = BRACKET_THICK + THICK_STOCK_BAND
BOTTOMING_LEAD_LIMITS = (_PITCH, 2.0 * _PITCH)
HAND_TAP_FLUTE_LENGTH = 0.75 * 25.4  # catalogue-valued, not measured
BAR_THREAD_LIMITS = (0.370 * 25.4, 0.496 * 25.4)
KP08_THREAD_LIMITS = (0.429 * 25.4, 0.555 * 25.4)
BAR_THREAD_DEPTH = 0.433 * 25.4
KP08_THREAD_DEPTH = 0.492 * 25.4
BAR_TIP_MARK_LIMITS = (0.433 * 25.4, 0.527 * 25.4)
KP08_TIP_MARK_LIMITS = (0.492 * 25.4, 0.586 * 25.4)


def _inch_floor(value: float, places: int) -> float:
    """``value`` mm rounded down to ``places`` inch places, as mm."""
    scale = 10**places
    return math.floor(value / 25.4 * scale + 1e-9) / scale * 25.4


# Whole physical reach: zero guaranteed thread-free tip credit.
BAR_REACH_MAX = leadscrew.BAR_SCREW_ENGAGEMENT_RANGE[1]  # 9.398
# The 5/8 (ASME B18.3: no plus length tolerance) reaches past the top face
# its length less the KP08 foot (UNVERIFIED 5.0, #2184), deepest on the
# thinnest foot the receipt check (jig step 7) accepts. That band is the
# vendor-acceptance band and is not widened here: KP08_FOOT_THICK_MIN .196,
# just under the nominal 5.0.
FOOT_PLACES = 3  # the receipt check prints .001
KP08_SCREW_LENGTH_MM = float(Fraction(leadscrew.KP08_SCREW_LENGTH)) * 25.4  # 5/8
KP08_FOOT_THICK_MIN = round(0.196 * 25.4, 9)  # 4.978
if not 0.0 < KP08_FOOT_THICK_MIN < leadscrew.KP08_FOOT_THICK:
    raise AssertionError("the KP08 receipt band must hold the nominal foot")
KP08_REACH_MAX = KP08_SCREW_LENGTH_MM - KP08_FOOT_THICK_MIN  # 10.897
# The thickest foot the same receipt check accepts: a thicker foot takes the
# 5/8 screw's engagement off one for one, and its worst-case full thread
# (leadscrew.full_thread_min: B18.3 short length, tip's incomplete pitches,
# mouth break) must stay rule 18's 1.5 D (owner's full-thread criterion),
# rounded down to the .001 it prints. The foot itself stays UNVERIFIED
# (#2184): this bounds the check, it is no measurement.
KP08_FOOT_THICK_MAX = _inch_floor(
    leadscrew.full_thread_min(leadscrew.KP08_SCREW_LENGTH, 0.0, SCREW)
    - 1.5 * THREAD_MAJOR_MM[SCREW],
    FOOT_PLACES,
)  # .292
if not (
    KP08_FOOT_THICK_MIN < leadscrew.KP08_FOOT_THICK < KP08_FOOT_THICK_MAX
    and leadscrew.full_thread_min(
        leadscrew.KP08_SCREW_LENGTH, KP08_FOOT_THICK_MAX, SCREW
    )
    >= 1.5 * THREAD_MAJOR_MM[SCREW]
):
    raise AssertionError("the KP08 foot's receipt band leaves the 5/8 under 1.5 D")
# Rule 18 for the bar screw: its worst-case full thread (leadscrew spec).
if leadscrew.BAR_SCREW_FULL_THREAD_MIN < 1.5 * THREAD_MAJOR_MM[SCREW]:
    raise AssertionError("the 5/8 bar screw's full thread in TL-28 is under 1.5 D")
# Physical tip separation does not by itself prove phase-seam clearance.
SCREW_TIP_GAP_MIN = THICK_MIN - BAR_REACH_MAX - KP08_REACH_MAX  # 4.8006
if SCREW_TIP_GAP_MIN <= 0.0:
    raise AssertionError("the end bracket's two screw tips collide")
KP08_REACH_MIN = (
    KP08_SCREW_LENGTH_MM - leadscrew.SHCS_LENGTH_TOL_MM - KP08_FOOT_THICK_MAX
)
KP08_FULL_THREAD_AT_RECEIPT_MAX = leadscrew.full_thread_min(
    leadscrew.KP08_SCREW_LENGTH, KP08_FOOT_THICK_MAX, SCREW
)
BAR_OPPOSED_CUT_CLEARANCE_MIN = (
    THICK_MIN - BAR_REACH_MAX - KP08_THREAD_LIMITS[1] - BOTTOMING_LEAD_LIMITS[1]
)
KP08_OPPOSED_CUT_CLEARANCE_MIN = (
    THICK_MIN - KP08_REACH_MAX - BAR_THREAD_LIMITS[1] - BOTTOMING_LEAD_LIMITS[1]
)
if (
    BAR_THREAD_LIMITS[0] + 1e-9 < BAR_REACH_MAX
    or KP08_THREAD_LIMITS[0] + 1e-9 < KP08_REACH_MAX
    or min(BAR_OPPOSED_CUT_CLEARANCE_MIN, KP08_OPPOSED_CUT_CLEARANCE_MIN) <= 0.0
):
    raise AssertionError("a TL-28 screw enters the opposed-phase cutting envelope")
for _full, _tip in (
    (BAR_THREAD_LIMITS, BAR_TIP_MARK_LIMITS),
    (KP08_THREAD_LIMITS, KP08_TIP_MARK_LIMITS),
):
    if (
        _tip[0] - BOTTOMING_LEAD_LIMITS[1] < _full[0]
        or _tip[1] - BOTTOMING_LEAD_LIMITS[0] > _full[1]
        or _tip[1] >= HAND_TAP_FLUTE_LENGTH
    ):
        raise AssertionError("bottoming tip marks do not hold full-thread limits")
# .8128 mm at prescribed marks, versus .0127 at drawing Fmax plus 2p.
TIP_MARK_SEAM_CLEARANCE_MIN = min(
    THICK_MIN - BAR_REACH_MAX - KP08_TIP_MARK_LIMITS[1],
    THICK_MIN - KP08_REACH_MAX - BAR_TIP_MARK_LIMITS[1],
)
if TIP_MARK_SEAM_CLEARANCE_MIN <= 0.0:
    raise AssertionError("a prescribed tap-tip mark enters the opposite screw")

# Construction-only blind precursor: independent of top thread depth.
BAR_TAP_DRILL_DEPTH = 0.625 * 25.4
BAR_TAP_SPEC = HoleSpec(
    "tapped", SCREW, end="blind", depth_mm=BAR_TAP_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": BAR_THREAD_DEPTH},
)
KP08_TAP_SPEC = HoleSpec("tapped", SCREW, end="through_all")
TAP_DRILL = blind_cut_dia_mm(BAR_TAP_SPEC)
THREAD_MAJOR = THREAD_MAJOR_MM[SCREW]
if not BAR_THREAD_DEPTH <= BAR_TAP_DRILL_DEPTH < BRACKET_THICK - TAP_DRILL / 2.0 * 0.60086:
    raise AssertionError("the precursor drill must leave the KP08 face intact")
BAR_TAP_FACE = ((0.0, 0.0, -1.0), 0.0)
KP08_TAP_FACE = ((0.0, 0.0, 1.0), BRACKET_THICK)

_LENGTH_LOW = _limits(BRACKET_LENGTH, LENGTH_PLACES)[0]
_R = THREAD_MAJOR_MM[SCREW] / 2.0


def _station_limits(value: float) -> tuple[float, float]:
    """A hole station's printed (low, high) limits, mm: exact millimetres
    with the KP08 span's own band."""
    low, high = printed_deviations(
        value, HOLE_PLACES, (-HOLE_BAND, HOLE_BAND), unit=METRIC_UNIT
    )
    return value + low, value + high


def _deviation(value: float) -> float:
    """A station's widest excursion from its model value."""
    low, high = _station_limits(value)
    return max(value - low, high - value)


_ROW_LIMITS = _limits(HOLE_ROW_Y, ROW_PLACES)
_ROW_DEVIATION = max(HOLE_ROW_Y - _ROW_LIMITS[0], _ROW_LIMITS[1] - HOLE_ROW_Y)

# --- The two fixed-fastener fits ------------------------------------------------
POSITION_RADIUS = max(math.hypot(_deviation(x), _ROW_DEVIATION) for x in HOLE_X)
KP08_SCREW_FLOAT = (leadscrew.KP08_HOLE_DIA - THREAD_MAJOR_MM[SCREW]) / 2.0  # 0.417
KP08_PATTERN_ALLOWANCE = KP08_SCREW_FLOAT - POSITION_RADIUS
BAR_HOLE_DIA = base_bar.BRACKET_HOLE_DIA  # .189, a #12 drill
BAR_SCREW_FLOAT = (BAR_HOLE_DIA - THREAD_MAJOR_MM[SCREW]) / 2.0  # 0.318 at the least hole
# The TL-20 pair against this part's pair: two holes fix only their centre
# distance, so with the joint free to slide and turn each screw is off its
# hole by half the difference of the two spacings. This part's spacing moves
# with both stations (along) and the row (across, second order).
_SPAN = abs(HOLE_X[1] - HOLE_X[0])
_ALONG = sum(_deviation(x) for x in HOLE_X)
BRACKET_PAIR_SPACING_ERROR = max(
    _ALONG, math.hypot(_SPAN + _ALONG, 2.0 * _ROW_DEVIATION) - _SPAN
)
BAR_PAIR_MISFIT = (
    BRACKET_PAIR_SPACING_ERROR
    + base_bar.bracket_pair_spacing_error(leadscrew.BASE_BAR_HOLES)
) / 2.0  # 0.261
BAR_PATTERN_ALLOWANCE = BAR_SCREW_FLOAT - BAR_PAIR_MISFIT
if not (KP08_PATTERN_ALLOWANCE > 0.0 and BAR_PATTERN_ALLOWANCE > 0.0):
    raise AssertionError("an end bracket hole pattern does not fit its mate")
# At two places this part's and TL-20's position radii together overrun the
# #8's float: the row needs three places.
_TWO_PLACE_RADIUS = math.hypot(
    printed_band_mm(2, unit=UNIT), printed_band_mm(2, unit=UNIT)
)
if not 2.0 * _TWO_PLACE_RADIUS > BAR_SCREW_FLOAT:
    raise AssertionError("the end bracket row no longer needs three places")

# Every tight band names its mates (drawing-guidelines rule 4): each station
# and the row serve both patterns.
MATE_CALLOUT = "KP08 + MHA-CH-06-TL-20"
ROW_CALLOUT = MATE_CALLOUT

# --- The KP08 base lands on the bracket ------------------------------------------
# Its 13 mm foot (UNVERIFIED) overhangs the 1/2 stock 0.15 mm a side (contract).
KP08_FOOT_OVERHANG = max(0.0, (leadscrew.KP08_WIDTH - BRACKET_WIDTH) / 2.0)
_KP08_CENTRE_X = (HOLE_X[0] + HOLE_X[1]) / 2.0
if not (
    0.0 < _KP08_CENTRE_X - leadscrew.KP08_LENGTH / 2.0
    and _KP08_CENTRE_X + leadscrew.KP08_LENGTH / 2.0 < BRACKET_LENGTH
    and KP08_FOOT_OVERHANG <= 0.15 + 1e-9
):
    raise AssertionError("the KP08 base overhangs its end bracket")
if abs(HOLE_X[1] - HOLE_X[0] - leadscrew.KP08_BOLT_SPACING) > 1e-9:
    raise AssertionError("the end bracket holes are off the block's bolt spacing")

# --- Rule 17: walls at the printed worst case ----------------------------------------
WALL_TARGET = WALL_TARGET_MM
WALL_FLOOR = WALL_FLOOR_MM


def _inch(value: float) -> str:
    return f"{value / 25.4:.3f}".lstrip("0")


WALLS_MM: dict[str, float] = {
    f"hole at {_inch(HOLE_X[0])} to inner end": _station_limits(HOLE_X[0])[0] - _R,
    f"hole at {_inch(HOLE_X[0])} to hole at {_inch(HOLE_X[1])}": _station_limits(
        HOLE_X[1]
    )[0]
    - _station_limits(HOLE_X[0])[1]
    - 2.0 * _R,
    f"hole at {_inch(HOLE_X[1])} to outer end": _LENGTH_LOW
    - _station_limits(HOLE_X[1])[1]
    - _R,
    "row to -Y side": HOLE_ROW_Y - _ROW_DEVIATION - _R,
    "row to +Y side": (BRACKET_WIDTH - WIDTH_STOCK_BAND)
    - (HOLE_ROW_Y + _ROW_DEVIATION)
    - _R,
}
for _wall, _mm in WALLS_MM.items():
    if _mm < WALL_TARGET:
        raise AssertionError(
            f"end bracket {_wall} wall {_mm:.3f} under drawing-guidelines.md rule 17"
        )
RULE_20_SHORTFALLS: tuple[str, ...] = ()

# --- Drawing -------------------------------------------------------------------------
# Native section witnesses own the two full-thread LIMIT dimensions.
BAR_THREAD_REFERENCE = "BarThreadReference"
BAR_THREAD_DEPTH_DIMENSION = "BarThreadDepth"
BAR_THREAD_WITNESS_X = HOLE_X[-1] + THREAD_MAJOR / 2.0
KP08_THREAD_REFERENCE = "KP08ThreadReference"
KP08_THREAD_DEPTH_DIMENSION = "KP08ThreadDepth"
KP08_THREAD_WITNESS_X = HOLE_X[0] - THREAD_MAJOR / 2.0
# Stations print from the final top wizard's visible holes.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BracketProfile": {"BracketLength", "BracketWidth"},
    # The stock thickness: a reference sketch, not the extrusion's depth,
    # whose import has no drawing-view attachment (farm r1).
    "BracketThickReference": {"BracketThick"},
    "KP08Taps": {"KP08Tap1X", "KP08Tap2X"},
    "HoleRowReference": {"HoleRowY"},
    BAR_THREAD_REFERENCE: {BAR_THREAD_DEPTH_DIMENSION},
    KP08_THREAD_REFERENCE: {KP08_THREAD_DEPTH_DIMENSION},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BracketProfile": {"BracketLength": LENGTH_PLACES, "BracketWidth": STOCK_PLACES},
    "BracketThickReference": {"BracketThick": STOCK_PLACES},
    "KP08Taps": dict.fromkeys(DRAWING_DIMENSIONS["KP08Taps"], HOLE_PLACES),
    "HoleRowReference": {"HoleRowY": ROW_PLACES},
    BAR_THREAD_REFERENCE: {BAR_THREAD_DEPTH_DIMENSION: TAP_CALLOUT_PLACES},
    KP08_THREAD_REFERENCE: {KP08_THREAD_DEPTH_DIMENSION: TAP_CALLOUT_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked end bracket dimension needs authored places")
# Every fabricated value prints as modelled at its inch places; the stations
# (the vendor span's) print exact millimetres (module docstring).
for _name, _value in (
    ("BracketLength", BRACKET_LENGTH),
    ("HoleRowY", HOLE_ROW_Y),
):
    _places = DRAWING_PRECISION_BY_NAME[_name]
    if abs(_value / 25.4 - round(_value / 25.4, _places)) > 1e-9:
        raise AssertionError(f"end bracket {_name} {_value} does not print as modelled")
# The metric vendor line's stations (owner ruling 4): (feature, dimension) ->
# (millimetre places, symmetric band mm).
METRIC_DIMENSIONS: dict[tuple[str, str], tuple[int, float]] = {
    ("KP08Taps", name): (HOLE_PLACES, HOLE_BAND)
    for name in sorted(DRAWING_DIMENSIONS["KP08Taps"])
}
for _x in HOLE_X:
    if abs(_x - round(_x, HOLE_PLACES)) > 1e-9:
        raise AssertionError(f"end bracket hole {_x} does not print exact in mm")

# Width and thickness are the bar as bought (their references carry STOCK);
# every station names its mates, and the row the same.
CALLOUTS_BELOW = {
    "KP08Tap1X": MATE_CALLOUT,
    "KP08Tap2X": MATE_CALLOUT,
    "HoleRowY": ROW_CALLOUT,
    BAR_THREAD_DEPTH_DIMENSION: "BOTTOM FULL THREAD\nBOTH HOLES",
    KP08_THREAD_DEPTH_DIMENSION: "TOP FULL THREAD\nBOTH HOLES",
}
# drawing-guidelines.md (units): an as-bought fraction is an untoleranced REF;
# the supplier's catalogue tolerance governs.
STOCK_CALLOUTS = {"BracketWidth": "STOCK", "BracketThick": "STOCK"}
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


# The bracket as made, in the model frame above; each hole is its tap drill.
PRECHIPS_SOLIDS: list[dict[str, Any]] = [
    {
        "name": "end bracket",
        "shape": "box",
        "at_mm": [0.0, -HALF_WIDTH, 0.0],
        "size_mm": [BRACKET_LENGTH, BRACKET_WIDTH, BRACKET_THICK],
        "note": (
            f"{NUMBER}, 6061-T6511 1/2 x 1 flat on edge; carries a {KP08_ID} block on "
            "base bar MHA-CH-06-TL-20 by 2 x #8-32 SHCS up from the bar and "
            "2 x #8-32 SHCS down through the block, in the same two holes"
        ),
        "measured": dict(_MEASURED),
    },
    *(_hole(f"tap {index}", x, TAP_DRILL) for index, x in enumerate(HOLE_X, start=1)),
]
