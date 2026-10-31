"""Native document length units: set an inch package's model units, and read
any document's units back.

A package that declares ``drawing_unit: in`` (issue #290) builds its part or
assembly in IPS with decimal inches, so the source model a drawing imports from
reads in the same unit as the sheet.  Millimetre and legacy packages are left
exactly as their template creates them.  The drawing's own document units are
set by the SDK (``set_units_inch`` / ``set_units_mm``); ``read_document_units``
is the shared readback for both kinds of document.

The model's units are CALCULATION settings, not presentation: the equation
manager evaluates every global in them, so the builder selects them once,
right after ``create_part`` / ``create_assembly`` and before any global,
sketch, feature or check (``apply_package_model_units``).  The save
chokepoints only prove the readback (``require_package_model_units``); they
never switch units under geometry that was already checked.

Preference IDs and values are read off the R2026x ``swconst.tlb``
(swUserPreferenceIntegerValue_e, swUnitSystem_e, swLengthUnit_e,
swFractionDisplay_e), the same constants the SDK's drawing setter uses.  Only
the unit system, length unit, decimal display and decimal places are written:
presentation (leading/trailing zeros, dual dimensions, printed precision)
belongs to each dimension's ``DRAWING_PRECISION`` and to the drawing.
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

# The model's CALCULATION places, not the grid it prints to.  The equation
# manager rounds a length global to the document's linear places for its unit
# (memory sw-globals-rounded-to-doc-decimals); the part template carries 8, so
# 8 keeps a global such as CamOd = 14.6mm exact to half of 1e-8 in (~1.3e-10 m,
# inside the builders' 1e-9 m readback budget).  Three places would re-evaluate
# it as .575 in (14.605 mm).  The printed places are each dimension's
# ``DRAWING_PRECISION`` and the sheet's own ``set_units_inch(decimals=...)``.
MODEL_INCH_DECIMALS = 8

_INCH_MODEL_UNITS: dict[str, int] = {
    "unit_system": UNIT_SYSTEM_IPS,
    "linear": LENGTH_INCHES,
    "linear_display": DECIMAL_DISPLAY,
    "linear_places": MODEL_INCH_DECIMALS,
}

# Readback names, in write order.  The native cam canary read Custom after
# explicit component writes despite the earlier IPS selection.  Selecting IPS
# last preserved IPS and eight places on the native canary. Read every field
# afterward because the selector must preserve the equation-safe eight places.
_PREFERENCES: tuple[tuple[str, int], ...] = (
    ("linear", _PREF_UNITS_LINEAR),
    ("linear_display", _PREF_UNITS_LINEAR_DECIMAL_DISPLAY),
    ("linear_places", _PREF_UNITS_LINEAR_DECIMAL_PLACES),
    ("unit_system", _PREF_UNIT_SYSTEM),
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


def _package_model_units(unit: DrawingUnit, label: str) -> dict[str, int] | None:
    """The full readback ``unit``'s model must show, or ``None`` for a
    millimetre/legacy model, which keeps its template's units untouched."""
    if unit == "mm":
        return None
    if unit != "in":
        raise ValueError(f"{label}: unknown model unit {unit!r}")
    return dict(_INCH_MODEL_UNITS)


def model_unit_mismatch(
    actual: dict[str, int], unit: DrawingUnit
) -> dict[str, tuple[int, int]]:
    """``{name: (actual, expected)}`` for every readback a ``unit`` MODEL gets
    wrong, its ``MODEL_INCH_DECIMALS`` calculation places included (a drawing's
    places are its own presentation, so ``document_unit_mismatch`` ignores
    them).  A millimetre/legacy model has no invariant here: empty."""
    wanted = _package_model_units(unit, "model")
    if wanted is None:
        return {}
    return {
        name: (actual.get(name, -1), want)
        for name, want in wanted.items()
        if actual.get(name) != want
    }


@_telemetry.traced("document.model_units", label_param="label")
def apply_package_model_units(
    adapter: Any, unit: DrawingUnit, *, label: str, model: Any = None
) -> dict[str, int] | None:
    """Select ``unit``'s document units on a package's new part or assembly.

    Call it right after ``create_part`` / ``create_assembly``, before the
    first global, sketch, feature or check: the unit system and places decide
    how every global evaluates, so geometry built and checked before this call
    would be re-evaluated unchecked.

    ``"in"`` writes IPS, inches, decimal display and ``MODEL_INCH_DECIMALS``
    places, requires every write to return exactly True, then reads all four
    back and raises on any difference -- including SolidWorks drifting the unit
    system to Custom after the length writes.  ``"mm"`` (a millimetre or legacy
    package) writes nothing and returns ``None``: those models keep the
    template's units, byte for byte.  ``model`` defaults to the active
    document.
    """
    wanted = _package_model_units(unit, label)
    if wanted is None:
        return None
    target = adapter.currentModel if model is None else model
    ext = _read_member(target, "Extension")
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


@_telemetry.traced("document.model_units.require", label_param="label")
def require_package_model_units(
    adapter: Any, unit: DrawingUnit, *, label: str, model: Any = None
) -> dict[str, int] | None:
    """Prove, writing nothing, that ``unit``'s model units are already selected.

    The save chokepoints call this instead of selecting units: the builder
    selected them before its first global (``apply_package_model_units``), so
    every geometry check already ran under them.  Any difference -- a builder
    that skipped the early setup, or places that drifted -- raises before the
    save; switching now would re-evaluate checked globals and publish a part no
    check saw.  ``"mm"`` reads nothing and returns ``None``.
    """
    wanted = _package_model_units(unit, label)
    if wanted is None:
        return None
    actual = read_document_units(adapter.currentModel if model is None else model)
    if actual != wanted:
        raise RuntimeError(
            f"{label}: model units read {actual!r}, expected {wanted!r}; select them "
            "with apply_package_model_units right after create_part/create_assembly, "
            "before any global, sketch or check -- never at save"
        )
    _telemetry.event("document.model_units.proved", label=label, unit=unit, **actual)
    return actual
