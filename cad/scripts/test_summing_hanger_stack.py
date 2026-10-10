from __future__ import annotations

import pytest

import fr_top_frame_spec as top_frame
import vn_knife_hanger_stud_spec as hanger_screw
from build_sm_knife_mount import CASTING_UNDERSIDE_Y
from build_sm_summing_assembly import (
    HANGER_SEAT_Y,
    HANGER_STUD_Y,
    _assert_hanger_axis_positive_y,
)


def _transform(rotation_rows: list[list[float]]) -> list[float]:
    return [
        *(value for row in rotation_rows for value in row),
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
    ]


def test_hanger_screw_seats_its_catalogue_length_on_the_counterbore_floor() -> None:
    # 91251A157 "Length is measured from under the head": the whole catalogue
    # length hangs below the counterbore floor, HANGER_GRIP above the underside.
    assert hanger_screw.UNDERHEAD_LEN == pytest.approx(hanger_screw.LENGTH)
    assert HANGER_SEAT_Y == pytest.approx(CASTING_UNDERSIDE_Y + top_frame.HANGER_GRIP)
    assert HANGER_STUD_Y + hanger_screw.UNDERHEAD_LEN == pytest.approx(HANGER_SEAT_Y)


def test_hanger_axis_validation_accepts_authored_positive_y_axis() -> None:
    _assert_hanger_axis_positive_y(
        "vn-knife-hanger-stud-1",
        _transform([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),
    )


@pytest.mark.parametrize(
    "rotation_rows",
    [
        [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]],
        [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]],
    ],
)
def test_hanger_axis_validation_rejects_transverse_or_reversed_axis(
    rotation_rows: list[list[float]],
) -> None:
    with pytest.raises(RuntimeError, match=r"local \+Y fastener axis.*assembly \+Y"):
        _assert_hanger_axis_positive_y(
            "vn-knife-mount-dowel-1",
            _transform(rotation_rows),
        )
