r"""MHA-PN-VN-52 pen-rod set screw: McMaster 91375A105 #4-40 x 3/16 cup point.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the v-block reads the screw from here, so the stock recipe does not
ride its cache key.  One screw runs in the v-block's #4-40 tap onto the pen
rod's turned pivot end and locks it.

Part frame (the vn-arbor/fulcrum-set-screw frame): axis +Y, cup end on the
Top plane at y = 0, socket face at y = +LENGTH.
"""

from __future__ import annotations

from _mcmaster_91375a105 import (
    CUP_DIA,
    HEX_AF,
    LENGTH,
    MAJOR_DIA,
    MASS_G,
    PITCH,
    POINT_LENGTH,
    SKU,
    THREAD,
)

__all__ = [
    "CUP_DIA",
    "HEX_AF",
    "LENGTH",
    "MAJOR_DIA",
    "MASS_G",
    "PITCH",
    "POINT_LENGTH",
    "SKU",
    "THREAD",
]
