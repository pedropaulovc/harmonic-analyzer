"""Create MHA-PD-VN-57's drawing with creation/settled/saved physical axial proofs.

Keep original identities for settled checks. Capture the actual serialized
FullNames from those same annotations only after successful saves/audit, at
``before_drawing_close``; cold reopening must find those exact names before
running the independent saved physical and presentation proofs.

The finished sheet aligns actual projected origins without rotating the part.
Its two forced text shelves preserve native physical stations; the purchased
note names the exact trimmed head-top rim. Finite native centre-mark ink and
fresh complete-text/foreign-line checks remain required after final rebuilds.
These local readbacks do not replace coordinator PDF and machinist qualification.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, NoReturn

from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name, place_view, set_view_position, view_name,
)

from _machinist_review_mode import MachinistReviewMode
import _telemetry
from _check import check
from _com import _early_bound
from _drawing_attachment import _is_same_attachment
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimensions import offset_dimension_text, set_dimension_callouts
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_edges import scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_layout_audit import _Reader, _dump_annotation
from _drawing_serialized_note_identity import capture_serialized_note_name
from _drawing_leader_notes import add_attached_note
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
from _layout_audit import (
    _segment_crossing, _segment_enters_box, annotation_geometry, calibrate_sheet_advance, display_box,
)
from _layout_geometry import Box, Segment, segment_box_distance
from _part_properties import part_drawing_unit
from _session import run_build
from _stock_trim_drawing import verify_machining_controls
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_reference_text import (
    measure_reference_text,
    shelve_reference_text,
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
    SHOULDER_LEN,
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

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

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
# Machinist review (clarity, r1-r3): at 16 mm out the angle's arc and its
# extension line along the chamfer rose ~12 mm above the tip and crossed the
# thread major's dimension line.  At 10 mm out they end ~8 mm above the tip,
# under that line, and the 45 deg text stays clear of the thread.
_ANGLE_TEXT_RADIUS = 0.010
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
# The native straight leader departs down-left from the actual sheet-left
# upper trimmed rim. Native automatic wrapping fits the measured left field.
_HEAD_TOP_R = HEAD_DIA / 2 - HEAD_CHAMFER
PURCHASED_NOTE_XY = (0.025, 0.198)  # Creation only; measured placement follows.
# Every view and the sheet are 4:1, so the title-block SCALE is the view
# scale and the isometric carries no scale label.
ISO_CENTER = (0.360, 0.165)
STOCK_CENTER = (0.180, 0.155)
STOCK_ISO_CENTER = (0.325, 0.165)
TOP_CENTER = (0.295, 0.245)
_REFERENCE_SHELF_AXES = {"SupplierHeadHeight": 1, "SupplierSocketAF": 0}
_PAPER_GAP_M = 0.002
_MARK_ARM_M = 0.003
# Machinist review (clarity, r1-r3): 2 mm past the thread major's shelf, the
# tail text's leader met its (outside-arrowed, so undrawn) dimension line
# right beside that shelf's end and read as the major's.  The column stands
# 8 mm clear and its arrows stand inside, so the leader lands on a drawn line
# and no outside arrow tail strikes the text's shelf.
_TAIL_COLUMN_GAP_M = 0.008
_DIM_ARROWS_INSIDE = 0  # swDimensionArrowsSide_e.swDimArrowsInside
# Machinist review r2 (minor, all runs): the shoulder's two supplier
# reference lines printed as a grey dash-dot across mid-shoulder and dashes
# over its flank.  They now lie on outline edges (the head's bearing face and
# the shoulder's flank, SUPPLIER_REFERENCE_STARTS) and draw in the outline's
# black, so they ARE those edges (draw_dt_pinion_arbor's recipe).
_REFERENCE_WITNESS_COLOR = 0  # COLORREF black, the outline's colour.
_SW_SEL_EXT_SKETCH_SEGS = 24  # swSelectType_e.swSelEXTSKETCHSEGS
_SHOULDER_WITNESS_LENGTHS = {
    "SupplierShoulderDiameter": SHOULDER_DIA,
    "SupplierShoulderLength": SHOULDER_LEN,
}
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
            (TOP_CENTER[0], TOP_CENTER[1] - 0.010), "horizontal", "EDGE",
        ),
    ):
        picks = model_points_in_view(
            adapter, view,
            [tuple(value / 1000 for value in point) for point in (first, second)],
            label=name,
        )
        if name == "SupplierSocketAF":
            text_xy = (sum(point[0] for point in picks) / 2, text_xy[1])
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


def _blacken_shoulder_witnesses(adapter: Any, front: Any) -> None:
    """Draw the shoulder's two supplier reference lines in the outline's black.

    Each is the SupplierReference sketch's one construction segment of its
    size's length, mapped into Front (the model entity, never a point pick);
    both lie on outline edges, so in black they print as those edges.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    native = _early_bound(front, "IView")
    if not drawing.ActivateView(view_name(adapter, front)):
        raise RuntimeError("cannot activate Front for the shoulder reference lines")
    model = native.ReferencedDocument
    feature = None if model is None else _early_bound(model, "IPartDoc").FeatureByName("SupplierReference")
    if feature is None:
        raise RuntimeError("Front's model has no SupplierReference sketch")
    sketch = _early_bound(_early_bound(feature, "IFeature").GetSpecificFeature2(), "ISketch")
    segments = [_early_bound(raw, "ISketchSegment") for raw in sketch.GetSketchSegments() or ()]
    selection = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for name, length_mm in _SHOULDER_WITNESS_LENGTHS.items():
        matches = [
            segment for segment in segments
            if bool(segment.ConstructionGeometry)
            and abs(float(segment.GetLength()) * 1000.0 - length_mm) <= 0.01
        ]
        if len(matches) != 1:
            raise RuntimeError(f"{name}: {len(matches)} construction segments match its length")
        in_view = native.GetCorresponding(matches[0])
        if in_view is None:
            raise RuntimeError(f"{name}: the reference line has no instance in Front")
        draw.ClearSelection2(True)
        data = selection.CreateSelectData()
        data.View = front
        if not _early_bound(in_view, "ISketchSegment").Select4(False, data):
            raise RuntimeError(f"{name}: cannot select the reference line in Front")
        if int(selection.GetSelectedObjectType3(1, -1)) != _SW_SEL_EXT_SKETCH_SEGS:
            raise RuntimeError(f"{name}: the reference line pick resolved to another entity")
        drawing.SetLineColor(_REFERENCE_WITNESS_COLOR)
    draw.ClearSelection2(True)
    draw.EditRebuild3()



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


def _assert_supplier_references(adapter: Any, identities: dict, configurations: dict) -> dict[str, Any]:
    """Fresh post-rebuild value/precision/band/identity/count/configuration checks."""
    if set(identities) != set(SUPPLIER_REFERENCE_DIMENSIONS):
        raise RuntimeError("supplier reference coverage is incomplete")
    required = {record[0]: name for name, record in identities.items()}
    counts = {name: 0 for name in identities}
    displays = {}
    found_views = set()
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    # Complete the census on FINISHED: native text must not be read from an
    # inactive finished sheet after the source-stock visit.
    for sheet_name in reversed(SHEET_NAMES):
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
                displays[name] = display
            view = view.GetNextView()
    if found_views != set(configurations) or any(count != 1 for count in counts.values()):
        raise RuntimeError(f"settled supplier view/dimension census changed: {counts}")
    return displays


@_telemetry.traced("drawing.pivot_physical_references_saved")
def _assert_saved_physical_references(
    adapter: Any, identities: dict, configurations: dict, *,
    serialized_full_names: dict[str, str],
    serialized_shelf_names: dict[str, str],
    paper: dict[str, Any],
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
    if (
        set(serialized_shelf_names) != set(_REFERENCE_SHELF_AXES)
        or any(not isinstance(value, str) or not value for value in serialized_shelf_names.values())
        or len(set(serialized_shelf_names.values())) != 2
    ):
        raise RuntimeError("reference shelves: missing, extra, empty or duplicate serialized FullNames")
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
        shelf_required = {full_name: name for name, full_name in serialized_shelf_names.items()}
        shelf_matches = {name: [] for name in _REFERENCE_SHELF_AXES}
        saved_views = {}
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
                    if not is_sheet_view:
                        saved_views.setdefault(record["view"], []).append((sheet_name, view))
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
                        shelf_name = shelf_required.get(full_name)
                        if shelf_name is not None:
                            shelf_matches[shelf_name].append((sheet_name, view, display))
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
            if name == "SupplierHeadHeight":
                # Fresh saved display only; no live shelf closure crosses close.
                _assert_text_shelf(adapter, display, axis=1, label=name)
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
        if any(len(found) != 1 for found in shelf_matches.values()):
            raise RuntimeError("reference shelves: saved exact FullName census changed")
        if serialized_shelf_names["SupplierHeadHeight"] != serialized_full_names["SupplierHeadHeight"]:
            raise RuntimeError("reference shelves: saved physical head identity disagrees")
        if set(saved_views) != set(configurations) or any(len(found) != 1 for found in saved_views.values()):
            raise RuntimeError("saved paper: actual view census changed")
        fresh_views = {}
        for owner, found in saved_views.items():
            sheet_name, view = found[0]
            if (sheet_name, str(view.ReferencedConfiguration)) != configurations[owner]:
                raise RuntimeError("saved paper: native view configuration changed")
            source = view.ReferencedDocument
            source_path = "" if source is None else str(_early_bound(source, "IModelDoc2").GetPathName() or "")
            if not source_path or not Path(source_path).is_absolute() or Path(source_path).resolve() != SOURCE.resolve():
                raise RuntimeError("saved paper: native source document changed")
            fresh_views[owner] = view
        if not drawing.ActivateSheet(SHEET_NAMES[0]):
            raise RuntimeError("saved paper: cannot activate finished sheet")
        for name, axis in _REFERENCE_SHELF_AXES.items():
            sheet_name, view, display = shelf_matches[name][0]
            annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
            if (
                sheet_name != SHEET_NAMES[0] or view_name(adapter, view) != identities[name][1]
                or int(annotation.OwnerType) != 0 or int(app.IsSame(annotation.Owner, view)) != 1
                or bool(annotation.IsDangling())
            ):
                raise RuntimeError(f"{name}: saved shelf owner/attachment changed")
            assert_supplier_reference_dimension(
                adapter, display, label=name, **SUPPLIER_REFERENCE_DIMENSIONS[name],
            )
            _assert_supplier_tolerance(display, name)
            _assert_text_shelf(adapter, display, axis=axis, label=name)
        top = fresh_views[identities["SupplierSocketAF"][1]]
        front = fresh_views[identities["SupplierHeadHeight"][1]]
        pictorials = [
            view for owner, view in fresh_views.items()
            if configurations[owner][0] == SHEET_NAMES[0]
            and owner not in (identities["SupplierSocketAF"][1], identities["SupplierHeadHeight"][1])
        ]
        if len(pictorials) != 1:
            raise RuntimeError("saved paper: finished pictorial census changed")
        _assert_socket_source(adapter, top, shelf_matches["SupplierSocketAF"][0][2])
        _assert_top_origin(adapter, front, top, pictorials[0])
        _assert_top_mark(adapter, top)
        _assert_saved_paper(
            adapter, front, top, pictorials[0], shelf_matches=shelf_matches, paper=paper,
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

def _assert_saved_paper(adapter: Any, front: Any, top: Any, iso: Any, *, shelf_matches: dict, paper: dict) -> None:
    """Fresh cold native paper proof using only exact serialized IDs and scalars."""
    labels = {"SupplierHeadDiameter", "SupplierThreadMajor", "ThreadLengthMin"}
    names = paper["names"]
    if set(names) != labels or len(set(names.values())) != len(labels) or any(
        not isinstance(value, str) or not value for value in names.values()
    ) or not isinstance(paper["note"], str) or not paper["note"]:
        raise RuntimeError("saved paper: incomplete exact serialized identity")
    found = {name: [] for name in labels}
    for raw in front.GetDisplayDimensions() or ():
        display = _early_bound(raw, "IDisplayDimension")
        full_name = _early_bound(display.GetDimension2(0), "IDimension").FullName
        for name, expected in names.items():
            if full_name == expected:
                found[name].append(display)
    if any(len(matches) != 1 for matches in found.values()):
        raise RuntimeError("saved paper: exact serialized dimension census changed")
    fresh = {name: matches[0] for name, matches in found.items()}
    for name, display in fresh.items():
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        if int(annotation.OwnerType) != 0 or int(adapter.swApp.IsSame(annotation.Owner, front)) != 1 or annotation.IsDangling():
            raise RuntimeError(f"{name}: saved paper native owner/attachment changed")
        if name != "ThreadLengthMin":
            assert_supplier_reference_dimension(adapter, display, label=name, **SUPPLIER_REFERENCE_DIMENSIONS[name])
            _assert_supplier_tolerance(display, name)
    model = _early_bound(adapter.currentModel, "IDrawingDoc")
    notes = []
    for sheet_name in SHEET_NAMES:
        if not model.ActivateSheet(sheet_name):
            raise RuntimeError("saved paper: cannot activate native note census sheet")
        view = model.GetFirstView()
        while view is not None:
            view = _early_bound(view, "IView")
            for raw in view.GetAnnotations() or ():
                annotation = _early_bound(raw, "IAnnotation")
                if int(annotation.GetType()) == 6 and annotation.GetName() == paper["note"]:
                    notes.append((sheet_name, view, annotation))
            view = view.GetNextView()
    if not model.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("saved paper: cannot activate finished sheet for native text reads")
    if len(notes) != 1:
        raise RuntimeError("saved paper: exact serialized purchased note census changed")
    sheet_name, owner, annotation = notes[0]
    if (
        sheet_name != SHEET_NAMES[0] or int(adapter.swApp.IsSame(owner, front)) != 1
        or int(annotation.OwnerType) != 0 or int(adapter.swApp.IsSame(annotation.Owner, front)) != 1
    ):
        raise RuntimeError("saved paper: exact purchased note owner changed")
    note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
    landing = _purchased_head_target(adapter, front)[1]
    _assert_note_wrap(adapter, note, landing=landing, frame=paper["wrap"])
    tail = fresh["ThreadLengthMin"].GetAnnotation()
    verify_machining_controls(
        [tail], expected={"ThreadLengthMin": EXPECTED_CONTROLS["ThreadLengthMin"]},
        tolerance_types=DIMENSION_TOLERANCE_TYPES, precision=DIMENSION_PRECISION,
    )
    _assert_tail_layout(adapter, tail, fresh["SupplierThreadMajor"].GetAnnotation(), frame=paper["tail"])
    _assert_paper_layout(
        adapter, front, top, iso, note,
        {**fresh, **{name: matches[0][2] for name, matches in shelf_matches.items()}},
        purchased_text=paper["text"],
    )



def _paper_annotation(adapter: Any, annotation: Any, *, label: str) -> dict[str, Any]:
    """Complete native fragments and strokes, never INote's leader-inclusive extent."""
    reader = _Reader(adapter)
    record = _dump_annotation(reader, annotation)
    errors = reader.take_errors()
    if record is None or errors:
        raise RuntimeError(f"{label}: unreadable native paper geometry: {errors}")
    for row in (record.get("display") or {}).get("texts") or ():
        if (
            len(row.get("pos") or ()) != 3
            or not all(math.isfinite(float(value)) for value in row["pos"])
            or any(
                row.get(key) is None or not math.isfinite(float(row[key]))
                or float(row[key]) <= 0
                for key in ("w", "h")
            )
            or row.get("ang") is None or not math.isfinite(float(row["ang"]))
        ):
            raise RuntimeError(f"{label}: incomplete native text fragment")
    geometry = annotation_geometry(record, owner=label, advance=calibrate_sheet_advance((record,)))
    if geometry is None or any(
        not all(math.isfinite(value) for value in (run.x0, run.y0, run.x1, run.y1))
        for run in geometry.segments
    ):
        raise RuntimeError(f"{label}: non-finite or absent native paper geometry")
    return record


def _finished_border(adapter: Any) -> Box:
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    properties = tuple(float(value) for value in sheet.GetProperties2())
    margins = tuple(float(sheet.GetZoneMargin(index)) for index in range(4))
    if (
        len(properties) != 8 or not all(map(math.isfinite, (*properties, *margins)))
        or properties[4] != 0 or any(value < 0 for value in margins)
    ):
        raise RuntimeError("finished sheet: invalid native third-angle border")
    top, bottom, right, left = margins  # swZoneMargin_e
    border = Box(left, bottom, properties[5] - right, properties[6] - top)
    if border.width <= 0 or border.height <= 0:
        raise RuntimeError("finished sheet: empty native inner border")
    return border


def _align_top_origin(adapter: Any, front: Any, top: Any, iso: Any) -> Any:
    """Translate only Top.X by the measured model-origin projection difference."""
    views = tuple(_early_bound(view, "IView") for view in (front, top, iso))
    before = []
    for view in views:
        state = (tuple(float(value) for value in view.Position),
                 float(view.ScaleDecimal), float(view.Angle))
        if len(state[0]) != 2 or not all(map(math.isfinite, (*state[0], *state[1:]))):
            raise RuntimeError("Top alignment: unreadable native view placement")
        before.append(state)
    front_origin = model_point_in_view(adapter, front, (0.0, 0.0, 0.0), label="Front model origin")
    top_origin = model_point_in_view(adapter, top, (0.0, 0.0, 0.0), label="Top model origin")
    target = (before[1][0][0] + front_origin[0] - top_origin[0], before[1][0][1])
    if not set_view_position(adapter, top, *target, move_children=False):
        raise RuntimeError("Top alignment: native view translation failed")
    rebuild_drawing(adapter, label="align pivot Top model origin")

    def settled() -> None:
        for index, view in enumerate(views):
            position, scale, angle = before[index]
            expected = target if index == 1 else position
            actual = tuple(float(value) for value in view.Position)
            if (
                len(actual) != 2 or not all(map(math.isfinite, actual))
                or math.dist(actual, expected) > 1e-8
                or not math.isclose(float(view.ScaleDecimal), scale, abs_tol=1e-12, rel_tol=0)
                or not math.isclose(float(view.Angle), angle, abs_tol=1e-12, rel_tol=0)
            ):
                raise RuntimeError("Top alignment: native position, scale or rotation drift")
        _assert_top_origin(adapter, front, top, iso)

    settled()
    return settled


def _trim_top_mark(adapter: Any, top: Any) -> Any:
    """Keep the real native mark, with finite measured ink on the projected axis."""
    top = _early_bound(top, "IView")
    marks = tuple(top.GetAnnotationsByType(13) or ())  # swCenterMark
    scale = float(top.ScaleDecimal)
    if len(marks) != 1 or not math.isfinite(scale) or scale <= 0:
        raise RuntimeError("Top centre mark: expected one native mark and positive actual scale")
    mark = _early_bound(_early_bound(marks[0], "IAnnotation").GetSpecificAnnotation(), "ICenterMark")
    mark.UseDocDisplaySettings = False
    mark.ShowLines = False
    mark.Size = _MARK_ARM_M / scale
    rebuild_drawing(adapter, label="finite pivot Top centre mark")

    _assert_top_mark(adapter, top)
    return lambda: _assert_top_mark(adapter, top)


def _assert_top_origin(adapter: Any, front: Any, top: Any, iso: Any) -> None:
    """Read-only origin/axis/outline proof, usable with fresh cold-saved views."""
    origins = []
    for view in (front, top):
        origin, x_axis = model_points_in_view(
            adapter, view, ((0.0, 0.0, 0.0), (0.001, 0.0, 0.0)), label="native projection axis",
        )
        if (
            not all(math.isfinite(value) for point in (origin, x_axis) for value in point)
            or abs(x_axis[0] - origin[0] - 0.004) > 1e-8
            or abs(x_axis[1] - origin[1]) > 1e-8
        ):
            raise RuntimeError("Top alignment: actual model X axis is not horizontal at native scale")
        origins.append(origin)
    if abs(origins[0][0] - origins[1][0]) > 1e-8 or origins[1][1] <= origins[0][1]:
        raise RuntimeError("Top alignment: projected model origins are not third-angle aligned")
    z_axis = model_point_in_view(adapter, top, (0.0, 0.0, 0.001), label="native Top Z axis")
    if (
        not all(map(math.isfinite, z_axis)) or abs(z_axis[0] - origins[1][0]) > 1e-8
        or abs(z_axis[1] - origins[1][1] + 0.004) > 1e-8
    ):
        raise RuntimeError("Top alignment: actual Top model Z axis changed")
    border = _finished_border(adapter)
    for view in (front, top, iso):
        view = _early_bound(view, "IView")
        box = Box(*(float(value) for value in view.GetOutline()))
        if (
            not all(map(math.isfinite, (box.xmin, box.ymin, box.xmax, box.ymax)))
            or box.width <= 0 or box.height <= 0
            or not math.isclose(float(view.ScaleDecimal), 4.0, abs_tol=1e-12, rel_tol=0)
            or not math.isclose(float(view.Angle), 0.0, abs_tol=1e-12, rel_tol=0)
            or box.xmin < border.xmin or box.xmax > border.xmax
            or box.ymin < border.ymin or box.ymax > border.ymax
        ):
            raise RuntimeError("Top alignment: actual view outline/scale/rotation changed")


def _assert_top_mark(adapter: Any, top: Any) -> None:
    top = _early_bound(top, "IView")
    current = tuple(top.GetAnnotationsByType(13) or ())
    scale = float(top.ScaleDecimal)
    if len(current) != 1 or not math.isfinite(scale) or scale <= 0:
        raise RuntimeError("Top centre mark: native mark census/scale changed")
    annotation = _early_bound(current[0], "IAnnotation")
    native = _early_bound(annotation.GetSpecificAnnotation(), "ICenterMark")
    if (
        bool(native.UseDocDisplaySettings) or bool(native.ShowLines)
        or not math.isclose(float(native.Size), _MARK_ARM_M / scale, rel_tol=0, abs_tol=1e-8)
        or int(annotation.Visible) != 1 or int(annotation.OwnerType) != 0
        or int(adapter.swApp.IsSame(annotation.Owner, top)) != 1
    ):
        raise RuntimeError("Top centre mark: finite native settings/owner did not persist")
    origin = model_point_in_view(adapter, top, (0.0, HEAD_H / 1000, 0.0), label="Top head axis")
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    lines = [
        tuple(float(value) for value in data.GetLineAtIndex2(index))
        for index in range(int(data.GetLineCount()))
    ]
    if not lines or any(
        len(line) != 10 or not all(map(math.isfinite, line)) for line in lines
    ) or not all(map(math.isfinite, origin)):
        raise RuntimeError("Top centre mark: unreadable finite native line endpoints")
    border = _finished_border(adapter)
    endpoints, axes = [], set()
    depth = lines[0][6]  # Native Top display depth need not be drawing-world zero.
    for line in lines:
        first, second = line[4:7], line[7:10]
        if abs(first[2] - depth) > 1e-8 or abs(second[2] - depth) > 1e-8:
            raise RuntimeError("Top centre mark: native line endpoints disagree on display depth")
        horizontal = abs(first[1] - origin[1]) <= 1e-8 and abs(second[1] - origin[1]) <= 1e-8
        vertical = abs(first[0] - origin[0]) <= 1e-8 and abs(second[0] - origin[0]) <= 1e-8
        if horizontal == vertical or math.dist(first, second) <= 1e-8:
            raise RuntimeError("Top centre mark: line is not on the actual projected axis")
        axes.add(0 if horizontal else 1)
        for x, y, _z in (first, second):
            if (
                not border.xmin <= x <= border.xmax or not border.ymin <= y <= border.ymax
                or max(abs(x - origin[0]), abs(y - origin[1])) > _MARK_ARM_M + 1e-5
            ):
                raise RuntimeError("Top centre mark: actual finite ink escapes border/arm")
            endpoints.append((x, y))
    bounds = Box.from_points(endpoints)
    if axes != {0, 1} or bounds is None or any(
        not math.isclose(actual, expected, abs_tol=1e-5, rel_tol=0)
        for actual, expected in zip(
            (bounds.xmin, bounds.ymin, bounds.xmax, bounds.ymax),
            (origin[0] - _MARK_ARM_M, origin[1] - _MARK_ARM_M,
             origin[0] + _MARK_ARM_M, origin[1] + _MARK_ARM_M), strict=True,
        )
    ):
        raise RuntimeError("Top centre mark: actual cross is not centred and finite")


def _assert_socket_source(adapter: Any, top: Any, display: Any) -> None:
    """Cold fresh exact native EDGE bijection at the two source socket stations."""
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    if (
        int(annotation.GetAttachedEntityCount3()) != 2 or len(attached) != 2
        or tuple(annotation.GetAttachedEntityTypes() or ()) != (1, 1)
        or bool(annotation.IsDangling()) or any(edge is None for edge in attached)
        or int(adapter.swApp.IsSame(attached[0], attached[1])) != 0
    ):
        raise RuntimeError("SupplierSocketAF: saved exact EDGE attachment pair changed")
    scan = scan_view_edges(top, label="saved physical socket flats")
    resolved = []
    for x in (-SOCKET_AF / 2, SOCKET_AF / 2):
        point = (x / 1000, HEAD_H / 1000, 0.0)
        matches = []
        for candidate in scan.edges:
            nearest = tuple(float(value) for value in (
                _early_bound(candidate.edge, "IEdge").GetClosestPointOn(point[0], point[1], point[2]) or ()
            )[:3])
            if len(nearest) == 3 and all(map(math.isfinite, nearest)) and math.dist(nearest, point) <= 1e-8:
                if not any(int(adapter.swApp.IsSame(candidate.edge, edge)) == 1 for edge in matches):
                    matches.append(candidate.edge)
        if len(matches) != 1:
            raise RuntimeError("SupplierSocketAF: saved exact trimmed socket station changed")
        resolved.append(matches[0])
    if int(adapter.swApp.IsSame(resolved[0], resolved[1])) != 0 or any(
        sum(int(adapter.swApp.IsSame(edge, actual)) == 1 for actual in attached) != 1
        for edge in resolved
    ):
        raise RuntimeError("SupplierSocketAF: saved physical EDGE attachment bijection changed")
    physical = measure_reference_text(adapter, display, axis=0, label="SupplierSocketAF")
    expected = sorted(model_points_in_view(
        adapter, top,
        [(x / 1000, HEAD_H / 1000, 0.0) for x in (-SOCKET_AF / 2, SOCKET_AF / 2)],
        label="actual socket width stations",
    ))
    if int(display.Type2) != 2 or any(
        abs(tip[0] - point[0]) > 1e-8 for tip, point in zip(physical["tips"], expected, strict=True)
    ) or abs(physical["tips"][1][0] - physical["tips"][0][0] - SOCKET_AF * _SHEET_PER_MODEL_MM) > 1e-8:
        raise RuntimeError("SupplierSocketAF: saved actual horizontal native span changed")
    outer = model_point_in_view(
        adapter, top, (HEAD_DIA / 2 / 1000, (HEAD_H - HEAD_CHAMFER) / 1000, 0.0),
        label="saved Top actual outer perimeter",
    )
    if not all(map(math.isfinite, outer)) or physical["text"].xmin < outer[0] + _PAPER_GAP_M:
        raise RuntimeError("SupplierSocketAF: saved complete native text crowds actual Top")


def _head_sheet_left_point(
    adapter: Any, front: Any,
) -> tuple[tuple[float, float, float], tuple[float, float]]:
    """Derive the circular rim's sheet-left extremum from the actual projection."""
    radius, y = _HEAD_TOP_R / 1000, HEAD_H / 1000
    samples = model_points_in_view(
        adapter, front,
        ((radius, y, 0.0), (-radius, y, 0.0), (0.0, y, radius), (0.0, y, -radius)),
        label="physical head-top projected radial axes",
    )
    if (
        len(samples) != 4 or any(len(point) != 2 for point in samples)
        or not all(math.isfinite(value) for point in samples for value in point)
    ):
        raise RuntimeError("Purchased Screw Note: unreadable actual head-top radial projection")
    x_axis = samples[0][0] - samples[1][0]
    z_axis = samples[2][0] - samples[3][0]
    span = math.hypot(x_axis, z_axis)
    center_x = (samples[0][0] + samples[1][0]) / 2
    if (
        span <= 1e-8
        or abs(center_x - (samples[2][0] + samples[3][0]) / 2) > 1e-8
        or max(point[1] for point in samples) - min(point[1] for point in samples) > 1e-8
    ):
        raise RuntimeError("Purchased Screw Note: actual head-top projection is not edge-on")
    point = (-radius * x_axis / span, y, -radius * z_axis / span)
    landing = model_point_in_view(adapter, front, point, label="purchased physical head-top rim")
    if (
        len(landing) != 2 or not all(map(math.isfinite, landing))
        or abs(landing[0] - (center_x - span / 2)) > 1e-8
        or abs(landing[1] - samples[0][1]) > 1e-8
    ):
        raise RuntimeError("Purchased Screw Note: actual sheet-left extremum projection changed")
    return point, landing


def _purchased_head_target(adapter: Any, front: Any) -> tuple[Any, tuple[float, float]]:
    """Prove the actual sheet-left landing on the exact existing head-top EDGE."""
    edge = _head_height_entities(adapter, front)[1]
    point, landing = _head_sheet_left_point(adapter, front)
    nearest = tuple(float(value) for value in (
        _early_bound(edge, "IEdge").GetClosestPointOn(point[0], point[1], point[2]) or ()
    )[:3])
    if len(nearest) != 3 or not all(map(math.isfinite, nearest)) or math.dist(nearest, point) > 1e-8:
        raise RuntimeError("Purchased Screw Note: head-top landing is not on the actual trimmed rim")
    return edge, landing


def _assert_text_shelf(adapter: Any, display: Any, *, axis: int, label: str) -> dict[str, Any]:
    actual = measure_reference_text(adapter, display, axis=axis, label=label)
    text = actual["text"]
    low = text.xmin if axis == 0 else text.ymin
    if _early_bound(display, "IDisplayDimension").OffsetText is not True or low < actual["reach"] + _PAPER_GAP_M:
        raise RuntimeError(f"{label}: complete native text crowds physical arrow reach")
    return actual


def _clear_socket_text(adapter: Any, top: Any, display: Any) -> None:
    """Keep the forced +X shelf wholly beside the actual source head perimeter."""
    before = _assert_text_shelf(adapter, display, axis=0, label="SupplierSocketAF")
    outer = model_point_in_view(
        adapter, top, (HEAD_DIA / 2 / 1000, (HEAD_H - HEAD_CHAMFER) / 1000, 0.0),
        label="Top source outer head right station",
    )
    if not all(map(math.isfinite, outer)):
        raise RuntimeError("SupplierSocketAF: non-finite actual source perimeter")
    target = outer[0] + _PAPER_GAP_M + 0.0002
    if before["text"].xmin < target:
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        position = tuple(float(value) for value in annotation.GetPosition())
        if len(position) != 3 or not all(map(math.isfinite, position)) or not annotation.SetPosition2(
            position[0] + target - before["text"].xmin, position[1], position[2],
        ):
            raise RuntimeError("SupplierSocketAF: cannot clear complete native text beside Top")
        rebuild_drawing(adapter, label="socket full fraction and qualifier clear actual Top")
    after = _assert_text_shelf(adapter, display, axis=0, label="SupplierSocketAF")
    if after["text"].xmin < outer[0] + _PAPER_GAP_M or any(
        math.dist(old, new) > 1e-8
        for key in ("tips", "witnesses")
        for old, new in zip(before[key], after[key], strict=True)
    ):
        raise RuntimeError("SupplierSocketAF: full native text/body clearance or physical stations changed")


def _tail_text_fragments(record: dict[str, Any]) -> tuple:
    """Measured ink of each acceptance fragment; a union can conceal row drift."""
    fragments = []
    for row in record["display"]["texts"]:
        box = display_box({"texts": (row,)})
        angle = float(row["ang"])
        if box is None or not all(map(math.isfinite, (
            angle, box.xmin, box.ymin, box.xmax, box.ymax,
        ))):
            raise RuntimeError("ThreadLengthMin: unreadable native acceptance fragment")
        fragments.append((str(row["t"]), angle, box.xmin, box.ymin, box.xmax, box.ymax))
    return tuple(sorted(fragments))


def _tail_measurement_snapshot(adapter: Any, tail: Any, display: Any, geometry: dict | None) -> dict:
    """Last measured ink plus current metadata, without masking native getter errors."""
    snapshot: dict[str, Any] = {
        "measurement_available": geometry is not None,
        "ink_measurement": "last_successful_read" if geometry is not None else "unavailable",
    }
    for key, getter in (
        ("full_name", lambda: str(_early_bound(display.GetDimension2(0), "IDimension").FullName)[:512]),
        ("owner", lambda: view_name(adapter, tail.Owner)),
        ("owner_type", lambda: int(tail.OwnerType)),
        ("offset_text", lambda: bool(display.OffsetText)),
        ("annotation_position", lambda: tuple(float(value) for value in tail.GetPosition())[:3]),
    ):
        try:
            snapshot[key] = getter()
        except Exception as error:
            snapshot.setdefault("metadata_errors", []).append({
                "field": key, "type": type(error).__name__, "error": str(error)[:500],
            })
    if geometry is not None:
        rows = geometry["record"]["display"]["texts"]
        snapshot.update(
            arrow_stations=geometry["tips"], witnesses=geometry["witnesses"],
            text_fragment_count=len(rows),
            text_fragments=[
                dict(text=str(row["t"])[:256], position=tuple(row["pos"][:3]),
                     width=row["w"], height=row["h"], angle=row["ang"])
                for row in rows[:12]
            ],
            text_fragments_truncated=len(rows) > 12,
        )
    return snapshot


def _tail_layout_refusal(
    adapter: Any, tail: Any, display: Any, *, frame: dict,
    current: dict | None, phase: str, error: Exception,
) -> NoReturn:
    reason = str(error)[:1000]
    snapshot = dict(
        phase=phase, failure_error_type=type(error).__name__, failure_error=reason,
        original=frame.get("original", {"measurement_available": False}),
        current=_tail_measurement_snapshot(adapter, tail, display, current),
        column=frame.get("column"), measured_translation=frame.get("offset_translation"),
    )
    _telemetry.event("drawing.pivot_tail_layout_refusal", **snapshot)
    prefix = "" if reason.startswith("ThreadLengthMin:") else "ThreadLengthMin: "
    raise RuntimeError(f"{prefix}{reason}; native_snapshot={snapshot!r}") from error


def _move_tail_column(adapter: Any, tail: Any, major: Any) -> Any:
    """Move the column, then restore actual native ink by one text-only translation."""
    tail = _early_bound(tail, "IAnnotation")
    display = _early_bound(tail.GetSpecificAnnotation(), "IDisplayDimension")
    frame: dict[str, Any] = {}
    current = None
    phase = "arrows_inside"
    try:
        display.ArrowSide = _DIM_ARROWS_INSIDE
        if int(display.ArrowSide) != _DIM_ARROWS_INSIDE:
            raise RuntimeError("ThreadLengthMin: arrows did not move inside its extension lines")
        phase = "measure_original"
        rebuild_drawing(adapter, label="measure pivot tail and thread-major ink")
        before = measure_reference_text(adapter, display, axis=1, label="ThreadLengthMin")
        current = before
        frame["original"] = _tail_measurement_snapshot(adapter, tail, display, before)
        original = tuple(float(value) for value in tail.GetPosition())
        major_record = _paper_annotation(adapter, major, label="SupplierThreadMajor")
        reach = display_box(major_record["display"])
        if (
            reach is None or not math.isfinite(reach.xmax)
            or len(original) != 3 or not all(map(math.isfinite, original))
            or display.OffsetText is not False
        ):
            raise RuntimeError("ThreadLengthMin: unavailable native column/major bounds")
        column = reach.xmax + _TAIL_COLUMN_GAP_M + 0.0002
        frame.update(
            tips=before["tips"], text=before["text"], column=column,
            words=tuple(sorted(str(row["t"]) for row in before["record"]["display"]["texts"])),
            fragments=_tail_text_fragments(before["record"]),
        )
        phase = "move_column"
        if not tail.SetPosition2(column, original[1], original[2]):
            raise RuntimeError("ThreadLengthMin: cannot move physical column")
        rebuild_drawing(adapter, label="pivot tail measured column")
        phase = "enable_native_offset"
        # With OffsetText=False GetPosition is the DIMENSION-LINE anchor, not
        # the text origin. This seeds offset mode; its actual ink must be read.
        offset_dimension_text(adapter, (tail,), {"ThreadLengthMin": original[:2]})
        phase = "measure_offset_text"
        current = None
        current = measure_reference_text(adapter, display, axis=1, label="ThreadLengthMin")
        if display.OffsetText is not True or any(
            abs(old[1] - new[1]) > 1e-8 or abs(new[0] - column) > 1e-8
            for old, new in zip(frame["tips"], current["tips"], strict=True)
        ):
            raise RuntimeError("ThreadLengthMin: native physical stations/column changed")
        fragments = _tail_text_fragments(current["record"])
        dx = current["text"].xmin - before["text"].xmin
        dy = current["text"].ymin - before["text"].ymin
        frame["offset_translation"] = (dx, dy)
        # Congruence is tighter than the existing 0.2 mm placement tolerance.
        # Native annotation dumps round coordinates to 0.1 um; allow 1 um for
        # that readback, never a changed word, angle, size or independent row.
        if len(fragments) != len(frame["fragments"]) or any(
            old[0] != new[0] or abs(old[1] - new[1]) > 1e-8
            or any(
                abs(new_value - old_value - shift) > 1e-6
                for old_value, new_value, shift in zip(old[2:], new[2:], (dx, dy, dx, dy), strict=True)
            )
            for old, new in zip(frame["fragments"], fragments, strict=True)
        ):
            raise RuntimeError("ThreadLengthMin: offset ink is not one congruent native text translation")
        if dx != 0.0 or dy != 0.0:
            phase = "restore_measured_text"
            position = tuple(float(value) for value in tail.GetPosition())
            if (
                len(position) != 3 or not all(map(math.isfinite, position))
                or display.OffsetText is not True
                or not tail.SetPosition2(position[0] - dx, position[1] - dy, position[2])
            ):
                raise RuntimeError("ThreadLengthMin: cannot restore measured acceptance ink")
            rebuild_drawing(adapter, label="restore measured pivot tail acceptance ink")
    except Exception as error:
        _tail_layout_refusal(adapter, tail, display, frame=frame, current=current, phase=phase, error=error)

    def settled() -> None:
        _assert_tail_layout(adapter, tail, major, frame=frame)
    settled()
    return settled, frame


def _assert_tail_layout(adapter: Any, tail: Any, major: Any, *, frame: dict[str, Any]) -> None:
    """Read-only replay over fresh native annotations and scalar pre-move stations."""
    tail = _early_bound(tail, "IAnnotation")
    display = _early_bound(tail.GetSpecificAnnotation(), "IDisplayDimension")
    actual = None
    try:
        actual = measure_reference_text(adapter, display, axis=1, label="ThreadLengthMin")
        column = frame["column"]
        if display.OffsetText is not True or int(display.ArrowSide) != _DIM_ARROWS_INSIDE or any(
            abs(old[1] - new[1]) > 1e-8 or abs(new[0] - column) > 1e-8
            for old, new in zip(frame["tips"], actual["tips"], strict=True)
        ):
            raise RuntimeError("ThreadLengthMin: native physical stations/column/arrows changed")
        if max(
            abs(getattr(frame["text"], key) - getattr(actual["text"], key))
            for key in ("xmin", "ymin", "xmax", "ymax")
        ) > 0.0002:
            raise RuntimeError("ThreadLengthMin: complete acceptance text moved")
        if tuple(sorted(str(row["t"]) for row in actual["record"]["display"]["texts"])) != frame["words"]:
            raise RuntimeError("ThreadLengthMin: complete native acceptance wording changed")
        fragments = _tail_text_fragments(actual["record"])
        if len(fragments) != len(frame["fragments"]) or any(
            old[0] != new[0] or abs(old[1] - new[1]) > 1e-8
            or max(abs(a - b) for a, b in zip(old[2:], new[2:], strict=True)) > 0.0002
            for old, new in zip(frame["fragments"], fragments, strict=True)
        ):
            raise RuntimeError("ThreadLengthMin: native acceptance fragment placement/format changed")
        current_major = _paper_annotation(adapter, major, label="SupplierThreadMajor")
        full = display_box(current_major["display"])
        if full is None or column < full.xmax + _TAIL_COLUMN_GAP_M:
            raise RuntimeError("ThreadLengthMin: physical column crowds complete thread-major ink")
        major_ink = annotation_geometry(
            current_major, owner="SupplierThreadMajor", advance=calibrate_sheet_advance((current_major,)),
        )
        tail_ink = annotation_geometry(
            actual["record"], owner="ThreadLengthMin", advance=calibrate_sheet_advance((actual["record"],)),
        )
        if any(
            _segment_crossing(first, second) is not None
            for first in major_ink.segments for second in tail_ink.segments
        ) or any(
            segment_box_distance(run, display_box({"texts": current_major["display"]["texts"]})) <= 1e-8
            for run in tail_ink.segments
        ):
            raise RuntimeError("ThreadLengthMin: native ink crosses thread-major line/text")
    except Exception as error:
        _tail_layout_refusal(adapter, tail, display, frame=frame, current=actual, phase="settled", error=error)


def _note_font(annotation: Any) -> tuple[Any, tuple]:
    """Keep the existing native font; LineLength alone is the wrapping control."""
    if int(annotation.GetTextFormatCount()) != 1:
        raise RuntimeError("Purchased Screw Note: expected one simple native text format")
    native = _early_bound(annotation.GetTextFormat(0), "ITextFormat")
    metrics = (
        str(native.TypeFaceName), float(native.CharHeight), float(native.WidthFactor),
        float(native.CharSpacingFactor), float(native.LineSpacing),
        bool(native.Bold), bool(native.Italic), bool(native.Underline),
        bool(native.Strikeout), bool(native.BackWards), bool(native.UpsideDown), bool(native.Vertical),
    )
    if not metrics[0] or not all(map(math.isfinite, metrics[1:5])) or any(value <= 0 for value in metrics[1:4]):
        raise RuntimeError("Purchased Screw Note: unreadable native font metrics")
    return native, metrics


def _place_purchased_note(
    adapter: Any, front: Any, note: Any, displays: dict[str, Any],
) -> Any:
    """One left-field native wrap/straight route, never a runtime layout search."""
    _edge, landing = _purchased_head_target(adapter, front)
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    shoulder = _paper_annotation(
        adapter, displays["SupplierShoulderLength"].GetAnnotation(), label="SupplierShoulderLength",
    )
    shoulder_geometry = annotation_geometry(
        shoulder, owner="SupplierShoulderLength", advance=calibrate_sheet_advance((shoulder,)),
    )
    shoulder_ink = shoulder_geometry.box() if shoulder_geometry is not None else None
    front_box = Box(*(float(value) for value in _early_bound(front, "IView").GetOutline()))
    border = _finished_border(adapter)
    gap = _PAPER_GAP_M + 0.0002
    left, right = border.xmin + gap, front_box.xmin - gap
    width = right - left
    if (
        shoulder_ink is None
        or not all(map(math.isfinite, (*landing, left, right, width, shoulder_ink.ymax)))
        or width <= 0
    ):
        raise RuntimeError("Purchased Screw Note: no measured native left wrapping field")
    # Include ALL actual source-band ink: the upper witness, arrow and any
    # actual outside stub, not a presumed dimension-line/text-only envelope.
    low = shoulder_ink.ymax + gap
    if low >= landing[1]:
        raise RuntimeError("Purchased Screw Note: actual shoulder ink blocks the left field")
    native, font = _note_font(annotation)
    frame = dict(line_length=width, font=font, left=left, low=low)
    native.LineLength = width
    if not annotation.SetTextFormat(0, False, native):
        raise RuntimeError("Purchased Screw Note: native word wrapping was refused")
    rebuild_drawing(adapter, label="native purchased-note automatic wrapping")
    wrapped = _paper_annotation(adapter, annotation, label="Purchased Screw Note")
    ink = display_box({"texts": wrapped["display"]["texts"]})
    position = tuple(float(value) for value in annotation.GetPosition())
    if (
        ink is None or len(position) != 3 or not all(map(math.isfinite, position))
        or ink.width > width + 1e-5 or ink.ymax + low - ink.ymin >= landing[1]
        or not annotation.SetPosition2(
            position[0] + left - ink.xmin, position[1] + low - ink.ymin, position[2],
        )
    ):
        raise RuntimeError(
            "Purchased Screw Note: cannot fit/place complete native left wrapped text; "
            f"ink={ink!r}, field={(left, right, low)!r}, landing={landing!r}"
        )
    rebuild_drawing(adapter, label="measured left straight purchased-note placement")

    def settled() -> None:
        _assert_note_wrap(adapter, note, landing=landing, frame=frame)
    settled()
    return settled, frame


def _assert_note_arrow(current: Any, landing: tuple, record: dict) -> None:
    """Prove full-precision native ink; the audit dump rounds coordinates to 0.1 um."""
    current = _early_bound(current, "IAnnotation")
    points = tuple(float(value) for value in current.GetLeaderPointsAtIndex(0) or ())
    raw_data = current.GetDisplayData()
    if raw_data is None:
        raise RuntimeError("Purchased Screw Note: native annotation display data is null")
    data = _early_bound(raw_data, "IDisplayData")
    arrow_count, line_count = data.GetArrowHeadCount(), data.GetLineCount()
    display = record["display"]
    if (
        type(arrow_count) is not int or type(line_count) is not int
        or arrow_count != 1 or line_count < 1
        or arrow_count != len(display.get("arrows") or ())
        or line_count != len(display.get("lines") or ())
    ):
        raise RuntimeError(
            "Purchased Screw Note: actual native arrow/line counts changed; "
            f"native={(arrow_count, line_count)!r}, "
            f"reported={(len(display.get('arrows') or ()), len(display.get('lines') or ()))!r}"
        )
    # SDK GetArrowHeadAtIndex2 returns all 12 doubles; GetLineAtIndex2
    # returns [color, lineType, unused, unused, startXYZ, endXYZ] (10).
    # Do not feed the shared collector's round(..., 7) into a 1e-8 proof.
    arrows = []
    for index in range(arrow_count):
        raw_arrow = data.GetArrowHeadAtIndex2(index)
        if raw_arrow is None:
            raise RuntimeError(f"Purchased Screw Note: native arrow row {index} is null")
        arrows.append(tuple(float(value) for value in raw_arrow))
    lines = []
    for index in range(line_count):
        raw_line = data.GetLineAtIndex2(index)
        if raw_line is None:
            raise RuntimeError(f"Purchased Screw Note: native line row {index} is null")
        line = tuple(float(value) for value in raw_line)
        if len(line) != 10 or not all(map(math.isfinite, line)):
            raise RuntimeError(
                f"Purchased Screw Note: native line {index} needs exactly ten finite doubles; "
                f"length={len(line)}, row={line[:10]!r}"
            )
        lines.append(line)
    # This fresh local note record also feeds the whole leader/arrow ink and
    # physical-body guards. Keep their endpoints unrounded, not just the tip
    # predicate below. The shared report collector remains unchanged.
    display["arrows"], display["lines"] = arrows, lines
    count, style = int(current.GetLeaderCount()), int(current.GetLeaderStyle())
    # SDK IAnnotation.GetLeaderStyle -> swLeaderStyle_e: attachment-mode
    # bitmasks swAttachLeaderTop/Center/Bottom/Nearest do not change shape.
    # Native drawing notes can retain swAttachLeaderNearest. Strip only
    # these documented bits; unknown bits remain in the exact base check.
    attachment_mask = 0x100 | 0x200 | 0x400 | 0x800
    attachment_mode = style & attachment_mask
    base_style = style & ~attachment_mask
    if (
        count != 1 or base_style != 1  # swSTRAIGHT
        or attachment_mode not in (0, 0x100, 0x200, 0x400, 0x800)
        or len(points) != 6 or not all(map(math.isfinite, points))
        or math.dist(points[3:5], landing) > 1e-8 or math.dist(points[:2], points[3:5]) <= 1e-8
        or len(arrows) != 1 or len(arrows[0]) != 12 or not all(map(math.isfinite, arrows[0]))
        or math.dist(arrows[0][:2], landing) > 1e-8
        or math.hypot(arrows[0][3], arrows[0][4]) <= 1e-8 or min(arrows[0][6:8]) <= 0
    ):
        leader_tip = points[3:5]
        arrow_tip = tuple(arrows[0][:2]) if arrows else ()
        leader_delta = tuple(
            actual - expected for actual, expected in zip(leader_tip, landing, strict=True)
        ) if len(leader_tip) == 2 else None
        arrow_delta = tuple(
            actual - expected for actual, expected in zip(arrow_tip, landing, strict=True)
        ) if len(arrow_tip) == 2 and all(isinstance(value, (int, float)) for value in arrow_tip) else None
        raise RuntimeError(
            "Purchased Screw Note: actual straight leader/arrow/landing changed; "
            f"leader_count={count}, style={style}, base_style={base_style}, "
            f"attachment_mode={attachment_mode}, points={points[:12]!r}, expected_tip={landing!r}, "
            f"leader_tip={leader_tip!r}, leader_delta_m={leader_delta!r}, "
            f"arrow_tip={arrow_tip!r}, arrow_delta_m={arrow_delta!r}, "
            f"arrow_count={len(arrows)}, arrow_lengths={[len(row) for row in arrows[:4]]!r}, "
            f"first_arrow={tuple(arrows[0][:12]) if arrows else ()!r}"
        )
    # annotation_geometry replaces matching display runs with registered
    # leaders. Give it this same validated native read, not the collector's
    # rounded leader points, so intended endpoint contact stays endpoint contact.
    record["leaders"] = [points]
    text = display_box({"texts": record["display"].get("texts") or ()})
    if text is None or not any(
        len(line) == 10 and all(map(math.isfinite, line))
        and math.dist(line[4:6], line[7:9]) > 1e-8 and any(
            math.dist(tip, landing) <= 1e-8
            and text.gap(Box.from_points((other,))) <= _PAPER_GAP_M
            for tip, other in ((line[4:6], line[7:9]), (line[7:9], line[4:6]))
        )
        for line in record["display"].get("lines") or ()
    ):
        raise RuntimeError(
            "Purchased Screw Note: actual full straight leader missing from native annotation display data; "
            f"expected_tip={landing!r}, native_lines={lines[:2]!r}"
        )


def _assert_note_wrap(adapter: Any, note: Any, *, landing: tuple, frame: dict) -> None:
    """Fresh native width/font/full-fragment proof, also used after cold reopening."""
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    native, font = _note_font(annotation)
    width = float(native.LineLength)
    if (
        bool(annotation.GetUseDocTextFormat(0)) or not math.isfinite(width) or width <= 0
        or not math.isclose(width, frame["line_length"], rel_tol=0, abs_tol=1e-8)
        or font[0] != frame["font"][0] or font[5:] != frame["font"][5:]
        or any(
            not math.isclose(actual, original, rel_tol=0, abs_tol=1e-10)
            for actual, original in zip(font[1:5], frame["font"][1:5], strict=True)
        )
    ):
        raise RuntimeError(
            "Purchased Screw Note: native wrapping width/font did not persist; "
            f"width={width!r}, font={font!r}, expected={frame!r}"
        )
    record = _paper_annotation(adapter, annotation, label="Purchased Screw Note")
    _assert_note_arrow(annotation, landing, record)
    points = tuple(float(value) for value in annotation.GetLeaderPointsAtIndex(0) or ())
    if (
        len(points) != 6 or not all(map(math.isfinite, points))
        or points[0] >= landing[0] or points[1] >= landing[1]
    ):
        raise RuntimeError("Purchased Screw Note: actual straight leader left its down-left field")
    rows = record["display"]["texts"]
    text = display_box({"texts": rows})
    ordered = sorted(rows, key=lambda row: (-float(row["pos"][1]), float(row["pos"][0])))
    printed = " ".join(str(row["t"]) for row in ordered).split()
    if (
        text is None or text.width > width + 1e-5
        or abs(text.xmin - frame["left"]) > 1e-5 or abs(text.ymin - frame["low"]) > 1e-5
        or printed != str(note.GetText() or "").split()
        or any(
            not math.isclose(float(row["h"]), font[1], rel_tol=0, abs_tol=1e-8)
            or str(row["font"]) != font[0] or abs(float(row["ang"])) > 1e-8
            for row in rows
        )
    ):
        raise RuntimeError(
            "Purchased Screw Note: complete native wrapped ink/font/width changed; "
            f"ink={text!r}, frame={frame!r}, fragments={len(rows)}"
        )


def _assert_paper_layout(
    adapter: Any, front: Any, top: Any, iso: Any, note: Any, displays: dict[str, Any],
    *, purchased_text: str,
) -> None:
    """Fresh owned-defect guards over complete actual native paper geometry."""
    border = _finished_border(adapter)
    edge, landing = _purchased_head_target(adapter, front)
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    if (
        int(annotation.GetAttachedEntityCount3()) != 1 or len(attached) != 1
        or tuple(annotation.GetAttachedEntityTypes() or ()) != (1,)
        or attached[0] is None or int(adapter.swApp.IsSame(attached[0], edge)) != 1
        or bool(annotation.IsDangling())
    ):
        raise RuntimeError("Purchased Screw Note: exact native head-top EDGE attachment changed")
    note_record = _paper_annotation(adapter, annotation, label="Purchased Screw Note")
    _assert_note_arrow(annotation, landing, note_record)
    if (
        int(annotation.OwnerType) != 0 or int(adapter.swApp.IsSame(annotation.Owner, front)) != 1
        or str(note.PropertyLinkedText or "") != property_link("Purchased Screw Note")
        or str(note.GetText() or "").replace("\r", "") != purchased_text.replace("\r", "")
    ):
        raise RuntimeError("Purchased Screw Note: native target/owner/property text changed")
    owned = {"Purchased Screw Note": note_record}
    for name, axis in _REFERENCE_SHELF_AXES.items():
        owned[name] = _assert_text_shelf(adapter, displays[name], axis=axis, label=name)["record"]
    foreign = []
    for view in (front, top):
        for raw in _early_bound(view, "IView").GetAnnotations() or ():
            item = _early_bound(raw, "IAnnotation")
            if any(
                int(adapter.swApp.IsSame(item, target)) == 1
                for target in (
                    annotation, *(displays[name].GetAnnotation() for name in _REFERENCE_SHELF_AXES)
                )
            ):
                continue
            foreign.append(_paper_annotation(adapter, item, label="neighbouring finished annotation"))
    records = [*owned.items(), *((f"neighbour {index}", record) for index, record in enumerate(foreign))]
    for name, record in owned.items():
        text = display_box({"texts": record["display"].get("texts") or ()})
        if text is None or (
            text.xmin < border.xmin or text.ymin < border.ymin
            or text.xmax > border.xmax or text.ymax > border.ymax
        ):
            raise RuntimeError(f"{name}: complete native text escapes inner border")
        for other_name, other in records:
            if other_name == name:
                continue
            other_text = display_box({"texts": other["display"].get("texts") or ()})
            geometry = annotation_geometry(other, owner=other_name, advance=calibrate_sheet_advance((other,)))
            if (
                other_text is not None and text.gap(other_text) < _PAPER_GAP_M
            ) or any(segment_box_distance(run, text) < _PAPER_GAP_M for run in geometry.segments):
                raise RuntimeError(f"{name}: complete native text crowds foreign text/line ({other_name})")
    note_text = display_box({"texts": owned["Purchased Screw Note"]["display"]["texts"]})
    for view in (front, top, iso):
        box = Box(*(float(value) for value in _early_bound(view, "IView").GetOutline()))
        if note_text.gap(box) < _PAPER_GAP_M:
            raise RuntimeError("Purchased Screw Note: complete native text crowds a finished view")
    top_points = model_points_in_view(
        adapter, top,
        [(x / 1000, (HEAD_H - HEAD_CHAMFER) / 1000, z / 1000)
         for x, z in ((-HEAD_DIA / 2, 0), (HEAD_DIA / 2, 0),
                      (0, -HEAD_DIA / 2), (0, HEAD_DIA / 2))],
        label="Top actual head perimeter",
    )
    body = Box.from_points(list(top_points))
    socket = measure_reference_text(adapter, displays["SupplierSocketAF"], axis=0, label="SupplierSocketAF")
    diameter = _paper_annotation(adapter, displays["SupplierHeadDiameter"].GetAnnotation(), label="SupplierHeadDiameter")
    diameter_text = display_box({"texts": diameter["display"]["texts"]})
    if (
        body is None or diameter_text is None
        or not all(math.isfinite(value) for point in top_points for value in point)
        or socket["text"].gap(body) < _PAPER_GAP_M
        or not diameter_text.ymax + _PAPER_GAP_M <= socket["tips"][0][1] <= body.ymin - 0.001
    ):
        raise RuntimeError("SupplierSocketAF: actual dimension line/text left the clear projected gap")
    note_record = owned["Purchased Screw Note"]
    note_ink = annotation_geometry(
        note_record, owner="Purchased Screw Note", advance=calibrate_sheet_advance((note_record,)),
    )
    # The complete native leader/arrow must not cross ANY foreign native ink.
    for other_name, other in records:
        if other_name == "Purchased Screw Note":
            continue
        geometry = annotation_geometry(other, owner=other_name, advance=calibrate_sheet_advance((other,)))
        text = display_box({"texts": other["display"].get("texts") or ()})
        if any(
            _segment_crossing(first, second) is not None
            for first in note_ink.segments for second in geometry.segments
        ) or text is not None and any(segment_box_distance(run, text) < _PAPER_GAP_M for run in note_ink.segments):
            raise RuntimeError("Purchased Screw Note: complete leader crosses foreign native ink")
    left_point, _left_projection = _head_sheet_left_point(adapter, front)
    radial_x, radial_z = left_point[0] * 1000 / _HEAD_TOP_R, left_point[2] * 1000 / _HEAD_TOP_R
    head = model_points_in_view(
        adapter, front,
        [(radial_x * radius / 1000, y / 1000, radial_z * radius / 1000) for radius, y in (
            (HEAD_DIA / 2, 0), (-HEAD_DIA / 2, 0),
            (-HEAD_DIA / 2, HEAD_H - HEAD_CHAMFER), (-_HEAD_TOP_R, HEAD_H),
            (_HEAD_TOP_R, HEAD_H), (HEAD_DIA / 2, HEAD_H - HEAD_CHAMFER),
        )], label="actual source head silhouette stations",
    )
    outline = [Segment(*first, *second) for first, second in zip(head, (*head[1:], head[0]), strict=True)]
    for run_index, run in enumerate(note_ink.segments):
        midpoint = ((run.x0 + run.x1) / 2, (run.y0 + run.y1) / 2)
        crosses = [
            (edge.x1 - edge.x0) * (midpoint[1] - edge.y0)
            - (edge.y1 - edge.y0) * (midpoint[0] - edge.x0) for edge in outline
        ]
        intersections = [
            (index, point, math.dist(point, landing))
            for index, edge in enumerate(outline)
            if (point := _segment_crossing(run, edge)) is not None
        ]
        inside_head = min(crosses) > 1e-12
        crosses_head = any(distance > 1e-8 for _index, _point, distance in intersections)
        enters_top = _segment_enters_box(run, body)
        if inside_head or crosses_head or enters_top:
            native_display = note_record["display"]
            raise RuntimeError(
                "Purchased Screw Note: actual leader enters projected head/Top body; "
                f"run_index={run_index}, role={run.role!r}, "
                f"endpoints={(run.x0, run.y0, run.x1, run.y1)!r}, midpoint={midpoint!r}, "
                f"inside_head={inside_head}, crosses_head={crosses_head}, enters_top={enters_top}, "
                f"head={head!r}, signed_crosses={crosses!r}, intersections={intersections!r}, "
                f"landing={landing!r}, top_box={body!r}, "
                f"registered_leaders={note_record['leaders']!r}, "
                f"native_arrows={native_display['arrows']!r}, "
                f"native_line_count={len(native_display['lines'])}, "
                f"native_lines={native_display['lines'][:4]!r}"
            )


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
        adapter, property_view=SPEC.artifact_stem, scale=SHEET_SCALE, layout=SPEC.layout,
        unit=part_drawing_unit("pd-vn-transgear-pivot-screw"),
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
    alignment_check = _align_top_origin(adapter, front, top, iso)
    centre_mark_check = _trim_top_mark(adapter, top)
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
    _blacken_shoulder_witnesses(adapter, front)
    tail_check, tail_frame = _move_tail_column(
        adapter, by_name["ThreadLengthMin"], supplier_refs["SupplierThreadMajor"],
    )
    head_entity, head_edge = _purchased_head_target(adapter, front)
    note = _early_bound(
        add_attached_note(
            adapter,
            front,
            text=property_link("Purchased Screw Note"),
            entity=head_entity,
            attached_to=head_entity,
            leader_attach_xy=head_edge,
            label="Purchased Screw Note",
            note_xy=PURCHASED_NOTE_XY,
        ),
        "INote",
    )
    original_note_annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
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

    def shelf_displays() -> dict[str, Any]:
        fresh = _assert_supplier_references(adapter, identities, configurations)
        return {name: fresh[name] for name in _REFERENCE_SHELF_AXES}

    shelf_check = shelve_reference_text(
        adapter, reacquire=shelf_displays, axes=_REFERENCE_SHELF_AXES,
        force=tuple(_REFERENCE_SHELF_AXES), label="pivot purchased references",
    )
    _clear_socket_text(adapter, top, shelf_displays()["SupplierSocketAF"])
    note_check, note_frame = _place_purchased_note(
        adapter, front, note, _assert_supplier_references(adapter, identities, configurations),
    )

    def settled_paper() -> None:
        fresh = _assert_supplier_references(adapter, identities, configurations)
        alignment_check()
        centre_mark_check()
        tail_check()
        note_check()
        verify_machining_controls(
            [by_name[name] for name in EXPECTED_CONTROLS],
            expected=EXPECTED_CONTROLS, tolerance_types=DIMENSION_TOLERANCE_TYPES,
            precision=DIMENSION_PRECISION,
        )
        _verify_reference_length(adapter, by_name["CutLength"])
        _assert_paper_layout(
            adapter, front, top, iso, note, fresh,
            purchased_text=properties["Purchased Screw Note"],
        )

    physical_labels = ("SupplierHeadHeight", "SupplierStockThreadLength")
    serialized_full_names: dict[str, str] = {}
    serialized_shelf_names: dict[str, str] = {}
    capture_called = False
    paper_refs = {
        "SupplierHeadDiameter": supplier_refs["SupplierHeadDiameter"],
        "SupplierThreadMajor": supplier_refs["SupplierThreadMajor"],
        "ThreadLengthMin": by_name["ThreadLengthMin"],
        "SupplierHeadHeight": supplier_refs["SupplierHeadHeight"],
    }
    paper_identities = _supplier_reference_identities(adapter, paper_refs)
    paper = dict(tail=tail_frame, wrap=note_frame, text=properties["Purchased Screw Note"])

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
        shelf_labels = tuple(_REFERENCE_SHELF_AXES)
        shelves = capture_serialized_physical_axial_names(
            adapter, {name: supplier_refs[name] for name in shelf_labels}, identities,
            configurations, labels=shelf_labels, drawing_path=OUTPUTS.slddrw,
            sheet_names=SHEET_NAMES,
        )
        if (
            set(shelves) != set(shelf_labels)
            or any(not isinstance(value, str) or not value for value in shelves.values())
            or len(set(shelves.values())) != 2
            or shelves["SupplierHeadHeight"] != captured["SupplierHeadHeight"]
        ):
            raise RuntimeError("reference shelves: serialized identity capture is incomplete")
        serialized_shelf_names.update(shelves)
        extra = {}
        for labels in (
            ("SupplierHeadDiameter", "SupplierThreadMajor"), ("SupplierHeadHeight", "ThreadLengthMin"),
        ):
            fresh_names = capture_serialized_physical_axial_names(
                adapter, {name: paper_refs[name] for name in labels}, paper_identities,
                configurations, labels=labels, drawing_path=OUTPUTS.slddrw, sheet_names=SHEET_NAMES,
            )
            if set(fresh_names) != set(labels) or len(set(fresh_names.values())) != 2 or any(
                not isinstance(value, str) or not value for value in fresh_names.values()
            ):
                raise RuntimeError("saved paper: incomplete serialized dimension identity capture")
            extra.update(fresh_names)
        if extra.pop("SupplierHeadHeight") != captured["SupplierHeadHeight"]:
            raise RuntimeError("saved paper: physical head identity changed between exact captures")
        paper["names"] = extra
        paper["note"] = capture_serialized_note_name(
            adapter, original_note_annotation, front, drawing_path=OUTPUTS.slddrw, source_path=SOURCE,
            sheet_names=SHEET_NAMES, sheet_name=SHEET_NAMES[0],
            configuration=configurations[view_name(adapter, front)][1],
            label="Purchased Screw Note",
        )

    result = await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Pivot Screw — Modified Stock Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        settled_checks=(shelf_check, settled_paper),
        checkpoint=checkpoint,
    )
    if not capture_called:
        raise RuntimeError("physical references: before_drawing_close identity checkpoint was never called")
    _assert_saved_physical_references(
        adapter, identities, configurations, serialized_full_names=serialized_full_names,
        serialized_shelf_names=serialized_shelf_names, paper=paper,
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
