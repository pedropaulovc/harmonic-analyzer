r"""Pure-data dimensional contract shared by the pivot-ball-mount part and drawing.

The marked-dimension map lives here so a change rebuilds both the SLDPRT and the
SLDDRW recipes from one source (see build_pivot_ball_mount.py for the geometry).
"""

from __future__ import annotations


# Nickel-plated ball-end pillar carrying each pivot shaft end: a seat pad, a stem,
# and a Ø13 ball cross-bored for the Ø6.35 pivot shaft. Four are used (two on
# the rocker-support apexes, two on the top-frame west rail).
BALL_DIA = 13.0  # the pivot ball (spherical)
BALL_CENTER_H = 25.2  # ball + cross-bore axis above the seat
BASE_DIA = 13.0  # seat pad diameter
BASE_H = 4.0  # seat pad height
STEM_DIA = 8.0  # pillar between the pad and the ball
BORE_DIA = 6.5  # shaft cross-bore
SHAFT_DIA = 6.35  # the mating Ø6.35 pivot shaft
SHAFT_BORE_DIA_BAND = (0.00, -0.05)
BASE_HEIGHT_TOLERANCE_MM = 0.05

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BallMountProfile": {"BallRise", "BaseHeight"},
    "ShaftBoreProfile": {"ShaftBoreDia"},
}

DRAWING_NOTES = "\n".join(
    (
        f"DATUM A IS SEAT FACE. DATUM B IS DIA {STEM_DIA:.0f} STEM AXIS.",
        f"{BALL_CENTER_H:.2f} BASIC LOCATES SPHERE CENTER AND CROSS-BORE AXIS FROM A.",
        f"MATING SHAFT MAX DIA {SHAFT_DIA:.2f}.",
        "BALL/STEM + STEM/PAD SHOULDERS: EDGE BREAK 0.10 MAX;",
        "NO TRANSITION BLEND OR UNDERCUT AT EITHER SHOULDER.",
        "EXTERIOR FINISH SYMBOL APPLIES TO BALL, STEM, AND PAD OD AFTER PLATE.",
    )
)
