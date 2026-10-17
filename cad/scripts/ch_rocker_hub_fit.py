r"""The press fit that joins the built-up rocker arm's hub to its strap.

PURE DATA, no SolidWorks/COM imports. MHA-CH-006 may be built up (its
``ch_rocker_arm_notes.BUILT_UP_PERMISSION_NOTE``): the turned hub MHA-CH-012
is pressed into the Ø10.20 hole of the flat strap MHA-CH-013. Both detail
builds and their drawing tests import this one module, so the hole's band, the
land's band and the interference they make are stated once.

User ruling (route v3, 2026-10-16): a press fit, the strap hole H7 and the hub
land r6. ISO 286-2, nominal sizes over 10 up to 18 mm: H7 is 0/+0.018 and r6
is +0.023/+0.034, so the diametral interference runs 0.005-0.034. H7/p6 was
refused: p6's +0.018 floor meets H7's +0.018 ceiling, so its least
interference is 0.000 and a worst-case pair goes together line-to-line. The
size range is the 10.20 nominal's (``ch_rocker_arm_spec.HUB_DIA``).
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
HUB_LAND_BAND = (0.034, 0.023)  # r6


def press_interference(
    land_band: tuple[float, float], hole_band: tuple[float, float]
) -> tuple[float, float]:
    """Diametral interference (least, greatest) of a land band in a hole band.

    The least is the smallest land in the largest hole, the greatest the
    largest land in the smallest hole. A press fit must interfere at both
    ends: a least of 0.000 is a line-to-line pair that need not hold.
    """
    least = round(land_band[1] - hole_band[0], 6)
    greatest = round(land_band[0] - hole_band[1], 6)
    if not least > 0.0:
        raise AssertionError(
            f"the hub land can go in the strap hole line-to-line or loose: "
            f"{(least, greatest)}"
        )
    return least, greatest


PRESS_INTERFERENCE = press_interference(HUB_LAND_BAND, STRAP_HOLE_BAND)

# The callout row both prints carry under their Ø (drawing-guidelines.md rule 4:
# a tight band names its mate and why).
INTERFERENCE_TEXT = (
    f"{PRESS_INTERFERENCE[0]:.3f}-{PRESS_INTERFERENCE[1]:.3f} DIAMETRAL INTERFERENCE"
)
