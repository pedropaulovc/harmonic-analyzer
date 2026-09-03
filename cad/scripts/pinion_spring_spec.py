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

No explicit bands: a hand-formed brass strip is governed by the title block's
two-place and angular tolerances (machinist review 2026-09-02: the +/-0.1 on
the foot length and both bend radii was over-specification).
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

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "SpringProfile": {"FootLen", "BendR", "KinkR"},
}

# The blade's foot-to-blade angle as the front view dimensions it: the
# interior angle between the foot and the blade (the sector clear of every
# other annotation); the terminal callout states its own angle from the same
# foot path, CCW.
FOOT_TO_BLADE_INTERIOR_DEG = 90.0 + BLADE_TILT_DEG  # 98.14

# Flagged from the short terminal in the front view: its true length and its
# path angle.  No band -- the title block's linear and angular tolerances
# govern a formed leaf (drawing-simplicity-policy.md rules 1-2).
TERMINAL_CALLOUT = "\n".join(
    (
        f"{FLAT_LEN:.2f} TERMINAL, INSIDE EDGE",
        f"{90.0 - BLADE_TILT_DEG + KINK_DEG:.2f} DEG CCW FROM FOOT INSIDE PATH",
    )
)

# Notes: the one form fact a maker cannot read off the views (policy rule 6).
# The blade's straight length and angle and the foot hole's location are
# view dimensions (machinist review 2026-09-02); the radii and the foot
# length are native dimensions.
DRAWING_NOTES = "\n".join(
    (
        f"FORM FROM {THICK:.2f} X {WIDTH:.2f} STRIP;",
        "RADII, LENGTHS AND ANGLES ARE ON THE INSIDE SURFACE.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
