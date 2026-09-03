r"""Pure-data dimensional contract for the connecting-rod clevis pin.

The bright circular head visible on every dark connecting-rod clevis in
``ch14_images/page002_img02.png`` and ``page002_img01.jpeg`` belongs to a
separate polished-steel pin.  The part origin is the front cheek's outer face;
the shank runs along local +Z through both #47 cheek holes and the rocker
tongue.

PURE DATA, no SolidWorks/COM imports.
"""

from __future__ import annotations

from _fit_limits import SHAFT_H
from connecting_rod_spec import CLEVIS_OUTSIDE_WIDTH, PIN_HOLE_DIA

SHANK_DIA = 1.8
SHANK_DIA_BAND = SHAFT_H
GRIP_LENGTH = 4.9
HEAD_DIA = 3.0
HEAD_THICKNESS = 0.6

# The #47 holes carry the unilateral +0.10/0 drilled-hole allowance, so their
# worst-case diameter is the nominal below.  A ground-shaft h band holds the
# pin at or below nominal and preserves this 0.194 mm minimum diametral running
# clearance even at both worst-case limits.
MIN_DIAMETRAL_CLEARANCE = PIN_HOLE_DIA - (SHANK_DIA + SHANK_DIA_BAND[0])

if min(SHANK_DIA, GRIP_LENGTH, HEAD_DIA, HEAD_THICKNESS) <= 0.0:
    raise ValueError("clevis-pin dimensions must all be positive")
if SHANK_DIA >= PIN_HOLE_DIA:
    raise ValueError(
        f"clevis-pin shank Ø{SHANK_DIA:g} does not fit the "
        f"#47 Ø{PIN_HOLE_DIA:g} holes"
    )
if MIN_DIAMETRAL_CLEARANCE <= 0.0:
    raise ValueError(
        "clevis-pin worst-case shank must remain below the worst-case #47 hole"
    )
if HEAD_DIA <= PIN_HOLE_DIA:
    raise ValueError("clevis-pin head must be larger than the #47 hole")
if abs(GRIP_LENGTH - CLEVIS_OUTSIDE_WIDTH) > 1e-12:
    raise ValueError(
        f"clevis-pin grip {GRIP_LENGTH:g} does not close the "
        f"{CLEVIS_OUTSIDE_WIDTH:g} clevis outside width"
    )
