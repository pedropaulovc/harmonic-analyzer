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
    %DOIT% assembly:output       # just that assembly + its stale prereqs
    %DOIT% part:summing_lever    # just that part
    %DOIT% verify:soundness      # one SW gate; check:math one offline gate
    %DOIT% export                # neutral STEP/STL/scene export
    %DOIT% release -- v0.2.0     # cut a release (args after --; opt-in)
    %DOIT% list --all            # every task
    %DOIT% clean                 # remove targets (+ wipe png/<asm>)

Full-rebuild escape (idiomatic doit -- a missing target forces a run, and
build_or_refresh takes the FULL branch when the target is absent)::

    del cad\out\sldasm\output.SLDASM
    %DOIT% forget assembly:output    # optional: also drop the cached hash
    %DOIT% assembly:output
"""

from __future__ import annotations

import hashlib
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

from doit.action import CmdAction

sys.path.insert(0, str(Path(__file__).resolve().parent / "cad" / "scripts"))

from _buildgraph import (  # noqa: E402
    ASSEMBLY_ORDER,
    CAD_OUT,
    POST_ASSEMBLY,
    SCRIPTS_DIR,
    artefact_for,
    part_scripts,
    part_stems,
    references_of,
    script_for,
)

REPO_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = REPO_ROOT / "cad" / "config"
COMMON = SCRIPTS_DIR / "_common.py"
CONFIG_PY = SCRIPTS_DIR / "_config.py"

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

DOIT_CONFIG = {
    "backend": "json",
    "dep_file": str(CAD_OUT / ".doit.db"),
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


# --- Shared build inputs that can invalidate ANY part or assembly geometry: the
# helper modules every build script imports (_common, _config, _gear, _chain,
# _chain_link) plus the YAML data layer. Coarse but correct -- a helper or YAML
# edit can change any body, and content-hashing means an edit that does not change
# a given part's bytes still costs only that one rebuild. (Excludes _buildgraph.py:
# it is the build-GRAPH helper imported here, not a geometry input.) Without these,
# editing e.g. _gear.py leaves every gear .SLDPRT reported up to date and
# downstream assemblies refresh from stale parts (codex review #1).
_HELPER_MODULES = [
    str(p.resolve())
    for p in sorted(SCRIPTS_DIR.glob("_*.py"))
    if p.name != "_buildgraph.py"
]
_CONFIG_YAMLS = [str(p.resolve()) for p in sorted(CONFIG_DIR.glob("*.yaml"))]
_SHARED_BUILD_DEPS = _HELPER_MODULES + _CONFIG_YAMLS

# --- Stamp files: the verify:/check: gates produce no CAD artefact, so a stamp
# under cad/out/reports/ is their doit ``target``. That makes each gate
# incremental (re-runs only when a file_dep changes) and individually
# addressable, exactly like a part/assembly target.
REPORTS = CAD_OUT / "reports"
VERIFY_PY = (SCRIPTS_DIR / "verify.py").resolve()
EXPORT_PY = (SCRIPTS_DIR / "export_models.py").resolve()
RELEASE_PY = (SCRIPTS_DIR / "cut_release.py").resolve()


def _run_stamped(cmd: list[str], label: str, stamp: str) -> None:
    """Run a gate subprocess; on success write its stamp target. _run raises on
    non-zero, so a failed gate never writes a stamp (stays stale -> re-runs)."""
    _run(cmd, label)
    Path(stamp).parent.mkdir(parents=True, exist_ok=True)
    Path(stamp).write_text(f"{label}\n", encoding="utf-8")


def task_part():
    """One task per part stem; addressable as ``part:<stem>``."""
    for script in part_scripts():
        stem = script.stem.removeprefix("build_")
        yield {
            "name": stem,
            "file_dep": [str(script.resolve()), *_SHARED_BUILD_DEPS],
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
# failed task never corrupts it. It stashes the changed-bit into _RECIPE_CHANGED
# for build_or_refresh to read in the same (serial) process.
_RECIPE_CHANGED: dict[str, bool] = {}


class _RecipeTracker:
    """uptodate: True (up-to-date) when the recipe is unchanged since last success."""

    def __init__(self, stem: str, recipe_files: list[str]):
        self.stem = stem
        self.recipe_files = sorted(recipe_files)
        self.digest: str | None = None

    def _calc(self) -> str:
        h = hashlib.md5()
        for f in self.recipe_files:
            h.update(f.encode())
            try:
                h.update(Path(f).read_bytes())
            except OSError:
                h.update(b"<missing>")
        return h.hexdigest()

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

    The recipe-changed bit comes from _RecipeTracker (uptodate), NOT doit's
    ``changed`` arg -- the latter is corrupted by a prior failed task (D2).
    """
    asm_script = SCRIPTS_DIR / f"build_{stem}_assembly.py"
    hooks = [SCRIPTS_DIR / h for h in POST_ASSEMBLY.get(stem, ())]

    target_missing = not Path(targets[0]).exists()
    recipe_changed = _RECIPE_CHANGED.get(stem, True)  # default FULL = fail-safe

    if target_missing or recipe_changed:
        why = "target missing" if target_missing else "recipe changed"
        _run([sys.executable, str(asm_script)], f"FULL build {stem} ({why})")
        for hook in hooks:
            _run([sys.executable, str(hook)], f"hook {hook.name}")
        return
    _run([sys.executable, str(SCRIPTS_DIR / "refresh_assembly.py"), stem],
         f"REFRESH {stem}")


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
    on output.SLDASM, so it runs after) and the refresh/full decision (only parts
    changed -> refresh).
    """
    for stem in ASSEMBLY_ORDER:
        asm_script = script_for(stem)
        hooks = [str((SCRIPTS_DIR / h).resolve()) for h in POST_ASSEMBLY.get(stem, ())]
        refs = references_of(stem)
        ref_targets = [
            _sldasm(r) if r in ASSEMBLY_ORDER else _sldprt(r) for r in refs
        ]
        # Recipe = everything whose change needs a FULL rebuild (re-insert/re-mate),
        # not a part-only refresh: the assembly script, its hooks, the helper
        # modules, AND the _config/YAML data layer -- a placement like
        # channels.station_pitch_mm changing means components must be re-inserted at
        # new coordinates, which an in-place reload cannot do (codex review #2).
        recipe_files = [str(asm_script.resolve()), *hooks, *_SHARED_BUILD_DEPS]
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
            _sldasm("output"),
            str((SCRIPTS_DIR / "pen_driver.py").resolve()),
            str((SCRIPTS_DIR / "truth_model.py").resolve()),
        ],
    }
    for suite, deps in suite_deps.items():
        stamp = str(REPORTS / f"verify-{suite}.ok")
        cmd = [sys.executable, str(VERIFY_PY), "--suite", suite]
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
    pytest_cmd = [sys.executable, "-m", "pytest", "-q"]
    specs = {
        "math": {
            "file_dep": [str(VERIFY_PY),
                         str((SCRIPTS_DIR / "truth_model.py").resolve())],
            "cmd": [sys.executable, str(VERIFY_PY), "--suite", "math"],
        },
        "config": {
            "file_dep": [str(VERIFY_PY),
                         str((SCRIPTS_DIR / "gen_dimensions.py").resolve()),
                         str((SCRIPTS_DIR / "_config.py").resolve()),
                         dims, *_CONFIG_YAMLS],
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

    Wraps ``export_models.py`` (which self-checks per-file staleness). file_dep on
    every part + assembly target; the spine edge keeps it after the verify gates.
    """
    target = str((CAD_OUT / "boxes" / "harmonic-analyzer.json").resolve())
    deps = ([_sldprt(s) for s in part_stems()]
            + [_sldasm(s) for s in ASSEMBLY_ORDER])
    return {
        "file_dep": [str(EXPORT_PY), *deps],
        "targets": [target],
        "task_dep": _spine_dep("export"),
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
    Depends on ``export`` (and via the spine, every SW verify gate).
    """
    return {
        "task_dep": _spine_dep("release"),
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
            + [f"verify:{s}" for s in ("soundness", "subsystems", "kinematics")]
            + [f"check:{s}" for s in
               ("math", "config", "graph", "nameplate", "recipe")]
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
