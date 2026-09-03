r"""Pure-data dimensional contract shared by the wheel axle and drawing."""

from __future__ import annotations

from _gtol_spec import CylinderFace, GeometricControl, PartDatum
from _surface_finish import MACHINED_UM, SurfaceFinishControl


FLANGE_DIA = 35.0
FLANGE_LEN = 3.0
STUD_DIA = 5.0
STUD_LEN = 14.0
STUD_DIA_BAND = (-0.02, -0.05)
COLLAR_DIA = 9.0
COLLAR_LEN = 4.0

# No geometric controls: the axle is one revolve turned in one setting, and
# the stud's running fit is the band on the model diameter
# (cad/docs/drawing-simplicity-policy.md rule 3). The typed tuples stay so
# build_wheel_axle's author_part_pmi call shape is unchanged.
PART_DATUMS: tuple[PartDatum, ...] = ()
GEOMETRIC_CONTROLS: tuple[GeometricControl, ...] = ()
# The stud OD is the one running surface: the magnifying wheel spins on it
# (rule 5).
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

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = "TURN COMPLETE IN ONE SETUP."
