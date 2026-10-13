"""Offline contracts for release-package blind machinist review benchmarks."""

from __future__ import annotations

from html import escape
from html.parser import HTMLParser
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


class _ReviewHTML(HTMLParser):
    """Collect rendered elements and their visible text without a browser."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[dict] = []
        self.stack: list[dict] = []
        self.feed(source)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        element = {"tag": tag, "attrs": dict(attrs), "text": ""}
        self.elements.append(element)
        if tag not in {"img", "meta", "link", "br", "hr", "input"}:
            self.stack.append(element)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        for element in self.stack:
            element["text"] += data

    def matching(self, tag: str, class_name: str | None = None) -> list[dict]:
        return [
            element
            for element in self.elements
            if element["tag"] == tag
            and (
                class_name is None
                or class_name in element["attrs"].get("class", "").split()
            )
        ]


def _viewer_report(verdict: str = "SHIP") -> dict:
    return {
        "verdict": _verdict(verdict),
        "reviewer": "claude",
        "model": "offline-model",
        "effort": "medium",
        "prompt_sha256": "0123456789abcdef" * 4,
        "duration_s": 1.25,
    }


@pytest.mark.parametrize("verdict", ["SHIP", "FIX"])
def test_review_html_verdict_badge(verdict: str) -> None:
    parsed = _ReviewHTML(evaluation.render_review_html(_viewer_report(verdict)))
    badges = [
        element
        for element in parsed.elements
        if f"verdict-{verdict.lower()}" in element["attrs"].get("class", "").split()
    ]
    assert len(badges) == 1
    assert badges[0]["text"].strip() == verdict
    assert "verdict" in badges[0]["attrs"]["class"].split()
    visible = "".join(element["text"] for element in parsed.matching("body"))
    for value in (
        "Ready for manufacture.",
        "claude",
        "offline-model",
        "medium",
        "0123456789ab",
        "1.25",
    ):
        assert value in visible


def test_review_html_findings_escape_text_and_highlight_whole_citations() -> None:
    report = _viewer_report("FIX")
    citation = 'rUlE 18 (<script>alert("rule")</script> & unsafe)'
    finding = {
        "where": '<img src=x onerror="alert(1)"> & Sheet 1',
        "issue": f"Before {citation} after.",
        "fix": '<a href="javascript:alert(2)">replace</a> & verify',
    }
    report["verdict"]["summary"] = '<script>alert("summary")</script> & review'
    report["verdict"]["blockers"] = [finding]
    source = evaluation.render_review_html(report)
    parsed = _ReviewHTML(source)
    cards = parsed.matching("article", "finding")
    assert len(cards) == 1
    for value in finding.values():
        assert value in cards[0]["text"]
    assert escape(finding["where"]) in source
    assert escape(finding["fix"]) in source
    assert escape(report["verdict"]["summary"]) in source
    marks = parsed.matching("mark", "rule-citation")
    assert [mark["text"] for mark in marks] == [citation]
    assert f'<mark class="rule-citation">{escape(citation)}</mark>' in source
    assert not parsed.matching("script")
    assert not parsed.matching("img")
    assert not parsed.matching("a")
    assert not any(
        key.lower().startswith("on")
        for element in parsed.elements
        for key in element["attrs"]
    )


@pytest.mark.parametrize(
    "text",
    [
        "rule 5 (avoid excessive GD&T)",
        "RULE 18 (fully defined features)",
        "Rule 21 (shop-ready sheets)",
    ],
)
def test_review_html_rule_citations_are_case_insensitive(text: str) -> None:
    report = _viewer_report()
    report["verdict"]["minor"] = [{"where": text, "issue": text, "fix": text}]
    marks = _ReviewHTML(evaluation.render_review_html(report)).matching(
        "mark", "rule-citation"
    )
    assert [mark["text"] for mark in marks] == [text, text, text]


@pytest.mark.parametrize(
    "text",
    [
        "rule 5 without a title",
        "rule five (avoid excessive GD&T)",
        "rule 5 (unclosed",
        "rule (avoid excessive GD&T)",
        "misrule 5 (not a citation)",
    ],
)
def test_review_html_does_not_mark_non_citations(text: str) -> None:
    report = _viewer_report()
    report["verdict"]["clarity"] = [{"where": text, "issue": text, "fix": text}]
    parsed = _ReviewHTML(evaluation.render_review_html(report))
    assert not parsed.matching("mark", "rule-citation")
    assert text in parsed.matching("article", "finding")[0]["text"]


def test_review_html_all_category_counts_and_cards() -> None:
    report = _viewer_report("FIX")
    categories = ("blockers", "over_specification", "clarity", "minor")
    for count, category in enumerate(categories, start=1):
        report["verdict"][category] = [
            {
                "where": f"{category} location {index}",
                "issue": f"{category} issue {index}",
                "fix": f"{category} fix {index}",
            }
            for index in range(count)
        ]
    parsed = _ReviewHTML(evaluation.render_review_html(report))
    assert len(parsed.matching("article", "finding")) == 10
    assert not parsed.matching("p", "empty")
    for count, category in enumerate(categories, start=1):
        section = next(
            element
            for element in parsed.elements
            if element["attrs"].get("id") == category
        )
        assert str(count) in section["text"]
        for finding in report["verdict"][category]:
            for value in finding.values():
                assert value in section["text"]


def test_review_html_empty_categories_are_explicit() -> None:
    parsed = _ReviewHTML(evaluation.render_review_html(_viewer_report()))
    assert [element["text"].strip() for element in parsed.matching("p", "empty")] == [
        "No findings."
    ] * 4
    for category in ("blockers", "over_specification", "clarity", "minor"):
        section = next(
            element
            for element in parsed.elements
            if element["attrs"].get("id") == category
        )
        assert "0" in section["text"]
        assert "No findings." in section["text"]


def test_review_html_metadata_is_visible_shortened_and_escaped() -> None:
    report = _viewer_report()
    for key in ("reviewer", "model", "effort", "duration_s"):
        report[key] = f'<script>{key}</script> & "value"'
    report["prompt_sha256"] = '<sha&"bad>123' + "z" * 52
    source = evaluation.render_review_html(report)
    parsed = _ReviewHTML(source)
    visible = "".join(element["text"] for element in parsed.matching("body"))
    for key in ("reviewer", "model", "effort", "duration_s"):
        assert report[key] in visible
        assert escape(report[key]) in source
    short_sha = report["prompt_sha256"][:12]
    assert short_sha in visible
    assert escape(short_sha) in source
    assert report["prompt_sha256"] not in source
    assert not parsed.matching("script")


def test_review_html_embeds_jpeg_sheets_and_full_size_links() -> None:
    sheets = ("data:image/jpeg;base64,/9j/AA==", "data:image/jpeg;base64,/9j/BB==")
    source = evaluation.render_review_html(_viewer_report(), sheets=sheets)
    parsed = _ReviewHTML(source)
    assert [image["attrs"]["src"] for image in parsed.matching("img")] == list(sheets)
    links = parsed.matching("a", "sheet-link")
    assert [link["attrs"]["href"] for link in links] == list(sheets)
    for link in links:
        assert link["attrs"]["target"] == "_blank"
        assert "noopener" in link["attrs"]["rel"].split()
    assert parsed.matching("style")
    assert "prefers-color-scheme" in source
    scripts = parsed.matching("script")
    assert len(scripts) == 1
    assert "src" not in scripts[0]["attrs"]
    assert "URL.createObjectURL" in scripts[0]["text"]
    assert "image/jpeg" in scripts[0]["text"]
    assert not parsed.matching("link")


@pytest.mark.parametrize(
    "sheet", ["https://example.invalid/sheet.jpg", 'javascript:alert("sheet")']
)
def test_review_html_rejects_non_jpeg_data_sheets(sheet: str) -> None:
    with pytest.raises(ValueError):
        evaluation.render_review_html(_viewer_report(), sheets=(sheet,))


@pytest.mark.parametrize("invalid", ["UNKNOWN", None, {"verdict": "SHIP"}])
def test_review_html_validates_verdict_schema(invalid: object) -> None:
    report = _viewer_report()
    report["verdict"] = invalid
    with pytest.raises(ValueError):
        evaluation.render_review_html(report)


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
        names = {d.outputs["pdf"].name for d in evaluation.mr.DRAWINGS_BY_NAME.values()}
        names |= {
            case["release_pdf"]
            for case in evaluation.load_evals()[1]
            if "release_pdf" in case
        }
        for name in names:
            (directory / name).write_bytes(b"offline frozen PDF")
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


@pytest.mark.parametrize("configuration", ["with_skill", "old_skill"])
def test_given_import_configuration_missing_package_does_not_allocate_iteration(
    tmp_path: Path, configuration: str
) -> None:
    _, cases = evaluation.load_evals(selectors=("1", "2"))
    source = tmp_path / "source"
    _report(source, cases[0])
    workspace = tmp_path / "workspace"
    with pytest.raises(ValueError, match=configuration):
        evaluation.import_iteration(workspace, cases, [f"{configuration}={source}"])
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


@pytest.mark.parametrize("configuration", ["with_skill", "old_skill"])
def test_single_configuration_import_grade_and_benchmark(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, configuration: str
) -> None:
    _, cases = evaluation.load_evals(selectors=("1",))
    case = {**cases[0], "expectations": [_expectation({"verdict": "SHIP"})]}
    source = tmp_path / "source"
    _report(source, case)
    iteration = evaluation.import_iteration(
        tmp_path / "workspace", [case], [f"{configuration}={source}"]
    )
    manifest = json.loads((iteration / "iteration.json").read_text(encoding="utf-8"))
    assert list(manifest["configurations"]) == [configuration]
    omitted = "old_skill" if configuration == "with_skill" else "with_skill"
    assert not (iteration / case["name"] / omitted).exists()
    assert not (iteration / "inputs" / omitted).exists()

    def forbidden(*args, **kwargs):
        pytest.fail("Deterministic grading must not invoke a model")

    monkeypatch.setattr(evaluation, "semantic_grade", forbidden)
    benchmark = evaluation.grade_iteration(iteration, jobs=1)
    assert [run["configuration"] for run in benchmark["runs"]] == [configuration]
    assert benchmark["runs"][0]["result"]["pass_rate"] == 1.0
    assert list(benchmark["run_summary"]) == [configuration]
    assert "delta" not in benchmark["run_summary"]
    markdown = (iteration / "benchmark.md").read_text(encoding="utf-8")
    label = "With Skill" if configuration == "with_skill" else "Old Skill"
    omitted_label = "Old Skill" if configuration == "with_skill" else "With Skill"
    assert f"| Metric | {label} |" in markdown
    assert f"| Eval | {label} |" in markdown
    assert omitted_label not in markdown
    assert "Delta" not in markdown
    assert "ungraded" not in markdown
    assert json.loads((iteration / "failures.json").read_text(encoding="utf-8")) == []


def test_empty_import_configurations_do_not_allocate_iteration(tmp_path: Path) -> None:
    _, cases = evaluation.load_evals(selectors=("1",))
    workspace = tmp_path / "workspace"
    with pytest.raises(ValueError):
        evaluation.import_iteration(workspace, cases, [])
    assert not workspace.exists()


def test_run_without_baseline_never_loads_or_reviews_old_skill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    _, cases = evaluation.load_evals(selectors=("1",))
    case = cases[0]
    composed = []
    reviewed = []
    graded = []

    def compose(kind, ref=None):
        composed.append((kind, ref))
        assert ref is None
        return "offline working prompt"

    def review(command, **kwargs):
        prompt = Path(command[command.index("--prompt-file") + 1])
        assert prompt.parent.name == "with_skill"
        assert prompt.read_text(encoding="utf-8") == "offline working prompt"
        reviewed.append(command)
        _report(Path(command[command.index("--report-dir") + 1]), case)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def grade(iteration, **kwargs):
        graded.append((iteration, kwargs))
        return {}

    monkeypatch.setattr(evaluation, "compose_prompt", compose)
    monkeypatch.setattr(evaluation.subprocess, "run", review)
    monkeypatch.setattr(evaluation, "grade_iteration", grade)
    args = evaluation._parse_args(
        [
            "run",
            "--workspace",
            str(tmp_path / "workspace"),
            "--baseline-ref",
            "none",
            "--runs",
            "1",
            "--jobs",
            "1",
        ]
    )
    iteration = evaluation.run_iteration(args, [case])
    assert composed == [(case["kind"], None)]
    assert len(reviewed) == 1
    assert len(graded) == 1
    assert graded[0][0] == iteration
    manifest = json.loads((iteration / "iteration.json").read_text(encoding="utf-8"))
    assert list(manifest["configurations"]) == ["with_skill"]
    assert not (iteration / "inputs" / "old_skill").exists()
    assert not (iteration / case["name"] / "old_skill").exists()


def test_release_pdf_override_reads_the_renamed_release_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A drawing renamed after its release keeps reading the release's PDF:
    import hashes it, and run stages it under the registry name."""
    from types import SimpleNamespace

    _, cases = evaluation.load_evals(selectors=("ha-measuring-stick-rules",))
    case = cases[0]
    assert case["package"] == "ms_stick"
    assert case["release_pdf"] == "ha-measuring-stick.pdf"
    registry_pdf = evaluation.mr.DRAWINGS_BY_NAME["ms_stick"].outputs["pdf"].name
    assert evaluation.release_pdf_name(case) == "ha-measuring-stick.pdf" != registry_pdf
    release = tmp_path / "renamed-release" / "pdf"

    def release_pdfs(name: str, workspace: Path) -> Path:
        # The release holds only the old basename, never the registry's.
        release.mkdir(parents=True, exist_ok=True)
        (release / case["release_pdf"]).write_bytes(b"renamed release PDF")
        return release

    monkeypatch.setattr(evaluation, "release_pdfs", release_pdfs)
    renamed_hash = hashlib.sha256(b"renamed release PDF").hexdigest()

    source = tmp_path / "source"
    report = _report(source, case)
    with pytest.raises(ValueError, match="source hashes do not match"):
        evaluation.import_iteration(tmp_path / "imported", [case], [f"with_skill={source}"])
    report["source_sha256"] = [renamed_hash]
    (source / f"{case['package']}.json").write_text(json.dumps(report), encoding="utf-8")
    assert evaluation.import_iteration(tmp_path / "imported", [case], [f"with_skill={source}"])

    staged = []

    def review(command, **kwargs):
        pdf_dir = Path(command[command.index("--pdf-dir") + 1])
        staged.append((pdf_dir / registry_pdf).read_bytes())
        _report(Path(command[command.index("--report-dir") + 1]), case)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(evaluation, "compose_prompt", lambda kind, ref=None: "prompt")
    monkeypatch.setattr(evaluation.subprocess, "run", review)
    monkeypatch.setattr(evaluation, "grade_iteration", lambda iteration, **kwargs: {})
    args = evaluation._parse_args(
        ["run", "--workspace", str(tmp_path / "run"), "--baseline-ref", "none",
         "--runs", "1", "--jobs", "1"]
    )
    evaluation.run_iteration(args, [case])
    assert staged == [b"renamed release PDF"]


def test_failure_records_preserve_metadata_and_exclude_passing_entries() -> None:
    expectations = [
        {
            **_expectation({"category": "blockers"}),
            "text": "Find omitted dimension.",
            "rule": 18,
            "polarity": "negative",
            "confidence": "high",
        },
        {**_expectation({"verdict": "SHIP"}), "text": "Passing control."},
    ]
    case = {
        "id": 1,
        "name": "known-case",
        "package": "known-package",
        "expectations": expectations,
    }
    benchmark = {
        "runs": [
            {
                "eval_id": 1,
                "eval_name": "known-case",
                "configuration": "with_skill",
                "run_number": 2,
                "expectations": [
                    {
                        "text": expectations[0]["text"],
                        "passed": False,
                        "evidence": "Missed it.",
                    },
                    {
                        "text": expectations[1]["text"],
                        "passed": True,
                        "evidence": "Correct.",
                    },
                ],
            }
        ]
    }
    assert evaluation.failure_records({"evals": [case]}, benchmark) == [
        {
            "eval_id": 1,
            "eval_name": "known-case",
            "package": "known-package",
            "configuration": "with_skill",
            "run_number": 2,
            "rule": 18,
            "polarity": "negative",
            "reviewer_error": "false_negative",
            "confidence": "high",
            "expectation_text": "Find omitted dimension.",
            "grader_evidence": "Missed it.",
            "metadata_sources": {
                "rule": "expectation",
                "polarity": "expectation",
                "confidence": "expectation",
            },
        }
    ]


@pytest.mark.parametrize(
    "check,polarity,error",
    [
        ({"category": "blockers"}, "negative", "false_negative"),
        ({"verdict": "FIX"}, "negative", "false_negative"),
        ({"absent_from": "blockers"}, "positive", "false_positive"),
        ({"max_count": {"blockers": 0}}, "positive", "false_positive"),
        ({"verdict": "SHIP"}, "positive", "false_positive"),
    ],
)
@pytest.mark.parametrize(
    "text,rule,origin",
    [
        ("Apply rule 18 (fully defined features).", 18, "text"),
        ("No numbered rule is known.", None, "missing"),
    ],
)
def test_failure_records_derive_legacy_metadata(
    check: dict, polarity: str, error: str, text: str, rule: int | None, origin: str
) -> None:
    expectation = {**_expectation(check), "text": text}
    case = {
        "id": 1,
        "name": "legacy",
        "package": "legacy-package",
        "expectations": [expectation],
    }
    benchmark = {
        "runs": [
            {
                "eval_id": 1,
                "eval_name": "legacy",
                "configuration": "old_skill",
                "run_number": 1,
                "expectations": [
                    {"text": text, "passed": False, "evidence": "Wrong finding."}
                ],
            }
        ]
    }
    records = evaluation.failure_records({"evals": [case]}, benchmark)
    assert len(records) == 1
    record = records[0]
    assert record["rule"] == rule
    assert record["polarity"] == polarity
    assert record["reviewer_error"] == error
    assert record["confidence"] is None
    assert record["metadata_sources"] == {
        "rule": origin,
        "polarity": "check",
        "confidence": "missing",
    }


def test_aggregate_writes_failed_expectations_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, cases = evaluation.load_evals(selectors=("1",))
    case = {
        **cases[0],
        "expectations": [
            {**_expectation({"verdict": "FIX"}), "text": "Apply rule 18."},
            {**_expectation({"verdict": "SHIP"}), "text": "Passing control."},
        ],
    }
    source = tmp_path / "source"
    _report(source, case)
    iteration = evaluation.import_iteration(
        tmp_path / "workspace", [case], [f"with_skill={source}"]
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Deterministic grading must not invoke a model")

    monkeypatch.setattr(evaluation, "semantic_grade", forbidden)
    benchmark = evaluation.grade_iteration(iteration, jobs=1)
    manifest = json.loads((iteration / "iteration.json").read_text(encoding="utf-8"))
    failures = json.loads((iteration / "failures.json").read_text(encoding="utf-8"))
    assert failures == evaluation.failure_records(manifest, benchmark)
    assert len(failures) == 1
    assert failures[0]["expectation_text"] == "Apply rule 18."
    assert failures[0]["rule"] == 18
    assert failures[0]["reviewer_error"] == "false_negative"
