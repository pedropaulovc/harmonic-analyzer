"""Historical coordinate-datum experiment, before the production helper migration.

Runs the unchanged recipe only up to its datum call, then observes the production
helper or a native insertion control. Partial sheets are diagnostic evidence,
never production outputs or completed print acceptance. No source is saved.

Supported recipe versions are pinned to 6976b79e4bcf3bf158cf4a688813e01967177299.
Current recipes use add_native_axis_datum and are deliberately rejected before
COM attachment. Validate current pipeline drawings with probe_vm2_datum_lifecycle
--production --ink-refresh cold; do not reinterpret this historical experiment.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "cad/scripts")]
HISTORICAL_REPLAY_COMMIT = "6976b79e4bcf3bf158cf4a688813e01967177299"
HISTORICAL_RECIPE_BLOBS = {
    "pinion_lift_rod": "a95acf171a8b005e53b93dbb5319450cff71b09a",
    "rack_pinion": "a8f00d149d55d23115d149eeb77b31aefc1d1f48",
}


def historical_recipe_blob(part):
    """Apply Git's checkout text filters so Windows CRLF is not version drift."""
    relative = f"cad/scripts/draw_{part}.py"
    return subprocess.check_output(
        ["git", "hash-object", "--path", relative, str(ROOT / relative)],
        cwd=ROOT, text=True,
    ).strip()


def require_historical_recipe(part):
    if historical_recipe_blob(part) != HISTORICAL_RECIPE_BLOBS[part]:
        raise RuntimeError(
            f"historical attachment probe does not support the current {part} recipe; "
            f"replay {HISTORICAL_REPLAY_COMMIT} in a separate isolated worktree with its pinned adapter, "
            "or validate current pipeline drawings with probe_vm2_datum_lifecycle.py "
            "--production --ink-refresh cold"
        )


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class DatumBoundary(Exception):
    """Stop the unchanged recipe immediately before its datum creation."""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=("pinion_lift_rod", "rack_pinion"))
    parser.add_argument("selection", choices=("coordinate", "edge", "dimension"))
    parser.add_argument("placement", choices=("requested", "native"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "cad/out/reports") or output.exists():
        raise ValueError("choose a new output directory inside this checkout's reports")
    require_historical_recipe(args.part)
    if Path(sys.prefix).resolve() != ROOT / ".venv":
        raise RuntimeError("use this checkout's own uv environment")
    if os.environ.get("HARMONIC_SW_AUTOSTART") != "0":
        raise RuntimeError("attach-only mode required")
    if not os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID"):
        raise RuntimeError("explicit inventoried SolidWorks PID required")
    if os.environ.get("HARMONIC_REMOTE_CACHE_MODE") != "off":
        raise RuntimeError("disable remote cache transfers")
    from _common import _early_bound
    import _drawing_common as common
    from _gear_drawing_entities import visible_circle_edge
    from diagnostics._owned_native_session import run_owned_diagnostic
    from solidworks_mcp.adapters.com_variant import null_callout
    import _telemetry

    async def probe(adapter):
        app = adapter.swApp
        if app.GetDocuments() or app.ActiveDoc is not None:
            raise RuntimeError("probe requires an empty inventory; no documents closed")
        recipe = importlib.import_module(f"draw_{args.part}")
        source = recipe.SOURCE.resolve(strict=True)
        if source.parent != ROOT / "cad/out/sldprt":
            raise RuntimeError("source leaves own checkout")
        output.mkdir(parents=True)
        receipt = output / "receipt.json"
        report = {
            "kind": "vm2-datum-one-variable-probe",
            "selection": args.selection, "placement": args.placement,
            "part": args.part, "source": str(source),
            "source_sha256_before": digest(source),
            "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "adapter": subprocess.check_output(["git", "-C", "SolidworksMCP-python", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "probe_sha256": digest(__file__),
            "recipe_sha256": digest(recipe.__file__),
            "helper_sha256": digest(common.__file__),
            "pid": int(app.GetProcessID()), "revision": str(app.RevisionNumber()),
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "status": "running", "scope": "partial diagnostic sheet, not acceptance",
        }
        started = time.perf_counter()

        def checkpoint():
            receipt.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

        checkpoint()
        captured = {}

        def capture(_adapter, view, **kwargs):
            captured.update(view=view, kwargs=kwargs)
            raise DatumBoundary()

        original = recipe.add_datum_feature
        recipe.add_datum_feature = capture
        try:
            with _telemetry.span("datum.probe.prepare", part=args.part):
                try:
                    await recipe.build(adapter)
                except DatumBoundary:
                    pass
                else:
                    raise RuntimeError("recipe never reached its datum boundary")
            recipe.add_datum_feature = original
            draw = _early_bound(adapter.currentModel, "IModelDoc2")
            view, kwargs = captured["view"], dict(captured["kwargs"])
            report["prepared_drawing"] = {
                "title": str(draw.GetTitle()), "path": str(draw.GetPathName()),
                "source": str(source), "datum_view": str(view.GetName2()),
            }
            report["original_call"] = kwargs.copy()
            report["view_position"] = list(view.Position)
            report["view_scale"] = list(view.ScaleRatio)
            diameter = recipe.ROD_DIA if args.part == "pinion_lift_rod" else recipe.BORE_DIA
            edge = visible_circle_edge(adapter, view, diameter)
            curve = _early_bound(_early_bound(edge, "IEdge").GetCurve(), "ICurve")
            if not curve.IsCircle():
                raise RuntimeError("resolved target is not circular")
            report["target_circle"] = list(curve.CircleParams)
            report["target_self_equality"] = int(app.IsSame(edge, edge))
            if report["target_self_equality"] != 1:
                raise RuntimeError("native identity positive control failed")
            if args.selection == "edge":
                kwargs.pop("edge_xy")
                kwargs["entity"] = edge
            dimension = None
            if args.selection == "dimension":
                name = "RodDia" if args.part == "pinion_lift_rod" else "BoreDia"
                annotations = [_early_bound(raw, "IAnnotation") for raw in view.GetAnnotations() or ()]
                dimensions = [annotation for annotation in annotations if int(annotation.GetType()) == 4]
                names = [common.dimension_name(adapter, annotation) for annotation in dimensions]
                report["dimension_names"] = names
                matches = [annotation for annotation, actual in zip(dimensions, names) if actual == name]
                if len(matches) != 1:
                    raise RuntimeError(f"expected exactly one {name} dimension")
                dimension = _early_bound(matches[0], "IAnnotation")
                kwargs.pop("edge_xy")
                kwargs["annotation"] = dimension
            checkpoint()
            with _telemetry.span("datum.probe.insert", selection=args.selection, placement=args.placement):
                if args.placement == "requested":
                    try:
                        original(adapter, view, **kwargs)
                    except RuntimeError as error:
                        report["production_helper"] = {"status": "rejected", "error": str(error)}
                        checkpoint()
                        if "position did not persist" not in str(error):
                            raise
                    else:
                        report["production_helper"] = {"status": "passed"}
                else:
                    # Native control, not a production replacement for the helper.
                    if dimension is not None:
                        drawing = _early_bound(draw, "IDrawingDoc")
                        if not drawing.ActivateView(view.GetName2()):
                            raise RuntimeError("failed to activate dimension view")
                        draw.ClearSelection2(True)
                        if not dimension.Select3(False, null_callout()):
                            raise RuntimeError("failed native-control dimension selection")
                    else:
                        common._select_annotation_entity(
                            adapter, view, edge_xy=kwargs.get("edge_xy"),
                            edge_entity=None, entity=kwargs.get("entity"),
                            entity_type="EDGE", label=kwargs["label"],
                        )
                    tag = draw.InsertDatumTag2()
                    if tag is None:
                        raise RuntimeError("native datum insertion returned no tag")
                    tag = _early_bound(tag, "IDatumTag")
                    if not tag.SetLabel("A"):
                        raise RuntimeError("native datum label rejected")
                    if kwargs.get("shoulder"):
                        tag.Shoulder = True
                    report["production_helper"] = {"status": "not_called_native_control"}
            tags = tuple(view.GetDatumTags() or ())
            if len(tags) != 1:
                raise RuntimeError("expected one newly authored datum")
            tag = _early_bound(tags[0], "IDatumTag")
            annotation = _early_bound(tag.GetAnnotation(), "IAnnotation")
            position = list(annotation.GetPosition() or ())
            attached = tuple(annotation.GetAttachedEntities3() or ())
            types = tuple(annotation.GetAttachedEntityTypes() or ())
            report["datum"] = {
                "label": str(tag.GetLabel()), "position": position,
                "shoulder": bool(tag.Shoulder), "forced_shoulder": bool(tag.ForcedShoulder),
                "attachment_types": types,
                "attachment_count": len(attached),
                "same_as_target_edge": [int(app.IsSame(item, edge)) if item is not None else None for item in attached],
                "same_as_dimension": [int(app.IsSame(item, dimension)) if item is not None else None for item in attached] if dimension is not None else [],
                "leaders": [list(annotation.GetLeaderPointsAtIndex(index) or ()) for index in range(annotation.GetLeaderCount())],
            }
            if len(position) != 3 or not all(math.isfinite(value) for value in position):
                raise RuntimeError("invalid datum position")
            report["requested_xy_error_m"] = math.hypot(
                position[0] - kwargs["symbol_xy"][0], position[1] - kwargs["symbol_xy"][1]
            )
            report["within_original_xy_limit"] = report["requested_xy_error_m"] <= kwargs["position_tolerance_m"]
            checkpoint()
            draw.ClearSelection2(True)
            if not draw.EditRebuild3():
                raise RuntimeError("diagnostic drawing rebuild rejected")
            report["position_after_rebuild"] = list(annotation.GetPosition() or ())
            report["exports"] = {}
            with _telemetry.span("datum.probe.export"):
                for suffix in ("SLDDRW", "pdf"):
                    path = output / f"partial.{suffix}"
                    code = draw.SaveAs3(str(path), 0, 0)
                    report["exports"][suffix] = {"return": code, "path": str(path)}
                    checkpoint()
                    if type(code) is not int or code != 0 or not path.is_file():
                        raise RuntimeError(f"diagnostic SaveAs3 rejected: {suffix}: {code!r}")
                    report["exports"][suffix]["sha256"] = digest(path)
                common.render_pdf_png(output / "partial.pdf", output / "partial.png", expected_pages=1)
                report["exports"]["png"] = {"path": str(output / "partial.png"), "sha256": digest(output / "partial.png")}
            report["position_after_save"] = list(annotation.GetPosition() or ())
            report["source_sha256_after"] = digest(source)
            if report["source_sha256_after"] != report["source_sha256_before"]:
                raise RuntimeError("diagnostic export changed saved source bytes")
            # Every document began in this probe's empty session. Still verify
            # exact paths before closing the diagnostic drawing and source.
            allowed = {source, output / "partial.SLDDRW"}
            documents = [_early_bound(raw, "IModelDoc2") for raw in app.GetDocuments() or ()]
            if any(Path(str(doc.GetPathName())).resolve() not in allowed for doc in documents):
                raise RuntimeError("unexpected document remains; nothing closed")
            targets = [(str(doc.GetPathName()), str(doc.GetTitle()), int(doc.GetType())) for doc in documents]
            if any(not row[1] for row in targets) or len({row[1].casefold() for row in targets}) != len(targets):
                raise RuntimeError("ambiguous close titles; nothing closed")
            report["closed_without_save"] = []
            for target_path, title, _kind in sorted(targets, key=lambda row: row[2] != 3):
                current = [_early_bound(raw, "IModelDoc2") for raw in app.GetDocuments() or ()]
                pairs = [(str(doc.GetPathName()), str(doc.GetTitle())) for doc in current]
                if any(pair not in [(row[0], row[1]) for row in targets] for pair in pairs):
                    raise RuntimeError("unexpected document appeared during closure")
                if (target_path, title) not in pairs:
                    continue
                app.CloseDoc(title)
                report["closed_without_save"].append({"path": target_path, "title": title})
                checkpoint()
            if app.GetDocuments() or app.ActiveDoc is not None:
                raise RuntimeError("probe did not return an empty inventory")
            report["source_sha256_after_close"] = digest(source)
            if report["source_sha256_after_close"] != report["source_sha256_before"]:
                raise RuntimeError("probe closure changed source bytes")
            report["status"] = "observed_and_closed"
        except Exception as error:
            report.update(status="failed", error=repr(error))
            raise
        finally:
            recipe.add_datum_feature = original
            report["elapsed_s"] = time.perf_counter() - started
            report["ended_utc"] = datetime.now(timezone.utc).isoformat()
            checkpoint()
        return {"receipt": str(receipt), "sha256": digest(receipt)}

    if args.worker:
        return run_owned_diagnostic(probe)
    import dodo
    with dodo._com_seat("VM2 datum attachment probe"):
        dodo._exec([
            sys.executable, str(Path(__file__).resolve()), args.part,
            args.selection, args.placement, str(output), "--worker",
        ], "VM2 datum attachment probe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
