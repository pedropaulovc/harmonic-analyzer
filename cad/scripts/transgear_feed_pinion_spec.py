r"""Pure-data dimensional contract shared by the transgear feed pinion + drawing.

The 12T brass feed pinion ("fifth gear") locked behind the reduction disc; its
long face bridges back to mesh the rack. See the batch gear-drawing pattern in
``cylinder_gear_spec``.
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

TEETH = 12
DIAMETRAL_PITCH = 30.0  # meshes the DP30 rack (build_transgear_feed_pinion.py)
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN

BORE_DIA = 5.0  # rides the stud's turned-down Ø5 front seat
FACE_WIDTH = 9.5
BORE_DIA_BAND = (0.05, 0.00)  # admits a nominal 5 mm reamer

# The bore RUNS: the pinion is locked to the reduction disc and the pair spins
# free on the transgear stud (build_paper_drive_assembly: "on the stud the
# 120T disc + 12T feed pinion (locked pair)"; drawing-simplicity-policy.md
# rule 5).
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
        # 30 DP, 14.5 deg full depth already fixes it: reference, not a
        # toleranced size (machinist review 2026-09-02).
        ("WHOLE DEPTH (REF)", f"{WHOLE_DEPTH:.2f}"),
        ("FACE WIDTH", f"{FACE_WIDTH:.2f}"),
        over_pins_row(OVER_PINS),
        ("TOOTH FORM", "INVOLUTE, FULL DEPTH"),
    ]
)

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).  The teeth run the full
# face -- the views show that -- so the only note is what runs on what.
DRAWING_NOTES = "RUNS FREE ON THE STUD, LOCKED TO THE 120T DISC IN FRONT OF IT."
