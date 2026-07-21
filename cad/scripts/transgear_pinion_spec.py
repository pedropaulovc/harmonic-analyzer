r"""Pure-data dimensional contract shared by the transgear pinion + drawing.

The tiny 12T steel "third gear" pinned on the knob shaft; it meshes the 120T
reduction disc for the permanent 1:10 paper-feed reduction. See the batch
gear-drawing pattern in ``cylinder_gear_spec``.
"""

from __future__ import annotations


MM_PER_IN = 25.4

TEETH = 12
DIAMETRAL_PITCH = 38.0            # meshes the 120T disc at its DP (build_transgear_pinion.py)
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN

BORE_DIA = 5.0                    # rides the knob shaft's turned-down Ø5 seat
FACE_WIDTH = 4.0

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
        ("WHOLE DEPTH (mm)", f"{WHOLE_DEPTH:.2f}"),
        ("FACE WIDTH (mm)", f"{FACE_WIDTH:.2f}"),
        ("TOOTH FORM", "INVOLUTE, FULL DEPTH"),
    ]
)

DRAWING_NOTES = "\n".join(
    (
        "CUT TEETH PER GEAR DATA.",
        "GEAR TEETH: CIRCULAR RUNOUT 0.05 MAX TO DATUM A.",
        "MESHES THE 120T REDUCTION DISC (MHA-070) FOR THE 1:10 PAPER FEED.",
    )
)
