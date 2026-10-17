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
from _gtol_cylinder import CylinderFace
from _surface_finish import SEAT_UM, SurfaceFinishControl
from mg_lever_press_fit_geom import (
    COLLAR_BORE_DIA,
    COLLAR_LENGTH,
    COLLAR_LENGTH_BAND,
    PRESS_FIT_BUDGET,
    PRESS_ZONE_DIA_BAND,
    PRESS_ZONE_LENGTH,
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
# second diameter: its top line's height IS the dome radius) as a plain Ø at
# the title block's .X, no band and no callout.  The press zone -- the
# cylinder the bracket collar grips, from
# PRESS_ZONE_LENGTH before the east tip to the dome tangent -- is a tighter
# band on the same unstepped Ø6, so it lives on the blanked ``PressZone``
# reference sketch: its start from the tip a single MIN limit
# (PRESS_ZONE_START_TOL_TYPE), its cylinder length to the tangent (a
# REFERENCE: start minus the dome radius), and its diameter carrying
# PRESS_ZONE_DIA_BAND, both limits native (drawing-guidelines.md rule 3
# (decimal places carry the tolerance)).  The
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
# that is good enough stays stock).  The zone's start is a MIN at .X: the
# selected land only has to cover the longest collar, so no tighter places
# (rule 4).  The zone diameter carries its band at three places; the two
# references read at .X.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RodProfile": {"OverallLength": 1, "DomeRadius": 1},
    "RodStock": {"RodDia": 1},
    "PressZone": {"PressZoneStart": 1, "PressZoneLen": 1, "PressZoneDia": 3},
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

# --- the MHA-MG-002 clamp screw's seat: the Ø6 body ---------------------------
# Owner ruling 2026-10-17: the clamp's thumb screw (MHA-VN-011) pinches the
# lever wherever the operator sets the clamp, so the OD it bears on is a
# static locating seat, Ra 3.2 (drawing-guidelines.md rule 6, SEAT_UM;
# mg-magnifying-lever.yaml machinist_exceptions RV-01).  The screw stands on
# the clamp's hex axis, the block's centre along the rod, and the block slides
# from flush with the west tip to against the collar face
# (mg_magnifying_lever_geom.clamp_radius_band), so the screw's tip can bear
# anywhere from about 5 to 150 of the body's 3..162 straight cylinder (the
# drawing test derives that reach from the clamp and screw geometry).  The
# symbol qualifies that whole face, as on the MHA-MG-004 vertical rod: a zone
# stopping where the travel runs out would add two lengths and nothing the
# shop could act on.  The revolve's one top line makes the body ONE Ø6
# cylindrical face from dome tangent to dome tangent, so the press zone is
# the same face: the zone keeps its own diameter band (PRESS_ZONE_DIA_BAND),
# the Ra 3.2 governs the face's finish.
SURFACE_FINISHES = (
    SurfaceFinishControl("clamp_screw_seat", SEAT_UM, CylinderFace(ROD_DIA)),
)
# The seat's reason stands at its symbol (rule 7: say why, where it applies),
# naming the clamp whose screw bears there.
CLAMP_NUMBER = "MHA-MG-002"
SCREW_SEAT_CALLOUT = f"{CLAMP_NUMBER} SCREW SEAT"

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
# The zone's start from the tip is a single MIN limit, "10.0 MIN", at the
# collar's MAXIMUM length: the rod's tip sits flush with the collar's outer
# face, so the selected land must reach past the collar's inner face on the
# longest collar (mg_lever_press_fit_geom: the bore is finished to the
# measured land, never to unselected stock), and a longer land only laps more
# rod (machinist review r2: the old 0/-0.05 band bought no function).  The
# model nominal IS the limit; mg_magnifying_bracket_spec.COLLAR_LENGTH_CALLOUT
# names this zone from the other side.  The callout names the mate the zone
# must cover (rule 4), two rows so the block stays narrow right of the tip.
PRESS_ZONE_START_TOL_TYPE = 5  # swTolType_e.swTolMIN: prints "10.0 MIN"
if PRESS_ZONE_LENGTH != COLLAR_LENGTH + COLLAR_LENGTH_BAND[0]:
    raise AssertionError("the press zone's minimum must be the collar's maximum length")
PRESS_ZONE_START_CALLOUT = f"PRESS ZONE COVERS\n{MATE_NUMBER} COLLAR"

# No note block (drawing-guidelines.md rule 7): the stock, the zone and its
# mate are callouts at their features.  Pressing the collar on, how to hold
# the rod and the force limit are the MHA-MG-000 assembly's step
# (mg_lever_press_fit_geom.PRESS_INSTALLATION_NOTES), not this part's.

# The isometric projection uses a scale different from the sheet.
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
