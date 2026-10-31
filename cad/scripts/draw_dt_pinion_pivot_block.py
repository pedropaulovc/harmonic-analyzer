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
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
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
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from dt_pinion_pivot_block_spec import (
    BLOCK_DEPTH,
    BLOCK_HEIGHT,
    BLOCK_WEST,
    BLOCK_WIDTH as BLOCK_WIDTH,
    BORE_CALLOUTS,
    BORE_DIA,
    BORE_UP,
    FRONT_BBOX_CX,
    FRONT_BBOX_CY,
    LIFT_BORE_RISE,
    LIFT_BORE_SPACING,
    SCREW_HALF_SPACING,
    SCREW_HOLE_CALLOUT_PRECISION,
    SCREW_HOLE_DIA,
    SURFACE_FINISHES,
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


BORE_R_SHEET = BORE_DIA * SHEET_SCALE[0] / 2000.0
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
    # (rule 14's list of defects is complete and does not include it).
    "LiftBoreCz": (
        _front_x(-BLOCK_WEST) - 0.010,
        _front_y(LIFT_BORE_RISE / 2.0),
    ),
    # Every horizontal/vertical witness from the pivot centre crosses its rim
    # at 0/90/180/270 deg.  The leader runs to the NEAR end of the text's
    # shoulder (the bottom line's), so the text sits up and right of the bore
    # and the leader climbs at ~65 deg, clear of the Ra symbol's ~30 deg
    # sector.  The six-line callout (limits, size, THRU - REAM and its mate)
    # is centred here, so its bottom stays over the Ra symbol and its left
    # edge right of the top view.
    "PivotBoreDia": (0.224, 0.205),
    # Up-left of the lift bore, in the clear band left of the top view and
    # above the lift-bore rise.
    "LiftBoreDia": (0.045, 0.182),
}
RIGHT_KEEP = {"Depth": (RIGHT_CENTER[0], FRONT_TOP_Y + 0.00925)}
TOP_KEEP = {}
DIMENSION_CALLOUTS = dict(BORE_CALLOUTS)
# One line ABOVE the lift-bore spacing (a multi-line above-callout does not
# print): machinist review r2 (#1014) asked the sheet to say why the
# bore-to-bore spacing is held from the pivot bore instead of the edges -- the
# lift rod's eccentric cam must clear the strap's pivot end cap (X) and hover
# over the follower stud at park (Y) (dt_pinion_pivot_block_geometry).
ABOVE_CALLOUTS = {"LiftBoreX": "SETS LIFT CAM CLEARANCE AND PARK GAP"}
# Front-view locations that start at the pivot bore: name -> the sheet axis
# each measures along (0 = x, 1 = y).
PIVOT_ORIGIN_DIMENSIONS = {"AnchorX": 0, "LiftBoreX": 0, "AnchorZ": 1, "LiftBoreCz": 1}
_ORIGIN_ARROWHEAD = 4  # swArrowStyle_e.swORIGIN_ARROWHEAD (no-fill circle)
_CLOSED_ARROWHEAD = 1  # swArrowStyle_e.swCLOSED_ARROWHEAD


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


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-pivot-block source", await adapter.open_model(str(SOURCE)))
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
    set_dimension_callouts(adapter, front_annotations, ABOVE_CALLOUTS, location="above")
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
    screw_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=east_screw_edge,
        callout_xy=(0.245, 0.250),
        label="hold-down screw hole",
        process="DRILL",
    )
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
        _front_x(0.0) + BORE_R_SHEET * 0.866,
        _front_y(0.0) + BORE_R_SHEET * 0.5,
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
    # symbols only where a surface runs, slides or locates)).  Its REAM
    # callout leaves the rim upper-left, its centre lines leave at 180 and
    # 270 deg, and the lift-bore rise's pivot-centre witness cuts the rim at
    # ~223 and ~317 deg, so the leader lands at 250 deg, under that witness
    # and left of the 270 deg centre line; the symbol sits in the empty band
    # left of the block, under the lift-bore rise and above the length
    # dimensions.
    lift_lower_edge = (
        _front_x(-LIFT_BORE_SPACING) - BORE_R_SHEET * 0.342,
        _front_y(LIFT_BORE_RISE) - BORE_R_SHEET * 0.940,
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

    # The sheet carries no general notes (BORE_CALLOUTS); only the isometric's
    # scale override is labelled.
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
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
