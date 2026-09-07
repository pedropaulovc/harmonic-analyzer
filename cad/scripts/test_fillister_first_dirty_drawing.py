"""Whole-text source visibility is observed, never inferred from a setter call."""

import asyncio
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, call

import pytest

import fillister_screw_spec
from diagnostics import probe_source_dirty_recipe as probe
from diagnostics import _source_dimension_snapshot as snapshot


def test_fillister_target_has_exact_four_required_dimensions(monkeypatch):
    capture = Mock(return_value=({}, {}))
    monkeypatch.setattr(probe, "_source_snapshot", capture)
    app, model, path = object(), object(), Path("owned.SLDPRT")
    selected = probe.Target("fillister_screw")
    probe.dimension_snapshot(app, model, path, target=selected)
    capture.assert_called_once_with(
        app, model, path, required=fillister_screw_spec.DRAWING_DIMENSIONS
    )
    assert probe.TARGETS[selected].copy_prefix == "fillister-screw"
    assert fillister_screw_spec.DRAWING_DIMENSIONS == {
        "HeadProfile": {"HeadDia"},
        "ShankProfile": {"ShankDia"},
        "Head": {"HeadHt"},
        "Shank": {"ShankLg"},
    }


def test_fillister_worker_forwards_target_pin_and_exact_source(monkeypatch, tmp_path):
    source = tmp_path / "fillister-screw.SLDPRT"
    source.write_bytes(b"owned test input")
    monkeypatch.setattr(probe, "require_owned_diagnostic_environment", lambda: None)
    monkeypatch.setattr(probe.benchmark, "revision", lambda _: "f" * 40)
    operation = AsyncMock()
    monkeypatch.setattr(probe, "probe", operation)
    adapter = object()
    monkeypatch.setattr(
        probe, "run_copy_diagnostic", lambda callback: asyncio.run(callback(adapter))
    )
    probe.main(
        [
            "--worker",
            "--target",
            "fillister_screw",
            "--source",
            str(source),
            "--expected-sha256",
            probe.file_digest(source),
            "--report-root",
            str(tmp_path),
        ]
    )
    operation.assert_awaited_once_with(
        adapter,
        source.resolve(),
        probe.file_digest(source),
        "f" * 40,
        tmp_path.resolve(),
        target=probe.Target.FILLISTER_SCREW,
    )


@pytest.mark.parametrize("show", [True, False])
def test_source_display_preserves_native_visibility_and_all_eight_text_fields(show):
    fields = {index: "#4-40 UNC-2A" if index in (1, 5) else "" for index in range(1, 9)}
    display = NS(
        ShowDimensionValue=show,
        IsHoleCallout=Mock(return_value=False),
        GetText=Mock(side_effect=fields.__getitem__),
    )
    actual = snapshot.display_presentation(display)
    assert actual == {
        "show_dimension_value": show,
        "text": {str(key): value for key, value in fields.items()},
    }
    assert display.GetText.call_args_list == [call(index) for index in range(1, 9)]


@pytest.mark.parametrize("value", [None, 0, 1, "false", object()])
def test_malformed_visibility_readback_fails_without_coercion(value):
    display = NS(ShowDimensionValue=value, IsHoleCallout=Mock(), GetText=Mock())
    with pytest.raises(RuntimeError, match="ShowDimensionValue"):
        snapshot.display_presentation(display)
    display.IsHoleCallout.assert_not_called()
    display.GetText.assert_not_called()


@pytest.mark.parametrize("value", [None, 0, 1, "false"])
def test_malformed_hole_callout_selector_cannot_skip_text_inventory(value):
    display = NS(ShowDimensionValue=True, IsHoleCallout=lambda: value, GetText=Mock())
    with pytest.raises(RuntimeError, match="IsHoleCallout"):
        snapshot.display_presentation(display)
    display.GetText.assert_not_called()


@pytest.mark.parametrize("value", [None, 42, False, ["text"]])
def test_malformed_text_readback_is_not_recast_as_empty_or_string(value):
    display = NS(
        ShowDimensionValue=True, IsHoleCallout=lambda: False, GetText=lambda _: value
    )
    with pytest.raises(RuntimeError, match="GetText"):
        snapshot.display_presentation(display)


def test_hole_callout_exclusion_remains_explicit_with_real_visibility():
    display = NS(ShowDimensionValue=False, IsHoleCallout=lambda: True, GetText=Mock())
    assert snapshot.display_presentation(display) == {
        "show_dimension_value": False,
        "text": {"exclusion": "GetText does not support hole callouts"},
    }
    display.GetText.assert_not_called()


@pytest.mark.parametrize("readback", ["native", "malformed"])
def test_real_whole_text_helper_is_only_an_observed_group_and_never_reaches_save(
    monkeypatch, tmp_path, readback
):
    import _drawing_common as common

    path = tmp_path / "fillister-screw-owned.SLDPRT"
    model = NS(dirty=False)
    model.GetType = lambda: 1
    model.GetPathName = lambda: str(path)
    model.GetSaveFlag = lambda: model.dirty
    app = NS(GetOpenDocumentByName=lambda _: model, IsSame=lambda a, b: int(a is b))
    text = {index: "" for index in range(1, 9)}
    display = NS(
        ShowDimensionValue=True,
        IsHoleCallout=lambda: False,
        GetText=lambda index: text[index],
    )

    def set_text(index, value):
        assert index == 0
        text.update({key: value if key in (1, 5) else "" for key in text})
        display.ShowDimensionValue = False if readback == "native" else 0
        model.dirty = True
        return None  # documented void; not a synthetic success boolean

    display.SetText = Mock(side_effect=set_text)
    annotation = NS(GetSpecificAnnotation=lambda: display)
    monkeypatch.setattr(
        common._sw_type_info, "early_bound_or_flag", lambda value, *_: value
    )
    monkeypatch.setattr(common, "dimension_name", lambda *_: "ShankDia")
    drawing = NS(EditRebuild3=Mock())
    adapter = NS(currentModel=drawing, _attempt=lambda operation: operation())

    def captured(*_, **_kwargs):
        return {
            "dimensions": {
                "ShankDia@ShankProfile": {
                    "native": {"value_system": 0.00226, "tolerance_type": 0},
                    "displays": [snapshot.display_presentation(display)],
                }
            }
        }, {"ShankDia@ShankProfile": model}

    monkeypatch.setattr(probe, "dimension_snapshot", captured)
    report = {"events": []}
    monitor = probe.DirtyMonitor(
        app, model, path, report, lambda: None, target=probe.Target.FILLISTER_SCREW
    )
    finalize, later = AsyncMock(), Mock()
    module = NS(set_dimension_text=common.set_dimension_text, finalize_drawing=finalize)
    original = module.set_dimension_text
    monitor.baseline()
    with pytest.raises(probe.DiagnosticStop):
        with probe.instrument_recipe(module, monitor):
            module.set_dimension_text(
                adapter, [annotation], {"ShankDia": "#4-40 UNC-2A"}
            )
            later()
    display.SetText.assert_called_once_with(0, "#4-40 UNC-2A")
    drawing.EditRebuild3.assert_called_once_with()
    later.assert_not_called()
    finalize.assert_not_called()
    assert module.set_dimension_text is original and module.finalize_drawing is finalize
    stop = report["stop"]
    assert (stop["boundary"], stop["phase"]) == ("recipe.set_dimension_text", "after")
    if readback == "malformed":
        assert "ShowDimensionValue" in stop["capture_error"]
        assert "snapshot" not in stop
        return
    assert stop["dimension_identity"] == {"ShankDia@ShankProfile": "same"}
    before = report["baseline"]["dimensions"]["ShankDia@ShankProfile"]
    after = stop["snapshot"]["dimensions"]["ShankDia@ShankProfile"]
    assert before["native"] == after["native"]
    assert before["displays"][0]["show_dimension_value"] is True
    assert after["displays"][0]["show_dimension_value"] is False
    assert after["displays"][0]["text"] == {
        str(index): "#4-40 UNC-2A" if index in (1, 5) else "" for index in range(1, 9)
    }


def test_fillister_is_not_silently_enrolled_in_full_owned_pilot():
    from diagnostics._recipe_acceptance_targets import TARGETS

    assert "fillister_screw" not in TARGETS
