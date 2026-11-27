r"""The whole pipeline as one doit graph: build -> verify -> export -> release.

doit decides *whether* each part/assembly is stale (md5 content hash, immune to
git/worktree mtime churn); the refresh primitive makes the assembly recipe cheap.

A ``.SLDASM`` is a thin reference layer over its part files, so when only a
referenced ``.SLDPRT`` changed, an assembly is REFRESHED (reopen + per-config
ForceRebuild3 + gates + in-place Save3 -- seconds) instead of rebuilt from
scratch (re-insert + re-mate ~122 components -- ~500 s). The recipe escalates to a
FULL rebuild (+ any post-assembly hooks) when the assembly script / shared helper
closure / a hook changed, or the target is missing. A refresh that hits a dangling mate, free
DOF, or interference FAILS LOUD (non-zero exit, .SLDASM untouched); recover with
the full escape below.

Task groups (the prefix says whether SolidWorks is required):

  part:<stem>        build one part            (COM -- needs SolidWorks)
  assembly:<stem>    build/refresh one assembly (COM)
  drawing:<stem>     build one manufacturing drawing (COM)
  package:features:<stem> isolated labelled STEP + face inventory (COM)
  package:features   aggregate every feature STEP (NO SolidWorks)
  package:manifest:<stem> bind declarations into features.toml (NO SolidWorks)
  package:manifest   aggregate every features.toml (NO SolidWorks)
  verify:<suite>     soundness/subsystems/kinematics gates (COM)
  check:<name>       math/config/graph/nameplate/recipe gates (NO SolidWorks)
  check:machinist_review:<stem> cached blind reviews + judge (NO SolidWorks)
  prechips:<stem>    pro + hobby HTML travelers + hobby PDF, latest PyPI prechips (in build + release, not build_bare; NO SolidWorks)
  prechips:standing  shop standing instructions HTML + PDF, common to every traveler (with the travelers; NO SolidWorks)
  cam:<stem>         NC programs posted by headless FreeCAD CAM (freecadcmd) with cycle times (in build + release, not build_bare; NO SolidWorks; FreeCAD 1.1+ on the submitter)
  export             neutral STEP/STL/glTF/scene export (COM)
  release            cut a tagged GitHub release (COM + gh; opt-in)
  build              EVERY part + assembly + EVERY gate -- the one safe entry
  build_bare         parts + assemblies only -- a quick rebuild

COM serialization (the single SolidWorks STA seat) is enforced at RUNTIME by a
cross-process file lock (``_com_seat`` / ``filelock``), NOT by fake ``task_dep``
edges: every COM subprocess acquires the machine-global seat lock before it drives
SolidWorks and releases it after, so at most one COM task touches the seat at a
time even under ``doit -n N``. Local ``check:*`` subprocesses share a separate
host-wide CPU-worker budget; remote leaves remain concurrent. The graph carries only
REAL dependency edges (an assembly's file_dep on its parts, verify/export on the
built ``.SLDASM``, release on export+verify), so the DAG reads true and a
COM failure no longer skips unrelated downstream COM tasks as a spine side effect.

Install (this repo is a uv project -- pyproject.toml + uv.lock at the root)::

    uv sync                      # core deps + pytest, from the lockfile

Run through uv (SolidWorks already open for the COM tasks)::

    uv run python -m doit                       # = `build`: every part + assembly + every gate
    uv run python -m doit -n 4                  # local seat only: cache restores/checks parallel within the host CPU budget
    uv run python build.py --verbosity warning  # concise console output; farm: no -n (build.py keeps 8 leaves in flight)

    uv run python -m doit build_bare            # quick: parts + assemblies only, no gates
    uv run python -m doit assembly:pd_paper_drive  # just that assembly + its stale prereqs
    uv run python -m doit part:sm_summing_lever    # just that part
    uv run python -m doit verify:soundness      # one SW gate; check:math one offline gate
    uv run python -m doit export                # neutral STEP/STL/glTF/scene export
    uv run python -m doit release               # cut the next vNN release (opt-in)
    uv run python -m doit list --all            # every task
    uv run python -m doit clean                 # remove targets (+ wipe png/<asm>)

Full-rebuild escape (idiomatic doit -- a missing target forces a run, and
build_or_refresh takes the FULL branch when the target is absent)::

    del cad\out\sldasm\pd-paper-drive.SLDASM
    %DOIT% forget assembly:pd_paper_drive    # optional: also drop the cached hash
    %DOIT% assembly:pd_paper_drive
"""

from __future__ import annotations

import ast
import contextlib
import datetime
import functools
import hashlib
import math
import os
import re
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from collections.abc import Iterable
from typing import Any
from doit.dependency import CHECKERS, Dependency, JsonDB, MD5Checker
from doit.tools import config_changed
from doit.loader import generate_tasks
from doit.task import Task, dict_to_task
from filelock import FileLock, Timeout  # noqa: E402
import yaml

# Every build/verify/export task routes its subprocess through ``_run``, which
# streams the child's stdout through this doit parent process -- and tees it to
# cad/out/logs when a log_stem is given. Build output carries non-ASCII (e.g. the
# "A ∩ B" gate labels); on Windows the parent stdout defaults to cp1252, so
# re-emitting that glyph raises UnicodeEncodeError and kills the reader (which can
# then hang the child on a full pipe). Force UTF-8 on the parent too, mirroring
# run_build (_session.py).
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")


sys.path.insert(0, str(Path(__file__).resolve().parent / "cad" / "scripts"))

# ``_resolved`` is the graph's per-process ``Path.resolve()`` memo (dropped by
# ``clear_import_caches``); dodo's per-task path plumbing shares it.
from _buildgraph import (  # noqa: E402
    _resolved,
    ASSEMBLY_ORDER,
    CAD_OUT,
    POST_ASSEMBLY,
    RECIPE_SKIP_MODULES,
    SCRIPTS_DIR,
    ASSEMBLY_CONTRACTS_TOKEN,
    all_config_files,
    artefact_for,
    assembly_contract_file,
    assembly_contract_files,
    assembly_contract_reads,
    config_files_of,
    data_deps_of,
    dict_table_entries,
    dict_table_recipe,
    drawing_registry_reads_selected,
    drawing_registry_recipe,
    fastener_rows_selected,
    interference_contract_file,
    is_racy_mtime,
    machine_family_files,
    tolerance_family_files,
    module_deps_of,
    part_row_files,
    part_scripts,
    part_stems,
    parts_registry_files,
    read_source,
    references_of,
    script_for,
    stamps_part_properties,
    source_text_digest,
    syntax_digest,
)

from machinist_review_config import (  # noqa: E402
    ReviewProfile,
    registered_review_profile,
    split_drawing_guidelines,
    validate_review_profile,
)

# Freeze both stages once, before prewarming the cache or executing any leaf.
# The same resolved values key remote verdicts, local freshness and CLI argv.
_MACHINIST_REVIEW_PROFILE = registered_review_profile()

import _artifact_cache as _cache  # noqa: E402  (remote build-artefact cache)
import _farm  # noqa: E402  (farm executor: cache-missing leaves run on the pool)
import _sw_lifecycle  # noqa: E402  (SolidWorks autostart/recover; lazy-imports sw_recovery)
import _telemetry  # noqa: E402  (observability spine: console logging + tracing)
import _local_check  # noqa: E402  (host-wide local check admission)
from _yaml_digest import yaml_digest as _yaml_content_digest  # noqa: E402
from _drawing_registry import DRAWINGS_BY_NAME  # noqa: E402
from _drawing_types import DRAWING_TEMPLATES  # noqa: E402
from _machinist_review_mode import (  # noqa: E402
    MachinistReviewMode,
    mode_for_drawing,
)
from _refresh_tier import (  # noqa: E402  (FULL / PARTS tier choice)
    RefreshTier,
    classify_refresh,
)

# A farm leaf execution (rw) opens its cache connection while the graph loads,
# instead of inside its first cache.probe; a no-op anywhere else (_cache.prewarm).
_cache.prewarm()

REPO_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = REPO_ROOT / "cad" / "config"
RELEASE_VERSION_FILE = (CONFIG_DIR / "release.yaml").resolve()
# The repo-owned part template (see _paths.PART_TEMPLATE -- path duplicated
# deliberately; importing _buildgraph from _paths would drag graph tooling
# into every part's dep closure). A runtime input of every part build.
PART_TEMPLATE = REPO_ROOT / "cad" / "templates" / "harmonic-analyzer.PRTDOT"


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
#
# Waiting for the seat is QUEUEING, not work, so it is DISCOUNTED from the enclosing
# ``task <label>`` span (see ``_com_seat``): a task's span duration times its build,
# not how contended the machine was when it ran.
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
# ``_session.run_build`` guard loud -- the runtime successor to the removed spine tripwire.
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
    WITHOUT the seat trips ``_session.run_build``'s guard loud -- the runtime successor to the
    removed ``_assert_spine_complete`` tripwire. Reentrancy-safe (``filelock`` counts
    same-process acquisitions), though no COM action nests it.

    **The wait gets its OWN top-level span, and the ``task <label>`` span starts once
    the seat is HELD** -- the two are siblings, never nested. Blocking on the seat is
    queueing, not work: inside the task span it made a duration report how contended
    the machine was (the same part reads 40 s on an idle seat and 20 min behind a cold
    assembly build), skewing every cross-run comparison and the watchdog calibration
    read off ``traces.jsonl``. Splitting keeps BOTH numbers exact and each in the
    signal it belongs to -- ``com.seat.wait <label>`` times the queue, ``task
    <label>`` times the work -- with no timestamp surgery on a live span (an earlier
    cut moved the task span's start forward instead; that is not a spec'd operation,
    and it left the pre-wait cache events dangling before their own span's start).
    Callers get the wait handed back so the task span can still carry it as a
    ``seat_wait_s`` attribute, and release logs the seat's TOTAL elapsed time.

    Yields the seconds spent blocked (0.0 when the seat was free)."""
    _COM_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    holder = f"{label} pid={os.getpid()}"
    entered = time.monotonic()
    with _telemetry.span(
        f"com.seat.wait {label}", label=label, service=_telemetry.BUILD_INFRA_SERVICE
    ) as wait_span:
        polls = 0
        while True:
            try:
                _COM_LOCK.acquire(timeout=_COM_SEAT_POLL_S)
                break
            except Timeout:
                polls += 1
                other = _read_seat_holder()
                _telemetry.debug(
                    f"[com.seat] {label} waiting for the SolidWorks seat"
                    + (f" (held by {other})" if other else "")
                )
        acquired = time.monotonic()
        waited = acquired - entered
        wait_span.set_attribute("polls", polls)
    _write_seat_holder(holder)
    prev = os.environ.get(_COM_SEAT_HELD_ENV)
    os.environ[_COM_SEAT_HELD_ENV] = holder
    try:
        yield waited
    finally:
        if prev is None:
            os.environ.pop(_COM_SEAT_HELD_ENV, None)
        else:
            os.environ[_COM_SEAT_HELD_ENV] = prev
        _clear_seat_holder(holder)
        _COM_LOCK.release()
        released = time.monotonic()
        # The task span has already closed here (the seat outlives it), so there is no
        # span to hang an event on: the seat's TOTAL elapsed time is a log record,
        # queryable in logs.jsonl by its structured fields.
        _telemetry.info(
            f"[com.seat] {label} released after {released - entered:.1f}s total "
            f"(waited {waited:.1f}s, held {released - acquired:.1f}s)",
            wait_s=round(waited, 2),
            held_s=round(released - acquired, 2),
            elapsed_s=round(released - entered, 2),
            service=_telemetry.BUILD_INFRA_SERVICE,
        )


def _tag_seat_wait(span, waited: float | None) -> None:
    """Carry the seat wait onto the task span, so "how long did this task queue?"
    is answerable from the task span alone (its sibling ``com.seat.wait`` span holds
    the same number as its duration). ``None`` = no seat was taken (a ``check:*``
    gate, or a test stubbing ``_com_seat``)."""
    if waited is not None:
        span.set_attribute("seat_wait_s", round(waited, 2))


# Drawing tasks declare only their source model as CAD input, while their code
# recipe follows the exporter's complete repo-local import closure (the vendored
# SolidWorks adapter included).
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
    return sorted(
        part_stems(),
        key=lambda s: hashlib.md5(
            f"{seed}\0{s}".encode(), usedforsecurity=False
        ).hexdigest(),
    )


# --- Comment/whitespace-insensitive content hashing for cad/config/*.yaml.
#
# doit's stock MD5Checker hashes RAW FILE BYTES, so a comment-only or reflow edit
# to a SHARED config (every part lists cad/config/*.yaml as a file_dep) flips that
# file's md5 and marks EVERY dependent part stale -> a spurious full rebuild. This
# bit us once: a provenance-comment retarget in the former monolithic tolerance
# config (value unchanged) rebuilt 75 parts. ContentChecker digests the *parsed* YAML instead -- key order
# preserved, comments and formatting discarded -- so only a real data change
# invalidates. Non-YAML deps (.py, .SLDPRT) fall through to the exact stock md5,
# so their stored state stays valid across the switch.
#
# NB: changing the checker class re-stamps every task's `checker:` field, which
# doit treats as changed -> run `doit reset-dep` once after this lands to migrate
# the db in place WITHOUT a rebuild (the on-disk artefacts are already current).
def _canonical_file_bytes(file_path: str) -> bytes:
    """Git-canonical content of a file, independent of Windows checkout EOLs.

    ``core.autocrlf=true`` may materialise a tracked text blob's LF as CRLF (or a
    conflict/patch can leave a mixed file) while Git still considers the content
    unchanged. Git's text heuristic is a NUL check in the first 8 KiB; mirror that
    boundary and clean CRLF to LF. Binary inputs are returned untouched.

    The ONE canonicalisation rule for hashing source content: any digest that must
    agree across checkouts (this seat's cache key, a farm worker's, the exporter's
    freshness sentinel) has to canonicalise identically, or identical code hashes
    differently per checkout and every cross-machine comparison silently fails.
    """
    data = Path(file_path).read_bytes()
    if b"\0" not in data[:8000]:
        data = data.replace(b"\r\n", b"\n")
    return data


def _canonical_file_md5(file_path: str) -> str:
    """MD5 of Git-canonical content -- see ``_canonical_file_bytes``.

    Avoids a subprocess per dependency on the cache hot path.
    """
    return hashlib.md5(_canonical_file_bytes(file_path)).hexdigest()


class ContentChecker(MD5Checker):
    """MD5Checker with three churn-immunities: it digests the PARSED form of YAML
    configs (comment-/whitespace-insensitive), the SYNTAX TREE of recipe code
    (comment-, docstring- and layout-insensitive -- ``_buildgraph.syntax_digest``),
    and keys ``.SLDPRT``/``.SLDASM`` artefacts on their producing task's
    build-input recipe rather than SolidWorks' volatile output bytes (build
    idempotency -- see ``_stable_artefact_digest``). Other text deps are
    Git-EOL-canonical; binary deps remain byte-identical to MD5Checker."""

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
            # geometry's inputs change. None -> not a declared target -> stock
            # byte md5.
            recipe = _stable_artefact_digest(file_path)
            return recipe if recipe is not None else _canonical_file_md5(file_path)
        if file_path.endswith(".py"):
            # A task whose output holds source lines or bytes also folds the
            # text itself: see _source_text_dep.
            syntax = syntax_digest(Path(file_path))
            return syntax if syntax is not None else _canonical_file_md5(file_path)
        if not file_path.endswith((".yaml", ".yml")):
            return _canonical_file_md5(file_path)
        with open(file_path, "rb") as fh:
            digest = _yaml_content_digest(fh.read())
        if digest is None:
            return _canonical_file_md5(file_path)  # malformed -> build fails loud later
        return digest

    def check_modified(self, file_path, file_stat, state):
        timestamp, size, digest = state
        # mtime unchanged -> content unchanged (stock fast path). A racily
        # recorded state stores 0.0 (see get_state), so it never takes this path.
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
        digest = self._digest(dep)
        # A dep written in the same file-time tick as this record could be
        # rewritten at the same size without moving its mtime, and the fast path
        # above would then vouch for stale content. Record 0.0 instead, so the
        # next check compares digests until the mtime has settled.
        if is_racy_mtime(timestamp):
            timestamp = 0.0
        return timestamp, size, digest


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
    return str(_resolved(artefact_for(SCRIPTS_DIR / f"build_{stem}.py")))


def _sldasm(stem: str) -> str:
    return str(_resolved(artefact_for(SCRIPTS_DIR / f"build_{stem}_assembly.py")))


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
    return str(_resolved(CAD_OUT / "sldprt" / f".{name}.execution"))


def _assembly_execution_token(stem: str) -> str:
    """Stable identity of the exact assembly artefact built or restored.

    Assembly rebuild state and mate references are persisted against the exact
    child CAD identities, not merely their recipes. Propagating this token to a
    parent prevents a same-recipe subassembly from being mixed with a parent that
    was saved against another SolidWorks identity (issue #301).
    """
    name = stem.replace("_", "-")
    return str(_resolved(CAD_OUT / "sldasm" / f".{name}.execution"))


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
    the child is labelled the moment it imports ``_telemetry``.

    The PARENT-side ``task <label>`` span uses it too (via ``service=`` on
    ``_telemetry.span``), so a task and the subprocess it spawns share one resource
    instead of the task span reading the umbrella name while its own children read
    the stage. What is left on the umbrella is only what genuinely has no stage --
    and the seat/cache phases have their own ``build-infra`` resource -- so
    ``harmonic-analyzer`` is now a namespace and a fallback, not a span label.
    A label this does not map (the fallback below) simply keeps the umbrella."""
    if label.startswith("part:"):
        return "part-build"
    if label.startswith(("assembly:", "FULL build", "REFRESH", "hook ")):
        return "assembly-build"
    if label.startswith(("drawing:", "drawing ")):
        return "drawing-export"
    if label.startswith("verify_soundness:"):
        return "verify-soundness"
    if label.startswith("verify:"):
        return "verify-" + label.split(":", 2)[1]
    if label.startswith("verify "):
        return "verify-" + label.split(None, 2)[1]
    if label.startswith("cam:"):
        return "cam-nc"
    if label.startswith("prechips:"):
        return "prechips-traveler"
    if label.startswith(("check:machinist_review:", "review_sweep:")):
        return "check-machinist-review"
    if label.startswith("check "):
        return "check-" + label.split(None, 2)[1]
    if label.startswith("cut release") or label in ("release", "package:release"):
        return "release"
    if label == "gallery":
        return "gallery"
    if label.startswith(("export", "package:features:", "package:manifest:")):
        return "export"
    return "harmonic-analyzer"


def _exec(
    cmd: list[str], label: str, log_stem: str | None = None, *, task: str | None = None
) -> None:
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
    started = time.time()
    rc = _run_subprocess(cmd, label, log_stem, task=task)
    if rc:
        _fail_task(label, rc, started=started)


_EXTERNAL_LOG_LEVELS = {
    "debug": "DEBUG",
    "info": "INFO",
    "success": "SUCCESS",
    "warning": "WARNING",
    "warn": "WARNING",
    "error": "ERROR",
    "critical": "CRITICAL",
}


def _external_console_level() -> str:
    raw = os.environ.get("HARMONIC_VERBOSITY", "warning").strip().lower()
    return _EXTERNAL_LOG_LEVELS.get(raw, "WARNING")


# Every COM subprocess (:func:`_exec_com`: part, assembly, drawing and hook
# runs) hashes str with seed 0, applied last so an inherited PYTHONHASHSEED
# cannot override it: a build that iterates a set of str issues its COM
# requests in one order on every run (DEVELOPING.md, "Deterministic COM
# request order"). It moves no cache key (dodo.py is in no recipe closure).
_COM_ENV_PINS = {"PYTHONHASHSEED": "0"}


def _run_subprocess(
    cmd: list[str],
    label: str,
    log_stem: str | None = None,
    *,
    task: str | None = None,
    env_pins: dict[str, str] | None = None,
) -> int:
    """Run the subprocess (span-less) and return its exit code (the raise-on-failure
    part is :func:`_exec`; the COM-retry wrapper :func:`_exec_com` needs the raw code
    to tell a SolidWorks crash/op-timeout (86/87) from an ordinary gate failure).

    ``label`` is the display name; ``task`` is the doit task the subprocess works
    for (default: ``label``, which already is one for most callers). The
    fastener-row guard is keyed on ``task``, so a FULL/REFRESH/hook subprocess
    with a display label still gets its assembly's rows. ``env_pins`` are set
    over everything else (:data:`_COM_ENV_PINS` for COM subprocesses)."""
    _telemetry.info(f">> {label}: {' '.join(cmd)}")
    env = _telemetry.inject_env()
    env["OTEL_SERVICE_NAME"] = _stage_name(label)
    # The catalog rows this task's cache key folds; `fastener` refuses others.
    rows = _fastener_rows_env(task or label)
    env.pop("HARMONIC_FASTENER_ROWS", None)
    if rows is not None:
        env["HARMONIC_FASTENER_ROWS"] = rows
    # The MCP adapter uses Loguru directly. Keep its console sink aligned with
    # the build's warning-by-default policy while preserving an explicit override.
    env.setdefault("LOGURU_LEVEL", _external_console_level())
    env.update(env_pins or {})
    if log_stem is None:
        return subprocess.run(cmd, cwd=str(REPO_ROOT), env=env).returncode
    LOGS.mkdir(parents=True, exist_ok=True)
    with (LOGS / f"{log_stem}.log").open("w", encoding="utf-8") as fh:
        fh.write(f">>  {label}: {' '.join(cmd)}\n")
        fh.flush()
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            fh.write(line)
            fh.flush()
        return proc.wait()


# SolidWorks autostart + reactive recovery for COM subprocesses (see _sw_lifecycle).
# Autostart is ONCE PER WORKER: the first COM task to reach _exec_com brings SW up
# (the flag is a module global, so each doit -n worker ensures once; later tasks see
# CONNECTED and skip). SW-free tasks never call _exec_com, so `doit list` / check:math
# never start SolidWorks. Retry is REACTIVE: a COM subprocess that fails in a SW way
# is retried with backoff, recovering SW in between.
_SW_ENSURED = False
# Backoff between COM-failure retries: 1, 2, 4 minutes (=> up to 3 retries, 4 attempts).
_COM_RETRY_BACKOFF_S: tuple[int, ...] = (60, 120, 240)
# Watchdog exit codes that unambiguously mean SolidWorks itself broke (see _watchdog):
# 86 crash, 87 op timeout, 88 a modal dialog blocking the seat (the 2026-09-02
# low-committed-memory box), 89 a seat of any age or origin that never reported
# ISldWorks.StartupProcessCompleted (_seat_forensics' connect-time gate) -- all
# four recover by kill + relaunch + retry locally; a farm leaf (autostart off)
# recovers none of them and re-runs only 89, once, on the untouched seat.
_WATCHDOG_EXIT_CODES = frozenset({86, 87, 88, 89})
# _watchdog.EXIT_SEAT_NOT_READY: the connect-time startup gate's exit, restated
# like the codes above (dodo never imports the per-subprocess _watchdog) and
# pinned equal by test_seat_startup_gate.
_EXIT_SEAT_NOT_READY = 89
# Pre-task memory preflight. SolidWorks' commit charge grows across a day of
# builds (66 GB after ~10 h on 2026-09-02, on a 127 GB seat) until SolidWorks
# itself pops "Warning! Your system is running critically low on committed
# memory" mid-task -- a modal that blocks the seat (watchdog exit 88) and
# precedes a crash. A fresh session sits at ~1.5 GB, so once the process is past
# this budget it is restarted BEFORE the next task, under the seat lock, where
# it costs one cold start (~7 min) instead of a lost task + the same restart.
# 0 disables.
_SW_MAX_COMMIT_GB_ENV = "HARMONIC_SW_MAX_COMMIT_GB"
_SW_MAX_COMMIT_GB_DEFAULT = 40.0


def _sw_autostart_enabled() -> bool:
    return os.environ.get("HARMONIC_SW_AUTOSTART", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _com_retry_backoff() -> tuple[int, ...]:
    """Per-retry backoff seconds. ``HARMONIC_COM_RETRY_BACKOFF_S`` (comma-separated)
    overrides the 1/2/4-min default — for tuning aggressiveness or driving the
    crash→recover→retry chain in a live test without minutes of real waiting."""
    raw = os.environ.get("HARMONIC_COM_RETRY_BACKOFF_S", "").strip()
    if not raw:
        return _COM_RETRY_BACKOFF_S
    try:
        parsed = tuple(int(x) for x in raw.split(",") if x.strip())
    except ValueError:
        return _COM_RETRY_BACKOFF_S
    return parsed or _COM_RETRY_BACKOFF_S


def _sw_max_commit_gb() -> float:
    """The preflight budget in GB; a non-numeric or non-finite override (``nan``
    would bypass both comparisons, ``inf`` would never restart) falls back to
    the default. ``<= 0`` disables the preflight."""
    try:
        value = float(os.environ.get(_SW_MAX_COMMIT_GB_ENV, _SW_MAX_COMMIT_GB_DEFAULT))
    except ValueError:
        return _SW_MAX_COMMIT_GB_DEFAULT
    return value if math.isfinite(value) else _SW_MAX_COMMIT_GB_DEFAULT


def _sw_commit_gb() -> float | None:
    """Committed (private) bytes of the SolidWorks main process, in GB -- the number
    its own low-memory warning keys on. ``None`` when it is not running, off-Windows,
    or on any probe error (the preflight then does nothing)."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        from solidworks_mcp.adapters import sw_recovery

        pids = sw_recovery.pids_of_image(sw_recovery.SW_MAIN_PROCESS)
        if not pids:
            return None

        class _MemoryCountersEx(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_MemoryCountersEx),
            wintypes.DWORD,
        ]
        total = 0
        for pid in pids:
            handle = kernel32.OpenProcess(
                0x1000, False, pid
            )  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                continue
            try:
                counters = _MemoryCountersEx()
                counters.cb = ctypes.sizeof(counters)
                if psapi.GetProcessMemoryInfo(
                    handle, ctypes.byref(counters), counters.cb
                ):
                    total += int(counters.PrivateUsage)
            finally:
                kernel32.CloseHandle(handle)
        return total / 1e9 if total else None
    except Exception:  # noqa: BLE001 - a probe glitch must never fail a build
        return None


def _sw_preflight() -> None:
    """Restart a bloated SolidWorks BEFORE a COM task (``_SW_MAX_COMMIT_GB_DEFAULT``).

    Runs under the seat lock at every COM call site (after :func:`_sw_ensure_once`),
    as a ``build-infra`` span so a trace answers "was this task's start a memory
    restart?" in one filter. Best-effort like the rest of the lifecycle glue."""
    budget = _sw_max_commit_gb()
    if budget <= 0:
        return
    commit = _sw_commit_gb()
    if commit is None or commit <= budget:
        return
    with _telemetry.span(
        "sw.memory_restart",
        service=_telemetry.BUILD_INFRA_SERVICE,
        commit_gb=round(commit, 1),
        budget_gb=budget,
    ) as span:
        _telemetry.warn(
            f"[sw] SolidWorks commit {commit:.1f} GB > {budget:.0f} GB budget "
            f"({_SW_MAX_COMMIT_GB_ENV}) -- restarting the seat before this task, "
            "ahead of its own low-memory modal",
            commit_gb=round(commit, 1),
            budget_gb=budget,
        )
        _telemetry.event(
            "sw.memory_restart", commit_gb=round(commit, 1), budget_gb=budget
        )
        state = _sw_lifecycle.force_recover()
        if state != _sw_lifecycle.CONNECTED_STATE:
            state = _sw_lifecycle.wait_until_ready()
        span.set_attribute("final_state", state)


def _sw_ensure_once() -> None:
    """Bring SolidWorks up once per doit worker, before this worker's first COM BUILD,
    then run the per-task memory preflight (:func:`_sw_preflight`) every time.

    Called at each COM call site as a TOP-LEVEL ``build-infra`` span (a sibling of the
    ``task`` span, like the seat wait), NOT from inside ``_exec_com``/the task span --
    so the ``sw.ensure_ready`` cost never inflates the ``task <label>`` "work" timing.
    Guarded by ``_SW_ENSURED`` (once per worker) and ``HARMONIC_SW_AUTOSTART`` (opt-out).
    Placed AFTER the under-seat cache re-probe, so a worker whose tasks all hit the
    cache never starts SolidWorks. Best-effort (``ensure_ready`` swallows its own
    failures and proceeds to ``connect``)."""
    global _SW_ENSURED
    if not _sw_autostart_enabled():
        return
    if not _SW_ENSURED:
        _sw_lifecycle.ensure_ready()
        _SW_ENSURED = True
    _sw_preflight()


def _exec_com(
    cmd: list[str],
    label: str,
    log_stem: str | None = None,
    *,
    task: str | None = None,
) -> None:
    """Run a COM subprocess with reactive SolidWorks recovery.

    If the subprocess exits with a watchdog crash/op-timeout/modal-dialog/
    seat-not-ready code (86/87/88/89) or leaves
    SolidWorks not-connected, retry up to ``len(_COM_RETRY_BACKOFF_S)`` times, waiting
    1/2/4 min then force-recovering SW (kill→relaunch) between attempts. An ordinary
    failure (gate assertion, build error) with SolidWorks still healthy is NOT retried
    -- it raises immediately.

    Autostart (bringing SolidWorks up before the first build) is separate:
    :func:`_sw_ensure_once`, called by each COM call site as a top-level sibling span
    BEFORE the task span -- not here, so it can't nest under the task span.

    Fail-loud contract of :func:`_exec` is preserved: a terminal failure still raises
    ``RuntimeError``. Under ``HARMONIC_SW_AUTOSTART=0`` (every farm leaf: the
    keeper owns the seat) nothing here may kill or relaunch SolidWorks, so there
    is no recovery loop -- except that exit 89 (the seat had not finished
    starting within the gate's bound) re-runs ONCE, untouched: a seat still
    loading add-ins is the one unhealthy state that heals by waiting, and the
    re-run's own gate waits again."""

    def run() -> tuple[int, float]:
        started = time.time()
        rc = _run_subprocess(cmd, label, log_stem, task=task, env_pins=_COM_ENV_PINS)
        return rc, started

    if not _sw_autostart_enabled():
        rc, started = run()
        if rc == _EXIT_SEAT_NOT_READY:
            _telemetry.warn(
                f"[sw] {label}: seat still starting (exit {rc}); re-running once "
                "on the same seat (autostart off: no recovery here)",
                exit_code=rc,
                attempt=1,
            )
            rc, started = run()
        if rc:
            _fail_task(label, rc, started=started)
        return

    backoff = _com_retry_backoff()
    last = len(backoff)
    for attempt in range(last + 1):
        # Per ATTEMPT, not per task: a retry that fails must name its own
        # capture, not the previous attempt's (they differ by exactly the seat
        # state this evidence exists to compare).
        rc, started = run()
        if rc == 0:
            return
        sw_broke = rc in _WATCHDOG_EXIT_CODES or not _sw_lifecycle.is_connected()
        if not sw_broke or attempt == last:
            _fail_task(label, rc, started=started)
        delay = backoff[attempt]
        _telemetry.warn(
            f"[sw] {label} failed (exit {rc}) with SolidWorks unhealthy; backoff "
            f"{delay}s then force-recover + retry {attempt + 1}/{last}",
            exit_code=rc,
            attempt=attempt + 1,
            backoff_s=delay,
        )
        time.sleep(delay)
        state = _sw_lifecycle.force_recover()
        # A recovery that ends anywhere but CONNECTED means SolidWorks is still
        # coming up, and the retry we are about to release would spend its whole
        # 60 s COM-attach window on a process that cannot answer yet -- a retry
        # slot burned for nothing (measured: final_state=starting, retry died on
        # "running but did not become COM-attachable"). Give it one BOUNDED grace
        # window first (see wait_until_ready -- deliberately not a second full
        # budget), then respawn regardless. Compare the state force_recover
        # RETURNED rather than probing again: it returns "error" precisely when
        # detect_state() blew up, so a second probe would re-raise that failure
        # out of _exec_com and abort the task -- inverting the best-effort retry.
        if state != _sw_lifecycle.CONNECTED_STATE:
            _telemetry.warn(
                f"[sw] {label}: recovery ended state={state}, not connected; "
                "waiting for the cold start rather than spending a retry on it",
                state=state,
                attempt=attempt + 1,
            )
            _telemetry.event(
                "sw.cold_start_wait", label=label, state=state, attempt=attempt + 1
            )
            _sw_lifecycle.wait_until_ready()


def _run(
    cmd: list[str], label: str, log_stem: str | None = None, *, task: str | None = None
) -> None:
    """Open a ``task <label>`` span and run the subprocess inside it (see
    :func:`_exec`). One span per task action, NAMED for the doit task
    (``task check:math``) so the trace reads as the task itself; the subprocess
    CONTINUES this span (via the injected TRACEPARENT) instead of adding a
    duplicate root layer under it.

    SolidWorks-FREE tasks ONLY -- it never takes the COM seat. Local checks
    additionally use their host-wide admission runner. Every COM task uses
    :func:`_cached_com_action`, which owns the seat lock, the remote-cache
    probe/store and the farm dispatch; there is therefore no code path that can
    reach SolidWorks while bypassing the cache or the farm."""
    with _telemetry.span(
        f"task {label}", label=label, cmd=" ".join(cmd), service=_stage_name(label)
    ):
        _exec(cmd, label, log_stem, task=task)


# --- Per-script helper dependencies, computed from each build script's REAL
# transitive imports (``module_deps_of``) instead of a blanket "every ``_*.py`` is
# a dep of every build". A leaf part that imports only the focused helpers it
# uses no longer rebuilds when an assembly-only helper (``_assembly``) or an
# unrelated one (``_gear``) changes; the closure follows each helper's imports
# transitively so it never under-invalidates as long as a script imports what
# it uses. (Excludes _buildgraph.py: the build-GRAPH helper
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
    name in ``_part_properties.part_properties``):

      * a PART stamps only its OWN row -> parts/<dashed-stem>.yaml + _defaults
        (editing one row rebuilds one part);
      * an ASSEMBLY that stamps in-script (none since the channel's spring
        variants became configurations of their part, #1610) depends on the
        rows of the parts it references (a superset of the rows it stamps --
        conservative); a non-stamping assembly
        needs NO parts row (a referenced part's row edit rebuilds that PART, whose
        new .SLDPRT triggers the assembly REFRESH);
      * a DRAWING reads its OWN part's row -> parts/<dashed-part>.yaml +
        _defaults (none for an assembly-sourced sheet, which has no row).
        Every dynamic registry read a drawing closure reaches is its own part
        (property/member helpers and reads of the drawing's native source
        identity);
        test_dodo_recipe.test_drawing_closures_read_no_foreign_dynamic_part_row
        fails loud on any new one.  A literal read of ANOTHER part's row
        (``_config.parts("ch-pivot-bracket")``) is its own concrete token;
      * any other caller (e.g. an offline check) -> the whole registry.
    """
    if kind in ("part", "drawing") and stem is not None:
        return part_row_files(stem.replace("_", "-"))
    if kind == "assembly" and stem is not None:
        if not stamps_part_properties(script):
            return []
        files: set[str] = set()
        defaults = CONFIG_DIR / "parts" / "_defaults.yaml"
        if defaults.exists():
            files.add(str(_resolved(defaults)))
        for ref in references_of(stem):
            files.update(part_row_files(ref.replace("_", "-")))
        return sorted(files)
    return parts_registry_files()


def _expand_assembly_contracts_token(
    stem: str | None, kind: str | None, script: Path
) -> list[str]:
    """Per-task expansion of the ``"assemblies/*"`` token (any closure reaching
    ``_assembly_contract``). An ASSEMBLY task reads only its OWN contract -- the
    build activates its own stem -- so a sibling's seed or free-stem edit never
    re-keys it. A DRAWING task reads exactly the contracts its closure names by
    literal stem (``_buildgraph.assembly_contract_reads``), so a new kit's
    contract never re-keys an unrelated sheet. Any other consumer, or a drawing
    closure that reaches a contract by a runtime value, keeps the whole family
    (conservative)."""
    if kind == "assembly" and stem is not None:
        return [assembly_contract_file(stem)]
    if kind == "drawing":
        reads = assembly_contract_reads(script)
        if reads is not None:
            return [assembly_contract_file(read) for read in sorted(reads)]
    return assembly_contract_files()


def _config_deps(script, stem: str | None = None, kind: str | None = None) -> list[str]:
    """The cad/config FILES this build script actually reads (fine-grained;
    conservative whole-config fallback on any unclassifiable ``_config`` use).

    Expands the tokens from ``config_files_of`` to concrete paths, narrowing the
    ``"parts/*"`` registry token to the task's own rows (see _expand_parts_token).
    """
    script = script if isinstance(script, Path) else Path(script)
    tokens = config_files_of(script)
    if "**" in tokens:
        return all_config_files()
    out: set[str] = set()
    for tok in tokens:
        if tok == "machine/*":
            out.update(machine_family_files())
        elif tok == "tolerances/*":
            out.update(tolerance_family_files())
        elif tok == "parts/*":
            out.update(_expand_parts_token(stem, kind, script))
        elif tok == ASSEMBLY_CONTRACTS_TOKEN:
            out.update(_expand_assembly_contracts_token(stem, kind, script))
        else:
            out.add(str(_resolved(CONFIG_DIR / tok)))
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
# Forensic artefacts a failing COM build step leaves behind: the saved copy of
# the failing document, the BMP of the seat and capture.json
# (``_seat_forensics.capture_com_failure`` / ``OUT_FAILURES``). A farm worker's
# workspace is DISPOSABLE, so the doit parent enumerates them on every failure
# path: the manifest goes to the process the pool captures into the leaf's
# ``task.log``, which is the one channel that always reaches the submitter.
FAILURES = REPORTS / "failures"
# The exact phrase a failure that captured nothing prints, shared between the
# emission (``_fail_task``) and the instruction that tells an operator to look
# for it (``_failure_artefact_hint``). One constant because the two must agree:
# an instruction naming a string the log does not contain is how the reader
# ends up running a download that fetches zero blobs.
_NO_ARTEFACTS = "no forensic artefacts captured"


def _failure_artefacts(since: float) -> list[Path]:
    """Artefacts THIS attempt wrote, newest-first by path.

    Scoped by mtime rather than by listing the whole tree: a local run keeps
    ``cad/out/reports/failures/`` across invocations (it is not a declared target,
    so no task's ``clean`` removes it), and a manifest that also names last
    week's captures sends the reader to the wrong evidence.

    An entry that cannot be stat'd is SKIPPED, not fatal: the tree is walked on
    the failure path, while the dying seat (or a virus scanner, or the pool's
    uploader) may still be moving files under it, and losing one raced temp file
    must not cost the reader the manifest for the artefacts that are there.
    """
    if not FAILURES.is_dir():
        return []
    found: list[Path] = []
    for path in FAILURES.rglob("*"):
        try:
            if path.is_file() and path.stat().st_mtime >= since:
                found.append(path)
        except OSError:
            continue
    return sorted(found)


def _artefact_record(path: Path) -> str | None:
    """One manifest entry (``relpath:size:digest16``), or ``None`` when the
    artefact is gone or unreadable.

    Digesting a saved SLDPRT takes seconds, so the file can vanish between the
    walk and the read; the entry is then dropped with a warning instead of
    aborting the manifest (and, per :func:`_fail_task`, instead of replacing the
    task's own failure)."""
    try:
        return (
            f"{path.relative_to(FAILURES).as_posix()}"
            f":{path.stat().st_size}"
            f":{_artefact_digest(path)[:16]}"
        )
    except OSError as exc:
        # A log sink is I/O too: see _fail_task on why no emission here may
        # escape.
        with contextlib.suppress(Exception):
            _telemetry.warn(
                f"[forensics] artefact {path} became unreadable while the "
                f"manifest was being written: {exc}",
                artefact=str(path),
            )
        return None


def _artefact_digest(path: Path) -> str:
    """SHA-256 of an artefact, read in chunks: a saved SLDPRT is tens of MB and
    this runs on the failure path, where the process is already in trouble."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _fail_task(label: str, rc: int, *, started: float) -> None:
    """Fail a task loud -- after publishing whatever forensics it left behind.

    Always raises. The manifest (path, size, sha256 of each artefact) is emitted
    from the doit PARENT, after the subprocess's own log has closed, so it lands
    in the leaf log the pool uploads even when the child died too hard to report
    anything itself. The digest is what lets the submitter verify the blob it
    downloads is the artefact the worker wrote.

    The seat's commit charge against the configured preflight budget goes out on
    its own record whenever a seat is running. "It was not memory pressure" was a
    hypothesis that had to be ruled out by hand on 2026-09-17 with no recorded
    number to rule it out with; both values come from the live helpers
    (:func:`_sw_commit_gb`, :func:`_sw_max_commit_gb`), never from a remembered
    figure. No seat (an offline task, or off-Windows) means no record rather than
    an "unknown GB" line on every pytest failure. ``started`` bounds the manifest
    to the artefacts THIS attempt wrote (see :func:`_failure_artefacts`).

    The manifest can NEVER replace the failure it documents, by either route.
    Enumerating and digesting the tree is I/O on a path where the workspace is
    already in trouble, so an ``OSError`` there degrades to a WARNING; and
    EMITTING is I/O as well -- ``logging`` does not guard a handler, so an
    ``emit`` that raises (OTel's ``LoggingHandler.emit`` is one unguarded line,
    and a full or locked sink is exactly the condition a dying worker is in)
    propagates straight out of ``_telemetry.error`` unless suppressed. Either
    way the ``RuntimeError`` carrying the exit code still goes out: the
    alternative is a leaf log whose last word is a FileNotFoundError under
    ``failures/`` or the log handler's own traceback, which reads as "the
    forensics broke" and hides which build step failed and with what code --
    the one fact this whole path exists to deliver (coderabbit, CrLoop772).

    Only the EMISSIONS are suppressed, never the manifest arithmetic around
    them: a ``NameError`` or a bad f-string here must stay loud, or this path
    becomes undebuggable. Same split as ``_seat_forensics.capture_com_failure``, which
    wraps its final ERROR record and nothing else.

    A failure that captured NOTHING says so on its own line. Most failures
    capture nothing: ``capture_com_failure`` fires at COM-failure sites, so an
    ordinary recipe rejection (``_check.check`` raising on a refused sketch
    relation, say) leaves ``failures/`` empty and there is no bundle to fetch.
    Emitting nothing at all made that indistinguishable from "the forensics
    never ran", and the submitter's message advertised a ``failures/*``
    download that resolved to zero blobs -- an absent artefact presented as a
    retrievable one, which is the same lie as a field reported blank when no
    read could have answered it. ``_failure_artefact_hint`` sends the reader to
    THIS line, so it has to exist in both outcomes (measured on
    ``part:pen_set_screw``, gate build 2026-09-18).
    """
    commit_gb = _sw_commit_gb()
    if commit_gb is not None:
        with contextlib.suppress(Exception):
            _telemetry.error(
                f"[forensics] {label} failed (exit {rc}) with the seat at "
                f"{commit_gb:.1f} GB of its {_sw_max_commit_gb():.1f} GB budget",
                label=label,
                exit_code=rc,
                seat_commit_gb=round(commit_gb, 2),
                seat_commit_budget_gb=_sw_max_commit_gb(),
            )
    try:
        artefacts = _failure_artefacts(started)
    except OSError as exc:
        artefacts = []
        with contextlib.suppress(Exception):
            _telemetry.warn(
                f"[forensics] {label}: cannot enumerate {FAILURES}: {exc}",
                label=label,
                exit_code=rc,
            )
    records = [record for record in (_artefact_record(p) for p in artefacts) if record]
    if records:
        with contextlib.suppress(Exception):
            _telemetry.error(
                f"[forensics] {label}: {len(records)} artefact(s) under "
                f"{FAILURES} -- upload prefix 'failures/' beside the leaf log",
                label=label,
                exit_code=rc,
                failure_dir=str(FAILURES),
                artefacts=" ".join(records),
            )
    else:
        with contextlib.suppress(Exception):
            _telemetry.error(
                f"[forensics] {label}: {_NO_ARTEFACTS} -- nothing was uploaded "
                f"under 'failures/', so this failure is diagnosed from this log",
                label=label,
                exit_code=rc,
                failure_dir=str(FAILURES),
                artefacts="",
            )
    raise RuntimeError(f"{label} failed (exit {rc})")


def _failure_artefact_hint(log_blob: str | None) -> str:
    """Where a farm leaf's forensic artefacts sit, derived from its log blob.

    The pool uploads the leaf's console log to
    ``<container>/leaf/<task>/<key>/<attempt>/task.log`` and its failure
    artefacts to the ``failures/`` prefix BESIDE it, so the submitter needs no
    extra protocol field to find them -- the log blob it already gets is the
    anchor.

    The bundle is CONDITIONAL and this side cannot see it: only failures whose
    recipe called ``capture_com_failure`` leave artefacts, the worker's
    workspace is gone by now, and ``LeafResult`` carries no artefact count. An
    unconditional download instruction therefore sent operators to a prefix
    with zero blobs (``part:pen_set_screw``, gate build 2026-09-18) -- worse
    than silence, because the pause before the failure implies something was
    captured. Probing the container from here is the wrong fix: it would put a
    network call on the path whose one job is to deliver the exit code.

    So the hint names the authority that always exists -- the leaf log's own
    ``[forensics]`` line, which :func:`_fail_task` now emits in BOTH outcomes --
    and marks the download as conditional on it. ``_NO_ARTEFACTS`` is shared
    with that emission so the string an operator is told to look for is the
    string the log actually contains.
    """
    if not log_blob or "/" not in log_blob:
        return "no leaf log blob was reported, so no failure artefacts either"
    container, _, blob = log_blob.partition("/")
    prefix = f"{blob.rsplit('/', 1)[0]}/failures/"
    return (
        f"forensics: the leaf log's '[forensics]' line says whether this "
        f"failure captured anything; if it says '{_NO_ARTEFACTS}' there is no "
        f"bundle, otherwise fetch it with: az storage blob download-batch "
        f"--source {container} --pattern '{prefix}*' "
        f"--destination cad/out/reports/failures"
    )


VERIFY_PY = (SCRIPTS_DIR / "verify.py").resolve()
# Verify gate logic that is NOT on any assembly's build closure (so it
# does not ride a .SLDASM digest) -> a direct file_dep of verify: tasks.
POSTBUILD_PY = (SCRIPTS_DIR / "_assembly_postbuild.py").resolve()
EXPORT_PY = (SCRIPTS_DIR / "export_models.py").resolve()
RELEASE_PY = (SCRIPTS_DIR / "cut_release.py").resolve()
# COM half of a release: SolidWorks Pack-and-Go of the top assembly and of every
# drawing, merged into cad/out/release/native/ (the `package:release` leaf). Split
# out of cut_release.py so the publisher itself needs no seat.
PACKAGE_NATIVE_PY = (SCRIPTS_DIR / "package_native.py").resolve()

# The gate suites, by SolidWorks-dependence -- the single source of truth for the
# verify:/check: task names (reused by build + release so a new gate is wired in
# one place).
_VERIFY_NAMES = ("soundness", "kinematics")  # need SW (spine); subsystems retired
# Offline checks REQUIRED on every build/release (fast, high-value):
_CHECK_NAMES = (
    "math",
    "config",
    "graph",
    "undefined_names",
    "nameplate",
    "numerals",
    "recipe",
    "cache",
    "telemetry",
    "watchdog",
    "flagonly",
    "partiso",
    "inert",
    "budget",
)
# Checks outside the every-build set. verify_telemetry is opt-in;
# features_bound is required only by release. Union must match the specs.
_OPTIONAL_CHECK_NAMES = ("verify_telemetry", "features_bound")


def _run_stamped(cmd: list[str], label: str, stamp: str, task: str) -> None:
    """Run a SolidWorks-free gate subprocess; on success write its stamp target.
    _run raises on non-zero, so a failed gate never writes a stamp (stays stale ->
    re-runs). The COM gates (``verify:*``) do NOT come here: they are
    cache-keyed leaves whose stamp is written by :func:`_cached_com_action`."""
    if task.startswith("check:"):
        cmd = _local_check.command(cmd, task)
    _run(cmd, label, log_stem=Path(stamp).stem, task=task)
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
        return _resolved(Path(f)).relative_to(REPO_ROOT).as_posix()
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


def _part_configuration_outputs(stem: str) -> list[Path]:
    """Exact member STEP/PNG/certificate outputs owned only by this part task."""
    from _part_configuration_exports import part_configuration_outputs

    return part_configuration_outputs(stem, CAD_OUT)


def _validate_part_configuration_outputs(stem: str, key: str) -> None:
    """Reject an incomplete or mismatched native/member set without retrying it.

    Validate after stamping every built/restored set, including a canonical
    publication winner adopted in place of a locally validated losing build.
    """
    from _part_configuration_exports import validate_member_exports

    try:
        validate_member_exports(stem, CAD_OUT)
    except (RuntimeError, ValueError) as exc:
        label = f"part:{stem}"
        raise RuntimeError(
            f"{label}: invalid member exports for cache key {key}: {exc}. "
            f"Investigate this cached set, then request an explicit forced cache "
            f"refresh of {label} with a reason; an ordinary retry restores the same key."
        ) from exc



def _part_cache_outputs(stem: str) -> list[Path]:
    """Native/STL/render outputs plus authoritative member STEP/PNG certificates."""
    png_dir = _png_dir(stem)
    return [
        Path(_sldprt(stem)), _stl(stem), png_dir,
        *(path for path in _part_configuration_outputs(stem) if png_dir not in path.parents),
    ]


def _assembly_cache_outputs(stem: str) -> list[Path]:
    """Everything an assembly build emits beyond its file_dep: the .SLDASM + renders,
    plus the per-stem extras a hit would otherwise leave missing/stale -- the top
    assembly's parts BOM (which export_gallery_and_bom writes into cad/out,
    OUTSIDE _png_dir).

    Includes the `.<stem>.massprops.sha` fingerprint sidecar (refresh_assembly's
    no-save key): it is machine-independent content (a geometry hash), so it MUST
    ride the cache -- else a clean cache consumer restores the .SLDASM without it,
    the next refresh takes the missing-sidecar path, force-saves a no-op .SLDASM,
    and reintroduces the parent-md5 cascade this whole mechanism exists to kill
    (codex review on #83). The input ledger (``_input_ledger``) rides it too: a
    restored assembly must say which inputs it was built from, or its next
    build could only rebuild it FULL."""
    sldasm = Path(_sldasm(stem))
    massprops = sldasm.parent / f".{sldasm.stem}.massprops.sha"
    # The free-DOF manifest sidecar (assemblies with freed operational DOF;
    # absent otherwise, skipped at pack time). It MUST ride the cache: a clean
    # cache consumer restores the .SLDASM without it and verify:kinematics
    # would then find no drive specs to author transiently and fail loud.
    dof = sldasm.parent / f".{sldasm.stem}.dof.json"
    outs = [sldasm, _png_dir(stem), massprops, dof, _input_ledger(stem)]
    if stem == "ha_harmonic_analyzer":
        outs.append(CAD_OUT / "ha-harmonic-analyzer-bom.csv")
    return outs


def _drawing_registry_dep(stem: str, registry: Path) -> str:
    """Selected row plus shared implementation; one-time drawing key migration."""
    recipe = drawing_registry_recipe(
        registry.read_text(encoding="utf-8"), DRAWINGS_BY_NAME[stem]
    )
    return _write_digest_sidecar(
        CAD_OUT / ".drawing-registry" / f"{stem}.digest",
        hashlib.md5(recipe.encode("utf-8")).hexdigest(),
    )


def _source_text_dep(label: str, deps: Iterable[str]) -> str:
    """A sidecar digest of the TEXT of the recipe code among ``deps``.

    ``ContentChecker`` folds recipe code by its syntax tree: all that a task
    which only RUNS the code can see. A task whose result also holds the text
    lists this sidecar beside its deps, so a comment, docstring or layout edit
    still moves it: recorded source hashes (``cam``), tests that read sources
    (``check:*``)."""
    h = hashlib.md5()
    sources = (dep for dep in set(deps) if dep.endswith(".py"))
    for tag, dep in sorted((_rel_tag(dep), dep) for dep in sources):
        text = source_text_digest(Path(dep))
        if text is not None:
            h.update(f"{tag}\0{text}\0".encode())
    return _write_digest_sidecar(
        CAD_OUT / ".source-text" / f"{label.replace(':', '-')}.digest", h.hexdigest()
    )


_FASTENER_CATALOG = (SCRIPTS_DIR / "_fastener_catalog.py").resolve()
# label -> the catalog rows its narrowed recipe folds (see _narrow_fastener_catalog).
_FASTENER_ROWS: dict[str, frozenset[str]] = {}


def _narrow_fastener_catalog(
    label: str, deps: list[str], own_row: str | None
) -> list[str]:
    """Swap ``_fastener_catalog.py`` for a digest of only the rows ``label`` reads.

    ``FASTENERS`` is a data registry: every catalogued part, its drawing and every
    assembly reaches it, so a one-row edit re-keyed ~97 leaves. When the task's
    whole Python closure reads the table only through ``fastener(...)``
    (``_buildgraph.fastener_rows_selected``), the dependency becomes a sidecar
    holding the shared code plus the selected rows, like ``_drawing_registry_dep``.
    ``_run_subprocess`` hands the same row set to the build as
    ``HARMONIC_FASTENER_ROWS`` and ``fastener`` refuses any other row, so a read
    the static analysis attributed wrongly fails loud instead of reusing a
    stale artefact. Anything unclassified keeps the whole file."""
    if str(_FASTENER_CATALOG) not in deps:
        return deps
    text = _FASTENER_CATALOG.read_text(encoding="utf-8")
    try:
        rows = frozenset(dict_table_entries(text, "FASTENERS"))
    except ValueError:
        return deps
    consumers = sorted(
        {Path(dep) for dep in deps if dep.endswith(".py")} - {_FASTENER_CATALOG}
    )
    selected = fastener_rows_selected(
        tuple(read_source(path) for path in consumers), own_row, rows
    )
    if selected is None:
        return deps
    _FASTENER_ROWS[label] = selected
    family, stem = label.split(":", 1)
    sidecar = _write_digest_sidecar(
        CAD_OUT / ".fastener-catalog" / f"{family}-{stem}.digest",
        hashlib.md5(
            dict_table_recipe(text, "FASTENERS", selected).encode("utf-8")
        ).hexdigest(),
    )
    return [sidecar if dep == str(_FASTENER_CATALOG) else dep for dep in deps]


def _fastener_rows_env(task: str) -> str | None:
    """The ``HARMONIC_FASTENER_ROWS`` value for ``task``'s build subprocess.

    ``task`` must be a doit task name (``part:x``, ``check:math``, ``release``).
    Only part, assembly and drawing recipes are narrowed, so any other task folds
    the whole catalog (when it reads it at all) and runs unguarded. A display
    label (``FULL build channel (...)``) or an unknown part/assembly/drawing stem
    raises: silently dropping the guard would let a read the static analysis
    missed publish under a key that does not fold its row.

    Recomputed from the task's own file_dep function when this process never
    built the graph (a ``doit -n`` worker), so the guard never depends on which
    process ran the task."""
    if not task or any(ch.isspace() for ch in task):
        raise ValueError(
            f"{task!r} is not a doit task name; pass the task the subprocess works "
            "for, or its fastener-row guard is lost"
        )
    family, _, stem = task.partition(":")
    if task not in _FASTENER_ROWS:
        if family == "part" and stem in part_stems():
            _part_file_deps(SCRIPTS_DIR / f"build_{stem}.py", stem)
        elif family == "assembly" and stem in ASSEMBLY_ORDER:
            _recipe_files(stem)
        elif family == "drawing" and stem in DRAWINGS_BY_NAME:
            _drawing_file_deps(stem)
        elif family in ("part", "assembly", "drawing"):
            raise ValueError(f"{task!r} names no {family} task; its fastener rows are unknown")
    rows = _FASTENER_ROWS.get(task)
    return None if rows is None else ",".join(sorted(rows))


def _drawing_file_deps(stem: str) -> list[str]:
    """Inputs for both doit freshness and the shared drawing-cache key.

    The part execution token carries the exact restored/built model identity. It
    prevents a drawing made against one set of SolidWorks persistent-reference IDs
    from hitting against a same-recipe part with different IDs.
    """
    spec = DRAWINGS_BY_NAME[stem]
    script = _resolved(spec.script)
    # Traverse first: helpers imported BY the registry must remain dependencies.
    runtime = _helper_deps(script)
    registry = _resolved(SCRIPTS_DIR / "_drawing_registry.py")
    if str(registry) in runtime:
        consumers = sorted({script, *(Path(path) for path in runtime)} - {registry})
        if drawing_registry_reads_selected(
            tuple(read_source(path) for path in consumers), stem
        ):
            runtime = [path for path in runtime if _resolved(Path(path)) != registry]
            runtime.append(_drawing_registry_dep(stem, registry))
    if spec.source_kind == "assembly":
        # Assembly-sourced drawings need the same exact-identity signal as
        # part-sourced drawings. The recipe-stable .SLDASM digest preserves
        # idempotency; its execution token catches a same-recipe rebuild with
        # new PIDs so the drawing cannot restore against a foreign identity.
        source_deps: tuple[str, ...] = (
            _sldasm(spec.part),
            _assembly_execution_token(spec.part),
        )
    else:
        source_deps = (_sldprt(spec.part), _part_execution_token(spec.part))
    deps = sorted(
        {
            str(script),
            str(RELEASE_VERSION_FILE),
            *source_deps,
            *runtime,
            # The cad/config rows the draw closure reads (Codex #936 T_oyK): a
            # sheet that prints another part's registry number must re-run, and
            # miss the cache, when that row changes without any geometry change.
            *_config_deps(script, spec.part, "drawing"),
            *(str(_resolved(path)) for path in spec.assets),
        }
    )
    return _narrow_fastener_catalog(f"drawing:{stem}", deps, spec.artifact_stem)


def _drawing_cache_outputs(stem: str) -> list[Path]:
    """Native drawing, every derived manufacturing output it emits, and its
    layout-audit report -- which rides the remote cache with the sheet, so a
    restored leaf still carries its findings and sheet dumps."""
    spec = DRAWINGS_BY_NAME[stem]
    return [_resolved(path) for path in (*spec.outputs.values(), spec.layout_report)]


# --- Inputs of the whole-machine COM stages (verify gates, neutral
# export, release packaging).
#
# Each is a cache-keyed COM leaf exactly like a part or an assembly, so ONE list is
# both doit's file_dep and the remote-cache key -- and `cache_status` reuses it to
# explain a miss. Every member MUST be machine-stable: repo files, the recipe-
# digested .SLDPRT/.SLDASM (immune to SolidWorks' save churn) and their execution
# tokens (exact CAD identity). A local absolute path or a timestamp here would make
# the submitter and the worker compute different keys, and every farm leaf would
# fail with "farm reported success but cache key ... is absent".
def _dof_json(stem: str) -> str:
    """The assembly's free-DOF manifest sidecar (gate input, not a build input)."""
    sldasm = Path(_sldasm(stem))
    return str(sldasm.parent / f".{sldasm.stem}.dof.json")


def _cad_identity_deps() -> list[str]:
    """Every built model plus its execution token -- the exact CAD identity the
    fleet-wide stages (neutral export, release packaging) consume. The token is
    what stops a same-recipe rebuild with fresh persistent-reference IDs from
    hitting a cache entry made against the previous identity."""
    deps: list[str] = []
    for stem in part_stems():
        deps += [_sldprt(stem), _part_execution_token(stem)]
    for stem in ASSEMBLY_ORDER:
        deps += [_sldasm(stem), _assembly_execution_token(stem)]
    return deps


def _soundness_file_deps(stem: str) -> list[str]:
    """One assembly's soundness-gate inputs: verify.py, the gate logic that lives
    outside every build closure, the assembly's OWN contract (its free-DOF sets decide the verdict,
    and verify.py is not run through ``_config_deps``), the assembly's OWN
    allowed-interference table with its import closure (verify.py resolves it
    by name at run time, so no import edge exposes it; it decides gate
    OUTCOMES, so an edit must re-run this gate even when no geometry moved,
    while another assembly's table never does), and the assembly itself with
    its execution token."""
    interference = interference_contract_file(stem)
    deps = [
        str(VERIFY_PY),
        str(POSTBUILD_PY),
        interference,
        *_helper_deps(interference),
        assembly_contract_file(stem),
        _sldasm(stem),
        _assembly_execution_token(stem),
    ]
    if stem == "pd_paper_drive":
        deps.append(_dof_json(stem))
    return deps


def _kinematics_file_deps() -> list[str]:
    """``verify:kinematics`` inputs.

    verify.py's gate LOGIC lives partly in _assembly_postbuild.py
    (load_dof_manifest/author_dof_drives -- the kinematics replays). Unlike
    verify's other helper imports (_assembly/focused helpers/build_*), that module is
    deliberately OUTSIDE every assembly recipe (it is on NO build script's
    closure), so a change to the replay logic does NOT bump any .SLDASM digest --
    and the .SLDASM deps below would then leave a fresh verify-kinematics.ok stamp
    valid, SKIPPING the gate (codex PR #193). Depend on it directly. The build_*
    helpers verify imports for constants need no such dep: they ride their
    .SLDPRT -> .SLDASM digest.

    The magnifier live-chain sweep (verify._verify_live_chain_one) opens
    mg-magnifier.SLDASM and authors its recorded lever drive spec transiently; the
    paper-feed proof (verify._verify_paper_feed_one) opens pd-paper-drive.SLDASM and
    drives the crank -- without those deps a rebuild of either would leave the
    stamp valid and SKIP the gates (codex #177/#189). The pen sweep + magnifier
    chain sweep read the .dof.json manifests directly (codex #221), and the
    transient pen equation reads _config VALUES through pen_driver/truth_model
    (machine/output.yaml + channels.yaml), which post-#221 are no longer on pen's
    build recipe -- so an amplitude edit would otherwise skip the sweep (codex
    #224). Those config deps are derived by the same static analyzer as the build
    recipes, so a new config read is picked up automatically.
    """
    return [
        str(VERIFY_PY),
        str(POSTBUILD_PY),
        _sldasm("pn_pen"),
        _assembly_execution_token("pn_pen"),
        _sldasm("mg_magnifier"),
        _assembly_execution_token("mg_magnifier"),
        _sldasm("pd_paper_drive"),
        _assembly_execution_token("pd_paper_drive"),
        _dof_json("pn_pen"),
        _dof_json("mg_magnifier"),
        str((SCRIPTS_DIR / "build_kinematic_probe.py").resolve()),
        str((SCRIPTS_DIR / "pen_driver.py").resolve()),
        str((SCRIPTS_DIR / "truth_model.py").resolve()),
        *_config_deps(SCRIPTS_DIR / "pen_driver.py"),
    ]


def _export_file_deps() -> list[str]:
    """Exporter runtime, every labelled feature STEP and inventory, and native identities."""
    return sorted({
        *_export_requirement_deps(),
        *(str(path) for path in _feature_bundle_outputs()),
        *(str(path.resolve()) for stem in part_stems()
          for path in _part_configuration_outputs(stem)),
        *_cad_identity_deps(),
    })


def _feature_exporter_deps(stem: str) -> list[str]:
    """The generic feature exporter and the config it reads for ``stem`` only:
    another part's registry row never re-keys this part's leaf."""
    sources = {
        EXPORT_PY.resolve(),
        *(Path(path).resolve() for path in module_deps_of(EXPORT_PY)),
    }
    return sorted({
        *(str(path) for path in sources),
        *(dep for path in sources if path.suffix == ".py"
          for dep in _config_deps(path, stem, "part")),
    })


def _feature_requirement_deps(stem: str) -> list[str]:
    """One part's declaration/citation closure and generic exporter inputs.

    Discovery identifies supported stems but never contributes another part's
    draw/spec files to this manifest. Config reads include dynamically loaded
    citation sources, not just imports the generic driver can see.
    """
    from export_features import source_paths

    sources = {path.resolve() for path in source_paths(stem)}
    return sorted({
        *_feature_exporter_deps(stem),
        *(str(path) for path in sources),
        *(dep for path in sources if path.suffix == ".py"
          for dep in _config_deps(path, stem, "part")),
    })


def _export_requirement_deps() -> list[str]:
    """Generic export runtime/config only; declarations belong to manifests."""
    return sorted({
        *_executed_closure([str(EXPORT_PY)]),
    })


def _feature_export_file_deps(stem: str) -> list[str]:
    """One labelled-STEP COM leaf's key: the generic exporter (and the config
    its closure reads for this part) and the exact native identity. No drawing
    declaration: a declaration edit never re-exports a STEP."""
    return sorted({
        *_feature_exporter_deps(stem),
        _sldprt(stem),
        _part_execution_token(stem),
    })


def _feature_manifest_file_deps(stem: str) -> list[str]:
    """One ``features.toml``: the declaration closure, the release revision,
    and the labelled STEPs and inventories it binds."""
    return sorted({
        *_feature_requirement_deps(stem),
        str(RELEASE_VERSION_FILE),
        *(str(path) for path in _feature_export_outputs(stem)),
    })


def _feature_export_outputs(stem: str) -> list[Path]:
    """One COM leaf's labelled STEPs, each followed by its face inventory."""
    from _export_feature_faces import inventory_path
    from export_features import exported_steps

    return [
        path.resolve()
        for step in exported_steps(stem, CAD_OUT)
        for path in (step, inventory_path(step))
    ]


def _feature_manifest_output(stem: str) -> Path:
    from export_features import bundle_paths

    return bundle_paths(stem, CAD_OUT)[0].resolve()


def _feature_bundle_outputs() -> list[Path]:
    """Every labelled STEP and inventory, for seat-free aggregate consumers."""
    from export_features import SUPPORTED_PARTS

    return [
        path for stem in SUPPORTED_PARTS for path in _feature_export_outputs(stem)
    ]


def _feature_manifest_outputs() -> list[Path]:
    from export_features import SUPPORTED_PARTS

    return [_feature_manifest_output(stem) for stem in SUPPORTED_PARTS]


def _export_cache_outputs() -> list[Path]:
    """What the export stage CERTIFIES, and therefore what it must ship.

    `release-neutral.json` records a sha256 and byte count for every file the
    bundle will contain -- each part's STEP + STL + isometric render, each
    assembly's GLB + render, each config mesh's STL, each scene JSON -- and
    `cut_release` refuses to stage a file whose bytes differ. So the cache entry
    MUST carry that whole inventory: a certificate written on a worker plus bytes
    taken from the submitter is exactly the "certify on machine A, ship machine B"
    hole it exists to close.

    The renders and per-part STLs are build-owned (a part leaf emits them; export
    only REPAIRS a missing one), so they are also part-cache outputs -- but that is
    not enough. doit's freshness is the recipe digest, deliberately immune to
    artefact bytes, so an up-to-date part task neither runs nor restores, and a
    submitter keeps whatever bytes its own older builds left. Renders in particular
    are NOT reproducible across seats (the window's pixel size sets the frame), so
    "equivalent by recipe" is not "the render we certified". v36's release failed
    on exactly that: `alignment-pinion_isometric.png` differed in size from the
    worker's certified copy.

    Cost, accepted: ~260 MB on top of the ~550 MB this entry already carries
    (step + gltf), duplicating bytes the part entries also hold. One transfer per
    export key buys a bundle whose every file is the one a single export validated.
    """
    return [
        (CAD_OUT / "step").resolve(),
        (CAD_OUT / "gltf").resolve(),
        (CAD_OUT / "boxes").resolve(),
        # The whole STL dir: per-part sidecars, per-config meshes, per-assembly
        # exports, plus colors.json and the export-src.json ledger.
        (CAD_OUT / "stl").resolve(),
        *(
            (_png_dir(stem) / f"{stem.replace('_', '-')}_isometric.png").resolve()
            for stem in (*part_stems(), *ASSEMBLY_ORDER)
        ),
        *(path.resolve() for stem in part_stems()
          for path in _part_configuration_outputs(stem)
          if path.suffix == ".png" and path.parent != _png_dir(stem)),
        (REPORTS / "release-neutral.json").resolve(),
    ]


def _package_file_deps() -> list[str]:
    """Release-packaging inputs: the Pack-and-Go script, the revision the title
    blocks carry, every model's exact identity, and every native drawing (each is
    Pack-and-Go'd with its references)."""
    return [
        str(PACKAGE_NATIVE_PY),
        str(RELEASE_VERSION_FILE),
        *_cad_identity_deps(),
        *(
            str(DRAWINGS_BY_NAME[stem].outputs["slddrw"].resolve())
            for stem in _drawing_order()
        ),
    ]


def _package_cache_outputs() -> list[Path]:
    """The prepared native tree cut_release.py copies into the release stage."""
    return [(CAD_OUT / "release" / "native").resolve()]


def _tag_cache_key(span: Any, key: str) -> None:
    """Name the cache key on a phase span (``cache.key``, its first 12 hex digits
    as ``cache.jsonl`` and the ``cache.*`` events print it). The sibling phase
    spans are separate root traces, so without it a build could only be tied to
    the key it produced by matching the next ``cache.store`` event on time."""
    span.set_attribute("cache.key", key[:12])


def _probe_cache(
    key: str, outputs: list[Path], label: str, span: Any, hit: str = "hit"
) -> str:
    """One remote-cache restore attempt for a phase span; returns its disposition.

    ``hit`` (or the caller's ``hit`` wording, e.g. ``hit-after-wait``) / ``miss`` /
    ``locked`` -- the last when the cached build exists but an output is
    share-locked by a document SolidWorks still holds
    (:class:`_artifact_cache.RestoreLocked`). A locked probe must NOT fall through
    to a local build (that forks the artefact's identity off the fleet's); the
    seat-holding caller releases the documents and re-probes instead. Under the
    farm executor the submitter holds no seat to release, so it fails loud.
    """
    _tag_cache_key(span, key)
    reason = _cache.forced_refresh(label)
    if reason is not None:
        _cache.note_refresh(label, key, reason)
        span.set_attribute("cache", "miss")
        return "miss"
    try:
        outcome = hit if _cache.restore(key, outputs, label) else "miss"
    except _cache.RestoreLocked:
        if _farm.enabled():
            raise
        outcome = "locked"
    span.set_attribute("cache", outcome)
    return outcome


def _release_seat_documents(label: str) -> None:
    """Free the cad/out documents a dead COM session left resident (share-locked).

    Runs ``release_seat_documents.py`` -- a ``run_build`` session with no work, so
    its connect-time discard + teardown close are the whole job -- HOLDING the
    seat, right before the under-seat re-probe. A crashed/killed build never
    reached its own teardown, which is the only other place documents are
    released; this is the recovery for that hole.
    """
    with _telemetry.span(
        f"sw.release_documents {label}",
        label=label,
        service=_telemetry.BUILD_INFRA_SERVICE,
    ):
        _sw_ensure_once()
        _exec_com(
            [sys.executable, str(SCRIPTS_DIR / "release_seat_documents.py")],
            f"release documents {label}",
            log_stem="release-seat-documents",
            task=label,
        )


def _reprobe_under_seat(
    key: str, outputs: list[Path], label: str, probed: str
) -> bool:
    """The under-seat re-probe every cached COM action runs: a peer may have
    published this exact artefact while we blocked for the seat, so restore it
    rather than rebuild (the fleet cache-split win; fable/codex review). Its OWN
    phase span, never inside the task span: it is another network round-trip, and
    on a hit a full download -- which would otherwise make the "work" span pure
    transfer. ``probed`` is the outside-seat disposition. Whichever probe first
    reads ``locked`` -- the outside one, or this one after a peer published
    while we queued -- gets ONE release of the seat's documents and one more
    probe; a probe still locked after the release is fatal.
    Returns True on a hit (the caller skips the build)."""
    released = False
    if probed == "locked":
        _release_seat_documents(label)
        released = True
    while True:
        with _telemetry.span(
            f"cache.reprobe {label}",
            label=label,
            service=_telemetry.BUILD_INFRA_SERVICE,
        ) as reprobe:
            outcome = _probe_cache(key, outputs, label, reprobe, hit="hit-after-wait")
        if outcome != "locked":
            return outcome == "hit-after-wait"
        if released:
            raise RuntimeError(
                f"{label}: cached outputs still share-locked after releasing the "
                "seat's documents -- close them in SolidWorks and rerun"
            )
        _release_seat_documents(label)
        released = True


def _adopt_canonical(key: str, outputs: list[Path], label: str) -> None:
    """A publication loser must leave the seat with the winner's whole archive."""
    with _com_seat(label):
        if not _reprobe_under_seat(key, outputs, label, "miss"):
            raise RuntimeError(
                f"{label}: lost cache publication but canonical outputs "
                f"could not be restored ({key[:12]})"
            )


@_farm.leaf_action
@_cache.keyed_action
def _cached_com_action(
    label: str,
    cmd: list[str],
    file_deps: list[str],
    outputs: list[Path],
    log_stem: str,
    stamp: str | None = None,
) -> None:
    """THE one way a COM subprocess runs: remote-cache probe, farm dispatch, or the
    local seat -- for every SolidWorks-touching task (parts, assemblies, drawings,
    the verify gates, the neutral export and the release Pack-and-Go).

    A HIT always skips the COM work. A MISS under the farm executor dispatches ONE
    leaf: the worker runs this same doit task with the cache in ``rw`` mode and
    publishes ``key``, which this side then restores -- so a machine with no
    SolidWorks seat can drive every stage of a release. A MISS locally takes the
    seat, re-probes in case a peer published while we queued, builds once, and
    publishes OUTSIDE the seat. The phase spans (``cache.probe`` /
    ``com.seat.wait`` / ``cache.reprobe`` / ``task`` / ``cache.store``) stay
    siblings, so queueing and network transfer can never be billed as work.

    ``stamp`` is the gate idiom: a task whose only output is
    ``cad/out/reports/<gate>.ok`` writes it HERE, after the gate passed, so a failed
    gate leaves no stamp (it stays stale and re-runs) while a cached gate restores
    the stamp instead of reopening the models. Every ``outputs`` path MUST live
    under ``cad/out`` -- the cache refuses to extract anything else."""
    with _telemetry.span(
        f"cache.probe {label}", label=label, service=_telemetry.BUILD_INFRA_SERVICE
    ) as probe:
        key = _cache_key(file_deps, label)
        probed = _probe_cache(key, outputs, label, probe)
        if probed == "hit":
            return

    if _farm.enabled():
        _farm_build(label, key, outputs)
        return

    with _com_seat(label) as waited:
        if _reprobe_under_seat(key, outputs, label, probed):
            return
        _sw_ensure_once()  # top-level sibling of the task span (once/worker)
        with _telemetry.span(
            f"task {label}", label=label, service=_stage_name(label)
        ) as sp:
            _tag_seat_wait(sp, waited)
            sp.set_attribute("cache", "miss")
            _tag_cache_key(sp, key)
            _exec_com(cmd, label, log_stem=log_stem)
            if stamp is not None:
                _write_stamp(label, stamp)

    # Publish OUTSIDE the seat -- an Azure upload is network, not COM, so it must
    # not hold the seat the next task is waiting for.
    _store_outputs(label, key, outputs)


def _store_outputs(label: str, key: str, outputs: list[Path]) -> None:
    """Publish a COM leaf's outputs under ``key`` (span ``cache.store``): a forced
    refresh must store (``_cache.require_refresh_store``), and a lost store
    adopts the winner's canonical outputs."""
    with _telemetry.span(
        f"cache.store {label}", label=label, service=_telemetry.BUILD_INFRA_SERVICE
    ) as store:
        _tag_cache_key(store, key)
        outcome = _cache.store(key, outputs, label)
        store.set_attribute("cache", outcome)
        _cache.require_refresh_store(label, outcome)
    if outcome == "lost":
        _adopt_canonical(key, outputs, label)


@_farm.leaf_action
@_cache.keyed_action
def _cached_drawing_action(stem: str) -> None:
    """Restore a matched part+drawing pair or build and publish the drawing."""
    spec = DRAWINGS_BY_NAME[stem]
    label = f"drawing:{stem}"
    file_deps = _drawing_file_deps(stem)
    outputs = _drawing_cache_outputs(stem)
    _cached_com_action(
        label,
        [sys.executable, str(spec.script.resolve()), spec.artifact_stem],
        file_deps,
        outputs,
        log_stem=f"drawing-{stem}",
    )


def _part_file_deps(script: Path, stem: str) -> list[str]:
    # The repo-owned part TEMPLATE is a runtime input of every part build
    # (_session._pin_default_part_template points the seat's default at it, so
    # NewPart inherits its document properties -- the DimXpert block-tolerance
    # get-only prefs ride it). Folding it in makes a template edit rebuild
    # every part AND shift the remote-cache key, so no seat can publish
    # template-drifted parts under a stale key.
    deps = [
        str(script.resolve()),
        str(RELEASE_VERSION_FILE),
        *_helper_deps(script),
        *_config_deps(script, stem, "part"),
        *data_deps_of(script),
        str(PART_TEMPLATE.resolve()),
    ]
    return _narrow_fastener_catalog(f"part:{stem}", deps, stem.replace("_", "-"))


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
        _assembly_execution_token(r)
        if r in ASSEMBLY_ORDER
        else _part_execution_token(r)
        for r in refs
    ]
    return [*_recipe_files(stem), *ref_targets, *ref_identities]


def _cache_key(file_deps: list[str], label: str | None = None) -> str:
    return _cache.cache_key(file_deps, ContentChecker._digest, label)


def _farm_build(label: str, key: str, outputs: list[Path]) -> None:
    """Build one cache-missing leaf on the farm, then restore its published key.

    The worker runs the same doit task with the cache in ``rw`` mode and stores
    ``key``; this side never takes the COM seat and never runs ``cache.store``.
    A farm failure is the task's failure (worker, category, exit code, log blob all
    in the message); a success whose key is still absent is an infrastructure
    fault and fails just as loud.

    ``farm_build.py`` runs this submitter from a private snapshot of the launch
    commit, so the key it computes is the one the worker publishes (#1114).
    """
    result = _farm.run_leaf(label, key)
    if result.state != "succeeded":
        failure = (
            f"{label} failed on {result.worker_id} [{result.failure_category}] "
            f"exit {result.exit_code}: {result.failure_message} "
            f"(log: {result.log_blob}) -- "
        )
        if result.failure_category == "cache_missing":
            failure += _farm.CACHE_MISSING_CAUSES + " -- "
        raise RuntimeError(
            failure
            # The worker's workspace is disposable, so a leaf's forensic
            # artefacts (failing document, seat BMP, capture.json) only exist as
            # blobs; name the command that fetches them, or the submitter has
            # nothing but this one-line message to diagnose from.
            + _failure_artefact_hint(result.log_blob)
        )
    with _telemetry.span(
        f"cache.restore {label}", label=label, service=_telemetry.BUILD_INFRA_SERVICE
    ) as restore:
        _tag_cache_key(restore, key)
        if not _cache.restore(key, outputs, label):
            raise RuntimeError(
                f"{label}: farm reported success but cache key {key[:12]} is "
                f"absent or failed integrity/restore -- {_farm.CACHE_MISSING_CAUSES}"
            )
        restore.set_attribute("cache", "hit")


@_farm.leaf_action
@_cache.keyed_action
def _cached_part_action(stem: str, script: Path) -> None:
    """Part action with a remote-cache shortcut: on a HIT the .SLDPRT (+ renders)
    are downloaded and the SolidWorks build is skipped; otherwise build, then push.
    Falls through to a normal build whenever the cache is off or errors.

    Opens its OWN spans HERE (rather than in _run) so every phase of the task is
    timed for what it is, and each carries the ``cache`` disposition + ``label``:
    ``cache.probe part:<stem>`` (the restore attempt -- on a HIT this IS the task,
    an Azure download, so the task never vanishes from the trace), the sibling
    ``com.seat.wait``/``task`` pair, and ``cache.store`` for the publish. The
    restore/store also record ``cache.hit``/``cache.miss``/``cache.store`` events, so
    a miss (and why the build ran) is backtraceable from the signals, not just the
    console."""
    label = f"part:{stem}"
    outputs = _part_cache_outputs(stem)
    with _telemetry.span(
        f"cache.probe {label}", label=label, service=_telemetry.BUILD_INFRA_SERVICE
    ) as probe:
        file_deps = _part_file_deps(script, stem)
        key = _cache_key(file_deps, label)
        probed = _probe_cache(key, outputs, label, probe)
        if probed == "hit":
            _stamp_part_execution(stem)
            _validate_part_configuration_outputs(stem, key)
            return

    if _farm.enabled():
        _farm_build(label, key, outputs)
        _stamp_part_execution(stem)
        _validate_part_configuration_outputs(stem, key)
        return

    with _com_seat(label) as waited:
        if _reprobe_under_seat(key, outputs, label, probed):
            _stamp_part_execution(stem)
            _validate_part_configuration_outputs(stem, key)
            return

        _sw_ensure_once()  # top-level sibling of the task span (once/worker)
        with _telemetry.span(
            f"task {label}", label=label, service=_stage_name(label)
        ) as sp:
            _tag_seat_wait(sp, waited)
            sp.set_attribute("cache", "miss")
            _tag_cache_key(sp, key)
            # Warn only once work starts, never for a probe or farm dispatch.
            if "_vn_" in stem:
                _telemetry.warn(
                    f"[vendor-part] Building {label} (cache key {key[:12]}); "
                    "vendor-part rebuilds should be rare: investigate the cache "
                    "provenance and refactor dependencies that cause unnecessary rebuilds.",
                    label=label,
                    key_full=key,
                    **{"cache.key": key[:12]},
                )
            _exec_com([sys.executable, str(script)], label, log_stem=f"part-{stem}")
            _stamp_part_execution(stem)
            _validate_part_configuration_outputs(stem, key)

    _publish_part(stem, key, outputs)


def _publish_part(stem: str, key: str, outputs: list[Path]) -> None:
    """Store a part's outputs under ``key``; a lost publication adopts the
    winner's whole archive."""
    label = f"part:{stem}"
    # Publish OUTSIDE the seat -- an Azure upload is network, not COM, so it must
    # not hold the seat the next task is waiting for.
    with _telemetry.span(
        f"cache.store {label}", label=label, service=_telemetry.BUILD_INFRA_SERVICE
    ) as store:
        _tag_cache_key(store, key)
        _validate_part_configuration_outputs(stem, key)
        outcome = _cache.store(key, outputs, label)
        store.set_attribute("cache", outcome)
        _cache.require_refresh_store(label, outcome)
    if outcome == "lost":
        _adopt_canonical(key, outputs, label)
        _stamp_part_execution(stem)
        _validate_part_configuration_outputs(stem, key)


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
    # An assembly that GENERATES parts in-script (none today, #1610; detected by
    # the same stamps_part_properties call-graph predicate the config tokens
    # use) instantiates the part TEMPLATE via
    # NewPart, so the template is a direct build input: fold it in so a
    # template edit FULL-rebuilds the generated parts and shifts the
    # assembly's cache key (codex #289 -- a cached assembly would otherwise
    # keep/restore parts built from the previous template). NON-generating
    # assemblies must NOT fold it: they get the template transitively through
    # their referenced parts' recipe digests (a template edit re-stamps the
    # parts -> shifted artefact digests -> REFRESH), and a direct fold would
    # escalate that refresh to a spurious ~500 s FULL rebuild.
    template = (
        [str(PART_TEMPLATE.resolve())] if stamps_part_properties(asm_script) else []
    )
    deps = [
        str(asm_script.resolve()),
        str(RELEASE_VERSION_FILE),
        *hooks,
        *_helper_deps(asm_script),
        *_config_deps(asm_script, stem, "assembly"),
        *template,
    ]
    return _narrow_fastener_catalog(f"assembly:{stem}", deps, None)


def _input_ledger(stem: str) -> Path:
    """Ledger of the per-input digests the last SUCCESSFUL build of <stem> was
    keyed from (``_cache.key_inputs`` over ``_assembly_file_deps``), next to the
    .SLDASM (cad/out, gitignored). build_or_refresh compares it with the current
    digests to choose the refresh tier, so the choice needs no process-local state
    and stays correct under ``doit -n`` workers (which may run the action in a
    separate process). Its tags are repo-relative and its digests the cache key's
    own, so it is machine-independent and rides the cache."""
    sldasm = Path(_sldasm(stem))
    return sldasm.parent / f".{sldasm.stem}.inputs.json"


def _read_input_ledger(path: Path) -> dict[str, str] | None:
    """A ledger's ``input -> digest`` map; None when absent or unreadable, which
    the tier choice treats as "unknown inputs" (FULL)."""
    try:
        recorded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    inputs = recorded.get("inputs") if isinstance(recorded, dict) else None
    if not isinstance(inputs, dict):
        return None
    return {str(tag): str(digest) for tag, digest in inputs.items()}


def _ledger_inputs(file_deps: list[str]) -> dict[str, str]:
    """``input tag -> digest`` exactly as the cache key folds ``file_deps``."""
    return dict(_cache.key_inputs(file_deps, ContentChecker._digest)[1])


def _write_input_ledger(path: Path, inputs: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"inputs": dict(sorted(inputs.items()))}, indent=1) + "\n",
        encoding="utf-8",
    )


def _assembly_tier(stem: str, target: str, current: dict[str, str]) -> tuple[RefreshTier, str]:
    """The tier that brings the saved ``target`` up to ``current`` inputs, and why
    (``_refresh_tier.classify_refresh`` over the recorded ledger)."""
    if not Path(target).exists():
        return RefreshTier.FULL, "target missing"
    recipe = frozenset(_rel_tag(path) for path in _recipe_files(stem))
    return classify_refresh(_read_input_ledger(_input_ledger(stem)), current, recipe)


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
# chokepoint -> doit staleness AND the remote cache key (also
# ContentChecker._digest) stay in
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


def _part_task(stem: str) -> dict[str, Any]:
    script = SCRIPTS_DIR / f"build_{stem}.py"
    return {
        "name": stem,
        "file_dep": _part_file_deps(script, stem),
        "targets": _canonical_targets(f"part:{stem}"),
        "uptodate": [
            _ExecutionIdentityTracker(_part_execution_token(stem)),
            not _cache.forced_refresh(f"part:{stem}"),
        ],
        # Remote-cache shortcut + COM seat lock wrap the build (_cached_part_action).
        "actions": [(_cached_part_action, [stem, script])],
        "clean": True,
        "verbosity": 2,
    }


def task_part():
    """One task per part stem; addressable as ``part:<stem>``.

    Parts have NO inter-part deps, so they carry no ``task_dep``: SolidWorks
    serialization is enforced at runtime by the COM seat lock inside
    ``_cached_part_action``, not by DAG edges. The tasks are YIELDED in per-seat
    order (``_seat_part_order``) as a best-effort scheduling hint so two cold
    builders diverge and split the fleet cache.
    """
    for stem in _seat_part_order():
        yield _part_task(stem)


# --- Recipe-change detection (the refresh tier), robust to failed tasks.
#
# doit injects a ``changed`` arg into the action listing this task's stale
# file_deps, but it is UNRELIABLE after an intervening task FAILS: it then
# falsely flags pristine recipe files (and omits the real change), forcing a
# spurious FULL (measured -- "D2"). Instead we track the recipe (assembly script
# / shared helper closure / hooks) with an ``uptodate`` callable modelled on doit's own
# ``config_changed``: it compares an md5 of the recipe CONTENT against the value
# saved on the last *successful* run (value_savers only fire on success), so a
# failed task never corrupts it. It also stashes the changed-bit into
# _RECIPE_CHANGED -- this drives the run/skip ``uptodate`` (and is asserted by
# test_dodo_recipe). The refresh-tier decision itself does not read this
# global: build_or_refresh recomputes it from an on-disk input ledger so it is
# correct under ``doit -n`` process workers (codex review).
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
        _RECIPE_CHANGED[self.stem] = last is None or last != self.digest
        return last is not None and last == self.digest


@_farm.leaf_action
@_cache.keyed_action
def build_or_refresh(stem, dependencies, changed, targets):
    """Bring one assembly stem up to date through the cheapest provable tier.

    The tier (``_assembly_tier`` -> ``_refresh_tier.classify_refresh``) compares
    the per-input digests the saved .SLDASM was keyed from (``_input_ledger``)
    with the current ones; a forced cache refresh (``_cache.forced_refresh``)
    is always FULL:

    * FULL (build_<stem>_assembly.py + any POST_ASSEMBLY hooks): the target or its
      ledger is missing, or a recipe input changed (assembly script / shared
      helper closure / config / a hook script);
    * PARTS (``refresh_assembly.py <stem> parts``, no hooks -- reopening
      preserves the existing configuration): only referenced parts changed.

    The decision is recomputed HERE from the on-disk ledger, NOT read from the
    _RECIPE_CHANGED module global: under ``doit -n`` the action may run in a
    worker process that never saw the parent's global, which would force a
    spurious FULL on every stale assembly and silently defeat the incremental
    refresh (codex review). The ledger is on disk (process-shared) and updated
    only on success. doit's own ``changed`` arg is likewise avoided -- it is
    corrupted by a prior failed task (D2).
    """
    label = f"assembly:{stem}"
    # Open the task span HERE (not in _run) so the cache decision + the tier's
    # build + any hooks share ONE trace rooted at this task: the cache events, the
    # tier ``mode`` attribute, and every subprocess span nest under it, so
    # a cache miss and the work it triggered are backtraceable from one trace.
    file_deps = _assembly_file_deps(stem)
    ledger = _input_ledger(stem)

    # Remote-cache shortcut: a HIT downloads the .SLDASM (+ renders, + the ledger
    # it was keyed from), skipping the COM build/refresh entirely. The ledger is
    # rewritten from the current inputs, exactly as the success tail does. The
    # per-input digests are taken only where a ledger is written or read.
    cache_outputs = _assembly_cache_outputs(stem)
    forced = _cache.forced_refresh(label) is not None
    with _telemetry.span(
        f"cache.probe {label}", label=label, service=_telemetry.BUILD_INFRA_SERVICE
    ) as probe:
        cache_key = _cache_key(file_deps, label)
        probed = _probe_cache(cache_key, cache_outputs, label, probe)
        if probed == "hit":
            _stamp_assembly_execution(stem)
            _write_input_ledger(ledger, _ledger_inputs(file_deps))
            return

    if _farm.enabled():
        _farm_build(label, cache_key, cache_outputs)
        _stamp_assembly_execution(stem)
        _write_input_ledger(ledger, _ledger_inputs(file_deps))
        return

    asm_script = SCRIPTS_DIR / f"build_{stem}_assembly.py"
    with _com_seat(label) as waited:
        if _reprobe_under_seat(cache_key, cache_outputs, label, probed):
            _stamp_assembly_execution(stem)
            _write_input_ledger(ledger, _ledger_inputs(file_deps))
            return

        current = _ledger_inputs(file_deps)
        # A forced refresh recomputes the result: never reload a local target.
        if forced:
            tier, why = RefreshTier.FULL, "forced cache refresh"
        else:
            tier, why = _assembly_tier(stem, targets[0], current)

        _sw_ensure_once()  # top-level sibling of the task span (once/worker)
        # The FULL+hooks (or a refresh) run HOLDING the seat, so the hooks operate
        # on the just-built model without another COM task interleaving.
        with _telemetry.span(
            f"task {label}", label=label, service=_stage_name(label)
        ) as sp:
            _tag_seat_wait(sp, waited)
            sp.set_attribute("cache", "miss")
            _tag_cache_key(sp, cache_key)
            sp.set_attribute("mode", tier.value)
            sp.set_attribute("mode_reason", why)

            if tier is RefreshTier.FULL:
                _exec_com(
                    [sys.executable, str(asm_script)],
                    f"FULL build {stem} ({why})",
                    log_stem=f"assembly-{stem}",
                    task=label,
                )
                for hook in (SCRIPTS_DIR / h for h in POST_ASSEMBLY.get(stem, ())):
                    _exec_com(
                        [sys.executable, str(hook)],
                        f"hook {hook.name}",
                        log_stem=f"hook-{stem}-{hook.stem}",
                        task=label,
                    )
            else:
                refresh = SCRIPTS_DIR / "refresh_assembly.py"
                _exec_com(
                    [sys.executable, str(refresh), stem, tier.value],
                    f"REFRESH {tier.value} {stem} ({why})",
                    log_stem=f"assembly-{stem}",
                    task=label,
                )
            # _exec raised if the build failed, so we only get here on success: record
            # this build's inputs for the next run's tier decision.
            _stamp_assembly_execution(stem)
            _write_input_ledger(ledger, current)
        # Same seat, saved model: the leaf proves its own soundness so the
        # verify_soundness:<stem> leaf restores the stamp instead of reopening.
        proved = _prove_soundness_in_leaf(stem)

    _publish_assembly(stem, cache_key, file_deps)
    if proved is not None:
        _publish_soundness(stem, proved)


def _publish_assembly(stem: str, key: str, file_deps: list[str]) -> None:
    """Store an assembly's outputs under ``key`` for other machines OUTSIDE the
    seat (an Azure upload is network, not COM). The output set is computed
    HERE, not taken from the task's start: the top-level gallery PNGs are
    glob-discovered and DID NOT EXIST yet on a clean builder then, so the
    early list would publish an incomplete archive (codex
    review). A lost publication adopts the winner's whole archive, re-stamps
    its token and rewrites the input ledger."""
    label = f"assembly:{stem}"
    outputs = _assembly_cache_outputs(stem)
    with _telemetry.span(
        f"cache.store {label}", label=label, service=_telemetry.BUILD_INFRA_SERVICE
    ) as store:
        _tag_cache_key(store, key)
        outcome = _cache.store(key, outputs, label)
        store.set_attribute("cache", outcome)
        _cache.require_refresh_store(label, outcome)
    if outcome == "lost":
        _adopt_canonical(key, outputs, label)
        _stamp_assembly_execution(stem)
        _write_input_ledger(_input_ledger(stem), _ledger_inputs(file_deps))


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

        adapter.connect()
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
    """Remove the .SLDASM target, its execution token, input ledger and
    png/<dashed> render dir."""
    _force_remove(Path(_sldasm(stem)))
    _force_remove(Path(_assembly_execution_token(stem)))
    _force_remove(_input_ledger(stem))
    _force_remove(CAD_OUT / "png" / stem.replace("_", "-"))


def _assembly_task(stem: str) -> dict[str, Any]:
    # Recipe = the files whose change forces a FULL rebuild (re-insert/re-mate)
    # vs a part-only refresh: the assembly script, its hooks, its helper
    # closure, AND the config docs THIS assembly reads (a placement like
    # channels.station_pitch_mm changing must re-insert components at new
    # coordinates, which an in-place reload cannot do; codex review #2).
    # Factored into _recipe_files so build_or_refresh computes the identical
    # digest.
    recipe_files = _recipe_files(stem)
    return {
        "name": stem,
        "file_dep": _assembly_file_deps(stem),
        "targets": _canonical_targets(f"assembly:{stem}"),
        "uptodate": [
            _RecipeTracker(stem, recipe_files),
            _ExecutionIdentityTracker(_assembly_execution_token(stem)),
            not _cache.forced_refresh(f"assembly:{stem}"),
        ],
        # No spine: ordering (parts + sub-assemblies before this one) comes from
        # the real file_dep on their targets above; SolidWorks serialization is
        # the COM seat lock inside build_or_refresh.
        "actions": [(build_or_refresh, [stem])],
        "clean": [(_clean_assembly, [stem])],
        "verbosity": 2,
    }


def task_assembly():
    """One task per assembly stem (``assembly:<stem>``).

    file_dep edges -- the assembly script, shared helper closure, this stem's hooks, and the
    referenced .SLDPRT/sub-.SLDASM targets -- give doit both ordering (top depends
    on the sub .SLDASMs, so it runs after) and the refresh/full decision (only
    parts changed -> refresh).
    """
    for stem in ASSEMBLY_ORDER:
        yield _assembly_task(stem)


def _clean_drawing(stem: str) -> None:
    for target in _drawing_cache_outputs(stem):
        _force_remove(target)


def _drawing_task(stem: str) -> dict[str, Any]:
    return {
        "name": stem,
        "file_dep": _drawing_file_deps(stem),
        "targets": _canonical_targets(f"drawing:{stem}"),
        "uptodate": [not _cache.forced_refresh(f"drawing:{stem}")],
        "actions": [(_cached_drawing_action, [stem])],
        "clean": [(_clean_drawing, [stem])],
        "verbosity": 2,
    }


def task_drawing():
    """Curated manufacturing drawings with identity-safe shared caching.

    A drawing depends on its authoritative source model (a part's SLDPRT or an
    assembly's SLDASM, per the registry row's ``source_kind``) plus explicitly
    declared drawing inputs. It is independently selectable as
    ``drawing:<stem>`` and deliberately excluded from ``build_bare``.
    """
    for stem in _drawing_order():
        yield _drawing_task(stem)


def _soundness_log_stem(stem: str) -> str:
    return f"verify-soundness-{stem.replace('_', '-')}"


def _soundness_stamp(stem: str) -> str:
    return str(REPORTS / f"{_soundness_log_stem(stem)}.ok")


def _soundness_command(stem: str) -> list[str]:
    return [sys.executable, str(VERIFY_PY), stem.replace("_", "-"), "--suite", "soundness"]


def _prove_soundness_in_leaf(stem: str) -> str | None:
    """Run ``verify_soundness:<stem>``'s battery on the assembly this leaf just
    saved, holding the same seat, and return the soundness key it proved.

    None when it did not prove one: the cache cannot publish (``ro``/off: the
    standalone leaf runs it as before), a forced soundness refresh (that leaf
    must probe its own key first), the key is already published (a no-op
    refresh that kept the token; the probe restored the stamp), or a gate
    failed. A failure is a WARN here, never an assembly failure: the assembly
    still publishes, and the standalone leaf misses, re-runs the battery and
    reports the failure exactly as before."""
    label = f"verify_soundness:{stem}"
    if not _cache.writable() or _cache.forced_refresh(label) is not None:
        return None
    key = _cache_key(_soundness_file_deps(stem), label)
    stamp = _soundness_stamp(stem)
    with _telemetry.span(
        f"cache.probe {label}", label=label, service=_telemetry.BUILD_INFRA_SERVICE
    ) as probe:
        if _probe_cache(key, [Path(stamp)], label, probe) == "hit":
            return None
    Path(stamp).unlink(missing_ok=True)
    _sw_ensure_once()  # the seat just ran the heaviest work: memory preflight
    with _telemetry.span(f"task {label}", label=label, service=_stage_name(label)) as sp:
        sp.set_attribute("cache", "in_leaf")
        _tag_cache_key(sp, key)
        try:
            _exec_com(
                _soundness_command(stem),
                label,
                log_stem=_soundness_log_stem(stem),
                task=label,
            )
        except RuntimeError as failed:
            sp.set_attribute("in_leaf", "failed")
            _telemetry.warn(
                f"{label}: in-leaf soundness failed ({failed}); the standalone "
                "leaf re-runs and reports it"
            )
            return None
    _write_stamp(label, stamp)
    return key


def _publish_soundness(stem: str, key: str) -> None:
    """Publish the in-leaf soundness stamp under ``key`` when it still describes
    the assembly on disk: a lost assembly publication that adopted another
    writer's different bytes re-stamped the execution token, so the soundness
    key moved and that proof is left to the standalone leaf."""
    label = f"verify_soundness:{stem}"
    if _cache_key(_soundness_file_deps(stem), label) != key:
        Path(_soundness_stamp(stem)).unlink(missing_ok=True)
        return
    _store_outputs(label, key, [Path(_soundness_stamp(stem))])


def _verify_soundness_task(stem: str) -> dict[str, Any]:
    deps = _soundness_file_deps(stem)
    stamp = _soundness_stamp(stem)
    cmd = _soundness_command(stem)
    return {
        "name": stem,
        "file_dep": deps,
        "targets": _canonical_targets(f"verify_soundness:{stem}"),
        "uptodate": [not _cache.forced_refresh(f"verify_soundness:{stem}")],
        "actions": [
            (
                _cached_com_action,
                [
                    f"verify_soundness:{stem}",
                    cmd,
                    deps,
                    [Path(stamp)],
                    _soundness_log_stem(stem),
                    stamp,
                ],
            )
        ],
        "clean": True,
        "verbosity": 2,
    }


def task_verify_soundness():
    """One independently stamped soundness gate per assembly, each a cache-keyed
    COM leaf whose stamp IS the cached output -- so a gate a peer (or a farm
    worker) already proved restores instead of reopening the model.

    A change to one assembly no longer invalidates a monolithic gate that reopens
    all nine models. The public ``verify:soundness`` task below aggregates these
    child stamps, preserving the existing CLI and release dependency.
    """
    for stem in ASSEMBLY_ORDER:
        yield _verify_soundness_task(stem)


def _verify_task(name: str) -> dict[str, Any]:
    if name == "soundness":
        child_stamps = [
            _soundness_stamp(stem)
            for stem in ASSEMBLY_ORDER
        ]
        soundness_stamp = str(REPORTS / "verify-soundness.ok")
        return {
            "name": "soundness",
            # The child stamps are targets of the verify_soundness:* tasks, so doit
            # derives the real producer edges from file_dep alone. The task_dep repeats
            # them for the FARM: the graph a worker receives is the task_dep CLOSURE of
            # the packaged scopes (doit's tasks_and_deps_iter walks task_dep, never
            # file_dep), so without it every dispatched verify_soundness:<stem> leaf is
            # refused as "not in the packaged graph".
            "task_dep": [f"verify_soundness:{stem}" for stem in ASSEMBLY_ORDER],
            "file_dep": [
                str(VERIFY_PY),
                str(POSTBUILD_PY),
                *child_stamps,
            ],
            "targets": _canonical_targets(f"verify:{name}"),
            "actions": [(_write_stamp, ["verify soundness", soundness_stamp])],
            "clean": True,
            "verbosity": 2,
        }
    if name == "kinematics":

        # Pass the graph's assemblies EXPLICITLY (dashed names) rather than letting
        # verify.py glob every *.SLDASM under cad/out/sldasm -- a stray/scratch
        # assembly left in a worktree must not be verified (codex review). kinematics
        # targets the pen + magnifier subs (verify.py's own defaults), no names.
        deps = _kinematics_file_deps()
        stamp = str(REPORTS / "verify-kinematics.ok")
        return {
            "name": "kinematics",
            "file_dep": deps,
            "targets": _canonical_targets(f"verify:{name}"),
            "uptodate": [not _cache.forced_refresh("verify:kinematics")],
            # No spine: the file_dep on the built .SLDASM orders this after the
            # assemblies; the COM seat lock (inside _cached_com_action) serializes it.
            "actions": [
                (
                    _cached_com_action,
                    [
                        "verify:kinematics",
                        [sys.executable, str(VERIFY_PY), "--suite", "kinematics"],
                        deps,
                        [Path(stamp)],
                        "verify-kinematics",
                        stamp,
                    ],
                )
            ],
            "clean": True,
            "verbosity": 2,
        }
    raise ValueError(f"unknown canonical task: verify:{name}")


def task_verify():
    """SolidWorks verification suites -- cache-keyed COM leaves: the seat lock
    serializes them locally, and under the farm executor each dispatches ONE leaf
    to a worker (the submitter needs no seat). Each stamps
    ``cad/out/reports/verify-<x>.ok`` on success, and that stamp is the cached
    output. The ``verify:`` prefix marks them SolidWorks-dependent (vs the
    SolidWorks-free ``check:`` tasks).
    """
    for name in _VERIFY_NAMES:
        yield _verify_task(name)


# Review inputs are independent of the draw recipe and registry. The CLI
# receives its PDF, package name and kind explicitly.
# Keep the review import closure pinned in the leaf tests.
_MACHINIST_REVIEW_MODULES = (
    "machinist_review.py",
    "machinist_review_config.py",
    "machinist_review_transport.py",
    "machinist_review_credentials.py",
    "machinist_review_sheets_mcp.py",
    "machinist_exceptions.py",
    "machinist_necessity.py",
    "_paths.py",
)


_ASSEMBLY_DOCUMENT = SCRIPTS_DIR / "ha_assembly_package.py"


def _steps_in_document() -> tuple[str, ...]:
    """``ha_assembly_package.STEPS_IN_DOCUMENT``, read statically: graph load
    imports no step or geometry module."""
    for node in ast.parse(read_source(_ASSEMBLY_DOCUMENT)).body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "STEPS_IN_DOCUMENT"
        ):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError("ha_assembly_package declares no STEPS_IN_DOCUMENT")


def _machinist_review_fitup_text(stem: str) -> Path | None:
    """The rendered ASSEMBLY.md fit-up section that an assembly review reads
    (rule 22, ``machinist_review._fitup_section``). None for a part, or a
    package whose steps still print on its sheets."""
    dashed = stem.removesuffix("_assembly").replace("_", "-")
    if (
        DRAWINGS_BY_NAME[stem].source_kind != "assembly"
        or dashed not in _steps_in_document()
    ):
        return None
    return Path(_canonical_targets(f"check:machinist_review_fitup:{stem}")[0]).resolve()


def _render_machinist_review_fitup(stem: str, target: Path) -> None:
    import ha_assembly_package

    dashed = stem.removesuffix("_assembly").replace("_", "-")
    text = "\n".join(ha_assembly_package.fitup_lines(dashed)).strip()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_file() or target.read_text(encoding="utf-8") != text:
        target.write_text(text, encoding="utf-8")


def _machinist_review_fitup_task(stem: str, target: Path) -> dict[str, Any]:
    """Render the section the review reads, on every run: it is cheap, and
    rendering it is the only exact dependency. The review is keyed on these
    bytes, not on the generator's code closure and config, so an edit that
    leaves the printed steps unchanged keeps the verdict."""
    return {
        "name": f"machinist_review_fitup:{stem}",
        "targets": _canonical_targets(f"check:machinist_review_fitup:{stem}"),
        "actions": [(_render_machinist_review_fitup, [stem, target])],
        "uptodate": [False],
        "clean": True,
    }


def _drawing_guidelines_version_dep() -> str:
    """The review's dependency on ``drawing-guidelines.md``: a sidecar holding
    only its frontmatter ``major_version``. Its review key and doit freshness
    both read this one file, so an edit that keeps the version re-keys no
    review and leaves every one fresh, and a bump re-keys them all. A missing
    or non-integer version fails the graph load. Other tasks that read the
    guidelines (``check:recipe``) keep hashing the whole file.

    Owner ruling 2026-11-17: "add a major version frontmatter to md file then
    rekey only when major version changes". A body edit without a bump is seen
    only by reviews that run for another reason; cached verdicts stand."""
    version, _body = split_drawing_guidelines(
        (SCRIPTS_DIR.parent / "docs" / "drawing-guidelines.md").read_text(
            encoding="utf-8"
        )
    )
    return _write_digest_sidecar(
        CAD_OUT / ".machinist-review" / "drawing-guidelines-major-version.digest",
        f"major_version={version}",
    )


def _machinist_review_prompts(kind: str) -> list[Path]:
    """Explicit per-kind prompt and schema inclusion list.

    Including only this kind's reviewer/severity files plus the shared judge
    prompt and schemas ensures adding or editing another kind's prompts
    (such as ``traveler``) never re-keys unrelated reviews."""
    prompts_dir = SCRIPTS_DIR / "prompts"
    names = (
        f"machinist_review_{kind}.md",
        f"machinist_review_{kind}_severity.md",
        "machinist_review_judge.md",
        "machinist_review_schema.json",
        "machinist_review_judge_schema.json",
    )
    return [prompts_dir / name for name in names]


def _machinist_review_file_deps(stem: str) -> list[str]:
    spec = DRAWINGS_BY_NAME[stem]
    dashed = stem.replace("_", "-")
    # The exception register is read by the review alone, like the necessity
    # register (rule 4); no SolidWorks leaf depends on either (#3663).
    register = CONFIG_DIR / "exceptions" / f"{dashed}.yaml"
    # TEMPORARY (#3663): a package not yet moved still declares in its build
    # contract (machinist_exceptions.legacy_path).
    if spec.source_kind == "part":
        unmoved = CONFIG_DIR / "parts" / f"{dashed}.yaml"
    else:
        unmoved = (
            CONFIG_DIR / "assemblies" / f"{dashed.removesuffix('-assembly')}.yaml"
        )
    necessity = CONFIG_DIR / "necessity" / f"{dashed}.yaml"
    # Selecting this kind's reviewer and severity contract also keys --kind
    # without hashing the registry. Judge instructions and schemas are shared.
    prompts = _machinist_review_prompts(spec.source_kind)
    fitup = _machinist_review_fitup_text(stem)
    return sorted({
        str(path.resolve())
        for path in (
            spec.outputs["pdf"],
            # Not pyproject.toml or uv.lock: the model, effort and prompts are
            # the verdict's inputs; an SDK or OMP release changes transport,
            # not judgement (#2882). The OMP binary was never keyed either.
            *(
                SCRIPTS_DIR / name
                for name in _MACHINIST_REVIEW_MODULES
                if name not in RECIPE_SKIP_MODULES
            ),
            *prompts,
            # The rubric is keyed by its major version, not its bytes.
            Path(_drawing_guidelines_version_dep()),
            *([register] if register.is_file() else []),
            *([unmoved] if unmoved.is_file() else []),
            *([necessity] if necessity.is_file() else []),
            *([fitup] if fitup else []),
        )
    })


def _machinist_review_key_deps(stem: str) -> list[str]:
    """``_machinist_review_file_deps`` once the fit-up section they name is
    rendered: a key computed outside the doit graph (the sweep, cache_status)
    hashes the text this tree prints, never a stale or missing file."""
    fitup = _machinist_review_fitup_text(stem)
    if fitup is not None:
        _render_machinist_review_fitup(stem, fitup)
    return _machinist_review_file_deps(stem)


def _machinist_review_dir(stem: str) -> Path:
    return (REPORTS / "machinist-review" / stem).resolve()


def _machinist_review_stamp(stem: str) -> Path:
    return REPORTS / f"check-machinist-review-{stem}.ok"


def _machinist_review_profile() -> ReviewProfile:
    return _MACHINIST_REVIEW_PROFILE


def _machinist_review_digest(profile: ReviewProfile):
    # The config module is a real review input. Its contextual digest records
    # both its actual source and the frozen effective profile, keeping normal
    # cache-key provenance instead of adding a virtual file or a post-hoc salt.
    config_path = (SCRIPTS_DIR / "machinist_review_config.py").resolve()
    effective = json.dumps(profile._asdict(), sort_keys=True, separators=(",", ":"))

    def digest(path: str) -> str:
        if Path(path).suffix.casefold() == ".pdf":
            # The reviewed sheet is keyed by the ink it prints: a rebuild that
            # prints the same sheet differs in export time, document ID and
            # font-subset tags, and must reuse its verdict (#2714). A file
            # PDFium cannot render keeps its byte digest.
            from _pdf_ink_digest import PdfInkError, pdf_ink_digest

            try:
                return pdf_ink_digest(path)
            except PdfInkError:
                pass
        # Review code keeps its byte digest: a verdict is keyed by the exact
        # reviewer program, and this key must not move with the recipes'.
        source = (
            _canonical_file_md5(path) if path.endswith(".py")
            else ContentChecker._digest(path)
        )
        if Path(path).resolve() == config_path:
            return hashlib.sha256(f"{source}\0{effective}".encode()).hexdigest()
        return source

    return digest


def _machinist_review_cache_key(
    stem: str, profile: ReviewProfile, label: str | None = None
) -> str:
    return _cache.cache_key(
        _machinist_review_key_deps(stem), _machinist_review_digest(profile), label
    )


def _store_reused_review(
    stem: str, key: str, directory: Path, label: str, **attributes: str
) -> str:
    """Store a verdict reused from another review under ``key``; on a lost
    publication another build published this key first, and its reports
    are adopted as canonical."""
    with _telemetry.span(
        f"cache.store {label}", label=label, service=_telemetry.BUILD_INFRA_SERVICE,
    ) as store:
        _tag_cache_key(store, key)
        for name, value in attributes.items():
            store.set_attribute(name, value)
        outcome = _cache.store(key, [directory], label)
        store.set_attribute("cache", outcome)
    if outcome == "lost":
        _adopt_canonical_review(stem, key, directory, label)
    return outcome


def _adopt_canonical_review(
    stem: str, key: str, directory: Path, label: str
) -> dict[str, Any]:
    """Replace this leaf's reports with those another build published under
    ``key`` first, and read their verdict. LEARN may soften a review verdict,
    never a failure to adopt the winning evidence: every failure is fatal."""
    try:
        shutil.rmtree(directory)
        if not _cache.restore(key, [directory], label):
            raise RuntimeError(
                f"{label}: lost cache publication but canonical reports "
                "could not be restored"
            )
        return _read_machinist_aggregate(stem)
    except (OSError, ValueError) as error:
        raise RuntimeError(f"{label}: could not adopt canonical reports: {error}") from error


def _machinist_review_context(stem: str, profile: ReviewProfile) -> str:
    """Cache key of every review input but the PDF: the scope in which a
    reviewed PDF's verdict may be carried to another sheet (_review_carry)."""
    pdf = str(Path(DRAWINGS_BY_NAME[stem].outputs["pdf"]).resolve())
    return _cache.cache_key(
        [dep for dep in _machinist_review_key_deps(stem) if dep != pdf],
        _machinist_review_digest(profile),
    )


def _carry_reviewed_verdict(
    stem: str, profile: ReviewProfile, key: str, directory: Path, label: str
) -> bool:
    """Reuse the verdict of a reviewed PDF of this drawing that this sheet
    prints the same as (#2714), recording where it came from and what
    differed. Anything that cannot be compared or restored reviews afresh."""
    import _review_carry

    pdf = Path(DRAWINGS_BY_NAME[stem].outputs["pdf"])
    with _telemetry.span(
        f"cache.carry {label}", label=label, service=_telemetry.BUILD_INFRA_SERVICE,
    ) as span:
        _tag_cache_key(span, key)
        try:
            carry = _review_carry.find(stem, _machinist_review_context(stem, profile), pdf)
        except OSError:
            carry = None
        if carry is None:
            span.set_attribute("cache", "miss")
            return False
        span.set_attribute("carried_from", carry.review_key)
        try:
            restored = _cache.restore(carry.review_key, [directory], label)
        except _cache.RestoreLocked as error:
            raise OSError(str(error)) from error
        try:
            if not restored or (directory / _review_carry.CARRIED_FILE).exists():
                raise ValueError("the reviewed verdict is not restorable")
            record = _review_carry.provenance(carry, _read_machinist_aggregate(stem))
        except (OSError, ValueError):
            shutil.rmtree(directory, ignore_errors=True)
            span.set_attribute("cache", "miss")
            return False
        span.set_attribute("cache", "hit")
    carried = directory / _review_carry.CARRIED_FILE
    carried.parent.mkdir(parents=True, exist_ok=True)
    carried.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    outcome = _store_reused_review(
        stem, key, directory, label, carried_from=carry.review_key
    )
    if outcome == "lost":
        # Another build published this key first; its reports, carried or
        # reviewed, replaced these and decide the verdict.
        _telemetry.info(f"{label}: carry lost to the verdict already published")
        return True
    _cache.record_event(
        "review_carried", label, key, from_key=carry.review_key,
        from_pdf_sha256=carry.pdf_sha256, verdict=record["carried_from"]["verdict"],
        difference=carry.comparison["pages"], store=outcome,
    )
    _telemetry.info(
        f"{label}: {record['carried_from']['verdict']} carried from review "
        f"{carry.review_key[:12]} (same sheet under the drawing-diff rule)"
    )
    return True


def _index_reviewed_pdf(
    stem: str, profile: ReviewProfile, key: str, directory: Path, label: str
) -> None:
    """Offer this leaf's PDF to later carries, unless its verdict was itself
    carried: carries are measured only against sheets the reviewers saw."""
    import _review_carry

    if (directory / _review_carry.CARRIED_FILE).exists():
        return
    try:
        _review_carry.index(
            stem, _machinist_review_context(stem, profile), key,
            Path(DRAWINGS_BY_NAME[stem].outputs["pdf"]),
        )
    except OSError as error:
        _telemetry.warn(f"{label}: reviewed PDF not indexed for carry-forward: {error}")


def _machinist_review_command(
    stem: str, profile: ReviewProfile, report_dir: Path | None = None
) -> list[str]:
    spec = DRAWINGS_BY_NAME[stem]
    return [
        sys.executable, str(SCRIPTS_DIR / "machinist_review.py"),
        "--pdf", str(spec.outputs["pdf"]), "--name", stem,
        "--kind", spec.source_kind, "--runs", "3",
        "--report-dir", str(report_dir or _machinist_review_dir(stem)),
        "--reviewer", profile.backend, "--model", profile.model,
        "--effort", profile.effort,
        "--judge-reviewer", profile.judge_backend, "--judge-model", profile.judge_model,
        "--judge-effort", profile.judge_effort,
    ]


def _read_machinist_aggregate(stem: str, directory: Path | None = None) -> dict[str, Any]:
    path = (directory or _machinist_review_dir(stem)) / f"{stem}.aggregate.json"
    aggregate = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(aggregate, dict)
        or aggregate.get("name") != stem
        or aggregate.get("kind") != DRAWINGS_BY_NAME[stem].source_kind
        or aggregate.get("verdict") not in ("SHIP", "FIX", "ERROR")
        or type(aggregate.get("gating_count")) is not int
        or aggregate["gating_count"] < 0
        or (aggregate.get("error") is not None
            and not isinstance(aggregate["error"], str))
    ):
        raise ValueError(f"{path}: invalid machinist aggregate")
    return aggregate


def _evaluate_machinist_review(
    stem: str, mode: MachinistReviewMode, aggregate: dict[str, Any]
) -> None:
    verdict = aggregate["verdict"]
    error = aggregate.get("error")
    if verdict == "SHIP" and error is None:
        return
    path = _machinist_review_dir(stem) / f"{stem}.aggregate.json"
    message = (
        f"check:machinist_review:{stem}: {verdict}, "
        f"gating_count={aggregate['gating_count']}; {path}"
    )
    if error:
        message += f"; {error}"
    no_verdict = verdict == "ERROR" or error is not None
    if mode is MachinistReviewMode.ENFORCE or (
        no_verdict and _cache.forced_refresh(f"check:machinist_review:{stem}") is not None
    ):
        raise RuntimeError(message)
    _telemetry.warn(message)


@_cache.keyed_action
def _cached_machinist_review_action(
    stem: str, mode: MachinistReviewMode, profile: ReviewProfile
) -> None:
    """Review on the submitter, caching verdicts BEFORE enforcing their policy.

    Cache the complete leaf directory, including attempt evidence and per-run
    reports: no transcripts or source snapshots are pruned from the payload.
    Provider/runner errors never publish and never leave a freshness stamp.
    """
    # An invalid profile does no work, not even taking the leaf's lock.
    validate_review_profile(profile)
    with _machinist_review_lock(stem):
        _machinist_review_leaf(stem, mode, profile)


def _machinist_review_lock(stem: str) -> FileLock:
    """Serializes the leaf of one drawing across processes: a review sweep of
    the sheet runs the same leaf on the same report directory (#2714)."""
    directory = _machinist_review_dir(stem)
    directory.parent.mkdir(parents=True, exist_ok=True)
    return FileLock(str(directory.with_name(f".{stem}.lock")))


def _machinist_review_leaf(
    stem: str, mode: MachinistReviewMode, profile: ReviewProfile
) -> tuple[str, dict[str, Any]]:
    """:func:`_cached_machinist_review_action` without its lock; returns the
    review key and the aggregate whose policy it evaluated."""
    # Validate direct action callers too, before removing stamps or probing.
    # Do not reselect defaults: this snapshot also owns the task's freshness.
    validate_review_profile(profile)
    label = f"check:machinist_review:{stem}"
    directory = _machinist_review_dir(stem)
    stamp = _machinist_review_stamp(stem)
    stamp.unlink(missing_ok=True)
    with _telemetry.span(
        f"cache.probe {label}", label=label, service=_telemetry.BUILD_INFRA_SERVICE
    ) as probe:
        key = _machinist_review_cache_key(stem, profile, label)
        try:
            # Restore into a clean evidence directory: an archive must not be
            # mixed with attempts retained under a previous input key.
            if directory.exists():
                shutil.rmtree(directory)
            probed = _probe_cache(key, [directory], label, probe)
        except (OSError, _cache.RestoreLocked) as error:
            aggregate = {"verdict": "ERROR", "gating_count": 0, "error": str(error)}
            _evaluate_machinist_review(stem, mode, aggregate)
            return key, aggregate
    try:
        if probed == "miss" and _cache.forced_refresh(label) is None:
            if _carry_reviewed_verdict(stem, profile, key, directory, label):
                probed = "hit"
        if probed != "hit":
            if probed == "locked":
                raise OSError(f"{label}: report outputs are locked")
            with _telemetry.span(
                f"task {label}", label=label, service=_stage_name(label)
            ) as work:
                _tag_cache_key(work, key)
                work.set_attribute("cache", "miss")
                code = _run_subprocess(
                    _machinist_review_command(stem, profile), label,
                    log_stem=f"machinist-review-{stem}", task=label,
                )
            aggregate = _read_machinist_aggregate(stem)
            if code not in (0, 1) or (code and aggregate["verdict"] == "SHIP"):
                raise ValueError(f"review command exited {code}")
            if aggregate["verdict"] != "ERROR" and aggregate.get("error") is None:
                with _telemetry.span(
                    f"cache.store {label}", label=label,
                    service=_telemetry.BUILD_INFRA_SERVICE,
                ) as store:
                    _tag_cache_key(store, key)
                    outcome = _cache.store(key, [directory], label)
                    store.set_attribute("cache", outcome)
                    _cache.require_refresh_store(label, outcome)
                if outcome == "lost":
                    aggregate = _adopt_canonical_review(stem, key, directory, label)
                if outcome in ("stored", "lost"):
                    _index_reviewed_pdf(stem, profile, key, directory, label)
        else:
            aggregate = _read_machinist_aggregate(stem)
            _index_reviewed_pdf(stem, profile, key, directory, label)
    except (OSError, ValueError) as error:
        aggregate = {"verdict": "ERROR", "gating_count": 0, "error": str(error)}
    _evaluate_machinist_review(stem, mode, aggregate)
    if aggregate["verdict"] != "ERROR" and aggregate.get("error") is None:
        _write_stamp(label, str(stamp))
    return key, aggregate


_MACHINIST_REVIEW_DEMOTIONS = CONFIG_DIR / "machinist-review" / "demoted.yaml"


def _demoted_reviews() -> frozenset[str]:
    """Drawings declared ``ENFORCE`` that run at ``LEARN`` until a batch
    converts their fits (``cad/config/machinist-review/demoted.yaml``, a
    mapping of drawing stem to the batch that removes the line; owner ruling
    2026-11-24: "Merge the policy now and demote the failing sheets to
    warn-only ... restoring enforcement per batch").

    Temporary (tracking issue #3511): an empty list fails the graph load, so
    the batch that deletes the last line deletes the file.

    The list lives here and not in the draw scripts because a draw script is
    its drawing's recipe input: editing the declaration rebuilds the sheet in
    SolidWorks. The mode feeds no review key and no recipe, so listing a
    sheet rebuilds and re-reviews nothing, and deleting its line restores
    enforcement the same way.
    """
    if not _MACHINIST_REVIEW_DEMOTIONS.is_file():
        return frozenset()
    doc = yaml.safe_load(_MACHINIST_REVIEW_DEMOTIONS.read_text(encoding="utf-8"))
    demoted = doc.get("demoted") if isinstance(doc, dict) and set(doc) == {"demoted"} else None
    if (
        not isinstance(demoted, dict)
        or not demoted
        or not all(
            isinstance(item, str) and item.strip()
            for pair in demoted.items()
            for item in pair
        )
    ):
        raise ValueError(
            f"{_MACHINIST_REVIEW_DEMOTIONS}: must hold one key 'demoted', a "
            "non-empty mapping of drawing stem to the batch that removes it; "
            "delete the file when no sheet is left"
        )
    return frozenset(demoted)


@functools.cache
def _reviewed_drawings() -> tuple[tuple[str, MachinistReviewMode], ...]:
    """Drawings opted in to machinist review, in build order.

    An undeclared (``OFF``) drawing gets no task: until its sheet stabilizes,
    reviewing it would spend model tokens on findings nobody acts on. A
    drawing on the demotion list runs at ``LEARN``; a listed stem that does
    not declare ``ENFORCE`` is a stale line and fails the graph load.
    """
    declared = {
        stem: mode_for_drawing(DRAWINGS_BY_NAME[stem].script)
        for stem in _drawing_order()
    }
    demoted = _demoted_reviews()
    stale = sorted(
        stem for stem in demoted
        if declared.get(stem) is not MachinistReviewMode.ENFORCE
    )
    if stale:
        raise ValueError(
            f"{_MACHINIST_REVIEW_DEMOTIONS}: not a drawing declared ENFORCE: {stale}"
        )
    return tuple(
        (stem, MachinistReviewMode.LEARN if stem in demoted else mode)
        for stem, mode in declared.items()
        if mode is not MachinistReviewMode.OFF
    )


def _machinist_review_task(
    stem: str, mode: MachinistReviewMode, profile: ReviewProfile
) -> dict[str, Any]:
    deps = _machinist_review_file_deps(stem)
    return {
        "name": f"machinist_review:{stem}",
        # The key folds the review code by bytes (_machinist_review_digest),
        # doit by syntax tree: the text sidecar, one for every sheet since they
        # share the code, keeps doit's freshness agreeing with the key.
        "file_dep": [*deps, _source_text_dep("check:machinist_review", deps)],
        # The real producer edge is the PDF file_dep. Repeating it in the
        # packaged task closure keeps a selected review's drawing admitted.
        "task_dep": [f"drawing:{stem}"],
        "uptodate": [
            config_changed({
                "mode": mode.value, "inputs": [_rel_tag(dep) for dep in deps],
                "profile": profile._asdict(),
            }),
            not _cache.forced_refresh(f"check:machinist_review:{stem}"),
        ],
        "targets": _canonical_targets(f"check:machinist_review:{stem}"),
        "actions": [(_cached_machinist_review_action, [stem, mode, profile])],
        "clean": True,
        "verbosity": 2,
    }


def _machinist_review_tasks():
    profile = _machinist_review_profile()
    reviewed = list(_reviewed_drawings())
    for stem, mode in reviewed:
        yield _machinist_review_task(stem, mode, profile)
    for stem, _mode in reviewed:
        fitup = _machinist_review_fitup_text(stem)
        if fitup is not None:
            yield _machinist_review_fitup_task(stem, fitup)


# --- Non-blocking machinist-review sweep (#2714) ---------------------------
# How old, in days, a review of a sheet's current ink may be before the sweep
# reviews that ink again; HARMONIC_REVIEW_SWEEP_DAYS overrides it.
_REVIEW_SWEEP_DAYS = 30
# This invocation's start: the summary reports only sheets swept since, so a
# record left by an earlier sweep never re-emits its findings.
_REVIEW_SWEEP_INVOKED = datetime.datetime.now(datetime.UTC).replace(microsecond=0)


def _review_sweep_dir() -> Path:
    return (REPORTS / "review-sweep").resolve()


def _review_sweep_days() -> int | None:
    """``HARMONIC_REVIEW_SWEEP_DAYS``: a positive whole number of days, or
    ``all`` (None: every selected sheet is reviewed)."""
    raw = os.environ.get("HARMONIC_REVIEW_SWEEP_DAYS", "").strip() or str(_REVIEW_SWEEP_DAYS)
    if raw == "all":
        return None
    if raw.isdecimal() and int(raw) > 0:
        return int(raw)
    raise ValueError(
        "HARMONIC_REVIEW_SWEEP_DAYS must be a positive whole number of days or "
        f"'all', not {raw!r}"
    )


def _reviewed_at(aggregate: dict[str, Any]) -> datetime.datetime | None:
    try:
        moment = datetime.datetime.fromisoformat(str(aggregate.get("reviewed_at")))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=datetime.UTC)


def _review_sweep_verdict(aggregate: dict[str, Any]) -> dict[str, Any]:
    return {
        "verdict": aggregate["verdict"],
        "gating_count": aggregate["gating_count"],
        "reviewed_at": aggregate.get("reviewed_at"),
        "error": aggregate.get("error"),
        "gating": [
            {key: item.get(key) for key in ("category", "where", "issue", "fix", "run_count")}
            for item in aggregate.get("confirmed", [])
            if isinstance(item, dict) and item.get("gating")
        ],
    }


def _review_sweep_action(stem: str, profile: ReviewProfile) -> None:
    """Sweep one sheet and record the outcome; never fails the invocation.

    First the build's own review leaf runs in LEARN: it restores, adopts or
    carries the sheet's verdict, or reviews an unreviewed ink and stores it
    under its key exactly as a build would. A sheet whose verdict is then a
    review of this ink no older than the sweep's age limit is done. Any other
    (carried, older, or ``all``) is reviewed again into the sweep's own report
    directory; that review never replaces the cached verdict, so a build's
    verdict changes only when its ink does.
    """
    import _review_carry

    days = _review_sweep_days()
    started = datetime.datetime.now(datetime.UTC).replace(microsecond=0)
    record: dict[str, Any] = {
        "stem": stem,
        "kind": DRAWINGS_BY_NAME[stem].source_kind,
        "swept_at": started.isoformat(),
        "days": "all" if days is None else days,
    }
    label = f"review_sweep:{stem}"
    try:
        with _machinist_review_lock(stem):
            record["review_key"], evaluated = _machinist_review_leaf(
                stem, MachinistReviewMode.LEARN, profile
            )
            if evaluated["verdict"] == "ERROR" or evaluated.get("error") is not None:
                raise ValueError(
                    f"review leaf: {evaluated.get('error') or 'ERROR verdict'}"
                )
            cached = _read_machinist_aggregate(stem)
            carried = (_machinist_review_dir(stem) / _review_carry.CARRIED_FILE).exists()
        record["cached"] = {**_review_sweep_verdict(cached), "carried": carried}
        reviewed_at = _reviewed_at(cached)
        if not carried and reviewed_at is not None and reviewed_at >= started:
            record["action"] = "reviewed"
        elif (
            not carried and reviewed_at is not None and days is not None
            and started - reviewed_at <= datetime.timedelta(days=days)
        ):
            record["action"] = "fresh"
        else:
            report_dir = _review_sweep_dir() / stem
            shutil.rmtree(report_dir, ignore_errors=True)
            with _telemetry.span(f"task {label}", label=label, service=_stage_name(label)):
                code = _run_subprocess(
                    _machinist_review_command(stem, profile, report_dir),
                    label, log_stem=f"review-sweep-{stem}",
                    task=f"check:machinist_review:{stem}",
                )
            review = _read_machinist_aggregate(stem, report_dir)
            # The build leaf's own consistency check.
            if code not in (0, 1) or (code and review["verdict"] == "SHIP"):
                raise ValueError(f"review command exited {code}")
            record["action"] = "re-reviewed"
            record["sweep"] = _review_sweep_verdict(review)
            if review["verdict"] == "ERROR" or review.get("error") is not None:
                record["error"] = f"review error: {review.get('error') or 'ERROR verdict'}"
    except Exception as error:  # noqa: BLE001 -- the sweep never fails a build
        record["error"] = f"{type(error).__name__}: {error}"
        _telemetry.warn(f"review_sweep:{stem}: {record['error']}")
    records = _review_sweep_dir() / "records"
    records.mkdir(parents=True, exist_ok=True)
    (records / f"{stem}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def _review_sweep_finding(record: dict[str, Any]) -> dict[str, Any] | None:
    """The fresh review of this sweep with gating findings, if any: the
    sweep's own review, or the leaf's when it reviewed the ink just now."""
    review = record.get("sweep") or (record["cached"] if record.get("action") == "reviewed" else None)
    if review and review["verdict"] == "FIX" and review["gating"]:
        return review
    return None


def _review_sweep_cell(text: Any) -> str:
    """Reviewer text as one Markdown table cell."""
    return " ".join(str(text).split()).replace("|", "\\|")


def _review_sweep_issue(record: dict[str, Any], review: dict[str, Any]) -> str:
    """A GitHub issue draft for one sheet's gating findings."""
    stem, cached = record["stem"], record["cached"]
    rows = "\n".join(
        f"| {number} | "
        + " | ".join(
            _review_sweep_cell(item[key])
            for key in ("category", "where", "issue", "fix", "run_count")
        )
        + " |"
        for number, item in enumerate(review["gating"], start=1)
    )
    return (
        f"# {stem}: machinist-review sweep findings ({record['swept_at'][:10]})\n\n"
        f"The sweep of {record['swept_at']} returned FIX for `{stem}` ({record['kind']}) "
        f"with {len(review['gating'])} gating finding(s). The build's cached verdict for "
        f"this ink is {cached['verdict']} (reviewed {cached['reviewed_at']}"
        f"{', carried' if cached['carried'] else ''}); the sweep did not replace it.\n\n"
        "Confirm every finding against the sheet before filing and delete the ones "
        "the sheet refutes.\n\n"
        "| # | category | where | finding | suggested fix | runs |\n"
        "|---|---|---|---|---|---|\n"
        f"{rows}\n\n"
        f"Review key `{record['review_key']}`; reports "
        f"`cad/out/reports/review-sweep/{stem}/` (or `machinist-review/{stem}/`).\n"
    )


def _write_review_sweep_summary() -> None:
    """Rewrite ``summary.{json,md}`` and ``issues/<stem>.md`` from the sheet
    records of this invocation, deleting older ones (a doit teardown: it runs
    in the main process after all tasks, once per swept sheet, and is
    idempotent)."""
    sweep = _review_sweep_dir()
    records = []
    for path in sorted((sweep / "records").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if datetime.datetime.fromisoformat(record["swept_at"]) >= _REVIEW_SWEEP_INVOKED:
            records.append(record)
        else:
            path.unlink()
    issues = sweep / "issues"
    shutil.rmtree(issues, ignore_errors=True)
    issues.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Machinist-review sweep", "",
        "| sheet | action | cached verdict | sweep verdict | gating | issue draft | error |",
        "|---|---|---|---|---|---|---|",
    ]
    for record in records:
        cached, sweep_review = record.get("cached"), record.get("sweep")
        review = _review_sweep_finding(record)
        draft = ""
        if review is not None:
            draft = f"issues/{record['stem']}.md"
            (sweep / draft).write_text(_review_sweep_issue(record, review), encoding="utf-8")
        record["issue_draft"] = draft or None
        cached_text = (
            f"{cached['verdict']} {cached['reviewed_at']}{' carried' if cached['carried'] else ''}"
            if cached else ""
        )
        lines.append(
            f"| {record['stem']} | {record.get('action', 'error')} | {cached_text} | "
            f"{sweep_review['verdict'] if sweep_review else ''} | "
            f"{len(review['gating']) if review else ''} | {draft} | {record.get('error') or ''} |"
        )
    counts = {
        "sheets": len(records),
        **{
            action: sum(record.get("action") == action for record in records)
            for action in ("fresh", "reviewed", "re-reviewed")
        },
        "errors": sum("error" in record for record in records),
        "issue_drafts": sum(bool(record["issue_draft"]) for record in records),
    }
    lines[1:1] = ["", ", ".join(f"{name} {count}" for name, count in counts.items())]
    (sweep / "summary.json").write_text(
        json.dumps({"counts": counts, "sheets": records}, indent=2) + "\n", encoding="utf-8"
    )
    (sweep / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def task_review_sweep():
    """Opt-in machinist-review sweep that never blocks a build (#2714).

    Not in ``build`` or ``release``. ``review_sweep`` sweeps every reviewed
    drawing, ``review_sweep:<stem>`` one. A sheet whose cached verdict is a
    review of its current ink no older than ``HARMONIC_REVIEW_SWEEP_DAYS``
    days (default 30; ``all`` sweeps every sheet) is skipped. A sheet with no
    verdict is reviewed by the build's own leaf and stored under its key, so a
    later build reuses it; any other is reviewed into
    ``cad/out/reports/review-sweep/<stem>/`` without replacing the cached
    verdict. FIX, findings and review errors never fail the invocation:
    ``review-sweep/summary.md`` lists them and ``issues/<stem>.md`` drafts one
    issue per sheet (DEVELOPING.md, "Machinist-review sweep")."""
    profile = _machinist_review_profile()
    for stem, _mode in _reviewed_drawings():
        yield _review_sweep_task(stem, profile)


def _review_sweep_task(stem: str, profile: ReviewProfile) -> dict[str, Any]:
    return {
        "name": stem,
        "task_dep": [f"drawing:{stem}"],
        "uptodate": [False],
        "actions": [(_review_sweep_action, [stem, profile])],
        "teardown": [(_write_review_sweep_summary,)],
        "verbosity": 2,
    }



def _executed_closure(cmd: list[str]) -> set[str]:
    """Source and config inputs of every Python entry point a command executes."""
    return {
        path
        for entry in (Path(arg) for arg in cmd if arg.endswith(".py"))
        for path in (
            str(entry.resolve()),
            *module_deps_of(entry),
            *_config_deps(entry),
        )
    }


# Offline tests are selected by collection, not enrollment: every ``test_*.py``
# that a bare ``pytest`` collects from pyproject's ``testpaths`` runs in exactly
# one gate. The gates below own the files they name; ``check:recipe`` runs the
# rest, so a new test file is gated by existing. A test file no gate may run
# goes in ``_UNGATED`` with its reason.
_UNGATED = frozenset(
    {
        # Runs the local FreeCAD install, which no build dependency tracks.
        "cad/scripts/test_as_machined_freecad.py",
        "cad/scripts/test_cam_nc_freecad.py",
        "cad/scripts/test_ch_rocker_strap_tl_sub_plate_cam_freecad.py",
    }
)
_GATE_TESTS: dict[str, tuple[str, ...]] = {
    "undefined_names": ("test_undefined_names.py",),
    "graph": (
        "test_buildgraph.py",
        "test_part_coverage.py",
        "test_assembly_sheet_isolation.py",
        "test_package_unit_declarations.py",
    ),
    "nameplate": ("test_fr_nameplate_geometry.py",),
    "numerals": ("test_dxf_text.py",),
    "cache": ("test_artifact_cache.py",),
    "telemetry": ("test_telemetry.py", "test_cut_release_telemetry.py"),
    "watchdog": ("test_watchdog.py",),
    "verify_telemetry": ("test_verify_telemetry.py",),
    "flagonly": ("test_flag_only.py",),
    "partiso": ("test_part_isolation.py",),
    "inert": ("test_recipe_inert.py",),
    "budget": ("test_error_budget.py",),
}


def _gate_tests(name: str) -> list[str]:
    return [str(SCRIPTS_DIR / test) for test in _GATE_TESTS[name]]


def _collected_tests() -> list[Path]:
    """Every gated test module a bare ``pytest`` collects (pyproject's
    ``testpaths`` minus ``norecursedirs``), less ``_UNGATED``."""
    import tomllib
    from fnmatch import fnmatch

    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        ini = tomllib.load(handle)["tool"]["pytest"]["ini_options"]
    collected = []
    for root in ini["testpaths"]:
        for path in (REPO_ROOT / root).rglob("test_*.py"):
            dirs = path.relative_to(REPO_ROOT / root).parts[:-1]
            if path.relative_to(REPO_ROOT).as_posix() in _UNGATED or any(
                fnmatch(part, pattern) for part in dirs for pattern in ini["norecursedirs"]
            ):
                continue
            collected.append(path)
    return sorted(collected)


def _check_recipe_spec(pytest_cmd: list[str]) -> dict[str, Any]:
    import _cam_programs
    import _process_plans
    import _shop_equipment

    review_bench = REPO_ROOT / "tools" / "machinist-review-evals" / "machinist_review_bench.py"
    owned = {SCRIPTS_DIR / test for tests in _GATE_TESTS.values() for test in tests}
    recipe_tests = [path for path in _collected_tests() if path not in owned]
    # These are runtime-read rather than imported, so module_deps_of cannot
    # discover them. A prompt/schema edit must invalidate check:recipe and rerun
    # the offline machinist-review contract.
    machinist_review_contract_deps = [
        # Reviewer and judge prompts/schemas are read at runtime.
        SCRIPTS_DIR.parent / "docs" / "drawing-guidelines.md",
        SCRIPTS_DIR.parent / "docs" / "traveler-guidelines.md",
        *(path for path in (SCRIPTS_DIR / "prompts").iterdir() if path.is_file()),
        # test_dt_cone_pivot_post_drawing reads the policy's GD&T allowlist;
        # allowlist edits must rerun its frame-ownership contract.
        SCRIPTS_DIR.parent / "docs" / "drawing-simplicity-policy.md",
    ]
    # test_out_param_binding SCANS sources instead of importing them (it reads
    # every top-level build script and every diagnostics/*.py looking for
    # VT_BYREF), so module_deps_of cannot see them -- an import graph does not
    # cover a file the test merely opens. Without these, the first green stamp
    # would freeze the gate: adding a VT_BYREF to a build script, or an unmarked
    # late-bound probe, leaves check:recipe "up to date" and the enforcement
    # silently stops enforcing (codex #418). Same failure shape as the
    # never-enrolled contract test above -- a green gate that checks nothing.
    scanned_by_binding_gate = {
        *(str(_resolved(path)) for path in SCRIPTS_DIR.glob("*.py")),
        *(str(_resolved(path)) for path in (SCRIPTS_DIR / "diagnostics").glob("*.py")),
    }
    # Drawing regressions read captured native sheet dumps at runtime.
    captured_fixtures = sorted(
        str(path.resolve()) for path in (SCRIPTS_DIR / "fixtures").glob("*.json")
    )
    recipe_test_deps = sorted(
        {
            # Pytest discovers shared fixtures outside the import closure.
            str((REPO_ROOT / "conftest.py").resolve()),
            *(str(path.resolve()) for path in recipe_tests),
            *(dep for path in recipe_tests for dep in module_deps_of(path)),
            # Reference DXFs a test reads through its imports (test_base_serial).
            # Tests also quote fake DXF names, so keep only committed files.
            *(
                dep
                for path in recipe_tests
                for dep in data_deps_of(path)
                if Path(dep).is_file()
            ),
            # The vm2 datum tests pin their committed probe receipts.
            *(
                str(path.resolve())
                for path in (
                    REPO_ROOT / "cad" / "docs" / "pipeline" / "evidence" / "vm2-datum-placement" / "probes"
                ).glob("*/receipt.json")
            ),
            *(str(path.resolve()) for path in machinist_review_contract_deps),
            # module_deps_of resolves only cad/scripts modules: name the
            # out-of-tree benchmark harness its test imports, and its imports.
            str(review_bench.resolve()),
            *module_deps_of(review_bench),
            *scanned_by_binding_gate,
            # Supplier native regressions read captured shelf facts.
            str((SCRIPTS_DIR / "testdata" / "supplier_top_r44.json").resolve()),
            # Carry-forward tests compare real build PDFs read at runtime.
            *(
                str(path.resolve())
                for path in (SCRIPTS_DIR / "testdata" / "review-carry").glob("*.pdf")
            ),
            # Shop-equipment contracts read the tracked shop records at runtime.
            *(str(path.resolve()) for path in _process_plans.shop_files()),
            *(str(path.resolve()) for path in _shop_equipment.files()),
            # test_measured_cuts reads the dechatter reports and results files
            # measured-cuts.toml names.
            *(
                str(path.resolve())
                for pattern in ("*.html", "*.json")
                for path in sorted((_process_plans.PROCESS_ROOT / "dechatter").glob(pattern))
            ),
            # test_cam_nc loads each CAM recipe by path (importlib, outside
            # cad/scripts); process tests read every plan at runtime, and a
            # plan's presence enrols it (_process_plans.enrolled_stems).
            # test_process_op_references also reads every plan's picture SVGs.
            *(str(_cam_programs.recipe_path(stem).resolve()) for stem in _cam_programs.CAM_STEMS),
            *(
                str(path.resolve())
                for pattern in ("*/plan.toml", "*/diagrams/*.svg")
                for path in sorted(_process_plans.PROCESS_ROOT.glob(pattern))
            ),
            # module_deps_of only walks cad/scripts; comparison tests import
            # sibling tools (and load render_diff via importlib) outside it.
            *(
                str((REPO_ROOT / "cad" / "comparisons" / "tools" / name).resolve())
                for name in (
                    "composite.py",
                    "pose_manifest.py",
                    "render_offline.py",
                    "release_diff.py",
                    "render_diff.py",
                    "pose_to_meshprobe.py",
                    "seed_manifest.py",
                )
            ),
            # test_pytest_scope reads pytest's own configuration.
            str((REPO_ROOT / "pyproject.toml").resolve()),
            # Root farm tests import farm_build.py, outside module_deps_of.
            str((REPO_ROOT / "farm_build.py").resolve()),
            # Release pairing tests compose the current and sealed identity maps.
            str(
                (REPO_ROOT / "cad" / "config" / "identity-migration-map.json").resolve()
            ),
            str(
                (REPO_ROOT / "cad" / "config" / "current-identity-map.json").resolve()
            ),
            # test_picture_clip and the prechips_traveler tests read the
            # picture-clip ratchet baseline.
            str(
                (REPO_ROOT / "cad" / "config" / "picture-clip-baseline.toml").resolve()
            ),
            # test_check_register reads every check and necessity register.
            *(
                str(path.resolve())
                for family in ("checks", "necessity")
                for path in sorted((REPO_ROOT / "cad" / "config" / family).glob("*.yaml"))
            ),
            *captured_fixtures,
        }
    )
    return {
        # _CONFIG_YAMLS: the metadata-ownership contracts read part rows via
        # _config.parts(), and module_deps_of tracks _config.py but not the
        # YAML documents it loads -- without these deps a finish/material
        # edit would leave the stamp valid and the guard silently stale
        # (codex review #361).
        "file_dep": [
            str((REPO_ROOT / "dodo.py").resolve()),
            str((REPO_ROOT / "build.py").resolve()),
            # Pytest hooks/child startup sit outside the cad/scripts import
            # map, so the executed closure cannot discover these inputs.
            str((REPO_ROOT / "conftest.py").resolve()),
            str((REPO_ROOT / "tests" / "_child_guard" / "sitecustomize.py").resolve()),
            str(
                (REPO_ROOT / "tests" / "_child_guard" / "harmonic_solidworks_guard.py")
                .resolve()
            ),
            *recipe_test_deps,
            *_CONFIG_YAMLS,
            *sorted(
                str(template.path.resolve())
                for template in DRAWING_TEMPLATES.values()
            ),
        ],
        # Repo-relative (the gate runs with cwd=REPO_ROOT): ~290 absolute
        # paths under a farm-run snapshot root exceed Windows' 32,767-char
        # command line (WinError 206), failing the gate before pytest runs.
        "cmd": [
            *pytest_cmd,
            # Fixed explicit inventory: skip repeated parent-directory
            # virtualenv-marker probes, not general discovery exclusions.
            "--collect-in-virtualenv",
            # Request up to eight workers; local admission reduces this
            # to available host CPU slots. Remote leaves have their own budget.
            # Steal individual tests to avoid a dominant-file tail.
            "-n",
            "8",
            "--dist",
            "worksteal",
            *(
                str(path.resolve().relative_to(REPO_ROOT.resolve()))
                for path in recipe_tests
            ),
        ],
        # A deleted/renamed source drops out of file_dep without comparison.
        # Keep inventories for both the adapter and source-scanning recipe
        # guards so additions/removals cannot leave an old green stamp.
        "uptodate": [
            config_changed(
                {
                    "recipe_tests": [_rel_tag(str(path)) for path in recipe_tests],
                    "recipe_scanned_sources": [
                        _rel_tag(path) for path in sorted(scanned_by_binding_gate)
                    ],
                    "recipe_captured_fixtures": [
                        _rel_tag(path) for path in captured_fixtures
                    ],
                }
            )
        ],
    }


def _check_undefined_names_spec(pytest_cmd: list[str]) -> dict[str, Any]:
    tracked_python = [
        str((REPO_ROOT / path).resolve())
        for path in subprocess.check_output(
            [
                "git",
                "ls-files",
                "--cached",
                "-z",
                "--",
                "cad/scripts",
                "dodo.py",
                "build.py",
                "farm_build.py",
            ],
            cwd=REPO_ROOT,
        ).decode("utf-8").split("\0")
        if path.endswith(".py")
    ]
    return {
        # Ruff scans the entire scripts tree, not only import-reachable modules.
        # Depend on every tracked Python input so a fresh typo invalidates the stamp.
        "file_dep": sorted(
            {
                *tracked_python,
                str((SCRIPTS_DIR / "test_undefined_names.py").resolve()),
            }
        ),
        "cmd": [*pytest_cmd, *_gate_tests("undefined_names")],
    }


def _check_math_spec(pytest_cmd: list[str]) -> dict[str, Any]:
    config_py = str((SCRIPTS_DIR / "_config.py").resolve())
    return {
        # The import closure of verify.py (truth_model, the base-footprint
        # build modules and the *_spec.py single-source modules they import,
        # build_summing_assembly for the counter-spring hang, ...) is derived
        # below from the command's entry point, like every gate's. Only the
        # YAML layer truth_model reads outside the _config accessors is
        # declared here (codex review).
        "file_dep": [config_py, *_CONFIG_YAMLS],
        "cmd": [sys.executable, str(VERIFY_PY), "--suite", "math"],
    }


def _check_config_spec(pytest_cmd: list[str]) -> dict[str, Any]:
    config_py = str((SCRIPTS_DIR / "_config.py").resolve())
    part_script_deps = [str(p.resolve()) for p in part_scripts()]
    return {
        "file_dep": [
            str(VERIFY_PY),
            str((SCRIPTS_DIR / "gen_dimensions.py").resolve()),
            config_py,
            *_CONFIG_YAMLS,
            *part_script_deps,
        ],
        "cmd": [sys.executable, str(VERIFY_PY), "--suite", "config"],
    }


def _check_graph_spec(pytest_cmd: list[str]) -> dict[str, Any]:
    config_py = str((SCRIPTS_DIR / "_config.py").resolve())
    part_script_deps = [str(p.resolve()) for p in part_scripts()]
    return {
        # test_config_accessor_coverage reads _config.py, so a new accessor
        # added there (without an entry in _buildgraph) must invalidate this
        # stamp -- else the "fails loud" coverage test silently never re-runs
        # and the perf benefit is lost (codex review #193).
        "file_dep": [
            str((SCRIPTS_DIR / "_buildgraph.py").resolve()),
            str((SCRIPTS_DIR / "test_buildgraph.py").resolve()),
            str((SCRIPTS_DIR / "test_part_coverage.py").resolve()),
            *part_script_deps,
            *(str(script_for(stem).resolve()) for stem in ASSEMBLY_ORDER),
            # test_assembly_sheet_isolation walks every builder's import
            # closure and scans the sheet/steps sources; it imports none.
            *(
                dep
                for stem in ASSEMBLY_ORDER
                for dep in module_deps_of(script_for(stem))
            ),
            *(
                str(path.resolve())
                for pattern in ("*_assembly_sheet.py", "*_steps.py")
                for path in sorted(SCRIPTS_DIR.glob(pattern))
            ),
            config_py,
            # test_package_unit_declarations reads every package's own raw
            # drawing_unit row (#290 explicit declarations).
            str((SCRIPTS_DIR / "test_package_unit_declarations.py").resolve()),
            *parts_registry_files(),
            *assembly_contract_files(),
            # test_part_coverage counts a tier-1 hardware.yaml row as the
            # part's deliverable (#2886).
            str((CONFIG_DIR / "hardware.yaml").resolve()),
        ],
        "cmd": [*pytest_cmd, *_gate_tests("graph")],
    }


def _check_nameplate_spec(pytest_cmd: list[str]) -> dict[str, Any]:
    return {
        # The plate outline, the etched field and the resist are all vendored
        # geometry; any contour or its pinned area/bbox must invalidate this
        # SolidWorks-free integrity gate.
        "file_dep": [
            str((SCRIPTS_DIR / "test_fr_nameplate_geometry.py").resolve()),
            str((SCRIPTS_DIR / "fr_nameplate_spec.py").resolve()),
            str((SCRIPTS_DIR / "build_fr_nameplate.py").resolve()),
            str((SCRIPTS_DIR / "fr_nameplate_drawing_spec.py").resolve()),
            str(
                (
                    REPO_ROOT / "cad" / "references" / "fr-nameplate-resist.dxf"
                ).resolve()
            ),
            str(
                (
                    REPO_ROOT / "cad" / "references" / "fr-nameplate-outline.dxf"
                ).resolve()
            ),
            str(
                (
                    REPO_ROOT / "cad" / "references" / "fr-nameplate-field.dxf"
                ).resolve()
            ),
            str(
                (
                    REPO_ROOT / "cad" / "references" / "fr-nameplate-letters.dxf"
                ).resolve()
            ),
        ],
        "cmd": [*pytest_cmd, *_gate_tests("nameplate")],
    }


def _check_numerals_spec(pytest_cmd: list[str]) -> dict[str, Any]:
    return {
        # Guards the GENERATED numerals DXFs (one per stroke layer) the
        # ms-stick build imports: byte-identical regeneration from
        # gen_ms_stick_numerals_dxf, closed-loop census, clearance from every
        # tick, and the bbox/volumes the build pins.
        # Deps: the test, the assets, the generator/build/font-render modules it
        # imports (module_deps_of) AND the cad/config files those modules read
        # (_config_deps -> machine/amplitude.yaml, which now owns the engraved
        # scale) -- so a layout-constant OR scale-config edit that forgot to
        # regenerate the DXF fails this gate instead of reusing its stamp. The
        # layer DXFs come from ms_stick_spec.NUMERAL_LAYER_DXFS (data_deps_of).
        "file_dep": [
            str((SCRIPTS_DIR / "test_dxf_text.py").resolve()),
            *module_deps_of(SCRIPTS_DIR / "test_dxf_text.py"),
            *_config_deps(SCRIPTS_DIR / "test_dxf_text.py"),
            *data_deps_of(SCRIPTS_DIR / "test_dxf_text.py"),
        ],
        "cmd": [*pytest_cmd, *_gate_tests("numerals")],
    }


def _check_cache_spec(pytest_cmd: list[str]) -> dict[str, Any]:
    return {
        # The artefact-cache provenance/observability unit tests (issue #73):
        # key derivation, event log, store-skip-on-hit drift. Pure python.
        "file_dep": [
            str((SCRIPTS_DIR / "_artifact_cache.py").resolve()),
            str((SCRIPTS_DIR / "test_artifact_cache.py").resolve()),
        ],
        "cmd": [*pytest_cmd, *_gate_tests("cache")],
    }


def _check_telemetry_spec(pytest_cmd: list[str]) -> dict[str, Any]:
    return {
        # The OTel observability spine: severity split, no-gap span status,
        # log<->trace correlation, cross-process propagation, plus the release
        # neutral-export aggregate/event shape. Pure python, so it runs as an
        # offline gate -- without this the spine or release observability could
        # regress while the required checks stay green.
        "file_dep": [
            str((SCRIPTS_DIR / "_telemetry.py").resolve()),
            str((SCRIPTS_DIR / "cut_release.py").resolve()),
            str((SCRIPTS_DIR / "export_models.py").resolve()),
            str((SCRIPTS_DIR / "test_telemetry.py").resolve()),
            str((SCRIPTS_DIR / "test_cut_release_telemetry.py").resolve()),
        ],
        "cmd": [*pytest_cmd, *_gate_tests("telemetry")],
    }


def _check_watchdog_spec(pytest_cmd: list[str]) -> dict[str, Any]:
    return {
        # The COM crash/hang watchdog (_watchdog.py): a NEW sldexitapp.exe
        # (SolidWorks' crash-report dialog) or 15 min of telemetry silence
        # hard-exits the COM subprocess (releasing the seat via the doit
        # parent); a hung SW window only warns. Pure python, injectable
        # probes -- so the fatal/log-only contract can't silently regress.
        # The test's closure (_session, _paths, _com, ...) is a dep because
        # the gate also pins the INTEGRATION (run_build arms/disarms the
        # watchdog, CAD_ROOT steers seat parking): an edit there must re-run
        # this gate, not reuse the old stamp (codex #344).
        "file_dep": [
            *module_deps_of(SCRIPTS_DIR / "test_watchdog.py"),
            str((SCRIPTS_DIR / "_watchdog.py").resolve()),
            str((SCRIPTS_DIR / "_telemetry.py").resolve()),
            # run_build's teardown (seat parking) lives in the recipe-inert
            # module, which no module_deps_of closure reaches.
            str((SCRIPTS_DIR / "_seat_forensics.py").resolve()),
            str((SCRIPTS_DIR / "test_watchdog.py").resolve()),
        ],
        "cmd": [*pytest_cmd, *_gate_tests("watchdog")],
    }


def _check_verify_telemetry_spec(pytest_cmd: list[str]) -> dict[str, Any]:
    return {
        # The verify-gate span SHAPE, driven by a mock SolidWorks whose COM
        # calls sleep at durations calibrated from the release logs: the
        # per-component dof.check / per-target whats_wrong floods stay
        # collapsed, and the slow gates (over-constrained / gear-ratios /
        # component-count / open) keep their child spans -- no gate regresses
        # back into one opaque 80-90 s span. Pure python (no SolidWorks).
        "file_dep": [
            str((SCRIPTS_DIR / "_telemetry.py").resolve()),
            str((SCRIPTS_DIR / "_assembly.py").resolve()),
            str((SCRIPTS_DIR / "verify.py").resolve()),
            str((SCRIPTS_DIR / "test_verify_telemetry.py").resolve()),
        ],
        "cmd": [*pytest_cmd, *_gate_tests("verify_telemetry")],
    }


def _check_flagonly_spec(pytest_cmd: list[str]) -> dict[str, Any]:
    return {
        # The targeted late-binding flag helper (_flag_only, issue #87) -- pure
        # dispatch glue. Was merged WITHOUT a check task, so it never ran in CI;
        # wired here so a regression in _com._flag_only fails an offline gate.
        "file_dep": [
            str((SCRIPTS_DIR / "_com.py").resolve()),
            str((SCRIPTS_DIR / "test_flag_only.py").resolve()),
        ],
        "cmd": [*pytest_cmd, *_gate_tests("flagonly")],
    }


def _check_partiso_spec(pytest_cmd: list[str]) -> dict[str, Any]:
    part_script_deps = [str(p.resolve()) for p in part_scripts()]
    return {
        # Parts must never reach the core or specialized assembly helpers, nor
        # the assembly step registry; the test scans every part script's
        # transitive repo-local closure (module_deps_of), so a helper gaining
        # such an import re-runs this gate. Pure python -> offline.
        "file_dep": sorted(
            {
                str((SCRIPTS_DIR / "_buildgraph.py").resolve()),
                str((SCRIPTS_DIR / "test_part_isolation.py").resolve()),
                *part_script_deps,
                *(dep for p in part_scripts() for dep in module_deps_of(p)),
            }
        ),
        "cmd": [*pytest_cmd, *_gate_tests("partiso")],
    }


def _check_inert_spec(pytest_cmd: list[str]) -> dict[str, Any]:
    scanned_by_binding_gate = {
        *(str(_resolved(path)) for path in SCRIPTS_DIR.glob("*.py")),
        *(str(_resolved(path)) for path in (SCRIPTS_DIR / "diagnostics").glob("*.py")),
    }
    return {
        # Recipe-inert modules (_buildgraph.RECIPE_INERT_MODULES) are in no
        # cache key, so they must never change a saved artefact: pinned call
        # sites only, no COM mutator before a save, pinned reads of tracked
        # code (test_recipe_inert.py). The gate scans every local module for
        # call sites, so every one is a dep, inert modules included.
        "file_dep": sorted(
            {
                str((REPO_ROOT / "dodo.py").resolve()),
                str((SCRIPTS_DIR / "_buildgraph.py").resolve()),
                str((SCRIPTS_DIR / "test_recipe_inert.py").resolve()),
                *scanned_by_binding_gate,
            }
        ),
        "cmd": [*pytest_cmd, *_gate_tests("inert")],
    }


def _check_budget_spec(pytest_cmd: list[str]) -> dict[str, Any]:
    return {
        # The coefficient-error budget (cad/docs/tolerance-policy.md): the
        # sensitivity model's linear gains agree with the exact channel
        # kinematics, the calibrated readout cancels common-mode error, the
        # nominal-design residual is corrected below 0.05 % MAE, every
        # toleranced nominal still resolves to the spec constant the CAD
        # builds from, the drawing limits equal the budget's, and the Monte
        # Carlo of error_budget.yaml lands inside its targets. Pure python.
        # Deps: the model, its config, every spec module the model OR the
        # test imports (the test lazily imports the notes/spec modules whose
        # drawing lines it pins to the budget -- a note edit must re-run
        # the gate, not reuse the stamp; Codex #742), and the three builders
        # the test reads as TEXT (they import SolidWorks so cannot be
        # imported offline: the assembly for its shared stations, the stick
        # for its spec import, the cylinder gear for its NotchPhase
        # tolerance call): module_deps_of cannot see them.
        "file_dep": sorted(
            {
                str((SCRIPTS_DIR / "error_budget.py").resolve()),
                str((SCRIPTS_DIR / "test_error_budget.py").resolve()),
                str((SCRIPTS_DIR / "build_ch_channel_assembly.py").resolve()),
                str((SCRIPTS_DIR / "build_dt_cylinder_gear.py").resolve()),
                str((SCRIPTS_DIR / "build_ms_stick.py").resolve()),
                # config: derived from the accessor scan of the model's and
                # the test's import closures (the same _config_deps every
                # part uses), never hand-listed -- a hand list missed
                # machine/gear_train.yaml, which cylinder_gear_spec reads
                # for the pitch the mesh-lag check converts at (Codex).
                *_config_deps(SCRIPTS_DIR / "error_budget.py"),
                *_config_deps(SCRIPTS_DIR / "test_error_budget.py"),
                str((CONFIG_DIR / "error_budget.yaml").resolve()),
                *module_deps_of(SCRIPTS_DIR / "error_budget.py"),
                *module_deps_of(SCRIPTS_DIR / "test_error_budget.py"),
            }
        ),
        "cmd": [*pytest_cmd, *_gate_tests("budget")],
    }


def _check_features_bound_spec(pytest_cmd: list[str]) -> dict[str, Any]:
    return {
        "file_dep": [
            str((SCRIPTS_DIR / "features_bound.py").resolve()),
            *(str(path) for path in _feature_bundle_outputs()),
            *(str(path) for path in _feature_manifest_outputs()),
            *(str((CAD_OUT / "step" / path.name).resolve())
              for path in _feature_bundle_outputs() if path.suffix == ".STEP"),
        ],
        "task_dep": ["package:manifest", "export"],
        "cmd": [sys.executable, str(SCRIPTS_DIR / "features_bound.py"),
                "--out", str(CAD_OUT)],
    }


_CHECK_SPEC_BUILDERS = {
    "undefined_names": _check_undefined_names_spec,
    "math": _check_math_spec,
    "config": _check_config_spec,
    "graph": _check_graph_spec,
    "nameplate": _check_nameplate_spec,
    "numerals": _check_numerals_spec,
    "recipe": _check_recipe_spec,
    "cache": _check_cache_spec,
    "telemetry": _check_telemetry_spec,
    "watchdog": _check_watchdog_spec,
    "verify_telemetry": _check_verify_telemetry_spec,
    "flagonly": _check_flagonly_spec,
    "partiso": _check_partiso_spec,
    "inert": _check_inert_spec,
    "budget": _check_budget_spec,
    "features_bound": _check_features_bound_spec,
}


def _check_spec(name: str) -> dict[str, Any]:
    builder = _CHECK_SPEC_BUILDERS.get(name)
    if builder is None:
        raise ValueError(f"unknown canonical task: check:{name}")
    # Parallel gates must not contend on pytest's shared cache directory.
    pytest_cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    return builder(pytest_cmd)


def _check_task(name: str) -> dict[str, Any]:
    spec = _check_spec(name)
    stamp = str(REPORTS / f"check-{name}.ok")
    # A gate's stamp must go stale whenever code or config it EXECUTES changes,
    # so every .py entry point on its command line contributes its local import
    # closure (lazy imports included) and the config that closure reads. Hand
    # lists drifted: check:math never listed build_summing_assembly.py or
    # gooseneck_geom.py, so a gooseneck edit left it green without running
    # (2026-09-23). The hand-listed deps above stay for what an import graph
    # cannot see: runtime-read data, scanned sources, dodo.py, and the tooling
    # modules module_deps_of excludes. test_dodo_recipe pins the invariant.
    # Tests read source text as well as running it (noqa markers, comments,
    # layout), so a gate also folds the text of the recipe code among its deps.
    deps = {
        *spec["file_dep"],
        *_executed_closure(spec["cmd"]),
        str(Path(_local_check.__file__).resolve()),
    }
    return {
        "name": name,
        "file_dep": sorted({*deps, _source_text_dep(f"check:{name}", deps)}),
        "task_dep": spec.get("task_dep", []),
        "uptodate": spec.get("uptodate", []),
        "targets": _canonical_targets(f"check:{name}"),
        "actions": [
            (_run_stamped, [
                spec["cmd"], spec.get("label", f"check {name}"),
                stamp, f"check:{name}",
            ])
        ],
        "clean": True,
        "verbosity": 2,
    }


def _check_task_names() -> tuple[str, ...]:
    names = tuple(_CHECK_SPEC_BUILDERS)
    # Tripwire: `build` and `release` depend on f"check:{c}" for c in _CHECK_NAMES,
    # so a registered spec without a matching required/optional name (or vice
    # versa) would silently never run in the default paths -- exactly the gap
    # Codex caught on freshness/flagonly. Keep enrollment and specs in lockstep.
    expected = set(_CHECK_NAMES) | set(_OPTIONAL_CHECK_NAMES)
    assert set(names) == expected, f"check specs vs check-names drift: {set(names) ^ expected}"
    return names


def task_check():
    """SolidWorks-FREE checks -- host-budgeted independently of remote leaves.

    ``check:math`` / ``check:config`` wrap ``verify.py --suite ...`` (verify.py
    runs those two without connecting to SolidWorks); ``check:graph`` /
    ``check:nameplate`` / ``check:recipe`` wrap the pure-python unit tests via
    pytest. None takes the COM seat lock; each reserves local CPU-worker slots.
    """
    for name in _check_task_names():
        yield _check_task(name)
    yield from _machinist_review_tasks()


def _prechips_task(stem: str) -> dict[str, Any]:
    import _process_plans
    from export_features import SUPPORTED_PARTS, bundle_paths

    # The parts whose manifests the plan binds: its own, or a family's.
    parts = _process_plans.part_stems(stem)
    unexported = sorted(set(parts) - set(SUPPORTED_PARTS))
    assert not unexported, f"traveler stem is not exported: {unexported}"
    label = f"prechips:{stem}"
    plan = _process_plans.plan_path(stem)
    targets = _canonical_targets(label)
    cmd = [
        sys.executable, str(SCRIPTS_DIR / "prechips_traveler.py"),
        stem, "--out", str(CAD_OUT),
    ]
    manifests = [bundle_paths(part, CAD_OUT)[0] for part in parts]
    return {
        "name": stem,
        "file_dep": sorted({
            # The plan directory also holds the diagrams/*.svg setup pictures
            # the hobby traveler embeds. Not its __pycache__: importing the
            # part's cam.py (cam_nc, test_cam_nc) writes one there at any
            # moment, and a compiled file is no traveler input.
            *(
                str(path.resolve())
                for path in plan.parent.rglob("*")
                if path.is_file()
                and "__pycache__" not in path.relative_to(plan.parent).parts
            ),
            *(str(path.resolve()) for path in _process_plans.shop_files()),
            *(str(manifest.resolve()) for manifest in manifests),
            # The render refuses a picture finding this ratchet does not list
            # (picture_clip.check).
            str(
                (REPO_ROOT / "cad" / "config" / "picture-clip-baseline.toml").resolve()
            ),
            *_executed_closure(cmd),
        }),
        "task_dep": [f"package:manifest:{part}" for part in parts],
        "targets": targets,
        # The wrapper runs the latest prechips release from PyPI (not a locked
        # dependency, #2502), so no local input pins the generator: always run.
        "uptodate": [False],
        # A refusal must not leave a previous success's stamp beside no sheet;
        # the wrapper removes the HTML and PDF itself.
        "actions": [
            (Path.unlink, [Path(targets[0])], {"missing_ok": True}),
            (_run_stamped, [cmd, label, targets[0], label]),
        ],
        "clean": True,
        "verbosity": 2,
    }


def _prechips_standing_task() -> dict[str, Any]:
    import _process_plans
    import prechips_traveler

    label = f"prechips:{prechips_traveler.STANDING_STEM}"
    targets = _canonical_targets(label)
    cmd = [
        sys.executable, str(SCRIPTS_DIR / "prechips_traveler.py"),
        "--standing", "--out", str(CAD_OUT),
    ]
    return {
        "name": prechips_traveler.STANDING_STEM,
        "file_dep": sorted({
            *(str(path.resolve()) for path in _process_plans.shop_files()),
            *_executed_closure(cmd),
        }),
        "targets": targets,
        # Latest PyPI prechips, like every traveler: always run.
        "uptodate": [False],
        "actions": [
            (Path.unlink, [Path(targets[0])], {"missing_ok": True}),
            (_run_stamped, [cmd, label, targets[0], label]),
        ],
        "clean": True,
        "verbosity": 2,
    }


def task_prechips():
    """prechips travelers for enrolled parts (pro and hobby HTML, plus the hobby
    sheet printed to ``<slug>-traveler.pdf``), rendered by the latest PyPI release.
    A family plan's task (one plan for several parts) also prints each part's
    placeholder, ``<part slug>-traveler.pdf``. With any traveler enrolled,
    ``prechips:standing`` renders the shop's standing instructions page, common
    to every traveler, to ``shop-standing-instructions.html`` and ``.pdf``.
    ``build`` and ``release`` run every one (release ships the PDFs);
    ``build_bare`` runs none."""
    import _process_plans

    for stem in _process_plans.TRAVELER_STEMS:
        yield _prechips_task(stem)
    if _process_plans.TRAVELER_STEMS:
        yield _prechips_standing_task()


def _cam_task(stem: str) -> dict[str, Any]:
    import _cam_programs

    label = f"cam:{stem}"
    targets = _canonical_targets(label)
    cmd = [
        sys.executable, str(SCRIPTS_DIR / "cam_nc.py"),
        stem, "--out", str(CAD_OUT),
    ]
    runtime = str(_cam_programs.RUNTIME_PATH.resolve())
    # The inputs manifest.json records, which a release re-checks, and the
    # as-machined report's FreeCAD script (run after the post, not an input
    # of the NC).
    deps = {
        *(str(p.resolve()) for p in _cam_programs.cam_inputs(stem, CAD_OUT).values()),
        str(_cam_programs.AS_MACHINED_RUNTIME_PATH.resolve()),
        *_executed_closure(cmd),
    }
    return {
        "name": stem,
        # Freshness is content: a CAD change re-exports the feature bundle and
        # re-posts every program. FreeCAD itself (and its post script) is not an
        # input; its version and the post's hash are recorded in manifest.json,
        # as is the runtime's own hash, so the runtime's text is an input too
        # (the recipe, outside cad/scripts, is already keyed by bytes).
        "file_dep": sorted({*deps, _source_text_dep(label, [runtime])}),
        # A family recipe posts from every part's bundle.
        "task_dep": [
            f"package:manifest:{part}" for part in _cam_programs.cam_parts(stem)
        ],
        "targets": targets,
        # A failed post or check must not leave a previous success's stamp; the
        # driver removes every program and the manifest itself.
        "actions": [
            (Path.unlink, [Path(targets[0])], {"missing_ok": True}),
            (_run_stamped, [cmd, label, targets[0], label]),
        ],
        "clean": True,
        "verbosity": 2,
    }


def task_cam():
    """NC programs for enrolled parts, posted by headless FreeCAD CAM
    (``freecadcmd``) from ``cad/process/<stem>/cam.py`` and checked against the
    part's feature bundle (a family recipe: every part's, posted once for the
    family), with each program's cycle time. ``build`` and
    ``release`` run every one (release ships the programs under ``nc/<stem>/``);
    ``build_bare`` runs none. Submitter-only, like ``prechips``: no farm worker
    has FreeCAD, so the submitter needs FreeCAD 1.1+ and the task fails loud
    without it."""
    import _cam_programs

    for stem in _cam_programs.CAM_STEMS:
        yield _cam_task(stem)


def task_export():
    """Export neutral CAD: STEP / STL / assembly glTF / boxes scene + the
    release-neutral manifest, from every built model.

    A cache-keyed COM leaf like a part: a HIT downloads the neutral set, and a MISS
    under the farm executor runs ONE leaf on a worker -- which is what lets a
    seatless machine cut a release. The comparison gallery is NOT here: it needs
    Blender and a GPU (which no farm worker has), so it is the separate,
    SolidWorks-free ``gallery`` task that ``release`` depends on.

    Always runs (``uptodate: False``) rather than gating on a single declared
    target: a deleted STEP/STL/colors output (with the boxes JSON + CAD inputs
    unchanged) must still be repaired, which doit would otherwise skip (codex
    review). On a HIT the cache restore repairs it; on a MISS the exporter
    self-checks every output's per-file staleness cheaply and prints "all exports
    fresh" when there is nothing to do -- keyed on the SAME churn-immune recipe
    digest (``_stable_artefact_digest``) doit and the remote cache use, NOT the
    .SLDPRT/.SLDASM mtime, which SolidWorks' save cascade bumps on every build.
    """
    deps = _export_file_deps()
    return {
        "file_dep": deps,
        "targets": _canonical_targets("export"),
        # Named STEP copies require the complete produced feature inventory;
        # native neutral formats also require soundness and kinematics.
        "task_dep": ["verify:soundness", "verify:kinematics", "package:features"],
        "uptodate": [False],
        # --record-digests: this runs AFTER every part/assembly is (re)built (its
        # file_dep) and the verify gates, so the natives are current and their
        # recipe digests are safe to RECORD as the export-freshness cache (a bare
        # standalone run must not -- see export_models.main).
        "actions": [
            (
                _cached_com_action,
                [
                    "export",
                    [sys.executable, str(EXPORT_PY), "--record-digests"],
                    deps,
                    _export_cache_outputs(),
                    "export",
                ],
            )
        ],
        "verbosity": 2,
    }


def task_gallery():
    """Refresh the reference-photo comparison gallery from the exported STLs
    (renders, composites, RMS scores, index.html) -- the showcase a release ships.

    SolidWorks-FREE but Blender+GPU-bound, so it is deliberately NOT a farm leaf and
    never takes the COM seat: it runs on the submitter, after ``export`` (the
    file_dep on the release-neutral manifest is that edge). It fails LOUD when
    Blender or a render is unavailable -- it is the only thing standing between a
    release and a stale gallery.
    """
    comparisons = REPO_ROOT / "cad" / "comparisons"
    tools = comparisons / "tools"
    return {
        "file_dep": [
            str(EXPORT_PY),
            str((REPORTS / "release-neutral.json").resolve()),
            str((comparisons / "manifest.json").resolve()),
            *(
                str((tools / name).resolve())
                for name in (
                    "render_offline.py",
                    "blender_worker.py",
                    "composite.py",
                    "gallery.py",
                )
            ),
        ],
        "targets": _canonical_targets("gallery"),
        # Always run: the gallery's own --stale-only pass is the cheap freshness
        # check, and a pair whose render was deleted must be regenerated.
        "uptodate": [False],
        "actions": [(_refresh_gallery, [])],
        "verbosity": 2,
    }


def _refresh_gallery() -> None:
    """``gallery``'s action. doit refuses a callable that declares ``task`` with a
    default, so ``_run`` (whose ``task`` is keyword-only, default ``None``) cannot
    be the action itself; this wrapper names the task explicitly instead."""
    _run(
        [sys.executable, str(EXPORT_PY), "--comparisons"],
        "gallery",
        "gallery",
        task="gallery",
    )


def _package_feature_task(stem: str) -> dict[str, Any]:
    deps = _feature_export_file_deps(stem)
    outputs = _feature_export_outputs(stem)
    return {
        "name": f"features:{stem}",
        "file_dep": deps,
        "targets": [str(path) for path in outputs],
        # Always probe the cache so existing but tampered/partial bundles repair.
        "uptodate": [False],
        "actions": [(_cached_com_action, [
            f"package:features:{stem}",
            [sys.executable, str(EXPORT_PY), "--features", stem],
            deps, outputs, f"features-{stem.replace('_', '-')}",
        ])],
        "clean": True,
        "verbosity": 2,
    }


def _package_features_task() -> dict[str, Any]:
    from export_features import SUPPORTED_PARTS

    return {
        "name": "features",
        "task_dep": [f"package:features:{stem}" for stem in SUPPORTED_PARTS],
        "file_dep": [str(path) for path in _feature_bundle_outputs()],
        "actions": [],
        "verbosity": 2,
    }


def _write_feature_manifest(stem: str) -> None:
    """``package:manifest:<stem>``'s action (``_run`` cannot be the action
    itself: doit refuses a callable declaring ``task`` with a default)."""
    label = f"package:manifest:{stem}"
    _run(
        [sys.executable, str(SCRIPTS_DIR / "export_features.py"), stem, "--out", str(CAD_OUT)],
        label,
        f"manifest-{stem.replace('_', '-')}",
        task=label,
    )


def _package_manifest_task(stem: str) -> dict[str, Any]:
    """Bind ``stem``'s declarations to its labelled STEP(s), seat-free."""
    return {
        "name": f"manifest:{stem}",
        "file_dep": _feature_manifest_file_deps(stem),
        "task_dep": [f"package:features:{stem}"],
        "targets": [str(_feature_manifest_output(stem))],
        "actions": [(_write_feature_manifest, [stem])],
        "clean": True,
        "verbosity": 2,
    }


def _package_manifests_task() -> dict[str, Any]:
    from export_features import SUPPORTED_PARTS

    return {
        "name": "manifest",
        "task_dep": [f"package:manifest:{stem}" for stem in SUPPORTED_PARTS],
        "file_dep": [str(path) for path in _feature_manifest_outputs()],
        "actions": [],
        "verbosity": 2,
    }


def _package_release_task() -> dict[str, Any]:
    deps = _package_file_deps()
    native = _package_cache_outputs()[0]
    return {
        "name": "release",
        "file_dep": deps,
        "targets": _canonical_targets("package:release"),
        # Always run: a native member deleted from the prepared tree (with the CAD
        # inputs unchanged) must be repaired, which a target-only check would skip.
        "uptodate": [False],
        "actions": [
            (
                _cached_com_action,
                [
                    "package:release",
                    [sys.executable, str(PACKAGE_NATIVE_PY)],
                    deps,
                    [native],
                    "package-release",
                ],
            )
        ],
        "clean": True,
        "verbosity": 2,
    }


def task_package():
    """Feature aggregation and cache-keyed native release packaging.

    ``package:features`` is action-free and seat-free. Its explicit task edges
    include every ``package:features:<stem>`` COM leaf in the packaged farm graph;
    file edges require each leaf's labelled STEPs and face inventories.
    ``package:manifest:<stem>`` binds the drawing's declarations to them
    without SolidWorks; ``package:manifest`` aggregates every manifest.

    ``package:release`` is the COM half of a release: SolidWorks Pack-and-Go of
    the top assembly and of every native drawing, merged and de-duplicated into
    ``cad/out/release/native/`` with a ``native-package.json`` sidecar carrying the
    document revision and the per-drawing source lists.

    This exists so ``release`` itself needs no seat: a cache-keyed COM leaf runs the
    Pack-and-Go (locally, or as ONE farm leaf), and cut_release.py then only copies
    the prepared tree. OPT-IN -- only `release` depends on it.
    """
    from export_features import SUPPORTED_PARTS

    for stem in SUPPORTED_PARTS:
        yield _package_feature_task(stem)
        yield _package_manifest_task(stem)
    yield _package_features_task()
    yield _package_manifests_task()
    yield _package_release_task()


def _run_release(relargs):
    """Run cut_release.py, forwarding any positional args (``doit release -- v22``).

    SolidWorks-FREE since the Pack-and-Go moved to the `package:release` leaf: the
    publisher stages the prepared native tree, the neutral exports, the drawings,
    the renders and the gallery, then tags and uploads. It takes NO COM seat, so it
    neither blocks another worktree's build nor needs SolidWorks on this machine --
    which is the whole point: a release can be cut from a seatless box, with every
    COM stage dispatched to the farm.

    ``build.py`` refuses a release with visibility debt before dispatching any
    leaf; a bare ``doit release`` reaches this check only after its gates."""
    import visibility_debt

    visibility_debt.assert_no_visibility_debt()
    _run([sys.executable, str(RELEASE_PY), *relargs], "cut release", task="release")


def task_release():
    """Cut a tagged release (native Pack-and-Go + neutral exports + gallery + diff +
    GitHub release). OPT-IN -- not in default_tasks. Needs `gh`; needs NO seat.

    Publishing is a side effect (no doit target), so it always runs. Forward
    Args after ``--``: ``doit release -- v22 --draft``. With no version, the
    latest compact release tag is incremented (for example, ``v21`` -> ``v22``).
    Gated on EVERY gate via REAL task_dep edges: ``export`` (which itself pulls the
    parts/assemblies + the ``verify:*`` gates), ``gallery``, ``package:release``
    (the Pack-and-Go tree it stages), every registered ``drawing:*`` artifact,
    the ``verify:*`` suites, and every offline
    ``check:*`` -- so a release cannot publish past a stale/failing gate or
    package a missing/stale drawing. It also renders every enrolled
    ``prechips:<stem>`` traveler, whose hobby PDF the bundle ships under
    ``travelers/`` (owner ruling 2026-11-14), and posts every enrolled
    ``cam:<stem>`` part's NC programs, which the bundle ships under
    ``nc/<stem>/`` (owner ruling 2026-11-17).
    """
    import _cam_programs

    return {
        "task_dep": [
            "export",
            "gallery",
            "package:release",
            "check:features_bound",
            *(f"drawing:{s}" for s in _drawing_order()),
            *(f"check:machinist_review:{s}" for s, _mode in _reviewed_drawings()),
            *(f"verify:{s}" for s in _VERIFY_NAMES),
            *(f"check:{c}" for c in _CHECK_NAMES),
            *(f"prechips:{s}" for s in _canonical_subtask_names("prechips")),
            *(f"cam:{s}" for s in _cam_programs.CAM_STEMS),
        ],
        "uptodate": [False],
        "pos_arg": "relargs",
        "actions": [(_run_release,)],
        "verbosity": 2,
    }


def task_build():
    """THE fully-safe entry point (also ``default_tasks``): every part + assembly
    + every gate (SolidWorks ``verify:*``, offline ``check:*``) + every drawing,
    and beside the drawing PDFs every enrolled ``prechips:<stem>`` traveler
    (HTML + hobby ``<slug>-traveler.pdf``) and every enrolled ``cam:<stem>``
    part's NC programs. ``build_bare`` renders and posts none.

    Use ``doit -n N`` to fan out SolidWorks-free work alongside the COM stream
    (serialized by the seat lock, not a spine).

    Ordering here is a SCHEDULING HINT only (real deps drive correctness): the
    offline ``check:*`` gates are listed FIRST so workers burn through that ~1 min of
    SolidWorks-free work before piling onto the COM seat, and the parts are in
    per-seat order so two cold builders diverge and split the fleet cache.

    Every COM gate is farm-dispatchable: under the farm executor each cache-missing
    gate runs on a worker. Offline checks, travelers and NC programs run on the
    submitter.
    """
    import _cam_programs

    return {
        "actions": None,
        "task_dep": (
            [f"check:{s}" for s in _CHECK_NAMES]
            + [f"part:{s}" for s in _seat_part_order()]
            + [f"assembly:{s}" for s in ASSEMBLY_ORDER]
            + [f"drawing:{s}" for s in _drawing_order()]
            + [f"check:machinist_review:{s}" for s, _mode in _reviewed_drawings()]
            + [f"verify:{s}" for s in _VERIFY_NAMES]
            + [f"prechips:{s}" for s in _canonical_subtask_names("prechips")]
            + [f"cam:{s}" for s in _cam_programs.CAM_STEMS]
        ),
    }


def task_build_bare():
    """Quick rebuild: parts + assemblies only -- no standalone gates, no export
    (in ``rw`` cache mode each rebuilt assembly still proves its soundness
    in-leaf, see :func:`_prove_soundness_in_leaf`).
    Parts in per-seat order (scheduling hint); the seat lock keeps COM serial."""
    return {
        "actions": None,
        "task_dep": (
            [f"part:{s}" for s in _seat_part_order()]
            + [f"assembly:{s}" for s in ASSEMBLY_ORDER]
        ),
    }


_CANONICAL_FAMILIES = (
    "part", "assembly", "drawing", "verify_soundness", "verify", "check",
    "prechips", "cam", "package", "review_sweep",
)


def _canonical_subtask_names(family: str) -> list[str]:
    """Enumerate names without constructing task dictionaries or input closures."""
    if family == "part":
        return _seat_part_order()
    if family in ("assembly", "verify_soundness"):
        return list(ASSEMBLY_ORDER)
    if family == "drawing":
        return _drawing_order()
    if family == "verify":
        return list(_VERIFY_NAMES)
    if family == "check":
        return [
            *_check_task_names(),
            *(f"machinist_review:{stem}" for stem, _mode in _reviewed_drawings()),
            *(
                f"machinist_review_fitup:{stem}"
                for stem, _mode in _reviewed_drawings()
                if _machinist_review_fitup_text(stem) is not None
            ),
        ]
    if family == "prechips":
        import _process_plans
        import prechips_traveler

        stems = list(_process_plans.TRAVELER_STEMS)
        return [*stems, prechips_traveler.STANDING_STEM] if stems else []
    if family == "cam":
        import _cam_programs

        return list(_cam_programs.CAM_STEMS)
    if family == "package":
        from export_features import SUPPORTED_PARTS

        return [
            *(name for stem in SUPPORTED_PARTS for name in (f"features:{stem}", f"manifest:{stem}")),
            "features",
            "manifest",
            "release",
        ]
    if family == "review_sweep":
        return [stem for stem, _mode in _reviewed_drawings()]
    raise ValueError(f"unknown canonical task family: {family}")


def _canonical_targets(name: str) -> list[str]:
    """The shared, dependency-free target definition used by factories and indexing."""
    family, _separator, subname = name.partition(":")
    if family == "part":
        return [
            _sldprt(subname), _part_execution_token(subname),
            *(str(path.resolve()) for path in _part_configuration_outputs(subname)),
        ]
    if family == "assembly":
        return [_sldasm(subname), _assembly_execution_token(subname)]
    if family == "drawing":
        return [str(path) for path in _drawing_cache_outputs(subname)]
    if family == "verify_soundness":
        return [_soundness_stamp(subname)]
    if family == "verify":
        return [str(REPORTS / f"verify-{subname}.ok")]
    if family == "check":
        if subname.startswith("machinist_review:"):
            stem = subname.removeprefix("machinist_review:")
            directory = _machinist_review_dir(stem)
            return [
                str(_machinist_review_stamp(stem)),
                str(directory / f"{stem}.aggregate.json"),
                str(directory / f"{stem}.aggregate.md"),
                *(
                    str(directory / stem / "runs" / f"r{run}" / f"{stem}.json")
                    for run in range(1, 4)
                ),
            ]
        if subname.startswith("machinist_review_fitup:"):
            stem = subname.removeprefix("machinist_review_fitup:")
            return [str(REPORTS / "machinist-review-fitup" / f"{stem}.md")]
        return [str(REPORTS / f"check-{subname}.ok")]
    if family == "prechips":
        import _process_plans
        import prechips_traveler

        outputs = (
            prechips_traveler.standing_paths(CAD_OUT)
            if subname == prechips_traveler.STANDING_STEM
            else _process_plans.traveler_outputs(subname, CAD_OUT)
        )
        return [
            str(REPORTS / f"prechips-{subname}.ok"),
            *(str(path) for path in outputs),
        ]
    if family == "cam":
        import _cam_programs

        return [
            str(REPORTS / f"cam-{subname}.ok"),
            *(str(path) for path in _cam_programs.cam_outputs(subname, CAD_OUT)),
        ]
    if family == "package":
        if subname.startswith("features:"):
            # The feature factory already computes these outputs for its action;
            # both paths use this same cheap output-only helper.
            return [str(path) for path in _feature_export_outputs(subname.removeprefix("features:"))]
        if subname.startswith("manifest:"):
            return [str(_feature_manifest_output(subname.removeprefix("manifest:")))]
        if subname == "release":
            return [str(_package_cache_outputs()[0] / "native-package.json")]
        if subname in ("features", "manifest"):
            return []
    if name == "export":
        return [
            str((CAD_OUT / "boxes" / "ha-harmonic-analyzer.json").resolve()),
            str((REPORTS / "release-neutral.json").resolve()),
        ]
    if name == "gallery":
        return [str((REPORTS / "comparison-gallery.json").resolve())]
    raise ValueError(f"unknown canonical target definition: {name}")


def _canonical_subtask_definition(family: str, subname: str) -> dict[str, Any]:
    if family == "part":
        return _part_task(subname)
    if family == "assembly":
        return _assembly_task(subname)
    if family == "drawing":
        return _drawing_task(subname)
    if family == "verify_soundness":
        return _verify_soundness_task(subname)
    if family == "verify":
        return _verify_task(subname)
    if family == "check":
        if subname.startswith("machinist_review:"):
            stem = subname.removeprefix("machinist_review:")
            return _machinist_review_task(
                stem, dict(_reviewed_drawings())[stem], _machinist_review_profile(),
            )
        if subname.startswith("machinist_review_fitup:"):
            stem = subname.removeprefix("machinist_review_fitup:")
            fitup = _machinist_review_fitup_text(stem)
            if fitup is None:
                raise ValueError(f"unknown canonical task: check:{subname}")
            return _machinist_review_fitup_task(stem, fitup)
        return _check_task(subname)
    if family == "prechips":
        import prechips_traveler

        if subname == prechips_traveler.STANDING_STEM:
            return _prechips_standing_task()
        return _prechips_task(subname)
    if family == "cam":
        return _cam_task(subname)
    if family == "package":
        if subname.startswith("features:"):
            return _package_feature_task(subname.removeprefix("features:"))
        if subname.startswith("manifest:"):
            return _package_manifest_task(subname.removeprefix("manifest:"))
        if subname == "features":
            return _package_features_task()
        if subname == "manifest":
            return _package_manifests_task()
        if subname == "release":
            return _package_release_task()
    if family == "review_sweep" and subname in dict(_reviewed_drawings()):
        return _review_sweep_task(subname, _machinist_review_profile())
    raise ValueError(f"unknown canonical task: {family}:{subname}")


def canonical_tasks(names: Iterable[str]) -> list[Task]:
    """Construct exactly these live doit tasks, never filtering fully built generators.

    The caller supplies the complete dependency closure. No task edge, freshness
    tracker, value saver or action is removed here. Conversion mirrors doit's
    loader: subtasks have their real basename, and groups retain every child edge
    and their generator's documentation without constructing those children.
    """
    requested = list(names)
    if any(not isinstance(name, str) or not name for name in requested):
        raise ValueError("canonical task names must be nonempty strings")
    if len(set(requested)) != len(requested):
        raise ValueError("duplicate canonical task name")
    singletons = {
        "export": task_export, "gallery": task_gallery,
        "release": task_release, "build": task_build, "build_bare": task_build_bare,
        "cache_status": task_cache_status,
    }
    family_names: dict[str, list[str]] = {}
    for name in requested:
        family, separator, subname = name.partition(":")
        if not separator and name in singletons:
            continue
        if family not in _CANONICAL_FAMILIES:
            raise ValueError(f"unknown canonical task: {name}")
        if family not in family_names:
            family_names[family] = _canonical_subtask_names(family)
        if separator and subname not in family_names[family]:
            raise ValueError(f"unknown canonical task: {name}")

    tasks: list[Task] = []
    for name in requested:
        family, separator, subname = name.partition(":")
        if not separator and name in singletons:
            creator = singletons[name]
            tasks.extend(generate_tasks(name, creator(), creator.__doc__))
        elif not separator:
            creator = globals()[f"task_{family}"]
            task = Task(name, None, doc=creator.__doc__, has_subtask=True)
            task.task_dep.extend(f"{family}:{child}" for child in family_names[family])
            tasks.append(task)
        else:
            definition = _canonical_subtask_definition(family, subname)
            definition["name"] = name
            task = dict_to_task(definition)
            task.subtask_of = family
            tasks.append(task)
    return tasks


def _ownership_namespace_has_aliases(
    directory: Path, *, filenames: frozenset[str], suffixes: frozenset[str] = frozenset(),
) -> bool:
    """Inspect only the two levels at which these families declare targets.

    A skipped feature/traveler namespace may contain a junction or file symlink
    into a queried namespace. In that case its real inventory must be consulted.
    Never recurse into native outputs, report trees, or arbitrary descendants.
    """
    if directory.is_symlink() or directory.is_junction():
        return True
    try:
        stems = os.scandir(directory)
    except FileNotFoundError:
        # Clean leaves have no output namespace to alias another target.
        return False
    with stems:
        for stem in stems:
            path = Path(stem.path)
            if stem.is_symlink() or path.is_junction():
                return True
            if not stem.is_dir(follow_symlinks=False):
                continue
            try:
                outputs = os.scandir(path)
            except FileNotFoundError:
                # A vanished sibling must not hide an alias in a later stem.
                continue
            with outputs:
                for output in outputs:
                    target = Path(output.path)
                    if (
                        target.name.lower() in filenames
                        or target.suffix.lower() in suffixes
                    ) and (output.is_symlink() or target.is_junction()):
                        return True
    return False


def canonical_target_owners(paths: Iterable[str] | None = None) -> dict[str, str]:
    """Index live owners of requested paths, or all declared targets with no query.

    Queries contain every genuine selected target and file_dep, not graph data.
    Heavy feature, traveler and review enrollment is evaluated only when its
    canonical namespace or an existing alias can own a queried path. Drawing
    output metadata is always consulted, including relocated outputs/collisions.
    Returned keys use OS path identity, not serialized path spelling.
    """
    from cad.scripts._selected_execution import _path_identity, _workspace_path

    workspace = REPO_ROOT.resolve(strict=False)
    requested = None if paths is None else {
        _path_identity(_workspace_path(workspace, str(path))) for path in paths
    }
    owners: dict[str, str] = {}

    def normalized(target: str | Path) -> str:
        return _path_identity(_workspace_path(workspace, str(target)))

    def queried_namespace(directory: Path) -> bool:
        if requested is None:
            return True
        prefix = normalized(directory)
        return any(path == prefix or path.startswith(prefix + "/") for path in requested)

    def include(name: str, targets: Iterable[str] | None = None) -> None:
        for target in _canonical_targets(name) if targets is None else targets:
            relative = normalized(target)
            if requested is not None and relative not in requested:
                continue
            previous = owners.setdefault(relative, name)
            if previous != name:
                raise ValueError(f"duplicate canonical target {relative}: {previous}, {name}")

    # Native/model and gate inventories are already cheap source metadata.
    # Normalize every declared native path so aliases cannot hide a producer.
    for stem in part_stems():
        include(f"part:{stem}")
    for stem in ASSEMBLY_ORDER:
        include(f"assembly:{stem}")
        include(f"verify_soundness:{stem}")
    for stem in DRAWINGS_BY_NAME:
        include(f"drawing:{stem}")
    for name in _VERIFY_NAMES:
        include(f"verify:{name}")
    for name in _check_task_names():
        include(f"check:{name}")
    for name in ("export", "gallery", "package:release"):
        include(name)

    # Potential review paths are entirely determined by loaded drawing metadata.
    # Membership still comes from the real review enrollment, never a filename.
    reviewed = None
    for stem in DRAWINGS_BY_NAME:
        name = f"check:machinist_review:{stem}"
        targets = _canonical_targets(name)
        fitup_name = f"check:machinist_review_fitup:{stem}"
        fitup_targets = _canonical_targets(fitup_name)
        if requested is not None and not any(
            normalized(target) in requested for target in (*targets, *fitup_targets)
        ):
            continue
        if reviewed is None:
            reviewed = dict(_reviewed_drawings())
        if stem in reviewed:
            include(name, targets)
            if _machinist_review_fitup_text(stem) is not None:
                include(fitup_name, fitup_targets)

    feature_root = CAD_OUT / "features"
    if queried_namespace(feature_root) or _ownership_namespace_has_aliases(
        feature_root, filenames=frozenset({"features.toml"}), suffixes=frozenset({".step", ".json"}),
    ):
        from export_features import SUPPORTED_PARTS

        for stem in SUPPORTED_PARTS:
            include(f"package:features:{stem}")
            include(f"package:manifest:{stem}")

    traveler_root = CAD_OUT / "travelers"
    stamp_prefix = normalized(REPORTS) + "/prechips-"
    traveler_stamp = requested is None or any(
        path.startswith(stamp_prefix) and path.endswith(".ok") for path in requested
    )
    if (
        queried_namespace(traveler_root)
        or traveler_stamp
        # Every traveler target is an .html or .pdf file directly under its stem.
        or _ownership_namespace_has_aliases(
            traveler_root, filenames=frozenset(), suffixes=frozenset({".html", ".pdf"}),
        )
        or any(path.is_symlink() for path in REPORTS.glob("prechips-*.ok"))
    ):
        for stem in _canonical_subtask_names("prechips"):
            include(f"prechips:{stem}")

    nc_root = CAD_OUT / "nc"
    cam_prefix = normalized(REPORTS) + "/cam-"
    if (
        queried_namespace(nc_root)
        or requested is None
        or any(path.startswith(cam_prefix) and path.endswith(".ok") for path in requested)
        # Every cam target is a .nc or manifest.json file directly under its stem.
        or _ownership_namespace_has_aliases(
            nc_root, filenames=frozenset({"manifest.json"}), suffixes=frozenset({".nc"}),
        )
        or any(path.is_symlink() for path in REPORTS.glob("cam-*.ok"))
    ):
        import _cam_programs

        for stem in _cam_programs.CAM_STEMS:
            include(f"cam:{stem}")
    return owners


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
    """(label, file_deps) for every cacheable leaf, in build order."""
    rows: list[tuple[str, list[str]]] = []
    for script in part_scripts():
        stem = script.stem.removeprefix("build_")
        rows.append((f"part:{stem}", _part_file_deps(script, stem)))
    for stem in ASSEMBLY_ORDER:
        rows.append((f"assembly:{stem}", _assembly_file_deps(stem)))
    for stem in _drawing_order():
        rows.append((f"drawing:{stem}", _drawing_file_deps(stem)))
    for stem, _mode in _reviewed_drawings():
        rows.append((
            f"check:machinist_review:{stem}", _machinist_review_key_deps(stem),
        ))
    for stem in ASSEMBLY_ORDER:
        rows.append((f"verify_soundness:{stem}", _soundness_file_deps(stem)))
    rows.append(("verify:kinematics", _kinematics_file_deps()))
    rows.append(("export", _export_file_deps()))
    from export_features import SUPPORTED_PARTS

    for stem in SUPPORTED_PARTS:
        rows.append((f"package:features:{stem}", _feature_export_file_deps(stem)))
    rows.append(("package:release", _package_file_deps()))
    return rows


def _cache_status(statusargs):
    args = [a.lower() for a in (statusargs or [])]
    only_miss = "miss" in args
    show_all = "all" in args
    filters = [a for a in args if a not in ("miss", "all")]

    cfg = _cache.config_summary()
    _telemetry.info(
        f"[cache_status] mode={cfg['mode']} epoch={cfg['epoch']} salt={cfg['salt']} "
        f"account={cfg['account']} container={cfg['container']}"
    )
    if not _cache.enabled():
        _telemetry.warn(
            "[cache_status] cache disabled (mode=off) -- keys computed, backend NOT probed"
        )

    hits = misses = unknown = 0
    for label, deps in _cache_rows():
        if filters and not any(f in label.lower() for f in filters):
            continue
        digest = (
            _machinist_review_digest(_machinist_review_profile())
            if label.startswith("check:machinist_review:")
            else ContentChecker._digest
        )
        key, inputs = _cache.key_inputs(deps, digest)
        present = _cache.probe(key)  # True / False / None (disabled|unreachable)
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
                before, after = (
                    previous.get(rel, "<absent>"),
                    current.get(rel, "<absent>"),
                )
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
