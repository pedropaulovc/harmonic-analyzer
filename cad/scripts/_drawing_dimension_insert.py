"""Sketch dimension insertion helpers, separate to limit cache blast radius."""

from __future__ import annotations

import math
from typing import Any

import _telemetry
from _com import _early_bound, _read_member


@_telemetry.traced("dim.diametric", label_param="label")
async def add_diametric_linear_dimension(
    adapter: Any,
    centerline: str,
    line: str,
    text_xy: tuple[float, float],
    label: str,
) -> Any:
    """Create a doubled centerline-to-outline diameter dimension."""
    from solidworks_mcp.adapters import sw_type_info as _sw_type_info
    from solidworks_mcp.adapters.solidworks.sketch import (
        _resolve_entity_ref,
        _select_sketch_entities,
    )

    model = adapter.currentModel
    model.ClearSelection2(True)
    if line.endswith((".start", ".end", ".center")):
        _select_sketch_entities(adapter, [centerline], 0)
        point = _resolve_entity_ref(adapter, line)
        if not bool(point.Select4(True, None)):
            raise RuntimeError(f"{label}: failed to select sketch point {line!r}")
    else:
        _select_sketch_entities(adapter, [centerline, line], 0)
    extension = _sw_type_info.early_bound_or_flag(
        model.Extension, "IModelDocExtension", "AddSpecificDimension"
    )
    display, status = extension.AddSpecificDimension(
        text_xy[0] / 1000.0,
        text_xy[1] / 1000.0,
        0.0,
        15,  # swDimensionType_e.swDiametricLinearDimension
        0,
    )
    model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(
            f"{label}: AddSpecificDimension(diametric) failed ({status})"
        )
    display = _early_bound(display, "IDisplayDimension")
    if not bool(_read_member(display, "Diametric")):
        raise RuntimeError(f"{label}: new dimension is not diametric")
    _telemetry.success(f"diametric dim {label}")
    return display


@_telemetry.traced("dim.angular_reference", label_param="label")
async def add_angular_reference_dimension(
    adapter: Any,
    first_line: str,
    second_line: str,
    text_xy: tuple[float, float],
    label: str,
    *,
    expected_degrees: float,
) -> Any:
    """Create and verify a driven angular dimension between two sketch lines."""
    from solidworks_mcp.adapters import sw_type_info as _sw_type_info
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    if expected_degrees <= 0.0 or expected_degrees >= 180.0:
        raise ValueError("expected reference angle must be between 0 and 180 degrees")
    model = adapter.currentModel
    model.ClearSelection2(True)
    _select_sketch_entities(adapter, [first_line, second_line], 0)
    extension = _sw_type_info.early_bound_or_flag(
        model.Extension, "IModelDocExtension", "AddSpecificDimension"
    )
    display, status = extension.AddSpecificDimension(
        text_xy[0] / 1000.0,
        text_xy[1] / 1000.0,
        0.0,
        3,  # swDimensionType_e.swAngularDimension
        0,
    )
    model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"{label}: AddSpecificDimension(angular) failed ({status})")
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    dimension.DrivenState = 1  # swDimensionDrivenState_e.swDimensionDriven
    if int(_read_member(dimension, "DrivenState")) != 1:
        raise RuntimeError(f"{label}: angular dimension did not become driven")

    expected_rad = math.radians(expected_degrees)
    actual_rad = abs(float(_read_member(dimension, "SystemValue")))
    if abs(actual_rad - expected_rad) > 1e-8:
        supplement_rad = abs(math.pi - actual_rad)
        if (
            abs(supplement_rad - expected_rad) > 1e-8
            or not display.SupplementaryAngle()
        ):
            raise RuntimeError(
                f"{label}: angular dimension measured {math.degrees(actual_rad):.6f} "
                f"deg, expected {expected_degrees:.6f} deg"
            )
        actual_rad = abs(float(_read_member(dimension, "SystemValue")))
    if abs(actual_rad - expected_rad) > 1e-8:
        raise RuntimeError(
            f"{label}: angular dimension readback {math.degrees(actual_rad):.6f} "
            f"deg != {expected_degrees:.6f} deg"
        )
    _telemetry.success(f"angular reference dim {label}: {expected_degrees:.3f} deg")
    return display
