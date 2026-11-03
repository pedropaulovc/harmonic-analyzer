r"""Pure pinion-pivot-block geometry consumed by the part, its drawing, the
drive-train assembly and the harmonic base's seat depth.

Keep drawing-only notes and annotation contracts out of this module, so an
edit to the manufacturing sheet's text cannot invalidate the drive-train
assembly or the harmonic base (the pinion_cam_geometry precedent).
"""

from __future__ import annotations

import _config
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
from _cone_axis_constants import AXIS_RAISE_MM

# #290: the registry row's drawing_unit (in) is this sheet's unit; the drive
# train, the rig layout and the base read its printed rows through it.
UNIT = drawing_unit(
    "parts/dt-pinion-pivot-block", _config.parts("dt-pinion-pivot-block")
)

# --- Nominal geometry (cad/DIMENSIONS.md "Chapter 25").
# These drive the part's named equation globals AND the drawing's coordinate
# math.  U28 (user, 2026-09-23) re-laid the block in the photographed order
# (ch25 page002_img07/img08 front pair, read against the annotated 6 mm lever
# rod): from the west end, lift bore | screw | PIVOT bore | screw.  The two
# hold-down screws straddle the pivot bore; the lift bore sits out near the west
# end, 18.5 from the pivot, so the plain (uncut) swing strap clears the eccentric
# lift cam by placement (U12) instead of by a relief.
# Layout: the PIVOT bore is the part origin; the lift bore is at
# (-LIFT_BORE_SPACING, LIFT_BORE_RISE), block x -BLOCK_WEST..+BLOCK_EAST,
# y -BORE_UP..BLOCK_HEIGHT-BORE_UP, z 0..BLOCK_DEPTH.  (Part -X = machine
# WEST: the assembly places the block mirrored.)  #290: the envelope and the
# hold-down stations snap to the .XX grid the sheet prints; the bore height
# (the drum axis, raised with the bank) keeps its millimetre nominal and prints
# .XX; the lift bore's spacing and rise (the cam park-gap closure) keep theirs
# and print at .XXX. ---
BLOCK_EAST = 13.97  # .55; pivot bore -> east end: 3.0 web past the east screw hole
BLOCK_WEST = 25.908  # 1.02; pivot bore -> west end: 4.3 web past the lift bore
BLOCK_WIDTH = BLOCK_EAST + BLOCK_WEST  # 1.57 (photo ~38-41 mm)
# The complete bore/top envelope, raised with the bank (20.5 + AXIS_RAISE_MM),
# snapped to the nearest .XX the sheet prints (.99 today).
BLOCK_HEIGHT = round(round((20.5 + AXIS_RAISE_MM) / 25.4, 2) * 25.4, 9)
BLOCK_HEIGHT_BAND = printed_band_mm(2, unit=UNIT)  # BlockHeight prints .XX
BLOCK_DEPTH = 11.176  # .44; U28: 12 -> 10.25; ruling (c) then put the back strap hard
# on this block and pinion_rig_layout sizes the shafts from the worst stack.
# Option E-a (Main, Codex #858): the strap-pinned torque shaft retreats up to
# the widest feeler setting (0.35) into the back block, so the shallowest
# printed block (depth - .XX row) must still bear the 9.5 floor: 10.25 bore
# 9.39, and 10.5 only 9.54 once the shaft's flush setting was booked.  Main
# (#858) asked for a real margin, >= 0.5 over the floor with the bands kept,
# so the depth grew to 11.0, outward from both block faces the cluster sits
# against, so the cluster and its drilled stations stay put
# (pinion_rig_layout).  #290: .44, whose half (.22) is the hold-down holes'
# printed depth station, leaves 10.47 worst at the inch .XX row.
# Depth prints .XX (dt_pinion_pivot_block_spec.DRAWING_PRECISION), and the
# rig's worst fitted stack reads that printed row (Main, Codex #854 P1;
# test_dt_pinion_pivot_block_drawing pins the two together).
BLOCK_DEPTH_PLACES = 2
BLOCK_DEPTH_BAND = printed_band_mm(BLOCK_DEPTH_PLACES, unit=UNIT)  # .01 in
BORE_UP = 12.0 + AXIS_RAISE_MM
BORE_DIA = 6.35  # 1/4 in: rides the Ø6.35 torque shaft / lift rod (derived)
LIFT_BORE_SPACING = 18.5  # pivot -> lift bore, horizontal (photo ~16-17): the
# eccentric collar (Ø14.6, ecc 2.0) orbits the lift axis and must clear the
# strap's R7.5 pivot end cap over the whole engage throw -- 1.83 of air
# nominal, 0.38 at the printed worst case (build_dt_drive_train_assembly)
LIFT_BORE_RISE = 2.16  # lift bore above the pivot bore: the ecc-down collar
# hovers 0.153 under the follower stud 7 above the pivot (re-proven at import
# by build_dt_drive_train_assembly's park-gap band)
SCREW_HALF_SPACING = 8.382  # .33; hold-down holes about the pivot bore:
# 2.7 web to the pivot bore, 4.8 to the lift bore
SCREW_HOLE_SPEC = HoleSpec("clearance", "#8")
SCREW_HOLE_DIA = blind_cut_dia_mm(SCREW_HOLE_SPEC)

# Derived spans (equations of the primitives above).
BLOCK_TOP_Y = BLOCK_HEIGHT - BORE_UP  # +8.5: block top above the pivot axis
BLOCK_BOTTOM_Y = -BORE_UP  # the base seat
FRONT_BBOX_CX = (BLOCK_EAST - BLOCK_WEST) / 2.0
FRONT_BBOX_CY = (BLOCK_TOP_Y + BLOCK_BOTTOM_Y) / 2.0
SCREW_SPACING = 2.0 * SCREW_HALF_SPACING  # 17.0
