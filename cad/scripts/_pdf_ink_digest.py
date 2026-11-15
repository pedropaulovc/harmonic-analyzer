"""Digest of the ink a drawing PDF prints, not of the file that carries it.

Every SolidWorks export stamps the file with its creation and modification time,
a random document ``/ID`` and random font-subset tags, so two builds of one
drawing never share bytes even when they print the same sheet. This digest
covers, page by page, the page size, the printed characters and the 144 dpi
grayscale raster PDFium paints (the resolution ``_drawing_diff`` compares at).
It has no tolerance: one changed pixel or character changes the digest.

``VERSION`` is folded into every digest, so changing what is read re-keys every
consumer instead of reusing a result under the older reading.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pypdfium2 as pdfium

VERSION = "pdf-ink-1"
DPI = 144
SCALE = DPI / 72.0


class PdfInkError(ValueError):
    """PDFium cannot open or render the file."""


def pdf_ink_digest(path: str | Path) -> str:
    """``pdf-ink-1:<sha256>`` of every page's size, characters and raster."""
    digest = hashlib.sha256(f"{VERSION}\0{DPI}\0".encode())
    try:
        document = pdfium.PdfDocument(str(path))
    except (pdfium.PdfiumError, OSError) as error:
        raise PdfInkError(f"{path}: cannot open PDF: {error}") from error
    try:
        if len(document) == 0:
            raise PdfInkError(f"{path}: PDF has no pages")
        for index in range(len(document)):
            page = document[index]
            try:
                text_page = page.get_textpage()
                try:
                    characters = "".join(
                        sorted("".join(text_page.get_text_range().split()))
                    )
                finally:
                    text_page.close()
                bitmap = page.render(scale=SCALE, grayscale=True, draw_annots=True)
                try:
                    header = (
                        page.get_size(),
                        bitmap.width,
                        bitmap.height,
                        bitmap.stride,
                    )
                    digest.update(repr(header).encode() + b"\0")
                    digest.update(characters.encode("utf-8", "surrogatepass") + b"\0")
                    digest.update(bytes(bitmap.buffer))
                finally:
                    bitmap.close()
            except pdfium.PdfiumError as error:
                raise PdfInkError(
                    f"{path}: cannot render page {index + 1}: {error}"
                ) from error
            finally:
                page.close()
    finally:
        document.close()
    return f"{VERSION}:{digest.hexdigest()}"
