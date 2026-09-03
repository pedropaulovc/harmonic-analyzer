"""Offline contracts for the blind machinist review runner."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

import machinist_review as mr


def _clean_verdict(verdict: str = "SHIP") -> dict[str, Any]:
    return {
        "verdict": verdict,
        "summary": "ready",
        "blockers": [],
        "over_specification": [],
        "clarity": [],
        "minor": [],
    }


def test_prompts_exist_and_are_calibrated_to_the_policy() -> None:
    part = mr.load_prompt("part")
    assembly = mr.load_prompt("assembly")
    # The recalibration that separates this prompt from the gap-hunting ones:
    # the title block is the general spec, and over-specification is a defect.
    for text in (part, assembly):
        assert "TITLE BLOCK FIRST" in text
        assert "do not run commands" in text  # keeps the review blind
        assert "over_specification" in text
        assert "Never pad a category" in text
    assert "loaded gun" in part
    assert "Decimal places" in part
    assert "Hidden lines" in part
    assert "DRILL or REAM" in part
    assert "granite surface plate" in part and "No CMM" in part
    assert "never call a geometric control uninspectable" in part
    assert "datum feature symbols on real, reachable surfaces" in part
    # Assembly packages are judged as real assembly drawings: exploded view,
    # parts list, balloons, ordered steps -- the current three-view sheets are
    # expected to FAIL this until they are built out.
    for item in ("exploded view", "parts list (BOM)", "Assembly steps in order"):
        assert item in assembly, item


def test_schema_is_strict_structured_output() -> None:
    schema = mr.load_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert set(mr.FINDING_KEYS) <= set(schema["properties"])
    finding = schema["$defs"]["findings"]["items"]
    assert finding["additionalProperties"] is False
    assert set(finding["required"]) == {"where", "issue", "fix"}
    assert schema["properties"]["verdict"]["enum"] == ["SHIP", "FIX"]
    assert schema["properties"]["summary"]["minLength"] == 1
    assert all(
        finding["properties"][key]["minLength"] == 1 for key in finding["required"]
    )


def test_claude_command_is_exact_and_neutral(tmp_path: Path) -> None:
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps(mr.load_schema()), encoding="utf-8")
    command = mr.build_claude_command(
        workdir=tmp_path,
        image=tmp_path / "sheet.png",
        schema=schema,
        model="fable",
        effort="high",
    )
    schema_json = json.dumps(mr.load_schema(), separators=(",", ":"))
    assert command == [
        "claude",
        "-p",
        "--model",
        "fable",
        "--effort",
        "high",
        "--input-format",
        "text",
        "--output-format",
        "stream-json",
        "--verbose",
        "--json-schema",
        schema_json,
        "--tools",
        "Read",
        "--allowedTools",
        "Read(sheet.png)",
        "--restricted",
        "--safe-mode",
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
        "--permission-prompts",
        "none",
        "--strict-mcp-config",
        "--no-chrome",
    ]
    assert mr.CAD_ROOT.parent.as_posix() not in " ".join(command).replace("\\", "/")


def test_codex_command_is_exact_and_neutral(tmp_path: Path) -> None:
    image = tmp_path / "sheet.png"
    schema = tmp_path / "schema.json"
    output = tmp_path / "verdict.json"
    command = mr.build_codex_command(
        workdir=tmp_path,
        image=image,
        schema=schema,
        output=output,
        model="gpt-5.6-sol",
        effort="high",
    )
    assert command == [
        "codex",
        "exec",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "-C",
        str(tmp_path),
        "-m",
        "gpt-5.6-sol",
        "-c",
        "model_reasoning_effort=high",
        "-i",
        str(image),
        "--output-schema",
        str(schema),
        "-o",
        str(output),
        "--json",
        "-",
    ]
    assert mr.CAD_ROOT.parent.as_posix() not in " ".join(command).replace("\\", "/")


def test_pass_requires_ship_with_no_gating_findings() -> None:
    clean = _clean_verdict()
    clean["minor"] = [{"where": "x", "issue": "y", "fix": "z"}]
    assert mr.is_pass(clean)
    assert not mr.is_pass({**clean, "verdict": "FIX"})
    for key in mr.GATING_KEYS:
        assert not mr.is_pass(
            {**clean, key: [{"where": "x", "issue": "y", "fix": "z"}]}
        )
    assert not mr.is_pass(None)


def test_claude_blindness_allows_only_neutral_image_read_and_output(
    tmp_path: Path,
) -> None:
    image = tmp_path / "sheet.png"
    image_read = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "Read",
                    "input": {"file_path": "sheet.png"},
                }
            ]
        },
    }
    structured = {
        "type": "assistant",
        "message": {
            "content": [{"type": "tool_use", "name": "StructuredOutput", "input": {}}]
        },
    }
    other_read = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "Read",
                    "input": {"file_path": "schema.json"},
                }
            ]
        },
    }
    command = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "dir"}}
            ]
        },
    }
    assert (
        mr.count_claude_tool_events([image_read, structured], allowed_image=image) == 0
    )
    assert (
        mr.count_claude_image_reads([image_read, structured], allowed_image=image) == 1
    )
    assert mr.count_claude_image_reads([other_read], allowed_image=image) == 0
    assert mr.count_claude_tool_events([other_read], allowed_image=image) == 1
    assert mr.count_claude_tool_events([command], allowed_image=image) == 1


def test_codex_blindness_fails_closed_on_every_tool_or_command() -> None:
    passive = {"type": "agent_message", "text": "review complete"}
    tool = {"type": "item.completed", "item": {"type": "tool_use", "name": "Read"}}
    command = {
        "type": "item.completed",
        "item": {"type": "command_execution", "command": "type sheet.png"},
    }
    assert mr.count_codex_tool_events([passive]) == 0
    assert mr.count_codex_tool_events([tool]) == 1
    assert mr.count_codex_tool_events([command]) == 1


def test_both_structured_verdict_parsers(tmp_path: Path) -> None:
    verdict = _clean_verdict()
    assert (
        mr.extract_claude_verdict([{"type": "result", "structured_output": verdict}])
        == verdict
    )

    output = tmp_path / "verdict.json"
    output.write_text(json.dumps(verdict), encoding="utf-8")
    assert mr.extract_codex_verdict(output, []) == verdict

    output.unlink()
    events = [
        {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": json.dumps(verdict)},
        }
    ]
    assert mr.extract_codex_verdict(output, events) == verdict


@pytest.mark.parametrize(
    "malformed",
    [
        {**_clean_verdict(), "verdict": "MAYBE"},
        {**_clean_verdict(), "unexpected": True},
        {**_clean_verdict(), "blockers": [{}]},
        {**_clean_verdict(), "summary": 7},
        {**_clean_verdict(), "summary": ""},
        {
            **_clean_verdict(),
            "minor": [{"where": "", "issue": "rough edge", "fix": "deburr"}],
        },
    ],
)
def test_structured_verdict_parsers_reject_schema_violations(
    tmp_path: Path, malformed: dict[str, Any]
) -> None:
    with pytest.raises(RuntimeError):
        mr.extract_claude_verdict([{"type": "result", "structured_output": malformed}])

    output = tmp_path / "verdict.json"
    output.write_text(json.dumps(malformed), encoding="utf-8")
    with pytest.raises(RuntimeError):
        mr.extract_codex_verdict(output, [])


def test_review_execution_uses_provider_defaults_and_model_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    verdict = _clean_verdict()
    commands: list[list[str]] = []
    prompts: list[str] = []

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        prompts.append(str(kwargs["input"]))
        if command[0] == "codex-test":
            output = Path(command[command.index("-o") + 1])
            output.write_text(json.dumps(verdict), encoding="utf-8")
            stdout = json.dumps({"type": "turn.completed"})
        else:
            read_event = {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Read",
                            "input": {"file_path": "sheet.png"},
                        }
                    ]
                },
            }
            result_event = {"type": "result", "structured_output": verdict}
            stdout = "\n".join((json.dumps(read_event), json.dumps(result_event)))
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(mr.subprocess, "run", fake_run)
    image = tmp_path / "input.png"
    image.write_bytes(b"png")

    claude_review = mr.review_sheet(
        mr.Sheet("claude-default", "part", image),
        reviewer="claude",
        report_dir=tmp_path / "claude-default",
        retries=0,
        claude="claude-test",
    )
    codex_review = mr.review_sheet(
        mr.Sheet("codex-default", "part", image),
        reviewer="codex",
        report_dir=tmp_path / "codex-default",
        retries=0,
        codex="codex-test",
    )
    claude_override = mr.review_sheet(
        mr.Sheet("claude-override", "part", image),
        reviewer="claude",
        model="claude-custom",
        report_dir=tmp_path / "claude-override",
        retries=0,
        claude="claude-test",
    )
    codex_override = mr.review_sheet(
        mr.Sheet("codex-override", "part", image),
        reviewer="codex",
        model="codex-custom",
        report_dir=tmp_path / "codex-override",
        retries=0,
        codex="codex-test",
    )

    assert (claude_review.model, codex_review.model) == ("fable", "gpt-5.6-sol")
    assert (claude_override.model, codex_override.model) == (
        "claude-custom",
        "codex-custom",
    )
    assert commands[0][commands[0].index("--model") + 1] == "fable"
    assert commands[1][commands[1].index("-m") + 1] == "gpt-5.6-sol"
    assert commands[2][commands[2].index("--model") + 1] == "claude-custom"
    assert commands[3][commands[3].index("-m") + 1] == "codex-custom"
    assert prompts[0].startswith("Use the Read tool to inspect sheet.png")
    assert prompts[1] == mr.load_prompt("part")
    assert claude_review.passed and claude_review.blind
    assert claude_override.passed and claude_override.blind
    assert claude_review.extra == {"image_read_events": 1}


def test_claude_review_fails_without_an_allowed_image_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    verdict = _clean_verdict()

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        stdout = json.dumps({"type": "result", "structured_output": verdict})
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(mr.subprocess, "run", fake_run)
    image = tmp_path / "input.png"
    image.write_bytes(b"png")
    review = mr.review_sheet(
        mr.Sheet("uninspected", "part", image),
        reviewer="claude",
        report_dir=tmp_path / "report",
        retries=0,
        claude="claude-test",
    )

    assert review.verdict == verdict
    assert not review.passed
    assert not review.blind
    assert review.tool_events == 0
    assert review.extra == {"image_read_events": 0}


def test_retry_cannot_erase_earlier_claude_blindness_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    verdict = _clean_verdict()
    calls = 0

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            unauthorized = {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Read",
                            "input": {"file_path": "schema.json"},
                        }
                    ]
                },
            }
            return subprocess.CompletedProcess(
                command,
                1,
                stdout=json.dumps(unauthorized),
                stderr="retry",
            )
        allowed = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "input": {"file_path": "sheet.png"},
                    }
                ]
            },
        }
        result = {"type": "result", "structured_output": verdict}
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="\n".join((json.dumps(allowed), json.dumps(result))),
            stderr="",
        )

    monkeypatch.setattr(mr.subprocess, "run", fake_run)
    image = tmp_path / "input.png"
    image.write_bytes(b"png")
    report_dir = tmp_path / "report"
    review = mr.review_sheet(
        mr.Sheet("retried", "part", image),
        reviewer="claude",
        report_dir=report_dir,
        retries=1,
        claude="claude-test",
    )

    assert review.verdict == verdict
    assert review.attempts == 2
    assert review.tool_events == 1
    assert review.extra == {"image_read_events": 1}
    assert not review.blind
    assert not review.passed
    saved_events = [
        json.loads(line)
        for line in (report_dir / "retried.events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [event["attempt"] for event in saved_events] == [1, 2, 2]


def test_review_cli_requires_reviewer_except_for_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert mr.main(["crank_arm", "--report-dir", str(tmp_path)]) == 2
    assert "--reviewer is required" in capsys.readouterr().err
    assert mr.main(["--index", "--report-dir", str(tmp_path)]) == 0
    assert (tmp_path / "index.md").is_file()


def test_review_serialises_and_indexes_with_provenance(tmp_path: Path) -> None:
    verdict = _clean_verdict("FIX")
    verdict["summary"] = "over-toleranced"
    verdict["over_specification"] = [
        {"where": "front view", "issue": "datum B", "fix": "drop"}
    ]
    review = mr.Review(
        name="crank_arm",
        kind="part",
        png="x.png",
        verdict=verdict,
        passed=mr.is_pass(verdict),
        blind=True,
        tool_events=0,
        reviewer="codex",
        model="gpt-5.6-sol",
        effort="high",
        prompt_sha256="a" * 64,
        png_sha256="b" * 64,
        duration_s=1.0,
        reviewed_at="now",
    )
    mr.write_review(review, tmp_path)
    loaded = mr.load_reviews(tmp_path)
    assert loaded == [review]
    assert (loaded[0].reviewer, loaded[0].model, loaded[0].effort) == (
        "codex",
        "gpt-5.6-sol",
        "high",
    )
    markdown = (tmp_path / "crank_arm.md").read_text(encoding="utf-8")
    assert "by codex/gpt-5.6-sol (high)" in markdown
    index = mr.render_index(loaded)
    assert (
        "| [crank_arm](crank_arm.md) | part | FAIL | FIX | 0 | 1 | 0 | 0 | yes |"
        in index
    )
    data = json.loads((tmp_path / "crank_arm.json").read_text(encoding="utf-8"))
    assert data["reviewer"] == "codex"


def test_every_registered_drawing_has_a_prompt_kind() -> None:
    for sheet in mr.all_sheets():
        assert sheet.kind in mr.PROMPT_FILES
        assert sheet.png.name.endswith("_drawing.png")
