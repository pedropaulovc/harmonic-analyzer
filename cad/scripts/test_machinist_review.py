"""Offline contracts for the blind machinist review runner and its sheet server."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import re
import struct
import sys
import threading
import tomllib
from pathlib import Path
from typing import Any, Sequence

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from PIL import Image, ImageDraw

import machinist_review as mr
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


def test_claude_command_exposes_only_the_sheet_tools(tmp_path: Path) -> None:
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps(mr.load_schema()), encoding="utf-8")
    mcp_config = tmp_path / "mcp.json"
    mcp_config.write_text("{}", encoding="utf-8")
    session_id = "2f4a6c8e-1111-4222-8333-444455556666"
    command = mr.build_claude_command(
        workdir=tmp_path,
        mcp_config=mcp_config,
        schema=schema,
        model="fable",
        effort="high",
        session_id=session_id,
    )

    assert command[:2] == ["claude", "-p"]
    assert _flag(command, "--model") == "fable"
    assert _flag(command, "--effort") == "high"
    assert _flag(command, "--output-format") == "stream-json"
    assert json.loads(_flag(command, "--json-schema")) == mr.load_schema()
    assert _flag(command, "--tools") == ""  # every built-in tool disabled
    start = command.index("--allowedTools") + 1
    end = next(
        (i for i in range(start, len(command)) if command[i].startswith("--")),
        len(command),
    )
    allowed = {name for value in command[start:end] for name in value.split(",") if name}
    assert allowed == SHEET_TOOLS
    assert (tmp_path / _flag(command, "--mcp-config")).resolve() == mcp_config.resolve()
    assert _flag(command, "--session-id") == session_id
    assert _flag(command, "--permission-mode") == "dontAsk"
    assert _flag(command, "--permission-prompts") == "none"
    assert _flag(command, "--setting-sources") == ""
    for flag in ("--restricted", "--strict-mcp-config", "--no-chrome", "--disable-slash-commands"):
        assert flag in command
    # --safe-mode disables MCP; isolation comes from explicit settings instead.
    assert "--safe-mode" not in command
    settings = json.loads(_flag(command, "--settings"))
    assert settings["disableAllHooks"] is True
    assert settings["autoMemoryEnabled"] is False
    assert settings["claudeMdExcludes"] == ["**"]
    assert not any(settings["enabledPlugins"].values())
    assert all(value == "1" for value in settings["env"].values())
    assert not any("Read" in value or ".png" in value for value in command)
    assert mr.CAD_ROOT.parent.as_posix() not in " ".join(command).replace("\\", "/")


def test_codex_command_enables_only_the_auto_approved_sheet_server(
    tmp_path: Path,
) -> None:
    sources = (tmp_path / "drawing.pdf", tmp_path / "sheet.png")
    schema = tmp_path / "schema.json"
    output = tmp_path / "verdict.json"
    command = mr.build_codex_command(
        workdir=tmp_path,
        sources=sources,
        schema=schema,
        output=output,
        model="gpt-6-astra",
        effort="low",
    )

    assert command[:2] == ["codex", "exec"]
    for flag in ("--ignore-user-config", "--ignore-rules", "--skip-git-repo-check", "--json"):
        assert flag in command
    assert _flag(command, "--sandbox") == "read-only"
    assert _flag(command, "-C") == str(tmp_path)
    assert _flag(command, "-m") == "gpt-6-astra"
    assert _flag(command, "--output-schema") == str(schema)
    assert _flag(command, "-o") == str(output)
    assert command[-1] == "-"
    assert "-i" not in command  # sheets arrive only through the MCP server

    overrides = _codex_overrides(command)
    assert overrides["model_reasoning_effort"] == "low"
    assert overrides["approval_policy"] == "never"
    for feature in ("shell_tool", "apply_patch_freeform", "view_image"):
        assert overrides[f"features.{feature}"] is False
    assert overrides["web_search"] == "disabled"
    assert overrides["mcp_servers.sheets.command"] == sys.executable
    script, *server_sources = overrides["mcp_servers.sheets.args"]
    assert Path(script).resolve() == Path(sheets.__file__).resolve()
    assert [Path(value) for value in server_sources] == [
        source.resolve() for source in sources
    ]
    # "auto" still blocks MCP calls under approval_policy=never.
    assert overrides["mcp_servers.sheets.default_tools_approval_mode"] == "approve"
    assert overrides["mcp_servers.sheets.enabled_tools"] == ["view_sheet", "crop"]
    assert not any(key.startswith("mcp_servers.") and not key.startswith(
        "mcp_servers.sheets.") for key in overrides)


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
            assert package.name not in tail
            tails.setdefault(package.kind, set()).add(tail)
    # The tail varies only with sheet count, never with name or reviewer.
    assert len(tails["part"]) == 2 and len(tails["assembly"]) == 2

    override = "custom rubric\n"
    package = mr.ReviewPackage("crank_arm", "part", ())
    assert mr._review_prompt(package, 2, prompt_text=override).startswith(override)


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
        "inspection_proven": True,
    }


_REJECTED_CALLS: dict[str, dict[str, list[dict[str, Any]]]] = {
    "claude": {
        "read": _claude_call("Read", {"file_path": "sheet-1.png"}, "bad"),
        "shell": _claude_call("Bash", {"command": "dir"}, "bad"),
        "unknown_sheets_tool": _claude_call("mcp__sheets__list_files", {}, "bad"),
        "unknown_server": _claude_call("mcp__files__view_sheet", {"sheet": 1}, "bad"),
        "view_below_range": _claude_call("view_sheet", {"sheet": 0}, "bad"),
        "view_above_range": _claude_call("view_sheet", {"sheet": 4}, "bad"),
        "crop_above_range": _claude_call(
            "crop", {"sheet": 4, "x1": 0, "y1": 0, "x2": 9, "y2": 9}, "bad"
        ),
        "view_string_sheet": _claude_call("view_sheet", {"sheet": "1"}, "bad"),
        "crop_missing_corner": _claude_call(
            "crop", {"sheet": 1, "x1": 0, "y1": 0, "x2": 9}, "bad"
        ),
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
        "unknown_sheets_tool": _codex_call("list_files", {}, "bad"),
        "unknown_server": _codex_call("view_sheet", {"sheet": 1}, "bad", server="files"),
        "view_below_range": _codex_call("view_sheet", {"sheet": 0}, "bad"),
        "view_above_range": _codex_call("view_sheet", {"sheet": 4}, "bad"),
        "crop_above_range": _codex_call(
            "crop", {"sheet": 4, "x1": 0, "y1": 0, "x2": 9, "y2": 9}, "bad"
        ),
        "view_string_sheet": _codex_call("view_sheet", {"sheet": "1"}, "bad"),
        "crop_missing_corner": _codex_call(
            "crop", {"sheet": 1, "x1": 0, "y1": 0, "x2": 9}, "bad"
        ),
    },
}


@pytest.mark.parametrize(
    ("reviewer", "case"),
    [(reviewer, case) for reviewer, cases in _REJECTED_CALLS.items() for case in cases],
)
def test_evidence_rejects_every_other_tool_and_out_of_range_sheet(
    reviewer: str, case: str
) -> None:
    events = [*_views(reviewer, (1, 2, 3)), *_REJECTED_CALLS[reviewer][case]]

    evidence = mr.evaluate_sheet_evidence(events, reviewer=reviewer, sheet_count=3)

    assert evidence["tool_events"] >= 1
    assert evidence["sheets_viewed"] == [1, 2, 3]  # rejected calls never prove views
    assert evidence["crop_calls"] == 0 and evidence["crops"] == []


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
    # The text-only grader has no sheets, so even the sheet server is a tool.
    assert mr.count_codex_tool_events(_views("codex", (1,))) == 1


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
    usage = mr._usage(codex_events, "codex")
    assert {key: usage[key] for key in (
        "input_tokens", "cached_input_tokens", "output_tokens"
    )} == {"input_tokens": 42015, "cached_input_tokens": 26756, "output_tokens": 162}


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
def test_attempt_workdir_is_neutral_then_retained_without_sheet_images(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reviewer: str
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
        seen["files"] = sorted(path.name for path in cwd.rglob("*"))
        if reviewer == "claude":
            config_path = cwd / _flag(command, "--mcp-config")
            seen["config"] = json.loads(config_path.read_text(encoding="utf-8"))
            stdout = _claude_stdout(3, _clean_verdict())
        else:
            assert _flag(command, "-C") == str(cwd)
            seen["overrides"] = _codex_overrides(command)
            Path(_flag(command, "-o")).write_text(
                json.dumps(_clean_verdict()), encoding="utf-8"
            )
            stdout = _codex_stdout(3)
        return mr.subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(mr.subprocess, "run", fake_run)
    package = mr.ReviewPackage("package", "assembly", sources)
    review = mr.review_package(
        package, reviewer=reviewer, report_dir=report_dir, retries=0,
        claude="claude-test", codex="codex-test",
    )

    assert review.passed and review.blind
    assert review.sheet_count == 3
    assert review.extra["sheets_viewed"] == [1, 2, 3]
    assert review.extra["inspection_proven"] is True
    assert review.extra["crop_calls"] == 0 and review.extra["crops"] == []
    assert not seen["cwd"].is_relative_to(report_dir)
    expected_inputs = {"schema.json", "mcp.json"} if reviewer == "claude" else {"schema.json"}
    assert set(seen["files"]) == expected_inputs  # no sheet PNGs to read
    server_sources = [str(source.resolve()) for source in sources]
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

    saved = json.loads((report_dir / "package.json").read_text(encoding="utf-8"))
    (record,) = saved["extra"]["evidence"]["attempts"]
    assert record["cwd"] == str(seen["cwd"])
    assert not Path(record["cwd"]).exists()
    retained = Path(record["retained_cwd"])
    assert retained.is_dir()
    assert retained.parent == report_dir / "package.attempts"
    assert retained.name == seen["cwd"].name and retained.name.startswith("machrev-")
    assert expected_inputs <= {path.name for path in retained.iterdir()}
    assert not list(retained.rglob("*.png"))
    assert Path(record["stdout_file"]).parent == retained
    assert record["sources"] == server_sources
    rerun = record["rerun_command"]
    assert len(rerun) == len(record["command"])
    assert not any(record["cwd"] in argument for argument in rerun)
    if reviewer == "claude":
        assert Path(_flag(rerun, "--mcp-config")) == retained / "mcp.json"
    else:
        assert _flag(rerun, "-C") == str(retained)
        assert Path(_flag(rerun, "-o")) == retained / "verdict.json"
        assert Path(_flag(rerun, "--output-schema")) == retained / "schema.json"
        assert [Path(path) for path in record["artifacts"]] == [retained / "verdict.json"]


def test_attempt_records_carry_session_id_and_resume_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import uuid

    source = _png_source(tmp_path / "page.png")
    verdict = _clean_verdict()
    thread_id = "0199c0de-1234-4abc-9def-0123456789ab"
    calls = 0

    def fake_run(command: list[str], **_kwargs: object):
        nonlocal calls
        calls += 1
        if command[0] == "codex-test":
            output = Path(command[command.index("-o") + 1])
            output.write_text(json.dumps(verdict), encoding="utf-8")
            stdout = _codex_stdout(1, thread_id)
            return mr.subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
        if calls == 1:
            return mr.subprocess.CompletedProcess(command, 1, stdout="", stderr="failed")
        stdout = _claude_stdout(1, verdict)
        return mr.subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(mr.subprocess, "run", fake_run)
    package = mr.ReviewPackage("package", "part", (source,))
    mr.review_package(
        package,
        reviewer="claude",
        report_dir=tmp_path / "claude",
        retries=1,
        claude="claude-test",
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
    claude_ids = [record["session_id"] for record in claude_attempts]
    assert len(set(claude_ids)) == 2  # fresh session per attempt: no prior context
    for record, session_id in zip(claude_attempts, claude_ids):
        assert uuid.UUID(session_id).version == 4
        command = record["command"]
        assert command[command.index("--session-id") + 1] == session_id
        assert record["resume_command"] == f"claude --resume {session_id}"

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

    monkeypatch.setattr(subprocess, "run", fake_run)
    report_dir = tmp_path / "reports"
    review = mr.review_package(
        mr.ReviewPackage("part", "part", (png,)),
        reviewer="claude",
        report_dir=report_dir,
        retries=1,
        claude="claude",
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    png = _png_source(tmp_path / "source.png")
    report_dir = tmp_path / "reports"
    calls = 0
    failed_stdout = 'diagnostic before JSON\n{"type": "turn.failed"}\n'
    failed_stderr = "reviewer diagnostic: interrupted response\n"
    invalid_verdict = "incomplete response, not JSON"
    success_events = _codex_events(1)
    success_stdout = "\n".join(json.dumps(event) for event in success_events) + "\n"

    def fake_run(command: list[str], **kwargs: Any):
        nonlocal calls
        calls += 1
        output = Path(command[command.index("-o") + 1])
        if calls == 1:
            output.write_text(invalid_verdict, encoding="utf-8")
            session = Path(kwargs["cwd"]) / "session"
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
        output.write_text(json.dumps(_clean_verdict()), encoding="utf-8")
        return mr.subprocess.CompletedProcess(
            command, 0, stdout=success_stdout, stderr=""
        )

    monkeypatch.setattr(mr.subprocess, "run", fake_run)
    review = mr.review_package(
        mr.ReviewPackage("part", "part", (png,)),
        reviewer="codex",
        report_dir=report_dir,
        retries=1,
        codex="codex-test",
    )

    assert review.passed and review.blind
    assert review.error is None
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
    assert Path(failed["stdout_file"]).read_text(encoding="utf-8") == failed_stdout
    assert Path(failed["stderr_file"]).read_text(encoding="utf-8") == failed_stderr
    artifacts = {Path(path).name: Path(path) for path in failed["artifacts"]}
    assert artifacts["verdict.json"].read_text(encoding="utf-8") == invalid_verdict
    assert (artifacts["session"] / "trace.txt").read_text(encoding="utf-8") == (
        "failed attempt trace"
    )
    assert succeeded["outcome"] == "succeeded"
    assert succeeded["error"] is None
    assert succeeded["exit_code"] == 0
    assert Path(succeeded["stdout_file"]).read_text(encoding="utf-8") == success_stdout
    assert Path(succeeded["stderr_file"]).read_bytes() == b""
    success_artifacts = {Path(path).name: Path(path) for path in succeeded["artifacts"]}
    assert json.loads(
        success_artifacts["verdict.json"].read_text(encoding="utf-8")
    ) == (_clean_verdict())
    assert failed["retained_cwd"] != succeeded["retained_cwd"]
    for record in (failed, succeeded):
        assert not Path(record["cwd"]).exists()
        retained = Path(record["retained_cwd"])
        assert retained.is_dir() and retained.is_relative_to(report_dir)
        for path in (
            record["stdout_file"],
            record["stderr_file"],
            *record["artifacts"],
        ):
            assert Path(path).parent == retained
            assert Path(path).exists()
    events = [
        json.loads(line)
        for line in Path(review.events_file).read_text(encoding="utf-8").splitlines()
    ]
    assert events == [
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

    monkeypatch.setattr(mr.subprocess, "run", fake_run)
    review = mr.review_package(
        mr.ReviewPackage("part", "part", (png,)),
        reviewer="claude",
        report_dir=tmp_path / "reports",
        retries=1,
        claude="claude",
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
    import subprocess
    from concurrent.futures import ThreadPoolExecutor

    verdict = _clean_verdict()

    def fake_run(command, **_kwargs):
        output = Path(command[command.index("-o") + 1])
        output.write_text(json.dumps(verdict), encoding="utf-8")
        return subprocess.CompletedProcess(
            command, 0, stdout=_codex_stdout(1), stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
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
    import subprocess

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
        output = Path(command[command.index("-o") + 1])
        output.write_text(json.dumps(verdict), encoding="utf-8")
        return subprocess.CompletedProcess(
            command, 0, stdout=_codex_stdout(2), stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
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
        str(source.resolve())
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
    import subprocess
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
        output = Path(command[command.index("-o") + 1])
        output.write_text(json.dumps(verdict), encoding="utf-8")
        return subprocess.CompletedProcess(
            command, 0, stdout=_codex_stdout(2), stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
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
    assert mr.main([]) == 2
    assert capsys.readouterr().err == (
        "--reviewer is required for review runs (choose claude or codex)\n"
    )

    assert mr.main(["--reviewer", "codex"]) == 2
    assert capsys.readouterr().err == (
        "no drawing names given; use --all, --png or a name\n"
    )

    assert mr.main(["--reviewer", "codex", "not-a-drawing"]) == 2
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

    def fake_run(command: list[str], **kwargs: object):
        commands.append(command)
        if command[0] == "codex-test":
            output = Path(command[command.index("-o") + 1])
            output.write_text(json.dumps(verdict), encoding="utf-8")
            stdout = _codex_stdout(2)
        else:
            stdout = _claude_stdout(2, verdict)
        return mr.subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(mr.subprocess, "run", fake_run)
    package = mr.ReviewPackage("package", "assembly", sources)
    claude_review = mr.review_package(
        package,
        reviewer="claude",
        report_dir=tmp_path / "claude",
        retries=0,
        claude="claude-test",
    )
    codex_review = mr.review_package(
        package,
        reviewer="codex",
        report_dir=tmp_path / "codex",
        retries=0,
        codex="codex-test",
    )

    assert (claude_review.model, claude_review.effort) == ("claude-fable-5-1", "medium")
    assert (codex_review.model, codex_review.effort) == ("gpt-6-astra", "low")
    assert claude_review.blind and codex_review.blind
    assert claude_review.passed and codex_review.passed
    assert claude_review.extra["sheets_viewed"] == [1, 2]
    assert codex_review.extra["sheets_viewed"] == [1, 2]
    assert len(commands) == 2
    assert "-i" not in commands[1]


# --- sheet server --------------------------------------------------------------


def test_sheet_constants_match_the_measured_cli_contract() -> None:
    assert sheets.VIEW_BOX == (1976, 1280)
    assert sheets.MAX_SCALE == 8
    assert sheets.CROP_BUDGET == 40


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
    assert mr._PDFIUM_LOCK is sheets.PDFIUM_LOCK
    assert mr.SheetStore is sheets.SheetStore

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
