r"""Connecting-rod drawing prose -- the manufacturing notes the part build
stamps into the SLDPRT and the isometric-view label.

Split OUT of ``ch_connecting_rod_spec`` (codex #354): assemblies import
geometry from the spec, so drawing-only prose living there made every notes
edit full-rebuild ``assembly:ch_channel``.  This module is imported ONLY by
``build_ch_connecting_rod`` (which stamps the properties), the drawing and the
offline drawing test -- never by an assembly -- so a notes edit rebuilds the
part + drawing and leaves the assembly to its cheap token refresh.
"""

from __future__ import annotations

from ch_connecting_rod_spec import TINE_MIN

# Every size, location and band prints from its native model dimension, and
# each tight band names its mate on its own callout (drawing-guidelines.md
# rules 4 and 7), so the one note states the tines' known shortfall against
# the 2.0 wall target as a plain fact (rule 20).  The material (1018 plate)
# and the black finish are title-block rows, never restated here (rule 2).
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
    "InsideCorners": {"InsideCornerR"},
    "PinHoleProfile": {"PinHoleDia"},
}

# The tines, slot, the plate's near face and its thickness hold the inter-arm
# gap and the ring's float in its cam slot: three places, as their model
# bands are written. The fork over the tines is their reference sum, at the
# same places. The reamed press hole's band is written at three places too;
# the inside corners' single-limit radius at one.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "Plate": {"RingThick": 3},
    "ForkBoss": {"ForkThick": 3},
    "ForkSlotProfile": {
        "TineNear": 3,
        "SlotWidth": 3,
        "RingFaceNear": 3,
    },
    "InsideCorners": {"InsideCornerR": 1},
    "PinHoleProfile": {"PinHoleDia": 3},
}

DRAWING_NOTES = f"1. TINE WALL {TINE_MIN:.2f} MIN."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
