"""Dump the Hole Wizard database tables (ANSI Inch) -- the DEFINITIVE size
tokens + hole diameters for the Hole Wizard conversion.

The first geometry probe (diag_hole_wizard.py) showed size tokens like
``"#47"`` (number drill) and ``"#8"`` (screw clearance) cutting the WRONG
diameters, so the tokens are enumerated straight from the wizard database via
``ISldWorks::GetHoleStandardsData`` instead of guessed. Late-bound ByRef
variant out-params are passed as explicit VT_BYREF VARIANTs.

Prints a machine-readable table dump to stdout (the dump IS the output; the
diag_cwm print exemption applies).

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/diag_hole_wizard_tables.py

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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # cad/scripts

from _common import run_build  # noqa: E402

# (hole type swWzdGeneralHoleTypes_e, fastener IDs of interest)
WANT = [
    (4, {26: "bottoming tap", 27: "tapped hole"}),
    (2, {18: "all drills", 19: "fractional drills", 22: "screw clearances",
         24: "number drills", 703: "dowel"}),
    (0, {0: "binding cbore", 2: "fillister cbore", 3: "hex bolt cbore",
         8: "pan cbore", 9: "socket cap cbore"}),
]


def _byref():
    import pythoncom
    from win32com.client import VARIANT
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)


def _tolist(v):
    val = getattr(v, "value", v)
    if val is None:
        return []
    return list(val)


def _early(obj, iface: str):
    """Wrap a raw dispatch in the gen_py early-bound class for ``iface``.

    ``CastTo`` fails here ('Invalid index': the raw dispatch's GetTypeInfo is
    not resolvable), so the wrapper class is taken straight from the already-
    loaded sldworks gen_py module. Early binding makes the interface's [out]
    params come back as result tuples -- the late-bound byref VARIANTs
    mis-marshal on GetFastenerTable.
    """
    from solidworks_mcp.adapters import sw_type_info

    sw_type_info._ensure_loaded()
    cls = getattr(sw_type_info._wrapper_module, iface)
    return cls(obj._oleobj_)


async def build(adapter) -> dict[str, str]:
    app = adapter.swApp
    for hole_type, wanted in WANT:
        hsd_raw = app.GetHoleStandardsData(hole_type)
        if hsd_raw is None:
            print(f"== hole_type {hole_type}: GetHoleStandardsData -> None")
            continue
        hsd = _early(hsd_raw, "IHoleStandardsData")
        ret, indexes, standards = hsd.GetHoleStandards()
        indexes, standards = _tolist(indexes), _tolist(standards)
        print(f"== hole_type {hole_type}: standards {list(zip(indexes, standards))}")
        ansi = None
        for std in standards:
            if "inch" in str(std).lower() and "ansi" in str(std).lower():
                ansi = std
                break
        if ansi is None:
            print(f"   !! no Ansi Inch standard found in {standards}")
            continue
        ret, fids, fnames = hsd.GetFastenerTypes(ansi)
        fids, fnames = _tolist(fids), _tolist(fnames)
        print(f"   fastener types: {list(zip(fids, fnames))}")
        for fid, fname in zip(fids, fnames):
            if int(fid) not in wanted:
                continue
            ret, ttypes = hsd.GetFastenerTableTypes(ansi, fid)
            ttypes = _tolist(ttypes)
            print(f"   -- fastener {fid} ({fname}): table types {ttypes}")
            for tt in ttypes:
                ret, table = hsd.GetFastenerTable(ansi, fid, tt)
                if not ret or table is None:
                    print(f"      table {tt}: unavailable")
                    continue
                table = _early(table, "IHoleDataTable")
                ret, cols = table.GetColumnNames()
                cols = [str(c) for c in _tolist(cols)]
                nraw = table.GetRowCount()
                nrows = int(nraw[-1] if isinstance(nraw, tuple) else nraw)
                print(f"      table {tt}: {nrows} rows, cols {cols}")
                for r in range(nrows):
                    ret, row = table.GetRowData(r)
                    row = [str(x) for x in _tolist(row)]
                    print(f"        [{r:3d}] {row}")
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
