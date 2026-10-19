"""Recording paper and pen anchors, independent of feed-law checks."""

from __future__ import annotations

import math

import pd_platen_spec as platen
import pd_latch_hook_geometry as hook
from _column_clamp_interface import BAR_DEPTH
import mg_wheel_bar_geom
from _mg_wheel_rim_geometry import RIM_WIRE_R

# Actual recording geometry, shared with the paper and pen native builders.
# These are source anchors, not a reduced paper stroke or nominal-only gate.
RECORDING_PAPER_WIDTH_MM = 233.2386
RECORDING_PAPER_HEIGHT_MM = 80.5
# Machine -X edge of the platen to the paper's -X edge. The sheet sits as close
# to centred between the brass edge clips as the finite rack allows: the pen
# nib (PEN_NIB_X_MM, set by the CG-balanced rod line) lies 15.2 to -X of the
# feed stud, so a centred sheet (18.2007 each side) would sweep its far edge
# past the rack's engaged-feed window. This is the largest 0.1-grid inset that
# keeps the full located sweep >= 1.0 inside that window
# (test_paper_drive_rack_travel asserts both the margin and the grid optimum;
# the window comes from pd_paper_drive_assembly_steps).
RECORDING_PAPER_LEFT_INSET_MM = 14.6
RECORDING_PAPER_RIGHT_INSET_MM = (
    platen.PLATE_WIDTH - RECORDING_PAPER_WIDTH_MM - RECORDING_PAPER_LEFT_INSET_MM
)
PAPER_FRONT_Z = (
    hook.BAR_BACK_FACE_Z - BAR_DEPTH - platen.PLATE_THICKNESS - 0.5
)
# The pen rod line. x: plumb under the magnifying wheel's rim-tangent wire (the
# wire hangs from the rim groove's 3 o'clock point straight onto the adjuster
# stud eye on the rod axis). z: the paper-most 0.1-grid line on which the pen
# stirrup's paper-side corner still stands 2 x 0.25 off the paper with the
# v-block's pivot bore where the CG balance puts it (pn_pen_carriage_geom;
# test_pn_pen_carriage_geom asserts both). The magnifying wheel's rim plane
# derives from it (mg_wheel_group.WHEEL_MID_Z).
PEN_ROD_X = round(mg_wheel_bar_geom.WHEEL_X - RIM_WIRE_R, 6)
PEN_Z_MID = -162.5
PEN_BLOCK_YAW_DEG = 45.0
PEN_PAPER_CLEARANCE_MM = 0.25
PEN_NIB_X_MM = PEN_ROD_X - math.tan(math.radians(PEN_BLOCK_YAW_DEG)) * (
    PAPER_FRONT_Z - PEN_PAPER_CLEARANCE_MM - PEN_Z_MID
)
