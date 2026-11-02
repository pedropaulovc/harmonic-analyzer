r"""MHA-PN-VN-55 pen-hanger jam nut: McMaster 90760A009 thin #8-32 hex nut.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the pen assembly reads the nut from here, so the stock recipe does
not ride its cache key.  The zinc-plated steel small-pattern nut runs onto
the MHA-PN-VN-50 hanger screw outboard of the MHA-PN-VN-54 nut and is jammed
against it, locking the screw (``joint_retention``
pn-pen/hanger-screw-in-nut).

Part frame: thread axis local +Z over z = 0..THICKNESS.  The pen assembly
places it un-rotated on the MHA-PN-VN-54 nut's outer face less THICKNESS, so
z = THICKNESS bears on that nut and z = 0 is the outer face. The thread is
not modelled: the plain bore retains the rounded #8-32 major envelope.
"""

from __future__ import annotations

from _mcmaster_90760a009 import (
    ACROSS_CORNERS,
    ACROSS_FLATS,
    BORE_DIA,
    MASS_G,
    SKU,
    THICKNESS,
    THREAD,
    nut_volume,
)

# Full screw thread standing past the jam nut's outer face, in pitches, the
# screw's tip chamfer excluded: both nuts then run on full thread.
THREAD_PAST_MIN_PITCHES = 2

# Source drawing: 1/4 in AF and 0.094 in height; exact 3/32 in stays native.
# The existing 4.166 mm bore is rounded; do not label it as exact .164 in.
DRAWING_REFERENCE_PRECISION = {"AcrossFlats": 0, "Height": 3, "ThreadNominalMajor": 3}
SUPPLIER_FRACTION_DENOMINATOR = 4
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
    "THREAD_PAST_MIN_PITCHES",
    "nut_volume",
]
