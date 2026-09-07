"""Bounded native radial-spacing selection, not a geometry-placement mock proof."""

from types import SimpleNamespace
from unittest.mock import Mock
from copy import deepcopy
from pathlib import Path

import pytest

from diagnostics import probe_dimension_arrangement as probe


TYPES = {
    "NoseRadius": 5,
    "TipCentreX": 11,
    "TipRadius": 5,
    "BarLength": 11,
    "FulcrumDia": 6,
    "RD1": 2,
    "RD2": 2,
    "RD3": 2,
    "RD4": 6,
    "RD5": 6,
}
RADIAL = {name: kind for name, kind in TYPES.items() if kind in (5, 6)}


def context(monkeypatch):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(probe, "null_callout", lambda: None)
    selected = []
    view = SimpleNamespace(GetName2=lambda: "Drawing View1")
    displays = {
        name: SimpleNamespace(Type2=kind, GetNameForSelection=lambda name=name: name)
        for name, kind in TYPES.items()
    }
    annotations = {
        name: SimpleNamespace(
            GetName=lambda name=name: name,
            Visible=1,
            OwnerType=0,
            Owner=view,
            GetSpecificAnnotation=lambda name=name: displays[name],
        )
        for name in TYPES
    }
    view.GetAnnotationsByType = lambda _: tuple(annotations.values())

    def select(name, *args):
        assert args == ("DIMENSION", 0.0, 0.0, 0.0, True, 0, None, 0)
        selected.append(displays[name])
        return True

    selection = SimpleNamespace(
        GetSelectedObjectCount2=lambda _: len(selected),
        GetSelectedObject6=lambda index, _: selected[index - 1],
    )
    extension = SimpleNamespace(
        SelectByID2=Mock(side_effect=select), AlignDimensions=Mock(return_value=True)
    )
    model = SimpleNamespace(
        SelectionManager=selection,
        Extension=extension,
        ClearSelection2=Mock(side_effect=lambda _: selected.clear()),
        ActivateView=Mock(return_value=True),
    )
    app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    return SimpleNamespace(currentModel=model, swApp=app), view, annotations, displays


def test_radial_variant_selects_exact_five_owned_native_dimensions_once(monkeypatch):
    adapter, view, annotations, _ = context(monkeypatch)
    result = probe.arrange_once(
        adapter,
        view,
        TYPES,
        annotations,
        arrangement=probe.Arrangement.RADIAL_SPACE_EVENLY,
    )
    assert result["selected"] == tuple(RADIAL)
    assert result["dimension_types"] == RADIAL
    assert result["alignment"] == "SpaceEvenly"
    assert result["alignment_value"] == 1
    assert result["arrangement"] == "radial_space_evenly"
    adapter.currentModel.Extension.AlignDimensions.assert_called_once_with(1, 0.001)
    assert adapter.currentModel.Extension.SelectByID2.call_count == 5
    assert adapter.currentModel.ClearSelection2.call_count == 2


def test_original_autoarrange_still_selects_all_ten_in_one_native_call(monkeypatch):
    adapter, view, annotations, _ = context(monkeypatch)
    result = probe.arrange_once(adapter, view, TYPES, annotations)
    assert result["selected"] == tuple(TYPES)
    assert result["dimension_types"] == TYPES
    assert result["alignment"] == "AutoArrange"
    adapter.currentModel.Extension.AlignDimensions.assert_called_once_with(0, 0.001)


@pytest.mark.parametrize("name", ["FulcrumDia", "RD5", "TipCentreX"])
def test_fresh_native_type_must_match_captured_semantic_type_even_unselected(
    monkeypatch, name
):
    adapter, view, annotations, displays = context(monkeypatch)
    displays[name].Type2 = 3
    with pytest.raises(RuntimeError, match="dimension type"):
        probe.arrange_once(
            adapter,
            view,
            TYPES,
            annotations,
            arrangement=probe.Arrangement.RADIAL_SPACE_EVENLY,
        )
    adapter.currentModel.Extension.AlignDimensions.assert_not_called()
    assert adapter.currentModel.ClearSelection2.call_count == 2


@pytest.mark.parametrize(
    "fault", ["empty", "missing", "extra_radial", "unknown", "bool", "float"]
)
def test_empty_unsupported_or_changed_radial_family_refused_before_native_selection(
    monkeypatch, fault
):
    adapter, view, annotations, _ = context(monkeypatch)
    types = dict(TYPES)
    if fault == "empty":
        types.clear()
    if fault == "missing":
        del types["FulcrumDia"]
    if fault == "extra_radial":
        types["TipCentreX"] = 5
    if fault == "unknown":
        types["RD5"] = 0
    if fault == "bool":
        types["RD5"] = True
    if fault == "float":
        types["RD5"] = 6.0
    with pytest.raises(ValueError):
        probe.arrange_once(
            adapter,
            view,
            types,
            annotations,
            arrangement=probe.Arrangement.RADIAL_SPACE_EVENLY,
        )
    adapter.currentModel.Extension.SelectByID2.assert_not_called()
    adapter.currentModel.Extension.AlignDimensions.assert_not_called()


def test_unselected_linear_annotation_cannot_be_replaced_silently(monkeypatch):
    adapter, view, annotations, _ = context(monkeypatch)
    handles = {**annotations, "TipCentreX": object()}
    with pytest.raises(RuntimeError, match="replaced"):
        probe.arrange_once(
            adapter,
            view,
            TYPES,
            handles,
            arrangement=probe.Arrangement.RADIAL_SPACE_EVENLY,
        )
    adapter.currentModel.Extension.AlignDimensions.assert_not_called()


def test_native_false_is_not_followed_by_autoarrange_or_another_candidate(monkeypatch):
    adapter, view, annotations, _ = context(monkeypatch)
    adapter.currentModel.Extension.AlignDimensions.return_value = False
    with pytest.raises(RuntimeError, match="SpaceEvenly rejected"):
        probe.arrange_once(
            adapter,
            view,
            TYPES,
            annotations,
            arrangement=probe.Arrangement.RADIAL_SPACE_EVENLY,
        )
    adapter.currentModel.Extension.AlignDimensions.assert_called_once_with(1, 0.001)


def test_selector_requires_enum_before_any_native_selection(monkeypatch):
    adapter, view, annotations, _ = context(monkeypatch)
    with pytest.raises(ValueError, match="arrangement"):
        probe.arrange_once(
            adapter, view, TYPES, annotations, arrangement="radial_space_evenly"
        )
    adapter.currentModel.Extension.SelectByID2.assert_not_called()


def test_parent_forwards_exact_selected_variant_without_running_worker(
    monkeypatch, tmp_path
):
    import dodo

    receipt = tmp_path / "receipt.json"
    receipt.touch()
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", "31860")
    monkeypatch.setattr(probe, "read_inputs", Mock())
    runner = Mock()
    monkeypatch.setattr(dodo, "_run", runner)
    assert (
        probe.main(["--receipt", str(receipt), "--arrangement", "radial_space_evenly"])
        == 0
    )
    command = runner.call_args.args[0]
    assert command[command.index("--arrangement") + 1] == "radial_space_evenly"
    assert command.count("--worker") == 1
    assert runner.call_args.kwargs["com"] is True


def test_unknown_cli_variant_rejected_before_receipt_or_native_wrapper(monkeypatch):
    inputs = Mock()
    monkeypatch.setattr(probe, "read_inputs", inputs)
    with pytest.raises(SystemExit):
        probe.main(["--receipt", "not-opened.json", "--arrangement", "stagger_radial"])
    inputs.assert_not_called()


@pytest.mark.parametrize("variant", tuple(probe.Arrangement))
@pytest.mark.parametrize("view", [probe.VIEW, "Sheet1/Drawing View3"])
def test_selected_subset_never_exempts_remaining_other_dimension_or_view_crossings(
    variant, view
):
    with pytest.raises(RuntimeError, match="leaves dimension"):
        probe.require_clearance(
            {view: [{"leader_annotation": "RD1", "target_annotation": "datum A"}]},
            variant,
        )


@pytest.mark.parametrize("section", ["checked", "dimensions", "semantic_attachments"])
def test_native_semantic_or_dimension_change_rejected_even_for_selected_radial(section):
    before = {
        "semantics": {
            name: {}
            for name in (
                "checked",
                "excluded",
                "models",
                "dimensions",
                "dimensions_excluded",
                "semantic_attachments",
            )
        },
        "layout": {},
        "annotations": {},
    }
    after = deepcopy(before)
    after["semantics"][section]["FulcrumDia"] = "changed actual witness"
    with pytest.raises(RuntimeError, match="attachment snapshot changed"):
        probe.compare_arranged(
            SimpleNamespace(), before, after, {}, {}, {"Drawing View1/FulcrumDia"}
        )


def test_unselected_linear_movement_is_not_accepted_as_radial_arrangement(monkeypatch):
    before = {
        "semantics": {
            name: {}
            for name in (
                "checked",
                "excluded",
                "models",
                "dimensions",
                "dimensions_excluded",
                "semantic_attachments",
            )
        },
        "layout": {},
        "annotations": {},
    }
    monkeypatch.setattr(
        probe.pilot.shoulder,
        "compare_all_annotation_layout",
        lambda *_: {"Drawing View1/TipCentreX": "position changed"},
    )
    with pytest.raises(RuntimeError, match="unselected annotation"):
        probe.compare_arranged(
            SimpleNamespace(swApp=object()),
            before,
            before,
            {},
            {},
            {f"Drawing View1/{name}" for name in RADIAL},
        )


def test_required_recipe_gate_enrolls_radial_variant_tests():
    import dodo

    task = next(item for item in dodo.task_check() if item["name"] == "recipe")
    command = task["actions"][0][1][0]
    assert str(Path(__file__).resolve()) in command
    assert str(Path(__file__).resolve()) in task["file_dep"]
