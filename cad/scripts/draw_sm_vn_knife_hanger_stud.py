"""Create MHA-SM-VN-52's modified-stock cut and inspection drawing."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name, place_view, set_view_position, view_name,
)

import _telemetry
from _check import check
from _com import _early_bound
from _drawing_attachment import _is_same_attachment
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import offset_dimension_text, set_dimension_callouts
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_leader_notes import add_property_linked_callout
from _drawing_notes import add_property_linked_note, property_link
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _session import run_build
from _stock_trim_drawing import verify_machining_controls
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from sm_vn_knife_hanger_stud_spec import (
    CHAMFER_ANGLE,
    CATALOG_LENGTH,
    CHAMFER_ANGLE_TOLERANCE,
    CHAMFER_WIDTH,
    CHAMFER_WIDTH_TOLERANCE,
    DIMENSION_CALLOUTS,
    DIMENSION_PRECISION,
    DIMENSION_TOLERANCE_TYPES,
    DRAWING_DIMENSIONS,
    HEAD_AF,
    HEAD_H,
    HEAD_TOP_Y,
    LENGTH,
    SHANK_DIA,
    SUPPLIER_DRAWING_DIMENSIONS,
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_STOCK_CONFIGURATION,
    SUPPLIER_STOCK_TITLE,
    THREAD_LENGTH_MIN,
)

SPEC = DRAWINGS_BY_NAME["sm_vn_knife_hanger_stud"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SHEET_SCALE = (2.0, 1.0)
ISO_SCALE = SHEET_SCALE  # One-scale sheet: no per-view scale label.
SHEET_NAMES = ("FINISHED", "92314A253-STOCK")
_SHEET_PER_MODEL_MM = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000
# Sheet metres. The Front view centres the part's Y box (tip Y=0 to head
# top), so the finished tip lands half the scaled part height below it.
FRONT_CENTER = (0.110, 0.170)
TIP_SHEET_Y = FRONT_CENTER[1] - HEAD_TOP_Y / 2 * _SHEET_PER_MODEL_MM
# The chamfer meets the tip face one leg inside the thread major radius.
_CHAMFER_VERTEX = (
    FRONT_CENTER[0] + (SHANK_DIA / 2 - CHAMFER_WIDTH) * _SHEET_PER_MODEL_MM,
    TIP_SHEET_Y,
)
_ANGLE_TEXT_RADIUS = 0.016
# The B-size inner border is 12.7 mm in from the sheet edge; the title block
# spans x >= 0.216 below y = 0.065.
FRONT_KEEP = {
    # Text and dimension line left of the head, the three callout lines (under
    # 72 mm wide) centred 6 mm inside the left border and 10 mm clear of the hex.
    "CutLength": (0.055, FRONT_CENTER[1]),
    # The text stands wholly above the tail's top extension line and right of
    # the shank, so neither extension line crosses "10.62 min." or its lines.
    "ThreadLengthMin": (0.170, TIP_SHEET_Y + 0.039),
    # Dimension line 6 mm under the chamfer leg; its text leaves on a leader.
    "ChamferWidth": (
        FRONT_CENTER[0] + (SHANK_DIA - CHAMFER_WIDTH) / 2 * _SHEET_PER_MODEL_MM,
        TIP_SHEET_Y - 0.006,
    ),
    # The native 45 degrees in the open wedge right of the tip: its arc and
    # extension lines stand 16 mm out on the angle's bisector, below the
    # tail's top extension line and left of its dimension line.
    "ChamferAngle": (
        _CHAMFER_VERTEX[0]
        + _ANGLE_TEXT_RADIUS * math.cos(math.radians(CHAMFER_ANGLE / 2)),
        _CHAMFER_VERTEX[1]
        + _ANGLE_TEXT_RADIUS * math.sin(math.radians(CHAMFER_ANGLE / 2)),
    ),
}
# The chamfer callout stands below-right of the tip, under the tail's lower
# extension line and right of the leg's own extension lines.
CHAMFER_TEXT_XY = (0.157, TIP_SHEET_Y - 0.014)
# The purchased-screw note flags the unmodified head: its leader lands on
# the head-top edge, the note stands up and right in the open field.
HEAD_PICK_MM = (HEAD_AF / 4, HEAD_TOP_Y, 0.0)
PURCHASED_NOTE_XY = (0.130, 0.240)
# Every view and the sheet are 2:1, so the title-block SCALE is the view
# scale and the isometric carries no scale label.
ISO_CENTER = (0.340, 0.135)
STOCK_CENTER = (0.180, 0.160)
STOCK_ISO_CENTER = (0.325, 0.155)
# MHA-SM-00 cuts each bolt to its measured stack, so the native CutLength
# still drives the modelled trim but prints as the bracketed reference
# nominal; every other control keeps its native band.
REFERENCE_CONTROL = "CutLength"
REFERENCE_NOMINAL = LENGTH / 1000
EXPECTED_CONTROLS = {
    "ChamferWidth": (
        CHAMFER_WIDTH / 1000,
        -CHAMFER_WIDTH_TOLERANCE / 1000,
        CHAMFER_WIDTH_TOLERANCE / 1000,
    ),
    "ChamferAngle": (
        math.radians(CHAMFER_ANGLE),
        -math.radians(CHAMFER_ANGLE_TOLERANCE),
        math.radians(CHAMFER_ANGLE_TOLERANCE),
    ),
    "ThreadLengthMin": (THREAD_LENGTH_MIN / 1000, 0.0, 0.0),
}


def verify_cut_length_reference(adapter: Any, annotations: list[Any]) -> list[Any]:
    """Prove the one reference CutLength; return the banded controls.

    The reference still drives the trim at its nominal, carries no band and
    prints bracketed at its native precision.
    """
    controls, references = [], []
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        (references if name == REFERENCE_CONTROL else controls).append(annotation)
    if len(references) != 1:
        raise RuntimeError(
            f"{REFERENCE_CONTROL}: expected one sheet dimension, found {len(references)}"
        )
    display = _early_bound(references[0].GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(dimension.DrivenState) != 2:
        raise RuntimeError(f"{REFERENCE_CONTROL}: no longer drives the modelled trim")
    if not math.isclose(float(dimension.SystemValue), REFERENCE_NOMINAL, abs_tol=1e-9):
        raise RuntimeError(f"{REFERENCE_CONTROL}: native dimension nominal changed")
    brackets = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
    if int(tolerance.Type) != DIMENSION_TOLERANCE_TYPES[
        REFERENCE_CONTROL
    ] or brackets != ("(", ")"):
        raise RuntimeError(f"{REFERENCE_CONTROL}: reference display did not persist")
    if int(display.GetPrimaryPrecision2()) != DIMENSION_PRECISION[REFERENCE_CONTROL]:
        raise RuntimeError(f"{REFERENCE_CONTROL}: native display precision changed")
    return controls


def _format_supplier_reference(adapter: Any, display: Any, name: str) -> Any:
    display = _early_bound(display, "IDisplayDimension")
    supplier_reference_dimension(
        adapter, display, label=name, **SUPPLIER_REFERENCE_DIMENSIONS[name]
    )
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    if int(_early_bound(dimension.Tolerance, "IDimensionTolerance").Type) != 0:
        raise RuntimeError(f"{name}: an unsupported supplier band was added")
    return _early_bound(display.GetAnnotation(), "IAnnotation")


def _head_height_points_mm() -> tuple[tuple[float, float, float], ...]:
    return (
        (HEAD_AF / 4, LENGTH, math.sqrt(3) * HEAD_AF / 4),
        (0.0, HEAD_TOP_Y, HEAD_AF / 2),
    )


@_telemetry.traced("drawing.stud_head_height_entities")
def _head_height_entities(adapter: Any, front: Any) -> tuple[Any, Any]:
    """Name the physical underside hex segment and frontmost outer top trim arc."""
    front = _early_bound(front, "IView")
    if int(front.GetDisplayMode2()) != 2:  # swHIDDEN (hidden lines removed)
        raise RuntimeError("SupplierHeadHeight: front view is not hidden-lines-removed")
    scan = scan_view_edges(front, label="SupplierHeadHeight physical stations")
    bearing_point, top_point = _head_height_points_mm()
    tolerance_mm = 1e-5
    bearing_matches = []
    line_details = []
    for item in scan.lines:
        detail = {"line_mm": item.line, "geometry_error_mm": math.inf}
        line_details.append(detail)
        if not all(math.isfinite(value) for point in item.line for value in point):
            continue
        start, end = item.line
        vector = tuple(b - a for a, b in zip(start, end))
        length_sq = sum(value * value for value in vector)
        t = (
            sum((p - a) * v for p, a, v in zip(bearing_point, start, vector)) / length_sq
            if length_sq > 0.0 else 0.0
        )
        closest = tuple(a + min(1.0, max(0.0, t)) * v for a, v in zip(start, vector))
        point_error_mm = math.dist(closest, bearing_point)
        station_error_mm = max(abs(point[1] - LENGTH) for point in item.line)
        # The front-right outer hex side runs between (0, AF/sqrt(3))
        # and (AF/2, AF/(2sqrt(3))) in XZ, at the actual underside Y.
        hex_side_error_mm = max(
            abs(z - (HEAD_AF - x) / math.sqrt(3)) for x, _y, z in item.line
        )
        span_error_mm = max(
            max(0.0, -point[0], point[0] - HEAD_AF / 2) for point in item.line
        )
        geometry_error_mm = max(
            point_error_mm, station_error_mm, hex_side_error_mm, span_error_mm
        )
        detail.update(
            geometry_error_mm=geometry_error_mm, point_error_mm=point_error_mm,
            station_error_mm=station_error_mm, hex_side_error_mm=hex_side_error_mm,
            span_error_mm=span_error_mm, length_mm=math.sqrt(length_sq),
        )
        if (
            length_sq <= tolerance_mm ** 2
            or not 0.0 <= t <= 1.0
            or geometry_error_mm > tolerance_mm
        ):
            continue
        bearing_matches.append(item)
    line_details.sort(key=lambda row: row["geometry_error_mm"])
    top_matches = []
    circle_details = []
    top_point_m = tuple(value / 1000 for value in top_point)
    for item in scan.circles:
        detail = {
            "circle_mm": item.circle, "geometry_error_mm": math.inf,
            "shape_matches": False, "nearest_m": None, "point_error_m": None,
        }
        circle_details.append(detail)
        if not all(math.isfinite(value) for value in item.circle):
            continue
        cx, cy, cz, nx, ny, nz, radius = item.circle
        center_error_mm = max(abs(cx), abs(cy - HEAD_TOP_Y), abs(cz))
        radius_error_mm = abs(radius - HEAD_AF / 2)
        axis_error = max(abs(abs(ny) - 1.0), abs(nx), abs(nz))
        geometry_error_mm = center_error_mm + radius_error_mm + axis_error * HEAD_AF / 2
        shape_matches = (
            center_error_mm <= tolerance_mm
            and radius_error_mm <= tolerance_mm
            and axis_error <= 1e-6
        )
        detail.update(
            geometry_error_mm=geometry_error_mm, center_error_mm=center_error_mm,
            radius_error_mm=radius_error_mm, axis_error=axis_error,
            shape_matches=shape_matches,
        )
        if not shape_matches:
            continue
        raw = _early_bound(item.edge, "IEdge").GetClosestPointOn(
            top_point_m[0], top_point_m[1], top_point_m[2]
        )
        if raw is None or len(raw) < 3:
            continue
        nearest = tuple(float(value) for value in raw[:3])
        detail["nearest_m"] = nearest
        if not all(math.isfinite(value) for value in nearest):
            continue
        error_m = math.dist(nearest, top_point_m)
        detail.update(
            point_error_m=error_m, geometry_error_mm=geometry_error_mm + error_m * 1000
        )
        if error_m > 1e-8:
            continue
        top_matches.append(item)
    circle_details.sort(key=lambda row: row["geometry_error_mm"])
    _telemetry.event(
        "drawing.physical_head_height_geometry", label="SupplierHeadHeight",
        bearing_point_mm=bearing_point, top_point_mm=top_point,
        line_count=len(scan.lines), lines_mm=[row["line_mm"] for row in line_details[:12]],
        lines=line_details[:12],
        bearing_lines_mm=[item.line for item in bearing_matches[:12]],
        bearing_matches=len(bearing_matches), circle_count=len(scan.circles),
        circles=circle_details[:12], top_matches=len(top_matches),
    )
    if len(bearing_matches) != 1 or len(top_matches) != 1:
        raise RuntimeError(
            "SupplierHeadHeight: expected one actual underside hex edge and one "
            f"frontmost outer trim arc; bearing={len(bearing_matches)}, "
            f"top={len(top_matches)}; lines={line_details[:12]}; "
            f"circles={circle_details[:12]}"
        )
    bearing = bearing_matches[0]
    app = _early_bound(adapter.swApp, "ISldWorks")
    top = top_matches[0]
    if int(app.IsSame(bearing.edge, top.edge)) != 0:
        raise RuntimeError("SupplierHeadHeight: physical stations are not distinct edges")
    _telemetry.event(
        "drawing.physical_head_height_stations", label="SupplierHeadHeight",
        bearing_line_mm=bearing.line, top_circle_mm=top.circle,
        top_closest_point_m=top_point_m,
    )
    return bearing.edge, top.edge


@_telemetry.traced("drawing.stud_head_height_assert")
def _assert_physical_head_height(
    adapter: Any, front: Any, display: Any, entities: tuple[Any, Any] | None = None
) -> float:
    """Prove the native value/attachments; settled/saved callers rescan stations."""
    if entities is None:
        entities = _head_height_entities(adapter, front)
    display = _early_bound(display, "IDisplayDimension")
    raw_annotation = display.GetAnnotation()
    if raw_annotation is None:
        raise RuntimeError("SupplierHeadHeight: native dimension has no annotation")
    annotation = _early_bound(raw_annotation, "IAnnotation")
    kinds = tuple(int(kind) for kind in (annotation.GetAttachedEntityTypes() or ()))
    if (
        int(display.Type2) != 12  # swVertLinearDimension
        or int(annotation.GetAttachedEntityCount3()) != 2
        or kinds != (1, 1)  # swSelEDGES, never silhouettes or vertices
        or len(tuple(annotation.GetAttachedEntities3() or ())) != 2
        or int(annotation.OwnerType) != 0
        or annotation.Owner is None
        or int(_early_bound(adapter.swApp, "ISldWorks").IsSame(annotation.Owner, front)) != 1
    ):
        raise RuntimeError("SupplierHeadHeight: expected a vertical dimension on two actual edges")
    return assert_dimension_measures(
        adapter, display, expected_mm=HEAD_H, label="SupplierHeadHeight", entities=entities
    )


@_telemetry.traced("drawing.stud_head_height_add")
def _add_physical_head_height(adapter: Any, front: Any, text_xy: tuple[float, float]) -> Any:
    """Select/read back each actual station; never fall back to coordinate hits."""
    entities = _head_height_entities(adapter, front)
    points_m = []
    for entity, point in zip(entities, _head_height_points_mm(), strict=True):
        expected_m = tuple(value / 1000 for value in point)
        raw = _early_bound(entity, "IEdge").GetClosestPointOn(
            expected_m[0], expected_m[1], expected_m[2]
        )
        if raw is None or len(raw) < 3:
            raise RuntimeError("SupplierHeadHeight: actual physical pick point is unreadable")
        nearest_m = tuple(float(value) for value in raw[:3])
        if (
            not all(math.isfinite(value) for value in nearest_m)
            or math.dist(nearest_m, expected_m) > 1e-8
        ):
            raise RuntimeError("SupplierHeadHeight: actual pick moved off its physical station")
        points_m.append(nearest_m)
    picks = model_points_in_view(
        adapter, front, points_m, label="SupplierHeadHeight physical edge points"
    )
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    drawing = _early_bound(model, "IDrawingDoc")
    manager = _early_bound(model.SelectionManager, "ISelectionMgr")
    app = _early_bound(adapter.swApp, "ISldWorks")
    try:
        if not drawing.ActivateView(view_name(adapter, front)):
            raise RuntimeError("SupplierHeadHeight: cannot activate the exact front view")
        model.ClearSelection2(True)
        actual = []
        for index, (entity, point) in enumerate(zip(entities, picks, strict=True), start=1):
            data = _early_bound(manager.CreateSelectData(), "ISelectData")
            data.View = front
            if not _early_bound(entity, "IEntity").Select4(index > 1, data):
                raise RuntimeError(f"SupplierHeadHeight: physical edge selection {index} failed")
            if (
                int(manager.GetSelectedObjectCount2(-1)) != index
                or int(manager.GetSelectedObjectType3(index, -1)) != 1
            ):
                raise RuntimeError(f"SupplierHeadHeight: selection {index} count/type changed")
            selected = manager.GetSelectedObject6(index, -1)
            if selected is None or int(app.IsSame(selected, entity)) != 1:
                raise RuntimeError(f"SupplierHeadHeight: selection {index} is not the requested edge")
            actual.append(selected)
            # The drawing's selection manager uses drawing world coordinates.
            if manager.SetSelectionPoint2(index, -1, point[0], point[1], 0.0) is not True:
                raise RuntimeError(f"SupplierHeadHeight: selection point {index} was rejected")
        if int(app.IsSame(actual[0], actual[1])) != 0:
            raise RuntimeError("SupplierHeadHeight: selected physical stations are not distinct")
        display = model.AddVerticalDimension2(text_xy[0], text_xy[1], 0.0)
        if display is None:
            raise RuntimeError("SupplierHeadHeight: AddVerticalDimension2 returned no dimension")
    finally:
        model.ClearSelection2(True)
    _assert_physical_head_height(adapter, front, display, entities=entities)
    return display


def _add_supplier_references(adapter: Any, front: Any) -> dict[str, Any]:
    """Measure the surviving physical head and import the native major envelope."""
    flat = HEAD_AF / 2
    points_mm = (
        (-flat, LENGTH + HEAD_H / 3, HEAD_AF / (2 * math.sqrt(3))),
        (flat, LENGTH + HEAD_H / 3, HEAD_AF / (2 * math.sqrt(3))),
    )
    picks = model_points_in_view(
        adapter, front,
        [tuple(value / 1000 for value in point) for point in points_mm],
        label="SupplierHeadAF",
    )
    display = add_edge_dimension(
        adapter, front, p0=picks[0], p1=picks[1], text_xy=(0.110, 0.255),
        label="SupplierHeadAF", orientation="horizontal",
    )
    authored = {
        "SupplierHeadAF": _format_supplier_reference(adapter, display, "SupplierHeadAF")
    }
    authored["SupplierHeadHeight"] = _format_supplier_reference(
        adapter, _add_physical_head_height(adapter, front, (0.218, 0.216)),
        "SupplierHeadHeight",
    )
    references = curate_view_dimensions(
        adapter, front, keep={"SupplierThreadMajor": (0.170, 0.194)},
        view_label="nominal supplier thread-major envelope",
        dimensions_by_feature=SUPPLIER_DRAWING_DIMENSIONS,
    )
    for annotation in references:
        name = dimension_name(adapter, annotation)
        if name in authored:
            raise RuntimeError(f"{name}: duplicate supplier reference")
        authored[name] = _format_supplier_reference(
            adapter, annotation.GetSpecificAnnotation(), name
        )
    return authored


def _add_stock_reference(adapter: Any) -> tuple[Any, Any, Any]:
    """Show the original 2-inch solid on its own stock-only sheet."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not drawing.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("cannot activate knife-hanger stock sheet")
    stock = place_view(adapter, str(SOURCE), "*Front", *STOCK_CENTER, scale=SHEET_SCALE)
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *STOCK_ISO_CENTER, scale=SHEET_SCALE
    )
    for view in (stock, iso):
        _early_bound(view, "IView").ReferencedConfiguration = SUPPLIER_STOCK_CONFIGURATION
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("source-stock views did not rebuild")
    for view, centre in ((stock, STOCK_CENTER), (iso, STOCK_ISO_CENTER)):
        if str(_early_bound(view, "IView").ReferencedConfiguration) != SUPPLIER_STOCK_CONFIGURATION:
            raise RuntimeError("source-stock view references the finished bolt")
        if not set_view_position(adapter, view, *centre):
            raise RuntimeError("cannot position source-stock view")
        set_hidden_lines_removed(adapter, view)
    picks = model_points_in_view(
        adapter, stock,
        (
            (0.95 * HEAD_AF / 2000, LENGTH / 1000, 0.0),
            (0.0, (LENGTH - CATALOG_LENGTH) / 1000, 0.0),
        ),
        label="as-supplied under-head stock length",
    )
    display = add_edge_dimension(
        adapter, stock, p0=picks[0], p1=picks[1], text_xy=(0.130, 0.160),
        label="SupplierStockLength", orientation="vertical",
    )
    annotation = _format_supplier_reference(adapter, display, "SupplierStockLength")
    # ActivateView("") is documented to return False for sheet activation.
    # Read the actual edit mode and annotation ownership, not that return.
    drawing.ActivateView("")
    if drawing.GetEditSheet() is not True:
        raise RuntimeError("stock caption is not in sheet-edit mode")
    note = _early_bound(
        add_property_linked_note(adapter, "Supplier Reference Title", 0.016, 0.252), "INote"
    )
    if int(_early_bound(note.GetAnnotation(), "IAnnotation").OwnerType) != 1:
        raise RuntimeError("source-stock caption is not sheet-owned")
    return stock, iso, annotation


def _supplier_reference_identities(adapter: Any, references: dict[str, Any]) -> dict:
    """Capture native dimension, owner and attachment identities, not text values."""
    identities = {}
    for name, raw in references.items():
        annotation = _early_bound(raw, "IAnnotation")
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        full_name = str(_early_bound(display.GetDimension2(0), "IDimension").FullName)
        if not full_name or full_name in {value[0] for value in identities.values()}:
            raise RuntimeError(f"{name}: missing or duplicate native source identity")
        if name == "SupplierThreadMajor" and full_name.split("@")[:2] != [
            name, "SupplierReference"
        ]:
            raise RuntimeError("supplier major did not import its named model carrier")
        identities[name] = (
            full_name, view_name(adapter, annotation.Owner),
            tuple(annotation.GetAttachedEntities3() or ()),
            tuple(int(kind) for kind in (annotation.GetAttachedEntityTypes() or ())),
        )
    return identities


def _assert_supplier_references(adapter: Any, identities: dict, configurations: dict) -> None:
    """Fresh post-rebuild census, exact values, native attachment and stock separation."""
    if set(identities) != set(SUPPLIER_REFERENCE_DIMENSIONS):
        raise RuntimeError("supplier reference coverage is incomplete")
    required = {record[0]: name for name, record in identities.items()}
    counts = {name: 0 for name in identities}
    found_views = set()
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    for sheet_name in SHEET_NAMES:
        if not drawing.ActivateSheet(sheet_name):
            raise RuntimeError(f"cannot activate settled sheet {sheet_name}")
        sheet_view = _early_bound(drawing.GetFirstView(), "IView")
        if sheet_name == SHEET_NAMES[1]:
            titles = [
                _early_bound(annotation.GetSpecificAnnotation(), "INote")
                for raw in sheet_view.GetAnnotations() or ()
                if int((annotation := _early_bound(raw, "IAnnotation")).GetType()) == 6
                and int(annotation.OwnerType) == 1
                and str(_early_bound(annotation.GetSpecificAnnotation(), "INote").PropertyLinkedText or "")
                == property_link("Supplier Reference Title")
            ]
            if len(titles) != 1 or str(titles[0].GetText() or "").replace("\r", "") != SUPPLIER_STOCK_TITLE:
                raise RuntimeError("settled source-stock sheet caption changed")
        view = sheet_view.GetNextView()
        while view is not None:
            view = _early_bound(view, "IView")
            owner = view_name(adapter, view)
            found_views.add(owner)
            if configurations.get(owner) != (sheet_name, str(view.ReferencedConfiguration)):
                raise RuntimeError(f"{owner}: finished/source-stock configuration changed")
            if (sheet_name == SHEET_NAMES[1]) != (
                str(view.ReferencedConfiguration) == SUPPLIER_STOCK_CONFIGURATION
            ):
                raise RuntimeError(f"{owner}: finished/source-stock separation was lost")
            for raw in view.GetDisplayDimensions() or ():
                display = _early_bound(raw, "IDisplayDimension")
                dimension = _early_bound(display.GetDimension2(0), "IDimension")
                full_name = str(dimension.FullName)
                name = required.get(full_name)
                if name is None:
                    if sheet_name == SHEET_NAMES[1] or "@SupplierReference@" in full_name:
                        raise RuntimeError(f"unexpected source-stock dimension {full_name}")
                    continue
                counts[name] += 1
                _full_name, expected_owner, entities, kinds = identities[name]
                annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
                if owner != expected_owner or view_name(adapter, annotation.Owner) != owner:
                    raise RuntimeError(f"{name}: native source owner changed")
                assert_supplier_reference_dimension(
                    adapter, display, label=name, **SUPPLIER_REFERENCE_DIMENSIONS[name]
                )
                if name == "SupplierHeadHeight":
                    _assert_physical_head_height(adapter, view, display)
                attached = tuple(annotation.GetAttachedEntities3() or ())
                actual_kinds = tuple(int(kind) for kind in (annotation.GetAttachedEntityTypes() or ()))
                if len(attached) != len(entities) or actual_kinds != kinds or any(
                    not _is_same_attachment(
                        adapter, actual, expected, "SILHOUETTE" if kind == 46 else "EDGE"
                    )
                    for actual, expected, kind in zip(attached, entities, kinds, strict=True)
                ):
                    raise RuntimeError(f"{name}: native source attachment changed")
                if int(_early_bound(dimension.Tolerance, "IDimensionTolerance").Type) != 0:
                    raise RuntimeError(f"{name}: an unsupported supplier band was added")
            view = view.GetNextView()
    if found_views != set(configurations) or any(count != 1 for count in counts.values()):
        raise RuntimeError(f"settled supplier view/dimension census changed: {counts}")


@_telemetry.traced("drawing.stud_head_height_saved")
def _assert_saved_physical_head_height(adapter: Any, identities: dict, configurations: dict) -> None:
    """Audit only the finalized, closed SLDDRW, read-only; never rebuild or repair."""
    label = "SupplierHeadHeight"
    full_name, expected_owner, _entities, _kinds = identities[label]
    expected_configuration = configurations[expected_owner]
    if not full_name or expected_configuration[0] != SHEET_NAMES[0]:
        raise RuntimeError(f"{label}: saved identity is not on the finished sheet")
    saved_path = Path(OUTPUTS.slddrw).resolve()
    if not saved_path.is_file() or saved_path.suffix.lower() != ".slddrw":
        raise RuntimeError(f"{label}: finalized SLDDRW is missing")
    path_string = str(saved_path)
    app = _early_bound(adapter.swApp, "ISldWorks")
    if app.GetOpenDocumentByName(path_string) is not None:
        raise RuntimeError(f"{label}: finalize and close the drawing before saved proof")
    previous_model = adapter.currentModel
    try:
        opened = app.OpenDoc6(path_string, 3, 3, "", 0, 0)  # drawing, silent | read-only
        if not isinstance(opened, tuple) or len(opened) != 3:
            raise RuntimeError(f"{label}: saved OpenDoc6 did not return model/errors/warnings")
        model, errors, warnings = opened
        if model is None or errors != 0:
            raise RuntimeError(f"{label}: saved open failed ({errors=}, {warnings=})")
        model = _early_bound(model, "IModelDoc2")
        registered = app.GetOpenDocumentByName(path_string)
        if (
            int(model.GetType()) != 3
            or str(Path(str(model.GetPathName())).resolve()).casefold() != path_string.casefold()
            or registered is None
            or int(app.IsSame(registered, model)) != 1
            or app.ActiveDoc is None
            or int(app.IsSame(app.ActiveDoc, model)) != 1
        ):
            raise RuntimeError(f"{label}: saved reader acquired the wrong current drawing")
        adapter.currentModel = model
        drawing = _early_bound(model, "IDrawingDoc")
        if tuple(drawing.GetSheetNames() or ()) != SHEET_NAMES:
            raise RuntimeError(f"{label}: saved sheet census changed")
        matches = []
        for sheet_name in SHEET_NAMES:
            if not drawing.ActivateSheet(sheet_name):
                raise RuntimeError(f"{label}: cannot activate saved sheet {sheet_name}")
            sheet_view = _early_bound(drawing.GetFirstView(), "IView")
            view = sheet_view.GetNextView()
            while view is not None:
                view = _early_bound(view, "IView")
                for raw in view.GetDisplayDimensions() or ():
                    display = _early_bound(raw, "IDisplayDimension")
                    raw_dimension = display.GetDimension2(0)
                    if raw_dimension is None:
                        raise RuntimeError(f"{label}: saved dimension has no native identity")
                    dimension = _early_bound(raw_dimension, "IDimension")
                    if str(dimension.FullName) == full_name:
                        matches.append((sheet_name, view, display))
                view = view.GetNextView()
        if len(matches) != 1:
            raise RuntimeError(f"{label}: saved native FullName census is {len(matches)}, expected 1")
        sheet_name, front, display = matches[0]
        raw_annotation = display.GetAnnotation()
        if raw_annotation is None:
            raise RuntimeError(f"{label}: saved native dimension has no annotation")
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if (
            view_name(adapter, front) != expected_owner
            or view_name(adapter, annotation.Owner) != expected_owner
            or (sheet_name, str(front.ReferencedConfiguration)) != expected_configuration
        ):
            raise RuntimeError(f"{label}: saved native owner/configuration changed")
        if not drawing.ActivateSheet(sheet_name):
            raise RuntimeError(f"{label}: cannot reactivate saved finished sheet")
        if adapter.currentModel is None or int(app.IsSame(adapter.currentModel, model)) != 1:
            raise RuntimeError(f"{label}: saved reader lost the adapter's exact current drawing")
        measured = _assert_physical_head_height(adapter, front, display)
        assert_supplier_reference_dimension(
            adapter, display, label=label, **SUPPLIER_REFERENCE_DIMENSIONS[label]
        )
        native = _early_bound(display.GetDimension2(0), "IDimension")
        if int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0:
            raise RuntimeError(f"{label}: an unsupported supplier band was added after saving")
        bearing_point, top_point = _head_height_points_mm()
        _telemetry.event(
            "drawing.physical_head_height", phase="after_saved_reopen",
            full_name=full_name, measured_mm=measured, owner=expected_owner,
            configuration=str(front.ReferencedConfiguration),
            bearing_point_mm=bearing_point, top_point_mm=top_point,
            top_radius_mm=HEAD_AF / 2, open_warning_raw=warnings,
        )
    finally:
        try:
            reopened = app.GetOpenDocumentByName(path_string)
            if reopened is not None:
                reopened = _early_bound(reopened, "IModelDoc2")
                if (
                    int(reopened.GetType()) != 3
                    or str(Path(str(reopened.GetPathName())).resolve()).casefold()
                    != path_string.casefold()
                ):
                    raise RuntimeError(f"{label}: refuse to close an unrelated saved-proof document")
                title = str(reopened.GetTitle() or "")
                if not title:
                    raise RuntimeError(f"{label}: reopened drawing has no title for close")
                app.CloseDoc(title)
                if app.GetOpenDocumentByName(path_string) is not None:
                    raise RuntimeError(f"{label}: saved proof drawing did not close")
        finally:
            adapter.currentModel = previous_model


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open modified knife-hanger bolt", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Purchased Screw Note",
        "Supplier Reference Title",
    )
    properties = read_required_properties(
        adapter.currentModel, required, required=required
    )
    draw, _sheet = new_project_drawing(
        adapter, property_view=SPEC.artifact_stem, scale=SHEET_SCALE, layout=SPEC.layout
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="finished and original knife-hanger stock")
    if not _early_bound(draw, "IDrawingDoc").ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("cannot activate finished knife-hanger sheet")
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: "Knife-Hanger Bolt — Modified Stock Drawing",
            1: "Reference cut length, end chamfer and modified-part thread-tail acceptance",
            2: "Harmonic Analyzer Project",
            3: "MHA-SM-VN-52; McMaster-Carr 92314A253",
            4: "Native reference cut length, chamfer and thread-tail controls",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    # The consumed deburr sketch and the hidden thread-tail acceptance sketch
    # both lie on the Front plane, so the main view carries every control.
    annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="under-head length, cut-end chamfer and inspected thread tail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    verify_machining_controls(
        adapter,
        verify_cut_length_reference(adapter, annotations),
        expected=EXPECTED_CONTROLS,
        tolerance_types=DIMENSION_TOLERANCE_TYPES,
        precision=DIMENSION_PRECISION,
    )
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        if str(display.GetText(4) or "").replace("\r", "") != DIMENSION_CALLOUTS.get(
            name, ""
        ):
            raise RuntimeError(
                f"{name}: modified-part acceptance callout did not persist"
            )
    offset_dimension_text(adapter, annotations, {"ChamferWidth": CHAMFER_TEXT_XY})
    supplier_refs = _add_supplier_references(adapter, front)
    head_edge = model_point_in_view(
        adapter,
        front,
        tuple(value / 1000 for value in HEAD_PICK_MM),
        label="purchased hex head top edge",
    )
    note = _early_bound(
        add_property_linked_callout(
            adapter,
            front,
            property_name="Purchased Screw Note",
            edge_xy=head_edge,
            note_xy=PURCHASED_NOTE_XY,
        ),
        "INote",
    )
    printed = str(note.GetText() or "").replace("\r", "")
    if str(note.PropertyLinkedText or "") != property_link(
        "Purchased Screw Note"
    ) or printed != properties["Purchased Screw Note"].replace("\r", ""):
        raise RuntimeError("Purchased Screw Note: linked head note did not persist")
    stock, stock_iso, stock_annotation = _add_stock_reference(adapter)
    supplier_refs["SupplierStockLength"] = stock_annotation
    identities = _supplier_reference_identities(adapter, supplier_refs)
    configurations = {
        view_name(adapter, view): (sheet, str(_early_bound(view, "IView").ReferencedConfiguration))
        for sheet, views in ((SHEET_NAMES[0], (front, iso)), (SHEET_NAMES[1], (stock, stock_iso)))
        for view in views
    }
    if properties["Supplier Reference Title"].replace("\r", "") != SUPPLIER_STOCK_TITLE:
        raise RuntimeError("source-stock title does not identify the original screw")
    artifacts = await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Knife-Hanger Bolt — Modified Stock Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        settled_checks=(lambda: _assert_supplier_references(adapter, identities, configurations),),
    )
    _assert_saved_physical_head_height(adapter, identities, configurations)
    return artifacts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
