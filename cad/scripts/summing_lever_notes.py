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
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateWidth", "PlateLength"},
    "CylinderProfile": {"CylDia"},
    "HexKnifeFrontProfile": {"HexKnifeFrontS1dy"},
    "SummationAnchorProfile": {"AnchorOuterDia", "AnchorBoreDia"},
}

# Numeric sizes and methods belong to native dimensions, feature callouts,
# controls, and the title block.  These four short part-specific facts define
# the two like trunnions, preserve the functional sharp ridge against the
# general edge-break instruction, and name the authority for organic contours.
DRAWING_NOTES = "\n".join(
    (
        "1. 2X KNIFE TRUNNIONS: SAME PROFILE.",
        "2. BILATERALLY SYMMETRIC ABOUT PIVOT X/Y AXES.",
        "3. KNIFE RIDGES SHARP; DO NOT BREAK.",
        "4. UNDIMENSIONED CONTOURS PER SUPPLIED 3D MODEL.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:3"
