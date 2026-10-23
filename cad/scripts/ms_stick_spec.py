r"""Pure model/drawing contract for the graduated brass stick.

The 2026-10-10 user Option B ruling keeps the 200 x 8 x 3 blank and
groove geometry, shifting the whole scale and numerals 1.00 mm left.
Model dimensions own the manufacturing values, bands and decimal places.
The release supplies the engraved native/STEP model and its ruled-face/detail
drawings, not the generated build-input DXFs.
The 2026-10-23 owner ruling V-engraves the numerals: single-stroke sans
numerals cut as true 30-degree included V grooves (the model drafts every
stroke wall 15 degrees). The square-bottom graduations stay fixed.
"""

from __future__ import annotations

import math
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
_REFERENCES = Path(__file__).resolve().parents[1] / "references"
# One DXF per stroke layer (gen_ms_stick_numerals_dxf colours overlapping
# strokes apart; a drafted cut needs disjoint profiles). Literal names keep
# them in _buildgraph's data dependencies.
NUMERAL_LAYER_DXFS = (
    _REFERENCES / "ms-stick-numerals-1.dxf",
    _REFERENCES / "ms-stick-numerals-2.dxf",
    _REFERENCES / "ms-stick-numerals-3.dxf",
)
NUMERAL_HEIGHT_MM = 2.0
NUMERAL_GAP_MM = 0.6
NUMERAL_ROTATION_DEG = 90
# 2026-10-23 owner ruling: V-engrave the numerals with a 30-degree included
# V bit (the easiest hobby-mill route in brass). Single-stroke numerals, 0.24
# wide at the face (12% of the 2.0 height, legible and enamel-holding) and
# 0.40 deep; the drafted walls leave only NUMERAL_TIP_FLAT_MM at the root.
NUMERAL_V_INCLUDED_ANGLE_DEG = 30.0
NUMERAL_STROKE_WIDTH_MM = 0.24
NUMERAL_DEPTH = 0.40
NUMERAL_DEPTH_TOLERANCE_MM = 0.05
NUMERAL_TIP_FLAT_MM = NUMERAL_STROKE_WIDTH_MM - 2.0 * NUMERAL_DEPTH * math.tan(
    math.radians(NUMERAL_V_INCLUDED_ANGLE_DEG / 2.0)
)
NUMERALS_BBOX = (57.300, 1.721, 197.700, 4.400)
NUMERAL_VOLUME_MM3 = 2.6526
NUMERAL_FIRST_LAYER_VOLUME_MM3 = 1.5603

# Width and thickness give the sliding clearance in the 8.4 x 3.4 stop
# rebate; graduation positions set the amplitude-bar stations through the
# linear READOUT table. Overall length, tick lengths and numeral layout take
# the title block (2026-10-23 owner ruling): at .XX +/-0.51 the 199.49
# shortest bar still keeps the last tick whole (0.665 land past its groove). Groove width and depths hold the enamel fill; the
# deepest groove leaves 2.3 mm of stock at worst case, above the 2.0 target.
TITLE_BLOCK_XX_TOLERANCE_MM = 0.51
BODY_FIT_TOLERANCE_MM = 0.1
GRADUATION_POSITION_TOLERANCE_MM = 0.05
GRADUATION_WIDTH_TOLERANCE_MM = 0.05
GRADUATION_DEPTH_TOLERANCE_MM = 0.1

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
    "Tick0Width": GRADUATION_WIDTH_TOLERANCE_MM,
    "TickDepth": GRADUATION_DEPTH_TOLERANCE_MM,
    "NumeralDepth": NUMERAL_DEPTH_TOLERANCE_MM,
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
