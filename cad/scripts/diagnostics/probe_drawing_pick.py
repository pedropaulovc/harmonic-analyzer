"""Map the drawing edges around a failing coordinate pick.

    uv run python cad/scripts/diagnostics/probe_drawing_pick.py <draw_module> <label substring> [half_mm] [step_mm]

Runs the drawing recipe with its add_edge_dimension wrapped: when a call's
label contains the substring, the wrapper prints the target view's outline and
position, then scans a grid around p0/p1 with SelectByID2("EDGE") and prints
an ASCII map of the hits (sheet mm), so the right pick can be read off.  Then
it raises to stop the build (nothing is saved).  Needs the COM seat idle.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import _early_bound, run_build  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import null_callout  # noqa: E402

module_name, needle = sys.argv[1], sys.argv[2]
half = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0
step = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
draw_mod = importlib.import_module(module_name)
real_add_edge_dimension = draw_mod.add_edge_dimension


class Stop(RuntimeError):
    pass


def _scan(adapter, view, p0, p1):
    v = _early_bound(view, "IView")
    outline = tuple(v.GetOutline() or ())
    pos = tuple(v.Position or ())
    name = str(v.GetName2())
    print(f"VIEW {name!r} outline(m)={outline} position(m)={pos}")
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    ddoc.ActivateView(name)
    cx = (p0[0] + p1[0]) / 2.0 * 1000.0
    cy = (p0[1] + p1[1]) / 2.0 * 1000.0
    xs = [cx - half + i * step for i in range(int(2 * half / step) + 1)]
    ys = [cy + half - i * step for i in range(int(2 * half / step) + 1)]
    print(f"grid centre ({cx:.1f}, {cy:.1f}) mm, +/-{half} mm, step {step} mm; "
          f"p0={tuple(round(c*1000,2) for c in p0)} p1={tuple(round(c*1000,2) for c in p1)}")
    print("     " + "".join("|" if abs(x - cx) < step / 2 else " " for x in xs))
    for y in ys:
        row = []
        for x in xs:
            draw.ClearSelection2(True)
            hit = draw.Extension.SelectByID2("", "EDGE", x / 1000.0, y / 1000.0, 0.0, False, 0, null_callout(), 0)
            row.append("#" if hit else ("." if abs(y - cy) < step / 2 else " "))
        print(f"{y:6.1f} " + "".join(row))
    draw.ClearSelection2(True)
    # What is actually under p0/p1 and along the row: select with ANY type and
    # report the selection type code (swSelectType_e) + a coarse identity.
    sel = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for label_pt, pt in (("p0", p0), ("p1", p1)):
        for dx in (-0.002, -0.001, 0.0, 0.001, 0.002):
            draw.ClearSelection2(True)
            hit = draw.Extension.SelectByID2("", "", pt[0] + dx, pt[1], 0.0, False, 0, null_callout(), 0)
            kind = int(sel.GetSelectedObjectType3(1, -1)) if hit else -1
            print(f"  {label_pt} dx={dx*1000:+.0f}mm any-type hit={bool(hit)} type={kind}")
    # And: does a two-EDGE pick at p0/p1 yield a horizontal dimension at all?
    draw.ClearSelection2(True)
    ok0 = draw.Extension.SelectByID2("", "EDGE", p0[0], p0[1], 0.0, False, 0, null_callout(), 0)
    ok1 = draw.Extension.SelectByID2("", "EDGE", p1[0], p1[1], 0.0, True, 0, null_callout(), 0)
    dim = draw.AddHorizontalDimension2((p0[0]+p1[0])/2, p0[1] + 0.02, 0.0) if (ok0 and ok1) else None
    print(f"  EDGE picks ok0={bool(ok0)} ok1={bool(ok1)} -> AddHorizontalDimension2 {'OK' if dim is not None else 'None'}")
    draw.ClearSelection2(True)


def wrapper(adapter, view, *, p0, p1, text_xy, label, **kw):
    if needle in label:
        print(f"=== intercepted {label!r}")
        _scan(adapter, view, p0, p1)
        raise Stop(f"probe done for {label!r}")
    return real_add_edge_dimension(adapter, view, p0=p0, p1=p1, text_xy=text_xy, label=label, **kw)


draw_mod.add_edge_dimension = wrapper


async def build(adapter):
    try:
        await draw_mod.build(adapter)
    except Stop as exc:
        print(str(exc))
        # Snapshot the sheet as it stands so the section/detail can be SEEN.
        import subprocess
        # An unsaved drawing cannot export straight to PDF: save the SLDDRW
        # first (the pipeline's save_drawing does the same), then the PDF, and
        # trust file existence, not SaveAs3's return code.
        out = Path(__file__).with_name(f"probe-{module_name}.pdf")
        slddrw = out.with_suffix(".SLDDRW")
        draw = adapter.currentModel
        for path in (slddrw, out):
            if path.exists():
                path.unlink()
            draw.SaveAs3(str(path), 0, 0)
        print(f"snapshot pdf exists={out.exists()} -> {out}")
        if out.exists():
            subprocess.run(["pdftoppm", "-r", "100", "-png", "-singlefile", str(out), str(out.with_suffix(""))], check=False)
            print(f"snapshot png -> {out.with_suffix('.png')}")
    return {}


if __name__ == "__main__":
    _telemetry.set_service("diagnostic")
    sys.exit(run_build(build))
