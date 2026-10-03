"""Reject undefined names in build orchestration and CAD scripts without SolidWorks."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from cad.scripts._undefined_names import scan_undefined_names

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_tracked_build_sources_have_no_undefined_names() -> None:
    result = scan_undefined_names(REPO_ROOT)
    assert result.returncode == 0, result.stdout + result.stderr


def test_farm_preflight_refuses_undefined_name_before_fleet_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripts = tmp_path / "cad" / "scripts"
    scripts.mkdir(parents=True)
    # A throwaway copy of a real builder; never mutate the tracked original.
    source = REPO_ROOT / "cad" / "scripts" / "build_dt_crank_drive_gear.py"
    (scripts / source.name).write_bytes(
        source.read_bytes() + b"\nundefined_names_gate_negative_control()\n"
    )
    (tmp_path / "dodo.py").write_text("", encoding="utf-8")
    (tmp_path / "build.py").write_text("", encoding="utf-8")

    spec = importlib.util.spec_from_file_location("build", REPO_ROOT / "build.py")
    assert spec is not None and spec.loader is not None
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    monkeypatch.setattr(build, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        build, "_git", lambda *args: "" if args[0] == "status" else "a" * 40
    )
    monkeypatch.setattr(build, "_dirty_submodules", lambda: [])

    def no_fleet_query(*args: object) -> None:
        pytest.fail("farm preflight queried the fleet before checking undefined names")

    monkeypatch.setattr(build, "_require_fleet_protocol", no_fleet_query)
    with pytest.raises(build.FarmPreflightError, match="F821") as refusal:
        build._farm_preflight()
    assert "undefined_names_gate_negative_control" in str(refusal.value)
