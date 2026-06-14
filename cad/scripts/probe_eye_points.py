r"""Throwaway: validate the 4 spring-eye arc_center edge points on the live model
before baking them into build_motion_study_springs.py.

Each spring endpoint is a ring-centre RefPoint created at RUNTIME on a SHARED part
doc (inherited by all instances, NEVER saved) -- same recipe as the cam ring
point. arc_center needs a part-LOCAL point that lies ON the eye hole's circular
edge. Candidate edge points (from reading the part scripts):
  channel-lever tab hole  Ø4.0 @ local (177.8,0,0)   -> [179.8, 0, 0]
  summing-lever hole 0    Ø4.5 @ (37.10,~5.45,-69.05) -> [39.35, 8.0, -69.05]
  gooseneck counter eye   Ø4.0 @ pin Y163,Z0          -> [-109.0, 165.0, 0]
  boss-hook counter eye   Ø3.0 @ arm Y15,Z0           -> [5.25, 16.5, 0]

Attaches to the doc the kinematic build left open. NEVER saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_eye_points.py
"""

from __future__ import annotations

import asyncio

from _common import _flag, _read_member, log
from build_motion_study import _find_one
from solidworks_mcp.adapters.solidworks.assembly import _byref_i4

CANDIDATES = [
    ("channel-lever-1", [179.8, 0.0, 0.0]),
    ("summing-lever-1", [39.35, 8.0, -69.05]),
    ("gooseneck-1", [-109.0, 165.0, 0.0]),
    ("boss-hook-1", [5.25, 16.5, 0.0]),
]


async def _try_point(adapter, top, top_title, comp_needle, edge_point):
    from solidworks_mcp.adapters.base import CreateReferencePointParameters
    comp, _ = _find_one(adapter, comp_needle)
    if comp is None:
        log(f"  {comp_needle}: component NOT FOUND")
        return
    part = adapter._attempt(lambda: comp.GetModelDoc2(), default=None)
    if part is None:
        log(f"  {comp_needle}: GetModelDoc2 None")
        return
    part_title = str(_read_member(part, "GetTitle"))
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(part_title, False, 2, _byref_i4()), default=None)
    adapter.currentModel = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=part)
    try:
        res = await adapter.create_reference_point(
            CreateReferencePointParameters(mode="arc_center", edge_point=edge_point))
        name = res.data.get("name") if res.is_success else None
        log(f"  {comp_needle} ({part_title}) edge={edge_point} -> "
            f"{'OK ' + str(name) if name else 'FAIL ' + str(res.error)}")
    except Exception as exc:  # noqa: BLE001
        log(f"  {comp_needle} edge={edge_point} -> EXC {exc}")
    finally:
        adapter._attempt(
            lambda: adapter.swApp.ActivateDoc3(top_title, False, 2, _byref_i4()), default=None)
        adapter.currentModel = top


async def main():
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    print("Connecting (ATTACH) ...", flush=True)
    await adapter.connect()
    doc = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=None)
    if doc is None:
        log("no ActiveDoc")
        return
    _flag(doc, "IModelDoc2")
    adapter.currentModel = doc
    top_title = str(_read_member(doc, "GetTitle"))
    log(f"ActiveDoc = {top_title!r}")

    for comp_needle, edge_point in CANDIDATES:
        await _try_point(adapter, doc, top_title, comp_needle, edge_point)

    await adapter.disconnect()
    print("Disconnected (NOT saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
