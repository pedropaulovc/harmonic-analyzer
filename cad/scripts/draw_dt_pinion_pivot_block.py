r"""Create the curated machinist drawing for the pinion pivot block.

The SLDPRT remains authoritative.  This recipe supplies only the block's
views, dimension layout, hole callouts, and manufacturing notes;
sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.

The sheet runs at 3:1 with the raised envelope from the spec; the isometric carries an
explicit 2:1 override so it stays clear of the title block.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_pinion_pivot_block.py dt-pinion-pivot-block
"""

from __future__ import annotations

import argparse
import inspect
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import set_dimension_callouts
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_finish import add_surface_finish
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _printed_limits import drilled_limits, limits
from _session import run_build
from _surface_finish import MACHINED_UM, surface_finish_by_key
import _telemetry
from dt_pinion_pivot_block_notes import (
    LIFT_BORE_NOTE,
    LIFT_BORE_NOTE_NUMBER,
    LIFT_BORE_NOTE_TEXT,
)
from dt_pinion_pivot_block_spec import (
    BLOCK_DEPTH,
    BLOCK_EAST,
    BLOCK_HEIGHT,
    BLOCK_TOP_Y,
    BLOCK_WEST,
    BLOCK_WIDTH as BLOCK_WIDTH,
    BORE_UP,
    DRAWING_PRECISION,
    FRONT_BBOX_CX,
    FRONT_BBOX_CY,
    LIFT_BORE_BAND as LIFT_BORE_BAND,
    LIFT_BORE_DIA,
    LIFT_BORE_RISE,
    LIFT_BORE_SPACING,
    LIFT_ROD_MATE,
    PIVOT_BORE_BAND,
    PIVOT_BORE_DIA,
    PIVOT_SHAFT_MATE,
    SCREW_HALF_SPACING,
    SCREW_HOLE_CALLOUT_PRECISION,
    SCREW_HOLE_DIA,
    SURFACE_FINISHES,
    UNIT,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_pinion_pivot_block"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (3.0, 1.0)

# Sheet layout (meters). The part origin is the pivot bore; the front
# bounding box follows the raised stock's spec spans at 3:1. Third angle:
# the top view carrying the two hold-down holes sits above the front;
# the right view carries the block-height by depth section.
FRONT_CENTER = (0.140, 0.128)
TOP_CENTER = (0.140, 0.222)
RIGHT_CENTER = (0.285, 0.128)
# Lowered from 0.225: machinist review r1 (#1014) found its top vertex on the
# inner border (rule 13 (stay inside the border)).
ISO_CENTER = (0.360, 0.212)
ISO_NOTE_XY = (0.335, 0.167)


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front/top views (3:1, bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - FRONT_BBOX_CX) * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (3:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


PIVOT_BORE_R_SHEET = PIVOT_BORE_DIA * SHEET_SCALE[0] / 2000.0
LIFT_BORE_R_SHEET = LIFT_BORE_DIA * SHEET_SCALE[0] / 2000.0
SCREW_R_SHEET = SCREW_HOLE_DIA * SHEET_SCALE[0] / 2000.0
FRONT_TOP_Y = _front_y(BLOCK_HEIGHT - BORE_UP)
PIVOT_SHEET_XY = (_front_x(0.0), _front_y(0.0))
PIVOT_FINISH_XY = (0.208, FRONT_TOP_Y + 0.01125)

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  The front view has ONE datum, the pivot bore (the part origin and
# the axis the swing rig turns on): every location in it runs from that bore
# and carries the ASME dimension-origin circle there (PIVOT_ORIGIN_DIMENSIONS).
# Machinist review r1 (#1014) read the lift bore's 18.50/2.16 as chained off a
# bore that was itself located from the west end and the bottom (rule 10
# (dimension from a real feature)); the origin circles say which end each
# dimension starts from.  The lift bore stays on the pivot bore because that
# spacing is the functional one: the eccentric collar on the lift rod clears
# the strap's pivot end cap by 1.83 nominal, and edge baselines would double
# the spacing's band.  The lift-bore spacing sits above the view, the
# pivot-to-west-end station and overall width below it; the pivot height and
# overall height stack on the east side next to the pivot; the lift-bore rise
# stands outside the west end (rule 14 (keep text off the part): r1 found it
# between the bores, inside the outline); the leadered diameters land in the
# clear corners.
FRONT_KEEP = {
    "BlockWidth": (_front_x(FRONT_BBOX_CX), 0.074),
    "AnchorX": (_front_x(-BLOCK_WEST / 2.0), 0.084),
    # The position anchors the text stack, and the one-line function callout
    # above it pushes the dimension line down: at +0.00625 farm r3 drew the
    # line ~1 mm over the block's top edge (review r3, #1014), so the stack
    # rises until the line stands ~8 mm clear, like 26.00 below the view.
    "LiftBoreX": (_front_x(-LIFT_BORE_SPACING / 2.0), FRONT_TOP_Y + 0.0135),
    "BlockHeight": (0.226, 0.123),
    "AnchorZ": (0.212, 0.113),
    # Outside the west end: the pivot-centre witness runs west through the
    # lift bore to the dimension line, a conventional extension-line crossing
    # (rule 14's list of defects is complete and does not include it).  The
    # value and its SETS PARK GAP line stand below the pivot witness and ~20
    # mm west of the block (#2106 delta run 084519018Z: centred between the
    # witnesses, both lines ran across them and into the outline), above the
    # lift bore's Ra symbol.
    "LiftBoreCz": (
        _front_x(-BLOCK_WEST) - 0.0205,
        _front_y(0.0) - 0.008,
    ),
    # Every horizontal/vertical witness from the pivot centre crosses its rim
    # at 0/90/180/270 deg.  The leader runs to the NEAR end of the text's
    # shoulder (the bottom line's), so the text sits up and right of the bore
    # and the leader climbs at ~65 deg, clear of the Ra symbol's ~30 deg
    # sector.  The four-line callout (size, REAM THRU and the shaft's
    # acceptance) is centred here, so its bottom stays over the Ra symbol and
    # its left edge right of the top view.
    "PivotBoreDia": (0.224, 0.205),
    # Up-left of the lift bore, in the clear band left of the top view and
    # above the lift-bore rise.  Farm round 1 (f08277cd0ee5) centred the
    # block at x 0.045: its widest row ran through the inner border (x
    # ~0.0124) onto zone letter C.  At 0.055 the widest row ("MHA-DT-17
    # TURNS FREELY", ~58 mm) stays inside the border and left of the .728
    # extension line (x ~0.1025).
    "LiftBoreDia": (0.055, 0.182),
}
RIGHT_KEEP = {"Depth": (RIGHT_CENTER[0], FRONT_TOP_Y + 0.00925)}
TOP_KEEP = {}
# Each bore: size, then process, then at most two rows of words
# (rule 7; rule 26 size-process-depth order).  The lift bore's .728/.085
# locations carry value and band only; their reason is numbered note 1
# (dt_pinion_pivot_block_notes, which the feature export reads), flagged from
# the lift-bore callout.
# Upper-left, in the open band under the front view's 1.57 row (y ~0.074)
# and left of the title block (x 0.216): ~140 mm at the note font.
LIFT_BORE_NOTE_XY = (0.020, 0.058)
DIMENSION_CALLOUTS = {
    "PivotBoreDia": "\n".join(
        ("REAM THRU", f"{PIVOT_SHAFT_MATE[0]} ENTERS,", "TURNS BY HAND")
    ),
    "LiftBoreDia": "\n".join(
        (
            "F DRILL THRU",
            f"{LIFT_ROD_MATE[0]} TURNS FREELY",
            f"SEE NOTE {LIFT_BORE_NOTE_NUMBER}",
        )
    ),
}
# Front-view locations that start at the pivot bore: name -> the sheet axis
# each measures along (0 = x, 1 = y).
PIVOT_ORIGIN_DIMENSIONS = {"AnchorX": 0, "LiftBoreX": 0, "AnchorZ": 1, "LiftBoreCz": 1}
_ORIGIN_ARROWHEAD = 4  # swArrowStyle_e.swORIGIN_ARROWHEAD (no-fill circle)
_CLOSED_ARROWHEAD = 1  # swArrowStyle_e.swCLOSED_ARROWHEAD

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, beside the constants of the
# code that prints it, in the part frame (build_dt_pinion_pivot_block; the
# layout note at dt_pinion_pivot_block_geometry.BLOCK_EAST): the origin is the
# pivot bore's axis on the back face (the Front sketch plane, z = 0), +X runs
# from the west end (x = -BLOCK_WEST) to the east end (x = +BLOCK_EAST), +Y up
# from the bottom (base seat, y = -BORE_UP) to the top (y = BLOCK_TOP_Y), and
# the block is extruded +Z to the front face (z = BLOCK_DEPTH), the face the
# front view looks at.  Both bores run along Z (entered here from the
# front face); the two #8 hold-down holes run along Y (entered from the top
# face the top view shows), at mid-depth.  A band is the title block's row for
# the places the sheet prints (DRAWING_PRECISION) on the printed nominal, the
# DRILLED HOLES row on a drilled diameter, or the reamer's ANALYSIS band on the
# reamed pivot bore; the hold-down
# drill takes the DRILLED HOLES row at its callout's .XXX.  The declarations
# print nothing.
#
# The top view's hold-down stations (.69, 1.35 from the west end) and their
# depth location (.22 from the front face) are sheet edge dimensions
# (add_edge_dimension), which carry no per-dimension precision: they print at
# the drawing's document places, the ``decimals`` that build leaves
# new_project_drawing at its default.
EDGE_DIMENSION_PLACES = (
    inspect.signature(new_project_drawing).parameters["decimals"].default
)
_P = DRAWING_PRECISION["BlockProfile"]
_DEPTH_P = DRAWING_PRECISION["Block"]["Depth"]
_SELF = "draw_dt_pinion_pivot_block"
_GEOM = "dt_pinion_pivot_block_geometry"
_BUILD = "build_dt_pinion_pivot_block"
_NOTES = "dt_pinion_pivot_block_notes"
_FRAME = ("__frame__", (_BUILD, "build"), (_GEOM, "BLOCK_EAST"))
_UNIT = (_GEOM, "UNIT")


def _plane(axis: str, value: float) -> dict[str, Any]:
    return {"frame": "model", "axis": axis, "value": value}


part_metadata(
    model_sources=(
        (_BUILD, "build"),
        (_GEOM, "BLOCK_EAST"),
        (_GEOM, "BLOCK_WEST"),
        (_GEOM, "BORE_UP"),
        (_GEOM, "BLOCK_HEIGHT"),
        (_GEOM, "BLOCK_DEPTH"),
    ),
    precision_sources=(
        "DRAWING_PRECISION",
        "SCREW_HOLE_CALLOUT_PRECISION",
        (_GEOM, "BLOCK_DEPTH_PLACES"),
        (_SELF, "EDGE_DIMENSION_PLACES"),
        ("_drawing_edge_dimensions", "add_edge_dimension"),
        ("_drawing_common", "new_project_drawing"),
    ),
)
# The four ends and sides of the front view: the width 1.57 from the west end
# (FRONT_KEEP "BlockWidth"), the height .99 from the bottom ("BlockHeight").
requirement(
    "west_end",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), BLOCK_WEST),),
    requirements=("plane",),
    fields={"plane": (_plane("x", -BLOCK_WEST), (*_FRAME, (_GEOM, "BLOCK_WEST")))},
)
requirement(
    "east_end",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), BLOCK_EAST),),
    requirements=("width",),
    fields={
        "plane": (_plane("x", BLOCK_EAST), _FRAME),
        "width": (
            limits(BLOCK_WIDTH, _P["BlockWidth"], unit=UNIT),
            ((_GEOM, "BLOCK_WIDTH"), _UNIT, (_SELF, "FRONT_KEEP")),
        ),
        "width_nominal": (BLOCK_WIDTH, ((_GEOM, "BLOCK_WIDTH"),)),
        "width_from": ("west_end", ((_SELF, "FRONT_KEEP"),)),
    },
    precision={"width": _P["BlockWidth"]},
)
requirement(
    "bottom_face",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), BORE_UP),),
    requirements=("plane",),
    fields={"plane": (_plane("y", -BORE_UP), (*_FRAME, (_GEOM, "BORE_UP")))},
)
requirement(
    "top_face",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), BLOCK_TOP_Y),),
    requirements=("height",),
    fields={
        "plane": (_plane("y", BLOCK_TOP_Y), (*_FRAME, (_GEOM, "BLOCK_TOP_Y"))),
        "height": (
            limits(BLOCK_HEIGHT, _P["BlockHeight"], unit=UNIT),
            ((_GEOM, "BLOCK_HEIGHT"), _UNIT, (_SELF, "FRONT_KEEP")),
        ),
        "height_nominal": (BLOCK_HEIGHT, ((_GEOM, "BLOCK_HEIGHT"),)),
        "height_from": ("bottom_face", ((_SELF, "FRONT_KEEP"),)),
    },
    precision={"height": _P["BlockHeight"]},
)
# The broad faces: the depth .44 between them (RIGHT_KEEP "Depth").  The front
# face is the one the top view locates the hold-down holes from.
requirement(
    "back_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("plane",),
    fields={"plane": (_plane("z", 0.0), _FRAME)},
)
requirement(
    "front_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), BLOCK_DEPTH),),
    requirements=("depth",),
    fields={
        "plane": (_plane("z", BLOCK_DEPTH), (*_FRAME, (_GEOM, "BLOCK_DEPTH"))),
        "depth": (
            limits(BLOCK_DEPTH, _DEPTH_P, unit=UNIT),
            (
                (_GEOM, "BLOCK_DEPTH"),
                (_GEOM, "BLOCK_DEPTH_PLACES"),
                _UNIT,
                (_SELF, "RIGHT_KEEP"),
            ),
        ),
        "depth_nominal": (BLOCK_DEPTH, ((_GEOM, "BLOCK_DEPTH"),)),
        "depth_from": ("back_face", ((_SELF, "RIGHT_KEEP"),)),
    },
    precision={"depth": _DEPTH_P},
)
# The pivot bore at the .2510 reamer's size, REAM THRU, no band, the MHA-DT-19
# shaft its gauge (owner ruling 2026-11-24, fit audit question 12, option B);
# the lift bore drilled F THRU, the MHA-DT-17 rod turning freely in it (fit
# audit F26).  Each callout carries its acceptance by the mate (or the note it
# cites) under the size (DIMENSION_CALLOUTS), and Ra 63 (SURFACE_FINISHES:
# each turns its shaft).  The pivot bore's ``dia`` is the spec's ANALYSIS band
# (what the reamer is modelled to cut), not a requirement.  The pivot bore is
# the front view's one datum: 1.02 from the west end ("AnchorX") and .66 up
# from the bottom ("AnchorZ"); the lift bore stands .728 west of it
# ("LiftBoreX") and .085 above it ("LiftBoreCz"), at .XXX.
_CALLOUTS = ((_SELF, "DIMENSION_CALLOUTS"),)
_FINISH = ("SURFACE_FINISHES", ("_surface_finish", "MACHINED_UM"))
requirement(
    "pivot_bore",
    kind="hole",
    faces=(surface_finish_by_key(SURFACE_FINISHES, "pivot_bore").face,),
    # ``dia`` (the reamer's ANALYSIS band) stays a traveler requirement, as
    # #3492's MHA-PD-18 bore keeps it: prechips' drilled_block adapter refuses
    # a hole without one. The sheet prints the reamer's size and no band.
    requirements=(
        "dia",
        "thru",
        "process",
        "mate",
        "finish_ra",
        "x_from_west",
        "height",
    ),
    fields={
        "at": ([0.0, 0.0, BLOCK_DEPTH], (*_FRAME, (_GEOM, "BLOCK_DEPTH"))),
        "axis": ((0.0, 0.0, -1.0), _FRAME),
        "dia": (
            limits(PIVOT_BORE_DIA, _P["PivotBoreDia"], PIVOT_BORE_BAND, unit=UNIT),
            ((_GEOM, "PIVOT_BORE_DIA"), "PIVOT_BORE_BAND", _UNIT, (_SELF, "FRONT_KEEP")),
        ),
        "nominal_dia": (PIVOT_BORE_DIA, ((_GEOM, "PIVOT_BORE_DIA"),)),
        "process": ("ream", _CALLOUTS),
        "thru": (True, _CALLOUTS),
        "callout": (DIMENSION_CALLOUTS["PivotBoreDia"], _CALLOUTS),
        "mate": (PIVOT_SHAFT_MATE[0], _CALLOUTS),
        "mates": (" ".join(PIVOT_SHAFT_MATE), ("PIVOT_SHAFT_MATE",)),
        "finish_ra": (MACHINED_UM, _FINISH),
        "x_from_west": (
            limits(BLOCK_WEST, _P["AnchorX"], unit=UNIT),
            ((_GEOM, "BLOCK_WEST"), _UNIT, (_SELF, "FRONT_KEEP")),
        ),
        "x_from_west_nominal": (BLOCK_WEST, ((_GEOM, "BLOCK_WEST"),)),
        "x_from_west_from": ("west_end", ((_SELF, "FRONT_KEEP"),)),
        "height": (
            limits(BORE_UP, _P["AnchorZ"], unit=UNIT),
            ((_GEOM, "BORE_UP"), _UNIT, (_SELF, "FRONT_KEEP")),
        ),
        "height_nominal": (BORE_UP, ((_GEOM, "BORE_UP"),)),
        "height_from": ("bottom_face", ((_SELF, "FRONT_KEEP"),)),
    },
    precision={
        "dia": _P["PivotBoreDia"],
        "x_from_west": _P["AnchorX"],
        "height": _P["AnchorZ"],
    },
)
requirement(
    "lift_bore",
    kind="hole",
    faces=(surface_finish_by_key(SURFACE_FINISHES, "lift_bore").face,),
    requirements=("dia", "thru", "process", "mate", "finish_ra", "spacing", "rise"),
    fields={
        "at": (
            [-LIFT_BORE_SPACING, LIFT_BORE_RISE, BLOCK_DEPTH],
            (
                (_GEOM, "LIFT_BORE_SPACING"),
                (_GEOM, "LIFT_BORE_RISE"),
                (_GEOM, "BLOCK_DEPTH"),
            ),
        ),
        "axis": ((0.0, 0.0, -1.0), _FRAME),
        "dia": (
            drilled_limits(LIFT_BORE_DIA, _P["LiftBoreDia"], unit=UNIT),
            ((_GEOM, "LIFT_BORE_DIA"), "LIFT_BORE_BAND", _UNIT, (_SELF, "FRONT_KEEP")),
        ),
        "nominal_dia": (LIFT_BORE_DIA, ((_GEOM, "LIFT_BORE_DIA"),)),
        "process": ("drill", _CALLOUTS),
        "drill": ("F", _CALLOUTS),
        "thru": (True, _CALLOUTS),
        "callout": (DIMENSION_CALLOUTS["LiftBoreDia"], _CALLOUTS),
        "mate": (LIFT_ROD_MATE[0], _CALLOUTS),
        "mates": (" ".join(LIFT_ROD_MATE), ("LIFT_ROD_MATE",)),
        "note": (
            LIFT_BORE_NOTE_TEXT,
            ((_NOTES, "LIFT_BORE_NOTE_TEXT"), (_NOTES, "DRAWING_NOTES")),
        ),
        "finish_ra": (MACHINED_UM, _FINISH),
        "spacing": (
            limits(LIFT_BORE_SPACING, _P["LiftBoreX"], unit=UNIT),
            ((_GEOM, "LIFT_BORE_SPACING"), _UNIT, (_SELF, "FRONT_KEEP")),
        ),
        "spacing_nominal": (LIFT_BORE_SPACING, ((_GEOM, "LIFT_BORE_SPACING"),)),
        "spacing_from": ("pivot_bore", ((_SELF, "PIVOT_ORIGIN_DIMENSIONS"),)),
        "spacing_axis": ("x", ((_SELF, "PIVOT_ORIGIN_DIMENSIONS"),)),
        "rise": (
            limits(LIFT_BORE_RISE, _P["LiftBoreCz"], unit=UNIT),
            ((_GEOM, "LIFT_BORE_RISE"), _UNIT, (_SELF, "FRONT_KEEP")),
        ),
        "rise_nominal": (LIFT_BORE_RISE, ((_GEOM, "LIFT_BORE_RISE"),)),
        "rise_from": ("pivot_bore", ((_SELF, "PIVOT_ORIGIN_DIMENSIONS"),)),
        "rise_axis": ("y", ((_SELF, "PIVOT_ORIGIN_DIMENSIONS"),)),
    },
    precision={
        "dia": _P["LiftBoreDia"],
        "spacing": _P["LiftBoreX"],
        "rise": _P["LiftBoreCz"],
    },
)
# The two #8 normal-clearance hold-down holes: one native callout (2X Ø.196
# THRU ALL, its drill at SCREW_HOLE_CALLOUT_PRECISION's .XXX), each located
# along X from the west end (.69, 1.35) and both by the one .22 from the front
# face (build's top-view edge dimensions).  Through-all from the top face to
# the base seat; the base's #8-32 seats are transferred through them at
# assembly (that base's own sheet), not by this part.
_SCREW_DIA = (
    drilled_limits(SCREW_HOLE_DIA, SCREW_HOLE_CALLOUT_PRECISION, unit=UNIT),
    (
        (_GEOM, "SCREW_HOLE_DIA"),
        _UNIT,
        "SCREW_HOLE_CALLOUT_PRECISION",
        (_SELF, "build"),
    ),
)
_SCREW_THRU = ((_GEOM, "SCREW_HOLE_SPEC"), (_BUILD, "build"), (_SELF, "build"))
_EDGE_DIMENSIONS = ((_SELF, "build"), (_SELF, "EDGE_DIMENSION_PLACES"))
for _name, _sign in (("west_hold_down", -1.0), ("east_hold_down", 1.0)):
    _station = BLOCK_WEST + _sign * SCREW_HALF_SPACING
    requirement(
        _name,
        kind="hole",
        faces=(CylinderFace(SCREW_HOLE_DIA, contains_x_mm=_sign * SCREW_HALF_SPACING),),
        requirements=("dia", "thru", "x_from_west", "z_from_front"),
        fields={
            "at": (
                [_sign * SCREW_HALF_SPACING, BLOCK_TOP_Y, BLOCK_DEPTH / 2.0],
                (
                    (_GEOM, "SCREW_HALF_SPACING"),
                    (_GEOM, "BLOCK_TOP_Y"),
                    (_GEOM, "BLOCK_DEPTH"),
                ),
            ),
            "axis": ((0.0, -1.0, 0.0), _SCREW_THRU),
            "dia": _SCREW_DIA,
            "nominal_dia": (SCREW_HOLE_DIA, ((_GEOM, "SCREW_HOLE_DIA"),)),
            "process": ("drill", _SCREW_THRU),
            "thru": (True, _SCREW_THRU),
            "x_from_west": (
                limits(_station, EDGE_DIMENSION_PLACES, unit=UNIT),
                (
                    (_GEOM, "BLOCK_WEST"),
                    (_GEOM, "SCREW_HALF_SPACING"),
                    _UNIT,
                    *_EDGE_DIMENSIONS,
                ),
            ),
            "x_from_west_nominal": (
                _station,
                ((_GEOM, "BLOCK_WEST"), (_GEOM, "SCREW_HALF_SPACING")),
            ),
            "x_from_west_from": ("west_end", _EDGE_DIMENSIONS),
            "z_from_front": (
                limits(BLOCK_DEPTH / 2.0, EDGE_DIMENSION_PLACES, unit=UNIT),
                ((_GEOM, "BLOCK_DEPTH"), _UNIT, *_EDGE_DIMENSIONS),
            ),
            "z_from_front_nominal": (BLOCK_DEPTH / 2.0, ((_GEOM, "BLOCK_DEPTH"),)),
            "z_from_front_from": ("front_face", _EDGE_DIMENSIONS),
        },
        precision={
            "dia": SCREW_HOLE_CALLOUT_PRECISION,
            "x_from_west": EDGE_DIMENSION_PLACES,
            "z_from_front": EDGE_DIMENSION_PLACES,
        },
    )


def _arrowheads(annotation: Any, label: str) -> list[tuple[tuple[float, float], int]]:
    """Each arrowhead's tip on the sheet and its style (draw_mg_wheel_axle)."""
    data = annotation.GetDisplayData()
    if data is None:
        raise RuntimeError(f"{label} has no display data")
    data = _early_bound(data, "IDisplayData")
    heads = []
    for index in range(int(data.GetArrowHeadCount() or 0)):
        values = [float(value) for value in (data.GetArrowHeadAtIndex2(index) or ())]
        if len(values) < 9:
            raise RuntimeError(f"{label} arrowhead {index} is incomplete: {values!r}")
        heads.append(((values[0], values[1]), round(values[8])))
    if len(heads) != 2:
        raise RuntimeError(f"{label} has {len(heads)} arrowheads, expected 2")
    return heads


def _set_dimension_origin(
    adapter: Any, annotation: Any, *, origin: float, axis: int, label: str
) -> None:
    """Put the dimension-origin circle on the arrowhead nearest ``origin``
    along sheet ``axis``, read back from the ink (draw_mg_magnifying_vertical_rod)."""
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")

    def offset(head: tuple[tuple[float, float], int]) -> float:
        return abs(head[0][axis] - origin)

    heads = _arrowheads(annotation, label)
    near = min(range(2), key=lambda index: offset(heads[index]))
    styles = [_CLOSED_ARROWHEAD, _CLOSED_ARROWHEAD]
    styles[near] = _ORIGIN_ARROWHEAD
    for attempt in (styles, styles[::-1]):
        if not display.SetArrowHeadStyle2(False, *attempt):
            raise RuntimeError(f"failed to set the {label} arrowhead styles")
        rebuild_drawing(adapter, label=f"{label} dimension origin")
        heads = _arrowheads(annotation, label)
        at_origin = min(heads, key=offset)
        far = max(heads, key=offset)
        if (at_origin[1], far[1]) == (_ORIGIN_ARROWHEAD, _CLOSED_ARROWHEAD):
            return
    raise RuntimeError(f"{label} origin circle is not at the pivot bore: {heads!r}")


def _named(adapter: Any, annotations: list[Any], name: str) -> Any:
    matches = [a for a in annotations if dimension_name(adapter, a) == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one pinion-pivot-block {name} dimension")
    return matches[0]


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-pivot-block source", adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    drawing_model, sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Pivot Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion pivot block; manufacturing drawing; pivot bores",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(3, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(3, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(3, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    # Every hole here is a standard drill or ream fully defined by its
    # callout, so no view carries hidden lines (drawing-guidelines.md rule 9 (show internal shape in solid lines); Fable review r4).
    for view in (front, top, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    # Right view: the stock section carries only the block depth.
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    # Top view: the hold-downs are located by sheet dimensions below.
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_callouts(
        adapter,
        [*front_annotations, *top_annotations, *right_annotations],
        DIMENSION_CALLOUTS,
    )
    for name, axis in PIVOT_ORIGIN_DIMENSIONS.items():
        _set_dimension_origin(
            adapter,
            _named(adapter, front_annotations, name),
            origin=PIVOT_SHEET_XY[axis],
            axis=axis,
            label=f"pinion pivot block {name}",
        )

    for view, label in ((front, "front"), (top, "top")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    # Hold-down holes: ordinary coordinates baselined from the WEST end, the
    # top view's one datum (the pivot bore does not show in this view).
    # drawing-guidelines.md rule 5 (avoid excessive GD&T): a block carries no
    # frames, datums or basic boxes.  Both drills sit at exact mid-depth, so
    # one depth coordinate from the broad face locates the pair.
    west_end = (_front_x(-BLOCK_WEST), TOP_CENTER[1])
    for x_mm, text_y, label in (
        (-SCREW_HALF_SPACING, 0.248, "west hold-down station"),
        (SCREW_HALF_SPACING, 0.258, "east hold-down station"),
    ):
        add_edge_dimension(
            adapter,
            top,
            p0=west_end,
            p1=(_front_x(x_mm), TOP_CENTER[1] + SCREW_R_SHEET),
            text_xy=((west_end[0] + _front_x(x_mm)) / 2.0, text_y),
            label=label,
            orientation="horizontal",
        )
    add_edge_dimension(
        adapter,
        top,
        p0=(
            _front_x(-SCREW_HALF_SPACING - 5.0),
            TOP_CENTER[1] - BLOCK_DEPTH * SHEET_SCALE[0] / 2000.0,
        ),
        p1=(_front_x(-SCREW_HALF_SPACING), TOP_CENTER[1] - SCREW_R_SHEET),
        text_xy=(0.062, 0.212),
        label="hold-down depth location",
    )
    # The size callout rides the EAST hole, from the clear sheet right of the
    # top view (render r1: led from the left margin it crossed the block).
    east_screw_edge = (
        _front_x(SCREW_HALF_SPACING),
        TOP_CENTER[1] + SCREW_R_SHEET,
    )
    # Size first, then depth (rule 26): no process prefix.
    screw_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=east_screw_edge,
        callout_xy=(0.245, 0.250),
        label="hold-down screw hole",
    )
    # This render-time precision write is the declared exception RV-01 in
    # cad/config/parts/dt-pinion-pivot-block.yaml (Owner ruling
    # 2026-11-08 (Pedro), #2144 item 1.2): a part-authored precision does not
    # reach the callout (run 20261102T230110877Z).
    set_hole_callout_precision(
        screw_callout, {"hw-diam": SCREW_HOLE_CALLOUT_PRECISION}, label="hold-down screw hole"
    )
    # Anchored on the bore rim at ~30 deg: the pivot centre's AnchorZ witness
    # leaves the rim at 0 deg and LiftBoreX's at 90 deg, and the diameter
    # leader climbs at ~70 deg, so 30 deg is the clear sector.  Fable review
    # r4 read the full-size symbol, sitting on the top edge, as the top face's:
    # at routine size and lifted 11 mm clear of that edge, its leader leaves
    # the block through the top face (x ~0.193, inside the 0.200 corner, so
    # it cannot cross BlockHeight's extension line) and the symbol stays
    # under the PivotBoreDia callout.
    pivot_right_edge = (
        _front_x(0.0) + PIVOT_BORE_R_SHEET * 0.866,
        _front_y(0.0) + PIVOT_BORE_R_SHEET * 0.5,
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=pivot_right_edge,
        symbol_xy=PIVOT_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_bore"),
        label="pivot bore finish",
        char_height=0.0025,
    )
    # The lift bore runs MHA-DT-17 (drawing-guidelines.md rule 6 (roughness
    # symbols only where a surface runs, slides or locates)).  Its DRILL
    # callout leaves the rim upper-left, its centre lines leave at 180 and
    # 270 deg, and the lift-bore rise's pivot-centre witness cuts the rim at
    # ~223 and ~317 deg, so the leader lands at 250 deg, under that witness
    # and left of the 270 deg centre line; the symbol sits in the empty band
    # left of the block, under the lift-bore rise and above the length
    # dimensions.
    lift_lower_edge = (
        _front_x(-LIFT_BORE_SPACING) - LIFT_BORE_R_SHEET * 0.342,
        _front_y(LIFT_BORE_RISE) - LIFT_BORE_R_SHEET * 0.940,
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=lift_lower_edge,
        symbol_xy=(0.048, 0.118),
        control=surface_finish_by_key(SURFACE_FINISHES, "lift_bore"),
        label="lift bore finish",
        char_height=0.0025,
    )

    # The sheet's one numbered note is the lift-bore stations' reason, flagged
    # from that bore's callout; the isometric's scale override is labelled.
    if add_note(adapter, LIFT_BORE_NOTE, *LIFT_BORE_NOTE_XY) is None:
        raise RuntimeError("failed to add the lift-bore station note")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Pivot Block Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
