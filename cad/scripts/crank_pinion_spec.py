r"""Pure-data dimensional contract shared by the crank pinion and its drawing.

The 16T straight-spur pinion on the crankshaft that meshes the 64T crank-drive
gear (4:1 crank-to-cone reduction). See the batch gear-drawing pattern in
``cylinder_gear_spec``.
"""

from __future__ import annotations

import math

from _surface_finish import SurfaceFinishControl


MM_PER_IN = 25.4

TEETH = 16
DIAMETRAL_PITCH = 25.73110354953376  # fixed-post recentered mesh
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
BASE_DIA = PITCH_DIA * math.cos(math.radians(PRESSURE_ANGLE_DEG))
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN
ROOT_DIA = (TEETH - 2.0 * 1.157) / DIAMETRAL_PITCH * MM_PER_IN
PAIR_SHAFT_ANGLE_DEG = 12.52  # crossed axes against the 64T helical gear

BORE_DIA = 0.375 * MM_PER_IN  # 9.525 (3/8" crankshaft)
BORE_DIA_BAND = (0.050, 0.030)  # (upper, lower) deviations
FACE_WIDTH = 10.8

# No roughness callouts: the pinion is keyed to the crankshaft (it is the
# crank's drive), so nothing runs on the bore; the title block's Ra 3.2 covers
# every face (cad/docs/drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

# Derived tooth geometry -- the analytic record the build's constants are
# checked against (test_crank_pinion_drawing).  The pinion is a standard
# tooth: all the pair's backlash is thinned off the 64T.
TRANSVERSE_CIRCULAR_TOOTH_THICKNESS = math.pi * MODULE_MM / 2.0

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
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (REF)", f"{PITCH_DIA:.2f}"),
        ("OUTSIDE DIAMETER", f"{OUTSIDE_DIA:.2f} +0/-0.10"),
        ("WHOLE DEPTH", f"{WHOLE_DEPTH:.2f}"),
        ("FACE WIDTH", f"{FACE_WIDTH:.2f}"),
        ("CIRCULAR TOOTH THICKNESS", f"{TRANSVERSE_CIRCULAR_TOOTH_THICKNESS:.3f}"),
        ("TOOTH FORM", "SPUR INVOLUTE, FULL DEPTH"),
        (
            "MATES WITH",
            f"64T HELICAL CRANK-DRIVE GEAR, {PAIR_SHAFT_ANGLE_DEG:.2f} DEG CROSSED AXES",
        ),
    ]
)

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = "\n".join(
    (
        "DO NOT CHAMFER OR BLEND TOOTH FLANKS, TIPS OR ROOTS.",
        "FIXED TO THE CRANKSHAFT AT ASSEMBLY.",
    )
)
