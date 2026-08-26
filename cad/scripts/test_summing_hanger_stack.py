from __future__ import annotations

import pytest

from build_knife_hanger_stud import UNDERHEAD_LEN
from build_summing_assembly import _assert_hanger_axis_positive_y
from diagnostics.diag_build_91247A720 import GB_LEN, GB_WASHER_T


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


def test_hanger_bolt_seating_length_excludes_integral_washer_face() -> None:
    assert GB_LEN - UNDERHEAD_LEN == pytest.approx(GB_WASHER_T)


def test_hanger_axis_validation_accepts_authored_positive_y_axis() -> None:
    _assert_hanger_axis_positive_y(
        "knife-hanger-washer-1",
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
            "knife-hanger-washer-1",
            _transform(rotation_rows),
        )
