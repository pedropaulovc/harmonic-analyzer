"""TEMPORARY issue1667 farm experiment, not a production recovery abstraction.

Imported only after the baseline miss AND its unchanged first raw repeat. Reads
are observers, not inert: COM reads, imports and logging can all change timing.
No arm result is returned as a usable edge; the caller must fail the original miss.
"""

from __future__ import annotations

import contextlib
import json
import time
from typing import Any, Callable, Mapping, Sequence

from solidworks_mcp.adapters.pywin32_adapter import null_callout

from _com import _bind, _com_invoke, _early_bound
from _drawing_projection import _project_through, model_points_in_view
from _drawing_scan import _HIT_ZOOM_HALF
import _telemetry


def _emit(stage: str, stem: str, record: Mapping[str, Any]) -> None:
    """Persist every completed arm immediately, independently of the final report."""
    payload = json.dumps(record, default=str, sort_keys=True)
    fields = {
        key: value
        for key, value in record.items()
        if isinstance(value, (bool, int, float, str))
    }
    with contextlib.suppress(Exception):
        _telemetry.event(
            f"drawing.pick_diagnostic.{stage}",
            label=stem,
            diagnostic=payload,
            **fields,
        )
    with contextlib.suppress(Exception):
        _telemetry.warn(
            f"[1667 diagnostic] {stage} {payload}",
            label=stem,
            diagnostic=payload,
            **fields,
        )


def _read(record: dict[str, Any], key: str, probe: Callable[[], Any]) -> Any:
    started = time.perf_counter()
    try:
        value = probe()
        record[key] = value
        return value
    except Exception as exc:  # noqa: BLE001 - preserve the original failed pick
        record[f"{key}_error"] = f"{type(exc).__name__}: {exc}"
        return None
    finally:
        record[f"{key}_read_ms"] = (time.perf_counter() - started) * 1000.0


def _array(obj: Any, interface: str) -> tuple[float, ...]:
    if obj is None:
        raise RuntimeError(f"{interface} is null")
    values = _com_invoke(obj, interface, "ArrayData")
    if values is None:
        raise RuntimeError(f"{interface}.ArrayData is null")
    return tuple(float(value) for value in values)


def _view_name(view: Any) -> str:
    # ActiveDrawingView returns null when the sheet, rather than a view, is active.
    return "<sheet-or-no-active-view>" if view is None else str(
        _com_invoke(view, "IView", "GetName2")
    )


def _active_view_name(draw: Any) -> str:
    return _view_name(_com_invoke(draw, "IDrawingDoc", "ActiveDrawingView"))


def _selection(draw: Any) -> dict[str, Any]:
    """These observations happen AFTER the raw pick result was already emitted."""
    state: dict[str, Any] = {}
    manager = _read(state, "manager", lambda: _com_invoke(draw, "IModelDoc2", "SelectionManager"))
    # Never serialize COM proxies, even when an accessor returns one successfully.
    state.pop("manager", None)
    count = _read(
        state, "selected_count",
        lambda: int(_com_invoke(manager, "ISelectionMgr", "GetSelectedObjectCount2", -1)),
    )
    if count is None:
        return state
    state["selected_details_truncated"] = count > 8
    for index in range(1, min(count, 8) + 1):
        key = f"selected{index}"
        kind = _read(
            state, f"{key}_type",
            lambda i=index: int(_com_invoke(manager, "ISelectionMgr", "GetSelectedObjectType3", i, -1)),
        )
        _read(
            state, f"{key}_drawing_view",
            lambda i=index: _view_name(_com_invoke(manager, "ISelectionMgr", "GetSelectedObjectsDrawingView2", i, -1)),
        )
        if kind in (1, 2, 3):  # swSelEDGES, swSelFACES, swSelVERTICES
            def owner(i: int = index) -> str:
                entity = _com_invoke(manager, "ISelectionMgr", "GetSelectedObject6", i, -1)
                bound = _early_bound(_bind(entity, "IEntity"), "IEntity")
                component = bound.GetComponent()
                return "" if component is None else str(
                    _com_invoke(component, "IComponent2", "Name2")
                ).replace("\\", "/")

            _read(state, f"{key}_owner", owner)
        else:
            state[f"{key}_owner_unavailable"] = "not EDGE/FACE/VERTEX; no IEntity cast attempted"
    return state


def _client_geometry(hwnd: int) -> dict[str, Any]:
    # The module itself is deferred; even ctypes startup is after the raw repeat.
    import ctypes
    from ctypes import wintypes

    if not hwnd:
        raise RuntimeError("IModelView.GetViewHWndx64 returned a null HWND")
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.GetClientRect.restype = wintypes.BOOL
    user32.ClientToScreen.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
    user32.ClientToScreen.restype = wintypes.BOOL
    state: dict[str, Any] = {"hwnd": hwnd, "units": "device pixels"}

    def client_rect() -> tuple[int, int, int, int]:
        rect = wintypes.RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            raise ctypes.WinError(ctypes.get_last_error())
        return rect.left, rect.top, rect.right, rect.bottom

    def screen_origin() -> tuple[int, int]:
        point = wintypes.POINT(0, 0)
        if not user32.ClientToScreen(hwnd, ctypes.byref(point)):
            raise RuntimeError("ClientToScreen returned False")
        return point.x, point.y

    _read(state, "client_rect_px", client_rect)
    _read(state, "client_screen_origin_px", screen_origin)
    return state


def _viewport(draw: Any) -> dict[str, Any]:
    state: dict[str, Any] = {}
    viewport = _read(state, "active_model_view", lambda: _com_invoke(draw, "IModelDoc2", "ActiveView"))
    state.pop("active_model_view", None)
    for member in ("Scale2", "EnableGraphicsUpdate", "FrameLeft", "FrameTop", "FrameWidth", "FrameHeight", "FrameState"):
        _read(state, member, lambda m=member: _com_invoke(viewport, "IModelView", m))
    for member, interface in (("Transform", "IMathTransform"), ("Orientation3", "IMathTransform"), ("Translation3", "IMathVector")):
        _read(
            state, f"{member}_array",
            lambda m=member, i=interface: _array(_com_invoke(viewport, "IModelView", m), i),
        )
    hwnd = _read(
        state, "hwnd",
        lambda: int(_early_bound(_bind(viewport, "IModelView"), "IModelView").GetViewHWndx64()),
    )
    if hwnd is not None:
        _read(state, "client_geometry", lambda: _client_geometry(hwnd))
    return state


def collect_after_raw_repeat(
    adapter: Any,
    view: Any,
    *,
    sheet_xy: Sequence[float],
    stem: str,
    instance: str,
    point_mm: Sequence[float],
    projection_inputs: Mapping[str, Any] | None,
    repeat: Mapping[str, Any],
    baseline_scale2: float | None,
    activation_view_name: str | None,
) -> dict[str, Any]:
    """A bounded, ordered experiment; all results remain diagnostic failures."""
    draw = adapter.currentModel
    report: dict[str, Any] = {
        "baseline_failure_preserved": True,
        "instrumented_not_timing_equivalent": True,
        "prebaseline_new_COM_reads": 0,
        "baseline_selection_state_unavailable": "not read, to preserve raw-repeat control",
        "baseline_active_view_unavailable": "not read until after the first raw repeat",
        "original_view_transform_unavailable": "ArrayData not read before baseline",
        "original_viewport_transform_unavailable": "not read before baseline",
        "original_projection_inputs": dict(projection_inputs or {}),
        "original_sheet_xy_m": tuple(sheet_xy),
        "original_point_mm": tuple(point_mm),
        "intended_instance": instance,
        "original_activation_view_name": activation_view_name,
        "fresh_explode_unavailable": "retained existing offsets only; explode reads can mutate state",
        "projection_frame": "original component Transform2 plus retained explode; neither re-read",
        "prebaseline_existing_mutators": "ActivateView then UpdateViewDisplayGeometry while unzoomed",
        "observer_effect_warning": "state reads, selection inspection, imports and logs may heal or delay COM",
        "causality_warning": "sequential cumulative arms are not isolated or reversible A/B tests",
        "historical_redraw_confounds": "same API, not historical fit/rezoom/capture sequence",
        "arms": [],
    }
    arms: list[dict[str, Any]] = report["arms"]
    healed_by = ""
    history: list[str] = [str(repeat["arm"])]

    def inspect(record: dict[str, Any]) -> None:
        _read(record, "selection", lambda: _selection(draw))
        _read(record, "active_drawing_view_after_pick", lambda: _active_view_name(draw))
        _emit("arm", stem, record)

    def pick(arm: str, *, mutators: Sequence[tuple[str, Callable[[], Any]]] = (), entity_type: str = "EDGE", xy: Sequence[float] = sheet_xy) -> dict[str, Any]:
        record: dict[str, Any] = {
            "arm": arm, "prior_arms": tuple(history), "entity_type": entity_type,
            "sheet_xy_m": tuple(xy), "baseline_scale2": baseline_scale2,
            "baseline_failure_preserved": True,
            "prior_edge_success": healed_by or "<none>",
        }
        arms.append(record)
        history.append(arm)
        try:
            draw.ClearSelection2(True)
            for name, mutate in mutators:
                _read(record, name, mutate)
            if mutators:
                # Same accessor as the existing baseline read, now AFTER each
                # intervention. This read is itself an observer before the pick.
                scale = _read(record, "scale2_after_mutator", lambda: float(draw.ActiveView.Scale2))
                if scale is not None and baseline_scale2 is not None:
                    record["scale2_delta_from_baseline"] = scale - baseline_scale2
            extension = draw.Extension
            callout = null_callout()
            started = time.perf_counter()
            try:
                record["select_result"] = bool(extension.SelectByID2(
                    "", entity_type, xy[0], xy[1], 0.0, False, 0, callout, 0
                ))
            finally:
                record["select_ms"] = (time.perf_counter() - started) * 1000.0
        except Exception as exc:  # noqa: BLE001 - an arm cannot replace baseline failure
            record["arm_error"] = f"{type(exc).__name__}: {exc}"
        _emit("raw", stem, record)  # BEFORE count/type/owner/active-view reads
        inspect(record)
        return record

    def note_hit(record: Mapping[str, Any]) -> None:
        nonlocal healed_by
        if not record.get("select_result") or healed_by:
            return
        if record.get("entity_type") == "":
            selected = record.get("selection") or {}
            if not any(
                value == 1
                and str(selected.get(f"{key.removesuffix('_type')}_owner", "")).casefold()
                == instance.casefold()
                for key, value in selected.items()
                if key.startswith("selected") and key.endswith("_type")
            ):
                report["typeless_nonedge_wrong_owner_or_unknown_hit"] = True
                # This selection is still an intervention in later arms' history,
                # but a FACE/VERTEX hit is not healing the original EDGE miss.
                return
        healed_by = str(record["arm"])
        report["first_nonempty_edge_arm"] = healed_by
        report["stop_reason"] = "EDGE selection succeeded; not proof of intended owner or cause"
        # Selection/active-view observers have already run; this is a plain pick
        # without an explicit mutator, not a claim that those reads were inert.
        pick(f"persistence_after_observer_reads_of_{healed_by}")

    first_repeat = dict(repeat)
    arms.append(first_repeat)
    inspect(first_repeat)  # first new state reads follow the already emitted raw repeat
    note_hit(first_repeat)

    snapshot: dict[str, Any] = {}
    report["observer_snapshot"] = snapshot
    _read(snapshot, "intended_drawing_view", lambda: _view_name(view))
    _read(snapshot, "active_drawing_view_before_clear", lambda: _active_view_name(draw))
    _read(snapshot, "clear_before_state", lambda: draw.ClearSelection2(True))
    _read(snapshot, "active_drawing_view_after_clear", lambda: _active_view_name(draw))
    _read(snapshot, "selection_after_clear", lambda: _selection(draw))
    _read(snapshot, "selection_filters_applied", lambda: bool(_com_invoke(adapter.swApp, "ISldWorks", "GetApplySelectionFilter")))
    _read(snapshot, "selection_filters", lambda: tuple(int(v) for v in (_com_invoke(adapter.swApp, "ISldWorks", "GetSelectionFilters") or ())))
    _read(snapshot, "edge_selection_filter", lambda: bool(_com_invoke(adapter.swApp, "ISldWorks", "GetSelectionFilter", 1)))
    _read(snapshot, "viewport", lambda: _viewport(draw))
    _read(snapshot, "drawing_view_transform_array", lambda: _array(_com_invoke(view, "IView", "ModelToViewTransform"), "IMathTransform"))
    _read(snapshot, "drawing_view_outline_m", lambda: tuple(float(v) for v in (_com_invoke(view, "IView", "GetOutline") or ())))
    _emit("observers", stem, snapshot)

    def reactivate() -> bool:
        if activation_view_name is None:
            raise RuntimeError("original pre-pick ActivateView string unavailable")
        return bool(_com_invoke(draw, "IDrawingDoc", "ActivateView", activation_view_name))

    note_hit(pick("raw_repeat_after_observers"))
    mutator_arms: Sequence[tuple[str, Sequence[tuple[str, Callable[[], Any]]]]] = (
        ("historical_GraphicsRedraw2_under_zoom", (("GraphicsRedraw2", lambda: draw.GraphicsRedraw2()),)),
        ("refresh_display_geometry_under_zoom", (("UpdateViewDisplayGeometry", lambda: _com_invoke(view, "IView", "UpdateViewDisplayGeometry")),)),
        ("reactivate_view_under_zoom", (("ActivateView", reactivate),)),
        ("reactivate_and_refresh_under_zoom", (
            ("ActivateView", reactivate),
            ("UpdateViewDisplayGeometry", lambda: _com_invoke(view, "IView", "UpdateViewDisplayGeometry")),
        )),
    )
    if not healed_by:
        note_hit(pick("typeless_after_observers", entity_type=""))
    else:
        record = {"arm": "typeless_after_observers", "not_run": f"selection_succeeded_{healed_by}"}
        arms.append(record)
        _emit("arm", stem, record)
    for arm, mutators in mutator_arms:
        if healed_by:
            record = {"arm": arm, "not_run": f"selection_succeeded_{healed_by}"}
            arms.append(record)
            _emit("arm", stem, record)
        else:
            note_hit(pick(arm, mutators=mutators))

    corner = (sheet_xy[0] + 0.9 * _HIT_ZOOM_HALF, sheet_xy[1] + 0.9 * _HIT_ZOOM_HALF)
    control = pick("empty_candidate_original_zoom_corner", xy=corner)
    control["empty_status"] = "candidate only; no independent rendered-emptiness evidence"
    report["empty_control"] = control
    _emit("empty_control", stem, control)

    # Projection is intentionally AFTER all arms; geometry/anchors are never moved.
    projection: dict[str, Any] = {
        "read_phase": "post_arms",
        "non_atomic_reads": True,
        "pixel_frame_warning": (
            "Win32 device-pixel/SOLIDWORKS screen-pixel DPI equivalence "
            "is not independently established"
        ),
    }
    report["post_arms_projection"] = projection
    original_points = (projection_inputs or {}).get("model_points_m")
    if original_points:
        fresh = _read(
            projection,
            "fresh_sheet_xy_m",
            lambda: model_points_in_view(
                adapter,
                view,
                [original_points[0]],
                label=f"{stem} issue1667 post_arms projection",
            )[0],
        )
        if fresh is not None:
            projection["sheet_delta_m"] = tuple(fresh[i] - sheet_xy[i] for i in range(2))
    else:
        projection["fresh_projection_unavailable"] = "original model point was not retained"
    _read(
        projection,
        "current_drawing_transform_array",
        lambda: _array(
            _com_invoke(view, "IView", "ModelToViewTransform"), "IMathTransform"
        ),
    )
    _read(projection, "viewport", lambda: _viewport(draw))
    utility = _read(
        projection,
        "math_utility",
        lambda: _com_invoke(adapter.swApp, "ISldWorks", "GetMathUtility"),
    )
    projection.pop("math_utility", None)
    transform = _read(
        projection,
        "viewport_transform",
        lambda: _com_invoke(
            _com_invoke(draw, "IModelDoc2", "ActiveView"), "IModelView", "Transform"
        ),
    )
    projection.pop("viewport_transform", None)
    _read(
        projection,
        "baseline_point_current_viewport_px",
        lambda: _project_through(
            utility, transform, (*sheet_xy, 0.0), label="baseline point current viewport"
        ),
    )
    corner_px = _read(
        projection,
        "empty_candidate_current_viewport_px",
        lambda: _project_through(
            utility, transform, (*corner, 0.0), label="empty candidate current viewport"
        ),
    )
    rect = projection.get("viewport", {}).get("client_geometry", {}).get("client_rect_px")
    if corner_px is not None and rect is not None:
        projection["empty_candidate_inside_current_client"] = (
            rect[0] <= corner_px[0] < rect[2] and rect[1] <= corner_px[1] < rect[3]
        )
    _emit("projection", stem, projection)
    _read(report, "final_clear", lambda: draw.ClearSelection2(True))
    return report
