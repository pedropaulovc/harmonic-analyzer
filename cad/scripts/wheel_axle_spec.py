r"""Pure-data dimensional contract shared by the wheel axle and drawing."""

from __future__ import annotations

from _gtol_spec import CylinderFace, GeometricControl, PartDatum, PlanarFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


FLANGE_DIA = 35.0
FLANGE_LEN = 3.0
STUD_DIA = 5.0
STUD_LEN = 17.0  # 2026-09-02: runs through the washer + hex nut (ch21 p.51), tip 3 proud
STUD_DIA_BAND = (-0.02, -0.05)
WHEEL_HUB_RIDE = 10.0
WASHER_START = FLANGE_LEN + WHEEL_HUB_RIDE
COLLAR_DIA = 9.0  # the WASHER under the nut (2026-09-02: the collar was the photo's
# washer + hex nut collapsed; the nut is now its own part, wheel-axle-nut)
COLLAR_LEN = 1.0
NUT_AF = 8.0  # hex nut across flats (ch21 p.51, low)
NUT_H = 3.0
NUT_BORE_DIA = 5.1  # slips the O5 stud (0.05 radial)

# Geometric controls, authored on the model as plain annotations by the part build
# (_part_pmi.author_part_pmi) and IMPORTED onto the sheet — the sheet types no
# tolerance strings. Axis +Y from the flange's bar-side face: flange Ø35
# y 0..3, stud Ø5 y 3..20, washer Ø9 y 13..14, so each face resolves by its
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
        tolerance_zone="diametral",
    ),
    GeometricControl(
        "collar_runout",
        "circular_runout",
        "0.05",
        CylinderFace(COLLAR_DIA),
        datums=("B",),
    ),
)
SURFACE_FINISHES = (
    SurfaceFinishControl("stud_bearing", MACHINED_UM, CylinderFace(STUD_DIA)),
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
