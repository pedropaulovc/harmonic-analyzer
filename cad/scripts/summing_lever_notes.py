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

# --- Marked-dimension contract.  build_summing_lever marks exactly these. ---
# The body length, trunnions, hex, thicknesses and hole pattern are dimensioned
# natively on the sheet between picked model edges (draw_summing_lever), so
# only the three sketch-owned sizes ride the model-dimension import.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateWidth"},
    "CylinderProfile": {"CylDia"},
    "SummationAnchorProfile": {"AnchorOuterDia"},
}

# Two process facts a machinist cannot read off the views
# (cad/docs/drawing-simplicity-policy.md rule 6): the summation arm and rib
# curves are cast/pattern contours the print does not dimension, and the
# knife edges are the one exception to the title block's edge break.
DRAWING_NOTES = "\n".join(
    (
        "1. UNDIMENSIONED CONTOURS PER SUPPLIED MODEL.",
        "2. KNIFE EDGES SHARP; DO NOT BREAK.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:5"
