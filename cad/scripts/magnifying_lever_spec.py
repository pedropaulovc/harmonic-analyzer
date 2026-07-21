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
# pick fails) and ONLY the auto-imported profile marks are dependable.  The far
# dome-centre station (from the left end) plus the dome radius fully define the
# Ø6 x 165 rod; the outside diameter and the overall length are carried in the
# note + the dome-radius callout (the note-based path the recipe pitfall
# endorses for un-pickable turned features). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"RightDomeCentre", "DomeRadius"},
}

# True free-text instructions only.  The un-pickable OD form/finish requirement
# and the overall length + stock diameter live here (nothing on the capsule is a
# selectable edge for a datum/FCF/Ra symbol).  The part build stamps these
# strings into the SLDPRT; the drawing displays only $PRPSHEET links, so the
# print cannot silently diverge from its source model.
DRAWING_NOTES = "\n".join(
    (
        "STOCK: Ø6 ROUND BRASS ROD, ONE PIECE; OVERALL LENGTH 165.",
        "FORM BOTH ENDS TO A FULL HEMISPHERE (R3 = ROD RADIUS).",
        "TURN OR CENTRELESS-GRIND THE OD STRAIGHT AND SMOOTH, Ra 1.6 -",
        "THE CLAMP BLOCK SLIDES ALONG IT TO SET THE MAGNIFICATION.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 4:1"
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
