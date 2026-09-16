r"""Create the curated machinist drawing for the two-plate harmonic base.

The SLDPRT remains authoritative.  This recipe supplies only the base's views,
native footprint/socket dimensions, the ordinary-coordinate mounting-hole table,
and manufacturing notes; every shared sheet/template, import, curation, and
export behavior lives in ``_drawing_common``.

The base is a stepped gray-iron frame with a raised rim, four column sockets,
and blind tapped hardware seats. The plate is 457 mm long, so the whole sheet
runs 1:4; the front elevation is also 1:4 and the pictorial isometric is 1:6.

Run with SolidWorks open::

    uv run python cad\scripts\draw_harmonic_base.py harmonic-base
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from win32com.client.dynamic import Dispatch as dynamic_dispatch

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    create_blank_drawing_sheets,
    create_section_view,
    create_view_theoretical_datum,
    curate_view_dimensions,
    finalize_drawing,
    dimension_name,
    insert_hole_table,
    import_cosmetic_threads,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
    visible_view_entities,
    view_name,
)

from _drawing_registry import DRAWINGS_BY_NAME
from _part_pmi import _resolve_faces
from _surface_finish import surface_finish_by_key
from build_harmonic_base import (
    BASE_CROSS_TAP_DRILL_DIA,
    BASE_CROSS_TAP_SPEC,
    BASE_SPOTFACE_DEPTH,
    BASE_SPOTFACE_PLANE_Z,
    BLOCK_SCREW_HOLE_DIA,
    BLOCK_SCREW_XZ,
    COLUMN_X,
    COLUMN_SOCKET_XZ,
    COLUMN_SOCKET_DIAMETER,
    FOOT_SCREW_HOLE_DIA,
    FOOT_SCREW_XZ,
    HOLD_DOWN_TAP_DRILL_DIA,
    HOLE_XZ,
    LOCK_KNOB_XZ,
    LOCK_SCREW_HOLE_DIA,
    NAMEPLATE_SCREW_HOLE_DIA,
    NAMEPLATE_SCREW_XZ,
    RIM_CHAMFER,
    SERIAL_HEIGHT_MM,
    SERIAL_TEXT,
    SERIAL_XZ,
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
    BOTTOM_THICKNESS,
    DRAWING_NOTES,
    LIP_H,
    LIP_W,
    RIM_TOP,
    STACK_HEIGHT,
    SURFACE_FINISHES,
    TOP_LENGTH,
)
from frame_attachment_spec import (
    BASE_SCREW_SEAT_Z,
    BASE_SCREW_Y,
    SCREW_SPOTFACE_DIAMETER,
)
from solidworks_mcp.adapters.com_variant import dispatch_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
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

SHEET_SCALE = (1.0, 4.0)
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]
SHEET_NAMES = ("GEOMETRY", "HOLES-SOCKETS")

if abs((BOTTOM_REAR_Z - BOTTOM_FRONT_Z) - BOTTOM_WIDTH) > 1e-12:
    raise AssertionError("base drawing extents disagree with the overall depth")

# Two landscape B sheets keep each annotation authoritative and readable:
# exterior geometry on sheet 1; the associative hole table, sockets and
# cross-taps on sheet 2.
TOP_CENTER = (0.145, 0.185)
SIDE_CENTER = (0.145, 0.100)
# The isometric owns the whole field right of the sheet-1 dimension envelope
# (x 0.275-0.410, y 0.070-0.265). At 1:6 the pictorial spans ~0.083 x 0.041,
# so it is centred in that region instead of floating above a dead strip.
ISO_SCALE = (1, 6)
ISO_CENTER = (0.3425, 0.175)
HOLE_TOP_CENTER = (0.280, 0.195)
HOLE_SIDE_CENTER = (0.280, 0.095)
SECTION_CENTER = (0.375, 0.135)
HOLE_TABLE_ANCHOR = (0.018, 0.260)

# Per-view survivors of the native marked-dimension import. Sheet 1 owns the
# exterior envelope and edge geometry. Sheet 2 owns socket and hole definition.
GEOMETRY_TOP_KEEP = {
    "BottomLen": (TOP_CENTER[0], 0.244),
    "TopLen": (TOP_CENTER[0], 0.230),
    "BottomWid": (0.238, 0.172),
    "TopWid": (0.217, 0.200),
    "PadCornerRadius": (0.070, 0.236),
    "FlangeCornerRadius": (0.040, 0.215),
    "RimInnerCornerRadius": (0.050, 0.232),
}
SIDE_KEEP = {
    "BottomThickness": (0.073, 0.085),
}
HOLE_TOP_KEEP: dict[str, tuple[float, float]] = {}
SECTION_KEEP: dict[str, tuple[float, float]] = {}
GEOMETRY_CALLOUTS = {
    "TopLen": "PAD CENTERED ON FLANGE",
    "PadCornerRadius": "PAD",
    "FlangeCornerRadius": "FLANGE",
    "RimInnerCornerRadius": "RIM INNER",
}

# Native table tags keep their source association while short leaders separate
# the closely spaced screw patterns. Coordinates below are sheet layout only.
HOLE_TAG_POSITIONS = {
    "A3": (0.325, 0.176),
    "A4": (0.326, 0.215),
    "C1": (0.247, 0.216),
    "D1": (0.247, 0.187),
    "E1": (0.257, 0.155),
    "E2": (0.262, 0.226),
    "E3": (0.287, 0.192),
    "F1": (0.265, 0.192),
    "F2": (0.277, 0.224),
    "F3": (0.287, 0.155),
    "F4": (0.293, 0.223),
    "G1": (0.306, 0.187),
    "G2": (0.289, 0.206),
    "G3": (0.312, 0.173),
    "G4": (0.312, 0.214),
    "H3": (0.343, 0.181),
    "H4": (0.343, 0.214),
}

# Hole-table origin is the finished plate's lower-left theoretical sharp
# corner. The physical corner is filleted, so the native table is seeded from
# the two visible outer edges and reattached to a retained view point there.
_TABLE_ORIGIN_XY = (
    HOLE_TOP_CENTER[0] - BOTTOM_LENGTH * VIEW_SCALE / 2000.0,
    HOLE_TOP_CENTER[1] - BOTTOM_REAR_Z * VIEW_SCALE / 1000.0,
)


def _plan_xy(
    x_mm: float, z_mm: float, *, center: tuple[float, float] = TOP_CENTER
) -> tuple[float, float]:
    """Sheet point for a machine X/Z station in one top view."""
    return (
        center[0] + x_mm * VIEW_SCALE / 1000.0,
        center[1] - z_mm * VIEW_SCALE / 1000.0,
    )


def _hole_rim(x_mm: float, z_mm: float, diameter_mm: float) -> tuple[float, float]:
    """Sheet pick on a hole-sheet plan rim, offset in machine +X."""
    return _plan_xy(x_mm + diameter_mm / 2.0, z_mm, center=HOLE_TOP_CENTER)


@_telemetry.traced("drawing.base_cross_tap_edge")
def _cross_tap_edge(view: Any, *, x_mm: float = COLUMN_X) -> Any:
    """Pick the tap entry itself, not the nearby larger spotface circle."""
    center = (x_mm / 1000.0, BASE_SCREW_Y / 1000.0, BASE_SCREW_SEAT_Z / 1000.0)
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


def _add_cross_spotface_dimension(adapter: Any, view: Any) -> None:
    """Dimension the actual front spotface entry, not its section projection."""
    center = (-COLUMN_X / 1000.0, BASE_SCREW_Y / 1000.0, BASE_SPOTFACE_PLANE_Z / 1000.0)
    matches = []
    for raw in visible_view_entities(view, 1, label="base front spotface entry"):
        edge = _early_bound(raw, "IEdge")
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if not curve.IsCircle():
            continue
        values = tuple(float(value) for value in curve.CircleParams)
        if (
            abs(values[6] - SCREW_SPOTFACE_DIAMETER / 2000.0) < 1e-7
            and all(abs(values[index] - center[index]) < 1e-7 for index in range(3))
            and abs(abs(values[5]) - 1.0) < 1e-7
        ):
            matches.append(edge)
    if len(matches) != 1:
        raise RuntimeError(f"expected one actual front spotface entry, found {len(matches)}")
    drawing = adapter.currentModel
    if not _early_bound(drawing, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate front spotface view")
    drawing.ClearSelection2(True)
    if not view.SelectEntity(matches[0], False):
        raise RuntimeError("failed to select the actual front spotface circle")
    display = drawing.AddDiameterDimension2(0.193, 0.135, 0.0)
    drawing.ClearSelection2(True)
    if display is None:
        raise RuntimeError("failed to dimension the actual front spotface")
    display = _early_bound(display, "IDisplayDimension")
    actual_mm = float(_early_bound(display.GetDimension2(0), "IDimension").SystemValue) * 1000.0
    if abs(actual_mm - SCREW_SPOTFACE_DIAMETER) > 1e-5:
        raise RuntimeError(f"front spotface measured {actual_mm}, expected {SCREW_SPOTFACE_DIAMETER} mm")
    caption = (
        "4X SPOTFACE\nCROSS-SCREW HOLES\nFRONT/REAR\n"
        f"{BASE_SPOTFACE_DEPTH:.2f} DEEP"
    )
    display.SetText(4, caption)
    display.SetPrecision3(1, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != 1 or str(display.GetText(4)) != caption:
        raise RuntimeError("front spotface precision or caption did not persist")


@_telemetry.traced("drawing.base_cross_tap_readback")
def _check_cross_tap_callout(display: Any) -> None:
    expected = {
        "hw-tapdrldia": BASE_CROSS_TAP_DRILL_DIA,
        "hw-tapdrldepth": BASE_CROSS_TAP_SPEC.depth_mm,
        "hw-threaddepth": BASE_CROSS_TAP_SPEC.overrides_mm["ThreadDepth"],
    }
    expected_strings = {
        "hw-threaddesc": "10-32 UNF",
        "hw-threadclass": BASE_CROSS_TAP_SPEC.thread_class,
    }
    found = set()
    for raw in display.GetHoleCalloutVariables() or ():
        late = dynamic_dispatch(raw._oleobj_)
        name = str(late.VariableName)
        if name in expected_strings:
            if int(late.Type) != 3:
                raise RuntimeError(f"base tap callout {name} is not a string variable")
            actual = str(_early_bound(raw, "ICalloutStringVariable").String or "")
            if actual.strip(" -") != expected_strings[name]:
                raise RuntimeError(
                    f"base tap callout {name}: {actual!r} != {expected_strings[name]!r}"
                )
            found.add(name)
            continue
        if name not in expected:
            raise RuntimeError(f"unexpected base tap callout variable {name!r}")
        if int(late.Type) != 1:
            raise RuntimeError(f"base tap callout {name} is not a length variable")
        length = _early_bound(raw, "ICalloutLengthVariable")
        actual_mm = float(length.Length) * 1000.0
        if abs(actual_mm - expected[name]) > 1e-5:
            raise RuntimeError(
                f"base tap callout {name}: {actual_mm} != {expected[name]} mm"
            )
        found.add(name)
    required = set(expected) | set(expected_strings)
    if found != required:
        raise RuntimeError(
            f"base tap callout is missing native variables: {required - found}"
        )


def _set_cross_tap_total_quantity(display: Any) -> None:
    """Aggregate both two-hole features without resolving their size/depth tokens."""
    definitions = {
        definition_part: str(display.GetText(definition_part) or "")
        for definition_part in (5, 6, 7, 8)
    }
    # swDimensionTextCalloutAboveDefinition=7 pairs with writable
    # swDimensionTextCalloutAbove=3; the raw count is not its resolved "2X".
    definition = definitions[7]
    if (
        not definition.lstrip().startswith("<NUM_INST>X ")
        or definition.count("<NUM_INST>") != 1
        or "<hw-tapdrldia>" not in definition
        or "<hw-tapdrldepth>" not in definition
        or not str(display.GetText(3) or "").lstrip().startswith("2X ")
    ):
        raise RuntimeError(f"expected one native two-instance drill definition: {definitions!r}")
    quantity = len(COLUMN_SOCKET_XZ)
    updated = definition.replace("<NUM_INST>", str(quantity), 1)
    display.SetText(3, updated)
    if (
        str(display.GetText(7)) != updated
        or not str(display.GetText(3)).lstrip().startswith(f"{quantity}X ")
        or any(
            str(display.GetText(part) or "") != definitions[part]
            for part in (5, 6, 8)
        )
    ):
        raise RuntimeError("aggregate cross-tap quantity or untouched native definitions did not persist")


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
    display = drawing.AddHorizontalDimension2(0.240, 0.140, 0.0)
    drawing.ClearSelection2(True)
    if display is None:
        raise RuntimeError("failed to create base rim-width dimension")
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    actual_mm = float(dimension.SystemValue) * 1000.0
    if abs(actual_mm - LIP_W) > 1e-5:
        raise RuntimeError(f"base rim width measured {actual_mm}, expected {LIP_W} mm")
    return display


def _horizontal_base_edge(view: Any, height_mm: float) -> Any:
    candidates = []
    for raw in visible_view_entities(view, 1, label="base height edges"):
        edge = _early_bound(raw, "IEdge")
        if not _early_bound(edge.GetCurve(), "ICurve").IsLine():
            continue
        x0, y0, z0, x1, y1, z1 = tuple(edge.GetCurveParams2())[:6]
        if (
            abs(y0 - height_mm / 1000.0) < 1e-7
            and abs(y1 - y0) < 1e-7
            and abs(z1 - z0) < 1e-7
            and abs(x1 - x0) > 1e-6
        ):
            candidates.append((abs(x1 - x0), edge))
    if not candidates:
        raise RuntimeError(f"base front lacks a horizontal edge at {height_mm} mm")
    return max(candidates, key=lambda item: item[0])[1]


def _add_base_height(
    adapter: Any,
    view: Any,
    upper_edge: Any,
    expected_mm: float,
    text_xy: tuple[float, float],
    label: str,
    *,
    lower_entity: Any | None = None,
) -> Any:
    drawing = adapter.currentModel
    if not _early_bound(drawing, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate {label} view")
    drawing.ClearSelection2(True)
    lower = _horizontal_base_edge(view, 0.0) if lower_entity is None else lower_entity
    for index, edge in enumerate((lower, upper_edge)):
        if not view.SelectEntity(edge, index > 0):
            raise RuntimeError(f"failed to select {label} edge {index}")
    display = drawing.AddVerticalDimension2(*text_xy, 0.0)
    drawing.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"failed to create {label}")
    display = _early_bound(display, "IDisplayDimension")
    actual_mm = (
        float(_early_bound(display.GetDimension2(0), "IDimension").SystemValue) * 1000.0
    )
    if abs(actual_mm - expected_mm) > 1e-5:
        raise RuntimeError(f"{label} measured {actual_mm}, expected {expected_mm} mm")
    return display


def _attached_note(
    adapter: Any,
    view: Any,
    edge: Any,
    text: str,
    position: tuple[float, float],
) -> None:
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(
        view_name(adapter, view)
    ):
        raise RuntimeError("failed to activate base feature-note view")
    note = add_note(adapter, text, *position)
    if note is None:
        raise RuntimeError(f"failed to create base feature note {text!r}")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if not annotation.SetAttachedEntities(dispatch_array([edge])):
        raise RuntimeError(f"failed to attach base feature note {text!r}")
    if annotation.SetLeader3(1, 0, True, False, False, False) != 0:
        raise RuntimeError(f"failed to give base feature note a leader: {text!r}")
    if not annotation.SetPosition2(*position, 0.0):
        raise RuntimeError(f"failed to position base feature note {text!r}")
    if int(annotation.GetAttachedEntityCount3()) != 1:
        raise RuntimeError(f"base feature note lost its source edge: {text!r}")


def _serial_edge(view: Any) -> Any:
    candidates = []
    for raw in visible_view_entities(view, 1, label="base stamped identifier"):
        edge = _early_bound(raw, "IEdge")
        values = tuple(float(value) for value in edge.GetCurveParams2())
        x0, y0, z0, x1, y1, z1 = values[:6]
        if max(abs(y0 - RIM_TOP / 1000.0), abs(y1 - RIM_TOP / 1000.0)) > 1e-7:
            continue
        distance = (
            ((x0 + x1) / 2.0 - SERIAL_XZ[0] / 1000.0) ** 2
            + ((z0 + z1) / 2.0 - SERIAL_XZ[1] / 1000.0) ** 2
        ) ** 0.5
        if distance < SERIAL_HEIGHT_MM / 1000.0:
            candidates.append((distance, edge))
    if not candidates:
        raise RuntimeError("base stamped identifier lacks a visible source edge")
    return min(candidates, key=lambda item: item[0])[1]


def _spread_hole_tags(view: Any, table: Any) -> None:
    table_locations = {}
    for row in range(1, int(table.RowCount)):
        tag = str(table.DisplayedText2(row, 0, False) or "").strip()
        if not tag or tag in table_locations:
            raise RuntimeError(f"duplicate or empty native hole-table tag at row {row}: {tag!r}")
        table_locations[tag] = tuple(
            float(table.DisplayedText2(row, column, False))
            for column in (1, 2)
        )
    remaining = dict(HOLE_TAG_POSITIONS)
    found = set()
    for raw in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.GetType()) != 6:
            continue
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        tag = str(note.GetText()).strip()
        if tag in table_locations:
            if tag in found:
                raise RuntimeError(f"duplicate native hole-table view tag: {tag}")
            found.add(tag)
        position = remaining.pop(tag, None)
        if position is None:
            continue
        if annotation.SetLeader3(1, 0, True, False, False, False) != 0:
            raise RuntimeError(f"failed to give native hole tag {tag} a leader")
        if not annotation.SetPosition2(*position, 0.0):
            raise RuntimeError(f"failed to reposition native hole tag {tag}")
        if str(note.GetText()).strip() != tag:
            raise RuntimeError(f"moving native hole tag changed its text: {tag}")
        if tag in ("D1", "E1", "F1", "E3", "F3", "G1"):
            points = tuple(float(value) for value in annotation.GetLeaderPointsAtIndex(0) or ())
            if len(points) < 6 or len(points) % 3:
                raise RuntimeError(f"native hole tag {tag} has no complete leader: {points!r}")
            expected = tuple(
                origin + coordinate * VIEW_SCALE / 1000.0
                for origin, coordinate in zip(_TABLE_ORIGIN_XY, table_locations[tag])
            )
            endpoint = points[-3:-1]
            if sum((actual - wanted) ** 2 for actual, wanted in zip(endpoint, expected)) > 0.001 ** 2:
                raise RuntimeError(
                    f"native {tag} leader does not reach its table hole: "
                    f"table_mm={table_locations[tag]!r}, end={endpoint!r}, centre={expected!r}"
                )
            _telemetry.info(
                f"native hole binding: tag={tag}, table_mm={table_locations[tag]!r}, "
                f"leader_end={endpoint!r}, centre={expected!r}"
            )
    if remaining:
        raise RuntimeError(f"native hole-table tags not found: {sorted(remaining)}")
    if found != set(table_locations):
        raise RuntimeError(f"native table/view tag bijection failed: missing={set(table_locations) - found}")


def _section_geometry_controls(adapter: Any, view: Any) -> None:
    levels: dict[float, list[tuple[float, Any]]] = {STACK_HEIGHT: [], RIM_TOP: []}
    chamfers: dict[str, list[tuple[float, Any]]] = {"UPPER RIM": [], "UNDERSIDE": []}
    for raw in visible_view_entities(view, 1, label="base section rim and chamfers"):
        edge = _early_bound(raw, "IEdge")
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if curve.IsLine():
            x0, y0, z0, x1, y1, z1 = tuple(edge.GetCurveParams2())[:6]
            # Section A-A is a YZ cut: these native diagonal edges expose
            # both equal legs of the actual 45-degree chamfer.
            if (
                abs(x1 - x0) < 1e-7
                and abs(abs(y1 - y0) - RIM_CHAMFER / 1000.0) < 1e-7
                and abs(abs(z1 - z0) - RIM_CHAMFER / 1000.0) < 1e-7
            ):
                if abs(max(y0, y1) - RIM_TOP / 1000.0) < 1e-7:
                    chamfers["UPPER RIM"].append(((z0 + z1) / 2.0, edge))
                elif abs(min(y0, y1)) < 1e-7:
                    chamfers["UNDERSIDE"].append(((z0 + z1) / 2.0, edge))
            if abs(y1 - y0) > 1e-7:
                continue
            span = ((x1 - x0) ** 2 + (z1 - z0) ** 2) ** 0.5
            for height, candidates in levels.items():
                if span > 1e-6 and abs(y0 - height / 1000.0) < 1e-7:
                    candidates.append((span, edge))
    if any(not candidates for candidates in levels.values()):
        raise RuntimeError("base section lacks exact deck/rim edges")
    if any(not candidates for candidates in chamfers.values()):
        raise RuntimeError("base section lacks the actual equal-leg upper/underside chamfer edges")
    drawing = adapter.currentModel
    if not _early_bound(drawing, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate base section controls")
    drawing.ClearSelection2(True)
    for index, candidates in enumerate(levels.values()):
        if not view.SelectEntity(
            max(candidates, key=lambda item: item[0])[1], index > 0
        ):
            raise RuntimeError("failed to select exact base rim-step edges")
    step = drawing.AddHorizontalDimension2(0.393, 0.215, 0.0)
    drawing.ClearSelection2(True)
    if step is None:
        raise RuntimeError("failed to create base rim-step dimension")
    step = _early_bound(step, "IDisplayDimension")
    actual = (
        float(_early_bound(step.GetDimension2(0), "IDimension").SystemValue) * 1000.0
    )
    if abs(actual - LIP_H) > 1e-5:
        raise RuntimeError(f"base rim step measured {actual}, expected {LIP_H} mm")
    step.SetText(4, "RIM ABOVE\nDECK")
    step.SetPrecision3(1, -1, -1, -1)
    if int(step.GetPrimaryPrecision2()) != 1:
        raise RuntimeError("base rim-step precision did not persist")
    # No root-radius callout: a 0.5 mm internal root at the pad-to-flange
    # junction is not measurable with hobby-shop kit, so the model keeps its
    # fillet and the deck cutter's own corner radius defines it (2026-09
    # review over-specification item).
    for label, candidates in chamfers.items():
        edge = (
            min(candidates, key=lambda item: item[0])[1]
            if label == "UPPER RIM"
            else max(candidates, key=lambda item: item[0])[1]
        )
        vertices = (edge.GetStartVertex(), edge.GetEndVertex())
        drawing.ClearSelection2(True)
        for index, vertex in enumerate(vertices):
            if vertex is None or not view.SelectEntity(vertex, index > 0):
                raise RuntimeError(f"failed to select actual {label} chamfer endpoints")
        text_xy = (0.400, 0.184) if label == "UPPER RIM" else (0.395, 0.103)
        display = drawing.AddHorizontalDimension2(*text_xy, 0.0)
        drawing.ClearSelection2(True)
        if display is None:
            raise RuntimeError(f"failed to dimension the section {label} chamfer")
        display = _early_bound(display, "IDisplayDimension")
        actual_mm = float(_early_bound(display.GetDimension2(0), "IDimension").SystemValue) * 1000.0
        if abs(actual_mm - RIM_CHAMFER) > 1e-5:
            raise RuntimeError(f"section {label} chamfer measured {actual_mm}, expected {RIM_CHAMFER} mm")
        caption = f"X 45 DEG\n{label}"
        display.SetText(4, caption)
        display.SetPrecision3(1, -1, -1, -1)
        if int(display.GetPrimaryPrecision2()) != 1 or str(display.GetText(4)) != caption:
            raise RuntimeError(f"section {label} chamfer precision or caption did not persist")


ALL_HOLES = (
    *((x, z, HOLD_DOWN_TAP_DRILL_DIA) for x, z in HOLE_XZ),
    (*PIVOT_SCREW_XZ, PIVOT_SCREW_HOLE_DIA),
    (*STOP_SCREW_XZ, STOP_SCREW_HOLE_DIA),
    *((x, z, BLOCK_SCREW_HOLE_DIA) for x, z in BLOCK_SCREW_XZ),
    *((x, z, FOOT_SCREW_HOLE_DIA) for x, z in FOOT_SCREW_XZ),
    # Keep later seat groups after the earlier mounting-seat groups.
    *((x, z, NAMEPLATE_SCREW_HOLE_DIA) for x, z in NAMEPLATE_SCREW_XZ),
    (*LOCK_KNOB_XZ, LOCK_SCREW_HOLE_DIA),
    *((x, z, COLUMN_SOCKET_DIAMETER) for x, z in COLUMN_SOCKET_XZ),
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
    for index in range(len(COLUMN_SOCKET_XZ)):
        name = "SocketDia" if index == 0 else f"Socket{index}Dia"
        raw = adapter.currentModel.Parameter(f"{name}@ColumnSocketProfile")
        if raw is None:
            raise RuntimeError(f"source is missing the native {name} socket dimension")
        dimension = _early_bound(raw, "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        if int(tolerance.Type) != 0:  # swTolNONE; the assigned tube governs fit
            raise RuntimeError(f"{name} retains a fixed bore tolerance; rebuild the match-fit source")
    source_properties = read_required_properties(
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
    if source_properties["Manufacturing Notes"].replace("\r\n", "\n").strip() != DRAWING_NOTES:
        raise RuntimeError("source lacks the approved finished-land acceptance; rebuild harmonic-base")
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="harmonic-base package")
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
    ddoc = _early_bound(drawing_model, "IDrawingDoc")

    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate harmonic-base geometry sheet")
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=SHEET_SCALE)
    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (top, side, iso):
        set_hidden_lines_removed(adapter, view)

    top_dimensions = curate_view_dimensions(
        adapter, top, keep=GEOMETRY_TOP_KEEP, view_label="geometry top"
    )
    side_dimensions = curate_view_dimensions(
        adapter, side, keep=SIDE_KEEP, view_label="geometry front"
    )
    set_dimension_callouts(
        adapter,
        [*top_dimensions, *side_dimensions],
        GEOMETRY_CALLOUTS,
    )
    for annotation in top_dimensions:
        name = dimension_name(adapter, annotation)
        if name not in ("PadCornerRadius", "FlangeCornerRadius", "RimInnerCornerRadius"):
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArcExtensionLineOrOppositeSide = False
        if display.ArcExtensionLineOrOppositeSide:
            raise RuntimeError(f"{name} leader did not stay on its native corner arc")
    set_dimension_precision(
        adapter,
        [*top_dimensions, *side_dimensions],
        {
            name: 1
            for name in (
                "BottomLen",
                "BottomWid",
                "TopLen",
                "TopWid",
                "PadCornerRadius",
                "FlangeCornerRadius",
                "RimInnerCornerRadius",
                "BottomThickness",
            )
        },
    )

    rim_width = _add_rim_width(adapter, top)
    rim_width.SetText(4, "FROM PAD OUTER EDGE\nTO RIM INNER FACE\n4 SIDES")
    rim_width.SetPrecision3(1, -1, -1, -1)
    if int(rim_width.GetPrimaryPrecision2()) != 1:
        raise RuntimeError("base rim-width precision did not persist")
    overall_height = _add_base_height(
        adapter,
        side,
        _horizontal_base_edge(side, RIM_TOP),
        RIM_TOP,
        (0.052, 0.099),
        "overall rim height",
    )
    set_reference_dimension(
        adapter,
        overall_height.GetAnnotation(),
        label="derived overall rim height",
    )
    overall_height.SetPrecision3(1, -1, -1, -1)
    if int(overall_height.GetPrimaryPrecision2()) != 1:
        raise RuntimeError("base overall reference precision did not persist")
    # All three height dimensions stack on the LEFT of the front view, shortest
    # nearest the outline: 12.7 at x 0.073, this 40.6 at 0.0625, the overall
    # reference at 0.052. Its text clears the 53.3 text above the view.
    flange_to_rim = _add_base_height(
        adapter, side, _horizontal_base_edge(side, RIM_TOP),
        RIM_TOP - BOTTOM_THICKNESS, (0.0625, 0.112), "visible flange-to-rim height",
        lower_entity=_horizontal_base_edge(side, BOTTOM_THICKNESS),
    )
    flange_to_rim.SetPrecision3(1, -1, -1, -1)
    if int(flange_to_rim.GetPrimaryPrecision2()) != 1:
        raise RuntimeError("base flange-to-rim height precision did not persist")

    add_note(adapter, "TOP VIEW SCALE 1:4", 0.100, 0.255)
    add_note(adapter, "FRONT VIEW SCALE 1:4", 0.105, 0.075)
    add_note(adapter, "ISOMETRIC VIEW SCALE 1:6", 0.3183, 0.145)
    _attached_note(
        adapter,
        top,
        _serial_edge(top),
        f'STAMPED ID "{SERIAL_TEXT}"\n{SERIAL_HEIGHT_MM:.1f} HIGH\nAPPROX AS SHOWN',
        (0.125, 0.130),
    )
    deck_control = surface_finish_by_key(SURFACE_FINISHES, "deck")
    deck_face = _resolve_faces(
        _early_bound(top.ReferencedDocument, "IModelDoc2"),
        {"deck": deck_control.face},
    )["deck"]
    deck_box = tuple(float(value) for value in deck_face.GetBox())
    if len(deck_box) != 6:
        raise RuntimeError("qualified deck face has no native bounding box")
    deck_point = tuple(float(value) for value in (deck_face.GetClosestPointOn(
        deck_box[0] + (deck_box[3] - deck_box[0]) / 4.0,
        (deck_box[1] + deck_box[4]) / 2.0,
        deck_box[2] + 3.0 * (deck_box[5] - deck_box[2]) / 4.0,
    ) or ()))
    if len(deck_point) != 5 or abs(deck_point[1] - STACK_HEIGHT / 1000.0) > 1e-7:
        raise RuntimeError(f"native deck leader point is not on the deck plane: {deck_point!r}")
    deck_finish = add_surface_finish(
        adapter, top,
        symbol_xy=(0.040, 0.138),
        control=deck_control,
        label="deck seat finish",
        char_height=0.0025,
        entity_type="FACE",
        entity=deck_face,
        leader_attach_xy=model_point_in_view(
            adapter, top, deck_point[:3], label="qualified deck face finish anchor",
        ),
    )
    underside_finish = add_surface_finish(
        adapter, side,
        symbol_xy=(0.040, 0.052),
        control=surface_finish_by_key(SURFACE_FINISHES, "underside"),
        label="underside seat finish",
        char_height=0.0025,
        entity=_horizontal_base_edge(side, 0.0),
        leader_attach_xy=model_point_in_view(
            adapter, side, (-BOTTOM_LENGTH / 4000.0, 0.0, 0.0),
            label="underside finish edge",
        ),
    )
    for label, symbol in (("deck", deck_finish), ("underside", underside_finish)):
        annotation = _early_bound(symbol.GetAnnotation(), "IAnnotation")
        annotation.BentLeaderLength = 0.035
        if abs(float(annotation.BentLeaderLength) - 0.035) > 1e-7:
            raise RuntimeError(f"{label} finish leader did not clear its roughness text")
    for view in (top, side):
        set_hidden_lines_visible(adapter, view)

    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate harmonic-base holes sheet")
    hole_top = place_view(
        adapter, str(SOURCE), "*Top", *HOLE_TOP_CENTER, scale=SHEET_SCALE
    )
    hole_side = place_view(
        adapter, str(SOURCE), "*Front", *HOLE_SIDE_CENTER, scale=SHEET_SCALE
    )
    section_line_x = _plan_xy(COLUMN_X, 0.0, center=HOLE_TOP_CENTER)[0]
    section = create_section_view(
        adapter,
        hole_top,
        line_start=(section_line_x, HOLE_TOP_CENTER[1] - 0.040),
        line_end=(section_line_x, HOLE_TOP_CENTER[1] + 0.040),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=SHEET_SCALE,
        label="base column-socket section",
    )
    for view in (hole_top, hole_side, section):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(
        adapter, hole_top, keep=HOLE_TOP_KEEP, view_label="holes top"
    )
    curate_view_dimensions(
        adapter, section, keep=SECTION_KEEP, view_label="section A-A"
    )
    _section_geometry_controls(adapter, section)
    _add_cross_spotface_dimension(adapter, hole_side)
    # Sheet-2 left notes column, below the hole table: the socket-matching
    # note stacks above the linked land note so neither crowds the TOP VIEW
    # caption. The hole table's SIZE cells are generated by SolidWorks and are
    # not text-editable, so the note names the table as the reference source.
    add_note(
        adapter,
        "A1-A4 BORE DIAMETERS (HOLE TABLE): REFERENCE ONLY\n"
        "MATCH SOCKETS TO ASSIGNED ACTUAL MHA-083 TUBES\n"
        "CLOSE HAND-SLIP; NO PERCEPTIBLE ROCK\n"
        "RETAIN CORNER/ORIENTATION MATCH MARKS",
        0.020,
        0.073,
    )
    if not auto_center_marks(adapter, hole_top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the base hole pattern")

    table_origin = create_view_theoretical_datum(
        adapter,
        hole_top,
        point_xy=(-BOTTOM_LENGTH / 2000.0, -BOTTOM_REAR_Z / 1000.0),
        label="harmonic-base finished-corner table origin",
    )
    hole_entities, table_x_axis, table_y_axis = _visible_hole_table_entities(
        adapter, hole_top
    )
    hole_table = insert_hole_table(
        adapter,
        hole_top,
        datum_xy=_TABLE_ORIGIN_XY,
        datum_point=table_origin,
        hole_points=tuple(_hole_rim(x, z, diameter) for x, z, diameter in ALL_HOLES),
        datum_axes=(table_x_axis, table_y_axis),
        hole_entities=hole_entities,
        expected_locations_mm=tuple(
            (x + BOTTOM_LENGTH / 2.0, BOTTOM_WIDTH / 2.0 - z)
            for x, z, _diameter in ALL_HOLES
        ),
        anchor_xy=HOLE_TABLE_ANCHOR,
        basic_locations=False,
        label="harmonic-base mounting",
    )
    hole_feature = _early_bound(
        _early_bound(hole_table, "IHoleTableAnnotation").HoleTable, "IHoleTable"
    )
    hole_feature.CombineSameSize = True
    if not hole_feature.CombineSameSize or hole_feature.CombineTags:
        raise RuntimeError("base hole table did not retain individual coordinate tags")
    if int(hole_table.RowCount) != len(ALL_HOLES) + 1:
        raise RuntimeError("combining base hole sizes changed individual table rows")
    for row in range(int(hole_table.RowCount)):
        hole_table.SetRowHeight(row, 0.007, 0)
    table_height = sum(
        float(hole_table.GetRowHeight(row)) for row in range(int(hole_table.RowCount))
    )
    if table_height > HOLE_TABLE_ANCHOR[1] - 0.025:
        raise RuntimeError(
            f"base hole table exceeds the inner border: {table_height} m"
        )
    drawing_model.EditRebuild3()
    _spread_hole_tags(hole_top, hole_table)
    tap_callout = add_native_hole_callout(
        adapter,
        hole_side,
        edge=_cross_tap_edge(hole_side),
        callout_xy=(0.285, 0.130),
        label="base column-retention taps",
        process=(
            "MHA-132 TUBE CROSS-SCREWS\n"
            "THRU BOTH WALLS, SINGLE CONTINUOUS THREAD\n"
            "DEPTHS FROM SPOTFACE FLOOR\n"
            "ON A1-A4 X CENTRES\n2 EACH FRONT/REAR FACE"
        ),
    )
    _set_cross_tap_total_quantity(tap_callout)
    _check_cross_tap_callout(tap_callout)
    base_edge = _horizontal_base_edge(hole_side, 0.0)
    endpoints = (base_edge.GetStartVertex(), base_edge.GetEndVertex())
    if any(vertex is None for vertex in endpoints):
        raise RuntimeError("cross-axis underside edge lacks native endpoint vertices")
    left_base_vertex = min(
        (_early_bound(vertex, "IVertex") for vertex in endpoints),
        key=lambda vertex: float(vertex.GetPoint()[0]),
    )
    base_point = tuple(float(value) for value in left_base_vertex.GetPoint())
    if base_point[0] >= 0.0 or abs(base_point[1]) > 1e-7:
        raise RuntimeError("cross-axis datum is not the left base-underside vertex")
    tap_height = _add_base_height(
        adapter,
        hole_side,
        _cross_tap_edge(hole_side, x_mm=-COLUMN_X),
        BASE_SCREW_Y,
        (0.211, 0.096),
        "cross-tap axis height",
        lower_entity=left_base_vertex,
    )
    tap_height.SetPrecision3(2, -1, -1, -1)
    if int(tap_height.GetPrimaryPrecision2()) != 2:
        raise RuntimeError("native cross-axis height precision did not persist")
    # The hole table measures every coordinate from the virtual corner of the
    # flange's west and rear faces, so the plan profile carries the seat grade
    # once, read off the same west edge the table's Y axis is seeded from. The
    # symbol's own target names the surface ("FLANGE EDGES, 4 SIDES"), which
    # the three nested plan outlines made necessary; the part owns one control
    # per perimeter face and this single callout states all four.
    flange_finish = add_surface_finish(
        adapter, hole_top,
        symbol_xy=(0.170, 0.205),
        control=surface_finish_by_key(SURFACE_FINISHES, "flange_west"),
        label="flange perimeter seat finish",
        char_height=0.0025,
        edge_entity=table_y_axis,
        leader_attach_xy=_plan_xy(
            -BOTTOM_LENGTH / 2.0, 0.0, center=HOLE_TOP_CENTER
        ),
    )
    flange_annotation = _early_bound(flange_finish.GetAnnotation(), "IAnnotation")
    flange_annotation.BentLeaderLength = 0.035
    if abs(float(flange_annotation.BentLeaderLength) - 0.035) > 1e-7:
        raise RuntimeError("flange perimeter finish leader did not clear its roughness text")
    add_note(adapter, "TOP VIEW SCALE 1:4", 0.235, 0.237)
    add_note(adapter, "FRONT CROSS-TAP VIEW SCALE 1:4", 0.245, 0.075)
    # Three nested outlines (flange, pad side, rim inner) sit within 1.6 mm of
    # each other at the table origin, so the corner is named instead of left to
    # be inferred from A1-A4 symmetry. Section A-A is projected from a vertical
    # cutting line, which lays machine +Y across the sheet: it reads as the
    # upright section turned 90 degrees clockwise, and says so.
    add_note(adapter, "ORIGIN: FLANGE OUTER\nSHARP CORNER (X0 Y0)", 0.207, 0.1525)
    add_note(adapter, "SECTION A-A\nROTATED\n90 DEG CW", 0.342, 0.2025)
    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.020, 0.046, char_height=0.0035,
    )
    section_threads = import_cosmetic_threads(adapter, section)
    if section_threads[1] == 0:
        raise RuntimeError("section A-A has no native cosmetic-thread instances")
    _telemetry.info(f"section A-A native cosmetic threads: seeds/instances={section_threads!r}")
    for view in (hole_top, hole_side, section):
        set_hidden_lines_visible(adapter, view)

    for sheet_index, sheet_name in enumerate(SHEET_NAMES, start=1):
        if not ddoc.ActivateSheet(sheet_name):
            raise RuntimeError(f"failed to label drawing sheet {sheet_name}")
        if (
            add_note(
                adapter, f"SHEET {sheet_index} OF {len(SHEET_NAMES)}", 0.350, 0.263
            )
            is None
        ):
            raise RuntimeError(f"failed to stamp sheet count on {sheet_name}")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Harmonic Base Manufacturing Drawing",
        scale=SHEET_SCALE,
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=14,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
