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

# Every size, location and band prints from its native model dimension, and
# each tight band names its mate at its own callout or through a flag note
# that callout links (drawing-guidelines.md rules 4 and 7). The tines' known
# shortfall against the .080 wall target is the near tine's own printed lower
# limit, named TINE WALL on its callout (rule 20). The material (1018 plate),
# the black finish and the inside corners' R.040 MAX are title-block rows,
# never restated here (rule 2).
#
# Note 1 is the reamed pin hole's matched press fit, linked from its
# callout: its .0004 band is narrower than the shop's reamer row, so the hole
# is reamed to its pin. The acceptance is the ANSI FN2 window the pin budget
# is held to (ch_rod_pivot_pin_spec.PRESS_INTERFERENCE_MAX), rounded inward.
# Pending owner confirmation (fan-out Q1, delegated ruling 2026-11-07, #2144).
#
# Notes 2 and 3 each name one mate for two tight bands that serve it (fan-out
# rounds 1-2: named at both callouts it printed twice, named at one the other
# band had none): the fork slot's width and the tine walls that locate it run
# on the arm; the ring and shank's thickness and its offset that centres it
# on the fork slide in the cam's slot.
PIN_NAME = "ROD PIVOT PIN"
PIN_NUMBER = "MHA-CH-10"
ARM_NUMBER = "MHA-CH-06"
CAM_NUMBER = "MHA-DT-12"
PIN_FIT_NOTE_NUMBER = 1
SLOT_FIT_NOTE_NUMBER = 2
CAM_SLOT_NOTE_NUMBER = 3
PIN_FIT_INTERFERENCE = (".0002", ".0008")
DRAWING_NOTES = "\n".join(
    (
        f"{PIN_FIT_NOTE_NUMBER}. MATCHED PRESS FIT ON {PIN_NAME} {PIN_NUMBER}:",
        f"    REAM {PIN_FIT_INTERFERENCE[0]}-{PIN_FIT_INTERFERENCE[1]}"
        " UNDER THE MEASURED PIN.",
        f"{SLOT_FIT_NOTE_NUMBER}. FORK SLOT: RUNNING FIT ON ARM {ARM_NUMBER}.",
        f"{CAM_SLOT_NOTE_NUMBER}. RING AND SHANK: SLIDING FIT IN {CAM_NUMBER} CAM SLOT.",
    )
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  build_ch_connecting_rod marks exactly these. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"RingOuterDia", "ShankWidthDim"},
    "Plate": {"RingThick"},
    "StrapBoreProfile": {"StrapBoreDia"},
    "ForkProfile": {"ForkWidthDim"},
    "ForkBoss": {"ForkThick"},
    "ForkSlotProfile": {
        "TineNear",
        "SlotWidth",
        "RingFaceNear",
        "SlotDepth",
        "ForkBossLength",
    },
    "PinHoleProfile": {"PinHoleDia"},
}

# Decimal-inch places (#290): the tines, slot, the plate's near face and its
# thickness hold the inter-arm gap and the ring's float in its cam slot, so
# they print at three places with their +/-.002 bands; the fork over the tines
# is their reference sum at the same places. The strap bore prints 1.213 at
# three with its +.004/.000; the reamed press hole at four. The ring OD, shank
# width, fork width, slot depth and boss length take the title block's .XX.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateProfile": {"RingOuterDia": 2, "ShankWidthDim": 2},
    "Plate": {"RingThick": 3},
    "StrapBoreProfile": {"StrapBoreDia": 3},
    "ForkProfile": {"ForkWidthDim": 2},
    "ForkBoss": {"ForkThick": 3},
    "ForkSlotProfile": {
        "TineNear": 3,
        "SlotWidth": 3,
        "RingFaceNear": 3,
        "SlotDepth": 2,
        "ForkBossLength": 2,
    },
    "PinHoleProfile": {"PinHoleDia": 4},
}

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
