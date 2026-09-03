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

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pinion_cam_geometry import (
    BORE as BORE,
    BOSS_DIA as BOSS_DIA,
    BOSS_PROUD as BOSS_PROUD,
    BOSS_Z as BOSS_Z,
    CAM_LEN as CAM_LEN,
    CAM_OD as CAM_OD,
    ECC as ECC,
    TAP_DRILL_DIA as TAP_DRILL_DIA,
)

# Ream band about the 6.37 mid nominal: 6.375 MAX / 6.360 MIN (running fit
# on the Ø6.35 lift rod). Asymmetric because BORE is the model's as-cut
# nominal, not the band midpoint.
BORE_BAND = (0.005, -0.010)
COLLAR_OD_TOLERANCE_MM = 0.05
# CollarCy (the eccentricity) carries NO +/- band: it is the BASIC dimension
# feeding the OD-axis position frame (drawing-simplicity-policy.md rule 4).
COLLAR_DEPTH_TOLERANCE_MM = 0.05
BOSS_DIA_TOLERANCE_MM = 0.05
BOSS_PROJECTION_TOLERANCE_MM = 0.05

# The follower stud rides the OD (a cam_follower_contact face, rule 5); the
# set-pinned bore does not run on the lift rod, so it takes the block Ra 3.2.
SURFACE_FINISHES = (SurfaceFinishControl("od", MACHINED_UM, CylinderFace(CAM_OD)),)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CollarProfile": {"CollarOd", "CollarCy"},
    "BoreProfile": {"BoreDia"},
    "Collar": {"Depth"},
    "BossProfile": {"BossDia", "BossCz"},
    "SetPinBossProjection": {"BossProjection"},
}

# Notes: the eccentricity fact and the set-screw lines only
# (drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = "\n".join(
    (
        f"BORE AND <MOD-DIAM>{CAM_OD:.2f} OD ARE NOT CONCENTRIC: OFFSET {ECC:.2f}, IN THE BOSS PLANE.",
        "DRILL AND TAP M2.5 X 0.45 THROUGH THE BOSS INTO THE BORE.",
        "M2.5 X 5 FLAT-POINT SET SCREW SUPPLIED LOOSE.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1\n(SET-SCREW BOSS HIDDEN AT REAR)"


# The one allowlisted frame (policy rule 3, "cams"): the OD axis to the bore
# axis in a diametral zone equivalent to the retired +/-0.05 coordinate, in
# the form a 4-jaw offset is actually checked (indicator on the OD, bore on
# the spindle axis).
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "cam OD axis position": "0.10",
}
