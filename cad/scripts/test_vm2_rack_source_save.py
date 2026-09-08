"""Offline contracts for the rack source-write diagnostic, not native proof."""

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
