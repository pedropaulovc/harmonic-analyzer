"""Offline contracts for the blind machinist review runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import machinist_review as mr


def test_prompts_exist_and_are_calibrated_to_the_policy() -> None:
    part = mr.load_prompt("part")
    assembly = mr.load_prompt("assembly")
    # The recalibration that separates this prompt from the gap-hunting ones:
    # the title block is the general spec, and over-specification is a defect.
    for text in (part, assembly):
        assert "TITLE BLOCK FIRST" in text
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
    for key in ("where", "issue", "fix"):
        assert finding["properties"][key]["minLength"] == 1


def test_command_references_only_the_neutral_workdir(tmp_path: Path) -> None:
    cmd = mr.build_command(
        workdir=tmp_path,
        image=tmp_path / "sheet.png",
        schema=tmp_path / "schema.json",
        output=tmp_path / "verdict.json",
        model="gpt-test",
        effort="high",
    )
    joined = " ".join(cmd)
    repo = mr.CAD_ROOT.parent.as_posix()
    assert repo not in joined.replace("\\", "/")
    assert cmd[-1] == "-"  # prompt on stdin, never inline
    for flag in ("--ignore-user-config", "--ignore-rules", "--ephemeral", "--json"):
        assert flag in cmd
    assert cmd[cmd.index("--sandbox") + 1] == "read-only"
    assert cmd[cmd.index("-m") + 1] == "gpt-test"
    assert "model_reasoning_effort=high" in cmd


def test_pass_requires_ship_with_no_gating_findings() -> None:
    clean = {
        "verdict": "SHIP",
        "summary": "ready",
        "blockers": [],
        "over_specification": [],
        "clarity": [],
        "minor": [{"where": "x", "issue": "y", "fix": "z"}],
    }
    assert mr.is_pass(clean)
    assert not mr.is_pass({**clean, "verdict": "FIX"})
    for key in mr.GATING_KEYS:
        assert not mr.is_pass({**clean, key: [{"where": "x", "issue": "y", "fix": "z"}]})
    assert not mr.is_pass(None)


def test_verdict_validation_rejects_every_schema_violation() -> None:
    clean = {
        "verdict": "SHIP",
        "summary": "ready",
        "blockers": [],
        "over_specification": [],
        "clarity": [],
        "minor": [{"where": "x", "issue": "y", "fix": "z"}],
    }
    assert mr.validate_verdict(clean) is clean

    invalid = [
        {key: value for key, value in clean.items() if key != "summary"},
        {**clean, "unexpected": True},
        {**clean, "verdict": "MAYBE"},
        {**clean, "verdict": 1},
        {**clean, "summary": ""},
        {**clean, "summary": 1},
        {**clean, "blockers": {}},
        {**clean, "minor": ["not an object"]},
        {**clean, "minor": [{"where": "x", "issue": "y"}]},
        {
            **clean,
            "minor": [
                {"where": "x", "issue": "y", "fix": "z", "unexpected": True}
            ],
        },
        {**clean, "minor": [{"where": "", "issue": "y", "fix": "z"}]},
        {**clean, "minor": [{"where": "x", "issue": "", "fix": "z"}]},
        {**clean, "minor": [{"where": "x", "issue": "y", "fix": ""}]},
        {**clean, "minor": [{"where": "x", "issue": 1, "fix": "z"}]},
    ]
    for value in invalid:
        with pytest.raises(ValueError):
            mr.validate_verdict(value)
        assert not mr.is_pass(value)


def test_extract_verdict_validates_file_and_event_fallback(tmp_path: Path) -> None:
    invalid = {
        "verdict": "SHIP",
        "summary": "ready",
        "blockers": [],
        "over_specification": [],
        "clarity": [],
        "minor": [],
        "unexpected": True,
    }
    output = tmp_path / "verdict.json"
    output.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ValueError, match="keys must be exact"):
        mr._extract_verdict(output, [])

    output.unlink()
    events = [{"type": "agent_message", "text": json.dumps(invalid)}]
    with pytest.raises(ValueError, match="keys must be exact"):
        mr._extract_verdict(output, events)


def test_tool_events_are_detected_at_any_depth() -> None:
    assert mr.count_tool_events([{"type": "agent_message", "text": "{}"}]) == 0
    assert mr.count_tool_events([{"type": "item.completed", "item": {"type": "command_execution", "command": "ls"}}]) == 1
    assert mr.count_tool_events([{"type": "turn.started"}, {"type": "mcp_tool_call"}]) == 1


def test_retry_persists_all_attempts_and_cannot_hide_tool_use(
    tmp_path: Path, monkeypatch
) -> None:
    import subprocess

    png = tmp_path / "source.png"
    png.write_bytes(b"image")
    verdict = {
        "verdict": "SHIP",
        "summary": "ready",
        "blockers": [],
        "over_specification": [],
        "clarity": [],
        "minor": [],
    }
    calls = 0

    def fake_run(command, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            event = {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": "read something",
                },
            }
            return subprocess.CompletedProcess(
                command, 1, stdout=json.dumps(event), stderr="failed"
            )
        output = Path(command[command.index("-o") + 1])
        output.write_text(json.dumps(verdict), encoding="utf-8")
        event = {"type": "agent_message", "text": json.dumps(verdict)}
        return subprocess.CompletedProcess(
            command, 0, stdout=json.dumps(event), stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    report_dir = tmp_path / "reports"
    review = mr.review_sheet(
        mr.Sheet("part", "part", png),
        report_dir=report_dir,
        retries=1,
        codex="codex",
    )

    assert review.attempts == 2
    assert review.tool_events == 1
    assert not review.blind
    assert not review.passed
    records = [
        json.loads(line)
        for line in (report_dir / "part.events.jsonl").read_text().splitlines()
    ]
    assert [record["attempt"] for record in records] == [1, 2]
    assert records[0]["event"]["item"]["type"] == "command_execution"
    assert records[1]["event"]["type"] == "agent_message"


def test_arbitrary_png_reports_with_same_basename_do_not_collide(
    tmp_path: Path, monkeypatch
) -> None:
    import subprocess
    from concurrent.futures import ThreadPoolExecutor

    verdict = {
        "verdict": "SHIP",
        "summary": "ready",
        "blockers": [],
        "over_specification": [],
        "clarity": [],
        "minor": [],
    }

    def fake_run(command, **_kwargs):
        output = Path(command[command.index("-o") + 1])
        output.write_text(json.dumps(verdict), encoding="utf-8")
        return subprocess.CompletedProcess(
            command, 0, stdout=json.dumps({"type": "turn.completed"}), stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    inputs = [tmp_path / "left" / "part.png", tmp_path / "right" / "part.png"]
    for index, image in enumerate(inputs):
        image.parent.mkdir()
        image.write_bytes(f"png-{index}".encode())
    sheets = [mr._sheet_for_png(image, "part") for image in inputs]
    assert sheets[0].name != sheets[1].name

    report_dir = tmp_path / "reports"
    with ThreadPoolExecutor(max_workers=2) as pool:
        reviews = list(
            pool.map(
                lambda sheet: mr.review_sheet(
                    sheet, report_dir=report_dir, retries=0, codex="codex-test"
                ),
                sheets,
            )
        )

    names = {review.name for review in reviews}
    assert len(names) == 2
    assert {path.stem for path in report_dir.glob("*.json")} == names
    assert {path.stem for path in report_dir.glob("*.md")} == names
    assert {Path(review.events_file or "").name for review in reviews} == {
        f"{name}.events.jsonl" for name in names
    }
    index = mr.write_index(report_dir).read_text(encoding="utf-8")
    assert all(f"]({name}.md)" in index for name in names)


def test_review_serialises_and_indexes(tmp_path: Path) -> None:
    verdict = {
        "verdict": "FIX",
        "summary": "over-toleranced",
        "blockers": [],
        "over_specification": [{"where": "front view", "issue": "datum B", "fix": "drop"}],
        "clarity": [],
        "minor": [],
    }
    review = mr.Review(
        name="crank_arm", kind="part", png="x.png", verdict=verdict,
        passed=mr.is_pass(verdict), blind=True, tool_events=0, model="m", effort="high",
        prompt_sha256="a" * 64, png_sha256="b" * 64, duration_s=1.0, reviewed_at="now",
    )
    mr.write_review(review, tmp_path)
    loaded = mr.load_reviews(tmp_path)
    assert loaded[0].verdict == verdict and not loaded[0].passed
    index = mr.render_index(loaded)
    assert "| [crank_arm](crank_arm.md) | part | FAIL | FIX | 0 | 1 | 0 | 0 | yes |" in index
    assert json.loads((tmp_path / "crank_arm.json").read_text())["name"] == "crank_arm"


def test_every_registered_drawing_has_a_prompt_kind() -> None:
    for sheet in mr.all_sheets():
        assert sheet.kind in mr.PROMPT_FILES
        assert sheet.png.name.endswith("_drawing.png")
