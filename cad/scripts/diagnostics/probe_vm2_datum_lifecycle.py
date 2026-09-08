"""Cold-open and move/scale a copied VM2 datum drawing; never save its source."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("witness", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    witness_path = args.witness.resolve(strict=True)
    output = args.output.resolve()
    if not witness_path.is_relative_to(ROOT / "cad/out/reports"):
        raise ValueError("witness must belong to this checkout")
    if not output.is_relative_to(ROOT / "cad/out/reports") or output.exists():
        raise ValueError("choose a new own report directory")
    if Path(sys.prefix).resolve() != ROOT / ".venv":
        raise RuntimeError("requires own uv environment")
    if os.environ.get("HARMONIC_SW_AUTOSTART") != "0" or not os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID"):
        raise RuntimeError("requires attach-only mode and inventoried PID")
    from _common import _early_bound, check
    from _drawing_common import render_pdf_png
    from _gear_drawing_entities import visible_circle_edge
    from diagnostics._owned_native_session import run_owned_diagnostic
    from solidworks_mcp.adapters.com_variant import double_array

    async def probe(adapter):
        app = adapter.swApp
        if app.GetDocuments() or app.ActiveDoc is not None:
            raise RuntimeError("requires an empty seat; no documents closed")
        witness = json.loads(witness_path.read_text(encoding="utf-8"))
        if witness["status"] != "observed_and_closed" or witness["selection"] != "edge":
            raise RuntimeError("requires completed semantic-edge insertion witness")
        source = Path(witness["source"]).resolve(strict=True)
        original = Path(witness["exports"]["SLDDRW"]["path"]).resolve(strict=True)
        if source.parent != ROOT / "cad/out/sldprt" or not original.is_relative_to(ROOT / "cad/out/reports"):
            raise RuntimeError("input leaves own experiment")
        if digest(original) != witness["exports"]["SLDDRW"]["sha256"] or digest(source) != witness["source_sha256_after"]:
            raise RuntimeError("input identity changed since insertion witness")
        output.mkdir(parents=True)
        working = output / f"{source.stem}-lifecycle.SLDDRW"
        shutil.copyfile(original, working)
        if digest(working) != digest(original):
            raise RuntimeError("working copy differs")
        receipt = output / "receipt.json"
        report = {
            "kind": "vm2-datum-lifecycle", "status": "running",
            "scope": "copied partial probe drawing, not complete production print acceptance",
            "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "adapter": subprocess.check_output(["git", "-C", "SolidworksMCP-python", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "probe_sha256": digest(__file__), "witness": str(witness_path), "witness_sha256": digest(witness_path),
            "source": str(source), "source_sha256_before": digest(source),
            "original": str(original), "original_sha256": digest(original),
            "working": str(working), "pid": int(app.GetProcessID()), "revision": str(app.RevisionNumber()),
            "started_utc": datetime.now(timezone.utc).isoformat(), "stages": [], "closures": [],
        }
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
            reference = _early_bound(view.ReferencedDocument, "IModelDoc2")
            if Path(str(reference.GetPathName())).resolve() != source:
                raise RuntimeError("drawing reference resolved to another source")
            tags = [_early_bound(raw, "IDatumTag") for raw in view.GetDatumTags() or ()]
            if len(tags) != 1 or str(tags[0].GetLabel()) != "A":
                raise RuntimeError("expected exactly datum A")
            annotation = _early_bound(tags[0].GetAnnotation(), "IAnnotation")
            attached = tuple(annotation.GetAttachedEntities3() or ())
            types = tuple(annotation.GetAttachedEntityTypes() or ())
            if types != (1,) or len(attached) != 1 or attached[0] is None:
                raise RuntimeError("datum does not have exactly one attached model edge")
            edge = _early_bound(attached[0], "IEdge")
            if expected_edge is not None and int(app.IsSame(edge, expected_edge)) != 1:
                raise RuntimeError("datum attaches to a different resolved edge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                raise RuntimeError("datum edge is not circular")
            circle = list(curve.CircleParams)
            radius = witness["target_circle"][6]
            assert_axis(circle, radius)
            cylinders = []
            for face in edge.GetTwoAdjacentFaces2() or ():
                if face is None:
                    raise RuntimeError("datum edge has a missing adjacent face")
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
                   "source_sha256": digest(source)}
            report["stages"].append(row)
            checkpoint()
            if row["source_sha256"] != report["source_sha256_before"]:
                raise RuntimeError("lifecycle changed saved source bytes")
            return row

        async def open_drawing():
            check("cold open datum lifecycle drawing", await adapter.open_model(str(working)))
            draw = _early_bound(adapter.currentModel, "IModelDoc2")
            if Path(str(draw.GetPathName())).resolve() != working:
                raise RuntimeError("wrong active drawing")
            drawing = _early_bound(draw, "IDrawingDoc")
            view = _early_bound(drawing.GetFirstView(), "IView").GetNextView()
            view = _early_bound(view, "IView")
            edge = visible_circle_edge(adapter, view, witness["target_circle"][6] * 2000)
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

        checkpoint()
        try:
            draw, view, edge = await open_drawing()
            initial = observe(view, "cold_open", edge)
            limit = witness["original_call"]["position_tolerance_m"]
            if math.dist(initial["position"][:2], witness["position_after_save"][:2]) > limit:
                raise RuntimeError("cold reopen exceeded unchanged placement tolerance")
            export(draw, "cold_open")
            shift = (0.008, 0.005)
            requested = [initial["view_position"][index] + shift[index] for index in range(2)]
            view.Position = double_array(requested)
            if not draw.EditRebuild3():
                raise RuntimeError("move rebuild rejected")
            moved = observe(view, "moved", edge)
            if math.dist(moved["view_position"], requested) > 1e-8:
                raise RuntimeError("view did not move as requested")
            expected = [initial["position"][index] + shift[index] for index in range(2)]
            report["translation_error_m"] = math.dist(moved["position"][:2], expected)
            if report["translation_error_m"] > limit:
                raise RuntimeError("datum did not follow view within unchanged tolerance")
            export(draw, "moved")
            ratio = list(initial["view_scale"])
            view.ScaleRatio = double_array([ratio[0] * 1.25, ratio[1]])
            if not draw.EditRebuild3():
                raise RuntimeError("scale rebuild rejected")
            scaled = observe(view, "scaled", edge)
            if abs(scaled["view_scale"][0] / scaled["view_scale"][1] - ratio[0] / ratio[1] * 1.25) > 1e-10:
                raise RuntimeError("scale readback rejected")
            export(draw, "scaled")
            view.ScaleRatio = double_array(ratio)
            view.Position = double_array(initial["view_position"])
            if not draw.EditRebuild3():
                raise RuntimeError("restore rebuild rejected")
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
        dodo._exec([sys.executable, str(Path(__file__).resolve()), str(witness_path), str(output), "--worker"], "VM2 datum lifecycle probe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
