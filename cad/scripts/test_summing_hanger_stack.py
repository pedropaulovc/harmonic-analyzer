from __future__ import annotations

import pytest

from build_knife_hanger_stud import UNDERHEAD_LEN
from knife_hanger_stud_spec import (
    FINISHED_UNDERHEAD_MM,
    STOCK_UNDERHEAD_MM,
    TRIM_LENGTH_MM,
)
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


def test_hanger_bolt_seats_its_trimmed_length_without_the_washer_face() -> None:
    # The purchased underhead still excludes the integral washer face ...
    assert STOCK_UNDERHEAD_MM == pytest.approx(GB_LEN - GB_WASHER_T)
    # ... and the assembly seats the FINISHED length, the stock trimmed to
    # the measured stack.
    assert UNDERHEAD_LEN == FINISHED_UNDERHEAD_MM
    assert FINISHED_UNDERHEAD_MM == pytest.approx(STOCK_UNDERHEAD_MM - TRIM_LENGTH_MM)


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
