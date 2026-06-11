r"""Orchestrator: rebuild the entire machine from scratch (M6.5).

Runs every part reproduction script, then the four subassemblies, then
the top-level harmonic-analyzer.SLDASM -- each as its own subprocess (one
SolidWorks COM session at a time, exactly like running the scripts by
hand). Stops at the first failure with that script's exit code.

Checkpointing: a script is SKIPPED when its artefact already exists in
cad/out (so a crashed or interrupted run resumes where it stopped).
``--clean`` deletes cad/out/{sldprt,sldasm,png} first for a true
from-empty rebuild.

Artefact mapping: build_<name>.py -> cad/out/sldprt/<name with - >.SLDPRT;
build_<name>_assembly.py -> cad/out/sldasm/<name>.SLDASM.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_all.py [--clean]
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
CAD_OUT = SCRIPTS_DIR.parent / "out"

ASSEMBLY_ORDER = ("frame", "drive_train", "channel", "output", "harmonic_analyzer")


def part_scripts() -> list[Path]:
    """Every build_*.py except the assemblies and this orchestrator."""
    out = []
    for path in sorted(SCRIPTS_DIR.glob("build_*.py")):
        if path.name == "build_all.py" or path.name.endswith("_assembly.py"):
            continue
        out.append(path)
    return out


def artefact_for(script: Path) -> Path:
    stem = script.stem.removeprefix("build_")
    if stem.endswith("_assembly"):
        name = stem.removesuffix("_assembly").replace("_", "-")
        return CAD_OUT / "sldasm" / f"{name}.SLDASM"
    return CAD_OUT / "sldprt" / f"{stem.replace('_', '-')}.SLDPRT"


def run_script(script: Path) -> None:
    artefact = artefact_for(script)
    if artefact.exists():
        print(f"--  skip {script.name} ({artefact.name} exists)")
        return
    print(f">>  {script.name}")
    started = time.monotonic()
    proc = subprocess.run([sys.executable, str(script)], cwd=SCRIPTS_DIR.parent.parent)
    elapsed = time.monotonic() - started
    if proc.returncode:
        print(f"!!  {script.name} failed (exit {proc.returncode}) after {elapsed:.0f}s")
        sys.exit(proc.returncode)
    if not artefact.exists():
        print(f"!!  {script.name} exited 0 but {artefact} is missing")
        sys.exit(1)
    print(f"OK  {script.name} in {elapsed:.0f}s")


def main() -> int:
    if "--clean" in sys.argv[1:]:
        for sub in ("sldprt", "sldasm", "png"):
            target = CAD_OUT / sub
            if target.exists():
                shutil.rmtree(target)
                print(f"--  cleaned {target}")

    queue = part_scripts() + [
        SCRIPTS_DIR / f"build_{name}_assembly.py" for name in ASSEMBLY_ORDER
    ]
    missing = [p.name for p in queue if not p.exists()]
    if missing:
        print(f"!!  missing scripts: {missing}")
        return 1

    started = time.monotonic()
    for i, script in enumerate(queue, 1):
        print(f"[{i}/{len(queue)}] ", end="")
        run_script(script)
    print(f"\nAll {len(queue)} scripts done in {(time.monotonic() - started) / 60.0:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
