"""Measure mixin for PyWin32 SolidWorks operations (Phase 6).

Implements dimensional measurement (``IModelDocExtension::CreateMeasure`` +
``IMeasure::Calculate``) over entities selected by name or by a point lying
on them.
"""

from __future__ import annotations

import math
from typing import Any, cast

from ..base import (
    AdapterResult,
    AdapterResultStatus,
    MeasureParameters,
)
from .features import _flag_feature_methods, _read_member, _select_by_point

# IMeasure::ArcOption values (no public enum; documented in the API example)
_ARC_OPTIONS = {"center": 0, "minimum": 1, "maximum": 2}

# IMeasure numeric properties: name → ("linear" | "area" | "angle").
# Linear values are metres, areas m², angles radians; -1 marks not-applicable.
_MEASURE_PROPERTIES: dict[str, str] = {
    "Distance": "linear",
    "CenterDistance": "linear",
    "NormalDistance": "linear",
    "Projection": "linear",
    "Normal": "linear",
    "DeltaX": "linear",
    "DeltaY": "linear",
    "DeltaZ": "linear",
    "X": "linear",
    "Y": "linear",
    "Z": "linear",
    "Length": "linear",
    "TotalLength": "linear",
    "ArcLength": "linear",
    "ChordLength": "linear",
    "Perimeter": "linear",
    "Diameter": "linear",
    "Radius": "linear",
    "Area": "area",
    "TotalArea": "area",
    "Angle": "angle",
}

_MEASURE_FLAGS = ("IsParallel", "IsIntersect", "IsPerpendicular")


class SolidWorksMeasureMixin:
    """Expose the SolidWorks measure tool via a mixin-local helper."""

    async def measure(self, params: MeasureParameters) -> AdapterResult[dict[str, Any]]:
        return _measure_impl(self, params)


def _snake_case(name: str) -> str:
    """Convert a COM property name like ``CenterDistance`` to snake_case.

    Args:
        name: CamelCase property name.

    Returns:
        str: snake_case key for the result payload.
    """
    out = [name[0].lower()]
    for char in name[1:]:
        if char.isupper():
            out.append("_")
        out.append(char.lower())
    return "".join(out)


def _select_measure_entities(adapter: Any, params: MeasureParameters) -> None:
    """Select every requested entity, replacing the current selection set.

    Named entities go through ``SelectByID2`` with their name; unnamed ones
    (faces/edges/vertices) are located by a point on them — subject to the
    view-dependent picking caveat documented on :func:`_select_by_point`, which
    finds an edge or face the pick misses by geometry.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        params: Entities to select.

    Raises:
        Exception: When any entity fails to select.
    """
    from ..com_variant import null_callout

    adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True))
    for position, entity in enumerate(params.entities):
        append = position > 0
        if entity.name:
            selected = bool(
                adapter._attempt(
                    lambda e=entity, a=append: (
                        adapter.currentModel.Extension.SelectByID2(
                            e.name,
                            e.entity_type,
                            0.0,
                            0.0,
                            0.0,
                            a,
                            0,
                            null_callout(),
                            0,
                        )
                    ),
                    default=False,
                )
            )
        else:
            selected = _select_by_point(
                adapter, entity.entity_type, entity.point, 0, append
            )
        if not selected:
            location = entity.name or entity.point
            raise Exception(
                f"Failed to select {entity.entity_type} at {location} "
                f"(entity {position + 1} of {len(params.entities)})"
            )


def _read_measurements(adapter: Any, measure: Any) -> dict[str, Any]:
    """Read every applicable value off a calculated ``IMeasure``.

    Properties returning the -1 not-applicable sentinel are omitted. Linear
    values are converted to millimetres, areas to mm² and angles to degrees.

    Args:
        adapter: Connected adapter (for ``_attempt``).
        measure: The ``IMeasure`` dispatch after a successful ``Calculate``.

    Returns:
        dict[str, Any]: snake_case measurement values plus the
        parallel/intersect/perpendicular flags.
    """
    values: dict[str, Any] = {}
    for prop, kind in _MEASURE_PROPERTIES.items():
        raw = adapter._attempt(lambda p=prop: _read_member(measure, p), default=None)
        if raw is None:
            continue
        number = float(raw)
        if number == -1.0:
            continue
        if kind == "linear":
            number *= 1000.0
        elif kind == "area":
            number *= 1_000_000.0
        elif kind == "angle":
            number = math.degrees(number)
        values[_snake_case(prop)] = number
    for flag in _MEASURE_FLAGS:
        raw = adapter._attempt(lambda f=flag: _read_member(measure, f), default=None)
        if raw is not None:
            values[_snake_case(flag)] = bool(raw)
    return values


def _measure_impl(
    adapter: Any, params: MeasureParameters
) -> AdapterResult[dict[str, Any]]:
    """Measure the selected entities via the measure tool.

    Selects the requested entities, creates the measure tool
    (``IModelDocExtension::CreateMeasure``), applies the arc option and
    calculates over the current selection (``Calculate(None)`` per the API:
    a null entity array means "measure the selection").

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Entities and arc-distance option.

    Returns:
        AdapterResult[dict[str, Any]]: Measurements in millimetres / mm² /
        degrees, or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if not params.entities:
        return AdapterResult(
            status=AdapterResultStatus.ERROR, error="No entities to measure"
        )
    arc_option = _ARC_OPTIONS.get(params.arc_option)
    if arc_option is None:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown arc_option: {params.arc_option!r} "
            f"(expected one of {sorted(_ARC_OPTIONS)})",
        )

    def _measure_operation() -> dict[str, Any]:
        try:
            _select_measure_entities(adapter, params)

            extension = adapter.currentModel.Extension
            extension = _flag_feature_methods(extension, "IModelDocExtension")
            measure = extension.CreateMeasure()
            if measure is None:
                raise Exception("Failed to create the measure tool")
            measure = _flag_feature_methods(measure, "IMeasure")

            measure.ArcOption = arc_option
            # Calculate(NULL) measures the current selection. Bare None
            # marshals as VT_NULL which some SolidWorks params reject (the
            # SelectByID2 Callout class of failures) — fall back to a typed
            # null dispatch.
            try:
                calculated = bool(measure.Calculate(None))
            except Exception:
                from ..com_variant import null_variant

                calculated = bool(measure.Calculate(null_variant()))
            if not calculated:
                raise Exception(
                    "Measure failed: invalid combination of selected entities"
                )
            return _read_measurements(adapter, measure)
        finally:
            adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True))

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("measure", _measure_operation),
    )
