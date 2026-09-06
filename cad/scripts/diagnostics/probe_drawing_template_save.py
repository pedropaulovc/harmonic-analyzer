"""Owned blank-drawing save control: two native call shapes x two extensions.

Production ModelDoc2.SaveAs3(path,0,0) is the positive call shape. Compare the
failed prepared-template extension.SaveAs3(path,0,1,None,advanced0,0,0) shape on
fresh drawings with SLDDRW and DRWDOT targets. This compares complete call shapes
(including their different Options), not method identity alone. No source part,
global preference or existing document is changed. No PDF/PNG, view or rebuild.
Native run requires reviewed source, exclusive seat and AUTOSTART=0.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check  # noqa: E402
import _drawing_common as common  # noqa: E402
from solidworks_mcp.adapters.solidworks import drawing  # noqa: E402
from diagnostics._owned_native_documents import DocumentKind, run_copy_diagnostic  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment  # noqa: E402
from diagnostics.benchmark_drawing_recipes import revision  # noqa: E402
from diagnostics.probe_drawing_attachments import file_digest  # noqa: E402

CELLS = (
    ("model_save_as3", ".SLDDRW"),
    ("model_save_as3", ".DRWDOT"),
    ("extension_save_as3", ".SLDDRW"),
    ("extension_save_as3", ".DRWDOT"),
)


def invoke_save(model, target, method, row):
    if method == "model_save_as3":
        row["arguments"] = [str(target), 0, 0]
        row["returned"] = model.SaveAs3(str(target), 0, 0)
        return
    if method != "extension_save_as3":
        raise ValueError("unknown bounded save call shape")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    options = extension.GetAdvancedSaveAsOptions(0)
    if options is None:
        raise RuntimeError("advanced save options are unavailable")
    row["arguments"] = [str(target), 0, 1, None, "GetAdvancedSaveAsOptions(0)", 0, 0]
    row["returned"] = extension.SaveAs3(str(target), 0, 1, None, options, 0, 0)


def document_witness(model):
    return {
        "path": str(model.GetPathName()),
        "title": str(model.GetTitle()),
        "type": int(model.GetType()),
        "dirty": bool(model.GetSaveFlag()),
    }


def file_witness(target):
    if not target.is_file():
        return {"status": "absent"}
    return {
        "status": "present",
        "bytes": target.stat().st_size,
        "sha256": file_digest(target),
    }


def sheet_witness(model):
    sheet = _early_bound(_early_bound(model, "IDrawingDoc").GetCurrentSheet(), "ISheet")
    return {
        "properties": list(sheet.GetProperties2() or ()),
        "name": str(sheet.GetName()),
    }


async def capture(adapter, report_root):
    template = common.PROJECT_DRWDOT.resolve(strict=True)
    report_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="template-save-", dir=report_root))
    adapter.ownership.register_directory(directory)
    adapter.ownership.register_source(template)
    report = {
        "revision": revision("HEAD"),
        "template": str(template),
        "status": "running",
        "cells": [],
        "scope": "complete production0 versus advanced-silent1 call shapes; not method-only attribution",
    }
    report_path = directory / "save.json"

    def checkpoint():
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    def create(output, source_template):
        with adapter.ownership.creating_document(DocumentKind.DRAWING, output):
            return drawing.new_drawing(
                adapter,
                template=str(source_template),
                width=common.ASME_B_WIDTH_M,
                height=common.ASME_B_HEIGHT_M,
            )

    checkpoint()
    try:
        for index, (method, extension) in enumerate(CELLS):
            target = directory / f"cell-{index}{extension}"
            if target.exists():
                raise RuntimeError("save control target is not fresh")
            model = _early_bound(create(target, template), "IModelDoc2")
            row = {
                "method": method,
                "extension": extension,
                "target": str(target),
                "before": document_witness(model),
                "sheet_before": sheet_witness(model),
                "status": "running",
            }
            report["cells"].append(row)
            checkpoint()
            started = time.perf_counter()
            try:
                with adapter.ownership.saving_as(target):
                    model.ClearSelection2(True)
                    try:
                        invoke_save(model, target, method, row)
                    finally:
                        row["native_seconds"] = time.perf_counter() - started
                        row["after"] = document_witness(model)
                        row["file"] = file_witness(target)
                        checkpoint()
                if row["file"].get("bytes", 0) <= 0:
                    raise RuntimeError("save call produced no complete native file")
                if method == "extension_save_as3" and tuple(row["returned"])[:2] != (
                    True,
                    0,
                ):
                    raise RuntimeError(
                        "modern SaveAs3 did not return success plus zero errors"
                    )
                check(
                    "close saved control drawing", await adapter.close_model(save=False)
                )
                if extension == ".DRWDOT":
                    model = create(directory / f"verification-{index}.SLDDRW", target)
                else:
                    check(
                        "reopen saved control drawing",
                        await adapter.open_model(str(target)),
                    )
                    model = adapter.currentModel
                row["reopened"] = document_witness(_early_bound(model, "IModelDoc2"))
                row["sheet_reopened"] = sheet_witness(model)
                if row["sheet_reopened"] != row["sheet_before"]:
                    raise RuntimeError("saved drawing/template sheet readback changed")
                row["status"] = "persisted"
            except Exception as error:
                row.update(status="rejected", error=repr(error))
            finally:
                checkpoint()
                try:
                    await adapter.close_owned_documents()
                except Exception as cleanup_error:
                    row["cleanup_error"] = repr(cleanup_error)
                    raise
                finally:
                    checkpoint()
            if index == 0 and row["status"] != "persisted":
                raise RuntimeError(
                    "production SLDDRW positive control failed; remaining cells not attempted"
                )
        report["status"] = "captured"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        checkpoint()
    return {"save_control": str(report_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-root", type=Path, default=ROOT / "cad/out/reports/template-save"
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    require_owned_diagnostic_environment()
    if args.worker:
        return run_copy_diagnostic(lambda adapter: capture(adapter, args.report_root))
    import dodo

    dodo._run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--report-root",
            str(args.report_root.resolve()),
            "--worker",
        ],
        "drawing template save control",
        log_stem="template-save",
        com=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
