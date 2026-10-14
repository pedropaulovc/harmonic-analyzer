r"""MHA-VN-064 pen-hanger jam nut: McMaster 90760A009 thin #8-32 hex nut.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the pen assembly reads the nut from here, so the stock recipe does
not ride its cache key.  The zinc-plated steel small-pattern nut runs onto
the MHA-VN-007 hanger screw outboard of the MHA-VN-063 nut and is jammed
against it, locking the screw (``joint_retention``
pn-pen/hanger-screw-in-nut).

Part frame: thread axis local +Z over z = 0..THICKNESS.  The pen assembly
places it un-rotated on the MHA-VN-063 nut's outer face less THICKNESS, so
z = THICKNESS bears on that nut and z = 0 is the outer face.  The thread is
not modelled: the bore is the #8-32 basic major diameter.
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

__all__ = [
    "ACROSS_CORNERS",
    "ACROSS_FLATS",
    "BORE_DIA",
    "MASS_G",
    "SKU",
    "THICKNESS",
    "THREAD",
    "THREAD_PAST_MIN_PITCHES",
    "nut_volume",
]
