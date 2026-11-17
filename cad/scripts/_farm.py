"""Farm executor: dispatch one cache-missing doit leaf to the SolidWorks build farm.

The constants and frozen wire types below mirror
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

import _thread
import asyncio
import getpass
import hashlib
import json
import os
import socket
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from doit.reporter import ConsoleReporter

import _telemetry

FARM_PROTOCOL_VERSION = 7

TASK_QUEUE_CONTROL = "solidworks-control"  # coordinator and parked leaf workflows
TASK_QUEUE_COM = "solidworks-com"  # build_leaf activity tasks
WORKFLOW_BUILD_FIFO = "BuildFifo7"
WORKFLOW_BUILD_FIFO_ID = "solidworks-build-fifo-7"
ACTIVITY_BUILD_LEAF = "build_leaf"
NAMESPACE = "solidworks"

CONFIG_ENV = "SOLIDWORKS_POOL_CONFIG"
DEFAULT_CONFIG_PATH = Path.home() / ".solidworks-pool" / "config.json"
FIFO_HEARTBEAT_INTERVAL_S = 15
FIFO_PRODUCER_LEASE_S = 120
FIFO_RPC_TIMEOUT_S = 10
FIFO_RPC_RETRY_INTERVAL_S = 1
STATUS_POLL_INTERVAL_S = 1
# Consecutive read-outage budget only; this never acknowledges producer ownership.
FIFO_LEAF_STATUS_RETRY_S = 120
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
    build_id: str
    leaf_timeout_s: int | None = None  # per-attempt budget; None takes the default
    refresh_reason: str | None = None  # explicit overwrite for this leaf only


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
    # Milliseconds the leaf spent in each worker phase it reached (queue, admit,
    # seat_gate, acquire_source, source_restore, source_verify, execute,
    # publish_log), mirroring the pool contract; a phase never entered is absent.
    # Defaulted so a worker that predates the field still decodes.
    phase_ms: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class RegisterBuild:
    build_id: str
    submitter: str
    display_name: str


@dataclass(frozen=True)
class HeartbeatBuild:
    build_id: str
    sequence: int


@dataclass(frozen=True)
class CloseBuild:
    build_id: str
    reason: str


@dataclass(frozen=True)
class BuildStatus:
    build_id: str
    fifo_ordinal: int
    producer_state: str
    ownership_state: str
    lease_deadline: str
    outstanding_leaf_count: int
    unconfirmed_attempt_count: int
    reserved_capacity: int
    occupied_capacity: int


@dataclass(frozen=True)
class SubmitLeaf:
    request: LeafRequest
    farm_run: str | None


@dataclass(frozen=True)
class LeafKey:
    build_id: str
    workflow_id: str


@dataclass(frozen=True)
class LeafBinding:
    build_id: str
    workflow_id: str
    run_id: str


@dataclass(frozen=True)
class LeafAttempt:
    binding: LeafBinding
    activity_id: str
    attempt: int
    worker_id: str
    slot_id: str


@dataclass(frozen=True)
class LeafStatus:
    key: LeafKey
    state: str
    binding: LeafBinding | None
    unconfirmed_attempts: list[LeafAttempt]
    error_code: str | None = None
    error: str | None = None


def clamp_leaf_timeout_s(requested: int | None) -> int:
    """The budget the farm will actually grant, mirroring its own clamp.

    The control plane clamps whatever it is given; the submitter computes the
    same value so the workflow id it dedupes on matches the budget the leaf
    will really run under.
    """

    if requested is None:
        return LEAF_TIMEOUT_DEFAULT_S
    return max(LEAF_TIMEOUT_MIN_S, min(LEAF_TIMEOUT_MAX_S, requested))


def workflow_id(
    build_id: str, task: str, cache_key: str | None, commit: str, timeout_s: int
) -> str:
    return f"leaf:{build_id}:{task}:{cache_key or commit[:16]}:{timeout_s}s"


def leaf_action(function):
    """Mark a doit action that dispatches its task as a farm leaf on a miss."""
    function._farm_leaf_action = True
    return function


def enabled() -> bool:
    return os.environ.get("HARMONIC_EXECUTOR", "local") == "farm"


# Why a worker can build the leaf, exit 0 and still not publish the key this
# submitter waits on. The submitter builds from a private snapshot of the
# launch commit (farm_build.py), so the causes are the ways its keying
# environment differs from the worker's.
CACHE_MISSING_CAUSES = (
    "the worker built the launch commit but did not publish the key this "
    "submitter computed. Likely causes: HARMONIC_CACHE_SALT / "
    "HARMONIC_CACHE_ACCOUNT / HARMONIC_CACHE_CONTAINER differing from the "
    "workers', or a publish that failed on the worker (see its task.log). Compare "
    "this task's row in cad/out/reports/cache.jsonl with the worker's"
)


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


class BuildOwnershipError(RuntimeError):
    """The producer cannot prove it still owns admission to the build farm."""


def _build_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid4().hex


async def _connect_client(identity: str):
    # Keep Temporal's Rust bridge out of local builds and offline check workers.
    from temporalio.client import Client
    from temporalio.service import TLSConfig

    config = load_config()
    address = config["temporal_address"]
    return await Client.connect(
        address,
        namespace=config["namespace"],
        api_key=Path(config["token"]).read_text(encoding="ascii").strip(),
        tls=TLSConfig(
            server_root_ca_cert=Path(config["ca_cert"]).read_bytes(),
            domain=address.rsplit(":", 1)[0],
            client_cert=Path(config["client_cert"]).read_bytes(),
            client_private_key=Path(config["client_key"]).read_bytes(),
        ),
        identity=identity,
    )


async def _fifo_handle(client):
    from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

    await asyncio.wait_for(
        client.start_workflow(
            WORKFLOW_BUILD_FIFO,
            id=WORKFLOW_BUILD_FIFO_ID,
            task_queue=TASK_QUEUE_CONTROL,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        ),
        timeout=FIFO_RPC_TIMEOUT_S,
    )
    # Deliberately no coordinator run pin: continue-as-new preserves ownership.
    handle = client.get_workflow_handle(WORKFLOW_BUILD_FIFO_ID)
    description = await asyncio.wait_for(
        handle.describe(rpc_timeout=timedelta(seconds=FIFO_RPC_TIMEOUT_S)),
        timeout=FIFO_RPC_TIMEOUT_S,
    )
    if description.workflow_type != WORKFLOW_BUILD_FIFO:
        raise RuntimeError(
            f"farm coordinator {WORKFLOW_BUILD_FIFO_ID}: expected workflow type "
            f"{WORKFLOW_BUILD_FIFO!r}, found {description.workflow_type!r}; "
            "a coordinated producer/pool/worker cutover to an idle, physically "
            "drained fleet is required; do not invoke the legacy coordinator"
        )
    return handle


async def _rpc_update(handle, name: str, arg, result_type, operation: str):
    # Stable, bounded IDs make an uncertain RPC safe to reconcile or repeat.
    update_id = "fifo:" + hashlib.sha256(operation.encode("utf-8")).hexdigest()
    return await asyncio.wait_for(
        handle.execute_update(
            name,
            arg,
            id=update_id,
            result_type=result_type,
            rpc_timeout=timedelta(seconds=FIFO_RPC_TIMEOUT_S),
        ),
        timeout=FIFO_RPC_TIMEOUT_S,
    )


async def _rpc_query(handle, name: str, arg, result_type):
    return await asyncio.wait_for(
        handle.query(
            name,
            arg,
            result_type=result_type,
            rpc_timeout=timedelta(seconds=FIFO_RPC_TIMEOUT_S),
        ),
        timeout=FIFO_RPC_TIMEOUT_S,
    )


def _is_transient_fifo_error(exc: Exception) -> bool:
    from temporalio.client import WorkflowUpdateRPCTimeoutOrCancelledError
    from temporalio.service import RPCError, RPCStatusCode

    if isinstance(exc, RPCError):
        return exc.status in {
            RPCStatusCode.CANCELLED,
            RPCStatusCode.UNKNOWN,
            RPCStatusCode.DEADLINE_EXCEEDED,
            RPCStatusCode.RESOURCE_EXHAUSTED,
            RPCStatusCode.ABORTED,
            RPCStatusCode.INTERNAL,
            RPCStatusCode.UNAVAILABLE,
        }
    return isinstance(
        exc, (TimeoutError, ConnectionError, WorkflowUpdateRPCTimeoutOrCancelledError)
    )


async def _reserved_leaf_status(handle, key: LeafKey) -> LeafStatus:
    """Reconcile the same accepted reservation through a bounded read outage.

    Action workers have no acknowledged parent lease. This independent monotonic
    budget bounds only consecutive transient read failures, including an RPC in
    flight. A successful reserved reply may begin another read-outage budget.
    """
    deadline = time.monotonic() + FIFO_LEAF_STATUS_RETRY_S
    last_error = None
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"leaf reservation status unavailable for {FIFO_LEAF_STATUS_RETRY_S}s: "
                f"{key.workflow_id}; accepted work remains under the coordinator"
            ) from last_error
        try:
            return await asyncio.wait_for(
                _rpc_query(handle, "leaf_status", key, LeafStatus), timeout=remaining
            )
        except Exception as exc:
            if not _is_transient_fifo_error(exc):
                raise
            last_error = exc
            await asyncio.sleep(
                min(STATUS_POLL_INTERVAL_S, max(0, deadline - time.monotonic()))
            )


def producer_build(display_name: str):
    """Register the parent producer before scheduling or cache checks."""
    return _ProducerBuild(_display_name(display_name))


class _ProducerBuild:
    """One parent thread owns the client, renewal loop and normal close.

    Spawned doit workers inherit only the build ID, never the renewal thread.
    Lease-bounded transient retries keep the same registration and update ID.
    Lease loss stops local scheduling; capacity changes do not. Accepted
    reservations remain under the coordinator's grant and physical-drain fences.
    """

    def __init__(self, display_name: str):
        self.build_id = _build_id()
        self.display_name = display_name
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._failure: BaseException | None = None
        self._executing = False
        self._reason = "finished"
        self._previous_id: str | None = None
        self._lease_deadline: float | None = None
        self._lease_wall: datetime | None = None
        self._thread = threading.Thread(
            target=self._run, name="farm-build-lease", daemon=True
        )

    def __enter__(self):
        self._previous_id = os.environ.get("HARMONIC_FARM_BUILD_ID")
        os.environ["HARMONIC_FARM_BUILD_ID"] = self.build_id
        try:
            _record_build(self.build_id)
            self._thread.start()
            # Windows CPython 3.12/3.13 needs finite waits to deliver Ctrl-C.
            while not self._ready.wait(timeout=1):
                pass
            if self._failure is not None:
                raise BuildOwnershipError(
                    f"build {self.build_id} ownership failed: {self._failure}"
                ) from self._failure
            self._executing = True
            # A failure can race registration acknowledgement and task execution.
            self.check()
            return self
        except BaseException as exc:
            self._executing = False
            self._reason = "cancelled" if isinstance(exc, KeyboardInterrupt) else "failed"
            self._stop.set()
            if self._thread.ident is not None:
                self._thread.join()
            self._restore_env()
            raise

    def finish(self, success: bool) -> None:
        self._reason = "finished" if success else "failed"

    def check(self) -> None:
        if self._failure is not None:
            raise BuildOwnershipError(
                f"build {self.build_id} ownership lost: {self._failure}"
            ) from self._failure

    def __exit__(self, exc_type, exc, traceback):
        self._executing = False
        if exc is not None:
            self._reason = "cancelled" if isinstance(exc, KeyboardInterrupt) else "failed"
        if self._failure is not None:
            self._reason = "failed"
        self._stop.set()
        try:
            self._thread.join()
        finally:
            self._restore_env()
        if exc is None or isinstance(exc, KeyboardInterrupt):
            self.check()
        return False

    def _restore_env(self) -> None:
        if self._previous_id is None:
            os.environ.pop("HARMONIC_FARM_BUILD_ID", None)
        else:
            os.environ["HARMONIC_FARM_BUILD_ID"] = self._previous_id

    def _fail(self, exc: BaseException) -> None:
        if self._failure is None:
            self._failure = exc
            self._ready.set()
            if self._executing:
                # Doit's main thread may be waiting for spawned action workers.
                # Stop the parent, not their shared remote workflow executions.
                _thread.interrupt_main()

    def _run(self) -> None:
        try:
            asyncio.run(self._serve())
        except BaseException as exc:
            self._fail(exc)

    def _lease_remaining(self) -> float:
        if self._lease_deadline is None:
            raise BuildOwnershipError("producer has no acknowledged lease")
        remaining = self._lease_deadline - time.monotonic()
        if remaining <= 0:
            raise BuildOwnershipError("producer's acknowledged lease expired")
        return remaining

    def _accept_status(self, status: BuildStatus, *, renewed: bool = False) -> None:
        if self._lease_deadline is not None:
            self._lease_remaining()
        deadline = datetime.fromisoformat(status.lease_deadline.replace("Z", "+00:00"))
        if (
            status.build_id != self.build_id
            or status.producer_state != "open"
            or status.ownership_state not in {"waiting", "active"}
            or deadline.tzinfo is None
            or deadline <= datetime.now(timezone.utc)
        ):
            raise BuildOwnershipError(
                f"coordinator refused build {self.build_id}: "
                f"{status.producer_state}/{status.ownership_state}"
            )
        if self._lease_wall is None or (renewed and deadline > self._lease_wall):
            self._lease_wall = deadline
            self._lease_deadline = time.monotonic() + (
                deadline - datetime.now(timezone.utc)
            ).total_seconds()
        # Duplicate heartbeats never extend the acknowledged lease.
        self._lease_remaining()

    async def _leased_rpc(self, call, *args) -> BuildStatus | None:
        """Retry uncertain transport results, never a coordinator refusal.

        Every retry is bounded by the last acknowledged lease. The caller keeps
        the same heartbeat sequence and operation ID until it gets an answer.
        """
        while not self._stop.is_set():
            remaining = self._lease_remaining()
            try:
                return await asyncio.wait_for(call(*args), timeout=remaining)
            except Exception as exc:
                if not _is_transient_fifo_error(exc):
                    raise
                remaining = self._lease_remaining()
                if not self._stop.is_set():
                    self._stop.wait(min(FIFO_RPC_RETRY_INTERVAL_S, remaining))
        return None

    async def _serve(self) -> None:
        handle = None
        try:
            client = await asyncio.wait_for(
                _connect_client(submitter()), timeout=FIFO_RPC_TIMEOUT_S
            )
            handle = await _fifo_handle(client)
            status = await _rpc_update(
                handle,
                "register_build",
                RegisterBuild(self.build_id, submitter(), self.display_name),
                BuildStatus,
                f"register:{self.build_id}",
            )
            self._accept_status(status)
            _telemetry.info(
                f"Farm build registered: {self.build_id}",
                build_id=self.build_id,
                fifo_ordinal=status.fifo_ordinal,
                ownership_state=status.ownership_state,
            )
            heartbeat_due = time.monotonic() + FIFO_HEARTBEAT_INTERVAL_S
            # The renewer owns a valid lease before scheduler/cache work starts.
            # Ready native leaves park at the coordinator until a slot is granted.
            self._ready.set()
            sequence = 0
            while not self._stop.is_set():
                self._lease_remaining()
                if time.monotonic() >= heartbeat_due:
                    sequence += 1
                    status = await self._leased_rpc(
                        _rpc_update,
                        handle,
                        "heartbeat_build",
                        HeartbeatBuild(self.build_id, sequence),
                        BuildStatus,
                        f"heartbeat:{self.build_id}:{sequence}",
                    )
                    if status is None:
                        break
                    self._accept_status(status, renewed=True)
                    heartbeat_due = time.monotonic() + FIFO_HEARTBEAT_INTERVAL_S
                # This loop owns its dedicated thread. Wait for the next
                # renewal (or lease expiry), waking immediately on producer close.
                self._stop.wait(
                    min(
                        max(0, heartbeat_due - time.monotonic()),
                        self._lease_remaining(),
                    )
                )
        except BaseException as exc:
            self._reason = "failed"
            self._fail(exc)
        finally:
            if handle is not None:
                try:
                    await _rpc_update(
                        handle,
                        "close_build",
                        CloseBuild(self.build_id, self._reason),
                        BuildStatus,
                        f"close:{self.build_id}:{self._reason}",
                    )
                except Exception as exc:
                    # No new local work remains. Server lease expiry fences an
                    # unacknowledged close; it cannot change the command result
                    # or erase any ownership failure already recorded above.
                    _telemetry.warn(
                        f"Farm build close unacknowledged: {self.build_id}: {exc}; "
                        "the producer lease will expire",
                        build_id=self.build_id,
                    )


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


def run_leaf(task: str, cache_key: str | None) -> LeafResult:
    """Run ``task`` on the farm and return its result once the workflow closes.

    Duplicate submissions within this build attach to its exact coordinator
    binding. Other builds have distinct workflow IDs even for identical keys.
    Ctrl-C propagates without cancelling accepted work. A workflow cancelled
    through ``farm.py cancel`` returns a failed result with
    ``failure_category="cancelled"``; every other failure
    (connection, protocol) propagates as-is: it is a local fault, not a build
    outcome.
    Admission is the parent's successful full preflight label set, inherited by
    action workers through ``HARMONIC_FARM_ADMITTED_LEAVES``. Refuse locally
    before constructing a request or touching telemetry or farm identity.
    """
    raw_admission = os.environ.get("HARMONIC_FARM_ADMITTED_LEAVES")
    try:
        admitted = json.loads(raw_admission) if raw_admission is not None else None
    except (ValueError, RecursionError):
        admitted = None
    if (
        not isinstance(admitted, list)
        or any(not isinstance(label, str) or not label.strip() for label in admitted)
        or task not in admitted
    ):
        raise RuntimeError(
            f"farm leaf {task!r} lacks preflight admission: "
            "HARMONIC_FARM_ADMITTED_LEAVES must be a JSON list of non-empty "
            "labels containing this task"
        )
    from _artifact_cache import forced_refresh

    refresh_reason = forced_refresh(task)
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
            build_id=_required_build_id(),
            leaf_timeout_s=leaf_timeout_s(),
            refresh_reason=refresh_reason,
        )
        budget = clamp_leaf_timeout_s(request.leaf_timeout_s)
        wf_id = workflow_id(request.build_id, task, cache_key, request.commit, budget)
        sp.set_attribute("workflow_id", wf_id)
        sp.set_attribute("leaf_timeout_s", budget)
        result = asyncio.run(_dispatch(request, wf_id))
        sp.set_attribute("worker", result.worker_id)
        sp.set_attribute("attempt", result.attempt)
        sp.set_attribute("state", result.state)
        # The worker's own phase split, so a slow leaf's farm.run span says whether
        # it waited (queue/seat_gate), fetched (acquire_source) or built (execute)
        # without joining the pool's log by time window.
        for phase, ms in result.phase_ms.items():
            sp.set_attribute(f"phase.{phase}_ms", ms)
        return result


def _record_json(relative: str, value: object) -> None:
    """Atomically write one record of the farm run in ``HARMONIC_FARM_RUN_DIR``.

    ``farm_build.py`` reads these records for status, watch and cancel; one
    file per writer keeps parallel action processes independent.
    """
    directory = os.environ.get("HARMONIC_FARM_RUN_DIR")
    if not directory:
        return
    run_dir = Path(directory)
    path = run_dir / relative
    if path.parent != run_dir:
        path.parent.mkdir(exist_ok=True)  # never the run directory itself
    staging = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    staging.write_text(json.dumps(value), encoding="utf-8")
    os.replace(staging, path)


def _record_build(build_id: str) -> None:
    # Before registration: even an accepted RPC whose response is lost is named.
    _record_json(
        "build.json",
        {"build_id": build_id, "farm_run": os.environ.get("HARMONIC_FARM_RUN")},
    )


def _required_build_id() -> str:
    build_id = os.environ.get("HARMONIC_FARM_BUILD_ID")
    if not build_id:
        raise BuildOwnershipError("farm task has no parent build ownership")
    return build_id


def _record_leaf(record: dict, *, best_effort: bool = False) -> None:
    """Record a leaf's lifecycle state: ``requested`` before submission, then
    ``bound`` (with the exact run) and finally the worker's result.

    The ``requested`` write must succeed: an unnamed reservation could outlive
    an explicit cancel. Later writes are best-effort, because by then the
    coordinator holds the accepted work and the record already names it.
    """
    name = hashlib.sha256(record["workflow_id"].encode("utf-8")).hexdigest()[:32]
    try:
        _record_json(f"leaves/{name}.json", record)
    except OSError as exc:
        if not best_effort:
            raise
        _telemetry.warn(f"farm leaf record not updated: {record['workflow_id']}: {exc}")


class FarmReporter(ConsoleReporter):
    """doit's console reporter, also recording each failed task for the run."""

    def add_failure(self, task, fail):
        super().add_failure(task, fail)
        lines = [line for line in fail.get_msg().splitlines() if line.strip()]
        self._errors = [*getattr(self, "_errors", []), {
            "task": task.name, "error": lines[-1][:500] if lines else "",
        }]
        _record_json("task-errors.json", self._errors)


def _display_name(label: str | None = None) -> str:
    """Validate human metadata before any farm side effect; preserve its text."""
    if label is None:
        label = os.environ.get("HARMONIC_FARM_DISPLAY_NAME")
    if (
        label is None
        or not label.strip()
        or len(label) > 160
        or any(
            unicodedata.category(char) in {"Cc", "Zl", "Zp"}
            or char in "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
            for char in label
        )
    ):
        raise RuntimeError(
            "--display-name / HARMONIC_FARM_DISPLAY_NAME must be nonblank, "
            "single-line, free of control characters, and at most 160 characters"
        )
    try:
        label.encode("utf-8")
    except UnicodeEncodeError:
        raise RuntimeError(
            "--display-name / HARMONIC_FARM_DISPLAY_NAME must contain valid Unicode"
        ) from None
    return label


async def _dispatch(request: LeafRequest, wf_id: str) -> LeafResult:
    _display_name()
    if request.build_id != _required_build_id():
        raise BuildOwnershipError("leaf build ID does not match parent ownership")
    from temporalio.client import WorkflowFailureError
    from temporalio.exceptions import CancelledError

    client = await asyncio.wait_for(
        _connect_client(request.submitter), timeout=FIFO_RPC_TIMEOUT_S
    )
    coordinator = await _fifo_handle(client)
    identity = {
        "workflow_id": wf_id,
        "task": request.task,
        "commit": request.commit,
        "build_id": request.build_id,
    }
    _telemetry.info(f"Farm workflow requested: {wf_id}", **identity)
    record = {
        "task": request.task,
        "workflow_id": wf_id,
        "build_id": request.build_id,
        "farm_run": os.environ.get("HARMONIC_FARM_RUN"),
        "refresh_reason": request.refresh_reason,
        "state": "requested",
    }
    _record_leaf(record)
    # Only the coordinator can reserve and start a leaf. Creator metadata stays
    # on the run it starts; attaching to a canonical ID never rewrites the memo.
    key = LeafKey(request.build_id, wf_id)
    status = await _rpc_update(
        coordinator,
        "submit_leaf",
        SubmitLeaf(request, os.environ.get("HARMONIC_FARM_RUN")),
        LeafStatus,
        f"submit:{request.build_id}:{wf_id}",
    )
    while True:
        if status.key != key:
            raise BuildOwnershipError("coordinator returned a foreign leaf reservation")
        if status.error_code or status.state == "recovery_required":
            raise BuildOwnershipError(
                f"leaf reservation requires operator recovery "
                f"[{status.error_code or 'recovery_required'}]: "
                f"{status.error or wf_id}"
            )
        if status.state not in {
            "reserved", "bound", "admitted", "terminal", "drained", "missing_closed"
        }:
            raise BuildOwnershipError("coordinator returned an invalid leaf reservation state")
        binding = status.binding
        if binding is not None:
            if (
                binding.build_id != request.build_id
                or binding.workflow_id != wf_id
                or not binding.run_id
            ):
                raise BuildOwnershipError("coordinator returned a foreign leaf binding")
            break
        if status.state != "reserved":
            raise BuildOwnershipError("accepted leaf closed without a proven run binding")
        await asyncio.sleep(STATUS_POLL_INTERVAL_S)
        status = await _reserved_leaf_status(coordinator, key)
    handle = client.get_workflow_handle(
        wf_id, run_id=binding.run_id, result_type=LeafResult
    )
    _telemetry.info(f"Farm workflow attached: {wf_id}", **identity)
    _telemetry.event("farm.attached", **identity)
    record.update(state="bound", run_id=binding.run_id)
    _record_leaf(record, best_effort=True)
    try:
        result = await handle.result(follow_runs=False)
    except WorkflowFailureError as exc:
        if not isinstance(exc.cause, CancelledError):
            raise
        result = LeafResult(
            state="failed",
            exit_code=None,
            worker_id="",
            attempt=0,
            cache_present=False,
            log_blob=None,
            failure_category="cancelled",
            failure_message="cancelled via farm.py cancel",
        )
    record.update(
        state=result.state,
        worker_id=result.worker_id,
        attempt=result.attempt,
        exit_code=result.exit_code,
        failure_category=result.failure_category,
        failure_message=result.failure_message,
        log_blob=result.log_blob,
    )
    _record_leaf(record, best_effort=True)
    return result
