r"""Gooseneck geometry nominals -- the prose-free import surface for assemblies.

``build_summing_assembly`` needs the post's arm height, arm end face and the
end-screw shank to prove the counter spring's top eye hangs on the screw, but
importing ``build_gooseneck`` for them would fold the whole part build --
including ``gooseneck_spec``'s DRAWING_NOTES prose -- into the summing assembly
recipe (codex #361, the same closure leak ``boss_hook_geom`` fixes for the
hook): a text-only note edit would escalate to a full COM re-insert of the
assembly.  Assemblies import THIS module; ``build_gooseneck`` re-imports the
same constants so the two can never drift.

Part frame: origin at the vertical leg's mid-height (machine (197, 1210, 0));
the arm runs toward NEGATIVE part x and the assembly places the part Ry(180),
so machine x = COLUMN_X - part x.
"""

from __future__ import annotations

TUBE_DIA = 16.0  # DIMENSIONS.md ch19: scaled vs frame anchors (med)
WALL_T = 2.0  # tube wall: O16 x 2.0 WALL tube stock (codex review #361)
ARM_Y = 163.3  # arm centreline = machine 1373.3: the end screw runs on the tube
# axis, so the arm height IS the spring hang -- eye centre 1370.7 (coil-bottom
# origin 1041.8 + body 325.3 + top lead 3.6) + eye inner radius 4.45 - shank
# radius 1.8 - 0.05 air gap (derived; was 1386 when a lug hung under the arm)
ARM_END_X = -95.25  # arm end face = machine 101.75: the eye centre (machine 95)
# sits 6.75 in from the end face -- the coil's O12.5 body, hanging under the
# eye, clears the end face by 0.5 (the coil top 1367.1 rises above the tube
# underside 1365.3, so the clearance has to come from x) -- and 1.25 from the
# head shoulder (wire band 0.9 -> 0.35 air) (derived)
SCREW_SHANK_DIA = 3.6  # book p.45 "slotted screw" in the tube end (low)
SCREW_SHANK_LEN = 8.0  # EXPOSED shank, end face to head underside (low)
SCREW_HEAD_DIA = 10.0  # slotted round head (low): wider than the eye's 8.9
# inner diameter so the head RETAINS a slack eye (the p.45 photo reads the
# head at ~0.8x the tube OD, so O10 is the conservative end of that read);
# its underside (axis - 5.0 = 1368.3) clears the coil's top wire (1368.0)
# by 0.3 where the two overlap in x (build_summing_assembly proves it)
SCREW_HEAD_T = 2.0  # head thickness (low)
SCREW_SLOT_W = 0.8  # p.45 axial end view: diagonal driver slot width (low)
SCREW_SLOT_D = 0.8  # matching depth documented on the gooseneck print (low)
SCREW_SLOT_ANGLE_DEG = 45.0  # diagonal across the outer head face, not axis-aligned
PLUG_T = 6.0  # end plug capping the bore behind the screw: 6.0 gives the
# #6-32 tap ~7 full threads (a 2.0 cap would hold ~2.5) (derived)
