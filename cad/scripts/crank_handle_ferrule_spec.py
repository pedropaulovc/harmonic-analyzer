r"""Pure-data contract for MHA-150, the crank handle's brass ferrule.

User ruling 2026-09-29 (ch11 p.14 and p.15 photographs): the bright ring at the
crank end of the ebonized handle is a separate brass ferrule, not a painted
band on the oak.  It is epoxied on a turned tenon of MHA-022, seated against
the tenon's shoulder, and its outer end face is the face that runs against
the crank arm MHA-020.

Every size is routine (.X): the oak tenon is turned to suit this bore, and the
handle's end play is set by facing the MHA-139 shoulder at assembly (user
ruling 2026-09-29, after the MHA-150 machinist review), so no length here is a
stack term.

Local frame: the axis is local +X, the part's origin plane is the arm-bearing
end face (x=0), and the seat face against the oak shoulder is at x=LENGTH --
the handle's own frame, so the drive train places both with one transform.

PURE DATA, no SolidWorks/COM imports.
"""

from __future__ import annotations

OUTER_DIA = 15.0
BORE_DIA = 10.0
LENGTH = 7.0

# Brass wall, on radius, at the title block's .X worst case.
GENERAL_1PL_MM = 0.8
WALL_WORST = ((OUTER_DIA - GENERAL_1PL_MM) - (BORE_DIA + GENERAL_1PL_MM)) / 2.0
if WALL_WORST < 1.5:
    raise AssertionError("MHA-150 ferrule wall is under 1.5 at the .X worst case")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FerruleProfile": {"OuterDia", "BoreDia", "Length"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "FerruleProfile": {"OuterDia": 1, "BoreDia": 1, "Length": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-150 dimension needs authored places")

# The mating part, quoted only to identify it (rule 6).  Written here rather
# than read from _config.parts so crank-handle.yaml is not a rebuild input; the
# offline test checks it against the registry.
HANDLE_NUMBER = "MHA-022"
HANDLE_NAME = "CRANK HANDLE"
# The oak tenon is turned to suit this bore for an epoxy line (the handle spec
# reads it from here); stated on this sheet too, so the bore's loose band has
# its acceptance (MHA-150 re-review).
TENON_GLUE_LINE = (0.05, 0.15)
DRAWING_NOTES = "\n".join(
    (
        f"THE {HANDLE_NUMBER} {HANDLE_NAME} TENON IS TURNED TO SUIT THIS BORE FOR",
        f"  {TENON_GLUE_LINE[0]:.2f}-{TENON_GLUE_LINE[1]:.2f} DIAMETRAL CLEARANCE; "
        "EPOXY THE RING ON, SEATED ON ITS SHOULDER.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
