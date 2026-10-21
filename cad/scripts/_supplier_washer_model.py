"""Model-owned supplier bands on exact, construction-only washer witnesses.

Stock recipes initially make +Y solids. Their optional normalization moves
bodies only, so witnesses are authored directly in the final model planes.
Neither this module nor the drawing changes a solid or a native size value.
"""

from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any, Literal

from solidworks_mcp.adapters.com_variant import double_array

import _telemetry
from _check import check
from _com import _early_bound
from _drawing_marks import mark_dimensions_for_drawing
from _drawing_precision import _named_dimensions
from _feature_tree import name_last_feature
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
)
from _sketch_circle import define_circle

OUTER_DIAMETER = "supplier outer diameter"
BORE_DIAMETER = "supplier bore diameter"
THICKNESS = "supplier thickness"
FACE_FEATURE = "SupplierWasherFaceReference"
THICKNESS_FEATURE = "SupplierWasherThicknessReference"
SOURCE_DIMENSIONS = {
    OUTER_DIAMETER: (FACE_FEATURE, "SupplierOuterDiameter"),
    BORE_DIAMETER: (FACE_FEATURE, "SupplierBoreDiameter"),
    THICKNESS: (THICKNESS_FEATURE, "SupplierThickness"),
}


def _assert_supplier_washer_presentation(
    display: Any, *, label: str, units: Literal["in", "mm"],
    precision: int, expected_mm: float, callout: str | None,
) -> None:
    """Read model-owned ink without assuming a visible drawing-view owner."""
    display = _early_bound(display, "IDisplayDimension")
    allowed_types = (2, 11, 12) if label == THICKNESS else (6,)
    if int(display.Type2) not in allowed_types:
        raise RuntimeError(f"{label}: model supplier dimension has the wrong native type")
    raw = display.GetDimension2(0)
    if raw is None:
        raise RuntimeError(f"{label}: model supplier dimension is missing")
    native = _early_bound(raw, "IDimension")
    if not math.isclose(abs(float(native.SystemValue)), expected_mm / 1000.0,
                        rel_tol=0.0, abs_tol=1e-9):
        raise RuntimeError(f"{label}: model supplier dimension differs from its exact carrier")
    prefix = "(" if label == THICKNESS else "(<MOD-DIAM>"
    if (
        display.GetUseDocUnits()
        or int(display.GetUnits()) != {"mm": 0, "in": 3}[units]
        or int(display.GetFractionBase()) != 1  # swDECIMAL
        or int(display.GetPrimaryPrecision2()) != precision
        or int(display.GetPrimaryTolPrecision2()) != precision
        or display.ShowParenthesis
        or display.GetOverride()
        or not display.ShowDimensionValue
        or str(display.GetText(1) or "") != prefix
        or str(display.GetText(2) or "") != f" {units})"
        or str(display.GetText(4) or "") != (callout or "")
    ):
        raise RuntimeError(f"{label}: model supplier units/precision/reference ink changed")


def assert_supplier_washer_band(
    display: Any, *, nominal_mm: float,
    band: tuple[float, float, str] | None, precision: int, label: str,
) -> None:
    """Read only; supplier tolerance precision is not a millimetre precision."""
    native = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
    if band is None:
        if int(tolerance.Type) != 0:
            raise RuntimeError(f"{label}: unexpected native supplier tolerance")
        return
    lower, upper, style = band
    if (
        int(tolerance.Type) != {"bilateral": 2, "limits": 3, "symmetric": 4}[style]
        or not math.isclose(float(tolerance.GetMinValue()), (lower - nominal_mm) / 1000.0,
                            rel_tol=0.0, abs_tol=1e-12)
        or not math.isclose(float(tolerance.GetMaxValue()), (upper - nominal_mm) / 1000.0,
                            rel_tol=0.0, abs_tol=1e-12)
        or int(display.GetPrimaryTolPrecision2()) != precision
    ):
        raise RuntimeError(f"{label}: model-owned supplier band/type/precision changed")


@_telemetry.traced("part.assert_supplier_washer_body")
def assert_supplier_washer_body(
    model: Any, *, axis: Literal["y", "z"], bore_mm: float,
    outer_mm: float, thickness_mm: float,
) -> None:
    """Independently read actual solid circular edges, not witness metadata."""
    bodies = tuple(_early_bound(model, "IPartDoc").GetBodies2(0, False) or ())
    if len(bodies) != 1:
        raise RuntimeError("supplier washer must have exactly one solid body")
    circles = []
    for raw in _early_bound(bodies[0], "IBody2").GetEdges() or ():
        curve = _early_bound(_early_bound(raw, "IEdge").GetCurve(), "ICurve")
        if curve.IsCircle():
            circles.append(tuple(float(value) for value in curve.CircleParams))
    index = 1 if axis == "y" else 2
    if len(circles) != 4:
        raise RuntimeError("supplier washer solid must have four circular end rims")
    for diameter in (outer_mm, bore_mm):
        for station in (0.0, thickness_mm):
            center = [0.0, 0.0, 0.0]
            center[index] = station / 1000.0
            matches = [
                circle for circle in circles
                if all(math.isclose(a, b, rel_tol=0.0, abs_tol=1e-9)
                       for a, b in zip(circle[:3], center, strict=True))
                and math.isclose(circle[6], diameter / 2000.0, rel_tol=0.0, abs_tol=1e-9)
                and math.isclose(abs(circle[3 + index]), 1.0, rel_tol=0.0, abs_tol=1e-9)
            ]
            if len(matches) != 1:
                raise RuntimeError(f"supplier washer solid differs at {diameter:g} / {station:g} mm")


def _construction(adapter: Any, entity: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity], "ISketchSegment")
    segment.ConstructionGeometry = True
    if segment.ConstructionGeometry is not True:
        raise RuntimeError("supplier washer witness is not construction geometry")


def _model_point(adapter: Any, sketch: Any, coordinates: tuple[float, ...]) -> tuple[float, ...]:
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform").Inverse()
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    # CreatePoint requires VT_ARRAY|VT_R8; a bare sequence can silently
    # marshal as variants and be read as the origin (_drawing_leaders).
    point = utility.CreatePoint(double_array(list(coordinates)))
    if transform is None or point is None:
        raise RuntimeError("supplier washer source coordinate mapping is unavailable")
    created = tuple(float(value) for value in _early_bound(point, "IMathPoint").ArrayData)
    _assert_point(created, coordinates, "supplier washer source point marshaling")
    mapped = _early_bound(point, "IMathPoint").MultiplyTransform(transform)
    if mapped is None:
        raise RuntimeError("supplier washer source coordinate mapping failed")
    return tuple(float(value) for value in _early_bound(mapped, "IMathPoint").ArrayData)


def _point_coordinates(point: Any) -> tuple[float, ...]:
    point = _early_bound(point, "ISketchPoint")
    return tuple(float(getattr(point, coordinate)) for coordinate in ("X", "Y", "Z"))


def _assert_point(actual: tuple[float, ...], expected: tuple[float, ...], label: str) -> None:
    if len(actual) != 3 or not all(
        math.isclose(a, b, rel_tol=0.0, abs_tol=1e-9)
        for a, b in zip(actual, expected, strict=True)
    ):
        raise RuntimeError(f"{label}: source geometry {actual!r} != {expected!r}")


def assert_supplier_washer_source_attachment(
    adapter: Any, model: Any, display: Any, *, label: str,
    axis: Literal["y", "z"], bore_mm: float, outer_mm: float, thickness_mm: float,
    visible: bool = False,
) -> None:
    """Resolve the named owner's actual geometry independently of the import.

    A diameter must attach to its exact construction circle. Thickness must
    attach to the two points of the sole line at the physical OD flank.
    """
    feature_name, dimension_name = SOURCE_DIMENSIONS[label]
    raw = _early_bound(model, "IPartDoc").FeatureByName(feature_name)
    if raw is None:
        raise RuntimeError(f"{label}: missing source feature {feature_name}")
    feature = _early_bound(raw, "IFeature")
    sketch = _early_bound(feature.GetSpecificFeature2(), "ISketch")
    source_display, source_native = _named_dimensions(
        adapter, feature_name, {dimension_name}, feature=feature
    )[dimension_name]
    native = _early_bound(display.GetDimension2(0), "IDimension")
    full_name = str(native.FullName or "")
    owner = native.GetFeatureOwner()
    if (
        full_name.split("@")[:2] != [dimension_name, feature_name]
        or str(source_native.FullName).split("@")[:2] != [dimension_name, feature_name]
        or owner is None
        or int(adapter.swApp.IsSame(owner, feature)) != 1
        or int(display.Type2) != int(source_display.Type2)
    ):
        raise RuntimeError(f"{label}: imported dimension does not belong to its named model witness")
    segments = [_early_bound(segment, "ISketchSegment")
                for segment in sketch.GetSketchSegments() or ()]
    if len(segments) != (1 if label == THICKNESS else 2) or any(
        segment.ConstructionGeometry is not True for segment in segments
    ):
        raise RuntimeError(f"{label}: unexpected source witness segment inventory")
    top_plane = (axis == "y") != (label == THICKNESS)
    # Independently check the sketch's final model plane, including Top's -Z.
    for local, expected in (
        ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ((0.001, 0.0, 0.0), (0.001, 0.0, 0.0)),
        ((0.0, 0.001, 0.0), (0.0, 0.0, -0.001) if top_plane else (0.0, 0.001, 0.0)),
    ):
        _assert_point(_model_point(adapter, sketch, local), expected, label)
    if label == THICKNESS:
        segment = segments[0]
        if int(segment.GetType()) != 0 or int(display.Type2) not in (2, 11, 12):
            raise RuntimeError(f"{label}: source thickness is not a native line dimension")
        line = _early_bound(segment, "ISketchLine")
        points = (line.GetStartPoint2(), line.GetEndPoint2())
        sign = 1.0 if axis == "y" else -1.0
        expected_local = ((outer_mm / 2000.0, 0.0, 0.0),
                          (outer_mm / 2000.0, sign * thickness_mm / 1000.0, 0.0))
        for point, expected in zip(points, expected_local, strict=True):
            _assert_point(_point_coordinates(point), expected, label)
        expected_entities = points
    else:
        circles = []
        for segment in segments:
            if int(segment.GetType()) != 1:
                raise RuntimeError(f"{label}: source face contains a non-circle")
            circle = _early_bound(segment, "ISketchArc")
            if int(circle.IsCircle()) != 1:
                raise RuntimeError(f"{label}: source diameter is a partial arc")
            _assert_point(_point_coordinates(circle.GetCenterPoint2()), (0.0, 0.0, 0.0), label)
            circles.append((segment, float(circle.GetRadius()) * 2000.0))
        for diameter in (outer_mm, bore_mm):
            if sum(math.isclose(value, diameter, rel_tol=0.0, abs_tol=1e-6)
                   for _, value in circles) != 1:
                raise RuntimeError(f"{label}: source circles differ from the exact solid recipe")
        expected_mm = outer_mm if label == OUTER_DIAMETER else bore_mm
        expected_entities = tuple(segment for segment, diameter in circles
                                  if math.isclose(diameter, expected_mm, rel_tol=0.0, abs_tol=1e-6))
        if int(display.Type2) != 6:
            raise RuntimeError(f"{label}: source diameter lost its native diameter type")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    attached = list(annotation.GetAttachedEntities3() or ())
    for entity in expected_entities:
        matches = [i for i, item in enumerate(attached)
                   if item is not None and int(adapter.swApp.IsSame(item, entity)) == 1]
        if len(matches) != 1:
            raise RuntimeError(f"{label}: attachment is not the independently resolved source entity")
        attached.pop(matches[0])
    if attached or annotation.IsDangling() or (visible and int(annotation.Visible) != 1):
        raise RuntimeError(f"{label}: unexpected, hidden or dangling source attachments")


def _finish_reference(
    adapter: Any, dims: SketchDims, feature: str, labels: tuple[str, ...], *,
    values: Mapping[str, float], units: Literal["in", "mm"],
    precision: Mapping[str, int], bands: Mapping[str, tuple[float, float, str]],
    bore_callout: str | None,
) -> None:
    name_last_feature(adapter, feature)
    dims.apply(adapter, feature)
    named = _named_dimensions(adapter, feature, {SOURCE_DIMENSIONS[label][1] for label in labels})
    for label in labels:
        name = SOURCE_DIMENSIONS[label][1]
        display, native = named[name]
        nominal = values[label]
        lower, upper, style = bands[label]
        if not all(map(math.isfinite, (lower, upper))) or lower >= upper:
            raise ValueError(f"{label}: invalid supplier band")
        if style == "symmetric" and not math.isclose(nominal - lower, upper - nominal,
                                                     rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(f"{label}: symmetric source band is not centred on the exact carrier")
        tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
        tolerance.Type = {"bilateral": 2, "limits": 3, "symmetric": 4}[style]
        if not tolerance.SetValues((lower - nominal) / 1000.0, (upper - nominal) / 1000.0):
            raise RuntimeError(f"{label}: model supplier deviations were rejected")
        if display.GetOverride() or not display.ShowDimensionValue:
            raise RuntimeError(f"{label}: model supplier dimension hides or overrides its native value")
        # Source-model presentation is authored here, not through the shared
        # formatter whose attachment contract requires a visible drawing view.
        # swDECIMAL=1; HalfAway=0 preserves the supplier's decimal rounding.
        if int(display.SetUnits2(False, {"mm": 0, "in": 3}[units], 1, 0, False, 0)) != 0:
            raise RuntimeError(f"{label}: model supplier units were rejected")
        # Unlike _drawing_tolerances' mm-place inference, these are supplier
        # unit places. Both the native success status and readback are required.
        status = display.SetPrecision3(precision[label], -1, precision[label], -1)
        if int(status) != 0:
            raise RuntimeError(f"{label}: model supplier precision failed ({status!r})")
        display.ShowParenthesis = False
        display.SetText(1, "(" if label == THICKNESS else "(<MOD-DIAM>")
        display.SetText(2, f" {units})")
        display.SetText(4, bore_callout if label == BORE_DIAMETER and bore_callout else "")
        _assert_supplier_washer_presentation(
            display, label=label, units=units, precision=precision[label],
            expected_mm=nominal, callout=bore_callout if label == BORE_DIAMETER else None,
        )
        assert_supplier_washer_band(display, nominal_mm=nominal, band=bands[label],
                                    precision=precision[label], label=label)
    mark_dimensions_for_drawing(adapter, feature, {SOURCE_DIMENSIONS[label][1] for label in labels})


@_telemetry.traced("part.supplier_washer_source_author")
async def author_supplier_washer_references(
    adapter: Any, *, axis: Literal["y", "z"], bore_mm: float,
    outer_mm: float, thickness_mm: float, units: Literal["in", "mm"],
    precision: Mapping[str, int], bands: Mapping[str, tuple[float, float, str]],
    bore_callout: str | None = None,
) -> None:
    """Append only banded witnesses after the unchanged +Y stock recipe."""
    if set(bands) not in ({THICKNESS}, {OUTER_DIAMETER, BORE_DIAMETER, THICKNESS}):
        raise ValueError("unsupported washer supplier band coverage")
    assert_supplier_washer_body(adapter.currentModel, axis="y", bore_mm=bore_mm,
                               outer_mm=outer_mm, thickness_mm=thickness_mm)
    values = {OUTER_DIAMETER: outer_mm, BORE_DIAMETER: bore_mm, THICKNESS: thickness_mm}
    face_labels = tuple(label for label in (OUTER_DIAMETER, BORE_DIAMETER) if label in bands)
    if face_labels:
        check("create supplier washer face reference",
              await adapter.create_sketch("Top" if axis == "y" else "Front"))
        dims = SketchDims()
        for label in face_labels:
            circle = await define_circle(
                adapter, 0.0, 0.0, values[label] / 2.0, label, dims=dims,
                names=(None, None, SOURCE_DIMENSIONS[label][1]),
            )
            _construction(adapter, circle)
        await ensure_fully_defined(adapter, "supplier washer face reference")
        check("exit supplier washer face reference", await adapter.exit_sketch())
        _finish_reference(adapter, dims, FACE_FEATURE, face_labels, values=values, units=units,
                          precision=precision, bands=bands, bore_callout=bore_callout)
    check("create supplier washer thickness reference",
          await adapter.create_sketch("Front" if axis == "y" else "Top"))
    dims = SketchDims()
    end = thickness_mm if axis == "y" else -thickness_mm
    (line,) = await add_line_chain(adapter, [(outer_mm / 2.0, 0.0), (outer_mm / 2.0, end)], close=False)
    _construction(adapter, line)
    await anchor_point_to_origin(adapter, f"{line}.start", outer_mm / 2.0, 0.0, "supplier OD flank")
    dims.record(None)  # Radial placement is not another printed supplier size.
    check("orient supplier thickness witness", await adapter.add_sketch_constraint(line, None, "vertical"))
    await dimension_between(adapter, f"{line}.start", f"{line}.end", "distance", thickness_mm, THICKNESS)
    dims.record("SupplierThickness")
    await ensure_fully_defined(adapter, "supplier washer thickness reference")
    check("exit supplier washer thickness reference", await adapter.exit_sketch())
    _finish_reference(adapter, dims, THICKNESS_FEATURE, (THICKNESS,), values=values, units=units,
                      precision=precision, bands=bands, bore_callout=bore_callout)
    assert_supplier_washer_references(
        adapter, axis=axis, bore_mm=bore_mm, outer_mm=outer_mm, thickness_mm=thickness_mm,
        units=units, precision=precision, bands=bands, bore_callout=bore_callout,
    )


@_telemetry.traced("part.assert_supplier_washer_source")
def assert_supplier_washer_references(
    adapter: Any, *, axis: Literal["y", "z"], bore_mm: float,
    outer_mm: float, thickness_mm: float, units: Literal["in", "mm"],
    precision: Mapping[str, int], bands: Mapping[str, tuple[float, float, str]],
    bore_callout: str | None = None,
) -> None:
    values = {OUTER_DIAMETER: outer_mm, BORE_DIAMETER: bore_mm, THICKNESS: thickness_mm}
    part = _early_bound(adapter.currentModel, "IPartDoc")
    for label, band in bands.items():
        feature, name = SOURCE_DIMENSIONS[label]
        raw = part.FeatureByName(feature)
        display, _ = _named_dimensions(adapter, feature, {name}, feature=raw)[name]
        assert_supplier_washer_source_attachment(
            adapter, part, display, label=label, axis=axis, bore_mm=bore_mm,
            outer_mm=outer_mm, thickness_mm=thickness_mm,
        )
        _assert_supplier_washer_presentation(
            display, label=label, units=units, precision=precision[label],
            expected_mm=values[label], callout=bore_callout if label == BORE_DIAMETER else None,
        )
        assert_supplier_washer_band(display, nominal_mm=values[label], band=band,
                                    precision=precision[label], label=label)
