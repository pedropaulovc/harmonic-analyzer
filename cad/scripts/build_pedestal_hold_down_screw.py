r"""Purchased arbor-pedestal hold-down screw: McMaster 90280A197, black.

U34c: one #8-32 x 3/4 in slotted fillister holds each arbor pedestal
(MHA-004) through its ledge hole into a base seat transferred from that hole
at assembly (ch12 p.18 img09 shows the single dark slotted head on the
flange). The machine's black finish matches the dark heads in the photos.
"""

from __future__ import annotations

import sys

from _common import PANEL_BLACK, run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_90280A197 import build_90280A197
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

PART_NAME = "pedestal-hold-down-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

THREAD = "#8-32"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, _PITCH = FILLISTER_SIZES["90280A197"]


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="90280A197",
                author=build_90280A197,
                transform=RigidTransform(),
            ),
        ),
        material=MATERIAL,
        color=PANEL_BLACK,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
