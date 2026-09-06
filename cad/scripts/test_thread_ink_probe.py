"""The exported-ink comparison must see strokes, not just page bounding boxes."""

from PIL import Image
import pytest

from probe_drawing_thread_ink import ink_difference


def test_identical_exports_have_no_ink_difference(tmp_path):
    first, second = tmp_path / "a.png", tmp_path / "b.png"
    image = Image.new("RGB", (10, 10), "white")
    image.save(first)
    image.save(second)
    assert ink_difference(first, second)["difference_box_pixels"] is None


def test_one_changed_internal_stroke_pixel_is_detected(tmp_path):
    first, second = tmp_path / "a.png", tmp_path / "b.png"
    image = Image.new("RGB", (10, 10), "white")
    image.save(first)
    image.putpixel((3, 4), (0, 0, 0))
    image.save(second)
    assert ink_difference(first, second)["difference_box_pixels"] == (3, 4, 4, 5)


def test_different_page_sizes_are_not_a_valid_visibility_witness(tmp_path):
    first, second = tmp_path / "a.png", tmp_path / "b.png"
    Image.new("RGB", (10, 10), "white").save(first)
    Image.new("RGB", (20, 10), "white").save(second)
    with pytest.raises(ValueError, match="dimensions differ"):
        ink_difference(first, second)
