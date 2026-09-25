"""Every offline test file under ``cad/scripts`` runs inside some ``check:*`` gate.

``dodo`` enrolls tests explicitly (plus the ``test_*_drawing.py`` glob), so a new
test file that nobody enrolls passes in the local suite and never runs in a
``doit`` build -- a green gate that checks nothing.  Codex on #844 and #814:
``test_mirror_retirement_expectations.py`` shipped that way.  This guard reads
the pytest arguments of every ``check:*`` task and fails on any ``test_*.py``
that none of them collects, unless it is exempted below with a reason.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parents[1]

# Test files that deliberately run in no check:* gate, each with its reason.
EXEMPT: dict[str, str] = {}


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _collected_by_check_gates() -> dict[str, list[str]]:
    """Test file name -> the check:* tasks whose pytest command collects it."""
    collected: dict[str, list[str]] = {}
    for task in _load_dodo().task_check():
        _run, (cmd, *_rest) = task["actions"][0]
        for arg in cmd:
            path = Path(str(arg))
            if path.suffix != ".py" or not path.name.startswith("test_"):
                continue
            if path.resolve().parent != SCRIPTS:
                continue
            collected.setdefault(path.name, []).append(task["name"])
    return collected


def test_every_offline_test_file_runs_in_a_check_gate() -> None:
    collected = _collected_by_check_gates()
    on_disk = {path.name for path in SCRIPTS.glob("test_*.py")}
    orphans = sorted(on_disk - set(collected) - set(EXEMPT))
    assert not orphans, (
        "test files no check:* gate collects (enroll them in dodo.task_check, "
        f"or exempt them with a reason): {orphans}"
    )


def test_exemptions_name_real_uncollected_files() -> None:
    collected = _collected_by_check_gates()
    on_disk = {path.name for path in SCRIPTS.glob("test_*.py")}
    listed = set(EXEMPT)
    assert not (listed - on_disk), (
        f"exempted files that no longer exist: {sorted(listed - on_disk)}"
    )
    assert not (listed & set(collected)), (
        f"exempted files a gate now collects -- drop them: {sorted(listed & set(collected))}"
    )
    assert all(reason.strip() for reason in EXEMPT.values())
