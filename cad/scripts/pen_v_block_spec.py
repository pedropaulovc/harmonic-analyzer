r"""Pen v-block dimensional contract -- the single source of truth shared by the
part build (``build_pen_v_block.py``) and its manufacturing drawing
(``draw_pen_v_block.py``).

PURE DATA, no SolidWorks/COM imports: the nominal geometry (the "editable
knobs"), the derived spans the drawing needs for its view math, and the
marked-dimension -> kept-dimension NAME map.  Keeping this in ONE module means a
rename or a nominal change is a single edit that reaches both scripts, so the
part-side ``mark_dimensions_for_drawing`` set and the drawing-side ``keep`` maps
cannot silently drift apart.

Build-graph consequence (intended): both ``build_pen_v_block`` and
``draw_pen_v_block`` import from THIS file, so ``module_deps_of`` folds it into
BOTH recipe digests -- an edit here rebuilds the part AND the drawing.  The
drawing does not import ``build_pen_v_block``, so a pure build-logic edit that
leaves this spec (and the .SLDPRT geometry) untouched does not force a drawing
rebuild; a geometry change still re-renders the drawing via its .SLDPRT
``file_dep``.

The offline lockstep test (``test_pen_v_block_drawing.py``) asserts the part
marks and the drawing keeps EXACTLY ``DRAWING_DIMENSIONS`` -- the drift alarm,
run without SolidWorks in ~1 s.
"""

from __future__ import annotations

# --- Nominal geometry (DIMENSIONS.md "Chapter 24", all scaled from the p.65
# close-up vs the ~5 mm square rod, low).  These drive the part's named
# equation globals AND the drawing's coordinate math. ---
BLOCK_LENGTH = 32.0  # X
BLOCK_HEIGHT = 18.0  # Y
BLOCK_DEPTH = 16.0  # Z
CHAMFER = 6.0  # 45 deg top corners
BORE_DIA = 8.0  # two vertical pen bores
BORE_X = (11.0, 21.0)
SLIT_LENGTH = 26.0  # stopped cut from x=0; hinge remains 26..32
SLIT_Y = (4.0, 8.0)  # slit band
SCREW_HOLE_DIA = 2.5  # front-face clamp/set screw hole
SCREW_HOLE_XY = (29.0, 11.0)

# Derived spans (equations of the primitives above).
SLIT_WIDTH = SLIT_Y[1] - SLIT_Y[0]  # 4.0
HINGE_LENGTH = BLOCK_LENGTH - SLIT_LENGTH  # 6.0: the uncut flex hinge

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  ``build_pen_v_block`` marks exactly these; ``draw_pen_v_block``
# keeps exactly their union across its per-view ``keep`` maps.  The offline test
# enforces ``union(marks) == union(keeps)`` so a rename in one script that isn't
# mirrored in the other fails before any SolidWorks build. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "OutlineProfile": {"Length", "Chamfer2dx"},
    "Block": {"Depth"},
    "BoreProfile": {"Bore0X", "Bore1X", "Bore0Dia"},
    "SlitProfile": {"SlitLength", "SlitWidth", "SlitY0"},
    "ScrewHoleProfile": {"ScrewHoleCx", "ScrewHoleCz", "ScrewHoleDiaDim"},
}

# True free-text instructions only.  Geometry, datum structure, form/orientation,
# and roughness live in native dimensions / datum tags / FCFs / surface symbols.
# The part build stamps these strings into the SLDPRT; the drawing displays only
# $PRPSHEET links, so the print cannot silently diverge from its source model.
DRAWING_NOTES = "\n".join(
    (
        "PEN BORES: 2X <MOD-DIAM>8 THRU (VERTICAL), CENTRED ACROSS 16 DEPTH.",
        "CLAMP SLIT: SAW OR MILL 4 WIDE THRU DEPTH FROM LEFT END ONLY;",
        "STOP AT 26 -- THE UNCUT 6 AT THE RIGHT END IS THE FLEX HINGE.",
        "CLAMP-SCREW HOLE <MOD-DIAM>2.5 DRILL THRU (FRONT TO BACK);",
        "THREAD/FIT TO SUIT CLAMP SCREW AT ASSEMBLY.",
        "FINISH: PAINT MACHINE GREEN AFTER MACHINING; MASK THE PEN BORES.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
