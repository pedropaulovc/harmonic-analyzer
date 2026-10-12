"""Offline contracts for release-package blind machinist review benchmarks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

import machinist_review_bench as evaluation


def _verdict(value: str = "SHIP") -> dict:
    return {
        "verdict": value,
        "summary": "Ready for manufacture.",
        "blockers": [],
        "over_specification": [],
        "clarity": [],
        "minor": [],
    }


def _expectation(check: dict) -> dict:
    return {"text": "Manufacturing contract", "check": check}


@pytest.mark.parametrize(
    "actual,expected,passed",
    [("SHIP", "SHIP", True), ("FIX", "SHIP", False), ("FIX", "FIX", True)],
)
def test_verdict_grading(actual: str, expected: str, passed: bool) -> None:
    result = evaluation.grade_check(
        _verdict(actual), _expectation({"verdict": expected})
    )
    assert result is not None
    assert result["text"] == "Manufacturing contract"
    assert result["passed"] is passed
    assert isinstance(result["evidence"], str) and result["evidence"]


@pytest.mark.parametrize(
    "count,limit,passed", [(0, 0, True), (1, 0, False), (2, 2, True), (3, 2, False)]
)
def test_count_grading(count: int, limit: int, passed: bool) -> None:
    verdict = _verdict()
    verdict["blockers"] = [
        {"where": "Sheet 1", "issue": "Undefined bore", "fix": "Specify bore"}
    ] * count
    result = evaluation.grade_check(
        verdict, _expectation({"max_count": {"blockers": limit}})
    )
    assert result is not None
    assert result["passed"] is passed
    assert result["evidence"]


@pytest.mark.parametrize(
    "check",
    [{"category": "blockers"}, {"category": "any"}, {"absent_from": "blockers"}],
)
@pytest.mark.parametrize("contains_words", [False, True])
def test_semantic_expectations_are_not_keyword_graded(
    check: dict, contains_words: bool
) -> None:
    verdict = _verdict("FIX")
    if contains_words:
        verdict["blockers"] = [
            {
                "where": "Manufacturing contract",
                "issue": "Manufacturing contract",
                "fix": "Manufacturing contract",
            }
        ]
    assert evaluation.grade_check(verdict, _expectation(check)) is None


def test_missing_count_category_is_rejected() -> None:
    verdict = _verdict()
    del verdict["blockers"]
    with pytest.raises(ValueError):
        evaluation.grade_check(verdict, _expectation({"max_count": {"blockers": 0}}))


@pytest.mark.parametrize(
    "check", [{"category": "blockers"}, {"absent_from": "blockers"}]
)
def test_missing_semantic_category_is_rejected(check: dict) -> None:
    verdict = _verdict()
    del verdict["blockers"]
    with pytest.raises(ValueError):
        evaluation.grade_check(verdict, _expectation(check))


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.mark.parametrize(
    "check",
    [
        {"category": "not-a-category"},
        {"absent_from": "not-a-category"},
        {"max_count": {"not-a-category": 0}},
        {"max_count": {"blockers": True}},
        {"max_count": {"blockers": -1}},
    ],
)
def test_invalid_check_categories_and_limits_are_rejected(check: dict) -> None:
    with pytest.raises(ValueError):
        evaluation.grade_check(_verdict(), _expectation(check))


@pytest.fixture
def prompt_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    prompts = repo / "cad" / "scripts" / "prompts"
    prompts.mkdir(parents=True)
    for kind in ("part", "assembly"):
        (prompts / f"machinist_review_{kind}.md").write_text(
            f"LEGACY {kind} instructions\n", encoding="utf-8"
        )
    _git(repo, "add", ".")
    _git(
        repo,
        "-c",
        "user.name=Offline test",
        "-c",
        "user.email=offline@example.invalid",
        "commit",
        "-m",
        "legacy",
    )
    _git(repo, "tag", "legacy")
    guidelines = repo / "cad" / "docs" / "drawing-guidelines.md"
    guidelines.parent.mkdir()
    guidelines.write_text("MODERN shared guidelines\n", encoding="utf-8")
    for kind in ("part", "assembly"):
        (prompts / f"machinist_review_{kind}.md").write_text(
            f"MODERN {kind} instructions\n", encoding="utf-8"
        )
    _git(repo, "add", ".")
    _git(
        repo,
        "-c",
        "user.name=Offline test",
        "-c",
        "user.email=offline@example.invalid",
        "commit",
        "-m",
        "modern",
    )
    _git(repo, "tag", "modern")
    guidelines.write_text("UNCOMMITTED guidelines\n", encoding="utf-8")
    return repo


@pytest.mark.parametrize("kind", ["part", "assembly"])
def test_ref_prompt_uses_historical_guidelines_and_kind(
    prompt_repo: Path, kind: str
) -> None:
    prompt = evaluation.compose_prompt(kind, ref="modern", repo=prompt_repo)
    assert "MODERN shared guidelines" in prompt
    assert f"MODERN {kind} instructions" in prompt
    assert prompt.index("MODERN shared guidelines") < prompt.index(
        f"MODERN {kind} instructions"
    )
    assert "LEGACY" not in prompt
    assert "UNCOMMITTED" not in prompt


@pytest.mark.parametrize("kind", ["part", "assembly"])
def test_legacy_ref_prompt_does_not_inherit_current_guidelines(
    prompt_repo: Path, kind: str
) -> None:
    assert (
        evaluation.compose_prompt(kind, ref="legacy", repo=prompt_repo)
        == f"LEGACY {kind} instructions\n"
    )


def test_working_prompt_delegates_to_review_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def load(kind: str) -> str:
        calls.append(kind)
        return "working prompt"

    monkeypatch.setattr(evaluation.mr, "load_prompt", load)
    assert evaluation.compose_prompt("assembly") == "working prompt"
    assert calls == ["assembly"]


def test_default_workspace_uses_agent_scratchpad(tmp_path: Path) -> None:
    assert (
        evaluation.default_workspace(
            {
                "HARMONIC_AGENT_SCRATCHPAD": str(tmp_path),
                "LOCALAPPDATA": str(tmp_path / "ignored"),
            }
        )
        == tmp_path / "harmonic-analyzer" / "machinist-review-evals"
    )


def test_default_workspace_falls_back_to_localappdata(tmp_path: Path) -> None:
    assert (
        evaluation.default_workspace({"LOCALAPPDATA": str(tmp_path)})
        == tmp_path
        / "harmonic-analyzer-agent-scratchpad"
        / "harmonic-analyzer"
        / "machinist-review-evals"
    )


def test_eval_filters_match_ids_and_descriptive_names() -> None:
    skill_name, cases = evaluation.load_evals()
    assert skill_name == "machinist-review"
    assert len(cases) > 1
    _, selected = evaluation.load_evals(
        selectors=(str(cases[0]["id"]), cases[-1]["name"])
    )
    assert [case["id"] for case in selected] == [cases[0]["id"], cases[-1]["id"]]


def test_eval_filters_do_not_duplicate_cases() -> None:
    _, cases = evaluation.load_evals()
    _, selected = evaluation.load_evals(
        selectors=(str(cases[0]["id"]), cases[0]["name"])
    )
    assert selected == [cases[0]]


def test_unknown_eval_filter_is_rejected() -> None:
    with pytest.raises(ValueError):
        evaluation.load_evals(selectors=("not-a-real-eval",))


def test_iteration_layout_and_viewer_metadata(tmp_path: Path) -> None:
    _, cases = evaluation.load_evals(selectors=("1",))
    workspace = tmp_path / "outside-git" / "benchmarks"
    configurations = {"with_skill": {"ref": None}, "old_skill": {"ref": "origin/main"}}
    first = evaluation.create_iteration(workspace, cases, configurations)
    second = evaluation.create_iteration(workspace, cases, configurations)
    assert first == workspace / "iteration-1"
    assert second == workspace / "iteration-2"
    manifest = json.loads((first / "iteration.json").read_text(encoding="utf-8"))
    assert manifest["evals"] == cases
    assert manifest["configurations"] == configurations
    case = cases[0]
    case_dir = first / case["name"]
    metadata = json.loads((case_dir / "eval_metadata.json").read_text(encoding="utf-8"))
    for config in configurations:
        run = evaluation.run_directory(first, case, config, 1)
        assert run == case_dir / config / "run-1"
        assert (run / "outputs").is_dir()
        assert (
            json.loads((run / "eval_metadata.json").read_text(encoding="utf-8"))
            == metadata
        )
    assert not (workspace / ".git").exists()


@pytest.fixture(autouse=True)
def offline_release_pdfs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def release_pdfs(release: str, workspace: Path) -> Path:
        directory = tmp_path / "fixture-pdfs" / release
        directory.mkdir(parents=True, exist_ok=True)
        for drawing in evaluation.mr.DRAWINGS_BY_NAME.values():
            (directory / drawing.outputs["pdf"].name).write_bytes(b"offline frozen PDF")
        return directory

    monkeypatch.setattr(evaluation, "release_pdfs", release_pdfs)


def _report(directory: Path, case: dict, model: str = "offline-reviewer") -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    report = {
        "name": case["package"],
        "kind": case["kind"],
        "verdict": _verdict(),
        "blind": True,
        "tool_events": 0,
        "duration_s": 1.25,
        "model": model,
        "prompt_sha256": "a" * 64,
        "source_sha256": [hashlib.sha256(b"offline frozen PDF").hexdigest()],
        "error": None,
    }
    (directory / f"{case['package']}.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    return report


def test_import_sparse_sources_number_runs_per_eval(tmp_path: Path) -> None:
    _, cases = evaluation.load_evals(selectors=("1", "2"))
    sources = [tmp_path / f"source-{number}" for number in range(3)]
    first_report = _report(sources[0], cases[0], "first")
    second_report = _report(sources[1], cases[1], "second")
    third_report = _report(sources[2], cases[0], "third")
    old = tmp_path / "old"
    for case in cases:
        _report(old, case)
    iteration = evaluation.import_iteration(
        tmp_path / "workspace",
        cases,
        [*(f"with_skill={source}" for source in sources), f"old_skill={old}"],
    )
    for case, number, expected in [
        (cases[0], 1, first_report),
        (cases[0], 2, third_report),
        (cases[1], 1, second_report),
    ]:
        run = iteration / case["name"] / "with_skill" / f"run-{number}"
        assert (
            json.loads((run / "outputs" / "review.json").read_text(encoding="utf-8"))
            == expected
        )
        timing = json.loads((run / "timing.json").read_text(encoding="utf-8"))
        assert timing["total_duration_seconds"] == 1.25
        assert timing["total_tokens"] is None
        assert timing["tokens_measured"] is False
        assert (run / "provenance.json").is_file()
    assert not (iteration / cases[1]["name"] / "with_skill" / "run-2").exists()
    assert not (iteration / cases[0]["name"] / "with_skill" / "run-3").exists()


def test_missing_import_configuration_does_not_allocate_iteration(
    tmp_path: Path,
) -> None:
    _, cases = evaluation.load_evals(selectors=("1",))
    source = tmp_path / "source"
    _report(source, cases[0])
    workspace = tmp_path / "workspace"
    with pytest.raises(ValueError, match="old_skill"):
        evaluation.import_iteration(workspace, cases, [f"with_skill={source}"])
    assert not workspace.exists()


def test_workspace_inside_git_is_rejected(prompt_repo: Path) -> None:
    _, cases = evaluation.load_evals(selectors=("1",))
    workspace = prompt_repo / "benchmarks"
    with pytest.raises(ValueError):
        evaluation.create_iteration(workspace, cases, {})
    assert not workspace.exists()


def test_deterministic_grade_and_exact_benchmark_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, cases = evaluation.load_evals(selectors=("1",))
    case = {
        **cases[0],
        "expectations": [
            _expectation({"verdict": "SHIP"}),
            _expectation({"max_count": {"blockers": 0}}),
        ],
    }
    source = tmp_path / "source"
    _report(source, case)
    iteration = evaluation.import_iteration(
        tmp_path / "workspace",
        [case],
        [
            f"old_skill={source}",
            f"with_skill={source}",
        ],
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Deterministic grading must not invoke a model")

    monkeypatch.setattr(evaluation, "semantic_grade", forbidden)
    for config in ("old_skill", "with_skill"):
        run = iteration / case["name"] / config / "run-1"
        evaluation.grade_run(run, case, model="unused", effort="medium", timeout=1)
        grade = json.loads((run / "grading.json").read_text(encoding="utf-8"))
        assert grade["summary"] == {
            "passed": 2,
            "failed": 0,
            "total": 2,
            "pass_rate": 1.0,
        }
        assert grade["grader"]["model"] is None
        assert grade["eval_feedback"]["suggestions"] == []
    benchmark = evaluation.aggregate_iteration(iteration)
    assert set(benchmark) == {"metadata", "runs", "run_summary", "notes"}
    assert [run["configuration"] for run in benchmark["runs"]] == [
        "with_skill",
        "old_skill",
    ]
    assert list(benchmark["run_summary"]) == ["with_skill", "old_skill", "delta"]
    assert benchmark["metadata"]["evals_run"] == [case["id"]]
    assert benchmark["metadata"]["runs_per_configuration"] == 1
    assert benchmark["metadata"]["executor_model"] == "offline-reviewer"
    assert benchmark["metadata"]["analyzer_model"] == ""
    assert (
        json.loads((iteration / "benchmark.json").read_text(encoding="utf-8"))
        == benchmark
    )


def test_review_main_uses_registry_pdf_basename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    mr = evaluation.mr
    _, cases = evaluation.load_evals(selectors=("1",))
    case = cases[0]
    calls = []

    def review(package, **kwargs):
        calls.append((package, kwargs))
        return SimpleNamespace(
            name=package.name, verdict=_verdict(), passed=True, blind=True, duration_s=0
        )

    monkeypatch.setattr(mr, "review_package", review)
    monkeypatch.setattr(mr, "write_index", lambda directory: directory / "index.html")
    pdf_dir = tmp_path / "frozen-release" / "pdf"
    report_dir = tmp_path / "reports"
    assert (
        mr.main(
            [
                case["package"],
                "--pdf-dir",
                str(pdf_dir),
                "--report-dir",
                str(report_dir),
                "--reviewer",
                "claude",
                "--jobs",
                "1",
            ]
        )
        == 0
    )
    assert len(calls) == 1
    package, controls = calls[0]
    assert package.name == case["package"]
    assert package.kind == case["kind"]
    assert package.sources == (
        pdf_dir / mr.DRAWINGS_BY_NAME[case["package"]].outputs["pdf"].name,
    )
    assert controls["report_dir"] == report_dir
    assert controls["reviewer"] == "claude"


@pytest.mark.parametrize("uses_tool", [False, True])
def test_semantic_grader_is_neutral_text_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, uses_tool: bool
) -> None:
    from types import SimpleNamespace

    verdict = _verdict()
    expectation = _expectation({"absent_from": "blockers"})
    response = {
        "expectations": [
            {
                "text": expectation["text"],
                "passed": True,
                "evidence": "No matching finding in blockers.",
            }
        ],
        "eval_feedback": {"suggestions": [], "overall": "Clear expectation."},
    }
    events = [
        {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 20}}
    ]
    if uses_tool:
        events.insert(
            0,
            {
                "type": "item.completed",
                "item": {"type": "command_execution", "command": "dir"},
            },
        )
    observed = []
    monkeypatch.setattr(evaluation.shutil, "which", lambda name: "offline-codex")

    def run(command, **kwargs):
        observed.append(command)
        workdir = Path(command[command.index("-C") + 1])
        assert workdir == kwargs["cwd"]
        assert workdir.name.startswith("machgrade-")
        assert not workdir.is_relative_to(evaluation.REPO_ROOT)
        assert set(path.name for path in workdir.iterdir()) == {"schema.json"}
        assert "--ignore-user-config" in command and "--ignore-rules" in command
        assert command[command.index("--sandbox") + 1] == "read-only"
        assert "--skip-git-repo-check" in command
        assert command[command.index("-m") + 1] == "gpt-6.1-sol"
        assert command[command.index("-c") + 1] == "model_reasoning_effort=medium"
        assert command[-2:] == ["--json", "-"]
        schema = Path(command[command.index("--output-schema") + 1])
        assert (
            json.loads(schema.read_text(encoding="utf-8")) == evaluation.GRADER_SCHEMA
        )
        assert kwargs["timeout"] == 600
        instructions, data = kwargs["input"].split("\nREVIEW JSON\n", 1)
        review_text, expectations_text = data.split("\nEXPECTATIONS\n", 1)
        assert json.loads(review_text) == verdict
        assert json.loads(expectations_text) == [expectation]
        assert "Do not use tools" in instructions
        for secret in (
            str(evaluation.REPO_ROOT),
            str(tmp_path),
            "with_skill",
            "old_skill",
            "origin/main",
            "prompt_sha256",
            ".pdf",
        ):
            assert secret not in kwargs["input"]
        Path(command[command.index("-o") + 1]).write_text(
            json.dumps(response), encoding="utf-8"
        )
        return SimpleNamespace(
            returncode=0,
            stdout="\n".join(json.dumps(event) for event in events),
            stderr="",
        )

    monkeypatch.setattr(evaluation.subprocess, "run", run)
    directory = tmp_path / "with_skill" / "grader"
    if uses_tool:
        with pytest.raises(ValueError, match="tool"):
            evaluation.semantic_grade(
                verdict,
                [expectation],
                directory,
                model="gpt-6.1-sol",
                effort="medium",
                timeout=600,
            )
        assert not (directory / "response.json").exists()
    else:
        assert (
            evaluation.semantic_grade(
                verdict,
                [expectation],
                directory,
                model="gpt-6.1-sol",
                effort="medium",
                timeout=600,
            )
            == response
        )
        assert (
            json.loads((directory / "response.json").read_text(encoding="utf-8"))
            == response
        )
    assert len(observed) == 1


def test_mismatched_import_pdf_hash_does_not_allocate_iteration(tmp_path: Path) -> None:
    _, cases = evaluation.load_evals(selectors=("1",))
    source = tmp_path / "source"
    report = _report(source, cases[0])
    report["source_sha256"] = ["0" * 64]
    (source / f"{cases[0]['package']}.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    workspace = tmp_path / "workspace"
    with pytest.raises(ValueError):
        evaluation.import_iteration(
            workspace, cases, [f"with_skill={source}", f"old_skill={source}"]
        )
    assert not (workspace / "iteration-1").exists()


def test_grade_iteration_excludes_uncompleted_review_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, cases = evaluation.load_evals(selectors=("1",))
    case = {**cases[0], "expectations": [_expectation({"verdict": "SHIP"})]}
    source = tmp_path / "source"
    _report(source, case)
    iteration = evaluation.import_iteration(
        tmp_path / "workspace",
        [case],
        [
            f"with_skill={source}",
            f"old_skill={source}",
        ],
    )
    incomplete = evaluation.run_directory(iteration, case, "with_skill", 2)

    def forbidden(*args, **kwargs):
        pytest.fail("Deterministic grading must not invoke a model")

    monkeypatch.setattr(evaluation, "semantic_grade", forbidden)
    benchmark = evaluation.grade_iteration(iteration, jobs=1)
    assert [run["configuration"] for run in benchmark["runs"]] == [
        "with_skill",
        "old_skill",
    ]
    assert all(run["run_number"] == 1 for run in benchmark["runs"])
    assert not (incomplete / "grading.json").exists()
    assert any(
        "Ungraded runs excluded" in note and "run-2" in note
        for note in benchmark["notes"]
    )
