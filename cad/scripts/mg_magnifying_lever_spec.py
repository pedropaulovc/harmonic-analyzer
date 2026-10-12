r"""Magnifying-lever dimensional contract -- the single source of truth shared by
the part build (``build_mg_magnifying_lever.py``) and its manufacturing drawing
(``draw_mg_magnifying_lever.py``).

PURE DATA, no SolidWorks/COM imports.  The turned-rod nominals live in the
drawing-FREE ``mg_magnifying_lever_geom`` module (the rod length and the
configured stations) and the config-free ``mg_lever_press_fit_geom`` (the press
zone the collar grips, the bore it enters, the fit budget) so the assembly can
import the knife-axis station without pulling this drawing contract into its
recipe closure; the two the drawing places views by are re-exported here
unchanged for the drawing-side consumers and the offline lockstep test
(``test_mg_magnifying_lever_drawing.py``), which asserts the part marks and the
drawing keeps EXACTLY ``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations

from mg_lever_press_fit_geom import (
    COLLAR_BORE_BAND,
    COLLAR_BORE_DIA,
    PRESS_FIT_BUDGET,
    PRESS_FORCE_MAX_KN,
    PRESS_ZONE_LENGTH,  # noqa: F401 (re-export)
    ROD_DIA,
)
from mg_magnifying_lever_geom import ROD_LENGTH  # noqa: F401 (re-export)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The rod is a REVOLVED capsule (hemispherical ends): a smooth
# tangent-continuous body with NO flat face, no end-face circle and no pickable
# silhouette edge, so coordinate picks are unreliable (verified: the dome-tip
# pick fails) and ONLY the auto-imported profile marks are dependable.  The far
# dome-centre station (from the left end) plus the dome radius fully define the
# Ø6 x 165 rod; the overall length is carried in the note (the note-based path
# the recipe pitfall endorses for un-pickable turned features).  The stock
# diameter prints once from the blanked ``RodStock`` reference sketch (the
# profile cannot carry a second diameter: its top line's height IS the dome
# radius).  The press zone -- the STRAIGHT rod the bracket collar grips, from
# its inner face to the dome tangent -- is a band on the same Ø6, so it lives on
# the blanked ``PressZone`` reference sketch: its length and its diameter
# carrying PRESS_ZONE_DIA_BAND natively (policy rule 2); the drawing shows both
# sketches in the front view (_drawing_hidden_sketches). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"RightDomeCentre", "DomeRadius"},
    "RodStock": {"RodDia"},
    "PressZone": {"PressZoneLen", "PressZoneDia"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RodProfile": {"RightDomeCentre": 2, "DomeRadius": 2},
    "RodStock": {"RodDia": 2},
    "PressZone": {"PressZoneLen": 2, "PressZoneDia": 3},
}
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != {
    name for names in DRAWING_PRECISION.values() for name in names
}:
    raise AssertionError("every marked lever dimension needs authored places")


def _deviation(value: float) -> str:
    """One printed deviation of the mating bore: a bare 0, else signed to the
    bore's three places."""
    return "0" if value == 0.0 else f"{value:+.3f}"


# Dimension callouts that state a manufacturing fact (the mate, its band, the
# interference) are derived here from the fit contract -- never typed on the
# sheet (_drawing_contract's spec-string rule).  <MOD-DIAM> is SolidWorks' own
# Ø token; it carries its own leading gap, so no space before it.
PRESS_ZONE_DIA_CALLOUT = (
    f"IN MHA-MG-001<MOD-DIAM>{COLLAR_BORE_DIA:.3f} "
    f"{_deviation(COLLAR_BORE_BAND[0])}/{_deviation(COLLAR_BORE_BAND[1])} BORE: "
    f"{PRESS_FIT_BUDGET['interference_min']:.3f}-"
    f"{PRESS_FIT_BUDGET['interference_max']:.3f} INTERFERENCE"
)

# True free-text instructions only.  The un-pickable OD form/finish requirement
# and the overall length + stock description live here (nothing on the capsule
# is a selectable edge for a datum/FCF/Ra symbol); the stock diameter, the dome
# radius and the press zone's size and band are native dimensions. The last
# 10 mm from the un-pickable dome tip is reference information, like the
# overall length; both notes derive from the geometry owner. Instructions say
# how to hold and press the rod (retention is the MHA-MG-001 bracket sheet's).
# The force is the fit budget's worst case, never typed. The part stamps these
# strings into the SLDPRT; the drawing displays only $PRPSHEET links.
DRAWING_NOTES = "\n".join(
    (
        f"Ø{ROD_DIA:g} ROUND BAR, ONE PIECE; OVERALL LENGTH ({ROD_LENGTH:g}) REF.",
        "OD STRAIGHT AND SMOOTH, Ra 1.6: THE CLAMP BLOCK SLIDES ALONG IT.",
        f"PRESS ZONE START ({PRESS_ZONE_LENGTH:g}) FROM TIP REF; SELECT OR LAP.",
        f"PRESS MHA-MG-001 COLLAR ONTO ROD HELD NEAR ITS END; {PRESS_FORCE_MAX_KN:.1f} kN MAX AT TIGHT FIT.",
    )
)

# The detail/end and isometric projections use scales different from the sheet.
END_VIEW_NOTE = "END VIEW SCALE 4:1"
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
