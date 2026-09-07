"""Author BASIC designations in source parts; imported drawings only verify them.

An imported display dimension refers to the source model's dimension. Changing
its tolerance in a drawing cannot establish a saved source-part contract.
Keep this helper separately imported by its actual part/drawing consumers.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

from _common import _early_bound
from _drawing_marks import _named_dimension
import _telemetry


_BASIC = 1  # swTolType_e.swTolBASIC


@_telemetry.traced("dim.author_basic")
def author_basic_dimensions(
    adapter: Any, specification: Mapping[str, Iterable[str]]
) -> None:
    """Resolve the full source manifest before setting any tolerance types."""
    if int(adapter.currentModel.GetType()) != 1:
        raise ValueError("BASIC source dimensions must be authored in a part")
    targets = []
    for feature, names in sorted(specification.items()):
        names = tuple(names)
        if not feature or not names or len(set(names)) != len(names):
            raise ValueError("BASIC dimension manifest requires unique nonempty names")
        for name in sorted(names):
            if not name:
                raise ValueError("BASIC dimension names must be nonempty")
            _, dimension = _named_dimension(adapter, feature, name)
            value = float(dimension.SystemValue)
            if not math.isfinite(value):
                raise RuntimeError(f"{name}@{feature}: nonfinite source value")
            targets.append((f"{name}@{feature}", dimension, value))
    if not targets:
        raise ValueError("BASIC source manifest must not be empty")
    for label, dimension, _ in targets:
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = _BASIC
        if int(tolerance.Type) != _BASIC:
            raise RuntimeError(f"{label}: source BASIC designation was rejected")
    for label, dimension, value in targets:
        if (
            int(dimension.GetToleranceType()) != _BASIC
            or float(dimension.SystemValue) != value
        ):
            raise RuntimeError(f"{label}: BASIC authoring changed its value or type")
    _telemetry.info("source BASIC dimensions authored", dimension_count=len(targets))


def require_basic_dimension(display: Any, *, label: str) -> None:
    """Fail on a stale/unboxed imported source dimension; do not alter its part."""
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    if int(dimension.GetToleranceType()) != _BASIC:
        raise RuntimeError(
            f"{label}: imported source dimension is not BASIC; rebuild its source part"
        )
