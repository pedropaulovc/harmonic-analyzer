"""Bounded zero-Z serialization is distinct from coordinate or identity drift."""

from copy import deepcopy
import json
import math
from pathlib import Path

import pytest

from diagnostics._reopen_annotation_comparison import (
    MAX_COORDINATE_DELTA_M,
    MAX_COORDINATE_ULPS,
    compare_reopened_annotations,
)
from diagnostics.audit_drawing_snapshot_delta import changed_leaves


FIXTURE = (
    Path(__file__).parents[1] / "docs/pipeline/evidence/crankshaft-43xc6f6u-zero-z.json"
)
PATHS = ("position", "text", "line_start", "line_end")


def inventory(vector, path="position"):
    if path == "position":
        return {"a": {"position": vector}}
    if path == "text":
        return {"a": {"generic": {"texts": [{"position": vector}]}}}
    start, end = (vector, [0.4, 0.5, 0.006])
    if path == "line_end":
        start, end = end, start
    return {"a": {"generic": {"lines": [[0.0] * 4 + start + end]}}}


def test_retained_fifteen_z_transitions_keep_raw_values_and_other_ink_exact():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    before, after = fixture["built"], fixture["reopened"]
    result = compare_reopened_annotations(before, after)
    assert result["status"] == "passed"
    assert result["rejected"] == []
    assert result["coordinate_roundoff"] == []
    assert len(result["zero_z_serialization"]) == 15
    actual = result["zero_z_serialization"]
    original = fixture["original_rejected"]
    assert [row["path"] for row in actual] == [row["path"] for row in original]
    for row, rejected in zip(actual, original, strict=True):
        for field in ("before", "after", "delta"):
            assert row[field] == rejected[field]
        assert abs(row["delta"]) <= row["coordinate_budget_m"] <= MAX_COORDINATE_DELTA_M
        assert row["vector_scale_m"] > 0.08
    # An exact same-session/audit comparison still retains all fifteen changes.
    assert len(changed_leaves(before, after)) == 15
    fcf = before["Drawing View2/DetailItem352"]
    assert fcf["position"][2] == 0.004762500000000003


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("scale", [0.016, 1000.0])
@pytest.mark.parametrize("zero", [0.0, -0.0])
@pytest.mark.parametrize("direction", ["to_zero", "from_zero"])
def test_zero_z_budget_boundary_and_nextafter(path, scale, zero, direction):
    budget = min(MAX_COORDINATE_DELTA_M, MAX_COORDINATE_ULPS * math.ulp(scale))
    before, after = (
        inventory([scale, scale / 2, -budget], path),
        inventory([scale, scale / 2, zero], path),
    )
    if direction == "from_zero":
        before, after = after, before
    result = compare_reopened_annotations(before, after)
    assert result["status"] == "passed"
    assert len(result["zero_z_serialization"]) == 1
    assert result["zero_z_serialization"][0]["coordinate_budget_m"] == budget
    outside = inventory([scale, scale / 2, -math.nextafter(budget, math.inf)], path)
    zero_bank = inventory([scale, scale / 2, zero], path)
    if direction == "from_zero":
        outside, zero_bank = zero_bank, outside
    result = compare_reopened_annotations(outside, zero_bank)
    assert result["status"] == "failed"
    assert result["zero_z_serialization"] == []


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("axis", [0, 1])
def test_even_one_ulp_xy_change_disallows_special_z_rule(path, axis):
    before = [0.2, 0.1, 1e-32]
    after = [0.2, 0.1, 0.0]
    after[axis] = math.nextafter(after[axis], math.inf)
    result = compare_reopened_annotations(
        inventory(before, path), inventory(after, path)
    )
    assert result["status"] == "failed"
    assert result["zero_z_serialization"] == []


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("new_z", [2e-32, -1e-32, 0.0047625])
def test_nonzero_to_nonzero_drift_never_gets_vector_budget(path, new_z):
    result = compare_reopened_annotations(
        inventory([0.2, 0.1, 1e-32], path), inventory([0.2, 0.1, new_z], path)
    )
    assert result["status"] == "failed"
    assert result["zero_z_serialization"] == []


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("bad_component", [0, False, None, "0"])
def test_nonfloat_vector_component_disallows_zero_z_budget(path, bad_component):
    before, after = [bad_component, 0.1, 1e-32], [bad_component, 0.1, 0.0]
    result = compare_reopened_annotations(
        inventory(before, path), inventory(after, path)
    )
    assert result["status"] == "failed"
    assert result["zero_z_serialization"] == []


@pytest.mark.parametrize("size", [1, 2, 4])
def test_incomplete_or_oversized_position_has_no_zero_z_budget(size):
    before, after = [0.2, 0.1, 1e-32, 0.0], [0.2, 0.1, 0.0, 0.0]
    result = compare_reopened_annotations(
        inventory(before[:size]), inventory(after[:size])
    )
    assert result["zero_z_serialization"] == []
    assert result["status"] == ("failed" if size == 4 else "passed")


@pytest.mark.parametrize("size", [7, 9, 11])
def test_line_must_have_exact_documented_ten_slots(size):
    before, after = (
        inventory([0.2, 0.1, 1e-32], "line_start"),
        inventory([0.2, 0.1, 0.0], "line_start"),
    )
    for bank in (before, after):
        line = bank["a"]["generic"]["lines"][0]
        bank["a"]["generic"]["lines"][0] = (line + [0.0])[:size]
    result = compare_reopened_annotations(before, after)
    assert result["status"] == "failed"
    assert result["zero_z_serialization"] == []


@pytest.mark.parametrize("mutation", ["style", "plane", "semantics", "arc", "unknown"])
def test_special_zero_z_category_cannot_hide_other_changes(mutation):
    before, after = inventory([0.2, 0.1, 1e-32]), inventory([0.2, 0.1, 0.0])
    additions = {
        "style": {"native": {"lines": [{"width_m": 1e-32}]}},
        "plane": {"generic": {"texts": [{"plane": [1e-32]}]}},
        "semantics": {"semantic": {"value": 1e-32}},
        "arc": {"generic": {"arcs": [[1e-32]]}},
        "unknown": {"unknown": {"position": [0.2, 0.1, 1e-32]}},
    }
    before["other"] = additions[mutation]
    # Only the test's extra numeric leaf changes, never a source value in production.
    after["other"] = json.loads(json.dumps(before["other"]).replace("1e-32", "0.0"))
    result = compare_reopened_annotations(before, after)
    assert result["status"] == "failed"
    assert len(result["zero_z_serialization"]) == 1
    assert len(result["rejected"]) == 1


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_xy_is_rejected_before_zero_z_classification(value):
    with pytest.raises(ValueError, match="nonfinite"):
        compare_reopened_annotations(
            inventory([value, 0.1, 1e-32]), inventory([value, 0.1, 0.0])
        )


def test_container_type_change_remains_fatal():
    before, after = inventory([0.2, 0.1, 1e-32]), inventory((0.2, 0.1, 0.0))
    result = compare_reopened_annotations(before, after)
    assert result["status"] == "failed"
    assert result["zero_z_serialization"] == []


def test_zero_z_rule_does_not_round_inputs():
    before, after = inventory([0.2, 0.1, 1e-32]), inventory([0.2, 0.1, 0.0])
    originals = deepcopy((before, after))
    compare_reopened_annotations(before, after)
    assert (before, after) == originals
