r"""Blind senior-machinist review of rendered drawing sheets via Claude or Codex.

The review the fleet is gated on (``cad/docs/drawing-simplicity-policy.md``):
each sheet PNG is copied into a neutral temp directory and handed to the
explicitly selected reviewer with NO repo context, under the calibrated prompt
in ``cad/scripts/prompts/`` — a part print gets the part prompt, an assembly
orientation sheet the assembly prompt.  The verdict comes back as structured
JSON (``machinist_review_schema.json``) and is written, with its reviewer,
model, and effort provenance, under ``cad/out/reports/machinist-review/``.

Why the prompt is calibrated the way it is: the earlier ad-hoc reviews asked a
"senior machinist" to hunt for MISSING tolerances / datums / finishes and were
rewarded for gaps, so the fleet grew inspection-package GD&T on hand-crank
parts.  The prompt now reads the title block as the general spec, scores
over-specification as a defect, and encodes the shop-practice rules from
Harvey (*Machine Shop Trade Secrets*, ch. 9) and Lipton (*Metalworking Sink or
Swim*, ch. 2-3): decimal places carry tolerance, GD&T only where a ± cannot
say it, hidden lines on, one origin, drill vs ream, few specific notes.

Isolation is enforced independently for each provider in a neutral temp
directory. Claude runs restricted and may only Read the copied ``sheet.png``
before returning StructuredOutput. Codex receives the copied image, schema,
and output paths through isolated ``codex exec`` and its event stream must
contain no tool or command activity. A blindness-policy violation fails the
review closed.

The caller deliberately chooses the opposite provider from the agent launching
the review: a GPT/ChatGPT agent passes ``--reviewer claude``; a Claude Code
agent passes ``--reviewer codex``.

Usage (SolidWorks-free; needs the rendered PNGs under ``cad/out/png``)::

    uv run cad/scripts/machinist_review.py --reviewer claude crank_arm pivot_shaft
    uv run cad/scripts/machinist_review.py --reviewer codex --all --jobs 4
    uv run cad/scripts/machinist_review.py --reviewer claude --png some/sheet.png --kind part
    uv run cad/scripts/machinist_review.py --index      # rebuild index.md only

Exit status is 0 only when every reviewed sheet passes (``SHIP`` with no
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from _drawing_registry import DRAWINGS, DRAWINGS_BY_NAME, CAD_ROOT  # noqa: E402

PROMPTS_DIR = SCRIPTS_DIR / "prompts"
PROMPT_FILES = {
    "part": PROMPTS_DIR / "machinist_review_part.md",
    "assembly": PROMPTS_DIR / "machinist_review_assembly.md",
}
SCHEMA_FILE = PROMPTS_DIR / "machinist_review_schema.json"
REPORT_DIR = CAD_ROOT / "out" / "reports" / "machinist-review"

DEFAULT_MODELS = {
    "claude": "fable",
    "codex": "gpt-5.6-sol",
}
DEFAULT_EFFORT = "high"
REVIEWERS = tuple(DEFAULT_MODELS)
FINDING_KEYS = ("blockers", "over_specification", "clarity", "minor")
GATING_KEYS = ("blockers", "over_specification", "clarity")

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
class Sheet:
    name: str
    kind: str  # "part" | "assembly"
    png: Path


@dataclass
class Review:
    name: str
    kind: str
    png: str
    verdict: dict[str, Any] | None
    passed: bool
    blind: bool
    tool_events: int
    reviewer: str
    model: str
    effort: str
    prompt_sha256: str
    png_sha256: str
    duration_s: float
    reviewed_at: str
    error: str | None = None
    events_file: str | None = None
    attempts: int = 1
    extra: dict[str, Any] = field(default_factory=dict)


def sheet_for(name: str) -> Sheet:
    spec = DRAWINGS_BY_NAME[name]
    return Sheet(name=name, kind=spec.source_kind, png=spec.outputs["png"])


def all_sheets() -> list[Sheet]:
    return [sheet_for(spec.name) for spec in DRAWINGS]


def load_prompt(kind: str) -> str:
    return PROMPT_FILES[kind].read_text(encoding="utf-8")


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_claude_command(
    *,
    workdir: Path,
    image: Path,
    schema: Path,
    model: str,
    effort: str,
    claude: str = "claude",
) -> list[str]:
    """Return the exact isolated ``claude -p`` argv."""
    if image.parent != workdir or schema.parent != workdir:
        raise ValueError("review inputs must be inside the neutral workdir")
    schema_json = json.dumps(
        json.loads(schema.read_text(encoding="utf-8")),
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
        "--restricted",
        "--safe-mode",
        "--no-session-persistence",
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
    image: Path,
    schema: Path,
    output: Path,
    model: str,
    effort: str,
    codex: str = "codex",
) -> list[str]:
    """Return the exact isolated ``codex exec`` argv."""
    if any(path.parent != workdir for path in (image, schema, output)):
        raise ValueError("review inputs and output must be inside the neutral workdir")
    return [
        codex,
        "exec",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "-C",
        str(workdir),
        "-m",
        model,
        "-c",
        f"model_reasoning_effort={effort}",
        "-i",
        str(image),
        "--output-schema",
        str(schema),
        "-o",
        str(output),
        "--json",
        "-",
    ]


def _walk(obj: Any) -> Iterable[Any]:
    yield obj
    if isinstance(obj, dict):
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk(value)


def count_claude_tool_events(
    events: Sequence[dict[str, Any]], *, allowed_image: Path
) -> int:
    """Count Claude events other than Read(sheet.png) and StructuredOutput."""
    hits = 0
    for event in events:
        matched = False
        for node in _walk(event):
            if not isinstance(node, dict):
                continue
            kind = str(node.get("type", "")).lower()
            if (
                kind == "tool_use"
                and str(node.get("name", "")).lower() == "structuredoutput"
            ):
                continue
            if kind == "tool_use" and str(node.get("name", "")).lower() == "read":
                tool_input = node.get("input")
                raw_path = (
                    tool_input.get("file_path")
                    if isinstance(tool_input, dict)
                    else None
                )
                if raw_path:
                    read_path = Path(str(raw_path))
                    if not read_path.is_absolute():
                        read_path = allowed_image.parent / read_path
                    if read_path.resolve() == allowed_image.resolve():
                        continue
            if "command" in node and node.get("command"):
                matched = True
                break
            if any(marker in kind for marker in _TOOL_EVENT_MARKERS):
                matched = True
                break
        hits += int(matched)
    return hits


def count_codex_tool_events(events: Sequence[dict[str, Any]]) -> int:
    """Count every Codex event containing tool or command activity."""
    hits = 0
    for event in events:
        matched = False
        for node in _walk(event):
            if not isinstance(node, dict):
                continue
            if "command" in node and node.get("command"):
                matched = True
                break
            kind = str(node.get("type", "")).lower()
            if any(marker in kind for marker in _TOOL_EVENT_MARKERS):
                matched = True
                break
        hits += int(matched)
    return hits


def is_pass(verdict: dict[str, Any] | None) -> bool:
    if not verdict or verdict.get("verdict") != "SHIP":
        return False
    return all(not verdict.get(key) for key in GATING_KEYS)


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


def _validate_verdict(verdict: Any) -> dict[str, Any]:
    if not isinstance(verdict, dict):
        raise RuntimeError("structured verdict is not an object")
    missing = [k for k in ("verdict", "summary", *FINDING_KEYS) if k not in verdict]
    if missing:
        raise RuntimeError(f"verdict missing keys {missing}")
    return verdict


def extract_claude_verdict(events: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Extract Claude's schema-validated structured result."""
    text = ""
    for event in reversed(events):
        structured = event.get("structured_output")
        if isinstance(structured, dict):
            return _validate_verdict(structured)
        if event.get("type") == "result":
            text = str(event.get("result") or "")
            if text.strip():
                break
    if not text.strip():
        raise RuntimeError("claude produced no final message")
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise RuntimeError(f"final message is not JSON: {text[:200]!r}")
    return _validate_verdict(json.loads(text[start : end + 1]))


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
    return _validate_verdict(json.loads(text[start : end + 1]))


def review_sheet(
    sheet: Sheet,
    *,
    reviewer: str,
    model: str | None = None,
    effort: str = DEFAULT_EFFORT,
    report_dir: Path = REPORT_DIR,
    retries: int = 1,
    timeout_s: float = 1800.0,
    claude: str | None = None,
    codex: str | None = None,
) -> Review:
    if reviewer not in REVIEWERS:
        raise ValueError(f"unknown reviewer {reviewer!r}; choose one of {REVIEWERS}")
    if not sheet.png.is_file():
        raise FileNotFoundError(f"{sheet.name}: sheet PNG missing: {sheet.png}")
    model = model or DEFAULT_MODELS[reviewer]
    executable = (claude if reviewer == "claude" else codex) or shutil.which(reviewer)
    if not executable:
        raise RuntimeError(f"{reviewer} CLI not found on PATH")

    prompt = load_prompt(sheet.kind)
    if reviewer == "claude":
        prompt = (
            "Use the Read tool to inspect sheet.png, the only drawing supplied. "
            "Do not read any other file. Then perform this blind review.\n\n"
            + prompt
        )
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    png_sha = _sha256(sheet.png)
    report_dir.mkdir(parents=True, exist_ok=True)
    events_path = report_dir / f"{sheet.name}.events.jsonl"

    started = time.monotonic()
    error: str | None = None
    verdict: dict[str, Any] | None = None
    events: list[dict[str, Any]] = []
    attempts = 0
    image: Path | None = None
    for attempt in range(retries + 1):
        attempts = attempt + 1
        workdir = Path(tempfile.mkdtemp(prefix="machrev-"))
        try:
            image = workdir / "sheet.png"
            shutil.copyfile(sheet.png, image)
            schema = workdir / "schema.json"
            shutil.copyfile(SCHEMA_FILE, schema)
            output = workdir / "verdict.json"
            if reviewer == "claude":
                cmd = build_claude_command(
                    workdir=workdir,
                    image=image,
                    schema=schema,
                    model=model,
                    effort=effort,
                    claude=executable,
                )
            else:
                cmd = build_codex_command(
                    workdir=workdir,
                    image=image,
                    schema=schema,
                    output=output,
                    model=model,
                    effort=effort,
                    codex=executable,
                )
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
            events = _parse_events(proc.stdout)
            events_path.write_text(
                "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    f"{reviewer} exit {proc.returncode}: {proc.stderr.strip()[-800:]}"
                )
            verdict = (
                extract_claude_verdict(events)
                if reviewer == "claude"
                else extract_codex_verdict(output, events)
            )
            error = None
            break
        except Exception as exc:  # noqa: BLE001 - recorded, retried, reported
            error = f"{type(exc).__name__}: {exc}"
            verdict = None
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    if image is None:
        raise RuntimeError("review attempt did not create its neutral image")
    tool_events = (
        count_claude_tool_events(events, allowed_image=image)
        if reviewer == "claude"
        else count_codex_tool_events(events)
    )
    review = Review(
        name=sheet.name,
        kind=sheet.kind,
        png=str(sheet.png),
        verdict=verdict,
        passed=is_pass(verdict) and tool_events == 0,
        blind=tool_events == 0,
        tool_events=tool_events,
        reviewer=reviewer,
        model=model,
        effort=effort,
        prompt_sha256=prompt_sha,
        png_sha256=png_sha,
        duration_s=round(time.monotonic() - started, 1),
        reviewed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        error=error,
        events_file=str(events_path),
        attempts=attempts,
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
    lines = [
        f"# {review.name} — {'PASS' if review.passed else 'FAIL'}",
        "",
        f"- kind: {review.kind}",
        f"- reviewed: {review.reviewed_at} by {review.reviewer}/{review.model} "
        f"({review.effort}), {review.duration_s}s, attempts {review.attempts}",
        f"- blind: {review.blind} (tool events: {review.tool_events})",
        f"- png sha256: {review.png_sha256[:12]}  prompt sha256: {review.prompt_sha256[:12]}",
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
        data = json.loads(path.read_text(encoding="utf-8"))
        reviews.append(Review(**data))
    return reviews


def render_index(reviews: Sequence[Review]) -> str:
    def _n(review: Review, key: str) -> str:
        return str(len((review.verdict or {}).get(key) or []))

    passed = sum(1 for r in reviews if r.passed)
    lines = [
        "# Machinist review index",
        "",
        f"{passed}/{len(reviews)} sheets pass. Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}.",
        "",
        "| sheet | kind | result | verdict | blockers | over-spec | clarity | minor | blind | reviewed |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(reviews, key=lambda r: (r.passed, r.name)):
        verdict = (r.verdict or {}).get("verdict", "ERROR" if r.error else "?")
        lines.append(
            f"| [{r.name}]({r.name}.md) | {r.kind} | {'PASS' if r.passed else 'FAIL'} | "
            f"{verdict} | {_n(r, 'blockers')} | {_n(r, 'over_specification')} | "
            f"{_n(r, 'clarity')} | {_n(r, 'minor')} | {'yes' if r.blind else 'NO'} | "
            f"{r.reviewed_at} |"
        )
    return "\n".join(lines) + "\n"


def write_index(report_dir: Path = REPORT_DIR) -> Path:
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
    parser.add_argument("--png", type=Path, help="review one arbitrary sheet PNG")
    parser.add_argument("--kind", choices=("part", "assembly"), default="part")
    parser.add_argument("--reviewer", choices=REVIEWERS)
    parser.add_argument(
        "--model", help="reviewer model (defaults to fable or gpt-5.6-sol)"
    )
    parser.add_argument("--effort", default=DEFAULT_EFFORT)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument(
        "--timeout", type=float, default=1800.0, help="seconds per sheet"
    )
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--index", action="store_true", help="only rebuild index.md")
    parser.add_argument(
        "--missing-ok",
        action="store_true",
        help="skip sheets whose PNG is not rendered instead of failing",
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

    sheets: list[Sheet]
    if args.png:
        sheets = [Sheet(name=args.png.stem, kind=args.kind, png=args.png.resolve())]
    elif args.all:
        sheets = all_sheets()
    else:
        unknown = [n for n in args.names if n not in DRAWINGS_BY_NAME]
        if unknown or not args.names:
            print(f"unknown or missing drawing names: {unknown}", file=sys.stderr)
            return 2
        sheets = [sheet_for(n) for n in args.names]
    if args.missing_ok:
        skipped = [s.name for s in sheets if not s.png.is_file()]
        if skipped:
            print(
                f"skipping {len(skipped)} unrendered sheets: {skipped}", file=sys.stderr
            )
        sheets = [s for s in sheets if s.png.is_file()]

    reviews: list[Review] = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = {
            pool.submit(
                review_sheet,
                sheet,
                reviewer=args.reviewer,
                model=args.model,
                effort=args.effort,
                report_dir=report_dir,
                retries=args.retries,
                timeout_s=args.timeout,
            ): sheet
            for sheet in sheets
        }
        for future in as_completed(futures):
            sheet = futures[future]
            try:
                review = future.result()
            except Exception as exc:  # noqa: BLE001 - one sheet must not sink the run
                print(f"{sheet.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
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
    errored = len(sheets) - len(reviews)
    print(
        f"{len(reviews) - len(failed)}/{len(sheets)} pass; index: {index}",
        file=sys.stderr,
    )
    return 0 if not failed and not errored else 1


if __name__ == "__main__":
    sys.exit(main())
