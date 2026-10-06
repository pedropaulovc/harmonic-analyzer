r"""Create the curated machinist drawing for the magnifying-lever clamp block.

A prismatic brass block (20 x 26 x 12) carrying two skew slip bores -- the lever
bore Ø6.2 along the depth, the vertical-rod bore Ø5.2 along the height -- and a
#4-40 thumb-screw tapped from the top into the lever bore.  Every face is flat,
so the block dimensions ride the auto-imported profile marks (FRONT: block +
lever bore; TOP: rod bore) with the depth added across the right-view section.

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_magnifying_clamp.py magnifying-clamp
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from mg_magnifying_clamp_spec import GEOMETRIC_TOLERANCES_MM

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_annotation_extent import (
    annotation_ink,
    assert_annotation_reservations,
    place_annotation_in_field,
    require_clear,
)
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    dimension_name,
    rebuild_drawing,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME, DRAWING_TEMPLATES
from _surface_finish import surface_finish_by_key
from mg_magnifying_clamp_spec import (
    BLOCK_DEPTH,
    BLOCK_HEIGHT,
    BLOCK_WIDTH,
    LEVER_BORE_DIA,
    LEVER_BORE_Y,
    ROD_BORE_X,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["mg_magnifying_clamp"]
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

SHEET_SCALE = (4.0, 1.0)

FRONT_CENTER = (0.120, 0.120)
TOP_CENTER = (0.120, 0.215)
# Right view pulled left of the title block (x>~0.258, y<~0.070): the 48x104 mm
# section at x=0.250 clipped the title block's top-left corner (layout audit).
RIGHT_CENTER = (0.225, 0.120)
ISO_CENTER = (0.350, 0.215)


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + (model_x_mm) * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - BLOCK_HEIGHT / 2.0) * SHEET_SCALE[0] / 1000.0


FRONT_KEEP = {
    # The overall height is outside the front view on the right. Its old
    # left-hand witness crossed the lever-bore callout.
    "Width": (FRONT_CENTER[0], _front_y(BLOCK_HEIGHT) + 0.014),
    "Height": (FRONT_CENTER[0] + BLOCK_WIDTH * 2.0 / 1000.0 + 0.032, FRONT_CENTER[1]),
    "LeverBoreYDim": (
        FRONT_CENTER[0] + BLOCK_WIDTH * 2.0 / 1000.0 + 0.020,
        _front_y(LEVER_BORE_Y / 2.0),
    ),
    "LeverBoreDiaDim": (0.048, _front_y(LEVER_BORE_Y) - 0.004),
}
TOP_KEEP = {
    # Put the station above the plan: its former long witnesses crossed the
    # front width and the native cosmetic-thread note.
    "RodBoreXDim": (_front_x(ROD_BORE_X / 2.0), TOP_CENTER[1] + 0.038),
    "RodBoreDiaDim": (0.200, TOP_CENTER[1] + 0.032),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}

DIMENSION_CALLOUTS = {
    "LeverBoreDiaDim": "THRU - SLIP FIT Ø6 ROD",
    "RodBoreDiaDim": "THRU - SLIP FIT Ø5 ROD",
}

RIGHT_HALF_Z = BLOCK_DEPTH / 2.0 * SHEET_SCALE[0] / 1000.0
RIGHT_HALF_Y = BLOCK_HEIGHT / 2.0 * SHEET_SCALE[0] / 1000.0

# Text reservations are sheet-space drafting lanes, not model dimensions.
# The settled check includes the native witnesses, leaders and centre marks.
TEXT_FIELDS = {
    "Width": (0.104, 0.181, 0.138, 0.190),
    "Height": (0.180, 0.101, 0.200, 0.137),
    "LeverBoreYDim": (0.167, 0.090, 0.187, 0.121),
    "LeverBoreDiaDim": (0.019, 0.130, 0.077, 0.158),
    "RodBoreXDim": (0.119, 0.246, 0.147, 0.264),
    "RodBoreDiaDim": (0.174, 0.239, 0.257, 0.263),
    "thumb-screw thread": (0.023, 0.245, 0.080, 0.264),
    "block depth": (0.201, 0.214, 0.249, 0.235),
    "datum A": (0.264, 0.082, 0.286, 0.104),
    "top-face parallelism": (0.266, 0.184, 0.306, 0.207),
    "lever bore finish": (0.155, 0.147, 0.197, 0.171),
    "manufacturing notes": (0.018, 0.024, 0.212, 0.064),
}


def _assert_readability(
    adapter: Any, allocated: dict[str, Any], views: tuple[Any, ...], char_height: float
) -> None:
    """Re-read the exported field against every surviving native annotation."""
    annotations = dict(allocated)
    allocated_names = {
        str(_early_bound(item, "IAnnotation").GetName()) for item in allocated.values()
    }
    for index, view in enumerate(views):
        for raw in _early_bound(view, "IView").GetAnnotations() or ():
            annotation = _early_bound(raw, "IAnnotation")
            if int(annotation.Visible) in (2, 3):
                continue
            name = str(annotation.GetName())
            if name not in allocated_names:
                annotations[f"view {index}: {name}"] = annotation
    inks = assert_annotation_reservations(
        adapter,
        annotations,
        TEXT_FIELDS,
        text_heights={"lever bore finish": char_height, "Width": char_height},
        check_own_lines=tuple(FRONT_KEEP) + tuple(TOP_KEEP) + ("block depth",),
    )
    template = DRAWING_TEMPLATES[SPEC.layout]
    keepout = (template.title_block_left_m, 0.0, template.width_m, template.title_block_top_m)
    for label in TEXT_FIELDS:
        ink = inks[label]
        require_clear(label, ink.text, {"title block": keepout})
        for line in ink.lines:
            box = line.box()
            require_clear(label, (box.xmin, box.ymin, box.xmax, box.ymax), {"title block": keepout})


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-clamp source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Magnifying Clamp Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying clamp; brass block; skew slip bores",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(4, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    for view in (right, iso):
        set_hidden_lines_removed(adapter, view)
    # Front carries the vertical-rod + screw hidden bores; top exposes the rod
    # bore + the tapped screw hole crossing the depth.
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    set_dimension_callouts(
        adapter, [*front_annotations, *top_annotations], DIMENSION_CALLOUTS
    )
    allocated = {
        dimension_name(adapter, annotation): annotation
        for annotation in [*front_annotations, *top_annotations]
    }
    heights = annotation_ink(adapter, allocated["Width"], label="ordinary width text").heights
    char_height = heights[0]
    if any(abs(height - char_height) > 1e-7 for height in heights):
        raise RuntimeError("clamp ordinary dimension has mixed native text heights")
    for view, label in ((front, "front"), (top, "top")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    # Block depth (12): dimension the right view's flat front/back silhouette
    # faces (a prism section, so the edges are pickable).
    depth = add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0] - RIGHT_HALF_Z, RIGHT_CENTER[1]),
        p1=(RIGHT_CENTER[0] + RIGHT_HALF_Z, RIGHT_CENTER[1]),
        text_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + RIGHT_HALF_Y + 0.050),
        label="block-depth overall",
    )

    # The imported native cosmetic-thread note remains associated with the
    # top-view tapped hole. Give it its own above-left lane.
    thread_notes = [
        _early_bound(raw, "IAnnotation")
        for raw in _early_bound(top, "IView").GetAnnotations() or ()
        if int(_early_bound(raw, "IAnnotation").GetType()) == 6
        and int(_early_bound(raw, "IAnnotation").Visible) not in (2, 3)
    ]
    if len(thread_notes) != 1:
        raise RuntimeError("clamp top view has no unique native thumb-screw note")

    # Datum A = the block bottom seat (front view); Ra 1.6 on the lever bore (the
    # functional sliding surface), tagged on its rim.
    # Keep both the datum box and its complete leader above the title block.
    datum = add_datum_feature(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] + 0.010, _front_y(0.0)),
        symbol_xy=(RIGHT_CENTER[0] + 0.049, _front_y(0.0) + 0.024),
        datum="A",
        label="block bottom seat",
    )
    parallelism = add_feature_control_frame(
        adapter,
        # The frame is right of the depth witnesses, so neither its text nor
        # the frame can be cut by the new above-view overall depth.
        right,
        edge_xy=(RIGHT_CENTER[0] + 0.012, _front_y(BLOCK_HEIGHT)),
        frame_xy=(RIGHT_CENTER[0] + 0.045, _front_y(BLOCK_HEIGHT) + 0.019),
        characteristic="parallelism",
        tolerance=GEOMETRIC_TOLERANCES_MM["block top-face parallelism"],
        datums=("A",),
        label="block top-face parallelism",
    )
    finish = add_surface_finish(
        adapter,
        front,
        edge_xy=(
            FRONT_CENTER[0] + LEVER_BORE_DIA * SHEET_SCALE[0] / 2000.0,
            _front_y(LEVER_BORE_Y),
        ),
        symbol_xy=(FRONT_CENTER[0] + 0.030, _front_y(LEVER_BORE_Y) + 0.008),
        control=surface_finish_by_key(SURFACE_FINISHES, "lever_bore"),
        label="lever bore finish",
        char_height=char_height,
    )

    notes = add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.180)

    allocated.update(
        {
            "thumb-screw thread": thread_notes[0],
            "block depth": _early_bound(depth, "IDisplayDimension").GetAnnotation(),
            "datum A": _early_bound(datum, "IDatumTag").GetAnnotation(),
            "top-face parallelism": _early_bound(parallelism, "IGtol").GetAnnotation(),
            "lever bore finish": _early_bound(finish, "ISFSymbol").GetAnnotation(),
            "manufacturing notes": _early_bound(notes, "INote").GetAnnotation(),
        }
    )
    rebuild_drawing(adapter, label="clamp annotation fields")
    for label, field in TEXT_FIELDS.items():
        place_annotation_in_field(adapter, allocated[label], label=label, field=field)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        spec=SPEC,
        pdf_title="Magnifying Clamp Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(
            lambda: _assert_readability(adapter, allocated, (front, top, right), char_height),
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
