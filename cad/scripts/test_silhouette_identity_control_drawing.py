from types import SimpleNamespace as NS
import asyncio
from unittest.mock import Mock

import pytest

from diagnostics import _silhouette_identity_control as control
from diagnostics import _recipe_view_entity_acceptance as observer
from diagnostics import _silhouette_attachment_witness as silhouette
from diagnostics._recipe_view_roles import ViewRole, ViewResolver
from test_owned_native_documents_drawing import Model, facade, native as native
from test_silhouette_attachment_witness_drawing import fixture as silhouette_fixture
from test_view_recipe_acceptance_drawing import bank as view_bank


@pytest.mark.parametrize("raw", [None, (), [], "abc", (True,), (-1,), (256,), (1.0,)])
def test_bad_native_references_rejected(raw):
    with pytest.raises(RuntimeError, match="native persistent reference"):
        control._byte_reference(raw)


def test_literal_byte_references_and_native_comparisons(monkeypatch):
    monkeypatch.setattr(control, "_variant", lambda value: value)
    calls = []

    def compare(first, second):
        calls.append((first, second))
        return int(first == second)

    extension = NS(GetPersistReference3=lambda value: value, IsSamePersistentID=compare)
    records = {}
    control.persistent_controls(extension, {
        "expected": (1, 2), "selected": (1, 2), "selected_again": (1, 2),
        "expected_face": (3,), "selected_face": (4,),
    }, records)
    assert records["expected"] == {"value": (1, 2)}
    assert records["compare.expected.selected"] == {"value": 1}
    assert records["compare.expected_face.selected_face"] == {"value": 0}
    assert len(calls) == 5


def test_missing_reference_never_becomes_a_comparison(monkeypatch):
    def compare(*unused):
        pytest.fail("missing native IDs must not be compared")

    extension = NS(GetPersistReference3=lambda value: None, IsSamePersistentID=compare)
    records = {}
    control.persistent_controls(extension, {"expected": object()}, records)
    assert "empty" in records["expected"]["error"]
    assert records["compare.expected.selected"] == {"status": "missing_reference"}


def test_capture_never_drives_unowned_document_or_replaces_original_error():
    def deny():
        raise RuntimeError("not owned")

    records = {}
    control.capture(NS(ownership=NS(assert_current_owned=deny)), None, None, None, records)
    assert records == {"persistent_identity_control": {"capture_error": "RuntimeError('not owned')"}}


@pytest.fixture
def owned_scene(native, monkeypatch):
    """Real ownership/observer contexts; only the native COM objects are doubled."""
    monkeypatch.setattr(control, "_early_bound", lambda obj, _: obj)
    monkeypatch.setattr(silhouette, "_early_bound", lambda obj, _: obj)
    monkeypatch.setattr(control, "_variant", lambda value: value)
    bank = view_bank.__wrapped__(monkeypatch)
    user = Model(None, title="Unrelated dirty drawing", dirty=True)
    native.app.documents.append(user)
    native.app.ActiveDoc = user
    adapter = facade(native)
    part_path = native.directory / "owned-source.SLDPRT"
    part_path.write_bytes(b"owned source bytes")
    asyncio.run(adapter.open_model(str(part_path)))
    source = adapter.currentModel
    asyncio.run(adapter.open_model(str(native.copy)))
    drawing = adapter.currentModel
    drawing.references = [source]
    drawing.SelectionManager = bank.manager
    drawing.GetCurrentSheet = bank.adapter.currentModel.GetCurrentSheet
    bank.view.ReferencedDocument = source
    bank.view.ReferencedConfiguration = "Default"
    bank.adapter = adapter
    _, _, expected, face, *_ = silhouette_fixture()
    expected.GetView = lambda: bank.view
    selected = NS(**vars(expected))
    bank.view.entity = bank.entity = expected
    bank.manager.GetSelectedObjectType3 = lambda *_: 46
    bank.manager.GetSelectedObject6 = Mock(return_value=selected)
    bank.manifest.view_roles = {"finish": ViewRole("*Front", 7, "SILHOUETTE", ViewResolver.BORE)}
    bank.witness = observer.ViewEntityAcceptance(bank.module, bank.manifest)
    calls = []
    state = NS(failure=None, source_effect="unchanged")

    def extension(scope, model):
        def reference(entity):
            calls.append((scope, "reference", entity))
            if scope == "source" and state.source_effect == "dirty":
                model.dirty = True
            if state.failure == (scope, "reference"):
                raise RuntimeError(f"{scope} native reference failed")
            if entity is expected or entity is selected:
                return (11, 22)
            assert entity is face
            return (33, 44)

        def compare(first, second):
            calls.append((scope, "compare", first, second))
            if state.failure == (scope, "compare"):
                raise RuntimeError(f"{scope} native comparison failed")
            return int(first == second)

        return NS(GetPersistReference3=reference, IsSamePersistentID=compare)

    for scope, model in (("drawing", drawing), ("source", source)):
        model.Extension = extension(scope, model)
        for name in ("Save3", "EditRebuild3", "ForceRebuild3", "ClearSelection2", "GraphicsRedraw2"):
            setattr(model, name, Mock(side_effect=AssertionError(f"unexpected {name}")))
    return NS(**locals())


def assert_owned_cleanup(scene):
    asyncio.run(scene.adapter.close_owned_documents())
    assert scene.native.app.documents == [scene.user]
    assert scene.user.dirty and scene.user.Visible and scene.user.path == ""
    assert scene.part_path.read_bytes() == b"owned source bytes"
    assert scene.native.copy.read_bytes() == b"copy"
    assert scene.native.source.read_bytes() == b"original"
    for model in (scene.drawing, scene.source):
        for name in ("Save3", "EditRebuild3", "ForceRebuild3", "ClearSelection2", "GraphicsRedraw2"):
            getattr(model, name).assert_not_called()


@pytest.mark.parametrize("source_effect", ["unchanged", "dirty"])
def test_full_owned_capture_retains_both_document_ids_comparisons_and_observed_dirty_flags(
    owned_scene, source_effect
):
    scene = owned_scene
    scene.state.source_effect = source_effect
    evidence = {}
    control.capture(scene.adapter, scene.bank.view, scene.expected, scene.selected, evidence)
    rows = evidence["persistent_identity_control"]
    assert "capture_error" not in rows
    assert rows["repeated_selection_same"] == 1
    for scope in ("drawing", "source"):
        row = rows[scope]
        assert row["dirty_before"] is False
        assert row["dirty_after"] is (scope == "source" and source_effect == "dirty")
        assert row["expected"] == row["selected"] == row["selected_again"] == {"value": (11, 22)}
        assert row["expected_face"] == row["selected_face"] == {"value": (33, 44)}
        assert all(row[key] == {"value": 1} for key in row if key.startswith("compare."))
    assert len(scene.calls) == 20
    assert scene.adapter.currentModel is scene.native.app.ActiveDoc is scene.drawing
    scene.bank.manager.GetSelectedObject6.assert_called_once_with(1, -1)
    assert_owned_cleanup(scene)


def test_accepted_native_identity_never_calls_failure_only_control(owned_scene, monkeypatch):
    scene = owned_scene
    capture = Mock(side_effect=AssertionError("successful selection must not query persistent IDs"))
    monkeypatch.setattr(control, "capture", capture)
    scene.bank.manager.GetSelectedObject6.return_value = scene.expected
    with scene.bank.witness.observe(scene.adapter):
        scene.bank.module.add_surface_finish(
            scene.adapter, scene.bank.view, label="finish",
            entity=scene.expected, entity_type="SILHOUETTE",
        )
    capture.assert_not_called()
    assert scene.calls == []
    assert set(scene.bank.witness.recorded) == {"finish"}
    assert all("persistent_identity_control" not in row for row in scene.bank.witness.context_report["stages"])
    assert_owned_cleanup(scene)


def test_source_dirty_before_precedes_drawing_context_persistent_queries(owned_scene):
    scene = owned_scene
    original = scene.drawing.Extension.GetPersistReference3

    def query(entity):
        scene.source.dirty = True
        return original(entity)

    scene.drawing.Extension.GetPersistReference3 = query
    evidence = {}
    control.capture(scene.adapter, scene.bank.view, scene.expected, scene.selected, evidence)
    row = evidence["persistent_identity_control"]["source"]
    assert row["dirty_before"] is False and row["dirty_after"] is True
    assert_owned_cleanup(scene)


@pytest.mark.parametrize("operation", ["repeated_selection", "get_face"])
def test_partial_capture_keeps_both_dirty_brackets_before_first_entity_query(owned_scene, operation):
    scene = owned_scene

    def query(*args):
        scene.source.dirty = scene.drawing.dirty = True
        raise RuntimeError(f"{operation} failed after dirtying documents")

    if operation == "repeated_selection":
        scene.bank.manager.GetSelectedObject6.side_effect = query
    else:
        scene.expected.GetFace = query
    evidence = {}
    control.capture(scene.adapter, scene.bank.view, scene.expected, scene.selected, evidence)
    rows = evidence["persistent_identity_control"]
    assert operation in rows["capture_error"]
    assert rows["drawing"] == rows["source"] == {"dirty_before": False, "dirty_after": True}
    assert scene.calls == []
    assert_owned_cleanup(scene)


def test_partial_capture_retains_final_dirty_read_error_without_masking_primary(owned_scene):
    scene = owned_scene
    original = scene.source.GetSaveFlag
    state = NS(read="unarmed")

    def query(*args):
        state.read = "armed"
        raise RuntimeError("primary native query failure")

    def dirty():
        if state.read == "armed":
            state.read = "observed"
            raise RuntimeError("final dirty read failure")
        return original()

    scene.bank.manager.GetSelectedObject6.side_effect = query
    scene.source.GetSaveFlag = dirty
    evidence = {}
    control.capture(scene.adapter, scene.bank.view, scene.expected, scene.selected, evidence)
    rows = evidence["persistent_identity_control"]
    assert rows["capture_error"] == "RuntimeError('primary native query failure')"
    assert rows["drawing"] == {"dirty_before": False, "dirty_after": False}
    assert rows["source"] == {"dirty_before": False, "dirty_after_error": "RuntimeError('final dirty read failure')"}
    assert scene.calls == []
    scene.source.GetSaveFlag = original
    assert_owned_cleanup(scene)


def test_partial_capture_keeps_final_owned_active_guard_without_masking_primary(owned_scene):
    scene = owned_scene

    def query(*args):
        scene.native.app.ActiveDoc = scene.user
        raise RuntimeError("primary native selection failed")

    scene.bank.manager.GetSelectedObject6.side_effect = query
    evidence = {}
    control.capture(scene.adapter, scene.bank.view, scene.expected, scene.selected, evidence)
    rows = evidence["persistent_identity_control"]
    assert rows["capture_error"] == "RuntimeError('primary native selection failed')"
    assert "final_ownership_error" in rows
    assert rows["drawing"] == rows["source"] == {"dirty_before": False, "dirty_after": False}
    assert scene.calls == []
    scene.native.app.ActiveDoc = scene.drawing
    assert_owned_cleanup(scene)


@pytest.mark.parametrize("failure", [None, ("source", "reference"), ("drawing", "compare"), "selection"])
def test_real_failure_hook_retains_controls_and_original_strict_identity_rejection(
    owned_scene, monkeypatch, failure
):
    scene = owned_scene
    primary = []
    require_same = silhouette.require_same

    def rejecting(*args, **kwargs):
        try:
            return require_same(*args, **kwargs)
        except RuntimeError as error:
            primary.append(error)
            raise

    monkeypatch.setattr(silhouette, "require_same", rejecting)
    if failure == "selection":
        scene.bank.manager.GetSelectedObject6.side_effect = [scene.selected, RuntimeError("native repeated selection failed")]
    else:
        scene.state.failure = failure
    with pytest.raises(RuntimeError, match=r"VIEW selection silhouette entity.*returned 0") as caught:
        with scene.bank.witness.observe(scene.adapter):
            scene.bank.module.add_surface_finish(
                scene.adapter, scene.bank.view, label="finish",
                entity=scene.expected, entity_type="SILHOUETTE",
            )
    assert len(primary) == 1 and caught.value is primary[0]
    row = scene.bank.witness.context_report["stages"][-1]
    assert row["error"] == repr(primary[0])
    assert row["silhouette"]["expected"] == row["silhouette"]["actual"]
    records = row["persistent_identity_control"]
    if failure == "selection":
        assert records == {
            "capture_error": "RuntimeError('native repeated selection failed')",
            "drawing": {"dirty_before": False, "dirty_after": False},
            "source": {"dirty_before": False, "dirty_after": False},
        }
        assert scene.calls == []
    else:
        assert records["source"]["dirty_before"] is records["source"]["dirty_after"] is False
        if failure is None:
            assert records["drawing"]["compare.expected.selected"] == {"value": 1}
            assert records["source"]["compare.expected.selected"] == {"value": 1}
        if failure == ("source", "reference"):
            assert "native reference failed" in records["source"]["expected"]["error"]
            assert records["source"]["compare.expected.selected"] == {"status": "missing_reference"}
        if failure == ("drawing", "compare"):
            assert "native comparison failed" in records["drawing"]["compare.expected.selected"]["error"]
            assert records["source"]["compare.expected.selected"] == {"value": 1}
    assert scene.bank.witness.recorded == scene.bank.witness.selected == {}
    assert scene.bank.annotations == {}
    assert observer.drawing._select_annotation_entity is scene.bank.selected
    assert scene.bank.module.add_surface_finish is scene.bank.originals["add_surface_finish"]
    assert_owned_cleanup(scene)
