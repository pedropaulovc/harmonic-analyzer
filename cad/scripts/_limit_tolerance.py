"""A model dimension printed as its two limits (``swTolLIMIT``).

LIMIT prints the upper limit over the lower and no nominal, so a dimension
whose function is a range, rather than a size and a band, reads as that range.
The model holds a nominal inside the limits; the deviations stay on the native
tolerance, and the two limits print at the tolerance precision, which this
sets to the caller's places (as build_pd_platen_guide._depth_limits does).
Separate (as ``_single_limit_tolerance``) to limit cache blast radius: only
the recipes that call it carry it in their closure.
"""

from __future__ import annotations

import math
from typing import Any

import _telemetry
from _com import _early_bound
from _drawing_precision import _named_dimension
from _drawing_tolerances import _set_tolerance_precision

SW_TOL_LIMIT = 3  # swTolType_e.swTolLIMIT


def set_limits(
    adapter: Any,
    feature_name: str,
    dimension_name: str,
    *,
    limits: tuple[float, float],
    places: int,
    display_unit: str,
) -> None:
    """Print ``dimension_name@feature_name`` as the ``(minimum, maximum)`` mm
    limits at ``places`` decimals of ``display_unit``.

    Fails loud when the model's nominal lies outside the limits, when
    SolidWorks rejects the deviations, when ``places`` would round a printed
    limit, or when the type, the deviations or the precision do not read back.
    """
    label = f"{dimension_name}@{feature_name}"
    minimum, maximum = limits
    display, dimension = _named_dimension(adapter, feature_name, dimension_name)
    value = float(dimension.SystemValue) * 1000.0
    if not minimum < value < maximum:
        raise RuntimeError(
            f"{label}: nominal {value:.7f} is outside {minimum:g}-{maximum:g}"
        )
    lower, upper = minimum - value, maximum - value
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = SW_TOL_LIMIT
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != SW_TOL_LIMIT
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: LIMIT tolerance readback changed")
    # The limits, not the deviations around the nominal, are what prints.
    _set_tolerance_precision(
        display, limits, display_unit=display_unit, label=label, places=places
    )
    _telemetry.success(f"{label}: limits {minimum:g}-{maximum:g} mm at {places} places")
