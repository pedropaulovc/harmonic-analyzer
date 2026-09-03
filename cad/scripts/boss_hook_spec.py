r"""Pure-data dimensional contract shared by the summing-lever boss hook and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_boss_hook`` imports the marked-
dimension NAME map + notes from here; ``draw_boss_hook`` imports the hook's wire
geometry from ``boss_hook_geom`` / ``build_boss_hook`` for its view math and
keeps exactly ``DRAWING_DIMENSIONS`` across its per-view keep maps.
"""

from __future__ import annotations

from boss_hook_geom import ELBOW_R


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The J-hook is a single swept wire; its whole shape is three
# numbers -- the wire diameter (WireProfile), the straight rise and the arm run
# (HookPath).  The elbow radius is a sketch relation (the merged rise joint sets
# r = ElbowR), so it rides the bend callout rather than a duplicate-named
# imported dim. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "WireProfile": {"RodDia"},
    "HookPath": {"Rise", "ArmRun"},
}

# Bend callout, leadered onto the elbow's outer arc (machinist review
# 2026-09-02: the radius and the crack check were buried in a remote note).
# One decimal so the title block's .X tolerance governs the radius.
BEND_NOTE = "\n".join(
    (
        f"R{ELBOW_R:.1f} AT THE WIRE CENTRELINE",
        "NO CRACKS AT THE BEND",
    )
)

# Notes: part-specific process facts only, never a tolerance, never a
# dimension, never the title block (drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = "LENGTHS ALONG THE WIRE CENTRELINE TO THE TANGENT POINTS."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
