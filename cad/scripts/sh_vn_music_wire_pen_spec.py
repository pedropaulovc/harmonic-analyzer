r"""PenWire member contract of sh-vn-music-wire (MHA-SH-VN-56).

PURE DATA, no SolidWorks/COM imports. The package drawing
``draw_sh_vn_music_wire`` prints only the supplier wire diameter; this member's
straight rest run is installed geometry, not a purchase dimension.
"""

from __future__ import annotations

from sh_vn_music_wire_pen_geom import WIRE_DIA

BOM_DESCRIPTION = f"PEN WIRE 2, {WIRE_DIA / 25.4:.3f} MUSIC WIRE"
