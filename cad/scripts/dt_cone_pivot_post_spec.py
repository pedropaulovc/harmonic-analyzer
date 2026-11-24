r"""Pure-data dimensional contract shared by the cone pivot post and drawing.

The hand-modelled ``cone-pivot-post-v2.SLDPRT`` supplies the cone, foot and
mounting datums. Its original 86 mm height was manually rederived from the
second ch30 eight-view
(``references/albert-michelsons-harmonic-analyzer/ch30_images/page003_img01.png``).
The normal-24DP crossed crank uses the raised common journal station law,
with the same head height and bore spacing above the unrelieved platform.
The casting proportions came from the two sharp ch11 details
(``ch11_images/page002_img05.jpeg`` and ``page002_img06.jpeg``); the retained
diameters and journal stations are the exact harvested feature dimensions.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``).  Each
fabricated nominal is the exact millimetre value of the inch it prints (the
trailing comments).  The cone/crank axis heights and the bore spacing are
mesh closures: they keep their configured values and print rounded.
"""

from __future__ import annotations

import math

import _config
from _fit_ream_h7 import REAM_H7
from _gtol_cylinder import CylinderFace
from _gtol_controls import GeometricControl, PartDatum
from _gtol_planar import PlanarFace
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import (
    angular_band_deg,
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    edge_break_radius_mm,
    printed_band_mm,
    printed_deviations,
)
from _surface_finish import MACHINED_UM, SEAT_UM, SurfaceFinishControl
import _cone_axis_constants as cone_axis
import dt_cone_post_envelope as post_envelope
from dt_post_mount_stack import (
    POST_BODY_HEIGHT_MM,
    POST_MOUNT_COUNTERBORE_DEPTH_MM,
)


MM_PER_IN = 25.4
# The sheet unit the registry row declares; every band below is read for it.
UNIT = drawing_unit("parts/dt-cone-pivot-post", _config.parts("dt-cone-pivot-post"))


def _printed_limits(model: float, places: int) -> tuple[float, float]:
    """(min, max) an accepted part may show for a general-grade dimension."""
    lower, upper = printed_deviations(model, places, unit=UNIT)
    return model + lower, model + upper


# Main casting: the upper 1.05 in is a very slightly larger head around the
# main body; both cylinders share the vertical body/swing axis.  HEAD_DIA is
# v36's harvested 42.7506 (user ruling 2026-09-28: MHA-DT-05's v36 post
# geometry is restored, and with it the Ø44 as-cast collar reading is
# withdrawn), snapped to the .XX it prints.  Nothing mates on the head, but the
# mounting counterbores' wall to its OD reads its limits, so it prints .XX.
BLOCK_HEIGHT = POST_BODY_HEIGHT_MM
HEAD_DIA = 42.672  # 1.68
HEAD_HEIGHT = 26.67  # 1.05
HEAD_BASE_Y = BLOCK_HEIGHT - HEAD_HEIGHT

# Straight crank/sprocket journal in the harvested PART frame.  It starts at
# local -Z and projects along local +Z to CRANK_BOSS_END_Z.  The assembly's exact
# Ry(180) installation maps that long boss toward machine -Z.  Keep Pedro's
# corrected source dimension in inches: 2.8360 in replaces the 2.85086614 in
# initial derivation.
#
# v36 geometry (user ruling 2026-09-28): the crankshaft MHA-DT-11 runs directly
# in the Ø.4385 crank bore (owner ruling 2026-11-23, tool audit Q11; it was
# Ø.4500), whose height follows the crossed-crank config
# above the unchanged foot -- no eccentric bushing, no drop, fixed centres.
# The boss starts .842 north of the post axis, the harvested head's tangent
# plane (the Ø42.7506 head, radius 21.3753) on the .XXX grid its station
# prints at, and runs the harvested 2.8360 in from there.  That station seats
# the 16T on the boss face (build_dt_drive_train_assembly, the crankshaft's
# seat), a mesh closure, and the far face seats the crankshaft's collar: the
# boss face stands 0.051 mm proud of the .XX 1.68 head's tangent plane.  The
# north face is the boss's machined end, stationed from the post axis on the
# print.
CRANK_BOSS_DIA = 21.844  # .86
CRANK_BORE_DIA = 11.1379  # .4385 in
CRANK_BORE_HEIGHT = _config.machine("gear_train", "crank_axis_height_mm")
CRANK_BORE_OFFSET = 0.0
CRANK_BOSS_NORTH_FACE = 21.3868  # .842
CRANK_BOSS_START_Z = -CRANK_BOSS_NORTH_FACE
CRANK_BOSS_LENGTH_IN = 2.8360
CRANK_BOSS_LENGTH = CRANK_BOSS_LENGTH_IN * MM_PER_IN
CRANK_BOSS_END_Z = CRANK_BOSS_START_Z + CRANK_BOSS_LENGTH

# The boss must lie wholly in the head's nominal height band: the independent
# boss-overlap volume oracle clips it against HEAD_DIA, never the lower body.
CRANK_BOSS_HEAD_MARGIN_MM = min(
    CRANK_BORE_HEIGHT - CRANK_BOSS_DIA / 2.0 - HEAD_BASE_Y,
    BLOCK_HEIGHT - CRANK_BORE_HEIGHT - CRANK_BOSS_DIA / 2.0,
)
if CRANK_BOSS_HEAD_MARGIN_MM <= 0.0:
    raise AssertionError("crank boss lies outside the post head's height band")

# Inclined cone-shaft journal.  The configured cone-line incline is baked
# into the part; downstream placement composes it with the exact Ry(180)
# installation instead of re-authoring the harvested feature frame.
INCLINE_DEG = _config.machine("cone_incline", "derived_incline_deg")
CONE_AXIS_VIEW = "CONE JOURNAL"
BORE_HEIGHT = cone_axis.CONE_AXIS_HEIGHT_MM
CONE_BOSS_DIA = 17.272  # .68
BORE_DIA = 11.1379  # .4385 in
# The journal bore's two rims bound the cone shaft MHA-DT-04's bearing on
# this post: the north rim is the inner edge of its collar's thrust ring on
# the .827 face, and both rims end the journal's supported length
# (dt_cone_gear_shaft_spec: THRUST_RING_MIN less two breaks keeps the .060
# floor, and JOURNAL_SUPPORT_SPAN_MIN_MM takes a break off each end).  The
# cone-shaft spec derives that largest break (THRUST_EDGE_BREAK_MAX); it
# imports this spec, so the value is restated here and the post's sheet
# asserts the two agree.  The model breaks both rims AT the maximum, a
# 45-degree chamfer, and the sheet prints it as a leader note on the far rim
# in Section A-A, BREAK .004 MAX / BOTH BORE RIMS (the title block's .010
# would take the ring under its floor; machinist review r1, farm run
# 20261124T110807008Z: a 20:1 detail for one break was over-specification).
JOURNAL_RIM_BREAK = 0.1016  # .004 MAX
# The sheet's leader note on that rim: the single limit and which rims.
JOURNAL_RIM_BREAK_NOTE = (
    f"BREAK .{round(JOURNAL_RIM_BREAK / 25.4 * 1000.0):03d} MAX\nBOTH BORE RIMS"
)
# The harvested 1.654 face-to-face: MHA-DT-04's bearing length, which the
# cone shaft's stations and the gear stack close on.  It is its own value, not
# the body's Ø.
CONE_BOSS_LENGTH = 42.011
# The cast body below the head.  #2756 (machinist reviews of #2725 and of the
# R5 rolling-main build): on the Ø1.65 envelope the boss ends stood .002 proud
# of the body and lay flush or inside it at the printed limits, so no route
# could make the pads drawn.  Delegated ruling 2026-11-17 (MainBuild), no owner
# precedent (#2144; Main's 2026-11-13 interim on the same feature was itself
# pending the owner on #2756): the body is cast Ø1.60 at the title
# block's .XX band, so both cone bosses stand clear of it as real cast pads,
# as on the original casting and like the integral crank boss.  It stays
# inside the Ø1.65 envelope the swing platform, the base and the drive-train
# foot containment are laid out on (dt_cone_post_envelope.BLOCK_DIA), so
# nothing outside the post moves; the bearing length and the collar face's
# station are unchanged.
BODY_DIA = 40.64  # 1.60
if _printed_limits(BODY_DIA, 2)[1] > post_envelope.BLOCK_DIA:
    raise AssertionError("the post body's printed limit passes the platform's envelope")

# Two vertical ANSI-inch 1/4 Fillister Head Screw counterbores in the top face.
# Ry(180) maps part-local +X to machine -X, so the assembly intentionally mates
# local east/west axes to the opposite platform names.
#
# MHA-DT-VN-61 must provide a shank long enough to reach the platform from the
# counterbore floor, BLOCK_HEIGHT - ATTACHMENT_CBORE_DEPTH.  The unchanged
# dia .453 x .24 counterbore takes its ASME B18.6.3 fillister head; the
# purchased-stock spec owns the actual head envelope, stock-length,
# cut-to-fit and engagement guards.  Raising the casting also raises that
# floor, so the former 3-1/2-inch stock is no longer long enough.
# #2697: letter M (.295), .045 over the 1/4 screw; the sheet prints the drill's
# own decimal, so the owned drill meets DRILLED HOLES +.004/0 (19/64 prints
# .297 and cuts .2969, under it).  MHA-DT-00 turns the post on these
# screws until the MHA-DT-37 pivot runs free in MHA-DT-39; at 9/32 that turn
# covered the tip's print-worst lateral error with 0.13 mm to spare
# (build_dt_drive_train_assembly's TIP_LATERAL_CAPACITY_MM), which held three
# MHA-DT-21 stations at .XXX.  The fillister head still seats all round the
# hole ("counterbore floor annulus" below).
ATTACHMENT_THRU_DIA = 7.493  # .295, letter M
ATTACHMENT_CBORE_DIA = 11.5062  # .453
ATTACHMENT_CBORE_DEPTH = POST_MOUNT_COUNTERBORE_DEPTH_MM
# The mounting counterbores' Hole Wizard callout prints its diameters at
# three inch places (#290).  The depth only has to sink the fillister head,
# so it prints .XX (MHA-DT-05 machinist review); the model keeps 6.0198
# because the screw's cut length closes on it (dt_post_mount_stack).
MOUNT_HOLE_CALLOUT_PLACES = 3
MOUNT_CBORE_DEPTH_PLACES = 2
WEB_FLOOR_MM = WALL_FLOOR_MM


# R2: a nominal v36 hole centre at 13.44 left only 1.04 mm to the restored
# head OD at the mm sheet's printed limits (head .X), so the complete matched
# post/platform pattern moved inward to 12.98.  The inch sheet prints the head
# .XX and the counterbore's native hole callout three places (its
# twist-drilled through hole takes the DRILLED HOLES row); the pattern keeps
# its station, snapped to the .XX it prints, and the wall to the head OD now
# meets the rule-17 target at print-worst.
ATTACHMENT_X = 12.954  # .51
ATTACHMENT_SPACING = 2.0 * ATTACHMENT_X
_HEAD_R_PRINT_MIN = _printed_limits(HEAD_DIA, 2)[0] / 2.0
_CBORE_R_PRINT_MAX = _printed_limits(ATTACHMENT_CBORE_DIA, 3)[1] / 2.0
MOUNT_HEAD_WEB_WORST = (
    _HEAD_R_PRINT_MIN
    - _printed_limits(ATTACHMENT_X, 2)[1]
    - _CBORE_R_PRINT_MAX
)
if MOUNT_HEAD_WEB_WORST < WALL_TARGET_MM:
    raise AssertionError("mounting counterbore leaves under the .080 in wall target to the head OD")

# The cone shaft MHA-DT-04's collar bears on the NORTH cone-boss end face, so
# the print locates that face from the post axis (rule 10) instead of calling
# the boss symmetric in a note.  Owner ruling 2026-11-24, audit part 2 C9
# ("Yes: add the look and relax the rest."): the face takes the title
# block's .XXX band (it was +/-.002, the largest .001 band inside half the
# face-to-face band).  Step 23's look at the bushing erases it from the tip
# air; the drive-train stacks that place the collar, the 64T and T120 from
# it book the station's printed limits (CONE_BOSS_NORTH_STATION_DEVIATIONS_MM:
# build_dt_drive_train_assembly, crank_boss_rim, dt_cone_tip_air).
CONE_BOSS_NORTH_STATION = CONE_BOSS_LENGTH / 2.0
CONE_BOSS_NORTH_STATION_DEVIATIONS_MM = printed_deviations(
    CONE_BOSS_NORTH_STATION, 3, unit=UNIT
)
CONE_BOSS_NORTH_STATION_TOLERANCE_MM = max(
    abs(deviation) for deviation in CONE_BOSS_NORTH_STATION_DEVIATIONS_MM
)
# Both cone bosses stand clear of the body at every printed limit (#2756):
# the north face at its station's least, the far face at the face-to-face's
# least less the north station's greatest, each against the body's largest
# radius.  Each pad stands at least the title block's edge break proud, so
# breaking its rim never reaches the body.
_BODY_RADIUS_MAX = _printed_limits(BODY_DIA, 2)[1] / 2.0
_NORTH_STATION_LIMITS = tuple(
    CONE_BOSS_NORTH_STATION + deviation
    for deviation in CONE_BOSS_NORTH_STATION_DEVIATIONS_MM
)
CONE_BOSS_STANDOFF_WORST_MM = {
    "north": _NORTH_STATION_LIMITS[0] - _BODY_RADIUS_MAX,
    "far": _printed_limits(CONE_BOSS_LENGTH, 3)[0]
    - _NORTH_STATION_LIMITS[1]
    - _BODY_RADIUS_MAX,
}
CONE_BOSS_STANDOFF_FLOOR_MM = max(
    edge_break_radius_mm(unit=UNIT), edge_break_chamfer_mm(unit=UNIT)
)
for _name, _standoff in CONE_BOSS_STANDOFF_WORST_MM.items():
    if _standoff < CONE_BOSS_STANDOFF_FLOOR_MM:
        raise AssertionError(
            f"the {_name} cone boss stands {_standoff:.3f} mm off the body at the "
            f"printed limits, under the {CONE_BOSS_STANDOFF_FLOOR_MM:.3f} mm edge break"
        )

# Final solid volume, the sum of the per-feature analytic terms the build
# checks natively one feature at a time (build_dt_cone_pivot_post.py asserts
# the sum at import):
#
#   body      pi*(BODY_DIA/2)^2*BLOCK_HEIGHT
#   head      pi*((HEAD_DIA/2)^2 - (BODY_DIA/2)^2)*HEAD_HEIGHT
#   crank boss outside the head cylinder
#   crank bore pi*(CRANK_BORE_DIA/2)^2*CRANK_BOSS_LENGTH
#   cone pads outside the body cylinder
#   cone bore pi*(BORE_DIA/2)^2*CONE_BOSS_LENGTH
#   2x (thru pi*(ATTACHMENT_THRU_DIA/2)^2*(BLOCK_HEIGHT-cbore_depth)
#       + cbore pi*(ATTACHMENT_CBORE_DIA/2)^2*cbore_depth)
#   2x journal rim break pi*JOURNAL_RIM_BREAK^2*(BORE_DIA/2 + JOURNAL_RIM_BREAK/3)
#       (its triangle, legs JOURNAL_RIM_BREAK, revolved about the bore axis)
#
# The old v36 constant, harvested from v2's B-rep rather
# than summed, read 112 302.9406: 2.05 mm^3 (0.002%) apart.  The feature sum
# is the authority, as it has been since the 2026-09-21 farm build of a
# Ø44-collar recipe read 121 575.3 against its constant: that recipe had never
# bored the crank boss (7 401.7), because the bore cut's default direction
# (opposite the sketch normal) found the collar to bite instead of flipping
# into the boss.  The build still reverses that cut explicitly.  Mass at gray
# iron 7.20 g/cc.
# Growing the 86 mm feature-sum reference adds only the body column less the
# two through drills.  The head shell's height and the contained boss/pad/bore
# intersections are unchanged; the builder independently recomputes them.
# The constant is that sum at the 86 mm reference for the inch sizes (#290)
# and the Ø40.64 body of #2756 (111 108.3126 on the Ø41.91 envelope, 112 123.5736
# at the harvested Ø42.011), with the letter M through drills of #2697
# (111 752.8114 at 9/32 on the Ø41.91 body), and with the two journal bores
# at Ø.4385 (tool audit Q11; 106 527.63207 at Ø.4500 crank and Ø.483 cone
# bores; the smaller bores leave 1 245.87414 more iron).  The two journal
# rim breaks come off it.
HARVESTED_VOLUME_MM3 = (
    107_773.50621
    + math.pi
    * ((BODY_DIA / 2.0) ** 2 - 2.0 * (ATTACHMENT_THRU_DIA / 2.0) ** 2)
    * (BLOCK_HEIGHT - 86.0)
    - 2.0 * math.pi * JOURNAL_RIM_BREAK**2 * (BORE_DIA / 2.0 + JOURNAL_RIM_BREAK / 3.0)
)
HARVESTED_MASS_KG = HARVESTED_VOLUME_MM3 * 7.20e-6

# Both bores are running journals, each reamed to the `shaft_in_bushing` fit
# class (.0010-.0023 in) on its shaft's fleet `SHAFT_H` (0/-.0008 in) band
# (tolerance-policy.md, "How a critical-feature tolerance is decided", step
# 6b).  Owner ruling 2026-11-23, tool audit Q11 (option B): "Both bores dia
# .4385 +.0005/0 (7/16 over reamer of the Shars set), both journals .4375
# 0/-.0008".  The bores were Ø.4500 and Ø.483 +.0010/+.0005, sized for .4500
# and .4835 reamers the shop never owned (the inventory owns only the LMS
# 5948 adjustable set and the .3760); one bought reamer now cuts both:
#
#   crank:   bore .4385 +.0005/.0000, shaft .4375 (crankshaft MHA-DT-11)
#   journal: bore .4385 +.0005/.0000, shaft .4375 (cone shaft MHA-DT-04)
#
# Apart from these two, the spacing between them and the cone-axis height (both
# below), nothing else on this casting is an accuracy feature: the title
# block's general grades govern, the body's diameter included (#2756).
RUNNING_BORE_BAND = REAM_H7  # the crank bore
JOURNAL_BORE_BAND = REAM_H7  # the cone journal bore

# Crank-above-cone bore spacing (U31, 2026-09-23, option 3a). The crank axis
# is located FROM THE CONE AXIS, not from the foot. Two foot-referenced .XX
# heights would stack their bands; at fixed centres that could close the
# 16T:64T crossed mesh and make it bind. Under the user ruling 2026-09-28
# the mesh has no backlash window or fit-up adjustment. Its closing-corner
# budget is now crank_mesh_stack.standard_check() backlash > 0, read at the low
# end of this U31 band and the retained angularity frame. The upper bound
# predates that no-bind-only requirement; keep it as ruled (+0.37 mm, printed
# +.014 in, inside it), without treating its former backlash-window
# derivation as a current gate.  The spacing is the physical fixed-centre
# pair's (a mesh closure, printed rounded to .001).  How the shop holds it is
# theirs (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)).
CRANK_ABOVE_CONE = CRANK_BORE_HEIGHT - BORE_HEIGHT
CRANK_ABOVE_CONE_BAND = (0.3556, 0.0)  # +.014/.000

# Cone-axis height above the foot.  The post's journal sets the cone shaft's
# height; at the shaft's tip MHA-DT-21 stands directly on the same platform top
# (user ruling 2026-09-29, no shim), so the tip's stub must enter the
# adjuster's cup on this band plus the block's AxisHeight band (the plate top
# is common to both and cancels).  The height takes the title block's .XX
# band, printed by the general tolerance rather than repeated on the dimension
# (machinist review); build_dt_drive_train_assembly asserts the capture closes.
JOURNAL_AXIS_HEIGHT_TOLERANCE_MM = printed_band_mm(2, unit=UNIT)  # +/-.010

# Webs around the Ø.4385 crank bore, at print-worst (drawing-guidelines.md
# rule 17 (walls and webs); the inch floor).  The bore is centred on the
# post's symmetry plane, which is what keeps the two mounting holes beside it
# workable; its worst case is the running band's maximum with the crank axis
# at its highest (the cone axis at the top of its own band above plus the
# whole spacing band).  The through holes are drilled (DRILLED HOLES row),
# their stations and the body height print .XX, the counterbore's diameter
# three places and its depth .XX (its native hole callout), and the boss
# diameter .XX.
_DRILL_OVERSIZE = drilled_oversize_mm(unit=UNIT)
_CRANK_BORE_R_MAX = (CRANK_BORE_DIA + RUNNING_BORE_BAND[0]) / 2.0
_CRANK_AXIS_Y_MAX = (
    CRANK_BORE_HEIGHT + JOURNAL_AXIS_HEIGHT_TOLERANCE_MM + CRANK_ABOVE_CONE_BAND[0]
)
_HOLE_X_MIN = _printed_limits(ATTACHMENT_X, 2)[0]
_BLOCK_TOP_MIN = _printed_limits(BLOCK_HEIGHT, 2)[0]
_CBORE_CORNER = (
    _HOLE_X_MIN - _CBORE_R_PRINT_MAX,
    _BLOCK_TOP_MIN
    - _printed_limits(ATTACHMENT_CBORE_DEPTH, MOUNT_CBORE_DEPTH_PLACES)[1]
    - _CRANK_AXIS_Y_MAX,
)
CRANK_BORE_WEBS_WORST = {
    "mounting thru hole": _HOLE_X_MIN
    - (ATTACHMENT_THRU_DIA + _DRILL_OVERSIZE) / 2.0
    - _CRANK_BORE_R_MAX,
    # the counterbore's bottom inner corner sits above and beside the bore
    "mounting counterbore": math.hypot(*_CBORE_CORNER) - _CRANK_BORE_R_MAX,
    "top face": _BLOCK_TOP_MIN - _CRANK_AXIS_Y_MAX - _CRANK_BORE_R_MAX,
    "crank boss OD": _printed_limits(CRANK_BOSS_DIA, 2)[0] / 2.0 - _CRANK_BORE_R_MAX,
}
# The cast boss itself, not just its bore, must also remain below the top at
# the closing printed corner.  Its lower edge may blend into the lower body;
# the nominal boss/head containment above is what the volume oracle requires.
CRANK_BOSS_TOP_MARGIN_WORST_MM = (
    _BLOCK_TOP_MIN - _CRANK_AXIS_Y_MAX - _printed_limits(CRANK_BOSS_DIA, 2)[1] / 2.0
)
if CRANK_BOSS_TOP_MARGIN_WORST_MM <= 0.0:
    raise AssertionError("crank boss breaches the post's print-worst top outline")
if _CBORE_CORNER[1] <= 0.0:
    raise AssertionError("mounting counterbore reaches below the crank axis")
for _name, _web in CRANK_BORE_WEBS_WORST.items():
    if _web < WEB_FLOOR_MM:
        raise AssertionError(
            f"Ø{CRANK_BORE_DIA} crank bore leaves {_web:.3f} to the {_name} at "
            f"print-worst, under the {WEB_FLOOR_MM} web floor"
        )

# The inward pattern also clears the smaller lower body and the inclined
# cone journal bore; the counterbore floor keeps a full screw-head seat
# outside the through drill.  Use the through-drill's unilateral oversize and
# the loosest title-block angular row on the cone axis; its BASIC angle and
# angularity frame are tighter, so this overbounds the printed corner.
MOUNT_OTHER_WEBS_WORST = {
    "body foot OD": _printed_limits(BODY_DIA, 2)[0] / 2.0
    - _printed_limits(ATTACHMENT_X, 2)[1]
    - (ATTACHMENT_THRU_DIA + _DRILL_OVERSIZE) / 2.0,
    "inclined cone bore": _HOLE_X_MIN
    * math.cos(math.radians(INCLINE_DEG + angular_band_deg(unit=UNIT)))
    - (ATTACHMENT_THRU_DIA + _DRILL_OVERSIZE) / 2.0
    - (BORE_DIA + JOURNAL_BORE_BAND[0]) / 2.0,
    "counterbore floor annulus": (
        _printed_limits(ATTACHMENT_CBORE_DIA, 3)[0]
        - ATTACHMENT_THRU_DIA
        - _DRILL_OVERSIZE
    ) / 2.0,
}
for _name, _web in MOUNT_OTHER_WEBS_WORST.items():
    if _web < WEB_FLOOR_MM:
        raise AssertionError(
            f"mounting holes leave {_web:.3f} to the {_name} at print-worst, "
            f"under the {WEB_FLOOR_MM} web floor"
        )

# Journal-plan reference sketch (Top plane, all construction).  The configured
# plan angle between the crank axis and the cone-journal axis is REAL model
# geometry -- ConeShaftNormal's angle -- but no face carries it into a view.
# Two construction rays and a driving angular dimension use the same
# ConeIncline owner as the actual plane.
JOURNAL_REFERENCE_LENGTH = 40.0
JOURNAL_REFERENCE_X = JOURNAL_REFERENCE_LENGTH * math.sin(math.radians(INCLINE_DEG))
JOURNAL_REFERENCE_Z = JOURNAL_REFERENCE_LENGTH * math.cos(math.radians(INCLINE_DEG))
CRANK_BOSS_NEAR_Z = abs(CRANK_BOSS_START_Z)

# The foot seat's symbol names the mate it seats on (rule 7, say why at the
# callout), as pd_transgear_front_bushing names its thrust faces' mates.
FOOT_SEAT_FINISH_TARGET = "SEATS ON MHA-DT-20"
SURFACE_FINISHES = (
    # The post is a casting that may be left as-cast everywhere else; the
    # faces that MUST be cut say so on the face (the title block's surface row
    # is the process statement "CAST/MACHINED", not a grade).
    SurfaceFinishControl(
        "foot_seat",
        SEAT_UM,
        PlanarFace((0, -1, 0), 0.0),
        production_method=FOOT_SEAT_FINISH_TARGET,
        display_unit=UNIT,
    ),
    # The crankshaft MHA-DT-11 runs in the crank bore, so it is a running
    # journal (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)), like the cone bore.
    SurfaceFinishControl(
        "crank_bore",
        MACHINED_UM,
        CylinderFace(CRANK_BORE_DIA, contains_y_mm=CRANK_BORE_HEIGHT),
        display_unit=UNIT,
    ),
    SurfaceFinishControl(
        "journal_bore",
        MACHINED_UM,
        CylinderFace(BORE_DIA, contains_y_mm=BORE_HEIGHT),
        display_unit=UNIT,
    ),
    # The cone shaft's thrust collar runs on the north cone-boss end face
    # (#914), so it is a running face.  Part-local normal: Ry(180) maps it to
    # machine +Z, the direction cone stations grow toward the gears.
    SurfaceFinishControl(
        "cone_boss_north_face",
        MACHINED_UM,
        PlanarFace(
            (
                -math.sin(math.radians(INCLINE_DEG)),
                0.0,
                -math.cos(math.radians(INCLINE_DEG)),
            ),
            CONE_BOSS_LENGTH / 2.0,
        ),
        display_unit=UNIT,
    ),
)

# Only dimensions that exist natively on the authored model are marked for the
# curated print, so the drawing cannot drift from the part.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "MainBodyProfile": {"MainBodyDia"},
    "MainBody": {"MainBodyHt"},
    "HeadProfile": {"HeadDia"},
    "Head": {"HeadHt"},
    "AttachmentScrewHoles": {"MountWestX", "MountEastX"},
    "CrankBossProfile": {"CrankAxisY", "CrankBossDia"},
    "CrankSprocketBoss": {"CrankBossLen"},
    "CrankBoreProfile": {"CrankBoreDia"},
    "ConeBossProfile": {"JournalAxisY", "ConeBossDia"},
    "ConeShaftBoss": {"ConeBossLen"},
    "JournalBoreProfile": {"JournalBoreDia"},
    "JournalPlanReference": {"InclineAngle"},
    "CrankBossStationReference": {"CrankBossStartZ"},
    "ConeBossStationReference": {"ConeBossNorthZ"},
    "BoreSpacingReference": {"CrankAboveCone"},
}

# Decimal places are product definition: they select the title-block general
# band (.X +/-.1, .XX +/-.01, .XXX +/-.005 in), so the PART owns them and the
# sheet only proves they survived the import (drawing-simplicity-policy.md `How the repository implements the guidelines`).
# Nothing prints .X: every size below feeds a wall, web or stack check.  The
# body and head diameters, the body height, the boss diameters, the
# mounting-hole stations and the cone-axis height (its own band) take two:
# the body's Ø1.60 is a cast size whose .XX band still leaves the mounting
# holes' outer wall over the floor (MOUNT_OTHER_WEBS_WORST) and both cone
# bosses proud of it (CONE_BOSS_STANDOFF_WORST_MM), so rule 17 gives it no
# tighter band.  The cone boss length is the harvested 1.654
# MHA-DT-04 bearing length, three places; the shaft collar bears on the
# boss's north face, half the length's band off the post centre, and that
# half lands on the cone-tip adjuster's engagement
# (build_dt_drive_train_assembly.TIP_EMBED_WORST_MM).  The crank
# boss length is Pedro's 2.836 in source dimension, three places.  The
# crank-axis height (a reference), the crank-above-cone spacing and the crank
# boss's machined north-face station (the 16T's seat) are mesh closures
# printed to .001.  The basic plan angle feeds the retained crank-bore angularity frame;
# its four places spell the configured geometry, not a tighter general
# angular band.  The two reamed running bores take four, the places their
# size limits are written in.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "MainBodyProfile": {"MainBodyDia": 2},
    "MainBody": {"MainBodyHt": 2},
    "HeadProfile": {"HeadDia": 2},
    "Head": {"HeadHt": 2},
    "AttachmentScrewHoles": {"MountWestX": 2, "MountEastX": 2},
    "CrankBossProfile": {"CrankAxisY": 3, "CrankBossDia": 2},
    "CrankSprocketBoss": {"CrankBossLen": 3},
    "CrankBoreProfile": {"CrankBoreDia": 4},
    "ConeBossProfile": {"JournalAxisY": 2, "ConeBossDia": 2},
    "ConeShaftBoss": {"ConeBossLen": 3},
    "JournalBoreProfile": {"JournalBoreDia": 4},
    # BASIC since #906: it feeds the crank bore's angularity frame; four places
    # retain the configured nominal without changing the frame's zone.
    "JournalPlanReference": {"InclineAngle": 4},
    "CrankBossStationReference": {"CrankBossStartZ": 3},
    "ConeBossStationReference": {"ConeBossNorthZ": 3},
    "BoreSpacingReference": {"CrankAboveCone": 3},
}

_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
if any(
    name not in DRAWING_DIMENSIONS.get(feature, frozenset())
    for feature, name in _PRECISION_NAMES
):
    raise AssertionError("DRAWING_PRECISION names a dimension the part never marks")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")

# No general note: the foot's mate rides its Ra symbol (FOOT_SEAT_FINISH_TARGET,
# rule 7: the reason on the callout it explains), and the inside-corner ceiling
# remains solely in the title block.  Every size, band and finish remains on a
# dimension or native symbol (drawing-guidelines.md rule 2 (the title block is
# the general specification) and rule 7 (notes: few, flagged, never a
# method)).  No wall falls short of the rule-17 target, so none is stated.
DRAWING_NOTES = ""

# One frame, on the drawing-simplicity-policy.md `GD&T allowlist (rule 5)` allowlist since #906 (USER RULING 2026-09-26,
# option ii): the crank bore's orientation to the cone journal.  The 16T:64T
# crossed mesh loses backlash to yaw and tilt of the crank axis -- the #906
# pose study (dt-logs/crankhub/crank-mesh-angle-20260926.jsonl) measured
# -0.100 at 1 deg of yaw and -0.041 at 1 deg of tilt, toward binding on fixed
# centres -- and a +/- on a dimension cannot hold an axis's
# direction in two planes at once.  A diametral zone of .004 in over the boss
# holds both to about 0.08 deg; the basic angle is the plan angle the print
# already carries.  The running fits stay size limits.
# Datum A alone leaves the zone free to turn about the journal axis, which
# bounds the plan angle but not tilt; the foot seat as secondary datum B
# clocks it, so the same zone holds tilt too.
CRANK_BORE_ANGULARITY_IN = ".004"
CRANK_BORE_ANGULARITY_MM = float(CRANK_BORE_ANGULARITY_IN) * MM_PER_IN
CRANK_BORE_ANGLE_LIMIT_DEG = math.degrees(
    math.atan(CRANK_BORE_ANGULARITY_MM / CRANK_BOSS_LENGTH)
)
PART_DATUMS = (
    PartDatum("A", CylinderFace(BORE_DIA, contains_y_mm=BORE_HEIGHT)),
    PartDatum("B", PlanarFace((0, -1, 0), 0.0)),
)
GEOMETRIC_CONTROLS = (
    GeometricControl(
        "crank_bore_angularity",
        "angularity",
        CRANK_BORE_ANGULARITY_IN,
        CylinderFace(CRANK_BORE_DIA, contains_y_mm=CRANK_BORE_HEIGHT),
        datums=("A", "B"),
        tolerance_zone="diametral",
    ),
)
BASIC_DIMENSIONS = frozenset({"InclineAngle"})
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {}
