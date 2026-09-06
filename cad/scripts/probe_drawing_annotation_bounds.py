"""Copy-only native display-data/font calibration, through the normal COM seat.

Use ``uv run python cad/scripts/probe_drawing_annotation_bounds.py DRAWING``.
The JSON captures complete native text origins, reference codes and primitives;
the matching PDF permits an independent glyph-ink/transform measurement.
No source drawing or referenced model is saved.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any

from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import _style_surface_finish, render_pdf_png
from _drawing_annotation_bounds import (
    annotation_box,
    _native_symbol_extent,
    TextRun,
    font_cell_extent,
    _text_box,
)
from solidworks_mcp.adapters.solidworks.drawing import save_drawing
import _telemetry


def observe(operation):
    try:
        return operation()
    except Exception as error:
        return {"error": repr(error)}


def font_file_evidence() -> dict[str, Any]:
    import winreg

    with winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
    ) as key:
        registered, _kind = winreg.QueryValueEx(key, "Century Gothic (TrueType)")
    path = Path(registered)
    if not path.is_absolute():
        path = Path(os.environ["WINDIR"]) / "Fonts" / path
    path = path.resolve(strict=True)
    return {
        "registry_name": "Century Gothic (TrueType)",
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "scope": "registered regular font binary; alternate per-user font installations require recalibration",
    }


def capture(annotation: Any) -> dict[str, Any]:
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    fmt = _early_bound(annotation.GetTextFormat(0), "ITextFormat")
    result = {
        "name": annotation.GetName(),
        "kind": annotation.GetType(),
        "anchor": tuple(annotation.GetPosition() or ()),
        "format": {
            name: observe(lambda name=name: getattr(fmt, name))
            for name in (
                "CharHeight",
                "CharHeightInPts",
                "TypeFaceName",
                "WidthFactor",
                "Bold",
                "Italic",
            )
        },
        "height_in_points": observe(lambda: fmt.IsHeightSpecifiedInPts()),
        "text": [
            {
                "value": data.GetTextAtIndex(i),
                "position": tuple(data.GetTextPositionAtIndex(i)),
                "height_m": data.GetTextHeightAtIndex(i),
                "font": data.GetTextFontAtIndex(i),
                "angle": data.GetTextAngleAtIndex(i),
                "reference": data.GetTextRefPositionAtIndex(i),
                "inverted": data.GetTextInvertAtIndex(i),
                "plane": tuple(data.GetTextPlaneAtIndex(i) or ()),
            }
            for i in range(data.GetTextCount())
        ],
        "lines": [tuple(data.GetLineAtIndex3(i)) for i in range(data.GetLineCount())],
        "arcs": [tuple(data.GetArcAtIndex2(i)) for i in range(data.GetArcCount())],
        "polylines": [
            tuple(data.GetPolylineAtIndex2(i)) for i in range(data.GetPolyLineCount())
        ],
        "triangles": [
            tuple(data.GetTriangleAtIndex(i)) for i in range(data.GetTriangleCount())
        ],
        "arrowheads": [
            tuple(data.GetArrowHeadAtIndex2(i)) for i in range(data.GetArrowHeadCount())
        ],
        "polygons": [
            tuple(data.GetPolygonAtIndex(i)) for i in range(data.GetPolygonCount())
        ],
        "leaders": [
            tuple(annotation.GetLeaderPointsAtIndex(i) or ())
            for i in range(annotation.GetLeaderCount())
        ],
    }
    if result["kind"] == 6:
        result["note_extent"] = tuple(
            _early_bound(annotation.GetSpecificAnnotation(), "INote").GetExtent()
        )
    return result


def verify_pdf_font_cells(report: dict[str, Any], pdf: Path) -> dict[str, Any]:
    """Independent exported glyph-ink witness, with repeated text explicit.

    Text search is diagnostic correspondence, never manufacturing-entity
    identity. Only a unique native/PDF literal is eligible for this witness.
    """
    import pypdfium2

    document = pypdfium2.PdfDocument(pdf)
    page = document[0]
    text_page = page.get_textpage()
    candidates = [
        (a, t)
        for a in report["annotations"]
        if a["kind"] in {2, 4, 5, 7}
        for t in a["text"]
        if len(t["value"].strip()) >= 4 and "<" not in t["value"]
    ]
    result: dict[str, Any] = {"checked": [], "excluded": []}
    try:
        for annotation, text in candidates:
            value = text["value"]
            hits = []
            search = text_page.search(value)
            while (hit := search.get_next()) is not None:
                hits.append(hit)
            if len(hits) != 1 or sum(t["value"] == value for _a, t in candidates) != 1:
                result["excluded"].append(
                    {
                        "text": value,
                        "reason": "nonunique native/PDF literal",
                        "pdf_hits": len(hits),
                    }
                )
                continue
            fmt = annotation["format"]
            signature = (
                fmt["TypeFaceName"],
                fmt["CharHeight"],
                fmt["CharHeightInPts"],
                annotation["height_in_points"],
                fmt["WidthFactor"],
                fmt["Bold"],
                fmt["Italic"],
            )
            run = TextRun(
                value,
                tuple(text["position"][:2]),
                text["height_m"],
                text["font"],
                text["angle"],
                text["reference"],
                text["inverted"],
            )
            cell = _text_box(run, signature, font_cell_extent, None)
            first, count = hits[0]
            glyphs = [text_page.get_charbox(i) for i in range(first, first + count)]
            ink = tuple(
                value * 0.0254 / 72
                for value in (
                    min(g[0] for g in glyphs),
                    min(g[1] for g in glyphs),
                    max(g[2] for g in glyphs),
                    max(g[3] for g in glyphs),
                )
            )
            row = {
                "name": annotation["name"],
                "kind": annotation["kind"],
                "text": value,
                "cell_m": cell.bounds,
                "pdf_ink_m": ink,
            }
            result["checked"].append(row)
            if not (
                cell.xmin <= ink[0]
                and cell.ymin <= ink[1]
                and cell.xmax >= ink[2]
                and cell.ymax >= ink[3]
            ):
                raise RuntimeError(
                    f"native logical font cell misses exported glyph ink: {row}"
                )
        if len(result["checked"]) < 3:
            raise RuntimeError(
                "font calibration requires three unique exported text witnesses"
            )
        return result
    finally:
        text_page.close()
        page.close()
        document.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    source = args.drawing.resolve(strict=True)
    if not args.worker:
        sys.path.insert(0, str(CAD_ROOT.parent))
        import dodo

        dodo._run(
            [sys.executable, str(Path(__file__).resolve()), str(source), "--worker"],
            "annotation bounds calibration",
            log_stem="drawing-annotation-bounds-probe",
            com=True,
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("--worker requires the machine-global COM seat")

    async def probe(adapter: Any) -> dict[str, str]:
        root = CAD_ROOT / "out/reports"
        root.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="annotation-bounds-", dir=root))
        copy = folder / f"{folder.name}-{source.name}"
        observed = folder / f"{folder.name}-observed.SLDDRW"
        shutil.copy2(source, copy)
        hashes = {source: hashlib.sha256(source.read_bytes()).hexdigest()}
        report: dict[str, Any] = {
            "source": str(source),
            "copy": str(copy),
            "observed": str(observed),
            "stage": "open",
        }
        try:
            check("open unique bounds copy", await adapter.open_model(str(copy)))
            model = adapter.currentModel
            if Path(model.GetPathName()).resolve() != copy:
                raise RuntimeError("SolidWorks opened the wrong bounds copy")
            drawing = _early_bound(model, "IDrawingDoc")
            report["solidworks_revision"] = _early_bound(
                adapter.swApp, "ISldWorks"
            ).RevisionNumber()
            report["font_file"] = font_file_evidence()
            rows = []
            for sheet in drawing.GetViews() or ():
                for raw_view in sheet:
                    view = _early_bound(raw_view, "IView")
                    document = view.ReferencedDocument
                    if document is not None:
                        part = Path(document.GetPathName()).resolve(strict=True)
                        hashes[part] = hashlib.sha256(part.read_bytes()).hexdigest()
                    for kind in (2, 4, 5, 6, 7, 13, 15):
                        for raw in view.GetAnnotationsByType(kind) or ():
                            annotation = _early_bound(raw, "IAnnotation")
                            if kind == 7:
                                _style_surface_finish(
                                    adapter,
                                    _early_bound(
                                        annotation.GetSpecificAnnotation(), "ISFSymbol"
                                    ),
                                    annotation,
                                    label="bounds typography calibration",
                                )
                            rows.append((view.GetName2(), annotation))
            model.EditRebuild3()
            report["stage"] = "snapshot"
            report["annotations"] = [
                {"view": view, **capture(annotation)} for view, annotation in rows
            ]
            report["stage"] = "symbol_definitions"
            environment = _early_bound(adapter.swApp.GetEnvironment(), "IEnvironment")
            report["symbol_definitions"] = {}
            for token in (
                "<MOD-DIAM>",
                "<GTOL-FLAT>",
                "<GTOL-PERP>",
                "<GTOL-POSI>",
                "<GTOL-SPROF>",
            ):
                report["symbol_definitions"][token] = {
                    method: observe(
                        lambda method=method: getattr(environment, method)(token)
                    )
                    for method in (
                        "GetSymEdgeCounts",
                        "GetSymLines",
                        "GetSymCircles",
                        "GetSymArcs",
                        "GetSymArcs2",
                    )
                }
            report["symbol_extents"] = {
                token: _native_symbol_extent(environment, token)
                for token in report["symbol_definitions"]
            }
            report["stage"] = "measured_bounds"
            report["measured_bounds"] = []
            report["no_ink_exclusions"] = []
            for (view, annotation), captured in zip(rows, report["annotations"]):
                if (
                    captured["kind"] == 6
                    and not captured["text"]
                    and not captured["lines"]
                    and not captured["arcs"]
                    and not captured["polylines"]
                ):
                    report["no_ink_exclusions"].append(
                        {
                            "view": view,
                            "name": captured["name"],
                            "reason": "empty native note has no text or primitives",
                        }
                    )
                    continue
                report["measured_bounds"].append(
                    {"view": view, **asdict(annotation_box(adapter, annotation))}
                )
            pdf = folder / "bounds.pdf"
            outputs = save_drawing(adapter, str(observed), pdf_path=str(pdf))
            if "pdf" not in outputs:
                raise RuntimeError(f"bounds calibration PDF failed: {outputs}")
            render_pdf_png(pdf, folder / "bounds.png")
            report["stage"] = "pdf_font_cell_check"
            report["pdf_font_cells"] = verify_pdf_font_cells(report, pdf)
            report["stage"] = "passed"
        except Exception as error:
            report["error"] = repr(error)
            raise
        finally:
            try:
                current = adapter.currentModel
                if current is not None and Path(current.GetPathName()).resolve() in {
                    copy,
                    observed,
                }:
                    check(
                        "close bounds copy without additional saves",
                        await adapter.close_model(save=False),
                    )
                report["source_unchanged"] = {
                    str(path): hashlib.sha256(path.read_bytes()).hexdigest() == digest
                    for path, digest in hashes.items()
                }
                if not all(report["source_unchanged"].values()):
                    raise RuntimeError("bounds probe changed source bytes")
            finally:
                (folder / "bounds.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )
                _telemetry.info(f"annotation bounds report: {folder}")
        return {"report": str(folder / "bounds.json")}

    _telemetry.set_service("drawing-annotation-bounds-probe")
    return run_build(probe)


if __name__ == "__main__":
    raise SystemExit(main())
