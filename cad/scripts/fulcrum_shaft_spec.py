r"""Pure-data dimensional contract shared by the fulcrum shaft and drawing."""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace, GeometricControl, PartDatum
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

SHAFT_DIA = 0.25 * MM_PER_IN
SHAFT_LENGTH = 182.0
SHAFT_DIA_BAND = SHAFT_H

# No geometric controls: the shaft is one plain cylinder whose running fit is
# the SHAFT_H band on the model diameter (cad/docs/drawing-simplicity-policy.md
# rule 3). The typed tuples stay so build_fulcrum_shaft's author_part_pmi call
# shape is unchanged.
PART_DATUMS: tuple[PartDatum, ...] = ()
GEOMETRIC_CONTROLS: tuple[GeometricControl, ...] = ()
# The bearing OD is the one running surface: the channel levers rock on it
# (rule 5).
SURFACE_FINISHES = (
    SurfaceFinishControl("bearing", MACHINED_UM, CylinderFace(SHAFT_DIA)),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "SectionProfile": {"ShaftDia"},
    "Shaft": {"Depth"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6). The plain-cylinder
# geometry and the turned-or-ground finish are what the views and the title
# block already say (machinist review of the sibling pivot shaft, 2026-09-02).
DRAWING_NOTES = "CENTRES OK."
END_VIEW_NOTE = "END VIEW SCALE 2:1"
# The isometric renders at ISO_SCALE (1, 2) while the sheet/title block reads
# 1:1, so without this the pictorial is silently half scale -- the sheet's own
# title block would misstate it. Mirrors cylinder-gear-shaft, whose identical
# 1:2 iso carries the same note (codex #334).
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
