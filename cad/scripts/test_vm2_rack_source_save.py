"""Offline contracts for the rack source-write diagnostic, not native proof."""

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from diagnostics.probe_vm2_rack_source_save import (
    assert_manufacturing_preserved,
    instrument_attempt,
    manufacturing_state,
)


def test_tolerance_readback_includes_type_and_both_deviations():
    tolerance = SimpleNamespace(Type=2, GetMinValue=lambda: 0.00003,
                                GetMaxValue=lambda: 0.00006)
    dimension = SimpleNamespace(SystemValue=0.005, Tolerance=tolerance)
    assert manufacturing_state(dimension, lambda value, _kind: value, getattr) == {
        "system_value_m": 0.005, "tolerance_type": 2,
        "tolerance_min_m": 0.00003, "tolerance_max_m": 0.00006,
    }


@pytest.mark.parametrize("minimum,maximum", [(float("nan"), 0.1), (0.1, float("inf")), (0.2, 0.1)])
def test_tolerance_readback_rejects_invalid_limits(minimum, maximum):
    tolerance = SimpleNamespace(Type=2, GetMinValue=lambda: minimum,
                                GetMaxValue=lambda: maximum)
    with pytest.raises(RuntimeError):
        manufacturing_state(SimpleNamespace(SystemValue=0.005, Tolerance=tolerance),
                            lambda value, _kind: value, getattr)


@pytest.mark.parametrize("field", ["system_value_m", "tolerance_type", "tolerance_min_m", "tolerance_max_m"])
def test_preservation_rejects_each_manufacturing_change(field):
    baseline = {"system_value_m": 0.005, "tolerance_type": 2,
                "tolerance_min_m": 0.00003, "tolerance_max_m": 0.00006}
    assert_manufacturing_preserved(baseline, dict(baseline))
    changed = dict(baseline)
    changed[field] += 0.000001
    with pytest.raises(RuntimeError, match="nominal/tolerance changed"):
        assert_manufacturing_preserved(baseline, changed)


def test_checkpoint_readback_getters_do_not_recurse_into_checkpoint():
    events = []
    native = SimpleNamespace(GetDimension=lambda: "dimension", SetText=lambda *_args: None)

    def checkpoint(label):
        events.append(label)
        assert observed(lambda: native.GetDimension()) == "dimension"

    observed = instrument_attempt(lambda operation, **_kwargs: operation(), checkpoint)
    assert observed(lambda: native.SetText(4, "THRU - REAM")) is None
    assert events == ["before:COM:SetText", "after:COM:SetText"]


def test_read_only_attempt_keeps_original_arguments_and_return():
    calls = []

    def original(operation, *args, **kwargs):
        calls.append((operation(), args, kwargs))
        return "original-result"

    observed = instrument_attempt(original, lambda _label: pytest.fail("getter checkpoint"))
    assert observed(lambda: None, 7, default="missing") == "original-result"
    assert calls == [(None, (7,), {"default": "missing"})]


@pytest.mark.parametrize("method,result", [
    ("SetPosition", False), ("SetPosition", None),
    ("EditRebuild3", False), ("SetPrecision3", -1),
    ("SetPrecision3", 1), ("SetPrecision3", False),
])
def test_named_mutation_rejection_cannot_be_swallowed(method, result):
    native = SimpleNamespace(**{method: lambda *_args: result})
    operations = {
        "SetPosition": lambda: native.SetPosition(0, 0, 0),
        "EditRebuild3": lambda: native.EditRebuild3(),
        "SetPrecision3": lambda: native.SetPrecision3(2, -1, -1, -1),
    }
    observed = instrument_attempt(lambda *_args: pytest.fail("must bypass swallowing wrapper"), lambda _label: None)
    with pytest.raises(RuntimeError, match="rejected"):
        observed(operations[method])


def test_native_exception_propagates_instead_of_becoming_default():
    def fail(*_args):
        raise RuntimeError("native SetText failure")

    native = SimpleNamespace(SetText=fail)
    observed = instrument_attempt(lambda *_args: None, lambda _label: None)
    with pytest.raises(RuntimeError, match="native SetText failure"):
        observed(lambda: native.SetText(4, "THRU - REAM"))


# These are recorded September 8 native controls, not fabricated observations
# of the older uninstrumented 1cce1464 -> 612fda6a event. The originals are
# published byte-for-byte; a missing receipt is a failure, never a skipped test.
EVIDENCE = Path(__file__).resolve().parents[1] / "docs/pipeline/evidence/vm2-datum-placement/probes"
BASELINE = "aa70ef6a9907311ccc78cf3bd5de4252e887a78aeef10a99652037be1161ef90"
RECEIPTS = {
    "full": ("d0720d8798bcd0de3fa6730eeccaebdd4cd05649355f45e7b8df8ed9a3a7bad0", "00a6bbd8a60f64ae4fae5feeadc843e9103026a5ac5642fd596dce5d3f68b1a1"),
    "precision": ("545e1e05b74e47b741fedf36b1e82d44a953f351804fb1ba333578bb047f72f8", BASELINE),
    "callout": ("91a20c4ae69ff5badad933493659abbf043d52b68e9280ff0bfef04fe6f80265", "03543e8283c5ddfccc64d33ebed50ca16fe51df06732a5464329f46cfdc5baff"),
}
RECORDED_MANUFACTURING = {
    "system_value_m": 0.004999999906, "tolerance_type": 2,
    "tolerance_min_m": 2.9999999999999997e-05, "tolerance_max_m": 5e-05,
}


def load_native_receipt(mode):
    payload = (EVIDENCE / f"rack-source-save-{mode}/receipt.json").read_bytes()
    assert hashlib.sha256(payload).hexdigest() == RECEIPTS[mode][0]
    return json.loads(payload)


def expected_checkpoint_labels(mode):
    labels = ["before:open_model", "after:open_model", "before:new_project_drawing",
              "before:COM:SetText", "after:COM:SetText", "after:new_project_drawing"]
    for operation, count in (("place_view", 3), ("set_hidden_lines_removed", 3),
                             ("insert_marked_dimensions", 1), ("delete_unnamed_imports", 1)):
        labels.extend([f"before:{operation}", f"after:{operation}"] * count)
    labels.extend([
        "before:curate_dimensions", "before:COM:SetPosition", "after:COM:SetPosition",
        "before:COM:EditRebuild3", "after:COM:EditRebuild3", "after:curate_dimensions",
    ] * 2)
    for operation, method, included in (
        ("set_dimension_callouts", "SetText", mode != "precision"),
        ("set_dimension_precision", "SetPrecision3", mode != "callout"),
    ):
        if included:
            labels.extend([f"before:{operation}", f"before:COM:{method}",
                           f"after:COM:{method}", f"after:{operation}"])
            continue
        labels.append(f"omitted:{operation}")
    labels.extend(["before:auto_center_marks", "after:auto_center_marks", "before_datum",
                   "before:drawing_rebuild", "after:drawing_rebuild",
                   "before:SaveAs3:SLDDRW", "after:SaveAs3:SLDDRW",
                   "before:SaveAs3:pdf", "after:SaveAs3:pdf", "before:close", "after:close"])
    return labels


def assert_native_causation(receipt, mode):
    assert mode in RECEIPTS and receipt["mode"] == mode
    assert receipt["kind"] == "vm2-rack-reference-save-cause"
    assert receipt["status"] == "observed_and_closed"
    assert receipt["preparation_boundary"] == "before_datum"
    assert receipt["probe_sha256"] == "e13074e7aecda1dddc91d6252c4ea8b08d54b92257aac24790b2d0f375bd0bf4"
    assert receipt["recipe_sha256"] == "95043886df0142cfad60647d3dddaabba05b8c7514b1a8fde121843602599742"
    assert receipt["helper_sha256"] == "d64281f8509c8d1a270c22eb35871bcf5846585c9f8b9c8389d11182c7eece9d"
    assert receipt["adapter"] == "2269009ed56712867826516f4406afc98a0c2814"
    assert receipt["baseline_sha256"] == receipt["baseline_sha256_final"] == BASELINE
    assert receipt["source_sha256_initial"] == BASELINE
    assert receipt["source_sha256_final"] == RECEIPTS[mode][1]
    assert receipt["source_manufacturing_initial"] == RECORDED_MANUFACTURING
    rows = receipt["checkpoints"]
    labels = [row["label"] for row in rows]
    assert labels == expected_checkpoint_labels(mode)
    times = [datetime.fromisoformat(row["utc"]) for row in rows]
    assert times == sorted(times)
    write_index = labels.index("after:SaveAs3:SLDDRW")
    callout_index = labels.index("before:set_dimension_callouts") + 2 if mode != "precision" else len(rows)
    for index, row in enumerate(rows):
        expected_hash = RECEIPTS[mode][1] if index >= write_index else BASELINE
        assert row["source_sha256"] == expected_hash
        if index in (0, len(rows) - 1):
            assert "source_dimension" not in row
            continue
        assert row["source_dirty_before_readback"] is (callout_index <= index < write_index)
        assert row["source_dirty_after_readback"] is row["source_dirty_before_readback"]
        source = row["source_dimension"]
        assert source["manufacturing"] == RECORDED_MANUFACTURING
        assert source["same_as_source_dimension"] == 1
        assert source["full_name"] == "BoreDia@BoreProfile@rack-pinion.Part"
        assert source["text_below"] == ("THRU - REAM" if index >= callout_index else "")
        assert source["primary_precision"] == -2
        for dimension in row["drawing_dimensions"]:
            assert dimension["manufacturing"] == RECORDED_MANUFACTURING
            assert dimension["same_as_source_dimension"] == 1
        if index >= labels.index("after:insert_marked_dimensions"):
            assert len(row["drawing_dimensions"]) == 1
    writes = [row for row in rows if "source_change_copy" in row]
    assert [row["label"] for row in writes] == ([] if mode == "precision" else ["after:SaveAs3:SLDDRW"])
    assert len(receipt["exports"]) == 2
    for export in receipt["exports"]:
        assert type(export["return"]) is int and export["return"] == 0
    assert receipt["closed_without_explicit_save"] == [receipt["exports"][0]["path"], receipt["source"]]


@pytest.mark.parametrize("mode", RECEIPTS)
def test_published_native_controls_pin_settext_dirtying_and_native_save(mode):
    assert_native_causation(load_native_receipt(mode), mode)


@pytest.mark.parametrize("damage", [
    "missing_checkpoint", "unknown_checkpoint", "stale_probe", "dirty_on_open",
    "dirty_from_readback", "dirty_before_settext", "write_before_native_save",
    "write_at_pdf", "tolerance_change", "nominal_change", "wrong_dimension",
    "no_change_snapshot", "save_rejected", "missing_closure",
])
def test_real_receipt_causation_rejects_missing_or_contradictory_evidence(damage):
    receipt = deepcopy(load_native_receipt("full"))
    rows = receipt["checkpoints"]
    labels = [row["label"] for row in rows]
    if damage == "missing_checkpoint":
        rows.pop(labels.index("before:SaveAs3:SLDDRW"))
    elif damage == "unknown_checkpoint":
        rows[1]["label"] = "unknown"
    elif damage == "stale_probe":
        receipt["probe_sha256"] = "0" * 64
    elif damage == "dirty_on_open":
        rows[1]["source_dirty_before_readback"] = True
    elif damage == "dirty_from_readback":
        rows[1]["source_dirty_after_readback"] = True
    elif damage == "dirty_before_settext":
        rows[labels.index("before:set_dimension_callouts")]["source_dirty_before_readback"] = True
    elif damage == "write_before_native_save":
        rows[labels.index("before:SaveAs3:SLDDRW")]["source_sha256"] = receipt["source_sha256_final"]
    elif damage == "write_at_pdf":
        rows[labels.index("after:SaveAs3:SLDDRW")]["source_sha256"] = BASELINE
    elif damage == "tolerance_change":
        rows[-2]["source_dimension"]["manufacturing"]["tolerance_max_m"] = 0.001
    elif damage == "nominal_change":
        rows[-2]["drawing_dimensions"][0]["manufacturing"]["system_value_m"] = 0.006
    elif damage == "wrong_dimension":
        rows[-2]["drawing_dimensions"][0]["same_as_source_dimension"] = 0
    elif damage == "no_change_snapshot":
        del rows[labels.index("after:SaveAs3:SLDDRW")]["source_change_copy"]
    elif damage == "save_rejected":
        receipt["exports"][0]["return"] = 1
    elif damage == "missing_closure":
        receipt["closed_without_explicit_save"] = []
    with pytest.raises(AssertionError):
        assert_native_causation(receipt, "full")


def test_precision_control_rejects_a_source_dirty_transition():
    receipt = deepcopy(load_native_receipt("precision"))
    row = next(row for row in receipt["checkpoints"] if row["label"] == "after:COM:SetPrecision3")
    row["source_dirty_before_readback"] = row["source_dirty_after_readback"] = True
    with pytest.raises(AssertionError):
        assert_native_causation(receipt, "precision")
