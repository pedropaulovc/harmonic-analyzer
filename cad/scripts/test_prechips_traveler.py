"""Wrapper contracts for the opt-in prechips travelers, without SolidWorks or
network: every ``uv tool run`` call is stubbed at ``subprocess.run``."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import prechips_traveler as wrapper
import _process_plans as plans

_UV = "uv-under-test"
_VERSION = "9.9.9"


@pytest.fixture
def process(tmp_path, monkeypatch):
    monkeypatch.setattr(plans, "PROCESS_ROOT", tmp_path / "process")
    monkeypatch.setenv("UV", _UV)

    def author(stem: str) -> None:
        plans.plan_path(stem).parent.mkdir(parents=True)
        plans.plan_path(stem).write_text('title = "Smoke plate"\n', encoding="utf-8")

    return tmp_path / "out", author


def _uv_stub(monkeypatch, *, probe=None, traveler=None):
    """Route stubbed ``uv tool run`` calls: the ``@latest`` version probe, then
    each pinned ``prechips traveler`` run (writes its ``--out`` unless refused).
    ``traveler(profile)`` returns an exit code or ``(code, stderr)``."""
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        if f"{wrapper.PACKAGE}@latest" in cmd:
            return probe(cmd) if probe else subprocess.CompletedProcess(cmd, 0, f"{_VERSION}\n", "")
        profile = cmd[cmd.index("--profile") + 1]
        outcome = traveler(profile) if traveler else 0
        code, stderr = outcome if isinstance(outcome, tuple) else (outcome, "")
        if code == 0:
            Path(cmd[cmd.index("--out") + 1]).write_text(profile, encoding="utf-8")
        return subprocess.CompletedProcess(cmd, code, None, stderr)

    monkeypatch.setattr(wrapper.subprocess, "run", run)
    return calls


def test_latest_release_renders_pro_then_hobby_pinned_to_one_version(process, monkeypatch):
    out, author = process
    author("smoke_part")
    calls = _uv_stub(monkeypatch)
    assert wrapper.main(["smoke_part", "--out", str(out)]) == 0
    probe, *runs = calls
    assert probe[:5] == [_UV, "tool", "run", "--from", "prechips@latest"]
    pro, hobby = plans.traveler_paths("smoke_part", out)
    head = [_UV, "tool", "run", "--from", f"prechips=={_VERSION}", "prechips", "traveler",
            str(plans.plan_path("smoke_part"))]
    assert runs == [
        [*head, "--profile", "pro", "--out", str(pro)],
        [*head, "--profile", "hobby", "--out", str(hobby)],
    ]
    assert pro.read_text(encoding="utf-8") == "pro"
    assert hobby.read_text(encoding="utf-8") == "hobby"


def test_latest_version_reads_the_probe_output(monkeypatch):
    def run(cmd, **kwargs):
        assert cmd[:7] == [_UV, "tool", "run", "--from", "prechips@latest", "python", "-c"]
        return subprocess.CompletedProcess(cmd, 0, "0.9.0\r\n", "")

    monkeypatch.setattr(wrapper.subprocess, "run", run)
    assert wrapper.latest_version(_UV) == "0.9.0"


def test_refusal_propagates_and_removes_previous_travelers(process, monkeypatch):
    out, author = process
    author("refused_part")
    paths = plans.traveler_paths("refused_part", out)
    paths[0].parent.mkdir(parents=True)
    for path in paths:
        path.write_text("previous success", encoding="utf-8")
    calls = _uv_stub(
        monkeypatch, traveler=lambda profile: (2, "prechips: stock_fit: blank too short\n"),
    )
    assert wrapper.main(["refused_part", "--out", str(out)]) == 2
    assert not any(path.exists() for path in paths)
    assert len(calls) == 2  # the probe, then the refused pro run only


def test_hobby_refusal_removes_the_pro_traveler(process, monkeypatch):
    out, author = process
    author("smoke_part")
    _uv_stub(monkeypatch, traveler=lambda profile: 0 if profile == "pro" else 2)
    assert wrapper.main(["smoke_part", "--out", str(out)]) == 2
    assert not any(path.exists() for path in plans.traveler_paths("smoke_part", out))


# uv's own diagnostics, as uv 0.9.8 printed them when provoked on this host:
# an unreachable index exits 2 with ``error:``; an unresolvable pin exits 1 with ``×``.
@pytest.mark.parametrize(("code", "stderr"), [
    (2, "error: Failed to fetch: `https://pypi.org/simple/prechips/`\n"
        "  Caused by: Request failed after 3 retries\n"),
    (1, "  × No solution found when resolving tool dependencies:\n"
        "  ╰─▶ Because there is no version of prechips==9.9.9 and you require\n"),
])
def test_uv_failure_during_render_is_not_a_refusal(process, monkeypatch, code, stderr):
    out, author = process
    author("smoke_part")
    _uv_stub(monkeypatch, traveler=lambda profile: 0 if profile == "pro" else (code, stderr))
    assert wrapper.main(["smoke_part", "--out", str(out)]) == 1
    assert not any(path.exists() for path in plans.traveler_paths("smoke_part", out))
    assert wrapper.uv_error(stderr) is not None
    assert wrapper.uv_error("usage: prechips ...\nprechips: error: bad plan\n") is None


def test_missing_plan_fails_without_running_uv(process, monkeypatch):
    out, _author = process
    monkeypatch.setattr(
        wrapper.subprocess, "run",
        lambda *args, **kwargs: pytest.fail("uv ran without a plan"),
    )
    assert wrapper.main(["unplanned_part", "--out", str(out)]) == 2
    assert not any(path.exists() for path in plans.traveler_paths("unplanned_part", out))


def test_unreachable_pypi_fails_before_any_sheet(process, monkeypatch):
    out, author = process
    author("smoke_part")
    paths = plans.traveler_paths("smoke_part", out)
    paths[0].parent.mkdir(parents=True)
    paths[0].write_text("previous success", encoding="utf-8")
    calls = _uv_stub(
        monkeypatch,
        probe=lambda cmd: subprocess.CompletedProcess(cmd, 2, "", "error: Failed to fetch"),
    )
    assert wrapper.main(["smoke_part", "--out", str(out)]) == 1
    assert len(calls) == 1
    assert not any(path.exists() for path in paths)
    with pytest.raises(RuntimeError, match="network access to PyPI is required"):
        wrapper.latest_version(_UV)


def test_missing_uv_fails_clearly(process, monkeypatch):
    out, author = process
    author("smoke_part")
    monkeypatch.delenv("UV")
    monkeypatch.setattr(wrapper.shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        wrapper.subprocess, "run",
        lambda *args, **kwargs: pytest.fail("ran without uv"),
    )
    assert wrapper.main(["smoke_part", "--out", str(out)]) == 1
    with pytest.raises(RuntimeError, match="uv was not found"):
        wrapper._uv()
