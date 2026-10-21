"""Pure data/error/evidence tests; no COM, SDK, telemetry, renderer, or farm calls."""

from __future__ import annotations

import asyncio
from collections import Counter
from contextlib import asynccontextmanager, nullcontext
from dataclasses import replace
import hashlib
import json
from io import StringIO
import math
from types import SimpleNamespace
from pathlib import Path
import sys

import pytest

import _bulk_visibility_contract_probe as probe


def fixture_nodes(**visibility: bool) -> dict[probe.NodeId, probe.NodeState]:
    return {
        key: probe.NodeState(
            key=key,
            parent=probe.PARENTS[key],
            family=probe.FAMILIES[key],
            own=visibility.get(key, True),
            component_path=f"N-1/{key}" if probe.PARENTS[key] else str(key),
            source_path=f"/{probe.FAMILIES[key] or 'N'}.sldasm",
            configuration="Default",
            transform=probe.translation(0.0),
        )
        for key in probe.NodeId
    }


def test_real_parent_own_flags_and_effective_visibility_are_distinct() -> None:
    nodes = fixture_nodes(N=False)
    observed = probe.effective(nodes)
    assert nodes[probe.NodeId.P1].own is True
    assert observed == {
        probe.NodeId.N: False,
        probe.NodeId.P1: False,
        probe.NodeId.P2: False,
        probe.NodeId.Q1: False,
        probe.NodeId.Q2: True,
    }


@pytest.mark.parametrize(
    "change",
    [
        {"parent": None},
        {"family": probe.Family.Q},
        {"key": probe.NodeId.P2},
        {"own": 1},
    ],
)
def test_malformed_real_parent_inventory_is_not_plannable(change: dict) -> None:
    nodes = fixture_nodes()
    nodes[probe.NodeId.P1] = replace(nodes[probe.NodeId.P1], **change)
    with pytest.raises(probe.ProbeFailure) as caught:
        probe.plan_families(nodes, frozenset((probe.Family.P,)))
    assert caught.value.verdict is probe.Verdict.PRESERVATION


def test_incomplete_inventory_is_not_a_no_change_success() -> None:
    nodes = fixture_nodes()
    del nodes[probe.NodeId.P2]
    with pytest.raises(probe.ProbeFailure, match="incomplete"):
        probe.effective(nodes)


def test_mixed_family_plan_is_leaf_only_and_does_not_mutate_input() -> None:
    nodes = fixture_nodes(P1=False, P2=False)
    before = dict(nodes)
    assert probe.plan_families(nodes, frozenset((probe.Family.P,))) == (
        (probe.NodeId.Q1, probe.NodeId.Q2),
        (probe.NodeId.P1, probe.NodeId.P2),
    )
    assert nodes == before
    assert nodes[probe.NodeId.N].own is True


@pytest.mark.parametrize(
    ("nodes", "requested", "message"),
    [
        (fixture_nodes(), frozenset(), "empty"),
        (fixture_nodes(), frozenset((probe.Family.MISSING,)), "missing"),
        (fixture_nodes(N=False), frozenset((probe.Family.P,)), "inherit hidden"),
    ],
)
def test_refusal_is_prewrite_and_preserves_inventory(nodes, requested, message) -> None:
    before = dict(nodes)
    with pytest.raises(probe.PrewriteRefusal, match=message) as caught:
        probe.plan_families(nodes, requested)
    assert caught.value.verdict is probe.Verdict.REFUSAL
    assert nodes == before


def test_no_change_does_not_canonicalize_real_parent_or_leaf_flags() -> None:
    nodes = fixture_nodes(P1=False, P2=False)
    assert probe.plan_families(nodes, frozenset((probe.Family.Q,))) == ((), ())
    assert nodes[probe.NodeId.N].own is True
    assert nodes[probe.NodeId.P1].own is False


def test_shown_sibling_can_make_its_family_drawable_without_showing_parent() -> None:
    nodes = fixture_nodes(N=False)
    assert probe.plan_families(nodes, frozenset((probe.Family.Q,))) == (
        (probe.NodeId.P1, probe.NodeId.P2),
        (),
    )
    assert nodes[probe.NodeId.N].own is False
    assert probe.effective(nodes)[probe.NodeId.Q1] is False


@pytest.mark.parametrize("identities", [((1, 0), (0, 1)), ((0, 1), (1, 0))])
def test_selection_accepts_only_exact_duplicate_free_native_bijection(
    identities,
) -> None:
    probe.selected_bijection(identities, (20, 20), (0, 0), (1, 1), (1, 1), 2)


@pytest.mark.parametrize(
    ("identities", "types", "marks", "own", "selected", "count", "verdict"),
    [
        (((1,),), (20,), (0,), (1,), (1,), 2, probe.Verdict.SELECTION),
        (
            ((1, 0), (1, 0)),
            (20, 20),
            (0, 0),
            (1, 1),
            (1, 1),
            2,
            probe.Verdict.SELECTION,
        ),
        (
            ((1, 1), (0, 0)),
            (20, 20),
            (0, 0),
            (1, 1),
            (1, 1),
            2,
            probe.Verdict.SELECTION,
        ),
        (((2, 0), (0, 1)), (20, 20), (0, 0), (1, 1), (1, 1), 2, probe.Verdict.IDENTITY),
        (
            ((True, 0), (0, 1)),
            (20, 20),
            (0, 0),
            (1, 1),
            (1, 1),
            2,
            probe.Verdict.IDENTITY,
        ),
        (((1, 0), (0, 1)), (20, 2), (0, 0), (1, 1), (1, 1), 2, probe.Verdict.SELECTION),
        (
            ((1, 0), (0, 1)),
            (20, 20),
            (0, 16),
            (1, 1),
            (1, 1),
            2,
            probe.Verdict.SELECTION,
        ),
        (((1, 0), (0, 1)), (20, 20), (0, 0), (1, 0), (1, 1), 2, probe.Verdict.IDENTITY),
        (((1, 0), (0, 1)), (20, 20), (0, 0), (1, 1), (1, 0), 2, probe.Verdict.IDENTITY),
        (
            ((1, 0), (0, 1)),
            (20, 20),
            (0, 0),
            (1, 1),
            (1, True),
            2,
            probe.Verdict.IDENTITY,
        ),
        ((), (), (), (), (), 0, probe.Verdict.SELECTION),
    ],
)
def test_partial_duplicate_marked_foreign_or_unsupported_selection_fails_closed(
    identities, types, marks, own, selected, count, verdict
) -> None:
    with pytest.raises(probe.ProbeFailure) as caught:
        probe.selected_bijection(identities, types, marks, own, selected, count)
    assert caught.value.verdict is verdict


@pytest.mark.parametrize(
    "value", [None, (), (0.0,) * 15, (math.nan,) * 16, (math.inf,) * 16, (True,) * 16]
)
def test_transform_requires_exact_finite_sixteen_double_array(value) -> None:
    with pytest.raises(probe.ProbeFailure):
        probe.matrix(value, "placement")


def test_translation_and_tolerance_preserve_fixed_fixture_geometry() -> None:
    expected = probe.translation(0.015)
    assert probe.matrix(expected, "placement") == expected
    near = list(expected)
    near[9] += 0.5e-9
    assert probe.equal_transform(near, expected)
    near[9] += 2e-9
    assert not probe.equal_transform(near, expected)
    rotation = list(expected)
    rotation[0] += 2e-12
    assert not probe.equal_transform(rotation, expected)


def component_rows(paths: dict[probe.Document, Path]) -> list[dict]:
    specifications = (
        ("Nested-1", probe.Document.N, 0.0),
        ("Nested-1/P-1", probe.Document.P, -0.015),
        ("Nested-1/P-2", probe.Document.P, 0.0),
        ("Nested-1/Q-1", probe.Document.Q, 0.015),
        ("Q-2", probe.Document.Q, 0.030),
    )
    return [
        {
            "path": name,
            "source": probe.normalized(paths[source]),
            "configuration": "Default",
            "visible": 1,
            "transform": probe.translation(x),
        }
        for name, source, x in specifications
    ]


def test_persisted_fixture_admission_requires_real_nested_paths_and_exact_sources(
    tmp_path,
) -> None:
    paths = {
        key: tmp_path / f"{key}.sldasm"
        for key in (probe.Document.P, probe.Document.Q, probe.Document.N)
    }
    rows = component_rows(paths)
    admitted = probe.fixture_instances(rows, paths, root_assembly=True)
    assert admitted["Nested-1"] is probe.NodeId.N
    assert admitted["Nested-1/P-2"] is probe.NodeId.P2
    assert admitted["Q-2"] is probe.NodeId.Q2
    nested_rows = [
        dict(row, path=row["path"].removeprefix("Nested-1/")) for row in rows[1:4]
    ]
    assert set(
        probe.fixture_instances(nested_rows, paths, root_assembly=False).values()
    ) == {probe.NodeId.P1, probe.NodeId.P2, probe.NodeId.Q1}


@pytest.mark.parametrize(
    "fault",
    [
        "flat",
        "duplicate",
        "wrong_source",
        "wrong_pose",
        "hidden",
        "boolean_visibility",
        "configuration",
        "missing",
    ],
)
def test_invalid_fixture_is_not_a_native_visibility_result(tmp_path, fault) -> None:
    paths = {
        key: tmp_path / f"{key}.sldasm"
        for key in (probe.Document.P, probe.Document.Q, probe.Document.N)
    }
    rows = component_rows(paths)
    if fault == "flat":
        rows[1]["path"] = "P-1"
    elif fault == "duplicate":
        rows[2]["path"] = rows[1]["path"]
    elif fault == "wrong_source":
        rows[1]["source"] = probe.normalized(paths[probe.Document.Q])
    elif fault == "wrong_pose":
        rows[1]["transform"] = probe.translation(-0.014)
    elif fault == "hidden":
        rows[1]["visible"] = 0
    elif fault == "boolean_visibility":
        rows[1]["visible"] = True
    elif fault == "configuration":
        rows[1]["configuration"] = "Other"
    else:
        rows.pop()
    with pytest.raises(probe.ProbeFailure):
        probe.fixture_instances(rows, paths, root_assembly=True)


@pytest.mark.parametrize(
    "value",
    [
        (False, 0, 0),
        (True, 1, 0),
        (True, 0, 1),
        (True, False, 0),
        [True, 0, 0],
        (True, 0),
    ],
)
def test_native_save_out_contract_rejects_false_errors_warnings_or_wrong_shape(
    value,
) -> None:
    with pytest.raises(probe.ProbeFailure) as caught:
        probe.checked_tuple(value, "SaveAs3", save=True)
    assert caught.value.verdict is probe.Verdict.CONSTRUCTION


def test_native_save_and_open_success_have_distinct_result_requirements() -> None:
    assert probe.checked_tuple((True, 0, 0), "save", save=True) == (True, 0, 0)
    identity = object()
    assert probe.checked_tuple((identity, 0, 0), "open", save=False)[0] is identity
    with pytest.raises(probe.ProbeFailure, match="null model"):
        probe.checked_tuple((None, 0, 0), "open", save=False)


def test_projection_uses_outward_rounding_and_pdf_y_inversion() -> None:
    assert probe.roi_box((0.2159, 0.1397, 0.0), 0.008) == (2455, 1555, 2645, 1745)
    lower = probe.roi_box((0.2159, 0.1297, 0.0), 0.008)
    upper = probe.roi_box((0.2159, 0.1497, 0.0), 0.008)
    assert lower[1] > upper[1]


@pytest.mark.parametrize(
    ("centre", "half"),
    [
        ((0.0, 0.0), 0.008),
        ((math.nan, 0.1), 0.008),
        ((0.2, math.inf), 0.008),
        ((0.2, 0.1), math.nan),
        ((0.2, 0.1), -0.008),
        ((True, 0.1), 0.008),
    ],
)
def test_invalid_projection_cannot_qualify_visual_oracle(centre, half) -> None:
    with pytest.raises(probe.ProbeFailure) as caught:
        probe.roi_box(centre, half)
    assert caught.value.verdict is probe.Verdict.VISUAL


def ink_cell() -> bytes:
    return b"".join(
        bytes((0, 0, 0) if 2 <= x < 18 and 2 <= y < 18 else (255, 255, 255))
        for y in range(20)
        for x in range(20)
    )


def test_fixed_rgb_oracle_requires_positive_ink_white_margin_and_exact_restoration() -> (
    None
):
    baseline = ink_cell()
    evidence = probe.validate_rgb_cell(baseline, (20, 20), baseline=None)
    assert evidence["dark_pixels"] == 256
    assert evidence["white_border"] is True
    assert evidence["all_white"] is False
    probe.validate_rgb_cell(baseline, (20, 20), baseline=baseline)
    white = bytes((255,)) * len(baseline)
    probe.validate_rgb_cell(white, (20, 20), baseline=baseline, hidden=True)
    with pytest.raises(probe.ProbeFailure, match="unqualified"):
        probe.validate_rgb_cell(white, (20, 20), baseline=None)
    contaminated = bytearray(baseline)
    contaminated[0] = 0
    with pytest.raises(probe.ProbeFailure, match="unqualified"):
        probe.validate_rgb_cell(bytes(contaminated), (20, 20), baseline=None)
    changed = bytearray(baseline)
    changed[(2 * 20 + 2) * 3] = 1
    with pytest.raises(probe.ProbeFailure, match="differs"):
        probe.validate_rgb_cell(bytes(changed), (20, 20), baseline=baseline)
    off_white = bytearray(white)
    off_white[0] = 254
    with pytest.raises(probe.ProbeFailure, match="ink remains"):
        probe.validate_rgb_cell(
            bytes(off_white), (20, 20), baseline=baseline, hidden=True
        )


@pytest.mark.parametrize(
    ("data", "width", "height"),
    [(b"", 20, 20), (b"\xff" * 75, 5.0, 5), (b"\xff" * 48, 4, 4)],
)
def test_invalid_rgb_shape_is_not_visual_evidence(data, width, height) -> None:
    with pytest.raises(probe.ProbeFailure):
        probe.rgb_evidence(data, width, height)


def test_decoded_image_accounting_checks_peak_not_only_output_png_size() -> None:
    base = 3 * 5101 * 3301 * 4 + 1024 * 1024
    retained = probe.MAX_IMAGE_BYTES - base
    assert probe.image_working_bytes(3, 5101, 3301, retained) == probe.MAX_IMAGE_BYTES
    with pytest.raises(probe.ProbeFailure):
        probe.image_working_bytes(3, 5101, 3301, retained + 1)


@pytest.mark.parametrize(
    "arguments",
    [
        (0, 5100, 3300, 0),
        (4, 5100, 3300, 0),
        (3, 5102, 3300, 0),
        (3, 5100, 3302, 0),
        (3, 5100, 3300, -1),
        (True, 5100, 3300, 0),
    ],
)
def test_invalid_image_dimensions_or_buffer_counts_fail_closed(arguments) -> None:
    with pytest.raises(probe.ProbeFailure):
        probe.image_working_bytes(*arguments)


def test_receipt_atomically_deduplicates_values_but_keeps_every_observation(
    tmp_path,
) -> None:
    receipt = probe.Receipt(tmp_path)
    value = {"view": "A", "own": True}
    receipt.observe(probe.SnapshotKind.FULL, "before", value)
    receipt.observe(probe.SnapshotKind.FULL, "after", dict(value))
    receipt.checkpoint()
    data = json.loads((tmp_path / "report.json").read_text())
    assert len(data["snapshots"]) == 1
    assert [row["id"] for row in data["observations"]] == ["F001", "F002"]
    assert len(data["cases"]["C00"]["checkpoints"]) == 2
    assert data["handoff_allowed"] is False
    assert not (tmp_path / "report.json.tmp").exists()


@pytest.mark.parametrize(
    ("kind", "limit"), [(probe.SnapshotKind.FULL, 192), (probe.SnapshotKind.SOURCE, 16)]
)
def test_receipt_checkpoint_ceiling_is_not_silently_truncated(
    tmp_path, kind, limit
) -> None:
    receipt = probe.Receipt(tmp_path)
    for _ in range(limit):
        receipt.observe(kind, "bounded", {"value": 1})
    with pytest.raises(probe.ProbeFailure, match="ceiling"):
        receipt.observe(kind, "one-too-many", {"value": 2})
    assert len(receipt.data["observations"]) == limit


def test_invalid_checkpoint_kind_does_not_consume_a_slot(tmp_path) -> None:
    receipt = probe.Receipt(tmp_path)
    with pytest.raises(probe.ProbeFailure, match="invalid checkpoint kind"):
        receipt.observe("F", "not-an-enum", {})
    assert not receipt.counts


def test_receipt_preserves_primary_object_traceback_and_later_restoration_notes(
    tmp_path, capsys
) -> None:
    receipt = probe.Receipt(tmp_path)
    try:
        raise ValueError("first native boundary")
    except ValueError as primary:
        receipt.failure(primary)
        secondary = RuntimeError("restore failed")
        primary.add_note("restoration also failed")
        receipt.failure(secondary, secondary=True)
        receipt.failure(primary)
        assert receipt.primary is primary
        receipt.terminal()
    data = json.loads((tmp_path / "report.json").read_text())
    assert data["primary_error"]["type"] == "ValueError"
    assert "first native boundary" in data["primary_error"]["traceback"]
    assert data["primary_error"]["notes"] == ["restoration also failed"]
    assert len(data["secondary_errors"]) == 1
    terminal = json.loads(capsys.readouterr().out.split("BULK_VISIBILITY_TERMINAL ")[1])
    report = tmp_path / "report.json"
    assert terminal["sha256"] == hashlib.sha256(report.read_bytes()).hexdigest()
    assert terminal["size"] == report.stat().st_size
    assert data["artifacts"] == []


def test_receipt_refuses_duplicate_artifact_and_report_self_hash(tmp_path) -> None:
    receipt = probe.Receipt(tmp_path)
    path = tmp_path / "fixture.pdf"
    path.write_bytes(b"actual artifact bytes")
    receipt.artifact(path, "pdf")
    assert (
        receipt.data["artifacts"][0]["sha256"]
        == hashlib.sha256(path.read_bytes()).hexdigest()
    )
    with pytest.raises(probe.ProbeFailure, match="overwrite/self-hash"):
        receipt.artifact(path, "pdf")
    with pytest.raises(probe.ProbeFailure, match="overwrite/self-hash"):
        receipt.artifact(tmp_path / "report.json", "report")


@pytest.mark.parametrize("name", ["../outside.json", "child/file.json", "", ".", ".."])
def test_report_path_cannot_escape_flat_owned_directory(tmp_path, name) -> None:
    receipt = probe.Receipt(tmp_path)
    with pytest.raises(probe.ProbeFailure):
        receipt.path(name)


def test_atomic_report_peak_is_checked_before_overwriting_evidence(
    tmp_path, monkeypatch
) -> None:
    receipt = probe.Receipt(tmp_path)
    report = tmp_path / "report.json"
    before = report.read_bytes()
    monkeypatch.setattr(probe, "MAX_FILES_BYTES", len(before) + 1)
    with pytest.raises(probe.ProbeFailure, match="atomic report temporary"):
        receipt.checkpoint()
    assert report.read_bytes() == before
    assert not (tmp_path / "report.json.tmp").exists()


def test_oversized_report_is_refused_without_replacing_last_receipt(
    tmp_path, monkeypatch
) -> None:
    receipt = probe.Receipt(tmp_path)
    report = tmp_path / "report.json"
    before = report.read_bytes()
    monkeypatch.setattr(probe, "MAX_REPORT_BYTES", 64)
    with pytest.raises(probe.ProbeFailure, match="report exceeds"):
        receipt.checkpoint()
    assert report.read_bytes() == before


def test_walked_entry_limit_and_nested_directory_refusal_are_fail_closed(
    tmp_path,
) -> None:
    receipt = probe.Receipt(tmp_path)
    nested = tmp_path / "not-flat"
    nested.mkdir()
    with pytest.raises(probe.ProbeFailure, match="nonregular"):
        receipt.limits()
    nested.rmdir()
    for index in range(44):
        (tmp_path / f"artifact-{index}.json").write_bytes(b"x")
    with pytest.raises(probe.ProbeFailure, match="walked-entry ceiling"):
        receipt.limits()


@pytest.mark.parametrize(
    ("stage", "former_local_limit"),
    [
        (probe.Stage.CONSTRUCTION, 100.0),
        (probe.Stage.FUNDAMENTAL, 50.0),
        (probe.Stage.VISUAL, 130.0),
        (probe.Stage.EXTENDED, 130.0),
    ],
)
def test_normal_stage_can_spend_unused_shared_time(
    tmp_path, stage, former_local_limit
) -> None:
    origin = 2048.0
    clock = [origin]
    subject = OfflineProbe(tmp_path, clock=lambda: clock[0])
    clock[0] = origin + 7.0
    subject.stage(stage)
    row = subject.receipt.data["stages"][stage]
    assert row["started_seconds"] == 7.0
    assert subject.receipt.stage_started == origin + 7.0
    clock[0] += former_local_limit + 1.0
    subject.tick()
    subject.stage_passed()
    assert row["status"] is probe.Verdict.PASSED
    assert row["seconds"] == former_local_limit + 1.0
    assert subject.receipt.primary is None


def test_stage_transitions_keep_total_normal_time_and_allow_exact_completion(
    tmp_path,
) -> None:
    origin = 2048.0
    clock = [origin]
    subject = OfflineProbe(tmp_path, clock=lambda: clock[0])
    clock[0] = origin + 3.0
    with subject.stage_scope(probe.Stage.CONSTRUCTION):
        clock[0] = origin + 200.0
        subject.run_case(probe.Case.CONSTRUCTION, subject.tick)
    with subject.stage_scope(probe.Stage.FUNDAMENTAL):
        clock[0] = origin + 300.0
        subject.tick()
    with subject.stage_scope(probe.Stage.VISUAL):
        clock[0] = origin + 410.0
        subject.tick()
        clock[0] = origin + 480.0
        subject.tick()
        clock[0] = origin + 481.0
        subject.tick()
        clock[0] = origin + 900.0
        subject.run_case(probe.Case.PERSISTENCE, subject.tick)
    for stage, started, seconds in (
        (probe.Stage.CONSTRUCTION, 3.0, 197.0),
        (probe.Stage.FUNDAMENTAL, 200.0, 100.0),
        (probe.Stage.VISUAL, 300.0, 600.0),
    ):
        row = subject.receipt.data["stages"][stage]
        assert row["status"] is probe.Verdict.PASSED
        assert row["started_seconds"] == started
        assert row["seconds"] == seconds
    assert (
        subject.receipt.data["cases"][probe.Case.PERSISTENCE]["status"]
        is probe.Verdict.PASSED
    )
    with pytest.raises(probe.ProbeFailure) as caught:
        with subject.stage_scope(probe.Stage.EXTENDED):
            subject.tick()
            clock[0] = math.nextafter(clock[0], math.inf)
            subject.tick()
    error = caught.value
    elapsed = clock[0] - origin
    stage_elapsed = clock[0] - (origin + 900.0)
    assert error.verdict is probe.Verdict.DEADLINE
    assert f"{probe.Stage.EXTENDED}/{probe.Case.PERSISTENCE}" in str(error)
    assert "binding=normal_global;" in str(error)
    assert f"global_elapsed={elapsed!r}s" in str(error)
    assert "global_limit=900.0s" in str(error)
    assert f"stage_elapsed={stage_elapsed!r}s" in str(error)
    assert "cleanup_stage_limit" not in str(error)
    failed = subject.receipt.data["stages"][probe.Stage.EXTENDED]
    assert failed["status"] is probe.Verdict.DEADLINE
    assert failed["started_seconds"] == 900.0
    assert failed["seconds"] == stage_elapsed
    assert failed["reason"] == str(error)
    assert subject.receipt.started == origin


@pytest.mark.parametrize(
    ("started", "boundary", "binding"),
    [
        (300.0, 370.0, "cleanup_stage"),
        (920.0, 970.0, "cleanup_global"),
        (900.0, 970.0, "cleanup_global,cleanup_stage"),
    ],
)
@pytest.mark.parametrize("overrun", [False, True])
def test_cleanup_enforces_global_and_local_time_independently(
    tmp_path, started, boundary, binding, overrun
) -> None:
    origin = 2048.0
    clock = [origin]
    samples = []

    def now():
        samples.append(clock[0])
        return clock[0]

    subject = OfflineProbe(tmp_path, clock=now)
    subject.mode = probe.RunMode.CLEANUP
    clock[0] = origin + started

    def finish_cleanup():
        clock[0] = origin + boundary
        if overrun:
            clock[0] = math.nextafter(clock[0], math.inf)
        before = len(samples)
        try:
            subject.receipt.deadline(cleanup=True)
        finally:
            assert len(samples) == before + 1
        subject.cleanup()

    expected = pytest.raises(probe.ProbeFailure) if overrun else nullcontext()
    with expected as caught:
        with subject.stage_scope(probe.Stage.CLEANUP):
            subject.run_case(probe.Case.CLEANUP, finish_cleanup)
    elapsed = clock[0] - origin
    stage_elapsed = clock[0] - (origin + started)
    row = subject.receipt.data["stages"][probe.Stage.CLEANUP]
    assert row["started_seconds"] == started
    assert row["seconds"] == stage_elapsed
    if overrun:
        error = caught.value
        assert error.verdict is probe.Verdict.DEADLINE
        assert f"{probe.Stage.CLEANUP}/{probe.Case.CLEANUP}" in str(error)
        assert f"binding={binding};" in str(error)
        assert f"global_elapsed={elapsed!r}s" in str(error)
        assert "global_limit=970.0s" in str(error)
        assert f"stage_elapsed={stage_elapsed!r}s" in str(error)
        assert "cleanup_stage_limit=70.0s" in str(error)
        assert row["status"] is probe.Verdict.DEADLINE
        assert row["reason"] == str(error)
        assert subject.receipt.primary is error
        assert (
            subject.receipt.data["cases"][probe.Case.CLEANUP]["status"]
            is probe.Verdict.DEADLINE
        )
    else:
        assert row["status"] is probe.Verdict.PASSED
        assert subject.receipt.data["cleanup"]["status"] is probe.Verdict.PASSED
        assert subject.receipt.counts[probe.SnapshotKind.SOURCE] == 1
        assert subject.receipt.primary is None
        assert not subject.app.models and not subject.acquisitions


@pytest.mark.parametrize("restore_error", [False, True])
@pytest.mark.parametrize("restored_elapsed", [900.125, 970.125])
def test_deadline_keeps_mandatory_restoration_and_owned_cleanup_semantics(
    tmp_path, monkeypatch, restore_error, restored_elapsed
) -> None:
    origin = 2048.0
    clock = [origin]
    fixture = sheet_inventory.__wrapped__(tmp_path, monkeypatch, clock=lambda: clock[0])
    fixture = sheet_scale_construction.__wrapped__(fixture, monkeypatch)
    fixture = sheet_mode_contract.__wrapped__(fixture, monkeypatch)
    subject = fixture.subject
    subject.create_drawing()
    original = prepare_sheet_mode_export(fixture)
    secondary = OSError("inert late selection restoration")
    if restore_error:
        fixture.controls.resume_error = secondary
    manager = fixture.drawing.SelectionManager
    resume = manager.ResumeSelectionList2

    def late_resume(append):
        clock[0] = origin + restored_elapsed
        return resume(append)

    monkeypatch.setattr(manager, "ResumeSelectionList2", late_resume)
    fixture.mode_events.clear()

    def expire_inside_guard():
        with subject.selection_guard():
            clock[0] = origin + 900.125
            subject.tick()

    primary = capture_and_cleanup_failure(subject, expire_inside_guard)
    assert primary.verdict is probe.Verdict.DEADLINE
    assert "binding=normal_global;" in str(primary)
    assert f"{probe.Stage.CONSTRUCTION}/{probe.Case.CONSTRUCTION}" in str(primary)
    assert fixture.drawing.current is original["sheet"]
    assert fixture.drawing.ActiveDrawingView is None
    assert not manager.suspended
    assert manager.selected[0][2] == 16
    assert ("ResumeSelectionList2",) in fixture.mode_events
    restoration = subject.receipt.data["cases"][probe.Case.CONSTRUCTION]["operations"]
    (restoration,) = [row for row in restoration if row["bucket"] == "restore"]
    assert restoration["status"] is (
        probe.Verdict.RESTORATION if restore_error else probe.Verdict.PASSED
    )
    assert any(
        row["label"] == "selection-guard-restored"
        for row in subject.receipt.data["observations"]
    )
    secondary_errors = subject.receipt.data["secondary_errors"]
    assert any(row["message"] == str(secondary) for row in secondary_errors) is (
        restore_error
    )
    cleanup = subject.receipt.data["cleanup"]
    if restored_elapsed > 970.0:
        assert cleanup["status"] is probe.Verdict.RESTORATION
        assert set(cleanup["remaining_owned"]) == {
            probe.Document.DRAWING,
            probe.Document.R,
        }
        assert not subject.app.close_calls
        assert any(
            "binding=cleanup_global;" in row["message"] for row in secondary_errors
        )
    else:
        assert cleanup["status"] is probe.Verdict.PASSED
        assert not subject.acquisitions and not subject.app.models
        assert subject.app.closed == [fixture.drawing, fixture.source]
        assert subject.receipt.counts[probe.SnapshotKind.SOURCE] == 1
    assert subject.receipt.primary is primary
    assert subject.mode is probe.RunMode.CLEANUP
    assert subject.receipt.data["handoff_allowed"] is False


def test_failure_classification_does_not_rename_native_error_objects() -> None:
    original = OSError("native error")
    original.probe_verdict = probe.Verdict.SELECTION
    assert probe.failure_verdict(original) is probe.Verdict.SELECTION
    assert probe.failure_verdict(KeyboardInterrupt()) is probe.Verdict.INTERRUPTED
    assert (
        probe.failure_verdict(
            probe.InjectedFailure(
                probe.Case.EXCEPTION_ENABLED, probe.Injection.AFTER_SELECTION
            )
        )
        is probe.Verdict.INTERRUPTED
    )
    assert (
        probe.failure_verdict(
            probe.ProbeFailure(probe.Verdict.PLURAL, "both not consumed")
        )
        is probe.Verdict.PLURAL
    )


class OfflineConfiguration:
    Name = "Default"

    def GetDisplayStates(self):
        return ("Display State-1",)

    def GetDisplayStatesCount(self):
        return 1


class OfflineModel:
    """Explicit native boundary fake, never a native correctness oracle."""

    def __init__(self, title, kind, path, *, readonly=True):
        self.title, self.kind, self.path = title, kind, str(path)
        self.readonly = readonly
        self.title_error = None
        self.open_error = None
        self.unsupported_identity = False
        self.hidden = False
        self.live = True
        self.disconnected_accesses = []

    def assert_live(self, operation):
        if not self.live:
            self.disconnected_accesses.append(operation)
            raise RuntimeError(f"disconnected document handle: {operation}")

    def GetTitle(self):
        self.assert_live("GetTitle")
        if self.title_error is not None:
            error, self.title_error = self.title_error, None
            raise error
        return self.title

    def GetType(self):
        self.assert_live("GetType")
        return self.kind

    def GetPathName(self):
        self.assert_live("GetPathName")
        return self.path

    def IsOpenedReadOnly(self):
        self.assert_live("IsOpenedReadOnly")
        return self.readonly

    def GetSaveFlag(self):
        self.assert_live("GetSaveFlag")
        return False

    def GetConfigurationNames(self):
        self.assert_live("GetConfigurationNames")
        return ("Default",)

    def GetActiveConfiguration(self):
        self.assert_live("GetActiveConfiguration")
        return OfflineConfiguration()

    def GetConfigurationByName(self, name):
        self.assert_live("GetConfigurationByName")
        assert name == "Default"
        return OfflineConfiguration()


class OfflineSheet:
    def __init__(self, drawing):
        self.drawing = drawing

    def SetName(self, name):
        self.drawing.assert_live("SetName")
        self.drawing.sheet = name
        self.drawing.title = f"Draw - {name}"

    def GetName(self):
        return self.drawing.sheet


class OfflineDrawing(OfflineModel):
    """Sheet-qualified titles are simulated, not an observed native outcome."""

    def __init__(self, path=""):
        super().__init__("Draw - Sheet1", 3, path, readonly=False)
        self.sheet = "Sheet1"
        self.edit_sheet_mode = False

    def GetEditSheet(self):
        self.assert_live("GetEditSheet")
        return self.edit_sheet_mode

    def EditSheet(self):
        self.assert_live("EditSheet")
        self.edit_sheet_mode = True

    def GetSheetNames(self):
        self.assert_live("GetSheetNames")
        return (self.sheet,)

    def GetViews(self):
        self.assert_live("GetViews")
        return ((object(),),)

    def GetCurrentSheet(self):
        self.assert_live("GetCurrentSheet")
        return OfflineSheet(self)

    def ActivateSheet(self, name):
        self.assert_live("ActivateSheet")
        self.sheet = name
        self.title = f"Draw - {name}"
        return True


class OfflineModelHandle:
    """Wrapper generation tracks refresh; only its document controls liveness."""

    def __init__(self, document, generation):
        self.document, self.generation = document, generation

    def __getattr__(self, name):
        self.document.assert_live(name)
        return getattr(self.document, name)


class OfflineApplication:
    """Only in-memory document inventory/return values; no host collaborators."""

    def __init__(self, root):
        self.models = []
        self.open_results = []
        self.new_results = []
        self.closed = []
        self.close_calls = []
        self.close_error = None
        self.inventory_generation = 0
        self.identity_calls = []
        self.lookup_calls = []
        self.preference_calls = []
        self.new_calls = []
        self.activation_calls = []
        self.preference_error = None
        self.ActiveDoc = None
        self.template = root / "assembly.asmdot"
        self.template.write_bytes(b"offline template admission fixture")
        self.preference_result = str(self.template)

    @staticmethod
    def document(handle):
        return handle.document if isinstance(handle, OfflineModelHandle) else handle

    def fresh_handle(self, document):
        return (
            OfflineModelHandle(document, self.inventory_generation)
            if self.inventory_generation
            else document
        )

    @property
    def ActiveDoc(self):
        return self.fresh_handle(self._active) if self._active is not None else None

    @ActiveDoc.setter
    def ActiveDoc(self, handle):
        self._active = self.document(handle)

    def IsSame(self, left, right):
        self.identity_calls.append((left, right))
        left, right = self.document(left), self.document(right)
        left.assert_live("IsSame")
        right.assert_live("IsSame")
        if left.unsupported_identity or right.unsupported_identity:
            return 2
        return int(left is right)

    def GetDocuments(self):
        return tuple(self.fresh_handle(model) for model in self.models)

    def GetOpenDocumentByName(self, path):
        self.lookup_calls.append(path)
        found = next(
            (
                model
                for model in self.models
                if probe.normalized(model.GetPathName()) == probe.normalized(path)
            ),
            None,
        )
        return self.fresh_handle(found) if found is not None else None

    def OpenDoc6(self, path, kind, options, configuration, errors, warnings):
        assert options in (1, 3, 67)
        assert configuration in ("", "Default")
        model, errors, warnings = self.open_results.pop(0)
        if model not in self.models:
            self.models.append(model)
        self.ActiveDoc = model
        if model.open_error is not None:
            raise model.open_error
        return model, errors, warnings

    def GetUserPreferenceStringValue(self, preference):
        self.preference_calls.append(preference)
        assert preference == 9
        if self.preference_error is not None:
            raise self.preference_error
        return self.preference_result

    def NewDocument(self, template, paper, width, height):
        self.new_calls.append((template, paper, width, height))
        assert Path(template).is_file()
        model = self.new_results.pop(0)
        self.models.append(model)
        self.ActiveDoc = model
        return model

    def ActivateDoc3(self, title, preferences, option, errors):
        self.activation_calls.append((title, preferences, option, errors))
        assert preferences is False and type(option) is int and option == 2
        assert type(errors) is int and errors == 0
        matches = [model for model in self.models if model.title == title]
        if len(matches) != 1:
            return None, 0
        self.ActiveDoc = matches[0]
        return self.fresh_handle(matches[0]), 0

    def CloseDoc(self, title):
        matches = [
            model for model in self.models if model.title.casefold() == title.casefold()
        ]
        assert len(matches) == 1, (
            "production must refuse an ambiguous title before CloseDoc"
        )
        model = matches[0]
        self.close_calls.append(title)
        self.closed.append(model)
        if self.close_error is not None:
            raise self.close_error
        # Official CloseDoc collateral behavior is a contract premise, not a
        # native observation. Deliberately model it so unsafe named closes fail.
        collateral = [
            candidate
            for candidate in self.models
            if candidate is not model
            and candidate is not self._active
            and candidate.hidden
        ]
        self.models.remove(model)
        model.live = False
        for candidate in collateral:
            self.closed.append(candidate)
            self.models.remove(candidate)
            candidate.live = False
        self.ActiveDoc = self.models[-1] if self.models else None
        # Refreshing wrappers must not disconnect handles of surviving models.
        self.inventory_generation += 1

    def RevisionNumber(self):
        return "offline-boundary-not-a-native-version"


class OfflineProbe(probe.NativeProbe):
    """Run production orchestration with explicit offline COM/telemetry ports."""

    def __init__(self, root, *, clock=None):
        # Deliberately do not invoke NativeProbe.__init__ or import its SDK.
        reports = root / "reports"
        reports.mkdir()
        self.root = root
        self.receipt = (
            probe.Receipt(reports)
            if clock is None
            else probe.Receipt(reports, clock=clock)
        )
        self.adapter = SimpleNamespace(currentModel=None)
        self.app = OfflineApplication(root)
        self.telemetry = SimpleNamespace(span=lambda *args, **kwargs: nullcontext())
        self.documents, self.acquisitions = {}, {}
        self.generations = Counter()
        self.paths = {
            label: root / f"{label}.sldprt"
            for label in (
                probe.Document.P,
                probe.Document.Q,
                probe.Document.N,
                probe.Document.R,
                probe.Document.DRAWING,
            )
        }
        self.source_baselines, self.disk_baselines = {}, {}
        self.saved_drawing_hash = None
        self.view_handles, self.node_handles = {}, {}
        self.mode = probe.RunMode.EXPERIMENT
        self.construction_action = lambda: None

    def bind(self, raw, interface):
        probe.require(
            raw is not None, probe.Verdict.IDENTITY, f"offline null {interface}"
        )
        return raw

    def construct(self):
        self.construction_action()

    def case_checkpoint(self, label):
        # Native snapshots are not simulated successes. These tests target the
        # orchestration/receipt path, not native view/source/selection behavior.
        self.receipt.observe(
            probe.SnapshotKind.FULL, label, {"offline_boundary_only": True}
        )


@pytest.fixture
def sheet_inventory(tmp_path, monkeypatch, *, clock=None):
    """Complete views() inventory through explicit inert native boundary ports."""
    subject = OfflineProbe(tmp_path, clock=clock)
    source = OfflineModel("R", 2, tmp_path / "R.sldasm")
    sheets = {
        key: SimpleNamespace(GetName=lambda key=key: str(key)) for key in probe.ViewId
    }
    sheet_calls, pseudo_sheet_reads, context_calls = [], [], []
    controls = SimpleNamespace(pseudo_sheet_error=None, lookup_error=None)

    class SheetPseudoView:
        def __init__(self, name):
            self.Name = str(name)

        @property
        def Sheet(self):
            pseudo_sheet_reads.append(self.Name)
            if controls.pseudo_sheet_error is not None:
                raise controls.pseudo_sheet_error
            return None

    views, components, groups = {}, {}, {}
    states = fixture_nodes()
    subject.component_names = {
        state.component_path: key for key, state in states.items()
    }
    subject.view_baselines = {}
    for view_id in probe.ViewId:
        view = OfflineModel(f"view-{view_id}", 0, "")
        view.Name = f"view-{view_id}"
        view.Sheet = sheets[view_id]
        view.ReferencedDocument = source
        view.ReferencedConfiguration = "Default"
        view.GetOrientationName = lambda: "*Front"
        view.ScaleRatio = (5.0, 1.0)
        view.UseSheetScale = 0
        view.Position = (0.1, 0.2, 0.0)
        view.ModelToViewTransform = SimpleNamespace(ArrayData=probe.translation(0.0))
        nodes = {}
        for key, state in states.items():
            node = OfflineModel(f"dc-{view_id}-{key}", 0, "")
            node.IsRoot = lambda: False
            node.View = view
            node.Visible = state.own
            node.Component = SimpleNamespace(
                state={
                    "path": state.component_path,
                    "source": state.source_path,
                    "configuration": state.configuration,
                    "transform": state.transform,
                }
            )
            nodes[key] = node
        for key, node in nodes.items():
            node.GetChildren = lambda key=key, nodes=nodes: tuple(
                nodes[child] for child in probe.NodeId if probe.PARENTS[child] is key
            )
        root = SimpleNamespace(
            IsRoot=lambda: True,
            GetChildren=lambda nodes=nodes: tuple(
                nodes[key] for key in probe.NodeId if probe.PARENTS[key] is None
            ),
        )
        view.RootDrawingComponent2 = lambda _resolve, root=root: root
        views[view_id], components[view_id] = view, nodes
        groups[view_id] = [SheetPseudoView(view_id), view]

    drawing = OfflineDrawing()
    drawing.groups = [groups[probe.ViewId.B], groups[probe.ViewId.A]]
    drawing.current = probe.ViewId.A
    drawing.ActiveDrawingView = None
    drawing.GetViews = lambda: tuple(tuple(group) for group in drawing.groups)

    def named_sheet(name):
        sheet_calls.append(name)
        if controls.lookup_error is not None:
            raise controls.lookup_error
        return sheets[name]

    def current_sheet():
        context_calls.append(("GetCurrentSheet",))
        return sheets[drawing.current]

    def activate_sheet(name):
        context_calls.append(("ActivateSheet", name))
        drawing.current = name
        drawing.ActiveDrawingView = None
        return True

    def activate_view(name):
        context_calls.append(("ActivateView", name))
        drawing.ActiveDrawingView = next(
            view for view in views.values() if view.Name == name
        )
        return True

    drawing.Sheet = named_sheet
    drawing.GetCurrentSheet = current_sheet
    drawing.ActivateSheet = activate_sheet
    drawing.ActivateView = activate_view
    monkeypatch.setattr(subject, "draw", lambda: drawing)
    monkeypatch.setattr(subject, "model", lambda label: source)
    monkeypatch.setattr(subject, "component_state", lambda component: component.state)
    monkeypatch.setattr(
        subject,
        "activate",
        lambda label: context_calls.append(("activate", label)) or drawing,
    )
    return SimpleNamespace(
        subject=subject,
        source=source,
        drawing=drawing,
        sheets=sheets,
        groups=groups,
        views=views,
        components=components,
        controls=controls,
        sheet_calls=sheet_calls,
        pseudo_sheet_reads=pseudo_sheet_reads,
        context_calls=context_calls,
    )


def test_sheet_inventory_resolves_distinct_named_groups(sheet_inventory):
    fixture = sheet_inventory
    result = fixture.subject.views()
    assert set(result) == set(probe.ViewId)
    for key, (view, nodes) in result.items():
        assert view is fixture.views[key]
        assert set(nodes) == set(probe.NodeId)
        assert all(
            node.drawing_component is fixture.components[key][name]
            for name, node in nodes.items()
        )
    assert fixture.sheet_calls == [group[0].Name for group in fixture.drawing.groups]
    assert fixture.pseudo_sheet_reads == []
    assert fixture.context_calls == []
    assert fixture.drawing.current is probe.ViewId.A


def test_sheet_inventory_order_is_not_active_sheet_order(sheet_inventory):
    fixture = sheet_inventory
    fixture.drawing.groups.reverse()
    fixture.controls.pseudo_sheet_error = AssertionError("pseudo Sheet is not an owner")
    result = fixture.subject.views()
    assert {key: view for key, (view, _nodes) in result.items()} == fixture.views
    assert fixture.sheet_calls == [str(probe.ViewId.A), str(probe.ViewId.B)]
    assert fixture.context_calls == []
    assert fixture.drawing.current is probe.ViewId.A
    # A fresh full read must retain real view and drawing-component generations.
    assert set(fixture.subject.views()) == set(probe.ViewId)
    assert fixture.pseudo_sheet_reads == []


@pytest.mark.parametrize("name", [None, "", 17, "UnexpectedSheet"])
def test_sheet_inventory_rejects_invalid_pseudo_name(sheet_inventory, name):
    fixture = sheet_inventory
    fixture.drawing.groups[0][0].Name = name
    with pytest.raises(probe.ProbeFailure):
        fixture.subject.views()
    assert fixture.sheet_calls == []
    assert fixture.context_calls == []


@pytest.mark.parametrize("fault", ["null", "wrong_name", "invalid_name"])
def test_sheet_inventory_named_lookup_fails_closed(sheet_inventory, fault):
    fixture = sheet_inventory
    fixture.sheets[probe.ViewId.B] = {
        "null": None,
        "wrong_name": SimpleNamespace(GetName=lambda: str(probe.ViewId.A)),
        "invalid_name": SimpleNamespace(GetName=lambda: None),
    }[fault]
    with pytest.raises(probe.ProbeFailure):
        fixture.subject.views()
    assert fixture.sheet_calls == [str(probe.ViewId.B)]
    assert fixture.context_calls == []
    assert fixture.pseudo_sheet_reads == []


def test_sheet_inventory_preserves_named_lookup_exception(sheet_inventory):
    fixture = sheet_inventory
    original = OSError("named sheet lookup failed")
    fixture.controls.lookup_error = original
    with pytest.raises(OSError) as caught:
        fixture.subject.views()
    assert caught.value is original
    assert fixture.sheet_calls == [str(probe.ViewId.B)]
    assert fixture.context_calls == []


@pytest.mark.parametrize("fault", ["null", "wrong_name"])
@pytest.mark.parametrize("reverse", [False, True])
def test_sheet_inventory_retains_real_view_owner_check(sheet_inventory, fault, reverse):
    fixture = sheet_inventory
    if reverse:
        fixture.drawing.groups.reverse()
    first, last = (probe.ViewId(group[0].Name) for group in fixture.drawing.groups)
    fixture.views[last].Sheet = None if fault == "null" else fixture.sheets[first]
    with pytest.raises(probe.ProbeFailure):
        fixture.subject.views()
    # The first group passed, but failure in the second is not skipped.
    assert fixture.sheet_calls == [str(first), str(last)]
    assert fixture.context_calls == []


@pytest.mark.parametrize(
    "fault",
    [
        "missing_group",
        "extra_group",
        "empty_group",
        "sheet_only",
        "extra_real_view",
        "null_pseudo",
        "duplicate_name",
    ],
)
def test_sheet_inventory_rejects_incomplete_or_ambiguous_groups(sheet_inventory, fault):
    fixture = sheet_inventory
    groups = fixture.drawing.groups
    if fault == "missing_group":
        groups.pop()
    elif fault == "extra_group":
        groups.append(groups[0])
    elif fault == "empty_group":
        groups[1] = []
    elif fault == "sheet_only":
        groups[1] = groups[1][:1]
    elif fault == "extra_real_view":
        groups[1].append(groups[1][1])
    elif fault == "null_pseudo":
        groups[1][0] = None
    else:
        groups[1][0].Name = str(probe.ViewId.B)
    with pytest.raises(probe.ProbeFailure):
        fixture.subject.views()
    assert fixture.context_calls == []


@pytest.mark.parametrize(
    "fault",
    [
        "source",
        "orientation",
        "configuration",
        "scale",
        "component_path",
        "component_owner",
        "duplicate_component",
        "missing_component",
    ],
)
def test_sheet_inventory_keeps_downstream_contracts(sheet_inventory, fault):
    fixture = sheet_inventory
    view = fixture.views[probe.ViewId.A]
    if fault == "source":
        view.ReferencedDocument = OfflineModel("foreign R", 2, "foreign.sldasm")
    elif fault == "orientation":
        view.GetOrientationName = lambda: "*Back"
    elif fault == "configuration":
        view.ReferencedConfiguration = "Other"
    elif fault == "scale":
        view.ScaleRatio = (1.0, 1.0)
    else:
        node = fixture.components[probe.ViewId.A][probe.NodeId.Q2]
        if fault == "component_path":
            node.Component.state["path"] = "foreign"
        elif fault == "duplicate_component":
            nodes = fixture.components[probe.ViewId.A]
            nodes[probe.NodeId.P2].Component.state["path"] = nodes[
                probe.NodeId.P1
            ].Component.state["path"]
        elif fault == "missing_component":
            root = view.RootDrawingComponent2(False)
            children = root.GetChildren()
            root.GetChildren = lambda: tuple(
                child for child in children if child is not node
            )
        else:
            node.View = fixture.views[probe.ViewId.B]
    expected = (
        "unmapped/duplicate full drawing component path"
        if fault == "duplicate_component"
        else None
    )
    with pytest.raises(probe.ProbeFailure, match=expected):
        fixture.subject.views()
    assert fixture.sheet_calls == [str(probe.ViewId.B), str(probe.ViewId.A)]
    assert fixture.context_calls == []


@pytest.mark.parametrize(
    "fault", ["view_generation", "component_generation", "transform", "position"]
)
def test_sheet_inventory_retains_generation_and_layout_baselines(
    sheet_inventory, fault
):
    from copy import copy

    fixture = sheet_inventory
    fixture.subject.views()
    fixture.sheet_calls.clear()
    view = fixture.views[probe.ViewId.A]
    if fault == "view_generation":
        fixture.groups[probe.ViewId.A][1] = copy(view)
    elif fault == "component_generation":
        nodes = fixture.components[probe.ViewId.A]
        nodes[probe.NodeId.Q2] = copy(nodes[probe.NodeId.Q2])
    elif fault == "transform":
        view.ModelToViewTransform.ArrayData = probe.translation(0.01)
    else:
        view.Position = (0.11, 0.2, 0.0)
    with pytest.raises(probe.ProbeFailure):
        fixture.subject.views()
    assert fixture.sheet_calls == [str(probe.ViewId.B), str(probe.ViewId.A)]
    assert fixture.context_calls == []


def test_activate_view_consumes_full_named_sheet_inventory(sheet_inventory):
    fixture = sheet_inventory
    fixture.subject.activate_view(probe.ViewId.A)
    assert fixture.sheet_calls == [str(probe.ViewId.B), str(probe.ViewId.A)]
    assert fixture.context_calls == [
        ("activate", probe.Document.DRAWING),
        ("ActivateSheet", probe.ViewId.A),
        ("ActivateView", fixture.views[probe.ViewId.A].Name),
        ("GetCurrentSheet",),
    ]
    assert fixture.drawing.ActiveDrawingView is fixture.views[probe.ViewId.A]
    assert fixture.pseudo_sheet_reads == []


@pytest.mark.parametrize("reverse", [False, True])
def test_activate_view_refuses_late_group_failure_before_view_activation(
    sheet_inventory, reverse
):
    fixture = sheet_inventory
    if reverse:
        fixture.drawing.groups.reverse()
    names = [group[0].Name for group in fixture.drawing.groups]
    fixture.views[probe.ViewId(names[-1])].Sheet = None
    with pytest.raises(probe.ProbeFailure):
        fixture.subject.activate_view(probe.ViewId.A)
    assert fixture.sheet_calls == names
    assert fixture.context_calls == [
        ("activate", probe.Document.DRAWING),
        ("ActivateSheet", probe.ViewId.A),
    ]
    assert fixture.drawing.ActiveDrawingView is None


class InertWriteOnlyError(Exception):
    """Retained server-shaped failure without importing pywin32 or the SDK."""

    def __init__(self):
        super().__init__("Unable to read write-only property.")
        self.hresult = -2147352567
        self.excepinfo = (
            61836,
            "SOLIDWORKS Design",
            "Unable to read write-only property.",
            r"C:\Program Files\Dassault Systemes\SOLIDWORKS 3DEXPERIENCE R2026x\SOLIDWORKS\lang\english\sldworks.chm",
            455052,
            0,
        )
        self.argerror = None


class OfflineReadinessDrawing(OfflineDrawing):
    @property
    def IActiveView(self):
        raise InertWriteOnlyError()


@pytest.fixture
def sheet_scale_construction(sheet_inventory, monkeypatch):
    """Run actual create_drawing/readback/views with inert native object ports."""
    fixture = sheet_inventory
    subject, drawing = fixture.subject, fixture.drawing
    drawing.__class__ = OfflineReadinessDrawing
    fixture.controls.scale_result = False
    fixture.scale_writes = []
    fixture.created_views = []
    fixture.markers = []
    template = subject.root / "cad/templates/harmonic-analyzer-landscape.DRWDOT"
    template.parent.mkdir(parents=True)
    template.write_bytes(b"offline drawing template")

    class ScaleReadbackView(OfflineModel):
        @property
        def UseSheetScale(self):
            return fixture.controls.scale_result

        @UseSheetScale.setter
        def UseSheetScale(self, value):
            fixture.scale_writes.append(value)

    for view in fixture.views.values():
        view.__class__ = ScaleReadbackView
        view.DisableAutoUpdate = False
    for sheet in fixture.sheets.values():
        sheet.SetName = lambda name: setattr(drawing, "title", f"Draw - {name}")
        sheet.GetProperties = lambda: (12, 13, 5, 1, False, 0.4318, 0.2794)
    all_views = drawing.GetViews
    drawing.GetViews = lambda: (
        all_views() if len(fixture.created_views) == 2 else ((object(),),)
    )
    drawing.NewSheet4 = lambda *arguments: True

    def create_view(path, orientation, x, y, z):
        view = fixture.views[drawing.current]
        fixture.created_views.append(view)
        return view

    def insert_note(text):
        fixture.markers.append(text)
        position = []

        def set_position(x, y, z):
            position[:] = (x, y, z)
            return True

        annotation = SimpleNamespace(
            SetPosition=set_position, GetPosition=lambda: tuple(position)
        )
        return SimpleNamespace(GetAnnotation=lambda: annotation, GetText=lambda: text)

    drawing.CreateDrawViewFromModelView3 = create_view
    drawing.ClearSelection2 = lambda _all: None
    drawing.InsertNote = insert_note
    drawing.AutomaticViewUpdate = True
    drawing.ActiveView = SimpleNamespace(EnableGraphicsUpdate=True)
    drawing.FeatureManager = SimpleNamespace(
        EnableFeatureTree=True, EnableFeatureTreeWindow=True
    )
    subject.app.new_results.append(drawing)
    monkeypatch.setattr(
        subject,
        "model",
        lambda label: drawing if label is probe.Document.DRAWING else fixture.source,
    )
    monkeypatch.setattr(subject, "doubles", lambda values: tuple(values))
    monkeypatch.setattr(subject, "rebuild", lambda: None)
    return fixture


@pytest.mark.parametrize("value_a", [False, 0])
@pytest.mark.parametrize("value_b", [False, 0])
def test_sheet_scale_representation_passes_full_inventory_and_caller(
    sheet_inventory, value_a, value_b
):
    fixture = sheet_inventory
    fixture.views[probe.ViewId.A].UseSheetScale = value_a
    fixture.views[probe.ViewId.B].UseSheetScale = value_b
    fixture.subject.views()
    assert all(
        type(state["use_sheet_scale"]) is int and state["use_sheet_scale"] == 0
        for state in fixture.subject.view_baselines.values()
    )
    canonical = json.dumps(fixture.subject.view_baselines, sort_keys=True)
    for view in fixture.views.values():
        view.UseSheetScale = 0 if type(view.UseSheetScale) is bool else False
    fixture.subject.views()
    assert json.dumps(fixture.subject.view_baselines, sort_keys=True) == canonical
    fixture.subject.activate_view(probe.ViewId.A)
    assert fixture.drawing.ActiveDrawingView is fixture.views[probe.ViewId.A]


@pytest.mark.parametrize("value", [True, 1])
@pytest.mark.parametrize("view_id", tuple(probe.ViewId))
@pytest.mark.parametrize("reverse", [False, True])
def test_sheet_scale_enabled_still_fails_independent_view_contract(
    sheet_inventory, value, view_id, reverse
):
    fixture = sheet_inventory
    if reverse:
        fixture.drawing.groups.reverse()
    fixture.views[view_id].UseSheetScale = value
    with pytest.raises(probe.ProbeFailure, match="view projection/scale/configuration"):
        fixture.subject.views()


class SheetScaleInt(int):
    pass


@pytest.mark.parametrize("value", [0.0, "0", None, -1, 2, SheetScaleInt(0)])
@pytest.mark.parametrize("view_id", tuple(probe.ViewId))
def test_sheet_scale_malformed_inventory_value_fails_closed(
    sheet_inventory, value, view_id
):
    fixture = sheet_inventory
    fixture.views[view_id].UseSheetScale = value
    with pytest.raises(probe.ProbeFailure, match="UseSheetScale: expected") as caught:
        fixture.subject.views()
    assert caught.value.verdict is probe.Verdict.PRESERVATION


@pytest.mark.parametrize("value", [False, 0])
def test_sheet_scale_constructor_readback_reaches_complete_fixture(
    sheet_scale_construction, value
):
    fixture = sheet_scale_construction
    fixture.controls.scale_result = value
    fixture.subject.create_drawing()
    assert fixture.scale_writes == [0, 0]
    assert all(type(value) is int for value in fixture.scale_writes)
    assert len(fixture.created_views) == 2
    assert set(fixture.subject.view_baselines) == set(probe.ViewId)
    assert all(
        type(state["use_sheet_scale"]) is int and state["use_sheet_scale"] == 0
        for state in fixture.subject.view_baselines.values()
    )
    assert "fixture" in fixture.subject.receipt.data
    assert "initial_flags" not in fixture.subject.receipt.data["fixture"]
    assert not hasattr(fixture.subject, "harness_flags")


@pytest.fixture
def sheet_mode_contract(sheet_scale_construction, monkeypatch):
    """Actual admission/construction/export/guard with explicit inert native ports."""
    fixture = sheet_scale_construction
    subject = fixture.subject
    fixture.mode_events = []
    fixture.mode_results = []
    fixture.edit_calls = []
    fixture.saved_pdfs = []
    fixture.rendered_exports = []
    fixture.controls.edit_error = None
    fixture.controls.edit_normalizes = True
    fixture.controls.edit_return = None
    fixture.controls.resume_error = None

    inert_insert_note = fixture.drawing.InsertNote

    class ModeDrawing(OfflineReadinessDrawing):
        def GetEditSheet(self):
            self.assert_live("GetEditSheet")
            fixture.mode_events.append(
                ("GetEditSheet", self.current, self.SelectionManager.suspended)
            )
            result = (
                fixture.mode_results.pop(0)
                if fixture.mode_results
                else self.edit_sheet_mode
            )
            if isinstance(result, BaseException):
                raise result
            return result

        def EditSheet(self):
            self.assert_live("EditSheet")
            fixture.mode_events.append(("EditSheet",))
            fixture.edit_calls.append(self)
            if fixture.controls.edit_error is not None:
                raise fixture.controls.edit_error
            if fixture.controls.edit_normalizes:
                self.edit_sheet_mode = True
            return fixture.controls.edit_return

        @property
        def Extension(self):
            self.assert_live("Extension")
            fixture.mode_events.append(("Extension", self.current))
            return SimpleNamespace(SaveAs3=self.save_pdf)

        def save_pdf(self, path, *arguments):
            self.assert_live("SaveAs3")
            assert arguments == (0, 1, None, None, 0, 0)
            assert self.SelectionManager.suspended
            assert self.current is probe.ViewId.A
            fixture.mode_events.append(("SaveAs3", self.current))
            fixture.saved_pdfs.append(Path(path))
            Path(path).write_bytes(b"%PDF-inert-native-port-not-a-visual-oracle")
            return True, 0, 0

    class SelectionManager:
        def __init__(self):
            self.selected = []
            self.suspended = False

        def GetSelectedObjectCount2(self, mark):
            assert mark == -1
            return len(self.selected)

        def GetSelectedObject6(self, index, mark):
            assert mark == -1
            return self.selected[index - 1][0]

        def GetSelectedObjectType3(self, index, mark):
            assert mark == -1
            return 20

        def GetSelectedObjectMark(self, index):
            return self.selected[index - 1][2]

        def GetSelectedObjectsDrawingView2(self, index, mark):
            assert mark == -1
            return self.selected[index - 1][1]

        def SuspendSelectionList(self):
            assert not self.suspended
            fixture.mode_events.append(("SuspendSelectionList",))
            self.original, self.selected = self.selected, []
            self.suspended = True
            return int(bool(self.original))

        def ResumeSelectionList2(self, append):
            assert append is False and self.suspended
            fixture.mode_events.append(("ResumeSelectionList2",))
            self.selected = self.original
            self.suspended = False
            if fixture.controls.resume_error is not None:
                raise fixture.controls.resume_error

    def install_receiver(drawing, *, sheet_qualified_titles=True):
        """Install receiver-local ports; no closure retains an earlier generation."""
        drawing.__class__ = ModeDrawing
        drawing.sheet_qualified_titles = sheet_qualified_titles
        drawing.SelectionManager = SelectionManager()
        drawing.current = probe.ViewId.A
        drawing.ActiveDrawingView = None
        drawing.AutomaticViewUpdate = True
        drawing.ActiveView = SimpleNamespace(EnableGraphicsUpdate=True)
        drawing.FeatureManager = SimpleNamespace(
            EnableFeatureTree=True, EnableFeatureTreeWindow=True
        )
        drawing.groups = [
            fixture.groups[probe.ViewId.B],
            fixture.groups[probe.ViewId.A],
        ]
        drawing.GetViews = lambda: (
            tuple(tuple(group) for group in drawing.groups)
            if len(fixture.created_views) == 2
            else ((object(),),)
        )
        drawing.Sheet = lambda name: fixture.sheets[name]

        def current_sheet():
            drawing.assert_live("GetCurrentSheet")
            fixture.mode_events.append(("GetCurrentSheet", drawing.current))
            return fixture.sheets[drawing.current]

        def activate_sheet(name):
            drawing.assert_live("ActivateSheet")
            fixture.mode_events.append(("ActivateSheet", name))
            drawing.current, drawing.sheet = name, name
            if drawing.sheet_qualified_titles:
                drawing.title = f"Draw - {name}"
            drawing.ActiveDrawingView = None
            return True

        def activate_view(name):
            drawing.assert_live("ActivateView")
            fixture.mode_events.append(("ActivateView", name))
            drawing.ActiveDrawingView = next(
                view for view in fixture.views.values() if view.Name == name
            )
            return True

        def create_view(*arguments):
            drawing.assert_live("CreateDrawViewFromModelView3")
            fixture.mode_events.append(
                ("CreateDrawViewFromModelView3", drawing.current)
            )
            view = fixture.views[drawing.current]
            fixture.created_views.append(view)
            return view

        def clear_selection(all_selected):
            drawing.assert_live("ClearSelection2")
            assert all_selected is True
            fixture.mode_events.append(("ClearSelection2", drawing.current))
            drawing.SelectionManager.selected = []

        drawing.GetCurrentSheet = current_sheet
        drawing.ActivateSheet = activate_sheet
        drawing.ActivateView = activate_view
        drawing.CreateDrawViewFromModelView3 = create_view
        drawing.ClearSelection2 = clear_selection
        drawing.NewSheet4 = lambda *arguments: (
            fixture.mode_events.append(("NewSheet4",)) or True
        )
        drawing.InsertNote = lambda text: (
            fixture.mode_events.append(("InsertNote", drawing.current))
            or inert_insert_note(text)
        )
        return drawing

    fixture.install_mode_receiver = install_receiver
    install_receiver(fixture.drawing)

    def rename_sheet(name):
        fixture.mode_events.append(("SetName", name))
        fixture.drawing.current, fixture.drawing.sheet = name, name
        if fixture.drawing.sheet_qualified_titles:
            fixture.drawing.title = f"Draw - {name}"

    for sheet in fixture.sheets.values():
        sheet.SetName = rename_sheet
    monkeypatch.setattr(subject, "model", probe.NativeProbe.model.__get__(subject))
    monkeypatch.setattr(subject, "draw", probe.NativeProbe.draw.__get__(subject))
    monkeypatch.setattr(
        subject, "activate", probe.NativeProbe.activate.__get__(subject)
    )
    monkeypatch.setattr(
        subject, "rebuild", lambda: fixture.mode_events.append(("rebuild",))
    )

    # Admit the source through the real owner/configuration path, not a model()
    # shortcut that would mask an unadmitted or replaced drawing at export.
    source_component = fixture.components[probe.ViewId.A][probe.NodeId.N].Component
    configuration = SimpleNamespace(
        Name="Default",
        GetDisplayStates=lambda: ("Display State-1",),
        GetDisplayStatesCount=lambda: 1,
        GetDisplayStateComponentVisibility=lambda *arguments: (
            (1,),
            (source_component,),
        ),
    )
    fixture.source.path = str(subject.paths[probe.Document.R])
    fixture.source.GetComponents = lambda _top: (source_component,)
    fixture.source.GetActiveConfiguration = lambda: configuration
    fixture.source.GetConfigurationByName = lambda name: configuration
    with subject.acquiring(probe.Document.R) as before:
        subject.app.models.append(fixture.source)
        subject.app.ActiveDoc = fixture.source
        subject.acquired(probe.Document.R, fixture.source, before)
        subject.claim(probe.Document.R, 2, subject.paths[probe.Document.R])
    subject.expected = {
        view_id: {key: True for key in probe.NodeId} for view_id in probe.ViewId
    }

    def render_export(export, pdf):
        assert pdf in fixture.saved_pdfs
        fixture.rendered_exports.append(export)

    monkeypatch.setattr(subject, "render_export", render_export)
    return fixture


def sheet_mode_record(subject):
    (record,) = [
        row
        for row in subject.receipt.data["ledger"]
        if row["event"] == "drawing_sheet_mode_normalization"
    ]
    assert record is subject.drawing_mode_record
    return record


def prepare_sheet_mode_export(fixture):
    """A marked sentinel context makes actual guard restoration observable."""
    fixture.subject.activate_view(probe.ViewId.B, sheet_only=True)
    fixture.drawing.SelectionManager.selected = [
        (
            fixture.components[probe.ViewId.B][probe.NodeId.P1],
            fixture.views[probe.ViewId.B],
            16,
        )
    ]
    return fixture.subject.context(fixture.subject.views())


def replace_sheet_mode_drawing(fixture):
    """Real close/admission, keeping the construction receiver disconnected."""
    subject, old = fixture.subject, fixture.drawing
    subject.close(probe.Document.DRAWING)
    assert not old.live
    # E5 regressions supply opaque UI-hint changes independently of sheet names.
    replacement = fixture.install_mode_receiver(
        OfflineDrawing(), sheet_qualified_titles=False
    )
    replacement.edit_sheet_mode = True
    with subject.acquiring(probe.Document.DRAWING) as before:
        subject.app.models.append(replacement)
        subject.app.ActiveDoc = replacement
        subject.acquired(probe.Document.DRAWING, replacement, before)
        # The reopen branch has a persisted path and admits existing real views.
        path = subject.paths[probe.Document.DRAWING]
        replacement.path = str(path)
        subject.claim(probe.Document.DRAWING, 3, path)
    fixture.drawing = replacement
    subject.activate(probe.Document.DRAWING)
    return old, replacement


@pytest.mark.parametrize("initial", [False, True])
def test_sheet_mode_actual_construction_normalizes_once_before_any_geometry(
    sheet_mode_contract, initial
):
    fixture = sheet_mode_contract
    fixture.drawing.edit_sheet_mode = initial
    fixture.subject.create_drawing()
    record = sheet_mode_record(fixture.subject)
    assert record["boundary"] == "admitted_new_drawing"
    assert record["document"] is probe.Document.DRAWING
    assert record["generation"] == 1
    assert record["active_identity"]["native_identity"] == 1
    assert record["pre"]["mode"] is (
        probe.DrawingEditMode.SHEET if initial else probe.DrawingEditMode.FORMAT
    )
    assert record["post"]["mode"] is probe.DrawingEditMode.SHEET
    assert all(
        row["mode"] is probe.DrawingEditMode.SHEET
        for row in record["before_views"].values()
    )
    assert fixture.edit_calls == [fixture.drawing]
    names = [event[0] for event in fixture.mode_events]
    assert names[:5] == [
        "GetEditSheet",
        "EditSheet",
        "GetEditSheet",
        "GetCurrentSheet",
        "SetName",
    ]
    assert names.count("GetEditSheet") == 4
    expected_mutators = Counter(
        {
            "EditSheet": 1,
            "SetName": 1,
            "NewSheet4": 1,
            "ActivateSheet": 5,
            "ActivateView": 1,
            "CreateDrawViewFromModelView3": 2,
            "ClearSelection2": 2,
            "InsertNote": 2,
            "rebuild": 1,
        }
    )
    assert (
        Counter(name for name in names if name in expected_mutators)
        == expected_mutators
    )
    assert len(fixture.subject.app.activation_calls) == 1
    assert fixture.scale_writes == [0, 0]
    for index, event in enumerate(fixture.mode_events):
        if event[0] == "CreateDrawViewFromModelView3":
            assert fixture.mode_events[index - 1] == ("GetEditSheet", event[1], False)
    assert len(fixture.created_views) == len(fixture.markers) == 2
    assert fixture.saved_pdfs == []
    assert fixture.subject.receipt.counts[probe.SnapshotKind.FULL] == 0
    assert fixture.subject.receipt.counts[probe.SnapshotKind.SOURCE] == 0
    assert not fixture.subject.receipt.data["observations"]
    fixture.subject.receipt.checkpoint()
    persisted = json.loads((fixture.subject.receipt.root / "report.json").read_text())
    (saved,) = [
        row
        for row in persisted["ledger"]
        if row["event"] == "drawing_sheet_mode_normalization"
    ]
    assert saved["pre"]["mode"] == ("sheet" if initial else "sheet_format")
    assert saved["post"]["mode"] == "sheet"
    assert all(row["mode"] == "sheet" for row in saved["before_views"].values())
    assert all(
        row["status"] == probe.ActiveObservation.NOT_OBSERVED
        for row in saved["exports"].values()
    )
    assert "drawing_sheet_mode_normalization" not in persisted["fixture"]


@pytest.mark.parametrize("pre", ["native_error", None, 0, 1, "sheet", 1.0])
def test_sheet_mode_pre_getter_failure_is_only_diagnostic(sheet_mode_contract, pre):
    fixture = sheet_mode_contract
    value = InertWriteOnlyError() if pre == "native_error" else pre
    fixture.mode_results[:] = [value, True, True, True]
    fixture.subject.create_drawing()
    row = sheet_mode_record(fixture.subject)["pre"]
    assert row["status"] is probe.ActiveObservation.ERROR
    assert "mode" not in row
    if isinstance(value, Exception):
        assert row["error"]["hresult"] == value.hresult
        assert row["error"]["excepinfo"] == value.excepinfo
    else:
        assert row["raw_type"] == type(value).__name__
        assert row["raw_repr"] == repr(value)
        assert row["error"]["type"] == "ProbeFailure"
    assert fixture.edit_calls == [fixture.drawing]
    assert len(fixture.created_views) == len(fixture.markers) == 2


@pytest.mark.parametrize(
    "failure",
    ["void_no_change", "post_false", "post_invalid", "post_error", "edit_error"],
)
def test_sheet_mode_failed_normalization_preserves_primary_and_owned_cleanup(
    sheet_mode_contract, monkeypatch, failure
):
    fixture = sheet_mode_contract
    native = InertWriteOnlyError()
    if failure == "void_no_change":
        fixture.controls.edit_normalizes = False
    elif failure == "edit_error":
        fixture.controls.edit_error = native
    else:
        fixture.mode_results[:] = [
            False,
            {"post_false": False, "post_invalid": 1, "post_error": native}[failure],
        ]
    reporting = OSError("mode failure case-final reporting failed")
    fail_case_final_checkpoint_once(fixture.subject, monkeypatch, reporting)
    primary = capture_and_cleanup_failure(
        fixture.subject, fixture.subject.create_drawing
    )
    assert fixture.created_views == fixture.markers == fixture.saved_pdfs == []
    assert fixture.edit_calls == [fixture.drawing]
    assert fixture.drawing in fixture.subject.app.closed
    assert fixture.subject.receipt.data["cleanup"]["status"] is probe.Verdict.PASSED
    record = sheet_mode_record(fixture.subject)
    if failure == "edit_error":
        assert primary is native
        assert record["normalization"]["error"]["hresult"] == native.hresult
        assert record["post"]["status"] is probe.ActiveObservation.NOT_OBSERVED
        assert (
            fixture.subject.receipt.data["primary_error"]["hresult"] == native.hresult
        )
        assert (
            fixture.subject.receipt.data["primary_error"]["excepinfo"]
            == native.excepinfo
        )
    else:
        assert probe.failure_verdict(primary) is probe.Verdict.CONSTRUCTION
        assert record["normalization"]["status"] is probe.Verdict.PASSED
        if failure == "post_error":
            assert primary is native
            assert (
                fixture.subject.receipt.data["primary_error"]["hresult"]
                == native.hresult
            )
            assert record["post"]["error"]["excepinfo"] == native.excepinfo
        elif failure == "post_invalid":
            assert isinstance(primary, probe.ProbeFailure)
            assert record["post"]["raw_type"] == "int"
        else:
            assert record["post"]["mode"] is probe.DrawingEditMode.FORMAT
    assert any(
        row["message"] == str(reporting)
        for row in fixture.subject.receipt.data["secondary_errors"]
    )
    fixture.subject.receipt.checkpoint()
    persisted = json.loads((fixture.subject.receipt.root / "report.json").read_text())
    assert persisted["primary_error"]["message"] == str(primary)
    assert any(
        row["event"] == "drawing_sheet_mode_normalization"
        for row in persisted["ledger"]
    )


@pytest.mark.parametrize("active", ["foreign", "null"])
def test_sheet_mode_active_receiver_refuses_before_getter_or_mutator(
    sheet_mode_contract, monkeypatch, active
):
    fixture = sheet_mode_contract
    claim = fixture.subject.claim

    def claim_then_change_active(label, kind, path):
        result = claim(label, kind, path)
        if label is probe.Document.DRAWING:
            fixture.subject.app.ActiveDoc = (
                OfflineDrawing() if active == "foreign" else None
            )
        return result

    monkeypatch.setattr(fixture.subject, "claim", claim_then_change_active)
    with pytest.raises(probe.ProbeFailure) as caught:
        fixture.subject.create_drawing()
    assert caught.value.verdict is probe.Verdict.IDENTITY
    assert fixture.mode_events == fixture.edit_calls == fixture.created_views == []
    assert fixture.markers == []
    assert fixture.subject.app.activation_calls == []
    record = sheet_mode_record(fixture.subject)
    assert record["active_identity"]["status"] is probe.ActiveObservation.ERROR
    assert record["pre"]["status"] is probe.ActiveObservation.NOT_OBSERVED
    assert record["normalization"]["status"] is probe.ActiveObservation.NOT_OBSERVED


@pytest.mark.parametrize("view_id", tuple(probe.ViewId))
@pytest.mark.parametrize("failure", ["format", "invalid", "native_error"])
def test_sheet_mode_each_actual_insertion_gate_refuses_affected_geometry(
    sheet_mode_contract, view_id, failure
):
    fixture = sheet_mode_contract
    native = InertWriteOnlyError()
    value = {"format": False, "invalid": 1, "native_error": native}[failure]
    fixture.mode_results[:] = [False, True]
    if view_id is probe.ViewId.B:
        fixture.mode_results.append(True)
    fixture.mode_results.append(value)
    primary = capture_and_cleanup_failure(
        fixture.subject, fixture.subject.create_drawing
    )
    assert probe.failure_verdict(primary) is probe.Verdict.CONSTRUCTION
    row = sheet_mode_record(fixture.subject)["before_views"][view_id]
    assert row["required_mode"] is probe.DrawingEditMode.SHEET
    assert row["document"] is probe.Document.DRAWING
    assert row["generation"] == 1
    expected_count = int(view_id is probe.ViewId.B)
    assert len(fixture.created_views) == len(fixture.markers) == expected_count
    assert fixture.views[view_id] not in fixture.created_views
    assert fixture.edit_calls == [fixture.drawing]
    assert fixture.saved_pdfs == []
    assert fixture.drawing in fixture.subject.app.closed
    if failure == "native_error":
        assert primary is native
        assert (
            fixture.subject.receipt.data["primary_error"]["hresult"] == native.hresult
        )
        assert row["error"]["hresult"] == native.hresult
    elif failure == "invalid":
        assert isinstance(primary, probe.ProbeFailure)
        assert row["raw_type"] == "int" and "mode" not in row
    else:
        assert row["mode"] is probe.DrawingEditMode.FORMAT


@pytest.mark.parametrize("boundary", ["pre", "post", "A", "B"])
@pytest.mark.parametrize(
    "interrupt_type",
    [KeyboardInterrupt, SystemExit, GeneratorExit, probe.InjectedFailure],
)
def test_sheet_mode_construction_control_flow_is_never_diagnostic(
    sheet_mode_contract, boundary, interrupt_type
):
    fixture = sheet_mode_contract
    interruption = (
        probe.InjectedFailure(probe.Case.CONSTRUCTION, probe.Injection.AFTER_SELECTION)
        if interrupt_type is probe.InjectedFailure
        else interrupt_type("stop mode read")
    )
    before = {"pre": [], "post": [False], "A": [False, True], "B": [False, True, True]}
    fixture.mode_results[:] = [*before[boundary], interruption]
    primary = capture_and_cleanup_failure(
        fixture.subject, fixture.subject.create_drawing
    )
    assert primary is interruption
    assert len(fixture.edit_calls) == int(boundary != "pre")
    assert len(fixture.created_views) == int(boundary == "B")
    assert fixture.drawing in fixture.subject.app.closed
    record = sheet_mode_record(fixture.subject)
    row = (
        record[boundary]
        if boundary in ("pre", "post")
        else record["before_views"][probe.ViewId[boundary]]
    )
    assert row["status"] is probe.ActiveObservation.OBSERVING
    assert "mode" not in row and "error" not in row


def test_sheet_mode_observer_never_swallows_owner_or_evidence_errors(
    sheet_mode_contract, monkeypatch
):
    fixture = sheet_mode_contract
    fixture.subject.create_drawing()
    fixture.mode_events.clear()
    owned = fixture.subject.documents.pop(probe.Document.DRAWING)
    try:
        with pytest.raises(probe.ProbeFailure, match="not admitted"):
            fixture.subject._observe_drawing_edit_mode(
                fixture.drawing, {}, verdict=probe.Verdict.CONSTRUCTION
            )
    finally:
        fixture.subject.documents[probe.Document.DRAWING] = owned
    assert fixture.mode_events == []
    original = OSError("receipt row write failed")

    class FailingRow(dict):
        def update(self, **values):
            if "raw_type" in values:
                raise original
            return super().update(**values)

    with pytest.raises(OSError) as caught:
        fixture.subject._observe_drawing_edit_mode(
            fixture.drawing, FailingRow(), verdict=probe.Verdict.CONSTRUCTION
        )
    assert caught.value is original


@pytest.mark.parametrize("export", tuple(probe.Export))
def test_sheet_mode_actual_export_observes_inside_guard_and_restores_context(
    sheet_mode_contract, export
):
    fixture = sheet_mode_contract
    fixture.subject.create_drawing()
    original = prepare_sheet_mode_export(fixture)
    before_counts = fixture.subject.receipt.counts.copy()
    fixture.mode_events.clear()
    fixture.subject.export(export)
    events = fixture.mode_events
    mode_index = next(i for i, event in enumerate(events) if event[0] == "GetEditSheet")
    assert events[mode_index] == ("GetEditSheet", probe.ViewId.A, True)
    assert events[mode_index - 2 : mode_index + 2] == [
        ("ClearSelection2", probe.ViewId.A),
        ("Extension", probe.ViewId.A),
        ("GetEditSheet", probe.ViewId.A, True),
        ("SaveAs3", probe.ViewId.A),
    ]
    assert (
        next(
            i
            for i, event in enumerate(events)
            if event == ("ActivateSheet", probe.ViewId.A)
        )
        < mode_index
    )
    assert events.index(("SuspendSelectionList",)) < mode_index
    assert events.index(("ResumeSelectionList2",)) > mode_index
    assert fixture.subject.context(fixture.subject.views()) == original
    assert fixture.edit_calls == [fixture.drawing]
    assert len(fixture.saved_pdfs) == 1
    assert fixture.rendered_exports == [export]
    row = sheet_mode_record(fixture.subject)["exports"][export]
    assert row["mode"] is probe.DrawingEditMode.SHEET
    assert row["document"] is probe.Document.DRAWING and row["generation"] == 1
    assert (
        fixture.subject.receipt.counts["pdf_export"] - before_counts["pdf_export"] == 1
    )
    assert (
        fixture.subject.receipt.counts[probe.SnapshotKind.FULL]
        - before_counts[probe.SnapshotKind.FULL]
        == 3
    )
    assert (
        fixture.subject.receipt.counts[probe.SnapshotKind.SOURCE]
        == before_counts[probe.SnapshotKind.SOURCE]
    )
    assert [
        event["label"] for event in fixture.subject.receipt.data["observations"]
    ] == [
        f"{export}-before-export",
        "selection-guard-restored",
        f"{export}-after-export",
    ]


@pytest.mark.parametrize("failure", ["format", "invalid", "native_error"])
@pytest.mark.parametrize("restore_error", [False, True])
def test_sheet_mode_export_failure_restores_guard_keeps_evidence_and_cleans_up(
    sheet_mode_contract, failure, restore_error
):
    fixture = sheet_mode_contract
    fixture.subject.create_drawing()
    original = prepare_sheet_mode_export(fixture)
    native = InertWriteOnlyError()
    fixture.mode_results[:] = [
        {"format": False, "invalid": "True", "native_error": native}[failure]
    ]
    secondary = OSError("selection resume reported failure")
    if restore_error:
        fixture.controls.resume_error = secondary
    fixture.mode_events.clear()
    primary = capture_and_cleanup_failure(
        fixture.subject, lambda: fixture.subject.export(probe.Export.BASELINE)
    )
    assert probe.failure_verdict(primary) is probe.Verdict.VISUAL
    assert fixture.saved_pdfs == fixture.rendered_exports == []
    assert not (fixture.subject.receipt.root / "E0.pdf").exists()
    assert ("ResumeSelectionList2",) in fixture.mode_events
    assert fixture.drawing.current is original["sheet"]
    assert fixture.drawing.ActiveDrawingView is None
    assert not fixture.drawing.SelectionManager.suspended
    assert fixture.drawing.SelectionManager.selected[0][2] == 16
    assert fixture.drawing in fixture.subject.app.closed
    row = sheet_mode_record(fixture.subject)["exports"][probe.Export.BASELINE]
    assert row["required_mode"] is probe.DrawingEditMode.SHEET
    assert row["generation"] == 1
    if failure == "native_error":
        assert primary is native
        assert (
            fixture.subject.receipt.data["primary_error"]["hresult"] == native.hresult
        )
        assert (
            fixture.subject.receipt.data["primary_error"]["excepinfo"]
            == native.excepinfo
        )
        assert row["error"]["hresult"] == native.hresult
    elif failure == "invalid":
        assert isinstance(primary, probe.ProbeFailure)
        assert row["raw_repr"] == "'True'" and "mode" not in row
    else:
        assert row["mode"] is probe.DrawingEditMode.FORMAT
    if restore_error:
        assert any(
            row["message"] == str(secondary)
            for row in fixture.subject.receipt.data["secondary_errors"]
        )
    assert fixture.subject.receipt.primary is primary
    fixture.subject.receipt.checkpoint()
    persisted = json.loads((fixture.subject.receipt.root / "report.json").read_text())
    assert persisted["primary_error"]["message"] == str(primary)
    (record,) = [
        item
        for item in persisted["ledger"]
        if item["event"] == "drawing_sheet_mode_normalization"
    ]
    assert record["exports"]["E0"]["required_mode"] == "sheet"


@pytest.mark.parametrize(
    "interrupt_type",
    [KeyboardInterrupt, SystemExit, GeneratorExit, probe.InjectedFailure],
)
def test_sheet_mode_export_control_flow_propagates_after_guard_restoration(
    sheet_mode_contract, interrupt_type
):
    fixture = sheet_mode_contract
    fixture.subject.create_drawing()
    original = prepare_sheet_mode_export(fixture)
    interruption = (
        probe.InjectedFailure(probe.Case.CONSTRUCTION, probe.Injection.AFTER_SELECTION)
        if interrupt_type is probe.InjectedFailure
        else interrupt_type("stop export mode read")
    )
    fixture.mode_results[:] = [interruption]
    with pytest.raises(interrupt_type) as caught:
        fixture.subject.export(probe.Export.BASELINE)
    assert caught.value is interruption
    assert fixture.subject.context(fixture.subject.views()) == original
    assert not fixture.drawing.SelectionManager.suspended
    assert fixture.saved_pdfs == []
    row = sheet_mode_record(fixture.subject)["exports"][probe.Export.BASELINE]
    assert row["status"] is probe.ActiveObservation.OBSERVING


@pytest.mark.parametrize("replacement_mode", [True, False])
def test_sheet_mode_e5_consumes_current_admitted_generation_not_disposed_origin(
    sheet_mode_contract, replacement_mode
):
    fixture = sheet_mode_contract
    fixture.subject.create_drawing()
    old, replacement = replace_sheet_mode_drawing(fixture)
    owned = fixture.subject.documents[probe.Document.DRAWING]
    admitted_title = owned.title
    admitted = (owned.native, owned.path, owned.kind, owned.generation, owned.state)
    replacement.edit_sheet_mode = replacement_mode
    original = prepare_sheet_mode_export(fixture)
    replacement.title = "Opaque reopened UI hint :: not a path or sheet name"
    assert replacement.title != admitted_title
    fixture.mode_events.clear()
    if replacement_mode:
        fixture.subject.export(probe.Export.REOPENED)
        assert fixture.subject.context(fixture.subject.views()) == original
        assert len(fixture.saved_pdfs) == 1
    else:
        with pytest.raises(probe.ProbeFailure) as caught:
            fixture.subject.export(probe.Export.REOPENED)
        assert caught.value.verdict is probe.Verdict.VISUAL
        assert fixture.saved_pdfs == []
        assert fixture.subject.context(fixture.subject.views()) == original
    assert owned.title == replacement.title
    assert (
        owned.native,
        owned.path,
        owned.kind,
        owned.generation,
        owned.state,
    ) == admitted
    assert owned.path is not None and owned.generation == 2
    refreshes = [
        row
        for row in fixture.subject.receipt.data["ledger"]
        if row["event"] == "title_refresh" and row["generation"] == 2
    ]
    assert any(
        row["fresh_title"] == replacement.title
        and row["path"] == str(owned.path)
        and row["kind"] == 3
        and row["native_is_same"] == 1
        for row in refreshes
    )
    assert any(
        call == (replacement.title, False, 2, 0)
        for call in fixture.subject.app.activation_calls
    )
    assert fixture.subject.model(probe.Document.DRAWING) is not old
    assert (
        fixture.subject.app.document(fixture.subject.model(probe.Document.DRAWING))
        is replacement
    )
    assert old.disconnected_accesses == []
    assert fixture.edit_calls == [old]
    assert [event for event in fixture.mode_events if event[0] == "GetEditSheet"] == [
        ("GetEditSheet", probe.ViewId.A, True)
    ]
    record = sheet_mode_record(fixture.subject)
    assert record["generation"] == 1
    assert record["post"]["generation"] == 1
    row = record["exports"][probe.Export.REOPENED]
    assert row["generation"] == 2 and row["document"] is probe.Document.DRAWING
    assert row["mode"] is (
        probe.DrawingEditMode.SHEET
        if replacement_mode
        else probe.DrawingEditMode.FORMAT
    )


@pytest.mark.parametrize(
    "fault", ("cleared_path", "changed_path", "wrong_kind", "identity", "collision")
)
def test_sheet_mode_saved_replacement_drift_refuses_before_e5_mode_gate(
    sheet_mode_contract, fault
):
    fixture = sheet_mode_contract
    subject = fixture.subject
    subject.create_drawing()
    old, replacement = replace_sheet_mode_drawing(fixture)
    owned = subject.documents[probe.Document.DRAWING]
    admitted = (owned.title, owned.path, owned.kind, owned.generation, owned.native)
    prepare_sheet_mode_export(fixture)
    replacement.title = "Opaque saved hint with rejected admission drift"
    if fault == "cleared_path":
        replacement.path = ""
    elif fault == "changed_path":
        replacement.path = str(subject.root / "another-drawing.slddrw")
    elif fault == "wrong_kind":
        replacement.kind = 2
    elif fault == "identity":
        foreign = OfflineDrawing(replacement.path)
        foreign.title = replacement.title
        subject.app.models[subject.app.models.index(replacement)] = foreign
        subject.app.ActiveDoc = foreign
    else:
        replacement.title = fixture.source.title.swapcase()
    fixture.mode_events.clear()
    activation_calls = list(subject.app.activation_calls)
    close_calls = list(subject.app.close_calls)
    with pytest.raises(probe.ProbeFailure) as caught:
        subject.export(probe.Export.REOPENED)
    assert caught.value.verdict is probe.Verdict.PRESERVATION
    assert (
        owned.title,
        owned.path,
        owned.kind,
        owned.generation,
        owned.native,
    ) == admitted
    assert owned.path is not None and owned.generation == 2
    assert not [
        event
        for event in fixture.mode_events
        if event[0] in ("GetEditSheet", "SaveAs3")
    ]
    assert subject.app.activation_calls == activation_calls
    assert subject.app.close_calls == close_calls
    assert not [row for row in title_refreshes(subject) if row["generation"] == 2]
    assert fixture.saved_pdfs == fixture.rendered_exports == []
    assert subject.receipt.counts["selection_guard"] == 0
    assert old.disconnected_accesses == replacement.disconnected_accesses == []
    assert fixture.edit_calls == [old]
    assert (
        sheet_mode_record(subject)["exports"][probe.Export.REOPENED]["status"]
        is probe.ActiveObservation.NOT_OBSERVED
    )
    event = subject.receipt.data["observations"][-1]
    assert event["label"] == "E5-before-export"
    snapshot = subject.receipt.data["snapshots"][event["content"]]
    assert snapshot["source"]["observation_error"]["message"] == str(caught.value)


@pytest.mark.parametrize("state", ["absent", "pending"])
def test_sheet_mode_e5_never_observes_an_unadmitted_replacement(
    sheet_mode_contract, state
):
    fixture = sheet_mode_contract
    fixture.subject.create_drawing()
    old, replacement = replace_sheet_mode_drawing(fixture)
    if state == "absent":
        fixture.subject.documents.pop(probe.Document.DRAWING)
    else:
        fixture.subject.documents[
            probe.Document.DRAWING
        ].state = probe.AcquisitionState.PENDING
    fixture.mode_events.clear()
    with pytest.raises(probe.ProbeFailure, match="not admitted"):
        fixture.subject.export(probe.Export.REOPENED)
    assert fixture.mode_events == []
    assert fixture.saved_pdfs == []
    assert old.disconnected_accesses == replacement.disconnected_accesses == []
    assert (
        sheet_mode_record(fixture.subject)["exports"][probe.Export.REOPENED]["status"]
        is probe.ActiveObservation.NOT_OBSERVED
    )


def test_sheet_mode_actual_c00_retains_two_full_and_no_source_observations(
    sheet_mode_contract, monkeypatch
):
    fixture = sheet_mode_contract
    subject = fixture.subject
    monkeypatch.setattr(
        subject, "case_checkpoint", probe.NativeProbe.case_checkpoint.__get__(subject)
    )

    def construct():
        subject.create_drawing()
        subject._constructed_drawing_checkpoint()

    subject.run_case(probe.Case.CONSTRUCTION, construct)
    assert subject.receipt.counts[probe.SnapshotKind.FULL] == 2
    assert subject.receipt.counts[probe.SnapshotKind.SOURCE] == 0
    assert [event["label"] for event in subject.receipt.data["observations"]] == [
        "constructed-drawing",
        "case-candidate-complete",
    ]
    assert len(subject.receipt.data["cases"]) == 29
    assert subject.receipt.data["bounds"]["case_slots"] == 32
    assert len(fixture.edit_calls) == 1
    assert (
        len([event for event in fixture.mode_events if event[0] == "GetEditSheet"]) == 4
    )
    context = subject.context(subject.views())
    assert set(context) == {"sheet", "view", "selection", "flags"}
    snapshots = dict(subject.receipt.data["snapshots"])
    subject.drawing_mode_record["pre"]["raw_repr"] = "diagnostic-only changed"
    assert subject.context(subject.views()) == context
    subject.checkpoint("same-semantic-state-after-mode-diagnostic-change")
    assert subject.receipt.data["snapshots"] == snapshots


@pytest.fixture
def readiness(sheet_inventory, monkeypatch):
    """Actual readback/orchestration; only native receiver ports are inert."""
    fixture = sheet_inventory
    subject, drawing = fixture.subject, fixture.drawing
    fixture.reads = []
    fixture.faults = {}
    fixture.writes = []
    fixture.accept_writes = False
    fixture.ignored_writes = set()

    def write_flag(key, value):
        assert fixture.accept_writes, f"unexpected inert flag write: {key}"
        assert type(value) is bool
        fixture.writes.append((key, value))
        if key not in fixture.ignored_writes:
            fixture.flag_values[key] = value

    fixture.flag_values = {
        "A_disable": False,
        "B_disable": True,
        "automatic": True,
        "graphics": False,
        "tree": True,
        "tree_window": False,
    }

    class ReadPort:
        def __init__(self, members):
            self.members = members

        def __getattr__(self, member):
            key = self.members[member]
            fixture.reads.append(key)
            if key in fixture.faults:
                raise fixture.faults[key]
            return fixture.flag_values[key]

        def __setattr__(self, member, value):
            if member == "members":
                object.__setattr__(self, member, value)
            else:
                write_flag(self.members[member], value)

    viewport = ReadPort({"EnableGraphicsUpdate": "graphics"})
    tree = ReadPort(
        {"EnableFeatureTree": "tree", "EnableFeatureTreeWindow": "tree_window"}
    )
    ports = {"ActiveView": viewport, "FeatureManager": tree}

    class ReadinessDrawing(OfflineReadinessDrawing):
        def __getattribute__(self, member):
            if member == "ActiveDrawingView" and "view" in fixture.faults:
                raise fixture.faults["view"]
            if member in ports or member == "AutomaticViewUpdate":
                key = "automatic" if member == "AutomaticViewUpdate" else member
                fixture.reads.append(key)
                if key in fixture.faults:
                    raise fixture.faults[key]
                return fixture.flag_values[key] if key == "automatic" else ports[key]
            return super().__getattribute__(member)

        def __setattr__(self, member, value):
            if member == "AutomaticViewUpdate":
                write_flag("automatic", value)
            elif member in ports:
                raise AssertionError(
                    f"viewport/tree receiver must not be assigned: {member}"
                )
            else:
                super().__setattr__(member, value)

    class ReadinessView(OfflineModel):
        @property
        def DisableAutoUpdate(self):
            key = f"{probe.ViewId(self.Sheet.GetName()).name}_disable"
            fixture.reads.append(key)
            if key in fixture.faults:
                raise fixture.faults[key]
            return fixture.flag_values[key]

        @DisableAutoUpdate.setter
        def DisableAutoUpdate(self, value):
            write_flag(f"{probe.ViewId(self.Sheet.GetName()).name}_disable", value)

    drawing.__class__ = ReadinessDrawing
    for view in fixture.views.values():
        view.__class__ = ReadinessView
    fixture.ports = ports
    fixture.selection_reads = []

    def selected_count(mark):
        fixture.selection_reads.append(("count", mark))
        if "selection" in fixture.faults:
            raise fixture.faults["selection"]
        return 0

    drawing.SelectionManager = SimpleNamespace(GetSelectedObjectCount2=selected_count)
    full_views = drawing.GetViews
    drawing.GetViews = lambda: ((object(),),)
    try:
        with subject.acquiring(probe.Document.DRAWING) as before:
            subject.app.models.append(drawing)
            subject.app.ActiveDoc = drawing
            subject.acquired(probe.Document.DRAWING, drawing, before)
            subject.claim(probe.Document.DRAWING, 3, None)
    finally:
        drawing.GetViews = full_views
    admitted_model = probe.NativeProbe.model
    monkeypatch.setattr(
        subject,
        "model",
        lambda label: (
            admitted_model(subject, label)
            if label is probe.Document.DRAWING
            else fixture.source
        ),
    )
    monkeypatch.setattr(subject, "sources", lambda: {"inert_source_inventory": True})
    subject.expected = {
        view_id: {key: True for key in probe.NodeId} for view_id in probe.ViewId
    }
    subject.receipt.data["fixture"] = {
        "paths": {key: str(path) for key, path in subject.paths.items()},
        "native_generations": dict(subject.generations),
    }
    return fixture


def readiness_snapshot(subject, *, full_count=1):
    (event,) = [
        event
        for event in subject.receipt.data["observations"]
        if event["label"] == "constructed-drawing"
    ]
    assert event["id"] == "F001"
    assert subject.receipt.counts[probe.SnapshotKind.FULL] == full_count
    construction = subject.receipt.data["cases"][probe.Case.CONSTRUCTION]
    assert not any(
        identifier.startswith(probe.SnapshotKind.SOURCE)
        for identifier in construction["checkpoints"]
    )
    return subject.receipt.data["snapshots"][event["content"]]


def assert_full_readiness_views(snapshot):
    assert set(snapshot["views"]) == set(probe.ViewId)
    for view_id, observed in snapshot["views"].items():
        assert set(observed["nodes"]) == set(probe.NodeId)
        assert observed["effective"] == {key: True for key in probe.NodeId}
        assert observed["view"]["use_sheet_scale"] == 0
        assert observed["nodes"][probe.NodeId.P1]["parent"] == probe.NodeId.N
        assert observed["nodes"][probe.NodeId.Q2]["parent"] is None


def test_readiness_flags_use_active_view_and_exact_six_values(readiness):
    fixture = readiness
    with pytest.raises(InertWriteOnlyError) as caught:
        _ = fixture.drawing.IActiveView
    assert caught.value.hresult == -2147352567
    assert caught.value.excepinfo[2] == "Unable to read write-only property."
    assert caught.value.argerror is None
    assert fixture.subject.flags() == fixture.flag_values
    assert Counter(fixture.reads) == Counter(
        (*fixture.flag_values, "ActiveView", "FeatureManager")
    )
    assert fixture.context_calls == []
    assert fixture.subject.app.activation_calls == []


def test_readiness_late_flag_error_retains_six_independent_receipts(readiness):
    fixture = readiness
    original = InertWriteOnlyError()
    fixture.faults["tree_window"] = original
    values, evidence, error = fixture.subject._flag_observations(
        fixture.subject.views()
    )
    assert error is original
    assert values == {
        key: value for key, value in fixture.flag_values.items() if key != "tree_window"
    }
    assert set(evidence["values"]) == set(fixture.flag_values)
    assert evidence["receiver"]["document"] == probe.Document.DRAWING
    assert evidence["receiver"]["generation"] == 1
    assert evidence["receiver"]["status"] == "passed"
    for key, row in evidence["values"].items():
        assert row["owner"] and row["member"] and row["provenance"]
        if key != "tree_window":
            assert row["status"] == "passed"
            assert type(row["value"]) is bool
            assert row["value"] is fixture.flag_values[key]
            assert row["type"] == "bool"
            assert row["repr"] == repr(fixture.flag_values[key])
        else:
            assert row["status"] == "failed"
            assert row["error"]["message"] == str(original)
            assert row["error"]["traceback"]
            assert row["error"]["hresult"] == original.hresult
            assert tuple(row["error"]["excepinfo"]) == original.excepinfo
            assert row["error"]["argerror"] is None
    assert Counter(fixture.reads) == Counter(
        (*fixture.flag_values, "ActiveView", "FeatureManager")
    )
    fixture.reads.clear()
    with pytest.raises(InertWriteOnlyError) as caught:
        fixture.subject.flags()
    assert caught.value is original
    assert Counter(fixture.reads) == Counter(
        (*fixture.flag_values, "ActiveView", "FeatureManager")
    )


@pytest.mark.parametrize(
    ("dependency", "blocked"),
    [
        ("ActiveView", {"graphics"}),
        ("FeatureManager", {"tree", "tree_window"}),
    ],
)
def test_readiness_failed_dependency_only_blocks_its_own_flags(
    readiness, dependency, blocked
):
    fixture = readiness
    original = InertWriteOnlyError()
    fixture.faults[dependency] = original
    values, evidence, error = fixture.subject._flag_observations(
        fixture.subject.views()
    )
    assert error is original
    assert values == {
        key: value for key, value in fixture.flag_values.items() if key not in blocked
    }
    assert evidence["dependencies"][dependency]["status"] == "failed"
    for key, row in evidence["values"].items():
        assert row["status"] == ("blocked" if key in blocked else "passed")
    assert Counter(fixture.reads) == Counter(
        (
            *(key for key in fixture.flag_values if key not in blocked),
            "ActiveView",
            "FeatureManager",
        )
    )


@pytest.mark.parametrize(
    "key", ["A_disable", "B_disable", "automatic", "graphics", "tree", "tree_window"]
)
@pytest.mark.parametrize("value", [0, 1, None, "False", 0.0])
def test_readiness_nonboolean_is_failed_receipt_not_a_default(readiness, key, value):
    fixture = readiness
    fixture.flag_values[key] = value
    values, evidence, error = fixture.subject._flag_observations(
        fixture.subject.views()
    )
    assert isinstance(error, probe.ProbeFailure)
    assert key not in values
    assert set(values) == set(fixture.flag_values) - {key}
    assert evidence["values"][key]["status"] == "failed"
    assert evidence["values"][key]["error"]["message"]
    assert Counter(fixture.reads) == Counter(
        (*fixture.flag_values, "ActiveView", "FeatureManager")
    )
    with pytest.raises(probe.ProbeFailure):
        fixture.subject.flags()


@pytest.mark.parametrize("fault", ["foreign_active", "null_active", "unadmitted"])
def test_readiness_owner_failure_blocks_all_unsafe_reads_without_activation(
    readiness, fault
):
    fixture = readiness
    if fault == "foreign_active":
        fixture.subject.app.ActiveDoc = OfflineDrawing()
    elif fault == "null_active":
        fixture.subject.app.ActiveDoc = None
    else:
        fixture.subject.documents.clear()
    values, evidence, error = fixture.subject._flag_observations(
        fixture.subject.views()
    )
    assert isinstance(error, probe.ProbeFailure)
    assert values == {}
    assert evidence["receiver"]["status"] == "failed"
    assert all(row["status"] == "blocked" for row in evidence["values"].values())
    assert fixture.reads == []
    with pytest.raises(probe.ProbeFailure):
        fixture.subject.flags()
    assert fixture.reads == []
    assert fixture.subject.app.activation_calls == []
    assert fixture.context_calls == []


def test_readiness_null_viewport_blocks_graphics_without_substitution(readiness):
    fixture = readiness
    fixture.ports["ActiveView"] = None
    fixture.drawing.ActiveDrawingView = fixture.views[probe.ViewId.A]
    values, evidence, error = fixture.subject._flag_observations(
        fixture.subject.views()
    )
    assert isinstance(error, probe.ProbeFailure)
    assert set(values) == set(fixture.flag_values) - {"graphics"}
    assert evidence["dependencies"]["ActiveView"]["status"] == "failed"
    assert evidence["values"]["graphics"]["status"] == "blocked"
    assert "graphics" not in fixture.reads
    assert fixture.subject.app.activation_calls == []
    with pytest.raises(probe.ProbeFailure):
        fixture.subject.flags()


def test_readiness_context_observes_zero_selection_and_sheet_context(readiness):
    fixture = readiness
    context = fixture.subject.context(fixture.subject.views())
    assert set(context) == {"sheet", "view", "selection", "flags"}
    assert context["sheet"] == probe.ViewId.A
    assert context["view"] is None
    assert context["selection"] == []
    assert context["flags"] == fixture.flag_values
    assert fixture.selection_reads == [("count", -1)]
    assert Counter(fixture.reads) == Counter(
        (*fixture.flag_values, "ActiveView", "FeatureManager")
    )


@pytest.mark.parametrize("branch", ["sheet", "view", "selection", "tree_window"])
def test_readiness_checkpoint_retains_full_views_and_independent_context(
    readiness, monkeypatch, branch
):
    fixture = readiness
    original = InertWriteOnlyError()
    if branch == "sheet":

        def fail_sheet():
            raise original

        monkeypatch.setattr(fixture.drawing, "GetCurrentSheet", fail_sheet)
    else:
        fixture.faults[branch] = original
    with pytest.raises(InertWriteOnlyError) as caught:
        fixture.subject.checkpoint("constructed-drawing")
    assert caught.value is original
    snapshot = readiness_snapshot(fixture.subject)
    assert_full_readiness_views(snapshot)
    context = snapshot["context"]
    if branch != "view":
        assert context["view"] is None
    if branch != "sheet":
        assert context["sheet"] == probe.ViewId.A
    if branch != "selection":
        assert context["selection"] == []
    if branch != "tree_window":
        assert context["flags"] == fixture.flag_values
    evidence = context["flag_observations"]
    assert set(evidence["values"]) == set(fixture.flag_values)
    assert evidence["values"]["tree_window"]["status"] == (
        "failed" if branch == "tree_window" else "passed"
    )
    assert fixture.selection_reads == [("count", -1)]
    assert Counter(fixture.reads) == Counter(
        (*fixture.flag_values, "ActiveView", "FeatureManager")
    )
    persisted = json.loads((fixture.subject.receipt.root / "report.json").read_text())
    event = persisted["observations"][0]
    assert persisted["snapshots"][event["content"]]["views"]
    assert "initial_flags" not in fixture.subject.receipt.data["fixture"]
    assert not hasattr(fixture.subject, "harness_flags")


def test_readiness_success_initializes_only_from_single_validated_checkpoint(readiness):
    fixture = readiness
    fixture.subject._constructed_drawing_checkpoint()
    snapshot = readiness_snapshot(fixture.subject)
    assert_full_readiness_views(snapshot)
    assert fixture.subject.harness_flags == snapshot["context"]["flags"]
    assert (
        fixture.subject.receipt.data["fixture"]["initial_flags"] == fixture.flag_values
    )
    assert Counter(fixture.reads) == Counter(
        (*fixture.flag_values, "ActiveView", "FeatureManager")
    )
    (identity,) = fixture.subject.receipt.data["native_identity_controls"]
    assert all(value == 1 for value in identity["positive_is_same"].values())
    assert set(identity["negative_is_same"].values()) == {0}


@pytest.mark.parametrize("later", ["none", "flags", "report"])
def test_readiness_identity_primary_survives_later_checkpoint_failure(
    readiness, monkeypatch, later
):
    fixture = readiness
    original = probe.ProbeFailure(probe.Verdict.IDENTITY, "identity closure refused")
    secondary = InertWriteOnlyError()

    def fail_identity():
        raise original

    monkeypatch.setattr(fixture.subject, "identity_controls", fail_identity)
    if later == "flags":
        fixture.faults["tree_window"] = secondary
    elif later == "report":

        def fail_report():
            raise secondary

        monkeypatch.setattr(fixture.subject.receipt, "checkpoint", fail_report)
    with pytest.raises(probe.ProbeFailure) as caught:
        fixture.subject._constructed_drawing_checkpoint()
    assert caught.value is original
    assert_full_readiness_views(readiness_snapshot(fixture.subject))
    assert not hasattr(fixture.subject, "harness_flags")
    assert "initial_flags" not in fixture.subject.receipt.data["fixture"]
    if later != "none":
        assert any(
            row["message"] == str(secondary)
            for row in fixture.subject.receipt.data["secondary_errors"]
        )
    assert Counter(fixture.reads) == Counter(
        (*fixture.flag_values, "ActiveView", "FeatureManager")
    )


def test_readiness_failure_stops_actual_run_before_c01_or_candidate(
    readiness, monkeypatch
):
    fixture = readiness
    original = InertWriteOnlyError()
    fixture.faults["tree_window"] = original
    fixture.subject.construction_action = (
        fixture.subject._constructed_drawing_checkpoint
    )
    reached = []
    monkeypatch.setattr(
        fixture.subject, "apply", lambda *args, **kwargs: reached.append("candidate")
    )
    with pytest.raises(InertWriteOnlyError) as caught:
        fixture.subject.run()
    assert caught.value is original
    assert reached == []
    assert fixture.subject.receipt.primary is original
    assert fixture.subject.receipt.data["handoff_allowed"] is False
    assert all(
        row["status"] is probe.Verdict.NOT_EXECUTED
        for case, row in fixture.subject.receipt.data["cases"].items()
        if case is not probe.Case.CONSTRUCTION
    )
    assert_full_readiness_views(readiness_snapshot(fixture.subject))
    assert "initial_flags" not in fixture.subject.receipt.data["fixture"]
    assert not hasattr(fixture.subject, "harness_flags")


def test_readiness_context_owner_failure_blocks_all_dependent_branches(readiness):
    fixture = readiness
    fixture.subject.app.ActiveDoc = OfflineDrawing()
    context, error = fixture.subject._context_observations(fixture.subject.views())
    assert isinstance(error, probe.ProbeFailure)
    assert fixture.reads == []
    assert fixture.selection_reads == []
    assert fixture.context_calls == []
    assert fixture.subject.app.activation_calls == []
    assert not any(key in context for key in ("sheet", "view", "selection"))
    assert context["observations"]["receiver"]["status"] == "failed"
    with pytest.raises(probe.ProbeFailure):
        fixture.subject.context(fixture.subject.views())
    assert fixture.reads == []
    assert fixture.selection_reads == []


def test_readiness_context_preserves_first_error_and_later_branch_receipts(readiness):
    fixture = readiness
    primary = InertWriteOnlyError()
    secondary = OSError("later tree-window getter")
    fixture.faults["selection"] = primary
    fixture.faults["tree_window"] = secondary
    context, error = fixture.subject._context_observations(fixture.subject.views())
    assert error is primary
    assert context["sheet"] == probe.ViewId.A
    assert context["view"] is None
    assert context["observations"]["selection"]["error"]["message"] == str(primary)
    assert context["flag_observations"]["values"]["tree_window"]["error"][
        "message"
    ] == str(secondary)
    assert context["flags"] == {
        key: value for key, value in fixture.flag_values.items() if key != "tree_window"
    }
    assert Counter(fixture.reads) == Counter(
        (*fixture.flag_values, "ActiveView", "FeatureManager")
    )
    with pytest.raises(InertWriteOnlyError) as caught:
        fixture.subject.context(fixture.subject.views())
    assert caught.value is primary


def test_readiness_checkpoint_returns_the_complete_validated_context(readiness):
    fixture = readiness
    context = fixture.subject.checkpoint("constructed-drawing")
    assert context == readiness_snapshot(fixture.subject)["context"]
    assert context["flags"] == fixture.flag_values
    assert context["selection"] == []
    assert fixture.selection_reads == [("count", -1)]
    assert Counter(fixture.reads) == Counter(
        (*fixture.flag_values, "ActiveView", "FeatureManager")
    )


def test_readiness_source_error_keeps_context_and_report_failures_secondary(
    readiness, monkeypatch
):
    fixture = readiness
    primary = OSError("source readback failed first")
    context_error = InertWriteOnlyError()
    reporting = OSError("report persistence failed last")

    def fail_sources():
        raise primary

    def fail_report():
        raise reporting

    monkeypatch.setattr(fixture.subject, "sources", fail_sources)
    monkeypatch.setattr(fixture.subject.receipt, "checkpoint", fail_report)
    fixture.faults["selection"] = context_error
    with pytest.raises(OSError) as caught:
        fixture.subject.checkpoint("constructed-drawing")
    assert caught.value is primary
    snapshot = readiness_snapshot(fixture.subject)
    assert_full_readiness_views(snapshot)
    assert snapshot["source"]["observation_error"]["message"] == str(primary)
    assert snapshot["context"]["flags"] == fixture.flag_values
    assert snapshot["context"]["observations"]["selection"]["error"]["message"] == str(
        context_error
    )
    messages = [
        row["message"] for row in fixture.subject.receipt.data["secondary_errors"]
    ]
    assert str(context_error) in messages
    assert str(reporting) in messages


def test_readiness_failed_actual_identity_control_keeps_comparison_evidence(
    readiness, monkeypatch
):
    fixture = readiness
    same = fixture.subject.same

    def wrong_distinct_result(left, right):
        if (
            left is fixture.views[probe.ViewId.A]
            and right is fixture.views[probe.ViewId.B]
        ):
            return 1
        return same(left, right)

    monkeypatch.setattr(fixture.subject, "same", wrong_distinct_result)
    with pytest.raises(probe.ProbeFailure) as caught:
        fixture.subject._constructed_drawing_checkpoint()
    assert caught.value.verdict is probe.Verdict.IDENTITY
    (identity,) = fixture.subject.receipt.data["native_identity_controls"]
    assert identity["negative_is_same"] == {
        "distinct_views": 1,
        "distinct_same_part_instances": 0,
    }
    assert identity["positive_is_same"]
    assert all(value == 1 for value in identity["positive_is_same"].values())
    assert_full_readiness_views(readiness_snapshot(fixture.subject))
    assert not hasattr(fixture.subject, "harness_flags")
    assert "initial_flags" not in fixture.subject.receipt.data["fixture"]


def test_readiness_entry_keeps_getter_primary_through_reporting_and_owned_cleanup(
    readiness, monkeypatch
):
    fixture = readiness
    original = InertWriteOnlyError()
    reporting = OSError("case-final report failed after readiness")
    fixture.faults["tree_window"] = original
    fixture.subject.construction_action = (
        fixture.subject._constructed_drawing_checkpoint
    )
    with pytest.raises(InertWriteOnlyError) as caught:
        invoke_offline_entry(fixture.subject, monkeypatch, reporting)
    assert caught.value is original
    assert fixture.subject.receipt.primary is original
    assert fixture.subject.receipt.data["handoff_allowed"] is False
    assert fixture.subject.receipt.data["cleanup"]["status"] is probe.Verdict.PASSED
    assert fixture.subject.app.closed == [fixture.drawing]
    assert all(
        row["status"] is probe.Verdict.NOT_EXECUTED
        for case, row in fixture.subject.receipt.data["cases"].items()
        if case not in (probe.Case.CONSTRUCTION, probe.Case.CLEANUP)
    )
    assert any(
        row["message"] == str(reporting)
        for row in fixture.subject.receipt.data["secondary_errors"]
    )
    assert_full_readiness_views(readiness_snapshot(fixture.subject))
    receipt = fixture.subject.receipt
    cleanup = receipt.data["cases"][probe.Case.CLEANUP]
    (source,) = [
        event
        for event in receipt.data["observations"]
        if event["id"] in cleanup["checkpoints"]
        and event["id"].startswith(probe.SnapshotKind.SOURCE)
    ]
    assert source["id"] == "S001"
    assert source["label"] == "cleanup-final-empty-and-source-disk"
    assert source["content"] in receipt.data["snapshots"]
    assert receipt.counts[probe.SnapshotKind.SOURCE] == 1
    assert receipt.data["observations"].index(source) > next(
        index
        for index, event in enumerate(receipt.data["observations"])
        if event["id"] == "F001"
    )


def test_readiness_flags_reacquire_and_bind_the_current_viewport(
    readiness, monkeypatch
):
    fixture = readiness
    first = SimpleNamespace(EnableGraphicsUpdate=False)
    second = SimpleNamespace(EnableGraphicsUpdate=True)
    bound = []
    bind = fixture.subject.bind

    def capture_binding(raw, interface):
        if interface == "IModelView":
            bound.append(raw)
        return bind(raw, interface)

    monkeypatch.setattr(fixture.subject, "bind", capture_binding)
    fixture.ports["ActiveView"] = first
    assert fixture.subject.flags()["graphics"] is False
    fixture.ports["ActiveView"] = second
    assert fixture.subject.flags()["graphics"] is True
    assert bound == [first, second]
    assert fixture.reads.count("ActiveView") == 2
    assert fixture.subject.app.activation_calls == []


@pytest.mark.parametrize("failure", ["tree_window", "report"])
def test_readiness_helper_never_initializes_after_incomplete_checkpoint(
    readiness, monkeypatch, failure
):
    fixture = readiness
    original = InertWriteOnlyError()
    if failure == "report":

        def fail_report():
            raise original

        monkeypatch.setattr(fixture.subject.receipt, "checkpoint", fail_report)
    else:
        fixture.faults[failure] = original
    with pytest.raises(InertWriteOnlyError) as caught:
        fixture.subject._constructed_drawing_checkpoint()
    assert caught.value is original
    assert_full_readiness_views(readiness_snapshot(fixture.subject))
    assert not hasattr(fixture.subject, "harness_flags")
    assert "initial_flags" not in fixture.subject.receipt.data["fixture"]
    assert Counter(fixture.reads) == Counter(
        (*fixture.flag_values, "ActiveView", "FeatureManager")
    )


def test_readiness_semantic_context_ignores_valid_receiver_wrapper_types(readiness):
    fixture = readiness
    views = fixture.subject.views()
    before = fixture.subject.context(views)
    first, error = fixture.subject._context_observations(views)
    assert error is None

    class FreshViewport(SimpleNamespace):
        pass

    class FreshTree(SimpleNamespace):
        pass

    fixture.ports["ActiveView"] = FreshViewport(
        EnableGraphicsUpdate=fixture.flag_values["graphics"]
    )
    fixture.ports["FeatureManager"] = FreshTree(
        EnableFeatureTree=fixture.flag_values["tree"],
        EnableFeatureTreeWindow=fixture.flag_values["tree_window"],
    )
    after = fixture.subject.context(views)
    second, error = fixture.subject._context_observations(views)
    assert error is None
    assert (
        before
        == after
        == {
            "sheet": probe.ViewId.A,
            "view": None,
            "selection": [],
            "flags": fixture.flag_values,
        }
    )
    for dependency in ("ActiveView", "FeatureManager"):
        first_row = first["flag_observations"]["dependencies"][dependency]
        second_row = second["flag_observations"]["dependencies"][dependency]
        assert first_row["status"] == second_row["status"] == "passed"
        assert first_row["type"] != second_row["type"]
    assert first["flags"] == second["flags"] == fixture.flag_values
    assert fixture.subject.app.activation_calls == []


def test_readiness_noop_set_flags_reacquires_viewport_and_checks_whole_vector(
    readiness,
):
    fixture = readiness
    fixture.subject.set_flags(dict(fixture.flag_values))
    assert Counter(fixture.reads) == Counter(
        {
            **{key: 2 for key in fixture.flag_values},
            "ActiveView": 3,
            "FeatureManager": 3,
        }
    )
    assert fixture.subject.receipt.counts["harness_flag_writes"] == 0
    assert fixture.subject.app.activation_calls == []
    assert fixture.context_calls == []
    assert (
        sum(
            left is fixture.drawing and right is fixture.drawing
            for left, right in fixture.subject.app.identity_calls
        )
        >= 3
    )


@pytest.mark.parametrize(
    "changed",
    [
        {"A_disable", "B_disable", "automatic", "graphics", "tree", "tree_window"},
        {"graphics"},
        {"A_disable", "tree_window"},
    ],
)
def test_readiness_set_flags_changes_only_requested_fields_and_reads_whole_vector(
    readiness, changed
):
    fixture = readiness
    fixture.accept_writes = True
    requested = {
        key: not value if key in changed else value
        for key, value in fixture.flag_values.items()
    }
    fixture.subject.set_flags(requested)
    assert fixture.flag_values == requested
    assert dict(fixture.writes) == {key: requested[key] for key in changed}
    assert len(fixture.writes) == len(changed)
    assert fixture.subject.receipt.counts["harness_flag_writes"] == len(changed)
    assert Counter(fixture.reads) == Counter(
        {
            **{key: 2 for key in requested},
            "ActiveView": 3,
            "FeatureManager": 3,
        }
    )
    assert fixture.subject.app.activation_calls == []


def test_readiness_set_flags_refuses_unconsumed_write_after_full_readback(readiness):
    fixture = readiness
    fixture.accept_writes = True
    fixture.ignored_writes.add("graphics")
    requested = {**fixture.flag_values, "graphics": not fixture.flag_values["graphics"]}
    with pytest.raises(probe.ProbeFailure) as caught:
        fixture.subject.set_flags(requested)
    assert caught.value.verdict is probe.Verdict.RESTORATION
    assert fixture.writes == [("graphics", requested["graphics"])]
    assert fixture.flag_values["graphics"] is not requested["graphics"]
    assert Counter(fixture.reads) == Counter(
        {
            **{key: 2 for key in requested},
            "ActiveView": 3,
            "FeatureManager": 3,
        }
    )


@pytest.mark.parametrize("invalid", ["missing", "extra", "nonbool"])
def test_readiness_set_flags_rejects_malformed_vector_before_writes(readiness, invalid):
    fixture = readiness
    requested = dict(fixture.flag_values)
    if invalid == "missing":
        del requested["graphics"]
    elif invalid == "extra":
        requested["foreign"] = True
    else:
        requested["graphics"] = 1
    with pytest.raises(probe.ProbeFailure):
        fixture.subject.set_flags(requested)
    assert fixture.writes == []
    assert Counter(fixture.reads) == Counter(
        (*fixture.flag_values, "ActiveView", "FeatureManager")
    )


def test_readiness_successful_actual_c00_keeps_existing_two_full_checkpoints(
    readiness, monkeypatch
):
    fixture = readiness
    monkeypatch.setattr(
        fixture.subject,
        "case_checkpoint",
        probe.NativeProbe.case_checkpoint.__get__(fixture.subject),
    )
    fixture.subject.run_case(
        probe.Case.CONSTRUCTION, fixture.subject._constructed_drawing_checkpoint
    )
    snapshot = readiness_snapshot(fixture.subject, full_count=2)
    assert_full_readiness_views(snapshot)
    assert fixture.subject.receipt.counts[probe.SnapshotKind.SOURCE] == 0
    assert [
        event["label"] for event in fixture.subject.receipt.data["observations"]
    ] == ["constructed-drawing", "case-candidate-complete"]
    assert (
        fixture.subject.receipt.data["cases"][probe.Case.CONSTRUCTION]["status"]
        is probe.Verdict.PASSED
    )
    assert (
        fixture.subject.receipt.data["fixture"]["initial_flags"]
        == snapshot["context"]["flags"]
    )
    assert fixture.subject.harness_flags == fixture.flag_values
    assert fixture.writes == []
    assert Counter(fixture.reads) == Counter(
        {
            **{key: 2 for key in fixture.flag_values},
            "ActiveView": 2,
            "FeatureManager": 2,
        }
    )


def test_readiness_emergency_report_keeps_identity_primary_after_later_failures(
    readiness, monkeypatch
):
    fixture = readiness
    primary = probe.ProbeFailure(
        probe.Verdict.IDENTITY, "identity closure failed first"
    )
    later = InertWriteOnlyError()
    reporting = OSError("persistent readiness report failure")

    def fail_identity():
        raise primary

    def fail_report():
        raise reporting

    monkeypatch.setattr(fixture.subject, "identity_controls", fail_identity)
    monkeypatch.setattr(fixture.subject.receipt, "checkpoint", fail_report)
    fixture.faults["tree_window"] = later
    with pytest.raises(probe.ProbeFailure) as caught:
        fixture.subject._constructed_drawing_checkpoint()
    assert caught.value is primary
    assert fixture.subject.receipt.primary is primary
    assert_full_readiness_views(readiness_snapshot(fixture.subject))
    emergency = json.loads(
        (fixture.subject.receipt.root / "emergency.json").read_text()
    )
    assert emergency["primary"]["type"] == "ProbeFailure"
    assert emergency["primary"]["message"] == str(primary)
    assert any(
        "constructed-drawing readback also failed" in note
        for note in emergency["primary"]["notes"]
    )
    assert emergency["reported_error"]["type"] == "InertWriteOnlyError"
    assert emergency["reported_error"]["message"] == str(later)
    assert emergency["reported_error"]["hresult"] == later.hresult
    assert tuple(emergency["reported_error"]["excepinfo"]) == later.excepinfo
    assert emergency["report_error"] == repr(reporting)
    messages = [
        row["message"] for row in fixture.subject.receipt.data["secondary_errors"]
    ]
    assert str(later) in messages
    assert str(reporting) in messages
    assert "initial_flags" not in fixture.subject.receipt.data["fixture"]
    assert not hasattr(fixture.subject, "harness_flags")


@pytest.mark.parametrize("value", [True, 1])
def test_sheet_scale_constructor_rejects_enabled_scale(sheet_scale_construction, value):
    fixture = sheet_scale_construction
    fixture.controls.scale_result = value
    with pytest.raises(probe.ProbeFailure, match="explicit view scale not consumed"):
        fixture.subject.create_drawing()
    assert len(fixture.created_views) == 1
    assert fixture.markers == []
    assert "fixture" not in fixture.subject.receipt.data


@pytest.mark.parametrize("value", [0.0, "0", None, -1, 2, SheetScaleInt(0)])
def test_sheet_scale_constructor_rejects_malformed_readback(
    sheet_scale_construction, value
):
    fixture = sheet_scale_construction
    fixture.controls.scale_result = value
    with pytest.raises(probe.ProbeFailure, match="UseSheetScale: expected") as caught:
        fixture.subject.create_drawing()
    assert caught.value.verdict is probe.Verdict.CONSTRUCTION
    assert len(fixture.created_views) == 1
    assert fixture.markers == []
    assert "fixture" not in fixture.subject.receipt.data


class TemplateString(str):
    pass


@pytest.fixture
def assembly_template(tmp_path, monkeypatch):
    template = tmp_path / "explicit.ASMDOT"
    content = b"the worker-visible explicit assembly template"
    template.write_bytes(content)
    identity = {
        "path": str(template),
        "size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    monkeypatch.setattr(probe, "ASSEMBLY_TEMPLATE_PATH", template)
    monkeypatch.setattr(probe, "ASSEMBLY_TEMPLATE_SIZE", identity["size"])
    monkeypatch.setattr(probe, "ASSEMBLY_TEMPLATE_SHA256", identity["sha256"])
    return identity


def assert_template_evidence(evidence, value, *, explicit=False):
    expected_value = (
        value
        if type(value) in (str, int, float, bool, type(None))
        and not (type(value) is float and not math.isfinite(value))
        else repr(value)
    )
    assert evidence["value"] == expected_value
    assert evidence["type"] == type(value).__name__
    assert evidence["repr"] == repr(value)
    predicates = {
        "is_string",
        "nonempty",
        "fully_qualified",
        "exists",
        "is_file",
        "assembly_suffix",
    }
    if explicit:
        predicates.update(("size_matches", "sha256_matches"))
    assert set(evidence["predicates"]) == predicates


@pytest.mark.parametrize("label", (probe.Document.N_AUTHOR, probe.Document.R_AUTHOR))
def test_explicit_assembly_template_records_identity_before_new_document(
    tmp_path, monkeypatch, assembly_template, label
):
    subject = OfflineProbe(tmp_path)
    template = assembly_template["path"]
    subject.app.preference_result = template
    model = OfflineModel("Authoring", 2, "", readonly=False)
    subject.app.new_results.append(model)
    new_document = subject.app.NewDocument

    def recorded_new_document(*arguments):
        recorded = json.loads((subject.receipt.root / "report.json").read_text())
        row = recorded["assembly_templates"][0]
        assert row["chosen"] == row["expected_identity"] == assembly_template
        assert all(
            value is True for value in row["explicit_input"]["predicates"].values()
        )
        return new_document(*arguments)

    monkeypatch.setattr(subject.app, "NewDocument", recorded_new_document)
    assert subject.new_assembly(label) is model

    assert subject.app.preference_calls == [9]
    assert subject.app.new_calls == [(template, 0, 0.0, 0.0)]
    assert tuple(type(value) for value in subject.app.new_calls[0]) == (
        str,
        int,
        float,
        float,
    )
    (row,) = subject.receipt.data["assembly_templates"]
    assert row["document"] is label
    assert_template_evidence(row["preference"], template)
    assert_template_evidence(row["explicit_input"], template, explicit=True)
    assert all(value is True for value in row["preference"]["predicates"].values())
    assert row["file_identity"] == row["chosen"] == assembly_template


@pytest.mark.parametrize(
    "value",
    (
        None,
        False,
        2,
        math.inf,
        -math.inf,
        math.nan,
        Path("assembly.asmdot"),
        TemplateString("x"),
    ),
)
def test_nonexact_string_template_preference_is_diagnostic_not_creation_input(
    tmp_path, assembly_template, value
):
    subject = OfflineProbe(tmp_path)
    subject.app.preference_result = value
    model = OfflineModel("Authoring", 2, "", readonly=False)
    subject.app.new_results.append(model)
    assert subject.new_assembly(probe.Document.N_AUTHOR) is model
    (row,) = subject.receipt.data["assembly_templates"]
    assert_template_evidence(row["preference"], value)
    assert row["preference"]["predicates"] == {
        "is_string": False,
        "nonempty": None,
        "fully_qualified": None,
        "exists": None,
        "is_file": None,
        "assembly_suffix": None,
    }
    assert (
        row["expected_identity"]
        == row["file_identity"]
        == row["chosen"]
        == (assembly_template)
    )
    assert all(value is True for value in row["explicit_input"]["predicates"].values())
    assert subject.app.new_calls == [(assembly_template["path"], 0, 0.0, 0.0)]
    assert subject.app.preference_calls == [9]
    persisted = json.loads((subject.receipt.root / "report.json").read_text())
    assert persisted["assembly_templates"][0]["preference"] == row["preference"]


@pytest.mark.parametrize("origin", ("preference", "explicit_input"))
@pytest.mark.parametrize(
    ("fault", "failed"),
    (
        ("empty", {"nonempty"}),
        ("relative", {"fully_qualified"}),
        ("missing", {"exists", "is_file"}),
        ("directory", {"is_file"}),
        ("suffix", {"assembly_suffix"}),
    ),
)
def test_template_path_predicates_gate_only_explicit_creation_input(
    tmp_path, monkeypatch, assembly_template, origin, fault, failed
):
    subject = OfflineProbe(tmp_path)
    monkeypatch.chdir(tmp_path)
    directory = tmp_path / "directory.asmdot"
    directory.mkdir()
    wrong_suffix = tmp_path / "existing.prtdot"
    wrong_suffix.write_bytes(Path(assembly_template["path"]).read_bytes())
    value = {
        "empty": "",
        "relative": subject.app.template.name,
        "missing": str(tmp_path / "missing.asmdot"),
        "directory": str(directory),
        "suffix": str(wrong_suffix),
    }[fault]
    if origin == "preference":
        subject.app.preference_result = value
        model = OfflineModel("Authoring", 2, "", readonly=False)
        subject.app.new_results.append(model)
        assert subject.new_assembly(probe.Document.N_AUTHOR) is model
    else:
        monkeypatch.setattr(probe, "ASSEMBLY_TEMPLATE_PATH", value)
        with pytest.raises(probe.ProbeFailure) as caught:
            subject.new_assembly(probe.Document.N_AUTHOR)
        assert caught.value.verdict is probe.Verdict.CONSTRUCTION

    (row,) = subject.receipt.data["assembly_templates"]
    assert_template_evidence(row[origin], value, explicit=origin == "explicit_input")
    predicates = row[origin]["predicates"]
    assert {name for name, passed in predicates.items() if passed is False} == failed
    if fault in ("relative", "directory", "suffix"):
        assert predicates["exists"] is True
    if fault in ("relative", "suffix"):
        assert predicates["is_file"] is True
    if origin == "preference":
        assert (
            row["expected_identity"]
            == row["file_identity"]
            == row["chosen"]
            == (assembly_template)
        )
        assert all(
            passed is True for passed in row["explicit_input"]["predicates"].values()
        )
        assert subject.app.new_calls == [(assembly_template["path"], 0, 0.0, 0.0)]
    else:
        assert_template_evidence(row["preference"], subject.app.preference_result)
        assert row["expected_identity"] == dict(assembly_template, path=value)
        message = str(caught.value)
        refused = {
            name.strip()
            for name in message.removeprefix(
                "explicit assembly template refused: "
            ).split(",")
        }
        assert failed <= refused <= set(predicates)
        assert not refused.intersection(
            name for name, passed in predicates.items() if passed is True
        )
        assert "missing" not in message.lower()
        if fault == "suffix":
            assert row["file_identity"] == dict(
                assembly_template, path=str(wrong_suffix)
            )
        else:
            assert "file_identity" not in row
        assert "chosen" not in row
        assert not subject.app.new_calls
        assert not subject.acquisitions and not subject.documents
    assert subject.app.preference_calls == [9]
    persisted = json.loads((subject.receipt.root / "report.json").read_text())
    assert persisted["assembly_templates"] == [row]


@pytest.mark.parametrize(
    ("predicate", "constant", "field", "wrong"),
    (
        ("size_matches", "ASSEMBLY_TEMPLATE_SIZE", "size", 0),
        ("sha256_matches", "ASSEMBLY_TEMPLATE_SHA256", "sha256", "0" * 64),
    ),
)
def test_explicit_template_identity_mismatch_is_recorded_before_refusal(
    tmp_path, monkeypatch, assembly_template, predicate, constant, field, wrong
):
    subject = OfflineProbe(tmp_path)
    monkeypatch.setattr(probe, constant, wrong)

    with pytest.raises(probe.ProbeFailure, match=predicate) as caught:
        subject.new_assembly(probe.Document.N_AUTHOR)

    assert caught.value.verdict is probe.Verdict.CONSTRUCTION
    (row,) = subject.receipt.data["assembly_templates"]
    assert_template_evidence(
        row["explicit_input"], assembly_template["path"], explicit=True
    )
    assert {
        name
        for name, passed in row["explicit_input"]["predicates"].items()
        if passed is not True
    } == {predicate}
    assert row["expected_identity"] == {**assembly_template, field: wrong}
    assert row["file_identity"] == assembly_template
    assert "chosen" not in row
    assert not subject.app.new_calls
    assert not subject.acquisitions and not subject.documents
    assert subject.app.preference_calls == [9]
    persisted = json.loads((subject.receipt.root / "report.json").read_text())
    assert persisted["assembly_templates"] == [row]


def test_template_preference_exception_preserves_primary_without_acquisition(
    tmp_path, assembly_template
):
    subject = OfflineProbe(tmp_path)
    original = OSError("native template preference read failed")
    subject.app.preference_error = original
    with pytest.raises(OSError) as caught:
        subject.new_assembly(probe.Document.N_AUTHOR)
    assert caught.value is original
    assert subject.receipt.primary is original
    assert subject.app.preference_calls == [9]
    assert not subject.app.new_calls and not subject.acquisitions
    assert not subject.receipt.data.get("unresolved_acquisitions")
    (row,) = subject.receipt.data["assembly_templates"]
    assert row["preference"]["status"] == "error"
    assert row["preference"]["error"]["type"] == "OSError"
    assert row["preference"]["error"]["message"] == str(original)
    assert row["expected_identity"] == assembly_template
    assert "chosen" not in row and "file_identity" not in row
    persisted = json.loads((subject.receipt.root / "report.json").read_text())
    assert persisted["assembly_templates"] == [row]
    assert persisted["primary_error"]["message"] == str(original)


def capture_and_cleanup_failure(subject, action):
    """Exercise actual run/case/stage and owned cleanup, retaining the first error."""
    subject.construction_action = action
    with pytest.raises(BaseException) as caught:
        subject.run()
    original = caught.value
    subject.mode = probe.RunMode.CLEANUP
    try:
        with subject.stage_scope(probe.Stage.CLEANUP):
            subject.cleanup()
    except BaseException as cleanup_error:
        original.add_note(
            f"offline exercised owned cleanup also failed: {cleanup_error!r}"
        )
        subject.receipt.failure(cleanup_error, secondary=True)
    assert subject.receipt.primary is original
    assert subject.receipt.data["handoff_allowed"] is False
    assert all(
        row["status"] is probe.Verdict.NOT_EXECUTED
        for case, row in subject.receipt.data["cases"].items()
        if case is not probe.Case.CONSTRUCTION
    )
    return original


def test_non_null_open_warning_is_owned_before_rejection_and_discarded_once(tmp_path):
    subject = OfflineProbe(tmp_path)
    model = OfflineModel("P", 1, subject.paths[probe.Document.P])
    subject.app.open_results.append((model, 0, 4))
    original = capture_and_cleanup_failure(
        subject, lambda: subject.open_source(probe.Document.P)
    )
    assert isinstance(original, probe.ProbeFailure)
    assert "errors/warnings" in str(original)
    assert subject.app.closed == [model]
    assert not subject.acquisitions and not subject.documents
    acquired = next(
        row for row in subject.receipt.data["ledger"] if row["event"] == "acquired"
    )
    assert acquired["state"] is probe.AcquisitionState.PENDING
    assert not any(row["event"] == "claim" for row in subject.receipt.data["ledger"])


@pytest.mark.parametrize("failure", ["warning", "kind", "path", "readonly"])
def test_known_p_and_rejected_q_both_close_without_write_admitting_q(tmp_path, failure):
    subject = OfflineProbe(tmp_path)
    p = OfflineModel("P", 1, subject.paths[probe.Document.P])
    q = OfflineModel(
        "Q",
        2 if failure == "kind" else 1,
        tmp_path / "unexpected.sldprt"
        if failure == "path"
        else subject.paths[probe.Document.Q],
        readonly=failure != "readonly",
    )
    subject.app.open_results.extend(((p, 0, 0), (q, 0, int(failure == "warning"))))
    captured = {}

    def action():
        subject.open_source(probe.Document.P)
        assert subject.model(probe.Document.P) is p
        try:
            subject.open_source(probe.Document.Q)
        except BaseException as error:
            captured["original"] = error
            assert (
                subject.acquisitions[probe.Document.Q].state
                is probe.AcquisitionState.PENDING
            )
            assert probe.Document.Q not in subject.documents
            with pytest.raises(probe.ProbeFailure, match="not admitted"):
                subject.model(probe.Document.Q)
            with pytest.raises(probe.ProbeFailure, match="not admitted"):
                subject.activate(probe.Document.Q)
            raise

    original = capture_and_cleanup_failure(subject, action)
    assert original is captured["original"]
    assert subject.app.closed == [q, p]
    assert not subject.app.models
    assert not subject.acquisitions and not subject.documents
    expected = (
        probe.Verdict.PRESERVATION
        if failure == "readonly"
        else probe.Verdict.CONSTRUCTION
    )
    assert subject.receipt.data["cases"][probe.Case.CONSTRUCTION]["status"] is expected
    assert (
        subject.receipt.data["stages"][probe.Stage.CONSTRUCTION]["status"] is expected
    )


@pytest.mark.parametrize("failure", ["kind", "path"])
def test_new_document_admission_failure_retains_owned_unadmitted_model(
    tmp_path, assembly_template, failure
):
    subject = OfflineProbe(tmp_path)
    model = OfflineModel(
        "AuthoringN",
        3 if failure == "kind" else 2,
        "" if failure == "kind" else tmp_path / "unexpected.sldasm",
    )
    subject.app.new_results.append(model)
    original = capture_and_cleanup_failure(
        subject, lambda: subject.new_assembly(probe.Document.N_AUTHOR)
    )
    assert isinstance(original, probe.ProbeFailure)
    assert original.verdict is probe.Verdict.CONSTRUCTION
    assert subject.app.closed == [model]
    assert not subject.documents and not subject.acquisitions


def test_saved_drawing_open_warning_is_owned_before_tuple_rejection(tmp_path):
    subject = OfflineProbe(tmp_path)
    path = subject.paths[probe.Document.DRAWING]
    path.write_bytes(b"offline saved drawing")
    model = OfflineModel("Drawing", 3, path, readonly=False)
    subject.app.open_results.append((model, 0, 8))
    original = capture_and_cleanup_failure(subject, subject.open_saved_drawing)
    assert isinstance(original, probe.ProbeFailure)
    assert "errors/warnings" in str(original)
    assert subject.app.closed == [model]
    assert subject.receipt.counts["drawing_reopen"] == 0


def test_foreign_hidden_model_refuses_every_close_and_preserves_owned_models(tmp_path):
    subject = OfflineProbe(tmp_path)
    p = OfflineModel("P", 1, subject.paths[probe.Document.P])
    q = OfflineModel("Q", 1, subject.paths[probe.Document.Q])
    foreign = OfflineModel("Foreign", 1, tmp_path / "foreign.sldprt")
    foreign.hidden = True
    subject.app.open_results.extend(((p, 0, 0), (q, 0, 1)))

    def action():
        subject.open_source(probe.Document.P)
        try:
            subject.open_source(probe.Document.Q)
        finally:
            subject.app.models.append(foreign)

    original = capture_and_cleanup_failure(subject, action)
    assert isinstance(original, probe.ProbeFailure)
    assert "errors/warnings" in str(original)
    assert not subject.app.close_calls
    assert not subject.app.closed
    assert subject.app.models == [p, q, foreign]
    assert set(subject.acquisitions) == {probe.Document.P, probe.Document.Q}
    assert set(subject.receipt.data["cleanup"]["remaining_owned"]) == {
        probe.Document.P,
        probe.Document.Q,
    }
    assert any(row["event"] == "discard_held" for row in subject.receipt.data["ledger"])
    assert foreign not in subject.app.closed
    assert subject.receipt.data["cleanup"]["status"] is probe.Verdict.RESTORATION


def test_foreign_ambiguous_title_is_not_used_as_a_close_target(tmp_path):
    subject = OfflineProbe(tmp_path)
    p = OfflineModel("P", 1, subject.paths[probe.Document.P])
    foreign = OfflineModel("p", 1, tmp_path / "foreign.sldprt")

    def action():
        subject.app.open_results.append((p, 0, 0))
        subject.open_source(probe.Document.P)
        subject.app.models.append(foreign)
        subject.inventory()

    original = capture_and_cleanup_failure(subject, action)
    assert isinstance(original, probe.ProbeFailure)
    assert not subject.app.closed
    assert subject.app.models == [p, foreign]
    assert subject.receipt.data["cleanup"]["errors"]


def test_preexisting_foreign_model_is_not_acquired_or_closed(tmp_path):
    subject = OfflineProbe(tmp_path)
    foreign = OfflineModel("Foreign", 1, tmp_path / "foreign.sldprt")
    subject.app.models.append(foreign)
    original = capture_and_cleanup_failure(
        subject, lambda: subject.open_source(probe.Document.P)
    )
    assert isinstance(original, probe.ProbeFailure)
    assert "unowned" in str(original)
    assert not subject.app.closed
    assert subject.app.models == [foreign]
    assert not subject.acquisitions


def test_positive_ownership_survives_title_reader_failure_without_write_admission(
    tmp_path,
):
    subject = OfflineProbe(tmp_path)
    model = OfflineModel("P", 1, subject.paths[probe.Document.P])
    original = OSError("native title reader failed")
    model.title_error = original
    subject.app.open_results.append((model, 0, 0))
    propagated = capture_and_cleanup_failure(
        subject, lambda: subject.open_source(probe.Document.P)
    )
    assert propagated is original
    assert subject.app.closed == [model]
    assert not any(row["event"] == "claim" for row in subject.receipt.data["ledger"])


def test_unresolved_identity_is_recorded_and_never_adopted_for_use_or_close(tmp_path):
    subject = OfflineProbe(tmp_path)
    model = OfflineModel("P", 1, subject.paths[probe.Document.P])
    model.unsupported_identity = True
    subject.app.open_results.append((model, 0, 0))
    original = capture_and_cleanup_failure(
        subject, lambda: subject.open_source(probe.Document.P)
    )
    assert isinstance(original, probe.ProbeFailure)
    assert original.verdict is probe.Verdict.IDENTITY
    assert (
        subject.acquisitions[probe.Document.P].state
        is probe.AcquisitionState.UNRESOLVED
    )
    assert subject.app.models == [model]
    assert not subject.app.closed and not subject.documents
    assert any(
        row.get("state") is probe.AcquisitionState.UNRESOLVED and "error" in row
        for row in subject.receipt.data["ledger"]
    )


def test_native_acquisition_exception_records_uncertainty_and_refuses_all_closes(
    tmp_path,
):
    subject = OfflineProbe(tmp_path)
    p = OfflineModel("P", 1, subject.paths[probe.Document.P])
    unreturned = OfflineModel("Unreturned", 1, subject.paths[probe.Document.Q])
    unreturned.hidden = True
    original = OSError("native open raised after opening an unreturned document")
    unreturned.open_error = original
    subject.app.open_results.extend(((p, 0, 0), (unreturned, 0, 0)))

    def action():
        subject.open_source(probe.Document.P)
        subject.open_source(probe.Document.Q)

    propagated = capture_and_cleanup_failure(subject, action)
    assert propagated is original
    assert not subject.app.close_calls
    assert not subject.app.closed
    assert subject.app.models == [p, unreturned]
    assert probe.Document.P in subject.acquisitions
    assert any(row["event"] == "discard_held" for row in subject.receipt.data["ledger"])
    assert probe.Document.Q not in subject.acquisitions
    assert (
        subject.receipt.data["unresolved_acquisitions"][0]["document"]
        is probe.Document.Q
    )


def fail_case_final_checkpoint_once(subject, monkeypatch, error):
    checkpoint = subject.receipt.checkpoint
    failed = []

    def injecting_checkpoint():
        row = subject.receipt.data["cases"][subject.receipt.case]
        if "operation_counts" in row and not failed:
            failed.append(error)
            raise error
        checkpoint()

    monkeypatch.setattr(subject.receipt, "checkpoint", injecting_checkpoint)


def invoke_offline_entry(subject, monkeypatch, reporting):
    """Actual entry/error/cleanup path, with every external port isolated."""

    def factory(adapter, root, receipt):
        assert root == subject.root
        subject.receipt = receipt
        fail_case_final_checkpoint_once(subject, monkeypatch, reporting)
        return subject

    monkeypatch.setattr(
        probe, "__file__", str(subject.root / "cad/scripts/offline_probe.py")
    )
    monkeypatch.setattr(
        probe, "source_identity", lambda root: {"offline_boundary_only": True}
    )
    monkeypatch.setattr(probe, "NativeProbe", factory)
    asyncio.run(probe.run_bulk_visibility_probe(subject.adapter))


def test_case_final_reporting_failure_preserves_original_object_cause_and_classification(
    tmp_path, monkeypatch
):
    subject = OfflineProbe(tmp_path)
    original = probe.ProbeFailure(
        probe.Verdict.PLURAL, "second selected object not consumed"
    )
    cause = ValueError("native control cause")
    reporting = OSError("final report failed")

    def action():
        raise original from cause

    subject.construction_action = action
    with pytest.raises(probe.ProbeFailure) as caught:
        invoke_offline_entry(subject, monkeypatch, reporting)
    assert caught.value is original
    assert caught.value.__cause__ is cause
    assert subject.receipt.primary is original
    assert (
        subject.receipt.data["cases"][probe.Case.CONSTRUCTION]["status"]
        is probe.Verdict.PLURAL
    )
    assert (
        subject.receipt.data["stages"][probe.Stage.CONSTRUCTION]["status"]
        is probe.Verdict.PLURAL
    )
    assert subject.receipt.data["probe_controls_status"] is probe.Controls.FAILED
    assert subject.receipt.data["handoff_allowed"] is False
    assert any("final checkpoint" in note for note in original.__notes__)
    assert any(
        row["message"] == str(reporting)
        for row in subject.receipt.data["secondary_errors"]
    )
    assert subject.receipt.data["cleanup"]["status"] is probe.Verdict.PASSED
    data = json.loads((subject.receipt.root / "report.json").read_text())
    assert "raise original from cause" in data["primary_error"]["traceback"]
    assert data["primary_error"]["type"] == "ProbeFailure"
    assert data["primary_error"]["notes"]


def test_case_final_reporting_failure_is_primary_when_no_earlier_failure(
    tmp_path, monkeypatch
):
    subject = OfflineProbe(tmp_path)
    reporting = OSError("only final checkpoint failed")
    with pytest.raises(OSError) as caught:
        invoke_offline_entry(subject, monkeypatch, reporting)
    assert caught.value is reporting
    assert subject.receipt.primary is reporting
    assert (
        subject.receipt.data["cases"][probe.Case.CONSTRUCTION]["status"]
        is probe.Verdict.CONSTRUCTION
    )
    assert (
        subject.receipt.data["stages"][probe.Stage.CONSTRUCTION]["status"]
        is probe.Verdict.CONSTRUCTION
    )
    assert subject.receipt.data["probe_controls_status"] is probe.Controls.UNSUPPORTED
    assert subject.receipt.data["handoff_allowed"] is False
    assert not subject.receipt.data["secondary_errors"]


@pytest.mark.parametrize("removed", (False, True))
def test_owned_discard_failure_is_not_automatically_retried_or_write_admitted(
    tmp_path, monkeypatch, removed
):
    subject = OfflineProbe(tmp_path)
    model = OfflineModel("P", 1, subject.paths[probe.Document.P])
    subject.app.open_results.append((model, 0, 0))
    subject.open_source(probe.Document.P)
    original = OSError("native discard failed")
    if removed:
        close = subject.app.CloseDoc

        def close_then_raise(title):
            close(title)
            raise original

        monkeypatch.setattr(subject.app, "CloseDoc", close_then_raise)
    else:
        subject.app.close_error = original
    with pytest.raises(OSError) as first:
        subject.close(probe.Document.P)
    assert first.value is original
    with pytest.raises(probe.ProbeFailure):
        subject.close(probe.Document.P)
    with pytest.raises(probe.ProbeFailure, match="not admitted"):
        subject.model(probe.Document.P)
    assert subject.app.closed == [model]
    assert subject.app.models == ([] if removed else [model])
    assert not model.disconnected_accesses
    assert subject.app.close_calls == ["P"]
    assert subject.acquisitions[probe.Document.P].native is None
    assert (
        subject.acquisitions[probe.Document.P].state
        is probe.AcquisitionState.DISCARD_ATTEMPTED
    )
    assert subject.receipt.data["handoff_allowed"] is False


def admit_offline_drawing(subject, *, saved=False):
    path = subject.paths[probe.Document.DRAWING] if saved else ""
    drawing = OfflineDrawing(path)
    with subject.acquiring(probe.Document.DRAWING) as before:
        subject.app.models.append(drawing)
        subject.app.ActiveDoc = drawing
        subject.acquired(probe.Document.DRAWING, drawing, before)
        subject.claim(probe.Document.DRAWING, 3, path if saved else None)
    return drawing


def title_refreshes(subject):
    return [
        row for row in subject.receipt.data["ledger"] if row["event"] == "title_refresh"
    ]


def activation_receipt(subject):
    return next(
        row
        for row in reversed(subject.receipt.data["ledger"])
        if row["event"] == "activation"
    )


@pytest.mark.parametrize("saved", (False, True))
@pytest.mark.parametrize("opaque", (False, True))
def test_drawing_title_refresh_activation_then_second_change_cleanup(
    tmp_path, saved, opaque
):
    subject = OfflineProbe(tmp_path)
    drawing = admit_offline_drawing(subject, saved=saved)
    owned = subject.documents[probe.Document.DRAWING]
    admission = [
        dict(row)
        for row in subject.receipt.data["ledger"]
        if row["event"] in ("acquired", "claim")
    ]
    generation, native, path, kind = (
        owned.generation,
        owned.native,
        owned.path,
        owned.kind,
    )
    drawing.GetCurrentSheet().SetName(probe.ViewId.A)
    assert drawing.ActivateSheet(probe.ViewId.B) is True
    if opaque:
        drawing.title = "Opaque activation hint | unrelated to filename and sheet"
    fresh = drawing.title

    assert subject.activate(probe.Document.DRAWING) is drawing

    assert fresh != "Draw - Sheet1"
    assert subject.app.activation_calls == [(fresh, False, 2, 0)]
    assert owned.title == fresh and owned.native is native
    assert owned.path == path and owned.kind == kind == 3
    assert owned.generation == generation
    assert owned.state is probe.AcquisitionState.ADMITTED
    event = activation_receipt(subject)
    assert event["cached_title"] == "Draw - Sheet1"
    assert event["validated_title"] == fresh
    assert event["arguments"] == [fresh, False, 2, 0]
    assert event["pre_active"]["state"] is probe.ActiveObservation.OWNED
    assert event["pre_active"]["documents"] == [probe.Document.DRAWING]
    assert event["result_type"] == "tuple" and event["result_length"] == 2
    assert event["result_repr"] == repr((drawing, 0))
    assert event["component_types"] == ["OfflineDrawing", "int"]
    assert event["status"] == 0 and event["returned_model_null"] is False
    assert event["returned_native_is_same"] == 1
    assert event["post_active"]["native_is_same"] == 1
    assert event["state"] is probe.ActivationState.PASSED
    subject.inventory()
    assert len(title_refreshes(subject)) == 1
    assert admission == [
        row
        for row in subject.receipt.data["ledger"]
        if row["event"] in ("acquired", "claim")
    ]
    assert drawing.ActivateSheet(probe.ViewId.A) is True
    if opaque:
        drawing.title = "Another opaque hint for final owned cleanup"
    latest = drawing.title

    with subject.stage_scope(probe.Stage.CLEANUP):
        subject.cleanup()

    assert subject.app.close_calls == [latest]
    assert not subject.app.models and not subject.acquisitions
    assert not subject.documents and subject.adapter.currentModel is None
    assert not drawing.disconnected_accesses
    assert not drawing.live and owned.native is None
    assert (owned.path, owned.kind, owned.generation) == (path, kind, generation)
    assert subject.receipt.data["cleanup"]["status"] is probe.Verdict.PASSED
    assert admission == [
        row
        for row in subject.receipt.data["ledger"]
        if row["event"] in ("acquired", "claim")
    ]
    refreshes = title_refreshes(subject)
    assert [(row["cached_title"], row["fresh_title"]) for row in refreshes] == [
        ("Draw - Sheet1", fresh),
        (fresh, latest),
    ]
    assert all(
        row["native_is_same"] == 1
        and row["kind"] == kind
        and row["path"] == (str(path) if saved else "")
        and row["generation"] == generation
        for row in refreshes
    )
    persisted = json.loads((subject.receipt.root / "report.json").read_text())
    assert persisted["cleanup"]["status"] == "passed"
    assert any(row["event"] == "activation" for row in persisted["ledger"])


@pytest.mark.parametrize("saved", (False, True))
@pytest.mark.parametrize("opaque", (False, True))
def test_direct_discard_refreshes_latest_drawing_title(tmp_path, saved, opaque):
    subject = OfflineProbe(tmp_path)
    drawing = admit_offline_drawing(subject, saved=saved)
    owned = subject.documents[probe.Document.DRAWING]
    admitted = (owned.path, owned.kind, owned.generation)
    drawing.ActivateSheet(probe.ViewId.A)
    if opaque:
        drawing.title = "Opaque direct-discard UI hint"
    latest = drawing.title

    subject.close(probe.Document.DRAWING)

    assert subject.app.close_calls == [latest]
    assert not subject.app.activation_calls and not subject.acquisitions
    assert not drawing.disconnected_accesses
    assert not drawing.live and owned.native is None
    assert (owned.path, owned.kind, owned.generation) == admitted
    assert title_refreshes(subject)[0]["context"] == "discard"
    attempt = next(
        row
        for row in subject.receipt.data["ledger"]
        if row["event"] == "discard_attempt"
    )
    frozen = attempt["preclose_inventory"][probe.Document.DRAWING]
    assert frozen == {
        "title": latest,
        "path": str(admitted[0]) if saved else "",
        "kind": 3,
        "generation": admitted[2],
        "state": probe.AcquisitionState.ADMITTED,
    }


@pytest.mark.parametrize("saved", (False, True))
@pytest.mark.parametrize(
    "consumer", ("ownership_inventory", "inventory", "discard_inventory")
)
def test_actual_inventory_refreshes_only_authenticated_drawing_hint(
    tmp_path, saved, consumer
):
    subject = OfflineProbe(tmp_path)
    drawing = admit_offline_drawing(subject, saved=saved)
    owned = subject.documents[probe.Document.DRAWING]
    admitted = (owned.native, owned.path, owned.kind, owned.generation, owned.state)
    admission = [
        dict(row)
        for row in subject.receipt.data["ledger"]
        if row["event"] in ("acquired", "claim")
    ]
    drawing.title = "Opaque inventory UI hint :: not a filename convention"

    inventory = getattr(subject, consumer)()

    assert set(inventory) == {probe.Document.DRAWING}
    assert owned.title == drawing.title
    assert (
        owned.native,
        owned.path,
        owned.kind,
        owned.generation,
        owned.state,
    ) == admitted
    assert subject.documents[probe.Document.DRAWING] is owned
    assert subject.acquisitions[probe.Document.DRAWING] is owned
    assert admission == [
        row
        for row in subject.receipt.data["ledger"]
        if row["event"] in ("acquired", "claim")
    ]
    (refresh,) = title_refreshes(subject)
    assert refresh == {
        "event": "title_refresh",
        "context": "discard" if consumer == "discard_inventory" else "inventory",
        "document": probe.Document.DRAWING,
        "generation": admitted[3],
        "cached_title": "Draw - Sheet1",
        "fresh_title": drawing.title,
        "native_is_same": 1,
        "kind": 3,
        "path": str(admitted[1]) if saved else "",
    }
    assert not subject.app.activation_calls and not subject.app.close_calls
    assert not drawing.disconnected_accesses


@pytest.mark.parametrize("active", ("null", "other_owned", "foreign"))
def test_activation_records_pre_active_without_requiring_target_already_active(
    tmp_path, active
):
    subject = OfflineProbe(tmp_path)
    p = OfflineModel("P", 1, subject.paths[probe.Document.P])
    subject.app.open_results.append((p, 0, 0))
    subject.open_source(probe.Document.P)
    if active == "other_owned":
        q = OfflineModel("Q", 1, subject.paths[probe.Document.Q])
        subject.app.open_results.append((q, 0, 0))
        subject.open_source(probe.Document.Q)
    else:
        subject.app.ActiveDoc = (
            None if active == "null" else OfflineModel("Foreign", 1, "")
        )

    assert subject.activate(probe.Document.P) is p

    assert subject.app.activation_calls == [("P", False, 2, 0)]
    event = activation_receipt(subject)
    assert (
        event["pre_active"]["state"]
        == {
            "null": "null",
            "other_owned": "owned",
            "foreign": "foreign_or_ambiguous",
        }[active]
    )
    assert event["post_active"]["native_is_same"] == 1
    assert not title_refreshes(subject)


@pytest.mark.parametrize("saved", (False, True))
def test_unchanged_drawing_title_adds_no_refresh_event(tmp_path, saved):
    subject = OfflineProbe(tmp_path)
    drawing = admit_offline_drawing(subject, saved=saved)
    subject.activate(probe.Document.DRAWING)
    subject.close(probe.Document.DRAWING)
    assert subject.app.activation_calls == [("Draw - Sheet1", False, 2, 0)]
    assert subject.app.close_calls == ["Draw - Sheet1"]
    assert not title_refreshes(subject) and not drawing.disconnected_accesses


@pytest.mark.parametrize(
    "consumer", ("ownership_inventory", "discard_inventory", "activate", "close")
)
@pytest.mark.parametrize(
    "saved,fault",
    [
        (saved, fault)
        for saved in (False, True)
        for fault in (
            "replacement_old",
            "replacement_new",
            "unsupported_identity",
            "disconnected_identity",
            "identity_error",
            "saved_path",
            "relative_path",
            "wrong_kind",
            "noninteger_kind",
            "empty_title",
            "nonstring_title",
            "nonstring_path",
            "title_error",
            "path_error",
            "kind_error",
        )
    ]
    + [(True, "cleared_path")],
)
def test_drawing_title_refresh_refuses_identity_or_metadata_faults_atomically(
    tmp_path, monkeypatch, consumer, saved, fault
):
    subject = OfflineProbe(tmp_path)
    drawing = admit_offline_drawing(subject, saved=saved)
    owned = subject.documents[probe.Document.DRAWING]
    admitted = (owned.title, owned.path, owned.kind, owned.generation, owned.native)
    drawing.title = "Opaque changed hint with a rejected identity or metadata"
    original = OSError(f"unreadable {fault}")
    original.hresult = -2147352567
    original.excepinfo = (61836, "inert native boundary", str(original), None, 0, 0)
    metadata_reads = []
    if fault.startswith("replacement"):
        replacement = OfflineDrawing(drawing.path)
        if fault == "replacement_new":
            replacement.title = drawing.title
        subject.app.models[:] = [replacement]
        subject.app.ActiveDoc = replacement
    elif fault == "unsupported_identity":
        drawing.unsupported_identity = True
    elif fault == "disconnected_identity":
        drawing.live = False
    elif fault == "identity_error":

        def identity_error(_left, _right):
            raise original

        monkeypatch.setattr(subject.app, "IsSame", identity_error)
    elif fault in ("saved_path", "relative_path"):
        drawing.path = str(tmp_path / "saved.slddrw") if fault == "saved_path" else "x"
    elif fault == "cleared_path":
        drawing.path = ""
    elif fault in ("wrong_kind", "noninteger_kind"):
        drawing.kind = 2 if fault == "wrong_kind" else 3.0
    elif fault in ("empty_title", "nonstring_title"):
        drawing.title = "" if fault == "empty_title" else None
    elif fault == "nonstring_path":
        drawing.path = None
    else:
        member = {
            "title_error": "GetTitle",
            "path_error": "GetPathName",
            "kind_error": "GetType",
        }[fault]

        def unreadable():
            raise original

        monkeypatch.setattr(drawing, member, unreadable)
    for model in {drawing, *subject.app.models}:
        for member in ("GetTitle", "GetPathName", "GetType"):
            getter = getattr(model, member)

            def observed_getter(getter=getter, member=member):
                metadata_reads.append(member)
                return getter()

            monkeypatch.setattr(model, member, observed_getter)

    with pytest.raises((probe.ProbeFailure, OSError, RuntimeError)) as caught:
        if consumer in ("activate", "close"):
            getattr(subject, consumer)(probe.Document.DRAWING)
        else:
            getattr(subject, consumer)()

    if fault.endswith("_error"):
        assert caught.value is original
        record = probe.error_record(caught.value)
        assert record["hresult"] == original.hresult
        assert record["excepinfo"] == original.excepinfo
    assert (
        owned.title,
        owned.path,
        owned.kind,
        owned.generation,
        owned.native,
    ) == admitted
    assert owned.state is probe.AcquisitionState.ADMITTED
    if fault.startswith("replacement") or fault in (
        "unsupported_identity",
        "disconnected_identity",
        "identity_error",
    ):
        assert metadata_reads == []
    else:
        assert metadata_reads == {
            "empty_title": ["GetTitle"],
            "nonstring_title": ["GetTitle"],
            "title_error": ["GetTitle"],
            "nonstring_path": ["GetTitle", "GetPathName"],
            "path_error": ["GetTitle", "GetPathName"],
        }.get(fault, ["GetTitle", "GetPathName", "GetType"])
    notes = probe.error_record(caught.value).get("notes", [])
    if fault in ("saved_path", "relative_path", "cleared_path", "wrong_kind"):
        context = (
            "activation"
            if consumer == "activate"
            else "discard"
            if consumer in ("discard_inventory", "close")
            else "inventory"
        )
        assert caught.value.verdict is (
            probe.Verdict.RESTORATION
            if consumer in ("discard_inventory", "close")
            else probe.Verdict.PRESERVATION
        )
        assert str(caught.value) == (
            f"owned {context} path/type changed: {probe.Document.DRAWING}"
        )
        assert notes == [
            f"owned metadata: context={context!r}; document={probe.Document.DRAWING!r}; "
            f"generation=1; state={probe.AcquisitionState.ADMITTED!r}; "
            f"native_is_same=1; expected_title={admitted[0]!r}; "
            f"fresh_title={drawing.title!r}; "
            f"expected_path={(str(admitted[1]) if saved else None)!r}; "
            f"fresh_path={drawing.path!r}; expected_kind=3; fresh_kind={drawing.kind!r}"
        ]
    else:
        assert not any(
            "owned metadata:" in note or "native_is_same=1" in note for note in notes
        )
    if consumer == "activate":
        assert activation_receipt(subject)["error"]["notes"] == notes
    elif consumer == "close":
        held = subject.receipt.data["ledger"][-1]
        assert held["event"] == "discard_held"
        assert held["remaining_acquisitions"] == [probe.Document.DRAWING]
        assert held["error"]["notes"] == notes
    assert not title_refreshes(subject)
    assert not subject.app.close_calls and not subject.app.activation_calls


@pytest.mark.parametrize("saved", (False, True))
@pytest.mark.parametrize("consumer", ("ownership_inventory", "discard_inventory"))
@pytest.mark.parametrize("reverse", (False, True))
@pytest.mark.parametrize(
    "fault",
    (
        "foreign",
        "foreign_same_title",
        "duplicate",
        "missing",
        "path",
        "collision",
        "part_title",
        "canonical_n_title",
        "canonical_r_title",
        "authoring_n_title",
        "authoring_r_title",
    ),
)
def test_late_inventory_failure_rolls_back_every_staged_title(
    tmp_path, monkeypatch, saved, consumer, reverse, fault
):
    subject = OfflineProbe(tmp_path)
    drawing = admit_offline_drawing(subject, saved=saved)
    p = OfflineModel("P", 1, subject.paths[probe.Document.P])
    subject.app.open_results.append((p, 0, 0))
    subject.open_source(probe.Document.P)
    immutable_label = {
        "part_title": probe.Document.P,
        "canonical_n_title": probe.Document.N,
        "canonical_r_title": probe.Document.R,
        "authoring_n_title": probe.Document.N_AUTHOR,
        "authoring_r_title": probe.Document.R_AUTHOR,
    }.get(fault)
    if immutable_label is not None and immutable_label is not probe.Document.P:
        path = (
            subject.paths[immutable_label]
            if immutable_label in (probe.Document.N, probe.Document.R)
            else None
        )
        assembly = OfflineModel(
            "Immutable assembly UI hint",
            2,
            path if path is not None else "",
            readonly=path is not None,
        )
        assembly.GetComponents = lambda _top_level_only: (p,)
        configuration = SimpleNamespace(
            Name="Default",
            GetDisplayStates=lambda: ("Display State-1",),
            GetDisplayStatesCount=lambda: 1,
            GetDisplayStateComponentVisibility=lambda *arguments: ((1,), (p,)),
        )
        assembly.GetActiveConfiguration = lambda: configuration
        assembly.GetConfigurationByName = lambda name: configuration
        monkeypatch.setattr(
            subject, "component_state", lambda component: {"path": "inert-P-1"}
        )
        with subject.acquiring(immutable_label) as before:
            subject.app.models.append(assembly)
            subject.app.ActiveDoc = assembly
            subject.acquired(immutable_label, assembly, before)
            subject.claim(immutable_label, 2, path)
    owned = subject.documents[probe.Document.DRAWING]
    drawing.title = "Opaque staged drawing hint pending whole-inventory validation"
    if fault in ("foreign", "foreign_same_title"):
        subject.app.models.append(
            OfflineModel(
                drawing.title if fault == "foreign_same_title" else "Foreign", 1, ""
            )
        )
    elif fault == "duplicate":
        subject.app.models.append(p)
    elif fault == "missing":
        subject.app.models.remove(p)
    elif fault == "path":
        p.path = str(tmp_path / "drift.sldprt")
    elif immutable_label is not None:
        subject.app.document(
            subject.documents[immutable_label].native
        ).title = "Changed immutable part or assembly UI hint"
    else:
        # Change the cached part title too, so its own immutable-title guard
        # passes and the whole-inventory fresh-name collision is decisive.
        p.title = drawing.title.swapcase()
        subject.documents[probe.Document.P].title = p.title
    if reverse:
        subject.app.models.reverse()
    admitted = {
        key: (
            owner.title,
            owner.path,
            owner.kind,
            owner.generation,
            owner.native,
            owner.state,
        )
        for key, owner in subject.acquisitions.items()
    }
    admission = [
        dict(row)
        for row in subject.receipt.data["ledger"]
        if row["event"] in ("acquired", "claim")
    ]
    metadata_reads = []
    for model in set(subject.app.models):
        for member in ("GetTitle", "GetPathName", "GetType"):
            getter = getattr(model, member)

            def observed_getter(model=model, member=member, getter=getter):
                metadata_reads.append((model, member))
                return getter()

            monkeypatch.setattr(model, member, observed_getter)
    identity_start = len(subject.app.identity_calls)

    with pytest.raises(probe.ProbeFailure) as caught:
        getattr(subject, consumer)()

    assert owned.title == "Draw - Sheet1"
    assert admitted == {
        key: (
            owner.title,
            owner.path,
            owner.kind,
            owner.generation,
            owner.native,
            owner.state,
        )
        for key, owner in subject.acquisitions.items()
    }
    assert admission == [
        row
        for row in subject.receipt.data["ledger"]
        if row["event"] in ("acquired", "claim")
    ]
    context = "discard" if consumer == "discard_inventory" else "inventory"
    assert caught.value.verdict is (
        probe.Verdict.RESTORATION
        if consumer == "discard_inventory"
        else probe.Verdict.PRESERVATION
    )
    notes = probe.error_record(caught.value)["notes"]
    if immutable_label is not None:
        prior = admitted[immutable_label]
        immutable = subject.app.document(prior[4])
        assert str(caught.value) == f"owned {context} title changed: {immutable_label}"
        assert notes == [
            f"owned metadata: context={context!r}; document={immutable_label!r}; "
            f"generation={prior[3]!r}; state={prior[5]!r}; native_is_same=1; "
            f"expected_title={prior[0]!r}; fresh_title={immutable.title!r}; "
            f"expected_path={(str(prior[1]) if prior[1] is not None else None)!r}; "
            f"fresh_path={immutable.path!r}; expected_kind={prior[2]!r}; "
            f"fresh_kind={immutable.kind!r}"
        ]
    elif fault == "collision":
        current_label, previous_label = (
            (probe.Document.DRAWING, probe.Document.P)
            if reverse
            else (probe.Document.P, probe.Document.DRAWING)
        )
        current = subject.app.document(admitted[current_label][4])
        previous = subject.app.document(admitted[previous_label][4])
        prefix = (
            f"owned title collision: context={context!r}; document={current_label!r}; "
            f"generation=1; native_is_same=1; fresh_title={current.title!r}; "
            f"fresh_path={current.path!r}; fresh_kind={current.kind!r}; "
            f"collision_key={current.title.casefold()!r}; "
        )
        if consumer == "ownership_inventory":
            suffix = f"known_casefold_titles={[previous.title.casefold()]!r}"
        else:
            conflict = {
                previous_label: {
                    "title": previous.title,
                    "path": previous.path,
                    "kind": previous.kind,
                    "generation": 1,
                    "state": probe.AcquisitionState.ADMITTED,
                }
            }
            suffix = f"conflicting_frozen={conflict!r}"
        assert notes == [prefix + suffix]
        assert len(subject.app.identity_calls) - identity_start == 4
        assert Counter(metadata_reads) == Counter(
            (model, member)
            for model in (drawing, p)
            for member in ("GetTitle", "GetPathName", "GetType")
        )
    elif fault in ("foreign", "foreign_same_title"):
        foreign = next(
            model for model in subject.app.models if model not in (drawing, p)
        )
        assert not any(model is foreign for model, member in metadata_reads)
        assert not any("native_is_same=1" in note for note in notes)
    assert not title_refreshes(subject)
    assert not subject.app.close_calls and not subject.app.activation_calls


@pytest.mark.parametrize("fault", ("title", "path", "kind", "identity"))
@pytest.mark.parametrize("reverse", (False, True))
def test_saved_drawing_survivor_keeps_strict_frozen_postclose_contract(
    tmp_path, monkeypatch, fault, reverse
):
    subject = OfflineProbe(tmp_path)
    p = OfflineModel("P", 1, subject.paths[probe.Document.P])
    q = OfflineModel("Q", 1, subject.paths[probe.Document.Q])
    subject.app.open_results.extend(((p, 0, 0), (q, 0, 0)))
    subject.open_source(probe.Document.P)
    drawing = admit_offline_drawing(subject, saved=True)
    subject.open_source(probe.Document.Q)
    owned = subject.documents[probe.Document.DRAWING]
    admitted = (owned.path, owned.kind, owned.generation)
    drawing.title = "Opaque authenticated hint frozen before CloseDoc"
    frozen_title = drawing.title
    subject.adapter.currentModel = q
    subject.view_handles[probe.ViewId.A] = object()
    subject.node_handles[probe.ViewId.A, probe.NodeId.P1] = object()
    if reverse:
        subject.app.models.reverse()
    close = subject.app.CloseDoc

    def changed_close(title):
        assert all(owner.native is None for owner in subject.acquisitions.values())
        close(title)
        if fault == "title":
            drawing.title = "Another opaque hint introduced inside close transaction"
        elif fault == "path":
            drawing.path = str(tmp_path / "moved-survivor.slddrw")
        elif fault == "kind":
            drawing.kind = 2
        else:
            replacement = OfflineDrawing(drawing.path)
            replacement.title = frozen_title
            subject.app.models[subject.app.models.index(drawing)] = replacement
        subject.app.ActiveDoc = p

    monkeypatch.setattr(subject.app, "CloseDoc", changed_close)
    with pytest.raises(probe.ProbeFailure) as caught:
        subject.close(probe.Document.Q)

    assert caught.value.verdict is probe.Verdict.RESTORATION
    assert str(caught.value) == (
        "post-close survivor changed pre-close owner identity"
        if fault == "identity"
        else "unexpected/ambiguous post-close survivor; no adoption permitted"
    )
    assert owned.title == frozen_title
    assert (owned.path, owned.kind, owned.generation) == admitted
    assert (
        set(subject.acquisitions)
        == set(subject.documents)
        == {
            probe.Document.P,
            probe.Document.Q,
            probe.Document.DRAWING,
        }
    )
    assert all(owner.native is None for owner in subject.acquisitions.values())
    assert subject.adapter.currentModel is None
    assert not subject.view_handles and not subject.node_handles
    assert subject.app.close_calls == ["Q"]
    assert not q.live
    assert not p.disconnected_accesses and not q.disconnected_accesses
    assert not drawing.disconnected_accesses
    (refresh,) = title_refreshes(subject)
    assert refresh["fresh_title"] == frozen_title and refresh["context"] == "discard"
    attempt = next(
        row
        for row in subject.receipt.data["ledger"]
        if row["event"] == "discard_attempt"
    )
    assert attempt["preclose_inventory"][probe.Document.DRAWING] == {
        "title": frozen_title,
        "path": str(admitted[0]),
        "kind": admitted[1],
        "generation": admitted[2],
        "state": probe.AcquisitionState.ADMITTED,
    }
    assert not [
        row for row in subject.receipt.data["ledger"] if row["event"] == "discard"
    ]
    for label in (probe.Document.DRAWING, probe.Document.Q, probe.Document.P):
        with pytest.raises(probe.ProbeFailure):
            subject.close(label)
    assert subject.app.close_calls == ["Q"] and title_refreshes(subject) == [refresh]


def test_saved_title_metadata_cleanup_failure_preserves_primary_and_held_owner(
    tmp_path,
):
    subject = OfflineProbe(tmp_path)
    primary = OSError("inert construction failure preceding saved cleanup drift")
    held = {}

    def action():
        drawing = admit_offline_drawing(subject, saved=True)
        held["drawing"] = drawing
        held["owner"] = subject.documents[probe.Document.DRAWING]
        drawing.title = "Exact opaque fresh hint observed by failed cleanup"
        drawing.path = str(tmp_path / "unexpected-saved-location.slddrw")
        raise primary

    assert capture_and_cleanup_failure(subject, action) is primary
    drawing, owned = held["drawing"], held["owner"]
    assert subject.receipt.primary is primary
    assert subject.receipt.data["primary_error"]["message"] == str(primary)
    assert subject.receipt.data["cleanup"]["status"] is probe.Verdict.RESTORATION
    assert subject.receipt.data["cleanup"]["remaining_owned"] == [
        probe.Document.DRAWING
    ]
    assert subject.acquisitions[probe.Document.DRAWING] is owned
    assert subject.documents[probe.Document.DRAWING] is owned
    assert owned.native is drawing and owned.title == "Draw - Sheet1"
    assert owned.path == subject.paths[probe.Document.DRAWING]
    assert owned.kind == 3 and owned.generation == 1
    assert owned.state is probe.AcquisitionState.ADMITTED
    assert not drawing.disconnected_accesses
    assert not title_refreshes(subject)
    assert not subject.app.activation_calls and not subject.app.close_calls
    (held_close,) = [
        row for row in subject.receipt.data["ledger"] if row["event"] == "discard_held"
    ]
    expected_note = (
        f"owned metadata: context='discard'; document={probe.Document.DRAWING!r}; "
        f"generation=1; state={probe.AcquisitionState.ADMITTED!r}; native_is_same=1; "
        f"expected_title='Draw - Sheet1'; fresh_title={drawing.title!r}; "
        f"expected_path={str(owned.path)!r}; fresh_path={drawing.path!r}; "
        f"expected_kind=3; fresh_kind=3"
    )
    assert held_close["error"]["notes"] == [expected_note]
    assert held_close["remaining_acquisitions"] == [probe.Document.DRAWING]
    assert any(
        expected_note in error["notes"]
        for error in subject.receipt.data["cleanup"]["errors"]
    )
    assert subject.receipt.data["secondary_errors"]


@pytest.mark.parametrize("saved", (False, True))
@pytest.mark.parametrize(
    "state",
    (
        probe.AcquisitionState.PENDING,
        probe.AcquisitionState.UNRESOLVED,
        probe.AcquisitionState.DISCARD_ATTEMPTED,
    ),
)
def test_nonadmitted_drawing_never_refreshes_or_activates(tmp_path, saved, state):
    subject = OfflineProbe(tmp_path)
    drawing = admit_offline_drawing(subject, saved=saved)
    owned = subject.documents.pop(probe.Document.DRAWING)
    owned.state = state
    drawing.ActivateSheet(probe.ViewId.A)
    if state is not probe.AcquisitionState.PENDING:
        owned.native = None
        drawing.live = False
    for operation in (
        subject.ownership_inventory,
        subject.discard_inventory,
        lambda: subject.activate(probe.Document.DRAWING),
        lambda: subject.close(probe.Document.DRAWING),
    ):
        with pytest.raises(probe.ProbeFailure):
            operation()
    assert owned.title == "Draw - Sheet1"
    assert not drawing.disconnected_accesses
    assert not title_refreshes(subject)
    assert not subject.app.close_calls and not subject.app.activation_calls


@pytest.mark.parametrize("saved", (False, True))
@pytest.mark.parametrize(
    "fault",
    (
        "null",
        "status",
        "boolean_status",
        "float_status",
        "malformed",
        "wrong_return",
        "wrong_active",
        "null_active",
        "call_error",
        "pre_error",
        "post_error",
    ),
)
def test_activation_failure_retains_partial_receipt_and_never_retries(
    tmp_path, monkeypatch, saved, fault
):
    subject = OfflineProbe(tmp_path)
    drawing = admit_offline_drawing(subject, saved=saved)
    drawing.ActivateSheet(probe.ViewId.A)
    original = OSError(f"activation {fault}")
    foreign = OfflineModel("Foreign", 1, "")
    activate = subject.app.ActivateDoc3
    active_get = type(subject.app).ActiveDoc.fget
    reads = []
    captured_result = []

    def active_read(app):
        reads.append("read")
        if fault == "pre_error" or fault == "post_error" and len(reads) == 2:
            raise original
        return active_get(app)

    def failing_activation(*args):
        result = activate(*args)
        if fault == "call_error":
            raise original
        if fault in ("wrong_active", "null_active"):
            subject.app.ActiveDoc = foreign if fault == "wrong_active" else None
        result = {
            "null": (None, 0),
            "status": (drawing, 1),
            "boolean_status": (drawing, False),
            "float_status": (drawing, 0.0),
            "malformed": [drawing, 0],
            "wrong_return": (foreign, 0),
        }.get(fault, result)
        captured_result.append(result)
        return result

    monkeypatch.setattr(
        OfflineApplication,
        "ActiveDoc",
        property(active_read, type(subject.app).ActiveDoc.fset),
    )
    monkeypatch.setattr(subject.app, "ActivateDoc3", failing_activation)

    with pytest.raises((probe.ProbeFailure, OSError)) as caught:
        subject.activate(probe.Document.DRAWING)

    if fault.endswith("_error"):
        assert caught.value is original
    event = activation_receipt(subject)
    assert event["state"] is probe.ActivationState.FAILED
    assert event["cached_title"] == "Draw - Sheet1"
    assert event["validated_title"] == "Draw - BulkTarget"
    assert event["error"]["message"] == str(caught.value)
    assert len(subject.app.activation_calls) == (0 if fault == "pre_error" else 1)
    assert not subject.app.close_calls
    assert subject.adapter.currentModel is None
    if captured_result:
        assert event["result_repr"] == repr(captured_result[0])
        assert event["result_type"] == type(captured_result[0]).__name__
    if fault == "pre_error":
        assert event["pre_active"]["state"] is probe.ActiveObservation.ERROR
    if fault == "post_error":
        assert event["post_active"]["state"] is probe.ActiveObservation.ERROR
    if fault in (
        "pre_error",
        "call_error",
        "null",
        "status",
        "boolean_status",
        "float_status",
        "malformed",
        "wrong_return",
    ):
        assert event["post_active"]["state"] is probe.ActiveObservation.NOT_OBSERVED


@pytest.mark.parametrize("saved", (False, True))
def test_activation_observation_identity_error_refuses_before_native_mutation(
    tmp_path, monkeypatch, saved
):
    subject = OfflineProbe(tmp_path)
    drawing = admit_offline_drawing(subject, saved=saved)
    drawing.ActivateSheet(probe.ViewId.A)
    foreign = OfflineModel("ForeignActive", 1, "")
    subject.app.ActiveDoc = foreign
    original = OSError("pre-active identity read failed")
    same = subject.same

    def unreadable_identity(left, right):
        if left is foreign:
            raise original
        return same(left, right)

    monkeypatch.setattr(subject, "same", unreadable_identity)
    with pytest.raises(OSError) as caught:
        subject.activate(probe.Document.DRAWING)
    assert caught.value is original
    assert not subject.app.activation_calls
    event = activation_receipt(subject)
    assert event["pre_active"]["state"] is probe.ActiveObservation.ERROR
    assert event["post_active"]["state"] is probe.ActiveObservation.NOT_OBSERVED
    assert event["error"]["message"] == str(original)


@pytest.mark.parametrize("saved", (False, True))
def test_activation_native_error_remains_primary_through_actual_owned_cleanup(
    tmp_path, monkeypatch, saved
):
    subject = OfflineProbe(tmp_path)
    drawing = admit_offline_drawing(subject, saved=saved)
    drawing.ActivateSheet(probe.ViewId.A)
    original = OSError("native activation threw")
    activate = subject.app.ActivateDoc3

    def throwing_activation(*args):
        activate(*args)
        raise original

    monkeypatch.setattr(subject.app, "ActivateDoc3", throwing_activation)
    assert (
        capture_and_cleanup_failure(
            subject, lambda: subject.activate(probe.Document.DRAWING)
        )
        is original
    )
    assert subject.receipt.primary is original
    assert subject.app.activation_calls == [("Draw - BulkTarget", False, 2, 0)]
    assert subject.app.close_calls == ["Draw - BulkTarget"]
    assert not drawing.disconnected_accesses
    assert subject.receipt.data["cleanup"]["status"] is probe.Verdict.PASSED
    persisted = json.loads((subject.receipt.root / "report.json").read_text())
    assert persisted["primary_error"]["message"] == str(original)
    event = next(row for row in persisted["ledger"] if row["event"] == "activation")
    assert event["failed_at"] == "calling" and event["state"] == "failed"
    assert event["post_active"]["state"] == "not_observed"


@pytest.mark.parametrize("saved", (False, True))
def test_closed_renamed_drawing_is_never_activated_or_closed_again(tmp_path, saved):
    subject = OfflineProbe(tmp_path)
    drawing = admit_offline_drawing(subject, saved=saved)
    drawing.ActivateSheet(probe.ViewId.A)
    subject.close(probe.Document.DRAWING)
    identity_count = len(subject.app.identity_calls)

    with pytest.raises(probe.ProbeFailure, match="not admitted"):
        subject.activate(probe.Document.DRAWING)
    subject.close(probe.Document.DRAWING)

    assert subject.app.close_calls == ["Draw - BulkTarget"]
    assert not subject.app.activation_calls
    assert len(subject.app.identity_calls) == identity_count
    assert not drawing.disconnected_accesses


@pytest.mark.parametrize("saved", (False, True))
def test_invalidated_admitted_drawing_refuses_before_activation_or_identity_calls(
    tmp_path, saved
):
    subject = OfflineProbe(tmp_path)
    drawing = admit_offline_drawing(subject, saved=saved)
    owned = subject.documents[probe.Document.DRAWING]
    owned.native = None
    drawing.live = False
    identity_count = len(subject.app.identity_calls)

    with pytest.raises(probe.ProbeFailure, match="handle invalidated"):
        subject.activate(probe.Document.DRAWING)
    with pytest.raises(probe.ProbeFailure, match="discard held"):
        subject.close(probe.Document.DRAWING)

    assert not subject.app.activation_calls and not subject.app.close_calls
    assert len(subject.app.identity_calls) == identity_count
    assert not drawing.disconnected_accesses
    assert owned.title == "Draw - Sheet1" and not title_refreshes(subject)
    assert activation_receipt(subject)["state"] is probe.ActivationState.FAILED


@pytest.mark.parametrize("label", (probe.Document.P, probe.Document.N_AUTHOR))
def test_part_and_assembly_activation_keep_existing_route_without_inventory_walk(
    tmp_path, monkeypatch, assembly_template, label
):
    subject = OfflineProbe(tmp_path)
    if label is probe.Document.P:
        model = OfflineModel("Part", 1, subject.paths[label])
        subject.app.open_results.append((model, 0, 0))
        subject.open_source(label)
    else:
        model = OfflineModel("Assembly", 2, "", readonly=False)
        subject.app.new_results.append(model)
        subject.new_assembly(label)

    def no_inventory():
        raise AssertionError("part/assembly activation added a full inventory walk")

    monkeypatch.setattr(subject.app, "GetDocuments", no_inventory)
    assert subject.activate(label) is model
    assert subject.app.activation_calls == [(model.title, False, 2, 0)]
    assert activation_receipt(subject)["state"] is probe.ActivationState.PASSED
    assert not title_refreshes(subject)


@pytest.mark.parametrize("consumer", ("ownership_inventory", "discard_inventory"))
@pytest.mark.parametrize(
    "label", tuple(key for key in probe.Document if key is not probe.Document.DRAWING)
)
def test_nondrawing_titles_remain_immutable(tmp_path, consumer, label):
    subject = OfflineProbe(tmp_path)
    # This isolates the admitted-owner metadata contract, not source geometry.
    kind = 1 if label in (probe.Document.P, probe.Document.Q) else 2
    path = (
        None
        if label in (probe.Document.N_AUTHOR, probe.Document.R_AUTHOR)
        else subject.paths[label]
    )
    model = OfflineModel("Original", kind, path if path is not None else "")
    owned = probe.OwnedDocument(
        model, "Original", path, kind, 1, probe.AcquisitionState.ADMITTED
    )
    subject.acquisitions[label] = subject.documents[label] = owned
    subject.app.models.append(model)
    subject.app.ActiveDoc = model
    model.title = "Changed"

    with pytest.raises(probe.ProbeFailure, match="title changed"):
        getattr(subject, consumer)()

    assert owned.title == "Original" and owned.native is model
    assert not title_refreshes(subject) and not subject.app.close_calls


@pytest.mark.parametrize("saved", (False, True))
def test_pending_other_owner_blocks_activation_refresh_before_commit(tmp_path, saved):
    subject = OfflineProbe(tmp_path)
    drawing = admit_offline_drawing(subject, saved=saved)
    drawing.ActivateSheet(probe.ViewId.A)
    pending = OfflineModel("Pending", 1, "")
    subject.app.models.append(pending)
    subject.acquisitions[probe.Document.P] = probe.OwnedDocument(
        pending, "Pending", None, None, 1, probe.AcquisitionState.PENDING
    )

    with pytest.raises(probe.ProbeFailure, match="pending/unresolved"):
        subject.activate(probe.Document.DRAWING)

    assert subject.documents[probe.Document.DRAWING].title == "Draw - Sheet1"
    assert not title_refreshes(subject) and not subject.app.activation_calls
    assert activation_receipt(subject)["pre_active"]["state"] is (
        probe.ActiveObservation.NOT_OBSERVED
    )


def test_prior_failure_remains_primary_when_drawing_replacement_blocks_cleanup(
    tmp_path,
):
    subject = OfflineProbe(tmp_path)
    original = OSError("original construction failure")
    drawing = admit_offline_drawing(subject)
    replacement = OfflineDrawing()
    replacement.ActivateSheet(probe.ViewId.A)
    subject.app.models[:] = [replacement]
    subject.app.ActiveDoc = replacement

    def action():
        raise original

    assert capture_and_cleanup_failure(subject, action) is original
    assert subject.receipt.primary is original
    assert subject.receipt.data["secondary_errors"]
    assert subject.acquisitions[probe.Document.DRAWING].native is drawing
    assert subject.acquisitions[probe.Document.DRAWING].title == "Draw - Sheet1"
    assert not subject.app.close_calls and not subject.app.activation_calls
    assert not title_refreshes(subject)


@pytest.mark.parametrize("changed", ("title", "path", "kind"))
def test_changed_admitted_metadata_refuses_discard_without_losing_ownership(
    tmp_path, changed
):
    subject = OfflineProbe(tmp_path)
    model = OfflineModel("P", 1, subject.paths[probe.Document.P])
    subject.app.open_results.append((model, 0, 0))
    subject.open_source(probe.Document.P)
    setattr(
        model,
        changed,
        {
            "title": "Changed-but-still-owned",
            "path": str(tmp_path / "changed.sldprt"),
            "kind": 2,
        }[changed],
    )

    with pytest.raises(probe.ProbeFailure) as caught:
        subject.close(probe.Document.P)

    assert caught.value.verdict is probe.Verdict.RESTORATION
    assert not subject.app.close_calls
    assert subject.app.models == [model]
    assert subject.acquisitions[probe.Document.P].native is model
    assert probe.Document.P in subject.documents
    assert any(row["event"] == "discard_held" for row in subject.receipt.data["ledger"])


def test_offline_closed_handles_raise_instead_of_simulating_native_liveness(tmp_path):
    application = OfflineApplication(tmp_path)
    removed = OfflineModel("Removed", 1, tmp_path / "removed.sldprt")
    live = OfflineModel("Live", 1, tmp_path / "live.sldprt")
    application.models.extend((removed, live))
    application.ActiveDoc = live
    survivor_witness = OfflineModelHandle(live, 0)
    application.CloseDoc("Removed")
    for method in (
        removed.GetTitle,
        removed.GetType,
        removed.GetPathName,
        removed.IsOpenedReadOnly,
        removed.GetSaveFlag,
        removed.GetConfigurationNames,
        removed.GetActiveConfiguration,
        lambda: removed.GetConfigurationByName("Default"),
        lambda: application.IsSame(removed, live),
        lambda: application.IsSame(live, removed),
        lambda: OfflineModelHandle(removed, 0).GetTitle(),
    ):
        with pytest.raises(RuntimeError, match="disconnected document handle"):
            method()
    fresh = application.GetDocuments()[0]
    lookup = application.GetOpenDocumentByName(live.path)
    assert isinstance(fresh, OfflineModelHandle) and fresh.generation == 1
    assert isinstance(lookup, OfflineModelHandle) and lookup.generation == 1
    assert fresh is not lookup
    for handle in (live, survivor_witness, fresh, lookup, application.ActiveDoc):
        assert handle.GetTitle() == "Live"
        assert application.IsSame(handle, survivor_witness) == 1
        assert application.IsSame(survivor_witness, handle) == 1
    assert not live.disconnected_accesses


def test_direct_q_then_p_close_reacquires_saved_survivor_with_preclose_owner_witness(
    tmp_path, monkeypatch
):
    subject = OfflineProbe(tmp_path)
    p = OfflineModel("P", 1, subject.paths[probe.Document.P])
    q = OfflineModel("Q", 1, subject.paths[probe.Document.Q])
    subject.app.open_results.extend(((p, 0, 0), (q, 0, 0)))
    subject.open_source(probe.Document.P)
    subject.open_source(probe.Document.Q)
    subject.adapter.currentModel = q
    subject.view_handles[probe.ViewId.A] = object()
    subject.node_handles[probe.ViewId.A, probe.NodeId.P1] = object()
    close = subject.app.CloseDoc
    identity_boundaries = []

    def invalidated_close(title):
        assert subject.adapter.currentModel is None
        assert all(owned.native is None for owned in subject.acquisitions.values())
        assert all(owned.native is None for owned in subject.documents.values())
        assert not subject.view_handles and not subject.node_handles
        close(title)
        identity_boundaries.append(len(subject.app.identity_calls))

    monkeypatch.setattr(subject.app, "CloseDoc", invalidated_close)
    subject.close(probe.Document.Q)

    assert subject.app.close_calls == ["Q"]
    assert subject.app.closed == [q] and subject.app.models == [p]
    assert set(subject.acquisitions) == {probe.Document.P}
    survivor = subject.model(probe.Document.P)
    assert isinstance(survivor, OfflineModelHandle)
    assert survivor.document is p and survivor.generation == 1
    assert str(subject.paths[probe.Document.P]) in subject.app.lookup_calls
    postclose_identity = subject.app.identity_calls[identity_boundaries[0] :]
    assert any(p is left or p is right for left, right in postclose_identity)
    for operands in postclose_identity:
        assert all(subject.app.document(handle) is p for handle in operands)
        assert all(
            handle is p
            or isinstance(handle, OfflineModelHandle)
            and handle.generation == 1
            for handle in operands
        )
    attempt = next(
        row
        for row in subject.receipt.data["ledger"]
        if row["event"] == "discard_attempt"
    )
    frozen = attempt["preclose_inventory"]
    assert set(frozen) == {probe.Document.P, probe.Document.Q}
    assert frozen[probe.Document.P]["path"] == str(subject.paths[probe.Document.P])
    assert frozen[probe.Document.Q]["title"] == "Q"
    assert frozen[probe.Document.Q]["kind"] == 1

    subject.close(probe.Document.P)

    assert subject.app.close_calls == ["Q", "P"]
    assert subject.app.closed == [q, p] and not subject.app.models
    assert not subject.acquisitions and not subject.documents
    assert not p.disconnected_accesses and not q.disconnected_accesses
    discarded = [
        row for row in subject.receipt.data["ledger"] if row["event"] == "discard"
    ]
    assert [row["document"] for row in discarded] == [
        probe.Document.Q,
        probe.Document.P,
    ]
    assert all(row["implicit"] is False for row in discarded)


@pytest.mark.parametrize("witness", ("mismatched", "unsupported", "disconnected"))
@pytest.mark.parametrize("earlier_failure", (False, True))
def test_same_metadata_replacement_refuses_preclose_owner_adoption_atomically(
    tmp_path, monkeypatch, witness, earlier_failure
):
    subject = OfflineProbe(tmp_path)
    p = OfflineModel("P", 1, subject.paths[probe.Document.P])
    q = OfflineModel("Q", 1, subject.paths[probe.Document.Q])
    replacement = OfflineModel(p.title, p.kind, p.path)
    subject.app.open_results.extend(((p, 0, 0), (q, 0, int(earlier_failure))))
    close = subject.app.CloseDoc
    held, admitted, primary, identity_boundaries = {}, {}, [], []

    def replacing_close(title):
        assert title == "Q"
        assert all(owned.native is None for owned in subject.acquisitions.values())
        assert all(owned.native is None for owned in subject.documents.values())
        assert subject.adapter.currentModel is None
        assert not subject.view_handles and not subject.node_handles
        close(title)
        assert subject.app.models == [p]
        subject.app.models[0] = replacement
        subject.app.ActiveDoc = replacement
        if witness == "disconnected":
            p.live = False
            subject.app.closed.append(p)
        elif witness == "unsupported":
            p.unsupported_identity = True
        identity_boundaries.append(len(subject.app.identity_calls))

    def action():
        subject.open_source(probe.Document.P)
        subject.adapter.currentModel = p
        subject.view_handles[probe.ViewId.A] = object()
        subject.node_handles[probe.ViewId.A, probe.NodeId.P1] = object()
        try:
            subject.open_source(probe.Document.Q)
        except BaseException as error:
            primary.append(error)
            held.update(subject.acquisitions)
            admitted.update(subject.documents)
            raise
        held.update(subject.acquisitions)
        admitted.update(subject.documents)
        subject.close(probe.Document.Q)

    monkeypatch.setattr(subject.app, "CloseDoc", replacing_close)
    expected = {
        "mismatched": "post-close survivor changed pre-close owner identity",
        "unsupported": "unsupported native identity result 2",
        "disconnected": "disconnected document handle: IsSame",
    }[witness]
    if earlier_failure:
        original = capture_and_cleanup_failure(subject, action)
        assert original is primary[0]
        assert original.verdict is probe.Verdict.CONSTRUCTION
        assert subject.receipt.primary is original
        assert subject.receipt.data["cleanup"]["status"] is probe.Verdict.RESTORATION
        assert any(
            expected in row["message"]
            for row in subject.receipt.data["cleanup"]["errors"]
        )
        assert subject.receipt.data["cases"][probe.Case.CONSTRUCTION]["status"] is (
            probe.Verdict.CONSTRUCTION
        )
    else:
        with pytest.raises(
            (probe.ProbeFailure, RuntimeError), match=expected
        ) as caught:
            action()
        if witness != "disconnected":
            assert caught.value.verdict is (
                probe.Verdict.IDENTITY
                if witness == "unsupported"
                else probe.Verdict.RESTORATION
            )
    assert subject.app.close_calls == ["Q"]
    assert subject.app.closed == ([q, p] if witness == "disconnected" else [q])
    assert subject.app.models == [replacement]
    assert set(subject.acquisitions) == set(held)
    assert set(subject.documents) == set(admitted)
    assert all(subject.acquisitions[key] is owned for key, owned in held.items())
    assert all(subject.documents[key] is owned for key, owned in admitted.items())
    assert all(owned.native is None for owned in subject.acquisitions.values())
    assert all(owned.native is None for owned in subject.documents.values())
    assert subject.adapter.currentModel is None
    assert not subject.view_handles and not subject.node_handles
    assert not any(row["event"] == "discard" for row in subject.receipt.data["ledger"])
    assert len(identity_boundaries) == 1
    postclose_identity = subject.app.identity_calls[identity_boundaries[0] :]
    assert any(
        left.document is replacement
        and right.document is replacement
        and left.generation == right.generation == 1
        for left, right in postclose_identity
        if isinstance(left, OfflineModelHandle)
        and isinstance(right, OfflineModelHandle)
    )
    assert any(
        isinstance(left, OfflineModelHandle)
        and left.document is replacement
        and left.generation == 1
        and right is p
        for left, right in postclose_identity
    )
    assert all(
        subject.app.document(handle) is not q
        for operands in postclose_identity
        for handle in operands
    )
    assert p.disconnected_accesses == (["IsSame"] if witness == "disconnected" else [])
    assert not q.disconnected_accesses
    assert not replacement.disconnected_accesses
    assert subject.model(probe.Document.P) is None
    for label in (probe.Document.Q, probe.Document.P):
        with pytest.raises(probe.ProbeFailure):
            subject.close(label)
    assert subject.app.close_calls == ["Q"]
    assert subject.receipt.data["handoff_allowed"] is False


def test_implicit_drawing_dependency_close_invalidates_all_references_first(
    tmp_path, monkeypatch
):
    subject = OfflineProbe(tmp_path)
    drawing_path = subject.paths[probe.Document.DRAWING]
    drawing_path.write_bytes(b"offline saved drawing")
    drawing = OfflineModel("Drawing", 3, drawing_path, readonly=False)
    drawing.hidden = True
    subject.app.open_results.append((drawing, 0, 0))
    with subject.acquiring(probe.Document.DRAWING) as before:
        result = subject.app.OpenDoc6(str(drawing_path), 3, 1, "", 0, 0)
        subject.acquired(probe.Document.DRAWING, result[0], before)
        probe.checked_tuple(result, "offline drawing admission", save=False)
        subject.claim(probe.Document.DRAWING, 3, drawing_path)
    q = OfflineModel("Q", 1, subject.paths[probe.Document.Q])
    subject.app.open_results.append((q, 0, 0))
    subject.open_source(probe.Document.Q)
    subject.view_handles[probe.ViewId.A] = object()
    subject.node_handles[probe.ViewId.A, probe.NodeId.P1] = object()
    subject.adapter.currentModel = drawing
    close = subject.app.CloseDoc

    def invalidated_close(title):
        assert not subject.view_handles and not subject.node_handles
        assert subject.adapter.currentModel is None
        assert all(owned.native is None for owned in subject.acquisitions.values())
        close(title)

    monkeypatch.setattr(subject.app, "CloseDoc", invalidated_close)
    subject.close(probe.Document.Q)

    assert subject.app.close_calls == ["Q"]
    assert subject.app.closed == [q, drawing]
    assert not subject.acquisitions and not subject.documents
    assert not drawing.disconnected_accesses and not q.disconnected_accesses
    discarded = {
        row["document"]: row["implicit"]
        for row in subject.receipt.data["ledger"]
        if row["event"] == "discard"
    }
    assert discarded == {probe.Document.Q: False, probe.Document.DRAWING: True}


@pytest.mark.parametrize(
    "fault",
    ("absent_acquisition", "lost_acquisition", "duplicate_live", "duplicate_owner"),
)
def test_preclose_inventory_requires_bijection_with_every_acquisition(tmp_path, fault):
    subject = OfflineProbe(tmp_path)
    p = OfflineModel("P", 1, subject.paths[probe.Document.P])
    q = OfflineModel("Q", 1, subject.paths[probe.Document.Q])
    subject.app.open_results.extend(((p, 0, 0), (q, 0, 0)))
    subject.open_source(probe.Document.P)
    subject.open_source(probe.Document.Q)
    if fault == "absent_acquisition":
        subject.app.models.remove(p)
    elif fault == "lost_acquisition":
        subject.acquisitions.pop(probe.Document.P)
    elif fault == "duplicate_live":
        subject.app.models.append(p)
    else:
        subject.acquisitions[probe.Document.N] = subject.acquisitions[probe.Document.P]
    retained = dict(subject.acquisitions)

    with pytest.raises(probe.ProbeFailure) as caught:
        subject.close(probe.Document.Q)

    assert caught.value.verdict is probe.Verdict.RESTORATION
    assert subject.acquisitions == retained
    assert not subject.app.close_calls and not subject.app.closed
    assert any(row["event"] == "discard_held" for row in subject.receipt.data["ledger"])


def test_duplicate_owned_titles_refuse_before_any_close(tmp_path):
    subject = OfflineProbe(tmp_path)
    p = OfflineModel("Same", 1, subject.paths[probe.Document.P])
    q = OfflineModel("same", 1, subject.paths[probe.Document.Q])
    subject.app.open_results.extend(((p, 0, 0), (q, 0, 1)))

    def action():
        subject.open_source(probe.Document.P)
        subject.open_source(probe.Document.Q)

    original = capture_and_cleanup_failure(subject, action)

    assert "errors/warnings" in str(original)
    assert not subject.app.close_calls
    assert subject.app.models == [p, q]
    assert set(subject.acquisitions) == {probe.Document.P, probe.Document.Q}
    assert subject.receipt.data["cleanup"]["status"] is probe.Verdict.RESTORATION


@pytest.mark.parametrize(
    "fault",
    (
        "foreign",
        "title",
        "path",
        "kind",
        "duplicate_survivor",
        "retained_target",
        "missing_lookup",
        "different_lookup",
        "lookup_error",
        "identity_error",
    ),
)
def test_postclose_reconciliation_is_atomic_and_refuses_every_retry(
    tmp_path, monkeypatch, fault
):
    subject = OfflineProbe(tmp_path)
    p = OfflineModel("P", 1, subject.paths[probe.Document.P])
    q = OfflineModel("Q", 1, subject.paths[probe.Document.Q])
    subject.app.open_results.extend(((p, 0, 0), (q, 0, 0)))
    subject.open_source(probe.Document.P)
    subject.open_source(probe.Document.Q)
    subject.adapter.currentModel = p
    subject.view_handles[probe.ViewId.A] = object()
    subject.node_handles[probe.ViewId.A, probe.NodeId.P1] = object()
    original = OSError(f"fresh reconciliation {fault}")
    close = subject.app.CloseDoc
    lookup = subject.app.GetOpenDocumentByName
    same = subject.app.IsSame

    def changed_close(title):
        close(title)
        if fault == "foreign":
            subject.app.models.append(
                OfflineModel("Intruder", 1, tmp_path / "intruder.sldprt")
            )
        elif fault in ("title", "path", "kind"):
            setattr(
                p,
                fault,
                {
                    "title": "Changed",
                    "path": str(tmp_path / "changed.sldprt"),
                    "kind": 2,
                }[fault],
            )
        elif fault == "duplicate_survivor":
            subject.app.models.append(p)
        elif fault == "retained_target":
            subject.app.models.append(
                OfflineModel("Q", 1, subject.paths[probe.Document.Q])
            )

    def failed_lookup(path):
        if subject.app.inventory_generation and probe.normalized(
            path
        ) == probe.normalized(p.path):
            if fault == "missing_lookup":
                return None
            if fault == "different_lookup":
                return OfflineModel("Other", 1, p.path)
            if fault == "lookup_error":
                raise original
        return lookup(path)

    def failed_identity(left, right):
        if fault == "identity_error" and subject.app.inventory_generation:
            raise original
        return same(left, right)

    monkeypatch.setattr(subject.app, "CloseDoc", changed_close)
    monkeypatch.setattr(subject.app, "GetOpenDocumentByName", failed_lookup)
    monkeypatch.setattr(subject.app, "IsSame", failed_identity)
    with pytest.raises((probe.ProbeFailure, OSError)) as caught:
        subject.close(probe.Document.Q)

    if fault in ("lookup_error", "identity_error"):
        assert caught.value is original
    else:
        assert caught.value.verdict is probe.Verdict.RESTORATION
    assert subject.app.close_calls == ["Q"]
    assert set(subject.acquisitions) == {probe.Document.P, probe.Document.Q}
    assert set(subject.documents) == {probe.Document.P, probe.Document.Q}
    assert all(owned.native is None for owned in subject.acquisitions.values())
    assert not subject.view_handles and not subject.node_handles
    assert subject.adapter.currentModel is None
    assert not any(row["event"] == "discard" for row in subject.receipt.data["ledger"])
    assert not p.disconnected_accesses and not q.disconnected_accesses
    for label in (probe.Document.Q, probe.Document.P):
        with pytest.raises(probe.ProbeFailure):
            subject.close(label)
    assert subject.app.close_calls == ["Q"]


def test_pathless_nontarget_survivor_is_not_adopted_from_metadata(
    tmp_path, assembly_template
):
    subject = OfflineProbe(tmp_path)
    authoring = OfflineModel("Authoring", 2, "", readonly=False)
    subject.app.new_results.append(authoring)
    subject.new_assembly(probe.Document.N_AUTHOR)
    q = OfflineModel("Q", 1, subject.paths[probe.Document.Q])
    subject.app.open_results.append((q, 0, 0))
    subject.open_source(probe.Document.Q)

    with pytest.raises(probe.ProbeFailure, match="pathless") as caught:
        subject.close(probe.Document.Q)

    assert caught.value.verdict is probe.Verdict.RESTORATION
    assert subject.app.close_calls == ["Q"]
    assert subject.app.models == [authoring]
    assert set(subject.acquisitions) == {probe.Document.N_AUTHOR, probe.Document.Q}
    assert all(owned.native is None for owned in subject.acquisitions.values())
    assert not authoring.disconnected_accesses and not q.disconnected_accesses
    with pytest.raises(probe.ProbeFailure):
        subject.close(probe.Document.N_AUTHOR)
    assert subject.app.close_calls == ["Q"]


def test_case_restore_failure_remains_primary_when_final_reporting_also_fails(
    tmp_path, monkeypatch
):
    subject = OfflineProbe(tmp_path)
    drawing = OfflineModel(
        "AdmittedDrawing", 3, subject.paths[probe.Document.DRAWING], readonly=False
    )
    subject.app.open_results.append((drawing, 0, 0))
    with subject.acquiring(probe.Document.DRAWING) as before:
        result = subject.app.OpenDoc6(
            str(subject.paths[probe.Document.DRAWING]), 3, 1, "", 0, 0
        )
        subject.acquired(probe.Document.DRAWING, result[0], before)
        probe.checked_tuple(result, "offline drawing admission", save=False)
        subject.claim(probe.Document.DRAWING, 3, subject.paths[probe.Document.DRAWING])
    assert subject.model(probe.Document.DRAWING) is drawing
    original = probe.ProbeFailure(probe.Verdict.RESTORATION, "flag restore failed")
    reporting = OSError("final checkpoint failed after restore")
    calls = []

    def set_flags(flags):
        calls.append(flags)
        if len(calls) == 2:
            raise original

    monkeypatch.setattr(subject, "flags", lambda: {"graphics": True})
    monkeypatch.setattr(subject, "set_flags", set_flags)
    fail_case_final_checkpoint_once(subject, monkeypatch, reporting)
    with pytest.raises(probe.ProbeFailure) as caught:
        with subject.stage_scope(probe.Stage.CONSTRUCTION):
            subject.run_case(
                probe.Case.CONSTRUCTION,
                lambda: None,
                flag_overrides={"graphics": False},
            )
    assert caught.value is original
    assert calls == [{"graphics": False}, {"graphics": True}]
    assert subject.receipt.primary is original
    assert (
        subject.receipt.data["cases"][probe.Case.CONSTRUCTION]["status"]
        is probe.Verdict.RESTORATION
    )
    assert (
        subject.receipt.data["stages"][probe.Stage.CONSTRUCTION]["status"]
        is probe.Verdict.RESTORATION
    )
    assert any(
        row["message"] == str(reporting)
        for row in subject.receipt.data["secondary_errors"]
    )
    assert subject.receipt.data["handoff_allowed"] is False


def test_owned_hidden_collateral_close_is_reconciled_without_retrying_gone_models(
    tmp_path,
):
    subject = OfflineProbe(tmp_path)
    p = OfflineModel("P", 1, subject.paths[probe.Document.P])
    p.hidden = True
    q = OfflineModel("Q", 1, subject.paths[probe.Document.Q])
    subject.app.open_results.extend(((p, 0, 0), (q, 0, 1)))

    def action():
        subject.open_source(probe.Document.P)
        subject.open_source(probe.Document.Q)

    original = capture_and_cleanup_failure(subject, action)
    assert isinstance(original, probe.ProbeFailure)
    assert "errors/warnings" in str(original)
    assert subject.app.close_calls == ["Q"]
    assert subject.app.closed == [q, p]
    assert not subject.app.models
    assert not subject.acquisitions and not subject.documents
    discarded = [
        row["document"]
        for row in subject.receipt.data["ledger"]
        if row["event"] == "discard"
    ]
    assert discarded.count(probe.Document.P) == discarded.count(probe.Document.Q) == 1


def test_unresolved_live_acquisition_holds_known_owned_model_without_any_close(
    tmp_path,
):
    subject = OfflineProbe(tmp_path)
    p = OfflineModel("P", 1, subject.paths[probe.Document.P])
    unresolved = OfflineModel("Unknown", 1, subject.paths[probe.Document.Q])
    unresolved.hidden = True
    unresolved.unsupported_identity = True
    subject.app.open_results.extend(((p, 0, 0), (unresolved, 0, 0)))

    def action():
        subject.open_source(probe.Document.P)
        subject.open_source(probe.Document.Q)

    original = capture_and_cleanup_failure(subject, action)
    assert isinstance(original, probe.ProbeFailure)
    assert original.verdict is probe.Verdict.IDENTITY
    assert not subject.app.close_calls and not subject.app.closed
    assert subject.app.models == [p, unresolved]
    assert (
        subject.acquisitions[probe.Document.P].state is probe.AcquisitionState.ADMITTED
    )
    assert (
        subject.acquisitions[probe.Document.Q].state
        is probe.AcquisitionState.UNRESOLVED
    )
    assert subject.receipt.data["cleanup"]["errors"]
    assert any(row["event"] == "discard_held" for row in subject.receipt.data["ledger"])


@pytest.mark.parametrize("intruder", ("foreign", "unresolved"))
def test_probe_refusal_preserves_primary_through_mandatory_session_teardown(
    tmp_path, monkeypatch, intruder
):
    import _session
    import draw_ch_channel_assembly as drawing

    subject = OfflineProbe(tmp_path)
    events, original, recorded, probe_exit, normal_work = [], [], [], [], []
    outer_teardown = [False]
    owned = OfflineModel("P", 1, subject.paths[probe.Document.P])
    other = OfflineModel("Other", 1, subject.paths[probe.Document.Q])
    other.hidden = True
    subject.app.open_results.append((owned, 0, 0))
    if intruder == "unresolved":
        other.open_error = OSError("offline open left an unreturned model")
        subject.app.open_results.append((other, 0, 0))

    def construction():
        subject.open_source(probe.Document.P)
        try:
            if intruder == "foreign":
                subject.app.models.append(other)
                subject.app.ActiveDoc = other
                subject.close(probe.Document.P)
            else:
                subject.open_source(probe.Document.Q)
        except Exception as error:
            original.append(error)
            raise

    subject.construction_action = construction

    async def connect():
        assert not subject.app.models
        events.append("connect")

    async def disconnect():
        assert not subject.app.models
        events.append("disconnect")

    def unexpected_normal_work(*args, **kwargs):
        normal_work.append("entered")
        raise AssertionError("normal native drawing work must remain blocked")

    async def unexpected_async_work(*args, **kwargs):
        unexpected_normal_work()

    adapter = SimpleNamespace(
        swApp=subject.app,
        currentModel=None,
        connect=connect,
        disconnect=disconnect,
        open_model=unexpected_async_work,
        _attempt=lambda action, **kwargs: action(),
    )
    # Retain actual session discard/teardown; only their native/host ports are
    # in-memory. A probe close before sw.disconnect is an immediate test failure.
    close = subject.app.CloseDoc

    def close_from_outer_session(title):
        assert outer_teardown[0], "probe ownership barrier allowed a native close"
        if not probe_exit:
            probe_exit.append(
                (tuple(subject.app.models), tuple(subject.app.close_calls))
            )
        events.append(f"outer-close:{title}")
        close(title)

    def close_all(include_unsaved):
        assert include_unsaved is True and not subject.app.models
        events.append("close-all")

    def resident_outputs(candidate):
        assert candidate is adapter and not subject.app.models
        events.append("resident-check")
        return []

    def park(application):
        assert application is subject.app
        events.append("park")
        return str(tmp_path)

    @asynccontextmanager
    async def aspan(name, **kwargs):
        if name == "sw.disconnect":
            outer_teardown[0] = True
        try:
            yield
        finally:
            if name == "sw.disconnect":
                outer_teardown[0] = False

    root = SimpleNamespace(
        record_exception=recorded.append, set_status=lambda value: None
    )
    telemetry = SimpleNamespace(
        build_session=lambda *args, **kwargs: nullcontext(root),
        aspan=aspan,
        span=lambda *args, **kwargs: nullcontext(),
        set_service=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
        success=lambda *args, **kwargs: None,
        warn=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: events.append("error"),
        shutdown=lambda: events.append("shutdown"),
        Status=lambda *args: args,
        StatusCode=SimpleNamespace(ERROR="offline-error"),
    )

    def factory(candidate, root_path, receipt):
        assert candidate is adapter and root_path == tmp_path
        subject.adapter, subject.receipt = candidate, receipt
        return subject

    monkeypatch.setitem(
        sys.modules,
        "solidworks_mcp.adapters.pywin32_adapter",
        SimpleNamespace(PyWin32Adapter=lambda settings: adapter),
    )
    monkeypatch.delenv("TRACEPARENT", raising=False)
    monkeypatch.setattr(
        _session,
        "sys",
        SimpleNamespace(
            argv=[str(tmp_path / "draw_ch_channel_assembly.py")],
            stdout=StringIO(),
            stderr=StringIO(),
        ),
    )
    monkeypatch.setattr(_session, "_telemetry", telemetry)
    monkeypatch.setattr(
        _session,
        "_watchdog",
        SimpleNamespace(
            start=lambda: events.append("watchdog-start"),
            stop=lambda: events.append("watchdog-stop"),
        ),
    )
    monkeypatch.setattr(_session, "_pin_default_part_template", lambda candidate: None)
    monkeypatch.setattr(_session, "_resident_output_documents", resident_outputs)
    forensics = _session._seat_forensics
    monkeypatch.setattr(forensics, "_telemetry", telemetry)
    monkeypatch.setattr(forensics, "note_seats_before_connect", lambda: None)
    monkeypatch.setattr(forensics, "record_seat_provenance", lambda candidate: {})
    monkeypatch.setattr(forensics, "release_seat_working_directory", park)
    monkeypatch.setattr(subject.app, "CloseDoc", close_from_outer_session)
    monkeypatch.setattr(
        subject.app, "IActiveDoc2", lambda: subject.app.ActiveDoc, raising=False
    )
    monkeypatch.setattr(subject.app, "CloseAllDocuments", close_all, raising=False)
    # The already-created traced build wrapper resolves aspan on this module.
    monkeypatch.setattr(drawing._telemetry, "aspan", aspan)
    monkeypatch.setattr(
        drawing, "_config", SimpleNamespace(machine=lambda *keys: "neutral")
    )
    monkeypatch.setattr(
        drawing, "SPRING_STEMS", ("ch-vn-channel-spring-installed-stretch00",)
    )
    source = tmp_path / "production-source.SLDASM"
    source.write_bytes(b"offline normal-work sentinel")
    monkeypatch.setattr(drawing, "SOURCE", source)
    for name in (
        "_early_bound",
        "read_required_properties",
        "_validate_source",
        "_create_sheets",
        "_place_assembled_sheet",
        "_place_exploded_sheet",
        "_place_fitup_sheets",
    ):
        monkeypatch.setattr(drawing, name, unexpected_normal_work)
    monkeypatch.setattr(drawing, "finalize_drawing", unexpected_async_work)
    monkeypatch.setattr(
        probe, "__file__", str(tmp_path / "cad/scripts/offline_probe.py")
    )
    monkeypatch.setattr(
        probe, "source_identity", lambda root_path: {"offline_boundary_only": True}
    )
    monkeypatch.setattr(probe, "NativeProbe", factory)

    assert _session.run_build(drawing.build) == 1

    assert len(original) == 1 and recorded == [original[0]]
    assert subject.receipt.primary is original[0]
    if intruder == "foreign":
        assert isinstance(original[0], probe.ProbeFailure)
        assert "foreign/unresolved live identity" in str(original[0])
    else:
        assert original[0] is other.open_error
        assert subject.receipt.data["unresolved_acquisitions"][0]["document"] == (
            probe.Document.Q
        )
    assert probe_exit == [((owned, other), ())]
    assert probe.Document.P in subject.acquisitions
    assert probe.Document.Q not in subject.acquisitions
    assert any(row["event"] == "discard_held" for row in subject.receipt.data["ledger"])
    assert not any(
        row["event"] == "discard_attempt" for row in subject.receipt.data["ledger"]
    )
    assert subject.receipt.data["secondary_errors"]
    assert subject.receipt.data["handoff_allowed"] is False and not normal_work
    assert subject.app.close_calls == ["Other", "P"]
    assert not subject.app.models
    assert events == [
        "watchdog-start",
        "connect",
        "close-all",
        "resident-check",
        "outer-close:Other",
        "outer-close:P",
        "close-all",
        "resident-check",
        "park",
        "disconnect",
        "watchdog-stop",
        "error",
        "shutdown",
    ]
    data = json.loads((subject.receipt.root / "report.json").read_text())
    assert data["held_model_scope"] == "probe_exit"
    assert data["outer_session_teardown"] == "not_observed_by_probe"
    assert data["handoff_allowed"] is False
    assert data["primary_error"]["message"] == str(original[0])
    assert data["cleanup"]["remaining_owned"] == [probe.Document.P]
