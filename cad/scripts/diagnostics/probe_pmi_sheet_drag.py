r"""Does a synthesized mouse drag of an imported gtol persist on a SHEET?

Part-side UI drags persist where every API setter reverts.  Same question on
the drawing: open a scratch copy of the built SLDDRW, compute the frame's
screen pixels via the drawing view transform, click (verify via
ISelectionMgr: type 6 = swSelGTOLS), drag to a distinct spot, save, reopen,
read back.

Run (SolidWorks open, desktop unlocked, hands off the mouse)::

    uv run python cad/scripts/diagnostics/probe_pmi_sheet_drag.py
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

SLDDRW = CAD_ROOT / "out" / "slddrw" / "transgear-stub.SLDDRW"
SCRATCH = CAD_ROOT / "out" / "slddrw" / "transgear-stub-sheetdrag.SLDDRW"
DRAG_PX = (220, 40)


def _gtols(draw):
    ddoc = _early_bound(draw, "IDrawingDoc")
    view = _early_bound(ddoc.GetFirstView(), "IView")
    out = {}
    while True:
        raw = view.GetNextView()
        if raw is None:
            break
        view = _early_bound(raw, "IView")
        for item in tuple(view.GetAnnotations() or ()):
            item = _early_bound(item, "IAnnotation")
            if bool(item.IsDimXpert()) and int(item.GetType()) == 5:
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
    shutil.copy2(SLDDRW, SCRATCH)
    adapter = PyWin32Adapter({})
    _watchdog.start()
    try:
        await adapter.connect()
        check = await adapter.open_model(str(SCRATCH))
        if not check.is_success:
            raise RuntimeError(f"open failed: {check.error}")
        draw = adapter.currentModel
        draw.ViewZoomtofit2()
        draw.GraphicsRedraw2()
        time.sleep(1.0)

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
        selmgr = _early_bound(draw.SelectionManager, "ISelectionMgr")
        mview = draw.ActiveView
        items = _gtols(draw)
        name, item = next(iter(items.items()))
        before = tuple(item.GetPosition() or ())
        anchor = _pixel(sw, mview, before)
        _telemetry.info(f"{name} before={before} anchor px={anchor}")

        grab = None
        for dy in range(-8, 25, 6):
            for dx in range(-8, 70, 8):
                candidate = (anchor[0] + dx, anchor[1] + dy)
                draw.ClearSelection2(True)
                _click(candidate)
                if int(selmgr.GetSelectedObjectCount2(-1)) > 0:
                    kind = int(selmgr.GetSelectedObjectType3(1, -1))
                    if kind == 6:
                        _telemetry.info(f"gtol selected at {candidate}")
                        grab = candidate
                        break
            if grab:
                break
        if grab is None:
            raise RuntimeError("could not click-select the gtol frame on sheet")

        _drag(grab, (grab[0] + DRAG_PX[0], grab[1] + DRAG_PX[1]))
        after = tuple(item.GetPosition() or ())
        _telemetry.info(f"after drag: {before} -> {after}")

        draw.ClearSelection2(True)
        draw.SaveAs3(os.path.abspath(SCRATCH), 0, 0)
        _telemetry.info(f"post-save: {tuple(item.GetPosition() or ())}")
        adapter.swApp.QuitDoc(str(_read_member(draw, "GetTitle")))

        check = await adapter.open_model(str(SCRATCH))
        if not check.is_success:
            raise RuntimeError(f"reopen failed: {check.error}")
        draw = adapter.currentModel
        for iname, iitem in _gtols(draw).items():
            _telemetry.info(f"reopened {iname}: {tuple(iitem.GetPosition() or ())}")
        adapter.swApp.QuitDoc(str(_read_member(draw, "GetTitle")))
        SCRATCH.unlink(missing_ok=True)
        _telemetry.success("sheet-drag probe complete (scratch removed)")
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
