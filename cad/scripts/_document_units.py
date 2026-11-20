"""Select a package's model document units (issues #290, #889).

A package that declares ``drawing_unit: in`` builds its part or assembly in
IPS decimal inches.  These are calculation settings: the equation manager
evaluates every global at the document's linear places, so the builder calls
:func:`apply_package_model_units` right after ``create_part`` /
``create_assembly``, before any global, sketch, feature or check.  Millimetre
packages keep their template's length units untouched.

Every part also gets eight angular places (:func:`keep_equation_angles_exact`):
the template's two rounded ``ConeIncline = 12.5182deg`` to 12.52 (#889).  A
part that never calls :func:`apply_package_model_units` calls that directly.
Assemblies write no angular global, so their angular places are left alone;
``_dimensions.set_global`` fails on any unit literal the document rounds.

IPS is selected LAST: native runs showed IPS-first followed by the explicit
length/places writes reads back Custom (4), while IPS-last reads back IPS
with the eight places intact.  The angular places are written first and read
back with the rest.  Preference IDs and values are from the R2026x
``swconst.tlb`` (swUserPreferenceIntegerValue_e, swUnitSystem_e,
swLengthUnit_e, swFractionDisplay_e).
"""

from __future__ import annotations

from typing import Any

import _telemetry
from _com import _read_member
from _package_units import DrawingUnit

_OPTION_NONE = 0  # swDetailingNoOptionSpecified
_DOC_PART = 1  # swDocumentTypes_e.swDocPART

# Eight places keep a global such as CamOd = 14.6mm exact to half of 1e-8 in,
# inside the builders' 1e-9 m readback budget; three would re-evaluate it as
# .575 in.  Printed places are each dimension's own DRAWING_PRECISION.
MODEL_INCH_DECIMALS = 8
# The same for angles: eight places hold a degree global to 5e-9 deg.
MODEL_ANGLE_DECIMALS = 8

_Preference = tuple[str, int, int]

_ANGULAR_PLACES: tuple[_Preference, ...] = (
    ("swUnitsAngularDecimalPlaces", 52, MODEL_ANGLE_DECIMALS),
)

# (name, swUserPreferenceIntegerValue_e, value) in write order, IPS last.
_INCH_MODEL_UNITS: tuple[_Preference, ...] = (
    ("swUnitsLinear", 47, 3),  # swINCHES
    ("swUnitsLinearDecimalDisplay", 48, 1),  # swDECIMAL
    ("swUnitsLinearDecimalPlaces", 49, MODEL_INCH_DECIMALS),
    ("swUnitSystem", 263, 3),  # swUnitSystem_IPS
)


def _write_and_read_back(
    adapter: Any, preferences: tuple[_Preference, ...], *, label: str, event: str
) -> None:
    """Write ``preferences`` in order, requiring each write to return True,
    then read all of them back and raise on any difference."""
    ext = _read_member(adapter.currentModel, "Extension")
    for name, pref, value in preferences:
        if ext.SetUserPreferenceInteger(pref, _OPTION_NONE, value) is not True:
            raise RuntimeError(f"{label}: model unit {name} = {value} rejected")
    actual = {
        name: ext.GetUserPreferenceInteger(pref, _OPTION_NONE)
        for name, pref, _value in preferences
    }
    expected = {name: value for name, _pref, value in preferences}
    if actual != expected:
        raise RuntimeError(f"{label}: model units read {actual!r}, wrote {expected!r}")
    _telemetry.event(event, label=label, **actual)


@_telemetry.traced("document.angle_places", label_param="label")
def keep_equation_angles_exact(adapter: Any, *, label: str) -> None:
    """Give the active new part eight angular places, read back."""
    _write_and_read_back(
        adapter, _ANGULAR_PLACES, label=label, event="document.angle_places.readback"
    )


@_telemetry.traced("document.model_units", label_param="label")
def apply_package_model_units(adapter: Any, unit: DrawingUnit, *, label: str) -> None:
    """Select ``unit``'s document units on the active new part or assembly.

    A part gets its eight angular places first.  ``"in"`` then writes the
    four inch preferences (IPS last); ``"mm"`` writes no length preference.
    Each write must return True, and all are read back together, raising on
    any difference.
    """
    if unit not in ("mm", "in"):
        raise ValueError(f"{label}: unknown model unit {unit!r}")
    is_part = int(_read_member(adapter.currentModel, "GetType")) == _DOC_PART
    preferences = (_ANGULAR_PLACES if is_part else ()) + (
        _INCH_MODEL_UNITS if unit == "in" else ()
    )
    if preferences:
        _write_and_read_back(
            adapter, preferences, label=label, event="document.model_units.readback"
        )
