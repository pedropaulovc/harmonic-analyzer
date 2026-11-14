r"""MHA-DT-03-TL-VN-50 keyed arbor nut: McMaster 95462A505 grade 5 1/4-28 hex nut.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the arbor kit (MHA-DT-03-TL-05) reads the nut from here, so the
stock recipe does not ride its cache key.  The nut runs onto the keyed
cutting arbor's 1/4-28 thread (MHA-DT-03-TL-03) and clamps the backing
collar (MHA-DT-03-TL-04) and the blank to the arbor's shoulder (issue #2465).

Part frame: thread axis local +Z over z = 0..THICKNESS.  The kit places it
with z = 0 on the collar's far face. The thread is not modelled: the plain
bore is the 1/4-28 basic major.
"""

from __future__ import annotations

from _mcmaster_95462a505 import (
    ACROSS_CORNERS,
    ACROSS_FLATS,
    BORE_DIA,
    MASS_G,
    SKU,
    THICKNESS,
    THREAD,
    nut_volume,
)

# Catalogue: 7/16 in AF and 7/32 in height; the height prints .219 REF at
# three places (MHA-MG-VN-52's 3/32 precedent), the bore its .250 nominal major.
DRAWING_REFERENCE_PRECISION = {"AcrossFlats": 0, "Height": 3, "ThreadNominalMajor": 3}
SUPPLIER_FRACTION_DENOMINATOR = 16
SUPPLIER_NOMINAL_MAJOR_MM = 6.35  # .250
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
