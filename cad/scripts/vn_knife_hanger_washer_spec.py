"""Native reference dimensions for the purchased knife-hanger washer.

The purchased sheet does not add manufacturing PMI.  These three names are
renamed on the source model after the vendor geometry is built, marked for
model-item import, and shown parenthesized on the receiving-reference sheet.
The values therefore remain owned by the native ``.SLDPRT`` dimensions rather
than by drawing-local nominal text.
"""

from __future__ import annotations


OUTER_DIAMETER_DIM = "ReferenceOuterDiameter"
INNER_DIAMETER_DIM = "ReferenceInnerDiameter"
THICKNESS_DIM = "ReferenceThickness"

DRAWING_DIMENSIONS = {
    "AnnulusProfile": {OUTER_DIAMETER_DIM, INNER_DIAMETER_DIM},
    "WasherBody": {THICKNESS_DIM},
}

# Receiving reference dimensions use ordinary two-place millimetres; the
# underlying native model values remain read back independently of display
# rounding.  These are reference dimensions, not manufacturing tolerances.
DRAWING_PRECISION = {
    "AnnulusProfile": {
        OUTER_DIAMETER_DIM: 2,
        INNER_DIAMETER_DIM: 2,
    },
    "WasherBody": {THICKNESS_DIM: 2},
}

DRAWING_PRECISION_BY_NAME = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
