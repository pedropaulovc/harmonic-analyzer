"""Every ``cad/scripts/test_*.py`` runs in exactly one ``check:*`` gate.

A test file no gate runs is a green build that checks nothing: 22 files sat
outside every gate until 2026-09-24, one of them red since 997f3534. check:recipe
now picks up the directory by glob, so the "run nowhere" arm below cannot fire
while that glob stands; this file exists to catch the glob being replaced by a
hand list again, a file running in two gates, and a stale ``_UNGATED_TESTS``
entry.
"""

from __future__ import annotations

import importlib.util
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None, (
        f"could not locate dodo.py under {REPO_ROOT}"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _gate_runs(dodo) -> dict[str, list[str]]:
    """``test_*.py`` file name -> every check gate whose command names it."""
    runs: dict[str, list[str]] = defaultdict(list)
    for task in dodo.task_check():
        command = task["actions"][0][1][0]
        for arg in command:
            path = Path(str(arg))
            if path.name.startswith("test_") and path.suffix == ".py":
                runs[path.name].append(task["name"])
    return runs


def _coverage_problems(
    test_files: set[str], runs: dict[str, list[str]], ungated: dict[str, str]
) -> list[str]:
    problems = []
    for name in sorted(test_files):
        gates = runs.get(name, [])
        if name in ungated and gates:
            problems.append(f"{name} is in _UNGATED_TESTS but check:{gates[0]} runs it")
        if name not in ungated and not gates:
            problems.append(f"{name} runs in no check:* gate and is not in _UNGATED_TESTS")
        if len(gates) > 1:
            problems.append(f"{name} runs {len(gates)} times: check:{', check:'.join(gates)}")
    for name, reason in sorted(ungated.items()):
        if name not in test_files:
            problems.append(f"_UNGATED_TESTS names {name}, which does not exist")
        if not reason.strip():
            problems.append(f"_UNGATED_TESTS gives {name} no reason")
    return problems


def test_every_script_test_runs_in_exactly_one_gate() -> None:
    dodo = _load_dodo()
    test_files = {path.name for path in dodo.SCRIPTS_DIR.glob("test_*.py")}
    problems = _coverage_problems(test_files, _gate_runs(dodo), dodo._UNGATED_TESTS)
    assert not problems, "check:* test coverage:\n" + "\n".join(problems)


def test_coverage_check_reports_each_failure_shape() -> None:
    """Positive control: the checker flags the shapes it exists to catch."""
    problems = _coverage_problems(
        {"test_orphan.py", "test_twice.py", "test_ungated_but_run.py"},
        {"test_twice.py": ["recipe", "graph"], "test_ungated_but_run.py": ["recipe"]},
        {"test_ungated_but_run.py": "needs a seat", "test_gone.py": "needs a seat"},
    )
    assert problems == [
        "test_orphan.py runs in no check:* gate and is not in _UNGATED_TESTS",
        "test_twice.py runs 2 times: check:recipe, check:graph",
        "test_ungated_but_run.py is in _UNGATED_TESTS but check:recipe runs it",
        "_UNGATED_TESTS names test_gone.py, which does not exist",
    ]


def test_recipe_gate_skips_ungated_tests() -> None:
    """An ``_UNGATED_TESTS`` entry really leaves check:recipe's command."""
    dodo = _load_dodo()
    assert "test_gear.py" in _gate_runs(dodo)
    dodo._UNGATED_TESTS = {"test_gear.py": "positive control"}
    assert "test_gear.py" not in _gate_runs(dodo)
