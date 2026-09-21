r"""Pure-data dimensional contract shared by the alignment pinion and its drawing.

The long 42T brass drum pinion (ch.25) that engages the whole cylinder-gear
train to zero the machine to sines or cosines. See the batch gear-drawing
pattern in ``cylinder_gear_spec``.
"""

from __future__ import annotations

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

TEETH = 42  # cad/config/machine/alignment_pinion.yaml
DIAMETRAL_PITCH = 49.82  # meshes the cylinder train (gear_train.yaml)
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN

BORE_DIA = 8.0  # Ø8 arbor through-bore (build_pinion_arbor.py)
ARBOR_BORE_BAND = (-0.020, -0.040)  # (upper, lower) deviations; matched press
# Finish the bore to the measured MHA-102 shaft. This is a matched-pair
# acceptance range, not an interchangeable limit stack across random parts.
ARBOR_DIAMETRAL_INTERFERENCE_MM = (0.010, 0.030)
FACE_WIDTH = 143.2  # spans all 20 cylinder-gear stations
FACE_WIDTH_TOLERANCE_MM = 0.5
OUTSIDE_DIA_BAND = (0.0, -0.10)  # finished tooth-tip envelope

SURFACE_FINISHES = (
    SurfaceFinishControl("drum_bore", MACHINED_UM, CylinderFace(BORE_DIA)),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GearBlank": {"FaceWidth"},
    "GearBlankProfile": {"OutsideDia"},
    "ArborBoreProfile": {"ArborBoreDia"},
}

DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GearBlank": {"FaceWidth": 1},
    "GearBlankProfile": {"OutsideDia": 2},
    "ArborBoreProfile": {"ArborBoreDia": 2},
}
DRAWING_PRECISION_BY_NAME = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked alignment-pinion dimension needs native precision")


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
        ("WHOLE DEPTH (mm, REF)", f"{WHOLE_DEPTH:.2f}"),
        ("TOOTH FORM", "INVOLUTE, FULL DEPTH"),
    ]
)

DRAWING_NOTES = "\n".join(
    (
        "MATES WITH CYLINDER-GEAR BANK MHA-027.",
        "TOOTH FLANKS, TIPS, AND ROOTS: DO NOT CHAMFER OR BLEND.",
    )
)
