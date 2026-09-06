"""Copy-only native alignment control for an exact mixed datum/GTol/SF bank."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
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
from _drawing_common import render_pdf_png
from diagnostics._owned_native_documents import save_drawing
import _telemetry


_INTERFACES = {2: "IDatumTag", 5: "IGtol", 7: "ISFSymbol"}


def snapshot(adapter, view):
    result, native = {}, {}
    for kind in _INTERFACES:
        for raw in view.GetAnnotationsByType(kind) or ():
            annotation = _early_bound(raw, "IAnnotation")
            key = f"{kind}:{annotation.GetName()}"
            if key in result or int(adapter.swApp.IsSame(annotation.Owner, view)) != 1:
                raise RuntimeError("mixed bank has ambiguous annotation/view identity")
            entities = tuple(annotation.GetAttachedEntities3() or ())
            if (
                annotation.IsDangling()
                or not entities
                or any(item is None for item in entities)
            ):
                raise RuntimeError(
                    "mixed bank requires non-dangling exact attachment handles"
                )
            measured = annotation_box(adapter, annotation)
            result[key] = {
                "kind": kind,
                "position": tuple(annotation.GetPosition()),
                "visibility": annotation.Visible,
                "attachment_types": tuple(annotation.GetAttachedEntityTypes() or ()),
                "bounds": asdict(measured),
                "content": (
                    measured.format_signature,
                    tuple(
                        (
                            run.value,
                            run.font,
                            run.height_m,
                            run.angle_rad,
                            run.reference,
                            run.inverted,
                        )
                        for run in measured.text_runs
                    ),
                ),
            }
            native[key] = annotation, entities
    return result, native


def unchanged(adapter, before, before_native, after, after_native):
    if before.keys() != after.keys():
        raise RuntimeError("native mixed command changed annotation inventory")
    for key, original in before.items():
        observed = after[key]
        for field in ("kind", "visibility", "attachment_types", "content"):
            if original[field] != observed[field]:
                raise RuntimeError(f"mixed command changed {key} {field}")
        first, entities = before_native[key]
        second, actual_entities = after_native[key]
        if (
            len(entities) != len(actual_entities)
            or int(adapter.swApp.IsSame(first, second)) != 1
        ):
            raise RuntimeError(
                "mixed command replaced native annotation or attachment inventory"
            )
        if any(
            int(adapter.swApp.IsSame(a, b)) != 1
            for a, b in zip(entities, actual_entities)
        ):
            raise RuntimeError("mixed command changed exact attachment identity")


def leader_position_trials(adapter, view, before, native):
    """Probe axis-aligned moves derived from the actual view and native body."""
    outline = tuple(view.GetOutline())
    rows = []
    for key, (annotation, _entities) in native.items():
        kind = before[key]["kind"]
        if kind not in {2, 7}:
            continue
        row = {"key": key, "kind": kind, "outline": outline, "moves": []}
        rows.append(row)
        original = tuple(annotation.GetPosition())
        if kind == 7:
            row["leader_status"] = annotation.SetLeader3(
                2, 0, True, False, False, False
            )
            row["leader_style"] = annotation.GetLeaderStyle()
            if row["leader_status"] != 0 or row["leader_style"] != 2:
                raise RuntimeError("native SF bent-leader setting rejected")
        body = annotation_box(adapter, annotation).body
        offsets = (
            body.xmin - original[0],
            body.ymin - original[1],
            body.xmax - original[0],
            body.ymax - original[1],
        )
        gap = 0.003
        targets = (
            ("above", (original[0], outline[3] + gap - offsets[1], original[2])),
            ("below", (original[0], outline[1] - gap - offsets[3], original[2])),
            ("left", (outline[0] - gap - offsets[2], original[1], original[2])),
            ("right", (outline[2] + gap - offsets[0], original[1], original[2])),
        )
        accepted = []
        for direction, target in targets:
            result = annotation.SetPosition2(*target)
            actual = tuple(annotation.GetPosition())
            measured = annotation_box(adapter, annotation)
            row["moves"].append(
                {
                    "direction": direction,
                    "target": target,
                    "return": result,
                    "actual": actual,
                    "target_error_m": math.dist(actual, target),
                    "sheet_target_error_m": math.dist(actual[:2], target[:2]),
                    "bounds": asdict(measured),
                    "leaders": [
                        tuple(annotation.GetLeaderPointsAtIndex(i) or ())
                        for i in range(int(annotation.GetLeaderCount()))
                    ],
                }
            )
            if result and math.dist(actual[:2], target[:2]) < 1e-8:
                accepted.append((direction, target))
            if (
                not annotation.SetPosition2(*original)
                or math.dist(tuple(annotation.GetPosition())[:2], original[:2]) > 1e-8
            ):
                raise RuntimeError(
                    "native datum/SF original position could not be restored"
                )
        if accepted:
            row["retained_direction"], target = accepted[0]
            if (
                not annotation.SetPosition2(*target)
                or math.dist(tuple(annotation.GetPosition())[:2], target[:2]) > 1e-8
            ):
                raise RuntimeError("native datum/SF accepted target did not repeat")
        after, after_native = snapshot(adapter, view)
        unchanged(adapter, before, native, after, after_native)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument(
        "--mode", choices=("commands", "leader_position"), default="commands"
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
                "--mode",
                args.mode,
                "--worker",
            ],
            "mixed native annotation commands",
            log_stem="mixed-annotation-commands",
            com=True,
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("--worker requires the machine-global COM seat")

    async def probe(adapter: Any) -> dict[str, str]:
        root = CAD_ROOT / "out/reports"
        root.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="mixed-commands-", dir=root))
        adapter.ownership.register_directory(folder)
        adapter.ownership.register_source(source)
        copy = folder / f"{folder.name}-{source.name}"
        saved = folder / f"observed-{copy.name}"
        shutil.copy2(source, copy)
        hashes = {source: hashlib.sha256(source.read_bytes()).hexdigest()}
        report: dict[str, Any] = {
            "source": str(source),
            "copy": str(copy),
            "commands": [],
        }
        try:
            check("open unique mixed bank copy", await adapter.open_model(str(copy)))
            if Path(adapter.currentModel.GetPathName()).resolve() != copy:
                raise RuntimeError("SolidWorks opened the wrong mixed bank copy")
            drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
            app = _early_bound(adapter.swApp, "ISldWorks")
            selection = _early_bound(
                adapter.currentModel.SelectionManager, "ISelectionMgr"
            )
            views = [
                _early_bound(view, "IView")
                for sheet in drawing.GetViews() or ()
                for view in sheet[1:]
            ]
            for view in views:
                reference = Path(view.ReferencedDocument.GetPathName()).resolve(
                    strict=True
                )
                hashes[reference] = hashlib.sha256(reference.read_bytes()).hexdigest()
            view = next(
                (
                    item
                    for item in views
                    if all(item.GetAnnotationsByType(kind) for kind in _INTERFACES)
                ),
                None,
            )
            if view is None:
                raise RuntimeError("no native view has all three datum/GTol/SF kinds")
            before, native = snapshot(adapter, view)
            report["view"] = view.GetName2()
            report["before"] = before
            original, original_native = before, native
            if args.mode == "leader_position":
                if not drawing.ActivateView(view.GetName2()):
                    raise RuntimeError("native datum/SF view activation rejected")
                report["leader_position_trials"] = leader_position_trials(
                    adapter, view, before, native
                )
            for command in (317, 307) if args.mode == "commands" else ():
                if not drawing.ActivateView(view.GetName2()):
                    raise RuntimeError("mixed native view activation rejected")
                adapter.currentModel.ClearSelection2(True)
                command_report: dict[str, Any] = {"command": command, "selection": []}
                report["commands"].append(command_report)
                for key, (annotation, _entities) in native.items():
                    if not annotation.Select2(True, 0):
                        raise RuntimeError(
                            f"native mixed annotation selection rejected {key}"
                        )
                if int(selection.GetSelectedObjectCount2(-1)) != len(native):
                    raise RuntimeError("mixed native selection count differs")
                for index, (key, (annotation, _entities)) in enumerate(
                    native.items(), 1
                ):
                    kind = before[key]["kind"]
                    specific = _early_bound(
                        selection.GetSelectedObject6(index, -1), _INTERFACES[kind]
                    )
                    if int(app.IsSame(specific.GetAnnotation(), annotation)) != 1:
                        raise RuntimeError(
                            "mixed native selected object identity differs"
                        )
                    command_report["selection"].append(
                        {
                            "key": key,
                            "native_type": selection.GetSelectedObjectType3(index, -1),
                        }
                    )
                enabled = app.IsCommandEnabled(command)
                command_report["enabled"] = enabled
                if enabled:
                    command_report["return"] = app.RunCommand(command, "")
                    if not command_report["return"]:
                        raise RuntimeError("enabled mixed command rejected selection")
                adapter.currentModel.ClearSelection2(True)
                after, after_native = snapshot(adapter, view)
                unchanged(adapter, original, original_native, after, after_native)
                command_report["movement_m"] = {
                    key: math.dist(before[key]["position"], row["position"])
                    for key, row in after.items()
                }
                command_report["after"] = after
                before, native = after, after_native
            pdf = folder / "mixed.pdf"
            result = save_drawing(adapter, str(saved), pdf_path=str(pdf))
            if "pdf" not in result:
                raise RuntimeError(f"mixed bank PDF failed: {result}")
            render_pdf_png(pdf, folder / "mixed.png")
            report["outcome"] = "captured"
        except Exception as error:
            report["error"] = repr(error)
            raise
        finally:
            try:
                current = adapter.currentModel
                if current is not None and Path(current.GetPathName()).resolve() in {
                    copy,
                    saved,
                }:
                    check(
                        "close mixed bank copy", await adapter.close_model(save=False)
                    )
                report["source_unchanged"] = {
                    str(path): hashlib.sha256(path.read_bytes()).hexdigest() == digest
                    for path, digest in hashes.items()
                }
                if not all(report["source_unchanged"].values()):
                    raise RuntimeError("mixed bank control changed source bytes")
            finally:
                (folder / "mixed.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )
                _telemetry.info(f"mixed annotation command observations: {folder}")
        return {"report": str(folder / "mixed.json")}

    _telemetry.set_service("drawing-mixed-native-command-probe")
    return run_copy_diagnostic(probe)


if __name__ == "__main__":
    raise SystemExit(main())
