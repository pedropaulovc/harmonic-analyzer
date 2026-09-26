r"""Pinion-pivot-block dimensional contract -- the single source of truth shared
by the part build (``build_pinion_pivot_block.py``) and its manufacturing
drawing (``draw_pinion_pivot_block.py``).

PURE DATA, no SolidWorks/COM imports: the nominal geometry (the "editable
knobs"), the derived spans the drawing needs for its view math, and the
marked-dimension -> kept-dimension NAME map.  Keeping this in ONE module means
a rename or a nominal change is a single edit that reaches both scripts, so the
part-side ``mark_dimensions_for_drawing`` set and the drawing-side ``keep``
maps cannot silently drift apart.

Build-graph consequence (intended): both ``build_pinion_pivot_block`` and
``draw_pinion_pivot_block`` import THIS file, so ``module_deps_of`` folds it
into BOTH recipe digests -- an edit here rebuilds the part AND the drawing.
The drawing does not import the build script, so a pure build-logic edit that
leaves this spec (and the .SLDPRT geometry) untouched does NOT force a drawing
rebuild; a geometry change still re-renders the drawing via its .SLDPRT
``file_dep``.

The offline lockstep test (``test_pinion_pivot_block_drawing.py``) asserts the
part marks and the drawing keeps EXACTLY ``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations

import _config
from _fit_limits import REAM_SLIDE
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

# Nominal geometry lives in pinion_pivot_block_geometry (shared with the
# assembly and the base); this contract re-exports it for the part and sheet.
from pinion_pivot_block_geometry import (
    BLOCK_EAST as BLOCK_EAST,
    BLOCK_WEST as BLOCK_WEST,
    BLOCK_WIDTH as BLOCK_WIDTH,
    BLOCK_HEIGHT as BLOCK_HEIGHT,
    BLOCK_DEPTH as BLOCK_DEPTH,
    BORE_UP as BORE_UP,
    BORE_DIA as BORE_DIA,
    LIFT_BORE_SPACING as LIFT_BORE_SPACING,
    LIFT_BORE_RISE as LIFT_BORE_RISE,
    SCREW_HALF_SPACING as SCREW_HALF_SPACING,
    SCREW_HOLE_SPEC as SCREW_HOLE_SPEC,
    SCREW_HOLE_DIA as SCREW_HOLE_DIA,
    BLOCK_TOP_Y as BLOCK_TOP_Y,
    BLOCK_BOTTOM_Y as BLOCK_BOTTOM_Y,
    FRONT_BBOX_CX as FRONT_BBOX_CX,
    FRONT_BBOX_CY as FRONT_BBOX_CY,
    SCREW_SPACING as SCREW_SPACING,
)

# One fit per shaft (Main R2, converged-r7 review): the same REAM_SLIDE band
# MHA-056 holds on the same Ø6.35 h shafts, never a line-to-line limit on a
# bore that must turn or slide by hand.
BORE_DIA_BAND = REAM_SLIDE

# Both reamed bores are running faces (rule 5): MHA-062 turns in the pivot
# bore and MHA-060 in the lift bore (Main, MHA-061 eye pass: the lift bore
# had none).  They share a diameter.  The harvested pivot-bore cylinder
# spans y=-BORE_DIA/2..+BORE_DIA/2, while the raised lift bore does not reach
# the pivot bore's lower generator; that point makes the pivot selector
# exact.  The lift bore sits LIFT_BORE_SPACING west, beyond the pivot
# bore's x-span, which makes its selector exact.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "pivot_bore",
        MACHINED_UM,
        CylinderFace(BORE_DIA, contains_y_mm=-BORE_DIA / 2.0),
    ),
    SurfaceFinishControl(
        "lift_bore",
        MACHINED_UM,
        CylinderFace(BORE_DIA, contains_x_mm=-LIFT_BORE_SPACING),
    ),
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_pinion_pivot_block`` marks exactly these;
# ``draw_pinion_pivot_block`` keeps exactly their union across its per-view
# ``keep`` maps. The offline test enforces ``union(marks) == union(keeps)``. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {
        "BlockWidth",
        "BlockHeight",
        "AnchorX",
        "AnchorZ",
        "PivotBoreDia",
        "LiftBoreX",
        "LiftBoreCz",
        "LiftBoreDia",
    },
    "Block": {"Depth"},
}


def _registry_name(part: str) -> str:
    """A mating part as its own sheet names it: number and title, uppercase."""
    row = _config.parts(part)
    return f"{row['number']} {str(row['title']).upper()}"


# Each running bore's mate is named from the registry, so the note cannot
# drift from that part's own title block (Main, pc-r7 eye pass: the note said
# "TORQUE SHAFT" where MHA-062's title reads PINION PIVOT SHAFT).
PIVOT_SHAFT_NAME = _registry_name("pinion-pivot-shaft")
LIFT_ROD_NAME = _registry_name("pinion-lift-rod")

# True free-text instructions only. Geometry lives in native dimensions and
# the two running-bore surface symbols (policy rule 3: a block carries no
# frames or datums). The part
# build stamps these strings into the SLDPRT; the drawing displays only
# $PRPSHEET links, so the print cannot silently diverge from its source model.
DRAWING_NOTES = "\n".join(
    (
        # Fable review r4 (rule 2): name each running bore's mate and state the
        # functional acceptance; the REAM and hold-down callouts are not repeated.
        f"PIVOT BORE RUNS ON {PIVOT_SHAFT_NAME},",
        f"  LIFT BORE ON {LIFT_ROD_NAME};",
        "  EACH SHAFT TURNS FREELY BY HAND.",
        # Assembly operations are never part notes (rule 6): the front
        # block's feeler setting is on the drive-train assembly step list
        # (ruling (c), Codex #854), and spotting the base seats through the
        # block holes is RIG_SET_STEP plus the harmonic base's
        # "TRANSFER FROM MHA-061" callout (Main, MHA-061 eye pass).
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
