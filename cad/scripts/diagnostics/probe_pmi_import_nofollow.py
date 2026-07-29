r"""Import PMI with swDetailingDimsFollowDimXpertLayout OFF, then move + save.

Fresh scratch drawing: disable the follow-DimXpert-layout detailing toggle
(359) BEFORE placing the view and importing, then move the gtols, save,
reopen, read back.

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/probe_pmi_import_nofollow.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
import _watchdog  # noqa: E402
from _common import CAD_ROOT, _early_bound, _read_member  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter  # noqa: E402

SOURCE = CAD_ROOT / "out" / "sldprt" / "transgear-stub.SLDPRT"
SCRATCH = CAD_ROOT / "out" / "slddrw" / "transgear-stub-nofollow.SLDDRW"
TARGETS = {"DetailItem2": (0.24, 0.11), "DetailItem3": (0.24, 0.13)}


def _pmi(view):
    out = {}
    for raw in tuple(view.GetAnnotations() or ()):
        item = _early_bound(raw, "IAnnotation")
        if bool(item.IsDimXpert()):
            out[str(item.GetName())] = item
    return out


async def main() -> int:
    _telemetry.set_service("diagnostics")
    adapter = PyWin32Adapter({})
    _watchdog.start()
    try:
        await adapter.connect()
        from solidworks_mcp.adapters.solidworks.drawing import new_drawing, place_view

        new_drawing(adapter)
        draw = adapter.currentModel
        ext = draw.Extension
        ok = ext.SetUserPreferenceToggle(359, 0, False)
        _telemetry.info(
            f"follow-layout set ok={ok}, now "
            f"{bool(ext.GetUserPreferenceToggle(359, 0))}"
        )
        view = _early_bound(
            place_view(adapter, str(SOURCE), "*Front", 0.15, 0.15, scale=(4.0, 1.0)),
            "IView",
        )
        view.ImportAnnotations(False, False, True, False, False)
        for name, item in _pmi(view).items():
            if int(item.GetType()) != 5:
                continue
            before = tuple(item.GetPosition() or ())
            target = (*TARGETS[name], before[2])
            _early_bound(item.GetSpecificAnnotation(), "IGtol").SetPosition(*target)
            _telemetry.info(
                f"moved {name}: {before} -> {tuple(item.GetPosition() or ())}"
            )
        draw.SaveAs3(os.path.abspath(SCRATCH), 0, 0)
        for name, item in _pmi(view).items():
            _telemetry.info(
                f"post-save {name}: {tuple(item.GetPosition() or ())}"
            )
        adapter.swApp.QuitDoc(str(_read_member(draw, "GetTitle")))

        check = await adapter.open_model(str(SCRATCH))
        if not check.is_success:
            raise RuntimeError(f"reopen failed: {check.error}")
        draw = adapter.currentModel
        ddoc = _early_bound(draw, "IDrawingDoc")
        view = _early_bound(ddoc.GetFirstView(), "IView")
        view = _early_bound(view.GetNextView(), "IView")
        for name, item in _pmi(view).items():
            _telemetry.info(
                f"reopened {name}: {tuple(item.GetPosition() or ())}"
            )
        adapter.swApp.QuitDoc(str(_read_member(draw, "GetTitle")))
        SCRATCH.unlink(missing_ok=True)
        _telemetry.success("no-follow import probe complete")
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
