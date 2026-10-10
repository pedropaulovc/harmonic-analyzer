"""Shared fit-limit formatting for released drawing callouts.

PURE DATA, no SolidWorks/COM imports.  Every released MAX/MIN final-size
callout must derive from its spec nominal plus a NAMED offset band through
:func:`fit_limits` — literal limit text in a drawing script is a defect: a
spec retune rebuilds the part and the displayed nominal while the released
shop limits silently keep the old values (codex #359 rounds 2-3, six sheets).

The bands here are the fit CLASSES shared across parts; a band peculiar to
one part (an asymmetric mid-nominal ream, a press band) lives as a named
constant in that part's ``*_spec.py`` next to the nominal it tolerances.
"""

from __future__ import annotations

# Fit classes: (upper, lower) offsets in mm, added to the nominal.
# Reamed slide/running fit for a ground rod or arbor over its shared nominal.
REAM_SLIDE = (0.025, 0.010)
# Ground-shaft h band: nominal down to -0.020.
SHAFT_H = (0.000, -0.020)
# ISO H7 reamed hole, 3-6 mm size range: +0.012 / +0.000.
REAM_H7 = (0.012, 0.000)


def band_text(band: tuple[float, float]) -> str:
    """Render an ``(upper, lower)`` band the way a shop note quotes it.

    Upper deviation first (ASME Y14.5 §2.3.2).  A note that quotes a band beside
    a nominal must render it from the SAME constant the model dimension is
    toleranced with, or the two drift — the half-migrated pattern where the
    nominal is f-stringed and the band beside it is typed.

    A nil deviation keeps its band's SIGN (``-0.00`` on the low side of a
    unilateral band), because that is what the released sheets print today and
    this helper exists to make a relocation a pure refactor.  Y14.5 §2.3.2
    actually prefers a bare ``0`` for a nil limit; switching to it changes ink on
    every affected sheet, so it is a deliberate drawing change to make on its
    own, not a side effect of moving a constant.
    """
    upper, lower = band
    if upper <= lower:
        raise ValueError(f"fit band is inverted: {band!r}")
    low = f"{lower:+.2f}" if lower else "-0.00"
    return f"{upper:+.2f}/{low}"


def deviations(band: tuple[float, float]) -> tuple[float, float]:
    """Return ``(lower, upper)`` — the argument order the model setter takes.

    The bands above are written ``(upper, lower)`` because that is how a fit is
    quoted on a print (upper deviation first, ASME Y14.5 §2.3.2), but
    ``_drawing_marks.set_dimension_bilateral_tolerance`` takes
    ``(lower_deviation_mm, upper_deviation_mm)``.  BOTH orderings type-check and
    a silent swap INVERTS the band, so no call site is allowed to transpose by
    hand — splat this instead::

        set_dimension_bilateral_tolerance(adapter, "StubProfile", "SeatDia",
                                          *deviations(SHAFT_H))
    """
    upper, lower = band
    if upper <= lower:
        raise ValueError(f"fit band is inverted: {band!r}")
    return lower, upper


def fit_limits(
    nominal: float,
    band: tuple[float, float],
    *,
    decimals: int = 3,
    diameter: bool = False,
) -> str:
    """Render ``X.XXX MAX / X.XXX MIN`` from a nominal + (upper, lower) band."""
    upper, lower = band
    if upper <= lower:
        raise ValueError(f"fit band is inverted: {band!r}")
    prefix = "<MOD-DIAM>" if diameter else ""
    return (
        f"{prefix}{nominal + upper:.{decimals}f} MAX / "
        f"{prefix}{nominal + lower:.{decimals}f} MIN"
    )
