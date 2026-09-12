r"""Create the curated machinist drawing for the rocker arm.

The SLDPRT remains authoritative.  This recipe supplies only the rocker-arm
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The front view carries the curved profile and both bore locations; its aligned
right orthographic carries the 2.50 plate and integral central-hub thicknesses.
Native radial dimensions define the long arcs without an off-sheet dimensional
paragraph.  The sheet runs at 1:2 with a 1:4 isometric.

Run with SolidWorks open::

    uv run python cad\scripts\draw_rocker_arm.py rocker-arm
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
    view_name,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _hole_spec import blind_cut_dia_mm
from _surface_finish import surface_finish_by_key
from rocker_arm_notes import DIMENSION_CALLOUTS, DIMENSION_PRECISION
from rocker_arm_spec import (
    ARM_DEPTH,
    ARM_THICKNESS,
    HUB_LENGTH,
    PIVOT_HOLE_DIA,
    R_BOTTOM,
    R_TOP,
    ROD_HOLE_X,
    ROD_HOLE_SPEC,
    ROD_HOLE_Y,
    ROD_TIP_X,
    SURFACE_FINISHES,
    TIP_FACE,
    TOP_ARC_LEN,
    TOP_END_Y,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["rocker_arm"]
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

SHEET_SCALE = (1.0, 2.0)  # 1:2
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
_PIVOT_MID_Y = ARM_DEPTH / 2.0
_ROD_HOLE_DIA = blind_cut_dia_mm(ROD_HOLE_SPEC)
_BBOX_CY = TOP_END_Y / 2.0
_ROD_TIP_Y = TOP_END_Y - TIP_FACE * math.cos(TOP_ARC_LEN / 2.0 / R_TOP)

FRONT_CENTER = (0.180, 0.175)
RIGHT_CENTER = (0.315, FRONT_CENTER[1])
ISO_CENTER = (0.350, 0.215)


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (1:2)."""
    return (
        FRONT_CENTER[0] + mx * _S / 1000.0,
        FRONT_CENTER[1] + (my - _BBOX_CY) * _S / 1000.0,
    )


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


def _checked_value(display: Any, *, expected_mm: float, precision: int, label: str) -> Any:
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - expected_mm) > 1e-5:
        raise RuntimeError(
            f"{label}: measured {measured_mm:g}, expected {expected_mm:g} mm"
        )
    display.SetPrecision3(precision, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != precision:
        raise RuntimeError(f"{label}: precision did not persist")
    return display


def _checked_dimension(
    adapter: Any,
    view: Any,
    *,
    p0: tuple[float, float],
    p1: tuple[float, float],
    text_xy: tuple[float, float],
    label: str,
    expected_mm: float,
    precision: int = 2,
    orientation: str = "smart",
    centers: bool = False,
) -> Any:
    display = add_edge_dimension(
        adapter,
        view,
        p0=p0,
        p1=p1,
        text_xy=text_xy,
        label=label,
        orientation=orientation,
    )
    if centers:
        set_arc_endpoints_to_center(adapter, display, label=label)
    return _checked_value(
        display, expected_mm=expected_mm, precision=precision, label=label
    )


def _radius_edge(adapter: Any, view: Any, radius_mm: float, *, label: str) -> Any:
    candidates: list[tuple[float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label=f"{label} curves"):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        radius = float(curve.CircleParams[6]) * 1000.0
        candidates.append((abs(radius - radius_mm), edge))
    if not candidates:
        raise RuntimeError(f"{label}: no circular edge")
    error, edge = min(candidates, key=lambda item: item[0])
    if error > 0.01:
        raise RuntimeError(f"{label}: no edge at R{radius_mm:.3f}")
    return edge


def _add_radial_dimension(
    adapter: Any,
    view: Any,
    entity: Any,
    *,
    position: tuple[float, float],
    label: str,
    expected_mm: float,
) -> Any:
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate view for {label}")
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    selection_data = selection_manager.CreateSelectData()
    selection_data.View = view
    if not _early_bound(entity, "IEntity").Select4(False, selection_data):
        raise RuntimeError(f"failed to select {label} edge")
    display = draw.AddRadialDimension2(*position, 0.0)
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"failed to create {label}")
    draw.EditRebuild3()
    return _checked_value(display, expected_mm=expected_mm, precision=2, label=label)


FRONT_KEEP = {
    "BottomRodX": (0.180, 0.205),
    "RodTipLen": (0.275, 0.220),
    "PivotDia": (0.180, 0.135),
    "PivotZ": (0.150, 0.150),
    "HubDia": (0.180, 0.115),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}



async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-arm source", await adapter.open_model(str(SOURCE)))
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
            0: "Rocker Arm Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm; single plate; plain rod-end pivot bore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (front, right):
        set_hidden_lines_visible(adapter, view)
    set_hidden_lines_removed(adapter, iso)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, front_annotations, DIMENSION_PRECISION)

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    # The two long radii are native radial dimensions attached directly to the
    # visible profile arcs.  This avoids the former dimensional paragraph and
    # its off-sheet model-dimension witnesses.
    _add_radial_dimension(
        adapter,
        front,
        _radius_edge(adapter, front, R_TOP, label="top profile radius"),
        position=(0.085, 0.225),
        label="top profile radius",
        expected_mm=R_TOP,
    )
    _add_radial_dimension(
        adapter,
        front,
        _radius_edge(adapter, front, R_BOTTOM, label="bottom profile radius"),
        position=(0.085, 0.135),
        label="bottom profile radius",
        expected_mm=R_BOTTOM,
    )
    _checked_dimension(
        adapter,
        front,
        p0=_project_mm(
            adapter,
            front,
            (-ROD_TIP_X, _ROD_TIP_Y, 0.0),
            label="rocker left extreme",
        ),
        p1=_project_mm(
            adapter,
            front,
            (ROD_TIP_X, _ROD_TIP_Y, 0.0),
            label="rocker right extreme",
        ),
        text_xy=(FRONT_CENTER[0], 0.105),
        label="rocker overall length",
        expected_mm=2.0 * ROD_TIP_X,
        orientation="horizontal",
    )

    pivot_rim = _sheet_xy(0.0, _PIVOT_MID_Y - PIVOT_HOLE_DIA / 2.0)
    rod_rim = _sheet_xy(ROD_HOLE_X, ROD_HOLE_Y - _ROD_HOLE_DIA / 2.0)
    _checked_dimension(
        adapter,
        front,
        p0=pivot_rim,
        p1=rod_rim,
        text_xy=(0.205, 0.145),
        label="rod-pin X location",
        expected_mm=ROD_HOLE_X,
        orientation="horizontal",
        centers=True,
    )
    _checked_dimension(
        adapter,
        front,
        p0=pivot_rim,
        p1=rod_rim,
        text_xy=(0.275, 0.165),
        label="rod-pin Y location",
        expected_mm=ROD_HOLE_Y - _PIVOT_MID_Y,
        orientation="vertical",
        centers=True,
    )

    # The right orthographic remains aligned with the front view and carries
    # both the single-plate thickness and integral central-hub length.
    _checked_dimension(
        adapter,
        right,
        p0=_project_mm(
            adapter,
            right,
            (0.0, ARM_DEPTH - 1.0, -ARM_THICKNESS / 2.0),
            label="rocker plate rear face",
        ),
        p1=_project_mm(
            adapter,
            right,
            (0.0, ARM_DEPTH - 1.0, ARM_THICKNESS / 2.0),
            label="rocker plate front face",
        ),
        text_xy=(RIGHT_CENTER[0], 0.205),
        label="rocker plate thickness",
        expected_mm=ARM_THICKNESS,
        orientation="horizontal",
    )
    _checked_dimension(
        adapter,
        right,
        p0=_project_mm(
            adapter,
            right,
            (0.0, _PIVOT_MID_Y + 4.0, -HUB_LENGTH / 2.0),
            label="hub rear face",
        ),
        p1=_project_mm(
            adapter,
            right,
            (0.0, _PIVOT_MID_Y + 4.0, HUB_LENGTH / 2.0),
            label="hub front face",
        ),
        text_xy=(RIGHT_CENTER[0], 0.135),
        label="integral hub length",
        expected_mm=HUB_LENGTH,
        precision=3,
        orientation="horizontal",
    )

    add_native_hole_callout(
        adapter,
        front,
        edge_xy=rod_rim,
        callout_xy=(0.290, 0.130),
        label="plain rod-end pivot bore",
    )
    pivot_bore_edge = visible_circle_edge(adapter, front, PIVOT_HOLE_DIA)
    add_surface_finish(
        adapter,
        front,
        edge_entity=pivot_bore_edge,
        symbol_xy=(0.140, 0.190),
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_bore"),
        label="pivot bore finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)
    add_property_linked_note(adapter, "Isometric View Note", 0.315, 0.150)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Arm Manufacturing Drawing",
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
