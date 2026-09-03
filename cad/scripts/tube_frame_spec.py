r"""Pure-data dimensional contract shared by the tube frame column and drawing.

PURE DATA, no SolidWorks/COM imports (see ``crank_arm_spec`` for the reference
split). ``build_tube_frame`` imports the tube nominals + the marked-dimension
NAME map from here; ``draw_tube_frame`` imports the same nominals for its view
math and keeps exactly ``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations


MM_PER_IN = 25.4

# --- Hollow steel column (legacy part; book ch. 5-6). Ø1.0 in tube, 0.12 in
# wall, topped by an integral polished dome cap. OD rederived from the ch30
# eight views (Ø23.8 +/-1.0 -> 1 in stock); wall + length as in
# build_tube_frame. ---
OUTER_DIA = 1.0 * MM_PER_IN  # 25.4
OUTER_DIA_BAND = (0.00, -0.05)  # (upper, lower) deviations
WALL_THICKNESS = 0.12 * MM_PER_IN  # 3.048
INNER_DIA = OUTER_DIA - 2.0 * WALL_THICKNESS  # 19.304
COLUMN_LENGTH = 994.0  # OVERALL, dome apex included: top at machine 1044.8
# (base top 50.8 + 994.0), a +8.6 capped stub above the top-frame casting's
# rail top 1036.2 and 4.1 above its corner-boss tops 1040.7 -- the ch30 p002
# plate shows the columns ending just above the bosses (2026-09-02 user
# re-read; supersedes the 2026-08-02 +28.6 stub / 1064.8 top)
COLUMN_LENGTH_TOLERANCE_MM = 0.25

# --- Integral dome cap: the polished turned cap pressed into each column top
# (top.png / ch30 p002), modeled integral. Full-width spherical cap: base
# radius OUTER_DIA/2 at the tube mouth, CAP_HEIGHT proud, so the sphere
# radius follows from the chord: R = (a^2 + h^2) / (2h). ---
CAP_HEIGHT = 3.3  # cap rise above the tube mouth (y 1041.5 -> 1044.8)
BODY_LENGTH = COLUMN_LENGTH - CAP_HEIGHT  # 990.7 straight tube below the cap
CAP_SPHERE_RADIUS = (
    (OUTER_DIA / 2.0) ** 2 + CAP_HEIGHT**2
) / (2.0 * CAP_HEIGHT)  # 26.088: SR of the dome

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_tube_frame`` marks exactly these; ``draw_tube_frame`` keeps
# exactly their union across its per-view keep maps. The finished OD and the
# OVERALL length (tube + dome cap; the cap sketch's apex height dim) are the
# acceptance dimensions. The stock-result ID is deliberately not dimensioned;
# the title-block material specification owns the tube wall. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "AnnulusProfile": {"OuterDia"},
    "CapProfile": {"CapApexY"},
}

# Notes: part-specific process facts only, never a tolerance (the OD band
# and the length tolerance ride the model dimensions), never the title block
# (drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = "\n".join(
    (
        "STOCK OD 25.40 MIN AS RECEIVED; ID AS RECEIVED, DO NOT MACHINE.",
        "FINISH OD TO SIZE FULL LENGTH; FACE BOTTOM END SQUARE.",
        "DOME CAP SR26.09 X 3.3: TURN AND BLEND FLUSH WITH THE OD. CAPPED END UP.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 2:1"
LENGTH_VIEW_NOTE = "LENGTH VIEW SCALE 1:5"

