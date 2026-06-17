r"""Reproduction script: channel spring, INSTALLED length (book ch. 17).

The p. 40-41 machine photos show the 20 channel springs visibly stretched
between the lever tabs and the summing-lever plate -- open coils, roughly
twice the free 32 mm body. This part is the same spring as
build_channel_spring.py (same wire, OD, coil count) at the installed
extension, with an asymmetric BOTTOM lead: the bottom attachment passes
the straight lead wire down through the plate's O4.5 hole with the end
loop hanging under the plate (the loop is too small to thread the 5.1
plate edge-wise), so the lead must span the plate thickness:

    top eye centre    1063.65  (lever tab hole 1067.02 - drop 3.37)
    coil body bottom   993.14  (corrected .cs plate top 992.54 + 0.6 clearance)
    bottom eye centre  984.04  (loop top 987.39, plate bottom 987.44)
    body = 1063.65 - 2.0 (top lead) - 993.14             = 68.51
    bottom lead = 993.14 - 984.04                        = 9.1

    The plate is the coplanar .cs casting (top 992.54, see build_summing_lever);
    that is 5.46 BELOW the old M6.4 998, so the installed body grew 63.05 -> 68.51
    against the fixed channel-lever tab at 1063.65.

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
from build_channel_spring import COIL_BODY_LENGTH, HOOK_LEAD, build_spring

PART_NAME = "channel-spring-installed"

LEVER_EYE_Y = 1063.65  # machine: top eye centre (M6.3 layout)
PLATE_EYE_Y = 984.04  # machine: bottom eye centre, under the corrected .cs plate
# (dropped 5.46 from the old 989.5 -- the coplanar plate sits at 987.44..992.54)
TOP_LEAD = HOOK_LEAD  # 2.0
BOTTOM_LEAD = 9.1  # spans the 5.1 plate + clearances (see docstring)
INSTALLED_BODY_LENGTH = LEVER_EYE_Y - PLATE_EYE_Y - TOP_LEAD - BOTTOM_LEAD  # 63.05
TOP_EYE_LOCAL_Y = INSTALLED_BODY_LENGTH + TOP_LEAD  # 65.05 above the part origin

assert INSTALLED_BODY_LENGTH > COIL_BODY_LENGTH, "installed spring must be stretched"


async def build(adapter) -> dict[str, str]:
    return await build_spring(
        adapter, PART_NAME, INSTALLED_BODY_LENGTH, leads=(BOTTOM_LEAD, TOP_LEAD)
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
