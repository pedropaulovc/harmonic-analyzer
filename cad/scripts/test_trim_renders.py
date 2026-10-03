"""Consumer-visible image refresh boundaries, without Blender or SolidWorks."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject

import trim_renders


def _colored_pdf(path: Path) -> None:
    writer = PdfWriter()
    for rgb in ((1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0)):
        page = writer.add_blank_page(width=72, height=36)
        content = DecodedStreamObject()
        content.set_data(f"{' '.join(map(str, rgb))} rg 0 0 72 36 re f".encode())
        page.replace_contents(content)
    with path.open("wb") as target:
        writer.write(target)


def test_pdf_thumbnail_uses_requested_sheet_at_full_sheet_resolution(tmp_path: Path) -> None:
    source = tmp_path / "assembly.pdf"
    _colored_pdf(source)
    drive = tmp_path / "drive.png"
    frame = tmp_path / "fr-frame.png"

    trim_renders.render_pdf_sheet(source, drive, 3)
    trim_renders.render_pdf_sheet(source, frame, 2)

    with Image.open(drive) as image:
        assert image.size == (300, 150)
        assert image.convert("RGB").getpixel((150, 75)) == (255, 255, 0)
        assert image.info["dpi"] == pytest.approx((300, 300), abs=0.01)
    with Image.open(frame) as image:
        assert image.size == (300, 150)
        assert image.convert("RGB").getpixel((150, 75)) == (0, 0, 255)


@pytest.mark.parametrize("page_index", [-1, 4])
def test_pdf_thumbnail_refuses_missing_sheet(tmp_path: Path, page_index: int) -> None:
    source = tmp_path / "assembly.pdf"
    _colored_pdf(source)
    target = tmp_path / "thumbnail.png"

    with pytest.raises(ValueError, match="required sheet .* is missing"):
        trim_renders.render_pdf_sheet(source, target, page_index)

    assert not target.exists()


def test_missing_release_inputs_do_not_replace_old_thumbnails(tmp_path: Path) -> None:
    target = tmp_path / "images"
    target.mkdir()
    old = target / "fr-frame.png"
    old.write_bytes(b"previously published frame")

    with pytest.raises(FileNotFoundError, match="required README image sources are missing"):
        trim_renders.regenerate_readme_images(tmp_path / "missing-release", target)

    assert old.read_bytes() == b"previously published frame"
    assert not (target / "dt-pinion-arbor-drawing.png").exists()


def test_incomplete_prepared_set_cannot_partially_replace_images(tmp_path: Path) -> None:
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    target = tmp_path / "images"
    target.mkdir()
    first = trim_renders.README_IMAGE_NAMES[0]
    (prepared / first).write_bytes(b"new image")
    (target / first).write_bytes(b"previous image")

    with pytest.raises(FileNotFoundError, match="required prepared README image is missing"):
        trim_renders.install_readme_images(prepared, target)

    assert (target / first).read_bytes() == b"previous image"


def test_partial_install_reports_replaced_images_and_preserves_remaining_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    target = tmp_path / "images"
    target.mkdir()
    names = trim_renders.README_IMAGE_NAMES
    failed = names[3]
    for name in names:
        (prepared / name).write_bytes(f"new {name}".encode())
        (target / name).write_bytes(f"old {name}".encode())
    replace = trim_renders.os.replace

    def locked_replace(source: Path, destination: Path) -> None:
        if destination == target / failed:
            raise PermissionError(f"locked image: {failed}")
        replace(source, destination)

    monkeypatch.setattr(trim_renders.os, "replace", locked_replace)
    with pytest.raises(PermissionError, match="locked image") as failure:
        trim_renders.install_readme_images(prepared, target)

    assert failure.value.__notes__ == [
        f"partially installed README images: {', '.join(names[:3])}"
    ]
    for name in names[:3]:
        assert (target / name).read_bytes() == f"new {name}".encode()
    for name in names[3:]:
        assert (target / name).read_bytes() == f"old {name}".encode()
    assert not list(target.glob("*.tmp"))


@pytest.mark.parametrize("edge", ["left", "top", "right", "bottom"])
def test_display_pose_rejects_a_machine_clipped_at_any_edge(
    tmp_path: Path, edge: str
) -> None:
    from PIL import ImageDraw, ImageOps

    target = tmp_path / "display-pose.png"
    image = Image.new("RGB", (40, 60), "white")
    bounds = {
        "left": (0, 10, 29, 49),
        "top": (10, 0, 29, 49),
        "right": (10, 10, 39, 49),
        "bottom": (10, 10, 29, 59),
    }[edge]
    ImageDraw.Draw(image).rectangle(bounds, fill="black")
    image.save(target)

    with pytest.raises(ValueError, match="machine touches an image edge"):
        trim_renders.validate_display_pose(target)

    # A one-pixel white margin moves the same machine across the acceptance
    # boundary; the guard must not reject all render output indiscriminately.
    ImageOps.expand(image, border=1, fill="white").save(target)
    trim_renders.validate_display_pose(target)


def test_display_pose_refuses_blank_renderer_output(tmp_path: Path) -> None:
    target = tmp_path / "display-pose.png"
    Image.new("RGB", (40, 60), "white").save(target)

    with pytest.raises(ValueError, match="contains no machine"):
        trim_renders.validate_display_pose(target)
