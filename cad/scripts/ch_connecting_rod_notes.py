r"""Connecting-rod drawing-only data -- the marked-dimension and precision
contract and the isometric-view label the part build stamps into the SLDPRT.

Split OUT of ``ch_connecting_rod_spec`` (codex #354): assemblies import
geometry from the spec, so drawing-only prose living there made every notes
edit full-rebuild ``assembly:ch_channel``.  This module is imported ONLY by
``build_ch_connecting_rod`` (which stamps the properties), the drawing and the
offline drawing test -- never by an assembly -- so a notes edit rebuilds the
part + drawing and leaves the assembly to its cheap token refresh.
"""

from __future__ import annotations

# Every size, location and band prints from its native model dimension, and
# each tight band names its mate on its own callout (drawing-guidelines.md
# rules 4 and 7). The tines' known shortfall against the .080 wall target is
# the near tine's own printed lower limit, named TINE WALL on its callout
# (rule 20), so the sheet carries no general note. The material (1018 plate),
# the black finish and the inside corners' R.040 MAX are title-block rows,
# never restated here (rule 2).
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
