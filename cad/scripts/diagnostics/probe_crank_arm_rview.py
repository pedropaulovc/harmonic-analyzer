r"""Probe: what does SelectByID2 actually hit in the crank-arm *Right view?

Places the right view exactly as draw_crank_arm does, then walks a grid of
sheet stations along the top/bottom (y = centre +/- 0.016) and the centreline,
reporting for each whether an EDGE selects and what entity it resolves to
(via ISelectionMgr).  Settles the sheet-x <-> part-z mapping and edge
selectability empirically instead of by camera-convention reasoning.

Run with SolidWorks open::

    uv run python cad\scripts\diagnostics\probe_crank_arm_rview.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import CAD_ROOT, _early_bound, check, run_build  # noqa: E402
from _drawing_common import new_project_drawing, view_name  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import null_callout  # noqa: E402
from solidworks_mcp.adapters.solidworks.drawing import place_view  # noqa: E402

SOURCE = CAD_ROOT / "out" / "sldprt" / "crank-arm.SLDPRT"
RIGHT_CENTER = (0.300, 0.135)


async def build(adapter: Any) -> None:
    check("open crank-arm source", await adapter.open_model(str(SOURCE)))
    draw_model, _sheet = new_project_drawing(
        adapter, property_view="crank-arm", scale=(2.0, 1.0)
    )
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, right)):
        raise RuntimeError("failed to activate the right view")

    # Report the view's actual outline so the bbox/centre assumption is checked
    # directly instead of inferred.
    outline = right.GetOutline()
    _telemetry.info(f"view outline (sheet m): {[round(v, 4) for v in outline]}")

    sel_mgr = draw.SelectionManager

    def describe(x: float, y: float, label: str, append: bool = False) -> bool:
        hit = draw.Extension.SelectByID2(
            "", "EDGE", x, y, 0.0, append, 0, null_callout(), 0
        )
        if not hit:
            _telemetry.info(f"{label} ({x:.4f},{y:.4f}): NO HIT")
            return False
        idx = sel_mgr.GetSelectedObjectCount2(-1)
        ent = sel_mgr.GetSelectedObject6(idx, -1)
        curve = "?"
        try:
            edge = _early_bound(ent, "IEdge")
            c = edge.GetCurve()
            if c.IsLine():
                v1 = edge.GetStartVertex()
                v2 = edge.GetEndVertex()
                p1 = [round(v * 1000, 2) for v in v1.GetPoint()]
                p2 = [round(v * 1000, 2) for v in v2.GetPoint()]
                curve = f"LINE {p1}->{p2}"
            elif c.IsCircle():
                cp = [round(v, 2) for v in c.CircleParams]
                curve = f"CIRCLE params={cp}"
            else:
                curve = "OTHER"
        except Exception as exc:  # noqa: BLE001 - probe: report, not fail
            curve = f"?({exc})"
        _telemetry.info(f"{label} ({x:.4f},{y:.4f}): {curve}")
        return True

    # Candidate picks (sheet-right = part -Z: left outline = z=8 south face,
    # right outline = z=-9.2 hub end).
    lx, rx = 0.2828, 0.3172
    draw.ClearSelection2(True)
    ok0 = describe(lx, 0.119, "width p0 (corner z8,y-8)")
    ok1 = describe(lx, 0.151, "width p1 (corner z8,y+8)", append=True)
    if ok0 and ok1:
        dim = draw.AddDimension2(0.252, 0.135, 0.0)
        _telemetry.info(f"width AddDimension2 -> {'OK' if dim is not None else 'None'}")
    draw.ClearSelection2(True)
    describe(lx, 0.145, "datum A candidate (z8 face, y+5)")
    draw.ClearSelection2(True)
    describe(rx, 0.135, "FCF hub end candidate (z-9.2, y0)")
    draw.ClearSelection2(True)
    describe(rx, 0.145, "FCF hub end candidate (z-9.2, y+5)")
    draw.ClearSelection2(True)


if __name__ == "__main__":
    _telemetry.set_service("diagnostics")
    sys.exit(run_build(build))
