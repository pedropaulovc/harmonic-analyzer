r"""MHA-SM-VN-55 counter-anchor jam nut: McMaster 90760A140 thin #10-24 hex nut.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the summing assembly reads the nut from here, so the stock recipe
does not ride its cache key.  The zinc-plated steel narrow-profile nut runs
down the MHA-SM-VN-50 counter anchor (the trimmed 9490T1 open eyebolt) and is
jammed against the MHA-SM-03 summing-lever boss top face, locking the
anchor with its eye clocked (drawing-guidelines.md rule 23).

Part frame: thread axis local +Z over z = 0..THICKNESS, the same frame as
the MHA-PN-VN-55 pen-hanger jam nut.  The axis is published as ``ScrewAxis``.
The thread is not modelled: the bore is the #10-24 basic major diameter.
"""

from __future__ import annotations

from _mcmaster_90760a140 import (
    ACROSS_CORNERS,
    ACROSS_FLATS,
    BORE_DIA,
    MASS_G,
    SKU,
    THICKNESS,
    THREAD,
    nut_volume,
)

# Source drawing: 5/16 in AF and 0.109 in height; exact 7/64 in stays native.
# The thread carrier is the basic nominal major, not a measured thread profile.
DRAWING_REFERENCE_PRECISION = {"AcrossFlats": 0, "Height": 3, "ThreadNominalMajor": 3}
SUPPLIER_FRACTION_DENOMINATOR = 16
SUPPLIER_NOMINAL_MAJOR_MM = 0.190 * 25.4
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
