r"""Pure-data dimensional contract shared by the pinion return leaf spring and
its manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  The pinion return spring is NOT a coil
spring: it is a bent BRASS LEAF -- a 0.8 x 4.0 strip formed as a flat screw-down
foot, an R2 bend up to a blade leaning 12.38 deg off the foot plane, then a
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
    KINK_DEG as KINK_DEG,
    R_BEND as R_BEND,
    R_KINK as R_KINK,
    THICK as THICK,
    WIDTH as WIDTH,
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "SpringProfile": {"FootLen", "BendR", "KinkR", "FlatLen"},
}

DRAWING_NOTES = "\n".join(
    (
        f"FORM FROM {THICK:.2f}+/-0.05 THK X {WIDTH:.2f}+/-0.05 WIDE STRIP.",
        "ALL FORMED-PROFILE RADII APPLY TO THE INSIDE SURFACE; TANGENT",
        "  LENGTHS AND ANGLES APPLY TO THE INSIDE-SURFACE PATH IN FRONT VIEW.",
        f"STRAIGHT BLADE TANGENT LENGTH {BLADE_STRAIGHT_LEN:.2f}+/-0.10; PATH ANGLE",
        "  77.62+/-1.00 DEG CCW FROM FOOT PATH, LEFT FREE END TOWARD BEND.",
        "FREE-FLAT INSIDE PATH: 2.00+/-0.10 TRUE LENGTH; DIRECTION 7.62+/-1.00",
        "  DEG LEFT OF VERTICAL WITH FOOT HORIZONTAL AS SHOWN. THE SHORT LINE",
        "  ACROSS ITS TIP IS THE 0.80 STRIP END FACE, NOT THE FREE-FLAT LENGTH.",
        "FOOT HOLE AXIS 3.10+/-0.10 FROM LEFT FREE END AND 2.00+/-0.05",
        "  FROM THE LOWER LONG EDGE SHOWN IN TOP VIEW; SIZE PER NATIVE CALLOUT.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
