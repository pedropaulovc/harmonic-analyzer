r"""Replicate the user's working sheet recipe with pipeline helpers.

Established 2026-07-29: PMI on cylindrical faces is only legal in the
axis-perpendicular (Top) annotation view, and on sheets it displays in a
Top-aligned SECTION view exposing the annotated faces (the collar occludes
the seat/base in a plain top view).  This probe builds that recipe entirely
from pipeline helpers on a COPY of the fresh part:

1. front view (4:1) + horizontal section cut at mid-seat, top-aligned
2. ImportAnnotations(DimXpert) into the section view
3. dumps what landed where, saves the SLDDRW + a B&W PDF, renders a PNG.

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/probe_pmi_section_import.py
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
import _watchdog  # noqa: E402
from _common import CAD_ROOT, _early_bound, _read_member  # noqa: E402
from _drawing_common import create_section_view, model_point_in_view  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter  # noqa: E402

SOURCE = Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else CAD_ROOT / "out" / "sldprt" / "transgear-stub.SLDPRT"
)
SCRATCH_PRT = CAD_ROOT / "out" / "sldprt" / "transgear-stub-secttest.SLDPRT"
SCRATCH_DRW = CAD_ROOT / "out" / "slddrw" / "transgear-stub-secttest.SLDDRW"
OUT_PDF = CAD_ROOT / "out" / "pdf" / "transgear-stub-secttest.pdf"
SEAT_MID_Y = 0.016  # model metres — both gtols attach at this height


def _dump(draw, tag):
    ddoc = _early_bound(draw, "IDrawingDoc")
    view = _early_bound(ddoc.GetFirstView(), "IView")
    while True:
        raw = view.GetNextView()
        if raw is None:
            break
        view = _early_bound(raw, "IView")
        items = []
        for raw_ann in tuple(view.GetAnnotations() or ()):
            item = _early_bound(raw_ann, "IAnnotation")
            if bool(item.IsDimXpert()):
                pos = tuple(round(v, 5) for v in tuple(item.GetPosition() or ()))
                items.append(f"{item.GetName()}:t{item.GetType()}@{pos}")
        _telemetry.info(
            f"{tag}: '{view.GetName2()}' type={int(view.Type)} {items}"
        )


async def main() -> int:
    _telemetry.set_service("diagnostics")
    adapter = PyWin32Adapter({})
    _watchdog.start()
    try:
        await adapter.connect()
        adapter.swApp.CloseAllDocuments(True)
        shutil.copy2(SOURCE, SCRATCH_PRT)
        SCRATCH_DRW.unlink(missing_ok=True)

        from solidworks_mcp.adapters.solidworks.drawing import new_drawing, place_view

        new_drawing(adapter)
        draw = adapter.currentModel
        front = _early_bound(
            place_view(
                adapter, str(SCRATCH_PRT), "*Front", 0.09, 0.15, scale=(4.0, 1.0)
            ),
            "IView",
        )
        cut_x, cut_y = model_point_in_view(
            adapter, front, (0.0, SEAT_MID_Y, 0.0), label="seat mid"
        )
        _telemetry.info(f"seat mid projects to sheet ({cut_x:.4f}, {cut_y:.4f})")
        section = create_section_view(
            adapter,
            front,
            line_start=(cut_x - 0.04, cut_y),
            line_end=(cut_x + 0.04, cut_y),
            view_xy=(0.24, 0.15),
            section_label="C",
            scale=(4, 1),
            label="pmi section",
        )
        section.ImportAnnotations(False, False, True, False, False)
        _dump(draw, "post-import")

        sw = adapter.swApp
        sw.SetUserPreferenceToggle(323, False)  # swPDFExportInColor: B&W sheets
        try:
            draw.SaveAs3(os.path.abspath(OUT_PDF), 0, 0)
        finally:
            sw.SetUserPreferenceToggle(323, True)
        draw.SaveAs3(os.path.abspath(SCRATCH_DRW), 0, 0)
        if not SCRATCH_DRW.exists() or not OUT_PDF.exists():
            raise RuntimeError("save produced no artefacts")
        adapter.swApp.QuitDoc(str(_read_member(draw, "GetTitle")))
        _telemetry.success(f"section-import probe complete: {OUT_PDF}")
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
