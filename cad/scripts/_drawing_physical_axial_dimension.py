"""Native physical axial dimensions for supplier heads and stock lengths.

``Type2 == swLinearDimension`` alone says nothing about sheet orientation.  The
native arrow records must independently prove a vertical dimension at the exact
projected physical stations, at the view's current scale, as well as passing the
unchanged named-edge/native-value assertion.

The 1e-8 m sheet-position bound inherits the recipes' exact physical-edge
GetClosestPointOn predicate and equals the existing 1e-5 mm model-length
precision.  For these sub-metre coordinates it conservatively exceeds IEEE
double transform roundoff; it is not fitted to a native receipt.  The independent
model-length tolerance remains unchanged.  The 1e-9 normalized direction bound
is an exact-axis numerical check, not an angular layout allowance.

SDK: IDisplayDimension.Type2 / swDimensionType_e.swLinearDimension (2),
IAnnotation.GetDisplayData, IDisplayData.GetArrowHeadCount / GetArrowHeadAtIndex2
([tipXYZ, directionXYZ, width, height, style, normalXYZ]), and IView.ScaleDecimal
(getter only).  The assertion never selects, modifies, rebuilds, or saves.
The stock-only creator selects actual model edges through IView.SelectEntity.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import view_name

from _com import _early_bound
from _drawing_edge_dimensions import assert_dimension_measures
from _drawing_projection import model_points_in_view
import _telemetry


__all__ = [
    "add_native_physical_axial_dimension",
    "assert_native_physical_axial_dimension",
    "capture_serialized_physical_axial_names",
]

_POSITION_TOL_M = 1e-8
_DIRECTION_TOL = 1e-9


def _native_integer(value: Any, name: str) -> int:
    # Do not truncate a malformed count/type (2.5), parse text, or accept bool.
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a native integer, got {repr(value)[:120]}")
    return value


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number, got {repr(value)[:120]}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite, got {number!r}")
    return number


@_telemetry.traced("drawing.physical_axial_dimension_native_assert", label_param="label")
def assert_native_physical_axial_dimension(
    adapter: Any,
    view: Any,
    display: Any,
    *,
    entities: tuple[Any, Any],
    points_m: tuple[tuple[float, float, float], tuple[float, float, float]],
    expected_mm: float,
    label: str,
    phase: str = "settled",
) -> float:
    """Return the unchanged shared measured millimetres only if every proof holds.

    All native metadata, attachments, value, arrows, scale and projected stations
    are read anew on every invocation, including settled/saved callers.  Failure
    evidence is bounded, records the failing stage, and chains the original
    binder/getter/proof exception rather than replacing it with diagnostic work.
    """
    snapshot: dict[str, Any] = {"label": label, "phase": phase, "display_null": display is None}
    stage = "display"
    try:
        if display is None:
            raise RuntimeError("native display dimension is null")
        stage = "display_bind"
        display = _early_bound(display, "IDisplayDimension")
        stage = "annotation"
        raw_annotation = display.GetAnnotation()
        snapshot["annotation_null"] = raw_annotation is None
        if raw_annotation is None:
            raise RuntimeError("native dimension has no annotation")
        stage = "annotation_bind"
        annotation = _early_bound(raw_annotation, "IAnnotation")
        stage = "application_bind"
        app = _early_bound(adapter.swApp, "ISldWorks")
        stage = "type2"
        snapshot["type2"] = _native_integer(display.Type2, "Type2")
        stage = "attached_count"
        snapshot["attached_count"] = _native_integer(
            annotation.GetAttachedEntityCount3(), "attached count"
        )
        stage = "attached_entities"
        attached = annotation.GetAttachedEntities3()
        attached_length = 0 if attached is None else len(attached)
        snapshot["attached_length"] = attached_length
        snapshot["attached_nulls"] = tuple(
            attached[index] is None for index in range(min(attached_length, 4))
        )
        stage = "attached_types"
        raw_kinds = annotation.GetAttachedEntityTypes()
        kinds_length = 0 if raw_kinds is None else len(raw_kinds)
        snapshot["kinds_length"] = kinds_length
        # Record the bounded native slots before validation: a malformed slot
        # must not erase the array/earlier slots the native getter did return.
        # Non-scalar diagnostic representations are bounded, never coerced for
        # acceptance. Validate the original values, with no second native read.
        kind_slots = tuple(raw_kinds[index] for index in range(min(kinds_length, 4)))
        snapshot["kinds"] = tuple(
            kind if kind is None or isinstance(kind, (bool, int, float))
            else repr(kind)[:120]
            for kind in kind_slots
        )
        for index, kind in enumerate(kind_slots):
            _native_integer(kind, f"attachment type {index}")
        stage = "dangling"
        dangling = annotation.IsDangling()
        if not isinstance(dangling, bool):
            raise TypeError("IsDangling must return a native boolean")
        snapshot["dangling"] = dangling
        stage = "owner_type"
        snapshot["owner_type"] = _native_integer(annotation.OwnerType, "OwnerType")
        stage = "owner"
        owner = annotation.Owner
        snapshot["owner_null"] = owner is None
        stage = "owner_same"
        snapshot["owner_same"] = (
            None if owner is None else _native_integer(app.IsSame(owner, view), "owner IsSame")
        )

        stage = "metadata_predicates"
        if snapshot["type2"] != 2:  # swDimensionType_e.swLinearDimension ONLY
            raise RuntimeError("expected linear dimension Type2=2")
        if snapshot["owner_type"] != 0 or snapshot["owner_null"] or snapshot["owner_same"] != 1:
            raise RuntimeError("expected exact front-view owner (OwnerType=0, IsSame=1)")
        if (
            snapshot["attached_count"] != 2 or attached_length != 2
            or kinds_length != 2 or snapshot["kinds"] != (1, 1)  # swSelEDGES
            or any(snapshot["attached_nulls"]) or snapshot["dangling"]
        ):
            raise RuntimeError("expected two nonnull actual edge attachments, not dangling")

        stage = "physical_inputs"
        if len(entities) != 2 or any(entity is None for entity in entities):
            raise ValueError("expected two nonnull named physical edges")
        expected = _finite_number(expected_mm, "expected_mm")
        if expected <= 0:
            raise ValueError("expected_mm must be positive")
        if len(points_m) != 2 or any(len(point) != 3 for point in points_m):
            raise ValueError("expected exactly two physical model XYZ stations")
        physical_points = tuple(
            tuple(_finite_number(value, f"physical station {index} coordinate {axis}")
                  for axis, value in enumerate(point))
            for index, point in enumerate(points_m)
        )
        snapshot["points_m"] = physical_points
        stage = "physical_measurement"
        # Preserve the existing exact unordered edge bijection, finiteness and
        # native model-value tolerance (default 1e-5 mm), without a second guard.
        measured_mm = assert_dimension_measures(
            adapter, display, expected_mm=expected_mm, label=label, entities=entities
        )
        snapshot["measured_mm"] = measured_mm

        stage = "display_data"
        raw_data = annotation.GetDisplayData()
        snapshot["display_data_null"] = raw_data is None
        if raw_data is None:
            raise RuntimeError("native annotation has no display data")
        stage = "display_data_bind"
        data = _early_bound(raw_data, "IDisplayData")
        stage = "arrow_count"
        snapshot["arrow_count"] = _native_integer(data.GetArrowHeadCount(), "arrow count")
        if snapshot["arrow_count"] != 2:
            raise RuntimeError("expected exactly two native arrow heads")
        arrow_heads: list[tuple[float, ...]] = []
        arrow_lengths: list[int | None] = []
        snapshot["arrow_heads"] = arrow_heads
        snapshot["arrow_lengths"] = arrow_lengths
        directions: list[tuple[float, float, float]] = []
        for index in range(2):
            stage = f"arrow_head_{index}"
            raw_arrow = data.GetArrowHeadAtIndex2(index)
            length = None if raw_arrow is None else len(raw_arrow)
            arrow_lengths.append(length)
            if raw_arrow is None:
                raise RuntimeError(f"native arrow head {index} is null")
            # Only evidence is truncated: acceptance always requires all 12 SDK
            # doubles, including width/height/style/normal, finite and present.
            arrow = tuple(
                _finite_number(raw_arrow[slot], f"arrow head {index} slot {slot}")
                for slot in range(min(length, 12))
            )
            arrow_heads.append(arrow)
            if length != 12:
                raise RuntimeError(f"native arrow head {index} must contain exactly 12 doubles")
            stage = f"arrow_direction_{index}"
            norm = math.hypot(*arrow[3:6])
            if not math.isfinite(norm) or norm <= 0:
                raise RuntimeError(f"native arrow head {index} direction must be finite and nonzero")
            unit = (arrow[3] / norm, arrow[4] / norm, arrow[5] / norm)
            directions.append(unit)
            if (
                abs(unit[0]) > _DIRECTION_TOL or abs(unit[2]) > _DIRECTION_TOL
                or abs(abs(unit[1]) - 1.0) > _DIRECTION_TOL
            ):
                raise RuntimeError(f"native arrow head {index} direction is not sheet-vertical")
        tips = tuple(arrow[:3] for arrow in arrow_heads)
        snapshot["arrow_tips"] = tips
        snapshot["arrow_directions"] = tuple(directions)
        stage = "arrow_geometry"
        if directions[0][1] * directions[1][1] >= 0:
            raise RuntimeError("native vertical arrow directions must have opposite Y signs")
        if any(abs(tip[2]) > _POSITION_TOL_M for tip in tips):
            raise RuntimeError("native arrow tips must lie in the sheet Z plane")
        if abs(tips[0][0] - tips[1][0]) > _POSITION_TOL_M:
            raise RuntimeError("native vertical arrow tips must have the same sheet X")
        native_ys = tuple(sorted(tip[1] for tip in tips))
        span_m = native_ys[1] - native_ys[0]
        snapshot["span_m"] = span_m
        if not math.isfinite(span_m) or span_m <= 0:
            raise RuntimeError("native vertical arrow span must be finite and positive")

        stage = "view_bind"
        native_view = _early_bound(view, "IView")
        stage = "scale_decimal"
        scale = _finite_number(native_view.ScaleDecimal, "ScaleDecimal")
        snapshot["scale_decimal"] = scale
        if scale <= 0:
            raise RuntimeError("native view ScaleDecimal must be positive")
        expected_span_m = expected / 1000.0 * scale
        snapshot["expected_span_m"] = expected_span_m
        if not math.isfinite(expected_span_m) or expected_span_m <= 0:
            raise RuntimeError("scaled physical length must be finite and positive")
        stage = "station_projection"
        projected = model_points_in_view(adapter, view, points_m, label=label)
        snapshot["projected_length"] = len(projected)
        if len(projected) != 2 or any(len(point) != 2 for point in projected):
            raise RuntimeError("expected exactly two projected physical sheet XY stations")
        sheet_points = tuple(
            tuple(_finite_number(value, f"projected station {index} coordinate {axis}")
                  for axis, value in enumerate(point))
            for index, point in enumerate(projected)
        )
        station_ys = tuple(sorted(point[1] for point in sheet_points))
        snapshot["projected_station_ys"] = station_ys
        projected_span = station_ys[1] - station_ys[0]
        snapshot["projected_span_m"] = projected_span
        stage = "station_geometry"
        if not math.isfinite(projected_span) or projected_span <= 0:
            raise RuntimeError("projected physical station span must be finite and positive")
        if abs(projected_span - expected_span_m) > _POSITION_TOL_M:
            raise RuntimeError("projected physical station span disagrees with scaled physical length")
        if any(abs(actual - station) > _POSITION_TOL_M
               for actual, station in zip(native_ys, station_ys, strict=True)):
            raise RuntimeError("native arrow tips do not match the projected physical station Ys")
        if (
            abs(span_m - projected_span) > _POSITION_TOL_M
            or abs(span_m - expected_span_m) > _POSITION_TOL_M
        ):
            raise RuntimeError("native arrow span disagrees with projected/scaled physical length")
    except Exception as exc:
        reason = str(exc)[:500]
        snapshot.update(
            failure_stage=stage, failure_error_type=type(exc).__name__, failure_error=reason
        )
        _telemetry.event("drawing.physical_axial_dimension_native_refusal", reason=reason, **snapshot)
        prefix = "" if reason.startswith(label) else f"{label}: "
        raise RuntimeError(f"{prefix}{reason}; native_snapshot={snapshot!r}") from exc

    _telemetry.event("drawing.physical_axial_dimension_native_proof", **snapshot)
    return measured_mm


@_telemetry.traced("drawing.physical_axial_dimension_native_add", label_param="label")
def add_native_physical_axial_dimension(
    adapter: Any,
    view: Any,
    *,
    entities: tuple[Any, Any],
    points_m: tuple[tuple[float, float, float], tuple[float, float, float]],
    text_xy: tuple[float, float],
    expected_mm: float,
    label: str,
) -> Any:
    """Create a stock dimension from two actual edges in the drawing's view.

    IView.SelectEntity(Entity, AppendFlag) supplies the drawing context for
    model edges; IEntity.Select4 is deliberately not used.  GetClosestPointOn
    returns [XYZ, UParameter, NotUsed]: validate the first four finite doubles,
    ignore the documented unused fifth, and prove the supplied point is on the
    actual trimmed edge, not merely its underlying curve.

    SetSelectionPoint2(Index, Mark, X, Y, Z) uses world coordinates in the
    context of its ISelectionMgr.  This manager belongs to the active DRAWING:
    set projected sheet XY,0, as in the proven head flow, and require the
    documented GetSelectionPoint2(Index, Mark) to read that same point back.
    The source-model XYZ stations are independently checked on their edges;
    they are never compared with drawing-manager selection coordinates.
    No rebuild, type coercion, repair or alternate selection path is attempted.
    """
    snapshot: dict[str, Any] = {"label": label, "phase": "creation"}
    stage = "model_bind"
    model = None
    try:
        try:
            model = _early_bound(adapter.currentModel, "IModelDoc2")
            if model is None:
                raise RuntimeError("no current drawing model")
            stage = "physical_inputs"
            if len(entities) != 2 or any(entity is None for entity in entities):
                raise ValueError("expected two nonnull named physical edges")
            if len(points_m) != 2 or any(len(point) != 3 for point in points_m):
                raise ValueError("expected exactly two physical model XYZ stations")
            physical_points = tuple(
                tuple(_finite_number(value, f"physical station {index} coordinate {axis}")
                      for axis, value in enumerate(point))
                for index, point in enumerate(points_m)
            )
            snapshot["points_m"] = physical_points
            expected = _finite_number(expected_mm, "expected_mm")
            if expected <= 0:
                raise ValueError("expected_mm must be positive")
            if len(text_xy) != 2:
                raise ValueError("expected a dimension text sheet XY point")
            text_point = tuple(_finite_number(value, "text coordinate") for value in text_xy)
            stage = "application_bind"
            app = _early_bound(adapter.swApp, "ISldWorks")
            stage = "physical_distinctness"
            snapshot["physical_edges_same"] = _native_integer(
                app.IsSame(entities[0], entities[1]), "physical edges IsSame"
            )
            if snapshot["physical_edges_same"] != 0:
                raise RuntimeError("named physical edges are not provably distinct")
            closest_points = []
            snapshot["closest_points_m"] = closest_points
            for index, (entity, point) in enumerate(zip(entities, physical_points, strict=True), 1):
                stage = f"physical_edge_{index}"
                edge = _early_bound(entity, "IEdge")
                raw_closest = edge.GetClosestPointOn(point[0], point[1], point[2])
                if raw_closest is None or len(raw_closest) != 5:
                    raise RuntimeError(f"physical edge {index} closest point must contain five doubles")
                closest = tuple(
                    _finite_number(raw_closest[slot], f"physical edge {index} closest point slot {slot}")
                    for slot in range(4)
                )
                closest_points.append(closest[:3])
                if math.dist(closest[:3], point) > _POSITION_TOL_M:
                    raise RuntimeError(f"physical station {index} is not on its actual trimmed edge")
            stage = "station_projection"
            projected = model_points_in_view(adapter, view, physical_points, label=label)
            if len(projected) != 2 or any(len(point) != 2 for point in projected):
                raise RuntimeError("expected exactly two projected physical sheet XY stations")
            sheet_points = tuple(
                tuple(_finite_number(value, f"projected station {index} coordinate {axis}")
                      for axis, value in enumerate(point))
                for index, point in enumerate(projected)
            )
            snapshot["projected_points_m"] = sheet_points
            stage = "view_bind"
            native_view = _early_bound(view, "IView")
            drawing = _early_bound(model, "IDrawingDoc")
            manager = _early_bound(model.SelectionManager, "ISelectionMgr")
            stage = "activate_view"
            name = view_name(adapter, view)
            snapshot["view_name"] = name
            if not isinstance(name, str) or not name or drawing.ActivateView(name) is not True:
                raise RuntimeError("cannot activate exact physical dimension drawing view")
            stage = "clear_selection"
            model.ClearSelection2(True)
            selected = []
            snapshot["selection_kinds"] = []
            snapshot["selection_same"] = []
            for index, entity in enumerate(entities, 1):
                stage = f"select_edge_{index}"
                if native_view.SelectEntity(entity, index > 1) is not True:
                    raise RuntimeError(f"failed to select physical edge {index} in drawing view")
                stage = f"selection_count_{index}"
                count = _native_integer(manager.GetSelectedObjectCount2(-1), "selection count")
                snapshot["selection_count"] = count
                if count != index:
                    raise RuntimeError(f"selection count changed at physical edge {index}")
                stage = f"selection_kind_{index}"
                kind = _native_integer(manager.GetSelectedObjectType3(index, -1), "selection type")
                snapshot["selection_kinds"].append(kind)
                if kind != 1:  # swSelectType_e.swSelEDGES
                    raise RuntimeError(f"selected physical object {index} is not an EDGE")
                stage = f"selection_identity_{index}"
                actual = manager.GetSelectedObject6(index, -1)
                if actual is None:
                    raise RuntimeError(f"selected physical edge {index} is null")
                same = _native_integer(app.IsSame(actual, entity), "selected edge IsSame")
                snapshot["selection_same"].append(same)
                if same != 1:
                    raise RuntimeError(f"wrong selected object at physical edge {index}")
                if selected and _native_integer(
                    app.IsSame(selected[0], actual), "selected pair IsSame"
                ) != 0:
                    raise RuntimeError("selected physical edges are not provably distinct")
                selected.append(actual)
            for index, point in enumerate(sheet_points, 1):
                stage = f"set_selection_point_{index}"
                if manager.SetSelectionPoint2(index, -1, point[0], point[1], 0.0) is not True:
                    raise RuntimeError(f"cannot set physical selection point {index}")
            # Read the complete list again after both appends and point setters:
            # neither may silently replace the first selected edge or point.
            stage = "final_selection_count"
            snapshot["selection_count"] = _native_integer(
                manager.GetSelectedObjectCount2(-1), "selection count"
            )
            if snapshot["selection_count"] != 2:
                raise RuntimeError("expected exactly two selected physical edges before creation")
            selected = []
            readback_points = []
            snapshot["selection_points_m"] = readback_points
            for index, (entity, point) in enumerate(zip(entities, sheet_points, strict=True), 1):
                stage = f"final_selection_edge_{index}"
                if _native_integer(manager.GetSelectedObjectType3(index, -1), "selection type") != 1:
                    raise RuntimeError(f"selected physical object {index} is not an EDGE")
                actual = manager.GetSelectedObject6(index, -1)
                if actual is None or _native_integer(
                    app.IsSame(actual, entity), "selected edge IsSame"
                ) != 1:
                    raise RuntimeError(f"wrong selected object at physical edge {index}")
                if selected and _native_integer(
                    app.IsSame(selected[0], actual), "selected pair IsSame"
                ) != 0:
                    raise RuntimeError("selected physical edges are not provably distinct")
                selected.append(actual)
                stage = f"selection_point_{index}"
                raw_point = manager.GetSelectionPoint2(index, -1)
                if raw_point is None or len(raw_point) != 3:
                    raise RuntimeError(f"selection point {index} must contain exactly three doubles")
                actual_point = tuple(
                    _finite_number(value, f"selection point {index} coordinate {axis}")
                    for axis, value in enumerate(raw_point)
                )
                readback_points.append(actual_point)
                if math.dist(actual_point, (*point, 0.0)) > _POSITION_TOL_M:
                    raise RuntimeError(f"selection point {index} differs from projected physical station")
            stage = "native_creation"
            display = model.AddVerticalDimension2(text_point[0], text_point[1], 0.0)
            snapshot["display_null"] = display is None
            if display is None:
                raise RuntimeError("native vertical dimension creation returned null")
        except Exception as exc:
            reason = str(exc)[:500]
            snapshot.update(
                failure_stage=stage, failure_error_type=type(exc).__name__, failure_error=reason
            )
            _telemetry.event("drawing.physical_axial_dimension_native_refusal", reason=reason, **snapshot)
            raise RuntimeError(f"{label}: {reason}; native_snapshot={snapshot!r}") from exc
        assert_native_physical_axial_dimension(
            adapter, view, display, entities=entities, points_m=physical_points,
            expected_mm=expected_mm, label=label, phase="creation",
        )
        return display
    finally:
        if model is not None:
            model.ClearSelection2(True)


@_telemetry.traced("drawing.physical_axial_serialized_identity_capture")
def capture_serialized_physical_axial_names(
    adapter: Any,
    references: dict[str, Any],
    identities: dict,
    configurations: dict,
    *,
    labels: tuple[str, str],
    drawing_path: Path,
    sheet_names: tuple[str, ...],
) -> dict[str, str]:
    """Read actual post-save names, anchored ONLY to the two original annotations.

    Call at ``before_drawing_close``, after the successful saves and strict audit.
    FullName includes a containing-model name; neither it nor GetName() or
    GetNameForSelection() is assumed immutable across a save or a cold reopen.
    This census does not repeat the physical proof, select, activate, or repair.

    SDK: IDrawingDoc.GetViews() returns unordered sheet rows, each led by its
    sheet view. IAnnotation.GetName() and IDisplayDimension.GetNameForSelection()
    take zero arguments; ISldWorks.IsSame(Object1, Object2) compares native
    objects, not their Python wrappers or diagnostic names.
    """
    if (
        not isinstance(labels, (tuple, list))
        or len(labels) != 2 or any(not isinstance(label, str) or not label for label in labels)
        or len(set(labels)) != 2
    ):
        raise RuntimeError("serialized physical references require exactly two distinct labels")
    missing = object()
    errors: list[tuple[str, Exception]] = []
    problems: list[str] = []
    inventory: list[dict[str, Any]] = []
    matches: dict[str, list[dict[str, Any]]] = {label: [] for label in labels}
    expected: dict[str, dict[str, Any]] = {}
    originals: dict[str, Any] = {}
    original_owners: dict[str, Any] = {}
    evidence: dict[str, Any] = {
        "phase": "serialized_capture",
        "expected_original_full_names": {},
        "expected_serialized_full_names": {},
        "label_match_counts": {label: 0 for label in labels},
        "originals": expected,
        "inventory": inventory,
    }

    def observe(record, key, getter, *, native=False):
        # A thrown getter leaves its field absent, not an invented null/empty
        # value. Continue independent reads/rows so the original cause and all
        # reachable actual IDs survive together in the refusal.
        try:
            value = getter()
        except Exception as exc:
            errors.append((key, exc))
            record.setdefault("errors", []).append({
                "field": key, "type": type(exc).__name__, "error": str(exc)[:500],
            })
            return missing
        if native:
            record[f"{key}_null"] = value is None
        else:
            record[key] = (
                value if value is None or isinstance(value, (str, bool, int, float))
                else {"type": type(value).__name__, "repr": repr(value)[:120]}
            )
        return value

    def same(record, key, left, right):
        value = observe(record, key, lambda: app.IsSame(left, right))
        if value is missing:
            return missing
        checked = observe(
            record, f"{key}_integer", lambda: _native_integer(value, key)
        )
        if checked is not missing and checked not in (0, 1):
            problems.append(f"{key}: unknown native IsSame state {checked!r}")
        return checked

    def require(condition, reason):
        if not condition:
            problems.append(reason)

    path = Path(drawing_path).resolve()
    evidence["expected_document_path"] = str(path)
    for label in labels:
        record = expected[label] = {}
        identity = identities.get(label)
        if not isinstance(identity, tuple) or len(identity) != 4:
            problems.append(f"{label}: missing original four-field identity")
        else:
            full_name, owner, _entities, _kinds = identity
            record.update(full_name=full_name, owner=owner)
            evidence["expected_original_full_names"][label] = full_name
            require(
                isinstance(full_name, str) and bool(full_name)
                and isinstance(owner, str) and bool(owner),
                f"{label}: original FullName/owner must be nonempty native names",
            )
            captured = configurations.get(owner) if isinstance(owner, str) else None
            if isinstance(captured, tuple) and len(captured) == 2:
                record.update(sheet=captured[0], configuration=captured[1])
            else:
                problems.append(f"{label}: missing captured sheet/configuration")
        raw = references.get(label)
        record["annotation_null"] = raw is None
        if raw is None:
            problems.append(f"{label}: original annotation is null or missing")
            continue
        annotation = observe(
            record, "annotation_bind", lambda: _early_bound(raw, "IAnnotation"), native=True
        )
        if annotation is missing or annotation is None:
            problems.append(f"{label}: original annotation binding is unavailable")
            continue
        originals[label] = annotation
        observe(record, "annotation_name", lambda: annotation.GetName())
        observe(record, "owner_type", lambda: _native_integer(annotation.OwnerType, "original OwnerType"))
        original_owners[label] = observe(record, "owner", lambda: annotation.Owner, native=True)

    app = observe(
        evidence, "application_bind", lambda: _early_bound(adapter.swApp, "ISldWorks"), native=True
    )
    model = observe(
        evidence, "model_bind", lambda: _early_bound(adapter.currentModel, "IModelDoc2"), native=True
    )
    require(model is not missing and model is not None, "current drawing is null or unavailable")
    require(app is not missing and app is not None, "native application is null or unavailable")
    if app is not missing and app is not None and len(originals) == 2:
        require(
            same(evidence, "original_annotations_is_same", originals[labels[0]], originals[labels[1]]) == 0,
            "original annotations must be provably distinct (IsSame=0)",
        )
    if model is not missing and model is not None:
        actual_path = observe(evidence, "document_path", lambda: model.GetPathName())
        observe(evidence, "document_title", lambda: model.GetTitle())
        document_type = observe(
            evidence, "document_type", lambda: _native_integer(model.GetType(), "document type")
        )
        require(document_type == 3, "current document is not a native drawing (type=3)")
        absolute_path = isinstance(actual_path, str) and bool(actual_path) and Path(actual_path).is_absolute()
        resolved_path = (
            observe(evidence, "resolved_document_path", lambda: str(Path(actual_path).resolve()))
            if absolute_path else missing
        )
        require(
            absolute_path and isinstance(resolved_path, str) and Path(resolved_path) == path,
            "current drawing path does not equal the actual saved output",
        )
        if app is not missing and app is not None:
            current = observe(
                evidence, "open_document", lambda: app.GetOpenDocumentByName(str(path)), native=True
            )
            active = observe(evidence, "active_document", lambda: app.ActiveDoc, native=True)
            for key, document in (("open_document_is_same", current), ("active_document_is_same", active)):
                if document is missing or document is None:
                    problems.append(f"{key}: saved output is not the current drawing")
                else:
                    require(
                        same(evidence, key, document, model) == 1,
                        f"{key}: saved output is not the current drawing (IsSame=1)",
                    )

    drawing = missing
    if model is not missing and model is not None:
        drawing = observe(
            evidence, "drawing_bind", lambda: _early_bound(model, "IDrawingDoc"), native=True
        )
    rows = missing
    if drawing is not missing and drawing is not None:
        actual_sheets = observe(evidence, "sheet_names", lambda: drawing.GetSheetNames())
        require(
            isinstance(actual_sheets, (tuple, list)) and tuple(actual_sheets) == tuple(sheet_names),
            "saved drawing sheet census changed",
        )
        if isinstance(actual_sheets, (tuple, list)):
            evidence["sheet_names"] = tuple(actual_sheets)
        rows = observe(evidence, "view_rows", lambda: drawing.GetViews(), native=True)
    actual_row_sheets = []
    actual_views: list[dict[str, Any]] = []
    all_dimensions: list[dict[str, Any]] = []
    require(isinstance(rows, (tuple, list)), "actual all-sheet view census is unavailable")
    for row_index, row in enumerate(rows if isinstance(rows, (tuple, list)) else ()):
        if not isinstance(row, (tuple, list)) or not row:
            problems.append(f"sheet row {row_index}: missing native sheet view")
            inventory.append({"row_index": row_index, "row_raw_none": row is None})
            continue
        sheet_record: dict[str, Any] = {"row_index": row_index}
        sheet_view = observe(
            sheet_record, "sheet_view_bind", lambda: _early_bound(row[0], "IView"), native=True
        )
        sheet = missing
        if sheet_view is not missing and sheet_view is not None:
            sheet = observe(sheet_record, "sheet", lambda: view_name(adapter, sheet_view))
        actual_row_sheets.append(sheet)
        for view_index, raw_view in enumerate(row):
            record = dict(sheet_record, view_index=view_index, is_sheet_view=view_index == 0, dimensions=[])
            if "errors" in record:
                record["errors"] = list(record["errors"])
            inventory.append(record)
            view = observe(
                record, "view_bind", lambda: _early_bound(raw_view, "IView"), native=True
            )
            if view is missing or view is None:
                problems.append(f"sheet row {row_index} view {view_index}: null/unavailable view")
                continue
            observe(record, "view", lambda: view_name(adapter, view))
            if view_index != 0:
                actual_views.append(record)
                observe(record, "configuration", lambda: view.ReferencedConfiguration)
                source = observe(record, "source", lambda: view.ReferencedDocument, native=True)
                if source is not missing and source is not None:
                    source_model = observe(
                        record, "source_bind", lambda: _early_bound(source, "IModelDoc2"), native=True
                    )
                    if source_model is not missing and source_model is not None:
                        observe(record, "source_path", lambda: source_model.GetPathName())
            displays = observe(record, "displays", lambda: view.GetDisplayDimensions(), native=True)
            if displays is missing:
                continue
            record["raw_none"] = displays is None
            if displays is not None and not isinstance(displays, (tuple, list)):
                problems.append(f"sheet row {row_index} view {view_index}: malformed display array")
                record["malformed_display_array"] = {
                    "type": type(displays).__name__, "repr": repr(displays)[:120],
                }
                continue
            record["count"] = 0 if displays is None else len(displays)
            for display_index, raw_display in enumerate(displays if displays is not None else ()):
                item: dict[str, Any] = {"display_index": display_index, "label_is_same": {}}
                record["dimensions"].append(item)
                all_dimensions.append(item)
                display = observe(
                    item, "display_bind", lambda: _early_bound(raw_display, "IDisplayDimension"), native=True
                )
                if display is missing or display is None:
                    problems.append("actual display dimension is null or unavailable")
                    continue
                observe(item, "selection_name", lambda: display.GetNameForSelection())
                raw_annotation = observe(item, "annotation", lambda: display.GetAnnotation(), native=True)
                if raw_annotation is not missing and raw_annotation is not None:
                    annotation = observe(
                        item, "annotation_bind", lambda: _early_bound(raw_annotation, "IAnnotation"), native=True
                    )
                    if annotation is not missing and annotation is not None:
                        observe(item, "annotation_name", lambda: annotation.GetName())
                        observe(item, "owner_type", lambda: _native_integer(annotation.OwnerType, "OwnerType"))
                        owner = observe(item, "owner", lambda: annotation.Owner, native=True)
                        if owner is not missing and owner is not None:
                            if item.get("owner_type") == 0:
                                observe(item, "owner", lambda: view_name(adapter, owner))
                            elif item.get("owner_type") == 1:
                                sheet_owner = observe(
                                    item, "sheet_owner_bind", lambda: _early_bound(owner, "ISheet"), native=True
                                )
                                if sheet_owner is not missing and sheet_owner is not None:
                                    observe(item, "owner", lambda: sheet_owner.GetName())
                            if app is not missing and app is not None:
                                same(item, "owner_is_same", owner, view)
                        if app is not missing and app is not None:
                            for label in labels:
                                if label in originals:
                                    equality = same(item["label_is_same"], label, annotation, originals[label])
                                    if equality == 1:
                                        matches[label].append({"view": record, "dimension": item, "native_view": view})
                    else:
                        problems.append("actual native annotation binding is unavailable")
                else:
                    problems.append("actual display has no native annotation")
                native_dimension = observe(
                    item, "native_dimension", lambda: display.GetDimension2(0), native=True
                )
                if native_dimension is missing or native_dimension is None:
                    problems.append("actual display has no native dimension")
                    continue
                dimension = observe(
                    item, "dimension_bind", lambda: _early_bound(native_dimension, "IDimension"), native=True
                )
                if dimension is not missing and dimension is not None:
                    observe(item, "full_name", lambda: dimension.FullName)
                else:
                    problems.append("actual native dimension binding is unavailable")

    require(
        len(actual_row_sheets) == len(sheet_names)
        and all(isinstance(name, str) for name in actual_row_sheets)
        and set(actual_row_sheets) == set(sheet_names),
        "all-sheet view rows do not cover the exact saved sheets",
    )
    serialized: dict[str, str] = {}
    evidence["actual_full_names_by_label"] = {
        label: [
            match["dimension"]["full_name"] for match in matches[label]
            if "full_name" in match["dimension"]
        ]
        for label in labels
    }
    for label in labels:
        evidence["label_match_counts"][label] = len(matches[label])
        require(len(matches[label]) == 1, f"{label}: original annotation census must be exactly 1")
        if len(matches[label]) != 1:
            continue
        match = matches[label][0]
        record, item = match["view"], match["dimension"]
        captured = expected[label]
        require(
            not record["is_sheet_view"] and record.get("view") == captured.get("owner")
            and record.get("sheet") == captured.get("sheet")
            and record.get("configuration") == captured.get("configuration")
            and all(key in captured for key in ("owner", "sheet", "configuration")),
            f"{label}: captured view/sheet/configuration changed",
        )
        require(
            sum(view.get("view") == captured.get("owner") for view in actual_views) == 1,
            f"{label}: captured view name is not unique in actual drawing",
        )
        require(
            item.get("owner_type") == 0 and not isinstance(item.get("owner_type"), bool)
            and isinstance(item.get("owner_type"), int) and item.get("owner_is_same") == 1
            and item.get("owner") == captured.get("owner"),
            f"{label}: annotation must have the exact native view owner (OwnerType=0, IsSame=1)",
        )
        original_owner = original_owners.get(label, missing)
        if original_owner is missing or original_owner is None or app is missing or app is None:
            problems.append(f"{label}: original native owner is unavailable")
        else:
            require(
                same(captured, "owner_is_same", original_owner, match["native_view"]) == 1
                and captured.get("owner_type") == 0
                and isinstance(captured.get("owner_type"), int)
                and not isinstance(captured.get("owner_type"), bool),
                f"{label}: original native owner changed",
            )
        source_path = record.get("source_path")
        require(
            isinstance(source_path, str) and bool(source_path) and Path(source_path).is_absolute(),
            f"{label}: matched view has no actual source document path",
        )
        full_name = item.get("full_name")
        if "full_name" in item:
            evidence["expected_serialized_full_names"][label] = full_name
        require(isinstance(full_name, str) and bool(full_name), f"{label}: native FullName is empty or malformed")
        if isinstance(full_name, str) and full_name:
            serialized[label] = full_name
            require(
                sum(other.get("full_name") == full_name for other in all_dimensions) == 1,
                f"{label}: serialized FullName is not unique in actual drawing",
            )
    require(
        len(serialized) == 2 and len(set(serialized.values())) == 2,
        "physical references require two distinct actual serialized FullNames",
    )
    evidence["problems"] = problems
    boundary = {
        key: evidence[key] for key in ("document_path", "document_title", "document_type")
        if key in evidence
    }
    for record in inventory:
        _telemetry.event(
            "drawing.physical_axial_identity_inventory",
            phase=evidence["phase"], **boundary, **record,
        )
    if errors or problems:
        stage, cause = errors[0] if errors else ("identity_predicates", RuntimeError("; ".join(problems)))
        evidence.update(failure_stage=stage, failure_error_type=type(cause).__name__, failure_error=str(cause)[:500])
        _telemetry.event("drawing.physical_axial_serialized_identity", status="refused", **evidence)
        raise RuntimeError(f"serialized physical identity capture refused; native_snapshot={evidence!r}") from cause
    _telemetry.event("drawing.physical_axial_serialized_identity", status="captured", **evidence)
    return serialized
