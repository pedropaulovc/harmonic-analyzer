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
import codecs
import getpass
import json
import os
import socket
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import BinaryIO

from filelock import FileLock

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

REPO_ROOT = Path(__file__).resolve().parents[2]
FAILED_LOG_TIMEOUT_S = 30.0
FAILED_LOG_LOCK_ENV = "HARMONIC_FARM_LOG_LOCK"


def _failed_log_lock_path() -> Path:
    """One output lock shared by the doit processes in this submitter build."""

    override = os.environ.get(FAILED_LOG_LOCK_ENV)
    if override:
        return Path(override)
    path = (
        Path(tempfile.gettempdir())
        / "harmonic-analyzer"
        / f"farm-output-{os.getpid()}.lock"
    )
    # dodo imports _farm before it spawns its workers, so this build-specific path
    # travels to every worker without serializing unrelated build invocations.
    os.environ[FAILED_LOG_LOCK_ENV] = str(path)
    return path


_FAILED_LOG_LOCK_PATH = _failed_log_lock_path()


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


def pool_home() -> Path:
    """The pool checkout whose operator CLI reads completed leaf logs."""

    return Path(
        os.environ.get("SOLIDWORKS_POOL_HOME", REPO_ROOT.parent / "solidworks-pool")
    )


def run_pool_cli(
    pool: Path,
    *args: str,
    stdout: int | BinaryIO = subprocess.PIPE,
    stderr: int | BinaryIO | None = None,
    timeout_s: float | None = None,
) -> subprocess.CompletedProcess:
    """Run the pool's ``farm.py`` in its own locked environment.

    Captured output is decoded explicitly as UTF-8 for machine-readable callers.
    Supplied binary sinks receive raw child streams instead, allowing failure-log
    output to be spooled without requiring ``sys.stderr`` to expose ``fileno``.
    """

    argv = [
        "uv",
        "run",
        "--frozen",
        "--project",
        str(pool),
        "python",
        str(pool / "farm.py"),
        *args,
    ]
    env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    if stdout == subprocess.PIPE:
        return subprocess.run(
            argv,
            cwd=REPO_ROOT,
            env=env,
            stdout=stdout,
            stderr=stderr,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
    return subprocess.run(
        argv,
        cwd=REPO_ROOT,
        env=env,
        stdout=stdout,
        stderr=stderr,
        timeout=timeout_s,
    )


def _write_spooled_utf8(spool: BinaryIO) -> int:
    """Copy a binary spool to task stderr; return decoded characters written."""

    spool.seek(0)
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    written_chars = 0
    ends_with_newline = True
    while chunk := spool.read(64 * 1024):
        text = decoder.decode(chunk)
        if text:
            sys.stderr.write(text)
            written_chars += len(text)
            ends_with_newline = text.endswith(("\n", "\r"))
    tail = decoder.decode(b"", final=True)
    if tail:
        sys.stderr.write(tail)
        written_chars += len(tail)
        ends_with_newline = tail.endswith(("\n", "\r"))
    if written_chars and not ends_with_newline:
        sys.stderr.write("\n")
    sys.stderr.flush()
    return written_chars


def _write_failed_task_log_block(
    identity: str,
    result: LeafResult,
    spool: BinaryIO | None,
    warnings: list[str],
    retrieval_exit_code: int | None,
) -> None:
    """Write one already-retrieved failure as an indivisible console block."""

    print(f"--- begin failed farm task log: {identity} ---", file=sys.stderr, flush=True)
    if result.log_blob is None:
        print(
            "no task log was published for this failed leaf",
            file=sys.stderr,
            flush=True,
        )
    elif spool is not None:
        try:
            written_chars = _write_spooled_utf8(spool)
        except (OSError, ValueError) as exc:
            written_chars = 0
            warnings.append(f"the retrieved task log could not be read: {exc}")
        if retrieval_exit_code == 0 and written_chars == 0:
            warnings.append("task log retrieval returned no output")
    for warning in warnings:
        print(
            f"warning: {warning}; the original farm failure is unchanged",
            file=sys.stderr,
            flush=True,
        )
    print(file=sys.stderr, flush=True)
    print(f"--- end failed farm task log: {identity} ---", file=sys.stderr, flush=True)


def _emit_failed_task_log(task: str, wf_id: str, result: LeafResult) -> None:
    """Retrieve in parallel, then print one failed leaf as a complete block."""

    identity = f"{task} ({wf_id})"
    warnings: list[str] = []
    spool: BinaryIO | None = None
    retrieval_exit_code: int | None = None
    if result.log_blob is not None:
        try:
            spool = tempfile.TemporaryFile()
        except OSError as exc:
            warnings.append(f"task log retrieval could not create its spool: {exc}")
        else:
            try:
                retrieved = run_pool_cli(
                    pool_home(),
                    "logs",
                    wf_id,
                    "--log-blob",
                    result.log_blob,
                    stdout=spool,
                    stderr=spool,
                    timeout_s=FAILED_LOG_TIMEOUT_S,
                )
            except subprocess.TimeoutExpired:
                warnings.append(
                    f"task log retrieval timed out after {FAILED_LOG_TIMEOUT_S:g}s"
                )
            except OSError as exc:
                warnings.append(f"task log retrieval could not start: {exc}")
            else:
                retrieval_exit_code = retrieved.returncode
                if retrieval_exit_code != 0:
                    warnings.append(
                        f"task log retrieval exited {retrieval_exit_code}"
                    )

    lock_path = _failed_log_lock_path()
    output_lock = FileLock(str(lock_path))
    locked = False
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        output_lock.acquire()
        locked = True
    except OSError as exc:
        warnings.append(f"failed task log output could not be serialized: {exc}")
    try:
        _write_failed_task_log_block(
            identity, result, spool, warnings, retrieval_exit_code
        )
    finally:
        if locked:
            try:
                output_lock.release()
            except OSError:
                pass
        if spool is not None:
            try:
                spool.close()
            except OSError:
                pass


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
        if result.state != "succeeded":
            _emit_failed_task_log(task, wf_id, result)
        return result


async def _dispatch(request: LeafRequest, wf_id: str) -> LeafResult:
    # temporalio loads a Rust bridge; import it only when a leaf is dispatched so
    # local builds and the offline check:* workers never pay for it.
    from temporalio.client import Client, WorkflowFailureError
    from temporalio.common import WorkflowIDConflictPolicy
    from temporalio.exceptions import CancelledError
    from temporalio.service import TLSConfig

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
    )
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
        return await handle.result()
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
