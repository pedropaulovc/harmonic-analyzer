"""Final evidence failures must not erase the original crank-arm probe failure."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import probe_crank_arm_entities as probe
from test_crank_arm_entities_drawing import native as native


@pytest.mark.parametrize("operation", ["success", "failure"])
@pytest.mark.parametrize("field", ["source", "token", "both"])
@pytest.mark.parametrize("fault", ["unreadable", "changed"])
def test_source_capture_retains_report_and_primary_when_final_reads_fail(
    native, monkeypatch, operation, field, fault
):
    primary = RuntimeError("original native snapshot failed")
    failures = {"source": OSError("source cannot be read"), "token": OSError("token cannot be read")}
    reads = []
    real_sha, real_read_text = probe.sha, Path.read_text
    pin = probe.EXPECTED_SOURCE_SHA

    def final_value(name, read):
        reads.append(name)
        if field not in {name, "both"}:
            return read()
        if fault == "unreadable":
            raise failures[name]
        return "changed-but-matching-source-and-token"

    def snapshot(*_args, **_kwargs):
        # Provenance already succeeded. Only the final readbacks are corrupted.
        monkeypatch.setattr(probe, "sha", lambda path: final_value("source", lambda: real_sha(path)))

        def read_text(path, *args, **kwargs):
            if path == native.token:
                return final_value("token", lambda: real_read_text(path, *args, **kwargs))
            return real_read_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read_text)
        if operation == "failure":
            raise primary
        return native.observed, {}

    native.snapshot.side_effect = snapshot
    with pytest.raises(ExceptionGroup) as raised:
        asyncio.run(probe.capture_source(native.adapter, native.directory))
    assert reads == ["source", "token"], "one failed read must not skip the other"
    assert probe.EXPECTED_SOURCE_SHA == pin
    report = json.loads((native.directory / "measurements.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["provenance"]["source_sha256"] == report["provenance"]["execution_token"] == pin
    errors = list(raised.value.exceptions)
    if operation == "failure":
        assert errors.pop(0) is primary
        assert report["error"] == repr(primary)
    if operation == "success":
        assert "error" not in report
        assert report["source_snapshot"]["observed_dimensions"]["configuration"] == "Default"
    assert report["final_errors"] == [repr(error) for error in errors]
    affected = [name for name in ("source", "token") if field in {name, "both"}]
    assert len(errors) == len(affected)
    for name, report_field in (("source", "source_sha256_after"), ("token", "execution_token_after")):
        if name not in affected:
            assert report[report_field] == pin
            continue
        error = errors[affected.index(name)]
        assert report[report_field] == {"error": repr(error)}
        if fault == "unreadable":
            assert error is failures[name]
        if fault == "changed":
            assert isinstance(error, RuntimeError)
            assert report_field in str(error)


@pytest.mark.parametrize("final_fault", ["none", "source_unreadable"])
def test_source_report_write_failure_preserves_original_and_all_final_errors(
    native, monkeypatch, final_fault
):
    primary = RuntimeError("primary source dimension failure")
    unreadable = OSError("final source hash unavailable")
    persistence = OSError("report storage unavailable")
    attempts = []
    real_write_text = Path.write_text

    def snapshot(*_args, **_kwargs):
        if final_fault == "source_unreadable":
            monkeypatch.setattr(probe, "sha", Mock(side_effect=unreadable))
        raise primary

    def write_text(path, text, *args, **kwargs):
        if path == native.directory / "measurements.json":
            attempts.append(json.loads(text))
            raise persistence
        return real_write_text(path, text, *args, **kwargs)

    native.snapshot.side_effect = snapshot
    monkeypatch.setattr(Path, "write_text", write_text)
    with pytest.raises(ExceptionGroup) as raised:
        asyncio.run(probe.capture_source(native.adapter, native.directory))
    assert raised.value.exceptions[0] is primary
    assert len(attempts) == 1
    assert attempts[0]["status"] == "failed"
    assert attempts[0]["error"] == repr(primary)
    assert attempts[0]["execution_token_after"] == probe.EXPECTED_SOURCE_SHA

    def leaves(error):
        if isinstance(error, ExceptionGroup):
            return [leaf for child in error.exceptions for leaf in leaves(child)]
        return [error]

    assert leaves(raised.value)[-1] is persistence
    if final_fault == "source_unreadable":
        assert raised.value.exceptions[1] is unreadable
        assert attempts[0]["final_errors"] == [repr(unreadable)]


def test_positive_control_attempts_all_final_guards_and_reports_primary_first(native, monkeypatch):
    from diagnostics import benchmark_drawing_recipes as benchmark
    from diagnostics import _recipe_template_factory as templates

    primary = RuntimeError("positive-control template configuration failed")
    guard = RuntimeError("template guard failed")
    original_error = OSError("original source unreadable")
    copy_error = OSError("source copy unreadable")
    token_error = OSError("original token unreadable")
    events, checkpoints = [], []
    real_read_text, real_persist = Path.read_text, probe.persist_report

    async def configure(*_args):
        def hash_after(path):
            if path == native.source:
                events.append("original")
                raise original_error
            events.append("copy")
            raise copy_error

        def read_text(path, *args, **kwargs):
            if path == native.token:
                events.append("token")
                raise token_error
            return real_read_text(path, *args, **kwargs)

        monkeypatch.setattr(probe, "sha", hash_after)
        monkeypatch.setattr(Path, "read_text", read_text)
        raise primary

    def guards():
        events.append("guards")
        return [guard]

    controller = SimpleNamespace(configure=configure, final_guards=guards, guards={"fixture": "failed"})
    monkeypatch.setattr(templates, "RecipeTemplateFactory", lambda _kind: controller)
    monkeypatch.setattr(benchmark, "load_recipe", Mock(return_value=object()))
    native.adapter.ownership.assert_current_owned = Mock()

    def persist(path, report):
        checkpoints.append(deepcopy(report))
        return real_persist(path, report)

    monkeypatch.setattr(probe, "persist_report", persist)
    with pytest.raises(ExceptionGroup) as raised:
        asyncio.run(probe.positive_control(native.adapter, native.directory))
    assert events == ["guards", "copy", "original", "token"]
    assert raised.value.exceptions[0] is primary
    template_group, *other_errors = raised.value.exceptions[1:]
    assert template_group.exceptions == (guard,)
    assert other_errors == [copy_error, original_error, token_error]
    report = json.loads((native.directory / "measurements.json").read_text(encoding="utf-8"))
    assert len(checkpoints) == 2 and checkpoints[0]["status"] == "running"
    assert report["status"] == "failed" and report["error"] == repr(primary)
    assert report["template_guard_details"] == {"fixture": "failed"}
    assert len(report["final_errors"]) == 4
    for field, error in (
        ("template_guards", template_group),
        ("source_copy_sha256_after", copy_error),
        ("source_original_sha256_after", original_error),
        ("execution_token_after", token_error),
    ):
        assert report[field] == {"error": repr(error)}
