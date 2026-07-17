r"""Create the curated machinist drawing for the cone-tip spacer bushing."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from cone_tip_bushing_spec import BORE_DIA, LENGTH, OUTER_DIA
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cone_tip_bushing"]
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

# O6 x 4 is tiny: 8:1 puts the end-view circle at O48 on the sheet, matching
# the lever-bushing print's read (O12 at 4:1). The part is extruded from the
# Top plane (axis along Y), so the circular end view is *Top and the side
# view is *Front (axis vertical on the sheet).
SHEET_SCALE = (8.0, 1.0)
END_CENTER = (0.085, 0.190)
SIDE_CENTER = (0.190, 0.190)
ISO_CENTER = (0.315, 0.205)

END_KEEP = {
    "ODDim": (
        END_CENTER[0] - 0.035,
        END_CENTER[1] + 0.010,
    ),
    "BoreDiaDim": (
        END_CENTER[0] + OUTER_DIA * SHEET_SCALE[0] / 1000.0 + 0.005,
        END_CENTER[1] - 0.010,
    ),
}
SIDE_KEEP = {
    "Depth": (SIDE_CENTER[0] + 0.036, SIDE_CENTER[1]),
}
DIMENSION_CALLOUTS = {
    "BoreDiaDim": "1/32 IN THRU\n+0.05/-0.00",
    "Depth": "+/-0.03",
}
# The bore is an exact inch conversion (1/32 in = 0.794); the sheet default of
# 2 decimals (0.79) would contradict the note, so this one dim displays 3.
DIMENSION_PRECISION = {"BoreDiaDim": 3}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-tip-bushing source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Tip Bushing Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone tip bushing; turned spacer; brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Top", *END_CENTER, scale=(8, 1))
    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=(8, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(8, 1))
    for view in (end, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, side)

    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="end"
    )
    side_annotations = curate_view_dimensions(
        adapter, side, keep=SIDE_KEEP, view_label="side"
    )
    annotations = [*end_annotations, *side_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, annotations, DIMENSION_PRECISION)
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to end view")
    # Axis centerline of the OD cylinder in the side view: with the axis
    # vertical, it marks which edge pair is the end faces (datum B and the
    # parallelism frame attach there) vs the OD silhouette. Pick the cylindrical
    # face between the left silhouette and the bore's hidden lines.
    add_view_centerline(
        adapter,
        side,
        face_xy=(SIDE_CENTER[0] - 0.012, SIDE_CENTER[1]),
        label="bushing side-view axis centerline",
    )

    outer_top = (
        END_CENTER[0],
        END_CENTER[1] + OUTER_DIA * SHEET_SCALE[0] / 2000.0,
    )
    bore_edge = (
        END_CENTER[0] + BORE_DIA * SHEET_SCALE[0] / 2000.0,
        END_CENTER[1],
    )
    half_length = LENGTH * SHEET_SCALE[0] / 2000.0
    bottom_end = (SIDE_CENTER[0], SIDE_CENTER[1] - half_length)
    top_end = (SIDE_CENTER[0], SIDE_CENTER[1] + half_length)
    # Pick the bore at 12 o'clock, because the symbol goes straight ABOVE it.
    #
    # A datum feature symbol is not freely placeable: IAnnotation::SetPosition2
    # sets "the point where the leader hits the symbol", and its Remarks restrict
    # a symbol inserted directly on an edge to "along that edge or extensions of
    # that edge", otherwise landing "as near as possible" to the request.  On a
    # CIRCLE the permitted set IS the circumference, so the tag re-attaches at
    # the circle point nearest the symbol.  Picking `bore_edge` (3 o'clock) while
    # placing the symbol at 12 fought that: the tag collapsed onto the bore,
    # printing its box over the centerline with the triangle across the "A", and
    # symbol_xy went inert (0.227 and 0.150 rendered pixel-identical).  Picking
    # the clock position the symbol sits at lets the leader run RADIALLY out to
    # it -- the draw_pivot_bushing.py spelling.
    #
    # Measured, with the pick at 12 o'clock: symbol_xy IS now honoured exactly,
    # and it is the box's BOTTOM edge that lands on it (the documented "point
    # where the leader hits the symbol") -- +0.037 puts that edge at y=0.227,
    # +0.055 at y=0.245.  0.037 is the keeper: at 0.055 the box collides with the
    # OD-runout frame's text at y=0.254.
    #
    # The bore's straight side-view flank is NOT an alternative here: it is
    # unpickable as both an EDGE and a SILHOUETTE ("failed to select" at
    # x=0.186825, and likewise at the right flank x=0.193175).
    bore_top = (
        END_CENTER[0],
        END_CENTER[1] + BORE_DIA * SHEET_SCALE[0] / 2000.0,
    )
    add_datum_feature(
        adapter,
        end,
        edge_xy=bore_top,
        symbol_xy=(END_CENTER[0], END_CENTER[1] + 0.037),
        datum="A",
        label="bushing bore axis",
    )
    add_datum_feature(
        adapter,
        side,
        edge_xy=bottom_end,
        symbol_xy=(SIDE_CENTER[0] - 0.012, bottom_end[1] - 0.020),
        datum="B",
        label="bushing reference end",
    )
    add_feature_control_frame(
        adapter,
        end,
        edge_xy=outer_top,
        frame_xy=(0.072, 0.254),
        characteristic="circular_runout",
        tolerance="0.05",
        datums=("A",),
        label="bushing OD runout",
    )
    add_feature_control_frame(
        adapter,
        side,
        edge_xy=top_end,
        frame_xy=(SIDE_CENTER[0] + 0.016, top_end[1] + 0.024),
        characteristic="parallelism",
        tolerance="0.03",
        datums=("B",),
        label="bushing end-face parallelism",
    )
    # Right of the end view at just above bore height, not up at (0.148, 0.234):
    # that was ~50 mm from the bore it annotates and dragged a long diagonal
    # leader back across the view.  The symbol's ARM extends left of the anchor
    # and its TEXT renders ABOVE the arm and to the RIGHT (ASME Y14.36), so it
    # occupies roughly x=0.112..0.151 / y=0.200..0.215 -- right of the OD circle
    # (which ends at x=0.109), clear of the BoreDiaDim callout below it (that
    # text tops out at y=0.190) and well left of the side view (x=0.166).
    add_surface_finish(
        adapter,
        end,
        edge_xy=bore_edge,
        symbol_xy=(0.115, 0.200),
        roughness_ra="1.6",
        label="bushing bore finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.022, 0.095)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Bushing Manufacturing Drawing",
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
