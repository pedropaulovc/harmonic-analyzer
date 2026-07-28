r"""Pure-data dimensional contract shared by the pinion arbor and drawing."""

from __future__ import annotations

from _gtol_spec import CylinderFace, GeometricControl, PartDatum, PlanarFace


SHAFT_DIA = 8.0
SHAFT_LEN = 226.25
CAP_SAG = 1.2
CAP_R = (SHAFT_DIA / 2.0) ** 2 / (2.0 * CAP_SAG) + CAP_SAG / 2.0  # 7.27

# Geometric controls, authored on the MODEL as DimXpert PMI by the part build
# (_part_pmi.author_part_pmi) and IMPORTED onto the sheet — the sheet types no
# tolerance strings. The arbor is one Ø8 bearing cylinder plus the flat front
# tip (the -Z face at z=0; the back end is the crown, which has no face to
# square to the axis).
PART_DATUMS = (
    # The bearing shaft axis the flat tip is squared against.
    PartDatum("A", CylinderFace(SHAFT_DIA)),
)
GEOMETRIC_CONTROLS = (
    GeometricControl(
        "bearing_cylindricity", "cylindricity", "0.01", CylinderFace(SHAFT_DIA)
    ),
    GeometricControl(
        "flat_tip_perpendicularity",
        "perpendicularity",
        "0.05",
        PlanarFace((0, 0, -1), 0.0),
        datums=("A",),
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDia"},
    "Shaft": {"Depth"},
    "BackCapProfile": {"CapSagDim"},
}

DRAWING_NOTES = "\n".join(
    (
        "CENTRE MARKS 1.0 DEEP MAX.",
        "TURN OR CENTRELESS-GRIND FULL BEARING LENGTH; NO FLATS OR STEPS.",
        f"CROWN BACK END SR{CAP_R:.2f} X {CAP_SAG:g} HIGH; BLEND SMOOTH, NO SHARP RIM.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 2:1"
