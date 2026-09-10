r"""Create the curated machinist drawing for the rocker-arm support.

The SLDPRT remains authoritative.  This recipe supplies only the support's
views, dimension layout, hole table, and casting/machining notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The support is a green-painted gray-iron casting: a trapezoidal wall with a
square window cut from both faces (leaving a central web), a rounded/chamfered
window rim, and four 1/2-13 UNC-2B tapped holes up through the foot. The sheet
runs 1:2, with each view's scale pinned explicitly.

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
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    import_cosmetic_threads,
    insert_hole_table,
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
from build_rocker_arm_support import (
    BOSS_DEPTH,
    CHAMFER,
    HALF_Y,
    HOLES,
    HOLE_TAP_DRILL_DIA,
    WIDE,
)
from rocker_arm_support_drawing_spec import SURFACE_FINISHES
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    iter_views,
    place_view,
    view_name,
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
# sheet. Third-angle projection keeps the taper beside the window face and the
# tapping setup below it. The projected group sits below the zone strip with
# enough separation for dimensions and leaders.
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]
FRONT_CENTER = (0.085, 0.185)
RIGHT_CENTER = (0.170, 0.185)
BOTTOM_CENTER = (0.085, 0.095)
ISO_CENTER = (0.360, 0.201)

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position (meters).
FRONT_KEEP = {
    "Depth": (0.085, 0.253),  # 177.8 overall cast width, above
    # Keep square callout text in the opening rather than on its boundary.
    "WinWidth": (0.085, 0.207),
    "CavWidth": (0.085, 0.173),
}
DIMENSION_CALLOUTS = {
    "WinWidth": "SQ POCKET",
    "CavWidth": "SQ CAVITY THRU",
}
DIMENSION_PRECISION = {
    "Depth": 1,
    "WinWidth": 1,
    "CavWidth": 1,
    "WallHeight": 1,
    "FootSpan": 1,
    "TopSpan": 1,
}
RIGHT_KEEP = {
    "WallHeight": (0.197, 0.185),  # 177.8 wall height, right of the taper
    "FootSpan": (0.170, 0.133),  # 63.5 foot section, below the view
    "TopSpan": (0.170, 0.238),  # 16.93 top section, above the view
}

# Top-left anchor; the native four-row table grows down and right while
# remaining clear of the isometric and title block.
HOLE_TABLE_ANCHOR = (0.270, 0.130)
# Independent drawing contract measured from the chamfered datum edges.
EXPECTED_HOLE_TABLE_LOCATIONS_MM = (
    (147.95, 47.94),
    (27.31, 47.94),
    (147.95, 13.02),
    (27.31, 13.02),
)


def _bottom_sheet_xy(hole_xz: tuple[float, float]) -> tuple[float, float]:
    """Sheet pick point on a foot-hole rim in the bottom view."""
    x_mm, z_mm = hole_xz
    return (
        BOTTOM_CENTER[0] + x_mm * VIEW_SCALE / 1000.0,
        BOTTOM_CENTER[1] + (z_mm + HOLE_TAP_DRILL_DIA / 2.0) * VIEW_SCALE / 1000.0,
    )


def _bottom_datum_axes(adapter: Any, view: Any) -> tuple[Any, Any]:
    """Return the two chamfer-offset datum axes visible in the bottom view."""
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
        for edge in edges:
            edge = _early_bound(edge, "IEdge")
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
        raise RuntimeError("bottom view is missing a chamfer-offset foot datum edge")
    return x_axes[0], y_axes[0]


def _right_seat_edge(adapter: Any, view: Any) -> Any:
    """Return the mounting-face edge in the right view: the line at y = -HALF_Y
    running along Z. A coordinate pick at the trapezoid's bottom lands on the
    chamfer edges that share that sheet point, so the seat is found by geometry."""
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
        for edge in edges:
            edge = _early_bound(edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsLine():
                continue
            root_y, direction_z = (
                float(curve.LineParams[1]),
                abs(float(curve.LineParams[5])),
            )
            if abs(root_y + HALF_Y / 1000.0) <= 2e-6 and direction_z >= 0.99:
                start = _early_bound(edge.GetStartVertex(), "IVertex").GetPoint()
                end = _early_bound(edge.GetEndVertex(), "IVertex").GetPoint()
                candidates.append((abs(float(end[2]) - float(start[2])), edge))
    if not candidates:
        raise RuntimeError("right view has no model edge on the mounting-face plane")
    span, edge = max(candidates, key=lambda item: item[0])
    if span < (2.0 * WIDE - 2.0 * CHAMFER - 0.1) / 1000.0:
        raise RuntimeError(f"mounting-face edge spans only {span * 1000.0:.3f} mm")
    return edge


def _add_side_symmetry_centerline(adapter: Any) -> Any:
    """Draw the side-view centre plane that locates the taper and central web."""
    model = adapter.currentModel
    drawing = _early_bound(model, "IDrawingDoc")
    drawing.EditSheet()
    sketch_manager = _early_bound(model.SketchManager, "ISketchManager")
    extension = 0.004
    half_height = HALF_Y * VIEW_SCALE / 1000.0
    centerline = sketch_manager.CreateCenterLine(
        RIGHT_CENTER[0],
        RIGHT_CENTER[1] - half_height - extension,
        0.0,
        RIGHT_CENTER[0],
        RIGHT_CENTER[1] + half_height + extension,
        0.0,
    )
    if centerline is None:
        raise RuntimeError("failed to create side-view symmetry centerline")
    model.ClearSelection2(True)
    model.EditRebuild3()
    return centerline


def _remove_isometric_thread_callouts(adapter: Any, view: Any) -> int:
    """Delete the cosmetic-thread CALLOUT notes on the pictorial view.

    The four foot taps are one Hole Wizard feature whose cosmetic threads ride
    into every view. In the orthographic views they draw the thread circles
    the print needs; on the shaded isometric one thread also carries a generic
    "1/2-13 Tapped Hole" callout that repeats the native hole table. That
    callout is an ``INote`` reachable ONLY through ``ICThread.ThreadCallout``
    (never via ``GetFirstAnnotation3``, so a text-match note sweep finds 0),
    and the threads themselves only enumerate on the finalizer's rebuilt sheet
    — the ``place_view`` handle sees none, so the view is re-resolved by name.
    Returns the number of callouts deleted.
    """
    wanted = view_name(adapter, view)
    bound_view = next(
        _early_bound(v, "IView")
        for v in iter_views(adapter)
        if view_name(adapter, v) == wanted
    )
    # In-session the threads (and their callout) are unreachable until the
    # view has explicitly imported them; the export renders them regardless.
    seeds, _instances = import_cosmetic_threads(adapter, bound_view)
    callouts: list[Any] = []
    thread = bound_view.GetFirstCThread()
    while thread is not None:
        thread = _early_bound(thread, "ICThread")
        next_thread = thread.GetNext()
        note = thread.ThreadCallout
        if note is not None:
            callouts.append(_early_bound(note, "INote").GetAnnotation())
        thread = next_thread
    _telemetry.info(
        f"isometric: {seeds} cosmetic thread(s), {len(callouts)} callout(s)"
    )
    draw = adapter.currentModel
    removed = 0
    for annotation in callouts:
        annotation = _early_bound(annotation, "IAnnotation")
        draw.ClearSelection2(True)
        if not annotation.Select2(False, 0):
            raise RuntimeError("failed to select an isometric thread callout")
        draw.EditDelete()
        removed += 1
    draw.ClearSelection2(True)
    return removed


def _expect_one_callout_removed(removed: int) -> None:
    if removed != 1:
        raise RuntimeError(
            f"isometric view removed {removed} thread callout(s), expected 1"
        )


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
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 2))
    bottom = place_view(adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (front, right, bottom):
        set_hidden_lines_visible(adapter, view)
    set_hidden_lines_removed(adapter, iso)

    front_dimensions = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_dimensions = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    dimensions = [*front_dimensions, *right_dimensions]
    set_dimension_callouts(adapter, dimensions, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, dimensions, DIMENSION_PRECISION)
    if not auto_center_marks(adapter, bottom, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to bottom view")
    _add_side_symmetry_centerline(adapter)

    # The mounting face is the trapezoid's bottom edge in the right view. The
    # symbol sits below-right of the foot, past the 63.5 width dimension's
    # right extension line (x ~0.186 at 1:2), with the leader pinned to the
    # seat's right corner so it rises up-left without crossing that dimension.
    seat_y = RIGHT_CENTER[1] - HALF_Y * VIEW_SCALE / 1000.0
    seat_half_w = WIDE * VIEW_SCALE / 1000.0
    add_surface_finish(
        adapter,
        right,
        edge_entity=_right_seat_edge(adapter, right),
        symbol_xy=(RIGHT_CENTER[0] + seat_half_w + 0.030, seat_y - 0.030),
        control=surface_finish_by_key(SURFACE_FINISHES, "mounting_face"),
        label="mounting face finish",
        leader_attach_xy=(RIGHT_CENTER[0] + seat_half_w - 0.002, seat_y),
    )

    datum_x_axis, datum_y_axis = _bottom_datum_axes(adapter, bottom)
    # No position frame on this part (simplicity policy rule 3/4), so the hole
    # coordinates are ordinary two-place dimensions under the title block's
    # ±0.51 — NOT basic: a basic dimension is toleranced only by the frame it
    # feeds, and without one it has no tolerance at all.
    insert_hole_table(
        adapter,
        bottom,
        datum_xy=(
            BOTTOM_CENTER[0] - BOSS_DEPTH / 2.0 * VIEW_SCALE / 1000.0,
            BOTTOM_CENTER[1] - WIDE * VIEW_SCALE / 1000.0,
        ),
        hole_points=tuple(_bottom_sheet_xy(hole) for hole in HOLES),
        datum_axes=(datum_x_axis, datum_y_axis),
        expected_locations_mm=EXPECTED_HOLE_TABLE_LOCATIONS_MM,
        anchor_xy=HOLE_TABLE_ANCHOR,
        basic_locations=False,
        label="rocker-arm-support",
    )

    # x=0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127), which the re-centred frame rule
    # now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker-Arm Support Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # The cosmetic threads reach the views only on the finalizer's full
        # rebuild (the view's annotation list is EMPTY during authoring), so
        # the isometric's callout is removed there, right before export.
        pre_export=lambda: _expect_one_callout_removed(
            _remove_isometric_thread_callouts(adapter, iso)
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
