r"""Blind senior-machinist review of rendered drawing packages via Claude.

The review the fleet is gated on (``cad/docs/drawing-simplicity-policy.md``):
each drawing package is rendered or copied into a neutral temp directory and
handed to ``claude -p --model claude-fable-5-1 --effort medium`` (or
``codex exec --model gpt-6-astra`` at low reasoning) with NO repo context under
the calibrated prompt in ``cad/scripts/prompts/``. ``--reviewer`` is mandatory
and MUST name a different model family from the agent that authored or last
edited the drawing script: a Claude-driven session (Fable, Opus, Sonnet)
reviews with ``--reviewer codex``, a Codex/GPT-driven session with
``--reviewer claude``. A same-family verdict is not the gate, even a ``SHIP``.
``--author-family`` names the author's family explicitly and a same-family pair
is refused unless ``--last-resort`` says so. A last-resort run needs the
cross-family reviewer's quota refusal for that drawing, which this tool keeps as
``<name>.quota-refused.json`` when a run is refused for usage limits, and an
author model (read from the draw script's last commit trailer) that meets the
tier rule; otherwise it is refused before any reviewer runs. ``--rebuttals``
answers a FIX verdict's gating findings with cited user rulings, recording it
as ``accepted_with_rulings``. Registry part and assembly
PDFs are split into full-resolution page images and every page is supplied
to one reviewer invocation. The schema-validated verdict and its
provenance are written under ``cad/out/reports/machinist-review/``, and a
passing registry-drawing review is also recorded in the tracked review ledger
(``machinist_ledger.py``) with the content of every sheet it saw, so the drift
check can tell later whether the sheet now shipping is the one reviewed.

Why the prompt is calibrated the way it is: the earlier ad-hoc reviews asked a
"senior machinist" to hunt for MISSING tolerances / datums / finishes and were
rewarded for gaps, so the fleet grew inspection-package GD&T on hand-crank
parts.  The prompt now reads the title block as the general spec, scores
over-specification as a defect, and encodes the shop-practice rules from
Harvey (*Machine Shop Trade Secrets*, ch. 9) and Lipton (*Metalworking Sink or
Swim*, ch. 2-3): decimal places carry tolerance, GD&T only where a ± cannot
say it, hidden lines on, one origin, drill vs ream, few specific notes.

Isolation is enforced by Claude's restricted mode in a neutral temp directory:
nothing in the invocation references the repo, every page is copied as a
``sheet-N.png``, safe mode disables project/user customizations, MCP is disabled,
and Read is the only available tool. The event stream is scanned so any tool
use beyond reading the copied package images flags the review as non-blind.
Blindness is enforced by those tool restrictions and the neutral workdir, not
by ephemerality: each attempt's session transcript is kept under the CLI's own
home instead of discarded, on a fresh session id per attempt so it never loads
prior context. The verdict JSON's attempt records name the session id and a
ready-to-run resume command (``claude --resume <id>`` / ``codex resume <id>``)
so a completed review's reasoning can be reopened offline.

Usage (SolidWorks-free; needs the native PDFs under ``cad/out/pdf``)::

    uv run cad/scripts/machinist_review.py crank_arm pivot_shaft --reviewer codex --author-family claude
    uv run cad/scripts/machinist_review.py --all --jobs 4 --reviewer codex --author-family claude
    uv run cad/scripts/machinist_review.py --png sheet-1.png --png sheet-2.png --kind assembly         --reviewer codex --author-family claude
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
import machinist_ledger  # noqa: E402

PROMPTS_DIR = SCRIPTS_DIR / "prompts"
PROMPT_FILES = {
    "part": PROMPTS_DIR / "machinist_review_part.md",
    "assembly": PROMPTS_DIR / "machinist_review_assembly.md",
}
SCHEMA_FILE = PROMPTS_DIR / "machinist_review_schema.json"
REPORT_DIR = CAD_ROOT / "out" / "reports" / "machinist-review"
QUOTA_REFUSED_SUFFIX = ".quota-refused.json"

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
# PDFium's native API is process-global and not thread-safe.  Hold this only while
# opening/counting/rendering/closing PDFs; Codex review subprocesses remain parallel.
# The ledger renders too (recording a passing review), so it is the ledger's lock.
_PDFIUM_LOCK = machinist_ledger._PDFIUM_LOCK


# Event/item types that indicate tool or command activity. Claude permits only
# Read(sheet.png) and StructuredOutput; Codex permits none of these.
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
    return PROMPT_FILES[kind].read_text(encoding="utf-8")


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


def _pdf_page_count(path: Path) -> int:
    import pypdfium2 as pdfium

    with _PDFIUM_LOCK:
        document = pdfium.PdfDocument(str(path))
        try:
            page_count = len(document)
        finally:
            document.close()
    if page_count < 1:
        raise ValueError(f"PDF has no sheets: {path}")
    return page_count


def _sheet_count(package: ReviewPackage) -> int:
    return sum(
        _pdf_page_count(source) if source.suffix.casefold() == ".pdf" else 1
        for source in package.sources
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


def _materialize_images(package: ReviewPackage, workdir: Path) -> list[Path]:
    import pypdfium2 as pdfium

    images: list[Path] = []
    for source in package.sources:
        if source.suffix.casefold() != ".pdf":
            image = workdir / f"sheet-{len(images) + 1}.png"
            shutil.copyfile(source, image)
            images.append(image)
            continue
        with _PDFIUM_LOCK:
            document = pdfium.PdfDocument(str(source))
            try:
                for page_index in range(len(document)):
                    page = document[page_index]
                    try:
                        rendered = page.render(scale=300.0 / 72.0).to_pil()
                        image = workdir / f"sheet-{len(images) + 1}.png"
                        rendered.save(image, dpi=(300, 300))
                        images.append(image)
                    finally:
                        page.close()
            finally:
                document.close()
    return images


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
        "Return one verdict for the package as a whole.\n"
    )
    if sheet_count > 1:
        prompt += (
            "Compare every sheet against every other sheet before accepting SHIP.\n"
        )
    if reviewer == "claude":
        prompt = (
            f"Use the Read tool to inspect every copied sheet-1.png through "
            f"sheet-{sheet_count}.png in order. Do not read any other file. "
            "Then perform this blind review.\n\n" + prompt
        )
    return prompt


def build_claude_command(
    *,
    workdir: Path,
    images: Sequence[Path],
    schema: Path,
    model: str,
    effort: str,
    session_id: str,
    claude: str = "claude",
    schema_content: str | None = None,
) -> list[str]:
    """Return the exact isolated ``claude -p`` argv for one package."""
    if (
        schema.parent != workdir
        or not images
        or any(image.parent != workdir for image in images)
    ):
        raise ValueError("review inputs must be inside the neutral workdir")
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
        "Read",
        "--allowedTools",
        *(f"Read({image.name})" for image in images),
        "--restricted",
        "--safe-mode",
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
    images: Sequence[Path],
    schema: Path,
    output: Path,
    model: str,
    effort: str,
    codex: str = "codex",
) -> list[str]:
    """Return the exact isolated ``codex exec`` argv for one package."""
    if not images or any(path.parent != workdir for path in (*images, schema, output)):
        raise ValueError("review inputs and output must be inside the neutral workdir")
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
    for image in images:
        command.extend(("-i", str(image)))
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


def _claude_event_evidence(
    events: Sequence[dict[str, Any]], *, allowed_images: Sequence[Path]
) -> tuple[int, set[Path]]:
    """Return unauthorized-event count and copied package images read."""
    allowed = {path.resolve() for path in allowed_images}
    workdirs = {path.parent for path in allowed}
    unauthorized = 0
    reads: set[Path] = set()
    for event in events:
        event_unauthorized = False
        for node in _walk(event):
            if not isinstance(node, dict):
                continue
            kind = str(node.get("type", "")).lower()
            name = str(node.get("name", "")).lower()
            if kind == "tool_use" and name == "structuredoutput":
                continue
            if kind == "tool_use" and name == "read":
                tool_input = node.get("input")
                raw_path = (
                    tool_input.get("file_path")
                    if isinstance(tool_input, dict)
                    else None
                )
                if raw_path:
                    candidates = (
                        [Path(str(raw_path))]
                        if Path(str(raw_path)).is_absolute()
                        else [workdir / str(raw_path) for workdir in workdirs]
                    )
                    match = next(
                        (
                            candidate.resolve()
                            for candidate in candidates
                            if candidate.resolve() in allowed
                        ),
                        None,
                    )
                    if match is not None:
                        reads.add(match)
                        continue
                event_unauthorized = True
                continue
            if ("command" in node and node.get("command")) or any(
                marker in kind for marker in _TOOL_EVENT_MARKERS
            ):
                event_unauthorized = True
        unauthorized += int(event_unauthorized)
    return unauthorized, reads


def count_tool_events(
    events: Sequence[dict[str, Any]], *, allowed_images: Sequence[Path] = ()
) -> int:
    return _claude_event_evidence(events, allowed_images=allowed_images)[0]


def count_codex_tool_events(events: Sequence[dict[str, Any]]) -> int:
    """Count every Codex tool or command event; blind reviews permit none."""
    return _claude_event_evidence(events, allowed_images=())[0]


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
    allowed_images: list[Path] = []
    verdict_images: list[Path] = []
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
            "images": [],
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
            images = _materialize_images(package, workdir)
            attempt_record["images"] = [str(image) for image in images]
            allowed_images.extend(images)
            if len(images) != sheet_count:
                raise RuntimeError(
                    f"{package.name}: materialized {len(images)} sheets, "
                    f"expected {sheet_count}"
                )
            schema = workdir / "schema.json"
            schema.write_bytes(schema_bytes)
            output = workdir / "verdict.json"
            cmd = (
                build_claude_command(
                    workdir=workdir,
                    images=images,
                    schema=schema,
                    model=model,
                    effort=effort,
                    session_id=session_id,
                    claude=executable,
                )
                if reviewer == "claude"
                else build_codex_command(
                    workdir=workdir,
                    images=images,
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
                raise RuntimeError(
                    f"{reviewer} exit {proc.returncode}: {proc.stderr.strip()[-800:]}"
                )
            verdict = (
                extract_claude_verdict(attempt_events)
                if reviewer == "claude"
                else extract_codex_verdict(output, attempt_events)
            )
            verdict_images = list(images)
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
            retained_dir.mkdir(parents=True, exist_ok=True)
            for stream, content in (("stdout", stdout), ("stderr", stderr)):
                if content is not None:
                    path = retained_dir / f"{stream}.txt"
                    path.write_bytes(
                        content
                        if isinstance(content, bytes)
                        else content.encode("utf-8")
                    )
                    attempt_record[f"{stream}_file"] = str(path)
            # Inputs are already identified by the source hashes, image paths,
            # and retained schema. Move generated artifacts rather than copying
            # the entire workdir (and every drawing image) on each retry.
            inputs = {Path(image) for image in attempt_record["images"]}
            inputs.add(workdir / "schema.json")
            for artifact in sorted(workdir.iterdir()):
                if artifact in inputs:
                    continue
                artifact_dir = retained_dir / "artifacts"
                artifact_dir.mkdir(exist_ok=True)
                retained = artifact_dir / artifact.name
                shutil.move(str(artifact), str(retained))
                attempt_record["artifacts"].append(str(retained))
            shutil.rmtree(workdir, ignore_errors=True)

    _write_events(events_path, events)
    if reviewer == "claude":
        tool_events, _ = _claude_event_evidence(events, allowed_images=allowed_images)
        _, read_images = _claude_event_evidence(
            success_events, allowed_images=verdict_images
        )
        inspection_proven = bool(verdict_images) and set(verdict_images) == read_images
        extra = {
            "image_read_events": len(read_images),
            "images_read": sorted(path.name for path in read_images),
        }
    else:
        tool_events = count_codex_tool_events(events)
        inspection_proven = True
        extra = {}
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
    lines = [
        f"# {review.name} — {'PASS' if review.passed else 'FAIL'}",
        "",
        f"- kind: {review.kind}",
        f"- sheets: {review.sheet_count}",
        f"- reviewed: {review.reviewed_at} by {review.reviewer}/{review.model} "
        f"({review.effort}), {review.duration_s}s, attempts {review.attempts}",
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
        if path.name.endswith(QUOTA_REFUSED_SUFFIX):  # evidence, not a report
            continue
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
    parser.add_argument("--reviewer", choices=REVIEWERS)
    parser.add_argument(
        "--author-family",
        choices=machinist_ledger.AUTHOR_FAMILIES,
        help="model family that authored or last edited the drawing script; "
        "must differ from the reviewer's family",
    )
    parser.add_argument(
        "--last-resort",
        action="store_true",
        help="allow a same-family review because the cross-family reviewer refused "
        "this drawing on quota; recorded as last_resort",
    )
    parser.add_argument(
        "--author-model",
        help="cross-check for the model in the draw script's last commit trailer",
    )
    parser.add_argument(
        "--quota-refusal",
        type=Path,
        help="the cross-family reviewer's quota-refused report "
        "(default: <report-dir>/<name>.quota-refused.json)",
    )
    parser.add_argument(
        "--rebuttals",
        type=Path,
        help="cited user rulings answering every gating finding of this run's verdict",
    )
    parser.add_argument("--ledger", type=Path, default=machinist_ledger.LEDGER_PATH)
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
    if args.author_family is None:
        print(
            "--author-family is required for review runs (claude, gpt or mimo)",
            file=sys.stderr,
        )
        return 2
    same_family = machinist_ledger.reviewer_family(args.reviewer) == args.author_family
    if same_family and not args.last_resort:
        print(
            f"--reviewer {args.reviewer} is the same family as the {args.author_family} "
            "author, so its verdict is not the gate; use the other reviewer "
            "(or --last-resort to record it as last_resort)",
            file=sys.stderr,
        )
        return 2
    if args.last_resort and not same_family:
        print("--last-resort applies only to a same-family review", file=sys.stderr)
        return 2
    args.refusal = None
    if args.rebuttals is not None and (args.png or args.all or len(args.names) != 1):
        print("--rebuttals applies to exactly one registry drawing", file=sys.stderr)
        return 2
    if args.last_resort:
        problem = _last_resort_problem(args)
        if problem:
            print(f"--last-resort refused: {problem}", file=sys.stderr)
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
    unrecorded: list[str] = []
    accepted: list[str] = []
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
            _keep_quota_refusal(review, report_dir)
            recorded = _record_in_ledger(review, package, args, prompt_text)
            if recorded is None:
                unrecorded.append(review.name)
            elif recorded and recorded.status == machinist_ledger.ACCEPTED_WITH_RULINGS:
                accepted.append(review.name)
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
    failed = [r.name for r in reviews if not r.passed and r.name not in accepted]
    errored = len(packages) - len(reviews)
    print(
        f"{len(reviews) - len(failed)}/{len(packages)} pass; index: {index}",
        file=sys.stderr,
    )
    return 0 if not failed and not errored and not unrecorded else 1


def _record_in_ledger(
    review: Review,
    package: ReviewPackage,
    args: argparse.Namespace,
    prompt_text: str | None,
) -> machinist_ledger.Recorded | bool | None:
    """Record an accepted registry-drawing review; None when it failed or does not count.

    Arbitrary ``--png`` packages and rubric overrides are not the gate, so they
    never enter the ledger.  A FIX enters it only with ``--rebuttals``.
    """
    if args.png or prompt_text is not None or review.verdict is None:
        return False
    if not review.passed and args.rebuttals is None:
        return False
    try:
        recorded = machinist_ledger.record_review(
            asdict(review),
            package.sources[0],
            author_family=args.author_family,
            author_model=args.author_model,
            refusal=args.refusal,
            rebuttals=None
            if review.passed or args.rebuttals is None
            else machinist_ledger.load_rebuttals(args.rebuttals, name=review.name),
            provenance={
                **machinist_ledger.git_state(),
                "report": (args.report_dir / f"{review.name}.json").resolve().as_posix(),
            },
            ledger_path=args.ledger,
        )
    except (OSError, ValueError) as exc:
        print(f"{review.name}: not recorded in the ledger: {exc}", file=sys.stderr)
        return None
    if not recorded.counts:
        # Recorded is not accepted: the pre-run check can pass and the evidence
        # still lapse before the reviewer finishes (a refusal ageing past 24 h).
        print(
            f"{recorded.name}: {recorded.slot} review recorded in the ledger but does "
            f"NOT count: {recorded.problem}",
            file=sys.stderr,
        )
        return None
    print(
        f"ledger: {recorded.name} recorded as {recorded.slot} {recorded.status} "
        f"({len(recorded.sheets)} sheets) in {args.ledger}",
        file=sys.stderr,
    )
    return recorded


def _keep_quota_refusal(review: Review, report_dir: Path) -> None:
    """Keep a usage-limit refusal where the next run's report cannot overwrite it."""
    if review.verdict is not None:
        return
    report = report_dir / f"{review.name}.json"
    if machinist_ledger.quota_evidence(asdict(review), report) is None:
        return
    kept = report_dir / f"{review.name}{QUOTA_REFUSED_SUFFIX}"
    shutil.copyfile(report, kept)
    print(
        f"{review.name}: {review.reviewer} refused on quota; kept {kept} as the "
        "evidence a same-family --last-resort run needs",
        file=sys.stderr,
    )


def _last_resort_problem(args: argparse.Namespace) -> str:
    """Why a same-family run would not count as the policy's last resort.

    Checked before any reviewer runs, so a run that could never count spends
    no quota.  Sets ``args.refusal`` to the recorded quota refusal.
    """
    if args.png or args.all or len(args.names) != 1:
        return "name exactly one registry drawing; a quota refusal is per drawing"
    if args.prompt_file is not None:
        return "a rubric override is not the gate"
    name = args.names[0]
    refusal_report = args.quota_refusal or args.report_dir / f"{name}{QUOTA_REFUSED_SUFFIX}"
    if refusal_report.resolve() == (args.report_dir / f"{name}.json").resolve():
        return f"{refusal_report} is the report this run overwrites; pass its kept copy"
    model = args.model or DEFAULT_MODELS[args.reviewer]
    effort = args.effort or DEFAULT_EFFORTS[args.reviewer]
    try:
        author = machinist_ledger.resolve_author(name, args.author_family, args.author_model)
        args.refusal = machinist_ledger.quota_refusal(
            refusal_report, name=name, author_family=args.author_family
        )
    except (OSError, ValueError, KeyError) as exc:
        return str(exc)
    pdf = DRAWINGS_BY_NAME[name].outputs["pdf"]
    if not pdf.is_file():
        return f"no rendered PDF at {pdf}"
    stale = machinist_ledger.refusal_problem(
        args.refusal,
        pdf_sha256=machinist_ledger.sha256_file(pdf),
        reviewed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    if stale:
        return stale
    if author["model_source"] != "trailer":
        return "the draw script's last commit names no author model in a trailer"
    return machinist_ledger.last_resort_tier_problem(author["model"], model, effort) or ""


if __name__ == "__main__":
    sys.exit(main())
