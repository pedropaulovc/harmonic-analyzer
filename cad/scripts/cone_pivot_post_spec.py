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
BORE_HEIGHT = 33.368
CONE_BOSS_DIA = 17.2
BORE_DIA = 12.2808
CONE_BOSS_LENGTH = BLOCK_DIA

# Two vertical ANSI-inch 1/4 Fillister Head Screw counterbores in the top face.
# Ry(180) maps part-local +X to machine -X, so the assembly intentionally mates
# local east/west axes to the opposite platform names.
ATTACHMENT_SPACING = 26.88704
ATTACHMENT_X = ATTACHMENT_SPACING / 2.0
ATTACHMENT_THRU_DIA = 7.14248
ATTACHMENT_CBORE_DIA = 11.50874
ATTACHMENT_CBORE_DEPTH = 6.0198

# V2 B-rep ground truth cascaded through Pedro's boss-length correction and
# the as-cast collar re-read.  The collar step adds a 21.3753..22.0 mm radius
# annulus over the head's 26.6 mm, less the part of it the crank boss already
# occupies.
HARVESTED_VOLUME_MM3 = 114_171.7672
HARVESTED_MASS_KG = 0.822036724

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
# Nothing else on this casting is an accuracy feature, so nothing else carries
# a band: the title block's general grades govern.
RUNNING_BORE_BAND = (0.005, -0.025)

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
    "JournalBoreProfile": {"JournalBoreDia"},
    "JournalPlanReference": {"CrankBossStartZ", "JournalAngle"},
}

# Decimal places are product definition: they select the title-block general
# band (.X +/-0.8, .XX +/-0.51, .XXX +/-0.13), so the PART owns them and the
# sheet only proves they survived the import (drawing-simplicity-policy rule 2).
# The as-cast collar diameter and the cast body/boss sizes take one place --
# nothing mates on them.  The two bearing-axis heights, the two mounting-hole
# stations and the machined spot-face station take two.  Only the two running
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
    "JournalBoreProfile": {"JournalBoreDia": 3},
    "JournalPlanReference": {"CrankBossStartZ": 2, "JournalAngle": 2},
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

# Notes identify the mating parts the two journals and the foot serve; every
# size, band and finish on this sheet is carried by a dimension or a native
# symbol instead (drawing-simplicity-policy rules 1 and 6).
DRAWING_NOTES = "\n".join(
    (
        "CRANK BORE CARRIES CRANKSHAFT MHA-026.",
        "CONE BORE CARRIES CONE GEAR SHAFT MHA-014.",
        "FOOT SEATS ON CONE SWING PLATFORM MHA-091.",
    )
)

# The post carries no datums or feature-control frames under the drawing
# simplicity policy: nothing on it is the cam/follower mate, and its two
# running fits are held by size limits, not by position frames.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {}
