r"""Pure-data dimensional contract shared by the alignment pinion and its drawing.

The long 42T brass drum pinion (ch.25) that engages the whole cylinder-gear
train to zero the machine to sines or cosines. See the batch gear-drawing
pattern in ``cylinder_gear_spec``.
"""

from __future__ import annotations


MM_PER_IN = 25.4

TEETH = 42                        # cad/config/machine/alignment_pinion.yaml
DIAMETRAL_PITCH = 49.82           # meshes the cylinder train (gear_train.yaml)
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN

BORE_DIA = 8.0                    # Ø8 arbor through-bore (build_pinion_arbor.py)
FACE_WIDTH = 143.2                # spans all 20 drum stations

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ArborBoreProfile": {"ArborBoreDia"},
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
        ("FACE WIDTH (mm)", f"{FACE_WIDTH:.1f}"),
        ("TOOTH FORM", "INVOLUTE, FULL DEPTH"),
    ]
)

DRAWING_NOTES = "\n".join(
    (
        "CUT TEETH FULL LENGTH PER GEAR DATA.",
        "GEAR TEETH: CIRCULAR RUNOUT 0.05 MAX ABOUT DATUM A, MEASURED AT THE TOOTH TIPS.",
        f"LONG PINION DRUM: FACE {FACE_WIDTH:.1f}; SPANS ALL 20 CYLINDER-GEAR STATIONS.",
        "Ø8 STEEL ARBOR (MHA-102) PRESSES THROUGH THE BORE.",
    )
)
