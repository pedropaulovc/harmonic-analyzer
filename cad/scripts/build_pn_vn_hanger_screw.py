"""Build the hanger screw from McMaster 93075A199 (#8-32 x 1")."""

from __future__ import annotations

import math
import sys
from functools import partial

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _supplier_screw_save import save_supplier_reference_part
from _mcmaster_93075a199 import (
    HX_UNDERSIDE,
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_STARTS,
    SUPPLIER_REFERENCE_PLANES,
)
from diagnostics.diag_build_93075A199 import build_93075A199

PART_NAME = "pn-vn-hanger-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                "93075A199",
                build_93075A199,
                RigidTransform(
                    translation_mm=(0.0, 0.0, -HX_UNDERSIDE),
                    rotation_radians=(math.pi / 2.0, 0.0, 0.0),
                ),
            ),
        ),
        material=MATERIAL,
        save_threaded_part=partial(
            save_supplier_reference_part,
            dimensions=SUPPLIER_REFERENCE_DIMENSIONS,
            starts=SUPPLIER_REFERENCE_STARTS,
            planes=SUPPLIER_REFERENCE_PLANES,
        ),
        screw_axis_planes=("Top Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
