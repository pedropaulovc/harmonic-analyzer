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
# The crank journal runs in this bore: a band on the model dimension.  The
# body, collar and boss outside diameters are as-cast and carry NO band (the
# title block's two-place tolerance governs what the pattern shop delivers).
CRANK_BORE_TOLERANCE_MM = 0.025
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
# The cone gear shaft's integral journal turns in this bore.  Its 0.05 mm
# diametral clearance is already in the nominal (cone_gear_shaft_spec
# JOURNAL_CLEARANCE); the bore may run over but never under it.  (upper,
# lower) deviations, applied to the model dimension by build_cone_pivot_post.
JOURNAL_BORE_BAND = (0.025, 0.000)
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

# Only dimensions that exist natively on the authored model are marked for the
# curated print.  The inclined journal bore (sketched on the journal-normal
# plane) imports into the section cut normal to that axis; the boss length
# (a mid-plane extrude along the journal axis) imports into the plan.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "MainBodyProfile": {"MainBodyDia"},
    "MainBody": {"MainBodyHt"},
    "HeadProfile": {"HeadDia"},
    "Head": {"HeadHt"},
    "CrankBossProfile": {"CrankAxisY", "CrankBossDia"},
    "CrankBoreProfile": {"CrankBoreDia"},
    "ConeShaftBoss": {"ConeBossLen"},
    "JournalBoreProfile": {"JournalBoreDia"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).  Material, paint and
# masking live in the title block; the journal is dimensioned in the
# axis-normal section; the attachment holes by their native callout.  The
# swing angle of the journal prints one place (title-block +/-1 degree).
DRAWING_NOTES = "\n".join(
    (
        "MACHINE THE FOOT SEAT, BOTH BOSS END FACES, BOTH BORES AND THE TOP FACE;",
        "AS-CAST ELSEWHERE. MOUNTING PAIR CENTRED ON THE POST AXIS.",
        "BORE THE CRANK BORE AND THE INCLINED JOURNAL FROM THE FINISHED FOOT SEAT.",
        f"JOURNAL AXIS {INCLINE_DEG:.1f} DEG FROM THE CRANK BORE ABOUT THE POST AXIS; SECTION A-A IS NORMAL TO IT.",
    )
)
