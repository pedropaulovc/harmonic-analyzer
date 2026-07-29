r"""Map which part-space axes an imported-PMI move can persist along.

Clean scratch copy of the built part: log before positions, move one gtol
pure-x, the other pure-y (z always preserved), move the datum with preserved
z, save WITHOUT rebuild, read, reopen, read, then import into a scratch
drawing view and read the sheet projections.

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/probe_pmi_constraints.py
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
SCRATCH = CAD_ROOT / "out" / "sldprt" / "transgear-stub-constraints.SLDPRT"


def _pmi(model):
    out = {}
    for raw_view in tuple(model.Extension.AnnotationViews or ()):
        aview = _early_bound(raw_view, "IAnnotationView")
        if bool(aview.UnassignedView):
            continue
        for raw in tuple(aview.GetAnnotations2(True, True) or ()):
            item = _early_bound(raw, "IAnnotation")
            out[str(item.GetName())] = item
    return out


def _log_all(model, tag):
    for name, item in _pmi(model).items():
        _telemetry.info(
            f"{tag} {name} kind={item.GetType()}: "
            f"{tuple(item.GetPosition() or ())}"
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
        _log_all(model, "before")
        items = _pmi(model)
        for name, item in items.items():
            kind = int(item.GetType())
            before = tuple(item.GetPosition() or ())
            if kind == 5 and name == "DetailItem2":
                target = (before[0] + 0.020, before[1], before[2])  # pure +x
            elif kind == 5:
                target = (before[0], before[1] + 0.015, before[2])  # pure +y
            else:
                target = (before[0] + 0.010, before[1] + 0.010, before[2])
            if kind == 5:
                _early_bound(item.GetSpecificAnnotation(), "IGtol").SetPosition(*target)
            else:
                item.SetPosition2(*target)
            _telemetry.info(
                f"asked {name}: {target} -> got {tuple(item.GetPosition() or ())}"
            )
        model.SaveAs3(os.path.abspath(SCRATCH), 0, 0)
        _log_all(model, "post-save")
        adapter.swApp.QuitDoc(str(_read_member(model, "GetTitle")))

        check = await adapter.open_model(str(SCRATCH))
        if not check.is_success:
            raise RuntimeError(f"reopen failed: {check.error}")
        model = adapter.currentModel
        _log_all(model, "reopened")
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
        _telemetry.success("constraint probe complete (scratch removed)")
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
