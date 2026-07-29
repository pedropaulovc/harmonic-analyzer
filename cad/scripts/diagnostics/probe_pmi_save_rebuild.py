r"""Does SaveAs3 rebuild (and revert moved PMI)?  options=0 vs AvoidRebuildOnSave.

Two scratch copies of the built transgear-stub drawing: open, move both gtols
via IGtol::SetPosition (no rebuild), SaveAs3 in place with options=0 (copy A)
or options=8 = swSaveAsOptions_AvoidRebuildOnSave (copy B), reopen, read back.

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/probe_pmi_save_rebuild.py
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

SLDDRW = CAD_ROOT / "out" / "slddrw" / "transgear-stub.SLDDRW"
TARGETS = {"DetailItem2": (0.54, 0.21, 0.0), "DetailItem3": (0.57, 0.23, 0.0)}


def _first_view(draw):
    ddoc = _early_bound(draw, "IDrawingDoc")
    view = _early_bound(ddoc.GetFirstView(), "IView")
    return _early_bound(view.GetNextView(), "IView")


def _gtols(view):
    out = {}
    for raw in tuple(view.GetAnnotations() or ()):
        item = _early_bound(raw, "IAnnotation")
        if bool(item.IsDimXpert()) and int(item.GetType()) == 5:
            out[str(item.GetName())] = item
    return out


async def _one(adapter, scratch: Path, options: int) -> None:
    shutil.copy2(SLDDRW, scratch)
    check = await adapter.open_model(str(scratch))
    if not check.is_success:
        raise RuntimeError(f"open failed: {check.error}")
    draw = adapter.currentModel
    was = bool(draw.GetUserPreferenceToggle(359))
    draw.SetUserPreferenceToggle(359, False)
    _telemetry.info(f"swDetailingDimsFollowDimXpertLayout was {was}, now False")
    for name, item in _gtols(_first_view(draw)).items():
        gtol = _early_bound(item.GetSpecificAnnotation(), "IGtol")
        before = tuple(item.GetPosition() or ())
        target = (TARGETS[name][0], TARGETS[name][1], before[2])  # keep on-plane z
        gtol.SetPosition(*target)
        _telemetry.info(
            f"options={options} moved {name}: "
            f"after={tuple(item.GetPosition() or ())}"
        )
    draw.SaveAs3(os.path.abspath(scratch), 0, options)
    for name, item in _gtols(_first_view(draw)).items():
        _telemetry.info(
            f"options={options} post-save-in-session {name}: "
            f"{tuple(item.GetPosition() or ())}"
        )
    adapter.swApp.QuitDoc(str(_read_member(draw, "GetTitle")))

    check = await adapter.open_model(str(scratch))
    if not check.is_success:
        raise RuntimeError(f"reopen failed: {check.error}")
    draw = adapter.currentModel
    was = bool(draw.GetUserPreferenceToggle(359))
    draw.SetUserPreferenceToggle(359, False)
    _telemetry.info(f"swDetailingDimsFollowDimXpertLayout was {was}, now False")
    for name, item in _gtols(_first_view(draw)).items():
        pos = tuple(item.GetPosition() or ())
        kept = abs(pos[0] - TARGETS[name][0]) < 0.001
        _telemetry.info(
            f"options={options} {name}: {pos} kept_move={kept}"
        )
    adapter.swApp.QuitDoc(str(_read_member(draw, "GetTitle")))
    scratch.unlink(missing_ok=True)


async def main() -> int:
    _telemetry.set_service("diagnostics")
    adapter = PyWin32Adapter({})
    _watchdog.start()
    try:
        await adapter.connect()
        await _one(adapter, SLDDRW.with_name("transgear-stub-save0.SLDDRW"), 0)
        await _one(adapter, SLDDRW.with_name("transgear-stub-save8.SLDDRW"), 8)
        _telemetry.success("save-rebuild probe complete")
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
