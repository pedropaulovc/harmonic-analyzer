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
_CAM_PHASE = math.radians(channel_frame_geom.CYLINDER_LOCK_PHASE_DEG)
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
# Ring and shank: one plate, .086 thick. Both pass between the same two
# tooth discs of the closed cam slot (cylinder_bank_layout), and a flat rod
# held by its fork on the arm needs the cam-vs-arm offset inside its float
# there (test_channel_axial_budget). The plate's near face prints as a
# location from the fork's datum face (+/-RING_FACE_BAND) and its thickness
# as a size at the ring (+/-RING_THICKNESS_BAND): .084 at its thinnest
# (drawing-guidelines.md rule 17). The two bands spend the same axial window
# the two face ordinates did (#982 review r1: the thickness prints directly).
# .086 puts the near face on a three-place ordinate from the fork face (.077).
RING_THICKNESS = 2.1844  # .086
# .32 (not the .31 nearest 8.0 mm): the shank's half-width is the two BASIC
# datum-B offsets, which print .16 exactly at the sheet's two places.
SHANK_WIDTH = 8.128  # .32
SHANK_THICKNESS = RING_THICKNESS  # one plate thickness, ring to shank
# --- Fork (the U-shaped clevis straddling the 2.500 +/-0.025 mm rocker strap). ---
# The rod is flat: ring, shank and fork share one mid-plane (z = 0), the cam
# plane, which is also the arm plane (rocker_bank_layout.ARM_MID_DZ). Two tines
# straddle the arm; the bridge joining them sits below the arm's bottom edge;
# the pin hole runs through both tines on the rod axis at CENTER_DISTANCE.
# Each inter-arm gap (pitch 7.0565 - arm 2.500) holds one tine of each
# neighbouring rod, so both tines and the slot carry explicit bands (Main
# ruling 2026-10, option b), located from one finished fork face (#982):
# the near tine prints from that face, the slot as a size, the far tine as
# the same tine size (2X), and the fork over the tines as a reference.
# 0.35 mm MIN (running floor plus spare) to the neighbouring fork at the worst case
# (ch_rod_pivot_pin_spec checks it).
FORK_WIDTH = 9.906  # .39 across the fork (X), crown radius FORK_WIDTH / 2 on the pin
# Slot = the arm's thickest strap + the 0.10 running floor at its least,
# centred on its band so the ring-to-slot offset stays even.
FORK_SLOT_WIDTH = 2.6924  # .106
FORK_SLOT_BAND = (0.0508, -0.0508)  # +/-.002; (upper, lower) deviations
# Each tine, outer face to slot wall. The pitch fixes the tine below the
# .080 wall target: .065 at its thinnest (MHA-CH-03 RV-02).
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
# The ring and shank's near face from the fork's datum face (the near tine's
# outer face): the plate centred on the fork.
RING_FACE_NEAR = (FORK_THICKNESS - RING_THICKNESS) / 2.0  # .077
RING_FACE_BAND = (0.0508, -0.0508)  # +/-.002; (upper, lower) deviations
RING_THICKNESS_BAND = (0.0508, -0.0508)  # +/-.002; (upper, lower), at the ring
SHANK_THICKNESS_BAND = RING_THICKNESS_BAND
if RING_THICKNESS + RING_THICKNESS_BAND[1] < WALL_TARGET_MM:
    raise AssertionError("the rod's thinnest ring/shank section is under drawing-guidelines.md rule 17 (walls and webs)'s .080 in")
# The flat slot floor (the crotch) below the pin centre. The arm's curved
# bottom edge dips into the slot as the arm turns on the pin; the floor clears
# it by 1.0 MIN at the printed worst case of both parts through the solved
# swing (ch_rod_pivot_pin_spec.BUDGET). SlotDepth (crown top to floor) prints
# .58.
FORK_CROTCH_BELOW_PIN = 14.732 - FORK_WIDTH / 2.0  # SlotDepth .58
# The fork boss's root step onto the shank. The bridge below the slot floor
# (ForkBossLength less SlotDepth, both .XX from the crown top) keeps .080 MIN.
FORK_BASE_BELOW_PIN = 18.034 - FORK_WIDTH / 2.0  # ForkBossLength .71
# The MHA-CH-10 rod pivot pin presses into this hole through both tines and
# runs in the arm's #47 rod hole (user ruling 2026-10-09, PR #1292 review F1,
# press fit as the bar pin; ch_rod_pivot_pin_spec holds the fit budget).
# Reamed .077 +.0009/+.0005 in under the 5/64 drill rod: a purchased .0775
# chucking reamer cuts inside it. No countersink: the reamed hole runs
# straight through each tine, so the tine's whole thickness is the pin's land.
PIN_HOLE_DIA = 1.9558  # .077 in
PIN_HOLE_BAND = (0.02286, 0.0127)  # (upper, lower) deviations, reamed; native
# Every inside corner -- the slot floor's two, the fork's root step onto the
# shank (four) and the shank onto the ring (two) -- is one modelled fillet,
# inside the title block's INSIDE CORNERS R.040 MAX, which governs them on the
# print (machinist review: a tighter all-corners MAX named no function).
# That ceiling still clears the arm over the slot floor (the offline drawing
# test checks it against ch_rod_pivot_pin_spec), and stays well inside half
# the slot.
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
