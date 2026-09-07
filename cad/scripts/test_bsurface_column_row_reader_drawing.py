"""Explicit experimental getter order; the disputed default stays unchanged."""

import json
from unittest.mock import call

import pytest

from diagnostics import _bsurface_attachment_witness as reader
from test_bsurface_column_row_control_drawing import native_shaped_data
from test_bsurface_silhouette_drawing import (
    bank as bank,
    bsurface as bsurface,
    bsurface_binding as bsurface_binding,
    early_bound as early_bound,
    test_real_view_fcf_observer_uses_bsurface_on_selection_built_and_fresh_cold
    as _exercise_real_observer,
)


@pytest.fixture(autouse=True)
def experimental_reader(monkeypatch):
    monkeypatch.setenv("HARMONIC_BSURF_GRID_CONTROL", "column-row-reader")


def test_native_domain_is_read_once_and_stored_in_logical_row_major_order(bsurface):
    c = bsurface
    native_shaped_data(c.data)
    evidence = {}
    result = reader.snapshot(c.face, c.surface, evidence=evidence)
    spline = result["bspline"]
    assert spline["control_point_order"] == "column-row"
    assert spline["ControlPointRowCount"] == 5
    assert spline["ControlPointColumnCount"] == 25
    assert spline["UOrder"] == 5 and spline["VOrder"] == 3
    assert spline["UKnots"] == c.data.UKnots
    assert spline["VKnots"] == c.data.VKnots
    assert len(spline["control_points"]) == 5
    assert all(len(row) == 25 for row in spline["control_points"])
    assert spline["control_points"][0][24] == (25.0, 1.0, -0.0, 2.0)
    assert spline["control_points"][4][0] == (1.0, 5.0, -0.0, 2.0)
    assert spline["control_points"][4][24][2].hex() == (-0.0).hex()
    assert c.data.GetControlPoints.call_args_list == [
        call(column, row) for row in range(1, 6) for column in range(1, 26)
    ]
    assert len(evidence["control_point_reads"]) == 125
    assert evidence["control_point_reads"][24]["arguments"] == (25, 1)
    assert evidence["control_point_reads"][25]["arguments"] == (1, 2)
    assert "grid_control" not in evidence
    json.dumps(evidence, allow_nan=False)


@pytest.mark.parametrize(
    "bad", [None, (1.0,), (1, 2.0, 3.0, 4.0), (1.0, float("inf"), 3.0, 4.0),
            OSError("actual interior read failed")],
)
def test_rejection_keeps_actual_arguments_and_never_publishes_partial_grid(bsurface, bad):
    c = bsurface
    original = native_shaped_data(c.data)

    def point(first, second):
        if (first, second) != (12, 3):
            return original(first, second)
        if isinstance(bad, Exception):
            raise bad
        return bad

    c.data.GetControlPoints.side_effect = point
    evidence = {}
    with pytest.raises((RuntimeError, OSError)) as raised:
        reader.snapshot(c.face, c.surface, evidence=evidence)
    if isinstance(bad, Exception):
        assert raised.value is bad
    else:
        assert "GetControlPoints(12,3)" in str(raised.value)
    assert "control_points" not in evidence["bspline"]
    last = evidence["control_point_reads"][-1]
    assert (last["row"], last["column"], last["arguments"]) == (3, 12, (12, 3))
    assert c.data.GetControlPoints.call_count == 62
    assert c.data.GetControlPoints.call_args == call(12, 3)


def test_experiment_requires_retained_evidence_before_any_native_read(bsurface):
    c = bsurface
    with pytest.raises(ValueError, match="evidence sink"):
        reader.snapshot(c.face, c.surface)
    c.surface.Parameterization2.assert_not_called()
    c.data.GetControlPoints.assert_not_called()


def test_disputed_default_is_not_replaced_by_the_experiment(bsurface, monkeypatch):
    c = bsurface
    native_shaped_data(c.data)
    monkeypatch.delenv("HARMONIC_BSURF_GRID_CONTROL")
    evidence = {}
    with pytest.raises(RuntimeError, match=r"GetControlPoints\(1,6\)"):
        reader.snapshot(c.face, c.surface, evidence=evidence)
    assert "control_point_order" not in evidence["bspline"]
    assert c.data.GetControlPoints.call_args_list == [call(1, i) for i in range(1, 7)]


def test_oversized_experimental_matrix_rejects_before_getter(bsurface):
    c = bsurface
    c.data.ControlPointColumnCount = 65
    c.data.ControlPointRowCount = 64
    with pytest.raises(RuntimeError, match="exceeds read budget"):
        reader.snapshot(c.face, c.surface, evidence={})
    c.data.GetControlPoints.assert_not_called()


@pytest.mark.parametrize("cold_change", [None, "coefficient", "pid"])
def test_real_fcf_observer_keeps_native_identity_and_cold_geometry_checks(
    bsurface, bank, monkeypatch, cold_change,
):
    _exercise_real_observer(bsurface, bank, monkeypatch, cold_change)
