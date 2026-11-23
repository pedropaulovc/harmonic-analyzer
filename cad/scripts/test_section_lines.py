import pytest

import _drawing_leaders as leaders
import _section_lines as section_lines

# drawing:mg_magnifying_wheel, run 20261122T184921959Z: the face view's
# GetSectionLineInfo2 with A-A (drawn left to right, then reversed) and B-B
# (drawn right to left). Chains in model metres, arrows on the sheet.
LAYER = -1.0
A_A = [
    *(1.0, 4.0, -0.058, 0.0, 0.0, 0.058, 0.0, 0.0),
    *(0.044, 0.138, 0.0, 0.044, 0.15, 0.0, 0.006, 0.003, 1.0),
    *(0.156, 0.138, 0.0, 0.156, 0.15, 0.0, 0.006, 0.003, 1.0),
    *(0.03532645, 0.14800794, 0.0, 0.15847816, 0.14800794, 0.0, 0.00635),
]
B_B = [
    *(1.0, 4.0, 0.022, -0.005588, 0.0, 0.007763, -0.005588, 0.0),
    *(0.12, 0.132412, 0.0, 0.12, 0.144412, 0.0, 0.006, 0.003, 1.0),
    *(0.109763, 0.132412, 0.0, 0.109763, 0.144412, 0.0, 0.006, 0.003, 1.0),
    *(0.12190627, 0.14241994, 0.0, 0.10309104, 0.14241994, 0.0, 0.00635),
]


def _face_view(point):
    # The face view's model-to-view transform in that run: 1:1, at (0.1, 0.15).
    return (point[0] + 0.1, point[1] + 0.15)


def _flat(strokes):
    return [value for stroke in strokes for point in stroke for value in point]


def _shafts(segments):
    # Each line: its chain stroke, then per arrow its shaft and 6 head strokes.
    return [segments[i] for i in (1, 8)]


def test_two_lines_read_a_layer_ahead_of_each() -> None:
    values = [2.0, LAYER, *A_A, LAYER, *B_B]
    segments = section_lines.parse_section_lines(values, _face_view)
    assert len(segments) == 2 * (1 + 2 * 7)
    a_a, b_b = segments[:15], segments[15:]
    assert _flat([a_a[0]]) == pytest.approx([0.042, 0.15, 0.158, 0.15])
    assert _flat([b_b[0]]) == pytest.approx([0.122, 0.144412, 0.107763, 0.144412])
    # The help's single-layer reading: r10's failure.
    with pytest.raises(
        RuntimeError, match=r"section arrow 1: .*chain on the sheet \[\]"
    ):
        leaders.parse_section_line_info(values, _face_view)
    with pytest.raises(RuntimeError, match="parsed"):
        section_lines.parse_section_lines([*values, 0.0], _face_view)


def test_one_line_layout_reads_as_drawing_leaders_does() -> None:
    values = [1.0, LAYER, *A_A]
    ours = section_lines.parse_section_lines(values, _face_view)
    theirs = leaders.parse_section_line_info(values, _face_view)
    assert len(ours) == len(theirs)
    assert ours[0] == theirs[0]  # the chain


def test_arrows_are_where_the_sheet_prints_them() -> None:
    # MHA-MG-05 (mg-magnifying-wheel.pdf, run 20261121T201300466Z) prints
    # A-A's left arrow from the chain's end (0.042, 0.150) up to (0.042,
    # 0.162); _drawing_leaders tips the reported shaft down, below the line.
    a_a = section_lines.parse_section_lines([1.0, LAYER, *A_A], _face_view)
    printed = [((0.042, 0.15), (0.042, 0.162)), ((0.158, 0.15), (0.158, 0.162))]
    assert _flat(_shafts(a_a)) == pytest.approx(_flat(printed))
    # _drawing_leaders tips arrow 1's head at (0.044, 0.138), below the line.
    mirrored = leaders.parse_section_line_info([1.0, LAYER, *A_A], _face_view)
    assert mirrored[2][0] == pytest.approx((0.044, 0.138))
    assert a_a[2][0] == pytest.approx((0.042, 0.162))
    # B-B drawn right to left looked along +y: its arrows up from its ends.
    b_b = section_lines.parse_section_lines([1.0, LAYER, *B_B], _face_view)
    up = [
        ((0.122, 0.144412), (0.122, 0.156412)),
        ((0.107763, 0.144412), (0.107763, 0.156412)),
    ]
    assert _flat(_shafts(b_b)) == pytest.approx(_flat(up))


def test_an_arrow_off_its_chain_end_raises() -> None:
    floating = [*A_A]
    floating[8] = 0.050  # arrow 1's start x
    floating[11] = 0.050  # its end x: 8 mm in, not 2
    with pytest.raises(RuntimeError, match="section arrow 1: reported"):
        section_lines.parse_section_lines([1.0, LAYER, *floating], _face_view)
