"""Only mapped drawing coordinates receive a cold-reopen representation budget."""

from copy import deepcopy
import json
import math
from pathlib import Path

import pytest

from diagnostics import _reopen_annotation_comparison as comparison
from diagnostics import probe_datum_shoulder as shoulder
from diagnostics import probe_datum_policy_recipes as pilot
from diagnostics.audit_drawing_snapshot_delta import changed_leaves

AUDIT = (
    Path(__file__).parent.parent
    / "docs/pipeline/evidence/datum-policy-79q2phjn-delta.json"
)


def nested(path, value):
    if not path:
        return value
    token, *rest = path
    if isinstance(token, int):
        return [None] * token + [nested(rest, value)]
    return {token: nested(rest, value)}


def path_tokens(pointer):
    tokens = [
        part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:]
    ]
    return tuple(int(token) if token.isdecimal() else token for token in tokens)


def test_committed_190_leaf_repro_classifies_roundoff_but_rejects_real_title_motion():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    counts = {"passed": 0, "failed": 0}
    for delta in audit["differences"]:
        tokens = path_tokens(delta["path"])[1:]  # inventories start at annotation name
        result = comparison.compare_reopened_annotations(
            nested(tokens, delta["before"]), nested(tokens, delta["after"])
        )
        counts[result["status"]] += 1
        observed = result["rejected"] + result["coordinate_roundoff"]
        assert len(observed) == 1
        assert observed[0]["before"] == delta["before"]
        assert observed[0]["after"] == delta["after"]
        assert observed[0]["delta"] == delta["delta"]
        if result["status"] == "failed":
            assert tokens[0] == "Sheet1/DetailItem245"
            assert abs(delta["delta"]) > 0.007
    assert counts == {"passed": 187, "failed": 3}


@pytest.mark.parametrize(
    "path",
    [
        ("position", 0),
        ("generic", "texts", 0, "position", 2),
        ("generic", "lines", 0, 4),
        ("generic", "lines", 0, 9),
        ("native", "anchor", 1),
        ("native", "note_extent", 0),
        ("native", "text_runs", 0, "position", 0),
        ("native", "lines", 0, "start", 0),
        ("native", "primitive_boxes", 0, "ymax"),
        ("measurement", "native_leader_segments", 0, "end", 1),
        ("measurement", "body", "xmin"),
        ("measurement", "leader_decorations", 0, "ymin"),
    ],
)
def test_mapped_coordinate_budget_is_bounded_and_retains_unrounded_values(path):
    initial = 0.25
    at_budget = initial + comparison.MAX_COORDINATE_ULPS * math.ulp(initial)
    before = {"View/Name": nested(path, initial)}
    accepted = comparison.compare_reopened_annotations(
        before, {"View/Name": nested(path, at_budget)}
    )
    assert accepted["status"] == "passed"
    assert accepted["coordinate_roundoff"][0]["after"] == at_budget
    outside = math.nextafter(at_budget, math.inf)
    assert (
        comparison.compare_reopened_annotations(
            before, {"View/Name": nested(path, outside)}
        )["status"]
        == "failed"
    )


def test_absolute_cap_stays_small_even_for_very_large_coordinates():
    initial = 1000.0
    assert math.ulp(initial) > comparison.MAX_COORDINATE_DELTA_M
    assert (
        comparison.compare_reopened_annotations(
            {"a": {"position": [initial]}},
            {"a": {"position": [math.nextafter(initial, math.inf)]}},
        )["status"]
        == "failed"
    )


def test_missing_ink_tail_retains_its_values_in_failure_report():
    removed = {"value": "A", "position": [0.1, 0.2]}
    report = comparison.compare_reopened_annotations(
        {"a": {"generic": {"texts": [removed]}}},
        {"a": {"generic": {"texts": []}}},
    )
    assert report["status"] == "failed"
    assert [row["kind"] for row in report["rejected"]] == ["length", "missing"]
    assert report["rejected"][1]["before"] == removed
    assert report["rejected"][1]["after"] == {"missing": True}


@pytest.mark.parametrize(
    "path",
    [
        ("semantic", "dimensions", 0, "value"),
        ("semantic", "geometry", 0),
        ("semantic", "kind"),
        ("generic", "lines", 0, 0),
        ("generic", "lines", 0, 1),
        ("generic", "lines", 0, 2),
        ("generic", "lines", 0, 3),
        ("generic", "arcs", 0, 4),
        ("generic", "texts", 0, "height"),
        ("generic", "texts", 0, "angle"),
        ("generic", "texts", 0, "plane", 0),
        ("native", "lines", 0, "width_m"),
        ("native", "text_runs", 0, "height_m"),
        ("native", "format_signature", 1),
        ("unknown", "position", 0),
    ],
)
def test_one_ulp_is_not_waived_in_semantics_style_or_unmapped_fields(path):
    assert (
        comparison.compare_reopened_annotations(
            {"a": nested(path, 0.3)},
            {"a": nested(path, math.nextafter(0.3, math.inf))},
        )["status"]
        == "failed"
    )


@pytest.mark.parametrize("actual", [[0.0, 0.1], (0.0,), [0], [False], [], None])
def test_coordinate_shape_and_numeric_types_remain_exact(actual):
    assert (
        comparison.compare_reopened_annotations(
            {"a": {"position": [0.0]}}, {"a": {"position": actual}}
        )["status"]
        == "failed"
    )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_values_fail_even_when_unchanged(value):
    row = {"a": {"position": (value,)}}
    with pytest.raises(ValueError, match="nonfinite"):
        comparison.compare_reopened_annotations(row, row)


@pytest.mark.parametrize(
    "mutation", ["remove", "reorder", "text", "xml", "font", "support", "inventory"]
)
def test_rendered_ink_semantics_and_inventory_changes_are_not_roundoff(mutation):
    before = {
        "a": {
            "semantic": {"frames": ["<frame>A</frame>"], "font": "Century Gothic"},
            "generic": {
                "texts": [
                    {"value": "A", "position": [0.1, 0.2]},
                    {"value": "B", "position": [0.3, 0.4]},
                ]
            },
            "measurement_exclusion": "unsupported font",
        }
    }
    after = deepcopy(before)
    if mutation == "remove":
        after["a"]["generic"]["texts"].pop()
    if mutation == "reorder":
        after["a"]["generic"]["texts"].reverse()
    if mutation == "text":
        after["a"]["generic"]["texts"][0]["value"] = "C"
    if mutation == "xml":
        after["a"]["semantic"]["frames"] = ["<frame>C</frame>"]
    if mutation == "font":
        after["a"]["semantic"]["font"] = "Arial"
    if mutation == "support":
        after["a"]["measurement_exclusion"] = "missing body"
    if mutation == "inventory":
        after["b"] = after.pop("a")
    assert comparison.compare_reopened_annotations(before, after)["status"] == "failed"


def test_same_session_comparison_and_exact_audit_still_report_one_ulp():
    initial, actual = 0.3, math.nextafter(0.3, math.inf)
    before = {"a": {"semantic": {}, "generic": {}, "position": [initial]}}
    after = {"a": {"semantic": {}, "generic": {}, "position": [actual]}}
    assert len(changed_leaves(before, after)) == 1
    assert shoulder.compare_all_annotation_layout(None, before, after)
    assert comparison.compare_reopened_annotations(before, after)["status"] == "passed"


def test_cold_callsite_keeps_attachment_and_layout_checks(monkeypatch):
    calls = []

    def exact(old, new, stage):
        calls.append(stage)
        if old != new:
            raise RuntimeError("changed attachment or view layout")

    monkeypatch.setattr(pilot.attachments, "compare", exact)
    monkeypatch.setattr(pilot.attachments, "check_layout", exact)
    before = {
        "semantics": {"face_signature": 0.3},
        "layout": {"view_scale": 1.0},
        "annotations": {"a": {"position": [0.3]}},
    }
    after = deepcopy(before)
    after["annotations"]["a"]["position"] = [math.nextafter(0.3, math.inf)]
    assert pilot.compare_drawing_reopen(before, after)["status"] == "passed"
    assert len(calls) == 2
    after["semantics"]["face_signature"] = math.nextafter(0.3, math.inf)
    with pytest.raises(RuntimeError, match="attachment"):
        pilot.compare_drawing_reopen(before, after)


def test_live_export_callsite_still_rejects_one_ulp(monkeypatch):
    monkeypatch.setattr(pilot.attachments, "compare", lambda *_: None)
    monkeypatch.setattr(pilot.attachments, "check_layout", lambda *_: None)
    before = {
        "semantics": {},
        "layout": {},
        "annotations": {"a": {"semantic": {}, "generic": {}, "position": [0.3]}},
    }
    after = deepcopy(before)
    after["annotations"]["a"]["position"] = [math.nextafter(0.3, math.inf)]
    with pytest.raises(RuntimeError, match="annotation layout"):
        pilot.compare_drawing(None, before, after)
