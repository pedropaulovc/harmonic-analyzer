"""Hidden, dimensioned supplier envelopes without changing purchased solids.

A helical groove or driver slot can remove a nominal diameter or dome apex.
These construction references retain those supplier sizes from the exact same
per-SKU constants used by the solid recipe, not from rounded printed values.
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
from _supplier_screw_reference_names import FEATURE_BY_PLANE
from _supplier_screw_reference_names import REFERENCE_SKETCHES as REFERENCE_SKETCHES
import _telemetry


def _construction(adapter: Any, entity: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity}: supplier reference is not construction geometry")


async def _anchor(
    adapter: Any,
    dimensions: SketchDims,
    entity: str,
    start: tuple[float, float],
    name: str,
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
        line = check(
            f"create {name} supplier reference", await adapter.add_line(*start, *end)
        )
    finally:
        set_sketch_direct_db(adapter, False)
    _construction(adapter, line)
    check(
        f"orient {name} supplier reference",
        await adapter.add_sketch_constraint(line, None, orientation),
    )
    await dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        f"{orientation}_distance",
        abs(value),
        name,
    )
    dimensions.record(name)
    await _anchor(adapter, dimensions, line, start, name)


async def _angle(
    adapter: Any,
    dimensions: SketchDims,
    name: str,
    degrees: float,
    start: tuple[float, float],
) -> None:
    # Unit-length construction rays encode only the source's included angle.
    # Their length and placement are unmarked bookkeeping, not supplier sizes.
    radians = math.radians(degrees)
    set_sketch_direct_db(adapter, True)
    try:
        baseline = check(
            f"create {name} baseline",
            await adapter.add_line(*start, start[0] + 1.0, start[1]),
        )
        ray = check(
            f"create {name} angle ray",
            await adapter.add_line(
                *start, start[0] + math.cos(radians), start[1] + math.sin(radians)
            ),
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
        adapter,
        f"{baseline}.start",
        f"{baseline}.end",
        "horizontal_distance",
        1.0,
        name,
    )
    dimensions.record(f"{name}BaselineLength")
    await _anchor(adapter, dimensions, baseline, start, name)
    check(
        f"join {name} rays",
        await adapter.add_sketch_constraint(
            f"{baseline}.start", f"{ray}.start", "coincident"
        ),
    )
    await dimension_between(
        adapter, f"{ray}.start", f"{ray}.end", "distance", 1.0, name
    )
    dimensions.record(f"{name}RayLength")
    check(
        f"dimension {name} supplier angle",
        await adapter.add_sketch_dimension(baseline, ray, "angular", degrees),
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
    """Author fully defined, hidden supplier-size reference sketches.

    Rows are ``(name, exact_value, horizontal|vertical|angle)``. Signed linear
    values select the direction from ``starts[name]``; the native dimension is
    the positive length. Angular values are degrees. Front/Top sketch planes
    are chosen by ``planes``; Top sketch Y is model -Z. Only the named sizes,
    never anchor dimensions or angle-ray lengths, are marked for drawing.
    """
    starts = starts or {}
    planes = planes or {}
    names = [name for name, _, _ in dimensions]
    if len(names) != len(set(names)):
        raise ValueError("supplier reference dimension names must be unique")
    if (set(starts) | set(planes)) - set(names):
        raise ValueError("supplier reference placement names do not match dimensions")
    for name, value, orientation in dimensions:
        if not name or not math.isfinite(value) or value == 0.0:
            raise ValueError(
                f"{name}: supplier reference value must be finite and nonzero"
            )
        if orientation not in ("horizontal", "vertical", "angle"):
            raise ValueError(f"{name}: unsupported supplier reference orientation")
        if orientation == "angle" and not 0.0 < value < 180.0:
            raise ValueError(
                f"{name}: supplier included angle must be between 0 and 180"
            )
        if planes.get(name, "Front") not in FEATURE_BY_PLANE:
            raise ValueError(f"{name}: unsupported supplier reference plane")
        if not all(math.isfinite(value) for value in starts.get(name, (0.0, 0.0))):
            raise ValueError(f"{name}: supplier reference start must be finite")
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
        mark_dimensions_for_drawing(adapter, feature, {name for name, _, _ in rows})
        blank_reference_sketches(adapter, (feature,))


async def save_supplier_reference_part(
    adapter: Any,
    part_name: str,
    suppressed_features: tuple[str, ...],
    *,
    dimensions: Sequence[tuple[str, float, str]],
    starts: Mapping[str, tuple[float, float]] | None = None,
    planes: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Add references in the final stock frame, then use the normal part saver."""
    from _simplified_part import save_simplified_part

    await add_supplier_reference_sketch(
        adapter, dimensions, starts=starts, planes=planes
    )
    return await save_simplified_part(adapter, part_name, suppressed_features)
