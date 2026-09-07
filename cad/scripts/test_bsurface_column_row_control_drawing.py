"""Observe the proposed native index domain without accepting an alternate grid."""

import json
from unittest.mock import call

import pytest

from diagnostics import _bsurface_attachment_witness as reader
from test_bsurface_silhouette_drawing import (
    bsurface as bsurface,
    bsurface_binding as bsurface_binding,
)


@pytest.fixture(autouse=True)
def explicit_control(monkeypatch):
    monkeypatch.setenv("HARMONIC_BSURF_GRID_CONTROL", "column-row-grid")


def native_shaped_data(data):
    # Dimensions observed in 5fe0i713. Values here are synthetic test data.
    data.ControlPointRowCount = 5
    data.ControlPointColumnCount = 25
    data.ControlPointDimension = 4
    data.UOrder, data.VOrder = 5, 3
    data.UKnots = tuple(float(i) for i in range(30))
    data.VKnots = tuple(float(i) for i in range(8))

    def point(first, second):
        if not 1 <= first <= 25 or not 1 <= second <= 5:
            return None
        return (float(first), float(second), -0.0, 2.0)

    data.GetControlPoints.side_effect = point
    return point


def test_full_column_row_control_retains_all_pairs_then_original_failure(bsurface):
    c = bsurface
    native_shaped_data(c.data)
    evidence = {}
    with pytest.raises(RuntimeError, match=r"GetControlPoints\(1,6\)"):
        reader.snapshot(c.face, c.surface, evidence=evidence)
    control = evidence["grid_control"]
    assert control["mode"] == "column-row-grid"
    assert control["scope"] == "raw_index_observation_not_acceptance"
    assert control["metadata"] == {"rows": 5, "columns": 25, "dimension": 4}
    assert control["status"] == "all_vectors_finite"
    assert control["valid_vectors"] == 125
    queries = [(first, second) for first in range(1, 26) for second in range(1, 6)]
    assert [(row["first"], row["second"]) for row in control["reads"]] == queries
    assert c.data.GetControlPoints.call_args_list == [call(*pair) for pair in queries] + [
        call(1, column) for column in range(1, 7)
    ]
    last = control["reads"][-1]["returned"]["value"]
    assert [value["value"] for value in last] == [25.0, 5.0, -0.0, 2.0]
    assert last[2]["value"].hex() == (-0.0).hex()
    assert "control_points" not in evidence["bspline"]
    c.surface.GetBSurfParams3.assert_called_once_with(False, False, c.parameterization, 0.01)
    json.dumps(evidence, allow_nan=False)


@pytest.mark.parametrize(
    "bad_value",
    [None, (1.0,), (1, 2.0, 3.0, 4.0), (float("nan"), 2.0, 3.0, 4.0), OSError("native read")],
)
def test_interior_rejection_is_retained_without_truncating_domain(bsurface, bad_value):
    c = bsurface
    original = native_shaped_data(c.data)

    def point(first, second):
        if (first, second) != (12, 3):
            return original(first, second)
        if isinstance(bad_value, Exception):
            raise bad_value
        return bad_value

    c.data.GetControlPoints.side_effect = point
    evidence = {}
    with pytest.raises(RuntimeError, match=r"GetControlPoints\(1,6\)"):
        reader.snapshot(c.face, c.surface, evidence=evidence)
    control = evidence["grid_control"]
    assert control["status"] == "invalid_vectors"
    assert control["valid_vectors"] == 124
    assert len(control["reads"]) == 125
    rejected = next(row for row in control["reads"] if (row["first"], row["second"]) == (12, 3))
    assert rejected["vector_error"]
    assert control["reads"][-1]["first"] == 25
    assert control["reads"][-1]["second"] == 5
    assert "control_points" not in evidence["bspline"]
    json.dumps(evidence, allow_nan=False)


def test_optin_requires_evidence_before_native_calls(bsurface):
    c = bsurface
    with pytest.raises(ValueError, match="evidence sink"):
        reader.snapshot(c.face, c.surface)
    c.surface.Parameterization2.assert_not_called()
    c.data.GetControlPoints.assert_not_called()


def test_full_grid_budget_is_enforced_before_any_control_read(bsurface):
    c = bsurface
    c.data.ControlPointColumnCount = 65
    c.data.ControlPointRowCount = 64
    with pytest.raises(RuntimeError, match="exceeds read budget"):
        reader.snapshot(c.face, c.surface, evidence={})
    c.data.GetControlPoints.assert_not_called()


def test_exploratory_vectors_never_replace_ordinary_grid(bsurface, monkeypatch):
    c = bsurface
    monkeypatch.setenv("HARMONIC_BSURF_GRID_CONTROL", "off")
    expected = reader.snapshot(c.face, c.surface)
    original = c.data.GetControlPoints.side_effect
    c.data.GetControlPoints.reset_mock()

    def point(first, second):
        if c.data.GetControlPoints.call_count <= 8:
            return (999.0, 998.0, 997.0)
        return original(first, second)

    c.data.GetControlPoints.side_effect = point
    monkeypatch.setenv("HARMONIC_BSURF_GRID_CONTROL", "column-row-grid")
    evidence = {}
    assert reader.snapshot(c.face, c.surface, evidence=evidence) == expected
    assert c.data.GetControlPoints.call_count == 16
    assert evidence["grid_control"]["reads"][0]["returned"]["value"][0]["value"] == 999.0


def test_original_getter_exception_survives_exploratory_failures(bsurface):
    c = bsurface
    primary = OSError("original getter failed")
    c.data.GetControlPoints.side_effect = primary
    evidence = {}
    with pytest.raises(OSError) as raised:
        reader.snapshot(c.face, c.surface, evidence=evidence)
    assert raised.value is primary
    assert len(evidence["grid_control"]["reads"]) == 8
    assert evidence["grid_control"]["valid_vectors"] == 0
    assert evidence["control_point_reads"] == [
        {"row": 1, "column": 1, "returned": {"error": repr(primary)}}
    ]
