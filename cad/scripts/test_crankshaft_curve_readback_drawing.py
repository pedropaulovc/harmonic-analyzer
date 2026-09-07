"""Raw curve call shapes, immutable copied inputs and no-save owned lifecycle."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import _raw_edge_curve as raw
from diagnostics import probe_crankshaft_curves as probe
from diagnostics import _owned_native_documents as owned
from test_owned_native_documents_drawing import Model, native as native


@pytest.fixture
def edge(monkeypatch):
    monkeypatch.setattr(raw, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(raw.attachments, "_early_bound", lambda value, _: value)
    spline = NS(
        Dimension=3,
        Order=3,
        Periodic=0,
        ControlPointsCount=3,
        KnotPointsCount=6,
        GetControlPoints=Mock(
            return_value=(True, (0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 2.0, 0.0, 0.0))
        ),
        GetKnotPoints=Mock(return_value=(True, (0.0, 0.0, 0.0, 1.0, 1.0, 1.0))),
    )
    curve = NS(
        Identity=Mock(return_value=3004),
        IsCircle=Mock(return_value=False),
        IsLine=Mock(return_value=False),
        IsBcurve=Mock(return_value=True),
        GetEndParams=Mock(return_value=(True, 0.0, 1.0, False, False)),
        GetBCurveParams5=Mock(return_value=spline),
        CircleParams=(0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.01),
        LineParams=(0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
    )
    trim = NS(
        CurveType=3004,
        CurveTag=17,
        Sense=True,
        UMinValue=0.0,
        UMaxValue=1.0,
        StartPoint=(0.0, 0.0, 0.0),
        EndPoint=(2.0, 0.0, 0.0),
    )
    result = NS(
        GetCurve=Mock(return_value=curve),
        GetCurveParams3=Mock(return_value=trim),
        GetStartVertex=lambda: NS(GetPoint=lambda: trim.StartPoint),
        GetEndVertex=lambda: NS(GetPoint=lambda: trim.EndPoint),
    )
    return NS(edge=result, curve=curve, trim=trim, spline=spline)


@pytest.mark.parametrize(
    "closed,periodic", [(False, False), (True, False), (True, True)]
)
def test_preserves_native_closure_periodicity_raw_weighted_points_and_trim(
    edge, closed, periodic
):
    edge.curve.GetEndParams.return_value = (True, 0.0, 1.0, closed, periodic)
    edge.spline.Periodic = int(periodic)
    edge.spline.Dimension = 4
    edge.spline.GetControlPoints.return_value = (
        True,
        tuple(float(i) for i in range(12)),
    )
    if periodic:
        edge.spline.KnotPointsCount = 4
        edge.spline.GetKnotPoints.return_value = (True, (0.0, 0.2, 0.7, 1.0))
    row = {}
    raw.read_edge(edge.edge, row)
    edge.curve.GetBCurveParams5.assert_called_once_with(
        False, False, not periodic, closed
    )
    assert row["end_params_return"] == (True, 0.0, 1.0, closed, periodic)
    assert row["trim"] == vars(edge.trim)
    assert row["GetControlPoints"] == edge.spline.GetControlPoints.return_value
    assert row["GetKnotPoints"] == edge.spline.GetKnotPoints.return_value
    assert row["identity"] == 3004 and row["spline"]["Dimension"] == 4


@pytest.mark.parametrize("kind", ["line", "circle"])
def test_existing_analytic_positive_controls_are_unchanged_no_conversion(edge, kind):
    getattr(edge.curve, f"Is{kind.title()}").return_value = True
    row = {}
    original = raw.attachments.geometry(edge.edge, 1)
    raw.read_edge(edge.edge, row)
    assert row["existing_geometry"] == original
    edge.curve.GetBCurveParams5.assert_not_called()
    assert row["analytic_parameters"] == getattr(edge.curve, f"{kind.title()}Params")


@pytest.mark.parametrize(
    "returned",
    [
        None,
        (),
        (False, 0.0, 1.0, False, False),
        (1, 0.0, 1.0, False, False),
        (True, float("nan"), 1.0, False, False),
        (True, 0.0, 1.0, 0, False),
        (True, "0", 1.0, False, False),
    ],
)
def test_end_params_rejects_failed_or_wrong_typed_native_shapes_retains_raw(
    edge, returned
):
    edge.curve.GetEndParams.return_value = returned
    row = {}
    with pytest.raises(RuntimeError):
        raw.read_edge(edge.edge, row)
    assert row["end_params_return"] is returned
    edge.curve.GetBCurveParams5.assert_not_called()


@pytest.mark.parametrize(
    "attribute,value",
    [
        ("Dimension", 2),
        ("Dimension", True),
        ("Order", 0),
        ("Order", 65),
        ("ControlPointsCount", 2),
        ("ControlPointsCount", 10001),
        ("KnotPointsCount", 5),
        ("Periodic", 1),
        ("Periodic", False),
    ],
)
def test_spline_metadata_is_bounded_and_not_coerced(edge, attribute, value):
    setattr(edge.spline, attribute, value)
    row = {}
    with pytest.raises(RuntimeError):
        raw.read_edge(edge.edge, row)
    assert row["spline"][attribute] == value
    edge.spline.GetControlPoints.assert_not_called()


@pytest.mark.parametrize("method", ["GetControlPoints", "GetKnotPoints"])
@pytest.mark.parametrize(
    "damage",
    ["false", "integer_status", "wrong_shape", "short", "nan", "bool", "string"],
)
def test_retval_out_arrays_are_exact_finite_complete_and_retained(edge, method, damage):
    returned = getattr(edge.spline, method).return_value
    status, values = returned
    if damage == "false":
        status = False
    if damage == "integer_status":
        status = 1
    if damage == "short":
        values = values[:-1]
    if damage == "nan":
        values = (float("nan"), *values[1:])
    if damage == "bool":
        values = (True, *values[1:])
    if damage == "string":
        values = ("0", *values[1:])
    returned = (status, values) if damage != "wrong_shape" else values
    getattr(edge.spline, method).return_value = returned
    row = {}
    with pytest.raises(RuntimeError):
        raw.read_edge(edge.edge, row)
    assert row[method] is returned


@pytest.mark.parametrize(
    "damage",
    ["null_spline", "not_bcurve", "bad_sense", "bad_trim", "bad_endpoint", "knots"],
)
def test_unsupported_curve_trim_and_knot_cases_fail_without_fallback(edge, damage):
    if damage == "null_spline":
        edge.curve.GetBCurveParams5.return_value = None
    if damage == "not_bcurve":
        edge.curve.IsBcurve.return_value = False
    if damage == "bad_sense":
        edge.trim.Sense = 1
    if damage == "bad_trim":
        edge.trim.UMaxValue = -1.0
    if damage == "bad_endpoint":
        edge.trim.StartPoint = (0.0, 0.0)
    if damage == "knots":
        edge.spline.GetKnotPoints.return_value = (True, (0.0, 0.0, 1.0, 0.0, 1.0, 1.0))
    with pytest.raises(RuntimeError):
        raw.read_edge(edge.edge, {})
    assert edge.curve.GetBCurveParams5.call_count <= 1


def test_capture_maps_named_feature_membership_not_same_radius(monkeypatch, edge):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    cylinder = NS(
        Identity=lambda: 4002,
        IsCylinder=lambda: True,
        CylinderParams=(0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.002489),
    )
    target_face, wrong_face = (NS(GetSurface=lambda: cylinder) for _ in range(2))
    edges = []
    for kind in ("line", "circle", "bcurve", "bcurve"):
        item = deepcopy(edge.edge)
        item.GetCurve.return_value.IsLine.return_value = kind == "line"
        item.GetCurve.return_value.IsCircle.return_value = kind == "circle"
        face = target_face if len(edges) == 2 else wrong_face
        item.GetTwoAdjacentFaces2 = lambda face=face: (face, None)
        edges.append(item)
    feature = NS(Name="PinHole", GetFaces=lambda: (target_face,))
    monkeypatch.setattr(probe, "_feature_by_name", lambda adapter, name: feature)
    model = NS(GetBodies2=lambda *args: (NS(GetEdges=lambda: edges),))
    adapter = NS(currentModel=model, swApp=NS(IsSame=lambda a, b: int(a is b)))
    report, checkpoints = {}, []
    probe.capture_edges(adapter, report, lambda: checkpoints.append(1))
    assert report["coverage"] == {
        "line": [0],
        "circle": [1],
        "PinHole_nonanalytic": [2],
    }
    assert report["edges"][3]["PinHole_face_indices"] == []
    assert len(checkpoints) == 4
    adapter.swApp.IsSame = lambda a, b: 2
    with pytest.raises(RuntimeError):
        probe.capture_edges(adapter, {}, lambda: None)


@pytest.mark.parametrize(
    "outcome",
    ["pass", "curve_failure", "source_value", "copy_write", "runtime", "cleanup"],
)
def test_owned_copy_lifecycle_retains_failure_and_final_guards(
    native, monkeypatch, tmp_path, outcome
):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(
        probe.pilot, "helper_fingerprints", lambda: {"helper": "frozen"}
    )
    monkeypatch.setattr(
        probe.pilot, "adapter_fingerprints", lambda: {"adapter": "frozen"}
    )
    monkeypatch.setattr(probe.pilot.benchmark, "revision", lambda _: "frozen")
    user = Model(None, title="Unsaved user drawing", dirty=True)
    native.app.documents.append(user)
    native.app.ActiveDoc = user
    observed, dimension = [], object()

    def dimensions(model, target, path):
        assert target == "crankshaft" and Path(model.path) == path
        assert model.path != str(native.source)
        observed.append(model)
        value = 2 if outcome == "source_value" and len(observed) == 2 else 1
        return {"configuration": "Default", "dimensions": {"exact": value}}, {
            "exact": dimension
        }

    monkeypatch.setattr(probe.pilot, "source_dimensions", dimensions)

    def capture(adapter, report, checkpoint):
        report["edges"] = [{"raw_return": [True, 3.25], "status": "captured"}]
        checkpoint()
        if outcome == "curve_failure":
            raise RuntimeError("primary curve failure")
        if outcome == "copy_write":
            Path(adapter.currentModel.path).write_bytes(b"unexpected save")
        if outcome == "runtime":
            monkeypatch.setattr(
                probe.pilot, "adapter_fingerprints", lambda: {"changed": 1}
            )
        if outcome == "cleanup":

            async def reject():
                raise RuntimeError("cleanup refused")

            monkeypatch.setattr(adapter.ownership, "close_owned_documents", reject)
            raise RuntimeError("primary before cleanup")

    monkeypatch.setattr(probe, "capture_edges", capture)
    expected = probe.file_digest(native.source)
    guarded = owned.DiagnosticAdapter(native.adapter)
    operation = probe.probe(guarded, native.source, expected, tmp_path / "reports")
    if outcome == "pass":
        asyncio.run(operation)
    else:
        with pytest.raises(ExceptionGroup):
            asyncio.run(operation)
    (receipt,) = (tmp_path / "reports").glob("*/curves.json")
    report = json.loads(receipt.read_text())
    assert report["source_final"] == expected
    assert len(observed) == 2  # Failed curve API still receives final source read.
    assert report["dirty_before_read"] is report["dirty_after_read"] is False
    assert report["edges"][0]["raw_return"] == [True, 3.25]
    assert report["status"] == ("captured" if outcome == "pass" else "failed")
    assert user in native.app.documents and user.dirty
    if outcome == "cleanup":
        assert "primary before cleanup" in report["errors"][0]
        assert "cleanup refused" in report["cleanup_error"]
        assert "source_final" in report and "adapter_final" in report
    else:
        assert native.app.documents == [user]
    if outcome in ("copy_write", "runtime"):
        assert report["final_guard_errors"]


@pytest.mark.parametrize(
    "missing",
    [
        "HARMONIC_SW_AUTOSTART",
        "HARMONIC_DIAGNOSTIC_SW_PID",
        "HARMONIC_REMOTE_CACHE_MODE",
    ],
)
def test_parent_rejects_unsafe_environment_before_native_wrapper(
    monkeypatch, tmp_path, missing
):
    for name, value in (
        ("HARMONIC_SW_AUTOSTART", "0"),
        ("HARMONIC_DIAGNOSTIC_SW_PID", "31860"),
        ("HARMONIC_REMOTE_CACHE_MODE", "off"),
    ):
        monkeypatch.setenv(name, value)
    monkeypatch.delenv(missing)
    with pytest.raises(RuntimeError):
        probe.main(["--source", str(tmp_path / "not-opened.SLDPRT")])
