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
# centre-to-pin distance is a BASIC sheet dimension.  Notes carry only what the
# sheet does not dimension natively, so no number appears in both places.
# Kept to 10 display lines: the notes share the left column with the 170 mm
# stepped-thickness view (outline ~180 mm tall), and the column between the
# bottom border and the top zone border is ~186 mm -- a taller block either
# overlaps the view or pushes it across the border (layout audit).
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
        "2. RING 3.00 THICK, STEP AT THE RING OD;",
        "   SHANK AND HEAD 2.50; ONE MIDPLANE.",
        "3. RING WALL 4.50 MIN AFTER BORING.",
        "4. HEAD 10.00 W x 10.50 HIGH, R5.00 CROWN;",
        "   SHOULDERS RISE 1.20 OFF THE 8.00 SHANK.",
        "5. PIN C/L 2.40 BELOW CROWN; PIN HOLE 1X.",
        "6. FILLETS R1.0 MAX; NO DRAFT REQUIRED.",
        "7. GENERAL Ra 3.2: MACHINED ONLY; OTHERS AS CAST.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
