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
# Cam-lobe direction vs the alignment-notch centreline (the channel's phase
# datum); error_budget.yaml cam_phase. Carried on the native NotchPhase
# angular dimension (build_cylinder_gear), lobe axis to notch radial.
CAM_PHASE_TOLERANCE_DEG = 0.25
NOTCH_WIDTH = 0.4  # alignment saw-kerf
NOTCH_WIDTH_BAND = (0.10, 0.0)  # (upper, lower) deviations
NOTCH_DEPTH = 3.0
NOTCH_DEPTH_TOLERANCE_MM = 0.2
TIP_RADIUS = OUTSIDE_DIA / 2.0
NOTCH_FLOOR_RADIUS = TIP_RADIUS - NOTCH_DEPTH
NOTCH_MEAN_RADIUS = (NOTCH_FLOOR_RADIUS + TIP_RADIUS) / 2.0
# +Y is a tooth crest (the cam lobe direction).  The phase kerf is the first
# root counter-clockwise from the cam lobe, half a circular pitch away, and is
# cut as a vertical slot whose centreline crosses the mean notch radius at
# NOTCH_PHASE_DEG from the lobe axis.
NOTCH_PHASE_DEG = 180.0 / TEETH
NOTCH_CENTER_X = -NOTCH_MEAN_RADIUS * math.sin(math.radians(NOTCH_PHASE_DEG))

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
    "NotchProfile": {"NotchDepth", "NotchWidth", "NotchPhase"},
}

# Decimal places ARE the tolerance statement (drawing-simplicity policy rule
# 2), so the MODEL owns them: build_cylinder_gear applies this map to the
# .SLDPRT and draw_cylinder_gear only reads it back.  Three places where a
# three-place band rides the dimension (the matched running bore's reference
# nominal, the cam eccentricity); two where the band is a two-place one (cam
# OD, face width, kerf width); one on the reference cam thickness and the
# kerf depth; the notch phase is an angle read to the tenth of a degree.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GearBlank": {"FaceWidth": 2},
    "BoreProfile": {"BoreDia": 3},
    "CamProfile": {"CamDia": 2, "CamCy": 3},
    "CamBoss": {"CamThickness": 1},
    "NotchProfile": {"NotchDepth": 1, "NotchWidth": 2, "NotchPhase": 1},
}

_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
if any(
    name not in DRAWING_DIMENSIONS.get(feature, frozenset())
    for feature, name in _PRECISION_NAMES
):
    raise AssertionError("DRAWING_PRECISION names a dimension the part never marks")
if any(
    name not in {name for names in DRAWING_PRECISION.values() for name in names}
    for names in DRAWING_DIMENSIONS.values()
    for name in names
):
    raise AssertionError("a marked dimension prints without part-authored places")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")

# The one sheet-derived dimension: the parenthesised end-to-end axial stack
# (face width plus cam thickness), a read-only sum with no model dimension to
# import.  Its places are still specification, so the sheet reads them here.
DRAWING_REFERENCE_PRECISION: dict[str, int] = {"overall axial thickness": 1}


def matched_bore_limits(finished_shaft_dia_mm: float) -> tuple[float, float]:
    """Return finished bore MIN/MAX for the measured mating MHA-028 arbor."""
    minimum, maximum = BORE_DIAMETRAL_CLEARANCE_MM
    return finished_shaft_dia_mm + minimum, finished_shaft_dia_mm + maximum
