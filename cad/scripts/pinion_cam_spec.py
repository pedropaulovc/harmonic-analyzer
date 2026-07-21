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
        "ECCENTRIC COLLAR: THE <MOD-DIAM>6.35 BORE AND THE <MOD-DIAM>9.2 OD ARE NOT",
        "CONCENTRIC -- THE BORE IS OFFSET 1.0 FROM THE OD AXIS (2.0 FULL LIFT).",
        "REAM THE BORE 6.360-6.375 THRU; SLIDING FIT ON THE LIFT ROD; Ra 1.6.",
        "SET-PIN BOSS ON THE THICK SIDE: <MOD-DIAM>3.2, PROUD 0.5 OF THE OD;",
        "RELEASE HOLD - DO NOT MANUFACTURE: DEFINE THE SET-PIN HOLE, PIN SPECIFICATION,",
        "  ENGAGEMENT IN THE LIFT ROD, AND RETENTION METHOD.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
