r"""Purchased MHA-CH-06-TL-VN-63 oblique-trammel nut bracket screw: McMaster 91251A188.

The ``#8-32 X 1-7/8 SHCS`` (``ch_rocker_arm_tl_vn_oblique_block_screw_spec``) that holds the TL-29 nut bracket to TL-22 pivot block 1, into a blind tap.
The stock recipe ``diagnostics/diag_build_91251A188.py`` builds the catalogue screw on
the 91251A family recipe (``diag_mcmaster_socket_head.build_socket_head``);
the recipe's standalone run is catalog-only (no vendor model, so no replica
gate).

Frame: screw axis +Y, head up, the bearing face (head underside) at y = 0,
the tip at y = -length.  The axis is published as ``ScrewAxis``
(Front ∩ Right), the stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_block_screw.py
"""

from __future__ import annotations

import math
import sys

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from _com import _early_bound
from _drawing_precision import _named_dimension
from _supplier_screw_reference import add_supplier_reference_sketch
from _supplier_screw_reference_names import FEATURE_BY_PLANE
from _simplified_part import save_simplified_part
from ch_rocker_arm_tl_vn_oblique_block_screw_spec import SKU
from diagnostics.diag_build_91251A188 import build_91251A188
import ch_rocker_arm_tl_vn_oblique_block_screw_spec as supplier

PART_NAME = "ch-rocker-arm-tl-vn-oblique-block-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def _save_supplier_part(adapter, part_name, suppressed_features) -> dict[str, str]:
    await add_supplier_reference_sketch(
        adapter,
        supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        starts=supplier.SUPPLIER_REFERENCE_STARTS,
        planes=supplier.SUPPLIER_REFERENCE_PLANES,
    )
    for name in supplier.SUPPLIER_REFERENCE_MINIMUMS:
        feature = FEATURE_BY_PLANE[supplier.SUPPLIER_REFERENCE_PLANES.get(name, "Front")]
        display, native = _named_dimension(adapter, feature, name)
        tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
        # swTolMIN: source semantics belong to this new MODEL reference,
        # never a drawing text suffix or the stock's physical thread geometry.
        tolerance.Type = 5
        if not tolerance.SetValues(0.0, 0.0):
            raise RuntimeError(f"{name}: supplier thread-length minimum rejected")
        if display.SetUnits2(False, 3, 1, 0, False, 0) != 0:
            raise RuntimeError(f"{name}: supplier source inch units rejected")
        if display.SetPrecision3(3, -1, 3, -1) != 0:
            raise RuntimeError(f"{name}: supplier source precision rejected")
        if (
            int(tolerance.Type) != 5
            or not math.isclose(float(tolerance.GetMinValue()), 0.0, rel_tol=0.0, abs_tol=1e-10)
            or not math.isclose(float(tolerance.GetMaxValue()), 0.0, rel_tol=0.0, abs_tol=1e-10)
            or display.GetUseDocUnits()
            or int(display.GetUnits()) != 3
            or int(display.GetPrimaryPrecision2()) != 3
            or int(display.GetPrimaryTolPrecision2()) != 3
        ):
            raise RuntimeError(f"{name}: model-owned supplier minimum did not persist")
    return await save_simplified_part(adapter, part_name, suppressed_features)


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_91251A188),),
        material=MATERIAL,
        save_threaded_part=_save_supplier_part,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
