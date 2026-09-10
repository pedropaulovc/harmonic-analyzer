r"""Pure-data dimensional contract shared by the pinion turning handle and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A turned tee: a fat grip cylinder with a
domed cap, a cross rod through the grip, and a blind tubular hub that seats over
the pinion arbor stub.  The nominals drive the part's named equation globals AND
the drawing's coordinate math; the marked-dimension map keeps the part marks and
drawing keeps in lockstep (``test_pinion_handle_drawing.py``).
"""

from __future__ import annotations

from _fit_limits import REAM_SLIDE
from pinion_handle_geometry import (
    CAP_RADIUS as CAP_RADIUS,
    CAP_SAG as CAP_SAG,
    GRIP_DIA as GRIP_DIA,
    GRIP_LEN as GRIP_LEN,
    ROD_DIA as ROD_DIA,
    ROD_DOWN as ROD_DOWN,
    ROD_HOLE_DIA as ROD_HOLE_DIA,
    ROD_SPAN as ROD_SPAN,
    ROD_UP as ROD_UP,
    TUBE_ID as TUBE_ID,
    TUBE_LEN as TUBE_LEN,
    TUBE_OD as TUBE_OD,
    WALL_T as WALL_T,
)

# Reamed holes retain native size tolerances. Match the cross rod to its body
# for a light press fit; routine lengths use the title-block tolerances.
ROD_HOLE_REAM_BAND = (0.005, -0.005)  # body cross-hole ream tolerance
TUBE_ID_BAND = REAM_SLIDE
TUBE_LENGTH_BAND = (0.10, 0.00)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GripProfile": {"GripDia"},
    "CapProfile": {"CapR"},
    "TubeProfile": {"TubeOd", "TubeId"},
    "Tube": {"TubeLen"},
    "RodProfile": {"RodDia"},
    "Rod": {"RodSpan"},
    "RodHoleProfile": {"RodHoleDia"},
}

# The handle and arbor rotate together. This static socket is not a running
# bearing, so it has no local roughness requirement under the simplicity policy.
SURFACE_FINISHES = ()

DRAWING_NOTES = "MATCH CROSS ROD TO BODY FOR LIGHT PRESS FIT."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
