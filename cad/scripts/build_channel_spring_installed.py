r"""Reproduction script: channel spring, INSTALLED length (book ch. 17).

The p. 40-41 machine photos show the 20 channel springs visibly stretched
between the lever tabs and the summing-lever plate -- open coils, roughly
twice the free 32 mm body. This part is the same spring as
build_channel_spring.py (same wire, OD, coil count) at the installed
extension. The bottom does NOT thread through the plate: a separate little
open hook fastener (build_spring_hook.py) seats in the plate's O2.0 bore and
the spring's bottom eye links onto its arm just ABOVE the plate. So the bottom
lead is a normal short hook lead (symmetric with the top), not a plate-spanning
one, and the bottom eye sits above the plate:

    top eye centre    1063.15  (lever spring hole 1066.52 - drop 3.37)
    bottom eye centre  996.54  (on the hook arm; its O5.5 ring bottom 993.29
                                clears the plate top 992.54 by 0.75)
    coil body bottom   998.54  (bottom eye + 2.0 bottom lead)
    body = 1063.15 - 2.0 (top lead) - 998.54             = 62.61
    bottom lead                                          = 2.0

    The plate is the coplanar .cs casting (top 992.54, see build_summing_lever).
    The top eye is the LIVE neutral lever spring hole (OD-62.2 re-anchor): the
    lever pivots about FULCRUM=(-199.9, 1065.9) with the spring hole 177.8 out
    along the arm, so at the 0.20 deg neutral tilt the hole sits at 1066.52, NOT
    the pre-re-anchor 1067.02 -- the eye is 0.50 lower. build_channel_assembly is
    the authority: its verify:math gate (spring:neutral-body-canonical) fails loud
    if this drifts from the solver's neutral gap, so neutral always mates this one
    canonical body x20 instead of spawning a stretch variant.

The bottom eye is on the spring axis now (the hook reaches +X to it, not the
spring reaching down through the plate), so the summing-lever plate holes are
coaxial with the spring axis in Z (z_j + 0.8) and shifted one arm-offset -X to
seat the hook shank (see build_summing_lever.py and build_channel_assembly.py).

Dimensions: cad/DIMENSIONS.md ch. 17 + ch. 18 (M6.4).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_channel_spring_installed.py
"""

from __future__ import annotations

import sys

from _common import run_build
from _spring import COIL_BODY_LENGTH, HOOK_LEAD, build_spring

PART_NAME = "channel-spring-installed"

LEVER_EYE_Y = 1063.25  # LIVE neutral top eye = lever spring hole 1066.62 - drop
# 3.37 (ch30 GT re-anchor: the corrected rocker lever angle nudged the neutral
# lever tilt to 0.231 deg, lifting the eye 0.10; was 1063.15 at the OD-62.2
# re-anchor). The assembly's solve_state is the authority --
# verify:math spring:neutral-body-canonical guards this value.
PLATE_EYE_Y = 996.54  # bottom eye centre, ABOVE the .cs plate (top 992.54) on the
# spring-hook arm: plate bottom 987.44 + hook arm height (SHANK_RISE 7.6 + ELBOW_R
# 1.5 = 9.1). High enough that the eye's O5.5 ring clears the plate (its bottom
# 993.29 > 992.54). The spring no longer threads the plate -- the hook bridges it.
TOP_LEAD = HOOK_LEAD  # 2.0
BOTTOM_LEAD = HOOK_LEAD  # 2.0: normal hook lead (no longer spans the plate)
INSTALLED_BODY_LENGTH = LEVER_EYE_Y - PLATE_EYE_Y - TOP_LEAD - BOTTOM_LEAD  # 68.01
TOP_EYE_LOCAL_Y = INSTALLED_BODY_LENGTH + TOP_LEAD  # 70.01 above the part origin

assert INSTALLED_BODY_LENGTH > COIL_BODY_LENGTH, "installed spring must be stretched"


async def build(adapter) -> dict[str, str]:
    return await build_spring(
        adapter, PART_NAME, INSTALLED_BODY_LENGTH, leads=(BOTTOM_LEAD, TOP_LEAD),
        eye_axes=True,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
