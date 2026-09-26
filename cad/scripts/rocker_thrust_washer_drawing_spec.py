"""Pure-data drawing contract for the rocker-bank south thrust washer (MHA-148).

Split from ``rocker_thrust_washer_spec`` on purpose: that module gives
``build_channel_assembly`` and ``rocker_bank_layout`` the washer's size, so
product-definition data living there would re-key the channel assembly on a
finish edit (the codex #354 lesson for connecting-rod). This module is
imported only by the part build (which authors the PMI) and its drawing.
"""

from __future__ import annotations

from _gtol_spec import PlanarFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from rocker_thrust_washer_spec import THICKNESS

# Rule 5's running-surface case, twice: the washer is a thrust face on both
# sides. The part runs z 0..THICKNESS and the channel assembly puts its +Z
# face on rocker 0's hub (build_channel_assembly, SOUTH_WASHER_Z); the -Z face
# runs on the south pivot-bracket ear, across the end-play leaf's gap.
# PlanarFace offsets run ALONG the outward normal.
SURFACE_FINISHES = (
    SurfaceFinishControl("hub_face", MACHINED_UM, PlanarFace((0, 0, 1), THICKNESS)),
    SurfaceFinishControl("ear_face", MACHINED_UM, PlanarFace((0, 0, -1), 0.0)),
)
