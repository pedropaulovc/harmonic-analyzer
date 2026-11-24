r"""Connecting-rod dimensional contract -- the single source of truth shared by
the part build (``build_ch_connecting_rod.py``) and its manufacturing drawing
(``draw_ch_connecting_rod.py``).

PURE DATA, no SolidWorks/COM imports (see ``dt_crank_arm_spec`` for the pattern).
The nominal geometry here MUST match the constants in build_ch_connecting_rod.py
(the test cross-checks the load-bearing ones); the marked-dimension -> kept map
is the drift alarm the offline test enforces.
"""

from __future__ import annotations

import math

import _config
import channel_frame_geom
import _rocker_interface as rocker_interface
import dt_cylinder_gear_spec
from _gtol_cylinder import CylinderFace
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl

# #290: the registry row's drawing_unit (in) is this sheet's unit. Lengths
# stay physical millimetres, each the exact decimal of its printed inch value;
# the centre distance is the kinematic closure and stays exact.
UNIT = drawing_unit("parts/ch-connecting-rod", _config.parts("ch-connecting-rod"))

# --- Nominal geometry (DIMENSIONS.md "Chapter 13 - Connecting rods"). ---
# Close the actual phased cam centre to the level rocker's pin. The rocker
# bank is fixed; raising the drive axis changes this physical rod length.
_HOME_PIN_XY = (
    channel_frame_geom.ROCKER_PIVOT_XY[0] - rocker_interface.ROD_HOLE_X,
    channel_frame_geom.ROCKER_PIVOT_XY[1]
    + rocker_interface.ROD_HOLE_Y - rocker_interface.PIVOT_MID_Y,
)
_CAM_PHASE = math.radians(channel_frame_geom.CAM_HOME_PHASE_DEG)
_HOME_CAM_XY = (
    channel_frame_geom.CAM_SHAFT_XY[0]
    + dt_cylinder_gear_spec.ECCENTRICITY * math.sin(_CAM_PHASE),
    channel_frame_geom.CAM_SHAFT_XY[1]
    + dt_cylinder_gear_spec.ECCENTRICITY * math.cos(_CAM_PHASE),
)
CENTER_DISTANCE = math.dist(_HOME_PIN_XY, _HOME_CAM_XY)
RING_BORE_DIA = 30.8102  # 1.213: strap bore riding the eccentric cam
RING_BORE_DIA_BAND = (0.0762, 0.0)  # +.003/.000 running bore; (upper, lower)
# The bore runs on the cylinder gear's integral eccentric cam (MHA-DT-12):
# (least, most) diametral clearance over both printed bands.
STRAP_DIAMETRAL_CLEARANCE = (
    RING_BORE_DIA + RING_BORE_DIA_BAND[1]
    - (dt_cylinder_gear_spec.CAM_DIA + dt_cylinder_gear_spec.CAM_DIA_BAND[0]),
    RING_BORE_DIA + RING_BORE_DIA_BAND[0]
    - (dt_cylinder_gear_spec.CAM_DIA + dt_cylinder_gear_spec.CAM_DIA_BAND[1]),
)
# Ring OD 1.61 over the bore: the radial strap wall follows from the two.
RING_OUTER_DIA = 40.894  # 1.61
RING_WALL = (RING_OUTER_DIA - RING_BORE_DIA) / 2.0  # radial strap wall
# Ring and shank at the original's proportions (owner ruling 2026-11-18,
# #3114; references ch13 page001_img02: the ring nearly fills the gap between
# neighbouring gears): the ring .170 thick, the shank stepped down to .13 on
# both faces (the photo reads it about .138; .13 is the two-place size whose
# title-block band stays inside the ring). Both pass between the same two tooth discs of the closed cam
# slot (cylinder_bank_layout), and the slot locates the rod along the bank:
# the ring slides between the two discs, and the fork carries its rocker arm
# with it (the arm floats on the pivot shaft, test_channel_axial_budget).
# The ring's near face prints as a location from the fork's datum face
# (+/-RING_FACE_BAND) and its thickness as a size at the ring
# (+/-RING_THICKNESS_BAND). .170 puts the near face on a three-place
# ordinate from the fork face (.035).
RING_THICKNESS = 4.318  # .170
# .32 (not the .31 nearest 8.0 mm): the shank's half-width is the two BASIC
# datum-B offsets, which print .16 exactly at the sheet's two places.
SHANK_WIDTH = 8.128  # .32
SHANK_THICKNESS = 3.302  # .13
# --- Fork (the U-shaped clevis straddling the .098 +/-.001 rocker strap). ---
# The rod is flat: ring, shank and fork share one mid-plane (z = 0), the cam
# plane, which is also the arm plane (rocker_bank_layout.ARM_MID_DZ). Two tines
# straddle the arm; the bridge joining them sits below the arm's bottom edge;
# the pin hole runs through both tines on the rod axis at CENTER_DISTANCE.
# Each gap between neighbouring straps holds one tine of each neighbouring
# rod, so both tines and the slot carry explicit bands (Main ruling 2026-10,
# option b), located from one finished fork face (#982): the near tine prints
# from that face, the slot as a size, the far tine as the same tine size
# (2X), and the fork over the tines as a reference. The arms float on the
# pivot shaft (#3114), so that gap is judged with two neighbours closed up
# hub on hub: 0.35 mm MIN (running floor plus spare) to the neighbouring
# fork at the worst case (sh_vn_pivot_pin_rod_spec checks it).
FORK_WIDTH = 9.906  # .39 across the fork (X), crown radius FORK_WIDTH / 2 on the pin
# Slot = the arm's thickest strap + the 0.10 running floor at its least,
# centred on its band so the ring-to-slot offset stays even.
FORK_SLOT_WIDTH = 2.6924  # .106
FORK_SLOT_BAND = (0.0508, -0.0508)  # +/-.002; (upper, lower) deviations
# Each tine, outer face to slot wall. The gap between neighbouring straps
# fixes the tine below the .080 wall target: .065 at its thinnest (MHA-CH-03
# RV-02).
TINE_THICKNESS = 1.7018  # .067
TINE_BAND = (0.0508, -0.0508)  # +/-.002; (upper, lower) deviations
TINE_MIN = TINE_THICKNESS + TINE_BAND[1]
FORK_THICKNESS = 6.096  # .240 outer face to outer face (Z): two tines and the slot
if not math.isclose(FORK_THICKNESS, 2.0 * TINE_THICKNESS + FORK_SLOT_WIDTH):
    raise AssertionError("the fork is its two tines and its slot")
# The reference fork thickness's worst-case spread: two tines and the slot.
FORK_THICKNESS_BAND = (
    2.0 * TINE_BAND[0] + FORK_SLOT_BAND[0],
    2.0 * TINE_BAND[1] + FORK_SLOT_BAND[1],
)
# The ring's near face from the fork's datum face (the near tine's outer
# face): the ring centred on the fork.
RING_FACE_NEAR = (FORK_THICKNESS - RING_THICKNESS) / 2.0  # .035
RING_FACE_BAND = (0.0508, -0.0508)  # +/-.002; (upper, lower) deviations
RING_THICKNESS_BAND = (0.0508, -0.0508)  # +/-.002; (upper, lower), at the ring
# The shank's near face from the same datum face, and its thickness: both at
# the title block's .XX (machinist review: a third place there served no
# function). .05 and .13 are the two-place pair whose bands leave neither
# shank face proud of its ring face, so the ring alone meets the tooth
# discs; the shank's mid-plane then stands .005 off the ring's, toward the
# datum face.
SHANK_FACE_NEAR = 1.27  # .05
_LINEAR_2PL = printed_band_mm(2, unit=UNIT)
SHANK_FACE_BAND = (_LINEAR_2PL, -_LINEAR_2PL)
SHANK_THICKNESS_BAND = (_LINEAR_2PL, -_LINEAR_2PL)
# (near, far) least step from each ring face down to its shank face.
SHANK_INSIDE_RING_MIN = (
    SHANK_FACE_NEAR + SHANK_FACE_BAND[1] - (RING_FACE_NEAR + RING_FACE_BAND[0]),
    RING_FACE_NEAR + RING_FACE_BAND[1] + RING_THICKNESS + RING_THICKNESS_BAND[1]
    - (SHANK_FACE_NEAR + SHANK_FACE_BAND[0] + SHANK_THICKNESS + SHANK_THICKNESS_BAND[0]),
)
if min(SHANK_INSIDE_RING_MIN) <= 0.0:
    raise AssertionError("a shank face can stand proud of its ring face")
if SHANK_THICKNESS + SHANK_THICKNESS_BAND[1] < WALL_TARGET_MM:
    raise AssertionError("the rod's thinnest ring/shank section is under drawing-guidelines.md rule 17 (walls and webs)'s .080 in")
# The flat slot floor (the crotch) below the pin centre. The arm's curved
# bottom edge dips into the slot as the arm turns on the pin; the floor clears
# it by 1.0 MIN at the printed worst case of both parts through the solved
# swing (sh_vn_pivot_pin_rod_spec.BUDGET). SlotDepth (crown top to floor) prints
# .58.
FORK_CROTCH_BELOW_PIN = 14.732 - FORK_WIDTH / 2.0  # SlotDepth .58
# The fork boss's root step onto the shank. The bridge below the slot floor
# (ForkBossLength less SlotDepth, both .XX from the crown top) keeps .080 MIN.
FORK_BASE_BELOW_PIN = 18.034 - FORK_WIDTH / 2.0  # ForkBossLength .71
# The MHA-SH-VN-58 rod pivot pin presses into this hole through both tines and
# runs in the arm's #47 rod hole (user ruling 2026-10-09, PR #1292 review F1,
# press fit as the bar pin; sh_vn_pivot_pin_rod_spec holds the fit budget).
# Owner ruling 2026-11-24, fit audit question 3: reamed with the .0775 reamer
# and printed with no band, the pin itself the gauge (it presses in, it does
# not enter by hand); a pin that enters by hand is bonded at MHA-CH-00. The
# model sits at the reamer's size, which the sheet prints; PIN_HOLE_LIMITS is
# the ANALYSIS band, what the reamer is modelled to cut
# (sh_vn_pivot_pin_spec.HOLE_REAMED_LIMITS), not a printed limit. No
# countersink: the reamed hole runs straight through each tine, so the
# tine's whole thickness is the pin's land.
PIN_HOLE_LIMITS = (1.9685, 1.97866)  # .0775-.0779 in, the reamer's cut
PIN_HOLE_DIA = 1.9685  # .0775 in, the reamer
if PIN_HOLE_DIA != PIN_HOLE_LIMITS[0]:
    raise AssertionError("the pin hole's model must be its reamer's size")
# Every other inside corner a radius this size can seat in -- the slot
# floor's two and the two ledges where the shank's faces meet the fork's root
# step -- is one modelled fillet, inside the title block's INSIDE CORNERS
# R.040 MAX, which governs them on the print (machinist review: a tighter
# all-corners MAX named no function). The shank's four corners onto the
# ring's OD and the fork's step keep the 1/8 in end mill's radius and print
# their own R.065 (owner ruling 2026-11-23, tool audit Q9;
# ch_connecting_rod_notes.SHANK_CORNER_R). The two corners where a shank
# face meets the ring's OD are modelled sharp under the title block's MAX:
# the ring stands .015 over the shank's near face, less than this radius,
# and .025 over its far face at nominal only
# (build_ch_connecting_rod.RING_STEPS). That ceiling still clears the arm over
# the slot floor (the offline drawing test checks it against
# sh_vn_pivot_pin_rod_spec), and stays well inside half the slot.
INSIDE_CORNER_R = 0.5  # model only, never printed
if 2.0 * INSIDE_CORNER_R >= FORK_SLOT_WIDTH + FORK_SLOT_BAND[1]:
    raise AssertionError("the slot floor's corner radii meet across the slot")

# --- Derived spans (mirror build_ch_connecting_rod). ---
RING_OUTER_RADIUS = RING_OUTER_DIA / 2.0
FORK_CROWN_RADIUS = FORK_WIDTH / 2.0  # centred on the pin
FORK_TOP_Y = CENTER_DISTANCE + FORK_CROWN_RADIUS  # crown top
FORK_CROTCH_Y = CENTER_DISTANCE - FORK_CROTCH_BELOW_PIN
FORK_BASE_Y = CENTER_DISTANCE - FORK_BASE_BELOW_PIN
RING_BOTTOM_Y = -RING_OUTER_RADIUS

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "strap_bore", MACHINED_UM, CylinderFace(RING_BORE_DIA), display_unit=UNIT
    ),
)


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  build_ch_connecting_rod marks exactly these; draw_ch_connecting_rod
# keeps exactly their union across its per-view ``keep`` maps. ---
# The marked-dimension contract moved to ``ch_connecting_rod_notes`` with the rest
# of the drawing-only data (codex #354): it changes for drawing-only mark/keep
# updates, and ``build_ch_channel_assembly`` imports this module.

# Drawing prose (DRAWING_NOTES / ISOMETRIC_VIEW_NOTE) lives in
# ch_connecting_rod_notes.py so assemblies importing this spec never inherit a
# notes edit into their rebuild closure (codex #354).


# Manufacturing GD&T limits: the sheet prints the inch text, the budgets read
# the derived millimetre zone.
GEOMETRIC_TOLERANCES_IN: dict[str, str] = {
    "rocker pin hole position": ".008",
}
GEOMETRIC_TOLERANCES_MM: dict[str, float] = {
    key: float(value) * 25.4 for key, value in GEOMETRIC_TOLERANCES_IN.items()
}
