r"""Pure-data dimensional contract shared by the pinion arbor and drawing."""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace, GeometricControl, PartDatum
from _surface_finish import MACHINED_UM, SurfaceFinishControl


SHAFT_DIA = 8.0
SHAFT_LEN = 226.25
SHAFT_DIA_BAND = SHAFT_H
CAP_SAG = 1.2
CAP_R = (SHAFT_DIA / 2.0) ** 2 / (2.0 * CAP_SAG) + CAP_SAG / 2.0  # 7.27
OVERALL_LEN = SHAFT_LEN + CAP_SAG  # 227.45 crown tip to the flat front end

# No geometric controls: the arbor is one bearing cylinder plus a crowned
# back end, and its running fit is the SHAFT_H band on the model diameter
# (cad/docs/drawing-simplicity-policy.md rule 3). The typed tuples stay so
# build_pinion_arbor's author_part_pmi call shape is unchanged.
PART_DATUMS: tuple[PartDatum, ...] = ()
GEOMETRIC_CONTROLS: tuple[GeometricControl, ...] = ()
# The bearing OD is the one running surface: the arbor turns in the strap
# bores under the zeroing crank (rule 5).
SURFACE_FINISHES = (
    SurfaceFinishControl("bearing", MACHINED_UM, CylinderFace(SHAFT_DIA)),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDia"},
    "Shaft": {"Depth"},
    "BackCapProfile": {"CapSagDim"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6). The crown's SR and
# height ride the CapSagDim callout in the enlarged crown detail; the
# turned-or-ground finish and "no flats or steps" were what the title block
# and the views already say (machinist review, 2026-09-02).
DRAWING_NOTES = "\n".join(
    (
        "CENTRES OK.",
        "BLEND THE CROWN SMOOTH; NO SHARP RIM.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 2:1"
