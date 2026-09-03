r"""Pure-data dimensional contract shared by the crank-drive gear and its drawing.

The dark steel 64T gear at the cone set's large end; it carries the crossed-axis
helical accommodation for its 16T crank pinion mate. See the batch gear-drawing
pattern in ``cylinder_gear_spec``.
"""

from __future__ import annotations

import math

from _surface_finish import SurfaceFinishControl


MM_PER_IN = 25.4

TEETH = 64
DIAMETRAL_PITCH = 25.73110354953376  # fixed-post recentered mesh
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
BASE_DIA = PITCH_DIA * math.cos(math.radians(PRESSURE_ANGLE_DEG))
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN
ROOT_DIA = (TEETH - 2.0 * 1.157) / DIAMETRAL_PITCH * MM_PER_IN
HELIX_ANGLE_DEG = 12.0  # recentered crossed-axis accommodation
BACKLASH_MM = 0.15
PAIR_SHAFT_ANGLE_DEG = 12.52  # crossed axes against the 16T spur pinion

BORE_DIA = 0.375 * MM_PER_IN  # 9.525 (3/8" cone-shaft journal)
BORE_DIA_BAND = (0.050, 0.030)  # (upper, lower) deviations
FACE_WIDTH = 8.0

# No roughness callouts: the gear is keyed to the cone shaft (it drives it),
# so nothing runs on the bore; the title block's Ra 3.2 covers every face
# (cad/docs/drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

# Derived tooth geometry -- kept as the analytic record the build's own
# constants are checked against (test_crank_drive_gear_drawing).
TOTAL_TWIST_DEG = math.degrees(
    FACE_WIDTH * math.tan(math.radians(HELIX_ANGLE_DEG)) / (PITCH_DIA / 2.0)
)
TRANSVERSE_CIRCULAR_TOOTH_THICKNESS = math.pi * MODULE_MM / 2.0 - BACKLASH_MM
NORMAL_MODULE_MM = MODULE_MM * math.cos(math.radians(HELIX_ANGLE_DEG))
NORMAL_PRESSURE_ANGLE_RAD = math.atan(
    math.tan(math.radians(PRESSURE_ANGLE_DEG)) * math.cos(math.radians(HELIX_ANGLE_DEG))
)
NORMAL_PRESSURE_ANGLE_DEG = math.degrees(NORMAL_PRESSURE_ANGLE_RAD)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BoreProfile": {"BoreDia"},
}


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear/sprocket data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


# The tooth system a machinist sets a cutter and a dividing head from.  The
# helix hand and the thinned tooth (the pair's backlash is all on the 64T) are
# the two facts the views cannot show.
GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        ("DIAMETRAL PITCH (TRANSVERSE)", f"{DIAMETRAL_PITCH:.2f}"),
        ("PRESSURE ANGLE (TRANSVERSE)", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("HELIX ANGLE", f"{HELIX_ANGLE_DEG:.2f} DEG"),
        ("PITCH DIAMETER (REF)", f"{PITCH_DIA:.2f}"),
        ("OUTSIDE DIAMETER", f"{OUTSIDE_DIA:.2f} +0/-0.10"),
        ("WHOLE DEPTH", f"{WHOLE_DEPTH:.2f}"),
        ("FACE WIDTH", f"{FACE_WIDTH:.2f}"),
        (
            "TRANSVERSE TOOTH THICKNESS",
            f"{TRANSVERSE_CIRCULAR_TOOTH_THICKNESS:.3f} (THINNED {BACKLASH_MM:.2f})",
        ),
        ("TOOTH FORM", "14.5 DEG TRANSVERSE INVOLUTE, HELICAL"),
        ("MATES WITH", f"16T CRANK PINION, {PAIR_SHAFT_ANGLE_DEG:.2f} DEG CROSSED AXES"),
    ]
)

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = "\n".join(
    (
        "HELIX: GAP ADVANCES CCW FROM -Z TO +Z, VIEWED FROM +Z (+Z IS OUT OF THE END VIEW).",
        "DO NOT CHAMFER OR BLEND TOOTH FLANKS, TIPS OR ROOTS.",
        "FIXED TO THE CONE SHAFT AT ASSEMBLY.",
    )
)
