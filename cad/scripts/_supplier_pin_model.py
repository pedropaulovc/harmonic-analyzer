"""Part-hidden spring-pin source references; never add or change solid bodies.

The radial wall witness uses the exact WALL_T that authors the stock tube.
The separate MATING HOLE circle is an application diagram authorised by the
supplier's hole window, not a hole in the pin and not a pin-OD tolerance.
"""

from __future__ import annotations

import math
from typing import Any

import _telemetry
from _check import check
from _com import _early_bound
from _drawing_marks import mark_dimensions_for_drawing
from _drawing_precision import _named_dimension, set_dimension_display_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import name_last_feature
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
)
from _sketch_circle import define_circle
from _supplier_pin_data import (
    MATING_HOLE_DIMENSION,
    MATING_HOLE_FEATURE,
    WALL_DIMENSION,
    WALL_FEATURE,
    SupplierPinReference,
)


def _construction(adapter: Any, entity: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity], "ISketchSegment")
    segment.ConstructionGeometry = True
    if segment.ConstructionGeometry is not True:
        raise RuntimeError(f"{entity}: source-reference construction state did not persist")


def _finish_reference(
    adapter: Any, dims: SketchDims, feature: str, name: str, expected_mm: float, precision: int
) -> None:
    name_last_feature(adapter, feature)
    dims.apply(adapter, feature)
    display, dimension = _named_dimension(adapter, feature, name)
    expected_types = (6,) if name == MATING_HOLE_DIMENSION else (2, 11, 12)
    if int(display.Type2) not in expected_types:
        raise RuntimeError(f"{name}: native source reference has the wrong dimension type")
    actual_mm = float(dimension.SystemValue) * 1000.0
    if not math.isclose(actual_mm, expected_mm, rel_tol=0.0, abs_tol=1e-6):
        raise RuntimeError(f"{name}: native source reference {actual_mm:g} != {expected_mm:g} mm")
    set_dimension_display_precision(adapter, feature, name, precision)
    mark_dimensions_for_drawing(adapter, feature, {name})
    blank_reference_sketches(adapter, (feature,))


@_telemetry.traced("drawing.supplier_pin_source_author")
async def author_supplier_spring_pin_references(
    adapter: Any, source: SupplierPinReference
) -> None:
    """Author native wall and distinct supplier-application diagram dimensions."""
    if (
        source.wall_mm is None or source.wall_precision is None
        or source.application_hole_limits is None or source.application_hole_precision is None
    ):
        raise ValueError(f"{source.sku}: incomplete spring-pin source references")
    # A radial wall segment on the real tube's section: the two end radii
    # come from the same exact nominal diameter/WALL_T as its solid recipe.
    inner_radius = source.diameter_mm / 2.0 - source.wall_mm
    outer_radius = source.diameter_mm / 2.0
    check("create supplier wall reference", await adapter.create_sketch("Right"))
    dims = SketchDims()
    (wall,) = await add_line_chain(
        adapter, [(inner_radius, 0.0), (outer_radius, 0.0)], close=False
    )
    _construction(adapter, wall)
    await anchor_point_to_origin(
        adapter, f"{wall}.start", inner_radius, 0.0, "source wall inner radius"
    )
    dims.record(None)  # Inner-radius placement is not a printed supplier size.
    check("orient radial wall witness", await adapter.add_sketch_constraint(wall, None, "horizontal"))
    await dimension_between(
        adapter, f"{wall}.start", f"{wall}.end", "distance", source.wall_mm, "supplier wall"
    )
    dims.record(WALL_DIMENSION)
    await ensure_fully_defined(adapter, "supplier wall radial witness")
    check("exit supplier wall reference", await adapter.exit_sketch())
    _finish_reference(
        adapter, dims, WALL_FEATURE, WALL_DIMENSION, source.wall_mm, source.wall_precision
    )

    lower, upper = source.application_hole_limits
    lower_mm = lower * source.unit_mm
    check("create supplier mating-hole reference", await adapter.create_sketch("Right"))
    dims = SketchDims()
    circle = await define_circle(
        adapter, *source.application_hole_center, lower_mm / 2.0,
        "supplier mating-hole application", dims=dims,
        names=(None, None, MATING_HOLE_DIMENSION),
    )
    _construction(adapter, circle)
    await ensure_fully_defined(adapter, "supplier mating-hole application diagram")
    check("exit supplier mating-hole reference", await adapter.exit_sketch())
    _finish_reference(
        adapter, dims, MATING_HOLE_FEATURE, MATING_HOLE_DIMENSION,
        lower_mm, source.application_hole_precision,
    )
    # The native carrier is the lower source limit, independent of the pin's
    # actual/installed OD. A LIMIT display prints the exact acceptance pair.
    set_dimension_bilateral_tolerance(
        adapter, MATING_HOLE_FEATURE, MATING_HOLE_DIMENSION,
        0.0, (upper - lower) * source.unit_mm,
    )
    display, dimension = _named_dimension(adapter, MATING_HOLE_FEATURE, MATING_HOLE_DIMENSION)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 3  # swTolLIMIT
    display.SetPrecision3(-1, -1, source.application_hole_precision, -1)
    assert_supplier_spring_pin_references(adapter, source)


@_telemetry.traced("drawing.supplier_pin_source_readback")
def assert_supplier_spring_pin_references(adapter: Any, source: SupplierPinReference) -> None:
    """Read back both named native source witnesses without modifying them."""
    if (
        source.wall_mm is None or source.wall_precision is None
        or source.application_hole_limits is None or source.application_hole_precision is None
    ):
        raise ValueError(f"{source.sku}: incomplete spring-pin source references")
    lower, upper = source.application_hole_limits
    for feature, name, expected_mm, precision, kinds in (
        (WALL_FEATURE, WALL_DIMENSION, source.wall_mm, source.wall_precision, (2, 11, 12)),
        (MATING_HOLE_FEATURE, MATING_HOLE_DIMENSION, lower * source.unit_mm,
         source.application_hole_precision, (6,)),
    ):
        display, dimension = _named_dimension(adapter, feature, name)
        if int(display.Type2) not in kinds:
            raise RuntimeError(f"{source.sku}: {name} has the wrong native source type")
        if (
            not math.isclose(float(dimension.SystemValue) * 1000.0, expected_mm,
                             rel_tol=0.0, abs_tol=1e-6)
            or int(display.GetPrimaryPrecision2()) != precision
        ):
            raise RuntimeError(f"{source.sku}: {name} source value/precision changed")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        if name == WALL_DIMENSION:
            if int(tolerance.Type) != 0:
                raise RuntimeError(f"{source.sku}: wall gained an unsourced tolerance")
        elif (
            int(tolerance.Type) != 3
            or not math.isclose(float(tolerance.GetMinValue()), 0.0, rel_tol=0.0, abs_tol=1e-12)
            or not math.isclose(
                float(tolerance.GetMaxValue()), (upper - lower) * source.unit_mm / 1000.0,
                rel_tol=0.0, abs_tol=1e-12,
            )
            or int(display.GetPrimaryTolPrecision2()) != source.application_hole_precision
        ):
            raise RuntimeError(f"{source.sku}: native mating-hole limits/type/precision changed")
