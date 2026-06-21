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
  verify:<suite>     soundness/subsystems/kinematics gates (COM)
  check:<name>       math/config/graph/nameplate/recipe gates (NO SolidWorks)
  export             neutral STEP/STL/scene export (COM)
  release            cut a tagged GitHub release (COM + gh; opt-in)
  build              EVERY part + assembly + EVERY gate -- the one safe entry
  build_bare         parts + assemblies only -- a quick rebuild

COM serialization (the single SolidWorks STA seat) is enforced by a linear
``task_dep`` *spine* through every COM task, NOT by forbidding -n -- so the
SolidWorks-free ``check:*`` tasks fan out in parallel while COM stays serial.
``doit -n N`` is now SAFE (see the _spine_dep / _COM_TAIL block below).

Install (one-off, in the Windows SolidWorks build venv -- this repo has no
pyproject.toml of its own)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe -m pip install doit pillow pytest

Run with that same venv's python (SolidWorks already open)::

    set "DOIT=C:\src\SolidworksMCP-python\.venv\Scripts\python.exe -m doit"

    %DOIT%                       # = `build`: every part + assembly + every gate
    %DOIT% -n 4                  # same, fanning out the SolidWorks-free checks
    %DOIT% build_bare            # quick: parts + assemblies only, no gates
    %DOIT% assembly:paper_drive  # just that assembly + its stale prereqs
    %DOIT% part:summing_lever    # just that part
    %DOIT% verify:soundness      # one SW gate; check:math one offline gate
    %DOIT% export                # neutral STEP/STL/scene export
    %DOIT% release -- v0.2.0     # cut a release (args after --; opt-in)
    %DOIT% list --all            # every task
    %DOIT% clean                 # remove targets (+ wipe png/<asm>)

Full-rebuild escape (idiomatic doit -- a missing target forces a run, and
build_or_refresh takes the FULL branch when the target is absent)::

    del cad\out\sldasm\paper-drive.SLDASM
    %DOIT% forget assembly:paper_drive    # optional: also drop the cached hash
    %DOIT% assembly:paper_drive
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Part tasks run via doit ``CmdAction(verbosity=2)``, which pipes each build
# script's stdout and RE-EMITS it through this doit parent process. Build output
# carries non-ASCII (e.g. the "A ∩ B" gate labels); on Windows the parent stdout
# defaults to cp1252, so re-emitting that glyph raises UnicodeEncodeError and kills
# doit's reader thread (which can then hang the child on a full pipe). The child's
# own run_build reconfigure does not help here -- the crash is in the PARENT. Force
# UTF-8 on the parent too, mirroring run_build (_common.py).
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")

import yaml as _yaml
from doit.action import CmdAction
from doit.dependency import CHECKERS, Dependency, JsonDB, MD5Checker, get_file_md5

sys.path.insert(0, str(Path(__file__).resolve().parent / "cad" / "scripts"))

from _buildgraph import (  # noqa: E402
    ASSEMBLY_ORDER,
    CAD_OUT,
    POST_ASSEMBLY,
    SCRIPTS_DIR,
    artefact_for,
    module_deps_of,
    part_scripts,
    part_stems,
    references_of,
    script_for,
)

REPO_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = REPO_ROOT / "cad" / "config"

# --- COM spine: keep SolidWorks serial WITHOUT changing how COM work runs.
#
# There is one SolidWorks STA seat, so COM tasks must never run concurrently.
# Rather than the old global -n hard-fail (which also blocked the SolidWorks-FREE
# work), every COM task is chained into a single linear ``task_dep`` spine -- a
# topological linearization of the COM sub-DAG:
#
#   part:a -> ... -> part:z -> assembly:frame -> ... -> assembly:harmonic_analyzer
#          -> verify:soundness -> verify:subsystems -> verify:kinematics
#          -> export -> release
#
# Because each COM task waits on its predecessor, at most ONE COM task is ever
# "ready", so the seat is never contended even under ``doit -n N`` -- identical
# runtime behaviour to the old serial run, just enforced by DAG edges instead of
# -n=1. Subprocess-per-task isolation is UNCHANGED. The SolidWorks-free ``check:*``
# tasks depend only on real artefacts (never the spine), so they fan out in
# parallel. Tradeoff: a COM failure mid-spine skips the later COM tasks in that
# run; fix-and-rerun recovers (doit skips up-to-date tasks).
_COM_TAIL = [
    "verify:soundness",
    "verify:subsystems",
    "verify:kinematics",
    "export",
    "release",
]


def _com_spine_order() -> list[str]:
    """The full COM task order: parts, then assemblies, then the SW tail."""
    parts = [f"part:{stem}" for stem in part_stems()]
    asms = [f"assembly:{stem}" for stem in ASSEMBLY_ORDER]
    return parts + asms + _COM_TAIL


_SPINE = _com_spine_order()
_SPINE_PRED = {name: _SPINE[i - 1] for i, name in enumerate(_SPINE) if i > 0}


def _spine_dep(name: str) -> list[str]:
    """The one ``task_dep`` edge that keeps ``name`` serial on the COM seat
    (empty for the first COM task)."""
    pred = _SPINE_PRED.get(name)
    return [pred] if pred else []


def _assert_spine_complete() -> None:
    """Tripwire: a gap in the spine would let ``doit -n N`` run two COM tasks at
    once and deadlock the single STA seat. Fail loud before any task runs."""
    order = _com_spine_order()
    if len(order) != len(set(order)):
        raise SystemExit("dodo: duplicate task in COM spine")
    if not part_stems():
        raise SystemExit("dodo: no part scripts found -- COM spine is empty")


_assert_spine_complete()


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
class ContentChecker(MD5Checker):
    """MD5Checker that digests the parsed form of YAML configs (comment- and
    whitespace-insensitive); byte-identical to MD5Checker for every other file."""

    @staticmethod
    def _digest(file_path: str) -> str:
        if not file_path.endswith((".yaml", ".yml")):
            return get_file_md5(file_path)
        try:
            with open(file_path, "rb") as fh:
                data = _yaml.safe_load(fh)
        except _yaml.YAMLError:
            return get_file_md5(file_path)  # malformed -> fall back; build fails loud later
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


def _run(cmd: list[str], label: str) -> None:
    """Run a build/refresh subprocess from the repo root; raise on non-zero so
    doit marks the task failed and stops (fail-loud -- no stale artefact)."""
    print(f">>  {label}: {' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if proc.returncode:
        raise RuntimeError(f"{label} failed (exit {proc.returncode})")


# --- Per-script helper dependencies, computed from each build script's REAL
# transitive imports (``module_deps_of``) instead of a blanket "every ``_*.py`` is
# a dep of every build". A leaf part that imports only ``_common`` no longer
# rebuilds when an assembly-only helper (``_assembly``) or an unrelated one
# (``_gear``) changes; the closure follows imports (``_chain_link -> _chain ->
# _common``; ``_common -> _config``) so it never under-invalidates as long as a
# script imports what it uses. (Excludes _buildgraph.py: the build-GRAPH helper
# imported here, not a geometry input.)
#
# The YAML data layer stays a blanket dep of EVERY build: ``parts.yaml`` is read
# transitively by ``_common.part_properties`` for almost every part (custom-
# property stamping), and a placement YAML edit can move any body. Coarse but
# correct, and content-hashing means an edit that doesn't change a given part's
# inputs still costs only that one rebuild.
_CONFIG_YAMLS = [str(p.resolve()) for p in sorted(CONFIG_DIR.glob("*.yaml"))]


def _helper_deps(script) -> list[str]:
    """This build script's transitive ``_*.py`` helper imports (resolved paths)."""
    return module_deps_of(script if isinstance(script, Path) else Path(script))

# --- Stamp files: the verify:/check: gates produce no CAD artefact, so a stamp
# under cad/out/reports/ is their doit ``target``. That makes each gate
# incremental (re-runs only when a file_dep changes) and individually
# addressable, exactly like a part/assembly target.
REPORTS = CAD_OUT / "reports"
VERIFY_PY = (SCRIPTS_DIR / "verify.py").resolve()
EXPORT_PY = (SCRIPTS_DIR / "export_models.py").resolve()
RELEASE_PY = (SCRIPTS_DIR / "cut_release.py").resolve()

# The gate suites, by SolidWorks-dependence -- the single source of truth for the
# verify:/check: task names (reused by build + release so a new gate is wired in
# one place).
_VERIFY_NAMES = ("soundness", "subsystems", "kinematics")   # need SW (spine)
_CHECK_NAMES = ("math", "config", "graph", "nameplate", "recipe")  # offline


def _run_stamped(cmd: list[str], label: str, stamp: str) -> None:
    """Run a gate subprocess; on success write its stamp target. _run raises on
    non-zero, so a failed gate never writes a stamp (stays stale -> re-runs)."""
    _run(cmd, label)
    Path(stamp).parent.mkdir(parents=True, exist_ok=True)
    Path(stamp).write_text(f"{label}\n", encoding="utf-8")


def _digest_files(files: list[str]) -> str:
    """md5 over the *content* of each file (sorted, name-tagged) -- the recipe
    fingerprint shared by _RecipeTracker (the run/skip uptodate) and
    build_or_refresh (the FULL/REFRESH decision), so the two never disagree.

    YAML configs are folded in by their PARSED content (ContentChecker._digest),
    exactly like the file_dep checker -- so a comment/whitespace-only edit to a
    shared cad/config/*.yaml doesn't force a spurious assembly FULL rebuild, while
    a real placement-value change (which needs a re-insert) still does."""
    h = hashlib.md5()
    for f in sorted(files):
        h.update(f.encode())
        try:
            h.update(ContentChecker._digest(f).encode())
        except OSError:
            h.update(b"<missing>")
    return h.hexdigest()


def _recipe_files(stem: str) -> list[str]:
    """Files whose change forces a FULL rebuild of <stem> (re-insert/re-mate)
    rather than a part-only refresh: the assembly script, its hooks, the helper
    modules it transitively imports (``_helper_deps`` -> ``module_deps_of``, incl.
    _assembly/_transforms), and the _config/YAML data layer (a placement like
    channels.station_pitch_mm changing must re-insert components at new
    coordinates, which an in-place reload cannot do)."""
    asm_script = script_for(stem)
    hooks = [str((SCRIPTS_DIR / h).resolve()) for h in POST_ASSEMBLY.get(stem, ())]
    return [str(asm_script.resolve()), *hooks, *_helper_deps(asm_script), *_CONFIG_YAMLS]


def _recipe_sidecar(stem: str) -> Path:
    """Sidecar holding the recipe digest of the last SUCCESSFUL build of <stem>,
    next to the .SLDASM (cad/out, gitignored). build_or_refresh reads it so the
    FULL/REFRESH decision needs no process-local state and stays correct under
    ``doit -n`` workers (which may run the action in a separate process)."""
    return CAD_OUT / "sldasm" / f".{stem.replace('_', '-')}.recipe.md5"


def task_part():
    """One task per part stem; addressable as ``part:<stem>``."""
    for script in part_scripts():
        stem = script.stem.removeprefix("build_")
        yield {
            "name": stem,
            "file_dep": [str(script.resolve()), *_helper_deps(script), *_CONFIG_YAMLS],
            "targets": [_sldprt(stem)],
            # COM spine: serialize parts on the single SW seat (see _spine_dep).
            "task_dep": _spine_dep(f"part:{stem}"),
            "actions": [CmdAction([sys.executable, str(script)], cwd=str(REPO_ROOT))],
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
    target_missing = not Path(targets[0]).exists()
    digest = _digest_files(_recipe_files(stem))
    sidecar = _recipe_sidecar(stem)
    try:
        last = sidecar.read_text(encoding="utf-8").strip()
    except OSError:
        last = None
    recipe_changed = (last is None or last != digest)  # missing sidecar = FULL

    asm_script = SCRIPTS_DIR / f"build_{stem}_assembly.py"
    hooks = [SCRIPTS_DIR / h for h in POST_ASSEMBLY.get(stem, ())]
    if target_missing or recipe_changed:
        why = "target missing" if target_missing else "recipe changed"
        _run([sys.executable, str(asm_script)], f"FULL build {stem} ({why})")
        for hook in hooks:
            _run([sys.executable, str(hook)], f"hook {hook.name}")
    else:
        _run([sys.executable, str(SCRIPTS_DIR / "refresh_assembly.py"), stem],
             f"REFRESH {stem}")
    # _run raised if the build failed, so we only get here on success: record this
    # build's recipe digest for the next run's FULL/REFRESH decision.
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(digest + "\n", encoding="utf-8")


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
    _force_remove(_recipe_sidecar(stem))
    _force_remove(CAD_OUT / "png" / stem.replace("_", "-"))
    if stem == "channel":
        for variant in sorted(
            (CAD_OUT / "sldprt").glob("channel-spring-installed-stretch*.SLDPRT")
        ):
            _force_remove(variant)


def task_assembly():
    """One task per assembly stem (``assembly:<stem>``).

    file_dep edges -- the assembly script, _common.py, this stem's hooks, and the
    referenced .SLDPRT/sub-.SLDASM targets -- give doit both ordering (top depends
    on the sub .SLDASMs, so it runs after) and the refresh/full decision (only
    parts changed -> refresh).
    """
    for stem in ASSEMBLY_ORDER:
        refs = references_of(stem)
        ref_targets = [
            _sldasm(r) if r in ASSEMBLY_ORDER else _sldprt(r) for r in refs
        ]
        # Recipe = the files whose change forces a FULL rebuild (re-insert/re-mate)
        # vs a part-only refresh: the assembly script, its hooks, AND the shared
        # helper/_config/YAML data layer (a placement like channels.station_pitch_mm
        # changing must re-insert components at new coordinates, which an in-place
        # reload cannot do; codex review #2). Factored into _recipe_files so
        # build_or_refresh computes the identical digest.
        recipe_files = _recipe_files(stem)
        yield {
            "name": stem,
            "file_dep": [*recipe_files, *ref_targets],
            "targets": [_sldasm(stem)],
            "uptodate": [_RecipeTracker(stem, recipe_files)],
            # COM spine: serialize assemblies after every part on the SW seat.
            "task_dep": _spine_dep(f"assembly:{stem}"),
            "actions": [(build_or_refresh, [stem])],
            "clean": [(_clean_assembly, [stem])],
            "verbosity": 2,
        }


def task_verify():
    """SolidWorks verification suites -- need SW open, run on the COM spine.

    ``verify:soundness`` / ``verify:subsystems`` / ``verify:kinematics`` each wrap
    ``verify.py --suite <x>`` and stamp ``cad/out/reports/verify-<x>.ok`` on
    success. The ``verify:`` prefix marks them as SolidWorks-dependent (vs the
    SolidWorks-free ``check:`` tasks).
    """
    asm_targets = [_sldasm(s) for s in ASSEMBLY_ORDER]
    suite_deps = {
        "soundness": asm_targets,
        "subsystems": asm_targets,
        "kinematics": [
            _sldasm("pen"),
            str((SCRIPTS_DIR / "pen_driver.py").resolve()),
            str((SCRIPTS_DIR / "truth_model.py").resolve()),
        ],
    }
    # Pass the graph's assemblies EXPLICITLY (dashed names) rather than letting
    # verify.py glob every *.SLDASM under cad/out/sldasm -- a stray/scratch
    # assembly left in a worktree must not be verified (codex review). kinematics
    # targets only the pen sub (verify.py's own default), so it needs no names.
    asm_names = [s.replace("_", "-") for s in ASSEMBLY_ORDER]
    for suite, deps in suite_deps.items():
        stamp = str(REPORTS / f"verify-{suite}.ok")
        cmd = [sys.executable, str(VERIFY_PY)]
        if suite in ("soundness", "subsystems"):
            cmd += asm_names
        cmd += ["--suite", suite]
        yield {
            "name": suite,
            "file_dep": [str(VERIFY_PY), *deps],
            "targets": [stamp],
            "task_dep": _spine_dep(f"verify:{suite}"),
            "actions": [(_run_stamped, [cmd, f"verify {suite}", stamp])],
            "clean": True,
            "verbosity": 2,
        }


def task_check():
    """SolidWorks-FREE checks -- no COM, so they run in parallel under ``-n N``.

    ``check:math`` / ``check:config`` wrap ``verify.py --suite ...`` (verify.py
    runs those two without connecting to SolidWorks); ``check:graph`` /
    ``check:nameplate`` / ``check:recipe`` wrap the pure-python unit tests via
    pytest. None is on the COM spine.
    """
    dims = str((REPO_ROOT / "cad" / "DIMENSIONS.md").resolve())
    config_py = str((SCRIPTS_DIR / "_config.py").resolve())
    # The tolerance audit (check:config) scans every build_*.py for PART_NAME, so a
    # part script added/renamed without touching YAML/DIMENSIONS must still
    # invalidate the stamp (codex review).
    part_script_deps = [str(p.resolve()) for p in part_scripts()]
    pytest_cmd = [sys.executable, "-m", "pytest", "-q"]
    specs = {
        "math": {
            # truth_model reads harmonics/phases/amplitudes/magnification from
            # _config + the YAML layer, so those must invalidate the math stamp
            # too (codex review).
            "file_dep": [str(VERIFY_PY),
                         str((SCRIPTS_DIR / "truth_model.py").resolve()),
                         config_py, *_CONFIG_YAMLS],
            "cmd": [sys.executable, str(VERIFY_PY), "--suite", "math"],
        },
        "config": {
            "file_dep": [str(VERIFY_PY),
                         str((SCRIPTS_DIR / "gen_dimensions.py").resolve()),
                         config_py, dims, *_CONFIG_YAMLS, *part_script_deps],
            "cmd": [sys.executable, str(VERIFY_PY), "--suite", "config"],
        },
        "graph": {
            "file_dep": [str((SCRIPTS_DIR / "_buildgraph.py").resolve()),
                         str((SCRIPTS_DIR / "test_buildgraph.py").resolve())],
            "cmd": [*pytest_cmd, str(SCRIPTS_DIR / "test_buildgraph.py")],
        },
        "nameplate": {
            "file_dep": [str((SCRIPTS_DIR / "_nameplate_geometry.py").resolve()),
                         str((SCRIPTS_DIR / "test_nameplate_geometry.py").resolve())],
            "cmd": [*pytest_cmd, str(SCRIPTS_DIR / "test_nameplate_geometry.py")],
        },
        "recipe": {
            "file_dep": [str((REPO_ROOT / "dodo.py").resolve()),
                         str((SCRIPTS_DIR / "test_dodo_recipe.py").resolve())],
            "cmd": [*pytest_cmd, str(SCRIPTS_DIR / "test_dodo_recipe.py")],
        },
    }
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
    """Neutral-format export (STEP / STL / scene boxes). Needs SW; COM spine.

    Always runs ``export_models.py`` (``uptodate: False``) -- it self-checks every
    output's per-file staleness cheaply and prints "all exports fresh" when there
    is nothing to do. We do NOT gate on a single declared target: a deleted
    STEP/STL/colors output (with the boxes JSON + CAD inputs unchanged) must still
    be regenerated, which doit would otherwise skip (codex review).
    """
    target = str((CAD_OUT / "boxes" / "harmonic-analyzer.json").resolve())
    deps = ([_sldprt(s) for s in part_stems()]
            + [_sldasm(s) for s in ASSEMBLY_ORDER])
    return {
        "file_dep": [str(EXPORT_PY), *deps],
        "targets": [target],
        "task_dep": _spine_dep("export"),
        "uptodate": [False],
        "actions": [CmdAction([sys.executable, str(EXPORT_PY)], cwd=str(REPO_ROOT))],
        "verbosity": 2,
    }


def _run_release(relargs):
    """Run cut_release.py, forwarding any positional args (``doit release -- v0.2.0``)."""
    _run([sys.executable, str(RELEASE_PY), *relargs], "cut release")


def task_release():
    """Cut a tagged release (Pack-and-Go + neutral exports + diff + GitHub
    release). OPT-IN -- not in default_tasks. Needs SW + gh; spine tail.

    Publishing is a side effect (no doit target), so it always runs. Forward
    args after ``--``: ``doit release -- v0.2.0 --draft`` (default auto patch-bump).
    Gated on EVERY gate: ``export`` pulls the SW ``verify:*`` chain via the spine,
    and the offline ``check:*`` gates are added explicitly so a release cannot
    publish past a stale/failing math/config/unit-test gate (codex review).
    """
    return {
        "task_dep": [*_spine_dep("release"), *(f"check:{c}" for c in _CHECK_NAMES)],
        "uptodate": [False],
        "pos_arg": "relargs",
        "actions": [(_run_release,)],
        "verbosity": 2,
    }


def task_build():
    """THE fully-safe entry point (also ``default_tasks``): every part + assembly
    + every gate (SolidWorks ``verify:*`` and offline ``check:*``).

    No neutral export / Pack-and-Go -- those are downstream on the spine, and doit
    only runs a selected task's upstream prerequisites. Use ``doit -n N`` to fan
    out the ``check:*`` work alongside the serial COM stream.
    """
    return {
        "actions": None,
        "task_dep": (
            [f"part:{s}" for s in part_stems()]
            + [f"assembly:{s}" for s in ASSEMBLY_ORDER]
            + [f"verify:{s}" for s in _VERIFY_NAMES]
            + [f"check:{s}" for s in _CHECK_NAMES]
        ),
    }


def task_build_bare():
    """Quick rebuild: parts + assemblies only -- no verification, no export."""
    return {
        "actions": None,
        "task_dep": (
            [f"part:{s}" for s in part_stems()]
            + [f"assembly:{s}" for s in ASSEMBLY_ORDER]
        ),
    }
