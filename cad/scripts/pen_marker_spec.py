r"""Pure-data dimensional contract shared by the pen marker and drawing."""

from __future__ import annotations

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

BARREL_DIA = 8.0  # (low)
BARREL_TOP_Y = 110.0  # ch30 p002/p004 + v4_t00612: ~75 of barrel shows in front
# of the 36 block plus the 6 nib reach -- a full-length marker, not a 60 stub
CONE_H = 5.0  # tip nose (low) — the ch24 macro shows a blunt bullet nose
# (~0.6x dia), not the needle cone the old 12 gave; keep the same tip origin

SURFACE_FINISHES = (
    SurfaceFinishControl("barrel", MACHINED_UM, CylinderFace(BARREL_DIA)),
)

# The profile chain also emits ConeRadius / BarrelLen / BarrelRadius, but the
# print carries the machinist set: the tip-cone height plus the drawing-native
# barrel diameter and overall length (the barrel length is the implied link of
# the chain — dimensioning it too would double-dimension the part).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "MarkerProfile": {"ConeH"},
}

DRAWING_NOTES = "\n".join(
    (
        "TURN BARREL AND TIP CONE IN ONE SETUP; TIP POINT 0.2 MAX FLAT.",
        "TIP CONE RUNS TO FULL BARREL DIAMETER (INCLUDED ANGLE 77.3 REF).",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "marker tip runout": "0.10",
}
