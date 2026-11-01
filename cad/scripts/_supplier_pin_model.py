"""Model-owned supplier pin references, bands and presentation; never alter solids.

Dowel witnesses use the exact constant that authors the solid, checked against
its native cylindrical face. A spring pin's optional mating-hole circle is
application data, not a hole cut or pin-OD tolerance. Drawings retain these model values
and bands while explicitly formatting their own imported display dimensions.
"""

from __future__ import annotations

import math
from typing import Any

import _telemetry
from _check import check
from _com import _bind, _early_bound
from _drawing_marks import mark_dimensions_for_drawing
from _drawing_precision import _named_dimension, _named_dimensions
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
    DIAMETER_DIMENSION,
    DIAMETER_FEATURE,
    MATING_HOLE_DIMENSION,
    MATING_HOLE_FEATURE,
    WALL_DIMENSION,
    WALL_FEATURE,
    SupplierPinReference,
    declares_application_hole,
)

# Literal registration is required by the hidden-reference routing guard.
REFERENCE_SKETCHES = (
    "SupplierPinDiameterReference",
    "SupplierMatingHoleReference",
    "SupplierPinWallReference",
)


def _reference_suffix(source: SupplierPinReference) -> str:
    """As _supplier_dimensions: an inch sheet already reads UNIT: IN.

    The drawing shares this model-owned text, so the package's sheet unit
    names it, not a document's: a millimetre part keeps its template's units,
    which read inches on one farm seat and millimetres on another (98296A031).
    """
    return ")" if source.units == "in" and source.sheet_unit == "in" else f" {source.units})"


def _reference_contract(
    source: SupplierPinReference, feature: str
) -> tuple[str, dict[str, Any], tuple[float, float, int] | None]:
    """Native formatter arguments and signed mm deviations; no print-value carrier."""
    band = None
    if feature == DIAMETER_FEATURE:
        if source.diameter_band is None:
            raise ValueError(f"{source.sku}: model diameter reference requires a source band")
        name = DIAMETER_DIMENSION
        value, precision, presentation = source.diameter_mm, source.diameter_precision, "diameter"
        label = f"{source.sku} supplier diameter"
        callout = "SUPPLIER LIMITS" if source.diameter_uses_limits else None
        lower, upper = source.diameter_deviations_mm
        band = (lower, upper, 3 if source.diameter_uses_limits else 2)
    elif feature == WALL_FEATURE:
        if source.wall_mm is None or source.wall_precision is None:
            raise ValueError(f"{source.sku}: incomplete supplier wall reference")
        name = WALL_DIMENSION
        value, precision, presentation = source.wall_mm, source.wall_precision, "length"
        label, callout = f"{source.sku} supplier wall", "WALL"
    elif feature == MATING_HOLE_FEATURE:
        if not declares_application_hole(source):
            raise ValueError(f"{source.sku}: no supplier mating-hole reference is declared")
        name = MATING_HOLE_DIMENSION
        lower, upper = source.application_hole_limits
        value, precision = lower * source.unit_mm, source.application_hole_precision
        presentation = "diameter"
        label = f"{source.sku} supplier mating-hole application"
        callout = "MATING HOLE\nSUPPLIER APPLICATION ONLY"
        band = (0.0, (upper - lower) * source.unit_mm, 3)
    else:
        raise ValueError(f"unknown supplier pin reference {feature!r}")
    return name, {
        "label": label, "units": source.units, "precision": precision,
        "expected_mm": value, "presentation": presentation, "callout": callout,
    }, band


def _cylinder_radii_mm(model: Any, axis: int, *, label: str) -> tuple[float, ...]:
    bodies = tuple(_early_bound(model, "IPartDoc").GetBodies2(0, False) or ())
    if len(bodies) != 1 or bodies[0] is None:
        raise RuntimeError(f"{label}: source must have exactly one solid body")
    radii = []
    for raw_face in _early_bound(bodies[0], "IBody2").GetFaces() or ():
        raw_surface = _early_bound(raw_face, "IFace2").GetSurface()
        if raw_surface is None:
            raise RuntimeError(f"{label}: source face has no surface")
        surface = _early_bound(raw_surface, "ISurface")
        if not surface.IsCylinder():
            continue
        parameters = tuple(float(value) for value in (surface.CylinderParams or ()))
        if len(parameters) != 7 or not all(math.isfinite(value) for value in parameters):
            raise RuntimeError(f"{label}: invalid native cylinder parameters")
        if (
            abs(abs(parameters[axis + 3]) - 1.0) < 1e-8
            and all(abs(parameters[index]) < 1e-8 for index in range(3) if index != axis)
            and parameters[6] > 0.0
        ):
            radii.append(parameters[6] * 1000.0)
    if not radii:
        raise RuntimeError(f"{label}: no real coaxial cylindrical face")
    return tuple(radii)


def _point_mm(raw: Any, *, label: str) -> tuple[float, float, float]:
    if raw is None:
        raise RuntimeError(f"{label}: source sketch has a missing point")
    point = _early_bound(raw, "ISketchPoint")
    xyz = (float(point.X) * 1000.0, float(point.Y) * 1000.0, float(point.Z) * 1000.0)
    if not all(math.isfinite(value) for value in xyz):
        raise RuntimeError(f"{label}: source sketch has an invalid point")
    return xyz


def _reference_entities(model: Any, feature: str, source: SupplierPinReference) -> tuple[Any, ...]:
    """Resolve intended named sketch geometry, never an import's own attachments."""
    raw_feature = _early_bound(model, "IPartDoc").FeatureByName(feature)
    if raw_feature is None:
        raise RuntimeError(f"{source.sku}: missing model reference {feature}")
    sketch = _early_bound(_early_bound(raw_feature, "IFeature").GetSpecificFeature2(), "ISketch")
    segments = tuple(sketch.GetSketchSegments() or ())
    if len(segments) != 1:
        raise RuntimeError(f"{source.sku}: {feature} must contain one native witness entity")
    segment = _early_bound(segments[0], "ISketchSegment")
    if not segment.ConstructionGeometry:
        raise RuntimeError(f"{source.sku}: {feature} is not reference construction geometry")
    if feature == WALL_FEATURE:
        if int(segment.GetType()) != 0:  # swSketchLINE
            raise RuntimeError(f"{source.sku}: wall witness is not a line")
        line = _early_bound(segment, "ISketchLine")
        endpoints = (line.GetStartPoint2(), line.GetEndPoint2())
        points = tuple(_point_mm(point, label=feature) for point in endpoints)
        radii = _cylinder_radii_mm(model, 0, label=source.sku)
        expected_radii = (source.diameter_mm / 2.0 - source.wall_mm, source.diameter_mm / 2.0)
        if (
            not math.isclose(math.dist(*points), source.wall_mm, rel_tol=0.0, abs_tol=1e-6)
            or any(not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-6)
                   for actual, expected in zip(sorted(math.dist(point, (0.0, 0.0, 0.0)) for point in points),
                                               expected_radii, strict=True))
            or not math.isclose(min(radii), expected_radii[0], rel_tol=0.0, abs_tol=1e-6)
            or not math.isclose(max(radii), expected_radii[1], rel_tol=0.0, abs_tol=1e-6)
        ):
            raise RuntimeError(f"{source.sku}: wall witness does not span the real tube radii")
        return endpoints
    if int(segment.GetType()) != 1:  # swSketchARC
        raise RuntimeError(f"{source.sku}: {feature} is not a circle")
    circle = _early_bound(segment, "ISketchArc")
    if int(circle.IsCircle()) != 1:
        raise RuntimeError(f"{source.sku}: {feature} is not a complete circle")
    center = _point_mm(circle.GetCenterPoint2(), label=feature)
    diameter = 2.0 * float(circle.GetRadius()) * 1000.0
    if feature == DIAMETER_FEATURE:
        expected_diameter, expected_offset = source.diameter_mm, 0.0
        actual_solid_diameter = 2.0 * max(_cylinder_radii_mm(model, 1, label=source.sku))
        if not math.isclose(diameter, actual_solid_diameter, rel_tol=0.0, abs_tol=1e-6):
            raise RuntimeError(f"{source.sku}: native OD witness differs from real cylindrical solid")
    elif feature == MATING_HOLE_FEATURE:
        expected_diameter = source.application_hole_limits[0] * source.unit_mm
        expected_offset = math.hypot(*source.application_hole_center)
    else:
        raise ValueError(f"unknown pin reference {feature!r}")
    if (
        not math.isclose(diameter, expected_diameter, rel_tol=0.0, abs_tol=1e-6)
        or not math.isclose(math.dist(center, (0.0, 0.0, 0.0)), expected_offset,
                            rel_tol=0.0, abs_tol=1e-6)
    ):
        raise RuntimeError(f"{source.sku}: named {feature} geometry differs from its source")
    return (segment,)


def assert_supplier_pin_model_reference(
    adapter: Any, model: Any, display: Any, feature: str, source: SupplierPinReference,
    *, view: Any | None,
) -> None:
    """Read the actual model witness and attachments in their owning context."""
    name, kwargs, band = _reference_contract(source, feature)
    display = _early_bound(display, "IDisplayDimension")
    kinds = (6,) if kwargs["presentation"] == "diameter" else (2, 11, 12)
    if int(display.Type2) not in kinds:
        raise RuntimeError(f"{source.sku}: {name} has the wrong native source type")
    raw_feature = _early_bound(model, "IPartDoc").FeatureByName(feature)
    if raw_feature is None:
        raise RuntimeError(f"{source.sku}: {name} has no named model owner")
    _, source_dimension = _named_dimensions(adapter, feature, {name}, feature=raw_feature)[name]
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    # This contract also applies to hidden MODEL references. The shared
    # supplier formatter deliberately requires a visible drawing-view owner,
    # so source presentation is authored/read here without that drawing guard.
    measured_mm = abs(float(dimension.SystemValue)) * 1000.0
    prefix = "(<MOD-DIAM>" if kwargs["presentation"] == "diameter" else "("
    if not math.isfinite(measured_mm) or not math.isclose(
        measured_mm, kwargs["expected_mm"], rel_tol=0.0, abs_tol=1e-5
    ):
        raise RuntimeError(
            f"{source.sku}: {name} native source value/presentation changed "
            f"(native_value_mm: actual={measured_mm!r}, expected={kwargs['expected_mm']!r})"
        )
    presentation_fields = (
        ("use_document_units", lambda: bool(display.GetUseDocUnits()), False),
        ("units", lambda: int(display.GetUnits()), {"mm": 0, "in": 3}[source.units]),
        ("fraction_base", lambda: int(display.GetFractionBase()), 1),
        ("primary_precision", lambda: int(display.GetPrimaryPrecision2()), kwargs["precision"]),
        ("show_parentheses", lambda: bool(display.ShowParenthesis), False),
        ("override", lambda: bool(display.GetOverride()), False),
        ("show_native_value", lambda: bool(display.ShowDimensionValue), True),
        ("prefix", lambda: str(display.GetText(1) or ""), prefix),
        ("suffix", lambda: str(display.GetText(2) or ""), _reference_suffix(source)),
        ("below_callout", lambda: str(display.GetText(4) or ""), kwargs["callout"] or ""),
    )
    for field, read, expected in presentation_fields:
        actual = read()
        if actual != expected:
            raise RuntimeError(
                f"{source.sku}: {name} native source value/presentation changed "
                f"({field}: actual={actual!r}, expected={expected!r})"
            )
    # Native imported dimensions may carry a drawing-context document suffix.
    # The resolved model owner plus dimension/feature names establish identity.
    expected_owner = [name, feature]
    if (
        str(dimension.FullName).split("@")[:2] != expected_owner
        or str(source_dimension.FullName).split("@")[:2] != expected_owner
    ):
        raise RuntimeError(f"{source.sku}: imported {name} belongs to the wrong model dimension")
    expected = _reference_entities(model, feature, source)
    entity_interface = "ISketchPoint" if feature == WALL_FEATURE else "ISketchSegment"
    if view is not None:
        mapped = tuple(view.GetCorresponding(entity) for entity in expected)
        if any(entity is None for entity in mapped):
            raise RuntimeError(f"{source.sku}: {name} has no intended witness in its drawing view")
        expected = tuple(_early_bound(_bind(entity, entity_interface), entity_interface)
                         for entity in mapped)
        if len(expected) == 2 and int(adapter.swApp.IsSame(*expected)) != 0:
            raise RuntimeError(f"{source.sku}: {name} drawing witness endpoints are not distinct")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    remaining = list(annotation.GetAttachedEntities3() or ())
    if annotation.IsDangling() or len(remaining) != len(expected):
        raise RuntimeError(f"{source.sku}: {name} has dangling or unexpected source attachments")
    for entity in expected:
        matches = [
            index for index, actual in enumerate(remaining)
            if actual is not None
            and int(adapter.swApp.IsSame(
                _early_bound(_bind(actual, entity_interface), entity_interface), entity
            )) == 1
        ]
        if len(matches) != 1:
            raise RuntimeError(f"{source.sku}: {name} does not attach to its intended witness")
        remaining.pop(matches[0])
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if band is None:
        if int(tolerance.Type) != 0:
            raise RuntimeError(f"{source.sku}: {name} gained an unsourced tolerance")
    else:
        lower, upper, kind = band
        if (
            int(tolerance.Type) != kind
            or not math.isclose(float(tolerance.GetMinValue()), lower / 1000.0, rel_tol=0.0, abs_tol=1e-12)
            or not math.isclose(float(tolerance.GetMaxValue()), upper / 1000.0, rel_tol=0.0, abs_tol=1e-12)
            or int(display.GetPrimaryTolPrecision2()) != kwargs["precision"]
        ):
            raise RuntimeError(f"{source.sku}: {name} native band/precision changed")


def _construction(adapter: Any, entity: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity], "ISketchSegment")
    segment.ConstructionGeometry = True
    if segment.ConstructionGeometry is not True:
        raise RuntimeError(f"{entity}: source-reference construction state did not persist")


def _finish_reference(
    adapter: Any, dims: SketchDims, feature: str, source: SupplierPinReference
) -> None:
    name_last_feature(adapter, feature)
    dims.apply(adapter, feature)
    name, kwargs, band = _reference_contract(source, feature)
    display, dimension = _named_dimension(adapter, feature, name)
    if band is not None:
        lower, upper, kind = band
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = kind
        if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
            raise RuntimeError(f"{source.sku}: {name} source band was rejected")
    if display.GetOverride() or not display.ShowDimensionValue:
        raise RuntimeError(f"{source.sku}: {name} hides or overrides its native source value")
    # swDECIMAL=1; swUnitsDecimalRounding_HalfAway=0. No numeric text or
    # SystemValue replacement: only the source-owned units, places and ink.
    if display.SetUnits2(False, {"mm": 0, "in": 3}[source.units], 1, 0, False, 0) != 0:
        raise RuntimeError(f"{source.sku}: {name} source units were rejected")
    precision = kwargs["precision"]
    if display.SetPrecision3(precision, -1, precision if band is not None else -1, -1) != 0:
        raise RuntimeError(f"{source.sku}: {name} source primary/tolerance precision was rejected")
    display.ShowParenthesis = False
    display.SetText(1, "(<MOD-DIAM>" if kwargs["presentation"] == "diameter" else "(")
    display.SetText(2, _reference_suffix(source))
    display.SetText(4, kwargs["callout"] or "")
    mark_dimensions_for_drawing(adapter, feature, {name})
    assert_supplier_pin_model_reference(
        adapter, adapter.currentModel, display, feature, source, view=None,
    )


@_telemetry.traced("drawing.supplier_pin_dowel_source_author")
async def author_supplier_dowel_references(adapter: Any, source: SupplierPinReference) -> None:
    """Exact nominal OD witness in the Top end-view plane; never a print literal."""
    if source.diameter_band is None:
        raise ValueError(f"{source.sku}: dowel diameter source band is missing")
    check("create supplier dowel OD reference", await adapter.create_sketch("Top"))
    dims = SketchDims()
    circle = await define_circle(
        adapter, 0.0, 0.0, source.diameter_mm / 2.0,
        "supplier exact nominal dowel OD", dims=dims, names=(None, None, DIAMETER_DIMENSION),
    )
    _construction(adapter, circle)
    await ensure_fully_defined(adapter, "supplier exact nominal dowel OD")
    check("exit supplier dowel OD reference", await adapter.exit_sketch())
    _finish_reference(adapter, dims, DIAMETER_FEATURE, source)
    blank_reference_sketches(adapter, (DIAMETER_FEATURE,))
    assert_supplier_dowel_references(adapter, adapter.currentModel, source)


@_telemetry.traced("drawing.supplier_pin_dowel_source_readback")
def assert_supplier_dowel_references(
    adapter: Any, model: Any, source: SupplierPinReference,
) -> None:
    feature = _early_bound(model, "IPartDoc").FeatureByName(DIAMETER_FEATURE)
    if feature is None:
        raise RuntimeError(f"{source.sku}: missing model reference {DIAMETER_FEATURE}")
    display, _ = _named_dimensions(
        adapter, DIAMETER_FEATURE, {DIAMETER_DIMENSION}, feature=feature,
    )[DIAMETER_DIMENSION]
    assert_supplier_pin_model_reference(
        adapter, model, display, DIAMETER_FEATURE, source, view=None,
    )


@_telemetry.traced("drawing.supplier_pin_source_author")
async def author_supplier_spring_pin_references(adapter: Any, source: SupplierPinReference) -> None:
    """Author and fully format wall plus any separate supplier-application witness."""
    _reference_contract(source, WALL_FEATURE)
    application_hole = declares_application_hole(source)
    if application_hole:
        _reference_contract(source, MATING_HOLE_FEATURE)
    inner_radius = source.diameter_mm / 2.0 - source.wall_mm
    outer_radius = source.diameter_mm / 2.0
    check("create supplier wall reference", await adapter.create_sketch("Right"))
    dims = SketchDims()
    (wall,) = await add_line_chain(adapter, [(inner_radius, 0.0), (outer_radius, 0.0)], close=False)
    _construction(adapter, wall)
    await anchor_point_to_origin(adapter, f"{wall}.start", inner_radius, 0.0, "source wall inner radius")
    dims.record(None)
    check("orient radial wall witness", await adapter.add_sketch_constraint(wall, None, "horizontal"))
    await dimension_between(
        adapter, f"{wall}.start", f"{wall}.end", "distance", source.wall_mm, "supplier wall"
    )
    dims.record(WALL_DIMENSION)
    await ensure_fully_defined(adapter, "supplier wall radial witness")
    check("exit supplier wall reference", await adapter.exit_sketch())
    _finish_reference(adapter, dims, WALL_FEATURE, source)

    if application_hole:
        lower = source.application_hole_limits[0]
        check("create supplier mating-hole reference", await adapter.create_sketch("Right"))
        dims = SketchDims()
        circle = await define_circle(
            adapter, *source.application_hole_center, lower * source.unit_mm / 2.0,
            "supplier mating-hole application", dims=dims, names=(None, None, MATING_HOLE_DIMENSION),
        )
        _construction(adapter, circle)
        await ensure_fully_defined(adapter, "supplier mating-hole application diagram")
        check("exit supplier mating-hole reference", await adapter.exit_sketch())
        _finish_reference(adapter, dims, MATING_HOLE_FEATURE, source)
        blank_reference_sketches(adapter, (WALL_FEATURE, MATING_HOLE_FEATURE))
    else:
        blank_reference_sketches(adapter, (WALL_FEATURE,))
    assert_supplier_spring_pin_references(adapter, adapter.currentModel, source)


@_telemetry.traced("drawing.supplier_pin_source_readback")
def assert_supplier_spring_pin_references(
    adapter: Any, model: Any, source: SupplierPinReference,
) -> None:
    references = [(WALL_FEATURE, WALL_DIMENSION)]
    if declares_application_hole(source):
        references.append((MATING_HOLE_FEATURE, MATING_HOLE_DIMENSION))
    elif _early_bound(model, "IPartDoc").FeatureByName(MATING_HOLE_FEATURE) is not None:
        raise RuntimeError(f"{source.sku}: model carries an undeclared supplier mating-hole reference")
    for feature_name, name in references:
        feature = _early_bound(model, "IPartDoc").FeatureByName(feature_name)
        if feature is None:
            raise RuntimeError(f"{source.sku}: missing model reference {feature_name}")
        display, _ = _named_dimensions(adapter, feature_name, {name}, feature=feature)[name]
        assert_supplier_pin_model_reference(
            adapter, model, display, feature_name, source, view=None,
        )
