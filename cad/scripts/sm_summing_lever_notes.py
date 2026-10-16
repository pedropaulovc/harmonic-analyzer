r"""Summing-lever drawing prose -- the view labels the part build stamps into
the SLDPRT, the mate-naming dimension callouts, the marked-dimension contract
and the joint proofs that let the print state no shortfall.

Split OUT of ``summing_lever_spec`` (codex #354, same treatment as
``connecting_rod_notes``): ``build_summing_assembly`` and ``build_knife_mount``
import the lever's geometry constants, so drawing prose living in that import
closure made every notes edit full-rebuild the summing assembly and knife
mount.  Imported ONLY by ``build_sm_summing_lever``, its drawing and the
offline drawing test.
"""

from __future__ import annotations

from magnifying_bracket_joint_layout import LINEAR_BAND
from sm_summing_lever_spec import HOLE_SPEC, SPRING_SEAT_T

# --- Marked-dimension contract.  build_sm_summing_lever marks exactly these. ---
# Every cast contour is sized on the views (machinist review 2026-10-16: the
# sheet may not defer to a pattern the package does not include): the plate,
# the summation web's side radius, each rib's arc, end station and thickness,
# the boss, the spring-anchor pad under the hole row, and the trunnion
# envelope, length and knife-edge radius.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateWidth", "PlateLength"},
    "CoefficientsPlate": {"PlateThickness"},
    "SpringPadProfile": {"SpringPadWidth", "SpringSeatThickness"},
    "CylinderProfile": {"CylDia"},
    "SummationAnchorProfile": {"AnchorOuterDia"},
    "SummationAnchor": {"AnchorHeight"},
    "SummationPlateProfile": {"SummationArcRadius"},
    "SummationPlate": {"WebThickness"},
    "EdgeRibFrontProfile": {
        "EdgeRibFrontArcR",
        "EdgeRibFrontEndTopX",
        "EdgeRibFrontEndTopY",
    },
    "EdgeRibFront": {"EdgeRibThickness"},
    "MiddleRib": {"MiddleRibThickness"},
    "HexKnifeBack": {"HexKnifeBackDepth"},
    "KnifeRidgeFillet": {"KnifeRidgeRadius"},
    "KnifeEnvelopeReference": {"HexWidth", "HexHeight"},
}

# Model-owned text the part writes onto its own dimensions (prefix compartment).
# The summation web's two sides share one radius; both trunnions one length,
# one knife-edge radius and one hexagon (Detail A shows the +Z one).  A radial
# prefix replaces the native R, so a radius prefix carries its own.
DIMENSION_PREFIXES: dict[tuple[str, str], str] = {
    ("SummationPlateProfile", "SummationArcRadius"): "2X R",
    ("HexKnifeBack", "HexKnifeBackDepth"): "2X ",
    ("KnifeRidgeFillet", "KnifeRidgeRadius"): "2X R",
    ("KnifeEnvelopeReference", "HexWidth"): "2X ",
    ("KnifeEnvelopeReference", "HexHeight"): "2X ",
}

KNIFE_MOUNT_NUMBER = "MHA-SM-002"  # sm-knife-mount: the knife-edge seat
BRACKET_NUMBER = "MHA-MG-001"  # mg-magnifying-bracket
BRACKET_SCREW_NUMBER = "MHA-VN-050"  # vn-magnifying-bracket-screw

# Drawing-side callout text keyed on the parametric dimension name: each tight
# band names its mate and function (drawing-guidelines rule 4), and the rib
# dimensions say which ribs share them (one outline in the end views).  A
# vertical dimension whose text stands above its span takes its callout above
# the value, one whose text hangs below takes it below, so the dimension line
# never runs through its own callout.
# The mid rib runs tangent from the boss axis to the rib arc; the boss axis is
# located by the 76.20s in the plan, so the rib arc's callout in the front
# profile, where those tangents show, gives its apex words, not a third 76.20.
# Each summation-web side arc rises from the boss's quadrant (visible in the
# plan) and meets axis A at the plate end inside the cylinder, so its radius
# names that end.  The three receiver coordinates are one bracket hole pattern:
# the outer station names the mate once.  The spring-anchor pad is on the
# underside, which no view shows full length, so its width says it runs the
# plate's length.
DIMENSION_CALLOUTS_ABOVE: dict[str, str] = {
    "EdgeRibFrontEndTopX": "ALL RIBS",
    "EdgeRibFrontEndTopY": "END RIBS",
    "SummationArcRadius": "TO AXIS A\nAT PLATE END",
    "ReceiverX0": f"MATCHES HOLES IN\nBRACKET {BRACKET_NUMBER}",
}
DIMENSION_CALLOUTS_BELOW: dict[str, str] = {
    "HexHeight": f"VERTEX UP\nKNIFE-EDGE SEAT\nIN {KNIFE_MOUNT_NUMBER}",
    "EdgeRibFrontArcR": "ALL RIBS\nMID RIB APEX\nAT BOSS AXIS",
    "RibDepth": f"TAPPED END RIB\nCONTAINS {BRACKET_SCREW_NUMBER} TAP DRILL",
    "SpringPadWidth": "UNDERSIDE PAD\nFULL LENGTH",
}

# Leads the 2-56 receiver callout: what its two depth bands hold.
BRACKET_TAP_CALLOUT_PROCESS = (
    f"FULL THREAD IN END RIB, DRILL CLEARS {BRACKET_SCREW_NUMBER} TIP\n"
)

# --- Joint proofs the print relies on (drawing-guidelines rules 18 and 20). ---
# The 20 channel-spring anchors thread through the pad: its worst-case
# thickness at the title block's .XX band, less 1.5 incomplete threads, is
# the full thread a 6-32 engages, and it must reach 1.5D, so the print states
# no shortfall.
if HOLE_SPEC.size != "#6-32":
    raise AssertionError(
        f"spring-anchor engagement assumes #6-32, not {HOLE_SPEC.size}"
    )
SPRING_TAP_MAJOR_DIA = 0.138 * 25.4
SPRING_TAP_PITCH = 25.4 / 32.0
SPRING_TAP_ENGAGEMENT_MIN = SPRING_SEAT_T - LINEAR_BAND - 1.5 * SPRING_TAP_PITCH
if SPRING_TAP_ENGAGEMENT_MIN < 1.5 * SPRING_TAP_MAJOR_DIA:
    raise AssertionError(
        f"20X {HOLE_SPEC.size} keeps {SPRING_TAP_ENGAGEMENT_MIN:.3f} of full "
        f"thread, under 1.5D"
    )

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
BACK_VIEW_NOTE = "BACK VIEW SCALE 1:1"
