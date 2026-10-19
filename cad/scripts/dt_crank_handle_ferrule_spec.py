r"""Pure-data contract for MHA-DT-34, the crank handle's brass ferrule.

User ruling 2026-09-29 (ch11 p.14 and p.15 photographs): the bright ring at the
crank end of the ebonized handle is a separate brass ferrule, not a painted
band on the oak.  It is epoxied on a turned tenon of MHA-DT-08, seated against
the tenon's shoulder, and its outer end face is the face that runs against
the crank arm MHA-DT-06.

The oak tenon is turned to suit this bore, and the handle's end play is set by
facing the MHA-DT-32 shoulder at assembly (user ruling 2026-09-29, after the
MHA-DT-34 machinist review), so no length here is a stack term and every size
but the bore and the seat mouth's chamfer is routine (.X).  The bore keeps a
+/-0.10 band (Codex P1/P2 on #1139, user ruling 2026-09-30): at .X a large
bore let the fitted tenon outgrow the MHA-DT-08 shoulder it seats on, and a
small one thinned the oak round the pivot bore under 1.5.

Local frame: the axis is local +X, the part's origin plane is the arm-bearing
end face (x=0), and the seat face against the oak shoulder is at x=LENGTH --
the handle's own frame, so the drive train places both with one transform.

PURE DATA, no SolidWorks/COM imports.
"""

from __future__ import annotations

import math

from dt_crank_hub_geometry import EDGE_BREAK_MAX_MM, GENERAL_1PL_TOL_MM

# The ring leaves the bench at the 9/16-in rod's own OD and is skimmed to the
# Ø12.5 grip contour with the MHA-DT-08 shoulder after the epoxy cures (user
# ruling 2026-10-01, local review of 47cb8a46b: glued on, the ring can sit
# 0.175 off the reamed bore, so an oak shoulder turned true to the bore could
# not finish flush with a pre-turned OD).  The default configuration is the
# ring as made; INSTALLED is it skimmed, and the drive train places that.
STOCK_DIA = 0.5625 * 25.4
# Cold-drawn brass rod, 9/16 in, -0.002 in (ASSUMPTION, the supplier's
# commercial tolerance; not sourced in this repo).
STOCK_DIA_MIN = round(STOCK_DIA - 0.002 * 25.4, 6)
OUTER_DIA = STOCK_DIA
# Ø12.5 x 7 as installed (user ruling 2026-09-30, ch30 eight-views-4: the
# ring reads ~Ø11-12, not the Ø15 first derived).
INSTALLED_OUTER_DIA = 12.5
INSTALLED_CONFIG = "INSTALLED"
# 7.7 (local review of 1f3067ef2): the fitted tenon keeps 1.5 of oak over the
# reamed pivot bore with 0.10 of eccentricity between them.
BORE_DIA = 7.7
BORE_DIA_TOL = 0.10
LENGTH = 7.0
# Joint dimensions shared with MHA-DT-08, whose spec imports this one.
# The shortest tenon must retain this much uninterrupted bonded length.
TENON_LENGTH = 5.0
TENON_GLUE_LENGTH_FLOOR = 3.5
# Owner ruling A on #1661: the seat-mouth chamfer clears the R0.3 tenon root.
# Its maximum is the glue-length budget rounded DOWN to a one-place limit:
# 5.0 - 0.8 - 0.25 - 3.5 = 0.45, hence 0.4.  Derive it here rather than
# tightening it independently of the handle's joint-length requirement.
SEAT_MOUTH_CHAMFER_MIN = 0.3
SEAT_MOUTH_CHAMFER_MAX = (
    math.floor(
        round(
            (
                TENON_LENGTH
                - GENERAL_1PL_TOL_MM
                - EDGE_BREAK_MAX_MM
                - TENON_GLUE_LENGTH_FLOOR
            )
            * 10.0,
            6,
        )
    )
    / 10.0
)
if SEAT_MOUTH_CHAMFER_MAX < SEAT_MOUTH_CHAMFER_MIN:
    raise AssertionError("MHA-DT-34 glue-length budget cannot clear the tenon root")
# Modelled at the midpoint; the native band prints both functional limits.
SEAT_MOUTH_CHAMFER = round((SEAT_MOUTH_CHAMFER_MIN + SEAT_MOUTH_CHAMFER_MAX) / 2.0, 6)
SEAT_MOUTH_CHAMFER_TOL = round(
    (SEAT_MOUTH_CHAMFER_MAX - SEAT_MOUTH_CHAMFER_MIN) / 2.0, 6
)

# Brass wall, on radius, as made: the smallest stock over the largest bore.
# The skimmed wall, with the ring off-centre, is MHA-DT-08's check.
WALL_WORST = (STOCK_DIA_MIN - (BORE_DIA + BORE_DIA_TOL)) / 2.0
if WALL_WORST < 1.5:
    raise AssertionError("MHA-DT-34 ferrule wall is under 1.5 at the worst case")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FerruleProfile": {"OuterDia", "BoreDia", "Length", "SeatMouthChamfer"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "FerruleProfile": {"OuterDia": 2, "BoreDia": 2, "Length": 1, "SeatMouthChamfer": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-DT-34 dimension needs authored places")
# The OD is the rod as supplied: a reference, not a turned size.
REFERENCE_DIMENSIONS = frozenset({"OuterDia"})

# The mating part, quoted only to identify it (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)).  Written here rather
# than read from _config.parts so dt-crank-handle.yaml is not a rebuild input; the
# offline test checks it against the registry.
HANDLE_NUMBER = "MHA-DT-08"
HANDLE_NAME = "CRANK HANDLE"
# The tenon root's largest radius on MHA-DT-08, quoted for the chamfer's
# callout: dt_crank_handle_spec.INSIDE_CORNER_R_MAX, which cannot be imported
# here (that spec imports this one); the offline test checks it.
HANDLE_ROOT_R_MAX = 0.3
# The chamfer's band names its end and its reason at the callout (rule 4).
SEAT_MOUTH_CHAMFER_CALLOUT = "\n".join(
    (
        "X 45 DEG SEAT END",
        f"CLEARS {HANDLE_NUMBER}",
        f"TENON ROOT R{HANDLE_ROOT_R_MAX:.1f}",
    )
)
# The oak tenon is turned to suit this bore for an epoxy line (the handle spec
# reads it from here); stated on this sheet too, so the fitted joint has its
# acceptance (MHA-DT-34 re-review).
TENON_GLUE_LINE = (0.05, 0.15)
DRAWING_NOTES = "\n".join(
    (
        "BORE THRU.",
        f"OD AS SUPPLIED (9/16 IN ROD); SKIMMED TO <MOD-DIAM>{INSTALLED_OUTER_DIA:.1f} WITH {HANDLE_NUMBER} AFTER CURE.",
        f"THE {HANDLE_NUMBER} {HANDLE_NAME} TENON IS TURNED TO SUIT THIS BORE FOR",
        f"  {TENON_GLUE_LINE[0]:.2f}-{TENON_GLUE_LINE[1]:.2f} DIAMETRAL CLEARANCE; "
        "EPOXY THE RING ON, SEATED ON ITS SHOULDER.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
