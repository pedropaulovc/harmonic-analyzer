r"""Pure-data contract for the rocker arm hub filing button (MHA-CH-006-TL-04).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
rocker arm's hub filing hold (traveler setup S6, inventory fixture
``hub-filing-buttons``) two buttons ride the headed filing
stud (MHA-CH-006-TL-05) that locates in the arm's reamed pivot bore: one seats
on each hub face, the stud's nut clamps the arm between them, and the hub is
filed down until the file rides on both hardened rims all round. The rim is
the filing line, so the button O.D. is the hub O.D. Two are made, O1 drill
rod torch-hardened and lapped (shop-additions section 1: the shop has no
grinder, so bore, faces and O.D. are lapped).

Frame: the button axis is model +Z (the inventory fixture frame's stud axis),
the hub-seating face at Z0 and the outer face at +Z.
"""

from __future__ import annotations

import ch_rocker_arm_spec as rocker
from _printed_tolerance import printed_deviations
from _gtol_cylinder import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

THICKNESS = 4.0
THICKNESS_PLACES = 3  # lapped faces: the stack the stud's stations hold

# The rim is the filing line: the button O.D. is the hub O.D. Codex round 3
# found the shop-additions 0.010 lapped band unsupported: the hub prints at
# two places, so the three-place general band already holds the filed hub
# far inside it, and a hub taper inside that band is harmless.
OD = rocker.HUB_DIA
OD_PLACES = 3
# A button O.D. of HUB_DIA at the three-place band files the hub to about
# 10.07-10.33, inside the hub's printed two-place O9.69-10.71.
_OD_MIN, _OD_MAX = [round(OD + deviation, 12) for deviation in printed_deviations(OD, OD_PLACES)]
_HUB_MIN, _HUB_MAX = [round(rocker.HUB_DIA + deviation, 12) for deviation in printed_deviations(rocker.HUB_DIA, 2)]
if not (_HUB_MIN <= _OD_MIN and _OD_MAX <= _HUB_MAX):
    raise AssertionError("filing-button rim band leaves the hub's printed O.D. band")
# The rim's runout to its bore, printed as a measurable acceptance on the
# O.D. (drawing-simplicity-policy: the button is off the GD&T allowlist, so
# plain runout wording, no frame or datum) with its reason. It is the whole
# remainder of the arm's hub coaxiality budget after the two body fits; the
# stud spec, which owns that budget, asserts it is the largest TIR at these
# places (Main's round-6 ruling).
OD_RUNOUT_TIR = 0.025
OD_RUNOUT_PLACES = 3
if round(OD_RUNOUT_TIR, OD_RUNOUT_PLACES) != OD_RUNOUT_TIR:
    raise AssertionError("the rim runout does not print at its places")

# The bore prints as a reference and its fit to the stud governs (callout).
# BORE_BAND is the design intent of that fit for the stud's stack checks
# only; features.toml carries what the print says, the nominal and the note.
BORE_DIA = 6.51
BORE_BAND = (0.005, -0.005)
BORE_PLACES = 3
# Both bore ends carry a 45 degree entry chamfer (the button is reversible):
# the stud's MAX seat fillet would otherwise hold the lower button off the
# head face at the tightest fit (codex 4280374810). Printed as a MIN leg on
# the bore callout, as draw_dt_cone_tip_block names its bore's two
# countersinks; the stud spec asserts the worst-case clearance.
BORE_CHAMFER = 0.3
BORE_CHAMFER_PLACES = 1
BORE_CHAMFER_ANGLE_DEG = 45.0
if round(BORE_CHAMFER, BORE_CHAMFER_PLACES) != BORE_CHAMFER:
    raise AssertionError(
        "filing-button bore chamfer MIN does not print as its model value"
    )
BORE_CHAMFER_CALLOUT = f"{BORE_CHAMFER:.{BORE_CHAMFER_PLACES}f} MIN X {BORE_CHAMFER_ANGLE_DEG:.0f}\u00b0 BOTH ENDS"
# drawing-guidelines.md rule 4 (tighten only for function, and name the mate) and drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the matched fit sits on the bore's callout, naming
# the mate by Number with its acceptance (callout above, callout below).
BORE_FIT_CALLOUT = (
    BORE_CHAMFER_CALLOUT,
    "SLIDES ON MHA-CH-006-TL-05 STUD BY HAND WITHOUT SHAKE",
)
BORE_FIT_NOTE = " ".join(part for part in BORE_FIT_CALLOUT if part)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"DiscDia", "BoreDia"},
    "Disc": {"DiscThick"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"DiscDia": OD_PLACES, "BoreDia": BORE_PLACES},
    "Disc": {"DiscThick": THICKNESS_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked filing-button dimension needs authored places")

# The bore locates on the stud: a machining-required symbol at the project's
# machined grade (codex round 8); the fit callout governs its size.
SURFACE_FINISHES = (SurfaceFinishControl("bore", MACHINED_UM, CylinderFace(BORE_DIA)),)
# The blind reviewer sees only the sheet: each note states a function.
# Hardness lives in the Finish field.
# drawing-guidelines.md rule 17 (walls and webs) wall: the rim between the printed O.D. lower limit and the bore.
RIM_WALL_MIN = 1.78
if round((_OD_MIN - BORE_DIA) / 2.0, 2) != RIM_WALL_MIN:
    raise AssertionError("filing-button stated rim wall drifted from its geometry")
# Pending exception ruling: MHA-CH-006-TL-04 rim wall 1.78 MIN (#1369).
RIM_WALL_NOTE = f"RIM WALL {RIM_WALL_MIN:.2f} MIN."
# drawing-guidelines.md rule 4 (tighten only for function, and name the mate):
# each three-place size names its mate on its own dimension (callout below);
# the O.D. carries its runout acceptance above its value.
# The runout's reason rides under the O.D.'s mate: one line above (a broken
# above-callout does not print, draw_dt_cone_gear_shaft), and in one line the
# reason would reach the edge view and the isometric.
OD_CALLOUT = "SETS FILED MHA-CH-006 HUB\nRUNOUT HOLDS HUB COAXIALITY"
OD_RUNOUT_CALLOUT = f"RUNOUT {OD_RUNOUT_TIR:.{OD_RUNOUT_PLACES}f} TIR TO BORE"
THICKNESS_CALLOUT = "STACKS MHA-CH-006 HUB"
# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the
# title block's edge break does not apply to the rim; a leadered note on the
# rim edge says so.
RIM_CORNER_NOTE = "BOTH RIM CORNERS SHARP"
DRAWING_NOTES = RIM_WALL_NOTE
REFERENCE_DIMENSIONS = frozenset({"BoreDia"})
REFERENCE_CALLOUTS = {"BoreDia": BORE_FIT_CALLOUT}
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 4:1"

