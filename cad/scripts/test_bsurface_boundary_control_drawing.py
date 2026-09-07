"""Opt-in native index observations cannot substitute for the accepted grid."""

import json
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from diagnostics import _bsurface_attachment_witness as reader
from diagnostics import _silhouette_attachment_witness as witness
from diagnostics import probe_datum_policy_recipes as pilot
from test_bsurface_silhouette_drawing import (
    bsurface as bsurface,
    bsurface_binding as bsurface_binding,
    early_bound as early_bound,
)


@pytest.fixture(autouse=True)
def clean_control_environment(monkeypatch):
    monkeypatch.delenv("HARMONIC_BSURF_GRID_CONTROL", raising=False)


@pytest.mark.parametrize("mode", [None, "off"])
def test_default_native_sequence_and_geometry_are_unchanged(bsurface, monkeypatch, mode):
    c = bsurface
    if mode is not None:
        monkeypatch.setenv("HARMONIC_BSURF_GRID_CONTROL", mode)
    evidence = {}
    result = reader.snapshot(c.face, c.surface, evidence=evidence)
    assert c.data.GetControlPoints.call_args_list == [
        call(row, column) for row in (1, 2) for column in (1, 2, 3, 4)
    ]
    assert "grid_control" not in evidence
    c.data.GetControlPoints.reset_mock()
    assert reader.snapshot(c.face, c.surface) == result
    assert c.data.GetControlPoints.call_count == 8
    c.surface.GetBSurfParams3.assert_has_calls([
        call(False, False, c.parameterization, 0.01),
        call(False, False, c.parameterization, 0.01),
    ])


@pytest.mark.parametrize("mode", ["", "boundary_domain", "ON", "unknown"])
@pytest.mark.parametrize("route", ["parent", "worker"])
def test_invalid_mode_refuses_before_owned_environment_or_native_route(
    monkeypatch, tmp_path, mode, route,
):
    monkeypatch.setenv("HARMONIC_BSURF_GRID_CONTROL", mode)
    environment = Mock(side_effect=AssertionError("native routing reached"))
    monkeypatch.setattr(pilot, "require_owned_diagnostic_environment", environment)
    arguments = ["--source-root", str(tmp_path), "--guard-root", str(tmp_path)]
    if route == "worker":
        arguments.append("--worker")
    with pytest.raises(ValueError, match="HARMONIC_BSURF_GRID_CONTROL"):
        pilot.main(arguments)
    environment.assert_not_called()


def test_direct_invalid_mode_and_missing_optin_sink_refuse_before_native(bsurface, monkeypatch):
    c = bsurface
    monkeypatch.setenv("HARMONIC_BSURF_GRID_CONTROL", "unknown")
    with pytest.raises(ValueError, match="HARMONIC_BSURF_GRID_CONTROL"):
        reader.snapshot(c.face, c.surface)
    monkeypatch.setenv("HARMONIC_BSURF_GRID_CONTROL", "boundary-domain")
    with pytest.raises(ValueError, match="evidence sink"):
        reader.snapshot(c.face, c.surface)
    c.surface.Parameterization2.assert_not_called()
    c.surface.GetBSurfParams3.assert_not_called()
    c.data.GetControlPoints.assert_not_called()


@pytest.mark.asyncio
async def test_direct_pilot_rejects_invalid_mode_before_owned_setup(monkeypatch, tmp_path):
    monkeypatch.setenv("HARMONIC_BSURF_GRID_CONTROL", "unknown")
    register = Mock(side_effect=AssertionError("owned setup reached"))
    adapter = SimpleNamespace(ownership=SimpleNamespace(register_directory=register))
    output = tmp_path / "untouched"
    with pytest.raises(ValueError, match="HARMONIC_BSURF_GRID_CONTROL"):
        await pilot.pilot(adapter, "HEAD", tmp_path, tmp_path, output)
    register.assert_not_called()
    assert not output.exists()


@pytest.mark.parametrize("rows,columns", [(5, 25), (2, 2), (1, 1), (4096, 1)])
def test_boundary_plan_is_finite_deduplicated_and_metadata_derived(rows, columns):
    indices = reader.boundary_indices(rows=rows, columns=columns)
    assert indices == tuple(dict.fromkeys((
        (2, 3), (1, rows), (1, rows + 1), (rows, 1), (rows + 1, 1),
        (columns, 1), (columns + 1, 1), (1, columns), (1, columns + 1),
        (0, 1), (1, 0),
    )))
    assert len(indices) <= 11
    assert indices[0] == (2, 3)
    assert all(type(index) is int and 0 <= index <= 4097 for pair in indices for index in pair)


@pytest.mark.parametrize("bad_count", [True, 0, -1, 4097, 5.0, "5"])
def test_boundary_plan_rejects_unvalidated_counts(bad_count):
    with pytest.raises(RuntimeError, match="BSURF"):
        reader.boundary_indices(rows=bad_count, columns=25)


def test_optin_retains_native_shaped_boundary_reads_then_same_grid_failure(bsurface, monkeypatch):
    c = bsurface
    # Counts/orders/dimension from the retained vxy0llpy receipt. Synthetic
    # coefficients are not native evidence or an inferred index-domain repair.
    c.data.ControlPointRowCount = 5
    c.data.ControlPointColumnCount = 25
    c.data.ControlPointDimension = 4
    c.data.UOrder, c.data.VOrder = 5, 3
    c.data.UKnots = tuple(float(i) for i in range(30))
    c.data.VKnots = tuple(float(i) for i in range(8))
    native_error = OSError("explicit out-of-domain request rejected")

    def point(row, column):
        if row == 26:
            raise native_error
        if not 1 <= row <= 25 or not 1 <= column <= 5:
            return None
        return (float(row), float(column), -0.0, 2.0)

    c.data.GetControlPoints.side_effect = point
    monkeypatch.setenv("HARMONIC_BSURF_GRID_CONTROL", "boundary-domain")
    evidence = {}
    with pytest.raises(RuntimeError, match=r"GetControlPoints\(1,6\): expected 4 native doubles, got None"):
        witness.require_same(c.app, c.view, c.entity, c.entity,
                             drawing=c.app.drawing, label="tooth tip", evidence=evidence)
    partial = evidence["expected"]["face_surface"]
    control = partial["grid_control"]
    assert control["mode"] == "boundary-domain"
    assert control["scope"] == "raw_index_observation_not_acceptance"
    assert control["metadata"] == {"rows": 5, "columns": 25, "dimension": 4}
    queries = reader.boundary_indices(rows=5, columns=25)
    records = control["reads"]
    assert [(row["row"], row["column"]) for row in records] == list(queries)
    assert records[0]["returned"]["value"][0]["value"] == 2.0
    by_index = {(row["row"], row["column"]): row for row in records}
    assert by_index[1, 6]["returned"] == {"type": "builtins.NoneType", "value": None}
    assert by_index[26, 1]["returned"] == {"error": repr(native_error)}
    assert by_index[0, 1]["returned"]["value"] is None
    assert by_index[1, 0]["returned"]["value"] is None
    assert c.data.GetControlPoints.call_args_list == [call(*pair) for pair in queries] + [
        call(1, column) for column in range(1, 7)
    ]
    assert "control_points" not in partial["bspline"]
    assert "actual" not in evidence
    c.surface.GetBSurfParams3.assert_called_once_with(False, False, c.parameterization, 0.01)
    json.dumps(evidence, allow_nan=False)


def test_exploratory_values_do_not_replace_the_full_grid(bsurface, monkeypatch):
    c = bsurface
    expected = reader.snapshot(c.face, c.surface)
    original = c.data.GetControlPoints.side_effect
    query_count = len(reader.boundary_indices(rows=2, columns=4))
    c.data.GetControlPoints.reset_mock()

    def point(row, column):
        if c.data.GetControlPoints.call_count <= query_count:
            return (999.0, 998.0, 997.0)
        return original(row, column)

    c.data.GetControlPoints.side_effect = point
    monkeypatch.setenv("HARMONIC_BSURF_GRID_CONTROL", "boundary-domain")
    evidence = {}
    assert reader.snapshot(c.face, c.surface, evidence=evidence) == expected
    assert c.data.GetControlPoints.call_count == query_count + 8
    assert evidence["grid_control"]["reads"][0]["returned"]["value"][0]["value"] == 999.0


def test_optin_does_not_mask_original_grid_getter_exception(bsurface, monkeypatch):
    c = bsurface
    primary = OSError("native getter rejected")
    c.data.GetControlPoints.side_effect = primary
    monkeypatch.setenv("HARMONIC_BSURF_GRID_CONTROL", "boundary-domain")
    evidence = {}
    with pytest.raises(OSError) as raised:
        reader.snapshot(c.face, c.surface, evidence=evidence)
    assert raised.value is primary
    queries = reader.boundary_indices(rows=2, columns=4)
    assert c.data.GetControlPoints.call_args_list == [call(*pair) for pair in queries] + [call(1, 1)]
    assert all(row["returned"] == {"error": repr(primary)} for row in evidence["grid_control"]["reads"])
    assert evidence["control_point_reads"] == [
        {"row": 1, "column": 1, "returned": {"error": repr(primary)}},
    ]
    assert "control_points" not in evidence["bspline"]
