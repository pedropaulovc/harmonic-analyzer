r"""Check the four stock-spring support RefPoints on the active assembly.

Run with cad/scripts on PYTHONPATH after opening a disposable motion assembly.
Creates transient part features only; never saves any document.
"""

from __future__ import annotations

import asyncio

import _telemetry
from _common import _flag, _read_member, log
from build_motion_study import _find_one
from build_motion_study_springs import (
    CH_LEVER_EYE, SUM_LEVER_EYE, GOOSENECK_EYE, COUNTER_ANCHOR_EYE, _eye_point,
)

CANDIDATES = [
    ("channel-lever-1", CH_LEVER_EYE),
    ("summing-lever-1", SUM_LEVER_EYE),
    ("gooseneck-1", GOOSENECK_EYE),
    ("boss-hook-1", COUNTER_ANCHOR_EYE),
]


async def _try_point(adapter, comp_needle, local_point):
    name = await _eye_point(adapter, comp_needle, local_point, comp_needle)
    comp, _ = _find_one(adapter, comp_needle)
    part = _read_member(comp, "GetModelDoc2")
    feature = part.FeatureByName(name)
    ref = _read_member(feature, "GetSpecificFeature2")
    point = _read_member(ref, "GetRefPoint")
    actual = tuple(float(value) * 1000.0 for value in _read_member(point, "ArrayData"))
    if len(actual) != 3 or any(abs(a - b) > 1e-6 for a, b in zip(actual, local_point)):
        raise RuntimeError(f"{comp_needle}: RefPoint {actual} != {local_point} mm")
    if comp.GetCorresponding(feature) is None:
        raise RuntimeError(f"{comp_needle}: RefPoint has no assembly correspondence")
    log(f"  {comp_needle}: {name} = {actual} mm; assembly correspondence OK")


async def main():
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    _telemetry.info("Connecting (ATTACH) ...")
    await adapter.connect()
    try:
        doc = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=None)
        if doc is None:
            raise RuntimeError("no ActiveDoc")
        _flag(doc, "IModelDoc2")
        adapter.currentModel = doc
        log(f"ActiveDoc = {str(_read_member(doc, 'GetTitle'))!r}")
        for comp_needle, local_point in CANDIDATES:
            await _try_point(adapter, comp_needle, local_point)
    finally:
        await adapter.disconnect()
        _telemetry.info("Disconnected (NOT saved).")


if __name__ == "__main__":
    asyncio.run(main())
