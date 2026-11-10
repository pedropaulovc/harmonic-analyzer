"""Wrapper contracts against the installed prechips CLI, without SolidWorks.

The plans here are literal-only (no ``[cad]`` table) under a custom profile
with ``enforce = []``, so a real prechips run needs no feature export.
"""

from __future__ import annotations

import subprocess

import pytest

import prechips_traveler as wrapper
import _process_plans as plans

_LITERAL_PLAN = """\
title = "Smoke plate"
part = "smoke-part"
revision = "v0"
material = "6061 aluminium"
stock = "1 plate"

[[tools]]
id = "file"
name = "Fine file"
description = "Fine-cut mill file."

[[setups]]
machine_kind = "other"
title = "Bench"
machine = "Bench"

[[setups.operations]]
tool = "file"
instruction = "Break edges."
"""


@pytest.fixture
def process(tmp_path, monkeypatch):
    root = tmp_path / "process"
    monkeypatch.setattr(plans, "PROCESS_ROOT", root)
    profile = tmp_path / "profile.toml"
    profile.write_text('name = "smoke"\nfeatures = []\nenforce = []\n', encoding="utf-8")

    def author(stem: str, text: str) -> None:
        plans.plan_path(stem).parent.mkdir(parents=True)
        plans.plan_path(stem).write_text(text, encoding="utf-8")

    return tmp_path / "out", str(profile), author


def test_literal_plan_writes_one_standalone_html(process):
    out, profile, author = process
    author("smoke_part", _LITERAL_PLAN)
    assert wrapper.main(["smoke_part", "--out", str(out), "--profile", profile]) == 0
    html = plans.traveler_html("smoke_part", out)
    assert "Smoke plate" in html.read_text(encoding="utf-8")
    assert sorted(path.name for path in html.parent.iterdir()) == ["traveler.html"]


def test_refusal_propagates_and_removes_previous_html(process):
    out, profile, author = process
    author("refused_part", '[cad]\nfile = "missing.toml"\nadapter = "unsupported"\n')
    html = plans.traveler_html("refused_part", out)
    html.parent.mkdir(parents=True)
    html.write_text("previous success", encoding="utf-8")
    assert wrapper.main(["refused_part", "--out", str(out), "--profile", profile]) == 2
    assert not html.exists()


def test_missing_plan_fails_without_running_prechips(process, monkeypatch):
    out, _profile, _author = process
    monkeypatch.setattr(
        wrapper.subprocess, "run",
        lambda *args, **kwargs: pytest.fail("prechips ran without a plan"),
    )
    assert wrapper.main(["unplanned_part", "--out", str(out)]) == 2
    assert not plans.traveler_complete("unplanned_part", out)


def test_build_runs_the_strict_pro_profile(process, monkeypatch):
    out, _profile, author = process
    author("smoke_part", _LITERAL_PLAN)
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(wrapper.subprocess, "run", run)
    assert wrapper.main(["smoke_part", "--out", str(out)]) == 0
    (cmd,) = calls
    assert cmd[1:5] == ["-m", "prechips", "traveler", str(plans.plan_path("smoke_part"))]
    assert cmd[5:] == [
        "--profile", "pro", "--out", str(plans.traveler_html("smoke_part", out)),
    ]
