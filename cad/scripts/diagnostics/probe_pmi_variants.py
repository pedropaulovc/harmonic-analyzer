r"""Which move recipe makes a part-space PMI move survive save?

Three fresh scratch copies of the clean built part, one scenario each:

  select  — IAnnotation::Select3 first, then IGtol::SetPosition (z kept)
  double  — IGtol::SetPosition applied twice in a row (z kept)
  zoff    — IGtol::SetPosition with z pushed 5 mm off-plane

Each scenario: move both gtols +20 mm x, save (no rebuild), read back.

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/probe_pmi_variants.py
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


def _gtols(model, activate=False):
    out = {}
    for raw_view in tuple(model.Extension.AnnotationViews or ()):
        aview = _early_bound(raw_view, "IAnnotationView")
        if bool(aview.UnassignedView):
            continue
        annotations = tuple(aview.GetAnnotations2(True, True) or ())
        if activate and annotations:
            ok = aview.Activate()
            _telemetry.info(f"annotation view activate -> {ok}")
        for raw in annotations:
            item = _early_bound(raw, "IAnnotation")
            if int(item.GetType()) == 5:
                out[str(item.GetName())] = item
    return out


async def _scenario(adapter, tag: str) -> None:
    scratch = SOURCE.with_name(f"transgear-stub-{tag}.SLDPRT")
    shutil.copy2(SOURCE, scratch)
    check = await adapter.open_model(str(scratch))
    if not check.is_success:
        raise RuntimeError(f"{tag}: open failed: {check.error}")
    model = adapter.currentModel
    for name, item in _gtols(model, activate=(tag == "activate")).items():
        before = tuple(item.GetPosition() or ())
        z = before[2] + (0.005 if tag == "zoff" else 0.0)
        target = (before[0] + 0.020, before[1], z)
        gtol = _early_bound(item.GetSpecificAnnotation(), "IGtol")
        if tag == "select":
            item.Select3(False, None)
        gtol.SetPosition(*target)
        if tag == "double":
            gtol.SetPosition(*target)
        _telemetry.info(
            f"{tag} asked {name}: {target} -> {tuple(item.GetPosition() or ())}"
        )
    model.ClearSelection2(True)
    model.SaveAs3(os.path.abspath(scratch), 0, 0)
    for name, item in _gtols(model).items():
        _telemetry.info(
            f"{tag} post-save {name}: {tuple(item.GetPosition() or ())}"
        )
    adapter.swApp.QuitDoc(str(_read_member(model, "GetTitle")))
    scratch.unlink(missing_ok=True)


async def main() -> int:
    _telemetry.set_service("diagnostics")
    adapter = PyWin32Adapter({})
    _watchdog.start()
    try:
        await adapter.connect()
        for tag in ("activate",):
            await _scenario(adapter, tag)
        _telemetry.success("variant probe complete")
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
