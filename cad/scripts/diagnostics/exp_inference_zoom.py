r"""Smoking-gun experiment: does VIEW ZOOM change SolidWorks' sketch-inference
result for an identical hex?

Hypothesis: sketch inference snapping tolerance is partly SCREEN-space, so the
same sketch coordinates collapse (or not) depending on the current view scale.
That would make inference deterministic-per-view but context-sensitive across
sessions -- explaining why earlier full builds did not hit the collapse.

For each zoom box (model-space extents the view is fitted to), build the
hex-bolt head through the INFERENCE path (AddToDB=False) and measure the head
volume. If the volume varies with zoom, inference is view-dependent.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diagnostics\exp_inference_zoom.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio

HEAD_AF = 12.7
HEAD_H = 5.5
RADIUS = HEAD_AF / math.sqrt(3.0)
HALF_FLAT = HEAD_AF / 2.0
POINTS = [
    (RADIUS, 0.0), (RADIUS / 2.0, HALF_FLAT), (-RADIUS / 2.0, HALF_FLAT),
    (-RADIUS, 0.0), (-RADIUS / 2.0, -HALF_FLAT), (RADIUS / 2.0, -HALF_FLAT),
]
ANALYTIC = math.sqrt(3.0) / 2.0 * HEAD_AF**2 * HEAD_H

# Zoom boxes in METRES: the half-extent the view is fitted to. Small box = zoomed
# IN (fine tolerance), large box = zoomed OUT (coarse tolerance).
ZOOM_HALF_EXTENTS_M = [0.005, 0.02, 0.05, 0.2, 1.0, 5.0]


async def _build_inference(adapter) -> float:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    await adapter.create_part()
    await adapter.create_sketch("Top")
    sm = adapter.currentSketchManager
    sm.AddToDB = False  # inference ON
    verts = POINTS + [POINTS[0]]
    try:
        for (x1, y1), (x2, y2) in zip(verts, verts[1:]):
            await adapter.add_line(x1, y1, x2, y2)
    finally:
        sm.AddToDB = False
    await adapter.exit_sketch()
    await adapter.create_extrusion(ExtrusionParameters(depth=HEAD_H))
    mp = await adapter.get_mass_properties()
    return mp.data.volume if mp.is_success else float("nan")


async def main() -> int:
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    await adapter.connect()
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    print(f"analytic head volume = {ANALYTIC:.2f} mm^3 ; inference path, varying view zoom\n")
    results = []
    for half in ZOOM_HALF_EXTENTS_M:
        await adapter.create_part()
        model = adapter.currentModel
        # Fit the view to a box of +-half metres so the on-screen scale changes.
        adapter._attempt(lambda h=half: model.ViewZoomTo2(-h, -h, -h, h, h, h), default=None)
        adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
        # Re-open a fresh part already zoomed: set zoom right after sketch start.
        from solidworks_mcp.adapters.base import ExtrusionParameters
        await adapter.create_part()
        m2 = adapter.currentModel
        adapter._attempt(lambda h=half: m2.ViewZoomTo2(-h, -h, -h, h, h, h), default=None)
        await adapter.create_sketch("Top")
        sm = adapter.currentSketchManager
        sm.AddToDB = False
        verts = POINTS + [POINTS[0]]
        for (x1, y1), (x2, y2) in zip(verts, verts[1:]):
            await adapter.add_line(x1, y1, x2, y2)
        await adapter.exit_sketch()
        await adapter.create_extrusion(ExtrusionParameters(depth=HEAD_H))
        mp = await adapter.get_mass_properties()
        vol = mp.data.volume if mp.is_success else float("nan")
        tag = "OK" if abs(vol - ANALYTIC) < 0.5 else "COLLAPSE"
        print(f"  zoom +-{half*1000:7.1f} mm : volume={vol:8.2f} mm^3  {tag}")
        results.append(round(vol, 1))
        adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    print(f"\n  distinct volumes across zoom levels: {sorted(set(results))}")
    print("  --> view-dependent" if len(set(results)) > 1 else "  --> NOT view-dependent")
    await adapter.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
