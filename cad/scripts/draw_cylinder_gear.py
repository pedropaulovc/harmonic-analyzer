r"""Create the simplicity-policy manufacturing drawing for the cylinder gear.

The portrait sheet uses one aligned third-angle row: the cam-side front view
shows the eccentric follower, bore and phase notch, while the right view shows
the axial stack.  A standard isometric supplies pictorial clarity without
replacing those manufacturing views.
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
    set_reference_dimensions,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _surface_finish import surface_finish_by_key
from cylinder_gear_spec import (
    BORE_DIA,
    BORE_FIT_CALLOUT,
    CAM_DIA,
    CAM_THICKNESS,
    ECCENTRICITY,
    FACE_WIDTH,
    OVERALL_THICKNESS,
    SURFACE_FINISHES,
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
# 1:1 layout.  The cam-side front view exposes every radial feature, so a
# redundant opposite face view would only consume the exterior dimension lanes.
SHEET_SCALE = (3.0, 2.0)
VIEW_SCALE = (3, 2)
FRONT_CENTER = (0.105, 0.270)
RIGHT_CENTER = (0.205, 0.270)
ISO_CENTER = (0.165, 0.145)
GEAR_DATA_POS = (0.015, 0.410)
MANUFACTURING_NOTES_POS = (0.015, 0.105)

FRONT_KEEP = {
    "BoreDia": (0.080, 0.210),
    "NotchWidth": (0.105, 0.340),
    "NotchDepth": (0.050, 0.325),
    "CamDia": (0.175, 0.325),
    "CamCy": (0.160, 0.260),
}
RIGHT_KEEP = {
    "FaceWidth": (0.205, 0.220),
    "CamThickness": (0.205, 0.345),
}
DIMENSION_CALLOUTS = {
    "BoreDia": BORE_FIT_CALLOUT,
    "NotchWidth": "ALIGNMENT NOTCH",
    "NotchDepth": "FROM OD",
}
DIMENSION_PRECISION = {
    "BoreDia": 3,
    "CamDia": 2,
    "FaceWidth": 2,
    "CamCy": 3,
    "CamThickness": 2,
    "NotchWidth": 2,
    "NotchDepth": 1,
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
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE
    )
    set_hidden_lines_removed(adapter, iso)
    for view in (front, right):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    annotations = [*front_annotations, *right_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, annotations, DIMENSION_PRECISION)
    set_reference_dimensions(adapter, annotations, {"BoreDia"})

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to cam-side front view")

    # Face width and cam width remain the two authoritative axial dimensions.
    # The policy also requires a conspicuous overall length, so show the measured
    # end-to-end stack as a checked REFERENCE dimension rather than closing an
    # independently toleranced dimension chain.
    cam_bore_wall = CAM_DIA / 2.0 - ECCENTRICITY - BORE_DIA / 2.0
    overall_pick_y = -(BORE_DIA / 2.0 + cam_bore_wall / 2.0)
    overall = _checked_edge_dimension(
        adapter,
        right,
        p0=_project_mm(
            adapter,
            right,
            (0.0, overall_pick_y, 0.0),
            label="overall gear front edge",
        ),
        p1=_project_mm(
            adapter,
            right,
            (0.0, overall_pick_y, OVERALL_THICKNESS),
            label="overall cam rear edge",
        ),
        text_xy=(RIGHT_CENTER[0] + 0.020, 0.200),
        label="overall axial thickness",
        expected_mm=OVERALL_THICKNESS,
        precision=1,
        orientation="horizontal",
    )
    overall.ShowParenthesis = True
    if not overall.ShowParenthesis:
        raise RuntimeError("overall axial thickness was not shown as reference")

    bore_edge = visible_circle_edge(adapter, front, BORE_DIA)
    add_surface_finish(
        adapter,
        front,
        symbol_xy=(0.140, 0.200),
        control=surface_finish_by_key(SURFACE_FINISHES, "cylinder_gear_bore"),
        label="cylinder gear bore finish",
        entity=bore_edge,
        leader_attach_xy=_project_mm(
            adapter,
            front,
            (0.0, -BORE_DIA / 2.0, 0.0),
            label="bore finish leader attachment",
        ),
        char_height=0.0025,
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
        symbol_xy=(0.220, 0.310),
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
