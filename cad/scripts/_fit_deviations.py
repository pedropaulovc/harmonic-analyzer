"""Numerical fit deviations and validation, separate from class data and drawing ink.

No SolidWorks/COM imports. Class and text edits must not re-key every model
that only needs validated numerical deviations.
"""

from __future__ import annotations


def validate_band(band: tuple[float, float]) -> None:
    """Reject inverted or zero-width ``(upper, lower)`` fit bands."""
    upper, lower = band
    if upper <= lower:
        raise ValueError(f"fit band is inverted: {band!r}")


def deviations(band: tuple[float, float]) -> tuple[float, float]:
    """Return ``(lower, upper)`` — the argument order the model setter takes.

    The named bands are written ``(upper, lower)`` because that is how a fit is
    quoted on a print (upper deviation first, ASME Y14.5 §2.3.2), but
    ``_drawing_marks.set_dimension_bilateral_tolerance`` takes
    ``(lower_deviation_mm, upper_deviation_mm)``.  BOTH orderings type-check and
    a silent swap INVERTS the band, so no call site is allowed to transpose by
    hand — splat this instead::

        set_dimension_bilateral_tolerance(adapter, "StubProfile", "SeatDia",
                                          *deviations(SHAFT_H))
    """
    upper, lower = band
    validate_band(band)
    return lower, upper
