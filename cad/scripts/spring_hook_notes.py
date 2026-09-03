r"""Spring-hook drawing prose -- the manufacturing notes the part build stamps
into the SLDPRT, the isometric-view label, the elbow flag note, the elbow
angle's tolerance and the marked-dimension contract.

Split OUT of ``spring_hook_spec`` (codex #354, same treatment as
``connecting_rod_notes``): ``build_channel_assembly`` imports the hook's
geometry constants, so drawing prose living in that import closure made every
notes edit full-rebuild ``assembly:channel``.  Imported ONLY by
``build_spring_hook`` and the offline drawing test.  The elbow-angle
tolerance lives here for the same reason: it is a print fact, not geometry,
and a retune must not rebuild the channel assembly.
"""

from __future__ import annotations

from spring_hook_spec import ELBOW_R

# --- Marked-dimension contract.  The elbow angle is a DRIVEN reference
# dimension between the shank and arm path lines (build_spring_hook authors
# it); it carries the loose forming band below. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HookPath": {"Rise", "ArmRun", "ElbowAngle"},
    "WireProfile": {"RodDia"},
}

# The elbow: 90 degrees between the shank and the arm.  A short open wire
# hook does not need the title block's +/-1 degree (machinist review
# 2026-09-02: over-specification), so the model dimension carries a
# deliberately loose +/-5 degree band.
ELBOW_ANGLE_DEG = 90.0
ELBOW_ANGLE_TOLERANCE_DEG = 5.0

# Flagged from the elbow's outer silhouette in the front view: the stated
# radius is at the wire centreline (drawing-simplicity-policy.md rule 6:
# important process facts are flagged from the view, not buried in the
# block).
ELBOW_CALLOUT = f"R{ELBOW_R:.2f}\nWIRE C/L"

# Notes: process facts only (policy rule 6).  The rise, arm, wire diameter,
# elbow angle and the two overalls are sheet dimensions; the elbow radius is
# its flag note.
DRAWING_NOTES = "FORM COLD; NO KINKS AT THE ELBOW."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 5:1"
