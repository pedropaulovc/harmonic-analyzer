r"""Synthesized sheet drag + write-back check into the referenced part.

The user's manual sheet drags this morning left SEPARATED positions in the
PART file — evidence that dragging imported DimXpert PMI on a sheet writes
the position back into the referenced model, which the drawing save then
re-saves.  If a SYNTHESIZED drag does the same, the pipeline can place PMI
deterministically at part-build time via a throwaway section drawing.

Uses the transgear-stub-secttest pair probe_pmi_section_import.py left on
disk (drawing references the -secttest part COPY, so nothing pipeline-owned
is touched).

Run (SolidWorks open, desktop unlocked, hands off the mouse)::

    uv run python cad/scripts/diagnostics/probe_pmi_sheet_drag2.py
"""

from __future__ import annotations

import asyncio
import ctypes
import os
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

SCRATCH_PRT = CAD_ROOT / "out" / "sldprt" / "transgear-stub-secttest.SLDPRT"
SCRATCH_DRW = CAD_ROOT / "out" / "slddrw" / "transgear-stub-secttest.SLDDRW"
DRAG_PX = (150, 90)


def _sheet_gtols(draw):
    ddoc = _early_bound(draw, "IDrawingDoc")
    view = _early_bound(ddoc.GetFirstView(), "IView")
    out = {}
    while True:
        raw = view.GetNextView()
        if raw is None:
            break
        view = _early_bound(raw, "IView")
        for raw_ann in tuple(view.GetAnnotations() or ()):
            item = _early_bound(raw_ann, "IAnnotation")
            if bool(item.IsDimXpert()) and int(item.GetType()) == 5:
                out[str(item.GetName())] = item
    return out


def _part_positions(model):
    out = {}
    for raw_view in tuple(model.Extension.AnnotationViews or ()):
        aview = _early_bound(raw_view, "IAnnotationView")
        for raw in tuple(aview.GetAnnotations2(False, True) or ()):
            item = _early_bound(raw, "IAnnotation")
            if int(item.GetType()) == 5:
                out[str(item.GetName())] = tuple(item.GetPosition() or ())
    return out


def _pixel(sw, mview, sheet_xyz):
    from solidworks_mcp.adapters.com_variant import double_array

    mu = _early_bound(sw.GetMathUtility(), "IMathUtility")
    # a bare python list mis-marshals here (elements shift one slot); the
    # typed VT_R8 array is what the pipeline's model_point_in_view uses
    point = _early_bound(
        mu.CreatePoint(double_array([float(v) for v in sheet_xyz])), "IMathPoint"
    )
    transform = _early_bound(mview.Transform, "IMathTransform")
    pixel = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
    x, y, _ = tuple(pixel.ArrayData)
    hwnd = int(mview.GetViewHWndx64)
    return win32gui.ClientToScreen(hwnd, (int(x), int(y)))


def _click(xy):
    win32api.SetCursorPos(xy)
    time.sleep(0.12)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.18)


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
    adapter = PyWin32Adapter({})
    _watchdog.start()
    try:
        await adapter.connect()
        adapter.swApp.CloseAllDocuments(True)
        check = await adapter.open_model(str(SCRATCH_DRW))
        if not check.is_success:
            raise RuntimeError(f"open failed: {check.error}")
        draw = adapter.currentModel
        draw.ViewZoomtofit2()
        draw.GraphicsRedraw2()
        time.sleep(1.0)

        hwnds: list[int] = []

        def _collect(hwnd, _):
            title = win32gui.GetWindowText(hwnd)
            if (
                win32gui.IsWindowVisible(hwnd)
                and win32gui.GetClassName(hwnd).startswith("Afx:")
                and "SOLIDWORKS" in title
            ):
                hwnds.append(hwnd)

        win32gui.EnumWindows(_collect, None)
        if not hwnds:
            raise RuntimeError("no visible SOLIDWORKS main window")
        win32gui.ShowWindow(hwnds[0], win32con.SW_SHOWMAXIMIZED)
        try:
            win32gui.SetForegroundWindow(hwnds[0])
        except Exception:
            # Windows denies foreground steals from background processes; a
            # synthetic ALT tap lifts the lock (documented SetForegroundWindow
            # unlock), with SwitchToThisWindow as the fallback.
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            try:
                win32gui.SetForegroundWindow(hwnds[0])
            except Exception:
                import win32process

                user32 = ctypes.windll.user32
                fg = win32gui.GetForegroundWindow()
                fg_thread = win32process.GetWindowThreadProcessId(fg)[0] if fg else 0
                our_thread = win32api.GetCurrentThreadId()
                if fg_thread and fg_thread != our_thread:
                    user32.AttachThreadInput(our_thread, fg_thread, True)
                try:
                    win32gui.SetForegroundWindow(hwnds[0])
                except Exception:
                    user32.SwitchToThisWindow(hwnds[0], True)
                finally:
                    if fg_thread and fg_thread != our_thread:
                        user32.AttachThreadInput(our_thread, fg_thread, False)
        time.sleep(0.5)
        if win32gui.GetForegroundWindow() != hwnds[0]:
            raise RuntimeError("could not bring SOLIDWORKS to the foreground")

        sw = adapter.swApp
        selmgr = _early_bound(draw.SelectionManager, "ISelectionMgr")
        mview = draw.ActiveView
        items = _sheet_gtols(draw)
        # pick the on-sheet frame (the second sits off the A-size sheet edge)
        name, item = min(
            items.items(), key=lambda kv: tuple(kv[1].GetPosition() or ())[0]
        )
        before = tuple(item.GetPosition() or ())
        anchor = _pixel(sw, mview, before)
        _telemetry.info(f"{name} before={before} anchor px={anchor}")

        grab = None
        for dy in range(-12, 25, 6):
            for dx in range(-12, 80, 8):
                candidate = (anchor[0] + dx, anchor[1] + dy)
                draw.ClearSelection2(True)
                _click(candidate)
                if int(selmgr.GetSelectedObjectCount2(-1)) > 0:
                    kind = int(selmgr.GetSelectedObjectType3(1, -1))
                    if kind == 6:  # swSelGTOLS
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
        draw.SaveAs3(os.path.abspath(SCRATCH_DRW), 0, 0)
        adapter.swApp.CloseAllDocuments(True)

        check = await adapter.open_model(str(SCRATCH_DRW))
        if not check.is_success:
            raise RuntimeError(f"drawing reopen failed: {check.error}")
        for iname, iitem in _sheet_gtols(adapter.currentModel).items():
            _telemetry.info(
                f"reopened sheet {iname}: {tuple(iitem.GetPosition() or ())}"
            )
        adapter.swApp.CloseAllDocuments(True)

        check = await adapter.open_model(str(SCRATCH_PRT))
        if not check.is_success:
            raise RuntimeError(f"part reopen failed: {check.error}")
        for iname, pos in _part_positions(adapter.currentModel).items():
            _telemetry.info(f"part file {iname}: {pos}")
        adapter.swApp.QuitDoc(str(_read_member(adapter.currentModel, "GetTitle")))
        _telemetry.success("sheet-drag2 probe complete (scratch pair kept)")
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
