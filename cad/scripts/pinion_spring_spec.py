r"""Pure-data dimensional contract shared by the pinion return leaf spring and
its manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  The pinion return spring is NOT a coil
spring: it is a bent BRASS LEAF -- a 0.8 x 4.0 strip formed as a flat screw-down
foot, an R2 bend up to a blade leaning BLADE_TILT_DEG off vertical, then a
subtle R1.5 kink (~20 deg back) to a short free flat.  The nominals drive the
part's named equation globals AND the drawing's coordinate math; the marked-
dimension map keeps the part marks and drawing keeps in lockstep
(``test_pinion_spring_drawing.py``).

The build re-imports these primitives so the drawing and the drive-train
assembly (which imports the derived geometry from ``build_pinion_spring``) read
one source of truth.
"""

from __future__ import annotations

from pinion_spring_geometry import (
    BLADE_STRAIGHT_LEN as BLADE_STRAIGHT_LEN,
    BLADE_TILT_DEG as BLADE_TILT_DEG,
    FLAT_LEN as FLAT_LEN,
    FOOT_LEN as FOOT_LEN,
    HOLE_FROM_END as HOLE_FROM_END,
    KINK_DEG as KINK_DEG,
    R_BEND as R_BEND,
    R_KINK as R_KINK,
    THICK as THICK,
    WIDTH as WIDTH,
)

FOOT_LENGTH_TOLERANCE_MM = 0.10
BEND_RADIUS_TOLERANCE_MM = 0.10
KINK_RADIUS_TOLERANCE_MM = 0.10

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "SpringProfile": {"FootLen", "BendR", "KinkR"},
}

TERMINAL_CALLOUT = "\n".join(
    (
        f"{FLAT_LEN:.2f}+/-0.10 TRUE LENGTH - SHORT TERMINAL INSIDE EDGE",
        f"{90.0 - BLADE_TILT_DEG + KINK_DEG:.2f}+/-1 DEG CCW FROM FOOT INSIDE PATH",
    )
)

DRAWING_NOTES = "\n".join(
    (
        f"FORM FROM {THICK:.2f}+/-0.05 THK X {WIDTH:.2f}+/-0.05 WIDE STRIP.",
        "ALL FORMED-PROFILE RADII APPLY TO THE INSIDE SURFACE; TANGENT",
        "  LENGTHS AND ANGLES APPLY TO THE INSIDE-SURFACE PATH IN FRONT VIEW.",
        f"STRAIGHT BLADE TANGENT LENGTH {BLADE_STRAIGHT_LEN:.2f}+/-0.10; PATH ANGLE",
        f"  {90.0 - BLADE_TILT_DEG:.2f}+/-1.00 DEG CCW FROM FOOT PATH, LEFT FREE END TOWARD BEND.",
        f"FORM SHORT TERMINAL INSIDE EDGE FROM R{R_KINK:.2f} KINK EXIT TO FREE TIP;",
        f"  THE LINE ACROSS ITS TIP IS THE {THICK:.2f} STRIP END FACE.",
        f"FOOT HOLE AXIS {HOLE_FROM_END:.2f}+/-0.10 FROM LEFT FREE END AND {WIDTH / 2.0:.2f}+/-0.05",
        "  FROM THE LOWER LONG EDGE SHOWN IN TOP VIEW; SIZE PER NATIVE CALLOUT.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "spring screw-down foot flatness": "0.10",
}
