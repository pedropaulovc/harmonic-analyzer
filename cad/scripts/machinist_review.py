r"""Blind senior-machinist review of rendered drawing packages via Claude.

The review the fleet is gated on (``cad/docs/drawing-simplicity-policy.md``):
each drawing package is rendered or copied into a neutral temp directory and
handed to ``claude -p --model fable --effort high`` with NO repo context under
the calibrated prompt in ``cad/scripts/prompts/``. A part print is one PNG; an
assembly PDF is split into full-resolution page images and every page is
supplied to one reviewer invocation. The schema-validated verdict and its
provenance are written under ``cad/out/reports/machinist-review/``.

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

Usage (SolidWorks-free; needs the rendered PNGs under ``cad/out/png``)::

    uv run cad/scripts/machinist_review.py crank_arm pivot_shaft
    uv run cad/scripts/machinist_review.py --all --jobs 4
    uv run cad/scripts/machinist_review.py --png sheet-1.png --png sheet-2.png --kind assembly
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
import threading
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

DEFAULT_MODEL = "fable"
DEFAULT_EFFORT = "high"
FINDING_KEYS = ("blockers", "over_specification", "clarity", "minor")
GATING_KEYS = ("blockers", "over_specification", "clarity")
# PDFium's native API is process-global and not thread-safe.  Hold this only while
# opening/counting/rendering/closing PDFs; Codex review subprocesses remain parallel.
_PDFIUM_LOCK = threading.Lock()


# Claude must use Read once to inspect the neutral ``sheet.png`` copy.  Any
# other tool use in the stream means the review escaped the intended input.
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
    source = spec.outputs["pdf" if spec.source_kind == "assembly" else "png"]
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
    stem = resolved[0].stem if len(resolved) == 1 else "assembly-package"
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
        raise ValueError(f"assembly PDF has no sheets: {path}")
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
        if suffix == ".pdf" and package.kind != "assembly":
            raise ValueError(f"{package.name}: part review requires one PNG sheet")
    sheet_count = _sheet_count(package)
    if package.kind == "part" and sheet_count != 1:
        raise ValueError(f"{package.name}: part review requires exactly one PNG sheet")
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


def _review_prompt(package: ReviewPackage, sheet_count: int) -> str:
    prompt = load_prompt(package.kind)
    if package.kind == "assembly":
        prompt += (
            "\n\nPACKAGE INPUT\n"
            f"This invocation includes all {sheet_count} sheet images in order. "
            "Return one verdict for the package as a whole. Compare every sheet "
            "against every other sheet before accepting SHIP.\n"
        )
    return prompt


def build_command(
    *,
    workdir: Path,
    images: Sequence[Path],
    schema: Path,
    model: str,
    effort: str,
    claude: str = "claude",
) -> list[str]:
    """Return the exact isolated ``claude -p`` argv.

    The prompt is sent on stdin rather than as a positional argument.  Claude
    gets one restricted file tool so it can read only the copied image in the
    neutral working directory; safe mode and strict empty MCP configuration
    prevent repo instructions or external context from entering the review.
    """
    if schema.parent != workdir or not images or any(image.parent != workdir for image in images):
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


def _walk(obj: Any) -> Iterable[Any]:
    yield obj
    if isinstance(obj, dict):
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk(value)


def count_tool_events(
    events: Sequence[dict[str, Any]], *, allowed_images: Sequence[Path] = ()
) -> int:
    """Count Claude events except reads of copied package images and output."""
    allowed = {path.resolve() for path in allowed_images}
    workdir = next(iter(allowed)).parent if allowed else None
    hits = 0
    for event in events:
        matched = False
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
                if raw_path and workdir is not None:
                    read_path = Path(str(raw_path))
                    if not read_path.is_absolute():
                        read_path = workdir / read_path
                    if read_path.resolve() in allowed:
                        continue
            if ("command" in node and node.get("command")) or any(
                marker in kind for marker in _TOOL_EVENT_MARKERS
            ):
                matched = True
                break
        hits += int(matched)
    return hits


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


def _extract_verdict(events: Sequence[dict[str, Any]]) -> dict[str, Any]:
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


def review_package(
    package: ReviewPackage,
    *,
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    report_dir: Path = REPORT_DIR,
    retries: int = 1,
    timeout_s: float = 1800.0,
    claude: str | None = None,
) -> Review:
    sheet_count = _validate_package(package)
    claude_exe = claude or shutil.which("claude")
    if not claude_exe:
        raise RuntimeError("claude CLI not found on PATH")
    prompt = (
        f"Use the Read tool to inspect every copied sheet-1.png through "
        f"sheet-{sheet_count}.png in order. Do not read any other file. "
        "Then perform this blind review.\n\n"
        + _review_prompt(package, sheet_count)
    )
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    source_sha = [_sha256(source) for source in package.sources]
    report_dir.mkdir(parents=True, exist_ok=True)
    events_path = report_dir / f"{package.name}.events.jsonl"

    started = time.monotonic()
    error: str | None = None
    verdict: dict[str, Any] | None = None
    events: list[dict[str, Any]] = []
    allowed_images: list[Path] = []
    attempts = 0
    for attempt in range(retries + 1):
        attempts = attempt + 1
        workdir = Path(tempfile.mkdtemp(prefix="machrev-"))
        attempt_events: list[dict[str, Any]] = []
        try:
            images = _materialize_images(package, workdir)
            allowed_images.extend(images)
            if len(images) != sheet_count:
                raise RuntimeError(
                    f"{package.name}: materialized {len(images)} sheets, "
                    f"expected {sheet_count}"
                )
            schema = workdir / "schema.json"
            shutil.copyfile(SCHEMA_FILE, schema)
            cmd = build_command(
                workdir=workdir,
                images=images,
                schema=schema,
                model=model,
                effort=effort,
                claude=claude_exe,
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
            attempt_events = _parse_events(proc.stdout)
            if proc.returncode != 0:
                raise RuntimeError(
                    f"claude exit {proc.returncode}: {proc.stderr.strip()[-800:]}"
                )
            verdict = _extract_verdict(attempt_events)
            error = None
            break
        except subprocess.TimeoutExpired as exc:
            partial_stdout = exc.stdout or ""
            if isinstance(partial_stdout, bytes):
                partial_stdout = partial_stdout.decode("utf-8", errors="replace")
            attempt_events = _parse_events(partial_stdout)
            error = f"{type(exc).__name__}: {exc}"
            verdict = None
        except Exception as exc:  # noqa: BLE001 - recorded, retried, reported
            error = f"{type(exc).__name__}: {exc}"
            verdict = None
        finally:
            events.extend(_tag_events(attempts, attempt_events))
            shutil.rmtree(workdir, ignore_errors=True)

    _write_events(events_path, events)
    tool_events = count_tool_events(events, allowed_images=allowed_images)
    review = Review(
        name=package.name,
        kind=package.kind,
        sources=[str(source) for source in package.sources],
        source_sha256=source_sha,
        verdict=verdict,
        passed=is_pass(verdict) and tool_events == 0,
        blind=tool_events == 0,
        tool_events=tool_events,
        model=model,
        effort=effort,
        prompt_sha256=prompt_sha,
        sheet_count=sheet_count,
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
    source_hashes = ", ".join(value[:12] for value in review.source_sha256)
    lines = [
        f"# {review.name} — {'PASS' if review.passed else 'FAIL'}",
        "",
        f"- kind: {review.kind}",
        f"- sheets: {review.sheet_count}",
        f"- reviewed: {review.reviewed_at} by {review.model} ({review.effort}), "
        f"{review.duration_s}s, attempts {review.attempts}",
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
        help="review an arbitrary PNG; repeat to form one assembly package",
    )
    parser.add_argument("--kind", choices=("part", "assembly"), default="part")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--effort", default=DEFAULT_EFFORT)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument(
        "--timeout", type=float, default=1800.0, help="seconds per package"
    )
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
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
        if args.kind == "part" and len(args.png) != 1:
            print("part review requires exactly one --png", file=sys.stderr)
            return 2
        packages = [_package_for_pngs(args.png, args.kind)]
    elif args.all:
        packages = all_packages()
    else:
        unknown = [n for n in args.names if n not in DRAWINGS_BY_NAME]
        if unknown or not args.names:
            print(f"unknown or missing drawing names: {unknown}", file=sys.stderr)
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

    reviews: list[Review] = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = {
            pool.submit(
                review_package,
                package,
                model=args.model,
                effort=args.effort,
                report_dir=report_dir,
                retries=args.retries,
                timeout_s=args.timeout,
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
