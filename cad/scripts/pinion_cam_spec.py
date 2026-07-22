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

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CollarProfile": {"CollarOd", "CollarCy"},
    "BoreProfile": {"BoreDia"},
    "Collar": {"Depth"},
    "BossProfile": {"BossDia", "BossCz"},
}

DRAWING_NOTES = "\n".join(
    (
        f"BORE AND OD ARE NOT CONCENTRIC; {ECC:.2f} ECCENTRICITY APPLIES AT BOTH ENDS.",
        "AXIS C IS PARALLEL TO AXIS B WITHIN 0.03; THE OFFSET DIRECTION IS",
        "  COMMON TO BOTH ENDS (B AND C ARE COPLANAR WITH THE BOSS AXIS PLANE).",
        "DATUM A IS THE FRONT END FACE; B IS THE FINAL REAMED BORE AXIS;",
        f"  C IS THE <MOD-DIAM>{CAM_OD:.2f} OD AXIS; D IS THE BOSS OD AXIS.",
        "THE SET-SCREW BOSS IS INTEGRAL WITH THE CAM BODY.",
        "BASIC BOSS/TAP AXES EACH INTERSECT B PERPENDICULAR TO IT AND LIE IN",
        "  THE PLANE CONTAINING B AND C.",
        "POSITION BOSS OD AXIS TO A|B|C; POSITION TAP PITCH AXIS TO DATUM D.",
        "DRILL/TAP M2.5 X 0.45-6H THROUGH BOSS TO BORE; 2.00 MIN FULL THREAD.",
        "  SUPPLY ISO 4026 M2.5 X 5 A2-70 FLAT-POINT SET SCREW LOOSE.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1\n(SET-SCREW BOSS HIDDEN AT REAR)"
