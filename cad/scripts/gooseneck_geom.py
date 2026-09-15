r"""Gooseneck geometry nominals -- the prose-free import surface for assemblies.

``build_summing_assembly`` needs the post's arm height, arm end face and the
end-screw shank to prove the counter spring's top eye hangs on the screw, but
importing ``build_gooseneck`` for them would fold the whole part build --
including ``gooseneck_spec``'s DRAWING_NOTES prose -- into the summing assembly
recipe (codex #361): a text-only note edit would escalate to a full COM
re-insert of the assembly. Assemblies import this module; ``build_gooseneck``
re-imports the
same constants so the two can never drift.

Part origin is the vertical leg's mid-height. The arm runs toward negative
part X; the summing assembly places it Ry(180), so machine X = COLUMN_X -
part X. Sliding the post sets spring tension, not the part's dimensions.
"""

from __future__ import annotations

TUBE_DIA = 16.0  # DIMENSIONS.md ch19: scaled vs frame anchors (med)
WALL_T = 2.0  # tube wall: O16 x 2.0 WALL tube stock (codex review #361)
ARM_Y = 163.3  # arm/screw axis above the part origin
BEND_R = 51.0  # 90-degree bend centreline radius (med)
ARM_END_X = -101.8  # flat arm-end face; exposed screw runs toward negative X
# The arm END is what makes the counter spring hang plumb in the saved neutral
# pose: the spring's top eye rides the exposed shank's midpoint, so
# spring_mount_geom puts that eye at COLUMN_X - ARM_END_X + SCREW_SHANK_LEN/2 =
# -197 + 101.8 + 4 = -91.2 -- exactly the summing-lever counter anchor's machine
# X (COUNTER_ANCHOR_XY).  Was -95.25, which hung the eye at -97.75 and leaned
# the 351 mm spring 6.55 mm off plumb.  Sliding the post sets tension, never
# this face.
ARM_RUN = -ARM_END_X - BEND_R  # 50.8 (2"): straight run after the bend exit
SCREW_SHANK_DIA = 3.6  # axial #6-32 spring screw envelope
SCREW_SHANK_LEN = 8.0  # exposed shank: end face to head underside
SCREW_HEAD_DIA = 12.0  # approved retention for the 1330K524 double-loop eye
# The former Ø10 head left only 0.2502 mm nominal radial overlap. Ø12 gives
# 1.2502 mm; the summing assembly also checks the loop's axial band and coil
# clearance against this head and the arm end.
SCREW_HEAD_T = 2.0  # head thickness (low)
PLUG_T = 6.0  # end plug capping the bore behind the screw: 6.0 gives the
# #6-32 tap ~7 full threads (a 2.0 cap would hold ~2.5) (derived)
