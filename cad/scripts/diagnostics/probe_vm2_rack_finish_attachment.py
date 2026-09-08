"""Compare finish attachment on the owned failed drawing and saved control.

Attach only. By default, neither edit annotations nor close the failed drawing.
The saved control is opened for readback and closed without saving. The explicit
--reattach-failed experiment edits only the witnessed unsaved finish association.
--close-failed discards only that witnessed drawing and its own source, without saving.
--fresh-insert replaces only the copied drawing's finish for a selection-point control.
--save-reopen saves only an explicit owned diagnostic copy, then cold-reopens it.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "cad/scripts")]


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("witness", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--reattach-failed", action="store_true")
    parser.add_argument("--point-trials", action="store_true")
    parser.add_argument("--close-failed", action="store_true")
    parser.add_argument("--saved-candidate", type=Path)
    parser.add_argument("--save-reopen", action="store_true")
    parser.add_argument("--fresh-insert", action="store_true")
    args = parser.parse_args()
    if args.point_trials and not args.reattach_failed:
        parser.error("--point-trials requires --reattach-failed")
    if args.fresh_insert and (not args.saved_candidate or args.reattach_failed):
        parser.error("--fresh-insert requires --saved-candidate and excludes --reattach-failed")
    if args.save_reopen and (not args.saved_candidate or not (args.point_trials or args.fresh_insert)):
        parser.error("--save-reopen requires --saved-candidate and a placement experiment")
    if args.save_reopen and args.close_failed:
        parser.error("--save-reopen excludes --close-failed; use a new closure witness afterward")
    witness_path, output = args.witness.resolve(strict=True), args.output.resolve()
    candidate = args.saved_candidate.resolve(strict=True) if args.saved_candidate else None
    if candidate is not None and (not candidate.is_relative_to(ROOT / "cad/out/reports/datum-placement") or candidate.suffix.upper() != ".SLDDRW"):
        raise RuntimeError("candidate must be an own diagnostic drawing copy")
    if not witness_path.is_relative_to(ROOT / "cad/out/reports") or not output.is_relative_to(ROOT / "cad/out/reports") or output.exists():
        raise RuntimeError("requires own witness and new own output")
    if Path(sys.prefix).resolve() != ROOT / ".venv" or os.environ.get("HARMONIC_SW_AUTOSTART") != "0":
        raise RuntimeError("own uv and attach-only mode required")
    witness = json.loads(witness_path.read_text(encoding="utf-8"))
    from _common import _early_bound, check
    from _gear_drawing_entities import visible_circle_edge
    from diagnostics._owned_native_session import run_owned_diagnostic
    from diagnostics.probe_vm2_datum_lifecycle import read_rack_finish
    import dodo

    async def probe(adapter):
        app = adapter.swApp
        source = ROOT / "cad/out/sldprt/rack-pinion.SLDPRT"
        control = ROOT / "cad/out/slddrw/rack-pinion.SLDDRW"
        docs = [_early_bound(raw, "IModelDoc2") for raw in app.GetDocuments() or ()]
        actual = [(str(doc.GetPathName()), str(doc.GetTitle()), int(doc.GetType()),
                   "dirty" if doc.GetSaveFlag() else "clean") for doc in docs]
        expected = [(row["path"], row["title"], row["type"], row["state"]) for row in witness["documents"]]
        if witness["status"] != "read_only_complete" or int(app.GetProcessID()) != witness["pid"] or actual != expected:
            raise RuntimeError("ownership witness no longer matches")
        if len(docs) != 2 or {row[0] for row in actual} != {str(source), str(candidate) if candidate else ""}:
            raise RuntimeError("expected only own source and unsaved failed drawing")
        source_witness = next(row for row in witness["documents"] if row["path"] == str(source))
        if digest(source) != source_witness["saved_sha256_before"]:
            raise RuntimeError("source identity changed since inventory")
        failed = next(doc for doc in docs if int(doc.GetType()) == 3)
        report = {"kind": "vm2-rack-finish-attachment-control", "status": "running",
                  "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                  "probe_sha256": digest(__file__), "ownership_sha256": digest(witness_path),
                  "source_sha256_before": digest(source), "control_sha256_before": digest(control),
                  "mode": "fresh_insert" if args.fresh_insert else "reattach_failed" if args.reattach_failed else "close_failed" if args.close_failed else "read_only",
                  "observations": []}

        def checkpoint():
            output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

        def observe(doc, label):
            adapter.currentModel = doc
            drawing = _early_bound(doc, "IDrawingDoc")
            view = _early_bound(_early_bound(drawing.GetFirstView(), "IView").GetNextView(), "IView")
            reference = _early_bound(view.ReferencedDocument, "IModelDoc2")
            if Path(reference.GetPathName()).resolve() != source:
                raise RuntimeError("finish drawing references another source")
            edge = visible_circle_edge(adapter, view, 5.0)
            row = read_rack_finish(app, view, edge)
            row.update(stage=label, path=str(doc.GetPathName()), title=str(doc.GetTitle()))
            report["observations"].append(row)
            checkpoint()
            return view, edge

        checkpoint()
        try:
            active = app.ActiveDoc
            report["active_before"] = str(_early_bound(active, "IModelDoc2").GetPathName()) if active is not None else None
            if candidate is not None:
                activation = app.ActivateDoc3(str(candidate), False, 1, 0)
                report["activation_return"] = repr(activation)
                active = app.ActiveDoc
                if active is None or int(app.IsSame(active, failed)) != 1:
                    raise RuntimeError("could not activate the exact diagnostic drawing")
                checkpoint()
            view, edge = observe(failed, "failed_repositioned_finish")
            if args.fresh_insert:
                drawing = _early_bound(failed, "IDrawingDoc")
                if not drawing.ActivateView(str(view.GetName2())):
                    raise RuntimeError("could not activate the copied finish view")
                annotations = [_early_bound(raw, "IAnnotation") for raw in view.GetAnnotations() or ()]
                finishes = [item for item in annotations if int(item.GetType()) == 7]
                if len(finishes) != 1:
                    raise RuntimeError("fresh-insert control needs exactly one original finish")
                manager = _early_bound(failed.SelectionManager, "ISelectionMgr")
                failed.ClearSelection2(True)
                from solidworks_mcp.adapters.com_variant import dispatch_array
                original_symbol = _early_bound(finishes[0].GetSpecificAnnotation(), "ISFSymbol")
                selection_count = failed.Extension.MultiSelect2(dispatch_array([original_symbol]), False, None)
                report["finish_selection_count"] = selection_count
                checkpoint()
                if int(selection_count) != 1:
                    raise RuntimeError("could not select the copied finish")
                selected = manager.GetSelectedObject6(1, -1)
                if int(manager.GetSelectedObjectCount2(-1)) != 1 or int(app.IsSame(selected, original_symbol)) != 1:
                    raise RuntimeError("copied finish deletion selection mismatch")
                if not failed.Extension.DeleteSelection2(0):
                    raise RuntimeError("copied finish deletion rejected")
                failed.ClearSelection2(True)
                if any(int(_early_bound(raw, "IAnnotation").GetType()) == 7 for raw in view.GetAnnotations() or ()):
                    raise RuntimeError("copied finish remained after deletion")
                data = _early_bound(manager.CreateSelectData(), "ISelectData")
                data.View = view
                data.X, data.Y, data.Z = (.2225, .175, .0015)
                if not _early_bound(edge, "IEntity").Select4(False, data):
                    raise RuntimeError("fresh finish semantic edge selection failed")
                if int(manager.GetSelectedObjectCount2(-1)) != 1 or int(app.IsSame(manager.GetSelectedObject6(1, -1), edge)) != 1:
                    raise RuntimeError("fresh finish semantic edge identity mismatch")
                raw = failed.Extension.InsertSurfaceFinishSymbol3(
                    1, 2, .278, .113, 0., 0, 10, "", "", "", "", "", "", "",
                )
                if raw is None:
                    raise RuntimeError("fresh finish insertion returned null")
                symbol = _early_bound(raw, "ISFSymbol")
                observe(failed, "fresh_insert_immediate")
                if not failed.EditRebuild3():
                    raise RuntimeError("fresh finish rebuild rejected")
                observe(failed, "fresh_insert_rebuild")
                if not symbol.SetText(8, "Ra 1.6"):
                    raise RuntimeError("fresh finish roughness rejected")
                observe(failed, "fresh_text_immediate")
                annotation = _early_bound(symbol.GetAnnotation(), "IAnnotation")
                if int(annotation.SetLeader3(2, 0, True, False, False, False)) != 0:
                    raise RuntimeError("fresh finish leader style rejected")
                observe(failed, "fresh_leader_style_immediate")
                failed.ClearSelection2(True)
                if not failed.EditRebuild3():
                    raise RuntimeError("fresh finish styled rebuild rejected")
                observe(failed, "fresh_styled_rebuild")
            if args.reattach_failed:
                from solidworks_mcp.adapters.com_variant import dispatch_array
                annotations = [_early_bound(raw, "IAnnotation") for raw in view.GetAnnotations() or ()]
                finishes = [item for item in annotations if int(item.GetType()) == 7]
                if len(finishes) != 1:
                    raise RuntimeError("expected exactly one failed finish annotation")
                report["reattach_return"] = finishes[0].SetAttachedEntities(dispatch_array([edge]))
                checkpoint()
                observe(failed, "after_semantic_reattach")
                report["rebuild_return"] = failed.EditRebuild3()
                checkpoint()
                observe(failed, "after_reattach_rebuild")
                if args.point_trials:
                    annotation = finishes[0]
                    original_point = tuple(annotation.GetLeaderPointsAtIndex(0)[-3:])
                    report["point_trials"] = []

                    def point_state(label, native_return):
                        attached = tuple(annotation.GetAttachedEntities3() or ())
                        report["point_trials"].append({
                            "trial": label, "return": native_return,
                            "types": list(annotation.GetAttachedEntityTypes() or ()),
                            "equality": [int(app.IsSame(item, edge)) for item in attached],
                            "leader": list(annotation.GetLeaderPointsAtIndex(0) or ()),
                            "dangling": bool(annotation.IsDangling()),
                        })
                        checkpoint()

                    for label, point in (("same_attached_xyz", original_point),
                                         ("right_rim_original_z", (.2225, .175, original_point[2])),
                                         ("right_rim_source_z", (.2225, .175, .003))):
                        if not annotation.SetAttachedEntities(dispatch_array([edge])):
                            raise RuntimeError("trial baseline reattachment rejected")
                        point_state(label, annotation.SetLeaderAttachmentPointAtIndex(0, *point))
                    manager = _early_bound(failed.SelectionManager, "ISelectionMgr")
                    for label, point in (("selected_sheet_point", (.2225, .175, .0015)),
                                         ("selected_model_point", (.0025, 0, .003))):
                        failed.ClearSelection2(True)
                        data = _early_bound(manager.CreateSelectData(), "ISelectData")
                        data.View = view
                        data.X, data.Y, data.Z = point
                        if not _early_bound(edge, "IEntity").Select4(False, data):
                            raise RuntimeError("explicit semantic edge selection rejected")
                        point_state(label, annotation.SetAttachedEntities(dispatch_array([edge])))
                    failed.ClearSelection2(True)
                    observe(failed, "after_point_trials")
                    report["point_trials_rebuild"] = failed.EditRebuild3()
                    checkpoint()
                    observe(failed, "after_point_trials_rebuild")
            if args.save_reopen:
                report["candidate_save_return"] = failed.SaveAs3(str(candidate), 0, 0)
                if report["candidate_save_return"] != 0:
                    raise RuntimeError("diagnostic candidate save failed")
                checkpoint()
                titles = [str(failed.GetTitle()), next(str(doc.GetTitle()) for doc in docs if int(doc.GetType()) == 1)]
                for title in titles:
                    app.CloseDoc(title)
                if app.GetDocuments():
                    raise RuntimeError("candidate cold reopen requires empty seat")
                check("cold reopen experimental finish", await adapter.open_model(str(candidate)))
                failed = _early_bound(adapter.currentModel, "IModelDoc2")
                observe(failed, "fresh_insert_cold_reopen" if args.fresh_insert else "after_point_trials_cold_reopen")
                report["candidate_sha256_after"] = digest(candidate)
            check("open saved production finish control", await adapter.open_model(str(control)))
            opened = _early_bound(adapter.currentModel, "IModelDoc2")
            if Path(opened.GetPathName()).resolve() != control:
                raise RuntimeError("control open returned another drawing")
            try:
                observe(opened, "saved_original_finish")
            finally:
                app.CloseDoc(str(opened.GetTitle()))
            remaining = [_early_bound(raw, "IModelDoc2") for raw in app.GetDocuments() or ()]
            after = [(str(doc.GetPathName()), str(doc.GetTitle()), int(doc.GetType()),
                      "dirty" if doc.GetSaveFlag() else "clean") for doc in remaining]
            if sorted(after) != sorted(actual):
                raise RuntimeError("control changed the original document inventory or dirty flags")
            if digest(source) != report["source_sha256_before"] or digest(control) != report["control_sha256_before"]:
                raise RuntimeError("readback changed saved source/control bytes")
            if args.close_failed:
                report["closed_without_save"] = []
                # Closing a drawing can also unload its source. Retain names
                # from the verified inventory, never dereference closed handles.
                for target_path, target_title, _kind, _state in sorted(after, key=lambda row: row[2] != 3):
                    present = [str(_early_bound(raw, "IModelDoc2").GetPathName()) for raw in app.GetDocuments() or ()]
                    if target_path not in present:
                        report["closed_without_save"].append({"path": target_path, "title": target_title, "state": "already_unloaded"})
                        checkpoint()
                        continue
                    app.CloseDoc(target_title)
                    report["closed_without_save"].append({"path": target_path, "title": target_title})
                    checkpoint()
                if app.GetDocuments() or app.ActiveDoc is not None:
                    raise RuntimeError("owned failed-drawing closure did not empty the seat")
                if digest(source) != report["source_sha256_before"] or digest(control) != report["control_sha256_before"]:
                    raise RuntimeError("no-save closure changed saved input bytes")
            report.update(status="closed_without_save" if args.close_failed else "fresh_insert_observed" if args.fresh_insert else "reattach_observed" if args.reattach_failed else "read_only_complete", source_sha256_after=digest(source),
                          control_sha256_after=digest(control))
        except Exception as error:
            report.update(status="failed", error=repr(error))
            raise
        finally:
            checkpoint()
        return {"receipt": str(output), "sha256": digest(output)}

    with dodo._com_seat("VM2 rack finish attachment control"):
        return run_owned_diagnostic(probe)


if __name__ == "__main__":
    raise SystemExit(main())
