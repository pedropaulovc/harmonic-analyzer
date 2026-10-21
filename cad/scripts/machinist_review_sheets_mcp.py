"""Bounded, deterministic sheet images for blind reviews, without source-file access.

PDFs are rendered from vectors; PNG zooms sample the original image, not the
thumbnail. PNG physical resolution comes from valid DPI metadata, otherwise
300 dpi is assumed and explicitly reported. A crop's reported effective dpi is
its information resolution: PNG display upsampling adds pixels, not detail, so
PNG crops report min(display dpi, source dpi) per axis. Neither filenames nor
image metadata are exposed to the reviewer. One process owns one SheetStore and
its crop budget.
"""

from __future__ import annotations

import argparse
import io
import math
import os
import re
import threading
from ctypes import byref, c_long
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from PIL import Image as PILImage
from mcp.server.fastmcp import FastMCP, Image
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ImageContent, TextContent, ToolAnnotations

PDFIUM_LOCK = threading.RLock()
# Measured CLI image sizes from a 5100×3300 source: Claude 2000×1295,
# Codex .159.1 1976×1280. Use the smaller box to avoid CLI-side resizing.
VIEW_BOX = (1976, 1280)
MAX_SCALE = 8
CROP_BUDGET = 40

# --- text layer (exact sheet strings, organized by view) --------------------
VIEW_LABEL_RE = re.compile(
    r"^(?:FRONT|TOP|RIGHT|LEFT|BOTTOM|SIDE|ISOMETRIC(?:\s+VIEW)?|"
    r"DETAIL\s+[A-Z0-9]+|SECTION\s+[A-Z0-9]+(?:\s*[-–]\s*[A-Z0-9]+)?)"
    r"(?:\s+SCALE)?(?:\s*[:：]?\s*\d+\s*[:：]\s*\d+)?\s*$",
    re.IGNORECASE,
)
NOTES_RE = re.compile(r"^(NOTES?|NOTE)\b", re.IGNORECASE)
WATERMARK_RE = re.compile(r"Maker Product|Personal Use Only", re.IGNORECASE)
TITLE_KEYS = (
    "UNLESS OTHERWISE SPECIFIED",
    "DIMENSIONS ARE IN MILLIMETERS",
    "THIRD ANGLE",
    "MATERIAL",
    "FINISH",
    "WEIGHT",
    "SCALE",
    "DRAWN",
    "CHECKED",
    "APPROVED",
    "SHEET",
    "DO NOT SCALE",
    "TOLERANCES",
    "REV",
    "SIZE",
    "INTERPRET PER",
    "DIMENSIONING PER",
    "DRILLED HOLES",
    "EDGE BREAK",
    "SURFACE",
    "DWG",
    "BUILD",
    "UNIT",
)
OP_ONLY = re.compile(r"^[+\-±ØR⌀()]$")
NUM = re.compile(r"[\d.]")


def _view_geometry(
    width: float, height: float, *, downscale_only: bool = False
) -> tuple[tuple[int, int], float]:
    if not all(math.isfinite(value) and value > 0 for value in (width, height)):
        raise ValueError("sheet dimensions must be finite and positive")
    scale = min(VIEW_BOX[0] / width, VIEW_BOX[1] / height)
    if downscale_only:
        scale = min(scale, 1.0)
    size = tuple(
        min(bound, max(1, math.ceil(length * scale)))
        for length, bound in zip((width, height), VIEW_BOX)
    )
    return (size[0], size[1]), scale


def _validate_rect(rect: tuple[int, int, int, int], size: tuple[int, int]) -> None:
    if len(rect) != 4 or any(type(value) is not int for value in rect):
        raise ValueError("crop coordinates must be integers")
    x1, y1, x2, y2 = rect
    if not (0 <= x1 < x2 <= size[0] and 0 <= y1 < y2 <= size[1]):
        raise ValueError(
            f"crop must satisfy 0 <= x1 < x2 <= {size[0]} and "
            f"0 <= y1 < y2 <= {size[1]} in view_sheet pixels"
        )


def _prepare_image(
    image: PILImage.Image, *, preserve_color: bool = False
) -> PILImage.Image:
    mode = "RGB" if preserve_color else "L"
    # Composite transparent PNGs over the same white background as PDF rendering.
    if image.mode in {"RGBA", "LA", "PA"} or "transparency" in image.info:
        with image.convert("RGBA") as rgba:
            with PILImage.new("RGBA", image.size, "white") as background:
                background.alpha_composite(rgba)
                result = background.convert(mode)
        result.info = image.info.copy()
        return result
    return image.convert(mode)


def _png_dpi(image: PILImage.Image) -> tuple[tuple[float, float], bool]:
    dpi = image.info.get("dpi")
    if isinstance(dpi, (tuple, list)) and len(dpi) == 2:
        if all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value > 0
            for value in dpi
        ):
            return (float(dpi[0]), float(dpi[1])), False
    return (300.0, 300.0), True


def _trim_units(pixels: int, scale: float) -> float:
    # PDFium ceil-rounds *each* trim independently. Pick the middle of that
    # integer's rounding interval, avoiding n/scale*scale rounding above n.
    return (pixels - 0.5) / scale if pixels else 0.0


def render_sheet(
    page_or_original_image: Any,
    *,
    sheet: int = 1,
    sheet_count: int = 1,
    rect: tuple[int, int, int, int] | None = None,
    preserve_color: bool = False,
) -> tuple[bytes, str]:
    """Return metadata-free PNG and short text for a PDF page or original PIL image.

    Rectangles are half-open, top-left-origin pixels in the fitted view. Output
    always fits VIEW_BOX; crops magnify that view by at most MAX_SCALE. Reported
    effective dpi is information resolution. PDF DPI is the native render scale
    times 72, including any subpixel rounding of the fitted bitmap. PNG DPI is
    min(display, source) per axis: display dpi is output pixels per source inch,
    and upsampling beyond source pixels interpolates without adding detail.
    The caller retains ownership of the input page/image.
    Images are grayscale by default; preserve_color retains overlay colors in
    views and crops, including resizing, and renders PDFs without grayscale.
    """
    with PDFIUM_LOCK:
        is_png = isinstance(page_or_original_image, PILImage.Image)
        width, height = (
            page_or_original_image.size
            if is_png
            else page_or_original_image.get_size()
        )
        view_size, base_scale = _view_geometry(width, height, downscale_only=is_png)
        if rect is None:
            region = (0, 0, view_size[0], view_size[1])
            magnification = 1.0
            output_size = view_size
        else:
            _validate_rect(rect, view_size)
            region = rect
            region_width, region_height = rect[2] - rect[0], rect[3] - rect[1]
            magnification = min(
                MAX_SCALE, VIEW_BOX[0] / region_width, VIEW_BOX[1] / region_height
            )
            output_size = (
                min(VIEW_BOX[0], max(1, round(region_width * magnification))),
                min(VIEW_BOX[1], max(1, round(region_height * magnification))),
            )

        x1, y1, x2, y2 = region
        if is_png:
            dpi, assumed = _png_dpi(page_or_original_image)
            source_box = (
                width * x1 / view_size[0],
                height * y1 / view_size[1],
                width * x2 / view_size[0],
                height * y2 / view_size[1],
            )
            original = page_or_original_image
            mode = "RGB" if preserve_color else "L"
            prepared = (
                original
                if original.mode == mode and "transparency" not in original.info
                else _prepare_image(original, preserve_color=preserve_color)
            )
            try:
                # PIL's box samples the original region, never a downsampled view.
                rendered = prepared.resize(
                    output_size, PILImage.Resampling.LANCZOS, box=source_box
                )
            finally:
                if prepared is not original:
                    prepared.close()
            display_dpi = (
                dpi[0] * output_size[0] / (source_box[2] - source_box[0]),
                dpi[1] * output_size[1] / (source_box[3] - source_box[1]),
            )
            effective_dpi = (min(display_dpi[0], dpi[0]), min(display_dpi[1], dpi[1]))
            source_note = (
                "PNG 300 dpi assumed; no valid source DPI metadata"
                if assumed
                else "PNG source DPI metadata"
            )
            dpi_note = (
                f" (information resolution = min(display "
                f"{display_dpi[0]:.2f}×{display_dpi[1]:.2f}, source "
                f"{dpi[0]:.2f}×{dpi[1]:.2f}); {source_note})"
            )
        else:
            scale = base_scale * magnification
            # pypdfium2 first ceil-rounds the full bitmap, then independently
            # ceil-rounds left/bottom/right/top trim units. Select integer pixel
            # bounds on that bitmap before converting to trim units: naive PDF
            # box subtraction can erase a one-pixel-wide crop through rounding.
            full_width = math.ceil(width * scale)
            full_height = math.ceil(height * scale)
            left = math.floor(x1 * full_width / view_size[0])
            top = math.floor(y1 * full_height / view_size[1])
            right = math.ceil(x2 * full_width / view_size[0])
            bottom = math.ceil(y2 * full_height / view_size[1])
            trims = tuple(
                _trim_units(pixels, scale)
                for pixels in (left, full_height - bottom, full_width - right, top)
            )
            bitmap = page_or_original_image.render(
                scale=scale, crop=trims, grayscale=not preserve_color
            )
            try:
                with bitmap.to_pil() as native:
                    rendered = native.resize(output_size, PILImage.Resampling.LANCZOS)
            finally:
                bitmap.close()
            effective_dpi = (scale * 72, scale * 72)
            dpi_note = " (PDF vector render)"

        try:
            # Clearing info also removes inherited DPI/ICC/EXIF from source PNGs.
            rendered.info.clear()
            with io.BytesIO() as stream:
                rendered.save(stream, format="PNG", optimize=False, compress_level=6)
                png = stream.getvalue()
        finally:
            rendered.close()

    if rect is None:
        description = f"sheet {sheet} of {sheet_count}, {output_size[0]}×{output_size[1]} px"
    else:
        description = (
            f"sheet {sheet}, rect {rect}, {output_size[0]}×{output_size[1]} px"
        )
        description += (
            f", effective dpi {effective_dpi[0]:.2f}×{effective_dpi[1]:.2f}{dpi_note}"
        )
    return png, description


@dataclass(frozen=True)
class _Sheet:
    source: Any
    page_index: int | None
    view_size: tuple[int, int]


def _span_height(span: dict[str, Any]) -> float:
    return max(span["y2"] - span["y1"], 1.0)


ZONE_FURNITURE_RE = re.compile(r"^[A-Z0-9]$")
WATERMARK_FRAGMENT_RE = re.compile(r"maker|personal|solidworks|(?:^|\s)ake$", re.IGNORECASE)
# PDF text rendering modes that produce no ink (3 = invisible, 7 = clip only).
INVISIBLE_RENDER_MODES = (3, 7)


def _char_visibility(textpage: Any) -> list[tuple[tuple[float, float, float, float], bool]]:
    """Per-character (page-space box, is_printing) flags, keyed by render mode."""
    import pypdfium2.raw as raw

    flags: list[tuple[tuple[float, float, float, float], bool]] = []
    for index in range(textpage.count_chars()):
        box = textpage.get_charbox(index)
        if box is None:
            continue
        obj = textpage.get_textobj(index)
        printing = (
            obj is not None
            and raw.FPDFTextObj_GetTextRenderMode(obj.raw) not in INVISIBLE_RENDER_MODES
        )
        left, bottom, right, top = box
        flags.append(
            (
                (min(left, right), min(bottom, top), max(left, right), max(bottom, top)),
                printing,
            )
        )
    return flags


def _text_spans(
    page: Any, view_size: tuple[int, int]
) -> list[dict[str, Any]]:
    """Extract page text as spans in view_sheet pixels.

    Rectangles are transformed through PDFium's own page-to-device mapping, so
    text positions match the rendered view under page rotation and nonzero
    crop-box origins exactly as view_sheet/crop draw them. Non-rendering text
    (render mode 3 or 7) is excluded: it is not printed evidence. Border
    furniture is dropped narrowly — zone labels and the licence watermark
    only — so annotation text near an edge is preserved for rule 13 findings.
    """
    import pypdfium2.raw as raw

    spans: list[dict[str, Any]] = []

    def to_device(x: float, y: float) -> tuple[int, int]:
        out_x, out_y = c_long(), c_long()
        raw.FPDF_PageToDevice(
            page.raw, 0, 0, view_size[0], view_size[1], 0, x, y,
            byref(out_x), byref(out_y),
        )
        return out_x.value, out_y.value

    textpage = page.get_textpage()
    try:
        visibility = _char_visibility(textpage)
        textpage.count_rects()  # required before get_rect (pypdfium2 contract)
        for index in range(textpage.count_rects()):
            left, bottom, right, top = textpage.get_rect(index)
            text = re.sub(
                r"\s+", " ", (textpage.get_text_bounded(left, bottom, right, top) or "").strip()
            )
            if not text:
                continue
            in_span = [
                printing
                for box, printing in visibility
                if (box[0] + box[2]) / 2 >= left
                and (box[0] + box[2]) / 2 <= right
                and (box[1] + box[3]) / 2 >= bottom
                and (box[1] + box[3]) / 2 <= top
            ]
            if in_span and not any(in_span):
                continue
            corners = [
                to_device(x, y)
                for x, y in ((left, bottom), (right, bottom), (left, top), (right, top))
            ]
            x1 = min(p[0] for p in corners)
            y1 = min(p[1] for p in corners)
            x2 = max(p[0] for p in corners)
            y2 = max(p[1] for p in corners)
            if WATERMARK_RE.search(text) or WATERMARK_FRAGMENT_RE.search(text):
                continue
            if ZONE_FURNITURE_RE.match(text):
                continue
            spans.append({"x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2), "text": text})
    finally:
        textpage.close()
    return spans


def _fold_operators(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fold operator-only spans (+, -, ±, Ø, parens) into their numeric neighbor."""
    spans = list(spans)
    changed = True
    while changed:
        changed = False
        for index, span in enumerate(spans):
            if not OP_ONLY.match(span["text"]):
                continue
            height = _span_height(span)
            best: tuple[float, int] | None = None
            for other_index, other in enumerate(spans):
                if other_index == index or not NUM.search(other["text"]):
                    continue
                other_height = _span_height(other)
                gap = max(
                    0.0, max(span["x1"] - other["x2"], other["x1"] - span["x2"])
                )
                dy = abs(
                    (span["y1"] + span["y2"]) / 2 - (other["y1"] + other["y2"]) / 2
                )
                if (
                    dy > 0.4 * height
                    or not (0.5 * height <= other_height <= 2 * height)
                    or gap > 1.5 * height
                ):
                    continue
                if best is None or gap < best[0]:
                    best = (gap, other_index)
            if best is not None:
                other = spans[best[1]]
                text = (
                    span["text"] + other["text"]
                    if span["x2"] <= other["x1"] + 2
                    else other["text"] + span["text"]
                )
                merged = {
                    "x1": min(span["x1"], other["x1"]),
                    "y1": min(span["y1"], other["y1"]),
                    "x2": max(span["x2"], other["x2"]),
                    "y2": max(span["y2"], other["y2"]),
                    "text": text,
                }
                spans = [
                    value
                    for i, value in enumerate(spans)
                    if i not in (index, best[1])
                ] + [merged]
                changed = True
                break
    return spans


STACK_LIMIT_RE = re.compile(r"^[+±\-]?\d[\d.]*$")


def _stack_pairs(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Join a positively identified tolerance stack as 'upper/lower'.

    Only two spans ever join: the upper token carries an explicit +/± limit
    sign, or the lower token is negative, and both are plain limit values of
    similar size. Ordinary aligned rows (table cells, note lines, adjacent
    dimensions) are never synthesized into a single value, and a joined pair
    absorbs nothing further.
    """
    ordered = [dict(s) for s in sorted(spans, key=lambda s: (s["y1"], s["x1"]))]
    merged: list[dict[str, Any]] = []
    joined: set[int] = set()
    for span in ordered:
        target = None
        for candidate in merged:
            if id(candidate) in joined:
                continue
            if not (
                STACK_LIMIT_RE.match(span["text"])
                and STACK_LIMIT_RE.match(candidate["text"])
            ):
                continue
            upper, lower = (
                (candidate, span) if candidate["y1"] <= span["y1"] else (span, candidate)
            )
            if not (
                upper["text"].startswith(("+", "±"))
                or lower["text"].startswith("-")
            ):
                continue
            heights = (_span_height(span), _span_height(candidate))
            if max(heights) > 2 * min(heights):
                continue
            xoverlap = min(span["x2"], candidate["x2"]) - max(
                span["x1"], candidate["x1"]
            )
            dy = max(0.0, span["y1"] - candidate["y2"], candidate["y1"] - span["y2"])
            if (
                xoverlap > 0.5 * min(span["x2"] - span["x1"], candidate["x2"] - candidate["x1"])
                and dy <= 0.8 * min(heights)
            ):
                target = candidate
                break
        if target is not None:
            top, bottom = (target, span) if target["y1"] <= span["y1"] else (span, target)
            target["text"] = top["text"] + "/" + bottom["text"]
            target["x1"] = min(target["x1"], span["x1"])
            target["y1"] = min(target["y1"], span["y1"])
            target["x2"] = max(target["x2"], span["x2"])
            target["y2"] = max(target["y2"], span["y2"])
            joined.add(id(target))
        else:
            merged.append(span)
    return merged


def _text_lines(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge spans into text lines; stacked limits read as +0.03/0.00."""
    spans = _stack_pairs(_fold_operators(spans))
    spans = sorted(spans, key=lambda s: (s["y1"], s["x1"]))
    lines: list[dict[str, Any]] = []
    for span in spans:
        height = _span_height(span)
        placed = None
        for line in lines:
            dy = abs(
                (span["y1"] + span["y2"]) / 2 - (line["y1"] + line["y2"]) / 2
            )
            gap = max(0.0, span["x1"] - line["x2"], line["x1"] - span["x2"])
            band_hit = (line["y1"] <= (span["y1"] + span["y2"]) / 2 <= line["y2"]) or (
                span["y1"] <= (line["y1"] + line["y2"]) / 2 <= span["y2"]
            )
            tight = min(height, _span_height(line))
            if (dy <= 0.35 * height and gap <= 0.8 * tight) or (
                band_hit and gap <= 1.2 * tight
            ):
                placed = line
                break
        if placed is not None:
            gap_now = span["x1"] - placed["x2"]
            separator = "" if 0 <= gap_now < 0.3 * height else " "
            placed["text"] = (
                (placed["text"] + separator + span["text"])
                if span["x1"] >= placed["x1"]
                else (span["text"] + separator + placed["text"])
            )
            placed["x1"] = min(placed["x1"], span["x1"])
            placed["y1"] = min(placed["y1"], span["y1"])
            placed["x2"] = max(placed["x2"], span["x2"])
            placed["y2"] = max(placed["y2"], span["y2"])
            continue
        lines.append(dict(span))
    return lines


def _chain_groups(
    lines: list[dict[str, Any]], gap: float
) -> list[list[dict[str, Any]]]:
    """Group lines into spatial clusters by nearest-neighbor chaining."""
    remaining = sorted(lines, key=lambda line: (line["y1"], line["x1"]))
    groups: list[list[dict[str, Any]]] = []
    while remaining:
        block = [remaining.pop(0)]
        changed = True
        while changed:
            changed = False
            for line in list(remaining):
                for member in block:
                    dx = max(0.0, max(line["x1"] - member["x2"], member["x1"] - line["x2"]))
                    dy = max(0.0, max(line["y1"] - member["y2"], member["y1"] - line["y2"]))
                    if (dx * dx + dy * dy) ** 0.5 <= gap:
                        block.append(line)
                        remaining.remove(line)
                        changed = True
                        break
        groups.append(block)
    return groups


def sheet_text_document(
    spans: list[dict[str, Any]],
    *,
    sheet: int,
    sheet_count: int,
    view_size: tuple[int, int],
) -> str:
    """One sheet's exact text, organized by view, in view_sheet pixels.

    A view label names only its own spatial group; unlabeled groups keep
    honest bbox names rather than guessed view ownership, and a cluster
    carrying more than one view label stays unlabeled. The title block is
    the bottom-right region; border furniture and the licence watermark are
    excluded. A sheet without extractable text yields an empty document.
    """
    if not spans:
        return ""
    lines = _text_lines(spans)
    view_w, view_h = view_size
    title = [
        line
        for line in lines
        if line["x1"] > 0.5 * view_w
        and line["y1"] > 0.72 * view_h
        and not VIEW_LABEL_RE.match(line["text"].strip())
        and not NOTES_RE.match(line["text"].strip())
    ]
    notes = [
        line
        for line in lines
        if line not in title and NOTES_RE.match(line["text"].strip())
    ]
    rest = [line for line in lines if line not in title and line not in notes]

    groups: list[tuple[str, list[dict[str, Any]]]] = []
    for block in _chain_groups(rest, gap=90):
        labels = [
            line["text"].strip()
            for line in block
            if VIEW_LABEL_RE.match(line["text"].strip())
        ]
        if len(labels) == 1:
            groups.append((labels[0], block))
            continue
        x1 = min(line["x1"] for line in block)
        y1 = min(line["y1"] for line in block)
        x2 = max(line["x2"] for line in block)
        y2 = max(line["y2"] for line in block)
        kind = "unlabeled" if not labels else "multi-view"
        groups.append((f"({kind}) @ ({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f})", block))

    out = [
        f"Sheet text layer — sheet {sheet} of {sheet_count}.",
        "Rects (x1,y1)-(x2,y2) are view_sheet pixels; crop with margin.",
        "",
    ]

    def emit(header: str, members: list[dict[str, Any]]) -> None:
        out.append(header)
        for line in sorted(
            members, key=lambda line: (round(line["y1"] / 14), line["x1"])
        ):
            out.append(
                f'  ({line["x1"]:.0f},{line["y1"]:.0f})-({line["x2"]:.0f},{line["y2"]:.0f})'
                f'  {line["text"]}'
            )
        out.append("")

    groups.sort(
        key=lambda group: (
            min(line["y1"] for line in group[1]),
            min(line["x1"] for line in group[1]),
        )
    )
    for name, members in groups:
        header = (
            f'== view "{name}" =='
            if not name.startswith("(unlabeled)")
            else f"== view {name} =="
        )
        emit(header, members)
    if notes:
        emit("== notes ==", notes)
    if title:
        emit("== title block ==", title)
    return "\n".join(out).rstrip()


class SheetStore:
    """Open sources once, in order; own all native handles and memoized renders.

    A server process uses one store. Every crop attempt consumes its 40-call
    budget, including invalid rectangles, repeated cache hits and failed renders.
    """

    def __init__(self, sources: Sequence[Path], *, preserve_color: bool = False):
        import pypdfium2 as pdfium

        self._lock = threading.RLock()
        self._closed = False
        self._preserve_color = preserve_color
        self._sources: dict[Path, Any] = {}
        self._sheets: list[_Sheet] = []
        self._views: dict[int, tuple[bytes, str]] = {}
        self._crops: dict[tuple[int, int, int, int, int], tuple[bytes, str]] = {}
        self._texts: dict[int, str] = {}
        self._spans: dict[int, list[dict[str, Any]]] = {}
        self._crop_calls = 0
        try:
            with PDFIUM_LOCK:
                for source in sources:
                    path = Path(source).resolve()
                    suffix = path.suffix.casefold()
                    if suffix not in {".pdf", ".png"}:
                        raise ValueError("sheet sources must be PDF or PNG files")
                    if path not in self._sources:
                        if suffix == ".pdf":
                            self._sources[path] = pdfium.PdfDocument(str(path))
                        else:
                            with PILImage.open(path) as image:
                                if image.format != "PNG":
                                    raise ValueError("PNG sources must contain PNG images")
                                self._sources[path] = _prepare_image(
                                    image, preserve_color=preserve_color
                                )
                    opened = self._sources[path]
                    if suffix == ".pdf":
                        if len(opened) == 0:
                            raise ValueError("PDF source has no sheets")
                        for index in range(len(opened)):
                            page = opened[index]
                            try:
                                size, _ = _view_geometry(*page.get_size())
                            finally:
                                page.close()
                            self._sheets.append(_Sheet(opened, index, size))
                    else:
                        size, _ = _view_geometry(*opened.size, downscale_only=True)
                        self._sheets.append(_Sheet(opened, None, size))
                if not self._sheets:
                    raise ValueError("at least one sheet source is required")
        except BaseException:
            self.close()
            raise

    @property
    def sheet_count(self) -> int:
        return len(self._sheets)

    def __enter__(self) -> SheetStore:
        with self._lock:
            self._ensure_open()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        with self._lock, PDFIUM_LOCK:
            if self._closed:
                return
            self._closed = True
            try:
                for source in self._sources.values():
                    source.close()
            finally:
                self._sources.clear()
                self._sheets.clear()
                self._views.clear()
                self._crops.clear()
                self._texts.clear()
                self._spans.clear()

    def _ensure_open(self) -> None:
        if self._closed:
            raise ValueError("sheet store is closed")

    def _sheet(self, sheet: int) -> _Sheet:
        self._ensure_open()
        if type(sheet) is not int or not 1 <= sheet <= self.sheet_count:
            raise ValueError(f"sheet must be an integer from 1 to {self.sheet_count}")
        return self._sheets[sheet - 1]

    def view_size(self, sheet: int) -> tuple[int, int]:
        with self._lock:
            return self._sheet(sheet).view_size

    def _render(
        self, sheet: int, entry: _Sheet, rect: tuple[int, int, int, int] | None = None
    ) -> tuple[bytes, str]:
        with PDFIUM_LOCK:
            source = (
                entry.source if entry.page_index is None else entry.source[entry.page_index]
            )
            try:
                return render_sheet(
                    source, sheet=sheet, sheet_count=self.sheet_count, rect=rect,
                    preserve_color=self._preserve_color,
                )
            finally:
                if entry.page_index is not None:
                    source.close()

    def view_sheet(self, sheet: int) -> tuple[bytes, str]:
        with self._lock:
            entry = self._sheet(sheet)
            if sheet not in self._views:
                self._views[sheet] = self._render(sheet, entry)
            return self._views[sheet]

    def _attempt_crop(self) -> None:
        with self._lock:
            self._crop_calls += 1
            self._ensure_open()
            if self._crop_calls > CROP_BUDGET:
                raise ValueError(f"crop budget exhausted ({CROP_BUDGET} attempted calls)")

    def crop(self, sheet: int, x1: int, y1: int, x2: int, y2: int) -> tuple[bytes, str]:
        with self._lock:
            self._attempt_crop()
            entry = self._sheet(sheet)
            rect = (x1, y1, x2, y2)
            _validate_rect(rect, entry.view_size)
            key = (sheet, *rect)
            if key not in self._crops:
                self._crops[key] = self._render(sheet, entry, rect)
            return self._crops[key]

    def text_layer(self, sheet: int) -> str:
        """One sheet's exact text organized by view; empty without extractable text."""
        with self._lock:
            entry = self._sheet(sheet)
            if sheet in self._texts:
                return self._texts[sheet]
            spans = self._text_spans(sheet, entry)
        # Grouping is pure Python on copied spans; keep it off the global lock.
        document = sheet_text_document(
            spans,
            sheet=sheet,
            sheet_count=self.sheet_count,
            view_size=entry.view_size,
        )
        with self._lock:
            self._texts[sheet] = document
        return document

    def _text_spans(self, sheet: int, entry: _Sheet) -> list[dict[str, Any]]:
        """Memoized per-sheet spans; native extraction stays under the lock."""
        with self._lock:
            if sheet in self._spans:
                return self._spans[sheet]
            if entry.page_index is None:
                self._spans[sheet] = []
                return []
            with PDFIUM_LOCK:
                page = entry.source[entry.page_index]
                try:
                    spans = _text_spans(page, entry.view_size)
                finally:
                    page.close()
            self._spans[sheet] = spans
            return spans


def create_server(store: SheetStore) -> FastMCP:
    """Register only static-schema view_sheet/crop tools; SDK reports tool errors."""

    class SheetsServer(FastMCP):
        async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
            expected = {
                "view_sheet": {"sheet"},
                "crop": {"sheet", "x1", "y1", "x2", "y2"},
            }.get(name)
            if expected is not None and (
                not isinstance(arguments, dict)
                or set(arguments) != expected
                or any(type(value) is not int for value in arguments.values())
            ):
                # FastMCP normally validates/coerces before invoking a function.
                # Charge malformed crops too, and reject coercion/extra keys.
                try:
                    if name == "crop":
                        store._attempt_crop()
                    raise ValueError("provide exactly the tool's named integer arguments")
                except ValueError as exc:
                    raise ToolError(str(exc)) from exc
            return await super().call_tool(name, arguments)

    server = SheetsServer("sheets")
    annotations = ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=False, openWorldHint=False
    )

    @server.tool(
        description=(
            "View a 1-based sheet as a PNG fitted within 1976×1280 pixels. "
            "Images are grayscale except in color-preserving overlay mode, "
            "which retains red/blue/gray in views and crops. "
            "Sheets follow input order, expanding each PDF in page order. "
            "Call for every sheet in order before judging. The returned image's "
            "top-left pixel coordinates define crop rectangles."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
        ),
        structured_output=False,
    )
    def view_sheet(sheet: int) -> list[ImageContent | TextContent]:
        png, text = store.view_sheet(sheet)
        return [Image(data=png, format="png").to_image_content(), TextContent(type="text", text=text)]

    @server.tool(
        description=(
            "Zoom a 1-based sheet using integer top-left-origin view_sheet pixels: "
            "0 <= x1 < x2 <= view width and 0 <= y1 < y2 <= view height; "
            "right/bottom edges are exclusive. Output fits 1976×1280 pixels, "
            "grayscale except in color-preserving overlay mode, at most 8× the "
            "view scale. PDF crops render vectors; PNG crops use the "
            "original image (valid source DPI metadata, otherwise 300 dpi assumed); "
            "PNG effective dpi never exceeds source dpi, as upsampling adds no detail. "
            "Budget: 40 attempted crop calls per process, including invalid calls "
            "and repeats; repeated valid crops reuse a memoized rendering."
        ),
        annotations=annotations,
        structured_output=False,
    )
    def crop(sheet: int, x1: int, y1: int, x2: int, y2: int) -> list[ImageContent | TextContent]:
        png, text = store.crop(sheet, x1, y1, x2, y2)
        return [Image(data=png, format="png").to_image_content(), TextContent(type="text", text=text)]

    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preserve-color", action="store_true",
        help="Retain overlay colors in sheet views and crops instead of grayscale.",
    )
    parser.add_argument("sources", type=Path, nargs="+", help="PDF or PNG sheet sources")
    args = parser.parse_args(argv)
    with SheetStore(args.sources, preserve_color=args.preserve_color) as store:
        # Sources are resolved and open now. Leave the inherited per-attempt cwd
        # so an orphaned server cannot lock it against Windows rename/delete.
        os.chdir(Path(__file__).resolve().anchor)
        create_server(store).run(transport="stdio")


if __name__ == "__main__":
    main()
