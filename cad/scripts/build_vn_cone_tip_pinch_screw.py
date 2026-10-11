r"""Purchased cone tip pinch screw: McMaster 91794A112 in its stock local frame."""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _simplified_part import save_simplified_part
from diagnostics.diag_build_91794A112 import build_91794A112
from _mcmaster_91794a112 import SKU

PART_NAME = "vn-cone-tip-pinch-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

if SPEC.skus != (SKU,):
    raise AssertionError(f"{PART_NAME} catalogues {SPEC.skus}, not {SKU}")


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku=SKU,
                author=build_91794A112,
                transform=RigidTransform(),
            ),
        ),
        material=MATERIAL,
        save_threaded_part=save_simplified_part,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
