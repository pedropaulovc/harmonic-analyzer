r"""Build purchased MHA-VN-071: the crank seat shim pack, axis +Y, y 0..T.

The modelled pack is ``vn_crank_seat_shim_spec.PACK``, the one selected for
the nominal crank-seat gap: one McMaster 3088A 12 x 18 mm ring shim per
entry, thickest on the collar face.  Each stock recipe extrudes its annulus
as a new body at y = 0..t; every shim after the first is moved +Y onto the
one before, so the pack's collar face is the Top Plane (y = 0) and its boss
face y = THICKNESS.  The axis is published as ``ScrewAxis`` (Front ∩ Right),
the stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_vn_crank_seat_shim.py
"""

from __future__ import annotations

import sys

from _fastener_catalog import fastener
from _session import run_build
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_3088A006 import build_3088A006
from diagnostics.diag_build_3088A026 import build_3088A026
from diagnostics.diag_build_3088A066 import build_3088A066
from diagnostics.diag_build_3088A207 import build_3088A207
from diagnostics.diag_shim_3088a_12x18 import shim_volume
from vn_crank_seat_shim_spec import LAYER_Y, PACK

PART_NAME = "vn-crank-seat-shim"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

# The recipes the modelled pack uses; a pack change that needs another
# thickness fails here until its recipe is imported.
RECIPES = {
    "3088A006": build_3088A006,
    "3088A026": build_3088A026,
    "3088A066": build_3088A066,
    "3088A207": build_3088A207,
}


def components() -> tuple[StockComponent, ...]:
    """The modelled pack, collar side first, each shim on the one before."""
    return tuple(
        StockComponent(
            sku=sku,
            author=RECIPES[sku],
            transform=RigidTransform(translation_mm=(0.0, layer_y, 0.0)),
            parameters={
                "stacked_volume_mm3": sum(shim_volume(below) for below in PACK[:index])
            },
        )
        for index, (sku, layer_y) in enumerate(zip(PACK, LAYER_Y, strict=True))
    )


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=components(),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
