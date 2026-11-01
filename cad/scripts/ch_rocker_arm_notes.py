r"""Rocker-arm drawing prose -- the manufacturing notes the part build stamps
into the SLDPRT and the isometric-view label.

Split OUT of ``rocker_arm_spec`` (codex #354, same treatment as
``connecting_rod_notes``): ``build_channel_assembly`` imports the rocker's
geometry, so drawing prose living in that import closure made every notes edit
full-rebuild ``assembly:ch_channel``.  Imported ONLY by ``build_rocker_arm`` and
the offline drawing test.
"""

from __future__ import annotations

import math

from ch_pivot_shaft_spec import SHAFT_DIA, SHAFT_DIA_BAND
from ch_rocker_arm_spec import (
    HUB_COAXIALITY_DIA,
    HUB_DIA,
    HUB_ROOT_RADIUS_MAX,
    LINEAR_2PL,
    PIVOT_HOLE_BAND,
    PIVOT_HOLE_DIA,
    R_TOP,
    inch_text,
)
from ch_rod_pivot_pin_spec import BUDGET as ROD_JOINT_BUDGET

# Coaxiality is owned by the spec, including its eccentricity in the hub's OD
# floor. The note controls the result without prescribing the machining setup.


# True free-text instructions only; geometry / datum structure / roughness live
# in native dimensions / datum tags / FCFs / surface symbols. Hole process,
# size and through condition ride the native callouts; outline dimensions
# define the ends. BASIC radii and top height feed the arc-system profile
# frames directly; the BASIC pin coordinates feed the pin hole's position
# frame.
# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  build_rocker_arm marks exactly these. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StrapProfile": {"TopRadius", "BottomRadius", "RodTipLen", "TipLandAngle"},
    "PivotHoleProfile": {"PivotDia"},
    "HubProfile": {"HubDia"},
    # #743 PR2: the hub length carries its +.0020/0 band natively; the 20-arm
    # stack acceptance (rocker_bank_layout) caps the sum.
    "Hub": {"HubLength"},
    # The top edge's height over the pivot axis, +.020/0 natively (Codex #936
    # PRRT_kwDOPHDy386mV3AO). Only this one of the sketch's two dimensions
    # prints; the other places the line's foot on the pivot centre.
    "TopEdgeReference": {"TopAbovePivot"},
    # The strap thickness, +/-.001 natively at three places (Main ruling
    # 2026-10, option b; ch_rocker_arm_spec.ARM_THICKNESS_BAND): the Strap
    # extrude's depth, printed in the end view where the section reads. Its
    # mid-plane is located by a position frame to datum G, the hub's -Z end
    # face, at a BASIC to that plane (#948 ruling R; #1579 option 1).
    "Strap": {"StrapThickness"},
    # The hub-to-strap root fillets' single limit (HUB_ROOT_RADIUS_MAX).
    "HubRoot": {"HubRootRadius"},
}

# Decimal classes already authored by the part; shared with the offline
# requirement exporter. Decimal inch (#290): the BASIC arc radii and the
# pivot-to-edge height print the places their kinematic values need, the
# reamed bore and the hub length (the station pitch) four; the remaining
# dimensions take the sheet's default.
DEFAULT_DRAWING_PRECISION = 2
DRAWING_PRECISION = {
    "StrapProfile": {
        "TipLandAngle": DEFAULT_DRAWING_PRECISION,
        "TopRadius": 3,
        "BottomRadius": 3,
    },
    "PivotHoleProfile": {"PivotDia": 4},
    "Hub": {"HubLength": 4},
    "HubProfile": {"HubDia": DEFAULT_DRAWING_PRECISION},
    "TopEdgeReference": {"TopAbovePivot": 3},
    "Strap": {"StrapThickness": 3},
    "HubRoot": {"HubRootRadius": 3},
}
# swTolMAX prints the nominal then MAX, so the modelled radius IS the limit;
# the band runs from sharp up to it. Both strap faces: 2X. A custom radius
# prefix replaces SolidWorks' own "R" (r3 run printed "2X 0.2 max."), so it
# carries it (pn_pen_v_block_spec.DIMENSION_PREFIXES).
HUB_ROOT_R_BAND = (0.0, -HUB_ROOT_RADIUS_MAX)  # (upper, lower)
HUB_ROOT_R_TOL_TYPE = 6  # swTolType_e.swTolMAX
HUB_ROOT_PREFIX = "2X R"
# Why the corner is tighter than the title block: the foot cheeks run over it.
HUB_ROOT_CALLOUT = "CLEARS\nMHA-CH-01\nCHEEKS"
# The callout as printed, for the offline requirement exporter (features note).
HUB_ROOT_NOTE = (
    f"{HUB_ROOT_PREFIX}"
    f"{inch_text(HUB_ROOT_RADIUS_MAX, DRAWING_PRECISION['HubRoot']['HubRootRadius'])} MAX"
)
# Detail E's BASIC land length and angle count both ends: the J land is
# the K land's mirror. Their native dimensions carry 2X, not a mirror note.
TIP_LAND_PREFIX = "2X "
TIP_LAND_ANGLE_PREFIX = "2X "

# The minimum wall at the printed limits: the hub OD at its .XX band, the
# reamed bore at its largest and the OD's position zone.
_HUB_WALL_WORST = (
    HUB_DIA - LINEAR_2PL - (PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[0])
) / 2.0 - HUB_COAXIALITY_DIA / 2.0
# Printed at three places, rounded DOWN; never overstate the minimum.
_WALL_PLACES = 3
HUB_WALL_MIN = (
    math.floor(_HUB_WALL_WORST / 25.4 * 10**_WALL_PLACES + 1e-9)
    / 10**_WALL_PLACES
    * 25.4
)
# Named exception: MHA-CH-06 hub wall
HUB_WALL_NOTE = f"HUB WALL {inch_text(HUB_WALL_MIN, _WALL_PLACES)} MIN"

# BUILT_UP_PERMISSION_NOTE may be supplied only as exact explicit permission
# text in DRAWING_NOTES. None/absence means one_piece, never inferred permission.
# Route v3 (user ruling, 2026-10-16): the part may be the turned hub
# MHA-CH-12 joined to the flat strap MHA-CH-13. Permission only; the joint
# (its fit) is on those two details (ch_rocker_hub_fit), never a method here
# -- the note points at them so the joint is defined, not left open (r1
# machinist review of "MAY BE BUILT UP FROM ...").
BUILT_UP_PERMISSION_NOTE = (
    "2. MAY BE HUB MHA-CH-12 JOINED TO STRAP MHA-CH-13 PER THEIR DWGS."
)

# Two lines (drawing-guidelines rule 7; Opus #1020 r3 C3). The common arc
# centre's location is no longer a general note: it rides R800's own
# below-text callout (TOP_RADIUS_CALLOUT), at the feature it governs (rule 7).
DRAWING_NOTES = "\n".join(
    (
        # The OD ceiling is the amplitude bar's foot cheeks at d = 0
        # (ch_rocker_arm_spec); the hub OD's position frame to A in detail D
        # (HUB_COAXIALITY_DIA) holds the named-exception wall.
        f"1. {HUB_WALL_NOTE}; OD CLEARS MHA-CH-01 FOOT CHEEKS.",
        BUILT_UP_PERMISSION_NOTE,
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
# The end view prints at 3:1, not the sheet's 1:2, off the front's projection
# line: a removed view named by its viewing arrow (Opus #1020 r1), enlarged
# so the hub width, datum G and the strap's position read apart (r2).
VIEW_ARROW_LETTER = "F"
RIGHT_VIEW_SCALE = 3
RIGHT_VIEW_NOTE = f"VIEW {VIEW_ARROW_LETTER} SCALE {RIGHT_VIEW_SCALE}:1"


def _limits(low: float, high: float, places: int) -> str:
    """A clearance range (mm) in inch at ``places``, rounded outward, never inward."""
    scale = 10**places / 25.4
    return (
        f"{inch_text(math.floor(low * scale + 1e-9) / scale, places)}-"
        f"{inch_text(math.ceil(high * scale - 1e-9) / scale, places)}"
    )


# Named mates for the two tight bands (drawing-guidelines rule 4): the reamed
# bore runs on the MHA-CH-05 pivot shaft; the strap runs in the MHA-CH-03
# rod's fork slot (ch_rod_pivot_pin_spec.joint_budget side clearance).
PIVOT_SHAFT_CLEARANCE = (
    PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[1] - (SHAFT_DIA + SHAFT_DIA_BAND[0]),
    PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[0] - (SHAFT_DIA + SHAFT_DIA_BAND[1]),
)
# At the bore's own four places.
PIVOT_FIT_CALLOUT = (
    f"({_limits(*PIVOT_SHAFT_CLEARANCE, DRAWING_PRECISION['PivotHoleProfile']['PivotDia'])} DIAMETRAL\n"
    "CLEARANCE ON PIVOT\n"
    "SHAFT MHA-CH-05)"
)
# At the strap thickness's three places.
STRAP_FIT_CALLOUT = (
    f"({_limits(ROD_JOINT_BUDGET['side_clearance_min'], ROD_JOINT_BUDGET['side_clearance_max'], DRAWING_PRECISION['Strap']['StrapThickness'])} TOTAL\n"
    "SIDE CLEARANCE IN\n"
    "MHA-CH-03 FORK)"
)
# Integral hub length, not spacers, sets channel pitch: the hubs stack face to
# face on the pivot shaft (rocker_bank_layout). Below-text rows (above-text
# line breaks print as one run).
HUB_LENGTH_CALLOUT = "SETS ARM PITCH:\n20X STACK ON\nMHA-CH-05"
# The amplitude bar's foot rides the top edge (ch_rocker_arm_spec
# TOP_EDGE_BAND): the one profile frame names it below the frame.
TOP_EDGE_MATE_CALLOUT = "MHA-CH-01 FOOT TRACK"
# The rod-pin hole's mate (rule 4; Opus #1020 r3 C5): the MHA-CH-10 pin runs
# in it (ch_rod_pivot_pin_spec), a prefix row over the native #47 DRILL.
ROD_PIN_MATE_CALLOUT = "FOR PIN MHA-CH-10"
# The lower arc shares the top edge's centre (Opus #1020 r2 B1): below-text
# rows under R816 (above-text line breaks print as one run).
BOTTOM_RADIUS_CALLOUT = f"CONCENTRIC\nWITH R{inch_text(R_TOP, DRAWING_PRECISION['StrapProfile']['TopRadius'])}"
# That shared centre sits on A's axis (x = 0 in the clocked A|B|C frame; the
# 1:2 view cannot reach it): one below-text row under R800, the former note 1.
# Detail E's native BASIC angle defines the radial lands, so no note narrates
# their direction either.
TOP_RADIUS_CALLOUT = "CENTRE ABOVE A"
