"""The catalogue inch-fraction printer the BOM and ITEM rows share."""

from __future__ import annotations

import pytest

from _inch_fraction import inch_fraction


@pytest.mark.parametrize(
    ("inches", "printed"),
    (
        (1.0 / 64.0, "1/64"),
        (5.0 / 16.0, "5/16"),
        (7.0 / 16.0, "7/16"),
        (1.0, "1"),
        (1.25, "1-1/4"),
        (2.0 + 63.0 / 64.0, "2-63/64"),
    ),
)
def test_a_catalogue_length_prints_as_its_fraction(inches: float, printed: str) -> None:
    assert inch_fraction(inches * 25.4, what="screw length") == printed


@pytest.mark.parametrize(
    "length_mm",
    (
        8.0,  # metric stock: 0.31496 in, nearest 1/64 is 5/16 (7.9375)
        5.0 / 16.0 * 25.4 + 1e-6,  # 1 nm off the fraction still refuses
        1.0 / 128.0 * 25.4,  # finer than the catalogue's 1/64
        0.0,
        -5.0 / 16.0 * 25.4,
    ),
)
def test_a_length_off_the_sixty_fourths_refuses(length_mm: float) -> None:
    with pytest.raises(ValueError, match=r"screw length: .* 1/64 in"):
        inch_fraction(length_mm, what="screw length")
