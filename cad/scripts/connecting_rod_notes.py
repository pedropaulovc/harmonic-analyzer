r"""Connecting-rod drawing prose -- the manufacturing notes the part build
stamps into the SLDPRT, the isometric-view label and the head's flag note.

Split OUT of ``connecting_rod_spec`` (codex #354): assemblies import geometry
from the spec, so drawing-only prose living there made every notes edit
full-rebuild ``assembly:channel``.  This module is imported ONLY by
``build_connecting_rod`` (which stamps the properties), the drawing recipe and
the offline drawing test -- never by an assembly -- so a notes edit rebuilds
the part + drawing and leaves the assembly to its cheap token refresh.
"""

from __future__ import annotations

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  build_connecting_rod marks exactly these. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingDiscProfile": {"RingOuterDia"},
    "StrapBoreProfile": {"StrapBoreDia"},
    "ShankProfile": {"ShankWidthDim"},
}

# Notes: part-specific process facts only (drawing-simplicity-policy.md rule
# 6).  The strap-bore fit rides the model dimension, the pin drill its
# callout, the centre distance a sheet dimension; the as-cast head, the ring
# and the stepped thickness are dimensioned in their details (machinist
# review 2026-09-02: "per pattern" delegated the casting to a drawing that
# does not exist).  What no view can say: the three bodies share one
# midplane, and the wall that must survive boring.
DRAWING_NOTES = "\n".join(
    (
        "RING, SHANK AND HEAD SHARE ONE MIDPLANE.",
        "RING WALL 4.50 MIN AFTER BORING.",
    )
)
# Flagged from the crown arc in the head detail: the crown is a full round
# on the head width, so the width dimension sizes it.
CROWN_CALLOUT = "FULL R"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
