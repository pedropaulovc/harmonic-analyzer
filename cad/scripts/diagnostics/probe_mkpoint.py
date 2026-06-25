r"""Throwaway: get a mateable ring-centre RefPoint created on the connecting-rod
part doc. Edge-select failed when the part was non-active; ACTIVATE the part doc
first (ActivateDoc3), then arc_center on the Ø51 bore edge. Reports the feature
name + lists ref points. Fast. NEVER saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_mkpoint.py
"""

from __future__ import annotations

import asyncio

import _telemetry
from _common import _flag, _read_member, check, log
from build_motion_study import _find_one
from solidworks_mcp.adapters.solidworks.assembly import _byref_i4

# candidate points on the bore circular edge (mm) -- try a few Z in case the ring
# faces are not at +/-1.5 exactly.
CANDIDATES = [
    [25.5, 0.0, 1.5], [25.5, 0.0, -1.5], [25.5, 0.0, 0.0],
    [0.0, 25.5, 1.5], [-25.5, 0.0, 1.5],
]


async def main():
    from solidworks_mcp.adapters.base import CreateReferencePointParameters
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    _telemetry.info("Connecting (ATTACH) ...")
    await adapter.connect()
    top = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=None)
    if top is None:
        log("no ActiveDoc")
        return
    _flag(top, "IModelDoc2")
    adapter.currentModel = top
    top_title = str(_read_member(top, "GetTitle"))
    log(f"top = {top_title!r}")

    rod_comp, _ = _find_one(adapter, "connecting-rod-1", toplevel=False)
    part = adapter._attempt(lambda: rod_comp.GetModelDoc2(), default=None)
    title = str(_read_member(part, "GetTitle"))
    log(f"rod part = {title!r}")

    # activate the part doc so SelectByID2 resolves in it.
    act = adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(title, False, 2, _byref_i4()), default=None)
    active_now = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=None)
    log(f"  activated; ActiveDoc now = {str(_read_member(active_now, 'GetTitle'))!r}")
    adapter.currentModel = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=part)

    made = None
    for pt_mm in CANDIDATES:
        res = await adapter.create_reference_point(
            CreateReferencePointParameters(mode="arc_center", edge_point=pt_mm))
        if res.is_success:
            made = res.data
            name = made.get("name") if isinstance(made, dict) else getattr(made, "name", made)
            log(f"  CREATED ref point {name!r} from edge point {pt_mm}")
            break
        log(f"  edge point {pt_mm} -> {res.error}")

    # restore assembly active.
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(top_title, False, 2, _byref_i4()), default=None)
    log(f"  re-activated {top_title!r}; success={made is not None}")

    await adapter.disconnect()
    _telemetry.info("Disconnected (NOT saved).")


if __name__ == "__main__":
    asyncio.run(main())
