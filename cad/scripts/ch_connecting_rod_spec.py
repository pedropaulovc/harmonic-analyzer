r"""Connecting-rod dimensional contract -- the single source of truth shared by
the part build (``build_ch_connecting_rod.py``) and its manufacturing drawing
(``draw_ch_connecting_rod.py``).

PURE DATA, no SolidWorks/COM imports (see ``dt_crank_arm_spec`` for the pattern).
The nominal geometry here MUST match the constants in build_ch_connecting_rod.py
(the test cross-checks the load-bearing ones); the marked-dimension -> kept map
is the drift alarm the offline test enforces.
"""

from __future__ import annotations

from _hole_spec import HoleSpec
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

# --- Nominal geometry (DIMENSIONS.md "Chapter 13 - Connecting rods"). ---
CENTER_DISTANCE = 163.1010299795349  # fixed-post recenter; level arm, plumb rod
RING_BORE_DIA = 30.8  # strap bore riding the eccentric cam
RING_BORE_DIA_BAND = (0.10, 0.00)  # running bore; (upper, lower) deviations
RING_WALL = 5.0  # radial strap wall
RING_THICKNESS = 3.0
# The rod print leaves the ring thickness to the title block's 2-place class,
# +/-.02 in (title_block.yaml linear_2pl, pinned by test_cylinder_bank_layout):
# the loosest routine class a shop would read into it. The cylinder bank's
# closed cam slot must hold the thickest such ring (cylinder_bank_layout).
RING_THICKNESS_BAND = (0.508, -0.508)  # (upper, lower) deviations
SHANK_WIDTH = 8.0
SHANK_THICKNESS = 2.5
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
# The flat slot floor (the crotch) below the pin centre. It clears the arm's
# bottom edge (5.533 below the pin) through the +/-9 deg arm-to-rod swing.
FORK_CROTCH_BELOW_PIN = 8.0
FORK_BASE_BELOW_PIN = 11.0  # the fork boss's root step onto the shank
PIN_HOLE_SPEC = HoleSpec("drilled_number", "#47")
# 90-degree countersink on both tine outer faces: the peened pin ends fill
# them (ch_rod_pivot_pin_spec). Printed 3-place: the fill volume is the
# pin blank's upset allowance.
PIN_HOLE_CSK_DIA = 3.2
PIN_HOLE_CSK_BAND = (0.127, -0.127)  # (upper, lower) deviations

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
