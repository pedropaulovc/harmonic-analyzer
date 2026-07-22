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
