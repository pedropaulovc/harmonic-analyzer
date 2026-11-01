"""Build purchased pivot screw from dated supplier dimensions.

Datasheet-built nominal envelope, as for the bought leadscrew. No vendor
CAD or unreported edge/socket dimensions are inferred. Axis +Z, origin
on the shoulder end face; the nominal 5/16-18 thread envelope extends -Z,
at the shop-cut length its depth carries (``CutThreadLength``, the sheet's one
shop dimension), its end chamfered as the shop leaves it. Supplier sizes and
bands are model-owned construction references in a Right-plane sketch, in the
final part frame, not claims of helical attachment.
"""
from __future__ import annotations

import math
import sys

import _config
import ch_rocker_arm_tl_vn_oblique_pivot_screw_spec as part
from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bought_revolve import stock_properties
from _check import check
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _dimensions import name_dimensions
from _document_units import apply_package_model_units
from _drawing_marks import mark_dimensions_for_drawing
from _drawing_precision import _named_dimension
from _fastener_catalog import fastener
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _session import run_build
from _sketch import SketchDims, blank_reference_sketches, ensure_fully_defined
from _sketch_circle import define_circle
from _supplier_limits import set_supplier_limits
from _supplier_screw_reference import _linear
from _visibility import blank_reference_geometry

PART_NAME = "ch-rocker-arm-tl-vn-oblique-pivot-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material
AXIS_NAME = "PivotAxis"
MODEL_VOLUME = (
    math.pi / 4.0 * (part.SHOULDER_DIA**2 * part.SHOULDER_LENGTH
                     + part.HEAD_DIA**2 * part.HEAD_HEIGHT
                     + part.THREAD_DIA**2 * part.THREAD_LENGTH)
    # The 45 deg end chamfer's ring: leg^2 / 2 about radius r - leg / 3.
    - math.pi * part.CUT_CHAMFER**2 * (part.THREAD_DIA / 2.0 - part.CUT_CHAMFER / 3.0)
)


async def _ring(adapter, name, od, bore, length, *, offset=0.0, reverse=False):
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    plane = "Front"
    if offset:
        check(name + " plane", await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Front Plane", offset=offset)
        ))
        plane = "HeadPlane"
        name_last_feature(adapter, "HeadPlane")
        blank_reference_geometry(adapter, (("HeadPlane", "PLANE"),))
    check(name + " sketch", await adapter.create_sketch(plane))
    await define_circle(adapter, 0.0, 0.0, od / 2.0, name + " OD")
    if bore:
        await define_circle(adapter, 0.0, 0.0, bore / 2.0, name + " bore")
    await ensure_fully_defined(adapter, name)
    check(name + " exit", await adapter.exit_sketch())
    name_last_feature(adapter, name + "Profile")
    check(name + " extrusion", await adapter.create_extrusion(
        ExtrusionParameters(depth=length, reverse_direction=reverse)
    ))
    name_last_feature(adapter, name)


def _shop_cut_dimension(adapter) -> None:
    """The thread envelope's depth is the shop cut: plain, three places, named."""
    name_dimensions(adapter, part.CUT_FEATURE, [part.CUT_DIMENSION])
    display, native = _named_dimension(adapter, part.CUT_FEATURE, part.CUT_DIMENSION)
    if not math.isclose(float(native.SystemValue) * 1000.0, part.CUT_THREAD_LENGTH, abs_tol=1e-5):
        raise RuntimeError(part.CUT_DIMENSION + ": cut length changed")
    if display.SetPrecision3(part.CUT_THREAD_PLACES, -1, -1, -1) != 0:
        raise RuntimeError(part.CUT_DIMENSION + ": precision rejected")
    display.SetText(4, part.CUT_CALLOUT)
    if (int(display.GetPrimaryPrecision2()) != part.CUT_THREAD_PLACES
            or str(display.GetText(4) or "").replace("\r\n", "\n") != part.CUT_CALLOUT
            or int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0):
        raise RuntimeError(part.CUT_DIMENSION + ": shop presentation did not persist")
    mark_dimensions_for_drawing(adapter, part.CUT_FEATURE, {part.CUT_DIMENSION})


async def _supplier_references(adapter):
    """Right-plane construction carriers (sketch x is model -z), marked for drawing."""
    feature = part.REFERENCE_FEATURE
    check(f"create {feature}", await adapter.create_sketch("Right"))
    recorded = SketchDims()
    for name, value, orientation in part.REFERENCE_DIMENSIONS:
        await _linear(adapter, recorded, name, value, orientation, part.REFERENCE_STARTS[name])
    await ensure_fully_defined(adapter, feature)
    check(f"exit {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    recorded.apply(adapter, feature)
    for name, (lower, upper) in part.REFERENCE_TOLERANCES_MM.items():
        set_supplier_limits(adapter, feature, name, lower, upper)
    for name, value, _orientation in part.REFERENCE_DIMENSIONS:
        display, native = _named_dimension(adapter, feature, name)
        if not math.isclose(float(native.SystemValue) * 1000.0, value, abs_tol=1e-5):
            raise RuntimeError(name + ": nominal carrier value changed")
        precision = part.REFERENCE_FORMATS[name][0]
        banded = name in part.REFERENCE_TOLERANCES_MM
        if display.SetPrecision3(precision, -1, precision if banded else -1, -1) != 0:
            raise RuntimeError(name + ": source precision rejected")
        if (int(display.GetPrimaryPrecision2()) != precision
            or (banded and int(display.GetPrimaryTolPrecision2()) != precision)
            or (not banded and int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0)):
            raise RuntimeError(name + ": source presentation did not persist")
    mark_dimensions_for_drawing(adapter, feature, {name for name, _, _ in part.REFERENCE_DIMENSIONS})
    blank_reference_sketches(adapter, (feature,))


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreateAxisParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    await _ring(adapter, "Shoulder", part.SHOULDER_DIA, 0.0, part.SHOULDER_LENGTH)
    await _ring(adapter, "Head", part.HEAD_DIA, 0.0, part.HEAD_HEIGHT, offset=part.SHOULDER_LENGTH)
    await _ring(adapter, part.CUT_FEATURE, part.THREAD_DIA, 0.0, part.THREAD_LENGTH, reverse=True)
    check("chamfer thread end", await adapter.add_chamfer(
        part.CUT_CHAMFER, [[part.THREAD_DIA / 2.0, 0.0, -part.THREAD_LENGTH]]
    ))
    name_last_feature(adapter, "ThreadEndChamfer")
    check("publish axis", await adapter.create_axis(CreateAxisParameters(
        mode="two_planes", planes=["Top Plane", "Right Plane"]
    )))
    name_last_feature(adapter, AXIS_NAME)
    blank_reference_geometry(adapter, ((AXIS_NAME, "AXIS"),))
    await volume_check(adapter, PART_NAME, MODEL_VOLUME, max(0.01, MODEL_VOLUME * 1e-5))
    await bbox_extent_check(adapter, PART_NAME, "z", part.SHOULDER_LENGTH + part.HEAD_HEIGHT + part.THREAD_LENGTH)
    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    apply_custom_properties(adapter, stock_properties(_config.parts(PART_NAME)))
    _shop_cut_dimension(adapter)
    await _supplier_references(adapter)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
