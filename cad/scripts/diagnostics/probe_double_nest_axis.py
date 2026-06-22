r"""Throwaway probe: does a named reference axis inside a part nested in a
subassembly select by name via SelectByID2 -- RIGID vs FLEXIBLE?

The cam couplings + crank motor in build_motion_study all failed with
"Failed to select mate entity (AXIS at 'Axis1@connecting-rod-1@channel-1@
harmonic-analyzer')". The 1-channel rig that "proved" the named-axis recipe
placed parts DIRECTLY (single nesting), so it never exercised part-in-sub-in-top.

This builds a CLEAN throwaway parent (create_assembly makes a NEW doc, leaving
the user's harmonic-analyzer session open and untouched -> model tab active, no
motion study to block selection), inserts channel.SLDASM as channel-1 (genuine
`connecting-rod-1@channel-1@<parent>` double nesting, identical structure to the
failing case), then:

  1. enumerates the rod's RefAxis features by name (confirm Axis1/Axis2 exist);
  2. tries several SelectByID2 name formats for one nested axis while the sub is
     RIGID;
  3. set_component_solving(FLEXIBLE) + rebuild, then RE-tries every format --
     the leading hypothesis is that, like cylindrical faces, named axes fail to
     select through a FLEXIBLE sub.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_double_nest_axis.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from solidworks_mcp.adapters.com_variant import null_callout

import _telemetry
from _common import OUT_SLDASM, _flag, _read_member, log


def _features(model):
    feat = _read_member(model, "FirstFeature")
    for _ in range(100000):
        if not feat:
            break
        _flag(feat, "IFeature")
        yield feat
        feat = _read_member(feat, "GetNextFeature")


def _axis_features(part):
    out = []
    for feat in _features(part):
        if str(_read_member(feat, "GetTypeName2")) == "RefAxis":
            out.append((str(_read_member(feat, "Name")), feat))
    return out


def _find_comp(adapter, doc, needle):
    for c in (adapter._attempt(lambda: doc.GetComponents(False), default=None) or []):
        _flag(c, "IComponent2")
        if needle in str(_read_member(c, "Name2")):
            return c
    return None


def _try_select(adapter, doc, name, etype="AXIS"):
    adapter._attempt(lambda: doc.ClearSelection2(True))
    ok = adapter._attempt(
        lambda: doc.Extension.SelectByID2(
            name, etype, 0.0, 0.0, 0.0, False, 0, null_callout(), 0
        ),
        default=False,
    )
    return bool(ok)


def _run_format_tests(adapter, doc, leaf, sub, asm, ax, phase):
    log(f"--- {phase}: axis {ax!r} on {sub}/{leaf} ---")
    candidates = [
        f"{ax}@{leaf}@{sub}@{asm}",   # current (failing in the full asm)
        f"{ax}@{leaf}@{asm}",          # skip the sub level
        f"{ax}@{leaf}@{sub}",          # no top doc
        f"{ax}@{sub}/{leaf}@{asm}",    # slash component path
        f"{ax}@{leaf}",                # leaf only
    ]
    for nm in candidates:
        log(f"    SelectByID2 {nm!r} -> {_try_select(adapter, doc, nm)}")


async def main():
    from solidworks_mcp.adapters.base import (
        InsertComponentParameters,
        SetComponentSolvingParameters,
    )
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    ch_path = (OUT_SLDASM / "channel.SLDASM").resolve()
    if not ch_path.exists():
        log(f"missing {ch_path}")
        return
    log(f"channel.SLDASM = {ch_path} ({ch_path.stat().st_size} bytes)")

    adapter = PyWin32Adapter({})
    _telemetry.info("Connecting ...")
    await adapter.connect()

    # NEW empty assembly (does not touch the user's open harmonic-analyzer doc).
    log("create_assembly (fresh throwaway parent) ...")
    await adapter.create_assembly()
    doc = adapter.currentModel
    _flag(doc, "IModelDoc2")
    title = str(_read_member(doc, "GetTitle"))
    asm = title[:-7] if title.lower().endswith(".sldasm") else title
    log(f"parent title={title!r} asm={asm!r}")

    log("insert channel.SLDASM as channel-1 ...")
    res = await adapter.insert_component(
        InsertComponentParameters(
            file_path=str(ch_path), position=[0.0, 0.0, 0.0], rotation=[0.0, 0.0, 0.0]
        )
    )
    if not res.is_success:
        log(f"insert failed: {res.error}")
        await adapter.disconnect()
        return
    data = res.data
    sub = data["name"]
    log(f"  inserted as {sub!r} (fixed={data.get('fixed')})")

    comp = _find_comp(adapter, doc, "connecting-rod-1")
    if comp is None:
        log("connecting-rod-1 NOT FOUND under the inserted sub")
        await adapter.disconnect()
        return
    full = str(_read_member(comp, "Name2"))
    log(f"rod component Name2={full!r}")
    leaf = full.split("/")[-1]
    part = adapter._attempt(lambda: comp.GetModelDoc2(), default=None)
    axes = _axis_features(part) if part is not None else []
    log(f"rod axis features: {[a for a, _f in axes]}")
    if not axes:
        log("no axes -- abort")
        await adapter.disconnect()
        return
    ax = axes[0][0]

    # Calibration: planes (known-good single/double-nested in prior runs).
    log("=== calibration (PLANE) ===")
    for nm in ("Front Plane", f"Front Plane@{sub}@{asm}", f"Front Plane@{leaf}@{sub}@{asm}"):
        log(f"    SelectByID2 {nm!r} (PLANE) -> {_try_select(adapter, doc, nm, 'PLANE')}")

    # 1) RIGID (as inserted).
    _run_format_tests(adapter, doc, leaf, sub, asm, ax, "RIGID")

    # 2) FLEXIBLE.
    log(f"set_component_solving({sub}, flexible) + rebuild ...")
    flex = await adapter.set_component_solving(
        SetComponentSolvingParameters(name=sub, solving="flexible")
    )
    log(f"  flexible result: success={flex.is_success} error={flex.error}")
    adapter._attempt(lambda: doc.EditRebuild3())
    _run_format_tests(adapter, doc, leaf, sub, asm, ax, "FLEXIBLE")

    # 3) THE REAL PATH: cylindrical FACE via GetCorrespondingEntity, two levels
    #    deep, flexible. This is what the adapter's motor/mate code uses. Confirm
    #    it returns a usable entity (axes can't be mapped; faces can).
    from solidworks_mcp.adapters.solidworks.assembly import _component_cylindrical_face

    log("--- FLEXIBLE: cylindrical FACE via GetCorrespondingEntity ---")
    ent = _component_cylindrical_face(adapter, full, None)
    log(f"    _component_cylindrical_face({full!r}) -> {ent!r}")
    if ent is not None:
        _flag(ent, "IEntity")
        adapter._attempt(lambda: doc.ClearSelection2(True))
        ok = adapter._attempt(lambda: ent.Select4(False, null_callout()), default=False)
        et = adapter._attempt(lambda: ent.GetType(), default=None)
        log(f"    .GetType()={et}  Select4(in-context)={bool(ok)}")

    # 4) Face-walk COST on the cylinder-gear (the perf blocker the named axis was
    #    meant to dodge). Insert drive-train, time finding a gear's lobe face.
    log("insert drive-train.SLDASM (to time the cylinder-gear face walk) ...")
    dt_path = (OUT_SLDASM / "drive-train.SLDASM").resolve()
    if dt_path.exists():
        res2 = await adapter.insert_component(
            InsertComponentParameters(
                file_path=str(dt_path), position=[0.0, 0.0, 0.0], rotation=[0.0, 0.0, 0.0]
            )
        )
        if res2.is_success:
            dtsub = res2.data["name"]
            gear = _find_comp(adapter, doc, "cylinder-gear-1")
            if gear is not None:
                gname = str(_read_member(gear, "Name2"))
                gpart = adapter._attempt(lambda: gear.GetModelDoc2(), default=None)
                bodies = adapter._attempt(
                    lambda: gpart.GetBodies2(0, False), default=None
                ) if gpart else None
                nb = len(bodies) if isinstance(bodies, (list, tuple)) else (1 if bodies else 0)
                log(f"    gear={gname!r} bodies={nb}")
                import time as _t
                t0 = _t.time()
                gent = _component_cylindrical_face(adapter, gname, [0.0, 600.0, 0.0])
                log(f"    cylinder-gear lobe face walk: {_t.time()-t0:.1f}s -> {gent!r}")
        else:
            log(f"    drive-train insert failed: {res2.error}")

    await adapter.disconnect()
    _telemetry.info("Disconnected (throwaway parent left open, unsaved).")


if __name__ == "__main__":
    asyncio.run(main())
