r"""Pure-data dimensional contract shared by the wheel axle and drawing."""

from __future__ import annotations

from _gtol_spec import CylinderFace, GeometricControl, PartDatum, PlanarFace


FLANGE_DIA = 35.0
FLANGE_LEN = 3.0
STUD_DIA = 5.0
STUD_LEN = 14.0
COLLAR_DIA = 9.0
COLLAR_LEN = 4.0

# Geometric controls, authored on the MODEL as DimXpert PMI by the part build
# (_part_pmi.author_part_pmi) and IMPORTED onto the sheet — the sheet types no
# tolerance strings. Axis +Y from the flange's bar-side face: flange Ø35
# y 0..3, stud Ø5 y 3..17, collar Ø9 y 13..17, so each face resolves by its
# diameter (the flange seating face by its -Y normal at y=0).
PART_DATUMS = (
    # The flange's bar-side seating face, then the stud bearing axis.
    PartDatum("A", PlanarFace((0, -1, 0), 0.0)),
    PartDatum("B", CylinderFace(STUD_DIA)),
)
GEOMETRIC_CONTROLS = (
    GeometricControl(
        "stud_perpendicularity",
        "perpendicularity",
        "0.05",
        CylinderFace(STUD_DIA),
        datums=("A",),
        diameter=True,
    ),
    GeometricControl(
        "collar_runout", "circular_runout", "0.05", CylinderFace(COLLAR_DIA), datums=("B",)
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FlangeProfile": {"FlangeDia"},
    "StudProfile": {"StudDia"},
    "CollarProfile": {"CollarDia"},
    "Flange": {"FlangeLength"},
    "Stud": {"StudLength"},
    "Collar": {"CollarLength"},
}

DRAWING_NOTES = "\n".join(
    (
        "TURN COMPLETE IN ONE SETUP; STUD OD IS THE WHEEL BEARING SURFACE -- "
        "NO TOOL MARKS OR STEPS.",
    )
)
