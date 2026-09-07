"""Only source annotation positions get a bounded cold serialization budget."""

from copy import deepcopy
import json
import math
from pathlib import Path

import pytest

from diagnostics._source_pmi_comparison import compare_source_pmi
from diagnostics._source_dimension_snapshot import compare_source
from diagnostics._reopen_annotation_comparison import (
    MAX_COORDINATE_DELTA_M,
    MAX_COORDINATE_ULPS,
    compare_reopened_annotations,
)
from diagnostics.audit_drawing_snapshot_delta import changed_leaves


FIXTURE = (
    Path(__file__).parents[1]
    / "docs/pipeline/evidence/selected-view-pmi-dw50mqvy-source-cold.json"
)


def captured():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_full_retained_source_has_only_three_near_zero_x_differences():
    receipt = captured()
    first, last = receipt["before"], receipt["after"]
    changes = changed_leaves(first, last)
    assert [row["path"] for row in changes] == [
        f"/pmi/{index}/position_m/0" for index in range(3)
    ]
    assert [row["delta"] for row in changes] == [
        -1.4444474582904269e-33,
        9.860761315262648e-32,
        9.860761315262648e-32,
    ]
    assert [abs(row["delta"]) / math.ulp(row["before"]) for row in changes] == [
        15,
        2048,
        2048,
    ]
    assert compare_source(first["dimensions"], last["dimensions"]) == {}
    cold = compare_source_pmi(first["pmi"], last["pmi"], boundary="cold_reopen")
    assert cold["status"] == "passed"
    assert len(cold["coordinate_roundoff"]) == 3
    assert cold["rejected"] == []
    for actual, raw in zip(cold["coordinate_roundoff"], changes, strict=True):
        assert actual["before"] == raw["before"]
        assert actual["after"] == raw["after"]
        assert actual["delta"] == raw["delta"]
        assert (
            abs(actual["delta"])
            <= actual["coordinate_budget_m"]
            <= MAX_COORDINATE_DELTA_M
        )
    live = compare_source_pmi(first["pmi"], last["pmi"], boundary="same_session")
    assert live["status"] == "failed"
    assert len(live["rejected"]) == 3
    assert live["coordinate_roundoff"] == []


def test_drawing_leaf_comparison_keeps_its_existing_stricter_contract():
    receipt = captured()
    first, last = receipt["before"]["pmi"][1], receipt["after"]["pmi"][1]
    result = compare_reopened_annotations(
        {"drawing_annotation": {"position": first["position_m"]}},
        {"drawing_annotation": {"position": last["position_m"]}},
    )
    assert result["status"] == "failed"


@pytest.mark.parametrize("scale", [0.016, 1000.0])
def test_vector_ulp_and_hard_absolute_caps_both_apply(scale):
    before = [{"position_m": [0.0, scale, 0.0]}]
    budget = min(MAX_COORDINATE_DELTA_M, MAX_COORDINATE_ULPS * math.ulp(scale))
    after = deepcopy(before)
    after[0]["position_m"][0] = budget
    assert (
        compare_source_pmi(before, after, boundary="cold_reopen")["status"] == "passed"
    )
    after[0]["position_m"][0] = math.nextafter(budget, math.inf)
    assert (
        compare_source_pmi(before, after, boundary="cold_reopen")["status"] == "failed"
    )


@pytest.mark.parametrize(
    "fault",
    [
        "type",
        "bool",
        "missing",
        "extra",
        "order",
        "multiplicity",
        "label",
        "tolerance",
        "geometry",
        "owner",
        "coordinate_container",
        "coordinate_type",
    ],
)
def test_cold_position_policy_does_not_waive_any_other_source_pmi_change(fault):
    before = captured()["before"]["pmi"]
    after = deepcopy(before)
    if fault == "type":
        after[0]["type"] = float(after[0]["type"])
    elif fault == "bool":
        after[0]["owner_identity"] = True
    elif fault == "missing":
        del after[0]["visible"]
    elif fault == "extra":
        after[0]["unreviewed"] = 0
    elif fault == "order":
        after.reverse()
    elif fault == "multiplicity":
        after.append(deepcopy(after[0]))
    elif fault == "label":
        after[0]["signature"][1] = "B"
    elif fault == "tolerance":
        after[1]["signature"][1]["tolerance"] = "0.02"
    elif fault == "geometry":
        after[0]["face_spec_matches"] = False
    elif fault == "owner":
        after[0]["owner_identity"] = 0
    elif fault == "coordinate_type":
        before[0]["position_m"][0] = 0.0
        after[0]["position_m"][0] = 0
    else:
        after[0]["position_m"] = tuple(after[0]["position_m"])
    assert (
        compare_source_pmi(before, after, boundary="cold_reopen")["status"] == "failed"
    )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_is_rejected_even_when_unchanged(value):
    rows = [{"position_m": [value, 0.0, 0.0]}]
    with pytest.raises(ValueError, match="nonfinite"):
        compare_source_pmi(rows, deepcopy(rows), boundary="cold_reopen")


def test_source_dimension_and_tolerance_changes_still_fail_the_separate_exact_gate():
    before = captured()["before"]["dimensions"]
    for field in ("value_system", "tolerance_min", "tolerance_max", "tolerance_type"):
        after = deepcopy(before)
        row = next(iter(after["dimensions"].values()))["native"]
        row[field] += 1
        with pytest.raises(RuntimeError, match="value/tolerance/BASIC"):
            compare_source(before, after)
