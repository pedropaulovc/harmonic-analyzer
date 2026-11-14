r"""PenWire member contract of sh-vn-music-wire (MHA-SH-VN-56).

PURE DATA, no SolidWorks/COM imports. The package drawing
``draw_sh_vn_music_wire`` prints only the supplier wire diameter; this member's
straight rest run is installed geometry, not a purchase dimension.
"""

from __future__ import annotations

from _mcmaster_9666k142 import DIA_IN

# The catalogue size (.008).
BOM_DESCRIPTION = f"PEN WIRE 2, {f'{DIA_IN:.3f}'.removeprefix('0')} MUSIC WIRE"
