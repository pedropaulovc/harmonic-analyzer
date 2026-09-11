r"""Create the curated machinist drawing for the cone-tip spacer bushing."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from cone_tip_bushing_spec import GEOMETRIC_TOLERANCES_MM

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
from _surface_finish import surface_finish_by_key
from cone_tip_bushing_spec import BORE_DIA, LENGTH, OUTER_DIA, SURFACE_FINISHES
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
    "BoreDiaDim": "1/32 IN THRU",
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
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

    # The OD runout attaches at the OD's UPPER-LEFT 45 deg point, NOT its 12
    # o'clock -- and this is the whole reason the frame's own anchor is up-left.
    #
    # Datum A (below) leaders RADIALLY out of the bore at 12 o'clock, so it is a
    # vertical line along x = END_CENTER[0]. The OD's 12 o'clock lies exactly ON
    # that line, so an `outer_top` pick put the runout's arrowhead on top of the
    # datum leader: measured on the 2026-07-16 render, arrow tip (0.0852, 0.2146)
    # against the datum leader at x=0.0850 -- 0.2 mm apart, the stacked-arrowhead
    # tell. 45 deg moves the arrow to (0.0680, 0.2070), a clear 17 mm away, and
    # keeps the leader radial (it approaches the OD from OUTSIDE, so it never
    # crosses the circle). This is draw_pivot_bushing.py's `outer_edge_upper`
    # spelling and its stated rationale -- "so the four leaders do not converge
    # on one spot".
    _diag = 2.0**-0.5
    _outer_r = OUTER_DIA * SHEET_SCALE[0] / 2000.0
    outer_upper_left = (
        END_CENTER[0] - _outer_r * _diag,
        END_CENTER[1] + _outer_r * _diag,
    )
    bore_edge = (
        END_CENTER[0] + BORE_DIA * SHEET_SCALE[0] / 2000.0,
        END_CENTER[1],
    )
    half_length = LENGTH * SHEET_SCALE[0] / 2000.0
    bottom_end = (SIDE_CENTER[0], SIDE_CENTER[1] - half_length)
    top_end = (SIDE_CENTER[0], SIDE_CENTER[1] + half_length)
    # Pick the bore at 12 o'clock so A's leader runs radially above it.
    # A concentric bore-to-symbol ray necessarily crosses the OD; the runout
    # arrow uses the separate upper-left point to avoid stacking on that leader.
    # SetPosition2's anchor is where the leader hits the symbol, not the box
    # centre: +0.037 puts the box's bottom edge at y=0.227, below the runout frame.
    # Native insertion starts with a forced shoulder. The shared helper settles
    # its removal on this vertical ray before enforcing the requested position.
    bore_top = (
        END_CENTER[0],
        END_CENTER[1] + BORE_DIA * SHEET_SCALE[0] / 2000.0,
    )
    # Retain the existing 0.1 mm sheet-placement bound; no geometry tolerance
    # or requested coordinate is adjusted for the initial leader-mode offset.
    add_datum_feature(
        adapter,
        end,
        edge_xy=bore_top,
        symbol_xy=(END_CENTER[0], END_CENTER[1] + 0.037),
        datum="A",
        label="bushing bore axis",
        position_tolerance_m=0.0001,
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
        edge_xy=outer_upper_left,
        frame_xy=(0.072, 0.254),
        characteristic="circular_runout",
        tolerance=GEOMETRIC_TOLERANCES_MM["bushing OD runout"],
        datums=("A",),
        label="bushing OD runout",
    )
    add_feature_control_frame(
        adapter,
        side,
        edge_xy=top_end,
        frame_xy=(SIDE_CENTER[0] + 0.016, top_end[1] + 0.024),
        characteristic="parallelism",
        tolerance=GEOMETRIC_TOLERANCES_MM["bushing end-face parallelism"],
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
        control=surface_finish_by_key(SURFACE_FINISHES, "bushing_bore"),
        label="bushing bore finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.022, 0.095)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Bushing Manufacturing Drawing",
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
