"""Offline contracts for the blind machinist review runner."""

from __future__ import annotations

import json
from pathlib import Path

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
    clean = {"verdict": "SHIP", "summary": "", "blockers": [], "over_specification": [], "clarity": [], "minor": [{"where": "x", "issue": "y", "fix": "z"}]}
    assert mr.is_pass(clean)
    assert not mr.is_pass({**clean, "verdict": "FIX"})
    for key in mr.GATING_KEYS:
        assert not mr.is_pass({**clean, key: [{"where": "x", "issue": "y", "fix": "z"}]})
    assert not mr.is_pass(None)


def test_tool_events_are_detected_at_any_depth() -> None:
    assert mr.count_tool_events([{"type": "agent_message", "text": "{}"}]) == 0
    assert mr.count_tool_events([{"type": "item.completed", "item": {"type": "command_execution", "command": "ls"}}]) == 1
    assert mr.count_tool_events([{"type": "turn.started"}, {"type": "mcp_tool_call"}]) == 1


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
