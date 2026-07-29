r"""Do part-space DimXpert display moves survive the part's SAVE (no rebuild)?

Earlier probe rebuilt before saving (which reverts moves).  This one: open a
scratch copy of the built part, move the two gtols apart via IGtol::SetPosition
(readback), save WITHOUT rebuilding, read in-session, reopen, read again.
If the moves persist, import into a scratch drawing view to see the projection.

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/probe_pmi_part_save.py
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
SCRATCH = CAD_ROOT / "out" / "sldprt" / "transgear-stub-pmiprobe.SLDPRT"
TARGETS = {"DetailItem2": (0.030, 0.010, 0.0), "DetailItem3": (0.040, 0.020, 0.0)}


def _pmi_gtols(model):
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
        for name, item in _pmi_gtols(model).items():
            gtol = _early_bound(item.GetSpecificAnnotation(), "IGtol")
            before = tuple(item.GetPosition() or ())
            target = (TARGETS[name][0], TARGETS[name][1], before[2])  # on-plane z
            gtol.SetPosition(*target)
            _telemetry.info(
                f"moved {name}: after={tuple(item.GetPosition() or ())}"
            )
        model.SaveAs3(os.path.abspath(SCRATCH), 0, 0)
        for name, item in _pmi_gtols(model).items():
            _telemetry.info(
                f"post-save-in-session {name}: {tuple(item.GetPosition() or ())}"
            )
        adapter.swApp.QuitDoc(str(_read_member(model, "GetTitle")))

        check = await adapter.open_model(str(SCRATCH))
        if not check.is_success:
            raise RuntimeError(f"reopen failed: {check.error}")
        model = adapter.currentModel
        for name, item in _pmi_gtols(model).items():
            _telemetry.info(
                f"reopened {name}: {tuple(item.GetPosition() or ())}"
            )
        adapter.swApp.QuitDoc(str(_read_member(model, "GetTitle")))

        from solidworks_mcp.adapters.solidworks.drawing import new_drawing, place_view

        new_drawing(adapter)
        view = _early_bound(
            place_view(adapter, str(SCRATCH), "*Front", 0.15, 0.15, scale=(4.0, 1.0)),
            "IView",
        )
        view.ImportAnnotations(False, False, True, False, False)
        for raw in tuple(view.GetAnnotations() or ()):
            item = _early_bound(raw, "IAnnotation")
            if bool(item.IsDimXpert()):
                _telemetry.info(
                    f"sheet {item.GetName()} kind={item.GetType()}: "
                    f"{tuple(item.GetPosition() or ())}"
                )
        adapter.swApp.QuitDoc(str(_read_member(adapter.currentModel, "GetTitle")))
        SCRATCH.unlink(missing_ok=True)
        _telemetry.success("part-save probe complete (scratch removed)")
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
