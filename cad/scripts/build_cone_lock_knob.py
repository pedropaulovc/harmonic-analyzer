r"""Purchased cone lock knob: McMaster 91882A412 in its stock local frame."""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_91882A412 import build_91882A412
from diagnostics.diag_mcmaster_thumb import THUMB_SPECS

PART_NAME = "cone-lock-knob"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

THREAD = "1/4-20"
_LOCK = THUMB_SPECS["91882A412"]
COLLAR_DIA = 2.0 * _LOCK["collar_r"]
HEAD_DIA = 2.0 * _LOCK["head_r"]
HEAD_H = _LOCK["collar_h"] + _LOCK["head_h"]
SHANK_DIA = 2.0 * _LOCK["major_r"]
SHANK_LEN = _LOCK["length"]
STUD_DIA = 2.0 * _LOCK["major_r"]
STUD_LEN = _LOCK["length"]
WASHER_DIA = 2.0 * _LOCK["collar_r"]


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="91882A412",
                author=build_91882A412,
                transform=RigidTransform(),
            ),
        ),
        material=MATERIAL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
