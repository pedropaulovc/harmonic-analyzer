"""Pure McMaster 91882A221 dimensions for its recipe and assembly placement.

Separate from the other thumb-screw SKU and COM recipe to limit cache blast radius.
"""

from __future__ import annotations

THUMB_SPEC = dict(
    major_r=2.8448 / 2.0,
    pitch=0.635,
    length=11.1125,
    collar_r=6.35 / 2.0,
    collar_h=2.38125,
    head_r=9.525 / 2.0,
    head_h=2.38125,
)

HEAD_DIA = 2.0 * THUMB_SPEC["head_r"]
HEAD_H = THUMB_SPEC["head_h"]
HEAD_STACK_LEN = THUMB_SPEC["collar_h"] + THUMB_SPEC["head_h"]
SHANK_DIA = 2.0 * THUMB_SPEC["major_r"]
SHANK_LEN = THUMB_SPEC["length"]
