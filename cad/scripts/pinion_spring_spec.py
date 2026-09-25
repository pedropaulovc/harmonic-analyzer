r"""Pure-data dimensional contract shared by the pinion return leaf spring and
its manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  The pinion return spring is NOT a coil
spring: it is a bent BRASS LEAF -- a 0.8 thick strip formed as a flat screw-down
foot with a square screw pad at its free end, an R2 bend up to a blade leaning
BLADE_TILT_DEG off vertical, then a subtle R1.5 kink (~20 deg back) to a short
free flat.  The nominals drive the part's named equation globals AND the
drawing's coordinate math; the marked-dimension map keeps the part marks and
drawing keeps in lockstep (``test_pinion_spring_drawing.py``).

The build re-imports these primitives so the drawing and the drive-train
assembly (which imports the derived geometry from ``pinion_spring_geometry``)
read one source of truth.
"""

from __future__ import annotations

from pinion_spring_geometry import (
    BLADE_STRAIGHT_LEN as BLADE_STRAIGHT_LEN,
    BLADE_TILT_DEG as BLADE_TILT_DEG,
    FLAT_LEN as FLAT_LEN,
    FOOT_LEN as FOOT_LEN,
    HOLE_DIA as HOLE_DIA,
    HOLE_FROM_END as HOLE_FROM_END,
    KINK_DEG as KINK_DEG,
    PAD_LEN as PAD_LEN,
    PAD_WIDTH as PAD_WIDTH,
    R_BEND as R_BEND,
    R_KINK as R_KINK,
    THICK as THICK,
    WIDTH as WIDTH,
)

# U27 + Main's r6 ruling (c): the profile is hand-formed, so every formed
# feature prints one place with a +/-0.5 band -- looser than a formed leaf
# could ever be held to +/-0.10, tighter than the .X row's +/-0.8.  The foot
# length is formed too, and its screw seat is transferred to the base at
# assembly, so it no longer sets preload and takes the same band.
FORMED_TOLERANCE_MM = 0.5
FORMED_DIMENSIONS: dict[str, set[str]] = {
    "SpringProfile": {
        "FootLen",
        "BendR",
        "KinkH",
        "KinkV",
        "KinkR",
        "FlatLen",
        "TipH",
    },
}

# Everything the print carries.  The profile is baselined from the foot's free
# end (policy rule 7): the kink start and the tip are located from it, never
# from the model origin.  The pad, the strip width and the hole location are
# cut with the flat blank, so they take the title-block .XX row.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    **FORMED_DIMENSIONS,
    "Spring": {"StripWidth"},
    "PadProfile": {"PadWidth", "PadLen"},
}

# Decimal places ARE the tolerance statement (policy rule 2); the model owns
# them and the drawing reads them back.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "SpringProfile": {name: 1 for name in FORMED_DIMENSIONS["SpringProfile"]},
    "Spring": {"StripWidth": 2},
    "PadProfile": {"PadWidth": 2, "PadLen": 2},
}

_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked dimension must state its decimal places")

DRAWING_NOTES = "\n".join(
    (
        "CUT BLANK TO TEMPLATE OF TOP-VIEW PAD, DRILL, LEAVE STRIP LONG;",
        "  FORM, THEN TRIM FREE TIP.",
        "RADII AND FORMED-PROFILE DIMENSIONS ARE TO THE INSIDE SURFACE.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
