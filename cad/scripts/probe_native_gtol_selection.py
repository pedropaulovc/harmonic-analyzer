"""Prove native GTol projection and persisted attachment on a cone-gear copy.

Run ``uv run python cad/scripts/probe_native_gtol_selection.py <cone-gear.SLDDRW>``.
This opt-in diagnostic takes the normal COM seat/watchdog, creates a uniquely
named drawing copy, adds a face and circular-edge GTol, saves/reopens that copy,
and re-resolves each attached entity from its exact model role. It never saves
the source drawing or source part. Both source files' SHA-256 values must remain
unchanged. The saved diagnostic copy and JSON report are retained for inspection.

The two view names are explicit diagnostic inputs, not geometry selectors. No
annotation positions are supplied: the shared helper projects the kernel point
through the chosen view, and SolidWorks chooses the annotation location.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any

from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import add_feature_control_frame
from _drawing_entities import ModelEntities
from draw_cone_gear import ENTITY_ROLES
import _telemetry


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _views(model: Any) -> dict[str, Any]:
    drawing = _early_bound(model, "IDrawingDoc")
    views = [_early_bound(view, "IView") for sheet in drawing.GetViews() or () for view in sheet[1:]]
    result = {view.GetName2(): view for view in views}
    if len(result) != len(views):
        raise RuntimeError("diagnostic requires unique drawing view names")
    return result


def _annotation_state(adapter: Any, annotation: Any, entity: Any) -> dict[str, Any]:
    attached = tuple(annotation.GetAttachedEntities3() or ())
    if len(attached) != 1 or attached[0] is None:
        raise RuntimeError("native GTol lost its single attachment")
    application = _early_bound(adapter.swApp, "ISldWorks")
    if int(application.IsSame(entity, attached[0])) != 1:
        raise RuntimeError("native GTol attachment differs from exact resolved role")
    position = tuple(annotation.GetPosition() or ())
    sheet = _early_bound(_early_bound(adapter.currentModel, "IDrawingDoc").GetCurrentSheet(), "ISheet")
    width, height = tuple(sheet.GetProperties2())[5:7]
    if len(position) != 3 or not all(math.isfinite(value) for value in position):
        raise RuntimeError(f"native GTol position is not readable: {position}")
    if not (0 <= position[0] <= width and 0 <= position[1] <= height):
        raise RuntimeError(f"native GTol is outside its sheet: {position}")
    return {"name": annotation.GetName(), "position_m": position, "exact_attachment": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument("--face-view", default="Drawing View2")
    parser.add_argument("--edge-view", default="Drawing View1")
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    source = args.drawing.resolve(strict=True)
    if source.suffix.upper() != ".SLDDRW":
        raise ValueError("probe requires a native cone-gear drawing")
    if not args.worker:
        sys.path.insert(0, str(CAD_ROOT.parent))
        import dodo
        dodo._run(
            [sys.executable, str(Path(__file__).resolve()), str(source), "--worker",
             "--face-view", args.face_view, "--edge-view", args.edge_view],
            "native GTol selection probe", log_stem="native-gtol-selection-probe", com=True,
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("--worker requires the machine-global COM seat; invoke the probe without --worker")

    async def probe(adapter: Any) -> dict[str, str]:
        report_root = CAD_ROOT / "out/reports"
        report_root.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="native-gtol-selection-", dir=report_root))
        copy = folder / f"probe-{folder.name}-{source.name}"
        report_path = folder / "projection.json"
        report: dict[str, Any] = {"source": str(source), "copy": str(copy), "stage": "copy"}
        source_hashes = {source: _sha256(source)}
        shutil.copy2(source, copy)
        try:
            report["stage"] = "open"
            check("open unique GTol diagnostic copy", await adapter.open_model(str(copy)))
            model = adapter.currentModel
            if Path(model.GetPathName()).resolve() != copy:
                raise RuntimeError("SolidWorks opened a different drawing than the unique copy")
            views = _views(model)
            face_view, edge_view = views[args.face_view], views[args.edge_view]
            source_part = Path(face_view.ReferencedDocument.GetPathName()).resolve(strict=True)
            if source_part.stem != "cone-gear":
                raise RuntimeError(f"diagnostic requires the cone-gear source model, got {source_part}")
            source_hashes[source_part] = _sha256(source_part)
            entities = ModelEntities(face_view.ReferencedDocument).resolve(ENTITY_ROLES)
            before = {}
            report["stage"] = "insert"
            for role, entity_type, view in (
                ("front_face", "FACE", face_view), ("bore", "EDGE", edge_view),
            ):
                gtol = add_feature_control_frame(
                    adapter, view, entity=entities[role], entity_type=entity_type,
                    characteristic="perpendicularity" if role == "front_face" else "circular_runout",
                    tolerance="0.05", datums=("A",), label=f"native projection diagnostic {role}",
                )
                annotation = _early_bound(gtol.GetAnnotation(), "IAnnotation")
                before[role] = _annotation_state(adapter, annotation, entities[role])
            report["before"] = before
            report["stage"] = "save"
            saved = model.Save3(1, 0, 0)  # swSaveAsOptions_Silent, only this drawing copy
            if not (saved[0] if isinstance(saved, tuple) else saved):
                raise RuntimeError(f"diagnostic copy save failed: {saved}")
            check("close saved GTol diagnostic copy", await adapter.close_model(save=False))
            report["stage"] = "reopen"
            check("reopen GTol diagnostic copy", await adapter.open_model(str(copy)))
            if Path(adapter.currentModel.GetPathName()).resolve() != copy:
                raise RuntimeError("SolidWorks reopened a different drawing")
            views = _views(adapter.currentModel)
            entities = ModelEntities(views[args.face_view].ReferencedDocument).resolve(ENTITY_ROLES)
            annotations = [_early_bound(annotation, "IAnnotation") for view in views.values()
                           for annotation in view.GetAnnotationsByType(5) or ()]
            after = {}
            for role, expected in before.items():
                matches = [annotation for annotation in annotations if annotation.GetName() == expected["name"]]
                if len(matches) != 1:
                    raise RuntimeError(f"saved GTol {role} count is {len(matches)}, expected one")
                after[role] = _annotation_state(adapter, matches[0], entities[role])
                if math.dist(after[role]["position_m"], expected["position_m"]) > 1e-12:
                    raise RuntimeError(f"saved GTol {role} changed its native position")
            report["after"] = after
            report["stage"] = "passed"
        except Exception as error:
            report["error"] = repr(error)
            raise
        finally:
            try:
                current = adapter.currentModel
                if current is not None and Path(current.GetPathName()).resolve() == copy:
                    check("close GTol diagnostic copy without further saves", await adapter.close_model(save=False))
                report["source_hashes"] = {str(path): {"before": digest, "after": _sha256(path)} for path, digest in source_hashes.items()}
                if any(item["before"] != item["after"] for item in report["source_hashes"].values()):
                    raise RuntimeError("native GTol diagnostic changed source file bytes")
            finally:
                report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                _telemetry.info(f"native GTol projection report: {report_path}")
        return {"report": str(report_path), "copy": str(copy)}

    _telemetry.set_service("native-gtol-selection-probe")
    return run_build(probe)


if __name__ == "__main__":
    raise SystemExit(main())
