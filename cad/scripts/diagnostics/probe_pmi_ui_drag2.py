r"""Synthesized UI drag of a DimXpert gtol in the normal (saved) view state.

The UI positive control proved: PMI displays in the ordinary viewport (NOT in
an activated annotation view — activating hides it, which sank the first drag
probe), click-drags persist through save (x/z, in-plane), and Select3/
SelectByID2 simply never work for DimXpert items.  So: open a scratch copy,
leave the view alone except zoom-to-fit, compute the frame's pixels via
IModelView::Transform, CLICK and verify via ISelectionMgr, drag, read, save,
reopen, read.

Run (SolidWorks open, desktop unlocked, hands off the mouse)::

    uv run python cad/scripts/diagnostics/probe_pmi_ui_drag2.py
"""

from __future__ import annotations

import asyncio
import ctypes
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ctypes.windll.user32.SetProcessDPIAware()

import win32api  # noqa: E402
import win32con  # noqa: E402
import win32gui  # noqa: E402

import _telemetry  # noqa: E402
import _watchdog  # noqa: E402
from _common import CAD_ROOT, _early_bound, _read_member  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter  # noqa: E402

SOURCE = CAD_ROOT / "out" / "sldprt" / "transgear-stub.SLDPRT"
SCRATCH = CAD_ROOT / "out" / "sldprt" / "transgear-stub-uidrag2.SLDPRT"
DRAG_PX = (180, -60)


def _gtols(model):
    out = {}
    for raw_view in tuple(model.Extension.AnnotationViews or ()):
        aview = _early_bound(raw_view, "IAnnotationView")
        if bool(aview.UnassignedView):
            continue
        for raw in tuple(aview.GetAnnotations2(True, True) or ()):
            item = _early_bound(raw, "IAnnotation")
            if int(item.GetType()) == 5:
                out[str(item.GetName())] = item
    return out


def _pixel(sw, mview, model_xyz):
    mu = _early_bound(sw.GetMathUtility(), "IMathUtility")
    point = _early_bound(mu.CreatePoint(list(model_xyz)), "IMathPoint")
    transform = _early_bound(mview.Transform, "IMathTransform")
    pixel = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
    x, y, _ = tuple(pixel.ArrayData)
    hwnd = int(mview.GetViewHWndx64)
    return win32gui.ClientToScreen(hwnd, (int(x), int(y)))


def _click(xy):
    win32api.SetCursorPos(xy)
    time.sleep(0.15)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.2)


def _drag(from_xy, to_xy):
    win32api.SetCursorPos(from_xy)
    time.sleep(0.3)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.3)
    steps = 25
    for step in range(1, steps + 1):
        x = from_xy[0] + (to_xy[0] - from_xy[0]) * step // steps
        y = from_xy[1] + (to_xy[1] - from_xy[1]) * step // steps
        win32api.SetCursorPos((x, y))
        time.sleep(0.02)
    time.sleep(0.3)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.5)


async def main() -> int:
    _telemetry.set_service("diagnostics")
    shutil.copy2(SOURCE, SCRATCH)
    adapter = PyWin32Adapter({})
    _watchdog.start()
    try:
        await adapter.connect()
        check = await adapter.open_model(str(SCRATCH))
        if not check.is_success:
            raise RuntimeError(f"open failed: {check.error}")
        model = adapter.currentModel
        model.ShowNamedView2("*Isometric", -1)
        model.ViewZoomtofit2()
        model.GraphicsRedraw2()
        time.sleep(1.5)

        hwnds: list[int] = []

        def _collect(hwnd, _):
            title = win32gui.GetWindowText(hwnd)
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetClassName(hwnd).startswith("Afx:") and "SOLIDWORKS" in title:
                hwnds.append(hwnd)

        win32gui.EnumWindows(_collect, None)
        if not hwnds:
            raise RuntimeError("no visible SOLIDWORKS main window")
        win32gui.ShowWindow(hwnds[0], win32con.SW_SHOWMAXIMIZED)
        win32gui.SetForegroundWindow(hwnds[0])
        time.sleep(0.5)

        sw = adapter.swApp
        selmgr = _early_bound(model.SelectionManager, "ISelectionMgr")
        mview = model.ActiveView
        items = _gtols(model)
        name, item = next(iter(items.items()))
        before = tuple(item.GetPosition() or ())
        anchor = _pixel(sw, mview, before)
        _telemetry.info(f"{name} before={before} anchor px={anchor}")

        grab = None
        for dy in range(-10, 31, 8):
            for dx in range(-10, 61, 10):
                candidate = (anchor[0] + dx, anchor[1] + dy)
                model.ClearSelection2(True)
                _click(candidate)
                count = int(selmgr.GetSelectedObjectCount2(-1))
                if count > 0:
                    kind = int(selmgr.GetSelectedObjectType3(1, -1))
                    _telemetry.info(f"click {candidate} -> count={count} type={kind}")
                    if kind == 6:  # swSelGTOLS
                        grab = candidate
                        break
            if grab:
                break
        if grab is None:
            raise RuntimeError("could not click-select the gtol frame")

        _telemetry.info(f"dragging {name} from {grab} by {DRAG_PX}")
        _drag(grab, (grab[0] + DRAG_PX[0], grab[1] + DRAG_PX[1]))
        after = tuple(item.GetPosition() or ())
        _telemetry.info(f"after drag: {before} -> {after}")

        model.ClearSelection2(True)
        model.SaveAs3(os.path.abspath(SCRATCH), 0, 0)
        _telemetry.info(f"post-save: {tuple(item.GetPosition() or ())}")
        adapter.swApp.QuitDoc(str(_read_member(model, "GetTitle")))

        check = await adapter.open_model(str(SCRATCH))
        if not check.is_success:
            raise RuntimeError(f"reopen failed: {check.error}")
        model = adapter.currentModel
        for iname, iitem in _gtols(model).items():
            _telemetry.info(f"reopened {iname}: {tuple(iitem.GetPosition() or ())}")
        adapter.swApp.QuitDoc(str(_read_member(model, "GetTitle")))
        SCRATCH.unlink(missing_ok=True)
        _telemetry.success("drag2 probe complete (scratch removed)")
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
