r"""Pure-data dimensional contract shared by the rack-pinion disc and its drawing.

The large thin brass 120T reduction disc of the translational gearing ("fourth
gear"); driven 12:120 by the transgear pinion, locked coaxially to the feed
pinion. See the batch gear-drawing pattern in ``cylinder_gear_spec``.
"""

from __future__ import annotations

from _gear_inspection import (
    diametral_pitch_text,
    over_pins_row,
    pin_measurement,
    preferred_pin_dia_mm,
)
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
ROOT_DIA = (TEETH - 2.0 * 1.157) / DIAMETRAL_PITCH * MM_PER_IN

BORE_DIA = 5.0  # shares the stud's Ø5 front seat
FACE_WIDTH = 3.0
BORE_DIA_BAND = (0.05, 0.00)  # admits a nominal 5 mm reamer

# The bore RUNS: the disc spins free on the transgear stud
# (drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES = (SurfaceFinishControl("bore", MACHINED_UM, CylinderFace(BORE_DIA)),)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BoreProfile": {"BoreDia"},
}

# Over-pins acceptance (Machinery's Handbook 1.92/P wire, see _gear_inspection).
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
        # A cutter setting, not an inspection: the over-pins row is the
        # acceptance (the block .XX band on a 1.44 depth was the review's
        # blocker), so the depth reads as reference.
        ("WHOLE DEPTH (REF)", f"{WHOLE_DEPTH:.2f}"),
        ("FACE WIDTH", f"{FACE_WIDTH:.2f}"),
        over_pins_row(OVER_PINS),
        ("TOOTH FORM", "INVOLUTE, FULL DEPTH"),
    ]
)

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = "RUNS FREE ON THE STUD; MATES WITH THE 12T FEED PINION BEHIND IT."
