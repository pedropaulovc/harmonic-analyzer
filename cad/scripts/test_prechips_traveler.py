"""Wrapper contracts against the installed prechips CLI, without SolidWorks.

The plans here are literal-only (no ``[cad]`` table). Real prechips runs map
both traveler files to a custom profile with ``enforce = []``, so they need no
feature export; the build's own pro/hobby mapping is checked by command shape.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

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

    def smoke_profiles() -> None:
        monkeypatch.setattr(
            plans, "TRAVELER_PROFILES", {name: str(profile) for name in plans.TRAVELER_PROFILES},
        )

    return tmp_path / "out", smoke_profiles, author


def test_literal_plan_writes_both_standalone_travelers(process):
    out, smoke_profiles, author = process
    author("smoke_part", _LITERAL_PLAN)
    smoke_profiles()
    assert wrapper.main(["smoke_part", "--out", str(out)]) == 0
    paths = plans.traveler_paths("smoke_part", out)
    for path in paths:
        assert "Smoke plate" in path.read_text(encoding="utf-8")
    assert sorted(path.name for path in paths[0].parent.iterdir()) == [
        "traveler-hobby.html", "traveler.html",
    ]
    assert plans.traveler_complete("smoke_part", out)


def test_refusal_propagates_and_removes_previous_travelers(process):
    out, smoke_profiles, author = process
    author("refused_part", '[cad]\nfile = "missing.toml"\nadapter = "unsupported"\n')
    smoke_profiles()
    paths = plans.traveler_paths("refused_part", out)
    paths[0].parent.mkdir(parents=True)
    for path in paths:
        path.write_text("previous success", encoding="utf-8")
    assert wrapper.main(["refused_part", "--out", str(out)]) == 2
    assert not any(path.exists() for path in paths)


def test_hobby_refusal_removes_the_pro_traveler(process, monkeypatch):
    out, _smoke_profiles, author = process
    author("smoke_part", _LITERAL_PLAN)

    def run(cmd, **kwargs):
        if cmd[cmd.index("--profile") + 1] == "pro":
            Path(cmd[cmd.index("--out") + 1]).write_text("pro", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0)
        return subprocess.CompletedProcess(cmd, 2)

    monkeypatch.setattr(wrapper.subprocess, "run", run)
    assert wrapper.main(["smoke_part", "--out", str(out)]) == 2
    assert not any(path.exists() for path in plans.traveler_paths("smoke_part", out))


def test_missing_plan_fails_without_running_prechips(process, monkeypatch):
    out, _smoke_profiles, _author = process
    monkeypatch.setattr(
        wrapper.subprocess, "run",
        lambda *args, **kwargs: pytest.fail("prechips ran without a plan"),
    )
    assert wrapper.main(["unplanned_part", "--out", str(out)]) == 2
    assert not plans.traveler_complete("unplanned_part", out)


def test_build_runs_pro_then_hobby_from_the_same_plan(process, monkeypatch):
    out, _smoke_profiles, author = process
    author("smoke_part", _LITERAL_PLAN)
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(wrapper.subprocess, "run", run)
    assert wrapper.main(["smoke_part", "--out", str(out)]) == 0
    pro, hobby = plans.traveler_paths("smoke_part", out)
    head = ["-m", "prechips", "traveler", str(plans.plan_path("smoke_part"))]
    assert [cmd[1:] for cmd in calls] == [
        [*head, "--profile", "pro", "--out", str(pro)],
        [*head, "--profile", "hobby", "--out", str(hobby)],
    ]
