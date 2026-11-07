r"""Purchased MHA-DT-VN-69 locating pin: McMaster 98381A417.

A 1/16 x 3/8 alloy-steel dowel (``dt_vn_locating_pin_spec``); rule-23
retention, owner ruling 2026-11-07 (MHA-DT-00 rubric sample, PR #2248).
One, the tip-block locating dowel, locates the MHA-DT-21 cone tip block on
the MHA-DT-20 platform: pressed to the floor of the foot's blind .0620 ream,
a slip fit in the plate's .0630 thru ream, match-drilled at MHA-DT-00 step 2.
The stock recipe ``diagnostics/diag_build_98381A417.py`` models the nominal
cylinder, catalogue-only (no vendor model).

Frame: pin axis +Y, pressed end face at y = 0 (the Top Plane), lead end at
y = LENGTH.  The axis is published as ``ScrewAxis`` (Front ∩ Right), the
stock-part mate contract the assembly keys it by.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_vn_locating_pin.py
"""

from __future__ import annotations

import sys
from functools import wraps

from _appearance import POLISHED_STEEL
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_pin_model import author_supplier_dowel_references
from dt_vn_locating_pin_spec import SKU, SUPPLIER_REFERENCE
from diagnostics.diag_build_98381A417 import build_98381A417

PART_NAME = "dt-vn-locating-pin"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


@wraps(build_98381A417)
async def _build_pin_with_supplier_references(adapter, truth=None):
    await build_98381A417(adapter, truth)
    await author_supplier_dowel_references(adapter, SUPPLIER_REFERENCE)


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=_build_pin_with_supplier_references),),
        material=MATERIAL,
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
