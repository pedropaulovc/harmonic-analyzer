"""Wrapper contracts without a kernel, SolidWorks, or a real traveler run."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

import prechips_traveler as wrapper
import _process_plans as plans


@pytest.fixture
def wrapper_stubs(tmp_path, monkeypatch):
    out = tmp_path / "out"
    directory = out / "travelers" / "ch_rocker_arm"
    bound = directory / "plan.toml"
    shop = tuple(out / "travelers" / "_shop" / name for name in plans.SHOP_FILES)
    calls = {"cli": [], "capture": [], "verify": [], "kernel": []}
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
    monkeypatch.setattr(plans, "bind_plan", lambda stem, output: bound)
    monkeypatch.setattr(plans, "bind_shop", lambda output: shop)
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
        return calls.get("exit", 0)

    monkeypatch.setattr(wrapper.cli, "main", cli)
    return out, directory, bound, shop, calls, tracing


@pytest.mark.parametrize("code", [2, 3, 4, 7])
def test_cli_nonzero_exit_is_unchanged(wrapper_stubs, code):
    out, _, _, _, calls, _ = wrapper_stubs
    calls["exit"] = code
    assert wrapper.main(["ch_rocker_arm", "--out", str(out)]) == code
    assert not calls["verify"]


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


def test_check_mode_does_not_require_rendered_outputs(wrapper_stubs):
    out, _, _, _, calls, _ = wrapper_stubs
    assert wrapper.main(["ch_rocker_arm", "--out", str(out), "--check"]) == 0
    assert calls["cli"][0][0] == "check"
    assert not calls["verify"]


@pytest.mark.parametrize("binding", ["bind_plan", "bind_shop"])
def test_binding_failure_returns_bad_input_without_running_cli(
    wrapper_stubs, monkeypatch, binding
):
    out, _, _, _, calls, _ = wrapper_stubs
    errors = []
    monkeypatch.setattr(wrapper._telemetry, "error", errors.append)

    def fail(*args, **kwargs):
        raise plans.PlanBindError("synthetic plan.toml:9: unknown label")

    monkeypatch.setattr(plans, binding, fail)
    if hasattr(wrapper, binding):
        monkeypatch.setattr(wrapper, binding, fail)
    assert wrapper.main(["ch_rocker_arm", "--out", str(out)]) == 3
    assert not calls["cli"]
    assert not calls["verify"]
    assert any("9" in error and "unknown label" in error for error in errors)


def test_zero_exit_with_incomplete_traveler_is_failure(wrapper_stubs, monkeypatch):
    out, _, _, _, calls, _ = wrapper_stubs

    def fail(*args, **kwargs):
        raise plans.TravelerIncomplete("missing setup-S1.png")

    monkeypatch.setattr(plans, "verify_traveler", fail)
    if hasattr(wrapper, "verify_traveler"):
        monkeypatch.setattr(wrapper, "verify_traveler", fail)
    assert wrapper.main(["ch_rocker_arm", "--out", str(out)]) == 1
    assert calls["cli"]
