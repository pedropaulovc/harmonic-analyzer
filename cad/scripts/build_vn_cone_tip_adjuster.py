r"""Native stock build of the McMaster 94025A164 #10-32 cup-point adjuster.

Its conical apex is the thrust contact. Geometry-data consumers read
``vn_cone_tip_adjuster_spec`` directly, never this native build wrapper.
"""

from __future__ import annotations

import sys
from math import pi

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_94025A164 import build_94025A164
from vn_cone_tip_adjuster_spec import SS_HALF

PART_NAME = "vn-cone-tip-adjuster"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="94025A164",
                author=build_94025A164,
                transform=RigidTransform(
                    translation_mm=(0.0, SS_HALF, 0.0),
                    rotation_radians=(pi, 0.0, 0.0),
                ),
            ),
        ),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
