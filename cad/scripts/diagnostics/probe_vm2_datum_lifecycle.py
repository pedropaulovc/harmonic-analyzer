"""Cold-open and move/scale a copied VM2 datum drawing; guard source bytes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "cad/scripts")]


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def assert_axis(values, radius):
    """Require a finite cylinder/circle on the source's Z axis, in metres."""
    if len(values) != 7 or not all(math.isfinite(value) for value in values):
        raise RuntimeError("invalid cylindrical geometry")
    if max(abs(values[0]), abs(values[1]), abs(values[3]), abs(values[4]),
           abs(abs(values[5]) - 1), abs(values[6] - radius)) > 1e-8:
        raise RuntimeError(f"datum does not control the intended Z-axis cylinder: {values}")


def lifecycle_inputs(input_path, *, mode, ink_refresh, rack_dimension_location):
    """Resolve pinned local inputs before attaching; never invent a witness."""
    path = Path(input_path).resolve(strict=True)
    if not path.is_file():
        raise ValueError("lifecycle input must be a file")
    if mode == "production":
        if ink_refresh != "cold":
            raise ValueError("production lifecycle requires --ink-refresh cold")
        if rack_dimension_location != "original":
            raise ValueError("production layout must already come from its recipe")
        specifications = {
            "pinion-lift-rod": ("pinion_lift_rod_spec", "ROD_DIA", 0.00002),
            "rack-pinion": ("rack_pinion_spec", "BORE_DIA", 0.0001),
        }
        matches = [stem for stem in specifications
                   if path == ROOT / "cad/out/slddrw" / f"{stem}.SLDDRW"]
        if len(matches) != 1:
            raise ValueError("production input must be one of the two exact own pipeline drawings")
        stem = matches[0]
        module_name, diameter_name, limit = specifications[stem]
        specification = importlib.import_module(module_name)
        radius = getattr(specification, diameter_name) / 2000.0
        if not math.isfinite(radius) or radius <= 0:
            raise ValueError("production specification radius must be positive and finite")
        source = (ROOT / "cad/out/sldprt" / f"{stem}.SLDPRT").resolve(strict=True)
        if source.parent != ROOT / "cad/out/sldprt":
            raise ValueError("production source leaves own pipeline output")
        return {"mode": mode, "source": source, "original": path,
                "radius_m": radius, "position_tolerance_m": limit,
                "specification_path": str(Path(specification.__file__).resolve()),
                "specification_sha256": digest(specification.__file__)}
    if mode != "partial":
        raise ValueError("unknown lifecycle input mode")
    if not path.is_relative_to(ROOT / "cad/out/reports"):
        raise ValueError("witness must belong to this checkout")
    witness = json.loads(path.read_text(encoding="utf-8"))
    if witness["status"] != "observed_and_closed" or witness["selection"] != "edge":
        raise RuntimeError("requires completed semantic-edge insertion witness")
    source = Path(witness["source"]).resolve(strict=True)
    original = Path(witness["exports"]["SLDDRW"]["path"]).resolve(strict=True)
    if source.parent != ROOT / "cad/out/sldprt" or not original.is_relative_to(ROOT / "cad/out/reports"):
        raise RuntimeError("input leaves own experiment")
    if digest(original) != witness["exports"]["SLDDRW"]["sha256"] or digest(source) != witness["source_sha256_after"]:
        raise RuntimeError("input identity changed since insertion witness")
    return {"mode": mode, "source": source, "original": original,
            "radius_m": witness["target_circle"][6],
            "position_tolerance_m": witness["original_call"]["position_tolerance_m"],
            "witness": witness, "witness_path": path}


def assert_annotation_state(state, baseline=None):
    """Require a non-dangling tag and preserve both native shoulder readbacks."""
    if state["is_dangling"] is not False:
        raise RuntimeError("datum annotation is dangling")
    if baseline is None:
        return
    if any(state[key] != baseline[key] for key in ("shoulder", "forced_shoulder")):
        raise RuntimeError("datum shoulder state changed from first cold open")


def edge_ownership(app, edge, source_part, source_extension, view):
    """Map view topology to the source, require exact roundtrip and body identity."""
    from _common import _early_bound

    bodies = tuple(source_part.GetBodies2(0, False) or ())  # swSolidBody, including hidden bodies
    if len(bodies) != 1 or bodies[0] is None:
        raise RuntimeError(f"expected one source solid body, got {len(bodies)}")
    raw_model_edge = source_extension.GetCorrespondingEntity2(edge)
    if raw_model_edge is None:
        raise RuntimeError("no corresponding canonical source edge")
    model_edge = _early_bound(raw_model_edge, "IEdge")
    roundtrip = view.GetCorrespondingEntity(model_edge)
    if roundtrip is None:
        raise RuntimeError("canonical edge has no corresponding drawing-view edge")
    edge_self = int(app.IsSame(edge, edge))
    roundtrip_equality = int(app.IsSame(roundtrip, edge))
    if edge_self != 1 or roundtrip_equality != 1:
        raise RuntimeError(f"edge correspondence roundtrip mismatch: self={edge_self}, roundtrip={roundtrip_equality}")
    body = model_edge.GetBody()
    if body is None:
        raise RuntimeError("canonical datum edge has no owning body")
    self_equality = int(app.IsSame(bodies[0], bodies[0]))
    equality = int(app.IsSame(body, bodies[0]))
    if self_equality != 1 or equality != 1:
        raise RuntimeError(f"datum edge body identity mismatch: self={self_equality}, source={equality}")
    faces = tuple(model_edge.GetTwoAdjacentFaces2() or ())
    if len(faces) != 2 or any(face is None for face in faces):
        raise RuntimeError("datum edge must have exactly two nonnull adjacent faces")
    drawing_body = edge.GetBody()
    return model_edge, faces, {
        "source_solid_body_count": len(bodies), "source_body_self_equality": self_equality,
        "canonical_edge_body_same_as_source": equality, "adjacent_face_count": len(faces),
        "mapped_model_edge": "present", "view_edge_self_equality": edge_self,
        "roundtrip_edge_same": roundtrip_equality,
        "canonical_edge_vs_view_edge": int(app.IsSame(model_edge, edge)),
        "drawing_edge_body_vs_source_body": int(app.IsSame(drawing_body, bodies[0])) if drawing_body is not None else None,
    }


def assert_translated_ink(initial, moved, shift):
    """Reject partially stale arrays, even if one updated line contains the anchor."""
    maximum = 0.0
    for field, offsets in (("datum_lines", (1, 4)), ("datum_triangles", (0, 3, 6)),
                           ("dimension_lines", (4, 7)), ("dimension_triangles", (0, 3, 6))):
        if len(initial[field]) != len(moved[field]):
            raise RuntimeError(f"translated {field} primitive count changed")
        for before, after in zip(initial[field], moved[field], strict=True):
            for offset in offsets:
                expected = [before[offset + index] + shift[index] for index in range(2)]
                actual = after[offset:offset + 2]
                if len(actual) != 2 or not all(math.isfinite(value) for value in actual):
                    raise RuntimeError(f"invalid translated {field} primitive")
                maximum = max(maximum, math.dist(expected, actual))
    if maximum > 1e-8:
        raise RuntimeError(f"translated ink remains stale: error={maximum} m")
    return maximum


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("witness", type=Path, help="insertion receipt, or exact pipeline SLDDRW with --production")
    parser.add_argument("output", type=Path)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--rack-dimension-location", choices=("original", "above"), default="original")
    parser.add_argument("--ink-refresh", choices=("redraw", "cold"), default="redraw")
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args()
    witness_path = args.witness.resolve(strict=True)
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "cad/out/reports") or output.exists():
        raise ValueError("choose a new own report directory")
    if Path(sys.prefix).resolve() != ROOT / ".venv":
        raise RuntimeError("requires own uv environment")
    if os.environ.get("HARMONIC_SW_AUTOSTART") != "0" or not os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID"):
        raise RuntimeError("requires attach-only mode and inventoried PID")
    lifecycle_inputs(
        witness_path, mode="production" if args.production else "partial",
        ink_refresh=args.ink_refresh, rack_dimension_location=args.rack_dimension_location,
    )
    from _common import _early_bound, check
    from _drawing_common import dimension_name, model_point_in_view, render_pdf_png
    from _gear_drawing_entities import visible_circle_edge
    from diagnostics._owned_native_session import run_owned_diagnostic
    from solidworks_mcp.adapters.com_variant import double_array

    async def probe(adapter):
        app = adapter.swApp
        if app.GetDocuments() or app.ActiveDoc is not None:
            raise RuntimeError("requires an empty seat; no documents closed")
        inputs = lifecycle_inputs(
            witness_path, mode="production" if args.production else "partial",
            ink_refresh=args.ink_refresh, rack_dimension_location=args.rack_dimension_location,
        )
        source, original = inputs["source"], inputs["original"]
        radius, limit = inputs["radius_m"], inputs["position_tolerance_m"]
        output.mkdir(parents=True)
        working = output / f"{source.stem}-lifecycle.SLDDRW"
        shutil.copyfile(original, working)
        if digest(working) != digest(original):
            raise RuntimeError("working copy differs")
        receipt = output / "receipt.json"
        report = {
            "kind": "vm2-datum-lifecycle", "status": "running",
            "scope": ("complete production drawing lifecycle; first cold open is baseline, no pre-save insertion proof"
                      if inputs["mode"] == "production" else
                      "copied partial probe drawing, not complete production print acceptance"),
            "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "adapter": subprocess.check_output(["git", "-C", "SolidworksMCP-python", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "probe_sha256": digest(__file__), "input_mode": inputs["mode"],
            "radius_m": radius, "position_tolerance_m": limit,
            "source": str(source), "source_sha256_before": digest(source),
            "original": str(original), "original_sha256": digest(original),
            "working": str(working), "pid": int(app.GetProcessID()), "revision": str(app.RevisionNumber()),
            "started_utc": datetime.now(timezone.utc).isoformat(), "stages": [], "closures": [],
            "rack_dimension_location": args.rack_dimension_location,
            "ink_refresh": args.ink_refresh,
            "annotation_state_readbacks": [],
        }
        if inputs["mode"] == "partial":
            report.update(witness=str(witness_path), witness_sha256=digest(witness_path))
        if inputs["mode"] == "production":
            report.update(specification_path=inputs["specification_path"],
                          specification_sha256=inputs["specification_sha256"],
                          placement_reference="first_cold_open_baseline_no_pre_save_witness")
        started = time.perf_counter()

        def checkpoint():
            receipt.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

        def close_owned():
            while app.GetDocuments():
                docs = [_early_bound(raw, "IModelDoc2") for raw in app.GetDocuments()]
                rows = [(Path(str(doc.GetPathName())).resolve(), str(doc.GetTitle()), int(doc.GetType())) for doc in docs]
                if any(row[0] not in {source, working} for row in rows):
                    raise RuntimeError("unowned document present; refusing closure")
                if any(not row[1] for row in rows) or len({row[1].casefold() for row in rows}) != len(rows):
                    raise RuntimeError("ambiguous close titles")
                target = min(rows, key=lambda row: row[2] != 3)
                app.CloseDoc(target[1])
                remaining = [_early_bound(raw, "IModelDoc2") for raw in app.GetDocuments() or ()]
                if any(Path(str(doc.GetPathName())).resolve() == target[0] for doc in remaining):
                    raise RuntimeError("owned closure did not remove target")
                report["closures"].append({"path": str(target[0]), "title": target[1]})
                checkpoint()
            if app.ActiveDoc is not None:
                raise RuntimeError("active document remains")

        def observe(view, name, expected_edge=None):
            _early_bound(adapter.currentModel, "IModelDoc2").GraphicsRedraw2()
            reference = _early_bound(view.ReferencedDocument, "IModelDoc2")
            if Path(str(reference.GetPathName())).resolve() != source:
                raise RuntimeError("drawing reference resolved to another source")
            tags = [_early_bound(raw, "IDatumTag") for raw in view.GetDatumTags() or ()]
            if len(tags) != 1 or str(tags[0].GetLabel()) != "A":
                raise RuntimeError("expected exactly datum A")
            annotation = _early_bound(tags[0].GetAnnotation(), "IAnnotation")
            state = {"stage": name, "is_dangling": bool(annotation.IsDangling()),
                     "shoulder": bool(tags[0].Shoulder), "forced_shoulder": bool(tags[0].ForcedShoulder)}
            report["annotation_state_readbacks"].append(state)
            checkpoint()
            assert_annotation_state(state, report["annotation_state_readbacks"][0])
            attached = tuple(annotation.GetAttachedEntities3() or ())
            types = tuple(annotation.GetAttachedEntityTypes() or ())
            if types != (1,) or len(attached) != 1 or attached[0] is None:
                raise RuntimeError("datum does not have exactly one attached model edge")
            edge = _early_bound(attached[0], "IEdge")
            if expected_edge is not None and int(app.IsSame(edge, expected_edge)) != 1:
                raise RuntimeError("datum attaches to a different resolved edge")
            model_edge, faces, ownership = edge_ownership(
                app, edge, _early_bound(reference, "IPartDoc"),
                _early_bound(reference.Extension, "IModelDocExtension"), view,
            )
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                raise RuntimeError("datum edge is not circular")
            circle = list(curve.CircleParams)
            assert_axis(circle, radius)
            model_curve = _early_bound(model_edge.GetCurve(), "ICurve")
            if not model_curve.IsCircle():
                raise RuntimeError("canonical datum edge is not circular")
            model_circle = list(model_curve.CircleParams)
            assert_axis(model_circle, radius)
            if math.dist(model_circle, circle) > 1e-8:
                raise RuntimeError("canonical source circle differs from drawing-view circle")
            cylinders = []
            for face in faces:
                surface = _early_bound(_early_bound(face, "IFace2").GetSurface(), "ISurface")
                if surface.IsCylinder():
                    cylinders.append(list(surface.CylinderParams))
            if len(cylinders) != 1:
                raise RuntimeError("datum must border exactly one cylindrical face")
            assert_axis(cylinders[0], radius)
            position = list(annotation.GetPosition() or ())
            if len(position) != 3 or not all(math.isfinite(value) for value in position):
                raise RuntimeError("invalid datum position")
            row = {"stage": name, "position": position, "view_position": list(view.Position),
                   "view_scale": list(view.ScaleRatio), "circle": circle, "cylinder": cylinders[0],
                   "attachment_type": 1, "resolved_edge_same": int(app.IsSame(edge, expected_edge)) if expected_edge is not None else None,
                   "source_sha256": digest(source), "body_ownership": ownership,
                   "canonical_circle": model_circle}
            report["stages"].append(row)
            row["datum_lines"] = [list(tags[0].GetLineAtIndex(index)) for index in range(tags[0].GetLineCount())]
            row["datum_triangles"] = [list(tags[0].GetTriangleAtIndex(index)) for index in range(tags[0].GetTriangleCount())]
            points = [tuple(line[offset:offset + 2]) for line in row["datum_lines"] for offset in (1, 4)]
            if not points or min(math.dist(point, position[:2]) for point in points) > 1e-8:
                raise RuntimeError("datum primitives do not contain the current annotation anchor")
            center = model_point_in_view(adapter, view, tuple(circle[:3]), label="datum rim center")
            rim_radius = radius * row["view_scale"][0] / row["view_scale"][1]
            row["projected_rim_center"] = center
            row["projected_rim_radius_m"] = rim_radius
            row["datum_rim_error_m"] = min(abs(math.dist(point, center) - rim_radius) for point in points)
            if row["datum_rim_error_m"] > 1e-8:
                raise RuntimeError("datum ink no longer terminates on the projected intended rim")
            dimension = diameter_annotation(view)
            display = _early_bound(dimension.GetSpecificAnnotation(), "IDisplayDimension")
            data = _early_bound(display.GetDisplayData(), "IDisplayData")
            row["dimension_position"] = list(dimension.GetPosition())
            row["dimension_lines"] = [list(data.GetLineAtIndex2(index)) for index in range(data.GetLineCount())]
            row["dimension_triangles"] = [list(data.GetTriangleAtIndex(index)) for index in range(data.GetTriangleCount())]
            if not row["datum_lines"] or not row["datum_triangles"] or not row["dimension_lines"]:
                raise RuntimeError("missing datum/dimension ink primitives")
            checkpoint()
            if row["source_sha256"] != report["source_sha256_before"]:
                raise RuntimeError("lifecycle changed saved source bytes")
            return row

        def diameter_annotation(view):
            name = "RodDia" if source.stem == "pinion-lift-rod" else "BoreDia"
            annotations = [_early_bound(raw, "IAnnotation") for raw in view.GetAnnotations() or ()]
            matches = [item for item in annotations if int(item.GetType()) == 4 and dimension_name(adapter, item) == name]
            if len(matches) != 1:
                raise RuntimeError(f"expected exactly one {name}")
            return matches[0]

        async def open_drawing():
            check("cold open datum lifecycle drawing", await adapter.open_model(str(working)))
            draw = _early_bound(adapter.currentModel, "IModelDoc2")
            if Path(str(draw.GetPathName())).resolve() != working:
                raise RuntimeError("wrong active drawing")
            drawing = _early_bound(draw, "IDrawingDoc")
            view = _early_bound(drawing.GetFirstView(), "IView").GetNextView()
            view = _early_bound(view, "IView")
            edge = visible_circle_edge(adapter, view, radius * 2000)
            return draw, view, edge

        def export(draw, name):
            pdf = output / f"{name}.pdf"
            draw.ClearSelection2(True)
            result = draw.SaveAs3(str(pdf), 0, 0)
            if type(result) is not int or result != 0 or not pdf.is_file():
                raise RuntimeError(f"PDF export rejected: {result!r}")
            png = output / f"{name}.png"
            render_pdf_png(pdf, png, expected_pages=1)
            report["stages"][-1]["exports"] = {str(path): digest(path) for path in (pdf, png)}
            checkpoint()

        async def refresh_ink(draw, view, edge, name):
            if args.ink_refresh == "redraw":
                return draw, view, edge
            before = {"stage": name, "view_position": list(view.Position),
                      "view_scale": list(view.ScaleRatio)}
            result = draw.SaveAs3(str(working), 0, 0)
            if type(result) is not int or result != 0:
                raise RuntimeError(f"save {name} drawing rejected: {result!r}")
            close_owned()
            draw, view, edge = await open_drawing()
            if math.dist(before["view_position"], list(view.Position)) > 1e-8:
                raise RuntimeError("cold ink refresh changed view position")
            if math.dist(before["view_scale"], list(view.ScaleRatio)) > 1e-10:
                raise RuntimeError("cold ink refresh changed view scale")
            report.setdefault("ink_refreshes", []).append(before)
            checkpoint()
            return draw, view, edge

        checkpoint()
        try:
            draw, view, edge = await open_drawing()
            if args.rack_dimension_location == "above":
                if source.stem != "rack-pinion":
                    raise RuntimeError("rack layout delta is only valid for rack-pinion")
                dimension = diameter_annotation(view)
                previous = list(dimension.GetPosition())
                if not dimension.SetPosition2(previous[0], 0.213, previous[2]):
                    raise RuntimeError("rack diameter layout change rejected")
                if not draw.EditRebuild3():
                    raise RuntimeError("rack diameter layout rebuild rejected")
                if math.dist(list(dimension.GetPosition())[:2], (previous[0], 0.213)) > 1e-8:
                    raise RuntimeError("rack diameter layout readback differs")
            initial = observe(view, "cold_open", edge)
            if inputs["mode"] == "partial":
                if math.dist(initial["position"][:2], inputs["witness"]["position_after_save"][:2]) > limit:
                    raise RuntimeError("cold reopen exceeded unchanged placement tolerance")
            export(draw, "cold_open")
            shift = (0.008, 0.005)
            requested = [initial["view_position"][index] + shift[index] for index in range(2)]
            view.Position = double_array(requested)
            if not draw.EditRebuild3():
                raise RuntimeError("move rebuild rejected")
            draw, view, edge = await refresh_ink(draw, view, edge, "moved")
            moved = observe(view, "moved", edge)
            if math.dist(moved["view_position"], requested) > 1e-8:
                raise RuntimeError("view did not move as requested")
            expected = [initial["position"][index] + shift[index] for index in range(2)]
            report["translation_error_m"] = math.dist(moved["position"][:2], expected)
            if report["translation_error_m"] > limit:
                raise RuntimeError("datum did not follow view within unchanged tolerance")
            report["translation_ink_error_m"] = assert_translated_ink(initial, moved, shift)
            export(draw, "moved")
            ratio = list(initial["view_scale"])
            view.ScaleRatio = double_array([ratio[0] * 1.25, ratio[1]])
            if not draw.EditRebuild3():
                raise RuntimeError("scale rebuild rejected")
            draw, view, edge = await refresh_ink(draw, view, edge, "scaled")
            scaled = observe(view, "scaled", edge)
            if abs(scaled["view_scale"][0] / scaled["view_scale"][1] - ratio[0] / ratio[1] * 1.25) > 1e-10:
                raise RuntimeError("scale readback rejected")
            export(draw, "scaled")
            view.ScaleRatio = double_array(ratio)
            view.Position = double_array(initial["view_position"])
            if not draw.EditRebuild3():
                raise RuntimeError("restore rebuild rejected")
            draw, view, edge = await refresh_ink(draw, view, edge, "restored")
            restored = observe(view, "restored", edge)
            report["restore_error_m"] = math.dist(restored["position"][:2], initial["position"][:2])
            if report["restore_error_m"] > limit:
                raise RuntimeError("restored datum exceeded unchanged tolerance")
            result = draw.SaveAs3(str(working), 0, 0)
            if type(result) is not int or result != 0:
                raise RuntimeError(f"save restored drawing rejected: {result!r}")
            close_owned()
            draw, view, edge = await open_drawing()
            reopened = observe(view, "second_cold_open", edge)
            report["second_reopen_error_m"] = math.dist(reopened["position"][:2], initial["position"][:2])
            if report["second_reopen_error_m"] > limit:
                raise RuntimeError("second cold reopen exceeded unchanged tolerance")
            export(draw, "second_cold_open")
            close_owned()
            if digest(source) != report["source_sha256_before"] or digest(original) != report["original_sha256"]:
                raise RuntimeError("lifecycle changed original input bytes")
            report.update(status="passed", source_sha256_after=digest(source), working_sha256=digest(working))
        except Exception as error:
            report.update(status="failed", error=repr(error))
            raise
        finally:
            report.update(elapsed_s=time.perf_counter() - started, ended_utc=datetime.now(timezone.utc).isoformat())
            checkpoint()
        return {"receipt": str(receipt), "sha256": digest(receipt)}

    if args.worker:
        return run_owned_diagnostic(probe)
    import dodo
    with dodo._com_seat("VM2 datum lifecycle probe"):
        command = [sys.executable, str(Path(__file__).resolve()), str(witness_path), str(output), "--worker",
                   "--rack-dimension-location", args.rack_dimension_location,
                   "--ink-refresh", args.ink_refresh]
        if args.production:
            command.append("--production")
        dodo._exec(command, "VM2 datum lifecycle probe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
