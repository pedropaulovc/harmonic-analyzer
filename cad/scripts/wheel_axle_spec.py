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
OVERALL_LEN = FLANGE_LEN + STUD_LEN  # 17.0 bar-side face to the stud tip
COLLAR_START = OVERALL_LEN - COLLAR_LEN  # 13.0 bar-side face to the collar

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

# Marked model dimensions: the three diameters plus the axial stations from
# the flange's bar-side (faced) end -- 3.00 to the flange top, 13.00 to the
# collar (the extrusion's named start offset), with the collar's own 4.00 a
# reference; the drawing adds the 17.00 overall between the end faces
# (policy rule 7; machinist review 2026-09-02: the 14.00 stud length read as
# the overall and the dims ran from several faces).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FlangeProfile": {"FlangeDia"},
    "StudProfile": {"StudDia"},
    "CollarProfile": {"CollarDia"},
    "Flange": {"FlangeLength"},
    "Collar": {"CollarStart", "CollarLength"},
}

# The two concave shoulder roots (flange -> stud, stud -> collar) are
# modelled sharp; the print allows the turning tool's nose radius as a
# leadered note on one shoulder rather than a fillet feature (policy rule 7:
# every shoulder fillet on a turned part has a size; machinist review
# 2026-09-02: an unspecified root is a bench question). The wheel hub rides
# the stud mid-span, so R0.25 MAX at either root is a clearance, not a fit.
ROOT_NOTE = "2X ROOT R0.25 MAX"

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = "TURN COMPLETE IN ONE SETUP."
