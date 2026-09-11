r"""Pure-data dimensional contract for the cylinder gear and its drawing.

The involute tooth system lives in ``GEAR_DATA`` because an involute outline
has no authoritative circular edge to dimension.  Ordinary blank, cam and
notch geometry stays in named model dimensions or checked drawing dimensions,
so the sheet has one source for each manufacturing requirement.
"""

from __future__ import annotations

import math

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

# --- gear tooth system (build_cylinder_gear.py / gear_train.yaml) ------------
TEETH = 120
DIAMETRAL_PITCH = (
    49.82  # train DP (= 122*25.4/62.2), cad/config/machine/gear_train.yaml
)
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH  # 0.510
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN  # 61.18
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN  # 62.20
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN  # 1.10

# --- machinable blank (build_cylinder_gear.py) ------------------------------
BORE_DIA = 0.375 * MM_PER_IN  # 9.525 reference nominal; finish to the actual arbor
BORE_DIAMETRAL_CLEARANCE_MM = (0.030, 0.070)  # (minimum, maximum), matched fit
BORE_FIT_CALLOUT = (
    "FINISH BORE THRU; ALL 20 GEARS\n"
    "MATCH TO FINISHED\n"
    "CYLINDER-GEAR-SHAFT MHA-028\n"
    f"{BORE_DIAMETRAL_CLEARANCE_MM[0]:.3f}-{BORE_DIAMETRAL_CLEARANCE_MM[1]:.3f} "
    "DIAMETRAL CLEARANCE"
)
FACE_WIDTH = 3.0
FACE_WIDTH_TOLERANCE_MM = 0.05
CAM_DIA = 30.6  # integral eccentric cam disc
CAM_DIA_BAND = (0.0, -0.05)  # (upper, lower) deviations
CAM_THICKNESS = 3.5
CAM_THICKNESS_TOLERANCE_MM = 0.05
OVERALL_THICKNESS = FACE_WIDTH + CAM_THICKNESS
ECCENTRICITY = 8.64  # cam axis offset from the bore axis
ECCENTRICITY_TOLERANCE_MM = 0.025
SET_ECCENTRICITY_RANGE_MM = 0.025
NOTCH_WIDTH = 0.4  # alignment saw-kerf
NOTCH_WIDTH_BAND = (0.10, 0.0)  # (upper, lower) deviations
NOTCH_DEPTH = 3.0
NOTCH_DEPTH_TOLERANCE_MM = 0.2
TIP_RADIUS = OUTSIDE_DIA / 2.0
NOTCH_FLOOR_RADIUS = TIP_RADIUS - NOTCH_DEPTH
# +Y is a tooth crest.  The phase kerf is the first root counter-clockwise
# from the cam lobe, half a circular pitch away, and is cut as a vertical slot.
NOTCH_CENTER_X = (
    (NOTCH_FLOOR_RADIUS + TIP_RADIUS)
    / 2.0
    * math.cos(math.pi / 2.0 + math.pi / TEETH)
)

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "cylinder_gear_bore",
        MACHINED_UM,
        CylinderFace(BORE_DIA),
        production_method="BORE",
    ),
    SurfaceFinishControl("cam_follower", MACHINED_UM, CylinderFace(CAM_DIA)),
)

# Marked model dimensions are the authoritative blank, bore, cam and kerf
# requirements.  The sheet adds only a checked reference overall thickness.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GearBlank": {"FaceWidth"},
    "BoreProfile": {"BoreDia"},
    "CamProfile": {"CamDia", "CamCy"},
    "CamBoss": {"CamThickness"},
    "NotchProfile": {"NotchDepth", "NotchWidth"},
}

def matched_bore_limits(finished_shaft_dia_mm: float) -> tuple[float, float]:
    """Return finished bore MIN/MAX for the measured mating MHA-028 arbor."""
    minimum, maximum = BORE_DIAMETRAL_CLEARANCE_MM
    return finished_shaft_dia_mm + minimum, finished_shaft_dia_mm + maximum



def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear/sprocket data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        ("DIAMETRAL PITCH", f"{DIAMETRAL_PITCH:.2f} (NONSTANDARD)"),
        ("MODULE (mm, REF)", f"{MODULE_MM:.3f}"),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (mm, REF)", f"{PITCH_DIA:.2f}"),
        ("OUTSIDE DIAMETER (mm)", f"{OUTSIDE_DIA:.2f} +0/-0.10"),
        ("WHOLE DEPTH (mm)", f"{WHOLE_DEPTH:.2f} +0.05/0"),
        ("TOOTH FORM", "INVOLUTE, FULL DEPTH"),
    ]
)

DRAWING_NOTES = "\n".join(
    (
        "ALIGNMENT NOTCH IS FIRST TOOTH ROOT CCW FROM CAM LOBE AS VIEWED FROM CAM FACE.",
        "CAM ECCENTRICITY RANGE ACROSS ALL 20 MHA-027 GEARS IN ONE ANALYZER: "
        f"{SET_ECCENTRICITY_RANGE_MM:.3f} MAX.",
    )
)
