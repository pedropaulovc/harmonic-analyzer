r"""Shadow drawing-change gate: does a regenerated sheet need a new machinist review?

The owner ruling under evaluation: a drawing regenerated incrementally should not
need a new machinist review when its sheet did not meaningfully change. This
module only CLASSIFIES and RECORDS that question against the anchor, the last
machinist-reviewed sheet. It is shadow-only: ``build``, ``release`` and
``check:machinist_review`` never consult it, and it skips nothing.

Stages run cheapest first; the first that decides wins:

1. ``bytes``: identical PDF bytes are ``unchanged``.
2. ``render``: the repository overlay diff (``_drawing_diff``) finds no changed,
   added or removed page: ``unchanged``.
3. ``text``: a different page count, or a different multiset of printed text
   runs on any page (``_pdf_ink``), is ``meaningful``. Only title-block
   version-stamp values are ignored, as the overlay diff ignores them.
4. ``layout``: a layout-audit finding absent from the anchor's report is
   ``meaningful``. A finding is identified by kind, sheet and the annotations
   involved, never by its coordinates, which move with the annotations.
5. ``judge``: Claude Haiku, in one of two variants (``JudgeVariant``):

   - ``precheck``: the machinist review's existing minimal-change precheck
     (``machinist_review._review_session`` with ``precheck_diff``: its prompt,
     schema, AFTER-sheets-then-overlays package, sheet-inspection evidence and
     ``validate_precheck``). ``skip``/``rendering_noise`` is ``noise``;
     ``review`` and ``skip``/``assembly_single_part`` are ``meaningful``, with
     the precheck's skip kind recorded verbatim.
   - ``side_by_side``: ``prompts/machinist_review_change_gate.md`` over BEFORE
     pages, AFTER pages and overlays on one pixel grid, through the same routed
     Claude transport, sheets server and inspection evidence; the strict schema
     answers ``noise``, ``meaningful`` or ``unsure`` directly.

   A failed or invalid judge is ``unsure``, with ``judge_error`` recorded.

Stages 1-4 make no model call. ``<name>.change-gate.json`` and the
``drawing_change_gate`` span record the anchor and current SHA-256, the deciding
stage, the verdict, judge variant and model, the SHA-256 of the prompt actually
sent, diff statistics and reason.

Run from the repository root, without SolidWorks::

    uv run --frozen python cad/scripts/machinist_review_change_gate.py \
        --before ANCHOR.pdf --after CURRENT.pdf [--kind part|assembly] \
        [--before-layout ANCHOR.json --after-layout CURRENT.json] \
        [--judge-variant precheck|side_by_side | --no-judge]
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
import tempfile
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Sequence
from zipfile import ZipFile

import numpy as np
from PIL import Image

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import _telemetry  # noqa: E402
from _drawing_diff import (  # noqa: E402
    DPI,
    SCALE,
    TITLE_BLOCK_HEIGHT_PT,
    TITLE_BLOCK_WIDTH_PT,
    _VERSION,
    _document,
    create_drawing_diff,
)
from _paths import CAD_ROOT  # noqa: E402
from _pdf_ink import POINT_M, read_pdf_ink  # noqa: E402
import machinist_review as mr  # noqa: E402
import machinist_review_transport as _claude_transport  # noqa: E402

PROMPT_FILE = mr.PROMPTS_DIR / "machinist_review_change_gate.md"
SCHEMA_FILE = mr.PROMPTS_DIR / "machinist_review_change_gate_schema.json"
REPORT_DIR = CAD_ROOT / "out" / "reports" / "drawing-change-gate"
# Changed tokens quoted in the sidecar and reason; the counts are always complete.
TOKEN_EXAMPLES = 20


class ChangeVerdict(Enum):
    UNCHANGED = "unchanged"
    NOISE = "noise"
    MEANINGFUL = "meaningful"
    UNSURE = "unsure"


# The side-by-side judge may answer only these; UNCHANGED is for stages 1-2.
JUDGE_VERDICTS = (ChangeVerdict.NOISE, ChangeVerdict.MEANINGFUL, ChangeVerdict.UNSURE)


class GateStage(Enum):
    BYTES = "bytes"
    RENDER = "render"
    TEXT = "text"
    LAYOUT = "layout"
    JUDGE = "judge"


class JudgeVariant(Enum):
    PRECHECK = "precheck"
    SIDE_BY_SIDE = "side_by_side"


@dataclass(frozen=True)
class JudgeSettings:
    """The cheap judge: Claude Haiku over the review's routed Claude transport."""

    variant: JudgeVariant = JudgeVariant.SIDE_BY_SIDE
    model: str = "claude-haiku-5-5"
    effort: str = "low"
    retries: int = 1
    timeout_s: float = 600.0


@dataclass(frozen=True)
class GateResult:
    name: str
    anchor_sha256: str
    current_sha256: str
    stage: GateStage
    verdict: ChangeVerdict
    reason: str
    judge_variant: JudgeVariant | None
    judge_model: str | None
    judge_error: str | None
    prompt_sha256: str | None
    precheck_skip_kind: str | None
    diff: dict[str, Any]
    sidecar: Path


@dataclass(frozen=True)
class _Decision:
    stage: GateStage
    verdict: ChangeVerdict
    reason: str
    judge_model: str | None = None
    prompt_sha256: str | None = None
    precheck_skip_kind: str | None = None
    judge_error: str | None = None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _failed(
    judge: JudgeSettings, error: str, prompt_sha256: str | None = None
) -> _Decision:
    # Any judge failure is "unsure": doubt never becomes noise.
    return _Decision(
        GateStage.JUDGE,
        ChangeVerdict.UNSURE,
        f"Judge failed: {error}",
        judge.model,
        prompt_sha256,
        judge_error=error,
    )


def page_tokens(pdf: Path) -> tuple[list[Counter[str]], int]:
    """Each page's printed text runs, and how many version stamps were ignored.

    A run is one PDF text object (``_pdf_ink``), so "12.50" and "12.60" are
    different tokens even though they share every character but one. Only a
    whole run matching the overlay diff's version pattern inside the lower-right
    title block is ignored: every build restamps it.
    """
    pages: list[Counter[str]] = []
    ignored = 0
    for page in read_pdf_ink(pdf):
        left = page.width - TITLE_BLOCK_WIDTH_PT * POINT_M
        top = TITLE_BLOCK_HEIGHT_PT * POINT_M
        tokens: Counter[str] = Counter()
        for span in page.spans:
            if _VERSION.fullmatch(span.text) and span.xmin >= left and span.ymax <= top:
                ignored += 1
                continue
            tokens[span.text] += 1
        pages.append(tokens)
    return pages, ignored


def _layout_findings(path: Path) -> Counter[tuple[str, str, str, str]]:
    report = json.loads(path.read_text(encoding="utf-8"))
    findings = report.get("findings") if isinstance(report, dict) else None
    if not isinstance(findings, list):
        raise ValueError(f"layout-audit report has no findings list: {path}")
    return Counter(
        (
            str(f.get("kind", "")),
            str(f.get("sheet", "")),
            str(f.get("a", "")),
            str(f.get("b", "")),
        )
        for f in findings
    )


def _ink_pixels(png: bytes) -> tuple[int, int]:
    """Added (blue) and removed (red) overlay pixels; shared gray has r == b."""
    with Image.open(io.BytesIO(png)) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.int16)
    red, blue = rgb[..., 0], rgb[..., 2]
    return int(np.count_nonzero(blue > red)), int(np.count_nonzero(red > blue))


def _render_pages(pdf: Path, directory: Path, label: str) -> list[Path]:
    """Color PNGs on the overlay's pixel grid, so one crop selects one region."""
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    with _document(pdf) as document:
        for index in range(len(document)):
            page = document[index]
            try:
                bitmap = page.render(scale=SCALE, draw_annots=True)
                try:
                    with bitmap.to_pil() as image:
                        path = directory / f"{label}-{index + 1:04d}.png"
                        image.save(path, format="PNG", dpi=(DPI, DPI))
                finally:
                    bitmap.close()
            finally:
                page.close()
            paths.append(path)
    return paths


def validate_judgment(value: Any) -> dict[str, Any]:
    """The side-by-side contract: one permitted verdict and a nonempty reason."""
    if not isinstance(value, dict) or set(value) != {"verdict", "reason"}:
        raise ValueError("judge output must contain exactly verdict and reason")
    if value["verdict"] not in {verdict.value for verdict in JUDGE_VERDICTS}:
        raise ValueError("judge verdict must be noise, meaningful or unsure")
    if not isinstance(value["reason"], str) or not value["reason"].strip():
        raise ValueError("judge reason must be nonempty text")
    return value


def side_by_side_prompt(pages: int, *, layout_compared: bool) -> str:
    """The effective side-by-side prompt; its SHA-256 identifies what was sent."""
    layout = (
        "No layout-audit finding is new relative to the anchor's report."
        if layout_compared
        else "Layout-audit reports were not supplied; no layout comparison ran."
    )
    return (
        PROMPT_FILE.read_text(encoding="utf-8").rstrip() + "\n\nPACKAGE INPUT\n"
        f"Pages per drawing: {pages}.\n"
        f"Sheets 1..{pages} are BEFORE pages, {pages + 1}..{2 * pages} AFTER pages and "
        f"{2 * pages + 1}..{3 * pages} BEFORE/AFTER overlays, each in page order.\n"
        f"Call view_sheet for sheets 1..{3 * pages} in order before deciding. "
        "Use only view_sheet and crop.\n"
        "The gate verified that every page's printed text-run multiset is identical "
        "on BEFORE and AFTER, so the question is only whether geometry, annotation "
        "content or attachment changed, or only positions. "
        f"{layout}\n"
        "Return the change-gate schema verdict.\n"
    )


def _side_by_side_attempt(
    name: str, sheets: Sequence[Path], prompt: str, judge: JudgeSettings, evidence: Path
) -> dict[str, Any]:
    """One isolated routed-Claude attempt, as the review runs its judge."""
    # cleanup_state removes only homes carrying the review's owned prefix.
    home = Path(tempfile.mkdtemp(prefix="machrev-home-"))
    provenance: dict[str, Any] = {
        "private_home": str(home),
        "package": name,
        "phase": "drawing_change_gate",
        "attempt": 1,
    }
    try:
        workdir = Path(tempfile.mkdtemp(prefix="machrev-", dir=home))
        schema = workdir / "schema.json"
        schema.write_bytes(SCHEMA_FILE.read_bytes())
        mcp_config = workdir / "mcp.json"
        mcp_config.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "sheets": {
                            "command": sys.executable,
                            "args": [
                                str(mr.SHEETS_SERVER),
                                "--preserve-color",
                                *(str(path.resolve()) for path in sheets),
                            ],
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        command = mr.build_claude_invocation(
            workdir=workdir,
            mcp_config=mcp_config,
            schema=schema,
            model=judge.model,
            effort=judge.effort,
            session_id=str(uuid.uuid4()),
        )
        completed = mr._run_reviewer(
            command,
            reviewer="claude",
            input=prompt,
            timeout=judge.timeout_s,
            cwd=str(workdir),
            env=None,
            transport_provenance=provenance,
        )
        evidence.write_text(completed.stdout or "", encoding="utf-8")
        if completed.returncode != 0:
            raise RuntimeError(
                f"claude exit {completed.returncode}: {completed.stderr[-400:]}"
            )
        events = mr._parse_events(completed.stdout)
        final_route = max((event.get("route_index", 0) for event in events), default=0)
        final = [
            event for event in events if event.get("route_index", 0) == final_route
        ]
        inspected = mr.evaluate_sheet_evidence(
            final, reviewer="claude", sheet_count=len(sheets)
        )
        if inspected["tool_events"] or not inspected["inspection_proven"]:
            raise RuntimeError("judge must inspect every sheet using only sheet tools")
        return mr.extract_claude_verdict(final, validator=validate_judgment)
    finally:
        _claude_transport.cleanup_state(provenance)


def _side_by_side(
    name: str,
    before: Path,
    after: Path,
    overlays: list[Path],
    pages: int,
    layout_compared: bool,
    directory: Path,
    judge: JudgeSettings,
) -> _Decision:
    renders = directory / "renders"
    sheets = (
        *_render_pages(before, renders, "before"),
        *_render_pages(after, renders, "after"),
        *overlays,
    )
    prompt = side_by_side_prompt(pages, layout_compared=layout_compared)
    prompt_sha256 = _sha256(prompt.encode("utf-8"))
    error = ""
    for attempt in range(judge.retries + 1):
        evidence = directory / f"attempt-{attempt + 1}.events.jsonl"
        try:
            value = _side_by_side_attempt(name, sheets, prompt, judge, evidence)
        except Exception as exc:
            error = " ".join(f"{type(exc).__name__}: {exc}".split())[:500]
            _telemetry.warn(
                "drawing_change_gate.judge_attempt_failed",
                package=name,
                attempt=attempt + 1,
                error_category=type(exc).__name__,
            )
            continue
        return _Decision(
            GateStage.JUDGE,
            ChangeVerdict(value["verdict"]),
            value["reason"],
            judge.model,
            prompt_sha256,
        )
    return _failed(judge, error, prompt_sha256)


def _precheck(
    name: str,
    kind: str,
    after: Path,
    overlays: list[Path],
    overlay_diff: dict[str, Any],
    directory: Path,
    judge: JudgeSettings,
) -> _Decision:
    """Run the review's precheck exactly as ``aggregate_package`` composes it.

    The package is the AFTER sheets followed by one overlay per page, and the
    diff metadata gains ``after_sheet_count`` and ``overlay_sheets`` in the same
    order, so an identical input sends an identical precheck prompt.
    """
    snapshot = mr.ReviewPackage(name, kind, (after,))
    # The review lifecycle owns state a "review" decision preserves for its judge.
    with _claude_transport.session_lifecycle():
        try:
            after_sheet_count = mr._validate_package(snapshot)
            overlay_diff["after_sheet_count"] = after_sheet_count
            if not overlays or len(overlays) != len(overlay_diff["pages"]):
                raise RuntimeError("PDF diff did not provide an overlay for every page")
            overlay_diff["overlay_sheets"] = [
                {"sheet": after_sheet_count + index + 1, "image": member}
                for index, member in enumerate(overlay_diff["images"])
            ]
            review = mr._review_session(
                mr.ReviewPackage(name, kind, (*snapshot.sources, *overlays)),
                reviewer="claude",
                model=judge.model,
                effort=judge.effort,
                report_dir=directory,
                retries=judge.retries,
                timeout_s=judge.timeout_s,
                precheck_diff=overlay_diff,
            )
        except Exception as exc:
            _telemetry.warn(
                "drawing_change_gate.precheck_failed",
                package=name,
                error_category=type(exc).__name__,
            )
            return _failed(judge, f"{type(exc).__name__}: {exc}")
    if (
        not review.passed
        or not review.extra.get("session_id")
        or review.verdict is None
    ):
        return _failed(
            judge,
            review.error or "blind sheet/session evidence checks failed",
            review.prompt_sha256,
        )
    decision = review.verdict
    noise = (
        decision["decision"] == "skip" and decision["skip_kind"] == "rendering_noise"
    )
    return _Decision(
        GateStage.JUDGE,
        ChangeVerdict.NOISE if noise else ChangeVerdict.MEANINGFUL,
        decision["reason"],
        review.model,
        review.prompt_sha256,
        decision["skip_kind"],
    )


def _decide(
    name: str,
    kind: str,
    before: Path,
    after: Path,
    work_dir: Path,
    layouts: tuple[Path, Path] | None,
    judge: JudgeSettings | None,
    diff: dict[str, Any],
) -> _Decision:
    if before.read_bytes() == after.read_bytes():
        diff["bytes_identical"] = True
        return _Decision(
            GateStage.BYTES, ChangeVerdict.UNCHANGED, "PDF bytes are identical."
        )
    diff["bytes_identical"] = False

    # The precheck's own diff call, so its judge stage reuses it unchanged.
    precheck_dir = work_dir / "precheck"
    overlay_diff = create_drawing_diff(
        before.parent,
        after.parent,
        precheck_dir / "diff.zip",
        old_label="BEFORE",
        new_label="AFTER",
        include_unchanged=True,
    )
    counts = overlay_diff["page_counts"]
    diff["page_counts"] = dict(counts)
    diff["text_changed_pages"] = [
        page["page"] for page in overlay_diff["pages"] if page["text_changed"]
    ]
    overlays: list[Path] = []
    added_ink = removed_ink = 0
    with ZipFile(overlay_diff["asset_path"]) as archive:
        for index, member in enumerate(overlay_diff["images"]):
            png = archive.read(member)
            added, removed = _ink_pixels(png)
            added_ink += added
            removed_ink += removed
            overlay = precheck_dir / "overlays" / f"overlay-{index + 1:04d}.png"
            overlay.parent.mkdir(parents=True, exist_ok=True)
            overlay.write_bytes(png)
            overlays.append(overlay)
    diff["added_ink_pixels"] = added_ink
    diff["removed_ink_pixels"] = removed_ink
    if counts["changed"] == counts["added"] == counts["removed"] == 0:
        return _Decision(
            GateStage.RENDER,
            ChangeVerdict.UNCHANGED,
            "The overlay diff finds no changed page; only bytes or version stamps differ.",
        )

    before_tokens, before_stamps = page_tokens(before)
    after_tokens, after_stamps = page_tokens(after)
    diff["before_pages"] = len(before_tokens)
    diff["after_pages"] = len(after_tokens)
    diff["version_stamps_ignored"] = before_stamps + after_stamps
    if len(before_tokens) != len(after_tokens):
        return _Decision(
            GateStage.TEXT,
            ChangeVerdict.MEANINGFUL,
            f"Page count changed from {len(before_tokens)} to {len(after_tokens)}.",
        )
    added_tokens: Counter[str] = Counter()
    removed_tokens: Counter[str] = Counter()
    for old, new in zip(before_tokens, after_tokens):
        added_tokens += new - old
        removed_tokens += old - new
    diff["tokens_added"] = sum(added_tokens.values())
    diff["tokens_removed"] = sum(removed_tokens.values())
    diff["token_examples"] = {
        "added": sorted(added_tokens.elements())[:TOKEN_EXAMPLES],
        "removed": sorted(removed_tokens.elements())[:TOKEN_EXAMPLES],
    }
    if added_tokens or removed_tokens:
        return _Decision(
            GateStage.TEXT,
            ChangeVerdict.MEANINGFUL,
            f"Printed text changed: removed {diff['token_examples']['removed']}, "
            f"added {diff['token_examples']['added']}.",
        )

    diff["layout_compared"] = layouts is not None
    if layouts is not None:
        new = _layout_findings(layouts[1]) - _layout_findings(layouts[0])
        diff["layout_new_findings"] = [
            {"kind": kind_, "sheet": sheet, "a": a, "b": b}
            for kind_, sheet, a, b in sorted(new.elements())
        ]
        if new:
            kinds = sorted({finding[0] for finding in new})
            return _Decision(
                GateStage.LAYOUT,
                ChangeVerdict.MEANINGFUL,
                f"{sum(new.values())} layout-audit finding(s) absent from the anchor: {kinds}.",
            )

    if judge is None:
        return _Decision(
            GateStage.JUDGE,
            ChangeVerdict.UNSURE,
            "Stages 1-4 did not decide and no judge was consulted.",
        )
    if judge.variant is JudgeVariant.SIDE_BY_SIDE:
        return _side_by_side(
            name,
            before,
            after,
            overlays,
            len(after_tokens),
            layouts is not None,
            work_dir / "side_by_side",
            judge,
        )
    return _precheck(name, kind, after, overlays, overlay_diff, precheck_dir, judge)


def run_gate(
    before: Path,
    after: Path,
    *,
    name: str,
    kind: str,
    out_dir: Path = REPORT_DIR,
    layouts: tuple[Path, Path] | None = None,
    judge: JudgeSettings | None = None,
) -> GateResult:
    """Classify ``after`` against the reviewed anchor ``before`` and write the sidecar.

    ``name`` and ``kind`` select the precheck's owner exceptions and permitted
    skip kinds, as they do for ``machinist_review.py``.
    """
    work_dir = out_dir / f"{name}.change-gate"
    variant = judge.variant if judge is not None else None
    with _telemetry.span("drawing_change_gate", package=name, kind=kind) as span:
        # A fresh evidence directory: stale PDFs would join the overlay diff.
        if work_dir.is_dir():
            shutil.rmtree(work_dir)
        frozen = []
        for label, source in (("before", before), ("after", after)):
            target = work_dir / "sources" / label / "0001.pdf"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            frozen.append(target)
        anchor, current = frozen
        anchor_sha256 = _sha256(anchor.read_bytes())
        current_sha256 = _sha256(current.read_bytes())
        diff: dict[str, Any] = {}
        decision = _decide(name, kind, anchor, current, work_dir, layouts, judge, diff)
        sidecar = out_dir / f"{name}.change-gate.json"
        record = {
            "schema": 1,
            "shadow": True,
            "name": name,
            "kind": kind,
            "anchor_pdf": str(before.resolve()),
            "current_pdf": str(after.resolve()),
            "anchor_sha256": anchor_sha256,
            "current_sha256": current_sha256,
            "anchor_layout_sha256": _sha256(layouts[0].read_bytes())
            if layouts
            else None,
            "current_layout_sha256": _sha256(layouts[1].read_bytes())
            if layouts
            else None,
            "stage": decision.stage.value,
            "verdict": decision.verdict.value,
            "judge_variant": variant.value if variant is not None else None,
            "judge_model": decision.judge_model,
            "judge_error": decision.judge_error,
            "prompt_sha256": decision.prompt_sha256,
            "precheck_skip_kind": decision.precheck_skip_kind,
            "diff": diff,
            "reason": decision.reason,
            "evidence_dir": str(work_dir.resolve()),
            "decided_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        sidecar.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        attributes = {
            "anchor_sha256": anchor_sha256,
            "current_sha256": current_sha256,
            "stage": decision.stage.value,
            "verdict": decision.verdict.value,
            "judge_variant": record["judge_variant"],
            "judge_model": decision.judge_model,
            "judge_error": decision.judge_error,
            "prompt_sha256": decision.prompt_sha256,
            "precheck_skip_kind": decision.precheck_skip_kind,
            "reason": decision.reason,
            **{
                f"diff.{key}": value
                for key, value in diff.items()
                if isinstance(value, (bool, int, str))
            },
        }
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, value)
        _telemetry.info(
            "drawing_change_gate.decided",
            package=name,
            stage=decision.stage.value,
            verdict=decision.verdict.value,
            sidecar=str(sidecar),
        )
    return GateResult(
        name,
        anchor_sha256,
        current_sha256,
        decision.stage,
        decision.verdict,
        decision.reason,
        variant,
        decision.judge_model,
        decision.judge_error,
        decision.prompt_sha256,
        decision.precheck_skip_kind,
        diff,
        sidecar,
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--before",
        type=Path,
        required=True,
        help="anchor PDF: the last machinist-reviewed sheet",
    )
    parser.add_argument(
        "--after", type=Path, required=True, help="current regenerated PDF"
    )
    parser.add_argument("--before-layout", type=Path, help="anchor layout-audit JSON")
    parser.add_argument("--after-layout", type=Path, help="current layout-audit JSON")
    parser.add_argument(
        "--name",
        help="package name for outputs and owner exceptions (default: --after stem)",
    )
    parser.add_argument(
        "--kind",
        choices=sorted(mr.PROMPT_FILES),
        help="package kind (default: the registry's kind for a registered --name)",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=REPORT_DIR, help="sidecar directory"
    )
    judging = parser.add_mutually_exclusive_group()
    judging.add_argument(
        "--judge-variant",
        choices=[variant.value for variant in JudgeVariant],
        default=JudgeVariant.SIDE_BY_SIDE.value,
        help="judge used when stages 1-4 do not decide (default: side_by_side)",
    )
    judging.add_argument(
        "--no-judge",
        action="store_true",
        help="run stages 1-4 only; a sheet they leave undecided is recorded unsure",
    )
    args = parser.parse_args(argv)
    if (args.before_layout is None) != (args.after_layout is None):
        parser.error("--before-layout and --after-layout must be given together")
    args.name = args.name or args.after.stem
    if args.kind is None:
        spec = mr.DRAWINGS_BY_NAME.get(args.name)
        if spec is None:
            parser.error(
                f"--kind is required: {args.name!r} is not a registered drawing"
            )
        args.kind = spec.source_kind
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    layouts = (args.before_layout, args.after_layout) if args.before_layout else None
    judge = None if args.no_judge else JudgeSettings(JudgeVariant(args.judge_variant))
    run_gate(
        args.before,
        args.after,
        name=args.name,
        kind=args.kind,
        out_dir=args.out_dir,
        layouts=layouts,
        judge=judge,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
