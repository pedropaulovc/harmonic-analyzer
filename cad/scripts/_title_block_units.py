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

MM_PER_INCH = 25.4
# Physical millimetres per printed unit, for length rows.
LENGTH_UNITS: Mapping[str, float] = {"mm": 1.0, "in": MM_PER_INCH}
# Angular rows print and compute in degrees.
ANGLE_UNITS: Mapping[str, float] = {"deg": 1.0}


def quantity(
    row_name: str, row: Mapping[str, Any], name: str, units: Mapping[str, float]
) -> tuple[float, str]:
    """``(value, unit)`` of ``row``'s single ``<name>_<unit>`` entry.

    Refuses a bare ``<name>`` (no unit), an unknown unit suffix, more than one
    unit, and any value that is not a real number (a display string included).
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
    return float(value), unit


def length_mm(row_name: str, row: Mapping[str, Any], name: str) -> float:
    """``row``'s ``<name>_<unit>`` length in millimetres."""
    value, unit = quantity(row_name, row, name, LENGTH_UNITS)
    return value * LENGTH_UNITS[unit]


def render_number(value: float, unit: str, digits: int) -> str:
    """``value`` as the sheet prints it in ``unit`` at ``digits`` decimals.

    ASME Y14.5: millimetre values below one keep their leading zero
    (``0.51``); inch values drop it (``.01``); degrees take the degree sign.
    """
    if value < 0.0:
        raise ValueError(f"printed tolerance magnitudes are non-negative: {value!r}")
    text = f"{value:.{digits}f}"
    if unit == "mm":
        return text
    if unit == "in":
        return text[1:] if text.startswith("0.") else text
    if unit == "deg":
        return f"{text}°"
    raise ValueError(f"unknown display unit {unit!r}")


def _render(row_name: str, name: str, units: Mapping[str, float]) -> str:
    row = _config.title_block(row_name)
    value, unit = quantity(row_name, row, name, units)
    digits = row.get("digits")
    if isinstance(digits, bool) or not isinstance(digits, int) or digits < 0:
        raise ValueError(
            f"title_block.{row_name}.digits must be a non-negative integer, got {digits!r}"
        )
    return render_number(value, unit, digits)


def linear_band_display(places: int) -> str:
    """TOL_LIN_X / _XX / _XXX: the printed +/- for ``places``, e.g. ``±0.51``."""
    return "±" + _render(f"linear_{places}pl", "band", LENGTH_UNITS)


def angular_band_display() -> str:
    """TOL_ANG, e.g. ``±1°``."""
    return "±" + _render("angular", "value", ANGLE_UNITS)


def edge_break_radius_display() -> str:
    """TOL_EDGE_BREAK_R, e.g. ``R0.25``."""
    return "R" + _render("edge_break", "radius", LENGTH_UNITS)


def edge_break_chamfer_display() -> str:
    """TOL_CHAMFER_MAX, e.g. ``0.25``."""
    return _render("edge_break", "chamfer_max", LENGTH_UNITS)


def inside_corner_display() -> str:
    """TOL_INSIDE_CORNER, e.g. ``R1.0 MAX``."""
    return f"R{_render('inside_corner', 'radius', LENGTH_UNITS)} MAX"


def drilled_hole_plus_display() -> str:
    """TOL_HOLE_PLUS, the upper deviation with its sign, e.g. ``+0.10``."""
    return "+" + _render("drilled_hole", "plus", LENGTH_UNITS)


def drilled_hole_minus_display() -> str:
    """TOL_HOLE_MINUS: a nil limit is a bare ``0`` (ASME Y14.5-2009 §2.3.2),
    any other the signed lower deviation."""
    row = _config.title_block("drilled_hole")
    if length_mm("drilled_hole", row, "minus") == 0.0:
        return "0"
    return "-" + _render("drilled_hole", "minus", LENGTH_UNITS)
