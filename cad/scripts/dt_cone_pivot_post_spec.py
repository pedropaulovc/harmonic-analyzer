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
"""

from __future__ import annotations

import math

import _config
from _inch import inch
from _gtol_cylinder import CylinderFace
from _gtol_controls import GeometricControl, PartDatum
from _gtol_planar import PlanarFace
from _surface_finish import MACHINED_UM, SEAT_UM, SurfaceFinishControl
from dt_post_mount_stack import (
    CONE_AXIS_HEIGHT_MM,
    POST_BODY_HEIGHT_MM,
    POST_MOUNT_COUNTERBORE_DEPTH_MM,
)


MM_PER_IN = 25.4

# Main casting: the upper 1-1/16 in is a very slightly larger head around the
# main body; both cylinders share the vertical body/swing axis.  All-inch
# experiment: the body is 1-5/8 in (was 42.011) and the head 1-11/16 in (was
# v36's harvested 42.7506, user ruling 2026-09-28).  The head is a one-place
# reference size -- nothing mates on it; the body below it is the
# locating/bore cylinder and keeps its turned size.
BLOCK_DIA = inch(13, 8)
BLOCK_HEIGHT = POST_BODY_HEIGHT_MM
HEAD_DIA = inch(27, 16)
HEAD_HEIGHT = inch(17, 16)
HEAD_BASE_Y = BLOCK_HEIGHT - HEAD_HEIGHT
# Straight crank/sprocket journal in the harvested PART frame.  It starts at
# local -Z and projects along local +Z.  The assembly's exact Ry(180)
# installation maps that long boss toward machine -Z.  All-inch experiment:
# the boss runs 2-13/16 in (Pedro's corrected 2.8360 in source dimension,
# snapped).
#
# v36 geometry (user ruling 2026-09-28): the crankshaft MHA-DT-011 runs directly
# in the crank bore, whose height follows the crossed-crank config
# above the unchanged foot -- no eccentric bushing, no drop, fixed centres.
# The boss starts at the head's tangent plane, so its north face stands
# HEAD_DIA / 2 from the post
# axis, and runs CRANK_BOSS_LENGTH from there; nothing stands proud of
# that face inside the boss disc, so there is no spot face, retreat or run-out.
# The north face is the boss's machined end, stationed from the post axis on
# the print.
# The running bore is 15/32 in, the same reamer as the cone journal (1/32: the
# nearest 1/16, 7/16 in, leaves the crankshaft's relieved middle no room
# between its Ø3/8 through shaft and the journal at print-worst).
CRANK_BOSS_DIA = inch(7, 8)
CRANK_BORE_DIA = inch(15, 32)
CRANK_BORE_HEIGHT = _config.machine("gear_train", "crank_axis_height_mm")
CRANK_BORE_OFFSET = 0.0
CRANK_BOSS_NORTH_FACE = HEAD_DIA / 2.0
CRANK_BOSS_START_Z = -CRANK_BOSS_NORTH_FACE
CRANK_BOSS_LENGTH = inch(45, 16)
CRANK_BOSS_LENGTH_IN = CRANK_BOSS_LENGTH / MM_PER_IN
CRANK_BOSS_END_Z = CRANK_BOSS_START_Z + CRANK_BOSS_LENGTH
if CRANK_BOSS_END_Z <= CRANK_BOSS_NORTH_FACE:
    raise AssertionError("crank boss no longer runs through the whole head")

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
BORE_HEIGHT = CONE_AXIS_HEIGHT_MM
# Cone boss 11/16 in (was 17.2); the journal is reamed 15/32 in (was 12.2808;
# 1/32: the nearest 1/16, 1/2 in, leaves the cone shaft's 5/8 in collar a
# thrust ring with no room for its edge breaks over the rule-17 floor).
CONE_BOSS_DIA = inch(11, 16)
BORE_DIA = inch(15, 32)
CONE_BOSS_LENGTH = BLOCK_DIA

# Two vertical ANSI-inch 1/4 Fillister Head Screw counterbores in the top face.
# Ry(180) maps part-local +X to machine -X, so the assembly intentionally mates
# local east/west axes to the opposite platform names.
#
# MHA-VN-031 must provide a shank long enough to reach the platform from the
# counterbore floor, BLOCK_HEIGHT - ATTACHMENT_CBORE_DEPTH.  The 29/64 x 1/4
# deep counterbore takes its ASME B18.6.3 fillister head (0.237 in high) over a
# 9/32 close-fit drill for the 1/4-20 shank (inch drill chart); the
# purchased-stock spec owns the actual head envelope, stock-length,
# cut-to-fit and engagement guards.
ATTACHMENT_THRU_DIA = inch(9, 32)
ATTACHMENT_CBORE_DIA = inch(29, 64)
ATTACHMENT_CBORE_DEPTH = POST_MOUNT_COUNTERBORE_DEPTH_MM
WEB_FLOOR_MM = 1.5


def _row(places: int) -> float:
    return float(str(_config.title_block(f"linear_{places}pl")["display"]).lstrip("±"))


# R2: the mounting-hole centres must keep the policy's 1.5 mm hard floor to
# the head OD at the printed limits.  The head prints Ø42.9 (.X); the machined
# counterbore's native hole callout prints Ø11.51 (.XX), unlike its
# twist-drilled through hole (+0.10 / 0).  Each centre prints .XX.  All-inch
# experiment: the matched post/platform pattern stands on the outermost 1/16 in
# station that retains the floor at all three closing corners (1/2 in each
# side of the axis, 1 in apart).
_HEAD_R_PRINT_MIN = (round(HEAD_DIA, 1) - _row(1)) / 2.0
_CBORE_R_PRINT_MAX = (round(ATTACHMENT_CBORE_DIA, 2) + _row(2)) / 2.0
_ATTACHMENT_X_MAX = (
    _HEAD_R_PRINT_MIN - _CBORE_R_PRINT_MAX - _row(2) - WEB_FLOOR_MM
)
ATTACHMENT_X = inch(1, 2)
ATTACHMENT_SPACING = 2.0 * ATTACHMENT_X
MOUNT_HEAD_WEB_WORST = _HEAD_R_PRINT_MIN - (ATTACHMENT_X + _row(2)) - _CBORE_R_PRINT_MAX
if MOUNT_HEAD_WEB_WORST + 1e-9 < WEB_FLOOR_MM:
    raise AssertionError("mounting counterbore breaches the head's print-worst wall")
if ATTACHMENT_X + inch(1, 16) <= _ATTACHMENT_X_MAX + 1e-9:
    raise AssertionError("mounting holes are farther inward than the 1/16 in grid requires")

# Final solid volume, the sum of the per-feature analytic terms the build
# checks natively one feature at a time (build_dt_cone_pivot_post.py asserts
# the sum at import against its own Simpson quadrature):
#
#   body      pi*(BLOCK_DIA/2)^2*BLOCK_HEIGHT
#   head      pi*((HEAD_DIA/2)^2 - (BLOCK_DIA/2)^2)*HEAD_HEIGHT
#   crank boss outside the head cylinder  pi*rb^2*Lb - S(rb, HEAD_DIA/2)
#   crank bore pi*(CRANK_BORE_DIA/2)^2*Lb
#   cone pads outside the body cylinder   pi*rc^2*Lc - S(rc, BLOCK_DIA/2)
#   cone bore pi*(BORE_DIA/2)^2*Lc
#   2x (thru pi*(ATTACHMENT_THRU_DIA/2)^2*(BLOCK_HEIGHT-cbore_depth)
#       + cbore pi*(ATTACHMENT_CBORE_DIA/2)^2*cbore_depth)
#
# S(r, R) is the closed-form intersection of two perpendicular cylinders of
# radii r <= R crossing on axis (the boss starts on the head's tangent plane
# and the pads end on the body's, so each overlap is the whole bicylinder):
# 8R/3 * ((R^2 + r^2) E(m) - (R^2 - r^2) K(m)), m = (r/R)^2.  The 2026-09-21
# farm build of a Ø44-collar recipe read 121 575.3 against its constant: that
# recipe had never bored the crank boss, because the bore cut's default
# direction (opposite the sketch normal) found the collar to bite instead of
# flipping into the boss.  The build still reverses that cut explicitly.
# Mass at gray iron 7.20 g/cc.


def _elliptic_k_e(m: float) -> tuple[float, float]:
    """Complete elliptic integrals K(m), E(m) by the arithmetic-geometric mean."""
    a, b = 1.0, math.sqrt(1.0 - m)
    c_sq_sum = m / 2.0  # 2^(n-1) c_n^2 at n = 0, c_0^2 = m
    weight = 0.5
    while abs(a - b) > 1e-15:
        c = (a - b) / 2.0
        a, b = (a + b) / 2.0, math.sqrt(a * b)
        weight *= 2.0
        c_sq_sum += weight * c * c
    k = math.pi / (2.0 * a)
    return k, k * (1.0 - c_sq_sum)


def _bicylinder_mm3(r: float, big_r: float) -> float:
    """Volume common to two perpendicular cylinders of radii r < big_r whose axes cross."""
    if not 0.0 < r < big_r:
        raise AssertionError("bicylinder closed form needs the smaller radius first")
    k, e = _elliptic_k_e((r / big_r) ** 2)
    return 8.0 * big_r / 3.0 * ((big_r**2 + r**2) * e - (big_r**2 - r**2) * k)


HARVESTED_VOLUME_MM3 = (
    math.pi * (BLOCK_DIA / 2.0) ** 2 * BLOCK_HEIGHT
    + math.pi * ((HEAD_DIA / 2.0) ** 2 - (BLOCK_DIA / 2.0) ** 2) * HEAD_HEIGHT
    + math.pi * (CRANK_BOSS_DIA / 2.0) ** 2 * CRANK_BOSS_LENGTH
    - _bicylinder_mm3(CRANK_BOSS_DIA / 2.0, HEAD_DIA / 2.0)
    - math.pi * (CRANK_BORE_DIA / 2.0) ** 2 * CRANK_BOSS_LENGTH
    + math.pi * (CONE_BOSS_DIA / 2.0) ** 2 * CONE_BOSS_LENGTH
    - _bicylinder_mm3(CONE_BOSS_DIA / 2.0, BLOCK_DIA / 2.0)
    - math.pi * (BORE_DIA / 2.0) ** 2 * CONE_BOSS_LENGTH
    - 2.0
    * (
        math.pi * (ATTACHMENT_THRU_DIA / 2.0) ** 2 * (BLOCK_HEIGHT - ATTACHMENT_CBORE_DEPTH)
        + math.pi * (ATTACHMENT_CBORE_DIA / 2.0) ** 2 * ATTACHMENT_CBORE_DEPTH
    )
)
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
# budget is now crank_mesh_stack.standard_check() backlash > 0, read at the low
# end of this unchanged U31 band and the retained angularity frame. The
# upper +0.37 bound predates that no-bind-only requirement; keep it as ruled,
# without treating its former backlash-window derivation as a current gate.
# The current spacing follows the physical fixed-centre pair; its band stays
# +0.37/0.  How the shop holds it is theirs (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)).
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

# Webs around the Ø11.438 crank bore, at print-worst (drawing-guidelines.md rule 17 (walls and webs): 2.0
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
    BLOCK_HEIGHT - _row(1) - _CRANK_AXIS_Y_MAX - (CRANK_BOSS_DIA + _row(1)) / 2.0
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

# Journal-plan reference sketch (Top plane, all construction).  The configured
# plan angle between the crank axis and the cone-journal axis is REAL model
# geometry -- ConeShaftNormal's angle -- but no face carries it into a view.
# Two construction rays and a driving angular dimension use the same
# ConeIncline owner as the actual plane.
JOURNAL_REFERENCE_LENGTH = inch(25, 16)
JOURNAL_REFERENCE_X = JOURNAL_REFERENCE_LENGTH * math.sin(math.radians(INCLINE_DEG))
JOURNAL_REFERENCE_Z = JOURNAL_REFERENCE_LENGTH * math.cos(math.radians(INCLINE_DEG))
CRANK_BOSS_NEAR_Z = abs(CRANK_BOSS_START_Z)

SURFACE_FINISHES = (
    # The post is a casting that may be left as-cast everywhere else; the
    # faces that MUST be cut say so on the face (the title block's surface row
    # is the process statement "CAST/MACHINED", not a grade).
    SurfaceFinishControl("foot_seat", SEAT_UM, PlanarFace((0, -1, 0), 0.0)),
    # The crankshaft MHA-DT-011 runs in the crank bore, so it is a running
    # journal (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)), like the cone bore.
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
# sheet only proves they survived the import (drawing-simplicity-policy.md `How the repository implements the guidelines`).
# The head and the cast body/boss sizes take one place -- nothing mates on
# them.  The cone-axis height and the crank-above-cone spacing (each carries
# its own explicit band), the crank-axis height the print repeats only as a
# reference, the two mounting-hole stations and the crank boss's machined
# north-face station take two.  So does the cone boss length (user ruling
# 2026-09-29, option (a)): the shaft collar bears on its north face, half its
# band off the post centre, and that half lands on the cone-tip adjuster's
# engagement (build_dt_drive_train_assembly.TIP_EMBED_WORST_MM), which the .X
# band's 0.40 pushes out of the block's 1.0D working window.  The basic plan
# angle feeds the retained crank-bore angularity frame; its four places spell
# the configured geometry, not a tighter general angular band.  Only the two
# running bores take three, because their size limits deliver the
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
    # BASIC since #906: it feeds the crank bore's angularity frame; four places
    # retain the configured nominal without changing the frame's zone.
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
# dimension or native symbol (drawing-guidelines.md rule 2 (the title block is the general specification) and drawing-guidelines.md rule 7 (notes: few, flagged, never a method)).
DRAWING_NOTES = "\n".join(
    (
        "CRANK BORE CARRIES MHA-DT-011,",
        "CONE BORE MHA-DT-004; FOOT ON MHA-DT-020.",
        "CONE BOSS END FACES ARE SYMMETRIC ABOUT THE POST AXIS.",
        "DRILL MOUNTING HOLES FROM TOP FACE; CHECK CONE BORE AT BREAKOUT.",
    )
)

# One frame, on the drawing-simplicity-policy.md `GD&T allowlist (rule 5)` allowlist since #906 (USER RULING 2026-09-26,
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
