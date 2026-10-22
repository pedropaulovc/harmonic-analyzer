"""The +/- a metric sheet PRINTS for a dimension shown at a given places.

An accepted part is checked against the number its sheet prints and the title
block's row for that many places, not the inch grade behind the row (Codex P2
on #892, the W15 stacks).  A worst-case stack therefore reads each term from
the places its dimension prints at, so a dimension that later prints at more
places tightens its term by itself.

Pure data over ``title_block.yaml``; no SolidWorks, no drawing imports.
"""

from __future__ import annotations

import _config


def printed_band_mm(places: int) -> float:
    """The title block's printed +/- for a dimension shown at ``places``."""
    return float(str(_config.title_block(f"linear_{places}pl")["display"]).lstrip("±"))


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
