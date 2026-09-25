r"""Durable record of which drawing sheets a machinist review accepted.

``machinist_review.py`` writes its verdicts under the gitignored
``cad/out/reports/machinist-review/`` of whichever worktree ran it, keyed by
the reviewed PDF's sha256.  Those bytes churn on every render (timestamps, the
revision stamped into the title block), so neither the file nor the hash can
say, at integration or release time, whether the sheet now shipping is the
sheet a reviewer passed.  This module is that link.

* **Ledger** -- ``cad/reviews/machinist-ledger.json`` (tracked).  One entry per
  registry drawing, holding its last passing cross-family verdict and the
  content of every reviewed sheet.  A passing same-family verdict goes to a
  separate ``last_resort`` slot.  It counts only as the policy's last resort
  (``cad/docs/drawing-simplicity-policy.md``, "The gate"): the cross-family
  reviewer refused on quota, recorded as evidence, and the reviewer is a tier
  above an Opus/Sol author (or Fable/Astra at high effort for a Fable/Astra
  author).  Anything else is recorded and reported but never accepted.
* **Sheet content** -- each PDF page rendered at the review's 300 dpi,
  grayscale, thresholded to 1-bit ink, with the per-build revision text blanked
  (the REV cell value and the ``BUILD <rev>`` line, located from the PDF's own
  text layer).  The ledger keeps the sha256 of that raster and the raster itself
  (``cad/reviews/sheets/<sha256>.png``).
* **Match** -- a current sheet matches a reviewed one when the digests are
  equal or, failing that, when every ink pixel of each lies within
  ``MATCH_TOLERANCE_PX`` of ink in the other.  Re-rendering an unchanged drawing
  moves a few antialiased edge pixels (measured: up to ~30 px, and whole views
  shifted by 1-2 px), which an exact digest reads as a change; a one-character
  note edit leaves ink more than 2 px from anything in the other sheet
  (measured: "." -> "," leaves 4 px, "5" -> "6" leaves 105 px).
* **Drift check** -- ``check`` lists every drawing whose current sheets match
  neither its cross-family entry nor a counting last-resort entry.

No build task reads the ledger, so recording a review never re-keys a build.

Usage (SolidWorks-free)::

    uv run cad/scripts/machinist_ledger.py check                 # every registry drawing
    uv run cad/scripts/machinist_ledger.py check crank_pinion_pin
    uv run cad/scripts/machinist_ledger.py ingest <verdict.json> --author-family gpt
    uv run cad/scripts/machinist_ledger.py ingest <fable.json> --author-family claude \
        --author-model claude-opus-5-5 --quota-refusal <codex-refused.json>
    uv run cad/scripts/machinist_ledger.py fingerprint <drawing.pdf>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import threading
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from _drawing_registry import CAD_ROOT, DRAWINGS, DRAWINGS_BY_NAME  # noqa: E402

REPO_ROOT = CAD_ROOT.parent
LEDGER_PATH = CAD_ROOT / "reviews" / "machinist-ledger.json"
LEDGER_VERSION = 1

FINGERPRINT_DPI = 300
INK_THRESHOLD = 128  # grayscale value below which a pixel is ink
MASK_PAD_PT = 2.0  # anti-aliasing margin around a masked text run
MATCH_TOLERANCE_PX = 2  # 0.17 mm at 300 dpi
FINGERPRINT_ALGORITHM = "sheet-1bit-sha256-v1"

# Text stamped per build rather than per design: the REV cell value (a text line
# of its own) and the "BUILD <rev>" token under DO NOT SCALE DRAWING, which the
# PDF text layer may join onto that line.  Older builds suffix "-b<number>".  A
# revision-looking token anywhere else (e.g. inside a note) stays in the sheet.
_REVISION = r"(?:v\d+|DEV)(?:-b\d+)?"
_REV_CELL = re.compile(rf"^{_REVISION}$")
_BUILD_STAMP = re.compile(rf"\bBUILD\s+{_REVISION}\b")

# Reviewer CLI -> model family.  The author family is always named by the
# caller, never inferred from commit trailers.
REVIEWER_FAMILIES = {"claude": "claude", "codex": "gpt"}
AUTHOR_FAMILIES = ("claude", "gpt", "mimo")
FINDING_KEYS = ("blockers", "over_specification", "clarity", "minor")

CROSS_FAMILY = "cross_family"
LAST_RESORT = "last_resort"

# The user's standing last-resort rule, by model tier: work by a workhorse
# model (Opus, Sol) is reviewed by a top model (Fable, Astra); work by a top
# model is reviewed by a top model at high reasoning effort.
_TIERS = {"opus": "workhorse", "sol": "workhorse", "fable": "top", "astra": "top"}
_HIGH_EFFORTS = ("high", "xhigh", "max")
# What the reviewer CLIs print when an account is out of quota.
_QUOTA_REFUSAL = re.compile(r"hit your usage limit|usage[_ ]limit[_ ]reached", re.IGNORECASE)

# PDFium's native API is process-global and not thread-safe.
_PDFIUM_LOCK = threading.Lock()


# --- sheet content -----------------------------------------------------------------


def _volatile_spans(text: str) -> list[tuple[int, int]]:
    """(start, length) character spans of the per-build revision text."""
    spans = [(match.start(), len(match.group())) for match in _BUILD_STAMP.finditer(text)]
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if _REV_CELL.match(stripped):
            spans.append((offset + line.index(stripped), len(stripped)))
        offset += len(line)
    return spans


def _volatile_boxes(textpage: Any) -> list[tuple[float, float, float, float]]:
    """PDF-space boxes (left, bottom, right, top) of the per-build revision text."""
    boxes: list[tuple[float, float, float, float]] = []
    for start, length in _volatile_spans(textpage.get_text_range()):
        for index in range(textpage.count_rects(start, length)):
            boxes.append(textpage.get_rect(index))
    return boxes


def masked_sheets(pdf: Path, *, dpi: int = FINGERPRINT_DPI) -> list[Any]:
    """Every page of ``pdf`` as a boolean ink array with the revision text blanked."""
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
                        boxes = _volatile_boxes(textpage)
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
                    y1 = min(height, int((page_height - bottom + MASK_PAD_PT) * scale) + 1)
                    gray[y0:y1, x0:x1] = 255
                sheets.append(gray < INK_THRESHOLD)
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
    return [sheet_digest(ink) for ink in masked_sheets(pdf)]


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


def residual(reference: Any, current: Any, *, radius: int = MATCH_TOLERANCE_PX) -> int:
    """Ink pixels of either sheet farther than ``radius`` px from ink in the other."""
    if reference.shape != current.shape:
        return -1
    lost = reference & ~_dilate(current, radius)
    added = current & ~_dilate(reference, radius)
    return int(lost.sum() + added.sum())


def save_raster(ink: Any, path: Path) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(~ink).convert("1").save(path, optimize=True)


def load_raster(path: Path) -> Any:
    import numpy as np
    from PIL import Image

    with Image.open(path) as image:
        return ~np.array(image.convert("1"))


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
        },
        "drawings": {},
    }


def load_ledger(path: Path = LEDGER_PATH) -> dict[str, Any]:
    if not path.is_file():
        return empty_ledger()
    ledger = json.loads(path.read_text(encoding="utf-8"))
    if ledger.get("version") != LEDGER_VERSION:
        raise ValueError(f"{path}: ledger version {ledger.get('version')!r} != {LEDGER_VERSION}")
    if ledger.get("fingerprint") != empty_ledger()["fingerprint"]:
        raise ValueError(
            f"{path}: recorded with fingerprint settings {ledger.get('fingerprint')}, "
            f"this checkout uses {empty_ledger()['fingerprint']}"
        )
    return ledger


def save_ledger(ledger: dict[str, Any], path: Path = LEDGER_PATH) -> None:
    """Write the ledger and drop reference rasters no entry points at any more."""
    ledger["drawings"] = dict(sorted(ledger["drawings"].items()))
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(ledger, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    referenced = {
        digest
        for slots in ledger["drawings"].values()
        for entry in slots.values()
        for digest in entry["sheets"]
    }
    directory = sheets_dir(path)
    if directory.is_dir():
        for raster in directory.glob("*.png"):
            if raster.stem not in referenced:
                raster.unlink()


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
        raise ValueError(f"unknown author family {author_family!r}; expected {AUTHOR_FAMILIES}")
    if reviewer_family(reviewer) == author_family:
        return LAST_RESORT
    return CROSS_FAMILY


def _git(*args: str) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, check=False
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def git_state() -> dict[str, Any]:
    """HEAD and dirtiness of the checkout recording a review (provenance only)."""
    status = _git("status", "--porcelain", "--untracked-files=no")
    return {"head": _git("rev-parse", "HEAD"), "dirty": None if status is None else bool(status)}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def model_tier(model: str) -> str | None:
    lowered = model.lower()
    return next((tier for key, tier in _TIERS.items() if key in lowered), None)


def last_resort_tier_problem(author_model: str, reviewer_model: str, effort: str) -> str | None:
    """Why a same-family reviewer misses the last-resort tier rule, or None."""
    author, reviewer = model_tier(author_model), model_tier(reviewer_model)
    if author is None:
        return f"author model {author_model!r} has no last-resort tier (Opus, Sol, Fable, Astra)"
    if reviewer != "top":
        return f"reviewer {reviewer_model!r} is not a Fable/Astra model"
    if author == "top" and effort not in _HIGH_EFFORTS:
        return f"a {author_model} author needs the reviewer at high effort, not {effort!r}"
    return None


def quota_refusal(report: Path, *, name: str, author_family: str) -> dict[str, Any]:
    """Evidence that the cross-family reviewer refused ``name`` on quota.

    ``report`` is that reviewer's machinist_review JSON for the same drawing: no
    verdict, and a usage-limit refusal in its recorded error, event stream or
    attempt output.
    """
    data = json.loads(report.read_text(encoding="utf-8"))
    if data.get("name") != name:
        raise ValueError(f"{report}: refusal is for {data.get('name')!r}, not {name!r}")
    if reviewer_family(data["reviewer"]) == author_family:
        raise ValueError(f"{report}: refusal must come from the cross-family reviewer")
    if data.get("verdict") is not None:
        raise ValueError(f"{report}: that review returned a verdict; it was not refused")
    attempts = (data.get("extra") or {}).get("evidence", {}).get("attempts", [])
    outputs = [data.get("events_file")]
    outputs += [attempt.get(key) for attempt in attempts for key in ("stdout_file", "stderr_file")]
    texts = [(report, data.get("error") or "")]
    texts += [
        (Path(path), Path(path).read_text(encoding="utf-8", errors="replace"))
        for path in outputs
        if path and Path(path).is_file()
    ]
    for source, text in texts:
        match = _QUOTA_REFUSAL.search(text)
        if match is None:
            continue
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        return {
            "report": report.resolve().as_posix(),
            "evidence_file": source.resolve().as_posix(),
            "reviewer": data["reviewer"],
            "model": data["model"],
            "refused_at": data["reviewed_at"],
            "message": text[line_start : line_end if line_end >= 0 else None].strip()[:300],
        }
    raise ValueError(f"{report}: no usage-limit refusal in its error, events or attempt output")


@dataclass(frozen=True)
class Recorded:
    name: str
    slot: str
    sheets: tuple[str, ...]
    counts: bool


def record_review(
    review: dict[str, Any],
    pdf: Path,
    *,
    author_family: str,
    provenance: dict[str, Any],
    author_model: str | None = None,
    refusal: dict[str, Any] | None = None,
    ledger_path: Path = LEDGER_PATH,
) -> Recorded:
    """Enter one passing review in its slot, replacing that slot's previous entry.

    ``review`` is a machinist_review record (``Review`` as a dict).  Only a
    passing, blind review of one registry drawing's PDF is recorded, and ``pdf``
    must still hash to the reviewed ``source_sha256``: a re-rendered file is not
    the sheet the reviewer saw.  A same-family review lands in ``last_resort``
    and counts only with a quota ``refusal`` and the tier rule met.
    """
    name = review["name"]
    if name not in DRAWINGS_BY_NAME:
        raise ValueError(f"{name}: not a registry drawing; only registry PDFs enter the ledger")
    if not (review.get("passed") and review.get("blind")):
        raise ValueError(f"{name}: only a passing blind review is recorded")
    if len(review["source_sha256"]) != 1:
        raise ValueError(f"{name}: expected one reviewed PDF, got {len(review['source_sha256'])}")
    actual = sha256_file(pdf)
    if actual != review["source_sha256"][0]:
        raise ValueError(
            f"{pdf}: sha256 {actual[:12]} is not the reviewed {review['source_sha256'][0][:12]}"
        )
    slot = review_slot(review["reviewer"], author_family)
    problem = None
    if slot == LAST_RESORT:
        if refusal is None:
            problem = "no recorded quota refusal by the cross-family reviewer"
        elif author_model is None:
            problem = "author model not recorded"
        else:
            problem = last_resort_tier_problem(author_model, review["model"], review["effort"])
    sheets = masked_sheets(pdf)
    if len(sheets) != review["sheet_count"]:
        raise ValueError(
            f"{name}: {pdf} has {len(sheets)} sheets, the review saw {review['sheet_count']}"
        )
    digests = [sheet_digest(ink) for ink in sheets]
    for digest, ink in zip(digests, sheets):
        save_raster(ink, sheets_dir(ledger_path) / f"{digest}.png")
    verdict = review["verdict"]
    entry: dict[str, Any] = {
        "sheets": digests,
        "counts": problem is None,
        "reviewer": review["reviewer"],
        "reviewer_family": reviewer_family(review["reviewer"]),
        "model": review["model"],
        "effort": review["effort"],
        "author_family": author_family,
        "author_model": author_model,
        "prompt_sha256": review["prompt_sha256"],
        "reviewed_at": review["reviewed_at"],
        "source_sha256": review["source_sha256"][0],
        "verdict": verdict["verdict"],
        "summary": verdict["summary"],
        "findings": {key: len(verdict[key]) for key in FINDING_KEYS},
        "minor": [f"{item['where']}: {item['issue']}" for item in verdict["minor"]],
        "provenance": provenance,
    }
    if slot == LAST_RESORT:
        entry["quota_refusal"] = refusal
        entry["not_counted_because"] = problem
    ledger = load_ledger(ledger_path)
    ledger["drawings"].setdefault(name, {})[slot] = entry
    save_ledger(ledger, ledger_path)
    return Recorded(name=name, slot=slot, sheets=tuple(digests), counts=problem is None)


def ingest(
    report: Path,
    *,
    author_family: str,
    author_model: str | None = None,
    refusal_report: Path | None = None,
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
        refusal = quota_refusal(refusal_report, name=review["name"], author_family=author_family)
    return record_review(
        review,
        pdf or Path(sources[0]),
        author_family=author_family,
        author_model=author_model,
        refusal=refusal,
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
    last_resort: str  # "-" (none recorded) | "matches" | "drift"


def _compare(entry: dict[str, Any], current: Sequence[Any], raster_dir: Path) -> str:
    """Empty when ``current`` matches the reviewed sheets, else why not."""
    if len(entry["sheets"]) != len(current):
        return f"{len(entry['sheets'])} sheets reviewed, {len(current)} now"
    changed = []
    for index, (digest, ink) in enumerate(zip(entry["sheets"], current), start=1):
        if digest == sheet_digest(ink):
            continue
        reference = raster_dir / f"{digest}.png"
        if not reference.is_file():
            changed.append(f"{index} (reference raster missing)")
            continue
        pixels = residual(load_raster(reference), ink)
        if pixels < 0:
            changed.append(f"{index} (sheet size changed)")
        elif pixels:
            changed.append(f"{index} ({pixels} px)")
    return f"sheet {', '.join(changed)} changed" if changed else ""


def _reviewed(entry: dict[str, Any]) -> str:
    return f"{entry['reviewer']}/{entry['model']} {entry['reviewed_at']}"


def drawing_status(
    name: str, ledger: dict[str, Any], *, raster_dir: Path, pdf: Path | None = None
) -> Status:
    """Where ``name``'s current sheets stand against its recorded reviews.

    ``ok`` needs a matching cross-family entry, or a matching last-resort entry
    that counts under the policy's last-resort rule.
    """
    pdf = pdf or DRAWINGS_BY_NAME[name].outputs["pdf"]
    if not pdf.is_file():
        return Status(name, State.UNRENDERED, f"no rendered PDF at {pdf}", "-")
    current = masked_sheets(pdf)
    entry = ledger["drawings"].get(name, {})
    last = entry.get(LAST_RESORT)
    last_resort = "-"
    if last is not None:
        last_resort = "drift" if _compare(last, current, raster_dir) else "matches"
    cross = entry.get(CROSS_FAMILY)
    difference = "" if cross is None else _compare(cross, current, raster_dir)
    if cross is not None and not difference:
        return Status(name, State.OK, _reviewed(cross), last_resort)
    if last_resort == "matches" and last["counts"]:
        return Status(name, State.OK, f"last-resort {_reviewed(last)}", last_resort)
    if cross is not None:
        return Status(name, State.DRIFT, f"{difference} since {_reviewed(cross)}", last_resort)
    if last_resort == "matches":
        reason = f"last-resort SHIP does not count: {last['not_counted_because']}"
        return Status(name, State.UNREVIEWED, reason, last_resort)
    return Status(name, State.UNREVIEWED, "no cross-family SHIP recorded", last_resort)


def check(names: Iterable[str] = (), *, ledger_path: Path = LEDGER_PATH) -> list[Status]:
    ledger = load_ledger(ledger_path)
    selected = list(names) or [spec.name for spec in DRAWINGS]
    unknown = [name for name in selected if name not in DRAWINGS_BY_NAME]
    if unknown:
        raise ValueError(f"unknown drawing names: {unknown}")
    raster_dir = sheets_dir(ledger_path)
    return [drawing_status(name, ledger, raster_dir=raster_dir) for name in selected]


# --- CLI ---------------------------------------------------------------------------


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ledger", type=Path, default=LEDGER_PATH)
    commands = parser.add_subparsers(dest="command", required=True)

    check_cmd = commands.add_parser(
        "check", help="list drawings whose sheets lack a matching, counting SHIP"
    )
    check_cmd.add_argument("names", nargs="*", help="registry drawing names (default: all)")
    check_cmd.add_argument(
        "--allow-unrendered", action="store_true", help="do not fail on a drawing with no PDF"
    )
    check_cmd.add_argument("--json", action="store_true", help="machine-readable statuses")

    ingest_cmd = commands.add_parser("ingest", help="record an existing passing verdict JSON")
    ingest_cmd.add_argument("report", type=Path, help="machinist_review verdict JSON")
    ingest_cmd.add_argument("--author-family", required=True, choices=AUTHOR_FAMILIES)
    ingest_cmd.add_argument("--author-model", help="model that authored the drawing script")
    ingest_cmd.add_argument(
        "--quota-refusal", type=Path, help="the cross-family reviewer's quota-refused report"
    )
    ingest_cmd.add_argument("--pdf", type=Path, help="the reviewed PDF, if it moved since")

    fingerprint_cmd = commands.add_parser("fingerprint", help="print a PDF's sheet digests")
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
            pdf=args.pdf,
            ledger_path=args.ledger,
        )
        counted = "" if recorded.counts else ", does NOT count"
        print(
            f"recorded {recorded.name} as {recorded.slot} "
            f"({len(recorded.sheets)} sheets{counted})"
        )
        return 0

    statuses = check(args.names, ledger_path=args.ledger)
    if args.json:
        rows = [{**status.__dict__, "state": str(status.state)} for status in statuses]
        print(json.dumps(rows, indent=2))
    else:
        for status in statuses:
            print(
                f"{status.state:<10} {status.name:<32} "
                f"last-resort={status.last_resort:<7} {status.detail}"
            )
    accepted = {State.OK, State.UNRENDERED} if args.allow_unrendered else {State.OK}
    failing = [status for status in statuses if status.state not in accepted]
    print(
        f"{len(statuses) - len(failing)}/{len(statuses)} drawings match a counting SHIP",
        file=sys.stderr,
    )
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
