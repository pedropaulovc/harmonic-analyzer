from types import SimpleNamespace as NS
import asyncio
import json
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


@pytest.mark.parametrize("buffer", [bytes(range(20)), bytearray(range(20))])
def test_native_unsigned_byte_memoryview_references_are_decoded_without_unwrapping(buffer):
    raw = memoryview(buffer)
    assert raw.format == "B" and raw.ndim == 1 and raw.itemsize == 1 and raw.contiguous
    assert control._byte_reference(raw) == tuple(range(20))


def released_memoryview():
    raw = memoryview(b"abc")
    raw.release()
    return raw


@pytest.mark.parametrize("make", [
    lambda: memoryview(b""),
    lambda: memoryview(b"abcd").cast("B", shape=(2, 2)),
    lambda: memoryview(b"a").cast("B", shape=()),
    lambda: memoryview(control.array("I", [1, 2])),
    lambda: memoryview(control.array("b", [1, 2])),
    lambda: memoryview(b"ab").cast("c"),
    lambda: memoryview(b"abcd")[::2],
    released_memoryview,
])
def test_malformed_memoryview_reference_rejected(make):
    with pytest.raises(RuntimeError, match="native persistent reference"):
        control._byte_reference(make())


def test_released_memoryview_retains_raw_type_and_observation_error():
    records = {}
    control.persistent_controls(NS(GetPersistReference3=lambda _: released_memoryview()),
                                {"expected": object()}, records)
    assert records["raw_returns"]["expected"]["type"] == "builtins.memoryview"
    assert "observation_error" in records["raw_returns"]["expected"]
    assert "native persistent reference" in records["expected"]["error"]
    assert records["compare.expected.expected"] == {"status": "missing_reference"}


def test_owned_hook_and_both_contexts_use_native_memoryview_references(owned_scene):
    scene = owned_scene
    feature = NS(Name="Hook", GetTypeName2=lambda: "Sweep")
    scene.source.FeatureByName = Mock(return_value=feature)
    for model in (scene.drawing, scene.source):
        original = model.Extension.GetPersistReference3
        model.Extension.GetPersistReference3 = (
            lambda entity, read=original: memoryview(bytes(range(20)))
            if entity is feature else memoryview(bytes(read(entity)))
        )
    resolver = scene.source.Extension.GetObjectByPersistReference3 = Mock(return_value=(feature, 0))
    evidence = {}
    control.capture(scene.adapter, scene.bank.view, scene.expected, scene.selected, evidence)
    rows = evidence["persistent_identity_control"]
    for scope in ("drawing", "source"):
        assert rows[scope]["expected"] == {"value": (11, 22)}
        assert rows[scope]["compare.expected.selected"] == {"value": 1}
        assert rows[scope]["raw_returns"]["expected"] == {
            "type": "builtins.memoryview", "value": [11, 22],
            "element_types": ["builtins.int", "builtins.int"], "format": "B", "shape": [2],
        }
    assert rows["source_feature_control"]["status"] == "passed"
    assert rows["source_feature_control"]["reference"] == tuple(range(20))
    resolver.assert_called_once_with(tuple(range(20)))
    assert scene.adapter.currentModel is scene.native.app.ActiveDoc is scene.drawing
    assert_owned_cleanup(scene)


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


@pytest.mark.parametrize("raw", [None, (), (1, 2, 255), bytearray((1, 2)), [[1, 2]], "native text", False])
def test_raw_return_shape_survives_before_unchanged_reference_validation(raw):
    extension = NS(GetPersistReference3=lambda _: raw, IsSamePersistentID=lambda *_: 1)
    records = {}
    control.persistent_controls(extension, {"expected": object()}, records)
    observation = records["raw_returns"]["expected"]
    assert observation["type"] == f"{type(raw).__module__}.{type(raw).__qualname__}"
    json.dumps(observation, allow_nan=False)
    if type(raw) is tuple and raw:
        assert observation["value"] == [1, 2, 255]
        assert records["expected"] == {"value": raw}
    else:
        assert "error" in records["expected"]
        assert records["compare.expected.selected"] == {"status": "missing_reference"}
    if type(raw) is bytearray:
        assert observation["value"] == [1, 2]


def test_real_variant_metadata_is_observed_but_never_unwrapped_into_accepted_bytes():
    client = pytest.importorskip("win32com.client")
    pythoncom = pytest.importorskip("pythoncom")
    raw = client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_UI1, (1, 2, 255))
    extension = NS(GetPersistReference3=lambda _: raw)
    records = {}
    control.persistent_controls(extension, {"expected": object()}, records)
    observed = records["raw_returns"]["expected"]
    assert observed["type"] == "win32com.client.VARIANT"
    assert observed["variant_type"] == pythoncom.VT_ARRAY | pythoncom.VT_UI1
    assert observed["value"]["value"] == [1, 2, 255]
    assert "wrong type" in records["expected"]["error"]
    assert records["compare.expected.expected"] == {"status": "missing_reference"}
    json.dumps(observed, allow_nan=False)


def test_fake_variant_attributes_are_not_treated_as_native_variant():
    class NotVariant:
        @property
        def value(self):
            pytest.fail("do not guess a VARIANT by its attributes")

        @property
        def varianttype(self):
            pytest.fail("do not guess a VARIANT by its attributes")

    raw = NotVariant()
    observation = control._raw_return(raw)
    assert observation["encoding"] == "unsupported_object_repr"
    assert "variant_type" not in observation


@pytest.mark.parametrize("raw", [float("nan"), float("inf"), memoryview(b"abc"), {"nested": (True, 1.5, None)}])
def test_reference_shapes_remain_complete_json_safe_observations(raw):
    observed = control._raw_return(raw)
    assert observed["type"] == f"{type(raw).__module__}.{type(raw).__qualname__}"
    json.dumps(observed, allow_nan=False)


@pytest.mark.parametrize("outcome", ["passed", "missing", "wrong_name", "wrong_type", "empty_reference", "status_error", "wrong_object", "wrong_shape", "unknown_self", "borrowed"])
def test_owned_source_hook_feature_positive_control_uses_exact_handle_and_round_trip(owned_scene, outcome):
    from diagnostics._owned_native_documents import Ownership

    scene = owned_scene
    feature = NS(Name="Hook", GetTypeName2=lambda: "Sweep")
    scene.source.FeatureByName = Mock(return_value=feature)
    reference = (9, 8, 7)
    original_reference = scene.source.Extension.GetPersistReference3
    feature_reads = []

    def get_reference(entity):
        if entity is feature:
            feature_reads.append(entity)
            return None if outcome == "empty_reference" else reference
        return original_reference(entity)

    scene.source.Extension.GetPersistReference3 = get_reference
    returned = (feature, 0)
    if outcome == "status_error":
        returned = feature, 1
    if outcome == "wrong_object":
        returned = object(), 0
    if outcome == "wrong_shape":
        returned = [feature, 0]
    resolver = scene.source.Extension.GetObjectByPersistReference3 = Mock(return_value=returned)
    if outcome == "missing":
        scene.source.FeatureByName.return_value = None
    if outcome == "wrong_name":
        feature.Name = "OtherFeature"
    if outcome == "wrong_type":
        feature.GetTypeName2 = lambda: "ProfileFeature"
    if outcome == "unknown_self":
        scene.source.Extension.IsSamePersistentID = lambda *_: -1
    source_record = scene.adapter.ownership._record(scene.source)
    if outcome == "borrowed":
        source_record.ownership = Ownership.REFERENCE
    records = {}
    control._source_feature_control(scene.adapter, scene.source, records)
    row = records["source_feature_control"]
    assert row["status"] == ("passed" if outcome == "passed" else "failed")
    assert row["name"] == "Hook" and row["context"] == "source"
    assert scene.adapter.currentModel is scene.native.app.ActiveDoc is scene.drawing
    if outcome == "borrowed":
        scene.source.FeatureByName.assert_not_called()
        source_record.ownership = Ownership.COPY
    else:
        scene.source.FeatureByName.assert_called_once_with("Hook")
    if outcome in ("missing", "wrong_name", "wrong_type", "borrowed"):
        assert feature_reads == []
        resolver.assert_not_called()
    else:
        assert feature_reads == [feature]
        assert row["native_self"] == 1
        assert "feature" in row["raw_returns"]
        if outcome == "empty_reference":
            resolver.assert_not_called()
            assert row["raw_returns"]["feature"] == {"type": "builtins.NoneType", "value": None}
        else:
            resolver.assert_called_once_with(reference)
            assert row["reference"] == reference
    if outcome == "passed":
        assert row["persistent_self"] == 1
        assert row["roundtrip"]["native_same"] == 1
        assert row["roundtrip"]["error_code"] == {"type": "builtins.int", "value": 0}
    json.dumps(records, allow_nan=False)
    assert_owned_cleanup(scene)


def test_hook_feature_queries_remain_inside_both_document_dirty_brackets(owned_scene):
    scene = owned_scene
    feature = NS(Name="Hook", GetTypeName2=lambda: "Sweep")

    def lookup(name):
        assert name == "Hook"
        scene.source.dirty = True
        return feature

    scene.source.FeatureByName = lookup
    original = scene.source.Extension.GetPersistReference3
    scene.source.Extension.GetPersistReference3 = lambda entity: (1, 2) if entity is feature else original(entity)
    scene.source.Extension.GetObjectByPersistReference3 = lambda reference: (feature, 0)
    evidence = {}
    control.capture(scene.adapter, scene.bank.view, scene.expected, scene.selected, evidence)
    rows = evidence["persistent_identity_control"]
    assert rows["source_feature_control"]["status"] == "passed"
    assert rows["source"]["dirty_before"] is False and rows["source"]["dirty_after"] is True
    assert rows["drawing"]["dirty_before"] is rows["drawing"]["dirty_after"] is False
    assert_owned_cleanup(scene)


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
    monkeypatch.setattr(silhouette.persistent, "_early_bound", lambda obj, _: obj)
    monkeypatch.setattr(silhouette.persistent, "byte_variant", lambda value: value)
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
    capture = Mock(side_effect=AssertionError("successful selection must not run failure-only controls"))
    monkeypatch.setattr(control, "capture", capture)
    scene.bank.manager.GetSelectedObject6.return_value = scene.expected
    with scene.bank.witness.observe(scene.adapter):
        scene.bank.module.add_surface_finish(
            scene.adapter, scene.bank.view, label="finish",
            entity=scene.expected, entity_type="SILHOUETTE",
        )
    capture.assert_not_called()
    assert len(scene.calls) == 6  # Two mandatory drawing PID gates, no source query.
    assert all(call[0] == "drawing" for call in scene.calls)
    assert scene.source.GetSaveFlag() is scene.drawing.GetSaveFlag() is False
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
    # The native control disproved direct IsSame0 as a silhouette rejection.
    # Keep the original failure-retention test with an actual PID0 rejection.
    original_compare = scene.drawing.Extension.IsSamePersistentID
    compared = []

    def reject_first(first, second):
        compared.append((first, second))
        if len(compared) == 1:
            scene.calls.append(("drawing", "compare", first, second))
            return 0
        return original_compare(first, second)

    scene.drawing.Extension.IsSamePersistentID = reject_first
    if failure == "selection":
        scene.bank.manager.GetSelectedObject6.side_effect = [scene.selected, RuntimeError("native repeated selection failed")]
    else:
        scene.state.failure = failure
    with pytest.raises(RuntimeError, match="VIEW selection silhouette entity.*returned 0") as caught:
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
        assert len(scene.calls) == 3  # Mandatory predicate preceded failure capture.
        assert all(call[0] == "drawing" for call in scene.calls)
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
