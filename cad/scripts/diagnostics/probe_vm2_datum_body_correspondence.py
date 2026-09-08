"""Read-only correspondence control on the witnessed failed rack drawing."""

import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "cad/scripts")]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    if len(sys.argv) != 3:
        raise ValueError("provide ownership receipt and new output receipt")
    witness_path, output = [Path(value).resolve() for value in sys.argv[1:]]
    if not witness_path.is_relative_to(ROOT / "cad/out/reports") or not output.is_relative_to(ROOT / "cad/out/reports") or output.exists():
        raise ValueError("requires own witness and new own receipt")
    if Path(sys.prefix).resolve() != ROOT / ".venv" or os.environ.get("HARMONIC_SW_AUTOSTART") != "0":
        raise RuntimeError("own uv and attach-only mode required")
    from _common import _early_bound
    from _gear_drawing_entities import visible_circle_edge
    from diagnostics._owned_native_session import run_owned_diagnostic
    import dodo

    async def probe(adapter):
        app = adapter.swApp
        witness = json.loads(witness_path.read_text(encoding="utf-8"))
        if witness["status"] != "read_only_complete" or int(app.GetProcessID()) != witness["pid"]:
            raise RuntimeError("ownership witness is not current")
        docs = [_early_bound(raw, "IModelDoc2") for raw in app.GetDocuments() or ()]
        rows = [{"path": str(doc.GetPathName()), "title": str(doc.GetTitle()), "type": int(doc.GetType()),
                 "state": "dirty" if doc.GetSaveFlag() else "clean"} for doc in docs]
        expected = [{key: row[key] for key in ("path", "title", "type", "state")} for row in witness["documents"]]
        if rows != expected or len(rows) != 2:
            raise RuntimeError("document inventory differs from witness")
        source = ROOT / "cad/out/sldprt/rack-pinion.SLDPRT"
        source_row = next(row for row in witness["documents"] if row["type"] == 1)
        if Path(source_row["path"]).resolve() != source or digest(source) != source_row["saved_sha256_after"]:
            raise RuntimeError("source identity differs")
        draw = next(doc for doc in docs if int(doc.GetType()) == 3)
        adapter.currentModel = draw
        view = _early_bound(_early_bound(draw, "IDrawingDoc").GetFirstView(), "IView").GetNextView()
        view = _early_bound(view, "IView")
        model = _early_bound(view.ReferencedDocument, "IModelDoc2")
        if Path(str(model.GetPathName())).resolve() != source:
            raise RuntimeError("view references another source")
        edge = visible_circle_edge(adapter, view, 5.0)
        part = _early_bound(model, "IPartDoc")
        bodies = tuple(part.GetBodies2(0, False) or ())
        if len(bodies) != 1:
            raise RuntimeError("expected one source solid body")
        edge_body = edge.GetBody()
        result = {"kind": "vm2-body-correspondence", "source": str(source),
                  "source_sha256_before": digest(source), "documents_before": rows,
                  "body_self_same": int(app.IsSame(bodies[0], bodies[0])),
                  "edge_body_self_same": int(app.IsSame(edge_body, edge_body)),
                  "drawing_edge_body_vs_source_body": int(app.IsSame(edge_body, bodies[0]))}
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        extension = _early_bound(model.Extension, "IModelDocExtension")
        model_edge_raw = extension.GetCorrespondingEntity2(edge)
        result["mapped_model_edge"] = "missing" if model_edge_raw is None else "present"
        if model_edge_raw is not None:
            model_edge = _early_bound(model_edge_raw, "IEdge")
            result["mapped_edge_body_vs_source_body"] = int(app.IsSame(model_edge.GetBody(), bodies[0]))
            result["mapped_edge_vs_input"] = int(app.IsSame(model_edge, edge))
            result["mapped_circle"] = list(_early_bound(model_edge.GetCurve(), "ICurve").CircleParams)
            back = view.GetCorrespondingEntity(model_edge)
            result["roundtrip_edge_same"] = int(app.IsSame(back, edge)) if back is not None else None
            result["roundtrip_body_same"] = int(app.IsSame(_early_bound(back, "IEdge").GetBody(), edge_body)) if back is not None else None
        result["source_sha256_after"] = digest(source)
        result["documents_after"] = [{"path": str(doc.GetPathName()), "title": str(doc.GetTitle()), "type": int(doc.GetType()),
                                       "state": "dirty" if doc.GetSaveFlag() else "clean"} for doc in docs]
        result["status"] = "read_only_complete"
        if result["source_sha256_after"] != result["source_sha256_before"] or result["documents_after"] != rows:
            result["status"] = "state_changed"
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        if result["status"] != "read_only_complete":
            raise RuntimeError("read-only probe changed state")
        return result

    with dodo._com_seat("VM2 read-only body correspondence"):
        return run_owned_diagnostic(probe)


if __name__ == "__main__":
    raise SystemExit(main())
