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
# in the Ø.4500 crank bore, whose height follows the crossed-crank config
# above the unchanged foot -- no eccentric bushing, no drop, fixed centres.
# The boss started at the harvested head's tangent plane (the Ø42.7506 head,
# radius 21.3753), and runs the harvested 2.8360 in from there.  That station
# seats the 16T on the boss face (build_dt_drive_train_assembly, the
# crankshaft's seat), a mesh closure, so it stays put while the head snaps to
# its .XX 1.68 (#290): the boss face stands 0.039 mm proud of the head's
# tangent plane.  The north face is the boss's machined end, stationed from
# the post axis on the print.
CRANK_BOSS_DIA = 21.844  # .86
CRANK_BORE_DIA = 11.43  # .4500 in
CRANK_BORE_HEIGHT = _config.machine("gear_train", "crank_axis_height_mm")
CRANK_BORE_OFFSET = 0.0
CRANK_BOSS_NORTH_FACE = 21.3753
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
BORE_DIA = 12.2682  # .483 in
CONE_BOSS_LENGTH = post_envelope.BLOCK_DIA

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
ATTACHMENT_THRU_DIA = 7.14248
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
# the boss symmetric in a note.  The drive-train stacks book that face half the
# face-to-face band off the post axis (dt_cone_gear_shaft_spec,
# crank_boss_rim, build_dt_drive_train_assembly); the station's own band is the
# largest .001 in band inside that half, so no stack moves.
CONE_BOSS_NORTH_STATION = CONE_BOSS_LENGTH / 2.0
_CONE_BOSS_HALF_BAND = printed_band_mm(3, unit=UNIT) / 2.0  # ConeBossLen .XXX
CONE_BOSS_NORTH_STATION_TOLERANCE_MM = (
    math.floor(_CONE_BOSS_HALF_BAND / MM_PER_IN * 1000.0 + 1e-9) / 1000.0 * MM_PER_IN
)  # +/-.002
if CONE_BOSS_NORTH_STATION_TOLERANCE_MM > _CONE_BOSS_HALF_BAND:
    raise AssertionError(
        "north cone-boss face station band exceeds the stacks' half band"
    )

# Final solid volume, the sum of the per-feature analytic terms the build
# checks natively one feature at a time (build_dt_cone_pivot_post.py asserts
# the sum at import):
#
#   body      pi*(BLOCK_DIA/2)^2*BLOCK_HEIGHT
#   head      pi*((HEAD_DIA/2)^2 - (BLOCK_DIA/2)^2)*HEAD_HEIGHT
#   crank boss outside the head cylinder
#   crank bore pi*(CRANK_BORE_DIA/2)^2*CRANK_BOSS_LENGTH
#   cone pads outside the body cylinder
#   cone bore pi*(BORE_DIA/2)^2*CONE_BOSS_LENGTH
#   2x (thru pi*(ATTACHMENT_THRU_DIA/2)^2*(BLOCK_HEIGHT-cbore_depth)
#       + cbore pi*(ATTACHMENT_CBORE_DIA/2)^2*cbore_depth)
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
# The constant is that sum at the 86 mm reference for the inch sizes (#290).
HARVESTED_VOLUME_MM3 = 112_123.5736 + math.pi * (
    (post_envelope.BLOCK_DIA / 2.0) ** 2 - 2.0 * (ATTACHMENT_THRU_DIA / 2.0) ** 2
) * (BLOCK_HEIGHT - 86.0)
HARVESTED_MASS_KG = HARVESTED_VOLUME_MM3 * 7.20e-6

# Both bores are running journals reamed with owned decimal reamers, each
# band the one the `shaft_in_bushing` fit class (.0010-.0023 in) needs on its
# shaft's fleet `SHAFT_H` (0/-.0008 in) band (tolerance-policy.md, "How a
# critical-feature tolerance is decided", step 6b):
#
#   crank:   bore .4500 +.0005/.0000 (owned .4500 reamer), shaft .449
#            (crankshaft MHA-DT-11)
#   journal: bore .483 +.0010/+.0005 (owned .4835 reamer), shaft .4825
#            (cone shaft MHA-DT-04)
#
# Apart from these two, the spacing between them and the cone-axis height (both
# below), nothing else on this casting is an accuracy feature, so nothing else
# carries a band: the title block's general grades govern.
RUNNING_BORE_BAND = REAM_H7  # the crank bore
JOURNAL_BORE_BAND = (0.0254, 0.0127)  # the cone journal bore

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

# Webs around the Ø.4500 crank bore, at print-worst (drawing-guidelines.md
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
    "body foot OD": _printed_limits(post_envelope.BLOCK_DIA, 3)[0] / 2.0
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
# head, the body height, the boss diameters, the mounting-hole stations and
# the cone-axis height (its own band) take two.  The foot OD and the cone boss
# length share the harvested 1.654 (the boss spans the body), so they take
# three; the shaft collar bears on the boss's north face, half the length's
# band off the post centre, and that half lands on the cone-tip adjuster's
# engagement (build_dt_drive_train_assembly.TIP_EMBED_WORST_MM).  The crank
# boss length is Pedro's 2.836 in source dimension, three places.  The
# crank-axis height (a reference), the crank-above-cone spacing and the crank
# boss's machined north-face station (the 16T's seat) are mesh closures
# printed to .001.  The basic plan angle feeds the retained crank-bore angularity frame;
# its four places spell the configured geometry, not a tighter general
# angular band.  The two reamed running bores take four, the places their
# size limits are written in.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "MainBodyProfile": {"MainBodyDia": 3},
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
