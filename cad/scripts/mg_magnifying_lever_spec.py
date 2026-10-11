r"""Magnifying-lever dimensional contract -- the single source of truth shared by
the part build (``build_mg_magnifying_lever.py``) and its manufacturing drawing
(``draw_mg_magnifying_lever.py``).

PURE DATA, no SolidWorks/COM imports.  The turned-rod nominals live in the
drawing-FREE ``mg_magnifying_lever_geom`` module (the rod length and the
configured stations) and the config-free ``mg_lever_press_fit_geom`` (the press
zone the collar grips) so the assembly can import the knife-axis station without
pulling this drawing contract into its recipe closure; the two the drawing
places views by are re-exported here unchanged for the drawing-side consumers
and the offline lockstep test (``test_mg_magnifying_lever_drawing.py``), which
asserts the part marks and the drawing keeps EXACTLY ``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations

from mg_lever_press_fit_geom import PRESS_ZONE_LENGTH  # noqa: F401 (re-export)
from mg_magnifying_lever_geom import ROD_LENGTH  # noqa: F401 (re-export)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The rod is a REVOLVED capsule (hemispherical ends): a smooth
# tangent-continuous body with NO flat face, no end-face circle and no pickable
# silhouette edge, so coordinate picks are unreliable (verified: the dome-tip
# pick fails) and ONLY the auto-imported profile marks are dependable.  The far
# dome-centre station (from the left end) plus the dome radius fully define the
# Ø6 x 165 rod; the outside diameter and the overall length are carried in the
# note + the dome-radius callout (the note-based path the recipe pitfall
# endorses for un-pickable turned features).  The press zone -- the last
# PRESS_ZONE_LENGTH the bracket collar grips -- is a band on the same Ø6, so it
# lives on the blanked ``PressZone`` reference sketch: its length from the dome
# tip and its diameter carrying PRESS_ZONE_DIA_BAND natively (policy rule 2);
# the drawing shows that sketch in the front view (_drawing_hidden_sketches). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"RightDomeCentre", "DomeRadius"},
    "PressZone": {"PressZoneLen", "PressZoneDia"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RodProfile": {"RightDomeCentre": 2, "DomeRadius": 2},
    "PressZone": {"PressZoneLen": 2, "PressZoneDia": 3},
}
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != {
    name for names in DRAWING_PRECISION.values() for name in names
}:
    raise AssertionError("every marked lever dimension needs authored places")

# True free-text instructions only.  The un-pickable OD form/finish requirement
# and the overall length + stock diameter live here (nothing on the capsule is a
# selectable edge for a datum/FCF/Ra symbol); the press zone's size and band are
# the native PressZone dimensions, so note 4 says only how to hold them and what
# they mate (the press and its retention are the MHA-MG-001 bracket sheet's).  The
# part build stamps these strings into the SLDPRT; the drawing displays only
# $PRPSHEET links, so the print cannot silently diverge from its source model.
DRAWING_NOTES = "\n".join(
    (
        "Ø6 ROUND BAR, ONE PIECE; OVERALL LENGTH (165) REF.",
        "FORM BOTH ENDS TO A FULL HEMISPHERE (R3 = ROD RADIUS).",
        "OD STRAIGHT AND SMOOTH, Ra 1.6: THE CLAMP BLOCK SLIDES ALONG IT.",
        "PRESS ZONE: SELECT OR LAP STOCK TO THE SIZE SHOWN;"
        " PRESSED INTO THE MHA-MG-001 COLLAR.",
    )
)
