"""Pure stock specification for the MHA-VN-050 magnifying-bracket screws.

The joint layout owns the screw dimensions and nominal engagement. The stock
recipe retains its supplied frame: head +Y, shank -Y, under-head plane Y=0.
"""

from __future__ import annotations

from magnifying_bracket_joint_layout import (
    ENGAGEMENT as ENGAGEMENT_NOMINAL,
    SCREW_HEAD_DIA as HEAD_DIA,
    SCREW_HEAD_HEIGHT as HEAD_H,
    SCREW_LENGTH as LENGTH,
    SCREW_MAJOR_DIA as MAJOR_DIA,
    SCREW_PITCH as PITCH,
    SCREW_SKU as SKU,
    SCREW_THREAD as THREAD,
)

__all__ = [
    "SKU",
    "THREAD",
    "MAJOR_DIA",
    "LENGTH",
    "HEAD_H",
    "HEAD_DIA",
    "PITCH",
    "ENGAGEMENT_NOMINAL",
]
