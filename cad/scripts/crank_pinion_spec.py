r"""Pure-data dimensional contract shared by the crank pinion and its drawing.

The 16T straight-spur pinion on the crankshaft that meshes the 64T crank-drive
gear (4:1 crank-to-cone reduction). See the batch gear-drawing pattern in
``cylinder_gear_spec``.
"""

from __future__ import annotations


MM_PER_IN = 25.4

TEETH = 16
DIAMETRAL_PITCH = 26.57           # crank_drive_diametral_pitch (gear_train.yaml)
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN
ROOT_DIA = (TEETH - 2.0 * 1.157) / DIAMETRAL_PITCH * MM_PER_IN

BORE_DIA = 0.375 * MM_PER_IN       # 9.525 (3/8" crankshaft)
FACE_WIDTH = 10.8

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
        ("ROOT DIAMETER (mm)", f"{ROOT_DIA:.2f}"),
        ("FACE WIDTH (mm)", f"{FACE_WIDTH:.2f}"),
        ("TOOTH FORM", "INVOLUTE, FULL DEPTH"),
        ("MATING GEAR", "64T (MHA-021)"),
    ]
)

DRAWING_NOTES = "\n".join(
    (
        "CUT TEETH PER GEAR DATA.",
        "PINION BLANK CONCENTRIC WITH BORE WITHIN 0.05 TIR.",
        "ROOT FLOOR IS A CONCENTRIC ARC AT THE ROOT DIAMETER ABOVE.",
        "REMOVABLE ON THE CRANKSHAFT.",
    )
)
