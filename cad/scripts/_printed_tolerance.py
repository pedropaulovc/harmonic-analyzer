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

Pure data over ``title_block.yaml``; no SolidWorks, no drawing imports.
"""

from __future__ import annotations

import _config
from _title_block_units import ANGLE_UNITS, length_mm, quantity


def _length_mm(row_name: str, name: str) -> float:
    return length_mm(row_name, _config.title_block(row_name), name)


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
    row = _config.title_block("angular")
    value, _unit, _digits = quantity("angular", row, "value", ANGLE_UNITS)
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
