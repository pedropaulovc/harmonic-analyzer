r"""Purchased MHA-CH-13-TL-VN-52 hub washer: McMaster 96659A104.

The #10 SAE flat washer (``ch_rocker_strap_tl_vn_hub_washer_spec``; owner
rulings 2026-11-23) under the MHA-CH-13-TL-VN-51 hub screw's head, on the
strap blank round its hub hole. One washer picked by measurement from the
owned pack and kept with the fixture. Tier 1: HARDWARE.md carries it, no
drawing. The stock recipe ``diagnostics/diag_build_96659A104.py`` builds the
catalogue annulus (catalog-only, no vendor model), shared with the machine's
MHA-SM-VN-54; this is the fixture's own identity, never in a machine
assembly or BOM.

Frame: the recipe is built about +Y and turned so its axis is +Z: z = 0 the
face on the strap, the face under the screw head at z = THICKNESS. The axis
is published as ``ScrewAxis`` (Top ∩ Right), the stock-part mate contract.

Run only through the supervised farm launcher:
``part:ch_rocker_strap_tl_vn_hub_washer``.
"""

from __future__ import annotations

import math
import sys

from _fastener_catalog import fastener
from _mcmaster_96659a104 import DIMS
from _session import run_build
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_96659A104 import build_96659A104

# The catalogue module, not the washer spec: the spec imports the hub
# screw's catalogue for its reach checks, which would re-key this build.
SKU = DIMS.part_no

PART_NAME = "ch-rocker-strap-tl-vn-hub-washer"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

# Rx(+90 deg) takes the recipe's +Y axis to +Z; the bottom face (y = 0)
# stays on z = 0.
TRANSFORM = RigidTransform(rotation_radians=(math.pi / 2.0, 0.0, 0.0))


def build(adapter) -> dict[str, str]:
    return build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(sku=SKU, author=build_96659A104, transform=TRANSFORM),
        ),
        material=MATERIAL,
        screw_axis_planes=("Top Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
