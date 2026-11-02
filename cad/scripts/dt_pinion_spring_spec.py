r"""Pure-data dimensional contract shared by the pinion return leaf spring and
its manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  The pinion return spring is NOT a coil
spring: it is a bent 17-7 PH STAINLESS LEAF -- a 0.015 in (0.381) strip formed
as a flat screw-down foot with a square screw pad at its free end, an R3.3 bend
up to a blade leaning BLADE_LEAN_DEG west of vertical (in toward the strap),
then an R3.3 crest turning 25 deg back east to a short free flat.  The nominals drive the part's named equation globals AND the
drawing's coordinate math; the marked-dimension map keeps the part marks and
drawing keeps in lockstep (``test_dt_pinion_spring_drawing.py``).

The build re-imports these primitives so the drawing and the drive-train
assembly (which imports the derived geometry from ``dt_pinion_spring_geometry``)
read one source of truth.
"""

from __future__ import annotations

from _title_block_units import LENGTH_UNITS, render_number
from dt_pinion_spring_geometry import (
    FORMED_BAND_MM,
    FORMED_CONTACT_BANDS,
    BLADE_STRAIGHT_LEN as BLADE_STRAIGHT_LEN,
    BLADE_LEAN_DEG as BLADE_LEAN_DEG,
    FLAT_LEN as FLAT_LEN,
    FOOT_LEN as FOOT_LEN,
    HOLE_DIA as HOLE_DIA,
    HOLE_FROM_END as HOLE_FROM_END,
    KINK_ANGLE_PLACES as KINK_ANGLE_PLACES,
    KINK_DEG as KINK_DEG,
    PAD_HOLE_WEB_MIN,
    PAD_LEN as PAD_LEN,
    PAD_LEN_PLACES as PAD_LEN_PLACES,
    PAD_RELIEF_PLACES as PAD_RELIEF_PLACES,
    PAD_RELIEF_R as PAD_RELIEF_R,
    PAD_WIDTH as PAD_WIDTH,
    PAD_WIDTH_PLACES as PAD_WIDTH_PLACES,
    PAD_Z as PAD_Z,
    R_BEND as R_BEND,
    R_KINK as R_KINK,
    THICK as THICK,
    UNIT as UNIT,
    WIDTH as WIDTH,
    WIDTH_PLACES as WIDTH_PLACES,
)

# U27 + Main's r6 ruling (c): the profile is hand-formed.  The five that set
# the crest's preload on the MHA-DT-14 strap flank
# (dt_pinion_spring_geometry.FORMED_CONTACT_BANDS) carry a +/-.020 band --
# looser than a formed leaf could ever be held to +/-.004, tighter than a
# general row the drive train's preload and stress corner walk would not pass
# -- and their callouts name the mate (rule 4).  #290: they print at .XXX,
# because their nominals are the formed spring's millimetre design, kept.
# FlatLen shapes the flick past the contact, so it rides the title-block .XX
# row, and the kink's angle the angular row (machinist review, PR #1675).
FORMED_TOLERANCE_MM = FORMED_BAND_MM
# O2 (Main, 2026-09-24): the part is modelled INSTALLED; the maker forms the
# FREE shape.  The hidden construction-only FreeForm sketch carries the free
# profile, and the print locates the crest and sets the kink angle on it; the
# shape-invariant length and radii print from the installed profile.  The
# kink angle prints in place of the tip's location, which it and FlatLen fix
# (an offset of two general dimensions bounded nothing: machinist review, PR #1675).
FREE_FORM_SKETCH = "FreeForm"
REFERENCE_SKETCHES = (FREE_FORM_SKETCH,)
FREE_KINK_ANGLE = "FreeKinkAngle"
FORMED_DIMENSIONS: dict[str, set[str]] = {
    "SpringProfile": {"FootLen", "BendR", "KinkR", "FlatLen"},
    FREE_FORM_SKETCH: {"FreeKinkH", "FreeKinkV", FREE_KINK_ANGLE},
}
FORMED_BANDED_DIMENSIONS: dict[str, set[str]] = {
    feature: names & set(FORMED_CONTACT_BANDS)
    for feature, names in FORMED_DIMENSIONS.items()
}
if set().union(*FORMED_BANDED_DIMENSIONS.values()) != set(FORMED_CONTACT_BANDS):
    raise AssertionError("every preload-setting formed dimension must carry the band")
# The pad's bend relief prints as a single limit, R.010 MAX (swTolMAX prints the
# nominal, so the nominal is the limit), down to sharp: the wing, located from
# the hole's axis, keeps either end clear of the bend at FootLen's low limit
# (dt_pinion_spring_geometry.PAD_WING_FROM_HOLE).
PAD_RELIEF_FEATURE = "PadRelief"
PAD_RELIEF_DIMENSION = "PadReliefR"
PAD_RELIEF_TOL_TYPE = 6  # swTolType_e.swTolMAX
# The wing's length states the web it leaves the hole, under rule 17's .080
# target (rule 20; Codex, PR #1675).
# RV-01: the owner-approved hole-to-relief web stays above the .060 floor at
# the printed bands; the package declares the under-target web in its YAML
# (coordinator Main, 2026-10-19, PR #1675 option 1).
PAD_LEN_CALLOUT = (
    "HOLE WEB "
    f"{render_number(round(PAD_HOLE_WEB_MIN / LENGTH_UNITS[UNIT], 3), UNIT, 3)} MIN"
)

# Everything the print carries.  The profile is baselined from the pad hole's
# axis (drawing-guidelines.md rule 10 (dimension from a real feature)): the
# screw fixes the foot there, so the bend tangent and the FREE kink start are
# located from it, never from the model origin; the kink's height is from the
# foot's surface.  The pad, the strip width and the hole location are cut
# with the flat blank, so they take the title-block .XX row (the wing from the
# hole's axis too; the relief round is its single MAX limit); the strip width
# and the hole location are sheet dimensions picked on the blank's edges
# (draw_dt_pinion_spring._blank_dimensions).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    **FORMED_DIMENSIONS,
    "PadProfile": {"PadWidth", "PadLen"},
    PAD_RELIEF_FEATURE: {PAD_RELIEF_DIMENSION},
}

# Decimal places ARE the tolerance statement (drawing-simplicity-policy.md `How the repository implements the guidelines`); the model owns
# them and the drawing reads them back.
_FORMED_PLACES = 3  # the banded, kept millimetre nominals
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "SpringProfile": {
        name: _FORMED_PLACES if name in FORMED_CONTACT_BANDS else 2
        for name in FORMED_DIMENSIONS["SpringProfile"]
    },
    FREE_FORM_SKETCH: {
        name: KINK_ANGLE_PLACES if name == FREE_KINK_ANGLE else _FORMED_PLACES
        for name in FORMED_DIMENSIONS[FREE_FORM_SKETCH]
    },
    "PadProfile": {"PadWidth": PAD_WIDTH_PLACES, "PadLen": PAD_LEN_PLACES},
    PAD_RELIEF_FEATURE: {PAD_RELIEF_DIMENSION: PAD_RELIEF_PLACES},
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

# The #4 clearance Hole Wizard callout prints its drill size at the inch
# sheet's .XXX (#290).
HOLE_CALLOUT_PRECISION = 3

# The bend coupon qualifies a blank cut along the roll's length, its bends
# across the rolling direction (cad/docs/tolerance-policy.md); the blank also
# fits across the roll, so the print names the direction (Codex #859,
# PRRT_kwDOPHDy386mTtoA).  The notes state requirements, not the sequence of
# work (machinist review, PR #1675).
DRAWING_NOTES = "\n".join(
    (
        "CUT BLANK ALONG ROLL LENGTH (BENDS ACROSS ROLLING DIRECTION).",
        "RADII AND FORMED-PROFILE DIMENSIONS ARE TO THE INSIDE SURFACE.",
        "PHANTOM PROFILE IS THE FREE FORM; SOLID IS AS INSTALLED.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
