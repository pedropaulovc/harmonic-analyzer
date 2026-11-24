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

from ch_rocker_arm_spec import (
    HUB_COAXIALITY_DIA,
    HUB_DIA,
    HUB_ROOT_RADIUS_MAX,
    LINEAR_2PL,
    PIVOT_HOLE_BAND,
    PIVOT_HOLE_DIA,
    inch_text,
)

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
    # The hub length carries its +/-.002 band natively (#3114: the arms float
    # on the pivot shaft, so no stack sums the hubs).
    "Hub": {"HubLength"},
    # The top edge's height over the pivot axis, +.020/0 natively (Codex #936
    # PRRT_kwDOPHDy386mV3AO). Only this one of the sketch's two dimensions
    # prints; the other places the line's foot on the pivot centre.
    "TopEdgeReference": {"TopAbovePivot"},
    # The lower arc's midpoint below the pivot axis: with TopAbovePivot and
    # the two radii it places both arc centres on the mirror axis (rule 26),
    # no "concentric" prose.
    "BottomEdgeReference": {"BottomBelowPivot"},
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
# F-drilled bore three (the DRILLED HOLES row) and the hub length three (its
# +/-.002 band); the remaining dimensions take the sheet's default.
DEFAULT_DRAWING_PRECISION = 2
DRAWING_PRECISION = {
    "StrapProfile": {
        "TipLandAngle": DEFAULT_DRAWING_PRECISION,
        "TopRadius": 3,
        "BottomRadius": 3,
    },
    "PivotHoleProfile": {"PivotDia": 3},
    "Hub": {"HubLength": 3},
    "HubProfile": {"HubDia": DEFAULT_DRAWING_PRECISION},
    "TopEdgeReference": {"TopAbovePivot": 3},
    "BottomEdgeReference": {"BottomBelowPivot": 3},
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
# Two rows, not three: in view F the block stands between the strap's
# position frame and the hub top, which leaves room for three rows in all.
HUB_ROOT_CALLOUT = "CLEARS MHA-CH-01\nCHEEKS"
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
# F-drilled bore at the DRILLED HOLES row's largest and the OD's position zone.
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

# Two lines (drawing-guidelines rule 7; Opus #1020 r3 C3): the stated wall
# shortfall (rule 20) and the built-up permission. The hub OD's reason
# (the MHA-CH-01 foot cheeks) is printed once, on the hub-root radius.
DRAWING_NOTES = "\n".join(
    (
        # The hub OD's position frame to A in detail D (HUB_COAXIALITY_DIA)
        # holds the named-exception wall.
        f"1. {HUB_WALL_NOTE}.",
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


# Named mates for the bore and the strap (drawing-guidelines rule 4): the
# F-drilled bore runs on the MHA-CH-05 pivot shaft (owner ruling 2026-11-24,
# fit audit question 1: the drill and the mate, no number); the strap slides
# in the MHA-CH-03 rod's fork slot. View F's left margin holds rows of ~17
# characters.
PIVOT_FIT_CALLOUT = "RUNNING CLEARANCE ON MHA-CH-05"
# Under the strap thickness in view F.
STRAP_FIT_CALLOUT = "SLIDING FIT IN\nMHA-CH-03 FORK"
# The arms float on the pivot shaft, each located by its own rod (#3114): the
# hub's end faces only bound how close two neighbours can come, which the rod
# forks and the amplitude bars between them rely on (sh_vn_pivot_pin_rod_spec,
# ch_channel_assembly_spec.bar_gap_budget). Below-text rows (above-text line
# breaks print as one run). No "20X" here: on one length it reads as a
# feature count (rule 26; ch-fab-2 r3); the count is MHA-CH-00's.
HUB_LENGTH_CALLOUT = "KEEPS ADJACENT\nMHA-CH-06 APART"
# The amplitude bar's foot rides the top edge (ch_rocker_arm_spec
# TOP_EDGE_BAND): the one profile frame names it below the frame.
TOP_EDGE_MATE_CALLOUT = "MHA-CH-01 FOOT TRACK"
# The rod-pin hole's mate (rule 4; Opus #1020 r3 C5): the MHA-SH-VN-58 pin
# runs in it (sh_vn_pivot_pin_rod_spec), a prefix row over the native #47 DRILL.
ROD_PIN_MATE_CALLOUT = "FOR PIN MHA-SH-VN-58"
