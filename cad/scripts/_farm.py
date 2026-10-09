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
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

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
    display_name = _display_name()
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
    # (farm.py status --json reports it as farm_run). The display label likewise
    # remains the creator's when another session attaches to this shared ID.
    farm_run = os.environ.get("HARMONIC_FARM_RUN")
    memo = {"display_name": display_name}
    if farm_run:
        memo["farm_run"] = farm_run
    handle = await client.start_workflow(
        WORKFLOW_BUILD_LEAF,
        request,
        id=wf_id,
        task_queue=TASK_QUEUE_CONTROL,
        result_type=LeafResult,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        execution_timeout=EXECUTION_TIMEOUT,
        memo=memo,
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
