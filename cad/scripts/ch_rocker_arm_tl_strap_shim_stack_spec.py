r"""Pure-data contract for the rocker arm's strap shim stack (MHA-CH-06-TL-11).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). Four
stacks stand on the rocker riser blocks and carry the blank: in S1 under the
raw lower face (at X -158/-60/+60/+158), in S4 under the S3-faced strap face,
datum B (at X -120/-45/+45/+120), so the 312 mm span cannot spring under the
cutter. Each stack is one piece of O1 precision-ground flat stock, 3/32 x 3/4 in
(Abrams), sawn to length and milled to width, standing on a steel shim pack
from the approved 0.001-0.031 in assortment (MSC 86798816). The pack makes up
each blank's measured gap; its modelled thickness is the nominal for a
5/16 in blank. The same four stacks serve S1 and S4.

Frame (the inventory's fixture frame for ``fixtures.strap-shim-stack``):
origin at the centre of the stack's underside on the riser block, +X along
the blank, +Z up. The shim pack fills Z0..SHIM_THICK and the ground piece
SHIM_THICK..STACK_HEIGHT; the piece's top face bears on the work.
"""

from __future__ import annotations

import math

import ch_rocker_arm_spec as rocker
from _printed_tolerance import printed_band_mm

INCH = 25.4
# Abrams Industries O1 precision ground flat stock 3/32 x 3/4 x 18 in
# (purchase approved by Pedro 2026-10-11); faces as supplied.
STRIP_THICK = 3.0 / 32.0 * INCH  # 2.38125
STOCK_WIDTH = 0.75 * INCH
# Raw rocker blank, 5/16 in plate (rocker plan stock_state top_z 7.9375).
RAW_BLANK_THICK = 5.0 / 16.0 * INCH
# The arm's strap is centred in the blank: S3 faces datum B at
# (blank + strap) / 2 above the raw underside (plan to_z 5.21875), so turned
# over in S4 it hangs (blank - strap) / 2 above the raw ends' riser blocks.
# S1 sets the stacks at the same height (plan S1 hold: any equal height).
STACK_HEIGHT = (RAW_BLANK_THICK - rocker.ARM_THICKNESS) / 2.0  # 2.71875
SHIM_THICK = STACK_HEIGHT - STRIP_THICK  # 0.3375 nominal pack
if not 0.0 < SHIM_THICK < STACK_HEIGHT:
    raise AssertionError("strap shim stack: the ground piece alone overshoots the gap")
# AUTHOR'S CHOICE: the trial plan's 20 mm piece; the width is the trial
# envelope (12), milled down from the 3/4 in stock, so every S4 stack stays
# inside the arm's strap band (below).
STACK_LENGTH = 20.0
STACK_WIDTH = 12.0
if STACK_WIDTH >= STOCK_WIDTH:
    raise AssertionError("strap shim stack is wider than its flat stock")

# S4 stack stations (rocker plan S4 hold, mirrored by the turned-over blank):
# (|X|, |Y|) of the stack centre in the arm's pivot frame. At its widest and
# over its whole length each stack must stay inside the arm's strap band
# (R800 top edge, R816 bottom edge), so it bears only on datum B and never
# under the uncut skin outside the arm.
S4_STATIONS = ((45.0, 1.26), (120.0, 8.96))
_HALF_W_MAX = (STACK_WIDTH + printed_band_mm(1)) / 2.0
_HALF_L_MAX = (STACK_LENGTH + printed_band_mm(1)) / 2.0


def _strap_band(x: float) -> tuple[float, float]:
    """(bottom, top) of the arm at ``x`` in the pivot frame (pivot at Y0)."""
    bottom = rocker.CENTER_Y - math.sqrt(rocker.R_BOTTOM**2 - x**2)
    top = rocker.CENTER_Y - math.sqrt(rocker.R_TOP**2 - x**2)
    return bottom - rocker.PIVOT_MID_Y, top - rocker.PIVOT_MID_Y


for _x, _y in S4_STATIONS:
    # Both edges rise with |x|: the inner end bounds the top, the outer the bottom.
    _bottom = _strap_band(_x + _HALF_L_MAX)[0]
    _top = _strap_band(_x - _HALF_L_MAX)[1]
    if not (_bottom < _y - _HALF_W_MAX and _y + _HALF_W_MAX < _top):
        raise AssertionError(
            f"S4 strap shim stack at X{_x:g} overhangs the arm's strap band"
        )

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StripProfile": {"StackLength", "StackWidth"},
    "Strip": {"StripThick"},
    "ShimPack": {"ShimThick"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "StripProfile": {"StackLength": 1, "StackWidth": 1},
    "Strip": {"StripThick": 2},
    "ShimPack": {"ShimThick": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError(
        "every marked strap shim stack dimension needs authored places"
    )
# The stock thickness and the shim pack print as references: the pack is
# built to each blank's gap, so neither carries a band. The pack's acceptance
# is fit-up instead (Main's ruling 2026-10-14): a feeler of this size must not
# enter between the stack and the blank's strap face, nor (Codex #1448 P1, the
# upper bound) under the raw blank ends on the riser blocks with the strap snug.
REFERENCE_DIMENSIONS = ("StripThick", "ShimThick")
FIT_UP_FEELER_NO_GO = 0.05

DRAWING_NOTES = "BOTH FLAT FACES BEAR: KEEP THEM FREE OF NICKS."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 4:1"

# The prechips fixture solid (fixtures.strap-shim-stack, bound by
# _process_plans.bind_shop): the whole stack at its nominal height, a shim
# (adjustable-height) support bearing on the work underside. Record fields
# other than geometry are the rocker trial's, unchanged.
PRECHIPS_SOLIDS: list[dict] = [
    {
        "name": "stack",
        "shape": "box",
        "supply": "bought",
        "shim": True,
        "at_mm": [-STACK_LENGTH / 2.0, -STACK_WIDTH / 2.0, 0.0],
        "size_mm": [STACK_LENGTH, STACK_WIDTH, STACK_HEIGHT],
        "locates": "work underside (S1 raw lower face; S4 S3-faced strap face, datum B)",
        "bears": "face",
        "note": (
            "3/32 in ground flat + shim to the measured gap M - 5.219; 2.71875 is the "
            "nominal for a 7.9375 blank (ASSUMED placeholder, checklist A1)"
        ),
        "measured": {
            "status": "measured",
            "by": "placeholder (realistic, remeasure: #1413)",
            "date": "2026-10-12",
            "instrument": "digital calipers, height gauge and indicator; physical component sizes/fit only",
        },
    },
]
