r"""Purchased MHA-VN-051 knife-mount dowel: McMaster 98381A473.

A 1/8 x 3/4 alloy-steel dowel (``vn_knife_mount_dowel_spec``), pressed chamfer
end first to the floor of the blind reamed hole in the MHA-SM-002 knife
mount's top seat; its proud length slips into the blind hole in the MHA-FR-002
crossbar underside and keys the mount against turning about its MHA-VN-024
screw.  The stock recipe ``diagnostics/diag_build_98381A473.py`` models the
vendor model's chamfered and rounded ends; its standalone run is the replica
gate against the user-supplied vendor model.

Frame: pin axis +Y, pressed end face at y = 0 (the Top Plane), lead end at
y = LENGTH.  The axis is published as ``ScrewAxis`` (Front ∩ Right), the
stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_vn_knife_mount_dowel.py
"""

from __future__ import annotations

import sys

from _common import POLISHED_STEEL, run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_98381A473 import build_98381A473
from vn_knife_mount_dowel_spec import SKU

PART_NAME = "vn-knife-mount-dowel"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_98381A473),),
        material=MATERIAL,
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
