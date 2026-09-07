"""Observe the real tooth selector once; never replay or replace its predicates."""

from contextlib import contextmanager
from enum import StrEnum
import math
import os
import time
from unittest.mock import patch

from _common import _early_bound
import _gear_drawing_entities as gear
from _telemetry import span
from diagnostics._silhouette_identity_control import _raw_return


class ToothObservation(StrEnum):
    OFF = "off"
    ENDPOINTS = "endpoints"


def observation_from_environment():
    field = "HARMONIC_TOOTH_SELECTOR_OBSERVATION"
    raw = os.environ.get(field, ToothObservation.OFF.value)
    try:
        return ToothObservation(raw)
    except ValueError as error:
        raise ValueError(f"{field}: expected off or endpoints, got {raw!r}") from error


def require_targets(mode, targets):
    if mode is not ToothObservation.OFF and any(
        target not in {"crank_drive_gear", "crank_pinion"} for target in targets
    ):
        raise ValueError(
            "tooth selector observation requires crank_drive_gear/crank_pinion"
        )


def _raw(value):
    if type(value) in (tuple, list):
        return {"type": type(value).__name__, "value": [_raw(item) for item in value]}
    if value is None or type(value) in (str, bool, int, float):
        return _raw_return(value)
    return {
        "type": f"{type(value).__module__}.{type(value).__qualname__}",
        "python_wrapper_id": id(value),
    }


def _record_value(row, value, *, size=None):
    # Do not call repr/getattr on opaque native wrappers to serialize them.
    # Python ids correlate this call's wrappers only; they prove no native identity.
    try:
        row["returned"] = _raw(value)
        if size is not None:
            valid = (
                type(value) in (tuple, list)
                and len(value) == size
                and all(type(item) is float and math.isfinite(item) for item in value)
            )
            row["array_shape"] = "finite_native_doubles" if valid else "invalid"
            row["expected_size"] = size
    except Exception as error:
        row["encoding_error"] = repr(error)


def _read(rows, name, operation, *, size=None):
    row = {"name": name}
    rows.append(row)
    started = time.perf_counter()
    try:
        value = operation()
    except BaseException as error:
        row["error"] = repr(error)
        raise
    else:
        _record_value(row, value, size=size)
        return value
    finally:
        row["seconds"] = time.perf_counter() - started


def _same(app, first, second, rows, name):
    result = _read(rows, name, lambda: app.IsSame(first, second))
    if type(result) is not int or result != 1:
        raise RuntimeError(f"tooth observation {name}: native identity is {result!r}")


def _state(adapter, view, drawing, source, row):
    """Bounded owner membership and state, separate from the actual selector reads."""
    reads = row["reads"] = []
    adapter.ownership.assert_current_owned()
    app = adapter.swApp
    _same(app, adapter.currentModel, drawing, reads, "current_drawing")
    _same(app, app.ActiveDoc, drawing, reads, "active_drawing")
    model = _early_bound(drawing, "IModelDoc2")
    kind = _read(reads, "drawing.GetType", model.GetType)
    if type(kind) is not int or kind != 3:
        raise RuntimeError("tooth observation requires the owned DRAWING")
    _read(reads, "drawing.GetTitle", model.GetTitle)
    _read(reads, "drawing.GetPathName", model.GetPathName)
    groups = _early_bound(drawing, "IDrawingDoc").GetViews()
    if type(groups) not in (tuple, list) or not 1 <= len(groups) <= 16:
        raise RuntimeError("tooth observation GetViews: unsupported sheet array")
    matches = 0
    for sheet_index, group in enumerate(groups):
        if type(group) not in (tuple, list) or not 1 <= len(group) <= 128:
            raise RuntimeError("tooth observation GetViews: unsupported view array")
        for view_index, candidate in enumerate(group[1:], 1):
            status = _read(
                reads,
                f"owner_view[{sheet_index},{view_index}]",
                lambda candidate=candidate: app.IsSame(view, candidate),
            )
            if type(status) is not int or status not in (0, 1):
                raise RuntimeError(
                    "tooth observation GetViews: unknown native identity"
                )
            matches += status
    row["owner_view_matches"] = matches
    if matches != 1:
        raise RuntimeError("tooth observation view is not unique in the owned drawing")
    native_view = _early_bound(view, "IView")
    _same(app, native_view.ReferencedDocument, source, reads, "referenced_source")
    _read(reads, "view.GetName2", native_view.GetName2)
    _read(
        reads,
        "view.ReferencedConfiguration",
        lambda: native_view.ReferencedConfiguration,
    )
    _read(reads, "view.Position", lambda: native_view.Position, size=2)
    _read(reads, "view.ScaleDecimal", lambda: native_view.ScaleDecimal)
    transform = _read(
        reads, "view.ModelToViewTransform", lambda: native_view.ModelToViewTransform
    )
    _read(
        reads,
        "transform.ArrayData",
        lambda: _early_bound(transform, "IMathTransform").ArrayData,
        size=16,
    )
    # Recheck after the additional getters; do not run the selector on a switched document.
    adapter.ownership.assert_current_owned()
    _same(app, adapter.currentModel, drawing, reads, "final_current_drawing")
    _same(app, app.ActiveDoc, drawing, reads, "final_active_drawing")


class _ForwardAdapter:
    def __init__(self, adapter, row):
        self.adapter, self.row = adapter, row
        self.current = None

    def __getattr__(self, name):
        return getattr(self.adapter, name)

    def _attempt(self, operation, *args, **kwargs):
        # The actual production callback is invoked by the actual adapter's
        # _attempt. Its default/error policy is neither copied nor overridden.
        calls = self.current["calls"]
        names = tuple(getattr(getattr(operation, "__code__", None), "co_names", ()))
        name = "/".join(names) or "callback"

        def forwarded():
            return _read(calls, name, operation)

        result = self.adapter._attempt(forwarded, *args, **kwargs)
        row = {"name": "adapter._attempt.return", "callback_names": names}
        _record_value(row, result)
        calls.append(row)
        return result

    def _get_attr_or_call(self, obj, name):
        row = self.current
        return _read(
            row["calls"],
            f"{name}@python_wrapper_{id(obj)}",
            lambda: self.adapter._get_attr_or_call(obj, name),
            size=3 if name == "ArrayData" else None,
        )


@contextmanager
def observe_selector(adapter, module, source, trial, mode):
    """Patch only within the owned recipe scope; OFF does not inspect native state."""
    if mode is ToothObservation.OFF:
        yield
        return
    if mode is not ToothObservation.ENDPOINTS:
        raise ValueError(f"unsupported tooth observation {mode!r}")
    original = module.visible_tooth_tip_silhouette
    if original is not gear.visible_tooth_tip_silhouette:
        raise RuntimeError(
            "tooth observation requires the actual production selector alias"
        )
    records = trial.setdefault("tooth_selector_observations", [])

    def selector(actual_adapter, view, outside_diameter_mm):
        row = {
            "outside_diameter_mm": outside_diameter_mm,
            "enumerations": [],
            "candidates": [],
        }
        records.append(row)  # Survives the original exception in the pilot receipt.
        if actual_adapter is not adapter:
            raise RuntimeError("tooth observation received a different adapter")
        drawing = adapter.currentModel
        proxy = _ForwardAdapter(adapter, row)
        original_scan, original_bound = gear.visible_view_entities, gear._early_bound
        raw_handles, bound_handles = [], []

        def scan(*args, **kwargs):
            enumeration = {"kind": args[1], "label": kwargs.get("label")}
            row["enumerations"].append(enumeration)
            result = _read(
                enumeration.setdefault("reads", []),
                "visible_view_entities",
                lambda: original_scan(*args, **kwargs),
            )
            enumeration["count"] = len(result)
            raw_handles.extend(result)
            return result

        def bound(raw, kind, *args, **kwargs):
            result = original_bound(raw, kind, *args, **kwargs)
            if kind == "ISilhouetteEdge":
                candidate = {
                    "binding_index": len(bound_handles),
                    "enumeration_indices": [
                        index for index, item in enumerate(raw_handles) if item is raw
                    ],
                    "calls": [],
                }
                row["candidates"].append(candidate)
                bound_handles.append(result)
                proxy.current = candidate
            return result  # Never substitute native entity wrappers.

        started = time.perf_counter()
        try:
            entry = row["entry"] = {}
            with span("diagnostic.tooth_selector.state", phase="entry"):
                _state(adapter, view, drawing, source, entry)
            with (
                patch.object(gear, "visible_view_entities", scan),
                patch.object(gear, "_early_bound", bound),
            ):
                result = original(proxy, view, outside_diameter_mm)
            row["returned_binding_indices"] = [
                index for index, item in enumerate(bound_handles) if item is result
            ]
            return result
        except BaseException as error:
            row["error"] = repr(error)
            raise
        finally:
            exit_row = row["exit"] = {}
            try:
                with span("diagnostic.tooth_selector.state", phase="exit"):
                    _state(adapter, view, drawing, source, exit_row)
            except BaseException as error:
                # Evidence failures must not replace the selector exception/return.
                exit_row["observation_error"] = repr(error)
            row["seconds_including_observations"] = time.perf_counter() - started

    with patch.object(module, "visible_tooth_tip_silhouette", selector):
        yield
