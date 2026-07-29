r"""Which standard drawing view does each DimXpert annotation land in?

Empirical routing map for the PMI sheet-import leg: opens the BUILT
transgear-stub (which carries datum A on the base cylinder + two gtols),
creates a scratch drawing, places every standard orientation, imports
DimXpert into each, and logs what landed where.  Discards without saving.

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/probe_pmi_view_routing.py
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

SOURCE = CAD_ROOT / "out" / "sldprt" / "transgear-stub.SLDPRT"
ORIENTATIONS = ("*Front", "*Back", "*Left", "*Right", "*Top", "*Bottom", "*Isometric")
_TYPE_NAMES = {2: "datum", 5: "gtol", 4: "dim", 6: "note"}


async def main() -> int:
    _telemetry.set_service("diagnostics")
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    adapter = PyWin32Adapter({})
    _watchdog.start()
    try:
        await adapter.connect()
        from solidworks_mcp.adapters.solidworks.drawing import new_drawing, place_view

        new_drawing(adapter)
        for index, orientation in enumerate(ORIENTATIONS):
            x = 0.06 + (index % 4) * 0.10
            y = 0.20 if index < 4 else 0.08
            view = _early_bound(
                place_view(adapter, str(SOURCE), orientation, x, y, scale=(1.0, 1.0)),
                "IView",
            )
            before = len(tuple(view.GetAnnotations() or ()))
            view.ImportAnnotations(False, False, True, False, False)
            landed = []
            for item in tuple(view.GetAnnotations() or ()):
                item = _early_bound(item, "IAnnotation")
                kind = int(item.GetType())
                landed.append(
                    f"{_TYPE_NAMES.get(kind, kind)}:{item.GetName()}"
                )
            _telemetry.info(
                f"{orientation}: before={before} landed={landed!r}"
            )
        title = str(_read_member(adapter.currentModel, "GetTitle"))
        adapter.swApp.QuitDoc(title)
        _telemetry.success(f"scratch drawing discarded: {title}")
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
