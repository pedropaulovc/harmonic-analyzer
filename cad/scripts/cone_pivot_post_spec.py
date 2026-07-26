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


MM_PER_IN = 25.4

# Main casting: the upper 26.6 mm is a very slightly larger collar around the
# main body.  Both cylinders share the vertical body/swing axis.
BLOCK_DIA = 42.011
BLOCK_HEIGHT = 86.0
HEAD_DIA = 42.7506
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
CRANK_BOSS_START_Z = -HEAD_DIA / 2.0
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

# V2 B-rep ground truth cascaded through Pedro's boss-length correction.  The
# correction removes a uniform annular segment beyond the main casting.
HARVESTED_VOLUME_MM3 = 112_302.9406
HARVESTED_MASS_KG = 0.808581173

# Datum-coordinate definition of the inclined journal axis.  The bore passes
# through the body axis at y=BORE_HEIGHT and points toward +X/+Z.
_JOURNAL_SIN = math.sin(math.radians(INCLINE_DEG))
_JOURNAL_COS = math.cos(math.radians(INCLINE_DEG))
JOURNAL_AXIS_SECOND_POINT_DISTANCE = 100.0
JOURNAL_AXIS_POINTS = (
    ("P", 0.0, BORE_HEIGHT, 0.0),
    (
        "Q",
        JOURNAL_AXIS_SECOND_POINT_DISTANCE * _JOURNAL_SIN,
        BORE_HEIGHT,
        JOURNAL_AXIS_SECOND_POINT_DISTANCE * _JOURNAL_COS,
    ),
)
JOURNAL_AXIS_ORIENTATION_NOTE = "\n".join(
    (
        "O = A/B INTERSECTION; +Y ALONG B AWAY FROM A",
        "+X RIGHT; +Z DOWN IN UPPER PLAN",
    )
)

# Only dimensions that exist natively on the authored model are marked for the
# curated print.  Boss, journal and counterbore callouts are sourced from these
# same constants as attached notes, so the drawing cannot drift from the part.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "MainBodyProfile": {"MainBodyDia"},
    "MainBody": {"MainBodyHt"},
    "HeadProfile": {"HeadDia"},
    "Head": {"HeadHt"},
    "CrankBossProfile": {"CrankAxisY", "CrankBossDia"},
    "CrankBoreProfile": {"CrankBoreDia"},
}

DRAWING_NOTES = "\n".join(
    (
        "CAST ASTM A48 CLASS 30; MACHINE FOOT, BOSSES, BORES AND MOUNTING HOLES.",
        "DATUM A IS FOOT SEAT; B IS MAIN-BODY OD; C IS INCLINED JOURNAL AXIS.",
        f"CONE BOSS DIA {CONE_BOSS_DIA:.3f}; JOURNAL BORE DIA {BORE_DIA:.4f} THRU.",
        f"JOURNAL AXIS INTERSECTS B AT BASIC {BORE_HEIGHT:.3f} ABOVE A; "
        f"ANGLE {INCLINE_DEG:.4f} DEG ABOUT +Y.",
        f"CRANK BOSS DIA {CRANK_BOSS_DIA:.3f}; BORE DIA {CRANK_BORE_DIA:.3f} THRU "
        f"AT BASIC {CRANK_BORE_HEIGHT:.3f} ABOVE A.",
        f"2X 1/4 FILLISTER C'BORE DIA {ATTACHMENT_CBORE_DIA:.5f} X "
        f"{ATTACHMENT_CBORE_DEPTH:.4f} DEEP; THRU DIA {ATTACHMENT_THRU_DIA:.5f}; "
        f"C-C {ATTACHMENT_SPACING:.5f}.",
    )
)
