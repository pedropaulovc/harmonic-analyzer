"""Explicit source/view contracts retain exact identity across native contexts."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import _drawing_common as drawing
from test_native_annotation_placement_drawing import native_context


@pytest.fixture
def bank(monkeypatch):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _: value)
    model_entity, view_entity = object(), object()
    reverse = Mock(return_value=model_entity)
    source = SimpleNamespace(
        GetType=lambda: 1,
        Extension=SimpleNamespace(GetCorrespondingEntity2=reverse),
    )
    view = SimpleNamespace(
        ReferencedDocument=source,
        GetCorrespondingEntity=Mock(side_effect=AssertionError("no forward fallback")),
    )
    annotation = SimpleNamespace(
        GetAttachedEntities3=lambda: (view_entity,),
        GetAttachedEntityCount3=lambda: 1,
        GetAttachedEntityTypes=lambda: (1,),
        Owner=view,
        OwnerType=0,
    )
    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))
    return SimpleNamespace(**locals())


def validate(bank, entity_context, *, expected=None, entity_type="EDGE"):
    return drawing._validate_explicit_annotation_attachment(
        bank.adapter,
        bank.annotation,
        bank.view,
        bank.model_entity if expected is None else expected,
        entity_type=entity_type,
        entity_context=entity_context,
        label="controlled role",
    )


@pytest.mark.parametrize("kind,native_kind", [("EDGE", 1), ("FACE", 2)])
def test_model_identity_uses_only_exact_reverse_mapping(bank, kind, native_kind):
    bank.annotation.GetAttachedEntityTypes = lambda: (native_kind,)
    validate(bank, "model", entity_type=kind)
    bank.reverse.assert_called_once_with(bank.view_entity)
    bank.view.GetCorrespondingEntity.assert_not_called()


@pytest.mark.parametrize(
    "kind,native_kind", [("EDGE", 1), ("FACE", 2), ("SILHOUETTE", 46)]
)
def test_view_identity_never_calls_source_mapping(bank, kind, native_kind):
    bank.annotation.GetAttachedEntityTypes = lambda: (native_kind,)
    bank.reverse.side_effect = AssertionError("view comparison must stay direct")
    validate(bank, "view", expected=bank.view_entity, entity_type=kind)
    bank.reverse.assert_not_called()


@pytest.mark.parametrize(
    "fault",
    ["null", "wrong_entity", "unknown", "error", "wrong_document", "missing_document"],
)
def test_mapping_failure_never_falls_back_to_geometry_or_direct_identity(bank, fault):
    # Even direct native equality cannot substitute for the requested mapping.
    bank.annotation.GetAttachedEntities3 = lambda: (bank.model_entity,)
    if fault == "null":
        bank.reverse.return_value = None
    elif fault == "wrong_entity":
        bank.reverse.return_value = object()
    elif fault == "unknown":
        bank.adapter.swApp.IsSame = lambda a, b: (
            1 if a is bank.view and b is bank.view else -1
        )
    elif fault == "error":
        bank.reverse.side_effect = RuntimeError("native reverse rejected")
    elif fault == "wrong_document":
        bank.source.GetType = lambda: 3
    else:
        bank.view.ReferencedDocument = None
    with pytest.raises(RuntimeError):
        validate(bank, "model")
    bank.view.GetCorrespondingEntity.assert_not_called()


def test_wrong_view_fails_before_mapping(bank):
    bank.annotation.Owner = object()
    with pytest.raises(RuntimeError, match="view"):
        validate(bank, "model")
    bank.reverse.assert_not_called()


def test_model_silhouette_mapping_is_explicitly_unsupported(bank):
    bank.annotation.GetAttachedEntityTypes = lambda: (46,)
    with pytest.raises(ValueError, match="model.*EDGE.*FACE"):
        validate(bank, "model", entity_type="SILHOUETTE")
    bank.reverse.assert_not_called()


def test_context_is_an_enum_not_an_identity_fallback_flag(bank):
    with pytest.raises(ValueError):
        validate(bank, True)


@pytest.mark.parametrize("wrong_source", [False, True])
def test_explicit_model_finish_keeps_original_role_after_view_selection(
    monkeypatch, wrong_source
):
    adapter, view, selected, annotation = native_context(monkeypatch)
    expected_source = object()
    annotation.Owner, annotation.OwnerType = view, 0
    annotation.GetAttachedEntityTypes.return_value = (1,)
    reverse = Mock(return_value=object() if wrong_source else expected_source)
    view.ReferencedDocument = SimpleNamespace(
        GetType=lambda: 1,
        Extension=SimpleNamespace(GetCorrespondingEntity2=reverse),
    )

    def insert():
        return drawing.add_surface_finish(
            adapter,
            view,
            entity=expected_source,
            entity_context=drawing.AnnotationEntityContext.MODEL,
            symbol_xy=(0.12, 0.18),
            roughness_ra="1.6",
            label="model finish",
        )

    if wrong_source:
        with pytest.raises(RuntimeError, match="changed entity identity"):
            insert()
    else:
        insert()
    reverse.assert_called_once_with(selected)
    view.SelectEntity.assert_called_once_with(expected_source, False)
    adapter.currentModel.Extension.SelectByID2.assert_not_called()
