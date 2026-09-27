r"""Pure-data dimensional contract shared by the cylinder-gear arbor and drawing."""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

SHAFT_DIA = 0.375 * MM_PER_IN  # ch13: = cam bore (legacy parameters.kcl)
SHAFT_RADIUS = SHAFT_DIA / 2.0
# #743 (supersedes U34b's "span less 6.0"): the arbor runs the FULL depth of
# both pedestal straps, where the MHA-147 apex set screws bear on it, and each
# end stands a dome proud of its strap's outer face -- the bright dome the
# photographs show on each pedestal (ch13 p.23/25, ch25 p.67). So the
# cylindrical length IS the span over both installed MHA-004 straps, which the
# fitter measures; the stock is cut two domes longer and both ends are domed
# into it. The span is a REFERENCE value, not a machining target, and its
# nominal and the dome height are the bank's own geometry
# (cylinder_bank_layout.ARBOR_LENGTH / ARBOR_DOME_HEIGHT: this spec cannot
# import the layout, which reaches it through cylinder_gear_spec).
SHAFT_DIA_BAND = SHAFT_H
# The print's one statement of how the length is set: the fitter measures the
# span over both installed MHA-004 straps (drive-train assembly steps 8-9 carry
# the same measurement) and that span is the cylinder.
LENGTH_CALLOUT = "CUT TO FIT: SPAN OVER BOTH MHA-004"
DOME_CALLOUT = "BOTH ENDS"
ARBOR_BEARING_PROBE_Y_MM = 10.0

# The arbor is one plain cylinder extruded +Y from the origin (y 0..ARBOR_LENGTH,
# NOT mid-plane), domed past both ends, so the bearing face resolves by
# diameter alone.  The 20 cylinder gears and both thrust washers run on that
# single O.D., which also
# journals in the two arbor pedestals -- one running surface, one roughness
# control (drawing-simplicity policy rule 5).  No datums and no feature control
# frames: rule 3 keeps GD&T for the cast frame members and the gear blanks, and
# a plain rod's size limits plus the title-block general grade already state
# everything a lathe hand can hold on it.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "arbor_bearing",
        MACHINED_UM,
        # Any station on the cylinder: the gears run on it end to end.
        CylinderFace(SHAFT_DIA, contains_y_mm=ARBOR_BEARING_PROBE_Y_MM),
    ),
)

# The dome height is a manufacturing dimension no feature dimension states,
# so -- like the pedestal's locations (arbor_pedestal_spec.REFERENCE_SKETCHES)
# -- a hidden construction line along the axis over the north dome owns it,
# equation-bound to the same global the domes are built from.
REFERENCE_SKETCHES = ("DomeReference",)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDia"},
    "Shaft": {"Depth"},
    "DomeReference": {"DomeHeight"},
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
    # One place: a filed or form-turned dome only has to read as the dome
    # and clears nothing (it stands proud of the strap in free air).
    "DomeReference": {"DomeHeight": 1},
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
# call (each dome is turned on its centre, which may stay).
# The length is cut at assembly, so the shop supplies the bar long (190 covers
# the nominal span plus both domes and facing stock). The set screws' cup
# points bear in spots drilled through the pedestal taps at assembly (#743),
# so the bar itself is never flatted.
DRAWING_NOTES = "\n".join(
    (
        "3/8 IN GROUND STOCK OK.",
        "CENTRES OK.",
        "SUPPLY 190 LONG, UNCUT.",
        "NO FLATS; SET-SCREW SPOTS ARE DRILLED AT ASSEMBLY.",
    )
)
# The title block declares 1:1, so the off-scale pictorial must say so
# (codex machinist review).
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
