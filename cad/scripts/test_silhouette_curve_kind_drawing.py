"""Rejected curve observations cannot become acceptance or replace its error."""

import json
from unittest.mock import Mock, call

import pytest

from diagnostics import _silhouette_attachment_witness as witness
from diagnostics import _recipe_view_entity_acceptance as observer
from diagnostics._recipe_view_roles import VIEW_ROLES
from test_bsurface_column_row_control_drawing import native_shaped_data
from test_bsurface_silhouette_drawing import (
    bank as bank,
    bsurface as bsurface,
    bsurface_binding as bsurface_binding,
    early_bound as early_bound,
)


UNSUPPORTED = "unsupported or contradictory silhouette curve kind"


@pytest.mark.parametrize("line,circle", [(False, False), (True, True), (None, 0), (1, "yes")])
def test_rejected_predicates_retain_literal_types_arguments_and_identity(
    bsurface, line, circle,
):
    c = bsurface
    c.curve.IsLine = Mock(return_value=line)
    c.curve.IsCircle = Mock(return_value=circle)
    c.curve.Identity = Mock(return_value=3004)
    evidence = {}
    with pytest.raises(RuntimeError, match=UNSUPPORTED):
        witness.require_same(
            c.app, c.view, c.entity, c.entity, drawing=c.app.drawing,
            label="tooth", evidence=evidence,
        )
    partial = evidence["expected"]
    reads = partial["curve_reads"]
    assert [row["method"] for row in reads] == ["IsLine", "IsCircle", "Identity"]
    assert all(row["arguments"] == () for row in reads)
    for row, value in zip(reads, (line, circle, 3004), strict=True):
        assert row["returned"] == {"type": f"builtins.{type(value).__name__}", "value": value}
    assert set(partial) == {"face_surface", "curve_reads"}
    assert len(partial["face_surface"]["bspline"]["control_points"]) == 2
    assert "actual" not in evidence and "persistent_identity" not in evidence
    c.curve.IsLine.assert_called_once_with()
    c.curve.IsCircle.assert_called_once_with()
    c.curve.Identity.assert_called_once_with()
    json.dumps(evidence, allow_nan=False)


@pytest.mark.parametrize("returned", [None, True, "3005", 3005])
def test_diagnostic_identity_is_literal_evidence_never_a_fallback(bsurface, returned):
    c = bsurface
    c.curve.IsLine = Mock(return_value=False)
    c.curve.Identity = Mock(return_value=returned)
    evidence = {}
    with pytest.raises(RuntimeError) as raised:
        witness.snapshot(c.app, c.view, c.entity, evidence=evidence)
    assert str(raised.value) == UNSUPPORTED
    assert evidence["curve_reads"][-1]["returned"] == {
        "type": f"builtins.{type(returned).__name__}", "value": returned,
    }
    c.curve.Identity.assert_called_once_with()


def test_identity_getter_error_cannot_replace_classification_failure(bsurface):
    c = bsurface
    c.curve.IsLine = Mock(return_value=False)
    secondary = OSError("native Identity rejected")
    c.curve.Identity = Mock(side_effect=secondary)
    evidence = {}
    with pytest.raises(RuntimeError) as raised:
        witness.snapshot(c.app, c.view, c.entity, evidence=evidence)
    assert str(raised.value) == UNSUPPORTED and raised.value is not secondary
    assert evidence["curve_reads"][-1] == {
        "method": "Identity", "arguments": (), "returned": {"error": repr(secondary)},
    }
    c.curve.Identity.assert_called_once_with()


def test_rejection_without_evidence_sink_does_not_add_identity_getter(bsurface):
    c = bsurface
    c.curve.IsLine = Mock(return_value=False)
    c.curve.IsCircle = Mock(return_value=False)
    c.curve.Identity = Mock(side_effect=AssertionError("unretained diagnostic getter"))
    with pytest.raises(RuntimeError, match=UNSUPPORTED):
        witness.snapshot(c.app, c.view, c.entity)
    c.curve.IsLine.assert_called_once_with()
    c.curve.IsCircle.assert_called_once_with()
    c.curve.Identity.assert_not_called()


@pytest.mark.parametrize("field", ["IsLine", "IsCircle"])
def test_predicate_exception_keeps_primary_identity_and_partial_journal(bsurface, field):
    c = bsurface
    primary = RuntimeError(f"native {field} failed")
    c.curve.IsLine = Mock(return_value=False)
    c.curve.IsCircle = Mock(return_value=False)
    getattr(c.curve, field).side_effect = primary
    c.curve.Identity = Mock(side_effect=AssertionError("not a classified rejection"))
    evidence = {}
    with pytest.raises(RuntimeError) as raised:
        witness.snapshot(c.app, c.view, c.entity, evidence=evidence)
    assert raised.value is primary
    reads = evidence["curve_reads"]
    assert reads[-1] == {
        "method": field, "arguments": (), "returned": {"error": repr(primary)},
    }
    assert len(reads) == (1 if field == "IsLine" else 2)
    assert evidence["face_surface"]["identity"] == 4006
    c.curve.IsLine.assert_called_once_with()
    assert c.curve.IsCircle.call_count == (0 if field == "IsLine" else 1)
    c.curve.Identity.assert_not_called()


@pytest.mark.parametrize("kind", ["line", "circle"])
def test_accepted_geometry_and_native_read_count_unchanged(bsurface, kind):
    c = bsurface
    c.curve.IsLine = Mock(return_value=kind == "line")
    c.curve.IsCircle = Mock(return_value=kind == "circle")
    c.curve.CircleParams = (0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.003)
    c.curve.Identity = Mock(side_effect=AssertionError("accepted path extra read"))
    baseline, face = witness.snapshot(c.app, c.view, c.entity)
    c.curve.IsLine.reset_mock()
    c.curve.IsCircle.reset_mock()
    c.data.GetControlPoints.reset_mock()
    evidence = {}
    actual, actual_face = witness.snapshot(c.app, c.view, c.entity, evidence=evidence)
    assert actual == baseline and actual_face is face
    assert actual["curve_kind"] == kind
    assert set(actual) == {"curve_kind", "curve_parameters", "start", "end", "face_surface"}
    assert [row["method"] for row in evidence["curve_reads"]] == ["IsLine", "IsCircle"]
    c.curve.IsLine.assert_called_once_with()
    c.curve.IsCircle.assert_called_once_with()
    c.curve.Identity.assert_not_called()
    assert c.data.GetControlPoints.call_args_list == [
        call(row, column) for row in (1, 2) for column in (1, 2, 3, 4)
    ]


def test_encoder_error_does_not_replace_rejection(bsurface, monkeypatch):
    c = bsurface
    c.curve.IsLine = Mock(return_value=False)
    c.curve.Identity = Mock(return_value=3005)
    secondary = ValueError("journal encoding failed")
    monkeypatch.setattr(witness.bsurface, "_raw_return", Mock(side_effect=secondary))
    evidence = {}
    with pytest.raises(RuntimeError) as raised:
        witness.snapshot(c.app, c.view, c.entity, evidence=evidence)
    assert str(raised.value) == UNSUPPORTED
    assert evidence["curve_reads"][-1]["returned"] == {
        "type": "builtins.int", "observation_error": repr(secondary),
    }
    c.curve.Identity.assert_called_once_with()


@pytest.mark.parametrize("failure", ["unsupported", "predicate"])
def test_actual_view_observer_keeps_error_surface_journal_and_aliases(
    bsurface, bank, monkeypatch, failure,
):
    c = bsurface
    monkeypatch.setenv("HARMONIC_BSURF_GRID_CONTROL", "column-row-reader")
    native_shaped_data(c.data)
    label = "gear tooth-tip circular runout"
    bank.manifest.view_roles.clear()
    bank.manifest.view_roles[label] = VIEW_ROLES["crank_drive_gear"][label]
    bank.view.GetOrientationName = lambda: "*Right"
    bank.adapter.currentModel.GetType = lambda: 3
    bank.adapter.currentModel.Extension = c.app.drawing.Extension
    bank.entity = bank.view.entity = c.entity
    c.entity.GetView = lambda: bank.view
    bank.manager.GetSelectedObjectType3 = lambda *_: 46
    primary = RuntimeError("native classification getter failed")
    c.curve.IsLine = Mock(return_value=False)
    c.curve.IsCircle = Mock(return_value=False)
    if failure == "predicate":
        c.curve.IsCircle.side_effect = primary
    secondary = OSError("Identity observation unavailable")
    c.curve.Identity = Mock(side_effect=secondary)
    with pytest.raises(RuntimeError) as raised:
        with bank.witness.observe(bank.adapter):
            bank.module.add_feature_control_frame(
                bank.adapter, bank.view, label=label,
                entity=c.entity, entity_type="SILHOUETTE",
            )
    if failure == "predicate":
        assert raised.value is primary
        c.curve.Identity.assert_not_called()
    else:
        assert str(raised.value) == UNSUPPORTED
        c.curve.Identity.assert_called_once_with()
    stages = bank.witness.context_report["stages"]
    assert len(stages) == 1 and stages[0]["stage"] == "selected"
    assert stages[0]["error"] == repr(raised.value)
    partial = stages[0]["silhouette"]["expected"]
    spline = partial["face_surface"]["bspline"]
    assert len(spline["control_points"]) == 5
    assert all(len(row) == 25 for row in spline["control_points"])
    assert c.data.GetControlPoints.call_count == 125
    assert partial["curve_reads"][-1]["returned"]["error"] == repr(
        primary if failure == "predicate" else secondary
    )
    c.curve.IsLine.assert_called_once_with()
    c.curve.IsCircle.assert_called_once_with()
    assert bank.witness.recorded == bank.witness.selected == bank.annotations == {}
    assert observer.drawing._select_annotation_entity is bank.selected
    for name, original in bank.originals.items():
        assert getattr(bank.module, name) is original
        assert getattr(observer.drawing, name) is original
    json.dumps(bank.witness.context_report, allow_nan=False)
