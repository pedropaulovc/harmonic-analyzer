r"""Purchased arbor-pedestal hold-down screw: McMaster 90280A197, black.

U34c: one #8-32 x 3/4 in slotted fillister holds each arbor pedestal
(MHA-DT-002) through its ledge hole into a base seat transferred from that hole
at assembly (ch12 p.18 img09 shows the single dark slotted head on the
flange). The machine's black finish matches the dark heads in the photos.
"""

from __future__ import annotations

import sys

from _appearance import PANEL_BLACK
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _simplified_part import save_simplified_part
from diagnostics.diag_build_90280A197 import build_90280A197

PART_NAME = "vn-pedestal-hold-down-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


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
        save_threaded_part=save_simplified_part,
        color=PANEL_BLACK,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
