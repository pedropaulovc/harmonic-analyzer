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


@pytest.mark.parametrize("mutate_descendant", [False, True])
def test_instance_batches_preserve_descendant_own_flags(mutate_descendant):
    adapter, view, components, calls, selected = visibility_fixture((True, True, True))
    components[0].GetChildren = (components[1],)
    root = SimpleNamespace(GetChildren=(components[0], components[2]))
    view.RootDrawingComponent2 = lambda _: root
    if mutate_descendant:
        hide = adapter.currentModel.HideComponent2

        def corrupt_child():
            hide()
            components[1].Visible = False

        adapter.currentModel.HideComponent2 = corrupt_child
        with pytest.raises(RuntimeError, match="visibility readback mismatch"):
            visibility.set_drawing_view_instance_visibility(
                adapter, view, frozenset({"item-0"}), mode="hide", label="nested corruption"
            )
    else:
        visibility.set_drawing_view_instance_visibility(
            adapter, view, frozenset({"item-0"}), mode="hide", label="nested hide"
        )
        assert [c.Visible for c in components] == [False, True, True]
        assert calls == [("hide", (components[0].Name,)), ("rebuild",)]
    assert selected == []


def test_family_refuses_to_claim_leaf_is_visible_through_hidden_parent(monkeypatch):
    adapter, view, components, calls, _ = visibility_fixture((False, True, True))
    components[0].GetChildren = (components[1], components[2])
    root = SimpleNamespace(GetChildren=(components[0],))
    view.RootDrawingComponent2 = lambda _: root
    monkeypatch.setattr(
        visibility, "_drawing_component_stems",
        lambda _, component, stems: {"family"} if component is components[1] else set(),
    )
    with pytest.raises(RuntimeError, match="hidden ancestor"):
        visibility.isolate_drawing_view_components(
            adapter, view, visible_stems=frozenset({"family"}), label="hidden parent"
        )
    assert calls == []


def test_first_state_refusal_is_retained_in_exporter_manifest(monkeypatch, tmp_path):
    import json
    import time
    import dodo
    import _visibility_native_proof as proof

    failures = tmp_path / "cad/out/reports/failures"
    monkeypatch.setattr(proof, "PROOF", tmp_path / "cad/out/reports/visibility-proof")
    monkeypatch.setattr(proof._seat_forensics, "OUT_FAILURES", failures)
    monkeypatch.setattr(dodo, "FAILURES", failures)
    report = {"arms": [{"isolation": []}]}
    record = {"label": "first baseline"}
    report["arms"][0]["isolation"].append(record)
    before = {"view": {"position": [0.0, 0.0]}, "source": {}, "siblings": {}}
    after = {"view": {"position": [0.1, 0.0]}, "source": {}, "siblings": {}}
    started = time.time() - 1.0
    with pytest.raises(RuntimeError, match="state changed"):
        proof.record_and_assert_state(
            record, before, after, lambda: proof.persist_report("report.json", report)
        )
    exported = failures / "visibility-proof/report.json"
    stored = json.loads(exported.read_text(encoding="utf-8"))
    assert stored["arms"][0]["isolation"][0]["state_before"] == before
    assert stored["arms"][0]["isolation"][0]["state_after"] == after
    assert stored["arms"][0]["isolation"][0]["changed_state_fields"] == ["view"]
    assert exported in dodo._failure_artefacts(started)
    manifest = dodo._artefact_record(exported)
    assert manifest.startswith("visibility-proof/report.json:")
    assert f"failures/{manifest.split(':', 1)[0]}" == "failures/visibility-proof/report.json"
    assert json.loads((proof.PROOF / "report.json").read_text(encoding="utf-8")) == stored
