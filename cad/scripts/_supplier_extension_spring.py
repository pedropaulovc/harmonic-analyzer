"""Native source-size references for the two reconstructed extension springs.

The hidden length chord is the supplier's inside-hook/inside-loop measurement
in its +X frame, not an installed span or a bounding-box length. Circular
references are the author's exact nominal coil envelope and wire section;
they are not measurements inferred from the supplier display model's pitch.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name

from _check import check
from _com import _early_bound
from _drawing_hidden_sketches import _show_hidden_owners, curate_view_dimensions
from _drawing_marks import mark_dimensions_for_drawing
from _drawing_precision import _named_dimension
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _feature_tree import name_last_feature
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_spring_drawing import (
    assert_supplier_configuration_value,
    reacquire_supplier_dimensions,
)
from _supplier_spring_reference import (
    ReferenceState,
    SUPPLIER_FREE_CONFIGURATION,
    SUPPLIER_MAX_CONFIGURATION,
    add_supplier_reference_configurations,
)

FREE_FEATURE = "SupplierFreeLengthReference"
MAX_FEATURE = "SupplierMaximumLengthReference"
SECTION_FEATURE = "SupplierNominalSections"
SOURCE_FEATURES = {
    "free_front": (FREE_FEATURE,),
    "free_right": (SECTION_FEATURE,),
    "max_front": (MAX_FEATURE,),
}
FREE_LENGTH = "SupplierFreeLength"
MAX_LENGTH = "SupplierMaximumLength"
COIL_OD = "SupplierCoilOD"
WIRE_DIA = "SupplierWireDiameter"
DIMENSIONS_BY_FEATURE = {
    FREE_FEATURE: {FREE_LENGTH},
    MAX_FEATURE: {MAX_LENGTH},
    SECTION_FEATURE: {COIL_OD, WIRE_DIA},
}


async def _length_reference(
    adapter: Any, feature: str, name: str, length: float
) -> str:
    check(f"create {feature}", await adapter.create_sketch("Front"))
    dims = SketchDims()
    set_sketch_direct_db(adapter, True)
    try:
        line = check(
            f"create {name}", await adapter.add_line(-length / 2, 0.0, length / 2, 0.0)
        )
    finally:
        set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not segment.ConstructionGeometry:
        raise RuntimeError(f"{name}: source length chord must be construction geometry")
    check(
        f"horizontal {name}",
        await adapter.add_sketch_constraint(line, None, "horizontal"),
    )
    await dimension_between(
        adapter, f"{line}.start", f"{line}.end", "horizontal_distance", length, name
    )
    dims.record(name)
    await anchor_point_to_origin(adapter, f"{line}.start", -length / 2, 0.0, name)
    dims.record(f"{name}HalfSpan")
    await ensure_fully_defined(adapter, feature)
    check(f"exit {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    dims.apply(adapter, feature)
    mark_dimensions_for_drawing(adapter, feature, {name})
    blank_reference_sketches(adapter, (feature,))
    return feature


async def _sections(
    adapter: Any,
    *,
    coil_od_mm: float,
    wire_dia_mm: float,
    od_tolerance_mm: float | None,
    od_tolerance_precision: int | None,
) -> str:
    check("create supplier nominal sections", await adapter.create_sketch("Right"))
    dims = SketchDims()
    for name, diameter, center in (
        (COIL_OD, coil_od_mm, (0.0, 0.0)),
        # Right-plane sketch X = model -Z: the native coil seed is at +Z.
        (WIRE_DIA, wire_dia_mm, (-(coil_od_mm - wire_dia_mm) / 2, 0.0)),
    ):
        entity = await define_circle(
            adapter,
            *center,
            diameter / 2,
            name,
            dims=dims,
            names=(f"{name}CenterX", f"{name}CenterY", name),
        )
        segment = _early_bound(adapter._sketch_entities[entity], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not segment.ConstructionGeometry:
            raise RuntimeError(f"{name}: source section is not construction geometry")
    await ensure_fully_defined(adapter, SECTION_FEATURE)
    check("exit supplier nominal sections", await adapter.exit_sketch())
    name_last_feature(adapter, SECTION_FEATURE)
    dims.apply(adapter, SECTION_FEATURE)
    mark_dimensions_for_drawing(adapter, SECTION_FEATURE, {COIL_OD, WIRE_DIA})
    if od_tolerance_mm is not None:
        if od_tolerance_precision is None:
            raise ValueError("supplier OD tolerance precision is required")
        set_dimension_symmetric_tolerance(
            adapter, SECTION_FEATURE, COIL_OD, od_tolerance_mm
        )
        display, _ = _named_dimension(adapter, SECTION_FEATURE, COIL_OD)
        # The band is source-owned; preserve its inch spelling on import.
        if display.SetUnits2(False, 3, 1, 0, False, 0) != 0:
            raise RuntimeError("supplier OD source units were rejected")
        status = display.SetPrecision3(-1, -1, od_tolerance_precision, -1)
        if status != 0:
            raise RuntimeError(
                f"supplier OD source tolerance precision was rejected (status {status})"
            )
        if int(display.GetPrimaryTolPrecision2()) != od_tolerance_precision:
            raise RuntimeError("supplier OD source tolerance precision did not persist")
    blank_reference_sketches(adapter, (SECTION_FEATURE,))
    return SECTION_FEATURE


async def add_extension_spring_references(
    adapter: Any,
    *,
    free_length_mm: float,
    max_length_mm: float,
    coil_od_mm: float,
    wire_dia_mm: float,
    body_count: int,
    od_tolerance_mm: float | None = None,
    od_tolerance_precision: int | None = None,
) -> None:
    """Add nominal source gauges only; never author free/max physical solids."""

    async def free_refs(target: Any) -> tuple[str, ...]:
        length = await _length_reference(
            target, FREE_FEATURE, FREE_LENGTH, free_length_mm
        )
        section = await _sections(
            target,
            coil_od_mm=coil_od_mm,
            wire_dia_mm=wire_dia_mm,
            od_tolerance_mm=od_tolerance_mm,
            od_tolerance_precision=od_tolerance_precision,
        )
        return length, section

    async def maximum_refs(target: Any) -> tuple[str, ...]:
        return (
            await _length_reference(target, MAX_FEATURE, MAX_LENGTH, max_length_mm),
        )

    await add_supplier_reference_configurations(
        adapter,
        (
            ReferenceState(
                SUPPLIER_FREE_CONFIGURATION,
                None,
                free_refs,
                body_count=0,
                kind="diagram",
            ),
            ReferenceState(
                SUPPLIER_MAX_CONFIGURATION,
                None,
                maximum_refs,
                body_count=0,
                kind="diagram",
            ),
        ),
        body_count=body_count,
    )


def prepare_extension_spring_diagrams(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    reference_bounds: Callable[[str], tuple[float, float, float, float]],
) -> tuple[Callable[[], None], ...]:
    """Show only assigned construction gauges before native geometry fitting."""
    if set(views) != {*SOURCE_FEATURES, "installed_iso"}:
        raise RuntimeError(
            "extension spring diagram needs free, section, maximum and installed views"
        )
    for key, names in SOURCE_FEATURES.items():
        if set(_show_hidden_owners(adapter, views[key], names, view_label=key)) != set(
            names
        ):
            raise RuntimeError(f"{key}: nominal supplier gauges must be saved hidden")
    return ()


def extension_spring_dimensions(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    free_length_mm: float,
    reference_bounds: Callable[[str], tuple[float, float, float, float]],
    max_length_mm: float,
    coil_od_mm: float,
    wire_dia_mm: float,
    precision: Mapping[str, int],
    od_tolerance_mm: float | None = None,
    od_tolerance_precision: int | None = None,
) -> tuple[Callable[[], None], ...]:
    """Import source sizes and reacquire every native dimension after final rebuild."""
    rows_by_view = {
        "free_front": (
            (
                FREE_LENGTH,
                free_length_mm,
                "length",
                "STOCK FREE / INSIDE HOOKS OR LOOPS",
            ),
        ),
        "free_right": (
            (COIL_OD, coil_od_mm, "diameter", "NOMINAL STOCK COIL OD"),
            (WIRE_DIA, wire_dia_mm, "diameter", "NOMINAL STOCK WIRE SECTION"),
        ),
        "max_front": (
            (
                MAX_LENGTH,
                max_length_mm,
                "length",
                "STOCK MAXIMUM / INSIDE HOOKS OR LOOPS",
            ),
        ),
    }
    expected = {key: {} for key in views}
    configurations = {
        key: str(view.ReferencedConfiguration) for key, view in views.items()
    }
    required = {
        "free_front": SUPPLIER_FREE_CONFIGURATION,
        "free_right": SUPPLIER_FREE_CONFIGURATION,
        "max_front": SUPPLIER_MAX_CONFIGURATION,
    }
    for key, configuration in required.items():
        if configurations.get(key) != configuration:
            raise RuntimeError(f"{key}: nominal supplier gauge has wrong configuration")
    settings = {}
    for key, rows in rows_by_view.items():
        view = views[key]
        xmin, ymin, xmax, ymax = reference_bounds(key)
        positions = (
            {
                COIL_OD: (xmax + 0.006, ymax + 0.005),
                WIRE_DIA: (xmax + 0.006, ymin - 0.009),
            }
            if key == "free_right"
            else {rows[0][0]: ((xmin + xmax) / 2, ymax + 0.010)}
        )
        annotations = curate_view_dimensions(
            adapter,
            view,
            keep=positions,
            view_label=key,
            dimensions_by_feature=DIMENSIONS_BY_FEATURE,
        )
        by_name = {
            dimension_name(adapter, annotation): annotation
            for annotation in annotations
        }
        if len(annotations) != len(positions) or set(by_name) != set(positions):
            raise RuntimeError(
                f"{key}: supplier reference inventory differs from source"
            )
        for name, value, presentation, callout in rows:
            owner = next(
                feature
                for feature, names in DIMENSIONS_BY_FEATURE.items()
                if name in names
            )
            expected[key][name] = owner
            arguments = dict(
                label=name,
                units="in",
                precision=precision[name],
                expected_mm=value,
                presentation=presentation,
                callout=callout,
                configuration=configurations[key],
            )
            supplier_reference_dimension(
                adapter,
                _early_bound(
                    by_name[name].GetSpecificAnnotation(), "IDisplayDimension"
                ),
                **arguments,
            )
            settings[name] = (arguments, configurations[key])

    def settled() -> None:
        displays = reacquire_supplier_dimensions(
            adapter,
            views,
            expected=expected,
            configurations=configurations,
        )
        for name, (arguments, configuration) in settings.items():
            display = displays[name]
            # The shared assertion proves native dimension type before SI interpretation.
            assert_supplier_reference_dimension(adapter, display, **arguments)
            assert_supplier_configuration_value(
                display,
                configuration,
                arguments["expected_mm"],
                label=name,
            )
            native = _early_bound(display.GetDimension2(0), "IDimension")
            tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
            if name == COIL_OD and od_tolerance_mm is not None:
                if (
                    int(tolerance.Type) != 4
                    or abs(float(tolerance.GetMinValue()) + od_tolerance_mm / 1000)
                    > 1e-12
                    or abs(float(tolerance.GetMaxValue()) - od_tolerance_mm / 1000)
                    > 1e-12
                    or int(display.GetPrimaryTolPrecision2()) != od_tolerance_precision
                ):
                    raise RuntimeError(
                        "source supplier OD band changed after final rebuild"
                    )
            elif int(tolerance.Type) != 0:
                raise RuntimeError(f"{name}: unprovided supplier tolerance appeared")

    return (settled,)
