r"""Pure-data dimensional contract shared by the cylinder-gear arbor and drawing."""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

SHAFT_DIA = 0.375 * MM_PER_IN  # ch13: = cam bore (legacy parameters.kcl)
# U34b: the pedestals stand inboard against the end discs and the arbor is CUT
# TO FIT at assembly, so its length is a REFERENCE value, not a machining
# target. Nominal strap span 147.854 (inner faces -72.652 / +75.202) plus the
# two 10.0 straps is 167.854 over the outer faces; less FIT_SHORTFALL (3.0 per
# end) leaves 7.0 seated in each strap bore and 161.854 overall.
FIT_SHORTFALL = 6.0  # total: 3.0 short of each strap's outer face
SHAFT_LENGTH = 161.9  # REF; see LENGTH_CALLOUT
SHAFT_DIA_BAND = SHAFT_H
# The print's one statement of how the length is set: the fitter measures the
# span over both installed MHA-004 straps and cuts the arbor FIT_SHORTFALL
# under it (drive-train assembly steps 8-9 carry the same measurement).
LENGTH_CALLOUT = f"CUT TO FIT: SPAN OVER BOTH MHA-004 LESS {FIT_SHORTFALL:.1f}"

# The arbor is one plain cylinder extruded +Y from the origin (y 0..SHAFT_LENGTH,
# NOT mid-plane), so the bearing face resolves by diameter alone.  The 20
# cylinder gears and both end discs run on that single O.D., which also
# journals in the two arbor pedestals -- one running surface, one roughness
# control (drawing-simplicity policy rule 5).  No datums and no feature control
# frames: rule 3 keeps GD&T for the cast frame members and the gear blanks, and
# a plain rod's size limits plus the title-block general grade already state
# everything a lathe hand can hold on it.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "arbor_bearing",
        MACHINED_UM,
        CylinderFace(SHAFT_DIA, contains_y_mm=SHAFT_LENGTH / 2.0),
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDia"},
    "Shaft": {"Depth"},
}

# Decimal places are the tolerance (policy rule 2), so the MODEL owns them and
# the sheet only asserts what it imported.  3/8 in = 9.525 exactly: two places
# would print 9.525 as 9.53 and contradict the bore mates built on the exact
# inch conversion, and the O.D. carries the running band anyway.  The overall
# length is a free dimension -- one place puts it on the title block's .X row
# instead of claiming the .XX band a trailing 161.90 would, and the sheet
# parenthesizes it: the cut-to-fit callout, not the nominal, sets it.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ShaftProfile": {"ShaftDia": 3},
    "Shaft": {"Depth": 1},
}
_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
if any(
    name not in DRAWING_DIMENSIONS.get(feature, frozenset())
    for feature, name in _PRECISION_NAMES
):
    raise AssertionError("DRAWING_PRECISION names a dimension the part never marks")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")

# Three part-specific facts a machinist cannot read off the views (policy
# rule 6). The O.D. IS a catalog stock size, so the 20 um running band is a
# stock buy rather than a grind between centres, and a 162:9.5 slender bar is
# turned between centres -- saying the centre holes may stay saves a phone
# call (both ends finish up inside a pedestal bore, where they do no harm).
# The length is cut at assembly, so the shop supplies the bar long (170 covers
# the nominal span plus facing stock).
DRAWING_NOTES = "\n".join(
    (
        "3/8 IN GROUND STOCK OK.",
        "CENTRES OK.",
        "SUPPLY 170 LONG, UNCUT.",
    )
)
# The title block declares 1:1, so the off-scale pictorial must say so
# (codex machinist review).
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
