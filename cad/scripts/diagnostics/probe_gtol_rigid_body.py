"""Copy-only native GTol command/translation body-rigidity control.

Run ``uv run python cad/scripts/diagnostics/probe_gtol_rigid_body.py DRAWING``.
Calls the production layout helper with every guard intact. Diagnostic wrappers
only collect native primitives, text and measured bounds after its existing
operations; no alternate positioning strategy or fallback is attempted. Export
the unique drawing before/after, including a failed layout, without publishing
it as a production artefact. Source drawing and referenced-part hashes must stay
unchanged. The additional diagnostic reads are not a performance benchmark.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check, run_build  # noqa: E402
from _drawing_annotation_bounds import annotation_box, _native_snapshot  # noqa: E402
import _drawing_native_gtol as layout  # noqa: E402
import _telemetry  # noqa: E402
from diagnostics.probe_native_model_pmi import file_digest, render_pdf_png  # noqa: E402


def predicted_records(bank):
    return {
        name: {
            "position": row.position,
            "body": row.body.bounds,
            "frames": row.frames,
            "text": row.text,
            "format": row.text_format,
            "attachment_types": row.entity_types,
            "owner_type": row.owner_type,
        }
        for name, row in bank.items()
    }


def native_records(adapter, bank):
    extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    return {
        name: {
            "measured": asdict(annotation_box(adapter, row.annotation)),
            "native": asdict(_native_snapshot(row.annotation, extension)),
        }
        for name, row in bank.items()
    }


@contextmanager
def capture_stages(adapter, report, capture=native_records):
    """Observe exactly the existing production calls and restore every wrapper."""
    original_read, original_command = layout._read_gtols, layout._native_command
    original_move, original_assert = (
        layout._move_bank,
        layout._assert_measured_prediction,
    )
    reads = {}

    def record(stage, bank, **fields):
        report["steps"].append(
            {
                "stage": stage,
                **fields,
                "state": predicted_records(bank),
                "capture": capture(adapter, bank),
            }
        )

    def read(adapter, view, measure):
        bank = original_read(adapter, view, measure)
        view_name = str(view.GetName2())
        reads[view_name] = reads.get(view_name, 0) + 1
        record(
            "initial_witness" if reads[view_name] == 1 else "final_witness",
            bank,
            view=view_name,
            state_basis="native_measured",
        )
        return bank

    def command(adapter, drawing, view, bank, command):
        original_command(adapter, drawing, view, bank, command)
        record(
            "native_command",
            bank,
            command=command,
            view=str(view.GetName2()),
            state_basis="before_command",
        )

    def move(bank, deltas, stage):
        result = original_move(bank, deltas, stage)
        record(
            stage, result, requested_deltas=deltas, state_basis="derived_translation"
        )
        return result

    def assert_prediction(predicted, measured):
        report["predicted_final"] = predicted_records(predicted)
        report["measured_final"] = predicted_records(measured)
        original_assert(predicted, measured)

    layout._read_gtols, layout._native_command = read, command
    layout._move_bank, layout._assert_measured_prediction = move, assert_prediction
    try:
        yield
    finally:
        layout._read_gtols, layout._native_command = original_read, original_command
        layout._move_bank, layout._assert_measured_prediction = (
            original_move,
            original_assert,
        )


async def probe(adapter, source, directory):
    from solidworks_mcp.adapters.solidworks.drawing import save_drawing

    report = {
        "source": str(source),
        "source_hashes": {str(source): file_digest(source)},
        "steps": [],
    }
    report_path = directory / "rigid-body.json"
    copy = directory / f"{directory.name}-source.SLDDRW"
    shutil.copy2(source, copy)
    app = _early_bound(adapter.swApp, "ISldWorks")

    def export(stage):
        target = directory / f"{directory.name}-{stage}.SLDDRW"
        pdf, png = target.with_suffix(".pdf"), target.with_suffix(".png")
        outputs = save_drawing(adapter, str(target), pdf_path=str(pdf))
        if not pdf.is_file():
            raise RuntimeError(f"diagnostic export did not produce PDF: {outputs}")
        render_pdf_png(pdf, png)
        report.setdefault("exports", {})[stage] = {
            "drawing": str(target),
            "pdf": str(pdf),
            "png": str(png),
        }
        return target

    try:
        check("open unique GTol rigidity copy", await adapter.open_model(str(copy)))
        if Path(adapter.currentModel.GetPathName()).resolve() != copy:
            raise RuntimeError("SolidWorks opened a different drawing copy")
        drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
        views = {}
        for sheet in drawing.GetViews() or ():
            for raw in sheet[1:]:
                view = _early_bound(raw, "IView")
                name = str(view.GetName2())
                if name in views:
                    raise RuntimeError(f"duplicate drawing view name: {name}")
                views[name] = view
                source_part = str(Path(view.ReferencedDocument.GetPathName()).resolve())
                report["source_hashes"].setdefault(
                    source_part, file_digest(Path(source_part))
                )
        export("before")
        try:
            with capture_stages(adapter, report):
                report["layout"] = layout.arrange_native_gtol_columns(
                    adapter, views=views, measure_annotation=annotation_box
                )
        except Exception as error:
            report["layout_error"] = repr(error)
        output = export("observed")
        if not app.CloseAllDocuments(True):
            raise RuntimeError("failed to close diagnostic drawings before reopen")
        adapter.currentModel = None
        check(
            "reopen observed GTol rigidity copy", await adapter.open_model(str(output))
        )
        drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
        report["reopened"] = {}
        for sheet in drawing.GetViews() or ():
            for raw in sheet[1:]:
                view = _early_bound(raw, "IView")
                bank = layout._read_gtols(adapter, view, annotation_box)
                report["reopened"][str(view.GetName2())] = {
                    "state": predicted_records(bank),
                    "capture": native_records(adapter, bank),
                }
        export("reopened")
    except Exception as error:
        report["operation_error"] = repr(error)
        raise
    finally:
        try:
            if not app.CloseAllDocuments(True):
                raise RuntimeError("failed to close GTol diagnostic documents")
            adapter.currentModel = None
        finally:
            report["source_hashes_after"] = {
                name: file_digest(Path(name)) for name in report["source_hashes"]
            }
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            _telemetry.info(f"native GTol rigidity observations: {report_path}")
    if report["source_hashes"] != report["source_hashes_after"]:
        raise RuntimeError(
            "GTol rigidity diagnostic changed an original drawing or part"
        )
    if "layout_error" in report:
        raise RuntimeError(
            f"native rigidity failed; complete isolated evidence: {report_path}"
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
            "native GTol rigidity",
            com=True,
            log_stem="gtol-rigidity-probe",
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("worker requires the parent COM seat lock")
    reports = ROOT / "cad/out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="gtol-rigidity-", dir=reports))
    return run_build(lambda adapter: probe(adapter, source, directory))


if __name__ == "__main__":
    raise SystemExit(main())
