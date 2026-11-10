"""Experimental keyed one-part drawing reconciliation. --help and plan require no COM."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict
import difflib
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import sys
import time
from typing import Any

# Deliberately no native imports until after argument parsing and seat guard.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _drawing_reconcile import plan, recipe
from _feature_reconcile import DIMENSIONS as PART_DIMENSIONS
from benchmark_feature_reconcile import Benchmark as PartBenchmark, digest, write_json

PREFIX = "experiment.drawing_reconcile"
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "out" / "reports" / "drawing-reconcile"
DIAMETER_MM = 20.0
BASELINE_DEPTH_MM = 12.0
TARGET_DEPTH_MM = 16.0

# SDK enum values (developing-solidworks v3.12.1 enums/*.md); every literal is
# re-checked against the seat's installed swconst.tlb before any document work.
DOC_PART, DOC_DRAWING = 1, 3  # swDocumentTypes_e
OPEN_SILENT = 1  # swOpenDocOptions_Silent
DONT_REBUILD_ON_ACTIVATION = 1  # swRebuildOnActivation_e.swDontRebuildActiveDoc
THIS_CONFIGURATION = 1  # swInConfigurationOpts_e.swThisConfiguration / swSetValue_InThisConfiguration
SPECIFY_CONFIGURATION = 3  # swInConfigurationOpts_e.swSpecifyConfiguration
SET_VALUE_SUCCESSFUL = 0  # swSetValueReturnStatus_e.swSetValue_Successful
ANNOTATION_DISPLAY_DIMENSION, ANNOTATION_NOTE = 4, 6  # swAnnotationType_e
OWNER_VIEW, OWNER_SHEET, OWNER_TEMPLATE = 0, 1, 2  # swAnnotationOwner_e
ANNOTATION_VISIBLE = 1  # swAnnotationVisibilityState_e.swAnnotationVisible
UNITS_LINEAR, UNITS_LINEAR_DECIMAL_PLACES, LENGTH_MM = 47, 49, 0  # swUserPreferenceIntegerValue_e, swLengthUnit_e
NATIVE_LITERALS = {
    "swDocPART": DOC_PART, "swDocDRAWING": DOC_DRAWING, "swOpenDocOptions_Silent": OPEN_SILENT,
    "swDontRebuildActiveDoc": DONT_REBUILD_ON_ACTIVATION,
    "swThisConfiguration": THIS_CONFIGURATION, "swSetValue_InThisConfiguration": THIS_CONFIGURATION,
    "swSpecifyConfiguration": SPECIFY_CONFIGURATION, "swSetValue_Successful": SET_VALUE_SUCCESSFUL,
    "swDisplayDimension": ANNOTATION_DISPLAY_DIMENSION, "swNote": ANNOTATION_NOTE,
    "swAnnotationOwner_DrawingView": OWNER_VIEW, "swAnnotationOwner_DrawingSheet": OWNER_SHEET,
    "swAnnotationOwner_DrawingTemplate": OWNER_TEMPLATE, "swAnnotationVisible": ANNOTATION_VISIBLE,
    "swUnitsLinear": UNITS_LINEAR, "swUnitsLinearDecimalPlaces": UNITS_LINEAR_DECIMAL_PLACES, "swMM": LENGTH_MM,
    # Used by the SDK drawing helpers (new_drawing, insert_model_dims) and the
    # reused part/drawing saves and PDF export.
    "swDwgPapersUserDefined": 12, "swImportModelItemsFromEntireModel": 0,
    "swInsertDimensionsMarkedForDrawing": 0x8000, "swInsertDimensionsNotMarkedForDrawing": 0x80000,
    "swInsertHoleWizardLocationDimensions": 0x20000, "swPersistReferencedObject_Ok": 0,
    "swSaveAsCurrentVersion": 0, "swSaveAsOptions_Silent": 1, "swSaveAsOptions_AvoidRebuildOnSave": 8,
}
VALUE_TOLERANCE_MM = 1e-7
OUTLINE_TOLERANCE_MM = 1e-3
MODEL_SUFFIXES = (".sldprt", ".sldasm")
STALE_PATTERNS = ("*.SLDDRW", "*.SLDPRT", "*.pdf", "*.json", "*.jsonl")
PDF_TEXT_HELPER = {
    "helper": "pypdf.PageObject.extract_text",
    "repository_helper": None,
    "note": "No repository PDF text-extraction helper exists; pypdf is the repository's existing PDF "
            "dependency (_drawing_common.sanitize_pdf_metadata uses PdfReader).",
}


def native_path(path: Any) -> str:
    """Case-normalised absolute path for exact native reference comparisons."""
    return os.path.normcase(str(Path(str(path)).resolve()))


def model_references(pairs: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Split GetDocumentDependencies2 pairs into model (part/assembly) and other references."""
    models = [pair for pair in pairs if Path(pair[1]).suffix.lower() in MODEL_SUFFIXES]
    return models, [pair for pair in pairs if pair not in models]


def pdf_evidence(path: Path, expected_pages: int = 1) -> dict[str, Any]:
    """Exported PDF identity, page count and extracted text for parent-side diffing."""
    from pypdf import PdfReader

    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    if len(pages) != expected_pages:
        raise RuntimeError(f"PDF {path.name} has {len(pages)} pages, expected {expected_pages}")
    text = "\n\f\n".join(pages)
    return {"file": path.name, "sha256": digest(path), "bytes": path.stat().st_size,
            "page_count": len(pages), "text": text,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def compare_pdfs(clean: dict[str, Any], incremental: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Evidence only: byte identity is not expected (PDFs embed creation metadata)."""
    return {
        "clean": {key: clean[key] for key in ("file", "sha256", "page_count", "text_sha256")},
        "incremental": {key: incremental[key] for key in ("file", "sha256", "page_count", "text_sha256")},
        "sha256_equal": clean["sha256"] == incremental["sha256"],
        "page_count_equal": clean["page_count"] == incremental["page_count"],
        "text_equal": clean["text"] == incremental["text"],
        "text_diff": list(difflib.unified_diff(clean["text"].splitlines(), incremental["text"].splitlines(),
                                               "clean", "incremental", lineterm="", n=1))[:400],
        "clean_text_equals_baseline": clean["text"] == baseline["text"],
        "incremental_text_equals_baseline": incremental["text"] == baseline["text"],
    }


def _outline_size(outline: list[float]) -> tuple[float, float]:
    return outline[2] - outline[0], outline[3] - outline[1]


def compare_pair(clean: dict[str, Any], incremental: dict[str, Any]) -> dict[str, Any]:
    """Clean and reconciled drawings must agree on content; placement deltas are evidence."""
    a, b = clean["part_geometry"], incremental["part_geometry"]
    if any(abs(a["dimensions_mm"][key] - b["dimensions_mm"][key]) > VALUE_TOLERANCE_MM for key in a["dimensions_mm"]):
        raise RuntimeError("Clean/incremental part dimensions differ")
    for first, second in zip(a["bounds_mm"], b["bounds_mm"], strict=True):
        if any(abs(x - y) > 1e-6 for x, y in zip(first, second, strict=True)):
            raise RuntimeError("Clean/incremental part extents differ")
    if not math.isclose(a["volume_mm3"], b["volume_mm3"], rel_tol=1e-9):
        raise RuntimeError("Clean/incremental part volume differs")
    if clean["sheet"] != incremental["sheet"]:
        raise RuntimeError(f"Clean/incremental sheet differs: {clean['sheet']} != {incremental['sheet']}")
    if set(clean["views"]) != set(incremental["views"]):
        raise RuntimeError("Clean/incremental view sets differ")
    evidence: dict[str, Any] = {"view_position_delta_mm": {}, "view_outline_size_delta_mm": {},
                                "dimension_position_delta_mm": {}}
    for key, x in clean["views"].items():
        y = incremental["views"][key]
        for field in ("name", "orientation", "referenced_configuration", "scale", "model_out_of_date",
                      "display_dimension_count"):
            if x[field] != y[field]:
                raise RuntimeError(f"Clean/incremental view {key} {field} differs: {x[field]} != {y[field]}")
        size = [p - q for p, q in zip(_outline_size(x["outline_mm"]), _outline_size(y["outline_mm"]), strict=True)]
        evidence["view_outline_size_delta_mm"][key] = size
        # The view outline is the drawn model geometry: equal size proves the
        # reconciled view regenerated to the target model, not the baseline.
        if any(abs(delta) > OUTLINE_TOLERANCE_MM for delta in size):
            raise RuntimeError(f"Clean/incremental view {key} outline size differs: {size}")
        evidence["view_position_delta_mm"][key] = [p - q for p, q in zip(x["position_mm"], y["position_mm"], strict=True)]
    if set(clean["dimensions"]) != set(incremental["dimensions"]):
        raise RuntimeError("Clean/incremental dimension sets differ")
    for key, x in clean["dimensions"].items():
        y = incremental["dimensions"][key]
        if x["view"] != y["view"] or abs(x["value_mm"] - y["value_mm"]) > VALUE_TOLERANCE_MM:
            raise RuntimeError(f"Clean/incremental dimension {key} differs: {x} != {y}")
        evidence["dimension_position_delta_mm"][key] = [p - q for p, q in zip(x["position_mm"], y["position_mm"], strict=True)]
    if clean["note"]["text"] != incremental["note"]["text"]:
        raise RuntimeError("Clean/incremental note text differs")
    evidence["note_position_delta_mm"] = [p - q for p, q in zip(clean["note"]["position_mm"],
                                                                incremental["note"]["position_mm"], strict=True)]
    if clean["auto_annotations"] != incremental["auto_annotations"]:
        raise RuntimeError("Clean/incremental automatic annotation inventories differ")
    return evidence


def verify_native_literals() -> dict[str, int]:
    """Fail before any document work if a literal disagrees with the seat typelib."""
    from solidworks_mcp.adapters import sw_type_info
    observed = {name: sw_type_info.constant(name) for name in NATIVE_LITERALS}
    if observed != NATIVE_LITERALS:
        raise RuntimeError(f"Seat swconst disagrees with benchmark literals: {observed}")
    return observed


def pin_drawing_template(adapter: Any, layout: str) -> dict[str, Any]:
    """Resolve the repository template exactly as new_project_drawing; read-only seat probe."""
    from _drawing_types import DRAWING_TEMPLATES, DrawingLayout
    from solidworks_mcp.adapters import sw_type_info

    template = DRAWING_TEMPLATES[DrawingLayout(layout)]
    path = template.path
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(f"project drawing standard is missing: {path}")
    preference = sw_type_info.constant("swDefaultTemplateDrawing")  # raises if absent
    return {"layout": layout, "resolver": "_drawing_types.DRAWING_TEMPLATES (as _drawing_common.new_project_drawing)",
            "path": str(path.resolve()), "sha256": digest(path), "bytes": path.stat().st_size,
            "width_m": template.width_m, "height_m": template.height_m,
            # Observational only: creation always passes the pinned path.
            "seat_default_preference": "swDefaultTemplateDrawing", "seat_default_preference_id": preference,
            "seat_default_preference_value": adapter.swApp.GetUserPreferenceStringValue(preference),
            "repository_input": True}


class Harness:
    def __init__(self, adapter: Any, out: Path, template: dict[str, Any]):
        self.adapter = adapter
        self.out = out
        self.template = template
        self.phases: list[dict[str, Any]] = []
        # Part creation, dimension lookup, save and geometry/identity validation
        # reuse the qualified keyed-feature diagnostic unchanged (its events keep
        # their experiment.feature_reconcile names inside these spans).
        self.part = PartBenchmark(adapter, out)

    @contextmanager
    def phase(self, name: str, case: str, **attributes: Any):
        import _telemetry
        start = time.perf_counter()
        with _telemetry.span(f"{PREFIX}.{name}", case=case, **attributes) as span:
            ctx = span.get_span_context()
            row = {"phase": name, "case": case, "trace_id": f"{ctx.trace_id:032x}",
                   "span_id": f"{ctx.span_id:016x}", "status": "error"}
            try:
                yield
                row["status"] = "ok"
            finally:
                row["seconds"] = time.perf_counter() - start
                self.phases.append(row)

    def event(self, event_name: str, **attributes: Any) -> None:
        import _telemetry
        # Attribute keys are namespaced: _telemetry.event's first parameter is `name`.
        _telemetry.event(f"{PREFIX}.{event_name}", **{f"observed_{key}": value for key, value in attributes.items()})

    def model(self):
        from _com import _early_bound
        return _early_bound(self.adapter.currentModel, "IModelDoc2")

    def drawing(self):
        from _com import _early_bound
        return _early_bound(self.adapter.currentModel, "IDrawingDoc")

    def extension(self):
        from _com import _early_bound
        return _early_bound(self.model().Extension, "IModelDocExtension")

    def same(self, first: Any, second: Any) -> bool:
        # SDK compare-selected-objects example: 1=same, 0=different, -1=unknown.
        return int(self.adapter.swApp.IsSame(first, second)) == 1

    def require_not_open(self, *paths: Path) -> None:
        for path in paths:
            if self.adapter.swApp.GetOpenDocumentByName(str(path)) is not None:
                raise RuntimeError(f"Document must not be loaded: {path}")

    def require_active(self, path: Path | None) -> None:
        """EditRebuild3 works only in the context of the active document.

        ``path`` is None only for a new, not yet saved drawing (no path to compare).
        """
        from _com import _early_bound
        active = self.adapter.swApp.ActiveDoc
        if active is None or not self.same(active, self.adapter.currentModel):
            raise RuntimeError("The target document is not the active document")
        if path is not None and native_path(_early_bound(active, "IModelDoc2").GetPathName()) != native_path(path):
            raise RuntimeError(f"{path.name} is not the active document")

    @contextmanager
    def on(self, document: Any):
        """Temporarily address a loaded, non-active document through the adapter."""
        previous = self.adapter.currentModel
        self.adapter.currentModel = document
        try:
            yield
        finally:
            self.adapter.currentModel = previous

    async def open(self, path: Path) -> None:
        # Explicit drawing document type; every native output (including
        # swFileLoadWarning_ModelOutOfDate) is fatal.
        answer = self.adapter.swApp.OpenDoc6(str(path), DOC_DRAWING, OPEN_SILENT, "", 0, 0)
        if not isinstance(answer, (tuple, list)) or len(answer) != 3:
            raise RuntimeError(f"Unexpected OpenDoc6 readback: {answer!r}")
        document, errors, warnings = answer
        if document is None or errors or warnings:
            raise RuntimeError(f"OpenDoc6 failed/warned: errors={errors}, warnings={warnings}, path={path}")
        self.adapter.currentModel = document
        if native_path(self.model().GetPathName()) != native_path(path):
            raise RuntimeError(f"Opened wrong document: {self.model().GetPathName()} != {path}")

    def activate(self, path: Path) -> None:
        """Foreground an open document without rebuilding it (render-path pattern)."""
        from _com import _early_bound
        answer = self.adapter.swApp.ActivateDoc3(path.name, False, DONT_REBUILD_ON_ACTIVATION, 0)
        if not isinstance(answer, (tuple, list)) or len(answer) != 2:
            raise RuntimeError(f"Unexpected ActivateDoc3 readback: {answer!r}")
        document, errors = answer
        if document is None or int(errors) != 0:
            raise RuntimeError(f"ActivateDoc3 failed/warned: {path}, errors={errors}")
        document = _early_bound(document, "IModelDoc2")
        if native_path(document.GetPathName()) != native_path(path):
            raise RuntimeError(f"Activated the wrong document: {document.GetPathName()} != {path}")
        self.adapter.currentModel = document
        self.require_active(path)

    def loaded(self, path: Path):
        from _com import _early_bound
        document = self.adapter.swApp.GetOpenDocumentByName(str(path))
        return None if document is None else _early_bound(document, "IModelDoc2")

    def close(self, drawing: Path, part: Path) -> None:
        """Close the drawing, then prove its referenced part is unloaded."""
        document = self.loaded(drawing)
        if document is not None:
            self.adapter.swApp.CloseDoc(str(document.GetTitle()))
        self.adapter.currentModel = None
        child = self.loaded(part)
        if child is not None:
            # Expected after clean creation or incremental open (the part was
            # opened explicitly); after a drawing-only reopen it is evidence.
            self.adapter.swApp.CloseDoc(str(child.GetTitle()))
            self.event("part_closed_explicitly", part=part.name)
        self.require_not_open(drawing, part)

    def dependencies(self, path: Path) -> list[tuple[str, str]]:
        # Closed-document read; Searchflag=False reports where references were saved.
        answer = self.adapter.swApp.GetDocumentDependencies2(str(path), False, False, False)
        if not isinstance(answer, (tuple, list)) or not answer or len(answer) % 2:
            raise RuntimeError(f"Unexpected GetDocumentDependencies2 readback for {path}: {answer!r}")
        return [(str(answer[index]), str(answer[index + 1])) for index in range(0, len(answer), 2)]

    def retarget(self, drawing: Path, old_part: Path, new_part: Path) -> dict[str, Any]:
        """Repoint a closed byte-copied drawing to its byte-copied part."""
        self.require_not_open(drawing, old_part, new_part)
        before = self.dependencies(drawing)
        models, others = model_references(before)
        if len(models) != 1 or native_path(models[0][1]) != native_path(old_part):
            raise RuntimeError(f"Copied drawing does not reference exactly {old_part}: {before}")
        if not self.adapter.swApp.ReplaceReferencedDocument(str(drawing), models[0][1], str(new_part)):
            raise RuntimeError(f"ReplaceReferencedDocument failed: {drawing}")
        after = self.dependencies(drawing)
        models_after, others_after = model_references(after)
        if (len(models_after) != 1 or native_path(models_after[0][1]) != native_path(new_part)
                or others_after != others):
            raise RuntimeError(f"Retargeted drawing does not reference exactly {new_part}: {after}")
        return {"before": before, "after": after}

    async def create_part(self, spec: dict[str, Any], path: Path) -> None:
        """Fresh qualified cylinder at the target values, rebuilt and saved for the views."""
        await self.part.create(spec)
        if not self.model().EditRebuild3():
            raise RuntimeError("Part EditRebuild3 failed")
        self.part.save(path)

    def part_references(self, part: Path) -> dict[str, str]:
        document = self.loaded(part)
        if document is None:
            raise RuntimeError(f"Part is not loaded: {part}")
        with self.on(document):
            return self.part.refs()

    def create_views(self, spec: dict[str, Any], part: Path) -> dict[str, Any]:
        """New drawing on the pinned template, sheet setup, keyed model views."""
        from _com import _early_bound
        from solidworks_mcp.adapters.solidworks.drawing import new_drawing, place_view, set_units_mm
        if not Path(self.template["path"]).is_file():
            raise FileNotFoundError(self.template["path"])
        new_drawing(self.adapter, template=self.template["path"],
                    width=self.template["width_m"], height=self.template["height_m"])
        if int(self.model().GetType()) != DOC_DRAWING:
            raise RuntimeError("Pinned template did not create a drawing")
        drawing = self.drawing()
        # A hand-saved template can open in Edit Sheet Format mode (new_project_drawing).
        drawing.EditSheet()
        sheet = self.adapter._get_attr_or_call(drawing, "GetCurrentSheet")
        if sheet is None:
            raise RuntimeError("Drawing template has no current sheet")
        if spec["sheet"]["units"] != "mm":
            raise RuntimeError(f"Unsupported sheet units: {spec['sheet']['units']}")
        # Document-level unit preferences only; seat (system) options are never written.
        set_units_mm(self.adapter, decimals=spec["sheet"]["decimals"])
        scale = spec["sheet"]["scale"]
        if not _early_bound(sheet, "ISheet").SetScale(float(scale[0]), float(scale[1]), True, False):
            raise RuntimeError("Could not set the drawing sheet scale")
        views = {}
        for item in spec["views"]:
            x, y = (value / 1000 for value in item["position_mm"])
            view = _early_bound(place_view(self.adapter, str(part), item["orientation"], x, y,
                                           scale=tuple(item["scale"])), "IView")
            if not view.SetName2(item["name"]) or str(view.GetName2()) != item["name"]:
                raise RuntimeError(f"Could not key drawing view {item['key']} as {item['name']}")
            views[item["key"]] = view
        # CreateDrawViewFromModelView3 may auto-scale the sheet for its first
        # view; re-pin the sheet scale as finalize_drawing does.
        sheet = _early_bound(self.adapter._get_attr_or_call(drawing, "GetCurrentSheet"), "ISheet")
        if not sheet.SetScale(float(scale[0]), float(scale[1]), False, False):
            raise RuntimeError("Could not re-pin the drawing sheet scale")
        return views

    def annotate(self, spec: dict[str, Any], views: dict[str, Any]) -> dict[str, Any]:
        """Import the keyed model dimensions per view, then one free sheet note."""
        from _com import _early_bound
        from solidworks_mcp.adapters.solidworks.drawing import add_note, insert_model_dims
        inserted = {}
        for key in dict.fromkeys(item["view"] for item in spec["annotations"] if item["kind"] == "model_dimension"):
            # API-created dimensions are not reliably marked for drawing; import all.
            # Template auto-insertion plus DuplicateDims=True may legitimately
            # leave nothing new to insert; validation is the gate.
            inserted[key] = len(insert_model_dims(self.adapter, views[key], marked_only=False))
        drawing = self.drawing()
        # Sheet context, not the last annotated view (_supplier_wire_stock_drawing pattern).
        drawing.ActivateView("")
        if not drawing.GetEditSheet() or drawing.ActiveDrawingView is not None:
            raise RuntimeError("Could not restore sheet context for the note")
        notes = 0
        for item in spec["annotations"]:
            if item["kind"] != "note":
                continue
            x, y = (value / 1000 for value in item["position_mm"])
            note = add_note(self.adapter, item["text"], x, y)
            if note is None or str(_early_bound(note, "INote").GetText()) != item["text"]:
                raise RuntimeError(f"Could not insert note {item['key']}")
            notes += 1
        self.model().ClearSelection2(True)
        return {"inserted_annotations": inserted, "notes": notes}

    def annotation_row(self, raw: Any) -> tuple[Any, dict[str, Any]]:
        from _com import _early_bound
        annotation = _early_bound(raw, "IAnnotation")
        position = annotation.GetPosition()
        return annotation, {"type": int(annotation.GetType()), "owner_type": int(annotation.OwnerType),
                            "visible": int(annotation.Visible),
                            "position_mm": [float(value) * 1000 for value in (position or ())][:2]}

    def validate(self, spec: dict[str, Any], part: Path, part_refs: dict[str, str] | None,
                 expected_auto: dict[str, int] | None) -> dict[str, Any]:
        """Identical native gates for baseline, clean, incremental and no-op."""
        from _com import _early_bound
        from solidworks_mcp.adapters.solidworks.drawing import iter_views
        model = self.model()
        if int(model.GetType()) != DOC_DRAWING:
            raise RuntimeError("Validation target is not a drawing")
        drawing = self.drawing()
        sheet_names = [str(name) for name in (self.adapter._get_attr_or_call(drawing, "GetSheetNames") or ())]
        properties = list(_early_bound(self.adapter._get_attr_or_call(drawing, "GetCurrentSheet"),
                                       "ISheet").GetProperties2() or ())
        ext = self.extension()
        sheet = {"names": sheet_names, "scale": [float(value) for value in properties[2:4]],
                 "units_linear": int(ext.GetUserPreferenceInteger(UNITS_LINEAR, 0)),
                 "decimals": int(ext.GetUserPreferenceInteger(UNITS_LINEAR_DECIMAL_PLACES, 0))}
        if (len(sheet_names) != 1 or sheet["scale"] != spec["sheet"]["scale"]
                or sheet["units_linear"] != LENGTH_MM or sheet["decimals"] != spec["sheet"]["decimals"]):
            raise RuntimeError(f"Sheet contract mismatch: {sheet}")
        natives = {str(_early_bound(view, "IView").GetName2()): _early_bound(view, "IView")
                   for view in iter_views(self.adapter)}
        by_name = {item["name"]: item for item in spec["views"]}
        if sorted(natives) != sorted(by_name):
            raise RuntimeError(f"Unexpected drawing view set: {sorted(natives)}")
        views, documents = {}, {}
        for name, view in natives.items():
            item = by_name[name]
            raw_document = view.ReferencedDocument
            documents[item["key"]] = None if raw_document is None else _early_bound(raw_document, "IModelDoc2")
            observed = {
                "name": name, "orientation": str(view.GetOrientationName()),
                "referenced_path": str(documents[item["key"]].GetPathName()) if documents[item["key"]] else None,
                "referenced_configuration": str(view.ReferencedConfiguration),
                "scale": [float(value) for value in (view.ScaleRatio or ())],
                "position_mm": [float(value) * 1000 for value in (view.Position or ())],
                "outline_mm": [float(value) * 1000 for value in (view.GetOutline() or ())],
                "model_out_of_date": bool(view.IsModelOutOfDate()),
                "display_dimension_count": int(view.GetDisplayDimensionCount()),
            }
            self.event("view", key=item["key"], **{k: str(v) for k, v in observed.items()})
            if (observed["orientation"] != item["orientation"] or observed["referenced_path"] is None
                    or native_path(observed["referenced_path"]) != native_path(part)
                    or observed["referenced_configuration"] != item["configuration"]
                    or observed["scale"] != item["scale"] or len(observed["position_mm"]) != 2
                    or len(observed["outline_mm"]) != 4 or observed["model_out_of_date"]):
                raise RuntimeError(f"View {item['key']} contract mismatch: {observed}")
            views[item["key"]] = observed
        if not self.same(documents["front"], documents["side"]):
            raise RuntimeError("Views do not share the single part model")
        expected_dimensions = {PART_DIMENSIONS[item["dimension"]]: item for item in spec["annotations"]
                               if item["kind"] == "model_dimension"}
        dimensions, notes, auto = {}, [], Counter()
        owners = [(item["key"], natives[item["name"]], OWNER_VIEW) for item in spec["views"]]
        # GetFirstView is the sheet itself; only its sheet-owned annotations count there.
        owners.append(("sheet", _early_bound(drawing.GetFirstView(), "IView"), OWNER_SHEET))
        for owner_key, owner, owner_type in owners:
            for raw in owner.GetAnnotations() or ():
                annotation, row = self.annotation_row(raw)
                if row["owner_type"] == OWNER_TEMPLATE:
                    auto[f"template:{row['type']}"] += 1
                    continue
                if row["owner_type"] != owner_type:
                    continue  # reported by its own owner
                if row["type"] == ANNOTATION_NOTE:
                    note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
                    notes.append({**row, "owner": owner_key, "text": str(note.GetText()),
                                  "dangling": bool(annotation.IsDangling())})
                    continue
                if row["type"] != ANNOTATION_DISPLAY_DIMENSION:
                    auto[f"{owner_key}:{row['type']}"] += 1
                    continue
                display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
                native = _early_bound(display.GetDimension2(0), "IDimension")
                full_name = str(native.FullName)
                keyed = "@".join(full_name.split("@")[:2])
                item = expected_dimensions.get(keyed)
                configuration = views[owner_key]["referenced_configuration"] if owner_key in views else ""
                values = native.GetSystemValue3(SPECIFY_CONFIGURATION, configuration)
                if not isinstance(values, (tuple, list)) or len(values) != 1:
                    raise RuntimeError(f"Unexpected display dimension readback {full_name}: {values!r}")
                observed = {**row, "view": owner_key, "full_name": full_name, "value_mm": float(values[0]) * 1000,
                            "dangling": bool(annotation.IsDangling()),
                            "attached_entities": int(annotation.GetAttachedEntityCount3())}
                self.event("dimension", **{k: str(v) for k, v in observed.items()})
                key = item["key"] if item else full_name
                if item is None or key in dimensions:
                    raise RuntimeError(f"Unexpected or duplicate display dimension: {observed}")
                expected_mm = spec["part"]["parameters_mm"][item["dimension"]]
                # attached_entities is evidence only: a healthy imported model dimension read 0 natively
                # (attempt 1, Depth@ReconcileBody, dangling False), so IsDangling is the attachment proof.
                if (observed["view"] != item["view"] or observed["owner_type"] != OWNER_VIEW
                        or observed["visible"] != ANNOTATION_VISIBLE or observed["dangling"]
                        or len(observed["position_mm"]) != 2
                        or not math.isfinite(observed["value_mm"])
                        or abs(observed["value_mm"] - expected_mm) > VALUE_TOLERANCE_MM):
                    raise RuntimeError(f"Display dimension {item['key']} contract mismatch: {observed}")
                dimensions[key] = observed
        if sorted(dimensions) != sorted(item["key"] for item in expected_dimensions.values()):
            raise RuntimeError(f"Missing display dimensions: {sorted(dimensions)}")
        if sum(view["display_dimension_count"] for view in views.values()) != len(dimensions):
            raise RuntimeError("View display-dimension counts disagree with the annotation walk")
        declared_notes = [item for item in spec["annotations"] if item["kind"] == "note"]
        if (len(notes) != len(declared_notes) or len(notes) != 1 or notes[0]["text"] != declared_notes[0]["text"]
                or notes[0]["owner"] != declared_notes[0]["owner"] or notes[0]["visible"] != ANNOTATION_VISIBLE
                or notes[0]["dangling"] or len(notes[0]["position_mm"]) != 2):
            raise RuntimeError(f"Note contract mismatch: {notes}")
        auto = dict(sorted(auto.items()))
        self.event("annotation_inventory", dimensions=len(dimensions), notes=len(notes), auto=json.dumps(auto))
        # Template-driven automatic annotations (e.g. centre marks) are not in the
        # recipe; every run must reproduce the baseline's observed inventory.
        if expected_auto is not None and auto != expected_auto:
            raise RuntimeError(f"Automatic annotation inventory {auto} != baseline {expected_auto}")
        with self.on(documents["front"]):
            refs = part_refs if part_refs is not None else self.part.refs()
            geometry = self.part.validate(spec["part"], refs)
        return {"sheet": sheet, "views": views, "dimensions": dimensions, "note": notes[0],
                "auto_annotations": auto,
                "annotation_count": {"display_dimension": len(dimensions), "note": len(notes),
                                     "automatic": sum(auto.values())},
                "part_geometry": geometry, "part_feature_references": refs,
                "drawing_dirty": bool(model.GetSaveFlag())}

    def export_pdf(self, drawing: Path, path: Path) -> dict[str, Any]:
        """SDK save_drawing PDF call shape; the drawing keeps its own path."""
        path.unlink(missing_ok=True)
        result = self.extension().SaveAs3(str(path), 0, 1, None, None, 0, 0)
        if not isinstance(result, tuple) or len(result) != 3:
            raise RuntimeError(f"SaveAs3 returned invalid native status for {path}: {result!r}")
        ok, errors, warnings = result
        if not ok or errors or not path.is_file() or not path.stat().st_size:
            raise RuntimeError(f"PDF export failed: ok={ok}, errors={errors}, warnings={warnings}, path={path}")
        if native_path(self.model().GetPathName()) != native_path(drawing):
            raise RuntimeError("PDF export renamed the drawing document")
        return {"file": path.name, "save_warnings": int(warnings)}

    async def operation(self, case: str, mode: str, spec: dict[str, Any],
                        manifest: dict[str, Any] | None = None) -> dict[str, Any]:
        drawing = self.out / f"{case}.SLDDRW"
        part = self.out / f"{case}-part.SLDPRT"
        pdf = self.out / f"{case}.pdf"
        expected_auto = manifest["auto_annotations"] if manifest else None
        started = time.perf_counter()
        decision = retarget = creation = pdf_export = None
        prepared_drawing_hash = prepared_part_hash = None
        if mode != "clean":
            source_drawing = self.out / manifest["drawing_file"]
            source_part = self.out / manifest["part_file"]
        with self.phase("copy", case, skipped=mode == "clean"):
            if mode != "clean":
                if (digest(source_drawing) != manifest["drawing_sha256"]
                        or digest(source_part) != manifest["part_sha256"]):
                    raise RuntimeError("Source drawing/part bytes no longer match persisted manifest")
                # Part first: the copied drawing must never be older than its model.
                shutil.copyfile(source_part, part)
                shutil.copyfile(source_drawing, drawing)
                prepared_part_hash = digest(part)
        with self.phase("retarget", case, skipped=mode == "clean"):
            if mode != "clean":
                retarget = self.retarget(drawing, source_part, part)
                prepared_drawing_hash = digest(drawing)
        with self.phase("open", case, skipped=mode == "clean"):
            if mode != "clean":
                # The part is opened explicitly so it can be activated, edited,
                # rebuilt and saved in place; the drawing then binds to it.
                await self.part.open(part)
                await self.open(drawing)
                self.require_not_open(source_part, source_drawing)
        with self.phase("diff", case, skipped=mode == "clean"):
            decision = plan(manifest["recipe"], spec) if mode != "clean" else None
            if decision and decision.decision == "full_build":
                raise RuntimeError("Structural plan must be handled before native mutation")
        with self.phase("prevalidation", case, skipped=mode != "incremental"):
            if mode == "incremental":
                # Validate *all* copied-baseline contracts before the first mutation.
                self.validate(manifest["recipe"], part, manifest["part_feature_references"], expected_auto)
        with self.phase("part_edit", case, skipped=mode == "noop", mode=mode,
                        operation={"clean": "create_rebuild_save", "incremental": "dimension_edit"}.get(mode, "none")):
            if mode == "clean":
                await self.create_part(spec["part"], part)
            elif mode == "incremental":
                self.activate(part)
                for key, value in decision.edits:
                    status = self.part.dimension(key).SetSystemValue3(value / 1000, THIS_CONFIGURATION, None)
                    if int(status) != SET_VALUE_SUCCESSFUL:
                        raise RuntimeError(f"SetSystemValue3 failed: {status}")
            elif not decision or decision.decision != "noop":
                raise RuntimeError(f"Expected no-op plan, got {decision}")
        views = None
        with self.phase("view_create", case, skipped=mode != "clean"):
            if mode == "clean":
                views = self.create_views(spec, part)
        with self.phase("annotate", case, skipped=mode != "clean"):
            if mode == "clean":
                creation = self.annotate(spec, views)
                views = None  # No live view handles across rebuild/close/reopen.
        with self.phase("rebuild", case, skipped=mode == "noop"):
            if mode == "incremental":
                self.require_active(part)
                if not self.model().EditRebuild3():
                    raise RuntimeError("Part EditRebuild3 failed")
                self.activate(drawing)
            if mode != "noop":
                if mode == "clean":
                    self.require_active(None)  # new drawing; saved in the save phase
                if not self.model().EditRebuild3():
                    raise RuntimeError("Drawing EditRebuild3 failed")
        with self.phase("validation_before_save", case):
            refs = None if mode == "clean" else manifest["part_feature_references"]
            before = self.validate(spec, part, refs, expected_auto)
            refs = before["part_feature_references"]
        with self.phase("save", case, skipped=mode == "noop"):
            if mode == "incremental":
                # Part bytes first (it stays loaded), then the drawing that shows it.
                self.activate(part)
                self.part.save(part)
                self.activate(drawing)
            if mode != "noop":
                # SaveAs without SaveReferenced; clean saved its part in part_edit.
                self.part.save(drawing)
            saved_drawing_hash = digest(drawing)
            saved_part_hash = digest(part)
        with self.phase("pdf_export", case, skipped=mode == "noop"):
            if mode != "noop":
                pdf_export = self.export_pdf(drawing, pdf)
        with self.phase("close", case):
            self.close(drawing, part)
        with self.phase("reopen", case):
            await self.open(drawing)
        with self.phase("validation_after_reopen", case):
            after = self.validate(spec, part, refs, expected_auto)
        with self.phase("close_after_reopen", case):
            self.close(drawing, part)
        with self.phase("readback_integrity", case):
            if digest(drawing) != saved_drawing_hash or digest(part) != saved_part_hash:
                raise RuntimeError("Readback changed saved drawing/part bytes")
            if mode == "noop" and (saved_drawing_hash != prepared_drawing_hash
                                   or saved_part_hash != prepared_part_hash):
                raise RuntimeError("No-op mutated drawing/part bytes")
        seconds = time.perf_counter() - started
        # Evidence parsing (pypdf) is outside the timed row.
        evidence = pdf_evidence(pdf) if pdf_export else None
        return {"case": case, "mode": mode, "seconds": seconds,
                "decision": asdict(decision) if decision else {"decision": "clean"},
                "creation": creation, "retarget": retarget,
                "before_save": before, "after_reopen": after,
                "path": drawing.name, "part_path": part.name,
                "drawing_sha256": saved_drawing_hash, "prepared_drawing_sha256": prepared_drawing_hash,
                "part_sha256": saved_part_hash, "prepared_part_sha256": prepared_part_hash,
                "pdf_export": pdf_export, "pdf": evidence, "part_feature_references": refs}


async def benchmark(adapter: Any, out: Path, trials: int) -> dict[str, str]:
    import _telemetry
    from opentelemetry import trace
    from opentelemetry.sdk.trace import SpanProcessor

    out.mkdir(parents=True, exist_ok=True)
    for pattern in STALE_PATTERNS:  # canonical declared directory only (main enforces)
        for stale in out.glob(pattern):
            stale.unlink()
    raw = out / "spans.jsonl"
    raw.write_text("", encoding="utf-8")

    class RetainedSpans(SpanProcessor):
        def __init__(self):
            self.count = 0
            self.error = None
            self.completed = []

        def on_end(self, span):
            if not span.name.startswith(PREFIX):
                return
            self.completed.append(span)
            self.count += 1
            # Serialize only when the root ends (also on exceptions): evidence IO
            # must not inflate operation timings.
            if span.name == PREFIX:
                try:
                    with raw.open("w", encoding="utf-8") as stream:
                        for completed in self.completed:
                            stream.write(completed.to_json(indent=None) + "\n")
                except Exception as exc:
                    self.error = exc
                    raise

    retained = RetainedSpans()
    provider = trace.get_tracer_provider()
    if not hasattr(provider, "add_span_processor"):
        raise RuntimeError("A real OTel SDK provider is required")
    provider.add_span_processor(retained)
    base_spec = recipe(DIAMETER_MM, BASELINE_DEPTH_MM)
    target = recipe(DIAMETER_MM, TARGET_DEPTH_MM)
    write_json(out / "target-recipe.json", target)
    with _telemetry.span(PREFIX, trials=trials) as root:
        root_context = root.get_span_context()
        if not root_context.is_valid or not root.is_recording():
            raise RuntimeError("Benchmark requires recording OTel spans")
        native_literals = verify_native_literals()
        template = pin_drawing_template(adapter, base_spec["template"]["layout"])
        harness = Harness(adapter, out, template)
        cwd = str(adapter.swApp.GetCurrentWorkingDirectory())
        initial = await harness.operation("baseline", "clean", base_spec)
        manifest = {"schema": 1, "recipe": base_spec, "drawing_file": initial["path"],
                    "drawing_sha256": initial["drawing_sha256"], "part_file": initial["part_path"],
                    "part_sha256": initial["part_sha256"], "pdf_file": initial["pdf"]["file"],
                    "pdf_sha256": initial["pdf"]["sha256"],
                    "part_feature_references": initial["part_feature_references"],
                    "auto_annotations": initial["after_reopen"]["auto_annotations"],
                    "drawing_template": template, "seat_working_directory": cwd}
        manifest_path = out / "baseline-manifest.json"
        write_json(manifest_path, manifest)
        # Exercise persisted -- not in-memory -- recipe and reference readback.
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        protected = {name: digest(out / name) for name in
                     (manifest["drawing_file"], manifest["part_file"], manifest["pdf_file"])}
        added_view = recipe(DIAMETER_MM, TARGET_DEPTH_MM)
        added_view["views"].append({**added_view["views"][1], "key": "top", "name": "ReconcileTop",
                                    "orientation": "*Top", "position_mm": [110.0, 90.0]})
        removed_note = recipe(DIAMETER_MM, TARGET_DEPTH_MM)
        removed_note["annotations"] = [item for item in removed_note["annotations"] if item["kind"] != "note"]
        structural = {}
        with harness.phase("diff", "structural_refusal"):
            for name, changed in (("added_view", added_view), ("removed_note", removed_note)):
                structural[name] = plan(manifest["recipe"], changed)
                if structural[name].decision != "full_build" or structural[name].edits:
                    raise RuntimeError(f"Structural {name} was not refused before mutation")
        if any(digest(out / name) != value for name, value in protected.items()):
            raise RuntimeError("Structural refusal changed the baseline")
        results = []
        orders = []
        comparisons = []
        clean_manifest = {"auto_annotations": manifest["auto_annotations"]}
        for trial in range(trials):
            order = ("clean", "incremental") if trial % 2 == 0 else ("incremental", "clean")
            orders.append([*order, "noop"])
            pair = {}
            for mode in order:
                pair[mode] = await harness.operation(f"trial-{trial + 1}-{mode}", mode, target,
                                                     clean_manifest if mode == "clean" else manifest)
                results.append(pair[mode])
            placement = compare_pair(pair["clean"]["after_reopen"], pair["incremental"]["after_reopen"])
            comparisons.append({"trial": trial + 1, "placement_evidence": placement,
                                **compare_pdfs(pair["clean"]["pdf"], pair["incremental"]["pdf"], initial["pdf"])})
            edited = pair["incremental"]
            noop_manifest = {"recipe": target, "drawing_file": edited["path"],
                             "drawing_sha256": edited["drawing_sha256"], "part_file": edited["part_path"],
                             "part_sha256": edited["part_sha256"],
                             "part_feature_references": edited["part_feature_references"],
                             "auto_annotations": manifest["auto_annotations"]}
            results.append(await harness.operation(f"trial-{trial + 1}-noop", "noop", target, noop_manifest))
            if any(digest(out / name) != value for name, value in protected.items()):
                raise RuntimeError("Trials mutated the baseline drawing, part or PDF")
        template_after = pin_drawing_template(adapter, base_spec["template"]["layout"])
        _telemetry.event(f"{PREFIX}.template_provenance",
                         before=json.dumps(template, sort_keys=True),
                         after=json.dumps(template_after, sort_keys=True))
        # Seat default-template drift is retained as evidence, never model input.
        if (template_after["path"] != template["path"] or template_after["sha256"] != template["sha256"]
                or template_after["bytes"] != template["bytes"]):
            raise RuntimeError(f"Drawing template input changed: before={template!r}, after={template_after!r}")
    if retained.error or retained.count < len(harness.phases) + 1:
        raise RuntimeError(f"Incomplete retained OTel evidence: {retained.count}, {retained.error}")
    modes = {row["case"]: row["mode"] for row in results}
    phase_medians = {
        mode: {name: statistics.median(row["seconds"] for row in harness.phases
                                       if row["phase"] == name and modes.get(row["case"]) == mode)
               for name in dict.fromkeys(row["phase"] for row in harness.phases if modes.get(row["case"]) == mode)}
        for mode in ("clean", "incremental", "noop")}
    report = {
        "schema": 1,
        "experimental_limits": "Only one generated cylinder drawn on the project landscape template with keyed *Front/*Right views, its two keyed model dimensions imported as native display dimensions and one sheet note; only the part's keyed dimension values are reconciled.",
        "trace_id": f"{root_context.trace_id:032x}", "trials": trials, "orders": orders,
        "drawing_template": template, "drawing_template_after": template_after,
        "seat_working_directory": cwd, "native_literals": native_literals,
        "initial_baseline": initial,
        "structural_decisions": {name: asdict(decision) for name, decision in structural.items()},
        "results": results,
        "trial_seconds": [{"case": row["case"], "mode": row["mode"], "seconds": row["seconds"]} for row in results],
        "phases": harness.phases, "phase_median_seconds": phase_medians,
        "raw_spans": raw.name, "retained_span_count": retained.count,
        "median_seconds": {mode: statistics.median(row["seconds"] for row in results if row["mode"] == mode)
                           for mode in ("clean", "incremental", "noop")},
        "pdf_comparison": {"text_helper": PDF_TEXT_HELPER, "baseline": {
            key: initial["pdf"][key] for key in ("file", "sha256", "page_count", "text_sha256")},
            "trials": comparisons},
        "timing_note": "Warm-seat native operation wall times. Clean rows create, rebuild and save a fresh part at the target values (part_edit), create the drawing from the pinned repository template with two keyed model views (view_create), import the keyed model dimensions and add the note (annotate), rebuild, validate, save and export the PDF. Incremental rows include part+drawing copy, closed-document ReplaceReferencedDocument retargeting with dependency readback, explicit part and drawing open, copied-baseline prevalidation, the in-place part dimension edit, part and drawing rebuilds, and saves of both. No-op rows copy, retarget, open and validate without edit, rebuild, save or export, and must preserve the retargeted bytes. All rows include close/reopen and post-reopen validation. Baseline creation, PDF text extraction and span serialization are excluded, as are process/connect/farm/cache overhead. The drawing template is a repository input pinned by path and hash.",
    }
    write_json(out / "report.json", report)
    return {"report": str(out / "report.json"), "spans": str(raw)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("benchmark", help="Run on an admitted, locked farm seat only")
    run.add_argument("--out", type=Path, default=DEFAULT_OUT)
    run.add_argument("--trials", type=int, default=3)
    diff = sub.add_parser("plan", help="Diff a persisted baseline manifest against a recipe JSON without COM")
    diff.add_argument("manifest", type=Path)
    diff.add_argument("recipe", type=Path)
    args = parser.parse_args()
    if args.command == "plan":
        before = json.loads(args.manifest.read_text(encoding="utf-8"))
        after = json.loads(args.recipe.read_text(encoding="utf-8"))
        if not isinstance(before, dict) or "recipe" not in before:
            parser.error("manifest must be a JSON object with a recipe")
        print(json.dumps(asdict(plan(before["recipe"], after)), indent=2))
        return 0
    if args.trials < 3:
        parser.error("--trials must be at least 3")
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("Use the canonical verify:drawing_reconcile task; no standalone COM launch")
    if args.out.resolve() != DEFAULT_OUT.resolve():
        parser.error("--out must be the canonical declared diagnostic output directory")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from _session import run_build
    return run_build(lambda adapter: benchmark(adapter, args.out.resolve(), args.trials))


if __name__ == "__main__":
    raise SystemExit(main())
