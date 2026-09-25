"""Farm executor: dispatch one cache-missing doit leaf to the SolidWorks build farm.

The constants, ``LeafRequest``/``LeafResult`` and ``workflow_id`` below mirror
``solidworks-pool/agent/contract.py`` field-for-field; ``FARM_PROTOCOL_VERSION``
mirrors ``agent/protocol.py`` and guards drift between the two repos (a mismatch
fails admission on the farm). This module must never import the pool package.

Configuration is the same ``~/.solidworks-pool/config.json`` that ``farm.py``
writes (``farm.py credentials issue``); ``SOLIDWORKS_POOL_CONFIG`` overrides the
path. Certificate and token paths in the file are relative to the config
directory. The farm's external frontend requires both the mTLS client
certificate and the bearer token (``Authorization: Bearer <jwt>``).
"""

from __future__ import annotations

import asyncio
import getpass
import json
import os
import socket
import threading
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import _farm_order
import _telemetry

FARM_PROTOCOL_VERSION = 4

TASK_QUEUE_CONTROL = "solidworks-control"  # BuildLeaf workflow tasks
TASK_QUEUE_COM = "solidworks-com"  # build_leaf activity tasks
WORKFLOW_BUILD_LEAF = "BuildLeaf"
ACTIVITY_BUILD_LEAF = "build_leaf"
NAMESPACE = "solidworks"

CONFIG_ENV = "SOLIDWORKS_POOL_CONFIG"
DEFAULT_CONFIG_PATH = Path.home() / ".solidworks-pool" / "config.json"
EXECUTION_TIMEOUT = timedelta(hours=8)
LEAF_TIMEOUT_DEFAULT_S = 15 * 60
LEAF_TIMEOUT_MIN_S = 60
LEAF_TIMEOUT_MAX_S = 3 * 3600


@dataclass(frozen=True)
class LeafRequest:
    farm_protocol_version: int  # must equal FARM_PROTOCOL_VERSION
    commit: str
    task: str  # exact doit task name, e.g. "part:fulcrum_keeper"
    cache_key: str | None  # 64-hex expected buildcache key; None only for check:*
    traceparent: str | None
    submitter: str  # f"{user}@{host}", UI summary only
    leaf_timeout_s: int | None = None  # per-attempt budget; None takes the default


@dataclass(frozen=True)
class LeafResult:
    state: str  # "succeeded" | "failed"
    exit_code: int | None
    worker_id: str  # f"{computername}@{instance_id}"
    attempt: int
    cache_present: bool
    log_blob: str | None  # "<results-container>/<blob-name>"
    failure_category: str | None
    failure_message: str | None  # <=1000 chars, CR/LF stripped


def clamp_leaf_timeout_s(requested: int | None) -> int:
    """The budget the farm will actually grant, mirroring its own clamp.

    The control plane clamps whatever it is given; the submitter computes the
    same value so the workflow id it dedupes on matches the budget the leaf
    will really run under.
    """

    if requested is None:
        return LEAF_TIMEOUT_DEFAULT_S
    return max(LEAF_TIMEOUT_MIN_S, min(LEAF_TIMEOUT_MAX_S, requested))


def workflow_id(task: str, cache_key: str | None, commit: str, timeout_s: int) -> str:
    return f"leaf:{task}:{cache_key or commit[:16]}:{timeout_s}s"


def enabled() -> bool:
    return os.environ.get("HARMONIC_EXECUTOR", "local") == "farm"


def config_path() -> Path:
    override = os.environ.get(CONFIG_ENV)
    if override:
        return Path(override)
    return DEFAULT_CONFIG_PATH


_CONFIG_KEYS = (
    "temporal_address",
    "namespace",
    "ca_cert",
    "client_cert",
    "client_key",
    "token",
)
_CONFIG_FILE_KEYS = ("ca_cert", "client_cert", "client_key", "token")


def load_config(path: Path | None = None) -> dict:
    """The submitter's farm config with certificate and token paths resolved.

    Every problem is a ``RuntimeError("farm config <path>: <problem>")`` naming
    the path and offending key only; certificate contents are never read here
    and the token is read only to reject a blank file.
    """
    path = path or config_path()
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise RuntimeError(
            f"farm config {path}: not found; run `farm.py credentials issue` first"
        ) from None
    except OSError as exc:
        raise RuntimeError(f"farm config {path}: {exc.strerror}") from None
    try:
        config = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"farm config {path}: invalid JSON ({exc.msg})") from None
    if not isinstance(config, dict):
        raise RuntimeError(f"farm config {path}: expected a JSON object")
    for key in _CONFIG_KEYS:
        value = config.get(key)
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError(f"farm config {path}: {key} must be a non-empty string")
    for key in _CONFIG_FILE_KEYS:
        file = (path.parent / config[key]).resolve()
        if not file.is_file() or not os.access(file, os.R_OK):
            raise RuntimeError(f"farm config {path}: {key} file is not readable")
        config[key] = str(file)
    try:
        token = Path(config["token"]).read_text(encoding="ascii").strip()
    except UnicodeDecodeError:
        raise RuntimeError(
            f"farm config {path}: token file is not an ASCII JWT"
        ) from None
    if not token:
        raise RuntimeError(f"farm config {path}: token file is empty")
    return config


def submitter() -> str:
    return f"{getpass.getuser()}@{socket.gethostname()}"


RUN_ENV = "HARMONIC_FARM_RUN"


def fairness_key() -> str:
    """The task-queue fairness key this run's leaves are dispatched under.

    The pool round-robins its COM queue across fairness keys
    (``matching.enableFairness``), so each doit run gets its own key: one run's
    whole ready set cannot bury another's. ``build.py`` sets ``HARMONIC_FARM_RUN``
    once per farm run (the supervised launcher sets it to its run id); a
    process without one falls back to the submitter, the pool's own default.
    """
    return os.environ.get(RUN_ENV, "").strip() or submitter()


def leaf_timeout_s() -> int | None:
    """The per-attempt budget this run asks for, or ``None`` for the default.

    The control plane clamps whatever it is given, so an out-of-range value is
    not an error here; a value that is not a number is, because silently
    dispatching a 62 min cold run on the default budget would fail every leaf
    the same way.
    """

    raw = os.environ.get("HARMONIC_FARM_LEAF_TIMEOUT_S", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(
            f"HARMONIC_FARM_LEAF_TIMEOUT_S is not a number of seconds: {raw!r}"
        ) from None


# Leaves this process is waiting on right now. Under the farm's ``-P thread``
# runner every doit worker is a thread of this one process, so the count read at
# submit time IS the run's fan-out; it rides each ``farm.run`` span as
# ``inflight`` so the concurrency a run achieved is readable from traces.jsonl.
_inflight_lock = threading.Lock()
_inflight = 0


def _enter_flight() -> int:
    global _inflight
    with _inflight_lock:
        _inflight += 1
        return _inflight


def _leave_flight() -> None:
    global _inflight
    with _inflight_lock:
        _inflight -= 1


def run_leaf(task: str, cache_key: str | None) -> LeafResult:
    """Run ``task`` on the farm and return its result once the workflow closes.

    Shares the workflow with any other submitter of the same leaf
    (``USE_EXISTING``), so Ctrl-C here never cancels it -- the interrupt just
    propagates.

    The ``farm.run`` span records where the leaf's time went: ``inflight`` (this
    process's leaves in flight at submit, this one included), ``submit_s``
    (connect + start), ``remote_wait_s`` (attached until the result), and, read
    back from the workflow history, ``temporal_queue_s`` (activity scheduled
    until a worker took it) and ``worker_run_s`` (taken until closed). A
    successful leaf's worker run time also feeds the critical-path ledger
    (``_farm_order.record``) that orders the next run's submissions.

    A workflow cancelled through ``farm.py cancel`` comes back as a
    failed result with ``failure_category="cancelled"``; every other failure
    (connection, protocol) propagates as-is: it is a local fault, not a build
    outcome.
    """
    with _telemetry.span(
        f"farm.run {task}", label=task, service=_telemetry.BUILD_INFRA_SERVICE
    ) as sp:
        request = LeafRequest(
            farm_protocol_version=FARM_PROTOCOL_VERSION,
            commit=os.environ["HARMONIC_FARM_COMMIT"],
            task=task,
            cache_key=cache_key,
            traceparent=_telemetry.inject_env().get("TRACEPARENT"),
            submitter=submitter(),
            leaf_timeout_s=leaf_timeout_s(),
        )
        budget = clamp_leaf_timeout_s(request.leaf_timeout_s)
        wf_id = workflow_id(task, cache_key, request.commit, budget)
        sp.set_attribute("workflow_id", wf_id)
        sp.set_attribute("leaf_timeout_s", budget)
        sp.set_attribute("inflight", _enter_flight())
        timings: dict[str, float] = {}
        try:
            result = asyncio.run(_dispatch(request, wf_id, timings))
        finally:
            _leave_flight()
            for name, seconds in timings.items():
                sp.set_attribute(name, round(seconds, 3))
        sp.set_attribute("worker", result.worker_id)
        sp.set_attribute("attempt", result.attempt)
        sp.set_attribute("state", result.state)
        if result.state == "succeeded":
            observed = timings.get("worker_run_s", timings.get("remote_wait_s"))
            if observed is not None:
                _farm_order.record(task, observed)
        return result


async def _dispatch(
    request: LeafRequest, wf_id: str, timings: dict[str, float] | None = None
) -> LeafResult:
    # temporalio loads a Rust bridge; import it only when a leaf is dispatched so
    # local builds and the offline check:* workers never pay for it.
    from temporalio.client import Client, WorkflowFailureError
    from temporalio.common import Priority, WorkflowIDConflictPolicy
    from temporalio.exceptions import CancelledError
    from temporalio.service import TLSConfig

    timings = {} if timings is None else timings
    started = time.monotonic()
    config = load_config()
    address = config["temporal_address"]
    client = await Client.connect(
        address,
        namespace=config["namespace"],
        api_key=Path(config["token"]).read_text(encoding="ascii").strip(),
        tls=TLSConfig(
            server_root_ca_cert=Path(config["ca_cert"]).read_bytes(),
            domain=address.rsplit(":", 1)[0],
            client_cert=Path(config["client_cert"]).read_bytes(),
            client_private_key=Path(config["client_key"]).read_bytes(),
        ),
        identity=request.submitter,
    )
    _telemetry.info(
        f"Farm workflow requested: {wf_id}",
        workflow_id=wf_id,
        task=request.task,
        commit=request.commit,
    )
    handle = await client.start_workflow(
        WORKFLOW_BUILD_LEAF,
        request,
        id=wf_id,
        task_queue=TASK_QUEUE_CONTROL,
        result_type=LeafResult,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        execution_timeout=EXECUTION_TIMEOUT,
        # BuildLeaf's activity inherits this; attaching to a leaf another run
        # already started keeps that run's key.
        priority=Priority(fairness_key=fairness_key()),
    )
    attached = time.monotonic()
    timings["submit_s"] = attached - started
    _telemetry.info(
        f"Farm workflow attached: {wf_id}",
        workflow_id=wf_id,
        task=request.task,
        commit=request.commit,
    )
    _telemetry.event(
        "farm.attached",
        workflow_id=wf_id,
        task=request.task,
        commit=request.commit,
    )
    try:
        result = await handle.result()
        timings["remote_wait_s"] = time.monotonic() - attached
        timings.update(await _activity_timings(handle))
        return result
    except WorkflowFailureError as exc:
        timings["remote_wait_s"] = time.monotonic() - attached
        if not isinstance(exc.cause, CancelledError):
            raise
        return LeafResult(
            state="failed",
            exit_code=None,
            worker_id="",
            attempt=0,
            cache_present=False,
            log_blob=None,
            failure_category="cancelled",
            failure_message="cancelled via farm.py cancel",
        )


async def _activity_timings(handle) -> dict[str, float]:
    """Queue and run time of the leaf's last ``build_leaf`` attempt, from history.

    Best-effort: a history that cannot be read (or a test double without one)
    yields nothing, never a failed leaf. Temporal records a retried activity's
    ``ActivityTaskStarted`` only when it finally closes, so ``temporal_queue_s``
    is exact for a first attempt and includes the earlier attempts otherwise.
    """
    from temporalio.api.enums.v1 import EventType

    scheduled = started = closed = None
    closing = {
        EventType.EVENT_TYPE_ACTIVITY_TASK_COMPLETED,
        EventType.EVENT_TYPE_ACTIVITY_TASK_FAILED,
        EventType.EVENT_TYPE_ACTIVITY_TASK_TIMED_OUT,
        EventType.EVENT_TYPE_ACTIVITY_TASK_CANCELED,
    }
    try:
        async for event in handle.fetch_history_events():
            if event.event_type == EventType.EVENT_TYPE_ACTIVITY_TASK_SCHEDULED:
                scheduled, started, closed = event.event_time.ToDatetime(), None, None
            elif event.event_type == EventType.EVENT_TYPE_ACTIVITY_TASK_STARTED:
                started = event.event_time.ToDatetime()
            elif event.event_type in closing:
                closed = event.event_time.ToDatetime()
    except Exception as exc:  # noqa: BLE001 -- diagnostics must not fail a leaf
        _telemetry.debug(f"farm history unreadable for timings: {exc!r}")
        return {}
    timings: dict[str, float] = {}
    if scheduled is not None and started is not None:
        timings["temporal_queue_s"] = (started - scheduled).total_seconds()
    if started is not None and closed is not None:
        timings["worker_run_s"] = (closed - started).total_seconds()
    return timings
