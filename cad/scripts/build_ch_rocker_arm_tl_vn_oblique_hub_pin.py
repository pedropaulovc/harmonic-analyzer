"""Build purchased hub pin from dated supplier dimensions.

Datasheet-built nominal envelope, as for the bought leadscrew. No vendor
CAD or unreported edge/socket dimensions are inferred. Axis +Z, origin
on the bottom face. Supplier sizes and bands are model-owned construction
references in the final part frame, not claims of helical attachment.
"""
from __future__ import annotations

import math
import sys

import _config
import ch_rocker_arm_tl_vn_oblique_hub_pin_spec as part
from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bought_revolve import stock_properties
from _check import check
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _dimensions import name_dimensions
from _drawing_marks import mark_dimensions_for_drawing
from _drawing_precision import _named_dimension
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _fastener_catalog import fastener
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_save import save_part_and_images
from _session import run_build
from _sketch import ensure_fully_defined
from _sketch_circle import define_circle
from _supplier_screw_reference import add_supplier_reference_sketch
from _supplier_screw_reference_names import FEATURE_BY_PLANE
from _visibility import blank_reference_geometry
from _document_units import apply_package_model_units
from _part_properties import part_drawing_unit

PART_NAME = "ch-rocker-arm-tl-vn-oblique-hub-pin"
# swLengthUnit_e for each supplier reference unit.
_UNIT_CODES = {"mm": 0, "in": 3}
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material
AXIS_NAME = "HubAxis"
MODEL_VOLUME = math.pi / 4.0 * part.DIA**2 * part.CUT_LENGTH


async def _ring(adapter, name, od, bore, length):
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check(name + " sketch", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, od / 2.0, name + " OD")
    if bore:
        await define_circle(adapter, 0.0, 0.0, bore / 2.0, name + " bore")
    await ensure_fully_defined(adapter, name)
    check(name + " exit", await adapter.exit_sketch())
    name_last_feature(adapter, name + "Profile")
    check(name + " extrusion", await adapter.create_extrusion(
        ExtrusionParameters(depth=length)
    ))
    name_last_feature(adapter, name)


def _shop_cut_dimension(adapter) -> None:
    """The pin extrusion's depth is the shop cut: plain, two places, named."""
    name_dimensions(adapter, part.CUT_FEATURE, [part.CUT_DIMENSION])
    display, native = _named_dimension(adapter, part.CUT_FEATURE, part.CUT_DIMENSION)
    if not math.isclose(float(native.SystemValue) * 1000.0, part.CUT_LENGTH, abs_tol=1e-5):
        raise RuntimeError(part.CUT_DIMENSION + ": cut length changed")
    if display.SetPrecision3(part.CUT_PLACES, -1, -1, -1) != 0:
        raise RuntimeError(part.CUT_DIMENSION + ": precision rejected")
    display.SetText(4, part.CUT_CALLOUT)
    if (int(display.GetPrimaryPrecision2()) != part.CUT_PLACES
            or str(display.GetText(4) or "") != part.CUT_CALLOUT
            or int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0):
        raise RuntimeError(part.CUT_DIMENSION + ": shop presentation did not persist")
    mark_dimensions_for_drawing(adapter, part.CUT_FEATURE, {part.CUT_DIMENSION})


async def _supplier_references(adapter):
    await add_supplier_reference_sketch(
        adapter, part.SUPPLIER_REFERENCE_DIMENSIONS,
        starts=part.SUPPLIER_REFERENCE_STARTS,
        planes=part.SUPPLIER_REFERENCE_PLANES,
    )
    for name, (lower, upper) in part.SUPPLIER_REFERENCE_TOLERANCES_MM.items():
        feature = FEATURE_BY_PLANE[part.SUPPLIER_REFERENCE_PLANES[name]]
        set_dimension_bilateral_tolerance(adapter, feature, name, lower, upper)
    for name, value, _orientation in part.SUPPLIER_REFERENCE_DIMENSIONS:
        feature = FEATURE_BY_PLANE[part.SUPPLIER_REFERENCE_PLANES[name]]
        display, native = _named_dimension(adapter, feature, name)
        precision, presentation, _denominator, callout = part.SUPPLIER_REFERENCE_FORMATS[name]
        if not math.isclose(float(native.SystemValue) * 1000.0, value, abs_tol=1e-5):
            raise RuntimeError(name + ": nominal carrier value changed")
        units = part.SUPPLIER_REFERENCE_UNITS[name]
        code, suffix = _UNIT_CODES[units], f" {units})"
        if display.SetUnits2(False, code, 1, 0, False, 0) != 0:
            raise RuntimeError(f"{name}: {units} units rejected")
        banded = name in part.SUPPLIER_REFERENCE_TOLERANCES_MM
        if display.SetPrecision3(precision, -1, precision if banded else -1, -1) != 0:
            raise RuntimeError(name + ": source precision rejected")
        prefix = "(<MOD-DIAM>" if presentation == "diameter" else "("
        display.ShowParenthesis = False
        display.SetText(1, prefix)
        display.SetText(2, suffix)
        display.SetText(4, callout)
        if (display.GetUseDocUnits() or int(display.GetUnits()) != code
            or int(display.GetPrimaryPrecision2()) != precision
            or display.ShowParenthesis or display.GetOverride()
            or not display.ShowDimensionValue
            or str(display.GetText(1) or "") != prefix
            or str(display.GetText(2) or "") != suffix
            or str(display.GetText(4) or "") != callout
            or (banded and int(display.GetPrimaryTolPrecision2()) != precision)
            or (not banded and int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0)):
            raise RuntimeError(name + ": source presentation did not persist")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreateAxisParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    await _ring(adapter, part.CUT_FEATURE, part.DIA, 0.0, part.CUT_LENGTH)
    check("publish axis", await adapter.create_axis(CreateAxisParameters(
        mode="two_planes", planes=["Top Plane", "Right Plane"]
    )))
    name_last_feature(adapter, AXIS_NAME)
    blank_reference_geometry(adapter, ((AXIS_NAME, "AXIS"),))
    await volume_check(adapter, PART_NAME, MODEL_VOLUME, max(0.01, MODEL_VOLUME * 1e-5))
    await bbox_extent_check(adapter, PART_NAME, "z", part.CUT_LENGTH)
    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    apply_custom_properties(adapter, stock_properties(_config.parts(PART_NAME)))
    _shop_cut_dimension(adapter)
    await _supplier_references(adapter)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
