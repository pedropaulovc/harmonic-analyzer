"""Traveler-only machinist-review logic.

``machinist_review.py`` imports this module only when it reviews a
``--kind traveler`` package. It is not in dodo's ``_MACHINIST_REVIEW_MODULES``,
so an edit here never re-keys a part or assembly drawing review; a traveler
review leaf, when one exists, keys it instead.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Sequence

from _paths import CAD_ROOT
from machinist_exceptions import MachinistException, load_exceptions_file
from machinist_review_config import split_versioned_guidelines
from machinist_review_sheets_mcp import SheetStore

GUIDELINES_FILE = CAD_ROOT / "docs" / "traveler-guidelines.md"
PROCESS_ROOT = CAD_ROOT / "process"
# The shop's one standing-instructions page: everything common to every
# traveler, rendered once from ``cad/process/shop/`` and shipped per release as
# ``travelers/shop-standing-instructions.pdf``. A traveler review reads it so
# every reviewer and the judge share one definition of the shop's common sense.
STANDING_HTML = (
    CAD_ROOT / "out" / "travelers" / "shop-standing-instructions"
    / "shop-standing-instructions.html"
)
STANDING_HEADING = (
    "SHOP STANDING INSTRUCTIONS (common sense in this shop: the traveler must "
    "not repeat or re-word any of it)"
)


def split_guidelines(text: str) -> tuple[int, str]:
    """``(major_version, body)`` of ``cad/docs/traveler-guidelines.md``."""
    return split_versioned_guidelines(text, label="traveler guidelines")


def guidelines_body() -> str:
    """The traveler guidelines without their frontmatter."""
    return split_guidelines(GUIDELINES_FILE.read_text(encoding="utf-8"))[1].rstrip()


def load_exceptions(name: str) -> tuple[MachinistException, ...]:
    """A traveler's owner-declared exceptions, beside its process plan at
    ``cad/process/<underscore_stem>/machinist_exceptions.yaml``, so a traveler
    exception never re-keys the part drawing's review."""
    stem = name.replace("-", "_")
    return load_exceptions_file(PROCESS_ROOT / stem / "machinist_exceptions.yaml", stem)


# Block elements end a line of text; inside a table cell they separate parts
# of the cell with " / " instead.
_BLOCKS = frozenset({
    "p", "div", "section", "figure", "figcaption", "dt", "dd", "li",
    "h3", "h4", "h5", "h6", "br",
})


class _Extractor(HTMLParser):
    _SKIP = {"style", "script", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self._lines: list[str] = []
        self._buf: list[str] = []
        self._in_tr = False
        self._in_cell = False
        self._cells: list[str] = []
        self._in_heading = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP:
            self._skip += 1
            return
        if self._skip:
            return
        if tag == "img":
            alt = (dict(attrs).get("alt") or "").strip()
            if alt:
                self._flush()
                self._lines.append(f"[Diagram alt: {alt}]")
        elif tag == "tr":
            self._flush()
            self._in_tr = True
            self._cells = []
        elif tag in ("th", "td") and self._in_tr:
            self._in_cell = True
            self._buf = []
        elif tag == "span" and self._in_heading and self._buf:
            self._buf.append(" — ")
        elif tag in ("h1", "h2"):
            self._flush()
            self._in_heading = True
        elif tag in _BLOCKS:
            self._separate()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP:
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag in ("th", "td") and self._in_cell:
            cell = re.sub(r"\s+", " ", "".join(self._buf)).strip(" /")
            if cell:
                self._cells.append(cell)
            self._buf = []
            self._in_cell = False
        elif tag == "tr" and self._in_tr:
            if self._cells:
                self._lines.append(" | ".join(self._cells))
            self._in_tr = False
            self._cells = []
        elif tag in ("h1", "h2"):
            self._in_heading = False
            self._flush()
        elif tag in _BLOCKS:
            self._separate()

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._buf.append(data)

    def _separate(self) -> None:
        if not self._in_cell:
            self._flush()
            return
        text = "".join(self._buf).strip()
        if text and not text.endswith("/"):
            self._buf.append(" / ")

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        self._buf = []
        if text:
            self._lines.append(text)

    def result(self) -> str:
        self._flush()
        return "\n".join(self._lines)


def html_text(html: str) -> str:
    """Structured text of a prechips HTML traveler: one line per heading,
    block or table row, cells joined by `` | `` and blocks within a cell by
    `` / ``. Headless Chromium PDF printing splits kerning pairs and SVG labels
    in the PDF text layer (``ToTools``, ``off ff``, ``Z .1 165``); this gives
    reviewers the source text without exposing authoring files."""
    parser = _Extractor()
    parser.feed(html)
    return parser.result()


def standing_missing(path: Path) -> str:
    """Why a traveler review cannot run without the standing page at ``path``."""
    return (
        f"shop standing instructions page missing: {path}; a traveler review "
        "reads it as common sense the traveler must not repeat. Render it with "
        "cad/scripts/prechips_traveler.py (the shop standing render, "
        "`prechips standing cad/process/shop`), or pass --standing-html."
    )


def standing_section(html: str) -> str:
    """The standing page's text as the reviewers and the judge read it,
    extracted exactly as a traveler HTML's text is."""
    text = html_text(html)
    if not text:
        raise ValueError("shop standing instructions page has no text")
    return (
        f"\n{STANDING_HEADING}\n"
        "Text of the shop's one standing-instructions page, printed once and "
        "shipped beside every traveler (travelers/shop-standing-instructions.pdf), "
        "one line per block or table row.\n"
        f"{text}\n"
    )


def document_roles(
    sources: Sequence[Path], companion_count: int, sheet_count: int
) -> str:
    """Which sheets are the traveler and which the companion part drawing:
    the last ``companion_count`` sources, as the CLI's ``--companion-pdf``
    marks them."""
    if companion_count <= 0:
        return ""
    with SheetStore(tuple(sources[:-companion_count])) as traveler:
        traveler_sheets = traveler.sheet_count
    return (
        "\nDOCUMENT ROLES\n"
        f"- Sheets 1..{traveler_sheets}: process traveler under review.\n"
        f"- Sheets {traveler_sheets + 1}..{sheet_count}: companion part drawing "
        "(reference specification authority ONLY — check traveler completeness "
        "and agreement against it under rules T1, T2 and T14, and NEVER file "
        "findings against the part drawing's own tolerances, notes or layout).\n"
    )
