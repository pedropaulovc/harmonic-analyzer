"""Consumer-visible drawing overlays, using real synthetic vector/text PDFs."""

from __future__ import annotations

import io
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pytest
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    RectangleObject,
)

import _drawing_diff as diff


def _pdf(
    path: Path,
    pages: list[str],
    *,
    size: tuple[float, float] = (144, 144),
    rotation: int = 0,
    crop: tuple[float, float, float, float] | None = None,
) -> Path:
    """Write actual PDF content streams, with no renderer or parser mocks."""
    writer = PdfWriter()
    font = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Courier"),
            }
        )
    )
    for content in pages:
        page = writer.add_blank_page(width=size[0], height=size[1])
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        stream.set_data(content.encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
        if rotation:
            page.rotate(rotation)
        if crop is not None:
            page.cropbox = RectangleObject(crop)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def _text(text: str, x: float, y: float, size: float = 10) -> str:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return f"0 g BT /F1 {size} Tf {x} {y} Td ({escaped}) Tj ET\n"


def _square(x: float, y: float, side: float = 8) -> str:
    return f"0 g {x} {y} {side} {side} re f\n"


def _stamps(revision: str, build: str) -> str:
    # REV is stacked and centered; BUILD is inline, as in the project templates.
    # Courier advances exactly 0.6 em, so digit-count changes remain centered.
    return (
        _text("REV", 1080 - 3 * 8 * 0.6 / 2, 90, 8)
        + _text(revision, 1080 - len(revision) * 16 * 0.6 / 2, 70, 16)
        + _text(f"BUILD {build}", 650, 17, 7)
    )


def _compare(tmp_path: Path, *, old_label: str = "v42", new_label: str = "v43") -> dict:
    return diff.create_drawing_diff(
        tmp_path / "old",
        tmp_path / "new",
        tmp_path / "drawing-diff.zip",
        old_label=old_label,
        new_label=new_label,
    )


def _pixels(facts: dict, index: int = 0) -> np.ndarray:
    with ZipFile(facts["asset_path"]) as archive:
        with Image.open(io.BytesIO(archive.read(facts["images"][index]))) as image:
            return np.array(image.convert("RGB"))


def _has_color(pixels: np.ndarray, color: tuple[int, int, int]) -> bool:
    return bool(np.any(np.all(pixels == color, axis=2)))


def test_overlay_colors_removed_added_and_shared_ink(tmp_path: Path) -> None:
    _pdf(tmp_path / "old/part.pdf", [_square(20, 20) + _square(70, 70)])
    _pdf(tmp_path / "new/part.pdf", [_square(40, 20) + _square(70, 70)])

    facts = _compare(tmp_path)

    assert facts["changed_drawings"] == ["part.pdf"]
    assert facts["page_counts"] == {"changed": 1, "added": 0, "removed": 0, "unchanged": 0}
    pixels = _pixels(facts)
    assert _has_color(pixels, (220, 32, 32))
    assert _has_color(pixels, (0, 96, 224))
    assert _has_color(pixels, (208, 208, 208))


def test_first_release_includes_all_pages_even_blank_and_preserves_paths(tmp_path: Path) -> None:
    _pdf(tmp_path / "new/left/part.pdf", [_square(20, 20), ""])
    _pdf(tmp_path / "new/right/part.PDF", [_square(40, 40)])

    facts = diff.create_drawing_diff(
        None,
        tmp_path / "new",
        tmp_path / "first.zip",
        old_label="no previous release",
        new_label="v1",
    )

    assert facts["added_drawings"] == ["left/part.pdf", "right/part.PDF"]
    assert facts["changed_drawings"] == facts["removed_drawings"] == []
    assert facts["images"] == [
        "images/left/part.pdf/page-0001.png",
        "images/left/part.pdf/page-0002.png",
        "images/right/part.PDF/page-0001.png",
    ]
    assert facts["page_counts"]["added"] == 3
    pixels = _pixels(facts)
    assert _has_color(pixels, (0, 96, 224))
    assert not _has_color(pixels, (220, 32, 32))
    with ZipFile(facts["asset_path"]) as archive:
        assert not any(name.lower().endswith(".pdf") for name in archive.namelist())
        assert {"summary.json", "index.html"} <= set(archive.namelist())


def test_added_removed_pdfs_and_pages_are_classified_separately(tmp_path: Path) -> None:
    first, second = _square(10, 10), _square(30, 30)
    _pdf(tmp_path / "old/extended.pdf", [first])
    _pdf(tmp_path / "new/extended.pdf", [first, second])
    _pdf(tmp_path / "old/shortened.pdf", [first, second])
    _pdf(tmp_path / "new/shortened.pdf", [first])
    _pdf(tmp_path / "old/deleted/part.pdf", [first])
    _pdf(tmp_path / "new/created/part.pdf", [second])
    _pdf(tmp_path / "old/unchanged.pdf", [first])
    _pdf(tmp_path / "new/unchanged.pdf", [first])

    facts = _compare(tmp_path)

    assert facts["changed_drawings"] == ["extended.pdf", "shortened.pdf"]
    assert facts["added_drawings"] == ["created/part.pdf"]
    assert facts["removed_drawings"] == ["deleted/part.pdf"]
    assert facts["unchanged_drawings"] == ["unchanged.pdf"]
    assert facts["page_counts"] == {"changed": 0, "added": 2, "removed": 2, "unchanged": 3}
    removed_image = next(
        i for i, name in enumerate(facts["images"]) if "deleted/part.pdf" in name
    )
    assert _has_color(_pixels(facts, removed_image), (220, 32, 32))
    assert not _has_color(_pixels(facts, removed_image), (0, 96, 224))
    assert all(page["image"] is None for page in facts["pages"] if page["status"] == "unchanged")


@pytest.mark.parametrize(("before", "after"), [("v9", "v100-dirty"), ("v100-dirty", "v8")])
def test_only_build_revision_values_are_ignored_without_width_residue(
    tmp_path: Path, before: str, after: str
) -> None:
    body = _square(400, 400) + _text("SCALE: 2:1 UNIT: mm", 1100, 45, 8)
    _pdf(
        tmp_path / "old/part.pdf",
        [body + _stamps(before.removesuffix("-dirty"), before)],
        size=(1224, 792),
    )
    _pdf(
        tmp_path / "new/part.pdf",
        [body + _stamps(after.removesuffix("-dirty"), after)],
        size=(1224, 792),
    )

    facts = _compare(tmp_path)

    assert facts["images"] == []
    assert facts["unchanged_drawings"] == ["part.pdf"]
    with ZipFile(facts["asset_path"]) as archive:
        assert set(archive.namelist()) == {"summary.json", "index.html"}


@pytest.mark.parametrize("location", ["main_note", "title_note", "near_stamp", "outside_title_build"])
def test_version_notes_and_neighboring_title_block_ink_are_not_normalized(
    tmp_path: Path, location: str
) -> None:
    def content(version: str) -> str:
        result = _stamps("v42", "v42")
        if location == "main_note":
            result += _text("REV", 100, 500, 8) + _text(version, 100, 480, 16)
        elif location == "title_note":
            result += _text(f"USE {version} TOOL", 900, 145)
        elif location == "outside_title_build":
            result += _text(f"BUILD {version}", 650, 250, 7)
        else:
            result += _text(f"SCALE: {version}", 1120, 70, 8)
        return result

    _pdf(tmp_path / "old/part.pdf", [content("v9")], size=(1224, 792))
    _pdf(tmp_path / "new/part.pdf", [content("v8")], size=(1224, 792))

    facts = _compare(tmp_path)

    assert facts["changed_drawings"] == ["part.pdf"]
    assert len(facts["images"]) == 1
    assert facts["pages"][0]["text_changed"] is True
    # Small antialiased glyphs need not contain any fully covered pixel. The
    # consumer-visible contract is red/blue ink, not exact solid-fill RGB.
    pixels = _pixels(facts).astype(np.int16)
    red, green, blue = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
    assert np.any((red > green + 20) & (red > blue + 20))
    assert np.any((blue > red + 20) & (blue > green + 20))


@pytest.mark.parametrize("change", ["tiny_geometry", "tiny_dimension_text", "decimal_point"])
def test_small_meaningful_edits_have_no_changed_area_cutoff(tmp_path: Path, change: str) -> None:
    before = _square(50, 50, 40)
    after = before
    if change == "tiny_geometry":
        after += _square(20, 20, 0.5)
    elif change == "tiny_dimension_text":
        before += _text("10.2", 20, 20, 4)
        after += _text("10.3", 20, 20, 4)
    else:
        before += _text("102", 20, 20, 6)
        after += _text("10.2", 20, 20, 6)
    _pdf(tmp_path / "old/part.pdf", [before])
    _pdf(tmp_path / "new/part.pdf", [after])

    facts = _compare(tmp_path)

    assert facts["changed_drawings"] == ["part.pdf"]
    assert len(facts["images"]) == 1
    pixels = _pixels(facts).astype(np.int16)
    assert np.any((pixels[:, :, 2] > pixels[:, :, 0] + 20))


def test_minor_raster_antialiasing_is_ignored(tmp_path: Path) -> None:
    def line(x: float) -> str:
        return f"0 G 0.5 w {x} 20 m 110 101 l S\n"

    _pdf(tmp_path / "old/part.pdf", [line(20)])
    _pdf(tmp_path / "new/part.pdf", [line(20.0001)])

    facts = _compare(tmp_path)

    assert facts["images"] == []
    assert facts["unchanged_drawings"] == ["part.pdf"]


@pytest.mark.parametrize(("dx", "dy"), [(0.5, 0), (0, 0.5), (0.5, 0.5)])
@pytest.mark.parametrize("before_gray", [0, 0.25])
def test_one_pixel_edge_displacement_is_omitted(
    tmp_path: Path, dx: float, dy: float, before_gray: float
) -> None:
    # At 144 dpi, half a PDF point is one pixel. Diagonal matching uses the
    # documented Chebyshev bound, not a one-pixel Euclidean circle.
    before = _square(20, 20).replace("0 g", f"{before_gray} g", 1)
    _pdf(tmp_path / "old/part.pdf", [before])
    _pdf(tmp_path / "new/part.pdf", [_square(20 + dx, 20 + dy)])

    facts = _compare(tmp_path)

    assert facts["images"] == []
    assert facts["unchanged_drawings"] == ["part.pdf"]


@pytest.mark.parametrize(("dx", "dy"), [(1, 0), (0, 1), (1, 1)])
def test_edge_displacement_beyond_one_pixel_is_retained(
    tmp_path: Path, dx: float, dy: float
) -> None:
    _pdf(tmp_path / "old/part.pdf", [_square(20, 20)])
    _pdf(tmp_path / "new/part.pdf", [_square(20 + dx, 20 + dy)])

    facts = _compare(tmp_path)

    assert facts["changed_drawings"] == ["part.pdf"]
    pixels = _pixels(facts)
    assert _has_color(pixels, (220, 32, 32))
    assert _has_color(pixels, (0, 96, 224))


@pytest.mark.parametrize("removed", [False, True])
def test_isolated_single_pixel_feature_next_to_matched_edge_is_retained(
    tmp_path: Path, removed: bool
) -> None:
    common = _square(20, 20)
    # The mark is only one pixel, two pixels from the nearest common ink:
    # neither page area nor a larger matching neighborhood may erase it.
    with_mark = common + _square(28.5, 20, 0.5)
    _pdf(tmp_path / "old/part.pdf", [with_mark if removed else common])
    _pdf(tmp_path / "new/part.pdf", [common if removed else with_mark])

    facts = _compare(tmp_path)

    assert facts["changed_drawings"] == ["part.pdf"]
    assert _has_color(_pixels(facts), (220, 32, 32) if removed else (0, 96, 224))


@pytest.mark.parametrize("contrast", [68, 69, 255])
@pytest.mark.parametrize("removed", [False, True])
def test_unmatched_ink_has_an_inclusive_intensity_bound(
    contrast: int, removed: bool
) -> None:
    # Exact grayscale inputs pin the numerical bound independently of a PDF
    # renderer's grayscale conversion. The PDF tests cover archive behavior.
    blank = np.full((7, 7), 255, dtype=np.uint8)
    marked = blank.copy()
    marked[3, 3] = 255 - contrast
    before, after = (marked, blank) if removed else (blank, marked)

    png, text_changed = diff._overlay(
        diff._Raster(before, (3.5, 3.5), [], ()),
        diff._Raster(after, (3.5, 3.5), [], ()),
    )

    assert (png is not None) is (contrast > 68)
    assert text_changed is False


def test_neighborhood_does_not_wrap_between_opposite_page_edges() -> None:
    before = np.full((7, 7), 255, dtype=np.uint8)
    after = before.copy()
    before[3, 0] = 0
    after[3, -1] = 0

    png, _ = diff._overlay(
        diff._Raster(before, (3.5, 3.5), [], ()),
        diff._Raster(after, (3.5, 3.5), [], ()),
    )

    assert png is not None


def test_faint_printed_character_edit_bypasses_both_tolerances(tmp_path: Path) -> None:
    before = _text("10.2", 20, 20, 4).replace("0 g", "0.9 g", 1)
    after = _text("10.3", 20, 20, 4).replace("0 g", "0.9 g", 1)
    _pdf(tmp_path / "old/part.pdf", [before])
    _pdf(tmp_path / "new/part.pdf", [after])

    facts = _compare(tmp_path)

    assert facts["changed_drawings"] == ["part.pdf"]
    assert facts["pages"][0]["text_changed"] is True
    pixels = _pixels(facts).astype(np.int16)
    assert np.any(pixels[:, :, 0] > pixels[:, :, 2])
    assert np.any(pixels[:, :, 2] > pixels[:, :, 0])


def test_reordered_characters_with_the_same_inventory_still_compare_ink(tmp_path: Path) -> None:
    _pdf(tmp_path / "old/part.pdf", [_text("12", 20, 20)])
    _pdf(tmp_path / "new/part.pdf", [_text("21", 20, 20)])

    facts = _compare(tmp_path)

    assert facts["changed_drawings"] == ["part.pdf"]
    assert facts["pages"][0]["text_changed"] is False
    pixels = _pixels(facts).astype(np.int16)
    assert np.any(pixels[:, :, 0] > pixels[:, :, 2])
    assert np.any(pixels[:, :, 2] > pixels[:, :, 0])


@pytest.mark.parametrize("with_antialias_noise", [False, True])
def test_identical_ink_with_different_text_object_segmentation_is_omitted(
    tmp_path: Path, with_antialias_noise: bool
) -> None:
    before = _text("1234", 20, 20)
    after = _text("12", 20, 20) + _text("34", 32, 20)
    if with_antialias_noise:
        before += "0 G 0.5 w 20 20 m 110 101 l S\n"
        after += "0 G 0.5 w 20.0001 20 m 110 101 l S\n"
    _pdf(tmp_path / "old/part.pdf", [before])
    _pdf(tmp_path / "new/part.pdf", [after])

    facts = _compare(tmp_path)

    assert facts["images"] == []
    assert facts["unchanged_drawings"] == ["part.pdf"]


def test_changed_blank_page_dimensions_are_not_omitted(tmp_path: Path) -> None:
    _pdf(tmp_path / "old/part.pdf", [""], size=(144, 144))
    _pdf(tmp_path / "new/part.pdf", [""], size=(145, 144))

    facts = _compare(tmp_path)

    assert facts["changed_drawings"] == ["part.pdf"]
    assert len(facts["images"]) == 1
    assert facts["pages"][0]["old_size_points"] == [144, 144]
    assert facts["pages"][0]["new_size_points"] == [145, 144]


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_rotated_cropped_page_ink_is_compared_in_display_coordinates(
    tmp_path: Path, rotation: int
) -> None:
    _pdf(
        tmp_path / "old/part.pdf", [_square(30, 30)], rotation=rotation, crop=(10, 10, 130, 130)
    )
    _pdf(
        tmp_path / "new/part.pdf", [_square(50, 30)], rotation=rotation, crop=(10, 10, 130, 130)
    )

    facts = _compare(tmp_path)

    assert _pixels(facts).shape == (240, 240, 3)
    assert _has_color(_pixels(facts), (220, 32, 32))
    assert _has_color(_pixels(facts), (0, 96, 224))


def test_empty_inventory_writes_usable_deterministic_serializable_archive(tmp_path: Path) -> None:
    (tmp_path / "old").mkdir()
    (tmp_path / "new").mkdir()
    facts = _compare(tmp_path, old_label="v1<&", new_label="v2<&")
    second = diff.create_drawing_diff(
        tmp_path / "old",
        tmp_path / "new",
        tmp_path / "second.zip",
        old_label="v1<&",
        new_label="v2<&",
    )

    assert Path(facts["asset_path"]).read_bytes() == Path(second["asset_path"]).read_bytes()
    assert json.loads(json.dumps(facts))["asset_path"] == facts["asset_path"]
    assert facts["drawing_counts"] == {"changed": 0, "added": 0, "removed": 0, "unchanged": 0}
    with ZipFile(facts["asset_path"]) as archive:
        summary = json.loads(archive.read("summary.json"))
        assert summary["images"] == []
        assert "asset_path" not in summary
        index = archive.read("index.html").decode("utf-8")
        assert "v1&lt;&amp;" in index and "v2&lt;&amp;" in index


@pytest.mark.parametrize("bad_input", [b"not a PDF", b"%PDF-1.7\ncorrupt"])
def test_corrupt_pdf_raises_without_replacing_existing_archive(tmp_path: Path, bad_input: bytes) -> None:
    (tmp_path / "old").mkdir()
    (tmp_path / "new").mkdir()
    (tmp_path / "new/broken.pdf").write_bytes(bad_input)
    destination = tmp_path / "drawing-diff.zip"
    destination.write_bytes(b"existing release asset")

    with pytest.raises(ValueError, match="broken.pdf"):
        _compare(tmp_path)

    assert destination.read_bytes() == b"existing release asset"
    assert set(tmp_path.iterdir()) == {tmp_path / "old", tmp_path / "new", destination}


def test_zero_page_pdf_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "old").mkdir()
    _pdf(tmp_path / "new/empty.pdf", [])

    with pytest.raises(ValueError, match="empty.pdf"):
        _compare(tmp_path)

    assert not (tmp_path / "drawing-diff.zip").exists()


def test_missing_pdf_directory_does_not_silently_become_removed_inventory(tmp_path: Path) -> None:
    (tmp_path / "new").mkdir()

    with pytest.raises(ValueError, match="directory does not exist"):
        _compare(tmp_path)


def test_cli_writes_json_facts_and_renderer_releases_input_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _pdf(tmp_path / "new/part.pdf", [_square(20, 20)])
    target = tmp_path / "cli.zip"

    assert diff.main([str(tmp_path / "new"), str(target), "--new-label", "v1"]) == 0

    facts = json.loads(capsys.readouterr().out)
    assert facts["asset_path"] == str(target)
    assert facts["added_drawings"] == ["part.pdf"]
    # In particular Windows callers must be able to remove/move staged PDFs
    # immediately after generation; no native PDFium handle retains the input.
    source.unlink()
    assert not source.exists()
