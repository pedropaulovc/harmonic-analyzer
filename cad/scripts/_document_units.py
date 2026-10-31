"""Select an inch package's model document units (issue #290).

A package that declares ``drawing_unit: in`` builds its part or assembly in
IPS decimal inches.  These are calculation settings: the equation manager
evaluates every global at the document's linear places, so the builder calls
:func:`apply_package_model_units` right after ``create_part`` /
``create_assembly``, before any global, sketch, feature or check.  Millimetre
packages keep their template's units untouched.

IPS is selected LAST: native runs showed IPS-first followed by the explicit
length/places writes reads back Custom (4), while IPS-last reads back IPS
with the eight places intact.  Preference IDs and values are from the R2026x
``swconst.tlb`` (swUserPreferenceIntegerValue_e, swUnitSystem_e,
swLengthUnit_e, swFractionDisplay_e).
"""

from __future__ import annotations

from typing import Any

import _telemetry
from _com import _read_member
from _package_units import DrawingUnit

_OPTION_NONE = 0  # swDetailingNoOptionSpecified

# Eight places keep a global such as CamOd = 14.6mm exact to half of 1e-8 in,
# inside the builders' 1e-9 m readback budget; three would re-evaluate it as
# .575 in.  Printed places are each dimension's own DRAWING_PRECISION.
MODEL_INCH_DECIMALS = 8

# (name, swUserPreferenceIntegerValue_e, value) in write order, IPS last.
_INCH_MODEL_UNITS: tuple[tuple[str, int, int], ...] = (
    ("swUnitsLinear", 47, 3),  # swINCHES
    ("swUnitsLinearDecimalDisplay", 48, 1),  # swDECIMAL
    ("swUnitsLinearDecimalPlaces", 49, MODEL_INCH_DECIMALS),
    ("swUnitSystem", 263, 3),  # swUnitSystem_IPS
)


@_telemetry.traced("document.model_units", label_param="label")
def apply_package_model_units(adapter: Any, unit: DrawingUnit, *, label: str) -> None:
    """Select ``unit``'s document units on the active new part or assembly.

    ``"mm"`` writes nothing.  ``"in"`` writes the four inch preferences (IPS
    last), requires each write to return True, then reads all four back and
    raises on any difference.
    """
    if unit == "mm":
        return
    if unit != "in":
        raise ValueError(f"{label}: unknown model unit {unit!r}")
    ext = _read_member(adapter.currentModel, "Extension")
    for name, pref, value in _INCH_MODEL_UNITS:
        if ext.SetUserPreferenceInteger(pref, _OPTION_NONE, value) is not True:
            raise RuntimeError(f"{label}: model unit {name} = {value} rejected")
    actual = {
        name: ext.GetUserPreferenceInteger(pref, _OPTION_NONE)
        for name, pref, _value in _INCH_MODEL_UNITS
    }
    expected = {name: value for name, _pref, value in _INCH_MODEL_UNITS}
    if actual != expected:
        raise RuntimeError(f"{label}: model units read {actual!r}, wrote {expected!r}")
    _telemetry.event("document.model_units.readback", label=label, **actual)
