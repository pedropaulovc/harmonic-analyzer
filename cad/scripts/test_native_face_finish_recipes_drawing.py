"""Whole-cylinder finish calls use native FACE placement, not new equality."""

import ast
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

import draw_cone_gear_shaft as cone
import draw_crankshaft as crank
import draw_spring_hook as spring
from diagnostics._recipe_view_roles import VIEW_ROLES, ViewResolver
from test_native_annotation_placement_drawing import native_context
from test_view_recipe_acceptance_drawing import bank as bank
from diagnostics import _recipe_view_entity_acceptance as observer


@pytest.mark.parametrize(
    "module, target, label, view_name, entity_name, control_key, call_count",
    [
        (
            spring,
            "spring_hook",
            "shank seating finish",
            "front",
            "shank_face",
            "shank_seating",
            1,
        ),
        (
            crank,
            "crankshaft",
            "crankshaft bearing-journal finish",
            "right",
            "journal_face",
            "bearing_journal",
            1,
        ),
        (
            cone,
            "cone_gear_shaft",
            "pivot journal finish",
            "side",
            "pivot_face",
            "pivot_journal",
            2,
        ),
        (
            cone,
            "cone_gear_shaft",
            "tip journal finish",
            "side",
            "tip_face",
            "tip_journal",
            2,
        ),
    ],
)
def test_actual_recipe_call_keeps_part_control_and_omits_all_position_arguments(
    module, target, label, view_name, entity_name, control_key, call_count
):
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    build = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    calls = [
        node
        for node in ast.walk(build)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "add_surface_finish"
    ]
    assert len(calls) == call_count
    selected = [
        call for call in calls
        if any(
            keyword.arg == "label" and ast.literal_eval(keyword.value) == label
            for keyword in call.keywords
        )
    ]
    assert len(selected) == 1
    adapter, view, face = object(), object(), object()
    insert = Mock()
    scope = dict(vars(module), adapter=adapter, add_surface_finish=insert)
    scope.update({view_name: view, entity_name: face})
    # Keep the old call evaluable: failure must expose forbidden placement
    # arguments, not merely missing locals from the retired coordinate path.
    scope.update(pivot_top=(0.2, 0.21), tip_top=(0.03, 0.21))
    eval(compile(ast.Expression(selected[0]), module.__file__, "eval"), scope)
    insert.assert_called_once_with(
        adapter,
        view,
        entity=face,
        entity_type="FACE",
        control=module.surface_finish_by_key(module.SURFACE_FINISHES, control_key),
        label=label,
    )
    role = VIEW_ROLES[target][label]
    assert role.entity_kind == 2
    assert role.annotation_kind == 7


def test_shank_face_is_the_exact_existing_resolver_face(monkeypatch):
    adapter, view, face = object(), object(), object()
    silhouette = NS(GetFace=Mock(return_value=face))
    resolver = Mock(return_value=silhouette)
    monkeypatch.setattr(spring, "_shank_silhouette", resolver)
    monkeypatch.setattr(spring, "_early_bound", lambda value, _: value)
    assert spring._shank_face(adapter, view) is face
    resolver.assert_called_once_with(adapter, view)
    silhouette.GetFace.assert_called_once_with()


def test_shank_face_rejects_missing_underlying_face(monkeypatch):
    monkeypatch.setattr(
        spring, "_shank_silhouette", lambda *_: NS(GetFace=lambda: None)
    )
    monkeypatch.setattr(spring, "_early_bound", lambda value, _: value)
    with pytest.raises(RuntimeError, match="shank silhouette has no face"):
        spring._shank_face(object(), object())


@pytest.mark.parametrize(
    "target, label",
    [
        ("spring_hook", "shank seating finish"),
        ("crankshaft", "crankshaft bearing-journal finish"),
        ("cone_gear_shaft", "pivot journal finish"),
        ("cone_gear_shaft", "tip journal finish"),
    ],
)
def test_fresh_face_manifest_reresolves_without_retaining_old_handles(target, label):
    role = VIEW_ROLES[target][label]
    adapter, view, first, reopened = object(), object(), object(), object()
    resolver = Mock(side_effect=[first, reopened])
    module = NS(
        _shank_face=resolver, _visible_cylindrical_face=resolver,
        _cylindrical_face=resolver, JOURNAL_DIA=11.388, SECTION_DIAS=(11.388, 0.79375),
    )
    assert role.resolve(module, adapter, view) is first
    assert role.resolve(module, adapter, view) is reopened
    args = (adapter, view, module.JOURNAL_DIA)
    if target == "spring_hook":
        args = (adapter, view)
    if label == "tip journal finish":
        args = (adapter, view, module.SECTION_DIAS[-1])
    assert all(call.args == args for call in resolver.call_args_list)
    assert role.resolver not in (ViewResolver.SHANK, ViewResolver.JOURNAL)


def test_crank_recipe_reuses_its_centerline_face_without_resolving_a_silhouette():
    tree = ast.parse(Path(crank.__file__).read_text(encoding="utf-8"))
    build = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    names = [
        node.func.id
        for node in ast.walk(build)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert names.count("_visible_cylindrical_face") == 1
    assert "_visible_journal_silhouette" not in names


@pytest.mark.parametrize("identity", [1, 0, -1])
def test_native_face_helper_uses_no_leader_and_keeps_exact_selected_identity(
    monkeypatch, identity
):
    adapter, view, face, annotation = native_context(monkeypatch)
    adapter.swApp.IsSame.side_effect = None
    adapter.swApp.IsSame.return_value = identity

    def insert():
        return observer.drawing.add_surface_finish(
            adapter,
            view,
            entity=face,
            entity_type="FACE",
            roughness_ra="1.6",
            label="native face",
        )

    if identity == 1:
        insert()
    else:
        with pytest.raises(RuntimeError, match="attached to a different entity"):
            insert()
    view.SelectEntity.assert_called_once_with(face, False)
    adapter.swApp.IsSame.assert_called_once_with(face, face)
    args = adapter.currentModel.Extension.InsertSurfaceFinishSymbol3.call_args.args
    assert args[1:5] == (0, 0.0, 0.0, 0.0)
    annotation.SetPosition2.assert_not_called()
    annotation.SetLeader3.assert_not_called()
    annotation.SetLeaderAttachmentPointAtIndex.assert_not_called()


@pytest.mark.parametrize(
    "target, label",
    [
        ("spring_hook", "shank seating finish"),
        ("crankshaft", "crankshaft bearing-journal finish"),
        ("cone_gear_shaft", "pivot journal finish"),
        ("cone_gear_shaft", "tip journal finish"),
    ],
)
@pytest.mark.parametrize(
    "fault", [None, "wrong_face", "wrong_view", "hidden", "off_sheet"]
)
def test_face_observer_keeps_fresh_cold_identity_and_native_placement_guards(
    bank, monkeypatch, target, label, fault
):
    role = VIEW_ROLES[target][label]
    bank.witness.roles = {label: role}
    bank.manager.GetSelectedObjectType3 = lambda *_: 2
    bank.view.GetOrientationName = lambda: role.orientation
    bank.module.JOURNAL_DIA = 11.388
    bank.module.SECTION_DIAS = (11.388, 0.79375)
    bank.module._shank_face = lambda adapter, view: view.entity
    bank.module._visible_cylindrical_face = lambda adapter, view, diameter: view.entity
    bank.module._cylindrical_face = lambda adapter, view, diameter: view.entity
    raw = ("face", 4002, (0, 0, 0, 0, 1, 0, 0.0007), (0, 0, 0, 0.01, 0.01, 0.01), None)
    monkeypatch.setattr(observer.attachments, "geometry", lambda *_: raw)
    with bank.witness.observe(bank.adapter):
        bank.module.add_surface_finish(
            bank.adapter, bank.view, entity=bank.entity, entity_type="FACE", label=label
        )
    built = bank.witness.drawing_snapshot(bank.adapter, phase="built")
    assert built["explicit"][label]["kind"] == 2
    assert bank.witness.context_report["stages"][-1]["resolver_side_effect"] == (
        "activate_view" if target == "spring_hook" else "none"
    )
    cold_face = object()
    cold_view = NS(
        GetName2=lambda: "Drawing View1",
        GetOrientationName=lambda: role.orientation,
        entity=cold_face,
    )
    annotation = NS(**vars(bank.annotations[label]))
    annotation.Owner = cold_view
    annotation.GetAttachedEntities3 = lambda: (cold_face,)
    cold_view.GetAnnotations = lambda: (annotation,)
    monkeypatch.setattr(
        observer.attachments, "views", lambda _: {"Sheet/View": cold_view}
    )
    bank.view.GetName2 = Mock(side_effect=AssertionError("closed view queried"))
    bank.annotations[label].GetName = Mock(
        side_effect=AssertionError("closed annotation queried")
    )
    if fault == "wrong_face":
        cold_view.entity = object()  # Equal raw geometry does not certify this face.
    if fault == "wrong_view":
        annotation.Owner = object()
    if fault == "hidden":
        annotation.Visible = 3
    if fault == "off_sheet":
        annotation.GetPosition = lambda: (1, 0.2, 0)
    if fault is not None:
        with pytest.raises(RuntimeError):
            bank.witness.drawing_snapshot(bank.adapter, phase="reopened")
        return
    assert bank.witness.drawing_snapshot(bank.adapter, phase="reopened") == built
