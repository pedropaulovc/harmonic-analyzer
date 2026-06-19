r"""Controlled experiment: is SolidWorks sketch inference deterministic?

Draws the IDENTICAL hex-bolt head polygon many times in fresh part docs within
one session and extrudes + measures the head volume each time. Independent
variable: ``SketchManager.AddToDB`` (False = inference engine ON, the legacy
add_line_chain path; True = inference suppressed, the fix). Same inputs every
iteration -- the only question is whether the OUTPUT (head volume) varies.

Analytic head volume = sqrt(3)/2 * AF^2 * H = 768.2 mm^3. The full-build failure
was 512.2 mm^3 (exactly 2/3 -> two hex vertices collapsed). If the inference
path produces a MIX of 768.2 and 512.2 (or extrude failures) across identical
iterations, inference is nondeterministic. If it is always one value, it is
deterministic.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diagnostics\exp_inference_determinism.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio

# Hex-bolt head geometry (verbatim from build_hex_bolt.py).
HEAD_AF = 12.7
HEAD_H = 5.5
RADIUS = HEAD_AF / math.sqrt(3.0)
HALF_FLAT = HEAD_AF / 2.0
POINTS = [
    (RADIUS, 0.0),
    (RADIUS / 2.0, HALF_FLAT),
    (-RADIUS / 2.0, HALF_FLAT),
    (-RADIUS, 0.0),
    (-RADIUS / 2.0, -HALF_FLAT),
    (RADIUS / 2.0, -HALF_FLAT),
]
ANALYTIC = math.sqrt(3.0) / 2.0 * HEAD_AF**2 * HEAD_H  # 768.2 mm^3
N = 15


async def _one(adapter, add_to_db: bool) -> tuple[float, int]:
    """Build the hex head once with the given AddToDB; return (volume_mm3,
    n_sketch_segments). volume = nan / segments = -1 on a hard failure."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    await adapter.create_part()
    await adapter.create_sketch("Top")
    sm = adapter.currentSketchManager
    sm.AddToDB = add_to_db
    verts = POINTS + [POINTS[0]]
    n_seg = 0
    try:
        for (x1, y1), (x2, y2) in zip(verts, verts[1:]):
            res = await adapter.add_line(x1, y1, x2, y2)
            if res.is_success:
                n_seg += 1
    finally:
        sm.AddToDB = False
    await adapter.exit_sketch()
    ext = await adapter.create_extrusion(ExtrusionParameters(depth=HEAD_H))
    if not getattr(ext, "is_success", True):
        return float("nan"), n_seg
    mp = await adapter.get_mass_properties()
    vol = mp.data.volume if mp.is_success else float("nan")
    return vol, n_seg


async def _trial(adapter, add_to_db: bool, label: str) -> None:
    print(f"\n=== {label}  (AddToDB={add_to_db}, inference {'OFF' if add_to_db else 'ON'}) ===")
    vols = []
    for i in range(N):
        vol, n_seg = await _one(adapter, add_to_db)
        tag = "OK " if abs(vol - ANALYTIC) < 0.5 else ("COLLAPSE" if vol == vol else "EXTRUDE-FAIL")
        print(f"  iter {i:02d}: volume={vol:8.2f} mm^3  segments={n_seg}  {tag}")
        vols.append(round(vol, 1) if vol == vol else float("nan"))
        adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    distinct = sorted({v for v in vols if v == v})
    nan_count = sum(1 for v in vols if v != v)
    print(f"  --> distinct volumes: {distinct}   extrude-failures: {nan_count}")
    verdict = "NONDETERMINISTIC" if (len(distinct) > 1 or nan_count) else "deterministic"
    print(f"  --> {label}: {verdict}")


async def main() -> int:
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    await adapter.connect()
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    print(f"analytic head volume = {ANALYTIC:.2f} mm^3 ; iterations per trial = {N}")
    await _trial(adapter, False, "INFERENCE PATH")
    await _trial(adapter, True, "SUPPRESSED PATH")
    await adapter.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
