r"""Throwaway probe: select a named reference axis inside a part nested in a
subassembly (depth 2) via IComponent2.GetCorresponding(baseFeature).Select2 --
the depth-agnostic path (per SW docs: GetCorresponding maps ANY persistent-ID
object incl. IFeature; GetCorrespondingEntity is entity-only).

Proves the cam coupling can use named axes after all (no face walk -- the
cylinder-gear lobe-face walk measured 612 s/part, untenable x20).

  - rod Axis1 (channel-1/connecting-rod-N), rigid then flexible;
  - gear Axis3 (drive-train-1/cylinder-gear-N) -- the cam lobe axis, FAST.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_getcorresponding.py
"""

from __future__ import annotations

import asyncio

from solidworks_mcp.adapters.com_variant import null_callout

from _common import OUT_SLDASM, _flag, _read_member, log


def _features(model):
    feat = _read_member(model, "FirstFeature")
    for _ in range(100000):
        if not feat:
            break
        _flag(feat, "IFeature")
        yield feat
        feat = _read_member(feat, "GetNextFeature")


def _axis_feature(model, name):
    for feat in _features(model):
        if str(_read_member(feat, "GetTypeName2")) == "RefAxis" and \
                str(_read_member(feat, "Name")) == name:
            return feat
    return None


def _find_comp(adapter, doc, needle):
    for c in (adapter._attempt(lambda: doc.GetComponents(False), default=None) or []):
        _flag(c, "IComponent2")
        if needle in str(_read_member(c, "Name2")):
            return c
    return None


def _map_select(adapter, doc, comp, feat, mark, label):
    """comp.GetCorresponding(baseFeature) -> Select2(append, mark)."""
    adapter._attempt(lambda: doc.ClearSelection2(True))
    mapped = adapter._attempt(lambda: comp.GetCorresponding(feat), default=None)
    if mapped is None:
        log(f"    {label}: GetCorresponding -> None")
        return False
    _flag(mapped, "IFeature")
    ok = adapter._attempt(lambda: mapped.Select2(False, mark), default=False)
    nm = adapter._attempt(lambda: mapped.Name, default="?")
    log(f"    {label}: GetCorresponding -> {nm!r}  Select2(mark={mark})={bool(ok)}")
    return bool(ok)


async def main():
    from solidworks_mcp.adapters.base import (
        InsertComponentParameters,
        SetComponentSolvingParameters,
    )
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    print("Connecting ...", flush=True)
    await adapter.connect()

    await adapter.create_assembly()
    doc = adapter.currentModel
    _flag(doc, "IModelDoc2")
    log("created throwaway parent")

    # --- channel: rod Axis1, rigid then flexible ---
    ch = (OUT_SLDASM / "channel.SLDASM").resolve()
    res = await adapter.insert_component(
        InsertComponentParameters(file_path=str(ch), position=[0, 0, 0], rotation=[0, 0, 0])
    )
    sub = res.data["name"]
    log(f"inserted channel as {sub!r}")
    rod = _find_comp(adapter, doc, "connecting-rod-16")
    rname = str(_read_member(rod, "Name2"))
    rpart = adapter._attempt(lambda: rod.GetModelDoc2(), default=None)
    ax1 = _axis_feature(rpart, "Axis1") if rpart else None
    log(f"rod={rname!r} Axis1-feature={'found' if ax1 else 'MISSING'}")
    if ax1 is not None:
        _map_select(adapter, doc, rod, ax1, 1, "RIGID rod Axis1")
        await adapter.set_component_solving(
            SetComponentSolvingParameters(name=sub, solving="flexible")
        )
        adapter._attempt(lambda: doc.EditRebuild3())
        _map_select(adapter, doc, rod, ax1, 1, "FLEXIBLE rod Axis1")

    # --- drive-train: gear Axis3 (cam lobe), flexible ---
    dt = (OUT_SLDASM / "drive-train.SLDASM").resolve()
    res2 = await adapter.insert_component(
        InsertComponentParameters(file_path=str(dt), position=[0, 0, 0], rotation=[0, 0, 0])
    )
    if res2.is_success:
        dtsub = res2.data["name"]
        await adapter.set_component_solving(
            SetComponentSolvingParameters(name=dtsub, solving="flexible")
        )
        adapter._attempt(lambda: doc.EditRebuild3())
        gear = _find_comp(adapter, doc, "cylinder-gear-1")
        gname = str(_read_member(gear, "Name2")) if gear else "?"
        gpart = adapter._attempt(lambda: gear.GetModelDoc2(), default=None) if gear else None
        ax3 = _axis_feature(gpart, "Axis3") if gpart else None
        log(f"gear={gname!r} Axis3-feature={'found' if ax3 else 'MISSING'}")
        if ax3 is not None:
            import time as _t
            t0 = _t.time()
            _map_select(adapter, doc, gear, ax3, 2, "FLEXIBLE gear Axis3")
            log(f"    (gear Axis3 map+select took {_t.time()-t0:.2f}s -- no face walk)")

        # --- the real test: TWO entities selected, form a coincident mate ---
        if ax1 is not None and ax3 is not None:
            adapter._attempt(lambda: doc.ClearSelection2(True))
            m1 = adapter._attempt(lambda: rod.GetCorresponding(ax1), default=None)
            m3 = adapter._attempt(lambda: gear.GetCorresponding(ax3), default=None)
            if m1 and m3:
                _flag(m1, "IFeature"); _flag(m3, "IFeature")
                s1 = adapter._attempt(lambda: m1.Select2(False, 1), default=False)
                s3 = adapter._attempt(lambda: m3.Select2(True, 1), default=False)
                cnt = adapter._attempt(
                    lambda: doc.SelectionManager.GetSelectedObjectCount2(-1), default=0
                )
                log(f"    TWO-AXIS SELECT (rod Axis1 + gear Axis3, mark 1): "
                    f"rod={bool(s1)} gear={bool(s3)} count={cnt} "
                    f"-> {'READY for AddMate5' if cnt == 2 else 'NOT ready'}")

    await adapter.disconnect()
    print("Disconnected.", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
