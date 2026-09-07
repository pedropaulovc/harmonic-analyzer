"""Copy diagnostics preserve the existing native session, including failures."""

import asyncio
from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from diagnostics import _owned_native_documents as owned


class Model:
    def __init__(self, path, *, title=None, kind=3, dirty=False, visible=True):
        self.path = str(path) if path else ""
        self.title = title or (Path(path).name if path else "Drawing1")
        self.kind, self.dirty, self.Visible = kind, dirty, visible
        self.references = []

    def GetPathName(self):
        return self.path

    def GetTitle(self):
        return self.title

    def GetType(self):
        return self.kind

    def GetSaveFlag(self):
        return self.dirty

    def GetViews(self):
        return (
            (
                object(),
                *(SimpleNamespace(ReferencedDocument=ref) for ref in self.references),
            ),
        )


@pytest.fixture
def native(monkeypatch, tmp_path):
    monkeypatch.setattr(owned, "_early_bound", lambda value, _: value)
    directory = tmp_path / "diagnostic"
    directory.mkdir()
    copy = directory / "unique.SLDDRW"
    copy.write_bytes(b"copy")
    source = tmp_path / "source.SLDPRT"
    source.write_bytes(b"original")
    app = SimpleNamespace(documents=[], closes=[], ActiveDoc=None)
    app.GetDocuments = lambda: tuple(app.documents)
    app.IsSame = lambda first, second: int(first is second)
    app.GetOpenDocumentByName = lambda path: next(
        (doc for doc in app.documents if doc.path == str(path)), None
    )
    adapter = SimpleNamespace(swApp=app, currentModel=None, opens=[])

    def close(name):
        matches = [doc for doc in app.documents if doc.title == name]
        assert len(matches) == 1
        model = matches[0]
        app.closes.append(model)
        app.documents.remove(model)
        # Documented native collateral: any non-active hidden documents may close.
        app.documents[:] = [
            doc for doc in app.documents if doc.Visible or doc is app.ActiveDoc
        ]
        if app.ActiveDoc is model:
            app.ActiveDoc = None

    app.CloseDoc = close

    async def open_model(path):
        adapter.opens.append(path)
        model = app.GetOpenDocumentByName(path)
        if model is None:
            model = Model(path, kind=1 if Path(path).suffix == ".SLDPRT" else 3)
            app.documents.append(model)
        adapter.currentModel = app.ActiveDoc = model
        return SimpleNamespace(is_success=True, data=None)

    async def close_model(save=False):
        assert not save
        app.CloseDoc(adapter.currentModel.GetTitle())
        adapter.currentModel = None
        return SimpleNamespace(is_success=True, data=None)

    adapter.open_model, adapter.close_model = open_model, close_model
    return SimpleNamespace(
        adapter=adapter, app=app, directory=directory, copy=copy, source=source
    )


def facade(native):
    result = owned.DiagnosticAdapter(native.adapter)
    result.ownership.register_directory(native.directory)
    result.ownership.register_source(native.source)
    return result


def test_unrelated_dirty_unsaved_document_survives_open_and_last_trial_cleanup(native):
    user = Model(None, title="User drawing", dirty=True)
    native.app.documents.append(user)
    native.app.ActiveDoc = user
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.copy)))
    copy = adapter.currentModel
    asyncio.run(adapter.close_owned_documents())
    assert native.app.documents == [user]
    assert native.app.closes == [copy]
    assert user.dirty and user.Visible and user.path == ""
    adapter.ownership.checkpoint()
    evidence = json.loads((native.directory / "ownership.json").read_text())
    expected = {
        "path": "",
        "title": "User drawing",
        "kind": 3,
        "dirty": "dirty",
        "visible": "visible",
    }
    assert evidence["baseline_initial"] == [expected]
    assert evidence["final_inventory"] == [expected]
    assert evidence["baseline_preservation"] == {"status": "preserved"}


def test_initial_hidden_document_is_rejected_without_native_mutation(native):
    native.app.documents.append(Model(None, visible=False))
    with pytest.raises(RuntimeError, match="hidden"):
        facade(native)
    assert not native.app.closes and not native.adapter.opens


def test_new_hidden_document_prevents_documented_close_collateral(native):
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.copy)))
    native.app.documents.append(Model(None, title="Unexpected hidden", visible=False))
    with pytest.raises(RuntimeError, match="unexpected"):
        asyncio.run(adapter.close_owned_documents())
    assert not native.app.closes
    assert len(native.app.documents) == 2


@pytest.mark.parametrize("replacement", ["different", "same_path"])
def test_wrong_or_replaced_current_document_is_not_closed(native, replacement):
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.copy)))
    original = adapter.currentModel
    wrong = Model(native.copy if replacement == "same_path" else native.source)
    native.app.documents.remove(original)
    native.app.documents.append(wrong)
    native.adapter.currentModel = native.app.ActiveDoc = wrong
    with pytest.raises(RuntimeError, match="identity|replaced|current"):
        asyncio.run(adapter.close_model())
    assert not native.app.closes


def test_arbitrary_current_assignment_cannot_claim_an_unowned_native_document(native):
    adapter = facade(native)
    model = Model(None)
    native.app.documents.append(model)
    with pytest.raises(RuntimeError, match="unowned|unexpected"):
        adapter.currentModel = model
    assert native.adapter.currentModel is None


def test_failed_open_claims_only_exact_authorized_copy_for_cleanup(native):
    adapter = facade(native)
    original_open = native.adapter.open_model

    async def failing(path):
        await original_open(path)
        raise RuntimeError("native open failed after document creation")

    native.adapter.open_model = failing
    with pytest.raises(RuntimeError, match="native open failed"):
        asyncio.run(adapter.open_model(str(native.copy)))
    copy = native.adapter.currentModel
    asyncio.run(adapter.close_owned_documents())
    assert native.app.closes == [copy]


def test_failed_open_does_not_claim_wrong_document(native):
    user = Model(None, title="Existing unsaved", dirty=True)
    native.app.documents.append(user)
    adapter = facade(native)

    async def failing(_path):
        native.adapter.currentModel = native.app.ActiveDoc = user
        raise RuntimeError("wrong native open")

    native.adapter.open_model = failing
    with pytest.raises(RuntimeError, match="open|wrong"):
        asyncio.run(adapter.open_model(str(native.copy)))
    asyncio.run(adapter.close_owned_documents())
    assert native.app.documents == [user] and not native.app.closes


def test_borrowed_visible_source_is_never_a_close_target(native):
    source = Model(native.source, kind=1)
    native.app.documents.append(source)
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.source)))
    asyncio.run(adapter.close_model())
    asyncio.run(adapter.close_owned_documents())
    assert native.app.documents == [source] and not native.app.closes


def test_existing_dirty_source_rejected_without_losing_unrelated_dirty_document(native):
    source = Model(native.source, kind=1, dirty=True)
    native.app.documents.append(source)
    with pytest.raises(RuntimeError, match="dirty source"):
        facade(native)
    assert native.app.documents == [source] and not native.app.closes


def test_implicit_part_reference_is_witnessed_before_native_close_unloads_it(native):
    adapter = facade(native)
    original_open = native.adapter.open_model
    reference = Model(native.source, kind=1, visible=False)

    async def with_reference(path):
        result = await original_open(path)
        native.adapter.currentModel.references.append(reference)
        native.app.documents.append(reference)
        return result

    native.adapter.open_model = with_reference
    asyncio.run(adapter.open_model(str(native.copy)))
    asyncio.run(adapter.close_owned_documents())
    assert not native.app.documents
    assert len(native.app.closes) == 1


def test_preexisting_document_state_change_prevents_cleanup(native):
    user = Model(None, title="Visible baseline")
    native.app.documents.append(user)
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.copy)))
    user.dirty = True
    with pytest.raises(RuntimeError, match="baseline.*changed"):
        asyncio.run(adapter.close_owned_documents())
    assert not native.app.closes


def test_failed_save_as_tracks_exact_native_alias_for_safe_final_cleanup(native):
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.copy)))
    model = adapter.currentModel
    saved = native.directory / "observed.SLDDRW"
    with pytest.raises(RuntimeError, match="native save failed"):
        with adapter.ownership.saving_as(saved):
            model.path, model.title = str(saved), saved.name
            raise RuntimeError("native save failed after path transition")
    asyncio.run(adapter.close_owned_documents())
    assert native.app.closes == [model]


def test_save_as_cannot_authorize_borrowed_source_or_external_destination(native):
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.source)))
    with pytest.raises(RuntimeError, match="owned"):
        with adapter.ownership.saving_as(native.directory / "not-owned.SLDPRT"):
            pytest.fail("source must not enter a write scope")
    asyncio.run(adapter.close_model())
    asyncio.run(adapter.open_model(str(native.copy)))
    with pytest.raises(RuntimeError, match="directory"):
        with adapter.ownership.saving_as(native.directory.parent / "outside.SLDDRW"):
            pytest.fail("external output must not enter a write scope")


def test_wrong_active_document_rejects_save_even_with_unchanged_current_pointer(native):
    user = Model(None, title="Unrelated active", dirty=True)
    native.app.documents.append(user)
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.copy)))
    native.app.ActiveDoc = user
    with pytest.raises(RuntimeError, match="active"):
        with adapter.ownership.saving_as(native.directory / "observed.SLDDRW"):
            pytest.fail("SaveAs must not run against the user's active document")
    assert user.dirty and not native.app.closes


@pytest.mark.parametrize("first", ["source", "directory"])
def test_source_and_output_registration_cannot_overlap_in_either_order(native, first):
    adapter = owned.DiagnosticAdapter(native.adapter)
    with pytest.raises(RuntimeError, match="source|overlap"):
        if first == "source":
            adapter.ownership.register_source(native.copy)
            adapter.ownership.register_directory(native.directory)
        if first == "directory":
            adapter.ownership.register_directory(native.directory)
            adapter.ownership.register_source(native.copy)


def test_new_visible_implicit_reference_is_cleaned_up_without_touching_baseline(native):
    user = Model(None, title="Unrelated baseline", dirty=True)
    native.app.documents.append(user)
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.copy)))
    target = adapter.currentModel
    reference = Model(native.source, kind=1, visible=True)
    native.app.documents.append(reference)
    target.references.append(reference)
    adapter.ownership._add_references(target)
    asyncio.run(adapter.close_owned_documents())
    assert native.app.documents == [user]
    assert native.app.closes == [target, reference]


def test_delegate_part_creation_requires_scope_before_native_operation(native):
    calls = []

    async def create_part(*args, **kwargs):
        calls.append((args, kwargs))
        model = Model(None, kind=1)
        native.app.documents.append(model)
        native.app.ActiveDoc = native.adapter.currentModel = model
        return SimpleNamespace(is_success=True, data=None)

    native.adapter.create_part = create_part
    adapter = facade(native)
    with pytest.raises(RuntimeError, match="creation scope"):
        asyncio.run(adapter.create_part("new part", units="mm"))
    assert not calls


def test_delegate_part_creation_claims_raw_current_assignment_in_explicit_scope(native):
    calls = []

    async def create_part(*args, **kwargs):
        calls.append((args, kwargs))
        model = Model(None, kind=1)
        native.app.documents.append(model)
        native.app.ActiveDoc = native.adapter.currentModel = model
        return SimpleNamespace(is_success=True, data=None)

    native.adapter.create_part = create_part
    adapter = facade(native)
    with adapter.ownership.creating_document(
        owned.DocumentKind.PART, native.directory / "part.SLDPRT"
    ):
        asyncio.run(adapter.create_part("new part", units="mm"))
    model = adapter.currentModel
    asyncio.run(adapter.close_owned_documents())
    assert calls == [(("new part",), {"units": "mm"})]
    assert native.app.closes == [model]


def test_creation_scope_claims_one_exact_new_native_document(native):
    adapter = facade(native)
    with adapter.ownership.creating_document(owned.DocumentKind.DRAWING, native.copy):
        model = Model(None)
        native.app.documents.append(model)
        native.app.ActiveDoc = model
        adapter.currentModel = model
    asyncio.run(adapter.close_owned_documents())
    assert native.app.closes == [model]


def test_recipe_creation_scope_witnesses_first_save_to_exact_declared_output(native):
    adapter = facade(native)
    with adapter.ownership.creating_document(owned.DocumentKind.DRAWING, native.copy):
        model = Model(None)
        native.app.documents.append(model)
        native.app.ActiveDoc = model
        adapter.currentModel = model
        model.path, model.title = str(native.copy), native.copy.name
    asyncio.run(adapter.close_owned_documents())
    assert native.app.closes == [model]


def test_recipe_creation_scope_rejects_save_to_an_undeclared_path(native):
    adapter = facade(native)
    with pytest.raises(RuntimeError, match="creation.*path"):
        with adapter.ownership.creating_document(
            owned.DocumentKind.DRAWING, native.copy
        ):
            model = Model(None)
            native.app.documents.append(model)
            native.app.ActiveDoc = model
            adapter.currentModel = model
            model.path = str(native.directory / "not-declared.SLDDRW")
    assert not native.app.closes


def test_creation_scope_rejects_an_ambiguous_native_inventory(native):
    adapter = facade(native)
    with pytest.raises(RuntimeError, match="unexpected|ambiguous"):
        with adapter.ownership.creating_document(
            owned.DocumentKind.DRAWING, native.copy
        ):
            model = Model(None)
            native.app.documents.extend((model, Model(None, title="Unexpected")))
            native.app.ActiveDoc = model
            adapter.currentModel = model
    assert not native.app.closes


def test_creation_scope_cannot_claim_an_existing_baseline_document(native):
    user = Model(None, title="Existing unsaved", dirty=True)
    native.app.documents.append(user)
    adapter = facade(native)
    with pytest.raises(RuntimeError, match="existing"):
        with adapter.ownership.creating_document(
            owned.DocumentKind.DRAWING, native.copy
        ):
            adapter.currentModel = user
            pytest.fail("existing document must not enter creation body")
    assert not native.app.closes and user.dirty


def test_successful_save_scope_requires_native_path_readback(native):
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.copy)))
    with pytest.raises(RuntimeError, match="requested output"):
        with adapter.ownership.saving_as(native.directory / "never-saved.SLDDRW"):
            pass


def test_failure_preserves_source_hash_and_cleanup_evidence(native):
    user = Model(None, title="Preserved user's dirty drawing", dirty=True)
    native.app.documents.append(user)

    async def callback(adapter):
        adapter.ownership.register_directory(native.directory)
        adapter.ownership.register_source(native.source)
        await adapter.open_model(str(native.copy))
        native.app.documents.append(
            Model(None, title="Unexpected hidden", visible=False)
        )
        native.source.write_bytes(b"changed")
        raise RuntimeError("original probe failure")

    with pytest.raises(BaseExceptionGroup) as failure:
        asyncio.run(owned.owned_callback(native.adapter, callback))
    assert "original probe failure" in str(failure.value.exceptions)
    evidence = json.loads((native.directory / "ownership.json").read_text())
    assert evidence["source_hashes"][str(native.source)]["unchanged"] is False
    assert evidence["cleanup_error"]
    assert "Unexpected hidden" in evidence["cleanup_error"]
    assert evidence["baseline_initial"][0]["title"] == user.title
    assert evidence["baseline_preservation"] == {"status": "preserved"}
    assert {row["title"] for row in evidence["final_inventory"]} == {
        user.title,
        native.copy.name,
        "Unexpected hidden",
    }
    assert not native.app.closes


def test_changed_baseline_is_reported_without_rewriting_initial_evidence(native):
    user = Model(None, title="Immutable initial title")
    native.app.documents.append(user)
    adapter = facade(native)
    user.dirty = True
    adapter.ownership.checkpoint()
    evidence = json.loads((native.directory / "ownership.json").read_text())
    assert evidence["baseline_initial"][0]["dirty"] == "clean"
    assert evidence["final_inventory"][0]["dirty"] == "dirty"
    assert evidence["baseline_preservation"] == {"status": "changed"}


def test_callback_finalizer_closes_last_trial_document(native):
    async def callback(adapter):
        adapter.ownership.register_directory(native.directory)
        await adapter.open_model(str(native.copy))
        return {"result": "done"}

    assert asyncio.run(owned.owned_callback(native.adapter, callback)) == {
        "result": "done"
    }
    assert not native.app.documents and len(native.app.closes) == 1


def test_cleanup_does_not_pass_unloaded_target_or_reference_back_to_com(native):
    user = Model(None, title="Existing user document")
    native.app.documents.append(user)
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.copy)))
    target = adapter.currentModel
    reference = Model(native.source, kind=1, visible=False)
    target.references.append(reference)
    native.app.documents.append(reference)
    adapter.ownership._add_references(target)
    original_same = native.app.IsSame

    def reject_unloaded(first, second):
        if target in native.app.closes and (first is target or second is target):
            raise RuntimeError("COM wrapper is disconnected after CloseDoc")
        if target in native.app.closes and (first is reference or second is reference):
            raise RuntimeError("implicit reference wrapper was unloaded")
        return original_same(first, second)

    native.app.IsSame = reject_unloaded
    asyncio.run(adapter.close_owned_documents())
    assert native.app.documents == [user]


def test_freeze_requires_exact_completed_and_closed_owned_artifact(native):
    adapter = facade(native)
    with pytest.raises(RuntimeError, match="completed|closed"):
        adapter.ownership.freeze_owned_input(native.copy)
    asyncio.run(adapter.open_model(str(native.copy)))
    with pytest.raises(RuntimeError, match="completed|closed"):
        adapter.ownership.freeze_owned_input(native.copy)
    asyncio.run(adapter.close_model())
    adapter.ownership.freeze_owned_input(native.copy)
    adapter.ownership.register_source(native.copy)  # Explicit nested read-only reuse.
    with pytest.raises(RuntimeError, match="protected|source|frozen"):
        asyncio.run(adapter.open_model(str(native.copy)))
    evidence = adapter.ownership.evidence()
    assert evidence["frozen_inputs"][str(native.copy)]["native_state"]["path"] == str(
        native.copy
    )
    assert evidence["source_hashes"][str(native.copy)]["unchanged"]


@pytest.mark.parametrize("replacement", ["bytes", "file", "native_handle"])
def test_freeze_rejects_changed_file_or_replaced_native_handle(native, replacement):
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.copy)))
    asyncio.run(adapter.close_model())
    if replacement == "bytes":
        native.copy.write_bytes(b"replacement contents")
    if replacement == "file":
        substitute = native.directory / "substitute.SLDDRW"
        substitute.write_bytes(native.copy.read_bytes())
        substitute.replace(native.copy)
    if replacement == "native_handle":
        native.app.documents.append(Model(native.copy))
    with pytest.raises(RuntimeError, match="changed|unexpected|replaced"):
        adapter.ownership.freeze_owned_input(native.copy)


def test_frozen_artifact_replacement_is_rejected_on_nested_source_reuse(native):
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.copy)))
    asyncio.run(adapter.close_model())
    adapter.ownership.freeze_owned_input(native.copy)
    native.copy.write_bytes(b"changed after freeze")
    with pytest.raises(RuntimeError, match="changed|replaced"):
        adapter.ownership.register_source(native.copy)


def test_explicit_native_open_scope_preserves_readonly_call_shape_and_claims_source(
    native,
):
    adapter = facade(native)
    calls = []

    def open_doc(*args):
        calls.append(args)
        model = Model(native.source, kind=1)
        native.app.documents.append(model)
        native.app.ActiveDoc = model
        return model, 0, 0

    with adapter.ownership.opening_native_document(native.source) as claim:
        result = open_doc(str(native.source), 1, 3, "Exact configuration", 0, 0)
        claim(result[0])
    assert calls == [(str(native.source), 1, 3, "Exact configuration", 0, 0)]
    with pytest.raises(RuntimeError, match="borrowed|source|owned"):
        adapter.ownership.assert_current_owned()
    asyncio.run(adapter.close_owned_documents())
    assert native.app.closes == [result[0]]


def test_failed_explicit_native_open_claims_only_requested_source_for_cleanup(native):
    adapter = facade(native)
    model = Model(native.source, kind=1)
    with pytest.raises(RuntimeError, match="native result error"):
        with adapter.ownership.opening_native_document(native.source):
            native.app.documents.append(model)
            raise RuntimeError("native result error")
    asyncio.run(adapter.close_owned_documents())
    assert native.app.closes == [model]


def test_finalization_rejects_same_bytes_replacement_after_frozen_nested_reuse(native):
    async def callback(adapter):
        adapter.ownership.register_directory(native.directory)
        await adapter.open_model(str(native.copy))
        await adapter.close_model()
        adapter.ownership.freeze_owned_input(native.copy)
        adapter.ownership.register_source(native.copy)
        substitute = native.directory / "same-bytes.SLDDRW"
        substitute.write_bytes(native.copy.read_bytes())
        substitute.replace(native.copy)

    with pytest.raises(RuntimeError, match="source files changed"):
        asyncio.run(owned.owned_callback(native.adapter, callback))
    report = json.loads((native.directory / "ownership.json").read_text())
    frozen = report["source_hashes"][str(native.copy)]
    assert frozen["before"] == frozen["after"]
    assert not frozen["file_identity_unchanged"]
    assert not frozen["unchanged"]


def test_legacy_save_reconciles_rename_before_after_artifact_observation(native):
    user = Model(None, title="Preserved dirty drawing", dirty=True)
    native.app.documents.append(user)
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.copy)))
    model = adapter.currentModel
    target = native.directory / "renamed.SLDDRW"
    pdf, png = target.with_suffix(".pdf"), target.with_suffix(".png")
    calls, observations = [], []
    for path in (target, pdf, png):
        path.write_bytes(b"stale")

    def save(path, version, options):
        path = Path(path)
        assert not path.exists()
        calls.append((str(path), version, options))
        path.write_bytes(b"fresh " + path.suffix.encode())
        if path == target:
            model.path, model.title = str(path), path.name
        return 17  # Legacy code is not interpreted; existing file gate is retained.

    @contextmanager
    def observe(kind, path):
        adapter.ownership.assert_current_owned()
        observations.append(("before", kind, adapter.ownership.current.state["path"]))
        yield
        adapter.ownership.assert_current_owned()
        observations.append(("after", kind, adapter.ownership.current.state["path"]))

    model.SaveAs3 = save
    result = owned.save_drawing(
        adapter,
        str(target),
        pdf_path=str(pdf),
        png_path=str(png),
        artifact_context=observe,
    )
    assert calls == [(str(path), 0, 0) for path in (target, pdf, png)]
    assert result == {"drawing": str(target), "pdf": str(pdf), "png": str(png)}
    assert observations == [
        ("before", "drawing", str(native.copy)),
        ("after", "drawing", str(target)),
        ("before", "pdf", str(target)),
        ("after", "pdf", str(target)),
        ("before", "png", str(target)),
        ("after", "png", str(target)),
    ]
    asyncio.run(adapter.close_owned_documents())
    assert native.app.documents == [user]
    assert native.app.closes == [model]
    assert native.source.read_bytes() == b"original"


@pytest.mark.parametrize("phase", ["drawing", "pdf", "png"])
def test_legacy_save_checks_active_owner_after_observer_before_writes(native, phase):
    user = Model(None, title="User document", dirty=True)
    native.app.documents.append(user)
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.copy)))
    model = adapter.currentModel
    paths = [
        native.directory / "output.SLDDRW",
        native.directory / "output.pdf",
        native.directory / "output.png",
    ]
    calls = []
    for path in paths:
        path.write_bytes(b"stale")

    def save(path, version, options):
        calls.append((str(path), version, options))
        Path(path).write_bytes(b"new")
        if Path(path) == paths[0]:
            model.path, model.title = str(path), Path(path).name
        return 0

    @contextmanager
    def observe(kind, path):
        if kind == phase:
            native.app.ActiveDoc = user
        yield

    model.SaveAs3 = save
    with pytest.raises(RuntimeError, match="active"):
        owned.save_drawing(
            adapter,
            str(paths[0]),
            pdf_path=str(paths[1]),
            png_path=str(paths[2]),
            artifact_context=observe,
        )
    index = ["drawing", "pdf", "png"].index(phase)
    assert calls == [(str(path), 0, 0) for path in paths[:index]]
    assert all(path.read_bytes() == b"stale" for path in paths[index:])
    assert native.app.ActiveDoc is user
    assert not native.app.closes and user.dirty


def test_legacy_save_rejects_observer_switch_to_different_owned_document(native):
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.copy)))
    original = adapter.currentModel
    target = native.directory / "output.SLDDRW"
    target.write_bytes(b"stale")
    other = native.directory / "other.SLDDRW"
    other.write_bytes(b"other owned")
    calls = []
    original.SaveAs3 = lambda *args: calls.append(args)

    @contextmanager
    def observe(kind, path):
        asyncio.run(adapter.open_model(str(other)))
        adapter.ownership.assert_current_owned()  # Owned is not the same document.
        yield

    with pytest.raises(RuntimeError, match="owned document changed"):
        owned.save_drawing(adapter, str(target), artifact_context=observe)
    assert not calls
    assert target.read_bytes() == b"stale"


def test_legacy_save_failure_observer_sees_reconciled_renamed_document(native):
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.copy)))
    model = adapter.currentModel
    target = native.directory / "partial.SLDDRW"
    failure = RuntimeError("native failed after rename")
    observations = []

    def save(path, *_args):
        model.path, model.title = str(path), Path(path).name
        Path(path).write_bytes(b"retained partial file")
        raise failure

    @contextmanager
    def observe(kind, path):
        try:
            yield
        finally:
            adapter.ownership.assert_current_owned()
            observations.append((kind, adapter.ownership.current.state["path"]))

    model.SaveAs3 = save
    with pytest.raises(RuntimeError, match="native failed after rename") as caught:
        owned.save_drawing(adapter, str(target), artifact_context=observe)
    assert caught.value is failure
    assert observations == [("drawing", str(target))]
    assert target.read_bytes() == b"retained partial file"
    asyncio.run(adapter.close_owned_documents())
    assert native.app.closes == [model]


def test_legacy_save_keeps_native_and_after_observer_failures(native):
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.copy)))
    model = adapter.currentModel
    target = native.directory / "partial.SLDDRW"
    native_failure = RuntimeError("native save failed")
    observer_failure = RuntimeError("after bank failed")

    def save(path, *_args):
        model.path, model.title = str(path), Path(path).name
        Path(path).write_bytes(b"partial")
        raise native_failure

    @contextmanager
    def observe(kind, path):
        try:
            yield
        finally:
            adapter.ownership.assert_current_owned()
            raise observer_failure

    model.SaveAs3 = save
    with pytest.raises(ExceptionGroup) as caught:
        owned.save_drawing(adapter, str(target), artifact_context=observe)
    assert caught.value.exceptions == (native_failure, observer_failure)
    assert target.read_bytes() == b"partial"
    assert adapter.ownership.current.state["path"] == str(target)
    asyncio.run(adapter.close_owned_documents())
    assert native.app.closes == [model]


@pytest.mark.parametrize("target", [None, ""])
def test_legacy_save_requires_native_target_before_any_export(native, target):
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.copy)))
    calls = []
    adapter.currentModel.SaveAs3 = lambda *args: calls.append(args)
    pdf = native.directory / "existing.pdf"
    pdf.write_bytes(b"preserve")
    with pytest.raises(ValueError, match="native target"):
        owned.save_drawing(adapter, target, pdf_path=str(pdf))
    assert not calls
    assert pdf.read_bytes() == b"preserve"


@pytest.mark.parametrize("missing", ["drawing", "pdf", "png"])
def test_legacy_save_preserves_missing_file_gate_without_observer(native, missing):
    adapter = facade(native)
    asyncio.run(adapter.open_model(str(native.copy)))
    model = adapter.currentModel
    paths = [
        native.directory / "output.SLDDRW",
        native.directory / "output.pdf",
        native.directory / "output.png",
    ]
    index = ["drawing", "pdf", "png"].index(missing)
    calls = []
    for path in paths:
        path.write_bytes(b"stale")

    def save(path, version, options):
        path = Path(path)
        calls.append((str(path), version, options))
        assert not path.exists()
        if path == paths[0]:
            model.path, model.title = str(path), path.name
        if path != paths[index]:
            path.write_bytes(b"new")
        return 0

    model.SaveAs3 = save
    with pytest.raises(RuntimeError, match="SaveAs3 produced no file"):
        owned.save_drawing(
            adapter, str(paths[0]), pdf_path=str(paths[1]), png_path=str(paths[2])
        )
    assert calls == [(str(path), 0, 0) for path in paths[: index + 1]]
    assert not paths[index].exists()
    assert all(path.read_bytes() == b"stale" for path in paths[index + 1 :])
    adapter.ownership.assert_current_owned()
