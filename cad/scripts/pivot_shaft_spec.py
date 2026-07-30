r"""Pure-data dimensional contract shared by the pivot shaft and drawing."""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace, GeometricControl, PartDatum, PlanarFace


MM_PER_IN = 25.4

SHAFT_DIA = 0.25 * MM_PER_IN
SHAFT_LENGTH = 203.2
SHAFT_DIA_BAND = SHAFT_H
LENGTH_TOLERANCE_MM = 0.25

# Geometric controls, authored on the model as plain annotations by the part build
# (_part_pmi.author_part_pmi) and IMPORTED onto the sheet — the sheet types no
# tolerance strings. The shaft is one plain cylinder (mid-plane extrude, z
# ±SHAFT_LENGTH/2), so the bearing face resolves by diameter alone and each
# end face by its outward normal + offset.
PART_DATUMS = (
    # The bearing axis the end squareness is measured against.
    PartDatum("A", CylinderFace(SHAFT_DIA)),
)
GEOMETRIC_CONTROLS = (
    GeometricControl(
        "bearing_cylindricity", "cylindricity", "0.01", CylinderFace(SHAFT_DIA)
    ),
    GeometricControl(
        "plus_z_end_perpendicularity",
        "perpendicularity",
        "0.05",
        PlanarFace((0, 0, 1), SHAFT_LENGTH / 2.0),
        datums=("A",),
    ),
    GeometricControl(
        "minus_z_end_perpendicularity",
        "perpendicularity",
        "0.05",
        PlanarFace((0, 0, -1), SHAFT_LENGTH / 2.0),
        datums=("A",),
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "SectionProfile": {"ShaftDia"},
    "Shaft": {"Depth"},
}

# The length tolerance rides the 203.20 dimension itself (a machinist review
# flagged a tolerance living only in a general note as easy to miss), so the
# note carries just the finishing requirements.
DRAWING_NOTES = "\n".join(
    (
        "CENTRE MARKS 1.0 DEEP MAX.",
        "TURN OR CENTRELESS-GRIND FULL BEARING LENGTH; NO FLATS OR STEPS.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 2:1"
