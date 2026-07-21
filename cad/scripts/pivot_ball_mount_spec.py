r"""Pure-data dimensional contract shared by the pivot-ball-mount part and drawing.

The marked-dimension map lives here so a change rebuilds both the SLDPRT and the
SLDDRW recipes from one source (see build_pivot_ball_mount.py for the geometry).
"""

from __future__ import annotations


# Chrome-look ball-end pillar carrying each pivot shaft end: a seat pad, a stem,
# and a Ø13 ball cross-bored for the Ø6.35 pivot shaft. Four are used (two on
# the rocker-support apexes, two on the top-frame west rail).
BALL_DIA = 13.0  # the pivot ball (spherical)
BALL_CENTER_H = 25.2  # ball + cross-bore axis above the seat
BASE_DIA = 13.0  # seat pad diameter
BASE_H = 4.0  # seat pad height
STEM_DIA = 8.0  # pillar between the pad and the ball
BORE_DIA = 6.5  # shaft cross-bore
SHAFT_DIA = 6.35  # the mating Ø6.35 pivot shaft

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BallMountProfile": {"BallRise", "BallRadius", "BaseRadius", "BaseHeight"},
    "ShaftBoreProfile": {"ShaftBoreDia"},
}

DRAWING_NOTES = "\n".join(
    (
        "HEIGHTS ARE AXIS-TO-SEAT (DATUM A).",
        "BALL DIA 13 (SPHERICAL) ON A DIA 13 X 4 SEAT PAD, DIA 8 STEM;",
        "  BALL + CROSS-BORE AXIS CENTERED ON THE PILLAR AXIS.",
        "SHAFT CROSS-BORE DIA 6.5 THRU THE BALL CENTRE: CLOSE RUNNING",
        "  FIT ON THE DIA 6.35 PIVOT SHAFT.",
        "MATERIAL AISI 1018 STEEL; POLISHED, NICKEL PLATED. 4 USED.",
    )
)
