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
LIFT_BORE_RISE = 1.769918302299855  # v2 post raises the drive axis, steepening
# the parked strap to 49.864 deg.  Re-solving the follower-pin/cam contact puts
# the WEST lift bore above the pivot. This rise and the 12.5 c2c X spacing give
# exactly 0.15 mm parked air after the cam OD grows 9.2 -> 10.32 to restore its
# 0.575-mm thin-side wall. The block retains >1.8 mm above the reamed bore.
SCREW_HALF_SPACING = 13.5  # hold-down hole centres out past the bores: 0.6 web
# to the bore wall, 0.9 rim to the block end
SCREW_HOLE_DIA = 4.216  # #19 drill; mirrors _holes.NUMBER_DRILL_MM["#19"]
# (the offline test asserts they match) -- drawing view math only

# Derived spans (equations of the primitives above).
BLOCK_TOP_Y = BLOCK_HEIGHT - BORE_UP  # +4.0: block top above the pivot axis
BLOCK_BOTTOM_Y = -BORE_UP  # -12.0: the base seat
FRONT_BBOX_CY = (BLOCK_TOP_Y + BLOCK_BOTTOM_Y) / 2.0  # -4.0: front-view centre
BORE_SPACING = 2.0 * BORE_HALF_SPACING  # 15.0
SCREW_SPACING = 2.0 * SCREW_HALF_SPACING  # 27.0

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_pinion_pivot_block`` marks exactly these;
# ``draw_pinion_pivot_block`` keeps exactly their union across its per-view
# ``keep`` maps. The offline test enforces ``union(marks) == union(keeps)``. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {
        "BlockWidth",
        "BlockHeight",
        "AnchorZ",
        "PivotBoreX",
        "PivotBoreDia",
        "LiftBoreX",
        "LiftBoreCz",
        "LiftBoreDia",
    },
    "Block": {"Depth"},
}

# True free-text instructions only. Geometry, datum structure, form/orientation
# live in native dimensions / datum tags / FCFs / surface symbols. The part
# build stamps these strings into the SLDPRT; the drawing displays only
# $PRPSHEET links, so the print cannot silently diverge from its source model.
DRAWING_NOTES = "\n".join(
    (
        "BORES AND HOLD-DOWN HOLES SYMMETRIC ABOUT THE BLOCK MID-PLANE.",
        "PIVOT AND LIFT BORES: 1/4 IN REAM THRU;",
        "RUNNING FIT ON THE <MOD-DIAM>6.35 TORQUE SHAFT / LIFT ROD.",
        "HOLD-DOWN HOLES: #19 DRILL THRU, 2 PLACES,",
        "MATCHING THE MACHINE BED SCREW SEATS.",
        "2 BLOCKS REQUIRED; MACHINE IN ONE SETUP FOR MATCHED BORE HEIGHTS.",
        "FINISH: BLACK OXIDE AFTER MACHINING.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
