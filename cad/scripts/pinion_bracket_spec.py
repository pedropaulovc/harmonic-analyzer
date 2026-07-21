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

from pinion_bracket_geometry import (
    ARBOR_BORE as ARBOR_BORE,
    C2C as C2C,
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

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_pinion_bracket`` marks exactly these; ``draw_pinion_bracket``
# keeps exactly their union across its per-view ``keep`` maps. The offline test
# enforces ``union(marks) == union(keeps)``. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StrapProfile": {
        "ArborBoreCz",
        "PivotBoreDia",
        "ArborBoreDia",
        "BottomCapRadius",
    },
    "Strap": {"Depth"},
    # PinSeatCz locates the blind pin seat THROUGH the 5 mm thickness (mid-
    # thickness), so the seat is fully located, not just drawn centred.
    "PinSeatProfile": {"PinSeatDia", "PinSeatCy", "PinSeatCz"},
}

# True free-text instructions only. Geometry, datum structure, form/orientation
# live in native dimensions / datum tags / FCFs / surface symbols. The part
# build stamps these strings into the SLDPRT; the drawing displays only
# $PRPSHEET links, so the print cannot silently diverge from its source model.
DRAWING_NOTES = "\n".join(
    (
        "ONE STRAP: 5.00 THK. ENDS R9.00, CONCENTRIC WITH THEIR BORE AXES;",
        "  STRAIGHT SIDES TANGENT TO THE ENDS (18.00 WIDTH). BOTH BORES ON THE CENTRELINE.",
        "PIVOT BORE: <MOD-DIAM>6.360-6.375 THRU. ARBOR BORE: <MOD-DIAM>8.010-8.025 THRU.",
        "PIN SEAT: DRILL FROM THE LEFT ROUNDED EDGE IN FRONT VIEW; AXIS 2.00 BELOW",
        "  THE PIVOT AXIS AND MIDWAY THROUGH THE 5.00 THICKNESS; <MOD-DIAM>4 H7",
        "  (4.000-4.012) X 4.00 DEEP, FLAT BOTTOM; PRESS FIT WITH <MOD-DIAM>4 p6 PIN.",
        "2 STRAPS REQUIRED; MACHINE AS A MATCHED PAIR FOR COMMON BORE CENTRES.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
