r"""Pinion-pivot-block dimensional contract -- the single source of truth shared
by the part build (``build_dt_pinion_pivot_block.py``) and its manufacturing
drawing (``draw_dt_pinion_pivot_block.py``).

PURE DATA, no SolidWorks/COM imports: the nominal geometry (the "editable
knobs"), the derived spans the drawing needs for its view math, and the
marked-dimension -> kept-dimension NAME map.  Keeping this in ONE module means
a rename or a nominal change is a single edit that reaches both scripts, so the
part-side ``mark_dimensions_for_drawing`` set and the drawing-side ``keep``
maps cannot silently drift apart.

Build-graph consequence (intended): both ``build_dt_pinion_pivot_block`` and
``draw_dt_pinion_pivot_block`` import THIS file, so ``module_deps_of`` folds it
into BOTH recipe digests -- an edit here rebuilds the part AND the drawing.
The drawing does not import the build script, so a pure build-logic edit that
leaves this spec (and the .SLDPRT geometry) untouched does NOT force a drawing
rebuild; a geometry change still re-renders the drawing via its .SLDPRT
``file_dep``.

The offline lockstep test (``test_dt_pinion_pivot_block_drawing.py``) asserts the
part marks and the drawing keeps EXACTLY ``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations

import _config
from _fit_ream_slide import REAM_SLIDE
from _gtol_cylinder import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

# Nominal geometry lives in dt_pinion_pivot_block_geometry (shared with the
# assembly and the base); this contract re-exports it for the part and sheet.
from dt_pinion_pivot_block_geometry import (
    BLOCK_EAST as BLOCK_EAST,
    BLOCK_WEST as BLOCK_WEST,
    BLOCK_WIDTH as BLOCK_WIDTH,
    BLOCK_HEIGHT as BLOCK_HEIGHT,
    BLOCK_DEPTH as BLOCK_DEPTH,
    BLOCK_DEPTH_PLACES as BLOCK_DEPTH_PLACES,
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
    UNIT as UNIT,
)

# One fit per shaft (Main R2, converged-r7 review): the same REAM_SLIDE band
# MHA-DT-14 holds on the same Ø6.35 h shafts, never a line-to-line limit on a
# bore that must turn or slide by hand.
BORE_DIA_BAND = REAM_SLIDE

# Both reamed bores are running faces (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)): MHA-DT-19 turns in the pivot
# bore and MHA-DT-17 in the lift bore (Main, MHA-DT-18 eye pass: the lift bore
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
        display_unit=UNIT,
    ),
    SurfaceFinishControl(
        "lift_bore",
        MACHINED_UM,
        CylinderFace(BORE_DIA, contains_x_mm=-LIFT_BORE_SPACING),
        display_unit=UNIT,
    ),
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_dt_pinion_pivot_block`` marks exactly these;
# ``draw_dt_pinion_pivot_block`` keeps exactly their union across its per-view
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

# #290 inch sheet: the part authors each printed dimension's places
# (build_dt_pinion_pivot_block).  Four on the two reamed bores, whose
# +.0015/+.0010 band needs them; three on the lift bore's spacing and rise,
# kinematic nominals kept from the millimetre design (the cam park-gap
# closure, named by the spacing's callout); two on the snapped envelope and
# depth (BLOCK_DEPTH_PLACES, the row the rig's stack reads) and on the pivot
# bore's height (AnchorZ, .66).  No check reads that height's band: it lifts
# the whole rig (pivot, lift bore, cam) together, so the park gap holds, and
# at the engaged pose its .010 moves the mesh centre about 1% of that.  The
# model keeps its millimetre nominal (the bank's raised axis).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {
        "BlockWidth": 2,
        "BlockHeight": 2,
        "AnchorX": 2,
        "AnchorZ": 2,
        "PivotBoreDia": 4,
        "LiftBoreX": 3,
        "LiftBoreCz": 3,
        "LiftBoreDia": 4,
    },
    "Block": {"Depth": BLOCK_DEPTH_PLACES},
}
if {f: set(d) for f, d in DRAWING_PRECISION.items()} != DRAWING_DIMENSIONS:
    raise AssertionError("every marked dimension must state its decimal places")

# The #8 clearance Hole Wizard callout prints its drill size at the inch
# sheet's .XXX (#290).
SCREW_HOLE_CALLOUT_PRECISION = 3


def _registry_mate(row: dict) -> tuple[str, str]:
    """A mating part as its own sheet names it: number, then title in capitals."""
    return str(row["number"]), str(row["title"]).upper()


# Each running bore's mate is named from the registry, so the callout cannot
# drift from that part's own title block (Main, pc-r7 eye pass: the note said
# "TORQUE SHAFT" where MHA-DT-19's title reads PINION PIVOT SHAFT).  Each row is
# read by its literal name so the drawing's config deps carry those two rows
# (a computed name reads as the part's own row only).
PIVOT_SHAFT_MATE = _registry_mate(_config.parts("dt-pinion-pivot-shaft"))
LIFT_ROD_MATE = _registry_mate(_config.parts("dt-pinion-lift-rod"))


def _ream_callout(mate: tuple[str, str]) -> str:
    """The text under a reamed bore's size: process, fit and the mate it runs on
    (drawing-guidelines.md rule 4 (tighten only for function, and name the
    mate), at the callout it serves; machinist review r1, #1014).  One phrase
    per line keeps the block narrow beside the 3:1 front view."""
    number, title = mate
    return "\n".join(("THRU - REAM", "RUNNING FIT ON", number, title))


# The sheet carries no general notes: each bore's mate and fit ride its REAM
# callout (rule 7 (notes: few, flagged, never a method): flag it where it
# applies), the hold-downs are fully defined by their DRILL callout, and
# assembly operations (the front block's feeler setting, spotting the base seats
# through the block holes) live on the drive-train assembly's step list and the
# harmonic base's "TRANSFER FROM MHA-DT-18" callout.
BORE_CALLOUTS = {
    "PivotBoreDia": _ream_callout(PIVOT_SHAFT_MATE),
    "LiftBoreDia": _ream_callout(LIFT_ROD_MATE),
}
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
