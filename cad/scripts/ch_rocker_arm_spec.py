r"""Rocker-arm dimensional contract -- the single source of truth shared by the
part build (``build_ch_rocker_arm.py``) and its manufacturing drawing
(``draw_ch_rocker_arm.py``).

PURE DATA, no SolidWorks/COM imports (see ``dt_crank_arm_spec`` for the pattern).
Holds the nominal geometry (book ch. 14), the derived spans the drawing needs
for its view math, and the marked-dimension -> kept-dimension NAME map. The
part build marks EXACTLY ``DRAWING_DIMENSIONS``; the drawing keeps exactly their
union across its per-view ``keep`` maps -- the offline test
(``test_ch_rocker_arm_drawing.py``) fails loud if the two drift.
"""

from __future__ import annotations

import math
from _hole_spec import HoleSpec


from dt_cone_pivot_post_installation import MECHANISM_X_SHIFT
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

# --- Nominal geometry (DIMENSIONS.md "Chapter 14"). These MUST match the
# constants in build_ch_rocker_arm.py (the test cross-checks the load-bearing
# ones), so the drawing's view math reads the same solid the part builds. ---
CURVE_RADIUS = 800.0  # top-edge arc radius = amplitude-bar length (stated)
ARM_DEPTH = 16.0  # perpendicular top-to-bottom depth (p.29 callout)
ARM_THICKNESS = 2.5  # plate thickness, Z (p.27 callout)
# Milled strap faces either side of the integral hub, micrometer-checked
# (process plan op 20), printed 3-place natively on the strap's thickness
# (Main ruling 2026-10, option b): each inter-arm gap holds one tine of each
# neighbouring rod fork (ch_rod_pivot_pin_spec.joint_budget).
ARM_THICKNESS_BAND = (0.025, -0.025)  # (upper, lower) deviations
TOP_ARC_LEN = 292.1  # top edge arc length = 11.5" (ch.30 back view)
BOT_ARC_LEN = 266.7  # bottom edge arc length = 10.5" (ch.30 back-view sketch)
TIP_FACE = 5.588  # 0.22" tip face, perpendicular to the top edge
PIVOT_HOLE_DIA = 6.5  # rides the 6.35 pivot shaft
ROD_HOLE_X = 127.3738 - MECHANISM_X_SHIFT
ROD_HOLE_ABOVE_BOTTOM = 5.53312035905  # preserves the level-pose pin Y after X shift
ROD_HOLE_SPEC = HoleSpec("drilled_number", "#47")

SURFACE_FINISHES = (
    SurfaceFinishControl("pivot_bore", MACHINED_UM, CylinderFace(PIVOT_HOLE_DIA)),
)

# --- Derived spans (equations of the primitives; mirror build_ch_rocker_arm). ---
R_TOP = CURVE_RADIUS
R_BOTTOM = CURVE_RADIUS + ARM_DEPTH
CENTER_Y = CURVE_RADIUS + ARM_DEPTH

_ALPHA_TOP = (TOP_ARC_LEN / 2.0) / R_TOP
_ALPHA_BOT = (BOT_ARC_LEN / 2.0) / R_BOTTOM
TOP_END_X = R_TOP * math.sin(_ALPHA_TOP)
TOP_END_Y = CENTER_Y - R_TOP * math.cos(_ALPHA_TOP)
BOT_END_X = R_BOTTOM * math.sin(_ALPHA_BOT)

# Rod tip: the top-arc endpoint pushed out along the radius by the tip face.
_RAD_X = TOP_END_X / R_TOP
ROD_TIP_X = TOP_END_X + TIP_FACE * _RAD_X  # widest half-span (~146.25)

# Rod-pin hole Y (low in the strap, ch14 fan photo).
ROD_HOLE_Y = (
    CENTER_Y - math.sqrt(R_BOTTOM**2 - ROD_HOLE_X * ROD_HOLE_X)
) + ROD_HOLE_ABOVE_BOTTOM


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. build_ch_rocker_arm marks exactly these; draw_ch_rocker_arm keeps
# exactly their union across its per-view ``keep`` maps. ---
# The marked-dimension contract moved to ``ch_rocker_arm_notes`` with the rest of
# the drawing-only data (codex #354): it changes for drawing-only mark/keep
# updates, and assemblies import this module.

# The pivot bore rides at the strap mid-depth; assemblies place the arm off
# this (imported from here, never from build_ch_rocker_arm, so drawing-only edits
# stay out of assembly rebuild closures -- codex #354).
PIVOT_MID_Y = ARM_DEPTH / 2.0  # 8.0

# The amplitude bar's foot rides the top edge, and at d = 0 its cheeks pass
# over this arm's hub, so the print controls the edge's height over the pivot
# axis directly, on the mirror axis, one-sided: the edge may only come out
# high (user ruling 2026-09-26). The 808.00 centre distance is then REF, and
# the R800 governs only the curvature. With the amplitude bar's one-sided
# notch (ch_amplitude_bar_spec.BOTTOM_NOTCH_DEPTH_BAND) a bar can rest at most
# 1.0 higher than nominal: a steady lever tilt of ~0.45 deg on that channel.
# Its fundamental moves at most 0.0036 mm (0.04 % of the d = 88 term) across
# the stations: error_budget.hook_displacement with the edge 0.5 high and the
# notch 0.5 shallow (test_rocker_bank_layout pins both numbers).
# Policy rule 2 (Codex #936 PRRT_kwDOPHDy386mV3AO): the band is the part's,
# on a model dimension -- build_ch_rocker_arm's hidden TopEdgeReference sketch,
# whose one printed dimension IS this height and drives the arcs' centre.
TOP_EDGE_ABOVE_PIVOT = CENTER_Y - PIVOT_MID_Y - R_TOP  # 8.0
TOP_EDGE_BAND = (0.50, 0.0)  # (upper, lower)

# Drawing prose (DRAWING_NOTES / ISOMETRIC_VIEW_NOTE) lives in
# ch_rocker_arm_notes.py -- see ch_connecting_rod_notes for the rationale.


# Integral pivot hub (2026-09-02 photo re-derive, ch14 p.28 page002_img02 +
# ch17 p.40): every arm carries its own round boss on both faces at the
# pivot; neighbouring hubs touch face to face and SET the 7.0565 station
# pitch -- there are no loose spacer bushings (the 19 `pivot-bushing` parts
# are retired).
#
# The OD's floor is the hub wall: drawing-simplicity policy rule 12's 1.5
# over the reamed bore at its largest, with the OD at the bottom of the
# title block's .XX band (machinist review, MHA-CH-006 round 1: O10.00 left
# 1.48). The MHA-CH-009 thrust washer's own floor is higher, so the two share
# one O10.20 (ch_rocker_thrust_washer_spec). The ceiling is the amplitude bar's
# foot cheeks, which pass over the hub at d = 0 (channel_kinematics
# ``bar_bottom``); test_rocker_bank_layout pins the slack.
PIVOT_HOLE_BAND = (0.03, 0.0)  # (upper, lower): reamed; native on PivotDia
RULE12_WALL_FLOOR = 1.5  # drawing-simplicity policy rule 12
LINEAR_2PL = 0.508  # title-block .XX band (pinned to _config by the tests)
_HUB_FLOOR = PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[0] + 2.0 * RULE12_WALL_FLOOR + LINEAR_2PL
HUB_DIA_MIN = math.ceil(round(_HUB_FLOOR * 100.0, 9)) / 100.0  # 10.04
HUB_DIA = 10.2
if HUB_DIA < HUB_DIA_MIN:
    raise AssertionError(
        f"hub O{HUB_DIA:.2f} is under its rule-12 wall floor O{HUB_DIA_MIN:.2f}"
    )
HUB_LENGTH = 7.0565  # == machine channels.station_pitch_mm (asserted by the build)
# (upper, lower) on the printed hub length (#743 PR2): a hub may only come out
# long, and the 20-arm stack's acceptance (rocker_bank_layout.STACK_L20_ACCEPT)
# caps the sum, as the cylinder gears' overall thickness does.
HUB_LENGTH_BAND = (0.05, 0.0)

# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "rod-pin hole position": "0.20",
}
