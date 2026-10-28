r"""Purchased MHA-SM-VN-53 knife-mount dowel: McMaster 98381A473.

A 1/8 x 3/4 alloy-steel dowel (``sm_vn_knife_mount_dowel_spec``), pressed chamfer
end first up to the floor of a blind ream in the MHA-FR-02 crossbar's faced
underside (owner ruling 2026-10-24, T+H3); its proud length slips into the
MHA-SM-02 knife mount's round hole or open slot and keys the mount against
turning about its MHA-SM-VN-52 screw.  The stock recipe
``diagnostics/diag_build_98381A473.py`` models the vendor model's chamfered
and rounded ends; its standalone run is the replica gate against the
user-supplied vendor model.

Frame: pin axis +Y, pressed end face at y = 0 (the Top Plane), lead end at
y = LENGTH.  The axis is published as ``ScrewAxis`` (Front ∩ Right), the
stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_sm_vn_knife_mount_dowel.py
"""

from __future__ import annotations

import sys
from functools import wraps

from _appearance import POLISHED_STEEL
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_pin_model import author_supplier_dowel_references
from diagnostics.diag_build_98381A473 import build_98381A473
from sm_vn_knife_mount_dowel_spec import SKU, SUPPLIER_REFERENCE

PART_NAME = "sm-vn-knife-mount-dowel"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


@wraps(build_98381A473)
async def _build_pin_with_supplier_references(adapter, truth=None):
    await build_98381A473(adapter, truth)
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
