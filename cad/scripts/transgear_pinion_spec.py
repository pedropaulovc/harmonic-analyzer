r"""Pure-data dimensional contract shared by the transgear pinion + drawing.

The tiny 12T steel "third gear" pinned on the knob shaft; it meshes the 120T
reduction disc for the permanent 1:10 paper-feed reduction. See the batch
gear-drawing pattern in ``cylinder_gear_spec``.
"""

from __future__ import annotations

from _gear_inspection import (
    diametral_pitch_text,
    over_pins_row,
    pin_measurement,
    preferred_pin_dia_mm,
)
from _surface_finish import SurfaceFinishControl


MM_PER_IN = 25.4

TEETH = 12
DIAMETRAL_PITCH = 38.0  # meshes the 120T disc at its DP (build_transgear_pinion.py)
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN

BORE_DIA = 5.0  # rides the knob shaft's turned-down Ø5 seat
FACE_WIDTH = 4.0
BORE_DIA_BAND = (0.05, 0.00)  # admits a nominal 5 mm reamer

# No roughness callouts: the pinion is locked to the knob shaft (the knob
# cluster turns as one body), so nothing runs on the bore; the title block's
# Ra 3.2 covers every face (cad/docs/drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BoreProfile": {"BoreDia"},
}

# Over-pins acceptance (Machinery's Handbook 1.92/P wire, see _gear_inspection):
# the tooth-to-bore relationship the review asked for is checked with the
# same pin walked round the tooth spaces against the reamed bore.
PIN_DIA_MM = preferred_pin_dia_mm(DIAMETRAL_PITCH)
OVER_PINS = pin_measurement(
    teeth=TEETH,
    diametral_pitch=DIAMETRAL_PITCH,
    pressure_angle_deg=PRESSURE_ANGLE_DEG,
    pin_dia_mm=PIN_DIA_MM,
)


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear/sprocket data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        ("DIAMETRAL PITCH", diametral_pitch_text(DIAMETRAL_PITCH)),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (REF)", f"{PITCH_DIA:.2f}"),
        ("OUTSIDE DIAMETER", f"{OUTSIDE_DIA:.2f} +0/-0.10"),
        ("WHOLE DEPTH (REF)", f"{WHOLE_DEPTH:.2f}"),
        ("FACE WIDTH", f"{FACE_WIDTH:.2f}"),
        over_pins_row(OVER_PINS),
        ("TOOTH FORM", "INVOLUTE, FULL DEPTH"),
    ]
)

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = "FIXED TO THE KNOB SHAFT AT ASSEMBLY; MATES WITH THE 120T REDUCTION DISC."
