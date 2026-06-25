r"""Isolate WHAT dirties harmonic-analyzer.SLDASM.

Distinguishes three hypotheses for the dirty-on-open the user observed:

  (A) the on-disk file opens dirty by itself      -> build save is the bug
  (B) Pack-and-Go / GetPackAndGo dirties the doc  -> cut_release side effect
  (C) a config switch or rebuild dirties it        -> per-config save-state

Sequence (all via comtypes -- correct method dispatch, no late-binding ambiguity):
  1. CloseAllDocuments, OpenDoc6 (silent) -> read GetSaveFlag IMMEDIATELY  [A]
  2. GetPackAndGo (no save)               -> read GetSaveFlag again        [B]
  3. switch each config, back to Default  -> read GetSaveFlag after each   [C]

Run with the SW venv python:

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diagnostics\probe_clean_open.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402

import comtypes  # noqa: E402
import comtypes.client  # noqa: E402

SW_TYPELIB = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"
SW_TYPELIB_VER = (34, 0)
ASSEMBLY = r"C:\src\harmonic-analyzer\cad\out\sldasm\harmonic-analyzer.SLDASM"
SW_DOC_ASSEMBLY = 2
SW_OPEN_SILENT = 1


def flag(doc, tag):
    _telemetry.debug(f"[{tag}] GetSaveFlag (dirty?) = {bool(doc.GetSaveFlag())}")


def main() -> int:
    mod = comtypes.client.GetModule((comtypes.GUID(SW_TYPELIB), *SW_TYPELIB_VER))
    sw = comtypes.client.GetActiveObject("SldWorks.Application", interface=mod.ISldWorks)
    _telemetry.info(f"attached to SW revision {sw.RevisionNumber()}")

    sw.CloseAllDocuments(True)
    sw.OpenDoc6(ASSEMBLY, SW_DOC_ASSEMBLY, SW_OPEN_SILENT, "", 0, 0)
    doc = sw.IActiveDoc2
    _telemetry.info(
        f"opened; active config = {doc.ConfigurationManager.ActiveConfiguration.Name}")

    _telemetry.info("[A] immediately after silent open, before any other call:")
    flag(doc, "A:open")

    _telemetry.info("[B] after GetPackAndGo (no SavePackAndGo):")
    pg = doc.Extension.GetPackAndGo()
    _telemetry.debug(f"GetPackAndGo -> {'ok' if pg is not None else 'None'}")
    flag(doc, "B:getpackandgo")

    _telemetry.info("[C] switching configs:")
    for cfg in list(doc.GetConfigurationNames() or []):
        doc.ShowConfiguration2(cfg)
        _telemetry.debug(f"after ShowConfiguration2({cfg!r}):")
        flag(doc, f"C:{cfg}")
    doc.ShowConfiguration2("Default")
    flag(doc, "C:back-to-Default")
    return 0


if __name__ == "__main__":
    sys.exit(main())
