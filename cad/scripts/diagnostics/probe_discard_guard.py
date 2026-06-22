r"""Validate cut_release._discard_open_documents closes a dirty session silently.

Reproduces the exact condition that popped the "Save Modified Documents" modal:
an open top assembly whose flexible drive-train child is dirty (from activating
the operating/pinion_engaged config). The guard must close it WITHOUT a prompt --
proven by the script running to completion (a modal would hang it).

Tests twice: (1) whatever dirty session is currently open (the last probe left
the top + a dirty child open), (2) a freshly-created dirty session.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diagnostics\probe_discard_guard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # for cut_release

import comtypes
import comtypes.client

import _telemetry
from cut_release import SW_TYPELIB, SW_TYPELIB_VER, _discard_open_documents

ASSEMBLY = r"C:\src\harmonic-analyzer\cad\out\sldasm\harmonic-analyzer.SLDASM"
SW_DOC_ASSEMBLY = 2
SW_OPEN_SILENT = 1


def main() -> int:
    mod = comtypes.client.GetModule((comtypes.GUID(SW_TYPELIB), *SW_TYPELIB_VER))
    sw = comtypes.client.GetActiveObject("SldWorks.Application", interface=mod.ISldWorks)
    _telemetry.info(f"attached to SW revision {sw.RevisionNumber()}")

    # (1) Whatever is currently open -- the prior probe left a dirty child session.
    cur = sw.IActiveDoc2
    _telemetry.info(f"[1] currently active doc: "
                    f"{cur.GetTitle() if cur is not None else None}")
    _discard_open_documents(sw)
    if sw.IActiveDoc2 is not None:
        _telemetry.warn("[1] a doc is still active after discard")
        return 2
    _telemetry.success("[1] live dirty session closed silently (no modal)")

    # (2) Freshly create the exact failure state: open top, activate the flexible
    # operating config -> dirties the drive-train child, then discard.
    sw.OpenDoc6(ASSEMBLY, SW_DOC_ASSEMBLY, SW_OPEN_SILENT, "", 0, 0)
    doc = sw.IActiveDoc2
    doc.ShowConfiguration2("operating")
    _telemetry.info(f"[2] opened top, activated 'operating'; dirty="
                    f"{bool(doc.GetSaveFlag())}")
    _discard_open_documents(sw)
    if sw.IActiveDoc2 is not None:
        _telemetry.warn("[2] a doc is still active after discard")
        return 3
    _telemetry.success("[2] freshly-dirtied session closed silently (no modal)")

    _telemetry.success("guard validated -- no Save Modified Documents prompt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
