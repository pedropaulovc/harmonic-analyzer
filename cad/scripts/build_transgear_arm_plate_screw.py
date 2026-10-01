r"""Purchased transgear arm-plate screws: McMaster 91790A194, 18-8 stainless.

8-32 x 1/2 slotted 82 deg oval head, fully threaded, the length measured from
the top of the bevel (contract §3.3).  Two of them hold the arm plate
(MHA-165) on the arm (MHA-164): each head sits flush in one of the plate's
82 deg countersinks and the shank runs through the plate's Ø4.4 clearance
hole into the arm's #8-32 through tap.

Geometry source: the live McMaster pages, not a vendor model
(``diagnostics/diag_mcmaster_oval.py``; no replica gate, no .SLDPRT
committed).

Frame: axis +Y, head up, the top of the bevel at y = 0 (Top Plane), the
plane that sits flush with the plate's rear face; the crown rises above it
and the tip is at y = -LENGTH.  The assembly mates the Top Plane to the
plate's ``RearFace`` plane and the screw axis (Front Plane ∩ Right Plane)
to the plate's screw-hole axis.
"""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_91790A194 import build_91790A194
from transgear_arm_plate_screw_spec import SKU

PART_NAME = "transgear-arm-plate-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_91790A194),),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
