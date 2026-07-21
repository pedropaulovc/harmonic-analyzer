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
        "ONE STRAP SHOWN. EACH R9.00 OUTER ARC SHALL RUN WITHIN 0.05 TIR",
        "  TO A CLOSE-FIT GAGE PIN IN ITS CORRESPONDING BORE; SIDES TANGENT TO ARCS.",
        "PIN-SEAT BOTTOM PLANE 5.00+/-0.05 LEFT OF PIVOT-BORE AXIS; 3.00 MIN",
        "  FULL-DIAMETER ENGAGEMENT. FLAT-BOTTOM OR RELIEVE DRILL POINT.",
        "MAKE TWO CLAMPED FACE-TO-FACE AND REAM BOTH SETS OF BORES IN ONE SETUP.",
        "  A SINGLE 25 MM LONG GO PIN SHALL PASS THROUGH BOTH STRAPS AT EACH BORE",
        "  WITHOUT FORCE. STAMP MATCHING LETTER A ON OUTER FACE AT PIVOT END.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
