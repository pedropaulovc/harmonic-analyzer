r"""Positive control: does a REAL UI drag of a DimXpert gtol persist through save?

Every API position setter reverts at save.  Before declaring the feature dead,
reproduce the one form known to work in the UI — a mouse drag — synthetically:
open a scratch copy visibly, activate+reorient the front annotation view, zoom
to fit, compute the gtol frame's pixel position via IModelView::Transform,
SendInput-drag it 150 px right, then read/save/reopen/read.

Run (SolidWorks open, desktop unlocked, do not touch the mouse)::

    uv run python cad/scripts/diagnostics/probe_pmi_ui_drag.py
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ctypes

ctypes.windll.user32.SetProcessDPIAware()

import win32api  # noqa: E402
import win32con  # noqa: E402
import win32gui  # noqa: E402

import _telemetry  # noqa: E402
import _watchdog  # noqa: E402
from _common import CAD_ROOT, _early_bound, _read_member  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter  # noqa: E402

SOURCE = CAD_ROOT / "out" / "sldprt" / "transgear-stub.SLDPRT"
SCRATCH = CAD_ROOT / "out" / "sldprt" / "transgear-stub-uidrag.SLDPRT"
DRAG_PX = 150


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


def _front_annotation_view(model):
    for raw_view in tuple(model.Extension.AnnotationViews or ()):
        aview = _early_bound(raw_view, "IAnnotationView")
        if bool(aview.UnassignedView):
            continue
        if tuple(aview.GetAnnotations2(True, True) or ()):
            return aview
    raise RuntimeError("no populated annotation view")


def _screen_xy(sw, mview, model_xyz):
    mu = _early_bound(sw.GetMathUtility(), "IMathUtility")
    point = _early_bound(
        mu.CreatePoint(list(model_xyz)), "IMathPoint"
    )
    transform = _early_bound(mview.Transform, "IMathTransform")
    pixel = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
    x, y, _ = tuple(pixel.ArrayData)
    hwnd = int(mview.GetViewHWndx64)
    sx, sy = win32gui.ClientToScreen(hwnd, (int(x), int(y)))
    return sx, sy


def _drag(from_xy, to_xy):
    win32api.SetCursorPos(from_xy)
    time.sleep(0.3)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.3)
    steps = 20
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
        # make the PMI visible: swDisplayAnnotations=31, swDisplayAllAnnotations=197,
        # swDisplayDimXpertDimensions=360
        model.SetUserPreferenceToggle(31, True)
        model.SetUserPreferenceToggle(197, True)
        model.SetUserPreferenceToggle(360, True)
        was_hide = bool(model.GetUserPreferenceToggle(198))
        model.SetUserPreferenceToggle(198, False)  # swViewDisplayHideAllTypes
        _telemetry.info(f"hide-all-types was {was_hide}, now False")
        aview = _front_annotation_view(model)
        aview.Show()
        aview.ActivateAndReorient()
        model.ViewZoomtofit2()
        model.GraphicsRedraw2()
        time.sleep(2.5)

        sw = adapter.swApp
        candidates: list[int] = []

        def _collect(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if not (win32gui.GetClassName(hwnd).startswith("Afx:") and "SOLIDWORKS" in title):
                return
            candidates.append(hwnd)

        win32gui.EnumWindows(_collect, None)
        if not candidates:
            raise RuntimeError("no visible SOLIDWORKS main window found")
        sw_hwnd = candidates[0]
        win32gui.ShowWindow(sw_hwnd, win32con.SW_SHOWMAXIMIZED)
        win32gui.SetForegroundWindow(sw_hwnd)
        time.sleep(0.5)
        _telemetry.info(
            f"foreground now {win32gui.GetWindowText(win32gui.GetForegroundWindow())!r}"
        )

        items = _gtols(model)
        name, item = next(iter(items.items()))
        before = tuple(item.GetPosition() or ())
        mview = model.ActiveView
        sx, sy = _screen_xy(sw, mview, before)
        from PIL import ImageGrab

        shot = ImageGrab.grab()
        shot.save(
            "C:/Users/pedro/AppData/Local/Temp/claude/C--src-harmonic-analyzer/"
            "5abff248-7124-4f9b-9f48-4829dee216fe/scratchpad/grab_point.png"
        )
        _telemetry.info(f"computed anchor pixel ({sx}, {sy}); screenshot saved")
        selmgr = _early_bound(model.SelectionManager, "ISelectionMgr")
        grab = None
        for dy in range(0, 41, 8):
            for dx in range(0, 61, 10):
                candidate = (sx + dx, sy + dy)
                model.ClearSelection2(True)
                win32api.SetCursorPos(candidate)
                time.sleep(0.15)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                time.sleep(0.05)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                time.sleep(0.15)
                if int(selmgr.GetSelectedObjectCount2(-1)) > 0:
                    kind = int(selmgr.GetSelectedObjectType3(1, -1))
                    _telemetry.info(
                        f"click at {candidate} selected object type {kind}"
                    )
                    if kind == 6:  # swSelGTOLS
                        grab = candidate
                        break
            if grab:
                break
        if grab is None:
            raise RuntimeError("never managed to click-select the gtol frame")
        _telemetry.info(f"dragging {name} from screen {grab} by +{DRAG_PX}px x")
        _drag(grab, (grab[0] + DRAG_PX, grab[1]))
        after = tuple(item.GetPosition() or ())
        _telemetry.info(f"after drag {name}: {before} -> {after}")

        model.ClearSelection2(True)
        model.SaveAs3(os.path.abspath(SCRATCH), 0, 0)
        for iname, iitem in _gtols(model).items():
            _telemetry.info(
                f"post-save {iname}: {tuple(iitem.GetPosition() or ())}"
            )
        adapter.swApp.QuitDoc(str(_read_member(model, "GetTitle")))

        check = await adapter.open_model(str(SCRATCH))
        if not check.is_success:
            raise RuntimeError(f"reopen failed: {check.error}")
        model = adapter.currentModel
        for iname, iitem in _gtols(model).items():
            _telemetry.info(
                f"reopened {iname}: {tuple(iitem.GetPosition() or ())}"
            )
        adapter.swApp.QuitDoc(str(_read_member(model, "GetTitle")))
        SCRATCH.unlink(missing_ok=True)
        _telemetry.success("UI-drag probe complete (scratch removed)")
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
