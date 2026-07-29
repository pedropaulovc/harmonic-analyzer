r"""Does moving a DimXpert display annotation IN THE PART persist to sheets?

Sheet-side moves of imported PMI revert on rebuild (the sheet position is a
projection of the part-space annotation position).  This probe opens the built
transgear-stub PART, moves the two gtol frames apart in part space, saves,
then imports into a scratch drawing view and reads where they landed.

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/probe_pmi_part_position.py
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
        index = 0
        for raw_view in tuple(ext.AnnotationViews or ()):
            aview = _early_bound(raw_view, "IAnnotationView")
            if bool(aview.UnassignedView):
                continue
            for raw in tuple(aview.GetAnnotations2(True, True) or ()):
                item = _early_bound(raw, "IAnnotation")
                kind = int(item.GetType())
                before = tuple(item.GetPosition() or ())
                # spread annotations: gtols right of the part (+x), datum left
                target = (
                    (0.030 + 0.010 * index) if kind == 5 else -0.030,
                    0.010 * index,
                    0.0,
                )
                if kind == 5:
                    gtol = _early_bound(item.GetSpecificAnnotation(), "IGtol")
                    gtol.SetPosition(*target)
                    how = "IGtol.SetPosition"
                else:
                    how = f"SetPosition2={bool(item.SetPosition2(*target))}"
                after = tuple(item.GetPosition() or ())
                _telemetry.info(
                    f"part-space {item.GetName()} kind={kind}: before={before} "
                    f"{how} after={after} target={target}"
                )
                index += 1
        model.EditRebuild3()
        for raw_view in tuple(ext.AnnotationViews or ()):
            aview = _early_bound(raw_view, "IAnnotationView")
            if bool(aview.UnassignedView):
                continue
            for raw in tuple(aview.GetAnnotations2(True, True) or ()):
                item = _early_bound(raw, "IAnnotation")
                _telemetry.info(
                    f"post-rebuild {item.GetName()}: "
                    f"{tuple(item.GetPosition() or ())}"
                )
        saved = await adapter.save_file(str(SOURCE))
        if not saved.is_success:
            raise RuntimeError(f"save failed: {saved.error}")
        adapter.swApp.QuitDoc(str(_read_member(model, "GetTitle")))

        from solidworks_mcp.adapters.solidworks.drawing import new_drawing, place_view

        new_drawing(adapter)
        view = _early_bound(
            place_view(adapter, str(SOURCE), "*Front", 0.15, 0.15, scale=(4.0, 1.0)),
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
        draw_title = str(_read_member(adapter.currentModel, "GetTitle"))
        adapter.swApp.QuitDoc(draw_title)
        _telemetry.success("probe complete (part modified + saved; rebuild part task to restore)")
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
