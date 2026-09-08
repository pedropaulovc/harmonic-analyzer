"""Build the 1/2-13 UNC-2A hold-down screw from McMaster 91783A722.

The supplier's downloaded SLDPRT uses a 0.453571 mm visual helix, not the
catalog's nominal 25.4/13 mm thread pitch. Preserve that vendor representation
without treating its visual grooves as a manufacturing thread specification.
The receiving foot must be tapped 1/2-13 UNC-2B.
"""

from __future__ import annotations

import math
import sys

from _common import PANEL_BLACK, run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_91783A722 import (
    RH_HEAD_R,
    RH_HH,
    RH_LEN,
    RH_MAJOR_R,
    RH_THREAD_LEN,
    build_91783A722,
)

PART_NAME = "lag-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

HEAD_DIA = 2.0 * RH_HEAD_R
HEAD_H = RH_HH
SHANK_DIA = 2.0 * RH_MAJOR_R
SHANK_LEN = RH_LEN
THREAD_LEN = RH_THREAD_LEN  # supplier minimum threaded length
THREAD_SIZE = "1/2-13"  # authenticated McMaster 91783A722 catalog designation
THREAD_CLASS = "2A"
THREAD_PITCH = 25.4 / 13.0  # nominal purchased thread, NOT the vendor visual helix


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                "91783A722",
                build_91783A722,
                RigidTransform(rotation_radians=(math.pi, 0.0, 0.0)),
            ),
        ),
        material=MATERIAL,
        color=PANEL_BLACK,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
