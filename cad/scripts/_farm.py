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
import subprocess
import threading
import time
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

import _telemetry

REPO_ROOT = Path(__file__).resolve().parents[2]

FARM_PROTOCOL_VERSION = 5

TASK_QUEUE_CONTROL = "solidworks-control"  # coordinator and BuildLeaf workflows
TASK_QUEUE_COM = "solidworks-com"  # build_leaf activity tasks
WORKFLOW_BUILD_LEAF = "BuildLeaf"
WORKFLOW_BUILD_FIFO = "BuildFifo"
WORKFLOW_BUILD_FIFO_ID = "solidworks-build-fifo"
ACTIVITY_BUILD_LEAF = "build_leaf"
NAMESPACE = "solidworks"

CONFIG_ENV = "SOLIDWORKS_POOL_CONFIG"
DEFAULT_CONFIG_PATH = Path.home() / ".solidworks-pool" / "config.json"
FIFO_HEARTBEAT_INTERVAL_S = 15
FIFO_PRODUCER_LEASE_S = 120
FIFO_RPC_TIMEOUT_S = 10
STATUS_POLL_INTERVAL_S = 1
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
class BuildKey:
    build_id: str


@dataclass(frozen=True)
class BuildStatus:
    build_id: str
    fifo_ordinal: int
    producer_state: str
    ownership_state: str
    lease_deadline: str
    outstanding_leaf_count: int
    unconfirmed_attempt_count: int


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


@dataclass(frozen=True)
class AttemptAdmission:
    state: Literal["admitted", "drained", "denied"]
    reason: str | None


@dataclass(frozen=True)
class LeafStatus:
    key: LeafKey
    state: str
    binding: LeafBinding | None
    unconfirmed_attempts: list[LeafAttempt]
    error_code: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class ConfirmAttemptDrained:
    attempt: LeafAttempt
    evidence: str


@dataclass(frozen=True)
class ConfirmReservationDrained:
    key: LeafKey
    evidence: str
    run_id: str | None = None


@dataclass(frozen=True)
class FifoStatus:
    active: BuildStatus | None
    waiting: list[BuildStatus]
    draining: list[BuildStatus]
    capacity_error: str | None = None


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


# A drift report names at most this many paths; a checkout moved to another
# branch can differ in thousands, and the first few already say what happened.
_DRIFT_PATHS_SHOWN = 10

# Why a worker can build the leaf, exit 0 and still not publish the key this
# submitter waits on, once checkout drift has been ruled out. The worker keys
# the task from the launch commit; the submitter keyed it from this checkout
# and this process's environment, so the causes are the ways those differ.
CACHE_MISSING_CAUSES = (
    "the worker built the launch commit but did not publish the key this "
    "submitter computed. Likely causes: an input this checkout keyed differently "
    "from the commit (an artefact left by a local COM build whose .execution "
    "token no worker can reproduce -- e.g. a HARMONIC_REMOTE_CACHE_MODE=ro local "
    "build; `doit forget` the task and its dependents so they re-probe -- or a "
    "checkout edit that was reverted before this check), HARMONIC_CACHE_SALT / "
    "HARMONIC_CACHE_ACCOUNT / HARMONIC_CACHE_CONTAINER differing from the "
    "workers', or a publish that failed on the worker (see its task.log). Compare "
    "this task's row in cad/out/reports/cache.jsonl with the worker's"
)

# Tracked paths outside cad/ that can still move a key or the graph itself:
# the graph and its runner, the environment every recipe runs in, and what
# decides which submodules a worker checks out.
_KEY_AFFECTING_FILES = frozenset(
    {
        "dodo.py",
        "build.py",
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        ".farm-sources.json",
        ".gitmodules",
    }
)
_GITLINK_MODE = "160000"


def _can_move_a_key(path: str, gitlink: bool, task_inputs: frozenset[str]) -> bool:
    """Whether a changed tracked ``path`` can change some cache key or the graph.

    Conservative by construction -- refusing a harmless edit costs a relaunch,
    missing a real re-key costs the build. Every recipe input lives under
    ``cad/`` (scripts, config, templates, references), a key folds its
    dependencies' recipes transitively (a drawing keys its part's whole recipe
    through the ``.SLDPRT`` dep), and a ``.gitattributes`` rewrites checked-out
    bytes; so all of those count for every task, alongside the task's own
    recorded key inputs and any submodule.
    """
    return (
        gitlink
        or path.startswith("cad/")
        or path in _KEY_AFFECTING_FILES
        or path.rsplit("/", 1)[-1] == ".gitattributes"
        or path in task_inputs
    )


def checkout_drift(
    repo: Path = REPO_ROOT,
    commit: str | None = None,
    task_inputs: Iterable[str] | None = None,
) -> str | None:
    """Why this checkout no longer matches the launch commit, or ``None``.

    The submitter keys each task from the live files when it reaches the task,
    while every worker builds ``HARMONIC_FARM_COMMIT``. The farm preflight
    refused a dirty tree, so at launch the checkout WAS that commit's tree, and
    the commit's tree -- tracked files plus submodule gitlinks -- is the launch
    fingerprint. ``git diff <commit>`` compares the working tree (and the
    checked-out submodules, dirty ones included) against it without writing the
    index, so concurrent doit workers can run it side by side. A HEAD that moved
    to an identical tree is no drift: every key is unchanged.

    With ``task_inputs`` (the repo-relative paths a task's key was computed
    from) only a change that can move a key counts -- see ``_can_move_a_key``
    -- so a README edit mid-run does not stop a valid dispatch. Without it,
    any tracked difference counts: that is the explanation after a key has
    already gone missing, where every difference is a lead.
    """
    launched = commit or os.environ["HARMONIC_FARM_COMMIT"]
    raw = _git(
        repo,
        "diff",
        "--raw",
        "-z",
        "--no-renames",
        "--ignore-submodules=none",
        launched,
        "--",
    ).split("\0")
    # -z --raw: ":<old mode> <new mode> <old sha> <new sha> <status>", then the path.
    changed = [
        (path, _GITLINK_MODE in status.split()[:2])
        for status, path in zip(raw[0::2], raw[1::2])
        if status.startswith(":")
    ]
    if task_inputs is not None:
        inputs = frozenset(task_inputs)
        changed = [c for c in changed if _can_move_a_key(*c, inputs)]
    if not changed:
        return None
    paths = [path for path, _ in changed]
    head = _git(repo, "rev-parse", "HEAD").strip()
    moved = (
        f"HEAD {launched[:12]} (unchanged)"
        if head == launched
        else f"HEAD {launched[:12]} -> {head[:12]}"
    )
    shown = ", ".join(paths[:_DRIFT_PATHS_SHOWN])
    if len(paths) > _DRIFT_PATHS_SHOWN:
        shown += f" and {len(paths) - _DRIFT_PATHS_SHOWN} more"
    return (
        f"submitter checkout changed since launch: {moved}; changed: {shown}; "
        f"the farm builds {launched[:12]}, so keys would not match. Launch from "
        "an untouched worktree (scripts/farm-run.ps1 does this)."
    )


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if done.returncode != 0:
        raise RuntimeError(
            f"checkout drift check: git {' '.join(args)} failed "
            f"(exit {done.returncode}): {done.stderr.strip()}"
        )
    return done.stdout


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
    return client.get_workflow_handle(WORKFLOW_BUILD_FIFO_ID)


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


def producer_build(display_name: str):
    """The parent-only ownership seam, entered only after valid preflight."""
    return _ProducerBuild(_display_name(display_name))


class _ProducerBuild:
    """One parent thread owns the client, renewal loop and normal close.

    Spawned doit workers inherit only the build ID, never the renewal thread.
    Lease-bounded transient retries keep the same registration and update ID.
    Ownership loss stops local scheduling; accepted reservations still drain
    under the coordinator rather than being cancelled by this context.
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
            self._ready.wait()
            if self._failure is not None:
                raise BuildOwnershipError(
                    f"build {self.build_id} ownership failed: {self._failure}"
                ) from self._failure
            self._executing = True
            # A failure can race the transition from waiting to task execution.
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

    def _accept_status(
        self, status: BuildStatus, *, active: bool, renewed: bool = False
    ) -> bool:
        if self._lease_deadline is not None:
            self._lease_remaining()
        deadline = datetime.fromisoformat(status.lease_deadline.replace("Z", "+00:00"))
        if (
            status.build_id != self.build_id
            or status.producer_state != "open"
            or status.ownership_state not in {"waiting", "active"}
            or (active and status.ownership_state != "active")
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
        # Polls and duplicate heartbeats never extend the acknowledged lease.
        self._lease_remaining()
        return status.ownership_state == "active"

    async def _leased_rpc(self, call, *args) -> BuildStatus | None:
        """Retry uncertain transport results, never a coordinator refusal.

        Every retry is bounded by the last acknowledged lease. The caller keeps
        the same heartbeat sequence and operation ID until it gets an answer.
        """
        from temporalio.client import WorkflowUpdateRPCTimeoutOrCancelledError
        from temporalio.service import RPCError, RPCStatusCode

        while not self._stop.is_set():
            remaining = self._lease_remaining()
            try:
                return await asyncio.wait_for(call(*args), timeout=remaining)
            except (
                TimeoutError,
                ConnectionError,
                WorkflowUpdateRPCTimeoutOrCancelledError,
                RPCError,
            ) as exc:
                if isinstance(exc, RPCError) and exc.status not in {
                    RPCStatusCode.CANCELLED,
                    RPCStatusCode.UNKNOWN,
                    RPCStatusCode.DEADLINE_EXCEEDED,
                    RPCStatusCode.RESOURCE_EXHAUSTED,
                    RPCStatusCode.ABORTED,
                    RPCStatusCode.INTERNAL,
                    RPCStatusCode.UNAVAILABLE,
                }:
                    raise
                remaining = self._lease_remaining()
                if not self._stop.is_set():
                    await asyncio.sleep(min(STATUS_POLL_INTERVAL_S, remaining))
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
            active = self._accept_status(status, active=False)
            _telemetry.info(
                f"Farm build registered: {self.build_id}",
                build_id=self.build_id,
                fifo_ordinal=status.fifo_ordinal,
                ownership_state=status.ownership_state,
            )
            heartbeat_due = time.monotonic() + FIFO_HEARTBEAT_INTERVAL_S
            sequence = 0
            while not self._stop.is_set():
                self._lease_remaining()
                if active:
                    self._ready.set()
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
                    active = self._accept_status(status, active=active, renewed=True)
                    heartbeat_due = time.monotonic() + FIFO_HEARTBEAT_INTERVAL_S
                elif not active:
                    status = await self._leased_rpc(
                        _rpc_query,
                        handle,
                        "build_status",
                        BuildKey(self.build_id),
                        BuildStatus,
                    )
                    if status is None:
                        break
                    active = self._accept_status(status, active=False)
                await asyncio.sleep(
                    min(STATUS_POLL_INTERVAL_S, self._lease_remaining())
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

    Shares the workflow with any other submitter of the same leaf
    (``USE_EXISTING``), so Ctrl-C here never cancels it -- the interrupt just
    propagates. A workflow cancelled through ``farm.py cancel`` comes back as a
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
            build_id=_required_build_id(),
            leaf_timeout_s=leaf_timeout_s(),
        )
        budget = clamp_leaf_timeout_s(request.leaf_timeout_s)
        wf_id = workflow_id(task, cache_key, request.commit, budget)
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


def _record_json(name: str, value: dict) -> None:
    directory = os.environ.get("HARMONIC_FARM_REQUESTS")
    if not directory:
        return
    path = Path(directory) / f"{name}.json"
    staging = path.with_name(f"{name}.{os.getpid()}.tmp")
    staging.write_text(json.dumps(value), encoding="utf-8")
    os.replace(staging, path)


def _record_build(build_id: str) -> None:
    # Before registration: even an accepted RPC whose response is lost is named.
    _record_json(
        "build", {"build_id": build_id, "farm_run": os.environ.get("HARMONIC_FARM_RUN")}
    )


def _required_build_id() -> str:
    build_id = os.environ.get("HARMONIC_FARM_BUILD_ID")
    if not build_id:
        raise BuildOwnershipError("farm task has no parent build ownership")
    return build_id


def _record_request(task: str, wf_id: str) -> None:
    """Name a reservation before acceptance, even if launcher output is lost.

    One atomic file per canonical workflow keeps parallel action processes
    independent. A failed write fails dispatch: an unnamed reservation could
    otherwise outlive explicit launcher cancellation.
    """
    name = hashlib.sha256(wf_id.encode("utf-8")).hexdigest()[:32]
    _record_json(
        name,
        {
            "task": task,
            "workflow_id": wf_id,
            "build_id": _required_build_id(),
            "farm_run": os.environ.get("HARMONIC_FARM_RUN"),
        },
    )


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
    _record_request(request.task, wf_id)
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
        status = await _rpc_query(coordinator, "leaf_status", key, LeafStatus)
    handle = client.get_workflow_handle(
        wf_id, run_id=binding.run_id, result_type=LeafResult
    )
    _telemetry.info(f"Farm workflow attached: {wf_id}", **identity)
    _telemetry.event("farm.attached", **identity)
    try:
        return await handle.result(follow_runs=False)
    except WorkflowFailureError as exc:
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
