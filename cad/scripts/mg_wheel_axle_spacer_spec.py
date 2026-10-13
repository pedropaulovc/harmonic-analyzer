r"""Wheel-axle spacer (MHA-MG-011) dimensional contract.

PURE DATA, no SolidWorks/COM and no drawing imports.  A turned brass sleeve
on the 3/16 mg-wheel-axle between the mg-wheel-bar's front face and the
MHA-VN-057 back washer.  It carries the magnifying wheel forward off the bar
until the rim groove's mid-plane lands on the pen-rod line
(``paper_drive_geom.PEN_Z_MID``), so the pen wire leaving the groove hangs
plumb onto the pen rod (pn-pen re-derivation, user decision Option C).  Its
length is DERIVED from that line, never a second literal: it is the one part
of the wheel stack that moves with the pen line; the washers and the nuts are
unchanged, and the wheel's spokes sit 4.09 off its hub's back face
(``mg_magnifying_wheel_geom.HUB_BACK_Z``) so the lever wire clears the rim.

The spacer is not clamped: with the back washer and the wheel it floats on
the shank inside the endshake the nut sets (``mg_wheel_group``).  Nothing
runs on it by design (the wheel's hub runs on the back washer), so neither
face carries a roughness symbol.  Its length places the hub on the pin and so
enters the pin's thread stack, hence its explicit band.

Local frame: lathe axis +Z, origin on the axis at the face that bears on the
bar (Front Plane, z = 0, machine z ``BAR_FRONT_Z``); the washer face at
z = LENGTH.  The assembly places it like the washers (local +Z onto machine
-Z), Axis1 the bore axis.
"""

from __future__ import annotations

import math

import vn_wheel_axle_back_washer_spec as _back
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from _surface_finish import SurfaceFinishControl
from mg_magnifying_wheel_geom import HUB_BACK_Z
from mg_wheel_bar_geom import BAR_FRONT_Z
from paper_drive_geom import PEN_Z_MID

# Bar face -> spacer -> back washer -> hub back face -> spokes' mid-plane on
# the pen-rod line.
LENGTH = round(BAR_FRONT_Z - PEN_Z_MID - _back.MODEL_THICKNESS - HUB_BACK_Z, 6)
if LENGTH <= 0.0:
    raise AssertionError(f"pen line {PEN_Z_MID} leaves no room for the spacer")
# The axle's shank grows by this length and prints at .X
# (mg_wheel_axle_spec.SHANK_LEN), so the length must sit on the 0.1 grid: keep
# PEN_Z_MID there too.
if not math.isclose(LENGTH * 10.0, round(LENGTH * 10.0), abs_tol=1e-6):
    raise AssertionError(f"spacer length {LENGTH} is off the 0.1 grid")
# It moves the hub, and so the nut stack, along the pin: the thread length
# that keeps the locknut on full thread (mg_wheel_group) spends this band.
LENGTH_BAND = 0.03
LENGTH_PLACES = 2
LENGTH_CALLOUT = "SETS WHEEL STACK ON\nMG-WHEEL-AXLE THREAD"

# 7/16 bar as supplied (11.11) meets the .X O.D.: the washer's own O.D.
OD = 11.0
OD_PLACES = 1
# A drilled clearance bore on the 3/16 pin (mg_wheel_group proves it passes
# the largest pin); the title block's DRILLED HOLES row governs it.
BORE_DIA = 4.9
BORE_PLACES = 2
BORE_CALLOUT = "DRILL THRU"
BORE_DIA_MAX = round(BORE_DIA + drilled_oversize_mm(), 6)

MIN_WALL = 2.0  # drawing-guidelines.md rule 17 (walls and webs) target
WALL_WORST = (OD - printed_band_mm(OD_PLACES) - BORE_DIA_MAX) / 2.0  # 2.6
if WALL_WORST < MIN_WALL:
    raise AssertionError(f"MHA-MG-011 wall {WALL_WORST:.3f} < {MIN_WALL}")

# Marked model dimensions and the places the part authors on them
# (drawing-simplicity-policy.md `How the repository implements the
# guidelines`): the length carries LENGTH_BAND on its model dimension; the
# O.D. and the drilled bore take the title block's rows.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"SpacerOd", "SpacerBore"},
    "Spacer": {"SpacerLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"SpacerOd": OD_PLACES, "SpacerBore": BORE_PLACES},
    "Spacer": {"SpacerLength": LENGTH_PLACES},
}

# drawing-guidelines.md rule 6 (roughness symbols only where a surface runs,
# slides or locates): the hub runs on the back washer, not on this sleeve.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()
