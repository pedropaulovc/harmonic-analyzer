"""Raw native 3004 fixtures; VIEW identity and exact cold banks stay mandatory."""

from copy import deepcopy
import json
import math
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import _raw_edge_curve as raw
from diagnostics import _recipe_view_entity_acceptance as observer
from diagnostics import _view_intersection_curve_witness as witness
from diagnostics._recipe_view_roles import ViewRole, ViewResolver
from test_view_recipe_acceptance_drawing import bank as bank

ANALYTIC_GEOMETRY = observer.attachments.geometry
FIXTURE = (
    Path(__file__).with_name("fixtures")
    / "crankshaft-intersection-curves-zj92q9yo.json"
)
ROWS = json.loads(FIXTURE.read_text(encoding="utf-8"))["edges"]


def native_edge(row):
    spline = NS(**row["spline"])
    spline.GetControlPoints = Mock(return_value=deepcopy(row["GetControlPoints"]))
    spline.GetKnotPoints = Mock(return_value=deepcopy(row["GetKnotPoints"]))
    curve = NS(
        Identity=Mock(return_value=row["identity"]),
        IsLine=Mock(return_value=row["is_line"]),
        IsCircle=Mock(return_value=row["is_circle"]),
        IsBcurve=Mock(return_value=row["is_bcurve"]),
        GetEndParams=Mock(return_value=deepcopy(row["end_params_return"])),
        GetBCurveParams5=Mock(return_value=spline),
    )
    return NS(
        GetCurve=Mock(return_value=curve),
        GetCurveParams3=Mock(return_value=NS(**deepcopy(row["trim"]))),
    )


@pytest.fixture(autouse=True)
def early_bound(monkeypatch):
    for module in (witness, raw, raw.attachments):
        monkeypatch.setattr(module, "_early_bound", lambda value, _: value)


@pytest.mark.parametrize("row", ROWS, ids=["PinHole-0", "PinHole-7"])
def test_actual_native_3004_full_coefficients_metadata_trim_and_status_are_retained(
    row,
):
    edge = native_edge(row)
    evidence = {}
    kind, captured = witness.snapshot(edge, evidence)
    assert kind == "intersection_curve"
    assert captured == evidence
    assert captured["requested_identity"] == 3004
    expected_keys = {
        "identity",
        "is_line",
        "is_circle",
        "is_bcurve",
        "end_params_return",
        "trim",
        "bcurve_arguments",
        "bcurve_return",
        "spline",
        "GetControlPoints",
        "GetKnotPoints",
    }
    assert captured.keys() == expected_keys | {"requested_identity"}
    for key in expected_keys:
        assert json.loads(json.dumps(captured[key])) == row[key]
    assert captured["spline"] == {
        "Dimension": 3,
        "Order": 4,
        "Periodic": 1,
        "ControlPointsCount": 60,
        "KnotPointsCount": 61,
    }
    edge.GetCurve.return_value.GetBCurveParams5.assert_called_once_with(
        False, False, False, True
    )
    evidence["GetControlPoints"][1][0] += 0.01
    assert captured["GetControlPoints"][1][0] == row["GetControlPoints"][1][0]


@pytest.mark.parametrize(
    "damage",
    [
        "other_kind",
        "bool_kind",
        "missing",
        "trim_kind",
        "not_bcurve",
        "changed_identity",
        "short_controls",
        "nan_knot",
        "failed_controls",
    ],
)
def test_rejects_unproven_or_malformed_shapes_without_hiding_raw_failure(damage):
    edge = native_edge(ROWS[0])
    curve = edge.GetCurve.return_value
    spline = curve.GetBCurveParams5.return_value
    if damage == "other_kind":
        curve.Identity.return_value = 3005
    if damage == "bool_kind":
        curve.Identity.return_value = True
    if damage == "missing":
        edge.GetCurve.return_value = None
    if damage == "trim_kind":
        edge.GetCurveParams3.return_value.CurveType = 3005
    if damage == "not_bcurve":
        curve.IsBcurve.return_value = False
    if damage == "changed_identity":
        curve.Identity.side_effect = [3004, 3005]
    if damage == "short_controls":
        spline.GetControlPoints.return_value[1].pop()
    if damage == "nan_knot":
        spline.GetKnotPoints.return_value[1][0] = math.nan
    if damage == "failed_controls":
        spline.GetControlPoints.return_value[0] = False
    evidence = {}
    with pytest.raises(RuntimeError):
        witness.snapshot(edge, evidence)
    if damage in ("other_kind", "bool_kind", "missing"):
        curve.GetBCurveParams5.assert_not_called()
    if damage in ("short_controls", "failed_controls"):
        assert evidence["GetControlPoints"] is spline.GetControlPoints.return_value
    if damage == "nan_knot":
        assert math.isnan(evidence["GetKnotPoints"][1][0])


def curve_bank(bank, monkeypatch):
    monkeypatch.setattr(observer.attachments, "geometry", ANALYTIC_GEOMETRY)
    edge = native_edge(ROWS[0])
    bank.entity = bank.view.entity = edge
    bank.view.GetOrientationName = lambda: "*Right"
    bank.manifest.view_roles.clear()
    bank.manifest.view_roles["cross-hole true position"] = ViewRole(
        "*Right", 5, "EDGE", ViewResolver.CROSS_HOLE
    )
    bank.module._visible_cross_hole_edge = lambda adapter, view: view.entity
    return edge


def build_curve(bank):
    with bank.witness.observe(bank.adapter):
        bank.module.add_feature_control_frame(
            bank.adapter,
            bank.view,
            label="cross-hole true position",
            entity=bank.entity,
        )


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "selected_substitute",
        "attached_substitute",
        "wrong_view",
        "unknown_identity",
        "failed_getter",
    ],
)
def test_native_view_identity_still_required_even_when_all_curve_parameters_equal(
    bank, monkeypatch, fault
):
    edge = curve_bank(bank, monkeypatch)
    substitute = native_edge(ROWS[0])
    if fault == "selected_substitute":
        bank.manager.GetSelectedObject6 = lambda *_: substitute
    if fault == "unknown_identity":
        bank.adapter.swApp.IsSame = lambda *_: -1
    if fault == "failed_getter":
        edge.GetCurve.return_value.GetBCurveParams5.return_value.GetControlPoints.return_value[
            0
        ] = False
    if fault in ("selected_substitute", "unknown_identity", "failed_getter"):
        with pytest.raises(RuntimeError):
            build_curve(bank)
        row = bank.witness.context_report["stages"][-1]
        if fault == "failed_getter":
            assert row["argument_curve_read"]["GetControlPoints"][0] is False
        assert "error" in row
        return
    build_curve(bank)
    annotation = bank.annotations["cross-hole true position"]
    if fault == "attached_substitute":
        annotation.GetAttachedEntities3 = lambda: (substitute,)
    if fault == "wrong_view":
        annotation.Owner = object()
    if fault is not None:
        with pytest.raises(RuntimeError):
            bank.witness.drawing_snapshot(bank.adapter, phase="built")
        return
    result = bank.witness.drawing_snapshot(bank.adapter, phase="built")
    assert (
        result["explicit"]["cross-hole true position"]["geometry"][0]
        == "intersection_curve"
    )
    assert (
        bank.witness.context_report["stages"][0]["argument_curve_read"]
        == bank.witness.context_report["stages"][0]["selected_curve_read"]
    )


@pytest.mark.parametrize(
    "field", ["control", "knot", "trim_end", "endpoint", "tag", "sense", "domain"]
)
def test_any_changed_native_coefficient_or_trim_fails_exact_same_session_bank(
    bank, monkeypatch, field
):
    edge = curve_bank(bank, monkeypatch)
    build_curve(bank)
    curve = edge.GetCurve.return_value
    spline = curve.GetBCurveParams5.return_value
    trim = edge.GetCurveParams3.return_value
    if field == "control":
        values = spline.GetControlPoints.return_value[1]
        values[27] = math.nextafter(values[27], math.inf)
    if field == "knot":
        values = spline.GetKnotPoints.return_value[1]
        values[-1] = math.nextafter(values[-1], math.inf)
    if field == "trim_end":
        trim.UMaxValue = math.nextafter(trim.UMaxValue, math.inf)
    if field == "endpoint":
        trim.EndPoint[1] = math.nextafter(trim.EndPoint[1], math.inf)
    if field == "tag":
        trim.CurveTag += 1
    if field == "sense":
        trim.Sense = not trim.Sense
    if field == "domain":
        values = curve.GetEndParams.return_value
        values[2] = math.nextafter(values[2], math.inf)
    with pytest.raises(RuntimeError, match="raw VIEW geometry changed since selection"):
        bank.witness.drawing_snapshot(bank.adapter, phase="built")
    row = bank.witness.context_report["stages"][-1]
    assert row["initial_geometry"] != row["geometry"]
    assert row["curve_read"] == row["geometry"][1]


@pytest.mark.parametrize("fault", [None, "substituted_role", "coefficient", "trim_tag"])
def test_cold_role_uses_fresh_native_handles_and_preserves_exact_numeric_comparison(
    bank, monkeypatch, fault
):
    old_edge = curve_bank(bank, monkeypatch)
    build_curve(bank)
    built = bank.witness.drawing_snapshot(bank.adapter, phase="built")
    fresh_edge = native_edge(ROWS[0])
    fresh_view = NS(
        GetName2=lambda: "Drawing View1",
        GetOrientationName=lambda: "*Right",
        entity=fresh_edge,
    )
    annotation = NS(**vars(bank.annotations["cross-hole true position"]))
    annotation.Owner = fresh_view
    annotation.GetAttachedEntities3 = lambda: (fresh_edge,)
    fresh_view.GetAnnotations = lambda: (annotation,)
    monkeypatch.setattr(
        observer.attachments, "views", lambda _: {"Sheet/View": fresh_view}
    )
    old_edge.GetCurve = Mock(side_effect=AssertionError("closed edge queried"))
    bank.view.GetName2 = Mock(side_effect=AssertionError("closed view queried"))
    bank.annotations["cross-hole true position"].GetName = Mock(
        side_effect=AssertionError("closed annotation queried")
    )
    if fault == "substituted_role":
        fresh_view.entity = native_edge(ROWS[0])
        with pytest.raises(RuntimeError, match="entity"):
            bank.witness.drawing_snapshot(bank.adapter, phase="reopened")
        return
    if fault == "coefficient":
        values = fresh_edge.GetCurve.return_value.GetBCurveParams5.return_value.GetControlPoints.return_value[
            1
        ]
        values[5] = math.nextafter(values[5], math.inf)
    if fault == "trim_tag":
        fresh_edge.GetCurveParams3.return_value.CurveTag += 1
    reopened = bank.witness.drawing_snapshot(bank.adapter, phase="reopened")
    # The unchanged pilot compares these complete banks with != after reopen.
    assert (reopened == built) is (fault is None)


def test_analytic_geometry_and_non_edge_failure_do_not_enter_new_curve_path(
    monkeypatch,
):
    snapshot = Mock(side_effect=AssertionError("unexpected intersection read"))
    monkeypatch.setattr(observer.intersection, "snapshot", snapshot)
    for shape in (
        ("line", ((0, 0, 0), (0, 0, 1))),
        ("circle", (0,) * 7, (0, 1), (0,) * 3, (0,) * 3),
    ):
        monkeypatch.setattr(
            observer.attachments, "geometry", lambda *_, shape=shape: shape
        )
        assert observer.geometry(None, None, object(), 1) == shape
    monkeypatch.setattr(
        observer.attachments,
        "geometry",
        Mock(side_effect=observer.attachments.UnsupportedGeometry("unsupported face")),
    )
    with pytest.raises(
        observer.attachments.UnsupportedGeometry, match="unsupported face"
    ):
        observer.geometry(None, None, object(), 2)
    snapshot.assert_not_called()
