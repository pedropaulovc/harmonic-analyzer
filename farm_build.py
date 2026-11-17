"""Submit, track and cancel SolidWorks build-farm runs: the one farm entry point.

    uv run python farm_build.py run part:pn_pen_rod --display-name "Owner - Reason" --leaf-timeout 90
    uv run python farm_build.py watch <run-id | tag>
    uv run python farm_build.py status <run-id | tag>
    uv run python farm_build.py list [--tag T] [--state S] [--max-age-hours H]
    uv run python farm_build.py cancel <run-id | tag> --why "superseded by <sha>"

``run`` checks the caller's worktree (clean, HEAD known on origin), writes the
run record under the runs directory (outside every Git worktree) and starts a
detached supervisor, then waits until the build either passes its preflight
(the producer is about to register with the FIFO coordinator) or stops. The
supervisor survives the caller and every harness deadline. It joins a
kill-on-close Windows job before starting anything, so its whole process tree
dies with it and nothing it started can outlive it and keep dispatching. It
checks out a private detached snapshot of the commit, syncs a shared environment
keyed by the commit's lock and submodule pins, and runs ``farm_build.py _build``
from the snapshot: the commit being built supplies its own graph and farm client.
That child keeps doit as the local scheduler (freshness, cache restore, the
SolidWorks-free ``check:*`` tasks) and runs every cache-missing COM leaf on the
farm (``dodo._cached_com_action`` -> ``dodo._farm_build``). Afterwards the
supervisor moves the snapshot's ``cad/out`` into the run directory, removes the
snapshot and writes ``status.json``.

Records under ``<runs>/<run-id>/``, each written by the code that knows it:
``run.json`` (launch), ``supervisor.json`` (process identity), ``build.json``
(FIFO build id, written before registration), ``leaves/*.json`` (one per farm
workflow, written by the Temporal client: requested -> bound -> result),
``task-errors.json`` (doit's reporter), ``status.json`` (terminal outcome) and
``build.log``. ``status``/``watch`` derive the run's state from them: the terminal
record when it exists, else ``running`` while the supervisor lives, else
``launcher-died`` (the local outcome is unknown and remote leaves may still be
running; never read it as cancelled). ``watch`` exits 0 succeeded, 20 failed,
21 launcher-died, 22 cancelled.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = REPO_ROOT / "cad" / "scripts"
RECORD_SCHEMA = 1
RUN_ID_PATTERN = re.compile(r"\d{8}T\d{9}Z-[0-9a-f]{32}\Z")
TAG_PATTERN = re.compile(r"[A-Za-z0-9_-]+\Z")
WATCH_EXIT_CODES = {"succeeded": 0, "failed": 20, "launcher-died": 21, "cancelled": 22}
DEFAULT_PARALLELISM = "8"
_STOP_WAIT_S = 60


class LaunchError(Exception):
    """Why a command must stop before it changes anything; exit 2."""


class FarmPreflightError(Exception):
    """Why a build must stop before any farm side effect; printed as ``farm: <reason>``."""


# --- records -----------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text)


def write_json(path: Path, value: object, *, replace: bool = True) -> None:
    """Write ``value`` atomically; ``replace=False`` refuses an existing record."""
    if not replace and path.exists():
        raise LaunchError(f"refusing to overwrite existing record {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    staging.write_text(
        json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    os.replace(staging, path)


def read_json(path: Path) -> dict | list | None:
    """A record, or ``None`` when it does not exist (yet)."""
    deadline = time.monotonic() + 10
    while True:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except PermissionError:
            # A reader can hit a sharing violation right after os.replace.
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


def runs_root(explicit: str | None = None) -> Path:
    value = explicit or os.environ.get("HARMONIC_FARM_RUNS")
    if value:
        return Path(value).absolute()
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise LaunchError(
            "LOCALAPPDATA is unset; pass --runs-dir or set HARMONIC_FARM_RUNS"
        )
    return Path(local) / "ha-farm" / "runs"


def _new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")[:-3]
    return f"{stamp}Z-{uuid.uuid4().hex}"


def select_run(root: Path, selector: str) -> Path:
    """A run directory by run id, or the newest run carrying ``selector`` as its tag."""
    if RUN_ID_PATTERN.fullmatch(selector):
        run_dir = root / selector
        if not (run_dir / "run.json").is_file():
            raise LaunchError(f"no run record {run_dir / 'run.json'}")
        return run_dir
    if not TAG_PATTERN.fullmatch(selector):
        raise LaunchError(f"{selector!r} is neither a run id nor a tag")
    tagged = [
        (record["started_at"], run_dir)
        for run_dir, record in _run_records(root)
        if record.get("tag") == selector
    ]
    if not tagged:
        raise LaunchError(f"no run tagged {selector!r} under {root}")
    return max(tagged)[1]


def _run_records(root: Path):
    if not root.is_dir():
        return
    for run_dir in sorted(root.iterdir()):
        if RUN_ID_PATTERN.fullmatch(run_dir.name):
            record = read_json(run_dir / "run.json")
            if isinstance(record, dict):
                yield run_dir, record


# --- Windows processes and the run's job ---------------------------------------

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    _kernel32.OpenJobObjectW.restype = wintypes.HANDLE
    _kernel32.OpenJobObjectW.argtypes = (
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    )
    _kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    for _name, _args in {
        "CloseHandle": (wintypes.HANDLE,),
        "GetProcessTimes": (wintypes.HANDLE,)
        + (ctypes.POINTER(wintypes.FILETIME),) * 4,
        "GetExitCodeProcess": (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)),
        "TerminateProcess": (wintypes.HANDLE, wintypes.UINT),
        "TerminateJobObject": (wintypes.HANDLE, wintypes.UINT),
        "AssignProcessToJobObject": (wintypes.HANDLE, wintypes.HANDLE),
        "SetInformationJobObject": (
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ),
    }.items():
        getattr(_kernel32, _name).argtypes = _args
        getattr(_kernel32, _name).restype = wintypes.BOOL
    _kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    _kernel32.WaitForSingleObject.restype = wintypes.DWORD

    class _BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimits),
            ("IoInfo", ctypes.c_uint64 * 6),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]


_PROCESS_TERMINATE = 0x0001
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_SYNCHRONIZE = 0x00100000
_STILL_ACTIVE = 259
_ERROR_FILE_NOT_FOUND = 2
_ERROR_INVALID_PARAMETER = 87
_JOB_OBJECT_TERMINATE = 0x0008
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
_BREAKAWAY = 0x01000000  # CREATE_BREAKAWAY_FROM_JOB


def _require_windows() -> None:
    if sys.platform != "win32":
        raise LaunchError("farm runs are launched and tracked from Windows")


def _open_process(pid: int, access: int):
    """A handle to ``pid``, or ``None`` when no such process exists."""
    handle = _kernel32.OpenProcess(access, False, pid)
    if handle:
        return handle
    error = ctypes.get_last_error()
    if error == _ERROR_INVALID_PARAMETER:
        return None
    raise ctypes.WinError(error)


def _creation_time(handle) -> int:
    created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
    if not _kernel32.GetProcessTimes(
        handle,
        ctypes.byref(created),
        ctypes.byref(exited),
        ctypes.byref(kernel),
        ctypes.byref(user),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return (created.dwHighDateTime << 32) | created.dwLowDateTime


def process_identity(pid: int) -> int | None:
    """The creation time of live process ``pid``; ``None`` if it is gone.

    Access failures propagate: inability to read a process's identity is never
    evidence that it died.
    """
    _require_windows()
    handle = _open_process(pid, _PROCESS_QUERY_LIMITED_INFORMATION)
    if handle is None:
        return None
    try:
        code = wintypes.DWORD()
        if not _kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        if code.value != _STILL_ACTIVE:
            return None
        return _creation_time(handle)
    finally:
        _kernel32.CloseHandle(handle)


def process_alive(identity: dict | None) -> bool:
    """Whether the recorded ``{pid, created}`` is still that same live process."""
    if not identity or identity.get("created") is None:
        return False
    return process_identity(int(identity["pid"])) == int(identity["created"])


def _stop_process(identity: dict) -> bool:
    """Terminate exactly the recorded process; True once it is gone."""
    handle = _open_process(
        int(identity["pid"]),
        _PROCESS_TERMINATE | _PROCESS_QUERY_LIMITED_INFORMATION | _SYNCHRONIZE,
    )
    if handle is None:
        return True
    try:
        if _creation_time(handle) != int(identity["created"]):
            return True  # the PID now names another process
        _kernel32.TerminateProcess(handle, 1)
        return _kernel32.WaitForSingleObject(handle, _STOP_WAIT_S * 1000) == 0
    finally:
        _kernel32.CloseHandle(handle)


def join_kill_on_close_job(name: str) -> None:
    """Put this process, and so everything it starts, in a kill-on-close job.

    The handle is never closed: when this process exits for any reason, the job
    closes and Windows terminates every remaining member.
    """
    _require_windows()
    job = _kernel32.CreateJobObjectW(None, name)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = _ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not _kernel32.SetInformationJobObject(
        job,
        _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(limits),
        ctypes.sizeof(limits),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    if not _kernel32.AssignProcessToJobObject(job, _kernel32.GetCurrentProcess()):
        raise ctypes.WinError(ctypes.get_last_error())


def terminate_job(name: str) -> bool:
    """Terminate every member of the named job; False when the job is gone."""
    _require_windows()
    job = _kernel32.OpenJobObjectW(_JOB_OBJECT_TERMINATE, False, name)
    if not job:
        error = ctypes.get_last_error()
        if error == _ERROR_FILE_NOT_FOUND:
            return False
        raise ctypes.WinError(error)
    try:
        if not _kernel32.TerminateJobObject(job, 1):
            raise ctypes.WinError(ctypes.get_last_error())
        return True
    finally:
        _kernel32.CloseHandle(job)


def _spawn_detached(argv: list[str], **kwargs) -> subprocess.Popen:
    """Start ``argv`` outside the caller's console, group and (when allowed) job."""
    common = dict(
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        **kwargs,
    )
    try:
        return subprocess.Popen(argv, creationflags=_DETACHED | _BREAKAWAY, **common)
    except PermissionError:
        # The caller's job forbids breakaway; the trampoline still severs the
        # parent chain a harness tree-kill walks.
        return subprocess.Popen(argv, creationflags=_DETACHED, **common)


# --- git ---------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    try:
        done = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise LaunchError(f"git {' '.join(args)} could not start: {exc}") from None
    if done.returncode != 0:
        raise LaunchError(
            f"git {' '.join(args)} failed (exit {done.returncode}): {done.stderr.strip()}"
        )
    return done.stdout


def excluded_submodules(repo: Path, commit: str) -> frozenset[str]:
    """Submodule paths the commit's ``.farm-sources.json`` says no farm leaf reads.

    A missing file excludes nothing; a malformed one is refused. Paths are
    normalized as the worker normalizes them (``./references/`` = ``references``).
    """
    listed = _git(repo, "ls-tree", "--name-only", commit, "--", ".farm-sources.json")
    if not listed.strip():
        return frozenset()
    text = _git(repo, "show", f"{commit}:.farm-sources.json")
    try:
        declared = json.loads(text)
    except ValueError as exc:
        raise LaunchError(f".farm-sources.json is not valid JSON: {exc}") from None
    if not isinstance(declared, dict):
        raise LaunchError(".farm-sources.json must be a JSON object")
    paths = declared.get("exclude_submodules", [])
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        raise LaunchError(
            ".farm-sources.json: exclude_submodules must be a list of strings"
        )
    return frozenset(PurePosixPath(path).as_posix() for path in paths)


def _required_submodules(repo: Path, commit: str) -> list[tuple[str, str]]:
    """``(path, ls-tree line)`` for every gitlink a farm build needs checked out."""
    excluded = excluded_submodules(repo, commit)
    required = []
    for line in _git(repo, "ls-tree", "-r", "--full-tree", commit).splitlines():
        if line.startswith("160000 commit "):
            path = line.split("\t", 1)[1]
            if path not in excluded:
                required.append((path, line))
    return required


def _inside_a_worktree(path: Path) -> bool:
    probe = path
    while not probe.exists():
        probe = probe.parent
    done = subprocess.run(
        ["git", "-C", str(probe), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode == 0 and done.stdout.strip() == "true"


# --- run: launch ---------------------------------------------------------------


def _split_targets(values: list[str]) -> list[str]:
    targets = []
    for value in values:
        for component in value.split(","):
            target = component.strip()
            if not target:
                raise LaunchError("targets contain an empty component")
            if target.startswith("-"):
                raise LaunchError(f"targets contain an option-like selection: {target}")
            if "=" in target:
                # doit would remove it as a command-line variable and silently
                # build the default `build` closure instead.
                raise LaunchError(
                    f"targets are task selections, not doit variables: {target}"
                )
            if target == "release":
                raise LaunchError(
                    "release publishes from the owning worktree, never a disposable "
                    "snapshot; build its closure here and release there (DEVELOPING.md)"
                )
            targets.append(target)
    if not targets:
        raise LaunchError("name at least one target")
    return targets


def _validate_labels(display_name: str, refresh: list[str], reason: str | None) -> None:
    sys.path.insert(0, str(SCRIPTS_DIR))
    import _artifact_cache
    import _farm

    try:
        _farm._display_name(display_name)
        if reason is not None and not refresh:
            raise RuntimeError(
                "--force-cache-refresh-reason requires --force-cache-refresh labels"
            )
        if refresh:
            _artifact_cache.validate_refresh_reason(reason)
            if "" in refresh:
                raise RuntimeError("--force-cache-refresh contains an empty task label")
    except RuntimeError as problem:
        raise LaunchError(str(problem)) from None


def launch(options: argparse.Namespace) -> Path:
    """Validate, record and start one run; the run directory."""
    _require_windows()
    targets = _split_targets(options.targets)
    refresh = list(
        dict.fromkeys(
            label.strip()
            for value in options.force_cache_refresh
            for label in value.split(",")
        )
    )
    if options.leaf_timeout is None or not 1 <= options.leaf_timeout <= 180:
        raise LaunchError("--leaf-timeout must be 1-180 minutes")
    if not TAG_PATTERN.fullmatch(options.tag):
        raise LaunchError("--tag takes letters, digits, '_' and '-' only")
    _validate_labels(options.display_name, refresh, options.force_cache_refresh_reason)

    worktree = Path(options.worktree).resolve()
    pool_home = Path(
        options.pool_home
        or os.environ.get("SOLIDWORKS_POOL_HOME")
        or REPO_ROOT.parent / "solidworks-pool"
    ).resolve()
    if (
        not (pool_home / "farm.py").is_file()
        or not (pool_home / "agent" / "protocol.py").is_file()
    ):
        raise LaunchError(f"pool home {pool_home} lacks farm.py or agent/protocol.py")
    root = runs_root(options.runs_dir)
    if _inside_a_worktree(root):
        raise LaunchError(
            f"runs directory {root} must be outside every Git worktree "
            "(build snapshots are created under it)"
        )
    commit = _git(worktree, "rev-parse", "--verify", "HEAD").strip()
    if not _git(
        worktree, "for-each-ref", f"--contains={commit}", "refs/remotes/origin"
    ).strip():
        raise LaunchError(
            "HEAD is not known on origin; fetch and push before launching"
        )
    dirty = _git(
        worktree,
        "--no-optional-locks",
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    ).splitlines()
    if dirty:
        raise LaunchError(
            "worktree has uncommitted changes; the farm builds the pushed HEAD only:\n"
            + "\n".join(f"  {line}" for line in dirty)
        )
    common = Path(_git(worktree, "rev-parse", "--git-common-dir").strip())
    if not common.is_absolute():
        common = (worktree / common).resolve()
    required = _required_submodules(worktree, commit)

    run_id = _new_run_id()
    run_dir = root / run_id
    run_dir.mkdir(parents=True)
    record = {
        "schema": RECORD_SCHEMA,
        "run_id": run_id,
        "tag": options.tag,
        "display_name": options.display_name,
        "targets": targets,
        "leaf_timeout_minutes": options.leaf_timeout,
        "force_cache_refresh": refresh,
        "force_cache_refresh_reason": options.force_cache_refresh_reason
        if refresh
        else None,
        "worktree": str(worktree),
        "git_common_dir": str(common),
        "pool_home": str(pool_home),
        "commit": commit,
        "required_submodules": [path for path, _line in required],
        "cache_environment": {
            key: os.environ.get(key)
            for key in (
                "HARMONIC_CACHE_ACCOUNT",
                "HARMONIC_CACHE_CONTAINER",
                "HARMONIC_CACHE_SALT",
            )
        },
        "started_at": _now(),
        "snapshot": str(root / "snapshots" / run_id[-32:-20]),
        "job": f"Local\\harmonic-farm-{run_id}",
    }
    write_json(run_dir / "run.json", record, replace=False)
    # The trampoline starts the supervisor and exits, so no live parent chain
    # links the caller to the supervisor.
    trampoline = _spawn_detached(
        [sys.executable, str(Path(__file__).resolve()), "_spawn", str(run_dir)],
        cwd=run_dir,
    )
    if trampoline.wait() != 0 or not (run_dir / "supervisor.json").is_file():
        raise RuntimeError(f"supervisor did not start for {run_dir}")
    return run_dir


def await_preflight(run_dir: Path) -> int:
    """Block until the build registers (0) or the run ends; that run's exit code."""
    while True:
        if (run_dir / "build.json").is_file():
            return 0
        status = run_status(run_dir)
        if status["state"] != "running":
            if status["state"] == "launcher-died":
                return WATCH_EXIT_CODES["launcher-died"]
            return status["exit_code"] if status["exit_code"] is not None else 1
        time.sleep(0.5)


def spawn_supervisor(run_dir: Path) -> int:
    """The trampoline: start the supervisor, record its identity, exit."""
    # The base interpreter, not a venv shim: the supervisor imports only the
    # standard library and must not pin the caller's environment while it runs.
    supervisor = _spawn_detached(
        [
            getattr(sys, "_base_executable", sys.executable),
            "-I",
            str(Path(__file__).resolve()),
            "_supervise",
            str(run_dir),
        ],
        cwd=run_dir,  # never pin the caller's worktree as a current directory
    )
    write_json(
        run_dir / "supervisor.json",
        {"pid": supervisor.pid, "created": process_identity(supervisor.pid)},
    )
    return 0


# --- the supervisor ------------------------------------------------------------


def _run_logged(argv: list[str], log, **kwargs) -> None:
    log.write(f"farm-run $ {' '.join(argv)}\n".encode("utf-8"))
    log.flush()
    code = subprocess.call(argv, stdout=log, stderr=subprocess.STDOUT, **kwargs)
    if code != 0:
        raise RuntimeError(f"{argv[0]} {argv[1]} failed with exit {code}")


def finish_snapshot(record: dict, run_dir: Path) -> dict:
    """Keep the snapshot's ``cad/out`` under the run, then remove the snapshot.

    If the outputs cannot be moved the snapshot is the only copy and stays.
    """
    snapshot = Path(record["snapshot"])
    result = {
        "outputs": None,
        "outputs_preserved": False,
        "snapshot_removed": False,
        "cleanup_errors": [],
    }
    target = run_dir / "out"
    if target.is_dir():
        result.update(outputs=str(target), outputs_preserved=True)
    if not snapshot.exists():
        result["snapshot_removed"] = True
        return result
    produced = snapshot / "cad" / "out"
    if produced.is_dir():
        try:
            os.rename(produced, target)
            result.update(outputs=str(target), outputs_preserved=True)
        except OSError as exc:
            result["outputs"] = str(produced)
            result["cleanup_errors"].append(
                f"could not move {produced} to {target}: {exc}"
            )
            return result
    done = subprocess.run(
        [
            "git",
            f"--git-dir={record['git_common_dir']}",
            "worktree",
            "remove",
            "--force",
            str(snapshot),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode == 0:
        result["snapshot_removed"] = True
    else:
        result["cleanup_errors"].append(
            f"git worktree remove {snapshot} failed (exit {done.returncode}): {done.stderr.strip()}"
        )
    return result


def _terminal(
    record: dict, state: str, exit_code: int | None, cleanup: dict, **extra
) -> dict:
    started = _parse_time(record["started_at"])
    return {
        "state": state,
        "exit_code": exit_code,
        "finished_at": _now(),
        "elapsed_s": round((datetime.now(timezone.utc) - started).total_seconds(), 3),
        **cleanup,
        **extra,
    }


def supervise(run_dir: Path) -> int:
    record = read_json(run_dir / "run.json")
    # A snapshot under the runs directory can exceed MAX_PATH.
    count = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
    os.environ.update(
        {
            f"GIT_CONFIG_KEY_{count}": "core.longpaths",
            f"GIT_CONFIG_VALUE_{count}": "true",
            "GIT_CONFIG_COUNT": str(count + 1),
        }
    )
    snapshot = Path(record["snapshot"])
    code = 1
    with (run_dir / "build.log").open("ab") as log:
        try:
            # First: every process this run starts is a member and dies with it.
            join_kill_on_close_job(record["job"])
            prepared = time.monotonic()
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            git = ["git", f"--git-dir={record['git_common_dir']}"]
            _run_logged(
                [
                    *git,
                    "worktree",
                    "add",
                    "--quiet",
                    "--detach",
                    str(snapshot),
                    record["commit"],
                ],
                log,
            )
            if record["required_submodules"]:
                _run_logged(
                    [
                        "git",
                        "-C",
                        str(snapshot),
                        "submodule",
                        "update",
                        "--quiet",
                        "--init",
                        "--recursive",
                        "--",
                        *record["required_submodules"],
                    ],
                    log,
                )
            if not (snapshot / "farm_build.py").is_file():
                raise RuntimeError(f"{record['commit'][:12]} predates farm_build.py")
            log.write(
                f"farm-run snapshot {snapshot} ready in "
                f"{round(time.monotonic() - prepared, 3)} s\n".encode("utf-8")
            )
            log.flush()
            env = {
                k: v
                for k, v in os.environ.items()
                if k
                not in (
                    "HARMONIC_CACHE_REFRESH",
                    "VIRTUAL_ENV",
                    "UV_PROJECT_ENVIRONMENT",
                )
            }
            env.update(
                {
                    "PYTHONUNBUFFERED": "1",
                    "PYTHONUTF8": "1",
                    "SOLIDWORKS_POOL_HOME": record["pool_home"],
                    "HARMONIC_REMOTE_CACHE_MODE": "rw",
                }
            )
            # The snapshot's own .venv: uv hardlinks it from its cache (~7 s) and
            # `git worktree remove --force` deletes it with the snapshot.
            code = subprocess.call(
                [
                    "uv",
                    "run",
                    "--frozen",
                    "python",
                    "farm_build.py",
                    "_build",
                    str(run_dir),
                ],
                cwd=snapshot,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        except Exception as exc:  # noqa: BLE001 - every outcome writes status.json
            log.write(f"farm-run supervisor failed: {exc}\n".encode("utf-8"))
            code = 1
    cleanup = finish_snapshot(record, run_dir)
    state = "succeeded" if code == 0 and not cleanup["cleanup_errors"] else "failed"
    write_json(
        run_dir / "status.json",
        _terminal(
            record, state, code if code != 0 or state == "succeeded" else 1, cleanup
        ),
    )
    return 0


# --- the build (runs from the snapshot, in the shared environment) -------------


def _pool_farm(pool: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """One ``farm.py`` subcommand in the pool's own uv project; stdout captured."""
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
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "UV_NO_SYNC")
    }
    try:
        return subprocess.run(
            argv, cwd=REPO_ROOT, env=env, stdout=subprocess.PIPE, text=True
        )
    except OSError as exc:
        raise FarmPreflightError(
            f"{args[0]} could not start ({argv[0]}): {exc}"
        ) from None


def _tail(text: str | None, lines: int = 20) -> str:
    kept = [line for line in (text or "").splitlines() if line.strip()][-lines:]
    return "".join(f"\n  {line}" for line in kept)


def require_fleet_protocol(pool: Path, protocol: int) -> None:
    """Stop unless the pool CLI speaks ``protocol`` and its fleet verdict admits it."""
    result = _pool_farm(pool, "agents", "--json")
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    try:
        summary = json.loads(lines[-1]) if result.returncode == 0 and lines else None
    except json.JSONDecodeError:
        summary = None
    if not isinstance(summary, dict):
        raise FarmPreflightError(
            f"agents failed (exit {result.returncode}){_tail(result.stdout)}"
        )
    if summary.get("farm_protocol_version") != protocol:
        raise FarmPreflightError(
            f"pool CLI supports farm protocol {summary.get('farm_protocol_version')!r}, "
            f"but this client requires {protocol}"
        )
    # The pool decides mismatch/unreadable; "unverified" means no worker reported.
    if summary.get("verdict") not in ("matched", "unverified"):
        raise FarmPreflightError(
            summary.get("report")
            or f"fleet protocol verdict {summary.get('verdict')!r}"
        )
    print(f"farm: protocol {protocol}; fleet verdict {summary['verdict']}")


def require_leaf_admission(closure, pool: Path) -> list[str]:
    """The would-be leaves of ``closure``, each admitted by the pool's own rule.

    Loads the selected pool checkout's stdlib-only ``agent/protocol.py`` under a
    private module name, so an unrelated installed ``agent`` package cannot
    answer for it. Any failure to read the rule refuses the run.
    """
    tasks = sorted(
        task.name
        for task in closure
        if any(
            getattr(getattr(action, "py_callable", None), "_farm_leaf_action", False)
            for action in task.actions
        )
    )
    if not tasks:
        return []
    path = pool / "agent" / "protocol.py"
    if not path.is_file():
        raise FarmPreflightError(f"pool home {pool} has no agent/protocol.py")
    try:
        spec = importlib.util.spec_from_file_location("_selected_pool_protocol", path)
        protocol = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(protocol)
        refused = [task for task in tasks if not protocol.leaf_admitted(task)]
    except Exception as exc:  # noqa: BLE001 - an unreadable rule admits nothing
        raise FarmPreflightError(
            f"pool leaf admission could not be read ({path}): {exc}"
        ) from None
    if refused:
        raise FarmPreflightError(
            f"unsupported farm leaf targets in requested closure (pool {pool}):\n"
            + "\n".join(
                f"  {task} (prefix: {task.partition(':')[0]})" for task in refused
            )
        )
    return tasks


def run_farm_build(
    record: dict,
    namespace: dict,
    *,
    extra_config: dict | None = None,
    parallelism: str | None = None,
) -> int:
    """Preflight the requested closure, then run doit with farm dispatch.

    Exit 3 for a selection doit rejects and 2 for a refused preflight, both
    before any farm side effect or action; otherwise doit's own exit code.
    """
    from doit import loader as doit_loader
    from doit.cmd_base import TaskLoader2, tasks_and_deps_iter
    from doit.doit_cmd import DoitMain
    from doit.exceptions import InvalidCommand, InvalidDodoFile, InvalidTask

    import _farm
    import _undefined_names
    import build as local_build

    targets = record["targets"]
    pool = Path(record["pool_home"])
    try:
        config = doit_loader.load_doit_config(namespace)
        tasks = doit_loader.load_tasks(namespace, allow_delayed=True, args=targets)
        control = local_build._validate_farm_selection(tasks, targets)
    except (InvalidCommand, InvalidTask, InvalidDodoFile) as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 3
    closure = list(tasks_and_deps_iter(control.tasks, control.selected_tasks))
    refresh = record["force_cache_refresh"]
    try:
        try:
            label = _farm._display_name(record["display_name"])
        except RuntimeError as exc:
            raise FarmPreflightError(str(exc)) from None
        admitted = require_leaf_admission(closure, pool)
        if refresh:
            local_build._require_cache_refresh(
                tasks, {task.name for task in closure}, refresh
            )
        lint = _undefined_names.scan_undefined_names(REPO_ROOT)
        if lint.returncode != 0:
            raise FarmPreflightError(
                "undefined names in build sources (check:undefined_names):\n"
                + lint.stdout
                + lint.stderr
            )
        require_fleet_protocol(pool, _farm.FARM_PROTOCOL_VERSION)
    except (FarmPreflightError, local_build.CacheRefreshError) as problem:
        print(f"farm: {problem}", file=sys.stderr)
        return 2

    os.environ["HARMONIC_FARM_ADMITTED_LEAVES"] = json.dumps(admitted)
    if refresh:
        os.environ["HARMONIC_CACHE_REFRESH"] = json.dumps(
            {"labels": refresh, "reason": record["force_cache_refresh_reason"]},
            separators=(",", ":"),
        )

    class Preloaded(TaskLoader2):
        def load_doit_config(self):
            # Module-level reporter: doit pickles its class into action workers.
            return {**config, "reporter": _farm.FarmReporter}

        def load_tasks(self, cmd, pos_args):
            return tasks

    workers = parallelism or os.environ.get(
        "HARMONIC_FARM_PARALLELISM", DEFAULT_PARALLELISM
    )
    doit = DoitMain(Preloaded(), extra_config=extra_config)
    try:
        with _farm.producer_build(label) as producer:
            print(
                "farm: every SolidWorks task runs on the farm (parts, assemblies, "
                "drawings, verify:*, export, package:release)"
            )
            code = doit.run(["run", "-n", workers, "--continue", *targets])
            producer.finish(code == 0)
            return code
    except _farm.BuildOwnershipError as problem:
        print(f"farm: {problem}", file=sys.stderr)
        return 2


def build_main(run_dir: Path) -> int:
    record = read_json(run_dir / "run.json")
    if not isinstance(record, dict) or record.get("schema") != RECORD_SCHEMA:
        print(
            f"farm: {run_dir / 'run.json'} is not a schema-{RECORD_SCHEMA} run record",
            file=sys.stderr,
        )
        return 2
    head = _git(REPO_ROOT, "rev-parse", "HEAD").strip()
    if head != record["commit"]:
        print(f"farm: snapshot HEAD {head} is not the recorded commit", file=sys.stderr)
        return 2
    os.environ.update(
        {
            "HARMONIC_EXECUTOR": "farm",
            "HARMONIC_VERBOSITY": "info",
            "HARMONIC_SW_AUTOSTART": "0",
            "HARMONIC_FARM_COMMIT": record["commit"],
            "HARMONIC_FARM_DISPLAY_NAME": record["display_name"],
            "HARMONIC_FARM_LEAF_TIMEOUT_S": str(record["leaf_timeout_minutes"] * 60),
            "HARMONIC_FARM_RUN": record["run_id"],
            "HARMONIC_FARM_RUN_DIR": str(run_dir),
        }
    )
    sys.path.insert(0, str(SCRIPTS_DIR))
    namespace = vars(importlib.import_module("dodo"))
    return run_farm_build(record, namespace)


# --- status, watch, list ---------------------------------------------------------


def _cache_hits(outputs: Path | None, farm_tasks: set[str]) -> int:
    if outputs is None:
        return 0
    try:
        lines = (
            (outputs / "reports" / "cache.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    except OSError:
        return 0
    hits = set()
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("event") in ("restore_hit", "restore_hit_drift"):
            hits.add(event.get("label"))
    return len(hits - farm_tasks)


def _run_state(run_dir: Path) -> tuple[dict | None, bool, str]:
    """``(status.json, supervisor alive, state)``.

    Liveness first: the supervisor writes status.json before it exits, so a
    supervisor already gone with still no status.json never wrote one.
    """
    alive = process_alive(read_json(run_dir / "supervisor.json"))
    final = read_json(run_dir / "status.json")
    if final:
        return final, False, final["state"]
    return None, alive, "running" if alive else "launcher-died"


def run_status(run_dir: Path) -> dict:
    record = read_json(run_dir / "run.json")
    final, alive, state = _run_state(run_dir)
    supervisor = read_json(run_dir / "supervisor.json")
    leaves = (
        sorted(
            (read_json(path) for path in (run_dir / "leaves").glob("*.json")),
            key=lambda leaf: (leaf["task"], leaf["workflow_id"]),
        )
        if (run_dir / "leaves").is_dir()
        else []
    )
    settled = {
        workflow["workflow_id"]: workflow["outcome"]
        for workflow in ((final or {}).get("cancel") or {}).get("workflows", [])
    }
    for leaf in leaves:
        if leaf["state"] in ("requested", "bound") and leaf["workflow_id"] in settled:
            leaf["state"] = settled[leaf["workflow_id"]]
    build = read_json(run_dir / "build.json") or {}
    errors = read_json(run_dir / "task-errors.json") or []
    if final:
        outputs = final.get("outputs")
    elif (run_dir / "out").is_dir():
        outputs = str(run_dir / "out")
    else:
        outputs = str(Path(record["snapshot"]) / "cad" / "out")
    unsettled = [leaf for leaf in leaves if leaf["state"] in ("requested", "bound")]
    log = run_dir / "build.log"
    now = datetime.now(timezone.utc)
    status = {
        "run_id": record["run_id"],
        "tag": record["tag"],
        "state": state,
        "exit_code": final.get("exit_code") if final else None,
        "build_id": build.get("build_id"),
        "commit": record["commit"],
        "targets": record["targets"],
        "display_name": record["display_name"],
        "leaf_timeout_minutes": record["leaf_timeout_minutes"],
        "force_cache_refresh": record["force_cache_refresh"],
        "force_cache_refresh_reason": record["force_cache_refresh_reason"],
        "cache_environment": record["cache_environment"],
        "started_at": record["started_at"],
        "finished_at": final.get("finished_at") if final else None,
        "elapsed_s": final["elapsed_s"]
        if final
        else round((now - _parse_time(record["started_at"])).total_seconds(), 1),
        "log_idle_s": round(time.time() - log.stat().st_mtime, 1)
        if log.exists()
        else None,
        "supervisor": {**(supervisor or {}), "alive": alive},
        "run_dir": str(run_dir),
        "log": str(log),
        "outputs": outputs,
        "counts": {
            "hits": _cache_hits(
                Path(outputs) if outputs else None, {leaf["task"] for leaf in leaves}
            ),
            "requested": len(leaves),
            "succeeded": sum(leaf["state"] == "succeeded" for leaf in leaves),
            "failed": sum(leaf["state"] == "failed" for leaf in leaves),
            "in_flight": len(unsettled),
        },
        "leaves": leaves,
        "unsettled_workflows": [leaf["workflow_id"] for leaf in unsettled],
        "task_errors": errors,
    }
    if final and "cancel" in final:
        status["cancel"] = final["cancel"]
    return status


def _event(run_id: str, text: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"farm-run {stamp} {run_id} {text}", flush=True)


def watch(run_dir: Path, poll_s: float) -> int:
    seen: set[tuple] = set()
    announced = False
    while True:
        status = run_status(run_dir)
        if not announced:
            _event(
                status["run_id"],
                f"watching tag={status['tag']} state={status['state']} "
                f"commit={status['commit']} targets={','.join(status['targets'])}",
            )
            announced = True
        for leaf in status["leaves"]:
            key = ("leaf", leaf["workflow_id"], leaf["state"])
            if key not in seen:
                seen.add(key)
                cause = (
                    f" [{leaf.get('failure_category')}] {leaf.get('failure_message')}"
                    if leaf["state"] == "failed"
                    else ""
                )
                _event(
                    status["run_id"],
                    f"leaf {leaf['task']} {leaf['state']} {leaf['workflow_id']}{cause}",
                )
        for error in status["task_errors"]:
            key = ("error", error["task"], error["error"])
            if key not in seen:
                seen.add(key)
                _event(
                    status["run_id"], f"task failed {error['task']}: {error['error']}"
                )
        if status["state"] in WATCH_EXIT_CODES:
            counts = status["counts"]
            summary = (
                f"end {status['state']} exit_code={status['exit_code']} hits={counts['hits']} "
                f"farm={counts['requested']} succeeded={counts['succeeded']} "
                f"failed={counts['failed']} in_flight={counts['in_flight']}"
            )
            if status["state"] == "launcher-died":
                summary += (
                    "; LAUNCHER DIED: the supervisor is gone without a terminal record "
                    "(its process tree died with it); remote leaves may still be running: "
                    "`farm_build.py cancel` stops them"
                )
            _event(status["run_id"], summary)
            status.pop("leaves")
            print(json.dumps(status, ensure_ascii=False))
            return WATCH_EXIT_CODES[status["state"]]
        time.sleep(poll_s)


def list_runs(
    root: Path, tag: str | None, state: str | None, max_age_h: int | None
) -> None:
    now = datetime.now(timezone.utc)
    rows = []
    for run_dir, record in _run_records(root):
        if tag and record.get("tag") != tag:
            continue
        started = _parse_time(record["started_at"])
        if max_age_h and (now - started).total_seconds() > max_age_h * 3600:
            continue
        final, _alive, run_state = _run_state(run_dir)
        if state and run_state != state:
            continue
        rows.append(
            (
                started,
                {
                    "run_id": record["run_id"],
                    "tag": record["tag"],
                    "display_name": record["display_name"],
                    "state": run_state,
                    "exit_code": final.get("exit_code") if final else None,
                    "started_at": record["started_at"],
                    "commit": record["commit"],
                    "targets": record["targets"],
                    "run_dir": str(run_dir),
                },
            )
        )
    for _started, row in sorted(rows, key=lambda item: item[0], reverse=True):
        print(json.dumps(row, ensure_ascii=False))


# --- cancel --------------------------------------------------------------------


async def _reconcile_leaf(
    client, coordinator, build_id: str, leaf: dict, reason: str, binding_wait_s: int
) -> dict:
    """Cancel exactly the run the coordinator bound this leaf to, if it still runs."""
    import _farm
    from temporalio.client import WorkflowExecutionStatus

    workflow_id = leaf["workflow_id"]
    outcome = {
        "workflow_id": workflow_id,
        "task": leaf["task"],
        "outcome": None,
        "detail": None,
    }
    run_id = leaf.get("run_id")
    waited = time.monotonic()
    while run_id is None:
        status = await _farm._rpc_query(
            coordinator,
            "leaf_status",
            _farm.LeafKey(build_id, workflow_id),
            _farm.LeafStatus,
        )
        if status.key.build_id != build_id or status.key.workflow_id != workflow_id:
            raise RuntimeError(f"invalid coordinator reservation for {workflow_id}")
        if status.error_code or status.state == "recovery_required":
            return {
                **outcome,
                "outcome": "unresolved",
                "detail": f"operator recovery required: {status.error_code}: {status.error}",
            }
        if status.state == "missing_closed":
            # No retained reservation: never submitted, or drained and pruned.
            return {
                **outcome,
                "outcome": "settled-untracked",
                "detail": "producer fenced closed; reservation is no longer tracked",
            }
        if status.binding is not None:
            if (
                status.binding.build_id != build_id
                or status.binding.workflow_id != workflow_id
            ):
                raise RuntimeError(f"invalid coordinator binding for {workflow_id}")
            run_id = status.binding.run_id
            break
        if status.state == "drained" and not status.unconfirmed_attempts:
            return {
                **outcome,
                "outcome": "already-closed",
                "detail": "coordinator confirmed reservation physically drained",
            }
        if status.state != "reserved" or time.monotonic() - waited >= binding_wait_s:
            return {
                **outcome,
                "outcome": "unresolved",
                "detail": f"no exact binding ({status.state}) after {binding_wait_s} s",
            }
        await asyncio.sleep(1)
    outcome["run_id"] = run_id
    handle = client.get_workflow_handle(workflow_id, run_id=run_id)
    description = await handle.describe()
    if description.status != WorkflowExecutionStatus.RUNNING:
        return {
            **outcome,
            "outcome": "already-closed",
            "detail": description.status.name,
        }
    await handle.cancel(reason=reason)
    return {**outcome, "outcome": "cancelled"}


async def reconcile_remote(
    build_id: str, leaves: list[dict], reason: str, binding_wait_s: int
) -> tuple[list[dict], list[str]]:
    """Close producer admission, then settle every unsettled leaf; outcomes and errors."""
    import _farm

    errors: list[str] = []
    client = await _farm._connect_client(_farm.submitter())
    # Never start the coordinator implicitly: only an existing one owns leaves.
    coordinator = client.get_workflow_handle(_farm.WORKFLOW_BUILD_FIFO_ID)
    try:
        await _farm._rpc_update(
            coordinator,
            "close_build",
            _farm.CloseBuild(build_id, "cancelled"),
            _farm.BuildStatus,
            f"close:{build_id}:cancelled",
        )
    except Exception as exc:  # noqa: BLE001 - reported, retried by the operator
        errors.append(f"close_build {build_id} failed: {exc}")
    outcomes = []
    for leaf in leaves:
        try:
            outcome = await _reconcile_leaf(
                client, coordinator, build_id, leaf, reason, binding_wait_s
            )
        except Exception as exc:  # noqa: BLE001
            outcome = {
                "workflow_id": leaf["workflow_id"],
                "task": leaf["task"],
                "outcome": "error",
                "detail": str(exc),
            }
        if outcome["outcome"] in ("unresolved", "error"):
            errors.append(
                f"{outcome['workflow_id']}: {outcome['outcome']}: {outcome['detail']}"
            )
        outcomes.append(outcome)
    return outcomes, errors


def cancel(run_dir: Path, why: str, binding_wait_s: int) -> int:
    """Stop the run's process tree, then settle its farm work; 0 when accounted for."""
    if not why.strip():
        raise LaunchError("cancel --why must say why")
    record = read_json(run_dir / "run.json")
    supervisor = read_json(run_dir / "supervisor.json")
    _finished, _alive, was = _run_state(run_dir)
    if was == "running":
        # Every member at once: the supervisor cannot react to its child dying
        # by writing a `failed` record, and nothing is left to dispatch.
        terminate_job(record["job"])
        if not _stop_process(supervisor):
            print(
                f"farm-run cancel: supervisor {supervisor['pid']} did not exit; retry",
                file=sys.stderr,
            )
            return 1
        _event(record["run_id"], f"stopped supervisor {supervisor['pid']} and its job")
    finished = read_json(run_dir / "status.json")
    build_id = (read_json(run_dir / "build.json") or {}).get("build_id")
    unsettled = [
        leaf
        for leaf in run_status(run_dir)["leaves"]
        if leaf["state"] in ("requested", "bound")
    ]
    outcomes, errors = [], []
    if build_id:
        sys.path.insert(0, str(SCRIPTS_DIR))
        outcomes, errors = asyncio.run(
            reconcile_remote(
                build_id,
                unsettled,
                f"{why} (farm_build.py cancel {record['run_id']})",
                binding_wait_s,
            )
        )
        _event(record["run_id"], f"closed farm build {build_id}")
        for outcome in outcomes:
            _event(record["run_id"], f"{outcome['outcome']} {outcome['workflow_id']}")
    for problem in errors:
        print(f"farm-run cancel: {problem}", file=sys.stderr)
    if finished is not None or errors:
        # A finished run keeps its own record. An unfinished one with a leaf
        # unaccounted for keeps its snapshot and no record, so the same cancel
        # can be retried.
        if errors:
            print(
                "farm-run cancel: not finished; retry the same cancel", file=sys.stderr
            )
            return 1
        return 0
    cleanup = finish_snapshot(record, run_dir)
    write_json(
        run_dir / "status.json",
        _terminal(
            record,
            "cancelled",
            None,
            cleanup,
            cancel={
                "why": why,
                "by": f"{os.environ.get('USERNAME', '?')}@{os.environ.get('COMPUTERNAME', '?')}",
                "supervisor": was,
                "workflows": outcomes,
            },
        ),
    )
    print(json.dumps(read_json(run_dir / "status.json"), ensure_ascii=False))
    return 1 if cleanup["cleanup_errors"] else 0


# --- command line ----------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="farm_build.py",
        description=__doc__.split("\n\n")[0],
        allow_abbrev=False,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def runs(p):
        p.add_argument(
            "--runs-dir",
            help="run records root (default: HARMONIC_FARM_RUNS, "
            r"else %%LOCALAPPDATA%%\ha-farm\runs); must be outside every worktree",
        )

    run = sub.add_parser(
        "run", help="launch a farm build of the pushed HEAD", allow_abbrev=False
    )
    run.add_argument(
        "targets",
        nargs="+",
        metavar="TARGET",
        help="doit task selections (comma-separated lists allowed)",
    )
    run.add_argument(
        "--display-name",
        required=True,
        help="owner/session plus reason; nonblank, single-line, <=160 characters",
    )
    run.add_argument(
        "--leaf-timeout",
        type=int,
        required=True,
        metavar="MINUTES",
        help="per-attempt budget for each farm leaf, 1-180 minutes",
    )
    run.add_argument(
        "--force-cache-refresh",
        action="append",
        default=[],
        metavar="LABELS",
        help="rebuild and overwrite these exact cache-keyed leaves (repeatable)",
    )
    run.add_argument(
        "--force-cache-refresh-reason",
        metavar="TEXT",
        help="required with --force-cache-refresh; same rules as --display-name",
    )
    run.add_argument(
        "--tag", default="run", help="label recorded with the run (default: run)"
    )
    run.add_argument(
        "--worktree",
        default=str(REPO_ROOT),
        help="checkout whose pushed HEAD is built (default: this one)",
    )
    run.add_argument(
        "--pool-home",
        help="solidworks-pool checkout (default: "
        "SOLIDWORKS_POOL_HOME, else ../solidworks-pool)",
    )
    run.add_argument("--watch", action="store_true", help="keep watching after launch")
    run.add_argument("--poll-seconds", type=float, default=15)
    runs(run)
    for name, help_text in (
        ("status", "print one run's status as JSON"),
        ("watch", "follow a run to its end (exit 0/20/21/22)"),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("run", help="run id, or a tag (its newest run)")
        if name == "watch":
            command.add_argument("--poll-seconds", type=float, default=15)
        runs(command)
    listing = sub.add_parser("list", help="one JSON line per run, newest first")
    listing.add_argument("--tag")
    listing.add_argument("--state", choices=(*WATCH_EXIT_CODES, "running"))
    listing.add_argument("--max-age-hours", type=int)
    runs(listing)
    stop = sub.add_parser("cancel", help="stop a run and cancel its farm leaves")
    stop.add_argument("run", help="run id, or a tag (its newest run)")
    stop.add_argument("--why", required=True)
    stop.add_argument("--binding-wait-seconds", type=int, default=30)
    runs(stop)
    for internal in ("_spawn", "_supervise", "_build"):
        sub.add_parser(internal).add_argument("run_dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    options = _parser().parse_args(argv)
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            stream.reconfigure(encoding="utf-8")
    command = options.command
    if command == "_spawn":
        return spawn_supervisor(options.run_dir)
    if command == "_supervise":
        return supervise(options.run_dir)
    if command == "_build":
        return build_main(options.run_dir)
    try:
        root = runs_root(options.runs_dir)
        if command == "run":
            run_dir = launch(options)
            print(f"farm-run started {run_dir.name} {run_dir}", flush=True)
            code = await_preflight(run_dir)
            if code != 0 or not options.watch:
                if code != 0:
                    print(json.dumps(run_status(run_dir), ensure_ascii=False))
                return code
            return watch(run_dir, options.poll_seconds)
        if command == "list":
            list_runs(root, options.tag, options.state, options.max_age_hours)
            return 0
        run_dir = select_run(root, options.run)
        if command == "status":
            print(json.dumps(run_status(run_dir), ensure_ascii=False))
            return 0
        if command == "watch":
            return watch(run_dir, options.poll_seconds)
        return cancel(run_dir, options.why, options.binding_wait_seconds)
    except LaunchError as problem:
        print(f"farm-run {command}: {problem}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
