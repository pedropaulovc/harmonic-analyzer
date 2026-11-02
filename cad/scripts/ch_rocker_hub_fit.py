r"""The press fit that joins the built-up rocker arm's hub to its strap.

PURE DATA, no SolidWorks/COM imports. MHA-CH-06 may be built up (its
``ch_rocker_arm_notes.BUILT_UP_PERMISSION_NOTE``): the turned hub MHA-CH-12
is pressed into the Ø.400 hole of the flat strap MHA-CH-13. Both detail
builds and their drawing tests import this one module, so the hole's band, the
land's band and the interference they make are stated once.

User ruling (route v3, 2026-10-16): a press fit. #290 states it in inch on
the .400 nominal (``ch_rocker_arm_spec.HUB_DIA``): the strap hole is reamed
+.0005/.0000 with a .4000 reamer and the hub land is turned +.0013/+.0009, so
the diametral interference runs .0004-.0013. A land band whose least
interference is .0000 (+.0010/+.0005 in this hole) goes together
line-to-line and is refused.
"""

from __future__ import annotations

STRAP_HOLE_BAND = (0.0127, 0.0)  # (upper, lower): +.0005/.0000
HUB_LAND_BAND = (0.03302, 0.02286)  # (upper, lower): +.0013/+.0009


def press_interference(
    land_band: tuple[float, float], hole_band: tuple[float, float]
) -> tuple[float, float]:
    """Diametral interference (least, greatest) of a land band in a hole band.

    The least is the smallest land in the largest hole, the greatest the
    largest land in the smallest hole. A press fit must interfere at both
    ends: a least of .0000 is a line-to-line pair that need not hold.
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


def _inch_text(value_mm: float) -> str:
    """``value_mm`` as four-place decimal-inch print text: ``.0004``."""
    return f"{value_mm / 25.4:.4f}".removeprefix("0")


# The callout row both prints carry under their Ø (drawing-guidelines.md rule 4:
# a tight band names its mate and why).
INTERFERENCE_TEXT = (
    f"{_inch_text(PRESS_INTERFERENCE[0])}-{_inch_text(PRESS_INTERFERENCE[1])}"
    " DIAMETRAL INTERFERENCE"
)
