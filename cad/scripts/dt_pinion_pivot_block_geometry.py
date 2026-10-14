r"""Pure pinion-pivot-block geometry consumed by the part, its drawing, the
drive-train assembly and the harmonic base's seat depth.

Keep drawing-only notes and annotation contracts out of this module, so an
edit to the manufacturing sheet's text cannot invalidate the drive-train
assembly or the harmonic base (the pinion_cam_geometry precedent).
"""

from __future__ import annotations

from _hole_spec import HoleSpec, blind_cut_dia_mm
from _inch import inch
from _printed_tolerance import printed_band_mm

# --- Nominal geometry (cad/DIMENSIONS.md "Chapter 25").
# These drive the part's named equation globals AND the drawing's coordinate
# math.  U28 (user, 2026-09-23) re-laid the block in the photographed order
# (ch25 page002_img07/img08 front pair, read against the annotated 6 mm lever
# rod): from the west end, lift bore | screw | PIVOT bore | screw.  The two
# hold-down screws straddle the pivot bore; the lift bore sits out near the west
# end, 3/4 in from the pivot, so the plain (uncut) swing strap clears the eccentric
# lift cam by placement (U12) instead of by a relief.
# Layout: the PIVOT bore is the part origin; the lift bore is at
# (-LIFT_BORE_SPACING, LIFT_BORE_RISE), block x -BLOCK_WEST..+BLOCK_EAST,
# y -BORE_UP..BLOCK_HEIGHT-BORE_UP, z 0..BLOCK_DEPTH.  (Part -X = machine
# WEST: the assembly places the block mirrored.) ---
BLOCK_EAST = inch(9, 16)  # pivot bore -> east end: 3.1 web past the east screw hole
# Pivot bore -> west end: 4.8 web past the lift bore.  All-inch: 1 in (the
# nearest 1/16) left a 3.18 web, more than 25% off the 4.3 it had, so the
# next fraction up, which also makes the width a stock 1-5/8 in bar.
BLOCK_WEST = inch(17, 16)
BLOCK_WIDTH = BLOCK_EAST + BLOCK_WEST  # 1-5/8 in, 41.28 (photo ~38-41)
# All-inch: 1 in bar.  The bank's common raise (dt_post_mount_stack.AXIS_RAISE_MM)
# had made it 20.5 + 4.732; the top now stands 8.73 above the pivot.
BLOCK_HEIGHT = inch(1)
BLOCK_HEIGHT_BAND = printed_band_mm(2)  # BlockHeight prints .XX
BLOCK_DEPTH = inch(7, 16)  # U28: 12 -> 10.25; ruling (c) then put the back strap hard
# on this block and pinion_rig_layout sizes the shafts from the worst stack.
# Option E-a (Main, Codex #858): the strap-pinned torque shaft retreats up to
# the widest feeler setting (0.35) into the back block, so the shallowest
# printed block (depth - .XX row) must still bear the 9.5 floor: 10.25 bore
# 9.39, and 10.5 only 9.54 once the shaft's flush setting was booked.  Main
# (#858) asked for a real margin, >= 0.5 over the floor with the bands kept,
# so the depth grew to 11.0 (10.04 worst), outward from both block faces the
# cluster sits against, so the cluster and its drilled stations stay put
# (pinion_rig_layout).  All-inch: 7/16 in (10.15 worst).
# Depth prints at the drawing document's two places: MHA-DT-018's sheet is not
# precision-migrated (_drawing_contract), so the title block's .XX row governs
# it, and the rig's worst fitted stack reads that printed row (Main, Codex #854
# P1).  Migrating the sheet means stating these places natively; the band
# follows (test_dt_pinion_pivot_block_drawing pins the two together).
BLOCK_DEPTH_PLACES = 2
BLOCK_DEPTH_BAND = printed_band_mm(BLOCK_DEPTH_PLACES)  # 0.51
# All-inch: the pivot bore stands 21/32 in over the base (12.0 + the 4.732 raise
# had made it 16.732).  1/32 because the pivot height sets the strap's parked
# lean through its c2c (pinion_rig_park_geometry): 5/8 stands the strap
# vertical and 11/16 leans it twice as far.
BORE_UP = inch(21, 32)
BORE_DIA = 6.35  # 1/4 in: rides the Ø6.35 torque shaft / lift rod (derived)
LIFT_BORE_SPACING = inch(3, 4)  # pivot -> lift bore, horizontal (photo ~16-17): the
# eccentric collar orbits the lift axis and must clear the strap's pivot end
# cap over the whole engage throw (build_dt_drive_train_assembly)
# Lift bore above the pivot bore: the ecc-down collar hovers under the
# follower stud above the pivot (re-proven at import by
# build_dt_drive_train_assembly's park-gap band).  1/32: 1/16 moved it 26%.
LIFT_BORE_RISE = inch(3, 32)
# Hold-down holes about the pivot bore (11/16 in apart): 3.1 web (2.5 worst)
# to the pivot bore, 4.7 to the lift bore.  1/32: 5/16 left the pivot-bore web
# under 2.0 at its worst case, and 3/8 cut the east-end web by a quarter.
SCREW_HALF_SPACING = inch(11, 32)
SCREW_HOLE_SPEC = HoleSpec("clearance", "#8")
SCREW_HOLE_DIA = blind_cut_dia_mm(SCREW_HOLE_SPEC)

# Derived spans (equations of the primitives above).
BLOCK_TOP_Y = BLOCK_HEIGHT - BORE_UP  # +8.73: block top above the pivot axis
BLOCK_BOTTOM_Y = -BORE_UP  # the base seat
FRONT_BBOX_CX = (BLOCK_EAST - BLOCK_WEST) / 2.0
FRONT_BBOX_CY = (BLOCK_TOP_Y + BLOCK_BOTTOM_Y) / 2.0
SCREW_SPACING = 2.0 * SCREW_HALF_SPACING  # 11/16 in, 17.46
