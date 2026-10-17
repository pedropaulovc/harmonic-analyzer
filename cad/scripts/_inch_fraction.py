"""Print a vendor part's inch length as its catalogue fraction.

PURE: no SolidWorks, no config.  Purchased fasteners are modelled in
millimetres from inch catalogue sizes (25.4 mm/in), but BOM and ITEM rows
print the catalogue's own fraction (``5/16``, ``1-1/4``).  Deriving that text
from the part's spec length means a SKU or stock-length change moves the
printed fraction with it instead of leaving a typed copy behind; a length
that is not a whole number of 1/64 in raises rather than printing a rounded
fraction.
"""

from __future__ import annotations

from fractions import Fraction

MM_PER_IN = 25.4
DENOMINATOR = 64


def inch_fraction(length_mm: float, *, what: str) -> str:
    """``length_mm`` as a catalogue inch fraction: ``5/16``, ``1``, ``1-1/4``.

    ``what`` names the length in the error a non-1/64 in length raises.
    """
    inches = Fraction(length_mm / MM_PER_IN).limit_denominator(DENOMINATOR)
    if inches <= 0 or abs(float(inches) * MM_PER_IN - length_mm) > 1e-9:
        raise ValueError(
            f"{what}: {length_mm!r} mm is not a positive multiple of 1/{DENOMINATOR} in"
        )
    whole, part = divmod(inches, 1)
    if not part:
        return str(whole)
    if not whole:
        return str(part)
    return f"{whole}-{part}"
