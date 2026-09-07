"""Copy-only visible/hidden/visible PDF ink witness for cosmetic threads.

This is a diagnostic, not a production no-ink exemption. Both native display
data interfaces returned zero primitives on the saved screw; compare actual
exports before drawing any conclusion about rendered geometry. Source drawing
and referenced model bytes are guarded. All saved drawings are unique copies.
"""

from __future__ import annotations

import argparse
import hashlib
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
from _drawing_common import render_pdf_png
from probe_drawing_primitive_annotations import capture
from diagnostics._owned_native_documents import save_drawing
import _telemetry


def ink_difference(first: Path, second: Path) -> dict[str, Any]:
    """Compare actual rasterized exports; no generated or nominal geometry."""
    from PIL import Image, ImageChops

    with Image.open(first) as left, Image.open(second) as right:
        if left.size != right.size:
            raise ValueError("thread ink witness page dimensions differ")
        difference = ImageChops.difference(left.convert("RGB"), right.convert("RGB"))
        extrema = difference.getextrema()
        return {
            "page_pixels": left.size,
            "difference_box_pixels": difference.getbbox(),
            "max_channel_difference": max(value[1] for value in extrema),
        }


def vector_witness(path: Path) -> dict[str, Any]:
    """Record PDF path geometry/style, including subpixel strokes.

    PDFium's official public/fpdf_edit.h defines the segment coordinates,
    close flags, stroke width/colors and draw-mode out parameters used here:
    https://raw.githubusercontent.com/chromium/pdfium/main/public/fpdf_edit.h
    Non-path objects retain native type/bounds/matrix; the independent raster
    witness observes their rendered ink rather than claiming glyph identity.
    """
    import ctypes
    import pypdfium2 as pdfium
    import pypdfium2.raw as api

    document = pdfium.PdfDocument(path)
    objects = []
    try:
        if len(document) != 1:
            raise ValueError("thread vector witness requires one drawing sheet")
        page = document[0]
        for obj in page.get_objects():
            row = {
                "kind": obj.type,
                "level": obj.level,
                "bounds": obj.get_bounds(),
                "matrix": obj.get_matrix().get(),
            }
            objects.append(row)
            if obj.type != api.FPDF_PAGEOBJ_PATH:
                continue
            count = api.FPDFPath_CountSegments(obj)
            if count < 0:
                raise RuntimeError("PDFium could not count path segments")
            segments = []
            for index in range(count):
                segment = api.FPDFPath_GetPathSegment(obj, index)
                if not segment:
                    raise RuntimeError("PDFium returned a missing path segment")
                x, y = ctypes.c_float(), ctypes.c_float()
                if not api.FPDFPathSegment_GetPoint(segment, x, y):
                    raise RuntimeError("PDFium path coordinate read failed")
                segments.append(
                    (
                        api.FPDFPathSegment_GetType(segment),
                        x.value,
                        y.value,
                        int(api.FPDFPathSegment_GetClose(segment)),
                    )
                )
            row["segments"] = segments
            width = ctypes.c_float()
            fill, stroke = ctypes.c_int(), ctypes.c_int()
            if not api.FPDFPageObj_GetStrokeWidth(
                obj, width
            ) or not api.FPDFPath_GetDrawMode(obj, fill, stroke):
                raise RuntimeError("PDFium path style read failed")
            row["stroke_width"] = width.value
            row["draw_mode"] = (fill.value, stroke.value)
            for label, getter in (
                ("stroke_rgba", api.FPDFPageObj_GetStrokeColor),
                ("fill_rgba", api.FPDFPageObj_GetFillColor),
            ):
                channels = [ctypes.c_uint() for _ in range(4)]
                if not getter(obj, *channels):
                    raise RuntimeError("PDFium path color read failed")
                row[label] = tuple(channel.value for channel in channels)
        return {
            "objects": objects,
            "sha256": hashlib.sha256(
                json.dumps(objects, sort_keys=True).encode()
            ).hexdigest(),
        }
    finally:
        document.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument(
        "--visibility-control",
        choices=("annotation", "document_filter"),
        default="annotation",
    )
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    source = args.drawing.resolve(strict=True)
    if not args.worker:
        require_owned_diagnostic_environment()
        sys.path.insert(0, str(CAD_ROOT.parent))
        import dodo

        dodo._run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                str(source),
                "--visibility-control",
                args.visibility_control,
                "--worker",
            ],
            "cosmetic thread exported ink probe",
            log_stem="thread-ink",
            com=True,
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("--worker requires the machine-global COM seat")

    async def probe(adapter: Any) -> dict[str, str]:
        root = CAD_ROOT / "out/reports"
        root.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="thread-ink-", dir=root))
        adapter.ownership.register_directory(folder)
        adapter.ownership.register_source(source)
        copy = folder / f"{folder.name}-{source.name}"
        outputs = {
            phase: folder / f"{phase}-{copy.name}"
            for phase in ("visible", "hidden", "visible_again")
        }
        shutil.copy2(source, copy)
        hashes = {source: hashlib.sha256(source.read_bytes()).hexdigest()}
        report: dict[str, Any] = {
            "source": str(source),
            "copy": str(copy),
            "phases": {},
            "visibility_control": args.visibility_control,
        }
        threads = []
        try:
            check("open unique thread ink copy", await adapter.open_model(str(copy)))
            if Path(adapter.currentModel.GetPathName()).resolve() != copy:
                raise RuntimeError("SolidWorks opened the wrong thread ink copy")
            drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
            extension = _early_bound(
                adapter.currentModel.Extension, "IModelDocExtension"
            )
            report["drawing_filters"] = {
                "cosmetic_threads": extension.GetUserPreferenceToggle(41, 0),
                "annotations": extension.GetUserPreferenceToggle(31, 0),
            }
            if not all(report["drawing_filters"].values()):
                raise RuntimeError(
                    "thread ink positive control requires enabled native drawing filters"
                )
            for sheet in drawing.GetViews() or ():
                for raw_view in sheet[1:]:
                    view = _early_bound(raw_view, "IView")
                    reference = Path(view.ReferencedDocument.GetPathName()).resolve(
                        strict=True
                    )
                    hashes[reference] = hashlib.sha256(
                        reference.read_bytes()
                    ).hexdigest()
                    for raw in view.GetAnnotationsByType(1) or ():
                        annotation = _early_bound(raw, "IAnnotation")
                        if annotation.IsDangling() or int(annotation.Visible) != 1:
                            raise RuntimeError(
                                "thread ink positive control requires visible non-dangling annotations"
                            )
                        if int(adapter.swApp.IsSame(annotation.Owner, view)) != 1:
                            raise RuntimeError(
                                "thread ink annotation has wrong native view owner"
                            )
                        threads.append((view, annotation))
            if not threads:
                raise RuntimeError("thread ink control has no cosmetic threads")
            for phase, visibility in (
                ("visible", 1),
                ("hidden", 3),
                ("visible_again", 1),
            ):
                if args.visibility_control == "document_filter":
                    extension.SetUserPreferenceToggle(41, 0, visibility == 1)
                    if bool(extension.GetUserPreferenceToggle(41, 0)) != (
                        visibility == 1
                    ):
                        raise RuntimeError(
                            f"native drawing cosmetic-thread filter rejected {phase}"
                        )
                for _view, annotation in threads:
                    if args.visibility_control == "document_filter":
                        continue
                    annotation.Visible = visibility
                    actual = int(annotation.Visible)
                    if actual != visibility:
                        raise RuntimeError(
                            f"native cosmetic thread visibility rejected {phase}: requested={visibility}, actual={actual}"
                        )
                adapter.currentModel.GraphicsRedraw2()
                if not adapter.currentModel.EditRebuild3():
                    raise RuntimeError("thread ink drawing rebuild failed")
                report["phases"][phase] = {
                    "visibility": visibility,
                    "annotations": [
                        capture(adapter, view, annotation)
                        for view, annotation in threads
                    ],
                }
                pdf = folder / f"{phase}.pdf"
                result = save_drawing(adapter, str(outputs[phase]), pdf_path=str(pdf))
                if "pdf" not in result:
                    raise RuntimeError(f"thread ink PDF failed: {result}")
                render_pdf_png(pdf, folder / f"{phase}.png")
                report["phases"][phase]["vectors"] = vector_witness(pdf)
            report["visible_repeat"] = ink_difference(
                folder / "visible.png", folder / "visible_again.png"
            )
            report["visible_hidden"] = ink_difference(
                folder / "visible.png", folder / "hidden.png"
            )
            if report["visible_repeat"]["difference_box_pixels"] is not None:
                raise RuntimeError(
                    "visible thread A/A repeat ink differs; A/B is not a valid isolated witness"
                )
            vectors = {
                phase: values["vectors"]["sha256"]
                for phase, values in report["phases"].items()
            }
            if vectors["visible"] != vectors["visible_again"]:
                raise RuntimeError(
                    "visible thread A/A repeat native PDF vectors differ"
                )
            report["vector_geometry_unchanged"] = (
                vectors["visible"] == vectors["hidden"]
            )
            report["outcome"] = (
                "no_exported_ink_difference"
                if report["visible_hidden"]["difference_box_pixels"] is None
                and report["vector_geometry_unchanged"]
                else "exported_thread_ink_detected"
            )
        except Exception as error:
            report["error"] = repr(error)
            raise
        finally:
            try:
                current = adapter.currentModel
                if current is not None and Path(current.GetPathName()).resolve() in {
                    copy,
                    *outputs.values(),
                }:
                    check(
                        "close thread ink copy without further saves",
                        await adapter.close_model(save=False),
                    )
                report["source_unchanged"] = {
                    str(path): hashlib.sha256(path.read_bytes()).hexdigest() == digest
                    for path, digest in hashes.items()
                }
                if not all(report["source_unchanged"].values()):
                    raise RuntimeError("thread ink control changed source bytes")
            finally:
                (folder / "ink.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )
                _telemetry.info(f"thread ink observations: {folder}")
        return {"report": str(folder / "ink.json")}

    _telemetry.set_service("drawing-thread-ink-probe")
    return run_copy_diagnostic(probe)


if __name__ == "__main__":
    raise SystemExit(main())
