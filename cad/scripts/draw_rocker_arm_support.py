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
    add_edge_dimension,
    add_property_linked_note,
    add_surface_finish,
    create_section_view,
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
    HOLE_TAP_DRILL_DIA,
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
# and web at the front view's centre cut; the tapping setup stays below. The
# projected group clears the zone strip, with room for dimensions and leaders.
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
    "WebThickness": 2,  # a held thickness: 6.35, routine ±0.51
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
    # swDetailingSectionViewLineStyleDisplay (swconst.tlb R2026x): standard
    # without connector. The end segments/arrows identify the centre cut
    # without drawing a line through the front view's square-callout text.
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
            if name != "WebThickness"
        },
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
    if not auto_center_marks(adapter, bottom, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to bottom view")

    # The mounting face is the trapezoid's visible bottom edge in section A-A. The
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
        char_height=0.0025,
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
    # The datum walk + hole table leave the bottom view's HLV edge set stale (it exported the four tap circles and
    # nothing of the pocket/cavity/web above them).
    set_hidden_lines_visible(adapter, bottom)

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
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
