r"""Pure-data contract for MHA-150, the crank handle's brass ferrule.

User ruling 2026-09-29 (ch11 p.14 and p.15 photographs): the bright ring at the
crank end of the ebonized handle is a separate brass ferrule, not a painted
band on the oak.  It is epoxied on a turned tenon of MHA-022, seated against
the tenon's shoulder, and its outer end face is the face that runs against
the crank arm MHA-020.

Local frame: the axis is local +X, the part's origin plane is the arm-bearing
end face (x=0), and the seat face against the oak shoulder is at x=LENGTH --
the handle's own frame, so the drive train places both with one transform.

PURE DATA, no SolidWorks/COM imports.
"""

from __future__ import annotations

OUTER_DIA = 15.0
# The ring's bore slips over the oak tenon for an epoxy line: (upper, lower)
# deviations from the nominal.  The tenon band lives in crank_handle_spec.
BORE_DIA = 10.00
BORE_DIA_BAND = (0.05, 0.0)
# The ring's length is the first term of the handle's end-play stack
# (crank_handle_pivot_screw_spec): both faces are faced in one setting.
LENGTH = 7.00
LENGTH_TOL = 0.05

# Brass wall, on radius.
WALL = (OUTER_DIA - BORE_DIA) / 2.0
if WALL < 2.0:
    raise AssertionError("MHA-150 ferrule wall is under 2.0")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FerruleProfile": {"OuterDia", "BoreDia", "Length"},
}
# Decimal places are the tolerance (policy rule 2): the bore and the length
# carry their bands at two places; the OD is a free outer surface (.X).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "FerruleProfile": {"OuterDia": 1, "BoreDia": 2, "Length": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-150 dimension needs authored places")

# The mating part, quoted only to identify it (rule 6).  Hard-coded rather than
# read from _config.parts so crank-handle.yaml is not a rebuild input here; the
# offline test checks it against the registry.
HANDLE_NUMBER = "MHA-022"
DRAWING_NOTES = f"EPOXY ON THE {HANDLE_NUMBER} TENON, SEATED ON ITS SHOULDER."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
