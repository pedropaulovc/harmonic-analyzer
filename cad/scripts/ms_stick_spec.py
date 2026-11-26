r"""Pure model/drawing contract for the graduated brass stick.

The 2026-10-10 user Option B ruling shifted the whole scale and numerals
1.00 mm left on the blank; the 2026-10-23 owner ruling lengthened the blank so
the last graduation keeps a rule-17 land to the end face at worst case.
Model dimensions own the manufacturing values, bands and decimal places.
The release supplies the engraved native/STEP model and its ruled-face/detail
drawings, not the generated build-input DXFs.
The 2026-10-23 owner ruling V-engraves the numerals: single-stroke sans
numerals cut as true 30-degree included V grooves (the model drafts every
stroke wall 15 degrees). Issue #2433: the graduations are the same 30-degree
V, so one engraving bit (shop-equipment tools.engravers-esao-30-0-1) cuts
every tick and numeral stroke; no tool in the shop cuts the former
square-bottom .016-.024 groove.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``). Lengths stay
physical millimetres, each the exact decimal of the inch value it prints (see
the trailing comments). Exempt (owner ruling, calibration geometry): the
configured 14.2 / 1.42 mm pitch prints rounded (.559, .0559) at its own
+/-.002, as the 56.5 mm scale zero (2.224 from the 0 end) did until #2434;
the minor pitch prints four places so ten printed minor pitches equal the
printed full pitch. Issue #2434 (delegated ruling 2026-11-17, option 2, for
the owner's review on #2144): the end face nearest the 10 bears on the
amplitude bar when the stick sets it, so it is the graduations' datum: the
station table locates every graduation from it at +/-.002 (rule 10, one
baseline) and sheet 1 shows the 10 tick's .135 from it as a reference, so the
length's .XX band never moves a station. Every row adds the 3.43 mm 10-tick
land (.13504) to the pitches and prints rounded: that rounding is the
delegated ruling's, not a new owner exemption; its precedent is the owner
exemption above for the scale's datum distance at the 0 end (2.224 for
56.5 mm, rounded at the stations' +/-.002).
This is
dimensioning only: the 2026-10-10 scale position is unchanged. The 7.95
length stays .XX; nothing prints .X. The
unprinted 0.24 stroke width at the face is the modelled near-sharp V and
stays (owner ruling). The ESAO 0.1 mm-tip bit at the .016 MIN numeral depth
cuts strokes about 0.32 wide: stroke width is unprinted, the extra 0.04 a side
stays inside the .02 numeral gap's +/-.01 band, and note 3 leaves the font to
the shop.
"""

from __future__ import annotations

import math
from pathlib import Path

import _config
from _package_units import drawing_unit
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import printed_band_mm
from ms_stick_geom import (
    DIVISION_COUNT as DIVISION_COUNT,
    DIVISION_SPACING,
    MINOR_PER_DIVISION as MINOR_PER_DIVISION,
    MINOR_SPACING,
    SCALE_SPAN,
)

# The sheet unit the registry row declares.
UNIT = drawing_unit("parts/ms-stick", _config.parts("ms-stick"))


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as decimal-inch print text: ``.080``, ``7.95``."""
    text = f"{value_mm / 25.4:.{places}f}"
    return text[1:] if text.startswith("0.") else text


BODY_LENGTH = 201.93  # 7.95
BODY_WIDTH = 8.001  # .315
# Owner ruling 2026-11-20 (#2441, option B): "B". The bar keeps the 1/8 C360
# flat's supplied thickness; only its two edges are milled to the 8 mm width.
BODY_THICKNESS = 3.175  # .125
# The bar beyond the last full tick: the model derives scale zero from the
# length, the configured span and this land, which the 7.95 length sets to
# 3.43 so scale zero stays put. Every station-table row adds it: the table
# runs from the end face nearest the 10, the graduations' datum (#2434).
SCALE_END_MARGIN = 3.43
# Exempt with the pitch (calibration): scale zero stays at 56.5 where the
# 2026-10-10 Option B ruling put it, so every graduation the assembly sets the
# stop and the bar stations against is unmoved.
SCALE_START_X = BODY_LENGTH - SCALE_SPAN - SCALE_END_MARGIN
# The face width .016 MIN (.024 MAX below) at the face of a 30-degree V
# .020 MIN deep: the drafted walls leave TICK_TIP_FLAT_MM at the root, as a
# 0.1 mm-tip bit plunged .023-.037 cuts it.
TICK_WIDTH = 0.4064  # .016 MIN
TICK_LENGTH = 3.048  # .12
MINOR_TICK_LENGTH = 1.778  # .07
HALF_TICK_LENGTH = 4.064  # .16
TICK_DEPTH = 0.508  # .020 MIN
TICK_OVERHANG = 1.0
_REFERENCES = Path(__file__).resolve().parents[1] / "references"
# One DXF per stroke layer (gen_ms_stick_numerals_dxf colours overlapping
# strokes apart; a drafted cut needs disjoint profiles). Literal names keep
# them in _buildgraph's data dependencies.
NUMERAL_LAYER_DXFS = (
    _REFERENCES / "ms-stick-numerals-1.dxf",
    _REFERENCES / "ms-stick-numerals-2.dxf",
    _REFERENCES / "ms-stick-numerals-3.dxf",
)
NUMERAL_HEIGHT_MM = 2.032  # .08
NUMERAL_GAP_MM = 0.508  # .02
NUMERAL_ROTATION_DEG = 90
# 2026-10-23 owner ruling: V-engrave the numerals with a 30-degree included
# V bit (the easiest hobby-mill route in brass). Single-stroke numerals, 0.24
# wide at the face (12% of the .08 height, legible and enamel-holding) and
# .016 MIN deep; the drafted walls leave only NUMERAL_TIP_FLAT_MM at the root.
ENGRAVING_V_INCLUDED_ANGLE_DEG = 30.0
NUMERAL_STROKE_WIDTH_MM = 0.24
NUMERAL_DEPTH = 0.4064  # .016 MIN
_V_HALF_SLOPE = math.tan(math.radians(ENGRAVING_V_INCLUDED_ANGLE_DEG / 2.0))
NUMERAL_TIP_FLAT_MM = NUMERAL_STROKE_WIDTH_MM - 2.0 * NUMERAL_DEPTH * _V_HALF_SLOPE
TICK_TIP_FLAT_MM = TICK_WIDTH - 2.0 * TICK_DEPTH * _V_HALF_SLOPE
if not TICK_TIP_FLAT_MM > 0.0:
    raise AssertionError(f"a {TICK_WIDTH} wide tick's V closes above its {TICK_DEPTH} depth")


def tick_v_volume_mm3(length_mm: float) -> float:
    """Volume (mm^3) one V tick removes: its TICK_WIDTH x ``length_mm`` face outline
    (the open end runs off the ruled edge) cut TICK_DEPTH deep with every wall
    drafted inward, the integral over depth z of (w - 2zs) * (L - zs)."""
    w, d, s = TICK_WIDTH, TICK_DEPTH, _V_HALF_SLOPE
    return w * length_mm * d - (w + 2.0 * length_mm) * s * d**2 / 2.0 + 2.0 * s**2 * d**3 / 3.0


# Every tick cut: eleven full ticks, the minor ticks of ten divisions and the
# half-division tick, which covers the minor tick it overcuts.
TICK_VOLUME_MM3 = (
    DIVISION_COUNT * tick_v_volume_mm3(TICK_LENGTH)
    + (DIVISION_COUNT - 1) * (MINOR_PER_DIVISION - 1) * tick_v_volume_mm3(MINOR_TICK_LENGTH)
    - tick_v_volume_mm3(MINOR_TICK_LENGTH)
    + tick_v_volume_mm3(HALF_TICK_LENGTH)
)
# Each stroke's ends are the V bit's footprint, a half-round inscribed in this
# many facets (gen_ms_stick_numerals_dxf), so joints reach the full depth.
NUMERAL_END_FACETS = 8
# The deepest V the fixed 0.24 face outline supports: past it the drafted end
# facets meet and the cut collapses. NumeralDepth is editable only below it.
NUMERAL_DEPTH_MAX_MM = (
    NUMERAL_STROKE_WIDTH_MM / 2.0 * math.cos(math.pi / (2 * NUMERAL_END_FACETS))
    / _V_HALF_SLOPE
)
if not 0.0 < NUMERAL_DEPTH < NUMERAL_DEPTH_MAX_MM:
    raise AssertionError(
        f"NUMERAL_DEPTH {NUMERAL_DEPTH} must stay below {NUMERAL_DEPTH_MAX_MM:.3f}, where the "
        f"{NUMERAL_STROKE_WIDTH_MM} face outline's drafted walls meet; widen the stroke to go deeper"
    )
NUMERALS_BBOX = (57.2112, 1.7864, 197.7888, 4.4450)
NUMERAL_VOLUME_MM3 = 2.7305
# Each stroke layer's V removal over the layers cut before it (layers overlap
# at stroke joints): gen_ms_stick_numerals_dxf.summary()["layer_volumes_mm3"].
NUMERAL_LAYER_VOLUMES_MM3 = (1.7391, 0.8896, 0.1018)
# Per layer, the least removal one stroke adds as its layer is cut (a dropped
# stroke removes at least this much less): summary()["min_stroke_volumes_mm3"].
NUMERAL_LAYER_MIN_STROKE_MM3 = (0.0189, 0.0138, 0.0133)
# The least removal one stroke adds to the finished part, every layer cut
# (later layers cover some of it): summary()["final_min_stroke_mm3"].
NUMERAL_FINAL_MIN_STROKE_MM3 = 0.0058

# Width and thickness give the sliding clearance in the .330 x .134 stop
# rebate at the title block's .XXX; graduation positions set the
# amplitude-bar stations through the READOUT table, at their own +/-.002:
# the drawing's station table holds every graduation to the end face nearest
# the 10 (the 10 tick's land and the pitches print as references). The
# overall length (.XX), tick lengths and
# numeral layout take the title block. Graduation width and both engraving
# depths name no mate, so
# they are single ".nnn MIN" limits (coordinator ruling 2026-10-23); the
# title block's finish calls for the enamel fill they hold. Their ceilings
# are stated facts, not bands (coordinator ruling 2026-10-23, on codjiflo's
# #1905 review): the graduation width stays .024 MAX, so neighbouring grooves
# on the .0559 minor pitch never merge and the last one stays on the shortest
# bar; both depths leave the stated .080 of stock under them.
BODY_LENGTH_TOLERANCE_MM = printed_band_mm(2, unit=UNIT)
BODY_FIT_TOLERANCE_MM = printed_band_mm(3, unit=UNIT)
GRADUATION_POSITION_TOLERANCE_MM = 0.0508  # +/-.002
GRADUATION_FLOOR_MIN_MM = WALL_TARGET_MM
GRADUATION_FLOOR_CALLOUT = f"STOCK UNDER GROOVE {inch_text(GRADUATION_FLOOR_MIN_MM, 3)} MIN"
NUMERAL_FLOOR_CALLOUT = f"STOCK UNDER {inch_text(GRADUATION_FLOOR_MIN_MM, 3)} MIN"
GRADUATION_WIDTH_MAX_MM = 0.6096  # .024
GRADUATION_WIDTH_CALLOUT = f"{inch_text(GRADUATION_WIDTH_MAX_MM, 3)} MAX"
# swTolType_e.swTolMIN prints the nominal plus MIN: the model value is the
# printed minimum. (lower, upper) deviations are the stored readback pair.
MIN_LIMIT_TOL_TYPE = 5
MIN_LIMIT_DEVIATIONS_MM = {
    "Tick0Width": (0.0, TICK_WIDTH),
    "TickDepth": (0.0, TICK_DEPTH),
    "NumeralDepth": (0.0, NUMERAL_DEPTH),
}

# Construction chords use the actual finished edge and actual groove/glyph
# extents. The 10-tick land and both pitch chords terminate at true groove
# centres, never at either side of the finite-width cut. ScaleStartX stays
# unprinted: the scale's datum is the end face nearest the 10 (#2434).
REFERENCE_DIMENSIONS = {
    "ScaleEndReference": ("Tick10FromEnd", (SCALE_START_X + SCALE_SPAN, BODY_WIDTH), (BODY_LENGTH, BODY_WIDTH)),
    "FullLengthReference": ("FullTickLength", (SCALE_START_X, BODY_WIDTH - TICK_LENGTH), (SCALE_START_X, BODY_WIDTH)),
    "MinorLengthReference": ("MinorTickLength", (SCALE_START_X + MINOR_SPACING, BODY_WIDTH - MINOR_TICK_LENGTH), (SCALE_START_X + MINOR_SPACING, BODY_WIDTH)),
    "HalfLengthReference": ("HalfTickLength", (SCALE_START_X + DIVISION_SPACING / 2.0, BODY_WIDTH - HALF_TICK_LENGTH), (SCALE_START_X + DIVISION_SPACING / 2.0, BODY_WIDTH)),
    "FullPitchReference": ("FullTickPitch", (SCALE_START_X, BODY_WIDTH), (SCALE_START_X + DIVISION_SPACING, BODY_WIDTH)),
    "MinorPitchReference": ("MinorTickPitch", (SCALE_START_X, BODY_WIDTH), (SCALE_START_X + MINOR_SPACING, BODY_WIDTH)),
    "NumeralHeightReference": ("NumeralHeight", (SCALE_START_X + TICK_WIDTH / 2.0 + NUMERAL_GAP_MM, BODY_WIDTH - TICK_LENGTH - NUMERAL_GAP_MM), (SCALE_START_X + TICK_WIDTH / 2.0 + NUMERAL_GAP_MM + NUMERAL_HEIGHT_MM, BODY_WIDTH - TICK_LENGTH - NUMERAL_GAP_MM)),
    "NumeralXGapReference": ("NumeralXGap", (SCALE_START_X + TICK_WIDTH / 2.0, BODY_WIDTH - TICK_LENGTH - NUMERAL_GAP_MM), (SCALE_START_X + TICK_WIDTH / 2.0 + NUMERAL_GAP_MM, BODY_WIDTH - TICK_LENGTH - NUMERAL_GAP_MM)),
    "NumeralYGapReference": ("NumeralYGap", (SCALE_START_X + TICK_WIDTH / 2.0 + NUMERAL_GAP_MM, BODY_WIDTH - TICK_LENGTH - NUMERAL_GAP_MM), (SCALE_START_X + TICK_WIDTH / 2.0 + NUMERAL_GAP_MM, BODY_WIDTH - TICK_LENGTH)),
    # The 10 sits on the -X side of the last full tick (the bar ends just past
    # it): its gap runs from the glyph's +X ink edge to that tick's -X edge.
    "Numeral10GapReference": ("Numeral10XGap", (SCALE_START_X + SCALE_SPAN - TICK_WIDTH / 2.0 - NUMERAL_GAP_MM, BODY_WIDTH - TICK_LENGTH - NUMERAL_GAP_MM), (SCALE_START_X + SCALE_SPAN - TICK_WIDTH / 2.0, BODY_WIDTH - TICK_LENGTH - NUMERAL_GAP_MM)),
}
DRAWING_DIMENSIONS = {
    "BodyProfile": {"BodyLength", "BodyWidth"},
    "Body": {"BodyThickness"},
    "Tick0Profile": {"Tick0Width"},
    "Tick0Cut": {"TickDepth"},
    "Numerals": {"NumeralDepth"},
    **{feature: {row[0]} for feature, row in REFERENCE_DIMENSIONS.items()},
}
# Decimal-inch places, authored on the part: the overall length, tick
# lengths and numeral layout the title block's .XX, and .XXX for the bar's
# section in the stop rebate, the engraving limits and the scale stations,
# except the minor pitch's .XXXX needed across 100 calibrated subdivisions.
# Nothing on this part is .X.
_TWO_PLACE = frozenset({
    "BodyLength", "FullTickLength", "MinorTickLength", "HalfTickLength",
    "NumeralHeight", "NumeralXGap", "NumeralYGap", "Numeral10XGap",
})
DRAWING_PRECISION = {
    feature: {
        name: 2 if name in _TWO_PLACE else 4 if name == "MinorTickPitch" else 3
        for name in names
    }
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME = {
    name: places for dims in DRAWING_PRECISION.values() for name, places in dims.items()
}
# The model's own bands, beyond the title block's rows (physical mm, printed
# in inch): none. The station table prints +/-.002 for every graduation from
# the end face nearest the 10; the 10 tick's land and detail A's pitches are
# references.
DRAWING_TOLERANCES: dict[str, float] = {}

DRAWING_VALUES_BY_NAME = {
    "BodyLength": BODY_LENGTH,
    "BodyWidth": BODY_WIDTH,
    "BodyThickness": BODY_THICKNESS,
    "Tick0Width": TICK_WIDTH,
    "TickDepth": TICK_DEPTH,
    "NumeralDepth": NUMERAL_DEPTH,
    **{
        row[0]: abs(row[2][0] - row[1][0]) + abs(row[2][1] - row[1][1])
        for row in REFERENCE_DIMENSIONS.values()
    },
}
