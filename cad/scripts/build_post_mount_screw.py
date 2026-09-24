r"""Purchased cone pivot post mount screw: MSC 40923898 in its stock local frame.

Head up, under-head junction at the origin: the head seats on the MHA-016
counterbore floor and the shank runs down through the post into the
MHA-091 tap.  Modelled at the 86.0 cut-to-fit nominal (U37c).
"""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_40923898 import build_40923898
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

PART_NAME = "post-mount-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

THREAD = "1/4-20"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, THREAD_PITCH = FILLISTER_SIZES["40923898"]


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="40923898",
                author=build_40923898,
                transform=RigidTransform(),
            ),
        ),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
