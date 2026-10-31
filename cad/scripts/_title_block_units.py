"""Unit-explicit title-block rows: read a row's number with its unit, and render
the title-block text from it.

``title_block.yaml`` stores each printed general tolerance as a number whose
unit is part of its key (``band_mm`` or ``band_in``, ``plus_mm``,
``radius_mm``, ``value_deg``) and the ``digits`` the sheet prints it at.

* ``quantity`` reads one such entry from a row and refuses a value with no unit
  suffix, an unknown unit, two units at once, or a non-numeric value, so an
  inch string can never be read back as millimetres.
* The ``*_display`` renderers derive the TOL_* text from the number and its
  unit (ASME style: ``±0.51`` in mm, ``±.01`` in inches), never the reverse.
* Every reader and renderer takes the sheet's ``unit`` (``"mm"`` default, or
  ``"in"`` for a package declaring ``drawing_unit: in``) and refuses a length
  row printed in any other unit.

The TOL_* stamping (``_part_properties``) imports only this module.  Geometry
that sizes from the printed rows reads them through ``_printed_tolerance``,
which ``_buildgraph.TITLE_BLOCK_GEOMETRY_MODULES`` lists; keeping the two apart
keeps every stamping script out of that geometry classification.

Pure data; no SolidWorks, no drawing imports.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import _config
from _drawing_units import DrawingUnit

MM_PER_INCH = 25.4
# Physical millimetres per printed unit, for length rows.
LENGTH_UNITS: Mapping[str, float] = {"mm": 1.0, "in": MM_PER_INCH}
# Angular rows print and compute in degrees.
ANGLE_UNITS: Mapping[str, float] = {"deg": 1.0}


def quantity(
    row_name: str, row: Mapping[str, Any], name: str, units: Mapping[str, float]
) -> tuple[float, str, int]:
    """``(value, unit, digits)`` of ``row``'s single ``<name>_<unit>`` entry.

    Refuses a bare ``<name>`` (no unit), an unknown unit suffix, more than one
    unit, any value that is not a real number (a display string included), a
    missing ``digits``, and a value the sheet cannot print exactly at
    ``digits``: the physical band must be the band the sheet prints.
    ``row_name`` only labels the errors.
    """
    found: list[tuple[str, Any]] = []
    for key, value in row.items():
        if key == name:
            raise ValueError(
                f"title_block.{row_name}.{name} has no unit; "
                f"use {', '.join(f'{name}_{unit}' for unit in units)}"
            )
        suffix = key.removeprefix(f"{name}_")
        if suffix == key or "_" in suffix:
            continue
        if suffix not in units:
            raise ValueError(
                f"title_block.{row_name}.{key}: unknown unit {suffix!r} "
                f"(known: {', '.join(units)})"
            )
        found.append((suffix, value))
    if len(found) != 1:
        raise ValueError(
            f"title_block.{row_name} needs exactly one {name}_<unit> entry, "
            f"found {[f'{name}_{unit}' for unit, _ in found]}"
        )
    unit, value = found[0]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(
            f"title_block.{row_name}.{name}_{unit} must be a number, got {value!r}"
        )
    digits = row.get("digits")
    if isinstance(digits, bool) or not isinstance(digits, int) or digits < 0:
        raise ValueError(
            f"title_block.{row_name}.digits must be a non-negative integer, got {digits!r}"
        )
    _check_printable(f"title_block.{row_name}.{name}_{unit}", float(value), digits)
    return float(value), unit, digits


def _check_printable(label: str, value: float, digits: int) -> None:
    if abs(round(value, digits) - value) > 1e-9:
        raise ValueError(
            f"{label} = {value!r} does not print exactly at {digits} digits; "
            "the sheet would show a different band than the stacks use"
        )


def render_number(value: float, unit: str, digits: int) -> str:
    """``value`` as the sheet prints it in ``unit`` at ``digits`` decimals.

    ASME Y14.5: millimetre values below one keep their leading zero
    (``0.51``); inch values drop it (``.01``); degrees take the degree sign.
    A value that would round at ``digits`` is refused rather than printed as a
    different number.
    """
    if value < 0.0:
        raise ValueError(f"printed tolerance magnitudes are non-negative: {value!r}")
    _check_printable("printed tolerance", value, digits)
    text = f"{value:.{digits}f}"
    if unit == "mm":
        return text
    if unit == "in":
        return text[1:] if text.startswith("0.") else text
    if unit == "deg":
        return f"{text}°"
    raise ValueError(f"unknown display unit {unit!r}")


def sheet_quantity(
    row_name: str,
    row: Mapping[str, Any],
    name: str,
    units: Mapping[str, float],
    *,
    unit: DrawingUnit,
) -> tuple[float, str, int]:
    """``(value, printed unit, digits)`` of ``row``'s ``<name>_<unit>`` entry,
    where ``row`` is ``_config.title_block(row_name, unit=unit)``.

    A length row must be printed in the sheet's own unit: an inch sheet that
    fell back to a millimetre band (an ``in:`` row missing from
    title_block.yaml), or a millimetre sheet carrying an inch band, is refused
    rather than printed in the wrong unit.
    """
    label = row_name if unit == "mm" else f"{unit}.{row_name}"
    value, printed, digits = quantity(label, row, name, units)
    if units is LENGTH_UNITS and printed != unit:
        raise ValueError(
            f"title_block.{label}.{name}_{printed} cannot print on a {unit!r} "
            f"sheet; it needs {name}_{unit}"
        )
    return value, printed, digits


def sheet_length_mm(
    row_name: str, row: Mapping[str, Any], name: str, *, unit: DrawingUnit
) -> float:
    """``row``'s ``<name>`` length on a ``unit`` sheet, in millimetres."""
    value, printed, _digits = sheet_quantity(
        row_name, row, name, LENGTH_UNITS, unit=unit
    )
    return value * LENGTH_UNITS[printed]


def _render(
    row_name: str, name: str, units: Mapping[str, float], unit: DrawingUnit
) -> str:
    row = _config.title_block(row_name, unit=unit)
    value, printed, digits = sheet_quantity(row_name, row, name, units, unit=unit)
    return render_number(value, printed, digits)


def linear_band_display(places: int, *, unit: DrawingUnit = "mm") -> str:
    """TOL_LIN_X / _XX / _XXX: the printed +/- for ``places``, e.g. ``±0.51``
    (``±.01`` on an inch sheet)."""
    return "±" + _render(f"linear_{places}pl", "band", LENGTH_UNITS, unit)


def angular_band_display(*, unit: DrawingUnit = "mm") -> str:
    """TOL_ANG, e.g. ``±1°``."""
    return "±" + _render("angular", "value", ANGLE_UNITS, unit)


def edge_break_radius_display(*, unit: DrawingUnit = "mm") -> str:
    """TOL_EDGE_BREAK_R, e.g. ``R0.25`` (``R.010``)."""
    return "R" + _render("edge_break", "radius", LENGTH_UNITS, unit)


def edge_break_chamfer_display(*, unit: DrawingUnit = "mm") -> str:
    """TOL_CHAMFER_MAX, e.g. ``0.25`` (``.010``)."""
    return _render("edge_break", "chamfer_max", LENGTH_UNITS, unit)


def inside_corner_display(*, unit: DrawingUnit = "mm") -> str:
    """TOL_INSIDE_CORNER, e.g. ``R1.0 MAX`` (``R.040 MAX``)."""
    return f"R{_render('inside_corner', 'radius', LENGTH_UNITS, unit)} MAX"


def drilled_hole_plus_display(*, unit: DrawingUnit = "mm") -> str:
    """TOL_HOLE_PLUS, the upper deviation with its sign, e.g. ``+0.10``
    (``+.004``)."""
    return "+" + _render("drilled_hole", "plus", LENGTH_UNITS, unit)


def drilled_hole_minus_display(*, unit: DrawingUnit = "mm") -> str:
    """TOL_HOLE_MINUS: a nil limit is a bare ``0`` (ASME Y14.5-2009 §2.3.2),
    any other the signed lower deviation."""
    row = _config.title_block("drilled_hole", unit=unit)
    if sheet_length_mm("drilled_hole", row, "minus", unit=unit) == 0.0:
        return "0"
    return "-" + _render("drilled_hole", "minus", LENGTH_UNITS, unit)
