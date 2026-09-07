"""Production miss/hit orchestration through the actual owned-document facade."""

import asyncio
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from diagnostics import _owned_native_documents as owned
from diagnostics import probe_prepared_template_cache as probe
from test_owned_native_documents_drawing import Model, native  # noqa: F401


@pytest.fixture
def scene(native, monkeypatch, tmp_path):  # noqa: F811
    for name, value in {
        "HARMONIC_SW_AUTOSTART": "0",
        "HARMONIC_REMOTE_CACHE_MODE": "off",
        "HARMONIC_DIAGNOSTIC_SW_PID": "123",
        "HARMONIC_COM_SEAT": "test",
    }.items():
        monkeypatch.setenv(name, value)
    original = tmp_path / "original.DRWDOT"
    original.write_bytes(b"immutable source template")
    baseline = [
        Model(native.source, kind=1),
        Model(None, title="User drawing", dirty=True),
    ]
    native.app.documents.extend(baseline)
    native.app.ActiveDoc = baseline[-1]
    native.app.GetProcessID = lambda: 123
    native.app.RevisionNumber = lambda: "34.3.0"
    native.app.UserControl = True
    created, saves, faults = [], [], {}
    viewport_calls = []
    expected = {
        "units": {"system": 4, "linear": 0, "decimals": 2},
        "sheet_notes": [{"link": '$PRPSHEET:"Material"', "alignment": 1}],
        "blank_linked_extent_observations": [0.125],
    }

    class View:
        def __init__(self):
            self._scale = 1.0
            self.translation = [0.01 * (len(created) + 1), 0.002, 0.0]

        @property
        def Scale2(self):
            return self._scale

        @Scale2.setter
        def Scale2(self, value):
            viewport_calls.append(("scale", value))
            self._scale = value
            self.translation[0] += 0.01

        @property
        def Translation3(self):
            return SimpleNamespace(ArrayData=tuple(self.translation))

        @Translation3.setter
        def Translation3(self, value):
            viewport_calls.append(("translation", tuple(value.ArrayData)))
            self.translation = list(value.ArrayData)
            if faults.get("translation_readback"):
                self.translation[0] += 1e-12

        @property
        def Orientation3(self):
            matrix = [1.0] * 16
            if faults.get("orientation") and len(created) >= 2:
                matrix[0] += 1e-12
            return SimpleNamespace(ArrayData=matrix)

        @property
        def Transform(self):
            matrix = [1.0] * 16
            matrix[9:12] = self.translation
            matrix[12] = self._scale
            return SimpleNamespace(ArrayData=matrix)

        def GetVisibleBox(self):
            return (0, 0, 800, 600)

    class Drawing(Model):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.ActiveView = View()

        def GraphicsRedraw2(self):
            viewport_calls.append(("redraw", self.ActiveView.Scale2))

        def SaveAs3(self, path, version, options):
            assert (version, options) == (0, 0)
            Path(path).write_bytes(b"prepared native template")
            self.path, self.title = str(path), Path(path).name
            saves.append(Path(path))
            return 0

        def ClearSelection2(self, value):
            assert value is True

        def EditSheet(self):
            pass

        def ViewZoomtofit2(self):
            pass

        def GetCurrentSheet(self):
            return SimpleNamespace(SetScale=lambda *args: True)

    def create(adapter, **kwargs):
        model = Drawing(None, title=f"Owned blank {len(created)}")
        native.app.documents.append(model)
        created.append(model)
        native.app.ActiveDoc = model
        adapter.currentModel = model
        return model

    def activate(title, user, option, error):
        assert (user, option, error) == (False, 1, 0)
        doc = next(item for item in native.app.documents if item.title == title)
        native.app.ActiveDoc = doc
        return doc, 0

    def snapshot(adapter, spec):
        if faults.get("snapshot"):
            raise RuntimeError("raw native defaults rejected")
        value = deepcopy(expected)
        if faults.get("different_viewport_extents"):
            value["sheet_notes"][0]["extent"] = [
                adapter.currentModel.ActiveView.translation[0]
            ]
        if faults.get("independent_extent_drift") and len(created) >= 3:
            value["sheet_notes"][0]["extent"] = [1e-12]
        if faults.get("prepared_mismatch") and len(created) >= 2:
            value["units"]["decimals"] = 3
        if faults.get("original_mutation"):
            original.write_bytes(b"changed source; never reset")
        return value

    native.app.ActivateDoc3 = activate
    native.app.GetMathUtility = lambda: SimpleNamespace(
        CreateVector=lambda values: SimpleNamespace(
            ArrayData=tuple(values.value if hasattr(values, "value") else values)
        )
    )
    monkeypatch.setattr(probe.sheet_setup, "PROJECT_DRWDOT", original)
    monkeypatch.setattr(probe.sheet_setup, "new_drawing", create)
    monkeypatch.setattr(
        probe.sheet_setup,
        "new_project_drawing",
        lambda adapter, **kwargs: (create(adapter, **kwargs), object()),
    )
    monkeypatch.setattr(probe.sheet_setup, "assert_asme_b_sheet", lambda *a, **k: None)
    monkeypatch.setattr(probe, "snapshot_defaults", snapshot)
    monkeypatch.setattr(probe.prepared, "snapshot_defaults", snapshot)
    monkeypatch.setattr(
        probe.prepared,
        "preparation_inputs",
        lambda adapter, spec: {
            "template": probe.prepared._sha(original),
            "spec": [list(spec.scale), spec.decimals],
            "runtime": faults.get("runtime", "frozen"),
        },
    )
    reports = tmp_path / "reports"

    def run(**options):
        spec = options.pop("spec", probe.prepared.TemplateSpec((2, 1), 2))
        return asyncio.run(
            owned.owned_callback(
                native.adapter,
                lambda adapter: probe.probe(
                    adapter,
                    spec,
                    reports,
                    123,
                    **options,
                ),
            )
        )

    def report():
        paths = list(reports.glob("*/measurements.json"))
        assert len(paths) == 1
        return json.loads(paths[0].read_text()), paths[0].parent

    return SimpleNamespace(
        run=run,
        report=report,
        native=native,
        baseline=baseline,
        created=created,
        saves=saves,
        faults=faults,
        original=original,
        viewport_calls=viewport_calls,
    )


def test_real_cache_miss_hit_preserves_baseline_and_exact_one_save(scene):
    result = scene.run()
    report, directory = scene.report()
    assert result["measurements"] == str(directory / "measurements.json")
    assert report["status"] == "passed"
    assert [row["kind"] for row in report["accessors"]] == ["miss", "hit"]
    assert [row["variant"] for row in report["trials"]] == [
        "normal",
        "prepared_miss",
        "prepared_hit",
    ]
    assert len(scene.created) == 5 and len(scene.saves) == 1
    assert scene.native.app.closes == scene.created
    assert scene.native.app.documents == scene.baseline
    assert scene.native.adapter.opens == []
    assert scene.original.read_bytes() == b"immutable source template"
    assert all(row["status"] == "passed" for row in report["guards"])
    assert scene.viewport_calls == [
        ("redraw", 1.0),
        ("scale", 1.0),
        ("translation", (0.02, 0.002, 0.0)),
        ("redraw", 1.0),
    ]  # One verification redraw, then the unchanged production restore.
    assert all(
        "viewport_control" not in row
        for row in (*report["operation_scopes"], *report["trials"])
    )
    miss, hit = report["accessors"]
    assert miss["artifacts"] == hit["artifacts"]
    assert "relocation_seconds" in miss and "relocation_seconds" not in hit
    assert [row["operation"] for row in report["operation_scopes"]] == [
        "create",
        "save_as",
        "create",
    ]
    for row in report["trials"]:
        assert all(
            row[key] >= 0
            for key in ("setup_seconds", "witness_seconds", "cleanup_seconds")
        )
    evidence = json.loads((directory / "ownership.json").read_text())
    assert evidence["baseline_preservation"]["status"] == "preserved"
    assert [
        event["status"]
        for event in evidence["events"]
        if event["operation"] == "relocate_prepared_template"
    ] == ["relocated"]


def test_first_raw_failure_stops_before_cache_preparation_and_retains_cleanup(scene):
    scene.faults["snapshot"] = True
    with pytest.raises(ExceptionGroup):
        scene.run()
    report, _ = scene.report()
    assert report["status"] == "failed"
    assert report["accessors"] == []
    assert len(scene.created) == 1 and not scene.saves
    assert scene.native.app.documents == scene.baseline
    assert "raw native defaults rejected" in report["trials"][0]["error"]


def test_printed_policy_exports_all_three_and_compares_to_normal(scene, monkeypatch):
    exports, comparisons = [], []

    def capture(adapter, directory):
        adapter.ownership.assert_current_owned()
        exports.append(directory.name)
        return {"variant": directory.name}

    def compare(before, after):
        comparisons.append((before["variant"], after["variant"]))
        return {"changed_pixel_count": 0}

    monkeypatch.setattr(probe, "printed_witness", capture)
    monkeypatch.setattr(probe, "compare_printed", compare)
    scene.run(printed_format=probe.PrintedFormat.COMPARE)
    report, _ = scene.report()
    assert exports == ["normal", "prepared_miss", "prepared_hit"]
    assert comparisons == [("normal", "prepared_miss"), ("normal", "prepared_hit")]
    assert len(scene.created) == 5 and len(scene.saves) == 1
    assert report["printed_format"] == "compare"
    assert all("post_print_witness_seconds" in row for row in report["trials"])
    assert scene.native.app.documents == scene.baseline


def test_printed_difference_stops_before_hit_without_reset(scene, monkeypatch):
    monkeypatch.setattr(probe, "printed_witness", lambda *args: {"captured": "yes"})

    def reject(*args):
        raise RuntimeError("visible border changed")

    monkeypatch.setattr(probe, "compare_printed", reject)
    with pytest.raises(ExceptionGroup):
        scene.run(printed_format=probe.PrintedFormat.COMPARE)
    report, _ = scene.report()
    assert len(report["accessors"]) == 1
    assert "visible border changed" in report["trials"][-1]["error"]
    assert scene.native.app.documents == scene.baseline


def test_post_export_default_mutation_remains_a_failure(scene, monkeypatch):
    def mutate(*args):
        scene.faults["snapshot"] = True
        return {"captured": "yes"}

    monkeypatch.setattr(probe, "printed_witness", mutate)
    with pytest.raises(ExceptionGroup):
        scene.run(printed_format=probe.PrintedFormat.COMPARE)
    report, _ = scene.report()
    assert report["accessors"] == []
    assert "raw native defaults rejected" in report["trials"][0]["error"]
    assert scene.native.app.documents == scene.baseline


@pytest.mark.parametrize("change", ["none", "pixel", "glyph", "page", "file"])
def test_printed_comparison_rejects_real_output_changes(tmp_path, change):
    from PIL import Image

    snapshots = []
    for name in ("before", "after"):
        pdf, png = tmp_path / f"{name}.pdf", tmp_path / f"{name}.png"
        pdf.write_bytes(b"pdf bytes differ from appearance contract: " + name.encode())
        pixels = Image.new("RGB", (12, 12), "white")
        if name == "after" and change == "pixel":
            pixels.putpixel((4, 6), (0, 0, 0))
        pixels.save(png)
        snapshots.append(
            {
                "pdf": str(pdf),
                "png": str(png),
                "sha256": {
                    "pdf": probe.prepared._sha(pdf),
                    "png": probe.prepared._sha(png),
                },
                "page_size_pt": [12, 12],
                "glyphs": [{"text": "A", "box_pt": [1.0, 2.0, 3.0, 4.0]}],
            }
        )
    if change == "glyph":
        snapshots[1]["glyphs"][0]["box_pt"][0] += 1e-12
    if change == "page":
        snapshots[1]["page_size_pt"][0] = 13
    if change == "file":
        Path(snapshots[0]["pdf"]).write_bytes(b"unexpected mutation")
    if change == "none":
        assert probe.compare_printed(*snapshots)["changed_pixel_count"] == 0
        return
    with pytest.raises(RuntimeError):
        probe.compare_printed(*snapshots)


def test_printed_policy_rejects_untyped_selector_before_work(scene):
    with pytest.raises(ValueError, match="policy enum"):
        scene.run(printed_format="compare")
    assert not scene.created


def test_normal_to_prepared_difference_stops_before_hit_without_weakening(scene):
    scene.faults["prepared_mismatch"] = True
    with pytest.raises(ExceptionGroup):
        scene.run()
    report, _ = scene.report()
    assert [row["kind"] for row in report["accessors"]] == ["miss"]
    assert report["accessors"][0]["status"] == "passed"
    assert (
        report["accessors"][0]["normal_receipt_comparison"]
        == "different_scale_compare_requested_factory_trial"
    )
    assert report["trials"][-1]["status"] == "failed"
    assert report["trials"][-1]["failed_phase"] == "raw_defaults"
    assert len(scene.created) == 4
    assert scene.native.app.documents == scene.baseline


def test_distinct_new_document_pan_is_rejected_by_unchanged_normal_control(scene):
    scene.faults["different_viewport_extents"] = True
    with pytest.raises(ExceptionGroup):
        scene.run()
    report, _ = scene.report()
    assert report["status"] == "failed"
    assert report["accessors"][0]["status"] == "passed"
    assert report["trials"][-1]["status"] == "failed"
    assert report["trials"][-1]["failed_phase"] == "raw_defaults"
    assert scene.viewport_calls == [
        ("redraw", 1.0),
        ("scale", 1.0),
        ("translation", (0.02, 0.002, 0.0)),
        ("redraw", 1.0),
    ]
    assert all(
        "viewport_control" not in row
        for row in (*report["operation_scopes"], *report["trials"])
    )
    receipt = json.loads(
        (Path(report["accessors"][0]["directory"]) / "receipt.json").read_text()
    )
    assert receipt["viewport_before"] == receipt["viewport_restore"]["after"]
    assert receipt["before"] == receipt["after"]


def test_captured_viewport_applies_to_both_prepare_creates_and_miss_hit_trials(
    scene, monkeypatch
):
    monkeypatch.setattr(probe.viewports, "_early_bound", lambda value, _: value)
    scene.faults["different_viewport_extents"] = True
    exports = []
    monkeypatch.setattr(
        probe,
        "printed_witness",
        lambda adapter, directory: (
            exports.append(directory.name) or {"pdf": "captured"}
        ),
    )
    monkeypatch.setattr(
        probe, "compare_printed", lambda *args: {"changed_pixel_count": 0}
    )
    scene.run(
        viewport=probe.Viewport.CAPTURED, printed_format=probe.PrintedFormat.COMPARE
    )
    report, _ = scene.report()
    assert report["status"] == "passed"
    assert exports == ["normal", "prepared_miss", "prepared_hit"]
    restore_calls = ["scale", "translation", "redraw"]
    assert [call[0] for call in scene.viewport_calls] == (
        restore_calls * 2 + ["redraw"] + restore_calls * 3
    )  # Both CREATE scopes exit before the new production verification redraw.
    controls = [
        row["viewport_control"]
        for row in report["operation_scopes"]
        if row["operation"] == "create"
    ]
    controls += [row["viewport_control"] for row in report["trials"][1:]]
    assert len(controls) == 4
    assert all(row["after"] == report["captured_viewport"] for row in controls)
    assert len(scene.created) == 5 and len(scene.saves) == 1
    assert scene.native.app.documents == scene.baseline


@pytest.mark.parametrize(
    "fault", ["orientation", "translation_readback", "independent_extent_drift"]
)
def test_captured_viewport_does_not_waive_wrong_orientation_pan_or_raw_extent(
    scene, monkeypatch, fault
):
    monkeypatch.setattr(probe.viewports, "_early_bound", lambda value, _: value)
    scene.faults[fault] = True
    with pytest.raises(ExceptionGroup):
        scene.run(viewport=probe.Viewport.CAPTURED)
    report, _ = scene.report()
    assert report["status"] == "failed"
    assert [row["kind"] for row in report["accessors"]] == ["miss"]
    assert scene.native.app.documents == scene.baseline
    if fault == "orientation":
        assert scene.viewport_calls == []


def test_changed_source_is_recorded_and_never_reset(scene):
    scene.faults["original_mutation"] = True
    with pytest.raises(ExceptionGroup):
        scene.run()
    report, _ = scene.report()
    assert report["status"] == "failed"
    assert "immutable" in report["final_guard_error"]
    assert scene.original.read_bytes() == b"changed source; never reset"


def test_corrupted_published_cache_stops_before_hit(scene, monkeypatch):
    original_trial = probe.trial

    async def corrupt(adapter, spec, entry, directory, row, expected, checkpoint):
        await original_trial(adapter, spec, entry, directory, row, expected, checkpoint)
        if row["variant"] == "prepared_miss":
            entry.path.write_bytes(b"corrupted output")

    monkeypatch.setattr(probe, "trial", corrupt)
    with pytest.raises(ExceptionGroup):
        scene.run()
    report, _ = scene.report()
    assert len(report["accessors"]) == 1
    assert "immutable" in report["final_guard_error"]


@pytest.mark.parametrize(
    "name,value",
    [
        ("HARMONIC_SW_AUTOSTART", "1"),
        ("HARMONIC_DIAGNOSTIC_SW_PID", "456"),
        ("HARMONIC_REMOTE_CACHE_MODE", "rw"),
    ],
)
def test_parent_environment_guards_precede_dodo_or_native(
    scene, monkeypatch, name, value
):
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError):
        probe.main(["--expected-pid", "123"])
    assert scene.created == []


def test_wrong_running_pid_stops_before_files_or_native_creation(scene):
    scene.native.app.GetProcessID = lambda: 456
    with pytest.raises(RuntimeError, match="approved PID"):
        scene.run()
    assert not scene.created


def test_parent_uses_machine_seat_and_forwards_exact_pid(scene, monkeypatch):
    import dodo

    calls = []
    monkeypatch.setattr(dodo, "_run", lambda *a, **k: calls.append((a, k)))
    assert (
        probe.main(["--expected-pid", "123", "--scale", "2", "1", "--decimals", "2"])
        == 0
    )
    command = calls[0][0][0]
    assert command[command.index("--expected-pid") + 1] == "123"
    assert command[-1] == "--worker"
    assert calls[0][1]["com"] is True
    assert not scene.created


def test_ownership_evidence_retains_live_event_list(scene):
    guarded = owned.DiagnosticAdapter(scene.native.adapter)
    captured = guarded.ownership.evidence()
    assert captured["events"] is guarded.ownership.events
    guarded.ownership.events.append(
        {"operation": "checkpoint_failed", "errors": ["proof"]}
    )
    assert captured["events"][-1]["errors"] == ["proof"]


def test_relocation_receipt_write_failure_cannot_replace_validation_error(
    scene, monkeypatch
):
    original = owned.DiagnosticDocuments.relocate_prepared_template_directory
    write = Path.write_text

    def invalid(self, previous, entry):
        receipt = entry.directory / "receipt.json"
        receipt.write_text(receipt.read_text() + "\n")
        denied = Path(previous).parent.parent / "ownership.json"

        def fail_one(path, *args, **kwargs):
            if path == denied:
                raise PermissionError("refused audit write")
            return write(path, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", fail_one)
        return original(self, previous, entry)

    monkeypatch.setattr(
        owned.DiagnosticDocuments, "relocate_prepared_template_directory", invalid
    )
    with pytest.raises(ExceptionGroup) as caught:
        scene.run()
    assert "receipt hash differs" in repr(caught.value)
    assert "refused audit write" in repr(caught.value)
    report, directory = scene.report()
    assert "receipt hash differs" in report["accessors"][0]["error"]
    assert "refused audit write" in report["accessors"][0]["error"]
    retained = json.loads((directory / "normal/ownership.json").read_text())
    row = next(
        item
        for item in retained["events"]
        if item["operation"] == "relocate_prepared_template"
    )
    assert "receipt hash differs" in row["error"]
    assert "refused audit write" in row["persistence_errors"][0]


@pytest.mark.parametrize(
    "case,expected",
    [
        ("live_owned", "live owned/baseline"),
        ("baseline", "live owned/baseline"),
        ("source", "protected source"),
        ("frozen", "protected source"),
        ("unrelated_target", "exact registered pending-cache"),
        ("copied_replacement", "bytes/identity"),
        ("missing_receipt", "invalid prepared template"),
        ("mismatched_receipt", "receipt hash differs"),
        ("missing_closed_witness", "closed native DRWDOT"),
        ("changed_current", "current-document ownership changed"),
    ],
)
def test_relocation_rejects_unproven_identity_and_retains_failure(
    scene, monkeypatch, case, expected
):
    original = owned.DiagnosticDocuments.relocate_prepared_template_directory
    observed = {}

    def invalid(self, previous, entry):
        before_directories = set(self.directories)
        before_closed = dict(self.closed_artifacts)
        target = entry.path
        if case in {"live_owned", "baseline"}:
            model = Model(target, title="Unexpected reopened template")
            scene.native.app.documents.append(model)
            category = (
                owned.Ownership.COPY
                if case == "live_owned"
                else owned.Ownership.BASELINE
            )
            self.records.append(
                owned.NativeDocument(model, category, owned._state(model), {target})
            )
        if case == "source":
            self.sources[target] = owned._digest(target)
        if case == "frozen":
            self.frozen_inputs[target] = {
                "sha256": owned._digest(target),
                "file_identity": owned._file_identity(target),
            }
        if case == "unrelated_target":
            unrelated = entry.directory.parent.parent / entry.key
            unrelated.mkdir()
            entry = replace(entry, directory=unrelated)
        if case == "copied_replacement":
            replacement = target.with_name("replacement.DRWDOT")
            replacement.write_bytes(target.read_bytes())
            replacement.replace(target)
        if case == "missing_receipt":
            (entry.directory / "receipt.json").unlink()
        if case == "mismatched_receipt":
            receipt = entry.directory / "receipt.json"
            receipt.write_text(receipt.read_text() + "\n")
        if case == "missing_closed_witness":
            self.closed_artifacts.pop(Path(previous) / "prepared.DRWDOT")
            before_closed = dict(self.closed_artifacts)
        if case == "changed_current":
            self.adapter.currentModel = scene.baseline[0]
        try:
            original(self, previous, entry)
        except Exception as error:
            observed["error"] = repr(error)
            assert self.directories == before_directories
            assert self.closed_artifacts == before_closed
            raise
        pytest.fail("invalid relocation was accepted")

    monkeypatch.setattr(
        owned.DiagnosticDocuments, "relocate_prepared_template_directory", invalid
    )
    # Both the primary validation and failed final checkpoint remain failures.
    with pytest.raises(ExceptionGroup) as caught:
        scene.run()
    assert expected in repr(caught.value)
    assert "ownership checkpoints failed" in repr(caught.value)
    assert expected in observed["error"]
    report, directory = scene.report()
    assert report["status"] == "failed"
    assert expected in report["accessors"][0]["error"]
    evidence = json.loads((directory / "ownership.json").read_text())
    relocation = next(
        row
        for row in evidence["events"]
        if row["operation"] == "relocate_prepared_template"
    )
    assert relocation["status"] == "failed" and expected in relocation["error"]
    assert any(row["operation"] == "checkpoint_failed" for row in evidence["events"])
    assert all(model not in scene.native.app.closes for model in scene.baseline)
