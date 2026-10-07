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
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import timedelta
from io import TextIOWrapper
from pathlib import Path
from typing import BinaryIO

from filelock import FileLock, Timeout as FileLockTimeout

import _telemetry

REPO_ROOT = Path(__file__).resolve().parents[2]

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

FAILED_LOG_TIMEOUT_S = 30.0
FAILED_LOG_LOCK_TIMEOUT_S = 30.0
# Match the current pool worker's published task.log ceiling, not an SDK chunk size.
FAILED_LOG_MAX_BYTES = 16 * 1024 * 1024
FAILED_LOG_DIAGNOSTIC_BYTES = 64 * 1024
FAILED_LOG_LOCK_ENV = "HARMONIC_FARM_LOG_LOCK"


def _failed_log_lock_path() -> Path:
    """An output lock inherited by every doit process in this submitter run."""

    override = os.environ.get(FAILED_LOG_LOCK_ENV)
    if override:
        return Path(override)
    path = (
        Path(tempfile.gettempdir())
        / "harmonic-analyzer"
        / f"farm-output-{os.getpid()}.lock"
    )
    os.environ[FAILED_LOG_LOCK_ENV] = str(path)
    return path


# dodo imports _farm before spawning workers; the environment carries this
# run-specific lock to them without serializing unrelated submitter runs.
_failed_log_lock_path()


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
    # Milliseconds the leaf spent in each worker phase it reached (queue, admit,
    # seat_gate, acquire_source, source_restore, source_verify, execute,
    # publish_log), mirroring the pool contract; a phase never entered is absent.
    # Defaulted so a worker that predates the field still decodes.
    phase_ms: dict[str, int] = field(default_factory=dict)


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
    """The pool checkout supplying the operator CLI and its prepared environment."""

    pool = Path(
        os.environ.get("SOLIDWORKS_POOL_HOME", REPO_ROOT.parent / "solidworks-pool")
    )
    return pool if pool.is_absolute() else (REPO_ROOT / pool).resolve()


def _pool_python(pool: Path) -> Path:
    """Resolve the same project environment uv prepares during farm preflight."""

    pool_root = pool if pool.is_absolute() else (REPO_ROOT / pool).resolve()
    configured = os.environ.get("UV_PROJECT_ENVIRONMENT")
    environment = Path(configured) if configured else Path(".venv")
    if not environment.is_absolute():
        environment = pool_root / environment
    executable = (
        Path("Scripts") / "python.exe" if os.name == "nt" else Path("bin/python")
    )
    return environment / executable


def run_pool_cli(
    pool: Path,
    *args: str,
    interpreter: Path | None = None,
    stdout: int | BinaryIO = subprocess.PIPE,
    stderr: int | BinaryIO | None = None,
    timeout_s: float | None = None,
    max_stdout_bytes: int | None = None,
) -> subprocess.CompletedProcess:
    """Run the current pool CLI without importing its package into this process.

    Preflight uses uv to prepare the pool's locked environment. Failure-log
    reads use that interpreter directly, so the timeout kills the reader
    itself, not a uv parent that could leave the reader running.
    """

    pool = pool if pool.is_absolute() else (REPO_ROOT / pool).resolve()
    argv = (
        [
            "uv",
            "run",
            "--frozen",
            "--project",
            str(pool),
            "python",
            str(pool / "farm.py"),
            *args,
        ]
        if interpreter is None
        else [str(interpreter), str(pool / "farm.py"), *args]
    )
    env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    if max_stdout_bytes is not None:
        if interpreter is None or isinstance(stdout, int) or timeout_s is None:
            raise ValueError(
                "bounded log reads require a direct interpreter, spool and timeout"
            )
        return _run_bounded_log_reader(
            argv, env, stdout, stderr, timeout_s, max_stdout_bytes
        )
    text_options = (
        {"text": True, "encoding": "utf-8", "errors": "replace"}
        if stdout == subprocess.PIPE
        else {}
    )
    return subprocess.run(
        argv,
        cwd=REPO_ROOT,
        env=env,
        stdout=stdout,
        stderr=stderr,
        timeout=timeout_s,
        **text_options,
    )


class _FailedLogTooLarge(Exception):
    """The exact log reader exceeded the submitter's payload ceiling."""


def _run_bounded_log_reader(
    argv: list[str],
    env: dict[str, str],
    spool: BinaryIO,
    stderr: int | BinaryIO | None,
    timeout_s: float,
    max_bytes: int,
) -> subprocess.CompletedProcess:
    """Bound the reader's lifetime and spool growth while draining raw stdout."""

    with subprocess.Popen(
        argv,
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=stderr,
        bufsize=0,
    ) as process:
        assert process.stdout is not None
        timed_out = threading.Event()

        def expire() -> None:
            if process.poll() is None:
                timed_out.set()
                try:
                    process.kill()
                except OSError:
                    pass

        timer = threading.Timer(timeout_s, expire)
        timer.daemon = True
        timer.start()
        written = 0
        try:
            while chunk := process.stdout.read(
                min(64 * 1024, max_bytes - written + 1)
            ):
                if timed_out.is_set():
                    raise subprocess.TimeoutExpired(argv, timeout_s)
                written += len(chunk)
                if written > max_bytes:
                    raise _FailedLogTooLarge(
                        f"task log exceeded the {max_bytes}-byte output limit; "
                        "reader stopped and payload not shown"
                    )
                spool.write(chunk)
            returncode = process.wait()
            if timed_out.is_set():
                raise subprocess.TimeoutExpired(argv, timeout_s)
            return subprocess.CompletedProcess(argv, returncode)
        finally:
            timer.cancel()
            if process.poll() is None:
                process.kill()
            process.wait()
            timer.join()


def _write_spooled_utf8(spool: BinaryIO, line_prefix: str) -> int:
    """Write normalized, attributed UTF-8 lines without taking spool ownership."""

    spool.seek(0)
    reader = TextIOWrapper(spool, encoding="utf-8", errors="replace", newline=None)
    written_chars = 0
    try:
        for line in reader:
            written_chars += len(line)
            sys.stderr.write(
                line_prefix + line + ("" if line.endswith("\n") else "\n")
            )
    finally:
        reader.detach()
    sys.stderr.flush()
    return written_chars


def _write_failed_task_log_block(
    task: str,
    wf_id: str,
    result: LeafResult,
    payload: BinaryIO | None,
    diagnostics: BinaryIO | None,
    warnings: list[tuple[str, str]],
) -> None:
    """Keep reader diagnostics distinct from the exact failed-attempt payload."""

    identity = (
        f"task={task} workflow={wf_id} worker={result.worker_id} "
        f"attempt={result.attempt} log_blob={result.log_blob or '<absent>'}"
    )
    fields = {
        "task": task,
        "workflow_id": wf_id,
        "log_blob": result.log_blob or "",
        "worker_id": result.worker_id,
        "attempt": result.attempt,
    }
    sys.stderr.write(f"--- begin failed farm task log: {identity} ---\n")
    sys.stderr.flush()
    if payload is not None:
        _write_spooled_utf8(payload, f"[farm {identity}] ")
    if diagnostics is not None:
        diagnostics.seek(0, os.SEEK_END)
        size = diagnostics.tell()
        if size:
            # Bound reader output independently of the published worker log.
            diagnostics.seek(0)
            with tempfile.SpooledTemporaryFile(
                max_size=FAILED_LOG_DIAGNOSTIC_BYTES
            ) as bounded:
                bounded.write(diagnostics.read(FAILED_LOG_DIAGNOSTIC_BYTES))
                _write_spooled_utf8(bounded, f"[farm log-reader {identity}] ")
            if size > FAILED_LOG_DIAGNOSTIC_BYTES:
                warnings.append(
                    (
                        "diagnostic_truncated",
                        f"log reader diagnostics exceeded "
                        f"{FAILED_LOG_DIAGNOSTIC_BYTES} bytes; only the prefix is shown",
                    )
                )
    for reason, message in warnings:
        _telemetry.warn(
            f"{message}; the original farm failure is unchanged",
            reason=reason,
            **fields,
        )
    sys.stderr.write(f"--- end failed farm task log: {identity} ---\n")
    sys.stderr.flush()


def _emit_failed_task_log(task: str, wf_id: str, result: LeafResult) -> None:
    """Fetch in parallel, then serialize bounded output for this exact result."""

    warnings: list[tuple[str, str]] = []
    payload: BinaryIO | None = None
    diagnostics: BinaryIO | None = None
    readable_payload: BinaryIO | None = None
    try:
        if not result.log_blob:
            warnings.append(
                ("log_blob_absent", "no task log was published for this failed leaf")
            )
        else:
            try:
                payload = tempfile.TemporaryFile()
                diagnostics = tempfile.TemporaryFile()
            except OSError as exc:
                warnings.append(
                    (
                        "spool_create_error",
                        f"task log spool could not be created: {exc}",
                    )
                )
            else:
                pool = pool_home()
                try:
                    retrieved = run_pool_cli(
                        pool,
                        "logs",
                        wf_id,
                        "--log-blob",
                        result.log_blob,
                        interpreter=_pool_python(pool),
                        stdout=payload,
                        stderr=diagnostics,
                        timeout_s=FAILED_LOG_TIMEOUT_S,
                        max_stdout_bytes=FAILED_LOG_MAX_BYTES,
                    )
                except subprocess.TimeoutExpired:
                    warnings.append(
                        (
                            "retrieval_timeout",
                            f"task log retrieval timed out after {FAILED_LOG_TIMEOUT_S:g}s",
                        )
                    )
                except _FailedLogTooLarge as exc:
                    warnings.append(("retrieval_too_large", str(exc)))
                except OSError as exc:
                    warnings.append(
                        (
                            "retrieval_start_error",
                            f"task log retrieval could not start: {exc}",
                        )
                    )
                else:
                    if retrieved.returncode != 0:
                        warnings.append(
                            (
                                "retrieval_exit",
                                f"task log retrieval exited {retrieved.returncode}",
                            )
                        )
                    else:
                        payload.seek(0, os.SEEK_END)
                        size = payload.tell()
                        if size > FAILED_LOG_MAX_BYTES:
                            warnings.append(
                                (
                                    "retrieval_too_large",
                                    f"task log is {size} bytes, exceeding the "
                                    f"{FAILED_LOG_MAX_BYTES}-byte output limit; "
                                    "payload not shown",
                                )
                            )
                        elif size == 0:
                            warnings.append(
                                ("retrieval_empty", "task log retrieval returned no output")
                            )
                        else:
                            readable_payload = payload

        lock_path = _failed_log_lock_path()
        try:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            with FileLock(str(lock_path), timeout=FAILED_LOG_LOCK_TIMEOUT_S):
                _write_failed_task_log_block(
                    task, wf_id, result, readable_payload, diagnostics, warnings
                )
        except (OSError, FileLockTimeout) as exc:
            _telemetry.warn(
                f"failed task log output could not be serialized or written: {exc}; "
                "the original farm failure is unchanged; payload not shown completely",
                reason="output_lock_error",
                task=task,
                workflow_id=wf_id,
                log_blob=result.log_blob or "",
                worker_id=result.worker_id,
                attempt=result.attempt,
            )
    finally:
        for spool in (payload, diagnostics):
            if spool is not None:
                try:
                    spool.close()
                except OSError:
                    pass


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
        # The worker's own phase split, so a slow leaf's farm.run span says whether
        # it waited (queue/seat_gate), fetched (acquire_source) or built (execute)
        # without joining the pool's log by time window.
        for phase, ms in result.phase_ms.items():
            sp.set_attribute(f"phase.{phase}_ms", ms)
        if result.state != "succeeded":
            try:
                _emit_failed_task_log(task, wf_id, result)
            except Exception as exc:
                # Diagnostics are supplemental: an unavailable stream, spool,
                # lock or logger must never replace the worker's failed result.
                try:
                    _telemetry.warn(
                        f"failed task log diagnostic could not be emitted: {exc}; "
                        "the original farm failure is unchanged",
                        reason="diagnostic_error",
                        task=task,
                        workflow_id=wf_id,
                        log_blob=result.log_blob or "",
                        worker_id=result.worker_id,
                        attempt=result.attempt,
                    )
                except Exception:
                    pass
        return result


def _record_request(task: str, wf_id: str) -> None:
    """Name this workflow in the launcher run's request directory, if any.

    scripts/farm-run.ps1 exports ``HARMONIC_FARM_REQUESTS``. Its own copy of
    this process's output can lose the last lines when -Cancel stops it, so
    -Cancel also reads these files, written straight from here before the
    workflow can exist. One file per workflow, renamed into place, so parallel
    doit workers never share a handle and a reader never sees half a file. A
    write that fails fails the leaf before dispatch: an unnamed leaf could
    outlive a cancel.
    """
    directory = os.environ.get("HARMONIC_FARM_REQUESTS")
    if not directory:
        return
    name = hashlib.sha256(wf_id.encode("utf-8")).hexdigest()[:32]
    path = Path(directory) / f"{name}.json"
    staging = path.with_name(f"{name}.{os.getpid()}.tmp")
    staging.write_text(
        json.dumps({"task": task, "workflow_id": wf_id}), encoding="utf-8"
    )
    os.replace(staging, path)


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
    _record_request(request.task, wf_id)
    # A memo is written only by the start that creates the execution; an
    # attach (USE_EXISTING) leaves the creator's. The request records above say
    # this run asked for the leaf; only the memo says its own run created it
    # (farm.py status --json reports it as farm_run).
    farm_run = os.environ.get("HARMONIC_FARM_RUN")
    handle = await client.start_workflow(
        WORKFLOW_BUILD_LEAF,
        request,
        id=wf_id,
        task_queue=TASK_QUEUE_CONTROL,
        result_type=LeafResult,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        execution_timeout=EXECUTION_TIMEOUT,
        memo={"farm_run": farm_run} if farm_run else None,
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
