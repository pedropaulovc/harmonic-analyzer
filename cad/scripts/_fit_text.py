"""Fit-limit drawing text, separate so ink edits do not re-key numerical users.

PURE DATA, no SolidWorks/COM imports.  Every released MAX/MIN final-size
callout must derive from its spec nominal plus a NAMED offset band through
:func:`fit_limits` — literal limit text in a drawing script is a defect: a
spec retune rebuilds the part and the displayed nominal while the released
shop limits silently keep the old values (codex #359 rounds 2-3, six sheets).

The fit CLASSES shared across parts live in ``_fit_ream_slide``,
``_fit_shaft_h`` and ``_fit_ream_h7``; a band peculiar to
one part (an asymmetric mid-nominal ream, a press band) lives as a named
constant in that part's ``*_spec.py`` next to the nominal it tolerances.
"""

from __future__ import annotations

from _fit_deviations import validate_band


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
    validate_band(band)
    low = f"{lower:+.2f}" if lower else "-0.00"
    return f"{upper:+.2f}/{low}"


def fit_limits(
    nominal: float,
    band: tuple[float, float],
    *,
    decimals: int = 3,
    diameter: bool = False,
) -> str:
    """Render ``X.XXX MAX / X.XXX MIN`` from a nominal + (upper, lower) band."""
    upper, lower = band
    validate_band(band)
    prefix = "<MOD-DIAM>" if diameter else ""
    return (
        f"{prefix}{nominal + upper:.{decimals}f} MAX / "
        f"{prefix}{nominal + lower:.{decimals}f} MIN"
    )
