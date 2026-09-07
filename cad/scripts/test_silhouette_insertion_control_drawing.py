"""Proactive boundary observations never retry or waive native validation."""

import json
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import _silhouette_insertion_control as control
from diagnostics import _recipe_view_entity_acceptance as observer
from diagnostics._recipe_view_roles import ViewRole, ViewResolver
from test_owned_native_documents_drawing import native as native
from test_silhouette_identity_control_drawing import (
    owned_scene as owned_scene,
    assert_owned_cleanup,
)


@pytest.fixture
def scene(owned_scene, monkeypatch):
    scene = owned_scene
    monkeypatch.setattr(control, "_early_bound", lambda value, _: value)
    role = ViewRole("*Front", 7, "SILHOUETTE", ViewResolver.SHANK)
    scene.bank.witness.roles = {"finish": role}
    scene.bank.witness.selected = {
        "finish": (scene.expected, scene.selected, scene.bank.view)
    }
    scene.bank.witness.initial_faces = {"finish": scene.face}
    scene.fresh = NS(**vars(scene.expected))
    scene.attached = NS(**vars(scene.expected))
    scene.annotation = NS(
        GetAttachedEntities3=lambda: (scene.attached,),
        GetAttachedEntityTypes=lambda: (46,),
        GetAttachedEntityCount3=lambda: 1,
    )
    scene.bank.module._shank_silhouette = Mock(return_value=scene.fresh)
    scene.phase = "before"
    scene.native_calls = []

    def reference(entity):
        scene.native_calls.append((scene.phase, "reference", entity))
        if entity is scene.expected and scene.phase == "after":
            return memoryview(bytes((99, 88)))
        return memoryview(bytes((11, 22)))

    def compare(first, second):
        scene.native_calls.append((scene.phase, "compare", first, second))
        return int(first == second)

    scene.drawing.Extension.GetPersistReference3 = reference
    scene.drawing.Extension.IsSamePersistentID = compare
    scene.boundary = control.InsertionBoundaries(scene.bank.witness, scene.adapter)
    scene.bank_row = {
        "silhouette": {
            "persistent_identity": {
                "expected": {"reference": (11, 22)},
                "actual": {"reference": (11, 22)},
                "native_result": 1,
            }
        }
    }
    scene.original_style = Mock()
    monkeypatch.setattr(control.drawing, "_style_surface_finish", scene.original_style)
    validator = control.drawing._validate_explicit_annotation_attachment

    # Use the real shared PID predicate, with only its prior owner/shape guards
    # represented by this bounded native double; production validator is unedited.
    def validate(adapter, annotation, view, entity, **kwargs):
        control.persistent.require_same(
            adapter.currentModel, entity, scene.attached, label=kwargs["label"]
        )

    scene.validator = Mock(side_effect=validate)
    monkeypatch.setattr(
        control.drawing, "_validate_explicit_annotation_attachment", scene.validator
    )
    scene.real_validator = validator
    return scene


def run(scene):
    with scene.boundary.observe():
        scene.boundary.selected("finish", scene.bank_row)
        control.drawing._style_surface_finish(
            scene.adapter, object(), scene.annotation, label="finish"
        )
        scene.phase = "after"  # fixture represents the recipe's existing rebuild
        control.drawing._validate_explicit_annotation_attachment(
            scene.adapter,
            scene.annotation,
            scene.bank.view,
            scene.expected,
            entity_type="SILHOUETTE",
            entity_context=control.drawing.AnnotationEntityContext.VIEW,
            label="finish",
        )


def rows(scene):
    return scene.bank.witness.context_report["silhouette_insertion_boundaries"][
        "finish"
    ]


def test_failed_predicate_keeps_original_once_and_compares_stored_native_ids(
    scene, monkeypatch
):
    original_same = control.persistent.require_same
    predicate = Mock(wraps=original_same)
    monkeypatch.setattr(control.persistent, "require_same", predicate)
    with pytest.raises(RuntimeError, match="native IsSamePersistentID returned 0"):
        run(scene)
    scene.validator.assert_called_once()
    predicate.assert_called_once()
    scene.original_style.assert_called_once()
    assert control.persistent.require_same is predicate
    assert control.drawing._style_surface_finish is scene.original_style
    assert control.drawing._validate_explicit_annotation_attachment is scene.validator
    result = rows(scene)
    assert result["production_predicate"]["native_result"] == 0
    assert result["production_predicate"]["expected"]["reference"] == (99, 88)
    assert result["production_predicate"]["actual"]["reference"] == (11, 22)
    before = result["post_style_pre_rebuild"]
    assert before["persistent.pre_insert_expected.attached"] == {"value": 1}
    after = result["rejected_post_rebuild"]
    assert after["persistent.expected.attached"] == {"value": 0}
    assert after["persistent.pre_insert_expected.attached"] == {"value": 1}
    assert after["fresh_identity"]["persistent.pre_insert_expected.fresh"] == {
        "value": 1
    }
    assert (
        after["geometry.expected"]
        == after["geometry.attached"]
        == after["geometry.fresh"]
    )
    assert after["face_same.expected.attached"] == {"value": 1}
    assert after["face_same.pre_insert_selected.attached"] == {"value": 1}
    assert after["view_same.attached"] == {"value": 1}
    scene.bank.module._shank_silhouette.assert_called_once_with(
        scene.adapter, scene.bank.view
    )
    assert (
        after["fresh_resolver"]["scope"]
        == "existing resolver; activates witnessed view"
    )
    for name in ("pre_insert_self", "post_style_pre_rebuild", "rejected_post_rebuild"):
        assert result[name]["seconds"] >= 0
        assert (
            result[name]["drawing"]["dirty_before"]
            is result[name]["drawing"]["dirty_after"]
            is False
        )
        assert (
            result[name]["source"]["dirty_before"]
            is result[name]["source"]["dirty_after"]
            is False
        )
    assert all(kind != "reference" for _, kind, *_ in scene.native_calls[:3])
    json.dumps(result, allow_nan=False)
    assert_owned_cleanup(scene)


@pytest.mark.parametrize(
    "failure",
    ["capture", "resolver", "ownership", "malformed_attachment", "malformed_reference"],
)
def test_secondary_capture_failure_never_masks_original_or_leaks_wrappers(
    scene, monkeypatch, failure
):
    primary = RuntimeError("original native rejection")
    scene.validator.side_effect = primary
    original_same = control.persistent.require_same
    if failure == "capture":
        monkeypatch.setattr(
            scene.boundary, "rejected", Mock(side_effect=RuntimeError("capture failed"))
        )
    if failure == "resolver":
        scene.bank.module._shank_silhouette.side_effect = RuntimeError(
            "resolver failed"
        )
    if failure == "ownership":
        monkeypatch.setattr(
            scene.adapter.ownership,
            "assert_current_owned",
            Mock(side_effect=RuntimeError("ownership refused")),
        )
    if failure == "malformed_attachment":
        scene.annotation.GetAttachedEntities3 = lambda: ()
    if failure == "malformed_reference":
        scene.drawing.Extension.GetPersistReference3 = lambda _: memoryview(b"")
    with pytest.raises(RuntimeError) as raised:
        run(scene)
    assert raised.value is primary
    scene.validator.assert_called_once()
    assert control.persistent.require_same is original_same
    assert control.drawing._style_surface_finish is scene.original_style
    assert control.drawing._validate_explicit_annotation_attachment is scene.validator
    assert rows(scene)["production_predicate"]["original_error"] == repr(primary)
    json.dumps(rows(scene), allow_nan=False)
    # Restore the deliberately injected ownership refusal before normal cleanup.
    if failure == "ownership":
        monkeypatch.undo()
    assert_owned_cleanup(scene)


def test_success_never_fresh_resolves_or_captures_full_geometry(scene):
    scene.drawing.Extension.GetPersistReference3 = lambda _: (11, 22)
    run(scene)
    scene.validator.assert_called_once()
    scene.bank.module._shank_silhouette.assert_not_called()
    assert "rejected_post_rebuild" not in rows(scene)
    assert rows(scene)["production_predicate"]["native_result"] == 1
    assert_owned_cleanup(scene)


def test_actual_production_validator_still_rejects_and_is_called_once(scene):
    scene.annotation.OwnerType = 0
    scene.annotation.Owner = scene.bank.view
    scene.validator.side_effect = scene.real_validator
    with pytest.raises(RuntimeError, match="native IsSamePersistentID returned 0"):
        run(scene)
    scene.validator.assert_called_once()
    assert rows(scene)["production_predicate"]["native_result"] == 0
    assert_owned_cleanup(scene)


def test_old_wrapper_geometry_precedes_fresh_resolver_side_effect(scene):
    def fresh_resolver(*_):
        assert "geometry.expected" in rows(scene)["rejected_post_rebuild"]
        scene.expected.GetEndPoint = lambda: NS(ArrayData=(0.003, 0, 0.99))
        return scene.fresh

    scene.bank.module._shank_silhouette.side_effect = fresh_resolver
    with pytest.raises(RuntimeError, match="returned 0"):
        run(scene)
    after = rows(scene)["rejected_post_rebuild"]
    assert after["geometry.expected"]["value"]["end"] == (0.003, 0, 0.1)
    assert after["geometry.fresh"]["value"]["end"] == (0.003, 0, 0.1)
    assert_owned_cleanup(scene)


def test_existing_style_error_propagates_unchanged_and_restores_both_wrappers(scene):
    primary = RuntimeError("original styling failure")
    scene.original_style.side_effect = primary
    with pytest.raises(RuntimeError) as raised:
        run(scene)
    assert raised.value is primary
    scene.validator.assert_not_called()
    assert "post_style_pre_rebuild" not in rows(scene)
    assert control.drawing._style_surface_finish is scene.original_style
    assert control.drawing._validate_explicit_annotation_attachment is scene.validator
    assert_owned_cleanup(scene)


def test_changed_raw_geometry_is_retained_not_rounded_or_used_to_accept(scene):
    scene.attached.GetEndPoint = lambda: NS(ArrayData=(0.003, 0, 0.12))
    with pytest.raises(RuntimeError, match="returned 0"):
        run(scene)
    after = rows(scene)["rejected_post_rebuild"]
    assert after["geometry.attached"]["value"]["end"] == (0.003, 0, 0.12)
    assert after["geometry.expected"] != after["geometry.attached"]
    assert_owned_cleanup(scene)


def test_dirty_source_transition_is_observed_not_cleared(scene):
    query = scene.drawing.Extension.GetPersistReference3

    def changed(entity):
        scene.source.dirty = True
        return query(entity)

    scene.drawing.Extension.GetPersistReference3 = changed
    with pytest.raises(RuntimeError, match="returned 0"):
        run(scene)
    sample = rows(scene)["post_style_pre_rebuild"]
    assert sample["source"]["dirty_before"] is False
    assert sample["source"]["dirty_after"] is True
    assert scene.source.dirty
    assert_owned_cleanup(scene)


def test_observer_seam_registers_selected_bank_before_surface_style_and_validation(
    scene, monkeypatch
):
    scene.bank.witness.selected.clear()

    def build(adapter, view, **kwargs):
        control.drawing._select_annotation_entity(adapter, view, **kwargs)
        control.drawing._style_surface_finish(
            adapter, object(), scene.annotation, label=kwargs["label"]
        )
        scene.phase = "after"
        control.drawing._validate_explicit_annotation_attachment(
            adapter,
            scene.annotation,
            view,
            kwargs["entity"],
            **{k: v for k, v in kwargs.items() if k != "entity"},
        )

    monkeypatch.setattr(control.drawing, "add_surface_finish", build)
    scene.bank.module.add_surface_finish = build
    with pytest.raises(RuntimeError, match="returned 0"):
        with scene.bank.witness.observe(scene.adapter):
            scene.bank.module.add_surface_finish(
                scene.adapter,
                scene.bank.view,
                entity=scene.expected,
                entity_type="SILHOUETTE",
                label="finish",
            )
    result = rows(scene)
    assert list(result) == [
        "pre_insert_self",
        "post_style_pre_rebuild",
        "production_predicate",
        "rejected_post_rebuild",
    ]
    assert result["pre_insert_self"][
        "stored_selection_references"
    ] == scene.boundary.initial.get(
        "finish", {"pre_insert_expected": (11, 22), "pre_insert_actual": (11, 22)}
    )
    assert scene.bank.witness.recorded == {}
    assert control.drawing.add_surface_finish is build
    assert observer.drawing._select_annotation_entity is scene.bank.selected
    assert_owned_cleanup(scene)
