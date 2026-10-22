r"""PenWire print contract of sh-vn-music-wire (MHA-SH-VN-56).

PURE DATA, no SolidWorks/COM imports. ``build_sh_vn_music_wire`` marks the
native dimension names and stamps these notes; ``draw_sh_vn_music_wire``
keeps exactly ``DRAWING_DIMENSIONS`` for its PenWire sheet.
"""

from __future__ import annotations

from _mcmaster_9666k56 import SKU
from sh_vn_music_wire_pen_geom import WIRE_DIA

BOM_DESCRIPTION = f"PEN WIRE 2, {WIRE_DIA / 25.4:.3f} MUSIC WIRE"

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  Only the straight rest-run LENGTH (the Wire extrude depth) is
# marked; the purchased wire (McMaster-Carr 9666K56, 0.031 in) is named in a
# note (a 0.8 mm circle is below the ink width of the view), and the form is a
# plain straight run. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "Wire": {"Depth"},
}

# Lines kept short (<~66 chars) so the left-anchored block stays clear of the
# title block (x >= 0.264 m); it grows DOWNWARD from its anchor.
DRAWING_NOTES = "\n".join(
    (
        f"1. PURCHASED WIRE: McMASTER-CARR {SKU}, <MOD-DIAM>0.031 IN.",
        "2. LENGTH SHOWN IS THE STRAIGHT REST RUN, NOT A CUT",
        "   LENGTH.",
        "3. RIM WRAP, EYE TIE-OFF, AND DEVELOPED CUT LENGTH ARE",
        "   NOT DEFINED BY THE SOURCE MODEL. DO NOT RELEASE",
        "   UNTIL THOSE DETAILS ARE SPECIFIED.",
    )
)
ELEVATION_VIEW_NOTE = "ELEVATION SCALE 2:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
