r"""Pure-data dimensional contract shared by the pinion lift cam and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  An eccentric steel collar pinned to the
lift rod: the bore is offset ECC from the collar OD axis, so the two are NOT
concentric -- the drawing MUST dimension that offset (the cam-note precedent).
The nominals drive the part's named equation globals AND the drawing's
coordinate math; the marked-dimension map keeps the part marks and drawing keeps
in lockstep (``test_pinion_cam_drawing.py``).
"""

from __future__ import annotations

from _surface_finish import MACHINED_UM, SurfaceFinishControl
from _gtol_spec import CylinderFace
from pinion_lift_rod_spec import ROD_DIA as LIFT_ROD_DIA
from pinion_lift_rod_spec import ROD_DIA_BAND as LIFT_ROD_DIA_BAND
from pinion_cam_geometry import (
    BORE as BORE,
    CAM_LEN as CAM_LEN,
    CAM_OD as CAM_OD,
    ECC as ECC,
    SET_SCREW_Z as SET_SCREW_Z,
    TAP_DRILL_DIA as TAP_DRILL_DIA,
)

# U27 (Main, 2026-09-23): the cam is set-screwed to the lift rod (MHA-060), so
# the bore only has to slip over it.  A stock 6.4 mm reamer holds +/-0.03, and
# against the rod's h band that leaves 0.02-0.10 diametral clearance -- enough
# to slide on at assembly, small enough that the set screw's shift is noise
# under the feeler-set rig location.
LIFT_ROD_NUMBER = "MHA-060"
BORE_BAND = (0.03, -0.03)  # (upper, lower) deviations about BORE
SLIP_CLEARANCE_MIN = round(
    BORE + BORE_BAND[1] - (LIFT_ROD_DIA + LIFT_ROD_DIA_BAND[0]), 6
)
SLIP_CLEARANCE_MAX = round(
    BORE + BORE_BAND[0] - (LIFT_ROD_DIA + LIFT_ROD_DIA_BAND[1]), 6
)
if SLIP_CLEARANCE_MIN < 0.02 or SLIP_CLEARANCE_MAX > 0.10:
    raise AssertionError(
        f"cam slip clearance {SLIP_CLEARANCE_MIN}-{SLIP_CLEARANCE_MAX} is outside 0.02-0.10"
    )
# The cam OD is the working surface the follower rides, and the bore-to-OD
# offset IS the lift: both are on the drive train's critical list.  Nothing
# else on this collar mates with anything, so nothing else carries a band.
# Routine controlling dimensions use the title block's general grade.
COLLAR_OD_TOLERANCE_MM = 0.05
COLLAR_AXIS_TOLERANCE_MM = 0.05

# Rule 5: the roughness goes on the surface that runs.  The follower pin rides
# the cam OD; the set-screwed bore never moves on the rod, so it carries none.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "cam_od", MACHINED_UM, CylinderFace(CAM_OD), production_method="CAM OD"
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CollarProfile": {"CollarOd", "CollarCy"},
    "BoreProfile": {"BoreDia"},
    "Collar": {"Depth"},
    "TapDrillProfile": {"TapDrillDia", "TapCz"},
}

# The MODEL owns every printed decimal place: build_pinion_cam applies this
# map to the .SLDPRT and draw_pinion_cam only reads it back.  Two places on
# the critical trio -- the reamed running bore (its band rides the dimension),
# the cam OD and the bore-to-OD eccentricity that IS the lift -- and on the
# M2.5 tap drill, whose size is the drill's, not a band; one place everywhere
# else, so routine controlling dimensions use the title block's .X row.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "CollarProfile": {"CollarOd": 2, "CollarCy": 2},
    "BoreProfile": {"BoreDia": 2},
    "Collar": {"Depth": 1},
    "TapDrillProfile": {"TapDrillDia": 2, "TapCz": 1},
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

# The tapped-hole requirement is attached to its tap-drill dimension.  The sole
# linked note carries only the loose purchased hardware supplied with the cam:
# the 5-long screw sits ~1.1 below the OD in the 6.1-thick heavy side.
DRAWING_NOTES = "SUPPLY ISO 4026 M2.5 X 5 A2-70 FLAT-POINT SET SCREW LOOSE."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
