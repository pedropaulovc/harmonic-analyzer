r"""Incremental build graph for the machine (doit).

Replaces the hand-rolled ``cad/scripts/build_all.py`` orchestrator. doit decides
*whether* each part/assembly is stale (md5 content hash, immune to git/worktree
mtime churn); the refresh primitive makes the assembly recipe cheap.

A ``.SLDASM`` is a thin reference layer over its part files, so when only a
referenced ``.SLDPRT`` changed, an assembly is REFRESHED (reopen + per-config
ForceRebuild3 + gates + in-place Save3 -- seconds) instead of rebuilt from
scratch (re-insert + re-mate ~122 components -- ~500 s). The recipe escalates to a
FULL rebuild (+ any post-assembly hooks) when the assembly script / _common.py / a
hook changed, or the target is missing. A refresh that hits a dangling mate, free
DOF, or interference FAILS LOUD (non-zero exit, .SLDASM untouched); recover with
the full escape below.

Install (one-off, in the Windows SolidWorks build venv -- this repo has no
pyproject.toml of its own)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe -m pip install doit

Run with that same venv's python (SolidWorks already open). NEVER pass -n/-P:
a single SolidWorks STA session means parallel tasks deadlock (guarded below)::

    set "DOIT=C:\src\SolidworksMCP-python\.venv\Scripts\python.exe -m doit"

    %DOIT%                       # build/refresh everything stale, in order
    %DOIT% assembly:output       # just that assembly + its stale prereqs
    %DOIT% part:summing_lever    # just that part
    %DOIT% list --all            # every part + assembly task
    %DOIT% list --deps           # tasks with their file_deps
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
    references_of,
    script_for,
)

REPO_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = REPO_ROOT / "cad" / "config"
COMMON = SCRIPTS_DIR / "_common.py"
CONFIG_PY = SCRIPTS_DIR / "_config.py"

# --- Parallel guard: a single SolidWorks STA session, so any parallel run
# deadlocks. doit's parallelism is CLI-only (-n/--process/-P/--parallel-type);
# it is NOT settable via DOIT_CONFIG, so hard-fail here before any task runs.
_PARALLEL_TOKENS = ("-n", "--process", "--num-process", "-P", "--parallel-type")


def _guard_serial() -> None:
    for tok in sys.argv[1:]:
        base = tok.split("=", 1)[0]
        parallel = (
            base in _PARALLEL_TOKENS
            or (base.startswith("-n") and base[2:].isdigit())
            or (base.startswith("-P") and len(base) > 2)
        )
        if parallel:
            raise SystemExit(
                "doit: parallel disabled -- one SolidWorks STA session, never pass "
                "-n/-P (parallel tasks deadlock the COM seat)")


_guard_serial()

DOIT_CONFIG = {
    "backend": "json",
    "dep_file": str(CAD_OUT / ".doit.db"),
    "default_tasks": ["part", "assembly"],
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


def task_part():
    """One task per part stem; addressable as ``part:<stem>``."""
    for script in part_scripts():
        stem = script.stem.removeprefix("build_")
        yield {
            "name": stem,
            "file_dep": [str(script.resolve()), *_SHARED_BUILD_DEPS],
            "targets": [_sldprt(stem)],
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
            "actions": [(build_or_refresh, [stem])],
            "clean": [(_clean_assembly, [stem])],
            "verbosity": 2,
        }
