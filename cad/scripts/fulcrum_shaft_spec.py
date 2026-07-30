r"""Pure-data dimensional contract shared by the fulcrum shaft and drawing."""

from __future__ import annotations

from _gtol_spec import CylinderFace, GeometricControl, PartDatum, PlanarFace


MM_PER_IN = 25.4

SHAFT_DIA = 0.25 * MM_PER_IN
SHAFT_LENGTH = 182.0

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

DRAWING_NOTES = "\n".join(
    (
        "CENTRE MARKS 1.0 DEEP MAX.",
        "TURN OR CENTRELESS-GRIND FULL BEARING LENGTH; NO FLATS OR STEPS.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 2:1"
# The isometric renders at ISO_SCALE (1, 2) while the sheet/title block reads
# 1:1, so without this the pictorial is silently half scale -- the sheet's own
# title block would misstate it. Mirrors cylinder-gear-shaft, whose identical
# 1:2 iso carries the same note (codex #334).
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
