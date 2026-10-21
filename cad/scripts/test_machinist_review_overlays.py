"""Color-preserving review sheets and opt-in unchanged drawing overlays."""

from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import numpy as np
import pytest
from PIL import Image, ImageDraw

import _drawing_diff as diff
import machinist_review_sheets_mcp as sheets
from test_drawing_diff import _pdf, _square


COLORS = ((220, 32, 32), (0, 96, 224), (208, 208, 208))


def _overlay_png(path: Path, size: tuple[int, int] = (240, 160), mode: str = "RGB") -> Path:
    with Image.new(mode, size, "white") as image:
        draw = ImageDraw.Draw(image)
        for index, color in enumerate(COLORS):
            draw.rectangle(
                (index * size[0] // 3, 0, (index + 1) * size[0] // 3 - 1, size[1] - 1),
                fill=color,
            )
        image.save(path, format="PNG", dpi=(144, 144))
    return path


def _assert_overlay_colors(png: bytes) -> None:
    with Image.open(io.BytesIO(png)) as image:
        assert image.mode == "RGB"
        assert image.info == {}
        pixels = np.array(image)
        for color in COLORS:
            assert np.any(np.all(pixels == color, axis=2)), color


def _forbid_grayscale(monkeypatch: pytest.MonkeyPatch) -> None:
    original_convert = Image.Image.convert

    def convert(image, mode=None, *args, **kwargs):
        assert mode != "L", "color-preserving rendering must never convert to L"
        return original_convert(image, mode, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "convert", convert)


@pytest.mark.parametrize("size", [(240, 160), (2400, 1600)])
@pytest.mark.parametrize("mode", ["RGB", "RGBA"])
def test_color_views_and_crops_never_convert_to_grayscale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, size: tuple[int, int], mode: str
) -> None:
    path = _overlay_png(tmp_path / "overlay.png", size, mode)
    _forbid_grayscale(monkeypatch)
    with sheets.SheetStore([path], preserve_color=True) as store:
        view, _ = store.view_sheet(1)
        _assert_overlay_colors(view)
        width, height = store.view_size(1)
        rect = (width // 5, height // 5, width * 4 // 5, height * 4 // 5)
        crop, text = store.crop(1, *rect)
        _assert_overlay_colors(crop)
        assert "effective dpi" in text
        assert store.crop(1, *rect) == (crop, text)
        with Image.open(path) as original:
            assert sheets.render_sheet(original, preserve_color=True)[0] == view
            assert sheets.render_sheet(original, rect=rect, preserve_color=True)[0] == crop
            assert original.getpixel((0, 0))[:3] == COLORS[0]


def test_transparent_color_input_is_composited_over_white(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "transparent.png"
    with Image.new("RGBA", (20, 20), (220, 32, 32, 0)) as image:
        image.putpixel((10, 10), (*COLORS[1], 255))
        image.save(path)
    _forbid_grayscale(monkeypatch)
    with sheets.SheetStore([path], preserve_color=True) as store:
        with Image.open(io.BytesIO(store.view_sheet(1)[0])) as view:
            assert view.mode == "RGB"
            assert view.getpixel((0, 0)) == (255, 255, 255)
            assert view.getpixel((10, 10)) == COLORS[1]


def test_default_views_and_crops_still_return_grayscale(tmp_path: Path) -> None:
    path = _overlay_png(tmp_path / "overlay.png")
    with sheets.SheetStore([path]) as default, sheets.SheetStore(
        [path], preserve_color=False
    ) as explicit:
        rect = (20, 20, 200, 120)
        for rendered, expected in (
            (default.view_sheet(1), explicit.view_sheet(1)),
            (default.crop(1, *rect), explicit.crop(1, *rect)),
        ):
            assert rendered == expected
            with Image.open(io.BytesIO(rendered[0])) as image:
                assert image.mode == "L"
                assert image.info == {}
        with Image.open(path) as original:
            assert sheets.render_sheet(original)[0] == default.view_sheet(1)[0]
            assert sheets.render_sheet(original, rect=rect)[0] == default.crop(1, *rect)[0]
            assert original.mode == "RGB"
            assert original.getpixel((0, 0)) == COLORS[0]


def test_color_stores_own_independent_images_and_close_them(tmp_path: Path) -> None:
    path = _overlay_png(tmp_path / "overlay.png")
    with sheets.SheetStore([path], preserve_color=True) as survivor:
        with sheets.SheetStore([path, path], preserve_color=True) as first:
            owned = first._sources[path.resolve()]
            assert owned is not survivor._sources[path.resolve()]
            assert first.sheet_count == 2
            assert first.view_sheet(1)[0] == first.view_sheet(2)[0]
        with pytest.raises(ValueError, match="closed"):
            owned.getpixel((0, 0))
        first.close()  # Closing an already closed store remains harmless.
        with pytest.raises(ValueError, match="closed"):
            first.view_sheet(1)
        _assert_overlay_colors(survivor.view_sheet(1)[0])
        survivor_owned = survivor._sources[path.resolve()]
    with pytest.raises(ValueError, match="closed"):
        survivor_owned.getpixel((0, 0))


def test_constructor_failure_closes_owned_color_images(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _overlay_png(tmp_path / "overlay.png")
    opened = []
    prepare_image = sheets._prepare_image

    def observe(image, **kwargs):
        owned = prepare_image(image, **kwargs)
        opened.append(owned)
        return owned

    monkeypatch.setattr(sheets, "_prepare_image", observe)
    with pytest.raises(ValueError, match="PDF or PNG"):
        sheets.SheetStore([path, tmp_path / "invalid.jpg"], preserve_color=True)
    assert len(opened) == 1
    with pytest.raises(ValueError, match="closed"):
        opened[0].getpixel((0, 0))


def test_pdf_color_rendering_and_owned_native_handles_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _pdf(tmp_path / "colored.pdf", ["1 0 0 rg 20 20 40 40 re f\n"])
    _forbid_grayscale(monkeypatch)
    with sheets.SheetStore([path], preserve_color=True) as store:
        document = store._sources[path.resolve()]
        for png in (store.view_sheet(1)[0], store.crop(1, 100, 600, 600, 1150)[0]):
            with Image.open(io.BytesIO(png)) as image:
                assert image.mode in {"RGB", "RGBA"}
                pixels = np.array(image)[:, :, :3]
                assert np.any(np.all(pixels == (255, 0, 0), axis=2))
    assert document.raw is None
    with pytest.raises(ValueError, match="closed"):
        store.view_sheet(1)


def test_default_descriptions_are_unchanged_and_color_mode_preserves_schemas(tmp_path: Path) -> None:
    path = _overlay_png(tmp_path / "overlay.png")
    with sheets.SheetStore([path]) as gray, sheets.SheetStore([path], preserve_color=True) as color:
        gray_tools = asyncio.run(sheets.create_server(gray).list_tools())
        color_tools = asyncio.run(sheets.create_server(color).list_tools())
    expected_descriptions = {
        "view_sheet": (
            "View a 1-based sheet as a grayscale PNG fitted within 1976×1280 pixels. "
            "Sheets follow input order, expanding each PDF in page order. "
            "Call for every sheet in order before judging. The returned image's "
            "top-left pixel coordinates define crop rectangles."
        ),
        "crop": (
            "Zoom a 1-based sheet using integer top-left-origin view_sheet pixels: "
            "0 <= x1 < x2 <= view width and 0 <= y1 < y2 <= view height; "
            "right/bottom edges are exclusive. Output fits 1976×1280 grayscale pixels, "
            "at most 8× the view scale. PDF crops render vectors; PNG crops use the "
            "original image (valid source DPI metadata, otherwise 300 dpi assumed); "
            "PNG effective dpi never exceeds source dpi, as upsampling adds no detail. "
            "Budget: 40 attempted crop calls per process, including invalid calls "
            "and repeats; repeated valid crops reuse a memoized rendering."
        ),
    }
    assert {tool.name: tool.description for tool in gray_tools} == expected_descriptions
    gray_by_name = {tool.name: tool for tool in gray_tools}
    assert {tool.name for tool in color_tools} == {"view_sheet", "crop"}
    for tool in color_tools:
        assert tool.description != expected_descriptions[tool.name]
        assert "color-preserving overlay" in tool.description
        assert "retains red/blue/gray in views and crops" in tool.description
        assert tool.inputSchema == gray_by_name[tool.name].inputSchema
        assert tool.annotations == gray_by_name[tool.name].annotations
        expected = {"sheet"} if tool.name == "view_sheet" else {"sheet", "x1", "y1", "x2", "y2"}
        assert set(tool.inputSchema["properties"]) == expected
        assert set(tool.inputSchema["required"]) == expected


@pytest.mark.parametrize("preserve_color", [False, True])
def test_server_cli_parses_color_flag_and_closes_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, preserve_color: bool
) -> None:
    path = _overlay_png(tmp_path / "overlay.png")
    stores = []
    transports = []

    def create_server(store):
        stores.append(store)
        with Image.open(io.BytesIO(store.view_sheet(1)[0])) as image:
            assert image.mode == ("RGB" if preserve_color else "L")
        return SimpleNamespace(run=lambda *, transport: transports.append(transport))

    monkeypatch.setattr(sheets, "create_server", create_server)
    monkeypatch.setattr(sheets.os, "chdir", lambda _path: None)
    sheets.main([*(["--preserve-color"] if preserve_color else []), str(path)])
    assert transports == ["stdio"]
    assert len(stores) == 1
    with pytest.raises(ValueError, match="closed"):
        stores[0].view_sheet(1)


def test_unchanged_overlays_are_included_without_reclassifying_pages_or_drawings(
    tmp_path: Path,
) -> None:
    common = _square(70, 70)
    for version in ("before", "after"):
        _pdf(tmp_path / version / "unchanged.pdf", [common, ""])
    _pdf(tmp_path / "before/mixed.pdf", [common, common + _square(20, 20)])
    _pdf(tmp_path / "after/mixed.pdf", [common, common + _square(40, 20)])
    _pdf(tmp_path / "before/removed.pdf", [common])
    _pdf(tmp_path / "after/added.pdf", [common])
    options = dict(old_label="before", new_label="after")
    default = diff.create_drawing_diff(
        tmp_path / "before", tmp_path / "after", tmp_path / "default.zip", **options
    )
    included = diff.create_drawing_diff(
        tmp_path / "before", tmp_path / "after", tmp_path / "included.zip",
        include_unchanged=True, **options,
    )
    assert included["page_counts"] == {"changed": 1, "added": 1, "removed": 1, "unchanged": 3}
    assert included["unchanged_drawings"] == ["unchanged.pdf"]
    assert included["changed_drawings"] == ["mixed.pdf"]
    assert len(included["images"]) == len(included["pages"]) == 6
    assert included["images"] == [page["image"] for page in included["pages"]]
    assert len(default["images"]) == 3
    for key in included.keys() - {"asset_path", "images", "pages"}:
        assert included[key] == default[key], key
    with ZipFile(default["asset_path"]) as old_zip, ZipFile(included["asset_path"]) as new_zip:
        summary = json.loads(new_zip.read("summary.json"))
        assert summary == {key: value for key, value in included.items() if key != "asset_path"}
        for old, new in zip(default["pages"], included["pages"], strict=True):
            assert {key: value for key, value in old.items() if key != "image"} == {
                key: value for key, value in new.items() if key != "image"
            }
            png = new_zip.read(new["image"])
            if new["status"] != "unchanged":
                assert png == old_zip.read(old["image"])
                continue
            assert old["image"] is None
            with Image.open(io.BytesIO(png)) as image:
                assert image.mode == "RGB"
                pixels = np.array(image)
                assert np.array_equal(pixels[:, :, 0], pixels[:, :, 1])
                assert np.array_equal(pixels[:, :, 1], pixels[:, :, 2])
                if new["drawing"] == "unchanged.pdf" and new["page"] == 2:
                    assert np.all(pixels == 255)
                else:
                    assert np.any(np.all(pixels == (208, 208, 208), axis=2))
        assert b"3 unchanged (included)" in new_zip.read("index.html")
        assert b"3 unchanged (omitted)" in old_zip.read("index.html")
