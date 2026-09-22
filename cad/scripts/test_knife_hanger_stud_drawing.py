"""Offline manufacturing boundaries for the turned purchased stud."""

import math

import pytest

import build_knife_hanger_stud as build
import draw_knife_hanger_stud as drawing
import knife_hanger_interface as joint
import knife_hanger_stud_spec as spec
from diagnostics.diag_build_91247A720 import GB_WASHER_T


# --- the part is the joint's stud, number for number ---------------------------


def test_tip_is_the_interface_tip() -> None:
    assert spec.TIP_THREAD == joint.THREAD
    assert spec.TIP_DIA_MM == joint.THREAD_MAJOR_DIA_MM
    assert spec.TIP_LENGTH_MM == joint.STUD_TIP_LENGTH_MM
    assert spec.TIP_LENGTH_DEVIATIONS_MM == joint.STUD_TIP_LENGTH_DEVIATIONS_MM
    assert 0.0 < spec.TIP_CHAMFER_MM <= joint.STUD_TIP_CHAMFER_MAX_MM


def test_model_stations_come_from_the_spec() -> None:
    assert build.TIP_RADIUS_MM == pytest.approx(joint.THREAD_MAJOR_DIA_MM / 2.0)
    assert build.UNDERHEAD_Y_MM - build.SHOULDER_Y_MM == pytest.approx(
        spec.SHOULDER_UNDERHEAD_MM
    )
    assert build.SHOULDER_Y_MM - build.TIP_END_Y_MM == pytest.approx(
        joint.STUD_TIP_LENGTH_MM
    )
    assert build.UNDERHEAD_LEN == pytest.approx(
        spec.SHOULDER_UNDERHEAD_MM + joint.STUD_TIP_LENGTH_MM
    )
    assert spec.STOCK_UNDERHEAD_MM - spec.TRIM_LENGTH_MM == pytest.approx(
        build.UNDERHEAD_LEN
    )


def test_turn_profile_steps_down_from_the_shank() -> None:
    # The shoulder is an annulus from the tip's crest out to the stock crest;
    # the cutter's outside clears the stock thread and removes no shank.
    assert build.TIP_RADIUS_MM < build.SHANK_DIA / 2.0 < build.TURN_CUTTER_RADIUS_MM
    assert build.TIP_RADIUS_MM - spec.TIP_CHAMFER_MM > 0.0
    assert build.TURN_CUTTER_CLEARANCE_MM > 0.0


def test_cosmetic_thread_runs_the_full_tip_above_the_chamfer() -> None:
    # The build threads TIP_LENGTH - chamfer from the chamfer's top edge: the
    # whole cylindrical tip up to the shoulder, the chamfer excluded as the
    # interface excludes it from engagement.
    depth = spec.TIP_LENGTH_MM - spec.TIP_CHAMFER_MM
    start = build.TIP_END_Y_MM + spec.TIP_CHAMFER_MM
    assert start + depth == pytest.approx(build.SHOULDER_Y_MM)
    assert depth >= joint.MIN_ENGAGEMENT_MM - 1e-9


def test_shoulder_reference_matches_the_assembly_stack() -> None:
    # Not imported by the build: a top-frame or washer edit must fail here,
    # not silently re-key the stud.
    from build_knife_hanger_washer import THICKNESS as WASHER_THICKNESS
    from build_top_frame import RING_HEIGHT

    bearing_face_y = joint.CASTING_UNDERSIDE_Y + RING_HEIGHT + WASHER_THICKNESS
    assert spec.SHOULDER_UNDERHEAD_MM == pytest.approx(
        bearing_face_y - joint.SHOULDER_SEAT_Y, abs=1e-9
    )


# --- the sheet's controls are the model's --------------------------------------


def test_drawing_imports_exactly_the_tip_controls() -> None:
    assert spec.DRAWING_DIMENSIONS == {"StudTurnProfile": set(drawing.TIP_CONTROLS)}
    assert set(drawing.TIP_TOLERANCE_TYPES) == set(drawing.TIP_CONTROLS)


def test_tip_length_carries_the_interface_band() -> None:
    nominal, lower, upper = drawing.TIP_CONTROLS["TipLength"]
    assert nominal * 1000.0 == pytest.approx(joint.STUD_TIP_LENGTH_MM)
    assert (lower * 1000.0, upper * 1000.0) == pytest.approx(
        joint.STUD_TIP_LENGTH_DEVIATIONS_MM
    )
    assert drawing.TIP_TOLERANCE_TYPES["TipLength"] == drawing.SW_TOL_BILATERAL
    # Rule 2: the value prints as many places as its band needs.
    places = spec.DIMENSION_PRECISION["TipLength"]
    for deviation in joint.STUD_TIP_LENGTH_DEVIATIONS_MM:
        assert round(deviation, places) == pytest.approx(deviation)


def test_tip_chamfer_prints_as_the_interface_maximum() -> None:
    nominal, lower, upper = drawing.TIP_CONTROLS["TipChamfer"]
    assert nominal * 1000.0 == pytest.approx(joint.STUD_TIP_CHAMFER_MAX_MM)
    assert (lower, upper) == (0.0, 0.0)
    assert spec.TIP_CHAMFER_TOLERANCE_TYPE == 6  # swTolType_e.swTolMAX
    assert drawing.TIP_TOLERANCE_TYPES["TipChamfer"] == spec.TIP_CHAMFER_TOLERANCE_TYPE
    places = spec.DIMENSION_PRECISION["TipChamfer"]
    assert round(joint.STUD_TIP_CHAMFER_MAX_MM, places) == pytest.approx(
        joint.STUD_TIP_CHAMFER_MAX_MM
    )


def test_tip_chamfer_angle_is_proved_by_equal_legs() -> None:
    assert spec.TIP_CHAMFER_CALLOUT_SUFFIX == " X 45°"
    legs = spec.TIP_CHAMFER_MM / 1000.0
    assert drawing._chamfer_angle_problem(legs, legs) is None
    assert drawing._chamfer_angle_problem(legs * 1.1, legs)


def test_model_underhead_control_is_reproved() -> None:
    good = {
        "driven_state": 2,
        "value": spec.FINISHED_UNDERHEAD_MM / 1000.0,
        "tolerance_type": 0,
    }
    assert drawing._model_finished_problems(**good) == []
    assert drawing._model_finished_problems(**{**good, "driven_state": 1})
    assert drawing._model_finished_problems(**{**good, "value": 0.0451})
    assert drawing._model_finished_problems(**{**good, "tolerance_type": 1})


def test_overall_prints_as_a_one_place_reference() -> None:
    places = spec.DRAWING_REFERENCE_PRECISION["FinishedOverall"]
    assert places == spec.DIMENSION_PRECISION["FinishedOverall"] == 1
    model = spec.FINISHED_UNDERHEAD_MM
    text = f"({model:.1f})"
    assert drawing._finished_text_problem(1, [text], model) is None
    assert drawing._finished_text_problem(1, ["(", text[1:-1], ")"], model) is None
    assert drawing._finished_text_problem(-2, [text], model)
    assert drawing._finished_text_problem(1, [text[1:-1]], model)
    assert drawing._finished_text_problem(1, [f"({model:.2f})"], model)


# --- lathe orientation and sheet layout ----------------------------------------


def test_lathe_axis_reads_head_left_tip_right() -> None:
    assert drawing._axis_problem((1.0, 0.0)) is None
    assert drawing._axis_problem((-1.0, 0.0))
    assert drawing._axis_problem((0.0, -1.0))
    assert drawing._axis_problem((math.cos(0.01), math.sin(0.01)))


def _inside(box, region, margin=0.0) -> bool:
    return (
        box[0] >= region[0] + margin
        and box[1] >= region[1] + margin
        and box[2] <= region[2] - margin
        and box[3] <= region[3] - margin
    )


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _detail_circle_box() -> tuple[float, float, float, float]:
    radius = drawing.SHEET.fence_radius_mm * drawing.SHEET.detail_scale[0] / 1000.0
    x, y = drawing.SHEET.detail_center
    return (x - radius, y - radius, x + radius, y + radius)


def test_lathe_view_with_its_text_lanes_fits_its_cell() -> None:
    scale = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1] / 1000.0
    length = (build.HEAD_H + GB_WASHER_T + spec.FINISHED_UNDERHEAD_MM) * scale
    above = build.SHANK_DIA / 2.0 * scale + drawing.TIP_LENGTH_TEXT_OUT_M + 0.005
    below = drawing.HEAD_CORNER_MM * scale + drawing.FINISHED_TEXT_OUT_M + 0.005
    region = drawing.FRONT_REGION
    assert length < region[2] - region[0] - 2.0 * drawing.FRONT_FIT_MARGIN_M
    assert above + below < region[3] - region[1]


def test_sheet_cells_do_not_collide() -> None:
    template = drawing.DRAWING_TEMPLATES[drawing.SPEC.layout]
    title_block = (
        template.title_block_left_m,
        0.0,
        template.width_m,
        template.title_block_top_m,
    )
    detail = _detail_circle_box()
    cells = {
        "front": drawing.FRONT_REGION,
        "isometric": drawing.ISO_REGION,
        "tip detail": detail,
        "title block": title_block,
    }
    names = sorted(cells)
    for index, a in enumerate(names):
        for b in names[index + 1 :]:
            assert not _overlap(cells[a], cells[b]), (a, b)
    sheet = (0.0, 0.0, template.width_m, template.height_m)
    assert _inside(detail, sheet)


def test_tip_detail_frames_the_whole_tip_end() -> None:
    sheet = drawing.SHEET
    assert sheet.cut_end_y_mm == build.TIP_END_Y_MM
    assert sheet.detail_center_x_mm == 0.0
    # The fence takes in the faced end and the tip's crest with room above it
    # for the chamfer's dimension line.
    reach_end = sheet.detail_offset_mm
    crest = math.hypot(build.TIP_RADIUS_MM, sheet.detail_offset_mm)
    assert reach_end < sheet.fence_radius_mm
    assert crest < sheet.fence_radius_mm
    # The chamfer's text anchor sits inside the boundary, >= 1 mm of model
    # (6 mm of paper) from it, so its callout needs no crossing.
    scale = sheet.detail_scale[0] / sheet.detail_scale[1]
    text = (
        build.TIP_RADIUS_MM + drawing.CHAMFER_TEXT_OUT_M * 1000.0 / scale,
        sheet.detail_offset_mm - spec.TIP_CHAMFER_MM / 2.0,
    )
    assert math.hypot(*text) <= sheet.fence_radius_mm - 1.0
    assert drawing.DETAIL_BOUNDARY_CROSSINGS == {}


def test_iso_fit_translation_centres_the_outline_with_clearance() -> None:
    # The measured pictorial outline at 1.5:1 (54.3 x 101.4 mm: GetOutline is
    # 72.4 x 135.2 mm at 2:1 -- 1.37x the rendered ink -- scaled by 0.75).
    box = (0.330, 0.150, 0.3843, 0.2514)
    dx, dy = drawing._fit_translation(box, drawing.ISO_REGION, drawing.ISO_FIT_MARGIN_M)
    moved = (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)
    region = drawing.ISO_REGION
    margin = drawing.ISO_FIT_MARGIN_M
    assert _inside(moved, region, margin)
    # Centring splits the remaining slack evenly: no side is starved of margin.
    assert moved[0] - region[0] == pytest.approx(region[2] - moved[2])
    assert moved[1] - region[1] == pytest.approx(region[3] - moved[3])


def test_iso_fit_rejects_an_outline_that_cannot_fit() -> None:
    with pytest.raises(RuntimeError, match="cannot fit"):
        drawing._fit_translation(
            (0.0, 0.0, 0.1, 0.12), drawing.ISO_REGION, drawing.ISO_FIT_MARGIN_M
        )


# --- the generic ink gates ------------------------------------------------------


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


# Leaf 20260922T195516Z: a detail outline and its boundary circle, sheet metres.
VERTEX = (0.25752, 0.13908)
DETAIL = (0.22323, 0.10823, 0.30677, 0.19177)
BOUNDARY = ((0.265, 0.150), 0.03015)
REGION = (0.0127, 0.0127, 0.4191, 0.2667)


def _ink(*arcs, lines=(), name="TipChamfer") -> drawing.DimensionInk:
    return drawing.DimensionInk(
        name=name, lines=tuple(lines), arcs=arcs, triangles=(), arrowheads=2
    )


def test_stud4_sweeping_arc_is_rejected() -> None:
    # The exported regression: r = 84 mm, the long way round.
    problems = drawing._dimension_ink_problems(
        _ink(_arc(VERTEX, 0.084, 45.0, -8.0)), owner=DETAIL, obstacles={}, region=REGION
    )
    assert any("arc radius 84.0 mm" in problem for problem in problems)
    assert any("runs the long way round" in problem for problem in problems)


def test_ink_across_an_annotation_is_rejected() -> None:
    problems = drawing._dimension_ink_problems(
        _ink(lines=[(VERTEX, (0.360, 0.100))]),
        owner=DETAIL,
        obstacles={"detail label": (0.3185, 0.0919, 0.3509, 0.1081)},
        region=REGION,
    )
    assert problems == [
        "TipChamfer ink crosses detail label [318.5,91.9]..[350.9,108.1]mm"
    ]


def test_self_crossing_lines_are_rejected() -> None:
    problems = drawing._dimension_ink_problems(
        _ink(lines=[((0.24, 0.13), (0.26, 0.15)), ((0.24, 0.15), (0.26, 0.13))]),
        owner=DETAIL,
        obstacles={},
        region=REGION,
    )
    assert len(problems) == 1 and "cross at" in problems[0]


def test_no_dimension_may_cross_the_tip_detail_boundary() -> None:
    problems = drawing._dimension_ink_problems(
        _ink(lines=[((0.265, 0.150), (0.400, 0.150))]),
        owner=DETAIL,
        obstacles={},
        region=REGION,
        boundary=BOUNDARY,
    )
    assert len(problems) == 1 and "0 allowed" in problems[0]


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


def test_segment_circle_crossing() -> None:
    center, radius = (0.0, 0.0), 1.0
    assert drawing._segment_crosses_circle((0.0, 0.0), (2.0, 0.0), center, radius)
    assert drawing._segment_crosses_circle((-2.0, 0.5), (2.0, 0.5), center, radius)
    assert not drawing._segment_crosses_circle((-0.5, 0.0), (0.5, 0.0), center, radius)
    assert not drawing._segment_crosses_circle((-2.0, 1.5), (2.0, 1.5), center, radius)


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
    # A dimension with no straight dimension line (an angle) is not judged.
    assert drawing._extension_line_problems(_ink(), STUD12_SILHOUETTE) == []


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


def test_faced_end_circle_is_inside_the_tip_chamfer() -> None:
    radius, axial = drawing.FACED_END_CIRCLE
    assert axial == build.TIP_END_Y_MM
    assert radius == pytest.approx(build.TIP_RADIUS_MM - spec.TIP_CHAMFER_MM)
