"""Disposable saved-native SM H-H observation, not a native SHIP gate.

Temporary destination: cad/scripts/diagnostics/probe_mg_saved_thread_control.py.
Run ONLY through the temporary drawing:mg_magnifying_bracket farm record.
The cache archives install ALL their members in this source tree's cad/out;
outputs passed to restore are neither relocation destinations nor filters.
No recipes, saves, settings, rebuilds, startup, or session-wide document closes.
The imported diagnostic performs its existing single display-generation boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / "cad/out/reports/diagnostics/mg-saved-thread-control.json"
CONTRACT_PATH = Path(__file__).with_suffix(".json")
CONTROL = {
    "schema": 1,
    "sheet_number": 1,
    "sheet_name": "Lever Geometry",
    "section_label": "H",
    "feature_name": "BracketMountingTaps",
    "drawing": {
        "path": "cad/out/slddrw/sm-summing-lever.SLDDRW",
        "key": "0549c19080401aaeb43a3d9dc5c40e31c53d5743610994318174817cf9cb8363",
        "bytes": 480655,
        "sha256": "775c6edc4befe1c17f4f9dfca1a9d43d5943fc85e15c0ba5c0e411a5bcf6bcf1",
    },
    "part": {
        "path": "cad/out/sldprt/sm-summing-lever.SLDPRT",
        "key": "238dc7587b2a41b5ed7081a08f35f479039418c60291fd9497a265d1ec16457c",
        "bytes": 280124,
        "sha256": "ff952b3739770d218251ab4c8cb333cc3d10e7c34097dbad5762fb1bd771bfdf",
    },
    "historical_provenance": {
        "status": "VERIFIED_EXTERNAL_EVIDENCE",
        "packet": "pr1769-sm-thread-control-20261021",
        "source_report": "C:/farm-runs/com-perf-20261019/20261021T135951435Z-16ea74332725458cadf5ff30f4c0e661.out/reports/cache.jsonl",
        "evidence_files": {
            "historical-recipe-execution-proof.json": {
                "bytes": 16291,
                "sha256": "159e8b334be89c93acd356390b3a528b873a378cd47bed5f724c5221e47db1e8",
            },
            "cache-archives/inventory.json": {
                "bytes": 2823,
                "sha256": "7b6bfe45ae9902ec60311ec5150db2b06c82268811df78eea863e0be43043ce5",
            },
            "manifest.json": {
                "bytes": 4486,
                "sha256": "7cc81384ef133e1c07978e402de01df780f8f33abe8e66798fbb882e719c63c1",
            },
        },
        "epoch": "4",
        "salt": "sw2024-sp3",
        "salt_is_not_runtime_version_proof": True,
        "part_manifest_id": "14e77479a2c39bfcb2d5f215a44b89f73c94b5e10e53726f33831570f9092dd3",
        "drawing_manifest_id": "1482b721b32fc1036a5cad7c65ecfbea0ee6fb222b1cba0c5ba03ef7c703e2cb",
        "part_input_count": 53,
        "drawing_input_count": 56,
        "part_recipe_digest": "26177d5c641f86d7d18f250811d52806",
        "execution_token_canonical_md5": "c7a4f8894771527745ede767473c9f32",
        "linkage": "Historical 53-input recipe replay and preserved execution-token canonical MD5 match the drawing manifest; token value equals the pinned part SHA-256.",
        "historical_source_digests": {
            "cad/scripts/build_sm_summing_lever.py": "bd4ee26fe25279c93a4cfe747cb72307",
            "cad/scripts/draw_sm_summing_lever.py": "25b0af4513486fe1c82c09d6048c77bd",
            "cad/scripts/sm_summing_lever_notes.py": "e1fa8767ec5f9062ca716346830dee5d",
            "cad/scripts/sm_summing_lever_spec.py": "62e838d80e9a0a34bd1ff20d86e28e96",
        },
        "archives": {
            "drawing": {
                "sha256": "1d25552b200ec6c4f5b63b19021f25cbb8dbb322b8633332b86ceec2484c2352",
                "bytes": 1509610,
                "epoch": "4",
                "members": [
                    "cad/out/slddrw/sm-summing-lever.SLDDRW",
                    "cad/out/pdf/sm-summing-lever.pdf",
                    "cad/out/png/sm-summing-lever_drawing.png",
                    "cad/out/reports/layout-audit/sm-summing-lever.json",
                ],
                "contains_part": False,
                "contains_execution_token": False,
            },
            "part": {
                "sha256": "5002b730b4b41c547cdb39c9f3f6c15262c22fab9797543d1e07bdab91c895e1",
                "bytes": 563978,
                "epoch": "4",
                "members": [
                    "cad/out/sldprt/sm-summing-lever.SLDPRT",
                    "cad/out/stl/sm-summing-lever.STL",
                    "cad/out/png/sm-summing-lever",
                    "cad/out/png/sm-summing-lever/sm-summing-lever_isometric.png",
                ],
                "contains_execution_token": False,
            },
        },
        "scope": "Externally verified historical evidence, not worker-fetched proof files or live native reference resolution. The later archive inventory supersedes the proof JSON's pending archive-inventory note.",
    },
}
MISSING = object()


def file_identity(path):
    with path.open("rb") as stream:
        size = os.fstat(stream.fileno()).st_size
        sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"bytes": size, "sha256": sha256}


def canonical(path):
    return os.path.normcase(str(Path(path).resolve())) if path else ""


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    primary_exception = None
    primary_traceback = None
    report = {
        "kind": "mg-saved-sm-thread-control",
        "status": "running",
        "native_ship": "NOT_EVALUATED",
        "mode": "read_only_no_save_with_display_generation",
        "contract": CONTROL,
        "prior_evidence": {
            "packet": "pr1769-sm-thread-control-20261021",
            "saved_native_audit": "Hole Thread23: IAnnotation 6 lines + 1 polyline; three other empty cosmetic annotations",
            "saved_png": "paired flanks x=.1192 to .139 at y=.0596312 and .0683688; 4:1",
            "boundary": "Prior saved evidence is not this fresh probe, nor proof of ICThread-primary display counts.",
        },
        "part_input_provenance": {
            "historical_recipe_execution_linkage": "VERIFIED_EXTERNAL_EVIDENCE",
            "evidence": "contract.historical_provenance",
            "digest_semantics": "Historical recipe digest is not raw part MD5; do not recompute today's recipe as the historical part.",
            "runtime_proof_scope": "Verify pinned restored bytes and token digest derivation without writing a token; BASE ReferencedDocument exact path and IsSame remain required live witnesses.",
        },
        "reads": {},
        "errors": [],
        "primary_failure": None,
        "inventories": {},
        "restores": [],
        "opens": [],
        "closures": [],
        "views": [],
        "identity_comparisons": [],
        "diagnostic": None,
        "isolation_gate": "not_entered",
        "limitations": [
            "Python finally/report/cleanup is not guaranteed after watchdog os._exit, native crash, process kill, or machine loss.",
            "Native reads are not atomic against external UI/add-ins; exclusive worker-seat ownership is required.",
        ],
        "collection_completed": False,
    }

    def failure(label, error, original_tb=MISSING):
        nonlocal primary_exception, primary_traceback
        if primary_exception is None:
            # Retain the actual exception and original traceback before any
            # formatting, cleanup, or aggregate failure can obscure them.
            primary_exception = error
            primary_traceback = error.__traceback__ if original_tb is MISSING else original_tb
        # Error rendering must not interrupt an optional reader or cleanup.
        # Never fall back to repr(error), which can fail for the same reason.
        try:
            message = str(error)
        except BaseException:
            message = "<exception text unavailable>"
        row = {"operation": label, "type": type(error).__name__, "message": message}
        tb = error.__traceback__ if original_tb is MISSING else original_tb
        row["traceback_available"] = tb is not None
        row["traceback_frames"] = []
        while tb is not None:
            row["traceback_frames"].append({
                "file": tb.tb_frame.f_code.co_filename,
                "function": tb.tb_frame.f_code.co_name,
                "line": tb.tb_lineno,
            })
            tb = tb.tb_next
        report["errors"].append(row)
        if report["primary_failure"] is None:
            report["primary_failure"] = row
        return row

    def attempt(label, reader):
        try:
            return reader()
        except Exception as error:
            failure(label, error)
            return MISSING

    def observe(label, reader):
        value = attempt(label, reader)
        if value is not MISSING:
            report["reads"][label] = value
        return value

    def checkpoint():
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        # No default=str: unexpected native objects must not be rendered as COM repr.
        REPORT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    def pinned_identity(kind, phase):
        value = file_identity(ROOT / CONTROL[kind]["path"])
        report["reads"][f"{phase}.{kind}"] = value
        require(value == {key: CONTROL[kind][key] for key in ("bytes", "sha256")},
                f"{phase}: {kind} is not the pinned saved native")
        if kind == "part":
            # Match the preserved generation token's canonical text in memory;
            # never mint/write a production .execution token for this probe.
            token_md5 = hashlib.md5((value["sha256"] + "\n").encode("utf-8"), usedforsecurity=False).hexdigest()
            report["reads"][f"{phase}.part.execution_token_canonical_md5"] = token_md5
            require(token_md5 == CONTROL["historical_provenance"]["execution_token_canonical_md5"],
                    f"{phase}: part SHA does not derive the historical generation-token digest")
        return value

    try:
        checkpoint()
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--disposable-source-tree", action="store_true")
        args = parser.parse_args()
        require(args.disposable_source_tree, "explicit disposable source-tree acknowledgement required")
        require(os.environ.get("HARMONIC_COM_SEAT"), "the admitted task must hold the coordinated COM seat")
        require(os.environ.get("HARMONIC_SW_AUTOSTART") == "0", "attach-only worker seat required")
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        require(contract == CONTROL, "committed control contract differs from the immutable probe contract")
        report["reads"]["probe_identity"] = file_identity(Path(__file__))
        report["reads"]["contract_identity"] = file_identity(CONTRACT_PATH)
        sys.path[:0] = [str(ROOT), str(ROOT / "cad/scripts")]
        from diagnostics import _script_paths  # noqa: F401
        from diagnostics._owned_native_session import run_owned_diagnostic
        from _com import _early_bound
        import _artifact_cache as cache
        from draw_mg_magnifying_bracket import _mouth_thread_diagnostic

        async def probe(adapter):
            app = adapter.swApp
            owned = []
            targets = {kind: ROOT / CONTROL[kind]["path"] for kind in ("part", "drawing")}

            def inventory(label):
                rows = []
                report["inventories"][label] = {"enumerated": False, "documents": []}
                snapshot = report["inventories"][label]
                count = attempt(f"{label}.GetDocumentCount", lambda: app.GetDocumentCount())
                raw_docs = attempt(f"{label}.GetDocuments", lambda: app.GetDocuments())
                if type(count) is int and count >= 0:
                    snapshot["native_count"] = count
                else:
                    if count is not MISSING:
                        failure(f"{label}.GetDocumentCount", RuntimeError("native document count is not a nonnegative integer"))
                    return None
                if raw_docs is MISSING:
                    return None
                if raw_docs is None:
                    snapshot["null_document_array"] = True
                    failure(f"{label}.GetDocuments", RuntimeError("null document array is unavailable, not complete empty-session proof"))
                    return None
                if not isinstance(raw_docs, (tuple, list)) or len(raw_docs) != count:
                    failure(f"{label}.GetDocuments", RuntimeError("document array unavailable or cardinality differs from native count"))
                    return None
                snapshot["enumerated"] = True
                for index, raw in enumerate(raw_docs):
                    tag = f"{label}[{index}]"
                    data = {"handle_token": tag}
                    report["inventories"][label]["documents"].append(data)
                    doc = attempt(f"{tag}.bind", lambda: _early_bound(raw, "IModelDoc2"))
                    rows.append({"native": doc, "data": data})
                    if doc is MISSING or doc is None:
                        if doc is None:
                            failure(f"{tag}.bind", RuntimeError("null document in inventory"))
                        continue
                    # Each metadata reader is independent, including during cleanup.
                    for key, reader, expected_type in (
                        ("path", lambda: doc.GetPathName(), str),
                        ("title", lambda: doc.GetTitle(), str),
                        ("type", lambda: doc.GetType(), int),
                        ("dirty", lambda: doc.GetSaveFlag(), bool),
                    ):
                        value = attempt(f"{tag}.{key}", reader)
                        if value is not MISSING:
                            if type(value) is expected_type:
                                data[key] = value
                            else:
                                failure(f"{tag}.{key}", RuntimeError("native metadata result has an unavailable or unexpected type"))
                return rows

            def complete(rows):
                return rows is not None and all(
                    all(key in row["data"] for key in ("path", "title", "type", "dirty"))
                    for row in rows
                )

            def same(left, right, label):
                evidence = {"operation": label, "status": "unavailable"}
                report["identity_comparisons"].append(evidence)
                result = app.IsSame(left, right)
                # Official IsSame example: 0=different, 1=same, -1=unable
                # to determine. Unknown/unsupported is never ownership proof.
                if type(result) is int:
                    evidence["raw"] = result
                    evidence["status"] = {0: "different", 1: "same", -1: "unsupported"}.get(result, "unknown_code")
                else:
                    evidence["status"] = "unexpected_type"
                require(type(result) is int and result in (0, 1),
                        f"{label}: IsSame did not establish same/different identity")
                return result == 1

            def user_control(label):
                value = attempt(f"{label}.UserControl", lambda: app.UserControl)
                if type(value) is bool:
                    report["reads"][f"{label}.UserControl"] = value
                    return value
                report["reads"][f"{label}.UserControl_state"] = "UNAVAILABLE"
                if value is not MISSING:
                    failure(f"{label}.UserControl", RuntimeError("UserControl did not return an actual Boolean"))
                return MISSING

            def require_owned_inventory(rows, label, *, clean=False):
                require(complete(rows), f"{label}: complete live inventory required")
                require(len(rows) <= len(owned) <= 2, f"{label}: unknown or excess live documents")
                matched = set()
                for row in rows:
                    data = row["data"]
                    candidates = [
                        index for index, owner in enumerate(owned)
                        if canonical(data["path"]) == canonical(owner["data"]["path"])
                        and data["type"] == owner["data"]["type"]
                    ]
                    require(len(candidates) == 1, f"{label}: live document has no unique exact-path/type owner")
                    index = candidates[0]
                    require(index not in matched, f"{label}: duplicate live owner")
                    require(same(row["native"], owned[index]["native"], f"{label}.live_vs_owned[{index}]"),
                            f"{label}: live document differs from retained direct OpenDoc6 result")
                    require(data["title"] == owned[index]["data"]["title"],
                            f"{label}: owned document title changed")
                    if clean:
                        require(data["dirty"] is False, f"{label}: dirty owned document is stranded; refusing CloseDoc")
                    matched.add(index)
                return rows

            def open_native(kind, doc_type):
                path = targets[kind]
                row = {"kind": kind, "requested_path": str(path), "options": 3}
                report["opens"].append(row)
                # swOpenDocOptions_Silent=1 | swOpenDocOptions_ReadOnly=2.
                result = app.OpenDoc6(str(path), doc_type, 1 | 2, "", 0, 0)
                require(isinstance(result, tuple) and len(result) == 3,
                        "early-bound OpenDoc6 did not return document/errors/warnings")
                raw, errors, warnings = result
                row["returned_document"] = raw is not None
                require(raw is not None, f"OpenDoc6 returned no {kind}")
                doc = _early_bound(raw, "IModelDoc2")
                for key, reader, expected_type in (
                    ("path", lambda: doc.GetPathName(), str),
                    ("title", lambda: doc.GetTitle(), str),
                    ("type", lambda: doc.GetType(), int),
                    ("read_only", lambda: doc.IsOpenedReadOnly(), bool),
                ):
                    value = attempt(f"open.{kind}.{key}", reader)
                    if value is not MISSING:
                        if type(value) is expected_type:
                            row[key] = value
                        else:
                            failure(f"open.{kind}.{key}", RuntimeError("native open readback has an unavailable or unexpected type"))
                # Retain ONLY the direct result with certified path/type/title.
                # Never adopt auto-loaded references or arbitrary inventory deltas.
                if (type(row.get("path")) is str and canonical(row["path"]) == canonical(path)
                        and row.get("type") == doc_type and type(row.get("title")) is str and row["title"]):
                    owned.append({"native": doc, "data": {key: row[key] for key in ("path", "title", "type")}})
                    row["retained_owned"] = True
                    report["owned_documents"] = [dict(owner["data"]) for owner in owned]
                require(row.get("retained_owned") is True, f"OpenDoc6 did not certify the exact {kind} owner")
                require(type(errors) is int and type(warnings) is int, "OpenDoc6 status codes unavailable")
                row.update(errors=errors, warnings=warnings)
                require(errors == 0, f"OpenDoc6 reported {kind} load errors")
                require(row.get("read_only") is True, f"OpenDoc6 {kind} is not proven read-only")
                require_owned_inventory(inventory(f"after_open_{kind}"), f"after_open_{kind}")
                require(not report["errors"], "open readback/ownership collection failed")
                return doc

            def activate(doc, name, label):
                result = app.ActivateDoc3(name, False, 1, 0)  # swDontRebuildActiveDoc
                require(isinstance(result, tuple) and len(result) == 2,
                        "early-bound ActivateDoc3 did not return document/errors")
                raw, errors = result
                report["reads"][f"{label}.return"] = {"document_present": raw is not None, "errors": int(errors)}
                # The helper/return pointer alone is never an activation witness.
                active = app.ActiveDoc
                witnessed = active is not None and same(active, doc, f"{label}.ActiveDoc")
                report["reads"][f"{label}.ActiveDoc_IsSame"] = witnessed
                require(int(errors) == 0 and witnessed, f"{label}: exact active document not witnessed")

            # FIRST native boundary of the callback: read-only refusal gate.
            # This is deliberately OUTSIDE the mutation/cleanup try/finally.
            # Refusal must never activate/close a foreign or background session.
            report["isolation_gate"] = "refused"
            initial = inventory("initial")
            initial_active = attempt("initial.ActiveDoc", lambda: app.ActiveDoc)
            initial_current = attempt("initial.currentModel", lambda: adapter.currentModel)
            initial_control = user_control("initial")
            for label, handle in (("currentModel", initial_current), ("ActiveDoc", initial_active)):
                report["reads"][f"initial.{label}_state"] = (
                    "UNAVAILABLE" if handle is MISSING else "NULL" if handle is None else "PRESENT"
                )
            require(complete(initial) and initial == [] and not report["errors"],
                    "control requires a proven empty initial count AND complete native document array")
            require(initial_active is None and initial_current is None,
                    "control requires measured-null initial ActiveDoc and currentModel")
            require(initial_control is True, "control requires actual UserControl=True; no setter/repair permitted")
            report["isolation_gate"] = "accepted"
            try:
                # Historical cache restores are fatal on miss/RestoreLocked. There
                # is no recipe fallback, retry, or worker/session cleanup here.
                for kind in ("drawing", "part"):
                    spec = CONTROL[kind]
                    row = {"kind": kind, "key": spec["key"], "hit": None}
                    report["restores"].append(row)
                    row["hit"] = cache.restore(spec["key"], [targets[kind]], f"diagnostic:sm-thread-control-{kind}")
                    require(row["hit"] is True, f"historical {kind} cache restore missed; regeneration forbidden")
                # Both hashes are checked only after both archives have installed.
                for kind in ("drawing", "part"):
                    attempt(f"staged.{kind}.identity", lambda kind=kind: pinned_identity(kind, "staged"))
                require(not report["errors"], "staged native identity verification failed")
                part = open_native("part", 1)
                drawing_model = open_native("drawing", 3)
                require(not report["errors"], "open ownership collection failed")
                activate(drawing_model, str(targets["drawing"]), "activate_control")
                adapter.currentModel = drawing_model
                drawing = _early_bound(drawing_model, "IDrawingDoc")
                names = tuple(str(name) for name in drawing.GetSheetNames() or ())
                report["reads"]["sheet_names"] = names
                require(names and names[0] == CONTROL["sheet_name"], "intended sheet 1 is not Lever Geometry")
                rows = drawing.GetViews()
                require(rows is not None, "saved drawing returned no per-sheet views")
                candidates = []
                found_sheets = []
                for row_index, raw_row in enumerate(rows):
                    entries = list(raw_row or ())
                    require(entries, "empty native sheet view row")
                    sheet_view = _early_bound(entries[0], "IView")
                    name = str(sheet_view.Name)
                    sheet = _early_bound(drawing.Sheet(name), "ISheet")
                    require(sheet is not None, "sheet view does not resolve to ISheet")
                    sheet_name = str(sheet.GetName())
                    found_sheets.append(sheet_name)
                    report["views"].append({"row": row_index, "sheet": sheet_name,
                                            "sheet_view_name": name, "role": "sheet"})
                    for view_index, raw in enumerate(entries[1:], 1):
                        view = _early_bound(raw, "IView")
                        item = {"row": row_index, "index": view_index, "sheet": sheet_name}
                        report["views"].append(item)
                        view_name = attempt(f"view[{row_index},{view_index}].name", lambda: str(view.Name))
                        if view_name is not MISSING:
                            item["name"] = view_name
                        section = attempt(f"view[{row_index},{view_index}].section",
                                          lambda: _early_bound(view.GetSection(), "IDrSection"))
                        if section is MISSING:
                            continue
                        item["section_present"] = section is not None
                        if section is not None:
                            label = attempt(f"view[{row_index},{view_index}].label", lambda: str(section.GetLabel()))
                            if label is not MISSING:
                                item["section_label"] = label
                                if sheet_name == CONTROL["sheet_name"] and label == CONTROL["section_label"]:
                                    candidates.append(view)
                report["reads"]["H_candidates_on_intended_sheet"] = len(candidates)
                require(sorted(found_sheets) == sorted(names), "per-sheet view inventory differs from native sheet names")
                require(not report["errors"] and len(candidates) == 1, "exactly one native H section on intended sheet required")
                section = candidates[0]
                base = _early_bound(section.GetBaseView(), "IView")
                require(base is not None, "H section has no native base view")
                source = _early_bound(base.ReferencedDocument, "IModelDoc2")
                require(source is not None, "base view has no resolved ReferencedDocument")
                reference_path = observe("base.reference_path", lambda: str(source.GetPathName()))
                reference_same = observe("base.reference_IsSame_opened_part", lambda: same(source, part, "base.reference_vs_opened_part"))
                require(reference_path is not MISSING and canonical(reference_path) == canonical(targets["part"])
                        and reference_same is True, "base reference is not the exact staged/opened part")
                # GetViews order is not sheet order. Activate the pinned native
                # sheet by name, then independently witness its current identity.
                activated = drawing.ActivateSheet(CONTROL["sheet_name"])
                report["reads"]["activate_sheet.return"] = bool(activated)
                current_sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
                require(activated is True and current_sheet is not None
                        and str(current_sheet.GetName()) == CONTROL["sheet_name"], "intended sheet activation failed")
                report["diagnostic"] = _mouth_thread_diagnostic(
                    adapter, section, feature_name="BracketMountingTaps"
                )
                report["collection_completed"] = True
            except Exception as error:
                failure("collect", error)
            finally:
                # CloseDoc also closes non-active hidden documents. Therefore
                # EVERY live document must be an exact retained owned control,
                # and every live dirty flag must be measured False before ANY close.
                for index, owned_row in enumerate(sorted(owned, key=lambda row: row["data"]["type"] != 3)):
                    data = owned_row["data"]
                    closure = {"path": data["path"], "title": data["title"], "status": "stranded_owned"}
                    report["closures"].append(closure)

                    def close_owned():
                        now = require_owned_inventory(inventory(f"before_close_{index}"),
                                                      f"before_close_{index}", clean=True)
                        matches = [row for row in now if canonical(row["data"]["path"]) == canonical(data["path"])]
                        if not matches:
                            closure["status"] = "already_unloaded"
                            return
                        require(len(matches) == 1, "ambiguous owned path before CloseDoc")
                        title = matches[0]["data"]["title"]
                        require(title and sum(row["data"]["title"] == title for row in now) == 1,
                                "ambiguous/empty CloseDoc title")
                        # Last native read before CloseDoc. Never set this flag:
                        # closing the last doc with False may terminate the seat.
                        require(user_control(f"before_close_{index}") is True,
                                "UserControl not proven True; owned documents stranded")
                        app.CloseDoc(title)  # VT_VOID; may also unload the owned part.
                        closure["status"] = "close_requested_without_save"

                    attempt(f"close[{index}]", close_owned)
                # Initial state was proven empty/null. Only restore this Python
                # reference; never activate anything or force native emptiness.
                adapter.currentModel = initial_current
                final = inventory("final")
                final_active = attempt("final.ActiveDoc", lambda: app.ActiveDoc)
                report["reads"]["final.ActiveDoc_state"] = (
                    "UNAVAILABLE" if final_active is MISSING else "NULL" if final_active is None else "PRESENT"
                )
                observe("final.inventory_empty", lambda: (
                    require(complete(final) and final == [], "native documents remain or final inventory unavailable") or True
                ))
                observe("final.active_identity_restored", lambda: (
                    require(final_active is None, "initial null ActiveDoc was not restored") or True
                ))
                observe("final.currentModel_identity_restored", lambda: (
                    require(adapter.currentModel is None, "initial null currentModel was not restored") or True
                ))
                for kind in ("drawing", "part"):
                    attempt(f"final.{kind}.identity", lambda kind=kind: pinned_identity(kind, "final"))
                attempt("callback.checkpoint", checkpoint)
            return {"report": str(REPORT), "collection_completed": report["collection_completed"]}

        runner_failures = []
        report["runner_exit_code"] = run_owned_diagnostic(probe, failures=runner_failures)
        for phase, error, original_tb in runner_failures:
            failure(f"runner.{phase}", error, original_tb)
    except (Exception, SystemExit) as error:
        failure("driver", error)
    finally:
        # Also cover attach/import/contract failures that never entered the callback.
        for kind in ("drawing", "part"):
            if f"final.{kind}" not in report["reads"]:
                attempt(f"final.{kind}.identity", lambda kind=kind: pinned_identity(kind, "final"))
        report["status"] = "failed" if report["errors"] else (
            "observed_with_diagnostic_read_errors" if (report["diagnostic"] or {}).get("errors") else "observed"
        )
        try:
            checkpoint()
        except Exception as error:
            # A filesystem failure cannot be represented in an unwritable file.
            row = failure("report_write", error)
            try:
                print(f"control report write failed: {row['type']}: {row['message']}", file=sys.stderr)
            except BaseException:
                # Preserve the already-recorded primary failure if stderr fails too.
                pass
        if primary_exception is not None:
            # The pool publishes fresh regular files under this recognized
            # failure root even for nonzero leaves; it does not fetch our normal
            # diagnostic target on failure. Export only AFTER all native cleanup.
            report["status"] = "failed"
            try:
                frames = []
                tb = primary_traceback
                while tb is not None:
                    frames.append({
                        "file": tb.tb_frame.f_code.co_filename,
                        "function": tb.tb_frame.f_code.co_name,
                        "line": tb.tb_lineno,
                    })
                    tb = tb.tb_next
                report["primary_traceback"] = {
                    "available": primary_traceback is not None,
                    "frames": frames,
                    "locals_captured": False,
                }
                failure_path = (
                    ROOT / "cad/out/reports/failures/mg-saved-thread-control"
                    / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") / "capture.json"
                )
                report["failure_artifact"] = {
                    "workspace_path": failure_path.relative_to(ROOT).as_posix(),
                    "transport": "pool failures/ prefix beside this execution's task.log",
                    "publication": "pending_worker_upload",
                }
                failure_path.parent.mkdir(parents=True, exist_ok=False)
                failure_path.write_text(
                    json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
                )
            except Exception as error:
                row = failure("failure_artifact_write", error)
                try:
                    print(f"control failure artifact write failed: {row['type']}: {row['message']}", file=sys.stderr)
                except BaseException:
                    pass
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
