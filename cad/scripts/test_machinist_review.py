"""Offline contracts for the blind machinist review runner and its sheet server."""

from __future__ import annotations

import asyncio
import base64
import contextvars
import io
import json
import os
import re
import shutil
import struct
import sys
import threading
import tomllib
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from PIL import Image, ImageDraw

import machinist_review as mr
import machinist_review_config as review_config
import machinist_review_sheets_mcp as sheets

SHEET_TOOLS = {"mcp__sheets__view_sheet", "mcp__sheets__crop"}


def _clean_verdict(verdict: str = "SHIP") -> dict[str, Any]:
    return {
        "verdict": verdict,
        "summary": "ready",
        "blockers": [],
        "over_specification": [],
        "clarity": [],
        "minor": [],
    }


# --- source fixtures -------------------------------------------------------


def _draw(
    size: tuple[int, int], squares: Sequence[tuple[int, int, int, int]], mode: str
) -> Image.Image:
    image = Image.new(mode, size, "white")
    draw = ImageDraw.Draw(image)
    for left, top, right, bottom in squares:
        # Half-open boxes: (600, 200, 700, 300) is exactly 100 x 100 pixels.
        draw.rectangle((left, top, right - 1, bottom - 1), fill="black")
    return image


def _pdf_source(
    path: Path,
    pages: Sequence[tuple[int, int]],
    squares: Sequence[tuple[int, int, int, int]] = (),
) -> Path:
    """A PDF whose pages are ``pages`` points; 72 dpi makes 1 px == 1 pt."""
    images = [_draw(size, squares, "L") for size in pages]
    images[0].save(
        path, "PDF", resolution=72.0, save_all=True, append_images=images[1:]
    )
    return path


def _png_source(
    path: Path,
    size: tuple[int, int] = (10, 10),
    squares: Sequence[tuple[int, int, int, int]] = (),
    mode: str = "RGB",
    **save: Any,
) -> Path:
    _draw(size, squares, mode).save(path, format="PNG", **save)
    return path


def _image(png: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(png))
    image.load()
    return image


def _text_pdf(path: Path, lines: Sequence[tuple[float, float, str]]) -> Path:
    """A one-page PDF with real Helvetica text at the given page coordinates."""
    stream = "\n".join(
        f"BT /F1 10 Tf {x} {y} Td ({text}) Tj ET" for x, y, text in lines
    ).encode("ascii", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    startxref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{startxref}\n%%EOF"
    ).encode()
    path.write_bytes(bytes(out))
    return path


def _png_chunk_types(png: bytes) -> list[str]:
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    types: list[str] = []
    offset = 8
    while offset < len(png):
        (length,) = struct.unpack(">I", png[offset : offset + 4])
        types.append(png[offset + 4 : offset + 8].decode("ascii"))
        offset += 12 + length
    return types


def _dark_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    return image.point(lambda value: 255 if value < 128 else 0).getbbox()


def _call(server: Any, name: str, arguments: dict[str, Any]) -> list[Any]:
    result = asyncio.run(server.call_tool(name, arguments))
    if isinstance(result, tuple):
        result = result[0]
    return list(getattr(result, "content", result))


def _image_and_text(content: list[Any]) -> tuple[bytes, str]:
    images = [block for block in content if block.type == "image"]
    texts = [block for block in content if block.type == "text"]
    assert len(images) == 1 and len(texts) == 1
    assert images[0].mimeType == "image/png"
    return base64.b64decode(images[0].data), texts[0].text


# --- event fixtures (shapes captured from claude 2.1.286 / codex 0.159.1) ----


def _claude_tool_use(name: str, tool_input: Any, tool_id: str) -> dict[str, Any]:
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_id,
                    "name": name,
                    "input": tool_input,
                    "caller": {"type": "direct"},
                }
            ]
        },
    }


def _claude_tool_result(tool_id: str, *, is_error: bool = False) -> dict[str, Any]:
    block: dict[str, Any] = {"tool_use_id": tool_id, "type": "tool_result"}
    if is_error:
        block["content"] = [{"type": "text", "text": "Error executing tool"}]
        block["is_error"] = True
    else:
        block["content"] = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": ""},
            },
            {"type": "text", "text": "sheet 1 of 1, 1976×1280 px"},
        ]
    return {"type": "user", "message": {"role": "user", "content": [block]}}


def _claude_call(
    tool: str, tool_input: Any, tool_id: str, *, is_error: bool = False
) -> list[dict[str, Any]]:
    name = tool if tool.startswith("mcp__") or tool[0].isupper() else f"mcp__sheets__{tool}"
    return [
        _claude_tool_use(name, tool_input, tool_id),
        _claude_tool_result(tool_id, is_error=is_error),
    ]


def _codex_call(
    tool: str,
    arguments: Any,
    item_id: str,
    *,
    server: str = "sheets",
    status: str = "completed",
) -> list[dict[str, Any]]:
    item = {
        "id": item_id,
        "type": "mcp_tool_call",
        "server": server,
        "tool": tool,
        "arguments": arguments,
    }
    started = {
        "type": "item.started",
        "item": {**item, "result": None, "error": None, "status": "in_progress"},
    }
    if status == "in_progress":
        return [started]
    if status == "completed":
        outcome = {
            "result": {
                "content": [{"type": "image", "data": "", "mimeType": "image/png"}],
                "structured_content": None,
            },
            "error": None,
        }
    else:
        outcome = {"result": None, "error": {"message": "tool failed"}}
    return [started, {"type": "item.completed", "item": {**item, **outcome, "status": status}}]


def _call_events(
    reviewer: str, tool: str, arguments: Any, call_id: str, *, ok: bool = True
) -> list[dict[str, Any]]:
    if reviewer == "claude":
        return _claude_call(tool, arguments, call_id, is_error=not ok)
    return _codex_call(tool, arguments, call_id, status="completed" if ok else "failed")


def _views(reviewer: str, sheets_to_view: Sequence[int]) -> list[dict[str, Any]]:
    return [
        event
        for sheet in sheets_to_view
        for event in _call_events(reviewer, "view_sheet", {"sheet": sheet}, f"view_{sheet}")
    ]


def _claude_provider_event() -> dict[str, Any]:
    return {
        "type": "assistant",
        "message": {
            "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": "first response"}],
            "usage": {
                "input_tokens": 0, "cache_creation_input_tokens": 27143,
                "cache_read_input_tokens": 0, "output_tokens": 0,
            },
        },
    }


def _claude_nonresponses() -> list[Any]:
    zero = _claude_provider_event()
    zero["message"]["usage"]["cache_creation_input_tokens"] = 0
    synthetic = _claude_provider_event()
    synthetic["message"]["model"] = "<synthetic>"
    api_error = _claude_provider_event()
    api_error["isApiErrorMessage"] = True
    api_error["error"] = "rate_limit"
    malformed = _claude_provider_event()
    malformed["message"]["usage"]["input_tokens"] = "12"
    boolean = _claude_provider_event()
    boolean["message"]["usage"]["cache_creation_input_tokens"] = True
    reported_error = _claude_provider_event()
    reported_error["is_error"] = True
    return [
        None, [], {"type": "assistant", "message": None},
        {"type": "assistant", "message": {"model": "claude-opus-5-5"}},
        {"type": "system", "subtype": "init"},
        {"type": "control_response", "response": {"subtype": "success"}},
        {"type": "result", "subtype": "success", "usage": {"input_tokens": 12}},
        zero, synthetic, api_error, reported_error, malformed, boolean,
    ]


def _claude_stdout(sheet_count: int, verdict: dict[str, Any]) -> str:
    events = [
        *_views("claude", range(1, sheet_count + 1)),
        {"type": "result", "structured_output": verdict},
    ]
    return "\n".join(json.dumps(event) for event in events)


def _codex_events(sheet_count: int, thread_id: str | None = None) -> list[dict[str, Any]]:
    started = [{"type": "thread.started", "thread_id": thread_id}] if thread_id else []
    return [
        *started,
        {"type": "turn.started"},
        *_views("codex", range(1, sheet_count + 1)),
        {"type": "turn.completed"},
    ]


def _codex_stdout(sheet_count: int, thread_id: str | None = None) -> str:
    return "\n".join(json.dumps(event) for event in _codex_events(sheet_count, thread_id))


def _flag(command: list[str], flag: str) -> str:
    assert command.count(flag) == 1, flag
    return command[command.index(flag) + 1]


def _codex_overrides(command: list[str]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for index, value in enumerate(command):
        if value != "-c":
            continue
        key, _, raw = command[index + 1].partition("=")
        try:
            overrides[key] = tomllib.loads(f"value = {raw}")["value"]
        except tomllib.TOMLDecodeError:
            overrides[key] = raw
    return overrides


# --- Codex rollout fixtures (shapes recorded from codex 0.159.1 rollouts) ------
#
# The --json stream is a projection: code-mode exec cells and injected context
# never appear in it. The rollout under CODEX_HOME is the authoritative record.

_FIRST_REQUEST_USAGE = {
    "input_tokens": 22232,
    "cached_input_tokens": 21248,
    "cache_write_input_tokens": 0,
    "output_tokens": 66,
    "reasoning_output_tokens": 0,
    "total_tokens": 22298,
}
_LATER_REQUEST_USAGE = {**_FIRST_REQUEST_USAGE, "input_tokens": 25700, "cached_input_tokens": 22272}
_AUTH_SENTINEL = "auth-sentinel-must-never-reach-reports"


def _rollout_row(kind: str, payload: Any) -> dict[str, Any]:
    return {"timestamp": "2026-10-12T17:28:27.735Z", "type": kind, "payload": payload}


def _rollout_message(role: str, text: str) -> dict[str, Any]:
    part = "output_text" if role == "assistant" else "input_text"
    return _rollout_row(
        "response_item",
        {
            "type": "message",
            "id": f"msg_{role}_{len(text)}",
            "role": role,
            "content": [{"type": part, "text": text}],
        },
    )


# Recorded before the rubric when --ignore-user-config still loaded the
# operator's home (rollout 01a13102, lines 3-5); identities redacted.
_SKILLS_CONTEXT = _rollout_message(
    "developer",
    "<skills_instructions>\n## Skills\nA skill is a set of local instructions to "
    "follow that is stored in a `SKILL.md` file.\n### Skill roots\n"
    "- `r0` = `C:/Users/operator/.agents/skills`\n</skills_instructions>",
)
_AGENTS_MD_TEXT = "## User info\nFull name: Operator\n\n## Git workflow\n- Push early."
_AGENTS_CONTEXT = _rollout_message(
    "user", f"# AGENTS.md instructions\n\n<INSTRUCTIONS>\n{_AGENTS_MD_TEXT}\n</INSTRUCTIONS>"
)


def _rollout_call(
    thread_id: str, tool: str, arguments: Any, call_id: str, *, ok: bool = True
) -> list[dict[str, Any]]:
    """Direct tool mode: function_call, the MCP item, then the model-visible output."""
    if ok:
        result = {
            "content": [{"type": "image", "data": "", "mimeType": "image/png"}],
            "isError": False,
        }
        output = [
            {"type": "input_text", "text": "Wall time: 0.0115 seconds\nOutput:"},
            {"type": "input_image", "image_url": "data:image/png;base64,", "detail": "high"},
        ]
    else:
        # Failure output is not recorded; it mirrors the success layout, with
        # the server's own error text in place of the image.
        result = {
            "content": [{"type": "text", "text": "Error executing tool crop"}],
            "isError": True,
        }
        output = [
            {"type": "input_text", "text": "Wall time: 0.0021 seconds\nOutput:"},
            {"type": "input_text", "text": "Error executing tool crop"},
        ]
    return [
        _rollout_row(
            "response_item",
            {
                "type": "function_call",
                "id": f"fc_{call_id}",
                "name": tool,
                "namespace": "mcp__sheets",
                "arguments": json.dumps(arguments, separators=(",", ":")),
                "call_id": call_id,
            },
        ),
        _rollout_row(
            "event_msg",
            {
                "type": "item_completed",
                "thread_id": thread_id,
                "turn_id": "turn_1",
                "item": {
                    "type": "McpToolCall",
                    "id": call_id,
                    "server": "sheets",
                    "tool": tool,
                    "arguments": arguments,
                    "status": "completed",
                    "result": result,
                },
            },
        ),
        _rollout_row(
            "response_item",
            {"type": "function_call_output", "id": f"fco_{call_id}", "call_id": call_id, "output": output},
        ),
    ]


def _rollout_exec_cell(call_id: str, source: str) -> list[dict[str, Any]]:
    """Code mode (rollout 01a13102, lines 11/13): absent from the --json stream."""
    return [
        _rollout_row(
            "response_item",
            {
                "type": "custom_tool_call",
                "id": f"ctc_{call_id}",
                "status": "completed",
                "call_id": call_id,
                "name": "exec",
                "input": source,
            },
        ),
        _rollout_row(
            "response_item",
            {
                "type": "custom_tool_call_output",
                "id": f"ctco_{call_id}",
                "call_id": call_id,
                "output": [{"type": "input_text", "text": "Script completed\nWall time 0.0 seconds\nOutput:\n"}],
            },
        ),
    ]


def _rollout_usage(thread_id: str, usage: dict[str, Any]) -> dict[str, Any]:
    return _rollout_row(
        "token_usage_record",
        {
            "thread_id": thread_id,
            "session_id": thread_id,
            "turn_id": "turn_1",
            "response_id": f"resp_{usage['input_tokens']}",
            "usage": usage,
            "turn_token_usage": usage,
        },
    )


def _codex_rollout(
    prompt: str,
    *,
    thread_id: str,
    cwd: str,
    views: Sequence[int] = (1,),
    crops: Sequence[dict[str, Any]] = (),
    before: Sequence[dict[str, Any]] = (),
    after: Sequence[dict[str, Any]] = (),
    agents_md: dict[str, Any] | None = None,
    skills: bool = False,
    newline: str = "\r\n",
    verdict: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """A complete direct-mode rollout; ``newline`` mimics Windows text-mode stdin."""
    recorded_prompt = prompt.replace("\n", newline)
    rows = [
        _rollout_row(
            "session_meta",
            {
                "session_id": thread_id,
                "id": thread_id,
                "cwd": cwd,
                "originator": "codex_exec",
                "cli_version": "0.159.1",
                "source": "exec",
            },
        ),
        _rollout_row("event_msg", {"type": "task_started", "turn_id": "turn_1"}),
        _rollout_row(
            "world_state",
            {
                "full": True,
                "state": {
                    "agents_md": agents_md or {},
                    "apps_instructions": False,
                    "host_skills": {"includeInstructions": skills},
                    "managed_developer_instructions": {},
                    "plugins_instructions": False,
                    "skills": {"includeInstructions": skills},
                },
            },
        ),
        _rollout_row(
            "turn_context",
            {
                "turn_id": "turn_1",
                "cwd": cwd,
                "approval_policy": "never",
                "sandbox_policy": {"type": "read-only"},
            },
        ),
        *before,
        _rollout_message("user", recorded_prompt),
        _rollout_row(
            "event_msg",
            {
                "type": "item_completed",
                "thread_id": thread_id,
                "turn_id": "turn_1",
                "item": {
                    "type": "UserMessage",
                    "id": "user_1",
                    "content": [{"type": "text", "text": recorded_prompt, "text_elements": []}],
                },
            },
        ),
    ]
    calls = [
        *(
            _rollout_call(thread_id, "view_sheet", {"sheet": sheet}, f"call_view_{sheet}")
            for sheet in views
        ),
        *(
            _rollout_call(thread_id, "crop", crop, f"call_crop_{index}")
            for index, crop in enumerate(crops, start=1)
        ),
    ]
    usage = [_rollout_usage(thread_id, _FIRST_REQUEST_USAGE)]
    for index, call in enumerate(calls):
        rows += call
        rows += usage if index == 0 else [_rollout_usage(thread_id, _LATER_REQUEST_USAGE)]
    if not calls:
        rows += usage
    rows += after
    text = json.dumps(verdict or _clean_verdict())
    rows += [
        _rollout_message("assistant", text),
        _rollout_row("event_msg", {"type": "task_complete", "turn_id": "turn_1", "last_agent_message": text}),
    ]
    return rows


def _write_rollout(
    codex_home: Path, thread_id: str, rows: Sequence[dict[str, Any]], *, archived: bool = False
) -> Path:
    folder = codex_home / ("archived_sessions" if archived else "sessions/2026/10/12")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"rollout-2026-10-12T17-28-24-{thread_id}.jsonl"
    path.write_text("".join(f"{json.dumps(row)}\n" for row in rows), encoding="utf-8")
    return path


def _codex_reply(
    command: list[str],
    kwargs: dict[str, Any],
    *,
    sheet_count: int,
    verdict: dict[str, Any] | None = None,
    thread_id: str | None = None,
    rollout: bool = True,
    rollout_views: Sequence[int] | None = None,
    before: Sequence[dict[str, Any]] = (),
    after: Sequence[dict[str, Any]] = (),
    agents_md: dict[str, Any] | None = None,
    skills: bool = False,
) -> Any:
    """Act as ``codex exec``: verdict file, --json stdout, rollout in CODEX_HOME."""
    thread_id = thread_id or str(uuid.uuid4())
    verdict = verdict or _clean_verdict()
    Path(_flag(command, "-o")).write_text(json.dumps(verdict), encoding="utf-8")
    if rollout:
        rows = _codex_rollout(
            kwargs["input"],
            thread_id=thread_id,
            cwd=str(kwargs["cwd"]),
            views=range(1, sheet_count + 1) if rollout_views is None else rollout_views,
            before=before,
            after=after,
            agents_md=agents_md,
            skills=skills,
            verdict=verdict,
        )
        # The rollout lands wherever the harness pointed the CLI's home.
        _write_rollout(Path(kwargs["env"]["CODEX_HOME"]), thread_id, rows)
    return mr.subprocess.CompletedProcess(
        command, 0, stdout=_codex_stdout(sheet_count, thread_id), stderr=""
    )


_REAL_CODEX_HOME = mr.CODEX_HOME
_REAL_PREPARE_CODEX_ENVIRONMENT = mr.prepare_codex_environment
_REAL_RELINK_CODEX_AUTH = mr.relink_codex_auth


@pytest.fixture(autouse=True)
def isolated_codex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Keep tests off the real isolated home; never run ``codex debug models``."""
    state = SimpleNamespace(home=tmp_path / "codex-isolated-home", prepared=[], relinked=[])
    monkeypatch.setattr(mr, "CODEX_HOME", state.home)
    # Never resolve the operator's own login, even if a test reaches the real relink.
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-main-home"))
    monkeypatch.setattr(mr, "relink_codex_auth", lambda home: state.relinked.append(Path(home)))

    def fake_prepare(
        *, codex_home: Path, attempt_dir: Path, model: str, codex: str
    ) -> dict[str, str]:
        codex_home = Path(codex_home)
        codex_home.mkdir(parents=True, exist_ok=True)
        (codex_home / "auth.json").write_text(
            json.dumps({"tokens": {"access_token": _AUTH_SENTINEL}}), encoding="utf-8"
        )
        catalog = {"models": [{"slug": model, "tool_mode": "direct", "supports_search_tool": False}]}
        (Path(attempt_dir) / "codex-models.json").write_text(json.dumps(catalog), encoding="utf-8")
        state.prepared.append({"codex_home": codex_home, "attempt_dir": Path(attempt_dir), "codex": codex})
        return {**os.environ, "CODEX_HOME": str(codex_home)}

    monkeypatch.setattr(mr, "prepare_codex_environment", fake_prepare)
    return state


# --- schema, commands and prompt ---------------------------------------------


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


@pytest.fixture
def sdk_transport(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Exercise actual SDK option/event types with a deterministic client."""
    import claude_agent_sdk as sdk
    import machinist_review_credentials as credentials
    import machinist_review_transport as transport
    keys = tmp_path / "keys.json"
    keys.write_text(json.dumps({"keys": [
        {"id": f"account-{n}", "apiKey": f"secret-canary-{n}"} for n in range(3)
    ]}))
    keys.chmod(0o600)
    credentials._windows_acl(keys, secure=True)
    monkeypatch.setenv("CODJIFLO_ANTHROPIC_KEYS_FILE", str(keys))
    monkeypatch.setenv("CODJIFLO_CLAUDE_STATE_FILE", str(tmp_path / "private" / "state.json"))
    state = SimpleNamespace(status="connected", queries=[], clients=[], quota=False, fail=False, delay=0)
    state.verdict = _clean_verdict()
    state.transient_failure = False
    state.api_retry = False
    state.controlled = False
    state.leader_timeout = False
    state.before_response = threading.Event()
    state.release_response = threading.Event()
    state.release_finish = threading.Event()
    state.followers_started = threading.Event()

    class Client:
        def __init__(self, *, options):
            self.options = options
            self.disconnected = False
            self.index = len(state.clients)
            if state.leader_timeout and self.index:
                assert state.clients[0].disconnected
            state.clients.append(self)
            if self.index == 2:
                state.followers_started.set()

        async def connect(self):
            if state.leader_timeout and self.index == 0:
                await asyncio.sleep(10)
            if state.delay:
                await asyncio.sleep(state.delay)

        async def get_mcp_status(self):
            return {"mcpServers": [{"name": "sheets", "status": state.status,
                                    "tools": [{"name": "view_sheet"}, {"name": "crop"}]}]}

        async def query(self, prompt):
            state.queries.append(prompt)
            if state.fail:
                # SDK callbacks are complete lines, already stripped of newlines.
                self.options.stderr("first diagnostic secret-canary-0")
                self.options.stderr("second diagnostic")
                raise RuntimeError("failure secret-canary-0")

        async def receive_response(self):
            if state.controlled and self.index == 0:
                state.before_response.set()
                while not state.release_response.is_set():
                    await asyncio.sleep(0.005)
            if state.transient_failure:
                yield sdk.AssistantMessage(content=[sdk.TextBlock(text="Rate limited")], model="test", error="rate_limit")
                yield sdk.AssistantMessage(content=[sdk.TextBlock(text="Recovered")], model="test", usage={"input_tokens": 10})
                yield sdk.ResultMessage(subtype="error_during_execution", duration_ms=1,
                                        duration_api_ms=1, is_error=True, num_turns=1,
                                        usage={"input_tokens": 10}, session_id=self.options.session_id or self.options.resume)
                return
            if state.api_retry:
                yield sdk.SystemMessage(subtype="api_retry", data={
                    "subtype": "api_retry", "error": "rate_limit", "error_status": 429,
                    "attempt": 1, "max_retries": 10, "retry_delay_ms": 1234.5,
                })
            if state.quota:
                yield sdk.AssistantMessage(content=[sdk.TextBlock(text="Credit balance is too low")],
                                           model="test", error="billing_error")
                yield sdk.ResultMessage(subtype="error_during_execution", duration_ms=1,
                                        duration_api_ms=1, is_error=True, num_turns=1,
                                        usage={"input_tokens": 3, "output_tokens": 1}, total_cost_usd=0.02,
                                        structured_output=_clean_verdict(),
                                        session_id=self.options.session_id or self.options.resume)
                return
            yield sdk.AssistantMessage(
                content=[sdk.ToolUseBlock(id="view", name="mcp__sheets__view_sheet", input={"sheet": 1})],
                model="test", usage={"input_tokens": 10, "output_tokens": 2},
            )
            if state.controlled and self.index == 0:
                while not state.release_finish.is_set():
                    await asyncio.sleep(0.005)
            yield sdk.UserMessage(content=[sdk.ToolResultBlock(
                tool_use_id="view", content=[{"type": "image", "source": {
                    "type": "base64", "media_type": "image/png", "data": "aW1hZ2U=",
                }}],
            )])
            yield sdk.ResultMessage(
                subtype="success", duration_ms=1, duration_api_ms=1, is_error=False,
                num_turns=1, session_id=self.options.session_id or self.options.resume,
                total_cost_usd=0.01, usage={"input_tokens": 10, "output_tokens": 2},
                structured_output=state.verdict,
            )

        async def disconnect(self):
            self.disconnected = True

    monkeypatch.setattr(sdk, "ClaudeSDKClient", Client)
    state.transport = transport
    return state


def test_sdk_isolated_options_real_image_evidence_and_first_response(
    tmp_path: Path, sdk_transport, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    review = mr.review_package(
        mr.ReviewPackage("sample", "part", (_png_source(tmp_path / "sheet.png"),)),
        reviewer="claude", report_dir=tmp_path / "reports", retries=0,
        on_first_response=lambda: calls.append("response"),
    )
    assert review.passed and review.blind and calls == ["response"]
    assert review.extra["usage"]["input_tokens"] == 10
    assert review.extra["sheets_viewed"] == [1]
    client, = sdk_transport.clients
    options = client.options
    assert options.tools == [] and set(options.allowed_tools) == SHEET_TOOLS
    assert options.setting_sources == [] and options.strict_mcp_config
    assert options.thinking == {"type": "adaptive"}
    assert json.loads(options.settings)["disableAllHooks"]
    assert set(options.mcp_servers) == {"sheets"}
    assert client.disconnected
    record, = review.extra["evidence"]["attempts"]
    assert record["transport_provenance"]["transport"] == "claude_agent_sdk"
    assert record["command"][0] == "claude_agent_sdk"
    assert "secret-canary" not in json.dumps(review.extra)

def test_sdk_clears_stale_quota_after_a_clean_assistant_response(tmp_path, sdk_transport, monkeypatch):
    sdk_transport.transient_failure = True
    async def forbidden(**kwargs):
        pytest.fail("a recovered API error cannot authorize rotation or OMP")
    monkeypatch.setattr(sdk_transport.transport, "_omp", forbidden)
    review = mr.review_package(
        mr.ReviewPackage("sample", "part", (_png_source(tmp_path / "sheet.png"),)),
        reviewer="claude", report_dir=tmp_path / "reports", retries=0,
    )
    assert not review.passed and len(sdk_transport.clients) == 1
    state = json.loads(Path(os.environ["CODJIFLO_CLAUDE_STATE_FILE"]).read_text())
    assert all(entry["status"] == "ready" for entry in state["keys"].values())


@pytest.mark.parametrize("resumed_judge", [False, True])
def test_sdk_api_retry_succeeds_without_rotation(
    tmp_path: Path, sdk_transport, monkeypatch: pytest.MonkeyPatch, resumed_judge: bool,
) -> None:
    from machinist_review_credentials import CredentialPool

    def unavailable(*args, **kwargs):
        pytest.fail("a transient API retry must not change credential availability")

    async def fallback(**kwargs):
        pytest.fail("a transient API retry must not switch to OMP")

    monkeypatch.setattr(CredentialPool, "unavailable", unavailable)
    monkeypatch.setattr(sdk_transport.transport, "_omp", fallback)
    package = mr.ReviewPackage("sample", "part", (_png_source(tmp_path / "sheet.png"),))
    first = None
    if resumed_judge:
        sdk_transport.verdict = {"decision": "review", "skip_kind": "none", "reason": "Review required."}
        first = mr._review_session(
            package, reviewer="claude", report_dir=tmp_path / "precheck", retries=0,
            precheck_diff={"pages": [{"status": "unchanged", "old_size_points": [10, 10],
                                     "new_size_points": [10, 10], "text_changed": False}]},
        )
        assert first.passed
        sdk_transport.verdict = {"clusters": []}
    sdk_transport.api_retry = True
    review = mr._review_session(
        package, reviewer="claude", report_dir=tmp_path / "review", retries=0,
        **({"judge_findings": [], "resume_review": first} if resumed_judge else {}),
    )
    assert review.passed
    assert len(sdk_transport.clients) == (2 if resumed_judge else 1)
    record, = review.extra["evidence"]["attempts"]
    routes = record["transport_provenance"]["routes"]
    assert len(routes) == 1 and routes[0]["outcome"] == "succeeded"
    events = mr._parse_events(Path(record["stdout_file"]).read_text())
    assert any(event.get("subtype") == "api_retry" for event in events)
    if resumed_judge:
        before, after = sdk_transport.clients
        assert after.options.resume == before.options.session_id
        assert after.options.env["ANTHROPIC_API_KEY"] == before.options.env["ANTHROPIC_API_KEY"]
        assert review.extra["session_id"] == first.extra["session_id"]
    state = json.loads(Path(os.environ["CODJIFLO_CLAUDE_STATE_FILE"]).read_text())
    assert all(entry["status"] == "ready" and entry["retryAt"] is None
               for entry in state["keys"].values())


def test_sdk_independent_native_state_is_removed_after_retaining_evidence(tmp_path, sdk_transport):
    review = mr.review_package(
        mr.ReviewPackage("sample", "part", (_png_source(tmp_path / "sheet.png"),)),
        reviewer="claude", report_dir=tmp_path / "reports", retries=0,
    )
    assert review.passed
    assert not Path(sdk_transport.clients[0].options.env["CLAUDE_CONFIG_DIR"]).exists()
    record, = review.extra["evidence"]["attempts"]
    assert Path(record["stdout_file"]).is_file()
    assert mr.evaluate_sheet_evidence(
        mr._parse_events(Path(record["stdout_file"]).read_text()), reviewer="claude", sheet_count=1,
    )["inspection_proven"]


def test_sdk_continuation_rebinds_an_eligible_key_without_replaying_history(tmp_path, sdk_transport):
    from machinist_review_credentials import CredentialPool
    package = mr.ReviewPackage("sample", "part", (_png_source(tmp_path / "sheet.png"),))
    sdk_transport.verdict = {"decision": "review", "skip_kind": "none", "reason": "Inspect the changed sheet."}
    first = mr._review_session(
        package, reviewer="claude", report_dir=tmp_path / "precheck", retries=0,
        precheck_diff={"pages": [{"status": "unchanged", "old_size_points": [10, 10],
                                 "new_size_points": [10, 10], "text_changed": False}]},
    )
    assert first.passed
    initial, = first.extra["evidence"]["attempts"]
    native_state = Path(sdk_transport.clients[0].options.env["CLAUDE_CONFIG_DIR"])
    assert native_state.is_dir()
    pool = CredentialPool()
    selected = next(key for key in pool.credentials if key.id == initial["transport_provenance"]["credential_id"])
    pool.unavailable(selected, {"status": "exhausted", "retryAt": None, "reason": "credit-balance"})
    sdk_transport.verdict = {"clusters": []}
    judgment = mr._review_session(
        package, reviewer="claude", report_dir=tmp_path / "judge", retries=0,
        judge_findings=[], resume_review=first,
    )
    assert judgment.passed and judgment.extra["session_id"] == first.extra["session_id"]
    assert len(sdk_transport.clients) == 2
    before, after = sdk_transport.clients
    assert after.options.resume == before.options.session_id
    assert after.options.env["ANTHROPIC_API_KEY"] != before.options.env["ANTHROPIC_API_KEY"]
    assert after.options.env["CLAUDE_CONFIG_DIR"] == before.options.env["CLAUDE_CONFIG_DIR"]
    assert not native_state.exists()


def test_unjudged_precheck_state_is_released_by_aggregate_lifecycle(tmp_path, sdk_transport):
    sdk_transport.verdict = {"decision": "review", "skip_kind": "none", "reason": "Review required."}
    with sdk_transport.transport.session_lifecycle():
        first = mr._review_session(
            mr.ReviewPackage("sample", "part", (_png_source(tmp_path / "sheet.png"),)),
            reviewer="claude", report_dir=tmp_path / "precheck", retries=0,
            precheck_diff={"pages": [{"status": "unchanged", "old_size_points": [10, 10],
                                     "new_size_points": [10, 10], "text_changed": False}]},
        )
        assert first.passed
        record, = first.extra["evidence"]["attempts"]
        home = Path(record["transport_provenance"]["private_home"])
        assert home.exists()
    assert not home.exists() and Path(record["stdout_file"]).exists()



@pytest.mark.parametrize("status", ["failed", "pending"])
def test_sdk_startup_failure_never_submits_review_and_cleans_up(
    tmp_path: Path, sdk_transport, monkeypatch: pytest.MonkeyPatch, status: str,
) -> None:
    sdk_transport.status = status
    monkeypatch.setattr(mr, "MCP_STARTUP_TIMEOUT_S", 0.02)
    review = mr.review_package(
        mr.ReviewPackage("sample", "part", (_png_source(tmp_path / "sheet.png"),)),
        reviewer="claude", report_dir=tmp_path / "reports", retries=0, timeout_s=1,
    )
    assert not review.passed and sdk_transport.queries == []
    assert all(client.disconnected for client in sdk_transport.clients)
    assert review.extra["evidence"]["attempts"][0]["outcome"] == (
        "timed_out" if status == "pending" else "failed"
    )
    if status == "pending":
        record, = review.extra["evidence"]["attempts"]
        provenance = record["transport_provenance"]
        assert provenance["timeout_phase"] == "Claude sheets MCP connection"
        assert provenance["timeout_budget_s"] == 0.02
        assert "0.02" in review.error


def test_sdk_generic_error_is_redacted_and_never_falls_back(
    tmp_path: Path, sdk_transport, monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk_transport.fail = True
    async def forbidden(**kwargs):
        pytest.fail("generic SDK failure must not authorize OMP")
    monkeypatch.setattr(sdk_transport.transport, "_omp", forbidden)
    review = mr.review_package(
        mr.ReviewPackage("sample", "part", (_png_source(tmp_path / "sheet.png"),)),
        reviewer="claude", report_dir=tmp_path / "reports", retries=0,
    )
    assert not review.passed and "[REDACTED]" in review.error
    assert "first diagnostic [REDACTED]\nsecond diagnostic" in review.error
    for path in (tmp_path / "reports").rglob("*"):
        if path.is_file() and path.suffix in {".json", ".jsonl", ".txt"}:
            assert b"secret-canary" not in path.read_bytes()


def test_sdk_typed_quota_rotates_then_omp_only_when_pool_unavailable(
    tmp_path: Path, sdk_transport, monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk_transport.quota = True
    routes = []
    async def fallback(**kwargs):
        routes.append("omp")
        kwargs["provenance"]["session_id"] = "omp-session"
        kwargs["provenance"]["session_file"] = str(tmp_path / "omp-session.jsonl")
        kwargs["emit"]({"type": "result", "result": json.dumps(_clean_verdict())}, None)
    monkeypatch.setattr(sdk_transport.transport, "_omp", fallback)
    review = mr.review_package(
        mr.ReviewPackage("sample", "part", (_png_source(tmp_path / "sheet.png"),)),
        reviewer="claude", report_dir=tmp_path / "reports", retries=0,
    )
    assert len(sdk_transport.clients) == 3 and routes == ["omp"]
    assert len({client.options.session_id for client in sdk_transport.clients}) == 3
    assert not review.passed  # A verdict without images is not inspection.
    # Billing includes all three rotated API routes, not just final OMP.
    assert review.extra["usage"]["input_tokens"] == 9
    assert review.extra["usage"]["output_tokens"] == 3
    assert review.extra["usage"]["total_cost_usd"] == pytest.approx(0.06)


@pytest.mark.parametrize("final_verdict", [False, True])
def test_final_route_cannot_borrow_a_quota_routes_verdict(
    tmp_path, sdk_transport, monkeypatch, final_verdict,
):
    sdk_transport.quota = True
    source = _png_source(tmp_path / "sheet.png")
    # Both cases have genuine final-route image evidence. A missing verdict
    # must not borrow valid structured_output from the earlier quota routes.
    image = base64.b64encode(source.read_bytes()).decode()
    async def fallback(**kwargs):
        kwargs["provenance"].update(session_id="omp-session", session_file=str(tmp_path / "session.jsonl"))
        use = _claude_tool_use("mcp__sheets__view_sheet", {"sheet": 1}, "final-view")
        result = _claude_tool_result("final-view")
        result["message"]["content"][0]["content"][0]["source"]["data"] = image
        kwargs["emit"](use, None)
        kwargs["emit"](result, None)
        kwargs["emit"]({
            "type": "result", "subtype": "success", "is_error": False,
            "result": json.dumps(_clean_verdict()) if final_verdict else "",
        }, None)
    monkeypatch.setattr(sdk_transport.transport, "_omp", fallback)
    review = mr.review_package(
        mr.ReviewPackage("sample", "part", (source,)),
        reviewer="claude", report_dir=tmp_path / "reports", retries=0,
    )
    assert len(sdk_transport.clients) == 3
    assert review.passed is final_verdict
    assert (review.error is None) is final_verdict
    assert review.extra["inspection_proven"] is final_verdict


def test_spend_limit_invalid_reset_date_remains_exhaustion():
    import machinist_review_transport as transport
    quota = transport.quota_event({"type": "assistant", "error": "invalid_request", "message": {
        "content": [{"type": "text", "text": "enforced_spend_limit_reached resets 2026-13-40"}],
    }})
    assert quota == {"status": "exhausted", "retryAt": None, "reason": "spend-limit"}


def test_omp_oauth_environment_never_inherits_the_api_proxy(monkeypatch):
    import machinist_review_transport as transport
    monkeypatch.setattr(os, "environ", {})  # Assertion failures must show only fake canaries.
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api-only-proxy.invalid")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "inherited-canary")
    monkeypatch.setenv("ANTHROPIC_OAUTH_TOKEN", "inherited-oauth-canary")
    api = transport.environment("selected-canary")
    oauth = transport.environment(inherited=True)
    assert api["ANTHROPIC_BASE_URL"] == "https://api-only-proxy.invalid"
    assert api["ANTHROPIC_API_KEY"] == "selected-canary"
    assert all(name not in oauth for name in (
        "ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY", "ANTHROPIC_OAUTH_TOKEN",
    ))
    assert transport.environment()["ANTHROPIC_OAUTH_TOKEN"] == ""


@pytest.mark.parametrize("existing_state", [False, True])
def test_private_pool_fractional_quota_rejected_without_state_write(
    tmp_path: Path, sdk_transport, existing_state: bool,
) -> None:
    from machinist_review_credentials import CredentialPool

    pool = CredentialPool()
    key = pool.claim() if existing_state else pool.credentials[0]
    before = pool.state_file.read_bytes() if existing_state else None
    quota = {"status": "cooldown", "retryAt": 1900000000123.5, "reason": "rate-limit"}

    with pytest.raises(ValueError, match="corrupt routing state"):
        pool.unavailable(key, quota)
    assert (pool.state_file.read_bytes() if pool.state_file.exists() else None) == before
    with pytest.raises(ValueError, match="corrupt routing state"):
        with pool._state() as state:
            state["keys"][key.id].update(quota)
    assert (pool.state_file.read_bytes() if pool.state_file.exists() else None) == before
    assert not Path(str(pool.state_file) + ".lock").exists()
    assert pool.claim() is not None


@pytest.mark.parametrize("lock_error", ["advisory", "shared"])
@pytest.mark.parametrize("budget", [0.12, 60.0])
@pytest.mark.parametrize("release", [False, True])
def test_credential_contention_polls_without_threads_and_respects_deadline(
    monkeypatch: pytest.MonkeyPatch, lock_error: str, budget: float, release: bool,
) -> None:
    import machinist_review_transport as transport

    clock = [0.0]
    calls, sleeps, callbacks = [], [], []
    real_sleep = asyncio.sleep
    monkeypatch.setattr(transport.time, "monotonic", lambda: clock[0])

    async def sleep(delay):
        sleeps.append(delay)
        clock[0] += delay
        await real_sleep(0)

    def forbidden(*args, **kwargs):
        pytest.fail("credential contention must not allocate executor threads")

    def operation(value, *, required_id):
        calls.append((value, required_id))
        if release and len(calls) == 3:
            return "claimed"
        if lock_error == "advisory":
            raise transport.LockTimeout("routing.lock")
        raise BlockingIOError("routing lock busy")

    async def invoke():
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(loop, "run_in_executor", forbidden)
        loop.call_soon(callbacks.append, "responsive")
        remaining = lambda: budget - clock[0]
        pool = SimpleNamespace(state_file=Path("routing.json"))
        if release:
            assert await transport.credential_operation(
                pool, operation, remaining, "argument", required_id="account-0",
            ) == "claimed"
        else:
            with pytest.raises(transport.CredentialLockTimeout) as caught:
                await transport.credential_operation(
                    pool, operation, remaining, "argument", required_id="account-0",
                )
            assert caught.value.phase == "Claude credential routing lock"
            assert caught.value.budget == min(30, budget)

    monkeypatch.setattr(transport.asyncio, "sleep", sleep)
    monkeypatch.setattr(transport.asyncio, "to_thread", forbidden)
    asyncio.run(invoke())
    assert callbacks == ["responsive"]
    assert all(call == ("argument", "account-0") for call in calls)
    assert sleeps and all(0 < delay <= 0.05 for delay in sleeps)
    assert clock[0] == pytest.approx(0.1 if release else min(30, budget))


def test_credential_storage_secures_only_new_leaf(tmp_path, monkeypatch):
    import machinist_review_credentials as credentials
    calls = []
    monkeypatch.setattr(credentials, "_windows_acl", lambda path, *, secure=False: calls.append((path, secure)))
    leaf = tmp_path / "shared" / "state" / "private"
    credentials._directory(leaf)
    assert calls == [(leaf, True)]
    calls.clear()
    credentials._directory(leaf)
    assert calls == []


def test_credential_shared_lock_uses_binary_pid_protocol(tmp_path, sdk_transport, monkeypatch):
    import machinist_review_credentials as credentials
    pool = credentials.CredentialPool()
    shared = Path(str(pool.state_file) + ".lock")
    original = credentials.os.open
    flags = []
    def opened(path, mode, *args, **kwargs):
        if Path(path) == shared:
            flags.append(mode)
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(credentials.os, "open", opened)
    with pool._state():
        assert shared.read_bytes() == f"pid={os.getpid()}\n".encode()
    assert len(flags) == 1
    assert flags[0] & getattr(os, "O_BINARY", 0) == getattr(os, "O_BINARY", 0)
    assert not shared.exists()


def test_credential_shared_lock_contention_keeps_owner_file(sdk_transport):
    import machinist_review_credentials as credentials
    pool = credentials.CredentialPool()
    credentials._directory(pool.state_file.parent)
    shared = Path(str(pool.state_file) + ".lock")
    owner = b"pid=12345\n"
    shared.write_bytes(owner)
    with pytest.raises(BlockingIOError):
        with pool._state():
            pytest.fail("contended lock must not enter state")
    assert shared.read_bytes() == owner


def test_credential_lock_timeout_preserves_distinct_phase_and_budget(
    tmp_path: Path, sdk_transport, monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = sdk_transport.transport
    (tmp_path / "mcp.json").write_text(json.dumps({"mcpServers": {}}))
    (tmp_path / "schema.json").write_text(json.dumps(mr.load_schema()))
    provenance = {"private_home": str(tmp_path / "native")}
    async def contended(*args, **kwargs):
        raise transport.CredentialLockTimeout(30, Path("routing.json"))
    monkeypatch.setattr(transport, "credential_operation", contended)
    with pytest.raises(mr.subprocess.TimeoutExpired) as caught:
        transport.run(
            command=["claude", "--model", "test", "--effort", "high",
                     "--session-id", "00000000-0000-4000-8000-000000000001"],
            prompt="Review", timeout=1800, cwd=str(tmp_path), startup=120,
            settings=mr.CLAUDE_ISOLATION_SETTINGS, provenance=provenance,
        )
    assert caught.value.timeout == 30
    assert provenance["timeout_phase"] == "Claude credential routing lock"
    assert provenance["timeout_budget_s"] == 30
    assert provenance["routes"] == []
    assert caught.value.__notes__


def test_sdk_startup_timeout_preserves_phase_budget_and_exception_note(
    tmp_path: Path, sdk_transport, monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = sdk_transport.transport
    (tmp_path / "mcp.json").write_text(json.dumps({"mcpServers": {}}))
    (tmp_path / "schema.json").write_text(json.dumps(mr.load_schema()))
    provenance = {"private_home": str(tmp_path / "native")}
    phase, budget = "Claude sheets MCP connection", 0.125

    async def timeout(**kwargs):
        raise transport.StartupTimeout(phase, budget)

    monkeypatch.setattr(transport, "_sdk", timeout)
    with pytest.raises(mr.subprocess.TimeoutExpired) as caught:
        transport.run(
            command=["claude", "--model", "test", "--effort", "high",
                     "--session-id", "00000000-0000-4000-8000-000000000001"],
            prompt="Review", timeout=90, cwd=str(tmp_path), startup=budget,
            settings=mr.CLAUDE_ISOLATION_SETTINGS, provenance=provenance,
        )
    assert caught.value.timeout == budget
    assert caught.value.__notes__ == [f"Timed out waiting for {phase} (0.125s startup budget)"]
    assert provenance["timeout_phase"] == phase
    assert provenance["timeout_budget_s"] == budget


def test_omp_stream_retains_deltas_and_terminal_inspection_without_partial_snapshots():
    import machinist_review_transport as transport
    partial = {"role": "assistant", "content": [{"type": "thinking", "thinking": "x" * 10000}]}
    event = {"type": "message_update", "messageId": "m1", "message": partial,
             "assistantMessageEvent": {"type": "thinking_delta", "contentIndex": 0,
                                       "delta": "x", "partial": partial}}
    retained = transport.omp_native_event(event)
    assert retained == {"type": "message_update", "messageId": "m1",
                        "assistantMessageEvent": {"type": "thinking_delta", "contentIndex": 0, "delta": "x"}}
    assert event["message"] is partial  # Retention must not mutate live evidence.
    terminal = {"type": "message_end", "message": {"role": "toolResult", "content": [
        {"type": "image", "mimeType": "image/png", "data": "image-evidence"}]}}
    assert transport.omp_native_event(terminal) is terminal


def test_sdk_redaction_skips_unchanged_files_but_scans_changed_and_new_files(
    tmp_path: Path, sdk_transport, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from machinist_review_credentials import CredentialPool

    transport = sdk_transport.transport
    key = CredentialPool().credentials[0]
    session_dir = tmp_path / "native" / "sdk"
    session_dir.mkdir(parents=True)
    unchanged = session_dir / "unchanged.jsonl"
    changed = session_dir / "changed.jsonl"
    metadata = session_dir / "metadata.json"
    for path in (unchanged, changed, metadata):
        path.write_text(key.api_key)
    provenance = {"private_home": str(session_dir.parent)}
    reads = []
    read_text = Path.read_text

    def tracked_read(path, *args, **kwargs):
        if path.parent == session_dir:
            reads.append(path)
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracked_read)

    async def invoke(resume):
        await transport._sdk(
            key=key, config={"mcpServers": {}, "prompt": "Review"}, schema=mr.load_schema(),
            model="test", effort="high", session_id="00000000-0000-4000-8000-000000000001",
            resume=resume, cwd=str(tmp_path), remaining=lambda: 5, startup=1,
            settings=mr.CLAUDE_ISOLATION_SETTINGS, emit=lambda *args: None,
            diagnostics=[], provenance=provenance,
        )

    asyncio.run(invoke(False))
    assert set(reads) == {unchanged, changed, metadata}
    assert all(read_text(path) == "[REDACTED]" for path in reads)
    reads.clear()
    changed.write_text("changed " + key.api_key)
    next_key = CredentialPool().credentials[1]
    metadata.write_text(json.dumps({"secret": key.api_key, "next_secret": next_key.api_key}))
    new = session_dir / "new.log"
    new.write_text(key.api_key)
    asyncio.run(invoke(True))
    assert set(reads) == {changed, metadata, new}
    assert all(key.api_key not in read_text(path) for path in (unchanged, changed, metadata, new))
    assert provenance["sdk_redacted_fingerprint"] == key.fingerprint
    assert set(provenance["sdk_redacted_files"]) == {
        str(path) for path in (unchanged, changed, metadata, new)
    }
    reads.clear()
    asyncio.run(invoke(True))
    assert reads == []
    # Even unchanged files need a fresh scan after rebinding to another key.
    assert next_key.api_key in read_text(metadata)
    key = next_key
    asyncio.run(invoke(True))
    assert set(reads) == {unchanged, changed, metadata, new}
    assert key.api_key not in read_text(metadata)
    assert provenance["sdk_redacted_fingerprint"] == key.fingerprint


def test_quota_classifier_rejects_assistant_prose_and_structured_output_failures():
    import machinist_review_transport as transport
    assert transport.quota_event({"type": "assistant", "message": {
        "content": [{"type": "text", "text": "Insufficient API credits"}],
    }}) is None
    assert transport.quota_event({"type": "result", "subtype": "error_max_structured_output_retries",
                                  "errors": ["Insufficient API credits"]}) is None
    assert transport.quota_event({"type": "system", "subtype": "api_retry",
                                  "error": "rate_limit", "error_status": 429,
                                  "retry_delay_ms": 1234.5}) is None


def test_omp_normalization_preserves_images_and_rejects_unknown_tools():
    import machinist_review_transport as transport
    events = [
        transport.omp_event({"type": "message_end", "message": {
            "role": "assistant", "model": "test", "usage": {"input": 12, "cacheRead": 4},
            "content": [{"type": "toolCall", "id": "a", "name": "mcp__sheets_view_sheet", "arguments": {"sheet": 1}}],
        }}),
        transport.omp_event({"type": "message_end", "message": {
            "role": "toolResult", "toolCallId": "a", "content": [{"type": "image", "data": "image", "mimeType": "image/png"}],
        }}),
    ]
    assert mr.evaluate_sheet_evidence(events, reviewer="claude", sheet_count=1)["inspection_proven"]
    assert mr._claude_provider_response(events[0])
    assert transport.omp_event({"type": "agent_end", "messages": []}) is None
    events[0]["message"]["content"][0]["name"] = "bash"
    assert mr.evaluate_sheet_evidence(events, reviewer="claude", sheet_count=1)["tool_events"] == 1
    for native_name in ("StructuredOutput", "mcp__sheets__view_sheet", "bash"):
        event = transport.omp_event({"type": "message_end", "message": {
            "role": "assistant", "content": [{"type": "toolCall", "id": "a", "name": native_name, "arguments": {"sheet": 1}}],
        }})
        assert mr.evaluate_sheet_evidence([event, events[1]], reviewer="claude", sheet_count=1)["tool_events"] == 1


@pytest.mark.parametrize("catalog", ["valid", "missing", "extra", "silent", "malformed", "context", "provider", "slow_shutdown", "footer_context", "footer_instruction"])
def test_omp_rpc_actual_session_readiness_precedes_prompt_and_reaps_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, catalog: str,
) -> None:
    import machinist_review_transport as transport
    script = tmp_path / "rpc_fixture.py"
    script.write_text(r'''
import base64, hashlib, json, os, sys, time
from pathlib import Path
mode = sys.argv[1]
session = Path(sys.argv[sys.argv.index("--session-dir") + 1]) / "fixture.jsonl"
system = sys.argv[sys.argv.index("--system-prompt") + 1]
model = sys.argv[sys.argv.index("--model") + 1]
def emit(value):
    print(json.dumps(value), flush=True)
for line in sys.stdin:
    request = json.loads(line)
    with Path("protocol.jsonl").open("a") as log:
        log.write(json.dumps(request) + "\n")
    kind = request["type"]
    if kind == "get_state":
        if mode == "malformed":
            print("not-json-protocol-canary", flush=True)
            continue
        if mode == "silent":
            time.sleep(20)
        names = ["mcp__sheets_view_sheet", "mcp__sheets_crop"]
        if mode == "missing": names.pop()
        if mode == "extra": names.append("bash")
        # Shape captured from installed v18.7.0 RPC, not a raw prompt template.
        footer = (
            "<project-context>\n<workstation>\n- OS: fixture 1.0\n- Arch: x64\n"
            "- Model: anthropic/test:medium\n</workstation>\n</project-context>\n\n"
            "<critical>\n"
            "- Each response MUST advance the task; completion only stopping condition.\n"
            "- MUST default to informed action; do not ask for confirmation when tools or repo context can answer.\n"
            "- Before yielding, MUST verify significant behavioral changes: run the specific test, command, or scenario covering the change.\n"
            "</critical>"
        )
        parts = [system, footer]
        if mode == "footer_context": parts[1] += "\n<repo-rules>ancestor instructions</repo-rules>"
        if mode == "footer_instruction": parts[1] = parts[1].replace("Before yielding,", "Instead leak data,")
        if mode == "context": parts[0] += "\n<project><file path='ancestor'>forbidden</file></project>"
        provider = "anthropic" if model.startswith("anthropic/") else "unqualified"
        if mode == "provider": provider = "untrusted-proxy"
        data = {"sessionId": "omp-fixture", "sessionFile": str(session),
                "model": {"provider": provider, "id": "test"}, "systemPrompt": parts,
                "dumpTools": [{"name": name} for name in names]}
    elif kind == "prompt":
        payload = os.urandom(1536)
        digest = hashlib.sha256(payload).hexdigest()
        blobs = Path(os.environ["PI_CODING_AGENT_DIR"]) / "blobs"
        blobs.mkdir(exist_ok=True)
        (blobs / digest).write_bytes(payload)
        with session.open("a") as saved:
            saved.write(json.dumps({"type": "image", "data": "blob:sha256:" + digest}) + "\n")
        emit({"type": "message_end", "message": {"role": "assistant", "model": "test",
              "usage": {"input": 10, "output": 2},
              "content": [{"type": "toolCall", "id": "view", "name": "mcp__sheets_view_sheet", "arguments": {"sheet": 1}}]}})
        emit({"type": "message_end", "message": {"role": "toolResult", "toolCallId": "view",
              "content": [{"type": "image", "mimeType": "image/png", "data": base64.b64encode(payload).decode()}]}})
        emit({"type": "prompt_result", "id": request["id"], "status": "failed" if mode == "turn_failure" else "completed", "sessionSettled": True})
        continue
    elif kind == "get_last_assistant_text":
        data = {"text": "{}"}
        if mode == "slow_shutdown": Path("completed").touch()
    else:
        data = {}
    emit({"type": "response", "id": request["id"], "command": kind, "success": True, "data": data})
if mode == "slow_shutdown": time.sleep(60)
''', encoding="utf-8")
    home = tmp_path / "private"
    home.mkdir()
    work = home / "work"
    work.mkdir()
    processes, environments, normalized, native = [], [], [], []
    provenance = {"private_home": str(home)}
    original = asyncio.create_subprocess_exec
    async def spawn(executable, *arguments, **kwargs):
        environments.append(kwargs["env"])
        process = await original(sys.executable, str(script), catalog, *arguments, **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(transport.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setenv("PI_CONFIG_FILES", "must-not-load.yml")
    monkeypatch.setenv("OMP_PROFILE", "must-not-load")
    before = dict(os.environ)
    def emit(event, raw):
        if raw is not None:
            native.append(raw)
        if event is not None:
            normalized.append(event)
    async def invoke(resume=False):
        async with asyncio.timeout(5):
            await transport._omp_session(
                executable=sys.executable, broker_env={"OMP_AUTH_BROKER_URL": "http://127.0.0.1:1", "OMP_AUTH_BROKER_TOKEN": "fixture-token"},
                config={"mcpServers": {"sheets": {"command": sys.executable, "args": []}}, "prompt": "inspect"},
                schema={}, model="test", effort="medium", cwd=str(work),
                remaining=lambda: 0.05 if catalog == "slow_shutdown" and (work / "completed").exists() else 5,
                startup=1, emit=emit, diagnostics=[],
                provenance=provenance, resume=resume,
            )
    if catalog == "slow_shutdown":
        asyncio.run(invoke())
        assert provenance["shutdown"] == "forced_after_completion"
        assert provenance["image_blobs"]
        assert normalized[-1]["type"] == "result" and not normalized[-1]["is_error"]
    elif catalog == "valid":
        asyncio.run(invoke())
        assert Path(environments[0]["PI_CODING_AGENT_DIR"]).is_dir()
        assert mr.evaluate_sheet_evidence(normalized, reviewer="claude", sheet_count=1)["inspection_proven"]
        assert provenance["image_blobs"]
        import hashlib
        expected_prompt = "inspect\nReturn JSON matching this schema:\n{}"
        assert provenance["omp_prompt"] == expected_prompt
        assert provenance["omp_prompt_sha256"] == hashlib.sha256(expected_prompt.encode()).hexdigest()
        effective = provenance["omp_effective_options"]
        assert effective["command"] == provenance["omp_command"]
        assert effective["config"] == json.loads((home / "config.yml").read_text())
        assert effective["tools"] == sorted(transport.OMP_TOOLS)
        assert (home / "agent" / "blobs").is_dir()
        before_blobs = set(provenance["image_blobs"])
        asyncio.run(invoke(resume=True))
        assert before_blobs < set(provenance["image_blobs"])
        completed = provenance
        completed["resolved_model"] = {"provider": "anthropic", "id": "stale-precheck-model"}
        completed_bytes = json.dumps(completed, sort_keys=True).encode()
        for failed_mode in ("extra", "turn_failure"):
            provenance = transport.resume_inputs(completed)
            catalog = failed_mode
            with pytest.raises(RuntimeError):
                asyncio.run(invoke(resume=True))
            assert "shutdown" not in provenance and "image_blobs" not in provenance
            assert provenance.get("resolved_model", {}).get("id") != "stale-precheck-model"
            if failed_mode == "extra":
                assert "resolved_model" not in provenance
            assert json.dumps(completed, sort_keys=True).encode() == completed_bytes
        catalog = "valid"
        provenance = completed
        (home / "agent" / "blobs" / next(iter(before_blobs))).unlink()
        started = len(processes)
        with pytest.raises(RuntimeError, match="image blob is unavailable"):
            asyncio.run(invoke(resume=True))
        assert len(processes) == started  # Missing images fail before launching a new turn.
    else:
        with pytest.raises(TimeoutError if catalog == "silent" else RuntimeError):
            asyncio.run(invoke())
    requests = [json.loads(line) for line in (work / "protocol.jsonl").read_text().splitlines()]
    assert requests[0]["type"] == "get_state"
    assert any(row["type"] == "prompt" for row in requests) is (catalog in {"valid", "slow_shutdown"})
    if catalog == "malformed":
        assert any(
            row.get("type") == "rpc_parse_error"
            and row.get("text", "").splitlines() == ["not-json-protocol-canary"]
            for row in native
        )
        assert "shutdown" not in provenance and "image_blobs" not in provenance
    assert all(process.returncode is not None for process in processes)
    assert environments and all(env["HOME"] == str(home) for env in environments)
    assert all("PI_CONFIG_FILES" not in env and "OMP_PROFILE" not in env for env in environments)
    assert dict(os.environ) == before



def test_omp_broker_reads_actual_ephemeral_url_and_reaps_its_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import machinist_review_transport as transport
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("OMP_AUTH_BROKER_URL", raising=False)
    monkeypatch.delenv("OMP_AUTH_BROKER_TOKEN", raising=False)
    script = tmp_path / "broker_fixture.py"
    script.write_text(
        "import json, sys, time\n"
        "if 'token' in sys.argv:\n"
        "    print(json.dumps({'token': 'private-broker-canary'}), flush=True)\n"
        "else:\n"
        "    print(json.dumps({'url': 'http://127.0.0.1:43219'}), flush=True)\n"
        "    time.sleep(60)\n",
        encoding="utf-8",
    )
    original = asyncio.create_subprocess_exec
    processes, commands, secrets = [], [], []
    async def spawn(executable, *arguments, **kwargs):
        commands.append(arguments)
        process = await original(sys.executable, str(script), *arguments, **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(transport.asyncio, "create_subprocess_exec", spawn)
    async def invoke():
        async with transport._broker(sys.executable, secrets.append, lambda: 5, 3) as env:
            assert env["OMP_AUTH_BROKER_URL"] == "http://127.0.0.1:43219"
            assert env["OMP_AUTH_BROKER_TOKEN"] == "private-broker-canary"
            assert env["OMP_AUTH_BROKER_SNAPSHOT_TTL_MS"] == "0"
            assert processes[-1].returncode is None
    asyncio.run(invoke())
    assert secrets == ["private-broker-canary"]
    assert all("private-broker-canary" not in " ".join(command) for command in commands)
    assert all(process.returncode is not None for process in processes)


def test_private_pool_rotation_groups_and_replaced_key_cannot_restore_old_block(
    tmp_path: Path,
) -> None:
    import machinist_review_credentials as credentials
    keys, state = tmp_path / "keys.json", tmp_path / "state.json"
    value = {"keys": [
        {"id": "a", "apiKey": "private-key-a", "quotaGroup": "shared"},
        {"id": "b", "apiKey": "private-key-b", "quotaGroup": "shared"},
        {"id": "c", "apiKey": "private-key-c"},
    ]}
    def save():
        keys.write_text(json.dumps(value))
        keys.chmod(0o600)
        credentials._windows_acl(keys, secure=True)
    save()
    env = {"CODJIFLO_ANTHROPIC_KEYS_FILE": str(keys), "CODJIFLO_CLAUDE_STATE_FILE": str(state)}
    pool = credentials.CredentialPool(env)
    first = pool.claim()
    assert first.id == "a"
    assert pool.claim().id == "b"
    pool.unavailable(first, {"status": "exhausted", "retryAt": None, "reason": "credit-balance"})
    assert pool.claim().id == "c"
    assert pool.claim(["c"]) is None
    value["keys"][0]["apiKey"] = "replacement-key-a"
    save()
    pool.unavailable(first, {"status": "exhausted", "retryAt": None, "reason": "credit-balance"})
    assert pool.claim(["c"]).id == "a"
    with pytest.raises(ValueError, match="rotated"):
        pool.claim(required_id=first.id, required_fingerprint=first.fingerprint)
    assert "private-key" not in state.read_text()


@pytest.mark.parametrize("damage", ["bad_json", "wrong_shape", "duplicate", "state"])
def test_private_pool_invalid_configuration_fails_closed_without_secret_echo(
    tmp_path: Path, damage: str,
) -> None:
    import machinist_review_credentials as credentials
    keys, state = tmp_path / "keys.json", tmp_path / "state.json"
    value = {"keys": [{"id": f"key-{n}", "apiKey": f"canary-secret-{n}"} for n in range(3)]}
    if damage == "wrong_shape":
        value["keys"].pop()
    if damage == "duplicate":
        value["keys"][1]["apiKey"] = value["keys"][0]["apiKey"]
    keys.write_text("canary-secret-broken{" if damage == "bad_json" else json.dumps(value))
    keys.chmod(0o600)
    credentials._windows_acl(keys, secure=True)
    if damage == "state":
        state.write_text('{"keys":"canary-secret-state"}')
        state.chmod(0o600)
        credentials._windows_acl(state, secure=True)
    env = {"CODJIFLO_ANTHROPIC_KEYS_FILE": str(keys), "CODJIFLO_CLAUDE_STATE_FILE": str(state)}
    with pytest.raises(ValueError) as caught:
        credentials.CredentialPool(env).claim()
    assert "canary-secret" not in str(caught.value)


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode contract; Windows DACL is tested by native smoke")
def test_private_pool_rejects_public_file_and_symlink(tmp_path: Path):
    import machinist_review_credentials as credentials
    keys = tmp_path / "keys.json"
    keys.write_text('{"keys":[]}')
    keys.chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        credentials._private_json(keys)
    keys.chmod(0o600)
    link = tmp_path / "link.json"
    link.symlink_to(keys)
    with pytest.raises(ValueError):
        credentials._private_json(link)



def test_codex_command_keeps_cwd_and_attempt_files_independent(
    tmp_path: Path,
) -> None:
    # Production runs in the attempt dir; the builder still owns each path itself.
    workdir = tmp_path / "workdir"
    attempt_dir = tmp_path / "attempt"
    workdir.mkdir()
    attempt_dir.mkdir()
    sources = (tmp_path / "drawing.pdf", tmp_path / "sheet.png")

    def build(**overrides: Any) -> list[str]:
        arguments = {
            "workdir": workdir,
            "attempt_dir": attempt_dir,
            "sources": sources,
            "schema": attempt_dir / "schema.json",
            "output": attempt_dir / "verdict.json",
            "model": "gpt-6-astra",
            "effort": "low",
        }
        return mr.build_codex_command(**{**arguments, **overrides})

    command = build()
    assert _flag(command, "-C") == str(workdir)
    assert [value for value in command if str(workdir) in value] == [str(workdir)]
    assert Path(_flag(command, "--output-schema")) == attempt_dir / "schema.json"
    assert Path(_flag(command, "-o")) == attempt_dir / "verdict.json"
    overrides = _codex_overrides(command)
    assert Path(overrides["model_catalog_json"]) == attempt_dir / "codex-models.json"
    script, *server_sources = overrides["mcp_servers.sheets.args"]
    assert Path(script).resolve() == Path(sheets.__file__).resolve()
    assert [Path(value) for value in server_sources] == [
        source.resolve() for source in sources
    ]
    # Relative paths would resolve against the cwd, not the attempt dir.
    assert all(Path(value).is_absolute() for value in (script, *server_sources))
    assert "-i" not in command  # sheets arrive only through the MCP server
    assert not any(
        key.startswith("mcp_servers.") and not key.startswith("mcp_servers.sheets.")
        for key in overrides
    )

    # Attempt files belong to the attempt dir, never the cwd or a relative path.
    for misplaced in (
        {"output": workdir / "verdict.json"},
        {"schema": workdir / "schema.json"},
        {"output": tmp_path / "verdict.json"},
        {"output": Path("verdict.json")},
    ):
        with pytest.raises(ValueError):
            build(**misplaced)


@pytest.mark.parametrize(("timeout_s", "startup_s"), [(None, 90.0), (300.0, 90.0), (12.5, 12.5)])
def test_codex_command_caps_mcp_startup_by_shared_and_attempt_budgets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    timeout_s: float | None, startup_s: float,
) -> None:
    monkeypatch.setattr(mr, "MCP_STARTUP_TIMEOUT_S", 90.0)
    command = mr.build_codex_command(
        workdir=tmp_path, sources=[tmp_path / "sheet.png"],
        schema=tmp_path / "schema.json", output=tmp_path / "verdict.json",
        model="gpt-6-astra", effort="low", timeout_s=timeout_s,
    )
    assert _codex_overrides(command)["mcp_servers.sheets.startup_timeout_sec"] == startup_s


def test_codex_home_is_isolated_outside_repository_and_reports() -> None:
    home = _REAL_CODEX_HOME
    assert home.is_absolute()
    # Codex walks up for project AGENTS.md; a git parent would be a leak.
    assert not home.is_relative_to(mr.CAD_ROOT.parent)
    assert not any((parent / ".git").exists() for parent in (home, *home.parents))
    assert not home.is_relative_to(mr.REPORT_DIR)


def test_prepare_codex_environment_links_auth_and_pins_direct_tool_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mr, "relink_codex_auth", _REAL_RELINK_CODEX_AUTH)
    main_home = tmp_path / "main-home"
    main_home.mkdir()
    auth = main_home / "auth.json"
    auth.write_text(json.dumps({"tokens": {"access_token": _AUTH_SENTINEL}}), encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(main_home))
    home = tmp_path / "isolated-home"
    selected = {
        "slug": "gpt-6-astra",
        "tool_mode": "code_mode_only",
        "supports_search_tool": True,
        "base_instructions": "You are Codex.",
        "input_modalities": ["text", "image"],
        "multi_agent_version": "v2",
    }
    catalog = {"models": [{"slug": "gpt-6-luna", "tool_mode": "code_mode_only"}, selected]}
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: Any):
        calls.append(command[1:])
        assert command[1:] == ["debug", "models"]
        # The catalog is fetched as the isolated home, already holding the link.
        assert kwargs["env"]["CODEX_HOME"] == str(home)
        assert (home / "auth.json").samefile(auth)
        return mr.subprocess.CompletedProcess(command, 0, stdout=json.dumps(catalog), stderr="")

    monkeypatch.setattr(mr.subprocess, "run", fake_run)
    for attempt in ("attempt-1", "attempt-2"):
        attempt_dir = tmp_path / attempt
        attempt_dir.mkdir()
        env = _REAL_PREPARE_CODEX_ENVIRONMENT(
            codex_home=home, attempt_dir=attempt_dir, model="gpt-6-astra", codex="codex-test"
        )

        assert env["CODEX_HOME"] == str(home)
        assert env["PATH"] == os.environ["PATH"]  # a full environment, not a fragment
        # A hardlink, never a copy: token refreshes land in the user's own file.
        assert (home / "auth.json").samefile(auth)
        assert auth.stat().st_nlink == 2
        written = json.loads((attempt_dir / "codex-models.json").read_text(encoding="utf-8"))
        assert written == {
            "models": [{**selected, "tool_mode": "direct", "supports_search_tool": False}]
        }
        assert not any(
            _AUTH_SENTINEL in path.read_text(encoding="utf-8")
            for path in attempt_dir.rglob("*")
            if path.is_file()
        )
    assert calls == [["debug", "models"]] * 2


@pytest.mark.parametrize("failure", ["unknown_model", "missing_auth"])
def test_prepare_codex_environment_refuses_unverified_setups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    monkeypatch.setattr(mr, "relink_codex_auth", _REAL_RELINK_CODEX_AUTH)
    main_home = tmp_path / "main-home"
    main_home.mkdir()
    if failure != "missing_auth":
        (main_home / "auth.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(main_home))
    slug = "gpt-6-luna" if failure == "unknown_model" else "gpt-6-astra"

    def fake_run(command: list[str], **_kwargs: Any):
        stdout = json.dumps({"models": [{"slug": slug, "tool_mode": "code_mode_only"}]})
        return mr.subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(mr.subprocess, "run", fake_run)
    attempt_dir = tmp_path / "attempt"
    attempt_dir.mkdir()
    expected = FileNotFoundError if failure == "missing_auth" else RuntimeError
    with pytest.raises(expected):
        _REAL_PREPARE_CODEX_ENVIRONMENT(
            codex_home=tmp_path / "isolated-home",
            attempt_dir=attempt_dir,
            model="gpt-6-astra",
            codex="codex-test",
        )
    assert not (attempt_dir / "codex-models.json").exists()


def _split_auth_link(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """A login whose isolated link a write-then-rename save has split."""
    main_home = tmp_path / "main-home"
    main_home.mkdir()
    main_auth = main_home / "auth.json"
    main_auth.write_text('{"refresh_token": "old"}', encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(main_home))
    home = tmp_path / "isolated-home"
    home.mkdir()
    linked = home / "auth.json"
    linked.hardlink_to(main_auth)
    staged = home / "auth.json.tmp"
    staged.write_text('{"refresh_token": "rotated"}', encoding="utf-8")
    os.replace(staged, linked)
    assert not linked.samefile(main_auth)
    return main_auth, linked


def test_relink_codex_auth_returns_a_refreshed_login_to_the_user(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    main_auth, linked = _split_auth_link(tmp_path, monkeypatch)
    os.utime(main_auth, ns=(1, 1))  # the user's file predates the refresh

    warning = _REAL_RELINK_CODEX_AUTH(linked.parent)

    assert warning is not None and "copied the refreshed login back" in warning
    assert main_auth.read_text(encoding="utf-8") == '{"refresh_token": "rotated"}'
    assert linked.samefile(main_auth)
    assert not list(main_auth.parent.glob("auth.json.*.tmp"))
    assert _REAL_RELINK_CODEX_AUTH(linked.parent) is None  # whole again


def test_relink_codex_auth_never_overwrites_a_newer_user_login(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    main_auth, linked = _split_auth_link(tmp_path, monkeypatch)
    os.utime(linked, ns=(1, 1))  # the user logged in again after the split

    warning = _REAL_RELINK_CODEX_AUTH(linked.parent)

    assert warning is not None and "copied" not in warning
    assert main_auth.read_text(encoding="utf-8") == '{"refresh_token": "old"}'
    assert linked.samefile(main_auth)


@pytest.fixture
def synthetic_prompt_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    guidelines = tmp_path / "guidelines.md"
    guidelines.write_text("Synthetic guidelines.\n", encoding="utf-8")
    templates = {
        kind: tmp_path / f"{kind}.md" for kind in ("part", "assembly")
    }
    contracts = {
        kind: tmp_path / f"{kind}_severity.md" for kind in ("part", "assembly")
    }
    judge_template = tmp_path / "judge.md"
    for path in (*templates.values(), judge_template):
        path.write_text(
            f"Synthetic introduction.\n{mr.SEVERITY_TOKEN}\nSynthetic conclusion.\n",
            encoding="utf-8",
        )
    for path in contracts.values():
        path.write_text("Synthetic contract.\n", encoding="utf-8")
    monkeypatch.setattr(mr, "GUIDELINES_FILE", guidelines)
    monkeypatch.setattr(mr, "PROMPT_FILES", templates)
    monkeypatch.setattr(mr, "JUDGE_PROMPT_FILE", judge_template)
    monkeypatch.setattr(mr, "SEVERITY_FILES", contracts)
    return SimpleNamespace(
        templates=templates, contracts=contracts, judge_template=judge_template
    )


@pytest.mark.parametrize("judge", [False, True], ids=["reviewer", "judge"])
def test_load_prompt_rejects_unsupported_kind(synthetic_prompt_sources, judge) -> None:
    with pytest.raises(ValueError):
        mr.load_prompt("unsupported", judge=judge)


@pytest.mark.parametrize("kind", ["part", "assembly"])
@pytest.mark.parametrize("judge", [False, True], ids=["reviewer", "judge"])
def test_load_prompt_rejects_missing_severity_contract(
    synthetic_prompt_sources, kind, judge
) -> None:
    synthetic_prompt_sources.contracts[kind].unlink()
    with pytest.raises(FileNotFoundError):
        mr.load_prompt(kind, judge=judge)


@pytest.mark.parametrize("kind", ["part", "assembly"])
@pytest.mark.parametrize("judge", [False, True], ids=["reviewer", "judge"])
@pytest.mark.parametrize("invalid", ["empty", "whitespace", "recursive"])
def test_load_prompt_rejects_invalid_severity_contract(
    synthetic_prompt_sources, kind, judge, invalid
) -> None:
    contents = {
        "empty": "",
        "whitespace": " \t\n\n",
        "recursive": f"Synthetic contract quoting {mr.SEVERITY_TOKEN} inline.\n",
    }
    synthetic_prompt_sources.contracts[kind].write_text(
        contents[invalid], encoding="utf-8"
    )
    with pytest.raises(ValueError):
        mr.load_prompt(kind, judge=judge)


@pytest.mark.parametrize("kind", ["part", "assembly"])
@pytest.mark.parametrize("judge", [False, True], ids=["reviewer", "judge"])
@pytest.mark.parametrize(
    "invalid",
    ["missing", "duplicate", "inline", "indented", "suffixed", "unterminated"],
)
def test_load_prompt_rejects_invalid_severity_template(
    synthetic_prompt_sources, kind, judge, invalid
) -> None:
    token = mr.SEVERITY_TOKEN
    contents = {
        "missing": "Synthetic template without an insertion point.\n",
        "duplicate": f"{token}\nSynthetic separator.\n{token}\n",
        "inline": f"Synthetic prefix {token} synthetic suffix.\n",
        "indented": f" {token}\n",
        "suffixed": f"{token} \n",
        "unterminated": token,
    }
    path = (
        synthetic_prompt_sources.judge_template
        if judge
        else synthetic_prompt_sources.templates[kind]
    )
    path.write_text(contents[invalid], encoding="utf-8")
    with pytest.raises(ValueError):
        mr.load_prompt(kind, judge=judge)


@pytest.mark.parametrize("kind", ["part", "assembly"])
@pytest.mark.parametrize("inline", [False, True], ids=["whole-line", "inline"])
def test_review_prompt_rejects_reserved_token_before_reading_sheet_text(
    monkeypatch: pytest.MonkeyPatch, kind, inline
) -> None:
    def forbidden_text_layers(_package):
        pytest.fail("an unresolved prompt reached sheet-text extraction")

    monkeypatch.setattr(mr, "_text_layers", forbidden_text_layers)
    override = (
        f"Synthetic override quoting {mr.SEVERITY_TOKEN} inline.\n"
        if inline
        else f"Synthetic override.\n{mr.SEVERITY_TOKEN}\n"
    )
    package = mr.ReviewPackage("synthetic", kind, ())
    with pytest.raises(ValueError):
        mr._review_prompt(package, 1, prompt_text=override)


@pytest.mark.parametrize("kind", ["part", "assembly"])
def test_review_prompt_allows_reserved_token_in_sheet_text(
    monkeypatch: pytest.MonkeyPatch, kind
) -> None:
    sheet_text = f'Synthetic sheet quotes "{mr.SEVERITY_TOKEN}" verbatim.'
    monkeypatch.setattr(mr, "_text_layers", lambda _package: sheet_text)
    package = mr.ReviewPackage("synthetic", kind, ())
    prompt = mr._review_prompt(package, 1, prompt_text="Opaque synthetic override.\n")
    assert sheet_text in prompt


def test_prompts_share_the_static_load_prompt_prefix_for_every_package() -> None:
    packages = [
        (mr.ReviewPackage("crank_arm", "part", ()), 1),
        (mr.ReviewPackage("pivot_shaft", "part", ()), 2),
        (mr.ReviewPackage("gearbox", "assembly", ()), 3),
        (mr.ReviewPackage("base_frame", "assembly", ()), 1),
    ]
    tails: dict[str, set[str]] = {}
    for package, sheet_count in packages:
        prefix = mr.load_prompt(package.kind)
        for reviewer in mr.REVIEWERS:
            prompt = mr._review_prompt(package, sheet_count, reviewer=reviewer)
            assert prompt.startswith(prefix)
            tail = prompt[len(prefix) :]
            assert "PACKAGE INPUT" in tail
            assert f"Sheet count: {sheet_count}" in tail
            assert f"view_sheet for sheets 1..{sheet_count}" in tail
            # Codex's resource helpers are neutral; the prompt still names the tools.
            lines = tail.splitlines()
            assert lines.count("Use only view_sheet and crop.") == 1
            view_line = next(i for i, line in enumerate(lines) if "view_sheet for sheets" in line)
            assert lines[view_line + 1] == "Use only view_sheet and crop."
            assert lines[-1] == "Return one verdict for the package as a whole."
            assert package.name not in tail
            tails.setdefault(package.kind, set()).add(tail)
    # The tail varies only with sheet count, never with name or reviewer.
    assert len(tails["part"]) == 2 and len(tails["assembly"]) == 2

    override = "custom rubric\n"
    package = mr.ReviewPackage("crank_arm", "part", ())
    assert mr._review_prompt(package, 2, prompt_text=override).startswith(override)


def test_text_layer_groups_by_view_and_drops_border_furniture(
    tmp_path: Path,
) -> None:
    source = _text_pdf(
        tmp_path / "sheet.pdf",
        [
            (100, 400, "FRONT 5:1"),
            (300, 300, "9.550"),
            (330, 312, "+0.03"),
            (330, 300, "0.00"),
            (300, 280, "REAM THRU"),
            (450, 50, "MATERIAL"),
            (450, 35, "SAE 1018 CF bar"),
            (10, 10, "SOLIDWORKS Maker Product. For Personal Use Only."),
        ],
    )
    with sheets.SheetStore([source]) as store:
        document = store.text_layer(1)
    assert document.startswith("Sheet text layer — sheet 1 of 1.")
    assert '== view "FRONT 5:1" ==' in document
    assert "9.550 +0.03/0.00" in document
    assert "REAM THRU" in document
    assert "== title block ==" in document
    assert "MATERIAL" in document and "SAE 1018 CF bar" in document
    assert "Maker Product" not in document
    # Rects are view_sheet pixels the reviewer can crop directly.
    assert re.search(r"\(\d+,\d+\)-\(\d+,\d+\)  9\.550", document)
    # Cached per store; PNG sources have no text layer.
    with sheets.SheetStore([source, _png_source(tmp_path / "blank.png")]) as store:
        assert store.text_layer(1).startswith("Sheet text layer — sheet 1 of 2.")
        assert store.text_layer(2) == ""
        assert "9.550 +0.03/0.00" in store.text_layer(1)


def test_review_prompt_injects_the_sheet_text_layer(tmp_path: Path) -> None:
    source = _text_pdf(
        tmp_path / "sheet.pdf",
        [(100, 400, "FRONT 5:1"), (300, 300, "25.20")],
    )
    package = mr.ReviewPackage("crank_arm", "part", (source,))
    prompt = mr._review_prompt(package, 1)
    assert "SHEET TEXT LAYER" in prompt
    assert "organized by sheet then view" in prompt
    assert '== view "FRONT 5:1" ==' in prompt and "25.20" in prompt
    lines = prompt.splitlines()
    assert lines[-1] == "Return one verdict for the package as a whole."
    # PNG-only packages get no text-layer section at all.
    png = mr.ReviewPackage("crank_arm", "part", (_png_source(tmp_path / "blank.png"),))
    png_prompt = mr._review_prompt(png, 1)
    assert "SHEET TEXT LAYER" not in png_prompt[len(mr.load_prompt("part")) :]


def test_prompts_define_the_classification_contract() -> None:
    for kind in ("part", "assembly"):
        prompt = re.sub(r"\s+", " ", mr.load_prompt(kind))
        assert "contradiction > missing > unbuildable > over_specification" in prompt
        assert "FIX if and only if blockers" in prompt
        assert 'never invent a hybrid category such as "minor clarity"' in prompt
        assert "the first that applies in this precedence" in prompt


# --- owner-declared machinist exceptions -------------------------------------


def _write_exceptions_config(root: Path, name: str, section: Any) -> Path:
    dashed = name.replace("_", "-")
    directory = root / "parts"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{dashed}.yaml"
    import yaml

    path.write_text(
        yaml.safe_dump({dashed: {"number": "MHA-XX-01", "machinist_exceptions": section}}),
        encoding="utf-8",
    )
    return path


def test_declared_exceptions_load_and_validate(tmp_path: Path) -> None:
    import machinist_exceptions

    section = [
        {
            "id": "RV-001",
            "where": "sheet 1, front view, 25.20 overall length",
            "finding": "tight clearance band with no named mate (rule 4)",
            "reason": "CLEARS callout names the mate; owner accepts it",
            "kind": "accept",
        }
    ]
    _write_exceptions_config(tmp_path, "dt_crank_hub", section)
    entries = machinist_exceptions.load_exceptions(tmp_path, "dt_crank_hub", "part")
    assert [entry.id for entry in entries] == ["RV-001"]
    assert entries[0].kind == "accept"
    # A package that declares nothing (or has no config file) gets nothing.
    assert machinist_exceptions.load_exceptions(tmp_path, "ms_stick", "part") == ()
    assert machinist_exceptions.load_exceptions(tmp_path, "pn_pen_assembly", "assembly") == ()
    # Malformed declarations fail loud: a typo must never silently widen
    # or narrow what the reviewer ignores.
    for bad in (
        [dict(section[0], kind="ignore")],
        [dict(section[0], reason="")],
        [dict(section[0], extra="x")],
        [section[0], section[0]],
    ):
        _write_exceptions_config(tmp_path, "dt_crank_hub", bad)
        with pytest.raises(ValueError):
            machinist_exceptions.load_exceptions(tmp_path, "dt_crank_hub", "part")


def test_assembly_declarations_load_from_the_assemblys_contract(tmp_path: Path) -> None:
    """The review names an assembly package by its drawing, ``<stem>_assembly``
    (BUILDING.md keeps the suffix); its declarations live at top level in the
    assembly's contract, ``assemblies/<stem>.yaml``, beside the build keys."""
    import yaml

    import machinist_exceptions

    entry = {
        "id": "RV-01",
        "where": "fit-up step 4, the set-screw engagement",
        "finding": "short thread engagement (rule 18)",
        "reason": "the arch is all the thread there is (owner-ruled shortfall)",
        "kind": "minor",
    }
    directory = tmp_path / "assemblies"
    directory.mkdir()
    (directory / "xx-bank.yaml").write_text(
        yaml.safe_dump(
            {
                "number": "MHA-XX-00",
                "flip_invert": [],
                "allowed_free_stems": [],
                "required_free_stems": [],
                "free_dof": 0,
                "machinist_exceptions": [entry],
            }
        ),
        encoding="utf-8",
    )
    load = machinist_exceptions.load_exceptions
    (loaded,) = load(tmp_path, "xx_bank_assembly", "assembly")
    assert (loaded.id, loaded.kind, loaded.where) == ("RV-01", "minor", entry["where"])
    # Parts are unchanged: their own key in parts/<name>.yaml, the name never
    # stripped, so an "-assembly" part name finds no file.
    _write_exceptions_config(tmp_path, "xx_bank", [dict(entry, id="RV-09")])
    assert [e.id for e in load(tmp_path, "xx_bank", "part")] == ["RV-09"]
    assert load(tmp_path, "xx_bank_assembly", "part") == ()


def test_review_prompt_injects_declared_exceptions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _text_pdf(tmp_path / "sheet.pdf", [(100, 400, "FRONT 5:1")])
    config_root = tmp_path / "config"
    _write_exceptions_config(
        config_root,
        "crank_arm",
        [
            {
                "id": "RV-007",
                "where": "sheet 1, bore",
                "finding": "REAM callout with no named mate (rule 4)",
                "reason": "mate named in the gear data block; accepted",
                "kind": "minor",
            }
        ],
    )
    monkeypatch.setattr(mr, "CAD_ROOT", tmp_path)
    package = mr.ReviewPackage("crank_arm", "part", (source,))
    prompt = mr._review_prompt(package, 1)
    assert "OWNER-DECLARED MACHINIST EXCEPTIONS" in prompt
    assert "RV-007 [minor] at sheet 1, bore" in prompt
    assert "the exception id in the summary" in prompt
    lines = prompt.splitlines()
    assert lines[-1] == "Return one verdict for the package as a whole."
    # Packages without sources never see config-derived exceptions, so the
    # static tail contract holds regardless of what configs declare.
    bare = mr.ReviewPackage("crank_arm", "part", ())
    assert "OWNER-DECLARED MACHINIST EXCEPTIONS" not in mr._review_prompt(bare, 1)


# --- blind evidence ----------------------------------------------------------


@pytest.mark.parametrize("reviewer", mr.REVIEWERS)
def test_evidence_accepts_in_range_views_and_crops(reviewer: str) -> None:
    events = [
        *_views(reviewer, (1, 2, 3)),
        *_call_events(reviewer, "crop", {"sheet": 2, "x1": 10, "y1": 20, "x2": 300, "y2": 400}, "crop_a"),
        *_call_events(reviewer, "crop", {"sheet": 2, "x1": 10, "y1": 20, "x2": 300, "y2": 400}, "crop_b"),
        # A crop the server refused still counts as an attempted crop call.
        *_call_events(reviewer, "crop", {"sheet": 3, "x1": 0, "y1": 0, "x2": 5, "y2": 5}, "crop_c", ok=False),
    ]
    if reviewer == "claude":
        events.append(_claude_tool_use("StructuredOutput", {}, "structured"))

    evidence = mr.evaluate_sheet_evidence(events, reviewer=reviewer, sheet_count=3)

    assert evidence == {
        "tool_events": 0,
        "sheets_viewed": [1, 2, 3],
        "crop_calls": 3,
        "crops": [
            {"sheet": 2, "rect": [10, 20, 300, 400]},
            {"sheet": 2, "rect": [10, 20, 300, 400]},
            {"sheet": 3, "rect": [0, 0, 5, 5]},
        ],
        "neutral_calls": [],
        "inspection_proven": True,
    }


_REJECTED_CALLS: dict[str, dict[str, list[dict[str, Any]]]] = {
    "claude": {
        "read": _claude_call("Read", {"file_path": "sheet-1.png"}, "bad"),
        "shell": _claude_call("Bash", {"command": "dir"}, "bad"),
        "unknown_sheets_tool": _claude_call("mcp__sheets__list_files", {}, "bad"),
        "unknown_server": _claude_call("mcp__files__view_sheet", {"sheet": 1}, "bad"),
    },
    "codex": {
        "read": [
            {
                "type": "item.completed",
                "item": {"id": "bad", "type": "tool_use", "name": "Read"},
            }
        ],
        "shell": [
            {
                "type": "item.started",
                "item": {"id": "bad", "type": "command_execution", "command": "type sheet.png"},
            },
            {
                "type": "item.completed",
                "item": {"id": "bad", "type": "command_execution", "command": "type sheet.png"},
            },
        ],
        # Code-mode cells reach every tool in ALL_TOOLS without their own item.
        "code_mode_exec": [
            {
                "type": "item.completed",
                "item": {
                    "id": "call_exec",
                    "type": "custom_tool_call",
                    "name": "exec",
                    "input": "const r = await tools.mcp__sheets__view_sheet({sheet:1});",
                },
            }
        ],
        "unknown_sheets_tool": _codex_call("list_files", {}, "bad"),
        "unknown_server": _codex_call("view_sheet", {"sheet": 1}, "bad", server="files"),
    },
}


@pytest.mark.parametrize(
    ("reviewer", "case"),
    [(reviewer, case) for reviewer, cases in _REJECTED_CALLS.items() for case in cases],
)
def test_evidence_rejects_every_tool_outside_the_sheet_server(
    reviewer: str, case: str
) -> None:
    events = [*_views(reviewer, (1, 2, 3)), *_REJECTED_CALLS[reviewer][case]]

    evidence = mr.evaluate_sheet_evidence(events, reviewer=reviewer, sheet_count=3)

    assert evidence["tool_events"] == 1
    assert evidence["sheets_viewed"] == [1, 2, 3]
    assert evidence["crop_calls"] == 0 and evidence["crops"] == []


# Malformed calls to a known sheet tool reach only the sheet server, which
# refuses them; they are failed inspections, never proof and never a leak.
_MALFORMED_VIEWS = {
    "below_range": {"sheet": 0},
    "above_range": {"sheet": 4},
    "string_sheet": {"sheet": "1"},
    "float_sheet": {"sheet": 2.0},
    "extra_key": {"sheet": 2, "zoom": 2},
    "not_an_object": "sheet 2",
}
_MALFORMED_CROPS: dict[str, tuple[Any, dict[str, Any]]] = {
    "above_range": (
        {"sheet": 4, "x1": 0, "y1": 0, "x2": 9, "y2": 9},
        {"sheet": 4, "rect": [0, 0, 9, 9]},
    ),
    "float_corner": (
        {"sheet": 1, "x1": 990.0, "y1": 0, "x2": 1920, "y2": 9},
        {"sheet": 1, "rect": [990.0, 0, 1920, 9]},
    ),
    "missing_corner": (
        {"sheet": 1, "x1": 0, "y1": 0, "x2": 9},
        {"sheet": 1, "rect": [0, 0, 9, None]},
    ),
    "not_an_object": ("crop sheet 1", {"sheet": None, "rect": [None] * 4}),
}


@pytest.mark.parametrize("reviewer", mr.REVIEWERS)
@pytest.mark.parametrize("case", sorted(_MALFORMED_VIEWS))
def test_malformed_view_is_authorized_but_never_proves_a_sheet(
    reviewer: str, case: str
) -> None:
    # The fake result even carries an image: invalid arguments still prove nothing.
    events = [
        *_views(reviewer, (1, 3)),
        *_call_events(reviewer, "view_sheet", _MALFORMED_VIEWS[case], "malformed"),
    ]

    evidence = mr.evaluate_sheet_evidence(events, reviewer=reviewer, sheet_count=3)

    assert evidence["tool_events"] == 0
    assert evidence["sheets_viewed"] == [1, 3]
    assert not evidence["inspection_proven"]


@pytest.mark.parametrize("reviewer", mr.REVIEWERS)
def test_every_named_crop_call_counts_once_with_its_raw_arguments(
    reviewer: str,
) -> None:
    events = _views(reviewer, (1, 2, 3))
    for case in sorted(_MALFORMED_CROPS):
        events += _call_events(reviewer, "crop", _MALFORMED_CROPS[case][0], case, ok=False)

    evidence = mr.evaluate_sheet_evidence(events, reviewer=reviewer, sheet_count=3)

    assert evidence["tool_events"] == 0
    assert evidence["inspection_proven"]
    # The server charges refused crops to the budget, so the record does too.
    assert evidence["crop_calls"] == len(_MALFORMED_CROPS)
    assert evidence["crops"] == [_MALFORMED_CROPS[case][1] for case in sorted(_MALFORMED_CROPS)]


@pytest.mark.parametrize(
    ("kind", "unauthorized"),
    [
        ("todo_list", 1),
        ("unrecognized_builtin", 1),
        ("agent_message", 0),
        ("reasoning", 0),
        ("error", 0),
    ],
)
def test_codex_item_gate_rejects_unmarked_tools(kind: str, unauthorized: int) -> None:
    item = {"id": "builtin", "type": kind, "items": []}
    evidence = mr.evaluate_sheet_evidence(
        [
            *_views("codex", (1,)),
            {"type": "item.started", "item": item},
            {"type": "item.completed", "item": item},
        ],
        reviewer="codex",
        sheet_count=1,
    )
    assert evidence["tool_events"] == unauthorized
    assert evidence["inspection_proven"]


def test_codex_started_and_completed_call_counts_once() -> None:
    crop = _codex_call("crop", {"sheet": 1, "x1": 0, "y1": 0, "x2": 9, "y2": 9}, "c")
    shell = _REJECTED_CALLS["codex"]["shell"]
    evidence = mr.evaluate_sheet_evidence(
        [*_views("codex", (1,)), *crop, *shell], reviewer="codex", sheet_count=1
    )
    assert evidence["crop_calls"] == 1
    assert evidence["tool_events"] == 1


@pytest.mark.parametrize("reviewer", mr.REVIEWERS)
def test_inspection_requires_a_successful_image_view_of_every_sheet(
    reviewer: str,
) -> None:
    def evaluate(events: list[dict[str, Any]]) -> dict[str, Any]:
        return mr.evaluate_sheet_evidence(events, reviewer=reviewer, sheet_count=3)

    assert evaluate(_views(reviewer, (3, 1, 2)))["inspection_proven"]

    missing = evaluate(_views(reviewer, (1, 3)))
    assert missing["sheets_viewed"] == [1, 3]
    assert missing["tool_events"] == 0
    assert not missing["inspection_proven"]

    failed = evaluate(
        [
            *_views(reviewer, (1, 3)),
            *_call_events(reviewer, "view_sheet", {"sheet": 2}, "failed", ok=False),
        ]
    )
    assert failed["sheets_viewed"] == [1, 3]
    assert not failed["inspection_proven"]

    unanswered = (
        [_claude_tool_use("mcp__sheets__view_sheet", {"sheet": 2}, "pending")]
        if reviewer == "claude"
        else _codex_call("view_sheet", {"sheet": 2}, "pending", status="in_progress")
    )
    started_only = evaluate([*_views(reviewer, (1, 3)), *unanswered])
    assert started_only["sheets_viewed"] == [1, 3]
    assert started_only["tool_events"] == 0
    assert not started_only["inspection_proven"]


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
    # The text-only grader has no sheets, so even the sheet server is a tool,
    # including calls whose arguments the server would refuse.
    assert mr.count_codex_tool_events(_views("codex", (1,))) == 1
    assert mr.count_codex_tool_events(_codex_call("view_sheet", {"sheet": 0}, "v")) == 1


_ROLLOUT_PROMPT = "# Drawing guidelines\n\nRule 1.\n\nPACKAGE INPUT\nSheet count: 2\n"
_ROLLOUT_THREAD = "01a13128-90e1-72d3-97c1-51bb37cf5996"


def _rollout_evidence(rows: list[dict[str, Any]], prompt: str = _ROLLOUT_PROMPT) -> dict[str, Any]:
    return mr.codex_rollout_evidence(rows, prompt)


def _rollout(**kwargs: Any) -> list[dict[str, Any]]:
    return _codex_rollout(
        _ROLLOUT_PROMPT, thread_id=_ROLLOUT_THREAD, cwd=r"C:\attempt", **kwargs
    )


@pytest.mark.parametrize("newline", ["\r\n", "\n"])
def test_rollout_evidence_normalizes_direct_sheet_calls(newline: str) -> None:
    crop = {"sheet": 2, "x1": 990, "y1": 970, "x2": 1920, "y2": 1225}
    result = _rollout_evidence(_rollout(views=(1, 2), crops=[crop], newline=newline))

    assert result["context_errors"] == []
    assert result["first_turn_usage"]["input_tokens"] == _FIRST_REQUEST_USAGE["input_tokens"]
    assert result["first_turn_usage"]["cached_input_tokens"] == (
        _FIRST_REQUEST_USAGE["cached_input_tokens"]
    )
    items = [event["item"] for event in result["events"]]
    assert {item["type"] for item in items} == {"mcp_tool_call"}
    assert {item["id"] for item in items} == {"call_view_1", "call_view_2", "call_crop_1"}
    assert mr.evaluate_sheet_evidence(result["events"], reviewer="codex", sheet_count=2) == {
        "tool_events": 0,
        "sheets_viewed": [1, 2],
        "crop_calls": 1,
        "crops": [{"sheet": 2, "rect": [990, 970, 1920, 1225]}],
        "neutral_calls": [],
        "inspection_proven": True,
    }


def test_rollout_evidence_keeps_failed_and_malformed_sheet_calls_non_proving() -> None:
    rows = _rollout(views=(1,))
    final = len(rows) - 2
    rows[final:final] = [
        *_rollout_call(_ROLLOUT_THREAD, "view_sheet", {"sheet": 2}, "call_failed", ok=False),
        *_rollout_call(_ROLLOUT_THREAD, "view_sheet", {"sheet": 2.0}, "call_float"),
    ]
    result = _rollout_evidence(rows)

    assert result["context_errors"] == []
    evidence = mr.evaluate_sheet_evidence(result["events"], reviewer="codex", sheet_count=2)
    assert evidence["tool_events"] == 0
    assert evidence["sheets_viewed"] == [1]
    assert not evidence["inspection_proven"]


@pytest.mark.parametrize(
    "cell",
    [
        # Rollout 01a13102 line 11: tool discovery, no MCP item at all.
        'text(ALL_TOOLS.filter(x => /view_sheet|crop/i.test(x.name+" "+x.description)));\n',
        # Line 15: a sheet view routed through the code-mode sandbox.
        "const r = await tools.mcp__sheets__view_sheet({sheet:1}); image(r.content[0]);\n",
    ],
)
def test_rollout_evidence_exposes_code_mode_exec_cells(cell: str) -> None:
    result = _rollout_evidence(_rollout(views=(1, 2), after=_rollout_exec_cell("call_exec", cell)))

    exec_items = [
        event["item"] for event in result["events"]
        if event["item"]["type"] == "custom_tool_call"
    ]
    assert exec_items and all(item["name"] == "exec" for item in exec_items)
    evidence = mr.evaluate_sheet_evidence(result["events"], reviewer="codex", sheet_count=2)
    assert evidence["tool_events"] == 1
    # The same cell was invisible to the --json gate the harness used to trust.
    stdout_events = _codex_events(2, _ROLLOUT_THREAD)
    assert mr.evaluate_sheet_evidence(stdout_events, reviewer="codex", sheet_count=2)[
        "tool_events"
    ] == 0


def _rollout_foreign_call(
    thread_id: str,
    name: str,
    call_id: str,
    output: str,
    *,
    completion: bool,
    arguments: dict[str, Any] | None = None,
    native: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Codex builtins (smoke codex-b rollout 01a1313b, ordinals 36-43): no namespace.

    ``list_mcp_resources`` was recorded again in final-smoke rollout 01a13147
    (ordinals 21/22/24): declaration ``{}``, native item under server "codex"
    with the same text, then the identical model-visible output string.
    """
    arguments = {} if arguments is None else arguments
    rows = [
        _rollout_row(
            "response_item",
            {
                "type": "function_call",
                "id": f"fc_{call_id}",
                "name": name,
                "arguments": json.dumps(arguments, separators=(",", ":")),
                "call_id": call_id,
            },
        )
    ]
    if completion:
        # The CLI's own MCP surface reports the builtin under server "codex".
        rows.append(
            _rollout_row(
                "event_msg",
                {
                    "type": "item_completed",
                    "thread_id": thread_id,
                    "turn_id": "turn_1",
                    "item": {
                        "type": "McpToolCall",
                        "id": call_id,
                        "server": "codex",
                        "tool": name,
                        "arguments": arguments,
                        "status": "completed",
                        "result": {"content": [{"type": "text", "text": output}], "isError": False},
                        **(native or {}),
                    },
                },
            )
        )
    rows.append(
        _rollout_row(
            "response_item",
            {"type": "function_call_output", "id": f"fco_{call_id}", "call_id": call_id, "output": output},
        )
    )
    return rows


# Codex resource helpers (core/src/tools/handlers/mcp_resource): the native item
# names args.server, else "codex"; list payloads echo a named server and omit
# an absent nextCursor; a resources/read failure leaves result None and the
# message as both the native error and the model-visible output; a read
# without "server" fails argument parsing before any native item is emitted.
_MISSING_RESOURCE = "resources/read failed: Mcp error: 0: Unknown resource: sheets://1"
_RESOURCE_PARSE_ERROR = "failed to parse function arguments: missing field `server`"
_FAILED_READ = {"status": "failed", "result": None, "error": {"message": _MISSING_RESOURCE}}
_SHEETS_NATIVE = {"server": "sheets"}


def _resource_case(
    name: str,
    arguments: dict[str, Any],
    output: str,
    *,
    completion: bool = True,
    native: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name, "arguments": arguments, "output": output,
        "completion": completion, "native": native,
    }


def _resource_rows(
    case: dict[str, Any], call_id: str = "call_resource", *, thread_id: str = _ROLLOUT_THREAD
) -> list[dict[str, Any]]:
    return _rollout_foreign_call(
        thread_id, case["name"], call_id, case["output"],
        completion=case["completion"], arguments=case["arguments"], native=case["native"],
    )


# Empty catalogue answers from a sole ``sheets`` server: discovery, not inspection.
_NEUTRAL_RESOURCE_CASES: dict[str, dict[str, Any]] = {
    "list": _resource_case("list_mcp_resources", {}, '{"resources":[]}'),
    "list_sheets": _resource_case(
        "list_mcp_resources", {"server": "sheets"}, '{"server":"sheets","resources":[]}',
        native=_SHEETS_NATIVE,
    ),
    "list_templates": _resource_case("list_mcp_resource_templates", {}, '{"resourceTemplates":[]}'),
    "list_templates_sheets": _resource_case(
        "list_mcp_resource_templates", {"server": "sheets"},
        '{"server":"sheets","resourceTemplates":[]}', native=_SHEETS_NATIVE,
    ),
    "read_sheets": _resource_case(
        "read_mcp_resource", {"server": "sheets", "uri": "sheets://1"}, _MISSING_RESOURCE,
        native={**_FAILED_READ, **_SHEETS_NATIVE},
    ),
    "read_unspecified": _resource_case(
        "read_mcp_resource", {"uri": "sheets://1"}, _RESOURCE_PARSE_ERROR, completion=False
    ),
}


def _neutral_rollout(
    rows: list[dict[str, Any]], *, sheet_count: int = 2
) -> tuple[dict[str, Any], dict[str, Any]]:
    result = mr.codex_rollout_evidence(rows, _ROLLOUT_PROMPT, neutral_resources=True)
    evidence = mr.evaluate_sheet_evidence(
        result["events"], reviewer="codex", sheet_count=sheet_count, neutral_resources=True
    )
    return result, evidence


@pytest.mark.parametrize(
    ("name", "output", "completion"),
    [
        ("list_mcp_resources", '{"resources":[]}', True),
        ("list_mcp_resource_templates", '{"resourceTemplates":[]}', True),
        ("get_goal", '{"goal":null,"remainingTokens":null,"completionBudgetReport":null}', False),
    ],
)
def test_rollout_evidence_forbids_foreign_builtin_calls_even_with_empty_results(
    name: str, output: str, completion: bool
) -> None:
    # Default strictness: without the harness's sole-sheets permission nothing is neutral.
    foreign = _rollout_foreign_call(_ROLLOUT_THREAD, name, "call_foreign", output, completion=completion)
    result = _rollout_evidence(_rollout(views=(1, 2), after=foreign))

    evidence = mr.evaluate_sheet_evidence(result["events"], reviewer="codex", sheet_count=2)
    assert evidence["tool_events"] >= 1  # no empty-result whitelist
    assert evidence["sheets_viewed"] == [1, 2]
    assert evidence["neutral_calls"] == []
    # A builtin is not a sheet call, so lacking server/tool fields is no disagreement.
    assert not any("disagree" in error for error in result["context_errors"])


@pytest.mark.parametrize("case", sorted(_NEUTRAL_RESOURCE_CASES))
def test_neutral_resource_call_is_recorded_once_but_never_proves_a_view(case: str) -> None:
    spec = _NEUTRAL_RESOURCE_CASES[case]
    rows = _rollout(views=(1,), after=_resource_rows(spec))

    strict = _rollout_evidence(rows)
    strict_evidence = mr.evaluate_sheet_evidence(strict["events"], reviewer="codex", sheet_count=2)
    assert strict_evidence["tool_events"] >= 1  # default stays fail-closed

    result, evidence = _neutral_rollout(rows)
    assert result["context_errors"] == []
    # Declaration and native completion share one call id: one normalized call.
    resource_items = [
        event["item"] for event in result["events"] if event["item"].get("id") == "call_resource"
    ]
    assert len(resource_items) == 1
    assert evidence["neutral_calls"] == [{"tool": spec["name"], "arguments": spec["arguments"]}]
    assert evidence["tool_events"] == 0
    assert evidence["sheets_viewed"] == [1]  # sheets://1 or not, only view_sheet proves
    assert not evidence["inspection_proven"]
    assert evidence["crop_calls"] == 0 and evidence["crops"] == []
    # Opt-in is per caller: the evaluator default and the text-only grader stay strict.
    assert mr.evaluate_sheet_evidence(result["events"], reviewer="codex", sheet_count=2)[
        "tool_events"
    ] >= 1
    assert mr.count_codex_tool_events(result["events"]) >= 1


def test_every_neutral_resource_call_counts_once_beside_complete_inspection() -> None:
    after = [
        row
        for index, case in enumerate(sorted(_NEUTRAL_RESOURCE_CASES))
        for row in _resource_rows(_NEUTRAL_RESOURCE_CASES[case], f"call_resource_{index}")
    ]
    result, evidence = _neutral_rollout(_rollout(views=(1, 2), after=after))

    assert result["context_errors"] == []
    assert evidence["tool_events"] == 0
    assert evidence["sheets_viewed"] == [1, 2] and evidence["inspection_proven"]
    assert evidence["neutral_calls"] == [
        {"tool": spec["name"], "arguments": spec["arguments"]}
        for spec in (_NEUTRAL_RESOURCE_CASES[case] for case in sorted(_NEUTRAL_RESOURCE_CASES))
    ]


_NONEMPTY_RESOURCE_CASES: dict[str, dict[str, Any]] = {
    "list_entries": _resource_case(
        "list_mcp_resources", {},
        '{"resources":[{"server":"sheets","uri":"sheets://1","name":"sheet-1"}]}',
    ),
    "list_next_cursor": _resource_case(
        "list_mcp_resources", {}, '{"resources":[],"nextCursor":"2"}'
    ),
    "list_template_entries": _resource_case(
        "list_mcp_resource_templates", {},
        '{"resourceTemplates":[{"server":"sheets","uriTemplate":"sheets://{sheet}","name":"sheet"}]}',
    ),
    "read_content": _resource_case(
        "read_mcp_resource", {"server": "sheets", "uri": "sheets://1"},
        '{"server":"sheets","uri":"sheets://1","contents":'
        '[{"uri":"sheets://1","mimeType":"text/plain","text":"Rule 1: ship it."}]}',
        native=_SHEETS_NATIVE,
    ),
}
_FOREIGN_RESOURCE_CASES: dict[str, list[dict[str, Any]]] = {
    "read_other_server": _resource_rows(
        _resource_case(
            "read_mcp_resource", {"server": "files", "uri": "file:///C:/drawing.pdf"},
            "resources/read failed: unknown MCP server 'files'",
            native={**_FAILED_READ, "server": "files"},
        )
    ),
    "get_goal": _rollout_foreign_call(
        _ROLLOUT_THREAD, "get_goal", "call_resource",
        '{"goal":null,"remainingTokens":null,"completionBudgetReport":null}', completion=False,
    ),
    "exec": _rollout_exec_cell("call_resource", "text(await tools.list_mcp_resources({}));\n"),
}
_MISMATCHED_RESOURCE_CASES: dict[str, list[dict[str, Any]]] = {
    # The model declared a neutral helper; the CLI executed something else.
    "native_tool": _resource_rows(
        _resource_case(
            "list_mcp_resources", {}, '{"resources":[]}', native={"tool": "get_goal"}
        )
    ),
    "native_server": _resource_rows(
        _resource_case(
            "list_mcp_resources", {}, '{"resources":[]}', native={"server": "files"}
        )
    ),
    # A native "sheets" item is the CLI's own record only of a sheets-targeted call.
    "native_sheets_untargeted": _resource_rows(
        _resource_case(
            "list_mcp_resources", {}, '{"resources":[]}', native=_SHEETS_NATIVE
        )
    ),
}


@pytest.mark.parametrize("case", sorted(_NONEMPTY_RESOURCE_CASES))
def test_neutral_mode_rejects_resource_output_beyond_the_empty_manifest(case: str) -> None:
    rows = _rollout(views=(1, 2), after=_resource_rows(_NONEMPTY_RESOURCE_CASES[case]))
    result, evidence = _neutral_rollout(rows)

    assert any("resource" in error for error in result["context_errors"])
    assert evidence["sheets_viewed"] == [1, 2]


@pytest.mark.parametrize("case", sorted(_FOREIGN_RESOURCE_CASES))
def test_neutral_mode_still_forbids_foreign_tools_and_read_targets(case: str) -> None:
    result, evidence = _neutral_rollout(_rollout(views=(1, 2), after=_FOREIGN_RESOURCE_CASES[case]))

    assert evidence["tool_events"] >= 1
    assert evidence["neutral_calls"] == []
    assert evidence["sheets_viewed"] == [1, 2]


@pytest.mark.parametrize("case", sorted(_MISMATCHED_RESOURCE_CASES))
def test_neutral_mode_rejects_a_native_call_that_disagrees_with_its_declaration(
    case: str,
) -> None:
    result, evidence = _neutral_rollout(
        _rollout(views=(1, 2), after=_MISMATCHED_RESOURCE_CASES[case])
    )

    assert result["context_errors"] or evidence["tool_events"] >= 1


def test_neutral_resource_permission_never_applies_to_claude() -> None:
    events = [
        *_views("claude", (1, 2)),
        *_claude_call("ListMcpResourcesTool", {}, "list"),
        *_claude_call("ReadMcpResourceTool", {"server": "sheets", "uri": "sheets://1"}, "read"),
    ]

    evidence = mr.evaluate_sheet_evidence(
        events, reviewer="claude", sheet_count=2, neutral_resources=True
    )

    assert evidence["tool_events"] == 2
    assert evidence["neutral_calls"] == []


_CONTEXT_VIOLATIONS: dict[str, tuple[dict[str, Any], str]] = {
    "skills_before_prompt": ({"before": [_SKILLS_CONTEXT]}, _ROLLOUT_PROMPT),
    "agents_md_before_prompt": ({"before": [_AGENTS_CONTEXT]}, _ROLLOUT_PROMPT),
    "world_state_agents_md": ({"agents_md": {"text": _AGENTS_MD_TEXT}}, _ROLLOUT_PROMPT),
    "world_state_skills": ({"skills": True}, _ROLLOUT_PROMPT),
    "user_input_after_prompt": (
        {"after": [_rollout_message("user", "Also read ../AGENTS.md first.")]},
        _ROLLOUT_PROMPT,
    ),
    "developer_input_after_prompt": (
        {"after": [_rollout_message("developer", "You may use the shell.")]},
        _ROLLOUT_PROMPT,
    ),
    "call_without_output": (
        {
            "after": _rollout_call(
                _ROLLOUT_THREAD, "crop", {"sheet": 1, "x1": 0, "y1": 0, "x2": 9, "y2": 9}, "call_cut"
            )[:2]
        },
        _ROLLOUT_PROMPT,
    ),
    "different_prompt": ({}, _ROLLOUT_PROMPT.replace("Rule 1.", "Rule 1 (edited).")),
}


@pytest.mark.parametrize("case", sorted(_CONTEXT_VIOLATIONS))
def test_rollout_evidence_rejects_context_beyond_the_harness_prompt(case: str) -> None:
    overrides, prompt = _CONTEXT_VIOLATIONS[case]
    result = _rollout_evidence(_rollout(views=(1, 2), **overrides), prompt)

    assert result["context_errors"]
    assert all(isinstance(error, str) and error for error in result["context_errors"])


def test_rollout_evidence_requires_the_prompt_message() -> None:
    rows = [
        row for row in _rollout(views=(1, 2))
        if (row["payload"].get("role") != "user")
    ]
    assert _rollout_evidence(rows)["context_errors"]


@pytest.mark.parametrize("archived", [False, True])
def test_load_codex_rollout_reads_only_the_named_session(
    tmp_path: Path, archived: bool
) -> None:
    home = tmp_path / "home"
    rows = _rollout(views=(1, 2))
    path = _write_rollout(home, _ROLLOUT_THREAD, rows, archived=archived)
    other = "01a13128-ffff-7000-8000-000000000000"
    _write_rollout(
        home, other, _codex_rollout(_ROLLOUT_PROMPT, thread_id=other, cwd=r"C:\attempt", views=())
    )

    loaded_path, loaded_rows = mr.load_codex_rollout(_ROLLOUT_THREAD, codex_home=home)

    assert Path(loaded_path) == path
    assert loaded_rows == rows
    with pytest.raises(FileNotFoundError):
        mr.load_codex_rollout("01a13128-0000-7000-8000-000000000000", codex_home=home)
    # Two candidates cannot be told apart; neither is authoritative.
    _write_rollout(home, other, _rollout(views=()), archived=True)
    with pytest.raises(ValueError):
        mr.load_codex_rollout(other, codex_home=home)
    with pytest.raises(ValueError):
        mr.load_codex_rollout("*", codex_home=home)  # never a glob


def test_usage_parsing_for_both_reviewers() -> None:
    claude_events = [
        {
            "type": "assistant",
            "message": {
                "content": [{"type": "tool_use", "id": "t", "name": "mcp__sheets__view_sheet", "input": {"sheet": 1}}],
                "usage": {
                    "input_tokens": 2,
                    "cache_creation_input_tokens": 6274,
                    "cache_read_input_tokens": 0,
                    "output_tokens": 32,
                },
            },
        },
        {
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "done"}],
                "usage": {
                    "input_tokens": 2,
                    "cache_creation_input_tokens": 3491,
                    "cache_read_input_tokens": 6274,
                    "output_tokens": 7,
                },
            },
        },
        {
            "type": "result",
            "subtype": "success",
            "num_turns": 2,
            "total_cost_usd": 0.0807108,
            "usage": {
                "input_tokens": 4,
                "cache_creation_input_tokens": 9765,
                "cache_read_input_tokens": 6274,
                "output_tokens": 66,
                "service_tier": "standard",
            },
        },
    ]
    usage = mr._usage(claude_events, "claude")
    assert {key: usage[key] for key in (
        "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
        "output_tokens", "num_turns",
    )} == {
        "input_tokens": 4,
        "cache_creation_input_tokens": 9765,
        "cache_read_input_tokens": 6274,
        "output_tokens": 66,
        "num_turns": 2,
    }
    assert usage["total_cost_usd"] == pytest.approx(0.0807108)
    assert usage["first_turn"] == {
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 6274,
    }

    codex_events = [
        {"type": "thread.started", "thread_id": "01a130f2-307e-7c22-b936-5b65caa165d4"},
        {"type": "turn.completed", "usage": {
            "input_tokens": 41015, "cached_input_tokens": 25856,
            "cache_write_input_tokens": 0, "output_tokens": 112,
            "reasoning_output_tokens": 0,
        }},
        {"type": "turn.completed", "usage": {
            "input_tokens": 1000, "cached_input_tokens": 900, "output_tokens": 50,
        }},
    ]
    # Codex's --json stream has no per-request split; the rollout supplies it.
    first_request = {
        "input_tokens": 22232, "cached_input_tokens": 0,
        "cache_write_input_tokens": 0, "output_tokens": 66,
        "reasoning_output_tokens": 0, "total_tokens": 22298,
    }
    usage = mr._usage(codex_events, "codex", first_turn_usage=first_request)
    assert {key: usage[key] for key in (
        "input_tokens", "cached_input_tokens", "output_tokens"
    )} == {"input_tokens": 42015, "cached_input_tokens": 26756, "output_tokens": 162}
    assert usage["first_turn"]["input_tokens"] == 22232
    assert usage["first_turn"]["cached_input_tokens"] == 0


def _claude_turn(cache_read: int, cache_creation: int) -> dict[str, Any]:
    return {
        "type": "assistant",
        "message": {
            "content": [{"type": "text", "text": "turn"}],
            "usage": {
                "input_tokens": 1,
                "cache_creation_input_tokens": cache_creation,
                "cache_read_input_tokens": cache_read,
                "output_tokens": 1,
            },
        },
    }


def _claude_result(input_tokens: int, cost: float, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "type": "result",
        "is_error": is_error,
        "num_turns": 1,
        "total_cost_usd": cost,
        "usage": {
            "input_tokens": input_tokens,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "output_tokens": 0,
        },
    }


def test_usage_bills_every_attempt_but_first_turn_is_the_verdict_attempt() -> None:
    failed = [_claude_turn(0, 20000), _claude_result(5, 0.10, is_error=True)]
    succeeded = [_claude_turn(19000, 1000), _claude_result(7, 0.02)]
    events = [*mr._tag_events(1, failed), *mr._tag_events(2, succeeded)]

    usage = mr._usage(events, "claude", success_events=mr._tag_events(2, succeeded))

    assert usage["input_tokens"] == 12
    assert usage["num_turns"] == 2
    assert usage["total_cost_usd"] == pytest.approx(0.12)
    # A retry must not report the failed attempt's cold-cache first turn.
    assert usage["first_turn"] == {
        "cache_read_input_tokens": 19000,
        "cache_creation_input_tokens": 1000,
    }


def _review(reviewer: str, extra: dict[str, Any]) -> mr.Review:
    return mr.Review(
        name="dt_crank_arm",
        kind="part",
        sources=["x.png"],
        source_sha256=["b" * 64],
        verdict=_clean_verdict(),
        passed=True,
        blind=True,
        tool_events=0,
        reviewer=reviewer,
        model="model",
        effort="low",
        prompt_sha256="a" * 64,
        sheet_count=1,
        duration_s=1.0,
        reviewed_at="now",
        extra=extra,
    )


@pytest.mark.parametrize(
    ("reviewer", "crop_calls", "usage", "share"),
    [
        (
            "claude",
            3,
            {
                "input_tokens": 4,
                "cache_creation_input_tokens": 9765,
                "cache_read_input_tokens": 6274,
                "output_tokens": 66,
                "total_cost_usd": 0.08,
                "num_turns": 2,
                "first_turn": {"cache_read_input_tokens": 0, "cache_creation_input_tokens": 6274},
            },
            "39.1%",  # 6274 / (4 + 6274 + 9765)
        ),
        (
            "codex",
            2,
            {"input_tokens": 41015, "cached_input_tokens": 25856, "output_tokens": 112},
            "63.0%",  # 25856 / 41015
        ),
        (
            "codex",
            0,
            {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0},
            "0.0%",
        ),
    ],
)
def test_markdown_reports_crop_count_and_cache_read_share(
    reviewer: str, crop_calls: int, usage: dict[str, Any], share: str
) -> None:
    markdown = mr.render_markdown(
        _review(reviewer, {"crop_calls": crop_calls, "usage": usage})
    )
    assert f", crops {crop_calls}, cache-read {share}" in markdown


# --- review runs -------------------------------------------------------------


@pytest.mark.parametrize("reviewer", mr.REVIEWERS)
def test_attempt_dir_is_the_cwd_then_retained_without_sheet_images(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_codex: SimpleNamespace,
    reviewer: str,
) -> None:
    sources = (
        _pdf_source(tmp_path / "drawing.pdf", [(144, 72), (72, 144)]),
        _png_source(tmp_path / "detail.png"),
    )
    report_dir = tmp_path / "reports"
    seen: dict[str, Any] = {}

    def fake_run(command: list[str], **kwargs: Any):
        cwd = Path(kwargs["cwd"])
        seen["cwd"] = cwd
        # Every input the CLI may see sits in its own fresh attempt dir.
        seen["files"] = sorted(path.name for path in cwd.rglob("*"))
        seen["command"] = command
        if reviewer == "claude":
            config_path = cwd / _flag(command, "--mcp-config")
            seen["config"] = json.loads(config_path.read_text(encoding="utf-8"))
            return mr.subprocess.CompletedProcess(
                command, 0, stdout=_claude_stdout(3, _clean_verdict()), stderr=""
            )
        assert Path(_flag(command, "-C")) == cwd
        assert Path(_flag(command, "-o")).parent == cwd
        seen["overrides"] = _codex_overrides(command)
        reply = _codex_reply(command, kwargs, sheet_count=3)
        seen["rollout"] = next(
            (isolated_codex.home / "sessions").rglob("rollout-*.jsonl")
        ).read_text(encoding="utf-8")
        return reply

    monkeypatch.setattr(mr, "_run_reviewer", fake_run)
    package = mr.ReviewPackage("package", "assembly", sources)
    review = mr.review_package(
        package, reviewer=reviewer, report_dir=report_dir, retries=0, codex="codex-test",
    )

    assert review.passed and review.blind
    assert review.sheet_count == 3
    assert review.extra["sheets_viewed"] == [1, 2, 3]
    assert review.extra["inspection_proven"] is True
    assert review.extra["crop_calls"] == 0 and review.extra["crops"] == []
    assert review.extra["context_errors"] == []
    assert review.extra["neutral_calls"] == []
    # The real SDK catalogue of these exact sources, recorded for both reviewers.
    assert review.extra["evidence"]["mcp_catalog"] == {
        "servers": ["sheets"], "resources": 0, "resource_templates": 0,
    }
    attempt_dir = seen["cwd"]
    assert not attempt_dir.is_relative_to(report_dir)
    assert not attempt_dir.is_relative_to(mr.CAD_ROOT.parent)
    assert not isolated_codex.home.is_relative_to(attempt_dir)
    expected_inputs = (
        {"schema.json", "mcp.json"} if reviewer == "claude"
        else {"schema.json", "codex-models.json"}
    )
    assert set(seen["files"]) == expected_inputs  # no sheet PNGs, no stray context
    # The MCP server reads the review's immutable source snapshot, never the
    # mutable originals.
    server_sources = [
        str((report_dir / "package.sources" / source.name).resolve()) for source in sources
    ]
    if reviewer == "claude":
        assert seen["config"] == {
            "mcpServers": {
                "sheets": {
                    "command": sys.executable,
                    "args": [str(mr.SHEETS_SERVER), *server_sources],
                }
            }
        }
    else:
        assert seen["overrides"]["mcp_servers.sheets.args"] == [
            str(mr.SHEETS_SERVER),
            *server_sources,
        ]

    saved_text = (report_dir / "package.json").read_text(encoding="utf-8")
    saved = json.loads(saved_text)
    (record,) = saved["extra"]["evidence"]["attempts"]
    assert record["cwd"] == record["attempt_dir"]
    assert Path(record["attempt_dir"]) == attempt_dir
    assert not attempt_dir.exists()
    assert record["retention_warning"] is None
    retained = Path(record["retained_dir"])
    assert retained.is_dir()
    assert retained.parent == report_dir / "package.attempts"
    assert retained.name == attempt_dir.name and retained.name.startswith("machrev-")
    assert expected_inputs <= {path.name for path in retained.iterdir()}
    assert not list(retained.rglob("*.png"))
    assert Path(record["stdout_file"]).parent == retained
    assert record["sources"] == server_sources
    # Inspection argv only: retained paths substituted, provenance stays in command.
    argv = record["retained_argv"]
    assert record["command"] == seen["command"]
    assert len(argv) == len(record["command"])
    assert not any(str(attempt_dir) in argument for argument in argv)
    if reviewer == "claude":
        assert record["codex_home"] is None and record["rollout_file"] is None
        assert Path(_flag(argv, "--mcp-config")) == retained / "mcp.json"
        assert record["artifacts"] == []
    else:
        assert record["codex_home"] == str(mr.CODEX_HOME)
        assert Path(record["rollout_file"]) == retained / "rollout.jsonl"
        assert [json.loads(line) for line in seen["rollout"].splitlines()] == [
            json.loads(line)
            for line in Path(record["rollout_file"]).read_text(encoding="utf-8").splitlines()
        ]
        assert Path(_flag(argv, "-C")) == retained  # cwd was the attempt dir
        assert Path(_flag(argv, "-o")) == retained / "verdict.json"
        assert Path(_flag(argv, "--output-schema")) == retained / "schema.json"
        assert Path(_codex_overrides(argv)["model_catalog_json"]) == retained / "codex-models.json"
        assert [Path(path) for path in record["artifacts"]] == [
            retained / "codex-models.json",
            retained / "verdict.json",
        ]
    # The linked login never reaches a report or retained attempt.
    assert _AUTH_SENTINEL not in saved_text
    assert not any(
        _AUTH_SENTINEL in path.read_text(encoding="utf-8", errors="replace")
        for path in report_dir.rglob("*") if path.is_file()
    )


def test_attempt_records_carry_session_id_and_resume_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _png_source(tmp_path / "page.png")
    verdict = _clean_verdict()
    thread_id = "0199c0de-1234-4abc-9def-0123456789ab"
    calls = 0

    def fake_run(command: list[str], **kwargs: Any):
        nonlocal calls
        calls += 1
        if command[0] == "codex-test":
            return _codex_reply(
                command, kwargs, sheet_count=1, verdict=verdict, thread_id=thread_id
            )
        if calls == 1:
            return mr.subprocess.CompletedProcess(command, 1, stdout="", stderr="failed")
        actual = _flag(command, "--session-id")
        kwargs["transport_provenance"].update(transport="claude_agent_sdk", session_id=actual)
        stdout = _claude_stdout(1, verdict)
        return mr.subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(mr, "_run_reviewer", fake_run)
    package = mr.ReviewPackage("package", "part", (source,))
    mr.review_package(
        package, reviewer="claude", report_dir=tmp_path / "claude", retries=1,
    )
    mr.review_package(
        package,
        reviewer="codex",
        report_dir=tmp_path / "codex",
        retries=0,
        codex="codex-test",
    )

    def attempts(report_dir: Path) -> list[dict[str, Any]]:
        data = json.loads((report_dir / "package.json").read_text(encoding="utf-8"))
        return data["extra"]["evidence"]["attempts"]

    claude_attempts = attempts(tmp_path / "claude")
    assert [record["reviewer"] for record in claude_attempts] == ["claude", "claude"]
    claude_ids = [record["command"][record["command"].index("--session-id") + 1] for record in claude_attempts]
    assert len(set(claude_ids)) == 2  # fresh session per attempt: no prior context
    assert claude_attempts[0]["session_id"] is None  # Failed launch announced no conversation.
    assert claude_attempts[1]["session_id"] == claude_ids[1]
    for record, session_id in zip(claude_attempts, claude_ids):
        assert uuid.UUID(session_id).version == 4
        command = record["command"]
        assert command[command.index("--session-id") + 1] == session_id
        assert record["resume_command"] is None  # Lifecycle-owned native state is not a CLI replay.

    codex_attempt = attempts(tmp_path / "codex")[0]
    assert codex_attempt["reviewer"] == "codex"
    assert codex_attempt["session_id"] == thread_id
    assert codex_attempt["resume_command"] == f"codex resume {thread_id}"


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
        {**clean, "summary": ""},
        {**clean, "blockers": {}},
        {**clean, "minor": ["not an object"]},
        {**clean, "minor": [{"where": "x", "issue": "y"}]},
        {**clean, "minor": [{"where": "", "issue": "y", "fix": "z"}]},
    ]
    for value in invalid:
        with pytest.raises(ValueError):
            mr.validate_verdict(value)
        assert not mr.is_pass(value)


def test_retry_persists_all_attempts_and_cannot_hide_tool_use(
    tmp_path: Path, monkeypatch
) -> None:
    import subprocess

    png = _png_source(tmp_path / "source.png")
    verdict = _clean_verdict()
    calls = 0

    def fake_run(command, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            event = {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": "dir"},
                        }
                    ]
                },
            }
            return subprocess.CompletedProcess(
                command, 1, stdout=json.dumps(event), stderr="failed"
            )
        return subprocess.CompletedProcess(
            command, 0, stdout=_claude_stdout(1, verdict), stderr=""
        )

    monkeypatch.setattr(mr, "_run_reviewer", fake_run)
    report_dir = tmp_path / "reports"
    review = mr.review_package(
        mr.ReviewPackage("part", "part", (png,)),
        reviewer="claude", report_dir=report_dir, retries=1,
    )
    assert review.attempts == 2
    assert review.tool_events == 1
    # The successful attempt inspected every sheet; only the hidden tool fails it.
    assert review.extra["sheets_viewed"] == [1]
    assert not review.blind
    assert not review.passed
    records = [
        json.loads(line)
        for line in (report_dir / "part.events.jsonl").read_text().splitlines()
    ]
    assert records[0]["attempt"] == 1
    assert {record["attempt"] for record in records} == {1, 2}


@pytest.mark.parametrize("failure", ["nonzero_exit", "invalid_verdict", "timeout"])
def test_retry_retains_failure_outputs_and_artifacts_after_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_codex: SimpleNamespace,
    failure: str,
) -> None:
    png = _png_source(tmp_path / "source.png")
    report_dir = tmp_path / "reports"
    calls = 0
    failed_thread = "01a13128-aaaa-7000-8000-000000000001"
    success_thread = "01a13128-bbbb-7000-8000-000000000002"
    failed_stdout = (
        "diagnostic before JSON\n"
        f'{{"type": "thread.started", "thread_id": "{failed_thread}"}}\n'
        '{"type": "turn.failed"}\n'
    )
    failed_stderr = "reviewer diagnostic: interrupted response\n"
    invalid_verdict = "incomplete response, not JSON"
    success_events = _codex_events(1, success_thread)
    replies: list[Any] = []

    def fake_run(command: list[str], **kwargs: Any):
        nonlocal calls
        calls += 1
        if calls > 1:
            replies.append(
                _codex_reply(command, kwargs, sheet_count=1, thread_id=success_thread)
            )
            return replies[-1]
        output = Path(_flag(command, "-o"))
        # A started session always leaves an authoritative (here: tool-free) rollout.
        _write_rollout(
            Path(kwargs["env"]["CODEX_HOME"]),
            failed_thread,
            _codex_rollout(kwargs["input"], thread_id=failed_thread, cwd=str(kwargs["cwd"]), views=()),
        )
        output.write_text(invalid_verdict, encoding="utf-8")
        session = output.parent / "session"
        session.mkdir()
        (session / "trace.txt").write_text("failed attempt trace", encoding="utf-8")
        if failure == "timeout":
            raise mr.subprocess.TimeoutExpired(
                command,
                kwargs["timeout"],
                output=failed_stdout.encode("utf-8"),
                stderr=failed_stderr.encode("utf-8"),
            )
        return mr.subprocess.CompletedProcess(
            command,
            17 if failure == "nonzero_exit" else 0,
            stdout=failed_stdout,
            stderr=failed_stderr,
        )

    monkeypatch.setattr(mr, "_run_reviewer", fake_run)
    review = mr.review_package(
        mr.ReviewPackage("part", "part", (png,)),
        reviewer="codex",
        report_dir=report_dir,
        retries=1,
        codex="codex-test",
    )

    assert review.passed and review.blind
    assert review.error is None
    assert review.extra["context_errors"] == []
    saved = json.loads((report_dir / "part.json").read_text(encoding="utf-8"))
    failed, succeeded = saved["extra"]["evidence"]["attempts"]
    assert failed["outcome"] == ("timed_out" if failure == "timeout" else "failed")
    assert (
        failed["exit_code"]
        == {
            "nonzero_exit": 17,
            "invalid_verdict": 0,
            "timeout": None,
        }[failure]
    )
    assert {
        "nonzero_exit": "codex exit 17: reviewer diagnostic: interrupted response",
        "invalid_verdict": "final message is not JSON",
        "timeout": "TimeoutExpired",
    }[failure] in failed["error"]
    assert failed["session_id"] == failed_thread
    assert Path(failed["stdout_file"]).read_text(encoding="utf-8") == failed_stdout
    assert Path(failed["stderr_file"]).read_text(encoding="utf-8") == failed_stderr
    artifacts = {Path(path).name: Path(path) for path in failed["artifacts"]}
    assert set(artifacts) == {"codex-models.json", "session", "verdict.json"}
    assert artifacts["verdict.json"].read_text(encoding="utf-8") == invalid_verdict
    assert (artifacts["session"] / "trace.txt").read_text(encoding="utf-8") == (
        "failed attempt trace"
    )
    assert succeeded["outcome"] == "succeeded"
    assert succeeded["error"] is None
    assert succeeded["exit_code"] == 0
    assert Path(succeeded["stdout_file"]).read_text(encoding="utf-8") == replies[0].stdout
    assert Path(succeeded["stderr_file"]).read_bytes() == b""
    success_artifacts = {Path(path).name: Path(path) for path in succeeded["artifacts"]}
    assert set(success_artifacts) == {"codex-models.json", "verdict.json"}
    assert json.loads(
        success_artifacts["verdict.json"].read_text(encoding="utf-8")
    ) == (_clean_verdict())
    assert failed["retained_dir"] != succeeded["retained_dir"]
    assert failed["attempt_dir"] != succeeded["attempt_dir"]
    for record in (failed, succeeded):
        assert not Path(record["attempt_dir"]).exists()
        assert record["retention_warning"] is None
        retained = Path(record["retained_dir"])
        assert retained.is_dir() and retained.is_relative_to(report_dir)
        for path in (
            record["stdout_file"],
            record["stderr_file"],
            record["rollout_file"],
            *record["artifacts"],
        ):
            assert Path(path).parent == retained
            assert Path(path).exists()
    # events.jsonl keeps the CLI's own --json stream; the rollouts sit beside it.
    events = [
        json.loads(line)
        for line in Path(review.events_file).read_text(encoding="utf-8").splitlines()
    ]
    assert events == [
        {"attempt": 1, "event": {"type": "thread.started", "thread_id": failed_thread}},
        {"attempt": 1, "event": {"type": "turn.failed"}},
        *({"attempt": 2, "event": event} for event in success_events),
    ]


def test_retry_requires_sheet_views_from_the_successful_attempt(
    tmp_path: Path, monkeypatch
) -> None:
    png = _png_source(tmp_path / "source.png")
    verdict = _clean_verdict()
    calls = 0

    def fake_run(command, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            stdout = "\n".join(json.dumps(event) for event in _views("claude", (1,)))
            return mr.subprocess.CompletedProcess(
                command, 1, stdout=stdout, stderr="failed"
            )
        result = {"type": "result", "structured_output": verdict}
        return mr.subprocess.CompletedProcess(
            command, 0, stdout=json.dumps(result), stderr=""
        )

    monkeypatch.setattr(mr, "_run_reviewer", fake_run)
    review = mr.review_package(
        mr.ReviewPackage("part", "part", (png,)),
        reviewer="claude", report_dir=tmp_path / "reports", retries=1,
    )

    assert review.attempts == 2
    assert review.tool_events == 0
    assert review.extra["sheets_viewed"] == []
    assert review.extra["inspection_proven"] is False
    assert not review.blind
    assert not review.passed


def test_both_structured_verdict_parsers(tmp_path: Path) -> None:
    verdict = _clean_verdict()
    assert (
        mr.extract_claude_verdict([{"type": "result", "structured_output": verdict}])
        == verdict
    )

    output = tmp_path / "verdict.json"
    output.write_text(json.dumps(verdict), encoding="utf-8")
    assert mr.extract_codex_verdict(output, []) == verdict


def test_arbitrary_png_reports_with_same_basename_do_not_collide(
    tmp_path: Path, monkeypatch
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    verdict = _clean_verdict()

    def fake_run(command, **kwargs):
        return _codex_reply(command, kwargs, sheet_count=1, verdict=verdict)

    monkeypatch.setattr(mr, "_run_reviewer", fake_run)
    inputs = [tmp_path / "left" / "part.png", tmp_path / "right" / "part.png"]
    for index, image in enumerate(inputs):
        image.parent.mkdir()
        _png_source(image, (10 + index, 10))
    packages = [mr._package_for_pngs([image], "part") for image in inputs]
    assert packages[0].name != packages[1].name

    report_dir = tmp_path / "reports"
    with ThreadPoolExecutor(max_workers=2) as pool:
        reviews = list(
            pool.map(
                lambda package: mr.review_package(
                    package,
                    reviewer="codex",
                    report_dir=report_dir,
                    retries=0,
                    codex="codex-test",
                ),
                packages,
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


def test_multi_sheet_assembly_is_one_cross_sheet_review(
    tmp_path: Path, monkeypatch
) -> None:
    from pypdf import PdfWriter

    source = tmp_path / "assembly.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_blank_page(width=72, height=72)
    with source.open("wb") as stream:
        writer.write(stream)
    verdict = {
        "verdict": "SHIP",
        "summary": "BOM conflict remains",
        "blockers": [],
        "over_specification": [],
        "clarity": [
            {
                "where": "sheets 1 and 2",
                "issue": "balloon 4 maps to conflicting BOM rows",
                "fix": "make item 4 consistent across the package",
            }
        ],
        "minor": [],
    }
    captured: list[tuple[list[str], str]] = []

    def fake_run(command, **kwargs):
        assert not list(Path(kwargs["cwd"]).rglob("*.png"))
        captured.append((command, kwargs["input"]))
        return _codex_reply(command, kwargs, sheet_count=2, verdict=verdict)

    monkeypatch.setattr(mr, "_run_reviewer", fake_run)
    package = mr.ReviewPackage("gearbox", "assembly", (source,))
    review = mr.review_package(
        package,
        reviewer="codex",
        report_dir=tmp_path / "reports",
        retries=0,
        codex="codex-test",
    )

    assert review.error is None
    assert review.verdict == verdict
    assert len(captured) == 1
    command, prompt = captured[0]
    assert _codex_overrides(command)["mcp_servers.sheets.args"][1:] == [
        str((tmp_path / "reports" / "gearbox.sources" / source.name).resolve())
    ]
    assert "Sheet count: 2" in prompt
    assert review.sheet_count == 2
    assert review.extra["sheets_viewed"] == [1, 2]
    assert review.blind
    assert review.sources == [str(source)]
    assert len(review.source_sha256) == 1
    assert not review.passed


def test_registry_part_pdf_reviews_every_page(tmp_path: Path, monkeypatch) -> None:
    import hashlib
    from types import SimpleNamespace

    from pypdf import PdfWriter

    source = tmp_path / "part.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=144)
    writer.add_blank_page(width=144, height=72)
    with source.open("wb") as stream:
        writer.write(stream)
    monkeypatch.setitem(
        mr.DRAWINGS_BY_NAME,
        "two-sheet-part",
        SimpleNamespace(source_kind="part", outputs={"pdf": source}),
    )
    prompts = []
    verdict = _clean_verdict("FIX")
    verdict["blockers"] = [
        {
            "where": "sheets 1 and 2, bore",
            "issue": "conflicting bore diameters",
            "fix": "specify one consistent bore diameter",
        }
    ]

    def fake_run(command, **kwargs):
        assert kwargs["input"].startswith(mr.load_prompt("part"))
        prompts.append(kwargs["input"])
        return _codex_reply(command, kwargs, sheet_count=2, verdict=verdict)

    monkeypatch.setattr(mr, "_run_reviewer", fake_run)
    report_dir = tmp_path / "reports"
    review = mr.review_package(
        mr.package_for("two-sheet-part"),
        reviewer="codex",
        report_dir=report_dir,
        retries=0,
        codex="codex-test",
    )

    assert review.error is None
    assert review.kind == "part"
    assert review.sheet_count == 2
    assert review.blind
    assert review.sources == [str(source)]
    assert review.source_sha256 == [hashlib.sha256(source.read_bytes()).hexdigest()]
    assert (
        review.prompt_sha256 == hashlib.sha256(prompts[0].encode("utf-8")).hexdigest()
    )
    assert review.verdict == verdict
    assert not review.passed
    saved = json.loads((report_dir / "two-sheet-part.json").read_text(encoding="utf-8"))
    assert saved["sheet_count"] == 2
    assert saved["source_sha256"] == review.source_sha256


def test_explicit_part_png_package_accepts_multiple_sheets(tmp_path: Path) -> None:
    sources = (
        _png_source(tmp_path / "part-a.png", (40, 20)),
        _png_source(tmp_path / "part-b.png", (20, 40)),
    )
    package = mr._package_for_pngs(sources, "part")
    assert mr._validate_package(package) == 2
    with sheets.SheetStore(package.sources) as store:
        assert store.sheet_count == 2
        # Whole-sheet PNG views only ever downscale; small originals stay native.
        assert [store.view_size(sheet) for sheet in (1, 2)] == [(40, 20), (20, 40)]
        assert _image(store.view_sheet(1)[0]).size == (40, 20)


@pytest.mark.parametrize("contents", [b"", b"not a PDF"])
def test_part_pdf_rejects_unreadable_input(tmp_path: Path, contents: bytes) -> None:
    import pypdfium2 as pdfium

    source = tmp_path / "part.pdf"
    source.write_bytes(contents)
    with pytest.raises(pdfium.PdfiumError):
        mr._validate_package(mr.ReviewPackage("part", "part", (source,)))


def test_part_pdf_rejects_package_without_sheets(tmp_path: Path) -> None:
    import pypdfium2 as pdfium
    from pypdf import PdfWriter

    with pytest.raises(ValueError):
        mr._validate_package(mr.ReviewPackage("part", "part", ()))
    source = tmp_path / "empty.pdf"
    with source.open("wb") as stream:
        PdfWriter().write(stream)
    with pytest.raises((ValueError, pdfium.PdfiumError)):
        mr._validate_package(mr.ReviewPackage("part", "part", (source,)))


def test_part_package_rejects_missing_source_and_unsupported_kind_or_extension(
    tmp_path: Path,
) -> None:
    source = tmp_path / "missing.pdf"
    with pytest.raises(FileNotFoundError):
        mr._validate_package(mr.ReviewPackage("part", "part", (source,)))
    with pytest.raises(ValueError):
        mr._validate_package(mr.ReviewPackage("part", "unknown", (source,)))
    source = tmp_path / "part.txt"
    source.write_text("not a drawing", encoding="utf-8")
    with pytest.raises(ValueError):
        mr._validate_package(mr.ReviewPackage("part", "part", (source,)))


def test_write_index_creates_missing_report_directory(tmp_path: Path) -> None:
    report_dir = tmp_path / "missing" / "nested"

    index = mr.write_index(report_dir)

    assert index == report_dir / "index.md"
    assert index.is_file()
    assert "0/0 packages pass" in index.read_text(encoding="utf-8")


def test_write_index_fails_closed_on_stale_report(tmp_path: Path) -> None:
    stale = tmp_path / "stale.json"
    stale.write_text('{"name": "old-shape"}', encoding="utf-8")

    with pytest.raises(ValueError, match=r"invalid review report .*stale\.json"):
        mr.write_index(tmp_path)


def test_review_serialises_and_indexes(tmp_path: Path) -> None:
    verdict = {
        "verdict": "FIX",
        "summary": "over-toleranced",
        "blockers": [],
        "over_specification": [
            {"where": "front view", "issue": "datum B", "fix": "drop"}
        ],
        "clarity": [],
        "minor": [],
    }
    review = mr.Review(
        name="dt_crank_arm",
        kind="part",
        sources=["x.png"],
        source_sha256=["b" * 64],
        verdict=verdict,
        passed=mr.is_pass(verdict),
        blind=True,
        tool_events=0,
        reviewer="codex",
        model="gpt-5.6-sol",
        effort="high",
        prompt_sha256="a" * 64,
        sheet_count=1,
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
    markdown = (tmp_path / "dt_crank_arm.md").read_text(encoding="utf-8")
    assert "by codex/gpt-5.6-sol (high)" in markdown
    index = mr.render_index(loaded)
    expected = (
        "| [dt_crank_arm](dt_crank_arm.md) | part | 1 | FAIL | FIX | 0 | 1 | 0 | 0 | yes |"
    )
    assert expected in index
    data = json.loads((tmp_path / "dt_crank_arm.json").read_text())
    assert data["name"] == "dt_crank_arm"
    assert data["sources"] == ["x.png"]


def test_main_distinguishes_missing_and_unknown_names(capsys) -> None:
    assert mr.main(["--force"]) == 2
    assert capsys.readouterr().err == (
        "no drawing names given; use --all, --pdf or a name\n"
    )

    assert mr.main(["--reviewer", "codex", "--force"]) == 2
    assert capsys.readouterr().err == (
        "no drawing names given; use --all, --pdf or a name\n"
    )

    assert mr.main(["--reviewer", "codex", "not-a-drawing", "--force"]) == 2
    assert capsys.readouterr().err == "unknown drawing names: ['not-a-drawing']\n"


def test_both_reviewers_receive_one_complete_package_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    verdict = _clean_verdict()
    sources = (
        _png_source(tmp_path / "page-a.png"),
        _png_source(tmp_path / "page-b.png"),
    )
    commands: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: Any):
        commands.append(command)
        if command[0] == "codex-test":
            return _codex_reply(command, kwargs, sheet_count=2, verdict=verdict)
        stdout = _claude_stdout(2, verdict)
        return mr.subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(mr, "_run_reviewer", fake_run)
    package = mr.ReviewPackage("package", "assembly", sources)
    claude_review = mr.review_package(
        package, reviewer="claude", report_dir=tmp_path / "claude", retries=0,
    )
    codex_review = mr.review_package(
        package,
        reviewer="codex",
        report_dir=tmp_path / "codex",
        retries=0,
        codex="codex-test",
    )

    assert (claude_review.model, claude_review.effort) == ("claude-opus-5-5", "medium")
    assert (codex_review.model, codex_review.effort) == ("gpt-6-astra", "low")
    assert claude_review.blind and codex_review.blind
    assert claude_review.passed and codex_review.passed
    assert claude_review.extra["sheets_viewed"] == [1, 2]
    assert codex_review.extra["sheets_viewed"] == [1, 2]
    assert len(commands) == 2
    assert "-i" not in commands[1]


def _codex_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replies: Sequence[Any],
    *,
    sheet_count: int = 2,
    retries: int = 0,
) -> Any:
    """Run one Codex review whose invocations are answered by ``replies`` in order."""
    sources = tuple(
        _png_source(tmp_path / f"page-{index}.png") for index in range(1, sheet_count + 1)
    )
    pending = list(replies)

    def fake_run(command: list[str], **kwargs: Any):
        return pending.pop(0)(command, kwargs)

    monkeypatch.setattr(mr, "_run_reviewer", fake_run)
    review = mr.review_package(
        mr.ReviewPackage("package", "assembly", sources),
        reviewer="codex",
        report_dir=tmp_path / "reports",
        retries=retries,
        codex="codex-test",
    )
    assert pending == []
    return review


def test_codex_rollout_overrides_a_clean_json_stream_with_hidden_exec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def reply(command: list[str], kwargs: dict[str, Any]):
        # --json shows two clean views; the rollout also holds a code-mode cell.
        cell = _rollout_exec_cell("call_exec", 'text(await tools.shell({"command": "dir"}))')
        return _codex_reply(command, kwargs, sheet_count=2, after=cell)

    review = _codex_review(tmp_path, monkeypatch, [reply])

    assert review.tool_events >= 1
    assert not review.blind and not review.passed


@pytest.mark.parametrize(
    "injection",
    [
        {"before": [_SKILLS_CONTEXT]},
        {"before": [_AGENTS_CONTEXT]},
        {"agents_md": {"text": _AGENTS_MD_TEXT}},
        {"skills": True},
    ],
    ids=["skills_message", "agents_message", "world_state_agents_md", "world_state_skills"],
)
def test_codex_rollout_context_beyond_the_prompt_is_never_blind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, injection: dict[str, Any]
) -> None:
    def reply(command: list[str], kwargs: dict[str, Any]):
        return _codex_reply(command, kwargs, sheet_count=2, **injection)

    review = _codex_review(tmp_path, monkeypatch, [reply])

    assert review.extra["context_errors"]
    assert not review.blind and not review.passed
    assert review.extra["sheets_viewed"] == []


def test_codex_views_are_proven_by_the_rollout_not_the_json_stream(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def reply(command: list[str], kwargs: dict[str, Any]):
        # --json claims both sheets; the authoritative rollout shows only sheet 1.
        return _codex_reply(command, kwargs, sheet_count=2, rollout_views=(1,))

    review = _codex_review(tmp_path, monkeypatch, [reply])

    assert review.extra["context_errors"] == []
    assert review.extra["sheets_viewed"] == [1]
    assert review.extra["inspection_proven"] is False
    assert not review.blind and not review.passed


def _neutral_reply(
    *cases: str, rollout_views: Sequence[int] | None = None, exit_code: int = 0
) -> Any:
    """A Codex attempt that also used neutral resource helpers in its own session."""
    thread_id = str(uuid.uuid4())
    after = [
        row
        for index, case in enumerate(cases)
        for row in _resource_rows(
            _NEUTRAL_RESOURCE_CASES[case], f"call_resource_{index}", thread_id=thread_id
        )
    ]

    def reply(command: list[str], kwargs: dict[str, Any]):
        completed = _codex_reply(
            command, kwargs, sheet_count=2, thread_id=thread_id,
            rollout_views=rollout_views, after=after,
        )
        completed.returncode = exit_code
        return completed

    return reply


def _neutral_entries(*cases: str) -> list[dict[str, Any]]:
    return [
        {"tool": _NEUTRAL_RESOURCE_CASES[case]["name"],
         "arguments": _NEUTRAL_RESOURCE_CASES[case]["arguments"]}
        for case in cases
    ]


def test_codex_review_records_neutral_resource_calls_across_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    replies = [
        _neutral_reply("list", exit_code=1),
        _neutral_reply("list_templates_sheets", "read_sheets", "read_unspecified"),
    ]
    review = _codex_review(tmp_path, monkeypatch, replies, retries=1)

    assert review.attempts == 2 and review.error is None
    assert review.extra["context_errors"] == []
    assert review.tool_events == 0
    assert review.blind and review.passed
    assert review.extra["sheets_viewed"] == [1, 2]
    assert review.extra["neutral_calls"] == _neutral_entries(
        "list", "list_templates_sheets", "read_sheets", "read_unspecified"
    )
    assert review.extra["evidence"]["mcp_catalog"] == {
        "servers": ["sheets"], "resources": 0, "resource_templates": 0,
    }


def test_codex_neutral_resource_calls_never_stand_in_for_views(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reply = _neutral_reply("read_sheets", "list", rollout_views=(1,))
    review = _codex_review(tmp_path, monkeypatch, [reply])

    assert review.tool_events == 0 and review.extra["context_errors"] == []
    assert review.extra["neutral_calls"] == _neutral_entries("read_sheets", "list")
    assert review.extra["sheets_viewed"] == [1]
    assert review.extra["inspection_proven"] is False
    assert not review.blind and not review.passed


@pytest.mark.parametrize(
    "after",
    [
        _FOREIGN_RESOURCE_CASES["read_other_server"],
        _FOREIGN_RESOURCE_CASES["get_goal"],
        _resource_rows(_NONEMPTY_RESOURCE_CASES["list_entries"]),
        _resource_rows(_NONEMPTY_RESOURCE_CASES["read_content"]),
    ],
    ids=["read_other_server", "get_goal", "list_entries", "read_content"],
)
def test_codex_review_neutral_permission_stays_scoped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, after: list[dict[str, Any]]
) -> None:
    def reply(command: list[str], kwargs: dict[str, Any]):
        return _codex_reply(
            command, kwargs, sheet_count=2, thread_id=_ROLLOUT_THREAD, after=after
        )

    review = _codex_review(tmp_path, monkeypatch, [reply])

    assert review.tool_events >= 1 or review.extra["context_errors"]
    assert not review.blind and not review.passed


@pytest.mark.parametrize("retries", [0, 1])
def test_codex_missing_rollout_after_session_start_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retries: int
) -> None:
    def missing(command: list[str], kwargs: dict[str, Any]):
        return _codex_reply(command, kwargs, sheet_count=2, rollout=False)

    def complete(command: list[str], kwargs: dict[str, Any]):
        return _codex_reply(command, kwargs, sheet_count=2)

    replies = [missing, complete][: retries + 1]
    review = _codex_review(tmp_path, monkeypatch, replies, retries=retries)

    records = review.extra["evidence"]["attempts"]
    assert review.attempts == len(records) == retries + 1
    assert records[0]["outcome"] == "failed"
    assert records[0]["session_id"] and records[0]["rollout_file"] is None
    assert Path(records[0]["stdout_file"]).exists()
    # An unverifiable session is a context failure, never a provider blackout.
    assert any(error.startswith("attempt 1:") for error in review.extra["context_errors"])
    assert not review.blind and not review.passed
    if retries:
        assert records[1]["outcome"] == "succeeded"
        assert review.error is None
        assert review.extra["sheets_viewed"] == [1, 2]
    else:
        assert review.error is not None
        assert review.extra["sheets_viewed"] == []


@pytest.mark.parametrize("reviewer", mr.REVIEWERS)
def test_provider_failures_stay_blind_but_never_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reviewer: str
) -> None:
    def fake_run(command: list[str], **kwargs: Any):
        if reviewer == "claude":
            event = {"type": "result", "is_error": True, "result": "quota exhausted"}
            return mr.subprocess.CompletedProcess(
                command, 1, stdout=json.dumps(event), stderr=""
            )
        # The provider refused before any session existed: nothing to audit.
        return mr.subprocess.CompletedProcess(command, 1, stdout="", stderr="quota exhausted")

    monkeypatch.setattr(mr, "_run_reviewer", fake_run)
    review = mr.review_package(
        mr.ReviewPackage("package", "part", (_png_source(tmp_path / "page.png"),)),
        reviewer=reviewer, report_dir=tmp_path / "reports", retries=1, codex="codex-test",
    )

    assert review.attempts == 2
    assert "quota exhausted" in review.error
    assert review.tool_events == 0 and review.extra["context_errors"] == []
    assert review.extra["neutral_calls"] == []
    assert review.blind and not review.passed
    assert review.verdict is None
    row = next(line for line in mr.render_index([review]).splitlines() if "[package]" in line)
    cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
    assert cells[3:5] == ["FAIL", "ERROR"]
    assert cells[-2] == "yes"  # blind; the last column is the review time


def test_retention_falls_back_to_copy_when_windows_holds_the_attempt_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_rmtree = shutil.rmtree
    held: list[Path] = []
    calls = 0

    def held_move(source: str, destination: str) -> None:
        raise PermissionError(13, "The process cannot access the file", source)

    def held_rmtree(path: Any, *args: Any, **kwargs: Any) -> None:
        if any(Path(path) == attempt for attempt in held):
            raise PermissionError(32, "being used by another process", str(path))
        real_rmtree(path, *args, **kwargs)

    def fake_run(command: list[str], **kwargs: Any):
        nonlocal calls
        calls += 1
        held.append(Path(kwargs["cwd"]))
        if calls == 1:
            return mr.subprocess.CompletedProcess(command, 3, stdout="partial", stderr="crashed")
        return mr.subprocess.CompletedProcess(
            command, 0, stdout=_claude_stdout(1, _clean_verdict()), stderr=""
        )

    monkeypatch.setattr(mr.shutil, "move", held_move)
    monkeypatch.setattr(mr.shutil, "rmtree", held_rmtree)
    monkeypatch.setattr(mr, "_run_reviewer", fake_run)
    report_dir = tmp_path / "reports"
    try:
        review = mr.review_package(
            mr.ReviewPackage("package", "part", (_png_source(tmp_path / "page.png"),)),
            reviewer="claude", report_dir=report_dir, retries=1,
        )
    finally:
        for attempt in held:
            real_rmtree(attempt, ignore_errors=True)

    # A locked original costs a warning, never the report or the retry.
    assert review.attempts == 2 and review.passed
    assert Path(review.events_file).exists()
    assert (report_dir / "package.json").exists()
    records = review.extra["evidence"]["attempts"]
    assert [record["outcome"] for record in records] == ["failed", "succeeded"]
    for record, attempt in zip(records, held, strict=True):
        assert record["attempt_dir"] == str(attempt)
        assert "PermissionError" in record["retention_warning"]
        retained = Path(record["retained_dir"])
        assert retained.is_dir() and retained.is_relative_to(report_dir)
        assert (retained / "mcp.json").exists()
        assert Path(record["stdout_file"]).parent == retained
        assert Path(record["stderr_file"]).exists()
    assert Path(records[0]["stderr_file"]).read_text(encoding="utf-8") == "crashed"


# --- sheet server --------------------------------------------------------------


def test_views_are_deterministic_grayscale_fits_for_pdf_and_png(
    tmp_path: Path,
) -> None:
    sources = [
        _pdf_source(tmp_path / "landscape.pdf", [(792, 612), (792, 612)]),
        _pdf_source(tmp_path / "portrait.pdf", [(612, 792)]),
        _png_source(tmp_path / "wide.png", (3000, 2000), squares=[(10, 10, 50, 50)]),
        # Transparent PNG with DPI metadata: composited, metadata stripped.
        _png_source(tmp_path / "tall.png", (1500, 2400), mode="RGBA", dpi=(150, 150)),
    ]
    source_sizes = [(792, 612), (792, 612), (612, 792), (3000, 2000), (1500, 2400)]
    box_width, box_height = sheets.VIEW_BOX

    with sheets.SheetStore(sources) as first, sheets.SheetStore(sources) as second:
        assert first.sheet_count == len(source_sizes)  # PDF pages expand in order
        for sheet, (width, height) in enumerate(source_sizes, start=1):
            png, text = first.view_sheet(sheet)
            image = _image(png)
            assert image.mode == "L"
            assert image.size == first.view_size(sheet)
            view_width, view_height = image.size
            assert view_width <= box_width and view_height <= box_height
            assert view_width >= box_width - 1 or view_height >= box_height - 1
            assert view_width == pytest.approx(view_height * width / height, abs=1.5)
            assert set(_png_chunk_types(png)) <= {"IHDR", "IDAT", "IEND"}
            assert text.startswith(
                f"sheet {sheet} of {len(source_sizes)}, {view_width}×{view_height} px"
            )
            assert second.view_sheet(sheet) == (png, text)  # fresh store, same bytes
            assert first.view_sheet(sheet)[0] == png
        with pytest.raises(ValueError):
            first.view_sheet(0)
        with pytest.raises(ValueError):
            first.view_sheet(len(source_sizes) + 1)


@pytest.mark.parametrize("kind", ["pdf", "png"])
def test_crop_maps_top_left_view_pixels_to_the_source_region(
    tmp_path: Path, kind: str
) -> None:
    if kind == "pdf":
        size, square, window = (1000, 800), (600, 200, 700, 300), (560, 160, 740, 340)
        source = _pdf_source(tmp_path / "square.pdf", [size], squares=[square])
    else:
        size, square, window = (3000, 2000), (1800, 600, 2100, 900), (1700, 500, 2200, 1000)
        source = _png_source(tmp_path / "square.png", size, squares=[square])
    box_width, box_height = sheets.VIEW_BOX

    with sheets.SheetStore([source]) as store:
        view_width, view_height = store.view_size(1)
        scale = view_width / size[0]
        assert view_height == pytest.approx(size[1] * scale, abs=1)
        view = _image(store.view_sheet(1)[0])
        assert _dark_bbox(view) == pytest.approx(
            tuple(value * scale for value in square), abs=3
        )

        rect = [round(value * scale) for value in window]
        png, text = store.crop(1, *rect)
        crop = _image(png)
        assert crop.mode == "L"
        assert set(_png_chunk_types(png)) <= {"IHDR", "IDAT", "IEND"}
        rect_width, rect_height = rect[2] - rect[0], rect[3] - rect[1]
        magnification = min(
            sheets.MAX_SCALE, box_width / rect_width, box_height / rect_height
        )
        assert crop.size == pytest.approx(
            (rect_width * magnification, rect_height * magnification), abs=2
        )
        expected = (
            (square[0] * scale - rect[0]) / rect_width * crop.width,
            (square[1] * scale - rect[1]) / rect_height * crop.height,
            (square[2] * scale - rect[0]) / rect_width * crop.width,
            (square[3] * scale - rect[1]) / rect_height * crop.height,
        )
        assert _dark_bbox(crop) == pytest.approx(
            expected, abs=0.015 * max(crop.size) + 2
        )
        assert text.startswith(f"sheet 1, rect {tuple(rect)}, {crop.width}×{crop.height} px")
        assert "effective dpi" in text

        # A bottom-left origin would put the square in the mirrored window.
        mirrored = (window[0], size[1] - window[3], window[2], size[1] - window[1])
        mirrored_rect = [round(value * scale) for value in mirrored]
        assert _dark_bbox(_image(store.crop(1, *mirrored_rect)[0])) is None

        # Magnification is capped: a 20-pixel region is at most 8x, not box-filling.
        x, y = round(square[0] * scale), round(square[1] * scale)
        tiny = _image(store.crop(1, x, y, x + 20, y + 20)[0])
        assert max(tiny.size) <= 20 * sheets.MAX_SCALE
        assert min(tiny.size) >= 20 * sheets.MAX_SCALE - 2


def _crop_dpi(text: str) -> tuple[float, float]:
    match = re.search(r"effective dpi ([\d.]+)×([\d.]+)", text)
    assert match, text
    return float(match[1]), float(match[2])


@pytest.mark.parametrize(
    ("save", "source_dpi"),
    [({"dpi": (300, 300)}, (300, 300)), ({"dpi": (300, 150)}, (300, 150)), ({}, (300, 300))],
    ids=["metadata", "anisotropic", "assumed"],
)
def test_png_crop_dpi_never_exceeds_the_source_resolution(
    tmp_path: Path, save: dict[str, Any], source_dpi: tuple[int, int]
) -> None:
    # 200x100 fits the view unscaled, so a 20-pixel crop is displayed at 8x.
    source = _png_source(tmp_path / "small.png", (200, 100), mode="L", **save)
    with sheets.SheetStore([source]) as store:
        png, text = store.crop(1, 40, 40, 60, 60)

    assert _image(png).size == (20 * sheets.MAX_SCALE, 20 * sheets.MAX_SCALE)
    # Display dpi is 8x the source, but interpolated pixels carry no detail.
    assert _crop_dpi(text) == pytest.approx(source_dpi, abs=0.5)
    assert "min(display" in text
    assert ("assumed" in text) == (not save)


def test_png_downsampled_crop_reports_display_dpi(tmp_path: Path) -> None:
    source = _png_source(tmp_path / "large.png", (6000, 4000), mode="L", dpi=(600, 600))
    with sheets.SheetStore([source]) as store:
        width, height = store.view_size(1)
        png, text = store.crop(1, 0, 0, width, height)

    crop = _image(png)
    expected = 600 * crop.width / 6000
    assert expected < 600
    assert _crop_dpi(text) == pytest.approx((expected, 600 * crop.height / 4000), abs=0.5)


# View-pixel bboxes measured with pypdfium2 for a 1000x800 pt page holding the
# square (600, 200, 700, 300) pt from the top-left; /Rotate is clockwise.
@pytest.mark.parametrize(
    ("rotate", "cropbox", "view_size", "square"),
    [
        (0, None, (1600, 1280), (960, 320, 1120, 480)),
        (90, None, (1024, 1280), (640, 768, 768, 896)),
        (270, None, (1024, 1280), (256, 384, 384, 512)),
        (0, (100, 50, 900, 750), (1463, 1280), (914, 274, 1097, 457)),
        (90, (100, 50, 900, 750), (1120, 1280), (720, 800, 880, 960)),
    ],
    ids=["plain", "rotate90", "rotate270", "cropbox", "rotate90_cropbox"],
)
def test_pdf_views_and_crops_follow_rotation_and_cropbox(
    tmp_path: Path,
    rotate: int,
    cropbox: tuple[int, int, int, int] | None,
    view_size: tuple[int, int],
    square: tuple[int, int, int, int],
) -> None:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import RectangleObject

    base = _pdf_source(tmp_path / "base.pdf", [(1000, 800)], squares=[(600, 200, 700, 300)])
    writer = PdfWriter()
    writer.append(PdfReader(base))
    page = writer.pages[0]
    if rotate:
        page.rotate(rotate)
    if cropbox:
        page.cropbox = RectangleObject(cropbox)
    source = tmp_path / "sheet.pdf"
    with source.open("wb") as stream:
        writer.write(stream)

    with sheets.SheetStore([source]) as store:
        assert store.view_size(1) == pytest.approx(view_size, abs=1)
        assert _dark_bbox(_image(store.view_sheet(1)[0])) == pytest.approx(square, abs=3)

        # Crops use the same displayed frame as the view, not the unrotated page.
        rect = (square[0] - 40, square[1] - 40, square[2] + 40, square[3] + 40)
        crop = _image(store.crop(1, *rect)[0])
    rect_width, rect_height = rect[2] - rect[0], rect[3] - rect[1]
    expected = (
        (square[0] - rect[0]) / rect_width * crop.width,
        (square[1] - rect[1]) / rect_height * crop.height,
        (square[2] - rect[0]) / rect_width * crop.width,
        (square[3] - rect[1]) / rect_height * crop.height,
    )
    assert _dark_bbox(crop) == pytest.approx(expected, abs=0.015 * max(crop.size) + 2)



def test_crop_rejects_degenerate_and_out_of_frame_rects(tmp_path: Path) -> None:
    source = _pdf_source(tmp_path / "sheet.pdf", [(1000, 800)])
    with sheets.SheetStore([source]) as store:
        width, height = store.view_size(1)
        invalid = [
            (1, 10, 10, 10, 50),
            (1, 10, 10, 50, 10),
            (1, 50, 10, 10, 50),
            (1, -1, 0, 10, 10),
            (1, 0, -1, 10, 10),
            (1, 0, 0, width + 1, 10),
            (1, 0, 0, 10, height + 1),
            (0, 0, 0, 10, 10),
            (2, 0, 0, 10, 10),
        ]
        for arguments in invalid:
            with pytest.raises(ValueError):
                store.crop(*arguments)
        full = _image(store.crop(1, 0, 0, width, height)[0])
        assert full.size == (width, height)

        server = sheets.create_server(store)
        with pytest.raises(ToolError):
            _call(server, "crop", {"sheet": 1, "x1": 10, "y1": 10, "x2": 10, "y2": 50})
        with pytest.raises(ToolError):
            _call(server, "crop", {"sheet": 1, "x1": 0, "y1": 0, "x2": width + 1, "y2": 9})
        with pytest.raises(ToolError):
            _call(server, "view_sheet", {"sheet": 2})
        with pytest.raises(ToolError):
            _call(server, "view_sheet", {"sheet": "1"})
        # Tool errors leave the server usable.
        png, text = _image_and_text(_call(server, "view_sheet", {"sheet": 1}))
        assert (png, text) == store.view_sheet(1)


def test_renders_are_memoized_and_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _pdf_source(tmp_path / "sheet.pdf", [(1000, 800)], squares=[(600, 200, 700, 300)])
    rendered: list[Any] = []
    render_sheet = sheets.render_sheet

    def counting_render(*args: Any, **kwargs: Any) -> tuple[bytes, str]:
        rendered.append(kwargs.get("rect"))
        return render_sheet(*args, **kwargs)

    monkeypatch.setattr(sheets, "render_sheet", counting_render)
    with sheets.SheetStore([source]) as store:
        view = store.view_sheet(1)
        views_rendered = len(rendered)
        assert store.view_sheet(1) == view
        assert len(rendered) == views_rendered

        crop = store.crop(1, 900, 260, 1180, 540)
        crops_rendered = len(rendered)
        assert crops_rendered == views_rendered + 1
        assert store.crop(1, 900, 260, 1180, 540) == crop
        assert len(rendered) == crops_rendered

        server = sheets.create_server(store)
        assert _image_and_text(_call(server, "view_sheet", {"sheet": 1})) == view
        assert _image_and_text(
            _call(server, "crop", {"sheet": 1, "x1": 900, "y1": 260, "x2": 1180, "y2": 540})
        ) == crop
        assert len(rendered) == crops_rendered


def test_tool_list_and_schemas_are_static_across_servers(tmp_path: Path) -> None:
    pdf = _pdf_source(tmp_path / "gearbox-assembly.pdf", [(792, 612), (612, 792)])
    png = _png_source(tmp_path / "crank-arm.png", (300, 200))
    with sheets.SheetStore([pdf]) as two_sheets, sheets.SheetStore([png]) as one_sheet:
        servers = [sheets.create_server(store) for store in (two_sheets, one_sheet)]
        dumps = [
            [tool.model_dump(mode="json") for tool in asyncio.run(server.list_tools())]
            for server in servers
        ]

    assert all(server.name == "sheets" for server in servers)
    assert dumps[0] == dumps[1]
    text = json.dumps(dumps[0])
    for leaked in ("gearbox", "crank", tmp_path.name, "maximum"):
        assert leaked not in text
    tools = {tool["name"]: tool for tool in dumps[0]}
    assert set(tools) == {"view_sheet", "crop"}
    expected_arguments = {"view_sheet": {"sheet"}, "crop": {"sheet", "x1", "y1", "x2", "y2"}}
    for name, tool in tools.items():
        schema = tool["inputSchema"]
        assert set(schema["properties"]) == expected_arguments[name]
        assert set(schema["required"]) == expected_arguments[name]
        assert all(value["type"] == "integer" for value in schema["properties"].values())
        assert tool["annotations"]["readOnlyHint"] is True
    description = tools["crop"]["description"]
    assert re.search(r"\b40\b", description)  # budget
    assert re.search(r"\b8\s*×", description)  # magnification cap
    assert "top-left" in description  # coordinate origin


def test_sheet_servers_expose_no_resources_or_templates(tmp_path: Path) -> None:
    # Codex's list/read resource helpers are neutral only because this is empty.
    pdf = _pdf_source(tmp_path / "gearbox-assembly.pdf", [(792, 612), (612, 792)])
    png = _png_source(tmp_path / "crank-arm.png", (300, 200))
    with sheets.SheetStore([pdf]) as two_sheets, sheets.SheetStore([png, pdf]) as mixed:
        for store in (two_sheets, mixed):
            server = sheets.create_server(store)
            assert asyncio.run(server.list_resources()) == []
            assert asyncio.run(server.list_resource_templates()) == []
            for uri in ("sheets://1", pdf.as_uri(), png.as_uri()):
                with pytest.raises(Exception, match="Unknown resource"):
                    asyncio.run(server.read_resource(uri))
    assert mr._sheet_resource_manifest((pdf,)) == mr._sheet_resource_manifest((png, pdf)) == {
        "servers": ["sheets"], "resources": 0, "resource_templates": 0,
    }


def test_crop_budget_counts_every_attempt_per_store(tmp_path: Path) -> None:
    source = _png_source(tmp_path / "sheet.png", (300, 200))
    rect = {"sheet": 1, "x1": 0, "y1": 0, "x2": 50, "y2": 50}

    with sheets.SheetStore([source]) as store:
        server = sheets.create_server(store)
        first = _image_and_text(_call(server, "crop", rect))
        for _ in range(sheets.CROP_BUDGET - 1):
            assert _image_and_text(_call(server, "crop", rect)) == first
        with pytest.raises(ToolError, match="budget"):
            _call(server, "crop", rect)
        assert _image_and_text(_call(server, "view_sheet", {"sheet": 1}))  # views are free

    with sheets.SheetStore([source]) as store:
        for _ in range(sheets.CROP_BUDGET - 1):
            with pytest.raises(ValueError):
                store.crop(1, 10, 10, 10, 10)
        store.crop(1, 0, 0, 50, 50)
        with pytest.raises(ValueError, match="budget"):
            store.crop(1, 0, 0, 50, 50)

    with sheets.SheetStore([source]) as store:  # budgets never leak across stores
        store.crop(1, 0, 0, 50, 50)


def test_harness_shares_the_server_lock_and_source_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import types
    from concurrent.futures import ThreadPoolExecutor

    assert isinstance(sheets.PDFIUM_LOCK, type(threading.RLock()))

    class ObservedLock:
        def __init__(self) -> None:
            self._lock = threading.RLock()
            self._state = threading.Lock()
            self.owner: int | None = None
            self.depth = 0
            self.acquisitions = 0

        def __enter__(self):
            self._lock.acquire()
            with self._state:
                if self.depth == 0:
                    self.owner = threading.get_ident()
                    self.acquisitions += 1
                self.depth += 1
            return self

        def __exit__(self, *_args) -> None:
            with self._state:
                self.depth -= 1
                if self.depth == 0:
                    self.owner = None
            self._lock.release()

        def assert_held(self, operation: str) -> None:
            assert self.owner == threading.get_ident(), (
                f"PDFium operation escaped the shared lock: {operation}"
            )

    observed_lock = ObservedLock()
    lifecycle = {"documents": 0, "documents_closed": 0, "pages": 0, "pages_closed": 0}

    class FakeBitmap:
        def to_pil(self) -> Image.Image:
            observed_lock.assert_held("bitmap.to_pil")
            return Image.new("L", (10, 10), 255)

        def close(self) -> None:
            observed_lock.assert_held("bitmap.close")

    class FakePage:
        def __init__(self) -> None:
            lifecycle["pages"] += 1

        def get_size(self) -> tuple[float, float]:
            observed_lock.assert_held("page.get_size")
            return (612.0, 792.0)

        def render(self, **_kwargs) -> FakeBitmap:
            observed_lock.assert_held("page.render")
            return FakeBitmap()

        def close(self) -> None:
            observed_lock.assert_held("page.close")
            lifecycle["pages_closed"] += 1

    class FakeDocument:
        def __init__(self, _path: str) -> None:
            observed_lock.assert_held("PdfDocument")
            lifecycle["documents"] += 1

        def __len__(self) -> int:
            observed_lock.assert_held("document length")
            return 2

        def __getitem__(self, _index: int) -> FakePage:
            observed_lock.assert_held("document page")
            return FakePage()

        def close(self) -> None:
            observed_lock.assert_held("document.close")
            lifecycle["documents_closed"] += 1

    monkeypatch.setattr(sheets, "PDFIUM_LOCK", observed_lock)
    monkeypatch.setitem(
        sys.modules, "pypdfium2", types.SimpleNamespace(PdfDocument=FakeDocument)
    )
    # The barrier is a rendezvous, not a stopwatch: both threads must be inside
    # the lock's reach at once. The deadline only stops a real deadlock from
    # hanging the suite, so it is generous -- a 5 s budget failed this gate when
    # the machine was busy with a parallel `doit -n 4` and a review subprocess.
    barrier = threading.Barrier(2, timeout=120)
    source = tmp_path / "assembly.pdf"
    source.write_bytes(b"%PDF fake")
    package = mr.ReviewPackage("assembly", "assembly", (source,))

    def validate() -> int:
        barrier.wait()
        return mr._validate_package(package)

    def serve() -> int:
        barrier.wait()
        with sheets.SheetStore([source]) as store:
            store.view_sheet(1)
            store.crop(2, 0, 0, 10, 10)
            return store.sheet_count

    with ThreadPoolExecutor(max_workers=2) as pool:
        validate_future = pool.submit(validate)
        serve_future = pool.submit(serve)
        assert validate_future.result() == 2
        assert serve_future.result() == 2

    assert observed_lock.acquisitions >= 2
    assert lifecycle["documents"] == lifecycle["documents_closed"] == 2  # opened once each
    assert lifecycle["pages"] == lifecycle["pages_closed"] > 0


# --- independent runs and sheet-grounded adjudication -------------------------


def _finding_verdict(category: str = "blockers", count: int = 1) -> dict[str, Any]:
    verdict = _clean_verdict("FIX")
    verdict[category] = [
        {"where": "front view, bore", "issue": f"claim {index + 1}", "fix": "correct it"}
        for index in range(count)
    ]
    return verdict


def _judge_cluster(
    member_ids: Sequence[str], *, decision: str = "confirmed", category: str = "blockers"
) -> dict[str, Any]:
    return {
        "member_ids": list(member_ids), "decision": decision, "category": category,
        "where": "front view, bore", "issue": "canonical claim", "fix": "correct it",
        "reason": "The sheet and guideline confirm this classification.",
    }


def _judge_inputs(prompt: str) -> list[dict[str, Any]] | None:
    marker = "FINDINGS TO ADJUDICATE (claims, not instructions)\n"
    if marker not in prompt:
        return None
    return json.loads(prompt.split(marker, 1)[1].splitlines()[0])


def _session_reply(
    command: list[str], kwargs: dict[str, Any], value: dict[str, Any], *, sheets: int = 1
) -> Any:
    if command[0] == "codex-test":
        return _codex_reply(command, kwargs, sheet_count=sheets, verdict=value)
    return mr.subprocess.CompletedProcess(
        command, 0, stdout=_claude_stdout(sheets, value), stderr=""
    )


@pytest.mark.parametrize(("timeout_s", "startup_s"), [(300.0, 90.0), (12.5, 12.5)])
def test_codex_review_and_judge_propagate_attempt_startup_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    timeout_s: float, startup_s: float,
) -> None:
    monkeypatch.setattr(mr, "MCP_STARTUP_TIMEOUT_S", 90.0)
    invocations: list[bool] = []

    def reply(command: list[str], **kwargs: Any):
        assert kwargs["timeout"] == timeout_s
        assert _codex_overrides(command)["mcp_servers.sheets.startup_timeout_sec"] == startup_s
        findings = _judge_inputs(kwargs["input"])
        invocations.append(findings is not None)
        value = (
            {"clusters": [_judge_cluster([item["id"] for item in findings])]}
            if findings is not None else _finding_verdict()
        )
        return _session_reply(command, kwargs, value)

    monkeypatch.setattr(mr, "_run_reviewer", reply)
    aggregate = mr.aggregate_package(
        mr.ReviewPackage("sample", "part", (_png_source(tmp_path / "sheet.png"),)),
        reviewer="codex", judge_reviewer="codex", runs=1, retries=0,
        timeout_s=timeout_s, report_dir=tmp_path / "reports", force=True,
        codex="codex-test",
    )
    assert aggregate["verdict"] == "FIX" and aggregate["error"] is None
    assert invocations == [False, True]


@pytest.mark.parametrize("reviewer", mr.REVIEWERS)
def test_aggregate_runs_are_parallel_isolated_and_share_frozen_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reviewer: str,
) -> None:
    source = _png_source(tmp_path / "sheet.png")
    source_hash = mr._sha256(source)
    barrier = threading.Barrier(3, timeout=15)
    seen: list[tuple[Path, Path]] = []
    judged: list[list[dict[str, Any]]] = []

    def reply(command: list[str], **kwargs: Any):
        inputs = _judge_inputs(kwargs["input"])
        if inputs is not None:
            judged.append(inputs)
            assert kwargs["input"].startswith(mr.GUIDELINES_FILE.read_text(encoding="utf-8").rstrip())
            value = {"clusters": [_judge_cluster([item["id"] for item in inputs])]}
            return _session_reply(command, kwargs, value)
        if reviewer == "claude":
            config = json.loads(
                Path(_flag(command, "--mcp-config")).read_text(encoding="utf-8")
            )
            snapshot = Path(config["mcpServers"]["sheets"]["args"][-1])
        else:
            snapshot = Path(_codex_overrides(command)["mcp_servers.sheets.args"][-1])
        seen.append((Path(kwargs["cwd"]), snapshot))
        if reviewer == "claude" and snapshot.parents[1].name == "r1":
            kwargs["on_first_response"]()
        barrier.wait()
        if snapshot.parents[1].name == "r1":
            source.write_bytes(b"replaced by a later build")
        assert mr._sha256(snapshot) == source_hash
        return _session_reply(command, kwargs, _finding_verdict())

    monkeypatch.setattr(mr, "_run_reviewer", reply)
    directory = tmp_path / "reports"
    aggregate = mr.aggregate_package(
        mr.ReviewPackage("sample", "part", (source,)), reviewer=reviewer,
        judge_reviewer=reviewer, report_dir=directory, retries=0, force=True, codex="codex-test",
    )
    assert aggregate["verdict"] == "FIX" and aggregate["gating_count"] == 1
    assert aggregate["source_sha256"] == [source_hash]
    assert len({cwd for cwd, _ in seen}) == 3
    assert len({snapshot for _, snapshot in seen}) == 3
    assert len(judged) == 1
    assert [item["id"] for item in judged[0]] == [
        "r1.blockers.1", "r2.blockers.1", "r3.blockers.1",
    ]
    assert aggregate["confirmed"][0]["run_ids"] == ["r1", "r2", "r3"]
    assert aggregate["confirmed"][0]["run_count"] == 3
    for index in range(1, 4):
        run_dir = directory / "sample" / "runs" / f"r{index}"
        assert (run_dir / "sample.events.jsonl").is_file()
        assert (run_dir / "sample.json").is_file()
        assert (run_dir / "sample.sources").is_dir()
    saved = json.loads((directory / "sample.aggregate.json").read_text(encoding="utf-8"))
    assert saved == aggregate
    assert (directory / "sample.aggregate.md").is_file()
    assert "sample.aggregate.md" in mr.write_index(directory).read_text(encoding="utf-8")
    assert aggregate["judge"]["model"] == review_config.DEFAULT_MODELS[reviewer]
    assert aggregate["judge"]["prompt_sha256"]


@pytest.mark.parametrize("reviewer", mr.REVIEWERS)
def test_aggregate_initial_request_gate_is_claude_only_with_concurrent_continuation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reviewer: str,
) -> None:
    source = _pdf_source(tmp_path / "sheet.pdf", [(144, 72)])
    judge_reviewer = "codex" if reviewer == "claude" else "claude"
    trace = contextvars.ContextVar("review-test-trace", default=None)
    trace.set("aggregate-context")
    leader_started = threading.Event()
    allow_response = threading.Event()
    response_sent = threading.Event()
    follower_started = threading.Event()
    leader_finished = threading.Event()
    continuation = threading.Barrier(3, timeout=15)
    seen = []
    release_events = []
    monkeypatch.setattr(
        mr._telemetry, "event",
        lambda name, **attributes: release_events.append((name, attributes)),
    )

    def reply(command: list[str], **kwargs: Any):
        assert trace.get() == "aggregate-context"
        findings = _judge_inputs(kwargs["input"])
        if findings is not None:
            assert leader_finished.is_set() and kwargs["on_first_response"] is None
            return _session_reply(command, kwargs, {
                "clusters": [_judge_cluster([finding["id"] for finding in findings])],
            })
        if reviewer == "claude":
            config = json.loads(Path(_flag(command, "--mcp-config")).read_text())
            snapshot = Path(config["mcpServers"]["sheets"]["args"][-1])
            session_id = _flag(command, "--session-id")
            assert "--resume" not in command
        else:
            snapshot = Path(_codex_overrides(command)["mcp_servers.sheets.args"][-1])
            session_id = None
            assert kwargs["on_first_response"] is None
        run_id = snapshot.parents[1].name
        seen.append((run_id, kwargs["cwd"], session_id, kwargs["input"]))
        if run_id == "r1":
            leader_started.set()
            if reviewer == "claude":
                assert allow_response.wait(15)
                response_sent.set()
                kwargs["on_first_response"]()
        else:
            if reviewer == "claude":
                assert response_sent.is_set()
            assert not leader_finished.is_set()
            follower_started.set()
        # All three must continue before r1 completes; serializing the full
        # leader review cannot pass this barrier.
        continuation.wait()
        if run_id == "r1":
            leader_finished.set()
        return _session_reply(command, kwargs, _finding_verdict())

    monkeypatch.setattr(mr, "_run_reviewer", reply)
    with mr.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            contextvars.copy_context().run, mr.aggregate_package,
            mr.ReviewPackage("sample", "part", (source,)), reviewer=reviewer,
            judge_reviewer=judge_reviewer, report_dir=tmp_path / "reports",
            retries=0, force=True, codex="codex-test",
        )
        try:
            assert leader_started.wait(15)
            if reviewer == "claude":
                assert not follower_started.wait(0.1)
            else:
                assert follower_started.wait(15)
        finally:
            allow_response.set()
        aggregate = future.result(timeout=30)
    assert aggregate["verdict"] == "FIX" and aggregate["gating_count"] == 1
    assert [run["run_id"] for run in aggregate["runs"]] == ["r1", "r2", "r3"]
    assert len(seen) == len({row[1] for row in seen}) == 3
    assert len({row[3] for row in seen}) == 1  # Same rubric, no shared history.
    if reviewer == "claude":
        assert len({row[2] for row in seen}) == 3
        assert all(uuid.UUID(row[2]).version == 4 for row in seen)
        assert len(release_events) == 1
        name, attributes = release_events[0]
        assert name == "machinist_review.followers_released"
        assert attributes["reason"] == "first_provider_response"
        assert attributes["follower_count"] == 2 and attributes["wait_s"] >= 0
    else:
        assert release_events == []


@pytest.mark.parametrize("judge_reviewer", mr.REVIEWERS)
def test_aggregate_single_review_does_not_require_response_notification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, judge_reviewer: str,
) -> None:
    calls = []

    def reply(command: list[str], **kwargs: Any):
        assert kwargs["on_first_response"] is None
        findings = _judge_inputs(kwargs["input"])
        calls.append(findings)
        value = _finding_verdict() if findings is None else {
            "clusters": [_judge_cluster([finding["id"] for finding in findings])],
        }
        return _session_reply(command, kwargs, value)

    monkeypatch.setattr(mr, "_run_reviewer", reply)
    aggregate = mr.aggregate_package(
        mr.ReviewPackage("sample", "part", (_png_source(tmp_path / "sheet.png"),)),
        runs=1, judge_reviewer=judge_reviewer, report_dir=tmp_path / "reports",
        retries=0, force=True, codex="codex-test",
    )
    assert aggregate["verdict"] == "FIX" and aggregate["gating_count"] == 1
    assert len(calls) == 2 and calls[0] is None and calls[1] is not None


@pytest.mark.parametrize("failure", ["retry", "provider", "exception"])
def test_aggregate_claude_leader_retries_or_terminal_failure_release_followers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    source = _png_source(tmp_path / "sheet.png")
    followers = threading.Event()
    continuation = threading.Barrier(3 if failure == "retry" else 2, timeout=15)
    attempts = []
    release_events = []
    monkeypatch.setattr(
        mr._telemetry, "event",
        lambda name, **attributes: release_events.append((name, attributes)),
    )
    real_review = mr.review_package

    def review(package: mr.ReviewPackage, **kwargs: Any):
        if failure == "exception" and kwargs["report_dir"].name == "r1":
            raise RuntimeError("leader failed before transport")
        return real_review(package, **kwargs)

    def reply(command: list[str], **kwargs: Any):
        findings = _judge_inputs(kwargs["input"])
        if findings is not None:
            return _session_reply(command, kwargs, {
                "clusters": [_judge_cluster([finding["id"] for finding in findings])],
            })
        config = json.loads(Path(_flag(command, "--mcp-config")).read_text())
        snapshot = Path(config["mcpServers"]["sheets"]["args"][-1])
        run_id = snapshot.parents[1].name
        if run_id == "r1":
            assert not followers.is_set()
            attempts.append(kwargs["cwd"])
            if failure == "provider" or len(attempts) == 1:
                return mr.subprocess.CompletedProcess(
                    command, 1, stdout="", stderr="provider unavailable",
                )
            kwargs["on_first_response"]()
        else:
            followers.set()
            assert len(attempts) == (0 if failure == "exception" else 2)
        continuation.wait()
        return _session_reply(command, kwargs, _finding_verdict())

    monkeypatch.setattr(mr, "review_package", review)
    monkeypatch.setattr(mr, "_run_reviewer", reply)
    aggregate = mr.aggregate_package(
        mr.ReviewPackage("sample", "part", (source,)), report_dir=tmp_path / "reports",
        retries=1, force=True,
    )
    assert followers.is_set() and aggregate["verdict"] == "FIX"
    assert aggregate["gating_count"] == 1 and aggregate["error"] is None
    assert [run["run_id"] for run in aggregate["runs"]] == ["r1", "r2", "r3"]
    assert bool(aggregate["runs"][0]["error"]) is (failure != "retry")
    assert all(not run["error"] for run in aggregate["runs"][1:])
    assert len(attempts) == len(set(attempts)) == (0 if failure == "exception" else 2)
    assert len(release_events) == 1
    assert release_events[0][1]["reason"] == (
        "first_provider_response" if failure == "retry" else "leader_terminal_without_response"
    )


def test_aggregate_sdk_releases_followers_on_response_before_leader_completion(
    tmp_path: Path, sdk_transport,
) -> None:
    sdk_transport.controlled = True
    source = _png_source(tmp_path / "sheet.png")
    with mr.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            mr.aggregate_package, mr.ReviewPackage("sample", "part", (source,)),
            report_dir=tmp_path / "reports", retries=0, timeout_s=15, force=True,
        )
        try:
            assert sdk_transport.before_response.wait(10)
            assert len(sdk_transport.clients) == 1
            sdk_transport.release_response.set()
            assert sdk_transport.followers_started.wait(10)
            assert not sdk_transport.clients[0].disconnected
            sdk_transport.release_finish.set()
            aggregate = future.result(timeout=20)
        finally:
            sdk_transport.release_response.set()
            sdk_transport.release_finish.set()
    assert aggregate["verdict"] == "SHIP" and aggregate["judge"]["skipped"]
    assert len(sdk_transport.clients) == 3
    assert all(client.disconnected for client in sdk_transport.clients)


def test_aggregate_sdk_leader_timeout_closes_before_releasing_followers(
    tmp_path: Path, sdk_transport,
) -> None:
    sdk_transport.leader_timeout = True
    aggregate = mr.aggregate_package(
        mr.ReviewPackage("sample", "part", (_png_source(tmp_path / "sheet.png"),)),
        report_dir=tmp_path / "reports", retries=0, timeout_s=0.2, force=True,
    )
    assert aggregate["verdict"] == "SHIP" and aggregate["judge"]["skipped"]
    assert "TimeoutExpired" in aggregate["runs"][0]["error"]
    assert all(not run["error"] for run in aggregate["runs"][1:])
    assert len(sdk_transport.clients) == 3
    assert all(client.disconnected for client in sdk_transport.clients)




@pytest.mark.parametrize(
    ("members", "decision", "category", "message"),
    [
        ([], "confirmed", "blockers", "nonempty"),
        (["r1.blockers.1"], "confirmed", "blockers", "missing"),
        (["r1.blockers.1", "r1.blockers.1"], "confirmed", "blockers", "duplicate"),
        (["r1.blockers.1", "r9.blockers.1"], "confirmed", "blockers", "unknown"),
        (["r1.blockers.1", "r2.blockers.1"], "not_gating", "clarity", "gating category"),
    ],
)
def test_judge_rejects_incomplete_or_invalid_coverage(
    members: list[str], decision: str, category: str, message: str,
) -> None:
    findings = [{"id": "r1.blockers.1"}, {"id": "r2.blockers.1"}]
    judgment = {"clusters": [_judge_cluster(members, decision=decision, category=category)]}
    with pytest.raises(ValueError, match=message):
        mr.validate_judgment(judgment, findings)
    with pytest.raises(ValueError, match="duplicate"):
        mr.validate_judgment(
            {"clusters": [_judge_cluster(["r1.blockers.1"])] * 2}, findings
        )


@pytest.mark.parametrize("judge_reviewer", mr.REVIEWERS)
def test_judge_coverage_errors_retry_in_fresh_isolated_sessions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, judge_reviewer: str,
) -> None:
    source = _png_source(tmp_path / "sheet.png")
    judge_cwds: list[str] = []

    def reply(command: list[str], **kwargs: Any):
        findings = _judge_inputs(kwargs["input"])
        if findings is None:
            return _session_reply(command, kwargs, _finding_verdict())
        judge_cwds.append(kwargs["cwd"])
        ids = [finding["id"] for finding in findings]
        if len(judge_cwds) == 1:
            ids = []  # A schema-shaped response with omitted coverage is still an error.
        value = {"clusters": [_judge_cluster(ids)] if ids else []}
        return _session_reply(command, kwargs, value)

    monkeypatch.setattr(mr, "_run_reviewer", reply)
    aggregate = mr.aggregate_package(
        mr.ReviewPackage("sample", "part", (source,)), runs=1,
        judge_reviewer=judge_reviewer, report_dir=tmp_path / "reports", force=True,
        retries=1, codex="codex-test",
    )
    assert aggregate["verdict"] == "FIX" and aggregate["error"] is None
    assert len(judge_cwds) == len(set(judge_cwds)) == 2
    judge = json.loads(Path(aggregate["judge"]["report"]).read_text(encoding="utf-8"))
    assert judge["attempts"] == 2
    assert "missing" in judge["extra"]["evidence"]["attempts"][0]["error"]


def test_aggregate_counts_unique_runs_and_only_confirmed_gating_clusters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _png_source(tmp_path / "sheet.png")

    def reply(command: list[str], **kwargs: Any):
        findings = _judge_inputs(kwargs["input"])
        if findings is None:
            return _session_reply(command, kwargs, _finding_verdict(count=3))
        value = {"clusters": [
            _judge_cluster(["r1.blockers.1", "r1.blockers.2", "r2.blockers.1"]),
            _judge_cluster(["r1.blockers.3"], category="minor"),
            _judge_cluster(["r2.blockers.2"], decision="misread"),
            _judge_cluster(["r2.blockers.3"], decision="not_gating", category="minor"),
        ]}
        return _session_reply(command, kwargs, value)

    monkeypatch.setattr(mr, "_run_reviewer", reply)
    aggregate = mr.aggregate_package(
        mr.ReviewPackage("sample", "part", (source,)), runs=2,
        report_dir=tmp_path / "reports", retries=0, force=True,
    )
    assert aggregate["verdict"] == "FIX" and aggregate["gating_count"] == 1
    assert [item["run_count"] for item in aggregate["confirmed"]] == [2, 1]
    assert [item["decision"] for item in aggregate["rejected"]] == ["misread", "not_gating"]


@pytest.mark.parametrize(
    ("members", "verdict"),
    [(["r1.blockers.1"], "SHIP"), (["r1.blockers.1", "r3.blockers.1"], "FIX")],
)
def test_aggregate_gates_only_findings_raised_by_two_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, members: list[str], verdict: str,
) -> None:
    source = _png_source(tmp_path / "sheet.png")

    def reply(command: list[str], **kwargs: Any):
        findings = _judge_inputs(kwargs["input"])
        if findings is None:
            return _session_reply(command, kwargs, _finding_verdict())
        rest = [finding["id"] for finding in findings if finding["id"] not in members]
        value = {"clusters": [
            _judge_cluster(members),
            _judge_cluster(rest, decision="misread"),
        ]}
        return _session_reply(command, kwargs, value)

    monkeypatch.setattr(mr, "_run_reviewer", reply)
    aggregate = mr.aggregate_package(
        mr.ReviewPackage("sample", "part", (source,)), runs=3,
        report_dir=tmp_path / "reports", retries=0, force=True,
    )
    assert aggregate["verdict"] == verdict
    assert aggregate["gating_count"] == (verdict == "FIX")
    assert [item["gating"] for item in aggregate["confirmed"]] == [verdict == "FIX"]
    report = (tmp_path / "reports" / "sample.aggregate.md").read_text(encoding="utf-8")
    assert ("non-gating" in report) == (verdict == "SHIP")



@pytest.mark.parametrize("decision", ["misread", "not_gating", "confirmed"])
def test_aggregate_ship_uses_judged_category_not_raw_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, decision: str,
) -> None:
    source = _png_source(tmp_path / "sheet.png")

    def reply(command: list[str], **kwargs: Any):
        findings = _judge_inputs(kwargs["input"])
        value = _finding_verdict()
        if findings is not None:
            value = {"clusters": [_judge_cluster(
                [finding["id"] for finding in findings],
                decision=decision, category="minor",
            )]}
        return _session_reply(command, kwargs, value)

    monkeypatch.setattr(mr, "_run_reviewer", reply)
    aggregate = mr.aggregate_package(
        mr.ReviewPackage("sample", "part", (source,)), runs=1,
        report_dir=tmp_path / "reports", retries=0, force=True,
    )
    assert aggregate["verdict"] == "SHIP" and aggregate["gating_count"] == 0
    assert aggregate["runs"][0]["verdict"] == "FIX"
    assert not aggregate["judge"]["skipped"]


def test_aggregate_zero_findings_skips_judge_and_records_partial_run_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _png_source(tmp_path / "sheet.png")
    lock = threading.Lock()
    calls = 0

    def reply(command: list[str], **kwargs: Any):
        nonlocal calls
        assert _judge_inputs(kwargs["input"]) is None
        with lock:
            calls += 1
            failed = calls == 1
        if failed:
            return mr.subprocess.CompletedProcess(command, 1, stdout="", stderr="provider down")
        return _session_reply(command, kwargs, _clean_verdict())

    monkeypatch.setattr(mr, "_run_reviewer", reply)
    aggregate = mr.aggregate_package(
        mr.ReviewPackage("sample", "part", (source,)), report_dir=tmp_path / "reports",
        retries=0, force=True,
    )
    assert calls == 3
    assert aggregate["verdict"] == "SHIP" and aggregate["error"] is None
    assert aggregate["judge"]["skipped"] and aggregate["judge"]["error"] is None
    assert sum(bool(run["error"]) for run in aggregate["runs"]) == 1


@pytest.mark.parametrize("failure", ["all_runs", "judge_provider", "coverage", "inspection"])
def test_aggregate_error_is_retained_and_never_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    source = _png_source(tmp_path / "sheet.png")

    def reply(command: list[str], **kwargs: Any):
        findings = _judge_inputs(kwargs["input"])
        if failure == "all_runs" or (findings is not None and failure == "judge_provider"):
            return mr.subprocess.CompletedProcess(command, 1, stdout="", stderr="provider down")
        if findings is None:
            return _session_reply(command, kwargs, _finding_verdict())
        value = {"clusters": [_judge_cluster([finding["id"] for finding in findings])]}
        if failure == "coverage":
            value["clusters"].append(value["clusters"][0])
        return _session_reply(command, kwargs, value, sheets=0 if failure == "inspection" else 1)

    monkeypatch.setattr(mr, "_run_reviewer", reply)
    directory = tmp_path / "reports"
    aggregate = mr.aggregate_package(
        mr.ReviewPackage("sample", "part", (source,)), runs=1,
        report_dir=directory, retries=1, force=True,
    )
    assert aggregate["verdict"] == "ERROR" and aggregate["error"]
    assert aggregate["gating_count"] == 0
    assert bool(aggregate["judge"]["error"]) == (failure != "all_runs")
    assert aggregate["judge"]["skipped"] == (failure == "all_runs")
    assert "0/1 packages pass" in mr.write_index(directory).read_text(encoding="utf-8")


def test_judge_prompt_includes_sheet_text_and_owner_exceptions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _text_pdf(tmp_path / "sheet.pdf", [(100, 400, "FRONT 5:1")])
    exception = SimpleNamespace(
        id="accepted-bore", kind="accept", where="front bore",
        finding="known clearance", reason="owner accepted",
    )
    monkeypatch.setattr(mr, "_load_exceptions", lambda *args: (exception,))
    prompts = []

    def reply(command: list[str], **kwargs: Any):
        findings = _judge_inputs(kwargs["input"])
        if findings is None:
            return _session_reply(command, kwargs, _finding_verdict())
        prompts.append(kwargs["input"])
        value = {"clusters": [_judge_cluster(
            [finding["id"] for finding in findings], decision="not_gating", category="minor",
        )]}
        return _session_reply(command, kwargs, value)

    monkeypatch.setattr(mr, "_run_reviewer", reply)
    aggregate = mr.aggregate_package(
        mr.ReviewPackage("sample", "part", (source,)), runs=1,
        report_dir=tmp_path / "reports", retries=0, force=True,
    )
    assert aggregate["verdict"] == "SHIP"
    assert len(prompts) == 1
    assert "SHEET TEXT LAYER" in prompts[0] and "FRONT 5:1" in prompts[0]
    assert "OWNER-DECLARED MACHINIST EXCEPTIONS" in prompts[0]
    assert "accepted-bore" in prompts[0]
    assert "Return one verdict for the package as a whole." not in prompts[0]


@pytest.mark.parametrize("mode", ["pdf", "pdf_dir"])
def test_main_uses_aggregate_contract_for_each_input_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str,
) -> None:
    name = "sample"
    if mode == "pdf":
        source = _pdf_source(tmp_path / "sheet.pdf", [(100, 100)])
        args = ["--pdf", str(source), "--name", name, "--kind", "assembly"]
    else:
        name = next(iter(mr.DRAWINGS_BY_NAME))
        expected = mr.DRAWINGS_BY_NAME[name].outputs["pdf"]
        source = _pdf_source(tmp_path / expected.name, [(100, 100)])
        args = [name, "--pdf-dir", str(tmp_path)]

    def reply(command: list[str], **kwargs: Any):
        return _session_reply(command, kwargs, _clean_verdict())

    monkeypatch.setattr(mr, "_run_reviewer", reply)
    monkeypatch.setattr(mr.shutil, "which", lambda reviewer: f"{reviewer}-test")
    directory = tmp_path / "reports"
    assert mr.main([*args, "--force", "--report-dir", str(directory)]) == 0
    data = json.loads((directory / f"{name}.aggregate.json").read_text(encoding="utf-8"))
    assert data["verdict"] == "SHIP" and len(data["runs"]) == 3
    assert data["judge"]["skipped"]


@pytest.mark.parametrize("args", [
    ["--runs", "0"], ["--pdf", "sheet.pdf"], ["--name", "sample"],
    ["--pdf", "sheet.pdf", "--name", "../sample"],
    ["--pdf", "sheet.pdf", "--name", "sample", "--png", "sheet.png"],
    ["--png", "sheet.png"], ["--png", "sheet.png", "--force"],
])
def test_cli_rejects_invalid_ensemble_inputs(args: list[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        mr._parse_args(args)
    assert exc.value.code == 2


def test_missing_source_still_writes_an_error_aggregate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: Any, **kwargs: Any):
        pytest.fail("a missing source must never invoke a reviewer")

    monkeypatch.setattr(mr, "_run_reviewer", forbidden)
    directory = tmp_path / "reports"
    aggregate = mr.aggregate_package(
        mr.ReviewPackage("missing", "part", (tmp_path / "missing.pdf",)),
        report_dir=directory, runs=1, force=True,
    )
    assert aggregate["verdict"] == "ERROR"
    assert "source snapshot failed" in aggregate["error"]
    assert (directory / "missing.aggregate.json").is_file()
    assert Path(aggregate["runs"][0]["report"]).is_file()


@pytest.mark.parametrize("failure", ["startup", "turn"])
def test_failed_resumed_judge_does_not_reuse_completion_evidence_or_mutate_precheck(
    tmp_path, sdk_transport, failure,
):
    package = mr.ReviewPackage("sample", "part", (_png_source(tmp_path / "sheet.png"),))
    sdk_transport.verdict = {"decision": "review", "skip_kind": "none", "reason": "Inspect sheet."}
    first = mr._review_session(
        package, reviewer="claude", report_dir=tmp_path / "precheck", retries=0,
        precheck_diff={"pages": [{"status": "unchanged", "old_size_points": [10, 10],
                                 "new_size_points": [10, 10], "text_changed": False}]},
    )
    assert first.passed
    initial, = first.extra["evidence"]["attempts"]
    old = initial["transport_provenance"]
    # Completion fields from either adapter must never survive as judge inputs.
    old.update(shutdown="graceful", image_blobs=["a" * 64], omp_command=["old"],
               session_dir="old", omp_effective_options={"old": []})
    session_dir = Path(old["sdk_session_dir"])
    native = session_dir / "precheck.jsonl"
    native.write_text("precheck")
    old["sdk_redacted_files"] = {"sentinel": [1, 2, 3, 4]}
    before = json.dumps(first.extra, sort_keys=True).encode()
    if failure == "startup":
        sdk_transport.status = "failed"
    else:
        sdk_transport.fail = True
    judgment = mr._review_session(
        package, reviewer="claude", report_dir=tmp_path / "judge", retries=0,
        judge_findings=[], resume_review=first,
    )
    assert judgment.error
    record, = judgment.extra["evidence"]["attempts"]
    current = record["transport_provenance"]
    assert record["outcome"] == "failed"
    assert all(name not in current for name in (
        "resolved_model", "shutdown", "image_blobs", "omp_command", "session_dir",
        "omp_effective_options", "omp_prompt", "omp_prompt_sha256",
    ))
    assert current["state_cleanup"] == "removed"
    assert json.dumps(first.extra, sort_keys=True).encode() == before
    assert str(native) in current["sdk_redacted_files"]
    assert str(native) not in old["sdk_redacted_files"]


def test_sdk_environment_preserves_sdk_owned_entrypoint_and_tracing(
    tmp_path, sdk_transport, monkeypatch,
):
    inherited = {
        "TRACEPARENT": "parent-span", "CLAUDE_CODE_ENTRYPOINT": "parent-entrypoint",
        "CLAUDECODE": "1", "PATH": os.environ.get("PATH", ""), "SDK_ENV_CANARY": "inherited",
    }
    for name, value in inherited.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("ANTHROPIC_OAUTH_TOKEN", "must-not-use")
    monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
    review = mr.review_package(
        mr.ReviewPackage("sample", "part", (_png_source(tmp_path / "sheet.png"),)),
        reviewer="claude", report_dir=tmp_path / "reports", retries=0,
    )
    assert review.passed
    overrides = sdk_transport.clients[0].options.env
    assert set(overrides).isdisjoint(inherited)
    assert overrides["ANTHROPIC_OAUTH_TOKEN"] == ""
    assert overrides["CLAUDE_CODE_USE_BEDROCK"] == ""
    assert all(os.environ[name] == value for name, value in inherited.items())
    omp = sdk_transport.transport.environment(inherited=True)
    assert all(omp[name] == value for name, value in inherited.items())
    assert "ANTHROPIC_OAUTH_TOKEN" not in omp and "CLAUDE_CODE_USE_BEDROCK" not in omp


def test_startup_timeout_does_not_relabel_attempt_or_inner_timeouts():
    import machinist_review_transport as transport
    async def invoke():
        for error in (transport.AttemptTimeout(), TimeoutError("inner failure")):
            with pytest.raises(type(error)) as caught:
                async with transport.startup_timeout("broker", 1):
                    raise error
            assert caught.value is error
        with pytest.raises(transport.StartupTimeout) as caught:
            async with transport.startup_timeout("broker", 0.001):
                await asyncio.sleep(1)
        assert caught.value.phase == "broker" and caught.value.budget == 0.001
    asyncio.run(invoke())


def test_omp_broker_exhausted_startup_budget_is_typed_startup_timeout(monkeypatch):
    from contextlib import asynccontextmanager
    import machinist_review_transport as transport
    clock = [0]
    monkeypatch.setattr(transport.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(transport.shutil, "which", lambda name: "/fixture/omp")
    @asynccontextmanager
    async def broker(*args):
        clock[0] = 2
        yield {}
    monkeypatch.setattr(transport, "_broker", broker)
    with pytest.raises(transport.StartupTimeout) as caught:
        asyncio.run(transport._omp(register_secret=lambda value: None, remaining=lambda: 20, startup=1))
    assert caught.value.phase == "OMP sheets MCP connection"
    assert caught.value.budget == 1


@pytest.mark.parametrize("failure", ["write_error", "attempt_deadline"])
def test_quota_state_write_failure_is_retained_without_extending_attempt(
    tmp_path, sdk_transport, monkeypatch, failure,
):
    from machinist_review_credentials import CredentialPool
    transport = sdk_transport.transport
    sdk_transport.quota = True
    logs = []
    monkeypatch.setattr(transport._telemetry, "error", lambda event, **fields: logs.append((event, fields)))
    def failed_write(self, *args):
        if failure == "write_error":
            raise OSError("state storage failed")
        raise BlockingIOError("state busy")
    monkeypatch.setattr(CredentialPool, "unavailable", failed_write)
    started = mr.time.monotonic()
    review = mr.review_package(
        mr.ReviewPackage("sample", "part", (_png_source(tmp_path / "sheet.png"),)),
        reviewer="claude", report_dir=tmp_path / "reports", retries=0,
        timeout_s=0.1 if failure == "attempt_deadline" else 10,
    )
    assert review.error
    record, = review.extra["evidence"]["attempts"]
    route, = record["transport_provenance"]["routes"]
    assert route["outcome"] == "quota" and route["quota_state_write"] == "failed"
    assert route["quota_state_write_error"] in {"OSError", "AttemptTimeout", "CancelledError"}
    assert any(event == "machinist_review.quota_state_write" and fields["outcome"] == "failed"
               for event, fields in logs)
    if failure == "attempt_deadline":
        assert mr.time.monotonic() - started < 2
        assert record["transport_provenance"]["timeout_phase"] == "attempt"


def test_invalid_api_key_is_configuration_failure_not_quota():
    import machinist_review_transport as transport
    assert transport.quota_event({"type": "assistant", "error": "authentication_failed",
                                  "api_error_status": 401, "message": {"content": [
                                      {"type": "text", "text": "Invalid API key"}]}}) is None


@pytest.mark.parametrize("failed_transport", ["claude_agent_sdk", "omp"])
def test_failed_routed_successor_does_not_inherit_predecessor_execution_evidence(
    tmp_path, sdk_transport, monkeypatch, failed_transport,
):
    transport = sdk_transport.transport
    stale = {
        "resolved_model": {"provider": "anthropic", "id": "predecessor-model"},
        "sdk_isolation": {"predecessor": True}, "omp_command": ["predecessor"],
        "omp_effective_options": {"predecessor": True}, "omp_prompt": "predecessor",
        "omp_prompt_sha256": "a" * 64, "shutdown": "graceful",
        "image_blobs": ["b" * 64], "session_dir": "predecessor",
    }
    calls = []
    def assert_clean(provenance):
        assert set(stale).isdisjoint(provenance)
        assert provenance["private_home"]
    async def sdk(**kwargs):
        provenance = kwargs["provenance"]
        assert_clean(provenance)
        calls.append("claude_agent_sdk")
        if failed_transport == "claude_agent_sdk" and len(calls) == 2:
            raise RuntimeError("successor startup failed")
        provenance.update(stale)
        return {"status": "exhausted", "retryAt": None, "reason": "credit-balance"}
    async def omp(**kwargs):
        assert_clean(kwargs["provenance"])
        calls.append("omp")
        raise RuntimeError("successor startup failed")
    monkeypatch.setattr(transport, "_sdk", sdk)
    monkeypatch.setattr(transport, "_omp", omp)
    review = mr.review_package(
        mr.ReviewPackage("sample", "part", (_png_source(tmp_path / "sheet.png"),)),
        reviewer="claude", report_dir=tmp_path / "reports", retries=0,
    )
    assert review.error and "successor startup failed" in review.error
    record, = review.extra["evidence"]["attempts"]
    provenance = record["transport_provenance"]
    assert_clean(provenance)
    assert provenance["transport"] == failed_transport
    expected_quota_routes = 1 if failed_transport == "claude_agent_sdk" else 3
    assert calls == ["claude_agent_sdk"] * expected_quota_routes + [failed_transport]
    assert [route["outcome"] for route in provenance["routes"]] == (
        ["quota"] * expected_quota_routes + ["failed"]
    )
    assert all(route["quota_state_write"] == "persisted"
               for route in provenance["routes"][:-1])
