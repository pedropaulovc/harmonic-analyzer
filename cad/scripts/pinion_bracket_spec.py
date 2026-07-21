r"""Pinion-swing-bracket dimensional contract -- the single source of truth shared
by the part build (``build_pinion_bracket.py``) and its manufacturing drawing
(``draw_pinion_bracket.py``).

PURE DATA, no SolidWorks/COM imports: the nominal geometry (the "editable
knobs"), the derived spans the drawing needs for its view math, and the
marked-dimension -> kept-dimension NAME map.  Keeping this in ONE module means
a rename or a nominal change is a single edit that reaches both scripts, so the
part-side ``mark_dimensions_for_drawing`` set and the drawing-side ``keep``
maps cannot silently drift apart.

Build-graph consequence (intended): both ``build_pinion_bracket`` and
``draw_pinion_bracket`` import THIS file, so ``module_deps_of`` folds it into
BOTH recipe digests -- an edit here rebuilds the part AND the drawing.  The
drawing does not import the build script, so a pure build-logic edit that leaves
this spec (and the .SLDPRT geometry) untouched does NOT force a drawing rebuild;
a geometry change still re-renders the drawing via its .SLDPRT ``file_dep``.

The offline lockstep test (``test_pinion_bracket_drawing.py``) asserts the part
marks and the drawing keeps EXACTLY ``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations

# --- Nominal geometry (cad/config/dimensions.yaml "Chapter 25", photo-scaled).
# These drive the part's named equation globals AND the drawing's coordinate
# math. Layout: pivot bore at the origin, arbor bore at (0, C2C), strap up +Y,
# thickness z 0..THICKNESS; a blind pin seat bores into the west (-X) edge. ---
WIDTH = 18.0  # strap width (= cap diameter): build_drive_train STRAP_R_END = WIDTH/2
C2C = 43.0  # pivot bore -> arbor bore centre distance (up the strap centreline)
THICKNESS = 5.0  # strap thickness (photo-scaled, low)
PIVOT_BORE = 6.35  # 1/4 in: rides the torque shaft (build_pinion_pivot_shaft)
ARBOR_BORE = 8.0  # rides the steel drum arbor (build_pinion_arbor SHAFT_DIA)
PIN_BORE = 4.0  # cam-follower pin press seat -- build_pinion_cam_pin PIN_DIA
PIN_DROP = 2.0  # pivot bore centre -> pin bore axis, down the strap centreline
PIN_SEAT = 4.0  # blind depth of the pin seat from the x=-WIDTH/2 tangent plane

# Derived spans (equations of the primitives above).
R_END = WIDTH / 2.0  # 9.0: cap radius at each rounded end
HALF_WIDTH = R_END  # 9.0
OVERALL_LENGTH = C2C + 2.0 * R_END  # 61.0: cap tip to cap tip

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
