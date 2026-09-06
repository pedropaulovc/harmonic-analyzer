"""Copy-only cosmetic-thread/centerline inventory and view-motion witness.

Run with one or more drawing paths through uv. The worker holds the normal
machine-global COM seat, moves only unique unsaved copies, and guards source
drawing and referenced-model hashes. Native read failures remain in the report.
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

from _common import CAD_ROOT, _early_bound, check
from diagnostics._owned_native_documents import run_copy_diagnostic
from diagnostics._owned_native_session import require_owned_diagnostic_environment
from _drawing_annotation_bounds import annotation_box
from solidworks_mcp.adapters.com_variant import double_array
import _telemetry


def observe(operation):
    try:
        return operation()
    except Exception as error:
        return {"error": repr(error)}


def display_counts(data):
    """All documented display-data primitive inventories, including unsupported kinds."""
    return {
        label: int(getattr(data, method)())
        for label, method in (
            ("text", "GetTextCount"),
            ("lines", "GetLineCount"),
            ("arcs", "GetArcCount"),
            ("polylines", "GetPolyLineCount"),
            ("triangles", "GetTriangleCount"),
            ("arrowheads", "GetArrowHeadCount"),
            ("polygons", "GetPolygonCount"),
            ("ellipses", "GetEllipseCount"),
            ("parabolas", "GetParabolaCount"),
            ("points", "GetPointCount"),
        )
    }


def capture(adapter: Any, view: Any, annotation: Any) -> dict[str, Any]:
    kind = int(annotation.GetType())
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    specific = _early_bound(
        annotation.GetSpecificAnnotation(),
        {1: "ICThread", 13: "ICenterMark", 15: "ICenterLine"}[kind],
    )
    generic_counts = display_counts(data)
    if kind == 1:
        data = _early_bound(specific.GetDisplayData(), "IDisplayData")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    result = {
        "name": annotation.GetName(),
        "kind": kind,
        "visible": annotation.Visible,
        "dangling": annotation.IsDangling(),
        "owner_type": annotation.OwnerType,
        "owner_same_view": adapter.swApp.IsSame(annotation.Owner, view),
        "owner_same_model": adapter.swApp.IsSame(
            annotation.Owner, view.ReferencedDocument
        ),
        "position": tuple(annotation.GetPosition() or ()),
        "specific_interface": type(specific).__name__,
        "specific_annotation_same": adapter.swApp.IsSame(
            specific.GetAnnotation(), annotation
        ),
        "generic_display_counts": generic_counts,
        "specific_display_counts": display_counts(data),
        "view_native_display_counts": display_counts(
            _early_bound(view.GetDisplayData4(), "IDisplayData")
        ),
        "attachment_count": annotation.GetAttachedEntityCount3(),
        "attachment_types": tuple(annotation.GetAttachedEntityTypes() or ()),
        "attachment_nulls": [item is None for item in attached],
        "attachment_interfaces": [type(item).__name__ for item in attached],
        "text_count": data.GetTextCount(),
        "view_name": view.GetName2(),
        "view_position": tuple(view.Position),
        "view_scale": tuple(view.ScaleRatio),
        "view_angle": view.Angle,
        "view_outline": tuple(view.GetOutline()),
        "reference": view.GetReferencedModelName(),
        "bounds": observe(lambda: asdict(annotation_box(adapter, annotation))),
    }
    for label, count_name, getter in (
        ("lines", "GetLineCount", "GetLineAtIndex3"),
        ("arcs", "GetArcCount", "GetArcAtIndex2"),
        ("polylines", "GetPolyLineCount", "GetPolylineAtIndex2"),
        ("triangles", "GetTriangleCount", "GetTriangleAtIndex"),
        ("arrowheads", "GetArrowHeadCount", "GetArrowHeadAtIndex2"),
        ("polygons", "GetPolygonCount", "GetPolygonAtIndex"),
    ):
        result[label] = [
            tuple(getattr(data, getter)(index))
            for index in range(int(getattr(data, count_name)()))
        ]
    if kind == 1:
        feature = _early_bound(view.ReferencedDocument, "IPartDoc").FeatureByName(
            annotation.GetName()
        )
        if feature is not None:
            feature = _early_bound(feature, "IFeature")
        result["source_feature"] = (
            None
            if feature is None
            else {"name": feature.Name, "type": feature.GetTypeName2()}
        )
        result["pattern_count"] = specific.GetPatternedTransformsCount()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawings", nargs="+", type=Path)
    parser.add_argument(
        "--mode", choices=("inventory", "thread_filter"), default="inventory"
    )
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    sources = [path.resolve(strict=True) for path in args.drawings]
    if not args.worker:
        require_owned_diagnostic_environment()
        sys.path.insert(0, str(CAD_ROOT.parent))
        import dodo

        dodo._run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                *map(str, sources),
                "--mode",
                args.mode,
                "--worker",
            ],
            "primitive annotation coverage probe",
            log_stem="primitive-annotations",
            com=True,
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("--worker requires the machine-global COM seat")

    async def probe(adapter: Any) -> dict[str, str]:
        root = CAD_ROOT / "out/reports"
        root.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="primitive-annotations-", dir=root))
        adapter.ownership.register_directory(folder)
        for source in sources:
            adapter.ownership.register_source(source)
        report: dict[str, Any] = {"drawings": []}
        hashes = {
            path: hashlib.sha256(path.read_bytes()).hexdigest() for path in sources
        }
        try:
            for source in sources:
                copy = folder / f"{folder.name}-{source.name}"
                shutil.copy2(source, copy)
                row: dict[str, Any] = {
                    "source": str(source),
                    "copy": str(copy),
                    "views": [],
                }
                report["drawings"].append(row)
                try:
                    check(
                        "open unique primitive copy",
                        await adapter.open_model(str(copy)),
                    )
                    if Path(adapter.currentModel.GetPathName()).resolve() != copy:
                        raise RuntimeError("SolidWorks opened the wrong copy")
                    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
                    if args.mode == "thread_filter":
                        extension = _early_bound(
                            adapter.currentModel.Extension, "IModelDocExtension"
                        )
                        # Installed swconst.tlb values; DP_Detailing documents
                        # both filters as document-level preferences.
                        preferences = {
                            "swDisplayCosmeticThreads": 41,
                            "swDisplayAnnotations": 31,
                        }
                        row["filter_original"] = {
                            name: extension.GetUserPreferenceToggle(value, 0)
                            for name, value in preferences.items()
                        }
                        for name, value in preferences.items():
                            extension.SetUserPreferenceToggle(value, 0, True)
                            if not extension.GetUserPreferenceToggle(value, 0):
                                raise RuntimeError(
                                    f"copy display filter {name} did not enable"
                                )
                        adapter.currentModel.GraphicsRedraw2()
                        if not adapter.currentModel.EditRebuild3():
                            raise RuntimeError("copy display filter rebuild failed")
                        row["filter_enabled"] = {
                            name: extension.GetUserPreferenceToggle(value, 0)
                            for name, value in preferences.items()
                        }
                    for sheet in drawing.GetViews() or ():
                        for raw_view in sheet[1:]:
                            view = _early_bound(raw_view, "IView")
                            reference = Path(
                                view.ReferencedDocument.GetPathName()
                            ).resolve(strict=True)
                            hashes[reference] = hashlib.sha256(
                                reference.read_bytes()
                            ).hexdigest()
                            targets = [
                                _early_bound(raw, "IAnnotation")
                                for kind in (1, 13, 15)
                                for raw in view.GetAnnotationsByType(kind) or ()
                            ]
                            if not targets:
                                continue
                            before = [capture(adapter, view, ann) for ann in targets]
                            original = tuple(view.Position)
                            delta = (0.006, -0.004)
                            try:
                                target = tuple(a + b for a, b in zip(original, delta))
                                if not view.SetViewPosition(
                                    double_array(target), False
                                ):
                                    raise RuntimeError("native view motion rejected")
                                if not adapter.currentModel.EditRebuild3():
                                    raise RuntimeError("copy rebuild failed")
                                row["views"].append(
                                    {
                                        "before": before,
                                        "delta": delta,
                                        "after": [
                                            capture(adapter, view, ann)
                                            for ann in targets
                                        ],
                                    }
                                )
                            finally:
                                if not view.SetViewPosition(
                                    double_array(original), False
                                ):
                                    raise RuntimeError("copy view restore rejected")
                finally:
                    if (
                        adapter.currentModel is not None
                        and Path(adapter.currentModel.GetPathName()).resolve() == copy
                    ):
                        check(
                            "close unsaved primitive copy",
                            await adapter.close_model(save=False),
                        )
        except Exception as error:
            report["error"] = repr(error)
            raise
        finally:
            report["source_unchanged"] = {
                str(path): hashlib.sha256(path.read_bytes()).hexdigest() == digest
                for path, digest in hashes.items()
            }
            (folder / "primitives.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            _telemetry.info(f"primitive annotation observations: {folder}")
            if not all(report["source_unchanged"].values()):
                raise RuntimeError("primitive probe changed source bytes")
        return {"report": str(folder / "primitives.json")}

    _telemetry.set_service("drawing-primitive-annotation-probe")
    return run_copy_diagnostic(probe)


if __name__ == "__main__":
    raise SystemExit(main())
