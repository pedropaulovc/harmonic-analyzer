r"""Pure-data dimensional contract shared by the alignment pinion and its drawing.

The long 42T brass drum pinion (ch.25) that engages the whole cylinder-gear
train to zero the machine to sines or cosines. See the batch gear-drawing
pattern in ``cylinder_gear_spec``.
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

TEETH = 42  # cad/config/machine/alignment_pinion.yaml
DIAMETRAL_PITCH = 49.82  # meshes the cylinder train (gear_train.yaml)
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN
ROOT_DIA = (TEETH - 2.0 * 1.157) / DIAMETRAL_PITCH * MM_PER_IN

BORE_DIA = 8.0  # Ø8 arbor through-bore (build_pinion_arbor.py)
ARBOR_BORE_BAND = (-0.020, -0.040)  # light press; (upper, lower) deviations
FACE_WIDTH = 143.2  # spans all 20 drum stations

# No roughness callouts: the drum is pressed onto its steel arbor, so nothing
# runs on the bore; the title block's Ra 3.2 covers every face
# (cad/docs/drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ArborBoreProfile": {"ArborBoreDia"},
}

# The whole fit instruction lives at the bore leader (DETAIL B), not in a
# note (machinist review 2026-09-02: one place, not two wordings).
BORE_CALLOUT = "REAM THRU\nLIGHT PRESS ON ARBOR, FINISH TO FIT"

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
        ("WHOLE DEPTH (REF)", f"{WHOLE_DEPTH:.2f}"),
        ("FACE WIDTH", f"{FACE_WIDTH:.1f}"),
        over_pins_row(OVER_PINS),
        ("TOOTH FORM", "INVOLUTE, FULL DEPTH"),
    ]
)

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).  The full-length teeth
# are what SECTION A-A shows and the press fit is at the bore leader.
DRAWING_NOTES = "MATES WITH THE 20 CYLINDER GEARS; PRESSED ON THE PINION ARBOR."
