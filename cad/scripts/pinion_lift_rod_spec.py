r"""Pure-data dimensional contract shared by the pinion lift rod and drawing."""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

ROD_DIA = 6.35
ROD_LEN = 202.0
CAP_SAG = 1.2
CAP_R = round((ROD_DIA**2 / 4.0 + CAP_SAG**2) / (2.0 * CAP_SAG), 2)  # 4.80
OVERALL_LEN = ROD_LEN + CAP_SAG  # 203.2 crown tip to the flat front end
ROD_DIA_BAND = SHAFT_H
ROD_LENGTH_TOLERANCE_MM = 0.25

# The rod OD is the one running surface: the rod spins in the pivot-block
# bores as the cam input (cad/docs/drawing-simplicity-policy.md rule 5). No
# geometric controls: the running fit is the SHAFT_H band on the model
# diameter (rule 3).
SURFACE_FINISHES = (
    SurfaceFinishControl("bearing", MACHINED_UM, CylinderFace(ROD_DIA)),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"RodDia"},
    "Rod": {"Depth"},
}

# The crown's spherical radius and height, as the leadered note on the side
# view spells them (its sketch dims live on the Top plane, outside every
# placed view, so the crown is conveyed by a note ATTACHED to the crowned end
# rather than buried in the block -- machinist review 2026-09-02). Numbers in
# a note carry a decimal (policy rule 6).
CROWN_NOTE = "\n".join(
    (
        f"CROWN SR{CAP_R:.2f} X {CAP_SAG:.2f} HIGH",
        "BLEND SMOOTH, NO STEP",
    )
)

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6). The length tolerance
# rides the Depth dimension; the turned-or-ground finish and "no flats or
# steps" were what the title block and the views already say (machinist
# review, 2026-09-02). The rod is the same 1/4 in ground shafting as its
# sibling torque shaft, whose h band the SHAFT_H diameter already is.
DRAWING_NOTES = "GROUND 1/4 IN SHAFTING OK AS RECEIVED."
END_VIEW_NOTE = "END VIEW SCALE 2:1"
