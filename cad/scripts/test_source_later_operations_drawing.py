"""Additional selected-control banks keep native calls and default banks intact."""

import inspect
import ast
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import _source_save_boundaries as control
from test_source_save_boundaries_drawing import bank as source_bank


@pytest.fixture
def bank(tmp_path, monkeypatch):
    return source_bank.__wrapped__(tmp_path, monkeypatch)


@pytest.fixture
def remaining(bank):
    names = (
        "auto_center_marks",
        "visible_circle_edge",
        "add_datum_feature",
        "add_feature_control_frame",
        "add_surface_finish",
        "add_property_linked_note",
        "add_property_linked_note",
        "finalize_drawing",
    )
    calls, returns, originals = [], {}, {}
    text = NS(lower="fit")
    bank.observer.drawing_reader = Mock(side_effect=lambda: {"lower_text": text.lower})
    arg, keyword = object(), object()

    def sync(name):
        def operation(adapter, *args, **kwargs):
            assert adapter is bank.adapter
            assert args == (arg,)
            assert kwargs == {"native_option": keyword}
            calls.append(name)
            if name == "add_surface_finish":
                text.lower = ""  # Observation, not an acceptance waiver.
            return returns[name]

        return operation

    async def finalize(adapter, *args, **kwargs):
        assert adapter is bank.adapter
        assert args == (arg,)
        assert kwargs == {"native_option": keyword}
        calls.append("finalize_drawing")
        control.drawing.save_drawing(
            adapter,
            str(bank.outputs.slddrw),
            pdf_path=str(bank.outputs.pdf),
            artifact_context=bank.artifact,
        )
        return returns["finalize_drawing"]

    for name in dict.fromkeys(names):
        returns[name] = object()
        originals[name] = finalize if name == "finalize_drawing" else sync(name)
        setattr(bank.module, name, originals[name])
    return NS(**locals())


@pytest.mark.asyncio
async def test_selected_remaining_boundaries_keep_args_returns_order_and_all_raw_banks(
    remaining,
):
    r, bank = remaining, remaining.bank
    with bank.observer.observe():
        bank.module.set_dimension_callouts(bank.adapter, [], {})
        bank.module.set_dimension_precision(bank.adapter, [], {})
        for name in r.names[:-1]:
            result = getattr(bank.module, name)(
                bank.adapter, r.arg, native_option=r.keyword
            )
            assert result is r.returns[name]
        assert inspect.iscoroutinefunction(bank.module.finalize_drawing)
        result = await bank.module.finalize_drawing(
            bank.adapter, r.arg, native_option=r.keyword
        )
        assert result is r.returns["finalize_drawing"]
    bank.observer.require_used()
    assert r.calls == list(r.names)
    assert bank.observer.stages == list(control.STAGES)
    rows = bank.trial["source_boundaries"]["banks"]
    assert len(rows) == 25  # Default nine + before/after eight loaded calls.
    assert bank.observer.drawing_reader.call_count == 24
    labels = [row["boundary"] for row in rows]
    assert labels[:5] == [
        "initial",
        "before_callouts",
        "after_callouts",
        "before_precision",
        "after_precision",
    ]
    assert labels[-6:] == [
        "before_drawing.finalize_drawing#1",
        "before_native_save",
        "after_native_save",
        "before_pdf_export",
        "after_pdf_export",
        "after_drawing.finalize_drawing#1",
    ]
    for index in (1, 2):
        assert labels.count(f"before_drawing.add_property_linked_note#{index}") == 1
        assert labels.count(f"after_drawing.add_property_linked_note#{index}") == 1
    by_label = {row["boundary"]: row for row in rows}
    assert by_label["before_drawing.add_surface_finish#1"]["drawing"] == {
        "lower_text": "fit"
    }
    assert by_label["after_drawing.add_surface_finish#1"]["drawing"] == {
        "lower_text": ""
    }
    assert all(row["raw_system_values"] == (0.008000000001785,) for row in rows)
    assert len(bank.saved) == 25
    assert all(
        getattr(bank.module, name) is original for name, original in r.originals.items()
    )
    assert control.drawing.save_drawing is bank.save


@pytest.mark.asyncio
async def test_async_primary_and_post_read_error_survive_with_all_aliases_restored(
    remaining,
):
    r, bank = remaining, remaining.bank
    primary = RuntimeError("async native finalize failed")
    getter_failure = RuntimeError("post-finalize drawing getter failed")

    async def fail(*args, **kwargs):
        bank.observer.drawing_reader.side_effect = getter_failure
        raise primary

    bank.module.finalize_drawing = fail
    with pytest.raises(RuntimeError, match="async native finalize failed") as caught:
        with bank.observer.observe():
            bank.module.set_dimension_callouts(bank.adapter, [], {})
            bank.module.set_dimension_precision(bank.adapter, [], {})
            for name in r.names[:-1]:
                getattr(bank.module, name)(bank.adapter, r.arg, native_option=r.keyword)
            await bank.module.finalize_drawing(bank.adapter)
    assert caught.value is primary
    assert "post-finalize drawing getter failed" in primary.__notes__[0]
    assert bank.module.finalize_drawing is fail
    assert all(
        getattr(bank.module, name) is original
        for name, original in r.originals.items()
        if name != "finalize_drawing"
    )
    assert bank.module.set_dimension_callouts is bank.callouts
    assert control.drawing.save_drawing is bank.save
    last = bank.saved[-1]["source_boundaries"]
    assert last["banks"][-1]["boundary"] == "after_drawing.finalize_drawing#1"
    assert "post-finalize drawing getter failed" in last["banks"][-1]["error"]
    assert last["operation_errors"][-1] == {
        "boundary": "drawing.finalize_drawing#1",
        "error": repr(primary),
    }


@pytest.mark.parametrize(
    "mode",
    [
        "missing",
        "sync_finalize",
        "async_sync",
        "wrong_adapter",
        "wrong_order",
        "missing_use",
    ],
)
def test_selected_extra_scope_refuses_missing_changed_or_incomplete_calls(
    remaining, mode
):
    r, bank = remaining, remaining.bank
    if mode == "missing":
        del bank.module.add_surface_finish
    if mode == "sync_finalize":
        bank.module.finalize_drawing = lambda *args: None
    if mode == "async_sync":

        async def changed(*args):
            pass

        bank.module.auto_center_marks = changed
    with pytest.raises(RuntimeError):
        with bank.observer.observe():
            bank.module.set_dimension_callouts(bank.adapter, [], {})
            bank.module.set_dimension_precision(bank.adapter, [], {})
            if mode == "wrong_adapter":
                bank.module.auto_center_marks(object(), r.arg, native_option=r.keyword)
            if mode == "wrong_order":
                bank.module.add_datum_feature(
                    bank.adapter, r.arg, native_option=r.keyword
                )
            if mode == "missing_use":
                bank.observer.stages.extend(("native_save", "pdf_export"))
                bank.observer.require_used()
    assert r.calls == []
    assert bank.module.set_dimension_callouts is bank.callouts
    assert control.drawing.save_drawing is bank.save


def test_default_observer_never_reads_or_patches_remaining_aliases(bank):
    class GuardedModule:
        def __getattr__(self, name):
            if name in ("set_dimension_callouts", "set_dimension_precision", "OUTPUTS"):
                return getattr(bank.module, name)
            raise AssertionError(f"default observer accessed extra helper {name}")

    bank.observer.module = GuardedModule()
    with bank.observer.observe():
        bank.observer.module.set_dimension_callouts(bank.adapter, [], {})
        bank.observer.module.set_dimension_precision(bank.adapter, [], {})
        control.drawing.save_drawing(
            bank.adapter,
            str(bank.outputs.slddrw),
            pdf_path=str(bank.outputs.pdf),
            artifact_context=bank.artifact,
        )
    bank.observer.require_used()
    assert len(bank.saved) == 9
    assert bank.observer.stages == list(control.STAGES)


def test_sync_error_keeps_primary_and_restores_exact_selected_alias(remaining):
    r, bank = remaining, remaining.bank
    primary = RuntimeError("native center marks failed")
    failure = Mock(side_effect=primary)
    bank.module.auto_center_marks = failure
    with pytest.raises(RuntimeError, match="native center marks failed") as caught:
        with bank.observer.observe():
            bank.module.set_dimension_callouts(bank.adapter, [], {})
            bank.module.set_dimension_precision(bank.adapter, [], {})
            bank.module.auto_center_marks(bank.adapter, r.arg, native_option=r.keyword)
    assert caught.value is primary
    failure.assert_called_once_with(bank.adapter, r.arg, native_option=r.keyword)
    assert bank.module.auto_center_marks is failure
    assert (
        bank.saved[-1]["source_boundaries"]["banks"][-1]["boundary"]
        == "after_drawing.auto_center_marks#1"
    )
    assert control.drawing.save_drawing is bank.save


@pytest.mark.asyncio
@pytest.mark.parametrize("selection", ["valid", "wrong_entity"])
async def test_real_entity_and_source_observers_compose_in_actual_pilot_scope(
    remaining, monkeypatch, selection
):
    from diagnostics import probe_datum_policy_recipes as pilot
    from diagnostics import _owned_native_documents as owned
    from diagnostics._recipe_view_entity_acceptance import ViewEntityAcceptance
    from solidworks_mcp.adapters.solidworks import drawing as native_drawing
    from test_view_recipe_acceptance_drawing import bank as view_bank

    r, bank = remaining, remaining.bank
    view = view_bank.__wrapped__(monkeypatch)
    model, app = view.adapter.currentModel, bank.adapter.swApp
    documents = []
    for document, path, kind in (
        (bank.source, str(bank.path), 1),
        (model, "", 3),
    ):
        document.path = path
        document.GetPathName = lambda document=document: document.path
        document.GetTitle = lambda document=document: (
            Path(document.path).name if document.path else "Owned unsaved drawing"
        )
        document.GetType = lambda kind=kind: kind
        document.Visible = True
    model.GetSaveFlag = lambda: not bool(model.path)
    model.GetViews = lambda: ((object(),),)
    app.GetDocuments = lambda: tuple(documents)
    app.GetOpenDocumentByName = lambda path: next(
        (document for document in documents if document.path == str(path)), None
    )
    app.ActiveDoc = bank.adapter.currentModel = None

    async def open_source(path):
        assert Path(path) == bank.path
        documents.append(bank.source)
        app.ActiveDoc = bank.adapter.currentModel = bank.source
        return NS(is_success=True, data={})

    bank.adapter.open_model = open_source
    monkeypatch.setattr(owned, "_early_bound", lambda value, _: value)
    ledger = bank.adapter.ownership = owned.DiagnosticDocuments(bank.adapter)
    ledger.register_directory(bank.path.parent)
    await ledger.open_model(str(bank.path))
    with ledger.creating_document(owned.DocumentKind.DRAWING, bank.outputs.slddrw):
        documents.append(model)
        app.ActiveDoc = model
        ledger.assign_current(model)
    original_record = ledger.assert_current_owned()
    save_scopes = Mock(wraps=ledger.saving_as)
    monkeypatch.setattr(ledger, "saving_as", save_scopes)

    def native_save(adapter, path, *, pdf_path, artifact_context):
        @contextmanager
        def artifact(kind, target):
            with artifact_context(kind, target):
                yield
                if kind == "drawing":
                    model.path = target
            assert ledger.assert_current_owned() is original_record

        return bank.save(adapter, path, pdf_path=pdf_path, artifact_context=artifact)

    monkeypatch.setattr(native_drawing, "save_drawing", native_save)
    for name, original in view.originals.items():
        setattr(bank.module, name, original)
    entity = ViewEntityAcceptance(bank.module, view.manifest)
    if selection == "wrong_entity":
        view.manager.GetSelectedObject6 = lambda *_: object()

    async def build(adapter):
        bank.module.set_dimension_callouts(adapter, [], {})
        bank.module.set_dimension_precision(adapter, [], {})
        for name in r.names[:2]:
            getattr(bank.module, name)(adapter, r.arg, native_option=r.keyword)
        bank.module.add_datum_feature(adapter, view.view, label="coordinate datum")
        bank.module.add_feature_control_frame(
            adapter, view.view, label="coordinate FCF"
        )
        bank.module.add_surface_finish(
            adapter, view.view, label="finish", entity=view.entity
        )
        for _ in range(2):
            bank.module.add_property_linked_note(
                adapter, r.arg, native_option=r.keyword
            )
        return await bank.module.finalize_drawing(
            adapter, r.arg, native_option=r.keyword
        )

    bank.module.build = build
    # Execute the actual pilot's context-manager block, not a hand-copied order.
    # The two observer implementations and selection/attachment checks are real;
    # existing fixtures replace only native operations and source observations.
    scopes = [
        node
        for node in ast.walk(ast.parse(inspect.getsource(pilot.pilot)))
        if isinstance(node, ast.With)
        and {"source_boundaries", "entity_acceptance"}
        <= {
            name.id
            for item in node.items
            for name in ast.walk(item.context_expr)
            if isinstance(name, ast.Name)
        }
    ]
    assert len(scopes) == 1
    harness = ast.parse("async def run():\n    pass\n")
    harness.body[0].body = [
        deepcopy(scopes[0]),
        ast.Return(value=ast.Name(id="artifacts", ctx=ast.Load())),
    ]
    namespace = dict(
        save_control=nullcontext(),
        callout_control=None,
        source_boundaries=bank.observer,
        entity_acceptance=entity,
        adapter=bank.adapter,
        entity_handles=None,
        module=bank.module,
        build_kwargs={},
        nullcontext=nullcontext,
        patch=pilot.patch,
        owned_save_drawing=pilot.owned_save_drawing,
    )
    exec(
        compile(ast.fix_missing_locations(harness), "<pilot observer scope>", "exec"),
        namespace,
    )
    if selection == "valid":
        result = await namespace["run"]()
        assert result is r.returns["finalize_drawing"]
        bank.observer.require_used()
        entity.require_coverage()
        assert set(entity.coordinate) == {"coordinate datum", "coordinate FCF"}
        assert set(entity.selected) == set(entity.recorded) == {"finish"}
        assert [row["stage"] for row in entity.context_report["stages"]] == [
            "selected",
            "inserted",
        ]
        assert len(bank.trial["source_boundaries"]["banks"]) == 25
        save_scopes.assert_called_once_with(str(bank.outputs.slddrw))
        assert ledger.assert_current_owned() is original_record
        assert original_record.state["path"] == str(bank.outputs.slddrw)
    if selection == "wrong_entity":
        with pytest.raises(RuntimeError, match="VIEW argument/actual selection"):
            await namespace["run"]()
        assert (
            bank.saved[-1]["source_boundaries"]["banks"][-1]["boundary"]
            == "after_drawing.add_surface_finish#1"
        )
        assert entity.recorded == {}
        save_scopes.assert_not_called()
    for name, original in view.originals.items():
        assert getattr(bank.module, name) is original
        assert getattr(control.drawing, name) is original
    assert control.drawing._select_annotation_entity is view.selected
    assert control.drawing.save_drawing is bank.save
