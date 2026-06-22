r"""Probe: SolidWorks Pack-and-Go via comtypes (pywin32 can't retrieve IPackAndGo).

pywin32/win32com mishandles GetPackAndGo's [out,retval] IPackAndGo** param
(returns null across every invocation style -- pywin32 issues #1303/#622).
comtypes generates real [out,retval] handling from the typelib, so
ext.GetPackAndGo() should just return the object. This proves the FULL path
end-to-end: attach to the running SW, open the assembly, GetPackAndGo, set
options, SavePackAndGo to a test zip, and confirm the zip exists non-empty.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diagnostics\probe_packandgo_comtypes.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402

import comtypes  # noqa: E402
import comtypes.client  # noqa: E402

SW_TYPELIB = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"  # SldWorks type library
SW_TYPELIB_VER = (34, 0)  # matches the pywin32 gen_py module ...x0x34x0
ASSEMBLY = r"C:\src\harmonic-analyzer\cad\out\sldasm\harmonic-analyzer.SLDASM"
TEST_ZIP = r"C:\src\harmonic-analyzer\cad\out\release\_probe_packandgo.zip"

SW_DOC_ASSEMBLY = 2
SW_OPEN_SILENT = 1


def main() -> int:
    mod = comtypes.client.GetModule((comtypes.GUID(SW_TYPELIB), *SW_TYPELIB_VER))
    sw = comtypes.client.GetActiveObject("SldWorks.Application", interface=mod.ISldWorks)
    _telemetry.info(f"attached to SW; revision {sw.RevisionNumber()}")

    sw.CloseAllDocuments(True)
    res = sw.OpenDoc6(ASSEMBLY, SW_DOC_ASSEMBLY, SW_OPEN_SILENT, "", 0, 0)
    _telemetry.debug(f"OpenDoc6 returned {type(res).__name__}")

    doc = sw.IActiveDoc2
    ext = doc.Extension
    _telemetry.debug(f"ext = {ext!r}")

    pg = ext.GetPackAndGo()
    _telemetry.debug(f"GetPackAndGo -> {pg!r}")
    if pg is None:
        _telemetry.warn("comtypes ALSO returned None")
        return 2

    count = pg.GetDocumentNamesCount()
    _telemetry.info(f"GetDocumentNamesCount = {count}")

    pg.IncludeDrawings = False
    pg.IncludeSimulationResults = False
    pg.IncludeToolboxComponents = False
    pg.IncludeSuppressed = True
    pg.FlattenToSingleFolder = True
    ok = pg.SetSaveToName2(True, TEST_ZIP)
    _telemetry.debug(f"SetSaveToName2 -> {ok}")

    Path(TEST_ZIP).parent.mkdir(parents=True, exist_ok=True)
    if Path(TEST_ZIP).exists():
        Path(TEST_ZIP).unlink()
    statuses = ext.SavePackAndGo(pg)
    _telemetry.debug(f"SavePackAndGo statuses = {statuses}")

    zp = Path(TEST_ZIP)
    if zp.exists() and zp.stat().st_size > 0:
        _telemetry.success(f"zip written: {zp} ({zp.stat().st_size/1e6:.1f} MB)")
        return 0
    _telemetry.warn("no zip produced")
    return 3


if __name__ == "__main__":
    sys.exit(main())
