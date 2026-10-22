"""Create MHA-PD-VN-57's drawing with creation/settled/saved physical axial proofs.

Keep original identities for settled checks. Capture the actual serialized
FullNames from those same annotations only after successful saves/audit, at
``before_drawing_close``; cold reopening must find those exact names before
running the independent saved physical and presentation proofs.
"""

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
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_edges import scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_leader_notes import add_property_linked_callout
from _drawing_notes import add_property_linked_note, property_link
from _drawing_physical_axial_dimension import (
    add_native_physical_axial_dimension,
    assert_native_physical_axial_dimension,
    capture_serialized_physical_axial_names,
)
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _mcmaster_90325a174 import TIP_CHAMFER
from _session import run_build
from _stock_trim_drawing import verify_machining_controls
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from pd_vn_transgear_pivot_screw_spec import (
    CHAMFER_ANGLE,
    CHAMFER_ANGLE_TOLERANCE,
    CHAMFER_WIDTH,
    DIMENSION_CALLOUTS,
    DIMENSION_PRECISION,
    DIMENSION_TOLERANCE_TYPES,
    DRAWING_DIMENSIONS,
    FITTED_THREAD_LEN,
    HEAD_CHAMFER,
    HEAD_DIA,
    HEAD_H,
    SHOULDER_END_Y,
    SHOULDER_DIA,
    SKU,
    SOCKET_AF,
    SUPPLIER_DRAWING_DIMENSIONS,
    SUPPLIER_REFERENCE_BANDS,
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_STOCK_CONFIGURATION,
    SUPPLIER_STOCK_TITLE,
    THREAD_LEN,
    THREAD_LENGTH_MIN,
    THREAD_MAJOR,
    TIP_Y,
)

SPEC = DRAWINGS_BY_NAME["pd_vn_transgear_pivot_screw"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SHEET_SCALE = (4.0, 1.0)
ISO_SCALE = SHEET_SCALE  # One-scale sheet: no per-view scale label.
SHEET_NAMES = ("FINISHED", "90325A174-STOCK")
_SHEET_PER_MODEL_MM = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000
# Sheet metres. The Front view centres the part's Y box (faced tip to head
# top), so the tip lands half the scaled part height below it.
FRONT_CENTER = (0.140, 0.150)
TIP_SHEET_Y = FRONT_CENTER[1] - (HEAD_H - TIP_Y) / 2 * _SHEET_PER_MODEL_MM
SHOULDER_END_SHEET_Y = TIP_SHEET_Y + FITTED_THREAD_LEN * _SHEET_PER_MODEL_MM
# The chamfer meets the tip face one leg inside the thread major radius.
_CHAMFER_VERTEX = (
    FRONT_CENTER[0] + (THREAD_MAJOR / 2 - CHAMFER_WIDTH) * _SHEET_PER_MODEL_MM,
    TIP_SHEET_Y,
)
_ANGLE_TEXT_RADIUS = 0.016
# The B-size inner border is 12.7 mm in from the sheet edge; the title block
# spans x >= 0.216 below y = 0.065.
FRONT_KEEP = {
    # The reference length's dimension line stands left of the thread, level
    # with the span from the shoulder end to the tip; its text leaves on a
    # leader (CUT_LENGTH_TEXT_XY).
    "CutLength": (0.115, (TIP_SHEET_Y + SHOULDER_END_SHEET_Y) / 2),
    # The tail's text stands right of the shank, above its top extension
    # line, so neither extension line crosses the text or its lines.
    "ThreadLengthMin": (
        0.180,
        TIP_SHEET_Y + THREAD_LENGTH_MIN * _SHEET_PER_MODEL_MM + 0.016,
    ),
    # Dimension line 6 mm under the chamfer leg; its text leaves on a leader.
    "ChamferWidth": (
        FRONT_CENTER[0] + (THREAD_MAJOR - CHAMFER_WIDTH) / 2 * _SHEET_PER_MODEL_MM,
        TIP_SHEET_Y - 0.006,
    ),
    # The native 45 degrees in the open wedge right of the tip, 16 mm out on
    # the angle's bisector, below the tail's top extension line.
    "ChamferAngle": (
        _CHAMFER_VERTEX[0]
        + _ANGLE_TEXT_RADIUS * math.cos(math.radians(CHAMFER_ANGLE / 2)),
        _CHAMFER_VERTEX[1]
        + _ANGLE_TEXT_RADIUS * math.sin(math.radians(CHAMFER_ANGLE / 2)),
    ),
}
# The chamfer callout stands below-right of the tip, under the tail's lower
# extension line and right of the leg's own extension lines.
CHAMFER_TEXT_XY = (0.185, TIP_SHEET_Y - 0.018)
# The reference length's four lines stand wholly left of its dimension line
# (73 mm wide), so neither its arrows nor its extension lines strike them.
CUT_LENGTH_TEXT_XY = (0.062, (TIP_SHEET_Y + SHOULDER_END_SHEET_Y) / 2)
# The purchased-screw note flags the unmodified head and shoulder. Keep its
# head-top landing fixed; place the note farther into the right field so its
# straight leader bypasses the complete head-diameter text envelope.
HEAD_PICK_MM = (HEAD_DIA / 4, HEAD_H, 0.0)
PURCHASED_NOTE_XY = (0.190, 0.245)
# Every view and the sheet are 4:1, so the title-block SCALE is the view
# scale and the isometric carries no scale label.
ISO_CENTER = (0.360, 0.165)
STOCK_CENTER = (0.180, 0.155)
STOCK_ISO_CENTER = (0.325, 0.165)
TOP_CENTER = (0.295, 0.245)
# The cutting controls verify_machining_controls re-reads. CutLength, the
# fit-up length, still drives the facing cut but prints as a reference.
EXPECTED_CONTROLS = {
    "ChamferWidth": (CHAMFER_WIDTH / 1000, 0.0, 0.0),
    "ChamferAngle": (
        math.radians(CHAMFER_ANGLE),
        -math.radians(CHAMFER_ANGLE_TOLERANCE),
        math.radians(CHAMFER_ANGLE_TOLERANCE),
    ),
    "ThreadLengthMin": (THREAD_LENGTH_MIN / 1000, 0.0, 0.0),
}
if not math.isclose(SHOULDER_END_Y - FITTED_THREAD_LEN, TIP_Y, abs_tol=1e-9):
    raise AssertionError("the reference length does not end at the faced tip")


def _verify_reference_length(adapter: Any, annotation: Any) -> None:
    """The fit-up length prints "(9.15)" with no band (rule 19)."""
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if not math.isclose(
        float(dimension.SystemValue), FITTED_THREAD_LEN / 1000, abs_tol=1e-9
    ):
        raise RuntimeError("CutLength: native reference nominal changed")
    if int(display.GetPrimaryPrecision2()) != DIMENSION_PRECISION["CutLength"]:
        raise RuntimeError("CutLength: native display precision changed")
    if (
        int(tolerance.Type) != DIMENSION_TOLERANCE_TYPES["CutLength"]
        or (str(display.GetText(1) or ""), str(display.GetText(2) or "")) != ("(", ")")
        or not bool(display.ShowDimensionValue)
    ):
        raise RuntimeError("CutLength: reference display did not persist")


def _assert_supplier_tolerance(display: Any, name: str) -> None:
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    band = SUPPLIER_REFERENCE_BANDS.get(name)
    if int(tolerance.Type) != (2 if band is not None else 0):
        raise RuntimeError(f"{name}: native supplier tolerance type changed")
    if band is not None:
        lower, upper = (value / 1000 for value in band)
        if (
            not math.isclose(float(tolerance.GetMinValue()), lower, rel_tol=0.0, abs_tol=1e-12)
            or not math.isclose(float(tolerance.GetMaxValue()), upper, rel_tol=0.0, abs_tol=1e-12)
            or int(display.GetPrimaryTolPrecision2()) != SUPPLIER_REFERENCE_DIMENSIONS[name]["precision"]
        ):
            raise RuntimeError(f"{name}: model-owned source supplier band changed")


def _format_supplier_reference(adapter: Any, display: Any, name: str) -> Any:
    """Only purchased-reference presentation is drawing-owned; bands are read-only."""
    display = _early_bound(display, "IDisplayDimension")
    supplier_reference_dimension(
        adapter, display, label=name, **SUPPLIER_REFERENCE_DIMENSIONS[name]
    )
    _assert_supplier_tolerance(display, name)
    return _early_bound(display.GetAnnotation(), "IAnnotation")



def _head_height_points() -> tuple[tuple[float, float, float], ...]:
    """Actual bearing and true head-top rim points, in model metres."""
    return tuple(
        (radius / math.sqrt(2) / 1000, y / 1000, radius / math.sqrt(2) / 1000)
        for y, radius in ((0.0, HEAD_DIA / 2), (HEAD_H, HEAD_DIA / 2 - HEAD_CHAMFER))
    )


@_telemetry.traced("drawing.pivot_head_height_entities")
def _head_height_entities(adapter: Any, front: Any) -> tuple[Any, Any]:
    """Name one physical arc at each station; circle parameters alone are not identity."""
    front = _early_bound(front, "IView")
    if int(front.GetDisplayMode2()) != 2:  # swDisplayMode_e.swHIDDEN
        raise RuntimeError("SupplierHeadHeight: front view is not hidden-lines-removed")
    scan = scan_view_edges(front, label="SupplierHeadHeight physical head rims")
    resolved = []
    for station, y, radius, point in zip(
        ("bearing", "top"),
        (0.0, HEAD_H),
        (HEAD_DIA / 2, HEAD_DIA / 2 - HEAD_CHAMFER),
        _head_height_points(),
        strict=True,
    ):
        matches, candidates = [], []
        for item in scan.circles:
            geometry = tuple(float(value) for value in item.circle)
            cx, cy, cz, nx, ny, nz, actual_r = geometry
            center_error = math.dist((cx, cy, cz), (0.0, y, 0.0))
            radius_error = abs(actual_r - radius)
            axis_error = max(abs(nx), abs(abs(ny) - 1.0), abs(nz))
            named_circle = (
                all(math.isfinite(value) for value in geometry)
                and center_error <= 1e-5
                and radius_error <= 1e-5
                and axis_error <= 1e-6
            )
            candidate = {
                "circle_mm": geometry,
                "center_error_mm": center_error,
                "radius_error_mm": radius_error,
                "axis_error": axis_error,
                "nearest_m": (),
                "point_error_m": None,
            }
            candidates.append(candidate)
            if not named_circle:
                continue
            raw = _early_bound(item.edge, "IEdge").GetClosestPointOn(
                point[0], point[1], point[2]
            )
            nearest = tuple(float(value) for value in (raw or ())[:3])
            candidate["nearest_m"] = nearest
            if len(nearest) != 3 or not all(math.isfinite(value) for value in nearest):
                continue
            point_error = math.dist(nearest, point)
            candidate["point_error_m"] = point_error
            if point_error > 1e-8:
                continue
            matches.append(item.edge)
        candidates.sort(key=lambda item: (
            item["center_error_mm"] + item["radius_error_mm"] + item["axis_error"],
            item["point_error_m"] if item["point_error_m"] is not None else math.inf,
        ))
        evidence = candidates[:12]
        _telemetry.event(
            "drawing.pivot_head_height_edges", station=station,
            point_m=point, matches=len(matches), candidate_count=len(candidates),
            candidates=evidence,
        )
        if len(matches) != 1:
            raise RuntimeError(
                f"SupplierHeadHeight: {station} physical rim has {len(matches)} matches; "
                f"expected exactly 1 at y={y:g} r={radius:g} mm: {evidence!r}"
            )
        resolved.append(matches[0])
    if int(adapter.swApp.IsSame(resolved[0], resolved[1])) != 0:
        raise RuntimeError("SupplierHeadHeight: physical rim pair is not distinct")
    return resolved[0], resolved[1]


@_telemetry.traced("drawing.pivot_head_height_assert")
def _assert_physical_head_height(
    adapter: Any, front: Any, display: Any, *, entities: tuple[Any, Any] | None = None,
    phase: str = "settled",
) -> float:
    """Prove native vertical value/attachments; settled and saved calls rescan rims."""
    if entities is None:
        entities = _head_height_entities(adapter, front)
    return assert_native_physical_axial_dimension(
        adapter, front, display, entities=entities, points_m=_head_height_points(),
        expected_mm=HEAD_H, label="SupplierHeadHeight", phase=phase,
    )


@_telemetry.traced("drawing.pivot_head_height_add")
def _add_physical_head_height(
    adapter: Any, front: Any, text_xy: tuple[float, float]
) -> Any:
    """Select and read back the named physical rims, never coordinate-hit-test them."""
    entities = _head_height_entities(adapter, front)
    picks = model_points_in_view(
        adapter, front, _head_height_points(), label="SupplierHeadHeight physical rim points"
    )
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    drawing = _early_bound(model, "IDrawingDoc")
    manager = _early_bound(model.SelectionManager, "ISelectionMgr")
    try:
        if not drawing.ActivateView(view_name(adapter, front)):
            raise RuntimeError("SupplierHeadHeight: cannot activate exact front view")
        model.ClearSelection2(True)
        selected = []
        for index, (entity, point) in enumerate(zip(entities, picks, strict=True), 1):
            data = _early_bound(manager.CreateSelectData(), "ISelectData")
            data.View = front
            if not _early_bound(entity, "IEntity").Select4(index > 1, data):
                raise RuntimeError(f"SupplierHeadHeight: failed to select physical edge {index}")
            if int(manager.GetSelectedObjectCount2(-1)) != index:
                raise RuntimeError(f"SupplierHeadHeight: selection count changed at edge {index}")
            if int(manager.GetSelectedObjectType3(index, -1)) != 1:
                raise RuntimeError(f"SupplierHeadHeight: selected object {index} is not an EDGE")
            actual = manager.GetSelectedObject6(index, -1)
            if actual is None or int(adapter.swApp.IsSame(actual, entity)) != 1:
                raise RuntimeError(f"SupplierHeadHeight: wrong selected object at edge {index}")
            if selected and int(adapter.swApp.IsSame(selected[0], actual)) != 0:
                raise RuntimeError("SupplierHeadHeight: selected edges are not distinct")
            selected.append(actual)
            if manager.SetSelectionPoint2(index, -1, point[0], point[1], 0.0) is not True:
                raise RuntimeError(f"SupplierHeadHeight: cannot set physical selection point {index}")
        display = model.AddVerticalDimension2(text_xy[0], text_xy[1], 0.0)
        if display is None:
            raise RuntimeError("SupplierHeadHeight: native vertical dimension creation returned null")
        _assert_physical_head_height(adapter, front, display, entities=entities, phase="creation")
        return display
    finally:
        model.ClearSelection2(True)


def _add_supplier_references(adapter: Any, front: Any, top: Any) -> dict[str, Any]:
    """Measure physical head/socket; import native nominal-major and source bands."""
    head_r = HEAD_DIA / 2
    authored = {}
    for name, view, first, second, text_xy, orientation, entity_type in (
        (
            "SupplierHeadDiameter", front,
            (-head_r, HEAD_H / 2, 0.0), (head_r, HEAD_H / 2, 0.0),
            (0.140, 0.225), "horizontal", "SILHOUETTE",
        ),
        (
            "SupplierSocketAF", top,
            (-SOCKET_AF / 2, HEAD_H, 0.0), (SOCKET_AF / 2, HEAD_H, 0.0),
            (TOP_CENTER[0], 0.212), "horizontal", "EDGE",
        ),
    ):
        picks = model_points_in_view(
            adapter, view,
            [tuple(value / 1000 for value in point) for point in (first, second)],
            label=name,
        )
        display = add_edge_dimension(
            adapter, view, p0=picks[0], p1=picks[1], text_xy=text_xy,
            label=name, orientation=orientation, entity_type=entity_type,
        )
        authored[name] = _format_supplier_reference(adapter, display, name)
        if name == "SupplierHeadDiameter":
            height = _add_physical_head_height(adapter, front, (0.224, 0.201))
            authored["SupplierHeadHeight"] = _format_supplier_reference(
                adapter, height, "SupplierHeadHeight"
            )
    references = curate_view_dimensions(
        adapter, front,
        keep={
            "SupplierThreadMajor": (0.239, 0.119),
            "SupplierShoulderDiameter": (0.202, 0.172),
            "SupplierShoulderLength": (0.065, 0.170),
        },
        view_label="supplier nominal envelopes and model-owned source bands",
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


@_telemetry.traced("drawing.pivot_stock_length_entities")
def _stock_length_entities(
    adapter: Any, stock: Any,
) -> tuple[tuple[Any, Any], tuple[tuple[float, float, float], ...]]:
    """Resolve the actual outer shoulder and factory-tip trimmed rims, afresh.

    On a fixed circle the closest native edge point to its forward +Z extremum
    maximizes Z even when the depicted thread interrupts the circle.  A second
    native query proves that returned point belongs to the actual trimmed edge.
    Supporting-circle membership alone is never sufficient.
    """
    label = "SupplierStockThreadLength"
    stock = _early_bound(stock, "IView")
    source_evidence: dict[str, Any] = {"configured_source_path": str(SOURCE.resolve())}
    try:
        referenced = stock.ReferencedDocument
        source_evidence["referenced_document_null"] = referenced is None
        if referenced is None:
            raise RuntimeError(f"{label}: stock view has no native source document")
        native_path = _early_bound(referenced, "IModelDoc2").GetPathName()
        source_evidence["native_source_path"] = native_path
        if (
            not isinstance(native_path, str) or not native_path
            or not Path(native_path).is_absolute()
            or Path(native_path).resolve() != SOURCE.resolve()
        ):
            raise RuntimeError(f"{label}: native source path does not match the exact supplier part")
        configuration = str(stock.ReferencedConfiguration)
        source_evidence["configuration"] = configuration
        mode = int(stock.GetDisplayMode2())
        source_evidence["display_mode"] = mode
        if configuration != SUPPLIER_STOCK_CONFIGURATION:
            raise RuntimeError(f"{label}: actual source configuration is not AS SUPPLIED STOCK")
        if mode != 2:  # swDisplayMode_e.swHIDDEN
            raise RuntimeError(f"{label}: stock view is not hidden-lines-removed")
    finally:
        _telemetry.event("drawing.pivot_stock_length_source", **source_evidence)
    scan = scan_view_edges(stock, label=f"{label} physical stock rims")
    resolved, points = [], []
    for station, y, radius in (
        ("shoulder_outer", SHOULDER_END_Y, SHOULDER_DIA / 2),
        ("factory_tip", SHOULDER_END_Y - THREAD_LEN, THREAD_MAJOR / 2 - TIP_CHAMFER),
    ):
        candidates, matches = [], []
        forward = (0.0, y / 1000, radius / 1000)
        for item in scan.circles:
            geometry = tuple(float(value) for value in item.circle)
            candidate = {
                "circle_mm": geometry, "center_error_mm": math.inf,
                "radius_error_mm": math.inf, "axis_error": math.inf,
            }
            candidates.append(candidate)
            if len(geometry) != 7 or not all(math.isfinite(value) for value in geometry):
                continue
            cx, cy, cz, nx, ny, nz, actual_r = geometry
            norm = math.hypot(nx, ny, nz)
            center_error = math.dist((cx, cy, cz), (0.0, y, 0.0))
            radius_error = abs(actual_r - radius)
            axis_error = (
                max(abs(nx / norm), abs(abs(ny / norm) - 1.0), abs(nz / norm))
                if norm > 0 else math.inf
            )
            candidate.update(
                center_error_mm=center_error, radius_error_mm=radius_error,
                axis_error=axis_error,
            )
            if (
                center_error > 1e-5 or radius_error > 1e-5
                or axis_error > 1e-6 or actual_r <= 0
            ):
                continue
            edge = _early_bound(item.edge, "IEdge")
            point = forward
            valid = True
            for query in ("forward", "membership"):
                try:
                    raw = edge.GetClosestPointOn(point[0], point[1], point[2])
                    length = 0 if raw is None else len(raw)
                    candidate[f"{query}_length"] = length
                    # SDK: XYZ, UParameter, NotUsed. Never inspect the fifth slot.
                    slots = tuple(raw[index] for index in range(min(length, 4)))
                except Exception as exc:
                    _telemetry.event(
                        "drawing.pivot_stock_length_edges", **source_evidence,
                        station=station, query=query, probe_m=point,
                        candidate_count=len(candidates), candidates=candidates[-12:],
                        native_error_type=type(exc).__name__, native_error=str(exc)[:300],
                    )
                    raise RuntimeError(f"{label}: {station} native trim query failed") from exc
                candidate[f"{query}_xyz_u"] = tuple(
                    value if isinstance(value, (int, float)) or value is None else repr(value)[:80]
                    for value in slots
                )
                if length != 5 or len(slots) != 4 or any(
                    isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) for value in slots
                ):
                    valid = False
                    break
                values = tuple(float(value) for value in slots)
                actual = values[:3]
                plane_error = abs(actual[1] - y / 1000)
                radius_residual = abs(math.hypot(actual[0], actual[2]) - radius / 1000)
                candidate[f"{query}_plane_error_m"] = plane_error
                candidate[f"{query}_radius_error_m"] = radius_residual
                if plane_error > 1e-8 or radius_residual > 1e-8:
                    valid = False
                    break
                if query == "membership":
                    error = math.dist(actual, point)
                    candidate["membership_error_m"] = error
                    if error > 1e-8:
                        valid = False
                else:
                    point = actual
            if valid:
                candidate["point_m"] = point
                matches.append((item.edge, point))
        matches.sort(key=lambda match: match[1][2], reverse=True)
        candidates.sort(key=lambda candidate: (
            candidate["center_error_mm"] + candidate["radius_error_mm"] + candidate["axis_error"],
            -candidate.get("point_m", (0.0, 0.0, -math.inf))[2],
        ))
        leaders = (
            [match for match in matches if abs(match[1][2] - matches[0][1][2]) <= 1e-8]
            if matches else []
        )
        evidence = candidates[:12]
        _telemetry.event(
            "drawing.pivot_stock_length_edges", **source_evidence,
            station=station, forward_m=forward,
            matches=len(matches), frontmost_matches=len(leaders),
            candidate_count=len(candidates), candidates=evidence,
        )
        if not leaders:
            raise RuntimeError(
                f"{label}: {station} physical stock rim has no actual native match: {evidence!r}"
            )
        edge, point = leaders[0]
        if any(int(adapter.swApp.IsSame(edge, other)) != 1 for other, _point in leaders[1:]):
            raise RuntimeError(f"{label}: {station} has ambiguous distinct frontmost edges")
        resolved.append(edge)
        points.append(point)
    if int(adapter.swApp.IsSame(resolved[0], resolved[1])) != 0:
        raise RuntimeError(f"{label}: physical stock rim pair is not distinct")
    return (resolved[0], resolved[1]), (points[0], points[1])


@_telemetry.traced("drawing.pivot_stock_length_assert")
def _assert_physical_stock_length(
    adapter: Any, stock: Any, display: Any, *, phase: str = "settled",
) -> float:
    """Fresh actual stock configuration, trimmed entities, points and native proof."""
    entities, points = _stock_length_entities(adapter, stock)
    return assert_native_physical_axial_dimension(
        adapter, stock, display, entities=entities, points_m=points,
        expected_mm=THREAD_LEN, label="SupplierStockThreadLength", phase=phase,
    )


def _add_stock_reference(adapter: Any) -> tuple[Any, Any, Any]:
    """Measure the original .375-inch thread on its separate stock-only sheet."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not drawing.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("cannot activate original pivot-screw stock sheet")
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
            raise RuntimeError("source-stock view references the faced screw")
        if not set_view_position(adapter, view, *centre):
            raise RuntimeError("cannot position source-stock view")
        set_hidden_lines_removed(adapter, view)
    entities, points = _stock_length_entities(adapter, stock)
    display = add_native_physical_axial_dimension(
        adapter, stock, entities=entities, points_m=points, text_xy=(0.130, 0.118),
        expected_mm=THREAD_LEN, label="SupplierStockThreadLength",
    )
    annotation = _format_supplier_reference(adapter, display, "SupplierStockThreadLength")
    drawing.ActivateView("")  # False is documented when activating the sheet.
    if drawing.GetEditSheet() is not True:
        raise RuntimeError("stock caption is not in sheet-edit mode")
    note = _early_bound(
        add_property_linked_note(adapter, "Supplier Reference Title", 0.016, 0.252), "INote"
    )
    if int(_early_bound(note.GetAnnotation(), "IAnnotation").OwnerType) != 1:
        raise RuntimeError("source-stock caption is not sheet-owned")
    return stock, iso, annotation


def _supplier_reference_identities(adapter: Any, references: dict[str, Any]) -> dict:
    """Capture exact native identities; no drawing text stands in for a source size."""
    identities = {}
    source_names = {name for names in SUPPLIER_DRAWING_DIMENSIONS.values() for name in names}
    for name, raw in references.items():
        annotation = _early_bound(raw, "IAnnotation")
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        full_name = str(_early_bound(display.GetDimension2(0), "IDimension").FullName)
        if not full_name or full_name in {value[0] for value in identities.values()}:
            raise RuntimeError(f"{name}: missing or duplicate native source identity")
        if name in source_names and full_name.split("@")[:2] != [name, "SupplierReference"]:
            raise RuntimeError(f"{name}: imported reference has the wrong model carrier")
        identities[name] = (
            full_name, view_name(adapter, annotation.Owner),
            tuple(annotation.GetAttachedEntities3() or ()),
            tuple(int(kind) for kind in (annotation.GetAttachedEntityTypes() or ())),
        )
    return identities


def _assert_supplier_references(adapter: Any, identities: dict, configurations: dict) -> None:
    """Fresh post-rebuild value/precision/band/identity/count/configuration checks."""
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
                native = display.GetDimension2(0)
                if native is None:
                    raise RuntimeError(f"{owner}: settled display has no native dimension")
                dimension = _early_bound(native, "IDimension")
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
                    _assert_physical_head_height(adapter, view, display, phase="settled")
                elif name == "SupplierStockThreadLength":
                    _assert_physical_stock_length(adapter, view, display, phase="settled")
                attached = tuple(annotation.GetAttachedEntities3() or ())
                actual_kinds = tuple(int(kind) for kind in (annotation.GetAttachedEntityTypes() or ()))
                if len(attached) != len(entities) or actual_kinds != kinds or any(
                    not _is_same_attachment(
                        adapter, actual, expected, "SILHOUETTE" if kind == 46 else "EDGE"
                    )
                    for actual, expected, kind in zip(attached, entities, kinds, strict=True)
                ):
                    raise RuntimeError(f"{name}: native source attachment changed")
                _assert_supplier_tolerance(display, name)
            view = view.GetNextView()
    if found_views != set(configurations) or any(count != 1 for count in counts.values()):
        raise RuntimeError(f"settled supplier view/dimension census changed: {counts}")


@_telemetry.traced("drawing.pivot_physical_references_saved")
def _assert_saved_physical_references(
    adapter: Any, identities: dict, configurations: dict, *,
    serialized_full_names: dict[str, str],
) -> None:
    """Cold-read exact serialized names, then prove BOTH physical sizes afresh."""
    names = ("SupplierHeadHeight", "SupplierStockThreadLength")
    if (
        set(serialized_full_names) != set(names)
        or any(not isinstance(value, str) or not value for value in serialized_full_names.values())
        or len(set(serialized_full_names.values())) != 2
    ):
        raise RuntimeError(
            "physical references: missing, extra, empty or duplicate serialized FullNames; "
            f"expected labels={names!r}, serialized_full_names={serialized_full_names!r}"
        )
    required = {serialized_full_names[name]: name for name in names}
    path = OUTPUTS.slddrw.resolve()
    if not path.is_file():
        raise RuntimeError("SupplierHeadHeight: saved drawing is missing")
    path_string = str(path)
    app = _early_bound(adapter.swApp, "ISldWorks")
    previous = adapter.currentModel
    if app.GetOpenDocumentByName(path_string) is not None:
        raise RuntimeError("SupplierHeadHeight: finalize and close drawing before saved proof")
    try:
        opened = app.OpenDoc6(path_string, 3, 3, "", 0, 0)
        if not isinstance(opened, tuple) or len(opened) != 3:
            raise RuntimeError("SupplierHeadHeight: saved OpenDoc6 did not return model/errors/warnings")
        model, errors, warnings = opened
        if model is None or int(errors) != 0:
            raise RuntimeError(
                f"SupplierHeadHeight: saved drawing open failed ({errors=}, {warnings=})"
            )
        model = _early_bound(model, "IModelDoc2")
        if Path(str(model.GetPathName())).resolve() != path or int(model.GetType()) != 3:
            raise RuntimeError("SupplierHeadHeight: saved drawing path/type mismatch")
        current = app.GetOpenDocumentByName(path_string)
        if (
            current is None or int(app.IsSame(current, model)) != 1
            or app.ActiveDoc is None or int(app.IsSame(app.ActiveDoc, model)) != 1
        ):
            raise RuntimeError("SupplierHeadHeight: reopened file is not the current drawing")
        adapter.currentModel = model
        drawing = _early_bound(model, "IDrawingDoc")
        if tuple(str(name) for name in (drawing.GetSheetNames() or ())) != SHEET_NAMES:
            raise RuntimeError("SupplierHeadHeight: saved sheet census changed")
        expected_original_full_names = {name: identities[name][0] for name in names}
        matches = {name: [] for name in names}
        inventory = []
        inventory_errors = []
        document = {}
        try:
            document["document_path"] = model.GetPathName()
            document["document_title"] = model.GetTitle()
            document["document_type"] = model.GetType()
        except Exception as error:
            document["errors"] = [f"{type(error).__name__}: {error}"]
            inventory_errors.append(error)
        for sheet_name in SHEET_NAMES:
            try:
                if not drawing.ActivateSheet(sheet_name):
                    raise RuntimeError(f"physical references: cannot activate saved sheet {sheet_name}")
                view = _early_bound(drawing.GetFirstView(), "IView")
            except Exception as error:
                inventory.append({
                    "sheet": sheet_name, "errors": [f"{type(error).__name__}: {error}"],
                })
                inventory_errors.append(error)
                continue
            is_sheet_view = True
            while view is not None:
                view = _early_bound(view, "IView")
                record: dict[str, Any] = {
                    "sheet": sheet_name, "is_sheet_view": is_sheet_view, "dimensions": [],
                }
                inventory.append(record)
                try:
                    record["view"] = view_name(adapter, view)
                    record["configuration"] = view.ReferencedConfiguration
                    source = view.ReferencedDocument
                    record["source_document_null"] = source is None
                    if source is not None:
                        record["source_document_path"] = _early_bound(
                            source, "IModelDoc2"
                        ).GetPathName()
                except Exception as error:
                    record.setdefault("errors", []).append(f"{type(error).__name__}: {error}")
                    inventory_errors.append(error)
                try:
                    raw_dimensions = view.GetDisplayDimensions()
                    record["raw_none"] = raw_dimensions is None
                    if raw_dimensions is not None and not isinstance(raw_dimensions, (tuple, list)):
                        raise RuntimeError("physical references: malformed saved display array")
                    dimensions = () if raw_dimensions is None else raw_dimensions
                    record["count"] = len(dimensions)
                except Exception as error:
                    record.setdefault("errors", []).append(f"{type(error).__name__}: {error}")
                    inventory_errors.append(error)
                    dimensions = ()
                for index, raw in enumerate(dimensions):
                    item: dict[str, Any] = {"index": index, "display_null": raw is None}
                    record["dimensions"].append(item)
                    try:
                        if raw is None:
                            raise RuntimeError("physical references: saved display is null")
                        display = _early_bound(raw, "IDisplayDimension")
                        native = display.GetDimension2(0)
                        item["native_dimension_null"] = native is None
                        if native is None:
                            raise RuntimeError("physical references: saved display has no native dimension")
                        full_name = _early_bound(native, "IDimension").FullName
                        item["full_name"] = full_name
                        if not isinstance(full_name, str) or not full_name:
                            raise RuntimeError("physical references: saved native FullName is empty or invalid")
                        name = required.get(full_name)
                        if name is not None:
                            matches[name].append((sheet_name, view, display))
                    except Exception as error:
                        item.setdefault("errors", []).append(f"{type(error).__name__}: {error}")
                        inventory_errors.append(error)
                    if raw is None:
                        continue
                    try:
                        display = _early_bound(raw, "IDisplayDimension")
                        # SDK: IDisplayDimension.GetNameForSelection() has zero arguments.
                        item["selection_name"] = display.GetNameForSelection()
                    except Exception as error:
                        item.setdefault("errors", []).append(f"{type(error).__name__}: {error}")
                        inventory_errors.append(error)
                    try:
                        display = _early_bound(raw, "IDisplayDimension")
                        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
                        item["annotation_null"] = annotation is None
                        if annotation is None:
                            raise RuntimeError("physical references: saved annotation is null")
                        # SDK: IAnnotation.GetName() has zero arguments.
                        item["annotation_name"] = annotation.GetName()
                        item["owner_type"] = annotation.OwnerType
                        native_owner = annotation.Owner
                        item["owner_null"] = native_owner is None
                        if native_owner is not None:
                            item["owner_same_view"] = app.IsSame(native_owner, view)
                            if item["owner_type"] == 0:
                                item["owner"] = view_name(adapter, native_owner)
                    except Exception as error:
                        item.setdefault("errors", []).append(f"{type(error).__name__}: {error}")
                        inventory_errors.append(error)
                try:
                    view = view.GetNextView()
                    is_sheet_view = False
                except Exception as error:
                    record.setdefault("errors", []).append(f"{type(error).__name__}: {error}")
                    inventory_errors.append(error)
                    break
        label_match_counts = {name: len(matches[name]) for name in names}
        evidence = dict(
            phase="saved", expected_original_full_names=expected_original_full_names,
            expected_serialized_full_names=dict(serialized_full_names),
            label_match_counts=label_match_counts, inventory=inventory, **document,
        )
        _telemetry.event("drawing.physical_axial_identity_inventory", **evidence)
        if inventory_errors:
            raise RuntimeError(
                f"physical references: saved inventory getter/metadata refusal: "
                f"{inventory_errors[0]}; actual inventory={evidence!r}"
            ) from inventory_errors[0]
        if any(count != 1 for count in label_match_counts.values()):
            census = "; ".join(
                f"{name}: saved FullName census is {label_match_counts[name]}, expected exactly 1"
                for name in names
            )
            raise RuntimeError(f"{census}; actual inventory={evidence!r}")
        for name, expected_sheet in zip(names, SHEET_NAMES, strict=True):
            expected_owner = identities[name][1]
            captured_sheet, captured_configuration = configurations[expected_owner]
            if captured_sheet != expected_sheet:
                raise RuntimeError(f"{name}: captured owner is on the wrong sheet")
            if (name == "SupplierStockThreadLength") != (
                captured_configuration == SUPPLIER_STOCK_CONFIGURATION
            ):
                raise RuntimeError(f"{name}: captured source configuration changed")
        for name in names:
            original_full_name, expected_owner, _old_entities, _old_kinds = identities[name]
            full_name = serialized_full_names[name]
            sheet_name, front, display = matches[name][0]
            owner = view_name(adapter, front)
            annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
            if (
                owner != expected_owner
                or (sheet_name, str(front.ReferencedConfiguration)) != configurations[expected_owner]
                or annotation is None or view_name(adapter, annotation.Owner) != expected_owner
            ):
                raise RuntimeError(f"{name}: saved owner/configuration changed")
            if not drawing.ActivateSheet(sheet_name):
                raise RuntimeError(f"{name}: cannot reactivate saved physical-reference sheet")
            proof = (
                _assert_physical_head_height if name == "SupplierHeadHeight"
                else _assert_physical_stock_length
            )
            measured = proof(adapter, front, display, phase="saved")
            assert_supplier_reference_dimension(
                adapter, display, label=name, **SUPPLIER_REFERENCE_DIMENSIONS[name],
            )
            _assert_supplier_tolerance(display, name)
            actual_circles = tuple(
                tuple(float(value) for value in _early_bound(
                    _early_bound(edge, "IEdge").GetCurve(), "ICurve"
                ).CircleParams)
                for edge in annotation.GetAttachedEntities3()
            )
            common = dict(
                phase="after_saved_reopen", full_name=full_name,
                original_full_name=original_full_name,
                attached_circle_params_m=actual_circles, owner=owner,
                configuration=str(front.ReferencedConfiguration),
            )
            if name == "SupplierHeadHeight":
                _telemetry.event(
                    "drawing.pivot_head_height_proof", measured_head_height_mm=measured,
                    physical_points_m=_head_height_points(), **common,
                )
            else:
                _telemetry.event(
                    "drawing.pivot_stock_length_proof", measured_stock_thread_length_mm=measured,
                    **common,
                )
    finally:
        try:
            reopened = app.GetOpenDocumentByName(path_string)
            if reopened is not None:
                reopened = _early_bound(reopened, "IModelDoc2")
                if (
                    Path(str(reopened.GetPathName())).resolve() != path
                    or int(reopened.GetType()) != 3
                ):
                    raise RuntimeError("SupplierHeadHeight: refuse to close a different document")
                title = str(reopened.GetTitle() or "")
                if not title:
                    raise RuntimeError("SupplierHeadHeight: reopened drawing has no title")
                app.CloseDoc(title)
                if app.GetOpenDocumentByName(path_string) is not None:
                    raise RuntimeError("SupplierHeadHeight: reopened saved drawing did not close")
        finally:
            adapter.currentModel = previous


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open faced pivot screw", await adapter.open_model(str(SOURCE)))
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
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="finished and original pivot-screw stock")
    if not _early_bound(draw, "IDrawingDoc").ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("cannot activate finished pivot-screw sheet")
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: "Transgear Pivot Screw — Modified Stock Drawing",
            1: "Faced tip, end chamfer and modified-part thread-tail acceptance",
            2: "Harmonic Analyzer Project",
            3: f"MHA-PD-VN-57; McMaster-Carr {SKU}",
            4: "Native reference length, chamfer and thread-tail controls",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=SHEET_SCALE)
    # Force drawing-quality cosmetic threads on the finished projections.
    for view in (front, iso, top):
        set_hidden_lines_removed(adapter, view)
    # The consumed deburr sketch, the trim sketch and the hidden thread-tail
    # acceptance sketch all lie on the Front plane, so the main view carries
    # every control.
    annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="fitted reference length, faced-tip chamfer and thread tail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    by_name = {dimension_name(adapter, item): item for item in annotations}
    if set(by_name) != {"CutLength", *EXPECTED_CONTROLS}:
        raise RuntimeError(f"Front view controls are {sorted(by_name)}")
    verify_machining_controls(
        adapter,
        [by_name[name] for name in EXPECTED_CONTROLS],
        expected=EXPECTED_CONTROLS,
        tolerance_types=DIMENSION_TOLERANCE_TYPES,
        precision=DIMENSION_PRECISION,
    )
    _verify_reference_length(adapter, by_name["CutLength"])
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
    offset_dimension_text(
        adapter,
        annotations,
        {"ChamferWidth": CHAMFER_TEXT_XY, "CutLength": CUT_LENGTH_TEXT_XY},
    )
    supplier_refs = _add_supplier_references(adapter, front, top)
    head_edge = model_point_in_view(
        adapter,
        front,
        tuple(value / 1000 for value in HEAD_PICK_MM),
        label="purchased socket head top edge",
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
    supplier_refs["SupplierStockThreadLength"] = stock_annotation
    identities = _supplier_reference_identities(adapter, supplier_refs)
    configurations = {
        view_name(adapter, view): (sheet, str(_early_bound(view, "IView").ReferencedConfiguration))
        for sheet, views in ((SHEET_NAMES[0], (front, iso, top)), (SHEET_NAMES[1], (stock, stock_iso)))
        for view in views
    }
    if properties["Supplier Reference Title"].replace("\r", "") != SUPPLIER_STOCK_TITLE:
        raise RuntimeError("source-stock title does not identify the original screw")
    physical_labels = ("SupplierHeadHeight", "SupplierStockThreadLength")
    serialized_full_names: dict[str, str] = {}
    capture_called = False

    def checkpoint(stage: str) -> None:
        nonlocal capture_called
        if stage != "before_drawing_close":
            return
        if capture_called:
            raise RuntimeError("physical references: serialized identity capture called more than once")
        capture_called = True
        captured = capture_serialized_physical_axial_names(
            adapter, {name: supplier_refs[name] for name in physical_labels}, identities,
            configurations, labels=physical_labels, drawing_path=OUTPUTS.slddrw,
            sheet_names=SHEET_NAMES,
        )
        if (
            set(captured) != set(physical_labels)
            or any(not isinstance(value, str) or not value for value in captured.values())
            or len(set(captured.values())) != 2
        ):
            raise RuntimeError(
                f"physical references: serialized identity capture is incomplete: {captured!r}"
            )
        serialized_full_names.update(captured)

    result = await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Pivot Screw — Modified Stock Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        settled_checks=(lambda: _assert_supplier_references(adapter, identities, configurations),),
        checkpoint=checkpoint,
    )
    if not capture_called:
        raise RuntimeError("physical references: before_drawing_close identity checkpoint was never called")
    _assert_saved_physical_references(
        adapter, identities, configurations, serialized_full_names=serialized_full_names,
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
