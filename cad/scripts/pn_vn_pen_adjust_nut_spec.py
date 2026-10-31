r"""MHA-PN-VN-53 pen-adjust nut: McMaster 92671A115 brass #0-80 hex nut.

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

# Source drawing: 5/32 in AF and 0.047 in height; exact 3/64 in stays native.
# The thread carrier is the basic nominal major, not a measured thread profile.
DRAWING_REFERENCE_PRECISION = {"AcrossFlats": 0, "Height": 3, "ThreadNominalMajor": 3}
SUPPLIER_FRACTION_DENOMINATOR = 32
SUPPLIER_NOMINAL_MAJOR_MM = 1.524  # .060
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("ThreadNominalMajor", SUPPLIER_NOMINAL_MAJOR_MM, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "ThreadNominalMajor": (-SUPPLIER_NOMINAL_MAJOR_MM / 2.0, 0.0),
}

__all__ = [
    "ACROSS_CORNERS",
    "ACROSS_FLATS",
    "BORE_DIA",
    "DRAWING_REFERENCE_PRECISION",
    "MASS_G",
    "SKU",
    "SUPPLIER_FRACTION_DENOMINATOR",
    "SUPPLIER_NOMINAL_MAJOR_MM",
    "SUPPLIER_REFERENCE_DIMENSIONS",
    "SUPPLIER_REFERENCE_STARTS",
    "THICKNESS",
    "THREAD",
    "nut_volume",
]
