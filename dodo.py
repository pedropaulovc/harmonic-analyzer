r"""Incremental build graph for the machine (doit).

Replaces the hand-rolled ``cad/scripts/build_all.py`` orchestrator. doit decides
*whether* each part/assembly is stale (md5 content hash, immune to git/worktree
mtime churn); the refresh primitive makes the assembly recipe cheap.

A ``.SLDASM`` is a thin reference layer over its part files, so when only a
referenced ``.SLDPRT`` changed, an assembly is REFRESHED (reopen + per-config
ForceRebuild3 + gates + in-place Save3 -- seconds) instead of rebuilt from
scratch (re-insert + re-mate ~122 components -- ~500 s). The recipe escalates to a
FULL rebuild (+ engagement-config hooks) when the assembly script / _common.py / a
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

import shutil
import subprocess
import sys
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


# --- Parts: build_<stem>.py -> out/sldprt/<dashed>.SLDPRT. A part is stale when
# its own script, the shared modules, or any config yaml changed (coarse but
# correct: a _common/_config/yaml edit can invalidate any part -- rare).
_SHARED_PART_DEPS = [str(COMMON.resolve()), str(CONFIG_PY.resolve())] + [
    str(p.resolve()) for p in sorted(CONFIG_DIR.glob("*.yaml"))
]


def task_part():
    """One task per part stem; addressable as ``part:<stem>``."""
    for script in part_scripts():
        stem = script.stem.removeprefix("build_")
        yield {
            "name": stem,
            "file_dep": [str(script.resolve()), *_SHARED_PART_DEPS],
            "targets": [_sldprt(stem)],
            "actions": [CmdAction([sys.executable, str(script)], cwd=str(REPO_ROOT))],
            "clean": True,
            "verbosity": 2,
        }


def build_or_refresh(stem, dependencies, changed, targets):
    """FULL rebuild vs cheap REFRESH for one assembly stem.

    FULL (run build_<stem>_assembly.py + its POST_ASSEMBLY hooks) when the target
    is missing OR the recipe itself changed (assembly script / _common.py / a hook
    script) -- the engagement configs only exist after a fresh create_assembly, so
    the hooks must re-run. Otherwise only referenced parts changed: REFRESH
    (refresh_assembly.py, no hooks -- reopening preserves the existing configs).
    """
    asm_script = SCRIPTS_DIR / f"build_{stem}_assembly.py"
    hooks = [SCRIPTS_DIR / h for h in POST_ASSEMBLY.get(stem, ())]
    recipe = {str(asm_script.resolve()), str(COMMON.resolve())}
    recipe |= {str(h.resolve()) for h in hooks}

    target_missing = not Path(targets[0]).exists()
    changed_recipe = {str(Path(c).resolve()) for c in (changed or [])} & recipe

    if target_missing or changed_recipe:
        why = "target missing" if target_missing else f"recipe changed {sorted(changed_recipe)}"
        _run([sys.executable, str(asm_script)], f"FULL build {stem} ({why})")
        for hook in hooks:
            _run([sys.executable, str(hook)], f"hook {hook.name}")
        return
    _run([sys.executable, str(SCRIPTS_DIR / "refresh_assembly.py"), stem],
         f"REFRESH {stem}")


def _clean_assembly(stem):
    """Remove the .SLDASM target and wipe its png/<dashed> render dir."""
    target = Path(_sldasm(stem))
    png_dir = CAD_OUT / "png" / stem.replace("_", "-")
    if target.exists():
        target.unlink()
    if png_dir.exists():
        shutil.rmtree(png_dir, ignore_errors=True)


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
        yield {
            "name": stem,
            "file_dep": [str(asm_script.resolve()), str(COMMON.resolve()),
                         *hooks, *ref_targets],
            "targets": [_sldasm(stem)],
            "actions": [(build_or_refresh, [stem])],
            "clean": [(_clean_assembly, [stem])],
            "verbosity": 2,
        }
