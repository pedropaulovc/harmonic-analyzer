r"""Do SetPosition2 moves on imported DimXpert annotations persist?

Opens the built transgear-stub drawing, reads each PMI annotation's position,
moves it to a distinct target, reads back, rebuilds, reads back again, and
also tries the Color override.  Discards without saving.

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/probe_pmi_position.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
import _watchdog  # noqa: E402
from _common import CAD_ROOT, _early_bound, _read_member  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter  # noqa: E402

SLDDRW = CAD_ROOT / "out" / "slddrw" / "transgear-stub.SLDDRW"
_BLACK = 0x000000


async def main() -> int:
    _telemetry.set_service("diagnostics")
    adapter = PyWin32Adapter({})
    _watchdog.start()
    try:
        await adapter.connect()
        check = await adapter.open_model(str(SLDDRW))
        if not check.is_success:
            raise RuntimeError(f"open failed: {check.error}")
        draw = adapter.currentModel
        ddoc = _early_bound(draw, "IDrawingDoc")
        view = _early_bound(ddoc.GetFirstView(), "IView")  # sheet
        view = _early_bound(view.GetNextView(), "IView")  # first real view
        targets = {}
        moved = []
        for index, raw in enumerate(tuple(view.GetAnnotations() or ())):
            item = _early_bound(raw, "IAnnotation")
            if not bool(item.IsDimXpert()):
                continue
            name = str(item.GetName())
            before = tuple(item.GetPosition() or ())
            target = (0.30 + 0.03 * index, 0.05 + 0.02 * index, 0.0)
            kind = int(item.GetType())
            if kind == 5:  # gtol: type-specific setter
                gtol = _early_bound(item.GetSpecificAnnotation(), "IGtol")
                gtol.SetPosition(*target)
                ok = "IGtol.SetPosition"
            else:  # datum: try the older IAnnotation::SetPosition
                ok = f"SetPosition={bool(item.SetPosition(*target))}"
            after = tuple(item.GetPosition() or ())
            color_ok = None
            try:
                item.Color = _BLACK
                color_ok = int(item.Color) == _BLACK
            except Exception as error:  # noqa: BLE001
                color_ok = f"error: {error}"
            _telemetry.info(
                f"{name}: before={before} set_ok={ok} after={after} "
                f"target={target[:2]} color_black={color_ok}"
            )
            targets[name] = target
            moved.append(item)
        draw.EditRebuild3()
        for item in moved:
            name = str(item.GetName())
            final = tuple(item.GetPosition() or ())
            drift = (
                abs(final[0] - targets[name][0]),
                abs(final[1] - targets[name][1]),
            )
            _telemetry.info(
                f"{name}: post-rebuild={final} drift_from_target={drift}"
            )
        adapter.swApp.QuitDoc(str(_read_member(draw, "GetTitle")))
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
