"""Farm executor (``HARMONIC_EXECUTOR=farm``): the submitter never takes the COM
seat, never publishes, and turns a farm outcome into the task's outcome."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import build  # noqa: E402


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _leaf_result(dodo, **overrides):
    fields = dict(
        state="succeeded",
        exit_code=0,
        worker_id="sw-01@3",
        attempt=1,
        cache_present=True,
        log_blob="results/leaf/part__pen_rod/" + "k" * 64 + "/1/task.log",
        failure_category=None,
        failure_message=None,
    )
    fields.update(overrides)
    return dodo._farm.LeafResult(**fields)


@pytest.fixture
def farm_part(tmp_path, monkeypatch):
    """A farm-mode ``part:pen_rod`` whose probe misses; returns (dodo, script, calls)."""
    monkeypatch.setenv("HARMONIC_EXECUTOR", "farm")
    dodo = _load_dodo()
    script = tmp_path / "build_pen_rod.py"
    script.write_text("", encoding="utf-8")
    output = tmp_path / "pen-rod.SLDPRT"
    calls: dict[str, list] = {"restore": [], "store": [], "stamp": []}

    monkeypatch.setattr(dodo, "_part_file_deps", lambda _script, _stem: [str(script)])
    monkeypatch.setattr(dodo, "_part_cache_outputs", lambda _stem: [output])
    monkeypatch.setattr(dodo, "_cache_key", lambda _deps, _label: "k" * 64)
    monkeypatch.setattr(
        dodo, "_stamp_part_execution", lambda stem: calls["stamp"].append(stem)
    )
    monkeypatch.setattr(
        dodo._cache, "store", lambda *args: calls["store"].append(args) or "stored"
    )
    monkeypatch.setattr(
        dodo, "_com_seat", lambda label: pytest.fail(f"{label} took the COM seat")
    )
    monkeypatch.setattr(
        dodo, "_exec_com", lambda *_a, **_kw: pytest.fail("built locally")
    )

    def restore(outcomes):
        pending = iter(outcomes)
        monkeypatch.setattr(
            dodo._cache,
            "restore",
            lambda key, outputs, label: (
                calls["restore"].append((key, outputs, label)) or next(pending)
            ),
        )

    return dodo, script, calls, restore


def test_failed_leaf_fails_the_task_with_the_farm_diagnosis(farm_part, monkeypatch):
    dodo, script, calls, restore = farm_part
    restore((False,))
    monkeypatch.setattr(
        dodo._farm,
        "run_leaf",
        lambda label, key: _leaf_result(
            dodo,
            state="failed",
            exit_code=87,
            cache_present=False,
            failure_category="task_failed",
            failure_message="SolidWorks connect timed out",
        ),
    )

    with pytest.raises(RuntimeError) as failure:
        dodo._cached_part_action("pen_rod", script)

    assert str(failure.value) == (
        "part:pen_rod failed on sw-01@3 [task_failed] exit 87: SolidWorks connect "
        "timed out (log: results/leaf/part__pen_rod/" + "k" * 64 + "/1/task.log)"
    )
    assert calls["stamp"] == []
    assert calls["store"] == []


def test_success_without_the_key_is_an_infrastructure_fault(farm_part, monkeypatch):
    dodo, script, calls, restore = farm_part
    restore((False, False))  # probe miss, then the post-farm restore also misses
    monkeypatch.setattr(dodo._farm, "run_leaf", lambda label, key: _leaf_result(dodo))

    with pytest.raises(RuntimeError, match=r"farm reported success but cache key k{12} is absent"):
        dodo._cached_part_action("pen_rod", script)

    assert len(calls["restore"]) == 2
    assert calls["stamp"] == []


def test_success_restores_the_leaf_key_and_stamps_without_publishing(
    farm_part, monkeypatch
):
    dodo, script, calls, restore = farm_part
    restore((False, True))
    dispatched = []
    monkeypatch.setattr(
        dodo._farm,
        "run_leaf",
        lambda label, key: dispatched.append((label, key)) or _leaf_result(dodo),
    )

    dodo._cached_part_action("pen_rod", script)

    assert dispatched == [("part:pen_rod", "k" * 64)]
    assert [r[0] for r in calls["restore"]] == ["k" * 64, "k" * 64]
    assert calls["stamp"] == ["pen_rod"]
    assert calls["store"] == [], "the worker publishes; the submitter never does"


def test_com_gates_are_refused_under_the_farm_executor(monkeypatch):
    monkeypatch.setenv("HARMONIC_EXECUTOR", "farm")
    dodo = _load_dodo()
    monkeypatch.setattr(
        dodo, "_com_seat", lambda label: pytest.fail(f"{label} took the COM seat")
    )
    ran = []
    monkeypatch.setattr(dodo, "_exec", lambda cmd, label, log_stem: ran.append(label))

    with pytest.raises(RuntimeError, match=r"verify soundness: .*HARMONIC_EXECUTOR=local"):
        dodo._run(["x"], "verify soundness", com=True)
    dodo._run(["x"], "check math", com=False)
    assert ran == ["check math"]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def test_farm_build_refuses_a_dirty_tree_before_publishing(
    tmp_path, monkeypatch, capsys
):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "tracked.txt").write_text("v1\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-q", "-m", "init")
    (repo / "scratch.txt").write_text("wip\n", encoding="utf-8")
    monkeypatch.setattr(build, "REPO_ROOT", repo)

    launched = []
    real_run = build.subprocess.run

    def spy(argv, **kwargs):
        launched.append(argv[0])
        return real_run(argv, **kwargs)

    monkeypatch.setattr(build.subprocess, "run", spy)

    assert build.main(["--executor", "farm", "list"]) == 2

    err = capsys.readouterr().err
    assert err == "farm: working tree is dirty:\n  scratch.txt\n"
    assert launched == ["git", "git"], "stopped after the status checks; no publish"


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (["assembly:x"], ["-n", "8", "assembly:x"]),
        (["run", "assembly:x"], ["run", "-n", "8", "assembly:x"]),
        (["-n", "2", "assembly:x"], ["-n", "2", "assembly:x"]),
        (["run", "--process=3", "part:y"], ["run", "--process=3", "part:y"]),
        (["list"], ["list"]),
        ([], ["-n", "8"]),
    ],
)
def test_farm_runs_fan_out_unless_the_caller_chose(given, expected, monkeypatch):
    monkeypatch.delenv("HARMONIC_FARM_PARALLELISM", raising=False)
    commands = {"run": object(), "list": object()}
    assert build._with_farm_parallelism(list(given), commands) == expected
