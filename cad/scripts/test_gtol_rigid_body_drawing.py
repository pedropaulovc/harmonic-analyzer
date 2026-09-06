"""Diagnostic wrappers observe production guards and always restore hooks."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import probe_gtol_rigid_body as probe
from _drawing_view_packing import Rect
from test_native_gtol_drawing import native_context


def test_body_mismatch_reports_actual_prediction_and_error_vector(monkeypatch):
    adapter, view, rows, measure = native_context(monkeypatch, count=1)
    bank = probe.layout._read_gtols(adapter, view, measure)
    current = bank["GTol0"]
    changed = replace(current, body=current.body.translated((0.01, 0)))
    with pytest.raises(
        RuntimeError, match="predicted=.*measured=.*delta_m=.*position="
    ):
        probe.layout._assert_measured_prediction(bank, {"GTol0": changed})


def test_position_mismatch_reports_both_native_positions(monkeypatch):
    adapter, view, rows, measure = native_context(monkeypatch, count=1)
    bank = probe.layout._read_gtols(adapter, view, measure)
    changed = replace(bank["GTol0"], position=(0.8, 0.8, 0))
    with pytest.raises(RuntimeError, match="position drifted: predicted=.*measured="):
        probe.layout._assert_measured_prediction(bank, {"GTol0": changed})


def state():
    return SimpleNamespace(
        position=(0.1, 0.1, 0),
        body=Rect(0.1, 0.08, 0.13, 0.1),
        frames=("<frame/>",),
        text=("0.05", "DATUM B SIDE"),
        text_format=("Century Gothic", 0.0035),
        entity_types=(2,),
        owner_type=0,
    )


def test_wrappers_preserve_original_calls_and_capture_native_stages(monkeypatch):
    bank = {"GTol": state()}
    originals = {
        "_read_gtols": Mock(return_value=bank),
        "_native_command": Mock(),
        "_move_bank": Mock(return_value=bank),
        "_assert_measured_prediction": Mock(
            side_effect=RuntimeError("real rigidity failure")
        ),
    }
    for name, function in originals.items():
        monkeypatch.setattr(probe.layout, name, function)
    adapter, drawing = object(), object()
    view = SimpleNamespace(GetName2=lambda: "native-view")
    report = {"steps": []}
    capture = Mock(return_value={"GTol": {"native": "full primitives"}})
    with pytest.raises(RuntimeError, match="real rigidity failure"):
        with probe.capture_stages(adapter, report, capture):
            assert probe.layout._read_gtols(adapter, view, object()) is bank
            probe.layout._native_command(adapter, drawing, view, bank, 307)
            assert (
                probe.layout._move_bank(bank, {"GTol": (0.01, 0)}, "minimum clearance")
                is bank
            )
            probe.layout._assert_measured_prediction(bank, bank)
    assert [row["stage"] for row in report["steps"]] == [
        "initial_witness",
        "native_command",
        "minimum clearance",
    ]
    assert report["predicted_final"] == report["measured_final"]
    assert capture.call_count == 3
    for name, function in originals.items():
        assert getattr(probe.layout, name) is function
        function.assert_called_once()


def test_observer_read_error_propagates_and_does_not_mask_real_guard(monkeypatch):
    originals = {
        name: getattr(probe.layout, name)
        for name in (
            "_read_gtols",
            "_native_command",
            "_move_bank",
            "_assert_measured_prediction",
        )
    }
    with pytest.raises(ValueError, match="capture failed"):
        with probe.capture_stages(object(), {"steps": []}):
            raise ValueError("capture failed")
    assert all(
        getattr(probe.layout, name) is function for name, function in originals.items()
    )
