r"""Connecting-rod drawing prose -- the manufacturing notes the part build
stamps into the SLDPRT and the isometric-view label.

Split OUT of ``connecting_rod_spec`` (codex #354): assemblies import geometry
from the spec, so drawing-only prose living there made every notes edit
full-rebuild ``assembly:channel``.  This module is imported ONLY by
``build_connecting_rod`` (which stamps the properties) and the offline drawing
test -- never by an assembly -- so a notes edit rebuilds the part + drawing
and leaves the assembly to its cheap token refresh.
"""

from __future__ import annotations

# The strap-bore fit rides the Ø30.80 dimension callout (+0.10/0); the ring
# centre-to-pin distance is a BASIC sheet dimension.  Notes carry the occluded
# clevis construction that cannot be read reliably from the orthographic front
# view; no value duplicates a marked model dimension.
# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  build_connecting_rod marks exactly these. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingDiscProfile": {"RingOuterDia"},
    "StrapBoreProfile": {"StrapBoreDia"},
    "ShankProfile": {"ShankWidthDim"},
}

DRAWING_NOTES = "\n".join(
    (
        "1. STRAP BORE MACHINED; RUNS THE 30.60",
        "   CAM, 0.10 MIN CLR/SIDE.",
        "2. RING 3.00 THICK; SHANK 1.00 THICK",
        "   AND EXTENDS ONLY TO THE CLEVIS ROOT.",
        "3. RING WALL 4.50 MIN AFTER BORING.",
        "4. TWO D-SHAPED PRONGS, 8.00 W x 12.00 HIGH;",
        "   R4.00 CROWN, PIN C/L 6.00 ABOVE ROOT.",
        "5. PRONGS 1.00 THICK ABOUT A 2.90 SLOT;",
        "   OUTSIDE WIDTH 4.90, CENTRED AT LOCAL Z -4.05.",
        "6. U-BOTTOM WEB 2.00 HIGH; OVERLAP ROOT 0.50.",
        "7. OFFSET NECK OVERLAPS SHANK/NEAR PRONG 0.50;",
        "   PIN HOLE 1X THRU BOTH PRONGS; PIN IS A SEPARATE PART.",
        "8. FILLETS R1.0 MAX; NO DRAFT REQUIRED.",
        "9. GENERAL Ra 3.2: MACHINED ONLY; OTHERS AS CAST.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
