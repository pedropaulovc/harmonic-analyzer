import pytest

import _drawing_leaders as leaders
import _section_lines as section_lines

LAYER = 0
TEXT = [0.13, 0.1, 0.0, 0.13, 0.3, 0.0, 0.005]


def _line(chain_start, chain_end, tip1, tip2) -> list[float]:
    """One line: a single chain segment (lineType 4), each arrow tailed on a
    chain end, then the labels."""
    arrow1 = [*chain_start, *tip1, 0.002, 0.004, 1]
    arrow2 = [*chain_end, *tip2, 0.002, 0.004, 1]
    return [1, 4, *chain_start, *chain_end, *arrow1, *arrow2, *TEXT]


# One vertical line, as dt_crank_drive_gear's face view carries.
A_A = _line((0.1, 0.1, 0.0), (0.1, 0.3, 0.0), (0.12, 0.1, 0.0), (0.12, 0.3, 0.0))
# Run 20261121T071639071Z, drawing:mg_magnifying_wheel: B-B's own values as
# the help's reading took them for its arrow 1 -- nSegments 1, lineType 4,
# the chain at TIE 1's y from x 22.0 to 7.763 mm -- then arrows on its ends.
B_B = _line(
    (0.022, -0.005588, 0.0),
    (0.007763, -0.005588, 0.0),
    (0.022, -0.015, 0.0),
    (0.007763, -0.015, 0.0),
)


def test_one_line_reads_as_drawing_leaders_does() -> None:
    values = [1, LAYER, *A_A]
    expected = leaders.parse_section_line_info(values)
    assert section_lines.parse_section_lines(values) == expected
    assert section_lines.parse_section_lines([]) == []


def test_two_lines_read_a_layer_ahead_of_each() -> None:
    values = [2, LAYER, *A_A, LAYER, *B_B]
    first = leaders.parse_section_line_info([1, LAYER, *A_A])
    second = leaders.parse_section_line_info([1, LAYER, *B_B])
    assert section_lines.parse_section_lines(values) == [*first, *second]
    assert ((0.022, -0.005588), (0.007763, -0.005588)) in second
    # The help's single-layer reading: r10's failure.
    with pytest.raises(
        RuntimeError, match=r"section arrow 1: .*chain on the sheet \[\]"
    ):
        leaders.parse_section_line_info(values)
    with pytest.raises(RuntimeError, match="parsed"):
        section_lines.parse_section_lines([*values, 0.0])
