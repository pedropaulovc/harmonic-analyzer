r"""Reproduction script: channel spring, INSTALLED length (book ch. 17).

The p. 40-41 machine photos show the 20 channel springs visibly stretched
between the lever tabs and the summing-lever plate -- open coils, roughly
twice the free 32 mm body. This part is the same spring as
build_channel_spring.py (same wire, OD, coil count) at the installed
extension, with an asymmetric BOTTOM lead: the bottom attachment passes
the straight lead wire down through the plate's O4.5 hole with the end
loop hanging under the plate (the loop is too small to thread the 5.1
plate edge-wise), so the lead must span the plate thickness:

    top eye centre    1063.15  (lever spring hole 1066.52 - drop 3.37)
    coil body bottom   993.05  (corrected .cs plate top 992.54 + 0.51 clearance)
    bottom eye centre  984.04  (loop top 987.39, plate bottom 987.44)
    body = 1063.15 - 2.0 (top lead) - 993.05             = 68.01
    bottom lead = 993.05 - 984.04                        = 9.1

    The plate is the coplanar .cs casting (top 992.54, see build_summing_lever).
    The top eye is the LIVE neutral lever spring hole (OD-62.2 re-anchor): the
    lever pivots about FULCRUM=(-199.9, 1065.9) with the spring hole 177.8 out
    along the arm, so at the 0.20 deg neutral tilt the hole sits at 1066.52, NOT
    the pre-re-anchor 1067.02 -- the eye is 0.50 lower, the installed body 68.01
    (was a stale 68.51). build_channel_assembly is the authority: its
    verify:math gate (spring:neutral-body-canonical) fails loud if this drifts
    from the solver's neutral gap, so neutral always mates this one canonical
    body x20 instead of spawning a stretch variant.

The lead sits one coil mean radius (2.75) off the spring axis on the
helix-start side; after the assembly's Ry(+90) that is -Z, which is why
the summing-lever plate holes sit at z_j - 1.95 (see
build_summing_lever.py and build_channel_assembly.py).

Dimensions: cad/DIMENSIONS.md ch. 17 + ch. 18 (M6.4).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_channel_spring_installed.py
"""

from __future__ import annotations

import sys

from _common import run_build
from _spring import COIL_BODY_LENGTH, HOOK_LEAD, build_spring

PART_NAME = "channel-spring-installed"

LEVER_EYE_Y = 1063.15  # LIVE neutral top eye = lever spring hole 1066.52 - drop
# 3.37 (OD-62.2 re-anchor; was a stale 1063.65). The assembly's solve_state is
# the authority -- verify:math spring:neutral-body-canonical guards this value.
PLATE_EYE_Y = 984.04  # machine: bottom eye centre, under the corrected .cs plate
# (dropped 5.46 from the old 989.5 -- the coplanar plate sits at 987.44..992.54)
TOP_LEAD = HOOK_LEAD  # 2.0
BOTTOM_LEAD = 9.1  # spans the 5.1 plate + clearances (see docstring)
INSTALLED_BODY_LENGTH = LEVER_EYE_Y - PLATE_EYE_Y - TOP_LEAD - BOTTOM_LEAD  # 68.01
TOP_EYE_LOCAL_Y = INSTALLED_BODY_LENGTH + TOP_LEAD  # 70.01 above the part origin

assert INSTALLED_BODY_LENGTH > COIL_BODY_LENGTH, "installed spring must be stretched"


async def build(adapter) -> dict[str, str]:
    return await build_spring(
        adapter, PART_NAME, INSTALLED_BODY_LENGTH, leads=(BOTTOM_LEAD, TOP_LEAD)
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
