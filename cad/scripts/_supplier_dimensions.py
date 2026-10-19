"""Supplier-unit presentation of measured native reference dimensions.

The supplier's displayed precision is not its exact geometry: a 7/16 inch
length may print .438, but its native SystemValue remains 11.1125 mm.
This helper never assigns a dimension value or replaces its numeric text.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from _com import _early_bound
import _telemetry

# swDimensionType_e; reject angle/radius/ordinate values before interpreting SI.
_LINEAR_TYPES = (2, 11, 12)
_DIAMETER_TYPES = (6, 15)


def _measured_supplier_value(
    display: Any,
    *,
    label: str,
    presentation: Literal["length", "diameter", "angle"],
    expected_mm: float | None,
    expected_degrees: float | None,
) -> float:
    kind = int(display.Type2)
    if presentation == "angle":
        allowed = (3,)  # swAngularDimension
        expected = expected_degrees
        factor = 180.0 / math.pi
        unit = "deg"
        if expected_mm is not None:
            raise ValueError(f"{label}: an angle cannot specify expected_mm")
    else:
        allowed = _LINEAR_TYPES + (
            _DIAMETER_TYPES if presentation == "diameter" else ()
        )
        expected = expected_mm
        factor = 1000.0
        unit = "mm"
        if expected_degrees is not None:
            raise ValueError(f"{label}: a length cannot specify expected_degrees")
    if expected is None or not math.isfinite(expected) or expected <= 0.0:
        raise ValueError(
            f"{label}: expected native {unit} value must be finite and positive"
        )
    if kind not in allowed:
        raise RuntimeError(
            f"{label}: native dimension type {kind} is not {presentation}"
        )
    raw = display.GetDimension2(0)
    if raw is None:
        raise RuntimeError(f"{label}: supplier reference has no native dimension")
    measured = abs(float(_early_bound(raw, "IDimension").SystemValue)) * factor
    if not math.isfinite(measured) or not math.isclose(
        measured, expected, rel_tol=0.0, abs_tol=1e-5
    ):
        raise RuntimeError(
            f"{label}: native value {measured:g} {unit} != exact expected {expected:g} {unit}"
        )
    return measured


@_telemetry.traced("drawing.supplier_reference_dimension", label_param="label")
def supplier_reference_dimension(
    adapter: Any,
    dimension: Any,
    *,
    label: str,
    units: Literal["in", "mm", "deg"],
    precision: int,
    expected_mm: float | None = None,
    expected_degrees: float | None = None,
    presentation: Literal["length", "diameter", "angle"] = "length",
    fraction_denominator: int | None = None,
    callout: str | None = None,
) -> Any:
    """Format a native measured value, parenthesized and explicitly unit-labelled.

    Accepts an imported display dimension or a drawing-owned geometric one.
    Callers identify/verify its physical attachments before calling. Existing
    native supplier tolerance bands are retained, not converted into project
    fabrication controls. Finished/custom dimensions must not pass through here.

    ``fraction_denominator`` requests exact native inch fractions; no rounding
    to a nearby fraction is permitted. ``callout`` is below-value identification
    (for example a thread designation), never a replacement numeric dimension.
    """
    if units not in ("in", "mm", "deg") or presentation not in (
        "length",
        "diameter",
        "angle",
    ):
        raise ValueError(f"{label}: unsupported supplier units/presentation")
    if (units == "deg") != (presentation == "angle"):
        raise ValueError(f"{label}: angular units and presentation must agree")
    if not isinstance(precision, int) or not 0 <= precision <= 8:
        raise ValueError(f"{label}: supplier decimal precision must be 0..8")
    if fraction_denominator is not None and (
        units != "in"
        or fraction_denominator < 1
        or fraction_denominator & (fraction_denominator - 1)
    ):
        raise ValueError(f"{label}: inch fraction denominator must be a power of two")
    display = _early_bound(dimension, "IDisplayDimension")
    _measured_supplier_value(
        display,
        label=label,
        presentation=presentation,
        expected_mm=expected_mm,
        expected_degrees=expected_degrees,
    )
    if display.GetOverride() or not display.ShowDimensionValue:
        raise RuntimeError(
            f"{label}: supplier reference hides or overrides its native value"
        )
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    if annotation.IsDangling() or not any(annotation.GetAttachedEntities3() or ()):
        raise RuntimeError(
            f"{label}: supplier reference has no sound native attachment"
        )
    unit = {"mm": 0, "in": 3, "deg": 0}[units]  # swLengthUnit_e / swAngleUnit_e
    fraction = 2 if fraction_denominator is not None else 1  # swFractionDisplay_e
    denominator = fraction_denominator or 0
    if fraction_denominator is not None:
        inches = float(expected_mm) / 25.4
        if not math.isclose(
            inches * denominator, round(inches * denominator), rel_tol=0.0, abs_tol=1e-8
        ):
            raise ValueError(
                f"{label}: exact geometry cannot display that inch fraction"
            )
    # swUnitsDecimalRounding_HalfAway=0 matches supplier decimal rounding.
    if display.SetUnits2(False, unit, fraction, denominator, False, 0) != 0:
        raise RuntimeError(f"{label}: supplier units were rejected")
    display.SetPrecision3(precision, -1, -1, -1)
    display.ShowParenthesis = True
    prefix = (
        "<MOD-DIAM>"
        if presentation == "diameter" and int(display.Type2) in _LINEAR_TYPES
        else ""
    )
    suffix = "" if units == "deg" else f" {units}"
    display.SetText(1, prefix)  # swDimensionTextPrefix, never swDimensionTextAll
    display.SetText(2, suffix)  # swDimensionTextSuffix
    if callout is not None:
        display.SetText(4, callout)  # swDimensionTextCalloutBelow
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError(f"{label}: supplier presentation rebuild failed")
    if (
        display.GetUseDocUnits()
        or int(display.GetUnits()) != unit
        or int(display.GetPrimaryPrecision2()) != precision
        or int(display.GetFractionBase()) != fraction
        or not display.ShowParenthesis
        or display.GetOverride()
        or not display.ShowDimensionValue
        or str(display.GetText(1) or "") != prefix
        or str(display.GetText(2) or "") != suffix
        or (callout is not None and str(display.GetText(4) or "") != callout)
    ):
        raise RuntimeError(
            f"{label}: native supplier presentation did not survive rebuild"
        )
    if fraction_denominator is not None and (
        int(display.GetFractionValue()) != fraction_denominator
        or display.GetRoundToFraction()
    ):
        raise RuntimeError(f"{label}: exact supplier fraction did not persist")
    _measured_supplier_value(
        display,
        label=label,
        presentation=presentation,
        expected_mm=expected_mm,
        expected_degrees=expected_degrees,
    )
    return display
