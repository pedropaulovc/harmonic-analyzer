"""Offline safeguards for the late dimension-native-ordering positive control."""

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from diagnostics import probe_dimensions_after_gtol as probe
from _drawing_annotation_bounds import Segment, TextRun
from _drawing_view_packing import Rect


@pytest.mark.parametrize(
    "start,end,intersects",
    [
        ((-1, 0.5), (2, 0.5), True),
        ((0.5, -1), (0.5, 2), True),
        ((-1, -1), (2, 2), True),
        ((2, 2), (-1, -1), True),
        ((-2, -2), (-1, -1), False),
        ((-1, 1.1), (2, 1.1), False),
        ((-1, 1), (2, 1), True),
        ((0.5, 0.5), (0.5, 0.5), True),
        ((1.5, 1.5), (1.5, 1.5), False),
    ],
)
def test_leader_cell_intersection_is_a_bounded_segment_test(start, end, intersects):
    assert probe.segment_intersects_box(start, end, Rect(0, 0, 1, 1)) is intersects


def test_intersection_report_keeps_native_text_and_actual_segment_identity():
    source = SimpleNamespace(kind=5, leader_segments=(Segment((0, 0.5), (2, 0.5)),))
    target = SimpleNamespace(
        kind=4,
        text_runs=(TextRun("127.00", (0.5, 0), 0.0035, "Century Gothic", 0, 1, 0),),
        text_boxes=(Rect(0.5, 0, 1.0, 1),),
    )
    records = probe.leader_text_intersections(
        {"view/control": source, "view/dim": target}
    )
    assert len(records) == 1
    assert records[0]["dimension"] == "view/dim"
    assert records[0]["gtol"] == "view/control"
    assert records[0]["text"] == "127.00"
    assert records[0]["leader_segment_index"] == 0


def test_ambiguous_text_box_mapping_fails_instead_of_guessing():
    source = SimpleNamespace(kind=5, leader_segments=())
    target = SimpleNamespace(kind=4, text_runs=(), text_boxes=(Rect(0, 0, 1, 1),))
    with pytest.raises(RuntimeError, match="text boxes do not match"):
        probe.leader_text_intersections({"control": source, "dim": target})


def test_probe_uses_one_existing_native_arrange_and_no_manual_layout_writes():
    tree = ast.parse(Path(probe.__file__).read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    native_calls = [
        node
        for node in calls
        if isinstance(node.func, ast.Name)
        and node.func.id == "auto_arrange_view_dimensions"
    ]
    assert len(native_calls) == 1
    forbidden = {
        "SetPosition2",
        "SetViewPosition",
        "RunCommand",
        "AlignDimensions",
        "RemoveAlignment",
    }
    assert not [
        node
        for node in calls
        if isinstance(node.func, ast.Attribute) and node.func.attr in forbidden
    ]
    assert any(
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "_run"
        and any(
            keyword.arg == "com"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        )
        for node in calls
    )


def test_real_dimension_semantic_drift_is_not_treated_as_layout_movement(monkeypatch):
    semantics = {
        "checked": {},
        "excluded": {},
        "models": {},
        "dimensions_excluded": {},
        "dimensions": {"dim": {"value_system": 0.127}},
    }
    after_semantics = {**semantics, "dimensions": {"dim": {"value_system": 0.128}}}
    with pytest.raises(RuntimeError, match="dimensions"):
        probe.compare(
            None, {"semantics": semantics}, {"semantics": after_semantics}, {}, "after"
        )
