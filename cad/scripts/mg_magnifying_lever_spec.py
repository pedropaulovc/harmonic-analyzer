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

from _gtol_cylinder import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from mg_lever_press_fit_geom import (
    COLLAR_BORE_DIA,
    PRESS_FIT_BUDGET,
    PRESS_FORCE_MAX_KN,
    PRESS_ZONE_DIA_BAND,
    PRESS_ZONE_LENGTH,  # noqa: F401 (re-export)
    ROD_DIA,
)
from mg_magnifying_lever_geom import ROD_LENGTH  # noqa: F401 (re-export)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The rod is a REVOLVED capsule (hemispherical ends): a smooth
# tangent-continuous body with NO flat face and no end-face circle, so ONLY
# the auto-imported profile marks locate its ends.  The profile carries the
# overall length between the two dome TIPS (what a caliper picks up -- the far
# dome centre it replaced could not be measured) and the dome radius, a
# REFERENCE: each dome is a full hemisphere tangent to the bar, so its radius
# is half the selected press-zone diameter.  The stock diameter prints once
# from the blanked ``RodStock`` reference sketch (the profile cannot carry a
# second diameter: its top line's height IS the dome radius) with the
# cold-drawn bar's own band.  The press zone -- the cylinder the bracket collar
# grips, from PRESS_ZONE_LENGTH before the east tip to the dome tangent -- is a
# tighter band on the same unstepped Ø6, so it lives on the blanked
# ``PressZone`` reference sketch: its start from the tip carrying
# PRESS_ZONE_LENGTH_BAND, its cylinder length to the tangent (a REFERENCE:
# start minus the dome radius), and its diameter carrying PRESS_ZONE_DIA_BAND,
# both bands native (drawing-guidelines.md rule 3 (decimal places carry the tolerance)); the drawing shows both sketches in the
# front view (_drawing_hidden_sketches). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"OverallLength", "DomeRadius"},
    "RodStock": {"RodDia"},
    "PressZone": {"PressZoneStart", "PressZoneLen", "PressZoneDia"},
}
# The tip-to-tip length is checked at .X (+/-0.8): the rod's west end only
# bounds the clamp's travel.  The zone's start carries its axial band at .XX,
# matched to the collar's length band, so the selected zone covers the
# collar's true contact (the collar length less the dome radius).  The stock
# and zone diameters carry their bands at their own places; the two
# references read at .X.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RodProfile": {"OverallLength": 1, "DomeRadius": 1},
    "RodStock": {"RodDia": 2},
    "PressZone": {"PressZoneStart": 2, "PressZoneLen": 1, "PressZoneDia": 3},
}
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != {
    name for names in DRAWING_PRECISION.values() for name in names
}:
    raise AssertionError("every marked lever dimension needs authored places")
# The zone's cylinder length is the start from the tip less the dome radius:
# printed as a linear REFERENCE value (the start and the radius govern it).
REFERENCE_DIMENSIONS = frozenset({"PressZoneLen"})
# The dome radius follows the selected bar (a tangent full hemisphere): a
# RADIAL reference, "(R3.0)", keeping SolidWorks' own radius glyph.
RADIAL_REFERENCE_DIMENSIONS = frozenset({"DomeRadius"})

# Cold-drawn brass rod, h9 (upper, lower) deviations on the body.  The press
# zone is the same unstepped bar under a tighter band, so the zone's limits
# must lie inside the body's: stock is SELECTED to meet the zone (lapping can
# only shrink a bar), never stepped.
ROD_DIA_BAND = (0.0, -0.03)
if not (
    ROD_DIA_BAND[1] <= PRESS_ZONE_DIA_BAND[1] <= PRESS_ZONE_DIA_BAND[0] <= ROD_DIA_BAND[0]
):
    raise AssertionError("the press-zone band must lie inside the stock band")

# The clamp block slides along the rod's OD (fit_class shaft_in_bushing): its
# finish is the sliding surface's, native on the one Ø6 cylinder.
SURFACE_FINISHES = (
    SurfaceFinishControl("rod_od", MACHINED_UM, CylinderFace(ROD_DIA)),
)

# Dimension callouts that state a manufacturing fact (the mate, the
# interference) are derived here from the fit contract -- never typed on the
# sheet (_drawing_contract's spec-string rule).  The mating bore reads as the
# REFERENCE nominal the MHA-MG-001 sheet prints, under the same matched-fit
# interference its callout states (rule 25: the two sheets agree; the bore is
# fitted to the rod, so it carries no absolute band of its own).  <MOD-DIAM>
# is SolidWorks' own Ø token.  Two rows, so the block stays short of the
# isometric.
PRESS_ZONE_DIA_CALLOUT = (
    f"IN MHA-MG-001 (<MOD-DIAM>{COLLAR_BORE_DIA:.3f}) BORE:\n"
    f"{PRESS_FIT_BUDGET['interference_min']:.3f}-"
    f"{PRESS_FIT_BUDGET['interference_max']:.3f} DIAMETRAL INTERFERENCE"
)

# True free-text instructions only: the length, the zone, both diameter bands
# and the OD finish are native.  The zone is SELECTED stock or lapped down to
# its band -- lapping cannot enlarge an undersize bar, so the bar end must
# already meet the zone's lower limit.  Then how to hold and press the rod
# (retention is the MHA-MG-001 bracket sheet's).  The force is the fit
# budget's worst case, never typed.  The part stamps these strings into the
# SLDPRT; the drawing displays only $PRPSHEET links.
DRAWING_NOTES = "\n".join(
    (
        "PRESS ZONE Ø: SELECT OR LAP TO BAND. LAPPING CANNOT ENLARGE UNDERSIZE STOCK,",
        "SO SELECT A BAR END ALREADY AT OR ABOVE THE PRESS ZONE'S LOWER LIMIT.",
        f"PRESS MHA-MG-001 COLLAR ONTO ROD HELD NEAR ITS END; {PRESS_FORCE_MAX_KN:.1f} kN MAX AT TIGHT FIT.",
    )
)

# The isometric projection uses a scale different from the sheet.
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
