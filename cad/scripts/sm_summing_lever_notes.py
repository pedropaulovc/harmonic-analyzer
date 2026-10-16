r"""Summing-lever drawing prose -- the shortfall statements the part build
stamps into the SLDPRT, the view labels, the mate-naming dimension callouts,
and the marked-dimension contract.

Split OUT of ``summing_lever_spec`` (codex #354, same treatment as
``connecting_rod_notes``): ``build_summing_assembly`` and ``build_knife_mount``
import the lever's geometry constants, so drawing prose living in that import
closure made every notes edit full-rebuild the summing assembly and knife
mount.  Imported ONLY by ``build_sm_summing_lever``, its drawing and the
offline drawing test.
"""

from __future__ import annotations

import math

from magnifying_bracket_joint_layout import (
    LEVER_PLATE_THICKNESS,
    LEVER_PLATE_THICKNESS_BAND,
    POSITION_BAND,
    SCREW_MAJOR_DIA,
)
from sm_summing_lever_spec import HOLE_SPEC, PLATE_T

# --- Marked-dimension contract.  build_sm_summing_lever marks exactly these. ---
# Every cast contour is sized on the views (machinist review 2026-10-16: the
# sheet may not defer to a pattern the package does not include): the plate,
# the summation web's side radius, each rib's arc, end station and thickness,
# the boss, and the trunnion envelope and length.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateWidth", "PlateLength"},
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
    "KnifeEnvelopeReference": {"HexWidth", "HexHeight"},
}

# Model-owned text the part writes onto its own dimensions (prefix compartment).
# The summation web's two sides share one radius; both trunnions one length.
DIMENSION_PREFIXES: dict[tuple[str, str], str] = {
    ("SummationPlateProfile", "SummationArcRadius"): "2X R",
    ("HexKnifeBack", "HexKnifeBackDepth"): "2X ",
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
# already located by the 76.20 in the plan, so its apex takes words, not a
# second 76.20.
DIMENSION_CALLOUTS_ABOVE: dict[str, str] = {
    "EdgeRibFrontEndTopX": "ALL RIBS",
    "EdgeRibFrontEndTopY": "END RIBS",
    "EdgeRibThickness": "DATUM B END RIB",
    "MiddleRibThickness": "MID RIB\nAPEX AT BOSS AXIS",
    "PlateThickness": f"WALL AT {BRACKET_NUMBER} TAPS",
    "ReceiverX0": f"MATCHES {BRACKET_NUMBER}",
    "ReceiverX1": f"MATCHES {BRACKET_NUMBER}",
}
DIMENSION_CALLOUTS_BELOW: dict[str, str] = {
    "HexWidth": f"BOTH TRUNNIONS\nKNIFE-EDGE SEAT IN {KNIFE_MOUNT_NUMBER}",
    "HexHeight": "VERTEX UP",
    "EdgeRibFrontArcR": "ALL RIBS",
    "RibDepth": f"TAPPED END RIB\nCONTAINS {BRACKET_SCREW_NUMBER} TAP DRILL",
    "ReceiverY0": f"MATCHES {BRACKET_NUMBER}",
}

# Leads the 2-56 receiver callout: what its two depth bands hold.
BRACKET_TAP_CALLOUT_PROCESS = (
    f"FULL THREAD IN END RIB, DRILL CLEARS {BRACKET_SCREW_NUMBER} TIP\n"
)


def _floor2(value: float) -> float:
    """Round a worst-case minimum DOWN to the printed two places."""
    return math.floor(value * 100.0 + 1e-9) / 100.0


# --- Stated shortfalls (drawing-guidelines rule 20), computed, never typed. ---
# The 20 channel-spring anchors thread through the 5.08 plate: its worst-case
# thickness less 1.5 incomplete threads is the full thread a 6-32 engages.
if HOLE_SPEC.size != "#6-32":
    raise AssertionError(
        f"spring-anchor engagement assumes #6-32, not {HOLE_SPEC.size}"
    )
SPRING_TAP_MAJOR_DIA = 0.138 * 25.4
SPRING_TAP_PITCH = 25.4 / 32.0
SPRING_TAP_ENGAGEMENT_MIN = (
    PLATE_T - LEVER_PLATE_THICKNESS_BAND - 1.5 * SPRING_TAP_PITCH
)
# The 2-56 receiver row sits 2.54 off the plate's lower face; the bottoming
# tap's lead threads run past the -Z end rib into the plate alone, so the
# thread major's wall to the upper face takes the full plate and row bands.
BRACKET_TAP_WALL_MIN = (
    LEVER_PLATE_THICKNESS
    - LEVER_PLATE_THICKNESS_BAND
    - (LEVER_PLATE_THICKNESS / 2.0 + POSITION_BAND)
    - SCREW_MAJOR_DIA / 2.0
)

DRAWING_NOTES = (
    f"20X {HOLE_SPEC.size} ENGAGEMENT {_floor2(SPRING_TAP_ENGAGEMENT_MIN):.2f} MIN "
    f"({_floor2(SPRING_TAP_ENGAGEMENT_MIN / SPRING_TAP_MAJOR_DIA):.2f}D)"
)
BRACKET_RECEIVER_NOTE = f"2X #2-56 THREAD WALL {_floor2(BRACKET_TAP_WALL_MIN):.2f} MIN"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
BACK_VIEW_NOTE = "BACK VIEW SCALE 1:2"
