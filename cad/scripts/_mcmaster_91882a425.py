"""Pure McMaster 91882A425 dimensions for the shared thumb-screw recipe.

Kept per-SKU so editing this size does not re-key the 91882A221 part or placements.
"""

from __future__ import annotations

THUMB_SPEC = dict(
    major_r=6.35 / 2.0,
    pitch=1.27,
    length=19.05,
    collar_r=12.7 / 2.0,
    collar_h=9.525,
    head_r=25.4 / 2.0,
    head_h=6.35,
)
