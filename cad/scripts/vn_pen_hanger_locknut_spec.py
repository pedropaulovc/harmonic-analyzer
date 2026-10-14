r"""MHA-VN-063 pen-hanger locknut: McMaster 90631A009 #8-32 nylon-insert locknut.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the pen assembly reads the nut from here, so the stock recipe does
not ride its cache key.  The nut runs onto the MHA-VN-007 hanger screw's
thread on the pen-hanger strap's front face; its nylon insert's prevailing
torque locks the screw (``joint_retention`` pn-pen/hanger-screw-in-locknut).

Part frame: thread axis local +Z over z = 0..THICKNESS.  The pen assembly
places it un-rotated at the strap front less THICKNESS, so z = THICKNESS
bears on the strap and z = 0 is the insert end.  Neither the thread nor the
insert is modelled: the bore is the #8-32 basic major diameter.
"""

from __future__ import annotations

from _mcmaster_90631a009 import (
    ACROSS_CORNERS,
    ACROSS_FLATS,
    BORE_DIA,
    MASS_G,
    SKU,
    THICKNESS,
    THREAD,
    THREAD_PAST_MIN_PITCHES,
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
    "THREAD_PAST_MIN_PITCHES",
    "nut_volume",
]
