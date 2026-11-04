r"""Purchased transgear retaining ring: McMaster 97431A240 (MHA-PD-VN-61, R9-68).

A side-mount (E-style) external ring for a 1/8 in shaft, pushed sideways
into the MHA-PD-23 pin's groove in front of the MHA-PD-25 front bushing, where it
closes the disc cluster's float.

The body is the catalogue recipe (diagnostics/diag_build_97431A240), built
about +Y at mid-thickness and turned so its axis is +Z with the rear face on
the Front plane (the frame ``pd_vn_transgear_retaining_ring_spec`` states).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_vn_transgear_retaining_ring.py
"""

from __future__ import annotations

import math
import sys

from _appearance import PANEL_BLACK
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_97431A240 import build_97431A240
from pd_vn_transgear_retaining_ring_spec import SKU, THICKNESS

PART_NAME = "pd-vn-transgear-retaining-ring"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material  # phosphate-coated carbon steel

# Rx(+90 deg) takes the recipe's +Y axis to +Z; the lift puts the rear face
# (the recipe's -Y face) on z = 0.
TRANSFORM = RigidTransform(
    translation_mm=(0.0, 0.0, THICKNESS / 2.0),
    rotation_radians=(math.pi / 2.0, 0.0, 0.0),
)


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(sku=SKU, author=build_97431A240, transform=TRANSFORM),
        ),
        material=MATERIAL,
        color=PANEL_BLACK,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
