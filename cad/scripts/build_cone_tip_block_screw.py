r"""Purchased cone tip block hold-down screw: McMaster 93075A150, zinc plated.

I31: one #6-32 x 5/8 in hex head screw rises from the swing platform's
counterbored slot (MHA-091), through the horseshoe shim pack (MHA-141) and
the tip block's foot-flange slot (MHA-092), into the MHA-146 nylon-insert
locknut on the flange top.  The counterbore slot is one hex width across, so
its walls hold the head: the nut is turned from the side and no wrench goes
under the plate.

Geometry source: the catalogue, not a vendor model.  The dimensions are the
McMaster product page for 93075A150 (read through Browserbase on 2026-09-25):
#6-32 UNC, 5/8 in under the head, hex head 1/4 in across flats x 3/32 in
high, ASME B18.6.3.  ``diagnostics/diag_build_93075A150.py`` builds them with
the 93075A* family laws (``diagnostics/diag_mcmaster_hex_head.py``), which
reproduce the laws ``diagnostics/diag_build_93075A194.py`` reads off the
vendor 93075A194 model and proves in its replica gate
(``diag_build_mcmaster.py 93075A194``).  This size has no replica gate of its
own; ``test_cone_tip_block_screw_drawing.py`` pins the catalogue dimensions
against the tip block's hold-down stack and proves the family builder issues
93075A194's recipe call for call.  No McMaster .SLDPRT is committed or used.

The 91255A148 button-head recipe this part used until I31
(``diagnostics/diag_build_91255A148.py``) stays in the McMaster replica fleet
only; no production part builds from it.

Frame: axis +Y, head up, the bearing face (the underside) at y = 0.
"""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_93075A150 import DIMS, build_93075A150

PART_NAME = "cone-tip-block-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

THREAD = "#6-32"
SHANK_DIA = DIMS.major_dia
THREAD_PITCH = DIMS.pitch
SHANK_LEN = DIMS.length
HEAD_AF = DIMS.head_af
HEAD_H = DIMS.head_h


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="93075A150",
                author=build_93075A150,
                transform=RigidTransform(translation_mm=(0.0, -DIMS.underside_y, 0.0)),
            ),
        ),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
