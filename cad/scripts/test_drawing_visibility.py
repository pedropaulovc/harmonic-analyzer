"""Seatless contracts for drawing-context visibility batches."""
from types import SimpleNamespace

import pytest

import _drawing_balloons as visibility


def visibility_model(view):
    """A selection-aware model double, shared with native-identity tests."""
    selected = []
    view.ReferencedConfiguration = "Default"
    view.GetDisplayMode2 = lambda: 4
    calls = []
    pending = list(visibility._drawing_component_children(view.RootDrawingComponent2(False)))
    while pending:
        component = pending.pop()
        pending.extend(visibility._drawing_component_children(component))

        def select(append, data, component=component):
            assert append and data.View is view
            selected.append(component)
            return True

        component.Select = select

    def apply(shown):
        calls.append(("show" if shown else "hide", tuple(c.Name for c in selected)))
        for component in selected:
            component.Visible = shown

    def rebuild():
        calls.append(("rebuild",))
        return True

    manager = SimpleNamespace(
        CreateSelectData=lambda: SimpleNamespace(),
        GetSelectedObjectCount2=lambda mark: len(selected),
        GetSelectedObjectType3=lambda index, mark: 20,
        GetSelectedObjectsDrawingView2=lambda index, mark: view,
        GetSelectedObjectsComponent4=lambda index, mark: selected[index - 1],
    )
    model = SimpleNamespace(
        GetType=lambda: 3, SelectionManager=manager,
        ClearSelection2=lambda all: selected.clear(),
        HideComponent2=lambda: apply(False), ShowComponent2=lambda: apply(True),
        EditRebuild3=rebuild,
    )
    return model, calls, selected


def visibility_fixture(states=(True, True, False)):
    components = [SimpleNamespace(Name=f"assembly/item-{i}@View1", Visible=shown, GetChildren=())
                  for i, shown in enumerate(states)]
    root = SimpleNamespace(GetChildren=tuple(components))
    view = SimpleNamespace(RootDrawingComponent2=lambda resolve: root, GetName2=lambda: "View1")
    model, calls, selected = visibility_model(view)
    adapter = SimpleNamespace(currentModel=model, _get_attr_or_call=lambda obj, name: getattr(obj, name)())
    return adapter, view, components, calls, selected


def test_batches_both_polarities_and_skips_unchanged():
    adapter, view, components, calls, selected = visibility_fixture()
    visibility.set_drawing_view_instance_visibility(
        adapter, view, frozenset({"item-0", "item-2"}), mode="show", label="test"
    )
    assert [c.Visible for c in components] == [True, False, True]
    assert calls == [("hide", (components[1].Name,)), ("show", (components[2].Name,)), ("rebuild",)]
    assert selected == []
    calls.clear()
    visibility.set_drawing_view_instance_visibility(
        adapter, view, frozenset({"item-0", "item-2"}), mode="show", label="noop"
    )
    assert calls == []


def test_hide_named_shows_every_other_instance():
    adapter, view, components, calls, _ = visibility_fixture()
    visibility.set_drawing_view_instance_visibility(
        adapter, view, frozenset({"item-0"}), mode="hide", label="hide"
    )
    assert [c.Visible for c in components] == [False, True, True]
    assert len(calls) == 3


def test_missing_instance_refuses_before_mutation():
    adapter, view, components, calls, _ = visibility_fixture()
    with pytest.raises(RuntimeError, match="instances not in the view"):
        visibility.set_drawing_view_instance_visibility(
            adapter, view, frozenset({"missing"}), mode="show", label="missing"
        )
    assert calls == []
    assert [c.Visible for c in components] == [True, True, False]


@pytest.mark.parametrize("fault", ["selection", "count", "type", "view", "identity", "readback", "rebuild", "document"])
def test_native_failures_refuse_and_clear_selection(fault):
    adapter, view, components, calls, selected = visibility_fixture()
    model = adapter.currentModel
    if fault == "selection":
        components[1].Select = lambda *_: False
    elif fault == "count":
        model.SelectionManager.GetSelectedObjectCount2 = lambda _: 0
    elif fault == "type":
        model.SelectionManager.GetSelectedObjectType3 = lambda *_: 1
    elif fault == "view":
        model.SelectionManager.GetSelectedObjectsDrawingView2 = lambda *_: None
    elif fault == "identity":
        model.SelectionManager.GetSelectedObjectsComponent4 = lambda *_: components[0]
    elif fault == "readback":
        model.HideComponent2 = lambda: None
    elif fault == "rebuild":
        model.EditRebuild3 = lambda: False
    elif fault == "document":
        model.GetType = lambda: 2
    with pytest.raises(RuntimeError):
        visibility.set_drawing_view_instance_visibility(
            adapter, view, frozenset({"item-0"}), mode="show", label=fault
        )
    assert selected == []
    if fault not in {"readback", "rebuild"}:
        assert calls == []


def test_family_missing_preflights_all_leaves(monkeypatch):
    adapter, view, components, calls, _ = visibility_fixture()
    monkeypatch.setattr(visibility, "_drawing_component_stems", lambda *_: set())
    with pytest.raises(RuntimeError, match="component families not found"):
        visibility.isolate_drawing_view_components(
            adapter, view, visible_stems=frozenset({"missing"}), label="family"
        )
    assert calls == []
    assert [c.Visible for c in components] == [True, True, False]


def test_family_preserves_parent_and_checks_nested_leaves(monkeypatch):
    adapter, view, components, calls, _ = visibility_fixture((True, True, True))
    components[0].GetChildren = (components[1], components[2])
    root = SimpleNamespace(GetChildren=(components[0],))
    view.RootDrawingComponent2 = lambda _: root
    monkeypatch.setattr(visibility, "_drawing_component_stems",
                        lambda _, component, stems: {"family"} if component is components[1] else set())
    visibility.isolate_drawing_view_components(
        adapter, view, visible_stems=frozenset({"family"}), label="nested"
    )
    assert [c.Visible for c in components] == [True, True, False]
    assert calls == [("hide", (components[2].Name,)), ("rebuild",)]
