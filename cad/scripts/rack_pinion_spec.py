r"""Pure-data dimensional contract shared by the rack-pinion disc and its drawing.

The large thin brass 120T reduction disc of the translational gearing ("fourth
gear"); driven 12:120 by the transgear pinion, locked coaxially to the feed
pinion. See the batch gear-drawing pattern in ``cylinder_gear_spec``.
"""

from __future__ import annotations

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

TEETH = 120
DIAMETRAL_PITCH = 38.0  # disc OD ~82 at 120T (build_rack_pinion.py)
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN

BORE_DIA = 5.0  # shares the stud's Ø5 front seat
FACE_WIDTH = 3.0
BORE_DIA_BAND = (0.05, 0.03)

SURFACE_FINISHES = (
    SurfaceFinishControl("bore", MACHINED_UM, CylinderFace(BORE_DIA)),
)

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
        ("MODULE (mm, REF)", f"{MODULE_MM:.3f}"),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (mm, REF)", f"{PITCH_DIA:.2f}"),
        ("OUTSIDE DIAMETER (mm)", f"{OUTSIDE_DIA:.2f} +0/-0.10"),
        ("WHOLE DEPTH (mm)", f"{WHOLE_DEPTH:.2f} REF"),
        ("FACE WIDTH (mm)", f"{FACE_WIDTH:.2f}"),
        ("TOOTH FORM", "INVOLUTE, FULL DEPTH"),
    ]
)

DRAWING_NOTES = "\n".join(
    (
        "CUT TEETH PER GEAR DATA.",
        "THIN DISC GEAR; GEAR TEETH: CIRCULAR RUNOUT 0.05 MAX ABOUT DATUM A, MEASURED AT THE TOOTH TIPS.",
        "DRIVEN 12:120 BY THE TRANSGEAR PINION (MHA-080).",
        "LOCKED COAXIAL TO THE 12T FEED PINION (MHA-110).",
    )
)
