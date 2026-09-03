r"""Pinion-swing-bracket dimensional contract -- the single source of truth shared
by the part build (``build_pinion_bracket.py``) and its manufacturing drawing
(``draw_pinion_bracket.py``).

PURE DATA, no SolidWorks/COM imports: the nominal geometry (the "editable
knobs"), the derived spans the drawing needs for its view math, and the
marked-dimension -> kept-dimension NAME map.  Keeping this in ONE module means
a rename or a nominal change is a single edit that reaches both scripts, so the
part-side ``mark_dimensions_for_drawing`` set and the drawing-side ``keep``
maps cannot silently drift apart.

Build-graph consequence (intended): geometry lives in
``pinion_bracket_geometry`` so the drive-train assembly can consume it without
also depending on this module's drawing-only notes and annotation contract.
The part and drawing import this file, so note edits still rebuild the source
part whose custom properties carry them and then regenerate the drawing.

The offline lockstep test (``test_pinion_bracket_drawing.py``) asserts the part
marks and the drawing keeps EXACTLY ``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations

from _fit_limits import REAM_H7, REAM_SLIDE
from _surface_finish import SurfaceFinishControl
from pinion_bracket_geometry import (
    ARBOR_BORE as ARBOR_BORE,
    C2C as C2C,
    CAM_RELIEF_RADIUS as CAM_RELIEF_RADIUS,
    HALF_WIDTH as HALF_WIDTH,
    OVERALL_LENGTH as OVERALL_LENGTH,
    PIN_BORE as PIN_BORE,
    PIN_DROP as PIN_DROP,
    PIN_SEAT as PIN_SEAT,
    PIVOT_BORE as PIVOT_BORE,
    R_END as R_END,
    THICKNESS as THICKNESS,
    WIDTH as WIDTH,
)

ARBOR_BORE_CZ_TOLERANCE_MM = 0.10
PIVOT_BORE_BAND = REAM_SLIDE
ARBOR_BORE_BAND = REAM_SLIDE
PIN_SEAT_AXIS_TOLERANCE_MM = 0.05
THICKNESS_TOLERANCE_MM = 0.05
PIN_SEAT_DIA_BAND = REAM_H7
PIN_SEAT_DEPTH_BAND = (0.10, 0.00)
PIN_SEAT_CZ_TOLERANCE_MM = 0.05

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_pinion_bracket`` marks exactly these; ``draw_pinion_bracket``
# keeps exactly their union across its per-view ``keep`` maps. The offline test
# enforces ``union(marks) == union(keeps)``. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    # Both end radii print (the top cap is concentric with the arbor bore, the
    # bottom cap with the pivot bore); the (REF) overall is a drawing edge
    # dimension between the two arc extremes.
    "StrapProfile": {
        "ArborBoreCz",
        "PivotBoreDia",
        "ArborBoreDia",
        "BottomCapRadius",
        "TopCapRadius",
    },
    "Strap": {"Depth"},
    # The two R6.90 cam scallops are fully located on DETAIL B: one diameter
    # (2X) and each circle's centre from the pivot bore, in place of the old
    # "PER MODEL" note (machinist review 2026-09-02).
    "CamReliefParkProfile": {
        "CamReliefParkDia",
        "CamReliefParkX",
        "CamReliefParkY",
    },
    "CamReliefEngagedProfile": {"CamReliefEngagedX", "CamReliefEngagedY"},
    # PinSeatCz locates the blind pin seat THROUGH the 5 mm thickness (mid-
    # thickness), so the seat is fully located, not just drawn centred.
    "PinSeatProfile": {"PinSeatDia", "PinSeatCy", "PinSeatCz"},
    "PinSeat": {"PinSeatDepth"},
}

# No roughness callouts (machinist review 2026-09-02): the arbor bore is a
# reamed running fit whose size band is on the dimension; the title block's
# Ra 3.2 covers it and every other face (drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

# Notes: process facts only (policy rule 6) -- the paired reaming setup and
# the one part this strap is assembled with.  The scallops, the end arcs and
# every bore are dimensions on the views.
DRAWING_NOTES = "\n".join(
    (
        "REAM THE BORES WITH THE TWO STRAPS CLAMPED FACE-TO-FACE.",
        "MATES WITH MHA-116 CAM PIN, PRESSED INTO THE STUD SEAT.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
