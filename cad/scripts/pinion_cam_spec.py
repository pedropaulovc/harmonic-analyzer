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

CAM_OD = 9.2  # collar OD
CAM_LEN = 9.0  # collar length along the rod
ECC = 1.0  # bore offset from the collar OD axis -> 2.0 full lift
BORE = 6.35  # rides the Ø6.35 lift rod
BOSS_DIA = 3.2  # set-pin dome, proud of the OD on the heavy (thick) side
BOSS_PROUD = 0.5  # boss height proud of the OD
BOSS_Z = 1.7  # boss axis station from the front face

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CollarProfile": {"CollarOd", "CollarCy"},
    "Bore": {"BoreDia"},
    "Collar": {"Depth"},
    "BossProfile": {"BossDia"},
}

DRAWING_NOTES = "\n".join(
    (
        "ECCENTRIC COLLAR: THE <MOD-DIAM>6.35 BORE AND THE <MOD-DIAM>9.2 OD ARE NOT",
        "CONCENTRIC -- THE BORE IS OFFSET 1.0 FROM THE OD AXIS (2.0 FULL LIFT).",
        "REAM THE BORE THRU; RUNNING FIT ON THE LIFT ROD.",
        "SET-PIN BOSS ON THE THICK SIDE: <MOD-DIAM>3.2, PROUD 0.5 OF THE OD;",
        "DRILL AND PIN TO THE ROD AT ASSEMBLY.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
