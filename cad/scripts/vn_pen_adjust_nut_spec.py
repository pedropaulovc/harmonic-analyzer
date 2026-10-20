r"""MHA-VN-062 pen-adjust nut: McMaster 92671A115 brass #0-80 hex nut.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the pen carriage reads the nut from here, so the stock recipe does
not ride its cache key.  The nut jams the #0-80 adjuster stud on the pen
rod's top.

Part frame: thread axis local +Z; the nut runs z 0..THICKNESS.  The thread
is not modelled: the bore is the #0-80 basic major diameter.
"""

from __future__ import annotations

from _mcmaster_92671a115 import (
    ACROSS_CORNERS,
    ACROSS_FLATS,
    BORE_DIA,
    MASS_G,
    SKU,
    THICKNESS,
    THREAD,
    nut_volume,
)

# The inspected supplier drawing spells the exact 3/64 in model height as
# 0.047 in. Presentation must never round THICKNESS or the solid geometry.
DRAWING_REFERENCE_PRECISION = {"AcrossFlats": 0, "Height": 3}
SUPPLIER_FRACTION_DENOMINATOR = 32

__all__ = [
    "ACROSS_CORNERS",
    "ACROSS_FLATS",
    "BORE_DIA",
    "DRAWING_REFERENCE_PRECISION",
    "MASS_G",
    "SKU",
    "SUPPLIER_FRACTION_DENOMINATOR",
    "THICKNESS",
    "THREAD",
    "nut_volume",
]
