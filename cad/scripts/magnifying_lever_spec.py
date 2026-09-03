r"""Magnifying-lever dimensional contract -- the single source of truth shared by
the part build (``build_magnifying_lever.py``) and its manufacturing drawing
(``draw_magnifying_lever.py``).

PURE DATA, no SolidWorks/COM imports.  The turned-rod nominals live in the
drawing-FREE ``magnifying_lever_geom`` module so the assembly can import the
knife-axis station without pulling this drawing contract into its recipe
closure; they are re-exported here unchanged for the drawing-side consumers and
the offline lockstep test (``test_magnifying_lever_drawing.py``), which asserts
the part marks and the drawing keeps EXACTLY ``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations

from magnifying_lever_geom import ROD_DIA, ROD_LENGTH  # noqa: F401 (re-export)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The rod is a REVOLVED capsule (hemispherical ends): a smooth
# tangent-continuous body with NO flat face, no end-face circle and no pickable
# silhouette edge, so coordinate picks are unreliable (verified: the dome-tip
# pick fails) and ONLY the auto-imported profile marks are dependable.  The
# profile's axis line runs tip to tip, so its length dim IS the overall length
# (the controlling dimension, shown conventionally between the two tips); with
# the dome radius it fully defines the Ø6 x 165 rod. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"RodOverall", "DomeRadius"},
}

# Notes: the stock licence only (policy rule 6) -- the overall rides the axis
# dimension, the dome the radius callout.  No roughness: the clamp block and
# the bracket collar only slide along the rod when the magnification is set
# and are thumb-screwed / locked to it in service, so the block Ra covers the
# OD (rule 5).
DRAWING_NOTES = f"Ø{ROD_DIA:.1f} ROUND BAR STOCK; OD OK AS RECEIVED."
END_VIEW_NOTE = "END VIEW SCALE 4:1"
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
