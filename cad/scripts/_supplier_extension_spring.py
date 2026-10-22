"""Native source-size references for the two reconstructed extension springs.

The hidden length chord is the supplier's inside-hook/inside-loop measurement
in its +X frame, not an installed span or a bounding-box length. Circular
references are the author's exact nominal coil envelope and wire section;
they are not measurements inferred from the supplier display model's pitch.

Drawing import and settled readback live in ``_supplier_spring_drawing``;
these source gauges remain in the model-only part dependency closure.
"""

from __future__ import annotations

from typing import Any

from _check import check
from _com import _early_bound
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
