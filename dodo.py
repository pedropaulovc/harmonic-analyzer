r"""The whole pipeline as one doit graph: build -> verify -> export -> release.

doit decides *whether* each part/assembly is stale (md5 content hash, immune to
git/worktree mtime churn); the refresh primitive makes the assembly recipe cheap.

A ``.SLDASM`` is a thin reference layer over its part files, so when only a
referenced ``.SLDPRT`` changed, an assembly is REFRESHED (reopen + per-config
ForceRebuild3 + gates + in-place Save3 -- seconds) instead of rebuilt from
scratch (re-insert + re-mate ~122 components -- ~500 s). The recipe escalates to a
FULL rebuild (+ any post-assembly hooks) when the assembly script / _common.py / a
hook changed, or the target is missing. A refresh that hits a dangling mate, free
DOF, or interference FAILS LOUD (non-zero exit, .SLDASM untouched); recover with
the full escape below.

Task groups (the prefix says whether SolidWorks is required):

  part:<stem>        build one part            (COM -- needs SolidWorks)
  assembly:<stem>    build/refresh one assembly (COM)
  drawing:<stem>     build one manufacturing drawing (COM)
  verify:<suite>     soundness/subsystems/kinematics gates (COM)
  check:<name>       math/config/graph/nameplate/recipe gates (NO SolidWorks)
  export             neutral STEP/STL/glTF/scene export (COM)
  release            cut a tagged GitHub release (COM + gh; opt-in)
  build              EVERY part + assembly + EVERY gate -- the one safe entry
  build_bare         parts + assemblies only -- a quick rebuild

COM serialization (the single SolidWorks STA seat) is enforced at RUNTIME by a
cross-process file lock (``_com_seat`` / ``filelock``), NOT by fake ``task_dep``
edges: every COM subprocess acquires the machine-global seat lock before it drives
SolidWorks and releases it after, so at most one COM task touches the seat at a
time even under ``doit -n N`` -- while the SolidWorks-free ``check:*`` tasks (which
never take the lock) fan out in parallel. The task graph therefore carries only
REAL dependency edges (an assembly's file_dep on its parts, verify/export on the
built ``.SLDASM``, release on export+verify+preflight), so the DAG reads true and a
COM failure no longer skips unrelated downstream COM tasks as a spine side effect.

Install (this repo is a uv project -- pyproject.toml + uv.lock at the root)::

    git submodule update --init  # ./SolidworksMCP-python (COM adapter, branch personal)
    uv sync                      # core deps + pytest, from the lockfile

Run through uv (SolidWorks already open for the COM tasks)::

    uv run python -m doit                       # = `build`: every part + assembly + every gate
    uv run python -m doit -n 4                  # same, fanning out the SolidWorks-free checks
    uv run python -m doit build_bare            # quick: parts + assemblies only, no gates
    uv run python -m doit assembly:paper_drive  # just that assembly + its stale prereqs
    uv run python -m doit part:summing_lever    # just that part
    uv run python -m doit verify:soundness      # one SW gate; check:math one offline gate
    uv run python -m doit export                # neutral STEP/STL/glTF/scene export
    uv run python -m doit release               # cut the next vNN release (opt-in)
    uv run python -m doit list --all            # every task
    uv run python -m doit clean                 # remove targets (+ wipe png/<asm>)

Full-rebuild escape (idiomatic doit -- a missing target forces a run, and
build_or_refresh takes the FULL branch when the target is absent)::

    del cad\out\sldasm\paper-drive.SLDASM
    %DOIT% forget assembly:paper_drive    # optional: also drop the cached hash
    %DOIT% assembly:paper_drive
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Every build/verify/export task routes its subprocess through ``_run``, which
# streams the child's stdout through this doit parent process -- and tees it to
# cad/out/logs when a log_stem is given. Build output carries non-ASCII (e.g. the
# "A ∩ B" gate labels); on Windows the parent stdout defaults to cp1252, so
# re-emitting that glyph raises UnicodeEncodeError and kills the reader (which can
# then hang the child on a full pipe). Force UTF-8 on the parent too, mirroring
# run_build (_common.py).
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")

import yaml as _yaml
from doit.dependency import CHECKERS, Dependency, JsonDB, MD5Checker
from filelock import FileLock, Timeout  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent / "cad" / "scripts"))

from _buildgraph import (  # noqa: E402
    ASSEMBLY_ORDER,
    CAD_OUT,
    POST_ASSEMBLY,
    SCRIPTS_DIR,
    all_config_files,
    artefact_for,
    config_files_of,
    data_deps_of,
    machine_family_files,
    module_deps_of,
    part_row_files,
    part_scripts,
    part_stems,
    parts_registry_files,
    references_of,
    script_for,
    stamps_part_properties,
)

import _artifact_cache as _cache  # noqa: E402  (remote build-artefact cache)
import _telemetry  # noqa: E402  (observability spine: console logging + tracing)
from _drawing_registry import (  # noqa: E402
    DRAWINGS_BY_NAME,
    PROJECT_DRWDOT,
)

REPO_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = REPO_ROOT / "cad" / "config"
# The repo-owned part template (see _common.PART_TEMPLATE -- path duplicated
# deliberately; importing _buildgraph from _common would drag graph tooling
# into every part's dep closure). A runtime input of every part build.
PART_TEMPLATE = REPO_ROOT / "cad" / "templates" / "harmonic-analyzer.PRTDOT"
# The vendored COM adapter (``solidworks_mcp``) lives in this submodule and is
# imported AT RUNTIME by _common/_assembly (e.g. the mate/plane creation glue), so
# its source is a genuine build input of every COM task -- yet it is an installed
# package, not a repo-local ``_*.py`` helper, so ``module_deps_of`` never walks it.
# Its tracked source content is folded into every COM task's recipe (see
# ``_submodule_dep``) so a submodule bump -- committed pin OR a dirty local edit --
# busts the cache key and forces a rebuild (issue #144).
SUBMODULE_SRC = REPO_ROOT / "SolidworksMCP-python" / "src" / "solidworks_mcp"

# --- COM seat: serialize SolidWorks at RUNTIME with a cross-process file lock.
#
# There is one SolidWorks STA seat, so no two COM tasks may drive it at once. The
# old approach chained every COM task into a linear ``task_dep`` *spine* (fake edges
# that made the DAG lie and let a mid-spine COM failure skip unrelated downstream COM
# work). Instead each COM subprocess now acquires a single file lock right before it
# touches SolidWorks (``_com_seat``) and releases it after. ``doit -n N`` runs COM
# tasks in separate PROCESSES (MRunner -> multiprocessing.Process, spawn on Windows),
# so the lock MUST be cross-process: ``filelock`` uses OS advisory locks
# (msvcrt/fcntl) that release automatically when the holder dies, so a killed/crashed
# build never strands the seat (no stale lockfile to clean).
#
# The lock is MACHINE-GLOBAL (default under %PROGRAMDATA%/tmp; override with
# ``HARMONIC_COM_LOCK``), so it also serializes COM across worktrees and concurrent
# ``doit`` invocations on the one seat -- the spine only serialized within a single
# invocation. NB it serializes but does NOT isolate: SolidWorks keys open documents
# by FILENAME (not path) and carries session-global state, so genuinely-independent
# concurrent builds on one machine remain unsafe. The lock is a safety belt, not a
# green light for parallel independent builds.
#
# Only the actual COM subprocess is wrapped: the remote-cache RESTORE (an Azure
# download) and STORE (upload) run OUTSIDE the lock, so cache hits stay fully
# parallel and a publish never holds the seat. The SolidWorks-free ``check:*`` tasks
# never call ``_com_seat``, so they fan out under ``-n``.
def _com_lock_path() -> Path:
    override = os.environ.get("HARMONIC_COM_LOCK")
    if override:
        return Path(override)
    base = os.environ.get("PROGRAMDATA") or tempfile.gettempdir()
    return Path(base) / "harmonic-analyzer" / "com-seat.lock"


_COM_LOCK_PATH = _com_lock_path()
_COM_HOLDER_PATH = _COM_LOCK_PATH.with_suffix(".holder")
_COM_LOCK = FileLock(str(_COM_LOCK_PATH))
# Poll interval while blocked on the seat: log who holds it this often, so a wedged
# build (e.g. a modal SolidWorks dialog on the holder) is VISIBLE instead of N
# workers sitting silently in a timeout=-1 acquire.
_COM_SEAT_POLL_S = 30.0
# Set in the environment while the seat is held (inherited by the COM subprocess via
# ``_telemetry.inject_env``): a COM build launched under doit WITHOUT it trips the
# ``_common`` guard loud -- the runtime successor to the removed spine tripwire.
_COM_SEAT_HELD_ENV = "HARMONIC_COM_SEAT"


def _read_seat_holder() -> str | None:
    try:
        return _COM_HOLDER_PATH.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _write_seat_holder(holder: str) -> None:
    try:
        _COM_HOLDER_PATH.write_text(holder, encoding="utf-8")
    except OSError:
        pass  # best-effort diagnostic only


def _clear_seat_holder(holder: str) -> None:
    try:
        if _read_seat_holder() == holder:
            _COM_HOLDER_PATH.unlink()
    except OSError:
        pass


@contextlib.contextmanager
def _com_seat(label: str):
    """Hold the single SolidWorks seat for the duration of a COM subprocess.

    Blocks until the machine-global seat lock is free, then yields with it held.
    While blocked it logs the current holder every ``_COM_SEAT_POLL_S`` so a wedged
    seat is diagnosable rather than a silent hang. Sets ``HARMONIC_COM_SEAT`` in this
    process's environment (inherited by the COM subprocess) so a COM build launched
    WITHOUT the seat trips ``_common``'s guard loud -- the runtime successor to the
    removed ``_assert_spine_complete`` tripwire. Reentrancy-safe (``filelock`` counts
    same-process acquisitions), though no COM action nests it."""
    _COM_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    holder = f"{label} pid={os.getpid()}"
    while True:
        try:
            _COM_LOCK.acquire(timeout=_COM_SEAT_POLL_S)
            break
        except Timeout:
            other = _read_seat_holder()
            _telemetry.warn(f"[com.seat] {label} waiting for the SolidWorks seat"
                            + (f" (held by {other})" if other else ""))
    _write_seat_holder(holder)
    prev = os.environ.get(_COM_SEAT_HELD_ENV)
    os.environ[_COM_SEAT_HELD_ENV] = holder
    _telemetry.event("com.seat.acquired", label=label)
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop(_COM_SEAT_HELD_ENV, None)
        else:
            os.environ[_COM_SEAT_HELD_ENV] = prev
        _clear_seat_holder(holder)
        _COM_LOCK.release()

# Drawing tasks declare only their source model as CAD input, while their code
# recipe follows the exporter's complete repo-local import closure and the full
# SolidWorks adapter submodule digest.
# Their order is derived from the source part producer for stable scheduling;
# the runtime COM-seat lock provides serialization without adding false DAG edges.
def _drawing_order() -> list[str]:
    producer_order = {stem: i for i, stem in enumerate(_seat_part_order())}
    # Assembly-sourced drawings have no part producer; schedule them after the
    # part drawings (their .SLDASM source is the last COM artefact to settle).
    fallback = len(producer_order)
    return sorted(
        DRAWINGS_BY_NAME,
        key=lambda name: (
            producer_order.get(DRAWINGS_BY_NAME[name].part, fallback),
            name,
        ),
    )


# --- Per-seat part order: diverge two cold builders so they SPLIT the work.
#
# Parts have NO inter-part deps (``_part_file_deps`` never lists another part's
# .SLDPRT), so the order in which their tasks are offered to the scheduler is free.
# Two machines cold-building in the SAME order march in lock-step, each MISSING the
# shared remote cache on the same next part and building it in parallel -- N machines
# do N x the COM work. Permuting the part order per SEAT breaks the lock-step: seat A
# climbs one way, seat B another, so by the time the slower seat reaches a part the
# faster one has usually published it (a cache HIT), and the fleet builds each part
# ~once. With the spine gone this is a best-effort SCHEDULING HINT (it orders the
# ``task_part`` yield and the ``build`` task_dep list); correctness comes from the
# seat lock and the re-probe under it (``_cached_part_action``), so an imperfectly
# honored order costs a little cache-split efficiency, never a duplicated/skipped
# build. ``filelock`` grants no FIFO fairness anyway, so strict order was never on
# offer under ``-n``. Keyed on the HOSTNAME via ``hashlib`` (stable across a seat's
# processes, distinct across seats); ``HARMONIC_BUILD_ORDER_SEED`` overrides it.
def _build_order_seed() -> str:
    return os.environ.get("HARMONIC_BUILD_ORDER_SEED") or socket.gethostname()


def _seat_part_order() -> list[str]:
    """``part_stems()`` permuted deterministically per seat (see the block above)."""
    seed = _build_order_seed()
    return sorted(part_stems(),
                  key=lambda s: hashlib.md5(f"{seed}\0{s}".encode()).hexdigest())


# --- Comment/whitespace-insensitive content hashing for cad/config/*.yaml.
#
# doit's stock MD5Checker hashes RAW FILE BYTES, so a comment-only or reflow edit
# to a SHARED config (every part lists cad/config/*.yaml as a file_dep) flips that
# file's md5 and marks EVERY dependent part stale -> a spurious full rebuild. This
# bit us once: a provenance-comment retarget in tolerances.yaml (value unchanged)
# rebuilt 75 parts. ContentChecker digests the *parsed* YAML instead -- key order
# preserved, comments and formatting discarded -- so only a real data change
# invalidates. Non-YAML deps (.py, .SLDPRT) fall through to the exact stock md5,
# so their stored state stays valid across the switch.
#
# NB: changing the checker class re-stamps every task's `checker:` field, which
# doit treats as changed -> run `doit reset-dep` once after this lands to migrate
# the db in place WITHOUT a rebuild (the on-disk artefacts are already current).
def _canonical_file_md5(file_path: str) -> str:
    """MD5 of Git-canonical content, independent of Windows checkout EOLs.

    ``core.autocrlf=true`` may materialise a tracked text blob's LF as CRLF (or a
    conflict/patch can leave a mixed file) while Git still considers the content
    unchanged. Git's text heuristic is a NUL check in the first 8 KiB; mirror that
    boundary and clean CRLF to LF before hashing. Binary inputs retain their exact
    byte digest. This avoids a subprocess per dependency on the cache hot path.
    """
    data = Path(file_path).read_bytes()
    if b"\0" not in data[:8000]:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.md5(data).hexdigest()


class ContentChecker(MD5Checker):
    """MD5Checker with two churn-immunities: it digests the PARSED form of YAML
    configs (comment-/whitespace-insensitive), and keys ``.SLDPRT``/``.SLDASM``
    artefacts on their producing task's build-input recipe rather than SolidWorks'
    volatile output bytes (build idempotency -- see ``_stable_artefact_digest``).
    Text deps are Git-EOL-canonical; binary deps remain byte-identical to
    MD5Checker."""

    @staticmethod
    def _digest(file_path: str) -> str:
        if file_path.lower().endswith((".sldprt", ".sldasm")):
            # A SolidWorks artefact's BYTES are not idempotent: saving an assembly
            # rewrites volatile save metadata into every nested .SLDPRT/.SLDASM (the
            # parent-md5 cascade), so a part's bytes legitimately churn AFTER its
            # part: task -- and after a lower assembly -- recorded them. Hashing
            # those bytes marks the dependent assembly stale on EVERY build for no
            # geometry change (a no-op refresh that never reaches a fixpoint;
            # follow-up to #102). Key on the producing task's build INPUTS instead
            # (recipe, transitively), which are churn-immune and flip iff the
            # geometry's inputs change. None -> not a declared target (e.g. the
            # channel stretch-spring variants) -> stock byte md5.
            recipe = _stable_artefact_digest(file_path)
            return recipe if recipe is not None else _canonical_file_md5(file_path)
        if not file_path.endswith((".yaml", ".yml")):
            return _canonical_file_md5(file_path)
        try:
            with open(file_path, "rb") as fh:
                data = _yaml.safe_load(fh)
        except _yaml.YAMLError:
            return _canonical_file_md5(file_path)  # malformed -> build fails loud later
        canon = _yaml.safe_dump(
            data, default_flow_style=False, sort_keys=False, allow_unicode=True
        )
        return hashlib.md5(canon.encode("utf-8")).hexdigest()

    def check_modified(self, file_path, file_stat, state):
        timestamp, size, digest = state
        # mtime unchanged -> content unchanged (stock fast path).
        if file_stat.st_mtime == timestamp:
            return False
        # mtime changed: compare the CONTENT digest. (Stock MD5Checker short-
        # circuits to "modified" on a size difference here -- wrong for us, since a
        # comment edit changes the byte size while the parsed YAML is identical.)
        return digest != self._digest(file_path)

    def get_state(self, dep, current_state):
        timestamp = os.path.getmtime(dep)
        if current_state and current_state[0] == timestamp:
            return  # mtime optimization: state unchanged
        size = os.path.getsize(dep)
        return timestamp, size, self._digest(dep)


CHECKERS["content"] = ContentChecker


# --- Per-task DB checkpointing so an interrupted build resumes incrementally.
#
# doit 0.37's backends (json/dbm/sqlite3 alike) only persist .doit.db on a CLEAN
# process exit -- Dependency.close() is the sole caller of backend.dump(); set()
# merely mutates an in-memory dict (sqlite3.set() just caches + marks dirty, and
# its dump() even closes the connection). So a build killed mid-run (Ctrl-C,
# TaskStop, crash, SW hang) loses EVERY completed-part record and the next run
# rebuilds all ~71 parts from scratch (~25 min). Switching backend does not help.
#
# Fix: checkpoint after each successful task. JsonDB.dump() is a full-file rewrite
# that neither closes nor clears state, so it is safe to call repeatedly; we make
# it atomic (tmp + fsync + os.replace) so a kill mid-write can't corrupt the db,
# then call it once per task from save_success. Overhead is ~71 small writes per
# build; correctness is unchanged (same records, just flushed eagerly). Class-level
# monkeypatch -- adding this to dodo.py changes no task's file_dep, so it does not
# itself invalidate anything.
def _atomic_json_dump(self: JsonDB) -> None:
    tmp = f"{self.name}.tmp"
    with open(tmp, "w") as fh:
        fh.write(self.codec.encode(self._db))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, self.name)


JsonDB.dump = _atomic_json_dump

_orig_save_success = Dependency.save_success


def _save_success_checkpoint(self: Dependency, task, result_hash=None) -> None:
    _orig_save_success(self, task, result_hash)
    self.backend.dump()  # durable checkpoint -> interrupted build resumes here


Dependency.save_success = _save_success_checkpoint

DOIT_CONFIG = {
    "backend": "json",
    "dep_file": str(CAD_OUT / ".doit.db"),
    # Hash the PARSED form of cad/config/*.yaml so comment/whitespace-only edits to
    # a shared config no longer invalidate every dependent part (see ContentChecker
    # above). Non-YAML deps keep stock md5 behaviour.
    "check_file_uptodate": "content",
    # `build` is the one fully-safe entry point (parts + assemblies + every
    # gate). `build_bare` is the quick parts+assemblies rebuild; export/release
    # are opt-in.
    "default_tasks": ["build"],
}


def _sldprt(stem: str) -> str:
    return str(artefact_for(SCRIPTS_DIR / f"build_{stem}.py").resolve())


def _sldasm(stem: str) -> str:
    return str(artefact_for(SCRIPTS_DIR / f"build_{stem}_assembly.py").resolve())


def _part_execution_token(stem: str) -> str:
    """Stable identity of the exact part artefact built or restored.

    Recipe digests intentionally ignore SolidWorks persistent-reference IDs for
    cross-seat cache stability. Drawings need the orthogonal identity signal: a
    same-recipe rebuild may replace the model identity even when the recipe digest
    is unchanged. Hashing the freshly built/restored bytes makes repeated restores
    of the SAME cached part converge on the same token, while another build under
    that recipe gets a different token and correctly invalidates its drawings.
    """
    name = stem.replace("_", "-")
    return str((CAD_OUT / "sldprt" / f".{name}.execution").resolve())


def _assembly_execution_token(stem: str) -> str:
    """Stable identity of the exact assembly artefact built or restored.

    Assembly rebuild state and mate references are persisted against the exact
    child CAD identities, not merely their recipes. Propagating this token to a
    parent prevents a same-recipe subassembly from being mixed with a parent that
    was saved against another SolidWorks identity (issue #301).
    """
    name = stem.replace("_", "-")
    return str((CAD_OUT / "sldasm" / f".{name}.execution").resolve())


def _stamp_execution(artefact: str, token_path: str) -> None:
    token = Path(token_path)
    source = Path(artefact)
    token.parent.mkdir(parents=True, exist_ok=True)
    identity = hashlib.sha256(source.read_bytes()).hexdigest()
    token.write_text(identity + "\n", encoding="utf-8")


def _stamp_part_execution(stem: str) -> None:
    _stamp_execution(_sldprt(stem), _part_execution_token(stem))


def _stamp_assembly_execution(stem: str) -> None:
    _stamp_execution(_sldasm(stem), _assembly_execution_token(stem))


class _ExecutionIdentityTracker:
    """Require a valid exact-artefact identity token before treating a task as current.

    Returning false makes doit execute the normal cache action once. A hit restores
    the existing artefact, then the action stamps its exact identity. This migrates
    legacy part tasks and introduces assembly tokens without a cache epoch bump.
    """

    def __init__(self, token_path: str):
        self.token_path = token_path

    def __call__(self, task, values) -> bool:
        # doit injects these arguments by their RESERVED NAMES. Keep `task` and
        # `values` even though this validator does not otherwise need them.
        del task, values
        try:
            identity = Path(self.token_path).read_text(encoding="utf-8").strip()
        except OSError:
            return False
        return re.fullmatch(r"[0-9a-f]{64}", identity) is not None


def _stage_name(label: str) -> str:
    """The telemetry ``service.name`` (Aspire "resource" column) a subprocess with
    this doit task ``label`` should advertise, so a trace groups by PIPELINE STAGE
    -- part-build / assembly-build / verify-<suite> / check-<gate> / export / release
    -- instead of every process reading the same umbrella name. Injected into the
    child env as ``OTEL_SERVICE_NAME`` (the standard OTel var) by :func:`_exec`, so
    the child is labelled the moment it imports ``_telemetry``."""
    if label.startswith("part:"):
        return "part-build"
    if label.startswith(("assembly:", "FULL build", "REFRESH", "hook ")):
        return "assembly-build"
    if label.startswith(("drawing:", "drawing ")):
        return "drawing-export"
    if label.startswith("verify "):
        return "verify-" + label.split(None, 2)[1]
    if label.startswith("check "):
        return "check-" + label.split(None, 2)[1]
    if label.startswith("cut release") or label == "release":
        return "release"
    if label.startswith("export"):
        return "export"
    return "harmonic-analyzer"


def _exec(cmd: list[str], label: str, log_stem: str | None = None) -> None:
    """Run a subprocess from the repo root; raise on non-zero (fail-loud). The
    subprocess CONTINUES the active span via the injected ``TRACEPARENT`` and is
    labelled with its pipeline stage via ``OTEL_SERVICE_NAME`` (:func:`_stage_name`).

    This is the span-less core of :func:`_run`. The cached part/assembly actions open
    their OWN ``task`` span (so the cache decision + build share one trace) and call
    ``_exec`` directly; every other task goes through ``_run``.

    With ``log_stem`` the subprocess output is teed to ``cad/out/logs/<stem>.log``
    AND echoed live to the console, so a release can ship the part/assembly/gate
    build logs as an artefact (cut_release.py collects ``cad/out/logs``). Without
    it, output is inherited straight to the terminal -- the cheap path for the
    non-release happy path. Decode the pipe as UTF-8 (errors=replace) so the gate
    labels' non-ASCII glyphs survive on a cp1252 Windows console."""
    _telemetry.info(f">> {label}: {' '.join(cmd)}")
    env = _telemetry.inject_env()
    env["OTEL_SERVICE_NAME"] = _stage_name(label)
    if log_stem is None:
        rc = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env).returncode
    else:
        LOGS.mkdir(parents=True, exist_ok=True)
        with (LOGS / f"{log_stem}.log").open("w", encoding="utf-8") as fh:
            fh.write(f">>  {label}: {' '.join(cmd)}\n")
            fh.flush()
            proc = subprocess.Popen(
                cmd, cwd=str(REPO_ROOT), env=env, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace", bufsize=1)
            assert proc.stdout is not None
            for line in proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                fh.write(line)
                fh.flush()
            rc = proc.wait()
    if rc:
        raise RuntimeError(f"{label} failed (exit {rc})")


def _run(cmd: list[str], label: str, log_stem: str | None = None,
         com: bool = False) -> None:
    """Open a ``task <label>`` span and run the subprocess inside it (see
    :func:`_exec`). One span per task action, NAMED for the doit task
    (``task part:cone_gear``) so the trace reads as the task itself; the build
    subprocess CONTINUES this span (via the injected TRACEPARENT) instead of adding a
    duplicate root layer under it.

    ``com=True`` marks a SolidWorks-touching task: the subprocess runs holding the
    single COM seat (``_com_seat``), so it is serialized against every other COM task
    on the machine. SolidWorks-free tasks (the ``check:*`` gates) pass ``com=False``
    and never take the lock, so they fan out under ``-n``."""
    with _telemetry.span(f"task {label}", label=label, cmd=" ".join(cmd)):
        with (_com_seat(label) if com else contextlib.nullcontext()):
            _exec(cmd, label, log_stem)


# --- Per-script helper dependencies, computed from each build script's REAL
# transitive imports (``module_deps_of``) instead of a blanket "every ``_*.py`` is
# a dep of every build". A leaf part that imports only ``_common`` no longer
# rebuilds when an assembly-only helper (``_assembly``) or an unrelated one
# (``_gear``) changes; the closure follows imports (``_chain_link -> _chain ->
# _common``; ``_common -> _config``) so it never under-invalidates as long as a
# script imports what it uses. (Excludes _buildgraph.py: the build-GRAPH helper
# imported here, not a geometry input.)
#
# The YAML data layer is now a FINE-GRAINED dep: each part/assembly depends on
# ONLY the cad/config FILES it actually reads (``config_files_of`` -> static
# analysis of the ``_config.<accessor>`` calls across the script's import closure;
# see _buildgraph). machine.yaml and parts.yaml are split per-subsystem / per-part
# so the granularity is sub-file: a gear part that reads only
# machine("gear_train", ...) depends on machine/gear_train.yaml alone, so a
# channels.active_count edit (machine/channels.yaml) skips it; editing ONE part's
# registry row rebuilds only that part; and the 98 KB narrative dimensions.yaml
# (read by NO part) drops out of every part. Conservative by construction -- any
# unclassifiable ``_config`` use falls back to the whole config (the "**" token)
# -- so it can only ever over-rebuild, never skip a real change.
#
# ``_CONFIG_YAMLS`` (every config file, recursive) is retained only for the
# offline ``check:math`` / ``check:config`` gates, which audit the config broadly
# and must stay conservative (a gate that fails to re-run is worse than one that
# re-runs).
_CONFIG_YAMLS = all_config_files()


def _helper_deps(script) -> list[str]:
    """This build script's transitive ``_*.py`` helper imports (resolved paths)."""
    return module_deps_of(script if isinstance(script, Path) else Path(script))


def _expand_parts_token(stem: str | None, kind: str | None, script: Path) -> list[str]:
    """Per-task expansion of the ``"parts/*"`` registry token (the dynamic part
    name in ``_common.part_properties``):

      * a PART stamps only its OWN row -> parts/<dashed-stem>.yaml + _defaults
        (editing one row rebuilds one part);
      * an ASSEMBLY that stamps in-script (only build_channel_assembly, for its
        stretched springs) depends on the rows of the parts it references (a
        superset of the rows it stamps -- conservative); a non-stamping assembly
        needs NO parts row (a referenced part's row edit rebuilds that PART, whose
        new .SLDPRT triggers the assembly REFRESH);
      * any other caller (e.g. an offline check) -> the whole registry.
    """
    if kind == "part" and stem is not None:
        return part_row_files(stem.replace("_", "-"))
    if kind == "assembly" and stem is not None:
        if not stamps_part_properties(script):
            return []
        files: set[str] = set()
        defaults = CONFIG_DIR / "parts" / "_defaults.yaml"
        if defaults.exists():
            files.add(str(defaults.resolve()))
        for ref in references_of(stem):
            files.update(part_row_files(ref.replace("_", "-")))
        return sorted(files)
    return parts_registry_files()


def _expand_title_block_token(kind: str | None, script: Path) -> list[str]:
    """Per-task expansion of the ``"title_block"`` token (the TOL_* stamping in
    ``_common.part_properties``): every part stamps the title-block tolerance
    properties, as does an assembly that stamps in-script (build_channel_assembly,
    for its stretched springs) -> title_block.yaml; a NON-stamping assembly drops
    it (a title-block edit re-stamps the parts, whose shifted digests REFRESH the
    assembly -- keeping it in the assembly recipe would escalate to a spurious
    FULL rebuild). Any other caller keeps the dep, conservatively."""
    if kind == "assembly" and not stamps_part_properties(script):
        return []
    return [str((CONFIG_DIR / "title_block.yaml").resolve())]


def _config_deps(script, stem: str | None = None, kind: str | None = None) -> list[str]:
    """The cad/config FILES this build script actually reads (fine-grained;
    conservative whole-config fallback on any unclassifiable ``_config`` use).

    Expands the tokens from ``config_files_of`` to concrete paths, narrowing the
    ``"parts/*"`` registry token to the task's own rows (see _expand_parts_token)
    and the ``"title_block"`` token to stamping tasks only
    (_expand_title_block_token).
    """
    script = script if isinstance(script, Path) else Path(script)
    tokens = config_files_of(script)
    if "**" in tokens:
        return all_config_files()
    out: set[str] = set()
    for tok in tokens:
        if tok == "machine/*":
            out.update(machine_family_files())
        elif tok == "parts/*":
            out.update(_expand_parts_token(stem, kind, script))
        elif tok == "title_block":
            out.update(_expand_title_block_token(kind, script))
        else:
            out.add(str((CONFIG_DIR / tok).resolve()))
    return sorted(out)

# --- Stamp files: the verify:/check: gates produce no CAD artefact, so a stamp
# under cad/out/reports/ is their doit ``target``. That makes each gate
# incremental (re-runs only when a file_dep changes) and individually
# addressable, exactly like a part/assembly target.
REPORTS = CAD_OUT / "reports"
# Per-task build/verify logs (parts, assemblies, gates), teed by _run when a
# log_stem is passed; cut_release.py folds these into the release bundle so a
# release ships the logs that produced it. Gitignored (cad/out/logs/).
LOGS = CAD_OUT / "logs"
VERIFY_PY = (SCRIPTS_DIR / "verify.py").resolve()
# Verify/preflight gate logic that is NOT on any assembly's build closure (so it
# does not ride a .SLDASM digest) -> a direct file_dep of verify:/preflight tasks.
POSTBUILD_PY = (SCRIPTS_DIR / "_assembly_postbuild.py").resolve()
EXPORT_PY = (SCRIPTS_DIR / "export_models.py").resolve()
RELEASE_PY = (SCRIPTS_DIR / "cut_release.py").resolve()
PREFLIGHT_PY = (SCRIPTS_DIR / "preflight_release.py").resolve()

# The gate suites, by SolidWorks-dependence -- the single source of truth for the
# verify:/check: task names (reused by build + release so a new gate is wired in
# one place).
_VERIFY_NAMES = ("soundness", "kinematics")   # need SW (spine); subsystems retired
# Offline checks REQUIRED on every build/release (fast, high-value):
_CHECK_NAMES = ("math", "config", "graph", "nameplate", "recipe", "cache", "telemetry",
                "watchdog", "freshness", "flagonly", "partiso")
# Offline checks that are OPT-IN only (runnable via `doit check:<name>` but NOT
# depended on by `build`/`release`). ``verify_telemetry`` drives the real gates
# through a mock SolidWorks to pin span SHAPE (~20-30 s, ~20x the other offline
# checks) and has never caught a product defect -- so it is off the every-build
# required path. Union of both MUST match task_check's specs keys.
_OPTIONAL_CHECK_NAMES = ("verify_telemetry",)


def _run_stamped(cmd: list[str], label: str, stamp: str, com: bool = False) -> None:
    """Run a gate subprocess; on success write its stamp target. _run raises on
    non-zero, so a failed gate never writes a stamp (stays stale -> re-runs).
    ``com=True`` runs it holding the COM seat (SolidWorks ``verify:*``/preflight);
    the offline ``check:*`` gates pass ``com=False`` and stay parallel."""
    _run(cmd, label, log_stem=Path(stamp).stem, com=com)
    Path(stamp).parent.mkdir(parents=True, exist_ok=True)
    Path(stamp).write_text(f"{label}\n", encoding="utf-8")


def _write_stamp(label: str, stamp: str) -> None:
    """Write a dependency-aggregation stamp after all child gates succeeded."""
    Path(stamp).parent.mkdir(parents=True, exist_ok=True)
    Path(stamp).write_text(f"{label}\n", encoding="utf-8")


def _rel_tag(f: str) -> str:
    """Repo-relative, ``/``-normalised path tag for a recipe member, so
    ``_digest_files`` is LOCATION-INDEPENDENT: identical sources checked out under
    different roots (two SolidWorks seats, CI vs a workstation) hash the same.
    This matters because the recipe digest now feeds the cross-machine REMOTE CACHE
    KEY via ``_stable_artefact_digest`` -> an absolute tag would shift every
    assembly's key per checkout path and silently defeat cross-machine hits.
    Falls back to the basename for a path outside the repo (none today; defensive)."""
    try:
        return Path(f).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return os.path.basename(f)


def _digest_files(files: list[str]) -> str:
    """md5 over the *content* of each file (sorted, repo-relative-name-tagged) --
    the recipe fingerprint shared by _RecipeTracker (the run/skip uptodate),
    build_or_refresh (the FULL/REFRESH decision), and the remote cache key, so they
    never disagree. Tags are repo-relative (``_rel_tag``) so the digest is identical
    across checkout roots -- required for cross-machine cache hits.

    YAML configs are folded in by their PARSED content (ContentChecker._digest),
    exactly like the file_dep checker -- so a comment/whitespace-only edit to a
    shared cad/config/*.yaml doesn't force a spurious assembly FULL rebuild, while
    a real placement-value change (which needs a re-insert) still does."""
    h = hashlib.md5()
    for tag, f in sorted((_rel_tag(f), f) for f in files):
        h.update(tag.encode())
        try:
            h.update(ContentChecker._digest(f).encode())
        except OSError:
            h.update(b"<missing>")
    return h.hexdigest()


# --- SolidworksMCP-python submodule: a runtime build input of EVERY COM task.
#
# ``_common``/``_assembly`` import ``solidworks_mcp`` (the vendored COM adapter) at
# runtime for the mate/plane/feature creation glue, so its source is as much a part
# of a .SLDPRT/.SLDASM's recipe as ``_common.py`` -- but it is an INSTALLED package,
# not a repo-local ``_*.py`` helper, so ``module_deps_of`` (which walks only local
# ``_*.py`` imports) never included it. That left BOTH the local staleness digest
# AND the remote cache key blind to a submodule bump: bumping it left every COM
# task "up-to-date" and served stale cross-machine cache hits (issue #144).
#
# Fix: fold the submodule's tracked SOURCE content into every COM task's recipe via a
# synthetic file_dep whose CONTENT is a content-hash of the src tree. Hashing the tree
# (not just ``git rev-parse HEAD``) also catches a dirty/uncommitted submodule edit.
# One synthetic dep -- instead of the ~100 source files -- keeps the per-task dep set
# (and thus every cache-key / _digest_files fold) O(1), not a hundred md5s per COM
# task. The dep is added ONLY in the COM dep builders (``_part_file_deps`` /
# ``_recipe_files``), so the SolidWorks-free ``check:*`` tasks -- which never touch
# COM -- stay off it.
#
# THREE tiers (the over-rebuild fix): DRAWING tasks fold the WHOLE tree
# (``_submodule_dep`` -> ``_submodule_digest``); ASSEMBLY recipes fold the tree MINUS
# drawing.py (``_submodule_assembly_dep`` -> ``_submodule_assembly_digest``); PART
# recipes fold the tree MINUS {assembly.py, motion.py, drawing.py}
# (``_submodule_part_dep`` -> ``_submodule_part_digest``). So a bump touching only
# assembly.py/motion.py rebuilds the 8 assemblies but leaves all ~100 parts cached, and
# a bump touching only drawing.py rebuilds just the (few) drawing tasks. Every exclusion
# is SAFE because the excluded module is never CALLED by that tier's build scripts --
# enforced loud by ``check:partiso`` (test_part_isolation.py); see the exclusion sets
# below.
_SUBMODULE_DIGEST_FILE = REPORTS / ".solidworks-mcp-submodule.digest"
_SUBMODULE_ASSEMBLY_DIGEST_FILE = REPORTS / ".solidworks-mcp-submodule-assembly.digest"
_SUBMODULE_PART_DIGEST_FILE = REPORTS / ".solidworks-mcp-submodule-part.digest"
_SUBMODULE_DIGEST: str | None = None
_SUBMODULE_ASSEMBLY_DIGEST: str | None = None
_SUBMODULE_PART_DIGEST: str | None = None
_SUBMODULE_DEP_PATH: str | None = None
_SUBMODULE_ASSEMBLY_DEP_PATH: str | None = None
_SUBMODULE_PART_DEP_PATH: str | None = None

# THREE recipe-digest tiers over the submodule tree, so a bump to a module only some
# COM tasks reach doesn't rebuild the ones that can't. Each exclusion is proven from
# repo-local code and ENFORCED by test_part_isolation.py (``check:partiso``), which
# fails loud if a build script ever imports a module its tier excludes:
#
#   * DRAWING tasks fold the WHOLE tree (``_submodule_digest``).
#   * ASSEMBLY recipes fold the tree MINUS ``drawing.py`` (``_submodule_assembly_digest``)
#     -- see ``_ASSEMBLY_DIGEST_EXCLUDE_FILES``.
#   * PART recipes fold the tree MINUS {assembly.py, motion.py, drawing.py}
#     (``_submodule_part_digest``) -- see ``_PART_DIGEST_EXCLUDE_FILES``.
#
# Why each file drops out of a tier:
#   * assembly.py / motion.py -- the assembly+motion COM path. Excluded from the PART
#     digest only. They ARE loaded transitively (PyWin32Adapter mixes them in), but a
#     part only ever CALLS sketch/feature/export methods -- never an assembly/motion
#     method -- so their content can't change a part's geometry. Assemblies DO call
#     them, so they stay in the ASSEMBLY (and drawing) digest.
#   * drawing.py -- the ``IDrawingDoc`` helper set. Excluded from BOTH the part AND
#     assembly digests, because it is a stronger case than assembly/motion: it is NOT
#     even mixed into PyWin32Adapter (it is standalone module-level functions), so
#     nothing in a part OR assembly build graph imports it -- ONLY a ``draw_*`` drawing
#     script does. A drawing.py edit therefore rebuilds only the (few) drawing tasks,
#     never the ~100 parts or ~8 assemblies. This matches the module's own docstring
#     claim ("excluded from every part *and* assembly cache key"). Drawing tasks keep
#     folding it via the full ``_submodule_dep`` (task_drawing), so their recipe still
#     tracks it.
#
# CONSERVATIVE elsewhere: everything NOT named here (base, com_variant, sketch, feature,
# sw_type_info, pywin32_adapter, factory, AND the MCP-server surface tools/agents/ui/
# server*.py) stays in every digest -- a real shared-helper change still rebuilds parts.
# The MCP-server surface is deliberately KEPT (codex #191): excluding it would rest on a
# "not-REACHED through the package's own import graph" claim the repo-local guard cannot
# verify (base.py could start importing solidworks_mcp.tools), so we accept a rare
# over-rebuild rather than risk a stale part. drawing.py is different: its exclusion
# rests on "not-IMPORTED by any part/assembly build script", which IS repo-local
# checkable (check:partiso scans the transitive import closure of every part AND
# assembly script).
#
# Tags are PACKAGE-relative (relative to ``solidworks_mcp/``), so the module name is
# just ``solidworks_mcp.`` + the dotted tag -- ``test_part_isolation.py`` derives its
# forbidden-import sets straight from these.
#
# NOTE: adding drawing.py here shifts every PART and ASSEMBLY recipe/cache key once
# (a one-time migration); the build self-heals over one run, or ``doit reset-dep``
# migrates the ``.doit.db`` in place without a rebuild.
_ASSEMBLY_DIGEST_EXCLUDE_FILES = frozenset({
    "adapters/solidworks/drawing.py",
})
_PART_DIGEST_EXCLUDE_FILES = _ASSEMBLY_DIGEST_EXCLUDE_FILES | frozenset({
    "adapters/solidworks/assembly.py",
    "adapters/solidworks/motion.py",
})


def _submodule_src_files() -> list[Path]:
    """Every ``.py`` under the submodule's ``src/solidworks_mcp`` tree (sorted).
    Empty when the submodule isn't checked out -- the digest degrades to a stable
    empty-tree hash rather than crashing the build graph."""
    if not SUBMODULE_SRC.is_dir():
        return []
    return sorted(SUBMODULE_SRC.rglob("*.py"))


def _submodule_rel_tag(f: Path) -> str | None:
    """The PACKAGE-relative path tag (relative to ``solidworks_mcp/``) used to test a
    file against the exclusion sets, or None if it's outside the package tree. Matching
    on this tag keeps the classification identical across checkout roots / REPO_ROOT."""
    try:
        return f.resolve().relative_to(SUBMODULE_SRC.resolve()).as_posix()
    except ValueError:
        return None


def _is_part_relevant_submodule_file(f: Path) -> bool:
    """False for the assembly/motion COM modules AND drawing.py (all dropped from the
    PART recipe digest); every other submodule file stays in."""
    rel = _submodule_rel_tag(f)
    if rel is None:
        return True  # outside the package tree (defensive) -> keep it in the digest
    return rel not in _PART_DIGEST_EXCLUDE_FILES


def _is_assembly_relevant_submodule_file(f: Path) -> bool:
    """False only for drawing.py (dropped from the ASSEMBLY recipe digest -- no
    assembly build script imports it); assembly.py/motion.py and everything else stay
    in, since assemblies DO call the assembly/motion COM path."""
    rel = _submodule_rel_tag(f)
    if rel is None:
        return True
    return rel not in _ASSEMBLY_DIGEST_EXCLUDE_FILES


def _digest_submodule_files(files: list[Path]) -> str:
    """Fold a list of submodule files into one md5, each keyed by its REPO-RELATIVE
    tag (``_rel_tag``) + Git-EOL-canonical content md5 -- identical across checkout
    roots and Windows checkout materialisations, exactly like ``_digest_files``, so
    the derived cache key is cross-machine stable."""
    h = hashlib.md5()
    for f in files:
        h.update(_rel_tag(str(f)).encode())
        h.update(_canonical_file_md5(str(f)).encode())
    return h.hexdigest()


def _submodule_digest() -> str:
    """Content fingerprint of the WHOLE submodule source tree (DRAWING-task digest --
    the only tier that folds drawing.py), memoized (the tree is static within a run)."""
    global _SUBMODULE_DIGEST
    if _SUBMODULE_DIGEST is None:
        _SUBMODULE_DIGEST = _digest_submodule_files(_submodule_src_files())
    return _SUBMODULE_DIGEST


def _submodule_assembly_digest() -> str:
    """Content fingerprint of the ASSEMBLY-relevant submodule files (the whole tree
    MINUS drawing.py, which no assembly build imports), memoized. So a drawing.py edit
    leaves this digest -- and thus every assembly's recipe -- unchanged."""
    global _SUBMODULE_ASSEMBLY_DIGEST
    if _SUBMODULE_ASSEMBLY_DIGEST is None:
        files = [f for f in _submodule_src_files() if _is_assembly_relevant_submodule_file(f)]
        _SUBMODULE_ASSEMBLY_DIGEST = _digest_submodule_files(files)
    return _SUBMODULE_ASSEMBLY_DIGEST


def _submodule_part_digest() -> str:
    """Content fingerprint of the PART-RELEVANT submodule files only (drops the
    assembly/motion + MCP-server modules parts never reach), memoized. So an
    assembly-only submodule bump leaves this digest -- and thus every part's recipe
    -- unchanged, instead of rebuilding all ~100 parts."""
    global _SUBMODULE_PART_DIGEST
    if _SUBMODULE_PART_DIGEST is None:
        files = [f for f in _submodule_src_files() if _is_part_relevant_submodule_file(f)]
        _SUBMODULE_PART_DIGEST = _digest_submodule_files(files)
    return _SUBMODULE_PART_DIGEST


def _write_digest_sidecar(path: Path, digest: str) -> str:
    """Write ``digest`` to ``path`` write-only-if-changed (so its mtime -- and doit's
    stat fast-path -- stays stable across no-op runs; a bump flips the content, hence
    the mtime, hence every dependent COM task). Returns the resolved path string."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        current = path.read_text(encoding="utf-8").strip()
    except OSError:
        current = None
    if current != digest:
        path.write_text(digest + "\n", encoding="utf-8")
    return str(path.resolve())


def _submodule_dep() -> str:
    """Path to the synthetic file_dep tracking the WHOLE submodule for DRAWING tasks
    (``task_drawing``): a generated sidecar whose CONTENT is ``_submodule_digest()``.
    This is the only tier that folds drawing.py, so a drawing.py edit rebuilds drawings
    but nothing else. Its repo-relative path tag + machine-independent content make the
    resulting cache key identical across machines. Memoized to one write-check per
    process (called on every staleness probe)."""
    global _SUBMODULE_DEP_PATH
    if _SUBMODULE_DEP_PATH is None:
        _SUBMODULE_DEP_PATH = _write_digest_sidecar(
            _SUBMODULE_DIGEST_FILE, _submodule_digest())
    return _SUBMODULE_DEP_PATH


def _submodule_assembly_dep() -> str:
    """Path to the synthetic file_dep tracking the ASSEMBLY-relevant submodule slice
    (whole tree MINUS drawing.py) for ASSEMBLY recipes (``_recipe_files`` /
    ``_assembly_file_deps``): a separate sidecar whose CONTENT is
    ``_submodule_assembly_digest()``. Distinct from ``_submodule_dep`` so a drawing.py
    edit flips the drawing-task sidecar but leaves this one (and the ~8 assemblies)
    untouched. Memoized to one write-check per process."""
    global _SUBMODULE_ASSEMBLY_DEP_PATH
    if _SUBMODULE_ASSEMBLY_DEP_PATH is None:
        _SUBMODULE_ASSEMBLY_DEP_PATH = _write_digest_sidecar(
            _SUBMODULE_ASSEMBLY_DIGEST_FILE, _submodule_assembly_digest())
    return _SUBMODULE_ASSEMBLY_DEP_PATH


def _submodule_part_dep() -> str:
    """Path to the synthetic file_dep tracking the PART-RELEVANT submodule slice for
    PART recipes (``_part_file_deps``): a separate sidecar whose CONTENT is
    ``_submodule_part_digest()``. Distinct from ``_submodule_dep`` so an assembly-only
    submodule change flips the assembly sidecar (rebuilds assemblies) but leaves this
    one untouched (parts stay cached). Memoized to one write-check per process."""
    global _SUBMODULE_PART_DEP_PATH
    if _SUBMODULE_PART_DEP_PATH is None:
        _SUBMODULE_PART_DEP_PATH = _write_digest_sidecar(
            _SUBMODULE_PART_DIGEST_FILE, _submodule_part_digest())
    return _SUBMODULE_PART_DEP_PATH


# --- Remote artefact cache (opt-in, off by default; see _artifact_cache.py).
#
# A COM task's outputs are a pure function of its ``file_dep`` content, so we key a
# shared cache by that hash and download a prebuilt .SLDPRT/.SLDASM instead of
# driving SolidWorks. Keys fold each file with ContentChecker._digest -- IDENTICAL
# to the doit staleness check -- so a cache hit and "doit up-to-date" agree, and a
# comment-only YAML edit changes neither. A seat-less machine (HARMONIC_REMOTE_CACHE_MODE
# =ro) pulls; a builder (rw) pulls+pushes. Disabled (off) => zero behaviour change.
def _png_dir(stem: str) -> Path:
    return CAD_OUT / "png" / stem.replace("_", "-")


def _stl(stem: str) -> Path:
    """The part's binary STL sidecar (cad/out/stl/<dashed>.STL). save_part_and_images
    emits it next to the .SLDPRT; assembly placement reads it via stl_bbox_mm, so it
    MUST be cached alongside the part or a fresh consumer's assembly build fails on a
    missing bbox source (codex review)."""
    prt = Path(_sldprt(stem))
    return prt.parent.parent / "stl" / f"{prt.stem}.STL"


def _channel_spring_variants() -> list[Path]:
    """The dynamically-generated stretched-spring parts the channel assembly inserts
    for a non-neutral amplitude preset. They are not any task's declared target, so
    they must be enumerated by glob -- shared by _clean_assembly (remove) and the
    cache (pack), so a hit restores the components channel.SLDASM references."""
    return sorted((CAD_OUT / "sldprt").glob("channel-spring-installed-stretch*.SLDPRT"))


def _part_cache_outputs(stem: str) -> list[Path]:
    """Everything a part build emits that downstream tasks read: the .SLDPRT, its STL
    sidecar, and the render dir. Non-existent entries are skipped at pack time."""
    return [Path(_sldprt(stem)), _stl(stem), _png_dir(stem)]


def _assembly_cache_outputs(stem: str) -> list[Path]:
    """Everything an assembly build emits beyond its file_dep: the .SLDASM + renders,
    plus the per-stem extras a hit would otherwise leave missing/stale -- the channel
    stretch-spring components and the top assembly's parts BOM (which
    export_gallery_and_bom writes into cad/out, OUTSIDE _png_dir).

    Includes the `.<stem>.massprops.sha` fingerprint sidecar (refresh_assembly's
    no-save key): unlike the path-tagged recipe sidecar it is machine-independent
    content (a geometry hash), so it MUST ride the cache -- else a clean cache
    consumer restores the .SLDASM without it, the next refresh takes the missing-
    sidecar path, force-saves a no-op .SLDASM, and reintroduces the parent-md5
    cascade this whole mechanism exists to kill (codex review on #83)."""
    sldasm = Path(_sldasm(stem))
    massprops = sldasm.parent / f".{sldasm.stem}.massprops.sha"
    # The free-DOF manifest sidecar (assemblies with freed operational DOF;
    # absent otherwise, skipped at pack time). It MUST ride the cache: a clean
    # cache consumer restores the .SLDASM without it and verify:kinematics
    # would then find no drive specs to author transiently and fail loud.
    dof = sldasm.parent / f".{sldasm.stem}.dof.json"
    outs = [sldasm, _png_dir(stem), massprops, dof]
    if stem == "channel":
        outs += _channel_spring_variants()
    if stem == "harmonic_analyzer":
        outs.append(CAD_OUT / "harmonic-analyzer-bom.csv")
    return outs


def _drawing_file_deps(stem: str) -> list[str]:
    """Inputs for both doit freshness and the shared drawing-cache key.

    The part execution token carries the exact restored/built model identity. It
    prevents a drawing made against one set of SolidWorks persistent-reference IDs
    from hitting against a same-recipe part with different IDs.
    """
    spec = DRAWINGS_BY_NAME[stem]
    script = spec.script.resolve()
    runtime = [*_helper_deps(script), _submodule_dep()]
    if spec.source_kind == "assembly":
        # Assembly-sourced drawings need the same exact-identity signal as
        # part-sourced drawings. The recipe-stable .SLDASM digest preserves
        # idempotency; its execution token catches a same-recipe rebuild with
        # new PIDs so the drawing cannot restore against a foreign identity.
        source_deps: tuple[str, ...] = (
            _sldasm(spec.part), _assembly_execution_token(spec.part)
        )
    else:
        source_deps = (_sldprt(spec.part), _part_execution_token(spec.part))
    return sorted(
        {
            str(script),
            *source_deps,
            *runtime,
            *(str(path.resolve()) for path in spec.assets),
        }
    )


def _drawing_cache_outputs(stem: str) -> list[Path]:
    """Native drawing plus every derived manufacturing output it emits."""
    return [path.resolve() for path in DRAWINGS_BY_NAME[stem].outputs.values()]


def _cached_drawing_action(stem: str) -> None:
    """Restore a matched part+drawing pair or build and publish the drawing.

    Mirrors the part/assembly cache contract exactly: HIT always skips COM work;
    MISS takes the seat, re-probes after any wait, builds once, then stores outside
    the seat. The task span and console therefore state one unambiguous disposition.
    """
    spec = DRAWINGS_BY_NAME[stem]
    label = f"drawing:{stem}"
    cmd = [sys.executable, str(spec.script.resolve()), spec.artifact_stem]
    with _telemetry.span(f"task {label}", label=label) as sp:
        key = _cache_key(_drawing_file_deps(stem), label)
        outputs = _drawing_cache_outputs(stem)
        if _cache.restore(key, outputs, label):
            sp.set_attribute("cache", "hit")
            return

        with _com_seat(label):
            if _cache.restore(key, outputs, label):
                sp.set_attribute("cache", "hit-after-wait")
                return
            sp.set_attribute("cache", "miss")
            _exec(cmd, label, log_stem=f"drawing-{stem}")

        _cache.store(key, _drawing_cache_outputs(stem), label)


def _part_file_deps(script: Path, stem: str) -> list[str]:
    # The repo-owned part TEMPLATE is a runtime input of every part build
    # (_common._pin_default_part_template points the seat's default at it, so
    # NewPart inherits its document properties -- the DimXpert block-tolerance
    # get-only prefs ride it). Folding it in makes a template edit rebuild
    # every part AND shift the remote-cache key, so no seat can publish
    # template-drifted parts under a stale key.
    return [str(script.resolve()), *_helper_deps(script),
            *_config_deps(script, stem, "part"), *data_deps_of(script),
            str(PART_TEMPLATE.resolve()),
            _submodule_part_dep()]


def _assembly_file_deps(stem: str) -> list[str]:
    """Assembly recipe/CAD deps plus each referenced artefact's exact identity.

    The raw CAD targets retain the recipe-derived digest used for stable
    incrementality. The execution-token deps are orthogonal: they change only when
    a part/subassembly is built or restored as a different SolidWorks artefact, so
    doit refreshes the dependent assembly and the remote cache cannot serve an
    assembly saved against incompatible child PIDs/rebuild stamps (issue #301).
    """
    refs = references_of(stem)
    ref_targets = [_sldasm(r) if r in ASSEMBLY_ORDER else _sldprt(r) for r in refs]
    ref_identities = [
        _assembly_execution_token(r) if r in ASSEMBLY_ORDER
        else _part_execution_token(r)
        for r in refs
    ]
    return [*_recipe_files(stem), *ref_targets, *ref_identities]


def _cache_key(file_deps: list[str], label: str | None = None) -> str:
    return _cache.cache_key(file_deps, ContentChecker._digest, label)


def _cached_part_action(stem: str, script: Path) -> None:
    """Part action with a remote-cache shortcut: on a HIT the .SLDPRT (+ renders)
    are downloaded and the SolidWorks build is skipped; otherwise build, then push.
    Falls through to a normal build whenever the cache is off or errors.

    Opens the ``task part:<stem>`` span HERE (rather than in _run) so the cache
    decision and the build it gates share ONE trace: the restore/store record
    ``cache.hit``/``cache.miss``/``cache.store`` events on this span and a ``cache``
    attribute, so a miss (and why the build ran) is backtraceable from the trace,
    not just the console -- and a HIT still shows a (fast) task span instead of the
    task vanishing from the trace entirely."""
    label = f"part:{stem}"
    with _telemetry.span(f"task {label}", label=label) as sp:
        key = _cache_key(_part_file_deps(script, stem), label)
        outputs = _part_cache_outputs(stem)
        if _cache.restore(key, outputs, label):
            sp.set_attribute("cache", "hit")
            _stamp_part_execution(stem)
            return
        with _com_seat(label):
            # Re-probe under the seat: we may have blocked for the seat for minutes
            # while a peer builder published this exact part -- restore it rather than
            # rebuild (the fleet cache-split win; fable/codex review).
            if _cache.restore(key, outputs, label):
                sp.set_attribute("cache", "hit-after-wait")
                _stamp_part_execution(stem)
                return
            sp.set_attribute("cache", "miss")
            _exec([sys.executable, str(script)], label, log_stem=f"part-{stem}")
            _stamp_part_execution(stem)
        # Publish OUTSIDE the seat -- an Azure upload is network, not COM, so it must
        # not hold the seat the next task is waiting for.
        _cache.store(key, outputs, label)


def _recipe_files(stem: str) -> list[str]:
    """Files whose change forces a FULL rebuild of <stem> (re-insert/re-mate)
    rather than a part-only refresh: the assembly script, its hooks, the helper
    modules it transitively imports (``_helper_deps`` -> ``module_deps_of``, incl.
    _assembly/_transforms), and the config docs THIS assembly actually reads
    (``_config_deps``; a placement like channels.station_pitch_mm changing must
    re-insert components at new coordinates, which an in-place reload cannot do).
    The fine-grained config set means an edit to a YAML this assembly never reads
    no longer forces a spurious ~500 s FULL re-insert."""
    asm_script = script_for(stem)
    hooks = [str((SCRIPTS_DIR / h).resolve()) for h in POST_ASSEMBLY.get(stem, ())]
    # An assembly that GENERATES parts in-script (build_channel_assembly's
    # stretched springs; detected by the same stamps_part_properties call-graph
    # predicate the config tokens use) instantiates the part TEMPLATE via
    # NewPart, so the template is a direct build input: fold it in so a
    # template edit FULL-rebuilds the generated variants and shifts the
    # assembly's cache key (codex #289 -- a cached channel would otherwise
    # keep/restore springs built from the previous template). NON-generating
    # assemblies must NOT fold it: they get the template transitively through
    # their referenced parts' recipe digests (a template edit re-stamps the
    # parts -> shifted artefact digests -> REFRESH), and a direct fold would
    # escalate that refresh to a spurious ~500 s FULL rebuild.
    template = ([str(PART_TEMPLATE.resolve())]
                if stamps_part_properties(asm_script) else [])
    return [str(asm_script.resolve()), *hooks, *_helper_deps(asm_script),
            *_config_deps(asm_script, stem, "assembly"), *template,
            _submodule_assembly_dep()]


def _recipe_sidecar(stem: str) -> Path:
    """Sidecar holding the recipe digest of the last SUCCESSFUL build of <stem>,
    next to the .SLDASM (cad/out, gitignored). build_or_refresh reads it so the
    FULL/REFRESH decision needs no process-local state and stays correct under
    ``doit -n`` workers (which may run the action in a separate process)."""
    return CAD_OUT / "sldasm" / f".{stem.replace('_', '-')}.recipe.md5"


# --- Byte-churn-immune artefact digests (build idempotency; follow-up to #102).
#
# SolidWorks rewrites volatile save metadata into every nested .SLDPRT/.SLDASM when
# an assembly is saved (the parent-md5 cascade), so a part's BYTES change after its
# part: task recorded them -- and again, ~minutes later, when a higher assembly that
# also references it is saved. doit hashing those bytes marks the dependent assembly
# stale on EVERY build -> a no-op refresh that never reaches a fixpoint. We break the
# cascade by keying a .SLDPRT/.SLDASM's ContentChecker digest on the producing task's
# build INPUTS (its recipe, transitively through referenced artefacts) rather than its
# output bytes: identical to doit's own "up-to-date" semantics (a real script/config/
# referenced-part change still flips it), but immune to SolidWorks' save churn. One
# chokepoint -> doit staleness, the freshness guard (verify.py reuses this
# ContentChecker), AND the remote cache key (also ContentChecker._digest) stay in
# lockstep, and the cache now hits cross-machine despite per-build PID/save churn.
_ARTEFACT_INDEX: dict[str, tuple[str, str]] | None = None
_ARTEFACT_DIGEST_MEMO: dict[str, str] = {}


def _artefact_key(path: str) -> str:
    """Canonical lookup key for an artefact path (normcased absolute)."""
    return os.path.normcase(os.path.abspath(path))


def _artefact_index() -> dict[str, tuple[str, str]]:
    """``_artefact_key(path) -> ('part'|'assembly', stem)`` for every declared
    part/assembly target. Built once; the build graph is static within a run."""
    global _ARTEFACT_INDEX
    if _ARTEFACT_INDEX is None:
        idx: dict[str, tuple[str, str]] = {}
        for stem in part_stems():
            idx[_artefact_key(_sldprt(stem))] = ("part", stem)
        for stem in ASSEMBLY_ORDER:
            idx[_artefact_key(_sldasm(stem))] = ("assembly", stem)
        _ARTEFACT_INDEX = idx
    return _ARTEFACT_INDEX


def _stable_artefact_digest(path: str) -> str | None:
    """Recipe-derived digest of a ``.SLDPRT``/``.SLDASM`` artefact, immune to
    SolidWorks' save-metadata byte churn; ``None`` when ``path`` is not a declared
    part/assembly target (caller falls back to the stock byte md5).

    A PART's digest is its build-input recipe (script + helper closure + the config
    it reads) -- exactly the set doit/cache already track as the part task's
    file_dep. An ASSEMBLY folds its OWN recipe together with each referenced
    artefact's digest, recursively, so a leaf-part input change propagates up to
    every ancestor while a pure save-churn of an unchanged referenced part does
    not. Memoized (the graph is a static DAG within a run), so doit's many digest
    calls stay O(1) after the first compute. The recipe members are .py/.yaml, so
    this never recurses back into the artefact branch of ``ContentChecker._digest``.

    Recipe identity deliberately remains blind to a same-recipe from-scratch rebuild:
    that is what makes this digest cross-machine-stable and immune to parent-save byte
    churn. Exact ``.execution`` tokens carry the orthogonal CAD-identity signal through
    assembly ``file_dep`` and cache keys, so new PIDs refresh dependents without
    contaminating this stable digest (issue #301)."""
    key = _artefact_key(path)
    cached = _ARTEFACT_DIGEST_MEMO.get(key)
    if cached is not None:
        return cached
    info = _artefact_index().get(key)
    if info is None:
        return None
    kind, stem = info
    if kind == "part":
        digest = _digest_files(_part_file_deps(SCRIPTS_DIR / f"build_{stem}.py", stem))
    else:
        h = hashlib.md5()
        h.update(_digest_files(_recipe_files(stem)).encode())
        for ref in references_of(stem):
            ref_path = _sldasm(ref) if ref in ASSEMBLY_ORDER else _sldprt(ref)
            h.update((_stable_artefact_digest(ref_path) or "").encode())
        digest = h.hexdigest()
    _ARTEFACT_DIGEST_MEMO[key] = digest
    return digest


def task_part():
    """One task per part stem; addressable as ``part:<stem>``.

    Parts have NO inter-part deps, so they carry no ``task_dep``: SolidWorks
    serialization is enforced at runtime by the COM seat lock inside
    ``_cached_part_action``, not by DAG edges. The tasks are YIELDED in per-seat
    order (``_seat_part_order``) as a best-effort scheduling hint so two cold
    builders diverge and split the fleet cache.
    """
    scripts = {s.stem.removeprefix("build_"): s for s in part_scripts()}
    for stem in _seat_part_order():
        script = scripts[stem]
        yield {
            "name": stem,
            "file_dep": _part_file_deps(script, stem),
            "targets": [_sldprt(stem), _part_execution_token(stem)],
            "uptodate": [_ExecutionIdentityTracker(_part_execution_token(stem))],
            # Remote-cache shortcut + COM seat lock wrap the build (_cached_part_action).
            "actions": [(_cached_part_action, [stem, script])],
            "clean": True,
            "verbosity": 2,
        }


# --- Recipe-change detection (FULL vs REFRESH), robust to failed tasks.
#
# doit injects a ``changed`` arg into the action listing this task's stale
# file_deps, but it is UNRELIABLE after an intervening task FAILS: it then
# falsely flags pristine recipe files (and omits the real change), forcing a
# spurious FULL (measured -- "D2"). Instead we track the recipe (assembly script
# / _common.py / hooks) with an ``uptodate`` callable modelled on doit's own
# ``config_changed``: it compares an md5 of the recipe CONTENT against the value
# saved on the last *successful* run (value_savers only fire on success), so a
# failed task never corrupts it. It also stashes the changed-bit into
# _RECIPE_CHANGED -- this drives the run/skip ``uptodate`` (and is asserted by
# test_dodo_recipe). The FULL-vs-REFRESH decision itself no longer reads this
# global: build_or_refresh recomputes it from an on-disk sidecar so it is correct
# under ``doit -n`` process workers (codex review).
_RECIPE_CHANGED: dict[str, bool] = {}


class _RecipeTracker:
    """uptodate: True (up-to-date) when the recipe is unchanged since last success."""

    def __init__(self, stem: str, recipe_files: list[str]):
        self.stem = stem
        self.recipe_files = sorted(recipe_files)
        self.digest: str | None = None

    def _calc(self) -> str:
        return _digest_files(self.recipe_files)

    def __call__(self, task, values):
        self.digest = self._calc()
        task.value_savers.append(lambda: {"_recipe_digest": self.digest})
        last = values.get("_recipe_digest")
        _RECIPE_CHANGED[self.stem] = (last is None or last != self.digest)
        return (last is not None and last == self.digest)


def _assembly_run_mode(stem: str, target_missing: bool,
                       recipe_changed: bool) -> tuple[str, str]:
    """Choose FULL/REFRESH without sending known contacts to the generic gate."""
    if target_missing:
        return "full", "target missing"
    if recipe_changed:
        return "full", "recipe changed"
    if stem == "paper_drive":
        return "full", "bounded thread-contact gate requires full rebuild"
    return "refresh", "referenced artefact changed"


def build_or_refresh(stem, dependencies, changed, targets):
    """FULL rebuild vs cheap REFRESH for one assembly stem.

    FULL (run build_<stem>_assembly.py + any POST_ASSEMBLY hooks) when the target
    is missing OR the recipe itself changed (assembly script / _common.py / a hook
    script). Otherwise only referenced parts changed: REFRESH (refresh_assembly.py,
    no hooks -- reopening preserves the existing configuration).

    The recipe-changed decision is recomputed HERE from a sidecar digest (the
    last successful recipe digest), NOT read from the _RECIPE_CHANGED module
    global: under ``doit -n`` the action may run in a worker process that never
    saw the parent's global, which would force a spurious FULL on every stale
    assembly and silently defeat the incremental refresh (codex review). The
    sidecar is on disk (process-shared) and updated only on success. doit's own
    ``changed`` arg is likewise avoided -- it is corrupted by a prior failed
    task (D2).
    """
    label = f"assembly:{stem}"
    # Open the task span HERE (not in _run) so the cache decision + the FULL/REFRESH
    # build + any hooks share ONE trace rooted at this task: the cache events, the
    # FULL-vs-REFRESH ``mode`` attribute, and every subprocess span nest under it, so
    # a cache miss and the work it triggered are backtraceable from one trace.
    with _telemetry.span(f"task {label}", label=label) as sp:
        sidecar = _recipe_sidecar(stem)
        digest = _digest_files(_recipe_files(stem))

        # Remote-cache shortcut: a HIT downloads the .SLDASM (+ renders), skipping the
        # COM build/refresh entirely. The recipe sidecar is NOT cached -- its digest
        # tags by absolute path (machine-local) -- so recompute it here, exactly as the
        # success tail does, to keep the next run's FULL/REFRESH decision correct.
        cache_key = _cache_key(_assembly_file_deps(stem), label)
        cache_outputs = _assembly_cache_outputs(stem)

        def _record_recipe_digest() -> None:
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            sidecar.write_text(digest + "\n", encoding="utf-8")

        if _cache.restore(cache_key, cache_outputs, label):
            sp.set_attribute("cache", "hit")
            _stamp_assembly_execution(stem)
            _record_recipe_digest()
            return

        with _com_seat(label):
            # Re-probe under the seat: a peer builder may have published this assembly
            # while we blocked for the seat (fable/codex review) -> restore, don't
            # rebuild. The FULL+hooks (or REFRESH) run HOLDING the seat, so the hooks
            # operate on the just-built model without another COM task interleaving.
            if _cache.restore(cache_key, cache_outputs, label):
                sp.set_attribute("cache", "hit-after-wait")
                _stamp_assembly_execution(stem)
                _record_recipe_digest()
                return
            sp.set_attribute("cache", "miss")

            target_missing = not Path(targets[0]).exists()
            try:
                last = sidecar.read_text(encoding="utf-8").strip()
            except OSError:
                last = None
            recipe_changed = (last is None or last != digest)  # missing sidecar = FULL

            asm_script = SCRIPTS_DIR / f"build_{stem}_assembly.py"
            hooks = [SCRIPTS_DIR / h for h in POST_ASSEMBLY.get(stem, ())]
            if target_missing or recipe_changed:
                why = "target missing" if target_missing else "recipe changed"
                sp.set_attribute("mode", "full")
                _exec([sys.executable, str(asm_script)], f"FULL build {stem} ({why})",
                      log_stem=f"assembly-{stem}")
                for hook in hooks:
                    _exec([sys.executable, str(hook)], f"hook {hook.name}",
                          log_stem=f"hook-{stem}-{hook.stem}")
            else:
                sp.set_attribute("mode", "refresh")
                _exec([sys.executable, str(SCRIPTS_DIR / "refresh_assembly.py"), stem],
                      f"REFRESH {stem}", log_stem=f"assembly-{stem}")
            # _exec raised if the build failed, so we only get here on success: record
            # this build's recipe digest for the next run's FULL/REFRESH decision.
            _stamp_assembly_execution(stem)
            _record_recipe_digest()
        # Publish the fresh artefacts for other machines OUTSIDE the seat (an Azure
        # upload is network, not COM). RECOMPUTE the output set here, not reuse the one
        # from the top: the channel stretch parts and the top-level gallery PNGs are
        # glob-discovered and DID NOT EXIST yet on a clean builder when cache_outputs
        # was first computed, so the early list would publish an incomplete archive
        # (codex review). They exist now.
        _cache.store(cache_key, _assembly_cache_outputs(stem), label)


def _close_sw_documents() -> None:
    """Best-effort: close every open SolidWorks document to release file locks.

    A live or recently-failed build session holds .SLDASM/.png paths open on
    Windows, so a bare unlink/rmtree raises PermissionError. Swallows everything
    (no SolidWorks running, COM unavailable, ...) -- this is only a lock-release
    nudge before a retry."""
    try:
        sys.path.insert(0, str(SCRIPTS_DIR))
        from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

        adapter = PyWin32Adapter({})
        import asyncio

        asyncio.run(adapter.connect())
        adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    except Exception:  # noqa: BLE001 -- pure best-effort
        pass


def _force_remove(path: Path) -> None:
    """Unlink/rmtree a generated CAD output, retrying past a transient SolidWorks
    file lock; closes open SW documents before the final attempt. Never silently
    ignores a persistent failure -- the last attempt re-raises (codex review #7)."""
    if not path.exists():
        return
    remove = (lambda: shutil.rmtree(path)) if path.is_dir() else path.unlink
    for attempt in range(3):
        try:
            remove()
            return
        except PermissionError:
            if attempt == 0:
                _close_sw_documents()
            time.sleep(0.5)
    remove()  # final attempt: surface the error loudly rather than leave a stale lock


def _clean_assembly(stem):
    """Remove the .SLDASM target, its png/<dashed> render dir, and -- for channel
    -- the dynamically-generated stretched-spring variants (which are not any
    task's declared target, so a stale stretchNN body would otherwise be reused on
    the next build; codex review #4)."""
    _force_remove(Path(_sldasm(stem)))
    _force_remove(Path(_assembly_execution_token(stem)))
    _force_remove(_recipe_sidecar(stem))
    _force_remove(CAD_OUT / "png" / stem.replace("_", "-"))
    if stem == "channel":
        for variant in _channel_spring_variants():
            _force_remove(variant)


def task_assembly():
    """One task per assembly stem (``assembly:<stem>``).

    file_dep edges -- the assembly script, _common.py, this stem's hooks, and the
    referenced .SLDPRT/sub-.SLDASM targets -- give doit both ordering (top depends
    on the sub .SLDASMs, so it runs after) and the refresh/full decision (only
    parts changed -> refresh).
    """
    for stem in ASSEMBLY_ORDER:
        # Recipe = the files whose change forces a FULL rebuild (re-insert/re-mate)
        # vs a part-only refresh: the assembly script, its hooks, its helper
        # closure, AND the config docs THIS assembly reads (a placement like
        # channels.station_pitch_mm changing must re-insert components at new
        # coordinates, which an in-place reload cannot do; codex review #2).
        # Factored into _recipe_files so build_or_refresh computes the identical
        # digest.
        recipe_files = _recipe_files(stem)
        yield {
            "name": stem,
            "file_dep": _assembly_file_deps(stem),
            "targets": [_sldasm(stem), _assembly_execution_token(stem)],
            "uptodate": [
                _RecipeTracker(stem, recipe_files),
                _ExecutionIdentityTracker(_assembly_execution_token(stem)),
            ],
            # No spine: ordering (parts + sub-assemblies before this one) comes from
            # the real file_dep on their targets above; SolidWorks serialization is
            # the COM seat lock inside build_or_refresh.
            "actions": [(build_or_refresh, [stem])],
            "clean": [(_clean_assembly, [stem])],
            "verbosity": 2,
        }


def _clean_drawing(stem: str) -> None:
    for target in DRAWINGS_BY_NAME[stem].outputs.values():
        _force_remove(Path(target))


def task_drawing():
    """Curated manufacturing drawings with identity-safe shared caching.

    A drawing depends on its authoritative source model (a part's SLDPRT or an
    assembly's SLDASM, per the registry row's ``source_kind``) plus explicitly
    declared drawing inputs. It is independently selectable as
    ``drawing:<stem>`` and deliberately excluded from ``build_bare``.
    """
    for stem in _drawing_order():
        spec = DRAWINGS_BY_NAME[stem]
        yield {
            "name": stem,
            "file_dep": _drawing_file_deps(stem),
            "targets": [str(path.resolve()) for path in spec.outputs.values()],
            "actions": [(_cached_drawing_action, [stem])],
            "clean": [(_clean_drawing, [stem])],
            "verbosity": 2,
        }


def task_verify_soundness():
    """One independently stamped soundness gate per assembly.

    A change to one assembly no longer invalidates a monolithic gate that reopens
    all eight models. The public ``verify:soundness`` task below aggregates these
    child stamps, preserving the existing CLI and release dependency.
    """
    for stem in ASSEMBLY_ORDER:
        name = stem.replace("_", "-")
        sldasm = Path(_sldasm(stem))
        deps = [
            str(VERIFY_PY),
            str(POSTBUILD_PY),
            str(sldasm),
            _assembly_execution_token(stem),
        ]
        if stem == "paper_drive":
            deps.append(str(sldasm.parent / f".{sldasm.stem}.dof.json"))
        stamp = str(REPORTS / f"verify-soundness-{name}.ok")
        cmd = [sys.executable, str(VERIFY_PY), name, "--suite", "soundness"]
        yield {
            "name": stem,
            "file_dep": deps,
            "targets": [stamp],
            "actions": [(_run_stamped, [cmd, f"verify soundness {name}", stamp, True])],
            "clean": True,
            "verbosity": 2,
        }


def task_verify():
    """SolidWorks verification suites -- need SW open, serialized on the COM seat lock.

    ``verify:soundness`` / ``verify:subsystems`` / ``verify:kinematics`` each wrap
    ``verify.py --suite <x>`` and stamp ``cad/out/reports/verify-<x>.ok`` on
    success. The ``verify:`` prefix marks them as SolidWorks-dependent (vs the
    SolidWorks-free ``check:`` tasks).
    """
    def _dof_json(stem: str) -> str:
        sldasm = Path(_sldasm(stem))
        return str(sldasm.parent / f".{sldasm.stem}.dof.json")

    suite_deps = {
        # subsystems retired: its one unique gate (channel-independence) is folded
        # into soundness, which already opens `channel` (see verify._verify_static_one).
        "kinematics": [
            _sldasm("pen"),
            _assembly_execution_token("pen"),
            # The magnifier live-chain sweep (verify._verify_live_chain_one)
            # opens magnifier.SLDASM and authors its recorded lever drive spec
            # transiently; without this dep a magnifier rebuild would leave a
            # fresh verify-kinematics.ok stamp valid and SKIP the WIRE-1 gates
            # (codex review, PR #177).
            _sldasm("magnifier"),
            _assembly_execution_token("magnifier"),
            # The paper-feed kinematic proof (verify._verify_paper_feed_one) opens
            # paper-drive.SLDASM and drives the crank; without these deps a paper-drive
            # or probe change would leave a fresh verify-kinematics.ok stamp valid and
            # SKIP the crank->feed gate (codex #189).
            _sldasm("paper-drive"),
            _assembly_execution_token("paper_drive"),
            # The pen sweep + magnifier chain sweep read these manifests
            # directly (the transient drive specs). Same rationale as
            # soundness's paper-drive manifest dep above (codex #221).
            _dof_json("pen"),
            _dof_json("magnifier"),
            str((SCRIPTS_DIR / "build_kinematic_probe.py").resolve()),
            str((SCRIPTS_DIR / "pen_driver.py").resolve()),
            str((SCRIPTS_DIR / "truth_model.py").resolve()),
            # The transient pen equation reads _config VALUES through
            # pen_driver/truth_model (machine/output.yaml pen_rest_crank_deg /
            # pen_trace_half_mm / magnify_factor + channels.yaml harmonics/
            # phases/amplitudes). Post-#221 those files are no longer on pen's
            # build recipe (the saved model carries no equation), so without
            # these deps an amplitude edit would leave a fresh
            # verify-kinematics.ok stamp valid and SKIP the sweep (codex #224).
            # Derived by the same static analyzer as the build recipes, so a
            # new config read in pen_driver/truth_model is picked up
            # automatically. (_config.py itself needs no direct dep: it is on
            # pen's build closure, so it rides the pen.SLDASM recipe digest.)
            *_config_deps(SCRIPTS_DIR / "pen_driver.py"),
        ],
    }
    # Pass the graph's assemblies EXPLICITLY (dashed names) rather than letting
    # verify.py glob every *.SLDASM under cad/out/sldasm -- a stray/scratch
    # assembly left in a worktree must not be verified (codex review). kinematics
    # targets the pen + magnifier subs (verify.py's own defaults), no names.
    child_stamps = [
        str(REPORTS / f"verify-soundness-{stem.replace('_', '-')}.ok")
        for stem in ASSEMBLY_ORDER
    ]
    soundness_stamp = str(REPORTS / "verify-soundness.ok")
    yield {
        "name": "soundness",
        # Child stamps are targets of verify_soundness:* tasks, so doit derives
        # the real producer edges from file_dep without a synthetic task_dep.
        "file_dep": [str(VERIFY_PY), str(POSTBUILD_PY), *child_stamps],
        "targets": [soundness_stamp],
        "actions": [(_write_stamp, ["verify soundness", soundness_stamp])],
        "clean": True,
        "verbosity": 2,
    }

    for suite, deps in suite_deps.items():
        stamp = str(REPORTS / f"verify-{suite}.ok")
        cmd = [sys.executable, str(VERIFY_PY)]
        cmd += ["--suite", suite]
        yield {
            "name": suite,
            # verify.py's gate LOGIC lives partly in _assembly_postbuild.py
            # (load_dof_manifest/author_dof_drives -- the kinematics replays).
            # Unlike verify's other helper imports (_assembly/_common/build_*),
            # that module is deliberately OUTSIDE every assembly recipe (it is on
            # NO build script's closure), so a change to the replay logic does NOT
            # bump any .SLDASM digest -- and the .SLDASM file_deps below would then
            # leave a fresh verify-*.ok stamp valid, SKIPPING the gate (codex PR
            # #193). Depend on it directly. The build_* helpers verify imports for
            # constants need no such dep: they ride their .SLDPRT -> .SLDASM digest.
            "file_dep": [str(VERIFY_PY), str(POSTBUILD_PY), *deps],
            "targets": [stamp],
            # No spine: the file_dep on the built .SLDASM above orders this after the
            # assemblies; the COM seat lock (com=True) serializes it on the SW seat.
            "actions": [(_run_stamped, [cmd, f"verify {suite}", stamp, True])],
            "clean": True,
            "verbosity": 2,
        }


def task_check():
    """SolidWorks-FREE checks -- no COM, so they run in parallel under ``-n N``.

    ``check:math`` / ``check:config`` wrap ``verify.py --suite ...`` (verify.py
    runs those two without connecting to SolidWorks); ``check:graph`` /
    ``check:nameplate`` / ``check:recipe`` wrap the pure-python unit tests via
    pytest. None takes the COM seat lock, so they fan out under ``-n``.
    """
    config_py = str((SCRIPTS_DIR / "_config.py").resolve())
    # The tolerance audit (check:config) scans every build_*.py for PART_NAME, so a
    # part script added/renamed without touching the config YAML must still
    # invalidate the stamp (codex review).
    part_script_deps = [str(p.resolve()) for p in part_scripts()]
    pytest_cmd = [sys.executable, "-m", "pytest", "-q"]
    recipe_tests = [
        SCRIPTS_DIR / "test_dodo_recipe.py",
        SCRIPTS_DIR / "test_cut_release_version.py",
        SCRIPTS_DIR / "test_export_models.py",
        SCRIPTS_DIR / "test_verify_auto_repair.py",
        # The SolidWorks-free geometry contract for the drawing layout audit
        # (collision / sheet-overflow logic run before every drawing saves).
        SCRIPTS_DIR / "test_drawing_layout_check.py",
        # Drawing infrastructure and cross-sheet contracts do not follow the
        # per-sheet test_*_drawing.py suffix, so enroll them explicitly.
        SCRIPTS_DIR / "test_drawing_marks.py",
        SCRIPTS_DIR / "test_cone_drawing_batch_contract.py",
        SCRIPTS_DIR / "test_fastener_catalog.py",
        # One offline contract file per manufacturing drawing (test_*_drawing.py),
        # so registering a drawing auto-enrolls its contracts here.
        *sorted(SCRIPTS_DIR.glob("test_*_drawing.py")),
        # Cross-sheet ownership checks whose filename intentionally does not match
        # the one-file-per-drawing discovery pattern above.
        SCRIPTS_DIR / "test_fastener_drawing_metadata.py",
        SCRIPTS_DIR / "test_remaining_fastener_drawings.py",
        SCRIPTS_DIR / "test_pen_summing_drawing_batch_contract.py",
    ]
    recipe_test_deps = sorted({
        *(str(path.resolve()) for path in recipe_tests),
        *(dep for path in recipe_tests for dep in module_deps_of(path)),
    })
    specs = {
        "math": {
            # truth_model reads harmonics/phases/amplitudes/magnification from
            # _config + the YAML layer, so those must invalidate the math stamp
            # too (codex review). The base-footprint gate reads placement +
            # footprint constants straight off these build modules -- folded via
            # module_deps_of so the geometry contracts they import (the
            # *_spec.py single-source modules) invalidate the stamp too (codex
            # review #353: a FOOT_WIDTH edit in arbor_pedestal_spec.py must
            # re-run the gate, not leave its stamp valid).
            "file_dep": [str(VERIFY_PY),
                         *sorted({
                             str(Path(dep).resolve())
                             for module in (
                                 "truth_model.py",
                                 "build_drive_train_assembly.py",
                                 "build_cone_pivot_post.py",
                                 "build_cone_pivot_screw.py",
                                 "build_swing_stop_screw.py",
                                 "build_cone_swing_platform.py",
                                 "build_cone_lock_knob.py",
                                 "build_cone_tip_block.py",
                                 "build_cone_tip_bushing.py",
                                 "build_cone_tip_adjuster.py",
                                 "build_cone_tip_pinch_screw.py",
                                 "build_arbor_pedestal.py",
                                 "build_harmonic_base.py",
                             )
                             for dep in (
                                 SCRIPTS_DIR / module,
                                 *module_deps_of(SCRIPTS_DIR / module),
                             )
                         }),
                         config_py, *_CONFIG_YAMLS],
            "cmd": [sys.executable, str(VERIFY_PY), "--suite", "math"],
        },
        "config": {
            "file_dep": [str(VERIFY_PY),
                         str((SCRIPTS_DIR / "gen_dimensions.py").resolve()),
                         config_py, *_CONFIG_YAMLS, *part_script_deps],
            "cmd": [sys.executable, str(VERIFY_PY), "--suite", "config"],
        },
        "graph": {
            # test_config_accessor_coverage reads _config.py, so a new accessor
            # added there (without an entry in _buildgraph) must invalidate this
            # stamp -- else the "fails loud" coverage test silently never re-runs
            # and the perf benefit is lost (codex review #193).
            "file_dep": [str((SCRIPTS_DIR / "_buildgraph.py").resolve()),
                         str((SCRIPTS_DIR / "test_buildgraph.py").resolve()),
                         config_py],
            "cmd": [*pytest_cmd, str(SCRIPTS_DIR / "test_buildgraph.py")],
        },
        "nameplate": {
            # Guards the vendored engraving DXF the nameplate build imports; the
            # DXF is now the source of truth (the re-traced coordinate loops are
            # retired), so the gate depends on the file + its integrity test.
            "file_dep": [str((SCRIPTS_DIR / "test_nameplate_geometry.py").resolve()),
                         str((REPO_ROOT / "cad" / "references"
                              / "nameplate-engraving.dxf").resolve())],
            "cmd": [*pytest_cmd, str(SCRIPTS_DIR / "test_nameplate_geometry.py")],
        },
        "recipe": {
            # _CONFIG_YAMLS: the metadata-ownership contracts read part rows via
            # _config.parts(), and module_deps_of tracks _config.py but not the
            # YAML documents it loads -- without these deps a finish/material
            # edit would leave the stamp valid and the guard silently stale
            # (codex review #361).
            "file_dep": [str((REPO_ROOT / "dodo.py").resolve()),
                         *recipe_test_deps,
                         *_CONFIG_YAMLS,
                         str(PROJECT_DRWDOT.resolve())],
            "cmd": [*pytest_cmd, *(str(path) for path in recipe_tests)],
        },
        "cache": {
            # The artefact-cache provenance/observability unit tests (issue #73):
            # key derivation, event log, store-skip-on-hit drift. Pure python.
            "file_dep": [str((SCRIPTS_DIR / "_artifact_cache.py").resolve()),
                         str((SCRIPTS_DIR / "test_artifact_cache.py").resolve())],
            "cmd": [*pytest_cmd, str(SCRIPTS_DIR / "test_artifact_cache.py")],
        },
        "telemetry": {
            # The OTel observability spine: severity split, no-gap span status,
            # log<->trace correlation, cross-process propagation, plus the release
            # neutral-export aggregate/event shape. Pure python, so it runs as an
            # offline gate -- without this the spine or release observability could
            # regress while the required checks stay green.
            "file_dep": [str((SCRIPTS_DIR / "_telemetry.py").resolve()),
                         str((SCRIPTS_DIR / "cut_release.py").resolve()),
                         str((SCRIPTS_DIR / "export_models.py").resolve()),
                         str((SCRIPTS_DIR / "test_telemetry.py").resolve()),
                         str((SCRIPTS_DIR / "test_cut_release_telemetry.py").resolve())],
            "cmd": [*pytest_cmd,
                    str(SCRIPTS_DIR / "test_telemetry.py"),
                    str(SCRIPTS_DIR / "test_cut_release_telemetry.py")],
        },
        "watchdog": {
            # The COM crash/hang watchdog (_watchdog.py): a NEW sldexitapp.exe
            # (SolidWorks' crash-report dialog) or 15 min of telemetry silence
            # hard-exits the COM subprocess (releasing the seat via the doit
            # parent); a hung SW window only warns. Pure python, injectable
            # probes -- so the fatal/log-only contract can't silently regress.
            # _common.py is a dep because the gate also pins the INTEGRATION
            # (run_build arms/disarms the watchdog): an edit that drops those
            # calls must re-run this gate, not reuse the old stamp (codex #344).
            "file_dep": [str((SCRIPTS_DIR / "_watchdog.py").resolve()),
                         str((SCRIPTS_DIR / "_telemetry.py").resolve()),
                         str((SCRIPTS_DIR / "_common.py").resolve()),
                         str((SCRIPTS_DIR / "test_watchdog.py").resolve())],
            "cmd": [*pytest_cmd, str(SCRIPTS_DIR / "test_watchdog.py")],
        },
        "verify_telemetry": {
            # The verify-gate span SHAPE, driven by a mock SolidWorks whose COM
            # calls sleep at durations calibrated from the release logs: the
            # per-component dof.check / per-target whats_wrong floods stay
            # collapsed, and the slow gates (over-constrained / gear-ratios /
            # component-count / open) keep their child spans -- no gate regresses
            # back into one opaque 80-90 s span. Pure python (no SolidWorks).
            "file_dep": [str((SCRIPTS_DIR / "_telemetry.py").resolve()),
                         str((SCRIPTS_DIR / "_assembly.py").resolve()),
                         str((SCRIPTS_DIR / "verify.py").resolve()),
                         str((SCRIPTS_DIR / "test_verify_telemetry.py").resolve())],
            "cmd": [*pytest_cmd, str(SCRIPTS_DIR / "test_verify_telemetry.py")],
        },
        "freshness": {
            # verify.py's standalone-staleness guard: reuses doit's .doit.db ledger
            # + ContentChecker to refuse scoring a stale tree (the gap that let a
            # never-rebuilt 8-component frame trip component-count). Pure python ->
            # offline gate, so the guard can't regress while required checks stay green.
            "file_dep": [str(VERIFY_PY),
                         str((REPO_ROOT / "dodo.py").resolve()),
                         str((SCRIPTS_DIR / "_buildgraph.py").resolve()),
                         str((SCRIPTS_DIR / "test_verify_freshness.py").resolve())],
            "cmd": [*pytest_cmd, str(SCRIPTS_DIR / "test_verify_freshness.py")],
        },
        "flagonly": {
            # The targeted late-binding flag helper (_flag_only, issue #87) -- pure
            # dispatch glue. Was merged WITHOUT a check task, so it never ran in CI;
            # wired here so a regression in _common._flag_only fails an offline gate.
            "file_dep": [str((SCRIPTS_DIR / "_common.py").resolve()),
                         str((SCRIPTS_DIR / "test_flag_only.py").resolve())],
            "cmd": [*pytest_cmd, str(SCRIPTS_DIR / "test_flag_only.py")],
        },
        "partiso": {
            # Guards the three-tier submodule digest: parts must never import the
            # assembly/motion + drawing modules the PART recipe excludes, AND assemblies
            # must never import the drawing module the ASSEMBLY recipe excludes
            # (_submodule_part_digest / _submodule_assembly_digest), else that exclusion
            # could silently skip a real rebuild. Derives its forbidden sets from dodo's
            # exclude lists, so it depends on dodo.py + every part AND assembly script
            # AND the transitive repo-local helper closure the test actually scans
            # (module_deps_of): a helper like _gear.py gaining a forbidden import while
            # no build script changes must still re-run this gate, else the invariant
            # goes stale unnoticed (codex #191). The entry point of any new forbidden
            # import is always in this set -- a part/assembly script (caught) or a helper
            # already in its closure (caught) -- so it is self-healing. Pure python ->
            # offline.
            "file_dep": sorted({
                str((REPO_ROOT / "dodo.py").resolve()),
                str((SCRIPTS_DIR / "_buildgraph.py").resolve()),
                str((SCRIPTS_DIR / "test_part_isolation.py").resolve()),
                *part_script_deps,
                *(dep for p in part_scripts() for dep in module_deps_of(p)),
                *(str((SCRIPTS_DIR / f"build_{s}_assembly.py").resolve())
                  for s in ASSEMBLY_ORDER),
                *(dep for s in ASSEMBLY_ORDER
                  for dep in module_deps_of(SCRIPTS_DIR / f"build_{s}_assembly.py")),
            }),
            "cmd": [*pytest_cmd, str(SCRIPTS_DIR / "test_part_isolation.py")],
        },
    }
    # Tripwire: `build` and `release` depend on f"check:{c}" for c in _CHECK_NAMES, so a
    # spec added here without the matching name (or vice versa) would silently never run
    # in the default paths -- exactly the gap Codex caught on freshness/flagonly. Keep
    # the two in lockstep.
    _all_check_names = set(_CHECK_NAMES) | set(_OPTIONAL_CHECK_NAMES)
    assert set(specs) == _all_check_names, \
        f"check specs vs check-names drift: {set(specs) ^ _all_check_names}"
    for name, spec in specs.items():
        stamp = str(REPORTS / f"check-{name}.ok")
        yield {
            "name": name,
            "file_dep": spec["file_dep"],
            "targets": [stamp],
            "actions": [(_run_stamped, [spec["cmd"], f"check {name}", stamp])],
            "clean": True,
            "verbosity": 2,
        }


def task_export():
    """Complete release-neutral export (STEP / STL / assembly glTF / PNG manifest + scene). COM seat.

    Always runs ``export_models.py`` (``uptodate: False``) -- it self-checks every
    output's per-file staleness cheaply and prints "all exports fresh" when there
    is nothing to do. That self-check keys on the SAME churn-immune recipe digest
    (``_stable_artefact_digest``) doit/the remote cache use, NOT the .SLDPRT/.SLDASM
    mtime -- SolidWorks' save-cascade + cache-restore bump those mtimes on every
    build, which used to make the script re-export every part each release. We do
    NOT gate on a single declared target: a deleted STEP/STL/colors output (with the
    boxes JSON + CAD inputs unchanged) must still be regenerated, which doit would
    otherwise skip (codex review).
    """
    targets = [
        str((CAD_OUT / "boxes" / "harmonic-analyzer.json").resolve()),
        str((REPORTS / "release-neutral.json").resolve()),
    ]
    deps = ([_sldprt(s) for s in part_stems()]
            + [_sldasm(s) for s in ASSEMBLY_ORDER])
    return {
        "file_dep": [str(EXPORT_PY), *deps],
        "targets": targets,
        # REAL gate edge (was implicit via the spine): export writes neutral formats +
        # refreshes the comparison gallery into cad/out, side effects that must NOT be
        # generated from a model that then fails soundness/kinematics. So export waits
        # on the SW verify gates -- a genuine dependency, not a serialization hack.
        "task_dep": ["verify:soundness", "verify:kinematics"],
        "uptodate": [False],
        # --record-digests: this runs AFTER every part/assembly is (re)built (its
        # file_dep) and the verify gates, so the natives are current and their recipe
        # digests are safe to RECORD as the export-freshness cache (a bare standalone
        # run must not -- see export_models.main). com=True: holds the COM seat.
        "actions": [(_run, [[sys.executable, str(EXPORT_PY), "--record-digests"],
                            "export", "export", True])],
        "verbosity": 2,
    }


def task_preflight():
    """Release preflight (OPT-IN, COM seat): the gear-ratios proof on the
    reopened drive-train + channel (the only assemblies carrying real gear
    meshes), WITHOUT saving. Gates `release`.

    NOT in `build`/`default_tasks` -- gear-ratios re-proves a property the
    tooth-count config fixes (check:math validates it analytically), so it
    runs at release time only. Its file_dep on the two .SLDASM orders it after
    them; the COM seat lock keeps it serial on the STA seat. Stamps
    `cad/out/reports/preflight.ok`.
    """
    stamp = str(REPORTS / "preflight.ok")
    deps = [str(PREFLIGHT_PY), str(VERIFY_PY),
            str((SCRIPTS_DIR / "_assembly.py").resolve()), str(POSTBUILD_PY),
            _sldasm("drive_train"), _sldasm("channel")]
    return {
        "file_dep": deps,
        "targets": [stamp],
        # No spine: the file_dep on drive-train + channel .SLDASM orders this after
        # those assemblies; the COM seat lock (com=True) serializes it on the SW seat.
        # Always run (like export/release), so a stale stamp can never let
        # release skip the proof.
        "uptodate": [False],
        "actions": [(_run_stamped, [[sys.executable, str(PREFLIGHT_PY)],
                                    "release preflight", stamp, True])],
        "clean": True,
        "verbosity": 2,
    }


def _run_release(relargs):
    """Run cut_release.py, forwarding any positional args (``doit release -- v22``).

    com=True: the release job holds the COM seat for its ENTIRE duration -- including
    its non-COM tail (renders, zip, ``gh`` upload) -- so it blocks any other worktree's
    COM work until the release finishes. Accepted: a release is a serialized,
    machine-owning operation."""
    _run([sys.executable, str(RELEASE_PY), *relargs], "cut release", com=True)


def task_release():
    """Cut a tagged release (Pack-and-Go + neutral exports + diff + GitHub
    release). OPT-IN -- not in default_tasks. Needs SW + gh; holds the COM seat.

    Publishing is a side effect (no doit target), so it always runs. Forward
    Args after ``--``: ``doit release -- v22 --draft``. With no version, the
    latest compact release tag is incremented (for example, ``v21`` -> ``v22``).
    Gated on EVERY gate via REAL task_dep edges (the spine is gone, so these are now
    explicit): ``export`` (which itself pulls the parts/assemblies + the ``verify:*``
    gates), every registered ``drawing:*`` artifact that release stages,
    ``preflight`` (gear-ratios), the ``verify:*`` suites, and every offline
    ``check:*`` -- so a release cannot publish past a stale/failing gate or package
    a missing/stale drawing.
    """
    return {
        "task_dep": ["export", "preflight", *(f"drawing:{s}" for s in _drawing_order()),
                     *(f"verify:{s}" for s in _VERIFY_NAMES),
                     *(f"check:{c}" for c in _CHECK_NAMES)],
        "uptodate": [False],
        "pos_arg": "relargs",
        "actions": [(_run_release,)],
        "verbosity": 2,
    }


def task_build():
    """THE fully-safe entry point (also ``default_tasks``): every part + assembly
    + every gate (SolidWorks ``verify:*`` and offline ``check:*``).

    No neutral export / Pack-and-Go -- doit only runs a selected task's upstream
    prerequisites. Use ``doit -n N`` to fan out the ``check:*`` work alongside the
    COM stream (serialized by the seat lock, not a spine).

    Ordering here is a SCHEDULING HINT only (real deps drive correctness): the
    offline ``check:*`` gates are listed FIRST so workers burn through that ~1 min of
    SolidWorks-free work before piling onto the COM seat, and the parts are in
    per-seat order so two cold builders diverge and split the fleet cache.
    """
    return {
        "actions": None,
        "task_dep": (
            [f"check:{s}" for s in _CHECK_NAMES]
            + [f"part:{s}" for s in _seat_part_order()]
            + [f"assembly:{s}" for s in ASSEMBLY_ORDER]
            + [f"drawing:{s}" for s in _drawing_order()]
            + [f"verify:{s}" for s in _VERIFY_NAMES]
        ),
    }


def task_build_bare():
    """Quick rebuild: parts + assemblies only -- no verification, no export.
    Parts in per-seat order (scheduling hint); the seat lock keeps COM serial."""
    return {
        "actions": None,
        "task_dep": (
            [f"part:{s}" for s in _seat_part_order()]
            + [f"assembly:{s}" for s in ASSEMBLY_ORDER]
        ),
    }


# --- Cache diagnostic (issue #73): explain any miss in ONE command.
#
# SolidWorks-FREE and never takes the COM seat lock -- it computes the same
# key/file_dep set the build does and PROBES the backend (a presence check, no
# download), so it never touches the seat. For every part + assembly + drawing it
# prints HIT/MISS + key + (for a miss,
# or with `all`) the per-dep digests that produced the key, plus a drift flag when
# this seat's last-published key differs from the current one. That is the ad-hoc
# script we hand-wrote cutting v0.9.0, kept.
def _cache_rows() -> list[tuple[str, list[str]]]:
    """(label, file_deps) for every cacheable COM task, in build order."""
    rows: list[tuple[str, list[str]]] = []
    for script in part_scripts():
        stem = script.stem.removeprefix("build_")
        rows.append((f"part:{stem}", _part_file_deps(script, stem)))
    for stem in ASSEMBLY_ORDER:
        rows.append((f"assembly:{stem}", _assembly_file_deps(stem)))
    for stem in _drawing_order():
        rows.append((f"drawing:{stem}", _drawing_file_deps(stem)))
    return rows


def _cache_status(statusargs):
    args = [a.lower() for a in (statusargs or [])]
    only_miss = "miss" in args
    show_all = "all" in args
    filters = [a for a in args if a not in ("miss", "all")]

    cfg = _cache.config_summary()
    _telemetry.info(f"[cache_status] mode={cfg['mode']} epoch={cfg['epoch']} salt={cfg['salt']} "
                    f"account={cfg['account']} container={cfg['container']}")
    if not _cache.enabled():
        _telemetry.warn("[cache_status] cache disabled (mode=off) -- keys computed, backend NOT probed")

    hits = misses = unknown = 0
    for label, deps in _cache_rows():
        if filters and not any(f in label.lower() for f in filters):
            continue
        key, inputs = _cache.key_inputs(deps, ContentChecker._digest)
        present = _cache.probe(key)        # True / False / None (disabled|unreachable)
        if present is True:
            mark, hits = "HIT ", hits + 1
        elif present is False:
            mark, misses = "MISS", misses + 1
        else:
            mark, unknown = "?   ", unknown + 1
        if only_miss and present is not False:
            continue
        last = _cache.last_stored_key(label)
        drift = f"  DRIFT(last published {last[:12]})" if last and last != key else ""
        emit = _telemetry.warn if present is False else _telemetry.info
        emit(f"{mark} {key[:12]}  {label}{drift}")
        if drift:
            previous = dict(_cache.last_stored_inputs(label))
            current = dict(inputs)
            for rel in sorted(previous.keys() | current.keys()):
                before, after = previous.get(rel, "<absent>"), current.get(rel, "<absent>")
                if before != after:
                    _telemetry.debug(f"         {before} -> {after}  {rel}")
        if show_all or present is False:
            for rel, digest in inputs:
                _telemetry.debug(f"         {digest}  {rel}")
    _telemetry.success(f"[cache_status] {hits} hit / {misses} miss / {unknown} unknown")


def task_cache_status():
    """Diagnostic: per part/assembly/drawing, key + dep digests + backend HIT/MISS,
    so any miss is explainable in one command (issue #73). SolidWorks-FREE, never
    takes the COM seat lock, never in default_tasks.

    Positional args (after ``--``): label substrings to filter (e.g. ``cone_gear``);
    ``miss`` to show only misses; ``all`` to dump dep digests for every task (default:
    only for misses). ``HARMONIC_CACHE_DEBUG=1`` additionally logs key provenance from
    the build itself."""
    return {
        "uptodate": [False],
        "pos_arg": "statusargs",
        "actions": [(_cache_status,)],
        "verbosity": 2,
    }
