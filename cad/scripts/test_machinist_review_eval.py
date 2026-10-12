"""Offline regressions for resumable, blind prompt-evaluation evidence."""

from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
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
def frozen_baseline(tmp_path: Path, case) -> Path:
    baseline = tmp_path / "baseline.txt"
    baseline.write_bytes(b"Frozen rubric.\r\n")
    manifest = {
        **case[0],
        "baseline_prompt": {"path": baseline.name, "sha256": mr._sha256(baseline)},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return baseline


def _sheet_call(
    reviewer: str, tool: str, arguments: dict[str, Any], call_id: str,
    image: bytes, *, ok: bool = True, image_result: bool = True,
) -> list[dict[str, Any]]:
    encoded = base64.b64encode(image).decode("ascii")
    if reviewer == "claude":
        content = [{
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": encoded},
        }] if image_result else [{"type": "text", "text": "No image."}]
        return [
            {"type": "assistant", "message": {"content": [{
                "type": "tool_use", "id": call_id, "name": f"mcp__sheets__{tool}",
                "input": arguments,
            }]}},
            {"type": "user", "message": {"content": [{
                "type": "tool_result", "tool_use_id": call_id,
                "content": content, "is_error": not ok,
            }]}},
        ]
    item = {
        "id": call_id, "type": "mcp_tool_call", "server": "sheets",
        "tool": tool, "arguments": arguments, "status": "in_progress",
        "result": None, "error": None,
    }
    content = [{
        "type": "image", "data": encoded, "mimeType": "image/png",
    }] if image_result else [{"type": "text", "text": "No image."}]
    return [
        {"type": "item.started", "item": item},
        {"type": "item.completed", "item": {
            **item, "status": "completed" if ok else "failed",
            "result": {"content": content, "isError": not ok},
            "error": None if ok else {"message": "View failed."},
        }},
    ]


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {
        "calls": [], "mode": "valid", "crops": [],
        "verdict": {
            "verdict": "FIX", "summary": "Fit is justified; a hole remains unlocated.",
            "blockers": [{"where": "front view", "issue": "Hole location is absent.",
                          "fix": "Locate the hole from the datum edges."}],
            "over_specification": [], "clarity": [], "minor": [],
        },
    }

    def fake_run(command: list[str], **kwargs: Any):
        cwd = Path(kwargs["cwd"])
        reviewer = "codex" if "exec" in command else "claude"
        if reviewer == "codex":
            server_args = json.loads(next(
                argument.split("=", 1)[1] for argument in command
                if argument.startswith("mcp_servers.sheets.args=")
            ))
        else:
            config = json.loads(Path(command[command.index("--mcp-config") + 1]).read_text(encoding="utf-8"))
            server_args = config["mcpServers"]["sheets"]["args"]
        assert server_args[0] == str(mr.SHEETS_SERVER)
        sources = [Path(source) for source in server_args[1:]]
        assert all(source.is_absolute() and not source.is_relative_to(cwd) for source in sources)
        images = [source.read_bytes() for source in sources]
        state["calls"].append({
            "command": command, "prompt": kwargs["input"], "cwd": cwd,
            "files": {path.name for path in cwd.iterdir()},
            "sources": sources, "images": images,
        })
        verdict = deepcopy(state["verdict"])
        if state["mode"] == "invalid_schema":
            del verdict["blockers"]
        text = "not JSON" if state["mode"] == "malformed" else json.dumps(verdict)
        events = []
        if reviewer == "codex":
            events.append({"type": "thread.started", "thread_id": f"session-{len(state['calls'])}"})
        else:
            events.append({
                "type": "system", "subtype": "init",
                "session_id": command[command.index("--session-id") + 1],
            })
        if state["mode"] != "missing_view":
            for sheet, image in enumerate(images, start=1):
                events.extend(_sheet_call(
                    reviewer, "view_sheet", {"sheet": sheet}, f"view_{sheet}", image,
                    ok=state["mode"] != "failed_view",
                    image_result=state["mode"] != "text_view",
                ))
        for index, crop in enumerate(state["crops"]):
            events.extend(_sheet_call(reviewer, "crop", crop, f"crop_{index}", images[0]))
        if reviewer == "codex":
            Path(command[command.index("-o") + 1]).write_text(text, encoding="utf-8")
            events.extend([{"type": "item.completed", "item": {
                "id": "answer", "type": "agent_message", "text": text,
            }}, {"type": "turn.completed", "usage": {
                "input_tokens": 10, "cached_input_tokens": 0, "output_tokens": 10,
            }}])
        else:
            events.append({"type": "result", "subtype": "success", "is_error": False,
                           "result": text})
        if state["mode"] == "unblind":
            if reviewer == "codex":
                events.insert(0, {"type": "item.completed", "item": {
                    "id": "command_0", "type": "command_execution", "command": "pwd",
                    "aggregated_output": str(cwd), "exit_code": 0, "status": "completed",
                }})
            else:
                events.insert(0, {"type": "assistant", "message": {"content": [{
                    "type": "tool_use", "id": "read_0", "name": "Read",
                    "input": {"file_path": str(sources[0])},
                }]}})
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


def _preserve_report(result, directory: Path, report: dict[str, Any]) -> None:
    report_path = directory / result["report"]
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result["report_sha256"] = mr._sha256(report_path)
    result["review"] = report
    (directory / "result.json").write_text(json.dumps(result), encoding="utf-8")


def _preserve_events(result, directory: Path, events: list[dict[str, Any]]) -> None:
    events_path = directory / result["events"]
    events_path.write_text("\n".join(json.dumps(row) for row in events), encoding="utf-8")
    result["events_sha256"] = mr._sha256(events_path)
    for invocation in result["review"]["extra"]["evidence"]["attempts"]:
        if invocation["stdout_file"] is not None:
            Path(invocation["stdout_file"]).write_text("\n".join(
                json.dumps(row["event"]) for row in events
                if row["attempt"] == invocation["attempt"]
            ), encoding="utf-8")
    (directory / "result.json").write_text(json.dumps(result), encoding="utf-8")


def test_main_rejects_changed_selected_frozen_baseline_before_provider_execution(
    tmp_path: Path, frozen_baseline: Path, provider, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    frozen_baseline.write_bytes(frozen_baseline.read_bytes().replace(b"\r\n", b"\n"))
    candidate = tmp_path / "candidate.txt"
    candidate.write_bytes(b"Candidate rubric.")
    report_dir = tmp_path / "reports"
    monkeypatch.chdir(tmp_path)

    status = evaluation.main([
        "--cases", str(tmp_path / "manifest.json"),
        "--baseline", frozen_baseline.name, "--candidate", str(candidate),
        "--report-dir", str(report_dir), "--reviewer", "codex",
        "--model", "model-a", "--effort", "low", "--jobs", "1", "--retries", "0",
    ])

    assert status == 2
    assert json.loads(capsys.readouterr().out)["error"].startswith("ValueError:")
    assert provider["calls"] == []
    assert not report_dir.exists()


@pytest.mark.parametrize("selection", ["frozen", "custom"])
def test_main_accepts_selected_baseline_with_actual_prompt_provenance(
    tmp_path: Path, frozen_baseline: Path, provider, selection: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    baseline = frozen_baseline
    if selection == "custom":
        baseline = tmp_path / "custom" / frozen_baseline.name
        baseline.parent.mkdir()
        baseline.write_bytes(b"Intentional custom rubric.\r\n")
        frozen_baseline.write_bytes(b"Corrupted unselected frozen rubric.")
    candidate = tmp_path / "candidate.txt"
    candidate.write_bytes(b"Candidate rubric.\r\n")
    raw_prompts = {"baseline": baseline.read_bytes(), "candidate": candidate.read_bytes()}
    report_dir = tmp_path / "reports"

    status = evaluation.main([
        "--cases", str(tmp_path / "manifest.json"),
        "--baseline", str(baseline), "--candidate", str(candidate),
        "--report-dir", str(report_dir), "--reviewer", "codex",
        "--model", "model-a", "--effort", "low", "--jobs", "1", "--retries", "0",
    ])

    assert status == 0
    summary = json.loads(capsys.readouterr().out)
    assert all(result["error"] is None for result in summary["results"])
    run_dir = report_dir / summary["run_id"]
    identity = json.loads((run_dir / "identity.json").read_text(encoding="utf-8"))
    for version, raw in raw_prompts.items():
        assert identity["prompts"][version]["raw_sha256"] == hashlib.sha256(raw).hexdigest()
        assert (run_dir / "inputs" / f"{version}.txt").read_bytes() == raw
        assert any(raw.decode().replace("\r\n", "\n") in call["prompt"] for call in provider["calls"])
    if selection == "custom":
        assert identity["prompts"]["baseline"]["raw_sha256"] != (
            identity["manifest"]["baseline_prompt"]["sha256"]
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
    _, assembly_input, baseline_input, candidate_input = [
        call["prompt"] for call in provider["calls"]
    ]
    assert baseline_input.replace("Rubric A", "", 1) == assembly_input
    assert candidate_input.replace("Rubric B", "", 1) == assembly_input
    assert reviews[2]["prompt_sha256"] != reviews[3]["prompt_sha256"]
    for call in provider["calls"]:
        assert call["files"] == (
            {"schema.json", "mcp.json"} if reviewer == "claude" else {"schema.json"}
        )
        assert call["sources"] == list(part.sources)
        assert call["images"] == [part.sources[0].read_bytes()]
        assert call["cwd"] != part.sources[0].parent
        assert str(part.sources[0]) not in call["prompt"]
        assert part.name not in call["prompt"]
        assert "-i" not in call["command"]
        if reviewer == "codex":
            args = json.loads(next(
                argument.split("=", 1)[1] for argument in call["command"]
                if argument.startswith("mcp_servers.sheets.args=")
            ))
            assert args[1:] == [str(source.resolve()) for source in part.sources]
        else:
            assert call["command"][call["command"].index("--allowedTools") + 1] == (
                "mcp__sheets__view_sheet,mcp__sheets__crop"
            )


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
def test_matching_fix_evidence_resumes_without_model_execution(
    tmp_path: Path, case, provider, reviewer: str,
) -> None:
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


@pytest.mark.parametrize("change", ["prompt", "image", "model", "sheets_server"])
def test_changed_identity_executes_fresh_model_without_overwriting_old_evidence(
    tmp_path: Path, case, provider, change: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "run"
    old_identity = _identity(case)
    first = evaluation.run_case(old_identity, "baseline", case[1], "Rubric A", directory)
    assert first["error"] is None
    old_report = (directory / first["report"]).read_bytes()
    prompt, model = "Rubric A", "model-a"
    if change == "prompt":
        prompt = "New rubric"
    elif change == "image":
        case[1].sources[0].write_bytes(case[1].sources[0].read_bytes() + b"changed")
        case[0]["cases"][0]["sha256"] = mr._sha256(case[1].sources[0])
    elif change == "model":
        model = "model-b"
    else:
        original_sha256 = mr._sha256
        monkeypatch.setattr(mr, "_sha256", lambda path: (
            hashlib.sha256(b"changed sheet-server rendering").hexdigest()
            if Path(path) == mr.SHEETS_SERVER else original_sha256(path)
        ))
    identity = _identity(case, prompt=prompt, model=model)
    fresh = evaluation.run_case(identity, "baseline", case[1], prompt, directory)
    assert fresh["error"] is None
    assert fresh["run_id"] != first["run_id"]
    assert fresh["report"] != first["report"]
    assert (directory / first["report"]).read_bytes() == old_report
    assert len(provider["calls"]) == 2
    if change == "prompt":
        assert prompt in provider["calls"][-1]["prompt"]
        assert "Rubric A" not in provider["calls"][-1]["prompt"]
    elif change == "image":
        assert provider["calls"][-1]["images"] != provider["calls"][0]["images"]
    elif change == "model":
        command = provider["calls"][-1]["command"]
        assert command[command.index("-m") + 1] == model
    else:
        assert identity["sheets_server_sha256"] != old_identity["sheets_server_sha256"]
        assert identity["sheets_server_sha256"] == mr._sha256(mr.SHEETS_SERVER)
    assert evaluation.run_case(identity, "baseline", case[1], prompt, directory) == fresh
    assert len(provider["calls"]) == 2


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
@pytest.mark.parametrize("mode", [
    "malformed", "invalid_schema", "unblind", "missing_view", "failed_view", "text_view",
])
def test_invalid_model_evidence_is_not_scored_or_resumed(
    tmp_path: Path, case, provider, mode: str, reviewer: str,
) -> None:
    identity = _identity(case, reviewer=reviewer)
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


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
def test_foreign_sheet_cannot_redefine_recorded_allowlist(
    tmp_path: Path, case, provider, reviewer: str,
) -> None:
    identity = _identity(case, reviewer=reviewer)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    events_path = directory / result["events"]
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    for row in events:
        for node in mr._walk(row):
            if isinstance(node, dict) and node.get("name") == "mcp__sheets__view_sheet":
                node["input"]["sheet"] = 2
            elif isinstance(node, dict) and node.get("type") == "mcp_tool_call":
                node["arguments"]["sheet"] = 2
    _preserve_events(result, directory, events)
    assert result["review"]["blind"] is True
    with pytest.raises(ValueError, match="authorized sheet inspection"):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)
    fresh = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert fresh["error"] is None
    assert fresh["report"] != result["report"]
    assert len(provider["calls"]) == 2


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
def test_recorded_permission_bypass_is_rejected_despite_matching_report_hash(
    tmp_path: Path, case, provider, reviewer: str,
) -> None:
    identity = _identity(case, reviewer=reviewer)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    report_path = directory / result["report"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    command = report["extra"]["evidence"]["attempts"][0]["command"]
    if reviewer == "codex":
        command[command.index("--sandbox") + 1] = "danger-full-access"
    else:
        command[command.index("--permission-mode") + 1] = "bypassPermissions"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result["report_sha256"] = mr._sha256(report_path)
    result["review"] = report
    (directory / "result.json").write_text(json.dumps(result), encoding="utf-8")
    assert result["review"]["blind"] is True
    with pytest.raises(ValueError):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)
    fresh = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert fresh["error"] is None
    assert fresh["report"] != result["report"]
    assert len(provider["calls"]) == 2


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
def test_snapshots_recover_exact_inputs_after_original_files_are_overwritten(
    tmp_path: Path, case, provider, monkeypatch: pytest.MonkeyPatch, reviewer: str,
) -> None:
    raw_prompts = {
        "baseline": "Inspect Ø12.\r\nKeep the justified fit.\r\n".encode("utf-8"),
        "candidate": "Inspect Ø12 differently.\rUse the drawing.\n".encode("utf-8"),
    }
    originals = {version: tmp_path / f"arbitrary-{version}.txt" for version in raw_prompts}
    for version, original in originals.items():
        original.write_bytes(raw_prompts[version])
    schema_bytes = (
        json.dumps(mr.load_schema(), indent=2).replace("\n", "\r\n") + "\r\n"
    ).encode("utf-8")
    original_schema = tmp_path / "arbitrary-schema.json"
    original_schema.write_bytes(schema_bytes)
    monkeypatch.setattr(mr, "SCHEMA_FILE", original_schema)
    package = mr.ReviewPackage(case[1].name, "assembly", case[1].sources)
    identity = evaluation.make_identity(
        case[0], [package], {version: path.read_bytes() for version, path in originals.items()},
        reviewer=reviewer, model="model-a", effort="low", retries=0, timeout_s=30,
    )
    run_dir = tmp_path / "run"
    evaluation.persist_inputs(run_dir, identity, raw_prompts)
    results = {}
    for version in raw_prompts:
        prompt = (run_dir / "inputs" / f"{version}.txt").read_text(encoding="utf-8")
        results[version] = evaluation.run_case(identity, version, package, prompt, run_dir / version)
        assert results[version]["error"] is None
    for original in originals.values():
        original.write_bytes(b"replacement rubric")
    original_schema.write_bytes(b"{}")
    assert (run_dir / "inputs" / "schema.json").read_bytes() == schema_bytes
    for index, (version, raw) in enumerate(raw_prompts.items()):
        assert (run_dir / "inputs" / f"{version}.txt").read_bytes() == raw
        result = results[version]
        report = json.loads((run_dir / version / result["report"]).read_text(encoding="utf-8"))
        evidence = report["extra"]["evidence"]
        assert evidence["effective_prompt"] == provider["calls"][index]["prompt"]
        assert hashlib.sha256(evidence["effective_prompt"].encode("utf-8")).hexdigest() == (
            identity["prompts"][version]["effective_sha256"][package.name]
        )
        assert evidence["schema"].encode("utf-8") == schema_bytes
        evaluation.validate_evidence(result, identity, version, package, run_dir / version)


@pytest.mark.parametrize("field", ["effective_prompt", "schema"])
def test_provenance_content_must_match_identity_not_just_report_hash(
    tmp_path: Path, case, provider, field: str,
) -> None:
    identity = _identity(case)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    report_path = directory / result["report"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["extra"]["evidence"][field] += "\n"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result["report_sha256"] = mr._sha256(report_path)
    result["review"] = report
    with pytest.raises(ValueError):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
@pytest.mark.parametrize("failure", ["launch", "timeout", "nonzero_exit", "invalid_verdict"])
def test_complete_retry_evidence_resumes_after_provider_failure(
    tmp_path: Path, case, provider, monkeypatch: pytest.MonkeyPatch, failure: str,
    reviewer: str,
) -> None:
    identity = _identity(case, reviewer=reviewer)
    identity["retries"] = 1
    directory = tmp_path / "run"
    provider_run = mr.subprocess.run
    calls = 0

    def retrying_run(command, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            if failure == "launch":
                raise OSError("provider could not start")
            if failure == "timeout":
                raise mr.subprocess.TimeoutExpired(
                    command, kwargs["timeout"], output=b'{"type":"turn.started"}\n',
                    stderr=b"partial diagnostics",
                )
            if failure == "invalid_verdict":
                provider["mode"] = "malformed"
            process = provider_run(command, **kwargs)
            provider["mode"] = "valid"
            if failure == "nonzero_exit":
                process.returncode = 17
            return process
        return provider_run(command, **kwargs)

    monkeypatch.setattr(mr.subprocess, "run", retrying_run)
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    review = evaluation.validate_evidence(result, identity, "baseline", case[1], directory)
    failed, succeeded = review.extra["evidence"]["attempts"]
    assert failed["outcome"] == ("timed_out" if failure == "timeout" else "failed")
    assert failed["error"]
    assert failed["exit_code"] == {
        "launch": None, "timeout": None, "nonzero_exit": 17, "invalid_verdict": 0,
    }[failure]
    assert succeeded["outcome"] == "succeeded"
    assert evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory) == result
    assert calls == 2


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
@pytest.mark.parametrize("damage", [
    "unknown_field", "outcome", "exit_code", "stdout_events", "missing_stderr",
    "artifact_escape", "omitted_artifact", "session_id", "resume_command",
])
def test_retry_provenance_rejects_damage_despite_matching_report_hash(
    tmp_path: Path, case, provider, damage: str, reviewer: str,
) -> None:
    identity = _identity(case, reviewer=reviewer)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    report_path = directory / result["report"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    invocation = report["extra"]["evidence"]["attempts"][0]
    if damage == "unknown_field":
        invocation["unrecognized"] = True
    elif damage == "outcome":
        invocation["outcome"] = "failed"
        invocation["error"] = "Provider failed."
    elif damage == "exit_code":
        invocation["exit_code"] = False
    elif damage == "stdout_events":
        Path(invocation["stdout_file"]).write_text('{"type":"turn.started"}\n', encoding="utf-8")
    elif damage == "missing_stderr":
        Path(invocation["stderr_file"]).unlink()
    elif damage == "artifact_escape":
        outside = tmp_path / "outside.json"
        outside.write_bytes((Path(invocation["retained_cwd"]) / "schema.json").read_bytes())
        invocation["artifacts"] = [str(outside)]
    elif damage == "omitted_artifact":
        (Path(invocation["retained_cwd"]) / "unlisted.json").write_text("{}", encoding="utf-8")
        invocation["artifacts"] = []
    elif damage == "session_id":
        invocation["session_id"] = None
    else:
        invocation["resume_command"] = "codex resume forged-session"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result["report_sha256"] = mr._sha256(report_path)
    result["review"] = report
    with pytest.raises(ValueError):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
def test_mcp_provenance_preserves_sources_actual_argv_and_exact_replay(
    tmp_path: Path, case, provider, monkeypatch: pytest.MonkeyPatch, reviewer: str,
) -> None:
    def reject_text_grader(*args, **kwargs):
        raise AssertionError("The sheets evaluator must not use the text-only grader gate.")

    monkeypatch.setattr(mr, "count_codex_tool_events", reject_text_grader)
    provider["crops"] = [{"sheet": 1, "x1": 10, "y1": 20, "x2": 300, "y2": 400}]
    frozen_bytes = case[1].sources[0].read_bytes()
    identity = _identity(case, reviewer=reviewer)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    review = evaluation.validate_evidence(result, identity, "baseline", case[1], directory)
    invocation = review.extra["evidence"]["attempts"][0]
    cwd = Path(invocation["cwd"])
    retained = Path(invocation["retained_cwd"])
    assert not cwd.exists()
    assert cwd == provider["calls"][0]["cwd"]
    assert retained == (directory / result["report"]).parent / f"{case[1].name}.attempts" / cwd.name
    assert invocation["sources"] == [str(source.resolve()) for source in case[1].sources]
    assert invocation["command"] == provider["calls"][0]["command"]
    assert invocation["rerun_command"] == [
        argument.replace(str(cwd), str(retained)) for argument in invocation["command"]
    ]
    assert invocation["stdout_file"] == str(retained / "stdout.txt")
    assert invocation["stderr_file"] == str(retained / "stderr.txt")
    assert (retained / "schema.json").read_bytes() == (
        review.extra["evidence"]["schema"].encode("utf-8")
    )
    expected_files = {"schema.json", "stdout.txt", "stderr.txt"}
    if reviewer == "claude":
        expected_files.add("mcp.json")
        assert json.loads((retained / "mcp.json").read_text(encoding="utf-8")) == {
            "mcpServers": {"sheets": {
                "command": sys.executable,
                "args": [str(mr.SHEETS_SERVER), *(str(source.resolve()) for source in case[1].sources)],
            }},
        }
        assert invocation["artifacts"] == []
        assert invocation["command"][invocation["command"].index("--mcp-config") + 1] == str(cwd / "mcp.json")
    else:
        expected_files.add("verdict.json")
        assert invocation["artifacts"] == [str(retained / "verdict.json")]
        assert invocation["command"][invocation["command"].index("-C") + 1] == str(cwd)
        assert invocation["rerun_command"][invocation["rerun_command"].index("-C") + 1] == str(retained)
    assert {path.name for path in retained.iterdir()} == expected_files
    assert not (retained / "artifacts").exists()
    assert not list(retained.glob("*.png"))
    assert case[1].sources[0].read_bytes() == frozen_bytes
    assert review.source_sha256 == [case[0]["cases"][0]["sha256"]]
    assert review.extra["sheets_viewed"] == [1]
    assert review.extra["inspection_proven"] is True
    assert review.extra["crop_calls"] == 1
    assert review.extra["crops"] == [{"sheet": 1, "rect": [10, 20, 300, 400]}]
    assert evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory) == result
    assert len(provider["calls"]) == 1


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
def test_original_frozen_source_digest_is_revalidated_without_model_execution(
    tmp_path: Path, case, provider, reviewer: str,
) -> None:
    identity = _identity(case, reviewer=reviewer)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    source = case[1].sources[0]
    source.write_bytes(source.read_bytes() + b"tampered frozen source")
    with pytest.raises(ValueError, match="source changed"):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)
    fresh = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert fresh["error"] is not None
    assert len(provider["calls"]) == 1


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
@pytest.mark.parametrize("damage", ["missing", "foreign", "relative", "duplicate", "report_sources"])
def test_source_allowlist_cannot_be_redefined_by_preserved_report(
    tmp_path: Path, case, provider, reviewer: str, damage: str,
) -> None:
    identity = _identity(case, reviewer=reviewer)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    report = deepcopy(result["review"])
    invocation = report["extra"]["evidence"]["attempts"][0]
    if damage == "missing":
        invocation["sources"] = []
    elif damage == "foreign":
        foreign = tmp_path / "foreign.png"
        foreign.write_bytes(case[1].sources[0].read_bytes())
        invocation["sources"] = [str(foreign)]
    elif damage == "relative":
        invocation["sources"] = [case[1].sources[0].name]
    elif damage == "duplicate":
        invocation["sources"] *= 2
    else:
        report["sources"] = [str(Path(invocation["retained_cwd"]) / "sheet-1.png")]
    _preserve_report(result, directory, report)
    with pytest.raises(ValueError, match="allowlist|inputs/settings"):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
@pytest.mark.parametrize("damage", [
    "cwd_relative", "cwd_retained", "retained_missing", "retained_relative", "retained_escape",
    "rerun_missing", "rerun_original", "rerun_source", "actual_replay",
])
def test_actual_and_retained_paths_cannot_be_conflated_or_redirected(
    tmp_path: Path, case, provider, reviewer: str, damage: str,
) -> None:
    identity = _identity(case, reviewer=reviewer)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    report = deepcopy(result["review"])
    invocation = report["extra"]["evidence"]["attempts"][0]
    if damage == "cwd_relative":
        invocation["cwd"] = Path(invocation["cwd"]).name
    elif damage == "cwd_retained":
        invocation["cwd"] = invocation["retained_cwd"]
    elif damage == "retained_missing":
        invocation["retained_cwd"] = None
    elif damage == "retained_relative":
        invocation["retained_cwd"] = Path(invocation["retained_cwd"]).name
    elif damage == "retained_escape":
        invocation["retained_cwd"] = str(tmp_path / "machrev-foreign")
    elif damage == "rerun_missing":
        invocation["rerun_command"] = None
    elif damage == "rerun_original":
        invocation["rerun_command"] = invocation["command"]
    elif damage == "rerun_source":
        invocation["rerun_command"].append(str(tmp_path / "foreign.png"))
    else:
        invocation["command"] = invocation["rerun_command"]
    _preserve_report(result, directory, report)
    with pytest.raises(ValueError):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
@pytest.mark.parametrize("damage", [
    "schema_missing", "schema_content", "materialized_sheet", "unexpected_directory",
    "artifact_subdir", "extra_artifact", "stream_escape", "stream_relative",
])
def test_retained_workdir_requires_exact_direct_file_inventory(
    tmp_path: Path, case, provider, reviewer: str, damage: str,
) -> None:
    identity = _identity(case, reviewer=reviewer)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    report = deepcopy(result["review"])
    invocation = report["extra"]["evidence"]["attempts"][0]
    retained = Path(invocation["retained_cwd"])
    if damage == "schema_missing":
        (retained / "schema.json").unlink()
    elif damage == "schema_content":
        with (retained / "schema.json").open("ab") as stream:
            stream.write(b"\n")
    elif damage == "materialized_sheet":
        image = retained / "sheet-1.png"
        image.write_bytes(case[1].sources[0].read_bytes())
        invocation["artifacts"].append(str(image))
    elif damage == "unexpected_directory":
        (retained / "unexpected").mkdir()
    elif damage == "artifact_subdir":
        nested = retained / "artifacts"
        nested.mkdir()
        output = nested / "verdict.json"
        output.write_text(json.dumps(report["verdict"]), encoding="utf-8")
        invocation["artifacts"] = [str(output)]
    elif damage == "extra_artifact":
        output = retained / "unrelated.json"
        output.write_text("{}", encoding="utf-8")
        invocation["artifacts"].append(str(output))
    elif damage == "stream_escape":
        outside = tmp_path / "stdout.txt"
        outside.write_bytes(Path(invocation["stdout_file"]).read_bytes())
        invocation["stdout_file"] = str(outside)
    else:
        invocation["stdout_file"] = "stdout.txt"
    _preserve_report(result, directory, report)
    with pytest.raises(ValueError):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


@pytest.mark.parametrize("damage", [
    "missing", "server", "command", "script", "source", "source_order", "extra_setting",
])
def test_claude_mcp_config_must_match_exact_authorized_server_and_sources(
    tmp_path: Path, case, provider, damage: str,
) -> None:
    identity = _identity(case, reviewer="claude")
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    invocation = result["review"]["extra"]["evidence"]["attempts"][0]
    config_path = Path(invocation["retained_cwd"]) / "mcp.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    server = config["mcpServers"]["sheets"]
    if damage == "missing":
        config_path.unlink()
    else:
        if damage == "server":
            config["mcpServers"]["files"] = deepcopy(server)
        elif damage == "command":
            server["command"] = "foreign-python"
        elif damage == "script":
            server["args"][0] = str(tmp_path / "foreign-server.py")
        elif damage == "source":
            server["args"][1] = str(tmp_path / "foreign.png")
        elif damage == "source_order":
            server["args"].reverse()
        else:
            server["env"] = {"ALLOW_FILES": "1"}
        config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="MCP configuration"):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


@pytest.mark.parametrize("damage", ["source", "server", "legacy_image"])
def test_codex_mcp_argv_cannot_be_redirected_even_with_matching_replay(
    tmp_path: Path, case, provider, damage: str,
) -> None:
    identity = _identity(case)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    report = deepcopy(result["review"])
    invocation = report["extra"]["evidence"]["attempts"][0]
    command = invocation["command"]
    if damage == "legacy_image":
        command.extend(["-i", str(case[1].sources[0])])
    else:
        index = next(index for index, argument in enumerate(command) if argument.startswith("mcp_servers.sheets.args="))
        args = json.loads(command[index].split("=", 1)[1])
        args[1 if damage == "source" else 0] = str(tmp_path / "foreign.png")
        command[index] = f"mcp_servers.sheets.args={json.dumps(args)}"
    invocation["rerun_command"] = [
        argument.replace(invocation["cwd"], invocation["retained_cwd"]) for argument in command
    ]
    _preserve_report(result, directory, report)
    with pytest.raises(ValueError, match="command permissions/settings"):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
@pytest.mark.parametrize("damage", [
    "legacy_read", "foreign_server", "unknown_tool", "string_sheet", "bool_sheet",
    "extra_argument", "failed_view", "text_result", "missing_result", "crop_only",
])
def test_recomputed_mcp_evidence_rejects_forged_blind_review(
    tmp_path: Path, case, provider, reviewer: str, damage: str,
) -> None:
    identity = _identity(case, reviewer=reviewer)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    events_path = directory / result["events"]
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    for node in mr._walk(events):
        if not isinstance(node, dict):
            continue
        claude_call = node.get("name") == "mcp__sheets__view_sheet"
        codex_call = node.get("type") == "mcp_tool_call"
        if claude_call or codex_call:
            arguments = node["input" if claude_call else "arguments"]
            if damage == "legacy_read":
                if claude_call:
                    node["name"] = "Read"
                    node["input"] = {"file_path": str(case[1].sources[0])}
                else:
                    node["type"] = "tool_use"
                    node["name"] = "Read"
            elif damage == "foreign_server":
                if claude_call:
                    node["name"] = "mcp__files__view_sheet"
                else:
                    node["server"] = "files"
            elif damage == "unknown_tool":
                node["name" if claude_call else "tool"] = (
                    "mcp__sheets__list_files" if claude_call else "list_files"
                )
            elif damage == "string_sheet":
                arguments["sheet"] = "1"
            elif damage == "bool_sheet":
                arguments["sheet"] = True
            elif damage == "extra_argument":
                arguments["path"] = str(case[1].sources[0])
            elif damage == "crop_only":
                node["name" if claude_call else "tool"] = (
                    "mcp__sheets__crop" if claude_call else "crop"
                )
                arguments.update({"x1": 10, "y1": 20, "x2": 300, "y2": 400})
        if node.get("type") == "tool_result":
            if damage == "failed_view":
                node["is_error"] = True
            elif damage == "text_result":
                node["content"] = [{"type": "text", "text": "No image."}]
            elif damage == "missing_result":
                node["type"] = "text"
        elif node.get("type") == "mcp_tool_call" and node.get("status") == "completed":
            if damage == "failed_view":
                node["result"]["isError"] = True
            elif damage == "text_result":
                node["result"]["content"] = [{"type": "text", "text": "No image."}]
            elif damage == "missing_result":
                node["result"] = None
    _preserve_events(result, directory, events)
    assert result["review"]["blind"] is True
    with pytest.raises(ValueError, match="authorized sheet inspection"):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


def test_claude_successful_image_result_must_match_the_view_call_id(
    tmp_path: Path, case, provider,
) -> None:
    identity = _identity(case, reviewer="claude")
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    events = [json.loads(line) for line in (directory / result["events"]).read_text(encoding="utf-8").splitlines()]
    for node in mr._walk(events):
        if isinstance(node, dict) and node.get("type") == "tool_result":
            node["tool_use_id"] = "foreign-view"
    _preserve_events(result, directory, events)
    with pytest.raises(ValueError, match="authorized sheet inspection"):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
@pytest.mark.parametrize(("field", "value"), [
    ("sheets_viewed", []), ("sheets_viewed", [True]),
    ("inspection_proven", False), ("inspection_proven", 1),
    ("crop_calls", 1), ("crop_calls", False),
    ("crops", [{"sheet": 1, "rect": [10, 20, 300, 400]}]),
])
def test_recorded_inspection_fields_must_match_recomputed_evidence(
    tmp_path: Path, case, provider, reviewer: str, field: str, value: Any,
) -> None:
    identity = _identity(case, reviewer=reviewer)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    report = deepcopy(result["review"])
    report["extra"][field] = value
    _preserve_report(result, directory, report)
    with pytest.raises(ValueError, match="recorded sheet inspection"):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
def test_crop_history_counts_reused_call_ids_once_per_attempt(
    tmp_path: Path, case, provider, monkeypatch: pytest.MonkeyPatch, reviewer: str,
) -> None:
    identity = _identity(case, reviewer=reviewer)
    identity["retries"] = 1
    directory = tmp_path / "run"
    provider_run = mr.subprocess.run
    calls = 0

    def retrying_run(command, **kwargs):
        nonlocal calls
        calls += 1
        provider["crops"] = [{"sheet": 1, "x1": calls * 10, "y1": 20, "x2": 300, "y2": 400}]
        process = provider_run(command, **kwargs)
        if calls == 1:
            process.returncode = 17
        return process

    monkeypatch.setattr(mr.subprocess, "run", retrying_run)
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    review = evaluation.validate_evidence(result, identity, "baseline", case[1], directory)
    assert review.extra["crop_calls"] == 2
    assert review.extra["crops"] == [
        {"sheet": 1, "rect": [10, 20, 300, 400]},
        {"sheet": 1, "rect": [20, 20, 300, 400]},
    ]
    assert review.extra["sheets_viewed"] == [1]
    assert review.extra["inspection_proven"] is True
    assert evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory) == result
    assert calls == 2


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
@pytest.mark.parametrize("damage", ["unauthorized_retry", "missing_final_view"])
def test_final_attempt_cannot_launder_failed_attempt_tools_or_earlier_views(
    tmp_path: Path, case, provider, monkeypatch: pytest.MonkeyPatch,
    reviewer: str, damage: str,
) -> None:
    identity = _identity(case, reviewer=reviewer)
    identity["retries"] = 1
    directory = tmp_path / "run"
    provider_run = mr.subprocess.run
    calls = 0

    def retrying_run(command, **kwargs):
        nonlocal calls
        calls += 1
        provider["mode"] = (
            "unblind" if damage == "unauthorized_retry" and calls == 1
            else "missing_view" if damage == "missing_final_view" and calls == 2
            else "valid"
        )
        process = provider_run(command, **kwargs)
        if calls == 1:
            process.returncode = 17
        return process

    monkeypatch.setattr(mr.subprocess, "run", retrying_run)
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is not None
    report = deepcopy(result["review"])
    report["blind"] = True
    report["tool_events"] = 0
    report["extra"]["sheets_viewed"] = [1]
    report["extra"]["inspection_proven"] = True
    result["error"] = None
    _preserve_report(result, directory, report)
    with pytest.raises(ValueError, match="authorized sheet inspection"):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
def test_every_frozen_png_requires_its_own_successful_view(
    tmp_path: Path, case, provider, reviewer: str,
) -> None:
    second = tmp_path / "frozen-second.png"
    second.write_bytes(case[1].sources[0].read_bytes())
    package = mr.ReviewPackage(case[1].name, "assembly", (*case[1].sources, second))
    identity = _identity((case[0], package), reviewer=reviewer)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", package, "Rubric A", directory)
    assert result["error"] is None
    assert result["review"]["sheet_count"] == 2
    assert result["review"]["extra"]["sheets_viewed"] == [1, 2]
    events = [json.loads(line) for line in (directory / result["events"]).read_text(encoding="utf-8").splitlines()]
    for node in mr._walk(events):
        if not isinstance(node, dict):
            continue
        if node.get("name") == "mcp__sheets__view_sheet":
            node["input"]["sheet"] = 1
        elif node.get("type") == "mcp_tool_call":
            node["arguments"]["sheet"] = 1
    _preserve_events(result, directory, events)
    with pytest.raises(ValueError, match="authorized sheet inspection"):
        evaluation.validate_evidence(result, identity, "baseline", package, directory)


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
def test_pre_invocation_failure_has_no_fabricated_command_or_streams(
    tmp_path: Path, case, provider, monkeypatch: pytest.MonkeyPatch, reviewer: str,
) -> None:
    identity = _identity(case, reviewer=reviewer)
    identity["retries"] = 1
    builder_name = f"build_{reviewer}_command"
    builder = getattr(mr, builder_name)
    calls = 0

    def failing_builder(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("Could not prepare invocation.")
        return builder(**kwargs)

    monkeypatch.setattr(mr, builder_name, failing_builder)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    failed = result["review"]["extra"]["evidence"]["attempts"][0]
    assert failed["command"] is None
    assert failed["rerun_command"] is None
    assert failed["stdout_file"] is None
    assert failed["stderr_file"] is None
    assert failed["artifacts"] == []
    assert len(provider["calls"]) == 1
    assert evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory) == result


@pytest.mark.parametrize("field", ["report", "events"])
def test_checkpoint_file_paths_cannot_escape_the_case_directory(
    tmp_path: Path, case, provider, field: str,
) -> None:
    identity = _identity(case)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    outside = tmp_path / f"foreign-{field}.json"
    outside.write_bytes((directory / result[field]).read_bytes())
    result[field] = str(outside)
    result[f"{field}_sha256"] = mr._sha256(outside)
    with pytest.raises(ValueError, match="escapes case directory"):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


def test_codex_event_only_verdict_is_valid_without_inventing_an_output_artifact(
    tmp_path: Path, case, provider,
) -> None:
    identity = _identity(case)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    report = deepcopy(result["review"])
    invocation = report["extra"]["evidence"]["attempts"][0]
    (Path(invocation["retained_cwd"]) / "verdict.json").unlink()
    invocation["artifacts"] = []
    _preserve_report(result, directory, report)
    evaluation.validate_evidence(result, identity, "baseline", case[1], directory)
    assert evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory) == result
    assert len(provider["calls"]) == 1


@pytest.mark.parametrize("damage", ["output", "events"])
def test_codex_retained_output_and_event_verdict_must_both_match_report(
    tmp_path: Path, case, provider, damage: str,
) -> None:
    identity = _identity(case)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    forged = deepcopy(result["review"]["verdict"])
    forged["summary"] = "A different answer."
    if damage == "output":
        invocation = result["review"]["extra"]["evidence"]["attempts"][0]
        (Path(invocation["retained_cwd"]) / "verdict.json").write_text(json.dumps(forged), encoding="utf-8")
    else:
        events = [json.loads(line) for line in (directory / result["events"]).read_text(encoding="utf-8").splitlines()]
        for node in mr._walk(events):
            if isinstance(node, dict) and node.get("type") == "agent_message":
                node["text"] = json.dumps(forged)
        _preserve_events(result, directory, events)
    with pytest.raises(ValueError, match="Codex.*verdict"):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
@pytest.mark.parametrize("damage", ["cwd", "session", "outcome", "attempt_index"])
def test_retry_invocations_cannot_reuse_or_relabel_provenance(
    tmp_path: Path, case, provider, monkeypatch: pytest.MonkeyPatch,
    reviewer: str, damage: str,
) -> None:
    identity = _identity(case, reviewer=reviewer)
    identity["retries"] = 1
    provider_run = mr.subprocess.run
    calls = 0

    def retrying_run(command, **kwargs):
        nonlocal calls
        calls += 1
        process = provider_run(command, **kwargs)
        if calls == 1:
            process.returncode = 17
        return process

    monkeypatch.setattr(mr.subprocess, "run", retrying_run)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    report = deepcopy(result["review"])
    failed, succeeded = report["extra"]["evidence"]["attempts"]
    if damage == "cwd":
        succeeded["cwd"] = failed["cwd"]
        succeeded["retained_cwd"] = failed["retained_cwd"]
    elif damage == "session":
        original_session = succeeded["session_id"]
        succeeded["session_id"] = failed["session_id"]
        succeeded["resume_command"] = mr._resume_command(reviewer, failed["session_id"])
        if reviewer == "claude":
            succeeded["command"] = [
                argument.replace(original_session, failed["session_id"])
                for argument in succeeded["command"]
            ]
            succeeded["rerun_command"] = [
                argument.replace(original_session, failed["session_id"])
                for argument in succeeded["rerun_command"]
            ]
    elif damage == "outcome":
        failed["outcome"] = "succeeded"
        failed["error"] = None
        failed["exit_code"] = 0
    else:
        succeeded["attempt"] = 1
    _preserve_report(result, directory, report)
    with pytest.raises(ValueError):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)
