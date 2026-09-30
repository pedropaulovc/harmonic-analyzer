r"""Pure-data contract for MHA-152, the crank handle's brass ferrule.

User ruling 2026-09-29 (ch11 p.14 and p.15 photographs): the bright ring at the
crank end of the ebonized handle is a separate brass ferrule, not a painted
band on the oak.  It is epoxied on a turned tenon of MHA-022, seated against
the tenon's shoulder, and its outer end face is the face that runs against
the crank arm MHA-020.

The oak tenon is turned to suit this bore, and the handle's end play is set by
facing the MHA-139 shoulder at assembly (user ruling 2026-09-29, after the
MHA-152 machinist review), so no length here is a stack term and every size
but the bore is routine (.X).  The bore keeps a +/-0.10 band (Codex P1/P2 on
#1139, user ruling 2026-09-30): at .X a large bore let the fitted tenon
outgrow the MHA-022 shoulder it seats on, and a small one thinned the oak
round the pivot bore under 1.5.

Local frame: the axis is local +X, the part's origin plane is the arm-bearing
end face (x=0), and the seat face against the oak shoulder is at x=LENGTH --
the handle's own frame, so the drive train places both with one transform.

PURE DATA, no SolidWorks/COM imports.
"""

from __future__ import annotations

# Ø12.5 x 7 (user ruling 2026-09-30, ch30 eight-views-4 side view: the ring
# reads ~Ø11-12, not the Ø15 first derived).  The bore follows the smaller
# MHA-139 shoulder: the tenon over the Ø4.1 pivot bore keeps its 1.5 wall.
OUTER_DIA = 12.5
# Banded (local review of 1f3067ef2): the oak shoulder is turned flush with
# this OD after cure, so the OD's spread must sit inside the grip's 0.5
# contour allowance; at .X it spanned 1.6.
OUTER_DIA_TOL = 0.20
# 7.7 (local review of 1f3067ef2): the fitted tenon keeps 1.5 of oak over the
# reamed pivot bore with 0.10 of eccentricity between them.
BORE_DIA = 7.7
BORE_DIA_TOL = 0.10
LENGTH = 7.0

# Brass wall, on radius, at the worst case: the banded outside over the
# banded bore.
WALL_WORST = ((OUTER_DIA - OUTER_DIA_TOL) - (BORE_DIA + BORE_DIA_TOL)) / 2.0
if WALL_WORST < 1.5:
    raise AssertionError("MHA-152 ferrule wall is under 1.5 at the .X worst case")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FerruleProfile": {"OuterDia", "BoreDia", "Length"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "FerruleProfile": {"OuterDia": 2, "BoreDia": 2, "Length": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-152 dimension needs authored places")

# The mating part, quoted only to identify it (rule 6).  Written here rather
# than read from _config.parts so crank-handle.yaml is not a rebuild input; the
# offline test checks it against the registry.
HANDLE_NUMBER = "MHA-022"
HANDLE_NAME = "CRANK HANDLE"
# The oak tenon is turned to suit this bore for an epoxy line (the handle spec
# reads it from here); stated on this sheet too, so the fitted joint has its
# acceptance (MHA-152 re-review).
TENON_GLUE_LINE = (0.05, 0.15)
DRAWING_NOTES = "\n".join(
    (
        f"THE {HANDLE_NUMBER} {HANDLE_NAME} TENON IS TURNED TO SUIT THIS BORE FOR",
        f"  {TENON_GLUE_LINE[0]:.2f}-{TENON_GLUE_LINE[1]:.2f} DIAMETRAL CLEARANCE; "
        "EPOXY THE RING ON, SEATED ON ITS SHOULDER.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
