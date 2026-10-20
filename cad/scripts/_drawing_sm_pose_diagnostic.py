"""TEMPORARY issue1667 fixed-point viewport experiment; never a recovery path.

Imported only inside the original pick zoom, after the baseline (and a miss's
immediate unchanged raw repeat). Every observation is post-pick, non-atomic,
and potentially perturbing. This module always stops the drawing before save.
"""

from __future__ import annotations

import contextlib
from contextvars import ContextVar
from datetime import UTC, datetime
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import time
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

import numpy as np
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks import drawing as sw_drawing

from _com import _bind, _com_invoke, _early_bound
from _drawing_scan import _HIT_ZOOM_HALF, _zoomed_on
import _telemetry
import sm_knife_mount_spec as mount_spec
import sm_summing_lever_spec as lever_spec

STOP = "ISSUE1667_POSE_DIAGNOSTIC_STOP"
PRIORITY = (
    "controlY",
    "leverNear",
    "leverFarMidrib",
    "controlX",
    "leverPlateEnd",
    "leverPad",
    "controlZ",
)
PAD_CONTROL_OFFSET_M = 8e-6
DISCOVERY_SECONDS = 60.0
STUDY_SECONDS = 180.0
OPTIONAL_OBSERVATION_SECONDS = 15.0
PICK_CAP = 112
BLOCKS = (("A", "B", "A", "C", "A", "D", "A"), ("A", "D", "A", "C", "A", "B", "A"))
SHIFTS = {"A": (0.0, 0.0), "B": (0.25, 0.25), "C": (-0.25, -0.25), "D": (1.0, 1.0)}
ACHIEVED_TOLERANCE = 0.01
A_RESTORATION_TOLERANCE = 1e-6
PATH_LIMIT_UTF16 = 240  # Conservative budget, including the checkpoint temp.
EDGE_CAP = 1024
COMPONENT_CAP = 128
# v3.12.1 enums/swSelectType_e.md:672,896; documented return interface IView.
DRAWING_VIEW_SELECTION_TYPE = 12
SOURCE_TOLERANCE_M = 5e-6
TRANSFORM_TOLERANCE_M = 1e-10
SCALE_RELATIVE_TOLERANCE = 1e-8
MATRIX_STABILITY_TOLERANCE = 1e-10
FAILURES = Path(__file__).resolve().parents[1] / "out" / "reports" / "failures"
_PERFORMANCE: ContextVar[dict[str, Any] | None] = ContextVar(
    "sm1667_costs", default=None
)
_SPAN_EVENTS: ContextVar[dict[str, Any] | None] = ContextVar(
    "sm1667_events", default=None
)


class _Nonfinite(ValueError):
    """Invalid numerical evidence must not become an unavailable observer."""


def _cost(name: str, elapsed_ms: float) -> None:
    performance = _PERFORMANCE.get()
    if performance is not None:
        row = performance["costs"].setdefault(name, {"calls": 0, "total_ms": 0.0})
        row["calls"] += 1
        row["total_ms"] += elapsed_ms


def _count(name: str, count: int = 1) -> None:
    performance = _PERFORMANCE.get()
    if performance is not None:
        counts = performance["operation_counts"]
        counts[name] = counts.get(name, 0) + count


@contextlib.contextmanager
def _timed(name: str):
    started = time.perf_counter()
    try:
        yield
    finally:
        _cost(name, (time.perf_counter() - started) * 1000)


def _native_call(obj: Any, interface: str, member: str, *args: Any) -> Any:
    _count(f"{interface}.{member}")
    category = (
        "raw_selection"
        if member == "SelectByID2"
        else "selection_cleanup"
        if member == "ClearSelection2"
        else "explicit_initial_fit"
        if member == "ViewZoomtofit2"
        else "native_controls_observers"
    )
    with _timed(category):
        return _com_invoke(obj, interface, member, *args)


def _stamp() -> dict[str, Any]:
    return {
        "utc": datetime.now(UTC).isoformat(),
        "monotonic_ns": time.perf_counter_ns(),
    }


def _error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


class _Deadline(Exception):
    pass


class _Budget:
    """SOFT between-call deadline, not an interrupt for a hung native call."""

    def __init__(self, seconds: float) -> None:
        self.start = time.perf_counter()
        self.seconds = seconds
        self.calls = 0
        self.last_checkpoint: dict[str, Any] = {}

    def check(self, member: str) -> None:
        elapsed = time.perf_counter() - self.start
        self.last_checkpoint = {"member": member, "elapsed_s": elapsed, **_stamp()}
        if elapsed >= self.seconds:
            raise _Deadline(f"soft deadline {self.seconds:g}s before {member}")

    def call(self, obj: Any, interface: str, member: str, *args: Any) -> Any:
        self.check(f"{interface}.{member}")
        self.calls += 1
        return _native_call(obj, interface, member, *args)

    def report(self) -> dict[str, Any]:
        return {
            "soft_limit_s": self.seconds,
            "elapsed_s": time.perf_counter() - self.start,
            "calls": self.calls,
            "last_checkpoint": self.last_checkpoint,
            "hung_COM_call_not_interrupted": True,
        }


def _invoke(
    budget: _Budget | None, obj: Any, interface: str, member: str, *args: Any
) -> Any:
    return (
        budget.call(obj, interface, member, *args)
        if budget is not None
        else _native_call(obj, interface, member, *args)
    )


def _numbers(budget: _Budget | None, obj: Any, interface: str) -> tuple[float, ...]:
    if obj is None:
        raise RuntimeError(f"{interface} handle is null")
    values = _invoke(budget, obj, interface, "ArrayData")
    if values is None:
        raise RuntimeError(f"{interface}.ArrayData is null")
    numbers = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in numbers):
        raise _Nonfinite(f"{interface}.ArrayData contains nonfinite values")
    return numbers


def _observe(record: dict[str, Any], key: str, probe: Callable[[], Any]) -> Any:
    field: dict[str, Any] = {"begin": _stamp(), "stage": "post_pick_non_atomic"}
    record[key] = field
    try:
        value = probe()
        if value is None:
            field.update(status="unavailable", reason="native accessor returned null")
        else:
            field.update(status="available", value=value)
        return value
    except _Deadline:
        field.update(status="unavailable", reason="soft deadline before native call")
        raise
    except (_Nonfinite, TypeError, AssertionError):
        raise
    except Exception as exc:
        field.update(status="error", error=_error(exc))
        return None
    finally:
        field["end"] = _stamp()


def _value(record: Mapping[str, Any], key: str) -> Any:
    return record.get(key, {}).get("value")


def _event(stage: str, report: Mapping[str, Any], **fields: Any) -> None:
    # Count API submissions, not exporter retention; compare with serialized spans.
    started = time.perf_counter()
    try:
        _telemetry.event(
            f"drawing.sm_pose.{stage}", probe_id=report["probe_id"], **fields
        )
        counter = _SPAN_EVENTS.get()
        if counter is not None:
            counter["emitted_event_count"] += 1
    except Exception:
        counter = _SPAN_EVENTS.get()
        if counter is not None:
            counter["event_submission_errors"] += 1
    finally:
        _cost("telemetry_emission", (time.perf_counter() - started) * 1000)


def _native_point(
    utility: Any, transform: Any, point: Sequence[float], budget: _Budget | None = None
) -> tuple[float, ...]:
    native = _invoke(
        budget, utility, "IMathUtility", "CreatePoint", double_array(list(point))
    )
    if native is None:
        raise RuntimeError("CreatePoint returned null")
    result = _invoke(budget, native, "IMathPoint", "MultiplyTransform", transform)
    coordinates = _numbers(budget, result, "IMathPoint")
    if not all(math.isfinite(v) for v in coordinates):
        raise _Nonfinite("MultiplyTransform returned nonfinite coordinates")
    if len(coordinates) != 3:
        raise RuntimeError("MultiplyTransform returned incomplete coordinates")
    return coordinates


def _linear(values: Sequence[float]) -> np.ndarray:
    # Existing _drawing_balloons._anchor_model_points and
    # draw_fr_frame_assembly._transform_point use THIS layout including scale.
    # IMathTransform.ArrayData docs: rotation[0:9], translation[9:12], scale[12].
    data = np.asarray(values, dtype=float)
    if not np.isfinite(data).all():
        raise _Nonfinite("MathTransform contains nonfinite values")
    if data.shape != (16,) or not np.isfinite(data).all() or data[12] == 0:
        raise ValueError(
            "MathTransform must contain 16 finite values and nonzero scale"
        )
    return data[:9].reshape(3, 3).T * data[12]


def _apply(values: Sequence[float], point: Sequence[float]) -> np.ndarray:
    return _linear(values) @ np.asarray(point, dtype=float) + np.asarray(values[9:12])


def _verified_transform(
    utility: Any, transform: Any, point: Sequence[float], budget: _Budget | None = None
) -> dict[str, Any]:
    """Fresh-handle metrology control, NOT a historical-immutability claim."""
    result: dict[str, Any] = {
        "begin": _stamp(),
        "valid": False,
        "layout_source": "_drawing_balloons._anchor_model_points; draw_fr_frame_assembly._transform_point",
        "absolute_tolerance_output_units": TRANSFORM_TOLERANCE_M,
        "non_atomic": True,
        "historical_immutability_proven": False,
    }
    before = _numbers(budget, transform, "IMathTransform")
    result["array"] = before
    # One recorded point plus a full 3D affine basis discriminates transpose,
    # missing scale and translation. Fixed-size positive control, no searching.
    points = [
        tuple(point),
        (0.0, 0.0, 0.0),
        (0.001, 0.0, 0.0),
        (0.0, 0.001, 0.0),
        (0.0, 0.0, 0.001),
    ]
    result["samples"] = []
    for sample in points:
        native = _native_point(utility, transform, sample, budget)
        analytic = _apply(before, sample)
        discrepancy = float(np.max(np.abs(analytic - native)))
        result["samples"].append(
            {
                "input": sample,
                "native": native,
                "analytical": analytic.tolist(),
                "max_absolute_disagreement": discrepancy,
            }
        )
    after = _numbers(budget, transform, "IMathTransform")
    result["array_after_control"] = after
    result["handle_array_stable_during_control"] = _bits(before) == _bits(after)
    result["valid"] = result["handle_array_stable_during_control"] and all(
        sample["max_absolute_disagreement"] <= TRANSFORM_TOLERANCE_M
        for sample in result["samples"]
    )
    result["end"] = _stamp()
    return result


def _selected(
    draw: Any, budget: _Budget | None = None, *, adapter: Any = None, view: Any = None
) -> tuple[dict[str, Any], Any, Any]:
    """Read before clear; accept only preregistered coordinate-EDGE patterns."""
    record: dict[str, Any] = {
        "stage": "post_raw_before_any_clear",
        "begin": _stamp(),
        "items": [],
    }
    manager = _observe(
        record,
        "manager",
        lambda: _invoke(budget, draw, "IModelDoc2", "SelectionManager"),
    )
    if manager is not None:
        record["manager"]["value"] = "ISelectionMgr handle retained locally"
    count = _observe(
        record,
        "count",
        lambda: int(
            _invoke(budget, manager, "ISelectionMgr", "GetSelectedObjectCount2", -1)
        ),
    )
    record["all_selection_items_recorded"] = count == 0
    record["selection_observer_max_items"] = 9
    entity = owner = None
    handles = {}
    if count and count > 0:
        # Existing drawing convention reads the final edge first. Record every
        # item for canonical patterns; unexpected lists remain bounded/rejected.
        indices = list(dict.fromkeys([count, *range(1, min(count, 8) + 1)]))
        for index in indices:
            item: dict[str, Any] = {"index": index}
            kind = _observe(
                item,
                "type",
                lambda i=index: int(
                    _invoke(
                        budget,
                        manager,
                        "ISelectionMgr",
                        "GetSelectedObjectType3",
                        i,
                        -1,
                    )
                ),
            )
            selected = _observe(
                item,
                "entity",
                lambda i=index: _invoke(
                    budget, manager, "ISelectionMgr", "GetSelectedObject6", i, -1
                ),
            )
            handles[index] = selected
            if selected is not None:
                item["entity"]["value"] = (
                    "selected native entity handle retained locally"
                )
            record["items"].append(item)
            if index == count:
                record["type"], record["entity"] = item["type"], item["entity"]
                entity = selected
                if kind in (1, 2, 3) and entity is not None:
                    if budget is not None:
                        budget.check("selected IEntity.GetComponent binding")
                    owner = _observe(
                        record,
                        "owner_handle",
                        lambda: _invoke(
                            budget,
                            _early_bound(_bind(entity, "IEntity"), "IEntity"),
                            "IEntity",
                            "GetComponent",
                        ),
                    )
                    if owner is not None:
                        record["owner_handle"]["value"] = (
                            "IComponent2 handle retained locally"
                        )
                    _observe(
                        record,
                        "owner",
                        lambda: (
                            str(_invoke(budget, owner, "IComponent2", "Name2")).replace(
                                "\\", "/"
                            )
                            if owner is not None
                            else None
                        ),
                    )
        record["items"].sort(key=lambda item: item["index"])
        record["all_selection_items_recorded"] = len(record["items"]) == count
    first = next((item for item in record["items"] if item["index"] == 1), {})
    if count == 2:
        _observe(
            record,
            "IsSame_first_active_drawing_view_telemetry_only",
            lambda: int(
                _invoke(
                    budget, adapter.swApp, "ISldWorks", "IsSame", handles.get(1), view
                )
            ),
        )
        _observe(
            record,
            "IsSame_expected_view_self_telemetry_only",
            lambda: int(
                _invoke(budget, adapter.swApp, "ISldWorks", "IsSame", view, view)
            ),
        )
        _observe(
            record,
            "IsSame_first_selected_view_self_telemetry_only",
            lambda: int(
                _invoke(
                    budget,
                    adapter.swApp,
                    "ISldWorks",
                    "IsSame",
                    handles.get(1),
                    handles.get(1),
                )
            ),
        )
        _observe(
            record,
            "expected_view_name",
            lambda: _invoke(budget, view, "IView", "GetName2"),
        )
        if _value(first, "type") == DRAWING_VIEW_SELECTION_TYPE:
            _observe(
                record,
                "first_selected_view_name",
                lambda: _invoke(budget, handles.get(1), "IView", "GetName2"),
            )
        record["view_name_scope"] = (
            "SM recipe: one ordinary non-section model view on fresh exploded sheet; "
            "GetName2 exact-name convention, not a universal section-view identity proof"
        )
        for key in (
            "first_selected_view_name",
            "IsSame_first_active_drawing_view_telemetry_only",
            "IsSame_first_selected_view_self_telemetry_only",
        ):
            if key in record:
                first[key] = record[key]
    for item in record["items"]:
        if item["index"] == count:
            for key in ("owner", "owner_handle"):
                if key in record:
                    item[key] = record[key]
    single = count == 1 and _value(record, "type") == 1
    view_edge = (
        count == 2
        and _value(first, "type") == DRAWING_VIEW_SELECTION_TYPE
        and isinstance(_value(record, "expected_view_name"), str)
        and bool(_value(record, "expected_view_name").strip())
        and _value(record, "first_selected_view_name")
        == _value(record, "expected_view_name")
        and _value(record, "type") == 1
    )
    record["canonical_selection_pattern"] = (
        "single-edge" if single else "view-then-edge" if view_edge else None
    )
    record["canonical_selection_pattern_valid"] = bool(single or view_edge)
    record["end"] = _stamp()
    return record, entity, owner


def _identity(
    adapter: Any,
    selected: dict[str, Any],
    entity: Any,
    owner: Any,
    target: Mapping[str, Any] | None,
    budget: _Budget | None = None,
) -> bool:
    if target is None or entity is None:
        selected["identity_unavailable"] = (
            "no identified intended straight target or selected entity"
        )
        selected["accepted_own_edge"] = False
        return False
    same = _observe(
        selected,
        "IsSame_edge",
        lambda: int(
            _invoke(
                budget, adapter.swApp, "ISldWorks", "IsSame", entity, target["edge"]
            )
        ),
    )
    _observe(
        selected,
        "IsSame_owner_telemetry_only",
        lambda: int(
            _invoke(
                budget, adapter.swApp, "ISldWorks", "IsSame", owner, target["component"]
            )
        ),
    )
    selected["owner_identity_gate"] = (
        "full Name2 path only; component IsSame is unverified telemetry, not a gate"
    )
    accepted = (
        selected.get("canonical_selection_pattern_valid", False)
        and same == 1
        and str(_value(selected, "owner") or "").casefold()
        == target["instance"].casefold()
    )
    selected["accepted_own_edge"] = bool(accepted)
    selected["target_id"] = target["id"]
    for item in selected.get("items", []):
        if item["index"] == _value(selected, "count"):
            item["IsSame_expected_target_edge"] = selected["IsSame_edge"]
            item["IsSame_owner_telemetry_only"] = selected[
                "IsSame_owner_telemetry_only"
            ]
            item["expected_target_id"] = target["id"]
    return bool(accepted)


def _window_geometry(view_hwnd: int, frame_hwnd: int) -> dict[str, Any]:
    """Read-only Win32 registration. No assumed origin, DPI, or bitmap centre."""
    import ctypes
    from ctypes import wintypes

    user = ctypes.WinDLL("user32", use_last_error=True)
    specs = (
        (
            "GetClientRect",
            (wintypes.HWND, ctypes.POINTER(wintypes.RECT)),
            wintypes.BOOL,
        ),
        (
            "ClientToScreen",
            (wintypes.HWND, ctypes.POINTER(wintypes.POINT)),
            wintypes.BOOL,
        ),
        (
            "GetWindowRect",
            (wintypes.HWND, ctypes.POINTER(wintypes.RECT)),
            wintypes.BOOL,
        ),
        ("GetDpiForWindow", (wintypes.HWND,), wintypes.UINT),
        ("GetThreadDpiAwarenessContext", (), wintypes.HANDLE),
        ("GetWindowDpiAwarenessContext", (wintypes.HWND,), wintypes.HANDLE),
        ("GetAwarenessFromDpiAwarenessContext", (wintypes.HANDLE,), ctypes.c_int),
        (
            "GetWindowThreadProcessId",
            (wintypes.HWND, ctypes.POINTER(wintypes.DWORD)),
            wintypes.DWORD,
        ),
    )
    state: dict[str, Any] = {
        "coordinate_units": "Win32 caller-context pixels; device/logical equivalence gated below"
    }
    for name, args, returns in specs:
        try:
            member = getattr(user, name)
            member.argtypes, member.restype = args, returns
        except Exception as exc:
            state[f"{name}_prototype_error"] = _error(exc)

    def rectangle(hwnd: int, client: bool) -> list[int]:
        if not hwnd:
            raise RuntimeError("null window handle")
        rect = wintypes.RECT()
        if not (user.GetClientRect if client else user.GetWindowRect)(
            hwnd, ctypes.byref(rect)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return [rect.left, rect.top, rect.right, rect.bottom]

    def origin() -> list[int]:
        if not view_hwnd:
            raise RuntimeError("null view handle")
        point = wintypes.POINT(0, 0)
        if not user.ClientToScreen(view_hwnd, ctypes.byref(point)):
            raise ctypes.WinError(ctypes.get_last_error())
        return [point.x, point.y]

    def dpi(hwnd: int) -> int:
        if not hwnd:
            raise RuntimeError("null window handle")
        value = int(user.GetDpiForWindow(hwnd))
        if value == 0:
            raise RuntimeError("GetDpiForWindow returned 0")
        return value

    def awareness(hwnd: int | None) -> dict[str, int]:
        context = (
            user.GetThreadDpiAwarenessContext()
            if hwnd is None
            else user.GetWindowDpiAwarenessContext(hwnd)
        )
        if not context:
            raise RuntimeError("DPI awareness context unavailable")
        value = int(user.GetAwarenessFromDpiAwarenessContext(context))
        if value < 0:
            raise RuntimeError("DPI awareness invalid")
        return {"context": int(context), "awareness": value}

    def process() -> dict[str, int]:
        pid = wintypes.DWORD()
        thread = int(user.GetWindowThreadProcessId(view_hwnd, ctypes.byref(pid)))
        if not thread:
            raise RuntimeError("GetWindowThreadProcessId failed")
        return {"seat_process_id": pid.value, "seat_window_thread_id": thread}

    _observe(state, "view_client_rect_px", lambda: rectangle(view_hwnd, True))
    _observe(state, "view_client_screen_origin_px", origin)
    _observe(state, "grabbed_main_window_rect_px", lambda: rectangle(frame_hwnd, False))
    _observe(state, "view_dpi", lambda: dpi(view_hwnd))
    _observe(state, "main_window_dpi", lambda: dpi(frame_hwnd))
    _observe(state, "caller_thread_dpi_awareness", lambda: awareness(None))
    _observe(state, "seat_window_dpi_awareness", lambda: awareness(view_hwnd))
    _observe(state, "seat_process_identity", process)
    state["seat_process_awareness_unavailable"] = (
        "window awareness read, not a process-wide GetProcessDpiAwareness probe"
    )
    state["device_pixel_registration_available"] = bool(
        _value(state, "view_client_rect_px")
        and _value(state, "view_client_screen_origin_px")
        and _value(state, "grabbed_main_window_rect_px")
        and _value(state, "view_dpi") == _value(state, "main_window_dpi")
        and _value(state, "view_dpi") is not None
        and (_value(state, "caller_thread_dpi_awareness") or {}).get("awareness") == 2
        and (_value(state, "seat_window_dpi_awareness") or {}).get("awareness") == 2
    )
    state["registration_uncertainty_px"] = None
    state["registration_uncertainty_unavailable"] = (
        "native-vs-raster edge registration not independently measured"
    )
    return state


def _frame_hwnd(adapter: Any, budget: _Budget | None = None) -> int:
    frame = _invoke(budget, adapter.swApp, "ISldWorks", "Frame")
    if budget is not None:
        budget.check("IFrame early binding")
    return int(
        _invoke(
            budget,
            _early_bound(_bind(frame, "IFrame"), "IFrame"),
            "IFrame",
            "GetHWndx64",
        )
    )


def _viewport(
    adapter: Any,
    utility: Any,
    sheet_xy: Sequence[float],
    budget: _Budget | None = None,
    *,
    fixed_points: Mapping[str, Sequence[float]] | None = None,
) -> dict[str, Any]:
    state: dict[str, Any] = {"begin": _stamp(), "stage": "post_pick_non_atomic"}
    viewport = _invoke(budget, adapter.currentModel, "IModelDoc2", "ActiveView")
    for member in (
        "Scale2",
        "FrameLeft",
        "FrameTop",
        "FrameWidth",
        "FrameHeight",
        "FrameState",
    ):
        _observe(
            state, member, lambda m=member: _invoke(budget, viewport, "IModelView", m)
        )
    transform = _invoke(budget, viewport, "IModelView", "Transform")
    _observe(
        state,
        "Transform_control",
        lambda: _verified_transform(utility, transform, (*sheet_xy, 0.0), budget),
    )
    if fixed_points is not None:
        state["fixed_point_outputs"] = {}
        for point_id, xy in fixed_points.items():
            _observe(
                state["fixed_point_outputs"],
                point_id,
                lambda p=xy: _native_point(utility, transform, (*p, 0.0), budget),
            )
    for member, interface in (
        ("Orientation3", "IMathTransform"),
        ("Translation3", "IMathVector"),
    ):
        _observe(
            state,
            member,
            lambda m=member, i=interface: _numbers(
                budget, _invoke(budget, viewport, "IModelView", m), i
            ),
        )
    if budget is not None:
        budget.check("IModelView HWND early binding")
    hwnd = _observe(
        state,
        "view_hwnd",
        lambda: int(
            _invoke(
                budget,
                _early_bound(_bind(viewport, "IModelView"), "IModelView"),
                "IModelView",
                "GetViewHWndx64",
            )
        ),
    )
    frame = _observe(state, "main_window_hwnd", lambda: _frame_hwnd(adapter, budget))
    if budget is not None:
        budget.check("Win32 geometry observer bundle")
    _observe(state, "windows", lambda: _window_geometry(hwnd or 0, frame or 0))
    state["end"] = _stamp()
    return state


def _snapshot(
    adapter: Any,
    view: Any,
    utility: Any,
    point: Sequence[float],
    sheet_xy: Sequence[float],
    retained: Any = None,
) -> tuple[dict[str, Any], Any]:
    state: dict[str, Any] = {"begin": _stamp(), "stage": "post_pick_non_atomic"}
    for member in ("ReferencedConfiguration", "IsExploded", "GetName2"):
        _observe(state, member, lambda m=member: _invoke(None, view, "IView", m))
    reference = _observe(
        state,
        "ReferencedDocument",
        lambda: _invoke(None, view, "IView", "ReferencedDocument"),
    )
    if reference is not None:
        state["ReferencedDocument"]["value"] = (
            "referenced IModelDoc2 handle retained locally"
        )
        _observe(
            state,
            "reference_path",
            lambda: str(_invoke(None, reference, "IModelDoc2", "GetPathName")),
        )
        _observe(
            state,
            "reference_title",
            lambda: str(_invoke(None, reference, "IModelDoc2", "GetTitle")),
        )
    if retained is not None:
        _observe(
            state,
            "retained_handle_deferred_ArrayData",
            lambda: _numbers(None, retained, "IMathTransform"),
        )
    else:
        state["retained_handle_deferred_ArrayData"] = {
            "status": "unavailable",
            "reason": "no preprojection handle retained",
        }
    state["retained_handle_semantics"] = (
        "DEFERRED post-pick read; copy/live behavior undocumented; NOT the original numeric matrix"
    )
    fresh = _observe(
        state,
        "fresh_transform_handle",
        lambda: _invoke(None, view, "IView", "ModelToViewTransform"),
    )
    if fresh is not None:
        state["fresh_transform_handle"]["value"] = (
            "fresh IMathTransform handle retained locally"
        )
    _observe(
        state,
        "fresh_transform_control",
        lambda: _verified_transform(utility, fresh, point),
    )
    _observe(state, "viewport", lambda: _viewport(adapter, utility, sheet_xy))
    state["end"] = _stamp()
    return state, reference


def _pose_state(
    view: Any, components: Mapping[str, Any], budget: _Budget
) -> dict[str, Any]:
    """Read both families in each inside-zoom state bracket."""
    state: dict[str, Any] = {
        "begin": _stamp(),
        "stage": "post_pick_sequential_non_atomic",
        "components": {},
    }
    _observe(
        state,
        "view_transform",
        lambda: _numbers(
            budget, budget.call(view, "IView", "ModelToViewTransform"), "IMathTransform"
        ),
    )
    for member in ("ReferencedConfiguration", "IsExploded"):
        _observe(state, member, lambda m=member: budget.call(view, "IView", m))
    for instance, component in components.items():
        _observe(
            state["components"],
            instance,
            lambda c=component: _numbers(
                budget, budget.call(c, "IComponent2", "Transform2"), "IMathTransform"
            ),
        )
    state["end"] = _stamp()
    return state


def _source_witnesses() -> dict[str, dict[str, Any]]:
    # Frozen source study sm-witness-design/report.json. No builder import.
    # Builder-only expressions are mirrored explicitly, with file/line authority.
    s = lever_spec
    w, length, thickness = s.PLATE_W, s.PLATE_L, s.PLATE_T
    radius = s.CYL_R + 0.1 * s.MM_PER_IN  # build_sm_summing_lever:159-161,206
    rib_thickness = 0.2 * s.MM_PER_IN  # build_sm_summing_lever:160
    reach = s.HOLE_X - 4.1  # build_sm_summing_lever:222
    slope = radius / math.sqrt(s.SUM_H**2 - radius**2)
    rib_start = (
        -(radius**2) / s.SUM_H,
        radius * math.sqrt(1 - radius**2 / s.SUM_H**2),
        rib_thickness / 2,
    )
    rib_end = (-s.SUM_H + (thickness / 2) / slope, thickness / 2, rib_thickness / 2)
    hx, bottom, z = (
        mount_spec.BLK_HALF_X,
        mount_spec.BLK_BOT,
        mount_spec.SUPPORT_Z_THICK / 2,
    )
    mount_gap = 0.0  # frozen build_sm_knife_mount.py:137 MOUNT_GAP
    top = (
        999.7 - (979.7 + s.HEX_H / 2) - mount_gap
    )  # exact builder:135-139, NOT rounded BLK_TOP
    definitions = (
        (
            "leverNear",
            "lever",
            (s.HEX_W / 2, s.HEX_H / 4, length / 2 + s.HEX_DEPTH / 2),
            (s.HEX_W / 2, s.HEX_H / 4, length / 2),
            (s.HEX_W / 2, s.HEX_H / 4, length / 2 + s.HEX_DEPTH),
            "build_sm_summing_lever.py:524-595,675-689; sm_summing_lever_spec.py:42-54",
        ),
        (
            "leverPad",
            "lever",
            (w, thickness / 2 - s.SPRING_SEAT_T, 0),
            (w, thickness / 2 - s.SPRING_SEAT_T, -length / 2),
            (w, thickness / 2 - s.SPRING_SEAT_T, length / 2),
            "build_sm_summing_lever.py:337-427; sm_summing_lever_spec.py:137-146",
        ),
        (
            "leverFarMidrib",
            "lever",
            (-60.0, slope * (s.SUM_H - 60.0), rib_thickness / 2),
            rib_start,
            rib_end,
            "build_sm_summing_lever.py:979-1008,1053-1063,927-976",
        ),
        (
            "leverPlateEnd",
            "lever",
            ((reach + w) / 2, thickness / 2, length / 2),
            (reach, thickness / 2, length / 2),
            (w, thickness / 2, length / 2),
            "build_sm_summing_lever.py:337-370,222-237,743-841",
        ),
        (
            "controlY",
            "control",
            (hx, 0, z),
            (hx, bottom, z),
            (hx, top, z),
            "build_sm_knife_mount.py:112-148,270-345; sm_knife_mount_spec.py:36-45",
        ),
        (
            "controlX",
            "control",
            (0, bottom, z),
            (-hx, bottom, z),
            (hx, bottom, z),
            "build_sm_knife_mount.py:270-345",
        ),
        (
            "controlZ",
            "control",
            (hx, bottom, 0),
            (hx, bottom, -z),
            (hx, bottom, z),
            "build_sm_knife_mount.py:270-345",
        ),
    )
    result = {}
    for key, family, point, start, end, source in definitions:
        result[key] = {
            "id": key,
            "family": family,
            "point_local_m": [v / 1000 for v in point],
            "endpoints_local_m": [
                [v / 1000 for v in endpoint] for endpoint in (start, end)
            ],
            "source_refs": source,
            "source_coordinate_units": "part-local metres",
            "radius_to_knife_axis_m": math.hypot(point[0], point[1] - s.HEX_H / 2)
            / 1000
            if family == "lever"
            else None,
        }
    return result


def _component_snapshot(
    component: Any, utility: Any, point: Sequence[float], budget: _Budget
) -> dict[str, Any]:
    """Required transform only: unavailable fields refuse metrology, not identity discovery."""
    state: dict[str, Any] = {}
    handle = _observe(
        state,
        "Transform2_handle",
        lambda: budget.call(component, "IComponent2", "Transform2"),
    )
    if handle is not None:
        state["Transform2_handle"]["value"] = (
            "fresh IMathTransform handle retained locally"
        )
    _observe(state, "Transform2", lambda: _numbers(budget, handle, "IMathTransform"))
    _observe(
        state,
        "fresh_Transform2_control",
        lambda: _verified_transform(utility, handle, point, budget),
    )
    return state


def _optional_discovery_observations(
    reference: Any,
    configuration_name: Any,
    candidates: Mapping[str, Sequence[Mapping[str, Any]]],
    utility: Any,
    point: Sequence[float],
    record: dict[str, Any],
) -> None:
    """Optional context AFTER edge identification, isolated from required budget."""
    budget = _Budget(OPTIONAL_OBSERVATION_SECONDS)
    optional: dict[str, Any] = {
        "begin": _stamp(),
        "stage": "after_required_edge_identification",
        "required_discovery_already_frozen": True,
        "truncated": False,
        "presentation_warning": "read only; no enable/set; total transform is not independent drawing-pose proof",
    }
    record["optional_observations"] = optional
    try:
        for family in candidates.values():
            for candidate in family:
                state: dict[str, Any] = {}
                candidate["snapshot"]["optional_transforms"] = state
                for key, member, args in (
                    ("GetTotalTransform_false", "GetTotalTransform", (False,)),
                    ("GetTotalTransform_true", "GetTotalTransform", (True,)),
                    ("PresentationTransform", "PresentationTransform", ()),
                ):
                    _observe(
                        state,
                        key,
                        lambda m=member, a=args, c=candidate: _numbers(
                            budget,
                            budget.call(c["component"], "IComponent2", m, *a),
                            "IMathTransform",
                        ),
                    )
        root_record: dict[str, Any] = {
            "GetRootComponent3_resolve": False,
            "components_examined": 0,
            "component_cap": COMPONENT_CAP,
            "components": [],
            "matches": [],
        }
        optional["configuration_root"] = root_record
        if reference is None or not configuration_name:
            root_record["unavailable"] = "referenced document/configuration unavailable"
            return
        config = _observe(
            root_record,
            "configuration",
            lambda: budget.call(
                reference, "IModelDoc2", "GetConfigurationByName", configuration_name
            ),
        )
        if config is not None:
            root_record["configuration"]["value"] = (
                "IConfiguration handle retained locally"
            )
        root = _observe(
            root_record,
            "root",
            lambda: budget.call(config, "IConfiguration", "GetRootComponent3", False),
        )
        if root is None:
            root_record["unavailable"] = (
                "nonloading root unavailable; never resolve/load/activate"
            )
            return
        root_record["root"]["value"] = "nonloading configuration-root component handle"

        def children(component: Any, state: dict[str, Any]) -> list[Any]:
            values = _observe(
                state,
                "children",
                lambda: list(
                    budget.call(component, "IComponent2", "GetChildren") or ()
                ),
            )
            if values is not None:
                state["children"]["value"] = (
                    f"{len(values)} component handles retained locally"
                )
                if len(values) > COMPONENT_CAP:
                    root_record["truncated"] = True
            return (values or [])[: COMPONENT_CAP + 1]

        pending = children(root, root_record)
        while pending and root_record["components_examined"] < COMPONENT_CAP:
            component = pending.pop()
            root_record["components_examined"] += 1
            state = {"index": root_record["components_examined"] - 1}
            root_record["components"].append(state)
            path = _observe(
                state,
                "referenced_path",
                lambda: str(budget.call(component, "IComponent2", "GetPathName") or ""),
            )
            if (
                path
                and Path(path.replace("\\", "/")).stem.casefold() == "sm-summing-lever"
            ):
                _observe(
                    state,
                    "instance",
                    lambda: str(budget.call(component, "IComponent2", "Name2")),
                )
                state["post_pick_transforms"] = _component_snapshot(
                    component, utility, point, budget
                )
                root_record["matches"].append(state)
            pending.extend(children(component, state))
            if len(pending) > COMPONENT_CAP:
                root_record["truncated"] = True
                pending = pending[: COMPONENT_CAP + 1]
        root_record["truncated"] = bool(root_record.get("truncated") or pending)
    except _Deadline as exc:
        optional.update(truncated=True, deadline_error=_error(exc))
    except Exception as exc:
        optional["collection_error"] = _error(exc)
    finally:
        optional["budget"] = budget.report()
        optional["end"] = _stamp()


def _discover(
    adapter: Any,
    view: Any,
    utility: Any,
    inputs: Mapping[str, Any],
    source: Mapping[str, Any],
    report: dict[str, Any],
    reference: Any,
    configuration_name: Any,
) -> dict[str, dict[str, Any]]:
    budget = _Budget(DISCOVERY_SECONDS)
    record: dict[str, Any] = {
        "begin": _stamp(),
        "components": [],
        "edge_scans": [],
        "truncated": False,
        "component_cap": COMPONENT_CAP,
        "edge_cap_per_component": EDGE_CAP,
        "coordinate_convention": "existing _visible_edge_points treats view edge geometry as part metres; strict source-endpoint compatibility required",
    }
    report["discovery"] = record
    retained = inputs.get("retained_drawing_leaves", ())
    candidates: dict[str, list[dict[str, Any]]] = {"lever": [], "control": []}
    resolved: dict[str, dict[str, Any]] = {}
    try:
        record["retained_drawing_leaves_total"] = len(retained)
        if len(retained) > COMPONENT_CAP:
            record["truncated"] = True
        for leaf in retained[:COMPONENT_CAP]:
            budget.check("retained drawing component")
            if not leaf.visible or leaf.component is None:
                continue
            item: dict[str, Any] = {"instance": leaf.path}
            record["components"].append(item)
            path = _observe(
                item,
                "referenced_path",
                lambda: str(budget.call(leaf.component, "IComponent2", "GetPathName")),
            )
            stem = Path(path.replace("\\", "/")).stem.casefold() if path else ""
            family = {"sm-summing-lever": "lever", "sm-knife-mount": "control"}.get(
                stem
            )
            if family is None:
                continue
            item["family"] = family
            state = _component_snapshot(
                leaf.component, utility, source["leverPad"]["point_local_m"], budget
            )
            item["post_pick_transforms"] = state
            values = _value(state, "Transform2")
            # Identity discovery remains useful when this component's required
            # matrix is unavailable. The phase study refuses incomplete controls.
            offset = np.zeros(3)
            offsets = inputs.get("retained_explode_offsets", {})
            parts = leaf.path.split("/")
            for count in range(1, len(parts) + 1):
                offset += offsets.get(
                    "/".join(parts[:count]).casefold(), (0.0, 0.0, 0.0)
                )
            item["retained_explode_offset_m"] = offset.tolist()
            interpretation = _observe(
                item,
                "transform_interpretation",
                lambda: {
                    "base_origin_m": _apply(values, (0.0, 0.0, 0.0)).tolist(),
                    "actual_linear_minus_identity_max": float(
                        np.max(np.abs(_linear(values) - np.eye(3)))
                    ),
                },
            )
            item["base_origin_m"] = (
                interpretation.get("base_origin_m") if interpretation else None
            )
            item["source_expected_placement_rotation"] = (
                "identity at authored parked pose; actual free rock is not replaced"
            )
            checked = _value(state, "fresh_Transform2_control") or {}
            same_numeric_input = values is not None and values == checked.get("array")
            item["geometry_matrix_is_native_validated_matrix"] = bool(
                checked.get("valid") and same_numeric_input
            )
            candidates[family].append(
                {
                    "component": leaf.component,
                    "instance": leaf.path,
                    "values": values,
                    "offset": offset,
                    "snapshot": item,
                    "validated": bool(
                        checked.get("valid") and same_numeric_input and interpretation
                    ),
                }
            )
        record["family_counts"] = {key: len(items) for key, items in candidates.items()}
        if len(candidates["lever"]) == 1 and candidates["lever"][0]["validated"]:
            lever_values = candidates["lever"][0]["values"]
            knife_origin = _apply(lever_values, (0.0, lever_spec.HEX_H / 2000, 0.0))
            knife_axis = _linear(lever_values) @ np.array([0.0, 0.0, 1.0])
            knife_axis /= np.linalg.norm(knife_axis)
            record["knife_axis_source_crosscheck"] = {
                "source": "build_sm_summing_assembly.py:641-662,765-818",
                "reported_axis_origin_assembly_m": knife_origin.tolist(),
                "reported_axis_unit_assembly": knife_axis.tolist(),
                "mounts": [],
            }
            for mount in candidates["control"]:
                if mount["snapshot"]["base_origin_m"] is None:
                    continue
                delta = np.asarray(mount["snapshot"]["base_origin_m"]) - knife_origin
                record["knife_axis_source_crosscheck"]["mounts"].append(
                    {
                        "instance": mount["instance"],
                        "signed_axis_station_m": float(delta @ knife_axis),
                        "distance_to_reported_knife_line_m": float(
                            np.linalg.norm(delta - (delta @ knife_axis) * knife_axis)
                        ),
                        "expected_authored_relation": "mount base origin on lever theoretical knife line before explode",
                    }
                )

        def edges_for(
            component: dict[str, Any], family: str
        ) -> dict[str, dict[str, Any]]:
            scan: dict[str, Any] = {
                "instance": component["instance"],
                "family": family,
                "examined": 0,
                "errors": [],
                "matches": {},
                "truncated": False,
            }
            record["edge_scans"].append(scan)
            count = int(
                budget.call(
                    view, "IView", "GetVisibleEntityCount2", component["component"], 1
                )
                or 0
            )
            scan["reported_total"] = count
            if count > EDGE_CAP:
                scan.update(
                    truncated=True,
                    unavailable="visible edge count exceeds fixed cap; no enumeration",
                )
                return {}
            budget.check("raw_visible_entities")
            edges = sw_drawing.raw_visible_entities(view, component["component"], 1)
            scan["returned_total"] = len(edges)
            scan["truncated"] = len(edges) > EDGE_CAP
            matches: dict[str, list[tuple[Any, Any]]] = {
                key: [] for key, w in source.items() if w["family"] == family
            }
            for edge in edges[:EDGE_CAP]:
                budget.check("visible straight edge")
                scan["examined"] += 1
                try:
                    curve = budget.call(edge, "IEdge", "GetCurve")
                    if curve is None or not budget.call(curve, "ICurve", "IsLine"):
                        continue
                    params = tuple(
                        float(v)
                        for v in (budget.call(edge, "IEdge", "GetCurveParams2") or ())
                    )
                    if not all(math.isfinite(v) for v in params[:6]):
                        raise _Nonfinite("edge has nonfinite endpoints")
                    if len(params) < 6:
                        raise ValueError("edge has incomplete endpoints")
                    ends = np.asarray(params[:6]).reshape(2, 3)
                    for key in matches:
                        expected = np.asarray(source[key]["endpoints_local_m"])
                        discrepancy = min(
                            float(np.max(np.linalg.norm(ends - expected, axis=1))),
                            float(
                                np.max(np.linalg.norm(ends[::-1] - expected, axis=1))
                            ),
                        )
                        if discrepancy <= SOURCE_TOLERANCE_M:
                            budget.check("GetComponent identity")
                            owner = budget.call(
                                _early_bound(_bind(edge, "IEntity"), "IEntity"),
                                "IEntity",
                                "GetComponent",
                            )
                            geometry: dict[str, Any] = {
                                "raw_curve_params_first6_m": params[:6],
                                "source_endpoint_max_error_m": discrepancy,
                                "IsLine": True,
                                "component_filtered_enumeration": True,
                            }
                            owner_name = str(
                                budget.call(owner, "IComponent2", "Name2")
                            ).replace("\\", "/")
                            geometry["owner_full_Name2"] = owner_name
                            if (
                                owner_name.casefold()
                                != component["instance"].casefold()
                            ):
                                raise ValueError(
                                    "edge owner full Name2 does not match component-filtered instance"
                                )
                            _observe(
                                geometry,
                                "IsSame_owner_telemetry_only",
                                lambda: int(
                                    budget.call(
                                        adapter.swApp,
                                        "ISldWorks",
                                        "IsSame",
                                        owner,
                                        component["component"],
                                    )
                                ),
                            )
                            if (
                                int(
                                    budget.call(
                                        adapter.swApp, "ISldWorks", "IsSame", edge, edge
                                    )
                                )
                                != 1
                            ):
                                raise ValueError("native edge identity unavailable")
                            geometry["IsSame_self"] = 1
                            matches[key].append((edge, geometry))
                except _Deadline:
                    raise
                except (_Nonfinite, TypeError, AssertionError):
                    raise
                except Exception as exc:
                    scan["errors"].append(
                        {"edge_index": scan["examined"] - 1, "error": _error(exc)}
                    )
            found = {}
            for key, hits in matches.items():
                scan["matches"][key] = len(hits)
                if len(hits) == 1 and not scan["truncated"]:
                    edge, geometry = hits[0]
                    found[key] = {
                        **source[key],
                        **component,
                        "edge": edge,
                        "native_geometry": geometry,
                    }
            return found

        if len(candidates["lever"]) == 1:
            resolved.update(edges_for(candidates["lever"][0], "lever"))
        mounts = [
            item
            for item in candidates["control"]
            if item["snapshot"]["base_origin_m"] is not None
        ]
        mounts.sort(key=lambda item: item["snapshot"]["base_origin_m"][2], reverse=True)
        if (
            len(candidates["control"]) == len(mounts) == 2
            and mounts[0]["snapshot"]["base_origin_m"][2]
            > mounts[1]["snapshot"]["base_origin_m"][2]
        ):
            resolved.update(edges_for(mounts[0], "control"))
            record["control_instance_disposition"] = (
                "fixed front instance by base-Z; no missing-witness substitution"
            )
        else:
            record["control_instance_disposition"] = (
                "unavailable: not exactly two distinct base-Z mount origins"
            )
    except _Deadline as exc:
        record.update(truncated=True, deadline_error=_error(exc))
    finally:
        record["budget"] = budget.report()
        record["end"] = _stamp()
        record["frozen_subset"] = [key for key in PRIORITY if key in resolved]
        record["missing"] = [key for key in PRIORITY if key not in resolved]
        record["all_seven_frozen_before_intervention"] = len(resolved) == 7
        record["reduced_set_allowed"] = False
    _optional_discovery_observations(
        reference,
        configuration_name,
        candidates,
        utility,
        source["leverPad"]["point_local_m"],
        record,
    )
    return resolved


def _finite_tree(value: Any) -> None:
    if isinstance(value, (float, np.floating)) and not math.isfinite(value):
        raise _Nonfinite("nonfinite diagnostic evidence")
    if isinstance(value, Mapping):
        for child in value.values():
            _finite_tree(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _finite_tree(child)


def _bits(values: Sequence[float]) -> list[str]:
    _finite_tree(values)
    return [struct.pack(">d", float(value)).hex() for value in values]


def _ordered_bits(value: float) -> int:
    bits = struct.unpack(">Q", struct.pack(">d", value))[0]
    return (~bits & ((1 << 64) - 1)) if bits >> 63 else bits | (1 << 63)


def _axis_evidence(value: float, reference: float) -> dict[str, Any]:
    _finite_tree((value, reference))
    floor_bucket = math.floor(value)
    nearest_bucket = round(value)  # Python binary64, ties to even.
    integer_distance = value - round(value)
    half_distance = value - (math.floor(value) + 0.5)

    def side(distance: float) -> str:
        return "on" if distance == 0 else "below" if distance < 0 else "above"

    return {
        "value": value,
        "hex": value.hex(),
        "bits_be_hex": _bits((value,))[0],
        "minus_first_A": value - reference,
        "signed_binary64_ulp_steps_from_first_A": _ordered_bits(value)
        - _ordered_bits(reference),
        "ulp_at_value": math.ulp(value),
        "floor_integer_boundary": {
            "bucket": floor_bucket,
            "fraction": value - floor_bucket,
            "signed_distance_to_nearest_integer": integer_distance,
            "boundary_side": side(integer_distance),
        },
        "nearest_ties_even_half_integer_boundary": {
            "bucket": nearest_bucket,
            "fraction_from_bucket": value - nearest_bucket,
            "signed_distance_to_cell_half_integer": half_distance,
            "boundary_side": side(half_distance),
        },
    }


def _output_evidence(
    output: Sequence[float], reference: Sequence[float]
) -> dict[str, Any]:
    return {
        "native_output": list(output),
        "binary64_hex": [float(v).hex() for v in output],
        "bits_be_hex": _bits(output),
        "axes": [
            _axis_evidence(float(v), float(r))
            for v, r in zip(output[:2], reference[:2], strict=True)
        ],
        "units": "IModelView.Transform output units; NOT registered raster or internal pick precision",
    }


def _freeze_points(
    witnesses: Sequence[Mapping[str, Any]],
    view_values: Sequence[float],
    original_pad_xy: Sequence[float],
) -> list[dict[str, Any]]:
    frozen = []
    for witness in witnesses:
        tangent = (
            _linear(view_values)[:2]
            @ _linear(witness["values"])
            @ (
                np.asarray(witness["endpoints_local_m"][1])
                - witness["endpoints_local_m"][0]
            )
        )
        length = float(np.linalg.norm(tangent))
        if length <= 1e-12:
            raise ValueError(f"{witness['id']} degenerate projected edge")
        normal = np.array([-tangent[1], tangent[0]]) / length
        assembly = (
            _apply(witness["values"], witness["point_local_m"]) + witness["offset"]
        )
        projected = _apply(view_values, assembly)[:2]
        centre = tuple(
            float(v)
            for v in (original_pad_xy if witness["id"] == "leverPad" else projected)
        )
        points = {"original": centre}
        if witness["id"] == "leverPad":
            # Freeze the source-projected +8um point independently of oldXY drift.
            points["plus8um"] = tuple(
                float(projected[i] + PAD_CONTROL_OFFSET_M * normal[i]) for i in range(2)
            )
        _finite_tree(points)
        frozen.append(
            {
                "id": witness["id"],
                "centre_sheet_xy_m": centre,
                "source_projected_sheet_xy_m": projected.tolist(),
                "normal": normal.tolist(),
                "projected_edge_length_m": length,
                "points": points,
                "point_binary64_hex": {
                    key: [v.hex() for v in xy] for key, xy in points.items()
                },
                "pad_original_is_exact_baseline_xy": witness["id"] == "leverPad",
            }
        )
    return frozen


def _path_plan(root: Path, probe_id: str) -> tuple[Path, dict[str, Any]]:
    short = f"sm1667-{probe_id[:8]}"
    out_dir = root / short
    files = {
        "checkpoint": out_dir / "p.json",
        "checkpoint_temp": out_dir / "p.tmp",
        "original_png": out_dir / "orig.png",
    }
    for index, witness in enumerate(PRIORITY):
        for arm in SHIFTS:
            files[f"{witness}.{arm}.png"] = out_dir / f"w{index}{arm}.png"
    # _seat_forensics._capture_dir uses a fixed-width UTC-ms directory.
    final_dir = root / short / "YYYYMMDDTHHMMSSmmmZ"
    for suffix in ("desktop.png", "window.png", "region.bmp", "sheet.pdf"):
        files[f"final.{suffix}"] = final_dir / f"{short}-{suffix}"
    paths = {}
    for key, path in files.items():
        units = len(str(path.absolute()).encode("utf-16-le")) // 2
        paths[key] = {
            "path": str(path),
            "utf16_units": units,
            "safe": units <= PATH_LIMIT_UTF16,
            "refusal": None
            if units <= PATH_LIMIT_UTF16
            else "conservative Windows path budget exceeded",
        }
    return out_dir, {
        "limit_utf16_units": PATH_LIMIT_UTF16,
        "paths": paths,
        "max_utf16_units": max(row["utf16_units"] for row in paths.values()),
        "final_label": short,
        "final_timestamp_is_fixed_width_budget_template": True,
        "capture_refusal_does_not_refuse_study": True,
    }


class _Checkpoint:
    """Atomic same-directory replacement; only OSError disables mid-study writes."""

    def __init__(self, report: dict[str, Any], path: Path, temp: Path) -> None:
        self.report, self.path, self.temp = report, path, temp
        self.disabled = False
        self.final_attempted = False
        report["checkpoint"] = {
            "path": str(path),
            "temp_path": str(temp),
            "attempts": [],
            "mid_writes_disabled": False,
            "last_good_attempt": None,
            "timing_snapshot_note": "JSON is a pre-serialization snapshot: its own final attempt remains started; prior receipts are complete. Stop/cancel telemetry carries the final write/replace receipt.",
        }

    def __call__(self, *, final: bool = False) -> None:
        if (self.disabled and not final) or (final and self.final_attempted):
            return
        if final:
            self.final_attempted = True
        record: dict[str, Any] = {
            "final": final,
            "begin": _stamp(),
            "status": "started",
        }
        self.report["checkpoint"]["attempts"].append(record)
        operation = "serialization"
        started = time.perf_counter()
        begin = started
        try:
            _finite_tree(self.report)
            begin = time.perf_counter()
            payload = json.dumps(self.report, sort_keys=True, allow_nan=False) + "\n"
            record["serialization_ms"] = (time.perf_counter() - begin) * 1000
            _cost("checkpoint_serialization", record["serialization_ms"])
            operation = "write"
            begin = time.perf_counter()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.temp.write_text(payload, encoding="utf-8")
            record["write_ms"] = (time.perf_counter() - begin) * 1000
            _cost("checkpoint_write", record["write_ms"])
            operation = "replace"
            begin = time.perf_counter()
            os.replace(self.temp, self.path)
            record["replace_ms"] = (time.perf_counter() - begin) * 1000
            _cost("checkpoint_replace", record["replace_ms"])
            record.update(status="written", bytes_utf8=len(payload.encode("utf-8")))
            self.report["checkpoint"]["last_good_attempt"] = (
                len(self.report["checkpoint"]["attempts"]) - 1
            )
        except OSError as exc:
            if operation == "serialization":
                raise
            self.disabled = True
            self.report["checkpoint"]["mid_writes_disabled"] = True
            record.update(
                status="io-error",
                operation=operation,
                error_type=type(exc).__name__,
                errno=exc.errno,
                path=str(self.temp if operation == "write" else self.path),
                error=_error(exc),
                final_failure_loud=final,
            )
            with contextlib.suppress(Exception):
                _telemetry.warn(
                    f"[1667] {'FINAL checkpoint FAILED' if final else 'checkpoint failed; mid-study writes disabled'}: {exc}",
                    probe_id=self.report["probe_id"],
                    **record,
                )
        finally:
            if f"{operation}_ms" not in record:
                record[f"{operation}_ms"] = (time.perf_counter() - begin) * 1000
                _cost(f"checkpoint_{operation}", record[f"{operation}_ms"])
            record["elapsed_ms"] = (time.perf_counter() - started) * 1000
            record["end"] = _stamp()
            _cost("checkpoint_total", record["elapsed_ms"])


def _capture_png(report: dict[str, Any], key: str, hwnd: int) -> dict[str, Any]:
    planned = report["path_budget"]["paths"][key]
    if not planned["safe"]:
        return {
            "status": "refused",
            "reason": planned["refusal"],
            "path": planned["path"],
        }
    result: dict[str, Any] = {"begin": _stamp()}
    started = time.perf_counter()
    _count("window_png_capture")
    try:
        with _timed("capture"):

            def capture() -> dict[str, Any]:
                path = Path(planned["path"])
                path.parent.mkdir(parents=True, exist_ok=True)
                return _window_png(path, hwnd)

            _observe(result, "image", capture)
    finally:
        result["capture_ms"] = (time.perf_counter() - started) * 1000
        result["end"] = _stamp()
    return result


@contextlib.contextmanager
def _study_zoom(
    adapter: Any, centre: Sequence[float], state: dict[str, Any], budget: _Budget
):
    budget.check("ViewZoomTo2")
    started = time.perf_counter()
    entered = False
    cleanup_started = None
    body_error = None
    _count("zoom_to_box_attempts")
    try:
        with _zoomed_on(adapter, centre, _HIT_ZOOM_HALF):
            entered = True
            state["zoom_in_ms"] = (time.perf_counter() - started) * 1000
            _cost("zoom_in", state["zoom_in_ms"])
            try:
                yield
            except BaseException as exc:
                body_error = exc
                raise
            finally:
                cleanup_started = time.perf_counter()
    except BaseException as exc:
        if body_error is not None and exc is not body_error:
            body_error.add_note(f"zoom cleanup also failed: {exc!r}")
            raise body_error
        raise
    finally:
        _count("zoom_fit_cleanup_attempts")
        if not entered:
            state["zoom_entry_and_failed_cleanup_ms"] = (
                time.perf_counter() - started
            ) * 1000
        else:
            state["zoom_fit_cleanup_ms"] = (
                time.perf_counter() - cleanup_started
            ) * 1000
            _cost("zoom_fit_cleanup", state["zoom_fit_cleanup_ms"])


def _phase_bracket(
    adapter: Any,
    view: Any,
    utility: Any,
    frozen: Mapping[str, Any],
    components: Mapping[str, Any],
    budget: _Budget,
) -> dict[str, Any]:
    with _timed("state_controls_inclusive"):
        return {
            "viewport": _viewport(
                adapter,
                utility,
                frozen["centre_sheet_xy_m"],
                budget,
                fixed_points=frozen["points"],
            ),
            "pose": _pose_state(view, components, budget),
            "inside_zoom": True,
        }


def _matrix_comparison(actual: Any, expected: Any) -> dict[str, Any]:
    if actual is None or expected is None:
        return {"available": False, "within_tolerance": False, "bit_equal": None}
    a, b = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    _finite_tree((a.tolist(), b.tolist()))
    if a.shape != b.shape or a.shape != (16,):
        return {
            "available": True,
            "within_tolerance": False,
            "bit_equal": False,
            "shape_mismatch": True,
        }
    delta = float(np.max(np.abs(a - b)))
    return {
        "available": True,
        "within_tolerance": delta <= MATRIX_STABILITY_TOLERANCE,
        "max_absolute_delta": delta,
        "bit_equal": _bits(a) == _bits(b),
        "actual_bits_be_hex": _bits(a),
        "expected_bits_be_hex": _bits(b),
    }


def _bracket_controls(
    bracket: Mapping[str, Any],
    first: Mapping[str, Any],
    reference: Mapping[str, Any],
    point_id: str,
    arm: str,
) -> dict[str, Any]:
    viewport, first_viewport = bracket["viewport"], first["viewport"]
    control = _value(viewport, "Transform_control") or {}
    first_control = _value(first_viewport, "Transform_control") or {}
    actual = _value(viewport.get("fixed_point_outputs", {}), point_id)
    initial = _value(first_viewport.get("fixed_point_outputs", {}), point_id)
    checks: dict[str, Any] = {}
    missing, failed = [], []

    def gate(name: str, available: bool, passes: bool, evidence: Any = None) -> None:
        checks[name] = {
            "available": bool(available),
            "passes": bool(available and passes),
            "evidence": evidence,
        }
        if not available:
            missing.append(name)
        elif not passes:
            failed.append(name)

    gate(
        "native_transform_control",
        bool(control) and bool(first_control),
        bool(control.get("valid") and first_control.get("valid")),
    )
    gate(
        "native_fixed_point_output",
        actual is not None and initial is not None,
        actual is not None,
    )
    if actual is not None and initial is not None:
        delta = [actual[i] - initial[i] for i in range(2)]
        error = max(abs(delta[i] - SHIFTS[arm][i]) for i in range(2))
        gate(
            "achieved_translation",
            True,
            error <= ACHIEVED_TOLERANCE,
            {"requested": SHIFTS[arm], "achieved": delta, "max_error": error},
        )
        if arm == "A":
            gate(
                "A_restoration",
                True,
                max(abs(v) for v in delta) <= A_RESTORATION_TOLERANCE,
                delta,
            )
        checks["output_evidence"] = _output_evidence(actual, initial)
        if arm == "D":
            models = {}
            for model in (
                "floor_integer_boundary",
                "nearest_ties_even_half_integer_boundary",
            ):
                axes = []
                for value, origin in zip(actual[:2], initial[:2], strict=True):
                    observed = _axis_evidence(float(value), float(origin))[model]
                    baseline = _axis_evidence(float(origin), float(origin))[model]
                    axes.append(
                        {
                            "bucket_shift": observed["bucket"] - baseline["bucket"],
                            "boundary_side_matches": observed["boundary_side"]
                            == baseline["boundary_side"],
                            "phase_preserving_under_named_model": (
                                observed["bucket"] - baseline["bucket"] == 1
                                and observed["boundary_side"]
                                == baseline["boundary_side"]
                            ),
                        }
                    )
                models[model] = {
                    "axes": axes,
                    "phase_preserving_under_named_model": all(
                        a["phase_preserving_under_named_model"] for a in axes
                    ),
                }
            checks["D_integer_request_phase_models"] = models
    scales = (_value(viewport, "Scale2"), _value(first_viewport, "Scale2"))
    scale_available = all(v is not None and math.isfinite(v) and v > 0 for v in scales)
    relative = abs(scales[0] / scales[1] - 1) if scale_available else None
    gate(
        "Scale2",
        scale_available,
        relative is not None and relative <= SCALE_RELATIVE_TOLERANCE,
        relative,
    )
    for key in (
        "FrameLeft",
        "FrameTop",
        "FrameWidth",
        "FrameHeight",
        "FrameState",
        "view_hwnd",
        "main_window_hwnd",
    ):
        a, b = _value(viewport, key), _value(first_viewport, key)
        gate(key, a is not None and b is not None, a == b, {"actual": a, "first_A": b})
    orientation = _matrix_comparison(
        _value(viewport, "Orientation3"), _value(first_viewport, "Orientation3")
    )
    gate(
        "Orientation3",
        orientation["available"],
        orientation["within_tolerance"],
        orientation,
    )
    if control.get("array") is not None and first_control.get("array") is not None:
        a, b = list(control["array"]), list(first_control["array"])
        # Translation is the intervention; every other transform entry is a control.
        for index in (9, 10, 11):
            a[index] = b[index] = 0.0
        shape = _matrix_comparison(a, b)
    else:
        shape = _matrix_comparison(None, None)
    gate("viewport_linear_shape", shape["available"], shape["within_tolerance"], shape)
    windows, first_windows = (
        _value(viewport, "windows") or {},
        _value(first_viewport, "windows") or {},
    )
    for key in (
        "view_client_rect_px",
        "view_client_screen_origin_px",
        "grabbed_main_window_rect_px",
        "view_dpi",
        "main_window_dpi",
        "caller_thread_dpi_awareness",
        "seat_window_dpi_awareness",
        "seat_process_identity",
    ):
        a, b = _value(windows, key), _value(first_windows, key)
        gate(
            f"windows.{key}",
            a is not None and b is not None,
            a == b,
            {"actual": a, "first_A": b},
        )
    pose = bracket["pose"]
    expected_view = _value(reference, "view_transform_control") or {}
    view_matrix = _matrix_comparison(
        _value(pose, "view_transform"), expected_view.get("array")
    )
    gate(
        "drawing_view_transform",
        view_matrix["available"] and bool(expected_view.get("valid")),
        view_matrix["within_tolerance"],
        view_matrix,
    )
    for key in ("ReferencedConfiguration", "IsExploded"):
        a, b = _value(pose, key), _value(reference, key)
        gate(
            key, a is not None and b is not None, a == b, {"actual": a, "reference": b}
        )
    expected_components = reference.get("components", {})
    gate(
        "both_component_families",
        len(expected_components) == 2,
        len(expected_components) == 2,
    )
    for instance in expected_components:
        comparison = _matrix_comparison(
            _value(pose["components"], instance), _value(expected_components, instance)
        )
        gate(
            f"component.{instance}",
            comparison["available"],
            comparison["within_tolerance"],
            comparison,
        )
    return {
        "admitted": not missing and not failed,
        "missing_metadata": missing,
        "observed_control_failures": failed,
        "checks": checks,
    }


def _response_details(
    states: Sequence[Mapping[str, Any]], point_id: str
) -> dict[str, Any]:
    classes = [
        state.get("picks", {})
        .get(point_id, {})
        .get("selection_identity_class", "missing")
        for state in states
    ]
    groups = {
        arm: [
            (state, outcome)
            for state, outcome in zip(states, classes, strict=True)
            if state["arm"] == arm
        ]
        for arm in SHIFTS
    }
    a_classes = [outcome for _, outcome in groups["A"]]
    a_stable = len(a_classes) == 8 and len(set(a_classes)) == 1
    arms = {}
    for arm, entries in groups.items():
        expected = 8 if arm == "A" else 2
        outcomes = [outcome for _, outcome in entries]
        disagreements = []
        for i, (left, lclass) in enumerate(entries):
            for right, rclass in entries[i + 1 :]:
                if lclass == rclass:
                    continue
                transforms, crossings = [], []
                for bracket in ("before", "after"):
                    lcontrol = (
                        left.get("point_controls", {})
                        .get(point_id, {})
                        .get(bracket, {})
                    )
                    rcontrol = (
                        right.get("point_controls", {})
                        .get(point_id, {})
                        .get(bracket, {})
                    )
                    le = lcontrol.get("checks", {}).get("output_evidence")
                    re = rcontrol.get("checks", {}).get("output_evidence")
                    lm = (
                        _value(
                            left.get(bracket, {}).get("viewport", {}),
                            "Transform_control",
                        )
                        or {}
                    )
                    rm = (
                        _value(
                            right.get(bracket, {}).get("viewport", {}),
                            "Transform_control",
                        )
                        or {}
                    )
                    transforms.append(
                        bool(
                            le
                            and re
                            and le["bits_be_hex"] == re["bits_be_hex"]
                            and lm.get("array") is not None
                            and rm.get("array") is not None
                            and _bits(lm["array"]) == _bits(rm["array"])
                        )
                    )
                    if le and re:
                        for axis, (la, ra) in enumerate(
                            zip(le["axes"], re["axes"], strict=True)
                        ):
                            for model in (
                                "floor_integer_boundary",
                                "nearest_ties_even_half_integer_boundary",
                            ):
                                if (
                                    la[model]["boundary_side"]
                                    != ra[model]["boundary_side"]
                                    or la[model]["bucket"] != ra[model]["bucket"]
                                ):
                                    crossings.append(
                                        {
                                            "bracket": bracket,
                                            "axis": axis,
                                            "model": model,
                                        }
                                    )
                identical = all(transforms)
                disagreements.append(
                    {
                        "left": left["id"],
                        "right": right["id"],
                        "recorded_transform_class": "bit-identical"
                        if identical
                        else "changed-or-missing",
                        "timing_redraw_candidate_not_internal_nondeterminism_proof": identical,
                        "ULP_boundary_crossings": crossings,
                    }
                )
        arms[arm] = {
            "classes": outcomes,
            "replicates_agree": len(outcomes) == expected and len(set(outcomes)) == 1,
            "reversible_arm": arm != "A"
            and a_stable
            and len(outcomes) == 2
            and len(set(outcomes)) == 1
            and outcomes[0] != a_classes[0],
            "nonreproducible": len(set(outcomes)) > 1,
            "disagreements": disagreements,
        }
    reversible = any(row["reversible_arm"] for row in arms.values())
    label = (
        "incomplete"
        if len(states) != 14 or any(c in ("missing", "unreadable") for c in classes)
        else "reversible-response"
        if reversible
        else "no-response"
        if len(set(classes)) == 1
        else "nonreproducible"
    )
    return {
        "uncontrolled_pattern_label": label,
        "classes": classes,
        "all_eight_A_classes_agree": a_stable,
        "arms": arms,
        "nonreproducible_arms": [
            arm for arm, row in arms.items() if row["nonreproducible"]
        ],
    }


def _adjudicate(witness: dict[str, Any]) -> None:
    states = witness["states"]
    pad = witness["id"] == "leverPad"
    witness["pad_own_edge_positive_control_per_block"] = (
        [
            {
                "block": block,
                "at_least_one_exact_own_edge_hit": any(
                    pick.get("accepted_own_edge", False)
                    for state in states
                    if state["block"] == block
                    for pick in state["picks"].values()
                ),
                "observed_classes": {
                    point: [
                        state["picks"]
                        .get(point, {})
                        .get("selection_identity_class", "missing")
                        for state in states
                        if state["block"] == block
                    ]
                    for point in witness["fixed"]["points"]
                },
            }
            for block in (1, 2)
        ]
        if pad
        else []
    )
    scales = [
        _value(state.get(bracket, {}).get("viewport", {}), "Scale2")
        for state in states
        for bracket in ("before", "after")
    ]
    valid_scales = bool(scales) and all(
        v is not None and math.isfinite(v) and v > 0 for v in scales
    )
    scale_variation = (
        (max(scales) - min(scales)) / min(scales) if valid_scales else None
    )
    endpoints = {}
    for point_id in witness["fixed"]["points"]:
        details = _response_details(states, point_id)
        missing, failures = [], []
        for state in states:
            for bracket in ("before", "after"):
                control = state.get("point_controls", {}).get(point_id, {}).get(bracket)
                if control is None:
                    missing.append(f"{state['id']}.{bracket}")
                else:
                    missing.extend(
                        f"{state['id']}.{bracket}.{key}"
                        for key in control["missing_metadata"]
                    )
                    failures.extend(
                        f"{state['id']}.{bracket}.{key}"
                        for key in control["observed_control_failures"]
                    )
        if pad:
            failures.extend(
                f"pad_own_edge_control_block_{row['block']}"
                for row in witness["pad_own_edge_positive_control_per_block"]
                if not row["at_least_one_exact_own_edge_hit"]
            )
        if scale_variation is not None and scale_variation > SCALE_RELATIVE_TOLERANCE:
            failures.append("aggregate_Scale2_variation")
        admitted = (
            len(states) == 14
            and not missing
            and not failures
            and details["uncontrolled_pattern_label"] != "incomplete"
        )
        label = details["uncontrolled_pattern_label"]
        if not admitted and label != "incomplete":
            label = "incomplete" if missing else "control-failed"
        timings = {}
        for arm in SHIFTS:
            samples = [
                state["picks"][point_id]
                for state in states
                if state["arm"] == arm
                and point_id in state["picks"]
                and "select_ms" in state["picks"][point_id]
            ]
            values = sorted(sample["select_ms"] for sample in samples)
            timings[arm] = {
                "n": len(values),
                "select_ms": values,
                "range_ms": [values[0], values[-1]] if values else None,
                "first_after_zoom": [sample["first_after_zoom"] for sample in samples],
                "descriptive_only_not_speedup_delta": True,
            }
        endpoints[point_id] = {
            **details,
            "label": label,
            "admitted": admitted,
            "missing_metadata": missing,
            "observed_control_failures": failures,
            "per_arm_selection_timing": timings,
            "scale_relative_variation": scale_variation,
            "role": "primary"
            if pad and point_id == "original"
            else "within-pad-control"
            if pad
            else "secondary",
        }
    witness["endpoints"] = endpoints


def _phase_study(
    adapter: Any,
    view: Any,
    utility: Any,
    witnesses: Sequence[Mapping[str, Any]],
    frozen: Sequence[Mapping[str, Any]],
    report: dict[str, Any],
    checkpoint: _Checkpoint,
) -> None:
    budget = _Budget(STUDY_SECONDS)
    started = time.perf_counter()
    picks_total = 0
    components = {w["instance"]: w["component"] for w in witnesses}
    report["study"] = {
        "witnesses": [],
        "begin": _stamp(),
        "capture_asymmetry": "block1 first A and B/C/D captured AFTER picks and closing bracket; block2 no captures",
    }
    try:
        budget.check("explicit initial fit")
        _invoke(budget, adapter.currentModel, "IModelDoc2", "ViewZoomtofit2")
        report["study"]["explicit_initial_fit_completed"] = True
        for witness, fixed in zip(witnesses, frozen, strict=True):
            budget.check(f"start witness {witness['id']}")
            record: dict[str, Any] = {
                "id": witness["id"],
                "fixed": fixed,
                "states": [],
                "begin": _stamp(),
                "emitted_event_count": 0,
                "event_submission_errors": 0,
            }
            report["study"]["witnesses"].append(record)
            token = _SPAN_EVENTS.set(record)
            span_started = time.perf_counter()
            span_body_started = None
            span_body_ms = 0.0
            try:
                with _telemetry.span(
                    "drawing.sm_pose.viewport_witness",
                    probe_id=report["probe_id"],
                    witness=witness["id"],
                    json_path=report["checkpoint"]["path"],
                ) as span:
                    span_body_started = time.perf_counter()
                    try:
                        offsets = None
                        first = None
                        for block, sequence in enumerate(BLOCKS, start=1):
                            for index, arm in enumerate(sequence):
                                budget.check(
                                    f"{witness['id']} block{block} state{index}"
                                )
                                state = {
                                    "id": f"b{block}s{index}",
                                    "block": block,
                                    "index": index,
                                    "arm": arm,
                                    "requested_output_shift": SHIFTS[arm],
                                    "picks": {},
                                    "begin": _stamp(),
                                }
                                record["states"].append(state)
                                if offsets is None and arm != "A":
                                    state["refusal"] = (
                                        "first A native transform missing/singular; offsets cannot be derived"
                                    )
                                    checkpoint()
                                    continue
                                offset = (0.0, 0.0) if offsets is None else offsets[arm]
                                centre = tuple(
                                    fixed["centre_sheet_xy_m"][i] + offset[i]
                                    for i in range(2)
                                )
                                state["requested_zoom_centre_sheet_xy_m"] = centre
                                with _study_zoom(adapter, centre, state, budget):
                                    state["before"] = _phase_bracket(
                                        adapter,
                                        view,
                                        utility,
                                        fixed,
                                        components,
                                        budget,
                                    )
                                    if first is None:
                                        first = state["before"]
                                        control = (
                                            _value(
                                                first["viewport"], "Transform_control"
                                            )
                                            or {}
                                        )
                                        if control.get("valid"):
                                            linear = _linear(control["array"])[:2, :2]
                                            determinant = float(np.linalg.det(linear))
                                            record["offset_derivation"] = {
                                                "first_A_state": state["id"],
                                                "linear_2x2": linear.tolist(),
                                                "determinant": determinant,
                                                "derived_once_no_feedback": True,
                                            }
                                            if determinant != 0 and math.isfinite(
                                                determinant
                                            ):
                                                # Moving the zoom centre subtracts its linear image.
                                                offsets = {
                                                    key: tuple(
                                                        float(v)
                                                        for v in -np.linalg.solve(
                                                            linear, shift
                                                        )
                                                    )
                                                    for key, shift in SHIFTS.items()
                                                }
                                                _finite_tree(offsets)
                                                record["offset_derivation"][
                                                    "sheet_centre_offsets_m"
                                                ] = offsets
                                    point_order = list(fixed["points"])
                                    if block == 2:
                                        point_order.reverse()
                                    state["point_order"] = point_order
                                    for pick_index, point_id in enumerate(point_order):
                                        budget.check(
                                            f"{witness['id']} {state['id']} {point_id}"
                                        )
                                        if picks_total >= PICK_CAP:
                                            raise _Deadline(
                                                "112 study selection cap reached"
                                            )
                                        pick = {
                                            "point_id": point_id,
                                            "first_after_zoom": pick_index == 0,
                                        }
                                        state["picks"][point_id] = pick
                                        picks_total += 1
                                        _pick(
                                            adapter,
                                            fixed["points"][point_id],
                                            witness,
                                            arm,
                                            budget,
                                            record=pick,
                                            view=view,
                                        )
                                        _event(
                                            "phase_pick",
                                            report,
                                            json_path=report["checkpoint"]["path"],
                                            witness=witness["id"],
                                            state=state["id"],
                                            point=point_id,
                                            result=pick.get(
                                                "selection_identity_class", "unreadable"
                                            ),
                                            raw_result=pick.get("raw_result", False),
                                            select_ms=pick.get("select_ms", 0.0),
                                        )
                                    state["after"] = _phase_bracket(
                                        adapter,
                                        view,
                                        utility,
                                        fixed,
                                        components,
                                        budget,
                                    )
                                    state["point_controls"] = {
                                        point: {
                                            name: _bracket_controls(
                                                state[name],
                                                first,
                                                report["pose_reference"],
                                                point,
                                                arm,
                                            )
                                            for name in ("before", "after")
                                        }
                                        for point in fixed["points"]
                                    }
                                    _invoke(
                                        budget,
                                        adapter.currentModel,
                                        "IModelDoc2",
                                        "ClearSelection2",
                                        True,
                                    )
                                    capture = block == 1 and (index == 0 or arm != "A")
                                    if capture:
                                        budget.check(
                                            "inside-zoom PNG after picks and closing bracket"
                                        )
                                        state["capture"] = _capture_png(
                                            report,
                                            f"{witness['id']}.{arm}.png",
                                            _value(
                                                state["before"]["viewport"],
                                                "main_window_hwnd",
                                            )
                                            or 0,
                                        )
                                state["end"] = _stamp()
                                _adjudicate(record)
                                checkpoint()  # OUTSIDE zoom, including after its fit cleanup.
                                budget.check("after state checkpoint")
                    finally:
                        try:
                            _adjudicate(record)
                        finally:
                            record["end"] = _stamp()
                            span_body_ms = (
                                time.perf_counter() - span_body_started
                            ) * 1000
                            with contextlib.suppress(Exception):
                                span.set_attribute(
                                    "emitted_event_count", record["emitted_event_count"]
                                )
                                span.set_attribute(
                                    "event_submission_errors",
                                    record["event_submission_errors"],
                                )
                                span.set_attribute(
                                    "study_selection_attempts",
                                    sum(len(s["picks"]) for s in record["states"]),
                                )
            finally:
                _SPAN_EVENTS.reset(token)
                span_scope_ms = (time.perf_counter() - span_started) * 1000
                _cost("witness_span_scope_inclusive", span_scope_ms)
                _cost("witness_span_setup_cleanup", span_scope_ms - span_body_ms)
    except _Deadline as exc:
        report["study"]["truncated"] = _error(exc)
    finally:
        elapsed = (time.perf_counter() - started) * 1000
        _cost("total_study_inclusive", elapsed)
        report["study"]["budget"] = {
            **budget.report(),
            "study_selection_attempts": picks_total,
            "study_selection_cap": PICK_CAP,
            "raw_results_recorded": sum(
                "raw_result" in p
                for w in report["study"]["witnesses"]
                for s in w["states"]
                for p in s["picks"].values()
            ),
            "elapsed_ms_including_instrumentation": elapsed,
        }
        report["study"]["end"] = _stamp()


def _pick(
    adapter: Any,
    xy: Sequence[float],
    target: Mapping[str, Any] | None,
    arm: str,
    budget: _Budget | None = None,
    handles: dict[str, Any] | None = None,
    record: dict[str, Any] | None = None,
    *,
    view: Any = None,
) -> dict[str, Any]:
    record = {} if record is None else record
    record.update(arm=arm, sheet_xy_m=list(xy), begin=_stamp())
    pick_started = time.perf_counter()
    draw = adapter.currentModel
    try:
        _invoke(budget, draw, "IModelDoc2", "ClearSelection2", True)
        extension = _invoke(budget, draw, "IModelDoc2", "Extension")
        callout = null_callout()
        record["select_begin"] = _stamp()
        started = time.perf_counter()
        try:
            record["raw_result"] = bool(
                _invoke(
                    budget,
                    extension,
                    "IModelDocExtension",
                    "SelectByID2",
                    "",
                    "EDGE",
                    xy[0],
                    xy[1],
                    0.0,
                    False,
                    0,
                    callout,
                    0,
                )
            )
        finally:
            record["select_ms"] = (time.perf_counter() - started) * 1000
            record["select_end"] = _stamp()
        started = time.perf_counter()
        with _timed("identity_reads_inclusive"):
            selection, entity, owner = _selected(
                draw, budget, adapter=adapter, view=view
            )
            record["selection"] = selection
            record["accepted_own_edge"] = (
                _identity(adapter, selection, entity, owner, target, budget)
                and record["raw_result"]
            )
        record["identity_ms"] = (time.perf_counter() - started) * 1000
        if handles is not None:
            handles.update(entity=entity, owner=owner)
        count = _value(selection, "count")
        same = _value(selection, "IsSame_edge")
        if not record["raw_result"] and count == 0:
            identity_class = "no-selection"
        elif selection.get("accepted_own_edge"):
            identity_class = "target"
        elif (
            count is not None
            and count > 0
            and selection.get("all_selection_items_recorded")
            and all(
                _value(item, "type") is not None and _value(item, "entity") is not None
                for item in selection["items"]
            )
            and (
                (same in (0, 1) and _value(selection, "owner") is not None)
                or _value(selection, "type") != 1
            )
        ):
            identity_class = "different-target"
        else:
            identity_class = "unreadable"
        record["selection_identity_class"] = identity_class
        record["selection_identity_readable"] = identity_class != "unreadable"
    except _Deadline:
        record["collection_error"] = (
            "soft study deadline during pick/identity observers"
        )
        raise
    except (_Nonfinite, TypeError, AssertionError):
        raise
    except Exception as exc:
        record["collection_error"] = _error(exc)
        record["accepted_own_edge"] = False
        record["selection_identity_class"] = "unreadable"
        record["selection_identity_readable"] = False
    finally:
        record["selection_with_identity_ms"] = (
            time.perf_counter() - pick_started
        ) * 1000
        _cost("selection_with_identity_inclusive", record["selection_with_identity_ms"])
    record["end"] = _stamp()
    return record


def _window_png(path: Path, hwnd: int) -> dict[str, Any]:
    from PIL import ImageGrab

    if not hwnd:
        raise RuntimeError(
            "main-window HWND unavailable; do not guess screenshot origin"
        )
    image = ImageGrab.grab(window=hwnd)
    image.save(path)
    return {
        "path": str(path),
        "image_size_px": list(image.size),
        "window_hwnd": hwnd,
        "method": "ImageGrab.grab(window=main_frame_hwnd)",
        "begin_or_end_not_atomic": True,
    }


def _field_failures(value: Any, prefix: str = "") -> list[dict[str, str]]:
    """Index honest per-field gaps without inventing substitutes for them."""
    gaps: list[dict[str, str]] = []
    if isinstance(value, dict):
        if value.get("status") in ("error", "unavailable"):
            gaps.append(
                {
                    "field": prefix,
                    "status": value["status"],
                    "reason": str(value.get("error", value.get("reason", ""))),
                }
            )
        for key, child in value.items():
            if key == "unavailable_or_error_fields":
                continue
            field = f"{prefix}.{key}" if prefix else str(key)
            if key.endswith("_error") and child:
                gaps.append({"field": field, "status": "error", "reason": str(child)})
            elif isinstance(child, (dict, list)):
                gaps.extend(_field_failures(child, field))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            gaps.extend(_field_failures(child, f"{prefix}[{index}]"))
    return gaps


def collect_and_stop(
    adapter: Any,
    view: Any,
    *,
    sheet_xy: Sequence[float],
    instance: str,
    point_mm: Sequence[float],
    baseline: Mapping[str, Any],
    immediate_repeat: Mapping[str, Any] | None,
    projection_inputs: Mapping[str, Any],
    capture_final: Callable[[str], Mapping[str, Any]],
) -> None:
    """Always tagged ordinary RuntimeError; cancellation skips all later captures."""
    collector_started = time.perf_counter()
    probe_id = uuid4().hex
    execution = {
        key: os.environ[key]
        for key in (
            "HARMONIC_FARM_BUILD_ID",
            "HARMONIC_FARM_RUN",
            "HARMONIC_FARM_COMMIT",
            "HARMONIC_WORKER_ID",
            "OTEL_SERVICE_INSTANCE_ID",
            "FARM_EXECUTION_ID",
            "FARM_LEAF_WORKFLOW_ID",
            "FARM_WORKFLOW_ID",
            "TRACEPARENT",
            "HARMONIC_BUILD_ID",
            "FARM_WORKER_ID",
        )
        if os.environ.get(key)
    }
    out_dir, path_budget = _path_plan(FAILURES, probe_id)
    performance: dict[str, Any] = {
        "costs": {},
        "operation_counts": {},
        "operation_count_scope": "instrumented _invoke calls plus explicit _zoomed_on/capture attempts; NOT a complete COM/redraw census; final callback internal calls excluded",
        "added_explicit_redraw_calls": 0,
        "leaf_execute_ms": None,
        "complete_balloon_selection_ms": None,
        "leaf_and_balloon_timing_status": "external telemetry required; diagnostic stops before balloon insertion/finalization/store",
        "native_input_identity_status": "parent must join farm prerequisite keys/execution digests; no native document hashing/reads added here",
        "r1_source": "b43c5a61175f4df940c47afafbe1bd9931d03663",
        "r1_worker_attempt": "w5attempt1",
        "r1_run": "20261020T124258353Z-a107808c625a43bbac86327d16c196cd",
        "baseline_selection_counts": {
            "original": 1,
            "immediate_exact_repeat": int(immediate_repeat is not None),
        },
        "selection_timing_scope": "baseline/raw repeat caller timings retained separately; added raw-selection cost includes postobserver pick plus study; not full balloon insertion",
        "r1_measured_phases_ms": {
            "baseline_raw_miss": 105.841,
            "immediate_raw_miss": 3.1183,
            "postobserver_miss": 17.2556,
            "collector": 15344.5,
            "leaf_execute": 71881,
            "final_bundle_failed": 62,
        },
        "r1_not_a_paired_baseline": "new experiment/workload, rebased source and uncontrolled worker/window phase; no speedup percentages",
        "instrumentation_change_ledger": [
            {
                "change": "final_capture_path_repair",
                "new_output": "short-label desktop/window PNG, native BMP and sheet PDF after study",
                "new_cost_entry": "final_capture_bundle",
                "baseline": "R1 failed in 62ms; successful path baseline unavailable",
                "absolute_delta_ms": None,
                "relative_delta": None,
                "comparison": "fail-to-success changed output; not a performance win",
            },
            {
                "change": "atomic_checkpoint_and_state_cadence",
                "new_output": "same-directory p.tmp then os.replace p.json after each state outside zoom",
                "new_cost_entry": "checkpoint_serialization/checkpoint_write/checkpoint_replace/checkpoint_total",
                "baseline": "R1 direct writes per witness, untimed; unmeasured, not zero",
                "absolute_delta_ms": None,
                "relative_delta": None,
                "comparison": "different payload/cadence; offline matched payload benchmarks would be separate",
            },
            {
                "change": "per_witness_spans_and_emissions",
                "new_output": "one child span per witness; 14 events, Pad 28; count attribute in finally",
                "new_cost_entry": "witness_span_setup_cleanup/telemetry_emission",
                "baseline": "R1 events on parent, untimed; unmeasured, not zero",
                "absolute_delta_ms": None,
                "relative_delta": None,
                "comparison": "setup/cleanup and emission measured; inclusive scope reported separately; no paired R1 delta",
            },
            {
                "change": "explicit_initial_fit",
                "new_output": "fit after original postobserver pick/PNG and before first study zoom",
                "new_cost_entry": "explicit_initial_fit",
                "baseline": "operation absent in R1 (not a measured successful equivalent)",
                "absolute_delta_ms": None,
                "relative_delta": None,
                "comparison": "added intervention cost measured directly, no paired speedup",
            },
        ],
    }
    report: dict[str, Any] = {
        "schema": 2,
        "experiment": "issue1667-fixed-sheet-xy-viewport-phase",
        "probe_id": probe_id,
        "begin": _stamp(),
        "execution_identity": execution,
        "execution_identity_available": bool(execution),
        "diagnostic_only_never_publish": True,
        "baseline": dict(baseline),
        "baseline_raw_result": bool(baseline.get("select_result")),
        "initial_selection_stage": "success_control_post_baseline"
        if baseline.get("select_result")
        else "post_immediate_miss_rawrepeat",
        "initial_selection": {"status": "not_yet_sampled"},
        "immediate_repeat": immediate_repeat,
        "original_sheet_xy_m": list(sheet_xy),
        "original_local_point_mm": list(point_mm),
        "intended_instance": instance,
        "original_numeric_inputs": {
            key: projection_inputs.get(key)
            for key in (
                "explode_offset_m",
                "model_points_m",
                "part_points_m",
                "component_transform",
                "retained_explode_offsets",
            )
        },
        "prebaseline_added_native_reads": 0,
        "complete": False,
        "errors": [],
        "artifact_directory": str(out_dir),
        "artifact_link": f"failures/{out_dir.name}/p.json",
        "path_budget": path_budget,
        "performance": performance,
        "preregistration": {
            "all_seven_required": True,
            "witness_order": list(PRIORITY),
            "blocks": [list(block) for block in BLOCKS],
            "requested_output_shifts": SHIFTS,
            "study_selection_count": PICK_CAP,
            "soft_budget_s": STUDY_SECONDS,
            "primary": "leverPad.original",
            "within_pad_control": "leverPad.plus8um",
            "other_witnesses": "secondary, adjudicated independently per point",
            "selection_classes": [
                "target",
                "no-selection",
                "different-target",
                "unreadable",
            ],
            "reversible_response": "all 8 A classes agree; both replicates of >=1 arm agree and differ from A; controls admitted",
            "no_response": "all 14 classes equal with controls admitted",
            "mixed_arms": "a reversible arm retains reversible primary label; report every nonreproducible arm separately",
            "pad_control_gate": "at least one exact own-edge hit across either fixed point in EACH block; +8um need not universally hit",
            "achieved_tolerance_output_units": ACHIEVED_TOLERANCE,
            "A_restoration_tolerance_output_units": A_RESTORATION_TOLERANCE,
            "scale_relative_tolerance": SCALE_RELATIVE_TOLERANCE,
            "matrix_tolerance": MATRIX_STABILITY_TOLERANCE,
            "no_posthoc_subset_or_substitution": True,
        },
        "evidence_limits": [
            "positive: outcome dependence on translation reported by IModelView.Transform; NOT an internal rounding/aperture mechanism",
            "scalar outputs remain transform-output units unless independent raster registration validates them",
            "D is an integer-shift request; phase-preserving labels apply ONLY to named floor / nearest-ties-even models",
            "B/C null expected under pixel-centre nearest quantization; null does not refute every viewport mechanism",
            "post-pick non-atomic controls can perturb timing/state and do not prove historical baseline pose",
            "bit-identical recorded transforms with different classes are a timing/redraw candidate, not proof of internal nondeterminism",
            "manual explode offsets are retained original numeric inputs; IsExploded does not prove continuous explode-step immutability",
            "block1 captures after picks/closing brackets are a known block asymmetry",
            "no production fix, recovery policy, paired R1 speedup, or absolute hit-test pixel convention established",
        ],
    }
    checkpoint = _Checkpoint(report, out_dir / "p.json", out_dir / "p.tmp")
    token = _PERFORMANCE.set(performance)
    primary_error: Exception | None = None
    cancellation: BaseException | None = None
    try:
        # FIRST added native reads on a hit; after the immediate raw repeat on a
        # miss. No clear or screenshot precedes this preserved selection.
        selection, entity, owner = _selected(
            adapter.currentModel, adapter=adapter, view=view
        )
        report["initial_selection"] = selection
        checkpoint()
        utility = _invoke(None, adapter.swApp, "ISldWorks", "GetMathUtility")
        points = projection_inputs.get("model_points_m") or ()
        if not points:
            raise RuntimeError("original assembly-space projection input missing")
        _linear(projection_inputs.get("component_transform"))
        snapshot, reference = _snapshot(
            adapter,
            view,
            utility,
            points[0],
            sheet_xy,
            projection_inputs.get("model_to_view_transform_handle"),
        )
        report["post_raw_snapshot"] = snapshot
        control = _value(snapshot, "fresh_transform_control") or {}
        report["original_point_in_fresh_matrix"] = (
            _apply(control["array"], points[0])[:2].tolist()
            if control.get("valid")
            else None
        )
        if report["original_point_in_fresh_matrix"] is not None:
            report["fresh_minus_original_sheet_xy_m"] = [
                report["original_point_in_fresh_matrix"][i] - sheet_xy[i]
                for i in range(2)
            ]
        source = _source_witnesses()
        report["source_witnesses"] = source
        report["source_authority"] = {}
        for filename in (
            "_drawing_sm_pose_diagnostic.py",
            "_drawing_balloons.py",
            "draw_sm_summing_assembly.py",
            "sm_summing_lever_spec.py",
            "sm_knife_mount_spec.py",
            "build_sm_summing_lever.py",
            "build_sm_knife_mount.py",
            "build_sm_summing_assembly.py",
        ):
            _observe(
                report["source_authority"],
                filename,
                lambda name=filename: hashlib.sha256(
                    Path(__file__).with_name(name).read_bytes()
                ).hexdigest(),
            )
        discovered = _discover(
            adapter,
            view,
            utility,
            projection_inputs,
            source,
            report,
            reference,
            _value(snapshot, "ReferencedConfiguration"),
        )
        _identity(adapter, selection, entity, owner, discovered.get("leverPad"))
        report["baseline_own_target_positive_control"] = bool(
            baseline.get("select_result") and selection.get("accepted_own_edge")
        )
        report["postobserver_exact_oldXY_repeat"] = _pick(
            adapter,
            sheet_xy,
            discovered.get("leverPad"),
            "postobserver_exact_oldXY",
            view=view,
        )
        viewport = _viewport(adapter, utility, sheet_xy)
        report["original_zoom_capture_mapping"] = viewport
        _invoke(None, adapter.currentModel, "IModelDoc2", "ClearSelection2", True)
        report["original_zoom_postobserver_png"] = _capture_png(
            report,
            "original_png",
            _value(viewport, "main_window_hwnd") or 0,
        )
        # Every witness is identified/frozen BEFORE the first viewport intervention.
        witnesses = [discovered[key] for key in PRIORITY if key in discovered]
        report["unique_edge_identity_checks"] = []
        for index, left in enumerate(witnesses):
            for right in witnesses[index + 1 :]:
                check = {"left": left["id"], "right": right["id"]}
                _observe(
                    check,
                    "IsSame",
                    lambda a=left, b=right: int(
                        _invoke(
                            None,
                            adapter.swApp,
                            "ISldWorks",
                            "IsSame",
                            a["edge"],
                            b["edge"],
                        )
                    ),
                )
                report["unique_edge_identity_checks"].append(check)
        report["frozen_witnesses"] = [
            {
                key: witness[key]
                for key in (
                    "id",
                    "family",
                    "instance",
                    "point_local_m",
                    "endpoints_local_m",
                    "source_refs",
                    "native_geometry",
                    "values",
                    "validated",
                )
            }
            | {"explode_offset_m": witness["offset"].tolist()}
            for witness in witnesses
        ]
        report["pose_reference"] = {
            "stage": "first_post_pick_view_snapshot_and_required_component_discovery; sequential_not_atomic",
            "view_transform_control": snapshot.get("fresh_transform_control"),
            "ReferencedConfiguration": snapshot.get("ReferencedConfiguration"),
            "IsExploded": snapshot.get("IsExploded"),
            "components": {
                w["instance"]: w["snapshot"]["post_pick_transforms"]["Transform2"]
                for w in witnesses
            },
        }
        prereg = report["preregistration"]
        prereg.update(
            discovered_order=[w["id"] for w in witnesses],
            missing_witnesses=[key for key in PRIORITY if key not in discovered],
            source_native_metrology_valid=bool(
                len(witnesses) == 7
                and control.get("valid")
                and all(w["validated"] for w in witnesses)
                and not report["discovery"].get("truncated")
                and all(
                    _value(check, "IsSame") == 0
                    for check in report["unique_edge_identity_checks"]
                )
            ),
        )
        if prereg["source_native_metrology_valid"]:
            frozen = _freeze_points(witnesses, control["array"], sheet_xy)
            report["frozen_points"] = frozen
            checkpoint()
            _phase_study(adapter, view, utility, witnesses, frozen, report, checkpoint)
        else:
            report["study_refusal"] = (
                "all seven unique source witnesses and native transform controls required; no reduced set/substitutions"
            )
        by_id = {w["id"]: w for w in report.get("study", {}).get("witnesses", [])}
        report["endpoints"] = {
            key: by_id[key]["endpoints"]
            if key in by_id
            else {
                "original": {
                    "label": "incomplete",
                    "admitted": False,
                    "missing_metadata": ["witness not reached"],
                }
            }
            for key in PRIORITY
        }
        report["primary_endpoint"] = report["endpoints"]["leverPad"]["original"]
        report["preregistered_evidence_sufficient"] = report["primary_endpoint"][
            "admitted"
        ]
        study = report.get("study", {})
        report["complete"] = bool(
            len(by_id) == 7
            and study.get("budget", {}).get("raw_results_recorded") == PICK_CAP
            and all(
                len(w["states"]) == 14
                and all("after" in state for state in w["states"])
                for w in by_id.values()
            )
            and not study.get("truncated")
        )
    except Exception as exc:
        primary_error = exc
        report["errors"].append(
            {"stage": "collection", "error": _error(exc), **_stamp()}
        )
        report["complete"] = False
    except BaseException as exc:
        cancellation = exc
        report["cancelled"] = True
        report["complete"] = False
    finally:
        try:
            _invoke(None, adapter.currentModel, "IModelDoc2", "ClearSelection2", True)
        except BaseException as exc:
            report["errors"].append(
                {"stage": "final_clear", "error": _error(exc), **_stamp()}
            )
            report["complete"] = False
            if cancellation is not None:
                cancellation.add_note(f"final selection clear also failed: {exc!r}")
            elif not isinstance(exc, Exception):
                cancellation = exc
                report["cancelled"] = True
            elif primary_error is None:
                primary_error = exc
        if cancellation is None and not isinstance(
            primary_error, (_Nonfinite, TypeError, AssertionError)
        ):
            final_paths = [
                v for key, v in path_budget["paths"].items() if key.startswith("final.")
            ]
            if all(v["safe"] for v in final_paths):
                _count("final_capture_bundle_attempts")
                try:
                    with _timed("final_capture_bundle"):
                        _observe(
                            report,
                            "final_poststudy_capture_bundle",
                            lambda: dict(capture_final(path_budget["final_label"])),
                        )
                except BaseException as exc:
                    if isinstance(exc, Exception):
                        report["errors"].append(
                            {"stage": "final_capture", "error": _error(exc), **_stamp()}
                        )
                        if primary_error is None:
                            primary_error = exc
                    else:
                        cancellation = exc
                        report["cancelled"] = True
                    report["complete"] = False
            else:
                report["final_poststudy_capture_bundle"] = {
                    "status": "refused",
                    "reason": "planned final bundle path exceeds conservative budget",
                    "unsafe_paths": [v for v in final_paths if not v["safe"]],
                }
        report["end"] = _stamp()
        performance["collector_elapsed_ms_before_final_checkpoint"] = (
            time.perf_counter() - collector_started
        ) * 1000
        report["unavailable_or_error_fields"] = _field_failures(report)
        # Primary endpoint is never gated by completion of later secondary witnesses
        # or by optional captures. Exceptional partial studies still expose per-point data.
        if "primary_endpoint" not in report:
            reached = {w["id"]: w for w in report.get("study", {}).get("witnesses", [])}
            report["endpoints"] = {
                key: value.get("endpoints", {}) for key, value in reached.items()
            }
            report["primary_endpoint"] = (
                report["endpoints"]
                .get("leverPad", {})
                .get(
                    "original",
                    {
                        "label": "incomplete",
                        "admitted": False,
                        "missing_metadata": ["primary not reached"],
                    },
                )
            )
            report["preregistered_evidence_sufficient"] = report["primary_endpoint"][
                "admitted"
            ]
        try:
            checkpoint(final=True)  # One final attempt, even after a prior OSError.
        except Exception as exc:
            report["artifact_serialization_or_programming_error"] = _error(exc)
            report["complete"] = False
            with contextlib.suppress(Exception):
                _telemetry.warn(
                    f"[1667] FINAL checkpoint not serialized: {exc}", probe_id=probe_id
                )
            if cancellation is not None:
                cancellation.add_note(f"final checkpoint also failed: {exc!r}")
            elif primary_error is None:
                primary_error = exc
            else:
                primary_error.add_note(f"final checkpoint also failed: {exc!r}")
        finally:
            _event(
                "cancelled" if cancellation is not None else "stop",
                report,
                json_path=str(checkpoint.path),
                baseline_raw_result=report["baseline_raw_result"],
                complete=report["complete"],
                primary_label=report["primary_endpoint"]["label"],
                study_picks=report.get("study", {})
                .get("budget", {})
                .get("study_selection_attempts", 0),
                collector_elapsed_ms_to_stop_event=(
                    time.perf_counter() - collector_started
                )
                * 1000,
                checkpoint_final_attempt=json.dumps(
                    report["checkpoint"]["attempts"][-1], allow_nan=False
                ),
            )
            _PERFORMANCE.reset(token)
    if cancellation is not None:
        raise cancellation
    raise RuntimeError(
        f"{STOP} baseline_raw={report['baseline_raw_result']} complete={report['complete']} "
        f"primary={report['primary_endpoint']['label']} "
        f"evidence_sufficient={report['preregistered_evidence_sufficient']} artifact={checkpoint.path}"
    ) from primary_error
