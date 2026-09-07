"""The extracted initializer preserves the native call sequence and readbacks."""

from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

import _drawing_sheet_setup as setup


def read_member(obj, name):
    value = getattr(obj, name)
    return value() if callable(value) else value


@pytest.fixture
def native(monkeypatch):
    trace = Mock()
    draw, sheet, note = trace.draw, trace.sheet, trace.note
    draw.GetFirstView.return_value = trace.sheet_view
    draw.GetCurrentSheet.return_value = sheet
    trace.sheet_view.GetAnnotations.return_value = [trace.annotation]
    trace.annotation.GetType.return_value = 6
    trace.annotation.GetSpecificAnnotation.return_value = note
    note.GetText.side_effect = [
        setup._OLD_EDGE_BREAK_NOTE,
        setup._METRIC_EDGE_BREAK_NOTE,
    ]
    note.SetText.return_value = True
    draw.Extension.SetUserPreferenceInteger.return_value = True
    draw.Extension.GetUserPreferenceInteger.return_value = 2
    sheet.SetScale.return_value = True
    sheet.GetProperties2.return_value = [0, 0, 2.0, 1.0, 0, 0.4318, 0.2794]
    trace.new_drawing.return_value = draw
    monkeypatch.setattr(setup, "new_drawing", trace.new_drawing)
    monkeypatch.setattr(setup, "set_units_mm", trace.set_units_mm)
    monkeypatch.setattr(setup, "_early_bound", lambda obj, kind: obj)
    monkeypatch.setattr(
        setup._sw_type_info, "early_bound_or_flag", lambda obj, *args: obj
    )
    adapter = SimpleNamespace(
        _get_attr_or_call=read_member,
        _attempt=lambda operation, default=None: operation(),
    )
    return adapter, trace


def test_normal_setup_keeps_exact_native_call_order_values_and_readbacks(native):
    adapter, trace = native
    assert setup.new_project_drawing(adapter, scale=(2, 1), decimals=3) == (
        trace.draw,
        trace.sheet,
    )
    assert trace.mock_calls == [
        call.new_drawing(
            adapter, template=str(setup.PROJECT_DRWDOT), width=0.4318, height=0.2794
        ),
        call.draw.EditSheet(),
        call.draw.GetFirstView(),
        call.sheet_view.GetAnnotations(),
        call.annotation.GetType(),
        call.annotation.GetSpecificAnnotation(),
        call.note.GetText(),
        call.note.SetText(setup._METRIC_EDGE_BREAK_NOTE),
        call.note.GetText(),
        call.draw.GetCurrentSheet(),
        call.set_units_mm(adapter, decimals=3),
        *[
            operation
            for scope in range(200, 210)
            for operation in (
                call.draw.Extension.SetUserPreferenceInteger(372, scope, 2),
                call.draw.Extension.GetUserPreferenceInteger(372, scope),
            )
        ],
        call.sheet.SetScale(2.0, 1.0, True, False),
        call.sheet.GetProperties2(),
        call.draw.ViewZoomtofit2(),
        call.draw.ForceRebuild3(False),
        call.draw.EditRebuild3(),
    ]


@pytest.mark.parametrize("damage", ["set_false", "wrong_readback"])
def test_dimension_style_rejection_stops_before_scale_or_rebuild(native, damage):
    adapter, trace = native
    if damage == "set_false":
        trace.draw.Extension.SetUserPreferenceInteger.return_value = False
    if damage == "wrong_readback":
        trace.draw.Extension.GetUserPreferenceInteger.return_value = 1
    with pytest.raises(RuntimeError, match="failed to pin dimension text/leader style"):
        setup.new_project_drawing(adapter, scale=(2, 1))
    trace.sheet.SetScale.assert_not_called()
    trace.draw.ForceRebuild3.assert_not_called()


@pytest.mark.parametrize(
    "damage", ["missing_note", "duplicate_note", "set_false", "wrong_readback"]
)
def test_edge_break_guards_remain_loud_before_dimension_setup(native, damage):
    adapter, trace = native
    if damage == "missing_note":
        trace.sheet_view.GetAnnotations.return_value = []
    if damage == "duplicate_note":
        trace.sheet_view.GetAnnotations.return_value *= 2
        trace.note.GetText.side_effect = [setup._METRIC_EDGE_BREAK_NOTE] * 2
    if damage == "set_false":
        trace.note.SetText.return_value = False
    if damage == "wrong_readback":
        trace.note.GetText.side_effect = [setup._OLD_EDGE_BREAK_NOTE] * 2
    with pytest.raises(RuntimeError, match="edge-break"):
        setup.new_project_drawing(adapter, scale=(2, 1))
    trace.set_units_mm.assert_not_called()


@pytest.mark.parametrize(
    "damage",
    [
        "no_sheet",
        "scale_set_false",
        "scale_readback",
        "size_readback",
        "short_readback",
    ],
)
def test_sheet_guards_remain_loud_before_viewport_or_rebuild(native, damage):
    adapter, trace = native
    if damage == "no_sheet":
        trace.draw.GetCurrentSheet.return_value = None
    if damage == "scale_set_false":
        trace.sheet.SetScale.return_value = False
    if damage == "scale_readback":
        trace.sheet.GetProperties2.return_value[2] = 1.0
    if damage == "size_readback":
        trace.sheet.GetProperties2.return_value[5] = 0.5
    if damage == "short_readback":
        trace.sheet.GetProperties2.return_value = []
    with pytest.raises(RuntimeError, match=r"sheet|ASME B"):
        setup.new_project_drawing(adapter, scale=(2, 1))
    trace.draw.ViewZoomtofit2.assert_not_called()
    trace.draw.ForceRebuild3.assert_not_called()
