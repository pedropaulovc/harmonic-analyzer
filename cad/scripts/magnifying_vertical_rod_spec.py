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
# dependable.  The far dome-centre station (from the left end) plus the dome
# radius fully define the Ø5 x 150 rod; the outside diameter and the overall
# length ride the dome-radius callout + the note.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"RightDomeCentre", "DomeRadius"},
}

DRAWING_NOTES = "\n".join(
    (
        "Ø5 ROUND BAR, ONE PIECE; OVERALL LENGTH (150) REF.",
        "FORM BOTH ENDS TO A FULL HEMISPHERE (R2.5 = ROD RADIUS).",
        "OD STRAIGHT AND SMOOTH, Ra 1.6.",
        "THE CLAMP BLOCK AND OUTPUT FIXTURE SLIDE ALONG IT.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 4:1"
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
