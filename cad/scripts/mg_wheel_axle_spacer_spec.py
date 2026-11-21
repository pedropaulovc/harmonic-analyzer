r"""Wheel-axle spacer (MHA-MG-11) dimensional contract.

PURE DATA, no SolidWorks/COM and no drawing imports.  A turned brass sleeve
on the 3/16 mg-wheel-axle between the mg-wheel-bar's front face and the
MHA-MG-VN-54 back washer.  It carries the magnifying wheel forward off the bar
until the rim groove's mid-plane lands on the pen-rod line
(``_recording_geometry.PEN_Z_MID``), so the pen wire leaving the groove hangs
plumb onto the pen rod (pn-pen re-derivation, user decision Option C).  Its
length is DERIVED from that line, never a second literal: it is the one part
of the wheel stack that moves with the pen line; the washers and the nuts are
unchanged, and the wheel's spokes stand off its hub's back face
(``mg_magnifying_wheel_geom.HUB_BACK_Z``) so the lever wire clears the rim.

The spacer is not clamped: with the back washer and the wheel it floats on
the shank inside the endshake the nut sets (``mg_wheel_group``).  Nothing
runs on it by design (the wheel's hub runs on the back washer), so neither
face carries a roughness symbol.  MHA-MG-00 presses the pin with the spacer
on its shank and gauges the pin's step from the spacer's outer face (owner
ruling 2026-11-21, fit at assembly), so the length leaves the pin's thread
stack and prints at the title block's .XXX.

Local frame: lathe axis +Z, origin on the axis at the face that bears on the
bar (Front Plane, z = 0, machine z ``BAR_FRONT_Z``); the washer face at
z = LENGTH.  The assembly places it like the washers (local +Z onto machine
-Z), Axis1 the bore axis.
"""

from __future__ import annotations

import _config
import mg_vn_wheel_axle_back_washer_spec as _back
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_deviations
from _surface_finish import SurfaceFinishControl
from mg_magnifying_wheel_geom import HUB_BACK_Z
from mg_wheel_bar_geom import BAR_FRONT_Z
from _recording_geometry import PEN_Z_MID

# #290: the spacer's sheet prints decimal inch.
UNIT = drawing_unit("parts/mg-wheel-axle-spacer", _config.parts("mg-wheel-axle-spacer"))

# Bar face -> spacer -> back washer -> hub back face -> spokes' mid-plane on
# the pen-rod line.
LENGTH = round(BAR_FRONT_Z - PEN_Z_MID - _back.MODEL_THICKNESS - HUB_BACK_Z, 6)
if LENGTH <= 0.0:
    raise AssertionError(f"pen line {PEN_Z_MID} leaves no room for the spacer")
# Owner ruling 2026-11-21 (tight-tolerance audit, row 3): "fit at assembly".
# MHA-MG-00 sets the pin's press depth from this spacer's outer face, so its
# length moves only the wheel's mid-plane off the pen line (by the band) and
# no longer the nut stack; it prints .732 at the title block's .XXX (was
# .731-.733). The length closes the pen line, so it keeps its millimetre
# value and prints rounded at .XXX; the stack reads the printed limits.
LENGTH_PLACES = 3
LENGTH_LIMITS = tuple(
    LENGTH + deviation
    for deviation in printed_deviations(LENGTH, LENGTH_PLACES, unit=UNIT)
)
# Rule 3: a three-place size at the title block names its function. Two lines
# narrower than the 3:1 extension-line span (18.6 x 3 = 55.8 mm).
LENGTH_CALLOUT = (
    f"SETS WHEEL {_config.parts('mg-magnifying-wheel')['number']}\nON THE PEN LINE"
)

# 7/16 bar as supplied (.4375) meets the .44 O.D.: the washer's own O.D.
OD = 11.176  # .44
OD_PLACES = 2
OD_MAX = OD + printed_deviations(OD, OD_PLACES, unit=UNIT)[1]
# A drilled clearance bore on the 3/16 pin (mg_wheel_group proves it passes
# the largest pin): a #10 drill (.1935) in the title block's DRILLED HOLES
# row.
BORE_DIA = 4.9022  # .193
BORE_PLACES = 3
BORE_CALLOUT = "DRILL THRU"
BORE_DIA_MAX = round(BORE_DIA + drilled_oversize_mm(unit=UNIT), 6)

WALL_WORST = (
    OD + printed_deviations(OD, OD_PLACES, unit=UNIT)[0] - BORE_DIA_MAX
) / 2.0  # .111
if WALL_WORST < WALL_TARGET_MM:
    raise AssertionError(f"MHA-MG-11 wall {WALL_WORST / 25.4:.4f} in < .080 target")

# Marked model dimensions and the places the part authors on them
# (drawing-simplicity-policy.md `How the repository implements the
# guidelines`): the length, the O.D. and the
# drilled bore take the title block's rows.
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
