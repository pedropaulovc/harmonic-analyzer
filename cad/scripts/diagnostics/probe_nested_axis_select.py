r"""Throwaway probe: find the SelectByID2 name that selects a named reference
axis inside a part nested in a (flexible) subassembly.

ATTACHES to the already-open harmonic-analyzer session (does NOT CloseAllDocuments
or reopen -- the 22 min reload is the whole thing we are avoiding). The failed
build_motion_study run left the assembly open with the 3 subs flexible; the cam
couplings + crank motor all failed with "Failed to select mate entity
(AXIS at 'Axis1@connecting-rod-1@channel-1@harmonic-analyzer')". This probe:

  1. confirms the rod/crankshaft parts actually carry Axis1/Axis2 (enumerate the
     part doc's reference-axis features by name);
  2. tries several SelectByID2 name formats for one nested axis and reports which
     (if any) returns True;
  3. tries the GetCorrespondingEntity -> Select4 path as a fallback.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_nested_axis_select.py
"""

from __future__ import annotations

import asyncio

import _telemetry
from _common import _flag, _read_member, log


def _features(adapter, model):
    feat = _read_member(model, "FirstFeature")
    for _ in range(100000):
        if not feat:
            break
        _flag(feat, "IFeature")
        yield feat
        feat = _read_member(feat, "GetNextFeature")


def _axis_features(adapter, part):
    out = []
    for feat in _features(adapter, part):
        tn = str(_read_member(feat, "GetTypeName2"))
        if tn == "RefAxis":
            out.append((str(_read_member(feat, "Name")), feat))
    return out


def _find_comp(adapter, doc, name2):
    for c in (adapter._attempt(lambda: doc.GetComponents(False), default=None) or []):
        _flag(c, "IComponent2")
        if str(_read_member(c, "Name2")) == name2:
            return c
    return None


def _try_select(adapter, doc, name, etype="AXIS"):
    adapter._attempt(lambda: doc.ClearSelection2(True))
    ok = adapter._attempt(
        lambda: doc.Extension.SelectByID2(name, etype, 0.0, 0.0, 0.0, False, 0, None, 0),
        default=False,
    )
    return bool(ok)


async def main():
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    _telemetry.info("Connecting (ATTACH, no close) ...")
    await adapter.connect()

    doc = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=None)
    if doc is None:
        log("no ActiveDoc -- the assembly is not open")
        return
    _flag(doc, "IModelDoc2")
    adapter.currentModel = doc
    title = str(_read_member(doc, "GetTitle"))
    asm = title[:-7] if title.lower().endswith(".sldasm") else title
    log(f"active doc title={title!r} asm={asm!r}")

    # Calibration: does SelectByID2 resolve at all in this (motion-tab) session?
    # Top-level + single-nested PLANE are known-good (the run's grounding mates
    # used 'Front Plane@channel-1@...' successfully). If these are False the
    # Motion tab is blocking selection and the whole probe is confounded.
    log("--- calibration selections ---")
    for nm, et in (
        ("Front Plane", "PLANE"),
        (f"Front Plane@channel-1@{asm}", "PLANE"),
        (f"Front Plane@connecting-rod-1@channel-1@{asm}", "PLANE"),
    ):
        log(f"    SelectByID2 {nm!r} ({et}) -> {_try_select(adapter, doc, nm, et)}")

    for path in ("channel-1/connecting-rod-1", "drive-train-1/crankshaft-1"):
        comp = _find_comp(adapter, doc, path)
        if comp is None:
            log(f"  component NOT FOUND: {path}")
            continue
        leaf = path.split("/")[-1]
        sub = path.split("/")[0]
        part = adapter._attempt(lambda c=comp: c.GetModelDoc2(), default=None)
        axes = _axis_features(adapter, part) if part is not None else []
        log(f"\n=== {path} -> axis features: {[a for a, _f in axes]}")

        # B: name-format candidates for the first axis.
        if axes:
            ax = axes[0][0]
            candidates = [
                f"{ax}@{leaf}@{sub}@{asm}",   # current (failing)
                f"{ax}@{leaf}@{asm}",          # skip the sub level
                f"{ax}@{leaf}@{sub}",          # no top doc
                f"{ax}@{sub}/{leaf}@{asm}",    # slash component path
            ]
            for nm in candidates:
                log(f"    SelectByID2 {nm!r} -> {_try_select(adapter, doc, nm)}")

        # C: GetCorrespondingEntity -> Select4 fallback.
        if axes and part is not None:
            feat = axes[0][1]
            refax = adapter._attempt(lambda f=feat: f.GetSpecificFeature2(), default=None)
            ent = adapter._attempt(lambda c=comp, r=refax: c.GetCorrespondingEntity(r),
                                   default=None)
            if ent is not None:
                _flag(ent, "IEntity")
                adapter._attempt(lambda: doc.ClearSelection2(True))
                ok = adapter._attempt(lambda e=ent: e.Select4(False, None), default=False)
                log(f"    GetCorrespondingEntity(refax).Select4 -> {bool(ok)}")
            else:
                log("    GetCorrespondingEntity returned None")

    await adapter.disconnect()
    _telemetry.info("Disconnected (assembly left open).")


if __name__ == "__main__":
    asyncio.run(main())
