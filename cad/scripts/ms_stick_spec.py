r"""Pure model/drawing contract for the graduated brass stick.

The 2026-10-10 user Option B ruling keeps the 200 x 8 x 3 blank (all-inch
experiment: 7-7/8 x 5/16 x 1/8) and groove geometry, shifting the whole scale
and numeral DXF 1.00 mm left (now a 1/16 end margin).
Model dimensions own the manufacturing values, bands and decimal places.
The release supplies the engraved native/STEP model and its ruled-face/detail
drawings, not the generated build-input DXF. Name its pinned outline font on the
print while retaining the native model as the exact numeral-outline authority.
The 2026-10-11 user Option A numeral ruling changes only their cut envelope:
0.10 +/-0.05 deep, cut with a 30-degree included V bit (a print note; the model
carries the depth as straight walls).
Surface glyph outlines/placement and the square-bottom graduations stay fixed.
"""

from __future__ import annotations

from pathlib import Path

from _inch import inch
from ms_stick_geom import (
    DIVISION_COUNT as DIVISION_COUNT,
    DIVISION_SPACING,
    MINOR_PER_DIVISION as MINOR_PER_DIVISION,
    MINOR_SPACING,
    SCALE_SPAN,
)

# All-inch experiment: a 7-7/8 x 5/16 x 1/8 blank (was 200 x 8 x 3); the
# configured 9/16 division (amplitude.yaml) spans 5-5/8, so tick 0 lands at
# 2-3/16 with a 1/16 end margin.
BODY_LENGTH = inch(63, 8)  # 200.025 (was 200.0)
BODY_WIDTH = inch(5, 16)  # 7.9375 (was 8.0)
BODY_THICKNESS = inch(1, 8)  # 3.175 (was 3.0)
SCALE_END_MARGIN = inch(1, 16)  # 1.5875 (was 1.5)
SCALE_START_X = BODY_LENGTH - SCALE_SPAN - SCALE_END_MARGIN
TICK_WIDTH = 0.4  # engraving cutter width, below the 1/32 grid (kept)
TICK_LENGTH = inch(1, 8)  # 3.175 (was 3.0)
MINOR_TICK_LENGTH = inch(1, 16)  # 1.5875 (was 1.8)
HALF_TICK_LENGTH = inch(3, 16)  # 4.7625 (was 4.0)
TICK_DEPTH = 0.5  # enamel-fill engraving depth, below the 1/32 grid (kept)
TICK_OVERHANG = 1.0  # sketch run-out past the edge, not a machined size
NUMERALS_DXF = Path(__file__).resolve().parents[1] / "references" / "ms-stick-numerals.dxf"
NUMERAL_HEIGHT_MM = 2.0
NUMERAL_GAP_MM = 0.6
NUMERAL_ROTATION_DEG = 90
NUMERAL_AREA_MM2 = 13.108
NUMERAL_DEPTH = 0.10
NUMERAL_DEPTH_TOLERANCE_MM = 0.05
NUMERAL_V_BIT_INCLUDED_ANGLE_DEG = 30.0
NUMERALS_BBOX = (56.3625, 1.1552, 197.6375, 4.1625)  # regenerated (was 57.300, 1.393, 197.700, 4.400)

# Width and thickness govern the running clearance in the 11/32 x 5/32 stop
# window; engraving position accuracy is noncumulative along the scale.
# The 2026-10-10 user Option B ruling keeps the complete last tick:
# routine +/-0.1 facing gives a 199.925 minimum against a 198.7625 maximum
# groove edge, leaving 1.1625 mm worst-case land (1.3875 mm nominal).
# Depth only holds enamel: its loose band leaves 2.475 mm of stock at worst case
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
    "BodyLength": BODY_LENGTH_TOLERANCE_MM,
    "BodyWidth": BODY_FIT_TOLERANCE_MM,
    "BodyThickness": BODY_FIT_TOLERANCE_MM,
    "Tick0Width": GRADUATION_WIDTH_TOLERANCE_MM,
    "TickDepth": GRADUATION_DEPTH_TOLERANCE_MM,
    "NumeralDepth": NUMERAL_DEPTH_TOLERANCE_MM,
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
# gen_ms_stick_numerals_dxf uses _dxf_text's pinned DejaVuSans.ttf closed loops,
# not a single-stroke font or a constant-width graduation cutter path.
DRAWING_NOTES = "NUMERALS: DEJAVU SANS OUTLINES\nNUMERAL OUTLINES: ms-stick.SLDPRT (REFERENCE)"
NUMERAL_TOOL_NOTE = (
    f"NUMERALS: {NUMERAL_V_BIT_INCLUDED_ANGLE_DEG:g}° INCLUDED V ENGRAVING BIT;\n"
    "ENAMEL-FILLED"
)
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
