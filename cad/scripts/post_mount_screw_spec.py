r"""Pure-data contract shared by the MHA-142 post mount screw part and drawing.

MHA-142 is MSC 40923898 (1/4-20 x 3-1/2 slotted fillister, U37c) cut to
length: a MODIFIED purchased part.  Its head seats on the MHA-016
counterbore floor and the shank threads through the MHA-091 plate, which
swings over the base, so the cut end must never stand proud of the plate's
underside.  The cut length is therefore a real, model-owned dimension on the
sheet, with the band that chain allows (policy rule 2), not a number in an
installation note (rule 6, Main's eye pass of warm-c486).

The engagement this leaves is the named rule-12 exception in
``cad/docs/drawing-simplicity-policy.md``; it is held here as a model
assert, not printed on the part sheet.
"""

from __future__ import annotations

import math

import cone_pivot_post_spec as post
import cone_swing_platform_spec as platform
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

SKU = "40923898"
THREAD_DIA_MM, CUT_LENGTH_MM, _HEAD_H, _HEAD_DIA, _PITCH = FILLISTER_SIZES[SKU]

# Head seated on the MHA-016 counterbore floor: the under-head face to the
# plate's top face, at the model's nominal post.
GRIP_MM = post.BLOCK_HEIGHT - post.ATTACHMENT_CBORE_DEPTH
# The longest cut whose end is flush with the MHA-091 underside.
FLUSH_LENGTH_MM = GRIP_MM + platform.PLATE_THICKNESS

# Model-owned drawing controls: one hidden reference sketch whose single
# driving dimension IS the cut length, under-head face to cut end.
CUT_LENGTH_SKETCH = "CutLengthReference"
CUT_LENGTH_DIMENSION = "CutLength"
DRAWING_DIMENSIONS: dict[str, set[str]] = {CUT_LENGTH_SKETCH: {CUT_LENGTH_DIMENSION}}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    CUT_LENGTH_SKETCH: {CUT_LENGTH_DIMENSION: 1}
}
DRAWING_PRECISION_BY_NAME = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
REFERENCE_SKETCHES = (CUT_LENGTH_SKETCH,)

# (upper, lower), the _fit_limits convention.  The nominal 86.0 (U37c) is
# the shortest acceptable cut; the upper deviation reaches toward flush,
# FLOORED at the dimension's own places so a rounded limit can never let the
# end stand proud.  At the model's nominal post and plate that reads flush to
# 0.3 short of the MHA-091 underside.
_PLACES = DRAWING_PRECISION[CUT_LENGTH_SKETCH][CUT_LENGTH_DIMENSION]
_SCALE = 10**_PLACES
CUT_LENGTH_BAND = (
    math.floor((FLUSH_LENGTH_MM - CUT_LENGTH_MM) * _SCALE + 1e-9) / _SCALE,
    0.0,
)
CUT_LENGTH_MAX_MM = CUT_LENGTH_MM + CUT_LENGTH_BAND[0]
CUT_LENGTH_MIN_MM = CUT_LENGTH_MM + CUT_LENGTH_BAND[1]
if CUT_LENGTH_MAX_MM > FLUSH_LENGTH_MM + 1e-9:
    raise ValueError(
        f"MHA-142 long limit {CUT_LENGTH_MAX_MM:.2f} stands proud of the "
        f"MHA-091 underside ({FLUSH_LENGTH_MM:.2f})"
    )
if CUT_LENGTH_BAND[0] <= CUT_LENGTH_BAND[1]:
    raise ValueError(f"MHA-142 cut-length band is empty: {CUT_LENGTH_BAND!r}")

# The named rule-12 exception (User, U37c/U41): 0.90D minimum engagement.
# Enforced here at the short limit; never printed on the part sheet.
MIN_ENGAGEMENT_DIAMETERS = 0.90
ENGAGEMENT_MIN_MM = CUT_LENGTH_MIN_MM - GRIP_MM
if ENGAGEMENT_MIN_MM / THREAD_DIA_MM < MIN_ENGAGEMENT_DIAMETERS:
    raise ValueError(
        f"MHA-142 engagement {ENGAGEMENT_MIN_MM:.2f} at the short limit is "
        f"under {MIN_ENGAGEMENT_DIAMETERS:.2f}D"
    )

# Rule 6: no dimension, no tolerance, no installation sequence.  The cut
# length is the dimension above; how the screws go in is an MHA-A03 step.
MANUFACTURING_NOTES = (
    "CHAMFER CUT END.\nUNDIMENSIONED PURCHASED GEOMETRY IS REFERENCE."
)
