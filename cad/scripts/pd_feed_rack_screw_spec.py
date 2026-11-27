r"""Pure stock specification for the MHA-PD-VN-72 feed-rack screws.

PURE DATA, no SolidWorks/COM imports. McMaster-Carr 91794A060 #0-80 x 1/2
18-8 stainless slotted fillisters, ASME B18.6.3 (owner ruling 2026-11-26,
#3738; ``_mcmaster_91794a060``), used at stock length, untrimmed (x4): each
head sits on a MHA-PD-27 counterbore floor and the thread enters one of the
MHA-PD-26 strip's taps. Four more spare screws are cut and filed to a point
as MHA-PD-00's transfer screws. The engagement, floor and tip-reach facts
live in ``pd_feed_rack_spec`` (SCREW_LENGTH, SCREW_FLOOR, ENGAGEMENT_*).

Frame (the fillister family's): axis +Y, head up, the under-head bearing
face at y = 0 (Top Plane), the factory tip at y = -LENGTH; ``ScrewAxis`` is
Front Plane x Right Plane.
"""

from __future__ import annotations

from _mcmaster_91794a060 import FILLISTER_SIZE, SKU, THREAD

STEM = "pd-vn-feed-rack-screw"
CONFIGURATION = None
MAJOR_DIA, LENGTH, HEAD_H, HEAD_DIA, PITCH = FILLISTER_SIZE
SHANK_DIA = MAJOR_DIA
SHANK_LEN = LENGTH

_IN = 25.4
# ASME B18.6.3-2013: machine screws up to 1 in long carry +0/-.03 in on length.
LENGTH_MINUS = 0.03 * _IN
LENGTH_MIN = LENGTH - LENGTH_MINUS

BOM_DESCRIPTION = f"{THREAD} FILLISTER SCREW, MCMASTER {SKU}"

# --- frame (part mm) ---
AXIS = (0.0, 1.0, 0.0)  # head up
UNDER_HEAD_Y = 0.0
TIP_Y = UNDER_HEAD_Y - LENGTH
