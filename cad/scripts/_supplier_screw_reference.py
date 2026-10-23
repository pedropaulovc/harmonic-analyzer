"""Hidden model-owned nominal supplier envelopes; never change purchased solids.

A groove or driver slot can remove a nominal diameter or dome apex. These
construction references retain the exact source sizes, not rounded ink. They
are authored only after the stock recipe's final body transform.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from _check import check
from _com import _early_bound
from _drawing_marks import mark_dimensions_for_drawing
from _feature_tree import name_last_feature
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _supplier_screw_layout import supplier_screw_lane_plan
from _supplier_screw_reference_names import FEATURE_BY_PLANE
from _supplier_screw_reference_names import REFERENCE_SKETCHES as REFERENCE_SKETCHES
import _telemetry


def _assert_line_frame(
    adapter: Any,
    entity: str,
    start: tuple[float, float],
    end: tuple[float, float],
) -> None:
    """A positive length alone must not hide a flipped or translated chord."""
    line = _early_bound(adapter._sketch_entities[entity], "ISketchLine")
    for raw, expected in (
        (line.GetStartPoint2(), start),
        (line.GetEndPoint2(), end),
    ):
        if raw is None:
            raise RuntimeError(f"{entity}: supplier reference endpoint is missing")
        point = _early_bound(raw, "ISketchPoint")
        actual = (float(point.X), float(point.Y), float(point.Z))
        target = (expected[0] / 1000.0, expected[1] / 1000.0, 0.0)
        if not all(math.isfinite(value) for value in actual) or any(
            abs(value - wanted) > 1e-8  # Same 1e-5 mm exact-value guard as import.
            for value, wanted in zip(actual, target, strict=True)
        ):
            raise RuntimeError(f"{entity}: supplier reference moved from its final-frame coordinates")


def _construction(adapter: Any, entity: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity}: supplier reference is not construction geometry")


async def _anchor(
    adapter: Any, dimensions: SketchDims, entity: str, start: tuple[float, float], name: str
) -> None:
    await anchor_point_to_origin(adapter, f"{entity}.start", *start, name)
    for coordinate, axis in zip(start, ("X", "Y"), strict=True):
        if abs(coordinate) >= 1e-9:
            dimensions.record(f"{name}Start{axis}")


async def _linear(
    adapter: Any,
    dimensions: SketchDims,
    name: str,
    value: float,
    orientation: str,
    start: tuple[float, float],
) -> None:
    end = (
        (start[0] + value, start[1])
        if orientation == "horizontal"
        else (start[0], start[1] + value)
    )
    set_sketch_direct_db(adapter, True)
    try:
        line = check(f"create {name} supplier reference", await adapter.add_line(*start, *end))
    finally:
        set_sketch_direct_db(adapter, False)
    _construction(adapter, line)
    check(
        f"orient {name} supplier reference",
        await adapter.add_sketch_constraint(line, None, orientation),
    )
    await dimension_between(
        adapter, f"{line}.start", f"{line}.end", f"{orientation}_distance", abs(value), name
    )
    dimensions.record(name)
    # CreateLine can weld either end to an earlier, anchored witness. After
    # orientation and size, both points then have no remaining freedom; a new
    # origin anchor would redundantly constrain that connected construction.
    native = _early_bound(adapter._sketch_entities[line], "ISketchLine")
    endpoints = (native.GetStartPoint2(), native.GetEndPoint2())
    if any(point is None for point in endpoints):
        raise RuntimeError(f"{name}: supplier reference endpoint is missing")
    states = tuple(_early_bound(point, "ISketchPoint").Status for point in endpoints)
    if any(not isinstance(state, int) for state in states):
        raise RuntimeError(f"{name}: supplier reference endpoint status is unreadable")
    if states != (3, 3):  # swConstrainedStatus_e.swFullyConstrained
        await _anchor(adapter, dimensions, line, start, name)
    _assert_line_frame(adapter, line, start, end)


async def _angle(
    adapter: Any,
    dimensions: SketchDims,
    name: str,
    degrees: float,
    start: tuple[float, float],
) -> None:
    # Unit rays carry only the included angle. Their lengths are unmarked
    # bookkeeping, not additional supplier dimensions.
    radians = math.radians(degrees)
    set_sketch_direct_db(adapter, True)
    try:
        baseline = check(
            f"create {name} baseline",
            await adapter.add_line(*start, start[0] + 1.0, start[1]),
        )
        ray = check(
            f"create {name} angle ray",
            await adapter.add_line(*start, start[0] + math.cos(radians), start[1] + math.sin(radians)),
        )
    finally:
        set_sketch_direct_db(adapter, False)
    for entity in (baseline, ray):
        _construction(adapter, entity)
    check(
        f"orient {name} baseline",
        await adapter.add_sketch_constraint(baseline, None, "horizontal"),
    )
    await dimension_between(
        adapter, f"{baseline}.start", f"{baseline}.end", "horizontal_distance", 1.0, name
    )
    dimensions.record(f"{name}BaselineLength")
    await _anchor(adapter, dimensions, baseline, start, name)
    check(
        f"join {name} rays",
        await adapter.add_sketch_constraint(f"{baseline}.start", f"{ray}.start", "coincident"),
    )
    await dimension_between(adapter, f"{ray}.start", f"{ray}.end", "distance", 1.0, name)
    dimensions.record(f"{name}RayLength")
    # The generic SDK angle path selects one segment and a vertex. Here the
    # supplier control must drive the angle BETWEEN these two existing rays.
    from solidworks_mcp.adapters.com_variant import double_array
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    segment = _early_bound(adapter._sketch_entities[baseline], "ISketchSegment")
    sketch = _early_bound(segment.GetSketch(), "ISketch")
    if sketch is None:
        raise RuntimeError(f"{name}: angle baseline has no native sketch owner")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    if transform is None:
        raise RuntimeError(f"{name}: angle sketch has no model-to-sketch transform")
    inverse = _early_bound(transform.Inverse(), "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    if inverse is None or utility is None:
        raise RuntimeError(f"{name}: cannot transform the angular text point")
    # Halfway along the unit rays' bisector, in their actual owning plane.
    wedge = (
        (start[0] + 0.5 * math.cos(radians / 2.0)) / 1000.0,
        (start[1] + 0.5 * math.sin(radians / 2.0)) / 1000.0,
        0.0,
    )
    point = _early_bound(utility.CreatePoint(double_array(list(wedge))), "IMathPoint")
    if point is None:
        raise RuntimeError(f"{name}: cannot create the angular text point")
    projected = _early_bound(point.MultiplyTransform(inverse), "IMathPoint")
    if projected is None:
        raise RuntimeError(f"{name}: cannot project the angular text point")
    text_xyz = tuple(float(value) for value in (projected.ArrayData or ()))
    if len(text_xyz) != 3 or not all(math.isfinite(value) for value in text_xyz):
        raise RuntimeError(f"{name}: angular text point is invalid: {text_xyz!r}")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    try:
        _select_sketch_entities(adapter, [baseline, ray], 0)
        display, status = _early_bound(model.Extension, "IModelDocExtension").AddSpecificDimension(
            *text_xyz, 3, 0  # swDimensionType_e.swAngularDimension
        )
    finally:
        model.ClearSelection2(True)
    if display is None or status != 0:  # swAddSpecificDimension_Success
        raise RuntimeError(f"{name}: AddSpecificDimension(angular) failed ({status})")
    display = _early_bound(display, "IDisplayDimension")
    if int(display.Type2) != 3:
        raise RuntimeError(f"{name}: supplier angle is not a native angular dimension")
    angle = _early_bound(display.GetDimension2(0), "IDimension")
    if angle is None:
        raise RuntimeError(f"{name}: supplier angle has no native dimension")
    tolerance = math.radians(1e-5)  # Same exact-angle guard as the saved feature.
    actual = float(angle.SystemValue)
    if not math.isclose(actual, radians, rel_tol=0.0, abs_tol=tolerance):
        raise RuntimeError(f"{name}: supplier angle is not the specified {degrees:g} degrees")
    angle.DrivenState = 2  # swDimensionDrivenState_e.swDimensionDriving
    if int(angle.DrivenState) != 2 or not math.isclose(
        float(angle.SystemValue), radians, rel_tol=0.0, abs_tol=tolerance
    ):
        raise RuntimeError(f"{name}: supplier angle is not an exact driving control")
    _assert_line_frame(adapter, baseline, start, (start[0] + 1.0, start[1]))
    _assert_line_frame(
        adapter, ray, start,
        (start[0] + math.cos(radians), start[1] + math.sin(radians)),
    )
    dimensions.record(name)


@_telemetry.traced("part.supplier_reference_sketch")
async def add_supplier_reference_sketch(
    adapter: Any,
    dimensions: Sequence[tuple[str, float, str]],
    *,
    starts: Mapping[str, tuple[float, float]] | None = None,
    planes: Mapping[str, str] | None = None,
) -> None:
    """Author fully defined, hidden construction references in the FINAL frame.

    Rows are (name, exact signed mm, horizontal|vertical), or degrees/angle.
    The sign chooses direction from starts[name], not a displayed negative size.
    Front/Top coordinates are sketch mm; Top Y is model -Z. Only supplier
    sizes, never anchors or angle-ray lengths, are marked for drawing.
    """
    starts = starts or {}
    planes = planes or {}
    supplier_screw_lane_plan(dimensions, planes=planes)
    names = {name for name, _, _ in dimensions}
    if set(starts) - names:
        raise ValueError("supplier reference placement names do not match dimensions")
    for name in names:
        start = starts.get(name, (0.0, 0.0))
        if len(start) != 2 or not all(math.isfinite(value) for value in start):
            raise ValueError(f"{name}: supplier reference start must be a finite coordinate pair")
    part = _early_bound(adapter.currentModel, "IPartDoc")
    # Reject a duplicate authoring pass rather than silently creating a suffixed
    # feature that a drawing might confuse with an earlier carrier.
    for plane, feature in FEATURE_BY_PLANE.items():
        if any(planes.get(name, "Front") == plane for name in names) and part.FeatureByName(feature) is not None:
            raise RuntimeError(f"{feature}: supplier reference sketch already exists")
    for plane, feature in FEATURE_BY_PLANE.items():
        rows = [row for row in dimensions if planes.get(row[0], "Front") == plane]
        if not rows:
            continue
        check(f"create {feature}", await adapter.create_sketch(plane))
        recorded = SketchDims()
        for name, value, orientation in rows:
            start = starts.get(name, (0.0, 0.0))
            if orientation == "angle":
                await _angle(adapter, recorded, name, value, start)
            else:
                await _linear(adapter, recorded, name, value, orientation, start)
        await ensure_fully_defined(adapter, feature)
        check(f"exit {feature}", await adapter.exit_sketch())
        name_last_feature(adapter, feature)
        recorded.apply(adapter, feature)
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        for name, value, orientation in rows:
            native = model.Parameter(f"{name}@{feature}")
            if native is None:
                raise RuntimeError(f"{name}@{feature}: supplier reference dimension is missing")
            native = _early_bound(native, "IDimension")
            expected = math.radians(value) if orientation == "angle" else abs(value) / 1000.0
            tolerance = math.radians(1e-5) if orientation == "angle" else 1e-8
            measured = float(native.SystemValue)
            if not math.isfinite(measured) or not math.isclose(
                measured, expected, rel_tol=0.0, abs_tol=tolerance
            ):
                raise RuntimeError(f"{name}@{feature}: supplier reference value changed during constraint solving")
        mark_dimensions_for_drawing(adapter, feature, {name for name, _, _ in rows})
        blank_reference_sketches(adapter, (feature,))

