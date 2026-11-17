"""Reject undefined names in build orchestration and CAD scripts without SolidWorks."""

from __future__ import annotations

from pathlib import Path

import pytest

from cad.scripts._undefined_names import scan_undefined_names

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_tracked_build_sources_have_no_undefined_names() -> None:
    result = scan_undefined_names(REPO_ROOT)
    assert result.returncode == 0, result.stdout + result.stderr


def test_farm_preflight_refuses_undefined_name_before_fleet_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
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

    monkeypatch.syspath_prepend(str(REPO_ROOT / "cad" / "scripts"))
    monkeypatch.syspath_prepend(str(REPO_ROOT))
    import farm_build

    monkeypatch.setattr(farm_build, "REPO_ROOT", tmp_path)

    def no_fleet_query(*args: object) -> None:
        pytest.fail("farm preflight queried the fleet before checking undefined names")

    monkeypatch.setattr(farm_build, "require_fleet_protocol", no_fleet_query)
    record = {
        "targets": ["local"],
        "pool_home": str(tmp_path / "no-pool"),
        "display_name": "Undefined-names negative control",
        "force_cache_refresh": [],
        "force_cache_refresh_reason": None,
    }
    namespace = {"task_local": lambda: {"actions": [lambda: pytest.fail("ran")]}}
    assert farm_build.run_farm_build(record, namespace) == 2
    error = capsys.readouterr().err
    assert "F821" in error
    assert "undefined_names_gate_negative_control" in error
