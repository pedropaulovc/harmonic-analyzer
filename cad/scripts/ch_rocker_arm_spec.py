r"""Rocker-arm hub, fit and GD&T contract shared by the part and drawing.

PURE DATA, no SolidWorks/COM imports. Stable strap-outline geometry lives in
``ch_rocker_arm_outline_spec``; consumers of the guarded hub and fit dimensions
import this module directly. Drawing prose and the marked-dimension contract
live in ``ch_rocker_arm_notes``.
"""

from __future__ import annotations

import math
from _hole_spec import HoleSpec
from _gtol_cylinder import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

# Milled strap faces either side of the integral hub, micrometer-checked
# (process plan op 20), printed 3-place natively on the strap's thickness
# (Main ruling 2026-10, option b): each inter-arm gap holds one tine of each
# neighbouring rod fork (ch_rod_pivot_pin_spec.joint_budget).
ARM_THICKNESS_BAND = (0.025, -0.025)  # (upper, lower) deviations
PIVOT_HOLE_DIA = 6.5  # rides the 6.35 pivot shaft
ROD_HOLE_SPEC = HoleSpec("drilled_number", "#47")

SURFACE_FINISHES = (
    SurfaceFinishControl("pivot_bore", MACHINED_UM, CylinderFace(PIVOT_HOLE_DIA)),
)


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. build_ch_rocker_arm marks exactly these; draw_ch_rocker_arm keeps
# exactly their union across its per-view ``keep`` maps. ---
# The marked-dimension contract moved to ``ch_rocker_arm_notes`` with the rest of
# the drawing-only data (codex #354): it changes for drawing-only mark/keep
# updates, and assemblies import this module.


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
# only 1.33 wall at the printed OD minimum). The retained Ø0.10 position
# control is owner-approved (2026-10-19, relayed by coordinator; RV-04).
# Its radial eccentricity of zone / 2 consumes wall on one side, so the
# required diameter adds it twice to twice rule 17's 1.5 floor.
# The hub retains O10.20 above that floor. Its OD ceiling is the amplitude
# bar's foot cheeks at d = 0 (channel_kinematics ``bar_bottom``);
# test_rocker_bank_layout pins the slack.
PIVOT_HOLE_BAND = (0.03, 0.0)  # (upper, lower): reamed; native on PivotDia
RULE12_WALL_FLOOR = 1.5  # drawing-guidelines.md rule 17 (walls and webs)
HUB_COAXIALITY_DIA = 0.10  # authoritative diametral zone; the hub OD's position frame prints it
LINEAR_2PL = 0.508  # raw .XX class; notes judge the actual printed ±0.51
_HUB_FLOOR = (
    PIVOT_HOLE_DIA
    + PIVOT_HOLE_BAND[0]
    + 2.0 * (RULE12_WALL_FLOOR + HUB_COAXIALITY_DIA / 2.0)
    + LINEAR_2PL
)
HUB_DIA_MIN = math.ceil(round(_HUB_FLOOR * 100.0, 9)) / 100.0  # 10.14
HUB_DIA = 10.2
if HUB_DIA < HUB_DIA_MIN:
    raise AssertionError(
        f"hub O{HUB_DIA:.2f} is under its drawing-guidelines.md rule 17 (walls and webs) wall floor O{HUB_DIA_MIN:.2f}"
    )
HUB_LENGTH = 7.0565  # == machine channels.station_pitch_mm (asserted by the build)
# (upper, lower) on the printed hub length (#743 PR2): a hub may only come out
# long, and the 20-arm stack's acceptance (rocker_bank_layout.STACK_L20_ACCEPT)
# caps the sum, as the cylinder gears' overall thickness does.
HUB_LENGTH_BAND = (0.05, 0.0)
# The strap symmetric to the hub within this (total; #948 ruling R, PR #1292):
# the hub stack places the arm, the strap carries the rod's fork, so a flat
# rod's float on the arm is measured from the hub's mid-plane. The sheet
# prints it as a position zone on the strap width to datum G, the hub's -Z
# end face (the 20X stack registration), at a BASIC to the strap mid-plane.
# Owner ruling 2026-10-19 retains this frame and datum scheme (RV-05).
STRAP_HUB_SYMMETRY = 0.10
# The hub-to-strap root fillet (drawing-guidelines rule 16), printed as the
# single limit "R0.2 MAX" (Opus #1020 r2 C2). The MHA-CH-01 foot cheeks pass
# over the hub at d = 0 and the bar floats axially in its foot notch, so a
# cheek can run on the strap face, where the fillet stands its full radius
# proud of the hub wall: the radius is capped by the cheeks' radial air over
# the hub (test_rocker_bank_layout pins the worst case).
HUB_ROOT_RADIUS_MAX = 0.2

# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "rod-pin hole position": "0.20",
    "strap position to hub": "0.10",
    "hub OD position to bore": "0.10",
}
if float(GEOMETRIC_TOLERANCES_MM["strap position to hub"]) != STRAP_HUB_SYMMETRY:
    raise AssertionError("the strap position zone must print STRAP_HUB_SYMMETRY")
if float(GEOMETRIC_TOLERANCES_MM["hub OD position to bore"]) != HUB_COAXIALITY_DIA:
    raise AssertionError("the hub OD position zone must print HUB_COAXIALITY_DIA")
