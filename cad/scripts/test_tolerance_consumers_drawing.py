"""Current native tolerance ABI reaches both later-stack diagnostic consumers."""

import json
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import _model_dimension_coverage as coverage
from diagnostics import _source_dimension_snapshot as source
from test_source_save_boundaries_drawing import bank as bank


@pytest.fixture(params=["model_parameter", "save_boundary"])
def consumer(request, bank, monkeypatch):
    native = NS(
        Type=2,
        GetMinValue2=Mock(return_value=(0, -0.00004)),
        GetMaxValue2=Mock(return_value=(0, -0.00002)),
        GetMinValue=Mock(side_effect=AssertionError("obsolete minimum getter")),
        GetMaxValue=Mock(side_effect=AssertionError("obsolete maximum getter")),
    )
    bank.dimension.Tolerance = bank.native_tol = native
    bank.dimension.GetToleranceType = lambda: native.Type
    bank.dimension.Name = "ArborBoreDia"
    bank.dimension.GetType = lambda: 0
    monkeypatch.setattr(coverage, "_early_bound", lambda value, _: value)
    if request.param == "model_parameter":
        read = lambda: coverage._parameter(bank.dimension, "Default")
        keys = ("tolerance_min", "tolerance_max")
    else:
        read = lambda: bank.observer.capture("test")["tolerance"]
        keys = ("minimum", "maximum")
    return NS(native=native, read=read, keys=keys, bank=bank)


@pytest.mark.parametrize("kind,status", [(2, 0), (0, 1), (1, 1)])
def test_current_native_tuple_keeps_scalar_keys_and_exact_applicability(
    consumer, kind, status
):
    c = consumer
    c.native.Type = kind
    c.native.GetMinValue2.return_value = (status, -0.0)
    c.native.GetMaxValue2.return_value = (status, 0.0)
    row = c.read()
    assert row["tolerance_type"] == kind
    assert row["designation"] == ("basic" if kind == 1 else "other")
    for key, value in zip(c.keys, (-0.0, 0.0), strict=True):
        assert type(row[key]) is float and row[key].hex() == value.hex()
        assert row[f"{key}_status"] is source.ToleranceValueStatus(status)
        assert json.loads(json.dumps(row))[f"{key}_status"] == status
    c.native.GetMinValue2.assert_called_once_with()
    c.native.GetMaxValue2.assert_called_once_with()
    c.native.GetMinValue.assert_not_called()
    c.native.GetMaxValue.assert_not_called()


@pytest.mark.parametrize("bound", ["Min", "Max"])
@pytest.mark.parametrize(
    "returned",
    [
        None,
        (),
        (0,),
        (0, 0.0, 0.0),
        [0, 0.0],
        (False, 0.0),
        (True, 0.0),
        (0.0, 0.0),
        ("0", 0.0),
        (-1, 0.0),
        (2, 0.0),
        (0, False),
        (0, True),
        (0, 0),
        (0, "0.0"),
        (0, float("nan")),
        (1, float("inf")),
    ],
)
def test_consumers_refuse_malformed_status_value_without_legacy_retry(
    consumer, bound, returned
):
    c = consumer
    getattr(c.native, f"Get{bound}Value2").return_value = returned
    with pytest.raises(RuntimeError, match="source tolerance"):
        c.read()
    c.native.GetMinValue.assert_not_called()
    c.native.GetMaxValue.assert_not_called()


@pytest.mark.parametrize("bound", ["Min", "Max"])
def test_consumers_preserve_original_native_error(consumer, bound):
    c = consumer
    primary = RuntimeError("native tolerance read failed")
    getattr(c.native, f"Get{bound}Value2").side_effect = primary
    with pytest.raises(RuntimeError) as caught:
        c.read()
    assert caught.value is primary
    c.native.GetMinValue.assert_not_called()
    c.native.GetMaxValue.assert_not_called()


@pytest.mark.parametrize("bound", ["Min", "Max"])
@pytest.mark.parametrize("initial_status,final_status", [(0, 1), (1, 0)])
def test_save_boundary_rejects_status_only_change_and_retains_failed_bank(
    bank, bound, initial_status, final_status
):
    bank.native_tol.GetMinValue2 = Mock(return_value=(0, 0.0))
    bank.native_tol.GetMaxValue2 = Mock(return_value=(0, 0.0))
    getter = getattr(bank.native_tol, f"Get{bound}Value2")
    getter.return_value = (initial_status, 0.0)
    bank.observer.capture("initial")
    getter.return_value = (final_status, 0.0)
    with pytest.raises(RuntimeError, match="tolerance limits changed"):
        bank.observer.capture("after_native_save")
    row = bank.saved[-1]["source_boundaries"]["banks"][-1]
    key = "minimum" if bound == "Min" else "maximum"
    assert row["tolerance"][key] == 0.0
    assert row["tolerance"][f"{key}_status"] == final_status
    assert "tolerance limits changed" in row["error"]
    assert row["read_seconds"] >= 0


@pytest.mark.parametrize("bound", ["Min", "Max"])
def test_save_boundary_preserves_not_applicable_raw_value_changes(bank, bound):
    bank.native_tol.Type = 1
    bank.native_tol.GetMinValue2 = Mock(return_value=(1, 0.0))
    bank.native_tol.GetMaxValue2 = Mock(return_value=(1, 0.0))
    bank.observer.capture("initial")
    getattr(bank.native_tol, f"Get{bound}Value2").return_value = (1, 1e-20)
    with pytest.raises(RuntimeError, match="tolerance limits changed"):
        bank.observer.capture("after_precision")
    key = "minimum" if bound == "Min" else "maximum"
    row = bank.saved[-1]["source_boundaries"]["banks"][-1]
    assert row["tolerance"][key] == 1e-20
    assert row["tolerance"][f"{key}_status"] == 1
