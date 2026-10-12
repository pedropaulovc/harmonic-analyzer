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

import io
import math
import os
import sys
import threading
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


def _grayscale(image: PILImage.Image) -> PILImage.Image:
    # Composite transparent PNGs over the same white background as PDF rendering.
    if image.mode in {"RGBA", "LA", "PA"} or "transparency" in image.info:
        with image.convert("RGBA") as rgba:
            with PILImage.new("RGBA", image.size, "white") as background:
                background.alpha_composite(rgba)
                result = background.convert("L")
        result.info = image.info.copy()
        return result
    return image.convert("L")


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
) -> tuple[bytes, str]:
    """Return metadata-free L PNG and short text for a PDF page or original PIL image.

    Rectangles are half-open, top-left-origin pixels in the fitted view. Output
    always fits VIEW_BOX; crops magnify that view by at most MAX_SCALE. Reported
    effective dpi is information resolution. PDF DPI is the native render scale
    times 72, including any subpixel rounding of the fitted bitmap. PNG DPI is
    min(display, source) per axis: display dpi is output pixels per source inch,
    and upsampling beyond source pixels interpolates without adding detail.
    The caller retains ownership of the input page/image.
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
            gray = original if original.mode == "L" else _grayscale(original)
            try:
                # PIL's box samples the original region, never a downsampled view.
                rendered = gray.resize(
                    output_size, PILImage.Resampling.LANCZOS, box=source_box
                )
            finally:
                if gray is not original:
                    gray.close()
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
                scale=scale, crop=trims, grayscale=True
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


class SheetStore:
    """Open sources once, in order; own all native handles and memoized renders.

    A server process uses one store. Every crop attempt consumes its 40-call
    budget, including invalid rectangles, repeated cache hits and failed renders.
    """

    def __init__(self, sources: Sequence[Path]):
        import pypdfium2 as pdfium

        self._lock = threading.RLock()
        self._closed = False
        self._sources: dict[Path, Any] = {}
        self._sheets: list[_Sheet] = []
        self._views: dict[int, tuple[bytes, str]] = {}
        self._crops: dict[tuple[int, int, int, int, int], tuple[bytes, str]] = {}
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
                                self._sources[path] = _grayscale(image)
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
                    source, sheet=sheet, sheet_count=self.sheet_count, rect=rect
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
            "View a 1-based sheet as a grayscale PNG fitted within 1976×1280 pixels. "
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
            "right/bottom edges are exclusive. Output fits 1976×1280 grayscale pixels, "
            "at most 8× the view scale. PDF crops render vectors; PNG crops use the "
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


def main() -> None:
    with SheetStore([Path(source) for source in sys.argv[1:]]) as store:
        # Sources are resolved and open now. Leave the inherited per-attempt cwd
        # so an orphaned server cannot lock it against Windows rename/delete.
        os.chdir(Path(__file__).resolve().anchor)
        create_server(store).run(transport="stdio")


if __name__ == "__main__":
    main()
