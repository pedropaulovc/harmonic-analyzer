r"""Pure-data dimensional contract shared by the alignment pinion and its drawing.

The long 32T brass drum pinion (ch.25) that engages the whole cylinder-gear
train to zero the machine to sines or cosines. See the batch gear-drawing
pattern in ``cylinder_gear_spec``.
"""

from __future__ import annotations

import math

import _config

from _fit_limits import band_text
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pinion_arbor_spec import SHAFT_DIA as ARBOR_DIA
from pinion_arbor_spec import SHAFT_DIA_BAND as ARBOR_BOND_ZONE_BAND


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
# Slip fit bonded with Loctite 638, not a press: a press over the full 143.2
# bore is a seizing risk for a novice (U27, U6 precedent).  The band admits a
# stock 8 mm H7 reamer (8.000-8.015).  The drum sits on MHA-102's bond zone,
# not its journal lands (U39: Ø8 -0.01/-0.10), so the diametral clearance
# runs from 0.010 (the drum slides on by hand) up to the drum's upper
# deviation minus the arbor's lower one (0.200), inside the 0.25 mm bond gap
# the 638 technical data sheet allows.
ARBOR_BORE_BAND = (0.100, 0.000)  # (upper, lower) deviations
RETAINING_COMPOUND = "LOCTITE 638"
RETAINING_COMPOUND_MAX_GAP_MM = 0.25
FACE_WIDTH = 143.2  # general .X; located from the back end (drawing note)
# The tooth-tip OD prints at the .XX general grade (U27).  At the worst of
# +/-0.51, the drum tip keeps >= 0.21 mm to the 120T gap floor and the mesh
# keeps a contact ratio >= 1.13 (test_alignment_pinion_drawing).

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
        f"MHA-102 BOND ZONE: DIA {ARBOR_DIA:.2f} "
        f"{band_text(ARBOR_BOND_ZONE_BAND)} (REF).",
        "DRUM SHALL SLIDE ON MHA-102 BY HAND.",
        f"ON ASSEMBLY: BOND TO MHA-102 WITH {RETAINING_COMPOUND} AT THE "
        "DRUM STATION ON MHA-102.",
        "TOOTH FLANKS, TIPS, AND ROOTS: DO NOT CHAMFER OR BLEND.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
