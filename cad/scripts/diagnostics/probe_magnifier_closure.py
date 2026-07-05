r"""Throwaway diagnostic: WHY does the magnifier park closure read status=6?

Replays the recorded park specs on a fresh magnifier.SLDASM (exactly what the
release preflight does), then dumps GetWhatsWrong (feature + swFeatureError_e
code + warning flag) and every component's GetConstrainedStatus -- ground truth
for which replayed driver conflicts (code 46/47) instead of theorizing.

    uv run python cad\scripts\diagnostics\probe_magnifier_closure.py
"""

from __future__ import annotations

import asyncio

import pythoncom
from win32com.client import VARIANT

import _telemetry
from _common import OUT_SLDASM, _flag, _flag_only, _read_member, log
from _assembly import load_park_specs, replay_park_specs

_ERR = {
    0: "None", 1: "Warning", 2: "RebuildError",
    46: "MateOverDefining", 47: "MateCannotBeSolved", 48: "MateEntitiesBroken",
}
_STATUS = {1: "unknown", 2: "UNDER", 3: "fully", 4: "OVER", 5: "no-solution",
           6: "INVALID-SOLUTION", 7: "autosolve-off"}


def _whats_wrong(adapter, model):
    ext = _read_member(model, "Extension")
    f_v = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)
    e_v = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)
    w_v = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)
    _flag_only(ext, "GetWhatsWrong")
    ok = adapter._attempt(lambda: ext.GetWhatsWrong(f_v, e_v, w_v), default=None)
    log(f"    (GetWhatsWrong returned {ok!r})")
    feats = list(f_v.value or [])
    errs = list(e_v.value or [])
    warns = list(w_v.value or [])
    out = []
    for i, f in enumerate(feats):
        name = "?"
        if f is not None:
            _flag(f, "IFeature")
            name = str(_read_member(f, "Name"))
        out.append((name, int(errs[i]) if i < len(errs) else -1,
                    bool(warns[i]) if i < len(warns) else False))
    return out


def _statuses(adapter, model):
    conf = _read_member(model, "ConfigurationManager")
    root = adapter._attempt(
        lambda: conf.ActiveConfiguration.GetRootComponent3(True), default=None)
    for c in adapter._attempt(lambda: root.GetChildren, default=None) or []:
        name = str(_read_member(c, "Name2"))
        if bool(_read_member(c, "IsFixed")):
            log(f"    {name}: fixed")
            continue
        _flag_only(c, "GetConstrainedStatus")
        st = int(adapter._attempt(lambda c=c: c.GetConstrainedStatus(), default=-1))
        log(f"    {name}: status {st} ({_STATUS.get(st, '?')})")


async def main():
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    _telemetry.info("Connecting ...")
    await adapter.connect()

    path = (OUT_SLDASM / "magnifier.SLDASM").resolve()
    await adapter.open_model(str(path))
    model = adapter.currentModel
    _flag(model, "IModelDoc2")

    log("=== BEFORE replay ===")
    for n, ec, wn in _whats_wrong(adapter, model):
        log(f"    [{'WARN' if wn else 'ERROR'}] {n!r} code={ec} ({_ERR.get(ec, ec)})")
    _statuses(adapter, model)

    specs = load_park_specs("magnifier")
    log(f"replaying {len(specs)} park spec(s) ...")
    names = await replay_park_specs(adapter, specs)
    log(f"replayed: {names}")

    log("=== AFTER replay ===")
    for n, ec, wn in _whats_wrong(adapter, model):
        log(f"    [{'WARN' if wn else 'ERROR'}] {n!r} code={ec} ({_ERR.get(ec, ec)})")
    _statuses(adapter, model)

    # Measure the ACTUAL pose values the drivers demand, from the live wire
    # transform: hub-end |z| (the swing distance) and angle(Front@hw, Right
    # plane) (the spin angle) -- compare against the recorded spec scalars.
    import math
    from _assembly import component_transform
    arr = component_transform(adapter, "lever-wire-1")
    zrow = arr[6:9]  # part z-axis image = Front@hw normal
    org_z = arr[11] * 1000.0
    log(f"=== MEASURED at pose: hub z={org_z:.4f} (spec 142.77); "
        f"angle(Front@hw, Right)={math.degrees(math.acos(min(1.0, abs(zrow[0])))):.4f} "
        f"(spec 89.828); zrow={[round(v, 5) for v in zrow]}")

    # Isolate: suppress each wire driver in turn and re-check.
    from solidworks_mcp.adapters.base import SuppressMateParameters
    for suppress_name in ("PARK_wire_spin", "PARK_wire_swing"):
        await adapter.suppress_mate(
            SuppressMateParameters(name=suppress_name, suppress=True))
        adapter._attempt(lambda: model.ForceRebuild3(False))
        log(f"=== with {suppress_name} SUPPRESSED ===")
        for n, ec, wn in _whats_wrong(adapter, model):
            log(f"    [{'WARN' if wn else 'ERROR'}] {n!r} code={ec} ({_ERR.get(ec, ec)})")
        _statuses(adapter, model)
        await adapter.suppress_mate(
            SuppressMateParameters(name=suppress_name, suppress=False))

    # Discard unsaved (the preflight idiom) so the artefact stays pristine.
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    await adapter.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
