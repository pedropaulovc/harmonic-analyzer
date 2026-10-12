r"""Blind senior-machinist review of drawing packages via Claude or Codex.

The review the fleet is gated on (``cad/docs/drawing-simplicity-policy.md``):
each package is handed to an isolated CLI in a neutral attempt directory.
A private stdio MCP server supplies grayscale whole-sheet views fitting
1976×1280 pixels (about 118 dpi on 11×17 sheets) and vector-PDF region crops.
The cached prompt prefix is the shared drawing standard followed by the kind's
reviewer instructions; package-specific instructions come last.
``--reviewer`` is mandatory
and MUST name a different model family from the agent that authored or last
edited the drawing script: a Claude-driven session (Fable, Opus, Sonnet)
reviews with ``--reviewer codex``, a Codex/GPT-driven session with
``--reviewer claude``. A same-family verdict is not the gate, even a ``SHIP``.
PDF pages and PNG inputs are supplied in sheet order through ``view_sheet``;
``crop`` confirms fine details, with 8× magnification and 40 calls per attempt.
The schema-validated verdict and provenance are written under
``cad/out/reports/machinist-review/``.

Why the prompt is calibrated the way it is: the earlier ad-hoc reviews asked a
"senior machinist" to hunt for MISSING tolerances / datums / finishes and were
rewarded for gaps, so the fleet grew inspection-package GD&T on hand-crank
parts. Authors and reviewers now share one standard, distilled from Harvey
(*Machine Shop Trade Secrets*, ch. 9) and Lipton (*Metalworking Sink or Swim*,
ch. 2-3): the title block is the general spec and over-specification is a
defect as much as a missing dimension.

Claude disables built-in tools and user/project customizations; Codex ignores
user configuration/rules and disables configurable shell, image and web tools.
Only the private ``sheets`` MCP server is configured. Attempt directories hold
the schema, Claude's MCP configuration and outputs, never sheet PNGs. The event
stream rejects any other tool, and proves every sheet was viewed successfully
in the verdict-producing attempt. Crop coordinates, token/cache usage and first
Claude-turn cache usage are retained with the verdict.
Blindness does not depend on ephemerality: fresh sessions never load prior
context, and both the CLI transcript and attempt directory are retained. Attempt
records include the session id and a ready-to-run ``claude --resume <id>`` or
``codex resume <id>`` command so completed reasoning can be reopened offline.

Usage (SolidWorks-free; PDFs in ``cad/out/pdf`` or ``--pdf-dir``)::

    uv run cad/scripts/machinist_review.py crank_arm pivot_shaft
    uv run cad/scripts/machinist_review.py --all --jobs 4
    uv run cad/scripts/machinist_review.py --png sheet-1.png --png sheet-2.png --kind assembly
    uv run cad/scripts/machinist_review.py ch_pivot_shaft --pdf-dir release/pdf --reviewer codex
    uv run cad/scripts/machinist_review.py --index      # rebuild index.md only

Exit status is 0 only when every reviewed package passes (``SHIP`` with no
blocker, over-specification or clarity finding).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from _drawing_registry import DRAWINGS, DRAWINGS_BY_NAME, CAD_ROOT  # noqa: E402
from machinist_review_sheets_mcp import PDFIUM_LOCK as _PDFIUM_LOCK, SheetStore  # noqa: E402

PROMPTS_DIR = SCRIPTS_DIR / "prompts"
GUIDELINES_FILE = CAD_ROOT / "docs" / "drawing-guidelines.md"
PROMPT_FILES = {
    "part": PROMPTS_DIR / "machinist_review_part.md",
    "assembly": PROMPTS_DIR / "machinist_review_assembly.md",
}
SCHEMA_FILE = PROMPTS_DIR / "machinist_review_schema.json"
REPORT_DIR = CAD_ROOT / "out" / "reports" / "machinist-review"

DEFAULT_MODELS = {
    "claude": "claude-fable-5-1",
    "codex": "gpt-6-astra",
}
DEFAULT_EFFORTS = {
    "claude": "medium",
    "codex": "low",
}
REVIEWERS = tuple(DEFAULT_MODELS)
FINDING_KEYS = ("blockers", "over_specification", "clarity", "minor")
GATING_KEYS = ("blockers", "over_specification", "clarity")
# Tool descriptors and isolation settings are static across packages, so neither
# source paths nor sheet counts disturb the model's cached tool/prompt prefix.
SHEETS_SERVER = SCRIPTS_DIR / "machinist_review_sheets_mcp.py"
CLAUDE_ISOLATION_SETTINGS = {
    "disableAllHooks": True,
    "autoMemoryEnabled": False,
    "claudeMdExcludes": ["**"],
    "disableBundledSkills": True,
    "syncClaudeAiPlugins": False,
    "syncClaudeAiSkills": False,
    "enabledPlugins": {
        "cc-plugin-agents-md@builtin": False,
        "cc-plugin-telemetry@builtin": False,
        "cc-plugin-plugin-authoring@builtin": False,
    },
    "env": {
        "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1",
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
        "CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS": "1",
    },
}
_TOOL_EVENT_MARKERS = (
    "command_execution",
    "function_call",
    "tool_call",
    "tool_use",
    "mcp_tool_call",
    "exec_command",
    "local_shell",
    "web_search",
    "file_change",
    "shell",
    "view_image",
    "image_view",
    "apply_patch",
)


@dataclass(frozen=True)
class ReviewPackage:
    name: str
    kind: str  # "part" | "assembly"
    sources: tuple[Path, ...]


@dataclass
class Review:
    name: str
    kind: str
    sources: list[str]
    source_sha256: list[str]
    verdict: dict[str, Any] | None
    passed: bool
    blind: bool
    tool_events: int
    reviewer: str
    model: str
    effort: str
    prompt_sha256: str
    sheet_count: int
    duration_s: float
    reviewed_at: str
    error: str | None = None
    events_file: str | None = None
    attempts: int = 1
    extra: dict[str, Any] = field(default_factory=dict)


def package_for(name: str) -> ReviewPackage:
    spec = DRAWINGS_BY_NAME[name]
    source = spec.outputs["pdf"]
    return ReviewPackage(name=name, kind=spec.source_kind, sources=(source,))


def all_packages() -> list[ReviewPackage]:
    return [package_for(spec.name) for spec in DRAWINGS]


def load_prompt(kind: str) -> str:
    """The shared drawing guidelines followed by the kind's reviewer instructions."""
    guidelines = GUIDELINES_FILE.read_text(encoding="utf-8").rstrip()
    reviewer = PROMPT_FILES[kind].read_text(encoding="utf-8")
    return f"{guidelines}\n\n{reviewer}"


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package_for_pngs(paths: Sequence[Path], kind: str) -> ReviewPackage:
    resolved = tuple(path.resolve() for path in paths)
    identity = "\0".join(path.as_posix().casefold() for path in resolved).encode()
    suffix = hashlib.sha256(identity).hexdigest()[:16]
    stem = resolved[0].stem if len(resolved) == 1 else f"{kind}-package"
    return ReviewPackage(
        name=f"{stem}-{suffix}",
        kind=kind,
        sources=resolved,
    )


def _sheet_count(package: ReviewPackage) -> int:
    # The harness and MCP server share source expansion and rendering definitions.
    with SheetStore(package.sources) as sheets:
        return sheets.sheet_count


def _validate_package(package: ReviewPackage) -> int:
    if package.kind not in PROMPT_FILES:
        raise ValueError(f"{package.name}: unknown review kind {package.kind!r}")
    if not package.sources:
        raise ValueError(f"{package.name}: review package has no sheets")
    for source in package.sources:
        if not source.is_file():
            raise FileNotFoundError(f"{package.name}: review source missing: {source}")
        suffix = source.suffix.casefold()
        if suffix not in {".pdf", ".png"}:
            raise ValueError(f"{package.name}: expected PNG or PDF source: {source}")
    sheet_count = _sheet_count(package)
    return sheet_count

def _review_prompt(
    package: ReviewPackage,
    sheet_count: int,
    *,
    reviewer: str = "codex",
    prompt_text: str | None = None,
) -> str:
    prompt = load_prompt(package.kind) if prompt_text is None else prompt_text
    prompt += (
        "\n\nPACKAGE INPUT\n"
        f"Sheet count: {sheet_count}.\n"
        f"Call view_sheet for sheets 1..{sheet_count} in order before judging.\n"
    )
    if sheet_count > 1:
        prompt += (
            "Compare every sheet against every other sheet before accepting SHIP.\n"
        )
    return prompt + "Return one verdict for the package as a whole.\n"


def build_claude_command(
    *,
    workdir: Path,
    mcp_config: Path,
    schema: Path,
    model: str,
    effort: str,
    session_id: str,
    claude: str = "claude",
    schema_content: str | None = None,
) -> list[str]:
    """Return the exact isolated ``claude -p`` argv for one package."""
    if schema.parent != workdir or mcp_config.parent != workdir:
        raise ValueError("review configuration must be inside the neutral workdir")
    schema_json = json.dumps(
        json.loads(
            schema.read_text(encoding="utf-8")
            if schema_content is None
            else schema_content
        ),
        separators=(",", ":"),
    )
    return [
        claude,
        "-p",
        "--model",
        model,
        "--effort",
        effort,
        "--input-format",
        "text",
        "--output-format",
        "stream-json",
        "--verbose",
        "--json-schema",
        schema_json,
        "--tools",
        "",
        "--allowedTools",
        "mcp__sheets__view_sheet,mcp__sheets__crop",
        "--restricted",
        "--setting-sources",
        "",
        "--disable-slash-commands",
        "--settings",
        json.dumps(CLAUDE_ISOLATION_SETTINGS, separators=(",", ":")),
        "--mcp-config",
        str(mcp_config),
        "--session-id",
        session_id,
        "--permission-mode",
        "dontAsk",
        "--permission-prompts",
        "none",
        "--strict-mcp-config",
        "--no-chrome",
    ]


def build_codex_command(
    *,
    workdir: Path,
    sources: Sequence[Path],
    schema: Path,
    output: Path,
    model: str,
    effort: str,
    codex: str = "codex",
) -> list[str]:
    """Return the exact isolated ``codex exec`` argv for one package."""
    if not sources or any(path.parent != workdir for path in (schema, output)):
        raise ValueError("review configuration and output must be inside the neutral workdir")
    command = [
        codex,
        "exec",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "-C",
        str(workdir),
        "-m",
        model,
        "-c",
        f"model_reasoning_effort={effort}",
    ]
    overrides = {
        "approval_policy": "never",
        "features.shell_tool": False,
        "features.apply_patch_freeform": False,
        # This disables the freeform variant, not every model's patch tool.
        # The event gate rejects any residual builtin call, including patches.
        "features.view_image": False,
        "features.tool_search": False,
        "features.tool_search_always_defer_mcp_tools": False,
        "agents.enabled": False,
        "features.multi_agent_v2": False,
        "web_search": "disabled",
        "mcp_servers.sheets.command": sys.executable,
        "mcp_servers.sheets.args": [str(SHEETS_SERVER), *(str(p.resolve()) for p in sources)],
        # "auto" still requests approval for unannotated MCP tools in exec.
        # "approve" is Codex's explicit automatic-approval policy.
        "mcp_servers.sheets.default_tools_approval_mode": "approve",
        "mcp_servers.sheets.enabled_tools": ["view_sheet", "crop"],
    }
    for key, value in overrides.items():
        command.extend(("-c", f"{key}={json.dumps(value)}"))
    command.extend(
        (
            "--output-schema",
            str(schema),
            "-o",
            str(output),
            "--json",
            "-",
        )
    )
    return command


def _walk(obj: Any) -> Iterable[Any]:
    yield obj
    if isinstance(obj, dict):
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk(value)


def _tool_nodes(obj: Any) -> Iterable[dict[str, Any]]:
    """Find calls, not command-like fields inside their arguments or results."""
    if isinstance(obj, dict):
        kind = str(obj.get("type", "")).lower()
        if (
            obj.get("command")
            or any(marker in kind for marker in _TOOL_EVENT_MARKERS)
            or kind.endswith("_call")
        ):
            yield obj
            return
        for value in obj.values():
            yield from _tool_nodes(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _tool_nodes(value)


def evaluate_sheet_evidence(
    events: Sequence[dict[str, Any]], *, reviewer: str, sheet_count: int
) -> dict[str, Any]:
    """Fail closed on tools other than bounded sheet inspection.

    Codex announces the same call at start and completion; count it once.
    A view proves inspection only when its successful result contains an image.
    Attempt tags keep repeated tool ids in separate attempts distinct.
    """
    if reviewer not in REVIEWERS:
        raise ValueError(f"unknown reviewer {reviewer!r}")
    image_results: set[tuple[int, str]] = set()
    for row in events:
        attempt = row.get("attempt", 0)
        for node in _walk(row.get("event", row)):
            if (
                isinstance(node, dict)
                and node.get("type") == "tool_result"
                and not node.get("is_error")
                and any(
                    isinstance(part, dict) and part.get("type") == "image"
                    for part in (node.get("content") or [])
                )
            ):
                image_results.add((attempt, str(node.get("tool_use_id", ""))))

    unauthorized: set[tuple[Any, ...]] = set()
    crop_ids: set[tuple[Any, ...]] = set()
    views: set[int] = set()
    crops: list[dict[str, Any]] = []
    for event_index, row in enumerate(events):
        attempt = row.get("attempt", 0)
        event = row.get("event", row)
        nodes = _tool_nodes(event)
        if (
            reviewer == "codex"
            and isinstance(event, dict)
            and event.get("type") in {"item.started", "item.updated", "item.completed"}
            and isinstance(event.get("item"), dict)
        ):
            item = event["item"]
            # Tool items such as todo_list have no "tool"/"call" marker.
            # Only these explicit non-tool item kinds may bypass the allowlist.
            nodes = () if item.get("type") in {"agent_message", "reasoning", "error"} else (item,)
        for node_index, node in enumerate(nodes):
            kind = str(node.get("type", "")).lower()
            identity = (
                (attempt, kind, str(node["id"]))
                if node.get("id")
                else (attempt, event_index, node_index)
            )
            tool = None
            arguments = None
            successful = False
            if reviewer == "claude" and kind == "tool_use":
                name = node.get("name")
                if name == "StructuredOutput":
                    continue
                if name in {"mcp__sheets__view_sheet", "mcp__sheets__crop"}:
                    tool = str(name).removeprefix("mcp__sheets__")
                    arguments = node.get("input")
                    successful = (attempt, str(node.get("id", ""))) in image_results
            elif (
                reviewer == "codex"
                and kind == "mcp_tool_call"
                and node.get("server") == "sheets"
                and node.get("tool") in {"view_sheet", "crop"}
            ):
                tool = node["tool"]
                arguments = node.get("arguments")
                result = node.get("result")
                successful = (
                    node.get("status") == "completed"
                    and not node.get("error")
                    and isinstance(result, dict)
                    and not result.get("isError")
                    and any(
                        isinstance(part, dict) and part.get("type") == "image"
                        for part in (result.get("content") or [])
                    )
                )
            keys = {"sheet"} if tool == "view_sheet" else {"sheet", "x1", "y1", "x2", "y2"}
            valid = (
                tool is not None
                and isinstance(arguments, dict)
                and set(arguments) == keys
                and all(type(value) is int for value in arguments.values())
                and 1 <= arguments["sheet"] <= sheet_count
            )
            if not valid:
                unauthorized.add(identity)
                continue
            sheet = arguments["sheet"]
            if tool == "view_sheet" and successful:
                views.add(sheet)
            elif tool == "crop" and identity not in crop_ids:
                crop_ids.add(identity)
                crops.append({
                    "sheet": sheet,
                    "rect": [arguments[key] for key in ("x1", "y1", "x2", "y2")],
                })
    return {
        "tool_events": len(unauthorized),
        "sheets_viewed": sorted(views),
        "crop_calls": len(crop_ids),
        "crops": crops,
        "inspection_proven": sheet_count > 0 and views == set(range(1, sheet_count + 1)),
    }


def count_codex_tool_events(events: Sequence[dict[str, Any]]) -> int:
    """The benchmark's text-only grader permits no sheet or other tools."""
    return evaluate_sheet_evidence(events, reviewer="codex", sheet_count=0)["tool_events"]


def _usage(events: Sequence[dict[str, Any]], reviewer: str) -> dict[str, Any]:
    """Retain CLI usage, including the first Claude assistant-turn cache split."""
    rows = [row.get("event", row) for row in events]
    if reviewer == "codex":
        keys = ("input_tokens", "cached_input_tokens", "output_tokens")
        return {
            key: sum(
                (row.get("usage") or {}).get(key, 0)
                for row in rows if row.get("type") == "turn.completed"
            )
            for key in keys
        }
    keys = (
        "input_tokens", "cache_creation_input_tokens",
        "cache_read_input_tokens", "output_tokens",
    )
    results = [row for row in rows if row.get("type") == "result"]
    usage = {
        key: sum((row.get("usage") or {}).get(key, 0) for row in results)
        for key in keys
    }
    usage["total_cost_usd"] = sum(row.get("total_cost_usd", 0) for row in results)
    usage["num_turns"] = sum(row.get("num_turns", 0) for row in results)
    first = next(
        ((row.get("message") or {}).get("usage") or {}
         for row in rows if row.get("type") == "assistant"),
        {},
    )
    usage["first_turn"] = {
        key: first.get(key, 0)
        for key in ("cache_read_input_tokens", "cache_creation_input_tokens")
    }
    return usage


def validate_verdict(value: Any) -> dict[str, Any]:
    """Validate the complete repository verdict contract without extra packages."""
    if not isinstance(value, dict):
        raise ValueError("verdict must be an object")

    expected = {"verdict", "summary", *FINDING_KEYS}
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(
            f"verdict keys must be exact (missing={missing}, extra={extra})"
        )

    verdict = value["verdict"]
    if not isinstance(verdict, str) or verdict not in {"SHIP", "FIX"}:
        raise ValueError("verdict.verdict must be 'SHIP' or 'FIX'")
    summary = value["summary"]
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("verdict.summary must be a non-empty string")

    finding_keys = {"where", "issue", "fix"}
    for category in FINDING_KEYS:
        findings = value[category]
        if not isinstance(findings, list):
            raise ValueError(f"verdict.{category} must be an array")
        for index, finding in enumerate(findings):
            location = f"verdict.{category}[{index}]"
            if not isinstance(finding, dict):
                raise ValueError(f"{location} must be an object")
            actual_finding_keys = set(finding)
            if actual_finding_keys != finding_keys:
                missing = sorted(finding_keys - actual_finding_keys)
                extra = sorted(actual_finding_keys - finding_keys)
                raise ValueError(
                    f"{location} keys must be exact (missing={missing}, extra={extra})"
                )
            for key in finding_keys:
                text = finding[key]
                if not isinstance(text, str) or not text.strip():
                    raise ValueError(f"{location}.{key} must be a non-empty string")
    return value


def _valid_verdict(value: Any) -> dict[str, Any] | None:
    try:
        return validate_verdict(value)
    except ValueError:
        return None


def _tag_events(attempt: int, events: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"attempt": attempt, "event": event} for event in events]


def _write_events(path: Path, events: Sequence[dict[str, Any]]) -> None:
    text = "\n".join(json.dumps(event) for event in events)
    path.write_text(f"{text}\n" if text else "", encoding="utf-8")


def is_pass(verdict: dict[str, Any] | None) -> bool:
    verdict = _valid_verdict(verdict)
    if verdict is None or verdict["verdict"] != "SHIP":
        return False
    return all(not verdict[key] for key in GATING_KEYS)


def _parse_events(stdout: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def extract_claude_verdict(events: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Extract Claude's schema-validated structured result."""
    verdict: dict[str, Any] | None = None
    text = ""
    for event in reversed(events):
        structured = event.get("structured_output")
        if isinstance(structured, dict):
            verdict = structured
            break
        if event.get("type") == "result":
            text = str(event.get("result") or "")
            if text.strip():
                break
    if verdict is None:
        if not text.strip():
            raise RuntimeError("claude produced no final message")
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < 0:
            raise RuntimeError(f"final message is not JSON: {text[:200]!r}")
        parsed = json.loads(text[start : end + 1])
        if not isinstance(parsed, dict):
            raise RuntimeError("structured verdict is not an object")
        verdict = parsed
    return validate_verdict(verdict)


def extract_codex_verdict(
    output_file: Path, events: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """Extract Codex's output file, falling back to its last agent message."""
    text = output_file.read_text(encoding="utf-8") if output_file.is_file() else ""
    if not text.strip():
        for event in reversed(events):
            for node in _walk(event):
                if isinstance(node, dict) and node.get("type") == "agent_message":
                    text = str(node.get("text") or node.get("message") or "")
                    if text.strip():
                        break
            if text.strip():
                break
    if not text.strip():
        raise RuntimeError("codex produced no final message")
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise RuntimeError(f"final message is not JSON: {text[:200]!r}")
    return validate_verdict(json.loads(text[start : end + 1]))


def _codex_session_id(events: Sequence[dict[str, Any]]) -> str | None:
    """Return the session id Codex announced in its ``--json`` event stream.

    ``codex exec --json`` opens with a ``thread.started`` event whose
    ``thread_id`` is what ``codex resume`` takes; ``None`` when unrecoverable.
    """
    for event in events:
        for node in _walk(event):
            if isinstance(node, dict) and node.get("type") == "thread.started":
                thread_id = node.get("thread_id")
                if isinstance(thread_id, str) and thread_id:
                    return thread_id
    return None


def _resume_command(reviewer: str, session_id: str | None) -> str | None:
    """Ready-to-run command that reopens one attempt's persisted CLI session."""
    if session_id is None:
        return None
    resume = "claude --resume" if reviewer == "claude" else "codex resume"
    return f"{resume} {session_id}"


def review_package(
    package: ReviewPackage,
    *,
    reviewer: str,
    model: str | None = None,
    effort: str | None = None,
    report_dir: Path = REPORT_DIR,
    retries: int = 1,
    timeout_s: float = 1800.0,
    claude: str | None = None,
    codex: str | None = None,
    prompt_text: str | None = None,
) -> Review:
    if reviewer not in REVIEWERS:
        raise ValueError(f"unknown reviewer {reviewer!r}; choose one of {REVIEWERS}")
    sheet_count = _validate_package(package)
    model = model or DEFAULT_MODELS[reviewer]
    effort = effort or DEFAULT_EFFORTS[reviewer]
    executable = (claude if reviewer == "claude" else codex) or shutil.which(reviewer)
    if not executable:
        raise RuntimeError(f"{reviewer} CLI not found on PATH")
    prompt = _review_prompt(
        package, sheet_count, reviewer=reviewer, prompt_text=prompt_text
    )
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    source_sha = [_sha256(source) for source in package.sources]
    schema_bytes = SCHEMA_FILE.read_bytes()
    report_dir.mkdir(parents=True, exist_ok=True)
    events_path = report_dir / f"{package.name}.events.jsonl"

    started = time.monotonic()
    error: str | None = None
    verdict: dict[str, Any] | None = None
    events: list[dict[str, Any]] = []
    success_events: list[dict[str, Any]] = []
    attempt_records: list[dict[str, Any]] = []
    attempts = 0
    for attempt in range(retries + 1):
        attempts = attempt + 1
        workdir = Path(tempfile.mkdtemp(prefix="machrev-"))
        # Fresh session per attempt: a persisted session must never load the
        # context of an earlier attempt or review.
        session_id: str | None = str(uuid.uuid4()) if reviewer == "claude" else None
        attempt_events: list[dict[str, Any]] = []
        stdout: str | bytes | None = None
        stderr: str | bytes | None = None
        attempt_record: dict[str, Any] = {
            "attempt": attempts,
            "reviewer": reviewer,
            "cwd": str(workdir),
            "sources": [str(source.resolve()) for source in package.sources],
            "retained_cwd": None,
            "rerun_command": None,
            "command": None,
            "outcome": "failed",
            "error": None,
            "exit_code": None,
            "session_id": None,
            "resume_command": None,
            "stdout_file": None,
            "stderr_file": None,
            "artifacts": [],
        }
        attempt_records.append(attempt_record)
        try:
            mcp_config = workdir / "mcp.json"
            if reviewer == "claude":
                mcp_config.write_text(json.dumps({
                    "mcpServers": {
                        "sheets": {
                            "command": sys.executable,
                            "args": [str(SHEETS_SERVER), *(str(p.resolve()) for p in package.sources)],
                        },
                    },
                }), encoding="utf-8")
            schema = workdir / "schema.json"
            schema.write_bytes(schema_bytes)
            output = workdir / "verdict.json"
            cmd = (
                build_claude_command(
                    workdir=workdir,
                    mcp_config=mcp_config,
                    schema=schema,
                    model=model,
                    effort=effort,
                    session_id=session_id,
                    claude=executable,
                )
                if reviewer == "claude"
                else build_codex_command(
                    workdir=workdir,
                    sources=package.sources,
                    schema=schema,
                    output=output,
                    model=model,
                    effort=effort,
                    codex=executable,
                )
            )
            attempt_record["command"] = cmd
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_s,
                cwd=str(workdir),
            )
            attempt_record["exit_code"] = proc.returncode
            stdout, stderr = proc.stdout, proc.stderr
            attempt_events = _parse_events(proc.stdout)
            if proc.returncode != 0:
                # The claude CLI reports quota and auth failures in its JSON
                # result event, not on stderr; without it the error is blank.
                reported = next(
                    (
                        str(event["result"])
                        for event in reversed(attempt_events)
                        if isinstance(event, dict)
                        and event.get("is_error")
                        and event.get("result")
                    ),
                    "",
                )
                raise RuntimeError(
                    f"{reviewer} exit {proc.returncode}: "
                    f"{(reported or proc.stderr.strip())[-800:]}"
                )
            verdict = (
                extract_claude_verdict(attempt_events)
                if reviewer == "claude"
                else extract_codex_verdict(output, attempt_events)
            )
            success_events = list(attempt_events)
            error = None
            attempt_record["outcome"] = "succeeded"
            break
        except subprocess.TimeoutExpired as exc:
            stdout, stderr = exc.stdout, exc.stderr
            partial_stdout = stdout or ""
            if isinstance(partial_stdout, bytes):
                partial_stdout = partial_stdout.decode("utf-8", errors="replace")
            attempt_events = _parse_events(partial_stdout)
            error = f"{type(exc).__name__}: {exc}"
            attempt_record["outcome"] = "timed_out"
            attempt_record["error"] = error
            verdict = None
        except Exception as exc:  # noqa: BLE001 - recorded, retried, reported
            error = f"{type(exc).__name__}: {exc}"
            attempt_record["error"] = error
            verdict = None
        finally:
            if reviewer == "codex":
                session_id = _codex_session_id(attempt_events)
            attempt_record["session_id"] = session_id
            attempt_record["resume_command"] = _resume_command(reviewer, session_id)
            events.extend(_tag_events(attempts, attempt_events))
            retained_dir = report_dir / f"{package.name}.attempts" / workdir.name
            retained_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(workdir), str(retained_dir))
            attempt_record["retained_cwd"] = str(retained_dir)
            if attempt_record["command"]:
                attempt_record["rerun_command"] = [
                    argument.replace(str(workdir), str(retained_dir))
                    for argument in attempt_record["command"]
                ]
            for stream, content in (("stdout", stdout), ("stderr", stderr)):
                if content is not None:
                    path = retained_dir / f"{stream}.txt"
                    path.write_bytes(
                        content
                        if isinstance(content, bytes)
                        else content.encode("utf-8")
                    )
                    attempt_record[f"{stream}_file"] = str(path)
            inputs = {"schema.json", "mcp.json", "stdout.txt", "stderr.txt"}
            attempt_record["artifacts"] = [
                str(artifact) for artifact in sorted(retained_dir.iterdir())
                if artifact.name not in inputs
            ]

    _write_events(events_path, events)
    evidence = evaluate_sheet_evidence(events, reviewer=reviewer, sheet_count=sheet_count)
    successful = evaluate_sheet_evidence(
        success_events, reviewer=reviewer, sheet_count=sheet_count
    )
    tool_events = evidence["tool_events"]
    inspection_proven = successful["inspection_proven"]
    extra = {
        "sheets_viewed": successful["sheets_viewed"],
        "inspection_proven": inspection_proven,
        "crop_calls": evidence["crop_calls"],
        "crops": evidence["crops"],
        "usage": _usage(events, reviewer),
    }
    extra["evidence"] = {
        "effective_prompt": prompt,
        "schema": schema_bytes.decode("utf-8"),
        "attempts": attempt_records,
    }
    blind = tool_events == 0 and inspection_proven
    review = Review(
        name=package.name,
        kind=package.kind,
        sources=[str(source) for source in package.sources],
        source_sha256=source_sha,
        verdict=verdict,
        passed=is_pass(verdict) and blind,
        blind=blind,
        tool_events=tool_events,
        reviewer=reviewer,
        model=model,
        effort=effort,
        prompt_sha256=prompt_sha,
        sheet_count=sheet_count,
        duration_s=round(time.monotonic() - started, 1),
        reviewed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        error=error,
        events_file=str(events_path),
        attempts=attempts,
        extra=extra,
    )
    write_review(review, report_dir)
    return review


def write_review(review: Review, report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / f"{review.name}.json").write_text(
        json.dumps(asdict(review), indent=2), encoding="utf-8"
    )
    (report_dir / f"{review.name}.md").write_text(
        render_markdown(review), encoding="utf-8"
    )


def render_markdown(review: Review) -> str:
    source_hashes = ", ".join(value[:12] for value in review.source_sha256)
    usage = review.extra.get("usage") or {}
    if review.reviewer == "claude":
        cached = usage.get("cache_read_input_tokens", 0)
        total = cached + usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
    else:
        cached = usage.get("cached_input_tokens", 0)
        total = usage.get("input_tokens", 0)
    cache_share = cached / total if total else 0.0
    lines = [
        f"# {review.name} — {'PASS' if review.passed else 'FAIL'}",
        "",
        f"- kind: {review.kind}",
        f"- sheets: {review.sheet_count}",
        f"- reviewed: {review.reviewed_at} by {review.reviewer}/{review.model} "
        f"({review.effort}), {review.duration_s}s, attempts {review.attempts}, "
        f"crops {review.extra.get('crop_calls', 0)}, cache-read {cache_share:.1%}",
        f"- blind: {review.blind} (tool events: {review.tool_events})",
        f"- source sha256: {source_hashes}  prompt sha256: {review.prompt_sha256[:12]}",
    ]
    if review.error:
        lines += ["", f"**error:** {review.error}"]
    verdict = review.verdict
    if verdict:
        lines += ["", f"**{verdict['verdict']}** — {verdict['summary']}"]
        for key in FINDING_KEYS:
            items = verdict.get(key) or []
            lines += ["", f"## {key} ({len(items)})"]
            for item in items:
                lines.append(
                    f"- **{item.get('where', '?')}** — {item.get('issue', '')} "
                    f"→ _{item.get('fix', '')}_"
                )
    return "\n".join(lines) + "\n"


def load_reviews(report_dir: Path = REPORT_DIR) -> list[Review]:
    reviews: list[Review] = []
    for path in sorted(report_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            reviews.append(Review(**data))
        except (OSError, ValueError, TypeError) as exc:
            raise ValueError(f"invalid review report {path}: {exc}") from exc
    return reviews


def render_index(reviews: Sequence[Review]) -> str:
    def _n(review: Review, key: str) -> str:
        return str(len((review.verdict or {}).get(key) or []))

    passed = sum(1 for r in reviews if r.passed)
    lines = [
        "# Machinist review index",
        "",
        f"{passed}/{len(reviews)} packages pass. Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}.",
        "",
        "| package | kind | sheets | result | verdict | blockers | over-spec | clarity | minor | blind | reviewed |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(reviews, key=lambda r: (r.passed, r.name)):
        verdict = (r.verdict or {}).get("verdict", "ERROR" if r.error else "?")
        lines.append(
            f"| [{r.name}]({r.name}.md) | {r.kind} | {r.sheet_count} | "
            f"{'PASS' if r.passed else 'FAIL'} | {verdict} | {_n(r, 'blockers')} | "
            f"{_n(r, 'over_specification')} | {_n(r, 'clarity')} | "
            f"{_n(r, 'minor')} | {'yes' if r.blind else 'NO'} | {r.reviewed_at} |"
        )
    return "\n".join(lines) + "\n"


def write_index(report_dir: Path = REPORT_DIR) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    index = report_dir / "index.md"
    index.write_text(render_index(load_reviews(report_dir)), encoding="utf-8")
    return index


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "names", nargs="*", help="registry drawing names (e.g. crank_arm)"
    )
    parser.add_argument(
        "--all", action="store_true", help="review every registered drawing"
    )
    parser.add_argument(
        "--png",
        type=Path,
        action="append",
        help="review an arbitrary PNG; repeat to form one part or assembly package",
    )
    parser.add_argument("--kind", choices=("part", "assembly"), default="part")
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        help="read registry-named PDFs from this directory instead of cad/out/pdf",
    )
    parser.add_argument("--reviewer", choices=REVIEWERS)
    parser.add_argument(
        "--model",
        help=f"reviewer model (defaults: {DEFAULT_MODELS})",
    )
    parser.add_argument(
        "--effort",
        help=f"reasoning effort (defaults: {DEFAULT_EFFORTS})",
    )
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument(
        "--timeout", type=float, default=1800.0, help="seconds per package"
    )
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument(
        "--prompt-file",
        type=Path,
        help="UTF-8 rubric override; package and blind-inspection instructions still apply",
    )
    parser.add_argument("--index", action="store_true", help="only rebuild index.md")
    parser.add_argument(
        "--missing-ok",
        action="store_true",
        help="skip packages with an unrendered source instead of failing",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    report_dir: Path = args.report_dir
    if args.index:
        print(write_index(report_dir))
        return 0
    if args.reviewer is None:
        print(
            "--reviewer is required for review runs (choose claude or codex)",
            file=sys.stderr,
        )
        return 2

    packages: list[ReviewPackage]
    if args.png:
        packages = [_package_for_pngs(args.png, args.kind)]
    elif args.all:
        packages = all_packages()
    else:
        if not args.names:
            print("no drawing names given; use --all, --png or a name", file=sys.stderr)
            return 2
        unknown = [n for n in args.names if n not in DRAWINGS_BY_NAME]
        if unknown:
            print(f"unknown drawing names: {unknown}", file=sys.stderr)
            return 2
        packages = [package_for(n) for n in args.names]
    if args.pdf_dir is not None:
        if args.png:
            raise ValueError("--pdf-dir cannot be combined with --png")
        packages = [
            ReviewPackage(
                package.name,
                package.kind,
                (args.pdf_dir / DRAWINGS_BY_NAME[package.name].outputs["pdf"].name,),
            )
            for package in packages
        ]
    if args.missing_ok:
        skipped = [
            package.name
            for package in packages
            if not all(source.is_file() for source in package.sources)
        ]
        if skipped:
            print(
                f"skipping {len(skipped)} packages with unrendered sources: {skipped}",
                file=sys.stderr,
            )
        packages = [
            package
            for package in packages
            if all(source.is_file() for source in package.sources)
        ]
    prompt_text = (
        args.prompt_file.read_text(encoding="utf-8")
        if args.prompt_file is not None
        else None
    )

    reviews: list[Review] = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = {
            pool.submit(
                review_package,
                package,
                reviewer=args.reviewer,
                model=args.model,
                effort=args.effort,
                report_dir=report_dir,
                retries=args.retries,
                timeout_s=args.timeout,
                prompt_text=prompt_text,
            ): package
            for package in packages
        }
        for future in as_completed(futures):
            package = futures[future]
            try:
                review = future.result()
            except Exception as exc:  # noqa: BLE001 - one package must not sink the run
                print(f"{package.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
                continue
            reviews.append(review)
            verdict = (review.verdict or {}).get("verdict", "ERROR")
            counts = " ".join(
                f"{k}={len((review.verdict or {}).get(k) or [])}" for k in FINDING_KEYS
            )
            print(
                f"{'PASS' if review.passed else 'FAIL'} {review.name:<32} {verdict:<5} "
                f"{counts} blind={review.blind} {review.duration_s}s",
                file=sys.stderr,
            )
    index = write_index(report_dir)
    failed = [r.name for r in reviews if not r.passed]
    errored = len(packages) - len(reviews)
    print(
        f"{len(reviews) - len(failed)}/{len(packages)} pass; index: {index}",
        file=sys.stderr,
    )
    return 0 if not failed and not errored else 1


if __name__ == "__main__":
    sys.exit(main())
