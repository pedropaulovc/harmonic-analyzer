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

THICK = 0.8  # strip thickness (photo-scaled vs the 5.0 strap)
WIDTH = 4.0  # strip width = extrude depth, inside the strap's z band
FOOT_LEN = 31.0  # flat screw-down foot on the base, pointing WEST
R_BEND = 2.0  # foot-to-blade bend
R_KINK = 1.5  # the subtle bend-back near the top
KINK_DEG = 20.0  # turn back west near the tip
FLAT_LEN = 2.0  # free flat above the kink
BLADE_TILT_DEG = 12.38  # blade lean off the foot plane (= strap parked lean)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "SpringProfile": {"FootLen", "BendR", "KinkR", "FlatLen"},
}

DRAWING_NOTES = "\n".join(
    (
        "FORM FROM 0.8 THK X 4.0 WIDE HALF-HARD BRASS STRIP (CDA 260).",
        "PROFILE SHOWN IS THE STRIP CENTRELINE; ALL BEND RADII TO CENTRELINE.",
        "BLADE RISES 12.4 DEG OFF THE FOOT PLANE; SUBTLE KINK 20 DEG TOWARD THE FOOT NEAR THE TIP.",
        "FOOT SCREW HOLE <MOD-DIAM>3.25 (#4 CLEARANCE), 3.1 FROM THE FREE END.",
        "DEBURR AND BREAK SHARP EDGES; DO NOT NICK THE BLADE.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
