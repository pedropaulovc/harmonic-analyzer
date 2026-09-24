r"""Gooseneck geometry nominals -- the prose-free import surface for assemblies.

``build_summing_assembly`` needs the post's arm height, arm end face and the
end-screw shank to prove the counter spring's top eye hangs on the screw, but
importing ``build_gooseneck`` for them would fold the whole part build --
including ``gooseneck_spec``'s DRAWING_NOTES prose -- into the summing assembly
recipe (codex #361): a text-only note edit would escalate to a full COM
re-insert of the assembly. Assemblies import this module; ``build_gooseneck``
re-imports the same constants so the two can never drift.

Part origin is the vertical leg's mid-height. The arm runs toward negative
part X; the summing assembly places it Ry(180), so machine X = COLUMN_X -
part X. Sliding the post sets spring tension, not the part's dimensions.
"""

from __future__ import annotations

from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM

TUBE_DIA = 16.0  # DIMENSIONS.md ch19: scaled vs frame anchors (med)
WALL_T = 2.0  # tube wall: O16 x 2.0 WALL tube stock (codex review #361)
ARM_Y = 163.3  # arm/screw axis above the part origin
BEND_R = 51.0  # 90-degree bend centreline radius (med)
ARM_END_X = -101.8  # flat arm-end face; exposed screw runs toward negative X
# The saved/default assembly pose clamps the MHA-019 end band between the screw
# head and arm end.  The open 8 mm gap is installation access, not the spring's
# calibrated running position.  Assembly placement consumes the canonical
# derived eye centre below so its spring axis follows this clamped default.
ARM_RUN = -ARM_END_X - BEND_R  # 50.8 (2"): straight run after the bend exit
SCREW_SHANK_DIA = 3.6  # conservative external envelope used by assembly checks
SCREW_THREAD_MAJOR_DIA = THREAD_MAJOR_MM["#6-32"]
SPRING_SCREW_OPEN_GAP_MM = 8.0
# Native clamp calibration (verify:calibrate_summing_clamp, run
# 20260923T001401277Z-691cdb38; neutral/square mean, spread 4e-5 mm). The
# 1330K524 end loop is widest outside the tube OD, so it seats on the tube end's
# OD corner, 0.231 mm past the full-band position, and the head closes onto it.
SPRING_SCREW_CLAMPED_GAP_MM = 4.616832947108421
SPRING_SCREW_TRAVEL_MM = SPRING_SCREW_OPEN_GAP_MM - SPRING_SCREW_CLAMPED_GAP_MM
SPRING_EYE_CENTRE_FROM_ARM_END_MM = 2.2090440562497236
SCREW_HEAD_DIA = 12.0  # approved retention for the 1330K524 double-loop eye
# The former Ø10 head left only 0.2502 mm nominal radial overlap. Ø12 gives
# 1.2502 mm; the summing assembly also checks the loop's axial band and coil
# clearance against this head and the arm end.
# User ruling: machined webs 2 mm target, 1.5 floor, judged at the WORST case
# of the printed bands, fixed by geometry so bands can be LOOSE. The head prints
# at .X (+/-0.8) and the 0.8 slot at .XX (+/-0.51), so the web under the slot is
# 4.2 - 0.8 - (0.8 + 0.51) = 2.09 mm at worst (the 2.8 head at .XX gave 0.98).
# The underside (HEAD_X, the clamp face) is unchanged; only the slotted end face
# moves outboard. It stays 1.66 mm from the counter spring's raised half-turn,
# which plateaus from T = 3.2 (1.92 at the old 2.0), and 3.72 mm from its coil.
# The head diameter prints at .X: at Ø12.8 that clearance is still 1.26 mm.
SCREW_HEAD_T = 4.2
# Ø11.85 is the nominal model insert in the nominal Ø12.00 tube bore (0.075 mm
# radial gap). The drawing does not assume stock-ID accuracy: it match-turns
# this identified plug to the actual assigned bore for the filler supplier's
# 0.051-0.127 mm gap BETWEEN FACING SURFACES and holds it concentric. The
# supplier range is at brazing temperature; the AISI 1010 tube and AISI 1018
# plug are similar-expansion steels, so their centered cold-fit gap is retained
# to first order through brazing rather than translated into a diametral band.
PLUG_DIA = 11.85
# Policy rule 12 (U27): full-thread engagement >= 1.5D at the printed worst
# case. The plug prints at .X (+/-0.8), so 7.0 leaves 6.2 = 1.77D of #6-32
# (the former 6.0 gave 5.2 = 1.48D). The under-head length grows with it.
# All 6.2 is FULL thread: the plug is tapped through (TAP_CALLOUT "#6-32
# UNC-2B THRU"), so it has no tap-lead loss, and in the installed, clamped
# state the screw passes fully through it (9.58 reach at worst case), so its
# tip threads sit past the plug. The 8.0 open gap is assembly access only: the
# eye hangs loose and the screw carries no clamp load, so it is not a load case
# for engagement (Main ruling on Codex machinist r19 B2).
PLUG_T = 7.0
PLUG_BRAZE_RADIAL_CLEARANCE = 0.075
SPRING_SCREW_PLUG_ENGAGEMENT_MM = PLUG_T
SPRING_SCREW_UNDERHEAD_LENGTH_MM = (
    SPRING_SCREW_PLUG_ENGAGEMENT_MM + SPRING_SCREW_OPEN_GAP_MM
)
SCREW_TAP_MINOR_DIA = TAP_DRILL_MM["#6-32"]
SCREW_SLOT_W = 0.80
SCREW_SLOT_DEPTH = 0.80
