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

Holes (owner ruling 2026-11-06, Main, option B of the PR2 two-hole review):
two #29 tap drills THRU the 1 in height on the mid-width row (Y 0), at the
KP08's 42 mm bolt spacing about the screw axis, X 13.925 and 55.925 mm. Each
hole is tapped #8-32 UNC from BOTH faces: from the bottom (bar) face for a
#8-32 x 3/4 SHCS up through base bar 1 (the jig's common screw), from the top
(KP08) face for a #8-32 x 5/8 SHCS down through the KP08's Ø5 hole (the
owner-approved second length). A hand tap carries about 3/4 in of thread on a
shank wider than the tap drill, so it cannot thread the whole height; and the
two threads are cut from opposite faces, so they are not in phase. Each
thread therefore has a printed depth window (``BAR_THREAD_WINDOW``,
``KP08_THREAD_WINDOW``): deep enough that its own screw reaches no further
than its full thread, shallow enough that the thread and its bottoming tap's
lead (``TAP_LEAD``, 2 pitches) stop short of where the other screw reaches.
Each face is started with the plug tap and finished with the bottoming tap,
neither tap's point past its face's ``*_TAP_TIP_MAX``. The KP08 screw reaches
deepest on the thinnest KP08 foot; the receipt check's least foot
(``KP08_FOOT_THICK_MIN``) is set by both threads, and every window is taken
on it; its thickest (``KP08_FOOT_THICK_MAX``) keeps the 5/8's full thread at
1.5 D. The two screw tips stay ``SCREW_TIP_GAP_MIN`` apart at the worst case;
the common 3/4 from the top as well would collide (``COMMON_SCREW_TIP_GAP``).
This replaces the six-hole layout (four #8 bar taps and two #6-32 KP08 taps)
and the #6-32 button heads.

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

Rule 18 belongs to the screws' lengths (leadscrew spec): each screw's
worst-case full-thread engagement is 1.5 D and more
(``leadscrew.BAR_SCREW_FULL_THREAD_MIN``, ``leadscrew.KP08_SCREW_FULL_THREAD_MIN``);
this part proves each thread window holds its screw's whole reach in full
thread (``SCREW_REACH_MAX``).
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

# --- Holes: two tap drills THRU on the mid-width row, #8-32 from both faces ----
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
# Every tap callout's lengths print .XXX (.136, .436, .491); the sheet sets
# every length the native callout carries.
TAP_CALLOUT_PLACES = 3

# The two threads' depths from their own faces. Each face is started with
# the shop's 8-32 plug tap and finished with its bottoming tap
# (``taps-unc-hand``: 3-5 and 1-2 chamfered threads). The bottoming tap
# leaves full thread to the printed depth and partial thread at most
# TAP_LEAD past it; neither tap's point goes deeper than its face's
# TAP_TIP_MAX (marked on both taps), so the plug tap's longer lead cuts no
# deeper than the bottoming tap's.
TAP_LEAD = 2.0 * _PITCH  # 1.588
BAR_THREAD_DEPTH = round(0.491 * 25.4, 9)  # .491 from the bottom face
KP08_THREAD_DEPTH = round(0.436 * 25.4, 9)  # .436 from the top face
BAR_THREAD_LIMITS = _limits(BAR_THREAD_DEPTH, TAP_CALLOUT_PLACES)
KP08_THREAD_LIMITS = _limits(KP08_THREAD_DEPTH, TAP_CALLOUT_PLACES)


def _inch_floor(value: float, places: int) -> float:
    """``value`` mm rounded down to ``places`` inch places, as mm."""
    scale = 10**places
    return math.floor(value / 25.4 * scale + 1e-9) / scale * 25.4


def _inch_ceil(value: float, places: int) -> float:
    """``value`` mm rounded up to ``places`` inch places, as mm."""
    scale = 10**places
    return math.ceil(value / 25.4 * scale - 1e-9) / scale * 25.4


# The deepest each tap's point may go from its own face: its thread's
# deepest full depth plus the bottoming tap's lead, rounded down to .001.
BAR_TAP_TIP_MAX = _inch_floor(BAR_THREAD_LIMITS[1] + TAP_LEAD, TAP_CALLOUT_PLACES)  # .558
KP08_TAP_TIP_MAX = _inch_floor(
    KP08_THREAD_LIMITS[1] + TAP_LEAD, TAP_CALLOUT_PLACES
)  # .503
for _label, (_low, _high), _tip in (
    ("bar", BAR_THREAD_LIMITS, BAR_TAP_TIP_MAX),
    ("KP08", KP08_THREAD_LIMITS, KP08_TAP_TIP_MAX),
):
    if not _low + TAP_LEAD <= _tip <= _high + TAP_LEAD:
        raise AssertionError(
            f"the end bracket's {_label} bottoming tap cannot leave full thread "
            f"{_low:.3f} deep with its point at most {_tip:.3f}"
        )
# The deepest the 3/4 bar screw reaches past the bottom face, at TL-20's
# printed bands.
BAR_REACH_MAX = leadscrew.BAR_SCREW_ENGAGEMENT_RANGE[1]  # 12.294
# The 5/8 KP08 screw (ASME B18.3: no plus length tolerance) reaches past the
# top face its length less the KP08 foot (UNVERIFIED 5.0, #2184), deeper
# on a thinner foot. Its tip must stop in the KP08 thread's full thread
# (that thread's least depth) AND short of the bar-face thread and its
# tap's lead (their deepest, on the thinnest stock). The tighter of the two
# sets the least foot the receipt check accepts, rounded up to the .001 it
# prints; the KP08 screw's reach is taken on that least foot.
KP08_SCREW_LENGTH_MM = float(Fraction(leadscrew.KP08_SCREW_LENGTH)) * 25.4  # 5/8
KP08_FOOT_THICK_MIN = _inch_ceil(
    KP08_SCREW_LENGTH_MM
    - min(KP08_THREAD_LIMITS[0], THICK_MIN - BAR_THREAD_LIMITS[1] - TAP_LEAD),
    TAP_CALLOUT_PLACES,
)  # .196
if not 0.0 < KP08_FOOT_THICK_MIN < leadscrew.KP08_FOOT_THICK:
    raise AssertionError("the KP08 screw's 5/8 needs a foot thicker than nominal")
KP08_REACH_MAX = KP08_SCREW_LENGTH_MM - KP08_FOOT_THICK_MIN  # 10.897
# The thickest foot the same receipt check accepts: a thicker foot takes the
# 5/8 screw's engagement off one for one, and its worst-case full thread in
# the KP08 thread (leadscrew.full_thread_min: B18.3 short length, tip's
# incomplete pitches, mouth break) must stay rule 18's 1.5 D (owner's full-
# thread criterion), rounded down to the .001 it prints. The foot itself
# stays UNVERIFIED (#2184): this bounds the check, it is no measurement.
KP08_FOOT_THICK_MAX = _inch_floor(
    leadscrew.full_thread_min(leadscrew.KP08_SCREW_LENGTH, 0.0, SCREW)
    - 1.5 * THREAD_MAJOR_MM[SCREW],
    TAP_CALLOUT_PLACES,
)  # .292
if not (
    KP08_FOOT_THICK_MIN < leadscrew.KP08_FOOT_THICK < KP08_FOOT_THICK_MAX
    and leadscrew.full_thread_min(
        leadscrew.KP08_SCREW_LENGTH, KP08_FOOT_THICK_MAX, SCREW
    )
    >= 1.5 * THREAD_MAJOR_MM[SCREW]
):
    raise AssertionError("the KP08 foot's receipt band leaves the 5/8 under 1.5 D")
SCREW_REACH_MAX = {"bar": BAR_REACH_MAX, "kp08": KP08_REACH_MAX}
# Each window: its own screw's reach in full thread (low); the thread and
# its tap's lead short of the other screw's reach (high), on the thinnest
# stock the supplier band allows.
BAR_THREAD_WINDOW = (BAR_REACH_MAX, THICK_MIN - KP08_REACH_MAX - TAP_LEAD)
KP08_THREAD_WINDOW = (KP08_REACH_MAX, THICK_MIN - BAR_REACH_MAX - TAP_LEAD)
for _label, (_low, _high), (_lo, _hi), _tip, _other in (
    ("bar", BAR_THREAD_LIMITS, BAR_THREAD_WINDOW, BAR_TAP_TIP_MAX, KP08_REACH_MAX),
    ("KP08", KP08_THREAD_LIMITS, KP08_THREAD_WINDOW, KP08_TAP_TIP_MAX, BAR_REACH_MAX),
):
    if not _lo <= _low <= _high <= _hi:
        raise AssertionError(
            f"the end bracket's {_label} thread {_low:.3f}..{_high:.3f} leaves "
            f"its window {_lo:.3f}..{_hi:.3f}"
        )
    if _tip > THICK_MIN - _other:
        raise AssertionError(
            f"the end bracket's {_label} tap point {_tip:.3f} meets the other screw"
        )
# Rule 18 in full thread: 1.5 D at least in both threads.
for _label, _depth in (("bar", BAR_THREAD_LIMITS[0]), ("KP08", KP08_THREAD_LIMITS[0])):
    if _depth < 1.5 * THREAD_MAJOR_MM[SCREW]:
        raise AssertionError(f"end bracket {_label} full thread under 1.5 D")
# The two tips stay apart, on the thinnest stock and the least foot.
SCREW_TIP_GAP_MIN = THICK_MIN - BAR_REACH_MAX - KP08_REACH_MAX  # 1.90
if SCREW_TIP_GAP_MIN <= 0.0:
    raise AssertionError("the end bracket's two screw tips collide")
# Why both depths print three places: each window is the screw-tip gap less
# one tap lead wide, 0.317 (.0125). The title block's .XX band spans .020,
# so no two-place depth fits either window; .XXX's .010 does, .0025 to
# spare (machinist review 0c3ed35988 asked what the three places are for).
DEPTH_WINDOW_WIDTH = SCREW_TIP_GAP_MIN - TAP_LEAD  # 0.317
for _window in (BAR_THREAD_WINDOW, KP08_THREAD_WINDOW):
    if abs(_window[1] - _window[0] - DEPTH_WINDOW_WIDTH) > 1e-9:
        raise AssertionError("the end bracket's depth windows differ from the gap")
_TWO_PLACE_SPAN = sum(
    abs(d) for d in printed_deviations(BAR_THREAD_DEPTH, 2, unit=UNIT)
)  # .020
_THREE_PLACE_SPAN = sum(
    abs(d) for d in printed_deviations(BAR_THREAD_DEPTH, TAP_CALLOUT_PLACES, unit=UNIT)
)  # .010
if not _THREE_PLACE_SPAN <= DEPTH_WINDOW_WIDTH < _TWO_PLACE_SPAN:
    raise AssertionError("the end bracket's depth windows need fewer places")
# Why the KP08 screw is the 5/8 and not the jig's common 3/4: from the top
# the 3/4 would reach 14.07 past the face on the least foot and meet the bar
# screw's tip.
COMMON_SCREW_TIP_GAP = (
    THICK_MIN
    - BAR_REACH_MAX
    - (float(Fraction(leadscrew.BAR_SCREW_LENGTH)) * 25.4 - KP08_FOOT_THICK_MIN)
)
if COMMON_SCREW_TIP_GAP >= 0.0:
    raise AssertionError("the common 3/4 now fits the KP08 too: use it there")

# The native model: the bar-face thread is a BLIND tapped wizard from the
# bottom, its tap drill stopping where the KP08-face thread ends; the
# KP08-face thread is a THRU ALL tapped wizard from the top, whose drill
# completes the through hole (each wizard on an intact face). The bar side's
# blind drill depth is a modelling step only: the shop drills THRU from one
# face (the sheet's one Ø.136 THRU ALL).
BAR_TAP_DRILL_DEPTH = round(BRACKET_THICK - KP08_THREAD_DEPTH, 9)  # 14.326
BAR_TAP_SPEC = HoleSpec(
    "tapped",
    SCREW,
    end="blind",
    depth_mm=BAR_TAP_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": BAR_THREAD_DEPTH},
)
KP08_TAP_SPEC = HoleSpec("tapped", SCREW, end="through_all")
TAP_DRILL = blind_cut_dia_mm(KP08_TAP_SPEC)  # #29, .136
if blind_cut_dia_mm(BAR_TAP_SPEC) != TAP_DRILL:
    raise AssertionError("both TL-28 threads share one tap drill")
if not BAR_THREAD_DEPTH < BAR_TAP_DRILL_DEPTH < BRACKET_THICK:
    raise AssertionError("the bar-face tap drill must stop inside the bracket")
# Each face is the wizard's placement face: (model outward normal, its Z).
BAR_TAP_FACE = ((0.0, 0.0, -1.0), 0.0)  # the bottom, on TL-20's top
KP08_TAP_FACE = ((0.0, 0.0, 1.0), BRACKET_THICK)  # the top, under the KP08 foot
# The plan looks at the top face: its native callout prints the drill THRU
# and the KP08-face thread. Section A-A, cut along the hole row, draws both
# faces' cosmetic threads and prints the bar-face thread's depth from the
# bottom face: a hidden reference sketch's dimension (BAR_THREAD_REFERENCE),
# which the build proves equals the bar-face wizard's thread depth. Its two
# points stand on the outer hole's thread major diameter on the outer-end
# side (BAR_THREAD_WITNESS_X), where the section draws that thread's side
# line: the witness leaves the drawn thread end (machinist review
# 0c3ed35988: on the axis it started in the plain bore).
BAR_THREAD_REFERENCE = "BarThreadReference"
BAR_THREAD_DEPTH_DIMENSION = "BarThreadDepth"
THREAD_MAJOR = THREAD_MAJOR_MM[SCREW]  # the cosmetic thread's major diameter
BAR_THREAD_WITNESS_X = HOLE_X[-1] + THREAD_MAJOR / 2.0

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
# The stations print from the KP08-face wizard (the plan's visible holes);
# the bar-face wizard shares them (its placements are driven, unmarked).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BracketProfile": {"BracketLength", "BracketWidth"},
    # The stock thickness: a reference sketch, not the extrusion's depth,
    # whose import has no drawing-view attachment (farm r1).
    "BracketThickReference": {"BracketThick"},
    "KP08Taps": {"KP08Tap1X", "KP08Tap2X"},
    "HoleRowReference": {"HoleRowY"},
    # The bar-face thread's depth: section A-A's (BAR_THREAD_REFERENCE).
    BAR_THREAD_REFERENCE: {BAR_THREAD_DEPTH_DIMENSION},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BracketProfile": {"BracketLength": LENGTH_PLACES, "BracketWidth": STOCK_PLACES},
    "BracketThickReference": {"BracketThick": STOCK_PLACES},
    "KP08Taps": dict.fromkeys(DRAWING_DIMENSIONS["KP08Taps"], HOLE_PLACES),
    "HoleRowReference": {"HoleRowY": ROW_PLACES},
    BAR_THREAD_REFERENCE: {BAR_THREAD_DEPTH_DIMENSION: TAP_CALLOUT_PLACES},
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
for _depth in (BAR_THREAD_DEPTH, KP08_THREAD_DEPTH):
    if abs(_depth / 25.4 - round(_depth / 25.4, TAP_CALLOUT_PLACES)) > 1e-9:
        raise AssertionError(f"end bracket thread depth {_depth} does not print as modelled")
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
    # Section A-A's thread depth: which thread, from which face, and what
    # both depths (this one and the plan's top depth) do. Machinist review
    # 0c3ed35988 read the .436/.491 three places as unexplained: each window
    # (BAR_/KP08_THREAD_WINDOW) is its own screw's deepest reach in full
    # thread (low) to its own tap lead short of the opposed screw's tip
    # (high), SCREW_TIP_GAP_MIN - TAP_LEAD = .0125 wide, under a .XX band's
    # .020 (DEPTH_WINDOW_WIDTH; the test proves no .XX depth fits). Farm 26bb
    # (2 of 3) asked for .44/.49 on the untapped stock left between the two
    # threads; that gap is not what bounds them. At .48 the 3/4 bar screw's
    # tip (BAR_REACH_MAX, 12.294) passes the full thread into the bottoming
    # tap's lead; at .50 that lead runs past the 5/8 KP08 screw's tip on the
    # least foot; at .45 the top lead does the same to the bar screw's tip.
    # The sheet states the thread's scope, its mates by catalogue length (the
    # leadscrew spec's purchased 3/4 bar and 5/8 KP08 SHCS; farm 26bb: "the
    # sheet shows no screw length or other mate") and both limits' function,
    # in at most DEPTH_NOTE_ROWS_MAX rows (machinist review a966: a seven-row
    # note overruled its rule 7). Lower: the full thread holds the 3/4 bar
    # screw's tip. Upper (machinist review 957 read .49 MIN as enough once the
    # rows named only the mates): the bottoming tap's lead must clear the
    # 5/8 KP08 screw's tip. The depth itself prints only through its native
    # dimension.
    BAR_THREAD_DEPTH_DIMENSION: (
        "FULL THREAD FROM BOTTOM\n"
        f"HOLDS {leadscrew.BAR_SCREW_LENGTH} BAR SCREW TIP\n"
        "TAP LEAD CLEARS THE\n"
        f"{leadscrew.KP08_SCREW_LENGTH} KP08 TIP, EACH HOLE"
    ),
}
DEPTH_NOTE_ROWS_MAX = 4
if CALLOUTS_BELOW[BAR_THREAD_DEPTH_DIMENSION].count("\n") + 1 > DEPTH_NOTE_ROWS_MAX:
    raise AssertionError("the end bracket's depth note runs over its rows")
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
