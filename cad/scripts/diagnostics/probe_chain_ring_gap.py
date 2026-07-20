r"""Probe: machine-frame bounding boxes of the chain links clashing the ring.

Opens the built paper-drive assembly and prints GetBox for the two links the
top-assembly interference gate flagged against the crank-pin ring, so the
ring's relief swing can be sized from measured geometry instead of the chain
plane's nominal band.

Run with SolidWorks open (seat free)::

    uv run python cad\scripts\diagnostics\probe_chain_ring_gap.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import CAD_ROOT, _early_bound, check, run_build  # noqa: E402

SOURCE = CAD_ROOT / "out" / "sldasm" / "paper-drive.SLDASM"
TARGETS = ("chain-outer-link-18", "chain-inner-link-19", "chain-outer-link-17")


async def build(adapter: Any) -> None:
    check("open paper-drive", await adapter.open_model(str(SOURCE)))
    model = adapter.currentModel
    asm = _early_bound(model, "IAssemblyDoc")
    for comp in asm.GetComponents(True):
        name = comp.Name2.split("/")[-1]
        if name not in TARGETS:
            continue
        box = comp.GetBox(False, False)
        lo = [round(v * 1000, 2) for v in box[:3]]
        hi = [round(v * 1000, 2) for v in box[3:]]
        _telemetry.info(f"{name}: lo={lo} hi={hi}")


if __name__ == "__main__":
    _telemetry.set_service("diagnostics")
    sys.exit(run_build(build))
