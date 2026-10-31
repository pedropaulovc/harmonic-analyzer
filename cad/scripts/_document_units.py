"""Native document length units: set an inch package's model units, and read
any document's units back.

A package that declares ``drawing_unit: in`` (issue #290) saves its part or
assembly in IPS with decimal inches, so the source model a drawing imports from
reads in the same unit as the sheet.  Millimetre and legacy packages are left
exactly as their template creates them.  The drawing's own document units are
set by the SDK (``set_units_inch`` / ``set_units_mm``); ``read_document_units``
is the shared readback for both kinds of document.

Preference IDs and values are read off the R2026x ``swconst.tlb``
(swUserPreferenceIntegerValue_e, swUnitSystem_e, swLengthUnit_e,
swFractionDisplay_e), the same constants the SDK's drawing setter uses.  Only
the unit system, length unit, decimal display and decimal places are written:
presentation (leading/trailing zeros, dual dimensions, precision) belongs to
the drawing.
"""

from __future__ import annotations

from typing import Any

import _telemetry
from _com import _read_member
from _drawing_units import DrawingUnit

_PREF_UNIT_SYSTEM = 263  # swUnitSystem
_PREF_UNITS_LINEAR = 47  # swUnitsLinear
_PREF_UNITS_LINEAR_DECIMAL_DISPLAY = 48  # swUnitsLinearDecimalDisplay
_PREF_UNITS_LINEAR_DECIMAL_PLACES = 49  # swUnitsLinearDecimalPlaces
_OPTION_NONE = 0  # swDetailingNoOptionSpecified

UNIT_SYSTEM_IPS = 3  # swUnitSystem_IPS
UNIT_SYSTEM_MMGS = 5  # swUnitSystem_MMGS
LENGTH_MM = 0  # swMM
LENGTH_INCHES = 3  # swINCHES
DECIMAL_DISPLAY = 1  # swDECIMAL

# The model's own display places: the .XXX grid an inch part is dimensioned to.
MODEL_INCH_DECIMALS = 3

# Readback names, in write order (the unit system first: selecting it resets
# the length unit and places, so they are written after it).
_PREFERENCES: tuple[tuple[str, int], ...] = (
    ("unit_system", _PREF_UNIT_SYSTEM),
    ("linear", _PREF_UNITS_LINEAR),
    ("linear_display", _PREF_UNITS_LINEAR_DECIMAL_DISPLAY),
    ("linear_places", _PREF_UNITS_LINEAR_DECIMAL_PLACES),
)


def read_document_units(model: Any) -> dict[str, int]:
    """``model``'s unit system, length unit, decimal display and places, as
    the document extension reports them (option 0).  A non-integer readback
    raises: an unreadable unit is not proof of any unit."""
    ext = _read_member(model, "Extension")
    values: dict[str, int] = {}
    for name, pref in _PREFERENCES:
        value = ext.GetUserPreferenceInteger(pref, _OPTION_NONE)
        if type(value) is not int:
            raise RuntimeError(f"document unit {name} (pref {pref}) read {value!r}")
        values[name] = value
    return values


def expected_document_units(unit: DrawingUnit) -> dict[str, int]:
    """The readback a ``unit`` document must show, independent of places:
    IPS decimal inches, or MMGS millimetres."""
    if unit == "in":
        return {
            "unit_system": UNIT_SYSTEM_IPS,
            "linear": LENGTH_INCHES,
            "linear_display": DECIMAL_DISPLAY,
        }
    if unit == "mm":
        return {"unit_system": UNIT_SYSTEM_MMGS, "linear": LENGTH_MM}
    raise ValueError(f"unknown document unit {unit!r}")


def document_unit_mismatch(
    actual: dict[str, int], unit: DrawingUnit
) -> dict[str, tuple[int, int]]:
    """``{name: (actual, expected)}`` for every readback that is not ``unit``'s."""
    return {
        name: (actual.get(name, -1), want)
        for name, want in expected_document_units(unit).items()
        if actual.get(name) != want
    }


@_telemetry.traced("document.model_units", label_param="label")
def apply_package_model_units(
    adapter: Any, unit: DrawingUnit, *, label: str, model: Any = None
) -> dict[str, int] | None:
    """Select ``unit``'s document units on a package's part or assembly.

    ``"in"`` writes IPS, inches, decimal display and ``MODEL_INCH_DECIMALS``
    places, requires every write to return exactly True, then reads all four
    back and raises on any difference -- including SolidWorks drifting the unit
    system to Custom after the length writes.  ``"mm"`` (a millimetre or legacy
    package) writes nothing and returns ``None``: those models keep the
    template's units, byte for byte.  ``model`` defaults to the active
    document.
    """
    if unit == "mm":
        return None
    if unit != "in":
        raise ValueError(f"{label}: unknown model unit {unit!r}")
    target = adapter.currentModel if model is None else model
    ext = _read_member(target, "Extension")
    wanted = {
        "unit_system": UNIT_SYSTEM_IPS,
        "linear": LENGTH_INCHES,
        "linear_display": DECIMAL_DISPLAY,
        "linear_places": MODEL_INCH_DECIMALS,
    }
    for name, pref in _PREFERENCES:
        value = wanted[name]
        ok = adapter._attempt(
            lambda pref=pref, value=value: ext.SetUserPreferenceInteger(
                pref, _OPTION_NONE, value
            ),
            default=False,
        )
        if ok is not True:
            raise RuntimeError(
                f"{label}: model unit {name} (pref {pref}) = {value} rejected ({ok!r})"
            )
    actual = read_document_units(target)
    if actual != wanted:
        raise RuntimeError(
            f"{label}: model units did not persist: read {actual!r}, wrote {wanted!r}"
        )
    _telemetry.event("document.model_units.readback", label=label, unit=unit, **actual)
    return actual
