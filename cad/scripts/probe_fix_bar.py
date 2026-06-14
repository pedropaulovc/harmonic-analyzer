r"""FAST diagnostic: which way actually FIXES a part nested in a flexible sub?

_freeze_bars must pin each amplitude bar rigidly (it is a coefficient setting,
decoupled from the geared lever) so it does not flop. fix_component keeps
returning 0/20 -- FixComponent acts on the ACTIVE doc's selection and the
flexible sub's in-context doc may not be activatable. Rather than re-run the
full ~5 min gear probe each guess, flex channel-1 ONCE and try three fix paths
on a SINGLE bar, logging the real exception + IsFixed readback for each:

  (a) top-level   : currentModel=top,    name="channel-1/amplitude-bar-1"
  (b) in-sub      : currentModel=ch_doc, name="amplitude-bar-1" (no activate)
  (c) activate-sub: ActivateDoc3(ch) then name="amplitude-bar-1"

The first that yields IsFixed=True is the one _freeze_bars should use.

  C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_fix_bar.py

NEVER saves.
"""

from __future__ import annotations

import asyncio

from _common import _read_member, coincident_mate, log, named_ref
from build_motion_study import OUT_SLDASM, _find_family, _sub_model
from solidworks_mcp.adapters.solidworks.assembly import _byref_i4


async def _try_fix(adapter, model, name, tag):
    from solidworks_mcp.adapters.base import ComponentRefParameters
    adapter.currentModel = model
    res = await adapter.fix_component(ComponentRefParameters(name=name))
    ok = getattr(res, "is_success", False)
    err = getattr(res, "error", None)
    data = res.data if ok else None
    log(f"  [{tag}] name={name!r} is_success={ok} err={err!r} data={data}")
    return bool(data and data.get("fixed"))


async def main():
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters, SetComponentSolvingParameters,
    )
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    print("Connecting ...", flush=True)
    await adapter.connect()
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    asm_path = str((OUT_SLDASM / "harmonic-analyzer.SLDASM").resolve())
    await adapter.open_model(asm_path)
    top = adapter.currentModel
    top_title = str(_read_member(top, "GetTitle"))
    log(f"opened {asm_path} (title={top_title!r})")

    # flex channel-1
    await adapter.float_component(ComponentRefParameters(name="channel-1"))
    for plane in ("Front Plane", "Top Plane", "Right Plane"):
        await coincident_mate(
            adapter, named_ref(f"{plane}@channel-1", "PLANE"),
            named_ref(plane, "PLANE"), label=f"ground channel-1 {plane}")
    adapter._attempt(lambda: top.ForceRebuild3(False), default=None)
    log("  set channel-1 FLEXIBLE (blocking solve) ...")
    await adapter.set_component_solving(
        SetComponentSolvingParameters(name="channel-1", solving="flexible"))
    adapter._attempt(lambda: top.ForceRebuild3(False), default=None)

    _, ch_doc = _sub_model(adapter, "channel-1")
    ch_title = str(_read_member(ch_doc, "GetTitle"))
    log(f"  channel sub doc title={ch_title!r}")

    # (a) top-level path
    await _try_fix(adapter, top, "channel-1/amplitude-bar-1", "a:top-level")

    # (b) in-sub, no activate
    await _try_fix(adapter, ch_doc, "amplitude-bar-1", "b:in-sub-noact")

    # (c) activate sub doc, then fix by name
    act = adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(ch_title, False, 2, _byref_i4()), default=None)
    active = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=None)
    active_title = str(_read_member(active, "GetTitle")) if active else None
    log(f"  ActivateDoc3({ch_title!r}) -> ret={act!r} active_title={active_title!r}")
    adapter.currentModel = active or ch_doc
    await _try_fix(adapter, adapter.currentModel, "amplitude-bar-1", "c:activate-sub")

    # (d) + (e): select the dispatch directly via IComponent2.Select4, then call
    # FixComponent on the sub doc (d) and the top doc (e). No name string.
    bars = _find_family(adapter, "amplitude-bar", model=ch_doc)
    bar_c = bars[0][0] if bars else None
    for tag, fix_model in (("d:select4+subfix", ch_doc), ("e:select4+topfix", top)):
        if bar_c is None:
            break
        adapter.currentModel = fix_model
        adapter._attempt(lambda: fix_model.ClearSelection2(True), default=None)
        sel = adapter._attempt(lambda: bar_c.Select4(False, None, False), default=None)
        adapter._attempt(lambda: fix_model.FixComponent(), default=None)
        isfix = bool(_read_member(bar_c, "IsFixed"))
        log(f"  [{tag}] Select4->{sel!r} after FixComponent IsFixed={isfix}")
        if isfix:
            adapter._attempt(lambda: fix_model.UnfixComponent(), default=None)

    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(top_title, False, 2, _byref_i4()), default=None)
    adapter.currentModel = top
    if bar_c is not None:
        log(f"  final amplitude-bar-1 IsFixed={bool(_read_member(bar_c, 'IsFixed'))}")

    await adapter.disconnect()
    print("Disconnected (NOT saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
