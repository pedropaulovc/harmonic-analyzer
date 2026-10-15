"""Wrapper contracts without a kernel, SolidWorks, or a real traveler run."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from prechips.report import canonical_bytes, report_hash

import prechips_traveler as wrapper
import _process_plans as plans


@pytest.fixture
def wrapper_stubs(tmp_path, monkeypatch):
    out = tmp_path / "out"
    directory = out / "travelers" / "ch_rocker_arm"
    bound = directory / "plan.toml"
    shop = tuple(out / "travelers" / "_shop" / name for name in plans.SHOP_FILES)
    # A synthetic tracked shop: the HTML stamp counts its placeholders.
    tracked = tmp_path / "process" / "shop"
    tracked.mkdir(parents=True)
    for name in plans.SHOP_FILES:
        (tracked / name).write_text("version = 1\n", encoding="utf-8")
    monkeypatch.setattr(plans, "PROCESS_ROOT", tracked.parent)
    calls = {
        "cli": [],
        "capture": [],
        "verify": [],
        "kernel": [],
        "bind_plan": [],
        "bind_shop": [],
        "spans": [],
    }
    tracing = SimpleNamespace(
        trace_provider=object(),
        log_provider=object(),
        logger=logging.getLogger("test.prechips"),
    )
    monkeypatch.setattr(wrapper.telemetry, "configure", lambda *args, **kwargs: tracing)
    monkeypatch.setattr(
        wrapper._telemetry,
        "capture_external_telemetry",
        lambda *args: calls["capture"].append(args),
    )

    def bind_plan(stem, output, *, destination=None):
        calls["bind_plan"].append((stem, output, destination))
        return destination if destination is not None else bound

    def bind_shop(output, *, directory=None):
        calls["bind_shop"].append((output, directory))
        if directory is not None:
            return tuple(directory / name for name in plans.SHOP_FILES)
        # Like the real binder, install the shared shop the HTML stamp counts.
        shop[0].parent.mkdir(parents=True, exist_ok=True)
        for path in shop:
            path.write_text("version = 1\n", encoding="utf-8")
        return shop

    @contextmanager
    def span(name, **attributes):
        exceptions = []
        statuses = []
        current = SimpleNamespace(
            name=name,
            attributes=attributes,
            exceptions=exceptions,
            statuses=statuses,
            record_exception=exceptions.append,
            set_status=statuses.append,
        )
        calls["spans"].append(current)
        try:
            yield current
        except Exception as exc:
            current.record_exception(exc)
            current.set_status(
                wrapper._telemetry.Status(wrapper._telemetry.StatusCode.ERROR, str(exc))
            )
            raise

    monkeypatch.setattr(wrapper._telemetry, "run_pipeline_span", span)
    monkeypatch.setattr(wrapper._telemetry, "span", span)
    monkeypatch.setattr(plans, "bind_plan", bind_plan)
    monkeypatch.setattr(plans, "bind_shop", bind_shop)
    monkeypatch.setattr(plans, "traveler_dir", lambda stem, output: directory)
    monkeypatch.setattr(
        plans,
        "verify_traveler",
        lambda *args, **kwargs: calls["verify"].append((args, kwargs)),
    )
    # Patch directly imported helpers as well as their canonical module.
    for name in ("bind_plan", "bind_shop", "traveler_dir", "verify_traveler"):
        if hasattr(wrapper, name):
            monkeypatch.setattr(wrapper, name, getattr(plans, name))
    from prechips import kernel

    def discover():
        calls["kernel"].append(True)
        return "synthetic-freecad-kernel"

    monkeypatch.setattr(kernel, "discover_kernel", discover)
    if hasattr(wrapper, "discover_kernel"):
        monkeypatch.setattr(wrapper, "discover_kernel", discover)

    def cli(argv):
        calls["cli"].append(argv)
        if calls.get("exit", 0) == 0 and argv[0] == "traveler":
            directory.mkdir(parents=True, exist_ok=True)
            report = {"expected_exit": 0, "inputs": {}}
            report["hash"] = report_hash(report)
            (directory / "report.json").write_bytes(canonical_bytes(report))
            (directory / "traveler.html").write_text(
                '<html><meta name="prechips-report" '
                f'content="{report["hash"]}">synthetic traveler</html>',
                encoding="utf-8",
            )
        return calls.get("exit", 0)

    monkeypatch.setattr(wrapper.cli, "main", cli)
    return out, directory, bound, shop, calls, tracing


@pytest.mark.parametrize("code", [2, 3, 4, 7])
def test_cli_nonzero_exit_is_unchanged(wrapper_stubs, code):
    out, _, _, _, calls, _ = wrapper_stubs
    calls["exit"] = code
    assert wrapper.main(["ch_rocker_arm", "--out", str(out)]) == code
    assert not calls["verify"]
    root = calls["spans"][0]
    assert root.statuses[-1].status_code is wrapper._telemetry.StatusCode.ERROR
    assert str(code) in str(root.exceptions[-1])


def test_traveler_success_passes_bound_paths_and_captures_telemetry(
    wrapper_stubs, caplog, monkeypatch
):
    out, directory, bound, shop, calls, tracing = wrapper_stubs
    logs = []
    # Kernel discovery may use the repo logger rather than Python's logger.
    for name in ("info", "log"):
        if hasattr(wrapper._telemetry, name):
            monkeypatch.setattr(
                wrapper._telemetry, name, lambda *args, **kwargs: logs.append(str(args))
            )
    with caplog.at_level(logging.DEBUG):
        assert wrapper.main(["ch_rocker_arm", "--out", str(out)]) == 0
    assert calls["cli"] == [
        [
            "traveler",
            str(bound),
            "--inventory",
            str(shop[0]),
            "--policy",
            str(shop[1]),
            "--cutting-data",
            str(shop[2]),
            "--out",
            str(directory),
        ]
    ]
    assert calls["capture"] == [(tracing.trace_provider, tracing.log_provider)]
    assert calls["kernel"]
    assert "synthetic-freecad-kernel" in caplog.text + " ".join(logs)
    assert calls["verify"]
    assert calls["verify"][0][0] == ("ch_rocker_arm", out)
    report = json.loads((directory / "report.json").read_bytes())
    html_record = report["inputs"]["traveler:html"]
    assert html_record["path"] == "traveler.html"
    assert (
        html_record["sha256"]
        == hashlib.sha256((directory / "traveler.html").read_bytes()).hexdigest()
    )
    assert report["hash"] == report_hash(report)
    assert [span.name for span in calls["spans"]] == [
        "prechips_traveler",
        "prechips.bind",
        "prechips.verify",
    ]
    assert calls["spans"][0].attributes == {"stem": "ch_rocker_arm"}


def test_check_mode_does_not_require_rendered_outputs(wrapper_stubs):
    out, directory, _, _, calls, _ = wrapper_stubs
    assert wrapper.main(["ch_rocker_arm", "--out", str(out), "--check"]) == 0
    assert calls["cli"][0][0] == "check"
    assert not calls["verify"]
    scratch = directory / ".check"
    assert calls["bind_plan"] == [("ch_rocker_arm", out, scratch / "plan.toml")]
    assert calls["bind_shop"] == [(out, scratch / "_shop")]
    assert calls["cli"][0] == [
        "check",
        str(scratch / "plan.toml"),
        "--inventory",
        str(scratch / "_shop" / plans.SHOP_FILES[0]),
        "--policy",
        str(scratch / "_shop" / plans.SHOP_FILES[1]),
        "--cutting-data",
        str(scratch / "_shop" / plans.SHOP_FILES[2]),
        "--out",
        str(scratch),
    ]


@pytest.mark.parametrize("binding", ["bind_plan", "bind_shop"])
def test_binding_failure_returns_bad_input_without_running_cli(
    wrapper_stubs, monkeypatch, binding
):
    out, directory, _, _, calls, _ = wrapper_stubs
    directory.mkdir(parents=True)
    report = directory / "report.json"
    report.write_text('{"expected_exit": 0}', encoding="utf-8")
    errors = []
    monkeypatch.setattr(wrapper._telemetry, "error", errors.append)

    def fail(*args, **kwargs):
        assert not report.exists()
        raise plans.PlanBindError("synthetic plan.toml:9: unknown label")

    monkeypatch.setattr(plans, binding, fail)
    if hasattr(wrapper, binding):
        monkeypatch.setattr(wrapper, binding, fail)
    assert wrapper.main(["ch_rocker_arm", "--out", str(out)]) == 3
    assert not calls["cli"]
    assert not calls["verify"]
    assert any("9" in error and "unknown label" in error for error in errors)
    assert not report.exists()
    root = calls["spans"][0]
    assert root.statuses[-1].status_code is wrapper._telemetry.StatusCode.ERROR
    assert isinstance(root.exceptions[-1], plans.PlanBindError)


def test_zero_exit_with_incomplete_traveler_is_failure(wrapper_stubs, monkeypatch):
    out, _, _, _, calls, _ = wrapper_stubs

    def fail(*args, **kwargs):
        raise plans.TravelerIncomplete("missing setup-S1.png")

    monkeypatch.setattr(plans, "verify_traveler", fail)
    if hasattr(wrapper, "verify_traveler"):
        monkeypatch.setattr(wrapper, "verify_traveler", fail)
    assert wrapper.main(["ch_rocker_arm", "--out", str(out)]) == 1
    assert calls["cli"]
    assert calls["spans"][-1].name == "prechips.verify"
    root = calls["spans"][0]
    assert root.statuses[-1].status_code is wrapper._telemetry.StatusCode.ERROR
    assert isinstance(root.exceptions[-1], plans.TravelerIncomplete)


def test_zero_exit_without_fresh_html_cannot_certify_old_html(
    wrapper_stubs, monkeypatch
):
    out, directory, _, _, calls, _ = wrapper_stubs
    directory.mkdir(parents=True)
    html = directory / "traveler.html"
    html.write_bytes(b"old instructions")

    def no_html(argv):
        assert not html.exists()
        report = {"expected_exit": 0, "inputs": {}}
        report["hash"] = report_hash(report)
        (directory / "report.json").write_bytes(canonical_bytes(report))
        return 0

    monkeypatch.setattr(wrapper.cli, "main", no_html)
    assert wrapper.main(["ch_rocker_arm", "--out", str(out)]) == 1
    assert not html.exists()
    assert not calls["verify"]


def test_cli_bad_input_removes_old_success_report(wrapper_stubs, monkeypatch):
    out, directory, _, _, calls, _ = wrapper_stubs
    directory.mkdir(parents=True)
    report = directory / "report.json"
    report.write_text('{"expected_exit": 0}', encoding="utf-8")

    def bad_input(argv):
        assert not report.exists()
        return 3  # Bad input can return without producing a replacement report.

    monkeypatch.setattr(wrapper.cli, "main", bad_input)
    assert wrapper.main(["ch_rocker_arm", "--out", str(out)]) == 3
    assert not report.exists()
    assert not calls["verify"]


@pytest.mark.parametrize("code", [0, 3])
def test_check_preserves_full_generation_when_consumer_rewrites_outputs(
    wrapper_stubs, monkeypatch, code
):
    out, directory, bound, shop, calls, _ = wrapper_stubs
    original = {
        bound: b"previous bound plan",
        directory / "report.json": b'{"expected_exit": 0}',
        directory / "traveler.html": b"previous HTML",
        directory / "setup-S1.png": b"previous render",
        **{path: b"previous shop input" for path in shop},
    }
    for path, content in original.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    scratch = directory / ".check"
    scratch.mkdir()
    (scratch / "report.json").write_text("previous check", encoding="utf-8")

    def bind_plan(stem, output, *, destination=None):
        assert not (scratch / "report.json").exists()
        destination.write_text("edited authoring plan", encoding="utf-8")
        return destination

    def bind_shop(output, *, directory=None):
        directory.mkdir(parents=True, exist_ok=True)
        targets = tuple(directory / name for name in plans.SHOP_FILES)
        for target in targets:
            target.write_text("edited authoring shop", encoding="utf-8")
        return targets

    def check(argv):
        output = Path(argv[argv.index("--out") + 1])
        assert output == scratch
        for name in ("traveler.html", "setup-S1.png"):
            (output / name).write_text("temporary render", encoding="utf-8")
            (output / name).unlink()  # Model prechips check-mode render cleanup.
        (output / "report.json").write_text("fresh check", encoding="utf-8")
        return code

    monkeypatch.setattr(plans, "bind_plan", bind_plan)
    monkeypatch.setattr(plans, "bind_shop", bind_shop)
    monkeypatch.setattr(wrapper.cli, "main", check)
    assert wrapper.main(["ch_rocker_arm", "--out", str(out), "--check"]) == code
    assert {path: path.read_bytes() for path in original} == original
    assert not calls["verify"]


def test_unexpected_cli_exception_marks_pipeline_failed(wrapper_stubs, monkeypatch):
    out, _, _, _, calls, _ = wrapper_stubs
    failure = RuntimeError("synthetic consumer crash")

    def crash(argv):
        raise failure

    monkeypatch.setattr(wrapper.cli, "main", crash)
    with pytest.raises(RuntimeError, match="synthetic consumer crash"):
        wrapper.main(["ch_rocker_arm", "--out", str(out)])
    root = calls["spans"][0]
    assert root.exceptions == [failure]
    assert root.statuses[-1].status_code is wrapper._telemetry.StatusCode.ERROR
