r"""Summing-lever drawing prose -- the manufacturing notes the part build
stamps into the SLDPRT, the isometric-view label, and the marked-dimension
contract.

Split OUT of ``summing_lever_spec`` (codex #354, same treatment as
``connecting_rod_notes``): ``build_summing_assembly`` and ``build_knife_mount``
import the lever's geometry constants, so drawing prose living in that import
closure made every notes edit full-rebuild the summing assembly and knife
mount.  Imported ONLY by ``build_summing_lever`` and the offline drawing test.
"""

from __future__ import annotations

from summing_lever_spec import HOLE_X, PLATE_T, PLATE_W

# --- Marked-dimension contract.  build_summing_lever marks exactly these.
# The pivot diameter is NOT marked: every leader to the cylinder's circle in
# the front view crosses the edge-rib outline that wraps it, so the sheet
# dimensions the cylinder on its right view instead (silhouette to
# silhouette, diameter-prefixed). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateWidth", "PlateLength"},
    "SummationAnchorProfile": {"AnchorOuterDia"},
}

# The middle rib stops short of the coefficients plate's free edge so the
# spring-hole column stays clear (build_summing_lever.MID_RIB_PLATE_REACH =
# HOLE_X - 4.1; the offline test pins the two equal).
MID_RIB_REACH = HOLE_X - 4.1  # 35.75 from the pivot axis
MID_RIB_SHORT_OF_EDGE = PLATE_W - MID_RIB_REACH  # 8.70

# Notes: part-specific process facts only (drawing-simplicity-policy.md rule
# 6).  The spring-hole pattern, anchor bore, coefficients plate, pivot,
# trunnions and ribs are dimensioned natively on the sheet (top / right /
# detail views).  Two casting facts the views cannot carry legibly stay here:
# the summation arm's as-cast thickness (its faces are hidden in every
# orthographic view) and where the middle rib ends (its end edge sits
# between two spring holes).  Lines stay under ~38 characters: the block
# anchors at (0.020, 0.075) and shares its band with the top view's anchor.
DRAWING_NOTES = "\n".join(
    (
        "HEX VERTEX-UP RIDGE IS THE KNIFE EDGE.",
        f"SUMMATION ARM {PLATE_T:.2f} THICK AS CAST.",
        f"MID RIB ENDS {MID_RIB_SHORT_OF_EDGE:.2f} SHORT OF PLATE EDGE.",
        "AS CAST; MACHINE KNIFE EDGES + HOLES.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
