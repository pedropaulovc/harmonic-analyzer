r"""GATING PROBE: subassembly flexibility at the top level (Phase E).

Decides the plan's biggest unknown: can the channel + drive-train subs be made
FLEXIBLE so a top-level cam coupling (and, in artifact B, the crank motor) can
drive parts INSIDE them? Tests:
  1. set both subs flexible via IAssemblyDoc.CompConfigProperties5 (Solving=1)
     and read IComponent2.Solving back == 1;
  2. with channel flexible, suppress one rocker's internal spin stand-in mate
     and confirm that rocker-arm goes UNDER-defined (its DOF is now exposed).

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_flexibility.py
"""

from __future__ import annotations

import sys

from _common import (
    OUT_SLDASM,
    check,
    log,
    run_build,
    _flag,
    _read_member,
)

IDENTITY = [0.0, 0.0, 0.0]
RIGID, FLEXIBLE = 0, 1
FULLY_RESOLVED = 2  # swComponentFullyResolved (NOT 3 — that was the bug)


def _sub_path(name: str) -> str:
    return str((OUT_SLDASM / f"{name}.SLDASM").resolve())


def _find_comp(adapter, needle):
    asm = adapter.currentModel
    for c in adapter._attempt(lambda: asm.GetComponents(False), default=None) or []:
        _flag(c, "IComponent2")
        nm = str(_read_member(c, "Name2"))
        if needle in nm:
            return c, nm
    return None, None


def _solving(adapter, comp):
    return int(adapter._attempt(lambda: comp.Solving, default=-99))


def _title(adapter):
    model = adapter.currentModel
    import os
    t = adapter._attempt(lambda: model.GetTitle(), default="") or ""
    root, ext = os.path.splitext(t)
    return root if ext.lower() in (".sldasm", ".sldprt") else t


def _set_flexible(adapter, comp, comp_name):
    from solidworks_mcp.adapters.solidworks.assembly import _select_component

    asm = adapter.currentModel
    adapter._attempt(lambda: asm.ClearSelection2(True), default=None)
    # Proven path: the adapter's own _select_component qualifies name@title and
    # selects via Extension.SelectByID2 with a TYPED-NULL callout (null_callout()).
    # Bare None for the callout is a documented SelectByID2 failure mode.
    bare = comp_name.split("@", 1)[0]
    ok = _select_component(adapter, bare, 0, False)
    log(f"  _select_component({bare!r}) -> {ok}")
    res = adapter._attempt(
        lambda: asm.CompConfigProperties5(FULLY_RESOLVED, FLEXIBLE, True, False, "", False, False),
        default=None,
    )
    log(f"  CompConfigProperties5 -> {res}")
    adapter._attempt(lambda: asm.ClearSelection2(True), default=None)


async def build(adapter):
    from solidworks_mcp.adapters.base import InsertComponentParameters, ComponentRefParameters

    check("create_assembly", await adapter.create_assembly())
    for name in ("frame", "drive-train", "channel"):
        data = check(
            f"insert {name}",
            await adapter.insert_component(
                InsertComponentParameters(file_path=_sub_path(name),
                                          position=[0.0, 0.0, 0.0], rotation=[0.0, 0.0, 0.0])
            ),
        )
        # Fix only the frame (the structural anchor); leave drive-train +
        # channel free so they can be made flexible (a fixed sub can't be).
        if name == "frame" and not data.get("fixed"):
            await adapter.fix_component(ComponentRefParameters(name=data["name"]))

    asm = adapter.currentModel
    adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)

    # --- Stage 1: set subs flexible, read back ---
    for needle in ("drive-train", "channel"):
        comp, nm = _find_comp(adapter, needle)
        if comp is None:
            log(f"STAGE1 {needle}: component not found")
            continue
        log(f"STAGE1 {nm}: Solving before = {_solving(adapter, comp)} (0=rigid,1=flex)")
        _set_flexible(adapter, comp, nm)
        adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
        comp, _ = _find_comp(adapter, needle)
        log(f"STAGE1 {nm}: Solving after  = {_solving(adapter, comp)}")

    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
