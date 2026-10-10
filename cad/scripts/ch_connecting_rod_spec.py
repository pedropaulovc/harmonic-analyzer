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

import channel_frame_geom
import ch_rocker_arm_spec
import dt_cylinder_gear_spec
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

# --- Nominal geometry (DIMENSIONS.md "Chapter 13 - Connecting rods"). ---
# Close the actual phased cam centre to the level rocker's pin. The rocker
# bank is fixed; raising the drive axis changes this physical rod length.
_HOME_PIN_XY = (
    channel_frame_geom.ROCKER_PIVOT_XY[0] - ch_rocker_arm_spec.ROD_HOLE_X,
    channel_frame_geom.ROCKER_PIVOT_XY[1]
    + ch_rocker_arm_spec.ROD_HOLE_Y - ch_rocker_arm_spec.PIVOT_MID_Y,
)
_CAM_PHASE = math.radians(channel_frame_geom.CYLINDER_LOCK_PHASE_DEG)
_HOME_CAM_XY = (
    channel_frame_geom.CAM_SHAFT_XY[0]
    + dt_cylinder_gear_spec.ECCENTRICITY * math.sin(_CAM_PHASE),
    channel_frame_geom.CAM_SHAFT_XY[1]
    + dt_cylinder_gear_spec.ECCENTRICITY * math.cos(_CAM_PHASE),
)
CENTER_DISTANCE = math.dist(_HOME_PIN_XY, _HOME_CAM_XY)
RING_BORE_DIA = 30.8  # strap bore riding the eccentric cam
RING_BORE_DIA_BAND = (0.10, 0.00)  # running bore; (upper, lower) deviations
RING_WALL = 5.0  # radial strap wall
# Ring and shank 2.200 at three places, the title block's +/-.005 in class
# (title_block.yaml linear_3pl; #948 ruling R, PR #1292). Both pass between
# the same two tooth discs of the closed cam slot (cylinder_bank_layout), and
# a flat rod held by its fork on the arm needs the cam-vs-arm offset inside
# its float there: 2.200 at three places widens that float over the old
# 3.00 / 2.50 at two places by geometry, and still leaves a 2.073 section at
# its thinnest (drawing-simplicity rule 12).
RING_THICKNESS = 2.2
RING_THICKNESS_BAND = (0.127, -0.127)  # (upper, lower) deviations
SHANK_WIDTH = 8.0
SHANK_THICKNESS = RING_THICKNESS  # one plate thickness, ring to shank
SHANK_THICKNESS_BAND = RING_THICKNESS_BAND
# Ring and shank symmetric to the fork slot within this (total), so the
# ring's float in the cam slot and the fork's on the arm share a mid-plane.
RING_SLOT_SYMMETRY = 0.10
RULE12_SECTION_MIN = 2.0  # drawing-simplicity policy rule 12
if RING_THICKNESS + RING_THICKNESS_BAND[1] < RULE12_SECTION_MIN:
    raise AssertionError("the rod's thinnest ring/shank section is under rule 12's 2.0")
# --- Fork (the U-shaped clevis straddling the 2.500 +/-0.025 rocker strap). ---
# The rod is flat: ring, shank and fork share one mid-plane (z = 0), the cam
# plane, which is also the arm plane (rocker_bank_layout.ARM_MID_DZ). Two tines
# straddle the arm; the bridge joining them sits below the arm's bottom edge;
# the pin hole runs through both tines on the rod axis at CENTER_DISTANCE.
# Each inter-arm gap (pitch 7.0565 - arm 2.500) holds one tine of each
# neighbouring rod, so the fork's outer thickness and slot carry explicit
# 3-place bands (Main ruling 2026-10, option b): tine 1.59 MIN, 0.35 MIN to
# the neighbouring fork at the worst case (ch_rod_pivot_pin_spec checks both).
FORK_WIDTH = 10.0  # across the fork (X), crown radius FORK_WIDTH / 2 on the pin
FORK_THICKNESS = 6.075  # outer face to outer face (Z)
FORK_THICKNESS_BAND = (0.05, -0.05)  # (upper, lower) deviations
# Slot nominal = the arm's thickest strap (2.525) + the 0.10 running
# floor; the band is one-sided so the slot is never narrower than that.
FORK_SLOT_WIDTH = 2.625
FORK_SLOT_BAND = (0.127, 0.0)  # (upper, lower) deviations
# Slot centred in the fork: the two tines equal within this (|T_n - T_s|).
FORK_TINE_MATCH = 0.10
# The flat slot floor (the crotch) below the pin centre. The arm's curved
# bottom edge dips into the slot as the arm turns on the pin; the floor clears
# it by 1.0 MIN at the printed worst case of both parts through the solved
# swing (ch_rod_pivot_pin_spec.BUDGET: 1.20 worst).
FORK_CROTCH_BELOW_PIN = 9.75
# The fork boss's root step onto the shank. The bridge below the slot floor
# (ForkBossLength less SlotDepth, both .XX from the crown top) keeps 2.0 MIN.
FORK_BASE_BELOW_PIN = 13.0
# The MHA-CH-010 rod pivot pin presses into this hole through both tines and
# runs in the arm's #47 rod hole (user ruling 2026-10-09, PR #1292 review F1,
# press fit as the bar pin; ch_rod_pivot_pin_spec holds the fit budget).
# Reamed to H7 under the 5/64 drill rod: the 0.0775 in stock reamer cuts
# inside the band. No countersink: the reamed hole runs straight through each
# tine, so the tine's whole thickness is the pin's land.
PIN_HOLE_DIA = 1.968
PIN_HOLE_BAND = (0.010, 0.0)  # (upper, lower) deviations, reamed; native

# --- Derived spans (mirror build_ch_connecting_rod). ---
RING_OUTER_RADIUS = RING_BORE_DIA / 2.0 + RING_WALL  # 20.4
FORK_CROWN_RADIUS = FORK_WIDTH / 2.0  # 5.0, centred on the pin
FORK_TOP_Y = CENTER_DISTANCE + FORK_CROWN_RADIUS  # crown top (168.10)
FORK_CROTCH_Y = CENTER_DISTANCE - FORK_CROTCH_BELOW_PIN
FORK_BASE_Y = CENTER_DISTANCE - FORK_BASE_BELOW_PIN
FORK_TINE_THICKNESS = (FORK_THICKNESS - FORK_SLOT_WIDTH) / 2.0  # 1.725 nominal
RING_BOTTOM_Y = -RING_OUTER_RADIUS  # -20.4

SURFACE_FINISHES = (
    SurfaceFinishControl("strap_bore", MACHINED_UM, CylinderFace(RING_BORE_DIA)),
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


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "rocker pin hole position": "0.20",
}
