r"""Purchased MHA-DT-12-TL-VN-52 cam fixture clamp screw: McMaster 91251A337.

The ``10-32 X 5/16 SHCS`` (``dt_cylinder_gear_tl_vn_cam_clamp_screw_spec``)
that clamps each cylinder gear to the MHA-DT-12-TL-01 fixture through the
stub's tap. The stock recipe ``diagnostics/diag_build_91251A337.py`` builds
the catalogue screw on the 91251A family recipe
(``diag_mcmaster_socket_head.build_socket_head``), catalog-only.

Frame: screw axis +Y, head up, the bearing face (head underside) at y = 0,
the tip at y = -length. The axis is published as ``ScrewAxis``
(Front ∩ Right), the stock-part mate contract.

Run only through the supervised farm launcher:
``part:dt_cylinder_gear_tl_vn_cam_clamp_screw``.
"""

from __future__ import annotations

import sys
from functools import partial

import dt_cylinder_gear_tl_vn_cam_clamp_screw_spec as supplier
from _fastener_catalog import fastener
from _session import run_build
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_screw_save import save_supplier_reference_part
from diagnostics.diag_build_91251A337 import build_91251A337
from dt_cylinder_gear_tl_vn_cam_clamp_screw_spec import SKU

PART_NAME = "dt-cylinder-gear-tl-vn-cam-clamp-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_91251A337),),
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
