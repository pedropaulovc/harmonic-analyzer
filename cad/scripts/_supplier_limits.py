"""Print a supplier band on its native model dimension as stacked limits.

A bilateral band inside the reference parentheses prints its upper deviation
on its own line above the nominal and reads as a stray value; limits print
max over min inside the one parenthesis. The band stays on the model
dimension (never drawing-only text), as on dt_vn_post_mount_screw.
"""

from __future__ import annotations

from typing import Any

from _com import _early_bound
from _drawing_precision import _named_dimension
from _drawing_tolerances import set_dimension_bilateral_tolerance

LIMIT = 3  # swTolType_e.swTolLIMIT


def set_supplier_limits(
    adapter: Any, feature: str, name: str, lower_mm: float, upper_mm: float
) -> None:
    """Apply the signed deviations, then show them as limits; verify readback."""
    set_dimension_bilateral_tolerance(adapter, feature, name, lower_mm, upper_mm)
    _display, dimension = _named_dimension(adapter, feature, name)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = LIMIT
    lower_m, upper_m = lower_mm / 1000.0, upper_mm / 1000.0
    if not tolerance.SetValues(lower_m, upper_m):
        raise RuntimeError(f"{name}@{feature}: cannot retain supplier limits")
    if (
        int(tolerance.Type) != LIMIT
        or abs(float(tolerance.GetMinValue()) - lower_m) > 1e-9
        or abs(float(tolerance.GetMaxValue()) - upper_m) > 1e-9
    ):
        raise RuntimeError(f"{name}@{feature}: supplier limits did not persist")
