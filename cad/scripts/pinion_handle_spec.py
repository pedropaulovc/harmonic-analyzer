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
from _surface_finish import SurfaceFinishControl
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

# Press/ream bands peculiar to this part (per _fit_limits.py's contract, a
# part-specific band lives beside the nominal it tolerances, not in the shared
# fit-class table).  Symmetric about each nominal; rendered through
# :func:`fit_limits` so a nominal retune can never leave the released MAX/MIN
# text stale (codex #359).  The turned lengths (grip, bore depth, rod span)
# carry NO band: the title block's .XX tolerance governs them -- the arbor's
# flat tip seats on the bore floor, so the bore depth only shifts the grip
# station along the arbor (machinist review 2026-09-02).
ROD_PRESS_BAND = (0.0025, -0.0025)  # turned cross-rod OD tolerance
ROD_HOLE_REAM_BAND = (0.005, -0.005)  # body cross-hole ream tolerance
TUBE_ID_BAND = REAM_SLIDE

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GripProfile": {"GripDia"},
    "Grip": {"GripLen"},
    # The crown is a size on the view: its sphere radius and (REF) height.
    "CapProfile": {"CapR", "CapSagDim"},
    "TubeProfile": {"TubeOd", "TubeId"},
    "Tube": {"TubeLen"},
    "RodProfile": {"RodDia"},
    "Rod": {"RodSpan"},
    "RodHoleProfile": {"RodHoleDia"},
}

# No roughness callouts: the hub is locked to its arbor stub, so nothing runs
# on the bore; the title block's Ra 3.2 covers every face
# (cad/docs/drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

# Notes: process facts only, never a size (policy rule 6).  The crown, the
# cross-hole station and the lower arm are all dimensions on the views.
DRAWING_NOTES = "\n".join(
    (
        "PRESS THE CROSS ROD INTO THE REAMED BODY HOLE AFTER TURNING.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
