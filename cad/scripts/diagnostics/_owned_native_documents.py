"""Exact native ownership for copy-only diagnostics, not production builds.

The underlying COM handles and argument shapes remain unchanged. Only lifecycle
operations are guarded. Visible baseline documents, including unsaved/dirty ones,
are borrowed and immutable; hidden baseline documents are refused because native
ISldWorks.CloseDoc also closes non-active hidden documents. Every close witnesses
the complete native inventory, so a new unrelated document prevents cleanup.

Native inventory/reference contracts: ISldWorks.GetDocuments/IsSame/CloseDoc,
IDrawingDoc.GetViews and IView.ReferencedDocument (official SW2026 API reference).
Creation and SaveAs are explicit scopes, never inferred from arbitrary assignment.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum, IntEnum
import hashlib
import json
from pathlib import Path

from solidworks_mcp.adapters.base import AdapterResult, AdapterResultStatus

from _common import _early_bound
from diagnostics._owned_native_session import run_owned_diagnostic


class DocumentKind(IntEnum):
    PART = 1
    ASSEMBLY = 2
    DRAWING = 3


class Ownership(Enum):
    BASELINE = "baseline_borrowed"
    COPY = "owned_copy"
    SOURCE = "opened_read_only_source"
    REFERENCE = "implicit_read_only_reference"


class DocumentState(Enum):
    CLEAN = "clean"
    DIRTY = "dirty"
    VISIBLE = "visible"
    HIDDEN = "hidden"


@dataclass
class NativeDocument:
    handle: object
    ownership: Ownership
    state: dict
    paths: set[Path] = field(default_factory=set)


def _state(document):
    return {
        "path": str(document.GetPathName()),
        "title": str(document.GetTitle()),
        "kind": int(document.GetType()),
        "dirty": DocumentState.DIRTY if document.GetSaveFlag() else DocumentState.CLEAN,
        "visible": DocumentState.VISIBLE if document.Visible else DocumentState.HIDDEN,
    }


def _digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class DiagnosticDocuments:
    def __init__(self, adapter):
        self.adapter = adapter
        self.app = _early_bound(adapter.swApp, "ISldWorks")
        self.directories, self.sources, self.records = set(), {}, []
        self.current = None
        self.creation = None
        self.events = []
        self.failure = self.cleanup_error = None
        for document in self._documents():
            state = _state(document)
            if state["visible"] is DocumentState.HIDDEN:
                raise RuntimeError(
                    f"hidden pre-existing document prevents safe scoped CloseDoc: {state}"
                )
            self.records.append(NativeDocument(document, Ownership.BASELINE, state))
        self.inventory()

    def _documents(self):
        return tuple(
            _early_bound(raw, "IModelDoc2") for raw in self.app.GetDocuments() or ()
        )

    def _same(self, first, second):
        return (
            first is not None
            and second is not None
            and int(self.app.IsSame(first, second)) == 1
        )

    def _record(self, handle):
        # Filter by captured names before IsSame: CloseDoc may have unloaded
        # another hidden reference, whose wrapper must not be sent back to COM.
        state = _state(handle)
        matches = [
            record
            for record in self.records
            if record.state["path"] == state["path"]
            and record.state["title"] == state["title"]
            and record.state["kind"] == state["kind"]
            and self._same(record.handle, handle)
        ]
        if len(matches) > 1:
            raise RuntimeError("native ownership identity is duplicated")
        return matches[0] if matches else None

    def register_directory(self, directory):
        path = Path(directory).resolve(strict=True)
        if not path.is_dir():
            raise RuntimeError("diagnostic output directory does not exist")
        if any(source.is_relative_to(path) for source in self.sources):
            raise RuntimeError(
                f"diagnostic directory overlaps a registered source: {path}"
            )
        if (path / "ownership.json").exists() and path not in self.directories:
            raise RuntimeError(
                "diagnostic directory already contains ownership evidence"
            )
        self.directories.add(path)
        self.checkpoint()

    def register_source(self, source):
        path = Path(source).resolve(strict=True)
        if any(path.is_relative_to(directory) for directory in self.directories):
            raise RuntimeError(
                f"registered source overlaps diagnostic output directory: {path}"
            )
        for record in self.records:
            if record.ownership is not Ownership.BASELINE or not record.state["path"]:
                continue
            if (
                Path(record.state["path"]).resolve() == path
                and record.state["dirty"] is DocumentState.DIRTY
            ):
                raise RuntimeError(
                    "dirty source already open; coherent copied-file evidence is not established"
                )
        if path not in self.sources:
            self.sources[path] = _digest(path)
        self.checkpoint()

    def _output(self, path):
        path = Path(path).resolve()
        if path.parent not in self.directories:
            raise RuntimeError(
                "native output must belong to an exact registered diagnostic directory"
            )
        if path in self.sources or any(
            record.ownership is Ownership.BASELINE
            and record.state["path"]
            and Path(record.state["path"]).resolve() == path
            for record in self.records
        ):
            raise RuntimeError(
                f"native output aliases a protected source/baseline document: {path}"
            )
        if path.suffix.lower() not in {".slddrw", ".sldprt", ".sldasm", ".drwdot"}:
            raise RuntimeError(
                "diagnostic native output has an unsupported document extension"
            )
        return path

    def inventory(self, *, may_unload=()):
        documents, seen, paths, titles = self._documents(), [], set(), set()
        for document in documents:
            state = _state(document)
            path = (
                str(Path(state["path"]).resolve()).casefold() if state["path"] else ""
            )
            title = state["title"].casefold()
            if not title or title in titles or (path and path in paths):
                raise RuntimeError(f"ambiguous native title or document path: {state}")
            titles.add(title)
            if path:
                paths.add(path)
            record = self._record(document)
            if record is None:
                raise RuntimeError(
                    f"unexpected native document prevents isolated cleanup: {state}"
                )
            seen.append(record)
            if record.ownership is not Ownership.COPY and state != record.state:
                raise RuntimeError(
                    f"{record.ownership.value} document state changed: initial={record.state}, actual={state}"
                )
            if record.ownership is Ownership.COPY:
                if (
                    state["path"] != record.state["path"]
                    or state["title"] != record.state["title"]
                    or state["kind"] != record.state["kind"]
                ):
                    raise RuntimeError(
                        "owned native document identity/path changed outside its authorized scope"
                    )
            if state["path"]:
                named = self.app.GetOpenDocumentByName(state["path"])
                if not self._same(named, document):
                    raise RuntimeError(
                        "native full path does not resolve to the exact document identity"
                    )
        for record in tuple(self.records):
            if any(record is item for item in seen):
                continue
            if any(record is item for item in may_unload):
                self.records.remove(record)
                continue
            raise RuntimeError(
                f"native document disappeared or was replaced: {record.state}"
            )
        return documents

    def _add_references(self, model):
        if int(model.GetType()) != DocumentKind.DRAWING:
            return
        drawing = _early_bound(model, "IDrawingDoc")
        for sheet in drawing.GetViews() or ():
            for raw in sheet[1:]:
                view = _early_bound(raw, "IView")
                raw_reference = view.ReferencedDocument
                if raw_reference is None or isinstance(raw_reference, str):
                    continue  # Section reference is also exposed by its base view.
                reference = _early_bound(raw_reference, "IModelDoc2")
                if self._record(reference) is not None:
                    continue
                state = _state(reference)
                if not state["path"]:
                    raise RuntimeError("drawing reference has no native source path")
                path = Path(state["path"]).resolve(strict=True)
                if path.parent in self.directories:
                    self._output(path)
                    role = Ownership.COPY
                else:
                    self.register_source(path)
                    role = Ownership.REFERENCE
                self.records.append(NativeDocument(reference, role, state, {path}))

    def _claim_open(self, path):
        model = _early_bound(self.adapter.currentModel, "IModelDoc2")
        if model is None:
            model = _early_bound(
                self.app.GetOpenDocumentByName(str(path)), "IModelDoc2"
            )
        if (
            model is None
            or str(model.GetPathName()) == ""
            or Path(model.GetPathName()).resolve() != path
        ):
            raise RuntimeError(
                "native open returned the wrong document, not the authorized path"
            )
        if not self._same(self.app.GetOpenDocumentByName(str(path)), model):
            raise RuntimeError(
                "native open document does not match exact named identity"
            )
        record = self._record(model)
        if record is None:
            role = (
                Ownership.COPY if path.parent in self.directories else Ownership.SOURCE
            )
            record = NativeDocument(model, role, _state(model), {path})
            self.records.append(record)
        self._add_references(model)
        self.inventory()
        self.adapter.currentModel, self.current = model, record
        self.events.append(
            {
                "operation": "open",
                "path": str(path),
                "ownership": record.ownership.value,
            }
        )
        self.checkpoint()
        return model

    async def open_model(self, path, *args, **kwargs):
        self.inventory()
        path = Path(path).resolve(strict=True)
        if path.parent in self.directories:
            self._output(path)
        elif path not in self.sources:
            raise RuntimeError(
                "source open requires explicit read-only source registration"
            )
        try:
            result = await self.adapter.open_model(str(path), *args, **kwargs)
        except Exception as error:
            try:
                self._claim_open(path)
            except Exception as ownership_error:
                self.events.append(
                    {
                        "operation": "failed_open_unclaimed",
                        "path": str(path),
                        "error": repr(ownership_error),
                    }
                )
                self.checkpoint()
            raise error
        if not result.is_success:
            try:
                self._claim_open(path)
            except Exception as ownership_error:
                self.events.append(
                    {
                        "operation": "failed_open_unclaimed",
                        "path": str(path),
                        "error": repr(ownership_error),
                    }
                )
            self.checkpoint()
            return result
        self._claim_open(path)
        return result

    def assign_current(self, model):
        if model is None:
            self.adapter.currentModel = None
            self.current = None
            return
        record = self._record(model)
        created_now = False
        if (
            record is not None
            and self.creation is not None
            and self.creation[2] is None
        ):
            raise RuntimeError(
                "creation scope cannot claim an existing native document"
            )
        if record is None and self.creation is not None:
            kind, output, created = self.creation
            if created is not None:
                raise RuntimeError(
                    "creation scope attempted to claim a second native document"
                )
            if int(model.GetType()) != int(kind) or str(model.GetPathName()):
                raise RuntimeError(
                    "creation scope requires one new unsaved document of the declared kind"
                )
            if not self._same(self.app.ActiveDoc, model):
                raise RuntimeError(
                    "created native document is not the exact active handle"
                )
            record = NativeDocument(model, Ownership.COPY, _state(model), {output})
            self.records.append(record)
            created_now = True
            self._add_references(model)
        if record is None:
            raise RuntimeError(
                "arbitrary currentModel assignment cannot claim an unowned document"
            )
        self.inventory()
        self.adapter.currentModel, self.current = model, record
        if created_now:
            self.creation = kind, output, record

    def assert_current_owned(self):
        if self.current is None or self.current.ownership is not Ownership.COPY:
            raise RuntimeError(
                "native write requires an exact owned copy, not a borrowed source"
            )
        if not self._same(self.adapter.currentModel, self.current.handle):
            raise RuntimeError("current native document identity was replaced")
        if not self._same(self.app.ActiveDoc, self.current.handle):
            raise RuntimeError("native write requires the exact owned active document")
        self.inventory()
        return self.current

    @contextmanager
    def creating_document(self, kind, output):
        if not isinstance(kind, DocumentKind) or self.creation is not None:
            raise RuntimeError(
                "creation requires a non-nested explicit native document kind"
            )
        output = self._output(output)
        self.inventory()
        self.creation = kind, output, None
        try:
            yield
            if self.creation[2] is None:
                raise RuntimeError("creation scope produced no owned native document")
        finally:
            try:
                record = self.creation[2]
                if record is not None:
                    if not self._same(self.adapter.currentModel, record.handle):
                        raise RuntimeError(
                            "creation replaced the exact newly owned native handle"
                        )
                    actual = _state(record.handle)
                    path = Path(actual["path"]).resolve() if actual["path"] else None
                    if actual["kind"] != int(kind) or (
                        path is not None and path not in record.paths
                    ):
                        raise RuntimeError(
                            "creation saved to an undeclared native output path"
                        )
                    record.state = actual
                    self._add_references(record.handle)
                    self.inventory()
            finally:
                self.creation = None
                self.checkpoint()

    @contextmanager
    def saving_as(self, output):
        output = self._output(output)
        record = self.assert_current_owned()
        before = dict(record.state)
        record.paths.add(output)
        completed = False
        try:
            yield
            completed = True
        finally:
            if not self._same(self.adapter.currentModel, record.handle):
                raise RuntimeError("SaveAs replaced the exact owned native document")
            actual = _state(record.handle)
            path = Path(actual["path"]).resolve() if actual["path"] else None
            if actual["kind"] != before["kind"] or (
                path != output and actual["path"] != before["path"]
            ):
                raise RuntimeError(
                    "SaveAs changed native path outside the authorized output"
                )
            record.state = actual
            self._add_references(record.handle)
            self.inventory()
            self.checkpoint()
            if completed and path != output:
                raise RuntimeError(
                    "native SaveAs did not reach the requested output path"
                )

    async def close_model(self, save=False):
        if save:
            raise RuntimeError("diagnostic cleanup must never save a native document")
        if self.current is None or not self._same(
            self.adapter.currentModel, self.current.handle
        ):
            raise RuntimeError(
                "current native document identity is not the explicitly claimed handle"
            )
        self.inventory()
        record = self.current
        if record.ownership is Ownership.BASELINE:
            self.adapter.currentModel = self.current = None
            return AdapterResult(status=AdapterResultStatus.SUCCESS)
        return await self._close_record(record)

    async def _close_record(self, record):
        documents = self.inventory()
        collateral = tuple(
            self._record(doc)
            for doc in documents
            if not bool(doc.Visible) and not self._same(doc, self.app.ActiveDoc)
        )
        # Inventory already proved every collateral target is known, not baseline.
        if any(item.ownership is Ownership.BASELINE for item in collateral):
            raise RuntimeError("hidden baseline document prevents safe scoped cleanup")
        self.adapter.currentModel, self.current = record.handle, record
        result = await self.adapter.close_model(save=False)
        if not result.is_success:
            raise RuntimeError(f"native owned document close failed: {result}")
        if any(
            _state(doc)["title"].casefold() == record.state["title"].casefold()
            for doc in self._documents()
        ):
            raise RuntimeError("native owned document remained open after close")
        self.records.remove(record)
        self.adapter.currentModel = self.current = None
        self.inventory(may_unload=collateral)
        self.events.append(
            {
                "operation": "close",
                "path": record.state["path"],
                "ownership": record.ownership.value,
            }
        )
        self.checkpoint()
        return result

    async def close_owned_documents(self):
        self.inventory()
        while True:
            candidates = [
                record
                for record in self.records
                if record.ownership
                in (Ownership.COPY, Ownership.SOURCE, Ownership.REFERENCE)
            ]
            if not candidates:
                break
            # Close drawings before their copied/source references; native close
            # may unload hidden references, which the next inventory observes.
            candidates.sort(
                key=lambda record: record.state["kind"] != DocumentKind.DRAWING
            )
            await self._close_record(candidates[0])
        self.inventory()

    def evidence(self):
        hashes = {}
        for path, before in self.sources.items():
            try:
                after = _digest(path)
                hashes[str(path)] = {
                    "before": before,
                    "after": after,
                    "unchanged": before == after,
                }
            except OSError as error:
                hashes[str(path)] = {
                    "before": before,
                    "unchanged": False,
                    "error": repr(error),
                }
        baseline = [
            dict(record.state)
            for record in self.records
            if record.ownership is Ownership.BASELINE
        ]
        try:
            documents = self._documents()
            final_inventory = [_state(document) for document in documents]
            preserved = all(
                len(
                    matches := [
                        document
                        for document in documents
                        if self._same(document, record.handle)
                    ]
                )
                == 1
                and _state(matches[0]) == record.state
                for record in self.records
                if record.ownership is Ownership.BASELINE
            )
            preservation = {"status": "preserved" if preserved else "changed"}
        except Exception as error:
            final_inventory = []
            preservation = {"status": "unreadable", "error": repr(error)}
        return {
            "events": self.events,
            "source_hashes": hashes,
            "probe_error": self.failure,
            "cleanup_error": self.cleanup_error,
            "baseline_initial": baseline,
            "final_inventory": final_inventory,
            "baseline_preservation": preservation,
        }

    def checkpoint(self):
        evidence = self.evidence()
        for directory in self.directories:
            (directory / "ownership.json").write_text(
                json.dumps(evidence, indent=2, default=lambda value: value.value),
                encoding="utf-8",
            )


class DiagnosticAdapter:
    """Delegate native geometry calls unchanged, guard only document lifecycle."""

    def __init__(self, adapter):
        object.__setattr__(self, "_delegate", adapter)
        object.__setattr__(self, "ownership", DiagnosticDocuments(adapter))

    def __getattr__(self, name):
        return getattr(self._delegate, name)

    def __setattr__(self, name, value):
        if name == "currentModel":
            self.ownership.assign_current(value)
            return
        if name in {"ownership", "swApp", "_delegate"}:
            raise RuntimeError("diagnostic native session ownership cannot be replaced")
        setattr(self._delegate, name, value)

    async def open_model(self, path, *args, **kwargs):
        return await self.ownership.open_model(path, *args, **kwargs)

    async def close_model(self, save=False):
        return await self.ownership.close_model(save=save)

    async def close_owned_documents(self):
        await self.ownership.close_owned_documents()

    async def _create_document(self, operation, kind, *args, **kwargs):
        creation = self.ownership.creation
        if creation is None or creation[0] is not kind or creation[2] is not None:
            raise RuntimeError(
                "adapter document creation requires its explicit creation scope"
            )
        self.ownership.inventory()
        try:
            return await getattr(self._delegate, operation)(*args, **kwargs)
        finally:
            model = self._delegate.currentModel
            if model is not None and self.ownership._record(model) is None:
                self.ownership.assign_current(model)

    async def create_part(self, *args, **kwargs):
        return await self._create_document(
            "create_part", DocumentKind.PART, *args, **kwargs
        )

    async def create_assembly(self, *args, **kwargs):
        return await self._create_document(
            "create_assembly", DocumentKind.ASSEMBLY, *args, **kwargs
        )


async def owned_callback(adapter, callback):
    guarded = DiagnosticAdapter(adapter)
    errors, result = [], None
    try:
        result = await callback(guarded)
    except Exception as error:
        guarded.ownership.failure = repr(error)
        errors.append(error)
    try:
        await guarded.close_owned_documents()
    except Exception as error:
        guarded.ownership.cleanup_error = repr(error)
        errors.append(error)
    finally:
        guarded.ownership.checkpoint()
    if any(
        not row["unchanged"]
        for row in guarded.ownership.evidence()["source_hashes"].values()
    ):
        errors.append(
            RuntimeError("diagnostic source files changed; see ownership evidence")
        )
    if len(errors) == 1:
        raise errors[0]
    if errors:
        raise ExceptionGroup(
            "diagnostic failure with preserved cleanup/source evidence", errors
        )
    return result


def run_copy_diagnostic(callback):
    return run_owned_diagnostic(lambda adapter: owned_callback(adapter, callback))


def save_drawing(adapter, path, *args, **kwargs):
    """Preserve native drawing/PDF export call shapes within one SaveAs scope."""
    from solidworks_mcp.adapters.solidworks.drawing import save_drawing as native_save

    with adapter.ownership.saving_as(path):
        return native_save(adapter, path, *args, **kwargs)
