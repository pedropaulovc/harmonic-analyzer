"""The title block's general tolerances: the one reader and the one renderer.

``title_block.yaml`` stores each printed general tolerance as a number whose
unit is part of its key (``band_mm`` or ``band_in``, ``plus_mm``,
``radius_mm``, ``value_deg``) and the ``digits`` the sheet prints it at.  This
module is the only code that turns those rows into physical bands or into
title-block text:

* the physical accessors return millimetres (degrees for the angular row)
  whatever unit a row is printed in, converting inches at 25.4 mm/in;
* the ``*_display`` renderers derive the printed text from the number and its
  unit (ASME style: ``±0.51`` in mm, ``±.01`` in inches), never the reverse.

Nothing here parses a display string, and a value with no unit suffix, an
unknown unit, or a non-numeric value is refused, so an inch string can never be
read back as millimetres.

An accepted part is checked against the number its sheet prints and the title
block's row for that many places, not the inch grade behind the row (Codex P2
on #892, the W15 stacks).  A worst-case stack therefore reads each term from
the places its dimension prints at, so a dimension that later prints at more
places tightens its term by itself.

Pure data over ``title_block.yaml``; no SolidWorks, no drawing imports.
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


def _quantity(
    row_name: str, name: str, units: Mapping[str, float]
) -> tuple[float, str]:
    """``(value, unit)`` of the row's single ``<name>_<unit>`` entry.

    Refuses a bare ``<name>`` (no unit), an unknown unit suffix, more than one
    unit, and any value that is not a real number (a display string included).
    """
    row = _config.title_block(row_name)
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


def _length_mm(row_name: str, name: str) -> float:
    value, unit = _quantity(row_name, name, LENGTH_UNITS)
    return value * LENGTH_UNITS[unit]


def _digits(row_name: str) -> int:
    digits = _config.title_block(row_name).get("digits")
    if isinstance(digits, bool) or not isinstance(digits, int) or digits < 0:
        raise ValueError(
            f"title_block.{row_name}.digits must be a non-negative integer, got {digits!r}"
        )
    return digits


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
    value, unit = _quantity(row_name, name, units)
    return render_number(value, unit, _digits(row_name))


# --- physical bands -------------------------------------------------------


def printed_band_mm(places: int) -> float:
    """The title block's printed +/- for a dimension shown at ``places``, in mm."""
    return _length_mm(f"linear_{places}pl", "band")


def drilled_oversize_mm() -> float:
    """The title block's DRILLED HOLES plus allowance, in mm."""
    return _length_mm("drilled_hole", "plus")


def drilled_undersize_mm() -> float:
    """The title block's DRILLED HOLES minus allowance (a hard zero), in mm."""
    return _length_mm("drilled_hole", "minus")


def angular_band_deg() -> float:
    """The title block's general angular +/- in degrees."""
    value, _unit = _quantity("angular", "value", ANGLE_UNITS)
    return value


def edge_break_radius_mm() -> float:
    """The title block's largest edge-break radius, in mm."""
    return _length_mm("edge_break", "radius")


def edge_break_chamfer_mm() -> float:
    """The title block's largest edge-break chamfer, in mm."""
    return _length_mm("edge_break", "chamfer_max")


def inside_corner_radius_mm() -> float:
    """The title block's inside-corner radius ceiling, in mm."""
    return _length_mm("inside_corner", "radius")


# --- title-block text -----------------------------------------------------


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
    value, _unit = _quantity("drilled_hole", "minus", LENGTH_UNITS)
    if value == 0.0:
        return "0"
    return "-" + _render("drilled_hole", "minus", LENGTH_UNITS)


def printed_deviations(
    model: float, places: int, limits: tuple[float, float] | None = None
) -> tuple[float, float]:
    """``(lower, upper)`` deviations from the MODEL value an accepted part may
    show: the sheet prints the model rounded to ``places`` and checks the part
    against that number's limits -- the printed general row unless the
    dimension's own ``(lower, upper)`` limits are given."""
    if limits is None:
        grade = printed_band_mm(places)
        limits = (-grade, grade)
    lower, upper = limits
    printed = round(model, places)
    return printed + lower - model, printed + upper - model
