r"""Pure model/drawing contract for the graduated brass stick.

The 2026-10-10 user Option B ruling keeps the 200 x 8 x 3 blank and
groove geometry, shifting the whole scale and numeral DXF 1.00 mm left.
Model dimensions own the manufacturing values, bands and decimal places.
The release supplies the engraved native/STEP model and its ruled-face/detail
drawings, not the generated build-input DXF. Refer numeral outlines to that model.
"""

from __future__ import annotations

from pathlib import Path

from ms_stick_geom import (
    DIVISION_COUNT as DIVISION_COUNT,
    DIVISION_SPACING,
    MINOR_PER_DIVISION as MINOR_PER_DIVISION,
    MINOR_SPACING,
    SCALE_SPAN,
)

BODY_LENGTH = 200.0
BODY_WIDTH = 8.0
BODY_THICKNESS = 3.0
SCALE_END_MARGIN = 1.5
SCALE_START_X = BODY_LENGTH - SCALE_SPAN - SCALE_END_MARGIN
TICK_WIDTH = 0.4
TICK_LENGTH = 3.0
MINOR_TICK_LENGTH = 1.8
HALF_TICK_LENGTH = 4.0
TICK_DEPTH = 0.5
TICK_OVERHANG = 1.0
NUMERALS_DXF = Path(__file__).resolve().parents[1] / "references" / "ms-stick-numerals.dxf"
NUMERAL_HEIGHT_MM = 2.0
NUMERAL_GAP_MM = 0.6
NUMERAL_ROTATION_DEG = 90
NUMERAL_AREA_MM2 = 13.108
NUMERALS_BBOX = (57.300, 1.393, 197.700, 4.400)

# Width and thickness govern the running clearance in the 8.4 x 3.4 stop
# window; engraving position accuracy is noncumulative along the scale.
# The 2026-10-10 user Option B ruling keeps the complete last tick:
# routine +/-0.1 facing gives a 199.90 minimum against a 198.825 maximum
# groove edge, leaving 1.075 mm worst-case land (1.30 mm nominal).
# Depth only holds enamel: its loose band leaves 2.3 mm of stock at worst case
# (minimum thickness minus maximum depth), above the 2.0 mm web target.
BODY_LENGTH_TOLERANCE_MM = 0.1
BODY_FIT_TOLERANCE_MM = 0.1
GRADUATION_POSITION_TOLERANCE_MM = 0.05
GRADUATION_WIDTH_TOLERANCE_MM = 0.05
GRADUATION_DEPTH_TOLERANCE_MM = 0.1
GRADUATION_LENGTH_TOLERANCE_MM = 0.1
NUMERAL_TOLERANCE_MM = 0.1

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
    **{feature: {row[0]} for feature, row in REFERENCE_DIMENSIONS.items()},
}
DRAWING_PRECISION = {
    feature: {name: 2 for name in names}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME = {
    name: places for dims in DRAWING_PRECISION.values() for name, places in dims.items()
}
DRAWING_TOLERANCES = {
    "BodyLength": BODY_LENGTH_TOLERANCE_MM,
    "BodyWidth": BODY_FIT_TOLERANCE_MM,
    "BodyThickness": BODY_FIT_TOLERANCE_MM,
    "Tick0Width": GRADUATION_WIDTH_TOLERANCE_MM,
    "TickDepth": GRADUATION_DEPTH_TOLERANCE_MM,
    "ScaleStartX": GRADUATION_POSITION_TOLERANCE_MM,
    "FullTickLength": GRADUATION_LENGTH_TOLERANCE_MM,
    "MinorTickLength": GRADUATION_LENGTH_TOLERANCE_MM,
    "HalfTickLength": GRADUATION_LENGTH_TOLERANCE_MM,
    "FullTickPitch": GRADUATION_POSITION_TOLERANCE_MM,
    "MinorTickPitch": GRADUATION_POSITION_TOLERANCE_MM,
    "NumeralHeight": NUMERAL_TOLERANCE_MM,
    "NumeralXGap": NUMERAL_TOLERANCE_MM,
    "NumeralYGap": NUMERAL_TOLERANCE_MM,
}
DRAWING_NOTES = "NUMERAL OUTLINES: ms-stick.SLDPRT"
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
    **{
        row[0]: abs(row[2][0] - row[1][0]) + abs(row[2][1] - row[1][1])
        for row in REFERENCE_DIMENSIONS.values()
    },
}
