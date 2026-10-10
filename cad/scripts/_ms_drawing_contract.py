"""Read-only native dimension audit for the measuring-stick drawing package."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

import _telemetry
from _common import _early_bound
from _drawing_common import assert_imported_precision, dimension_name


@_telemetry.traced("drawing.ms_dimension_contract")
def assert_manufacturing_dimensions(
    adapter: Any, annotations: Iterable[Any], values: Mapping[str, float],
    precision: dict[str, int], *, bands: Mapping[str, tuple[float, float]] | None = None,
    angular: frozenset[str] = frozenset(),
) -> None:
    """Check the imported source value, band, non-reference state and places.

    No nominal, tolerance or display precision is authored by the drawing.
    The marked model name identifies each source; these are not sheet picks.
    """
    annotations = tuple(annotations)
    assert_imported_precision(adapter, annotations, precision)
    remaining = dict(values)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            raise RuntimeError(f"unexpected MS manufacturing dimension {name!r}")
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        expected = remaining.pop(name)
        measured = abs(float(dimension.SystemValue))
        measured = math.degrees(measured) if name in angular else measured * 1000.0
        if abs(measured - expected) > 1e-5:
            raise RuntimeError(f"{name}: source nominal {measured:g} != {expected:g}")
        if bool(display.ShowParenthesis) or bool(annotation.IsDangling()):
            raise RuntimeError(f"{name}: manufacturing dimension became reference or dangling")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        band = (bands or {}).get(name)
        if band is not None:
            actual = (float(tolerance.GetMinValue()) * 1000.0,
                      float(tolerance.GetMaxValue()) * 1000.0)
            if any(abs(a - b) > 1e-6 for a, b in zip(actual, band, strict=True)):
                raise RuntimeError(f"{name}: imported band {actual} != model band {band}")
        elif int(tolerance.Type) != 0:
            raise RuntimeError(f"{name}: unexpected explicit tolerance instead of title block")
    if remaining:
        raise RuntimeError(f"missing MS manufacturing dimensions: {sorted(remaining)}")
