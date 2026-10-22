"""Farm executor: dispatch one cache-missing doit leaf to the SolidWorks build farm.

The constants and frozen wire types below mirror
``solidworks-pool/agent/contract.py`` field-for-field; ``FARM_PROTOCOL_VERSION``
mirrors ``agent/protocol.py`` and guards drift between the two repos (a mismatch
fails admission on the farm). This module must never import the pool package.
Preparation publication uses the build wrapper's owned private-body bridge only
when a cache-missing leaf is about to submit; local/cache-only work never loads
the pool runtime or exports a graph.

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
import math
import os
import re
import socket
import stat
import subprocess
import tempfile
import threading
import time
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import _telemetry

REPO_ROOT = Path(__file__).resolve().parents[2]

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
        self._previous_requests: str | None = None
        self._owned_requests: tempfile.TemporaryDirectory[str] | None = None
        self._lease_deadline: float | None = None
        self._lease_wall: datetime | None = None
        self._thread = threading.Thread(
            target=self._run, name="farm-build-lease", daemon=True
        )

    def __enter__(self):
        self._previous_id = os.environ.get("HARMONIC_FARM_BUILD_ID")
        os.environ["HARMONIC_FARM_BUILD_ID"] = self.build_id
        try:
            self._previous_requests = os.environ.get("HARMONIC_FARM_REQUESTS")
            if not self._previous_requests:
                # Cleanup is explicit: uncertain publisher termination must
                # retain its receipts instead of a GC finalizer deleting them.
                self._owned_requests = tempfile.TemporaryDirectory(
                    prefix="harmonic-farm-requests-", delete=False,
                )
                os.environ["HARMONIC_FARM_REQUESTS"] = self._owned_requests.name
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
            self._restore_env(primary_error=exc)
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
            if exc is None or isinstance(exc, KeyboardInterrupt):
                self.check()
        except BaseException as lifecycle_error:
            self._restore_env(primary_error=lifecycle_error)
            raise
        else:
            self._restore_env(primary_error=exc)
        return False

    def _restore_env(self, *, primary_error: BaseException | None = None) -> None:
        if self._previous_id is None:
            os.environ.pop("HARMONIC_FARM_BUILD_ID", None)
        else:
            os.environ["HARMONIC_FARM_BUILD_ID"] = self._previous_id
        owned = self._owned_requests
        if owned is None:
            return
        if self._previous_requests is None:
            os.environ.pop("HARMONIC_FARM_REQUESTS", None)
        else:
            os.environ["HARMONIC_FARM_REQUESTS"] = self._previous_requests
        if primary_error is not None:
            # Doit terminates process workers without joining on exceptions,
            # and thread workers may continue. Even an empty/free receipt scan
            # cannot close the race before a worker's first publishing marker.
            message = (
                "Farm requests retained after a primary build exception or interrupt; "
                f"publisher cleanup cannot be inferred; owned directory: {owned.name}"
            )
        else:
            try:
                _require_quiescent_requests(Path(owned.name), self.build_id)
            except Exception as evidence_error:
                message = (
                    "Farm requests retained because owned preparation evidence "
                    f"is not quiescent ({type(evidence_error).__name__}); "
                    f"owned directory: {owned.name}"
                )
            else:
                try:
                    owned.cleanup()
                except Exception as cleanup_error:
                    message = (
                        "Farm requests cleanup could not be confirmed; possible residue "
                        f"at {owned.name} ({type(cleanup_error).__name__})"
                    )
                else:
                    self._owned_requests = None
                    return
        if primary_error is not None:
            primary_error.add_note(message)
        try:
            _telemetry.warn(message, build_id=self.build_id)
        except Exception:
            # A secondary diagnostic must not replace the primary build fault.
            pass
        if primary_error is None and self._reason == "finished":
            raise BuildOwnershipError(message) from None

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


def _atomic_json(path: Path, value: dict) -> None:
    staging = path.with_name(f"{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    try:
        staging.write_text(json.dumps(value), encoding="utf-8")
        os.replace(staging, path)
    finally:
        staging.unlink(missing_ok=True)


def _record_json(name: str, value: dict) -> None:
    directory = os.environ.get("HARMONIC_FARM_REQUESTS")
    if not directory:
        return
    _atomic_json(Path(directory) / f"{name}.json", value)


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


def _record_request(task: str, wf_id: str, refresh_reason: str | None = None) -> None:
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
            "refresh_reason": refresh_reason,
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


_PREPARATION_CAPABILITY = "preparation-publish-v1"


def _preparation_identity_digest(identity: dict[str, str]) -> str:
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _read_preparation_receipt(
    path: Path, *, build_id: str, identity: dict[str, str] | None = None,
) -> dict:
    """Use the same receipt schema and filename identity for owner and teardown."""
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, RecursionError) as exc:
        raise RuntimeError(
            f"farm preparation publication receipt is corrupt: {path}"
        ) from exc
    recorded_identity = receipt.get("identity") if isinstance(receipt, dict) else None
    if (
        not isinstance(recorded_identity, dict)
        or set(recorded_identity) != {
            "build_id", "workspace", "pool_home", "commit", "agent_identity_sha256",
        }
        or not all(isinstance(value, str) for value in recorded_identity.values())
        or recorded_identity["build_id"] != build_id
        or (identity is not None and recorded_identity != identity)
        or path.stem != _preparation_identity_digest(recorded_identity)
        or receipt.get("state") not in ("publishing", "succeeded", "failed")
        or (
            receipt["state"] == "failed"
            and (not isinstance(receipt.get("error"), str) or not receipt["error"])
        )
    ):
        raise RuntimeError(f"farm preparation publication receipt is invalid: {path}")
    return receipt


def _requests_entry_mode(path: Path) -> int:
    entry = path.lstat()
    if (
        stat.S_ISLNK(entry.st_mode)
        or getattr(entry, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise RuntimeError(f"farm requests evidence is an alias: {path}")
    return entry.st_mode


def _require_quiescent_requests(root: Path, build_id: str) -> None:
    """Inspect only our root after normal worker completion, never on an error.

    I1: every preparation receipt/staging write holds its digest lock.
    I2: publishing is atomic before any launch, so a free lock without JSON is safe.
    I3: succeeded/failed are absorbing; a free terminal receipt cannot relaunch.
    These prove normal-return cleanup only, not exception-time worker quiescence.
    """
    from filelock import FileLock

    if not stat.S_ISDIR(_requests_entry_mode(root)):
        raise RuntimeError(f"farm requests root is not a directory: {root}")
    preparation = root / "preparation"
    try:
        mode = _requests_entry_mode(preparation)
    except FileNotFoundError:
        return
    if not stat.S_ISDIR(mode):
        raise RuntimeError(f"farm preparation root is not a directory: {preparation}")
    digests, receipts, staging = set(), set(), set()
    for entry in preparation.iterdir():
        if not stat.S_ISREG(_requests_entry_mode(entry)):
            raise RuntimeError(f"farm preparation contains non-file evidence: {entry}")
        match = re.fullmatch(r"([0-9a-f]{64})\.(json|lock)", entry.name)
        if match is not None:
            digest, kind = match.groups()
            digests.add(digest)
            if kind == "json":
                receipts.add(digest)
        else:
            match = re.fullmatch(
                r"([0-9a-f]{64})\.json\.[0-9]+\.[0-9a-f]{32}\.tmp", entry.name,
            )
            if match is None:
                raise RuntimeError(f"farm preparation contains unknown evidence: {entry}")
            staging.add(match.group(1))
    if staging - digests:
        raise RuntimeError("farm preparation contains staging without a receipt or lock")
    for digest in sorted(digests):
        # Probe before reading. Windows filelock may unlink its file on release;
        # only snapshot JSON/lock digests are probed, never staging-only digests.
        lock = FileLock(str(preparation / f"{digest}.lock"))
        with lock.acquire(timeout=0):
            path = preparation / f"{digest}.json"
            try:
                if not stat.S_ISREG(_requests_entry_mode(path)):
                    raise RuntimeError(f"farm preparation receipt is not a file: {path}")
                receipt = _read_preparation_receipt(path, build_id=build_id)
            except FileNotFoundError:
                if digest in receipts:
                    raise
                continue
            if receipt["state"] == "publishing":
                raise RuntimeError(f"farm preparation publication is still publishing: {path}")


def _require_preparation_readiness() -> tuple[float, float]:
    """Refuse an unavailable publisher only when a real remote leaf is needed."""
    from build import _pool_home

    pool = _pool_home().resolve()
    try:
        readiness = json.loads(
            os.environ.get("HARMONIC_FARM_PREPARATION_READINESS", "null")
        )
    except (ValueError, RecursionError):
        readiness = None
    if isinstance(readiness, dict) and readiness.get("probe_error") is not None:
        raise RuntimeError(
            f"PoolHome {pool} preparation publisher readiness probe failed; "
            "repair the selected pool environment before remote dispatch"
        )
    if (
        not isinstance(readiness, dict)
        or readiness.get("capability") != _PREPARATION_CAPABILITY
    ):
        raise RuntimeError(
            f"PoolHome {pool} requires an updated pool revision supporting "
            "`preparation publish` and publisher readiness before remote dispatch"
        )
    if (
        not isinstance(readiness.get("configured"), bool)
        or not isinstance(readiness.get("configuration_error"), bool)
    ):
        raise RuntimeError(f"PoolHome {pool} returned invalid publisher readiness")
    if readiness["configuration_error"]:
        raise RuntimeError(
            f"PoolHome {pool} has invalid preparation publisher configuration; "
            "fix FARM_BOOTSTRAP_ACCOUNT or the pool configuration before remote dispatch"
        )
    if not readiness["configured"]:
        raise RuntimeError(
            f"PoolHome {pool} preparation publisher is not configured; set "
            "FARM_BOOTSTRAP_ACCOUNT or bootstrap_account in the pool configuration "
            "before remote dispatch"
        )
    if not isinstance(readiness.get("account"), str) or not readiness["account"].strip():
        raise RuntimeError(f"PoolHome {pool} returned invalid publisher account readiness")
    budgets = []
    for name in ("operation_timeout_s", "process_margin_s"):
        value = readiness.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError(f"PoolHome {pool} returned invalid publisher {name} readiness")
        try:
            budget = float(value)
        except OverflowError:
            raise RuntimeError(
                f"PoolHome {pool} returned invalid publisher {name} readiness"
            ) from None
        if not math.isfinite(budget) or budget <= 0:
            raise RuntimeError(f"PoolHome {pool} returned invalid publisher {name} readiness")
        budgets.append(budget)
    return budgets[0], budgets[1]


def _publish_preparation(
    pool: Path, workspace: Path, commit: str, agent_identity: str, *,
    operation_deadline: float, process_margin_s: float, clock: Callable[[], float],
) -> None:
    # The existing owned ProcessTree is the sole supervisor. Its selected-pool
    # private body shares this operation's original deadline, not a fresh budget.
    from build import _pool_preparation

    published = _pool_preparation(
        pool, workspace, commit=commit, operation_deadline=operation_deadline,
        process_margin_s=process_margin_s, clock=clock,
    )
    if (
        not isinstance(published, dict)
        or published.get("configured") is not True
        or published.get("commit") != commit
        or published.get("agent_identity_sha256") != agent_identity
    ):
        raise RuntimeError(
            "farm preparation publication does not match the admitted "
            "source and pool agent identity"
        )


def _ensure_preparation_published(request: LeafRequest) -> None:
    """Publish once across this build's action processes, or share its failure.

    The parent's existing requests directory owns these receipts and their OS
    locks. A holder interrupted after starting publication leaves a marker that
    fails closed; a later process must not launch a second publisher.
    """
    from build import (
        PoolProcessCleanupError, _pool_home, _pool_publication_clock,
        _raise_if_pool_publication_cancelled,
    )

    operation_timeout_s, process_margin_s = _require_preparation_readiness()
    pool = _pool_home().resolve()
    # This exact selected protocol counter is shared with the private child.
    # Its perf_counter domain (raw QPC on supported Windows CPython) is not the
    # unrelated duration-only monotonic domain used by FIFO/lease operations.
    clock = _pool_publication_clock(pool)
    started = clock()
    operation_deadline = started + operation_timeout_s
    observation_deadline = operation_deadline + process_margin_s

    commit = request.commit
    agent_identity = os.environ.get("HARMONIC_FARM_AGENT_IDENTITY", "")
    for name, value, length in (
        ("HARMONIC_FARM_COMMIT", commit, 40),
        ("HARMONIC_FARM_AGENT_IDENTITY", agent_identity, 64),
    ):
        if len(value) != length or any(char not in "0123456789abcdef" for char in value):
            raise RuntimeError(
                f"farm preparation publication requires admitted {name} "
                f"as a full lowercase {length}-hex identity"
            )
    if commit != os.environ.get("HARMONIC_FARM_COMMIT"):
        raise RuntimeError(
            "farm preparation publication source does not match the admitted commit"
        )
    workspace = REPO_ROOT.resolve()
    directory = os.environ.get("HARMONIC_FARM_REQUESTS")
    if not directory or not Path(directory).is_dir():
        raise BuildOwnershipError(
            "farm preparation publication has no parent-owned requests directory"
        )
    identity = {
        "build_id": request.build_id,
        "workspace": str(workspace),
        "pool_home": str(pool),
        "commit": commit,
        "agent_identity_sha256": agent_identity,
    }
    digest = _preparation_identity_digest(identity)
    receipts = Path(directory) / "preparation"
    receipts.mkdir(exist_ok=True)
    path = receipts / f"{digest}.json"
    from filelock import FileLock, Timeout

    with _telemetry.span(
        "farm.preparation", service=_telemetry.BUILD_INFRA_SERVICE,
        build_id=request.build_id, commit=commit,
    ) as sp:
        sp.set_attribute("operation_timeout_s", operation_timeout_s)
        sp.set_attribute("process_margin_s", process_margin_s)
        sp.set_attribute("operation_deadline_counter", operation_deadline)
        sp.set_attribute("publication_clock_domain", "perf_counter")
        lock = FileLock(str(path.with_suffix(".lock")))
        while True:
            _raise_if_pool_publication_cancelled()
            remaining = observation_deadline - clock()
            if remaining <= 0:
                raise RuntimeError(
                    f"farm preparation publication lock timed out after "
                    f"{operation_timeout_s:g}s work and {process_margin_s:g}s "
                    f"process margin for build {request.build_id} at PoolHome {pool}"
                )
            try:
                # Short Windows waits keep Ctrl-C responsive. The margin is
                # only for observing an existing owner's terminal outcome.
                lock.acquire(timeout=min(1.0, remaining))
            except Timeout:
                continue
            break
        try:
            _raise_if_pool_publication_cancelled()
            sp.set_attribute("lock_wait_ms", int((clock() - started) * 1000))
            try:
                receipt = _read_preparation_receipt(
                    path, build_id=request.build_id, identity=identity,
                )
            except FileNotFoundError:
                receipt = None
            # I3: terminal receipts are absorbing: no rewrite or second launch.
            if receipt is not None:
                sp.set_attribute("publication_state", receipt["state"])
                if receipt["state"] == "succeeded":
                    return
                if receipt["state"] == "publishing":
                    error = (
                        "farm preparation publication was interrupted or owned "
                        f"process cleanup is unconfirmed for build {request.build_id}; "
                        "verify publisher cleanup before restarting the build"
                    )
                else:
                    error = receipt["error"]
                raise RuntimeError(error)
            publication_started = clock()
            try:
                if publication_started >= operation_deadline:
                    raise RuntimeError(
                        "preparation publication operation deadline exhausted "
                        "before publisher launch"
                    )
                # I1: every receipt/staging write is under this digest lock.
                # I2: atomically record publishing before any publisher launch.
                _atomic_json(path, {
                    "identity": identity, "state": "publishing", "error": None,
                })
                _raise_if_pool_publication_cancelled()
                if clock() >= operation_deadline:
                    raise RuntimeError(
                        "preparation publication operation deadline exhausted "
                        "before publisher launch"
                    )
                _publish_preparation(
                    pool, workspace, commit, agent_identity,
                    operation_deadline=operation_deadline,
                    process_margin_s=process_margin_s, clock=clock,
                )
            except PoolProcessCleanupError:
                # The owned publisher may still be writing. Keep the
                # nonterminal marker; every observer must fail closed.
                sp.set_attribute("publication_state", "cleanup_unconfirmed")
                raise
            except Exception as exc:
                error = (
                    f"farm preparation publication failed for build "
                    f"{request.build_id}: {exc}"
                )
                _atomic_json(path, {
                    "identity": identity, "state": "failed", "error": error,
                })
                sp.set_attribute("publication_state", "failed")
                raise RuntimeError(error) from exc
            finally:
                sp.set_attribute(
                    "publication_ms",
                    int((clock() - publication_started) * 1000),
                )
            _atomic_json(path, {
                "identity": identity, "state": "succeeded", "error": None,
            })
            sp.set_attribute("publication_state", "succeeded")
        finally:
            lock.release()


async def _dispatch(request: LeafRequest, wf_id: str) -> LeafResult:
    _display_name()
    if request.build_id != _required_build_id():
        raise BuildOwnershipError("leaf build ID does not match parent ownership")
    _require_preparation_readiness()
    from temporalio.client import WorkflowFailureError
    from temporalio.exceptions import CancelledError

    client = await asyncio.wait_for(
        _connect_client(request.submitter), timeout=FIFO_RPC_TIMEOUT_S
    )
    coordinator = await _fifo_handle(client)
    # Parent registration and its independent lease renewer already precede all
    # task/cache work. Publish only here, after a genuine miss and coordinator
    # admission, but before recording or accepting the first remote reservation.
    _ensure_preparation_published(request)
    identity = {
        "workflow_id": wf_id,
        "task": request.task,
        "commit": request.commit,
        "build_id": request.build_id,
    }
    _telemetry.info(f"Farm workflow requested: {wf_id}", **identity)
    _record_request(request.task, wf_id, request.refresh_reason)
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
