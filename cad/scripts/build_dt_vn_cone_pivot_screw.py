r"""Purchased cone pivot screw: McMaster 91829A560 in its stock local frame."""

from __future__ import annotations

import math
import sys

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _drawing_precision import _named_dimension
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _supplier_screw_reference import add_supplier_reference_sketch
from _supplier_screw_reference_names import FEATURE_BY_PLANE
from _mcmaster_91829a560 import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_FORMATS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_STARTS,
    SUPPLIER_REFERENCE_TOLERANCES_IN,
)
from _simplified_part import save_simplified_part
from diagnostics.diag_build_91829A560 import build_91829A560

PART_NAME = "dt-vn-cone-pivot-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def _save_supplier_part(adapter, part_name, suppressed_features) -> dict[str, str]:
    await add_supplier_reference_sketch(
        adapter,
        SUPPLIER_REFERENCE_DIMENSIONS,
        starts=SUPPLIER_REFERENCE_STARTS,
        planes=SUPPLIER_REFERENCE_PLANES,
    )
    for name, (lower, upper) in SUPPLIER_REFERENCE_TOLERANCES_IN.items():
        feature = FEATURE_BY_PLANE[SUPPLIER_REFERENCE_PLANES.get(name, "Front")]
        set_dimension_bilateral_tolerance(
            adapter, feature, name, lower * 25.4, upper * 25.4
        )
    for name, value, _orientation in SUPPLIER_REFERENCE_DIMENSIONS:
        feature = FEATURE_BY_PLANE[SUPPLIER_REFERENCE_PLANES.get(name, "Front")]
        display, native = _named_dimension(adapter, feature, name)
        precision, presentation, denominator, callout = SUPPLIER_REFERENCE_FORMATS[name]
        if denominator is not None or presentation not in ("length", "diameter"):
            raise ValueError(f"{name}: unexpected shoulder-screw source presentation")
        if int(display.Type2) not in (2, 11, 12) or not math.isclose(
            float(native.SystemValue) * 1000.0,
            abs(value),
            rel_tol=0.0,
            abs_tol=1e-5,
        ):
            raise RuntimeError(f"{name}: source supplier native type/value changed")
        # These are MODEL display dimensions: use direct source presentation,
        # never the shared drawing-view-owned supplier formatter.
        if display.SetUnits2(False, 3, 1, 0, False, 0) != 0:
            raise RuntimeError(f"{name}: source supplier inch units rejected")
        tolerance_precision = precision if name in SUPPLIER_REFERENCE_TOLERANCES_IN else -1
        if display.SetPrecision3(precision, -1, tolerance_precision, -1) != 0:
            raise RuntimeError(f"{name}: source supplier precision rejected")
        prefix = "(<MOD-DIAM>" if presentation == "diameter" else "("
        display.ShowParenthesis = False
        display.SetText(1, prefix)
        display.SetText(2, " in)")
        display.SetText(4, callout or "")
        if (
            display.GetUseDocUnits()
            or int(display.GetUnits()) != 3
            or int(display.GetFractionBase()) != 1
            or int(display.GetPrimaryPrecision2()) != precision
            or display.ShowParenthesis
            or display.GetOverride()
            or not display.ShowDimensionValue
            or str(display.GetText(1) or "") != prefix
            or str(display.GetText(2) or "") != " in)"
            or str(display.GetText(4) or "") != (callout or "")
            or (
                name in SUPPLIER_REFERENCE_TOLERANCES_IN
                and int(display.GetPrimaryTolPrecision2()) != precision
            )
        ):
            raise RuntimeError(f"{name}: source supplier presentation did not persist")
    return await save_simplified_part(adapter, part_name, suppressed_features)


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="91829A560",
                author=build_91829A560,
                transform=RigidTransform(),
            ),
        ),
        material=MATERIAL,
        save_threaded_part=_save_supplier_part,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
