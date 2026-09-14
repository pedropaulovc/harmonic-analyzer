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

from summing_lever_spec import (
    ANCHOR_H,
    HEX_DEPTH,
    HEX_H,
    HEX_W,
    PLATE_L,
    PLATE_T,
)

# --- Marked-dimension contract.  build_summing_lever marks exactly these. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateWidth", "PlateLength"},
    "CylinderProfile": {"CylDia"},
    "SummationAnchorProfile": {"AnchorOuterDia"},
}

# The anchor-tap pattern (count, size, row X, start offset, spacing) and the
# counter-anchor tap size/location are dimensioned NATIVELY on the sheet (basic
# coordinates + position frames + Hole Wizard callouts); the notes must not
# repeat those numbers.  The boss HEIGHT is not a sketch dimension, so it is
# stated here -- it is the engagement the purchased counter anchor's shank is
# cut to.  Note 5 lists the machined features explicitly -- the sheet also
# carries the 20X controlled anchor-tap pattern, so "only knife edges and
# anchor bore" would contradict it (codex #354).  Notes 6-7 carry the no-nut
# rule: both lower spring anchors are purchased eyebolts that thread straight
# into this casting, so the casting is their nut and the eye clocking and
# threadlocker are the print's business, not an assembly aside.
DRAWING_NOTES = "\n".join(
    (
        f"1. HEX TRUNNIONS {HEX_W:.2f} W x {HEX_H:.2f} HIGH,",
        f"   {HEX_DEPTH:.2f} LONG EACH END; VERTEX UP",
        "   IS THE KNIFE EDGE.",
        f"2. COEFFICIENT PLATE {PLATE_T:.2f} THICK.",
        f"3. PIVOT {PLATE_L:.2f} LONG; NO BORE.",
        f"4. ANCHOR BOSS {ANCHOR_H:.2f} HIGH.",
        "5. CAST PART: UNDIMENSIONED CONTOURS",
        "   PER SUPPLIED MODEL/PATTERN.",
        "   MACHINE KNIFE EDGES AND TAP",
        "   SPRING ANCHOR SEATS ONLY.",
        "6. PURCHASED SPRING EYEBOLTS THREAD",
        "   DIRECTLY INTO THIS PART; NO NUTS.",
        "   TAP FULL DEPTH THROUGH PLATE",
        "   AND BOSS.",
        "7. CLOCK EACH EYE TO SPRING PULL",
        "   PLANE; SET WITH REMOVABLE",
        "   MEDIUM-STRENGTH THREADLOCKER.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
