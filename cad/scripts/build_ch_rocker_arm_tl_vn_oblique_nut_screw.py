r"""Purchased MHA-CH-06-TL-VN-66 oblique-trammel leadscrew nut screw: Olander 4C50BHCA.

The ``#4-40 X 1/2 BHCS`` (``ch_rocker_arm_tl_vn_oblique_nut_screw_spec``) holds the Tr8 flanged leadscrew nut to the TL-32 integral feed-block lug, into a blind tap.
The stock recipe ``diagnostics/diag_build_4C50BHCA.py`` builds the
catalogue screw on the shared button-head recipe
(``diag_mcmaster_button_head.build_button_head``) plus its nominal underhead
fillet; the recipe's standalone run is catalog-only (no vendor model, no
replica gate).

Frame: screw axis +Y, head up, the bearing face (head underside) at y = 0,
the tip at y = -length.  The axis is published as ``ScrewAxis``
(Front ∩ Right), the stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_nut_screw.py
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
from ch_rocker_arm_tl_vn_oblique_nut_screw_spec import SKU
from diagnostics.diag_build_4C50BHCA import build_4C50BHCA
import ch_rocker_arm_tl_vn_oblique_nut_screw_spec as supplier

PART_NAME = "ch-rocker-arm-tl-vn-oblique-nut-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def _save_supplier_part(adapter, part_name, suppressed_features) -> dict[str, str]:
    await add_supplier_reference_sketch(
        adapter,
        supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        starts=supplier.SUPPLIER_REFERENCE_STARTS,
        planes=supplier.SUPPLIER_REFERENCE_PLANES,
    )
    nominals = {
        name: abs(value) for name, value, _ in supplier.SUPPLIER_REFERENCE_DIMENSIONS
    }
    for name, (minimum, maximum) in supplier.SUPPLIER_REFERENCE_LIMITS_IN.items():
        feature = FEATURE_BY_PLANE[supplier.SUPPLIER_REFERENCE_PLANES.get(name, "Front")]
        display, native = _named_dimension(adapter, feature, name)
        lower = (minimum * 25.4 - nominals[name]) / 1000.0
        upper = (maximum * 25.4 - nominals[name]) / 1000.0
        tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
        # swTolLIMIT, on the new nominal MODEL carrier only. The stock solid
        # and all its existing dimensions remain untouched.
        tolerance.Type = 3
        if not tolerance.SetValues(lower, upper):
            raise RuntimeError(f"{name}: Olander source limits rejected")
        if display.SetUnits2(False, 3, 1, 0, False, 0) != 0:
            raise RuntimeError(f"{name}: Olander source inch units rejected")
        if display.SetPrecision3(3, -1, 3, -1) != 0:
            raise RuntimeError(f"{name}: Olander source limit precision rejected")
        if (
            int(tolerance.Type) != 3
            or not math.isclose(float(tolerance.GetMinValue()), lower, rel_tol=0.0, abs_tol=1e-10)
            or not math.isclose(float(tolerance.GetMaxValue()), upper, rel_tol=0.0, abs_tol=1e-10)
            or display.GetUseDocUnits()
            or int(display.GetUnits()) != 3
            or int(display.GetPrimaryPrecision2()) != 3
            or int(display.GetPrimaryTolPrecision2()) != 3
        ):
            raise RuntimeError(f"{name}: Olander model-owned source limits did not persist")
    return await save_simplified_part(adapter, part_name, suppressed_features)


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_4C50BHCA),),
        material=MATERIAL,
        save_threaded_part=_save_supplier_part,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
