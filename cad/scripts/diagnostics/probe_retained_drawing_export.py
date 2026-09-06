"""One no-setter cold-reopen/PDF-export observation of a retained rocker pilot.

No recipe, layout/default writes, rebuild, relink, or native drawing/source save.
Only a unique bytecopy of the retained SLDDRW is opened; its exact saved part
reference and all original inputs are protected by the shared owned lifecycle.
The production adapter's save_drawing skips an empty native-drawing target and
executes its existing PDF SaveAs3 branch once. Actual native path/identity and
input hashes must remain exact. Existing user documents are never cleared.

Title position differences are reported, not accepted as a representation
tolerance. Printed PDF glyph boxes and PNG pixels are independent observations.
Requires explicit seat grant, expected existing PID and AUTOSTART=0 before dodo.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check  # noqa: E402
from _drawing_common import render_pdf_png  # noqa: E402
from diagnostics import probe_datum_policy_recipes as pilot  # noqa: E402
from diagnostics.audit_drawing_snapshot_delta import audit_pair, changed_leaves  # noqa: E402
from diagnostics._owned_native_documents import run_copy_diagnostic  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment  # noqa: E402
from solidworks_mcp.adapters.solidworks.drawing import save_drawing as native_save  # noqa: E402
import _telemetry  # noqa: E402

EXPECTED_RECEIPT_SHA256 = (
    "a924f8259c3f3fc5049a19b2b6715cbaffeb863f003f075e61438fd0ae483feb"
)
EXPECTED_ARTIFACT_HASHES = {
    "drawing": "6e7a8b4b4d897b64ba856959c48fa3cafd99ca99461980a7ba52c56942e02c49",
    "pdf": "012066e547a5a0eba5d978a52b94d351f3de68ce7a3adae59d703c1f43adb1e0",
    "png": "86ddea93b4a5cfcc9a3f6f0b7a036359c79988eb982865b229b2c60104332f18",
}
TITLE_KEY = "Sheet1/DetailItem245"


def read_retained(receipt):
    if pilot.attachments.file_digest(receipt) != EXPECTED_RECEIPT_SHA256:
        raise RuntimeError("retained pilot receipt is not the reviewed exact input")
    result = json.loads(receipt.read_text(encoding="utf-8"))
    trial = result["trials"][0]
    if trial["target"] != "rocker_arm" or len(result["trials"]) != 1:
        raise RuntimeError("retained control requires the reviewed first rocker trial")
    paths = {
        key: Path(value).resolve(strict=True)
        for key, value in trial["artifacts"].items()
    }
    part = Path(trial["copy_source"]).resolve(strict=True)
    expected = dict(result["sources_before"])
    expected[str(part)] = trial["copy_hashes"]["copied"]
    expected[str(receipt)] = EXPECTED_RECEIPT_SHA256
    if paths.keys() != EXPECTED_ARTIFACT_HASHES.keys():
        raise RuntimeError(
            "retained artifact inventory differs from the reviewed input"
        )
    for kind, path in paths.items():
        expected[str(path)] = EXPECTED_ARTIFACT_HASHES[kind]
    return result, trial, paths, part, expected


def hashes(expected):
    return {path: pilot.attachments.file_digest(Path(path)) for path in expected}


def final_hashes(expected):
    result = {}
    for path in expected:
        try:
            result[path] = pilot.attachments.file_digest(Path(path))
        except OSError as error:
            result[path] = {"error": repr(error)}
    return result


def require_hashes(expected, phase):
    actual = hashes(expected)
    if actual != expected:
        raise RuntimeError(
            f"{phase}: protected retained native/output/source hash changed"
        )
    return actual


def capture_drawing(adapter, part, configuration):
    semantics = pilot.attachments.snapshot(adapter.currentModel, app=adapter.swApp)
    if not semantics["models"] or any(
        Path(row["path"]).resolve() != part or row["configuration"] != configuration
        for row in semantics["models"].values()
    ):
        raise RuntimeError(
            "retained drawing view uses the wrong exact source/configuration"
        )
    rows, handles = pilot.shoulder.all_annotation_layout(adapter)
    return {
        "semantics": semantics,
        "annotations": rows,
        "layout": pilot.attachments.layout(adapter.currentModel),
    }, handles


def title_fields(adapter):
    matches = []
    for sheet in _early_bound(adapter.currentModel, "IDrawingDoc").GetViews() or ():
        for raw_view in sheet:
            view = _early_bound(raw_view, "IView")
            for raw in view.GetAnnotations() or ():
                annotation = _early_bound(raw, "IAnnotation")
                if f"{view.GetName2()}/{annotation.GetName()}" == TITLE_KEY:
                    matches.append(annotation)
    if len(matches) != 1:
        raise RuntimeError("retained title annotation is not unique")
    annotation = matches[0]
    if int(annotation.GetType()) != 6 or int(annotation.OwnerType) != 2:
        raise RuntimeError("retained title must remain an exact sheet-format note")
    note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
    extent = tuple(float(value) for value in note.GetExtent() or ())
    if len(extent) != 6 or not all(math.isfinite(value) for value in extent):
        raise RuntimeError("visible title note has invalid native sheet extent")
    # Standard-note getter contracts read from the bundled SW2026 INote docs.
    # TextRightToLeft is intentionally not called: documented Hebrew-only.
    result = {
        "text": str(note.GetText()),
        "linked_text": str(note.PropertyLinkedText),
        "horizontal_justification": int(note.GetTextJustification()),
        "vertical_justification": int(note.GetTextVerticalJustification()),
        "locked": bool(note.LockPosition),
        "extent": extent,
        "position": tuple(annotation.GetPosition() or ()),
    }
    if result["text"] != "rocker-arm":
        raise RuntimeError(f"retained title content changed: {result}")
    if result["horizontal_justification"] not in (0, 1, 2, 3) or result[
        "vertical_justification"
    ] not in (0, 1, 2):
        raise RuntimeError(
            f"retained title has an unsupported standard-note alignment: {result}"
        )
    if len(result["position"]) != 3 or not all(
        math.isfinite(value) for value in result["position"]
    ):
        raise RuntimeError("retained title has an invalid native annotation position")
    return result


def export_pdf_only(adapter, pdf):
    adapter.ownership.assert_current_owned()
    if (
        pdf.suffix.lower() != ".pdf"
        or pdf.exists()
        or pdf.parent not in adapter.ownership.directories
    ):
        raise RuntimeError(
            "PDF export requires a new target inside the registered owned directory"
        )
    model = adapter.currentModel
    path = str(model.GetPathName())
    with _telemetry.span("diagnostic.retained_export.pdf"):
        # The inspected production helper skips false/empty targets before any
        # filesystem operation. Its PDF branch is identical to recipe export.
        artifacts = native_save(adapter, "", pdf_path=str(pdf))
    adapter.ownership.assert_current_owned()
    if (
        int(adapter.swApp.IsSame(model, adapter.currentModel)) != 1
        or str(model.GetPathName()) != path
    ):
        raise RuntimeError("PDF export changed the exact owned native drawing/path")
    if artifacts != {"pdf": str(pdf)} or not pdf.is_file():
        raise RuntimeError("production PDF-only export produced unexpected artifacts")
    return artifacts


def pdf_title(path, text="rocker-arm"):
    """Native PDF glyph ink boxes; local PDFium only, no SolidWorks or edits."""
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(path))
    try:
        if len(document) != 1:
            raise RuntimeError("retained title comparison requires one PDF page")
        page = document[0]
        textpage = page.get_textpage()
        search = textpage.search(text, match_case=True, match_whole_word=True)
        match = search.get_next()
        if match is None or search.get_next() is not None:
            raise RuntimeError("PDF must contain one exact readable rocker-arm title")
        index, count = match
        characters = [
            {"text": textpage.get_text_range(i, 1), "box_pt": textpage.get_charbox(i)}
            for i in range(index, index + count)
        ]
        boxes = [row["box_pt"] for row in characters]
        return {
            "page_size_pt": page.get_size(),
            "text": textpage.get_text_range(index, count),
            "ink_box_pt": (
                min(row[0] for row in boxes),
                min(row[1] for row in boxes),
                max(row[2] for row in boxes),
                max(row[3] for row in boxes),
            ),
            "characters": characters,
        }
    finally:
        document.close()


def compare_png(before, after):
    from PIL import Image, ImageChops

    with Image.open(before) as old, Image.open(after) as new:
        if old.size != new.size:
            raise RuntimeError("retained/exported PNG dimensions differ")
        difference = ImageChops.difference(old.convert("RGB"), new.convert("RGB"))
        red, green, blue = difference.split()
        peak = ImageChops.lighter(ImageChops.lighter(red, green), blue)
        changed = old.width * old.height - peak.histogram()[0]
        return {
            "size": old.size,
            "changed_pixel_count": changed,
            "changed_pixel_bounds": difference.getbbox(),
            "max_channel_delta": max(high for _, high in difference.getextrema()),
        }


async def probe(adapter, receipt, output_root):
    _, trial, paths, part, expected = read_retained(receipt)
    require_hashes(expected, "before native open")
    output_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="retained-export-", dir=output_root))
    adapter.ownership.register_directory(directory)
    for path in expected:
        adapter.ownership.register_source(Path(path))
    copy = directory / f"{directory.name}.SLDDRW"
    pdf, png = copy.with_suffix(".pdf"), copy.with_suffix(".png")
    report_path = directory / "retained-export.json"
    report = {
        "status": "running",
        "receipt": str(receipt),
        "inputs_before": expected,
        "copy": str(copy),
        "artifacts": {"pdf": str(pdf), "png": str(png)},
        "scope": "one reopen and PDF-only export; no setter/rebuild/native save; not whole-sheet visual acceptance",
        "helper_revision": pilot.benchmark.revision("HEAD"),
        "imported_adapter": pilot.adapter_fingerprints(),
    }

    def checkpoint():
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    checkpoint()
    _telemetry.info("retained no-setter export report", path=str(report_path))
    try:
        report["original_pdf_title"] = pdf_title(paths["pdf"])
        shutil.copy2(paths["drawing"], copy)
        copy_expected = {str(copy): expected[str(paths["drawing"])]}
        require_hashes(copy_expected, "drawing bytecopy")
        check("open unique retained drawing copy", await adapter.open_model(str(copy)))
        adapter.ownership.assert_current_owned()
        report["title_before"] = title_fields(adapter)
        report["before_export"], before_handles = capture_drawing(
            adapter, part, trial["source_before"]["configuration"]
        )
        source_model = adapter.swApp.GetOpenDocumentByName(str(part))
        report["source_before"], source_handles = pilot.source_dimensions(
            source_model, "rocker_arm", part
        )
        pilot.require_same_source(
            trial["source_before"],
            report["source_before"],
            "retained source cold reopen",
        )
        pilot.attachments.compare(
            trial["built"]["semantics"],
            report["before_export"]["semantics"],
            "retained cold reopen",
        )
        pilot.attachments.check_layout(
            trial["built"]["layout"],
            report["before_export"]["layout"],
            "retained cold reopen",
        )
        report["built_to_reopened"] = audit_pair(
            trial["built"], report["before_export"]
        )
        require_hashes(expected, "before PDF export")
        checkpoint()
        export_pdf_only(adapter, pdf)
        report["title_after"] = title_fields(adapter)
        report["after_export"], after_handles = capture_drawing(
            adapter, part, trial["source_before"]["configuration"]
        )
        report["source_after"], source_after_handles = pilot.source_dimensions(
            source_model, "rocker_arm", part
        )
        report["export_delta"] = audit_pair(
            report["before_export"], report["after_export"]
        )
        report["title_delta"] = changed_leaves(
            report["title_before"], report["title_after"]
        )
        render_pdf_png(pdf, png)
        report["reopened_pdf_title"] = pdf_title(pdf)
        report["pdf_title_delta"] = changed_leaves(
            report["original_pdf_title"], report["reopened_pdf_title"]
        )
        report["png_delta"] = compare_png(paths["png"], png)
        checkpoint()
        # No generic comparator relaxation: any newly observed export effect
        # still fails this witness, after all diagnostic artifacts are retained.
        pilot.shoulder.compare_all_annotation_layout(
            adapter.swApp,
            report["before_export"]["annotations"],
            report["after_export"]["annotations"],
            before_handles,
            after_handles,
        )
        pilot.require_same_source(
            report["source_before"],
            report["source_after"],
            "PDF export source",
            app=adapter.swApp,
            handles_before=source_handles,
            handles_after=source_after_handles,
        )
        pilot.compare_drawing(
            adapter.swApp, report["before_export"], report["after_export"]
        )
        if report["title_delta"]:
            raise RuntimeError(
                "PDF export changed title getter fields; see retained delta"
            )
        require_hashes(expected, "after PDF export")
        require_hashes(copy_expected, "after PDF export native drawing")
        if report["imported_adapter"] != pilot.adapter_fingerprints():
            raise RuntimeError("actual imported adapter changed during retained export")
        await adapter.close_owned_documents()
        require_hashes(copy_expected, "after no-save owned close")
        report["status"] = "observed"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        report["inputs_after"] = final_hashes(expected)
        report["copy_after"] = final_hashes((str(copy),))[str(copy)]
        checkpoint()
    return {"report": str(report_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--report-root", type=Path, default=ROOT / "cad/out/reports")
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args(argv)
    require_owned_diagnostic_environment()
    receipt = args.receipt.resolve(strict=True)
    read_retained(receipt)  # Exact reviewed receipt before the native parent wrapper.
    if not args.worker:
        import dodo

        dodo._run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--receipt",
                str(receipt),
                "--report-root",
                str(args.report_root.resolve()),
                "--worker",
            ],
            "retained drawing no-setter export",
            com=True,
            log_stem="retained-drawing-export",
        )
        return 0
    return run_copy_diagnostic(
        lambda adapter: probe(adapter, receipt, args.report_root.resolve())
    )


if __name__ == "__main__":
    raise SystemExit(main())
