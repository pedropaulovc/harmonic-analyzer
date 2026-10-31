"""Supplier-unit presentation of measured native reference dimensions.

A supplier's displayed precision is not its exact geometry: 7/16 inch may
print .438, while its native value remains 11.1125 mm. Never assign a value
or replace its numeric text. Attachment identity remains the caller's job.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from _com import _early_bound
import _telemetry

# swDimensionType_e: check type before interpreting the native SI value.
_LINEAR_TYPES = (2, 11, 12)
_DIAMETER_TYPES = (6, 15)


def _measured_supplier_value(
    display: Any,
    *,
    label: str,
    presentation: Literal["length", "diameter", "angle"],
    expected_mm: float | None,
    expected_degrees: float | None,
    configuration: str | None = None,
) -> float:
    if presentation not in ("length", "diameter", "angle"):
        raise ValueError(f"{label}: unsupported supplier presentation")
    if configuration is not None and (
        not isinstance(configuration, str) or not configuration.strip()
    ):
        raise ValueError(f"{label}: supplier configuration must be a nonempty name")
    kind = int(display.Type2)
    if presentation == "angle":
        allowed = (3,)  # swAngularDimension
        expected, factor, unit = expected_degrees, 180.0 / math.pi, "deg"
        if expected_mm is not None:
            raise ValueError(f"{label}: an angle cannot specify expected_mm")
    else:
        allowed = _LINEAR_TYPES + (_DIAMETER_TYPES if presentation == "diameter" else ())
        expected, factor, unit = expected_mm, 1000.0, "mm"
        if expected_degrees is not None:
            raise ValueError(f"{label}: a length cannot specify expected_degrees")
    if (
        isinstance(expected, bool)
        or not isinstance(expected, (int, float))
        or not math.isfinite(expected)
        or expected <= 0.0
    ):
        raise ValueError(f"{label}: expected native {unit} value must be finite and positive")
    if kind not in allowed:
        raise RuntimeError(f"{label}: native dimension type {kind} is not {presentation}")
    raw = display.GetDimension2(0)
    if raw is None:
        raise RuntimeError(f"{label}: supplier reference has no native dimension")
    native = _early_bound(raw, "IDimension")
    if configuration is None:
        value = float(native.SystemValue)
    else:
        values = native.GetSystemValue3(3, configuration)  # swSpecifyConfiguration
        if not isinstance(values, (tuple, list)) or len(values) != 1:
            raise RuntimeError(f"{label}: supplier configuration value is missing")
        value = float(values[0])
    measured = abs(value) * factor
    if not math.isfinite(measured) or not math.isclose(
        measured, expected, rel_tol=0.0, abs_tol=1e-5
    ):
        raise RuntimeError(
            f"{label}: native value {measured:g} {unit} != exact expected {expected:g} {unit}"
        )
    return measured


def _presentation(
    *,
    label: str,
    units: str,
    precision: int,
    presentation: str,
    fraction_denominator: int | None,
    callout: str | None,
    expected_mm: float | None,
) -> tuple[int, int, str, str]:
    if units not in ("in", "mm", "deg") or presentation not in (
        "length", "diameter", "angle"
    ):
        raise ValueError(f"{label}: unsupported supplier units/presentation")
    if (units == "deg") != (presentation == "angle"):
        raise ValueError(f"{label}: angular units and presentation must agree")
    if type(precision) is not int or not 0 <= precision <= 8:
        raise ValueError(f"{label}: supplier decimal precision must be 0..8")
    if fraction_denominator is not None:
        if (
            units != "in"
            or type(fraction_denominator) is not int
            or fraction_denominator < 1
            or fraction_denominator & (fraction_denominator - 1)
        ):
            raise ValueError(f"{label}: inch fraction denominator must be a power of two")
        if expected_mm is None or not math.isfinite(expected_mm):
            raise ValueError(f"{label}: an inch fraction requires an exact native length")
        scaled = expected_mm / 25.4 * fraction_denominator
        if not math.isclose(scaled, round(scaled), rel_tol=0.0, abs_tol=1e-8):
            raise ValueError(f"{label}: exact geometry cannot display that inch fraction")
    if callout is not None and (not isinstance(callout, str) or not callout.strip()):
        raise ValueError(f"{label}: supplier below-callout must be nonempty text")
    unit = {"mm": 0, "in": 3, "deg": 0}[units]
    fraction = 2 if fraction_denominator is not None else 1
    prefix = "(<MOD-DIAM>" if presentation == "diameter" else "("
    # SolidWorks already prints an inch mark after a fraction (1/4"), so a
    # fraction takes no " in" suffix; decimals still name their unit.
    suffix = ")" if units == "deg" or fraction_denominator is not None else f" {units})"
    return unit, fraction, prefix, suffix


def _sound_attachment(display: Any, *, label: str) -> Any:
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    types = tuple(int(kind) for kind in (annotation.GetAttachedEntityTypes() or ()))
    if (
        annotation.IsDangling()
        or int(annotation.Visible) != 1  # swAnnotationVisible
        or int(annotation.OwnerType) != 0  # swAnnotationOwner_DrawingView
        or annotation.Owner is None
        or not attached
        or any(entity is None for entity in attached)
        or len(attached) != int(annotation.GetAttachedEntityCount3())
        or len(types) != len(attached)
        or any(kind <= 0 for kind in types)
    ):
        raise RuntimeError(f"{label}: supplier reference has no sound native attachment")
    return annotation


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
    configuration: str | None = None,
) -> Any:
    """Dress a native measured value; retain its source tolerance, if any.

    Imported nominal model references are not claims of physical-edge or
    helical-thread attachment. Callers verify the appropriate source identity.
    A below-callout identifies the native size; it never replaces its value.
    """
    unit, fraction, prefix, suffix = _presentation(
        label=label, units=units, precision=precision, presentation=presentation,
        fraction_denominator=fraction_denominator, callout=callout, expected_mm=expected_mm,
    )
    display = _early_bound(dimension, "IDisplayDimension")
    _measured_supplier_value(
        display, label=label, presentation=presentation,
        expected_mm=expected_mm, expected_degrees=expected_degrees,
        configuration=configuration,
    )
    if display.GetOverride() or not display.ShowDimensionValue:
        raise RuntimeError(f"{label}: supplier reference hides or overrides its native value")
    _sound_attachment(display, label=label)
    # Exact fractions only; HalfAway=0 matches supplier decimal rounding.
    if display.SetUnits2(False, unit, fraction, fraction_denominator or 0, False, 0) != 0:
        raise RuntimeError(f"{label}: supplier units were rejected")
    # Preserve independently authored tolerance and dual precision.
    status = display.SetPrecision3(precision, -1, -1, -1)
    if status != 0:
        raise RuntimeError(f"{label}: supplier precision was rejected (status {status!r})")
    # ShowParenthesis can read True but render bare; use the proven native
    # prefix/suffix form, keeping the numerical dimension visible.
    display.ShowParenthesis = False
    display.SetText(1, prefix)  # swDimensionTextPrefix; never swDimensionTextAll
    display.SetText(2, suffix)
    display.SetText(4, callout or "")  # swDimensionTextCalloutBelow
    assert_supplier_reference_dimension(
        adapter, display, label=label, units=units, precision=precision,
        expected_mm=expected_mm, expected_degrees=expected_degrees,
        presentation=presentation, fraction_denominator=fraction_denominator,
        callout=callout,
        configuration=configuration,
    )
    return display


@_telemetry.traced("drawing.assert_supplier_reference_dimension", label_param="label")
def assert_supplier_reference_dimension(
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
    configuration: str | None = None,
) -> None:
    """Read persisted native state after the final rebuild; never repair it."""
    unit, fraction, prefix, suffix = _presentation(
        label=label, units=units, precision=precision, presentation=presentation,
        fraction_denominator=fraction_denominator, callout=callout, expected_mm=expected_mm,
    )
    display = _early_bound(dimension, "IDisplayDimension")
    _measured_supplier_value(
        display, label=label, presentation=presentation,
        expected_mm=expected_mm, expected_degrees=expected_degrees,
        configuration=configuration,
    )
    _sound_attachment(display, label=label)
    # Keep the same lazy read order: the first mismatch must not be obscured
    # by an unrelated later native reader. Report the actual rejected field.
    for field, read, expected in (
        ("use_document_units", lambda: bool(display.GetUseDocUnits()), False),
        ("units", lambda: int(display.GetUnits()), unit),
        ("primary_precision", lambda: int(display.GetPrimaryPrecision2()), precision),
        ("fraction_base", lambda: int(display.GetFractionBase()), fraction),
        ("show_parentheses", lambda: bool(display.ShowParenthesis), False),
        ("override", lambda: bool(display.GetOverride()), False),
        ("show_native_value", lambda: bool(display.ShowDimensionValue), True),
        ("prefix", lambda: str(display.GetText(1) or ""), prefix),
        ("suffix", lambda: str(display.GetText(2) or ""), suffix),
        ("below_callout", lambda: str(display.GetText(4) or ""), callout or ""),
    ):
        actual = read()
        if actual != expected:
            raise RuntimeError(
                f"{label}: native supplier presentation differs from its source "
                f"({field}: actual={actual!r}, expected={expected!r})"
            )
    if fraction_denominator is not None and (
        int(display.GetFractionValue()) != fraction_denominator or display.GetRoundToFraction()
    ):
        raise RuntimeError(f"{label}: exact supplier fraction did not persist")
