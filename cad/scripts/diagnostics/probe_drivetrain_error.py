r"""Throwaway diagnostic: WHAT is erroring on drive-train (the red X)?

drive-train<1> shows a rebuild error (red circle-X) when inserted + flexible in
a parent. Is the error LATENT on disk (drive-train.SLDASM itself) or only
triggered by FLEXIBLE solving in a parent? GetWhatsWrong names the culprit
feature(s) + error code either way -- this is also the fail-fast gate to add to
the build scripts.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_drivetrain_error.py
"""

from __future__ import annotations

import asyncio

import _telemetry
from _common import OUT_SLDASM, _flag, _read_member, log


# swFeatureError_e (the ones we expect to see)
_ERR = {
    0: "swFeatureErrorNone",
    1: "swFeatureWarning",
    2: "swFeatureError_RebuildError",
    3: "swFeatureError_DanglingNoMembers",
    4: "swFeatureError_DanglingHasMembers",
    5: "swSketchError_OverDefined",
    6: "swSketchError_NoSolution",
}


def _whats_wrong(adapter, model):
    """[(feature_name, error_code, is_warning), ...] for everything erroring."""
    ext = _read_member(model, "Extension")
    res = adapter._attempt(lambda: ext.GetWhatsWrong(), default=None)
    if not res or not isinstance(res, (list, tuple)):
        return None
    # pywin32 returns (retval, Features, ErrorCodes, Warnings) for the 3 outs.
    payload = res[1:] if len(res) == 4 else res
    feats, errs, warns = (list(payload[0] or []), list(payload[1] or []),
                          list(payload[2] or []))
    out = []
    for i, f in enumerate(feats):
        name = "?"
        if f is not None:
            _flag(f, "IFeature")
            name = str(_read_member(f, "Name"))
        ec = int(errs[i]) if i < len(errs) else -1
        wn = bool(warns[i]) if i < len(warns) else False
        out.append((name, ec, wn))
    return out


def _report(adapter, model, label):
    log(f"--- WhatsWrong: {label} ---")
    ww = _whats_wrong(adapter, model)
    if ww is None:
        log("    GetWhatsWrong returned nothing (no errors, or call failed)")
        return
    if not ww:
        log("    clean (no features in What's Wrong)")
        return
    for name, ec, wn in ww:
        kind = "WARN" if wn else "ERROR"
        log(f"    [{kind}] {name!r} code={ec} ({_ERR.get(ec, '?')})")


async def main():
    from solidworks_mcp.adapters.base import (
        InsertComponentParameters,
        SetComponentSolvingParameters,
    )
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    dt = (OUT_SLDASM / "drive-train.SLDASM").resolve()
    log(f"drive-train.SLDASM = {dt} ({dt.stat().st_size} bytes)")

    adapter = PyWin32Adapter({})
    _telemetry.info("Connecting ...")
    await adapter.connect()

    # 1) STANDALONE: open drive-train.SLDASM directly, force rebuild, check.
    log("=== STANDALONE ===")
    await adapter.open_model(str(dt))
    sub = adapter.currentModel
    _flag(sub, "IModelDoc2")
    adapter._attempt(lambda: sub.ForceRebuild3(False))
    _report(adapter, sub, "drive-train.SLDASM standalone (after ForceRebuild3)")

    # 2) FLEXIBLE-IN-PARENT: fresh parent, insert, flex, rebuild, check both
    #    the parent and the sub doc.
    log("=== FLEXIBLE-IN-PARENT ===")
    await adapter.create_assembly()
    doc = adapter.currentModel
    _flag(doc, "IModelDoc2")
    res = await adapter.insert_component(
        InsertComponentParameters(file_path=str(dt), position=[0, 0, 0], rotation=[0, 0, 0])
    )
    name = res.data["name"]
    log(f"inserted as {name!r}")
    _report(adapter, doc, "parent (drive-train inserted, rigid)")
    flex = await adapter.set_component_solving(
        SetComponentSolvingParameters(name=name, solving="flexible")
    )
    log(f"set flexible: success={flex.is_success} error={flex.error}")
    adapter._attempt(lambda: doc.ForceRebuild3(False))
    _report(adapter, doc, "parent (drive-train FLEXIBLE, after ForceRebuild3)")

    await adapter.disconnect()
    _telemetry.info("Disconnected (docs left open).")


if __name__ == "__main__":
    asyncio.run(main())
