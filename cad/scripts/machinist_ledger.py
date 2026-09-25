r"""Durable record of which drawing sheets a machinist review accepted.

``machinist_review.py`` writes its verdicts under the gitignored
``cad/out/reports/machinist-review/`` of whichever worktree ran it, keyed by
the reviewed PDF's sha256.  Those bytes churn on every render (timestamps, the
revision stamped into the title block), so neither the file nor the hash can
say, at integration or release time, whether the sheet now shipping is the
sheet a reviewer passed.  This module is that link.

* **Ledger** -- ``cad/reviews/machinist-ledger.json`` (tracked), plus the exact
  PDF each recorded review saw, content-addressed as
  ``cad/reviews/sheets/<sha256>.pdf``.  One entry per registry drawing and
  slot: ``cross_family`` holds the last accepted review by the other model
  family; ``last_resort`` holds a same-family review, which counts only under
  the policy's last-resort rule (``cad/docs/drawing-simplicity-policy.md``,
  "The gate"): a recorded quota refusal by the cross-family reviewer, captured
  by ``machinist_review.py``, within 24 h before the review, and the tier rule
  (an Opus/Sol author needs a Fable/Astra reviewer; a Fable/Astra author needs
  Fable/Astra at high effort) met by the author model named in the draw
  script's last commit trailer.  Anything else is recorded with ``counts:
  false`` and the reason, and is never accepted.
* **Accepted** -- a ``SHIP``, or ``accepted_with_rulings``: a verdict whose
  every blocker, over-specification and clarity finding is rebutted by a cited
  user ruling (ruling id plus the file and line recording it).  The rebuttal
  and the cited line are kept in the entry.  An unrebutted finding keeps the
  drawing failing.
* **Sheet content** -- each PDF page rendered at the review's 300 dpi,
  grayscale, thresholded to 1-bit ink, plus the page's text layer as spans
  (string and position).  The per-build revision text -- the REV cell value
  and the ``BUILD <rev>`` token -- is blanked in the ink and masked in the text.
* **Match** -- a current sheet matches a reviewed one when (a) the sha256 of
  the masked ink is equal, or (b) the text layer is equal -- every span's
  string, and its position within ``TEXT_POSITION_TOLERANCE_MM`` -- AND every
  ink pixel of each sheet lies within ``MATCH_TOLERANCE_PX`` of ink in the
  other.  Re-rendering an unchanged drawing moves antialiased edge pixels and
  whole views by 1-2 px (48 of 1161 surveyed render pairs), which the digest
  reads as a change; the text layer of those pairs was identical, positions
  within 0.06 mm.  Text is compared exactly because a dropped decimal point or
  a 3/8 swap on small text can hide inside the 2 px ink tolerance.
* **Drift check** -- ``check`` lists every drawing whose current sheets match
  no accepted, counting entry, with the command that clears each, and writes
  the leftover pixels (red) and the text difference of each changed sheet
  under ``--report-dir``.  ``release`` depends on it as ``check:machinist``
  (``dodo.py``), which reads the rendered ``cad/out/pdf`` sheets as file_deps.

No build task reads the ledger, so recording a review never re-keys a build.

Usage (SolidWorks-free)::

    uv run cad/scripts/machinist_ledger.py check                 # every registry drawing
    uv run cad/scripts/machinist_ledger.py check crank_pinion_pin
    uv run cad/scripts/machinist_ledger.py ingest <verdict.json> --author-family gpt
    uv run cad/scripts/machinist_ledger.py ingest <fix.json> --author-family claude \
        --rebuttals <rebuttals.json>
    uv run cad/scripts/machinist_ledger.py fingerprint <drawing.pdf>

A rebuttals file::

    {"drawing": "cone_pivot_post",
     "rebuttals": [{"category": "over_specification", "index": 0,
                    "where": "<the finding's where, verbatim>",
                    "ruling": "U31",
                    "citation": "C:/src/dt-logs/handoffs/DT-Assembly-cc-20260923.md:318",
                    "rebuttal": "the user ruled this band; the note carries it"}]}
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import threading
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from importlib.metadata import version
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from _drawing_registry import CAD_ROOT, DRAWINGS, DRAWINGS_BY_NAME  # noqa: E402

REPO_ROOT = CAD_ROOT.parent
LEDGER_PATH = CAD_ROOT / "reviews" / "machinist-ledger.json"
REPORT_DIR = CAD_ROOT / "out" / "reports" / "machinist-ledger"
LEDGER_VERSION = 1

FINGERPRINT_DPI = 300
INK_THRESHOLD = 128  # grayscale value below which a pixel is ink
MASK_PAD_PT = 2.0  # anti-aliasing margin around a masked text run
MATCH_TOLERANCE_PX = 2  # 0.17 mm at 300 dpi
# A tolerance, not grid rounding, so render wobble never flips a span across a
# grid line: twice the largest wobble measured between noise-only renders
# (0.058 mm over 48 pairs), well under a 0.3 mm move.
TEXT_POSITION_TOLERANCE_MM = 0.12
FINGERPRINT_ALGORITHM = "sheet-1bit-sha256-v1"
MM_PER_PT = 25.4 / 72.0

# Text stamped per build rather than per design: the REV cell value (a text line
# of its own) and the "BUILD <rev>" token under DO NOT SCALE DRAWING, which the
# PDF text layer may join onto that line.  Older builds suffix "-b<number>".  A
# revision-looking token anywhere else (e.g. inside a note) stays in the sheet.
_REVISION = r"(?:v\d+|DEV)(?:-b\d+)?"
_REV_CELL = re.compile(rf"^{_REVISION}$")
_BUILD_STAMP = re.compile(rf"\bBUILD\s+{_REVISION}\b")
_MASK_TOKEN = "#"

REVIEWER_FAMILIES = {"claude": "claude", "codex": "gpt"}
AUTHOR_FAMILIES = ("claude", "gpt", "mimo")
FINDING_KEYS = ("blockers", "over_specification", "clarity", "minor")
GATING_KEYS = ("blockers", "over_specification", "clarity")

CROSS_FAMILY = "cross_family"
LAST_RESORT = "last_resort"
SHIP = "ship"
ACCEPTED_WITH_RULINGS = "accepted_with_rulings"

# Model-name tokens -> family, and the user's standing last-resort tiers: work
# by a workhorse model (Opus, Sol) is reviewed by a top model (Fable, Astra);
# work by a top model is reviewed by a top model at high reasoning effort.
_MODEL_FAMILIES = {
    "claude": "claude", "opus": "claude", "sonnet": "claude", "haiku": "claude",
    "fable": "claude", "gpt": "gpt", "codex": "gpt", "sol": "gpt", "astra": "gpt",
    "luna": "gpt", "mimo": "mimo",
}  # fmt: skip
_TIERS = {"opus": "workhorse", "sol": "workhorse", "fable": "top", "astra": "top"}
_HIGH_EFFORTS = ("high", "xhigh", "max")
# What the reviewer CLIs print when an account is out of quota.
_QUOTA_REFUSAL = re.compile(
    r"hit your usage limit|usage[_ ]limit[_ ]reached", re.IGNORECASE
)
QUOTA_REFUSAL_MAX_AGE = timedelta(hours=24)
_TRAILER = re.compile(
    r"^co-authored-by:\s*([^<\n]+?)\s*(?:<[^>\n]*>)?\s*$", re.I | re.M
)
_CITATION = re.compile(r"^(?P<path>.+?)(?::(?P<line>\d+))?$")
_CITATION_WINDOW = 3  # lines either side of a cited line that may hold the ruling id

# PDFium's native API is process-global and not thread-safe.
_PDFIUM_LOCK = threading.Lock()


# --- sheet content -----------------------------------------------------------------


@dataclass(frozen=True)
class Span:
    """One text line of a sheet; no position when it carries masked text."""

    text: str
    left_mm: float | None
    bottom_mm: float | None


@dataclass(frozen=True)
class Sheet:
    ink: Any  # bool array, True = ink
    text: tuple[Span, ...]


def _volatile_spans(text: str) -> list[tuple[int, int]]:
    """(start, length) character spans of the per-build revision text."""
    spans = [
        (match.start(), len(match.group())) for match in _BUILD_STAMP.finditer(text)
    ]
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if _REV_CELL.match(stripped):
            spans.append((offset + line.index(stripped), len(stripped)))
        offset += len(line)
    return spans


def _page_text(
    textpage: Any,
) -> tuple[list[Span], list[tuple[float, float, float, float]]]:
    """The page's text spans and the PDF-space boxes of its revision text."""
    text = textpage.get_text_range()
    volatile = _volatile_spans(text)
    boxes: list[tuple[float, float, float, float]] = []
    for start, length in volatile:
        for index in range(textpage.count_rects(start, length)):
            boxes.append(textpage.get_rect(index))
    spans: list[Span] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        start = offset
        offset += len(line)
        body = line.rstrip("\r\n")
        if not body.strip():
            continue
        hits = [(s, n) for s, n in volatile if start <= s < start + len(body)]
        shown = body
        for s, n in sorted(hits, reverse=True):
            shown = shown[: s - start] + _MASK_TOKEN + shown[s - start + n :]
        lead = len(body) - len(body.lstrip())
        if hits or not textpage.count_rects(start + lead, len(body.strip())):
            spans.append(Span(shown.strip(), None, None))
            continue
        left, bottom, _, _ = textpage.get_rect(0)
        spans.append(Span(shown.strip(), left * MM_PER_PT, bottom * MM_PER_PT))
    return spans, boxes


def read_sheets(pdf: Path, *, dpi: int = FINGERPRINT_DPI) -> list[Sheet]:
    """Every page of ``pdf`` as masked 1-bit ink plus its masked text layer."""
    import numpy as np
    import pypdfium2 as pdfium

    scale = dpi / 72.0
    sheets = []
    with _PDFIUM_LOCK:
        document = pdfium.PdfDocument(str(pdf))
        try:
            for page_index in range(len(document)):
                page = document[page_index]
                try:
                    if page.get_rotation() % 360:
                        raise ValueError(f"{pdf}: page {page_index + 1} is rotated")
                    _, page_height = page.get_size()
                    textpage = page.get_textpage()
                    try:
                        spans, boxes = _page_text(textpage)
                    finally:
                        textpage.close()
                    gray = np.array(
                        page.render(scale=scale, grayscale=True).to_pil().convert("L")
                    )
                finally:
                    page.close()
                height, width = gray.shape
                for left, bottom, right, top in boxes:
                    x0 = max(0, int((left - MASK_PAD_PT) * scale))
                    x1 = min(width, int((right + MASK_PAD_PT) * scale) + 1)
                    y0 = max(0, int((page_height - top - MASK_PAD_PT) * scale))
                    y1 = min(
                        height, int((page_height - bottom + MASK_PAD_PT) * scale) + 1
                    )
                    gray[y0:y1, x0:x1] = 255
                sheets.append(Sheet(gray < INK_THRESHOLD, tuple(spans)))
        finally:
            document.close()
    if not sheets:
        raise ValueError(f"PDF has no sheets: {pdf}")
    return sheets


def sheet_digest(ink: Any) -> str:
    """sha256 of one sheet's packed 1-bit ink, bound to its pixel size."""
    import numpy as np

    height, width = ink.shape
    header = f"{FINGERPRINT_ALGORITHM} {width}x{height}\n".encode()
    return hashlib.sha256(header + np.packbits(ink, axis=1).tobytes()).hexdigest()


def fingerprint(pdf: Path) -> list[str]:
    """Per-sheet content digests of a drawing PDF, in page order."""
    return [sheet_digest(sheet.ink) for sheet in read_sheets(pdf)]


def _dilate(ink: Any, radius: int) -> Any:
    """Square (Chebyshev) dilation, separable into a row pass and a column pass."""
    out = ink.copy()
    for axis in (0, 1):
        source = out.copy()
        for step in range(1, radius + 1):
            if axis == 0:
                out[step:, :] |= source[:-step, :]
                out[:-step, :] |= source[step:, :]
            else:
                out[:, step:] |= source[:, :-step]
                out[:, :-step] |= source[:, step:]
    return out


def residual_mask(
    reference: Any, current: Any, *, radius: int = MATCH_TOLERANCE_PX
) -> Any:
    """Ink of either sheet farther than ``radius`` px from ink in the other."""
    lost = reference & ~_dilate(current, radius)
    added = current & ~_dilate(reference, radius)
    return lost | added


def residual(reference: Any, current: Any, *, radius: int = MATCH_TOLERANCE_PX) -> int:
    """Leftover ink pixels (see ``residual_mask``); -1 when the sheet sizes differ."""
    if reference.shape != current.shape:
        return -1
    return int(residual_mask(reference, current, radius=radius).sum())


def _where(span: Span) -> str:
    if span.left_mm is None:
        return ""
    return f" at ({span.left_mm:.2f}, {span.bottom_mm:.2f}) mm"


def text_difference(
    reference: Sequence[Span],
    current: Sequence[Span],
    *,
    tolerance_mm: float = TEXT_POSITION_TOLERANCE_MM,
) -> list[str]:
    """Readable text-layer changes: removed, added and moved spans (empty = equal)."""
    lines: list[str] = []
    before = Counter(span.text for span in reference)
    after = Counter(span.text for span in current)
    for text in sorted(before | after):
        old = sorted(
            (s for s in reference if s.text == text),
            key=lambda s: (s.left_mm or 0, s.bottom_mm or 0),
        )
        new = sorted(
            (s for s in current if s.text == text),
            key=lambda s: (s.left_mm or 0, s.bottom_mm or 0),
        )
        if len(old) != len(new):
            lines += [f"- {text!r}{_where(span)}" for span in old]
            lines += [f"+ {text!r}{_where(span)}" for span in new]
            continue
        for was, now in zip(old, new):
            if was.left_mm is None or now.left_mm is None:
                continue
            dx, dy = now.left_mm - was.left_mm, now.bottom_mm - was.bottom_mm
            if max(abs(dx), abs(dy)) > tolerance_mm:
                lines.append(f"~ {text!r} moved ({dx:+.2f}, {dy:+.2f}) mm{_where(now)}")
    return lines


@dataclass
class SheetDifference:
    index: int  # 1-based sheet number
    pixels: int  # leftover ink pixels; -1 when the sheet size changed
    text: list[str]
    mask: Any = field(repr=False, default=None)

    def summary(self) -> str:
        if self.pixels < 0:
            return f"{self.index} (sheet size changed)"
        parts = [f"{self.pixels} px"]
        if self.text:
            parts.append(
                f"{len(self.text)} text change{'s' if len(self.text) != 1 else ''}"
            )
        return f"{self.index} ({', '.join(parts)})"


def sheet_difference(
    reference: Sheet, current: Sheet, *, index: int
) -> SheetDifference | None:
    """None when ``current`` matches ``reference`` under rule (a) or (b)."""
    if sheet_digest(reference.ink) == sheet_digest(current.ink):
        return None
    text = text_difference(reference.text, current.text)
    if reference.ink.shape != current.ink.shape:
        return SheetDifference(index, -1, text)
    mask = residual_mask(reference.ink, current.ink)
    pixels = int(mask.sum())
    if not pixels and not text:
        return None
    return SheetDifference(index, pixels, text, mask)


def write_diff(
    name: str,
    differences: Sequence[SheetDifference],
    current: Sequence[Sheet],
    report_dir: Path,
) -> list[Path]:
    """Leftover pixels in red over the current sheet, plus the text difference."""
    import numpy as np
    from PIL import Image

    report_dir.mkdir(parents=True, exist_ok=True)
    written = []
    text_lines = []
    for difference in differences:
        text_lines.append(f"sheet {difference.summary()}")
        text_lines += [f"  {line}" for line in difference.text]
        if difference.mask is None:
            continue
        ink = current[difference.index - 1].ink
        image = np.full((*ink.shape, 3), 255, dtype=np.uint8)
        image[ink] = (170, 170, 170)
        image[difference.mask] = (220, 0, 0)
        path = report_dir / f"{name}-sheet{difference.index}-diff.png"
        Image.fromarray(image).save(path, optimize=True)
        written.append(path)
    path = report_dir / f"{name}-diff.txt"
    path.write_text("\n".join(text_lines) + "\n", encoding="utf-8", newline="\n")
    written.append(path)
    return written


# --- ledger ------------------------------------------------------------------------


def sheets_dir(ledger_path: Path) -> Path:
    return ledger_path.parent / "sheets"


def empty_ledger() -> dict[str, Any]:
    return {
        "version": LEDGER_VERSION,
        "fingerprint": {
            "algorithm": FINGERPRINT_ALGORITHM,
            "dpi": FINGERPRINT_DPI,
            "ink_threshold": INK_THRESHOLD,
            "masked": [_REV_CELL.pattern, _BUILD_STAMP.pattern],
            "match_tolerance_px": MATCH_TOLERANCE_PX,
            "text_position_tolerance_mm": TEXT_POSITION_TOLERANCE_MM,
        },
        "drawings": {},
    }


def load_ledger(path: Path = LEDGER_PATH) -> dict[str, Any]:
    if not path.is_file():
        return empty_ledger()
    ledger = json.loads(path.read_text(encoding="utf-8"))
    if ledger.get("version") != LEDGER_VERSION:
        raise ValueError(
            f"{path}: ledger version {ledger.get('version')!r} != {LEDGER_VERSION}"
        )
    if ledger.get("fingerprint") != empty_ledger()["fingerprint"]:
        raise ValueError(
            f"{path}: recorded with fingerprint settings {ledger.get('fingerprint')}, "
            f"this checkout uses {empty_ledger()['fingerprint']}"
        )
    return ledger


def save_ledger(ledger: dict[str, Any], path: Path = LEDGER_PATH) -> None:
    """Write the ledger and drop reviewed PDFs no entry points at any more."""
    ledger["drawings"] = dict(sorted(ledger["drawings"].items()))
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(ledger, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    referenced = {
        entry["pdf"]
        for slots in ledger["drawings"].values()
        for entry in slots.values()
    }
    directory = sheets_dir(path)
    if directory.is_dir():
        for stored in directory.glob("*.pdf"):
            if stored.stem not in referenced:
                stored.unlink()


def reviewer_family(reviewer: str) -> str:
    try:
        return REVIEWER_FAMILIES[reviewer]
    except KeyError:
        raise ValueError(
            f"unknown reviewer {reviewer!r}; expected one of {sorted(REVIEWER_FAMILIES)}"
        ) from None


def review_slot(reviewer: str, author_family: str) -> str:
    """``cross_family`` when the reviewer's family differs from the author's."""
    if author_family not in AUTHOR_FAMILIES:
        raise ValueError(
            f"unknown author family {author_family!r}; expected {AUTHOR_FAMILIES}"
        )
    if reviewer_family(reviewer) == author_family:
        return LAST_RESORT
    return CROSS_FAMILY


def _git(*args: str, repo: Path = REPO_ROOT) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def git_state() -> dict[str, Any]:
    """HEAD and dirtiness of the checkout recording a review (provenance only)."""
    status = _git("status", "--porcelain", "--untracked-files=no")
    return {
        "head": _git("rev-parse", "HEAD"),
        "dirty": None if status is None else bool(status),
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def model_key(model: str) -> str:
    """``Claude Opus 5.5`` and ``claude-opus-5-5`` -> ``claude-opus-5-5``."""
    return re.sub(r"[\s._]+", "-", model.strip().lower())


def model_family(model: str) -> str | None:
    tokens = model_key(model).split("-")
    return next(
        (_MODEL_FAMILIES[token] for token in tokens if token in _MODEL_FAMILIES), None
    )


def model_tier(model: str) -> str | None:
    tokens = model_key(model).split("-")
    return next((_TIERS[token] for token in tokens if token in _TIERS), None)


def last_resort_tier_problem(
    author_model: str, reviewer_model: str, effort: str
) -> str | None:
    """Why a same-family reviewer misses the last-resort tier rule, or None."""
    author, reviewer = model_tier(author_model), model_tier(reviewer_model)
    if author is None:
        return f"author model {author_model!r} has no last-resort tier (Opus, Sol, Fable, Astra)"
    if reviewer != "top":
        return f"reviewer {reviewer_model!r} is not a Fable/Astra model"
    if author == "top" and effort not in _HIGH_EFFORTS:
        return (
            f"a {author_model} author needs the reviewer at high effort, not {effort!r}"
        )
    return None


# --- author ------------------------------------------------------------------------


@dataclass(frozen=True)
class Author:
    model: str | None  # from the commit's Co-Authored-By trailer; None when it has none
    commit: str
    script: str


def script_authors(
    paths: Sequence[Path], *, repo: Path = REPO_ROOT
) -> dict[Path, Author | ValueError]:
    """The model named by the last commit that touched each path.

    Three git calls for any number of paths: a drift check that lists every
    unreviewed drawing must not spawn git per drawing.
    """
    rels = {
        path: path.resolve().relative_to(repo.resolve()).as_posix() for path in paths
    }
    status = _git("status", "--porcelain", "--", *rels.values(), repo=repo) or ""
    dirty = {line.split(maxsplit=1)[-1] for line in status.splitlines()}  # "XY path"
    log = (
        _git("log", "--format=%x00%H", "--name-only", "--", *rels.values(), repo=repo)
        or ""
    )
    last: dict[str, str] = {}
    for block in log.split("\x00")[1:]:
        commit, *files = block.strip().splitlines()
        for name in files:
            last.setdefault(name.strip(), commit)
    bodies: dict[str, str] = {}
    if last:
        shown = _git(
            "log", "--no-walk", "--format=%x00%H%n%B", *set(last.values()), repo=repo
        )
        for block in (shown or "").split("\x00")[1:]:
            commit, _, body = block.partition("\n")
            bodies[commit.strip()] = body
    authors: dict[Path, Author | ValueError] = {}
    for path, rel in rels.items():
        commit = last.get(rel)
        if rel in dirty:
            authors[path] = ValueError(
                f"{rel} has uncommitted changes; commit it so its author is on record"
            )
        elif commit is None:
            authors[path] = ValueError(
                f"{rel} has no commit; its author is not on record"
            )
        else:
            trailers = _TRAILER.findall(bodies.get(commit, ""))
            models = sorted({model_key(m) for m in trailers if model_family(m)})
            if len(models) > 1:
                authors[path] = ValueError(
                    f"{rel}: commit {commit[:12]} names several models {models}"
                )
            else:
                authors[path] = Author(models[0] if models else None, commit, rel)
    return authors


def script_author(path: Path, *, repo: Path = REPO_ROOT) -> Author:
    """The model named by the last commit that touched ``path``."""
    author = script_authors([path], repo=repo)[path]
    if isinstance(author, ValueError):
        raise author
    return author


def draw_script_author(name: str) -> Author:
    return script_author(SCRIPTS_DIR / DRAWINGS_BY_NAME[name].script_name)


def draw_script_authors(names: Sequence[str]) -> dict[str, Author | ValueError]:
    paths = {name: SCRIPTS_DIR / DRAWINGS_BY_NAME[name].script_name for name in names}
    found = script_authors(list(paths.values()))
    return {name: found[path] for name, path in paths.items()}


def resolve_author(
    name: str, author_family: str, author_model: str | None
) -> dict[str, Any]:
    """The author on record: the trailer's model, cross-checked against the claims."""
    author = draw_script_author(name)
    record = {"family": author_family, "commit": author.commit, "script": author.script}
    model = author.model
    source = "trailer"
    if model is None:
        model = None if author_model is None else model_key(author_model)
        source = "claimed"
    elif author_model is not None and model_key(author_model) != model:
        raise ValueError(
            f"{name}: --author-model {author_model} disagrees with {model} "
            f"in the trailer of {author.commit[:12]}"
        )
    if model is not None and model_family(model) != author_family:
        raise ValueError(
            f"{name}: author model {model} is not in the {author_family} family"
        )
    return {**record, "model": model, "model_source": source}


# --- quota refusal -----------------------------------------------------------------


def quota_evidence(data: dict[str, Any], report: Path) -> dict[str, Any] | None:
    """A usage-limit refusal in a machinist_review record, or None.

    Only what the tool itself wrote is searched: the record's error, its event
    stream and each attempt's error and captured stdout/stderr.
    """
    attempts = (data.get("extra") or {}).get("evidence", {}).get("attempts", [])
    sources: list[tuple[Path, str, dict[str, Any] | None]] = [
        (report, data.get("error") or "", None)
    ]
    if data.get("events_file") and Path(data["events_file"]).is_file():
        events = Path(data["events_file"])
        sources.append(
            (events, events.read_text(encoding="utf-8", errors="replace"), None)
        )
    for attempt in attempts:
        sources.append((report, attempt.get("error") or "", attempt))
        for key in ("stdout_file", "stderr_file"):
            if attempt.get(key) and Path(attempt[key]).is_file():
                output = Path(attempt[key])
                sources.append(
                    (
                        output,
                        output.read_text(encoding="utf-8", errors="replace"),
                        attempt,
                    )
                )
    for source, text, attempt in sources:
        match = _QUOTA_REFUSAL.search(text)
        if match is None:
            continue
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        attempt = attempt or (attempts[0] if attempts else {})
        return {
            "report": report.resolve().as_posix(),
            "evidence_file": source.resolve().as_posix(),
            "reviewer": data["reviewer"],
            "model": data["model"],
            "effort": data["effort"],
            "command": attempt.get("command"),
            "refused_at": data["reviewed_at"],
            "source_sha256": (data.get("source_sha256") or [None])[0],
            "message": text[line_start : line_end if line_end >= 0 else None].strip()[
                :300
            ],
        }
    return None


def quota_refusal(report: Path, *, name: str, author_family: str) -> dict[str, Any]:
    """Evidence that the cross-family reviewer refused ``name`` on quota."""
    data = json.loads(report.read_text(encoding="utf-8"))
    if data.get("name") != name:
        raise ValueError(f"{report}: refusal is for {data.get('name')!r}, not {name!r}")
    if reviewer_family(data["reviewer"]) == author_family:
        raise ValueError(f"{report}: refusal must come from the cross-family reviewer")
    if data.get("verdict") is not None:
        raise ValueError(
            f"{report}: that review returned a verdict; it was not refused"
        )
    evidence = quota_evidence(data, report)
    if evidence is None:
        raise ValueError(
            f"{report}: no usage-limit refusal in its error, events or attempt output"
        )
    return evidence


def refusal_problem(
    refusal: dict[str, Any], *, pdf_sha256: str, reviewed_at: str
) -> str | None:
    """Why a refusal does not license a same-family review of this PDF at this time."""
    if refusal.get("source_sha256") != pdf_sha256:
        return (
            f"the quota refusal was for a different PDF ({str(refusal.get('source_sha256'))[:12]}), "
            f"not {pdf_sha256[:12]}"
        )
    age = datetime.fromisoformat(reviewed_at) - datetime.fromisoformat(
        refusal["refused_at"]
    )
    if age < timedelta(0) or age > QUOTA_REFUSAL_MAX_AGE:
        hours = QUOTA_REFUSAL_MAX_AGE / timedelta(hours=1)
        return (
            f"the quota refusal at {refusal['refused_at']} is "
            f"{age / timedelta(hours=1):.1f} h before the review, not within {hours:g} h"
        )
    return None


# --- rulings -----------------------------------------------------------------------


def load_rebuttals(path: Path, *, name: str) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("drawing") != name:
        raise ValueError(
            f"{path}: rebuttals are for {data.get('drawing')!r}, not {name!r}"
        )
    rebuttals = data.get("rebuttals")
    if not isinstance(rebuttals, list) or not rebuttals:
        raise ValueError(f"{path}: no rebuttals listed")
    return rebuttals


def _cited_excerpt(ruling: str, citation: str) -> str:
    """The cited line(s) holding ``ruling``; raises when the citation does not."""
    match = _CITATION.match(citation.strip())
    path = Path(match["path"])
    path = path if path.is_absolute() else REPO_ROOT / path
    if not path.is_file():
        raise ValueError(f"citation {citation!r}: no such file")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(ruling)}(?![0-9])")
    if match["line"] is None:
        found = [line for line in lines if pattern.search(line)]
        if not found:
            raise ValueError(f"citation {citation!r} does not mention {ruling}")
        return found[0].strip()[:300]
    number = int(match["line"])
    if not 1 <= number <= len(lines):
        raise ValueError(f"citation {citation!r}: the file has {len(lines)} lines")
    window = lines[max(0, number - 1 - _CITATION_WINDOW) : number + _CITATION_WINDOW]
    if not any(pattern.search(line) for line in window):
        raise ValueError(
            f"citation {citation!r} does not mention {ruling} near that line"
        )
    return lines[number - 1].strip()[:300]


def apply_rebuttals(
    verdict: dict[str, Any], rebuttals: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Pair every gating finding with its cited ruling; raises on any gap."""
    findings = {
        (key, index): finding
        for key in GATING_KEYS
        for index, finding in enumerate(verdict.get(key) or [])
    }
    if not findings:
        raise ValueError(
            "the verdict has no blocker, over-specification or clarity finding to rebut"
        )
    records = {}
    for rebuttal in rebuttals:
        ref = (rebuttal.get("category"), rebuttal.get("index"))
        finding = findings.get(ref)
        if finding is None:
            raise ValueError(f"rebuttal {ref} names no finding of this verdict")
        if ref in records:
            raise ValueError(f"finding {ref} is rebutted twice")
        if rebuttal.get("where") != finding["where"]:
            raise ValueError(
                f"rebuttal {ref}: where {rebuttal.get('where')!r} != {finding['where']!r}"
            )
        ruling = str(rebuttal.get("ruling") or "").strip()
        text = str(rebuttal.get("rebuttal") or "").strip()
        citation = str(rebuttal.get("citation") or "").strip()
        if not ruling or not text or not citation:
            raise ValueError(
                f"rebuttal {ref} needs a ruling id, a citation and its text"
            )
        records[ref] = {
            "category": ref[0],
            "index": ref[1],
            "where": finding["where"],
            "issue": finding["issue"],
            "ruling": ruling,
            "citation": citation,
            "cited": _cited_excerpt(ruling, citation),
            "rebuttal": text,
        }
    missing = [
        f"{key}[{index}] {findings[key, index]['where']}"
        for key, index in findings
        if (key, index) not in records
    ]
    if missing:
        raise ValueError(f"findings with no cited ruling: {missing}")
    return [records[ref] for ref in findings]


# --- recording ---------------------------------------------------------------------


@dataclass(frozen=True)
class Recorded:
    name: str
    slot: str
    status: str
    sheets: tuple[str, ...]
    counts: bool
    problem: str | None


def record_review(
    review: dict[str, Any],
    pdf: Path,
    *,
    author_family: str,
    provenance: dict[str, Any],
    author_model: str | None = None,
    refusal: dict[str, Any] | None = None,
    rebuttals: Sequence[dict[str, Any]] | None = None,
    ledger_path: Path = LEDGER_PATH,
) -> Recorded:
    """Enter one accepted review in its slot, replacing that slot's previous entry.

    ``review`` is a machinist_review record (``Review`` as a dict): a blind
    review of one registry drawing's PDF that passed, or whose every gating
    finding ``rebuttals`` answers with a cited ruling.  ``pdf`` must still hash
    to the reviewed ``source_sha256`` -- a re-rendered file is not the sheet the
    reviewer saw -- and is stored beside the ledger.  A same-family review
    lands in ``last_resort`` and counts only with a recent quota ``refusal``, a
    trailer-verified author model and the tier rule met.
    """
    name = review["name"]
    if name not in DRAWINGS_BY_NAME:
        raise ValueError(
            f"{name}: not a registry drawing; only registry PDFs enter the ledger"
        )
    if not review.get("blind") or review.get("verdict") is None:
        raise ValueError(f"{name}: only a blind review with a verdict is recorded")
    status = SHIP
    rebutted: list[dict[str, Any]] = []
    if rebuttals:
        if review.get("passed"):
            raise ValueError(f"{name}: a passing review has nothing to rebut")
        rebutted = apply_rebuttals(review["verdict"], rebuttals)
        status = ACCEPTED_WITH_RULINGS
    elif not review.get("passed"):
        raise ValueError(
            f"{name}: only a passing review, or one with rebuttals, is recorded"
        )
    if len(review["source_sha256"]) != 1:
        raise ValueError(
            f"{name}: expected one reviewed PDF, got {len(review['source_sha256'])}"
        )
    actual = sha256_file(pdf)
    if actual != review["source_sha256"][0]:
        raise ValueError(
            f"{pdf}: sha256 {actual[:12]} is not the reviewed {review['source_sha256'][0][:12]}"
        )
    slot = review_slot(review["reviewer"], author_family)
    author = resolve_author(name, author_family, author_model)
    problem = None
    if slot == LAST_RESORT:
        problem = _last_resort_problem(review, author, refusal)
    sheets = read_sheets(pdf)
    if len(sheets) != review["sheet_count"]:
        raise ValueError(
            f"{name}: {pdf} has {len(sheets)} sheets, the review saw {review['sheet_count']}"
        )
    digests = [sheet_digest(sheet.ink) for sheet in sheets]
    stored = sheets_dir(ledger_path) / f"{actual}.pdf"
    if not stored.is_file():
        stored.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pdf, stored)
    verdict = review["verdict"]
    entry: dict[str, Any] = {
        "status": status,
        "counts": problem is None,
        "pdf": actual,
        "sheets": digests,
        "renderer": f"pypdfium2 {version('pypdfium2')}",
        "reviewer": review["reviewer"],
        "reviewer_family": reviewer_family(review["reviewer"]),
        "model": review["model"],
        "effort": review["effort"],
        "author": author,
        "prompt_sha256": review["prompt_sha256"],
        "reviewed_at": review["reviewed_at"],
        "verdict": verdict["verdict"],
        "summary": verdict["summary"],
        "findings": {key: len(verdict.get(key) or []) for key in FINDING_KEYS},
        "minor": [
            f"{item['where']}: {item['issue']}" for item in verdict.get("minor") or []
        ],
        "provenance": provenance,
    }
    if rebutted:
        entry["rebuttals"] = rebutted
    if slot == LAST_RESORT:
        entry["quota_refusal"] = refusal
        entry["quota_refusal_window_hours"] = QUOTA_REFUSAL_MAX_AGE / timedelta(hours=1)
        entry["not_counted_because"] = problem
    ledger = load_ledger(ledger_path)
    ledger["drawings"].setdefault(name, {})[slot] = entry
    save_ledger(ledger, ledger_path)
    return Recorded(name, slot, status, tuple(digests), problem is None, problem)


def _last_resort_problem(
    review: dict[str, Any], author: dict[str, Any], refusal: dict[str, Any] | None
) -> str | None:
    if refusal is None:
        return "no recorded quota refusal by the cross-family reviewer"
    stale = refusal_problem(
        refusal,
        pdf_sha256=review["source_sha256"][0],
        reviewed_at=review["reviewed_at"],
    )
    if stale:
        return stale
    if author["model_source"] != "trailer":
        return "the author model is not named by a trailer on the draw script's last commit"
    return last_resort_tier_problem(author["model"], review["model"], review["effort"])


def ingest(
    report: Path,
    *,
    author_family: str,
    author_model: str | None = None,
    refusal_report: Path | None = None,
    rebuttals_path: Path | None = None,
    pdf: Path | None = None,
    ledger_path: Path = LEDGER_PATH,
) -> Recorded:
    """Record an EXISTING verdict JSON against the exact PDF it reviewed."""
    review = json.loads(report.read_text(encoding="utf-8"))
    sources = review.get("sources") or []
    if len(sources) != 1 or not str(sources[0]).lower().endswith(".pdf"):
        raise ValueError(f"{report}: expected one registry PDF, got {sources}")
    refusal = None
    if refusal_report is not None:
        refusal = quota_refusal(
            refusal_report, name=review["name"], author_family=author_family
        )
    rebuttals = None
    if rebuttals_path is not None:
        rebuttals = load_rebuttals(rebuttals_path, name=review["name"])
    return record_review(
        review,
        pdf or Path(sources[0]),
        author_family=author_family,
        author_model=author_model,
        refusal=refusal,
        rebuttals=rebuttals,
        provenance={"ingested_from": Path(report).resolve().as_posix()},
        ledger_path=ledger_path,
    )


# --- drift check -------------------------------------------------------------------


class State(StrEnum):
    OK = "ok"
    DRIFT = "drift"
    UNREVIEWED = "unreviewed"
    UNRENDERED = "unrendered"


@dataclass(frozen=True)
class Status:
    name: str
    state: State
    detail: str
    via: str  # the accepting entry, e.g. "cross_family ship"; "" when none
    last_resort: str  # "-" (none recorded) | "matches" | "drift"
    diff_files: tuple[str, ...] = ()


@dataclass
class Comparison:
    problem: str  # empty when the sheets match
    differences: list[SheetDifference]


class _References:
    """Reviewed PDFs, verified and rendered once per check."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.cache: dict[str, list[Sheet]] = {}
        self.problems: dict[str, str] = {}

    def problem(self, sha: str) -> str:
        """Empty when the stored PDF exists and still hashes to ``sha``."""
        if sha not in self.problems:
            path = self.directory / f"{sha}.pdf"
            if not path.is_file():
                self.problems[sha] = "the reviewed PDF is missing from the ledger"
            elif sha256_file(path) != sha:
                self.problems[sha] = (
                    f"the stored reviewed PDF {path.name} does not hash to its name"
                )
            else:
                self.problems[sha] = ""
        return self.problems[sha]

    def get(self, sha: str) -> list[Sheet] | None:
        if sha not in self.cache:
            path = self.directory / f"{sha}.pdf"
            if not path.is_file():
                return None
            self.cache[sha] = read_sheets(path)
        return self.cache[sha]


def _compare(
    entry: dict[str, Any], current: Sequence[Sheet], references: _References
) -> Comparison:
    if len(entry["sheets"]) != len(current):
        return Comparison(
            f"{len(entry['sheets'])} sheets reviewed, {len(current)} now", []
        )
    stored = references.problem(entry["pdf"])
    if stored:
        return Comparison(stored, [])
    digests = [sheet_digest(sheet.ink) for sheet in current]
    if digests == entry["sheets"]:
        return Comparison("", [])
    reference = references.get(entry["pdf"])
    if reference is None:
        return Comparison("the reviewed PDF is missing from the ledger", [])
    differences = [
        difference
        for index, (was, now) in enumerate(zip(reference, current), start=1)
        if (difference := sheet_difference(was, now, index=index)) is not None
    ]
    if not differences:
        return Comparison("", [])
    return Comparison(
        f"sheet {', '.join(d.summary() for d in differences)} changed", differences
    )


def _reviewed(entry: dict[str, Any]) -> str:
    return f"{entry['reviewer']}/{entry['model']} {entry['reviewed_at']}"


def drawing_status(
    name: str,
    ledger: dict[str, Any],
    *,
    references: _References,
    pdf: Path | None = None,
    report_dir: Path | None = None,
) -> Status:
    """Where ``name``'s current sheets stand against its recorded reviews."""
    pdf = pdf or DRAWINGS_BY_NAME[name].outputs["pdf"]
    if not pdf.is_file():
        return Status(name, State.UNRENDERED, f"no rendered PDF at {pdf}", "", "-")
    entry = ledger["drawings"].get(name, {})
    if not entry:  # nothing to compare against: skip the 300 dpi render
        return Status(name, State.UNREVIEWED, "no accepted review recorded", "", "-")
    current = read_sheets(pdf)
    cross, last = entry.get(CROSS_FAMILY), entry.get(LAST_RESORT)
    cross_cmp = None if cross is None else _compare(cross, current, references)
    last_cmp = None if last is None else _compare(last, current, references)
    last_resort = (
        "-" if last_cmp is None else "drift" if last_cmp.problem else "matches"
    )
    if cross_cmp is not None and not cross_cmp.problem:
        return Status(
            name,
            State.OK,
            _reviewed(cross),
            f"{CROSS_FAMILY} {cross['status']}",
            last_resort,
        )
    if last_resort == "matches" and last["counts"]:
        return Status(
            name,
            State.OK,
            _reviewed(last),
            f"{LAST_RESORT} {last['status']}",
            last_resort,
        )
    if cross_cmp is None and last is not None and not last["counts"]:
        reason = f"last-resort review does not count: {last['not_counted_because']}"
        return Status(name, State.UNREVIEWED, reason, "", last_resort)
    if cross_cmp is None and last_cmp is None:
        return Status(
            name, State.UNREVIEWED, "no accepted review recorded", "", last_resort
        )
    reference, comparison = (
        (cross, cross_cmp) if cross_cmp is not None else (last, last_cmp)
    )
    files: list[Path] = []
    if report_dir is not None and comparison.differences:
        files = write_diff(name, comparison.differences, current, report_dir)
    return Status(
        name,
        State.DRIFT,
        f"{comparison.problem} since {_reviewed(reference)}",
        "",
        last_resort,
        tuple(path.as_posix() for path in files),
    )


def check(
    names: Iterable[str] = (),
    *,
    ledger_path: Path = LEDGER_PATH,
    report_dir: Path | None = None,
) -> list[Status]:
    ledger = load_ledger(ledger_path)
    selected = list(names) or [spec.name for spec in DRAWINGS]
    unknown = [name for name in selected if name not in DRAWINGS_BY_NAME]
    if unknown:
        raise ValueError(f"unknown drawing names: {unknown}")
    references = _References(sheets_dir(ledger_path))
    return [
        drawing_status(name, ledger, references=references, report_dir=report_dir)
        for name in selected
    ]


_REVIEWER_FOR = {"claude": "codex", "gpt": "claude", "mimo": "claude"}


def fix_command(status: Status, author: Author | ValueError | None = None) -> str:
    """The command that clears a failing drawing: render it, or review it."""
    if status.state == State.UNRENDERED:
        return f"uv run python -m doit drawing:{status.name}"
    review = f"uv run cad/scripts/machinist_review.py {status.name}"
    script = DRAWINGS_BY_NAME[status.name].script_name
    if author is None:
        try:
            author = draw_script_author(status.name)
        except ValueError as exc:
            author = exc
    if isinstance(author, ValueError):
        return f"{author}; then {review} --reviewer <other family> --author-family <family>"
    family = None if author.model is None else model_family(author.model)
    if family is None:
        return (
            f"{review} --reviewer <other family> --author-family <family that last "
            f"edited {script}> (its last commit names no model)"
        )
    return f"{review} --reviewer {_REVIEWER_FOR[family]} --author-family {family}"


# --- CLI ---------------------------------------------------------------------------


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ledger", type=Path, default=LEDGER_PATH)
    commands = parser.add_subparsers(dest="command", required=True)

    check_cmd = commands.add_parser(
        "check", help="list drawings whose sheets match no accepted, counting review"
    )
    check_cmd.add_argument(
        "names", nargs="*", help="registry drawing names (default: all)"
    )
    check_cmd.add_argument(
        "--allow-unrendered",
        action="store_true",
        help="do not fail on a drawing with no PDF",
    )
    check_cmd.add_argument(
        "--json", action="store_true", help="machine-readable statuses"
    )
    check_cmd.add_argument(
        "--report-dir",
        type=Path,
        default=REPORT_DIR,
        help="where changed sheets' diffs go",
    )

    ingest_cmd = commands.add_parser("ingest", help="record an existing verdict JSON")
    ingest_cmd.add_argument("report", type=Path, help="machinist_review verdict JSON")
    ingest_cmd.add_argument("--author-family", required=True, choices=AUTHOR_FAMILIES)
    ingest_cmd.add_argument(
        "--author-model",
        help="cross-check for the model in the draw script's commit trailer",
    )
    ingest_cmd.add_argument(
        "--quota-refusal",
        type=Path,
        help="the cross-family reviewer's quota-refused report",
    )
    ingest_cmd.add_argument(
        "--rebuttals",
        type=Path,
        help="cited user rulings answering every gating finding",
    )
    ingest_cmd.add_argument(
        "--pdf", type=Path, help="the reviewed PDF, if it moved since"
    )

    fingerprint_cmd = commands.add_parser(
        "fingerprint", help="print a PDF's sheet digests"
    )
    fingerprint_cmd.add_argument("pdf", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        return _run(args)
    except (OSError, ValueError) as exc:
        print(f"{args.command}: {exc}", file=sys.stderr)
        return 2


def _run(args: argparse.Namespace) -> int:
    if args.command == "fingerprint":
        for index, digest in enumerate(fingerprint(args.pdf), start=1):
            print(f"sheet {index}: {digest}")
        return 0
    if args.command == "ingest":
        recorded = ingest(
            args.report,
            author_family=args.author_family,
            author_model=args.author_model,
            refusal_report=args.quota_refusal,
            rebuttals_path=args.rebuttals,
            pdf=args.pdf,
            ledger_path=args.ledger,
        )
        counted = "" if recorded.counts else f", does NOT count: {recorded.problem}"
        print(
            f"recorded {recorded.name} as {recorded.slot} {recorded.status} "
            f"({len(recorded.sheets)} sheets{counted})"
        )
        # Recorded is not accepted: a row that does not count must not read as success.
        return 0 if recorded.counts else 1

    statuses = check(args.names, ledger_path=args.ledger, report_dir=args.report_dir)
    if args.json:
        authors = draw_script_authors(
            [status.name for status in statuses if status.state != State.OK]
        )
        rows = [
            {
                **status.__dict__,
                "state": str(status.state),
                "fix": None
                if status.state == State.OK
                else fix_command(status, authors[status.name]),
            }
            for status in statuses
        ]
        print(json.dumps(rows, indent=2))
    else:
        for status in statuses:
            print(
                f"{status.state:<10} {status.name:<32} {status.via or '-':<34} "
                f"last-resort={status.last_resort:<7} {status.detail}"
            )
            for path in status.diff_files:
                print(f"{'':<10} diff: {path}")
    accepted = {State.OK, State.UNRENDERED} if args.allow_unrendered else {State.OK}
    failing = [status for status in statuses if status.state not in accepted]
    via = Counter(status.via for status in statuses if status.state == State.OK)
    last_resort = sum(n for key, n in via.items() if key.startswith(LAST_RESORT))
    rulings = sum(n for key, n in via.items() if key.endswith(ACCEPTED_WITH_RULINGS))
    print(
        f"{len(statuses) - len(failing)}/{len(statuses)} drawings match an accepted review "
        f"({last_resort} via last resort, {rulings} accepted with rulings)",
        file=sys.stderr,
    )
    if failing:
        print(
            f"{len(failing)} drawings have no counting machinist review of the sheet "
            "now rendered; each blocks the release until its command runs:",
            file=sys.stderr,
        )
        authors = draw_script_authors([status.name for status in failing])
        for status in failing:
            fix = fix_command(status, authors[status.name])
            print(f"  {status.name} ({status.state}): {fix}", file=sys.stderr)
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
