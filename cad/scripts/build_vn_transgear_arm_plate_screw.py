r"""Purchased transgear arm-plate screws: McMaster 91790A196, 18-8 stainless,
cut to fit.

8-32 x 5/8 slotted 82 deg oval head, fully threaded, the length measured from
the top of the bevel (contract §3.3); the SKU is [INFERENCE], not yet read
live (``vn_transgear_arm_plate_screw_spec``).  Two of them hold the arm plate
(MHA-PD-019) on the arm (MHA-PD-018): each head sits flush in one of the plate's
82 deg countersinks and the shank runs through the plate's Ø4.5 clearance
hole into the arm's #8-32 through tap.  At assembly each tip is cut flush
with the arm's front face and the cut end broken (R9-44), so the part is
modelled as installed: CUT_LENGTH long with a CUT_END_BREAK_MAX 45 deg break.

Modelling route: the shared oval recipe draws the cut directly
(``build_91790A196(cut_length=..., cut_end_break=...)``): the revolve profile
ends the shank at the cut with the break in place of the factory 0.7P tip
chamfer, and the recipe's analytic revolved-volume check follows the cut.
MHA-VN-031 (``build_vn_post_mount_screw``) instead builds the supplied screw and
trims it with a cut-extrude, a deburr revolve-cut, equation-driven reference
sketches and B-rep rim reads, because its sheet dimensions the cut length
and the break from model dimensions.  This sheet prints neither (the
installation note states the cut), so that machinery buys nothing here and
every one of its COM calls would be unexercised native risk; the profile
route adds no COM call to the stock build and leaves the supplied-screw
catalog run unchanged.  The parameters ride ``StockComponent.parameters``
to the registered recipe, as ``build_vn_cone_tip_collar`` passes its seated cup.

Geometry source: the live McMaster pages of the series, not a vendor model
(``diagnostics/diag_mcmaster_oval.py``; no replica gate, no .SLDPRT
committed).

Frame: axis +Y, head up, the top of the bevel at y = 0 (Top Plane), the
plane that sits flush with the plate's rear face; the crown rises above it
and the cut end is at y = -LENGTH (= -CUT_LENGTH).  The assembly mates the
Top Plane to the plate's ``RearFace`` plane and the screw axis (Front Plane ∩
Right Plane) to the plate's screw-hole axis.
"""

from __future__ import annotations

import sys

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from _simplified_part import save_simplified_part
from diagnostics.diag_build_91790A196 import build_91790A196
from diagnostics.diag_mcmaster_oval import TIP_CHAMFER_PER_PITCH
from vn_transgear_arm_plate_screw_spec import (
    CUT_END_BREAK_MAX,
    CUT_LENGTH,
    PITCH,
    SKU,
    STOCK_LENGTH,
    STOCK_LENGTH_BAND,
)

PART_NAME = "vn-transgear-arm-plate-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

# Every in-band supplied screw is cut on full thread, so the cut removes the
# whole factory tip and the break is the only end chamfer.
if STOCK_LENGTH - STOCK_LENGTH_BAND[1] - TIP_CHAMFER_PER_PITCH * PITCH <= CUT_LENGTH:
    raise ValueError("the MHA-VN-040 cut does not clear the shortest stock's factory tip")


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku=SKU,
                author=build_91790A196,
                parameters={
                    "cut_length": CUT_LENGTH,
                    "cut_end_break": CUT_END_BREAK_MAX,
                },
            ),
        ),
        material=MATERIAL,
        save_threaded_part=save_simplified_part,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
