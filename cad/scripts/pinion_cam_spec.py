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

from _fit_limits import REAM_SLIDE
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from _gtol_spec import CylinderFace
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

# The bore is a RUNNING fit on the Ø6.35 lift rod (MHA-060), which is exactly
# what the shared REAM_SLIDE class is for; BORE is the model's as-cut nominal
# rather than the rod's, so the band is that fit class re-expressed about it
# and can never drift from the class (cad/docs/tolerance-policy.md).
LIFT_ROD_DIA = 6.35
LIFT_ROD_NUMBER = "MHA-060"
BORE_BAND = (
    round(LIFT_ROD_DIA + REAM_SLIDE[0] - BORE, 6),
    round(LIFT_ROD_DIA + REAM_SLIDE[1] - BORE, 6),
)
# The cam OD is the working surface the follower rides, and the bore-to-OD
# offset IS the lift: both are on the drive train's critical list.  Nothing
# else on this collar mates with anything, so nothing else carries a band --
# the title block's general grade governs it (tolerance-policy rule 11).
COLLAR_OD_TOLERANCE_MM = 0.05
COLLAR_AXIS_TOLERANCE_MM = 0.05

SURFACE_FINISHES = (SurfaceFinishControl("bore", MACHINED_UM, CylinderFace(BORE)),)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CollarProfile": {"CollarOd", "CollarCy"},
    "BoreProfile": {"BoreDia"},
    "Collar": {"Depth"},
    "BossProfile": {"BossDia", "BossCz"},
    "SetPinBossProjection": {"BossProjection"},
}

# drawing-simplicity-policy rule 6: four short lines of facts the views cannot
# show.  The eccentricity itself is DIMENSIONED on the sheet, so the note only
# says what a single dimension cannot -- that it is the same, and in the same
# direction, at both ends.
DRAWING_NOTES = "\n".join(
    (
        "BORE AND OD ARE NOT CONCENTRIC; THE ECCENTRICITY IS THE SAME",
        "  AND IN THE SAME DIRECTION AT BOTH ENDS.",
        "DRILL/TAP M2.5 X 0.45-6H THROUGH THE BOSS INTO THE BORE.",
        "SUPPLY ISO 4026 M2.5 X 5 A2-70 FLAT-POINT SET SCREW LOOSE.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
