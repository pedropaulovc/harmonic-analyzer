r"""Dimensional contract shared by the lever-bushing part and drawing.

PURE DATA: keep the turned-part nominals and marked-dimension map here so a
change rebuilds both the SLDPRT and SLDDRW recipes without making the drawing
import the part build implementation.
"""

from __future__ import annotations

from _gtol_spec import CylinderFace, GeometricControl, PartDatum, PlanarFace


OUTER_DIA = 12.0
BORE_DIA = 6.5
LENGTH = 4.0565
BORE_DIA_BAND = (0.03, 0.00)
LENGTH_TOLERANCE_MM = 0.03

# Geometric controls, authored on the model as plain annotations by the part build
# (_part_pmi.author_part_pmi) and IMPORTED onto the sheet — the sheet types no
# tolerance strings. The bushing is one annulus, axis along Z, mid-plane
# extruded z ±(LENGTH/2), so each face resolves by diameter or end normal.
PART_DATUMS = (
    # The bore axis the OD runout is measured against, then the reference end.
    PartDatum("A", CylinderFace(BORE_DIA)),
    PartDatum("B", PlanarFace((0, 0, 1), LENGTH / 2.0)),
)
GEOMETRIC_CONTROLS = (
    GeometricControl(
        "od_runout", "circular_runout", "0.05", CylinderFace(OUTER_DIA), datums=("A",)
    ),
    GeometricControl(
        "end_face_parallelism",
        "parallelism",
        "0.03",
        PlanarFace((0, 0, -1), LENGTH / 2.0),
        datums=("B",),
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "AnnulusProfile": {"OuterDia", "BoreDia"},
    "Bushing": {"Depth"},
}

DRAWING_NOTES = "\n".join(
    (
        "AVOID BORE BELL-MOUTH.",
        "TURN OD/FACES IN ONE SETUP; DRILL UNDERSIZE AND REAM BORE THRU.",
    )
)
