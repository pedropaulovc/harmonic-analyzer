r"""Spring-hook drawing prose -- the manufacturing notes the part build stamps
into the SLDPRT, the isometric-view label, and the marked-dimension contract.

Split OUT of ``spring_hook_spec`` (codex #354, same treatment as
``connecting_rod_notes``): ``build_channel_assembly`` imports the hook's
geometry constants, so drawing prose living in that import closure made every
notes edit full-rebuild ``assembly:channel``.  Imported ONLY by
``build_spring_hook`` and the offline drawing test.
"""

from __future__ import annotations

# --- Marked-dimension contract. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HookPath": {"Rise", "ArmRun"},
    "WireProfile": {"RodDia"},
}

# Notes: process facts only (drawing-simplicity-policy.md rule 6).  The rise,
# arm and wire diameter are sheet dimensions; the elbow radius is not.
DRAWING_NOTES = "\n".join(
    (
        "OPEN J-HOOK: 90 DEG ELBOW, R1.50 ON THE WIRE CENTRELINE.",
        "FORM COLD; NO KINKS AT THE ELBOW.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 5:1"
