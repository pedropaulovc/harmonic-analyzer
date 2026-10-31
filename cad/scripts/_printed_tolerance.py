"""The title block's general tolerances as physical bands, for geometry.

Worst-case stacks, fits and part dimensions that size from the printed general
tolerances read them here, in millimetres (degrees for the angular row),
whatever unit a row is printed in; ``_title_block_units`` converts inches at
25.4 mm/in and refuses a unitless, unknown-unit or non-numeric entry.  This
module is listed in ``_buildgraph.TITLE_BLOCK_GEOMETRY_MODULES``, so any build
whose import closure reaches it keeps ``title_block.yaml`` in its recipe.  The
TOL_* text lives in ``_title_block_units`` so the stamping stays out of that
classification.

An accepted part is checked against the number its sheet prints and the title
block's row for that many places, not the inch grade behind the row (Codex P2
on #892, the W15 stacks).  A worst-case stack therefore reads each term from
the places its dimension prints at, so a dimension that later prints at more
places tightens its term by itself.

Every accessor takes the sheet's ``unit`` (``"mm"``, or ``"in"`` for a
package declaring ``drawing_unit: in``) and returns millimetres either way.

Pure data over ``title_block.yaml``; no SolidWorks, no drawing imports.
"""

from __future__ import annotations

import math

import _config
from _title_block_units import ANGLE_UNITS, LENGTH_UNITS, length_mm, quantity


def _length_mm(row_name: str, name: str, unit: str) -> float:
    return length_mm(row_name, _config.title_block(row_name, unit=unit), name)


# --- physical bands -------------------------------------------------------


def printed_band_mm(places: int, *, unit: str = "mm") -> float:
    """The title block's printed +/- for a dimension shown at ``places``, in mm."""
    return _length_mm(f"linear_{places}pl", "band", unit)


def drilled_oversize_mm(*, unit: str = "mm") -> float:
    """The title block's DRILLED HOLES plus allowance, in mm."""
    return _length_mm("drilled_hole", "plus", unit)


def drilled_undersize_mm(*, unit: str = "mm") -> float:
    """The title block's DRILLED HOLES minus allowance (a hard zero), in mm."""
    return _length_mm("drilled_hole", "minus", unit)


def angular_band_deg(*, unit: str = "mm") -> float:
    """The title block's general angular +/- in degrees."""
    row = _config.title_block("angular", unit=unit)
    value, _unit, _digits = quantity("angular", row, "value", ANGLE_UNITS)
    return value


def edge_break_radius_mm(*, unit: str = "mm") -> float:
    """The title block's largest edge-break radius, in mm."""
    return _length_mm("edge_break", "radius", unit)


def edge_break_chamfer_mm(*, unit: str = "mm") -> float:
    """The title block's largest edge-break chamfer, in mm."""
    return _length_mm("edge_break", "chamfer_max", unit)


def inside_corner_radius_mm(*, unit: str = "mm") -> float:
    """The title block's inside-corner radius ceiling, in mm."""
    return _length_mm("inside_corner", "radius", unit)


def printed_deviations(
    model: float,
    places: int,
    limits: tuple[float, float] | None = None,
    *,
    unit: str = "mm",
) -> tuple[float, float]:
    """``(lower, upper)`` deviations in mm from the MODEL value (mm) an
    accepted part may show: the sheet prints the model rounded to ``places``
    in ``unit`` and checks the part against that number's limits -- the
    printed general row unless the dimension's own ``(lower, upper)`` limits
    (mm) are given."""
    if limits is None:
        grade = printed_band_mm(places, unit=unit)
        limits = (-grade, grade)
    lower, upper = limits
    per_unit = LENGTH_UNITS[unit]
    if unit == "in":
        # set_units_inch rounds half away from zero (swUnitsDecimalRounding
        # HalfAway): .625 prints .63, where round() would give .62. The 1e-9
        # absorbs the mm-to-inch conversion's float error at an exact tie.
        scaled = abs(model / per_unit) * 10**places
        printed = (
            math.copysign(math.floor(scaled + 0.5 + 1e-9) / 10**places, model)
            * per_unit
        )
    else:
        printed = round(model / per_unit, places) * per_unit
    return printed + lower - model, printed + upper - model
