"""All-scale control composition uses the real ownership and cache state machines."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from diagnostics import _owned_native_documents as owned
from diagnostics import probe_canonical_template_scales as fleet
from diagnostics import probe_prepared_template_cache as cache
from test_prepared_template_cache_probe_drawing import scene  # noqa: F401
from test_owned_native_documents_drawing import native  # noqa: F401


@pytest.fixture
def control(scene, monkeypatch, tmp_path):  # noqa: F811
    original_snapshot = cache.snapshot_defaults
    prints = []

    async def reopen(path):
        scene.native.adapter.opens.append(path)
        model = type(scene.created[-1])(path)
        scene.native.app.documents.append(model)
        scene.native.adapter.currentModel = scene.native.app.ActiveDoc = model
        return SimpleNamespace(is_success=True, data=None)

    def snapshot(adapter, spec):
        result = original_snapshot(adapter, spec)
        result["requested_scale"] = list(spec.scale)
        if (
            scene.faults.get("cold_raw")
            and adapter.currentModel.path
            and scene.native.adapter.opens
        ):
            result["units"]["decimals"] += 1
        return result

    def printed(adapter, directory):
        prints.append(directory)
        result = {"glyphs": ["TITLE", '$PRPSHEET:"Material"']}
        if scene.faults.get("cold_print") and adapter.currentModel.path:
            result["glyphs"][0] = "MISSING"
        return result

    def compare_printed(before, after):
        if before != after:
            raise RuntimeError("exact printed glyph comparison failed")
        return {"changed_pixel_count": 0}

    monkeypatch.setattr(scene.native.adapter, "open_model", reopen)
    monkeypatch.setattr(cache, "snapshot_defaults", snapshot)
    monkeypatch.setattr(cache.prepared, "snapshot_defaults", snapshot)
    monkeypatch.setattr(cache, "printed_witness", printed)
    monkeypatch.setattr(cache, "compare_printed", compare_printed)
    monkeypatch.setattr(
        fleet,
        "runtime_inputs",
        lambda *_: {"frozen": scene.faults.get("runtime", "same")},
    )
    reports = tmp_path / "fleet-reports"

    def run():
        return asyncio.run(
            owned.owned_callback(
                scene.native.adapter, lambda adapter: fleet.probe(adapter, reports, 123)
            )
        )

    def report():
        paths = list(reports.glob("*/measurements.json"))
        assert len(paths) == 1
        return json.loads(paths[0].read_text()), paths[0].parent

    return SimpleNamespace(scene=scene, run=run, report=report, prints=prints)


def test_all_fifteen_actual_specs_share_one_base_and_compare_same_requested_scales(
    control,
):
    expected = fleet.registered_specs()
    assert len(expected) == 15
    control.run()
    report, directory = control.report()
    assert report["status"] == "passed"
    assert [tuple(row["spec"]["scale"]) for row in report["pairs"]] == [
        spec.scale for spec in expected
    ]
    assert len(report["preparations"]) == 1
    assert [row["kind"] for row in report["preparations"][0]["accessors"]] == [
        "miss",
        "hit",
    ]
    assert len({row["base_key"] for row in report["pairs"]}) == 1
    for pair in report["pairs"]:
        assert pair["status"] == "passed"
        for variant in ("normal", "canonical"):
            row = pair[variant]
            assert row["status"] == row["cold"]["status"] == "passed"
            assert row["defaults"]["requested_scale"] == pair["spec"]["scale"]
            assert row["cold"]["defaults"] == row["defaults"]
            assert row["cold"]["sha256_before"] == row["cold"]["sha256_after_cleanup"]
            assert row["cold"]["printed_delta"]["changed_pixel_count"] == 0
            assert row["setup_seconds"] >= 0 and row["cold"]["save_seconds"] >= 0
    assert len(control.scene.native.adapter.opens) == 30
    assert (
        len(control.scene.saves) == 31
    )  # Thirty trial drawings; one canonical DRWDOT.
    assert len(control.prints) == 60
    assert control.scene.native.app.documents == control.scene.baseline
    assert all(
        Path(path).suffix == ".SLDDRW" for path in control.scene.native.adapter.opens
    )
    assert control.scene.original.read_bytes() == b"immutable source template"
    ownership = json.loads((directory / "ownership.json").read_text())
    assert ownership["baseline_preservation"]["status"] == "preserved"
    assert len(report["guards"][-1]["native_files"]) == 30


@pytest.mark.parametrize("fault", ["cold_raw", "cold_print", "original_mutation"])
def test_first_failed_cold_or_source_gate_stops_before_preparation_and_preserves_baseline(
    control, fault
):
    control.scene.faults[fault] = True
    with pytest.raises(ExceptionGroup):
        control.run()
    report, _ = control.report()
    assert report["status"] == "failed"
    assert len(report["pairs"]) == 1 and report["preparations"] == []
    assert "canonical" not in report["pairs"][0]
    assert control.scene.native.app.documents == control.scene.baseline
    if fault == "original_mutation":
        assert "original template changed" in report["final_guard_error"]
        assert control.scene.original.read_bytes() == b"changed source; never reset"
    else:
        assert report["pairs"][0]["normal"]["cold"]["status"] == "failed"
        assert report["pairs"][0]["normal"]["cold"]["failed_phase"] == (
            "cold_defaults" if fault == "cold_raw" else "cold_print"
        )
        assert control.scene.original.read_bytes() == b"immutable source template"


def test_noncanonical_default_change_is_rejected_at_same_scale_before_second_pair(
    control,
):
    control.scene.faults["prepared_mismatch"] = True
    with pytest.raises(ExceptionGroup):
        control.run()
    report, _ = control.report()
    assert len(report["pairs"]) == 1
    assert report["pairs"][0]["normal"]["status"] == "passed"
    assert report["pairs"][0]["canonical"]["failed_phase"] == "raw_defaults"
    assert control.scene.native.app.documents == control.scene.baseline


def test_failure_and_final_runtime_guard_both_survive(control, monkeypatch):
    def rejected(*_):
        control.scene.faults["runtime"] = "changed"
        raise RuntimeError("original printed failure")

    monkeypatch.setattr(cache, "printed_witness", rejected)
    with pytest.raises(ExceptionGroup):
        control.run()
    report, _ = control.report()
    assert "original printed failure" in report["error"]
    assert "runtime" in report["final_guard_error"]
    assert control.scene.native.app.documents == control.scene.baseline


def test_cold_viewport_getter_cannot_switch_to_baseline_before_restore(
    control, monkeypatch
):
    capture = cache.viewports.capture
    restores = []
    restore = cache.viewports.restore

    def switched(model):
        result = capture(model)
        if model.path.endswith(".SLDDRW"):
            control.scene.native.app.ActiveDoc = control.scene.baseline[-1]
            control.scene.native.adapter.currentModel = control.scene.baseline[-1]
        return result

    def record(*args):
        restores.append(args[1])
        return restore(*args)

    monkeypatch.setattr(cache.viewports, "capture", switched)
    monkeypatch.setattr(cache.viewports, "restore", record)
    with pytest.raises(ExceptionGroup):
        control.run()
    report, _ = control.report()
    assert report["pairs"][0]["normal"]["cold"]["status"] == "failed"
    assert not restores
    assert all(
        doc not in control.scene.native.app.closes for doc in control.scene.baseline
    )


def test_cleanup_native_byte_change_remains_fatal(control, monkeypatch):
    close = control.scene.native.app.CloseDoc

    def mutate(name):
        model = next(
            doc for doc in control.scene.native.app.documents if doc.title == name
        )
        if model.path.endswith(".SLDDRW") and len(control.scene.native.adapter.opens):
            Path(model.path).write_bytes(b"changed on close; never reset")
        close(name)

    monkeypatch.setattr(control.scene.native.app, "CloseDoc", mutate)
    with pytest.raises(ExceptionGroup):
        control.run()
    report, _ = control.report()
    assert "cleanup_hash_error" in report["pairs"][0]["normal"]
    assert "saved blank bytes changed" in report["final_guard_error"]
    assert control.scene.native.app.documents == control.scene.baseline


def test_wrong_pid_refuses_before_creation_or_output(control, monkeypatch):
    monkeypatch.setattr(control.scene.native.app, "GetProcessID", lambda: 999)
    with pytest.raises(RuntimeError, match="PID"):
        control.run()
    assert not control.scene.created and not control.scene.saves


@pytest.mark.parametrize("state", ["0", "1", ""])
def test_parent_environment_is_checked_before_dodo(monkeypatch, state):
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", state)
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", "123")
    import dodo

    calls = []
    monkeypatch.setattr(dodo, "_run", lambda *a, **kw: calls.append((a, kw)))
    if state != "0":
        with pytest.raises(RuntimeError):
            fleet.main(["--expected-pid", "123"])
        assert not calls
        return
    fleet.main(["--expected-pid", "123"])
    assert len(calls) == 1 and calls[0][1]["com"] is True


def test_paired_printed_comparator_remains_exact():
    # Real cache comparator: glyph changes reject even when image pixels match.
    before = {
        "page_size_pt": [792, 612],
        "glyphs": [{"text": "A", "box_pt": [1, 2, 3, 4]}],
        "png": "unused",
    }
    after = deepcopy(before)
    after["glyphs"][0]["text"] = "B"
    with pytest.raises(RuntimeError):
        cache.compare_printed(before, after)


def test_noncanonical_failure_receipt_is_not_mislabeled_as_same_spec_replay():
    with pytest.raises(ValueError, match="not an exact replay"):
        cache.require_canonical_failure_pin(
            cache.prepared.TemplateSpec((4, 1)), {"receipt": "historical"}
        )
    cache.require_canonical_failure_pin(
        cache.prepared.TemplateSpec(), {"receipt": "canonical"}
    )
    cache.require_canonical_failure_pin(cache.prepared.TemplateSpec((4, 1)), None)
