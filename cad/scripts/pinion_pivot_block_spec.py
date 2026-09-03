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

from _surface_finish import SurfaceFinishControl

# --- Nominal geometry (cad/DIMENSIONS.md "Chapter 25", photo-scaled low).
# These drive the part's named equation globals AND the drawing's coordinate
# math. Layout: block centred on the origin midway between the bores, both
# bores along Z, block x -18..18, y -12..6.75, z 0..12. ---
BLOCK_WIDTH = 36.0  # spans both bores + margin; widened 33 -> 36 (PR7) so the
# Ø8 screw heads at x +-13.5 seat fully on the block (edge 17.5 + 0.5 rim)
BLOCK_HEIGHT = 18.75  # v2 linkage closure; keeps the strap's r 11 bottom cap
# (PIVOT_Y - 11 = 51.8) swinging clear of the base top 50.8
BLOCK_DEPTH = 12.0  # photo-scaled (low)
BORE_UP = 12.0  # pivot bore height above the base seat -- sets PIVOT_Y (derived)
BORE_DIA = 6.35  # 1/4 in: rides the Ø6.35 torque shaft / lift rod (derived)
BORE_HALF_SPACING = 6.25  # half the pivot-to-lift rod spacing 12.5 -- the
# lift rod must clear BOTH the cone-pivot-post column (machine x -47.1)
# and the strap's swinging r 11 bottom cap (build_drive_train_assembly)
LIFT_BORE_RISE = 1.8561911789147132  # 2026-09 re-solve for the short near-
# vertical strap (pinion_bracket_geometry C2C 28, lean ~8.1 deg, follower stud
# 6 ABOVE the pivot): the lift bore sits this much above the pivot bore so the
# ecc-down cam collar hovers exactly 0.15 under the stud (scratchpad solver,
# re-proven at import by build_drive_train_assembly's park-gap band).
SCREW_HALF_SPACING = 13.5  # hold-down hole centres out past the bores: 0.6 web
# to the bore wall, 0.9 rim to the block end
SCREW_HOLE_DIA = 4.216  # #19 drill; mirrors _holes.NUMBER_DRILL_MM["#19"]
# (the offline test asserts they match) -- drawing view math only

# Derived spans (equations of the primitives above).
BLOCK_TOP_Y = BLOCK_HEIGHT - BORE_UP  # +6.75: block top above the pivot axis
BLOCK_BOTTOM_Y = -BORE_UP  # -12.0: the base seat
FRONT_BBOX_CY = (BLOCK_TOP_Y + BLOCK_BOTTOM_Y) / 2.0  # -2.625: front-view centre
BORE_SPACING = 2.0 * BORE_HALF_SPACING  # 12.5
SCREW_SPACING = 2.0 * SCREW_HALF_SPACING  # 27.0
LIFT_BORE_FROM_END = BLOCK_WIDTH / 2.0 - BORE_HALF_SPACING  # 11.75
SCREW_FROM_END = BLOCK_WIDTH / 2.0 - SCREW_HALF_SPACING  # 4.5
BORE_DIA_BAND = (0.05, 0.00)
# The two blocks are interchangeable parts, not a matched pair: the torque
# shaft and the lift rod each pass through BOTH, so the bore heights carry a
# band on the model dimensions instead of a "matched heights" note
# (machinist review 2026-09-02).
PIVOT_BORE_HEIGHT_TOLERANCE_MM = 0.05
LIFT_BORE_RISE_TOLERANCE_MM = 0.05

# No roughness callouts: the torque shaft is static in the pivot bore and the
# lift rod only turns in the lift bore at engage; the title block's Ra 3.2
# covers both reamed bores (cad/docs/drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_pinion_pivot_block`` marks exactly these;
# ``draw_pinion_pivot_block`` keeps exactly their union across its per-view
# ``keep`` maps. The offline test enforces ``union(marks) == union(keeps)``.
# The bores' longitudinal stations (PivotBoreX / LiftBoreX, unsigned distances
# to the sketch origin, i.e. the invisible mid-plane) are NOT marked: the print
# locates the lift bore from the end face and the pivot bore from the lift bore
# with drawing edge dimensions (machinist review 2026-09-02). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {
        "BlockWidth",
        "BlockHeight",
        "AnchorZ",
        "PivotBoreDia",
        "LiftBoreCz",
        "LiftBoreDia",
    },
    "Block": {"Depth"},
}

# Notes: process facts only (drawing-simplicity-policy.md rule 6).  Drill and
# ream ride the hole callouts; every location is a dimension from a face.
DRAWING_NOTES = "\n".join(
    (
        "REAM BOTH BORES IN ONE SETUP.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
