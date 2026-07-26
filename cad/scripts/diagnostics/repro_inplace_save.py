r"""Isolated repro: can an assembly OPENED from disk be saved in place silently,
with no UIAutomation watchdog?

Background: build_engagement_configs first tried ``adapter.save_file(PATH)`` and
it destroyed drive-train.SLDASM. The conclusion drawn at the time -- "this Makers
seat refuses every silent save, only the blocking Save() + a Save-All dialog
watchdog persists" -- is suspect: every NORMAL build saves fine through the SAME
``save_file`` (via save_assembly_and_images). The difference is only that a normal
build CREATES the assembly (active doc title != target path) while the engagement
build OPENS it (active doc title == target path), so ``save_file``'s SaveAs branch
does ``CloseDoc(PATH)`` + ``os.remove(PATH)`` on the very doc it is saving.

This repro tests the hypothesis that the right in-place save is simply
``ModelDoc2.Save3(swSaveAsOptions_Silent, &err, &warn)`` -- with the two [out]
params passed as proper pywin32 BYREF VARIANTs (the adapter's no-path branch
passes ``None, None``, which fails the COM call and falls through to the blocking
``Save()``).

It works on a COPY so the real drive-train.SLDASM stays pristine, and tries the
candidate save calls in order, logging mtime + GetSaveFlag + error/warning codes.

    uv run python cad\scripts\diagnostics\repro_inplace_save.py

LATE-BOUND PROBE: this script drives SolidWorks through its own
``GetObject``/``Dispatch`` (or a raw ``adapter.currentModel``), NOT the makepy
wrapper, so its ``[out]`` params land in the ``VT_BYREF`` VARIANTs passed in
rather than in the return tuple. That is the OPPOSITE of the build path, where
``_common._early_bound`` guarantees an early-bound object and the outs ride the
return tuple. Both are correct for their binding -- mixing them is the trap that
reads as "no data" instead of failing. See memory/sw-assembly-mate-diagnostics-api.md.
"""

from __future__ import annotations

import os
import shutil
import sys
from typing import Any

import pythoncom
from win32com.client import VARIANT

from _common import OUT_SLDASM, _flag, _read_member, check, log, run_build

SILENT = 1           # swSaveAsOptions_Silent
# swSaveAsOptions_SaveReferenced is 4; 8 is AvoidRebuildOnSave (checked against
# the swSaveAsOptions_e reference, not inferred). This constant said 8, so the
# retry below silently asked for AvoidRebuildOnSave and never actually saved
# references -- a false failure on the very path it was written to exercise.
SAVE_REFERENCED = 4
SRC = OUT_SLDASM / "drive-train.SLDASM"
COPY = OUT_SLDASM / "_repro_inplace.SLDASM"


def _byref_i4() -> VARIANT:
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


def _save_flag(model: Any) -> bool:
    return bool(model.GetSaveFlag())


def _dirty_refs(model: Any) -> list[str]:
    comps = model.GetComponents(False) or []
    out = []
    for c in comps:
        _flag(c, "IComponent2")
        md = _read_member(c, "GetModelDoc2")
        if md is not None and bool(_read_member(md, "GetSaveFlag")):
            out.append(str(_read_member(md, "GetPathName")))
    return out


def _try_save3(model: Any, options: int, label: str, path: str) -> bool:
    before = os.path.getmtime(path)
    err, warn = _byref_i4(), _byref_i4()
    try:
        ret = model.Save3(options, err, warn)
    except Exception as exc:  # noqa: BLE001 -- this is the diagnostic
        log(f"  {label}: Save3 raised {type(exc).__name__}: {exc}")
        return False
    after = os.path.getmtime(path)
    changed = after > before
    log(f"  {label}: ret={ret} err={err.value} warn={warn.value} "
        f"mtime={'CHANGED' if changed else 'unchanged'} "
        f"GetSaveFlag={_save_flag(model)}")
    return changed


async def build(adapter: Any) -> dict[str, str]:
    if not SRC.exists():
        raise RuntimeError(f"{SRC} missing -- build the drive-train first")
    shutil.copy2(SRC, COPY)
    log(f"copied {SRC.name} -> {COPY.name} (real file stays untouched)")

    try:
        path = str(COPY)
        check("open copy", await adapter.open_model(path))
        model = adapter.currentModel
        log(f"opened copy: GetSaveFlag={_save_flag(model)} (expect False=clean)")
        log(f"dirty referenced docs at open: {_dirty_refs(model)}")

        # Dirty the ASSEMBLY only, the way the engagement build does: add a derived
        # config (no part-doc change). This is the exact state that supposedly
        # needs the watchdog.
        from solidworks_mcp.adapters.base import CreateConfigurationParameters
        check("create _repro_cfg", await adapter.create_configuration(
            CreateConfigurationParameters(
                name="_repro_cfg", parent="Default",
                comment="repro dirtier", description="repro")))
        log(f"after add config: GetSaveFlag={_save_flag(model)} (expect True=dirty)")
        log(f"dirty referenced docs after config: {_dirty_refs(model)}")

        # The candidate clean save: in-place Save3(Silent) with REAL byref out
        # params. No path, no CloseDoc, no os.remove.
        ok = _try_save3(model, SILENT, "Save3(Silent)", path)
        if not ok:
            # If Silent alone did not write, try Silent|SaveReferenced.
            ok = _try_save3(model, SILENT | SAVE_REFERENCED,
                            "Save3(Silent|SaveReferenced)", path)

        # Confirm persistence: reopen and check the config survived.
        if ok:
            adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
            check("reopen copy", await adapter.open_model(path))
            cfgs = check("list configs", await adapter.list_configurations())
            persisted = "_repro_cfg" in cfgs
            log(f"reopened: configs={cfgs} -- _repro_cfg persisted={persisted}")
            return {"silent_save_works": str(ok), "persisted": str(persisted)}
        return {"silent_save_works": str(ok), "persisted": "n/a"}
    finally:
        adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
        for p in (COPY,):
            try:
                if p.exists():
                    p.unlink()
                    log(f"cleaned up {p.name}")
            except OSError as exc:
                log(f"could not remove {p.name}: {exc}")


if __name__ == "__main__":
    sys.exit(run_build(build))
