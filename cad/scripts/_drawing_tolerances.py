"""Model-dimension tolerance values and precision, separate to limit cache blast radius."""

from __future__ import annotations

import math
from typing import Any

import _telemetry
from _com import _early_bound, _read_member
from _drawing_precision import _named_dimension


def _tolerance_places(*deviations: float) -> int:
    """Return the fewest decimals that preserve every deviation, in the
    dimension's display unit (millimetres, or degrees for an angle).

    SOLIDWORKS stores tolerance values in metres or radians but renders them
    in the document's display units.  The drawing template defaults tolerance
    values to two decimal places, which would turn a real 0.004 mm deviation
    into 0.00, and angular tolerances to one, which printed a 0.25 deg band as
    +/-0.3.  Derive the override from the source values rather than
    maintaining a second per-drawing precision table.
    """
    for digits in range(9):
        if all(
            math.isclose(value, round(value, digits), rel_tol=0.0, abs_tol=1e-12)
            for value in deviations
        ):
            return digits
    raise ValueError(
        f"dimension tolerance needs more than 8 decimal places: {deviations!r}"
    )


@_telemetry.traced("dim.tolerance_precision", label_param="label")
def _set_tolerance_precision(
    display: Any,
    deviations: tuple[float, ...],
    *,
    label: str,
    places: int | None = None,
) -> int:
    """Set and verify a model display dimension's primary tolerance precision.

    ``places`` widens the tolerance to the nominal's places where a band's
    fewest places would print short of it (a 3-place ream's 0/-0.010 read
    "0.00 / -0.01"); it may never drop a digit a deviation needs.
    """
    display = _early_bound(display, "IDisplayDimension")
    digits = _tolerance_places(*deviations)
    if places is not None:
        if places < digits:
            raise ValueError(
                f"{label}: {places} tolerance places would round {deviations!r}, "
                f"which needs {digits}"
            )
        digits = places
    do_not_change = -1  # swDimensionPrecisionSettings_e
    display.SetPrecision3(do_not_change, do_not_change, digits, do_not_change)
    applied = int(display.GetPrimaryTolPrecision2())
    if applied != digits:
        raise RuntimeError(
            f"{label}: tolerance precision did not persist: "
            f"requested {digits} decimals, dimension reports {applied}"
        )
    return digits


def set_dimension_basic_tolerance(
    adapter: Any,
    feature_name: str,
    dimension_name: str,
) -> None:
    """Make a frame-controlled locator BASIC on its source-model dimension.

    BASIC defines the nominal locator; it must not inherit a title-block
    size or angle tolerance. The owning spec supplies its surviving frame.
    """
    _display, dimension = _named_dimension(adapter, feature_name, dimension_name)
    if dimension.SetToleranceType(1) is not True:  # swTolType_e.swTolBASIC
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: SetToleranceType rejected BASIC"
        )
    if int(dimension.GetToleranceType()) != 1:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: BASIC tolerance type did not persist"
        )
    _telemetry.success(f"toleranced {dimension_name}@{feature_name}: BASIC")


def set_dimension_symmetric_tolerance(
    adapter: Any,
    feature_name: str,
    dimension_name: str,
    tolerance_mm: float,
) -> None:
    """Tolerance one named source-model dimension and verify the stored values."""
    if tolerance_mm <= 0.0:
        raise ValueError("symmetric dimension tolerance must be positive")
    display, dimension = _named_dimension(adapter, feature_name, dimension_name)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 4  # swTolType_e.swTolSYMMETRIC
    tolerance_m = tolerance_mm / 1000.0
    # SOLIDWORKS 2026 rejects SetValues2 for this extrusion-depth dimension in
    # both all-configuration and active-configuration forms.  SetValues is the
    # source-model path already exercised by _holes._tolerance_hole_diameter.
    if not tolerance.SetValues(-tolerance_m, tolerance_m):
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: SetValues rejected +/-{tolerance_mm} mm"
        )
    if int(tolerance.Type) != 4:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: symmetric tolerance type did not persist"
        )
    minimum = float(tolerance.GetMinValue())
    maximum = float(tolerance.GetMaxValue())
    if abs(minimum + tolerance_m) > 1e-9 or abs(maximum - tolerance_m) > 1e-9:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: tolerance readback "
            f"{minimum:g}/{maximum:g} m != +/-{tolerance_m:g} m"
        )
    precision = _set_tolerance_precision(
        display, (-tolerance_mm, tolerance_mm), label=f"{dimension_name}@{feature_name}"
    )
    _telemetry.success(
        f"toleranced {dimension_name}@{feature_name}: +/-{tolerance_mm:g} mm "
        f"({precision} decimals)"
    )


def set_dimension_bilateral_tolerance(
    adapter: Any,
    feature_name: str,
    dimension_name: str,
    lower_deviation_mm: float,
    upper_deviation_mm: float,
    *,
    places: int | None = None,
) -> None:
    """Apply signed lower/upper deviations to one named source dimension.

    ``places`` prints the tolerance at the nominal's places
    (``_set_tolerance_precision``); by default, the fewest that keep it.
    """
    if lower_deviation_mm > upper_deviation_mm:
        raise ValueError("lower dimension deviation must not exceed upper deviation")
    if lower_deviation_mm == upper_deviation_mm:
        raise ValueError("bilateral dimension tolerance must have a nonzero range")
    display, dimension = _named_dimension(adapter, feature_name, dimension_name)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 2  # swTolType_e.swTolBILAT
    lower_m = lower_deviation_mm / 1000.0
    upper_m = upper_deviation_mm / 1000.0
    if not tolerance.SetValues(lower_m, upper_m):
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: SetValues rejected "
            f"{lower_deviation_mm:+.2f}/{upper_deviation_mm:+.2f} mm"
        )
    if int(tolerance.Type) != 2:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: bilateral tolerance type did not persist"
        )
    minimum = float(tolerance.GetMinValue())
    maximum = float(tolerance.GetMaxValue())
    if abs(minimum - lower_m) > 1e-9 or abs(maximum - upper_m) > 1e-9:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: tolerance readback "
            f"{minimum:g}/{maximum:g} m != {lower_m:g}/{upper_m:g} m"
        )
    precision = _set_tolerance_precision(
        display,
        (lower_deviation_mm, upper_deviation_mm),
        label=f"{dimension_name}@{feature_name}",
        places=places,
    )
    _telemetry.success(
        f"toleranced {dimension_name}@{feature_name}: "
        f"{lower_deviation_mm:+g}/{upper_deviation_mm:+g} mm "
        f"({precision} decimals)"
    )


@_telemetry.traced("dim.angular_tolerance", label_param="dimension_name")
def set_dimension_symmetric_angular_tolerance(
    adapter: Any,
    feature_name: str,
    dimension_name: str,
    tolerance_degrees: float,
    *,
    require_driven: bool = False,
) -> None:
    """Tolerance one angular model dimension; SolidWorks stores radians."""
    if tolerance_degrees <= 0.0:
        raise ValueError("symmetric angular tolerance must be positive")
    display, dimension = _named_dimension(adapter, feature_name, dimension_name)
    if require_driven and int(_read_member(dimension, "DrivenState")) != 1:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: expected a driven reference dimension"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 4  # swTolType_e.swTolSYMMETRIC
    tolerance_rad = math.radians(tolerance_degrees)
    if not tolerance.SetValues(-tolerance_rad, tolerance_rad):
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: SetValues rejected "
            f"+/-{tolerance_degrees} deg"
        )
    minimum = float(tolerance.GetMinValue())
    maximum = float(tolerance.GetMaxValue())
    if abs(minimum + tolerance_rad) > 1e-12 or abs(maximum - tolerance_rad) > 1e-12:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: angular tolerance readback "
            f"{minimum:g}/{maximum:g} rad != +/-{tolerance_rad:g} rad"
        )
    precision = _set_tolerance_precision(
        display,
        (-tolerance_degrees, tolerance_degrees),
        label=f"{dimension_name}@{feature_name}",
    )
    _telemetry.success(
        f"toleranced {dimension_name}@{feature_name}: +/-{tolerance_degrees:g} deg "
        f"({precision} decimals)"
    )
