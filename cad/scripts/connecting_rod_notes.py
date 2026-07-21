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
DRAWING_NOTES = "\n".join(
    (
        "1. STRAP BORE MACHINED; RUNS THE",
        "   30.60 ECCENTRIC CAM, 0.10 MIN CLR/SIDE.",
        "2. RING 3.00 THICK OVER ITS ANNULUS, STEP",
        "   AT THE RING OD; SHANK AND HEAD 2.50;",
        "   ALL CENTRED ON ONE MIDPLANE.",
        "3. RING WALL 5.00 NOM; 4.50 MIN AFTER",
        "   BORING.",
        "4. HEAD 10.00 W x 10.50 HIGH, R5.00 CROWN;",
        "   SHOULDERS RISE 1.20 WIDENING THE 8.00",
        "   SHANK. PIN C/L 2.40 BELOW CROWN.",
        "5. ROCKER PIN HOLE 1X.",
        "6. JUNCTION FILLETS R1.0 MAX, AS CAST OR",
        "   MACHINED; NO DRAFT REQUIRED.",
        "7. GENERAL Ra 3.2 APPLIES TO MACHINED",
        "   SURFACES; UNSPECIFIED SURFACES AS CAST.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
