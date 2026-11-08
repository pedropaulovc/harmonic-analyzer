"""Seatless contracts for drawing-context visibility batches."""
from types import SimpleNamespace

import pytest

import _drawing_balloons as visibility


def native_owner(name, path, configuration="Default", parent=None):
    return SimpleNamespace(
        Name2=name, GetPathName=lambda: path, ReferencedConfiguration=configuration,
        GetParent=lambda: parent,
    )


def native_same(left, right):
    return int(getattr(left, "_oleobj_", left) is getattr(right, "_oleobj_", right))


def visibility_model(view):
    """A selection-aware model double, shared with native-identity tests."""
    selected = []
    view.ReferencedConfiguration = "Default"
    view.GetDisplayMode2 = lambda: 4
    view.Type = 6
    calls = []
    pending = list(visibility._drawing_component_children(view.RootDrawingComponent2(False)))
    while pending:
        component = pending.pop()
        pending.extend(visibility._drawing_component_children(component))
        if not hasattr(component, "Component"):
            name = visibility._instance_name(component.Name)
            component.Component = native_owner(name, f"C:/native/{name}.SLDPRT")

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
        native_app=SimpleNamespace(IsSame=native_same),
    )
    return model, calls, selected


def visibility_fixture(states=(True, True, False)):
    components = [SimpleNamespace(Name=f"assembly/item-{i}@View1", Visible=shown, GetChildren=())
                  for i, shown in enumerate(states)]
    root = SimpleNamespace(GetChildren=tuple(components))
    view = SimpleNamespace(RootDrawingComponent2=lambda resolve: root, GetName2=lambda: "View1")
    model, calls, selected = visibility_model(view)
    adapter = SimpleNamespace(
        currentModel=model, swApp=model.native_app,
        _get_attr_or_call=lambda obj, name: getattr(obj, name)(),
    )
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
    with pytest.raises(RuntimeError) as error:
        visibility.set_drawing_view_instance_visibility(
            adapter, view, frozenset({"item-0"}), mode="show", label=fault
        )
    assert selected == []
    if fault not in {"readback", "rebuild"}:
        assert calls == []
    if fault == "identity":
        assert "expected_count=1, selected_count=1" in str(error.value)
        assert "missing=['assembly/item-1@View1']" in str(error.value)
        assert "unexpected=['assembly/item-0@View1']" in str(error.value)


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
        with pytest.raises(RuntimeError, match="unchanged occurrence tree flags changed"):
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


def section_fixture(count=3, shown_count=1):
    adapter, view, components, calls, selected = visibility_fixture((True,) * count)
    view.Type = 2
    source_path = "C:/native/assembly.SLDASM"
    view.ReferencedDocument = ""  # SDK: section documents resolve through GetBaseView.
    source = SimpleNamespace(GetPathName=lambda: source_path, GetType=lambda: 2)
    base = SimpleNamespace(Type=6, GetName2=lambda: "Base", ReferencedDocument=source)
    view.GetBaseView = lambda: base
    wrapper = native_owner("assembly-1", source_path)
    hidden = set(range(shown_count, count))

    def hidden_owner(index):
        owner = components[index].Component
        return native_owner(
            f"{wrapper.Name2}/{owner.Name2}", owner.GetPathName(),
            owner.ReferencedConfiguration, wrapper,
        )

    view.GetHiddenComponents = lambda: tuple(hidden_owner(i) for i in sorted(hidden))

    def apply(mode):
        calls.append((mode, tuple(c.Name for c in selected)))
        for component in selected:
            index = components.index(component)
            if mode == "hide":
                hidden.add(index)
            else:
                hidden.remove(index)
        # The generated section-tree flags deliberately remain True.

    adapter.currentModel.HideComponent2 = lambda: apply("hide")
    adapter.currentModel.ShowComponent2 = lambda: apply("show")
    adapter.currentModel.SelectionManager.GetSelectedObjectsComponent4 = (
        lambda index, mark: SimpleNamespace(
            Name="SectionAssembly/assembly-1/" + selected[index - 1].Component.Name2,
            Component=selected[index - 1].Component,
        )
    )
    return adapter, view, components, calls, selected, hidden, wrapper


@pytest.mark.parametrize("count,shown_count", [(3, 1), (147, 5)])
def test_section_uses_hidden_inventory_for_noop_not_true_tree_flags(count, shown_count):
    adapter, view, components, calls, _, hidden, _ = section_fixture(count, shown_count)
    visibility.set_drawing_view_instance_visibility(
        adapter, view, frozenset(f"item-{i}" for i in range(shown_count)),
        mode="show", label="section noop",
    )
    assert calls == []
    assert hidden == set(range(shown_count, count))
    assert all(component.Visible is True for component in components)


def test_section_hidden_show_and_hide_use_same_native_owner_in_different_wrapper():
    adapter, view, components, calls, selected, hidden, _ = section_fixture()
    visibility.set_drawing_view_instance_visibility(
        adapter, view, frozenset({"item-1"}), mode="show", label="section transition"
    )
    assert hidden == {0, 2}
    assert calls == [("hide", (components[0].Name,)), ("show", (components[1].Name,)), ("rebuild",)]
    assert all(component.Visible is True for component in components)
    assert selected == []


def test_section_readback_refuses_ineffective_show_even_with_true_tree_flags():
    adapter, view, _, _, selected, _, _ = section_fixture()
    adapter.currentModel.ShowComponent2 = lambda: None
    with pytest.raises(RuntimeError, match="visibility readback mismatch"):
        visibility.set_drawing_view_instance_visibility(
            adapter, view, frozenset({"item-1"}), mode="show", label="section missed show"
        )
    assert selected == []


@pytest.mark.parametrize("fault", [
    "unknown", "wrong-source", "wrong-wrapper-config", "wrong-leaf-config",
    "duplicate-hidden", "duplicate-view", "null-owner", "bad-array", "getter-error",
])
def test_section_inventory_refuses_unproved_owner_mapping(fault):
    adapter, view, components, calls, _, _, wrapper = section_fixture()
    if fault == "unknown":
        view.GetHiddenComponents = lambda: (native_owner("alien", "C:/native/alien.SLDPRT"),)
    elif fault == "wrong-source":
        wrapper.GetPathName = lambda: "C:/native/other.SLDASM"
    elif fault == "wrong-wrapper-config":
        wrapper.ReferencedConfiguration = "Other"
    elif fault == "wrong-leaf-config":
        view.GetHiddenComponents = lambda: (
            native_owner("assembly-1/item-1", components[1].Component.GetPathName(), "Other", wrapper),
        )
    elif fault == "duplicate-hidden":
        original = view.GetHiddenComponents
        view.GetHiddenComponents = lambda: (original()[0], original()[0])
    elif fault == "duplicate-view":
        components[2].Component = components[1].Component
    elif fault == "null-owner":
        view.GetHiddenComponents = lambda: (None,)
    elif fault == "bad-array":
        view.GetHiddenComponents = lambda: False
    elif fault == "getter-error":
        def unreadable():
            raise RuntimeError("native hidden inventory unreadable")
        view.GetHiddenComponents = unreadable
    with pytest.raises(RuntimeError):
        visibility.set_drawing_view_instance_visibility(
            adapter, view, frozenset({"item-0"}), mode="show", label=fault
        )
    assert calls == []


def test_section_direct_owners_and_view_config_not_active_source_config():
    adapter, view, components, calls, _, _, _ = section_fixture()
    view.GetBaseView().ReferencedDocument.ConfigurationManager = SimpleNamespace(
        ActiveConfiguration=SimpleNamespace(Name="Different active configuration")
    )
    view.GetHiddenComponents = lambda: (components[1].Component, components[2].Component)
    visibility.set_drawing_view_instance_visibility(
        adapter, view, frozenset({"item-0"}), mode="show", label="direct owners"
    )
    assert calls == []


def test_section_proves_every_level_of_nested_source_wrapper():
    _, view, components, _, _, _, wrapper = section_fixture()
    parent = native_owner("sub-1", "C:/native/sub.SLDASM", "Member")
    components[0].Component = native_owner("sub-1/item-0", "C:/native/item-0.SLDPRT", parent=parent)
    wrapped_parent = native_owner("assembly-1/sub-1", "C:/native/sub.SLDASM", "Member", wrapper)
    wrapped = native_owner("assembly-1/sub-1/item-0", "C:/native/item-0.SLDPRT", parent=wrapped_parent)
    view.GetHiddenComponents = lambda: (wrapped,)
    rows = visibility._visibility_components(view, label="nested wrapper")
    assert {row.name for row in rows if not row.visible} == {components[0].Name}
    wrapped_parent.Name2 = "assembly-1/wrong-sub"
    with pytest.raises(RuntimeError, match="exact view matches"):
        visibility._visibility_components(view, label="wrong nested chain")


@pytest.mark.parametrize("code", [-1, 0, True, None])
def test_native_identity_requires_exact_integer_same_code(code):
    adapter, view, _, calls, selected = visibility_fixture()
    adapter.swApp.IsSame = lambda *_: code
    with pytest.raises(RuntimeError, match="identity self-control"):
        visibility.set_drawing_view_instance_visibility(
            adapter, view, frozenset({"item-0"}), mode="show", label="bad native comparison"
        )
    assert calls == [] and selected == []


def test_native_identity_rejects_equal_metadata_but_different_occurrence():
    adapter, view, components, calls, selected = visibility_fixture()
    clone = native_owner(
        components[1].Component.Name2, components[1].Component.GetPathName(),
        components[1].Component.ReferencedConfiguration,
    )
    adapter.currentModel.SelectionManager.GetSelectedObjectsComponent4 = lambda *_: SimpleNamespace(
        Name=components[1].Name, Component=clone
    )
    with pytest.raises(RuntimeError, match="native_comparison=0"):
        visibility.set_drawing_view_instance_visibility(
            adapter, view, frozenset({"item-0"}), mode="show", label="foreign native owner"
        )
    assert calls == [] and selected == []


def test_native_identity_refuses_reordered_appended_selection():
    adapter, view, _, calls, selected = visibility_fixture((True, True, True))
    adapter.currentModel.SelectionManager.GetSelectedObjectsComponent4 = lambda index, mark: selected[-index]
    with pytest.raises(RuntimeError, match="native_comparison=0"):
        visibility.set_drawing_view_instance_visibility(
            adapter, view, frozenset(), mode="show", label="reordered selection"
        )
    assert calls == [] and selected == []


@pytest.mark.parametrize("fault", ["missing-base", "base-cycle", "missing-document", "not-assembly"])
def test_section_source_requires_real_acyclic_base_document(fault):
    adapter, view, _, calls, _, _, _ = section_fixture()
    base = view.GetBaseView()
    if fault == "missing-base":
        view.GetBaseView = lambda: None
    elif fault == "base-cycle":
        base.Type = 2
        base.GetBaseView = lambda: view
    elif fault == "missing-document":
        base.ReferencedDocument = ""
    elif fault == "not-assembly":
        base.ReferencedDocument.GetType = lambda: 1
    with pytest.raises(RuntimeError):
        visibility.set_drawing_view_instance_visibility(
            adapter, view, frozenset({"item-0"}), mode="show", label=fault
        )
    assert calls == []


@pytest.mark.parametrize("mutation", [
    "settle", "unchanged", "reverse", "mode", "position", "configuration", "siblings", "source",
])
def test_proof_allows_only_observed_target_quality_settling(mutation):
    from copy import deepcopy
    import _visibility_native_proof as proof

    before = {
        "view": {"display": [False, 3, True, True, True],
                 "position": [0.1, 0.2], "configuration": "Default"},
        "siblings": [{"display": [False, 3, True, True, True]}],
        "source": {"configuration": "Default"},
    }
    after = deepcopy(before)
    after["view"]["display"][2] = False
    if mutation == "unchanged":
        after = deepcopy(before)
    elif mutation == "reverse":
        before, after = after, before
    elif mutation == "mode":
        after["view"]["display"][1] = 4
    elif mutation == "position":
        after["view"]["position"][0] = 0.3
    elif mutation == "configuration":
        after["view"]["configuration"] = "Other"
    elif mutation == "siblings":
        after["siblings"][0]["display"][2] = False
    elif mutation == "source":
        after["source"]["configuration"] = "Other"
    record = {"label": mutation}
    saved = []
    checkpoint = lambda: saved.append(deepcopy(record))
    if mutation in {"settle", "unchanged"}:
        proof.record_and_assert_state(record, before, after, checkpoint)
    else:
        with pytest.raises(RuntimeError, match="state changed"):
            proof.record_and_assert_state(record, before, after, checkpoint)
    assert saved == [record]
    assert record["permitted_transition"] == (
        "target faceted HLR True->False" if mutation == "settle" else None
    )

def test_section_hidden_inventory_rejects_two_proved_representations():
    _, view, components, _, _, _, wrapper = section_fixture()
    native = components[1].Component
    wrapped = native_owner(
        "assembly-1/" + native.Name2, native.GetPathName(), native.ReferencedConfiguration, wrapper
    )
    components[0].Component = wrapped
    view.GetHiddenComponents = lambda: (wrapped,)
    with pytest.raises(RuntimeError, match="2 exact view matches"):
        visibility._visibility_components(view, label="ambiguous hidden owner")
