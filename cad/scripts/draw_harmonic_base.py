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
    set_reference_dimension,
    stamp_drawing_summary,
    visible_view_entities,
    view_name,
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
    "BottomEdgeChamfer": (TOP_CENTER[0] + 0.075, TOP_CENTER[1] - 0.020),
    "Socket0X": (TOP_CENTER[0] - 0.050, TOP_CENTER[1] - 0.050),
    "Socket0Z": (TOP_CENTER[0] - 0.085, TOP_CENTER[1]),
    "SocketDia": (TOP_CENTER[0] - 0.058, TOP_CENTER[1] + 0.043),
}
SIDE_KEEP = {
    "BottomThickness": (SIDE_CENTER[0] - 0.085, SIDE_CENTER[1]),
    "TopThickness": (SIDE_CENTER[0] + 0.075, SIDE_CENTER[1]),
    "TopRimChamfer": (SIDE_CENTER[0] + 0.075, SIDE_CENTER[1] + 0.018),
}
SECTION_KEEP = {
    "SocketDepth": (SECTION_CENTER[0] - 0.040, SECTION_CENTER[1]),
    "SpotFaceDia": (SECTION_CENTER[0] + 0.040, SECTION_CENTER[1] + 0.010),
    "SpotFaceDepth": (SECTION_CENTER[0] + 0.038, SECTION_CENTER[1] - 0.010),
    "PadRootRadius": (SECTION_CENTER[0] - 0.040, SECTION_CENTER[1] + 0.015),
}
DIMENSION_CALLOUTS = {
    "TopLen": "PAD CENTERED ON FLANGE",
    "SocketDia": "4X COLUMN SOCKET; FIT MHA-083 TUBE; SLIP BY HAND",
    "TopRimChamfer": "X 45 DEG; UPPER RIM EDGES",
    "BottomEdgeChamfer": "X 45 DEG; UNDERSIDE EDGES",
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


def _hole_rim(x_mm: float, z_mm: float, diameter_mm: float) -> tuple[float, float]:
    """Sheet pick on a plan-view hole rim, offset in machine +X."""
    return _plan_xy(x_mm + diameter_mm / 2.0, z_mm)


@_telemetry.traced("drawing.base_cross_tap_edge")
def _cross_tap_edge(view: Any) -> Any:
    """Pick the tap entry itself, not the nearby larger spotface circle."""
    center = (COLUMN_X / 1000.0, BASE_SCREW_Y / 1000.0, BASE_SCREW_SEAT_Z / 1000.0)
    radius = BASE_CROSS_TAP_DRILL_DIA / 2000.0
    matches = []
    for raw in visible_view_entities(view, 1, label="base cross-tap entry"):
        edge = _early_bound(raw, "IEdge")
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if not curve.IsCircle():
            continue
        values = tuple(float(value) for value in curve.CircleParams)
        if abs(values[6] - radius) > 1e-7:
            continue
        if any(abs(values[index] - center[index]) > 1e-7 for index in range(3)):
            continue
        if abs(abs(values[5]) - 1.0) > 1e-7:
            continue
        matches.append(edge)
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one base cross-tap entry edge, found {len(matches)}"
        )
    return matches[0]


@_telemetry.traced("drawing.base_cross_tap_readback")
def _check_cross_tap_callout(display: Any) -> None:
    expected = {
        "hw-tapdrldia": BASE_CROSS_TAP_DRILL_DIA,
        "hw-tapdrldepth": BASE_CROSS_TAP_SPEC.depth_mm,
        "hw-threaddepth": BASE_CROSS_TAP_SPEC.overrides_mm["ThreadDepth"],
    }
    found = set()
    for raw in display.GetHoleCalloutVariables() or ():
        variable = _early_bound(raw, "ICalloutVariable")
        name = str(variable.VariableName)
        if name not in expected:
            continue
        length = _early_bound(raw, "ICalloutLengthVariable")
        actual_mm = float(length.Length) * 1000.0
        if abs(actual_mm - expected[name]) > 1e-5:
            raise RuntimeError(
                f"base tap callout {name}: {actual_mm} != {expected[name]} mm"
            )
        found.add(name)
    if found != set(expected):
        raise RuntimeError(
            f"base tap callout is missing native variables: {set(expected) - found}"
        )


@_telemetry.traced("drawing.base_rim_width")
def _add_rim_width(adapter: Any, view: Any) -> Any:
    """Measure the two unchamfered rim-wall stations through exact model edges."""
    stations = (TOP_LENGTH / 2000.0, (TOP_LENGTH / 2.0 - LIP_W) / 1000.0)
    candidates: list[list[tuple[float, Any]]] = [[], []]
    for raw in visible_view_entities(view, 1, label="base rim wall edges"):
        edge = _early_bound(raw, "IEdge")
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if not curve.IsLine():
            continue
        values = tuple(float(value) for value in edge.GetCurveParams2())
        x0, y0, z0, x1, y1, z1 = values[:6]
        if abs(x0 - x1) > 1e-7 or abs(y0 - y1) > 1e-7 or z0 * z1 > 0:
            continue
        if not STACK_HEIGHT / 1000.0 - 1e-7 <= y0 <= RIM_TOP / 1000.0 + 1e-7:
            continue
        for index, station in enumerate(stations):
            if abs(x0 - station) <= 1e-7:
                candidates[index].append((y0, edge))
    if any(not items for items in candidates):
        raise RuntimeError("base rim width lacks exact outer/inner wall edges")
    drawing = adapter.currentModel
    if not _early_bound(drawing, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate base rim view")
    drawing.ClearSelection2(True)
    for index, items in enumerate(candidates):
        edge = max(items, key=lambda item: item[0])[1]
        if not view.SelectEntity(edge, index > 0):
            raise RuntimeError(f"failed to select base rim wall {index}")
    display = drawing.AddHorizontalDimension2(
        TOP_CENTER[0] + 0.045, TOP_CENTER[1] - 0.042, 0.0
    )
    drawing.ClearSelection2(True)
    if display is None:
        raise RuntimeError("failed to create base rim-width dimension")
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    actual_mm = float(dimension.SystemValue) * 1000.0
    if abs(actual_mm - LIP_W) > 1e-5:
        raise RuntimeError(f"base rim width measured {actual_mm}, expected {LIP_W} mm")
    return display


@_telemetry.traced("drawing.base_iso_annotation_visibility")
def _hide_iso_annotations(view: Any) -> None:
    for raw in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        annotation.Visible = 3  # swAnnotationHidden
        if int(annotation.Visible) != 3:
            raise RuntimeError("base isometric annotation did not hide")


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
    tap_callout = add_native_hole_callout(
        adapter,
        side,
        edge=_cross_tap_edge(side),
        callout_xy=(0.300, 0.105),
        label="base column-retention taps",
        process="FRONT AND REAR",
    )
    _check_cross_tap_callout(tap_callout)
    # Derived envelope features are dimensioned from their finished model
    # edges, not repeated in a note: the symmetric reveal, raised-rim width,
    # deck height, and overall rim height.
    reveal_dimension = add_edge_dimension(
        adapter,
        top,
        p0=_plan_xy(BOTTOM_LENGTH / 2.0, 0.0),
        p1=_plan_xy(TOP_LENGTH / 2.0, 0.0),
        text_xy=(TOP_CENTER[0] + 0.085, TOP_CENTER[1] - 0.042),
        orientation="horizontal",
        label="plate side reveal",
    )
    set_reference_dimension(
        adapter,
        _early_bound(reveal_dimension, "IDisplayDimension").GetAnnotation(),
        label="derived plate side reveal",
    )
    _add_rim_width(adapter, top)
    deck_dimension = add_edge_dimension(
        adapter,
        section,
        p0=model_point_in_view(
            adapter,
            section,
            (COLUMN_X / 1000.0, 0.0, 0.0),
            label="base section underside",
        ),
        p1=model_point_in_view(
            adapter,
            section,
            (COLUMN_X / 1000.0, STACK_HEIGHT / 1000.0, 0.0),
            label="base section deck",
        ),
        text_xy=(SECTION_CENTER[0] + 0.050, SECTION_CENTER[1]),
        orientation="vertical",
        label="deck height",
    )
    set_reference_dimension(
        adapter,
        _early_bound(deck_dimension, "IDisplayDimension").GetAnnotation(),
        label="derived deck height",
    )
    # Keep the vertical overall dimension outside the front-view silhouette.
    add_edge_dimension(
        adapter,
        side,
        p0=model_point_in_view(
            adapter,
            side,
            (0.0, 0.0, 0.0),
            label="base front underside",
        ),
        p1=model_point_in_view(
            adapter,
            side,
            (0.0, RIM_TOP / 1000.0, 0.0),
            label="base front rim top",
        ),
        text_xy=(SIDE_CENTER[0] - 0.105, SIDE_CENTER[1]),
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
    _hide_iso_annotations(iso)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Harmonic Base Manufacturing Drawing",
        scale=SHEET_SCALE,
        redundant_note_substrings=("Tapped Hole",),
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
