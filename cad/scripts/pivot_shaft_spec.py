r"""Pure-data dimensional contract shared by the pivot shaft and drawing."""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace, GeometricControl, PartDatum
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

SHAFT_DIA = 0.25 * MM_PER_IN
SHAFT_LENGTH = 170.0  # 2026-09: was 203.2 (8 in); the shaft now ends 4 past
# each pivot-bracket ear (ch14 page002_img07 shows a near-flush domed end)
SHAFT_DIA_BAND = SHAFT_H
LENGTH_TOLERANCE_MM = 0.25

# No geometric controls: the shaft is one plain cylinder whose running fit is
# the SHAFT_H band on the model diameter (cad/docs/drawing-simplicity-policy.md
# rule 3). The typed tuples stay so build_pivot_shaft's author_part_pmi call
# shape is unchanged.
PART_DATUMS: tuple[PartDatum, ...] = ()
GEOMETRIC_CONTROLS: tuple[GeometricControl, ...] = ()
# The bearing OD is the one running surface: the rocker arms swing on it
# (rule 5).
SURFACE_FINISHES = (
    SurfaceFinishControl("pivot_bearing", MACHINED_UM, CylinderFace(SHAFT_DIA)),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "SectionProfile": {"ShaftDia"},
    "Shaft": {"Depth"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6). The length tolerance
# rides the Depth dimension itself; the plain-cylinder geometry and the
# turned-or-ground finish are what the views and the title block already
# say (machinist review, 2026-09-02).
DRAWING_NOTES = "CENTRES OK."
END_VIEW_NOTE = "END VIEW SCALE 2:1"
