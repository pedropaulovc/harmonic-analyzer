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

from _printed_tolerance import printed_band_mm
from ch_pivot_shaft_spec import SHAFT_DIA, SHAFT_DIA_BAND
from ch_rocker_arm_spec import (
    HUB_COAXIALITY_DIA,
    HUB_DIA,
    HUB_ROOT_RADIUS_MAX,
    PIVOT_HOLE_BAND,
    PIVOT_HOLE_DIA,
    R_TOP,
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
    "StrapProfile": {"TopRadius", "BottomRadius", "RodTipLen"},
    "PivotHoleProfile": {"PivotDia"},
    "HubProfile": {"HubDia"},
    # #743 PR2: the hub length carries its +0.05/0 band natively; the 20-arm
    # stack acceptance (rocker_bank_layout) caps the sum.
    "Hub": {"HubLength"},
    # The top edge's height over the pivot axis, +0.50/0 natively (Codex #936
    # PRRT_kwDOPHDy386mV3AO). Only this one of the sketch's two dimensions
    # prints; the other places the line's foot on the pivot centre.
    "TopEdgeReference": {"TopAbovePivot"},
    # The strap thickness, +/-0.025 natively at three places (Main ruling
    # 2026-10, option b; ch_rocker_arm_spec.ARM_THICKNESS_BAND): the Strap
    # extrude's depth, printed in the end view where the section reads. Its
    # mid-plane is located by a position frame to datum G, the hub width
    # (#948 ruling R; Main's 2026-10-15 option B over the old 2X StrapOffset).
    "Strap": {"StrapThickness"},
    # The hub-to-strap root fillets' single limit (HUB_ROOT_RADIUS_MAX).
    "HubRoot": {"HubRootRadius"},
}

# Decimal classes already authored by the part; shared with the offline
# requirement exporter. The remaining dimensions/notes print at two places.
DEFAULT_DRAWING_PRECISION = 2
DRAWING_PRECISION = {
    "Hub": {"HubLength": 3},
    "HubProfile": {"HubDia": DEFAULT_DRAWING_PRECISION},
    "TopEdgeReference": {"TopAbovePivot": DEFAULT_DRAWING_PRECISION},
    "Strap": {"StrapThickness": 3},
    "HubRoot": {"HubRootRadius": 1},
}
# swTolMAX prints the nominal then MAX, so the modelled radius IS the limit;
# the band runs from sharp up to it. Both strap faces: 2X. A custom radius
# prefix replaces SolidWorks' own "R" (r3 run printed "2X 0.2 max."), so it
# carries it (pn_pen_v_block_spec.DIMENSION_PREFIXES).
HUB_ROOT_R_BAND = (0.0, -HUB_ROOT_RADIUS_MAX)  # (upper, lower)
HUB_ROOT_R_TOL_TYPE = 6  # swTolType_e.swTolMAX
HUB_ROOT_PREFIX = "2X R"
# Detail E's BASIC tip land counts both ends: the J land is the K land's
# mirror, so its length rides this 2X rather than a mirror note.
TIP_LAND_PREFIX = "2X "

# Judge the minimum wall against the metric band the shop actually reads,
# not the underlying 0.508 mm inch class: title_block.yaml prints ±0.51.
_HUB_WALL_WORST = (
    round(HUB_DIA, DEFAULT_DRAWING_PRECISION)
    - printed_band_mm(DEFAULT_DRAWING_PRECISION)
    - (round(PIVOT_HOLE_DIA, DEFAULT_DRAWING_PRECISION) + PIVOT_HOLE_BAND[0])
) / 2.0 - HUB_COAXIALITY_DIA / 2.0
# Round DOWN at the sheet's normal precision; never overstate the minimum.
HUB_WALL_MIN = (
    math.floor(_HUB_WALL_WORST * 10**DEFAULT_DRAWING_PRECISION + 1e-9)
    / 10**DEFAULT_DRAWING_PRECISION
)
# Named exception: MHA-CH-006 hub wall
HUB_WALL_NOTE = f"HUB WALL {HUB_WALL_MIN:.{DEFAULT_DRAWING_PRECISION}f} MIN"

# BUILT_UP_PERMISSION_NOTE may be supplied only as exact explicit permission
# text in DRAWING_NOTES. None/absence means one_piece, never inferred permission.
BUILT_UP_PERMISSION_NOTE = None

# Two lines (drawing-guidelines rule 7; Opus #1020 r3 C3).
DRAWING_NOTES = "\n".join(
    (
        # B2-1, option 4: datum C is the rod-pin hole and the BASIC pin
        # coordinates clock the A|B|C frame, so "above A" is that frame's
        # axis. The tip lands' 10.46° is the arc half-angle: radial to the
        # centre, which the 1:2 view cannot draw (~808 mm off the sheet). Both
        # ends' lands sit on the views (main-r1 Opus: the J LAND row and 2X
        # 5.59), and the views name datum C, so no mirror or datum narration.
        "1. ARC CENTRE DIRECTLY ABOVE A; TIP LANDS RADIAL TO IT.",
        # The OD ceiling is the amplitude bar's foot cheeks at d = 0
        # (ch_rocker_arm_spec); the hub OD's position frame to A in detail D
        # (HUB_COAXIALITY_DIA) holds the named-exception wall.
        f"2. {HUB_WALL_NOTE}; OD CLEARS MHA-CH-001 FOOT CHEEKS.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
# The end view prints at 3:1, not the sheet's 1:2, off the front's projection
# line: a removed view named by its viewing arrow (Opus #1020 r1), enlarged
# so the hub width, its datum and the strap's position read apart (r2).
VIEW_ARROW_LETTER = "F"
RIGHT_VIEW_SCALE = 3
RIGHT_VIEW_NOTE = f"VIEW {VIEW_ARROW_LETTER} SCALE {RIGHT_VIEW_SCALE}:1"


def _limits(low: float, high: float) -> str:
    """A clearance range at the sheet's places, rounded outward, never inward."""
    scale = 10**DEFAULT_DRAWING_PRECISION
    return (
        f"{math.floor(low * scale + 1e-9) / scale:.{DEFAULT_DRAWING_PRECISION}f}-"
        f"{math.ceil(high * scale - 1e-9) / scale:.{DEFAULT_DRAWING_PRECISION}f}"
    )


# Named mates for the two tight bands (drawing-guidelines rule 4): the reamed
# bore runs on the MHA-CH-005 pivot shaft; the strap runs in the MHA-CH-003
# rod's fork slot (ch_rod_pivot_pin_spec.joint_budget side clearance).
PIVOT_SHAFT_CLEARANCE = (
    PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[1] - (SHAFT_DIA + SHAFT_DIA_BAND[0]),
    PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[0] - (SHAFT_DIA + SHAFT_DIA_BAND[1]),
)
PIVOT_FIT_CALLOUT = (
    f"({_limits(*PIVOT_SHAFT_CLEARANCE)} DIAMETRAL\n"
    "CLEARANCE ON PIVOT\n"
    "SHAFT MHA-CH-005)"
)
STRAP_FIT_CALLOUT = (
    f"({_limits(ROD_JOINT_BUDGET['side_clearance_min'], ROD_JOINT_BUDGET['side_clearance_max'])} SIDE\n"
    "CLEARANCE IN ROD\n"
    "FORK MHA-CH-003)"
)
# Integral hub length, not spacers, sets channel pitch: the hubs stack face to
# face on the pivot shaft (rocker_bank_layout). Below-text rows (above-text
# line breaks print as one run).
HUB_LENGTH_CALLOUT = "SETS ARM PITCH:\n20X STACK ON\nMHA-CH-005"
# The amplitude bar's foot rides the top edge (ch_rocker_arm_spec
# TOP_EDGE_BAND): the one profile frame names it below the frame.
TOP_EDGE_MATE_CALLOUT = "MHA-CH-001 FOOT TRACK"
# The rod-pin hole's mate (rule 4; Opus #1020 r3 C5): the MHA-CH-010 pin runs
# in it (ch_rod_pivot_pin_spec), a prefix row over the native #47 DRILL.
ROD_PIN_MATE_CALLOUT = "FOR PIN MHA-CH-010"
# The lower arc shares the top edge's centre (Opus #1020 r2 B1): below-text
# rows under R816 (above-text line breaks print as one run).
BOTTOM_RADIUS_CALLOUT = f"CONCENTRIC\nWITH R{R_TOP:.0f}"
