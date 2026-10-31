r"""Pure model/drawing contract for the graduated brass stick.

The 2026-10-10 user Option B ruling shifted the whole scale and numerals
1.00 mm left on the blank; the 2026-10-23 owner ruling lengthened the blank so
the last graduation keeps a rule-17 land to the end face at worst case.
Model dimensions own the manufacturing values, bands and decimal places.
The release supplies the engraved native/STEP model and its ruled-face/detail
drawings, not the generated build-input DXFs.
The 2026-10-23 owner ruling V-engraves the numerals: single-stroke sans
numerals cut as true 30-degree included V grooves (the model drafts every
stroke wall 15 degrees). The square-bottom graduations stay fixed.

Issue #290 (decimal-inch pilot): the sheet prints decimal inch
(``drawing_unit: in``). Every length below is physical millimetres, authored
as the exact decimal of the inch value it prints, snapped to that printed
grid: the 8.1 x .315 x .118 bar, ticks .016 MIN wide and .020 MIN deep,
tick lengths .12 / .07 / .16, numerals .08 high, .02 off their tick and .016
MIN deep. Exempt (owner ruling, pitch/calibration geometry): the configured
14.2 mm full and 1.42 mm minor graduation pitch
(``cad/config/machine/amplitude.yaml``) and the 56.5 mm scale zero, the rule
the amplitude stations and the stop setting are read against; they print
rounded (2.224, .559, .056) at their own +/-.002.
The unprinted V-bit stroke width at the face (0.24) is tool geometry and stays.
The overall length is the one unmated, non-functional size: .X, 8.1 so the
shortest bar still keeps the .080 rule-17 land past the widest last groove.
The tick lengths take the title block's .XX: a full tick at .12 +.01 and a
half-division tick at .16 -.01 stay .02 apart.
"""

from __future__ import annotations

import math
from pathlib import Path

import _config
from _drawing_units import drawing_unit
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
# drawing-guidelines.md rule 17 (walls and webs) on the inch sheet: .080 in.
WALL_TARGET_MM = 2.032


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as decimal-inch print text: ``.080``, ``8.1``."""
    text = f"{value_mm / 25.4:.{places}f}"
    return text[1:] if text.startswith("0.") else text


BODY_LENGTH = 205.74  # 8.1
BODY_WIDTH = 8.001  # .315
BODY_THICKNESS = 2.9972  # .118
# Unprinted: the bar beyond the last full tick. The model derives scale zero
# from the length, the configured span and this margin, which the 8.1 length
# grows from 3.5 so scale zero stays put.
SCALE_END_MARGIN = 7.24
# Exempt with the pitch (calibration): scale zero stays at 56.5 where the
# 2026-10-10 Option B ruling put it, so every graduation the assembly sets the
# stop and the bar stations against is unmoved; it prints 2.224 at the
# stations' +/-.002.
SCALE_START_X = BODY_LENGTH - SCALE_SPAN - SCALE_END_MARGIN
if abs(SCALE_START_X - 56.5) > 1e-9:
    raise AssertionError(f"scale zero moved off its calibrated 56.5 mm: {SCALE_START_X}")
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
NUMERAL_V_INCLUDED_ANGLE_DEG = 30.0
NUMERAL_STROKE_WIDTH_MM = 0.24
NUMERAL_DEPTH = 0.4064  # .016 MIN
NUMERAL_TIP_FLAT_MM = NUMERAL_STROKE_WIDTH_MM - 2.0 * NUMERAL_DEPTH * math.tan(
    math.radians(NUMERAL_V_INCLUDED_ANGLE_DEG / 2.0)
)
# Each stroke's ends are the V bit's footprint, a half-round inscribed in this
# many facets (gen_ms_stick_numerals_dxf), so joints reach the full depth.
NUMERAL_END_FACETS = 8
# The deepest V the fixed 0.24 face outline supports: past it the drafted end
# facets meet and the cut collapses. NumeralDepth is editable only below it.
NUMERAL_DEPTH_MAX_MM = (
    NUMERAL_STROKE_WIDTH_MM / 2.0 * math.cos(math.pi / (2 * NUMERAL_END_FACETS))
    / math.tan(math.radians(NUMERAL_V_INCLUDED_ANGLE_DEG / 2.0))
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
# amplitude-bar stations through the linear READOUT table, at their own
# +/-.002. The overall length (.X), tick lengths and numeral layout take the
# title block. Graduation width and both engraving depths name no mate, so
# they are single ".nnn MIN" limits that hold the enamel fill (coordinator
# ruling 2026-10-23). Their ceilings are stated facts, not bands (coordinator
# ruling 2026-10-23, on codjiflo's #1905 review): the graduation width stays
# .024 MAX on the .056 minor pitch, so neighbouring grooves never merge and
# the last one stays on the shortest bar; both depths leave the stated .080
# of stock under them.
TITLE_BLOCK_X_TOLERANCE_MM = printed_band_mm(1, unit=UNIT)
BODY_FIT_TOLERANCE_MM = printed_band_mm(3, unit=UNIT)
GRADUATION_POSITION_TOLERANCE_MM = 0.0508  # +/-.002
GRADUATION_FLOOR_MIN_MM = WALL_TARGET_MM
GRADUATION_FLOOR_CALLOUT = f"STOCK UNDER GROOVE {inch_text(GRADUATION_FLOOR_MIN_MM, 3)} MIN"
NUMERAL_FLOOR_CALLOUT = f"STOCK UNDER {inch_text(GRADUATION_FLOOR_MIN_MM, 3)} MIN"
GRADUATION_WIDTH_MAX_MM = 0.6096  # .024
GRADUATION_WIDTH_CALLOUT = (
    f"{inch_text(GRADUATION_WIDTH_MAX_MM, 3)} MAX ON {inch_text(MINOR_SPACING, 3)} PITCH"
)
# The widest last groove, its zero and its noncumulative station both at
# their band, keeps the rule-17 land to the end face of the shortest bar the
# .X length allows.
LAST_GROOVE_LAND_MIN_MM = BODY_LENGTH - TITLE_BLOCK_X_TOLERANCE_MM - (
    SCALE_START_X + SCALE_SPAN + 2.0 * GRADUATION_POSITION_TOLERANCE_MM
    + GRADUATION_WIDTH_MAX_MM / 2.0
)
if LAST_GROOVE_LAND_MIN_MM < WALL_TARGET_MM:
    raise AssertionError(
        f"last graduation land {LAST_GROOVE_LAND_MIN_MM:.3f} mm is below the rule-17 target"
    )
# Both engraving depths leave the stated floor in the thinnest bar.
if BODY_THICKNESS - BODY_FIT_TOLERANCE_MM - max(TICK_DEPTH, NUMERAL_DEPTH) < GRADUATION_FLOOR_MIN_MM:
    raise AssertionError("an engraving's nominal depth already breaks the stated floor")
# swTolType_e.swTolMIN prints the nominal plus MIN: the model value is the
# printed minimum. (lower, upper) deviations are the stored readback pair.
MIN_LIMIT_TOL_TYPE = 5
MIN_LIMIT_DEVIATIONS_MM = {
    "Tick0Width": (0.0, TICK_WIDTH),
    "TickDepth": (0.0, TICK_DEPTH),
    "NumeralDepth": (0.0, NUMERAL_DEPTH),
}

# Construction chords use the actual finished edge and actual groove/glyph
# extents. ScaleStartX and both pitch chords terminate at true groove centres,
# never at either side of the finite-width cut. ScaleEndMargin stays unprinted.
REFERENCE_DIMENSIONS = {
    "ScaleStartReference": ("ScaleStartX", (0.0, BODY_WIDTH), (SCALE_START_X, BODY_WIDTH)),
    "FullLengthReference": ("FullTickLength", (SCALE_START_X, BODY_WIDTH - TICK_LENGTH), (SCALE_START_X, BODY_WIDTH)),
    "MinorLengthReference": ("MinorTickLength", (SCALE_START_X + MINOR_SPACING, BODY_WIDTH - MINOR_TICK_LENGTH), (SCALE_START_X + MINOR_SPACING, BODY_WIDTH)),
    "HalfLengthReference": ("HalfTickLength", (SCALE_START_X + DIVISION_SPACING / 2.0, BODY_WIDTH - HALF_TICK_LENGTH), (SCALE_START_X + DIVISION_SPACING / 2.0, BODY_WIDTH)),
    "FullPitchReference": ("FullTickPitch", (SCALE_START_X, BODY_WIDTH), (SCALE_START_X + DIVISION_SPACING, BODY_WIDTH)),
    "MinorPitchReference": ("MinorTickPitch", (SCALE_START_X, BODY_WIDTH), (SCALE_START_X + MINOR_SPACING, BODY_WIDTH)),
    "NumeralHeightReference": ("NumeralHeight", (SCALE_START_X + TICK_WIDTH / 2.0 + NUMERAL_GAP_MM, BODY_WIDTH - TICK_LENGTH - NUMERAL_GAP_MM), (SCALE_START_X + TICK_WIDTH / 2.0 + NUMERAL_GAP_MM + NUMERAL_HEIGHT_MM, BODY_WIDTH - TICK_LENGTH - NUMERAL_GAP_MM)),
    "NumeralXGapReference": ("NumeralXGap", (SCALE_START_X + TICK_WIDTH / 2.0, BODY_WIDTH - TICK_LENGTH - NUMERAL_GAP_MM), (SCALE_START_X + TICK_WIDTH / 2.0 + NUMERAL_GAP_MM, BODY_WIDTH - TICK_LENGTH - NUMERAL_GAP_MM)),
    "NumeralYGapReference": ("NumeralYGap", (SCALE_START_X + TICK_WIDTH / 2.0 + NUMERAL_GAP_MM, BODY_WIDTH - TICK_LENGTH - NUMERAL_GAP_MM), (SCALE_START_X + TICK_WIDTH / 2.0 + NUMERAL_GAP_MM, BODY_WIDTH - TICK_LENGTH)),
}
DRAWING_DIMENSIONS = {
    "BodyProfile": {"BodyLength", "BodyWidth"},
    "Body": {"BodyThickness"},
    "Tick0Profile": {"Tick0Width"},
    "Tick0Cut": {"TickDepth"},
    "Numerals": {"NumeralDepth"},
    **{feature: {row[0]} for feature, row in REFERENCE_DIMENSIONS.items()},
}
# Decimal-inch places, authored on the part: the overall length .X, the tick
# lengths and numeral layout the title block's .XX, and .XXX for the bar's
# section in the stop rebate, the engraving limits and the scale stations.
_ONE_PLACE = frozenset({"BodyLength"})
_TWO_PLACE = frozenset({
    "FullTickLength", "MinorTickLength", "HalfTickLength",
    "NumeralHeight", "NumeralXGap", "NumeralYGap",
})
DRAWING_PRECISION = {
    feature: {
        name: 1 if name in _ONE_PLACE else 2 if name in _TWO_PLACE else 3
        for name in names
    }
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME = {
    name: places for dims in DRAWING_PRECISION.values() for name, places in dims.items()
}
# The model's own bands, beyond the title block's rows (physical mm, printed
# in inch): the scale stations' +/-.002.
DRAWING_TOLERANCES = {
    "ScaleStartX": GRADUATION_POSITION_TOLERANCE_MM,
    "FullTickPitch": GRADUATION_POSITION_TOLERANCE_MM,
    "MinorTickPitch": GRADUATION_POSITION_TOLERANCE_MM,
}
# The model's stroke shapes are representative; the shop's own single-stroke
# sans font engraves the same V at the shown height and gaps.
DRAWING_NOTES = "NUMERALS: ANY SINGLE-STROKE SANS FONT"
NUMERAL_PLACEMENT_NOTE = (
    "NUMERALS 0-9 RIGHT OF FULL TICKS;\n"
    "10 LEFT OF FINAL FULL TICK.\n"
    "BOTH USE SHOWN GAPS"
)
FRONT_VIEW_NOTE = "RULED FACE SCALE 1:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"

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
