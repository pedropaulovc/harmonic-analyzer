"""TEMPORARY issue1667 SM acceptance-locus experiment; never a recovery path.

Imported only inside the original pick zoom, after the baseline (and a miss's
immediate unchanged raw repeat). Every observation is post-pick, non-atomic,
and potentially perturbing. This module always stops the drawing before save.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

import numpy as np
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks import drawing as sw_drawing

from _com import _bind, _com_invoke, _early_bound
from _drawing_pick_diagnostic import _array
from _drawing_scan import _HIT_ZOOM_HALF, _zoomed_on
import _telemetry
import sm_knife_mount_spec as mount_spec
import sm_summing_lever_spec as lever_spec

STOP = "ISSUE1667_POSE_DIAGNOSTIC_STOP"
PRIORITY = (
    "controlY", "leverNear", "leverFarMidrib", "controlX",
    "leverPlateEnd", "leverPad", "controlZ",
)
STEP_M = 8e-6
OFFSETS_M = tuple(index * STEP_M for index in range(-12, 13))
DISCOVERY_SECONDS = 60.0
SCAN_SECONDS = 180.0
PICK_CAP = 203  # seven fixed 25-point grids plus four boundary repeats each
GRID_PICK_CAP = 175
EDGE_CAP = 1024
COMPONENT_CAP = 128
SOURCE_TOLERANCE_M = 5e-6
TRANSFORM_TOLERANCE_M = 1e-10
FRESH_XY_THRESHOLD_M = 1e-10
SCALE_RELATIVE_TOLERANCE = 1e-6
MATRIX_STABILITY_TOLERANCE = 1e-10
FAILURES = Path(__file__).resolve().parents[1] / "out" / "reports" / "failures"


def _stamp() -> dict[str, Any]:
    return {"utc": datetime.now(UTC).isoformat(), "monotonic_ns": time.perf_counter_ns()}


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
        return _com_invoke(obj, interface, member, *args)

    def report(self) -> dict[str, Any]:
        return {"soft_limit_s": self.seconds, "elapsed_s": time.perf_counter() - self.start,
                "calls": self.calls, "last_checkpoint": self.last_checkpoint,
                "hung_COM_call_not_interrupted": True}


def _invoke(
    budget: _Budget | None, obj: Any, interface: str, member: str, *args: Any
) -> Any:
    return (budget.call(obj, interface, member, *args) if budget is not None
            else _com_invoke(obj, interface, member, *args))


def _numbers(budget: _Budget | None, obj: Any, interface: str) -> tuple[float, ...]:
    if obj is None:
        raise RuntimeError(f"{interface} handle is null")
    values = _invoke(budget, obj, interface, "ArrayData")
    if values is None:
        raise RuntimeError(f"{interface}.ArrayData is null")
    return tuple(float(value) for value in values)


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
    except Exception as exc:
        field.update(status="error", error=_error(exc))
        return None
    finally:
        field["end"] = _stamp()


def _value(record: Mapping[str, Any], key: str) -> Any:
    return record.get(key, {}).get("value")


def _event(stage: str, report: Mapping[str, Any], **fields: Any) -> None:
    # Full matrices/maps live in JSON; never put an oversized report in OTel.
    with contextlib.suppress(Exception):
        _telemetry.event(f"drawing.sm_pose.{stage}", probe_id=report["probe_id"], **fields)


def _native_point(
    utility: Any, transform: Any, point: Sequence[float], budget: _Budget | None = None
) -> tuple[float, ...]:
    native = _invoke(budget, utility, "IMathUtility", "CreatePoint", double_array(list(point)))
    if native is None:
        raise RuntimeError("CreatePoint returned null")
    result = _invoke(budget, native, "IMathPoint", "MultiplyTransform", transform)
    coordinates = _numbers(budget, result, "IMathPoint")
    if len(coordinates) != 3 or not all(math.isfinite(v) for v in coordinates):
        raise RuntimeError("MultiplyTransform returned incomplete/nonfinite coordinates")
    return coordinates


def _linear(values: Sequence[float]) -> np.ndarray:
    # Existing _drawing_balloons._anchor_model_points and
    # draw_fr_frame_assembly._transform_point use THIS layout including scale.
    # IMathTransform.ArrayData docs: rotation[0:9], translation[9:12], scale[12].
    data = np.asarray(values, dtype=float)
    if data.shape != (16,) or not np.isfinite(data).all() or data[12] == 0:
        raise ValueError("MathTransform must contain 16 finite values and nonzero scale")
    return data[:9].reshape(3, 3).T * data[12]


def _apply(values: Sequence[float], point: Sequence[float]) -> np.ndarray:
    return _linear(values) @ np.asarray(point, dtype=float) + np.asarray(values[9:12])


def _verified_transform(
    utility: Any, transform: Any, point: Sequence[float], budget: _Budget | None = None
) -> dict[str, Any]:
    """Fresh-handle metrology control, NOT a historical-immutability claim."""
    result: dict[str, Any] = {"begin": _stamp(), "valid": False,
        "layout_source": "_drawing_balloons._anchor_model_points; draw_fr_frame_assembly._transform_point",
        "absolute_tolerance_output_units": TRANSFORM_TOLERANCE_M,
        "non_atomic": True, "historical_immutability_proven": False}
    before = _numbers(budget, transform, "IMathTransform")
    result["array"] = before
    # One recorded point plus a full 3D affine basis discriminates transpose,
    # missing scale and translation. Fixed-size positive control, no searching.
    points = [tuple(point), (0.0, 0.0, 0.0), (0.001, 0.0, 0.0),
              (0.0, 0.001, 0.0), (0.0, 0.0, 0.001)]
    result["samples"] = []
    for sample in points:
        native = _native_point(utility, transform, sample, budget)
        analytic = _apply(before, sample)
        discrepancy = float(np.max(np.abs(analytic - native)))
        result["samples"].append({"input": sample, "native": native,
            "analytical": analytic.tolist(), "max_absolute_disagreement": discrepancy})
    after = _numbers(budget, transform, "IMathTransform")
    result["array_after_control"] = after
    result["handle_array_stable_during_control"] = before == after
    result["valid"] = (before == after and all(
        sample["max_absolute_disagreement"] <= TRANSFORM_TOLERANCE_M
        for sample in result["samples"]))
    result["end"] = _stamp()
    return result


def _selected(draw: Any, budget: _Budget | None = None) -> tuple[dict[str, Any], Any, Any]:
    """The hit branch's FIRST native observers; never clear selection here."""
    record: dict[str, Any] = {"stage": "post_raw_before_any_clear", "begin": _stamp()}
    manager = _observe(record, "manager", lambda: _invoke(budget, draw, "IModelDoc2", "SelectionManager"))
    # Proxies live only on the stack, never in the artifact.
    if manager is not None:
        record["manager"]["value"] = "ISelectionMgr handle retained locally"
    count = _observe(record, "count", lambda: int(_invoke(budget, manager, "ISelectionMgr", "GetSelectedObjectCount2", -1)))
    entity = owner = None
    if count and count > 0:
        kind = _observe(record, "type", lambda: int(_invoke(budget, manager, "ISelectionMgr", "GetSelectedObjectType3", count, -1)))
        entity = _observe(record, "entity", lambda: _invoke(budget, manager, "ISelectionMgr", "GetSelectedObject6", count, -1))
        if entity is not None:
            record["entity"]["value"] = "selected native entity handle retained locally"
        if kind in (1, 2, 3) and entity is not None:
            if budget is not None:
                budget.check("selected IEntity.GetComponent binding")
            owner = _observe(record, "owner_handle", lambda: _invoke(
                budget, _early_bound(_bind(entity, "IEntity"), "IEntity"), "IEntity", "GetComponent"))
            if owner is not None:
                record["owner_handle"]["value"] = "IComponent2 handle retained locally"
            _observe(record, "owner", lambda: str(_invoke(budget, owner, "IComponent2", "Name2")).replace("\\", "/") if owner is not None else None)
    record["end"] = _stamp()
    return record, entity, owner


def _identity(adapter: Any, selected: dict[str, Any], entity: Any, owner: Any,
              target: Mapping[str, Any] | None, budget: _Budget | None = None) -> bool:
    if target is None or entity is None:
        selected["identity_unavailable"] = "no identified intended straight target or selected entity"
        selected["accepted_own_edge"] = False
        return False
    same = _observe(selected, "IsSame_edge", lambda: int(_invoke(budget, adapter.swApp, "ISldWorks", "IsSame", entity, target["edge"])))
    owner_same = _observe(selected, "IsSame_owner", lambda: int(_invoke(budget, adapter.swApp, "ISldWorks", "IsSame", owner, target["component"])))
    accepted = (_value(selected, "count") == 1 and _value(selected, "type") == 1
                and same == 1 and owner_same == 1
                and str(_value(selected, "owner") or "").casefold() == target["instance"].casefold())
    selected["accepted_own_edge"] = accepted
    selected["target_id"] = target["id"]
    return accepted


def _window_geometry(view_hwnd: int, frame_hwnd: int) -> dict[str, Any]:
    """Read-only Win32 registration. No assumed origin, DPI, or bitmap centre."""
    import ctypes
    from ctypes import wintypes

    user = ctypes.WinDLL("user32", use_last_error=True)
    specs = (
        ("GetClientRect", (wintypes.HWND, ctypes.POINTER(wintypes.RECT)), wintypes.BOOL),
        ("ClientToScreen", (wintypes.HWND, ctypes.POINTER(wintypes.POINT)), wintypes.BOOL),
        ("GetWindowRect", (wintypes.HWND, ctypes.POINTER(wintypes.RECT)), wintypes.BOOL),
        ("GetDpiForWindow", (wintypes.HWND,), wintypes.UINT),
        ("GetThreadDpiAwarenessContext", (), wintypes.HANDLE),
        ("GetWindowDpiAwarenessContext", (wintypes.HWND,), wintypes.HANDLE),
        ("GetAwarenessFromDpiAwarenessContext", (wintypes.HANDLE,), ctypes.c_int),
        ("GetWindowThreadProcessId", (wintypes.HWND, ctypes.POINTER(wintypes.DWORD)), wintypes.DWORD),
    )
    state: dict[str, Any] = {"coordinate_units": "Win32 caller-context pixels; device/logical equivalence gated below"}
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
        if not (user.GetClientRect if client else user.GetWindowRect)(hwnd, ctypes.byref(rect)):
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
        context = (user.GetThreadDpiAwarenessContext() if hwnd is None
                   else user.GetWindowDpiAwarenessContext(hwnd))
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
    state["seat_process_awareness_unavailable"] = "window awareness read, not a process-wide GetProcessDpiAwareness probe"
    state["device_pixel_registration_available"] = bool(
        _value(state, "view_client_rect_px") and _value(state, "view_client_screen_origin_px")
        and _value(state, "grabbed_main_window_rect_px")
        and _value(state, "view_dpi") == _value(state, "main_window_dpi")
        and _value(state, "view_dpi") is not None
        and (_value(state, "caller_thread_dpi_awareness") or {}).get("awareness") == 2
        and (_value(state, "seat_window_dpi_awareness") or {}).get("awareness") == 2)
    state["registration_uncertainty_px"] = None
    state["registration_uncertainty_unavailable"] = "native-vs-raster edge registration not independently measured"
    return state


def _frame_hwnd(adapter: Any, budget: _Budget | None = None) -> int:
    frame = _invoke(budget, adapter.swApp, "ISldWorks", "Frame")
    if budget is not None:
        budget.check("IFrame early binding")
    return int(_invoke(budget, _early_bound(_bind(frame, "IFrame"), "IFrame"), "IFrame", "GetHWndx64"))


def _viewport(
    adapter: Any, utility: Any, sheet_xy: Sequence[float], budget: _Budget | None = None
) -> dict[str, Any]:
    state: dict[str, Any] = {"begin": _stamp(), "stage": "post_pick_non_atomic"}
    viewport = _invoke(budget, adapter.currentModel, "IModelDoc2", "ActiveView")
    for member in ("Scale2", "FrameLeft", "FrameTop", "FrameWidth", "FrameHeight", "FrameState"):
        _observe(state, member, lambda m=member: _invoke(budget, viewport, "IModelView", m))
    _observe(state, "Transform_control", lambda: _verified_transform(
        utility, _invoke(budget, viewport, "IModelView", "Transform"), (*sheet_xy, 0.0), budget))
    for member, interface in (("Orientation3", "IMathTransform"), ("Translation3", "IMathVector")):
        _observe(state, member, lambda m=member, i=interface: _numbers(budget, _invoke(budget, viewport, "IModelView", m), i))
    if budget is not None:
        budget.check("IModelView HWND early binding")
    hwnd = _observe(state, "view_hwnd", lambda: int(_invoke(
        budget, _early_bound(_bind(viewport, "IModelView"), "IModelView"), "IModelView", "GetViewHWndx64")))
    frame = _observe(state, "main_window_hwnd", lambda: _frame_hwnd(adapter, budget))
    if budget is not None:
        budget.check("Win32 geometry observer bundle")
    _observe(state, "windows", lambda: _window_geometry(hwnd or 0, frame or 0))
    state["end"] = _stamp()
    return state


def _snapshot(adapter: Any, view: Any, utility: Any, point: Sequence[float],
              sheet_xy: Sequence[float], retained: Any = None) -> tuple[dict[str, Any], Any]:
    state: dict[str, Any] = {"begin": _stamp(), "stage": "post_pick_non_atomic"}
    for member in ("ReferencedConfiguration", "IsExploded", "GetName2"):
        _observe(state, member, lambda m=member: _com_invoke(view, "IView", m))
    reference = _observe(state, "ReferencedDocument", lambda: _com_invoke(view, "IView", "ReferencedDocument"))
    if reference is not None:
        state["ReferencedDocument"]["value"] = "referenced IModelDoc2 handle retained locally"
        _observe(state, "reference_path", lambda: str(_com_invoke(reference, "IModelDoc2", "GetPathName")))
        _observe(state, "reference_title", lambda: str(_com_invoke(reference, "IModelDoc2", "GetTitle")))
    if retained is not None:
        _observe(state, "retained_handle_deferred_ArrayData", lambda: _array(retained, "IMathTransform"))
    else:
        state["retained_handle_deferred_ArrayData"] = {"status": "unavailable", "reason": "no preprojection handle retained"}
    state["retained_handle_semantics"] = "DEFERRED post-pick read; copy/live behavior undocumented; NOT the original numeric matrix"
    fresh = _observe(state, "fresh_transform_handle", lambda: _com_invoke(view, "IView", "ModelToViewTransform"))
    if fresh is not None:
        state["fresh_transform_handle"]["value"] = "fresh IMathTransform handle retained locally"
    _observe(state, "fresh_transform_control", lambda: _verified_transform(utility, fresh, point))
    _observe(state, "viewport", lambda: _viewport(adapter, utility, sheet_xy))
    state["end"] = _stamp()
    return state, reference


def _source_witnesses() -> dict[str, dict[str, Any]]:
    # Frozen source study sm-witness-design/report.json. No builder import.
    # Builder-only expressions are mirrored explicitly, with file/line authority.
    s = lever_spec
    w, length, thickness = s.PLATE_W, s.PLATE_L, s.PLATE_T
    radius = s.CYL_R + 0.1 * s.MM_PER_IN  # build_sm_summing_lever:159-161,206
    rib_thickness = 0.2 * s.MM_PER_IN  # build_sm_summing_lever:160
    reach = s.HOLE_X - 4.1  # build_sm_summing_lever:222
    slope = radius / math.sqrt(s.SUM_H ** 2 - radius ** 2)
    rib_start = (-radius ** 2 / s.SUM_H,
                 radius * math.sqrt(1 - radius ** 2 / s.SUM_H ** 2), rib_thickness / 2)
    rib_end = (-s.SUM_H + (thickness / 2) / slope, thickness / 2, rib_thickness / 2)
    hx, bottom, z = mount_spec.BLK_HALF_X, mount_spec.BLK_BOT, mount_spec.SUPPORT_Z_THICK / 2
    top = 999.7 - (979.7 + s.HEX_H / 2)  # exact builder:135-139, NOT rounded BLK_TOP
    definitions = (
        ("leverNear", "lever", (s.HEX_W / 2, s.HEX_H / 4, length / 2 + s.HEX_DEPTH / 2),
         (s.HEX_W / 2, s.HEX_H / 4, length / 2), (s.HEX_W / 2, s.HEX_H / 4, length / 2 + s.HEX_DEPTH),
         "build_sm_summing_lever.py:524-595,675-689; sm_summing_lever_spec.py:42-54"),
        ("leverPad", "lever", (w, thickness / 2 - s.SPRING_SEAT_T, 0),
         (w, thickness / 2 - s.SPRING_SEAT_T, -length / 2), (w, thickness / 2 - s.SPRING_SEAT_T, length / 2),
         "build_sm_summing_lever.py:337-427; sm_summing_lever_spec.py:137-146"),
        ("leverFarMidrib", "lever", (-60.0, slope * (s.SUM_H - 60.0), rib_thickness / 2),
         rib_start, rib_end, "build_sm_summing_lever.py:979-1008,1053-1063,927-976"),
        ("leverPlateEnd", "lever", ((reach + w) / 2, thickness / 2, length / 2),
         (reach, thickness / 2, length / 2), (w, thickness / 2, length / 2),
         "build_sm_summing_lever.py:337-370,222-237,743-841"),
        ("controlY", "control", (hx, 0, z), (hx, bottom, z), (hx, top, z),
         "build_sm_knife_mount.py:112-148,270-345; sm_knife_mount_spec.py:36-45"),
        ("controlX", "control", (0, bottom, z), (-hx, bottom, z), (hx, bottom, z),
         "build_sm_knife_mount.py:270-345"),
        ("controlZ", "control", (hx, bottom, 0), (hx, bottom, -z), (hx, bottom, z),
         "build_sm_knife_mount.py:270-345"),
    )
    result = {}
    for key, family, point, start, end, source in definitions:
        result[key] = {"id": key, "family": family,
            "point_local_m": [v / 1000 for v in point],
            "endpoints_local_m": [[v / 1000 for v in endpoint] for endpoint in (start, end)],
            "source_refs": source, "source_coordinate_units": "part-local metres",
            "radius_to_knife_axis_m": math.hypot(point[0], point[1] - s.HEX_H / 2) / 1000 if family == "lever" else None}
    return result


def _component_snapshot(component: Any, utility: Any, point: Sequence[float], budget: _Budget) -> dict[str, Any]:
    state: dict[str, Any] = {}
    for key, member, args in (("Transform2", "Transform2", ()),
                              ("GetTotalTransform_false", "GetTotalTransform", (False,)),
                              ("GetTotalTransform_true", "GetTotalTransform", (True,)),
                              ("PresentationTransform", "PresentationTransform", ())):
        _observe(state, key, lambda m=member, a=args: _numbers(budget, budget.call(component, "IComponent2", m, *a), "IMathTransform"))
    handle = budget.call(component, "IComponent2", "Transform2")
    _observe(state, "fresh_Transform2_control", lambda: _verified_transform(utility, handle, point, budget))
    state["presentation_warning"] = "read only; no enable/set; total transform is not independent drawing-pose proof"
    return state


def _discover(adapter: Any, view: Any, utility: Any, inputs: Mapping[str, Any],
              source: Mapping[str, Any], report: dict[str, Any], reference: Any,
              configuration_name: Any) -> dict[str, dict[str, Any]]:
    budget = _Budget(DISCOVERY_SECONDS)
    record: dict[str, Any] = {"begin": _stamp(), "components": [], "edge_scans": [],
        "truncated": False, "component_cap": COMPONENT_CAP, "edge_cap_per_component": EDGE_CAP,
        "coordinate_convention": "existing _visible_edge_points treats view edge geometry as part metres; strict source-endpoint compatibility required"}
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
            path = _observe(item, "referenced_path", lambda: str(budget.call(leaf.component, "IComponent2", "GetPathName")))
            stem = Path(path.replace("\\", "/")).stem.casefold() if path else ""
            family = {"sm-summing-lever": "lever", "sm-knife-mount": "control"}.get(stem)
            if family is None:
                continue
            item["family"] = family
            state = _component_snapshot(leaf.component, utility, source["leverPad"]["point_local_m"], budget)
            item["post_pick_transforms"] = state
            values = _value(state, "Transform2")
            if values is None:
                continue
            offset = np.zeros(3)
            offsets = inputs.get("retained_explode_offsets", {})
            parts = leaf.path.split("/")
            for count in range(1, len(parts) + 1):
                offset += offsets.get("/".join(parts[:count]).casefold(), (0., 0., 0.))
            item["retained_explode_offset_m"] = offset.tolist()
            item["base_origin_m"] = _apply(values, (0., 0., 0.)).tolist()
            item["source_expected_placement_rotation"] = "identity at authored parked pose; actual free rock is not replaced"
            item["actual_linear_minus_identity_max"] = float(np.max(np.abs(_linear(values) - np.eye(3))))
            checked = _value(state, "fresh_Transform2_control") or {}
            same_numeric_input = values == checked.get("array")
            item["geometry_matrix_is_native_validated_matrix"] = same_numeric_input
            candidates[family].append({"component": leaf.component, "instance": leaf.path,
                "values": values, "offset": offset, "snapshot": item,
                "validated": bool(checked.get("valid") and same_numeric_input)})
        record["family_counts"] = {key: len(items) for key, items in candidates.items()}
        if len(candidates["lever"]) == 1:
            lever_values = candidates["lever"][0]["values"]
            knife_origin = _apply(lever_values, (0., lever_spec.HEX_H / 2000, 0.))
            knife_axis = _linear(lever_values) @ np.array([0., 0., 1.])
            knife_axis /= np.linalg.norm(knife_axis)
            record["knife_axis_source_crosscheck"] = {
                "source": "build_sm_summing_assembly.py:641-662,765-818",
                "reported_axis_origin_assembly_m": knife_origin.tolist(),
                "reported_axis_unit_assembly": knife_axis.tolist(),
                "mounts": [],
            }
            for mount in candidates["control"]:
                delta = np.asarray(mount["snapshot"]["base_origin_m"]) - knife_origin
                record["knife_axis_source_crosscheck"]["mounts"].append({
                    "instance": mount["instance"],
                    "signed_axis_station_m": float(delta @ knife_axis),
                    "distance_to_reported_knife_line_m": float(np.linalg.norm(delta - (delta @ knife_axis) * knife_axis)),
                    "expected_authored_relation": "mount base origin on lever theoretical knife line before explode",
                })
        # Configuration-root observations are separately identified and nonloading.
        root_record: dict[str, Any] = {"GetRootComponent3_resolve": False, "components_examined": 0}
        record["configuration_root"] = root_record
        if reference is not None and configuration_name:
            config = budget.call(reference, "IModelDoc2", "GetConfigurationByName", configuration_name)
            root = _observe(root_record, "root", lambda: budget.call(config, "IConfiguration", "GetRootComponent3", False))
            if root is not None:
                root_record["root"]["value"] = "nonloading configuration-root component handle"
                pending = list(budget.call(root, "IComponent2", "GetChildren") or ())
                root_record["matches"] = []
                while pending and root_record["components_examined"] < COMPONENT_CAP:
                    component = pending.pop()
                    root_record["components_examined"] += 1
                    path = str(budget.call(component, "IComponent2", "GetPathName") or "")
                    if Path(path.replace("\\", "/")).stem.casefold() == "sm-summing-lever":
                        root_record["matches"].append({"instance": str(budget.call(component, "IComponent2", "Name2")),
                            "referenced_path": path, "post_pick_transforms": _component_snapshot(component, utility, source["leverPad"]["point_local_m"], budget)})
                    pending.extend(budget.call(component, "IComponent2", "GetChildren") or ())
                root_record["truncated"] = bool(pending)
            else:
                root_record["unavailable"] = "GetRootComponent3(False) null; may be inactive; never resolve/load/activate"
        else:
            root_record["unavailable"] = "referenced document/configuration unavailable"

        def edges_for(component: dict[str, Any], family: str) -> dict[str, dict[str, Any]]:
            scan: dict[str, Any] = {"instance": component["instance"], "family": family,
                "examined": 0, "errors": [], "matches": {}, "truncated": False}
            record["edge_scans"].append(scan)
            count = int(budget.call(view, "IView", "GetVisibleEntityCount2", component["component"], 1) or 0)
            scan["reported_total"] = count
            if count > EDGE_CAP:
                scan.update(truncated=True, unavailable="visible edge count exceeds fixed cap; no enumeration")
                return {}
            budget.check("raw_visible_entities")
            edges = sw_drawing.raw_visible_entities(view, component["component"], 1)
            scan["returned_total"] = len(edges)
            scan["truncated"] = len(edges) > EDGE_CAP
            matches: dict[str, list[tuple[Any, Any]]] = {key: [] for key, w in source.items() if w["family"] == family}
            for edge in edges[:EDGE_CAP]:
                budget.check("visible straight edge")
                scan["examined"] += 1
                try:
                    curve = budget.call(edge, "IEdge", "GetCurve")
                    if curve is None or not budget.call(curve, "ICurve", "IsLine"):
                        continue
                    params = tuple(float(v) for v in (budget.call(edge, "IEdge", "GetCurveParams2") or ()))
                    if len(params) < 6 or not all(math.isfinite(v) for v in params[:6]):
                        raise ValueError("edge has incomplete/nonfinite endpoints")
                    ends = np.asarray(params[:6]).reshape(2, 3)
                    for key in matches:
                        expected = np.asarray(source[key]["endpoints_local_m"])
                        discrepancy = min(float(np.max(np.linalg.norm(ends - expected, axis=1))),
                                          float(np.max(np.linalg.norm(ends[::-1] - expected, axis=1))))
                        if discrepancy <= SOURCE_TOLERANCE_M:
                            budget.check("GetComponent identity")
                            owner = _early_bound(_bind(edge, "IEntity"), "IEntity").GetComponent()
                            if int(budget.call(adapter.swApp, "ISldWorks", "IsSame", owner, component["component"])) != 1:
                                raise ValueError("edge owner identity not exact")
                            if int(budget.call(adapter.swApp, "ISldWorks", "IsSame", edge, edge)) != 1:
                                raise ValueError("native edge identity unavailable")
                            matches[key].append((edge, {"raw_curve_params_first6_m": params[:6],
                                "source_endpoint_max_error_m": discrepancy, "IsLine": True,
                                "IsSame_owner": 1, "IsSame_self": 1}))
                except _Deadline:
                    raise
                except Exception as exc:
                    scan["errors"].append({"edge_index": scan["examined"] - 1, "error": _error(exc)})
            found = {}
            for key, hits in matches.items():
                scan["matches"][key] = len(hits)
                if len(hits) == 1 and not scan["truncated"]:
                    edge, geometry = hits[0]
                    found[key] = {**source[key], **component, "edge": edge, "native_geometry": geometry}
            return found

        if len(candidates["lever"]) == 1:
            resolved.update(edges_for(candidates["lever"][0], "lever"))
        mounts = sorted(candidates["control"], key=lambda item: item["snapshot"]["base_origin_m"][2], reverse=True)
        if len(mounts) == 2 and mounts[0]["snapshot"]["base_origin_m"][2] > mounts[1]["snapshot"]["base_origin_m"][2]:
            front = edges_for(mounts[0], "control")
            if len(front) == 3:
                resolved.update(front)
                record["control_instance_disposition"] = "front complete"
            else:
                back = edges_for(mounts[1], "control")
                # Prefer the WHOLE back set, never mixed controls. If neither is
                # complete the preregistered front subset may lose only one edge.
                if len(back) == 3:
                    resolved.update(back)
                    record["control_instance_disposition"] = "whole back fallback before maps"
                else:
                    resolved.update(front)
                    record["control_instance_disposition"] = "front subset; back set incomplete; no mixing"
        else:
            record["control_instance_disposition"] = "unavailable: not exactly two distinct base-Z mount origins"
    except _Deadline as exc:
        record.update(truncated=True, deadline_error=_error(exc))
    finally:
        record["budget"] = budget.report()
        record["end"] = _stamp()
        record["frozen_subset"] = [key for key in PRIORITY if key in resolved]
        record["missing"] = [key for key in PRIORITY if key not in resolved]
        record["subset_frozen_before_any_map"] = True
        record["reduced_set_allowed_reason"] = "visibility/straight-edge/identity discovery only, never deadlines or residuals"
    return resolved


def _geometry(witnesses: Sequence[Mapping[str, Any]], view_values: Sequence[float]) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    view_linear = _linear(view_values)[:2]
    knife = np.array([0., lever_spec.HEX_H / 2000, 0.])
    theta = math.radians(0.3)
    rotation_z = np.array([[math.cos(theta), -math.sin(theta), 0.],
                           [math.sin(theta), math.cos(theta), 0.], [0., 0., 1.]])
    rows, signal, geometry = [], [], []
    for witness in witnesses:
        component_linear = _linear(witness["values"])
        point = np.asarray(witness["point_local_m"])
        endpoints = np.asarray(witness["endpoints_local_m"])
        tangent = view_linear @ component_linear @ (endpoints[1] - endpoints[0])
        length = float(np.linalg.norm(tangent))
        if length <= 1e-12:
            raise ValueError(f"{witness['id']} degenerate projected edge")
        normal = np.array([-tangent[1], tangent[0]]) / length
        lever = witness["family"] == "lever"
        derivative = view_linear @ component_linear @ np.cross([0., 0., 1.], point - knife) if lever else np.zeros(2)
        exact = view_linear @ component_linear @ ((rotation_z - np.eye(3)) @ (point - knife)) if lever else np.zeros(2)
        row = [*normal, *(normal if lever else [0., 0.]), float(normal @ derivative)]
        rows.append(row)
        signal.append(float(normal @ exact))
        assembly = _apply(witness["values"], point) + witness["offset"]
        sheet = _apply(view_values, assembly)[:2]
        geometry.append({"id": witness["id"], "normal": normal.tolist(),
            "projected_length_m": length, "rotation_xy_m_per_rad": derivative.tolist(),
            "rotation_normal_m_per_rad": row[-1], "predicted_sheet_xy_m": sheet.tolist(),
            "assembly_point_m": assembly.tolist(), "design_row": row})
    return np.asarray(rows), np.asarray(signal), geometry


def _svd(matrix: np.ndarray) -> dict[str, Any]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    norms = np.linalg.norm(matrix, axis=0)
    normalized = np.linalg.svd(matrix / np.where(norms > 0, norms, 1.), compute_uv=False)
    rank = int(np.linalg.matrix_rank(matrix))
    return {"shape": list(matrix.shape), "rank": rank, "singular_values": singular.tolist(),
        "condition_raw": float(singular[0] / singular[-1]) if rank == 5 else None,
        "column_l2_norms": norms.tolist(), "singular_values_column_normalized": normalized.tolist(),
        "condition_column_normalized": float(normalized[0] / normalized[-1]) if rank == 5 else None,
        "raw_units_mixed": "sheet-m translations and radians; normalized condition not physical uncertainty"}


def _feasibility(matrix: np.ndarray, signal: np.ndarray) -> dict[str, Any]:
    null = matrix[:, :4]
    translation = np.linalg.lstsq(null, signal, rcond=None)[0]
    residual = signal - null @ translation
    propagation = np.eye(len(signal)) - null @ np.linalg.pinv(null)
    bound = STEP_M / 2 * np.sum(np.abs(propagation), axis=1)
    robust = np.abs(residual) - bound >= 2.5 * STEP_M
    return {"theta_deg": 0.3, "matrix": _svd(matrix), "best_translation_m": translation.tolist(),
        "exact_rotation_signal_m": signal.tolist(), "residual_against_pure_translation_m": residual.tolist(),
        "bounded_midpoint_error_m": STEP_M / 2, "propagated_residual_error_bound_m": bound.tolist(),
        "witnesses_robustly_ge_20um": int(np.sum(robust)),
        "passes": bool(np.linalg.matrix_rank(matrix) == 5 and np.sum(robust) >= 2)}


def _pick(
    adapter: Any, xy: Sequence[float], target: Mapping[str, Any] | None, arm: str,
    budget: _Budget | None = None,
    handles: dict[str, Any] | None = None, record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = {} if record is None else record
    record.update(arm=arm, sheet_xy_m=list(xy), begin=_stamp())
    draw = adapter.currentModel
    try:
        _invoke(budget, draw, "IModelDoc2", "ClearSelection2", True)
        extension = _invoke(budget, draw, "IModelDoc2", "Extension")
        callout = null_callout()
        record["select_begin"] = _stamp()
        started = time.perf_counter()
        try:
            record["raw_result"] = bool(_invoke(budget, extension, "IModelDocExtension", "SelectByID2",
                "", "EDGE", xy[0], xy[1], 0., False, 0, callout, 0))
        finally:
            record["select_ms"] = (time.perf_counter() - started) * 1000
            record["select_end"] = _stamp()
        with contextlib.suppress(Exception):
            _telemetry.event("drawing.sm_pose.raw", arm=arm, result=record["raw_result"], select_ms=record["select_ms"])
        selection, entity, owner = _selected(draw, budget)
        record["selection"] = selection
        record["accepted_own_edge"] = _identity(adapter, selection, entity, owner, target, budget) and record["raw_result"]
        if handles is not None:
            handles.update(entity=entity, owner=owner)
        count, kind = _value(selection, "count"), _value(selection, "type")
        same = _value(selection, "IsSame_edge")
        if not record["raw_result"] and count == 0:
            identity_class = "no-selection"
        elif record["accepted_own_edge"]:
            identity_class = "target"
        elif (record["raw_result"] and count == 1 and kind == 1 and entity is not None
              and same == 0 and _value(selection, "owner") is not None):
            identity_class = "different"
        else:
            identity_class = "unreadable"
        record["selection_identity_class"] = identity_class
        record["selection_identity_readable"] = identity_class != "unreadable"
    except _Deadline:
        record["collection_error"] = "soft scan deadline during pick/identity observers"
        raise
    except Exception as exc:
        record["collection_error"] = _error(exc)
        record["accepted_own_edge"] = False
        record["selection_identity_class"] = "unreadable"
        record["selection_identity_readable"] = False
    record["end"] = _stamp()
    return record


def _band(picks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    state: dict[str, Any] = {"midpoint_m": None, "width_m": None,
        "interpretation": "selection acceptance locus, NOT measured drawn pose or true aperture"}
    if len(picks) != len(OFFSETS_M):
        state["status"] = "incomplete_scan"
        return state
    if any(pick.get("collection_error") for pick in picks):
        state["status"] = "collection_error"
        return state
    ambiguous = any(not pick.get("selection_identity_readable") for pick in picks)
    state["unreadable_selection_identity"] = ambiguous
    state["different_identified_edge_hit_indices"] = [
        index for index, pick in enumerate(picks) if pick.get("selection_identity_class") == "different"
    ]
    accepted = [i for i, pick in enumerate(picks) if pick.get("accepted_own_edge")]
    runs: list[list[int]] = []
    for index in accepted:
        if not runs or index != runs[-1][-1] + 1:
            runs.append([index])
        else:
            runs[-1].append(index)
    state["accepted_index_runs"] = runs
    state["censored"] = bool(accepted and (accepted[0] == 0 or accepted[-1] == len(picks) - 1))
    if ambiguous:
        state["status"] = "identity_ambiguous"
    elif not runs:
        state["status"] = "no_own_edge_interval"
    elif len(runs) != 1:
        state["status"] = "disjoint_bands"
    elif state["censored"]:
        state["status"] = "censored"
    else:
        lo, hi = runs[0][0], runs[0][-1]
        left = (OFFSETS_M[lo - 1] + OFFSETS_M[lo]) / 2
        right = (OFFSETS_M[hi] + OFFSETS_M[hi + 1]) / 2
        state.update(status="single_uncensored_interval", midpoint_m=(left + right) / 2,
                     width_m=right - left, midpoint_sampling_bound_m=STEP_M / 2,
                     boundary_brackets_m=[[OFFSETS_M[lo - 1], OFFSETS_M[lo]],
                                          [OFFSETS_M[hi], OFFSETS_M[hi + 1]]],
                     midpoint_sigma_m_if_independent_uniform_phases=STEP_M / math.sqrt(24),
                     endpoint_repeat_stability="pending four immediate same-zoom boundary repeats",
                     additional_mapping_systematic_uncertainty_m=None)
    return state


def _window_png(path: Path, hwnd: int) -> dict[str, Any]:
    from PIL import ImageGrab

    if not hwnd:
        raise RuntimeError("main-window HWND unavailable; do not guess screenshot origin")
    image = ImageGrab.grab(window=hwnd)
    image.save(path)
    return {"path": str(path), "image_size_px": list(image.size), "window_hwnd": hwnd,
        "method": "ImageGrab.grab(window=main_frame_hwnd)", "begin_or_end_not_atomic": True}


def _scan(adapter: Any, view: Any, utility: Any, witnesses: Sequence[Mapping[str, Any]],
          geometry: Sequence[Mapping[str, Any]], report: dict[str, Any], out_dir: Path,
          checkpoint: Callable[[], None]) -> None:
    budget = _Budget(SCAN_SECONDS)
    report["maps"] = []
    picks_total = 0
    grid_picks_total = boundary_picks_total = 0
    try:
        for witness, projection in zip(witnesses, geometry, strict=True):
            budget.check(f"start witness {witness['id']}")
            centre = projection["predicted_sheet_xy_m"]
            scan: dict[str, Any] = {"id": witness["id"], "instance": witness["instance"],
                "begin": _stamp(), "intervention": "new witness-centred zoom, not passive observation",
                "normal": projection["normal"], "picks": [], "target_geometry": witness["native_geometry"]}
            report["maps"].append(scan)
            grid_handles: list[dict[str, Any]] = []
            scan["boundary_repeats"] = []
            scan["boundary_stability"] = {
                "stable": False, "status": "not_collected",
                "scope": "seconds at this witness zoom only; not historical/baseline stability",
            }
            with _zoomed_on(adapter, centre, _HIT_ZOOM_HALF):
                before = _observe(scan, "viewport_before", lambda: _viewport(adapter, utility, centre, budget))
                _observe(scan, "view_transform_before", lambda: _numbers(budget, budget.call(view, "IView", "ModelToViewTransform"), "IMathTransform"))
                _observe(scan, "component_transform_before", lambda: _numbers(budget, budget.call(witness["component"], "IComponent2", "Transform2"), "IMathTransform"))
                for offset in OFFSETS_M:
                    budget.check(f"{witness['id']} offset {offset:g}")
                    if picks_total >= PICK_CAP:
                        raise _Deadline("203 scanning-pick cap reached")
                    xy = [centre[i] + offset * projection["normal"][i] for i in range(2)]
                    pick = {"offset_m": offset, "phase": "grid", "grid_index": len(scan["picks"])}
                    scan["picks"].append(pick)
                    holder: dict[str, Any] = {}
                    grid_handles.append(holder)
                    picks_total += 1
                    grid_picks_total += 1
                    _pick(adapter, xy, witness, f"map_{witness['id']}", budget, holder, pick)
                    control = _value(before or {}, "Transform_control") or {}
                    windows = _value(before or {}, "windows") or {}
                    if control.get("valid") and windows.get("device_pixel_registration_available"):
                        pixel = _apply(control["array"], (*xy, 0.))[:2]
                        centre_px = _apply(control["array"], (*centre, 0.))[:2]
                        pick["derived_client_pixel_xy"] = pixel.tolist()
                        pick["derived_pixel_offset"] = (pixel - centre_px).tolist()
                        pick["derived_rounded_client_pixel_xy"] = np.rint(pixel).astype(int).tolist()
                        pick["subpixel_step"] = float(np.linalg.norm(_linear(control["array"])[:2, :2] @ (np.asarray(projection["normal"]) * STEP_M))) < 1
                    else:
                        pick["pixel_mapping_unavailable"] = "fresh viewport transform/native or DPI/client registration unvalidated"
                scan["band"] = _band(scan["picks"])
                # Preregistered, SAME-XY stability amendment: no enlarged range,
                # no pooling repeats into the band, and no choice based on fit.
                if scan["band"]["status"] == "single_uncensored_interval":
                    lo, hi = scan["band"]["accepted_index_runs"][0][0], scan["band"]["accepted_index_runs"][0][-1]
                    repeat_order = (hi + 1, hi, lo, lo - 1)
                    scan["boundary_stability"].update(status="incomplete", begin=_stamp(),
                        grid_indices=list(repeat_order))
                    for index in repeat_order:
                        budget.check(f"{witness['id']} boundary-repeat grid {index}")
                        if picks_total >= PICK_CAP:
                            raise _Deadline("203 scanning-pick cap reached during boundary repeats")
                        grid = scan["picks"][index]
                        repeated = {"phase": "boundary-repeat", "grid_index": index,
                            "offset_m": grid["offset_m"], "same_original_grid_xy": True}
                        scan["boundary_repeats"].append(repeated)
                        holder = {}
                        picks_total += 1
                        boundary_picks_total += 1
                        _pick(adapter, grid["sheet_xy_m"], witness,
                            f"boundary_repeat_{witness['id']}", budget, holder, repeated)
                        same_outcome = (
                            repeated.get("selection_identity_readable", False)
                            and grid.get("selection_identity_readable", False)
                            and repeated.get("raw_result") == grid.get("raw_result")
                            and _value(repeated.get("selection", {}), "count") == _value(grid.get("selection", {}), "count")
                            and repeated.get("selection_identity_class") == grid.get("selection_identity_class")
                        )
                        if repeated.get("selection_identity_class") == "different":
                            exact_other = _observe(repeated, "IsSame_repeated_different_grid_edge",
                                lambda: int(budget.call(adapter.swApp, "ISldWorks", "IsSame",
                                    holder.get("entity"), grid_handles[index].get("entity"))))
                            same_outcome = same_outcome and exact_other == 1
                        repeated["matches_grid_outcome_count_identity"] = bool(same_outcome)
                    stability = scan["boundary_stability"]
                    stability.update(
                        stable=all(repeat["matches_grid_outcome_count_identity"] for repeat in scan["boundary_repeats"]),
                        end=_stamp(),
                    )
                    stability["status"] = "stable" if stability["stable"] else "unstable_or_unreadable"
                    stability["seconds_from_grid_start_at_this_zoom"] = (
                        stability["end"]["monotonic_ns"] - scan["picks"][0]["begin"]["monotonic_ns"]) / 1e9
                    scan["band"]["endpoint_repeat_stability"] = stability["status"]
                else:
                    scan["boundary_stability"]["status"] = "not_applicable_to_ambiguous_censored_disjoint_or_missing_band"
                budget.check(f"{witness['id']} post-map snapshot")
                _observe(scan, "viewport_after", lambda: _viewport(adapter, utility, centre, budget))
                _observe(scan, "view_transform_after", lambda: _numbers(budget, budget.call(view, "IView", "ModelToViewTransform"), "IMathTransform"))
                _observe(scan, "component_transform_after", lambda: _numbers(budget, budget.call(witness["component"], "IComponent2", "Transform2"), "IMathTransform"))
                budget.check(f"{witness['id']} inside-zoom PNG")
                _observe(scan, "inside_zoom_png", lambda: _window_png(out_dir / f"{witness['id']}-window.png", _value(before or {}, "main_window_hwnd") or 0))
                budget.check(f"{witness['id']} after inside-zoom PNG")
                rounded = [tuple(pick["derived_rounded_client_pixel_xy"]) for pick in scan["picks"] if "derived_rounded_client_pixel_xy" in pick]
                scan["duplicate_rounded_pixel_positions"] = len(rounded) - len(set(rounded)) if rounded else None
                scan["pixel_positions_not_deduplicated"] = True
            budget.check(f"{witness['id']} after zoom cleanup")
            scan["end"] = _stamp()
            _event("witness", report, witness=witness["id"], picks=len(scan["picks"]), band=scan["band"]["status"])
            checkpoint()
    except _Deadline as exc:
        report["scan_truncated"] = _error(exc)
    finally:
        for scan in report["maps"]:
            if "band" not in scan:
                scan["band"] = _band(scan["picks"])
        report["scan_budget"] = {**budget.report(), "pick_attempts": picks_total,
            "grid_pick_attempts": grid_picks_total, "boundary_repeat_attempts": boundary_picks_total,
            "raw_results_recorded": sum(
                "raw_result" in pick for scan in report["maps"]
                for pick in (*scan["picks"], *scan["boundary_repeats"])),
            "pick_cap": PICK_CAP, "grid_pick_cap": GRID_PICK_CAP,
            "boundary_repeats_max_per_witness": 4,
            "repeats_take_priority_over_next_witness_grid": True}


def _fit(report: dict[str, Any], matrix: np.ndarray, witnesses: Sequence[Mapping[str, Any]]) -> None:
    maps = report.get("maps", [])
    report["fit"] = {"available": False, "parameters": None,
        "interpretation": "acceptance-locus fit only; not physical pose or independent rendered-edge evidence"}
    fit = report["fit"]
    if len(maps) != len(witnesses) or report.get("scan_truncated"):
        fit["unavailable"] = "preregistered subset not completely mapped; no post-map subset selection"
        return
    if not report["preregistration"]["admissible"]:
        fit["unavailable"] = "actual-matrix preregistration failed"
        return
    statuses = {scan["id"]: scan["band"]["status"] for scan in maps}
    fit["band_statuses"] = statuses
    if any(value != "single_uncensored_interval" for value in statuses.values()):
        fit["unavailable"] = "censored/disjoint/identity-ambiguous/missing band; no exclusions or substitute centroids"
        return
    if not all(scan.get("boundary_stability", {}).get("stable") for scan in maps):
        fit["unavailable"] = "unstable/unreadable/incomplete same-zoom boundary repeats; no post-map reduced subset"
        return
    expected_view = report["post_raw_snapshot"]["fresh_transform_control"]["value"]["array"]
    brackets = []
    for scan, witness in zip(maps, witnesses, strict=True):
        stable = True
        for key, expected in (
            ("view_transform_before", expected_view), ("view_transform_after", expected_view),
            ("component_transform_before", witness["values"]),
            ("component_transform_after", witness["values"]),
        ):
            observed = _value(scan, key)
            stable = bool(stable and observed is not None and len(observed) == len(expected)
                and np.max(np.abs(np.asarray(observed) - expected)) <= MATRIX_STABILITY_TOLERANCE)
        brackets.append({"id": scan["id"], "reported_matrices_stable": stable})
    fit["matrix_brackets"] = brackets
    fit["matrix_stability_tolerance"] = MATRIX_STABILITY_TOLERANCE
    if not all(bracket["reported_matrices_stable"] for bracket in brackets):
        fit["unavailable"] = "reported pose/view matrices changed or unavailable across witness scans"
        return
    scales = [_value(_value(scan, key) or {}, "Scale2") for scan in maps for key in ("viewport_before", "viewport_after")]
    fit["scales"] = scales
    fit["scale_relative_tolerance"] = SCALE_RELATIVE_TOLERANCE
    valid_scales = all(value is not None and math.isfinite(value) and value > 0 for value in scales)
    variation = (max(scales) - min(scales)) / min(scales) if valid_scales else None
    fit["scale_relative_variation"] = variation
    fit["pooled_pixel_or_aperture_comparisons_allowed"] = bool(variation is not None and variation <= SCALE_RELATIVE_TOLERANCE)
    if not fit["pooled_pixel_or_aperture_comparisons_allowed"]:
        fit["unavailable"] = "missing/variable zoom scale; refuse pooled metrology"
        return
    y = np.array([scan["band"]["midpoint_m"] for scan in maps])
    diagnostics = _svd(matrix)
    fit["matrix"] = diagnostics
    if diagnostics["rank"] != 5:
        fit["unavailable"] = "rank deficient; parameters unidentifiable, not zero"
        return
    inverse = np.linalg.pinv(matrix)
    parameters = inverse @ y
    residual = y - matrix @ parameters
    bounds = STEP_M / 2 * np.sum(np.abs(inverse), axis=1)
    widths = [scan["band"]["width_m"] for scan in maps]
    null_matrix = matrix[:, :4]
    null_parameters = np.linalg.lstsq(null_matrix, y, rcond=None)[0]
    fit["best_pure_translation_parameters_m"] = null_parameters.tolist()
    fit["residual_against_best_pure_translation_m"] = (y - null_matrix @ null_parameters).tolist()
    fit["parameter_sigma_if_independent_uniform_sampling_phases"] = (
        STEP_M / math.sqrt(24) * np.linalg.norm(inverse, axis=1)).tolist()
    fit.update(available=True, parameters=parameters.tolist(),
        column_order=["common_control_tx_m", "common_control_ty_m", "additional_lever_tx_m", "additional_lever_ty_m", "theta_rad"],
        residuals_m=residual.tolist(), residual_l2_m=float(np.linalg.norm(residual)),
        parameter_sampling_error_bounds=bounds.tolist(),
        theta_sampling_error_bound_deg=math.degrees(bounds[4]),
        midpoint_sampling_bound_m=STEP_M / 2, widths_m=widths,
        width_range_m=[min(widths), max(widths)],
        mapping_uncertainty="additional systematic unknown; not included in sampling-only bounds",
        physical_pose_identified=False,
        state_stability="postscan bracket matrices reported separately; sequential zooms/observers can heal baseline",
        baseline_causal_verdict="unavailable")


def _field_failures(value: Any, prefix: str = "") -> list[dict[str, str]]:
    """Index honest per-field gaps without inventing substitutes for them."""
    gaps: list[dict[str, str]] = []
    if isinstance(value, dict):
        if value.get("status") in ("error", "unavailable"):
            gaps.append({"field": prefix, "status": value["status"],
                "reason": str(value.get("error", value.get("reason", "")))})
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


def collect_and_stop(adapter: Any, view: Any, *, sheet_xy: Sequence[float], instance: str,
                     point_mm: Sequence[float], baseline: Mapping[str, Any],
                     immediate_repeat: Mapping[str, Any] | None,
                     projection_inputs: Mapping[str, Any],
                     capture_final: Callable[[str], Mapping[str, Any]]) -> None:
    """Always tagged ordinary RuntimeError; cancellation skips all later captures."""
    probe_id = uuid4().hex
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    execution = {key: os.environ[key] for key in (
        "HARMONIC_FARM_BUILD_ID", "HARMONIC_FARM_RUN", "HARMONIC_FARM_COMMIT",
        "HARMONIC_WORKER_ID", "OTEL_SERVICE_INSTANCE_ID",
        "FARM_EXECUTION_ID", "FARM_LEAF_WORKFLOW_ID", "FARM_WORKFLOW_ID", "TRACEPARENT",
        "HARMONIC_BUILD_ID", "FARM_WORKER_ID") if os.environ.get(key)}
    execution_slug = re.sub(r"[^a-zA-Z0-9._-]", "-", next(iter(execution.values()), "execution-unavailable"))[:96]
    out_dir = FAILURES / f"issue1667-sm-pose-{execution_slug}-{stamp}-{probe_id}"
    report: dict[str, Any] = {"schema": 1, "probe_id": probe_id, "begin": _stamp(),
        "execution_identity_available": bool(execution), "execution_identity": execution,
        "diagnostic_only_never_publish": True, "baseline": dict(baseline),
        "baseline_raw_result": bool(baseline.get("select_result")),
        "initial_selection_stage": "success_control_post_baseline" if baseline.get("select_result") else "post_immediate_miss_rawrepeat",
        "initial_selection": {"status": "not_yet_sampled"}, "immediate_repeat": immediate_repeat,
        "original_sheet_xy_m": list(sheet_xy), "original_local_point_mm": list(point_mm),
        "intended_instance": instance,
        "original_numeric_inputs": {key: projection_inputs.get(key) for key in (
            "component_transform", "explode_offset_m", "model_points_m", "part_points_m")},
        "prebaseline_added_native_reads": 0, "complete": False, "errors": [], "maps": [],
        "artifact_directory": str(out_dir),
        "artifact_link": f"failures/{out_dir.name}/pose.json",
        "evidence_limits": ["post-pick non-atomic observers can change timing/state",
            "acceptance locus is not drawn edge pose or true aperture",
            "deferred retained handle cannot prove historical matrix immutability",
            "native seat uncontrolled; hit is positive control, not natural recurrence",
            "near-zero postscan residual cannot exclude baseline lag",
            "no physical/causal verdict or recovery policy from this diagnostic"]}
    primary_error: Exception | None = None
    cancelled = False
    cancellation_error: BaseException | None = None
    late_cancellation: BaseException | None = None
    path = out_dir / "pose.json"

    def checkpoint() -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")

    try:
        # FIRST added native reads on a hit; on a miss this observes only the
        # immediate rawrepeat. Cancellation here still reaches guarded cleanup.
        initial_selection, selected_entity, selected_owner = _selected(adapter.currentModel)
        report["initial_selection"] = initial_selection
        checkpoint()
        utility = _com_invoke(adapter.swApp, "ISldWorks", "GetMathUtility")
        points = projection_inputs.get("model_points_m") or ()
        if not points:
            raise RuntimeError("original assembly-space projection input missing")
        snapshot, reference = _snapshot(adapter, view, utility, points[0], sheet_xy,
            projection_inputs.get("model_to_view_transform_handle"))
        report["post_raw_snapshot"] = snapshot
        control = _value(snapshot, "fresh_transform_control") or {}
        report["original_point_in_fresh_matrix"] = (_apply(control["array"], points[0])[:2].tolist()
            if control.get("valid") else None)
        retained_values = _value(snapshot, "retained_handle_deferred_ArrayData")
        if retained_values is not None:
            _observe(report, "original_point_in_deferred_retained_matrix", lambda: _apply(retained_values, points[0])[:2].tolist())
        source = _source_witnesses()
        report["source_witnesses"] = source
        report["source_authority"] = {}
        for filename in ("sm_summing_lever_spec.py", "sm_knife_mount_spec.py", "build_sm_summing_lever.py", "build_sm_knife_mount.py", "build_sm_summing_assembly.py"):
            _observe(report["source_authority"], filename, lambda name=filename: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest())
        discovered = _discover(adapter, view, utility, projection_inputs, source, report,
            reference, _value(snapshot, "ReferencedConfiguration"))
        # The original HIT handle is still retained, and no clear has occurred.
        _identity(adapter, initial_selection, selected_entity, selected_owner, discovered.get("leverPad"))
        report["baseline_own_target_positive_control"] = bool(
            baseline.get("select_result") and initial_selection.get("accepted_own_edge"))
        report["postobserver_exact_oldXY_repeat"] = _pick(adapter, sheet_xy, discovered.get("leverPad"), "postobserver_exact_oldXY")
        report["fresh_xy_threshold_m"] = FRESH_XY_THRESHOLD_M
        fresh = report["original_point_in_fresh_matrix"]
        if fresh is not None:
            delta = [fresh[i] - sheet_xy[i] for i in range(2)]
            report["fresh_minus_original_sheet_xy_m"] = delta
            if max(abs(value) for value in delta) > FRESH_XY_THRESHOLD_M:
                report["freshXY_diagnostic_only"] = _pick(adapter, fresh, discovered.get("leverPad"), "freshXY_not_recovery")
            else:
                report["freshXY_not_picked"] = "difference <= recorded roundoff threshold"
        viewport = _observe(report, "original_zoom_capture_mapping", lambda: _viewport(adapter, utility, sheet_xy)) or {}
        _observe(report, "original_zoom_postobserver_png", lambda: _window_png(
            out_dir / "original-zoom-postobserver-window.png", _value(viewport, "main_window_hwnd") or 0))
        witnesses = [discovered[key] for key in PRIORITY if key in discovered]
        report["frozen_witnesses"] = [{key: witness[key] for key in (
            "id", "family", "instance", "point_local_m", "endpoints_local_m", "source_refs", "native_geometry", "values")}
            | {"explode_offset_m": witness["offset"].tolist()} for witness in witnesses]
        prereg: dict[str, Any] = {"begin": _stamp(), "frozen_order": [w["id"] for w in witnesses],
            "disposition": "complete-seven" if len(witnesses) == 7 else "preregistered-reduced-six" if len(witnesses) == 6 else "insufficient-witnesses",
            "admissible": False, "no_postmap_substitutions_or_exclusions": True,
            "actual_matrix_native_control_valid": bool(control.get("valid")),
            "all_component_native_controls_valid": all(witness["validated"] for witness in witnesses)}
        report["preregistration"] = prereg
        if len(witnesses) >= 6 and not report["discovery"]["truncated"] and control.get("valid") and prereg["all_component_native_controls_valid"]:
            matrix, signal, geometry = _geometry(witnesses, control["array"])
            prereg["actual_projection_geometry"] = geometry
            prereg["feasibility"] = _feasibility(matrix, signal)
            prereg["design_matrix"] = matrix.tolist()
            prereg["admissible"] = prereg["feasibility"]["passes"]
            checkpoint()  # subset + actual-matrix gate persisted BEFORE maps
            if prereg["admissible"]:
                _scan(adapter, view, utility, witnesses, geometry, report, out_dir, checkpoint)
                _fit(report, matrix, witnesses)
            else:
                report["fit"] = {"available": False, "unavailable": "actual native rank/discrimination gate failed"}
        else:
            prereg["unavailable"] = "incomplete discovery/deadline/native transform metrology control"
            report["fit"] = {"available": False, "unavailable": prereg["unavailable"]}
        postscan, _ = _snapshot(adapter, view, utility, points[0], sheet_xy)
        report["post_scan_snapshot"] = postscan
        postscan_components: dict[str, Any] = {}
        report["post_scan_component_snapshots"] = postscan_components
        postscan_budget = _Budget(DISCOVERY_SECONDS)
        for witness in witnesses:
            if witness["instance"] not in postscan_components:
                postscan_components[witness["instance"]] = _component_snapshot(
                    witness["component"], utility, witness["point_local_m"], postscan_budget)
        report["post_scan_component_snapshot_budget"] = postscan_budget.report()
        report["complete"] = bool(prereg["admissible"] and len(report["maps"]) == len(witnesses)
            and not report.get("scan_truncated") and all(len(scan["picks"]) == 25 for scan in report["maps"]))
        report["preregistered_evidence_sufficient"] = bool(report.get("fit", {}).get("available"))
    except Exception as exc:
        primary_error = exc
        report["errors"].append({"stage": "collection", "error": _error(exc), **_stamp()})
        report["complete"] = False
    except BaseException as exc:
        cancelled = True
        cancellation_error = exc
        report["cancelled"] = True
        raise
    finally:
        try:
            adapter.currentModel.ClearSelection2(True)
        except BaseException as exc:
            if cancelled:
                if cancellation_error is not None:
                    cancellation_error.add_note(f"pose final selection clear also failed: {exc!r}")
                report["errors"].append({"stage": "cancelled_final_clear", "error": _error(exc), **_stamp()})
            elif isinstance(exc, Exception):
                report["errors"].append({"stage": "final_clear", "error": _error(exc), **_stamp()})
                report["complete"] = False
            else:
                cancelled = True
                late_cancellation = exc
                report["cancelled"] = True
                report["complete"] = False
                report["errors"].append({"stage": "final_clear_cancellation", "error": _error(exc), **_stamp()})
        if not cancelled:
            try:
                _observe(report, "final_postscan_capture_bundle", lambda: dict(capture_final(
                    f"issue1667-sm-pose-{stamp}-{probe_id}-postscan")))
            except BaseException as exc:
                # No later native capture after a cancellation raised by the
                # capture bundle; persist its incomplete status, then propagate.
                cancelled = True
                late_cancellation = exc
                report["cancelled"] = True
                report["complete"] = False
                report["errors"].append({"stage": "final_capture_cancellation", "error": _error(exc), **_stamp()})
            report["end"] = _stamp()
            report["unavailable_or_error_fields"] = _field_failures(report)
            report["required_maps_complete"] = report["complete"]
            if report["unavailable_or_error_fields"]:
                report["complete"] = False
        try:
            checkpoint()
        except Exception as exc:
            report["artifact_write_error"] = _error(exc)
            report["complete"] = False
            if primary_error is None:
                primary_error = exc
        _event("cancelled" if cancelled else "stop", report, json_path=str(path),
            baseline_raw_result=report["baseline_raw_result"], complete=report["complete"],
            field_gaps=len(report.get("unavailable_or_error_fields", ())),
            maps=len(report["maps"]), errors=len(report["errors"]))
        if late_cancellation is not None:
            raise late_cancellation
    message = (f"{STOP} baseline_raw={report['baseline_raw_result']} "
        f"owner={_value(report['initial_selection'], 'owner')!r} "
        f"own_target={report.get('baseline_own_target_positive_control', False)} "
        f"complete={report['complete']} evidence_sufficient={report.get('preregistered_evidence_sufficient', False)} "
        f"errors={len(report['errors'])} field_gaps={len(report.get('unavailable_or_error_fields', ()))} artifact={path}")
    raise RuntimeError(message) from primary_error
