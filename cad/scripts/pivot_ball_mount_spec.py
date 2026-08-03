r"""Pure-data dimensional contract shared by the pivot-ball-mount part and drawing.

The marked-dimension map lives here so a change rebuilds both the SLDPRT and the
SLDDRW recipes from one source (see build_pivot_ball_mount.py for the geometry).
"""

from __future__ import annotations

from _gtol_spec import CylinderFace, SphereFace
from _surface_finish import GROUND_UM, MACHINED_UM, SurfaceFinishControl


# Nickel-plated ball-end pillar carrying each pivot shaft end: a seat pad, a stem,
# and a Ø13 ball cross-bored for the Ø6.35 pivot shaft. Two are used, on the
# rocker-support apexes (the top-lever fulcrum's end mounts are the black
# fulcrum-keeper brackets since the 2026-08-02 rederive).
BALL_DIA = 13.0  # the pivot ball (spherical)
BALL_CENTER_H = 25.2  # ball + cross-bore axis above the seat
BASE_DIA = 13.0  # seat pad diameter
BASE_H = 4.0  # seat pad height
STEM_DIA = 8.0  # pillar between the pad and the ball
BORE_DIA = 6.5  # shaft cross-bore
SHAFT_DIA = 6.35  # the mating Ø6.35 pivot shaft
SHAFT_BORE_DIA_BAND = (0.00, -0.05)
BASE_HEIGHT_TOLERANCE_MM = 0.05
BALL_DIAMETER_TOLERANCE_MM = 0.05
BASE_DIAMETER_TOLERANCE_MM = 0.05
STEM_DIAMETER_TOLERANCE_MM = 0.05

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "cross_bore",
        MACHINED_UM,
        CylinderFace(BORE_DIA, contains_y_mm=BALL_CENTER_H),
    ),
    SurfaceFinishControl(
        "turned_exterior_before_plate",
        GROUND_UM,
        SphereFace(BALL_DIA, center_mm=(0.0, BALL_CENTER_H, 0.0)),
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BallMountProfile": {
        "BallDia",
        "BallRise",
        "BaseDia",
        "BaseHeight",
        "StemDia",
    },
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


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "datum-B axis perpendicularity": "0.05",
    "cross-bore true position": "0.05",
    "sphere profile and center location": "0.10",
    "pad-to-stem runout": "0.05",
}
