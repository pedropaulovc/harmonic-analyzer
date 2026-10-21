"""Offline, deterministic red/blue drawing-PDF overlays for release assets.

Only geometrically identified BUILD/REV *values* in the template's lower-right
216 x 66 mm title block are normalized. No title-block rectangle is erased.
The 144 dpi comparison matches ink in both directions within one pixel along
each axis and 68 grayscale levels. There is no minimum changed area: isolated
high-contrast additions/removals survive. Printed-character inventory changes
disable both tolerances. Low-contrast edits, one-pixel edge movements/thickness
changes, gaps/bridges up to two pixels and dense-ink pattern changes can be
omitted. This is a bounded visual comparison, not semantic CAD equivalence.

PDFs pair by the current identity map composed with sealed historical identities,
within their original relative directory. Each parent-specific vendor clone gets
its own comparison against the same prior purchased drawing where applicable.
Renames are reported separately; drawing ink, including changed identity labels,
is still compared normally.

Run from the repository root, without SolidWorks::

    uv run python cad/scripts/_drawing_diff.py NEW_PDF_DIR DIFF.zip \
        --old-pdf-dir OLD_PDF_DIR --old-label v42 --new-label v43

Omit --old-pdf-dir for a first release. Extract the ZIP and open index.html.
"""

from __future__ import annotations

import argparse
import ctypes
import html
import importlib.util
import io
import json
import os
import re
import tempfile
from collections import defaultdict
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw
from PIL import Image, ImageFilter

DPI = 144
SCALE = DPI / 72.0
# Calibrated against v42/v43 knob-cup p1 and cone-gear p18. A one-pixel
# neighborhood needs 68 levels; two pixels still need 52 and hide more geometry.
ANTIALIAS_TOLERANCE = 68
SPATIAL_TOLERANCE_PIXELS = 1
# Both project templates have the same block width and height; portrait moves
# its left edge. See cad/templates/README.md and _drawing_registry.py.
TITLE_BLOCK_WIDTH_PT = 216.0 / 25.4 * 72.0
TITLE_BLOCK_HEIGHT_PT = 66.0 / 25.4 * 72.0
_VERSION = re.compile(r"(?<![\w.-])v[0-9]+(?:-dirty)?(?![\w.-])")
_LABEL = re.compile(r"\b(?:BUILD|REV)\b")


@dataclass(frozen=True)
class _Glyph:
    char: str
    box: tuple[int, int, int, int]  # device pixels, left/top/right/bottom


@dataclass
class _Raster:
    gray: np.ndarray
    size_points: tuple[float, float]
    stamp_boxes: list[tuple[int, int, int, int]]
    text: tuple[str, ...]


def _box(glyphs: list[_Glyph]) -> tuple[int, int, int, int]:
    return (
        min(g.box[0] for g in glyphs),
        min(g.box[1] for g in glyphs),
        max(g.box[2] for g in glyphs),
        max(g.box[3] for g in glyphs),
    )


def _device_box(
    page: pdfium.PdfPage,
    box: tuple[float, float, float, float],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    # PDFium's own mapping accounts for crop boxes and intrinsic /Rotate, just
    # like render(). Plain y = height - y would mask the wrong ink on such PDFs.
    points = []
    left, bottom, right, top = box
    for x, y in ((left, bottom), (left, top), (right, bottom), (right, top)):
        dx, dy = ctypes.c_int(), ctypes.c_int()
        if not pdfium_raw.FPDF_PageToDevice(
            page.raw, 0, 0, width, height, 0, x, y, dx, dy
        ):
            raise ValueError("PDFium could not map a text glyph to the rendered page")
        points.append((dx.value, dy.value))
    return (
        min(p[0] for p in points),
        min(p[1] for p in points),
        max(p[0] for p in points),
        max(p[1] for p in points),
    )


def _stamp_text(
    page: pdfium.PdfPage, width: int, height: int
) -> tuple[list[tuple[int, int, int, int]], tuple[str, ...]]:
    """Find value glyphs by label geometry, not PDF extraction order.

    SolidWorks writes text items as distinct text objects. In particular REV's
    value is below its label and can precede it by many extracted text runs.
    Grouping by object also prevents a note's embedded ``v42`` from becoming a
    version value merely because PDFium concatenated unrelated text objects.
    """
    runs: dict[int, list[_Glyph]] = defaultdict(list)
    text_page = page.get_textpage()
    try:
        for index in range(text_page.count_chars()):
            if pdfium_raw.FPDFText_IsGenerated(text_page.raw, index) == 1:
                continue
            codepoint = pdfium_raw.FPDFText_GetUnicode(text_page.raw, index)
            if not codepoint:
                continue
            char = chr(codepoint)
            owner = pdfium_raw.FPDFText_GetTextObject(text_page.raw, index)
            key = ctypes.cast(owner, ctypes.c_void_p).value or 0
            box = _device_box(page, text_page.get_charbox(index), width, height)
            runs[key].append(_Glyph(char, box))
    finally:
        text_page.close()

    labels: list[tuple[str, tuple[int, int, int, int]]] = []
    versions: list[list[_Glyph]] = []
    for glyphs in runs.values():
        text = "".join(g.char for g in glyphs)
        for match in _LABEL.finditer(text):
            labels.append((match.group(), _box(glyphs[match.start() : match.end()])))
        for match in _VERSION.finditer(text):
            versions.append(glyphs[match.start() : match.end()])

    def in_title(box: tuple[int, int, int, int]) -> bool:
        return (
            box[0] >= max(0, width - TITLE_BLOCK_WIDTH_PT * SCALE)
            and box[1] >= height - TITLE_BLOCK_HEIGHT_PT * SCALE
            and box[2] <= width
            and box[3] <= height
        )

    ignored: set[int] = set()
    boxes = []
    for label, label_box in labels:
        if not in_title(label_box):
            continue
        lx0, ly0, lx1, ly1 = label_box
        candidates = []
        for glyphs in versions:
            value = _box(glyphs)
            if not in_title(value):
                continue
            vx0, vy0, vx1, vy1 = value
            line_height = max(ly1 - ly0, vy1 - vy0, SCALE)
            if label == "BUILD":
                # BUILD and its identifier are inline, not just somewhere in
                # the same quadrant. A maximum gap keeps neighboring notes out.
                gap = vx0 - lx1
                adjacent = (
                    -SCALE <= gap <= max(8 * SCALE, 3 * (ly1 - ly0))
                    and abs((vy0 + vy1) - (ly0 + ly1)) <= line_height
                )
                distance = abs(gap)
            else:
                # REV is a small header centered above its release value.
                gap = vy0 - ly1
                offset = abs((vx0 + vx1 - lx0 - lx1) / 2)
                adjacent = (
                    -SCALE <= gap <= 2 * line_height
                    and offset <= max(8 * SCALE, 0.7 * max(vx1 - vx0, lx1 - lx0))
                )
                distance = abs(gap) + offset
            if adjacent:
                candidates.append((distance, glyphs))
        if candidates:
            _, glyphs = min(candidates, key=lambda item: item[0])
            # Individual tight glyph boxes, with one pixel for raster coverage,
            # never a whole cell or a rectangular union across a version string.
            for glyph in glyphs:
                ignored.add(id(glyph))
                left, top, right, bottom = glyph.box
                boxes.append((left - 1, top - 1, right + 1, bottom + 1))

    # A visible-character multiset is invariant to text-object splitting and
    # paint order. Its only purpose is protecting textual edits from the visual
    # tolerances; it is not a semantic comparison of text order or placement.
    # Version-looking text elsewhere is not normalized.
    text = tuple(
        sorted(
            glyph.char
            for glyphs in runs.values()
            for glyph in glyphs
            if id(glyph) not in ignored and not glyph.char.isspace()
        )
    )
    return boxes, text


@contextmanager
def _document(path: Path) -> Iterator[pdfium.PdfDocument]:
    try:
        document = pdfium.PdfDocument(str(path))
    except pdfium.PdfiumError as error:
        raise ValueError(f"Cannot open drawing PDF {path}: {error}") from error
    try:
        if len(document) == 0:
            raise ValueError(f"Drawing PDF has no pages: {path}")
        yield document
    finally:
        document.close()


def _raster(document: pdfium.PdfDocument, index: int, path: Path) -> _Raster:
    page = document[index]
    try:
        size = page.get_size()
        bitmap = page.render(scale=SCALE, grayscale=True, draw_annots=True)
        try:
            image = bitmap.to_pil()
            try:
                gray = np.array(image, dtype=np.uint8, copy=True)
            finally:
                image.close()
        finally:
            bitmap.close()
        height, width = gray.shape
        boxes, text = _stamp_text(page, width, height)
        return _Raster(gray, size, boxes, text)
    except Exception as error:
        raise ValueError(f"Cannot render drawing PDF {path}, page {index + 1}: {error}") from error
    finally:
        page.close()


def _nearby_darkest(gray: np.ndarray) -> np.ndarray:
    """Bounded Chebyshev ink matching, without wrapping at page boundaries."""
    with Image.fromarray(gray) as image:
        with image.filter(ImageFilter.MinFilter(2 * SPATIAL_TOLERANCE_PIXELS + 1)) as nearby:
            return np.array(nearby, dtype=np.int16)


def _overlay(
    old: _Raster | None, new: _Raster | None, *, include_unchanged: bool = False
) -> tuple[bytes | None, bool, bool]:
    available = [r for r in (old, new) if r is not None]
    height = max(r.gray.shape[0] for r in available)
    width = max(r.gray.shape[1] for r in available)

    def canvas(raster: _Raster | None) -> np.ndarray:
        result = np.full((height, width), 255, dtype=np.uint8)
        if raster is not None:
            h, w = raster.gray.shape
            result[:h, :w] = raster.gray
        return result

    before, after = canvas(old), canvas(new)
    text_changed = old is not None and new is not None and old.text != new.text
    if old is not None and new is not None:
        # Applying the union to BOTH sides avoids leaving either width's stamp
        # behind, including the -dirty suffix or a centered one-to-three-digit REV.
        for left, top, right, bottom in old.stamp_boxes + new.stamp_boxes:
            left, right = max(0, left), min(width, right)
            top, bottom = max(0, top), min(height, bottom)
            before[top:bottom, left:right] = 255
            after[top:bottom, left:right] = 255

    if old is not None and new is not None and not text_changed:
        # Each source pixel must find equal/darker ink (within the intensity
        # tolerance) in the other page's bounded neighborhood. Check BOTH
        # directions: dilation of only one side could hide a new isolated mark.
        # No pixel-count/page-percentage cutoff discards unmatched features.
        removed = _nearby_darkest(after) - before > ANTIALIAS_TOLERANCE
        added = _nearby_darkest(before) - after > ANTIALIAS_TOLERANCE
    else:
        # Character edits bypass both tolerances. Missing pages also retain
        # every ink level rather than matching against an absent counterpart.
        delta = after.astype(np.int16) - before
        removed = delta > 0
        added = delta < 0
    changed = (
        old is None
        or new is None
        or old.size_points != new.size_points
        or text_changed
        or bool(np.any(removed | added))
    )
    if not changed and not include_unchanged:
        return None, False, False

    # White paper; shared ink fades to light gray; changed ink retains its
    # source coverage against white. Fixed arithmetic gives deterministic PNGs.
    shared = (255 - np.minimum(before, after)).astype(np.uint16)
    base = (255 - shared * 47 // 255).astype(np.uint8)
    rgb = np.repeat(base[:, :, None], 3, axis=2)
    for mask, source, color in (
        (removed, before, (220, 32, 32)),
        (added, after, (0, 96, 224)),
    ):
        coverage = (255 - source[mask]).astype(np.uint16)
        for channel, component in enumerate(color):
            rgb[:, :, channel][mask] = 255 - coverage * (255 - component) // 255
    image = Image.fromarray(rgb)
    try:
        with io.BytesIO() as stream:
            image.save(stream, format="PNG", dpi=(DPI, DPI), compress_level=6)
            return stream.getvalue(), text_changed, changed
    finally:
        image.close()


def _pdfs(directory: Path) -> dict[str, Path]:
    if not directory.is_dir():
        raise ValueError(f"Drawing PDF directory does not exist: {directory}")
    return {
        path.relative_to(directory).as_posix(): path
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.suffix.lower() == ".pdf"
    }


def _drawing_pairs(old_files: dict[str, Path], new_files: dict[str, Path]) -> dict[str, str]:
    """Reuse release identity pairing without flattening relative PDF directories."""
    tool = Path(__file__).resolve().parents[1] / "comparisons" / "tools" / "release_diff.py"
    spec = importlib.util.spec_from_file_location("_drawing_release_pairing", tool)
    assert spec is not None and spec.loader is not None
    pairing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pairing)
    mapping = pairing.load_identity_map()
    old_groups, new_groups = defaultdict(list), defaultdict(list)
    for name in old_files:
        old_groups[Path(name).parent.as_posix()].append(name)
    for name in new_files:
        new_groups[Path(name).parent.as_posix()].append(name)
    pairs = {}
    for parent in sorted(old_groups.keys() | new_groups.keys()):
        old_names, new_names = old_groups[parent], new_groups[parent]
        matched = pairing.paired_keys(
            (Path(name).stem for name in old_names),
            (Path(name).stem for name in new_names),
            mapping,
        )
        old_stems = {Path(name).stem: name for name in old_names}
        new_stems = {Path(name).stem: name for name in new_names}
        pairs.update({new_stems[new]: old_stems[old] for new, old in matched.items()})
    return pairs


def _member(archive: ZipFile, name: str, content: bytes) -> None:
    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    archive.writestr(info, content)


def _index(summary: dict[str, Any]) -> bytes:
    escape = html.escape
    counts = summary["page_counts"]
    articles = []
    for page in summary["pages"]:
        if page["image"] is None:
            continue
        title = f"{page['drawing']} — page {page['page']} ({page['status']})"
        source = escape(quote(page["image"], safe="/"), quote=True)
        text_note = "<p>Printed text changed.</p>" if page["text_changed"] else ""
        articles.append(
            f'<article><h2>{escape(title)}</h2>{text_note}'
            f'<a href="{source}"><img loading="lazy" src="{source}" '
            f'alt="{escape(title, quote=True)}"></a></article>'
        )
    content = "\n".join(articles) or "<p>No effective drawing changes.</p>"
    unchanged_note = (
        "included"
        if any(page["status"] == "unchanged" and page["image"] for page in summary["pages"])
        else "omitted"
    )
    return (
        "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Drawing visual differences</title><style>"
        "body{font:16px system-ui,sans-serif;max-width:1500px;margin:2rem auto;padding:0 1rem}"
        "img{width:100%;height:auto;border:1px solid #ccc}article{margin:2rem 0}"
        ".added{color:#0060e0}.removed{color:#dc2020}.shared{color:#888}"
        "</style><h1>Drawing visual differences</h1>"
        f"<p>{escape(summary['old_label'])} → {escape(summary['new_label'])}</p>"
        '<p><strong class="added">Blue: added ink</strong> · '
        '<strong class="removed">Red: removed ink</strong> · '
        '<span class="shared">Light gray: shared ink</span></p>'
        f"<p>Pages: {counts['changed']} changed, {counts['added']} added, "
        f"{counts['removed']} removed, {counts['unchanged']} unchanged ({unchanged_note}).</p>"
        "<p>Only geometrically identified title-block BUILD/REV values are masked. "
        f"At {summary['dpi']} dpi, ink is matched in both directions within "
        f"{summary['spatial_tolerance_pixels']} pixel along each axis "
        f"(Chebyshev distance) and {summary['antialias_intensity_tolerance']} "
        "grayscale levels (0–255). There is no changed-area cutoff. "
        "Printed-character inventory changes disable both tolerances; text order "
        "and placement are not compared semantically. Low-contrast edits and "
        "edge movements/thickness changes within these bounds can be omitted, "
        "as can gaps/bridges up to two pixels and changes inside dense ink. "
        "Embedded-image shading and regenerated break lines can be omitted. "
        "This is not proof of CAD equivalence. Pages align at their top-left "
        "without rescaling. Added/removed pages and page-size changes are always "
        "included, even when blank.</p>"
        '<p><a href="summary.json">Machine-readable summary</a></p>'
        f"{content}</html>"
    ).encode("utf-8")


def create_drawing_diff(
    old_pdf_dir: Path | None,
    new_pdf_dir: Path,
    zip_path: Path,
    *,
    old_label: str,
    new_label: str,
    include_unchanged: bool = False,
) -> dict[str, Any]:
    """Write an overlay ZIP, including index/summary even when nothing changed.

    Drawing classifications are disjoint: ``changed_drawings`` contains common
    PDFs with changed/added/removed pages; additions/removals have their own lists.
    Names use current relative PDF paths (including their extension), with
    ``renamed_drawings`` recording the actual prior paths. Pages are paired by
    ordinal within each paired PDF, never by extracted text. ``asset_path`` is a
    string so the returned facts are JSON serializable.
    Corrupt/unrenderable inputs raise, without replacing a previous output ZIP.
    With ``include_unchanged``, every page has an RGB overlay, including shared
    gray ink on unchanged pages. Image presence does not affect classifications.
    """
    old_files = {} if old_pdf_dir is None else _pdfs(old_pdf_dir)
    new_files = _pdfs(new_pdf_dir)
    pairs = _drawing_pairs(old_files, new_files)
    removed = sorted(old_files.keys() - set(pairs.values()))
    summary: dict[str, Any] = {
        "schema_version": 1,
        "old_label": old_label,
        "new_label": new_label,
        "dpi": DPI,
        "antialias_intensity_tolerance": ANTIALIAS_TOLERANCE,
        "spatial_tolerance_pixels": SPATIAL_TOLERANCE_PIXELS,
        "spatial_distance_metric": "chebyshev",
        "comparison_rule": "symmetric-darker-ink-neighborhood-v1",
        "tolerances_disabled_for_text_changes": True,
        "text_comparison": "visible-character-multiset",
        "tolerance_limitations": [
            f"Ink contrast changes of at most {ANTIALIAS_TOLERANCE} grayscale levels "
            "can be omitted.",
            f"Ink movements/thickness changes within {SPATIAL_TOLERANCE_PIXELS} pixel "
            "along each axis can be omitted.",
            "Gaps/bridges up to two pixels (0.35 mm) and dense-ink pattern changes "
            "can be omitted.",
            "Text order and placement are not compared semantically.",
        ],
        "images": [],
        "changed_drawings": [],
        "renamed_drawings": {new: old for new, old in sorted(pairs.items()) if new != old},
        "added_drawings": sorted(new_files.keys() - pairs.keys()),
        "removed_drawings": removed,
        "unchanged_drawings": [],
        "page_counts": dict.fromkeys(("changed", "added", "removed", "unchanged"), 0),
        "pages": [],
    }
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{zip_path.name}.", dir=zip_path.parent)
    os.close(descriptor)
    temporary_path = Path(temporary)
    try:
        with ZipFile(temporary_path, "w") as archive:
            for name in sorted(new_files.keys() | set(removed)):
                old_name = pairs.get(name) if name in new_files else name
                old_path, new_path = old_files.get(old_name), new_files.get(name)
                # Explicitly nest renderer ownership; neither a page nor a
                # bitmap may outlive its document or retain a shared buffer.
                with ExitStack() as stack:
                    old_doc = stack.enter_context(_document(old_path)) if old_path else None
                    new_doc = stack.enter_context(_document(new_path)) if new_path else None
                    old_count = len(old_doc) if old_doc is not None else 0
                    new_count = len(new_doc) if new_doc is not None else 0
                    drawing_changed = False
                    for index in range(max(old_count, new_count)):
                        old = _raster(old_doc, index, old_path) if index < old_count else None
                        new = _raster(new_doc, index, new_path) if index < new_count else None
                        png, text_changed, changed = _overlay(
                            old, new, include_unchanged=include_unchanged
                        )
                        if old is None:
                            status = "added"
                        elif new is None:
                            status = "removed"
                        else:
                            status = "changed" if changed else "unchanged"
                        member = None
                        if png is not None:
                            member = f"images/{name}/page-{index + 1:04d}.png"
                            _member(archive, member, png)
                            summary["images"].append(member)
                        drawing_changed |= changed
                        summary["page_counts"][status] += 1
                        summary["pages"].append(
                            {
                                "drawing": name,
                                "old_drawing": old_name,
                                "new_drawing": name if new_path is not None else None,
                                "page": index + 1,
                                "status": status,
                                "image": member,
                                "text_changed": text_changed,
                                "old_size_points": list(old.size_points) if old else None,
                                "new_size_points": list(new.size_points) if new else None,
                            }
                        )
                    if old_path is not None and new_path is not None:
                        category = "changed_drawings" if drawing_changed else "unchanged_drawings"
                        summary[category].append(name)
            summary["drawing_counts"] = {
                status: len(summary[f"{status}_drawings"])
                for status in ("changed", "added", "removed", "unchanged")
            }
            _member(archive, "summary.json", (json.dumps(summary, indent=2) + "\n").encode("utf-8"))
            _member(archive, "index.html", _index(summary))
        os.replace(temporary_path, zip_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return {"asset_path": str(zip_path), **summary}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("new_pdf_dir", type=Path)
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--old-pdf-dir", type=Path)
    parser.add_argument("--old-label", default="no previous release")
    parser.add_argument("--new-label", required=True)
    args = parser.parse_args(argv)
    facts = create_drawing_diff(
        args.old_pdf_dir,
        args.new_pdf_dir,
        args.zip_path,
        old_label=args.old_label,
        new_label=args.new_label,
    )
    print(json.dumps(facts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
