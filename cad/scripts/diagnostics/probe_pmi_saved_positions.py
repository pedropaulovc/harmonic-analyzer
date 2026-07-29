r"""Read the saved transgear-stub drawing's PMI positions + colors (read-only).

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/probe_pmi_saved_positions.py
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
        view = _early_bound(ddoc.GetFirstView(), "IView")
        while True:
            raw = view.GetNextView()
            if raw is None:
                break
            view = _early_bound(raw, "IView")
            for item in tuple(view.GetAnnotations() or ()):
                item = _early_bound(item, "IAnnotation")
                if not bool(item.IsDimXpert()):
                    continue
                _telemetry.info(
                    f"view {view.GetName2()}: {item.GetName()} "
                    f"kind={item.GetType()} pos={tuple(item.GetPosition() or ())} "
                    f"color={int(item.Color):#08x}"
                )
        adapter.swApp.QuitDoc(str(_read_member(draw, "GetTitle")))
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
