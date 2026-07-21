r"""Pure-data dimensional contract shared by the crank-drive gear and its drawing.

The dark steel 64T gear at the cone set's large end; it carries the crossed-axis
helical accommodation for its 16T crank pinion mate. See the batch gear-drawing
pattern in ``cylinder_gear_spec``.
"""

from __future__ import annotations

import math


MM_PER_IN = 25.4

TEETH = 64
DIAMETRAL_PITCH = 26.57           # crank_drive_diametral_pitch (gear_train.yaml)
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN
ROOT_DIA = (TEETH - 2.0 * 1.157) / DIAMETRAL_PITCH * MM_PER_IN
HELIX_ANGLE_DEG = 12.52           # crossed-axis accommodation (build docstring)
BACKLASH_MM = 0.15

BORE_DIA = 0.375 * MM_PER_IN       # 9.525 (3/8" cone-shaft journal)
FACE_WIDTH = 10.0
TOTAL_TWIST_DEG = math.degrees(
    FACE_WIDTH * math.tan(math.radians(HELIX_ANGLE_DEG)) / (PITCH_DIA / 2.0)
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
        ("WHOLE DEPTH (mm)", f"{WHOLE_DEPTH:.2f}"),
        ("ROOT DIAMETER (mm)", f"{ROOT_DIA:.2f}"),
        ("FACE WIDTH (mm)", f"{FACE_WIDTH:.2f}"),
        ("TOOTH FORM", "INVOLUTE, FULL DEPTH"),
        ("HELIX ANGLE", f"{HELIX_ANGLE_DEG:.2f} DEG"),
        ("HELIX TWIST", f"+{TOTAL_TWIST_DEG:.2f} DEG, -Z TO +Z"),
        ("BACKLASH (mm)", f"{BACKLASH_MM:.2f}"),
        ("MATING PINION", "16T (MHA-025)"),
    ]
)

DRAWING_NOTES = "\n".join(
    (
        "CUT TEETH PER GEAR DATA.",
        "GEAR TEETH: CIRCULAR RUNOUT 0.05 MAX TO DATUM A.",
        "POSITIVE HELIX: GAP ADVANCES CCW -Z TO +Z, VIEWED FROM +Z.",
        "ROOT FLOOR IS A CONCENTRIC ARC AT THE ROOT DIAMETER ABOVE.",
        "HELICAL FLANKS ACCOMMODATE THE CROSSED-AXIS 16T CRANK-PINION MESH.",
    )
)
