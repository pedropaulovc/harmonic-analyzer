"""Inventory the seat; optionally discard only the witnessed failed rack drawing."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "cad/scripts")]


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--close-owned-failure-from", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "cad/out/reports") or output.exists():
        raise ValueError("choose a new receipt inside this checkout's reports")
    if Path(sys.prefix).resolve() != ROOT / ".venv":
        raise RuntimeError("use this checkout's own uv environment")
    if os.environ.get("HARMONIC_SW_AUTOSTART") != "0":
        raise RuntimeError("attach-only mode required")
    if not os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID"):
        raise RuntimeError("explicit inventoried SolidWorks PID required")
    from _common import _early_bound
    from diagnostics._owned_native_session import run_owned_diagnostic

    async def inventory(adapter):
        app = adapter.swApp
        report = {
            "kind": "vm2-datum-read-only-ownership",
            "utc": datetime.now(timezone.utc).isoformat(),
            "root": str(ROOT),
            "head": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "probe_sha256": digest(__file__),
            "pid": int(app.GetProcessID()),
            "revision": str(app.RevisionNumber()),
            "documents": [],
            "status": "running",
        }
        output.parent.mkdir(parents=True, exist_ok=True)

        def checkpoint():
            output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

        checkpoint()
        try:
            for raw in app.GetDocuments() or ():
                doc = _early_bound(raw, "IModelDoc2")
                path = str(doc.GetPathName())
                row = {
                    "path": path,
                    "title": str(doc.GetTitle()),
                    "type": int(doc.GetType()),
                    "state": "dirty" if doc.GetSaveFlag() else "clean",
                    "views": [],
                }
                report["documents"].append(row)
                if path:
                    row["saved_sha256_before"] = digest(path)
                checkpoint()
                if row["type"] != 3:
                    continue
                drawing = _early_bound(doc, "IDrawingDoc")
                raw_view = drawing.GetFirstView()
                while raw_view is not None:
                    view = _early_bound(raw_view, "IView")
                    reference = view.ReferencedDocument
                    view_row = {
                        "name": str(view.GetName2()),
                        "reference_name": str(view.GetReferencedModelName()),
                        "reference_path": (
                            str(_early_bound(reference, "IModelDoc2").GetPathName())
                            if reference is not None else None
                        ),
                        "datums": [],
                    }
                    row["views"].append(view_row)
                    for raw_tag in view.GetDatumTags() or ():
                        tag = _early_bound(raw_tag, "IDatumTag")
                        annotation = _early_bound(tag.GetAnnotation(), "IAnnotation")
                        attached = tuple(annotation.GetAttachedEntities3() or ())
                        view_row["datums"].append({
                            "label": str(tag.GetLabel()),
                            "position": list(annotation.GetPosition() or ()),
                            "attachment_types": list(annotation.GetAttachedEntityTypes() or ()),
                            "attachment_count": len(attached),
                            "null_attachment_indices": [
                                index for index, entity in enumerate(attached) if entity is None
                            ],
                        })
                    checkpoint()
                    raw_view = view.GetNextView()
            for row in report["documents"]:
                if row["path"]:
                    row["saved_sha256_after"] = digest(row["path"])
                    if row["saved_sha256_after"] != row["saved_sha256_before"]:
                        raise RuntimeError("saved document bytes changed during inventory")
            report["status"] = "read_only_complete"
            if args.close_owned_failure_from:
                witness_path = args.close_owned_failure_from.resolve(strict=True)
                witness = json.loads(witness_path.read_text(encoding="utf-8"))
                if witness["status"] != "read_only_complete":
                    raise RuntimeError("requires a successful read-only ownership receipt")
                for field in ("root", "pid", "revision", "documents"):
                    if witness[field] != report[field]:
                        raise RuntimeError(f"ownership changed since witness: {field}")
                expected_part = (
                    "C:\\src\\ha-assembly-granularity-integration\\cad\\out\\sldprt\\rack-pinion.SLDPRT"
                )
                rows = report["documents"]
                parts = [row for row in rows if row["type"] == 1]
                drawings = [row for row in rows if row["type"] == 3]
                if len(rows) != 2 or len(parts) != 1 or len(drawings) != 1:
                    raise RuntimeError("close permits only the witnessed two-document failure")
                part, drawing = parts[0], drawings[0]
                if part["path"] != expected_part or drawing["path"]:
                    raise RuntimeError("failed-drawing source ownership mismatch")
                if drawing["title"] != "Draw109 - Sheet1":
                    raise RuntimeError("unexpected unsaved drawing title")
                views = drawing["views"]
                if len(views) != 4 or views[0]["reference_path"] is not None:
                    raise RuntimeError("unexpected failed-drawing view inventory")
                if any(view["reference_path"] != expected_part for view in views[1:]):
                    raise RuntimeError("drawing references an unowned model")
                datums = [datum for view in views for datum in view["datums"]]
                if len(datums) != 1 or datums[0] != {
                    "label": "A",
                    "position": [0.21999999999999942, 0.20083662770023045, 0.0015],
                    "attachment_types": [1],
                    "attachment_count": 1,
                    "null_attachment_indices": [],
                }:
                    raise RuntimeError("datum does not match the retained retry failure")
                report["closure_witness"] = {
                    "path": str(witness_path), "sha256": digest(witness_path)
                }
                report["closed_without_save"] = []
                checkpoint()
                for target in (drawing, part):
                    present = [
                        _early_bound(raw, "IModelDoc2") for raw in app.GetDocuments() or ()
                    ]
                    titles = [str(doc.GetTitle()) for doc in present]
                    if target["title"] not in titles:
                        continue
                    if titles.count(target["title"]) != 1:
                        raise RuntimeError("ambiguous document title")
                    app.CloseDoc(target["title"])
                    report["closed_without_save"].append(target["title"])
                    checkpoint()
                if app.GetDocuments() or app.ActiveDoc is not None:
                    raise RuntimeError("owned failure closure did not empty the session")
                report["saved_sha256_after_close"] = digest(expected_part)
                if report["saved_sha256_after_close"] != part["saved_sha256_before"]:
                    raise RuntimeError("saved source changed during no-save closure")
                report["status"] = "owned_failure_closed_without_save_bytes_unchanged"
        except Exception as error:
            report.update(status="failed", error=repr(error))
            raise
        finally:
            checkpoint()
        return {"receipt": str(output), "sha256": digest(output)}

    if args.worker:
        return run_owned_diagnostic(inventory)
    import dodo
    with dodo._com_seat("VM2 datum read-only ownership"):
        command = [sys.executable, str(Path(__file__).resolve()), str(output), "--worker"]
        if args.close_owned_failure_from:
            command.extend(["--close-owned-failure-from", str(args.close_owned_failure_from.resolve())])
        dodo._exec(
            command,
            "VM2 datum read-only ownership",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
