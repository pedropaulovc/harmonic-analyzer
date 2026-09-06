"""Positive control: import unchanged plain part PMI at SolidWorks-native locations.

Run with ``uv run python cad/scripts/diagnostics/probe_native_model_pmi.py
<built-transgear-stub.SLDPRT>``. The parent takes the normal COM seat lock; the
worker opens only a uniquely named part copy and creates a new drawing. No model
or sheet annotation coordinates are written. Outputs and observations survive a
failed witness in a unique ``cad/out/reports/native-model-pmi-*`` directory.

This follows the official Get Annotations Arrays C# example: native third-angle
views, then InsertModelAnnotations3 for GTols and datums with AllViews enabled.
DuplicateDims suppresses duplicate *dimensions*, not a promise about other PMI:
the probe independently counts every imported semantic item. A passing machine
witness still requires inspection of both exported PNGs; Visible alone cannot
prove that text is rendered, unoccluded, or readable.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad/scripts"))

import _telemetry  # noqa: E402
from _common import _early_bound, check, run_build  # noqa: E402
from _drawing_common import render_pdf_png  # noqa: E402
from _gtol_spec import gtol_frame_signature  # noqa: E402
from _part_pmi import _face_geometry, _face_matches, _resolve_faces  # noqa: E402
from transgear_stub_spec import GEOMETRIC_CONTROLS, PART_DATUMS  # noqa: E402

ROWS = (*PART_DATUMS, *GEOMETRIC_CONTROLS)
BY_KEY = {row.key: row for row in ROWS}
_DATUM, _GTOL = 2, 5  # swAnnotationType_e
_OWNER_VIEW, _OWNER_PART = 0, 3  # swAnnotationOwner_e


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _expected_signature(row: Any) -> Any:
    if row.key.startswith("datum:"):
        return ("datum", row.letter)
    return ("gtol", asdict(gtol_frame_signature(row.frame_xml)))


def _signature(annotation: Any, kind: int) -> Any:
    raw = annotation.GetSpecificAnnotation()
    if raw is None:
        raise RuntimeError("plain annotation has no specific annotation interface")
    if kind == _DATUM:
        return ("datum", str(_early_bound(raw, "IDatumTag").GetLabel()))
    gtol = _early_bound(raw, "IGtol")
    if int(gtol.GetFormat()) != 2:  # swGtolFormatType_e.GTOL_SW2022
        raise RuntimeError("imported FCF is not in the source's SW2022 format")
    count = int(gtol.GetFrameCount())
    if count != 1:
        raise RuntimeError(f"expected one authored FCF frame, got {count}")
    frame = _early_bound(gtol.GetFrame(1), "IGtolFrame")
    return ("gtol", asdict(gtol_frame_signature(str(frame.GetSymbolXml() or ""))))


def _annotation_record(
    app: Any,
    annotation: Any,
    model: Any,
    faces: dict,
    *,
    view: Any = None,
    sheet_size: tuple | None = None,
) -> dict:
    """Read witnesses only; null/different identities are never silently accepted."""
    item = _early_bound(annotation, "IAnnotation")
    kind = int(item.GetType())
    signature = _signature(item, kind)
    keys = [row.key for row in ROWS if _expected_signature(row) == signature]
    key = keys[0] if len(keys) == 1 else None
    entities = tuple(item.GetAttachedEntities3() or ())
    types = tuple(int(value) for value in item.GetAttachedEntityTypes() or ())
    position = tuple(float(value) for value in item.GetPosition() or ())
    owner_type = int(item.OwnerType)
    expected_owner = model if owner_type == _OWNER_PART else view
    owner_same = (
        int(app.IsSame(item.Owner, expected_owner))
        if owner_type in (_OWNER_VIEW, _OWNER_PART) and expected_owner is not None
        else None
    )
    record = {
        "name": str(item.GetName()),
        "type": kind,
        "key": key,
        "signature": signature,
        "is_dimxpert": bool(item.IsDimXpert()),
        "visible": int(item.Visible),
        "dangling": bool(item.IsDangling()),
        "position_m": position,
        "owner_type": owner_type,
        "owner_identity": owner_same,
        "view": str(view.GetName2()) if view is not None else None,
        "attachment_count": len(entities),
        "attachment_types": types,
        "null_entities": sum(entity is None for entity in entities),
        "face_identity": None,
        "face_spec_matches": None,
    }
    if (
        key is not None
        and len(entities) == 1
        and types == (2,)
        and entities[0] is not None
    ):
        record["face_identity"] = int(app.IsSame(faces[key], entities[0]))
        geometry = _face_geometry(entities[0])
        record["face_spec_matches"] = geometry is not None and _face_matches(
            geometry, BY_KEY[key].face
        )
    if sheet_size is not None:
        record["anchor_on_sheet"] = (
            len(position) == 3
            and all(math.isfinite(value) for value in position)
            and 0 <= position[0] <= sheet_size[0]
            and 0 <= position[1] <= sheet_size[1]
        )
    return record


def witness_failures(records: list[dict], *, stage: str) -> list[str]:
    """Pure witness evaluator, intentionally separate from the COM observations."""
    failures = []
    counts = Counter(record["key"] for record in records)
    for key in BY_KEY:
        if counts[key] != 1:
            failures.append(f"{stage}: coverage {key}={counts[key]}, expected 1")
    for record in records:
        label = f"{stage}: {record['view']}/{record['name']}"
        if record["key"] not in BY_KEY:
            failures.append(f"{label}: unrecognized or ambiguous annotation semantics")
        for field, expected in (
            ("is_dimxpert", False),
            ("dangling", False),
            ("owner_identity", 1),
            ("attachment_count", 1),
            ("null_entities", 0),
            ("face_identity", 1),
            ("face_spec_matches", True),
        ):
            if record[field] != expected:
                failures.append(
                    f"{label}: {field}={record[field]!r}, expected {expected!r}"
                )
        if tuple(record["attachment_types"]) != (2,):
            failures.append(f"{label}: expected the source's one FACE attachment")
        if stage != "source" and record["visible"] != 1:
            failures.append(f"{label}: visible={record['visible']}, expected 1")
        position = record["position_m"]
        if len(position) != 3 or not all(math.isfinite(value) for value in position):
            failures.append(f"{label}: position is not a finite 3-vector")
        if stage == "source" and record["key"] in BY_KEY:
            expected_name = BY_KEY[record["key"]].annotation_name
            if record["name"] != expected_name:
                failures.append(f"{label}: source name is not {expected_name}")
        if record.get("anchor_on_sheet") is False:
            failures.append(f"{label}: native anchor is outside the sheet")
    return failures


def source_snapshot(app: Any, model: Any) -> list[dict]:
    faces = _resolve_faces(model, {row.key: row.face for row in ROWS})
    records = []
    raw = model.GetFirstAnnotation2()
    while raw is not None:
        item = _early_bound(raw, "IAnnotation")
        if int(item.GetType()) in (_DATUM, _GTOL):
            records.append(_annotation_record(app, item, model, faces))
        raw = item.GetNext3()
    return records


def drawing_snapshot(app: Any, drawing: Any, copy: Path) -> dict:
    sheets = tuple(drawing.GetViews() or ())
    if len(sheets) != 1 or len(sheets[0]) != 4:
        raise RuntimeError("positive control requires one sheet and three native views")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    props = tuple(sheet.GetProperties2() or ())
    if len(props) != 8 or not all(float(value) > 0 for value in props[5:7]):
        raise RuntimeError(f"unreadable native sheet dimensions: {props}")
    records, views = [], []
    for raw in sheets[0][1:]:
        view = _early_bound(raw, "IView")
        model = _early_bound(view.ReferencedDocument, "IModelDoc2")
        if Path(model.GetPathName()).resolve() != copy:
            raise RuntimeError(
                "native view references a document other than the isolated copy"
            )
        faces = _resolve_faces(model, {row.key: row.face for row in ROWS})
        views.append(
            {
                "name": str(view.GetName2()),
                "outline_m": tuple(view.GetOutline()),
                "source": str(model.GetPathName()),
            }
        )
        for kind in (_DATUM, _GTOL):
            for item in view.GetAnnotationsByType(kind) or ():
                records.append(
                    _annotation_record(
                        app, item, model, faces, view=view, sheet_size=props[5:7]
                    )
                )
    return {"sheet_properties": props, "views": views, "annotations": records}


def import_native_pmi(drawing: Any) -> list[dict]:
    """Exact official example call shape; no annotation creation or layout setter."""
    imports = []
    for label, mask in (("gtols", 32), ("datums", 2)):  # swInsertAnnotation_e
        start = time.perf_counter()
        with _telemetry.span("diagnostic.native_pmi_import", annotation_kind=label):
            result = drawing.InsertModelAnnotations3(0, mask, True, True, False, True)
        if isinstance(result, str):
            raise RuntimeError(
                f"native {label} import returned text, not annotations: {result}"
            )
        imports.append(
            {
                "kind": label,
                "returned_count": len(tuple(result or ())),
                "seconds": time.perf_counter() - start,
            }
        )
    return imports


def _close(app: Any, adapter: Any) -> None:
    if not app.CloseAllDocuments(True):
        raise RuntimeError("failed to close the isolated diagnostic documents")
    adapter.currentModel = None


async def probe(adapter: Any, source: Path, directory: Path) -> dict[str, str]:
    from solidworks_mcp.adapters.solidworks.drawing import new_drawing, save_drawing

    report: dict[str, Any] = {
        "source": str(source),
        "visual_review": "pending",
        "failures": [],
    }
    copy = directory / f"{directory.name}-transgear-stub.SLDPRT"
    report_path = directory / "observations.json"
    digest = file_digest(source)
    shutil.copy2(source, copy)
    if file_digest(copy) != digest:
        raise RuntimeError("source changed while making the isolated copy")
    app = _early_bound(adapter.swApp, "ISldWorks")
    start = time.perf_counter()
    try:
        check("open unique PMI source copy", await adapter.open_model(str(copy)))
        if Path(adapter.currentModel.GetPathName()).resolve() != copy:
            raise RuntimeError("SolidWorks did not open the unique source copy")
        report["source_annotations"] = source_snapshot(app, adapter.currentModel)
        source_errors = witness_failures(report["source_annotations"], stage="source")
        report["failures"].extend(source_errors)
        if source_errors:
            raise RuntimeError(
                "source positive control is not the expected authored part"
            )
        new_drawing(adapter)
        drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
        view_start = time.perf_counter()
        with _telemetry.span("diagnostic.native_pmi_views"):
            if not drawing.Create3rdAngleViews2(str(copy)):
                raise RuntimeError("Create3rdAngleViews2 rejected the source copy")
        report["view_seconds"] = time.perf_counter() - view_start
        report["imports"] = import_native_pmi(drawing)
        for stage in ("initial", "reopened"):
            snapshot = drawing_snapshot(app, drawing, copy)
            report[stage] = snapshot
            report["failures"].extend(
                witness_failures(snapshot["annotations"], stage=stage)
            )
            native = directory / f"{directory.name}-{stage}.SLDDRW"
            pdf, png = native.with_suffix(".pdf"), native.with_suffix(".png")
            export_start = time.perf_counter()
            with _telemetry.span("diagnostic.native_pmi_export", stage=stage):
                save_drawing(adapter, str(native), pdf_path=str(pdf))
                render_pdf_png(pdf, png)
            snapshot["exports"] = {
                "drawing": str(native),
                "pdf": str(pdf),
                "png": str(png),
            }
            snapshot["export_seconds"] = time.perf_counter() - export_start
            if stage == "initial":
                _close(app, adapter)
                check(
                    "reopen native PMI drawing", await adapter.open_model(str(native))
                )
                if Path(adapter.currentModel.GetPathName()).resolve() != native:
                    raise RuntimeError("SolidWorks reopened a different drawing")
                drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
        report["machine_witness"] = "passed" if not report["failures"] else "failed"
    except Exception as error:
        report["operation_error"] = repr(error)
        raise
    finally:
        try:
            _close(app, adapter)
        finally:
            report["seconds"] = time.perf_counter() - start
            report["sha256_before"] = digest
            report["source_sha256_after"] = file_digest(source)
            report["copy_sha256_after"] = file_digest(copy)
            for label in ("source", "copy"):
                if report[f"{label}_sha256_after"] != digest:
                    report["failures"].append(
                        f"{label} file changed during native PMI import"
                    )
            report["machine_witness"] = (
                "failed"
                if report["failures"] or "operation_error" in report
                else "passed"
            )
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            _telemetry.info(f"native model PMI observations: {report_path}")
    if report["failures"]:
        raise RuntimeError(
            "native PMI witness failed: " + "; ".join(report["failures"])
        )
    return {"report": str(report_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="built transgear-stub.SLDPRT")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    if source.suffix.upper() != ".SLDPRT":
        raise ValueError("the probe requires the built transgear-stub native part")
    if not args.worker:
        sys.path.insert(0, str(ROOT))
        import dodo

        dodo._run(
            [sys.executable, str(Path(__file__).resolve()), str(source), "--worker"],
            "native model PMI import positive control",
            com=True,
            log_stem="native-model-pmi-probe",
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("diagnostic worker requires the parent COM seat lock")
    reports = ROOT / "cad/out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="native-model-pmi-", dir=reports))
    _telemetry.set_service("native-model-pmi-probe")
    return run_build(lambda adapter: probe(adapter, source, directory))


if __name__ == "__main__":
    raise SystemExit(main())
