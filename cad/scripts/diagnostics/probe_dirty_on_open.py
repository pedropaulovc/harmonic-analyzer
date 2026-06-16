r"""Probe: why does harmonic-analyzer.SLDASM open dirty + pending rebuild?

Attaches READ-ONLY to the already-running SolidWorks and inspects the ACTIVE
document in place (does NOT CloseAllDocuments -- we want the exact state the user
is looking at). Reports, for the top assembly and every top-level child:

  * GetSaveFlag (True => doc is dirty / needs save)
  * What's Wrong entries (feature/mate rebuild errors or warnings)

Uses sw_type_info to flag pywin32 zero-arg methods so they dispatch as methods,
not properties (GetTitle/GetSaveFlag/etc. otherwise mis-resolve under late
binding).

Run with the SW venv python while the dirty assembly is open:

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diagnostics\probe_dirty_on_open.py
"""

from __future__ import annotations

import sys

import pythoncom
import win32com.client
from win32com.client import VARIANT

from solidworks_mcp.adapters import sw_type_info

_FEATURE_ERROR = {
    0: "none", 1: "warning", 2: "rebuild-error", 3: "dangling-no-members",
    4: "dangling-has-members", 5: "sketch-overdefined", 6: "sketch-nosolution",
    7: "sketch-overdefined-dangling",
}


def _byref():
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)


def whats_wrong(model):
    ext = sw_type_info.flagged(model.Extension, "IModelDocExtension")
    f, e, w = _byref(), _byref(), _byref()
    try:
        ext.GetWhatsWrong(f, e, w)
    except Exception as exc:  # noqa: BLE001
        return [("<GetWhatsWrong failed>", -1, repr(exc), False)]
    feats = list(f.value or [])
    codes = list(e.value or [])
    warns = list(w.value or [])
    out = []
    for i, feat in enumerate(feats):
        name = "?"
        if feat is not None:
            ff = sw_type_info.flagged(feat, "IFeature")
            try:
                name = str(ff.Name)
            except Exception:  # noqa: BLE001
                name = "<no Name>"
        code = int(codes[i]) if i < len(codes) else -1
        warn = bool(warns[i]) if i < len(warns) else False
        out.append((name, code, _FEATURE_ERROR.get(code, code), warn))
    return out


def report(label, model):
    model = sw_type_info.flagged(model, "IModelDoc2")
    try:
        dirty = bool(model.GetSaveFlag())
    except Exception as exc:  # noqa: BLE001
        dirty = f"<GetSaveFlag failed: {exc!r}>"
    print(f"\n=== {label} ===", flush=True)
    print(f"  GetSaveFlag (dirty?) = {dirty}", flush=True)
    ww = whats_wrong(model)
    if not ww:
        print("  What's Wrong: clean", flush=True)
    for entry in ww:
        print(f"  What's Wrong: {entry}", flush=True)


def main() -> int:
    sw = win32com.client.GetActiveObject("SldWorks.Application")
    print(f"attached to SW revision {sw.RevisionNumber()}", flush=True)

    doc = sw.ActiveDoc
    if doc is None:
        print("!! no active document -- open harmonic-analyzer.SLDASM first", flush=True)
        return 2
    doc = sw_type_info.flagged(doc, "IModelDoc2")
    title = doc.GetTitle()
    print(f"active doc: {title}", flush=True)
    cfg_names = list(doc.GetConfigurationNames() or [])
    print(f"configurations: {cfg_names}", flush=True)

    report(f"TOP {title}", doc)

    # Per top-level child: its own document's dirty + What's Wrong.
    comps = doc.GetComponents(False) or []
    seen = set()
    for comp in comps:
        comp = sw_type_info.flagged(comp, "IComponent2")
        name = str(comp.Name2)
        if "/" in name:  # top-level only
            continue
        try:
            sub = comp.GetModelDoc2()
        except Exception:  # noqa: BLE001
            sub = None
        if sub is None or id(sub) in seen:
            continue
        seen.add(id(sub))
        report(f"CHILD {name}", sub)

    return 0


if __name__ == "__main__":
    sys.exit(main())
