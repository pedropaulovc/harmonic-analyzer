r"""Build purchased MHA-PD-VN-68: McMaster 94773A606 shim, axis +Y, y 0..T.

The stock recipe ``diagnostics/diag_build_94773A606.py`` models the annulus
about +Y at the catalogue's nominal thickness, the frame
``build_pd_paper_drive_assembly`` places each shim in.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_vn_transgear_cluster_shim.py
"""

from __future__ import annotations

from functools import wraps
import sys

from _fastener_catalog import fastener
from _part_properties import part_drawing_unit
from _session import run_build
from _sketch import blank_reference_sketches
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_washer_model import author_supplier_washer_references
from diagnostics.diag_build_94773A606 import build_94773A606
from pd_vn_transgear_cluster_shim_spec import REFERENCE_SKETCHES, SKU
import pd_vn_transgear_cluster_shim_spec as part

PART_NAME = "pd-vn-transgear-cluster-shim"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


@wraps(build_94773A606)
async def _build_with_supplier_references(adapter, truth=None):
    await build_94773A606(adapter, truth)
    await author_supplier_washer_references(
        adapter,
        axis="y",
        bore_mm=part.ID,
        outer_mm=part.OD,
        thickness_mm=part.THICKNESS,
        units=part.SUPPLIER_UNITS,
        sheet_units=part_drawing_unit(PART_NAME),
        precision=part.DRAWING_REFERENCE_PRECISION,
        bands=part.SUPPLIER_TOLERANCES,
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
