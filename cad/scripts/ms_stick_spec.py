r"""Pure model/drawing contract for the unchanged graduated brass stick.

The 200 x 8 x 3 bar, grooves and numeral DXF retain their existing geometry.
The scale is configured in amplitude.yaml and read once by ms_stick_geom.
Model dimensions own the manufacturing values, bands and decimal places.
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
SCALE_END_MARGIN = 0.5
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
NUMERALS_BBOX = (58.300, 1.393, 198.700, 4.400)

# Width and thickness govern the running clearance in the 8.4 x 3.4 stop
# window; engraving position accuracy is noncumulative along the scale.
BODY_FIT_TOLERANCE_MM = 0.1
GRADUATION_POSITION_TOLERANCE_MM = 0.05
GRADUATION_WIDTH_DEPTH_TOLERANCE_MM = 0.05
GRADUATION_LENGTH_TOLERANCE_MM = 0.1
SCALE_END_MARGIN_TOLERANCE_MM = 0.25
NUMERAL_TOLERANCE_MM = 0.1

# Construction chords use the actual finished edge and actual groove/glyph
# extents. They carry sizes which the cut's overhanging profile does not own.
REFERENCE_DIMENSIONS = {
    "ScaleStartReference": ("ScaleStartX", (0.0, BODY_WIDTH), (SCALE_START_X, BODY_WIDTH)),
    "ScaleEndReference": ("ScaleEndMargin", (BODY_LENGTH - SCALE_END_MARGIN, BODY_WIDTH), (BODY_LENGTH, BODY_WIDTH)),
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
    "BodyWidth": BODY_FIT_TOLERANCE_MM,
    "BodyThickness": BODY_FIT_TOLERANCE_MM,
    "Tick0Width": GRADUATION_WIDTH_DEPTH_TOLERANCE_MM,
    "TickDepth": GRADUATION_WIDTH_DEPTH_TOLERANCE_MM,
    "ScaleStartX": GRADUATION_POSITION_TOLERANCE_MM,
    "ScaleEndMargin": SCALE_END_MARGIN_TOLERANCE_MM,
    "FullTickLength": GRADUATION_LENGTH_TOLERANCE_MM,
    "MinorTickLength": GRADUATION_LENGTH_TOLERANCE_MM,
    "HalfTickLength": GRADUATION_LENGTH_TOLERANCE_MM,
    "FullTickPitch": GRADUATION_POSITION_TOLERANCE_MM,
    "MinorTickPitch": GRADUATION_POSITION_TOLERANCE_MM,
    "NumeralHeight": NUMERAL_TOLERANCE_MM,
    "NumeralXGap": NUMERAL_TOLERANCE_MM,
    "NumeralYGap": NUMERAL_TOLERANCE_MM,
}
DRAWING_NOTES = "NUMERAL OUTLINES PER SUPPLIED MS-STICK-NUMERALS.DXF"
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
