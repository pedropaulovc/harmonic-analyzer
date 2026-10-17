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

from _fit_deviations import deviations
from mg_lever_press_fit_geom import (
    COLLAR_BORE_DIA,
    COLLAR_LENGTH,
    COLLAR_LENGTH_BAND,
    PRESS_FIT_BUDGET,
    PRESS_ZONE_DIA_BAND,
    PRESS_ZONE_LENGTH,
    PRESS_ZONE_LENGTH_BAND,
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
# second diameter: its top line's height IS the dome radius) as plain stock,
# no band.  The press zone -- the cylinder the bracket collar grips, from
# PRESS_ZONE_LENGTH before the east tip to the dome tangent -- is a tighter
# band on the same unstepped Ø6, so it lives on the blanked ``PressZone``
# reference sketch: its start from the tip carrying PRESS_ZONE_LENGTH_BAND,
# its cylinder length to the tangent (a REFERENCE: start minus the dome
# radius), and its diameter carrying PRESS_ZONE_DIA_BAND, both bands native
# (drawing-guidelines.md rule 3 (decimal places carry the tolerance)).  The
# zone's start is a solid line across the bar, so the zone reads between it
# and the dome tangent.  The drawing shows both sketches in the front view
# (_drawing_hidden_sketches). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"OverallLength", "DomeRadius"},
    "RodStock": {"RodDia"},
    "PressZone": {"PressZoneStart", "PressZoneLen", "PressZoneDia"},
}
# The tip-to-tip length is checked at .X (+/-0.8): the rod's west end only
# bounds the clamp's travel.  The stock diameter reads at .X too: the bar's
# own OD, held by no band of the print (drawing-guidelines.md rule 4: stock
# that is good enough stays stock).  The zone's start carries its axial band
# at .XX, matched to the collar's length band, so the selected zone covers the
# collar's true contact (the collar length less the dome radius).  The zone
# diameter carries its band at three places; the two references read at .X.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RodProfile": {"OverallLength": 1, "DomeRadius": 1},
    "RodStock": {"RodDia": 1},
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

# The PURCHASED bar: cold-drawn brass rod, h9 (upper, lower) deviations.  NOT
# printed -- the sheet's Ø6.0 is plain stock under the title block's .X -- it
# is the procurement contract the press zone relies on.  The zone is the same
# unstepped bar under a tighter band, SELECTED from this stock (never
# stepped), so its limits must lie inside the stock's or no bar could supply
# it.
ROD_DIA_BAND = (0.0, -0.03)
_stock_low, _stock_high = deviations(ROD_DIA_BAND)
_zone_low, _zone_high = deviations(PRESS_ZONE_DIA_BAND)
if not _stock_low <= _zone_low <= _zone_high <= _stock_high:
    raise AssertionError(
        "the press-zone band must lie inside the purchased stock's band, "
        "so the zone can be selected from that stock"
    )
# The stock diameter's callout: no turned band, the bar as bought.
ROD_DIA_CALLOUT = "STOCK OK"

# The mate both banded zone callouts name: the bracket whose collar the zone
# is pressed into.
MATE_NUMBER = "MHA-MG-001"

# Dimension callouts that state a manufacturing fact (the mate, the
# interference) are derived here from the fit contract -- never typed on the
# sheet (_drawing_contract's spec-string rule).  The mating bore reads as the
# REFERENCE nominal the MHA-MG-001 sheet prints, under the same matched-fit
# interference its callout states (rule 25: the two sheets agree; the bore is
# fitted to the rod, so it carries no absolute band of its own).  <MOD-DIAM>
# is SolidWorks' own Ø token.  Two rows, so the block stays short of the
# isometric.
PRESS_ZONE_DIA_CALLOUT = (
    f"IN {MATE_NUMBER} (<MOD-DIAM>{COLLAR_BORE_DIA:.3f}) BORE:\n"
    f"{PRESS_FIT_BUDGET['interference_min']:.3f}-"
    f"{PRESS_FIT_BUDGET['interference_max']:.3f} DIAMETRAL INTERFERENCE"
)
# The zone's start from the tip carries the collar's length band: the rod's
# tip sits flush with the collar's outer face, so the zone is exactly the
# collar's length (mg_magnifying_bracket_spec.COLLAR_LENGTH_CALLOUT names this
# zone from the other side).  The callout names that mate (rule 4).
if (PRESS_ZONE_LENGTH, PRESS_ZONE_LENGTH_BAND) != (COLLAR_LENGTH, COLLAR_LENGTH_BAND):
    raise AssertionError(
        "the press zone's start must match the collar's length, band and all"
    )
PRESS_ZONE_START_CALLOUT = f"PRESS ZONE START\nMATCHES {MATE_NUMBER}\nCOLLAR LENGTH"

# No note block (drawing-guidelines.md rule 7): the stock, the zone and its
# mate are callouts at their features.  Pressing the collar on, how to hold
# the rod and the force limit are the MHA-MG-000 assembly's step
# (mg_lever_press_fit_geom.PRESS_INSTALLATION_NOTES), not this part's.

# The isometric projection uses a scale different from the sheet.
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
