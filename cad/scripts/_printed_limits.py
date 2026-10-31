"""Numeric acceptance limits for drawing-owned feature requirements.

``limits(model, places, band=None, *, unit="mm")`` returns rounded
``[low, high]`` acceptance limits; an explicit native ``(upper, lower)`` band
qualifies the exact model nominal, while a general band qualifies its printed
nominal on a ``unit`` sheet. ``drilled_limits(model, places, *, unit="mm")``
uses that sheet's title-block drilled-hole band.

Pure data over ``title_block.yaml``; no SolidWorks or drawing declarations.
Drawing/feature-only: native geometry safeguards derive their bounds directly
from the unchanged ``_printed_tolerance.printed_deviations`` helper instead.
Neither native specs nor builders import this module, so drawing/feature-only
numeric edits cannot re-key native part or assembly recipes.
"""

from __future__ import annotations

from _printed_tolerance import drilled_oversize_mm, drilled_undersize_mm, printed_deviations


def limits(
    model: float,
    places: int,
    band: tuple[float, float] | None = None,
    *,
    unit: str = "mm",
) -> list[float]:
    """``[low, high]`` for a dimension: its explicit ``(upper, lower)`` native
    tolerance, else the general grade of its printed places on a ``unit``
    sheet."""
    # An explicit native tolerance qualifies the exact source dimension.
    # General grades qualify its printed nominal; use the source's Python
    # formatting convention without inventing a SolidWorks rounding mode.
    if band is not None:
        return [round(model + band[1], 12), round(model + band[0], 12)]
    low, high = printed_deviations(model, places, unit=unit)
    return [round(model + low, 12), round(model + high, 12)]


def drilled_limits(model: float, places: int, *, unit: str = "mm") -> list[float]:
    """Native Hole Wizard nominal with the ``unit`` sheet's printed drilled-hole
    deviations."""
    return limits(
        model, places, (drilled_oversize_mm(unit=unit), -drilled_undersize_mm(unit=unit))
    )
