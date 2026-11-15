"""Carry a machinist-review verdict to a sheet that prints what was reviewed.

A review key moves whenever the sheet's ink moves (``_pdf_ink_digest``): a
release revision stamp (``BUILD v49`` to ``BUILD v50``) or a note that the
seat's drawing window placed one pixel away changes no line of the drawing a
machinist reads, yet would roll the reviewers again (#2714). On such a miss,
the leaf compares the PDF with the PDFs already reviewed for that drawing
under the same non-PDF review inputs and, when one prints the same sheet under
the release drawing diff's page rule (``_drawing_diff.compare_drawings``),
reuses that review's verdict, ``SHIP`` or ``FIX``, recording where it came
from and what differed.

The rule is the owner's ruling of 2026-11-14 on #2714 (recorded at
issuecomment-6890086285): carry verdicts across the revision stamp and small
moves at the tolerance the repo's PDF diff already uses. That comparator's
documented limits therefore apply to verdict reuse: an edit of 1 px or less
at 144 dpi, or 68 grey levels or less, with no character change, carries the
earlier verdict unreviewed (measurements: issuecomment-6889445934).

The index is one create-only sidecar per freshly reviewed PDF::

    machinist-review/epoch-<epoch>/<stem>/<context>/<review key>.pdf

``context`` is the cache key of every review input but the PDF, so a prompt,
review-code, ``uv.lock`` or exception-file change finds no entry and the sheet
is reviewed again. The blob holds the reviewed PDF's bytes; its name is the
key its verdict is stored under. Writers never update a blob, so concurrent
builds cannot corrupt an entry, and a reader lists one drawing's prefix,
never the container. A carried verdict is never indexed: every carry is
measured against a PDF the reviewers saw, so differences cannot accumulate
across carries.
"""

from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import _artifact_cache as _cache

PREFIX = "machinist-review"
# Newest reviewed PDFs compared on one miss: each costs a download and one
# 144 dpi render (the sheet itself is rendered once), and only a key miss
# pays it.
CANDIDATES = 8
# Written into a carried leaf's report directory; its presence also keeps the
# leaf's PDF out of the index. A subdirectory, because machinist_review.py
# reads every top-level ``*.json`` of a report directory as a review.
CARRIED_FILE = "carry/provenance.json"


@dataclass(frozen=True)
class Carry:
    review_key: str
    pdf_sha256: str
    comparison: dict[str, Any]


def _prefix(stem: str, context: str) -> str:
    return f"{PREFIX}/{stem}/{context}/"


def entry_name(stem: str, context: str, review_key: str) -> str:
    return f"{_prefix(stem, context)}{review_key}.pdf"


def index(stem: str, context: str, review_key: str, pdf: Path) -> str:
    """Record ``pdf`` as reviewed under ``review_key``: create-only, so a
    second writer of the same entry leaves the first one's bytes. Every cache
    hit offers its PDF again, so an entry already listed is not uploaded.
    Returns :func:`_artifact_cache.publish_sidecar`'s outcome, or ``exists``."""
    if not _cache.writable():
        return "skip" if _cache.enabled() else "off"
    name = entry_name(stem, context, review_key)
    if any(listed == name for listed, _modified in _cache.list_sidecars(name)):
        return "exists"
    return _cache.publish_sidecar(name, pdf.read_bytes())


def find(stem: str, context: str, pdf: Path) -> Carry | None:
    """The newest reviewed PDF of ``stem`` under ``context`` that ``pdf``
    prints the same sheet as, or None. An entry that cannot be read or
    compared is skipped, never matched; a sheet that cannot be rendered, or
    scratch space that cannot be written, matches nothing."""
    import _drawing_diff

    entries = _cache.list_sidecars(_prefix(stem, context))[:CANDIDATES]
    if not entries:
        return None
    try:
        sheet = _drawing_diff.render_pages(pdf)
    except (OSError, ValueError):
        return None
    try:
        with tempfile.TemporaryDirectory(
            prefix="review-carry-", ignore_cleanup_errors=True
        ) as scratch:
            for number, (name, _modified) in enumerate(entries):
                review_key = name.rsplit("/", 1)[-1].removesuffix(".pdf")
                data = _cache.fetch_sidecar(name)
                if data is None:
                    continue
                reviewed = Path(scratch) / f"{number}.pdf"
                try:
                    reviewed.write_bytes(data)
                    comparison = _drawing_diff.compare_pages(
                        _drawing_diff.render_pages(reviewed), sheet
                    )
                except (OSError, ValueError):
                    continue
                if comparison["unchanged"]:
                    return Carry(
                        review_key, hashlib.sha256(data).hexdigest(), comparison
                    )
    except OSError:
        return None
    return None


def provenance(carry: Carry, aggregate: dict[str, Any]) -> dict[str, Any]:
    """The report record of a carried verdict."""
    import _drawing_diff

    return {
        "carried_from": {
            "review_key": carry.review_key,
            "pdf_sha256": carry.pdf_sha256,
            "verdict": aggregate["verdict"],
            "reviewed_at": aggregate.get("reviewed_at"),
            "reviewed_source_sha256": aggregate.get("source_sha256"),
        },
        "rule": _drawing_diff.COMPARISON_RULE,
        "difference": carry.comparison["pages"],
    }
