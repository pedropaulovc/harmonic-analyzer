r"""Rocker-arm drawing prose -- the manufacturing notes the part build stamps
into the SLDPRT and the isometric-view label.

Split OUT of ``rocker_arm_spec`` (codex #354, same treatment as
``connecting_rod_notes``): ``build_channel_assembly`` imports the rocker's
geometry, so drawing prose living in that import closure made every notes edit
full-rebuild ``assembly:channel``.  Imported ONLY by ``build_rocker_arm`` and
the offline drawing test.
"""

from __future__ import annotations

# True free-text instructions only; geometry / datum structure / roughness live
# in native dimensions / datum tags / FCFs / surface symbols.  Hole sizes ride
# their native callouts (Ø6.50 dim, Ø1.99 THRU ALL) -- the notes state process,
# fit and count, never a second copy of a sheet dimension.  16.00 depth is a
# REF: it is fixed by the concentric R800/R816 edges.
# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  build_rocker_arm marks exactly these. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StrapProfile": {"TopRadius", "BottomRadius"},
    "PivotHoleProfile": {"PivotDia"},
}

DRAWING_NOTES = "\n".join(
    (
        "1. PROFILE MIRROR-SYMMETRIC ABOUT THE",
        "   PIVOT-BORE AXIS; ROD-PIN HOLE AT ONE",
        "   END ONLY (1X), THE END SHOWN.",
        "2. STRAP 2.50 THICK; ALL HOLES THRU",
        "   THE THICKNESS.",
        "3. TOP EDGE R800.00, BOTTOM EDGE R816.00,",
        "   CONCENTRIC; COMMON CENTRE ON THE",
        "   MIRROR AXIS, 808.00 FROM THE PIVOT",
        "   AXIS (STRAP DEPTH 16.00 REF).",
        "4. ARC LENGTHS 292.10 TOP / 266.70 BOTTOM",
        "   TAPER THE ENDS.",
        "5. EACH TIP: 5.59 FACE PERP TO TOP EDGE.",
        "6. PIVOT HOLE: REAM +0.03/0, Ra 1.6.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
