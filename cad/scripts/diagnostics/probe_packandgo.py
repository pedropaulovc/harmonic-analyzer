r"""Probe (round 3): GetPackAndGo returns null for a reference-less part?

Round 2 finding: InvokeTypes with a declared [out] arg + pythoncom.Missing
SUCCEEDS (no COM error) but returns None on a-frame.SLDPRT. Hypothesis:
GetPackAndGo returns a null IPackAndGo when the document has no external
references (a standalone part), and works on the referencing ASSEMBLY. Test
the same call on the assembly (184 refs) vs the part to confirm, and report
GetDocumentNamesCount for the assembly.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diagnostics\probe_packandgo.py

LATE-BOUND PROBE: this script drives SolidWorks through its own
``GetObject``/``Dispatch`` (or a raw ``adapter.currentModel``), NOT the makepy
wrapper, so its ``[out]`` params land in the ``VT_BYREF`` VARIANTs passed in
rather than in the return tuple. That is the OPPOSITE of the build path, where
``_common._early_bound`` guarantees an early-bound object and the outs ride the
return tuple. Both are correct for their binding -- mixing them is the trap that
reads as "no data" instead of failing. See memory/sw-assembly-mate-diagnostics-api.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # for _common

from _common import OUT_SLDASM, OUT_SLDPRT, check, log, run_build  # noqa: E402

ASSEMBLY = OUT_SLDASM / "harmonic-analyzer.SLDASM"
PART = OUT_SLDPRT / "a-frame.SLDPRT"


def _probe_doc(adapter, label):  # noqa: ANN001
    import pythoncom
    import win32com.client

    model = adapter.currentModel
    ext_oleobj = model.Extension._oleobj_
    byref = pythoncom.VT_BYREF | pythoncom.VT_DISPATCH

    # retType VOID + one [out] VT_BYREF|VT_DISPATCH arg, placeholder Missing:
    # pywin32 returns the [out] value as the call result.
    raw = ext_oleobj.InvokeTypes(207, 0, pythoncom.DISPATCH_METHOD, (pythoncom.VT_VOID, 0),
                                 ((byref, 2),), pythoncom.Missing)
    if raw is None:
        log(f"[{label}] GetPackAndGo -> None (no PackAndGo object)")
        return
    pg = win32com.client.Dispatch(raw)
    try:
        cnt = pg.GetDocumentNamesCount()
        log(f"[{label}] GetPackAndGo -> OK IPackAndGo, GetDocumentNamesCount={cnt}")
    except Exception as exc:  # noqa: BLE001
        log(f"[{label}] GetPackAndGo -> object {type(raw).__name__} but count failed: {exc!r}")


async def build(adapter):  # noqa: ANN001
    check("open part", await adapter.open_model(str(PART)))
    _probe_doc(adapter, "PART a-frame (no refs)")

    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    check("open assembly", await adapter.open_model(str(ASSEMBLY)))
    _probe_doc(adapter, "ASSEMBLY harmonic-analyzer (184 refs)")
    return {"probe": "done -- see log"}


if __name__ == "__main__":
    sys.exit(run_build(build))
