r"""Purchased MHA-VN-024 knife-hanger screw: McMaster 91251A157, black oxide.

A #6-32 x 1-1/2 socket head cap screw (``vn_knife_hanger_stud_spec``) dropped
through the MHA-FR-002 crossbar's counterbore, its head on the counterbore
floor, threading into the bottoming tap in the MHA-SM-002 knife mount's top
seat and drawing the seat up against the crossbar underside.

Geometry source: the catalogue, not a vendor model.
``diagnostics/diag_build_91251A157.py`` builds it on the shared socket-head
recipe, partially threaded (3/4 in minimum thread from the tip, plain shank
above); it has no replica gate, and no McMaster .SLDPRT is committed or used.

Frame: axis +Y, thread tip at y = 0, under-head (bearing) face at
y = LENGTH.  The recipe puts the bearing face at y = 0 and the tip at
-LENGTH, so the component is lifted LENGTH up +Y.  Consumers read the
screw's dimensions from ``vn_knife_hanger_stud_spec``, not from this build.
"""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_91251A157 import build_91251A157
from vn_knife_hanger_stud_spec import LENGTH, SKU

PART_NAME = "vn-knife-hanger-stud"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                SKU,
                build_91251A157,
                RigidTransform(translation_mm=(0.0, LENGTH, 0.0)),
            ),
        ),
        material=MATERIAL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
