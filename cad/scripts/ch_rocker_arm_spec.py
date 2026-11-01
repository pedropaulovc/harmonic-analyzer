r"""Rocker-arm dimensional contract -- the single source of truth shared by the
part build (``build_ch_rocker_arm.py``) and its manufacturing drawing
(``draw_ch_rocker_arm.py``).

PURE DATA, no SolidWorks/COM imports (see ``dt_crank_arm_spec`` for the pattern).
Holds the nominal geometry (book ch. 14), the derived spans the drawing needs
for its view math, and the marked-dimension -> kept-dimension NAME map. The
part build marks EXACTLY ``DRAWING_DIMENSIONS``; the drawing keeps exactly their
union across its per-view ``keep`` maps -- the offline test
(``test_ch_rocker_arm_drawing.py``) fails loud if the two drift.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``). Lengths stay
physical millimetres, each fabricated one the exact decimal of its printed inch
value; the arc system, the pivot-to-edge height and the hub length (the station
pitch) are kinematic closures and stay exact.
"""

from __future__ import annotations

import math

import _config
from _hole_spec import HoleSpec
from _inch_wall_limits import WALL_FLOOR_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
import _rocker_interface
from _gtol_cylinder import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

UNIT = drawing_unit("parts/ch-rocker-arm", _config.parts("ch-rocker-arm"))


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as decimal-inch print text: ``.098``, ``31.496``."""
    text = f"{value_mm / 25.4:.{places}f}"
    return text[1:] if text.startswith("0.") else text


# --- Nominal geometry (DIMENSIONS.md "Chapter 14"). These MUST match the
# constants in build_ch_rocker_arm.py (the test cross-checks the load-bearing
# ones), so the drawing's view math reads the same solid the part builds. ---
# Plate thickness, Z (p.27 callout 2.5 mm), finished from 1/8 in flat.
ARM_THICKNESS = 2.4892  # .098
# Milled strap faces either side of the integral hub, micrometer-checked
# (process plan op 20), printed 3-place natively on the strap's thickness
# (Main ruling 2026-10, option b): each inter-arm gap holds one tine of each
# neighbouring rod fork (ch_rod_pivot_pin_spec.joint_budget).
ARM_THICKNESS_BAND = (0.0254, -0.0254)  # (upper, lower) deviations, +/-.001
TOP_ARC_LEN = 292.1  # top edge arc length = 11.5" (ch.30 back view)
BOT_ARC_LEN = 266.7  # bottom edge arc length = 10.5" (ch.30 back-view sketch)
TIP_FACE = 5.588  # .22 tip face, perpendicular to the top edge
PIVOT_HOLE_DIA = 6.5024  # .256, rides the .250 pivot shaft
ROD_HOLE_SPEC = HoleSpec("drilled_number", "#47")

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "pivot_bore", MACHINED_UM, CylinderFace(PIVOT_HOLE_DIA), display_unit=UNIT,
    ),
)

# --- Derived spans (equations of the primitives; mirror build_ch_rocker_arm). ---
R_TOP = _rocker_interface.CURVE_RADIUS

_ALPHA_TOP = (TOP_ARC_LEN / 2.0) / R_TOP
_ALPHA_BOT = (BOT_ARC_LEN / 2.0) / _rocker_interface.R_BOTTOM
TOP_END_X = R_TOP * math.sin(_ALPHA_TOP)
TOP_END_Y = _rocker_interface.CENTER_Y - R_TOP * math.cos(_ALPHA_TOP)
BOT_END_X = _rocker_interface.R_BOTTOM * math.sin(_ALPHA_BOT)

# Rod tip: the top-arc endpoint pushed out along the radius by the tip face.
_RAD_X = TOP_END_X / R_TOP
ROD_TIP_X = TOP_END_X + TIP_FACE * _RAD_X  # widest half-span (~146.25)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. build_ch_rocker_arm marks exactly these; draw_ch_rocker_arm keeps
# exactly their union across its per-view ``keep`` maps. ---
# The marked-dimension contract moved to ``ch_rocker_arm_notes`` with the rest of
# the drawing-only data (codex #354): it changes for drawing-only mark/keep
# updates, and assemblies import this module.

# The amplitude bar's foot rides the top edge, and at d = 0 its cheeks pass
# over this arm's hub, so the print controls the edge's height over the pivot
# axis directly, on the nominal mirror plane, one-sided: the edge may only come out
# high (user ruling 2026-09-26). The centre distance is then REF, and
# the R800 governs only the curvature. With the amplitude bar's one-sided
# notch (ch_amplitude_bar_spec.BOTTOM_NOTCH_DEPTH_BAND) a bar can rest at most
# 1.0 higher than nominal: a steady lever tilt of ~0.45 deg on that channel.
# Its fundamental moves at most 0.0036 mm (0.04 % of the d = 88 term) across
# the stations: error_budget.hook_displacement with the edge 0.5 high and the
# notch 0.5 shallow (test_rocker_bank_layout pins both numbers).
# drawing-simplicity-policy.md `How the repository implements the guidelines` (Codex #936 PRRT_kwDOPHDy386mV3AO): the band is the part's,
# on a model dimension -- build_ch_rocker_arm's hidden TopEdgeReference sketch,
# whose one printed dimension IS this height and drives the arcs' centre.
TOP_EDGE_ABOVE_PIVOT = _rocker_interface.CENTER_Y - _rocker_interface.PIVOT_MID_Y - R_TOP  # 8.0, .315

# Drawing prose (DRAWING_NOTES / ISOMETRIC_VIEW_NOTE) lives in
# ch_rocker_arm_notes.py -- see ch_connecting_rod_notes for the rationale.


# Integral pivot hub (2026-09-02 photo re-derive, ch14 p.28 page002_img02 +
# ch17 p.40): every arm carries its own round boss on both faces at the
# pivot; neighbouring hubs touch face to face and SET the 7.0565 station
# pitch -- there are no loose spacer bushings (the 19 `pivot-bushing` parts
# are retired).
#
# The OD's floor includes both the largest reamed bore and the bore-to-OD
# eccentricity (PR #1354, R9 machinist review: the old Ø0.50 coaxiality left
# only 1.33 wall at the printed OD minimum). The retained Ø.004 position
# control is owner-approved (2026-10-19, relayed by coordinator; RV-04).
# Its radial eccentricity of zone / 2 consumes wall on one side, so the
# required diameter adds it twice to twice rule 17's .060 floor.
# The hub's Ø.400 stands above that floor. Its OD ceiling is the amplitude
# bar's foot cheeks at d = 0 (channel_kinematics ``bar_bottom``);
# test_rocker_bank_layout pins the slack.
# Manufacturing GD&T zones as their frames print them (decimal inch, the
# source of truth); GEOMETRIC_TOLERANCES_MM restates them in mm for geometry.
GEOMETRIC_TOLERANCES_IN: dict[str, str] = {
    "rod-pin hole position": ".008",
    "strap position to hub": ".004",
    "hub OD position to bore": ".004",
    "top edge surface profile": ".020",
}
GEOMETRIC_TOLERANCES_MM: dict[str, float] = {
    name: float(zone) * 25.4 for name, zone in GEOMETRIC_TOLERANCES_IN.items()
}
# (upper, lower): the top edge's one-sided profile zone above, all outside.
TOP_EDGE_BAND = (GEOMETRIC_TOLERANCES_MM["top edge surface profile"], 0.0)
PIVOT_HOLE_BAND = (0.0254, 0.0)  # (upper, lower) +.0010/.0000: reamed; native on PivotDia
RULE12_WALL_FLOOR = WALL_FLOOR_MM  # drawing-guidelines.md rule 17 (walls and webs)
# Authoritative diametral zone; the hub OD's position frame prints it.
HUB_COAXIALITY_DIA = GEOMETRIC_TOLERANCES_MM["hub OD position to bore"]
LINEAR_2PL = printed_band_mm(2, unit=UNIT)  # .XX +/-.01, the band the sheet prints
_HUB_FLOOR = (
    PIVOT_HOLE_DIA
    + PIVOT_HOLE_BAND[0]
    + 2.0 * (RULE12_WALL_FLOOR + HUB_COAXIALITY_DIA / 2.0)
    + LINEAR_2PL
)
HUB_DIA_MIN = math.ceil(round(_HUB_FLOOR * 100.0, 9)) / 100.0  # 9.94
HUB_DIA = 10.16  # .400
if HUB_DIA < HUB_DIA_MIN:
    raise AssertionError(
        f"hub Ø{inch_text(HUB_DIA, 3)} is under its drawing-guidelines.md rule 17 (walls and webs) "
        f"wall floor Ø{inch_text(HUB_DIA_MIN, 3)}"
    )
HUB_LENGTH = 7.0565  # == machine channels.station_pitch_mm (asserted by the build); .2778
# (upper, lower) on the printed hub length (#743 PR2): a hub may only come out
# long, and the 20-arm stack's acceptance (rocker_bank_layout.STACK_L20_ACCEPT)
# caps the sum, as the cylinder gears' overall thickness does.
HUB_LENGTH_BAND = (0.0508, 0.0)  # +.0020/.0000
# The strap symmetric to the hub within this (total; #948 ruling R, PR #1292):
# the hub stack places the arm, the strap carries the rod's fork, so a flat
# rod's float on the arm is measured from the hub's mid-plane. The sheet
# prints it as a position zone on the strap width to datum G, the hub's -Z
# end face (the 20X stack registration), at a BASIC to the strap mid-plane.
# Owner ruling 2026-10-19 retains this frame and datum scheme (RV-05).
STRAP_HUB_SYMMETRY = GEOMETRIC_TOLERANCES_MM["strap position to hub"]
# The hub-to-strap root fillet (drawing-guidelines rule 16), printed as the
# single limit "R.008 MAX" (Opus #1020 r2 C2). The MHA-CH-01 foot cheeks pass
# over the hub at d = 0 and the bar floats axially in its foot notch, so a
# cheek can run on the strap face, where the fillet stands its full radius
# proud of the hub wall: the radius is capped by the cheeks' radial air over
# the hub (test_rocker_bank_layout pins the worst case).
HUB_ROOT_RADIUS_MAX = 0.2032  # .008
