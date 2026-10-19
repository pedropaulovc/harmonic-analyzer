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
