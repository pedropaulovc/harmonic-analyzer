r"""Purchased transgear disc screw: McMaster 91794A055, 18-8 stainless (x3).

#0-80 x 1/4 slotted fillister, fully threaded (contract §2.6, ruling 4).
Each screw passes the brass hub's flange clearance hole (MHA-PD-017) and
threads into a #0-80 through tap in the 120T disc (MHA-PD-006).  CUT TO FIT
at assembly (R9-47): each tip is cut TIP_BELOW_REAR_FACE under the disc's
rear face and the cut end broken, so the part is modelled as installed:
CUT_LENGTH long with a CUT_END_BREAK_MAX 45 deg break.

Geometry source: the vendor-model replica ``diagnostics/diag_build_91794A055``
(replica-gated against the local-only harvest; no .SLDPRT committed), which
draws the cut directly (``build_91794A055(cut_length=..., cut_end_break=...)``):
the revolve profile ends the shank at the cut with the break in place of the
factory tip chamfer, as MHA-VN-040's ``build_transgear_arm_plate_screw`` does.

Frame: axis +Y, head up, the under-head bearing face at y = 0 (Top Plane);
the cut end is at y = -LENGTH (= -CUT_LENGTH).  The assembly mates the Top
Plane to the flange's front face and the screw axis (Front Plane ∩ Right
Plane) to a flange hole's axis.
"""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_91794A055 import build_91794A055
from vn_transgear_disc_screw_spec import (
    CUT_END_BREAK_MAX,
    CUT_LENGTH,
    SHANK_LEN,
    SKU,
    STOCK_LENGTH_BAND,
    TIP_CHAMFER,
)

PART_NAME = "vn-transgear-disc-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material
if SPEC.skus != (SKU,):
    raise AssertionError(f"{PART_NAME} catalogues {SPEC.skus}, not {SKU}")
# The modelled cut lies on full thread of every in-band supplied screw, so
# the break is the model's only end chamfer.
if SHANK_LEN - STOCK_LENGTH_BAND[1] - TIP_CHAMFER <= CUT_LENGTH:
    raise ValueError("the MHA-VN-039 cut does not clear the shortest stock's factory tip")


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku=SKU,
                author=build_91794A055,
                parameters={
                    "cut_length": CUT_LENGTH,
                    "cut_end_break": CUT_END_BREAK_MAX,
                },
            ),
        ),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
