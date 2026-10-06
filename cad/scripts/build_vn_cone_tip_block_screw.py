r"""Purchased cone tip block hold-down screw: McMaster 91251A108, black oxide.

User ruling 2026-09-29 (photo
``references/albert-michelsons-harmonic-analyzer/eight-views-4.png``, lower
right): the cone tip block (MHA-DT-021) stands directly on the cone swing
platform (MHA-DT-020), held by one socket head cap screw rising from under the
platform through its counterbored clearance hole (counterbore on the
underside) into a blind #4-40 tapped hole in the block's bottom face.

Geometry source: the catalogue, not a vendor model.  The dimensions are the
McMaster product page for 91251A108 (read in a headless browser on
2026-09-29): #4-40 UNC-3A, 3/8 in under the head, fully threaded, socket head
Ø0.183 in x 0.112 in high, 3/32 in hex drive, black-oxide alloy steel, ASTM
A574.  ``diagnostics/diag_build_91251A108.py`` builds them; it has no replica
gate, and no McMaster .SLDPRT is committed or used.

Frame: axis +Y, head up, the bearing face (the underside) at y = 0.
"""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_91251A108 import build_91251A108

PART_NAME = "vn-cone-tip-block-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(sku="91251A108", author=build_91251A108),
        ),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
