r"""Pure-data dimensional contract shared by the wheel axle and drawing."""

from __future__ import annotations

from _gtol_spec import CylinderFace, GeometricControl, PartDatum
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

# The washer splits the stud exterior into two diameter-5 faces. Select the
# running surface at a station inside the wheel-hub span.
STUD_BEARING_FACE = CylinderFace(
    STUD_DIA,
    contains_y_mm=FLANGE_LEN + WHEEL_HUB_RIDE / 2.0,
)

# No geometric controls: the axle is one revolve turned in one setting, and
# the stud's running fit is the band on the model diameter
# (cad/docs/drawing-simplicity-policy.md rule 3). The typed tuples stay so
# build_wheel_axle's author_part_pmi call shape is unchanged.
PART_DATUMS: tuple[PartDatum, ...] = ()
GEOMETRIC_CONTROLS: tuple[GeometricControl, ...] = ()
# The stud OD is the one running surface: the magnifying wheel spins on it
# (rule 5).
SURFACE_FINISHES = (
    SurfaceFinishControl("stud_bearing", MACHINED_UM, STUD_BEARING_FACE),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FlangeProfile": {"FlangeDia"},
    "StudProfile": {"StudDia"},
    "CollarProfile": {"CollarDia"},
    "Flange": {"FlangeLength"},
    "Stud": {"StudLength"},
    "Collar": {"CollarLength"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = "TURN COMPLETE IN ONE SETUP."
