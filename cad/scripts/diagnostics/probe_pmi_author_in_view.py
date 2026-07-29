r"""Author PMI with a drawing-aligned annotation view ACTIVE from the start.

Post-hoc MoveAnnotations reverts on save like every other mutation.  This
probe instead wipes the scratch part's DimXpert scheme, inserts + activates a
*Front-aligned annotation view, re-authors the spec's PMI (datum + controls),
saves, reopens, reports which annotation views hold the annotations, and
imports into a scratch drawing to check routing.

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/probe_pmi_author_in_view.py
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
from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter  # noqa: E402

SOURCE = CAD_ROOT / "out" / "sldprt" / "transgear-stub.SLDPRT"
SCRATCH = CAD_ROOT / "out" / "sldprt" / "transgear-stub-authorview.SLDPRT"
_FRONT_VIEW = 1  # swStandardViews_e.swFrontView


def _report_views(model, tag):
    for raw_view in tuple(model.Extension.AnnotationViews or ()):
        aview = _early_bound(raw_view, "IAnnotationView")
        listed = []
        for raw in tuple(aview.GetAnnotations2(False, True) or ()):
            item = _early_bound(raw, "IAnnotation")
            listed.append(f"{item.GetName()}:t{item.GetType()}")
        if listed or not bool(aview.UnassignedView):
            _telemetry.info(
                f"{tag}: view unassigned={bool(aview.UnassignedView)} "
                f"n={aview.AnnotationCount} {listed}"
            )


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
        config = _read_member(_read_member(model, "GetActiveConfiguration"), "Name")
        manager = ext.DimXpertManager(str(config), True)
        dim_part = _early_bound(
            _read_member(manager, "DimXpertPart"), "IDimXpertPart"
        )
        dim_part.DeleteAllTolerances()
        _telemetry.info("existing DimXpert tolerances deleted")

        front_view = _early_bound(
            ext.InsertAnnotationView(_FRONT_VIEW, None, False, None, 0),
            "IAnnotationView",
        )
        _telemetry.info(f"front annotation view activate -> {front_view.Activate()}")

        from _part_pmi import author_part_pmi
        from transgear_stub_spec import GEOMETRIC_CONTROLS, PART_DATUMS

        await author_part_pmi(
            adapter, datums=PART_DATUMS, controls=GEOMETRIC_CONTROLS
        )
        _report_views(model, "post-author")
        model.SaveAs3(os.path.abspath(SCRATCH), 0, 0)
        adapter.swApp.QuitDoc(str(_read_member(model, "GetTitle")))

        check = await adapter.open_model(str(SCRATCH))
        if not check.is_success:
            raise RuntimeError(f"reopen failed: {check.error}")
        model = adapter.currentModel
        _report_views(model, "reopened")
        adapter.swApp.QuitDoc(str(_read_member(model, "GetTitle")))

        from solidworks_mcp.adapters.solidworks.drawing import new_drawing, place_view

        new_drawing(adapter)
        draw = adapter.currentModel
        for orientation, x in (("*Front", 0.09), ("*Bottom", 0.20)):
            view = _early_bound(
                place_view(adapter, str(SCRATCH), orientation, x, 0.13, scale=(4.0, 1.0)),
                "IView",
            )
            view.ImportAnnotations(False, False, True, False, False)
            landed = [
                f"{_early_bound(raw, 'IAnnotation').GetName()}:"
                f"t{_early_bound(raw, 'IAnnotation').GetType()}"
                for raw in tuple(view.GetAnnotations() or ())
                if bool(_early_bound(raw, "IAnnotation").IsDimXpert())
            ]
            _telemetry.info(f"sheet {orientation}: {landed}")
        adapter.swApp.QuitDoc(str(_read_member(adapter.currentModel, "GetTitle")))
        SCRATCH.unlink(missing_ok=True)
        _telemetry.success("author-in-view probe complete")
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
