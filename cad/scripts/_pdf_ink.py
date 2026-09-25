"""The ink a drawing leaf actually printed, read back from its vector PDF.

SolidWorks exports drawing text as real PDF text (glyph boxes are exact) and
every line as a stroked path carrying its width, colour and dash pattern. That
makes the PDF the calibration truth for ``_layout_audit``'s COM-derived text
boxes and model edges: it is what the machinist reads.

Coordinates are converted to sheet METRES with the origin at the sheet's
lower-left corner -- PDF user space is already y-up from the lower-left, in
points (1/72 in).

pypdfium2 is used (already a dependency for the PNG render); PyMuPDF is AGPL.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw

POINT_M = 0.0254 / 72.0


@dataclass(frozen=True)
class Glyph:
    char: str
    xmin: float
    ymin: float
    xmax: float
    ymax: float


@dataclass(frozen=True)
class Span:
    """The inked glyphs of one PDF text object: one printed text run."""

    text: str
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    glyphs: tuple[Glyph, ...]


@dataclass(frozen=True)
class Stroke:
    """One straight piece of a stroked or filled path, in sheet metres."""

    x0: float
    y0: float
    x1: float
    y1: float
    width: float  # stroke width, metres
    rgb: tuple[int, int, int]
    dashed: bool
    filled: bool
    stroked: bool


@dataclass(frozen=True)
class PageInk:
    width: float
    height: float
    glyphs: tuple[Glyph, ...]
    spans: tuple[Span, ...]
    strokes: tuple[Stroke, ...]


def _text_runs(page: "pdfium.PdfPage") -> tuple[list[Glyph], list[Span]]:
    """Every inked glyph, grouped by the PDF TEXT OBJECT that drew it.

    SolidWorks writes each display-data text item as its own text object, so
    the object is the natural run: "20.8" and "8.42" stay two runs even when
    they touch, which is exactly the case a baseline-and-gap grouping merges.
    Glyph boxes are pdfium's tight character boxes; generated characters
    (spaces and line breaks pdfium synthesises) carry no ink and are skipped.
    """
    text_page = page.get_textpage()
    by_object: dict[int, list[Glyph]] = {}
    order: list[int] = []
    glyphs: list[Glyph] = []
    for index in range(text_page.count_chars()):
        char = text_page.get_text_range(index, 1)
        if not char or char.isspace() or pdfium_raw.FPDFText_IsGenerated(text_page.raw, index) == 1:
            continue
        left, bottom, right, top = text_page.get_charbox(index)
        if right <= left or top <= bottom:
            continue
        glyph = Glyph(char, left * POINT_M, bottom * POINT_M, right * POINT_M, top * POINT_M)
        glyphs.append(glyph)
        owner = pdfium_raw.FPDFText_GetTextObject(text_page.raw, index)
        key = ctypes.cast(owner, ctypes.c_void_p).value or 0
        if key not in by_object:
            by_object[key] = []
            order.append(key)
        by_object[key].append(glyph)
    spans = []
    for key in order:
        run = by_object[key]
        spans.append(
            Span(
                "".join(g.char for g in run),
                min(g.xmin for g in run),
                min(g.ymin for g in run),
                max(g.xmax for g in run),
                max(g.ymax for g in run),
                tuple(run),
            )
        )
    return glyphs, spans


# Pieces per cubic Bezier: a quarter circle of 30 mm radius strays 0.01 mm.
BEZIER_PIECES = 8


def bezier_points(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    pieces: int = BEZIER_PIECES,
) -> list[tuple[float, float]]:
    """The cubic's points at ``pieces`` equal parameter steps, ends included."""
    points = []
    for step in range(pieces + 1):
        t = step / pieces
        u = 1.0 - t
        a, b, c, d = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
        points.append(
            (
                a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1],
            )
        )
    return points


def _strokes(page: "pdfium.PdfPage") -> list[Stroke]:
    strokes: list[Stroke] = []
    for obj in page.get_objects(max_depth=8):
        if obj.type != pdfium_raw.FPDF_PAGEOBJ_PATH:
            continue
        handle = obj.raw
        width = ctypes.c_float()
        pdfium_raw.FPDFPageObj_GetStrokeWidth(handle, width)
        r, g, b, a = (ctypes.c_uint() for _ in range(4))
        pdfium_raw.FPDFPageObj_GetStrokeColor(handle, r, g, b, a)
        fill_mode, stroke = ctypes.c_int(), ctypes.c_int()
        pdfium_raw.FPDFPath_GetDrawMode(handle, fill_mode, stroke)
        dashed = pdfium_raw.FPDFPageObj_GetDashCount(handle) > 0
        matrix = pdfium_raw.FS_MATRIX()
        pdfium_raw.FPDFPageObj_GetMatrix(handle, matrix)
        scale = (abs(matrix.a * matrix.d - matrix.b * matrix.c)) ** 0.5 or 1.0

        def to_sheet(x: float, y: float) -> tuple[float, float]:
            return (
                (matrix.a * x + matrix.c * y + matrix.e) * POINT_M,
                (matrix.b * x + matrix.d * y + matrix.f) * POINT_M,
            )

        def piece(a: tuple[float, float], z: tuple[float, float]) -> Stroke:
            return Stroke(
                a[0], a[1], z[0], z[1],
                width.value * scale * POINT_M,
                (r.value, g.value, b.value),
                dashed,
                fill_mode.value != 0,
                bool(stroke.value),
            )

        start = None
        previous = None
        controls: list[tuple[float, float]] = []
        for index in range(pdfium_raw.FPDFPath_CountSegments(handle)):
            segment = pdfium_raw.FPDFPath_GetPathSegment(handle, index)
            x, y = ctypes.c_float(), ctypes.c_float()
            pdfium_raw.FPDFPathSegment_GetPoint(segment, x, y)
            point = to_sheet(x.value, y.value)
            kind = pdfium_raw.FPDFPathSegment_GetType(segment)
            if kind == pdfium_raw.FPDF_SEGMENT_MOVETO or previous is None:
                start = previous = point
                controls = []
                continue
            if kind == pdfium_raw.FPDF_SEGMENT_BEZIERTO:
                # A cubic arrives as three BEZIERTO points (two controls, then
                # the end); its control polygon can sit well off the drawn arc.
                controls.append(point)
                if len(controls) < 3:
                    continue
                curve = bezier_points(previous, *controls)
                strokes.extend(piece(a, z) for a, z in zip(curve, curve[1:]))
                controls = []
            else:
                strokes.append(piece(previous, point))
            previous = point
            if pdfium_raw.FPDFPathSegment_GetClose(segment) and start is not None:
                strokes.append(piece(point, start))
                previous = start
    return strokes


def read_pdf_ink(path: Path) -> list[PageInk]:
    """Every page's glyphs, text runs and path pieces, in sheet metres."""
    document = pdfium.PdfDocument(str(path))
    pages = []
    try:
        for index in range(len(document)):
            page = document[index]
            width, height = page.get_size()
            glyphs, spans = _text_runs(page)
            pages.append(
                PageInk(
                    width * POINT_M,
                    height * POINT_M,
                    tuple(glyphs),
                    tuple(spans),
                    tuple(_strokes(page)),
                )
            )
    finally:
        document.close()
    return pages
