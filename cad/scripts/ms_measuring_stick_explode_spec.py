"""Pure contract shared by the measuring-stick builder's explode and its drawing.

Names the MS_EXPLODED presentation and the ordered native steps that open it:
the disassembly order, MHA-MS-000's assembly sequence read back to front --
the cover and its screws off the open side, the screws clear of the cover, the
bar out of the opened window, then the thumbscrew down its axis. Each step is
(label, families, axis, signed distance mm) along the assembly's global axes.
Positions come from the opened model; distances are presentation offsets, not
dimensions, sized for the drawing's *Isometric (it looks from +X+Y+Z, the
closed side): each further -Z step slides a part up and right on the sheet,
so the screws withdraw far enough to clear the cover's outline instead of
hiding behind it, and the thumbscrew drops clear of the block.

No local imports: an explode edit reaches the measuring-stick builder and its
drawing, never the top assembly that parks the stick by its placement spec.
"""

from __future__ import annotations

EXPLODED_VIEW_NAME = "MS_EXPLODED"
SOURCE_CONFIGURATION = "Default"
EXPLODE_STEPS = (
    ("cover comes off", ("ms-stop-plate", "vn-ms-stop-plate-screw"), "z", -24.0),
    ("plate screws withdraw", ("vn-ms-stop-plate-screw",), "z", -26.0),
    ("stick leaves window", ("ms-stick",), "z", -12.0),
    ("thumbscrew backs out", ("vn-thumb-screw",), "y", -22.0),
)
