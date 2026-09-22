"""Offline manufacturing boundaries for the shortened purchased stud."""

import math

import pytest

import draw_knife_hanger_stud as drawing
import knife_hanger_stud_spec as spec
from _hole_spec import TAP_DRILL_MM
from diagnostics.diag_build_91247A720 import GB_MAJOR_R


def test_root_chamfer_flat_clears_the_receiving_tap_drill() -> None:
    tap_drill = TAP_DRILL_MM["1/2-13"]
    flat_diameter = 2.0 * (GB_MAJOR_R - spec.CHAMFER_WIDTH_MM)
    assert flat_diameter < tap_drill


def test_iso_fit_translation_centres_the_outline_with_clearance() -> None:
    # The measured pictorial outline at 1.5:1 (54.3 x 101.4 mm: GetOutline is
    # 72.4 x 135.2 mm at 2:1 -- 1.37x the rendered ink -- scaled by 0.75).
    box = (0.330, 0.150, 0.3843, 0.2514)
    dx, dy = drawing._fit_translation(box, drawing.ISO_REGION, drawing.ISO_FIT_MARGIN_M)
    moved = (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)
    region = drawing.ISO_REGION
    margin = drawing.ISO_FIT_MARGIN_M
    assert moved[0] >= region[0] + margin and moved[2] <= region[2] - margin
    assert moved[1] >= region[1] + margin and moved[3] <= region[3] - margin
    # Centring splits the remaining slack evenly: no side is starved of margin.
    assert moved[0] - region[0] == pytest.approx(region[2] - moved[2])
    assert moved[1] - region[1] == pytest.approx(region[3] - moved[3])


def test_iso_fit_rejects_an_outline_that_cannot_fit() -> None:
    with pytest.raises(RuntimeError, match="cannot fit"):
        drawing._fit_translation((0.0, 0.0, 0.1, 0.12), drawing.ISO_REGION, drawing.ISO_FIT_MARGIN_M)


class _FakeDisplay:
    """Records ``SetText`` part writes the way IDisplayDimension stores them."""

    def __init__(self, parts: dict[int, str], *, shows_value: bool = True) -> None:
        self.parts = dict(parts)
        self.writes: list[tuple[int, str]] = []
        self.ShowDimensionValue = shows_value

    def SetText(self, part: int, text: str) -> None:
        self.writes.append((part, text))
        self.parts[part] = text

    def GetText(self, part: int) -> str:
        return self.parts.get(part, "")


def test_root_finish_words_ride_the_value_as_its_suffix() -> None:
    # stud-4's part-7 write left the prefix filled and the value switched off.
    display = _FakeDisplay({1: "stale", 3: "stale"}, shows_value=False)
    drawing._write_root_finish_callout(display, drawing.ROOT_FINISH_SUFFIX)
    assert display.writes == [
        (drawing.PREFIX, ""),
        (drawing.CALLOUT_ABOVE, ""),
        (drawing.CALLOUT_BELOW, ""),
        (drawing.SUFFIX, drawing.ROOT_FINISH_SUFFIX),
    ]
    assert display.ShowDimensionValue is True
    drawing._assert_root_finish_callout(display, drawing.ROOT_FINISH_SUFFIX)


def test_root_finish_suffix_is_one_line() -> None:
    # A multi-line suffix printed only its last line on the tube-frame chamfer.
    assert "\n" not in drawing.ROOT_FINISH_SUFFIX


def test_root_finish_suffix_lost_across_a_rebuild_is_rejected() -> None:
    display = _FakeDisplay({})
    with pytest.raises(RuntimeError, match="suffix"):
        drawing._assert_root_finish_callout(display, drawing.ROOT_FINISH_SUFFIX)


def test_root_finish_with_a_hidden_value_is_rejected() -> None:
    # stud-4: the words printed and the "45" did not.
    text = drawing.ROOT_FINISH_SUFFIX
    display = _FakeDisplay({drawing.SUFFIX: text}, shows_value=False)
    with pytest.raises(RuntimeError, match="value is hidden"):
        drawing._assert_root_finish_callout(display, text)


@pytest.mark.parametrize("part", [1, 3, 4])
def test_root_finish_text_leaking_into_another_lane_is_rejected(part: int) -> None:
    # Part 3 read back intact on stud-5 and never printed; part 1 printed twice.
    text = drawing.ROOT_FINISH_SUFFIX
    display = _FakeDisplay({drawing.SUFFIX: text, part: text})
    with pytest.raises(RuntimeError, match="leaked"):
        drawing._assert_root_finish_callout(display, text)


def _arc(center, radius, start_deg, end_deg, *, ccw=True) -> drawing.DimensionArc:
    def at(deg):
        return (
            center[0] + radius * math.cos(math.radians(deg)),
            center[1] + radius * math.sin(math.radians(deg)),
        )

    start, end = at(start_deg), at(end_deg)
    # The GetArcAtIndex2 layout: color, type, 2 unused, start, end, centre, normal, dir.
    raw = [0, 0, 0, 0, *start, 0, *end, 0, *center, 0, 0, 0, 1, 1.0 if ccw else 0.0]
    return drawing.DimensionArc.from_display(raw)


def test_arc_sweep_follows_its_rotation_direction() -> None:
    minor = _arc((0.0, 0.0), 0.013, 0.0, 45.0)
    assert minor.radius == pytest.approx(0.013)
    assert math.degrees(minor.sweep) == pytest.approx(45.0)
    # The same end points drawn clockwise are the long way round.
    assert math.degrees(_arc((0.0, 0.0), 0.013, 0.0, 45.0, ccw=False).sweep) == (
        pytest.approx(315.0)
    )
    samples = minor.samples()
    assert samples[0] == pytest.approx(minor.start)
    assert samples[-1] == pytest.approx(minor.end)


VERTEX = (0.2575, 0.1431)
DETAIL = (0.22323, 0.10823, 0.30677, 0.19177)
REGION = (0.0127, 0.0127, 0.4191, 0.2667)


def _ink(*arcs, lines=()) -> drawing.DimensionInk:
    return drawing.DimensionInk(
        name="ChamferAngle", lines=tuple(lines), arcs=arcs, triangles=(), arrowheads=2
    )


def test_stud4_angle_arc_is_rejected() -> None:
    # The exported regression: r = 84 mm about the vertex, running from the 45
    # deg leg the long way round to the -8 deg curate point.
    ink = _ink(_arc(VERTEX, 0.084, 45.0, -8.0))
    problems = drawing._dimension_ink_problems(
        ink, owner=DETAIL, obstacles={}, region=REGION
    )
    assert any("radius" in problem for problem in problems)
    assert any("long way round" in problem for problem in problems)


def test_pinned_angle_arc_with_its_leader_passes() -> None:
    arc = _arc(VERTEX, drawing.ANGLE_ARC_RADIUS_M, 0.0, 45.0)
    tip = drawing._bisector_point(VERTEX, drawing.ANGLE_ARC_RADIUS_M)
    leader = (tip, (0.3118, 0.1370))
    problems = drawing._dimension_ink_problems(
        _ink(arc, lines=[leader]),
        owner=DETAIL,
        obstacles={"isometric note": (0.3373, 0.1467, 0.3720, 0.1515)},
        region=REGION,
    )
    assert problems == []


def test_leader_across_an_annotation_is_rejected() -> None:
    arc = _arc(VERTEX, drawing.ANGLE_ARC_RADIUS_M, 0.0, 45.0)
    tip = drawing._bisector_point(VERTEX, drawing.ANGLE_ARC_RADIUS_M)
    problems = drawing._dimension_ink_problems(
        _ink(arc, lines=[(tip, (0.360, 0.100))]),
        owner=DETAIL,
        obstacles={"DETAIL A label": (0.3185, 0.0919, 0.3509, 0.1081)},
        region=REGION,
    )
    assert problems == [
        "ChamferAngle ink crosses DETAIL A label [318.5,91.9]..[350.9,108.1]mm"
    ]


def test_bisector_point_splits_the_chamfer_span() -> None:
    x, y = drawing._bisector_point((0.0, 0.0), 0.013)
    assert math.hypot(x, y) == pytest.approx(0.013)
    assert math.degrees(math.atan2(y, x)) == pytest.approx(drawing.CHAMFER_ANGLE_DEG / 2.0)


def test_segment_box_hits() -> None:
    box = (0.0, 0.0, 1.0, 1.0)
    assert drawing._segment_hits_box((-1.0, 0.5), (2.0, 0.5), box)
    assert drawing._segment_hits_box((0.2, 0.2), (0.3, 0.3), box)
    assert not drawing._segment_hits_box((-1.0, 2.0), (2.0, 1.5), box)
    assert not drawing._segment_hits_box((1.5, -1.0), (1.5, 2.0), box)


BOUNDARY = ((0.265, 0.150), 0.0383)


def test_leader_out_of_the_detail_is_the_one_allowed_boundary_crossing() -> None:
    arc = _arc(VERTEX, drawing.ANGLE_ARC_RADIUS_M, 0.0, 45.0)
    tip = drawing._bisector_point(VERTEX, drawing.ANGLE_ARC_RADIUS_M)
    shelf_start = (0.3206, 0.1330)
    ink = _ink(arc, lines=[(tip, shelf_start), (shelf_start, (0.400, 0.1330))])
    assert drawing._dimension_ink_problems(
        ink, owner=DETAIL, obstacles={}, region=REGION, boundary=BOUNDARY
    ) == []
    # A second exit -- e.g. an extension line stretched past the circle -- fails.
    stretched = (VERTEX, (0.320, VERTEX[1]))
    problems = drawing._dimension_ink_problems(
        _ink(arc, lines=[(tip, shelf_start), stretched]),
        owner=DETAIL,
        obstacles={},
        region=REGION,
        boundary=BOUNDARY,
    )
    assert problems == [
        "ChamferAngle ink crosses the detail boundary circle [265.0, 150.0] "
        "r 38.3 mm 2 time(s); 1 allowed"
    ]


def test_undeclared_dimension_may_not_cross_a_detail_boundary() -> None:
    ink = drawing.DimensionInk(
        name="Other",
        lines=(((0.265, 0.150), (0.400, 0.150)),),
        arcs=(),
        triangles=(),
        arrowheads=0,
    )
    problems = drawing._dimension_ink_problems(
        ink, owner=DETAIL, obstacles={}, region=REGION, boundary=BOUNDARY
    )
    assert len(problems) == 1 and "0 allowed" in problems[0]


def test_segment_circle_crossing() -> None:
    center, radius = (0.0, 0.0), 1.0
    assert drawing._segment_crosses_circle((0.0, 0.0), (2.0, 0.0), center, radius)
    assert drawing._segment_crosses_circle((-2.0, 0.5), (2.0, 0.5), center, radius)
    assert not drawing._segment_crosses_circle((-0.5, 0.0), (0.5, 0.0), center, radius)
    assert not drawing._segment_crosses_circle((-2.0, 1.5), (2.0, 1.5), center, radius)

