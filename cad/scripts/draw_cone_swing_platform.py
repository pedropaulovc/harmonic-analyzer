r"""Create the curated machinist drawing for the cone swing platform.

The SLDPRT remains authoritative.  The plan imports the plate outline,
post-mount pattern, lock notch and corner radii; the native Hole Wizard callout
defines the pivot clearance hole; section A-A exposes the shallow pivot-head
relief and plate thickness in solid lines.  Display precision comes from the
model.

The platform is an asymmetric steel wedge with a 1/4-in close-clearance pivot
hole over the stock screw shoulder, paired 1/4-20 post-mount taps, an open
west-edge lock notch, and four rounded plan corners.  The main plan and pivot
section run 1:2; the isometric runs 1:3.

Run with SolidWorks open::

    uv run python cad\scripts\draw_cone_swing_platform.py cone-swing-platform
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    assert_imported_precision,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)
from _hole_spec import blind_cut_dia_mm
from _surface_finish import surface_finish_by_key
from cone_swing_platform_spec import (
    DRAWING_PRECISION_BY_NAME,
    PIVOT_HOLE_DIA,
    POST_MOUNT_SPEC,
    SURFACE_FINISHES,
)


SPEC = DRAWINGS_BY_NAME["cone_swing_platform"]
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

SHEET_SCALE = (1.0, 3.0)  # 1:3 sheet; the 1:2 plan keeps the 266 mm envelope in-zone

# Sheet layout (meters).  The 1:2 plan is the main definition view; the
# pivot section and isometric occupy the open right-hand field.
TOP_CENTER = (0.115, 0.195)
ISO_CENTER = (0.330, 0.175)
SECTION_CENTER = (0.330, 0.075)

# Parametric model dimensions partition by the view where their geometry is
# visible.  The plan uses exterior lanes around the long vertical wedge.
TOP_KEEP = {
    "PlateLenDim": (0.045, TOP_CENTER[1]),
    "NorthEastX": (0.145, 0.255),
    "NorthEdgeZ": (0.170, 0.245),
    "NorthWestX": (0.080, 0.265),
    "SouthWestX": (0.065, 0.120),
    "SouthEastX": (0.155, 0.110),
    "PivotBearingReliefDia": (0.185, 0.225),
    "PostMountWestX": (0.080, 0.175),
    "PostMountWestZ": (0.060, 0.165),
    "PostMountEastX": (0.150, 0.175),
    "PostMountEastZ": (0.170, 0.165),
    "NotchRunAngle": (0.065, 0.145),
    "CapECx": (0.070, 0.130),
    "CapECz": (0.055, 0.150),
    "CapEDia": (0.085, 0.115),
    "CornerNER": (0.160, 0.263),
    "CornerNWR": (0.060, 0.270),
    "CornerSWR": (0.050, 0.105),
    "CornerSER": (0.165, 0.100),
}
SECTION_KEEP = {
    "PlateThk": (0.300, 0.075),
    "PivotBearingReliefDepth": (0.365, 0.105),
}


def _view_xy_mapper(adapter: Any, view: Any) -> Any:
    """Return a model-XYZ -> sheet-XY mapper for ``view``.

    Sheet coordinates are what every annotation placement is expressed in, so
    anything derived from model geometry (a rim centre, a leader attachment on
    an edge) has to come through this transform rather than a hand-measured
    literal -- a literal silently goes stale the next time the part is refitted.
    """
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    transform = _early_bound(view.ModelToViewTransform, "IMathTransform")

    def _view_xy(point_xyz: tuple[float, float, float]) -> tuple[float, float]:
        point = _early_bound(
            math_utility.CreatePoint(double_array(point_xyz)),
            "IMathPoint",
        )
        mapped = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        values = tuple(float(value) for value in mapped.ArrayData)
        return values[0], values[1]

    return _view_xy


def _add_cone_axis_centerline(adapter: Any, view: Any) -> tuple[float, float]:
    """Draw the plan-view cone axis through the modeled pivot-hole center."""
    _view_xy = _view_xy_mapper(adapter, view)

    expected_radius_m = PIVOT_HOLE_DIA / 2000.0
    pivot_centers: list[tuple[float, float]] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(c, 1), default=()
            )
            or ()
        )
        for raw_edge in edges:
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            parameters = tuple(float(value) for value in curve.CircleParams)
            if abs(parameters[6] - expected_radius_m) > 1e-6:
                continue
            pivot_centers.append(_view_xy(parameters[:3]))
    if not pivot_centers:
        raise RuntimeError(
            "cone-platform plan view has no visible pivot-hole rim at "
            f"radius {expected_radius_m:g} m"
        )

    pivot = pivot_centers[0]
    if any(
        abs(center[0] - pivot[0]) > 1e-6 or abs(center[1] - pivot[1]) > 1e-6
        for center in pivot_centers[1:]
    ):
        raise RuntimeError(
            f"cone-platform plan view has conflicting pivot centers: {pivot_centers!r}"
        )
    outline = tuple(float(value) for value in view.GetOutline())
    margin = 0.001
    if not (
        outline[0] - margin <= pivot[0] <= outline[2] + margin
        and outline[1] - margin <= pivot[1] <= outline[3] + margin
    ):
        raise RuntimeError(
            f"projected pivot center {pivot!r} falls outside plan-view outline "
            f"{outline!r}"
        )
    north = (pivot[0], outline[3])
    south = (pivot[0], outline[1])
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    model = adapter.currentModel
    # IDrawingDoc.EditSheet explicitly makes subsequently created geometry
    # sheet-owned. The endpoints are already transformed into sheet space, so
    # this keeps the centerline coincident with the projected model axis.
    drawing.EditSheet()
    sketch_manager = _early_bound(model.SketchManager, "ISketchManager")
    centerline = sketch_manager.CreateCenterLine(
        north[0], north[1], 0.0, south[0], south[1], 0.0
    )
    if centerline is None:
        raise RuntimeError("failed to create cone-axis centerline in plan view")
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    return pivot


def _visible_plan_controls(adapter: Any, view: Any) -> tuple[Any, Any]:
    """Return the pivot and post-mount rims from the plan view.

    The north-end and long-straight-side edges were dropped with the GD&T that
    referenced them (see ``build``) -- nothing else on this sheet attaches to
    them.
    """
    expected_radius_m = PIVOT_HOLE_DIA / 2000.0
    expected_mount_radius_m = blind_cut_dia_mm(POST_MOUNT_SPEC) / 2000.0
    pivot_edges: list[Any] = []
    mount_edges: list[Any] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(c, 1), default=()
            )
            or ()
        )
        for raw_edge in edges:
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            values = tuple(float(value) for value in curve.CircleParams)
            if abs(values[6] - expected_radius_m) <= 1e-6:
                pivot_edges.append(edge)
            if abs(values[6] - expected_mount_radius_m) <= 1e-6:
                mount_edges.append(edge)
    if not pivot_edges or len(mount_edges) < 2:
        raise RuntimeError("cone-platform plan view is missing pivot/mount controls")
    return pivot_edges[0], mount_edges[0]


def _horizontal_section_edge(view: Any, y_mm: float, *, label: str) -> Any:
    """Return the longest section edge lying on one broad-face station."""
    candidates: list[tuple[float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label=f"{label} section edges"):
        edge = _early_bound(raw_edge, "IEdge")
        start = edge.GetStartVertex()
        end = edge.GetEndVertex()
        if start is None or end is None:
            continue
        p0 = tuple(float(value) * 1000.0 for value in _early_bound(start, "IVertex").GetPoint())
        p1 = tuple(float(value) * 1000.0 for value in _early_bound(end, "IVertex").GetPoint())
        if abs(p0[1] - y_mm) <= 0.01 and abs(p1[1] - y_mm) <= 0.01:
            candidates.append((abs(p1[0] - p0[0]), edge))
    if not candidates:
        raise RuntimeError(f"pivot section has no {label} edge at y={y_mm:.3f} mm")
    return max(candidates, key=lambda item: item[0])[1]


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-swing-platform source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Plan View Note",
            "Isometric View Note",
            "Section View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Plan View Note",
            "Isometric View Note",
            "Section View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Swing Platform Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone swing platform; wedge plate; pivot; lock notch",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 3))
    for view in (top, iso):
        set_hidden_lines_removed(adapter, view)

    pivot_xy = _add_cone_axis_centerline(adapter, top)
    top_outline = tuple(float(value) for value in top.GetOutline())
    section = create_section_view(
        adapter,
        top,
        line_start=(top_outline[0] - 0.002, pivot_xy[1]),
        line_end=(top_outline[2] + 0.002, pivot_xy[1]),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(1, 2),
        label="pivot bearing section",
    )
    set_hidden_lines_removed(adapter, section)

    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="plan"
    )
    section_annotations = curate_view_dimensions(
        adapter, section, keep=SECTION_KEEP, view_label="pivot section"
    )
    annotations = [*top_annotations, *section_annotations]
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the pivot bore")

    pivot_edge, mount_edge = _visible_plan_controls(adapter, top)
    add_native_hole_callout(
        adapter,
        top,
        callout_xy=(0.200, 0.215),
        label="pivot close-clearance hole",
        edge=pivot_edge,
    )
    add_native_hole_callout(
        adapter,
        top,
        # Below the pair, not level with it: the model's own "1/4-20 Tapped
        # Hole" note drops a leader onto the east hole, and a callout placed
        # level with the holes routes its leader straight across that descent
        # (fail-loud layout gate, 2 leader crossings). Coming up from below
        # keeps this leader clear of the note for the whole span.
        callout_xy=(0.175, 0.225),
        label="v2 post-mount tapped holes",
        edge=mount_edge,
    )
    add_surface_finish(
        adapter,
        section,
        symbol_xy=(0.285, 0.118),
        control=surface_finish_by_key(SURFACE_FINISHES, "post_seat"),
        label="post and tip-block seat finish",
        char_height=0.0025,
        entity=_horizontal_section_edge(section, 6.35, label="top seat"),
    )
    add_surface_finish(
        adapter,
        section,
        symbol_xy=(0.285, 0.045),
        control=surface_finish_by_key(SURFACE_FINISHES, "base_slide"),
        label="base sliding-face finish",
        char_height=0.0025,
        entity=_horizontal_section_edge(section, 0.0, label="base slide"),
    )

    add_property_linked_note(adapter, "Plan View Note", 0.190, 0.205)
    add_property_linked_note(adapter, "Isometric View Note", 0.290, 0.135)
    add_property_linked_note(adapter, "Section View Note", 0.300, 0.115)

    # Annotation insertion can invalidate the exported display geometry.
    for view in (top, section, iso):
        set_hidden_lines_removed(adapter, view)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Swing Platform Manufacturing Drawing",
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
