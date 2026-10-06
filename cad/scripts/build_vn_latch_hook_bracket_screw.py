r"""Purchased MHA-VN-043 latch-hook bracket screw: McMaster 90280A108.

The foot-screw SKU (#4-40 x 3/8 slotted narrow fillister, zinc plated) in
its as-bought finish; ``vn_latch_hook_bracket_screw_spec`` owns the joint.
Frame: head up, under-head junction at y = 0, ``ScrewAxis`` = Front ∩ Right.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_vn_latch_hook_bracket_screw.py
"""

from __future__ import annotations

import sys

from _common import POLISHED_STEEL, run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_90280A108 import build_90280A108
from vn_latch_hook_bracket_screw_spec import SKU

PART_NAME = "vn-latch-hook-bracket-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(sku=SKU, author=build_90280A108, transform=RigidTransform()),
        ),
        material=MATERIAL,
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
