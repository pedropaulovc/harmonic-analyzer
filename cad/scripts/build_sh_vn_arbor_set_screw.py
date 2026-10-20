r"""Shared McMaster 91375A106 alloy-steel cup-point set screw (MHA-SH-VN-54).

The C45 black-oxide cup point bites the spotted steel arbor or shaft flat.
The vendor replica is lifted so the cup end sits at y = 0 and the socket
face at the unchanged stock length; consumers read dimensions from the pure
``sh_vn_arbor_set_screw_spec`` rather than importing this native recipe.
"""

from __future__ import annotations

import sys

from _appearance import PANEL_BLACK
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _simplified_part import save_simplified_part
from diagnostics.diag_build_91375A106 import HALF, build_91375A106

PART_NAME = "sh-vn-arbor-set-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material  # alloy steel, black oxide


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="91375A106",
                author=build_91375A106,
                transform=RigidTransform(translation_mm=(0.0, HALF, 0.0)),
            ),
        ),
        material=MATERIAL,
        save_threaded_part=save_simplified_part,
        color=PANEL_BLACK,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
