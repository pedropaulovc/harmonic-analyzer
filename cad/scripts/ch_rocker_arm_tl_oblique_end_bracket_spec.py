r"""Pure-data contract for the oblique-trammel jig's end bracket (MHA-CH-06-TL-28).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). Two
identical brackets carry the leadscrew feed's two KP08 pillow blocks (bought,
shop inventory ``fixtures.trammel-kp08-blocks``) on base bar 1's top
(MHA-CH-06-TL-20). Each lifts its block's base off the bar by the plate's
thickness and stands wholly on the bar, its outer end flush with the bar's
column-side edge (the user's 2026-10-17 ruling A′: the bar widened to 1/2 x 6
so the bracket no longer cantilevers past it). The layout (axis, stations
and every bought dimension) belongs to
``ch_rocker_arm_tl_vn_oblique_leadscrew_spec``, imported as ``leadscrew``; this
module never retypes one of its numbers.

Material and stock: 6061-T6 aluminium flat bar 1/2 x 3/4 in (12.70 x 19.05),
sawn and faced to ``leadscrew.BRACKET_LENGTH`` 68.9. Width and thickness stay
as bought and print "STOCK".

Frame (SolidWorks model, and the ``PRECHIPS_SOLIDS`` frame; the leadscrew
spec's): origin on the bottom face at the inner end (toward the rail),
mid-width; +X outward (machine +lateral), +Y along the screw, +Z up. Envelope
X 0 .. 68.9, Y -9.525 .. 9.525, Z 0 .. 12.7.

Holes, all six on the mid-width row (Y 0), tapped THRU from the top face:

- Two M4x0.7 metric tapped holes at X 14 and 56: the KP08's two base screws
  at its 42 bolt spacing, about the screw axis. They are metric because the
  bought block is (Main's ruling); every shop-chosen thread stays ANSI inch.
- Four #8-32 UNC tapped holes at X 7.5, 24, 46 and 62.5: the base-bar
  screws, #8-32 SHCS fitted up through the bar's counterbored clearance holes
  (``leadscrew.BASE_BAR_HOLE_SPEC``) into these taps; two pairs symmetric
  about the screw axis (ruling A′), the outer pair's half-span set by the
  rule-17 window in the leadscrew spec. A counterbore from the top would
  leave no wall to the M4s, so the screws come from underneath (JigAssembly
  ruling).

Bands. Both patterns are fixed-fastener fits, so every station and the row
print at three places (title block ±0.13): each hole then sits in a 0.13
half-side square, ``POSITION_RADIUS`` 0.184 from nominal. An M4 (major Ø4.0)
floats 0.25 in the KP08's Ø4.5 holes (``leadscrew.KP08_HOLE_DIA``,
UNVERIFIED), leaving ``KP08_PATTERN_ALLOWANCE`` 0.066 for the block's own hole
positions. A #8 (major Ø4.166) floats 0.406 in the bar's Ø4.978 normal-fit
clearance, leaving ``BAR_PATTERN_ALLOWANCE`` 0.222 for the bar's pattern. At
two places (±0.51) the corner would be 0.72 out and neither pattern would fit.
Each station is a DRO absolute from the faced inner end (rule 10) and names
its own mate (rule 4); the row is 9.525 from the -Y side face, a hidden
reference-sketch dimension (base bar ``RailRowReference``), and names both.
Pair spacings (18, 42) with the edge locations at two places would loosen the
8 between the patterns to ±1.02; that offset sets the screw line over the
bar's holes, and the KP08 and bar-screw floats are spent on the patterns
above, so the edge stations keep three places and carry the mates.

Rule 17 (walls, 2.0 target, 1.5 floor) at worst case: every station and the
row at ±0.13, the length at its one-place ±0.8, the stock width at its
two-place ±0.51, each thread at its major diameter: #8 at 7.5 to the inner
end 5.29; #8 at 7.5 to M4 at 14 2.16; M4 at 14 to #8 at 24 5.66; #8 at 24 to
#8 at 46 17.57; #8 at 46 to M4 at 56 5.66; M4 at 56 to #8 at 62.5 2.16; #8 at
62.5 to the outer end 3.39 (the length's one place suffices); the row to the
-Y side 7.31, to the +Y side 6.80. No rule-20 shortfall.

Rule 18 belongs to the screws' lengths (leadscrew spec): the #8 engagement is
``leadscrew.BAR_SCREW_ENGAGEMENT``; this part only proves its through thread
offers 1.5 D for both screws.
"""

from __future__ import annotations

import math
from typing import Any

import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
from _hole_spec import CLEARANCE_MM, THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

# Title-block DRILLED HOLES: plus allowance, zero minus (_printed_tolerance).
DRILLED_BAND = (drilled_oversize_mm(), 0.0)

# --- Identity ---------------------------------------------------------------
NUMBER = leadscrew.END_BRACKET_NUMBER
QUANTITY = leadscrew.END_BRACKET_QUANTITY
KP08_ID = leadscrew.KP08_ID

# --- Bracket: 6061-T6 1/2 x 3/4 in flat, sawn and faced to length ------------
BRACKET_LENGTH = round(leadscrew.BRACKET_LENGTH, 9)  # 68.9
BRACKET_WIDTH = round(leadscrew.BRACKET_WIDTH, 9)  # 19.05 stock
BRACKET_THICK = round(leadscrew.BRACKET_THICK, 9)  # 12.7 stock
HALF_WIDTH = round(BRACKET_WIDTH / 2.0, 9)
LENGTH_PLACES = 1
STOCK_PLACES = 2  # 19.05 and 12.70 print exactly at two places
STOCK_DIMENSIONS = {"BracketWidth", "BracketThick"}

# --- Holes: six taps THRU on the mid-width row ---------------------------------
HOLE_PLACES = 3  # fixed-fastener patterns (module docstring)
HOLE_ROW_Y = HALF_WIDTH  # 9.525 from the -Y side face to the row
BAR_SCREW = leadscrew.BAR_SCREW  # "#8-32"
BAR_TAP_X: tuple[float, ...] = tuple(round(x, 9) for x in leadscrew.BRACKET_BAR_HOLES_X)
BAR_TAP_SPEC = HoleSpec("tapped", BAR_SCREW, end="through_all")
BAR_TAP_DRILL = blind_cut_dia_mm(BAR_TAP_SPEC)  # 3.454
# The KP08's M4 base screws: the coarse M4x0.7 metric tap.
if leadscrew.KP08_SCREW != "M4":
    raise AssertionError("the KP08 tap size no longer matches its screw")
KP08_THREAD = "M4x0.7"
KP08_TAP_X: tuple[float, ...] = tuple(
    round(x, 9) for x in leadscrew.BRACKET_KP08_HOLES_X
)
KP08_TAP_SPEC = HoleSpec("tapped_metric", KP08_THREAD, end="through_all")
KP08_TAP_DRILL = blind_cut_dia_mm(KP08_TAP_SPEC)  # 3.3

_BAND = printed_band_mm(HOLE_PLACES)  # ±0.13
_LENGTH_BAND = printed_band_mm(LENGTH_PLACES)  # ±0.8
_STOCK_BAND = printed_band_mm(STOCK_PLACES)  # ±0.51
_BAR_R = THREAD_MAJOR_MM[BAR_SCREW] / 2.0
_KP08_R = THREAD_MAJOR_MM[KP08_THREAD] / 2.0

# --- The two fixed-fastener fits ------------------------------------------------
POSITION_RADIUS = math.hypot(_BAND, _BAND)  # 0.184
KP08_SCREW_FLOAT = (leadscrew.KP08_HOLE_DIA - THREAD_MAJOR_MM[KP08_THREAD]) / 2.0
KP08_PATTERN_ALLOWANCE = KP08_SCREW_FLOAT - POSITION_RADIUS  # 0.066
BAR_HOLE_DIA = CLEARANCE_MM[
    (leadscrew.BASE_BAR_HOLE_SPEC.size, leadscrew.BASE_BAR_HOLE_SPEC.fit)
]  # 4.978
BAR_SCREW_FLOAT = (BAR_HOLE_DIA - THREAD_MAJOR_MM[BAR_SCREW]) / 2.0
BAR_PATTERN_ALLOWANCE = BAR_SCREW_FLOAT - POSITION_RADIUS  # 0.222
if not (KP08_PATTERN_ALLOWANCE > 0.0 and BAR_PATTERN_ALLOWANCE > 0.0):
    raise AssertionError("an end bracket hole pattern does not fit its mate")
_TWO_PLACE_RADIUS = math.hypot(printed_band_mm(2), printed_band_mm(2))
if not _TWO_PLACE_RADIUS > max(KP08_SCREW_FLOAT, BAR_SCREW_FLOAT):
    raise AssertionError("the end bracket stations no longer need three places")

# Every tight band names its mate (drawing-guidelines rule 4): each station
# and the row, which serves both patterns.
KP08_MATE_CALLOUT = "MATCHES KP08 BLOCK HOLES"
BAR_MATE_CALLOUT = "MATCHES MHA-CH-06-TL-20"
ROW_CALLOUT = "\n".join(("HOLES IN LINE FOR KP08", "AND MHA-CH-06-TL-20"))

# --- The KP08 base lands on the bracket ------------------------------------------
_KP08_CENTRE_X = (KP08_TAP_X[0] + KP08_TAP_X[1]) / 2.0
if not (
    0.0 < _KP08_CENTRE_X - leadscrew.KP08_LENGTH / 2.0
    and _KP08_CENTRE_X + leadscrew.KP08_LENGTH / 2.0 < BRACKET_LENGTH
    and leadscrew.KP08_WIDTH < BRACKET_WIDTH
):
    raise AssertionError("the KP08 base overhangs its end bracket")
if abs(KP08_TAP_X[1] - KP08_TAP_X[0] - leadscrew.KP08_BOLT_SPACING) > 1e-9:
    raise AssertionError("the KP08 taps are off the block's bolt spacing")

# --- Rule 18: the through thread offers 1.5 D to both screws --------------------
for _thread in (BAR_SCREW, KP08_THREAD):
    if BRACKET_THICK < 1.5 * THREAD_MAJOR_MM[_thread]:
        raise AssertionError(f"end bracket {_thread} thread under 1.5 D")

# --- Rule 17: walls at the printed worst case ----------------------------------------
WALL_TARGET = 2.0
WALL_FLOOR = 1.5
# Every tap to its row neighbours and the end taps to the ends, in row order
# (ruling A′'s six taps interleave #8 and M4: 7.5/14/24/46/56/62.5).
_TAPS = sorted(
    [(x, "#8", _BAR_R) for x in BAR_TAP_X] + [(x, "M4", _KP08_R) for x in KP08_TAP_X]
)
_FIRST, _LAST = _TAPS[0], _TAPS[-1]
WALLS_MM: dict[str, float] = {
    f"{_FIRST[1]} tap at {_FIRST[0]:g} to inner end": _FIRST[0] - _BAND - _FIRST[2],
    **{
        f"{kind} tap at {x:g} to {next_kind} tap at {next_x:g}": (next_x - _BAND)
        - (x + _BAND)
        - r
        - next_r
        for (x, kind, r), (next_x, next_kind, next_r) in zip(_TAPS, _TAPS[1:])
    },
    f"{_LAST[1]} tap at {_LAST[0]:g} to outer end": (BRACKET_LENGTH - _LENGTH_BAND)
    - (_LAST[0] + _BAND)
    - _LAST[2],
    "row to -Y side": HOLE_ROW_Y - _BAND - _BAR_R,
    "row to +Y side": (BRACKET_WIDTH - _STOCK_BAND) - (HOLE_ROW_Y + _BAND) - _BAR_R,
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
    "Bracket": {"BracketThick"},
    "BarTaps": {f"BarTap{k}X" for k in range(1, len(BAR_TAP_X) + 1)},
    "KP08Taps": {"KP08Tap1X", "KP08Tap2X"},
    "HoleRowReference": {"HoleRowY"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BracketProfile": {"BracketLength": LENGTH_PLACES, "BracketWidth": STOCK_PLACES},
    "Bracket": {"BracketThick": STOCK_PLACES},
    "BarTaps": dict.fromkeys(DRAWING_DIMENSIONS["BarTaps"], HOLE_PLACES),
    "KP08Taps": {"KP08Tap1X": HOLE_PLACES, "KP08Tap2X": HOLE_PLACES},
    "HoleRowReference": {"HoleRowY": HOLE_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked end bracket dimension needs authored places")
for _name, _value in (
    ("BracketLength", BRACKET_LENGTH),
    ("BracketWidth", BRACKET_WIDTH),
    ("BracketThick", BRACKET_THICK),
    *((f"BarTap{k}X", x) for k, x in enumerate(BAR_TAP_X, start=1)),
    ("KP08Tap1X", KP08_TAP_X[0]),
    ("KP08Tap2X", KP08_TAP_X[1]),
    ("HoleRowY", HOLE_ROW_Y),
):
    if abs(_value - round(_value, DRAWING_PRECISION_BY_NAME[_name])) > 1e-9:
        raise AssertionError(f"end bracket {_name} {_value} does not print as modelled")

# Width and thickness are the bar as bought; every station names its mate,
# and the row names what it buys.
CALLOUTS_BELOW = dict.fromkeys(sorted(STOCK_DIMENSIONS), "STOCK") | {
    "KP08Tap1X": KP08_MATE_CALLOUT,
    "KP08Tap2X": KP08_MATE_CALLOUT,
    **dict.fromkeys(sorted(DRAWING_DIMENSIONS["BarTaps"]), BAR_MATE_CALLOUT),
    "HoleRowY": ROW_CALLOUT,
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
            f"{NUMBER}, 6061-T6 1/2 x 3/4 flat; carries a {KP08_ID} block on "
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
