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

# The strap-bore fit rides the Ø30.80 dimension callout (+0.10/0); the ring
# centre-to-pin distance is a BASIC sheet dimension; the fork thickness and
# slot carry their 3-place model bands; the pin hole's countersink Ø imports
# from its reference sketch with its band.  Notes carry only what the sheet
# does not dimension natively, so no number appears in both places.  The
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
    "CountersinkReference": {"PinCskDia"},
}

# The fork's outer thickness and slot hold the inter-arm gap (each gap holds
# one tine of each neighbouring rod): three places, as their bands are written.
# The countersink Ø is the peened pin's fill volume, hence three places too.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ForkBoss": {"ForkThick": 3},
    "ForkSlotProfile": {"SlotWidth": 3},
    "CountersinkReference": {"PinCskDia": 3},
}

DRAWING_NOTES = "\n".join(
    (
        "1. STRAP BORE MACHINED; RUNS THE 30.60",
        "   CAM, 0.10 MIN CLR/SIDE.",
        "2. RING 3.00, SHANK 2.50 THICK; RING,",
        "   SHANK AND FORK ON ONE MIDPLANE.",
        "3. RING WALL 4.50 MIN AFTER BORING.",
        "4. SLOT CENTRED; TINES EQUAL WITHIN 0.10",
        "5. PEEN PIN MHA-CH-010 INTO BOTH CSKS",
        "   AT ASSY: RECONSTRUCTION CHOICE #746.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"

# Descriptive text beneath the imported countersink Ø: the chamfer is
# equal-legged, so its included angle is 90 degrees; one feature sinks both
# tine faces.
PIN_CSK_CALLOUT = "90\u00b0 CSK BOTH SIDES"
