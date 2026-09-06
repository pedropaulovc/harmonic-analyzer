"""Copy-only diagnostic for native versus explicit-leader SF typography.

Run with ``uv run python cad/scripts/probe_drawing_annotation_layout.py <drawing>``.
The normal seat/watchdog wrapper owns COM. A unique native copy and diagnostic
PDF/PNG are saved; source files are hashed and never saved. Measurements and
individual rejected call shapes remain in layout.json, including no-op successes.
"""

from __future__ import annotations

import argparse
from dataclasses import fields
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any
from unittest.mock import patch

from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import add_surface_finish, render_pdf_png
import _drawing_common
from _drawing_entities import CircleEdge, LineEdge, _edge_geometry
from _part_pmi import _face_geometry
from solidworks_mcp.adapters import sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import save_drawing
import _telemetry


def _format(raw: Any) -> dict[str, Any]:
    value = _early_bound(raw, "ITextFormat")
    return {"height_m": value.CharHeight, "font": value.TypeFaceName,
            "width_factor": value.WidthFactor, "italic": value.Italic}


def _surface(annotation: Any) -> dict[str, Any]:
    symbol = _early_bound(annotation.GetSpecificAnnotation(), "ISFSymbol")
    return {"name": annotation.GetName(), "position": tuple(annotation.GetPosition()),
            "use_doc": annotation.GetUseDocTextFormat(0), "format": _format(annotation.GetTextFormat(0)),
            "orientation": symbol.Orientation, "angle": symbol.GetAngle(),
            "text": [{"value": symbol.GetTextAtIndex(index), "height_m": symbol.GetTextHeightAtIndex(index),
                      "angle": symbol.GetTextAngleAtIndex(index)} for index in range(symbol.GetTextCount())]}


def _attachment_geometry(annotation: Any) -> list[dict[str, Any]]:
    result = []
    attached = tuple(annotation.GetAttachedEntities3() or ())
    kinds = tuple(annotation.GetAttachedEntityTypes() or ())
    if len(attached) != 1 or len(kinds) != 1 or attached[0] is None:
        raise RuntimeError("SF geometry witness requires one attached model entity")
    for entity, kind in zip(attached, kinds):
        geometry = (_face_geometry(entity) if kind == 2 else
                    _edge_geometry(entity, kinds=frozenset({CircleEdge, LineEdge})) if kind == 1 else None)
        if geometry is None:
            raise RuntimeError(f"SF geometry witness does not support entity kind {kind}")
        row = {field.name: getattr(geometry, field.name) for field in fields(geometry) if field.name not in {"entity", "face"}}
        result.append({name: tuple(round(v, 9) for v in value) if isinstance(value, tuple)
                       else round(value, 9) if isinstance(value, float) else value for name, value in row.items()})
    return result


def _document_formats(extension: Any) -> dict[str, Any]:
    import pythoncom
    from win32com.client import gencache

    path = sw_type_info._find_aux_tlb("swconst.tlb")
    if path is None:
        raise RuntimeError("cannot read installed swconst typography enums")
    iid, lcid, _system, major, minor, _flags = pythoncom.LoadTypeLib(str(path)).GetLibAttr()
    constants = gencache.EnsureModule(str(iid), lcid, major, minor).constants
    return {name: extension.GetUserPreferenceTextFormat(getattr(constants, name), 0) for name in (
        "swDetailingDimensionTextFormat", "swDetailingSurfaceFinishTextFormat", "swDetailingNoteTextFormat",
    )}


def _validate_reopened_surface(before: dict[str, Any], after: dict[str, Any]) -> None:
    if after["format"] != before["format"] or after["orientation"] != 1 or after["angle"] != 0:
        raise RuntimeError("saved SF typography/orientation changed after reopen")
    if math.dist(after["position"], before["position"]) > 1e-12:
        raise RuntimeError("saved SF position changed after typography update")
    if not after["text"] or [item["value"] for item in after["text"]] != [item["value"] for item in before["text"]]:
        raise RuntimeError("saved SF rendered text content changed after reopen")
    if any(item["height_m"] != after["format"]["height_m"] or item["angle"] != 0 for item in after["text"]):
        raise RuntimeError("saved SF rendered glyphs do not match requested typography")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    source = args.drawing.resolve(strict=True)
    if not args.worker:
        sys.path.insert(0, str(CAD_ROOT.parent))
        import dodo
        dodo._run([sys.executable, str(Path(__file__).resolve()), str(source), "--worker"],
                  "drawing annotation layout probe", log_stem="drawing-annotation-layout-probe", com=True)
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("--worker requires the machine-global COM seat")

    async def probe(adapter: Any) -> dict[str, str]:
        root = CAD_ROOT / "out/reports"
        root.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="annotation-layout-", dir=root))
        copy = folder / f"probe-{folder.name}-{source.name}"
        report: dict[str, Any] = {"source": str(source), "copy": str(copy), "stage": "open"}
        hashes = {source: hashlib.sha256(source.read_bytes()).hexdigest()}
        shutil.copy2(source, copy)
        try:
            check("open unique layout copy", await adapter.open_model(str(copy)))
            model = adapter.currentModel
            if Path(model.GetPathName()).resolve() != copy:
                raise RuntimeError("SolidWorks opened the wrong drawing copy")
            drawing = _early_bound(model, "IDrawingDoc")
            extension = _early_bound(model.Extension, "IModelDocExtension")
            views = [_early_bound(view, "IView") for sheet in drawing.GetViews() or () for view in sheet[1:]]
            for view in views:
                part = Path(view.ReferencedDocument.GetPathName()).resolve(strict=True)
                hashes[part] = hashlib.sha256(part.read_bytes()).hexdigest()
            formats = _document_formats(extension)
            report["document_formats"] = {name: _format(value) for name, value in formats.items()}
            surfaces = [_early_bound(annotation, "IAnnotation") for view in views for annotation in view.GetAnnotationsByType(7) or ()]
            report["surface_before"] = [_surface(annotation) for annotation in surfaces]
            if not surfaces:
                raise RuntimeError("diagnostic requires at least one model-attached SF symbol")
            # Positive control: the previous explicit bent-leader call shape on
            # the exact same model entity, offset from its measured native point.
            original = surfaces[0]
            owner = _early_bound(original.Owner, "IView")
            attached = tuple(original.GetAttachedEntities3() or ())
            kinds = tuple(original.GetAttachedEntityTypes() or ())
            if len(attached) != 1 or len(kinds) != 1 or kinds[0] not in (1, 2):
                raise RuntimeError("explicit SF control requires one model edge or face")
            position = tuple(original.GetPosition())
            # Reproduce the pre-fix styling without bypassing entity selection,
            # annotation insertion or value checks. No production drawing is open.
            with patch.object(_drawing_common, "_style_surface_finish", lambda *_args, **_kwargs: None):
                explicit = add_surface_finish(
                    adapter, owner, entity=attached[0], entity_type={1: "EDGE", 2: "FACE"}[kinds[0]],
                    roughness_ra="1.6", symbol_xy=(position[0] + 0.03, position[1] + 0.03),
                    label="explicit bent-leader typography control",
                )
            surfaces.append(_early_bound(explicit.GetAnnotation(), "IAnnotation"))
            report["explicit_control"] = _surface(surfaces[-1])
            originals = {annotation.GetName(): tuple(annotation.GetAttachedEntities3()) for annotation in surfaces}
            geometries = {annotation.GetName(): _attachment_geometry(annotation) for annotation in surfaces}
            report["attachment_geometry_before"] = geometries
            report["stage"] = "document_font"
            for annotation in surfaces:
                if not annotation.SetTextFormat(0, True, None):
                    raise RuntimeError("native SF rejected documented use-doc text format")
                symbol = _early_bound(annotation.GetSpecificAnnotation(), "ISFSymbol")
                symbol.Orientation = 1  # swSFOrientation_Upright: native horizontal text
            report["surface_document_font"] = [_surface(annotation) for annotation in surfaces]
            report["stage"] = "dimension_font"
            for annotation in surfaces:
                symbol = _early_bound(annotation.GetSpecificAnnotation(), "ISFSymbol")
                _drawing_common._style_surface_finish(adapter, symbol, annotation, label="diagnostic SF typography")
                after = tuple(annotation.GetAttachedEntities3() or ())
                before = originals[annotation.GetName()]
                if len(after) != len(before) or any(int(adapter.swApp.IsSame(a, b)) != 1 for a, b in zip(before, after)):
                    raise RuntimeError("SF typography changed attachment identity")
            model.GraphicsRedraw2()
            report["surface_dimension_font"] = [_surface(annotation) for annotation in surfaces]
            report["stage"] = "export"
            pdf = folder / "layout.pdf"
            outputs = save_drawing(adapter, str(copy), pdf_path=str(pdf))
            if "drawing" not in outputs or "pdf" not in outputs:
                raise RuntimeError(f"layout copy export failed: {outputs}")
            render_pdf_png(pdf, folder / "layout.png")
            report["stage"] = "reopen"
            expected = {annotation.GetName(): _surface(annotation) for annotation in surfaces}
            check("close styled layout copy", await adapter.close_model(save=False))
            check("reopen styled layout copy", await adapter.open_model(str(copy)))
            if Path(adapter.currentModel.GetPathName()).resolve() != copy:
                raise RuntimeError("SolidWorks reopened the wrong styled copy")
            reopened = _early_bound(adapter.currentModel, "IDrawingDoc")
            views = [_early_bound(view, "IView") for sheet in reopened.GetViews() or () for view in sheet[1:]]
            surfaces = [_early_bound(annotation, "IAnnotation") for view in views for annotation in view.GetAnnotationsByType(7) or ()]
            report["surface_reopened"] = [_surface(annotation) for annotation in surfaces]
            for annotation in surfaces:
                state = _surface(annotation)
                before = expected[state["name"]]
                _validate_reopened_surface(before, state)
                # COM identity pointers are invalid across a close/reopen. The
                # immutable model-geometry witness is compared across that boundary.
                if _attachment_geometry(annotation) != geometries[state["name"]]:
                    raise RuntimeError("saved SF typography changed attachment geometry after reopen")
            report["attachment_geometry_reopened"] = {annotation.GetName(): _attachment_geometry(annotation) for annotation in surfaces}
            report["stage"] = "passed"
        except Exception as error:
            report["error"] = repr(error)
            raise
        finally:
            try:
                current = adapter.currentModel
                if current is not None and Path(current.GetPathName()).resolve() == copy:
                    check("close layout copy without further saves", await adapter.close_model(save=False))
                report["source_unchanged"] = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in hashes.items()}
                if not all(report["source_unchanged"].values()):
                    raise RuntimeError("layout diagnostic changed source bytes")
            finally:
                (folder / "layout.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                _telemetry.info(f"annotation layout report: {folder}")
        return {"report": str(folder / "layout.json")}

    _telemetry.set_service("drawing-annotation-layout-probe")
    return run_build(probe)


if __name__ == "__main__":
    raise SystemExit(main())
