"""Inch-fraction lengths for the all-inch dimension experiment.

Models stay in millimetres internally (every SolidWorks call and closure works
in mm); a nominal that a machinist reads off an inch rule is authored here as
an exact fraction so the source says what the drawing will say.

    inch(3, 8)   -> 9.525     # 3/8 in
    inch(1.5)    -> 38.1      # 1-1/2 in
    snap(30.6)   -> 30.1625   # nearest 1/16 in (19/16)
    snap(3.1, 32)-> 3.175     # nearest 1/32 in
"""

from __future__ import annotations

from fractions import Fraction

MM_PER_IN = 25.4
_MM_PER_IN = Fraction("25.4")


def inch(numerator: float, denominator: int = 1) -> float:
    """Return ``numerator/denominator`` inches in millimetres."""
    return float(Fraction(str(numerator)) / denominator * _MM_PER_IN)


def snap(mm: float, denominator: int = 16) -> float:
    """Return ``mm`` rounded to the nearest ``1/denominator`` inch, in mm."""
    return float(Fraction(round(mm / MM_PER_IN * denominator), denominator) * _MM_PER_IN)


def label(mm: float, denominator: int = 32) -> str:
    """Render ``mm`` as a reduced inch fraction (``1-3/8``), for logs and reports."""
    value = Fraction(round(mm / MM_PER_IN * denominator), denominator)
    whole, rest = divmod(value, 1)
    if not rest:
        return f"{whole}"
    if not whole:
        return f"{rest.numerator}/{rest.denominator}"
    return f"{whole}-{rest.numerator}/{rest.denominator}"
