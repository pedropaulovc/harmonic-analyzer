r"""Snap the assemblies back to the deterministic export pose (Default config).

The ``operating`` config (build_operating_config.py) frees the crank, and a
Basic Motion study (build_motion_study.py) turns it -- both leave the crank, and
through the live meshes the whole gear train, parked at an ARBITRARY angle. The
renders / 469-pair photo pipeline are gated on the canonical 0-DOF pose, so after
any hand-drag or motion study you must return there. This does exactly that:

  1. activate the ``Default`` configuration. The crank park driver is LIVE in
     Default, so it re-pins the single train DOF and SW re-solves every rotating
     member back to its canonical angle -- the under-defined ``operating`` pose is
     not carried over (each config stores its own last-solved positions).
  2. ForceRebuild.
  3. assert every top-level component is fully defined (0 DOF) AND the model is
     interference-free -- the same gates the build uses. This is the proof the
     reset actually restored determinism, not just switched a config name.
  4. with ``save`` (argv): re-save in place so the on-disk active config is
     Default. Default by default is READ-ONLY -- a motion study never saves, so
     the file is usually already clean; ``save`` is only for when something
     (an interrupted build) left the doc dirty.

Runs on both drive-train.SLDASM and harmonic-analyzer.SLDASM (whichever exist),
so one call resets the sub and the full device together.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\reset_pose.py [save]
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from _common import (
    OUT_SLDASM,
    assert_components_fully_defined,
    assert_model_healthy,
    check,
    check_no_interference,
    log,
    run_build,
)

REST = "Default"  # the deterministic, fully-defined, render/photo-gated pose
# Reset the sub first, then the parent (the parent references the sub's Default
# child config, so the sub being clean first keeps the parent solve honest).
ASSEMBLIES = ("drive-train", "harmonic-analyzer")


def _save_in_place(adapter: Any, sldasm: Path) -> None:
    """Silent in-place ``Save3`` (real BYREF VARIANTs), only if the doc is dirty.

    Same recipe the config builds use (see build_engagement_configs._save_assembly_
    in_place for the full why-not-save_file rationale): the active doc IS this path,
    so Save3(Silent | SaveReferenced, &err, &warn) writes without a dialog.
    """
    import pythoncom
    from win32com.client import VARIANT

    asm = adapter.currentModel
    if not bool(adapter._attempt(lambda: asm.GetSaveFlag(), default=True)):
        log(f"{sldasm.name} already clean -- nothing to save")
        return
    before = sldasm.stat().st_mtime
    err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    ret = adapter._attempt(lambda: asm.Save3(1 | 8, err, warn), default=False)
    if sldasm.stat().st_mtime <= before:
        raise RuntimeError(
            f"{sldasm.name} mtime unchanged after Save3(Silent) "
            f"(ret={ret}, err={err.value}, warn={warn.value})")
    log(f"saved {sldasm.name} (ret={ret}, err={err.value}, warn={warn.value})")


async def _reset_one(adapter: Any, name: str, do_save: bool) -> str:
    sldasm = OUT_SLDASM / f"{name}.SLDASM"
    if not sldasm.exists():
        log(f"{sldasm.name} not built -- skipping")
        return f"{name}: skipped (missing)"

    check(f"open {name}", await adapter.open_model(str(sldasm)))
    log(f"{name}: configs = {check('list configurations', await adapter.list_configurations())}")
    log(f"{name}: activating {REST}")
    check(f"activate {REST}", await adapter.set_active_configuration(REST))

    log(f"--- {name}: verifying deterministic pose ({REST}, strict 0 DOF) ---")
    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    assert_model_healthy(adapter, label=name, deep=True)
    log(f"{name}: restored to the canonical 0-DOF pose")

    if do_save:
        _save_in_place(adapter, sldasm)
    return f"{name}: reset to {REST}{' (saved)' if do_save else ''}"


async def build(adapter: Any) -> dict[str, str]:
    do_save = len(sys.argv) > 1 and sys.argv[1].lower() == "save"
    results = []
    for name in ASSEMBLIES:
        results.append(await _reset_one(adapter, name, do_save))
    return {"reset": "; ".join(results)}


if __name__ == "__main__":
    sys.exit(run_build(build))
