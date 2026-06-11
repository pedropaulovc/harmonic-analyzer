r"""Reproduction script: channel spring, INSTALLED length (book ch. 17).

The p. 40-41 machine photos show the 20 channel springs visibly stretched
between the lever tabs and the summing-lever plate -- open coils, roughly
twice the free 32 mm body. This part is the same spring as
build_channel_spring.py (same wire, OD, coil count, hooks) at the
installed extension, so the channel assembly can hang it from the lever
tab eye (machine y 1063.65) to the plate hole eye (machine y 996.0):

    eye c2c  = 1063.65 - 996.0 = 67.65
    body     = c2c - 2 x hook lead = 67.65 - 4.0 = 63.65
    pitch    = 63.65 / 28 = 2.27 (open-wound, as photographed)

Dimensions: cad/DIMENSIONS.md ch. 17 + the M6.3/M6.4 channel layout
(lever tab hole at (-22.10, 1067.02), eye drop 3.37; plate top y 998,
eye centre 2.0 below the plate top).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_channel_spring_installed.py
"""

from __future__ import annotations

import sys

from _common import run_build
from build_channel_spring import EYE_C2C, HOOK_LEAD, build_spring

PART_NAME = "channel-spring-installed"

INSTALLED_EYE_C2C = 67.65  # lever tab eye 1063.65 -> plate eye 996.0 (derived)
INSTALLED_BODY_LENGTH = INSTALLED_EYE_C2C - 2.0 * HOOK_LEAD  # 63.65

assert INSTALLED_EYE_C2C > EYE_C2C, "installed spring must be stretched"


async def build(adapter) -> dict[str, str]:
    return await build_spring(adapter, PART_NAME, INSTALLED_BODY_LENGTH)


if __name__ == "__main__":
    sys.exit(run_build(build))
