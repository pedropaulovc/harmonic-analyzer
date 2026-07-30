r"""Positive control for part-owned surface-finish PMI.

The production migration must not assume that a surface-finish symbol authored
on a ``.SLDPRT`` survives save/reopen or imports into a drawing.  This probe
copies the already-built transgear stud, verifies its production-authored named
Ra 1.6 symbol, then proves both behaviors without modifying released artefacts.

Run with a 3DEXPERIENCE-launched SolidWorks session already open::

    uv run python cad/scripts/diagnostics/probe_surface_finish_pmi.py
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
from _surface_finish import surface_finish_by_key  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter  # noqa: E402
from transgear_stub_spec import SURFACE_FINISHES  # noqa: E402

SOURCE = CAD_ROOT / "out" / "sldprt" / "transgear-stub.SLDPRT"
SCRATCH_PRT = CAD_ROOT / "out" / "sldprt" / "transgear-stub-surface-pmi.SLDPRT"
SCRATCH_DRW = CAD_ROOT / "out" / "slddrw" / "transgear-stub-surface-pmi.SLDDRW"
CONTROL = surface_finish_by_key(SURFACE_FINISHES, "gear_seat")
ANNOTATION_NAME = CONTROL.annotation_name
ROUGHNESS = f"Ra {CONTROL.roughness_um:g}"
SHEET_TARGET = (0.19, 0.19)

_SFS_ANNOTATION = 7
_INSERT_SURFACE_FINISH = 0x80


@_telemetry.traced("diagnostic.surface_finish_pmi.walk_part_annotations")
def _surface_annotations(model):
    found = {}
    raw = model.GetFirstAnnotation2()
    while raw is not None:
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.GetType()) == _SFS_ANNOTATION:
            found[str(annotation.GetName() or "")] = annotation
        raw = annotation.GetNext3()
    return found


@_telemetry.traced("diagnostic.surface_finish_pmi.walk_drawing_annotations")
def _drawing_surface_annotations(model):
    drawing = _early_bound(model, "IDrawingDoc")
    view = _early_bound(drawing.GetFirstView(), "IView")
    found = {}
    while True:
        raw_view = view.GetNextView()
        if raw_view is None:
            return found
        view = _early_bound(raw_view, "IView")
        for raw in tuple(view.GetAnnotations() or ()):
            annotation = _early_bound(raw, "IAnnotation")
            if int(annotation.GetType()) == _SFS_ANNOTATION:
                found[f"{view.GetName2()}/{annotation.GetName() or ''}"] = annotation


@_telemetry.traced("diagnostic.surface_finish_pmi.assert_symbol", label_param="stage")
def _assert_symbol(annotation, *, stage: str) -> None:
    symbol = _early_bound(annotation.GetSpecificAnnotation(), "ISFSymbol")
    if str(symbol.GetText(8) or "").strip() != ROUGHNESS:
        raise RuntimeError(
            f"{stage}: roughness mismatch: {symbol.GetText(8)!r} != {ROUGHNESS!r}"
        )
    if not bool(symbol.IsAttached()):
        raise RuntimeError(f"{stage}: surface-finish symbol is not attached")
    entities = tuple(annotation.GetAttachedEntities3() or ())
    if len(entities) != 1 or entities[0] is None:
        raise RuntimeError(
            f"{stage}: expected one attached entity, got {len(entities)}"
        )


@_telemetry.traced("diagnostic.surface_finish_pmi")
async def main() -> int:
    _telemetry.set_service("diagnostics")
    adapter = PyWin32Adapter({})
    _watchdog.start()
    try:
        await adapter.connect()
        adapter.swApp.CloseAllDocuments(True)
        shutil.copy2(SOURCE, SCRATCH_PRT)
        SCRATCH_DRW.unlink(missing_ok=True)

        with _telemetry.span("diagnostic.surface_finish_pmi.part_authoring"):
            result = await adapter.open_model(str(SCRATCH_PRT))
            if not result.is_success:
                raise RuntimeError(f"part open failed: {result.error}")
            model = adapter.currentModel
            authored = _surface_annotations(model)
            if tuple(authored) != (ANNOTATION_NAME,):
                raise RuntimeError(
                    "expected exactly the production-authored surface finish "
                    f"{ANNOTATION_NAME!r}, got {tuple(authored)!r}"
                )
            _assert_symbol(authored[ANNOTATION_NAME], stage="part authored")

        with _telemetry.span("diagnostic.surface_finish_pmi.part_save_reopen"):
            model.ClearSelection2(True)
            model.SaveAs3(os.path.abspath(SCRATCH_PRT), 0, 0)
            adapter.swApp.CloseAllDocuments(True)

            result = await adapter.open_model(str(SCRATCH_PRT))
            if not result.is_success:
                raise RuntimeError(f"part reopen failed: {result.error}")
            reopened = _surface_annotations(adapter.currentModel)
            if ANNOTATION_NAME not in reopened:
                raise RuntimeError(
                    "named part surface-finish annotation did not persist"
                )
            _assert_symbol(reopened[ANNOTATION_NAME], stage="part reopened")
            adapter.swApp.CloseAllDocuments(True)

        from solidworks_mcp.adapters.solidworks.drawing import new_drawing, place_view

        with _telemetry.span("diagnostic.surface_finish_pmi.drawing_import"):
            new_drawing(adapter)
            draw = adapter.currentModel
            drawing = _early_bound(draw, "IDrawingDoc")
            _early_bound(
                place_view(
                    adapter,
                    str(SCRATCH_PRT),
                    "*Front",
                    0.11,
                    0.15,
                    scale=(4.0, 1.0),
                ),
                "IView",
            )
            inserted = tuple(
                drawing.InsertModelAnnotations3(
                    0, _INSERT_SURFACE_FINISH, True, True, False, False
                )
                or ()
            )
            imported = [
                _early_bound(item, "IAnnotation")
                for item in inserted
                if int(_early_bound(item, "IAnnotation").GetType()) == _SFS_ANNOTATION
            ]
            _telemetry.info(
                f"InsertModelAnnotations3(surface finishes) -> {len(imported)}"
            )
            if len(imported) != 1:
                raise RuntimeError(
                    f"expected one imported surface finish, got {len(imported)}"
                )
            _assert_symbol(imported[0], stage="drawing imported")
            if str(imported[0].GetName() or "") != ANNOTATION_NAME:
                raise RuntimeError(
                    "drawing import lost annotation name: "
                    f"{imported[0].GetName()!r} != {ANNOTATION_NAME!r}"
                )
            if not imported[0].SetPosition2(*SHEET_TARGET, 0.0):
                raise RuntimeError("failed to position imported surface finish")
            draw.SaveAs3(os.path.abspath(SCRATCH_DRW), 0, 0)
            adapter.swApp.CloseAllDocuments(True)

        with _telemetry.span("diagnostic.surface_finish_pmi.drawing_final_reopen"):
            result = await adapter.open_model(str(SCRATCH_DRW))
            if not result.is_success:
                raise RuntimeError(f"drawing reopen failed: {result.error}")
            final = _drawing_surface_annotations(adapter.currentModel)
            _telemetry.info(f"drawing reopen surface-finish names: {tuple(final)}")
            if len(final) != 1:
                raise RuntimeError(
                    f"expected one reopened drawing surface finish, got {len(final)}"
                )
            reopened_annotation = next(iter(final.values()))
            _assert_symbol(reopened_annotation, stage="drawing reopened")
            position = tuple(reopened_annotation.GetPosition() or ())
            if (
                len(position) < 2
                or max(
                    abs(position[0] - SHEET_TARGET[0]),
                    abs(position[1] - SHEET_TARGET[1]),
                )
                > 0.0005
            ):
                raise RuntimeError(
                    "imported surface-finish position did not persist: "
                    f"{position!r} != {SHEET_TARGET!r}"
                )
            adapter.swApp.QuitDoc(str(_read_member(adapter.currentModel, "GetTitle")))
        _telemetry.success("surface-finish PMI positive control passed")
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
