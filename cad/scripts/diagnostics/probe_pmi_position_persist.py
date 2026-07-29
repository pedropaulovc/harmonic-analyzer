r"""Does a post-rebuild sheet-side PMI move survive save + reopen + rebuild?

Sheet moves of imported gtols revert on EditRebuild3 in the same session.
This probe orders the ops the way the build could: rebuild FIRST, then move,
then save to a scratch copy, reopen, read back, rebuild again, read back.

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/probe_pmi_position_persist.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
import _watchdog  # noqa: E402
from _common import CAD_ROOT, _early_bound, _read_member  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter  # noqa: E402

SLDDRW = CAD_ROOT / "out" / "slddrw" / "transgear-stub.SLDDRW"
SCRATCH = CAD_ROOT / "out" / "slddrw" / "transgear-stub-posprobe.SLDDRW"
TARGETS = {"DetailItem2": (0.54, 0.21, 0.0), "DetailItem3": (0.57, 0.23, 0.0)}


def _first_view(draw):
    ddoc = _early_bound(draw, "IDrawingDoc")
    view = _early_bound(ddoc.GetFirstView(), "IView")
    return _early_bound(view.GetNextView(), "IView")


def _pmi(view):
    out = {}
    for raw in tuple(view.GetAnnotations() or ()):
        item = _early_bound(raw, "IAnnotation")
        if bool(item.IsDimXpert()):
            out[str(item.GetName())] = item
    return out


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
        draw.ForceRebuild3(False)
        draw.EditRebuild3()
        for name, item in _pmi(_first_view(draw)).items():
            target = TARGETS.get(name)
            if target is None:
                continue
            gtol = _early_bound(item.GetSpecificAnnotation(), "IGtol")
            gtol.SetPosition(*target)
            item.Color = 0x000000
            _telemetry.info(
                f"moved {name}: after={tuple(item.GetPosition() or ())} target={target}"
            )
        saved = await adapter.save_file(str(SCRATCH))
        if not saved.is_success:
            raise RuntimeError(f"save failed: {saved.error}")
        adapter.swApp.QuitDoc(str(_read_member(draw, "GetTitle")))

        check = await adapter.open_model(str(SCRATCH))
        if not check.is_success:
            raise RuntimeError(f"reopen failed: {check.error}")
        draw = adapter.currentModel
        for name, item in _pmi(_first_view(draw)).items():
            _telemetry.info(
                f"reopened {name}: {tuple(item.GetPosition() or ())} "
                f"color={int(item.Color):#08x}"
            )
        draw.ForceRebuild3(False)
        draw.EditRebuild3()
        for name, item in _pmi(_first_view(draw)).items():
            _telemetry.info(
                f"post-rebuild {name}: {tuple(item.GetPosition() or ())}"
            )
        adapter.swApp.QuitDoc(str(_read_member(draw, "GetTitle")))
        SCRATCH.unlink(missing_ok=True)
        _telemetry.success("persist probe complete (scratch copy removed)")
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
