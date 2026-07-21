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
        "FORM FROM 0.80 THK X 4.00 WIDE STRIP.",
        "R2.00 AND R1.50 ON THE FRONT PROFILE ARE INSIDE BEND RADII.",
        f"STRAIGHT BLADE TANGENT LENGTH {BLADE_STRAIGHT_LEN:.2f}+/-0.10; BLADE AXIS",
        "  77.62+/-1.00 DEG CCW FROM FOOT AXIS.",
        "FREE-FLAT AXIS 97.62+/-1.00 DEG CCW FROM FOOT AXIS; ALL BENDS COPLANAR.",
        "HOLE <MOD-DIAM>3.25+/-0.05; AXIS 3.10+/-0.10 FROM THE LEFT FREE END",
        "  IN TOP VIEW AND 2.00+/-0.05 FROM EITHER LONG EDGE.",
        "LOWER BROAD FACE OF HORIZONTAL FOOT: FLATNESS 0.10.",
        "CONCAVE-SIDE BROAD FACE OF BLADE: Ra 0.8.",
        "RIGHT-HAND ORTHOGRAPHIC IS TOP VIEW.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
