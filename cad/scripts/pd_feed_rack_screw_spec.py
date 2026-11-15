r"""The ``RackScrew`` member of MHA-SH-VN-59: the feed rack's four screws.

PURE DATA, no SolidWorks/COM imports. McMaster-Carr 91794A055 #0-80 x 1/4
slotted fillisters (``sh_vn_fillister_screw_91794a055_spec``), used at stock
length, untrimmed (owner ruling 2026-11-13, #2410): each head sits on a
MHA-PD-27 counterbore floor and the thread enters one of the MHA-PD-26
strip's taps. The engagement, floor and tip-reach facts are the strip's
(``pd_feed_rack_spec``: SCREW_LENGTH, SCREW_FLOOR, ENGAGEMENT_*); this module
only names the member and its frame.

Frame (the fillister family's): axis +Y, head up, the under-head bearing
face at y = 0 (Top Plane), the factory tip at y = -LENGTH; ``ScrewAxis`` is
Front Plane x Right Plane.
"""

from __future__ import annotations

import pd_feed_rack_spec as _rack
import sh_vn_fillister_screw_91794a055_spec as _shared

STEM = _shared.PART_STEM
CONFIGURATION = _shared.RACK_SCREW_CONFIGURATION
BOM_DESCRIPTION = "RACK SCREW"

# The stock 1/4 shank under the head, as the strip's engagement reads it.
LENGTH = _rack.SCREW_LENGTH

# --- frame (part mm) ---
AXIS = (0.0, 1.0, 0.0)  # head up
UNDER_HEAD_Y = 0.0
TIP_Y = UNDER_HEAD_Y - LENGTH
