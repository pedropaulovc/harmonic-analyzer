"""The offline delta report must never turn a difference into acceptance."""

import math

import pytest

from diagnostics.audit_drawing_snapshot_delta import audit_pair, changed_leaves


def test_exact_numeric_deltas_keep_tiny_and_material_text_changes():
    before = {"annotations": {"Sheet1/Title": {"generic": {"x": 0.35}}}}
    after = {"annotations": {"Sheet1/Title": {"generic": {"x": 0.357}}}}
    report = audit_pair(before, after)
    assert report["changed_leaf_count"] == 1
    assert report["differences"][0]["path"] == "/annotations/Sheet1~1Title/generic/x"
    assert report["by_annotation"]["Sheet1/Title"]["max_absolute_numeric_delta"] > 0.006
    assert changed_leaves([0.1], [math.nextafter(0.1, math.inf)])[0]["delta"] > 0


def test_type_enum_string_inventory_and_array_shape_are_not_numeric_noise():
    before = {"flag": True, "kind": 2, "text": "A", "rows": [1], "old": {"x": 2}}
    after = {"flag": 1, "kind": 5, "text": "B", "rows": [1, 2], "new": {"x": 2}}
    rows = changed_leaves(before, after)
    assert {row["kind"] for row in rows} == {
        "type",
        "numeric",
        "value",
        "length",
        "missing",
    }
    assert next(row for row in rows if row["path"] == "/flag")["kind"] == "type"
    assert next(row for row in rows if row["path"] == "/kind")["delta"] == 3
    assert {row["path"] for row in rows if row["kind"] == "missing"} == {
        "/new/x",
        "/old/x",
        "/rows/1",
    }


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_snapshot_is_not_summarized_as_an_equal_witness(value):
    with pytest.raises(ValueError, match="nonfinite"):
        changed_leaves({"value": value}, {"value": value})


def test_complete_tree_and_original_comparator_subset_are_reported_separately():
    row = {"generic": {"texts": [{"position": [1.0]}]}, "native": {"position": [1.0]}}
    changed = {
        "generic": {"texts": [{"position": [2.0]}]},
        "native": {"position": [2.0]},
    }
    result = audit_pair({"annotations": {"a": row}}, {"annotations": {"a": changed}})
    assert result["changed_leaf_count"] == 2
    assert result["generic_or_anchor_changed_leaf_count"] == 1
    assert result["semantics_equal"] is True
