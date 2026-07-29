r"""Inspect the user's hand-normalized sheetdrag pair + test COM placement.

The user empirically established that FCFs on cylindrical faces are only legal
in an annotation view PERPENDICULAR to the face's axis (Top here), fixed the
part by right-click > Select Annotation View > Top, and rebuilt the drawing
with a standard 3-view + section view.  This probe, on COPIES (their files
stay untouched):

1. PART: dumps every annotation view (rotation matrix -> orientation guess,
   unassigned flag, DimXpert members + positions).
2. DRAWING: dumps every sheet view (name, type) and its DimXpert annotations.
3. DRAWING: moves one gtol via IGtol.SetPosition, saves, reopens, reads back —
   does programmatic placement persist now that the state is legal?

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/probe_pmi_fixed_state.py
"""

from __future__ import annotations

import asyncio
import math
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
import _watchdog  # noqa: E402
from _common import CAD_ROOT, _early_bound, _read_member  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter  # noqa: E402

SRC_PRT = CAD_ROOT / "out" / "sldprt" / "transgear-stub-sheetdrag.SLDPRT"
SRC_DRW = CAD_ROOT / "out" / "slddrw" / "transgear-stub-sheetdrag.SLDDRW"
CPY_PRT = CAD_ROOT / "out" / "sldprt" / "transgear-stub-inspect.SLDPRT"
CPY_DRW = CAD_ROOT / "out" / "slddrw" / "transgear-stub-inspect.SLDDRW"

_AXES = {
    (0, 0, 1): "Front-like (+Z normal)",
    (0, 0, -1): "Back-like (-Z normal)",
    (0, 1, 0): "Top-like (+Y normal)",
    (0, -1, 0): "Bottom-like (-Y normal)",
    (1, 0, 0): "Right-like (+X normal)",
    (-1, 0, 0): "Left-like (-X normal)",
}


def _orientation(aview) -> str:
    raw = tuple(aview.GetViewRotation() or ())
    if len(raw) != 9:
        return f"rotation={raw!r}"
    # rows are the view axes in model space; the third row is the view normal
    normal = raw[6:9]
    for axis, name in _AXES.items():
        if all(math.isclose(n, a, abs_tol=1e-6) for n, a in zip(normal, axis)):
            return name
    return f"normal={tuple(round(n, 4) for n in normal)}"


def _dump_part_views(model, tag):
    for raw_view in tuple(model.Extension.AnnotationViews or ()):
        aview = _early_bound(raw_view, "IAnnotationView")
        members = []
        for raw in tuple(aview.GetAnnotations2(False, True) or ()):
            item = _early_bound(raw, "IAnnotation")
            members.append(
                f"{item.GetName()}:t{item.GetType()}"
                f"@{tuple(round(v, 5) for v in tuple(item.GetPosition() or ()))}"
            )
        if members or not bool(aview.UnassignedView):
            _telemetry.info(
                f"{tag}: [{_orientation(aview)}] "
                f"unassigned={bool(aview.UnassignedView)} "
                f"shown={bool(aview.IsShown)} n={aview.AnnotationCount} {members}"
            )


def _dump_drawing(draw, tag):
    ddoc = _early_bound(draw, "IDrawingDoc")
    view = _early_bound(ddoc.GetFirstView(), "IView")
    found = {}
    while True:
        raw = view.GetNextView()
        if raw is None:
            break
        view = _early_bound(raw, "IView")
        vname = str(view.GetName2())
        vtype = int(view.Type)
        items = []
        for raw_ann in tuple(view.GetAnnotations() or ()):
            item = _early_bound(raw_ann, "IAnnotation")
            if not bool(item.IsDimXpert()):
                continue
            pos = tuple(round(v, 5) for v in tuple(item.GetPosition() or ()))
            items.append(f"{item.GetName()}:t{item.GetType()}@{pos}")
            found[str(item.GetName())] = item
        _telemetry.info(f"{tag}: view '{vname}' type={vtype} {items}")
    return found


async def main() -> int:
    _telemetry.set_service("diagnostics")
    adapter = PyWin32Adapter({})
    _watchdog.start()
    try:
        await adapter.connect()
        adapter.swApp.CloseAllDocuments(True)
        shutil.copy2(SRC_PRT, CPY_PRT)
        shutil.copy2(SRC_DRW, CPY_DRW)

        check = await adapter.open_model(str(CPY_PRT))
        if not check.is_success:
            raise RuntimeError(f"part open failed: {check.error}")
        _dump_part_views(adapter.currentModel, "part")
        adapter.swApp.QuitDoc(str(_read_member(adapter.currentModel, "GetTitle")))

        # the copied drawing references the ORIGINAL sheetdrag part (read-only
        # use; only the drawing copy is ever saved)
        check = await adapter.open_model(str(CPY_DRW))
        if not check.is_success:
            raise RuntimeError(f"drawing open failed: {check.error}")
        draw = adapter.currentModel
        gtols = {
            name: item
            for name, item in _dump_drawing(draw, "sheet").items()
            if int(item.GetType()) == 5
        }
        if not gtols:
            _telemetry.warn("no gtols on sheet — placement test skipped")
        else:
            name, item = next(iter(gtols.items()))
            before = tuple(item.GetPosition() or ())
            target = (before[0] + 0.03, before[1] + 0.02, before[2])
            spec = _early_bound(item.GetSpecificAnnotation(), "IGtol")
            set_ok = bool(spec.SetPosition(*target))
            moved = tuple(item.GetPosition() or ())
            _telemetry.info(
                f"move {name}: SetPosition={set_ok} {before} -> {moved}"
            )
            draw.SaveAs3(os.path.abspath(CPY_DRW), 0, 0)
            post_save = tuple(item.GetPosition() or ())
            _telemetry.info(f"post-save {name}: {post_save}")
            adapter.swApp.QuitDoc(str(_read_member(draw, "GetTitle")))

            check = await adapter.open_model(str(CPY_DRW))
            if not check.is_success:
                raise RuntimeError(f"reopen failed: {check.error}")
            draw = adapter.currentModel
            reopened = _dump_drawing(draw, "reopened")
            back = reopened.get(name)
            if back is not None:
                final = tuple(back.GetPosition() or ())
                drift = math.hypot(final[0] - target[0], final[1] - target[1])
                verdict = "PERSISTED" if drift < 0.0005 else "REVERTED"
                _telemetry.info(
                    f"{verdict}: {name} target={tuple(round(v, 5) for v in target)} "
                    f"final={tuple(round(v, 5) for v in final)} drift={drift * 1000:.2f} mm"
                )
        adapter.swApp.QuitDoc(str(_read_member(adapter.currentModel, "GetTitle")))
        CPY_PRT.unlink(missing_ok=True)
        CPY_DRW.unlink(missing_ok=True)
        _telemetry.success("fixed-state probe complete (copies removed)")
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
