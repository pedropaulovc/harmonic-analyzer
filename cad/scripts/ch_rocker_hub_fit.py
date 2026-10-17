r"""The press fit that joins the built-up rocker arm's hub to its strap.

PURE DATA, no SolidWorks/COM imports. MHA-CH-006 may be built up (its
``ch_rocker_arm_notes.BUILT_UP_PERMISSION_NOTE``): the turned hub MHA-CH-012
is pressed into the Ø10.20 hole of the flat strap MHA-CH-013. Both detail
builds and their drawing tests import this one module, so the hole's band, the
land's band and the interference they make are stated once.

User ruling (route v3, 2026-10-16): a press fit, the strap hole H7 and the hub
land p6. ISO 286-2, nominal sizes over 10 up to 18 mm: H7 is 0/+0.018 and p6
is +0.018/+0.029, so the diametral interference runs 0.000-0.029. The size
range is the 10.20 nominal's (``ch_rocker_arm_spec.HUB_DIA``).
"""

from __future__ import annotations

from ch_rocker_arm_spec import HUB_DIA

# ISO 286-2, 10-18 mm (the test pins the range): (upper, lower) deviations.
ISO_RANGE_MM = (10.0, 18.0)
if not ISO_RANGE_MM[0] < HUB_DIA <= ISO_RANGE_MM[1]:
    raise AssertionError(
        f"Ø{HUB_DIA} left the ISO 286 10-18 mm range the bands are read from"
    )
STRAP_HOLE_BAND = (0.018, 0.0)  # H7
HUB_LAND_BAND = (0.029, 0.018)  # p6

# Diametral interference (least, greatest): the smallest land in the largest
# hole, then the largest land in the smallest hole.
PRESS_INTERFERENCE = (
    round(HUB_LAND_BAND[1] - STRAP_HOLE_BAND[0], 6),
    round(HUB_LAND_BAND[0] - STRAP_HOLE_BAND[1], 6),
)
if PRESS_INTERFERENCE[0] < 0.0:
    raise AssertionError(
        f"the hub land can slip in the strap hole: {PRESS_INTERFERENCE}"
    )

# The callout row both prints carry under their Ø (drawing-guidelines.md rule 4:
# a tight band names its mate and why).
INTERFERENCE_TEXT = (
    f"{PRESS_INTERFERENCE[0]:.3f}-{PRESS_INTERFERENCE[1]:.3f} DIAMETRAL INTERFERENCE"
)
