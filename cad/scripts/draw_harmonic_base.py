r"""Create the curated machinist drawing for the two-plate harmonic base.

The SLDPRT remains authoritative.  This recipe supplies only the base's views,
overall footprint dimensions, the mounting-hole table, and casting notes; every
shared sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The base is a one-piece gray-iron casting: an 18 x 11 in lower flange with a
centred 17.5 x 10.5 in upper pad (a 6.35 mm reveal per long side), four counterbored
lag-screw mounting holes, and nine assembly-drilled hardware seats.  The plate
is 457 mm long, so the whole sheet runs 1:2; the isometric drops to 1:4.

Run with SolidWorks open::

    uv run python cad\scripts\draw_harmonic_base.py harmonic-base
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    insert_hole_table,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_harmonic_base import (
    BLOCK_SCREW_HOLE_DIA,
    BLOCK_SCREW_XZ,
    CBORE_DIA,
    FOOT_SCREW_HOLE_DIA,
    FOOT_SCREW_XZ,
    HOLE_DIA,
    HOLE_XZ,
    PIVOT_SCREW_HOLE_DIA,
    PIVOT_SCREW_XZ,
    STOP_SCREW_HOLE_DIA,
    STOP_SCREW_XZ,
)
from harmonic_base_spec import BOTTOM_LENGTH, BOTTOM_WIDTH, STACK_HEIGHT
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["harmonic_base"]
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

SHEET_SCALE = (1.0, 2.0)          # 1:2 whole sheet (457 mm plate)
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]  # 0.5 plan/front sheet-metres-per-mm

# Sheet layout (meters).  The plan (top) carries the footprint + the hole
# pattern; the isometric (1:4) shows the two-plate stack + reveal in 3D (so no
# flat front view is needed -- the plate thicknesses are in note 2); the hole
# table sits upper-right and the notes fill the lower-left.  The plan runs at the
# sheet's 1:2; only the 1:4 isometric carries a scale note.
TOP_CENTER = (0.130, 0.170)
SIDE_CENTER = (0.345, 0.075)

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position (meters).  Only the bottom plate's overall footprint is marked.
TOP_KEEP = {
    "BottomLen": (TOP_CENTER[0], TOP_CENTER[1] + BOTTOM_WIDTH * VIEW_SCALE / 2000.0 + 0.008),
    "BottomWid": (TOP_CENTER[0] + BOTTOM_LENGTH * VIEW_SCALE / 2000.0 + 0.017, TOP_CENTER[1]),
}

# Hole-table origin corner (the plate's lower-left plan corner) + the four
# mounting-hole rim picks, all in sheet meters.  The native table reads each
# hole's real Ø13 THRU / counterbore callout and its X/Y station from the datum.
_DATUM_XY = (
    TOP_CENTER[0] - BOTTOM_LENGTH * VIEW_SCALE / 2000.0,
    TOP_CENTER[1] - BOTTOM_WIDTH * VIEW_SCALE / 2000.0,
)
HOLE_TABLE_ANCHOR = (0.274, 0.256)


def _plan_xy(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point for a plan station (machine X, Z in mm), top view."""
    return (
        TOP_CENTER[0] + x_mm * VIEW_SCALE / 1000.0,
        TOP_CENTER[1] - z_mm * VIEW_SCALE / 1000.0,
    )


def _hole_rim(x_mm: float, z_mm: float, diameter_mm: float) -> tuple[float, float]:
    """Sheet pick on a plan-view hole rim, offset in machine +X."""
    return _plan_xy(x_mm + diameter_mm / 2.0, z_mm)


ALL_HOLES = (
    *((x, z, HOLE_DIA) for x, z in HOLE_XZ),
    (*PIVOT_SCREW_XZ, PIVOT_SCREW_HOLE_DIA),
    (*STOP_SCREW_XZ, STOP_SCREW_HOLE_DIA),
    *((x, z, BLOCK_SCREW_HOLE_DIA) for x, z in BLOCK_SCREW_XZ),
    *((x, z, FOOT_SCREW_HOLE_DIA) for x, z in FOOT_SCREW_XZ),
)


def _visible_hole_table_entities(
    adapter: Any, view: Any
) -> tuple[Any, tuple[Any, ...], Any, Any]:
    """Return plan origin, hole rims, and the B/C datum edges."""
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    vertices: list[tuple[tuple[float, float, float], Any]] = []
    circles: list[tuple[float, float, float, Any]] = []
    lines: list[tuple[tuple[float, ...], Any]] = []

    for component in components:
        visible_vertices = adapter._attempt(
            lambda c=component: view.GetVisibleEntities2(c, 2),  # swViewEntityType_Vertex
            default=(),
        ) or ()
        for vertex in visible_vertices:
            vertex = _early_bound(vertex, "IVertex")
            point = tuple(float(value) for value in vertex.GetPoint())
            vertices.append((point, vertex))

        visible_edges = adapter._attempt(
            lambda c=component: view.GetVisibleEntities2(c, 1),  # swViewEntityType_Edge
            default=(),
        ) or ()
        for edge in visible_edges:
            edge = _early_bound(edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if curve.IsCircle():
                parameters = tuple(float(value) for value in curve.CircleParams)
                circles.append((parameters[0], parameters[2], parameters[6], edge))
                continue
            if curve.IsLine():
                parameters = tuple(float(value) for value in curve.LineParams)
                lines.append((parameters, edge))

    if not vertices:
        raise RuntimeError("harmonic-base plan has no visible footprint vertices")

    visible_counterbores = [
        (x_mm, z_mm)
        for x_mm, z_mm in HOLE_XZ
        if any(
            abs(x - x_mm / 1000.0)
            + abs(z - z_mm / 1000.0)
            + abs(radius - CBORE_DIA / 2000.0)
            <= 5e-5
            for x, z, radius, _edge in circles
        )
    ]
    if visible_counterbores:
        raise RuntimeError(
            "underside-only counterbore rims are visible in the top view: "
            f"{visible_counterbores!r}"
        )

    x_min = min(point[0] for point, _entity in vertices)
    z_max = max(point[2] for point, _entity in vertices)
    datum_candidates = [
        (point[1], entity)
        for point, entity in vertices
        if abs(point[0] - x_min) <= 2e-6 and abs(point[2] - z_max) <= 2e-6
    ]
    if not datum_candidates:
        raise RuntimeError(
            "harmonic-base plan has no visible lower-left outer vertex at "
            f"drawing-context X={x_min:g}, Z={z_max:g} m"
        )

    selected_edges: list[Any] = []
    used: set[int] = set()
    for x_mm, z_mm, diameter_mm in ALL_HOLES:
        expected = (
            x_mm / 1000.0,
            z_mm / 1000.0,
            diameter_mm / 2000.0,
        )
        candidates = sorted(
            (
                abs(x - expected[0])
                + abs(z - expected[1])
                + abs(radius - expected[2]),
                index,
                edge,
            )
            for index, (x, z, radius, edge) in enumerate(circles)
            if index not in used
        )
        if not candidates or candidates[0][0] > 5e-5:
            nearest = candidates[0][0] if candidates else None
            raise RuntimeError(
                "harmonic-base plan has no visible circular rim for hole "
                f"({x_mm:g}, {z_mm:g}) diameter {diameter_mm:g} mm; "
                f"nearest error={nearest!r} m"
            )
        _, index, edge = candidates[0]
        used.add(index)
        selected_edges.append(edge)

    datum_b_candidates = [
        edge
        for parameters, edge in lines
        if abs(parameters[2] - BOTTOM_WIDTH / 2000.0) <= 2e-6
        and abs(parameters[3]) >= 0.99
    ]
    datum_c_candidates = [
        edge
        for parameters, edge in lines
        if abs(parameters[0] + BOTTOM_LENGTH / 2000.0) <= 2e-6
        and abs(parameters[5]) >= 0.99
    ]
    if not datum_b_candidates or not datum_c_candidates:
        raise RuntimeError(
            "harmonic-base plan is missing a visible outer B/C datum edge"
        )

    return (
        max(datum_candidates, key=lambda candidate: candidate[0])[1],
        tuple(selected_edges),
        datum_b_candidates[0],
        datum_c_candidates[0],
    )


def _visible_side_datum_edges(adapter: Any, view: Any) -> tuple[Any, Any]:
    """Return the finished underside A and top-pad face edges in the side view."""
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    candidates: list[tuple[float, Any]] = []
    for component in components:
        edges = adapter._attempt(
            lambda c=component: view.GetVisibleEntities2(c, 1),
            default=(),
        ) or ()
        for edge in edges:
            edge = _early_bound(edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsLine():
                continue
            parameters = tuple(float(value) for value in curve.LineParams)
            if abs(parameters[3]) < 0.99:
                continue
            candidates.append((parameters[1], edge))

    def _at_height(height_m: float, label: str) -> Any:
        matching = [
            edge
            for y, edge in candidates
            if abs(y - height_m) <= 2e-6
        ]
        if not matching:
            raise RuntimeError(
                f"harmonic-base side view has no visible {label} edge at "
                f"model Y={height_m:g} m"
            )
        return matching[0]

    return _at_height(0.0, "underside datum A"), _at_height(
        STACK_HEIGHT / 1000.0, "top pad"
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open harmonic-base source", await adapter.open_model(str(SOURCE)))
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
            "Side View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Side View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Harmonic Base Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "harmonic base; two-plate; gray iron casting",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently auto-scale,
    # which shifts every coordinate-based pick on it.
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=(1, 4))
    for view in (top, side):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the base hole pattern")

    datum_entity, hole_entities, datum_b_edge, datum_c_edge = (
        _visible_hole_table_entities(adapter, top)
    )
    datum_a_edge, top_pad_edge = _visible_side_datum_edges(adapter, side)

    # One complete hole table: four underside counterbores followed by every
    # top-side blind swing/pinion seat. Non-basic X/Y headers let the title-block
    # tolerance govern A1-A4; note 4 supplies the tighter seat-only tolerance.
    insert_hole_table(
        adapter,
        top,
        datum_xy=_DATUM_XY,
        hole_points=tuple(_hole_rim(x, z, diameter) for x, z, diameter in ALL_HOLES),
        datum_entity=datum_entity,
        hole_entities=hole_entities,
        anchor_xy=HOLE_TABLE_ANCHOR,
        basic_locations=True,
        label="harmonic-base mounting",
    )
    add_datum_feature(
        adapter,
        side,
        symbol_xy=(0.285, SIDE_CENTER[1] - STACK_HEIGHT / 8000.0),
        datum="A",
        label="machined underside datum",
        entity=datum_a_edge,
        shoulder=True,
    )
    add_datum_feature(
        adapter,
        top,
        symbol_xy=(0.060, _DATUM_XY[1] - 0.010),
        datum="B",
        label="machined long-side datum",
        entity=datum_b_edge,
        shoulder=True,
    )
    add_datum_feature(
        adapter,
        top,
        symbol_xy=(_DATUM_XY[0] + 0.013, 0.190),
        datum="C",
        label="machined left-end datum",
        entity=datum_c_edge,
        shoulder=True,
    )
    add_feature_control_frame(
        adapter,
        top,
        frame_xy=(0.190, 0.098),
        characteristic="position",
        tolerance="0.20",
        datums=("A", "B", "C"),
        diameter=True,
        quantity="4X DIA 13 THRU HOLES",
        label="through-hole true position",
        entity=hole_entities[2],
    )
    add_feature_control_frame(
        adapter,
        top,
        frame_xy=(0.190, 0.085),
        characteristic="position",
        tolerance="0.20",
        datums=("A", "B", "C"),
        diameter=True,
        quantity="4X DIA 23 UNDERSIDE C'BORES",
        label="underside counterbore true position",
        entity=hole_entities[0],
    )
    add_feature_control_frame(
        adapter,
        top,
        frame_xy=(0.110, 0.085),
        characteristic="position",
        tolerance="0.50",
        datums=("A", "B", "C"),
        diameter=True,
        quantity="8X BLIND TAPPED HOLES",
        label="tapped-hole true position",
        entity=hole_entities[8],
    )
    add_feature_control_frame(
        adapter,
        top,
        frame_xy=(0.060, 0.112),
        characteristic="position",
        tolerance="0.50",
        datums=("A", "B", "C"),
        diameter=True,
        quantity="1X DIA 6.53 BLIND HOLE",
        label="unthreaded pilot-hole true position",
        entity=hole_entities[4],
    )
    add_feature_control_frame(
        adapter,
        top,
        frame_xy=(0.060, 0.090),
        characteristic="perpendicularity",
        tolerance="0.10",
        datums=("A",),
        label="datum B perpendicularity to A",
        entity=datum_b_edge,
    )
    add_feature_control_frame(
        adapter,
        top,
        frame_xy=(0.025, 0.085),
        characteristic="perpendicularity",
        tolerance="0.10",
        datums=("A", "B"),
        label="datum C perpendicularity to A and B",
        entity=datum_c_edge,
    )
    add_feature_control_frame(
        adapter,
        side,
        frame_xy=(0.295, 0.093),
        characteristic="flatness",
        tolerance="0.10",
        label="datum A flatness",
        entity=datum_a_edge,
    )
    add_feature_control_frame(
        adapter,
        side,
        frame_xy=(0.365, 0.093),
        characteristic="parallelism",
        tolerance="0.10",
        datums=("A",),
        label="top-pad parallelism to A",
        entity=top_pad_edge,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.062)
    add_property_linked_note(adapter, "Side View Note", 0.250, 0.090)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Harmonic Base Manufacturing Drawing",
        scale=SHEET_SCALE,
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=3,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
