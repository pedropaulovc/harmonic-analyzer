"""Compare native dimension-selection call shapes on an unsaved drawing copy.

Run with ``uv run python cad/scripts/probe_drawing_dimension_selection.py <drawing>``.
The parent acquires the normal machine-global COM seat and watchdog. Production
drawings are never modified; a uniquely named copy is opened and closed without
saving. This is an opt-in diagnostic, not part of the drawing build hot path.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any

from _common import CAD_ROOT, _early_bound, check
from diagnostics._owned_native_documents import run_copy_diagnostic
from diagnostics._owned_native_session import require_owned_diagnostic_environment
import _telemetry


def _capture(results: list[dict[str, Any]], label: str, operation: Any) -> Any:
    try:
        result = operation()
        results.append({"operation": label, "result": result})
        _telemetry.info(f"dimension selection probe {label}: {result}")
        return result
    except Exception as error:
        results.append({"operation": label, "error": repr(error)})
        _telemetry.info(f"dimension selection probe {label}: {error!r}")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    source = args.drawing.resolve(strict=True)
    if source.suffix.upper() != ".SLDDRW":
        raise ValueError("probe requires a native drawing")
    if not args.worker:
        require_owned_diagnostic_environment()
        sys.path.insert(0, str(CAD_ROOT.parent))
        import dodo
        dodo._run(
            [sys.executable, str(Path(__file__).resolve()), str(source), "--worker"],
            "drawing dimension selection probe", log_stem="drawing-dimension-selection-probe", com=True,
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("--worker requires the machine-global COM seat; invoke the probe without --worker")

    async def probe(adapter: Any) -> dict[str, str]:
        report_root = CAD_ROOT / "out/reports"
        report_root.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="dimension-selection-", dir=report_root))
        adapter.ownership.register_directory(folder)
        adapter.ownership.register_source(source)
        copy = folder / f"probe-{folder.name}-{source.name}"
        shutil.copy2(source, copy)
        check("open unique diagnostic drawing copy", await adapter.open_model(str(copy)))
        model = adapter.currentModel
        results: list[dict[str, Any]] = []
        try:
            if Path(model.GetPathName()).resolve() != copy:
                raise RuntimeError("SolidWorks opened a different drawing than the unique copy")
            drawing = _early_bound(model, "IDrawingDoc")
            selection = _early_bound(model.SelectionManager, "ISelectionMgr")
            extension = _early_bound(model.Extension, "IModelDocExtension")
            views = [_early_bound(view, "IView") for sheet in drawing.GetViews() or () for view in sheet[1:]]
            bank = [(view, tuple(view.GetAnnotationsByType(4) or ())) for view in views]
            for view, annotations in bank:
                if not annotations:
                    continue
                name = view.GetName2()
                if not drawing.ActivateView(name):
                    raise RuntimeError(f"failed to activate {name}")
                annotation = _early_bound(annotations[0], "IAnnotation")
                _capture(results, "metadata", lambda: {
                    "view": name, "name": annotation.GetName(), "type": annotation.GetType(),
                    "visibility": annotation.Visible, "position": tuple(annotation.GetPosition()),
                })
                data = _early_bound(selection.CreateSelectData(), "ISelectData")
                data.View = view
                for label, operation in (
                    ("Select3_data", lambda: annotation.Select3(False, data)),
                    ("Select3_null", lambda: annotation.Select3(False, None)),
                    ("Select2", lambda: annotation.Select2(False, 0)),
                    ("MultiSelect2", lambda: extension.MultiSelect2((annotation,), False, data)),
                ):
                    model.ClearSelection2(True)
                    _capture(results, label, operation)
                    _capture(results, f"{label}_selected", lambda: selection.GetSelectedObjectCount2(-1))
                break
            for mode in ("Select2", "named"):
                model.ClearSelection2(True)
                count = 0
                for view, annotations in bank:
                    if not annotations:
                        continue
                    if not drawing.ActivateView(view.GetName2()):
                        raise RuntimeError("failed to activate bank view")
                    for raw_annotation in annotations:
                        annotation = _early_bound(raw_annotation, "IAnnotation")
                        if mode == "Select2":
                            selected = annotation.Select2(True, 0)
                        else:
                            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
                            selected = extension.SelectByID2(
                                display.GetNameForSelection(), "DIMENSION", 0, 0, 0, True, 0, None, 0,
                            )
                        if not selected:
                            raise RuntimeError(f"{mode} bank rejected {annotation.GetName()}")
                        count += 1
                selected_count = int(selection.GetSelectedObjectCount2(-1))
                if count == 0 or selected_count != count:
                    raise RuntimeError(f"{mode} bank count mismatch: selected {selected_count}/{count}")
                _capture(results, mode + "_bank_count", lambda: count)
                if not _capture(results, mode + "_AlignDimensions", lambda: extension.AlignDimensions(0, 0.001)):
                    raise RuntimeError(f"{mode} bank rejected AutoArrange")
        finally:
            try:
                await adapter.close_owned_documents()
            finally:
                report = folder / "selection.json"
                report.write_text(json.dumps({"source": str(source), "copy": str(copy), "results": results}, indent=2), encoding="utf-8")
        return {"report": str(report)}

    _telemetry.set_service("drawing-dimension-selection-probe")
    return run_copy_diagnostic(probe)


if __name__ == "__main__":
    raise SystemExit(main())
