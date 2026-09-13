r"""Create the curated machinist drawing for the two-plate harmonic base.

The SLDPRT remains authoritative.  This recipe supplies only the base's views,
native footprint/socket dimensions, the ordinary-coordinate mounting-hole table,
and manufacturing notes; every shared sheet/template, import, curation, and
export behavior lives in ``_drawing_common``.

The base is a stepped gray-iron frame with a raised rim, four column sockets,
and blind tapped hardware seats. The plate is 457 mm long, so the whole sheet
runs 1:4; the front elevation is also 1:4 and the pictorial isometric is 1:10.

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
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    create_section_view,
    create_view_theoretical_datum,
    curate_view_dimensions,
    finalize_drawing,
    insert_hole_table,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)

from _drawing_registry import DRAWINGS_BY_NAME
from build_harmonic_base import (
    BASE_CROSS_TAP_DRILL_DIA,
    BASE_CROSS_TAP_SPEC,
    BLOCK_SCREW_HOLE_DIA,
    BLOCK_SCREW_XZ,
    COLUMN_X,
    FOOT_SCREW_HOLE_DIA,
    FOOT_SCREW_XZ,
    HOLD_DOWN_TAP_DRILL_DIA,
    HOLE_XZ,
    LOCK_KNOB_XZ,
    LOCK_SCREW_HOLE_DIA,
    NAMEPLATE_SCREW_HOLE_DIA,
    NAMEPLATE_SCREW_XZ,
    PIVOT_SCREW_HOLE_DIA,
    PIVOT_SCREW_XZ,
    STOP_SCREW_HOLE_DIA,
    STOP_SCREW_XZ,
)
from harmonic_base_spec import (
    BOTTOM_FRONT_Z,
    BOTTOM_LENGTH,
    BOTTOM_REAR_Z,
    BOTTOM_WIDTH,
    LIP_W,
    RIM_TOP,
    STACK_HEIGHT,
    TOP_FRONT_Z,
    TOP_LENGTH,
    TOP_REAR_Z,
)
from frame_attachment_spec import (
    BASE_SCREW_SEAT_Z,
    BASE_SCREW_Y,
    CASTING_FULL_THREAD_DEPTH,
    CASTING_TAP_DRILL_DEPTH,
    COLUMN_SOCKET_DIAMETER,
)
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

SHEET_SCALE = (1.0, 4.0)  # 1:4 whole sheet keeps this data-dense print legible
PLAN_SCALE = SHEET_SCALE
VIEW_SCALE = PLAN_SCALE[0] / PLAN_SCALE[1]

if abs((BOTTOM_REAR_Z - BOTTOM_FRONT_Z) - BOTTOM_WIDTH) > 1e-12:
    raise AssertionError("base drawing extents disagree with the overall depth")

# Sheet layout (meters). The full-height native hole table owns the left
# column, where it may extend below the title-block top without entering that
# right-side keep-out. Views, controls, and notes occupy the remaining field.
TOP_CENTER = (0.230, 0.205)
SIDE_CENTER = (0.230, 0.145)
SECTION_CENTER = (0.360, 0.150)
ISO_SCALE = (1, 10)
ISO_CENTER = (0.350, 0.240)
SIDE_NOTE_XY = (0.170, 0.128)
SECTION_NOTE_XY = (0.385, 0.126)
ISO_NOTE_XY = (0.305, 0.212)

# Per-view survivors of the native marked-dimension import. Footprint and
# corner/edge-break dimensions live in the plan; plate thicknesses and the
# underside edge break live in the front elevation; socket/spotface depths and
# the pad-root fillet live only in section A-A.
TOP_KEEP = {
    "BottomLen": (
        TOP_CENTER[0],
        TOP_CENTER[1]
        + max(abs(BOTTOM_FRONT_Z), abs(BOTTOM_REAR_Z)) * VIEW_SCALE / 1000.0
        + 0.008,
    ),
    "TopLen": (
        TOP_CENTER[0],
        TOP_CENTER[1]
        + max(abs(TOP_FRONT_Z), abs(TOP_REAR_Z)) * VIEW_SCALE / 1000.0
        + 0.016,
    ),
    "BottomWid": (
        TOP_CENTER[0] + BOTTOM_LENGTH * VIEW_SCALE / 2000.0 + 0.017,
        TOP_CENTER[1],
    ),
    "TopWid": (
        TOP_CENTER[0] + TOP_LENGTH * VIEW_SCALE / 2000.0 + 0.030,
        TOP_CENTER[1],
    ),
    "PadCornerRadius": (TOP_CENTER[0] - 0.090, TOP_CENTER[1] + 0.030),
    "FlangeCornerRadius": (TOP_CENTER[0] + 0.075, TOP_CENTER[1] + 0.030),
    "RimInnerCornerRadius": (TOP_CENTER[0] + 0.015, TOP_CENTER[1] - 0.050),
    "TopRimChamfer": (TOP_CENTER[0] + 0.075, TOP_CENTER[1] - 0.020),
    "Socket0X": (TOP_CENTER[0] - 0.050, TOP_CENTER[1] - 0.050),
    "Socket0Z": (TOP_CENTER[0] - 0.085, TOP_CENTER[1]),
    "SocketDia": (TOP_CENTER[0] - 0.058, TOP_CENTER[1] + 0.043),
}
SIDE_KEEP = {
    "BottomThickness": (SIDE_CENTER[0] - 0.085, SIDE_CENTER[1]),
    "TopThickness": (SIDE_CENTER[0] + 0.075, SIDE_CENTER[1]),
    "BottomEdgeChamfer": (SIDE_CENTER[0] + 0.075, SIDE_CENTER[1] - 0.018),
}
SECTION_KEEP = {
    "SocketDepth": (SECTION_CENTER[0] - 0.040, SECTION_CENTER[1]),
    "SpotFaceDia": (SECTION_CENTER[0] + 0.040, SECTION_CENTER[1] + 0.010),
    "SpotFaceDepth": (SECTION_CENTER[0] + 0.038, SECTION_CENTER[1] - 0.010),
    "PadRootRadius": (SECTION_CENTER[0] - 0.040, SECTION_CENTER[1] + 0.015),
}
DIMENSION_CALLOUTS = {
    "SocketDia": "4X COLUMN SOCKET; FIT MHA-083 TUBE COLUMN",
    "SpotFaceDia": "4X SPOTFACE",
}

# Hole-table origin is the finished plate's lower-left theoretical sharp
# corner.  The physical corner is filleted, so the native table is seeded from
# the two visible outer edges and reattached to a retained view point at their
# virtual intersection.
_TABLE_ORIGIN_XY = (
    TOP_CENTER[0] - BOTTOM_LENGTH * VIEW_SCALE / 2000.0,
    TOP_CENTER[1] - BOTTOM_REAR_Z * VIEW_SCALE / 1000.0,
)
HOLE_TABLE_ANCHOR = (0.015, 0.265)


def _plan_xy(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point for a plan station (machine X, Z in mm), top view."""
    return (
        TOP_CENTER[0] + x_mm * VIEW_SCALE / 1000.0,
        TOP_CENTER[1] - z_mm * VIEW_SCALE / 1000.0,
    )


def _front_y(y_mm: float) -> float:
    """Sheet Y for a model-Y point in the bbox-centred front elevation."""
    return SIDE_CENTER[1] + (y_mm - RIM_TOP / 2.0) * VIEW_SCALE / 1000.0


def _section_y(y_mm: float) -> float:
    """Sheet Y for a section point spanning the lower plate to the deck."""
    return SECTION_CENTER[1] + (y_mm - STACK_HEIGHT / 2.0) * VIEW_SCALE / 1000.0


def _hole_rim(x_mm: float, z_mm: float, diameter_mm: float) -> tuple[float, float]:
    """Sheet pick on a plan-view hole rim, offset in machine +X."""
    return _plan_xy(x_mm + diameter_mm / 2.0, z_mm)


ALL_HOLES = (
    *((x, z, HOLD_DOWN_TAP_DRILL_DIA) for x, z in HOLE_XZ),
    (*PIVOT_SCREW_XZ, PIVOT_SCREW_HOLE_DIA),
    (*STOP_SCREW_XZ, STOP_SCREW_HOLE_DIA),
    *((x, z, BLOCK_SCREW_HOLE_DIA) for x, z in BLOCK_SCREW_XZ),
    *((x, z, FOOT_SCREW_HOLE_DIA) for x, z in FOOT_SCREW_XZ),
    # Keep later seat groups after the earlier mounting-seat groups.
    *((x, z, NAMEPLATE_SCREW_HOLE_DIA) for x, z in NAMEPLATE_SCREW_XZ),
    (*LOCK_KNOB_XZ, LOCK_SCREW_HOLE_DIA),
)


def _visible_hole_table_entities(
    adapter: Any, view: Any
) -> tuple[tuple[Any, ...], Any, Any]:
    """Return hole rims and the two outer edges used as ordinary table axes.

    The plan corners are broken by the modelled corner radii, so no finished
    vertex exists at the table origin.  The caller supplies these visible
    outer edges to establish their virtual intersection, while the retained
    view point makes that same theoretical corner visible on the sheet.
    """
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    circles: list[tuple[float, float, float, Any]] = []
    lines: list[tuple[tuple[float, ...], Any]] = []

    for component in components:
        visible_edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(
                    c, 1
                ),  # swViewEntityType_Edge
                default=(),
            )
            or ()
        )
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
                abs(x - expected[0]) + abs(z - expected[1]) + abs(radius - expected[2]),
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

    x_axis_candidates = [
        edge
        for parameters, edge in lines
        if abs(parameters[2] - BOTTOM_REAR_Z / 1000.0) <= 2e-6
        and abs(parameters[3]) >= 0.99
    ]
    y_axis_candidates = [
        edge
        for parameters, edge in lines
        if abs(parameters[0] + BOTTOM_LENGTH / 2000.0) <= 2e-6
        and abs(parameters[5]) >= 0.99
    ]
    if not x_axis_candidates or not y_axis_candidates:
        raise RuntimeError(
            "harmonic-base plan is missing a visible outer table-axis edge"
        )

    return (
        tuple(selected_edges),
        x_axis_candidates[0],
        y_axis_candidates[0],
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
            "Section View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Side View Note",
            "Section View Note",
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
            0: "Harmonic Base Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "harmonic base; stepped; gray-iron frame",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    if not extension.SetUserPreferenceInteger(542, 0, 1):
        raise RuntimeError("failed to set end-only section cutting line")
    if extension.GetUserPreferenceInteger(542, 0) != 1:
        raise RuntimeError("section cutting-line style did not persist")

    # Explicit per-view scale prevents coordinate-based picks drifting.
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=PLAN_SCALE)
    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=(1, 4))
    section_line_x = _plan_xy(COLUMN_X, 0.0)[0]
    section = create_section_view(
        adapter,
        top,
        line_start=(section_line_x, TOP_CENTER[1] - 0.040),
        line_end=(section_line_x, TOP_CENTER[1] + 0.040),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(1, 4),
        label="base column-socket section",
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (top, side, section, iso):
        set_hidden_lines_removed(adapter, view)

    top_dimensions = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    side_dimensions = curate_view_dimensions(
        adapter, side, keep=SIDE_KEEP, view_label="front elevation"
    )
    section_dimensions = curate_view_dimensions(
        adapter, section, keep=SECTION_KEEP, view_label="section A-A"
    )
    set_dimension_callouts(
        adapter,
        [*top_dimensions, *side_dimensions, *section_dimensions],
        DIMENSION_CALLOUTS,
    )
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the base hole pattern")

    table_origin = create_view_theoretical_datum(
        adapter,
        top,
        point_xy=(-BOTTOM_LENGTH / 2000.0, -BOTTOM_REAR_Z / 1000.0),
        label="harmonic-base finished-corner table origin",
    )
    hole_entities, table_x_axis, table_y_axis = _visible_hole_table_entities(
        adapter, top
    )

    # One complete hole table for the top-side mounting seats. Section A-A
    # separately defines the horizontal column-retention taps.
    insert_hole_table(
        adapter,
        top,
        datum_xy=_TABLE_ORIGIN_XY,
        datum_point=table_origin,
        hole_points=tuple(_hole_rim(x, z, diameter) for x, z, diameter in ALL_HOLES),
        datum_axes=(table_x_axis, table_y_axis),
        hole_entities=hole_entities,
        # Every printed LOC is re-derived from the shared stations: X from the
        # finished left edge, Y from the finished rear edge.
        expected_locations_mm=tuple(
            (x + BOTTOM_LENGTH / 2.0, BOTTOM_WIDTH / 2.0 - z)
            for x, z, _diameter in ALL_HOLES
        ),
        anchor_xy=HOLE_TABLE_ANCHOR,
        basic_locations=False,
        label="harmonic-base mounting",
    )
    tap_edge = model_point_in_view(
        adapter,
        section,
        (
            COLUMN_X / 1000.0,
            (BASE_SCREW_Y + BASE_CROSS_TAP_DRILL_DIA / 2.0) / 1000.0,
            (BASE_SCREW_SEAT_Z - COLUMN_SOCKET_DIAMETER) / 1000.0,
        ),
        label="base cross-tap longitudinal edge",
    )
    add_native_hole_callout(
        adapter,
        section,
        edge_xy=tap_edge,
        callout_xy=(0.300, 0.105),
        label="4X base column-retention bottoming taps",
        process=(
            f"4X {BASE_CROSS_TAP_SPEC.size} UNF-{BASE_CROSS_TAP_SPEC.thread_class} "
            f"BOTTOMING TAP; FULL THREAD {CASTING_FULL_THREAD_DEPTH:.2f}; "
            f"CYLINDRICAL DRILL {CASTING_TAP_DRILL_DEPTH:.2f}"
        ),
    )
    # Derived envelope features are dimensioned from their finished model
    # edges, not repeated in a note: the symmetric reveal, raised-rim width,
    # deck height, and overall rim height.
    add_edge_dimension(
        adapter,
        top,
        p0=_plan_xy(BOTTOM_LENGTH / 2.0, 0.0),
        p1=_plan_xy(TOP_LENGTH / 2.0, 0.0),
        text_xy=(TOP_CENTER[0] + 0.085, TOP_CENTER[1] - 0.042),
        orientation="horizontal",
        label="plate side reveal",
    )
    add_edge_dimension(
        adapter,
        top,
        p0=_plan_xy(TOP_LENGTH / 2.0, 0.0),
        p1=_plan_xy(TOP_LENGTH / 2.0 - LIP_W, 0.0),
        text_xy=(TOP_CENTER[0] + 0.045, TOP_CENTER[1] - 0.042),
        orientation="horizontal",
        label="raised rim width",
    )
    add_edge_dimension(
        adapter,
        section,
        p0=(SECTION_CENTER[0], _section_y(0.0)),
        p1=(SECTION_CENTER[0], _section_y(STACK_HEIGHT)),
        text_xy=(SECTION_CENTER[0] - 0.050, SECTION_CENTER[1]),
        orientation="vertical",
        label="deck height",
    )
    # Keep the vertical overall dimension outside the front-view silhouette.
    add_edge_dimension(
        adapter,
        side,
        p0=(SIDE_CENTER[0], _front_y(0.0)),
        p1=(SIDE_CENTER[0], _front_y(RIM_TOP)),
        text_xy=(SIDE_CENTER[0] - 0.085, SIDE_CENTER[1]),
        orientation="vertical",
        label="overall rim height",
    )

    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.170, 0.115, char_height=0.002
    )
    add_property_linked_note(adapter, "Side View Note", *SIDE_NOTE_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    add_property_linked_note(adapter, "Section View Note", *SECTION_NOTE_XY)

    # Curation and note insertion can leave the orthographic edge cache stale.
    # Reassert HLV only after every annotation is in place.
    for view in (top, side):
        set_hidden_lines_visible(adapter, view)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Harmonic Base Manufacturing Drawing",
        scale=SHEET_SCALE,
        redundant_note_substrings=("Tapped Hole",),
        # Seven top-side tapped groups plus the sectioned cross-tap group.
        expected_redundant_notes=8,
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
