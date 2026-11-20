r"""MHA-DT-03-TL-VN-51 round arbor nut: McMaster 90480A009 zinc-plated steel #8-32 hex nut.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  The nut runs onto the round cutting arbor's #8-32 thread
(MHA-DT-03-TL-07) and clamps the backing collar (MHA-DT-03-TL-08) and T024
to the arbor's shoulder (issue #2356; owner ruling 2026-11-20, Option 2:
"purchased #8-32 nut under the root").

Part frame: thread axis local +Z over z = 0..THICKNESS; z = 0 bears on the
collar's far face. The thread is not modelled: the plain bore retains the
rounded #8-32 major envelope (``_mcmaster_90480a009``).
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
# The 4.166 mm bore is rounded; do not label it as exact .164 in.
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
