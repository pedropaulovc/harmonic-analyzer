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

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

# --- Nominal geometry (DIMENSIONS.md "Chapter 24", all scaled from the p.65
# close-up vs the ~5 mm square rod, low).  These drive the part's named
# equation globals AND the drawing's coordinate math. ---
# Photo read (ch24 p.60 macro + the 4/4 video, v4_t00579..t00645): a plain
# brass block hanging on the square rod -- the rod drops into the bore nearest
# the paper and a side set screw (front face, over that bore) pins it; the
# second bore is a spare pen seat. The marker lies in a GROOVE milled along
# the block's bottom face (the U-notch on the p.60 end face), and the stirrup
# frame's thumb screw presses it up into that groove. The old read of the
# p.60 notch as a stopped flexure slit is refuted by t00612 (the marker runs
# through the groove, block level).
BLOCK_LENGTH = 36.0  # X, along the marker (t00612: ~2.2x the 16 end face)
BLOCK_HEIGHT = 18.0  # Y
BLOCK_DEPTH = 16.0  # Z
CHAMFER = 6.0  # 45 deg top corners
BORE_DIA = 8.0  # two vertical pen bores
BORE_X = (10.0, 26.0)  # rod bore (paper end) / spare pen seat (free end)
GROOVE_WIDTH = 8.5  # bottom marker groove, across Z (O8 barrel + 0.25 each side)
GROOVE_DEPTH = 4.5  # groove rise from the bottom face (the barrel stands 3.5 proud)
GROOVE_Z0 = (BLOCK_DEPTH - GROOVE_WIDTH) / 2.0  # 3.75: centred across the depth
SCREW_HOLE_DIA = 2.5  # front-face rod set-screw hole, over the rod bore
SCREW_HOLE_XY = (BORE_X[0], 11.0)

_UPPER_BORE_Y = (GROOVE_DEPTH + BLOCK_HEIGHT) / 2.0
SURFACE_FINISHES = tuple(
    SurfaceFinishControl(
        f"pen_bore_{index}",
        MACHINED_UM,
        CylinderFace(
            BORE_DIA,
            contains_x_mm=x,
            contains_y_mm=_UPPER_BORE_Y,
        ),
    )
    for index, x in enumerate(BORE_X)
)

# Derived spans (equations of the primitives above).

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  ``build_pen_v_block`` marks exactly these; ``draw_pen_v_block``
# keeps exactly their union across its per-view ``keep`` maps.  The offline test
# enforces ``union(marks) == union(keeps)`` so a rename in one script that isn't
# mirrored in the other fails before any SolidWorks build. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "OutlineProfile": {"Length", "Chamfer2dx"},
    "Block": {"Depth"},
    "BoreProfile": {"Bore0X", "Bore1X", "Bore0Dia"},
    "GrooveProfile": {"GrooveWidth", "GrooveZ0"},
    "Groove": {"GrooveDepth"},
    "ScrewHoleProfile": {"ScrewHoleCx", "ScrewHoleCz", "ScrewHoleDiaDim"},
}

# Position-controlled bore stations: save BASIC on these source dimensions so
# imported drawing boxes survive closing/reopening both native documents.
SOURCE_BASIC_DIMENSIONS: dict[str, set[str]] = {
    "BoreProfile": {"Bore0X", "Bore1X"},
}

# True free-text instructions only.  Geometry, datum structure, form/orientation,
# and roughness live in native dimensions / datum tags / FCFs / surface symbols.
# The part build stamps these strings into the SLDPRT; the drawing displays only
# $PRPSHEET links, so the print cannot silently diverge from its source model.
DRAWING_NOTES = "\n".join(
    (
        "PEN BORES: 2X <MOD-DIAM>8 THRU (VERTICAL), CENTRED ACROSS 16 DEPTH.",
        "MARKER GROOVE: MILL 8.5 WIDE X 4.5 DEEP ALONG THE FULL LENGTH OF",
        "THE BOTTOM FACE, CENTRED ACROSS THE 16 DEPTH; FLOOR FLAT.",
        "ROD SET-SCREW HOLE <MOD-DIAM>2.5 DRILL THRU (FRONT TO BACK) ON THE",
        "LEFT BORE AXIS; THREAD/FIT TO SUIT SET SCREW AT ASSEMBLY.",
        "FINISH: BRIGHT BRASS, DEBURR ALL EDGES; DO NOT PAINT.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "pen bore position": "0.20",
    "block top-face parallelism": "0.10",
}
