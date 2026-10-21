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


def test_deadlines_distinguish_work_stage_and_reserved_cleanup(tmp_path) -> None:
    clock = [0.0]
    receipt = probe.Receipt(tmp_path, clock=lambda: clock[0])
    clock[0] = 100.0
    receipt.deadline()
    clock[0] = 100.001
    with pytest.raises(probe.ProbeFailure) as caught:
        receipt.deadline()
    assert caught.value.verdict is probe.Verdict.DEADLINE
    receipt.stage = probe.Stage.CLEANUP
    receipt.stage_started = 410.0
    clock[0] = 480.0
    receipt.deadline(cleanup=True)
    clock[0] = 480.001
    with pytest.raises(probe.ProbeFailure):
        receipt.deadline(cleanup=True)


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

    def __init__(self, root):
        # Deliberately do not invoke NativeProbe.__init__ or import its SDK.
        reports = root / "reports"
        reports.mkdir()
        self.root = root
        self.receipt = probe.Receipt(reports)
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
