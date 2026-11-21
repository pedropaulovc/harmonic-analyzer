r"""The press fit that joins the built-up rocker arm's hub to its strap.

PURE DATA, no SolidWorks/COM imports. MHA-CH-06 may be built up (its
``ch_rocker_arm_notes.BUILT_UP_PERMISSION_NOTE``): the turned hub MHA-CH-12
is pressed into the Ø.400 hole of the flat strap MHA-CH-13. Both detail
builds and their drawing tests import this one module, so the hole's band and
the interference the land is turned to are stated once.

User ruling (route v3, 2026-10-16): a press fit. #290 states it in inch on
the .400 nominal (``ch_rocker_arm_spec.HUB_DIA``): the strap hole is reamed
+.0005/.0000 with a .4000 reamer, and the diametral interference runs
.0004-.0013.

Owner ruling 2026-11-21 (tight-tolerance audit, row 1): "matched fit only".
The land prints as the Ø.400 reference with the interference, turned to the
measured strap hole: the land's own .4009-.4013 band (the interference held
against every hole in the reamed band, .0004 wide) is gone, so each land
takes the .0009 the interference leaves over its own hole. A fit whose least
interference is .0000 goes together line-to-line and is refused.
"""

from __future__ import annotations

STRAP_HOLE_BAND = (0.0127, 0.0)  # (upper, lower): +.0005/.0000
PRESS_INTERFERENCE = (0.01016, 0.03302)  # diametral (least, greatest): .0004-.0013


def land_range(
    interference: tuple[float, float], hole_band: tuple[float, float]
) -> tuple[float, float]:
    """The land's (least, greatest) deviation over the hole's nominal across
    every hole in ``hole_band``, each land turned to its own measured hole.

    The least is the smallest hole plus the least interference, the greatest
    the largest hole plus the greatest. A press fit must interfere at both
    ends: a least interference of .0000 is a line-to-line pair that need not
    hold.
    """
    least, greatest = interference
    if not 0.0 < least < greatest:
        raise AssertionError(
            f"the hub land can go in the strap hole line-to-line or loose: "
            f"{interference}"
        )
    return round(hole_band[1] + least, 6), round(hole_band[0] + greatest, 6)


# .4004-.4018 over every hole the reamed band admits (the hub's supply wall
# and its bar take the extremes).
LAND_RANGE = land_range(PRESS_INTERFERENCE, STRAP_HOLE_BAND)
