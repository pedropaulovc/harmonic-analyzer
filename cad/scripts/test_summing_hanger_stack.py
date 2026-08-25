from __future__ import annotations

import pytest

from build_summing_assembly import _assert_hanger_axis_positive_y


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
