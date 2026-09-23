r"""Pure-data dimensional contract shared by the alignment pinion and its drawing.

The long 32T brass drum pinion (ch.25) that engages the whole cylinder-gear
train to zero the machine to sines or cosines. See the batch gear-drawing
pattern in ``cylinder_gear_spec``.
"""

from __future__ import annotations

import math

import _config

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

TEETH = int(_config.machine("alignment_pinion", "teeth"))
DIAMETRAL_PITCH = float(_config.machine("gear_train", "diametral_pitch"))
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN
_PRESSURE_ANGLE_RAD = math.radians(PRESSURE_ANGLE_DEG)
_BASE_RADIUS = (
    TEETH * MODULE_MM * math.cos(_PRESSURE_ANGLE_RAD) / 2.0
)
_BASE_TOOTH_HALF_ANGLE = (
    math.pi / (2.0 * TEETH)
    + math.tan(_PRESSURE_ANGLE_RAD)
    - _PRESSURE_ANGLE_RAD
)
_HALF_GAP_ANGLE = math.pi / TEETH - _BASE_TOOTH_HALF_ANGLE
MIN_CHORD_FLOOR_DIA = 2.0 * _BASE_RADIUS * math.cos(_HALF_GAP_ANGLE)
AS_CUT_RADIAL_TOOTH_DEPTH = OUTSIDE_DIA / 2.0 - MIN_CHORD_FLOOR_DIA / 2.0
# Tooth thickness is inspected as a base-tangent span.  Three teeth put the
# caliper contacts at r8.14, on the flanks at the pitch circle (r8.16).  The
# model is cut to the standard thickness, which is the upper limit.  The drum
# swings into the cylinder bank until its flanks seat, so centre distance
# takes up any thinning; the band only has to keep the flanks present.
BASE_TANGENT_SPAN_TEETH = 3
BASE_TANGENT_SPAN = (
    MODULE_MM
    * math.cos(_PRESSURE_ANGLE_RAD)
    * (
        math.pi * (BASE_TANGENT_SPAN_TEETH - 0.5)
        + TEETH * (math.tan(_PRESSURE_ANGLE_RAD) - _PRESSURE_ANGLE_RAD)
    )
)
BASE_TANGENT_SPAN_BAND = (0.0, -0.100)  # (upper, lower) deviations
BASE_CHORD_ROOT_FORM = "INVOLUTE FLANKS; GAP FLOOR CHORD AT BASE CIRCLE"

BORE_DIA = 8.0  # Ø8 arbor through-bore (build_pinion_arbor.py)
ARBOR_BORE_BAND = (-0.020, -0.040)  # (upper, lower) deviations; matched press
# Finish the bore to the measured MHA-102 shaft. This is a matched-pair
# acceptance range, not an interchangeable limit stack across random parts.
ARBOR_DIAMETRAL_INTERFERENCE_MM = (0.010, 0.030)
FACE_WIDTH = 143.2  # ±0.5 keeps all 20 gear stations covered at either limit
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
        (
            "MIN CHORD-FLOOR DIAMETER (mm, REF)",
            f"{MIN_CHORD_FLOOR_DIA:.3f}",
        ),
        (
            "AS-CUT RADIAL TOOTH DEPTH (mm, REF)",
            f"{AS_CUT_RADIAL_TOOTH_DEPTH:.3f}",
        ),
        ("TOOTH FORM", BASE_CHORD_ROOT_FORM),
        (
            f"BASE-TANGENT SPAN, OVER {BASE_TANGENT_SPAN_TEETH} TEETH (mm)",
            f"{BASE_TANGENT_SPAN:.3f} +{BASE_TANGENT_SPAN_BAND[0]:.3f}"
            f"/{BASE_TANGENT_SPAN_BAND[1]:.3f}",
        ),
    ]
)

DRAWING_NOTES = "\n".join(
    (
        "MATES WITH CYLINDER-GEAR BANK MHA-027.",
        "BORE LIMITS AND MATCHED FIT BOTH APPLY.",
        "MHA-102 ARBOR JOURNAL: DIA 8.00 +0.00/-0.02 (REF).",
        "MATCH TO MEASURED MHA-102 PINION ARBOR FOR "
        f"{ARBOR_DIAMETRAL_INTERFERENCE_MM[0]:.3f}-"
        f"{ARBOR_DIAMETRAL_INTERFERENCE_MM[1]:.3f} DIAMETRAL INTERFERENCE.",
        "143.2 +/-0.5 ENSURES FULL ENGAGEMENT AT ALL 20 MHA-027 GEAR STATIONS.",
        "TOOTH FLANKS, TIPS, AND ROOTS: DO NOT CHAMFER OR BLEND.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
