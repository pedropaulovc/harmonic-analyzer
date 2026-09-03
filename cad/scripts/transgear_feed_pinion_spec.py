r"""Pure-data dimensional contract shared by the transgear feed pinion + drawing.

The 12T brass feed pinion ("fifth gear") locked behind the reduction disc; its
long face bridges back to mesh the rack. See the batch gear-drawing pattern in
``cylinder_gear_spec``.
"""

from __future__ import annotations

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

TEETH = 12
DIAMETRAL_PITCH = 30.0  # meshes the DP30 rack (build_transgear_feed_pinion.py)
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN

BORE_DIA = 5.0  # rides the stud's turned-down Ø5 front seat
FACE_WIDTH = 9.5
BORE_DIA_BAND = (0.05, 0.03)

# The bore RUNS: the pinion is locked to the reduction disc and the pair spins
# free on the transgear stud (drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES = (SurfaceFinishControl("bore", MACHINED_UM, CylinderFace(BORE_DIA)),)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BoreProfile": {"BoreDia"},
}


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear/sprocket data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        ("DIAMETRAL PITCH", f"{DIAMETRAL_PITCH:.2f}"),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (REF)", f"{PITCH_DIA:.2f}"),
        ("OUTSIDE DIAMETER", f"{OUTSIDE_DIA:.2f} +0/-0.10"),
        ("WHOLE DEPTH", f"{WHOLE_DEPTH:.2f}"),
        ("FACE WIDTH", f"{FACE_WIDTH:.2f}"),
        ("TOOTH FORM", "INVOLUTE, FULL DEPTH"),
    ]
)

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = "\n".join(
    (
        "TEETH CUT THE FULL FACE: THE LONG FACE REACHES BACK TO MESH THE RACK.",
        "RUNS FREE ON THE STUD, LOCKED TO THE 120T DISC IN FRONT OF IT.",
    )
)
