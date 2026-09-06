"""Conservative native leader/text-cell crossing and alternative column contracts."""

from types import SimpleNamespace

import pytest

from _drawing_annotation_bounds import Segment
from _drawing_view_packing import Rect
from probe_drawing_right_gtol_column import (
    intersects_cell,
    right_translation,
    crossing_records,
    _same_native,
    _same_saved_frames,
)


@pytest.mark.parametrize(
    "start,end,expected",
    [
        ((0, 0.5), (2, 0.5), True),
        ((0, 2), (2, 2), False),
        ((0.5, 0.5), (0.5, 0.5), True),
        ((0, 0), (1, 1), True),
        ((-2, -2), (-1, -1), False),
    ],
)
def test_clipping_includes_touching_and_handles_degenerate_segments(
    start, end, expected
):
    assert (
        intersects_cell(Segment(start, end), Rect(0.25, 0.25, 0.75, 0.75)) is expected
    )


def test_right_column_keeps_y_and_clears_dimension_on_its_ray():
    delta = right_translation(
        Rect(0, 0, 0.02, 0.05),
        Rect(0.03, 0, 0.1, 0.1),
        (Rect(0.105, 0, 0.13, 0.05), Rect(0.3, 0.2, 0.4, 0.3)),
    )
    assert delta == pytest.approx((0.133, 0))


def test_crossing_report_excludes_intentional_own_frame_join():
    box = SimpleNamespace(
        kind=4,
        text_boxes=(Rect(0.25, 0.25, 0.75, 0.75),),
        text_runs=(SimpleNamespace(value="127"),),
    )
    rows = crossing_records(
        {"frame": (Segment((0, 0.5), (1, 0.5)),)}, {"frame": box, "dim": box}
    )
    assert len(rows) == 1
    assert rows[0]["target_annotation"] == "dim"
    assert rows[0]["target_text"] == ["127"]


def test_exact_entity_replacement_cannot_hide_behind_same_dimension_type():
    app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    annotation, entity = object(), object()
    before = {"dim": (annotation, 4, (entity,), (1,))}
    _same_native(app, before, before)
    with pytest.raises(RuntimeError, match="identity changed"):
        _same_native(app, before, {"dim": (annotation, 4, (object(),), (1,))})


@pytest.mark.parametrize(
    "field,value",
    [
        ("frames", ("differentXML",)),
        ("text", ("different tolerance",)),
        ("position", (0.1, 0.205, 0)),
    ],
)
def test_saved_frame_witness_rejects_content_or_layout_change(field, value):
    row = {
        "frames": ("nativeXML",),
        "text": ("0.05 A B",),
        "format": ("font",),
        "attachment_types": (1,),
        "position": (0.1, 0.2, 0),
        "body": (0.1, 0.2, 0.13, 0.207),
    }
    _same_saved_frames({"frame": row}, {"frame": row})
    with pytest.raises(RuntimeError, match="saved/reopened"):
        _same_saved_frames({"frame": row}, {"frame": {**row, field: value}})
