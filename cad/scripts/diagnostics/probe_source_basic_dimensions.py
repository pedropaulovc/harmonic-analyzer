"""Copy-only control: persist imported BASIC dimensions on their source part.

Run ``uv run python cad/scripts/diagnostics/probe_source_basic_dimensions.py
channel-lever.SLDDRW``. The original drawing is never opened; its referenced
part is opened read-only for baseline readback. Author IDimensionTolerance.Type
only on a uniquely named byte copy of that part, save/reopen it, and relink a
CLOSED drawing copy with ISldWorks.ReplaceReferencedDocument. Native saved
before/after/reopened exports and all observations survive a failed witness.

The four named LeverOutline dimensions are this experiment's explicit scope.
No production drawing/part, coordinate, annotation layout, or value is changed.

R2026x positive control, 2026-09-06: the saved lever and its freshly read source
had type 0 for all four targets. Copied-part type 1 persisted through both part
and relinked drawing save/reopen; PDF/PNG restored all four boxes. All eleven
dimension values and supported geometry signatures stayed unchanged; original
part/drawing SHA-256 hashes matched. Untested: other releases and configurations.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
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

from _common import _early_bound, check, run_build  # noqa: E402
from _drawing_marks import _named_dimension  # noqa: E402
from diagnostics import probe_drawing_attachments as attachments  # noqa: E402
from diagnostics.probe_native_model_pmi import file_digest, render_pdf_png  # noqa: E402
import _telemetry  # noqa: E402

TARGETS = {"LeverOutline": ("BarLength", "TipCentreX", "NoseRadius", "TipRadius")}
BASIC = 1  # swTolType_e.swTolBASIC; IDimensionTolerance.Type is the current API.


def exact_document(model, path):
    actual = Path(model.GetPathName()).resolve()
    if actual != path:
        raise RuntimeError(
            f"wrong active native document: expected {path}, got {actual}"
        )


def tolerance(dimension):
    raw = dimension.Tolerance
    if raw is None:
        raise RuntimeError("dimension has no native tolerance interface")
    native = _early_bound(raw, "IDimensionTolerance")
    current, legacy = int(native.Type), int(dimension.GetToleranceType())
    if current != legacy:
        raise RuntimeError(
            f"native/legacy tolerance getters disagree: {current}/{legacy}"
        )
    return {
        "tolerance_type": current,
        "designation": "basic" if current == BASIC else "other",
    }


def part_dimensions(adapter, path, configuration):
    exact_document(adapter.currentModel, path)
    rows, handles = {}, {}
    for feature, names in TARGETS.items():
        for name in names:
            _, dimension = _named_dimension(adapter, feature, name)
            full_name = str(dimension.FullName)
            suffix = f"@{path.stem}.Part"
            if not full_name.casefold().endswith(suffix.casefold()):
                raise RuntimeError(
                    f"named dimension belongs to wrong part: {full_name}"
                )
            values = tuple(dimension.GetSystemValue3(3, configuration) or ())
            if len(values) != 1 or not math.isfinite(float(values[0])):
                raise RuntimeError(f"unreadable source system value: {name}: {values}")
            key = f"{name}@{feature}"
            rows[key] = {
                "full_name": full_name,
                "value_system": round(float(values[0]), 12),
                **tolerance(dimension),
            }
            handles[key] = dimension
    return rows, handles


def canonical_semantics(snapshot, part):
    """Normalize only the verified renamed part owner; all feature IDs stay exact."""
    result = deepcopy(snapshot)
    suffix = f"@{part.stem}.Part"
    for reference in result["models"].values():
        if Path(reference["path"]).resolve() != part:
            raise RuntimeError(f"drawing unexpectedly references {reference['path']}")
        reference["path"] = "<source-part>"
    for semantic in result["dimensions"].values():
        if semantic["kind"] != "model_dimension":
            continue
        for component in semantic["components"]:
            full = component["qualified_name"]
            if not full.casefold().endswith(suffix.casefold()):
                raise RuntimeError(
                    f"imported dimension has wrong verified owner: {full}"
                )
            component["qualified_name"] = full[: -len(suffix)] + "@<source-part>"
    return result


def drawing_dimensions(adapter, part):
    model = adapter.currentModel
    semantic = canonical_semantics(attachments.snapshot(model), part)
    rows = {}
    for view_key, view in attachments.views(model).items():
        for raw in view.GetAnnotationsByType(4) or ():
            annotation = _early_bound(raw, "IAnnotation")
            display = _early_bound(
                annotation.GetSpecificAnnotation(), "IDisplayDimension"
            )
            for index in range(2 if int(display.Type2) == 10 else 1):
                dimension = _early_bound(display.GetDimension2(index), "IDimension")
                key = f"{view_key}/{annotation.GetName()}/{index}"
                if key in rows:
                    raise RuntimeError(f"duplicate native dimension identity: {key}")
                rows[key] = {
                    "name": str(dimension.Name),
                    "full_name": str(dimension.FullName),
                    "owner_type": int(annotation.OwnerType),
                    "visibility": int(annotation.Visible),
                    "kind": "drawing_reference"
                    if display.IsReferenceDim()
                    else "model_dimension",
                    **tolerance(dimension),
                }
    return {"semantics": semantic, "dimensions": rows}


def assert_part(before, after, stage, expected_type=None):
    if before.keys() != after.keys():
        raise RuntimeError(f"{stage}: named source dimension inventory changed")
    for key, prior in before.items():
        current = after[key]
        if current["value_system"] != prior["value_system"]:
            raise RuntimeError(f"{stage}: {key}: actual dimension value changed")
        wanted = prior["tolerance_type"] if expected_type is None else expected_type
        if current["tolerance_type"] != wanted:
            raise RuntimeError(
                f"{stage}: {key}: tolerance {current['tolerance_type']} != {wanted}"
            )


def assert_drawing(before, after, stage, expected_type=None):
    expected = {
        f"{name}@{feature}" for feature, names in TARGETS.items() for name in names
    }
    expected_semantics = deepcopy(before["semantics"])
    if expected_type is not None:
        # These exact source designations are the ONLY expected semantic change.
        for semantic in expected_semantics.get("dimensions", {}).values():
            if semantic["kind"] != "model_dimension":
                continue
            for component in semantic["components"]:
                if component["qualified_name"].rsplit("@", 1)[0] in expected:
                    component["tolerance_type"] = expected_type
                    component["designation"] = (
                        "basic" if expected_type == BASIC else "other"
                    )
    attachments.compare(expected_semantics, after["semantics"], stage)
    prior_rows, rows = before["dimensions"], after["dimensions"]
    if prior_rows.keys() != rows.keys():
        raise RuntimeError(f"{stage}: display dimension inventory changed")
    found = []
    for key, prior in prior_rows.items():
        current = rows[key]
        for field in ("name", "kind", "owner_type", "visibility"):
            if current[field] != prior[field]:
                raise RuntimeError(f"{stage}: {key}: {field} changed")
        identity = current["full_name"].rsplit("@", 1)[0]
        target = current["kind"] == "model_dimension" and identity in expected
        if target:
            found.append(identity)
        wanted = (
            expected_type
            if target and expected_type is not None
            else prior["tolerance_type"]
        )
        if current["tolerance_type"] != wanted:
            raise RuntimeError(
                f"{stage}: {key}: tolerance {current['tolerance_type']} != {wanted}"
            )
    if set(found) != expected or len(found) != len(expected):
        raise RuntimeError(
            f"{stage}: missing/duplicate target coverage: expected {expected}, got {found}"
        )


def save_part(adapter, path):
    exact_document(adapter.currentModel, path)
    # Generated IModelDoc2.Save3 returns (success, errors, warnings).
    result = adapter.currentModel.Save3(
        1, 0, 0
    )  # swSaveAsOptions_Silent, NOT SaveReferenced
    if (
        not isinstance(result, tuple)
        or len(result) != 3
        or not result[0]
        or int(result[1]) != 0
    ):
        raise RuntimeError(f"in-place copied part Save3 failed: {result!r}")
    return {
        "success": bool(result[0]),
        "errors": int(result[1]),
        "warnings": int(result[2]),
    }


async def probe(adapter, source, directory):
    from solidworks_mcp.adapters.solidworks.drawing import save_drawing

    app = _early_bound(adapter.swApp, "ISldWorks")
    report = {
        "source": str(source),
        "source_hashes": {str(source): file_digest(source)},
    }
    report_path = directory / "source-basic-dimensions.json"
    drawing_copy = directory / f"{directory.name}-source.SLDDRW"
    part_copy = directory / f"{directory.name}-part.SLDPRT"
    shutil.copy2(source, drawing_copy)

    def close():
        if not app.CloseAllDocuments(True):
            raise RuntimeError(
                "could not close native documents for isolated BASIC control"
            )
        adapter.currentModel = None

    async def open_copy(path):
        close()
        check("open unique BASIC control copy", await adapter.open_model(str(path)))
        exact_document(adapter.currentModel, path)

    def export(stage):
        output = directory / f"{directory.name}-{stage}.SLDDRW"
        if (
            output.exists()
            or Path(adapter.currentModel.GetPathName()).resolve() == output
        ):
            raise RuntimeError(
                "drawing export must use a NEW destination, never an open file"
            )
        pdf, png = output.with_suffix(".pdf"), output.with_suffix(".png")
        save_drawing(adapter, str(output), pdf_path=str(pdf))
        render_pdf_png(pdf, png)
        report.setdefault("exports", {})[stage] = {
            "drawing": str(output),
            "pdf": str(pdf),
            "png": str(png),
        }
        return output

    try:
        await open_copy(drawing_copy)
        references = {
            tuple(attachments.referenced_model(view).items())
            for view in attachments.views(adapter.currentModel).values()
        }
        if len(references) != 1:
            raise RuntimeError(
                f"control needs exactly one source part/configuration: {references}"
            )
        reference = dict(references.pop())
        part = Path(reference["path"]).resolve(strict=True)
        configuration = reference["configuration"]
        report["source_hashes"][str(part)] = file_digest(part)
        report["drawing_before"] = drawing_dimensions(adapter, part)
        assert_drawing(
            report["drawing_before"], report["drawing_before"], "drawing baseline"
        )
        export("before")
        close()
        # Read the actual source saved file freshly and explicitly READ ONLY.
        opened = app.OpenDoc6(
            str(part), 1, 3, configuration, 0, 0
        )  # PART; Silent|ReadOnly
        if (
            not isinstance(opened, tuple)
            or len(opened) != 3
            or opened[0] is None
            or int(opened[1]) != 0
        ):
            raise RuntimeError(f"read-only source part OpenDoc6 failed: {opened!r}")
        adapter.currentModel = _early_bound(opened[0], "IModelDoc2")
        report["source_part_before"], _ = part_dimensions(adapter, part, configuration)
        close()
        shutil.copy2(
            part, part_copy
        )  # matching internal document ID; never rebuild a replacement
        await open_copy(part_copy)
        report["copied_part_before"], handles = part_dimensions(
            adapter, part_copy, configuration
        )
        assert_part(
            report["source_part_before"],
            report["copied_part_before"],
            "byte copied source",
        )
        started = time.perf_counter()
        exact_document(adapter.currentModel, part_copy)
        for dimension in handles.values():
            _early_bound(dimension.Tolerance, "IDimensionTolerance").Type = BASIC
        adapter.currentModel.GraphicsRedraw2()
        report["copied_part_authored"], _ = part_dimensions(
            adapter, part_copy, configuration
        )
        assert_part(
            report["copied_part_before"],
            report["copied_part_authored"],
            "part authoring",
            BASIC,
        )
        report["part_save"] = save_part(adapter, part_copy)
        report["author_and_save_seconds"] = time.perf_counter() - started
        await open_copy(part_copy)
        report["copied_part_reopened"], _ = part_dimensions(
            adapter, part_copy, configuration
        )
        assert_part(
            report["copied_part_before"],
            report["copied_part_reopened"],
            "part save/reopen",
            BASIC,
        )
        close()
        if not part_copy.is_file():
            raise RuntimeError("closed-document relink target does not exist")
        if not app.ReplaceReferencedDocument(
            str(drawing_copy), str(part), str(part_copy)
        ):
            raise RuntimeError(
                "closed drawing ReplaceReferencedDocument rejected copied source"
            )
        await open_copy(drawing_copy)
        report["drawing_relinked"] = drawing_dimensions(adapter, part_copy)
        assert_drawing(
            report["drawing_before"],
            report["drawing_relinked"],
            "relinked drawing",
            BASIC,
        )
        output = export("after")
        await open_copy(output)
        report["drawing_reopened"] = drawing_dimensions(adapter, part_copy)
        assert_drawing(
            report["drawing_relinked"],
            report["drawing_reopened"],
            "drawing save/reopen",
            BASIC,
        )
        export("reopened")
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", operation_error=repr(error))
        raise
    finally:
        try:
            close()
        finally:
            report["source_hashes_after"] = {
                name: file_digest(Path(name)) for name in report["source_hashes"]
            }
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            _telemetry.info(f"source BASIC dimension observations: {report_path}")
            if report["source_hashes"] != report["source_hashes_after"]:
                raise RuntimeError(
                    "BASIC control changed an original source part or drawing"
                )
    return {"report": str(report_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    source = args.drawing.resolve(strict=True)
    if source.suffix.upper() != ".SLDDRW":
        raise ValueError("requires a native part drawing")
    if not args.worker:
        sys.path.insert(0, str(ROOT))
        import dodo

        dodo._run(
            [sys.executable, str(Path(__file__).resolve()), str(source), "--worker"],
            "source BASIC dimension persistence",
            com=True,
            log_stem="source-basic-dimensions",
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("worker requires the parent COM seat lock")
    reports = ROOT / "cad/out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="source-basic-dimensions-", dir=reports))
    return run_build(lambda adapter: probe(adapter, source, directory))


if __name__ == "__main__":
    raise SystemExit(main())
