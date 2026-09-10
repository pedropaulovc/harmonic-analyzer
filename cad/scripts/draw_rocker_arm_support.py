r"""Create the curated machinist drawing for the rocker-arm support.

The SLDPRT remains authoritative.  This recipe supplies only the support's
views, dimension layout, hole table, and make-critical annotations; every
shared sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The support is a painted gray-iron frame with a trapezoidal wall, two opposed
pockets leaving a central web, a through cavity, a chamfered window rim, and
four 5/16 clearance holes through its mounting foot. The sheet runs 1:2, with
each view's scale pinned explicitly.

Run with SolidWorks open::

    uv run python cad\scripts\draw_rocker_arm_support.py rocker-arm-support
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
    add_surface_finish,
    create_section_view,
    create_view_theoretical_datum,
    curate_view_dimensions,
    finalize_drawing,
    insert_hole_table,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from build_rocker_arm_support import (
    BIG,
    BOSS_DEPTH,
    CAV,
    CHAMFER,
    HALF_Y,
    HOLES,
    HOLE_DIA,
    WEB,
    WIDE,
)
from rocker_arm_support_drawing_spec import SURFACE_FINISHES
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["rocker_arm_support"]
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

SHEET_SCALE = (1.0, 2.0)

# Sheet layout (meters). A 177.8 mm casting with four views needs a 1:2 ASME B
# sheet. Section A-A replaces the side view, exposing the opposed pocket floors
# and web; the clearance-hole setup stays aligned below the front. The front
# shifts left of the section, and the bottom view drops to open an exterior
# annotation lane below the front without breaking the projected group.
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]
FRONT_CENTER = (0.105, 0.185)
RIGHT_CENTER = (0.205, 0.185)
BOTTOM_CENTER = (0.105, 0.075)
ISO_CENTER = (0.350, 0.201)

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position (meters). Every front-view callout is outside the part silhouette:
# overall size above, nested pocket sizes below, radii left, chamfer right.
FRONT_KEEP = {
    "Depth": (0.105, 0.258),
    "PocketRadius": (0.035, 0.150),
    "CavityRadius": (0.035, 0.190),
    "WinWidth": (0.105, 0.118),
    "CavWidth": (0.105, 0.128),
    "RimChamferSize": (0.165, 0.225),
}
DIMENSION_CALLOUTS = {
    "PocketRadius": "8X",
    "CavityRadius": "4X",
    "WinWidth": "SQ POCKET",
    "CavWidth": "SQ CAVITY THRU",
    "RimChamferSize": " X 45 DEG\n2 FACES",
}
DIMENSION_PRECISION = {
    "Depth": 1,
    "WinWidth": 1,
    "CavWidth": 1,
    "PocketRadius": 2,
    "CavityRadius": 1,
    "WallHeight": 1,
    "FootSpan": 1,
    "TopSpan": 1,
    "RimChamferSize": 2,
    "WebThickness": 2,  # a held thickness: 6.35, routine ±0.51
    "FootThickness": 2,
}
RIGHT_KEEP = {
    "WallHeight": (0.240, 0.185),
    "FootSpan": (0.205, 0.133),
    "TopSpan": (0.205, 0.238),
}

# Top-left anchor; the native four-row table grows down and right while
# remaining clear of the isometric and title block.
HOLE_TABLE_ANCHOR = (0.270, 0.130)
HOLE_TABLE_DATUM_XZ_MM = (-BOSS_DEPTH / 2.0, -WIDE)
EXPECTED_HOLE_TABLE_LOCATIONS_MM = (
    (149.22, 49.21),
    (28.58, 49.21),
    (149.22, 14.29),
    (28.58, 14.29),
)


def _bottom_sheet_xy(hole_xz: tuple[float, float]) -> tuple[float, float]:
    """Sheet pick point on a foot-hole rim in the bottom view."""
    x_mm, z_mm = hole_xz
    return (
        BOTTOM_CENTER[0] + x_mm * VIEW_SCALE / 1000.0,
        BOTTOM_CENTER[1] + (z_mm + HOLE_DIA / 2.0) * VIEW_SCALE / 1000.0,
    )


def _bottom_datum_axes(adapter: Any, view: Any) -> tuple[Any, Any]:
    """Return the chamfer-inset edges used to create the native table."""
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    x_axes: list[Any] = []
    y_axes: list[Any] = []
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(c, 1),
                default=(),
            )
            or ()
        )
        for raw_edge in edges:
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsLine():
                continue
            parameters = tuple(float(value) for value in curve.LineParams)
            if (
                abs(parameters[2] + (WIDE - CHAMFER) / 1000.0) <= 2e-6
                and abs(parameters[3]) >= 0.99
            ):
                x_axes.append(edge)
            if (
                abs(parameters[0] + (BOSS_DEPTH / 2.0 - CHAMFER) / 1000.0) <= 2e-6
                and abs(parameters[5]) >= 0.99
            ):
                y_axes.append(edge)
    if not x_axes or not y_axes:
        raise RuntimeError("bottom view is missing a chamfer-inset datum edge")
    return x_axes[0], y_axes[0]


def _right_seat_edge(adapter: Any, view: Any) -> Any:
    """Return the longest right-view edge on the mounting-face plane."""
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    candidates: list[tuple[float, Any]] = []
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(c, 1),
                default=(),
            )
            or ()
        )
        for raw_edge in edges:
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsLine():
                continue
            parameters = tuple(float(value) for value in curve.LineParams)
            if abs(parameters[1] + HALF_Y / 1000.0) > 2e-6 or abs(parameters[5]) < 0.99:
                continue
            start = _early_bound(edge.GetStartVertex(), "IVertex").GetPoint()
            end = _early_bound(edge.GetEndVertex(), "IVertex").GetPoint()
            candidates.append((abs(float(end[2]) - float(start[2])), edge))
    if not candidates:
        raise RuntimeError("right view has no model edge on the mounting-face plane")
    span, edge = max(candidates, key=lambda item: item[0])
    if span < (2.0 * WIDE - 2.0 * CHAMFER - 0.1) / 1000.0:
        raise RuntimeError(f"mounting-face edge spans only {span * 1000.0:.3f} mm")
    return edge


@_telemetry.traced("drawing.planar_centerline", label_param="label")
def _create_view_centerline(
    adapter: Any,
    view: Any,
    *,
    start_xy: tuple[float, float],
    end_xy: tuple[float, float],
    label: str,
) -> Any:
    """Create a retained centerline in one drawing view's sketch."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate centerline view {name!r}")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(sketch_manager.AddToDB)
    previous_display = bool(sketch_manager.DisplayWhenAdded)
    sketch_manager.AddToDB = True
    sketch_manager.DisplayWhenAdded = True
    try:
        centerline = sketch_manager.CreateCenterLine(
            start_xy[0],
            start_xy[1],
            0.0,
            end_xy[0],
            end_xy[1],
            0.0,
        )
    finally:
        sketch_manager.AddToDB = previous_add_to_db
        sketch_manager.DisplayWhenAdded = previous_display
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if centerline is None:
        raise RuntimeError(f"failed to create {label} centerline")
    return centerline


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-arm-support source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker-Arm Support Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker-arm support; manufacturing drawing; casting",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # swDetailingSectionViewLineStyleDisplay (swconst.tlb R2026x): end segments
    # only. Span the full parent view so SolidWorks derives a stable, complete
    # centre section; the dimensions occupy exterior lanes away from its arrows.
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    if not extension.SetUserPreferenceInteger(542, 0, 1):
        raise RuntimeError("failed to set end-only section cutting line")
    if extension.GetUserPreferenceInteger(542, 0) != 1:
        raise RuntimeError("section cutting-line style did not persist")

    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    right = create_section_view(
        adapter,
        front,
        line_start=(FRONT_CENTER[0], FRONT_CENTER[1] - 0.050),
        line_end=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.050),
        view_xy=RIGHT_CENTER,
        section_label="A",
        scale=(1, 2),
        label="rocker-arm support centre section",
    )
    bottom = place_view(adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (front, bottom):
        set_hidden_lines_visible(adapter, view)
    set_hidden_lines_removed(adapter, right)
    set_hidden_lines_removed(adapter, iso)

    front_dimensions = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_dimensions = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    dimensions = [*front_dimensions, *right_dimensions]
    set_dimension_callouts(adapter, dimensions, DIMENSION_CALLOUTS)
    set_dimension_precision(
        adapter,
        dimensions,
        {
            name: digits
            for name, digits in DIMENSION_PRECISION.items()
            if name not in {"WebThickness", "FootThickness"}
        },
    )
    _create_view_centerline(
        adapter,
        front,
        start_xy=(-BOSS_DEPTH / 2000.0, 0.0),
        end_xy=(BOSS_DEPTH / 2000.0, 0.0),
        label="front wall",
    )
    _create_view_centerline(
        adapter,
        front,
        start_xy=(0.0, -HALF_Y / 1000.0),
        end_xy=(0.0, HALF_Y / 1000.0),
        label="front vertical",
    )
    _create_view_centerline(
        adapter,
        right,
        start_xy=(0.0, -HALF_Y / 1000.0),
        end_xy=(0.0, HALF_Y / 1000.0),
        label="section web",
    )
    # Pick the two cut pocket floors in the upper web band, outside the
    # through cavity. HLR ensures the selected edges are visible section edges.
    web_y = RIGHT_CENTER[1] + (BIG + CAV) / 2.0 * VIEW_SCALE / 1000.0
    half_web = WEB * VIEW_SCALE / 1000.0
    web_dimension = _early_bound(
        add_edge_dimension(
            adapter,
            right,
            p0=(RIGHT_CENTER[0] - half_web, web_y),
            p1=(RIGHT_CENTER[0] + half_web, web_y),
            text_xy=(RIGHT_CENTER[0] + 0.012, RIGHT_CENTER[1] + 0.022),
            orientation="horizontal",
            label="section web thickness",
        ),
        "IDisplayDimension",
    )
    measured = float(
        _early_bound(web_dimension.GetDimension2(0), "IDimension").SystemValue
    )
    if abs(measured * 1000.0 - 2.0 * WEB) > 1e-5:
        raise RuntimeError(f"section web dimension measured {measured * 1000.0:.6f} mm")
    web_dimension.SetPrecision3(DIMENSION_PRECISION["WebThickness"], -1, -1, -1)
    if web_dimension.GetPrimaryPrecision2() != DIMENSION_PRECISION["WebThickness"]:
        raise RuntimeError("section web dimension precision did not persist")
    foot_pick_x = RIGHT_CENTER[0] + 0.010
    foot_dimension = _early_bound(
        add_edge_dimension(
            adapter,
            right,
            p0=(
                foot_pick_x,
                RIGHT_CENTER[1] - HALF_Y * VIEW_SCALE / 1000.0,
            ),
            p1=(
                foot_pick_x,
                RIGHT_CENTER[1] - BIG * VIEW_SCALE / 1000.0,
            ),
            text_xy=(RIGHT_CENTER[0] - 0.025, RIGHT_CENTER[1] - 0.043),
            orientation="vertical",
            label="section foot thickness",
        ),
        "IDisplayDimension",
    )
    measured = float(
        _early_bound(foot_dimension.GetDimension2(0), "IDimension").SystemValue
    )
    if abs(measured * 1000.0 - (HALF_Y - BIG)) > 1e-5:
        raise RuntimeError(
            f"section foot dimension measured {measured * 1000.0:.6f} mm"
        )
    foot_dimension.SetPrecision3(DIMENSION_PRECISION["FootThickness"], -1, -1, -1)
    if not auto_center_marks(adapter, bottom, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to bottom view")

    # The mounting face is the trapezoid's visible bottom edge in section A-A.
    # Keep the symbol near the foot while clearing the 63.5 width dimension.
    seat_y = RIGHT_CENTER[1] - HALF_Y * VIEW_SCALE / 1000.0
    seat_half_w = WIDE * VIEW_SCALE / 1000.0
    add_surface_finish(
        adapter,
        right,
        edge_entity=_right_seat_edge(adapter, right),
        symbol_xy=(RIGHT_CENTER[0] + seat_half_w + 0.020, seat_y - 0.010),
        control=surface_finish_by_key(SURFACE_FINISHES, "mounting_face"),
        label="mounting face finish",
        char_height=0.0025,
        leader_attach_xy=(RIGHT_CENTER[0] + seat_half_w - 0.002, seat_y),
    )

    datum_axes = _bottom_datum_axes(adapter, bottom)
    datum_point = create_view_theoretical_datum(
        adapter,
        bottom,
        point_xy=(
            HOLE_TABLE_DATUM_XZ_MM[0] / 1000.0,
            HOLE_TABLE_DATUM_XZ_MM[1] / 1000.0,
        ),
        label="rocker-arm-support lower-left theoretical corner",
    )
    # No position frame on this part (simplicity policy rule 3/4), so the hole
    # coordinates are ordinary two-place dimensions under the title block's
    # ±0.51 — NOT basic: a basic dimension is toleranced only by the frame it
    # feeds, and without one it has no tolerance at all.
    insert_hole_table(
        adapter,
        bottom,
        datum_xy=(
            BOTTOM_CENTER[0] + HOLE_TABLE_DATUM_XZ_MM[0] * VIEW_SCALE / 1000.0,
            BOTTOM_CENTER[1] + HOLE_TABLE_DATUM_XZ_MM[1] * VIEW_SCALE / 1000.0,
        ),
        hole_points=tuple(_bottom_sheet_xy(hole) for hole in HOLES),
        datum_point=datum_point,
        expected_locations_mm=EXPECTED_HOLE_TABLE_LOCATIONS_MM,
        datum_axes=datum_axes,
        anchor_xy=HOLE_TABLE_ANCHOR,
        basic_locations=False,
        label="rocker-arm-support",
    )
    # The drawing-sketch datum and hole table leave the bottom view's HLV edge
    # set stale, so restore its complete projected edge set before export.
    set_hidden_lines_visible(adapter, bottom)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker-Arm Support Manufacturing Drawing",
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
