r"""Pure-data dimensional contract shared by the cylinder-gear arbor and drawing."""

from __future__ import annotations

import _config
from _fit_shaft_h import SHAFT_H
from _gtol_cylinder import CylinderFace
from _package_units import drawing_unit
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

# #290: the registry row's drawing_unit (in) is this sheet's unit; the band,
# places and roughness below are authored for it.
UNIT = drawing_unit(
    "parts/dt-cylinder-gear-shaft", _config.parts("dt-cylinder-gear-shaft")
)

SHAFT_DIA = 0.375 * MM_PER_IN  # ch13: = cam bore (legacy parameters.kcl)
SHAFT_RADIUS = SHAFT_DIA / 2.0
# #743 (supersedes U34b's "span less 6.0"): the arbor runs the FULL depth of
# both pedestal straps, where the MHA-DT-VN-64 apex set screws bear on it, and each
# end stands a dome proud of its strap's outer face -- the bright dome the
# photographs show on each pedestal (ch13 p.23/25, ch25 p.67). So the
# cylindrical length IS the span over both installed MHA-DT-02 straps, which the
# fitter measures; the stock is cut two domes longer and both ends are domed
# into it. The span is a REFERENCE value, not a machining target, and its
# nominal and the dome height are the bank's own geometry
# (cylinder_bank_layout.ARBOR_LENGTH / ARBOR_DOME_HEIGHT: this spec cannot
# import the layout, which reaches it through dt_cylinder_gear_spec).
SHAFT_DIA_BAND = SHAFT_H
# The print's one statement of how the length is set: the fitter measures the
# span over both installed MHA-DT-02 straps (drive-train assembly steps 8-9 carry
# the same measurement) and that span is the cylinder, so its acceptance is
# that both dome roots (the cylinder's ends) finish at the straps' outer
# faces, each dome standing proud beyond (r1 machinist review: "span over"
# alone left the end condition open; PR #1658 Codex review: a bare "ENDS
# FLUSH" reads as the dome tips, 3 mm short).
LENGTH_CALLOUT = "CUT TO FIT: DOME ROOTS AT MHA-DT-02 OUTER FACES"
DOME_CALLOUT = "BOTH ENDS"
# drawing-guidelines.md rule 4 (tighten only for function, and name the mate):
# the O.D. band exists for the 20 MHA-DT-12 gears that run on it (their
# bores are matched to this finished bar) and the two MHA-DT-02 strap bores
# it fills, so the callout names both at the dimension.
SHAFT_DIA_CALLOUT = "RUNNING FIT IN MHA-DT-12 AND MHA-DT-02 BORES"
ARBOR_BEARING_PROBE_Y_MM = 10.0

# The arbor is one plain cylinder extruded +Y from the origin (y 0..ARBOR_LENGTH,
# NOT mid-plane), domed past both ends, so the bearing face resolves by
# diameter alone. The 20 cylinder gears, south disc and north spring run on
# that single O.D., which also
# journals in the two arbor pedestals -- one running surface, one roughness
# control (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)).  No datums and no feature control
# frames: drawing-guidelines.md rule 5 (avoid excessive GD&T) keeps GD&T for the cast frame members and the gear blanks, and
# a plain rod's size limits plus the title-block general grade already state
# everything a lathe hand can hold on it.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "arbor_bearing",
        MACHINED_UM,
        # Any station on the cylinder: the gears run on it end to end.
        CylinderFace(SHAFT_DIA, contains_y_mm=ARBOR_BEARING_PROBE_Y_MM),
        display_unit=UNIT,
    ),
)

# The dome height is a manufacturing dimension no feature dimension states,
# so -- like the pedestal's locations (dt_arbor_pedestal_spec.REFERENCE_SKETCHES)
# -- a hidden construction line along the axis over the north dome owns it,
# equation-bound to the same global the domes are built from. A construction
# arc over the same dome's silhouette carries its spherical radius, which the
# sheet prints as a reference: the height on the toleranced diameter already
# fixes it, but a bare height did not say the end is a spherical cap (r1
# machinist review; the MHA-CH-05 and MHA-DT-01 domes print the same way).
REFERENCE_SKETCHES = ("DomeReference",)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDia"},
    "Shaft": {"Depth"},
    "DomeReference": {"DomeHeight", "DomeRadius"},
}

# Decimal places are the tolerance (drawing-simplicity-policy.md `How the repository implements the guidelines`), so the MODEL owns them and
# the sheet only asserts what it imported.  Four places on the O.D.: its
# SHAFT_H band is 0/-.0008, and an inch nominal prints at its tolerance's
# places (.3750).  The overall
# length is a free dimension -- one place puts it on the title block's .X row
# instead of claiming the .XX band, and the sheet parenthesizes it: the
# cut-to-fit callout, not the nominal, sets it.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ShaftProfile": {"ShaftDia": 4},
    "Shaft": {"Depth": 1},
    # Two places: .X would print the .06 dome as .1 (2.5 mm), a different
    # dome; the reference radius follows at the same places.
    "DomeReference": {"DomeHeight": 2, "DomeRadius": 2},
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
# drawing-guidelines.md rule 7 (notes: few, flagged, never a method)). The O.D. IS a catalog stock size, so the .0008 in running band is a
# stock buy rather than a grind between centres, and a 6.5:.375 slender bar is
# turned between centres -- saying the centre holes may stay saves a phone
# call (each dome is turned on its centre, which may stay).
# The length is cut at assembly, so the shop supplies the bar long (7-1/2 in
# stock covers the nominal span plus both domes and facing stock) and the
# domes are turned on the cut ends (r1 machinist review: nothing tied the end
# form to the cut-to-fit). The set screws' cup points bear in spots drilled
# through the pedestal taps at assembly (#743), so the bar itself is never
# flatted.
DRAWING_NOTES = "\n".join(
    (
        "3/8 GROUND STOCK OK.",
        "CENTRES OK.",
        "SUPPLY 7-1/2 LONG, UNCUT; CUT AND DOME BOTH ENDS AT ASSEMBLY.",
        "NO FLATS; SET-SCREW SPOTS ARE DRILLED AT ASSEMBLY.",
    )
)
# The title block declares 1:1, so the off-scale pictorial must say so
# (codex machinist review).
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
