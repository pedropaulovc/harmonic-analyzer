r"""Create the curated machinist drawing for the pinion pivot block.

The SLDPRT remains authoritative.  This recipe supplies only the block's
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The sheet runs at 3:1 (the block is 36 x 18.75 x 12); the isometric carries an
explicit 2:1 override so it stays clear of the title block.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
mounting block carries no datums, frames, basics or roughness symbols; the
ream and bore-height bands ride the model dimensions and the hole callout says
the drill.  Every hole axis is located from a face (rule 7): the lift bore
from the left end and the base, the pivot bore from the lift bore and the
base, the hold-down pair from the left end and the broad face.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_pivot_block.py pinion-pivot-block
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pinion_pivot_block_spec import (
    BLOCK_DEPTH,
    BLOCK_WIDTH,
    BORE_DIA,
    BORE_HALF_SPACING,
    BORE_UP,
    FRONT_BBOX_CY,
    LIFT_BORE_FROM_END,
    LIFT_BORE_RISE,
    SCREW_FROM_END,
    SCREW_HALF_SPACING,
    SCREW_HOLE_DIA,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_pivot_block"]
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

# Sheet layout (meters).  The front view's model bbox runs -18..18 in X and
# -12..6.75 in Y; at 3:1 the view is 108 x 56 mm.  Third angle: the top view
# (block seen from above, carrying the two hold-down holes) sits ABOVE the
# front view; the right view (16 x 12 stock section) sits to its right.
FRONT_CENTER = (0.135, 0.130)
TOP_CENTER = (0.135, 0.220)
RIGHT_CENTER = (0.280, 0.130)
ISO_CENTER = (0.360, 0.225)


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front/top views (3:1, bbox-centred)."""
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (3:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


SCREW_R_SHEET = SCREW_HOLE_DIA * SHEET_SCALE[0] / 2000.0
BORE_R_SHEET = BORE_DIA * SHEET_SCALE[0] / 2000.0

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  Heights: the pivot bore from the base on the RIGHT (next to the
# block height), the lift bore's rise above the pivot on the LEFT; the two
# bore diameters lead to the clear corners; the block width is the outermost
# dimension under the view.  The bores' longitudinal stations are drawing
# edge dimensions from the left end (below the view, inboard of the width).
FRONT_KEEP = {
    "BlockWidth": (0.135, 0.080),
    "BlockHeight": (0.212, 0.130),
    "AnchorZ": (0.200, _front_y(-BORE_UP / 2.0)),
    "LiftBoreCz": (0.070, _front_y(LIFT_BORE_RISE / 2.0)),
    "PivotBoreDia": (0.235, 0.205),
    # Below the top view's outline (its 4.50 station hangs to ~0.188).
    "LiftBoreDia": (0.055, 0.176),
}
RIGHT_KEEP = {"Depth": (0.280, 0.168)}
TOP_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS = {
    "PivotBoreDia": "REAM THRU (1/4 IN)",
    "LiftBoreDia": "REAM THRU (1/4 IN)",
}
FRONT_DIAMETERS = ("PivotBoreDia", "LiftBoreDia")
STATION_TEXT_Y = 0.090
LIFT_STATION_TEXT_XY = (_front_x(-BLOCK_WIDTH / 2.0 + LIFT_BORE_FROM_END / 2.0), STATION_TEXT_Y)
BORE_SPACING_TEXT_XY = (_front_x(0.0), STATION_TEXT_Y)
BORE_SPACING_DECIMALS = 3  # .XXX: the strap swings on this pair
HOLD_DOWN_STATION_TEXT_XY = (_front_x(-BLOCK_WIDTH / 2.0 + SCREW_FROM_END / 2.0), 0.192)

_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
_DO_NOT_CHANGE_PRECISION = -1  # swDimensionPrecisionSettings_e


def _leaders_to_circumference(
    adapter: Any, annotations: list[Any], names: tuple[str, ...], *, label: str
) -> None:
    """End each named diameter leader at the nearest circumference.

    SolidWorks' default runs a diameter dimension line across the circle
    through its centre and its centre mark; with the arrows OUTSIDE the leader
    stops at the rim it names (drawing-simplicity-policy.md rule 7: never
    through a bore).
    """
    remaining = set(names)
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _sw_type_info.early_bound_or_flag(
            annotation.GetSpecificAnnotation(), "IDisplayDimension", "ArrowSide"
        )
        display.ArrowSide = _ARROWS_OUTSIDE
        if int(display.ArrowSide) != _ARROWS_OUTSIDE:
            raise RuntimeError(f"{label}: {name} arrows did not move outside")
        remaining.discard(name)
    if remaining:
        raise RuntimeError(f"{label}: diameter dimensions not found: {sorted(remaining)}")
    adapter.currentModel.EditRebuild3()


def _set_display_precision(adapter: Any, display: Any, digits: int, *, label: str) -> None:
    """Override one drawing-native dimension's primary decimal places.

    Three decimals put the dimension in the title block's .XXX class -- the
    way a drawing edge dimension (no model band to ride) is tightened.
    """
    display = _sw_type_info.early_bound_or_flag(
        display, "IDisplayDimension", "SetPrecision3", "GetPrimaryPrecision2"
    )
    adapter._attempt(
        lambda: display.SetPrecision3(
            digits,
            _DO_NOT_CHANGE_PRECISION,
            _DO_NOT_CHANGE_PRECISION,
            _DO_NOT_CHANGE_PRECISION,
        )
    )
    applied = adapter._attempt(lambda: display.GetPrimaryPrecision2())
    if applied != digits:
        raise RuntimeError(
            f"{label}: precision override did not take (requested {digits}, got {applied})"
        )
    adapter.currentModel.EditRebuild3()


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
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
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
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines ON in every orthographic view: the top view exposes the two
    # vertical hold-down drills, the right view both Z-bores edge-on.
    for view in (front, top, right):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    # Right view: the 16 x 12 stock section carries only the block depth.
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    # Top view: the hold-down pair is located by edge dimensions below.
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_callouts(
        adapter,
        [*front_annotations, *top_annotations, *right_annotations],
        DIMENSION_CALLOUTS,
    )
    _leaders_to_circumference(
        adapter, front_annotations, FRONT_DIAMETERS, label="front diameters"
    )

    for view, label in ((front, "front"), (top, "top")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    # Bore stations, one origin (the left end face): the lift bore from the
    # end, then the pivot bore from the lift bore -- the pair the strap
    # swings on, so it prints in the .XXX class.  The circular picks snap
    # both dimensions to the bore CENTRES.
    lift_bottom_rim = (
        _front_x(-BORE_HALF_SPACING),
        _front_y(LIFT_BORE_RISE) - BORE_R_SHEET,
    )
    lift_station = add_edge_dimension(
        adapter,
        front,
        p0=(_front_x(-BLOCK_WIDTH / 2.0), _front_y(-BORE_UP / 2.0)),
        p1=lift_bottom_rim,
        text_xy=LIFT_STATION_TEXT_XY,
        label="left end to lift bore axis",
        orientation="horizontal",
    )
    set_arc_endpoints_to_center(adapter, lift_station, label="left end to lift bore axis")
    bore_spacing = add_edge_dimension(
        adapter,
        front,
        p0=lift_bottom_rim,
        p1=(_front_x(BORE_HALF_SPACING), _front_y(0.0) - BORE_R_SHEET),
        text_xy=BORE_SPACING_TEXT_XY,
        label="lift bore axis to pivot bore axis",
        orientation="horizontal",
    )
    set_arc_endpoints_to_center(
        adapter, bore_spacing, label="lift bore axis to pivot bore axis"
    )
    _set_display_precision(
        adapter,
        bore_spacing,
        BORE_SPACING_DECIMALS,
        label="lift bore axis to pivot bore axis",
    )

    # Hold-down pair: the west hole from the left end (the top view's edge),
    # then the 27 spacing across the two hole circles; both sit at mid-depth
    # so the pick heights are identical.
    west_screw_rim = (
        _front_x(-SCREW_HALF_SPACING) - SCREW_R_SHEET,
        TOP_CENTER[1],
    )
    hold_down_station = add_edge_dimension(
        adapter,
        top,
        p0=(_front_x(-BLOCK_WIDTH / 2.0), TOP_CENTER[1] - 0.008),
        p1=west_screw_rim,
        text_xy=HOLD_DOWN_STATION_TEXT_XY,
        label="left end to hold-down hole axis",
        orientation="horizontal",
    )
    set_arc_endpoints_to_center(
        adapter, hold_down_station, label="left end to hold-down hole axis"
    )
    add_edge_dimension(
        adapter,
        top,
        p0=(_front_x(-SCREW_HALF_SPACING), TOP_CENTER[1] + SCREW_R_SHEET),
        p1=(_front_x(SCREW_HALF_SPACING), TOP_CENTER[1] + SCREW_R_SHEET),
        text_xy=(TOP_CENTER[0], 0.248),
        label="hold-down screw spacing",
    )

    # Hold-down pattern across the depth: both drills sit at mid-depth, so one
    # 6 from the broad face locates the pair.
    add_edge_dimension(
        adapter,
        top,
        p0=(_front_x(-17.0), TOP_CENTER[1] - BLOCK_DEPTH * SHEET_SCALE[0] / 2000.0),
        p1=(_front_x(-SCREW_HALF_SPACING), TOP_CENTER[1] - SCREW_R_SHEET),
        text_xy=(0.062, 0.212),
        label="hold-down depth location",
    )

    west_screw_edge = (
        _front_x(-SCREW_HALF_SPACING),
        TOP_CENTER[1] + SCREW_R_SHEET,
    )
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=west_screw_edge,
        callout_xy=(0.052, 0.252),
        label="hold-down screw hole",
        process="#19 DRILL",
    )

    # 0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127) the layout gate measures against,
    # which the re-centred frame rule now matches (~0.0126); 0.020 clears both.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.335, 0.180)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Pivot Block Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
