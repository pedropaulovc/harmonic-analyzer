"""One alignment-bore SetLowerText experiment; no production storage policy.

Install observe() BEFORE SourceSaveBoundaries.observe(): both recipe and common
callout aliases must refer to this delta when that observer checks identity.
The only mutation is SetLowerText followed by the existing one EditRebuild3.
LOWER_TEXT_BEFORE_SAVE queues the same exact request without either mutation;
it applies once inside the native artifact boundary after sheet finalization.
The before-save source bank is intentionally observed before the queued write.
The source observer retains raw GetText/value/tolerance banks unchanged; it must
not query the drawing-only lower-text field on source-part displays.

Native premise, not a persistence claim: EditDimensionProperties documents
DimensionLowerText separately from CalloutText2, for drawing displays only.
The official chamfer example demonstrates the void setter and string getter,
not imported diameter, multiline text, source cleanliness or cold persistence.
Those are this owned pilot's still-required native/export/cold acceptance gates.

https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDisplayDimension~SetLowerText.html
https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~EditDimensionProperties.html
https://help.solidworks.com/2026/english/api/sldworksapi/Get_Chamfer_Display_Dimension_Example_CSharp.htm
"""

from contextlib import contextmanager, nullcontext
from enum import StrEnum
from pathlib import Path
import time
from unittest.mock import patch

from _common import _early_bound
import _drawing_common as common
from _drawing_native_callouts import (
    DimensionSource,
    _dimension_witness,
    _same_dimension,
)
from diagnostics._callout_recipe_contract import HISTORICAL_REPLAY


class CalloutStorage(StrEnum):
    LOWER_TEXT = "lower_text"
    LOWER_TEXT_BEFORE_SAVE = "lower_text_before_save"


class _Lifetime(StrEnum):
    READY = "ready"
    ACTIVE = "active"
    CLOSED = "closed"


DIMENSION = "ArborBoreDia@ArborBoreProfile"
TEXT = "THRU - REAM\nPRESS FIT"
CALLOUT = {"ArborBoreDia": TEXT}


class LowerTextControl:
    def __init__(
        self, adapter, module, trial, source_handles, *, storage=CalloutStorage.LOWER_TEXT
    ):
        if trial["target"] != "alignment_pinion":
            raise ValueError("lower-text control requires only alignment_pinion")
        self._require_manifest(source_handles)
        if not isinstance(storage, CalloutStorage):
            raise ValueError("lower-text control requires an explicit storage enum")
        self.storage = storage
        self.adapter, self.module = adapter, module
        self.handles = dict(source_handles)
        self.path = Path(trial["copy_source"]).resolve()
        self.configuration = trial["source_before"]["configuration"]
        self.lifetime, self.calls = _Lifetime.READY, 0
        self.writes, self.pending = 0, None
        self.report = trial["lower_text_control"] = {
            "variant": storage.value,
            "scope": "one imported alignment diameter; no source lower-text reads",
            "operation": {},
            "snapshots": {},
        }

    @staticmethod
    def _require_manifest(handles):
        if set(handles) != {DIMENSION} or handles[DIMENSION] is None:
            raise RuntimeError("lower-text control requires exact source manifest")

    def _same(self, expected, actual, label):
        if (
            expected is None
            or actual is None
            or int(self.adapter.swApp.IsSame(expected, actual)) != 1
        ):
            raise RuntimeError(f"lower-text {label} native identity changed")

    def _drawing(self, adapter):
        if adapter is not self.adapter:
            raise RuntimeError("lower-text control adapter changed")
        adapter.ownership.assert_current_owned()
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        if model is None or model.GetType() != 3:  # swDocDRAWING
            raise RuntimeError("lower-text requires an owned DRAWING, never a part")
        self._same(model, adapter.swApp.ActiveDoc, "active drawing")
        return model

    def _read(self, annotation, handles, *, view=None):
        annotation = _early_bound(annotation, "IAnnotation")
        if (
            annotation.GetType() != 4
            or annotation.OwnerType != 0
            or annotation.Visible != 1
            or annotation.IsDangling() is not False
        ):
            raise RuntimeError("lower-text requires a visible view-owned dimension")
        owner = _early_bound(annotation.Owner, "IView")
        if owner is None:
            raise RuntimeError("lower-text dimension has no native view owner")
        if view is not None:
            self._same(view, owner, "view owner")
        source = _early_bound(owner.ReferencedDocument, "IModelDoc2")
        if (
            source is None
            or Path(source.GetPathName()).resolve() != self.path
            or owner.ReferencedConfiguration != self.configuration
        ):
            raise RuntimeError("lower-text view source/configuration changed")
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        if (
            display is None
            or display.Type2 != 6
            or display.IsReferenceDim() is not False
            or display.IsHoleCallout() is not False
        ):
            raise RuntimeError("lower-text requires the imported non-hole diameter")
        witness = _dimension_witness(self.adapter, owner, annotation)
        if (
            witness.source is not DimensionSource.MODEL
            or witness.display_type != 6  # swDiameterDimension
            or witness.display.IsHoleCallout() is not False
            or len(witness.dimensions) != 1
        ):
            raise RuntimeError("lower-text requires the imported non-hole diameter")
        dimension = witness.dimensions[0]
        self._same(handles[DIMENSION], dimension, "source IDimension")
        expected_name = f"{DIMENSION}@{self.path.stem}.Part"
        if dimension.FullName != expected_name:
            raise RuntimeError("lower-text dimension has wrong full source identity")
        entities = tuple(annotation.GetAttachedEntities3() or ())
        types = tuple(annotation.GetAttachedEntityTypes() or ())
        count = annotation.GetAttachedEntityCount3()
        if (
            type(count) is not int
            or count < 0
            or count != len(entities)
            or count != len(types)
            or any(type(kind) is not int for kind in types)
        ):
            raise RuntimeError("lower-text attachment inventory disagrees")
        lower = witness.display.GetLowerText()
        if type(lower) is not str:
            raise RuntimeError("lower-text getter did not return a native string")
        row = {
            "dimension": DIMENSION,
            "parameters": witness.parameters,
            "configuration": witness.configuration,
            "attachment_types": types,
            "lower_text": lower,
        }
        key = f"{owner.GetName2()}/{annotation.GetName()}"
        return key, row, (annotation, owner, witness, entities)

    def _unchanged(self, before, after):
        old_key, old_row, old = before
        key, row, new = after
        if old_key != key or {
            k: v for k, v in old_row.items() if k != "lower_text"
        } != {k: v for k, v in row.items() if k != "lower_text"}:
            raise RuntimeError("lower-text identity/configuration/attachments changed")
        self._same(old[0], new[0], "annotation")
        self._same(old[1], new[1], "owner")
        _same_dimension(self.adapter.swApp, key, old[2], new[2])
        for first, second in zip(old[3], new[3], strict=True):
            if first is None and second is None:
                continue  # Recorded null slot, not an invented geometry identity.
            self._same(first, second, "attached entity")

    def _call(self, adapter, annotations, callout_text, *, location="below"):
        if self.lifetime is not _Lifetime.ACTIVE or self.calls:
            raise RuntimeError("lower-text callout control must run exactly once")
        self.calls += 1
        record = self.report["operation"]
        started = time.perf_counter()
        try:
            if callout_text != CALLOUT or location != "below":
                raise RuntimeError("lower-text requires the exact bore mapping below")
            model = self._drawing(adapter)
            selected = tuple(annotations)
            if len(selected) != 1:
                raise RuntimeError("lower-text requires one exact passed annotation")
            before = self._read(selected[0], self.handles)
            record.update(annotation=before[0], before=before[1])
            if self.storage is CalloutStorage.LOWER_TEXT_BEFORE_SAVE:
                self.pending = model, before
                record["status"] = "queued"
                return
            self._apply(model, before)
        except BaseException as error:
            record.update(status="failed", error=repr(error))
            raise
        finally:
            record["seconds"] = time.perf_counter() - started

    def _apply(self, model, before):
        if self.writes:
            raise RuntimeError("lower-text native write must run exactly once")
        self.writes += 1  # A failed setter is not permission to retry.
        record = self.report["operation"]
        self._same(model, self._drawing(self.adapter), "pre-set drawing")
        display = before[2][2].display
        display.SetLowerText(TEXT)  # void; never interpret None as failure.
        record["setter_readback"] = display.GetLowerText()
        if record["setter_readback"] != TEXT:
            raise RuntimeError("SetLowerText exact native readback failed")
        model.EditRebuild3()  # Same one rebuild as set_dimension_callouts.
        self._same(model, self._drawing(self.adapter), "post-rebuild drawing")
        after = self._read(before[2][0], self.handles)
        record["after"] = after[1]
        self._unchanged(before, after)
        if after[1]["lower_text"] != TEXT:
            raise RuntimeError("rebuild lost the exact native lower text")
        record["status"] = "passed"

    def _apply_queued(self):
        record = self.report["operation"]
        started = time.perf_counter()
        try:
            if (
                self.lifetime is not _Lifetime.ACTIVE
                or self.pending is None
                or self.writes
                or record.get("status") != "queued"
            ):
                raise RuntimeError("queued lower-text native write must run exactly once")
            model, queued = self.pending
            self._same(model, self._drawing(self.adapter), "queued drawing")
            fresh = self._fresh_match(self.adapter, self.handles)
            record["before_save"] = fresh[1]
            self._unchanged(queued, fresh)
            self._apply(model, fresh)  # Fresh native display, not the queued handle.
        except BaseException as error:
            record.update(status="failed", error=repr(error))
            raise
        finally:
            record["before_save_seconds"] = time.perf_counter() - started

    def _save_wrapper(self, original):
        def save(adapter, slddrw_path, *, artifact_context=None, **kwargs):
            if (
                self.lifetime is not _Lifetime.ACTIVE
                or adapter is not self.adapter
                or Path(slddrw_path).resolve() != self.module.OUTPUTS.slddrw.resolve()
            ):
                raise RuntimeError("queued lower-text save scope changed")

            @contextmanager
            def artifact(kind, path):
                with (
                    artifact_context(kind, path) if artifact_context else nullcontext()
                ):
                    if kind == "drawing":
                        if Path(path).resolve() != self.module.OUTPUTS.slddrw.resolve():
                            raise RuntimeError("queued lower-text native target changed")
                        self._apply_queued()
                    yield

            return original(
                adapter, slddrw_path, artifact_context=artifact, **kwargs
            )

        return save

    @contextmanager
    def observe(self):
        if self.lifetime is not _Lifetime.READY:
            raise RuntimeError("lower-text context can be entered only once")
        self.lifetime = _Lifetime.ACTIVE
        try:
            original = getattr(self.module, "set_dimension_callouts", None)
            if original is None or hasattr(self.module, "verify_dimension_callouts"):
                raise ValueError(
                    "unsupported recipe contract for lower-text experiment. "
                    + HISTORICAL_REPLAY
                )
            if common.set_dimension_callouts is not original:
                raise RuntimeError("lower-text recipe/common helper alias changed")
            replacement = self._call
            save_scope = (
                patch.object(
                    common, "save_drawing", self._save_wrapper(common.save_drawing)
                )
                if self.storage is CalloutStorage.LOWER_TEXT_BEFORE_SAVE
                else nullcontext()
            )
            with (
                patch.object(self.module, "set_dimension_callouts", replacement),
                patch.object(common, "set_dimension_callouts", replacement),
                save_scope,
            ):
                yield
        finally:
            self.lifetime = _Lifetime.CLOSED

    def require_used(self):
        if (
            self.calls != 1 or self.writes != 1
            or self.report["operation"].get("status") != "passed"
        ):
            raise RuntimeError("lower-text requires one completed callout operation")

    def _fresh_match(self, adapter, source_handles):
        self._require_manifest(source_handles)
        model = self._drawing(adapter)
        matches = []
        for sheet in _early_bound(model, "IDrawingDoc").GetViews() or ():
            for raw_view in sheet:
                view = _early_bound(raw_view, "IView")
                for raw in view.GetAnnotations() or ():
                    annotation = _early_bound(raw, "IAnnotation")
                    if annotation.GetType() != 4:
                        continue
                    display = _early_bound(
                        annotation.GetSpecificAnnotation(), "IDisplayDimension"
                    )
                    dimension = _early_bound(display.GetDimension2(0), "IDimension")
                    if dimension is None:
                        raise RuntimeError("lower-text inventory has null parameter")
                    if "@".join(dimension.FullName.split("@")[:2]) != DIMENSION:
                        continue
                    matches.append(self._read(annotation, source_handles, view=view))
        if len(matches) != 1:
            raise RuntimeError("lower-text fresh inventory needs one exact dimension")
        self._same(model, self._drawing(adapter), "snapshot drawing")
        return matches[0]

    def _fresh_rows(self, adapter, source_handles):
        key, row, _ = self._fresh_match(adapter, source_handles)
        return {key: row}

    def boundary_snapshot(self):
        """Observe loss without accepting it or reading source-part lower text.

        For the nested source observer's non-initial banks only: the original
        source handles remain valid in this one open recipe context. Built/cold
        acceptance instead uses snapshot with phase-fresh source handles.
        No generic IDisplayData/text geometry is read and no setter is called.
        """
        if self.lifetime is not _Lifetime.ACTIVE:
            raise RuntimeError("lower-text boundary read requires the active context")
        return self._fresh_rows(self.adapter, self.handles)

    def snapshot(self, adapter, source_handles, *, phase, annotations):
        """Fresh drawing displays + supplied phase-fresh parameter handles only.

        annotations is the already captured all_annotation_layout mapping. Its
        generic text proves printed content independently of hidden lower storage;
        the pilot separately compares full raw geometry/render/cold witnesses.
        No full IDisplayData pass is repeated here and no old drawing handle is
        retained or compared across close/reopen.
        """
        record = self.report["snapshots"][phase] = {"rows": {}}
        try:
            self.require_used()
            record["rows"] = self._fresh_rows(adapter, source_handles)
            ((key, row),) = record["rows"].items()
            if row["lower_text"] != TEXT:
                raise RuntimeError("fresh drawing lost exact lower text")
            if key not in annotations:
                raise RuntimeError("lower-text has no matching native text witness")
            values = [text["value"] for text in annotations[key]["generic"]["texts"]]
            record["native_text_values"] = values
            if any(type(value) is not str for value in values):
                raise RuntimeError("lower-text native text witness is not strings")
            lines = [line for value in values for line in value.splitlines()]
            wanted = TEXT.splitlines()
            if any(lines.count(line) != 1 for line in wanted) or lines.index(
                wanted[0]
            ) >= lines.index(wanted[1]):
                raise RuntimeError("lower-text requested lines are not both displayed")
            row["displayed_lines"] = wanted
            record["status"] = "passed"
            return record["rows"]
        except BaseException as error:
            record.update(status="failed", error=repr(error))
            raise
