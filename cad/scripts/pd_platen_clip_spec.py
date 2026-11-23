r"""MHA-PD-03 platen clip: the part frame and the sheet's notes, read by the
feature export (export_features) only.

The clip's nominals predate the #880 spec split and live in
``build_pd_platen_clip``, which ``draw_pd_platen_clip`` already imports; its
feature declarations name them there explicitly. Nothing imports this module
but the exporter, so it keys neither the part nor the drawing.

Part frame (``build_pd_platen_clip``): length along +X from the near end,
width along +Y from the screw rail's outer edge, the flat rail's outward face
(where the screw heads seat) at z = 0 and its platen face at z = SHEET_T; the
bows crest ARCH_RISE outboard of z = 0, toward -Z.
"""

from __future__ import annotations

# The sheet prints no numbered note: every requirement is a dimension, its
# band or its callout, so the feature manifest's notes are empty.
DRAWING_NOTES = ""
