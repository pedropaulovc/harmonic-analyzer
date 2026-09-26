r"""Pure-data dimensional contract shared by the cone pivot post and drawing.

The hand-modelled ``cone-pivot-post-v2.SLDPRT`` is the dimensional authority.
Its 86 mm height was manually rederived from the second ch30 eight-view
(``references/albert-michelsons-harmonic-analyzer/ch30_images/page003_img01.png``).
The casting proportions were manually rederived from the two sharp ch11 details
(``ch11_images/page002_img05.jpeg`` and ``page002_img06.jpeg``).  Those photos
support proportions, not manufacturing tolerances; the decimal values below are
the exact dimensions harvested from v2's feature tree.
"""

from __future__ import annotations

import math

from _gtol_spec import CylinderFace, PlanarFace
from _surface_finish import MACHINED_UM, SEAT_UM, SurfaceFinishControl

import cone_post_dowel_spec as _dowel
from cone_pivot_post_installation import POST_ROTATION_Y_DEG


MM_PER_IN = 25.4

# Main casting: the upper 26.6 mm is an integral AS-CAST collar around the
# turned body, and it is a real step, not a rounding artefact.  Four sharp
# manual frames (ch11 page002_img04/05/06, ch30 page003_img01) show the seam
# 59.4-60.5 mm above the foot with a 0.8-1.27 mm radial step, orange-peel cast
# skin above it and a turned surface below, giving a collar of 44.0 +/- 0.4.
# The collar is therefore a one-place as-cast reference size; the body below
# it is the locating/bore cylinder and keeps its turned size.
BLOCK_DIA = 42.011
BLOCK_HEIGHT = 86.0
HEAD_DIA = 44.0
HEAD_HEIGHT = 26.6
HEAD_BASE_Y = BLOCK_HEIGHT - HEAD_HEIGHT

# Straight crank/sprocket journal in the harvested PART frame.  It starts at
# local -Z and projects along local +Z to +50.6591.  The assembly's exact
# Ry(180) installation maps that long boss toward machine -Z.  Keep Pedro's
# corrected source dimension in inches: 2.8360 in replaces the 2.85086614 in
# initial derivation.
CRANK_BOSS_DIA = 21.93
CRANK_BORE_DIA = 11.438
CRANK_BORE_HEIGHT = 72.7
CRANK_BORE_OFFSET = 0.0
# The boss's near face is a MACHINED SPOT FACE, not the rim of the cast
# collar: it is stationed from the post axis and the print dimensions it that
# way, so it does not follow the collar diameter.  Decoupling it also keeps
# the assembly's 0.25 mm north and 10.255 mm south crank-sprocket gaps.
CRANK_BOSS_NORTH_FACE = 21.3753
CRANK_BOSS_START_Z = -CRANK_BOSS_NORTH_FACE
CRANK_BOSS_LENGTH_IN = 2.8360
CRANK_BOSS_LENGTH = CRANK_BOSS_LENGTH_IN * MM_PER_IN
CRANK_BOSS_END_Z = CRANK_BOSS_START_Z + CRANK_BOSS_LENGTH

# Inclined cone-shaft journal.  Unlike v1, the 12.5182-degree incline is baked
# into the part; downstream placement composes it with the exact Ry(180)
# installation instead of re-authoring the harvested feature frame.
INCLINE_DEG = 12.5182
CONE_AXIS_VIEW = "CONE JOURNAL"
BORE_HEIGHT = 33.368
CONE_BOSS_DIA = 17.2
BORE_DIA = 12.2808
CONE_BOSS_LENGTH = BLOCK_DIA

# Two vertical ANSI-inch 1/4 Fillister Head Screw counterbores in the top face.
# Ry(180) maps part-local +X to machine -X, so the assembly intentionally mates
# local east/west axes to the opposite platform names.
#
# The screw is MHA-142, a 1/4-20 x 3-1/2 slotted fillister (MSC 40923898, user
# ruling U37c) cut to 86.0 at assembly.  Its ASME B18.6.3 head (dia 9.1-9.5 x
# 5.5 overall) sits about 0.5 below the top face in the dia 11.509 x 6.02
# counterbore.  Deepening the counterbore for a shorter screw is not an
# option: at 16.15 it would pass the crank bore with a 1.20 worst-case web.
ATTACHMENT_SPACING = 26.88704
ATTACHMENT_X = ATTACHMENT_SPACING / 2.0
ATTACHMENT_THRU_DIA = 7.14248
ATTACHMENT_CBORE_DIA = 11.50874
ATTACHMENT_CBORE_DEPTH = 6.0198

# #917 S1 dowel pair: two blind Ø.1255 slip-fit reams from the foot face,
# match-drilled through MHA-091 after fit-up.  The pattern is the platform's
# (cone_post_dowel_spec, plate-local from the pivot), carried into this part's
# frame the way the assembly installs it: the plate's Ry(+INCLINE) takes it to
# machine axes about the post axis (the pair's midpoint), and the post's own
# Ry(POST_ROTATION_Y_DEG) is undone.  It lands on the crank-axis diameter
# (part Z), at the screws' pitch radius, 90 deg from them.
POST_DOWEL_CENTRE_PLATE_XZ = tuple(
    sum(axis) / 2.0 for axis in zip(*_dowel.POST_DOWEL_PLATE_XZ, strict=True)
)


def _ry(x: float, z: float, degrees: float) -> tuple[float, float]:
    """Ry(degrees) on a plan (x, z), the assembly's convention
    (build_drive_train_assembly._plate_local_to_machine)."""
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return (x * c + z * s, -x * s + z * c)


def _plate_to_post_xz(x: float, z: float) -> tuple[float, float]:
    machine = _ry(
        x - POST_DOWEL_CENTRE_PLATE_XZ[0], z - POST_DOWEL_CENTRE_PLATE_XZ[1], INCLINE_DEG
    )
    post = _ry(*machine, -POST_ROTATION_Y_DEG)
    # The plate literal is three-place; so is the post's station.
    return tuple(round(value, 3) + 0.0 for value in post)


POST_DOWEL_XZ = tuple(_plate_to_post_xz(x, z) for x, z in _dowel.POST_DOWEL_PLATE_XZ)
POST_DOWEL_RADIUS = math.dist(*POST_DOWEL_XZ) / 2.0
if any(abs(x) > 1e-9 for x, _z in POST_DOWEL_XZ):
    raise AssertionError(f"post dowels left the crank-axis diameter: {POST_DOWEL_XZ}")
if abs(POST_DOWEL_RADIUS - ATTACHMENT_X) > 1e-3:
    raise AssertionError("post dowels are off the attachment screws' pitch radius")
POST_DOWEL_REAM_DIA = _dowel.POST_DOWEL_REAM_DIA
POST_DOWEL_BLIND_DEPTH = _dowel.POST_DOWEL_BLIND_DEPTH

# Final solid volume, the sum of the per-feature analytic terms the build
# checks natively one feature at a time (build_cone_pivot_post.py asserts
# the sum at import):
#
#   body      pi*21.0055^2*86                       = +119 210.4620
#   collar    pi*(22^2 - 21.0055^2)*26.6            = +  3 574.0470
#   crank boss outside the collar cylinder          = + 11 215.7157
#   spot face (collar proud of z=-21.3753 in disc)  = -     93.1451
#   crank bore pi*5.719^2*72.0344                   = -  7 401.6752
#   cone pads outside the body cylinder             = +    209.0550
#   cone bore pi*6.1404^2*42.011                    = -  4 976.2960
#   2x (thru pi*3.57124^2*79.9802 + cbore pi*5.75437^2*6.0198) = - 7 661.5921
#   2x dowel ream (pi*1.59385^2*8.5 + 118 deg point, #917 S1)  = -   140.7684
#                                                   = 113 935.8038
#
# The 2026-09-21 farm build of the previous recipe read 121 575.3: it had
# never bored the crank boss (7 401.7) and had only nicked the 45 mm^3 collar
# sliver behind the spot-face plane inside the bore disc -- a cut whose
# default direction (opposite the sketch normal) found the Ø44 collar to bite
# instead of auto-flipping into the boss.  Mass at gray iron 7.20 g/cc.
HARVESTED_VOLUME_MM3 = 113_935.8038
HARVESTED_MASS_KG = 0.820338

# Both bores are running journals, so both carry the SAME size band -- the one
# the `shaft_in_bushing` fit class needs and no tighter (tolerance-policy.md,
# "How a critical-feature tolerance is decided", step 6b).  Each mating shaft
# is turned to (bore nominal - 0.05) with the fleet's `SHAFT_H` (0/-0.020)
# band, so a bore held +0.005/-0.025 delivers exactly the class's 0.025..0.075
# mm diametral clearance:
#
#   crank:   shaft 11.368..11.388  bore 11.413..11.443  (crankshaft MHA-026)
#   journal: shaft 12.2108..12.2308 bore 12.2558..12.2858 (cone shaft MHA-014)
#
# Apart from the spacing between them (below) and #917's dowel reams (their
# band is the reamer's, carried on the hole feature), nothing else on this
# casting is an accuracy feature, so nothing else carries a band: the title
# block's general grades govern.
RUNNING_BORE_BAND = (0.005, -0.025)

# Crank-above-cone bore spacing (user ruling U31, 2026-09-23, option 3a).  The
# crank axis is located FROM THE CONE AXIS, not from the foot: the 16T:64T
# crank mesh closes on that spacing alone, and two foot-referenced .XX heights
# stacked to +/-1.02 mm -- enough to jam the pair or let it skip.  The band is
# the mesh contract less every other contributor, worst case (numbers from
# build_drive_train_assembly, 14.5 deg pressure angle):
#
#   centre-distance contract dC (depth band)          -0.150 .. +0.540
#   running float, loaded: gears push apart, so it only OPENS the mesh:
#     crank 0.0375 + 0.075/72.03 * 5.65 overhang       0      .. +0.043
#     cone  0.0375 + 0.075/42.01 * 5.68 overhang       0      .. +0.048
#   cone-bore plan angle +/-1 deg (title block):
#     64T 26.69 from the post axis -> dDX 0.444 * DX/C 0.142  +/-0.063
#   64T axial station +/-0.5 on the inclined shaft -> dC  +/-0.015
#   left for this spacing (dC)                        -0.072 .. +0.371
#   / dC/dDY = DY/C = 39.332/39.735 = 0.990           -0.073 .. +0.374
#
# The close side is then set by the assembly CHECK, not by running: backlash
# is read with the crank at rest, where gravity drops the crankshaft up to
# 0.043 toward the 64T.  B = 0.28 + 0.517 * dC (14.5 deg), so the static
# reading at a spacing of -0.002 (39.33 +0 against the 39.332 model) is
# 0.28 - 0.517 * (0.002 + 0.078 + 0.043) = 0.216, and at +0.368 it is
# 0.28 + 0.517 * (0.364 + 0.078 + 0.048) = 0.533: the drive-train sheet's
# 0.20-0.55 acceptance.  Printed 39.33 +0.37/0 (aim 39.51) is the post's one
# tight band, held by boring both journals in one setup (DRAWING_NOTES); a
# post bored outside it is rescued by opening the crank bore for an eccentric
# bushing, not scrapped.
CRANK_ABOVE_CONE = CRANK_BORE_HEIGHT - BORE_HEIGHT
CRANK_ABOVE_CONE_BAND = (0.37, 0.0)

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
    # The post is a casting that may be left as-cast everywhere else; the three
    # faces that MUST be cut say so on the face (the title block's surface row
    # is the process statement "CAST/MACHINED", not a grade).
    SurfaceFinishControl("foot_seat", SEAT_UM, PlanarFace((0, -1, 0), 0.0)),
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
    "JournalPlanReference": {"CrankBossStartZ", "InclineAngle"},
    "BoreSpacingReference": {"CrankAboveCone"},
}

# Decimal places are product definition: they select the title-block general
# band (.X +/-0.8, .XX +/-0.51, .XXX +/-0.13), so the PART owns them and the
# sheet only proves they survived the import (drawing-simplicity-policy rule 2).
# The as-cast collar diameter and the cast body/boss sizes take one place --
# nothing mates on them.  The cone-axis height, the crank-above-cone spacing
# (which carries its own explicit band), the crank-axis height the print
# repeats only as a reference, the two mounting-hole stations and the machined
# spot-face station take two.  The plan angle takes
# one: the title block holds angles to +/-1 deg, so a second place would only
# suggest a precision nobody sets up for.  Only the two running bores take
# three, and only because their size limits are what deliver the
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
    "ConeShaftBoss": {"ConeBossLen": 1},
    "JournalBoreProfile": {"JournalBoreDia": 3},
    "JournalPlanReference": {"CrankBossStartZ": 2, "InclineAngle": 1},
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
        "CRANK BORE CARRIES MHA-026, CONE BORE MHA-014; FOOT ON MHA-091.",
        "CONE BOSS END FACES ARE SYMMETRIC ABOUT THE POST AXIS.",
        "BORE BOTH IN ONE SETUP; INSPECT BORE-TO-BORE BEFORE UNCLAMPING.",
        "DRILL MOUNTING HOLES FROM TOP FACE; CHECK CONE BORE AT BREAKOUT.",
    )
)

# The post carries no datums or feature-control frames under the drawing
# simplicity policy: nothing on it is the cam/follower mate, and its two
# running fits are held by size limits, not by position frames.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {}
