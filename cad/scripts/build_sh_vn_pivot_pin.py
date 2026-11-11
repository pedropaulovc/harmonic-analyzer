r"""Reproduction script: MHA-SH-VN-58, McMaster 90145A299 pivot pins (40 used).

One purchased 5/64 x 5/16 dowel in two installed members
(``sh_vn_pivot_pin_spec``): ``RodPin`` (20) closes each connecting rod's fork
round its rocker arm (``sh_vn_pivot_pin_rod_spec``) and ``BarPin`` (20) each
amplitude bar's top notch round its channel lever
(``sh_vn_pivot_pin_bar_spec``). Each pin RUNS in the moving member's #47 hole
and is PRESSED through the reamed holes of its fork or bar, both ends dressed
flush at MHA-CH-00.

Each member is the INSTALLED pin: a Ø PIN_DIA cylinder its member's
PIN_INSTALLED_LENGTH long, one configured ``PinLen`` global. Layout: axis =
part Z, symmetric about the Front Plane (z = 0); Axis1 is the pin axis (Right
Plane x Top Plane), the channel assembly's concentric reference. Built as a
REVOLVE of a half-profile on the Right plane (a Right-plane sketch maps local
+x -> model -Z; the profile is symmetric, so the axis line's midpoint on the
origin centres the pin on the Front Plane).

The zero-body SUPPLIER_REFERENCE configuration holds the catalogue 5/64 x
5/16 side outline, construction only, whose two dimensions the purchase
drawing prints as supplier REF; no member carries a supplier length.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_sh_vn_pivot_pin.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

import _config
import sh_vn_pivot_pin_bar_spec as bar_pin
import sh_vn_pivot_pin_rod_spec as rod_pin
import sh_vn_pivot_pin_spec as pin
from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _dimensions import drive_dimension, set_global
from _document_units import apply_package_model_units
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _purchased_part_variants import (
    activate_member,
    apply_member_properties,
    assert_member_properties,
    assert_member_suppression,
    create_member_configurations,
    require_member_bodies,
    require_member_colour,
    require_member_configurations,
    save_member_part,
    select_member_features,
)
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    blank_reference_sketches,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from _supplier_spring_reference import (
    ReferenceState,
    add_supplier_reference_configurations,
)
from _visibility import assert_reference_geometry_hidden, blank_reference_geometry

PART_NAME = "sh-vn-pivot-pin"
if PART_NAME != pin.PART_STEM:
    raise AssertionError(f"{PART_NAME} != {pin.PART_STEM}")
# 18-8 stainless: the library's AISI 304, the 18-8 grade.
MATERIAL = "AISI 304"
CONFIGURATIONS = pin.CONFIGURATIONS
PIN_R = pin.PIN_DIA / 2.0
INSTALLED_LENGTHS = {
    rod_pin.CONFIGURATION: rod_pin.PIN_INSTALLED_LENGTH,
    bar_pin.CONFIGURATION: bar_pin.PIN_INSTALLED_LENGTH,
}
DESCRIPTIONS = {
    rod_pin.CONFIGURATION: rod_pin.BOM_DESCRIPTION,
    bar_pin.CONFIGURATION: bar_pin.BOM_DESCRIPTION,
}
# Neither member owns a feature of its own: one solid, one configured length.
MEMBER_FEATURES: dict[str, tuple[str, ...]] = {name: () for name in CONFIGURATIONS}

if tuple(INSTALLED_LENGTHS) != CONFIGURATIONS:
    raise AssertionError("each registered member needs its installed length")


def _construction(adapter: Any, entity: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity}: supplier outline must be construction-only")


async def _supplier_outline(adapter: Any) -> tuple[str, ...]:
    """The catalogue pin's side outline, length along x, diameter along y.

    Its first vertical side carries the diameter and its first horizontal side
    the length; closure defines the other two.
    """
    dims = SketchDims()
    check("create supplier pin outline", await adapter.create_sketch("Front"))
    points = [
        (0.0, 0.0),
        (0.0, pin.PIN_DIA),
        (pin.PIN_LENGTH, pin.PIN_DIA),
        (pin.PIN_LENGTH, 0.0),
    ]
    lines = await add_line_chain(adapter, points)
    for line in lines:
        _construction(adapter, line)
    await define_rectilinear_chain(
        adapter,
        lines,
        points,
        label=pin.SUPPLIER_FEATURE,
        dims=dims,
        names=[pin.DIAMETER_DIMENSION, pin.LENGTH_DIMENSION],
    )
    await ensure_fully_defined(adapter, pin.SUPPLIER_FEATURE)
    check("exit supplier pin outline", await adapter.exit_sketch())
    name_last_feature(adapter, pin.SUPPLIER_FEATURE)
    dims.apply(adapter, pin.SUPPLIER_FEATURE)
    mark_dimensions_for_drawing(
        adapter, pin.SUPPLIER_FEATURE, pin.DIMENSIONS_BY_FEATURE[pin.SUPPLIER_FEATURE]
    )
    blank_reference_sketches(adapter, (pin.SUPPLIER_FEATURE,))
    return (pin.SUPPLIER_FEATURE,)


async def _author_pin(adapter: Any) -> list[tuple[str, str]]:
    """Half-profile on the Right plane, revolved: the installed RodPin."""
    from solidworks_mcp.adapters.base import RevolveParameters

    half = rod_pin.PIN_INSTALLED_LENGTH / 2.0
    profile = SketchDims()
    check("create_sketch pin", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check("axis centerline", await adapter.add_centerline(-half, 0.0, half, 0.0))
    lines = await add_line_chain(
        adapter, [(-half, 0.0), (-half, PIN_R), (half, PIN_R), (half, 0.0)]
    )
    set_sketch_direct_db(adapter, False)
    end_a, journal, end_b, axis_line = lines
    for line, direction in (
        (end_a, "vertical"),
        (journal, "horizontal"),
        (end_b, "vertical"),
        (axis_line, "horizontal"),
    ):
        check(
            f"pin {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    # Symmetric about the Front Plane: the axis line's midpoint on the origin.
    check(
        "pin axis midpoint -> origin",
        await adapter.add_sketch_constraint("origin", axis_line, "midpoint"),
    )
    await dimension_between(
        adapter,
        f"{end_a}.end",
        f"{end_b}.start",
        "horizontal_distance",
        rod_pin.PIN_INSTALLED_LENGTH,
        "pin PinLen",
    )
    profile.record("PinLen", '"PinLen"')
    await add_diametric_linear_dimension(
        adapter, axis, journal, (0.0, PIN_R + 4.0), "PinDia"
    )
    profile.record("PinDia", '"PinDia"')
    await ensure_fully_defined(adapter, "pin sketch")
    check("exit_sketch pin", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs = profile.apply(adapter, "PinProfile")
    check("revolve pin", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Pin")
    volume = math.pi * PIN_R**2 * rod_pin.PIN_INSTALLED_LENGTH
    await volume_check(adapter, "installed RodPin", volume, 0.005 * volume)
    return drive_jobs


async def _readback(adapter: Any, configuration: str) -> None:
    """Check native member state without repairing or saving the document."""
    assert_member_suppression(adapter, configuration, MEMBER_FEATURES)
    require_member_bodies(adapter, configuration, 1, ("Axis1",))
    require_member_colour(adapter, configuration, POLISHED_STEEL)
    length = INSTALLED_LENGTHS[configuration]
    volume = math.pi * PIN_R**2 * length
    await volume_check(adapter, f"{configuration} pin", volume, 0.005 * volume)
    await bbox_extent_check(adapter, f"{configuration} length", "z", length)
    assert_member_properties(
        adapter, PART_NAME, configuration, DESCRIPTIONS[configuration], {}
    )
    assert_reference_geometry_hidden(adapter, f"{PART_NAME}--{configuration}")


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import SetGlobalVariableParameters

    require_member_configurations(PART_NAME, CONFIGURATIONS)
    check("create_part", await adapter.create_part())
    # The row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    await create_member_configurations(adapter, PART_NAME, CONFIGURATIONS)
    await activate_member(adapter, rod_pin.CONFIGURATION)
    # All globals are born after the member configurations exist
    # (IEquationMgr.Add3). The mm suffix is load-bearing (INCH document).
    await set_global(adapter, "PinDia", f"{pin.PIN_DIA}mm")
    await set_global(adapter, "PinLen", f"{rod_pin.PIN_INSTALLED_LENGTH}mm")
    drive_jobs = await _author_pin(adapter)
    await force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "pin axis")

    for configuration in CONFIGURATIONS:
        await select_member_features(adapter, configuration, MEMBER_FEATURES)
        check(
            f"PinLen in {configuration}",
            await adapter.set_global_variable(
                SetGlobalVariableParameters(
                    name="PinLen",
                    expression=f"{INSTALLED_LENGTHS[configuration]}mm",
                    configuration=configuration,
                )
            ),
        )
        await force_rebuild(adapter)
        blank_sketch(adapter, "PinProfile")
        blank_reference_geometry(adapter, (("Axis1", "AXIS"),))
        await apply_material(adapter, MATERIAL)
        await apply_color(adapter, POLISHED_STEEL)
        apply_member_properties(
            adapter, PART_NAME, configuration, DESCRIPTIONS[configuration], {}
        )
        await report_mass_properties(adapter)

    # The model's own sizes are the installed members'; only the supplier
    # outline's two dimensions print.
    clear_dimensions_for_drawing(adapter)
    await add_supplier_reference_configurations(
        adapter,
        (
            ReferenceState(
                pin.SUPPLIER_REFERENCE_CONFIGURATION,
                None,
                _supplier_outline,
                body_count=0,
                kind="diagram",
            ),
        ),
        body_count=1,
    )
    row = _config.parts(PART_NAME)
    apply_custom_properties(
        adapter,
        {
            "Number": str(row["number"]),
            "Stock Name": str(row["stock_name"]),
            "Supplier": str(row["supplier"]),
            "Supplier SKUs": ", ".join(str(sku) for sku in row["supplier_skus"]),
        },
    )
    apply_drawing_properties(adapter, PART_NAME)
    return await save_member_part(
        adapter,
        PART_NAME,
        CONFIGURATIONS,
        material=MATERIAL,
        readback=_readback,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
