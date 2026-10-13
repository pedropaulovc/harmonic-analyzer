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

__all__ = [
    "ACROSS_CORNERS",
    "ACROSS_FLATS",
    "BORE_DIA",
    "MASS_G",
    "SKU",
    "THICKNESS",
    "THREAD",
    "nut_volume",
]
