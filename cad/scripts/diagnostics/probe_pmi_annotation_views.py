r"""Map the built transgear-stub's annotation views and their annotations.

Which annotation view (feature name) does each DimXpert annotation live in?
A datum stuck in "Unassigned Items" never imports into any drawing view —
this names the view each annotation must move to.

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/probe_pmi_annotation_views.py
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
_TYPE_NAMES = {2: "datum", 5: "gtol", 4: "dim", 6: "note"}


async def main() -> int:
    _telemetry.set_service("diagnostics")
    adapter = PyWin32Adapter({})
    _watchdog.start()
    try:
        await adapter.connect()
        check = await adapter.open_model(str(SOURCE))
        if not check.is_success:
            raise RuntimeError(f"open failed: {check.error}")
        model = adapter.currentModel
        ext = model.Extension
        views = tuple(ext.AnnotationViews or ())
        _telemetry.info(f"annotation view count: {len(views)}")
        for raw in views:
            view = _early_bound(raw, "IAnnotationView")
            feature = _early_bound(raw, "IFeature")
            name = str(_read_member(feature, "Name"))
            unassigned = bool(view.UnassignedView)
            annotations = tuple(view.GetAnnotations2(False, True) or ())
            listed = []
            for item in annotations:
                item = _early_bound(item, "IAnnotation")
                kind = int(item.GetType())
                listed.append(f"{_TYPE_NAMES.get(kind, kind)}:{item.GetName()}")
            _telemetry.info(
                f"view {name!r} unassigned={unassigned} "
                f"count={view.AnnotationCount} annotations={listed!r}"
            )
        adapter.swApp.QuitDoc(str(_read_member(model, "GetTitle")))
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
