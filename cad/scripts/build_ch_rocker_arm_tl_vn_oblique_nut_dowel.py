r"""Purchased MHA-CH-06-TL-VN-81 oblique-trammel feed nut dowel: McMaster 98381A438.

A 3/32 x 1/2 in alloy-steel dowel (``ch_rocker_arm_tl_vn_oblique_nut_dowel_spec``)
that keys the TL-27 feed nut to the TL-32 feed-block lug against rotation.
The stock recipe ``diagnostics/diag_build_98381A438.py`` (the shared 98381A*
section) models the plain nominal cylinder (no vendor model, not
replica-gated); its standalone run is catalog-only.

Frame: pin axis +Y, one end face at y = 0 (the Top Plane), the other at
y = 1/2 in.  The axis is published as ``ScrewAxis`` (Front ∩ Right), the
stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_nut_dowel.py
"""

from __future__ import annotations

import math
import sys

from _appearance import POLISHED_STEEL
from _com import _early_bound
from _drawing_precision import _named_dimension
from _part_save import save_part_and_images
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_pin_model import _cylinder_radii_mm
from _supplier_screw_reference import add_supplier_reference_sketch
from _supplier_screw_reference_names import FEATURE_BY_PLANE
from ch_rocker_arm_tl_vn_oblique_nut_dowel_spec import SKU
from diagnostics.diag_build_98381A438 import build_98381A438
import ch_rocker_arm_tl_vn_oblique_nut_dowel_spec as part

PART_NAME = "ch-rocker-arm-tl-vn-oblique-nut-dowel"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material
# swLengthUnit_e for each supplier reference unit.
_UNIT_CODES = {"mm": 0, "in": 3}


async def _save_supplier_part(adapter, part_name) -> dict[str, str]:
    # Independent solid readback: nominal carriers are not physical proof.
    # The plain nominal cylinder (no vendor end forms) remains as authored.
    radii = _cylinder_radii_mm(adapter.currentModel, 1, label=part.SKU)
    if not math.isclose(2.0 * max(radii), part.DIA, rel_tol=0.0, abs_tol=1e-6):
        raise RuntimeError(f"{part.SKU}: supplier nominal OD differs from the real cylinder")
    await add_supplier_reference_sketch(
        adapter, part.SUPPLIER_REFERENCE_DIMENSIONS,
        starts=part.SUPPLIER_REFERENCE_STARTS,
        planes=part.SUPPLIER_REFERENCE_PLANES,
    )
    for name, value, _orientation in part.SUPPLIER_REFERENCE_DIMENSIONS:
        feature = FEATURE_BY_PLANE[part.SUPPLIER_REFERENCE_PLANES[name]]
        display, native = _named_dimension(adapter, feature, name)
        precision, presentation, denominator, callout = part.SUPPLIER_REFERENCE_FORMATS[name]
        units = part.SUPPLIER_REFERENCE_UNITS[name]
        if presentation not in ("length", "diameter") or (
            denominator is not None and units != "in"
        ):
            raise ValueError(f"{name}: unexpected supplier dowel presentation")
        if int(display.Type2) not in (2, 11, 12) or not math.isclose(
            float(native.SystemValue) * 1000.0, abs(value),
            rel_tol=0.0, abs_tol=1e-5,
        ):
            raise RuntimeError(f"{name}: supplier nominal carrier type/value changed")
        # Model-owned source ink, not the drawing-view-owned formatter: the
        # catalogue fraction where the table states one (fraction base 2).
        fraction = 1 if denominator is None else 2
        if display.SetUnits2(
            False, _UNIT_CODES[units], fraction, denominator or 0, False, 0
        ) != 0:
            raise RuntimeError(f"{name}: supplier {units} units rejected")
        if display.SetPrecision3(precision, -1, -1, -1) != 0:
            raise RuntimeError(f"{name}: supplier source precision rejected")
        prefix = "(<MOD-DIAM>" if presentation == "diameter" else "("
        suffix = f" {units})"
        display.ShowParenthesis = False
        display.SetText(1, prefix)
        display.SetText(2, suffix)
        display.SetText(4, callout or "")
        if (
            display.GetUseDocUnits()
            or int(display.GetUnits()) != _UNIT_CODES[units]
            or int(display.GetFractionBase()) != fraction
            or int(display.GetPrimaryPrecision2()) != precision
            or display.ShowParenthesis
            or display.GetOverride()
            or not display.ShowDimensionValue
            or str(display.GetText(1) or "") != prefix
            or str(display.GetText(2) or "") != suffix
            or str(display.GetText(4) or "") != (callout or "")
            or int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0
        ):
            raise RuntimeError(f"{name}: supplier source presentation did not persist")
    return await save_part_and_images(adapter, part_name)


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_98381A438),),
        material=MATERIAL,
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Right Plane"),
        save_unthreaded_part=_save_supplier_part,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
