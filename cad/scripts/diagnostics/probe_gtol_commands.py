"""Test documented annotation-spacing UI commands on fresh drawing copies.

Run ``uv run python cad/scripts/diagnostics/probe_gtol_commands.py <SLDDRW>``.
Per-view GTol banks test SpaceTightlyDown (317) then AnnotationAlignLeft (307),
and AutoArrangeDimension (2976) independently. Each command is saved/reopened,
its actual movement and native ink recorded, its source-entity persistent IDs
resolved again, and its PDF/PNG exported. No hand-positioning or PMI recreation.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
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
from _common import _early_bound, check, run_build  # noqa: E402
from _gtol_spec import gtol_frame_signature  # noqa: E402
from diagnostics.probe_gtol_autoarrange import metrics  # noqa: E402
from diagnostics.probe_native_model_pmi import file_digest, render_pdf_png  # noqa: E402


def resolve_reference(extension, reference):
    """Official Use Persistent Reference byte-array shape, generated out tuple."""
    import pythoncom
    from win32com.client import VARIANT

    result = extension.GetObjectByPersistReference3(
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_UI1, reference)
    )
    if not isinstance(result, tuple) or len(result) != 2:
        raise RuntimeError(
            f"unexpected persistent-reference result shape: {type(result)}"
        )
    entity, status = result
    if entity is None or int(status) != 0:
        raise RuntimeError(
            f"source persistent reference did not resolve: status={status}"
        )
    return entity


def snapshot(drawing, hashes):
    records, handles = {}, {}
    drawing_model = _early_bound(drawing, "IModelDoc2")
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    for sheet in drawing.GetViews() or ():
        for raw_view in sheet[1:]:
            view = _early_bound(raw_view, "IView")
            annotations = tuple(view.GetAnnotationsByType(5) or ())
            if not annotations:
                continue
            model = _early_bound(view.ReferencedDocument, "IModelDoc2")
            source = str(Path(model.GetPathName()).resolve())
            hashes.setdefault(source, file_digest(Path(source)))
            for raw in annotations:
                item = _early_bound(raw, "IAnnotation")
                key = f"{view.GetName2()}/{item.GetName()}"
                if key in records:
                    raise RuntimeError(f"duplicate native annotation identity: {key}")
                entities = tuple(item.GetAttachedEntities3() or ())
                kinds = tuple(item.GetAttachedEntityTypes() or ())
                if len(entities) != 1 or len(kinds) != 1 or entities[0] is None:
                    raise RuntimeError(f"{key}: expected one nonnull GTol attachment")
                reference = tuple(
                    int(value)
                    for value in extension.GetPersistReference3(entities[0]) or ()
                )
                if not reference:
                    raise RuntimeError(
                        f"{key}: source entity has no persistent reference"
                    )
                gtol = _early_bound(item.GetSpecificAnnotation(), "IGtol")
                frame = _early_bound(gtol.GetFrame(1), "IGtolFrame")
                records[key] = {
                    "view": str(view.GetName2()),
                    "name": str(item.GetName()),
                    "source": source,
                    "attachment_types": kinds,
                    "reference_context": "drawing",
                    "entity_reference": reference,
                    "dangling": bool(item.IsDangling()),
                    "frame_signature": asdict(
                        gtol_frame_signature(str(frame.GetSymbolXml()))
                    ),
                    "ink": metrics(item),
                }
                handles[key] = {
                    "annotation": item,
                    "entity": entities[0],
                    "extension": extension,
                }
    if not records:
        raise RuntimeError("drawing has no GTols for the positive control")
    return records, handles


def compare(before, after, handles, app, *, stage):
    if set(before) != set(after):
        raise RuntimeError(f"{stage}: native annotation coverage changed")
    movements = {}
    for key, prior in before.items():
        current = after[key]
        for field in ("source", "attachment_types", "frame_signature"):
            if current[field] != prior[field]:
                raise RuntimeError(f"{stage}: {key}: {field} changed")
        old_text = [row["text"] for row in prior["ink"]["gtol"]["text"]]
        new_text = [row["text"] for row in current["ink"]["gtol"]["text"]]
        if old_text != new_text or current["dangling"]:
            raise RuntimeError(f"{stage}: {key}: text changed or annotation dangling")
        expected_entity = resolve_reference(
            handles[key]["extension"], prior["entity_reference"]
        )
        if int(app.IsSame(expected_entity, handles[key]["entity"])) != 1:
            raise RuntimeError(f"{stage}: {key}: exact source entity identity changed")
        movements[key] = math.dist(prior["ink"]["position"], current["ink"]["position"])
    return movements


def run_command(app, model, drawing, bank, command):
    """Select one complete view-owned GTol bank, then run one documented command."""
    if len(bank) < 2:
        raise RuntimeError(
            "spacing positive control requires at least two GTols in a view"
        )
    view = bank[0][0]
    if any(name != view for name, item in bank):
        raise RuntimeError("native command bank must contain only one drawing view")
    model.ClearSelection2(True)
    if not drawing.ActivateView(view):
        raise RuntimeError(f"failed to activate {view}")
    for name, item in bank:
        if not item.Select2(True, 0):
            raise RuntimeError("failed to select native GTol bank")
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    count = int(selection.GetSelectedObjectCount2(-1))
    if count != len(bank):
        raise RuntimeError(f"selected GTol bank count {count} != {len(bank)}")
    enabled = bool(app.IsCommandEnabled(command))
    start = time.perf_counter()
    with _telemetry.span("diagnostic.gtol_command", command=command, view=view):
        accepted = bool(app.RunCommand(command, ""))
    model.ClearSelection2(True)
    return {
        "view": view,
        "command": command,
        "selected": count,
        "enabled": enabled,
        "return": accepted,
        "seconds": time.perf_counter() - start,
    }


async def probe(adapter, source, directory):
    from solidworks_mcp.adapters.solidworks.drawing import save_drawing

    app = _early_bound(adapter.swApp, "ISldWorks")
    report = {
        "source": str(source),
        "source_hashes": {str(source): file_digest(source)},
        "trials": [],
    }
    report_path = directory / "commands.json"
    try:
        for mode, commands in (("tight-left", (317, 307)), ("autoarrange", (2976,))):
            copy = directory / f"{directory.name}-{mode}-source.SLDDRW"
            shutil.copy2(source, copy)
            check(
                "open command control drawing copy", await adapter.open_model(str(copy))
            )
            if Path(adapter.currentModel.GetPathName()).resolve() != copy:
                raise RuntimeError("SolidWorks opened a different drawing")
            drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
            baseline, handles = snapshot(drawing, report["source_hashes"])
            compare(
                baseline,
                baseline,
                handles,
                app,
                stage="persistent-reference positive control",
            )
            trial = {"mode": mode, "baseline": baseline, "steps": []}
            report["trials"].append(trial)
            for command in commands:
                step = {"command": command, "calls": []}
                trial["steps"].append(step)
                for view in sorted({row["view"] for row in baseline.values()}):
                    bank = [
                        (view, handles[key]["annotation"])
                        for key, row in baseline.items()
                        if row["view"] == view
                    ]
                    step["calls"].append(
                        run_command(app, adapter.currentModel, drawing, bank, command)
                    )
                after, handles = snapshot(drawing, report["source_hashes"])
                step["after"] = after
                step["movement_m"] = compare(
                    baseline, after, handles, app, stage=f"command {command}"
                )
                output = directory / f"{directory.name}-{mode}-{command}.SLDDRW"
                save_drawing(adapter, str(output))
                if not app.CloseAllDocuments(True):
                    raise RuntimeError("failed to close command control drawings")
                adapter.currentModel = None
                check(
                    "reopen command control drawing",
                    await adapter.open_model(str(output)),
                )
                drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
                reopened, handles = snapshot(drawing, report["source_hashes"])
                step["reopened"] = reopened
                step["reopen_drift_m"] = compare(
                    after, reopened, handles, app, stage="save/reopen"
                )
                if any(delta > 1e-9 for delta in step["reopen_drift_m"].values()):
                    raise RuntimeError(
                        "native annotation position changed on save/reopen"
                    )
                native = (
                    directory / f"{directory.name}-{mode}-{command}-reopened.SLDDRW"
                )
                pdf, png = native.with_suffix(".pdf"), native.with_suffix(".png")
                save_drawing(adapter, str(native), pdf_path=str(pdf))
                render_pdf_png(pdf, png)
                step["png"] = str(png)
                baseline = reopened
            if not app.CloseAllDocuments(True):
                raise RuntimeError("failed to close command control drawings")
            adapter.currentModel = None
    except Exception as error:
        report["operation_error"] = repr(error)
        raise
    finally:
        try:
            if not app.CloseAllDocuments(True):
                raise RuntimeError("failed to close command control drawings")
            adapter.currentModel = None
        finally:
            report["source_hashes_after"] = {
                name: file_digest(Path(name)) for name in report["source_hashes"]
            }
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            _telemetry.info(f"native GTol command observations: {report_path}")
    if report["source_hashes"] != report["source_hashes_after"]:
        raise RuntimeError("original source drawing or part changed")
    if any(
        not call["return"]
        for trial in report["trials"]
        for step in trial["steps"]
        for call in step["calls"]
    ):
        raise RuntimeError(
            "one or more native commands rejected the selected GTol bank; see commands.json"
        )
    return {"report": str(report_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    source = args.drawing.resolve(strict=True)
    if source.suffix.upper() != ".SLDDRW":
        raise ValueError("requires a native drawing")
    if not args.worker:
        sys.path.insert(0, str(ROOT))
        import dodo

        dodo._run(
            [sys.executable, str(Path(__file__).resolve()), str(source), "--worker"],
            "GTol native spacing commands",
            com=True,
            log_stem="gtol-commands-probe",
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("worker requires parent COM seat lock")
    reports = ROOT / "cad/out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="gtol-commands-", dir=reports))
    return run_build(lambda adapter: probe(adapter, source, directory))


if __name__ == "__main__":
    raise SystemExit(main())
