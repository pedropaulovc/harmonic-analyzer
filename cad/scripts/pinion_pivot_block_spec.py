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

from _hole_spec import HoleSpec, blind_cut_dia_mm

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

# --- Nominal geometry (cad/DIMENSIONS.md "Chapter 25").
# These drive the part's named equation globals AND the drawing's coordinate
# math.  U28 (user, 2026-09-23) re-laid the block in the photographed order
# (ch25 page002_img07/img08 front pair, read against the annotated 6 mm lever
# rod): from the west end, lift bore | screw | PIVOT bore | screw.  The two
# hold-down screws straddle the pivot bore; the lift bore sits out near the west
# end, 18.5 from the pivot, so the plain (uncut) swing strap clears the eccentric
# lift cam by placement (U12) instead of by a relief.
# Layout: the PIVOT bore is the part origin (datum B); the lift bore is at
# (-LIFT_BORE_SPACING, LIFT_BORE_RISE), block x -BLOCK_WEST..+BLOCK_EAST,
# y -BORE_UP..BLOCK_HEIGHT-BORE_UP, z 0..BLOCK_DEPTH.  (Part -X = machine
# WEST: the assembly places the block mirrored.) ---
BLOCK_EAST = 14.0  # pivot bore -> east end: 3.0 web past the east screw hole
BLOCK_WEST = 26.0  # pivot bore -> west end: 4.3 web past the lift bore
BLOCK_WIDTH = BLOCK_EAST + BLOCK_WEST  # 40.0 (photo ~38-41)
BLOCK_HEIGHT = 20.5  # lift bore keeps 3.2 (2.1 worst) of web under the top
BLOCK_DEPTH = 10.25  # U28: 12 -> 10.25 so the 9-thick back strap keeps 0.30 of
# axial air to the back block; the outer faces (and the 192/202 shafts) stay put
BORE_UP = 12.0  # pivot bore height above the base seat -- sets PIVOT_Y (derived)
BORE_DIA = 6.35  # 1/4 in: rides the Ø6.35 torque shaft / lift rod (derived)
LIFT_BORE_SPACING = 18.5  # pivot -> lift bore, horizontal (photo ~16-17): the
# eccentric collar (Ø14.6, ecc 2.0) orbits the lift axis and must clear the
# strap's R7.5 pivot end cap over the whole engage throw -- 1.83 of air
# nominal, 0.38 at the printed worst case (build_drive_train_assembly)
LIFT_BORE_RISE = 2.16  # lift bore above the pivot bore: the ecc-down collar
# hovers 0.153 under the follower stud 7 above the pivot (re-proven at import
# by build_drive_train_assembly's park-gap band)
SCREW_HALF_SPACING = 8.5  # hold-down holes at +-8.5 about the pivot bore:
# 2.8 web (2.2 worst) to the pivot bore, 4.6 to the lift bore
SCREW_HOLE_SPEC = HoleSpec("clearance", "#8")
SCREW_HOLE_DIA = blind_cut_dia_mm(SCREW_HOLE_SPEC)

# Derived spans (equations of the primitives above).
BLOCK_TOP_Y = BLOCK_HEIGHT - BORE_UP  # +8.5: block top above the pivot axis
BLOCK_BOTTOM_Y = -BORE_UP  # -12.0: the base seat
FRONT_BBOX_CX = (BLOCK_EAST - BLOCK_WEST) / 2.0  # -6.0: front-view centre
FRONT_BBOX_CY = (BLOCK_TOP_Y + BLOCK_BOTTOM_Y) / 2.0  # -1.75: front-view centre
SCREW_SPACING = 2.0 * SCREW_HALF_SPACING  # 17.0
BORE_DIA_BAND = (0.05, 0.00)

# The two reamed bores share a diameter.  The harvested pivot-bore cylinder
# spans y=-BORE_DIA/2..+BORE_DIA/2, while the raised lift bore does not reach
# the pivot bore's lower generator; that point makes this selector exact.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "pivot_bore",
        MACHINED_UM,
        CylinderFace(BORE_DIA, contains_y_mm=-BORE_DIA / 2.0),
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

# True free-text instructions only. Geometry, datum structure, form/orientation
# live in native dimensions / datum tags / FCFs / surface symbols. The part
# build stamps these strings into the SLDPRT; the drawing displays only
# $PRPSHEET links, so the print cannot silently diverge from its source model.
DRAWING_NOTES = "\n".join(
    (
        "HOLD-DOWN HOLES SYMMETRIC ABOUT THE PIVOT BORE (DATUM B).",
        "PIVOT AND LIFT BORES: 1/4 IN REAM THRU;",
        "RUNNING FIT ON THE <MOD-DIAM>6.35 TORQUE SHAFT / LIFT ROD.",
        "HOLD-DOWN HOLES: #8 NORMAL CLEARANCE Ø4.978 THRU, 2 PLACES,",
        "OVER MATCHING #8-32 MACHINE BED SCREW SEATS.",
        "2 BLOCKS REQUIRED; MACHINE IN ONE SETUP FOR MATCHED BORE HEIGHTS.",
        "FINISH: BLACK OXIDE AFTER MACHINING.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "lift-bore parallelism": "0.10",
    "hold-down hole position": "0.25",
}
