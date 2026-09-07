"""Separate-source positive coverage; historical one-source negative stays loud."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from diagnostics import probe_crankshaft_curves as probe
from diagnostics import _owned_native_documents as owned
from test_crankshaft_curve_readback_drawing import edge as edge
from test_owned_native_documents_drawing import Model, native as native


@pytest.fixture
def crankshaft_shape(monkeypatch, edge):
    """Receipt zj92q9yo: circles 1..6, PinHole intersections 0/7, no lines."""
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    surface = NS(
        Identity=lambda: 4002,
        IsCylinder=lambda: True,
        CylinderParams=(0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.002489),
    )
    hole_face, other_face = (NS(GetSurface=lambda: surface) for _ in range(2))
    feature = NS(Name="PinHole", GetFaces=lambda: (hole_face,))
    monkeypatch.setattr(probe, "_feature_by_name", lambda adapter, name: feature)
    edges = []
    for index in range(8):
        item = deepcopy(edge.edge)
        curve = item.GetCurve.return_value
        intersection = index in (0, 7)
        curve.Identity.return_value = 3004 if intersection else 3002
        curve.IsCircle.return_value = not intersection
        curve.IsBcurve.return_value = intersection
        face = hole_face if intersection else other_face
        item.GetTwoAdjacentFaces2 = lambda face=face: (face, None)
        edges.append(item)
    model = NS(GetBodies2=lambda *args: (NS(GetEdges=lambda: edges),))
    return NS(currentModel=model, swApp=NS(IsSame=lambda a, b: int(a is b)))


def test_recorded_single_part_negative_remains_failure_with_all_eight_rows(
    crankshaft_shape,
):
    report = {}
    with pytest.raises(
        RuntimeError,
        match="^native line/circle/PinHole nonanalytic coverage incomplete$",
    ):
        probe.capture_edges(crankshaft_shape, report, lambda: None)
    assert report["coverage"] == {
        "line": [],
        "circle": list(range(1, 7)),
        "PinHole_nonanalytic": [0, 7],
    }
    assert len(report["edges"]) == 8
    assert all(row["status"] == "captured" for row in report["edges"])


@pytest.mark.parametrize(
    "damage", [None, "no_circle", "other_kind", "failed_getter", "no_feature"]
)
def test_paired_crankshaft_requires_native_circle_and_exact_feature_intersections(
    crankshaft_shape, damage
):
    edges = crankshaft_shape.currentModel.GetBodies2()[0].GetEdges()
    if damage == "no_circle":
        for item in edges[1:7]:
            item.GetCurve.return_value.IsCircle.return_value = False
    if damage == "other_kind":
        edges[0].GetCurve.return_value.Identity.return_value = 3005
    if damage == "failed_getter":
        edges[0].GetCurve.return_value.GetBCurveParams5.return_value = None
    if damage == "no_feature":
        for index in (0, 7):
            edges[index].GetTwoAdjacentFaces2 = lambda: (None, None)
    report = {}
    if damage is not None:
        with pytest.raises(RuntimeError):
            probe.capture_intersections(crankshaft_shape, report, lambda: None)
        return
    probe.capture_intersections(crankshaft_shape, report, lambda: None)
    assert report["coverage"]["PinHole_intersection"] == [0, 7]
    assert report["coverage"]["circle"] == list(range(1, 7))
    assert report["coverage"]["line"] == []


@pytest.mark.parametrize(
    "damage", [None, "no_line", "wrong_kind", "failed_line", "non_boolean"]
)
def test_rocker_line_positive_control_uses_actual_native_predicate_no_retry(
    monkeypatch, edge, damage
):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    curve = edge.curve
    curve.Identity.return_value = 3001
    curve.IsLine.return_value = True
    curve.IsBcurve.return_value = False
    if damage == "no_line":
        curve.IsLine.return_value = False
    if damage == "wrong_kind":
        curve.Identity.return_value = 3004
    if damage == "failed_line":
        curve.GetEndParams.return_value = (False, 0.0, 1.0, False, False)
    if damage == "non_boolean":
        curve.IsLine.return_value = 1
    later = deepcopy(edge.edge)
    model = NS(GetBodies2=lambda *args: (NS(GetEdges=lambda: (edge.edge, later)),))
    report = {}
    if damage is not None:
        with pytest.raises(RuntimeError):
            probe.capture_line(NS(currentModel=model), report, lambda: None)
        if damage != "no_line":
            later.GetCurve.assert_not_called()
        return
    probe.capture_line(NS(currentModel=model), report, lambda: None)
    assert report["coverage"] == {"line": [0]}
    assert report["edges"][0]["existing_geometry"][0] == "line"
    curve.GetBCurveParams5.assert_not_called()
    later.GetCurve.assert_not_called()


@pytest.mark.parametrize(
    "outcome",
    [
        "pass",
        "line_failure",
        "intersection_failure",
        "copy_write",
        "prior_copy_write",
        "runtime",
        "cleanup",
    ],
)
def test_pair_pins_both_sources_retains_failed_receipt_and_stops_first_failure(
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
    rocker = tmp_path / "rocker-arm.SLDPRT"
    rocker.write_bytes(b"pinned rocker")
    expected = {
        "rocker_arm": probe.file_digest(rocker),
        "crankshaft": probe.file_digest(native.source),
    }
    monkeypatch.setattr(probe.pilot, "EXPECTED_PART_HASHES", expected)
    user = Model(None, title="Unrelated unsaved drawing", dirty=True)
    native.app.documents.append(user)
    native.app.ActiveDoc = user
    observed, dimension = [], object()

    def dimensions(model, target, path):
        assert path not in (rocker, native.source)
        assert Path(model.path) == path
        observed.append(target)
        return {"configuration": "Default", "dimensions": {"value": 1}}, {
            "value": dimension
        }

    monkeypatch.setattr(probe.pilot, "source_dimensions", dimensions)
    stages, copies = [], []

    def capture(adapter, report, checkpoint):
        stage = report["proof"]
        stages.append(stage)
        copies.append(Path(report["copy"]))
        assert probe.file_digest(rocker) == expected["rocker_arm"]
        assert probe.file_digest(native.source) == expected["crankshaft"]
        report["edges"] = [{"status": "captured", "raw": [True, 3.25]}]
        report["coverage"] = (
            {"line": [0]}
            if stage == "rocker_line"
            else {"circle": [1], "PinHole_intersection": [0]}
        )
        checkpoint()
        if outcome == "line_failure" and stage == "rocker_line":
            raise RuntimeError("line positive control failed")
        if outcome == "intersection_failure" and stage == "crankshaft_intersections":
            raise RuntimeError("intersection positive control failed")
        if outcome == "copy_write":
            Path(adapter.currentModel.path).write_bytes(b"unexpected save")
        if outcome == "prior_copy_write" and stage == "crankshaft_intersections":
            copies[0].write_bytes(b"first copy changed during second stage")
        if outcome == "runtime":
            monkeypatch.setattr(
                probe.pilot, "adapter_fingerprints", lambda: {"changed": 1}
            )
        if outcome == "cleanup":

            async def reject():
                raise RuntimeError("cleanup refused")

            monkeypatch.setattr(adapter.ownership, "close_owned_documents", reject)
            raise RuntimeError("primary before cleanup")

    monkeypatch.setattr(probe, "capture_line", capture)
    monkeypatch.setattr(probe, "capture_intersections", capture)
    guarded = owned.DiagnosticAdapter(native.adapter)
    operation = probe.paired_probe(guarded, native.source, rocker, tmp_path / "reports")
    if outcome == "pass":
        asyncio.run(operation)
    else:
        with pytest.raises(ExceptionGroup):
            asyncio.run(operation)
    (receipt,) = (tmp_path / "reports").glob("*/paired-curves.json")
    report = json.loads(receipt.read_text())
    assert stages == (
        ["rocker_line", "crankshaft_intersections"]
        if outcome in ("pass", "intersection_failure", "prior_copy_write")
        else ["rocker_line"]
    )
    assert observed == [
        target
        for stage in stages
        for target in (
            ["rocker_arm"] * 2 if stage == "rocker_line" else ["crankshaft"] * 2
        )
    ]
    assert len(report["trials"]) == len(stages)
    assert report["status"] == ("captured" if outcome == "pass" else "failed")
    for trial in report["trials"]:
        child_path = Path(trial["report"])
        child = json.loads(child_path.read_text())
        assert trial["sha256"] == probe.file_digest(child_path)
        assert child["edges"][0]["raw"] == [True, 3.25]
        assert child["copy"] in report["final_inputs"]
    assert probe.file_digest(rocker) == expected["rocker_arm"]
    assert probe.file_digest(native.source) == expected["crankshaft"]
    assert user in native.app.documents and user.dirty
    if outcome != "cleanup":
        assert native.app.documents == [user]
    if outcome in ("copy_write", "prior_copy_write", "runtime"):
        assert report["final_guard_errors"]


@pytest.mark.parametrize("wrong_target", ["rocker_arm", "crankshaft"])
def test_pair_rejects_either_wrong_original_before_opening_any_copy(
    native, monkeypatch, tmp_path, wrong_target
):
    monkeypatch.setattr(probe.pilot, "helper_fingerprints", lambda: {})
    monkeypatch.setattr(probe.pilot, "adapter_fingerprints", lambda: {})
    rocker = tmp_path / "rocker.SLDPRT"
    rocker.write_bytes(b"rocker")
    expected = {
        "rocker_arm": probe.file_digest(rocker),
        "crankshaft": probe.file_digest(native.source),
    }
    expected[wrong_target] = "wrong pinned hash"
    monkeypatch.setattr(probe.pilot, "EXPECTED_PART_HASHES", expected)
    guarded = owned.DiagnosticAdapter(native.adapter)
    with pytest.raises(ExceptionGroup):
        asyncio.run(
            probe.paired_probe(guarded, native.source, rocker, tmp_path / "reports")
        )
    (receipt,) = (tmp_path / "reports").glob("*/paired-curves.json")
    report = json.loads(receipt.read_text())
    assert report["trials"] == []
    assert f"wrong pinned {wrong_target}" in report["errors"][0]
    assert native.adapter.opens == []


@pytest.mark.parametrize(
    "mode,rocker", [("paired_sources", None), ("single_part_negative", "extra.SLDPRT")]
)
def test_cli_requires_exact_source_contract_before_parent_wrapper(
    monkeypatch, mode, rocker
):
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", "31860")
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    arguments = ["--source", "not-opened.SLDPRT", "--mode", mode]
    if rocker is not None:
        arguments += ["--rocker-source", rocker]
    with pytest.raises(ValueError, match="requires --rocker-source"):
        probe.main(arguments)
