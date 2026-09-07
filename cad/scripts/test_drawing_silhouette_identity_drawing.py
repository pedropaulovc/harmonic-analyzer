"""Native drawing persistent-ID predicate, not wrapper or byte equality."""

from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

import _drawing_silhouette_identity as identity
from test_annotation_attachment_context_drawing import bank as bank, validate


@pytest.fixture
def scene(monkeypatch):
    monkeypatch.setattr(identity, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(identity, "byte_variant", lambda value: value)
    expected, actual = object(), object()
    reference = memoryview(bytes(index % 256 for index in range(1239)))
    extension = NS(
        GetPersistReference3=Mock(return_value=reference),
        IsSamePersistentID=Mock(return_value=1),
    )
    model = NS(GetType=lambda: 3, Extension=extension)
    return NS(**locals())


def test_native_comparator_is_mandatory_even_for_byte_identical_or_identical_handles(
    scene,
):
    evidence = {}
    identity.require_same(
        scene.model,
        scene.expected,
        scene.actual,
        label="view silhouette",
        evidence=evidence,
    )
    assert scene.extension.GetPersistReference3.call_args_list[0].args == (
        scene.expected,
    )
    assert scene.extension.GetPersistReference3.call_args_list[1].args == (
        scene.actual,
    )
    assert evidence["expected"]["return_type"] == "builtins.memoryview"
    assert len(evidence["expected"]["reference"]) == 1239
    assert evidence["native_result"] == 1
    scene.extension.IsSamePersistentID.return_value = 0
    with pytest.raises(RuntimeError, match="IsSamePersistentID returned 0"):
        identity.require_same(
            scene.model, scene.expected, scene.expected, label="same handle"
        )
    assert scene.extension.IsSamePersistentID.call_count == 2


def test_different_reference_bytes_do_not_override_positive_native_predicate(scene):
    scene.extension.GetPersistReference3.side_effect = [(1, 2), (7, 8, 9)]
    identity.require_same(
        scene.model, scene.expected, scene.actual, label="view silhouette"
    )
    scene.extension.IsSamePersistentID.assert_called_once_with((1, 2), (7, 8, 9))


@pytest.mark.parametrize("result", [0, -1, 2, True, False, 1.0, "1", None])
def test_different_unknown_or_malformed_native_comparison_is_never_coerced(
    scene, result
):
    scene.extension.IsSamePersistentID.return_value = result
    evidence = {}
    with pytest.raises(RuntimeError, match="IsSamePersistentID"):
        identity.require_same(
            scene.model,
            scene.expected,
            scene.actual,
            label="view silhouette",
            evidence=evidence,
        )
    assert evidence["native_result"] is result


@pytest.mark.parametrize("kind", [1, 2, 0, True, 3.0, "3", None])
def test_wrong_document_context_fails_before_any_reference_query(scene, kind):
    scene.model.GetType = lambda: kind
    with pytest.raises(RuntimeError, match="requires a drawing"):
        identity.require_same(
            scene.model, scene.expected, scene.actual, label="view silhouette"
        )
    scene.extension.GetPersistReference3.assert_not_called()
    scene.extension.IsSamePersistentID.assert_not_called()


@pytest.mark.parametrize(
    "raw", [None, (), "a", (True,), (1.0,), (-1,), (256,), ((1, 2),)]
)
def test_invalid_reference_stops_without_native_comparison(scene, raw):
    scene.extension.GetPersistReference3.return_value = raw
    evidence = {}
    with pytest.raises(RuntimeError, match="native persistent reference"):
        identity.require_same(
            scene.model,
            scene.expected,
            scene.actual,
            label="view silhouette",
            evidence=evidence,
        )
    assert "error" in evidence["expected"]
    scene.extension.IsSamePersistentID.assert_not_called()


@pytest.mark.parametrize("phase", ["first_reference", "second_reference", "compare"])
def test_partial_native_errors_retain_completed_reference_evidence(scene, phase):
    if phase == "first_reference":
        scene.extension.GetPersistReference3.side_effect = RuntimeError(
            "first reference"
        )
    if phase == "second_reference":
        scene.extension.GetPersistReference3.side_effect = [
            scene.reference,
            RuntimeError("second reference"),
        ]
    if phase == "compare":
        scene.extension.IsSamePersistentID.side_effect = RuntimeError("native compare")
    evidence = {}
    with pytest.raises(RuntimeError):
        identity.require_same(
            scene.model,
            scene.expected,
            scene.actual,
            label="view silhouette",
            evidence=evidence,
        )
    if phase == "first_reference":
        assert "first reference" in evidence["expected"]["error"]
    if phase == "second_reference":
        assert len(evidence["expected"]["reference"]) == 1239
        assert "second reference" in evidence["actual"]["error"]
    if phase == "compare":
        assert "native compare" in evidence["native_error"]
        assert len(evidence["actual"]["reference"]) == 1239


@pytest.mark.parametrize("side", ["expected", "actual"])
def test_null_silhouette_rejected_before_any_native_query(scene, side):
    setattr(scene, side, None)
    with pytest.raises(RuntimeError, match="null silhouette"):
        identity.require_same(
            scene.model, scene.expected, scene.actual, label="view silhouette"
        )
    scene.extension.GetPersistReference3.assert_not_called()


def test_real_ui1_variant_contains_exact_unsigned_bytes_without_com_calls():
    pythoncom = pytest.importorskip("pythoncom")
    pytest.importorskip("win32com.client")
    variant = identity.byte_variant((0, 127, 128, 255))
    assert variant.varianttype == pythoncom.VT_ARRAY | pythoncom.VT_UI1
    assert tuple(variant.value) == (0, 127, 128, 255)


@pytest.mark.parametrize("result", [1, 0, -1])
def test_explicit_production_silhouette_uses_drawing_predicate_not_direct_handle(
    bank, result
):
    bank.annotation.GetAttachedEntityTypes = lambda: (46,)
    bank.current.Extension.GetPersistReference3 = Mock(
        return_value=memoryview(b"opaque drawing ID")
    )
    bank.current.Extension.IsSamePersistentID = Mock(return_value=result)
    # Separate wrappers reproduce the native IsSame0 / drawing PID1 positive.
    expected = object()
    assert bank.adapter.swApp.IsSame(expected, bank.view_entity) == 0
    if result == 1:
        validate(bank, "view", expected=expected, entity_type="SILHOUETTE")
    else:
        with pytest.raises(RuntimeError, match="IsSamePersistentID"):
            validate(bank, "view", expected=expected, entity_type="SILHOUETTE")
    bank.current.Extension.IsSamePersistentID.assert_called_once()
    bank.reverse.assert_not_called()


@pytest.mark.parametrize("kind,native_kind", [("EDGE", 1), ("FACE", 2)])
def test_edge_and_face_never_call_persistent_identity(bank, kind, native_kind):
    bank.annotation.GetAttachedEntityTypes = lambda: (native_kind,)
    bank.current.Extension.GetPersistReference3 = Mock(
        side_effect=AssertionError("not a silhouette")
    )
    validate(bank, "view", expected=bank.view_entity, entity_type=kind)
    bank.current.Extension.GetPersistReference3.assert_not_called()


def test_wrong_annotation_view_rejects_before_drawing_persistent_query(bank):
    bank.annotation.GetAttachedEntityTypes = lambda: (46,)
    bank.annotation.Owner = object()
    bank.current.Extension.GetPersistReference3 = Mock()
    with pytest.raises(RuntimeError, match="owning view"):
        validate(bank, "view", expected=bank.view_entity, entity_type="SILHOUETTE")
    bank.current.Extension.GetPersistReference3.assert_not_called()
