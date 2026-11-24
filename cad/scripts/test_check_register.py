"""The check register: schema, agreement with the code, and the necessity
register's citations (tolerance-policy.md, "Checks in spec modules and tests")."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_register  # noqa: E402
from _paths import CAD_ROOT  # noqa: E402

_ENTRY = {
    "id": "C-01",
    "check": "RATIO_FLOOR",
    "kind": "mesh",
    "reason": "a tooth pair lets go",
    "source": "delegated ruling 2026-11-11 (Main), issue #2416",
    "basis": "after_setting",
}


def _tree(tmp_path: Path, entries: object, module_text: str = "RATIO_FLOOR = 1.2\n"):
    config = tmp_path / "config"
    scripts = tmp_path / "scripts"
    (config / "checks").mkdir(parents=True)
    scripts.mkdir()
    (scripts / "probe_spec.py").write_text(module_text, encoding="utf-8")
    path = config / "checks" / "probe-spec.yaml"
    path.write_text(yaml.safe_dump({"checks": entries}), encoding="utf-8")
    return config, scripts, path


def test_repository_registers_agree_with_the_code():
    assert check_register.problems(CAD_ROOT / "config", CAD_ROOT / "scripts") == []


def test_entry_loads_and_matches_its_module(tmp_path: Path):
    config, scripts, path = _tree(tmp_path, [_ENTRY])
    (entry,) = check_register.load_checks(path)
    assert (entry.check, entry.kind, entry.basis) == (
        "RATIO_FLOOR",
        "mesh",
        "after_setting",
    )
    assert check_register.problems(config, scripts) == []


def test_wall_and_thread_are_kinds_here_only():
    import machinist_necessity

    assert {"wall", "thread"} <= set(check_register.KINDS)
    assert not {"wall", "thread"} & set(machinist_necessity.KINDS)


@pytest.mark.parametrize(
    "entries",
    [
        [],
        [{**_ENTRY, "kind": "budget"}],
        [{**_ENTRY, "basis": "rss"}],
        [{**_ENTRY, "reason": " ".join(["word"] * 11)}],
        [{key: value for key, value in _ENTRY.items() if key != "source"}],
        [{**_ENTRY, "note": "extra"}],
        [_ENTRY, {**_ENTRY, "id": "C-02"}],
    ],
)
def test_malformed_register_is_rejected(tmp_path: Path, entries: object):
    _config, _scripts, path = _tree(tmp_path, entries)
    with pytest.raises(ValueError):
        check_register.load_checks(path)


def test_check_missing_from_its_module_is_a_problem(tmp_path: Path):
    config, scripts, _path = _tree(tmp_path, [_ENTRY], module_text="OTHER = 1\n")
    (problem,) = check_register.problems(config, scripts)
    assert "'RATIO_FLOOR', which probe_spec.py does not contain" in problem


def test_register_named_for_no_module_is_a_problem(tmp_path: Path):
    config, scripts, path = _tree(tmp_path, [_ENTRY])
    path.rename(path.with_name("gone-spec.yaml"))
    assert check_register.problems(config, scripts) == [
        "gone-spec.yaml: no module gone_spec.py"
    ]


def test_necessity_entry_citing_a_check_needs_that_check_registered(tmp_path: Path):
    config, scripts, _path = _tree(tmp_path, [_ENTRY])
    necessity = config / "necessity" / "probe.yaml"
    necessity.parent.mkdir()

    def cite(source: str) -> list[str]:
        necessity.write_text(
            yaml.safe_dump(
                {
                    "necessity": [
                        {
                            "id": "N-01",
                            "feature": "sheet 1, bore",
                            "kind": "mesh",
                            "reason": "sets mesh backlash",
                            "source": source,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return check_register.problems(config, scripts)

    assert cite("probe_spec.RATIO_FLOOR") == []
    assert cite("owner ruling 2026-11-24") == []
    (problem,) = cite("probe_spec.BACKLASH_BAND")
    assert (
        "cites probe_spec.BACKLASH_BAND, which has no entry in checks/probe-spec.yaml"
        in problem
    )
