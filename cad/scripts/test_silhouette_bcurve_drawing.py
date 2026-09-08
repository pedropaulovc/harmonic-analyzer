"""Explicit BCURVE reader controls; all native objects here are test doubles."""

from copy import deepcopy
import importlib
import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import _silhouette_attachment_witness as witness
from diagnostics import probe_datum_policy_recipes as pilot
from test_silhouette_attachment_witness_drawing import (
    early_bound as early_bound,
    fixture,
)
from test_view_recipe_acceptance_drawing import bank as bank, silhouette_bank
from test_tooth_selector_observation_drawing import scene as scene


@pytest.fixture
def bcurve(monkeypatch):
    reader = importlib.import_module("diagnostics._silhouette_bcurve_witness")
    monkeypatch.setattr(reader, "_early_bound", lambda obj, _: obj)
    monkeypatch.setenv("HARMONIC_SILHOUETTE_CURVE_CONTROL", "bcurve-3005")
    app, view, entity, face, surface, curve = fixture()
    data = NS(
        Dimension=4,
        Order=3,
        Periodic=0,
        ControlPointsCount=4,
        KnotPointsCount=7,
        GetControlPoints=Mock(return_value=(True, (0.25, -0.0, 0.5, 2.0) * 4)),
        GetKnotPoints=Mock(return_value=(True, (0.0, 0.0, 0.0, 0.5, 1.0, 1.0, 1.0))),
    )
    curve.IsLine = Mock(return_value=False)
    curve.IsCircle = Mock(return_value=False)
    curve.Identity = Mock(return_value=3005)
    curve.IsBcurve = Mock(return_value=True)
    curve.GetEndParams = Mock(return_value=(True, 2.0, 5.0, False, False))
    curve.GetBCurveParams5 = Mock(return_value=data)
    return NS(**locals())


@pytest.mark.parametrize(
    "closed,periodic", [(False, False), (True, False), (True, True)]
)
@pytest.mark.parametrize("dimension", [3, 4])
def test_native_arrays_statuses_domains_and_weights_are_not_normalized(
    bcurve, closed, periodic, dimension
):
    c = bcurve
    c.curve.GetEndParams.return_value = (True, 2.0, 5.0, closed, periodic)
    c.data.Dimension = dimension
    c.data.Periodic = int(periodic)
    c.data.KnotPointsCount = 5 if periodic else 7
    knots = tuple(
        float(i) / (c.data.KnotPointsCount - 1) for i in range(c.data.KnotPointsCount)
    )
    controls = tuple((0.25, -0.0, 0.5, 2.0)[:dimension]) * 4
    c.data.GetControlPoints.return_value = (True, controls)
    c.data.GetKnotPoints.return_value = (True, knots)
    evidence = {}
    result, face = witness.snapshot(c.app, c.view, c.entity, evidence=evidence)
    assert face is c.face and result["curve_kind"] == "bcurve-3005"
    row = result["curve_parameters"]
    assert row["domain"] == (2.0, 5.0)
    assert row["closure"] == ("closed" if closed else "open")
    assert row["spline"]["Periodic"] == int(periodic)
    assert row["control_points"] == controls and row["knots"] == knots
    assert row["control_points"][1].hex() == (-0.0).hex()
    c.curve.GetBCurveParams5.assert_called_once_with(False, False, not periodic, closed)
    c.curve.GetEndParams.assert_called_once_with()
    c.data.GetControlPoints.assert_called_once_with()
    c.data.GetKnotPoints.assert_called_once_with()
    assert (
        len(row["reads"]) == 10
    )  # identity, IsBcurve, domain, five metadata, two arrays
    json.dumps(evidence, allow_nan=False)


@pytest.mark.parametrize("mode", [None, "off"])
def test_default_bcurve_rejection_and_getters_are_unchanged(bcurve, monkeypatch, mode):
    c = bcurve
    if mode is None:
        monkeypatch.delenv("HARMONIC_SILHOUETTE_CURVE_CONTROL")
    else:
        monkeypatch.setenv("HARMONIC_SILHOUETTE_CURVE_CONTROL", mode)
    evidence = {}
    with pytest.raises(RuntimeError, match="unsupported or contradictory"):
        witness.snapshot(c.app, c.view, c.entity, evidence=evidence)
    assert [row["method"] for row in evidence["curve_reads"]] == [
        "IsLine",
        "IsCircle",
        "Identity",
    ]
    c.curve.Identity.assert_called_once_with()
    c.curve.IsBcurve.assert_not_called()
    c.curve.GetEndParams.assert_not_called()
    c.curve.GetBCurveParams5.assert_not_called()


@pytest.mark.parametrize("mode", ["", "3005", "true", "BCURVE-3005"])
def test_invalid_control_rejects_before_pilot_or_native_calls(monkeypatch, mode):
    monkeypatch.setenv("HARMONIC_SILHOUETTE_CURVE_CONTROL", mode)
    with pytest.raises(ValueError, match="HARMONIC_SILHOUETTE_CURVE_CONTROL"):
        pilot.main([])


@pytest.mark.parametrize(
    "field,value",
    [
        ("Identity", 3004),
        ("Identity", 3005.0),
        ("IsBcurve", 1),
        ("IsBcurve", False),
        ("GetEndParams", None),
        ("GetEndParams", (1, 2.0, 5.0, False, False)),
        ("GetEndParams", (True, 2, 5.0, False, False)),
        ("GetEndParams", (True, 5.0, 2.0, False, False)),
        ("GetEndParams", (True, 2.0, float("inf"), False, False)),
        ("GetEndParams", (True, 2.0, 5.0, 0, False)),
        ("GetBCurveParams5", None),
    ],
)
def test_curve_boundary_rejections_keep_partial_native_evidence(bcurve, field, value):
    c = bcurve
    getattr(c.curve, field).return_value = value
    evidence = {}
    with pytest.raises(RuntimeError, match="BCURVE"):
        witness.snapshot(c.app, c.view, c.entity, evidence=evidence)
    assert evidence["bcurve"]
    c.data.GetControlPoints.assert_not_called()
    c.data.GetKnotPoints.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [
        ("Dimension", 2),
        ("Dimension", True),
        ("Order", 1),
        ("Order", 65),
        ("Periodic", True),
        ("Periodic", 1),
        ("ControlPointsCount", 2),
        ("ControlPointsCount", 10001),
        ("KnotPointsCount", 10065),
        ("KnotPointsCount", 6),
    ],
)
def test_metadata_boundaries_reject_before_bulk_reads(bcurve, field, value):
    c = bcurve
    setattr(c.data, field, value)
    evidence = {}
    with pytest.raises(RuntimeError, match="BCURVE"):
        witness.snapshot(c.app, c.view, c.entity, evidence=evidence)
    assert len(evidence["bcurve"]["spline"]) == 5
    c.data.GetControlPoints.assert_not_called()
    c.data.GetKnotPoints.assert_not_called()


@pytest.mark.parametrize(
    "method,value",
    [
        ("GetControlPoints", None),
        ("GetControlPoints", (False, (0.0,) * 16)),
        ("GetControlPoints", (1, (0.0,) * 16)),
        ("GetControlPoints", (True, (0.0,) * 15)),
        ("GetControlPoints", (True, (True,) + (0.0,) * 15)),
        ("GetControlPoints", (True, (0,) + (0.0,) * 15)),
        ("GetControlPoints", (True, (float("nan"),) + (0.0,) * 15)),
        ("GetKnotPoints", (True, (0.0, 0.0, 0.0, 0.5, 0.2, 1.0, 1.0))),
        ("GetKnotPoints", (True, (0.0,) * 6)),
    ],
)
def test_failed_arrays_are_retained_before_validation(bcurve, method, value):
    c = bcurve
    getattr(c.data, method).return_value = value
    evidence = {}
    with pytest.raises(RuntimeError, match="BCURVE"):
        witness.snapshot(c.app, c.view, c.entity, evidence=evidence)
    assert evidence["bcurve"]["reads"][-1]["method"] == method
    assert "returned" in evidence["bcurve"]["reads"][-1]
    getattr(c.data, method).assert_called_once_with()
    json.dumps(evidence, allow_nan=False)


@pytest.mark.parametrize(
    "method",
    [
        "Identity",
        "IsBcurve",
        "GetEndParams",
        "GetBCurveParams5",
        "GetControlPoints",
        "GetKnotPoints",
    ],
)
def test_native_getter_error_is_original_and_never_retried(bcurve, method):
    c = bcurve
    native = c.data if method in {"GetControlPoints", "GetKnotPoints"} else c.curve
    primary = OSError(f"{method} native rejection")
    getattr(native, method).side_effect = primary
    evidence = {}
    with pytest.raises(OSError) as raised:
        witness.snapshot(c.app, c.view, c.entity, evidence=evidence)
    assert raised.value is primary
    assert repr(primary) in json.dumps(evidence)
    getattr(native, method).assert_called_once_with(
        *((False, False, True, False) if method == "GetBCurveParams5" else ())
    )


@pytest.mark.parametrize(
    "change,reason",
    [
        ("coefficient", "raw geometry"),
        ("weight", "raw geometry"),
        ("face", "silhouette face"),
        ("view", "owning view"),
        ("pid", "PersistentID"),
    ],
)
def test_bcurve_coefficients_never_replace_identity_or_exact_equality(
    bcurve, change, reason
):
    c = bcurve
    other = NS(**vars(c.entity))
    if change in {"coefficient", "weight"}:
        changed = deepcopy(c.data)
        values = list(changed.GetControlPoints.return_value[1])
        values[0 if change == "coefficient" else 3] += 1e-15
        changed.GetControlPoints.return_value = (True, tuple(values))
        c.curve.GetBCurveParams5.side_effect = [c.data, changed]
    if change == "face":
        other.GetFace = lambda: NS(**vars(c.face))
    if change == "view":
        other.GetView = object
    if change == "pid":
        other.persistent_ref = (7, 8, 9)
    with pytest.raises(RuntimeError, match=reason):
        witness.require_same(
            c.app,
            c.view,
            c.entity,
            other,
            drawing=c.app.drawing,
            label="tooth",
            evidence={},
        )


def test_actual_view_banks_use_fresh_cold_entities_and_reject_raw_drift(
    bcurve, bank, monkeypatch
):
    c = bcurve
    entity = silhouette_bank(bank, monkeypatch)
    entity.GetCurve = lambda: c.curve
    with bank.witness.observe(bank.adapter):
        bank.module.add_surface_finish(
            bank.adapter,
            bank.view,
            label="finish",
            entity=entity,
            entity_type="SILHOUETTE",
        )
    built = bank.witness.drawing_snapshot(bank.adapter, phase="built")
    cold_entity = NS(**vars(entity))
    cold_view = NS(
        GetName2=lambda: "Drawing View1",
        GetOrientationName=lambda: "*Front",
        entity=cold_entity,
    )
    cold_entity.GetView = lambda: cold_view
    annotation = NS(**vars(bank.annotations["finish"]))
    annotation.Owner = cold_view
    annotation.GetAttachedEntities3 = lambda: (cold_entity,)
    cold_view.GetAnnotations = lambda: (annotation,)
    from diagnostics import _recipe_view_entity_acceptance as observer

    monkeypatch.setattr(
        observer.attachments, "views", lambda _: {"Sheet/View": cold_view}
    )
    entity.GetCurve = Mock(side_effect=AssertionError("closed silhouette queried"))
    bank.view.GetName2 = Mock(side_effect=AssertionError("closed view queried"))
    bank.annotations["finish"].GetName = Mock(
        side_effect=AssertionError("closed annotation queried")
    )
    reopened = bank.witness.drawing_snapshot(bank.adapter, phase="reopened")
    assert bank.witness.compare_cold(built, reopened)["status"] == "passed"
    changed = deepcopy(reopened)
    values = list(
        changed["explicit"]["finish"]["geometry"]["curve_parameters"]["control_points"]
    )
    values[0] += 1e-15
    changed["explicit"]["finish"]["geometry"]["curve_parameters"]["control_points"] = (
        tuple(values)
    )
    assert bank.witness.compare_cold(built, changed)["status"] == "failed"


def test_complete_column_row_surface_and_bcurve_banks_are_both_retained(
    bcurve, monkeypatch
):
    from test_bsurface_silhouette_drawing import bsurface_fixture
    from test_bsurface_column_row_control_drawing import native_shaped_data

    c = bsurface_fixture()
    native_shaped_data(c.data)
    c.entity.GetCurve = lambda: bcurve.curve
    monkeypatch.setattr(witness.bsurface, "_early_bound", lambda obj, _: obj)
    monkeypatch.setenv("HARMONIC_BSURF_GRID_CONTROL", "column-row-reader")
    evidence = {}
    result, face = witness.snapshot(c.app, c.view, c.entity, evidence=evidence)
    assert face is c.face
    assert c.data.GetControlPoints.call_count == 125
    assert len(result["face_surface"]["bspline"]["control_points"]) == 5
    assert all(
        len(row) == 25 for row in result["face_surface"]["bspline"]["control_points"]
    )
    assert result["curve_parameters"] == evidence["bcurve"]
    assert (
        result["curve_parameters"]["control_points"]
        == bcurve.data.GetControlPoints.return_value[1]
    )
    bcurve.data.GetControlPoints.assert_called_once_with()
    json.dumps(evidence, allow_nan=False)


@pytest.mark.parametrize("family", ["line", "circle"])
def test_optin_does_not_add_getters_to_existing_analytic_branches(bcurve, family):
    c = bcurve
    c.curve.IsLine.return_value = family == "line"
    c.curve.IsCircle.return_value = family == "circle"
    c.curve.CircleParams = (0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.002)
    result, _ = witness.snapshot(c.app, c.view, c.entity, evidence={})
    assert result["curve_kind"] == family
    c.curve.Identity.assert_not_called()
    c.curve.IsBcurve.assert_not_called()
    c.curve.GetEndParams.assert_not_called()
    c.curve.GetBCurveParams5.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("control", ["off", "bcurve-3005"])
@pytest.mark.parametrize("mode", ["normal", "build_failure"])
async def test_actual_pilot_retains_explicit_control_on_success_and_failure(
    tmp_path, monkeypatch, control, mode
):
    from test_datum_policy_recipes_drawing import (
        test_one_fresh_recipe_each_in_order_and_stop_first_failure as exercise_pilot,
    )

    monkeypatch.setenv("HARMONIC_SILHOUETTE_CURVE_CONTROL", control)
    # This is an intentional observer-off control, not the matched tooth replay.
    monkeypatch.setenv("HARMONIC_TOOTH_SELECTOR_OBSERVATION", "off")
    await exercise_pilot(tmp_path, monkeypatch, mode, ("channel_lever",))
    (path,) = (tmp_path / "reports").glob("*/pilot.json")
    assert (
        json.loads(path.read_text(encoding="utf-8"))["silhouette_curve_control"]
        == control
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", ["main", "pilot"])
async def test_bcurve_requires_explicit_observer_before_routing(
    tmp_path, monkeypatch, entry
):
    monkeypatch.setenv("HARMONIC_SILHOUETTE_CURVE_CONTROL", "bcurve-3005")
    monkeypatch.delenv("HARMONIC_TOOTH_SELECTOR_OBSERVATION", raising=False)
    with pytest.raises(
        ValueError, match="HARMONIC_TOOTH_SELECTOR_OBSERVATION.*explicit"
    ):
        if entry == "main":
            pilot.main(["--help"])
            return
        await pilot.pilot(
            object(), "candidate", tmp_path, tmp_path, tmp_path / "reports"
        )
    assert not (tmp_path / "reports").exists()


@pytest.mark.parametrize("observer", ["off", "endpoints"])
def test_explicit_observer_values_are_accepted_before_help(monkeypatch, observer):
    monkeypatch.setenv("HARMONIC_SILHOUETTE_CURVE_CONTROL", "bcurve-3005")
    monkeypatch.setenv("HARMONIC_TOOTH_SELECTOR_OBSERVATION", observer)
    with pytest.raises(SystemExit) as raised:
        pilot.main(["--help"])
    assert raised.value.code == 0


@pytest.mark.parametrize("observer", ["", "ENDPOINTS", "unknown"])
def test_invalid_explicit_observer_still_rejects_before_help(monkeypatch, observer):
    monkeypatch.setenv("HARMONIC_SILHOUETTE_CURVE_CONTROL", "bcurve-3005")
    monkeypatch.setenv("HARMONIC_TOOTH_SELECTOR_OBSERVATION", observer)
    with pytest.raises(ValueError, match="HARMONIC_TOOTH_SELECTOR_OBSERVATION"):
        pilot.main(["--help"])


def test_default_curve_control_does_not_require_observer(monkeypatch):
    monkeypatch.delenv("HARMONIC_SILHOUETTE_CURVE_CONTROL", raising=False)
    monkeypatch.delenv("HARMONIC_TOOTH_SELECTOR_OBSERVATION", raising=False)
    with pytest.raises(SystemExit) as raised:
        pilot.main(["--help"])
    assert raised.value.code == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["passed", "radius_rejected"])
async def test_matched_endpoints_control_reaches_actual_pilot_and_keeps_guards(
    tmp_path, monkeypatch, scene, outcome
):
    from test_tooth_selector_observation_drawing import (
        test_actual_owned_pilot_scope_retains_journal_and_source_guards as exercise_pilot,
    )

    monkeypatch.setenv("HARMONIC_SILHOUETTE_CURVE_CONTROL", "bcurve-3005")
    await exercise_pilot(
        scene=scene, monkeypatch=monkeypatch, tmp_path=tmp_path, outcome=outcome
    )
    (path,) = (tmp_path / "reports").glob("*/pilot.json")
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["silhouette_curve_control"] == "bcurve-3005"
    assert report["tooth_selector_observation"] == "endpoints"


def test_real_recipe_gate_enrolls_control_tests_and_reader_exactly_once():
    import dodo

    recipe = next(task for task in dodo.task_check() if task["name"] == "recipe")
    commands = [Path(item).resolve() for item in recipe["actions"][0][1][0]]
    dependencies = [Path(item).resolve() for item in recipe["file_dep"]]
    assert commands.count(Path(__file__).resolve()) == 1
    assert dependencies.count(Path(__file__).resolve()) == 1
    reader = Path(__file__).parent / "diagnostics/_silhouette_bcurve_witness.py"
    assert dependencies.count(reader.resolve()) == 1
