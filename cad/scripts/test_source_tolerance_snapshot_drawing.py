"""Exact current IDimensionTolerance return/validity contract, without COM."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import _source_dimension_snapshot as snapshot


@pytest.fixture
def native_snapshot(monkeypatch, tmp_path):
    native = SimpleNamespace(
        Type=2,
        GetMinValue2=Mock(return_value=(0, 0.000025)),
        GetMaxValue2=Mock(return_value=(0, 0.000055)),
        GetMinValue=Mock(side_effect=AssertionError("obsolete getter called")),
        GetMaxValue=Mock(side_effect=AssertionError("obsolete getter called")),
    )
    path = tmp_path / "owned.SLDPRT"
    dimension = SimpleNamespace(
        FullName="BoreDia@BoreProfile@owned.Part",
        Tolerance=native,
        GetToleranceType=lambda: native.Type,
        GetSystemValue3=lambda *_args: (0.0127,),
    )
    display = SimpleNamespace(
        Type2=6,
        GetDimension2=lambda index: dimension if index == 0 else None,
        MarkedForDrawing=True,
        GetPrimaryPrecision2=lambda: 3,
        GetPrimaryTolPrecision2=lambda: 3,
        IsHoleCallout=lambda: False,
        GetText=lambda _part: "",
    )
    feature = SimpleNamespace(
        Name="BoreProfile",
        GetFirstDisplayDimension=display,
        GetNextDisplayDimension=lambda _display: None,
    )
    model = SimpleNamespace(
        ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="Default")
        )
    )
    monkeypatch.setattr(snapshot, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(snapshot, "_read_member", lambda obj, name: getattr(obj, name))
    monkeypatch.setattr(snapshot, "_iter_features", lambda _adapter: (feature,))

    def capture():
        return snapshot.dimension_snapshot(
            SimpleNamespace(IsSame=lambda a, b: int(a is b)),
            model,
            path,
            required={"BoreProfile": {"BoreDia"}},
        )[0]

    return native, capture


def _native(bank):
    return bank["dimensions"]["BoreDia@BoreProfile@owned.Part"]["native"]


def test_current_getters_preserve_exact_valid_status_and_values(native_snapshot):
    native, capture = native_snapshot
    row = _native(capture())
    assert row["tolerance_min"] == 0.000025
    assert row["tolerance_max"] == 0.000055
    assert row["tolerance_min_status"] == row["tolerance_max_status"] == 0
    native.GetMinValue2.assert_called_once_with()
    native.GetMaxValue2.assert_called_once_with()
    native.GetMinValue.assert_not_called()
    native.GetMaxValue.assert_not_called()


@pytest.mark.parametrize("kind", [0, 1])
def test_basic_and_none_preserve_not_valid_for_type(native_snapshot, kind):
    native, capture = native_snapshot
    native.Type = kind
    native.GetMinValue2.return_value = native.GetMaxValue2.return_value = (1, 0.0)
    before, after = capture(), capture()
    row = _native(before)
    assert row["tolerance_type"] == kind
    assert row["designation"] == ("basic" if kind == 1 else "other")
    assert row["tolerance_min"] == row["tolerance_max"] == 0.0
    assert row["tolerance_min_status"] == row["tolerance_max_status"] == 1
    assert snapshot.compare_source(before, after) == {}


@pytest.mark.parametrize("bound", ["min", "max"])
@pytest.mark.parametrize("before_status,after_status", [(0, 1), (1, 0)])
def test_validity_change_fails_even_with_identical_value(
    native_snapshot, bound, before_status, after_status
):
    native, capture = native_snapshot
    getter = getattr(native, f"Get{bound.title()}Value2")
    getter.return_value = (before_status, 0.0)
    before = capture()
    getter.return_value = (after_status, 0.0)
    with pytest.raises(RuntimeError, match="value/tolerance/BASIC changed"):
        snapshot.compare_source(before, capture())


@pytest.mark.parametrize("bound", ["min", "max"])
@pytest.mark.parametrize("status", [0, 1])
def test_value_change_remains_exact_even_when_not_valid_for_type(
    native_snapshot, bound, status
):
    native, capture = native_snapshot
    getter = getattr(native, f"Get{bound.title()}Value2")
    getter.return_value = (status, 0.0)
    before = capture()
    getter.return_value = (status, 1e-20)
    with pytest.raises(RuntimeError, match="value/tolerance/BASIC changed"):
        snapshot.compare_source(before, capture())


@pytest.mark.parametrize("bound", ["min", "max"])
@pytest.mark.parametrize(
    "returned",
    [
        None,
        0.0,
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
        (0, None),
        (0, float("nan")),
        (0, float("inf")),
        (1, -float("inf")),
    ],
)
def test_malformed_unknown_or_nonfinite_getter_result_fails(
    native_snapshot, bound, returned
):
    native, capture = native_snapshot
    getattr(native, f"Get{bound.title()}Value2").return_value = returned
    with pytest.raises(RuntimeError, match="tolerance"):
        capture()


@pytest.mark.parametrize("bound", ["min", "max"])
def test_native_exception_propagates_without_legacy_retry(native_snapshot, bound):
    native, capture = native_snapshot
    error = RuntimeError("native tolerance getter failed")
    getattr(native, f"Get{bound.title()}Value2").side_effect = error
    with pytest.raises(RuntimeError) as caught:
        capture()
    assert caught.value is error
    native.GetMinValue.assert_not_called()
    native.GetMaxValue.assert_not_called()
