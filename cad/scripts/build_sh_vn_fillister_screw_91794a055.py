r"""Build MHA-SH-VN-59: McMaster 91794A055 #0-80 x 1/4 fillisters, cut to fit (3 used).

Purchased 18-8 stainless slotted fillister, fully threaded (contract §2.6,
ruling 4; ``pd_transgear_disc_screw_spec``): three pass the brass hub's
flange clearance holes (MHA-PD-17) and thread into #0-80 through taps in the
reducer disc (MHA-PD-06). CUT TO FIT at assembly (R9-47): each tip is dressed
flush with the disc's rear face, modelled at CUT_LENGTH with a
CUT_END_BREAK_MAX 45 deg break via ``build_91794A055(cut_length=...,
cut_end_break=...)`` (the same direct profile route as
``build_pd_vn_transgear_arm_plate_screw``; the four stock-length rack screws
moved to MHA-PD-VN-72, 91794A060, in #3738).

Geometry source: the vendor-model replica ``diagnostics/diag_build_91794A055``
(replica-gated against the local-only harvest; no .SLDPRT committed).

Frame (the fillister family's): axis +Y, head up, the under-head bearing face
at y = 0 (Top Plane); the cut end at y = -CUT_LENGTH.
"""

from __future__ import annotations

import sys
from functools import partial

import _mcmaster_91794a055 as supplier
import pd_transgear_disc_screw_spec as disc
from _fastener_catalog import fastener
from _session import run_build
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_screw_save import save_supplier_reference_part
from diagnostics.diag_build_91794A055 import build_91794A055, shank_end

PART_NAME = "sh-vn-fillister-screw-91794a055"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material
SKU = supplier.SKU
if SPEC.skus != (SKU,):
    raise AssertionError(f"{PART_NAME} catalogues {SPEC.skus}, not {SKU}")
# The modelled cut lies on full thread of every in-band supplied screw, so
# the break is the cut screw's only end chamfer.
if (
    disc.SHANK_LEN - disc.STOCK_LENGTH_BAND[1] - disc.TIP_CHAMFER
    <= disc.CUT_LENGTH
):
    raise ValueError("the DiscScrew cut does not clear the shortest stock's factory tip")
shank_end(disc.CUT_LENGTH, disc.CUT_END_BREAK_MAX)


def build(adapter) -> dict[str, str]:
    return build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku=SKU,
                author=build_91794A055,
                parameters={
                    "cut_length": disc.CUT_LENGTH,
                    "cut_end_break": disc.CUT_END_BREAK_MAX,
                },
            ),
        ),
        material=MATERIAL,
        save_threaded_part=partial(
            save_supplier_reference_part,
            dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            starts=supplier.SUPPLIER_REFERENCE_STARTS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
        ),
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
