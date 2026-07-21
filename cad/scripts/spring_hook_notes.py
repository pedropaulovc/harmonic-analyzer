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

DRAWING_NOTES = "\n".join(
    (
        "1. OPEN J-HOOK: SHANK, 90 DEG ELBOW",
        "   R1.50 CL, THEN A 2.50 ARM.",
        "2. SHANK SEATS IN THE SUMMING-LEVER",
        "   PLATE BORE; ARM CATCHES THE",
        "   CHANNEL-SPRING BOTTOM EYE.",
        "3. Ra SYMBOL APPLIES TO THE STRAIGHT",
        "   SHANK OD (PLATE SEAT).",
        "4. FORM COLD FROM ANNEALED WIRE;",
        "   NO SHARP KINKS AT THE ELBOW.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 5:1"
