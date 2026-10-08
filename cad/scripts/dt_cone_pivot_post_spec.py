r"""Pure-data dimensional contract shared by the cone pivot post and drawing.

The hand-modelled ``cone-pivot-post-v2.SLDPRT`` supplies the cone, foot and
mounting datums.  Its original 86 mm height was manually rederived from the
second ch30 eight-view; the normal-24DP crossed crank requires a real 90 mm
body with the same 26.6 mm head, not a raised bore outside that casting.
The casting proportions came from the two sharp ch11 details
(``ch11_images/page002_img05.jpeg`` and ``page002_img06.jpeg``); the retained
diameters and journal stations are the exact harvested feature dimensions.
"""

from __future__ import annotations

import math

import _config
from _gtol_spec import CylinderFace, GeometricControl, PartDatum, PlanarFace
from _surface_finish import MACHINED_UM, SEAT_UM, SurfaceFinishControl


MM_PER_IN = 25.4

# Main casting: the upper 26.6 mm is a very slightly larger head around the
# main body; both cylinders share the vertical body/swing axis.  HEAD_DIA is
# v36's harvested 42.7506 (user ruling 2026-09-28: MHA-DT-005's v36 post geometry
# is restored, and with it the Ø44 as-cast collar reading is withdrawn).  The
# head is a one-place reference size -- nothing mates on it; the body below it
# is the locating/bore cylinder and keeps its turned size.
BLOCK_DIA = 42.011
BLOCK_HEIGHT = 90.0
HEAD_DIA = 42.7506
HEAD_HEIGHT = 26.6
HEAD_BASE_Y = BLOCK_HEIGHT - HEAD_HEIGHT

# Straight crank/sprocket journal in the harvested PART frame.  It starts at
# local -Z and projects along local +Z to +50.6591.  The assembly's exact
# Ry(180) installation maps that long boss toward machine -Z.  Keep Pedro's
# corrected source dimension in inches: 2.8360 in replaces the 2.85086614 in
# initial derivation.
#
# v36 geometry (user ruling 2026-09-28): the crankshaft MHA-DT-011 runs directly
# in the Ø11.438 crank bore, whose height follows the crossed-crank config
# above the unchanged foot -- no eccentric bushing, no drop, fixed centres.
# The boss starts at the head's tangent plane, so its north face stands
# HEAD_DIA / 2 from the post
# axis, and runs the harvested 2.8360 in from there; nothing stands proud of
# that face inside the boss disc, so there is no spot face, retreat or run-out.
# The north face is the boss's machined end, stationed from the post axis on
# the print.
CRANK_BOSS_DIA = 21.93
CRANK_BORE_DIA = 11.438
CRANK_BORE_HEIGHT = _config.machine("gear_train", "crank_axis_height_mm")
CRANK_BORE_OFFSET = 0.0
CRANK_BOSS_NORTH_FACE = HEAD_DIA / 2.0
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

# Inclined cone-shaft journal.  Unlike v1, the 12.5182-degree incline is baked
# into the part; downstream placement composes it with the exact Ry(180)
# installation instead of re-authoring the harvested feature frame.
INCLINE_DEG = _config.machine("cone_incline", "derived_incline_deg")
CONE_AXIS_VIEW = "CONE JOURNAL"
BORE_HEIGHT = 33.368
CONE_BOSS_DIA = 17.2
BORE_DIA = 12.2808
CONE_BOSS_LENGTH = BLOCK_DIA

# Two vertical ANSI-inch 1/4 Fillister Head Screw counterbores in the top face.
# Ry(180) maps part-local +X to machine -X, so the assembly intentionally mates
# local east/west axes to the opposite platform names.
#
# MHA-VN-031 must provide a shank long enough to reach the platform from the
# counterbore floor, BLOCK_HEIGHT - ATTACHMENT_CBORE_DEPTH.  The unchanged
# dia 11.509 x 6.02 counterbore takes its ASME B18.6.3 fillister head; the
# purchased-stock spec owns the actual head envelope, stock-length,
# cut-to-fit and engagement guards.  Raising the casting also raises that
# floor, so the former 3-1/2-inch stock is no longer long enough.
ATTACHMENT_THRU_DIA = 7.14248
ATTACHMENT_CBORE_DIA = 11.50874
ATTACHMENT_CBORE_DEPTH = 6.0198
WEB_FLOOR_MM = 1.5


def _row(places: int) -> float:
    return float(str(_config.title_block(f"linear_{places}pl")["display"]).lstrip("±"))


# R2: a nominal v36 hole centre at 13.44 leaves only 1.04 mm to the restored
# head OD at the printed limits.  The head prints Ø42.8 (.X); the machined
# counterbore's native hole callout prints Ø11.51 (.XX), unlike its twist-drilled
# through hole (+0.10 / 0).  Each centre prints .XX.  Move the complete matched
# post/platform pattern inward by the least printable amount that retains the
# policy's 1.5 mm hard floor at all three closing corners.
_HEAD_R_PRINT_MIN = (round(HEAD_DIA, 1) - _row(1)) / 2.0
_CBORE_R_PRINT_MAX = (round(ATTACHMENT_CBORE_DIA, 2) + _row(2)) / 2.0
_ATTACHMENT_X_MAX = (
    _HEAD_R_PRINT_MIN - _CBORE_R_PRINT_MAX - _row(2) - WEB_FLOOR_MM
)
ATTACHMENT_X = math.floor((_ATTACHMENT_X_MAX + 1e-10) * 100.0) / 100.0
ATTACHMENT_SPACING = 2.0 * ATTACHMENT_X
MOUNT_HEAD_WEB_WORST = _HEAD_R_PRINT_MIN - (ATTACHMENT_X + _row(2)) - _CBORE_R_PRINT_MAX
if MOUNT_HEAD_WEB_WORST + 1e-9 < WEB_FLOOR_MM:
    raise AssertionError("mounting counterbore breaches the head's print-worst wall")
if MOUNT_HEAD_WEB_WORST - 0.01 >= WEB_FLOOR_MM:
    raise AssertionError("mounting holes are farther inward than the printable floor requires")

# Final solid volume, the sum of the per-feature analytic terms the build
# checks natively one feature at a time (build_dt_cone_pivot_post.py asserts
# the sum at import):
#
#   body      pi*(BLOCK_DIA/2)^2*BLOCK_HEIGHT
#   head      pi*((HEAD_DIA/2)^2 - (BLOCK_DIA/2)^2)*HEAD_HEIGHT
#   crank boss outside the head cylinder            = + 11 611.2487
#   crank bore pi*5.719^2*72.0344                    = -  7 401.6750
#   cone pads outside the body cylinder             = +    209.0550
#   cone bore pi*6.1404^2*42.011                     = -  4 976.2961
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
HARVESTED_VOLUME_MM3 = 112_300.8902 + math.pi * (
    (BLOCK_DIA / 2.0) ** 2 - 2.0 * (ATTACHMENT_THRU_DIA / 2.0) ** 2
) * (BLOCK_HEIGHT - 86.0)
HARVESTED_MASS_KG = HARVESTED_VOLUME_MM3 * 7.20e-6

# Both bores are running journals, so both carry the SAME size band -- the one
# the `shaft_in_bushing` fit class needs and no tighter (tolerance-policy.md,
# "How a critical-feature tolerance is decided", step 6b).  Each mating shaft
# is turned to (bore nominal - 0.05) with the fleet's `SHAFT_H` (0/-0.020)
# band, so a bore held +0.005/-0.025 delivers exactly the class's 0.025..0.075
# mm diametral clearance:
#
#   crank:   shaft 11.368..11.388  bore 11.413..11.443  (crankshaft MHA-DT-011)
#   journal: shaft 12.2108..12.2308 bore 12.2558..12.2858 (cone shaft MHA-DT-004)
#
# Apart from these two, the spacing between them and the cone-axis height (both
# below), nothing else on this casting is an accuracy feature, so nothing else
# carries a band: the title block's general grades govern.
RUNNING_BORE_BAND = (0.005, -0.025)

# Crank-above-cone bore spacing (U31, 2026-09-23, option 3a). The crank axis
# is located FROM THE CONE AXIS, not from the foot. Two foot-referenced .XX
# heights would stack to +/-1.02 mm; at fixed centres that could close the
# 16T:64T crossed mesh and make it bind. Under the user ruling 2026-09-28
# the mesh has no backlash window or fit-up adjustment. Its closing-corner
# budget is now crank_mesh_stack.TIGHT_BACKLASH_MM > 0, which reads the low
# end of this unchanged U31 band and the retained angularity frame. The
# upper +0.37 bound predates that no-bind-only requirement; keep it as ruled,
# without treating its former backlash-window derivation as a current gate.
# The current spacing follows the physical fixed-centre pair; its band stays
# +0.37/0.  How the shop holds it is theirs (policy rule 6).
CRANK_ABOVE_CONE = CRANK_BORE_HEIGHT - BORE_HEIGHT
CRANK_ABOVE_CONE_BAND = (0.37, 0.0)

# Cone-axis height above the foot.  The post's journal sets the cone shaft's
# height; at the shaft's tip MHA-DT-021 stands directly on the same platform top
# (user ruling 2026-09-29, no shim), so the tip's stub must enter the
# adjuster's cup on this band plus the block's explicit AxisHeight band (the
# plate top is common to both and cancels).  The .XX grade (+/-0.51)
# overruns the cup's capture, so the height carries its own symmetric band;
# build_dt_drive_train_assembly asserts the capture closes.
JOURNAL_AXIS_HEIGHT_TOLERANCE_MM = 0.25

# Webs around the Ø11.438 crank bore, at print-worst (policy rule 12: 2.0
# target, 1.5 floor).  The bore is centred on the post's symmetry plane, which
# is what keeps the two mounting holes beside it workable; its worst case is
# the running band's maximum with the crank axis at its highest (the cone axis
# at the top of its own band above plus the whole +0.37 spacing band).  The
# through holes are drilled (+0.10/0), their stations and the counterbore's
# diameter/depth print .XX, and the top face and boss diameter print .X.
_DRILL_OVERSIZE = float(_config.title_block("drilled_hole")["plus_mm"])
_CRANK_BORE_R_MAX = (CRANK_BORE_DIA + RUNNING_BORE_BAND[0]) / 2.0
_CRANK_AXIS_Y_MAX = (
    CRANK_BORE_HEIGHT + JOURNAL_AXIS_HEIGHT_TOLERANCE_MM + CRANK_ABOVE_CONE_BAND[0]
)
_HOLE_X_MIN = ATTACHMENT_X - _row(2)
_CBORE_CORNER = (
    _HOLE_X_MIN - _CBORE_R_PRINT_MAX,
    BLOCK_HEIGHT
    - _row(1)
    - round(ATTACHMENT_CBORE_DEPTH, 2)
    - _row(2)
    - _CRANK_AXIS_Y_MAX,
)
CRANK_BORE_WEBS_WORST = {
    "mounting thru hole": _HOLE_X_MIN
    - (ATTACHMENT_THRU_DIA + _DRILL_OVERSIZE) / 2.0
    - _CRANK_BORE_R_MAX,
    # the counterbore's bottom inner corner sits above and beside the bore
    "mounting counterbore": math.hypot(*_CBORE_CORNER) - _CRANK_BORE_R_MAX,
    "top face": BLOCK_HEIGHT - _row(1) - _CRANK_AXIS_Y_MAX - _CRANK_BORE_R_MAX,
    "crank boss OD": (CRANK_BOSS_DIA - _row(1)) / 2.0 - _CRANK_BORE_R_MAX,
}
# The cast boss itself, not just its bore, must also remain below the top at
# the closing printed corner.  Its lower edge may blend into the lower body;
# the nominal boss/head containment above is what the volume oracle requires.
CRANK_BOSS_TOP_MARGIN_WORST_MM = (
    BLOCK_HEIGHT - _row(1) - _CRANK_AXIS_Y_MAX
    - (CRANK_BOSS_DIA + _row(1)) / 2.0
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
    "body foot OD": (round(BLOCK_DIA, 1) - _row(1)) / 2.0
    - (ATTACHMENT_X + _row(2))
    - (ATTACHMENT_THRU_DIA + _DRILL_OVERSIZE) / 2.0,
    "inclined cone bore": _HOLE_X_MIN
    * math.cos(
        math.radians(INCLINE_DEG + float(_config.title_block("angular")["value_deg"]))
    )
    - (ATTACHMENT_THRU_DIA + _DRILL_OVERSIZE) / 2.0
    - (round(BORE_DIA, 3) + RUNNING_BORE_BAND[0]) / 2.0,
    "counterbore floor annulus": (
        round(ATTACHMENT_CBORE_DIA, 2)
        - _row(2)
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

# Journal-plan reference sketch (Top plane, all construction).  The 12.5182 deg
# plan angle between the crank axis and the cone-journal axis is REAL model
# geometry -- ConeShaftNormal's angle -- but no face carries it into a view, so
# a construction sketch holds the two axis directions and a driven angular
# reference dimension reports the angle the print has to state.
JOURNAL_REFERENCE_LENGTH = 40.0
JOURNAL_REFERENCE_X = JOURNAL_REFERENCE_LENGTH * math.sin(math.radians(INCLINE_DEG))
JOURNAL_REFERENCE_Z = JOURNAL_REFERENCE_LENGTH * math.cos(math.radians(INCLINE_DEG))
CRANK_BOSS_NEAR_Z = abs(CRANK_BOSS_START_Z)

SURFACE_FINISHES = (
    # The post is a casting that may be left as-cast everywhere else; the
    # faces that MUST be cut say so on the face (the title block's surface row
    # is the process statement "CAST/MACHINED", not a grade).
    SurfaceFinishControl("foot_seat", SEAT_UM, PlanarFace((0, -1, 0), 0.0)),
    # The crankshaft MHA-DT-011 runs in the crank bore, so it is a running
    # journal (rule 5), like the cone bore.
    SurfaceFinishControl(
        "crank_bore",
        MACHINED_UM,
        CylinderFace(CRANK_BORE_DIA, contains_y_mm=CRANK_BORE_HEIGHT),
    ),
    SurfaceFinishControl(
        "journal_bore",
        MACHINED_UM,
        CylinderFace(BORE_DIA, contains_y_mm=BORE_HEIGHT),
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
    "BoreSpacingReference": {"CrankAboveCone"},
}

# Decimal places are product definition: they select the title-block general
# band (.X +/-0.8, .XX +/-0.51, .XXX +/-0.13), so the PART owns them and the
# sheet only proves they survived the import (drawing-simplicity-policy rule 2).
# The head and the cast body/boss sizes take one place -- nothing mates on
# them.  The cone-axis height and the crank-above-cone spacing (each carries
# its own explicit band), the crank-axis height the print repeats only as a
# reference, the two mounting-hole stations and the crank boss's machined
# north-face station take two.  So does the cone boss length (user ruling
# 2026-09-29, option (a)): the shaft collar bears on its north face, half its
# band off the post centre, and that half lands on the cone-tip adjuster's
# engagement (build_dt_drive_train_assembly.TIP_EMBED_WORST_MM), which the .X
# band's 0.40 pushes out of the block's 1.0D working window.  The plan angle
# takes one: the title block holds angles to +/-1 deg, so a second place
# would only suggest a precision nobody sets up for.  Only the two running
# bores take three, and only because their size limits are what deliver the
# `shaft_in_bushing` clearance band.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "MainBodyProfile": {"MainBodyDia": 1},
    "MainBody": {"MainBodyHt": 1},
    "HeadProfile": {"HeadDia": 1},
    "Head": {"HeadHt": 1},
    "AttachmentScrewHoles": {"MountWestX": 2, "MountEastX": 2},
    "CrankBossProfile": {"CrankAxisY": 2, "CrankBossDia": 1},
    "CrankSprocketBoss": {"CrankBossLen": 1},
    "CrankBoreProfile": {"CrankBoreDia": 3},
    "ConeBossProfile": {"JournalAxisY": 2, "ConeBossDia": 1},
    "ConeShaftBoss": {"ConeBossLen": 2},
    "JournalBoreProfile": {"JournalBoreDia": 3},
    # BASIC since #906: it feeds the crank bore's angularity frame, so it
    # prints the model's exact angle.
    "JournalPlanReference": {"InclineAngle": 4},
    "CrankBossStationReference": {"CrankBossStartZ": 2},
    "BoreSpacingReference": {"CrankAboveCone": 2},
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

# Notes identify mating parts and geometry relationships that are not
# recognizable from silhouette alone; every size, band and finish remains on a
# dimension or native symbol (drawing-simplicity-policy rules 1 and 6).
DRAWING_NOTES = "\n".join(
    (
        "CRANK BORE CARRIES MHA-DT-011,",
        "CONE BORE MHA-DT-004; FOOT ON MHA-DT-020.",
        "CONE BOSS END FACES ARE SYMMETRIC ABOUT THE POST AXIS.",
        "DRILL MOUNTING HOLES FROM TOP FACE; CHECK CONE BORE AT BREAKOUT.",
    )
)

# One frame, on the rule-3 allowlist since #906 (USER RULING 2026-09-26,
# option ii): the crank bore's orientation to the cone journal.  The 16T:64T
# crossed mesh loses backlash to yaw and tilt of the crank axis -- the #906
# pose study (dt-logs/crankhub/crank-mesh-angle-20260926.jsonl) measured
# -0.100 at 1 deg of yaw and -0.041 at 1 deg of tilt, toward binding on fixed
# centres -- and a +/- on a dimension cannot hold an axis's
# direction in two planes at once.  A diametral zone of CRANK_BORE_ANGULARITY_MM
# over the boss holds both to about 0.08 deg; the basic angle is the plan
# angle the print already carries.  The running fits stay size limits.
# Datum A alone leaves the zone free to turn about the journal axis, which
# bounds the plan angle but not tilt; the foot seat as secondary datum B
# clocks it, so the same zone holds tilt too.
CRANK_BORE_ANGULARITY_MM = 0.10
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
        f"{CRANK_BORE_ANGULARITY_MM:.2f}",
        CylinderFace(CRANK_BORE_DIA, contains_y_mm=CRANK_BORE_HEIGHT),
        datums=("A", "B"),
        tolerance_zone="diametral",
    ),
)
BASIC_DIMENSIONS = frozenset({"InclineAngle"})
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {}
