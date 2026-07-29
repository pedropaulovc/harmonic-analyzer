r"""Move PMI into drawing-aligned annotation views, then import and render.

The FCFs' auto-assigned annotation planes come from the selected cylinder
faces (arbitrary rotation about the axis), so nothing matches the drawing's
front/end orientations — suspected root of the rotated datum glyph and the
co-located frames on sheets.  This probe, on a scratch copy of the built part:

1. inserts explicit annotation views for *Front (gtols) and *Bottom (datum)
   via IModelDocExtension::InsertAnnotationView(swStandardViews_e...)
2. MoveAnnotations the gtols / datum into them
3. saves, imports into a scratch drawing (front + bottom views), exports a
   black-and-white PDF, and crops the result for inspection.

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/probe_pmi_aligned_views.py
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pythoncom  # noqa: E402
from win32com.client import VARIANT  # noqa: E402

import _telemetry  # noqa: E402
import _watchdog  # noqa: E402
from _common import CAD_ROOT, _early_bound, _read_member  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter  # noqa: E402

SOURCE = CAD_ROOT / "out" / "sldprt" / "transgear-stub.SLDPRT"
SCRATCH = CAD_ROOT / "out" / "sldprt" / "transgear-stub-aligned.SLDPRT"
SCRATCH_DRW = CAD_ROOT / "out" / "slddrw" / "transgear-stub-aligned.SLDDRW"
OUT_PDF = CAD_ROOT / "out" / "pdf" / "transgear-stub-aligned.pdf"
_FRONT_VIEW = 1  # swStandardViews_e.swFrontView
_BOTTOM_VIEW = 6  # swStandardViews_e.swBottomView


def _pmi_by_kind(model):
    gtols, datums = [], []
    for raw_view in tuple(model.Extension.AnnotationViews or ()):
        aview = _early_bound(raw_view, "IAnnotationView")
        for raw in tuple(aview.GetAnnotations2(True, True) or ()):
            item = _early_bound(raw, "IAnnotation")
            (gtols if int(item.GetType()) == 5 else datums).append(item)
    return gtols, datums


def _move(aview, items):
    payload = VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH,
        [getattr(item, "_oleobj_", item) for item in items],
    )
    return bool(aview.MoveAnnotations(payload))


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
        ext = model.Extension
        front_view = _early_bound(
            ext.InsertAnnotationView(_FRONT_VIEW, None, False, None, 0),
            "IAnnotationView",
        )
        bottom_view = _early_bound(
            ext.InsertAnnotationView(_BOTTOM_VIEW, None, False, None, 0),
            "IAnnotationView",
        )
        _telemetry.info("annotation views inserted (front, bottom)")
        gtols, datums = _pmi_by_kind(model)
        _telemetry.info(
            f"move gtols->front: {_move(front_view, gtols)}; "
            f"datum->bottom: {_move(bottom_view, datums)}"
        )
        for item in gtols + datums:
            _telemetry.info(
                f"{item.GetName()} pos now {tuple(item.GetPosition() or ())}"
            )
        model.SaveAs3(os.path.abspath(SCRATCH), 0, 0)
        adapter.swApp.QuitDoc(str(_read_member(model, "GetTitle")))

        from solidworks_mcp.adapters.solidworks.drawing import new_drawing, place_view

        sw = adapter.swApp
        sw.SetUserPreferenceToggle(323, False)  # swPDFExportInColor
        try:
            new_drawing(adapter)
            draw = adapter.currentModel
            front = _early_bound(
                place_view(adapter, str(SCRATCH), "*Front", 0.12, 0.17, scale=(4.0, 1.0)),
                "IView",
            )
            bottom = _early_bound(
                place_view(adapter, str(SCRATCH), "*Bottom", 0.30, 0.17, scale=(4.0, 1.0)),
                "IView",
            )
            for view in (front, bottom):
                view.ImportAnnotations(False, False, True, False, False)
                for raw in tuple(view.GetAnnotations() or ()):
                    item = _early_bound(raw, "IAnnotation")
                    if bool(item.IsDimXpert()):
                        _telemetry.info(
                            f"sheet {view.GetName2()}: {item.GetName()} "
                            f"kind={item.GetType()} "
                            f"{tuple(item.GetPosition() or ())}"
                        )
            draw.SaveAs3(os.path.abspath(OUT_PDF), 0, 0)
            draw.SaveAs3(os.path.abspath(SCRATCH_DRW), 0, 0)
            adapter.swApp.QuitDoc(str(_read_member(draw, "GetTitle")))
        finally:
            sw.SetUserPreferenceToggle(323, True)
        _telemetry.success("aligned-views probe complete")
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
