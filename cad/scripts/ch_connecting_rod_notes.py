r"""Connecting-rod drawing-only data -- the marked-dimension and precision
contract, the numbered fit notes and the isometric-view label the part build
stamps into the SLDPRT.

Split OUT of ``ch_connecting_rod_spec`` (codex #354): assemblies import
geometry from the spec, so drawing-only prose living there made every notes
edit full-rebuild ``assembly:ch_channel``.  This module is imported ONLY by
``build_ch_connecting_rod`` (which stamps the properties), the drawing and the
offline drawing test -- never by an assembly -- so a notes edit rebuilds the
part + drawing and leaves the assembly to its cheap token refresh.
"""

from __future__ import annotations

from _milled_corner_limit import CORNER_PLACES, CORNER_R, CORNER_REASON, corner_prefix

# The four corners where the shank's flanks meet the ring's OD and the fork's
# step keep the 1/8 in end mill's radius: nothing seats in them. Owner ruling
# 2026-11-23, tool audit Q9: "Print a local corner limit R.065 (.060-.070),
# cut with the 1/8 end mill; no 5/64 cutter" (_milled_corner_limit). The two
# ring corners are one fillet (ShankCorners), the two step corners one boss
# (StepCorners: the step is narrower than the radius, so the cutter's arc
# runs from the flank onto the step's outer corner); one global drives both,
# and the front view prints the fillet's radius as 4X R.065 at the title
# block's .XXX (.060-.070), with the reason beneath it. Here, not in
# ch_connecting_rod_spec, so the change re-keys the rod and its sheet alone.
SHANK_CORNER_R = CORNER_R  # .065
SHANK_CORNER_COUNT = 4
SHANK_CORNER_CALLOUT = CORNER_REASON
DIMENSION_PREFIXES: dict[tuple[str, str], str] = {
    ("ShankCorners", "ShankCornerR"): corner_prefix(SHANK_CORNER_COUNT),
}

# Every size, location and band prints from its native model dimension, and
# each tight band names its mate at its own callout or through a flag note
# that callout links (drawing-guidelines.md rules 4 and 7). The tines' known
# shortfall against the .080 wall target is the near tine's own printed lower
# limit, named TINE WALL on its callout (rule 20). The material (1018 CF flat),
# the black finish and the other inside corners' R.040 MAX are title-block
# rows, never restated here (rule 2); the four shank corners print their own
# R.065 (SHANK_CORNER_R).
#
# Note 1 is the reamed pin hole's press fit, linked from its callout. Owner
# ruling 2026-11-24, fit audit question 3: the hole is reamed .0775 and
# prints the reamer's size with no band (drawing-guidelines.md rule 4, form
# 3: reamed to the bought mate); the pin itself is the gauge: it presses in,
# it does not enter by hand. A pin that does enter by hand is bonded at
# MHA-CH-00, not a scrapped rod; no gauge pins.
#
# Notes 2 and 3 each name one mate for two tight bands that serve it (fan-out
# rounds 1-2: named at both callouts it printed twice, named at one the other
# band had none): the fork slot's width and the tine walls that locate it run
# on the arm; the ring's thickness and its near face's offset from the fork's
# datum face slide in the cam's slot, which locates the rod along the bank
# (owner ruling 2026-11-18, #3114: the arm floats on its shaft and follows
# the fork). The shank is stepped inside both ring faces and fits nothing,
# so its two dimensions link no note.
PIN_NAME = "ROD PIVOT PIN"
PIN_NUMBER = "MHA-SH-VN-58"  # its RodPin member
ARM_NUMBER = "MHA-CH-06"
CAM_NUMBER = "MHA-DT-12"
PIN_FIT_NOTE_NUMBER = 1
SLOT_FIT_NOTE_NUMBER = 2
CAM_SLOT_NOTE_NUMBER = 3
DRAWING_NOTES = "\n".join(
    (
        f"{PIN_FIT_NOTE_NUMBER}. PRESS FIT ON {PIN_NAME} {PIN_NUMBER}:",
        "    THE PIN DOES NOT ENTER BY HAND.",
        f"{SLOT_FIT_NOTE_NUMBER}. FORK SLOT: RUNNING FIT ON ARM {ARM_NUMBER}.",
        f"{CAM_SLOT_NOTE_NUMBER}. RING: SLIDING FIT IN {CAM_NUMBER} CAM SLOT; LOCATES ROD.",
    )
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  build_ch_connecting_rod marks exactly these. Each feature's
# dimensions print in one view, so a view's import brings nothing it must
# delete: RingFaceReference is a reference sketch of its own, apart from the
# fork's ForkSlotProfile, because the side view prints the ring's near face
# and the fork's detail prints the rest. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"RingOuterDia"},
    "Ring": {"RingThick"},
    "ShankProfile": {"ShankThick"},
    "Shank": {"ShankWidthDim"},
    "StrapBoreProfile": {"StrapBoreDia"},
    "ForkProfile": {"ForkWidthDim"},
    "ForkBoss": {"ForkThick"},
    "ForkSlotProfile": {
        "TineNear",
        "SlotWidth",
        "ShankFaceNear",
        "SlotDepth",
        "ForkBossLength",
    },
    "RingFaceReference": {"RingFaceNear"},
    "PinHoleProfile": {"PinHoleDia"},
    "ShankCorners": {"ShankCornerR"},
}

# Decimal-inch places (#290): the tines, slot, the ring's near face and its
# thickness hold the inter-arm gap and the ring's slide in its cam slot, so
# they print at three places with their +/-.002 bands; the fork over the tines
# is their reference sum at the same places. The shank's near face and
# thickness print at two places (.05 and .13: machinist review found a third
# place there over-specified) and take the title block's .XX: that band
# keeps both shank faces inside the ring's
# (ch_connecting_rod_spec.SHANK_INSIDE_RING_MIN). The strap bore prints 1.213
# at three with its +.005/.000; the reamed press hole at four; the shank's
# four corners R.065 at three (the title block's .XXX is their .060-.070).
# The ring OD, shank width, fork width, slot depth and boss length take the
# title block's .XX too.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"RingOuterDia": 2},
    "Ring": {"RingThick": 3},
    "ShankProfile": {"ShankThick": 2},
    "Shank": {"ShankWidthDim": 2},
    "StrapBoreProfile": {"StrapBoreDia": 3},
    "ForkProfile": {"ForkWidthDim": 2},
    "ForkBoss": {"ForkThick": 3},
    "ForkSlotProfile": {
        "TineNear": 3,
        "SlotWidth": 3,
        "ShankFaceNear": 2,
        "SlotDepth": 2,
        "ForkBossLength": 2,
    },
    "RingFaceReference": {"RingFaceNear": 3},
    "PinHoleProfile": {"PinHoleDia": 4},
    "ShankCorners": {"ShankCornerR": CORNER_PLACES},
}

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
