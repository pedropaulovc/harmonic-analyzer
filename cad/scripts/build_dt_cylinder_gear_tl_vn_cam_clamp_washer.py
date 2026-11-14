r"""Purchased MHA-DT-12-TL-VN-53 cam fixture clamp washer: McMaster 92141A011.

The #10 washer (``dt_cylinder_gear_tl_vn_cam_clamp_washer_spec``) under the
-VN-52 clamp screw's head, on each cylinder gear's cam face. The stock recipe
``diagnostics/diag_build_92141A011.py`` builds the catalogue annulus,
catalog-only (no vendor model).

Frame: axis +Y, the bottom face at y = 0, the top face (under the screw
head) at y = THICKNESS. The axis is published as ``ScrewAxis``
(Front ∩ Right), the stock-part mate contract.

Run only through the supervised farm launcher:
``part:dt_cylinder_gear_tl_vn_cam_clamp_washer``.
"""

from __future__ import annotations

import sys
from functools import wraps

import dt_cylinder_gear_tl_vn_cam_clamp_washer_spec as part
from _fastener_catalog import fastener
from _part_properties import part_drawing_unit
from _session import run_build
from _sketch import blank_reference_sketches
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_washer_model import author_supplier_washer_references
from diagnostics.diag_build_92141A011 import build_92141A011
from dt_cylinder_gear_tl_vn_cam_clamp_washer_spec import REFERENCE_SKETCHES, SKU

PART_NAME = "dt-cylinder-gear-tl-vn-cam-clamp-washer"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


@wraps(build_92141A011)
async def _build_with_supplier_references(adapter, truth=None):
    await build_92141A011(adapter, truth)
    await author_supplier_washer_references(
        adapter,
        axis="y",
        bore_mm=part.ID,
        outer_mm=part.OD,
        thickness_mm=part.THICKNESS,
        units=part.SUPPLIER_UNITS,
        sheet_units=part_drawing_unit(PART_NAME),
        precision=part.DRAWING_REFERENCE_PRECISION,
        references=part.SUPPLIER_MODEL_REFERENCES,
        bore_callout=part.SUPPLIER_BORE_CALLOUT,
    )
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=_build_with_supplier_references),),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
