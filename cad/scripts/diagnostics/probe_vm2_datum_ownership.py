"""Inventory the seat; optionally close witnessed own probes or production outputs."""

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
    closure = parser.add_mutually_exclusive_group()
    closure.add_argument("--close-owned-probe-from", type=Path)
    closure.add_argument("--close-production-from", type=Path)
    parser.add_argument("--inventory-witness", type=Path)
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
                        "annotations": [],
                    }
                    row["views"].append(view_row)
                    from _drawing_common import dimension_name
                    for raw_annotation in view.GetAnnotations() or ():
                        annotation = _early_bound(raw_annotation, "IAnnotation")
                        annotation_type = int(annotation.GetType())
                        view_row["annotations"].append({
                            "type": annotation_type,
                            "dimension_name": dimension_name(adapter, annotation)
                            if annotation_type == 4 else None,
                        })
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
            if args.close_production_from:
                if args.inventory_witness is None:
                    raise RuntimeError("production closure requires a prior inventory")
                previous = json.loads(args.inventory_witness.read_text(encoding="utf-8"))
                if previous["status"] != "read_only_complete":
                    raise RuntimeError("prior inventory was not successful")
                for field in ("root", "pid", "revision", "documents"):
                    if previous[field] != report[field]:
                        raise RuntimeError(f"production ownership changed: {field}")
                witness_path = args.close_production_from.resolve(strict=True)
                if not witness_path.is_relative_to(ROOT / "cad/out/reports/datum-placement"):
                    raise RuntimeError("production witness leaves own reports")
                witness = json.loads(witness_path.read_text(encoding="utf-8"))
                if witness["kind"] != "vm2-normal-datum-drawing-tasks" or witness["status"] != "passed":
                    raise RuntimeError("requires a successful normal production receipt")
                allowed = {}
                for stem in ("pinion-lift-rod", "rack-pinion"):
                    source = ROOT / f"cad/out/sldprt/{stem}.SLDPRT"
                    drawing = ROOT / f"cad/out/slddrw/{stem}.SLDDRW"
                    allowed[str(source)] = (1, witness["source_sha256_after"][str(source)], source)
                    allowed[str(drawing)] = (3, witness["outputs"][str(drawing)], source)
                rows = report["documents"]
                titles = [row["title"].casefold() for row in rows]
                if any(not title for title in titles) or len(set(titles)) != len(titles):
                    raise RuntimeError("ambiguous production close titles")
                for row in rows:
                    if row["path"] not in allowed or row["state"] != "clean":
                        raise RuntimeError("unowned or dirty production document; refusing closure")
                    doc_type, expected_hash, source = allowed[row["path"]]
                    if row["type"] != doc_type or row["saved_sha256_before"] != expected_hash:
                        raise RuntimeError("production document identity changed")
                    if doc_type == 3 and any(
                        view["reference_path"] not in (None, str(source)) for view in row["views"]
                    ):
                        raise RuntimeError("production drawing references another source")
                report["closure_witness"] = {"path": str(witness_path), "sha256": digest(witness_path)}
                report["closed_without_save"] = []
                checkpoint()
                for target in sorted(rows, key=lambda row: row["type"] != 3):
                    present = [_early_bound(raw, "IModelDoc2") for raw in app.GetDocuments() or ()]
                    current = [(str(doc.GetPathName()), str(doc.GetTitle())) for doc in present]
                    if any(pair not in {(row["path"], row["title"]) for row in rows} for pair in current):
                        raise RuntimeError("unowned document appeared during closure")
                    if (target["path"], target["title"]) not in current:
                        continue
                    app.CloseDoc(target["title"])
                    report["closed_without_save"].append(target["path"])
                    checkpoint()
                if app.GetDocuments() or app.ActiveDoc is not None:
                    raise RuntimeError("production closure did not empty the seat")
                if any(digest(Path(path)) != expected_hash for path, (_, expected_hash, _) in allowed.items()):
                    raise RuntimeError("production bytes changed during no-save closure")
                report["status"] = "production_closed_without_save_bytes_unchanged"
            if args.close_owned_probe_from:
                if args.inventory_witness is None:
                    raise RuntimeError("probe closure requires a prior read-only inventory")
                previous = json.loads(args.inventory_witness.read_text(encoding="utf-8"))
                if previous["status"] != "read_only_complete":
                    raise RuntimeError("prior inventory was not successful")
                for field in ("root", "pid", "revision", "documents"):
                    if previous[field] != report[field]:
                        raise RuntimeError(f"probe ownership changed since inventory: {field}")
                witness_path = args.close_owned_probe_from.resolve(strict=True)
                if not witness_path.is_relative_to(ROOT / "cad/out/reports/datum-placement"):
                    raise RuntimeError("probe witness is outside own reports")
                witness = json.loads(witness_path.read_text(encoding="utf-8"))
                if witness["kind"] != "vm2-datum-one-variable-probe" or witness["status"] != "failed":
                    raise RuntimeError("requires a failed own probe receipt")
                if (witness["pid"], witness["revision"]) != (report["pid"], report["revision"]):
                    raise RuntimeError("probe seat identity changed")
                source = Path(witness["source"]).resolve(strict=True)
                if source.parent != ROOT / "cad/out/sldprt" or source.stem not in {"pinion-lift-rod", "rack-pinion"}:
                    raise RuntimeError("probe source is outside the two owned parts")
                rows = report["documents"]
                parts = [row for row in rows if row["type"] == 1]
                drawings = [row for row in rows if row["type"] == 3]
                if len(rows) != 2 or len(parts) != 1 or len(drawings) != 1:
                    raise RuntimeError("expected exactly the probe source and one drawing")
                part, drawing = parts[0], drawings[0]
                if Path(part["path"]).resolve() != source:
                    raise RuntimeError("expected own source")
                expected_source_hash = witness["source_sha256_before"]
                if not drawing["path"]:
                    prepared = witness.get("prepared_drawing", {})
                    if prepared.get("title") != drawing["title"] or prepared.get("path") != "" or prepared.get("source") != str(source):
                        raise RuntimeError("failed receipt does not identify this unsaved drawing")
                if drawing["path"]:
                    saved = witness.get("exports", {}).get("SLDDRW", {})
                    if drawing["path"] != saved.get("path") or Path(drawing["path"]).resolve() != witness_path.parent / "partial.SLDDRW":
                        raise RuntimeError("unexpected saved probe drawing")
                    if drawing["saved_sha256_before"] != saved.get("sha256") or drawing["state"] != "clean" or part["state"] != "clean":
                        raise RuntimeError("saved failed-probe evidence changed")
                    if witness.get("error") != "RuntimeError('diagnostic export changed saved source bytes')":
                        raise RuntimeError("saved closure permits only the recorded export identity failure")
                    expected_source_hash = witness["source_sha256_after"]
                    report["retained_source_identity_failure"] = {
                        "before_probe": witness["source_sha256_before"],
                        "after_probe": expected_source_hash,
                        "acceptance": "failed; closure does not repair or accept identity drift",
                    }
                if part["saved_sha256_before"] != expected_source_hash:
                    raise RuntimeError("source changed after failed probe")
                views = drawing["views"]
                if len(views) != 4 or views[0]["reference_path"] is not None:
                    raise RuntimeError("unexpected probe drawing view inventory")
                if any(Path(view["reference_path"]).resolve() != source for view in views[1:]):
                    raise RuntimeError("probe drawing references an unowned source")
                if len({row["title"] for row in rows}) != 2:
                    raise RuntimeError("ambiguous document titles")
                report["closure_witness"] = {"path": str(witness_path), "sha256": digest(witness_path)}
                report["closed_without_save"] = []
                checkpoint()
                for target in (drawing, part):
                    present = [_early_bound(raw, "IModelDoc2") for raw in app.GetDocuments() or ()]
                    current = [(str(doc.GetPathName()), str(doc.GetTitle())) for doc in present]
                    allowed = {(row["path"], row["title"]) for row in rows}
                    if any(pair not in allowed for pair in current):
                        raise RuntimeError("unowned document appeared during closure")
                    if (target["path"], target["title"]) not in current:
                        continue
                    app.CloseDoc(target["title"])
                    report["closed_without_save"].append({"path": target["path"], "title": target["title"]})
                    checkpoint()
                if app.GetDocuments() or app.ActiveDoc is not None:
                    raise RuntimeError("probe closure did not empty the session")
                if digest(source) != expected_source_hash:
                    raise RuntimeError("source bytes changed during probe closure")
                report["status"] = "owned_probe_closed_without_save_bytes_unchanged"
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
        if args.close_owned_probe_from:
            command.extend(["--close-owned-probe-from", str(args.close_owned_probe_from.resolve())])
        if args.close_production_from:
            command.extend(["--close-production-from", str(args.close_production_from.resolve())])
        if args.inventory_witness:
            command.extend(["--inventory-witness", str(args.inventory_witness.resolve())])
        dodo._exec(
            command,
            "VM2 datum read-only ownership",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
