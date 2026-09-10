"""Offline regressions for resumable, blind prompt-evaluation evidence."""

from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

import machinist_review as mr
import machinist_review_eval as evaluation


@pytest.fixture
def case(tmp_path: Path) -> tuple[dict[str, Any], mr.ReviewPackage]:
    image = tmp_path / "frozen.png"
    image.write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII="
    ))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "cases": [{"name": "fit_case", "path": image.name,
                   "sha256": mr._sha256(image), "package_kind": "part",
                   "expected_behavior": "Recognize the fit while preserving unrelated blockers."}],
    }), encoding="utf-8")
    data, packages = evaluation.load_cases(manifest)
    return data, packages[0]


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {
        "calls": [], "mode": "valid", "relative_reads": False,
        "verdict": {
            "verdict": "FIX", "summary": "Fit is justified; a hole remains unlocated.",
            "blockers": [{"where": "front view", "issue": "Hole location is absent.",
                          "fix": "Locate the hole from the datum edges."}],
            "over_specification": [], "clarity": [], "minor": [],
        },
    }

    def fake_run(command: list[str], **kwargs: Any):
        cwd = Path(kwargs["cwd"])
        images = sorted(cwd.glob("sheet-*.png"))
        state["calls"].append({
            "command": command, "prompt": kwargs["input"], "cwd": cwd,
            "files": {path.name for path in cwd.iterdir()},
            "images": [path.read_bytes() for path in images],
        })
        verdict = deepcopy(state["verdict"])
        if state["mode"] == "invalid_schema":
            del verdict["blockers"]
        text = "not JSON" if state["mode"] == "malformed" else json.dumps(verdict)
        if "exec" in command:
            Path(command[command.index("-o") + 1]).write_text(text, encoding="utf-8")
            events = [{"type": "item.completed", "item": {
                "id": "item_0", "type": "agent_message", "text": text,
            }}, {"type": "turn.completed", "usage": {
                "input_tokens": 10, "cached_input_tokens": 0, "output_tokens": 10,
            }}]
        else:
            events = [{"type": "assistant", "message": {"content": [{
                "type": "tool_use", "id": f"read_{index}", "name": "Read",
                "input": {"file_path": image.name if state["relative_reads"] else str(image)},
            }]}} for index, image in enumerate(images)]
            events.append({"type": "result", "subtype": "success", "is_error": False,
                           "result": text})
        if state["mode"] == "unblind":
            events.insert(0, {"type": "item.completed", "item": {
                "id": "command_0", "type": "command_execution", "command": "pwd",
                "aggregated_output": str(cwd), "exit_code": 0, "status": "completed",
            }})
        return mr.subprocess.CompletedProcess(
            command, 0, stdout="\n".join(json.dumps(event) for event in events), stderr="",
        )

    monkeypatch.setattr(mr.shutil, "which", lambda executable: executable)
    monkeypatch.setattr(mr.subprocess, "run", fake_run)
    return state


def _identity(case, *, prompt: str = "Rubric A", reviewer: str = "codex", model: str = "model-a"):
    manifest, package = case
    return evaluation.make_identity(
        manifest, [package], {"baseline": prompt.encode(), "candidate": b"Rubric B"},
        reviewer=reviewer, model=model, effort="low", retries=0, timeout_s=30,
    )


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
def test_override_reaches_model_and_hash_without_losing_package_context(
    tmp_path: Path, case, provider, reviewer: str,
) -> None:
    _, part = case
    assembly = mr.ReviewPackage(part.name, "assembly", part.sources)
    reviews = []
    for index, (package, prompt) in enumerate([
        (part, ""), (assembly, ""), (assembly, "Rubric A"), (assembly, "Rubric B"),
    ]):
        identity = _identity((case[0], package), prompt=prompt, reviewer=reviewer)
        result = evaluation.run_case(identity, "baseline", package, prompt, tmp_path / str(index))
        assert result["error"] is None
        reviews.append(result["review"])
        sent = provider["calls"][-1]["prompt"]
        assert result["review"]["prompt_sha256"] == hashlib.sha256(sent.encode()).hexdigest()
        assert identity["prompts"]["baseline"]["effective_sha256"][package.name] == result["review"]["prompt_sha256"]
    part_input, assembly_input, baseline_input, candidate_input = [
        call["prompt"] for call in provider["calls"]
    ]
    assert assembly_input != part_input
    assert baseline_input.replace("Rubric A", "", 1) == assembly_input
    assert candidate_input.replace("Rubric B", "", 1) == assembly_input
    assert reviews[2]["prompt_sha256"] != reviews[3]["prompt_sha256"]
    if reviewer == "claude":
        assert part_input.strip()
    for call in provider["calls"]:
        assert call["files"] == {"sheet-1.png", "schema.json"}
        assert call["images"] == [part.sources[0].read_bytes()]
        assert call["cwd"] != part.sources[0].parent
        assert str(part.sources[0]) not in call["prompt"]
        assert part.name not in call["prompt"]
        assert all(str(part.sources[0]) not in argument for argument in call["command"])


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
def test_matching_fix_evidence_resumes_without_model_execution(
    tmp_path: Path, case, provider, reviewer: str,
) -> None:
    provider["relative_reads"] = True
    identity = _identity(case, reviewer=reviewer)
    directory = tmp_path / "run"
    first = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert first["error"] is None
    assert first["review"]["verdict"]["verdict"] == "FIX"
    assert first["review"]["passed"] is False
    assert evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory) == first
    assert len(provider["calls"]) == 1
    summary = evaluation.aggregate(identity, [first])
    assert summary["results"][0]["outcome"] == "unassessed"
    assert summary["counts"]["baseline"] == {"pass": 0, "fail": 0, "unassessed": 1, "invalid": 0}


@pytest.mark.parametrize("change", ["prompt", "image", "model"])
def test_changed_identity_executes_fresh_model_without_overwriting_old_evidence(
    tmp_path: Path, case, provider, change: str,
) -> None:
    directory = tmp_path / "run"
    first = evaluation.run_case(_identity(case), "baseline", case[1], "Rubric A", directory)
    assert first["error"] is None
    old_report = (directory / first["report"]).read_bytes()
    prompt, model = "Rubric A", "model-a"
    if change == "prompt":
        prompt = "New rubric"
    elif change == "image":
        case[1].sources[0].write_bytes(case[1].sources[0].read_bytes() + b"changed")
        case[0]["cases"][0]["sha256"] = mr._sha256(case[1].sources[0])
    else:
        model = "model-b"
    identity = _identity(case, prompt=prompt, model=model)
    fresh = evaluation.run_case(identity, "baseline", case[1], prompt, directory)
    assert fresh["error"] is None
    assert fresh["run_id"] != first["run_id"]
    assert fresh["report"] != first["report"]
    assert (directory / first["report"]).read_bytes() == old_report
    assert len(provider["calls"]) == 2
    if change == "prompt":
        assert provider["calls"][-1]["prompt"] == prompt
    elif change == "image":
        assert provider["calls"][-1]["images"] != provider["calls"][0]["images"]
    else:
        command = provider["calls"][-1]["command"]
        assert command[command.index("-m") + 1] == model
    assert evaluation.run_case(identity, "baseline", case[1], prompt, directory) == fresh
    assert len(provider["calls"]) == 2


@pytest.mark.parametrize("mode", ["malformed", "invalid_schema", "unblind"])
def test_invalid_model_evidence_is_not_scored_or_resumed(
    tmp_path: Path, case, provider, mode: str,
) -> None:
    identity = _identity(case)
    directory = tmp_path / "run"
    provider["mode"] = mode
    invalid = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert invalid["error"] is not None
    assert evaluation.aggregate(identity, [invalid])["results"][0]["outcome"] == "invalid"
    with pytest.raises(ValueError):
        evaluation.validate_evidence(invalid, identity, "baseline", case[1], directory)
    provider["mode"] = "valid"
    fresh = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert fresh["error"] is None
    assert fresh["report"] != invalid["report"]
    assert len(provider["calls"]) == 2


@pytest.mark.parametrize("damage", [
    "hash", "malformed_report", "verdict_schema", "blind_flag", "event_verdict", "cached_review",
])
def test_checkpoint_rejects_damaged_or_inconsistent_evidence(
    tmp_path: Path, case, provider, damage: str,
) -> None:
    identity = _identity(case)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    report = directory / result["report"]
    content = json.loads(report.read_text(encoding="utf-8"))
    if damage == "cached_review":
        result["review"]["verdict"]["blockers"] = []
    else:
        if damage == "verdict_schema":
            content["verdict"]["blockers"] = "missing"
        elif damage == "blind_flag":
            content["blind"] = False
        else:
            content["verdict"]["summary"] = "Different from the model's recorded answer."
        report.write_text("{" if damage == "malformed_report" else json.dumps(content), encoding="utf-8")
        if damage != "hash":
            result["report_sha256"] = mr._sha256(report)
            result["review"] = content
    (directory / "result.json").write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ValueError):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)
    fresh = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert fresh["error"] is None
    assert fresh["report"] != result["report"]
    assert len(provider["calls"]) == 2


def _assessment(result, outcome: str = "pass") -> dict[str, Any]:
    return {"schema_version": 1, "run_id": result["run_id"], "assessments": {
        "baseline": {result["case"]: {
            "report_sha256": result["report_sha256"], "outcome": outcome,
            "justification": "The fit is accepted without hiding the unrelated missing hole location.",
            "evidence": ["/blockers/0", "/over_specification"],
        }},
    }}


@pytest.mark.parametrize("outcome", ["pass", "fail"])
def test_human_targeted_assessment_is_independent_of_whole_sheet_fix(
    tmp_path: Path, case, provider, outcome: str,
) -> None:
    identity = _identity(case)
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", tmp_path / "run")
    assert result["error"] is None
    assessments = _assessment(result, outcome)
    if outcome == "fail":
        assessments["assessments"]["baseline"][result["case"]]["justification"] = (
            "The unrelated blocker is reported, but the targeted fit explanation is insufficient."
        )
    summary = evaluation.aggregate(identity, [result], assessments)
    assert summary["results"][0]["outcome"] == outcome
    assert summary["counts"]["baseline"][outcome] == 1
    assert summary["counts"]["baseline"]["unassessed"] == 0
    assert summary["results"][0]["review"]["passed"] is False
    assert result.get("outcome") is None


@pytest.mark.parametrize("damage", [
    "run_id", "report_hash", "missing_finding", "bad_reference", "empty_reason",
    "extra_field", "null_assessment", "invalid_evidence",
])
def test_stale_or_invalid_human_assessments_are_rejected(
    tmp_path: Path, case, provider, damage: str,
) -> None:
    identity = _identity(case)
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", tmp_path / "run")
    assert result["error"] is None
    assessments = _assessment(result)
    assessment = assessments["assessments"]["baseline"][result["case"]]
    if damage == "run_id":
        assessments["run_id"] = "0" * 64
    elif damage == "report_hash":
        assessment["report_sha256"] = "0" * 64
    elif damage == "missing_finding":
        assessment["evidence"] = ["/blockers/1"]
    elif damage == "bad_reference":
        assessment["evidence"] = ["/verdict"]
    elif damage == "empty_reason":
        assessment["justification"] = " "
    elif damage == "extra_field":
        assessment["automatic_score"] = 1
    elif damage == "null_assessment":
        assessments["assessments"]["baseline"][result["case"]] = None
    else:
        result["error"] = "Model evidence failed validation"
    with pytest.raises(ValueError):
        evaluation.aggregate(identity, [result], assessments)
