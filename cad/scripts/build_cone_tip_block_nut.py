r"""Purchased cone tip block hold-down nut: McMaster 90631A007, zinc plated.

I31: the #6-32 nylon-insert locknut that holds the tip block down.  It sits
on the top of the block's foot flange (MHA-092) over the flange slot and
takes the MHA-140 hex head screw rising from under the swing platform; it is
turned from the side with an open-end wrench while the platform's
counterbore slot holds the screw head.

Geometry source: the catalogue, not a vendor model.  The McMaster product
page for 90631A007 (read through Browserbase on 2026-09-25) gives #6-32,
5/16 in across flats and 11/64 in high, and nothing else;
``diagnostics/diag_build_90631A007.py`` builds that envelope, a sharp hex
prism bored at the #6-32 tap drill, and checks its volume against the closed
form.  No McMaster .SLDPRT is committed or used.

Frame: axis +Y, the bearing face at y = 0, the nut above it.
"""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics import diag_build_90631A007 as recipe
from diagnostics.diag_build_90631A007 import build_90631A007

PART_NAME = "cone-tip-block-nut"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

THREAD = recipe.THREAD
NUT_AF = recipe.NUT_AF
NUT_AC = recipe.NUT_AC
NUT_H = recipe.NUT_H
BORE_DIA = recipe.BORE_DIA


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="90631A007",
                author=build_90631A007,
                transform=RigidTransform(translation_mm=(0.0, NUT_H / 2.0, 0.0)),
            ),
        ),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
