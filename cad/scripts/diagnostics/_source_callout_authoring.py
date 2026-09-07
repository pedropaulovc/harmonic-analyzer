"""Deliberately author one copied alignment PART; never bless accidental saves.

The SetText below-callout field (4) is model presentation, not drawing-only
GetLowerText. Save3(1, 0, 0) is the existing copied-source BASIC control's
Silent-only in-place call; success, errors, native path and cold content are
independent gates. Original input hashes are never changed by this controller.

https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDisplayDimension~SetText.html
https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~Save3.html
"""

from contextlib import contextmanager
from copy import deepcopy
from enum import StrEnum
from pathlib import Path
import time
import sys
from unittest.mock import patch

from _common import _early_bound, check
import _drawing_common as common
from _drawing_marks import _named_dimension
from _drawing_native_callouts import DimensionSource, _dimension_witness
from diagnostics import probe_drawing_attachments as attachments
from diagnostics._source_dimension_snapshot import dimension_snapshot, tolerance


class SourceCalloutAuthoring(StrEnum):
    ALIGNMENT_FIT = "alignment_fit"


class _Phase(StrEnum):
    NEW = "new"
    AUTHORING = "authoring"
    AUTHORED = "authored"
    DRAWING = "drawing"
    CLOSED = "closed"


DIMENSION = "ArborBoreDia@ArborBoreProfile"
TEXT = "THRU - REAM\nPRESS FIT"
CALLOUT = {"ArborBoreDia": TEXT}
TARGETS = {"ArborBoreProfile": ("ArborBoreDia",)}


def require_selection(variant, storage, observation, save, order):
    if variant is None:
        return
    from diagnostics._native_drawing_save_control import DrawingSave
    from diagnostics._source_save_boundaries import SourceObservation

    if (
        variant is not SourceCalloutAuthoring.ALIGNMENT_FIT
        or storage is not None
        or observation is not SourceObservation.ALIGNMENT_SAVE
        or not isinstance(save, DrawingSave)
        or tuple(order) != ("alignment_pinion",)
    ):
        raise ValueError(
            "source callout authoring requires only alignment_pinion, alignment_save and explicit save; no lower-text control"
        )


def expected_copy_hash(trial, original_hash):
    """H1 exists only after explicit authoring and successful cold readback."""
    authoring = trial.get("source_callout_authoring")
    if authoring is None or authoring.get("status") != "passed":
        return original_hash
    baseline = authoring["baseline"]
    if (
        authoring["variant"] != SourceCalloutAuthoring.ALIGNMENT_FIT.value
        or authoring["original_sha256"] != original_hash
        or baseline["path"] != str(Path(trial["copy_source"]).resolve())
    ):
        raise RuntimeError("authored source baseline has wrong provenance")
    return baseline["sha256"]


class SourceCalloutControl:
    def __init__(self, adapter, module, trial, checkpoint):
        if trial["target"] != "alignment_pinion":
            raise ValueError("source authoring requires only alignment_pinion")
        self.adapter, self.module, self.trial, self.checkpoint = (
            adapter,
            module,
            trial,
            checkpoint,
        )
        self.path = Path(trial["copy_source"]).resolve(strict=True)
        initial_hash = attachments.file_digest(self.path)
        if initial_hash != trial["copy_hashes"]["copied"]:
            raise RuntimeError("owned PART changed before explicit authoring began")
        self.phase, self.calls = _Phase.NEW, 0
        self.report = trial["source_callout_authoring"] = {
            "variant": SourceCalloutAuthoring.ALIGNMENT_FIT.value,
            "original_sha256": initial_hash,
            "status": "running",
            "snapshots": {},
            "scope": "one authored source field; full observed parameter/text inventory before/after authoring and part reopen; recipe banks retain named manufacturing source, not full BREP immutability",
        }

    def _same(self, before, after, label):
        if (
            before is None
            or after is None
            or int(self.adapter.swApp.IsSame(before, after)) != 1
        ):
            raise RuntimeError(f"source callout {label} native identity changed")

    def _owned(self, kind):
        self.adapter.ownership.assert_current_owned()
        model = _early_bound(self.adapter.currentModel, "IModelDoc2")
        if model is None or model.GetType() != kind:
            raise RuntimeError("source callout has wrong owned document kind")
        self._same(model, self.adapter.swApp.ActiveDoc, "active document")
        if kind == 1 and Path(model.GetPathName()).resolve() != self.path:
            raise RuntimeError("source authoring has wrong copied PART path")
        return model

    def _part_snapshot(self):
        model = self._owned(1)
        rows, handles = dimension_snapshot(
            self.adapter.swApp, model, self.path, required=TARGETS
        )
        self._same(model, self._owned(1), "source snapshot")
        return rows, handles

    def _part_display(self, expected):
        display, parameter = _named_dimension(
            self.adapter, "ArborBoreProfile", "ArborBoreDia"
        )
        display = _early_bound(display, "IDisplayDimension")
        self._same(expected, parameter, "authored parameter")
        if (
            parameter.FullName != f"{DIMENSION}@{self.path.stem}.Part"
            or display.Type2 != 6
            or display.IsReferenceDim() is not False
            or display.IsHoleCallout() is not False
        ):
            raise RuntimeError(
                "source authoring requires the exact model bore diameter"
            )
        return display

    def _expected_authored(self, before):
        expected = deepcopy(before)
        name = f"{DIMENSION}@{self.path.stem}.Part"
        displays = expected["dimensions"][name]["displays"]
        if not displays:
            raise RuntimeError("source authoring has no observed target displays")
        for display in displays:
            # The literal below text and its definition are the sole expected
            # changes. No tolerance, value, precision, marking or other text.
            display["text"]["4"] = TEXT
            display["text"]["8"] = TEXT
        return expected

    async def author(self, source_model, before, handles, reader):
        if self.phase is not _Phase.NEW or set(handles) != {DIMENSION}:
            raise RuntimeError("source authoring requires a fresh exact manifest")
        self.phase = _Phase.AUTHORING  # A failed authoring call cannot be retried.
        started = time.perf_counter()
        try:
            self._same(source_model, self._owned(1), "authoring source")
            self.report["before"], original_handles = self._part_snapshot()
            self.configuration = before["configuration"]
            expected = self._expected_authored(self.report["before"])
            display = self._part_display(handles[DIMENSION])
            self._same(source_model, self._owned(1), "pre-set source")
            display.SetText(4, TEXT)  # void; not SetTextAll or drawing LowerText.
            self.report["setter_readback"] = display.GetText(4)
            if self.report["setter_readback"] != TEXT:
                raise RuntimeError("source SetText did not retain exact fit callout")
            source_model.GraphicsRedraw2()  # SetText's documented display update.
            self.report["authored"], actual_handles = self._part_snapshot()
            if (
                self.report["authored"] != expected
                or original_handles.keys() != actual_handles.keys()
            ):
                raise RuntimeError(
                    "source authoring changed fields beyond the exact fit text"
                )
            for name, handle in original_handles.items():
                self._same(handle, actual_handles[name], "source parameter")
            self._same(source_model, self._owned(1), "pre-save source")
            if attachments.file_digest(self.path) != self.report["original_sha256"]:
                raise RuntimeError("copied PART changed on disk before authorized Save3")
            self.report["save"] = source_model.Save3(1, 0, 0)
            returned = self.report["save"]
            if (
                type(returned) is not tuple
                or len(returned) != 3
                or type(returned[0]) is not bool
                or returned[0] is not True
                or type(returned[1]) is not int
                or returned[1] != 0
                or type(returned[2]) is not int
            ):
                raise RuntimeError(f"authored copied PART Save3 failed: {returned!r}")
            self._same(source_model, self._owned(1), "saved source")
            if source_model.GetSaveFlag() is not False:
                raise RuntimeError("authored copied PART remained dirty after Save3")
            saved_hash = attachments.file_digest(self.path)
            self.report["saved_sha256"] = saved_hash
            self.checkpoint()
            await self.adapter.close_owned_documents()
            check(
                "reopen authored alignment source copy",
                await self.adapter.open_model(str(self.path)),
            )
            reopened = self._owned(1)
            self.report["reopened"], _ = self._part_snapshot()
            after, fresh_handles = reader(reopened)
            if (
                self.report["reopened"] != expected
                or before != after
                or set(fresh_handles) != {DIMENSION}
            ):
                raise RuntimeError(
                    "authored copied PART cold content/parameters changed"
                )
            if (
                reopened.GetSaveFlag() is not False
                or attachments.file_digest(self.path) != saved_hash
            ):
                raise RuntimeError(
                    "authored source cold read changed dirty state or bytes"
                )
            self.handles = fresh_handles
            self.report["baseline"] = {"path": str(self.path), "sha256": saved_hash}
            self.report["status"] = "passed"
            self.phase = _Phase.AUTHORED
            return reopened, after, fresh_handles
        except BaseException as error:
            self.report.update(status="failed", error=repr(error))
            raise
        finally:
            self.report["seconds"] = time.perf_counter() - started
            primary = sys.exception()
            try:
                self.checkpoint()
            except BaseException as error:
                if primary is None:
                    raise
                primary.add_note(f"source authoring checkpoint also failed: {error!r}")

    def _read_drawing(self, annotation, view, handles):
        annotation = _early_bound(annotation, "IAnnotation")
        if (
            annotation.GetType() != 4
            or annotation.OwnerType != 0
            or annotation.Visible != 1
            or annotation.IsDangling() is not False
        ):
            raise RuntimeError(
                "source callout requires a visible, attached model dimension"
            )
        self._same(view, annotation.Owner, "drawing view owner")
        source = _early_bound(view.ReferencedDocument, "IModelDoc2")
        if (
            source is None
            or Path(source.GetPathName()).resolve() != self.path
            or view.ReferencedConfiguration != self.configuration
        ):
            raise RuntimeError(
                "imported source callout references the wrong source/configuration"
            )
        witness = _dimension_witness(self.adapter, view, annotation)
        if (
            witness.source is not DimensionSource.MODEL
            or witness.display_type != 6
            or len(witness.dimensions) != 1
            or witness.display.IsHoleCallout() is not False
        ):
            raise RuntimeError(
                "source callout import is not the exact non-hole model diameter"
            )
        self._same(
            handles[DIMENSION], witness.dimensions[0], "imported source parameter"
        )
        if witness.dimensions[0].FullName != f"{DIMENSION}@{self.path.stem}.Part":
            raise RuntimeError(
                "source callout imported dimension has wrong full identity"
            )
        entities = tuple(annotation.GetAttachedEntities3() or ())
        types = tuple(annotation.GetAttachedEntityTypes() or ())
        count = annotation.GetAttachedEntityCount3()
        if (
            type(count) is not int
            or count != len(entities)
            or count != len(types)
            or any(type(kind) is not int for kind in types)
        ):
            raise RuntimeError("source callout imported attachment inventory disagrees")
        text = {str(part): witness.display.GetText(part) for part in range(1, 9)}
        if any(type(value) is not str for value in text.values()):
            raise RuntimeError("source callout imported text is not native strings")
        return f"{view.GetName2()}/{annotation.GetName()}", {
            "parameters": witness.parameters,
            "configuration": witness.configuration,
            "attachment_types": types,
            "text": text,
            "tolerance": tolerance(witness.dimensions[0]),
        }

    def _drawing_rows(self, handles):
        if set(handles) != {DIMENSION}:
            raise RuntimeError("source callout needs exact phase-fresh source handle")
        model = self._owned(3)
        matches = []
        for sheet in _early_bound(model, "IDrawingDoc").GetViews() or ():
            for raw in sheet:
                view = _early_bound(raw, "IView")
                for raw_annotation in view.GetAnnotations() or ():
                    annotation = _early_bound(raw_annotation, "IAnnotation")
                    if annotation.GetType() != 4:
                        continue
                    display = _early_bound(
                        annotation.GetSpecificAnnotation(), "IDisplayDimension"
                    )
                    parameter = _early_bound(display.GetDimension2(0), "IDimension")
                    if parameter is None:
                        raise RuntimeError(
                            "source callout inventory has null parameter"
                        )
                    if "@".join(parameter.FullName.split("@")[:2]) == DIMENSION:
                        matches.append(self._read_drawing(annotation, view, handles))
        self._same(model, self._owned(3), "drawing snapshot")
        if len(matches) != 1:
            raise RuntimeError("source callout requires one exact imported dimension")
        return dict(matches)

    @contextmanager
    def observe(self):
        if self.phase is not _Phase.AUTHORED:
            raise RuntimeError(
                "source callout drawing context requires authored cold baseline"
            )
        self.phase = _Phase.DRAWING
        original = self.module.set_dimension_callouts
        try:
            if original is not common.set_dimension_callouts:
                raise RuntimeError("source callout recipe/common aliases changed")

            def verify(adapter, annotations, callout_text, *, location="below"):
                if (
                    adapter is not self.adapter
                    or self.calls
                    or callout_text != CALLOUT
                    or location != "below"
                ):
                    raise RuntimeError(
                        "source callout requires one exact read-only drawing request"
                    )
                self.calls += 1
                model = self._owned(3)
                selected = tuple(annotations)
                if len(selected) != 1:
                    raise RuntimeError(
                        "source callout drawing request has wrong inventory"
                    )
                annotation = _early_bound(selected[0], "IAnnotation")
                key, row = self._read_drawing(
                    annotation, _early_bound(annotation.Owner, "IView"), self.handles
                )
                self.report["imported_request"] = {key: row}
                self._same(model, self._owned(3), "import request drawing")
                if row["text"]["4"] != TEXT or row["text"]["8"] != TEXT:
                    raise RuntimeError(
                        "fresh import did not retain authored fit callout"
                    )
                self.report["import_verification"] = "passed"
                # No SetText, SetLowerText, rebuild, or alternative field.

            with (
                patch.object(self.module, "set_dimension_callouts", verify),
                patch.object(common, "set_dimension_callouts", verify),
            ):
                yield
        finally:
            self.phase = _Phase.CLOSED

    def require_used(self):
        if self.calls != 1 or self.report.get("import_verification") != "passed":
            raise RuntimeError(
                "source callout was not imported and verified exactly once"
            )

    def boundary_snapshot(self):
        if self.phase is not _Phase.DRAWING:
            raise RuntimeError(
                "source callout boundary requires active drawing lifetime"
            )
        return self._drawing_rows(self.handles)

    def snapshot(self, adapter, handles, *, phase, annotations):
        if adapter is not self.adapter:
            raise RuntimeError("source callout snapshot adapter changed")
        self.require_used()
        record = self.report["snapshots"][phase] = {}
        try:
            record["rows"] = self._drawing_rows(handles)
            ((key, row),) = record["rows"].items()
            if row["text"]["4"] != TEXT or row["text"]["8"] != TEXT:
                raise RuntimeError("saved/cold drawing lost authored fit callout")
            values = [text["value"] for text in annotations[key]["generic"]["texts"]]
            record["native_text_values"] = values
            if any(type(value) is not str for value in values):
                raise RuntimeError("source callout printed values are not strings")
            lines, wanted = (
                [line for value in values for line in value.splitlines()],
                TEXT.splitlines(),
            )
            if any(lines.count(line) != 1 for line in wanted) or lines.index(
                wanted[0]
            ) >= lines.index(wanted[1]):
                raise RuntimeError("source callout fit lines are not both printed")
            row["displayed_lines"] = wanted
            record["status"] = "passed"
            return record["rows"]
        except BaseException as error:
            record.update(status="failed", error=repr(error))
            raise
