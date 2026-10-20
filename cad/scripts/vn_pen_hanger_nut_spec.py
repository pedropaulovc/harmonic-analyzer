r"""MHA-VN-063 pen-hanger nut: McMaster 90480A009 zinc-plated steel #8-32 hex nut.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the pen assembly reads the nut from here, so the stock recipe does
not ride its cache key.  The nut runs onto the MHA-VN-007 hanger screw's
thread and bears on the pen-hanger strap's front face; the MHA-VN-064 jam
nut is jammed against it (``joint_retention`` pn-pen/hanger-screw-in-nut).

Part frame: thread axis local +Z over z = 0..THICKNESS.  The pen assembly
places it un-rotated at the strap front less THICKNESS, so z = THICKNESS
bears on the strap and z = 0 carries the jam nut.  The thread is not
modelled: the bore is the #8-32 basic major diameter.
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

# Supplier identification uses native 11/32 in across flats and 0.125 in
# height; these display settings do not alter either exact model constant.
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
