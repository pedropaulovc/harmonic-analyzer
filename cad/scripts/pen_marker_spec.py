r"""Pure-data dimensional contract shared by the pen marker and drawing."""

from __future__ import annotations

from _surface_finish import SurfaceFinishControl

BARREL_DIA = 8.0  # (low)
BARREL_TOP_Y = 110.0  # ch30 p002/p004 + v4_t00612: ~75 of barrel shows in front
# of the 36 block plus the 6 nib reach -- a full-length marker, not a 60 stub
CONE_H = 5.0  # tip nose (low) — the ch24 macro shows a blunt bullet nose
# (~0.6x dia), not the needle cone the old 12 gave; keep the same tip origin

# No roughness callouts: the marker is clamped in the v-block groove by the
# stirrup's set screw, so nothing runs on the barrel; the title block's Ra 3.2
# covers it (cad/docs/drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

# The profile chain also emits ConeRadius / BarrelLen / BarrelRadius, but the
# print carries the machinist set: the tip-cone height plus the drawing-native
# barrel diameter and overall length (the barrel length is the implied link of
# the chain — dimensioning it too would double-dimension the part).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "MarkerProfile": {"ConeH"},
}

# The tip allowance rides a leader on the apex (machinist review 2026-09-02:
# a detached "TIP FLAT 0.2 MAX" left the 110.00 / 5.00 ambiguous -- they run
# to the drawn theoretical sharp, and the flat is permitted, not dimensioned).
TIP_NOTE = "\n".join(
    (
        "DIMS TO THEORETICAL SHARP",
        "TIP FLAT <MOD-DIAM>0.20 MAX OK",
    )
)

DRAWING_NOTES = "\n".join(
    (
        "TURN BARREL AND TIP IN ONE SETTING.",
        "TIP CONE 77.3 DEG INCLUDED (REF).",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
