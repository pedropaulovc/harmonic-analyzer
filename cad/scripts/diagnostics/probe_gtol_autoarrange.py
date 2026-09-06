"""Copy-only GTol and mixed-bank AutoArrange control plus native ink measurements.

Run ``uv run python cad/scripts/diagnostics/probe_gtol_autoarrange.py <SLDDRW>``.
Each bank starts from a fresh uniquely named copy of the same saved drawing.
The parent takes the normal COM seat lock; no source document is saved.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad/scripts"))

import _telemetry  # noqa: E402
from _common import _early_bound, check  # noqa: E402
from diagnostics._owned_native_documents import run_copy_diagnostic  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment  # noqa: E402
from diagnostics.probe_native_model_pmi import file_digest, render_pdf_png  # noqa: E402


def observe(operation):
    try:
        return operation()
    except Exception as error:
        return {"error": repr(error)}


def text_data(data, *, font=None):
    return [
        {
            "text": str(data.GetTextAtIndex(i)),
            "position": tuple(data.GetTextPositionAtIndex(i) or ()),
            "height_m": float(data.GetTextHeightAtIndex(i)),
            "angle_rad": float(data.GetTextAngleAtIndex(i)),
            "font": font if font is not None else str(data.GetTextFontAtIndex(i)),
        }
        for i in range(int(data.GetTextCount()))
    ]


def metrics(annotation):
    result = {"position": tuple(annotation.GetPosition() or ())}
    raw = annotation.GetDisplayData()
    result["display_data"] = None
    if raw is not None:
        data = _early_bound(raw, "IDisplayData")
        result["display_data"] = {
            "text": observe(lambda: text_data(data)),
            "lines": observe(
                lambda: [
                    tuple(data.GetLineAtIndex3(i) or ())
                    for i in range(int(data.GetLineCount()))
                ]
            ),
        }
    if int(annotation.GetType()) == 5:
        gtol = _early_bound(annotation.GetSpecificAnnotation(), "IGtol")
        result["gtol"] = {
            "height": observe(lambda: float(gtol.GetHeight())),
            "text_point": observe(lambda: tuple(gtol.GetTextPoint() or ())),
            "text": observe(lambda: text_data(gtol, font=str(gtol.GetTextFont()))),
            "lines": observe(
                lambda: [
                    tuple(gtol.GetLineAtIndex(i) or ())
                    for i in range(int(gtol.GetLineCount()))
                ]
            ),
        }
    return result


def select_bank(model, drawing, rows, kinds):
    extension = _early_bound(model.Extension, "IModelDocExtension")
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    model.ClearSelection2(True)
    bank = [row for row in rows if row["kind"] in kinds]
    if not bank or (5 in kinds and not any(row["kind"] == 5 for row in bank)):
        raise RuntimeError("probe bank contains no GTols")
    if 4 in kinds and not any(row["kind"] == 4 for row in bank):
        raise RuntimeError("mixed probe bank contains no dimensions")
    for row in bank:
        if not drawing.ActivateView(row["view"]):
            raise RuntimeError(f"failed to activate {row['view']}")
        item = row["annotation"]
        if row["kind"] == 4:
            display = _early_bound(item.GetSpecificAnnotation(), "IDisplayDimension")
            selected = extension.SelectByID2(
                display.GetNameForSelection(), "DIMENSION", 0, 0, 0, True, 0, None, 0
            )
        else:
            selected = item.Select2(True, 0)
        if not selected:
            raise RuntimeError(f"bank selection failed: {row['name']}")
    count = int(selection.GetSelectedObjectCount2(-1))
    if count != len(bank):
        raise RuntimeError(f"bank selection count {count} != {len(bank)}")
    start = time.perf_counter()
    result = bool(extension.AlignDimensions(0, 0.001))
    return {
        "selected": count,
        "gtols": sum(row["kind"] == 5 for row in bank),
        "dimensions": sum(row["kind"] == 4 for row in bank),
        "return": result,
        "seconds": time.perf_counter() - start,
    }


def attachment_failures(records):
    """Keep empty dimension witnesses explicit; reject lost/changed entities."""
    failures = []
    for record in records:
        label = f"{record['view']}/{record['name']}"
        if record["entity_count_before"] != record["entity_count_after"]:
            failures.append(f"{label}: attachment count changed")
        if record["attachment_types_before"] != record["attachment_types_after"]:
            failures.append(f"{label}: attachment type changed")
        if any(value != 1 for value in record["entity_identity"]):
            failures.append(f"{label}: exact attachment identity not preserved")
        if record["dangling"]:
            failures.append(f"{label}: dangling after native arrangement")
        if record["kind"] == 5 and record["entity_count_after"] != 1:
            failures.append(f"{label}: GTol control requires one attached entity")
    return failures


async def probe(adapter, source, directory):
    from diagnostics._owned_native_documents import save_drawing

    adapter.ownership.register_directory(directory)
    adapter.ownership.register_source(source)

    app = _early_bound(adapter.swApp, "ISldWorks")
    report = {
        "source": str(source),
        "trials": [],
        "failures": [],
        "source_hashes": {str(source): file_digest(source)},
    }
    path = directory / "autoarrange.json"
    try:
        for mode, kinds in (
            ("gtol-only", (5,)),
            ("mixed", (4, 5)),
            ("displaced-dimensions-control", (4,)),
        ):
            copy = directory / f"{directory.name}-{mode}.SLDDRW"
            shutil.copy2(source, copy)
            check(
                "open unique AutoArrange control copy",
                await adapter.open_model(str(copy)),
            )
            model = adapter.currentModel
            if Path(model.GetPathName()).resolve() != copy:
                raise RuntimeError(
                    "SolidWorks opened a different drawing than the unique copy"
                )
            drawing = _early_bound(model, "IDrawingDoc")
            trial = {"mode": mode, "copy": str(copy), "annotations": []}
            report["trials"].append(trial)
            rows = []
            for sheet in drawing.GetViews() or ():
                for raw_view in sheet[1:]:
                    view = _early_bound(raw_view, "IView")
                    document = _early_bound(view.ReferencedDocument, "IModelDoc2")
                    reference = str(Path(document.GetPathName()).resolve())
                    report["source_hashes"].setdefault(
                        reference, file_digest(Path(reference))
                    )
                    for kind in (4, 5, 7):
                        for raw in view.GetAnnotationsByType(kind) or ():
                            item = _early_bound(raw, "IAnnotation")
                            rows.append(
                                {
                                    "view": str(view.GetName2()),
                                    "kind": kind,
                                    "name": str(item.GetName()),
                                    "annotation": item,
                                    "entities": tuple(
                                        item.GetAttachedEntities3() or ()
                                    ),
                                    "types": tuple(item.GetAttachedEntityTypes() or ()),
                                }
                            )
            if mode == "displaced-dimensions-control":
                item = next(row["annotation"] for row in rows if row["kind"] == 4)
                prior = tuple(item.GetPosition())
                if not item.SetPosition2(prior[0] + 0.02, prior[1] + 0.02, prior[2]):
                    raise RuntimeError(
                        "dimension positive-control displacement rejected"
                    )
                displaced = tuple(item.GetPosition())
                if math.dist(prior, displaced) < 0.001:
                    raise RuntimeError(
                        "dimension positive-control displacement had no effect"
                    )
                trial["displacement"] = {
                    "name": str(item.GetName()),
                    "before": prior,
                    "after": displaced,
                }
            for row in rows:
                trial["annotations"].append(
                    {
                        "view": row["view"],
                        "kind": row["kind"],
                        "name": row["name"],
                        "before": observe(lambda: metrics(row["annotation"])),
                    }
                )
            trial["align"] = observe(lambda: select_bank(model, drawing, rows, kinds))
            model.ClearSelection2(True)
            for row, saved in zip(rows, trial["annotations"]):
                item = row["annotation"]
                saved["after_position"] = tuple(item.GetPosition() or ())
                before_position = saved["before"].get("position")
                saved["moved_m"] = (
                    math.dist(before_position, saved["after_position"])
                    if before_position
                    else None
                )
                entities = tuple(item.GetAttachedEntities3() or ())
                types = tuple(item.GetAttachedEntityTypes() or ())
                saved["attachment_types_before"] = row["types"]
                saved["attachment_types_after"] = types
                saved["entity_count_before"] = len(row["entities"])
                saved["entity_count_after"] = len(entities)
                saved["entity_identity"] = [
                    int(app.IsSame(old, new))
                    if old is not None and new is not None
                    else None
                    for old, new in zip(row["entities"], entities)
                ]
                saved["dangling"] = bool(item.IsDangling())
                saved["attachment_witness"] = (
                    "exact_entities" if entities else "no_entities"
                )
            report["failures"].extend(attachment_failures(trial["annotations"]))
            output = directory / f"{directory.name}-{mode}-observed.SLDDRW"
            pdf, png = output.with_suffix(".pdf"), output.with_suffix(".png")
            save_drawing(adapter, str(output), pdf_path=str(pdf))
            render_pdf_png(pdf, png)
            trial["png"] = str(png)
            await adapter.close_owned_documents()
    except Exception as error:
        report["operation_error"] = repr(error)
        raise
    finally:
        try:
            await adapter.close_owned_documents()
        finally:
            report["source_hashes_after"] = {
                name: file_digest(Path(name)) for name in report["source_hashes"]
            }
            path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            _telemetry.info(f"native GTol AutoArrange observations: {path}")
    if report["source_hashes"] != report["source_hashes_after"]:
        raise RuntimeError(
            "source drawing or referenced model changed during the control"
        )
    if report["failures"]:
        raise RuntimeError(
            "attachment witness failed: " + "; ".join(report["failures"])
        )
    return {"report": str(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    source = args.drawing.resolve(strict=True)
    if source.suffix.upper() != ".SLDDRW":
        raise ValueError("requires a native drawing")
    if not args.worker:
        require_owned_diagnostic_environment()
        sys.path.insert(0, str(ROOT))
        import dodo

        dodo._run(
            [sys.executable, str(Path(__file__).resolve()), str(source), "--worker"],
            "GTol native AutoArrange positive control",
            com=True,
            log_stem="gtol-autoarrange-probe",
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("worker requires the parent seat lock")
    reports = ROOT / "cad/out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="gtol-autoarrange-", dir=reports))
    return run_copy_diagnostic(lambda adapter: probe(adapter, source, directory))


if __name__ == "__main__":
    raise SystemExit(main())
