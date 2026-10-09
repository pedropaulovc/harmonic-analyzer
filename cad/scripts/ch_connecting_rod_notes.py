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

from ch_connecting_rod_spec import (
    RING_SLOT_SYMMETRY,
    RING_THICKNESS,
    SHANK_THICKNESS,
)

# The strap-bore fit rides the Ø30.80 dimension callout (+0.10/0); the ring
# centre-to-pin distance is a BASIC sheet dimension; the fork thickness and
# slot carry their 3-place model bands; the reamed pin hole prints its size
# and band from the PinHoleDia model dimension at three places (policy rules
# 2 and 6, PR #1292 review N1), so note 5 names only the press and its pin.
# Notes carry only what the sheet does not dimension natively, so no number
# appears in both places.  The
# material (1018 plate) and the black finish are title-block rows, never
# restated here (simplicity policy rule 1).  Lines stay within 40 characters:
# the block sits in the column between the front view's pin annotations and
# the isometric view.
# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  build_ch_connecting_rod marks exactly these. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingDiscProfile": {"RingOuterDia"},
    "StrapBoreProfile": {"StrapBoreDia"},
    "ShankProfile": {"ShankWidthDim"},
    "ForkProfile": {"ForkWidthDim"},
    "ForkBoss": {"ForkThick"},
    "ForkSlotProfile": {"SlotWidth", "SlotDepth", "ForkBossLength"},
    "PinHoleProfile": {"PinHoleDia"},
}

# The fork's outer thickness and slot hold the inter-arm gap (each gap holds
# one tine of each neighbouring rod): three places, as their bands are written.
# The reamed press hole's band is written at three places too.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ForkBoss": {"ForkThick": 3},
    "ForkSlotProfile": {"SlotWidth": 3},
    "PinHoleProfile": {"PinHoleDia": 3},
}

# The pin pressed into the reamed fork pin hole (test_ch_connecting_rod_drawing
# pins it to the part registry).
PIN_NUMBER = "MHA-CH-010"
# Note 2 prints the one plate thickness ring to shank, at the title block's
# three places (#948 ruling R, PR #1292).
if SHANK_THICKNESS != RING_THICKNESS:
    raise AssertionError("note 2 states one thickness for the ring and the shank")

DRAWING_NOTES = "\n".join(
    (
        "1. STRAP BORE MACHINED; RUNS THE 30.60",
        "   CAM, 0.10 MIN CLR/SIDE.",
        f"2. RING AND SHANK {RING_THICKNESS:.3f} THICK;",
        f"   SYMMETRIC TO SLOT WITHIN {RING_SLOT_SYMMETRY:.2f}.",
        "3. RING WALL 4.50 MIN AFTER BORING.",
        "4. SLOT CENTRED; TINES EQUAL WITHIN 0.10",
        f"5. PRESS FIT PIN {PIN_NUMBER} INTO THE",
        "   REAMED PIN HOLE, BOTH TINES.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
