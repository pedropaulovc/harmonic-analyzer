r"""Recreate the sheet-drag scratch pair for a manual persistence test.

Copies the built part to transgear-stub-sheetdrag.SLDPRT, builds a fresh
drawing (front + bottom views, DimXpert annotations imported) referencing
THAT copy — so a manual drag + Ctrl+S on the sheet can never contaminate the
pipeline's transgear-stub artefacts — saves it as
transgear-stub-sheetdrag.SLDDRW and leaves it open, maximized and
foregrounded for the user.

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/make_sheetdrag_scratch.py
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import win32con  # noqa: E402
import win32gui  # noqa: E402

import _telemetry  # noqa: E402
import _watchdog  # noqa: E402
from _common import CAD_ROOT, _early_bound  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter  # noqa: E402

SOURCE = CAD_ROOT / "out" / "sldprt" / "transgear-stub.SLDPRT"
SCRATCH_PRT = CAD_ROOT / "out" / "sldprt" / "transgear-stub-sheetdrag.SLDPRT"
SCRATCH_DRW = CAD_ROOT / "out" / "slddrw" / "transgear-stub-sheetdrag.SLDDRW"


def _foreground_solidworks():
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
        _telemetry.warn("no visible SOLIDWORKS main window to foreground")
        return
    win32gui.ShowWindow(hwnds[0], win32con.SW_SHOWMAXIMIZED)
    win32gui.SetForegroundWindow(hwnds[0])


async def main() -> int:
    _telemetry.set_service("diagnostics")
    adapter = PyWin32Adapter({})
    _watchdog.start()
    try:
        await adapter.connect()
        adapter.swApp.CloseAllDocuments(True)
        SCRATCH_DRW.unlink(missing_ok=True)
        shutil.copy2(SOURCE, SCRATCH_PRT)
        _telemetry.info(f"part copied -> {SCRATCH_PRT.name}")

        from solidworks_mcp.adapters.solidworks.drawing import new_drawing, place_view

        new_drawing(adapter)
        draw = adapter.currentModel
        for orientation, x in (("*Front", 0.12), ("*Bottom", 0.30)):
            view = _early_bound(
                place_view(
                    adapter, str(SCRATCH_PRT), orientation, x, 0.17, scale=(4.0, 1.0)
                ),
                "IView",
            )
            view.ImportAnnotations(False, False, True, False, False)
            for raw in tuple(view.GetAnnotations() or ()):
                item = _early_bound(raw, "IAnnotation")
                if bool(item.IsDimXpert()):
                    _telemetry.info(
                        f"sheet {view.GetName2()}: {item.GetName()} "
                        f"kind={item.GetType()} {tuple(item.GetPosition() or ())}"
                    )
        # SaveAs3 returns False on mere warnings (e.g. the referenced scratch
        # part getting re-saved alongside), so gate on the file landing instead.
        ok = bool(draw.SaveAs3(os.path.abspath(SCRATCH_DRW), 0, 0))
        if not SCRATCH_DRW.exists():
            raise RuntimeError(f"save wrote nothing: {SCRATCH_DRW}")
        if not ok:
            _telemetry.warn("SaveAs3 reported False but the file was written")
        draw.ViewZoomtofit2()
        draw.GraphicsRedraw2()
        _foreground_solidworks()
        _telemetry.success(
            f"{SCRATCH_DRW.name} ready and open — drag the FCFs, Ctrl+S, report back"
        )
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
