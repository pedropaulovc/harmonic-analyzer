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
        drawing._fit_translation(
            (0.0, 0.0, 0.1, 0.12), drawing.ISO_REGION, drawing.ISO_FIT_MARGIN_M
        )


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


# Leaf 20260922T195516Z: the arc centre (= angle vertex), the cut-end detail
# outline and its boundary circle, sheet metres.
VERTEX = (0.25752, 0.13908)
DETAIL = (0.22323, 0.10823, 0.30677, 0.19177)
BOUNDARY = ((0.265, 0.150), 0.03015)
REGION = (0.0127, 0.0127, 0.4191, 0.2667)
R = drawing.ANGLE_ARC_RADIUS_M


def _ink(*arcs, lines=()) -> drawing.DimensionInk:
    return drawing.DimensionInk(
        name="ChamferAngle", lines=tuple(lines), arcs=arcs, triangles=(), arrowheads=2
    )


def _ray(deg: float, radius: float) -> tuple[float, float]:
    return (
        VERTEX[0] + radius * math.cos(math.radians(deg)),
        VERTEX[1] + radius * math.sin(math.radians(deg)),
    )


# The 0 deg witness line: out from the vertex (past its gap) along the end face
# to past the arc.
WITNESS = (_ray(0.0, 0.0015), _ray(0.0, R + 0.0015))
# The offset text right of the detail, leader from its shelf's left end.
SHELF_END = (0.3108, 0.1331)
SHELF = (SHELF_END, (0.4049, 0.1331))


def test_stud4_angle_arc_is_rejected() -> None:
    # The exported regression: r = 84 mm about the vertex, running from the 45
    # deg leg the long way round to the -8 deg curate point.
    ink = _ink(_arc(VERTEX, 0.084, 45.0, -8.0))
    problems = drawing._dimension_ink_problems(
        ink, owner=DETAIL, obstacles={}, region=REGION
    )
    assert any("radius" in problem for problem in problems)
    assert any("long way round" in problem for problem in problems)


def test_pinned_arc_with_its_witness_and_leader_passes() -> None:
    arc = _arc(VERTEX, R, 0.0, 45.0)
    tip = drawing._bisector_point(VERTEX, R)
    problems = drawing._dimension_ink_problems(
        _ink(arc, lines=[WITNESS, (tip, SHELF_END), SHELF]),
        owner=DETAIL,
        obstacles={"isometric note": (0.3373, 0.1467, 0.3720, 0.1515)},
        region=REGION,
        boundary=BOUNDARY,
    )
    assert problems == []
    assert drawing._span_problem((arc,)) is None
    assert drawing._witness_covers((WITNESS,), VERTEX, arc.start)


def test_arc_outside_the_chamfer_span_is_rejected() -> None:
    # stud-7..9: the model dimension kept 0..45 and ran an arc on to 216.6 deg.
    problem = drawing._span_problem((_arc(VERTEX, R, 216.6, 360.0),))
    assert problem is not None and "outside the 0..45 deg span" in problem


def test_arrow_without_a_witness_line_is_caught() -> None:
    # stud-6: the model dimension's end-face leg was undrawn sketch geometry,
    # so the 0 deg arrow ended on bare paper -- no line out of the vertex.
    arc = _arc(VERTEX, R, 0.0, 45.0)
    assert not drawing._witness_covers((), VERTEX, arc.start)
    # A stub that starts 30 mm out (the cutter leg's far end) is no witness.
    stub = (_ray(0.0, 0.0319), _ray(0.0, 0.034))
    far = _arc(VERTEX, 0.033, 0.0, 45.0)
    assert not drawing._witness_covers((stub,), VERTEX, far.start)
    # One that stops short of the arrow is no witness either.
    short = (_ray(0.0, 0.0015), _ray(0.0, R - 0.002))
    assert not drawing._witness_covers((short,), VERTEX, arc.start)


def test_leader_through_the_witness_line_is_rejected() -> None:
    arc = _arc(VERTEX, R, 0.0, 45.0)
    tip = drawing._bisector_point(VERTEX, R)
    problems = drawing._dimension_ink_problems(
        _ink(arc, lines=[WITNESS, (tip, (0.2640, 0.1250))]),
        owner=DETAIL,
        obstacles={},
        region=REGION,
    )
    assert len(problems) == 1 and "cross at" in problems[0]


def test_model_angle_control_is_reproved() -> None:
    nominal, lower, upper = drawing.MODEL_ANGLE_CONTROL
    good = {
        "driven_state": 2,
        "value": nominal,
        "tolerance_type": spec.DIMENSION_TOLERANCE_TYPES["ChamferAngle"],
        "lower": lower,
        "upper": upper,
    }
    assert drawing._model_angle_problems(**good) == []
    assert drawing._model_angle_problems(**{**good, "driven_state": 1})
    assert drawing._model_angle_problems(**{**good, "value": math.radians(44.0)})
    assert drawing._model_angle_problems(**{**good, "upper": 0.0})


def test_leader_across_an_annotation_is_rejected() -> None:
    arc = _arc(VERTEX, R, 0.0, 45.0)
    tip = drawing._bisector_point(VERTEX, R)
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
    assert math.degrees(math.atan2(y, x)) == pytest.approx(
        drawing.CHAMFER_ANGLE_DEG / 2.0
    )


def test_pinned_arc_stays_on_the_drawn_chamfer() -> None:
    # The 45 deg arrow needs no witness line only while the arc is inside the
    # ~14.4 mm chamfer Detail A draws (stud-6 render).
    assert drawing.ANGLE_ARC_RADIUS_M + drawing.ANGLE_ARC_RADIUS_TOLERANCE_M < 0.0144


def test_segment_box_hits() -> None:
    box = (0.0, 0.0, 1.0, 1.0)
    assert drawing._segment_hits_box((-1.0, 0.5), (2.0, 0.5), box)
    assert drawing._segment_hits_box((0.2, 0.2), (0.3, 0.3), box)
    assert not drawing._segment_hits_box((-1.0, 2.0), (2.0, 1.5), box)
    assert not drawing._segment_hits_box((1.5, -1.0), (1.5, 2.0), box)


def test_segment_intersection() -> None:
    assert drawing._segment_intersection((0, 0), (2, 2), (0, 2), (2, 0)) == (
        pytest.approx(1.0),
        pytest.approx(1.0),
    )
    assert drawing._segment_intersection((0, 0), (1, 1), (0, 2), (1, 3)) is None
    assert drawing._segment_intersection((0, 0), (1, 0), (2, -1), (2, 1)) is None


def test_leader_out_of_the_detail_is_the_one_allowed_boundary_crossing() -> None:
    arc = _arc(VERTEX, R, 0.0, 45.0)
    tip = drawing._bisector_point(VERTEX, R)
    # A second exit -- e.g. a witness line stretched past the circle -- fails.
    stretched = (VERTEX, _ray(45.0, 0.050))
    problems = drawing._dimension_ink_problems(
        _ink(arc, lines=[(tip, SHELF_END), SHELF, stretched]),
        owner=DETAIL,
        obstacles={},
        region=REGION,
        boundary=BOUNDARY,
    )
    assert problems == [
        "ChamferAngle ink crosses the detail boundary circle [265.0, 150.0] "
        "r 30.1 mm 2 time(s); 1 allowed"
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


def test_printed_places_follow_the_spec_and_the_render() -> None:
    texts = [" 45° CHAMFER TO EXISTING THREAD ROOT "]
    assert drawing.CHAMFER_ANGLE_PRECISION == spec.DIMENSION_PRECISION["ChamferAngle"]
    assert drawing._printed_places_problem(0, texts, 45.000000000000306) is None
    # stud-10/11: the drawing dimension followed the document default (-2).
    problem = drawing._printed_places_problem(-2, texts, 45.0)
    assert problem is not None and "prints -2 places" in problem
    stale = [" 45.00° CHAMFER TO EXISTING THREAD ROOT "]
    problem = drawing._printed_places_problem(0, stale, 45.0)
    assert problem is not None and "renders" in problem
    assert drawing._printed_places_problem(0, [], 45.0) is not None


def _mm_point(point: list[float]) -> tuple[float, float]:
    return (point[0] / 1000.0, point[1] / 1000.0)


# The pinned 45 deg exactly as leaf 20260922T205428Z (stud-10) logged it: the
# arc split around the inline value at the bisector, plus the 0 deg witness.
STUD10_VERTEX = (0.26509, 0.1312)
STUD10_ARCS = (
    ([265.09, 131.2], [277.09, 131.2], [276.95, 133.01]),
    ([265.09, 131.2], [274.56, 138.57], [273.57, 139.69]),
)
STUD10_WITNESS = (_mm_point([266.09, 131.2]), _mm_point([278.09, 131.2]))
STUD10_STATE = {
    "value_deg": 45.000000000000384,
    "model_deg": 45.000000000000306,
    "parenthesis": False,
    "texts": [" 45° CHAMFER TO EXISTING THREAD ROOT "],
}


def test_stud10_logged_angle_passes_every_option8_gate() -> None:
    arcs = tuple(
        drawing.DimensionArc(
            center=_mm_point(center),
            start=_mm_point(start),
            end=_mm_point(end),
            ccw=True,
        )
        for center, start, end in STUD10_ARCS
    )
    ink = _ink(*arcs, lines=[STUD10_WITNESS])
    # _pin_angle_arc: centre on the projected vertex, span, radius, one circle.
    for arc in arcs:
        assert math.dist(arc.center, STUD10_VERTEX) <= drawing.ANGLE_VERTEX_TOLERANCE_M
        assert abs(arc.radius - R) <= drawing.ANGLE_ARC_RADIUS_TOLERANCE_M
    assert drawing._span_problem(arcs) is None
    # The ink gate, in the stud-6 detail frame (its outline centre is fixed).
    box = (0.265 - 0.04177, 0.150 - 0.04177, 0.265 + 0.04177, 0.150 + 0.04177)
    assert (
        drawing._dimension_ink_problems(
            ink, owner=box, obstacles={}, region=REGION, boundary=BOUNDARY
        )
        == []
    )
    # _assert_arrows_on_drawn_edges: the 0 deg end has its witness from the
    # vertex; the 45 deg end is the one probed on the drawn chamfer.
    ends = [point for arc in arcs for point in (arc.start, arc.end)]

    def bearing(point: tuple[float, float]) -> float:
        return math.degrees(
            math.atan2(point[1] - STUD10_VERTEX[1], point[0] - STUD10_VERTEX[0])
        )

    face_end = min(ends, key=lambda point: abs(bearing(point)))
    chamfer_end = min(ends, key=lambda point: abs(bearing(point) - 45.0))
    assert drawing._witness_covers(ink.lines, STUD10_VERTEX, face_end)
    assert bearing(chamfer_end) == pytest.approx(45.0, abs=0.1)
    # _assert_chamfer_angle_display, with the spec's places now set explicitly.
    value = math.radians(STUD10_STATE["value_deg"])
    model = math.radians(STUD10_STATE["model_deg"])
    assert abs(value - model) <= drawing.ANGLE_VALUE_TOLERANCE_RAD
    assert not STUD10_STATE["parenthesis"]
    assert not any("(" in text for text in STUD10_STATE["texts"])
    places = spec.DRAWING_REFERENCE_PRECISION["ChamferAngle"]
    assert (
        drawing._printed_places_problem(
            places, STUD10_STATE["texts"], STUD10_STATE["model_deg"]
        )
        is None
    )
    # The stud-10/11 failure itself: the setting read -2 (follows the document).
    assert drawing._printed_places_problem(
        -2, STUD10_STATE["texts"], STUD10_STATE["model_deg"]
    )


# The stud as stud-12's front view drew it (leaf 20260922T212033Z, 2:1, axis
# at x = 104.0 mm, cut end at y = 122.46 mm): head, shank and cut-end rows.
STUD12_SILHOUETTE = (
    (0.08495, 0.21266, 0.12305, 0.228935),
    (0.0913, 0.125, 0.1167, 0.21266),
    (0.09384, 0.12246, 0.11416, 0.125),
)
STUD12_DIMENSION_LINE = (
    ((0.070, 0.21266), (0.070, 0.17778)),
    ((0.070, 0.12246), (0.070, 0.17222)),
)


def _finished_ink(*witnesses) -> drawing.DimensionInk:
    return drawing.DimensionInk(
        name="FinishedOverall",
        lines=(*witnesses, *STUD12_DIMENSION_LINE),
        arcs=(),
        triangles=(),
        arrowheads=2,
    )


def test_stud12_model_underhead_witnesses_are_rejected() -> None:
    # The model FinishedOverall's legs: the axis datum and the cutter's +2r
    # corner, so one witness ran to the axis and the other across the tip.
    ink = _finished_ink(
        ((0.104, 0.21266), (0.069, 0.21266)),
        ((0.1294, 0.12246), (0.069, 0.12246)),
    )
    problems = drawing._extension_line_problems(ink, STUD12_SILHOUETTE)
    assert len(problems) == 2
    assert "19.0 mm into the part" in problems[0]
    assert "through the part and 15.2 mm past it" in problems[1]


def test_drawn_edge_witnesses_pass() -> None:
    # Each stops 1.5 mm short of the drawn edge nearest the dimension line.
    ink = _finished_ink(
        ((0.069, 0.21266), (0.08345, 0.21266)),
        ((0.069, 0.12246), (0.09234, 0.12246)),
    )
    # stud-14's census: the witnesses end exactly at the drawn edge ends.
    stud14 = _finished_ink(
        ((0.08495, 0.21266), (0.069, 0.21266)),
        ((0.09384, 0.12246), (0.069, 0.12246)),
    )
    assert drawing._extension_line_problems(stud14, STUD12_SILHOUETTE) == []
    assert drawing._extension_line_problems(ink, STUD12_SILHOUETTE) == []
    assert (
        drawing._dimension_ink_problems(
            ink,
            owner=(0.0804, 0.1151, 0.1296, 0.2349),
            obstacles={},
            region=REGION,
            silhouette=STUD12_SILHOUETTE,
        )
        == []
    )
    # A dimension with no vertical dimension line (an angle) is not judged.
    assert drawing._extension_line_problems(_ink(), STUD12_SILHOUETTE) == []


def test_model_underhead_control_is_reproved() -> None:
    good = {
        "driven_state": 2,
        "value": spec.FINISHED_UNDERHEAD_MM / 1000.0,
        "tolerance_type": 0,
    }
    assert drawing._model_finished_problems(**good) == []
    assert drawing._model_finished_problems(**{**good, "driven_state": 1})
    assert drawing._model_finished_problems(**{**good, "value": 0.0452})
    assert drawing._model_finished_problems(**{**good, "tolerance_type": 1})


def test_underhead_prints_as_a_one_place_reference() -> None:
    places = spec.DRAWING_REFERENCE_PRECISION["FinishedOverall"]
    assert places == spec.DIMENSION_PRECISION["FinishedOverall"] == 1
    assert drawing._finished_text_problem(1, ["(45.1)"], 45.1) is None
    assert drawing._finished_text_problem(1, ["(", "45.1", ")"], 45.1) is None
    assert drawing._finished_text_problem(-2, ["(45.1)"], 45.1)
    assert drawing._finished_text_problem(1, ["45.1"], 45.1)
    assert drawing._finished_text_problem(1, ["(45.10)"], 45.1)


class _FakeCircle:
    def __init__(
        self, radius_mm: float, axial_mm: float, *, circle: bool = True
    ) -> None:
        self.CircleParams = (
            0.0,
            axial_mm / 1000.0,
            0.0,
            0.0,
            1.0,
            0.0,
            radius_mm / 1000.0,
        )
        self._circle = circle

    def IsCircle(self) -> bool:
        return self._circle

    def GetCurve(self) -> "_FakeCircle":
        return self


def test_bearing_circle_is_told_from_the_hex_underside(monkeypatch) -> None:
    # stud-13: a coordinate pick took the hex underside 0.2 mm above the
    # bearing face and read (45.3); the circle scan keys on the station.
    radius, axial = drawing.BEARING_CIRCLE
    hex_underside = _FakeCircle(radius, axial + 0.2)
    bearing = _FakeCircle(radius, axial)
    edges = [_FakeCircle(radius, axial, circle=False), hex_underside, bearing]
    monkeypatch.setattr(drawing, "visible_view_entities", lambda *a, **k: edges)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    assert drawing._circle_edge(None, radius, axial, label="bearing") is bearing
    with pytest.raises(RuntimeError, match="no circle"):
        drawing._circle_edge(None, radius, axial - 1.0, label="bearing")


def _turned(point: tuple[float, float]) -> tuple[float, float]:
    """The same sheet point with the view turned 90 deg (axis horizontal)."""
    return (point[1], -point[0])


def _turned_box(box: tuple[float, float, float, float]) -> tuple[float, ...]:
    a, b = _turned(box[:2]), _turned(box[2:])
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))


def test_extension_gate_reads_either_orientation() -> None:
    # stud-12's bad witnesses and stud-14's good ones, replayed with the view
    # turned so the dimension line is horizontal and its extensions vertical.
    silhouette = tuple(_turned_box(box) for box in STUD12_SILHOUETTE)

    def turned_ink(*witnesses):
        lines = (*witnesses, *STUD12_DIMENSION_LINE)
        return drawing.DimensionInk(
            name="FinishedOverall",
            lines=tuple((_turned(a), _turned(b)) for a, b in lines),
            arcs=(),
            triangles=(),
            arrowheads=2,
        )

    bad = turned_ink(
        ((0.104, 0.21266), (0.069, 0.21266)),
        ((0.1294, 0.12246), (0.069, 0.12246)),
    )
    problems = drawing._extension_line_problems(bad, silhouette)
    assert len(problems) == 2
    assert "19.0 mm into the part" in problems[0]
    assert "through the part and 15.2 mm past it" in problems[1]
    good = turned_ink(
        ((0.069, 0.21266), (0.08495, 0.21266)),
        ((0.069, 0.12246), (0.09384, 0.12246)),
    )
    assert drawing._extension_line_problems(good, silhouette) == []
