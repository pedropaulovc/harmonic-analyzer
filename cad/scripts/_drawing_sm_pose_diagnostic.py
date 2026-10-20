"""TEMPORARY issue1667 fixed-point viewport experiment; never a recovery path.

Imported only inside the original pick zoom, after the baseline (and a miss's
immediate unchanged raw repeat). Every observation is post-pick, non-atomic,
and potentially perturbing. This module always stops the drawing before save.

Visibility/settings observations are additive, bounded, and never adjudicate the
frozen phase hypothesis. Configured preferences and installed video controllers
do not attest an active rendering backend or explain a missed selection.
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
import subprocess
import time
import threading
import traceback
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
    "leverPad",
    "controlY",
    "leverNear",
    "leverFarMidrib",
    "controlX",
    "leverPlateEnd",
    "controlZ",
)
PAD_CONTROL_OFFSET_M = 8e-6
DISCOVERY_SECONDS = 60.0
STUDY_SECONDS = 180.0
OPTIONAL_OBSERVATION_SECONDS = 15.0
VISIBILITY_SECONDS = 30.0
VISIBILITY_CHECKPOINT_SECONDS = 5.0
VISIBILITY_GRACE_SECONDS = 5.0
VISIBILITY_EXIT_CODE = 90
PICK_CAP = 112
BLOCKS = (("A", "P-", "A", "N", "A", "P+", "A"), ("A", "P+", "A", "N", "A", "P-", "A"))
PAD_BLOCKS = (
    ("P-", "A", "N", "A", "P+", "A", "A"),
    ("P+", "A", "N", "A", "P-", "A", "A"),
)
ARMS = ("A", "P-", "P+", "N")
PHASE_TARGETS = {"P-": 0.25, "P+": 0.25, "N": 0.75}
INTEGER_OFFSETS = {"P-": -1, "P+": 1, "N": 0}
ACHIEVED_TOLERANCE = 1e-6
REFERENCE_SOURCE = "419cd18af1f6904f76bd794d487eb8616ecc8818"
REFERENCE_REPORT_SHA256 = (
    "a800fe59adae895ff6a96f1dcb932d048f364a32d78a2795da2772b4983cdc35"
)
REFERENCE_REPORT = "azure/failures/sm1667-16c43264/p.json"
# Actual frozen_points[].normal from the audited report, transformed by its
# normalized native 2x2 diag(1,-1). Never rounded prose or image-derived normals.
REFERENCE_OUTPUT_NORMALS = {
    "controlY": (-1.0, -3.3991657503963763e-17),
    "leverNear": (0.4999593663180295, 0.8660488623806825),
    "leverFarMidrib": (-0.32323645714960353, 0.9463182301791361),
    "controlX": (0.499959366318032, -0.866048862380681),
    "leverPlateEnd": (0.499959366318032, -0.8660488623806811),
    "leverPad": (0.4999593663180295, 0.8660488623806826),
    "controlZ": (0.49995936631802945, 0.8660488623806826),
}
# In-sample descriptive [maximum hit distance, minimum miss distance); not an
# identified aperture and NOT used to override the frozen group predictions.
REFERENCE_RADIUS_BOUNDS = {
    "controlX": (0.36608949606198316, 0.8660488623775303),
    "controlY": (0.999999999998181, None),
    "controlZ": (0.34150205717558746, 0.8660488623791073),
    "leverFarMidrib": (0.9463182301774148, None),
    "leverNear": (1.3660082286962272, None),
    "leverPad": (0.5245468052084893, 0.8660488623791073),
    "leverPlateEnd": (0.8660488623791058, None),
}
REFERENCE_FRAME = {
    "FrameLeft": 0,
    "FrameTop": 22,
    "FrameWidth": 1205,
    "FrameHeight": 677,
    "FrameState": 1,
}
REFERENCE_WINDOWS = {
    "view_client_rect_px": [0, 0, 1264, 598],
    "grabbed_main_window_rect_px": [0, 0, 1280, 752],
    "view_client_screen_origin_px": [-1, 116],
    "view_dpi": 96,
    "main_window_dpi": 96,
    "caller_thread_dpi_awareness": 0,
    "seat_window_dpi_awareness": 2,
}
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
_HISTORY: ContextVar[dict[str, Any] | None] = ContextVar("sm1667_history", default=None)
_visibility_exit = os._exit


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
        else "fit_native_call"
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


class _VisibilityDeadline:
    """Private self-exit only: no flush, COM, logging or report access on expiry."""

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        self.lock = threading.Lock()
        self.state = "disarmed"
        self.timer: Any = None

    def _fire(self) -> None:
        with self.lock:
            if self.state != "armed":
                return
            self.state = "fired"
        _visibility_exit(VISIBILITY_EXIT_CODE)

    def __enter__(self):
        started = time.perf_counter()
        with self.lock:
            self.state = "armed"
        self.timer = threading.Timer(self.seconds, self._fire)
        self.timer.daemon = True
        self.timer.start()
        _cost("visibility_guard_arm", (time.perf_counter() - started) * 1000)
        return self

    def __exit__(self, *exc: Any) -> None:
        started = time.perf_counter()
        with self.lock:
            fired = self.state == "fired"
            if not fired:
                self.state = "disarmed"
        if fired:
            # A returning getter must not continue when the callback won.
            _visibility_exit(VISIBILITY_EXIT_CODE)
            raise RuntimeError("self-exit unexpectedly returned")
        self.timer.cancel()
        _cost("visibility_guard_disarm", (time.perf_counter() - started) * 1000)


def _metadata_field(
    stage: str,
    probe: Callable[[], Any] | None = None,
    *,
    reason: str = "",
    status: str = "unavailable",
) -> dict[str, Any]:
    """Failure-preserving optional envelope; never relax scientific _observe."""
    field: dict[str, Any] = {"begin": _stamp(), "stage": stage}
    try:
        if probe is None:
            field.update(status=status, reason=reason)
        else:
            value = probe()
            if value is None:
                field.update(
                    status="unavailable", reason="native accessor returned null"
                )
            else:
                _finite_tree(value)
                # Reject handles and opaque Python values, not merely nonfinite floats.
                json.dumps(value, allow_nan=False)
                field.update(status="available", value=value)
    except _Deadline as exc:
        field.update(status="budget_skipped", reason=_error(exc))
    except Exception as exc:
        field.update(status="error", error=_error(exc))
    finally:
        field["end"] = _stamp()
    return field


def _metadata_scalar(value: Any, kind: type) -> Any:
    if value is None:
        return None
    if type(value) is not kind:
        raise ValueError(
            f"malformed scalar: expected {kind.__name__}, got {type(value).__name__}"
        )
    if kind is str and not value:
        raise ValueError("empty configuration is unavailable")
    return value


def _curve_packet(values: Any) -> dict[str, Any] | None:
    """IEdge.GetCurveParams2: numeric0:8, opaque packed int pairs8:11."""
    if values is None:
        return None
    packet = tuple(float(value) for value in values)
    if len(packet) != 11:
        raise ValueError(f"GetCurveParams2 requires11 doubles, got{len(packet)}")
    if not all(math.isfinite(value) for value in packet[:8]):
        raise ValueError("nonfinite GetCurveParams2 geometry/parameters")
    pairs = [
        list(struct.unpack("<ii", struct.pack("<d", value))) for value in packet[8:]
    ]
    return {
        "raw_double_bits_be": [struct.pack(">d", value).hex() for value in packet],
        "numeric_0_7": list(packet[:8]),
        "endpoints_local_m": [list(packet[:3]), list(packet[3:6])],
        "parameter_bounds": list(packet[6:8]),
        "packed_int32_pairs_le": pairs,
        "curve_type": pairs[0][1],
        "curve_tag": pairs[1][1],
        "sense_flag": pairs[2][1],
        "packing": "little-endian int32 pair in native Windows double; second integer documented",
    }


class _VisibilityCheckpoint:
    """New atomic snapshots, deliberately outside the frozen102 receipt ledger."""

    def __init__(self, report: dict[str, Any], path: Path, temp: Path) -> None:
        self.report, self.path, self.temp = report, path, temp

    def __call__(self) -> bool:
        # Caller owns the five-second guard across traversal/serialization/all I/O.
        with _timed("visibility_checkpoint_serialization"):
            _finite_tree(self.report)
            payload = json.dumps(self.report, sort_keys=True, allow_nan=False) + "\n"
        with _timed("visibility_checkpoint_write"):
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.temp.write_text(payload, encoding="utf-8")
        with _timed("visibility_checkpoint_replace"):
            os.replace(self.temp, self.path)
        return True


class _VisibilityTelemetry:
    """Cumulative optional observation allowance, paused across original science."""

    def __init__(self, report: dict[str, Any], checkpoint: Any) -> None:
        self.report, self.writer = report, checkpoint
        self.retained: dict[str, tuple[Any, int]] = {}
        self.pending_censuses: list[
            tuple[dict[str, Any], Sequence[Any], list[dict[str, Any]]]
        ] = []
        self.disabled = False
        stage = "not_reached"
        self.data: dict[str, Any] = {
            "schema_version": 1,
            "status": "unavailable",
            "profile_before": _metadata_field(
                stage, reason="before profile not reached"
            ),
            "profile_after": _metadata_field(stage, reason="after profile not reached"),
            "components_at_discovery": {},
            "censuses": [],
            "os_inventory": _metadata_field(
                stage, reason="required post-study attempt not reached"
            ),
            "active_graphics_backend": _metadata_field(
                stage,
                reason="no documented active-process/backend attestation established",
            ),
            "budget": {
                "soft_limit_s": VISIBILITY_SECONDS,
                "consumed_s": 0.0,
                "remaining_s": VISIBILITY_SECONDS,
                "calls": 0,
                "sections": [],
                "checkpoint_limit_s": VISIBILITY_CHECKPOINT_SECONDS,
                "hard_grace_s": VISIBILITY_GRACE_SECONDS,
                "exit_code": VISIBILITY_EXIT_CODE,
                "clock_scope": "cumulative active new-observer sections including new checkpoints; excludes original discovery/phase",
                "pending_stage": None,
                "checkpoint_status": "pending",
            },
            "costs": {
                "new_native_calls": {},
                "reused_native_calls": {},
                "profile_calls": 0,
                "component_calls": 0,
                "census_extra_calls": 0,
                "checkpoint_attempts": 0,
                "os_query_attempts": 0,
                "os_query_elapsed_s": 0.0,
                "scope": "known getter invocations; SDK hidden calls excluded; overlaps legacy performance scopes, no whole-leaf delta",
            },
            "deadline": {
                "exit_code": VISIBILITY_EXIT_CODE,
                "checkpoint_limit_s": VISIBILITY_CHECKPOINT_SECONDS,
                "grace_s": VISIBILITY_GRACE_SECONDS,
                "mechanism": "private locked Python timer; expiry only os._exit(90), no flush",
                "limitations": "not OS real-time; does not cancel server COM or guarantee seat health; pool redispatch remains possible",
            },
        }
        report["visibility_telemetry"] = self.data

    def _charge(self, row: dict[str, Any], started: float, calls: int = 0) -> None:
        elapsed = time.perf_counter() - started
        row.update(end=_stamp(), elapsed_s=elapsed, calls=calls)
        budget = self.data["budget"]
        budget["consumed_s"] += elapsed
        budget["remaining_s"] = max(0.0, VISIBILITY_SECONDS - budget["consumed_s"])
        budget["calls"] += calls
        _cost(f"visibility_{row['kind']}", elapsed * 1000)

    def checkpoint(self, stage: str) -> bool:
        budget = self.data["budget"]
        budget.update(pending_stage=stage, checkpoint_status="pending")
        row = {
            "name": stage,
            "kind": "checkpoint",
            "begin": _stamp(),
            "soft_limit_s": budget["remaining_s"],
            "hard_limit_s": VISIBILITY_CHECKPOINT_SECONDS,
            "status": "partial",
        }
        budget["sections"].append(row)
        self.data["costs"]["checkpoint_attempts"] += 1
        started = time.perf_counter()
        try:
            with _VisibilityDeadline(VISIBILITY_CHECKPOINT_SECONDS):
                self.finish(clear_pending=False)
                before = self.report.get("checkpoint", {}).get("last_good_attempt")
                result = self.writer()
                after = self.report.get("checkpoint", {}).get("last_good_attempt")
                success = result is True or (after is not None and after != before)
            budget["checkpoint_status"] = "written" if success else "failed"
            row["status"] = "complete" if success else "partial"
            if not success:
                self.disabled = True
            return success
        except Exception as exc:
            row["error"] = _error(exc)
            budget["checkpoint_status"] = "failed"
            self.disabled = True
            return False
        finally:
            self._charge(row, started)

    @contextlib.contextmanager
    def section(self, name: str, kind: str, original_budget: _Budget | None = None):
        started = time.perf_counter()
        try:
            if self.disabled or self.data["budget"]["remaining_s"] <= 0:
                yield None
                return
            if not self.checkpoint(name):
                yield None
                return
            remaining = self.data["budget"]["remaining_s"]
            if remaining <= 0:
                yield None
                return
            budget = _Budget(remaining)
            row = {
                "name": name,
                "kind": kind,
                "begin": _stamp(),
                "soft_limit_s": remaining,
                "hard_limit_s": remaining + VISIBILITY_GRACE_SECONDS,
                "status": "partial",
            }
            self.data["budget"]["sections"].append(row)
            active = time.perf_counter()
            try:
                with _VisibilityDeadline(row["hard_limit_s"]):
                    yield budget
                row["status"] = (
                    "complete"
                    if time.perf_counter() - budget.start < remaining
                    else "partial"
                )
            finally:
                self._charge(row, active, budget.calls)
            self.checkpoint(f"{name}:boundary")
        finally:
            if original_budget is not None:
                # Extras must not consume the frozen required-discovery budget.
                original_budget.start += time.perf_counter() - started

    def call(
        self, budget: _Budget, obj: Any, interface: str, member: str, *args: Any
    ) -> Any:
        before = budget.calls
        try:
            return budget.call(obj, interface, member, *args)
        finally:
            if budget.calls != before:
                name = f"{interface}.{member}"
                counts = self.data["costs"]["new_native_calls"]
                counts[name] = counts.get(name, 0) + 1

    def reuse(self, interface: str, member: str) -> None:
        counts = self.data["costs"]["reused_native_calls"]
        name = f"{interface}.{member}"
        counts[name] = counts.get(name, 0) + 1

    def field(
        self,
        stage: str,
        budget: _Budget | None,
        obj: Any,
        interface: str,
        member: str,
        kind: type,
        *args: Any,
    ) -> dict[str, Any]:
        if budget is None:
            return _metadata_field(
                stage,
                reason="observer allowance exhausted or precheckpoint failed",
                status="budget_skipped",
            )
        return _metadata_field(
            stage,
            lambda: _metadata_scalar(
                self.call(budget, obj, interface, member, *args), kind
            ),
        )

    def component(
        self,
        instance: str,
        component: Any,
        ordinal: int,
        original_budget: _Budget | None = None,
    ) -> None:
        self.retained[instance] = (component, ordinal)
        stage = "existing_discovery_retained_handle_non_atomic"
        row: dict[str, Any] = {
            "instance": instance,
            "discovery_ordinal": ordinal,
            "stage": stage,
            "begin": _stamp(),
            "status": "partial",
            "pending": True,
        }
        self.data["components_at_discovery"][instance] = row
        with self.section(
            f"component:{instance}", "component", original_budget
        ) as budget:
            self._component_fields(row, component, stage, budget)
        row["end"] = _stamp()
        row["pending"] = False
        row["status"] = (
            "complete"
            if all(
                row[m]["status"] == "available"
                for m in ("ReferencedConfiguration", "GetSuppression2")
            )
            else "partial"
        )

    def _component_fields(
        self, row: dict[str, Any], component: Any, stage: str, budget: _Budget | None
    ) -> None:
        before = budget.calls if budget else 0
        for member, kind in (
            ("ReferencedConfiguration", str),
            ("GetSuppression2", int),
        ):
            row[member] = self.field(
                stage, budget, component, "IComponent2", member, kind
            )
        self.data["costs"]["component_calls"] += (
            budget.calls if budget else 0
        ) - before
        row["status"] = (
            "complete"
            if all(
                row[m]["status"] == "available"
                for m in ("ReferencedConfiguration", "GetSuppression2")
            )
            else "partial"
        )

    def profile(self, adapter: Any, view: Any, *, after: bool = False) -> None:
        stage = (
            "post_study_cleanup_fit_non_atomic"
            if after
            else "post_baseline_pre_discovery_non_atomic"
        )
        row: dict[str, Any] = {
            "stage": stage,
            "begin": _stamp(),
            "view": {},
            "application": {},
            "components": {},
            "status": "partial",
            "pending": True,
            "components_status": "available"
            if after and self.retained
            else "unavailable",
        }
        if row["components_status"] == "unavailable":
            row["components_reason"] = (
                "no early component traversal"
                if not after
                else "discovery retained no component handles"
            )
        self.data["profile_after" if after else "profile_before"] = row
        with self.section(stage, "profile") as budget:
            for member in (
                "GetDisplayMode2",
                "GetFacettedHlrDisplay",
                "GetUseParentDisplayMode",
                "GetDisplayEdgesInShadedMode",
                "GetCThreadQuality",
                "IsLightweight",
                "ReferencedConfiguration",
            ):
                if member == "ReferencedConfiguration" and not after:
                    original = self.report.get("post_raw_snapshot", {}).get(member, {})
                    field = _metadata_field(
                        stage, lambda: _metadata_scalar(original.get("value"), str)
                    )
                    if original.get("status") != "available":
                        field = _metadata_field(
                            stage, reason="original view configuration unavailable"
                        )
                    field["reused_from"] = "post_raw_snapshot.ReferencedConfiguration"
                    row["view"][member] = field
                    self.reuse("IView", member)
                else:
                    kind = (
                        str
                        if member == "ReferencedConfiguration"
                        else int
                        if member == "GetDisplayMode2"
                        else bool
                    )
                    row["view"][member] = self.field(
                        stage, budget, view, "IView", member, kind
                    )
            for name in (
                "swUseSimpleOpenGL",
                "swEnablePerformancePipeline",
                "swHardwareAccSilhouetteEdges",
                "swSystemOptionDisplayAntiAliasing",
            ):

                def preference(n=name):
                    if budget is None:
                        raise _Deadline(
                            "observer allowance exhausted or precheckpoint failed"
                        )
                    budget.check(n)
                    from solidworks_mcp.adapters.sw_type_info import constant

                    integer = n == "swSystemOptionDisplayAntiAliasing"
                    member = (
                        "GetUserPreferenceIntegerValue"
                        if integer
                        else "GetUserPreferenceToggle"
                    )
                    return _metadata_scalar(
                        self.call(
                            budget, adapter.swApp, "ISldWorks", member, constant(n)
                        ),
                        int if integer else bool,
                    )

                row["application"][name] = _metadata_field(stage, preference)
            self.data["costs"]["profile_calls"] += budget.calls if budget else 0
        if after:
            # Separate child-metadata timing/calls, not double billed as profile getters.
            with self.section(f"{stage}:components", "component") as budget:
                for instance, (component, ordinal) in self.retained.items():
                    child = {
                        "instance": instance,
                        "discovery_ordinal": ordinal,
                        "stage": stage,
                        "begin": _stamp(),
                    }
                    self._component_fields(child, component, stage, budget)
                    child["end"] = _stamp()
                    row["components"][instance] = child
        row["end"] = _stamp()
        row["pending"] = False
        row["status"] = (
            "complete"
            if row["components_status"] == "available"
            and all(
                f["status"] == "available"
                for group in ("view", "application")
                for f in row[group].values()
            )
            and all(c["status"] == "complete" for c in row["components"].values())
            else "partial"
        )

    def census(self, instance: str, family: str) -> dict[str, Any]:
        stage = "existing_component_filtered_view_discovery"
        row = {
            "stage": stage,
            "begin": _stamp(),
            "instance": instance,
            "family": family,
            "association": "component_filtered_enumeration",
            "returned_total": None,
            "reported_total": _metadata_field(stage, reason="count not reached"),
            "native_return_shape": _metadata_field(
                stage, reason="enumeration not reached"
            ),
            "enumeration_status": "unavailable",
            "metadata_status": "unavailable",
            "status": "unavailable",
            "examined": 0,
            "metadata_complete": 0,
            "rows": [],
        }
        self.data["censuses"].append(row)
        return row

    def census_extras(
        self,
        census: dict[str, Any],
        edges: Sequence[Any],
        original_budget: _Budget,
        observed: Sequence[Mapping[str, Any]],
        *,
        allow_native: bool = True,
    ) -> None:
        stage = census["stage"]
        self.finish_census(census)
        with self.section(
            f"census:{census['instance']}", "census_extra", original_budget
        ) as budget:
            before = budget.calls if budget else 0
            for row, edge, captured in zip(
                census["rows"], edges, observed, strict=True
            ):
                if "GetCurve" in captured:
                    row["GetCurve"] = _metadata_field(
                        stage, lambda c=captured: True if c["GetCurve"] else None
                    )
                    if captured["GetCurve"] is False:
                        for dependent in ("IsLine", "GetCurveParams2"):
                            row[dependent] = _metadata_field(
                                stage,
                                reason="same-handle GetCurve returned null; dependent getter not applicable",
                            )
                if "IsLine" in captured:
                    row["IsLine"] = _metadata_field(
                        stage, lambda c=captured: _metadata_scalar(c["IsLine"], bool)
                    )
                for member in ("GetCurve", "IsLine", "GetCurveParams2"):
                    failure = captured.get(f"{member}_error")
                    if failure:
                        row[member] = _metadata_field(
                            stage, reason=failure["error"], status=failure["status"]
                        )
                if "GetCurveParams2" in captured:
                    row["GetCurveParams2"] = _metadata_field(
                        stage, lambda c=captured: _curve_packet(c["GetCurveParams2"])
                    )
                    continue
                if (
                    budget is None
                    or time.perf_counter() - budget.start >= budget.seconds
                ):
                    continue
                if (
                    allow_native
                    and captured.get("GetCurve") is True
                    and captured.get("IsLine") is False
                ):
                    # Same handle's original GetCurve already established the precondition.
                    # No retry on null/error; no owner/vertex/face/identity getters.
                    row["GetCurveParams2"] = _metadata_field(
                        stage,
                        lambda e=edge: _curve_packet(
                            self.call(budget, e, "IEdge", "GetCurveParams2")
                        ),
                    )
            self.data["costs"]["census_extra_calls"] += (
                budget.calls if budget else 0
            ) - before
            self.finish_census(census)
            if (
                budget is not None
                and time.perf_counter() - budget.start < budget.seconds
            ):
                json_started = time.perf_counter()
                census["serialized_rows_bytes_utf8"] = len(
                    json.dumps(census["rows"], allow_nan=False).encode("utf-8")
                )
                census["serialization_elapsed_s"] = time.perf_counter() - json_started
                _cost(
                    "visibility_census_json", census["serialization_elapsed_s"] * 1000
                )
        self.pending_censuses = [
            item for item in self.pending_censuses if item[0] is not census
        ]
        self.finish_census(census)

    @staticmethod
    def finish_census(census: dict[str, Any]) -> None:
        for row in census["rows"]:
            fields = [row[m] for m in ("GetCurve", "IsLine", "GetCurveParams2")]
            row["status"] = (
                "available"
                if all(f["status"] == "available" for f in fields)
                else "error"
                if any(f["status"] == "error" for f in fields)
                else "budget_skipped"
                if any(f["status"] == "budget_skipped" for f in fields)
                else "unavailable"
            )
        census["examined"] = sum(
            row["GetCurve"]["status"] != "budget_skipped" for row in census["rows"]
        )
        census["metadata_complete"] = sum(
            row["status"] == "available" for row in census["rows"]
        )
        census["metadata_status"] = (
            "complete"
            if census["returned_total"] is not None
            and census["metadata_complete"] == census["returned_total"]
            else "incomplete"
            if census["rows"]
            else "unavailable"
        )
        census["status"] = (
            "complete"
            if census["enumeration_status"] == "complete"
            and census["metadata_status"] == "complete"
            else "partial"
            if census["returned_total"] is not None
            else "unavailable"
        )
        census["end"] = _stamp()

    def inventory(self) -> None:
        stage = "post_study_os_inventory"
        fields = (
            "Name",
            "DeviceID",
            "PNPDeviceID",
            "DriverVersion",
            "DriverDate",
            "InstalledDisplayDrivers",
            "Status",
            "ConfigManagerErrorCode",
        )
        script = (
            "$ErrorActionPreference='Stop'; @(Get-CimInstance Win32_VideoController | Select-Object "
            + ",".join(fields)
            + ") | ConvertTo-Json -Depth 4 -Compress"
        )
        command = ["pwsh.exe", "-NoProfile", "-NonInteractive", "-Command", script]
        detail: dict[str, Any] = {
            "command": command,
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "timed_out": False,
            "timeout_s": 5.0,
        }
        self.data["costs"]["os_query_attempts"] += 1
        started = time.perf_counter()

        def query():
            startup = time.perf_counter()
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            detail["startup_elapsed_s"] = time.perf_counter() - startup
            query_started = time.perf_counter()
            try:
                stdout, stderr = process.communicate(timeout=5.0)
            except subprocess.TimeoutExpired as exc:
                # Only this Popen's retained process handle; no PID discovery/tree kill.
                process.kill()
                detail.update(
                    timed_out=True,
                    stdout=_subprocess_text(exc.output),
                    stderr=_subprocess_text(exc.stderr),
                    exit_code=process.poll(),
                )
                detail["query_elapsed_s"] = time.perf_counter() - query_started
                raise TimeoutError(
                    "owned Win32_VideoController query exceeded5s"
                ) from exc
            detail.update(stdout=stdout, stderr=stderr, exit_code=process.returncode)
            detail["query_elapsed_s"] = time.perf_counter() - query_started
            if process.returncode != 0:
                raise RuntimeError(f"CIM query exited{process.returncode}")
            parse_started = time.perf_counter()
            parsed = json.loads(stdout)
            rows = (
                parsed
                if isinstance(parsed, list)
                else [parsed]
                if isinstance(parsed, dict)
                else None
            )
            if rows is None or any(
                not isinstance(row, dict) or set(row) != set(fields) for row in rows
            ):
                raise ValueError(
                    "CIM inventory is not a complete explicit-field row array"
                )
            detail["parse_elapsed_s"] = time.perf_counter() - parse_started
            return {**detail, "rows": rows}

        self.data["os_inventory"] = _metadata_field(stage, query)
        if self.data["os_inventory"]["status"] != "available":
            self.data["os_inventory"].update(detail)
        elapsed = time.perf_counter() - started
        self.data["costs"]["os_query_elapsed_s"] = elapsed
        _cost("visibility_os_query", elapsed * 1000)

    def finish(self, *, clear_pending: bool = True) -> None:
        if clear_pending:
            self.data["budget"]["pending_stage"] = None
        if not clear_pending:
            for row in self.data["components_at_discovery"].values():
                if row.get("pending"):
                    row["status"] = "partial"
        sections = [
            self.data["profile_before"],
            self.data["profile_after"],
            *self.data["components_at_discovery"].values(),
            *self.data["censuses"],
        ]
        inventory = self.data["os_inventory"]["status"] == "available"

        def observed(value: Any) -> bool:
            if isinstance(value, Mapping):
                return value.get("status") == "available" or any(
                    observed(child) for child in value.values()
                )
            return isinstance(value, (tuple, list)) and any(
                observed(child) for child in value
            )

        any_observed = any(observed(row) for row in sections)
        self.data["status"] = (
            "complete"
            if inventory and all(row.get("status") == "complete" for row in sections)
            else "partial"
            if inventory or any_observed
            else "unavailable"
        )
        if not clear_pending and self.data["status"] == "complete":
            self.data["status"] = "partial"


def _subprocess_text(value: Any) -> str:
    return (
        value.decode("utf-8", errors="replace")
        if isinstance(value, bytes)
        else value or ""
    )


def _event(stage: str, report: Mapping[str, Any], **fields: Any) -> None:
    # Calls/escaping exceptions only: exporter retention requires trace joins.
    started = time.perf_counter()
    try:
        counter = _SPAN_EVENTS.get()
        if counter is not None and stage == "phase_pick":
            counter["phase_event_call_count"] += 1
        _telemetry.event(
            f"drawing.sm_pose.{stage}", probe_id=report["probe_id"], **fields
        )
    except Exception:
        counter = _SPAN_EVENTS.get()
        if counter is not None and stage == "phase_pick":
            counter["event_call_exception_count"] += 1
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
    # Builder-only expressions mirrored by current symbols on main21f2606d6.
    s = lever_spec
    w, length, thickness = s.PLATE_W, s.PLATE_L, s.PLATE_T
    radius = s.CYL_R + 0.1 * s.MM_PER_IN  # build_sm_summing_lever:ARC_R,RIB_PAD
    rib_thickness = (
        0.2 * s.MM_PER_IN
    )  # build_sm_summing_lever:RIB_T (not RECEIVER_RIB_T)
    reach = s.HOLE_X - 4.1  # build_sm_summing_lever:RIB_PLATE_REACH
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
    mount_gap = 0.0  # build_sm_knife_mount:MOUNT_GAP
    top = (
        999.7 - (979.7 + s.HEX_H / 2) - mount_gap
    )  # build_sm_knife_mount:CASTING_UNDERSIDE_Y,CONTACT_Y; NOT rounded BLK_TOP
    definitions = (
        (
            "leverNear",
            "lever",
            (s.HEX_W / 2, s.HEX_H / 4, length / 2 + s.HEX_DEPTH / 2),
            (s.HEX_W / 2, s.HEX_H / 4, length / 2),
            (s.HEX_W / 2, s.HEX_H / 4, length / 2 + s.HEX_DEPTH),
            "build_sm_summing_lever.py:_hex_knife,_knife_ridge_fillet; sm_summing_lever_spec.py:HEX_W,HEX_H,HEX_DEPTH; main21f2606d6",
        ),
        (
            "leverPad",
            "lever",
            (w, thickness / 2 - s.SPRING_SEAT_T, 0),
            (w, thickness / 2 - s.SPRING_SEAT_T, -length / 2),
            (w, thickness / 2 - s.SPRING_SEAT_T, length / 2),
            "build_sm_summing_lever.py:_coefficients_plate (SpringPad); sm_summing_lever_spec.py:SPRING_SEAT_T; main21f2606d6",
        ),
        (
            "leverFarMidrib",
            "lever",
            (-60.0, slope * (s.SUM_H - 60.0), rib_thickness / 2),
            rib_start,
            rib_end,
            "build_sm_summing_lever.py:_middle_rib,_summation_plate,ARC_R,RIB_T,TIP_X; main21f2606d6",
        ),
        (
            "leverPlateEnd",
            "lever",
            ((reach + w) / 2, thickness / 2, length / 2),
            (reach, thickness / 2, length / 2),
            (w, thickness / 2, length / 2),
            "build_sm_summing_lever.py:_coefficients_plate,RIB_PLATE_REACH,_edge_rib (EdgeRibFront); main21f2606d6",
        ),
        (
            "controlY",
            "control",
            (hx, 0, z),
            (hx, bottom, z),
            (hx, top, z),
            "build_sm_knife_mount.py:BLK_BOT,BLK_TOP,SUPPORT_Z_THICK,build (BlockProfile); sm_knife_mount_spec.py:BLK_HALF_X; main21f2606d6",
        ),
        (
            "controlX",
            "control",
            (0, bottom, z),
            (-hx, bottom, z),
            (hx, bottom, z),
            "build_sm_knife_mount.py:build (BlockProfile),BLK_BOT,SUPPORT_Z_THICK; main21f2606d6",
        ),
        (
            "controlZ",
            "control",
            (hx, bottom, 0),
            (hx, bottom, -z),
            (hx, bottom, z),
            "build_sm_knife_mount.py:build (BlockProfile),BLK_BOT,SUPPORT_Z_THICK; main21f2606d6",
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
    visibility: _VisibilityTelemetry | None = None,
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
        for ordinal, leaf in enumerate(retained[:COMPONENT_CAP]):
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
            if visibility is not None:
                visibility.component(leaf.path, leaf.component, ordinal, budget)
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
            census = (
                visibility.census(component["instance"], family) if visibility else None
            )
            try:
                reported = budget.call(
                    view, "IView", "GetVisibleEntityCount2", component["component"], 1
                )
            except Exception as exc:
                if census is not None:
                    census["reported_total"] = _metadata_field(
                        census["stage"], reason=_error(exc), status="error"
                    )
                raise
            if census is not None:
                visibility.reuse("IView", "GetVisibleEntityCount2")

                def strict_count():
                    value = _metadata_scalar(reported, int)
                    if value is not None and value < 0:
                        raise ValueError("negative native visible entity count")
                    return value

                census["reported_total"] = _metadata_field(
                    census["stage"], strict_count
                )
            count = int(reported or 0)
            scan["reported_total"] = count
            if count > EDGE_CAP:
                scan.update(
                    truncated=True,
                    unavailable="visible edge count exceeds fixed cap; no enumeration",
                )
                if census is not None:
                    census["enumeration_error"] = (
                        "original fixed cap refuses enumeration"
                    )
                    visibility.finish_census(census)
                return {}
            budget.check("raw_visible_entities")
            try:
                edges = sw_drawing.raw_visible_entities(view, component["component"], 1)
            except Exception as exc:
                if census is not None:
                    census["enumeration_error"] = _error(exc)
                    visibility.finish_census(census)
                raise
            observed: list[dict[str, Any]] = (
                [{} for _ in edges] if census is not None else []
            )
            if census is not None:
                census["rows"] = [
                    {
                        "ordinal": index,
                        "status": "budget_skipped",
                        **{
                            member: _metadata_field(
                                census["stage"],
                                reason="optional metadata not examined: allowance/cap/original discovery interruption",
                                status="budget_skipped",
                            )
                            for member in ("GetCurve", "IsLine", "GetCurveParams2")
                        },
                    }
                    for index in range(len(edges))
                ]
                visibility.pending_censuses.append((census, edges, observed))
                visibility.reuse("IView", "GetVisibleEntities2")
                census["returned_total"] = len(edges)
                native_count = _value(census, "reported_total")
                census["enumeration_status"] = (
                    "inconsistent"
                    if not edges and native_count not in (None, 0)
                    else "ambiguous"
                    if not edges
                    else "incomplete"
                    if native_count is None
                    else "complete"
                    if native_count == len(edges)
                    else "inconsistent"
                )
                census["native_return_shape"] = _metadata_field(
                    census["stage"],
                    (lambda: "nonempty helper sequence") if edges else None,
                    reason="helper normalizes native null and empty",
                )
            scan["returned_total"] = len(edges)
            scan["truncated"] = len(edges) > EDGE_CAP
            matches: dict[str, list[tuple[Any, Any]]] = {
                key: [] for key, w in source.items() if w["family"] == family
            }
            for edge_index, edge in enumerate(edges[:EDGE_CAP]):
                budget.check("visible straight edge")
                scan["examined"] += 1
                try:
                    native_member, native_before = "GetCurve", budget.calls
                    curve = budget.call(edge, "IEdge", "GetCurve")
                    if census is not None:
                        observed[edge_index]["GetCurve"] = curve is not None
                        visibility.reuse("IEdge", "GetCurve")
                    native_member, native_before = "IsLine", budget.calls
                    is_line = (
                        budget.call(curve, "ICurve", "IsLine")
                        if curve is not None
                        else None
                    )
                    if census is not None and curve is not None:
                        observed[edge_index]["IsLine"] = is_line
                        visibility.reuse("ICurve", "IsLine")
                    if curve is None or not is_line:
                        continue
                    native_member, native_before = "GetCurveParams2", budget.calls
                    raw_params = budget.call(edge, "IEdge", "GetCurveParams2")
                    if census is not None:
                        observed[edge_index]["GetCurveParams2"] = raw_params
                        visibility.reuse("IEdge", "GetCurveParams2")
                    params = tuple(float(v) for v in (raw_params or ()))
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
                except (_Deadline, _Nonfinite, TypeError, AssertionError) as exc:
                    if census is not None and native_member not in observed[edge_index]:
                        attempted = budget.calls > native_before
                        observed[edge_index][f"{native_member}_error"] = {
                            "status": "error" if attempted else "budget_skipped",
                            "error": _error(exc),
                        }
                        if attempted:
                            visibility.reuse(
                                "ICurve" if native_member == "IsLine" else "IEdge",
                                native_member,
                            )
                    raise
                except Exception as exc:
                    if census is not None:
                        if native_member not in observed[edge_index]:
                            observed[edge_index][f"{native_member}_error"] = {
                                "status": "error",
                                "error": _error(exc),
                            }
                            visibility.reuse(
                                "ICurve" if native_member == "IsLine" else "IEdge",
                                native_member,
                            )
                    scan["errors"].append(
                        {"edge_index": scan["examined"] - 1, "error": _error(exc)}
                    )
            if census is not None:
                visibility.census_extras(census, edges, budget, observed)
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
        if visibility is not None:
            for census, edges, observed in tuple(visibility.pending_censuses):
                visibility.census_extras(
                    census, edges, budget, observed, allow_native=False
                )
            for census in visibility.data["censuses"]:
                visibility.finish_census(census)
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
        for arm in ARMS:
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
def _isolate_state_native_error(state: dict[str, Any]):
    """Abandon only an operational native state, never checkpoint/adjudication CPU."""
    try:
        yield
    except (_Deadline, TypeError, AssertionError):
        raise
    except Exception as exc:
        stage = state["operation_stage"]
        if isinstance(exc, _Nonfinite):
            recoverable = stage in (
                "opening-native-bracket",
                "selection",
                "closing-native-bracket",
            )
        else:
            recoverable = stage in (
                "zoom-entry",
                "opening-native-bracket",
                "selection",
                "closing-native-bracket",
                "post-bracket-clear",
                "capture",
                "zoom-exit",
            )
        if not recoverable:
            raise
        state["operational_error"] = {
            "error": _error(exc),
            "error_type": type(exc).__name__,
            "stage": stage,
            "state": state["id"],
            "traceback": "".join(traceback.format_exception(exc)),
            "exception_notes": list(getattr(exc, "__notes__", ())),
            **_stamp(),
        }


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
                if body_error is None:
                    state["operation_stage"] = "zoom-exit"
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
    _count("phase_brackets")
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
    requested: Sequence[float],
    expected_phase: Sequence[float] | None,
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
        error = max(abs(delta[i] - requested[i]) for i in range(2))
        gate(
            "achieved_translation",
            True,
            error <= ACHIEVED_TOLERANCE,
            {"requested": requested, "achieved": delta, "max_error": error},
        )
        if arm == "A":
            gate(
                "A_restoration",
                True,
                max(abs(v) for v in delta) <= A_RESTORATION_TOLERANCE,
                delta,
            )
        checks["output_evidence"] = _output_evidence(actual, initial)
        if arm != "A":
            fractions = [
                float(value) - math.floor(float(value)) for value in actual[:2]
            ]
            phase_error = (
                max(abs(fractions[i] - expected_phase[i]) for i in range(2))
                if expected_phase is not None
                else None
            )
            gate(
                "absolute_phase",
                expected_phase is not None,
                phase_error is not None and phase_error <= ACHIEVED_TOLERANCE,
                {
                    "actual": fractions,
                    "expected": expected_phase,
                    "max_error": phase_error,
                },
            )
            gate(
                "interior_phase",
                True,
                all(min(f, 1 - f) >= 0.01 for f in fractions),
                fractions,
            )
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


def _reference_context(
    bracket: Mapping[str, Any], frozen: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    viewport = bracket["viewport"]
    control = _value(viewport, "Transform_control") or {}
    array = control.get("array")
    scale = float(array[12]) if array is not None else None
    orientation = (
        _linear(array)[:2, :2] / scale if scale is not None and scale > 0 else None
    )
    checks = {
        "native_control": bool(control.get("valid")),
        "uniform_scale": scale is not None
        and scale > 0
        and abs(scale / 119600.0 - 1) <= SCALE_RELATIVE_TOLERANCE,
        "normalized_2x2_orientation": orientation is not None
        and float(np.max(np.abs(orientation - np.diag([1.0, -1.0])))) <= 1e-6,
    }
    scale2 = _value(viewport, "Scale2")
    checks["Scale2"] = (
        scale2 is not None
        and scale2 > 0
        and abs(scale2 / 55.88 - 1) <= SCALE_RELATIVE_TOLERANCE
    )
    for key, expected in REFERENCE_FRAME.items():
        checks[key] = _value(viewport, key) == expected
    windows = _value(viewport, "windows") or {}
    for key, expected in REFERENCE_WINDOWS.items():
        actual = _value(windows, key)
        if key.endswith("awareness"):
            actual = (actual or {}).get("awareness")
        checks[f"windows.{key}"] = actual == expected
    normals = {}
    for fixed in frozen:
        normal = None
        if orientation is not None and checks["normalized_2x2_orientation"]:
            projected = np.linalg.solve(orientation.T, fixed["normal"])
            normal = (projected / np.linalg.norm(projected)).tolist()
        normals[fixed["id"]] = normal
        checks[f"normal.{fixed['id']}"] = (
            normal is not None
            and max(
                abs(normal[i] - REFERENCE_OUTPUT_NORMALS[fixed["id"]][i])
                for i in range(2)
            )
            <= 1e-6
        )
    _finite_tree((scale, normals))
    return {
        "admitted": all(checks.values()),
        "checks": checks,
        "failed": [key for key, passed in checks.items() if not passed],
        "uniform_scale": scale,
        "output_normals": normals,
        "normalized_2x2": orientation.tolist() if orientation is not None else None,
        "reference_source": REFERENCE_SOURCE,
        "reference_report": REFERENCE_REPORT,
        "reference_report_sha256": REFERENCE_REPORT_SHA256,
        "excluded_from_cross_run_equality": [
            "HWND",
            "PID",
            "thread IDs",
            "awareness contexts",
            "timestamps",
        ],
    }


def _derive_phases(first: Mapping[str, Any]) -> dict[str, Any] | None:
    viewport = first["viewport"]
    control = _value(viewport, "Transform_control") or {}
    original = _value(viewport.get("fixed_point_outputs", {}), "original")
    if not control.get("valid") or original is None:
        return None
    linear = _linear(control["array"])[:2, :2]
    determinant = float(np.linalg.det(linear))
    if determinant == 0 or not math.isfinite(determinant):
        return None
    inverse = np.linalg.inv(linear)
    shifts = {"A": [0.0, 0.0]}
    for arm, phase in PHASE_TARGETS.items():
        shifts[arm] = [
            (phase - (float(q) - math.floor(float(q)))) % 1 + INTEGER_OFFSETS[arm]
            for q in original[:2]
        ]
    offsets = {arm: (-inverse @ shift).tolist() for arm, shift in shifts.items()}
    phases = {
        arm: {
            point: (
                [PHASE_TARGETS[arm]] * 2
                if point == "original" and arm != "A"
                else [(float(q[i]) + shift[i]) % 1 for i in range(2)]
            )
            for point, field in viewport["fixed_point_outputs"].items()
            if (q := field.get("value")) is not None
        }
        for arm, shift in shifts.items()
    }
    result = {
        "linear_2x2": linear.tolist(),
        "inverse_2x2": inverse.tolist(),
        "determinant": determinant,
        "first_A_original_output": list(original),
        "first_A_point_outputs": {
            point: list(field["value"])
            for point, field in viewport["fixed_point_outputs"].items()
            if field.get("value") is not None
        },
        "requested_output_shifts": shifts,
        "sheet_centre_offsets_m": offsets,
        "expected_point_phases": phases,
        "derived_once_no_feedback": True,
    }
    _finite_tree(result)
    return result


def _prediction(
    witness_id: str,
    point_id: str,
    arm: str,
    bracket: Mapping[str, Any],
    derivation: Mapping[str, Any],
) -> dict[str, Any]:
    outputs = bracket["viewport"].get("fixed_point_outputs", {})
    q, edge = _value(outputs, point_id), _value(outputs, "original")
    if q is None or edge is None:
        return {
            "expected_class": None,
            "adjudicating": False,
            "reason": "native output unavailable",
        }
    # FLOOR FIRST on exact achieved binary64, never rounded q.
    offset = [math.floor(float(v)) - float(v) for v in q[:2]]
    group = [
        0 if abs(v) <= 1e-6 else -1 if abs(v + 1) <= 1e-6 else None for v in offset
    ]
    expected = None
    if arm in PHASE_TARGETS:
        expected = (
            "no-selection"
            if (
                arm == "N"
                and point_id == "original"
                and witness_id in ("leverPad", "controlZ")
            )
            else "target"
        )
    elif point_id == "plus8um":
        expected = "target"
    elif None not in group:
        bits = tuple(group)
        if witness_id == "controlX":
            expected = {
                (0, 0): "target",
                (-1, -1): "target",
                (0, -1): "no-selection",
            }.get(bits)
        elif witness_id in ("leverPad", "controlZ"):
            expected = {
                (0, 0): "target",
                (0, -1): "no-selection",
                (-1, -1): "no-selection",
            }.get(bits)
        else:
            expected = "target"
    distance = sum(
        REFERENCE_OUTPUT_NORMALS[witness_id][i]
        * (math.floor(float(q[i])) - float(edge[i]))
        for i in range(2)
    )
    actual_floor_group = [math.floor(float(q[i])) - float(edge[i]) for i in range(2)]
    first_points = derivation.get("first_A_point_outputs", {})
    shift = derivation.get("requested_output_shifts", {}).get(arm)
    expected_floor_group = None
    if point_id in first_points and "original" in first_points and shift is not None:
        predicted_q = [first_points[point_id][i] + shift[i] for i in range(2)]
        predicted_edge = [first_points["original"][i] + shift[i] for i in range(2)]
        expected_floor_group = [
            math.floor(predicted_q[i]) - predicted_edge[i] for i in range(2)
        ]
    return {
        "expected_class": expected,
        "adjudicating": expected is not None,
        "floor_minus_exact_output": offset,
        "floor_offset_group": group,
        "signed_floor_distance": distance,
        "actual_floor_offset_from_original_edge_output": actual_floor_group,
        "expected_floor_offset_from_original_edge_output": expected_floor_group,
        "expected_group_uses_first_A_plus_frozen_request_no_feedback": True,
        "radius_interval_closed_lower_open_upper": REFERENCE_RADIUS_BOUNDS[witness_id],
        "distance_is_descriptive_not_prediction_threshold": True,
        "zero_distance_label": "model-implied d=0, NOT observed selection"
        if arm == "A"
        and point_id == "original"
        and group == [0, 0]
        and witness_id in ("controlX", "leverPad")
        else None,
    }


def _history_admission(
    history: Mapping[str, Any], intended_owner: str
) -> dict[str, Any]:
    calls, anchors = history.get("calls", []), history.get("anchors", [])
    boundary = history.get("baseline_sequence")
    reasons = []
    if history.get("source_coverage") != "1667-leaf-selection-prefix-audit/21f2606d6":
        reasons.append("source-prefix coverage unavailable")
    if (
        history.get("source_coverage_kind")
        != "source-audit-attestation-not-runtime-native-coverage"
    ):
        reasons.append("source-prefix attestation kind unavailable")
    if history.get("discovery_before_attachment") is not True:
        reasons.append("attachment exclusion unavailable")
    if [r.get("sequence") for r in calls] != list(range(1, len(calls) + 1)):
        reasons.append("global sequence incomplete/duplicate/out-of-order")
    if intended_owner and boundary:
        baseline = next((r for r in calls if r["sequence"] == boundary), {})
        order, stem = history.get("source_order", []), baseline.get("anchor")
        prior = order[: order.index(stem)] if stem in order else None
        if prior is None or [a.get("stem") for a in anchors] != prior:
            reasons.append("executed source-order prefix not reconciled")
        prefix = [r for r in calls if r["sequence"] < boundary]
        if sum(a.get("attempts", 0) for a in anchors) != len(prefix):
            reasons.append("actual completed anchor-attempt sum mismatch")
        for anchor in anchors:
            rows = [r for r in prefix if r.get("anchor") == anchor.get("stem")]
            if not (
                anchor.get("completed")
                and len(rows) == anchor.get("attempts")
                and [r["sequence"] for r in rows]
                == list(
                    range(
                        anchor.get("first_sequence", 0),
                        anchor.get("last_sequence", -1) + 1,
                    )
                )
                and all(r.get("stage") == "anchor" for r in rows)
            ):
                reasons.append(f"incomplete anchor coverage: {anchor.get('stem')}")
        expected = ["baseline"] + (
            ["immediate-repeat"] if baseline.get("raw_result") is False else []
        )
        if [r.get("stage") for r in calls if r["sequence"] >= boundary] != expected + [
            "postobserver_exact_oldXY"
        ]:
            reasons.append("baseline/repeat/postobserver chronology incomplete")
    else:
        reasons.append("natural baseline boundary unavailable")
    for row in calls:
        if row.get("raw_result") is None or row.get("raw_error"):
            reasons.append(f"raw call unavailable: {row.get('sequence')}")
        if row.get("raw_result") is True:
            owner = row.get("actual_owner")
            if row.get("owner_status") != "known" or not owner:
                reasons.append(f"unknown-owner success: {row.get('sequence')}")
            elif (
                owner.replace("\\", "/").casefold()
                == intended_owner.replace("\\", "/").casefold()
            ):
                reasons.append(f"prior lever-owner success: {row.get('sequence')}")
    return {
        "evaluated_after_sequence": calls[-1]["sequence"] if calls else 0,
        "evaluated_at_monotonic_ns": time.perf_counter_ns(),
        "source_coverage_kind": "source-audit-attestation-not-runtime-native-coverage",
        "qualified": not reasons,
        "reasons": reasons,
        "prior_call_count": len(calls),
        "status": "qualified" if not reasons else "unprimed-P unavailable",
        "actual_completed_anchor_attempts": sum(a.get("attempts", 0) for a in anchors),
        "scope": "current-leaf explicit successful selection history only; NOT cold seat/process/cache",
    }


def _append_pick_history(
    record: dict[str, Any], xy: Sequence[float], arm: str
) -> dict[str, Any] | None:
    history = _HISTORY.get()
    if history is None:
        return None
    with _timed("history_recording"):
        calls = history["calls"]
        previous = calls[-1] if calls else None
        row = {
            "sequence": len(calls) + 1,
            "api": "IModelDocExtension.SelectByID2",
            "callsite": "_drawing_sm_pose_diagnostic._pick",
            "stage": arm,
            "sheet_xy_m": list(xy),
            "raw_call_status": "attempted",
            "raw_result": record.get("raw_result"),
            "raw_error": record.get("raw_error"),
            "actual_owner": None,
            "owner_status": "unknown",
            **{
                key: record[key]
                for key in (
                    "select_begin_utc_ns",
                    "select_end_utc_ns",
                    "select_begin_monotonic_ns",
                    "select_end_monotonic_ns",
                    "select_ms",
                )
            },
        }
        record["global_sequence"] = row["sequence"]
        record["global_predecessor"] = dict(previous) if previous else None
        record["sub15ms_after_rawmiss_descriptive_only"] = bool(
            previous
            and previous.get("raw_result") is False
            and record.get("select_ms", 15) < 15
        )
        calls.append(row)
    return row


def _point_protocol_unavailable(state: Mapping[str, Any], point_id: str) -> list[str]:
    reasons = []
    if state.get("reference_context", {}).get("admitted") is not True:
        reasons.append("reference_context")
    for name in ("before", "after"):
        if (
            state.get("point_controls", {})
            .get(point_id, {})
            .get(name, {})
            .get("admitted")
            is not True
        ):
            reasons.append(f"{name}_point_controls")
    before = state.get("predictions", {}).get(point_id)
    after = state.get("closing_predictions", {}).get(point_id)
    if before is None or after is None:
        reasons.append("prediction_or_closing_prediction")
    elif before["expected_class"] != after["expected_class"]:
        reasons.append("prediction_changed_in_bracket")
    pick = state.get("picks", {}).get(point_id, {})
    if pick.get("raw_call_status") != "attempted" or not isinstance(
        pick.get("raw_result"), bool
    ):
        reasons.append("raw_call_unavailable")
    if pick.get("selection_identity_readable") is not True:
        reasons.append("selection_identity")
    return reasons


def _adjudicate(witness: dict[str, Any]) -> None:
    states = witness["states"]
    scales = [
        _value(state.get(bracket, {}).get("viewport", {}), "Scale2")
        for state in states
        for bracket in ("before", "after")
    ]
    scale_valid = bool(scales) and all(
        v is not None and math.isfinite(v) and v > 0 for v in scales
    )
    variation = (max(scales) - min(scales)) / min(scales) if scale_valid else None
    endpoints = {}
    for point_id in witness["fixed"]["points"]:
        missing, failures, contradictions, predictions = [], [], [], []
        if (
            witness["id"] == "leverPad"
            and point_id == "original"
            and not witness.get("first_P_history_admission", {}).get("qualified")
        ):
            missing.append("unprimed-P unavailable")
        timings = {}
        for arm in ARMS:
            samples = [
                {
                    "state": s["id"],
                    "block": s["block"],
                    "index": s["index"],
                    "select_ms": s["picks"][point_id]["select_ms"],
                    "first_after_zoom": s["picks"][point_id]["first_after_zoom"],
                    "global_sequence": s["picks"][point_id].get("global_sequence"),
                }
                for s in states
                if s["arm"] == arm
                and point_id in s["picks"]
                and "select_ms" in s["picks"][point_id]
            ]
            values = [s["select_ms"] for s in samples]
            timings[arm] = {
                "n": len(samples),
                "samples": samples,
                "range_ms": [min(values), max(values)] if values else None,
                "descriptive_only_not_speedup_delta": True,
            }
        for state in states:
            if state.get("reference_context", {}).get("admitted") is not True:
                failures.append(f"{state['id']}.reference_context")
            for name in ("before", "after"):
                control = state.get("point_controls", {}).get(point_id, {}).get(name)
                if control is None:
                    missing.append(f"{state['id']}.{name}")
                else:
                    missing.extend(
                        f"{state['id']}.{name}.{key}"
                        for key in control["missing_metadata"]
                    )
                    failures.extend(
                        f"{state['id']}.{name}.{key}"
                        for key in control["observed_control_failures"]
                    )
            before = state.get("predictions", {}).get(point_id)
            after = state.get("closing_predictions", {}).get(point_id)
            pick = state.get("picks", {}).get(point_id, {})
            if pick.get("selection_identity_readable") is not True:
                missing.append(f"{state['id']}.selection_identity")
            if before is None or after is None or "raw_result" not in pick:
                missing.append(f"{state['id']}.prediction_or_pick")
                continue
            # Ambiguous A groups do not adjudicate; any before/after prediction
            # change is a protocol failure, not an outcome exclusion.
            expected = before["expected_class"]
            if expected != after["expected_class"]:
                failures.append(f"{state['id']}.prediction_changed_in_bracket")
            unavailable = _point_protocol_unavailable(state, point_id)
            matched = None
            if expected is not None and not unavailable:
                matched = (
                    (
                        pick.get("raw_result") is True
                        and pick.get("accepted_own_edge") is True
                        and pick.get("selection_identity_class") == "target"
                    )
                    if expected == "target"
                    else (
                        pick.get("raw_result") is False
                        and pick.get("canonical_empty_selection") is True
                        and pick.get("selection_identity_class") == "no-selection"
                    )
                )
            predictions.append(
                {
                    "state": state["id"],
                    "arm": state["arm"],
                    "expected": expected,
                    "actual": pick.get("selection_identity_class"),
                    "protocol_qualified": not unavailable,
                    "protocol_unavailable_reasons": unavailable,
                    "matches": matched,
                }
            )
            if matched is False:
                contradictions.append(state["id"])
        if variation is not None and variation > SCALE_RELATIVE_TOLERANCE:
            failures.append("aggregate_Scale2_variation")
        p = [row for row in predictions if row["arm"] in ("P-", "P+")]
        all_p = len(p) == 4 and all(row["matches"] is True for row in p)
        if witness.get("collection_error"):
            failures.append("witness_native_error_or_restoration")
        admitted = len(states) == 14 and not missing and not failures
        ready = admitted and all_p and not contradictions
        endpoints[point_id] = {
            "label": "candidate-consistent"
            if ready
            else "incomplete"
            if missing or len(states) != 14
            else "control-failed"
            if failures
            else "prediction-contradiction",
            "admitted": admitted,
            "candidate_ready": ready,
            "missing_metadata": missing,
            "observed_control_failures": failures,
            "contradictions": contradictions,
            "predictions": predictions,
            "all_four_P_exact_targets": all_p,
            "scale_relative_variation": variation,
            "per_arm_selection_timing": timings,
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
        "witness_errors": [],
        "begin": _stamp(),
        "capture_asymmetry": "Pad calibration A; other first A; first block P-/N/P+ after picks and closing bracket; no block2 captures",
    }
    try:
        budget.check("explicit initial fit")
        with _timed("explicit_initial_fit"):
            _invoke(budget, adapter.currentModel, "IModelDoc2", "ViewZoomtofit2")
        report["study"]["explicit_initial_fit_completed"] = True
        for witness, fixed in zip(witnesses, frozen, strict=True):
            budget.check(f"start witness {witness['id']}")
            record: dict[str, Any] = {
                "id": witness["id"],
                "fixed": fixed,
                "states": [],
                "begin": _stamp(),
                "phase_event_call_count": 0,
                "event_call_exception_count": 0,
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
                        derivation = None
                        first = None
                        sequences = (
                            PAD_BLOCKS if witness["id"] == "leverPad" else BLOCKS
                        )
                        if witness["id"] == "leverPad":
                            calibration = {
                                "id": "calibrationA",
                                "arm": "A",
                                "picks": {},
                                "begin": _stamp(),
                                "operation_stage": "zoom-entry",
                            }
                            record["calibration"] = calibration
                            with (
                                _timed("calibration_zoom_bracket_cleanup"),
                                _isolate_state_native_error(calibration),
                                _study_zoom(
                                    adapter,
                                    fixed["centre_sheet_xy_m"],
                                    calibration,
                                    budget,
                                ),
                            ):
                                calibration["operation_stage"] = (
                                    "opening-native-bracket"
                                )
                                calibration["before"] = _phase_bracket(
                                    adapter, view, utility, fixed, components, budget
                                )
                                calibration["operation_stage"] = "offset-derivation"
                                first = calibration["before"]
                                derivation = _derive_phases(first)
                                record["offset_derivation"] = derivation
                                calibration["reference_context"] = _reference_context(
                                    first, frozen
                                )
                                report["cross_run_reference_context"] = calibration[
                                    "reference_context"
                                ]
                                calibration["point_controls"] = {
                                    point: _bracket_controls(
                                        first,
                                        first,
                                        report["pose_reference"],
                                        point,
                                        "A",
                                        (0.0, 0.0),
                                        None,
                                    )
                                    for point in fixed["points"]
                                }
                                calibration["source_pose_controls_admitted"] = all(
                                    control["admitted"]
                                    for control in calibration[
                                        "point_controls"
                                    ].values()
                                )
                                calibration["operation_stage"] = "post-bracket-clear"
                                _invoke(
                                    budget,
                                    adapter.currentModel,
                                    "IModelDoc2",
                                    "ClearSelection2",
                                    True,
                                )
                                calibration["operation_stage"] = "capture"
                                calibration["capture"] = _capture_png(
                                    report,
                                    "leverPad.A.png",
                                    _value(first["viewport"], "main_window_hwnd") or 0,
                                )
                            calibration["end"] = _stamp()
                            with _timed("calibration_checkpoint"):
                                checkpoint()
                            if "operational_error" in calibration:
                                record["collection_error"] = {
                                    **calibration["operational_error"],
                                    "witness": witness["id"],
                                }
                                report["study"]["witness_errors"].append(
                                    record["collection_error"]
                                )
                                sequences = ()
                            elif (
                                not calibration["reference_context"]["admitted"]
                                or not calibration["source_pose_controls_admitted"]
                                or derivation is None
                            ):
                                report["study_refusal"] = (
                                    "cross-run calibration/source-pose context mismatch or invalid first-A inverse"
                                )
                                raise _Deadline(report["study_refusal"])
                        for block, sequence in enumerate(sequences, start=1):
                            for index, arm in enumerate(sequence):
                                budget.check(
                                    f"{witness['id']} block{block} state{index}"
                                )
                                state = {
                                    "id": f"b{block}s{index}",
                                    "block": block,
                                    "index": index,
                                    "arm": arm,
                                    "picks": {},
                                    "begin": _stamp(),
                                    "operation_stage": "zoom-entry",
                                }
                                record["states"].append(state)
                                if derivation is None and arm != "A":
                                    state["refusal"] = (
                                        "first A native transform missing/singular; offsets cannot be derived"
                                    )
                                    checkpoint()
                                    continue
                                offset = (
                                    (0.0, 0.0)
                                    if derivation is None
                                    else derivation["sheet_centre_offsets_m"][arm]
                                )
                                centre = tuple(
                                    fixed["centre_sheet_xy_m"][i] + offset[i]
                                    for i in range(2)
                                )
                                state["requested_zoom_centre_sheet_xy_m"] = centre
                                with (
                                    _isolate_state_native_error(state),
                                    _study_zoom(adapter, centre, state, budget),
                                ):
                                    state["operation_stage"] = "opening-native-bracket"
                                    state["before"] = _phase_bracket(
                                        adapter,
                                        view,
                                        utility,
                                        fixed,
                                        components,
                                        budget,
                                    )
                                    state["operation_stage"] = "offset-derivation"
                                    if first is None:
                                        first = state["before"]
                                        derivation = _derive_phases(first)
                                        record["offset_derivation"] = derivation
                                    state["reference_context"] = _reference_context(
                                        state["before"], frozen
                                    )
                                    if (
                                        derivation is None
                                        or not state["reference_context"]["admitted"]
                                    ):
                                        report["study_refusal"] = (
                                            "cross-run state context mismatch or invalid first-A inverse"
                                        )
                                        raise _Deadline(report["study_refusal"])
                                    state["requested_output_shift"] = derivation[
                                        "requested_output_shifts"
                                    ][arm]
                                    state["predictions"] = {
                                        point: _prediction(
                                            witness["id"],
                                            point,
                                            arm,
                                            state["before"],
                                            derivation,
                                        )
                                        for point in fixed["points"]
                                    }
                                    state["operation_stage"] = "point-order"
                                    point_order = list(fixed["points"])
                                    if witness["id"] == "leverPad":
                                        point_order = (
                                            ["original", "plus8um"]
                                            if arm in ("P-", "P+")
                                            else ["plus8um", "original"]
                                        )
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
                                            "raw_call_status": "not-attempted",
                                        }
                                        state["picks"][point_id] = pick
                                        picks_total += 1
                                        state["operation_stage"] = "selection"
                                        if (
                                            witness["id"] == "leverPad"
                                            and block == 1
                                            and index == 0
                                            and point_id == "original"
                                        ):
                                            report["first_P_history_admission"] = (
                                                _history_admission(
                                                    report["selection_history"],
                                                    report["intended_instance"],
                                                )
                                            )
                                            record["first_P_history_admission"] = (
                                                report["first_P_history_admission"]
                                            )
                                        try:
                                            _pick(
                                                adapter,
                                                fixed["points"][point_id],
                                                witness,
                                                arm,
                                                budget,
                                                record=pick,
                                                view=view,
                                            )
                                        finally:
                                            if pick["raw_call_status"] == "attempted":
                                                history_fields = {}
                                                if (
                                                    witness["id"] == "leverPad"
                                                    and block == 1
                                                    and index == 0
                                                    and point_id == "original"
                                                ):
                                                    admission = record[
                                                        "first_P_history_admission"
                                                    ]
                                                    history_fields = {
                                                        "history_boundary_sequence": admission[
                                                            "evaluated_after_sequence"
                                                        ],
                                                        "history_evaluated_at_monotonic_ns": admission[
                                                            "evaluated_at_monotonic_ns"
                                                        ],
                                                    }
                                                _event(
                                                    "phase_pick",
                                                    report,
                                                    json_path=report["checkpoint"][
                                                        "path"
                                                    ],
                                                    witness=witness["id"],
                                                    state=state["id"],
                                                    point=point_id,
                                                    global_sequence=pick[
                                                        "global_sequence"
                                                    ],
                                                    result=pick.get(
                                                        "selection_identity_class",
                                                        "unreadable",
                                                    ),
                                                    raw_result=pick.get("raw_result"),
                                                    raw_error=pick.get("raw_error", ""),
                                                    select_ms=pick["select_ms"],
                                                    **history_fields,
                                                )
                                    state["operation_stage"] = "closing-native-bracket"
                                    state["after"] = _phase_bracket(
                                        adapter,
                                        view,
                                        utility,
                                        fixed,
                                        components,
                                        budget,
                                    )
                                    state["operation_stage"] = "control-adjudication"
                                    state["closing_predictions"] = {
                                        point: _prediction(
                                            witness["id"],
                                            point,
                                            arm,
                                            state["after"],
                                            derivation,
                                        )
                                        for point in fixed["points"]
                                    }
                                    state["point_controls"] = {
                                        point: {
                                            name: _bracket_controls(
                                                state[name],
                                                first,
                                                report["pose_reference"],
                                                point,
                                                arm,
                                                state["requested_output_shift"],
                                                derivation["expected_point_phases"][
                                                    arm
                                                ].get(point),
                                            )
                                            for name in ("before", "after")
                                        }
                                        for point in fixed["points"]
                                    }
                                    state["operation_stage"] = "post-bracket-clear"
                                    _invoke(
                                        budget,
                                        adapter.currentModel,
                                        "IModelDoc2",
                                        "ClearSelection2",
                                        True,
                                    )
                                    capture = block == 1 and (
                                        arm != "A"
                                        or (index == 0 and witness["id"] != "leverPad")
                                    )
                                    if capture:
                                        budget.check(
                                            "inside-zoom PNG after picks and closing bracket"
                                        )
                                        state["operation_stage"] = "capture"
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
                                if "operational_error" in state:
                                    record["collection_error"] = {
                                        **state["operational_error"],
                                        "witness": witness["id"],
                                    }
                                    report["study"]["witness_errors"].append(
                                        record["collection_error"]
                                    )
                                    break
                                _adjudicate(record)
                                checkpoint()  # OUTSIDE zoom, including after its fit cleanup.
                                budget.check("after state checkpoint")
                            if "collection_error" in record:
                                break
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
                                    "phase_event_call_count",
                                    record["phase_event_call_count"],
                                )
                                span.set_attribute(
                                    "event_call_exception_count",
                                    record["event_call_exception_count"],
                                )
                                span.set_attribute(
                                    "study_selection_attempts",
                                    sum(len(s["picks"]) for s in record["states"]),
                                )
                                span.set_attribute(
                                    "witness_collection_failed",
                                    "collection_error" in record,
                                )
            finally:
                _SPAN_EVENTS.reset(token)
                span_scope_ms = (time.perf_counter() - span_started) * 1000
                _cost("witness_span_scope_inclusive", span_scope_ms)
                _cost("witness_span_setup_cleanup", span_scope_ms - span_body_ms)
            if "collection_error" in record:
                recovery = {
                    "witness": witness["id"],
                    "state": record["collection_error"]["state"],
                    "original_helper_cleanup_notes": record["collection_error"][
                        "exception_notes"
                    ],
                    "status": "not-attempted",
                    "begin": _stamp(),
                }
                record["recovery_fit_after_witness_error"] = recovery
                budget.check("recovery fit after witness error")
                recovery_started = time.perf_counter()
                _count("recovery_fit_after_witness_error_attempts")
                recovery["status"] = "started"
                try:
                    with _timed("recovery_fit_after_witness_error"):
                        _invoke(
                            budget, adapter.currentModel, "IModelDoc2", "ViewZoomtofit2"
                        )
                    recovery["status"] = "restored"
                except (_Deadline, _Nonfinite, TypeError, AssertionError):
                    raise
                except Exception as exc:
                    recovery.update(
                        status="restoration-failed",
                        error=_error(exc),
                        traceback="".join(traceback.format_exception(exc)),
                        exception_notes=list(getattr(exc, "__notes__", ())),
                    )
                    report["study"]["restoration_failure"] = recovery
                    report["study"]["truncated"] = (
                        f"restoration-failed after witness {witness['id']}"
                    )
                finally:
                    if recovery["status"] == "started":
                        recovery["status"] = "interrupted"
                    recovery["elapsed_ms"] = (
                        time.perf_counter() - recovery_started
                    ) * 1000
                    recovery["end"] = _stamp()
                checkpoint()  # Outside the state catch, zoom and child span.
                if "restoration_failure" in report["study"]:
                    break
                budget.check("after witness-error checkpoint")
    except _Deadline as exc:
        report["study"]["truncated"] = _error(exc)
    finally:
        elapsed = (time.perf_counter() - started) * 1000
        _cost("total_study_inclusive", elapsed)
        report["study"]["budget"] = {
            **budget.report(),
            "study_selection_attempts": picks_total,
            "study_selection_cap": PICK_CAP,
            "picked_states": sum(
                len(w["states"]) for w in report["study"]["witnesses"]
            ),
            "calibration_contexts": sum(
                "calibration" in w for w in report["study"]["witnesses"]
            ),
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
    record.update(
        arm=arm, sheet_xy_m=list(xy), begin=_stamp(), raw_call_status="not-attempted"
    )
    pick_started = time.perf_counter()
    draw = adapter.currentModel
    try:
        _invoke(budget, draw, "IModelDoc2", "ClearSelection2", True)
        extension = _invoke(budget, draw, "IModelDoc2", "Extension")
        callout = null_callout()
        # Refuse BEFORE starting the raw-call clocks/ledger. Retrieval, callout,
        # history and identity bookkeeping are outside this measured interval.
        if budget is not None:
            try:
                budget.check("IModelDocExtension.SelectByID2")
            except _Deadline:
                record["raw_call_refused_before_native"] = True
                raise
            budget.calls += 1
        record["select_begin_utc_ns"] = time.time_ns()
        record["select_begin_monotonic_ns"] = time.perf_counter_ns()
        record.update(raw_call_status="attempted", raw_result=None)
        try:
            record["raw_result"] = bool(
                _native_call(
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
        except BaseException as exc:
            record["raw_error"] = _error(exc)
            raise
        finally:
            record["select_end_monotonic_ns"] = time.perf_counter_ns()
            record["select_end_utc_ns"] = time.time_ns()
            record["select_ms"] = (
                record["select_end_monotonic_ns"] - record["select_begin_monotonic_ns"]
            ) / 1e6
            history_row = _append_pick_history(record, xy, arm)
        started = time.perf_counter()
        with _timed("identity_reads_inclusive"):
            selection, entity, owner = _selected(
                draw, budget, adapter=adapter, view=view
            )
            record["selection"] = selection
            if history_row is not None:
                with _timed("history_recording"):
                    actual_owner = _value(selection, "owner")
                    history_row.update(
                        actual_owner=actual_owner,
                        owner_status="known"
                        if actual_owner
                        else "empty"
                        if _value(selection, "count") == 0
                        else "unknown",
                    )
            record["accepted_own_edge"] = (
                _identity(adapter, selection, entity, owner, target, budget)
                and record["raw_result"]
            )
        if history_row is not None:
            with _timed("history_recording"):
                history_row["canonical_target_id"] = (
                    target["id"] if target and record["accepted_own_edge"] else None
                )
                predecessor = record.get("global_predecessor") or {}
                record["same_edge_predecessor_descriptive_only"] = bool(
                    history_row["canonical_target_id"]
                    and predecessor.get("canonical_target_id")
                    == history_row["canonical_target_id"]
                )
        record["identity_ms"] = (time.perf_counter() - started) * 1000
        if handles is not None:
            handles.update(entity=entity, owner=owner)
        count = _value(selection, "count")
        same = _value(selection, "IsSame_edge")
        record["canonical_empty_selection"] = bool(
            record.get("raw_result") is False
            and count == 0
            and selection.get("all_selection_items_recorded") is True
            and selection.get("items") == []
        )
        if record["canonical_empty_selection"]:
            identity_class = "no-selection"
        elif record["accepted_own_edge"]:
            identity_class = "target"
        elif (
            count is not None
            and count > 0
            and selection.get("all_selection_items_recorded")
            and all(
                _value(item, "type") is not None and _value(item, "entity") is not None
                for item in selection["items"]
            )
        ):
            kind = _value(selection, "type")
            first_item = selection["items"][0]
            # Availability, not equality with the intended identity, qualifies
            # adjudication. Fully observed wrong owner/view/edge stays a mismatch.
            owner_name = _value(selection, "owner")
            view_names_available = not (
                count == 2 and _value(first_item, "type") == DRAWING_VIEW_SELECTION_TYPE
            ) or all(
                isinstance(_value(selection, key), str)
                and bool(_value(selection, key).strip())
                for key in ("expected_view_name", "first_selected_view_name")
            )
            if kind == 1 and (
                not isinstance(owner_name, str)
                or not owner_name.strip()
                or not view_names_available
            ):
                identity_class = "unreadable"
            elif kind == 1 and same == 1:
                identity_class = "target-edge-noncanonical"
            elif kind == 1 and same == 0:
                identity_class = "different-target"
            elif kind is not None and kind > 1:
                identity_class = "non-edge-selection"
            else:
                identity_class = "unreadable"
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
            if (
                key.endswith("_error")
                and isinstance(child, (str, dict, list))
                and child
            ):
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
            "immediate_exact_repeat": int(
                bool(immediate_repeat)
                and immediate_repeat.get("raw_call_status") == "attempted"
            ),
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
            {
                "change": "recovery_fit_after_witness_error",
                "new_output": "one measured fit after an isolated witness error; failed restoration stops later collector native calls",
                "new_cost_entry": "recovery_fit_after_witness_error",
                "baseline": "f72557b61 aborted the whole study; continuation changes completed work",
                "absolute_delta_ms": None,
                "relative_delta": None,
                "comparison": "failure-to-continuation changed workload; no performance win or extra healthy-case COM call",
            },
            {
                "change": "complete_current_leaf_raw_history",
                "new_cost_entry": "history_recording/history_flushing",
                "baseline": "Python ledger absent; existing native call/read sequence unchanged",
                "absolute_delta_ms": None,
                "relative_delta": None,
                "comparison": "partial helper-body/owner-update bookkeeping and flush; excludes scope/anchor/external row updates, overlaps selection_with_identity_inclusive; NOT total instrumentation overhead or native speedup",
            },
            {
                "change": "no_pick_A_calibration",
                "new_cost_entry": "calibration_zoom_bracket_cleanup/calibration_checkpoint",
                "baseline": "added one zoom/bracket/cleanup/checkpoint, no raw pick",
                "absolute_delta_ms": None,
                "relative_delta": None,
                "comparison": "changed study work; added cost, not a production delta",
            },
            {
                "change": "numeric_field_gap_classification",
                "new_cost_entry": "field_gap_classification",
                "baseline": "exact 912179e24 function on preserved 125-entry native payload",
                "absolute_delta_ms": None,
                "relative_delta": None,
                "comparison": "matched offline receipt prepared separately, NOT native speed",
            },
        ],
        "review_corrections": {
            "source_before": "f72557b61",
            "isolated_witness_native_errors": "operational native phase only; checkpoint/adjudication/span failures remain outside isolation; no extra healthy-case COM",
            "chronological_timing_samples": "paired state/block/index/select_ms/first_after_zoom; replaces unpaired arrays; payload changes, no extra COM",
            "truthful_selection_classes": "rawFalse own edge and noncanonical/non-edge selections are distinct; no extra identity reads",
            "absolute_delta_ms": None,
            "relative_delta": None,
            "comparison": "unmeasured/confounded instrumentation corrections; not a matched native speedup",
        },
        "cpu_attribution": {
            "checkpoint_residual": "checkpoint_total minus serialization/write/replace includes finite-tree traversal and bookkeeping; NOT native work",
            "adjudication_cpu_ms": None,
            "adjudication_status": "unmeasured in-study _adjudicate/_prediction CPU; included in inclusive study/span timings, NOT native work",
        },
    }
    report: dict[str, Any] = {
        "schema": 3,
        "experiment": "issue1667-heldout-quarter-phase-normalization",
        "probe_id": probe_id,
        "begin": _stamp(),
        "execution_identity": execution,
        "execution_identity_available": bool(execution),
        "diagnostic_only_never_publish": True,
        "baseline": {
            key: value for key, value in baseline.items() if key != "selection_history"
        },
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
            "pad_blocks": [list(block) for block in PAD_BLOCKS],
            "absolute_phase_targets": PHASE_TARGETS,
            "integer_offsets": INTEGER_OFFSETS,
            "healthy_budgets": {
                "study_picks": 112,
                "picked_states": 98,
                "calibrations": 1,
                "brackets": 197,
                "checkpoints": 102,
                "state_PNGs": 28,
            },
            "study_selection_count": PICK_CAP,
            "soft_budget_s": STUDY_SECONDS,
            "primary": "leverPad.original",
            "within_pad_control": "leverPad.plus8um",
            "other_witnesses": "secondary, adjudicated independently per point",
            "selection_classes": [
                "target",
                "no-selection",
                "different-target",
                "target-edge-noncanonical",
                "non-edge-selection",
                "unreadable",
            ],
            "readiness": "all four P exact-target successes per point, all adjudicating N/A predictions match; complete controls and history-qualified first Pad P",
            "ambiguous_A_groups": "non-adjudicating, never treated as successful predictions",
            "history_contrast": "unprimed/primed association, not isolated priming cause",
            "achieved_tolerance_output_units": ACHIEVED_TOLERANCE,
            "A_restoration_tolerance_output_units": A_RESTORATION_TOLERANCE,
            "scale_relative_tolerance": SCALE_RELATIVE_TOLERANCE,
            "matrix_tolerance": MATRIX_STABILITY_TOLERANCE,
            "no_posthoc_subset_or_substitution": True,
        },
        "evidence_limits": [
            "positive: outcome dependence on translation reported by IModelView.Transform; NOT an internal rounding/aperture mechanism",
            "scalar outputs remain transform-output units unless independent raster registration validates them",
            "quarter-phase replication is bounded to the frozen reference context, not a universal pick algorithm",
            "first-P history admission is current-leaf explicit selector coverage, NEVER cold seat/process/cache",
            "source-prefix coverage is a source-audit attestation, not runtime proof of all native or implicit selections",
            "current-main PR1761 changes receiver rib/drill geometry; unchanged witnesses and historical predictions remain hypotheses, not geometry-identical replication",
            "post-pick non-atomic controls can perturb timing/state and do not prove historical baseline pose",
            "bit-identical recorded transforms with different classes are a timing/redraw candidate, not proof of internal nondeterminism",
            "manual explode offsets are retained original numeric inputs; IsExploded does not prove continuous explode-step immutability",
            "block1 captures after picks/closing brackets are a known block asymmetry",
            "no production fix, recovery policy, paired R1 speedup, or absolute hit-test pixel convention established",
        ],
    }
    checkpoint = _Checkpoint(report, out_dir / "p.json", out_dir / "p.tmp")
    visibility = _VisibilityTelemetry(
        report, _VisibilityCheckpoint(report, checkpoint.path, checkpoint.temp)
    )
    token = _PERFORMANCE.set(performance)
    report["selection_history"] = {"calls": [], "anchors": []}
    history_token = _HISTORY.set(report["selection_history"])
    primary_error: Exception | None = None
    cancellation: BaseException | None = None
    try:
        try:
            with _timed("history_flushing"):
                history = baseline.get("selection_history")
                if history is not None:
                    _finite_tree(history)
                    report["selection_history"].update(
                        json.loads(json.dumps(history, allow_nan=False))
                    )
                    _cost("history_recording", float(history.get("recording_ms", 0.0)))
            # FIRST added native reads on a hit; after the immediate raw repeat on a
            # miss. No clear or screenshot precedes this preserved selection.
            selection, entity, owner = _selected(
                adapter.currentModel, adapter=adapter, view=view
            )
            report["initial_selection"] = selection
            # The latest existing selection read belongs to repeat if it ran, else baseline.
            calls = report["selection_history"]["calls"]
            if calls and calls[-1].get("raw_result") is not None:
                calls[-1].update(
                    actual_owner=_value(selection, "owner"),
                    owner_status="known"
                    if _value(selection, "owner")
                    else "empty"
                    if _value(selection, "count") == 0
                    else "unknown",
                )
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
            visibility.profile(adapter, view)
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
                visibility,
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
                _phase_study(
                    adapter, view, utility, witnesses, frozen, report, checkpoint
                )
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
            report["candidate_ready"] = bool(
                report.get("first_P_history_admission", {}).get("qualified")
                and all(
                    endpoint.get("candidate_ready")
                    for points in report["endpoints"].values()
                    for endpoint in points.values()
                )
                and report.get("study", {})
                .get("budget", {})
                .get("raw_results_recorded")
                == PICK_CAP
                and not report.get("study", {}).get("witness_errors")
                and not report.get("study", {}).get("truncated")
            )
            report["preregistered_evidence_sufficient"] = report["candidate_ready"]
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
                and not study.get("witness_errors")
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
            restoration_failed = bool(
                report.get("study", {}).get("restoration_failure")
            )
            native_followup_refused = restoration_failed or any(
                "collection_error" in witness
                and witness.get("recovery_fit_after_witness_error", {}).get("status")
                != "restored"
                for witness in report.get("study", {}).get("witnesses", ())
            )
            report["native_followup_refused"] = native_followup_refused
            try:
                if not native_followup_refused:
                    _invoke(
                        None,
                        adapter.currentModel,
                        "IModelDoc2",
                        "ClearSelection2",
                        True,
                    )
                else:
                    report["final_clear_refusal"] = (
                        "witness-error restoration failed or did not complete; no later collector native calls"
                    )
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
            if (
                cancellation is None
                and not native_followup_refused
                and primary_error is None
                and report.get("study", {}).get("explicit_initial_fit_completed")
            ):
                visibility.profile(adapter, view, after=True)
            else:
                visibility.data["profile_after"] = _metadata_field(
                    "post_study_cleanup_fit_non_atomic",
                    reason="defined post-study fit state not established or native followup refused",
                )
            if cancellation is None:
                visibility.inventory()
            else:
                visibility.data["os_inventory"] = _metadata_field(
                    "post_study_os_inventory", reason="cancellation refuses new work"
                )
            visibility.finish()
            if native_followup_refused:
                report["final_poststudy_capture_bundle"] = {
                    "status": "refused",
                    "reason": "witness-error restoration failed or did not complete; mandatory outer caller cleanup is outside this collector",
                }
            if (
                not native_followup_refused
                and cancellation is None
                and not isinstance(
                    primary_error, (_Nonfinite, TypeError, AssertionError)
                )
            ):
                final_paths = [
                    v
                    for key, v in path_budget["paths"].items()
                    if key.startswith("final.")
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
                                {
                                    "stage": "final_capture",
                                    "error": _error(exc),
                                    **_stamp(),
                                }
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
            report["witness_error_count"] = len(
                report.get("study", {}).get("witness_errors", ())
            )
            performance["collector_elapsed_ms_before_final_checkpoint"] = (
                time.perf_counter() - collector_started
            ) * 1000
            with _timed("field_gap_classification"):
                report["unavailable_or_error_fields"] = _field_failures(report)
            # Primary endpoint is never gated by completion of later secondary witnesses
            # or by optional captures. Exceptional partial studies still expose per-point data.
            if "primary_endpoint" not in report:
                reached = {
                    w["id"]: w for w in report.get("study", {}).get("witnesses", [])
                }
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
                report["candidate_ready"] = False
                report["preregistered_evidence_sufficient"] = False
            first_pad = next(
                (
                    w
                    for w in report.get("study", {}).get("witnesses", [])
                    if w["id"] == "leverPad"
                ),
                {},
            )
            pad_p_states = [
                state
                for state in first_pad.get("states", [])
                if state["arm"] in ("P-", "P+")
            ]
            pad_p = [
                state.get("picks", {}).get("original", {}) for state in pad_p_states
            ]
            pad_p_qualified = [
                not _point_protocol_unavailable(state, "original")
                for state in pad_p_states
            ]
            history_qualified = report.get("first_P_history_admission", {}).get(
                "qualified", False
            )
            report["unprimed_primed_contrast"] = {
                "first_P_history_qualified": history_qualified,
                "first_P_exact_target": pad_p[0].get("accepted_own_edge")
                if pad_p
                else None,
                "later_P_exact_targets": [
                    p.get("accepted_own_edge") for p in pad_p[1:]
                ],
                "compared_P_protocol_qualified": pad_p_qualified,
                "first_miss_later_hit_association": bool(
                    history_qualified
                    and pad_p
                    and pad_p_qualified[0]
                    and pad_p[0].get("canonical_empty_selection")
                    and any(
                        qualified and p.get("accepted_own_edge")
                        for qualified, p in zip(
                            pad_p_qualified[1:], pad_p[1:], strict=True
                        )
                    )
                ),
                "interpretation": "association consistent with history/priming dependence; NOT an isolated causal effect",
                "timing_flags_never_erase_contradiction": True,
            }
            try:
                checkpoint(final=True)  # One final attempt, even after a prior OSError.
            except Exception as exc:
                report["artifact_serialization_or_programming_error"] = _error(exc)
                report["complete"] = False
                with contextlib.suppress(Exception):
                    _telemetry.warn(
                        f"[1667] FINAL checkpoint not serialized: {exc}",
                        probe_id=probe_id,
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
                    witness_error_count=report["witness_error_count"],
                    restoration_failed=restoration_failed,
                    native_followup_refused=native_followup_refused,
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
    finally:
        _HISTORY.reset(history_token)
        _PERFORMANCE.reset(token)
    if cancellation is not None:
        raise cancellation
    raise RuntimeError(
        f"{STOP} baseline_raw={report['baseline_raw_result']} complete={report['complete']} "
        f"primary={report['primary_endpoint']['label']} "
        f"witness_errors={report['witness_error_count']} "
        f"restoration_failed={restoration_failed} "
        f"evidence_sufficient={report['preregistered_evidence_sufficient']} artifact={checkpoint.path}"
    ) from primary_error
