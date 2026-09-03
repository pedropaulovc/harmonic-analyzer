r"""Rocker-arm drawing prose -- the manufacturing notes the part build stamps
into the SLDPRT and the isometric-view label.

Split OUT of ``rocker_arm_spec`` (codex #354, same treatment as
``connecting_rod_notes``): ``build_channel_assembly`` imports the rocker's
geometry, so drawing prose living in that import closure made every notes edit
full-rebuild ``assembly:channel``.  Imported ONLY by ``build_rocker_arm`` and
the offline drawing test.
"""

from __future__ import annotations

from rocker_arm_spec import (
    CENTER_Y,
    PIVOT_MID_Y,
    R_BOTTOM,
    R_TOP,
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  build_rocker_arm marks exactly these.  The two large radii are
# note-only (an imported R800 keeps an off-sheet centre witness); the arc
# ENDPOINTS (each arc's end x from the pivot) and the radial tip face are
# graphical, so the ends are dimensioned on the view (machinist review
# 2026-09-02: the end lands were only in prose and read as impossible). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StrapProfile": {
        "TopRadius",
        "BottomRadius",
        "TopRodX",
        "BottomRodX",
        "RodTipLen",
    },
    "PivotHoleProfile": {"PivotDia"},
}

# Notes: part-specific facts the views cannot carry (drawing-simplicity-
# policy.md rule 6).  The two large concentric radii are NOTE-ONLY marked
# dimensions, so their values and common centre live here -- the centre is
# fixed by the vertical centreline through the pivot bore (the seesaw's mirror
# line) and its height above the pivot axis.  The arc ends, the tip face and
# the overall length are view dimensions; the pivot bore's REAM and Ra ride
# the dimension and its roughness symbol, the pin drill its callout.
DRAWING_NOTES = "\n".join(
    (
        f"TOP EDGE R{R_TOP:.2f} / BOTTOM EDGE R{R_BOTTOM:.2f}, CONCENTRIC;",
        "CENTRE ON THE VERTICAL C/L THROUGH THE PIVOT BORE,",
        f"{CENTER_Y - PIVOT_MID_Y:.2f} ABOVE THE PIVOT AXIS. ENDS SYMMETRIC ABOUT THAT C/L.",
        "ROD-PIN HOLE AT THE END SHOWN ONLY.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
