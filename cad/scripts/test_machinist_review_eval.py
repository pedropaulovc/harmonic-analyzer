"""Offline regressions for resumable, blind prompt-evaluation evidence."""

from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Callable
import uuid

import pytest

import machinist_review as mr
import machinist_review_eval as evaluation

CODEX_CLI_VERSION = "0.159.1"


def _runtime(reviewer: str) -> dict[str, str]:
    return {
        "Pillow": "11.0.0", "pypdfium2": "4.30.0", "mcp": "1.12.0",
        "reviewer_cli": f"codex-cli {CODEX_CLI_VERSION}" if reviewer == "codex"
        else "omp v18.7.0",
        **({"claude-agent-sdk": "0.1.76", "routing": "sdk-api-pool-then-omp-v1"} if reviewer == "claude" else {}),
    }


def _rollout_row(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"timestamp": "2026-10-12T16:46:44.250Z", "type": kind, "payload": payload}


def _rollout_message(role: str, text: str, kinds: list[str]) -> dict[str, Any]:
    return _rollout_row("response_item", {
        "type": "message", "id": f"msg_{role}_{len(text)}", "role": role,
        "content": [{"type": "output_text" if role == "assistant" else "input_text", "text": text}],
        "internal_chat_message_metadata_passthrough": {"content_item_kinds": kinds},
    })


def _rollout_meta(session_id: str, cwd: Path, cli_version: str = CODEX_CLI_VERSION) -> dict[str, Any]:
    return _rollout_row("session_meta", {
        "session_id": session_id, "id": session_id, "timestamp": "2026-10-12T16:46:42.663Z",
        "cwd": str(cwd), "runtime_workspace_roots": [str(cwd)], "originator": "codex_exec",
        "cli_version": cli_version, "source": "exec", "thread_source": "user",
        "model_provider": "openai", "base_instructions": {"text": "You are Codex."},
    })


# Shapes recorded by codex 0.159.1 in the review's smoke rollout: global skills
# and ~/.codex/AGENTS.md precede the rubric, and a code-mode cell enumerates tools
# without leaving any item in the `codex exec --json` stream.
RECORDED_SKILLS_CONTEXT = _rollout_row("response_item", {
    "type": "message", "id": "msg_01a13102-6a1a-7cc2-a154-52d0292c39a0", "role": "developer",
    "content": [{"type": "input_text", "text": (
        "<skills_instructions>\n## Skills\nSkill roots: C:/Users/pedro/.agents/skills, "
        "~/.codex/skills/.system\n</skills_instructions>\n<recommended_plugins>\n</recommended_plugins>"
    )}],
    "internal_chat_message_metadata_passthrough": {"content_item_kinds": ["host_skills.instructions"]},
})
RECORDED_AGENTS_CONTEXT = _rollout_row("response_item", {
    "type": "message", "id": "msg_01a13102-6a1a-7cc2-a154-52e7197e7398", "role": "user",
    "content": [{"type": "input_text", "text": (
        "# AGENTS.md instructions for C:\\Users\\pedro\\.codex\n\n<INSTRUCTIONS>\n"
        "Reviewer family must differ from the author.\n</INSTRUCTIONS>"
    )}],
    "internal_chat_message_metadata_passthrough": {"content_item_kinds": ["agents_md.instructions"]},
})
RECORDED_EXEC_CELL = [
    _rollout_row("response_item", {
        "type": "custom_tool_call", "id": "ctc_01afb38264e57b6f016acd0ef5349c8199bd",
        "status": "completed", "call_id": "call_1b2751ac287e408c8bfd37bca8cbc7a3",
        "name": "exec",
        "input": "text(ALL_TOOLS.filter(t => !t.name.startsWith('mcp__sheets')).map(t => t.name))",
    }),
    _rollout_row("response_item", {
        "type": "custom_tool_call_output", "id": "ctco_01a13102-753f-7c92-ad47-5615c51d5fd7",
        "call_id": "call_1b2751ac287e408c8bfd37bca8cbc7a3",
        "output": [{"type": "input_text", "text": "Script completed\nWall time 0.0 seconds\nOutput:\n"}],
    }),
]
RECORDED_SHELL_CALL = _rollout_row("response_item", {
    "type": "function_call", "id": "fc_shell", "name": "shell",
    "arguments": json.dumps({"command": ["pwd"]}), "call_id": "call_shell",
})


def _rollout_sheet_call(
    tool: str, arguments: dict[str, Any], call_id: str, image: bytes,
    *, ok: bool = True, image_result: bool = True,
) -> list[dict[str, Any]]:
    """A direct (non-code-mode) sheets call as recorded with tool_mode=direct."""
    encoded = base64.b64encode(image).decode("ascii")
    content = [{"type": "image", "data": encoded, "mimeType": "image/png"}] if image_result else [
        {"type": "text", "text": "No image."}
    ]
    output = [{"type": "input_text", "text": "Wall time: 0.0115 seconds\nOutput:"}]
    output.append(
        {"type": "input_image", "image_url": f"data:image/png;base64,{encoded}", "detail": "high"}
        if image_result else {"type": "input_text", "text": "No image."}
    )
    return [
        _rollout_row("response_item", {
            "type": "function_call", "id": f"fc_{call_id}", "name": tool,
            "namespace": "mcp__sheets", "arguments": json.dumps(arguments), "call_id": call_id,
        }),
        _rollout_row("event_msg", {"type": "item_completed", "item": {
            "type": "McpToolCall", "id": call_id, "server": "sheets", "tool": tool,
            "arguments": arguments, "status": "completed" if ok else "failed",
            "result": {"content": content, "isError": not ok},
        }}),
        _rollout_row("response_item", {
            "type": "function_call_output", "id": f"fco_{call_id}", "call_id": call_id,
            "output": output,
        }),
    ]


def _rollout_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _edit_rollouts(
    result: dict[str, Any], edit: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
) -> None:
    """Rewrite every retained Codex rollout; rollouts are not covered by result hashes."""
    for invocation in result["review"]["extra"]["evidence"]["attempts"]:
        if invocation["rollout_file"] is not None:
            path = Path(invocation["rollout_file"])
            _write_rows(path, edit(_rollout_rows(path)))


def _edit_sheet_calls(
    result: dict[str, Any], events: list[dict[str, Any]], edit: Callable[[dict[str, Any]], None],
) -> None:
    """Apply one edit to every recorded form of each sheets call.

    That is Claude tool_use inputs, Codex --json mcp_tool_call items and both
    authoritative Codex rollout records (function_call and McpToolCall).
    """
    for node in mr._walk(events):
        if isinstance(node, dict) and str(node.get("name", "")).startswith("mcp__sheets__"):
            call = {"server": "sheets", "tool": node["name"].removeprefix("mcp__sheets__"),
                    "arguments": node["input"]}
            edit(call)
            node["name"] = f"mcp__{call['server']}__{call['tool']}"
            node["input"] = call["arguments"]
        elif isinstance(node, dict) and node.get("type") == "mcp_tool_call":
            call = {key: node[key] for key in ("server", "tool", "arguments")}
            edit(call)
            node.update(call)

    def rewrite(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for row in rows:
            payload = row.get("payload") or {}
            if payload.get("type") == "function_call" and payload.get("namespace") == "mcp__sheets":
                call = {"server": "sheets", "tool": payload["name"],
                        "arguments": json.loads(payload["arguments"])}
                edit(call)
                payload.update(namespace=f"mcp__{call['server']}", name=call["tool"],
                               arguments=json.dumps(call["arguments"]))
            item = payload.get("item") if payload.get("type") == "item_completed" else None
            if isinstance(item, dict) and item.get("type") == "McpToolCall":
                call = {key: item[key] for key in ("server", "tool", "arguments")}
                edit(call)
                item.update(call)
        return rows

    _edit_rollouts(result, rewrite)


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


def _neutral_output(tool: str, arguments: dict[str, Any]) -> str:
    """Codex's built-in resource helper text against the resource-free sheets server."""
    if tool == "read_mcp_resource":
        return f"resources/read failed: Unknown resource: {arguments.get('uri')}"
    key = "resources" if tool == "list_mcp_resources" else "resourceTemplates"
    scope = {"server": arguments["server"]} if "server" in arguments else {}
    return json.dumps({**scope, key: []})


def _neutral_call(
    reviewer: str, tool: str, arguments: dict[str, Any], call_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """One built-in resource request: (rollout rows, provider event-stream items).

    Codex declares it as an un-namespaced function call and records the native
    execution as an McpToolCall on its own ``codex`` server. Claude has no such
    neutral helper; its ListMcpResourcesTool use is an ordinary foreign tool.
    """
    text = _neutral_output(tool, arguments)
    failed = tool == "read_mcp_resource"
    if reviewer == "claude":
        return [], [
            {"type": "assistant", "message": {"content": [{
                "type": "tool_use", "id": call_id, "name": "ListMcpResourcesTool",
                "input": arguments,
            }]}},
            {"type": "user", "message": {"content": [{
                "type": "tool_result", "tool_use_id": call_id,
                "content": [{"type": "text", "text": text}], "is_error": failed,
            }]}},
        ]
    result = {"content": [{"type": "text", "text": text}], "isError": failed}
    status = "failed" if failed else "completed"
    rollout = [
        _rollout_row("response_item", {
            "type": "function_call", "id": f"fc_{call_id}", "name": tool,
            "arguments": json.dumps(arguments), "call_id": call_id,
        }),
        _rollout_row("event_msg", {"type": "item_completed", "item": {
            "type": "McpToolCall", "id": call_id, "server": "codex", "tool": tool,
            "arguments": arguments, "status": status, "result": result,
        }}),
        _rollout_row("response_item", {
            "type": "function_call_output", "id": f"fco_{call_id}", "call_id": call_id,
            "output": text,
        }),
    ]
    item = {
        "id": call_id, "type": "mcp_tool_call", "server": "codex", "tool": tool,
        "arguments": arguments, "status": "in_progress", "result": None, "error": None,
    }
    return rollout, [
        {"type": "item.started", "item": item},
        {"type": "item.completed", "item": {**item, "status": status, "result": result}},
    ]


@pytest.fixture
def provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {
        "calls": [], "mode": "valid", "crops": [], "rollouts": {}, "runtime_queries": [],
        # (tool, arguments) built-in resource requests made before viewing.
        "neutral": [],
        "verdict": {
            "verdict": "FIX", "summary": "Fit is justified; a hole remains unlocated.",
            "blockers": [{"where": "front view", "issue": "Hole location is absent.",
                          "fix": "Locate the hole from the datum edges."}],
            "over_specification": [], "clarity": [], "minor": [],
        },
    }
    # Never touch the operator's Codex home.
    monkeypatch.setattr(mr, "CODEX_HOME", tmp_path / "codex-home")

    def prepare_codex_environment(*, attempt_dir: Path, model: str, **kwargs: Any) -> dict[str, str]:
        (Path(attempt_dir) / "codex-models.json").write_text(json.dumps({"models": [{
            "slug": model, "display_name": model, "tool_mode": "direct",
            "supports_search_tool": False,
        }]}), encoding="utf-8")
        return {**os.environ, "CODEX_HOME": str(kwargs.get("codex_home", mr.CODEX_HOME))}

    def load_codex_rollout(session_id: str, **kwargs: Any) -> tuple[Path, list[dict[str, Any]]]:
        if session_id not in state["rollouts"]:
            raise FileNotFoundError(f"no Codex rollout for {session_id}")
        path = state["rollouts"][session_id]
        return path, _rollout_rows(path)

    def runtime_versions(reviewer: str) -> dict[str, str]:
        state["runtime_queries"].append(reviewer)
        return _runtime(reviewer)

    def fake_run(command: list[str], **kwargs: Any):
        cwd = Path(kwargs["cwd"])
        reviewer = kwargs["reviewer"]
        assert reviewer == ("codex" if "exec" in command else "claude")
        if reviewer == "codex":
            server_args = json.loads(next(
                argument.split("=", 1)[1] for argument in command
                if argument.startswith("mcp_servers.sheets.args=")
            ))
            attempt_dir = Path(command[command.index("-o") + 1]).parent
        else:
            config = json.loads(Path(command[command.index("--mcp-config") + 1]).read_text(encoding="utf-8"))
            server_args = config["mcpServers"]["sheets"]["args"]
            attempt_dir = Path(command[command.index("--mcp-config") + 1]).parent
        assert server_args[0] == str(mr.SHEETS_SERVER)
        sources = [Path(source) for source in server_args[1:]]
        assert all(
            source.is_absolute() and not source.is_relative_to(cwd)
            and not source.is_relative_to(attempt_dir)
            for source in sources
        )
        images = [source.read_bytes() for source in sources]
        state["calls"].append({
            "command": command, "prompt": kwargs["input"], "cwd": cwd,
            "attempt_dir": attempt_dir,
            "files": {path.name for path in attempt_dir.iterdir()},
            "codex_home": (kwargs.get("env") or {}).get("CODEX_HOME"),
            "sources": sources, "images": images,
        })
        verdict = deepcopy(state["verdict"])
        if state["mode"] == "invalid_schema":
            del verdict["blockers"]
        text = "not JSON" if state["mode"] == "malformed" else json.dumps(verdict)
        session_id = str(uuid.uuid4())
        events = []
        rollout = [
            _rollout_meta(session_id, cwd),
            _rollout_row("event_msg", {"type": "task_started", "turn_id": "turn-1"}),
        ]
        if state["mode"] == "injected_context":
            rollout.extend([RECORDED_SKILLS_CONTEXT, RECORDED_AGENTS_CONTEXT])
        rollout.append(_rollout_message("user", kwargs["input"], ["user.text"]))
        if state["mode"] == "exec_cell":
            rollout.extend(RECORDED_EXEC_CELL)
        if reviewer == "codex":
            events.append({"type": "thread.started", "thread_id": session_id})
        else:
            requested_session = command[command.index("--session-id") + 1]
            kwargs["transport_provenance"].update(
                transport="claude_agent_sdk", session_id=requested_session,
                requested_session_id=requested_session, credential_id="fixture",
                credential_fingerprint="a" * 64,
            )
            events.append({
                "type": "control_response",
                "response": {
                    "subtype": "success",
                    "request_id": "sheets-status",
                    "response": {"mcpServers": [{
                        "name": "sheets", "status": "connected",
                        "config": {"type": "stdio", **config["mcpServers"]["sheets"]},
                        "tools": [{"name": "view_sheet"}, {"name": "crop"}],
                    }]},
                },
            })
            events.append({
                "type": "system", "subtype": "init",
                "session_id": command[command.index("--session-id") + 1],
            })
        for index, (tool, arguments) in enumerate(state["neutral"]):
            neutral_rollout, neutral_events = _neutral_call(
                reviewer, tool, arguments, f"resource_{index}",
            )
            rollout.extend(neutral_rollout)
            events.extend(neutral_events)
        if state["mode"] != "missing_view":
            for sheet, image in enumerate(images, start=1):
                options = {
                    "ok": state["mode"] != "failed_view",
                    "image_result": state["mode"] != "text_view",
                }
                events.extend(_sheet_call(
                    reviewer, "view_sheet", {"sheet": sheet}, f"view_{sheet}", image, **options,
                ))
                rollout.extend(_rollout_sheet_call(
                    "view_sheet", {"sheet": sheet}, f"view_{sheet}", image, **options,
                ))
        for index, crop in enumerate(state["crops"]):
            events.extend(_sheet_call(reviewer, "crop", crop, f"crop_{index}", images[0]))
            rollout.extend(_rollout_sheet_call("crop", crop, f"crop_{index}", images[0]))
        rollout.extend([
            _rollout_row("token_usage_record", {"session_id": session_id, "usage": {
                "input_tokens": 10, "cached_input_tokens": 0, "output_tokens": 10,
            }}),
            _rollout_message("assistant", text, ["unknown"]),
            _rollout_row("event_msg", {"type": "task_complete", "turn_id": "turn-1"}),
        ])
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
            rollout.insert(3, RECORDED_SHELL_CALL)
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
        if reviewer == "codex" and state["mode"] != "no_rollout":
            path = mr.CODEX_HOME / "sessions" / f"rollout-{session_id}.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_rows(path, rollout)
            state["rollouts"][session_id] = path
        return mr.subprocess.CompletedProcess(
            command, 1 if state["mode"] == "provider_error" else 0,
            stdout="\n".join(json.dumps(event) for event in events),
            stderr="quota exhausted" if state["mode"] == "provider_error" else "",
        )

    monkeypatch.setattr(mr.shutil, "which", lambda executable: executable)
    monkeypatch.setattr(mr, "_run_reviewer", fake_run)
    monkeypatch.setattr(mr, "prepare_codex_environment", prepare_codex_environment)
    monkeypatch.setattr(mr, "relink_codex_auth", lambda home: None)
    monkeypatch.setattr(mr, "load_codex_rollout", load_codex_rollout)
    monkeypatch.setattr(evaluation, "runtime_versions", runtime_versions)
    return state


def _identity(
    case, *, prompt: str = "Rubric A", reviewer: str = "codex", model: str = "model-a",
    runtime: dict[str, str] | None = None,
):
    manifest, package = case
    return evaluation.make_identity(
        manifest, [package], {"baseline": prompt.encode(), "candidate": b"Rubric B"},
        reviewer=reviewer, model=model, effort="low", retries=0, timeout_s=30,
        runtime=runtime or _runtime(reviewer),
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


def _events(directory: Path, result) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (directory / result["events"]).read_text(encoding="utf-8").splitlines()]


def _argv_path(argument: str) -> Path | None:
    """The file an argv element names, bare or as a ``key=<JSON string>`` setting."""
    if Path(argument).is_absolute():
        return Path(argument)
    key, separator, value = argument.partition("=")
    try:
        decoded = json.loads(value) if separator else None
    except ValueError:
        return None
    return Path(decoded) if isinstance(decoded, str) and Path(decoded).is_absolute() else None


def test_runtime_versions_are_queried_once_and_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    packages: list[str] = []
    runs: list[list[str]] = []
    outcome = {"returncode": 0}

    def version(name: str) -> str:
        packages.append(name)
        return f"{name}-1.0"

    def run(command: list[str], **kwargs: Any):
        runs.append(command)
        return evaluation.subprocess.CompletedProcess(
            command, outcome["returncode"], stdout=f"codex-cli {CODEX_CLI_VERSION}\n", stderr="denied",
        )

    monkeypatch.setattr(evaluation.importlib.metadata, "version", version)
    monkeypatch.setattr(evaluation.shutil, "which", lambda name: f"C:/bin/{name}.exe")
    monkeypatch.setattr(evaluation.subprocess, "run", run)
    evaluation.runtime_versions.cache_clear()
    try:
        expected = {
            "Pillow": "Pillow-1.0", "pypdfium2": "pypdfium2-1.0", "mcp": "mcp-1.0",
            "reviewer_cli": f"codex-cli {CODEX_CLI_VERSION}",
        }
        assert evaluation.runtime_versions("codex") == expected
        assert evaluation.runtime_versions("codex") == expected
        assert packages == ["Pillow", "pypdfium2", "mcp"]
        assert runs == [["C:/bin/codex.exe", "--version"]]
        outcome["returncode"] = 1
        with pytest.raises(RuntimeError, match="--version"):
            evaluation.runtime_versions("claude")
    finally:
        evaluation.runtime_versions.cache_clear()


def test_sdk_runtime_provenance_does_not_require_claude_or_omp_executable(monkeypatch):
    queries = []
    monkeypatch.setattr(evaluation.importlib.metadata, "version", lambda name: f"{name}-fixture")
    def unavailable(name):
        queries.append(name)
        return None
    monkeypatch.setattr(evaluation.shutil, "which", unavailable)
    evaluation.runtime_versions.cache_clear()
    try:
        runtime = evaluation.runtime_versions("claude")
        assert runtime["claude-agent-sdk"] == "claude-agent-sdk-fixture"
        assert runtime["reviewer_cli"] == "omp-unavailable"
        assert runtime["routing"] == "sdk-api-pool-then-omp-v1"
        assert queries == ["omp"]
    finally:
        evaluation.runtime_versions.cache_clear()



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
    # Runtime versions belong to the run identity and are fetched once, not per case.
    assert identity["runtime"] == _runtime("codex")
    assert provider["runtime_queries"] == ["codex"]
    assert len(provider["calls"]) == 2
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
    source_snapshots = []
    for index, (package, prompt) in enumerate([
        (part, ""), (assembly, ""), (assembly, "Rubric A"), (assembly, "Rubric B"),
    ]):
        identity = _identity((case[0], package), prompt=prompt, reviewer=reviewer)
        result = evaluation.run_case(identity, "baseline", package, prompt, tmp_path / str(index))
        assert result["error"] is None
        source_snapshots.append([
            Path(source)
            for source in result["review"]["extra"]["evidence"]["attempts"][0]["sources"]
        ])
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
    attempt_dirs = {call["attempt_dir"] for call in provider["calls"]}
    assert len(attempt_dirs) == len(provider["calls"])
    for call, sources in zip(provider["calls"], source_snapshots):
        # Each attempt runs in its own neutral directory, outside the repository.
        assert call["cwd"] == call["attempt_dir"]
        assert not any((parent / ".git").exists() for parent in call["cwd"].resolve().parents)
        if reviewer == "codex":
            assert call["files"] == {"schema.json", "codex-models.json"}
            assert call["codex_home"] == str(mr.CODEX_HOME)
        else:
            assert call["files"] == {"schema.json", "mcp.json"}
        assert call["sources"] == sources
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
            assert args[1:] == [str(source.resolve()) for source in sources]


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
    review = evaluation.validate_evidence(first, identity, "baseline", case[1], directory)
    assert review.blind and review.tool_events == 0
    assert review.extra["inspection_proven"] is True
    if reviewer == "claude":
        (attempt,) = review.extra["evidence"]["attempts"]
        raw_events = [
            json.loads(line)
            for line in Path(attempt["stdout_file"]).read_text(encoding="utf-8").splitlines()
        ]
        status = next(row for row in raw_events if row.get("type") == "control_response")
        config = status["response"]["response"]["mcpServers"][0]["config"]
        assert config["type"] == "stdio" and config["command"] == sys.executable
        assert config["args"][0] == str(mr.SHEETS_SERVER)
    assert evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory) == first
    assert len(provider["calls"]) == 1
    summary = evaluation.aggregate(identity, [first])
    assert summary["results"][0]["outcome"] == "unassessed"
    assert summary["counts"]["baseline"] == {"pass": 0, "fail": 0, "unassessed": 1, "invalid": 0}


def test_codex_short_attempt_startup_budget_survives_evidence_reconstruction(
    tmp_path: Path, case, provider,
) -> None:
    identity = _identity(case)
    identity["timeout_s"] = 12.5
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    review = evaluation.validate_evidence(result, identity, "baseline", case[1], directory)
    (attempt,) = review.extra["evidence"]["attempts"]
    setting = "mcp_servers.sheets.startup_timeout_sec=12.5"
    assert setting in attempt["command"]
    assert setting in attempt["retained_argv"]
    assert review.blind and review.extra["inspection_proven"] is True
    assert evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory) == result
    assert len(provider["calls"]) == 1


@pytest.mark.parametrize("change", ["prompt", "image", "model", "sheets_server", "runtime"])
def test_changed_identity_executes_fresh_model_without_overwriting_old_evidence(
    tmp_path: Path, case, provider, change: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "run"
    old_identity = _identity(case)
    first = evaluation.run_case(old_identity, "baseline", case[1], "Rubric A", directory)
    assert first["error"] is None
    old_report = (directory / first["report"]).read_bytes()
    prompt, model, runtime = "Rubric A", "model-a", _runtime("codex")
    if change == "prompt":
        prompt = "New rubric"
    elif change == "image":
        case[1].sources[0].write_bytes(case[1].sources[0].read_bytes() + b"changed")
        case[0]["cases"][0]["sha256"] = mr._sha256(case[1].sources[0])
    elif change == "model":
        model = "model-b"
    elif change == "runtime":
        # A renderer upgrade can change image bytes without touching any source.
        runtime["pypdfium2"] = "5.0.0"
    else:
        original_sha256 = mr._sha256
        monkeypatch.setattr(mr, "_sha256", lambda path: (
            hashlib.sha256(b"changed sheet-server rendering").hexdigest()
            if Path(path) == mr.SHEETS_SERVER else original_sha256(path)
        ))
    identity = _identity(case, prompt=prompt, model=model, runtime=runtime)
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
    elif change == "runtime":
        assert identity["runtime"] != old_identity["runtime"]
    else:
        assert identity["sheets_server_sha256"] != old_identity["sheets_server_sha256"]
        assert identity["sheets_server_sha256"] == mr._sha256(mr.SHEETS_SERVER)
    assert evaluation.run_case(identity, "baseline", case[1], prompt, directory) == fresh
    assert len(provider["calls"]) == 2


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
@pytest.mark.parametrize("mode", [
    "malformed", "invalid_schema", "unblind", "missing_view", "failed_view", "text_view",
    "exec_cell", "injected_context", "no_rollout",
])
def test_invalid_model_evidence_is_not_scored_or_resumed(
    tmp_path: Path, case, provider, mode: str, reviewer: str,
) -> None:
    if reviewer == "claude" and mode in ("exec_cell", "injected_context", "no_rollout"):
        pytest.skip("Codex rollout evidence only")
    identity = _identity(case, reviewer=reviewer)
    directory = tmp_path / "run"
    provider["mode"] = mode
    invalid = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert invalid["error"] is not None
    assert evaluation.aggregate(identity, [invalid])["results"][0]["outcome"] == "invalid"
    with pytest.raises(ValueError):
        evaluation.validate_evidence(invalid, identity, "baseline", case[1], directory)
    if mode in ("exec_cell", "injected_context", "no_rollout") and "events" in invalid:
        # The --json projection is clean; only the rollout reveals the violation.
        assert mr.evaluate_sheet_evidence(
            _events(directory, invalid), reviewer="codex", sheet_count=1,
        )["tool_events"] == 0
        assert invalid["review"]["passed"] is False
        if mode != "no_rollout":
            assert invalid["review"]["blind"] is False
    provider["mode"] = "valid"
    fresh = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert fresh["error"] is None
    assert fresh["report"] != invalid["report"]
    assert len(provider["calls"]) == 2


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
def test_provider_error_is_blind_but_never_passes_or_scores(
    tmp_path: Path, case, provider, reviewer: str,
) -> None:
    identity = _identity(case, reviewer=reviewer)
    directory = tmp_path / "run"
    provider["mode"] = "provider_error"
    failed = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert failed["error"] is not None
    # A quota/exit failure is not a blindness violation, but it is never a pass.
    assert failed["review"]["error"]
    assert failed["review"]["blind"] is True
    assert failed["review"]["tool_events"] == 0
    assert failed["review"]["passed"] is False
    assert evaluation.aggregate(identity, [failed])["results"][0]["outcome"] == "invalid"
    with pytest.raises(ValueError):
        evaluation.validate_evidence(failed, identity, "baseline", case[1], directory)


@pytest.mark.parametrize("damage", [
    "hash", "malformed_report", "verdict_schema", "blind_flag", "event_verdict", "cached_review",
    "context_errors",
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
        elif damage == "context_errors":
            content["extra"]["context_errors"] = ["AGENTS.md before prompt"]
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
    events = _events(directory, result)

    def foreign_sheet(call: dict[str, Any]) -> None:
        if call["tool"] == "view_sheet":
            call["arguments"]["sheet"] = 2

    _edit_sheet_calls(result, events, foreign_sheet)
    _preserve_events(result, directory, events)
    assert result["review"]["blind"] is True
    with pytest.raises(ValueError, match="authorized sheet inspection"):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)
    fresh = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert fresh["error"] is None
    assert fresh["report"] != result["report"]
    assert len(provider["calls"]) == 2


@pytest.mark.parametrize("reviewer", ["codex"])
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
        runtime=_runtime(reviewer),
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
    provider_run = mr._run_reviewer
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

    monkeypatch.setattr(mr, "_run_reviewer", retrying_run)
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
    if reviewer == "codex":
        # A failed attempt with a started thread keeps its rollout too.
        started = failure in ("nonzero_exit", "invalid_verdict")
        assert (failed["rollout_file"] is not None) is started
        assert succeeded["rollout_file"] == str(Path(succeeded["retained_dir"]) / "rollout.jsonl")
        assert failed["cwd"] == failed["attempt_dir"]
        assert succeeded["cwd"] == succeeded["attempt_dir"]
    assert failed["attempt_dir"] != succeeded["attempt_dir"]
    assert evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory) == result
    assert calls == 2


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
@pytest.mark.parametrize("damage", [
    "unknown_field", "legacy_field", "outcome", "exit_code", "stdout_events", "missing_stderr",
    "artifact_escape", "omitted_artifact", "session_id", "resume_command", "retention_warning",
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
    elif damage == "legacy_field":
        # The renamed field must not survive: it claimed a runnable replay.
        invocation["rerun_command"] = invocation.pop("retained_argv")
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
        outside.write_bytes((Path(invocation["retained_dir"]) / "schema.json").read_bytes())
        invocation["artifacts"] = [str(outside)]
    elif damage == "omitted_artifact":
        (Path(invocation["retained_dir"]) / "unlisted.json").write_text("{}", encoding="utf-8")
        invocation["artifacts"] = []
    elif damage == "session_id":
        invocation["session_id"] = None
    elif damage == "retention_warning":
        invocation["retention_warning"] = " "
    else:
        invocation["resume_command"] = "codex resume forged-session"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result["report_sha256"] = mr._sha256(report_path)
    result["review"] = report
    with pytest.raises(ValueError):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
def test_mcp_provenance_preserves_sources_actual_argv_and_path_adapted_argv(
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
    attempt_dir = Path(invocation["attempt_dir"])
    cwd = Path(invocation["cwd"])
    retained = Path(invocation["retained_dir"])
    assert not attempt_dir.exists()
    assert invocation["retention_warning"] is None
    assert attempt_dir == provider["calls"][0]["attempt_dir"]
    assert cwd == provider["calls"][0]["cwd"]
    assert retained == (directory / result["report"]).parent / f"{case[1].name}.attempts" / attempt_dir.name
    report_path = directory / result["report"]
    snapshot_sources = [
        report_path.parent / f"{case[1].name}.sources" / source.name
        for source in case[1].sources
    ]
    assert invocation["sources"] == [str(source.resolve()) for source in snapshot_sources]
    assert [mr._sha256(source) for source in snapshot_sources] == [
        mr._sha256(source) for source in case[1].sources
    ]
    command = invocation["command"]
    assert command == provider["calls"][0]["command"]
    # retained_argv is not a replay. It only re-points the attempt's own files at
    # their retained copies; sources and every setting stay as run.
    retained_argv = invocation["retained_argv"]
    assert len(retained_argv) == len(command)
    moved = 0
    for original, adapted in zip(command, retained_argv):
        original_path = _argv_path(original)
        if original_path is not None and original_path.is_relative_to(attempt_dir):
            moved += 1
            adapted_path = _argv_path(adapted)
            assert adapted_path == retained / original_path.relative_to(attempt_dir)
            assert adapted_path.exists()
        else:
            assert adapted == original
    assert moved >= 1
    assert not any(str(attempt_dir) in argument for argument in retained_argv)
    assert invocation["stdout_file"] == str(retained / "stdout.txt")
    assert invocation["stderr_file"] == str(retained / "stderr.txt")
    assert (retained / "schema.json").read_bytes() == (
        review.extra["evidence"]["schema"].encode("utf-8")
    )
    expected_files = {"schema.json", "stdout.txt", "stderr.txt"}
    if reviewer == "claude":
        expected_files.add("mcp.json")
        assert cwd == attempt_dir
        assert invocation["codex_home"] is None
        assert invocation["rollout_file"] is None
        assert json.loads((retained / "mcp.json").read_text(encoding="utf-8")) == {
            "mcpServers": {"sheets": {
                "command": sys.executable,
                "args": [str(mr.SHEETS_SERVER), *(str(source.resolve()) for source in snapshot_sources)],
            }},
        }
        assert invocation["artifacts"] == []
        assert command[command.index("--mcp-config") + 1] == str(attempt_dir / "mcp.json")
    else:
        expected_files |= {"verdict.json", "codex-models.json", "rollout.jsonl"}
        assert cwd == attempt_dir
        assert invocation["codex_home"] == str(mr.CODEX_HOME)
        assert sorted(invocation["artifacts"]) == [
            str(retained / "codex-models.json"), str(retained / "verdict.json"),
        ]
        assert invocation["rollout_file"] == str(retained / "rollout.jsonl")
        meta = _rollout_rows(retained / "rollout.jsonl")[0]
        assert meta["payload"]["id"] == invocation["session_id"]
        assert command[command.index("-C") + 1] == str(attempt_dir)
        assert retained_argv[retained_argv.index("-C") + 1] == str(retained)
    assert {path.name for path in retained.iterdir()} == expected_files
    assert not (retained / "artifacts").exists()
    assert not list(retained.glob("*.png"))
    assert case[1].sources[0].read_bytes() == frozen_bytes
    assert review.source_sha256 == [case[0]["cases"][0]["sha256"]]
    assert review.extra["sheets_viewed"] == [1]
    assert review.extra["inspection_proven"] is True
    assert review.extra["crop_calls"] == 1
    assert review.extra["crops"] == [{"sheet": 1, "rect": [10, 20, 300, 400]}]
    assert review.extra["context_errors"] == []
    assert evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory) == result
    assert len(provider["calls"]) == 1


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
@pytest.mark.parametrize("state", ["unwarned", "warned", "warned_incomplete"])
def test_surviving_original_attempt_dir_requires_warning_and_complete_retention(
    tmp_path: Path, case, provider, reviewer: str, state: str,
) -> None:
    identity = _identity(case, reviewer=reviewer)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    report = deepcopy(result["review"])
    invocation = report["extra"]["evidence"]["attempts"][0]
    original = Path(invocation["attempt_dir"])
    # Windows can refuse to remove a directory a lingering MCP server still holds.
    original.mkdir()
    (original / "stdout.txt").write_text("locked", encoding="utf-8")
    try:
        if state != "unwarned":
            invocation["retention_warning"] = "WinError 32: attempt dir in use; copied, original left behind"
        if state == "warned_incomplete":
            Path(invocation["stderr_file"]).unlink()
        _preserve_report(result, directory, report)
        if state == "warned":
            evaluation.validate_evidence(result, identity, "baseline", case[1], directory)
        else:
            with pytest.raises(ValueError):
                evaluation.validate_evidence(result, identity, "baseline", case[1], directory)
    finally:
        shutil.rmtree(original)


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
@pytest.mark.parametrize(
    "damage", ["missing", "foreign", "relative", "duplicate", "report_sources", "snapshot_content"],
)
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
    elif damage == "snapshot_content":
        Path(invocation["sources"][0]).write_bytes(b"tampered snapshot")
    else:
        report["sources"] = [str(Path(invocation["retained_dir"]) / "sheet-1.png")]
    _preserve_report(result, directory, report)
    with pytest.raises(
        ValueError, match="allowlist|inputs/settings|immutable source snapshot",
    ):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
@pytest.mark.parametrize("damage", [
    "attempt_relative", "attempt_is_retained", "retained_missing", "retained_relative",
    "retained_escape", "argv_missing", "argv_original", "argv_source", "argv_foreign",
    "argv_setting", "actual_replay", "cwd_moved", "codex_home", "attempt_in_repo",
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
    retained_argv = invocation["retained_argv"]
    if damage == "attempt_relative":
        invocation["attempt_dir"] = Path(invocation["attempt_dir"]).name
    elif damage == "attempt_is_retained":
        invocation["attempt_dir"] = invocation["retained_dir"]
    elif damage == "retained_missing":
        invocation["retained_dir"] = None
    elif damage == "retained_relative":
        invocation["retained_dir"] = Path(invocation["retained_dir"]).name
    elif damage == "retained_escape":
        invocation["retained_dir"] = str(tmp_path / "machrev-foreign")
    elif damage == "argv_missing":
        invocation["retained_argv"] = None
    elif damage == "argv_original":
        invocation["retained_argv"] = invocation["command"]
    elif damage == "argv_source":
        retained_argv.append(str(tmp_path / "foreign.png"))
    elif damage == "argv_foreign":
        invocation["retained_argv"] = [
            argument.replace(invocation["retained_dir"], str(tmp_path / "machrev-foreign"))
            for argument in retained_argv
        ]
    elif damage == "argv_setting":
        # Only attempt-dir files move: settings may not.
        flag = "-m" if reviewer == "codex" else "--model"
        retained_argv[retained_argv.index(flag) + 1] = invocation["retained_dir"]
    elif damage == "actual_replay":
        invocation["command"] = retained_argv
    elif damage == "cwd_moved":
        invocation["cwd"] = str(tmp_path / "elsewhere")
    elif damage == "codex_home":
        invocation["codex_home"] = None if reviewer == "codex" else str(tmp_path / "codex-home")
    else:
        # The reviewer's cwd must stay outside every repository.
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        inside = repo / Path(invocation["attempt_dir"]).name
        invocation["attempt_dir"] = invocation["cwd"] = str(inside)
    _preserve_report(result, directory, report)
    match = "git repository" if damage == "attempt_in_repo" else None
    with pytest.raises(ValueError, match=match):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
@pytest.mark.parametrize("damage", [
    "schema_missing", "schema_content", "materialized_sheet", "unexpected_directory",
    "artifact_subdir", "extra_artifact", "stream_escape", "stream_relative", "rollout_record",
])
def test_retained_attempt_dir_requires_exact_direct_file_inventory(
    tmp_path: Path, case, provider, reviewer: str, damage: str,
) -> None:
    identity = _identity(case, reviewer=reviewer)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    report = deepcopy(result["review"])
    invocation = report["extra"]["evidence"]["attempts"][0]
    retained = Path(invocation["retained_dir"])
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
    elif damage == "stream_relative":
        invocation["stdout_file"] = "stdout.txt"
    elif reviewer == "codex":
        invocation["rollout_file"] = None
    else:
        (retained / "rollout.jsonl").write_text("", encoding="utf-8")
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
    config_path = Path(invocation["retained_dir"]) / "mcp.json"
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
def test_codex_mcp_argv_cannot_be_redirected_even_with_matching_retained_argv(
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
    invocation["retained_argv"] = mr._retained_argv(
        command, Path(invocation["attempt_dir"]), Path(invocation["retained_dir"]),
    )
    _preserve_report(result, directory, report)
    with pytest.raises(ValueError, match="command permissions/settings"):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


@pytest.mark.parametrize("damage", ["missing", "tool_mode", "search_tool", "model", "extra_model"])
def test_codex_model_catalog_must_pin_direct_tools_for_the_reviewed_model(
    tmp_path: Path, case, provider, damage: str,
) -> None:
    identity = _identity(case)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    report = deepcopy(result["review"])
    invocation = report["extra"]["evidence"]["attempts"][0]
    catalog_path = Path(invocation["retained_dir"]) / "codex-models.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    model = catalog["models"][0]
    if damage == "missing":
        catalog_path.unlink()
        invocation["artifacts"].remove(str(catalog_path))
    else:
        if damage == "tool_mode":
            # Code mode routes tools through an exec cell the --json stream omits.
            model["tool_mode"] = "code"
        elif damage == "search_tool":
            model["supports_search_tool"] = True
        elif damage == "model":
            model["slug"] = "model-b"
        else:
            catalog["models"].append({**model, "slug": "model-b"})
        catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    _preserve_report(result, directory, report)
    with pytest.raises(ValueError, match="catalog"):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


def test_recorded_rollout_shapes_separate_direct_sheets_calls_from_injection_and_exec() -> None:
    image = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII="
    )
    prompt = "Review the drawing.\nReturn JSON."
    cwd = Path("C:/Users/pedro/AppData/Local/Temp/machinist-review-codex-neutral")
    prefix = [_rollout_meta("session-1", cwd)]
    calls = _rollout_sheet_call("view_sheet", {"sheet": 1}, "call_view", image)
    answer = [_rollout_message("assistant", "{}", ["unknown"])]

    clean = mr.codex_rollout_evidence(
        [*prefix, _rollout_message("user", prompt, ["user.text"]), *calls, *answer], prompt,
    )
    assert clean["context_errors"] == []
    inspection = mr.evaluate_sheet_evidence(clean["events"], reviewer="codex", sheet_count=1)
    assert inspection["tool_events"] == 0
    assert inspection["inspection_proven"] is True

    injected = mr.codex_rollout_evidence([
        *prefix, RECORDED_SKILLS_CONTEXT, RECORDED_AGENTS_CONTEXT,
        _rollout_message("user", prompt, ["user.text"]), *calls, *answer,
    ], prompt)
    assert injected["context_errors"]

    executed = mr.codex_rollout_evidence([
        *prefix, _rollout_message("user", prompt, ["user.text"]),
        *RECORDED_EXEC_CELL, *calls, *answer,
    ], prompt)
    assert mr.evaluate_sheet_evidence(
        executed["events"], reviewer="codex", sheet_count=1,
    )["tool_events"] >= 1


@pytest.mark.parametrize("damage", [
    "deleted", "unrecorded", "malformed", "exec_cell", "shell_call", "agents_md", "skills",
    "session", "workdir", "cli_version", "dropped_view", "appended_user_input",
])
def test_retained_codex_rollout_is_authoritative_and_fails_closed(
    tmp_path: Path, case, provider, damage: str,
) -> None:
    identity = _identity(case)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    report = deepcopy(result["review"])
    invocation = report["extra"]["evidence"]["attempts"][0]
    rollout = Path(invocation["rollout_file"])
    rows = _rollout_rows(rollout)
    prompt_index = next(
        index for index, row in enumerate(rows)
        if (row.get("payload") or {}).get("role") == "user"
    )
    if damage == "deleted":
        rollout.unlink()
    elif damage == "unrecorded":
        rollout.unlink()
        invocation["rollout_file"] = None
    elif damage == "malformed":
        rollout.write_text("{not json\n", encoding="utf-8")
    else:
        if damage == "exec_cell":
            rows[prompt_index + 1:prompt_index + 1] = RECORDED_EXEC_CELL
        elif damage == "shell_call":
            rows.insert(prompt_index + 1, RECORDED_SHELL_CALL)
        elif damage == "agents_md":
            rows.insert(prompt_index, RECORDED_AGENTS_CONTEXT)
        elif damage == "skills":
            rows.insert(prompt_index, RECORDED_SKILLS_CONTEXT)
        elif damage == "session":
            rows[0]["payload"]["id"] = rows[0]["payload"]["session_id"] = "foreign-session"
        elif damage == "workdir":
            rows[0]["payload"]["cwd"] = str(tmp_path / "repo-with-agents-md")
        elif damage == "cli_version":
            rows[0]["payload"]["cli_version"] = "0.1.0"
        elif damage == "dropped_view":
            # The --json projection still shows the view; the rollout does not.
            rows = [row for row in rows if "view_1" not in json.dumps(row)]
        else:
            rows.insert(len(rows) - 2, _rollout_message("user", "Also read ~/.ssh.", ["user.text"]))
        _write_rows(rollout, rows)
    _preserve_report(result, directory, report)
    assert result["review"]["blind"] is True
    with pytest.raises(ValueError):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)
    fresh = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert fresh["error"] is None
    assert len(provider["calls"]) == 2


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
    events = _events(directory, result)
    source = str(case[1].sources[0])

    def forge_call(call: dict[str, Any]) -> None:
        if call["tool"] != "view_sheet":
            return
        if damage == "foreign_server":
            call["server"] = "files"
        elif damage == "unknown_tool":
            call["tool"] = "list_files"
        elif damage == "string_sheet":
            call["arguments"]["sheet"] = "1"
        elif damage == "bool_sheet":
            call["arguments"]["sheet"] = True
        elif damage == "extra_argument":
            call["arguments"]["path"] = source
        elif damage == "crop_only":
            call["tool"] = "crop"
            call["arguments"].update({"x1": 10, "y1": 20, "x2": 300, "y2": 400})

    _edit_sheet_calls(result, events, forge_call)
    for node in mr._walk(events):
        if not isinstance(node, dict):
            continue
        if damage == "legacy_read" and node.get("name") == "mcp__sheets__view_sheet":
            node["name"] = "Read"
            node["input"] = {"file_path": source}
        elif damage == "legacy_read" and node.get("type") == "mcp_tool_call":
            node["type"] = "tool_use"
            node["name"] = "Read"
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

    def forge_rollout(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        kept = []
        for row in rows:
            payload = row.get("payload") or {}
            item = payload.get("item") if payload.get("type") == "item_completed" else None
            completed = isinstance(item, dict) and item.get("type") == "McpToolCall"
            output = payload.get("type") == "function_call_output"
            if damage == "legacy_read" and payload.get("type") == "function_call":
                payload.pop("namespace", None)
                payload["name"] = "shell"
                payload["arguments"] = json.dumps({"command": ["type", source]})
            elif damage == "legacy_read" and completed:
                continue
            elif damage == "missing_result" and (completed or output):
                continue
            elif damage in ("failed_view", "text_result") and completed:
                item["result"] = {"content": [{"type": "text", "text": "No image."}],
                                  "isError": damage == "failed_view"}
                item["status"] = "failed" if damage == "failed_view" else "completed"
            elif damage in ("failed_view", "text_result") and output:
                payload["output"] = [{"type": "input_text", "text": "No image."}]
            kept.append(row)
        return kept

    _edit_rollouts(result, forge_rollout)
    _preserve_events(result, directory, events)
    assert result["review"]["blind"] is True
    with pytest.raises(ValueError, match="sheet inspection|rollout"):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


def test_claude_successful_image_result_must_match_the_view_call_id(
    tmp_path: Path, case, provider,
) -> None:
    identity = _identity(case, reviewer="claude")
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    events = _events(directory, result)
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
    ("neutral_calls", None),
    ("neutral_calls", [{"tool": "list_mcp_resources", "arguments": {"server": "sheets"}}]),
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
def test_malformed_named_crops_count_with_raw_evidence_without_breaking_blindness(
    tmp_path: Path, case, provider, reviewer: str,
) -> None:
    provider["crops"] = [
        {"sheet": 1, "x1": 990.0, "y1": 20, "x2": 1300, "y2": 400},
        {"sheet": 2, "x1": 10, "y1": 20},
        {"sheet": 1, "x1": 10, "y1": 20, "x2": 300, "y2": 400},
    ]
    identity = _identity(case, reviewer=reviewer)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    review = evaluation.validate_evidence(result, identity, "baseline", case[1], directory)
    # The server rejects malformed crops; they leak nothing, so they cost budget
    # and are recorded verbatim, but cannot prove inspection or break blindness.
    assert review.blind is True
    assert review.tool_events == 0
    assert review.extra["crop_calls"] == 3
    assert review.extra["crops"] == [
        {"sheet": 1, "rect": [990.0, 20, 1300, 400]},
        {"sheet": 2, "rect": [10, 20, None, None]},
        {"sheet": 1, "rect": [10, 20, 300, 400]},
    ]
    assert type(review.extra["crops"][0]["rect"][0]) is float
    report = deepcopy(result["review"])
    report["extra"]["crops"][0]["rect"][0] = 990
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
    provider_run = mr._run_reviewer
    calls = 0

    def retrying_run(command, **kwargs):
        nonlocal calls
        calls += 1
        provider["crops"] = [{"sheet": 1, "x1": calls * 10, "y1": 20, "x2": 300, "y2": 400}]
        process = provider_run(command, **kwargs)
        if calls == 1:
            process.returncode = 17
        return process

    monkeypatch.setattr(mr, "_run_reviewer", retrying_run)
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
@pytest.mark.parametrize("damage", ["unauthorized_retry", "missing_final_view", "failed_attempt_exec"])
def test_final_attempt_cannot_launder_failed_attempt_tools_or_earlier_views(
    tmp_path: Path, case, provider, monkeypatch: pytest.MonkeyPatch,
    reviewer: str, damage: str,
) -> None:
    if reviewer == "claude" and damage == "failed_attempt_exec":
        pytest.skip("Codex rollout evidence only")
    identity = _identity(case, reviewer=reviewer)
    identity["retries"] = 1
    directory = tmp_path / "run"
    provider_run = mr._run_reviewer
    calls = 0

    def retrying_run(command, **kwargs):
        nonlocal calls
        calls += 1
        provider["mode"] = (
            "unblind" if damage == "unauthorized_retry" and calls == 1
            else "exec_cell" if damage == "failed_attempt_exec" and calls == 1
            else "missing_view" if damage == "missing_final_view" and calls == 2
            else "valid"
        )
        process = provider_run(command, **kwargs)
        if calls == 1:
            process.returncode = 17
        return process

    monkeypatch.setattr(mr, "_run_reviewer", retrying_run)
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is not None
    report = deepcopy(result["review"])
    report["blind"] = True
    report["tool_events"] = 0
    report["extra"]["sheets_viewed"] = [1]
    report["extra"]["inspection_proven"] = True
    report["extra"]["context_errors"] = []
    result["error"] = None
    _preserve_report(result, directory, report)
    with pytest.raises(ValueError, match="sheet inspection|rollout"):
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
    events = _events(directory, result)

    def first_sheet_only(call: dict[str, Any]) -> None:
        if call["tool"] == "view_sheet":
            call["arguments"]["sheet"] = 1

    _edit_sheet_calls(result, events, first_sheet_only)
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
    assert failed["retained_argv"] is None
    assert failed["stdout_file"] is None
    assert failed["stderr_file"] is None
    assert failed["session_id"] is None
    assert failed["rollout_file"] is None
    assert not any(Path(path).name == "verdict.json" for path in failed["artifacts"])
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
    output = Path(invocation["retained_dir"]) / "verdict.json"
    output.unlink()
    invocation["artifacts"].remove(str(output))
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
        (Path(invocation["retained_dir"]) / "verdict.json").write_text(json.dumps(forged), encoding="utf-8")
    else:
        events = _events(directory, result)
        for node in mr._walk(events):
            if isinstance(node, dict) and node.get("type") == "agent_message":
                node["text"] = json.dumps(forged)
        _preserve_events(result, directory, events)
    with pytest.raises(ValueError, match="Codex.*verdict"):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
@pytest.mark.parametrize("damage", ["attempt_dir", "session", "outcome", "attempt_index"])
def test_retry_invocations_cannot_reuse_or_relabel_provenance(
    tmp_path: Path, case, provider, monkeypatch: pytest.MonkeyPatch,
    reviewer: str, damage: str,
) -> None:
    identity = _identity(case, reviewer=reviewer)
    identity["retries"] = 1
    provider_run = mr._run_reviewer
    calls = 0

    def retrying_run(command, **kwargs):
        nonlocal calls
        calls += 1
        process = provider_run(command, **kwargs)
        if calls == 1:
            process.returncode = 17
        return process

    monkeypatch.setattr(mr, "_run_reviewer", retrying_run)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    report = deepcopy(result["review"])
    failed, succeeded = report["extra"]["evidence"]["attempts"]
    if damage == "attempt_dir":
        succeeded["attempt_dir"] = failed["attempt_dir"]
        succeeded["retained_dir"] = failed["retained_dir"]
        if reviewer == "claude":
            succeeded["cwd"] = failed["cwd"]
    elif damage == "session":
        original_session = succeeded["session_id"]
        succeeded["session_id"] = failed["session_id"]
        succeeded["resume_command"] = (
            mr._transport_resume(succeeded["transport_provenance"], failed["session_id"])
            if reviewer == "claude" else mr._codex_resume_command(failed["session_id"])
        )
        if reviewer == "claude":
            for field in ("command", "retained_argv"):
                succeeded[field] = [
                    argument.replace(original_session, failed["session_id"])
                    for argument in succeeded[field]
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


RESOURCE_FREE_CATALOG = {"servers": ["sheets"], "resources": 0, "resource_templates": 0}
SHIP_VERDICT = {
    "verdict": "SHIP", "summary": "Every feature is located and toleranced.",
    "blockers": [], "over_specification": [], "clarity": [], "minor": [],
}
NEUTRAL_REQUESTS = {
    "list_scoped": ("list_mcp_resources", {"server": "sheets"}),
    "list_all": ("list_mcp_resources", {}),
    "templates": ("list_mcp_resource_templates", {"server": "sheets"}),
    "read_missing": ("read_mcp_resource", {"server": "sheets", "uri": "sheet://1"}),
}


@pytest.mark.parametrize("request_name", sorted(NEUTRAL_REQUESTS))
def test_codex_neutral_resource_request_passes_only_with_every_sheet_viewed(
    tmp_path: Path, case, provider, request_name: str,
) -> None:
    tool, arguments = NEUTRAL_REQUESTS[request_name]
    provider["neutral"] = [(tool, arguments)]
    provider["verdict"] = deepcopy(SHIP_VERDICT)
    identity = _identity(case)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    review = evaluation.validate_evidence(result, identity, "baseline", case[1], directory)
    assert review.blind is True and review.tool_events == 0 and review.passed is True
    assert review.extra["evidence"]["mcp_catalog"] == RESOURCE_FREE_CATALOG
    assert review.extra["neutral_calls"] == [{"tool": tool, "arguments": arguments}]
    # The request is recorded, never counted as a view or crop.
    assert review.extra["sheets_viewed"] == [1]
    assert review.extra["crop_calls"] == 0
    rollout = _rollout_rows(Path(review.extra["evidence"]["attempts"][0]["rollout_file"]))
    assert [
        row["payload"]["item"]["tool"] for row in rollout
        if isinstance(row["payload"].get("item"), dict)
        and row["payload"]["item"].get("server") == "codex"
    ] == [tool]
    assert evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory) == result
    assert len(provider["calls"]) == 1

    provider["mode"] = "missing_view"
    unviewed_dir = tmp_path / "unviewed"
    unviewed = evaluation.run_case(identity, "baseline", case[1], "Rubric A", unviewed_dir)
    # A completed review without every view is never blind evidence.
    assert unviewed["error"] is not None and unviewed["review"]["blind"] is False
    assert unviewed["review"]["tool_events"] == 0
    assert unviewed["review"]["passed"] is False
    assert unviewed["review"]["extra"]["neutral_calls"] == [{"tool": tool, "arguments": arguments}]
    with pytest.raises(ValueError):
        evaluation.validate_evidence(unviewed, identity, "baseline", case[1], unviewed_dir)


@pytest.mark.parametrize(("reviewer", "tool", "arguments"), [
    ("claude", "list_mcp_resources", {"server": "sheets"}),
    ("codex", "read_mcp_resource", {"server": "files", "uri": "file:///C:/Users/pedro/.ssh/id_rsa"}),
    ("codex", "list_mcp_resources", {"server": "files"}),
    ("codex", "list_mcp_resource_templates", {"server": "codex_apps"}),
    ("codex", "get_goal", {}),
    ("codex", "exec", {"code": "text(ALL_TOOLS.map(t => t.name))"}),
])
def test_resource_neutrality_is_codex_only_and_scoped_to_sheets(
    tmp_path: Path, case, provider, reviewer: str, tool: str, arguments: dict[str, Any],
) -> None:
    provider["neutral"] = [(tool, arguments)]
    provider["verdict"] = deepcopy(SHIP_VERDICT)
    identity = _identity(case, reviewer=reviewer)
    directory = tmp_path / "run"
    forbidden = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert forbidden["error"] is not None
    assert forbidden["review"]["passed"] is False
    assert forbidden["review"]["blind"] is False
    assert evaluation.aggregate(identity, [forbidden])["results"][0]["outcome"] == "invalid"
    with pytest.raises(ValueError):
        evaluation.validate_evidence(forbidden, identity, "baseline", case[1], directory)
    provider["neutral"] = []
    fresh = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert fresh["error"] is None
    assert fresh["review"]["extra"]["neutral_calls"] == []
    assert len(provider["calls"]) == 2


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
@pytest.mark.parametrize(("damage", "change"), [
    ("missing", None),
    ("alternate_server", {"servers": ["files"]}),
    ("extra_server", {"servers": ["sheets", "files"]}),
    ("resources", {"resources": 1}),
    ("templates", {"resource_templates": 1}),
    ("bool_count", {"resources": False}),
    ("current_server", {"servers": ["files"]}),
    ("current_resources", {"resources": 1}),
    ("current_templates", {"resource_templates": 2}),
    ("current_bool", {"resource_templates": False}),
])
def test_mcp_catalog_must_be_the_current_resource_free_sole_sheets_server(
    tmp_path: Path, case, provider, monkeypatch: pytest.MonkeyPatch,
    reviewer: str, damage: str, change: dict[str, Any] | None,
) -> None:
    if reviewer == "codex":
        provider["neutral"] = [NEUTRAL_REQUESTS["list_scoped"]]
    identity = _identity(case, reviewer=reviewer)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    report = deepcopy(result["review"])
    evidence = report["extra"]["evidence"]
    assert evidence["mcp_catalog"] == RESOURCE_FREE_CATALOG
    if change is None:
        del evidence["mcp_catalog"]
    else:
        evidence["mcp_catalog"] = {**RESOURCE_FREE_CATALOG, **change}
        if damage.startswith("current_"):
            # The SDK server itself declares a different catalog; the recorded
            # catalog agrees with it but no longer proves resource neutrality.
            monkeypatch.setattr(mr, "_sheet_resource_manifest", lambda sources: {
                **RESOURCE_FREE_CATALOG, **change,
            })
    _preserve_report(result, directory, report)
    with pytest.raises(ValueError, match="MCP catalog"):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


@pytest.mark.parametrize("damage", [
    "dropped", "duplicated", "foreign_server", "unscoped", "renamed", "raw_string_arguments",
    "extra_key", "id_only",
])
def test_recorded_neutral_calls_must_match_authoritative_rollout(
    tmp_path: Path, case, provider, damage: str,
) -> None:
    provider["neutral"] = [NEUTRAL_REQUESTS["list_scoped"]]
    identity = _identity(case)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    report = deepcopy(result["review"])
    calls = report["extra"]["neutral_calls"]
    assert calls == [{"tool": "list_mcp_resources", "arguments": {"server": "sheets"}}]
    if damage == "dropped":
        calls.clear()
    elif damage == "duplicated":
        calls.append(deepcopy(calls[0]))
    elif damage == "foreign_server":
        calls[0]["arguments"]["server"] = "files"
    elif damage == "unscoped":
        calls[0]["arguments"] = {}
    elif damage == "renamed":
        calls[0]["tool"] = "list_mcp_resource_templates"
    elif damage == "raw_string_arguments":
        calls[0]["arguments"] = json.dumps(calls[0]["arguments"])
    elif damage == "extra_key":
        calls[0]["id"] = "resource_0"
    else:
        calls[0] = {"id": "resource_0"}
    _preserve_report(result, directory, report)
    with pytest.raises(ValueError, match="recorded sheet inspection"):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


@pytest.mark.parametrize("damage", [
    "foreign_server", "listed_resource", "listed_template", "native_server", "namespaced",
    "projection_server",
])
def test_neutral_resource_rollout_tampering_fails_closed(
    tmp_path: Path, case, provider, damage: str,
) -> None:
    provider["neutral"] = [NEUTRAL_REQUESTS["list_scoped"]]
    identity = _identity(case)
    directory = tmp_path / "run"
    result = evaluation.run_case(identity, "baseline", case[1], "Rubric A", directory)
    assert result["error"] is None
    events = _events(directory, result)
    listed = {
        "listed_resource": {"server": "sheets", "resources": [
            {"server": "sheets", "uri": "file:///C:/drawings/answer.png", "name": "answer"},
        ]},
        "listed_template": {"server": "sheets", "resourceTemplates": [
            {"server": "sheets", "uriTemplate": "file:///{path}", "name": "files"},
        ]},
    }

    def forge(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for row in rows:
            payload = row.get("payload") or {}
            item = payload.get("item") if payload.get("type") == "item_completed" else None
            native = isinstance(item, dict) and item.get("id") == "resource_0"
            declared = payload.get("type") == "function_call" and payload.get("call_id") == "resource_0"
            output = payload.get("type") == "function_call_output" and payload.get("call_id") == "resource_0"
            if damage == "foreign_server" and declared:
                payload["arguments"] = json.dumps({"server": "files"})
            elif damage == "foreign_server" and native:
                item["arguments"] = {"server": "files"}
            elif damage in listed and native:
                item["result"]["content"][0]["text"] = json.dumps(listed[damage])
            elif damage in listed and output:
                payload["output"] = json.dumps(listed[damage])
            elif damage == "native_server" and native:
                item["server"] = "files"
            elif damage == "namespaced" and declared:
                payload["namespace"] = "mcp__files"
        return rows

    if damage == "projection_server":
        for row in events:
            item = row["event"].get("item")
            if isinstance(item, dict) and item.get("id") == "resource_0":
                item["server"] = "files"
        _preserve_events(result, directory, events)
    else:
        _edit_rollouts(result, forge)
    assert result["review"]["blind"] is True
    with pytest.raises(ValueError):
        evaluation.validate_evidence(result, identity, "baseline", case[1], directory)


def test_codex_argv_mcp_servers_bind_the_catalog(tmp_path: Path) -> None:
    command = mr.build_codex_command(
        workdir=tmp_path, sources=[tmp_path / "sheet.png"], schema=tmp_path / "schema.json",
        output=tmp_path / "verdict.json", model="model-a", effort="low",
    )
    assert evaluation._codex_mcp_servers(command) == set(RESOURCE_FREE_CATALOG["servers"])
    assert evaluation._codex_mcp_servers(
        [*command, "-c", 'mcp_servers.files.command="files-server"']
    ) == {"sheets", "files"}
    # A whole-table override names no server and can never match the catalog.
    assert evaluation._codex_mcp_servers([*command, "-c", "mcp_servers={}"]) == {"sheets", ""}
