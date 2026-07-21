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
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CollarProfile": {"CollarOd", "CollarCy"},
    "BoreProfile": {"BoreDia"},
    "Collar": {"Depth"},
    "BossProfile": {"BossDia", "BossCz"},
}

DRAWING_NOTES = "\n".join(
    (
        "BORE AND OD ARE NOT CONCENTRIC: BORE AXIS OFFSET 1.00+/-0.05 FROM",
        "  OD AXIS IN THE BOSS PLANE; BOSS IS ON THE THICK SIDE. FULL CAM LIFT 2.00 REF.",
        "BORE FINAL LIMITS 6.360-6.375 THRU, Ra 1.6; SLIDING FIT ON MATING",
        "  ROD 6.330-6.350.",
        "INTEGRAL BOSS <MOD-DIAM>3.20+/-0.05, 0.50+/-0.05 PROJECTION BEYOND OD.",
        "DRILL/TAP M3 X 0.5-6H THROUGH BOSS TO BORE, AXIS RADIAL IN BOSS PLANE;",
        "  3.00 MIN FULL THREAD. FIT ISO 4026 M3 X 6 FLAT-POINT SET SCREW,",
        "  A2-70, LOW-STRENGTH THREADLOCKER; TIGHTEN TO 1.0 N-m AFTER PHASING.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
