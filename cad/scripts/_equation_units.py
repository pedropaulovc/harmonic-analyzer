"""Angle-valued equation globals written at full precision (opt-in).

The SOLIDWORKS equation manager rounds a global's evaluated value to the
document's decimal places for its unit.  The project part template carries 8
linear places, so a millimetre global round-trips to ~5e-8 mm, but only 2
angular places: ``"ConeIncline" = 12.5182deg`` was stored as 12.52 deg and drove
the cone pivot post's plane and plan angle off the built geometry, silently,
from r6 to r10 (the r10 leaf log reads ``global ConeIncline = 12.5182deg ->
12.52``).  COM then reads the rounded value back as if it were the truth.

A script that writes an angular global imports this module and calls
:func:`set_angular_global`; nothing else needs it, so it stays out of
``_common`` (whose content keys every build).  The printed angle is unaffected:
a drawing dimension carries its own display precision (``DRAWING_PRECISION``).
"""

from __future__ import annotations

from typing import Any

import _telemetry
from _common import _early_bound, set_global

# swUserPreferenceIntegerValue_e.swUnitsAngularDecimalPlaces, read from the
# SOLIDWORKS 2026 swconst typelib (swUnitsLinearDecimalPlaces = 49 beside it
# matches the adapter's own constant).  8 is the API's maximum.
SW_UNITS_ANGULAR_DECIMAL_PLACES = 52
EQUATION_ANGULAR_DECIMALS = 8
# The stored global must read back the source value to this many degrees.
ANGULAR_GLOBAL_TOLERANCE_DEG = 1e-8


@_telemetry.traced("units.equation_angular_decimals")
def keep_equation_angles_exact(adapter: Any) -> None:
    """Give the active document's angle-valued equations 8 decimal places."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    before = int(
        extension.GetUserPreferenceInteger(SW_UNITS_ANGULAR_DECIMAL_PLACES, 0)
    )
    if not extension.SetUserPreferenceInteger(
        SW_UNITS_ANGULAR_DECIMAL_PLACES, 0, EQUATION_ANGULAR_DECIMALS
    ):
        raise RuntimeError("SetUserPreferenceInteger(angular decimals) failed")
    after = int(
        extension.GetUserPreferenceInteger(SW_UNITS_ANGULAR_DECIMAL_PLACES, 0)
    )
    if after != EQUATION_ANGULAR_DECIMALS:
        raise RuntimeError(f"angular decimal places read {after} after setting 8")
    _telemetry.success(f"angular decimal places {before} -> {after}")


@_telemetry.traced("param.angular_global", label_param="name")
async def set_angular_global(adapter: Any, name: str, degrees: float) -> float:
    """Write ``name = <degrees>deg`` exactly and prove the stored value.

    Widens the document's angular places first, writes the full ``repr`` of
    ``degrees``, and fails loud unless the equation manager stores it within
    :data:`ANGULAR_GLOBAL_TOLERANCE_DEG`.  Returns the stored value.
    """
    keep_equation_angles_exact(adapter)
    stored = await set_global(adapter, name, f"{degrees!r}deg")
    if abs(stored - degrees) > ANGULAR_GLOBAL_TOLERANCE_DEG:
        raise RuntimeError(f"global {name} stored {stored!r} deg, expected {degrees!r}")
    return stored
