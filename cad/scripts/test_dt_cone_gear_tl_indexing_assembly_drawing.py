"""Offline contract of the cone-gear indexing-kit fitter sheet (MHA-DT-03-TL-00)."""

from __future__ import annotations

import pytest

import draw_dt_cone_gear_tl_indexing_assembly as drawing
from _machinist_review_mode import MachinistReviewMode


def test_the_kit_sheet_is_reviewed_under_enforce() -> None:
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE


def test_the_exploded_view_draws_the_head_hub_and_each_visible_screw() -> None:
    lines = drawing.exploded_lines()
    # Two mount axes show edge-on: 150 and 30 degrees coincide.
    assert len(drawing.mount_axis_heights()) == 2
    assert len(lines["screw"]) == 6 * len(drawing.mount_axis_heights())
    assert {"head face", "hub top", "hub bottom", "hub end"} <= set(lines["phantom"])
    # Exploded: the hub stops short of the plate's back face and the screw
    # tips stand clear of its countersunk face.
    assert drawing.HEAD_FACE_Z < -drawing.HEAD_GAP < 0.0
    assert drawing.SCREW_TIP_Z > drawing.plate.THICKNESS


def _overlaps(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


@pytest.mark.parametrize("plus_z_screen", (-1.0, 1.0))
def test_exploded_labels_stay_apart_and_inside_the_border(plus_z_screen) -> None:
    cx, cy = drawing.EXPLODED_CENTER

    def sheet(point):
        return (cx + plus_z_screen * point[2] / 1000.0, cy + point[1] / 1000.0)

    tips = {text: sheet(point) for text, point in drawing.LABEL_TIPS.items()}
    head_top = sheet(drawing._yz(drawing.HEAD_HALF, drawing.HEAD_FACE_Z))[1]
    boxes = drawing.label_boxes(drawing.exploded_label_positions(tips, head_top))
    left, bottom, right, top = drawing.SHEET_INNER_BORDER
    for text, box in boxes.items():
        assert left < box[0] and box[2] < right and bottom < box[1] and box[3] < top, (
            text
        )
    texts = list(boxes)
    for i, a in enumerate(texts):
        for b in texts[i + 1 :]:
            assert not _overlaps(boxes[a], boxes[b]), (a, b)
