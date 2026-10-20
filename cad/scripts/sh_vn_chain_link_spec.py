"""Pure member specification for the shared McMaster-Carr 6261K171 chain.

InnerLink and OuterLink retain the inherited chain's dimensions and local
frame: the two pin stations are x=0 and x=LINK_PITCH, with pin axes along Z.
These are physical members of one cut chain, not separately purchased SKUs.
"""

from __future__ import annotations

from _chain import (
    BUSH_BORE_R,
    BUSH_HALF_LEN,
    INNER_PLATE_HOLE_R,
    INNER_PLATE_Z,
    OUTER_PLATE_HOLE_R,
    OUTER_PLATE_Z,
    PIN_HALF_LEN,
    PIN_R,
    ROLLER_R,
)

INNER_LINK_CONFIGURATION = "InnerLink"
OUTER_LINK_CONFIGURATION = "OuterLink"
CONFIGURATIONS = (INNER_LINK_CONFIGURATION, OUTER_LINK_CONFIGURATION)

INNER_LINK = dict(
    plate_z=INNER_PLATE_Z,
    plate_hole_r=INNER_PLATE_HOLE_R,
    body_outer_r=ROLLER_R,
    body_bore_r=BUSH_BORE_R,
    body_half_len=BUSH_HALF_LEN,
)
OUTER_LINK = dict(
    plate_z=OUTER_PLATE_Z,
    plate_hole_r=OUTER_PLATE_HOLE_R,
    body_outer_r=PIN_R,
    body_bore_r=None,
    body_half_len=PIN_HALF_LEN,
)
