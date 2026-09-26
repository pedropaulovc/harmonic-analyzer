r"""Pure-data dimensional contract shared by the pinion return leaf spring and
its manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  The pinion return spring is NOT a coil
spring: it is a bent 17-7 PH STAINLESS LEAF -- a 0.015 in (0.381) strip formed
as a flat screw-down foot with a square screw pad at its free end, an R3.3 bend
up to a blade leaning BLADE_LEAN_DEG west of vertical (in toward the strap),
then an R3.3 crest turning 25 deg back east to a short free flat.  The nominals drive the part's named equation globals AND the
drawing's coordinate math; the marked-dimension map keeps the part marks and
drawing keeps in lockstep (``test_pinion_spring_drawing.py``).

The build re-imports these primitives so the drawing and the drive-train
assembly (which imports the derived geometry from ``pinion_spring_geometry``)
read one source of truth.
"""

from __future__ import annotations

from pinion_spring_geometry import (
    FORMED_BAND_MM,
    BLADE_STRAIGHT_LEN as BLADE_STRAIGHT_LEN,
    BLADE_LEAN_DEG as BLADE_LEAN_DEG,
    FLAT_LEN as FLAT_LEN,
    FOOT_LEN as FOOT_LEN,
    HOLE_DIA as HOLE_DIA,
    HOLE_FROM_END as HOLE_FROM_END,
    KINK_DEG as KINK_DEG,
    PAD_LEN as PAD_LEN,
    PAD_LEN_PLACES as PAD_LEN_PLACES,
    PAD_WIDTH as PAD_WIDTH,
    PAD_WIDTH_PLACES as PAD_WIDTH_PLACES,
    PAD_Z as PAD_Z,
    R_BEND as R_BEND,
    R_KINK as R_KINK,
    THICK as THICK,
    WIDTH as WIDTH,
    WIDTH_PLACES as WIDTH_PLACES,
)

# U27 + Main's r6 ruling (c): the profile is hand-formed, so every formed
# feature prints one place with a +/-0.5 band -- looser than a formed leaf
# could ever be held to +/-0.10, tighter than the .X row's +/-0.8.  The foot
# length is formed too, and its screw seat is transferred to the base at
# assembly, so it no longer sets preload and takes the same band.
FORMED_TOLERANCE_MM = FORMED_BAND_MM
# O2 (Main, 2026-09-24): the part is modelled INSTALLED; the maker forms the
# FREE shape.  The hidden construction-only FreeForm sketch carries the free
# profile, and the print locates the crest and the tip from it; the
# shape-invariant length and radii print from the installed profile.
FREE_FORM_SKETCH = "FreeForm"
REFERENCE_SKETCHES = (FREE_FORM_SKETCH,)
FORMED_DIMENSIONS: dict[str, set[str]] = {
    "SpringProfile": {"FootLen", "BendR", "KinkR", "FlatLen"},
    FREE_FORM_SKETCH: {"FreeKinkH", "FreeKinkV", "FreeTipH"},
}

# Everything the print carries.  The profile is baselined from the foot's free
# end (policy rule 7): the FREE kink start and tip are located from it, never
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
    FREE_FORM_SKETCH: {name: 1 for name in FORMED_DIMENSIONS[FREE_FORM_SKETCH]},
    "Spring": {"StripWidth": WIDTH_PLACES},
    "PadProfile": {"PadWidth": PAD_WIDTH_PLACES, "PadLen": PAD_LEN_PLACES},
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
        "PHANTOM PROFILE IS THE FREE FORM; SOLID IS AS INSTALLED.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
