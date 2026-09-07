"""Native FACE placement must retain the positioned path's identity gates."""

from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

import _drawing_common as drawing
from _gtol_spec import CylinderFace
from _surface_finish import SurfaceFinishControl
from test_drawing_surface_finish_validation import _geometry
from test_native_annotation_placement_drawing import native_context


def face_context(monkeypatch):
    adapter, view, face, annotation = native_context(monkeypatch)
    annotation.OwnerType = 0
    annotation.Owner = view
    annotation.GetAttachedEntityTypes.return_value = (2,)
    # Even identical controlled-cylinder geometry cannot replace native identity.
    monkeypatch.setattr("_part_pmi._face_geometry", lambda value: _geometry(value, 10.0))
    return adapter, view, face, annotation


def finish(adapter, view, face, placement, **kwargs):
    if placement == "positioned":
        kwargs["symbol_xy"] = (0.12, 0.18)
    return drawing.add_surface_finish(
        adapter, view, entity=face, entity_type="FACE",
        control=SurfaceFinishControl("journal", 1.6, CylinderFace(10.0)),
        label="journal finish", **kwargs,
    )


@pytest.mark.parametrize("placement", ["native", "positioned"])
@pytest.mark.parametrize(
    "fault, message",
    [
        ("wrong_view", "different owning view"),
        ("missing_view", "different owning view"),
        ("sheet_owner", "owner is not a drawing view"),
        ("count_zero", "attachment mismatch"),
        ("count_two", "attachment mismatch"),
        ("wrong_kind", "attachment mismatch"),
        ("missing_kind", "attachment mismatch"),
        ("multiple_kinds", "attachment mismatch"),
        ("substituted_argument", "changed entity identity"),
        ("unknown_argument", "changed entity identity"),
    ],
)
def test_both_face_placements_reject_wrong_owner_type_count_or_original_argument(
    monkeypatch, placement, fault, message,
):
    adapter, view, selected, annotation = face_context(monkeypatch)
    original = selected
    if fault == "wrong_view":
        annotation.Owner = object()
    if fault == "missing_view":
        annotation.Owner = None
    if fault == "sheet_owner":
        annotation.OwnerType = 1
    if fault == "count_zero":
        annotation.GetAttachedEntityCount3.return_value = 0
    if fault == "count_two":
        annotation.GetAttachedEntityCount3.return_value = 2
    if fault == "wrong_kind":
        annotation.GetAttachedEntityTypes.return_value = (1,)
    if fault == "missing_kind":
        annotation.GetAttachedEntityTypes.return_value = ()
    if fault == "multiple_kinds":
        annotation.GetAttachedEntityTypes.return_value = (2, 2)
    if fault in {"substituted_argument", "unknown_argument"}:
        original = object()
    if fault == "unknown_argument":
        adapter.swApp.IsSame.side_effect = lambda a, b: -1 if a is original else int(a is b)
    with pytest.raises(RuntimeError, match=message):
        finish(adapter, view, original, placement)
    view.SelectEntity.assert_called_once_with(original, False)
    if placement == "native":
        annotation.SetPosition2.assert_not_called()
        annotation.SetLeader3.assert_not_called()
        annotation.SetLeaderAttachmentPointAtIndex.assert_not_called()


@pytest.mark.parametrize("placement", ["native", "positioned"])
def test_both_face_placements_keep_the_exact_original_face_and_owner(monkeypatch, placement):
    adapter, view, face, annotation = face_context(monkeypatch)
    result = finish(adapter, view, face, placement)
    assert result is adapter.currentModel.Extension.InsertSurfaceFinishSymbol3.return_value
    assert any(call.args == (view, view) for call in adapter.swApp.IsSame.call_args_list)
    assert any(call.args == (face, face) for call in adapter.swApp.IsSame.call_args_list)
    annotation.GetAttachedEntityTypes.assert_called_once_with()
    annotation.GetAttachedEntityCount3.assert_called_once_with()
    if placement == "native":
        annotation.SetPosition2.assert_not_called()
        annotation.SetLeader3.assert_not_called()
        annotation.SetLeaderAttachmentPointAtIndex.assert_not_called()


@pytest.mark.parametrize("fault", ["position", "empty", "dangling", "different"])
def test_native_face_keeps_its_existing_position_and_attachment_guard(monkeypatch, fault):
    adapter, view, face, annotation = face_context(monkeypatch)
    if fault == "position":
        annotation.GetPosition.return_value = (float("nan"), 0.18, 0.0)
    if fault == "empty":
        annotation.GetAttachedEntities3.return_value = ()
    if fault == "dangling":
        annotation.GetAttachedEntities3.return_value = (None,)
    if fault == "different":
        annotation.GetAttachedEntities3.return_value = (object(),)
    with pytest.raises(RuntimeError, match="native annotation"):
        finish(adapter, view, face, "native")
    annotation.SetPosition2.assert_not_called()


@pytest.mark.parametrize("mapping", ["exact", "missing", "different", "unknown"])
def test_native_model_face_uses_exact_source_reverse_mapping(monkeypatch, mapping):
    adapter, view, selected, annotation = face_context(monkeypatch)
    source_face = object()
    mapped = source_face
    if mapping == "missing":
        mapped = None
    if mapping in {"different", "unknown"}:
        mapped = object()
    reverse = Mock(return_value=mapped)
    view.ReferencedDocument = NS(
        GetType=lambda: 1, Extension=NS(GetCorrespondingEntity2=reverse),
    )
    if mapping == "unknown":
        adapter.swApp.IsSame.side_effect = lambda a, b: -1 if a is source_face else int(a is b)

    def insert():
        return finish(
            adapter, view, source_face, "native",
            entity_context=drawing.AnnotationEntityContext.MODEL,
        )

    if mapping == "exact":
        insert()
    else:
        with pytest.raises(RuntimeError, match="corresponding source entity|changed entity identity"):
            insert()
    reverse.assert_called_once_with(selected)
    annotation.SetPosition2.assert_not_called()
