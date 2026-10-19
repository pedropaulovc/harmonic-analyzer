"""Native nominal dimension diagrams, never reconstructed supplier part shapes.

The supplier drawings and read-only native inspections recorded in the pure
specs establish the exact sizes and axial datums. The diagrams comprise a plan
annulus, an OD-by-free-height envelope, a nominal flat strip and application
gauges. None represents a wave, bow, cone, loaded spring or physical free stock.
No vendor body, surface, curve coefficients or downloaded asset is retained.

Only ``Supplier-Dimensions`` contains the diagrams, with zero solid bodies.
The installed +Z annuli/cone, assembly references, transforms and existing
configurations remain owned by the original recipes. Diagram sketches are
saved hidden and are shown only in their assigned drawing views.
"""

from __future__ import annotations

from functools import partial
import math
from typing import Any

from _check import check
from _com import _early_bound
from _drawing_marks import mark_dimensions_for_drawing
from _drawing_precision import _named_dimension
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _feature_tree import name_last_feature
from _sketch import (
    SketchDims,
    _record_origin_anchor,
    add_line_chain,
    anchor_point_to_origin,
    blank_reference_sketches,
    ensure_fully_defined,
)
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from _supplier_spring_reference import (
    ReferenceState,
    SUPPLIER_DIAGRAM_CONFIGURATION,
    add_supplier_reference_configurations,
)

SUPPLIER_DIMENSION_NAMES = {
    "ID": "SupplierID",
    "OD": "SupplierOD",
    "FREE_HEIGHT": "SupplierFreeHeight",
    "THICKNESS": "SupplierThickness",
    "WORKING_HEIGHT": "SupplierWorkingHeight",
    "WORKING_DEFLECTION": "SupplierWorkingDeflection",
    "SHAFT_DIA": "SupplierShaftDia",
}
SUPPLIER_DIMENSIONS_BY_FEATURE = {
    "DiscSupplierPlan": ("SupplierID", "SupplierOD"),
    "DiscSupplierHeight": ("SupplierFreeHeight",),
    "DiscSupplierStrip": ("SupplierThickness",),
    "DiscSupplierApplication": ("SupplierWorkingHeight", "SupplierWorkingDeflection"),
    "DiscSupplierShaft": ("SupplierShaftDia",),
}


def source_free_height_limits(spec: Any) -> tuple[float, float]:
    """Supplier axial datums retained by the nominal free-height envelope."""
    if spec.SKU == "9714K24":
        return -spec.THICKNESS / 2.0, spec.FREE_HEIGHT - spec.THICKNESS / 2.0
    if spec.SKU in ("9714K392", "9715K43"):
        return -spec.FREE_HEIGHT / 2.0, spec.FREE_HEIGHT / 2.0
    raise ValueError(f"unsupported supplier disc spring {spec.SKU!r}")


def supplier_application_planes(spec: Any) -> tuple[float, float, float]:
    """Shared baseline, compressed gauge plane and free-upper gauge plane.

    These exact geometric datums define application dimensions without claiming
    that a spring's deformation at the working load has been modelled.
    """
    baseline, free_upper = source_free_height_limits(spec)
    return baseline, baseline + spec.WORKING_HEIGHT, free_upper


def _nominal_side_profiles(spec: Any) -> tuple[
    tuple[tuple[float, float], tuple[float, float]],
    tuple[tuple[float, float], tuple[float, float]],
]:
    """Envelope and flat-strip bounds used by both authoring and view fitting."""
    low, high = source_free_height_limits(spec)
    envelope = ((-spec.OD / 2.0, low), (spec.OD / 2.0, high))
    if spec.SKU == "9714K24":
        # Source strip datum: .2286 -> .381 mm, not the envelope baseline.
        middle = (spec.FREE_HEIGHT - spec.THICKNESS) / 2.0
        left, strip_low = spec.ID / 2.0, middle - spec.THICKNESS / 2.0
    else:
        left, strip_low = 0.0, -spec.THICKNESS / 2.0
    strip = (
        (left, strip_low),
        (left + (spec.OD - spec.ID) / 2.0, strip_low + spec.THICKNESS),
    )
    return envelope, strip


def supplier_diagram_extents(spec: Any) -> dict[str, tuple[float, float]]:
    """Expected 1:1 view widths/heights from the authored nominal geometry."""
    profiles = _nominal_side_profiles(spec)
    corners = [point for bounds in profiles for point in bounds]
    side_width = max(x for x, _y in corners) - min(x for x, _y in corners)
    side_height = max(y for _x, y in corners) - min(y for _x, y in corners)
    application = set(spec.SUPPLIER_APPLICATION_DIMENSIONS)
    diameters = [spec.ID, spec.OD]
    if "SHAFT_DIA" in application:
        diameters.append(spec.SHAFT_DIA)
    plan_diameter = max(diameters)
    extents = {
        "free_front": (side_width, side_height),
        "free_top": (plan_diameter, plan_diameter),
    }
    if application.intersection(("WORKING_HEIGHT", "WORKING_DEFLECTION")):
        baseline, compressed, free_upper = supplier_application_planes(spec)
        upper = free_upper if "WORKING_DEFLECTION" in application else compressed
        extents["free_right"] = (spec.OD, upper - baseline)
    return extents


async def _application_line(
    adapter: Any,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    name: str | None,
    dims: SketchDims,
    anchored: bool = False,
) -> str:
    """Dimension one axis-aligned application-gauge segment."""
    line, = await add_line_chain(adapter, [start, end], close=False)
    if not anchored:
        await anchor_point_to_origin(adapter, f"{line}.start", *start, "supplier gauge datum")
        _record_origin_anchor(dims, *start, None, None, None, None)
    dx, dy = end[0] - start[0], end[1] - start[1]
    if dx != 0.0 and dy != 0.0:
        raise ValueError("supplier application gauges must be axis-aligned")
    relation = "vertical_points" if dx == 0.0 else "horizontal_points"
    check(
        "align supplier application gauge",
        await adapter.add_sketch_constraint(f"{line}.start", f"{line}.end", relation),
    )
    check(
        "dimension supplier application gauge",
        await adapter.add_sketch_dimension(line, None, "linear", math.hypot(dx, dy)),
    )
    dims.record(name)
    return line


async def _nominal_rectangle(
    adapter: Any,
    lower_left: tuple[float, float],
    upper_right: tuple[float, float],
    *,
    height_name: str,
    dims: SketchDims,
) -> None:
    """A fully constrained size envelope or flat strip, not a spring section."""
    left, low = lower_left
    right, high = upper_right
    points = [(left, low), (left, high), (right, high), (right, low)]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter, lines, points, label="supplier nominal dimension diagram",
        dims=dims, names=[height_name, None],
    )


async def _finish_reference(
    adapter: Any, feature: str, dims: SketchDims, semantics: tuple[str, ...], *,
    spec: Any, segment_lengths_mm: tuple[float, ...], circles: bool = False,
) -> None:
    sketch = _early_bound(adapter.currentModel.GetActiveSketch2(), "ISketch")
    segments = tuple(
        _early_bound(raw, "ISketchSegment") for raw in (sketch.GetSketchSegments() or ())
    )
    if len(segments) != len(segment_lengths_mm):
        raise RuntimeError(f"{feature}: native nominal diagram segments changed")
    for segment in segments:
        # swSketchSegments_e: full circles are ARC (1), straight lines LINE (0).
        if int(segment.GetType()) != (1 if circles else 0):
            raise RuntimeError(f"{feature}: native nominal diagram segment type changed")
        if circles and int(_early_bound(segment, "ISketchArc").IsCircle()) != 1:
            raise RuntimeError(f"{feature}: nominal plan/gauge requires complete circles")
        segment.ConstructionGeometry = False
        if segment.ConstructionGeometry:
            raise RuntimeError(f"{feature}: nominal diagram must use continuous geometry")
    await ensure_fully_defined(adapter, feature)
    lengths = sorted(float(segment.GetLength()) * 1000.0 for segment in segments)
    if not all(
        math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-8)
        for actual, expected in zip(lengths, sorted(segment_lengths_mm), strict=True)
    ):
        raise RuntimeError(f"{feature}: native nominal diagram segment lengths changed")
    check(f"exit {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    dims.apply(adapter, feature)
    names = {SUPPLIER_DIMENSION_NAMES[key] for key in semantics}
    mark_dimensions_for_drawing(adapter, feature, names)
    for key in semantics:
        display, dimension = _named_dimension(adapter, feature, SUPPLIER_DIMENSION_NAMES[key])
        if not display.MarkedForDrawing or not math.isclose(
            float(dimension.SystemValue) * 1000.0,
            float(getattr(spec, key)),
            rel_tol=0.0,
            abs_tol=1e-8,
        ):
            raise RuntimeError(f"{feature}: exact supplier dimension {key} did not persist")


async def author_supplier_references(adapter: Any, *, spec: Any) -> tuple[str, ...]:
    """Author hidden native nominal diagrams and explicitly separate gauges."""
    features = []
    dims = SketchDims()
    check("create supplier nominal plan diagram", await adapter.create_sketch("Top"))
    for key in ("ID", "OD"):
        await define_circle(
            adapter, 0.0, 0.0, getattr(spec, key) / 2.0,
            f"{spec.SKU} nominal {key}", dims=dims,
            names=(None, None, SUPPLIER_DIMENSION_NAMES[key]),
        )
    await _finish_reference(
        adapter, "DiscSupplierPlan", dims, ("ID", "OD"), spec=spec,
        segment_lengths_mm=(math.pi * spec.ID, math.pi * spec.OD), circles=True,
    )
    features.append("DiscSupplierPlan")
    for key in ("ID", "OD"):
        band = getattr(spec, f"{key}_BAND", None)
        if band is not None:
            upper, lower = band
            if math.isclose(upper, -lower, rel_tol=0.0, abs_tol=1e-12):
                set_dimension_symmetric_tolerance(
                    adapter, "DiscSupplierPlan", SUPPLIER_DIMENSION_NAMES[key], upper
                )
            else:
                set_dimension_bilateral_tolerance(
                    adapter, "DiscSupplierPlan", SUPPLIER_DIMENSION_NAMES[key],
                    lower, upper, places=3,
                )

    envelope, strip = _nominal_side_profiles(spec)
    # A closed rectangle conveys only OD x free height, never the spring shape.
    dims = SketchDims()
    check("create supplier nominal size envelope", await adapter.create_sketch("Front"))
    await _nominal_rectangle(
        adapter, *envelope,
        height_name=SUPPLIER_DIMENSION_NAMES["FREE_HEIGHT"], dims=dims,
    )
    await _finish_reference(
        adapter, "DiscSupplierHeight", dims, ("FREE_HEIGHT",), spec=spec,
        segment_lengths_mm=(spec.OD, spec.OD, spec.FREE_HEIGHT, spec.FREE_HEIGHT),
    )
    features.append("DiscSupplierHeight")

    dims = SketchDims()
    check("create supplier nominal strip diagram", await adapter.create_sketch("Front"))
    await _nominal_rectangle(
        adapter, *strip,
        height_name=SUPPLIER_DIMENSION_NAMES["THICKNESS"], dims=dims,
    )
    strip_width = strip[1][0] - strip[0][0]
    await _finish_reference(
        adapter, "DiscSupplierStrip", dims, ("THICKNESS",), spec=spec,
        segment_lengths_mm=(strip_width, strip_width, spec.THICKNESS, spec.THICKNESS),
    )
    features.append("DiscSupplierStrip")

    application = set(spec.SUPPLIER_APPLICATION_DIMENSIONS)
    if application.intersection(("WORKING_HEIGHT", "WORKING_DEFLECTION")):
        baseline, compressed, free_upper = supplier_application_planes(spec)
        left, right = -spec.OD / 2.0, spec.OD / 2.0
        dims = SketchDims()
        check("create supplier application planes", await adapter.create_sketch("Right"))
        await _application_line(adapter, (left, baseline), (right, baseline), name=None, dims=dims)
        await _application_line(
            adapter, (left, baseline), (left, compressed),
            name=(
                SUPPLIER_DIMENSION_NAMES["WORKING_HEIGHT"]
                if "WORKING_HEIGHT" in application else None
            ),
            dims=dims, anchored=True,
        )
        await _application_line(
            adapter, (left, compressed), (right, compressed), name=None, dims=dims, anchored=True
        )
        height_semantics = ("WORKING_HEIGHT",) if "WORKING_HEIGHT" in application else ()
        if "WORKING_DEFLECTION" in application:
            await _application_line(
                adapter, (left, compressed), (left, free_upper),
                name=SUPPLIER_DIMENSION_NAMES["WORKING_DEFLECTION"], dims=dims, anchored=True,
            )
            await _application_line(
                adapter, (left, free_upper), (right, free_upper), name=None, dims=dims, anchored=True
            )
            height_semantics += ("WORKING_DEFLECTION",)
        gauge_lengths = (spec.OD, spec.OD, spec.WORKING_HEIGHT)
        if "WORKING_DEFLECTION" in application:
            gauge_lengths += (spec.OD, spec.WORKING_DEFLECTION)
        await _finish_reference(
            adapter, "DiscSupplierApplication", dims, height_semantics, spec=spec,
            segment_lengths_mm=gauge_lengths,
        )
        features.append("DiscSupplierApplication")
    if "SHAFT_DIA" in application:
        dims = SketchDims()
        check("create supplier mating-shaft gauge", await adapter.create_sketch("Top"))
        await define_circle(
            adapter, 0.0, 0.0, spec.SHAFT_DIA / 2.0, "nominal mating shaft, not spring bore",
            dims=dims, names=(None, None, SUPPLIER_DIMENSION_NAMES["SHAFT_DIA"]),
        )
        await _finish_reference(
            adapter, "DiscSupplierShaft", dims, ("SHAFT_DIA",), spec=spec,
            segment_lengths_mm=(math.pi * spec.SHAFT_DIA,), circles=True,
        )
        features.append("DiscSupplierShaft")
    blank_reference_sketches(adapter, tuple(features))
    return tuple(features)


async def add_supplier_disc_diagram(adapter: Any, *, spec: Any) -> None:
    """Add zero-solid nominal diagrams without altering an installed state."""
    await add_supplier_reference_configurations(
        adapter,
        (ReferenceState(
            name=SUPPLIER_DIAGRAM_CONFIGURATION,
            author=None,
            references=partial(author_supplier_references, spec=spec),
            body_count=0,
            kind="diagram",
        ),),
        body_count=1,
    )
