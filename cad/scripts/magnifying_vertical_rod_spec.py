r"""Magnifying vertical-rod dimensional contract -- the single source of truth
shared by the part build (``build_magnifying_vertical_rod.py``) and its
manufacturing drawing (``draw_magnifying_vertical_rod.py``).

PURE DATA, no SolidWorks/COM imports.  Nothing else consumes this rod's
nominals (unlike the magnifying LEVER rod, whose knife-axis station an assembly
imports and so needs a ``_geom`` split), so one ``_spec`` module is right here.
The offline lockstep test asserts the part marks and the drawing keeps EXACTLY
``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations

# --- rod nominals (DIMENSIONS.md ch20; ~half the Ø6 lever rod, low) -----------
ROD_LENGTH = 150.0
ROD_DIA = 5.0

# The rod is a REVOLVED capsule (hemispherical ends): a smooth tangent-continuous
# body with NO flat face, no end-face circle and no pickable silhouette edge, so
# coordinate picks are unreliable and ONLY the auto-imported profile marks are
# dependable.  The profile's axis line runs tip to tip, so its length dim IS the
# overall length (the controlling dimension, shown conventionally between the
# two tips); with the dome radius it fully defines the Ø5 x 150 rod.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"RodOverall", "DomeRadius"},
}

# Notes: the stock licence only (policy rule 6) -- the overall rides the axis
# dimension, the dome the radius callout.  No roughness: the rod is lock-mated
# in the clamp block and the output fixture in service (magnifier assembly), so
# nothing runs on it and the block Ra covers the OD (rule 5).
DRAWING_NOTES = f"Ø{ROD_DIA:.1f} ROUND BAR STOCK; OD OK AS RECEIVED."
END_VIEW_NOTE = "END VIEW SCALE 4:1"
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
