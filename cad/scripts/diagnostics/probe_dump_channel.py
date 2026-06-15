r"""Fast diagnostic: dump channel.SLDASM's per-part DISTANCE/ANGLE mate values.

Opens the channel sub assembly DIRECTLY (flat, not flexible -> the mate walk is
fast, no per-mate flexible-sub resolution) and logs every single-real-part
DISTANCE/ANGLE mate with its value + the planes it references. This is the ground
truth for the suppress classifier: the Basic Motion four-bar probe showed the bar
+ lever frozen at 0 deg while the rocker spun, and the classifier's amplitude-bar
"pose bucket" was 2870.1 (mm?) which cannot be the ~73 mm foot-X coordinate -- so
the bar's foot-X spin_driver may be mis-identified / not freed. Inspect here.

  C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_dump_channel.py

NEVER saves.
"""

from __future__ import annotations

import asyncio
import math

from build_motion_study import (
    DISTANCE, ANGLE, OUT_SLDASM, _iter_mates, _mate_value, _real_parts, _family,
)
from _common import log


async def main():
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    print("Connecting ...", flush=True)
    await adapter.connect()
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    path = str((OUT_SLDASM / "channel.SLDASM").resolve())
    await adapter.open_model(path)
    model = adapter.currentModel
    log(f"opened {path}")

    root = "channel"  # the doc-root pseudo-part name in its own mate group
    # Group single-real-part DISTANCE/ANGLE mates by (family, rounded value) so we
    # see exactly which values recur (pose/spin -> suppress) vs are unique (axial).
    from collections import defaultdict
    buckets = defaultdict(list)
    n = 0
    for _f, mate, name, mtype, parts, _val in _iter_mates(
            adapter, model, read_values=False, progress_every=40):
        if mtype not in (DISTANCE, ANGLE):
            continue
        reals = _real_parts(parts, root)
        if len(reals) != 1:
            continue
        fam = _family(reals[0])
        if fam not in ("amplitude-bar", "rocker-arm", "channel-lever", "connecting-rod"):
            continue
        val = _mate_value(adapter, mate, mtype)
        if val is None:
            continue
        disp = math.degrees(val) if mtype == ANGLE else val * 1000.0
        unit = "deg" if mtype == ANGLE else "mm"
        buckets[(fam, round(disp, 1), unit)].append(name)
        n += 1
    log(f"  walked, {n} single-real-part DISTANCE/ANGLE mates")
    log("  --- buckets (family, value, unit) -> count [first mate] ---")
    for (fam, v, unit), names in sorted(buckets.items()):
        tag = "RECUR" if len(names) >= 5 else "unique"
        log(f"    {tag:6s} {fam:16s} {v:10.1f} {unit:3s}  x{len(names):2d}  {names[0]}")

    await adapter.disconnect()
    print("Disconnected (NOT saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
