r"""Create the simplicity-policy manufacturing drawing for the cylinder gear.

The portrait sheet uses one aligned third-angle row: the gear-side front view
shows the phase notch, the right view shows the axial stack, and the cam-side
back view exposes the eccentric follower disc.  A standard isometric supplies
pictorial clarity without replacing those manufacturing views.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _surface_finish import surface_finish_by_key
from cylinder_gear_spec import (
    BORE_DIA,
    CAM_DIA,
    CAM_THICKNESS,
    ECCENTRICITY,
    FACE_WIDTH,
    NOTCH_CENTER_X,
    NOTCH_FLOOR_RADIUS,
    NOTCH_DEPTH,
    SURFACE_FINISHES,
    TIP_RADIUS,
)
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view


SPEC = DRAWINGS_BY_NAME["cylinder_gear"]
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

# Portrait makes the 62.2 mm gear materially larger than the old landscape
# 1:1 layout.  Front -> right -> back is an aligned third-angle row; the back
# view is necessary because the cam is completely hidden behind the gear in
# the front view and dimensions must never attach to hidden lines.
SHEET_SCALE = (3.0, 2.0)
VIEW_SCALE = (3, 2)
FRONT_CENTER = (0.070, 0.270)
RIGHT_CENTER = (0.140, 0.270)
BACK_CENTER = (0.210, 0.270)
ISO_CENTER = (0.165, 0.145)
GEAR_DATA_POS = (0.015, 0.410)
MANUFACTURING_NOTES_POS = (0.015, 0.105)

FRONT_KEEP = {
    "BoreDia": (0.025, 0.235),
    "NotchWidth": (0.070, 0.335),
}
RIGHT_KEEP = {
    "CamThickness": (0.140, 0.345),
}
BACK_KEEP = {
    "CamDia": (0.210, 0.340),
    # The eccentricity lies between two internal centres; keeping its text in
    # the open centre of the cam is clearer than a long leader through teeth.
    "CamCy": (0.183, 0.278),
}
DIMENSION_CALLOUTS = {
    "BoreDia": "REAM THRU",
    "NotchWidth": "ALIGNMENT NOTCH",
}
DIMENSION_PRECISION = {
    "BoreDia": 3,
    "CamDia": 2,
    "CamCy": 3,
    "CamThickness": 2,
    "NotchWidth": 2,
}


def _project_mm(
    adapter: Any,
    view: Any,
    xyz_mm: tuple[float, float, float],
    *,
    label: str,
) -> tuple[float, float]:
    return model_point_in_view(
        adapter,
        view,
        tuple(value / 1000.0 for value in xyz_mm),
        label=label,
    )


def _checked_edge_dimension(
    adapter: Any,
    view: Any,
    *,
    p0: tuple[float, float],
    p1: tuple[float, float],
    text_xy: tuple[float, float],
    label: str,
    expected_mm: float,
    precision: int,
    orientation: str,
) -> Any:
    """Add one source-geometry dimension and verify its value and precision."""
    display = add_edge_dimension(
        adapter,
        view,
        p0=p0,
        p1=p1,
        text_xy=text_xy,
        label=label,
        orientation=orientation,
    )
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - expected_mm) > 1e-5:
        raise RuntimeError(
            f"{label}: measured {measured_mm:g}, expected {expected_mm:g} mm"
        )
    display.SetPrecision3(precision, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != precision:
        raise RuntimeError(
            f"{label}: precision {display.GetPrimaryPrecision2()} != {precision}"
        )
    return display


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cylinder-gear source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
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
            0: "Cylinder Gear Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cylinder gear; integral eccentric cam; brass; 120T",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(
        adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE
    )
    right = place_view(
        adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE
    )
    back = place_view(adapter, str(SOURCE), "*Back", *BACK_CENTER, scale=VIEW_SCALE)
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE
    )
    set_hidden_lines_removed(adapter, iso)
    for view in (front, right, back):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    back_annotations = curate_view_dimensions(
        adapter, back, keep=BACK_KEEP, view_label="back"
    )
    annotations = [*front_annotations, *right_annotations, *back_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, annotations, DIMENSION_PRECISION)

    for view, label in ((front, "gear-side front"), (back, "cam-side back")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    # The gear blank width is visible in the right view but the mesh-critical
    # fixed-gear builder intentionally carries no marked sketch dimensions.
    # Read the actual end edges and fail if they no longer equal the shared spec.
    gear_pick_y = -0.75 * TIP_RADIUS
    _checked_edge_dimension(
        adapter,
        right,
        p0=_project_mm(
            adapter, right, (0.0, gear_pick_y, 0.0), label="gear front edge"
        ),
        p1=_project_mm(
            adapter,
            right,
            (0.0, gear_pick_y, FACE_WIDTH),
            label="gear rear edge",
        ),
        text_xy=(RIGHT_CENTER[0], 0.220),
        label="gear face width",
        expected_mm=FACE_WIDTH,
        precision=3,
        orientation="horizontal",
    )

    # The kerf rectangle deliberately overshoots the tooth tip so the cut opens;
    # its sketch height is not the manufacturing depth.  Dimension the real
    # tooth-tip-to-floor depth in the gear-side view and verify it against spec.
    _checked_edge_dimension(
        adapter,
        front,
        p0=_project_mm(
            adapter, front, (0.0, TIP_RADIUS, 0.0), label="notch tooth tip"
        ),
        p1=_project_mm(
            adapter,
            front,
            (NOTCH_CENTER_X, NOTCH_FLOOR_RADIUS, 0.0),
            label="notch floor",
        ),
        text_xy=(0.018, 0.320),
        label="alignment notch depth",
        expected_mm=NOTCH_DEPTH,
        precision=1,
        orientation="vertical",
    )

    bore_edge = visible_circle_edge(adapter, front, BORE_DIA)
    add_surface_finish(
        adapter,
        front,
        symbol_xy=(0.030, 0.205),
        control=surface_finish_by_key(SURFACE_FINISHES, "cylinder_gear_bore"),
        label="cylinder gear bore finish",
        entity=bore_edge,
    )

    # The follower finish belongs on the cam's cylindrical flank.  The side
    # view exposes that surface without dragging a leader across the gear face.
    cam_flank = _project_mm(
        adapter,
        right,
        (
            0.0,
            ECCENTRICITY + CAM_DIA / 2.0,
            FACE_WIDTH + CAM_THICKNESS / 2.0,
        ),
        label="cam follower flank",
    )
    add_surface_finish(
        adapter,
        right,
        edge_xy=cam_flank,
        symbol_xy=(cam_flank[0] + 0.010, 0.335),
        control=surface_finish_by_key(SURFACE_FINISHES, "cam_follower"),
        label="cam follower finish",
        entity_type="SILHOUETTE",
    )

    add_property_linked_note(
        adapter, "Gear Data", *GEAR_DATA_POS, char_height=0.0025
    )
    add_property_linked_note(
        adapter,
        "Manufacturing Notes",
        *MANUFACTURING_NOTES_POS,
        char_height=0.0025,
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cylinder Gear Manufacturing Drawing",
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
