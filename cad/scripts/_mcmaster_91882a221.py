"""Pure McMaster 91882A221 dimensions for its recipe and assembly placement.

Separate from the other thumb-screw SKU and COM recipe to limit cache blast radius.

MHA-VN-011 uses this steel raised knurled-head #4-40 x 7/16 in screw.
The native thumb-screw author and assembly placement read the same THUMB_SPEC.

Production part frame (build_vn_thumb_screw): the outer head face lies at X=0,
the axis runs along +X, the collar bearing face is at X=HEAD_STACK_LEN and the
thread tip at X=OVERALL_LEN.
"""

from __future__ import annotations

SKU = "91882A221"
THREAD = "#4-40"

THUMB_SPEC = dict(
    major_r=2.8448 / 2.0,
    pitch=0.635,
    length=11.1125,
    collar_r=6.35 / 2.0,
    collar_h=2.38125,
    head_r=9.525 / 2.0,
    head_h=2.38125,
)

PITCH = THUMB_SPEC["pitch"]
COLLAR_DIA = 2.0 * THUMB_SPEC["collar_r"]
COLLAR_H = THUMB_SPEC["collar_h"]
HEAD_DIA = 2.0 * THUMB_SPEC["head_r"]
HEAD_H = THUMB_SPEC["head_h"]
HEAD_STACK_LEN = COLLAR_H + HEAD_H
SHANK_DIA = 2.0 * THUMB_SPEC["major_r"]
SHANK_LEN = THUMB_SPEC["length"]
OVERALL_LEN = HEAD_STACK_LEN + SHANK_LEN
