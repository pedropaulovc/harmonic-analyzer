r"""MHA-PN-VN-54 pen-hanger nut: McMaster 90480A009 zinc-plated steel #8-32 hex nut.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the pen assembly reads the nut from here, so the stock recipe does
not ride its cache key.  The nut runs onto the MHA-PN-VN-50 hanger screw's
thread and bears on the pen-hanger strap's front face; the MHA-PN-VN-55 jam
nut is jammed against it (``joint_retention`` pn-pen/hanger-screw-in-nut).

Part frame: thread axis local +Z over z = 0..THICKNESS.  The pen assembly
places it un-rotated at the strap front less THICKNESS, so z = THICKNESS
bears on the strap and z = 0 carries the jam nut. The thread is not
modelled: the plain bore retains the rounded #8-32 major envelope.
"""

from __future__ import annotations

from _mcmaster_90480a009 import (
    ACROSS_CORNERS,
    ACROSS_FLATS,
    BORE_DIA,
    MASS_G,
    SKU,
    THICKNESS,
    THREAD,
    nut_volume,
)

# Source drawing: 11/32 in AF and 0.125 in height; exact 1/8 in stays native.
# The existing 4.166 mm bore is rounded; do not label it as exact .164 in.
DRAWING_REFERENCE_PRECISION = {"AcrossFlats": 0, "Height": 3, "ThreadNominalMajor": 3}
SUPPLIER_FRACTION_DENOMINATOR = 32
SUPPLIER_NOMINAL_MAJOR_MM = 4.1656  # .164
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
