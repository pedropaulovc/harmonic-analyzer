r"""Pure-data dimensional contract for the cylinder gear and its drawing.

The tooth system and ordinary blank, cam and notch geometry are shared by
part and assembly recipes. Drawing prose lives in ``cylinder_gear_notes`` so
wording changes do not invalidate the channel's geometry recipe.
"""

from __future__ import annotations

import math

import _config
import cylinder_gear_shaft_spec as arbor

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

# --- gear tooth system (build_cylinder_gear.py / gear_train.yaml) ------------
TEETH = 120
DIAMETRAL_PITCH = _config.machine("gear_train", "diametral_pitch")
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH  # 0.510
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN  # 61.18
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN  # 62.20
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN  # 1.10

# --- machinable blank (build_cylinder_gear.py) ------------------------------
BORE_DIAMETRAL_CLEARANCE_MM = (0.030, 0.070)  # (minimum, maximum), matched fit
# Representative finished geometry at the midpoint of the matched running fit.
# Manufacturing still matches every bore to the actual finished arbor.
BORE_DIA = arbor.SHAFT_DIA + sum(BORE_DIAMETRAL_CLEARANCE_MM) / 2.0
FACE_WIDTH = 3.0
# Face width controls mesh engagement across the mating cone-gear family.
FACE_WIDTH_TOLERANCE_MM = 0.05
CAM_DIA = 30.6  # integral eccentric cam disc
CAM_DIA_BAND = (0.0, -0.05)  # (upper, lower) deviations
CAM_THICKNESS = 3.5  # reference nominal; axial fit governs the finished thickness
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
    (NOTCH_FLOOR_RADIUS + TIP_RADIUS) / 2.0 * math.cos(math.pi / 2.0 + math.pi / TEETH)
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

# Marked model dimensions locate the blank, bore, cam and kerf. Bore diameter
# and cam thickness are reference nominals with finished-fit callouts.
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
