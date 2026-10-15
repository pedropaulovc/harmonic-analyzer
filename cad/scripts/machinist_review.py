r"""Blind senior-machinist review of drawing packages via Claude or Codex.

The review the fleet is gated on (``cad/docs/drawing-simplicity-policy.md``):
each package is handed to an isolated CLI in a neutral attempt directory.
A private stdio MCP server supplies grayscale whole-sheet views fitting
1976×1280 pixels (about 118 dpi on 11×17 sheets) and vector-PDF region crops.
The cached prompt prefix is the shared drawing standard followed by the kind's
reviewer instructions; package-specific instructions come last.
The reviewer is Claude Opus 5.5 by default (``--reviewer claude``), whoever
authored the drawing: the machinist review is exempt from the cross-family rule
that governs code review. An 80-case benchmark scored Opus with the zoom tool
above Fable and Astra at about a third of Fable's cost. ``--reviewer codex``
and ``--model`` select another reviewer when wanted (e.g. Opus over quota).
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

Claude disables built-in tools and user/project customizations. Codex uses an
isolated home with hardlinked (never copied) auth, a direct-tool model catalogue,
and a fresh neutral attempt directory. The auth link is checked before and after
every invocation and repaired if a CLI save split it (``relink_codex_auth``).
Only the private ``sheets`` MCP server is configured. Attempt directories hold
schema/configuration/output files, never sheet PNGs. Claude's event stream and
Codex's authoritative rollout reject unauthorized tools or injected context,
and prove every sheet was viewed in the verdict-producing attempt. Codex's
scoped resource helpers are neutral, non-proving calls only after the actual
SDK confirms this sole server exposes no resources or templates; their calls
are recorded. Other tools and unexpected resource content remain fail-closed.
Crop and token/cache usage are retained; first-turn usage belongs to that attempt.
Fresh sessions never load prior review context. Transcripts and attempt files
are retained even if Windows prevents moving the original cwd. The recorded
``retained_argv`` only adapts artifact paths for inspection, NOT a replay: it
does not supply stdin or a fresh session id. ``command`` records actual argv;
session ids and resume commands identify the completed CLI session.

Codex 0.159.1 uses a per-conversation ``prompt_cache_key`` and exposes no native
override for fresh exec sessions. Within-review cache reuse is supported here;
fresh-session prefix hits can occur, but cross-package affinity is not controlled
or promised. Claude's static rubric prefix can be reused across packages.
Never reuse a review session/context to get a hit.

Usage (SolidWorks-free; PDFs in ``cad/out/pdf`` or ``--pdf-dir``)::

    uv run cad/scripts/machinist_review.py crank_arm pivot_shaft
    uv run cad/scripts/machinist_review.py --all --jobs 4
    uv run cad/scripts/machinist_review.py --png sheet-1.png --png sheet-2.png --kind assembly
    uv run cad/scripts/machinist_review.py ch_pivot_shaft --pdf-dir release/pdf
    uv run cad/scripts/machinist_review.py --index      # rebuild index.md only

Exit status is 0 only when every reviewed package passes (``SHIP`` with no
blocker, over-specification or clarity finding).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
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
from machinist_exceptions import load_exceptions as _load_exceptions  # noqa: E402
from machinist_review_sheets_mcp import (  # noqa: E402
    PDFIUM_LOCK as _PDFIUM_LOCK,
    SheetStore,
    create_server as _create_sheet_server,
)

PROMPTS_DIR = SCRIPTS_DIR / "prompts"
GUIDELINES_FILE = CAD_ROOT / "docs" / "drawing-guidelines.md"
PROMPT_FILES = {
    "part": PROMPTS_DIR / "machinist_review_part.md",
    "assembly": PROMPTS_DIR / "machinist_review_assembly.md",
}
SCHEMA_FILE = PROMPTS_DIR / "machinist_review_schema.json"
REPORT_DIR = CAD_ROOT / "out" / "reports" / "machinist-review"
# Auth is linked here, never copied into an attempt or retained report.
CODEX_HOME = Path(tempfile.gettempdir()) / "machinist-review-codex-home"
# Parallel reviews share CODEX_HOME; one thread repairs its auth link at a time.
_CODEX_AUTH_LOCK = threading.Lock()

DEFAULT_MODELS = {
    "claude": "claude-opus-5-5",
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


def _sheet_resource_manifest(sources: Sequence[Path]) -> dict[str, Any]:
    """Inspect the actual SDK registry before permitting neutral MCP helpers."""
    with SheetStore(sources) as sheets:
        server = _create_sheet_server(sheets)

        async def catalog() -> dict[str, Any]:
            return {
                "servers": ["sheets"],
                "resources": len(await server.list_resources()),
                "resource_templates": len(await server.list_resource_templates()),
            }

        return asyncio.run(catalog())


def _resource_neutrality_permitted(catalog: Any) -> bool:
    return (
        catalog == {"servers": ["sheets"], "resources": 0, "resource_templates": 0}
        and type(catalog["resources"]) is int
        and type(catalog["resource_templates"]) is int
    )


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

def _text_layers(package: ReviewPackage) -> str:
    """Exact sheet text for the package prompt; empty without PDF text."""
    if not package.sources or os.environ.get("MACHINIST_REVIEW_TEXT_LAYER") == "off":
        return ""
    documents = []
    with SheetStore(package.sources) as store:
        for sheet in range(1, store.sheet_count + 1):
            document = store.text_layer(sheet)
            if document:
                documents.append(document)
    return "\n\n".join(documents)


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
        "Use only view_sheet, crop and sheet_text.\n"
    )
    if sheet_count > 1:
        prompt += (
            "Compare every sheet against every other sheet before accepting SHIP.\n"
        )
    layers = _text_layers(package)
    if (
        not layers
        and package.sources
        and os.environ.get("MACHINIST_REVIEW_TEXT_LAYER") == "off"
    ):
        prompt += (
            "\nSHEET TEXT LAYER\n"
            "Not pre-injected for this run: fetch it with the sheet_text tool "
            "(rect in view_sheet pixels; use the size view_sheet reports for a "
            "whole sheet). It comes organized by sheet then view.\n"
        )
    if layers:
        prompt += (
            "\nSHEET TEXT LAYER\n"
            "Extracted sheet text, organized by sheet then view; rects are "
            "view_sheet pixels. It is this prompt's content, not a tool, and a "
            "transcription aid rather than proof of print: confirm printed-"
            "evidence claims on the sheet image or a crop. Sheets without a "
            "section here have no extractable text and must be read from the "
            "images.\n"
            f"{layers}\n"
        )
    if package.sources:
        exceptions = _load_exceptions(CAD_ROOT / "config", package.name, package.kind)
        if exceptions:
            prompt += (
                "\nOWNER-DECLARED MACHINIST EXCEPTIONS\n"
                "The project owner has accepted these known departures. A "
                "would-be finding that matches one is not a finding: do not "
                'file it (kind "accept"), or file it at most under minor '
                '(kind "minor"), and never let it affect the verdict. Name '
                "the exception id in the summary when you apply one.\n"
            )
            for exception in exceptions:
                prompt += (
                    f"- {exception.id} [{exception.kind}] at {exception.where}: "
                    f"{exception.finding} — {exception.reason}\n"
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
        "--thinking",
        "adaptive",
        "--thinking-display",
        "summarized",
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
        "mcp__sheets__view_sheet,mcp__sheets__crop,mcp__sheets__sheet_text",
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
    attempt_dir: Path | None = None,
) -> list[str]:
    """Build argv using a neutral cwd and separately identified attempt files.

    ``prepare_codex_environment`` must create the direct-tool model catalog and
    supply the isolated CODEX_HOME environment before this command is invoked.
    The default attempt_dir is useful for standalone toy probes, not the harness.
    """
    attempt_dir = workdir if attempt_dir is None else attempt_dir
    if (
        not sources
        or not workdir.is_absolute()
        or not attempt_dir.is_absolute()
        or any(not path.is_absolute() or path.resolve().parent != attempt_dir.resolve()
               for path in (schema, output))
    ):
        raise ValueError("review configuration and output must be inside the absolute attempt_dir")
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
        "project_doc_max_bytes": 0,
        "skills.include_instructions": False,
        "features.plugins": False,
        "features.recommended_plugins": False,
        "include_environment_context": False,
        "include_permissions_instructions": False,
        "include_collaboration_mode_instructions": False,
        "include_apps_instructions": False,
        "features.code_mode": False,
        "features.code_mode_only": False,
        "features.code_mode_host": False,
        # Model catalog tool_mode takes precedence over these feature switches.
        # supports_search_tool must also be false to expose the MCP tools directly.
        "model_catalog_json": str(attempt_dir / "codex-models.json"),
        "features.shell_tool": False,
        # Legacy request, not proven removal: Codex 0.159.1 still declares
        # functions.apply_patch as a custom freeform tool with this switch false.
        "features.apply_patch_freeform": False,
        # Authoritative rollout evidence rejects every residual builtin call,
        # including patches, clocks and image generation, not just --json items.
        "features.view_image": False,
        "features.goals": False,
        "features.image_generation": False,
        "features.sleep_tool": False,
        "features.current_time_reminder": False,
        "features.tool_search": False,
        "features.tool_search_always_defer_mcp_tools": False,
        "features.apps": False,
        "features.browser_use": False,
        "features.computer_use": False,
        "features.memories": False,
        "agents.enabled": False,
        "features.multi_agent_v2": False,
        "tools.update_plan.enabled": False,
        "tools.experimental_request_user_input.enabled": False,
        "web_search": "disabled",
        # Stable in 0.159.1: injects a clock namespace (curr_time, sleep).
        "features.sleep_tool": False,
        "mcp_servers.sheets.command": sys.executable,
        "mcp_servers.sheets.args": [str(SHEETS_SERVER), *(str(p.resolve()) for p in sources)],
        "mcp_servers.sheets.default_tools_approval_mode": "approve",
        "mcp_servers.sheets.enabled_tools": ["view_sheet", "crop"],
        # An optional server races the first turn: under parallel reviews the
        # model was sampled before tools/list returned and judged with no tools.
        # Required servers are awaited, and exec fails if one cannot start.
        "mcp_servers.sheets.required": True,
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


def _codex_source_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").resolve()


def relink_codex_auth(codex_home: Path) -> str | None:
    """Keep the isolated home's ``auth.json`` a hardlink of the user's login.

    A ChatGPT login rotates its refresh token on every refresh and revokes the
    old one. Codex 0.159.1 saves ``auth.json`` in place, so a refresh during a
    review lands in the user's own file through the link. A CLI that saves by
    write-then-rename instead splits the link: the isolated copy then holds the
    newest token and the user's file a revoked one. This repairs that whatever
    the CLI version: a newer, different isolated copy is atomically copied back
    over the user's file, then the link is remade. Returns a warning when the
    link had been split, ``None`` otherwise.
    """
    source_auth = _codex_source_home() / "auth.json"
    linked = codex_home / "auth.json"
    with _CODEX_AUTH_LOCK:
        if not source_auth.is_file():
            raise FileNotFoundError(f"original Codex file login not found: {source_auth}")
        if not linked.exists():
            linked.hardlink_to(source_auth)
            return None
        if linked.samefile(source_auth):
            return None
        warning = f"isolated Codex auth link was split; relinked to {source_auth}"
        if (
            linked.stat().st_mtime_ns > source_auth.stat().st_mtime_ns
            and linked.read_bytes() != source_auth.read_bytes()
        ):
            staged = source_auth.with_name(f"auth.json.{uuid.uuid4().hex}.tmp")
            shutil.copy2(linked, staged)
            os.replace(staged, source_auth)
            warning = (
                f"isolated Codex auth link was split by a refresh; copied the "
                f"refreshed login back to {source_auth} and relinked"
            )
        linked.unlink()
        linked.hardlink_to(source_auth)
        return warning


def _warn_auth(warning: str | None) -> None:
    if warning:
        print(f"!! {warning}", file=sys.stderr)


def prepare_codex_environment(
    *, codex_home: Path, attempt_dir: Path, model: str, codex: str = "codex"
) -> dict[str, str]:
    """Link shared auth into an instruction-free home; retain direct model metadata.

    Codex 0.159.1 loads global AGENTS.md independently of project_doc_max_bytes,
    so the reviewer runs from its own home. That home shares the user's login
    through a hardlink (never a copy), kept whole by ``relink_codex_auth``
    before and after every Codex invocation.
    """
    source_home = _codex_source_home()
    if (
        not codex_home.is_absolute()
        or not attempt_dir.is_absolute()
        or codex_home.resolve() == source_home
        or codex_home.resolve().is_relative_to(attempt_dir.resolve())
        or attempt_dir.resolve().is_relative_to(codex_home.resolve())
    ):
        raise ValueError("isolated CODEX_HOME must be absolute and separate from attempt artifacts")
    codex_home.mkdir(parents=True, exist_ok=True)
    if any((codex_home / name).exists() for name in ("AGENTS.md", "AGENTS.override.md", "config.toml")):
        raise RuntimeError("isolated CODEX_HOME contains user instructions or configuration")
    _warn_auth(relink_codex_auth(codex_home))
    env = {**os.environ, "CODEX_HOME": str(codex_home)}
    catalog_result = subprocess.run(
        [codex, "debug", "models"], cwd=attempt_dir, env=env,
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    if catalog_result.returncode:
        raise RuntimeError(f"Codex model catalog unavailable: {catalog_result.stderr.strip()}")
    catalog = json.loads(catalog_result.stdout)
    models = catalog.get("models") if isinstance(catalog, dict) else None
    selected = [
        entry for entry in (models if isinstance(models, list) else [])
        if isinstance(entry, dict) and entry.get("slug") == model
    ]
    if len(selected) != 1:
        raise RuntimeError(f"Codex catalog must contain exactly one descriptor for {model!r}")
    descriptor = {**selected[0], "tool_mode": "direct", "supports_search_tool": False}
    (attempt_dir / "codex-models.json").write_text(
        json.dumps({"models": [descriptor]}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _warn_auth(relink_codex_auth(codex_home))
    return env


def load_codex_rollout(
    session_id: str, *, codex_home: Path | None = None
) -> tuple[Path, list[dict[str, Any]]]:
    """Read the uniquely identified authoritative session, never the --json projection.

    Missing, ambiguous, malformed or wrong-session evidence raises: callers must
    fail closed, including when a provider error produced only a partial rollout.
    """
    try:
        canonical_id = str(uuid.UUID(session_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Codex rollout requires a valid session UUID") from exc
    if canonical_id != session_id:
        raise ValueError("Codex rollout requires a canonical session UUID")
    home = codex_home or Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    paths = [
        path for root in (home / "sessions", home / "archived_sessions")
        if root.is_dir() for path in root.rglob(f"rollout-*-{canonical_id}.jsonl")
        if path.is_file()
    ]
    if not paths:
        raise FileNotFoundError(f"authoritative Codex rollout missing for {session_id}")
    if len(paths) != 1:
        raise ValueError(f"ambiguous authoritative Codex rollout for {session_id}")
    path = paths[0]
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed Codex rollout line {line_number}") from exc
        if not isinstance(row, dict) or not isinstance(row.get("payload"), dict):
            raise ValueError(f"invalid Codex rollout row {line_number}")
        rows.append(row)
    metadata = [row["payload"] for row in rows if row.get("type") == "session_meta"]
    if (
        len(metadata) != 1
        or metadata[0].get("id") != session_id
        or metadata[0].get("session_id", session_id) != session_id
    ):
        raise ValueError("Codex rollout session metadata does not match the requested session")
    return path, rows


def _codex_sheet_call(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Recognize only actual sheets function identities, not names inside code."""
    if payload.get("type") != "function_call":
        return None
    name, namespace = payload.get("name"), payload.get("namespace")
    if namespace == "mcp__sheets" and name in {"view_sheet", "crop", "sheet_text"}:
        tool = name
    elif namespace in {None, "functions"} and name in {
        "mcp__sheets__view_sheet", "mcp__sheets__crop", "mcp__sheets__sheet_text"
    }:
        tool = str(name).removeprefix("mcp__sheets__")
    else:
        return None
    arguments = payload.get("arguments")
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            pass
    return {
        "type": "mcp_tool_call", "id": payload.get("call_id") or payload.get("id"),
        "server": "sheets", "tool": tool, "arguments": arguments,
        "status": "in_progress", "result": None, "error": None,
    }


def _codex_resource_arguments(node: dict[str, Any]) -> Any:
    arguments = node.get("arguments")
    if isinstance(arguments, str):
        try:
            return json.loads(arguments)
        except json.JSONDecodeError:
            pass
    return arguments


def _is_neutral_codex_resource_call(node: dict[str, Any]) -> bool:
    """Recognize scoped resource identities; the caller must authorize neutrality."""
    kind = node.get("type")
    if kind == "function_call" and node.get("namespace") in (None, "functions"):
        name = node.get("name")
    elif kind in ("mcp_tool_call", "McpToolCall"):
        name = node.get("tool")
    else:
        return False
    if name not in (
        "list_mcp_resources", "list_mcp_resource_templates", "read_mcp_resource"
    ):
        return False
    arguments = _codex_resource_arguments(node)
    if not isinstance(arguments, dict) or arguments.get("server") not in (None, "sheets"):
        return False
    return kind == "function_call" or node.get("server") == "codex" or (
        node.get("server") == "sheets" and arguments.get("server") == "sheets"
    )


def _codex_missing_resource_error(text: Any) -> bool:
    import re

    if not isinstance(text, str) or any(char in text for char in "\r\n{}"):
        return False
    if text == "failed to parse function arguments: missing field `server`":
        return True
    return bool(
        re.match(
            r"(?:resources/read failed|unknown resource|resource not found|no such resource)",
            text, re.I,
        )
        and re.search(
            r"\b(?:unknown|missing|no such) resource\b|\bresource\b.*\b(?:not found|does not exist)\b",
            text, re.I,
        )
    )


def _codex_neutral_resource_result_errors(node: dict[str, Any]) -> list[str]:
    """Reject resource data even when the independently collected catalog is empty."""
    if not _is_neutral_codex_resource_call(node):
        return ["unscoped Codex resource helper call"]
    if node.get("type") == "function_call" or node.get("status") == "in_progress":
        if node.get("result") is None and not node.get("error"):
            return []
    tool = node.get("tool") or node.get("name")
    result, error = node.get("result"), node.get("error")
    if tool == "read_mcp_resource" and result is None:
        message = error.get("message") if isinstance(error, dict) else error
        if (
            (not isinstance(error, dict) or not error.keys() - {"message", "code"})
            and _codex_missing_resource_error(message)
        ):
            return []
        return ["unexpected resource read output; expected a missing-resource error"]
    if (
        not isinstance(result, dict)
        or result.keys() - {"content", "isError"}
        or not isinstance(result.get("isError", False), bool)
    ):
        return ["unexpected resource helper result"]
    content = result.get("content")
    if not isinstance(content, list) or len(content) != 1:
        return ["unexpected resource helper content"]
    part = content[0]
    if (
        not isinstance(part, dict) or part.keys() - {"type", "text"}
        or part.get("type") != "text" or not isinstance(part.get("text"), str)
    ):
        return ["unexpected non-text resource helper content"]
    text = part["text"]
    if tool == "read_mcp_resource":
        if result.get("isError") is True and _codex_missing_resource_error(text):
            if not error:
                return []
            message = error.get("message") if isinstance(error, dict) else error
            if (
                (not isinstance(error, dict) or not error.keys() - {"message", "code"})
                and _codex_missing_resource_error(message)
            ):
                return []
        return ["unexpected resource read content; expected a missing-resource error"]
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return ["unexpected resource list output"]
    key = "resources" if tool == "list_mcp_resources" else "resourceTemplates"
    if (
        result.get("isError") or error or node.get("status") == "failed"
        or not isinstance(value, dict) or value.keys() - {key, "server"}
        or value.get(key) != [] or value.get("server") not in (None, "sheets")
    ):
        return ["unexpected nonempty or malformed resource list output"]
    return []


def _codex_neutral_resource_output(
    payload: dict[str, Any], call: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Validate model-visible helper output separately from its native completion."""
    output = payload.get("output")
    if not isinstance(output, str):
        return {"content": [], "isError": True}, ["unexpected resource helper output"]
    result = {
        "content": [{"type": "text", "text": output}],
        "isError": call.get("tool") == "read_mcp_resource",
    }
    errors = _codex_neutral_resource_result_errors({
        **call, "status": "completed", "result": result, "error": None,
    })
    return result, errors


def _codex_rollout_output(
    payload: dict[str, Any], completed: dict[str, Any] | None
) -> tuple[dict[str, Any], list[str]]:
    """Accept PNG tool images, exact server metadata/errors and CLI timing only."""
    import re

    result = completed.get("result") if completed else None
    server_content = result.get("content", []) if isinstance(result, dict) else []
    server_text = {
        part["text"] for part in server_content
        if isinstance(part, dict) and part.get("type") == "text"
        and isinstance(part.get("text"), str)
    }
    parts = payload.get("output")
    content: list[dict[str, Any]] = []
    errors = []
    if not isinstance(parts, list):
        # Failed calls can have a string result. They never prove inspection.
        if not isinstance(parts, str) or not completed or not (
            completed.get("error") or isinstance(result, dict) and result.get("isError")
        ):
            errors.append("unexpected non-image sheet tool output")
        return {"content": [], "isError": True}, errors
    for part in parts:
        if not isinstance(part, dict):
            errors.append("malformed sheet tool output content")
        elif part.get("type") == "input_image":
            url = part.get("image_url")
            if isinstance(url, str) and url.startswith("data:image/png;base64,"):
                content.append({"type": "image", "data": url.removeprefix("data:image/png;base64,")})
            else:
                errors.append("sheet tool image is not an inline PNG")
        elif part.get("type") == "input_text":
            text = part.get("text")
            if not isinstance(text, str) or not (
                text in server_text
                or re.fullmatch(r"Wall time: [0-9.]+ seconds\r?\nOutput:\s*", text)
            ):
                errors.append("unexpected text in sheet tool output")
        else:
            errors.append("unexpected non-image sheet tool content")
    failed = bool(completed and (
        completed.get("error") or isinstance(result, dict) and result.get("isError")
    ))
    return {"content": content, "isError": failed or bool(errors)}, errors


def codex_rollout_evidence(
    events: Sequence[dict[str, Any]], prompt: str, *, neutral_resources: bool = False
) -> dict[str, Any]:
    """Normalize every authoritative call and reject unaccounted model input.

    The built-in model instructions are recorded in session_meta.base_instructions,
    not response_item context. Session/turn metadata and token accounting are
    protocol bookkeeping. Every other developer/user message is forbidden:
    only the exact harness prompt and bounded sheet tool outputs may add input.
    An independently authorized empty sheets catalog permits scoped resource
    helpers, but their outputs never establish sheet inspection.
    """
    normalized: list[dict[str, Any]] = []
    errors: list[str] = []
    calls: dict[str, dict[str, Any]] = {}
    completed: dict[str, dict[str, Any]] = {}
    outputs: set[str] = set()
    neutral_indices: dict[str, int] = {}
    first_usage: dict[str, Any] = {}
    fallback_usage: dict[str, Any] = {}
    metadata = []
    type_names = {
        "McpToolCall": "mcp_tool_call", "AgentMessage": "agent_message",
        "Reasoning": "reasoning", "Error": "error",
    }
    for row in events:
        if not isinstance(row, dict) or not isinstance(row.get("payload"), dict):
            errors.append("malformed authoritative Codex rollout row")
            continue
        payload = row["payload"]
        if row.get("type") == "session_meta":
            metadata.append(payload)
        elif row.get("type") == "token_usage_record" and not first_usage:
            usage = payload.get("usage")
            if isinstance(usage, dict):
                first_usage = dict(usage)
        elif row.get("type") == "event_msg":
            if payload.get("type") == "token_count" and not fallback_usage:
                info = payload.get("info")
                usage = info.get("last_token_usage") if isinstance(info, dict) else None
                if isinstance(usage, dict):
                    fallback_usage = dict(usage)
            item = payload.get("item")
            if isinstance(item, dict) and item.get("type") in {"McpToolCall", "mcp_tool_call"}:
                completed[str(item.get("id", ""))] = {
                    **item, "type": "mcp_tool_call",
                }
    if len(metadata) != 1 or not metadata[0].get("id"):
        errors.append("authoritative Codex rollout lacks unique session metadata")
    elif metadata[0].get("session_id", metadata[0]["id"]) != metadata[0]["id"]:
        errors.append("Codex rollout session identifiers disagree")
    session_id = metadata[0].get("id") if len(metadata) == 1 else None
    expected_prompt = prompt.replace("\r\n", "\n")
    prompt_seen = False
    for index, row in enumerate(events):
        payload = row.get("payload") if isinstance(row, dict) else None
        if not isinstance(payload, dict):
            continue
        kind = row.get("type")
        for key in ("session_id", "thread_id"):
            if session_id and payload.get(key, session_id) != session_id:
                errors.append(f"rollout row {index + 1} belongs to another session")
        if kind == "world_state":
            state = payload.get("state")
            if not isinstance(state, dict):
                errors.append("malformed Codex model-visible world state")
                continue
            for key, value in state.items():
                if key == "model" and isinstance(value, str):
                    continue
                if key == "realtime" and value == {"active": False}:
                    continue
                if key in {"skills", "host_skills"} and value in ({}, {"includeInstructions": False}):
                    continue
                if value:
                    errors.append(f"unexpected Codex world-state context: {key}")
        elif kind == "compacted":
            errors.append("Codex compaction introduced unaccounted context")
        elif kind == "response_item":
            item_kind = payload.get("type")
            if item_kind == "message":
                role, content = payload.get("role"), payload.get("content")
                if role == "assistant":
                    if not prompt_seen:
                        errors.append("assistant response precedes the harness prompt")
                    continue
                matches = (
                    role == "user" and isinstance(content, list) and len(content) == 1
                    and isinstance(content[0], dict) and content[0].get("type") == "input_text"
                    and isinstance(content[0].get("text"), str)
                    and content[0]["text"].replace("\r\n", "\n") == expected_prompt
                )
                if matches and not prompt_seen:
                    prompt_seen = True
                else:
                    position = "after" if prompt_seen else "before"
                    errors.append(f"unexpected {role!r} input {position} the harness prompt")
            elif item_kind == "reasoning":
                continue
            elif item_kind in {"function_call_output", "custom_tool_call_output"}:
                call_id = str(payload.get("call_id", ""))
                call = calls.get(call_id)
                if call is None:
                    errors.append("tool output lacks a preceding authoritative call")
                elif (
                    neutral_resources and call_id in neutral_indices
                    and _is_neutral_codex_resource_call(call)
                ):
                    result, output_errors = _codex_neutral_resource_output(payload, call)
                    errors.extend(output_errors)
                    native = completed.get(call_id)
                    if (
                        native and _is_neutral_codex_resource_call(native)
                        and native.get("tool") == call.get("tool")
                        and _codex_resource_arguments(native) == call.get("arguments")
                    ):
                        errors.extend(_codex_neutral_resource_result_errors(native))
                        item = {**native, "arguments": _codex_resource_arguments(native)}
                    else:
                        item = {**call, "status": "completed", "result": result}
                    normalized[neutral_indices[call_id]] = {"type": "item.completed", "item": item}
                elif call.get("type") != "mcp_tool_call":
                    errors.append("non-sheet tool result introduced reviewer input")
                else:
                    result, output_errors = _codex_rollout_output(payload, completed.get(call_id))
                    errors.extend(output_errors)
                    normalized.append({
                        "type": "item.completed",
                        "item": {**call, "status": "completed", "result": result},
                    })
                outputs.add(call_id)
            else:
                if not prompt_seen:
                    errors.append("tool or unknown response item precedes the harness prompt")
                call_id = str(payload.get("call_id") or payload.get("id") or f"rollout-{index}")
                item = _codex_sheet_call(payload)
                if (
                    item is None and neutral_resources and item_kind == "function_call"
                    and _is_neutral_codex_resource_call(payload)
                ):
                    item = {
                        "type": "mcp_tool_call", "id": call_id, "server": "codex",
                        "tool": payload["name"], "arguments": _codex_resource_arguments(payload),
                        "status": "in_progress", "result": None, "error": None,
                    }
                    neutral_indices[call_id] = len(normalized)
                if item is None:
                    item = {**payload, "id": call_id}
                if call_id in calls:
                    errors.append("duplicate authoritative Codex call identifier")
                calls[call_id] = item
                normalized.append({"type": "item.completed", "item": item})
        elif kind == "event_msg":
            item = payload.get("item")
            if isinstance(item, dict):
                if item.get("type") in {"UserMessage", "user_message"}:
                    content = item.get("content")
                    matches = (
                        prompt_seen and isinstance(content, list) and len(content) == 1
                        and isinstance(content[0], dict) and content[0].get("type") == "text"
                        and isinstance(content[0].get("text"), str)
                        and content[0]["text"].replace("\r\n", "\n") == expected_prompt
                    )
                    if not matches:
                        errors.append("unexpected user input in Codex protocol message")
                    continue
                item = {**item, "type": type_names.get(item.get("type"), item.get("type"))}
                if item.get("type") not in {"agent_message", "reasoning", "error"}:
                    call_id = str(item.get("id", ""))
                    call = calls.get(call_id)
                    if call is None and neutral_resources and call_id in neutral_indices:
                        call = normalized[neutral_indices[call_id]]["item"]
                    neutral_call = bool(
                        neutral_resources and call and _is_neutral_codex_resource_call(call)
                    )
                    neutral_item = neutral_resources and _is_neutral_codex_resource_call(item)
                    agrees = bool(
                        neutral_call and neutral_item
                        and call.get("tool") == item.get("tool")
                        and call.get("arguments") == _codex_resource_arguments(item)
                    )
                    if call and (
                        (
                            call.get("type") == "mcp_tool_call"
                            and item.get("type") == "mcp_tool_call" and not agrees
                            and any(call.get(key) != item.get(key)
                                    for key in ("server", "tool", "arguments"))
                        )
                        or neutral_item and not agrees
                    ):
                        errors.append("Codex executed MCP call disagrees with its model declaration")
                    if neutral_item:
                        errors.extend(_codex_neutral_resource_result_errors(item))
                        item = {**item, "arguments": _codex_resource_arguments(item)}
                        event = {"type": "item.completed", "item": item}
                        if agrees and call_id in neutral_indices:
                            normalized[neutral_indices[call_id]] = event
                        elif call_id not in neutral_indices:
                            neutral_indices[call_id] = len(normalized)
                            normalized.append(event)
                        else:
                            normalized.append(event)
                    else:
                        # Native completions prove call identity and
                        # provenance only: strip image payloads so inspection
                        # can never be established from server-side records
                        # the model itself never saw.
                        if isinstance(item.get("result"), dict):
                            native_result = item["result"]
                            content = native_result.get("content")
                            if isinstance(content, list):
                                item = {
                                    **item,
                                    "result": {
                                        **native_result,
                                        "content": [
                                            part for part in content
                                            if not (isinstance(part, dict)
                                                    and part.get("type") == "image")
                                        ],
                                    },
                                }
                        normalized.append({"type": "item.completed", "item": item})
            elif any(marker in str(payload.get("type", "")).lower()
                     for marker in ("tool_call", "command", "shell", "patch", "web_search")):
                normalized.append({
                    "type": "item.completed",
                    "item": {**payload, "id": payload.get("call_id") or payload.get("id")},
                })
    if not prompt_seen:
        errors.append("expected harness prompt missing from authoritative Codex rollout")
    for call_id in calls.keys() - outputs:
        errors.append(f"authoritative Codex call {call_id} has no recorded output")
    return {
        "events": normalized, "context_errors": errors,
        "first_turn_usage": first_usage or fallback_usage,
    }


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
    events: Sequence[dict[str, Any]], *, reviewer: str, sheet_count: int,
    neutral_resources: bool = False,
) -> dict[str, Any]:
    """Fail closed on tools other than bounded sheet inspection.

    Codex announces the same call at start and completion; count it once.
    A view proves inspection only when its successful result contains an image.
    Attempt tags keep repeated tool ids in separate attempts distinct.
    The empty, sheets-only MCP registry may permit scoped resource helpers as
    neutral calls. They never prove inspection; text-only graders remain strict.
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
    neutral_ids: set[tuple[Any, ...]] = set()
    neutral_calls: list[dict[str, Any]] = []
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
            if (
                reviewer == "codex"
                and neutral_resources
                and sheet_count > 0
                and _is_neutral_codex_resource_call(node)
                and not _codex_neutral_resource_result_errors(node)
            ):
                neutral_id = (
                    (attempt, str(node["id"]))
                    if node.get("id")
                    else (attempt, event_index, node_index)
                )
                if neutral_id not in neutral_ids:
                    neutral_ids.add(neutral_id)
                    arguments = node.get("arguments")
                    if isinstance(arguments, str):
                        arguments = json.loads(arguments)
                    neutral_calls.append({
                        "tool": node.get("tool") or node.get("name"),
                        "arguments": arguments,
                    })
                continue
            tool = None
            arguments = None
            successful = False
            if reviewer == "claude" and kind == "tool_use":
                name = node.get("name")
                if name == "StructuredOutput":
                    continue
                if name in {"mcp__sheets__view_sheet", "mcp__sheets__crop", "mcp__sheets__sheet_text"}:
                    tool = str(name).removeprefix("mcp__sheets__")
                    arguments = node.get("input")
                    successful = (attempt, str(node.get("id", ""))) in image_results
            elif (
                reviewer == "codex"
                and kind == "mcp_tool_call"
                and node.get("server") == "sheets"
                and node.get("tool") in {"view_sheet", "crop", "sheet_text"}
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
            if tool is None or sheet_count < 1:
                unauthorized.add(identity)
                continue
            if tool == "crop" and identity not in crop_ids:
                crop_ids.add(identity)
                raw = arguments if isinstance(arguments, dict) else {}
                crops.append({
                    "sheet": raw.get("sheet"),
                    "rect": [raw.get(key) for key in ("x1", "y1", "x2", "y2")],
                })
            # A rejected argument is a failed sheet inspection, not access to
            # any other source/tool. Never use it as proof, even with an image.
            if valid and tool == "view_sheet" and successful:
                views.add(arguments["sheet"])
    return {
        "tool_events": len(unauthorized),
        "sheets_viewed": sorted(views),
        "crop_calls": len(crop_ids),
        "crops": crops,
        "neutral_calls": neutral_calls,
        "inspection_proven": sheet_count > 0 and views == set(range(1, sheet_count + 1)),
    }


def count_codex_tool_events(events: Sequence[dict[str, Any]]) -> int:
    """The benchmark's text-only grader permits no sheet or other tools."""
    return evaluate_sheet_evidence(events, reviewer="codex", sheet_count=0)["tool_events"]


def _usage(
    events: Sequence[dict[str, Any]],
    reviewer: str,
    *,
    success_events: Sequence[dict[str, Any]] | None = None,
    first_turn_usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Sum billed attempts; take first-turn cache evidence from the verdict attempt."""
    rows = [row.get("event", row) for row in events]
    successful = (
        rows if success_events is None
        else [row.get("event", row) for row in success_events]
    )
    if reviewer == "codex":
        keys = ("input_tokens", "cached_input_tokens", "output_tokens")
        usage = {
            key: sum(
                (row.get("usage") or {}).get(key, 0)
                for row in rows if row.get("type") == "turn.completed"
            )
            for key in keys
        }
        usage["first_turn"] = {
            key: (first_turn_usage or {}).get(key, 0) for key in keys
        }
        return usage
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
         for row in successful if row.get("type") == "assistant"),
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





def _retain_attempt_dir(source: Path, destination: Path) -> str | None:
    """Preserve evidence even while a Windows child still holds its cwd."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(source), str(destination))
        return None
    except OSError as exc:
        warning = f"move failed ({type(exc).__name__}: {exc}); retained by copying"
    if source.exists():
        shutil.copytree(source, destination, dirs_exist_ok=True)
        try:
            shutil.rmtree(source)
        except OSError as exc:
            warning += f"; original cleanup failed ({type(exc).__name__}: {exc})"
    return warning


def _retained_argv(
    command: Sequence[str], attempt_dir: Path, retained_dir: Path
) -> list[str]:
    """Adapt artifact paths for inspection; this is NOT an executable replay.

    The original session id and missing stdin deliberately remain visible.
    Actual execution provenance is always retained separately in ``command``.
    """
    def adapted(value: str) -> str:
        path = Path(value)
        if path.is_absolute() and path.is_relative_to(attempt_dir):
            return str(retained_dir / path.relative_to(attempt_dir))
        return value

    result = []
    for argument in command:
        if "=" in argument:
            key, value = argument.split("=", 1)
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                decoded = None
            if isinstance(decoded, str) and adapted(decoded) != decoded:
                result.append(f"{key}={json.dumps(adapted(decoded))}")
                continue
        result.append(adapted(argument))
    return result

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
    # Snapshot the sources once: the injected text layer, the recorded hashes
    # and every attempt's sheet images must come from the same bytes, even if a
    # concurrent build rewrites the originals mid-review.
    snapshot_dir = report_dir / f"{package.name}.sources"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_sources = []
    for source in package.sources:
        target = snapshot_dir / source.name
        shutil.copyfile(source, target)
        snapshot_sources.append(target)
    snapshot = ReviewPackage(package.name, package.kind, tuple(snapshot_sources))
    mcp_catalog = _sheet_resource_manifest(snapshot.sources)
    neutral_resources = reviewer == "codex" and _resource_neutrality_permitted(mcp_catalog)
    model = model or DEFAULT_MODELS[reviewer]
    effort = effort or DEFAULT_EFFORTS[reviewer]
    executable = (claude if reviewer == "claude" else codex) or shutil.which(reviewer)
    if not executable:
        raise RuntimeError(f"{reviewer} CLI not found on PATH")
    prompt = _review_prompt(
        snapshot, sheet_count, reviewer=reviewer, prompt_text=prompt_text
    )
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    source_sha = [_sha256(source) for source in snapshot.sources]
    schema_bytes = SCHEMA_FILE.read_bytes()
    report_dir.mkdir(parents=True, exist_ok=True)
    events_path = report_dir / f"{package.name}.events.jsonl"

    started = time.monotonic()
    error: str | None = None
    verdict: dict[str, Any] | None = None
    events: list[dict[str, Any]] = []
    tool_history: list[dict[str, Any]] = []
    context_errors: list[str] = []
    success_events: list[dict[str, Any]] = []
    success_calls: list[dict[str, Any]] = []
    success_first_turn: dict[str, Any] = {}
    attempt_records: list[dict[str, Any]] = []
    attempts = 0
    for attempt in range(retries + 1):
        attempts = attempt + 1
        attempt_dir = Path(tempfile.mkdtemp(prefix="machrev-"))
        cwd = attempt_dir
        session_id: str | None = str(uuid.uuid4()) if reviewer == "claude" else None
        attempt_events: list[dict[str, Any]] = []
        rollout_rows: list[dict[str, Any]] = []
        rollout_details: dict[str, Any] = {
            "events": [], "context_errors": [], "first_turn_usage": {},
        }
        rollout_checked = False
        attempt_context: list[str] = []
        stdout: str | bytes | None = None
        stderr: str | bytes | None = None
        attempt_record: dict[str, Any] = {
            "attempt": attempts,
            "reviewer": reviewer,
            "cwd": str(cwd),
            "attempt_dir": str(attempt_dir),
            "codex_home": str(CODEX_HOME) if reviewer == "codex" else None,
            "sources": [str(source.resolve()) for source in snapshot.sources],
            "retained_dir": None,
            "retained_argv": None,
            "retention_warning": None,
            "rollout_file": None,
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

        def capture_rollout() -> None:
            nonlocal rollout_checked, session_id, rollout_rows, rollout_details
            if reviewer != "codex" or rollout_checked:
                return
            session_id = _codex_session_id(attempt_events)
            if not session_id:
                if attempt_record["exit_code"] == 0:
                    rollout_checked = True
                    attempt_context.append("successful Codex invocation lacks a rollout session id")
                return
            rollout_checked = True
            try:
                _, rollout_rows = load_codex_rollout(session_id, codex_home=CODEX_HOME)
                rollout_details = codex_rollout_evidence(
                    rollout_rows, prompt, neutral_resources=neutral_resources
                )
                attempt_context.extend(rollout_details["context_errors"])
            except Exception as exc:
                attempt_context.append(f"Codex rollout unavailable: {type(exc).__name__}: {exc}")

        try:
            resolved_attempt = attempt_dir.resolve()
            if any(
                (parent / ".git").exists()
                for parent in (resolved_attempt, *resolved_attempt.parents)
            ):
                raise RuntimeError("reviewer attempt directory must be outside every git repository")
            schema = attempt_dir / "schema.json"
            schema.write_bytes(schema_bytes)
            mcp_config = attempt_dir / "mcp.json"
            output = attempt_dir / "verdict.json"
            env = None
            if reviewer == "claude":
                mcp_config.write_text(json.dumps({
                    "mcpServers": {
                        "sheets": {
                            "command": sys.executable,
                            "args": [str(SHEETS_SERVER), *(str(p.resolve()) for p in snapshot.sources)],
                        },
                    },
                }), encoding="utf-8")
                cmd = build_claude_command(
                    workdir=attempt_dir, mcp_config=mcp_config, schema=schema,
                    model=model, effort=effort, session_id=session_id, claude=executable,
                )
            else:
                env = prepare_codex_environment(
                    codex_home=CODEX_HOME, attempt_dir=attempt_dir,
                    model=model, codex=executable,
                )
                cmd = build_codex_command(
                    workdir=cwd, attempt_dir=attempt_dir, sources=snapshot.sources,
                    schema=schema, output=output, model=model, effort=effort,
                    codex=executable,
                )
            attempt_record["command"] = cmd
            proc = subprocess.run(
                cmd, input=prompt, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout_s,
                cwd=str(cwd), env=env,
            )
            attempt_record["exit_code"] = proc.returncode
            stdout, stderr = proc.stdout, proc.stderr
            attempt_events = _parse_events(proc.stdout)
            capture_rollout()
            if attempt_context:
                raise RuntimeError("; ".join(attempt_context))
            if proc.returncode != 0:
                reported = next(
                    (str(event["result"]) for event in reversed(attempt_events)
                     if event.get("is_error") and event.get("result")),
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
            success_calls = (
                list(attempt_events) if reviewer == "claude"
                else list(rollout_details["events"])
            )
            success_first_turn = dict(rollout_details["first_turn_usage"])
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
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            attempt_record["error"] = error
            verdict = None
        finally:
            capture_rollout()
            if reviewer == "codex" and attempt_record["command"] is not None:
                _warn_auth(relink_codex_auth(CODEX_HOME))
            if attempt_record["command"] is None:
                # A planned Claude UUID is not a persisted, resumable session.
                session_id = None
            attempt_record["session_id"] = session_id
            attempt_record["resume_command"] = _resume_command(reviewer, session_id)
            events.extend(_tag_events(attempts, attempt_events))
            calls = attempt_events if reviewer == "claude" else rollout_details["events"]
            tool_history.extend(_tag_events(attempts, calls))
            context_errors.extend(f"attempt {attempts}: {value}" for value in attempt_context)
            retained_dir = report_dir / f"{package.name}.attempts" / attempt_dir.name
            attempt_record["retention_warning"] = _retain_attempt_dir(attempt_dir, retained_dir)
            attempt_record["retained_dir"] = str(retained_dir)
            if attempt_record["command"]:
                attempt_record["retained_argv"] = _retained_argv(
                    attempt_record["command"], attempt_dir, retained_dir
                )
            if rollout_rows:
                path = retained_dir / "rollout.jsonl"
                _write_events(path, rollout_rows)
                attempt_record["rollout_file"] = str(path)
            for stream, content in (("stdout", stdout), ("stderr", stderr)):
                if content is not None:
                    path = retained_dir / f"{stream}.txt"
                    path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
                    attempt_record[f"{stream}_file"] = str(path)
            inputs = {"schema.json", "mcp.json", "stdout.txt", "stderr.txt", "rollout.jsonl"}
            attempt_record["artifacts"] = [
                str(artifact) for artifact in sorted(retained_dir.iterdir())
                if artifact.name not in inputs
            ]

    _write_events(events_path, events)
    evidence = evaluate_sheet_evidence(
        tool_history, reviewer=reviewer, sheet_count=sheet_count,
        neutral_resources=neutral_resources,
    )
    successful = evaluate_sheet_evidence(
        success_calls, reviewer=reviewer, sheet_count=sheet_count,
        neutral_resources=neutral_resources,
    )
    tool_events = evidence["tool_events"]
    inspection_proven = successful["inspection_proven"]
    extra = {
        "sheets_viewed": successful["sheets_viewed"],
        "inspection_proven": inspection_proven,
        "crop_calls": evidence["crop_calls"],
        "crops": evidence["crops"],
        "neutral_calls": evidence["neutral_calls"],
        "exceptions": [
            {
                "id": exception.id,
                "where": exception.where,
                "finding": exception.finding,
                "reason": exception.reason,
                "kind": exception.kind,
            }
            for exception in _load_exceptions(CAD_ROOT / "config", package.name, package.kind)
        ],
        "context_errors": context_errors,
        "usage": _usage(
            events, reviewer, success_events=success_events,
            first_turn_usage=success_first_turn,
        ),
        "evidence": {
            "effective_prompt": prompt,
            "schema": schema_bytes.decode("utf-8"),
            "attempts": attempt_records,
            "mcp_catalog": mcp_catalog,
        },
    }
    # A provider failure is not evidence of unauthorized access. Successful
    # verdicts still require every sheet viewed; neither kind of failure passes.
    blind = tool_events == 0 and not context_errors and (error is not None or inspection_proven)
    review = Review(
        name=package.name, kind=package.kind, sources=[str(source) for source in package.sources],
        source_sha256=source_sha, verdict=verdict,
        passed=is_pass(verdict) and blind and error is None and inspection_proven,
        blind=blind, tool_events=tool_events, reviewer=reviewer, model=model,
        effort=effort, prompt_sha256=prompt_sha, sheet_count=sheet_count,
        duration_s=round(time.monotonic() - started, 1),
        reviewed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        error=error, events_file=str(events_path), attempts=attempts, extra=extra,
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
    parser.add_argument("--reviewer", choices=REVIEWERS, default="claude")
    parser.add_argument(
        "--model",
        help=(
            f"reviewer model (defaults: {DEFAULT_MODELS}; "
            "claude also takes claude-fable-5-1)"
        ),
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
