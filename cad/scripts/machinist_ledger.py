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
* **Backfill** -- ``backfill`` searches directories for every ``SHIP`` on
  record, finds the exact PDF each reviewed by its sha256 wherever it now
  lives, and ingests per drawing the newest one whose sheets match the current
  render and which counts.  A newer failing verdict of the same sheets (or one
  whose PDF is lost, so nothing shows it saw other sheets) blocks it.  Dry run
  unless ``--apply``; the table sorts every drawing into what was ingested,
  what drifted and what never had a ``SHIP``.  A draw script whose last
  commit names no model takes its family from ``cad/reviews/author-rulings.json``:
  a ruling on that drawing naming that exact commit, else the ``untrailered``
  class rule.  A ruling marked ``both_families`` (it and the class rule
  disagree) makes ``check`` require a counting review from each reviewer
  family, filed under ``both_families_<family>``.

No build task reads the ledger, so recording a review never re-keys a build.

Usage (SolidWorks-free)::

    uv run cad/scripts/machinist_ledger.py check                 # every registry drawing
    uv run cad/scripts/machinist_ledger.py check crank_pinion_pin
    uv run cad/scripts/machinist_ledger.py ingest <verdict.json> --author-family gpt
    uv run cad/scripts/machinist_ledger.py ingest <fix.json> --author-family claude \
        --rebuttals <rebuttals.json>
    uv run cad/scripts/machinist_ledger.py backfill <root>... --exclude <name> \
        [--checkout <rendered checkout>] [--apply]
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
import functools
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from importlib.metadata import version
from pathlib import Path
from typing import Any, NamedTuple

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import _telemetry  # noqa: E402
from _drawing_registry import CAD_ROOT, DRAWINGS, DRAWINGS_BY_NAME  # noqa: E402

REPO_ROOT = CAD_ROOT.parent
PROMPTS_DIR = SCRIPTS_DIR / "prompts"
LEDGER_PATH = CAD_ROOT / "reviews" / "machinist-ledger.json"
OUTAGES_PATH = CAD_ROOT / "reviews" / "outages.json"
AUTHOR_RULINGS_PATH = CAD_ROOT / "reviews" / "author-rulings.json"
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
REVIEW_FAMILIES = tuple(sorted(set(REVIEWER_FAMILIES.values())))  # ("claude", "gpt")
AUTHOR_FAMILIES = ("claude", "gpt", "mimo")
FINDING_KEYS = ("blockers", "over_specification", "clarity", "minor")
GATING_KEYS = ("blockers", "over_specification", "clarity")

CROSS_FAMILY = "cross_family"
LAST_RESORT = "last_resort"
OUTAGE_FALLBACK = "outage_fallback"  # same family, by user direction, during an outage
BOTH_FAMILIES = "both_families"  # slot prefix: both_families_<reviewer family>
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
    reviewed: str  # masked-ink sha256 of the reviewed sheet
    current: str  # and of the sheet now rendered
    mask: Any = field(repr=False, default=None)

    def summary(self) -> str:
        pair = f"reviewed {self.reviewed[:12]} -> now {self.current[:12]}"
        if self.pixels < 0:
            return f"{self.index} (sheet size changed; {pair})"
        parts = [f"{self.pixels} px"]
        if self.text:
            parts.append(
                f"{len(self.text)} text change{'s' if len(self.text) != 1 else ''}"
            )
        return f"{self.index} ({', '.join(parts)}; {pair})"


def sheet_difference(
    reference: Sheet, current: Sheet, *, index: int
) -> SheetDifference | None:
    """None when ``current`` matches ``reference`` under rule (a) or (b)."""
    reviewed, now = sheet_digest(reference.ink), sheet_digest(current.ink)
    if reviewed == now:
        return None
    text = text_difference(reference.text, current.text)
    if reference.ink.shape != current.ink.shape:
        return SheetDifference(index, -1, text, reviewed, now)
    mask = residual_mask(reference.ink, current.ink)
    pixels = int(mask.sum())
    if not pixels and not text:
        return None
    return SheetDifference(index, pixels, text, reviewed, now, mask)


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


def other_family(family: str) -> str:
    """The other reviewer family: the author under which a review is cross-family."""
    [other] = [f for f in REVIEW_FAMILIES if f != family]
    return other


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


_OBJECT_ID = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")


def _last_commits(blobs: dict[str, str], repo: Path) -> dict[str, str]:
    """The newest commit that produced each path's HEAD blob; stops once all are seen.

    Matching the blob, not just "touched the path", is what keeps a newer edit
    on a side branch that a merge did not take from reading as the author of
    the content the merge kept.  Every blob in ``blobs`` is committed, so an
    unbounded walk would only read older history -- which a shallow or partial
    clone (a farm worker's depth-1 fetch) does not have, making git fail or
    fetch its way back.
    """
    last: dict[str, str] = {}
    if not blobs:
        return last
    proc = subprocess.Popen(
        # -c: a merge whose result differs from every parent produced its blob
        [
            "git",
            "-C",
            str(repo),
            "log",
            "--format=%x00%H",
            "--raw",
            "-c",
            "--no-abbrev",
            "--no-renames",
            "--",
            *blobs,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        commit = ""
        for line in proc.stdout or ():
            line = line.rstrip("\n")
            if line.startswith("\x00"):
                commit = line[1:]
                continue
            meta, tab, path = line.partition("\t")
            if not tab or path not in blobs:
                continue
            ids = [token for token in meta.split() if _OBJECT_ID.match(token)]
            if ids and ids[-1] == blobs[path]:  # the post-image
                last.setdefault(path, commit)
                if len(last) == len(blobs):
                    break
    finally:
        proc.kill()
        proc.wait()
    return last


@functools.cache
def _shallow_file(repo: Path) -> Path | None:
    """Where this clone lists its shallow commits (a worktree shares its clone's)."""
    shallow = _git("rev-parse", "--git-path", "shallow", repo=repo)
    return repo / shallow if shallow else None


def _shallow_boundary(repo: Path) -> set[str]:
    """Commits whose parents this clone lacks; their diff lists every file."""
    path = _shallow_file(repo)
    if path is None or not path.is_file():
        return set()
    return set(path.read_text(encoding="utf-8").split())


def script_authors(
    paths: Sequence[Path], *, repo: Path = REPO_ROOT
) -> dict[Path, Author | ValueError]:
    """The model named by the last commit that touched each path.

    A fixed number of git calls for any number of paths: a drift check that
    lists every unreviewed drawing must not spawn git per drawing.
    """
    if not paths:  # an empty pathspec would make git walk every file's history
        return {}
    rels = {
        path: path.resolve().relative_to(repo.resolve()).as_posix() for path in paths
    }
    status = _git("status", "--porcelain", "--", *rels.values(), repo=repo) or ""
    dirty = {line.split(maxsplit=1)[-1] for line in status.splitlines()}  # "XY path"
    tree = _git("ls-tree", "HEAD", "--", *rels.values(), repo=repo) or ""
    blobs = {  # "<mode> blob <id>\t<path>"
        line.partition("\t")[2]: line.split()[2] for line in tree.splitlines()
    }
    last = _last_commits(
        {rel: blob for rel, blob in blobs.items() if rel not in dirty}, repo
    )
    boundary = _shallow_boundary(repo) if last else set()
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
        elif commit in boundary:
            authors[path] = ValueError(
                f"{rel}: this clone is shallow and its history stops at "
                f"{commit[:12]}, so the commit that last touched it is not on record"
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


def _draw_script(name: str, repo: Path) -> Path:
    scripts = repo / SCRIPTS_DIR.relative_to(REPO_ROOT)
    return scripts / DRAWINGS_BY_NAME[name].script_name


def draw_script_author(name: str, *, repo: Path = REPO_ROOT) -> Author:
    return script_author(_draw_script(name, repo), repo=repo)


def draw_script_authors(
    names: Sequence[str], *, repo: Path = REPO_ROOT
) -> dict[str, Author | ValueError]:
    paths = {name: _draw_script(name, repo) for name in names}
    found = script_authors(list(paths.values()), repo=repo)
    return {name: found[path] for name, path in paths.items()}


def resolve_author(
    name: str,
    author_family: str,
    author_model: str | None,
    *,
    repo: Path = REPO_ROOT,
    known: Author | None = None,
) -> dict[str, Any]:
    """The author on record: the trailer's model, cross-checked against the claims.

    ``known`` is the draw script's author when the caller already walked it.
    """
    author = known or draw_script_author(name, repo=repo)
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


_RULING_KEYS = ("drawing", "family", "commit", "ruled_by", "ruled_at", "evidence")
_RULE_KEYS = ("family", "ruled_by", "ruled_at", "evidence")
UNTRAILERED = "rule: no trailer"  # the author-family source the class rule gives


@dataclass(frozen=True)
class AuthorRulings:
    """Who authored a draw script whose producing commit names no model.

    ``drawings`` holds rulings on one drawing's exact commit; ``untrailered``
    is the class rule for every commit without a model trailer.  A trailer
    wins over both, and a drawing's ruling on its current commit over the rule.
    """

    drawings: dict[str, dict[str, Any]] = field(default_factory=dict)
    untrailered: dict[str, Any] | None = None

    def both_families(self, name: str) -> str:
        """Why ``name`` needs a counting review from every reviewer family; "" if not.

        Set on a drawing whose per-drawing ruling and class rule disagree on
        the author: one of the two reviews is then cross-family whoever wrote
        it.  It holds whatever the script's last commit, so it fails closed.
        """
        return (self.drawings.get(name) or {}).get("both_families", "")


class Ruled(NamedTuple):
    family: str | None
    source: str  # "ruling", UNTRAILERED, or "" when nothing applies
    ruling: dict[str, Any] | None
    problem: str  # why nothing applies


def load_author_rulings(path: Path = AUTHOR_RULINGS_PATH) -> AuthorRulings:
    """Recorded rulings on who authored a draw script whose commit names no model.

    Each drawing ruling names the exact commit it judged, so a later edit to
    the script -- a new author -- is never covered by it.  The ``untrailered``
    rule covers any commit whose trailers name no model.
    """
    if not path.is_file():
        return AuthorRulings()
    data = json.loads(path.read_text(encoding="utf-8"))
    rule = data.get("untrailered")
    if rule is not None:
        missing = [key for key in _RULE_KEYS if not rule.get(key)]
        if missing:
            raise ValueError(f"{path}: the untrailered rule lacks {missing}")
        if rule["family"] not in AUTHOR_FAMILIES:
            raise ValueError(
                f"{path}: untrailered: family {rule['family']!r} is not one of "
                f"{AUTHOR_FAMILIES}"
            )
    rulings: dict[str, dict[str, Any]] = {}
    for ruling in data.get("rulings", []):
        missing = [key for key in _RULING_KEYS if not ruling.get(key)]
        if missing:
            raise ValueError(f"{path}: ruling {ruling} lacks {missing}")
        if ruling["family"] not in AUTHOR_FAMILIES:
            raise ValueError(
                f"{path}: {ruling['drawing']}: family {ruling['family']!r} is not "
                f"one of {AUTHOR_FAMILIES}"
            )
        if not re.fullmatch(r"[0-9a-f]{40}", ruling["commit"]):
            raise ValueError(
                f"{path}: {ruling['drawing']}: commit must be a full sha, "
                f"not {ruling['commit']!r}"
            )
        both = ruling.get("both_families")
        if "both_families" in ruling and not (isinstance(both, str) and both):
            raise ValueError(
                f"{path}: {ruling['drawing']}: both_families must say why both "
                "families are required"
            )
        if ruling["drawing"] in rulings:
            raise ValueError(f"{path}: two rulings for {ruling['drawing']}")
        rulings[ruling["drawing"]] = ruling
    return AuthorRulings(rulings, rule)


def ruled_family(name: str, author: Author, rulings: AuthorRulings) -> Ruled:
    """The family the rulings assign an author whose commit names no model."""
    ruling = rulings.drawings.get(name)
    if ruling is not None and ruling["commit"] == author.commit:
        return Ruled(ruling["family"], "ruling", ruling, "")
    if rulings.untrailered is not None:
        return Ruled(
            rulings.untrailered["family"], UNTRAILERED, rulings.untrailered, ""
        )
    if ruling is None:
        problem = (
            f"{author.script} last commit {author.commit[:12]} names no model and "
            f"no ruling in {AUTHOR_RULINGS_PATH.name} covers it"
        )
    else:
        problem = (
            f"the {name} ruling judged {ruling['commit'][:12]}, but {author.script} "
            f"was last changed by {author.commit[:12]}"
        )
    return Ruled(None, "", None, problem)


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


# --- outage ------------------------------------------------------------------------

_OUTAGE_KEYS = (
    "id",
    "reviewer",
    "fallback_reviewer",
    "fallback_model",
    "directed_by",
    "quote",
    "directed_at",
    "started_at",
)


def load_outages(path: Path = OUTAGES_PATH) -> dict[str, dict[str, Any]]:
    """Named reviewer outages the user directed a same-family fallback for, by id.

    Each carries the user's words, when they were given, the window (open
    while ``ended_at`` is null) and an excerpt of the failing reviewer's
    output.  A fallback review counts only inside its outage's window, and
    stops counting once the outage is closed: that is the re-review list.
    """
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    outages: dict[str, dict[str, Any]] = {}
    for outage in data.get("outages", []):
        missing = [key for key in _OUTAGE_KEYS if not outage.get(key)]
        if missing:
            raise ValueError(f"{path}: outage {outage.get('id')} lacks {missing}")
        name = outage["id"]
        evidence = outage.get("evidence") or {}
        if not evidence.get("path") or not evidence.get("excerpt"):
            raise ValueError(f"{path}: {name}: evidence needs its path and an excerpt")
        for key in ("reviewer", "fallback_reviewer"):
            if outage[key] not in REVIEWER_FAMILIES:
                raise ValueError(f"{path}: {name}: unknown {key} {outage[key]!r}")
        if reviewer_family(outage["reviewer"]) == reviewer_family(
            outage["fallback_reviewer"]
        ):
            raise ValueError(
                f"{path}: {name}: the fallback is the same family as the reviewer "
                "that is down"
            )
        # Reviews are stamped in UTC; a naive window time cannot be compared.
        window = {
            key: datetime.fromisoformat(outage[key])
            for key in ("started_at", "ended_at")
            if outage.get(key) is not None
        }
        naive = [key for key, when in window.items() if when.tzinfo is None]
        if naive:
            raise ValueError(f"{path}: {name}: {naive[0]} needs a UTC offset")
        if "ended_at" in window and window["ended_at"] < window["started_at"]:
            raise ValueError(f"{path}: {name}: it ended before it started")
        if name in outages:
            raise ValueError(f"{path}: two outages named {name}")
        outages[name] = outage
    return outages


def outage_problem(
    review: dict[str, Any], author_family: str, outage: dict[str, Any]
) -> str | None:
    """Why ``review`` is not the fallback its outage directed; None when it is."""
    if reviewer_family(review["reviewer"]) != author_family:
        return "a cross-family review needs no outage"
    if reviewer_family(outage["reviewer"]) == author_family:
        return (
            f"outage {outage['id']} is of {outage['reviewer']}, not the cross-family "
            f"reviewer of a {author_family} author"
        )
    directed = (outage["fallback_reviewer"], outage["fallback_model"])
    if (review["reviewer"], review["model"]) != directed:
        return (
            f"{review['reviewer']}/{review['model']} is not the directed fallback "
            f"{'/'.join(directed)}"
        )
    reviewed = datetime.fromisoformat(review["reviewed_at"])
    started = datetime.fromisoformat(outage["started_at"])
    ended = outage.get("ended_at")
    if reviewed < started or (ended and reviewed > datetime.fromisoformat(ended)):
        return (
            f"reviewed at {review['reviewed_at']}, outside outage {outage['id']} "
            f"({outage['started_at']} to {ended or 'now'})"
        )
    return None


# --- prompt ------------------------------------------------------------------------


@functools.cache
def standard_rubrics(kind: str) -> tuple[str, ...]:
    """Every committed version of the standard rubric for a ``kind`` package."""
    rel = (PROMPTS_DIR / f"machinist_review_{kind}.md").relative_to(REPO_ROOT)
    commits = (_git("log", "--format=%H", "--", rel.as_posix()) or "").split()
    if not commits:
        return ()
    # One process for every version: a git spawn costs ~70 ms on Windows.
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "cat-file", "--batch"],
        input="".join(f"{commit}:{rel.as_posix()}\n" for commit in commits).encode(),
        capture_output=True,
        check=False,
    )
    rubrics, out = [], proc.stdout
    while out:
        header, _, out = out.partition(b"\n")
        fields = header.split()
        if len(fields) != 3:  # "<object> missing"
            continue
        size = int(fields[2])
        blob, out = out[:size], out[size + 1 :]
        rubrics.append(blob.decode("utf-8").replace("\r\n", "\n"))
    return tuple(rubrics)


def verdict_passes(review: dict[str, Any]) -> bool:
    """Pass or fail from the verdict itself: a SHIP with no gating finding.

    The record's ``passed`` flag must agree; an edited or malformed report is
    refused rather than trusted or silently corrected.
    """
    import machinist_review  # imports this module; a top-level import would cycle

    name = review["name"]
    try:
        verdict = machinist_review.validate_verdict(review["verdict"])
    except ValueError as exc:
        raise ValueError(f"{name}: its verdict is malformed: {exc}") from None
    passed = machinist_review.is_pass(verdict)
    if bool(review.get("passed")) != passed:
        raise ValueError(
            f"{name}: its passed flag ({review.get('passed')}) contradicts its "
            f"{verdict['verdict']} verdict"
        )
    return passed


def prompt_problem(review: dict[str, Any]) -> str | None:
    """Why a review's prompt is not the gate's; None under a committed rubric.

    A ``--prompt-file`` override (or any hand-edited prompt) is a different
    review, whatever its verdict, so it fails closed: the record must carry
    the exact prompt the reviewer saw, hashing to its ``prompt_sha256``, and
    that prompt must be exactly what machinist_review builds around a
    committed version of the standard rubric -- no text added or removed.
    """
    import machinist_review  # imports this module; a top-level import would cycle

    evidence = (review.get("extra") or {}).get("evidence") or {}
    prompt = evidence.get("effective_prompt")
    if not prompt:
        return "the record does not carry the prompt the reviewer saw"
    if hashlib.sha256(prompt.encode("utf-8")).hexdigest() != review.get(
        "prompt_sha256"
    ):
        return "the recorded prompt does not hash to its prompt_sha256"
    package = machinist_review.ReviewPackage(review["name"], review["kind"], ())
    text = prompt.replace("\r\n", "\n")
    standard = (
        machinist_review._review_prompt(
            package,
            review["sheet_count"],
            reviewer=review["reviewer"],
            prompt_text=rubric,
        )
        for rubric in standard_rubrics(review["kind"])
    )
    if text not in standard:
        return (
            f"its prompt is not the standard prompt around a committed rubric for a "
            f"{review['kind']} package (a --prompt-file override is not the gate)"
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
    # The whole id: "U31" must not match inside "U31A" or "U310".
    pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(ruling)}(?![A-Za-z0-9])")
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
    outage: dict[str, Any] | None = None,
    repo: Path = REPO_ROOT,
    digests: Sequence[str] | None = None,
    known_author: Author | None = None,
    rulings: AuthorRulings | None = None,
) -> Recorded:
    """Enter one accepted review in its slot, replacing that slot's previous entry.

    ``review`` is a machinist_review record (``Review`` as a dict): a blind
    review of one registry drawing's PDF that passed, or whose every gating
    finding ``rebuttals`` answers with a cited ruling.  ``pdf`` must still hash
    to the reviewed ``source_sha256`` -- a re-rendered file is not the sheet the
    reviewer saw -- and is stored beside the ledger.  A same-family review
    lands in ``last_resort`` and counts only with a recent quota ``refusal``, a
    trailer-verified author model and the tier rule met.  A same-family review
    the user directed during a named ``outage`` of the cross-family reviewer
    lands in ``outage_fallback`` instead: it counts while that outage is open.
    A drawing whose ``rulings`` (default: the tracked file) require both
    families files each review under its reviewer's family,
    ``both_families_<family>``; an outage fallback does not stand in for one.
    """
    name = review["name"]
    if name not in DRAWINGS_BY_NAME:
        raise ValueError(
            f"{name}: not a registry drawing; only registry PDFs enter the ledger"
        )
    if not review.get("blind") or review.get("verdict") is None:
        raise ValueError(f"{name}: only a blind review with a verdict is recorded")
    kind = DRAWINGS_BY_NAME[name].source_kind
    if review.get("kind") != kind:
        raise ValueError(
            f"{name}: its review kind is {review.get('kind')!r}, the registry's is "
            f"{kind!r}; only the {kind} rubric reviews it"
        )
    passed = verdict_passes(review)
    status = SHIP
    rebutted: list[dict[str, Any]] = []
    if rebuttals:
        if passed:
            raise ValueError(f"{name}: a passing review has nothing to rebut")
        rebutted = apply_rebuttals(review["verdict"], rebuttals)
        status = ACCEPTED_WITH_RULINGS
    elif not passed:
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
    if outage is not None:
        why = outage_problem(review, author_family, outage)
        if why:
            raise ValueError(f"{name}: not an outage fallback: {why}")
        slot = OUTAGE_FALLBACK
    rulings = load_author_rulings() if rulings is None else rulings
    both_families = rulings.both_families(name)
    if both_families and outage is not None:
        raise ValueError(
            f"{name}: both families are required ({both_families}); an outage "
            "fallback does not stand in for the missing family"
        )
    if both_families:  # either family's review counts; drawing_status needs each
        slot = f"{BOTH_FAMILIES}_{reviewer_family(review['reviewer'])}"
    author = resolve_author(
        name, author_family, author_model, repo=repo, known=known_author
    )
    problem = None
    if slot == LAST_RESORT:
        problem = _last_resort_problem(review, author, refusal)
    if digests is None:  # a caller that rendered these exact bytes may pass them
        digests = [sheet_digest(sheet.ink) for sheet in read_sheets(pdf)]
    digests = list(digests)
    if len(digests) != review["sheet_count"]:
        raise ValueError(
            f"{name}: {pdf} has {len(digests)} sheets, the review saw {review['sheet_count']}"
        )
    prompt = prompt_problem(review)
    if prompt:
        raise ValueError(f"{name}: not recorded: {prompt}")
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
    if outage is not None:
        entry["outage"] = outage
    if both_families:
        entry["both_families"] = both_families
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
    outage_id: str | None = None,
    outages_path: Path = OUTAGES_PATH,
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
    outage = None
    if outage_id is not None:
        outage = load_outages(outages_path).get(outage_id)
        if outage is None:
            raise ValueError(f"no outage {outage_id!r} in {outages_path}")
    return record_review(
        review,
        pdf or Path(sources[0]),
        author_family=author_family,
        author_model=author_model,
        refusal=refusal,
        rebuttals=rebuttals,
        provenance={"ingested_from": Path(report).resolve().as_posix()},
        ledger_path=ledger_path,
        outage=outage,
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
    missing: tuple[str, ...] = ()  # reviewer families a both-families drawing lacks


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

    def path(self, sha: str) -> Path:
        return self.directory / f"{sha}.pdf"

    def problem(self, sha: str) -> str:
        """Empty when the stored PDF exists and still hashes to ``sha``."""
        if sha not in self.problems:
            path = self.path(sha)
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
            path = self.path(sha)
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
    outages: dict[str, dict[str, Any]] | None = None,
    both_families: str = "",
) -> Status:
    """Where ``name``'s current sheets stand against its recorded reviews.

    An ``outage_fallback`` entry of the current sheets is accepted only while
    its outage (``outages``, default: the tracked file) is open; once it is
    closed the drawing needs a cross-family re-review.  ``both_families`` (the
    ruling's reason) instead requires a counting review of the current sheets
    from every reviewer family.
    """
    pdf = pdf or DRAWINGS_BY_NAME[name].outputs["pdf"]
    if not pdf.is_file():
        return Status(name, State.UNRENDERED, f"no rendered PDF at {pdf}", "", "-")
    entry = ledger["drawings"].get(name, {})
    if not entry:  # nothing to compare against: skip the 300 dpi render
        missing = REVIEW_FAMILIES if both_families else ()
        return Status(
            name, State.UNREVIEWED, "no accepted review recorded", "", "-", (), missing
        )
    current = read_sheets(pdf)
    if both_families:
        return _both_families_status(
            name, entry, current, references, both_families, report_dir
        )
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
    fallback = entry.get(OUTAGE_FALLBACK)
    if fallback is not None and not _compare(fallback, current, references).problem:
        outage_id = fallback["outage"]["id"]
        outage = (load_outages() if outages is None else outages).get(outage_id)
        if outage is None:
            reason = f"shipped on outage fallback {outage_id}, which is not on record"
            return Status(name, State.UNREVIEWED, reason, "", last_resort)
        if outage.get("ended_at"):
            reason = (
                f"shipped on outage fallback: outage {outage_id} ended at "
                f"{outage['ended_at']}, so it needs a cross-family re-review"
            )
            return Status(name, State.UNREVIEWED, reason, "", last_resort)
        return Status(
            name,
            State.OK,
            _reviewed(fallback),
            f"{OUTAGE_FALLBACK} {fallback['status']} ({outage_id})",
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


def _both_families_status(
    name: str,
    entry: dict[str, Any],
    current: Sequence[Sheet],
    references: _References,
    reason: str,
    report_dir: Path | None,
) -> Status:
    """OK only when a counting review from every reviewer family matches."""
    matched: dict[str, str] = {}  # reviewer family -> "<slot> <status>"
    drifted: list[tuple[dict[str, Any], Comparison]] = []
    for slot, recorded in entry.items():
        if not recorded.get("counts"):
            continue
        comparison = _compare(recorded, current, references)
        if comparison.problem:
            drifted.append((recorded, comparison))
            continue
        matched.setdefault(recorded["reviewer_family"], f"{slot} {recorded['status']}")
    missing = tuple(family for family in REVIEW_FAMILIES if family not in matched)
    if not missing:
        via = " + ".join(matched[family] for family in REVIEW_FAMILIES)
        return Status(name, State.OK, f"{BOTH_FAMILIES}: {reason}", via, "-")
    detail = (
        f"both families required ({reason}); no counting {', '.join(missing)} "
        "review of these sheets"
    )
    drift = [(r, c) for r, c in drifted if r["reviewer_family"] in missing]
    if not drift:
        return Status(name, State.UNREVIEWED, detail, "", "-", (), missing)
    reference, comparison = drift[0]
    files: list[Path] = []
    if report_dir is not None and comparison.differences:
        files = write_diff(name, comparison.differences, current, report_dir)
    return Status(
        name,
        State.DRIFT,
        f"{detail}; {comparison.problem} since {_reviewed(reference)}",
        "",
        "-",
        tuple(path.as_posix() for path in files),
        missing,
    )


def check(
    names: Iterable[str] = (),
    *,
    ledger_path: Path = LEDGER_PATH,
    report_dir: Path | None = None,
    outages: dict[str, dict[str, Any]] | None = None,
    rulings: AuthorRulings | None = None,
) -> list[Status]:
    outages = load_outages() if outages is None else outages
    rulings = load_author_rulings() if rulings is None else rulings
    ledger = load_ledger(ledger_path)
    selected = list(names) or [spec.name for spec in DRAWINGS]
    unknown = [name for name in selected if name not in DRAWINGS_BY_NAME]
    if unknown:
        raise ValueError(f"unknown drawing names: {unknown}")
    references = _References(sheets_dir(ledger_path))
    return [
        drawing_status(
            name,
            ledger,
            references=references,
            report_dir=report_dir,
            outages=outages,
            both_families=rulings.both_families(name),
        )
        for name in selected
    ]


# --- backfill ----------------------------------------------------------------------

_WALK_SKIP = {".git", ".venv", "node_modules", "__pycache__"}


class Backfill(StrEnum):
    """Where one drawing stands after its SHIPs on record were tried."""

    RECORDED = "already-recorded"  # the ledger already accepts the current sheets
    INGESTED = "ingested"  # a SHIP matched and counts (dry run: would be ingested)
    NOT_COUNTED = "not-counted"  # a SHIP matched; the reviewer-family rule rejects it
    CONTRADICTED = "contradicted"  # a SHIP matched; a newer failing verdict may too
    AUTHOR_UNKNOWN = "author-unknown"  # a SHIP matched; no trailer and no ruling given
    DRIFTED = "drifted"  # every locatable SHIP's sheets differ from the current ones
    PDF_LOST = "pdf-lost"  # SHIPs on record, but the bytes they reviewed exist nowhere
    NO_SHIP = "no-ship"  # no passing SHIP on record
    UNRENDERED = "unrendered"
    EXCLUDED = "excluded"


# The order the table lists categories in; for several SHIPs of one drawing, the
# best-placed outcome is the drawing's.
_BACKFILL_ORDER = list(Backfill)


@dataclass
class Candidate:
    """One SHIP verdict on record."""

    report: Path
    review: dict[str, Any]
    drawing: str  # registry name; "" when the record names none
    pdf: Path | None = None  # where the exact reviewed bytes still exist
    skip: str = ""  # why it cannot be ingested at all; "" when it can be tried


@dataclass
class Tried:
    candidate: Candidate
    outcome: Backfill
    detail: str
    scratch: Path | None = None  # the scratch ledger it was recorded in, if it was


@dataclass
class BackfillRow:
    name: str
    outcome: Backfill
    detail: str
    tried: list[Tried] = field(default_factory=list)


@dataclass
class BackfillResult:
    checkout: Path
    head: str | None
    rows: list[BackfillRow]
    skipped: list[Candidate]  # SHIPs that cannot be ingested whatever the sheets


@dataclass
class Found:
    """What the search roots hold: verdicts, quota refusals and PDFs by file name."""

    candidates: list[Candidate]
    objections: list[Candidate]  # failing verdicts (FIX, or SHIP with findings)
    refusals: list[tuple[Path, dict[str, Any]]]
    pdfs: _PdfIndex


class BackfillCache:
    """What a backfill already learned, kept between runs.

    PDF hashes are keyed by (path, size, mtime_ns), so a rerun hashes only
    new or changed files; sheet comparisons are keyed by the two PDFs'
    sha256, so a rerun renders only pairs it has not compared.  Both are
    dropped when the fingerprint settings change.
    """

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.pdfs: dict[str, list[Any]] = {}
        self.comparisons: dict[str, list[Any]] = {}
        self.sheets: dict[str, list[str]] = {}  # PDF sha256 -> sheet digests
        self.hashed = 0
        if path is None or not path.is_file():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if data.get("fingerprint") == empty_ledger()["fingerprint"]:
            self.pdfs = data.get("pdfs", {})
            self.comparisons = data.get("comparisons", {})
            self.sheets = data.get("sheets", {})

    def digest(self, path: Path, size: int, mtime_ns: int) -> str:
        key = str(path)
        known = self.pdfs.get(key)
        if known and known[:2] == [size, mtime_ns]:
            return known[2]
        sha = sha256_file(path)
        self.pdfs[key] = [size, mtime_ns, sha]
        self.hashed += 1
        return sha

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "fingerprint": empty_ledger()["fingerprint"],
            "pdfs": self.pdfs,
            "comparisons": self.comparisons,
            "sheets": self.sheets,
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, self.path)


BACKFILL_CACHE = REPORT_DIR / "backfill-cache.json"


class _PdfIndex:
    """Every PDF under the roots, found by content.

    The file a verdict names is tried first, then any ``<sha256>.pdf`` store,
    and only then is every other PDF hashed -- once, and only when a reviewed
    PDF was renamed or is lost -- so the lookup is by content wherever it lives.
    """

    def __init__(self, cache: BackfillCache | None = None) -> None:
        self.by_name: dict[str, list[Path]] = {}
        self.stats: dict[Path, tuple[int, int]] = {}
        self.cache = cache or BackfillCache(None)

    def add(self, path: Path, size: int, mtime_ns: int) -> None:
        self.by_name.setdefault(path.name, []).append(path)
        self.stats[path] = (size, mtime_ns)

    def _digest(self, path: Path) -> str:
        return self.cache.digest(path, *self.stats[path])

    def find(self, sha: str, name: str) -> Path | None:
        likely = [*self.by_name.get(name, []), *self.by_name.get(f"{sha}.pdf", [])]
        everything = (path for paths in self.by_name.values() for path in paths)
        for path in (*likely, *everything):
            if self._digest(path) == sha:
                return path
        return None


def _walk(roots: Sequence[Path]) -> Iterable[tuple[Path, int, int]]:
    """Every JSON and PDF under ``roots``, with the size and mtime_ns of each.

    ``os.scandir`` carries both from the directory listing on Windows, so a
    warm rerun costs a directory walk, not a stat or a read per file.
    """
    pending = [root for root in roots if root.is_dir()]
    while pending:
        directory = pending.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                if entry.name not in _WALK_SKIP:
                    pending.append(Path(entry.path))
            elif entry.name.endswith((".json", ".pdf")):
                stat = entry.stat()
                yield Path(entry.path), stat.st_size, stat.st_mtime_ns


def worktree_roots(repo: Path = REPO_ROOT) -> list[Path]:
    """Where every worktree of this repository keeps its PDFs and review records."""
    listing = _git("worktree", "list", "--porcelain", repo=repo) or ""
    worktrees = [
        Path(line.removeprefix("worktree ").strip())
        for line in listing.splitlines()
        if line.startswith("worktree ")
    ]
    return [
        path
        for worktree in worktrees
        for path in (
            worktree / "cad" / "out" / "pdf",
            worktree / "cad" / "out" / "reports" / "machinist-review",
        )
        if path.is_dir()
    ]


def _registry_name(review: dict[str, Any], by_pdf: dict[str, str]) -> str:
    """The registry drawing a verdict reviewed, by its name or its PDF's file name."""
    if review.get("name") in DRAWINGS_BY_NAME:
        return review["name"]
    sources = review.get("sources") or []
    return by_pdf.get(Path(str(sources[0])).name, "") if len(sources) == 1 else ""


def _skip_reason(review: dict[str, Any], drawing: str) -> str:
    sources = review.get("sources") or []
    if len(sources) != 1 or not str(sources[0]).lower().endswith(".pdf"):
        return f"reviewed {len(sources)} files, not one PDF"
    if not drawing:
        return f"{review.get('name')!r} is not a registry drawing"
    if not review.get("passed"):
        return "SHIP with gating findings (passed: false)"
    if not review.get("blind"):
        return "not a blind review"
    return ""


def find_reviews(roots: Sequence[Path], cache: BackfillCache | None = None) -> Found:
    """Every machinist_review record under ``roots``: verdicts and quota refusals."""
    by_pdf = {spec.outputs["pdf"].name: name for name, spec in DRAWINGS_BY_NAME.items()}
    candidates: list[Candidate] = []
    objections: list[Candidate] = []
    refusals: list[tuple[Path, dict[str, Any]]] = []
    pdfs = _PdfIndex(cache)
    seen: set[Path] = set()
    for path, size, mtime_ns in _walk(roots):
        if path.suffix == ".pdf":
            pdfs.add(path, size, mtime_ns)
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if '"prompt_sha256"' not in text:
            continue
        try:
            review = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(review, dict) or "reviewer" not in review:
            continue
        verdict = review.get("verdict")
        if verdict is None:
            if review.get("name") and quota_evidence(review, path) is not None:
                refusals.append((path, review))
            continue
        drawing = _registry_name(review, by_pdf)
        skip = _skip_reason(review, drawing)
        if not review.get("passed") and not skip.startswith("reviewed"):
            objections.append(Candidate(path, review, drawing))
        if verdict.get("verdict") == "SHIP":
            candidates.append(Candidate(path, review, drawing, skip=skip))
    return Found(candidates, objections, refusals, pdfs)


class _Located(_References):
    """Reviewed PDFs where they were found, rather than in the ledger's store."""

    def __init__(self) -> None:
        super().__init__(Path())
        self.paths: dict[str, Path] = {}

    def path(self, sha: str) -> Path:
        return self.paths[sha]


def _locate(candidate: Candidate, pdfs: _PdfIndex) -> Path | None:
    """A file holding exactly the bytes the review saw, wherever it is now."""
    sha = candidate.review["source_sha256"][0]
    return pdfs.find(sha, Path(str(candidate.review["sources"][0])).name)


def _refusal_for(
    candidate: Candidate, drawing: str, author_family: str, found: Found
) -> dict[str, Any] | None:
    """A recorded quota refusal licensing this same-family review, if any."""
    for path, data in found.refusals:
        if data.get("name") not in (drawing, candidate.review.get("name")):
            continue
        try:
            refusal = quota_refusal(
                path, name=data["name"], author_family=author_family
            )
        except ValueError:
            continue
        if not refusal_problem(
            refusal,
            pdf_sha256=candidate.review["source_sha256"][0],
            reviewed_at=candidate.review["reviewed_at"],
        ):
            return refusal
    return None


class _Matcher:
    """Reviewed sheets against one drawing's current render, cached by content."""

    def __init__(self, current: Path, cache: BackfillCache) -> None:
        self.current = current
        stat = current.stat()
        self.current_sha = cache.digest(current, stat.st_size, stat.st_mtime_ns)
        self.cache = cache
        self._sheets: list[Sheet] | None = None

    def sheets(self) -> list[Sheet]:
        if self._sheets is None:
            self._sheets = read_sheets(self.current)
        return self._sheets

    def match(self, candidate: Candidate, pdf: Path) -> tuple[str, bool]:
        """(problem, exact): the drift the ledger rule finds, "" when none."""
        sha = candidate.review["source_sha256"][0]
        key = f"{sha}:{self.current_sha}"
        if key not in self.cache.comparisons:
            located = _Located()
            located.paths[sha] = pdf
            reviewed = [sheet_digest(sheet.ink) for sheet in located.get(sha)]
            self.cache.sheets[sha] = reviewed
            current = self.sheets()
            comparison = _compare({"pdf": sha, "sheets": reviewed}, current, located)
            exact = reviewed == [sheet_digest(sheet.ink) for sheet in current]
            self.cache.comparisons[key] = [comparison.problem, exact]
        problem, exact = self.cache.comparisons[key]
        return problem, exact


def _objection(candidate: Candidate, matcher: _Matcher, found: Found) -> str:
    """A failing verdict, newer than ``candidate``, that may have seen these sheets.

    A later FIX of the sheets now rendered overrides an earlier SHIP of the
    same sheets; so does one whose reviewed PDF is lost, since nothing shows
    it reviewed other sheets.
    """
    shipped = datetime.fromisoformat(candidate.review["reviewed_at"])
    for other in found.objections:
        if other.drawing != candidate.drawing:
            continue
        if datetime.fromisoformat(other.review["reviewed_at"]) <= shipped:
            continue
        what = f"{_reviewed(other.review)} {other.review['verdict']['verdict']}"
        pdf = _locate(other, found.pdfs)
        if pdf is None:
            return (
                f"newer {what} reviewed a PDF that is lost, so it may have seen "
                f"these sheets [{other.report.resolve().as_posix()}]"
            )
        if not matcher.match(other, pdf)[0]:
            return (
                f"newer {what} reviewed these sheets "
                f"[{other.report.resolve().as_posix()}]"
            )
    return ""


def _checkout_head(checkout: Path) -> str | None:
    return _git("rev-parse", "HEAD", repo=checkout)


def _current_pdf(name: str, checkout: Path | None) -> Path:
    pdf = DRAWINGS_BY_NAME[name].outputs["pdf"]
    return pdf if checkout is None else checkout / "cad" / "out" / "pdf" / pdf.name


def _try(
    candidate: Candidate,
    matcher: _Matcher,
    *,
    author: Author | ValueError,
    rulings: AuthorRulings,
    found: Found,
    checkout: Path,
    head: str | None,
    scratch: Path,
) -> Tried:
    """Match one located SHIP against the current sheets, then record it in ``scratch``."""
    review, drawing = candidate.review, candidate.drawing
    problem, exact = matcher.match(candidate, candidate.pdf)
    if problem:
        return Tried(candidate, Backfill.DRIFTED, problem)
    match = "exact" if exact else "within tolerance"
    matched = f"{_reviewed(review)} matches ({match})"
    objection = _objection(candidate, matcher, found)
    if objection:
        return Tried(candidate, Backfill.CONTRADICTED, f"{matched}; {objection}")
    if isinstance(author, ValueError):
        return Tried(candidate, Backfill.AUTHOR_UNKNOWN, f"{matched}; {author}")
    both_families = rulings.both_families(drawing)
    if both_families:  # counts for its reviewer's family, whoever the author was
        family = other_family(reviewer_family(review["reviewer"]))
        source, ruling = BOTH_FAMILIES, rulings.drawings[drawing]
    elif author.model is not None:
        family, source, ruling = model_family(author.model), "trailer", None
    else:
        family, source, ruling, unruled = ruled_family(drawing, author, rulings)
    if family is None:
        return Tried(candidate, Backfill.AUTHOR_UNKNOWN, f"{matched}; {unruled}")
    refusal = None
    if review_slot(review["reviewer"], family) == LAST_RESORT:
        refusal = _refusal_for(candidate, drawing, family, found)
    provenance = {
        "backfilled_from": candidate.report.resolve().as_posix(),
        "reviewed_pdf_found_at": candidate.pdf.resolve().as_posix(),
        "matched_checkout": checkout.resolve().as_posix(),
        "matched_checkout_head": head,
        "author_family_source": source,
        "match": match,
    }
    if ruling is not None:
        provenance["author_ruling"] = ruling
    if both_families:
        provenance["both_families"] = both_families
    if review.get("name") != drawing:
        provenance["reviewed_as"] = review.get("name")
    try:
        recorded = record_review(
            {**review, "name": drawing},
            candidate.pdf,
            author_family=family,
            provenance=provenance,
            refusal=refusal,
            ledger_path=scratch,
            repo=checkout,
            digests=matcher.cache.sheets.get(review["source_sha256"][0]),
            known_author=author,
            rulings=rulings,
        )
    except ValueError as exc:
        return Tried(candidate, Backfill.NOT_COUNTED, f"{matched}; {exc}")
    if not recorded.counts:
        return Tried(
            candidate,
            Backfill.NOT_COUNTED,
            f"{matched}; {recorded.slot}: {recorded.problem}",
        )
    return Tried(
        candidate,
        Backfill.INGESTED,
        f"{matched}; {recorded.slot}, author {family} ({source})",
        scratch,
    )


def backfill(
    roots: Sequence[Path],
    *,
    checkout: Path | None = None,
    exclude: Iterable[str] = (),
    rulings: AuthorRulings | None = None,
    apply: bool = False,
    ledger_path: Path = LEDGER_PATH,
    cache_path: Path | None = BACKFILL_CACHE,
) -> BackfillResult:
    """Try every SHIP on record under ``roots`` against the current sheets.

    A SHIP is ingested only when the exact PDF it reviewed still exists, its
    sheets match the ones rendered now under the ledger's own rule, and it
    counts under the reviewer-family rule: cross-family, or last resort with a
    recorded quota refusal.  ``checkout`` is the checkout whose ``cad/out/pdf``
    is current and whose draw-script commits name the authors (default: this
    one).  ``rulings`` give the author family where the draw script's last
    commit names no model.  Newest SHIP first; the first that
    counts is the one recorded.  Nothing is written unless ``apply``.
    """
    excluded = set(exclude)
    rulings = rulings or AuthorRulings()
    unknown = sorted((excluded | set(rulings.drawings)) - set(DRAWINGS_BY_NAME))
    if unknown:
        raise ValueError(f"unknown drawing names: {unknown}")
    repo = checkout or REPO_ROOT
    cache = BackfillCache(cache_path)
    with _telemetry.span("backfill.discover", roots=len(roots)) as span:
        found = find_reviews(roots, cache)
        span.set_attributes(
            {
                "verdicts": len(found.candidates) + len(found.objections),
                "pdfs": len(found.pdfs.stats),
            }
        )
    with _telemetry.span("backfill.locate") as span:
        by_drawing: dict[str, list[Candidate]] = {}
        for candidate in found.candidates:
            if candidate.skip:
                continue
            candidate.pdf = _locate(candidate, found.pdfs)
            by_drawing.setdefault(candidate.drawing, []).append(candidate)
        span.set_attributes({"hashed": cache.hashed})
    try:
        with _telemetry.span("backfill.match") as span:
            result = _backfill_drawings(
                by_drawing,
                found,
                cache,
                repo=repo,
                checkout=checkout,
                excluded=excluded,
                rulings=rulings,
                apply=apply,
                ledger_path=ledger_path,
            )
            span.set_attributes(
                {
                    "hashed": cache.hashed,
                    "comparisons": len(cache.comparisons),
                }
            )
    finally:
        cache.save()
    return result


def _backfill_drawings(
    by_drawing: dict[str, list[Candidate]],
    found: Found,
    cache: BackfillCache,
    *,
    repo: Path,
    checkout: Path | None,
    excluded: set[str],
    rulings: AuthorRulings,
    apply: bool,
    ledger_path: Path,
) -> BackfillResult:
    ledger = load_ledger(ledger_path)
    references = _References(sheets_dir(ledger_path))
    tried_names = sorted(set(by_drawing) - excluded)
    authors = draw_script_authors(tried_names, repo=repo) if tried_names else {}
    head = _checkout_head(repo)
    rows: list[BackfillRow] = []
    with tempfile.TemporaryDirectory(prefix="machinist-backfill-") as tmp:
        for name in DRAWINGS_BY_NAME:
            ships = sorted(
                by_drawing.get(name, []),
                key=lambda c: datetime.fromisoformat(c.review["reviewed_at"]),
                reverse=True,
            )
            if name in excluded:
                rows.append(
                    BackfillRow(
                        name,
                        Backfill.EXCLUDED,
                        f"{len(ships)} SHIPs on record, excluded by ruling",
                    )
                )
                continue
            pdf = _current_pdf(name, checkout)
            if not pdf.is_file():
                rows.append(
                    BackfillRow(name, Backfill.UNRENDERED, f"no rendered PDF at {pdf}")
                )
                continue
            status = drawing_status(
                name,
                ledger,
                references=references,
                pdf=pdf,
                both_families=rulings.both_families(name),
            )
            if status.state == State.OK:
                slot = status.via.split()[0]
                entry = ledger["drawings"][name][slot]
                recorded = Candidate(ledger_path, entry, name)
                objection = _objection(recorded, _Matcher(pdf, cache), found)
                if not objection:
                    rows.append(
                        BackfillRow(
                            name, Backfill.RECORDED, f"{status.via} {status.detail}"
                        )
                    )
                    continue
                # A newer failing verdict of these sheets withdraws the entry.
                dropped = "dropped from the ledger" if apply else "to drop (--apply)"
                rows.append(
                    BackfillRow(
                        name,
                        Backfill.CONTRADICTED,
                        f"recorded {slot} {status.detail}: {objection}; {dropped}",
                    )
                )
                if apply:
                    del ledger["drawings"][name][slot]
                    if not ledger["drawings"][name]:
                        del ledger["drawings"][name]
                    save_ledger(ledger, ledger_path)
                continue
            if status.missing:  # both families required: only a missing one helps
                ships = [
                    ship
                    for ship in ships
                    if REVIEWER_FAMILIES.get(ship.review["reviewer"]) in status.missing
                ]
            if not ships:
                detail = "no passing SHIP on record"
                if status.missing:
                    detail = f"{status.detail}; no passing SHIP from it on record"
                rows.append(BackfillRow(name, Backfill.NO_SHIP, detail))
                continue
            matcher = _Matcher(pdf, cache)
            tried: list[Tried] = []
            for index, candidate in enumerate(ships):
                if candidate.pdf is None:
                    sha = candidate.review["source_sha256"][0]
                    tried.append(
                        Tried(
                            candidate,
                            Backfill.PDF_LOST,
                            f"no file holds the reviewed {sha[:12]}",
                        )
                    )
                    continue
                attempt = _try(
                    candidate,
                    matcher,
                    author=authors[name],
                    rulings=rulings,
                    found=found,
                    checkout=repo,
                    head=head,
                    # its own directory: a scratch save prunes its sheets dir
                    scratch=Path(tmp) / name / str(index) / "ledger.json",
                )
                tried.append(attempt)
                if attempt.outcome == Backfill.INGESTED:
                    break
            best = min(tried, key=lambda t: _BACKFILL_ORDER.index(t.outcome))
            rows.append(
                BackfillRow(
                    name,
                    best.outcome,
                    f"{best.detail} [{best.candidate.report.resolve().as_posix()}]",
                    tried,
                )
            )
            if apply and best.outcome == Backfill.INGESTED:
                _adopt(best, name, ledger, ledger_path)
    skipped = [candidate for candidate in found.candidates if candidate.skip]
    return BackfillResult(repo, head, rows, skipped)


def _adopt(tried: Tried, name: str, ledger: dict[str, Any], ledger_path: Path) -> None:
    """Move a scratch-recorded entry, and the PDF it reviewed, into the ledger."""
    scratch = load_ledger(tried.scratch)["drawings"][name]
    ledger["drawings"].setdefault(name, {}).update(scratch)
    for entry in scratch.values():
        stored = sheets_dir(ledger_path) / f"{entry['pdf']}.pdf"
        stored.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sheets_dir(tried.scratch) / stored.name, stored)
    save_ledger(ledger, ledger_path)


_REVIEWER_FOR = {"claude": "codex", "gpt": "claude", "mimo": "claude"}


def fix_command(status: Status, author: Author | ValueError | None = None) -> str:
    """The commands that clear a failing drawing: render it if needed, then review it."""
    review = _review_command(status.name, author)
    if status.missing:  # both families required: one review per missing family
        tools = {family: tool for tool, family in REVIEWER_FAMILIES.items()}
        review = " and ".join(
            f"uv run cad/scripts/machinist_review.py {status.name} "
            f"--reviewer {tools[family]} --author-family {other_family(family)}"
            for family in status.missing
        )
    if status.state == State.UNRENDERED:
        return f"uv run python -m doit drawing:{status.name}, then {review}"
    return review


def _review_command(name: str, author: Author | ValueError | None) -> str:
    review = f"uv run cad/scripts/machinist_review.py {name}"
    script = DRAWINGS_BY_NAME[name].script_name
    if author is None:
        try:
            author = draw_script_author(name)
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
    check_cmd.add_argument("--outages", type=Path, default=OUTAGES_PATH)

    ingest_cmd = commands.add_parser("ingest", help="record an existing verdict JSON")
    ingest_cmd.add_argument("report", type=Path, help="machinist_review verdict JSON")
    ingest_cmd.add_argument("--author-family", required=True, choices=AUTHOR_FAMILIES)
    ingest_cmd.add_argument(
        "--author-model",
        help="cross-check for the model in the draw script's commit trailer",
    )
    evidence = ingest_cmd.add_mutually_exclusive_group()
    evidence.add_argument(
        "--quota-refusal",
        type=Path,
        help="the cross-family reviewer's quota-refused report",
    )
    evidence.add_argument(
        "--outage",
        metavar="ID",
        help="a named outage in --outages that directed this same-family review",
    )
    ingest_cmd.add_argument("--outages", type=Path, default=OUTAGES_PATH)
    ingest_cmd.add_argument(
        "--rebuttals",
        type=Path,
        help="cited user rulings answering every gating finding",
    )
    ingest_cmd.add_argument(
        "--pdf", type=Path, help="the reviewed PDF, if it moved since"
    )

    backfill_cmd = commands.add_parser(
        "backfill",
        help="ingest the SHIPs on record whose reviewed sheets still match",
    )
    backfill_cmd.add_argument(
        "roots",
        nargs="*",
        type=Path,
        help="directories searched for verdict JSONs and the PDFs they reviewed "
        "(e.g. C:/src/dt-logs)",
    )
    backfill_cmd.add_argument(
        "--worktrees",
        action="store_true",
        help="also search every worktree's cad/out/pdf and machinist-review reports",
    )
    backfill_cmd.add_argument(
        "--cache",
        type=Path,
        default=BACKFILL_CACHE,
        help="hashes and comparisons kept between runs",
    )
    backfill_cmd.add_argument(
        "--checkout",
        type=Path,
        help="checkout whose cad/out/pdf is current and whose draw-script commits "
        "name the authors (default: this one)",
    )
    backfill_cmd.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="NAME",
        help="a drawing a ruling keeps out of the backfill",
    )
    backfill_cmd.add_argument(
        "--author-rulings",
        type=Path,
        default=AUTHOR_RULINGS_PATH,
        help="recorded rulings on the author family of draw scripts whose last "
        "commit names no model",
    )
    backfill_cmd.add_argument(
        "--apply", action="store_true", help="write the ledger (default: dry run)"
    )
    backfill_cmd.add_argument(
        "--json", action="store_true", help="machine-readable rows"
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


def _print_backfill(result: BackfillResult, args: argparse.Namespace) -> None:
    rows = sorted(result.rows, key=lambda r: (_BACKFILL_ORDER.index(r.outcome), r.name))
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "name": row.name,
                        "outcome": str(row.outcome),
                        "detail": row.detail,
                        "tried": [
                            {
                                "report": t.candidate.report.as_posix(),
                                "reviewed_at": t.candidate.review["reviewed_at"],
                                "reviewer": t.candidate.review["reviewer"],
                                "outcome": str(t.outcome),
                                "detail": t.detail,
                            }
                            for t in row.tried
                        ],
                    }
                    for row in rows
                ],
                indent=2,
            )
        )
    else:
        for row in rows:
            print(f"{row.outcome:<16} {row.name:<32} {row.detail}")
        for candidate in result.skipped:
            print(
                f"{'skipped':<16} {candidate.review.get('name')!s:<32} "
                f"{candidate.skip} [{candidate.report.as_posix()}]"
            )
    counts = Counter(row.outcome for row in result.rows)
    mode = "applied" if args.apply else "dry run, nothing written"
    print(
        f"backfill ({mode}) against {result.checkout.as_posix()} at "
        f"{(result.head or '?')[:12]}; excluded: {', '.join(args.exclude) or 'none'}",
        file=sys.stderr,
    )
    print(
        ", ".join(f"{outcome}: {counts[outcome]}" for outcome in _BACKFILL_ORDER)
        + f"; {len(result.skipped)} SHIP records skipped",
        file=sys.stderr,
    )


def _run(args: argparse.Namespace) -> int:
    if args.command == "backfill":
        roots = [*args.roots, *(worktree_roots() if args.worktrees else [])]
        if not roots:
            raise ValueError("name the roots to search, or pass --worktrees")
        result = backfill(
            roots,
            cache_path=args.cache,
            checkout=args.checkout,
            exclude=args.exclude,
            rulings=load_author_rulings(args.author_rulings),
            apply=args.apply,
            ledger_path=args.ledger,
        )
        _print_backfill(result, args)
        return 0
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
            outage_id=args.outage,
            outages_path=args.outages,
        )
        counted = "" if recorded.counts else f", does NOT count: {recorded.problem}"
        print(
            f"recorded {recorded.name} as {recorded.slot} {recorded.status} "
            f"({len(recorded.sheets)} sheets{counted})"
        )
        # Recorded is not accepted: a row that does not count must not read as success.
        return 0 if recorded.counts else 1

    statuses = check(
        args.names,
        ledger_path=args.ledger,
        report_dir=args.report_dir,
        outages=load_outages(args.outages),
    )
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
    rulings = sum(n for key, n in via.items() if ACCEPTED_WITH_RULINGS in key)
    fallback = [s for s in statuses if s.via.startswith(OUTAGE_FALLBACK)]
    print(
        f"{len(statuses) - len(failing)}/{len(statuses)} drawings match an accepted review "
        f"({last_resort} via last resort, {rulings} accepted with rulings, "
        f"{len(fallback)} via outage fallback)",
        file=sys.stderr,
    )
    by_outage: dict[str, list[str]] = {}
    for status in fallback:
        outage_id = status.via.rsplit("(", 1)[1].rstrip(")")
        by_outage.setdefault(outage_id, []).append(status.name)
    outages = load_outages(args.outages)
    for outage_id, names in by_outage.items():
        print(
            f"on outage fallback, re-review cross-family when "
            f"{outages[outage_id]['reviewer']} recovers: {', '.join(names)}",
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
            why = (
                f"drift: {status.detail}"
                if status.state == State.DRIFT
                else status.state
            )
            print(f"  {status.name} ({why}): {fix}", file=sys.stderr)
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
