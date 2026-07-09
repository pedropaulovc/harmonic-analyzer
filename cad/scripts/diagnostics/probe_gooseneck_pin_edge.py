r"""Throwaway probe: which edge point on the gooseneck spring pin accepts
create_reference_point(arc_center)? Opens the part standalone; never saves.

    uv run python cad\scripts\diagnostics\probe_gooseneck_pin_edge.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import OUT_SLDPRT, check, log, run_build  # noqa: E402


CANDIDATES = [
    [-98.0, 165.0, 0.0],
    [-98.0, 163.0, 2.0],
    [-98.0, 163.0, -2.0],
    [-98.0, 161.0, 0.0],
    [-109.0, 165.0, 0.0],
    [-109.0, 163.0, 2.0],
]


async def build(adapter):
    from solidworks_mcp.adapters.base import CreateReferencePointParameters
    check("open gooseneck", await adapter.open_model(
        str((OUT_SLDPRT / "gooseneck.SLDPRT").resolve())))
    for ep in CANDIDATES:
        res = await adapter.create_reference_point(
            CreateReferencePointParameters(mode="arc_center", edge_point=ep))
        name = None
        if res.is_success:
            name = res.data.get("name") if isinstance(res.data, dict) else None
        log(f"arc_center @ {ep} -> {'OK ' + str(name) if res.is_success else 'FAIL'}")
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
