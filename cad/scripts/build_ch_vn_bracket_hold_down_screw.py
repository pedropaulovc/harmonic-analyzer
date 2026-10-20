r"""Purchased rocker-bracket hold-down screw: McMaster 90280A196, black.

Owner Q13c: one #8-32 x 5/8 in slotted narrow fillister holds each MHA-CH-08
pivot-bracket foot down into the #8-32 seat transferred into MHA-FR-05's top
face at assembly. The 5/8 length (not the arbor pedestals' 3/4 MHA-DT-VN-62)
keeps that seat at 11.5 thread / 14.7 drill depth. Black like MHA-DT-VN-62.
"""

from __future__ import annotations

import sys

from _appearance import PANEL_BLACK
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _simplified_part import save_simplified_part
from diagnostics.diag_build_90280A196 import build_90280A196

PART_NAME = "ch-vn-bracket-hold-down-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="90280A196",
                author=build_90280A196,
                transform=RigidTransform(),
            ),
        ),
        material=MATERIAL,
        save_threaded_part=save_simplified_part,
        color=PANEL_BLACK,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
