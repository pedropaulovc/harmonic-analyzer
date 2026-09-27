r"""Amplitude-bar drawing prose -- the manufacturing notes the part build stamps
into the SLDPRT, the view labels, and the notch-depth band the notes print.

Split OUT of ``amplitude_bar_spec`` (the ``rocker_arm_notes`` treatment, codex
#354): the channel kinematics, the rocker-bank layout and the spring specs
import the bar's geometry, so drawing prose in that import closure re-keyed
the channel, magnifier and summing assemblies on every notes edit.  Imported
ONLY by ``build_amplitude_bar`` and the offline tests.
"""

from __future__ import annotations

from _hole_spec import drill_process
from amplitude_bar_spec import BOTTOM_NOTCH_HEIGHT, TOP_PIN_HOLE_SPEC

# The foot notch's roof rides the rocker's top edge, and at d = 0 the cheeks
# either side pass over the rocker hub; a deep notch drops them onto it one
# for one. So the depth is one-sided, shallow only (user ruling 2026-09-26):
# a shallow notch just lifts the bar at rest (rocker_arm_spec.TOP_EDGE_BAND
# states the lift budget and its effect on the channel).
BOTTOM_NOTCH_DEPTH_BAND = (0.0, -0.50)  # (upper, lower) deviations

# The title-block QTY cell owns the 20-off count; notch orientation and
# coplanarity are stated because no view resolves them at 1:4 (machinist
# round 1): both notches live in ONE profile sketch cut thru the full depth,
# so open-to-opposite-ends / common-plane / centred-on-width IS the model
# truth, and the pin hole runs thru the top-notch cheeks at mid-depth.
DRAWING_NOTES = "\n".join(
    (
        "1. BAR SECTION 6.35 SQUARE.",
        # One-sided: the upper deviation is zero (tested).
        f"2. BOTTOM NOTCH 3.18 W x {BOTTOM_NOTCH_HEIGHT:.2f}"
        f" +0/{BOTTOM_NOTCH_DEPTH_BAND[1]:.2f} DEEP;",
        "   TOP NOTCH 3.18 W x 12.70 DEEP;",
        "   BOTH THRU THE FULL DEPTH, OPEN TO",
        "   OPPOSITE ENDS, CENTRED ON THE WIDTH",
        "   WITHIN 0.10, IN ONE COMMON PLANE;",
        "   ROOTS R0.40 MAX.",
        f"3. TOP PIN HOLE {drill_process(TOP_PIN_HOLE_SPEC)} THRU BOTH",
        "   TOP-NOTCH CHEEKS AT MID-DEPTH,",
        "   6.35 BELOW THE BAR TOP.",
        "4. BOTTOM NOTCH FLOOR: Ra 0.8.",
        "5. DIMS APPLY AFTER PLATING.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:8"
END_VIEW_NOTE = "END VIEW SCALE 4:1"
