"""Pure contract shared by the measuring-stick builder's explode and its drawing.

Names the MS_EXPLODED presentation and the ordered native steps that open it:
the disassembly order, MHA-MS-00's assembly sequence read back to front --
the cover and its screws off the open side, the screws clear of the cover, the
bar out of the opened window, then the thumbscrew up its axis. Each step is
(label, families, axis, signed distance mm) along the assembly's global axes.
Positions come from the opened model; distances are presentation offsets, not
dimensions. The named MS CLAMP EXPLODED ISOMETRIC preserves the original
graduation inspection: viewer +X-Y-Z, sheet up -Y. Positive Z steps slide
parts up and right, clear of the cover; the screw backs out above the block.

No local imports: an explode edit reaches the measuring-stick builder and its
drawing, never the top assembly that parks the stick by its placement spec.
"""

from __future__ import annotations

EXPLODED_VIEW_NAME = "MS_EXPLODED"
SOURCE_CONFIGURATION = "Default"
EXPLODE_STEPS = (
    ("cover comes off", ("ms-stop-plate", "ms-vn-stop-plate-screw"), "z", 24.0),
    ("plate screws withdraw", ("ms-vn-stop-plate-screw",), "z", 26.0),
    ("stick leaves window", ("ms-stick",), "z", 12.0),
    ("thumbscrew backs out", ("ms-vn-thumb-screw",), "y", 22.0),
)
