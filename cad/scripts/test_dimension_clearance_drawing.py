"""Shared final gate retains the original measured all-view dimension contract."""

from types import SimpleNamespace

import pytest

import _drawing_leader_clearance as clearance
from _drawing_annotation_bounds import Segment
from _drawing_view_packing import Rect
from diagnostics import probe_dimension_arrangement as probe


def row(kind, body, *, strokes=(), leaders=(), decorations=(), text="manufacturing"):
    return SimpleNamespace(
        kind=kind,
        body=body,
        native_strokes=strokes,
        native_leader_segments=leaders,
        leader_decorations=decorations,
        text_runs=(SimpleNamespace(value=text),),
    )


@pytest.mark.parametrize("kind", [2, 4, 5, 6, 7])
@pytest.mark.parametrize("ink", ["displayed", "native", "decoration"])
def test_shared_gate_rejects_each_original_foreign_body_type_and_actual_ink(kind, ink):
    stroke = Segment((0.0, 0.005), (0.020, 0.005), 0.0)
    kwargs = {
        "displayed": {"strokes": (stroke,)},
        "native": {"leaders": (stroke,)},
        "decoration": {"decorations": (Rect(0.007, 0.002, 0.013, 0.008),)},
    }[ink]
    rows = {
        "profile": {
            "diameter": row(4, Rect(-0.020, 0.002, -0.010, 0.008), **kwargs),
            "other": row(kind, Rect(0.005, 0.001, 0.015, 0.009)),
        }
    }
    assert clearance.dimension_crossings(rows) == probe.dimension_crossings(rows)
    with pytest.raises(RuntimeError, match='"target_annotation": "other"'):
        clearance.validate_dimension_leader_clearance(rows)


def test_shared_gate_is_same_view_closed_touching_and_exact_name_self_excluding():
    stroke = Segment((0.0, 0.005), (0.010, 0.005), 0.0)
    dimension = row(4, Rect(0.005, 0.001, 0.015, 0.009), strokes=(stroke,))
    rows = {"profile": {"own": dimension}, "holes": {"other": dimension}}
    assert (
        clearance.validate_dimension_leader_clearance(rows)["profile"][
            "dimension_count"
        ]
        == 1
    )
    rows["profile"]["touching"] = row(2, Rect(0.010, 0.005, 0.020, 0.010))
    with pytest.raises(RuntimeError, match="touching"):
        clearance.validate_dimension_leader_clearance(rows)


def test_original_center_mark_exclusion_is_not_extended_to_datums():
    stroke = Segment((0.0, 0.005), (0.010, 0.005), 0.0)
    rows = {
        "front": {
            "dimension": row(4, Rect(-0.020, 0.002, -0.010, 0.008), strokes=(stroke,)),
            "center": row(15, Rect(0.001, 0.001, 0.009, 0.009)),
        }
    }
    assert clearance.dimension_crossings(rows) == {"front": []}
    rows["front"]["center"].kind = 2
    with pytest.raises(RuntimeError, match="center"):
        clearance.validate_dimension_leader_clearance(rows)
