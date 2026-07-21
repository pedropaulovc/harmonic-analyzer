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

from summing_lever_spec import HEX_DEPTH, HEX_H, HEX_W, PLATE_L, PLATE_T

# --- Marked-dimension contract.  build_summing_lever marks exactly these. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateWidth", "PlateLength"},
    "CylinderProfile": {"CylDia"},
    "SummationAnchorProfile": {"AnchorOuterDia"},
}

# The spring-hole pattern (count, size, row X, start offset, pitch) and the
# anchor-eye size/location are dimensioned NATIVELY on the sheet (basic
# coordinates + position frames); the notes must not repeat those numbers.
# Note 4 lists the machined features explicitly -- the sheet also carries the
# 20X controlled spring-hole pattern, so "only knife edges and anchor bore"
# would contradict it (codex #354).
DRAWING_NOTES = "\n".join(
    (
        f"1. HEX TRUNNIONS {HEX_W:.2f} W x {HEX_H:.2f} HIGH,",
        f"   {HEX_DEPTH:.2f} LONG EACH END; VERTEX UP IS",
        "   THE KNIFE EDGE.",
        f"2. COEFFICIENT PLATE {PLATE_T:.2f} THICK.",
        f"3. PIVOT CYLINDER {PLATE_L:.2f} LONG; NO BORE.",
        "4. CAST PART: UNDIMENSIONED CONTOURS",
        "   PER SUPPLIED MODEL/PATTERN. MACHINE",
        "   THE KNIFE EDGES, SPRING HOLES,",
        "   AND ANCHOR BORE ONLY.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
