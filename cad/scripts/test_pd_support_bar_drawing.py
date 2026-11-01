"""Offline contracts for the support-bar drawing (MHA-PD-07)."""

from __future__ import annotations

import asyncio
import math
import re
from types import SimpleNamespace

import pytest

import _config
from _column_clamp_interface import BAR_DEPTH
from _inch_wall_limits import WALL_TARGET_MM
import build_pd_support_bar as part
import draw_pd_support_bar as drawing
import pd_support_bar_drawing_spec as sheet_spec
import pd_support_bar_spec as spec


def test_printed_mating_numbers_resolve_to_the_registered_parts() -> None:
    registered = {row["number"] for row in _config.parts().values()}
    references = (
        (
            drawing.DIMENSION_CALLOUTS["ClampSlotCboreWidth"],
            "sh-vn-clamp-screw",
        ),
        (
            drawing.DIMENSION_CALLOUTS["ClampSlotCboreDepth"],
            "sh-vn-clamp-screw",
        ),
        (drawing.CLAMP_CBORE_CALLOUT, "sh-vn-clamp-screw"),
        (drawing.DIMENSION_CALLOUTS["Depth"], "sh-vn-fillister-screw-90280a108"),
    )
    for text, mate in references:
        printed = set(re.findall(r"\bMHA-[A-Z0-9]+(?:-[A-Z0-9]+)+\b", text))
        assert printed <= registered, printed - registered
        assert _config.parts(mate)["number"] in printed


def test_printed_bands_match_the_bar_and_drilled_slot_limits() -> None:
    from _printed_tolerance import drilled_oversize_mm, printed_deviations

    # .XXX at the inch print: each band is the printed limit's furthest
    # reach from the mm nominal, the rounding of .374 included.
    for value, band in (
        (spec.BAR_HEIGHT, spec.BAR_HEIGHT_BAND),
        (BAR_DEPTH, spec.BAR_DEPTH_BAND),
    ):
        lower, upper = printed_deviations(value, spec.BAR_BAND_PLACES, unit="in")
        assert band == max(-lower, upper)
    assert (spec.BAR_HEIGHT_BAND, spec.BAR_DEPTH_BAND) == pytest.approx(
        (0.127, 0.1274)
    )
    assert part.CLAMP_SLOT_WIDTH_LIMITS == (0.0, drilled_oversize_mm(unit="in"))


def test_clamp_holes_find_the_back_arc_taps_at_the_printed_worst_case() -> None:
    """Review of PR #1471: the clamp row printed .X (±0.8), whose 2.263
    position zone over-runs the 0.812 the #8 clearance holes float on the
    #8-32 shanks. Fixed fastener: each screw threads into an MHA-SH-02
    back-arc tap held ±0.1 along the bar and in height (sh_column_clamp_fit),
    so the bar's zone (2·√2·band, plus the print's rounding) plus the tap's
    must stay inside the least hole's float; the band is the widest .XXX
    that does. A drift in the band, the hole, the shank or the taps' bands
    breaks one of these."""
    from _hole_spec import HoleSpec, blind_cut_dia_mm
    from sh_column_clamp_back_geom import HOLE_SPEC as BACK_ARC_TAP
    from sh_column_clamp_fit import EAR_HEIGHT_BAND, EAR_STATION_BAND
    from sh_vn_clamp_screw_spec import SHANK_DIA

    # The mate: #8-32 taps in the back arc, located ±0.1 on both axes.
    assert (BACK_ARC_TAP.kind, BACK_ARC_TAP.size) == ("tapped", "#8-32")
    assert EAR_STATION_BAND == EAR_HEIGHT_BAND == 0.1
    tap_zone = 2.0 * math.hypot(EAR_STATION_BAND, EAR_HEIGHT_BAND)
    # The float: the least drilled #8 clearance hole over the basic major.
    assert part.CLAMP_THROUGH_HOLE_SPEC == HoleSpec("clearance", "#8")
    assert part.DRILLED_HOLE_LIMITS[0] == 0.0
    hole_min = blind_cut_dia_mm(part.CLAMP_THROUGH_HOLE_SPEC)
    assert (hole_min, SHANK_DIA) == pytest.approx((4.978, 4.1656))
    hole_float = hole_min - SHANK_DIA
    assert part.CLAMP_HOLE_FLOAT == pytest.approx(hole_float)

    def zone(band: float) -> float:
        return 2.0 * math.sqrt(2.0) * band

    # The .XXX print rounds the mm stations, so the zone carries that
    # rounding on top of the band's.
    band = part.CLAMP_POSITION_BAND
    assert band == pytest.approx(0.1778)  # ±.007
    assert part.clamp_position_zone(band) >= zone(band)
    assert part.BACK_ARC_TAP_ZONE == pytest.approx(tap_zone)
    assert part.clamp_position_zone(band) + tap_zone <= hole_float  # .796 <= .812
    assert part.clamp_position_zone(band + 0.0254) + tap_zone > hole_float


def test_row_nominals_are_the_built_holes() -> None:
    left = -part.BAR_LENGTH / 2.0
    assert part.HANGER_ROW_HEIGHT == spec.BAR_HEIGHT / 2.0 - spec.HANGER_TAP_Y == 14.5
    assert part.HANGER_STATIONS == pytest.approx(
        tuple(x - left for x in (spec.PIVOT_TAP_X, *spec.BRACKET_TAP_X))
    )
    assert part.HANGER_STATIONS == pytest.approx((168.06, 291.06, 298.06))
    # Both rows read from the same (left, x = -226.06) end.
    assert part.CLAMP_ROW_START_X == left
    assert part.CLAMP_ROW_X == (-214.5, -179.5, 179.5, 214.5)
    assert sorted(part.CLAMP_ROW_X) == sorted(part.CLAMP_HOLE_X)
    assert part.CLAMP_STATIONS == pytest.approx((11.56, 46.56, 405.56, 440.56))
    # END A's (east, -X) pair are round and locate the bar; the west pair are
    # the slots (owner ruling 2026-10-15, option A).
    assert sorted(part.CLAMP_ROUND_X) == [-214.5, -179.5]
    assert sorted(part.CLAMP_SLOT_X) == [179.5, 214.5]
    assert sorted((*part.CLAMP_ROUND_X, *part.CLAMP_SLOT_X)) == list(part.CLAMP_ROW_X)
    # The clamp line keeps its machine height under the bar's top edge (the
    # SH column clamps), so it stands off the shortened bar's centre.
    assert part.CLAMP_ROW_HEIGHT == pytest.approx(14.0)
    assert part.CLAMP_ROW_HEIGHT == pytest.approx(spec.BAR_HEIGHT / 2.0 - spec.CLAMP_TAP_Y)


def _authored_row(monkeypatch, row) -> list[tuple[str, float, str | None]]:
    """Run the builder's row author against a recording stub: each dimension
    it creates as (name, built value, drive equation), in creation order."""
    import _sketch

    values: list[float] = []
    names: list[str] = []
    lines = iter(range(100))

    class _Adapter:
        async def create_sketch(self, plane):
            return plane

        async def add_line(self, *_points):
            return f"line{next(lines)}"

        async def add_sketch_constraint(self, *args):
            return args

        async def exit_sketch(self):
            return None

    async def anchor(_adapter, _point, x, y, _label):
        values.extend(abs(c) for c in (x, y) if c != 0.0)

    async def dimension(_adapter, _a, _b, _kind, value, _label):
        values.append(value)

    async def defined(_adapter, _label):
        return None

    monkeypatch.setattr(part, "check", lambda _label, result: result)
    monkeypatch.setattr(part, "set_sketch_direct_db", lambda *_args: None)
    monkeypatch.setattr(part, "_as_construction", lambda *_args: None)
    monkeypatch.setattr(part, "anchor_point_to_origin", anchor)
    monkeypatch.setattr(part, "dimension_between", dimension)
    monkeypatch.setattr(part, "ensure_fully_defined", defined)
    monkeypatch.setattr(part, "name_last_feature", lambda *_args: None)
    monkeypatch.setattr(_sketch, "_feature_by_name", lambda _adapter, name: name)
    monkeypatch.setattr(_sketch, "_display_dimensions", lambda _f, _n: list(values))
    monkeypatch.setattr(
        _sketch,
        "_rename_dimensions",
        lambda _dims, _f, recorded: names.extend(recorded),
    )
    jobs = dict(asyncio.run(part._author_row(_Adapter(), row)))
    return [
        (name, value, jobs.get(f"{name}@{row.feature}"))
        for name, value in zip(names, values, strict=True)
    ]


def _evaluate(equation: str, globals_mm: dict[str, float]) -> float:
    text = re.sub(r'"(\w+)"', lambda m: repr(globals_mm[m.group(1)]), equation)
    text = re.sub(r"(\d)mm\b", r"\1", text)
    return float(eval(text, {"__builtins__": {}}))  # noqa: S307 - literal arithmetic


@pytest.mark.parametrize(
    "globals_mm",
    [
        {"BarLength": 452.12, "BarHeight": 25.654},
        {"BarLength": 500.0, "BarHeight": 30.0},
        {"BarLength": 440.0, "BarHeight": 26.0},
    ],
)
def test_reference_rows_follow_the_bar_globals_onto_the_holes(
    monkeypatch, globals_mm
) -> None:
    """Review of PR #1471 (round 3): the row heights and stations were built
    without equations, so a Tools > Equations edit of BarHeight or BarLength
    moved the top face and the left end but left the old values, and the
    reference rows' points drifted off the real holes. Every row dimension now
    carries an equation; evaluated at any bar size it must land on the holes
    the builder places, which stay put relative to the bar centre (the pivot
    circle at PIVOT_TAP_X/HANGER_TAP_Y, the Hole Wizard taps at
    BRACKET_TAP_X/HANGER_TAP_Y and the clamp counterbores at CLAMP_HOLE_X/CLAMP_TAP_Y)."""
    assert (spec.BAR_HEIGHT, part.BAR_LENGTH) == (25.654, 452.12)
    built = {"BarLength": part.BAR_LENGTH, "BarHeight": spec.BAR_HEIGHT}
    rows = (
        (
            part.HANGER_ROW,
            sheet_spec.HANGER_STATION_NAMES,
            [(x, spec.HANGER_TAP_Y) for x in (spec.PIVOT_TAP_X, *spec.BRACKET_TAP_X)],
        ),
        (
            part.CLAMP_ROW,
            sheet_spec.CLAMP_STATION_NAMES,
            sorted((x, spec.CLAMP_TAP_Y) for x in part.CLAMP_HOLE_X),
        ),
    )
    length, height = globals_mm["BarLength"], globals_mm["BarHeight"]
    for row, names, holes in rows:
        (row_y,) = {y for _x, y in holes}
        expected = {
            f"{row.prefix}RiseX": length / 2.0,
            f"{row.prefix}RiseY": height / 2.0,
            row.height_name: height / 2.0 - row_y,
            f"{row.prefix}StartX": length / 2.0,
            # Each station runs from the moved left end to its unmoved hole.
            **{name: x + length / 2.0 for name, (x, _y) in zip(names, holes)},
        }
        authored = _authored_row(monkeypatch, row)
        for name, value, drive in authored:
            assert drive is not None, name
            # Neutral at the built size, tracking the holes at any other.
            assert _evaluate(drive, built) == pytest.approx(value), name
            assert _evaluate(drive, globals_mm) == pytest.approx(expected[name]), name


def test_rows_stack_shortest_nearest_the_bar() -> None:
    def heights(keep: dict, names: tuple[str, ...]) -> list[float]:
        return [keep[name][1] for name in names]

    face = heights(drawing.FRONT_KEEP, (*sheet_spec.HANGER_STATION_NAMES, "Length"))
    back = heights(drawing.BACK_KEEP, sheet_spec.CLAMP_STATION_NAMES)
    # The front face's long rows step 6 and 7 mm so the 17.345 line clears
    # detail C's counterbore-width callout under it (machinist review).
    for rows, bar_bottom, step in (
        (face, drawing.FACE_BOTTOM, 0.008),
        (back, drawing.BACK_BOTTOM, 0.006),
    ):
        assert all(y < bar_bottom for y in rows)
        assert all(a - b >= step - 1e-9 for a, b in zip(rows, rows[1:]))
    # Long-row texts stay between their extension lines.
    for name, span in zip(
        (*sheet_spec.HANGER_STATION_NAMES[1:], "Length"),
        (*part.HANGER_STATIONS[1:], part.BAR_LENGTH),
    ):
        x = drawing.FRONT_KEEP[name][0]
        assert drawing.LEFT_END < x < drawing.LEFT_END + span * drawing._S
    # In the front-face view that end is on the sheet's right: the long clamp
    # rows' texts stand between it and their holes. The first two rows'
    # banded texts are wider than their spans, so they stand right of the
    # end's extension line and left of the isometric view (its r6 outline's
    # left edge), at a conservative 2.76 mm a character (2.3 measured).
    iso_left = 0.3216
    for name, station, hole_x in zip(
        sheet_spec.CLAMP_STATION_NAMES, part.CLAMP_STATIONS, part.CLAMP_ROW_X
    ):
        x = drawing.BACK_KEEP[name][0]
        value, band = (
            f"{v / 25.4:.3f}".lstrip("0")
            for v in (station, part.CLAMP_POSITION_BAND)
        )
        text = f"{value} \u00b1{band}"
        half = len(text) * 0.00276 / 2.0
        if (drawing.RIGHT_END - drawing._back_x(hole_x)) > 2.0 * half:
            assert drawing._back_x(hole_x) < x - half < x + half < drawing.RIGHT_END
        else:
            assert drawing.RIGHT_END < x - half < x + half < iso_left, name


def test_clamp_callout_stands_between_the_bar_and_the_length_line() -> None:
    """r7 audit: the 4-line counterbore callout's first line sat on the face
    view's 452.0 length line. Native callout metrics measured on the farm
    (r6/r7 layout audits): the text block centres 2.8 mm under the anchor,
    lines 5.6 mm apart, each line's box 0.9..4.5 mm above its position; the
    length line runs 2.8 mm under its text anchor."""
    pitch, below_anchor = 0.0056, 0.0028
    # The native size and DRILL, C'BORE lines, then the mate lines.
    lines = 2 + len(sheet_spec.CLAMP_CBORE_CALLOUT.splitlines())
    centre = drawing.CLAMP_CALLOUT_XY[1] - below_anchor
    first = centre + (lines - 1) * pitch / 2.0
    last = centre - (lines - 1) * pitch / 2.0
    length_line = drawing.FRONT_KEEP["Length"][1] - 0.0028  # 160.2 mm
    assert first + 0.0045 <= length_line - 0.003
    assert last + 0.0009 >= drawing.BACK_TOP + 0.005


def test_slide_faces_carry_the_slide_grade() -> None:
    from _surface_finish import MACHINED_UM

    controls = {control.key: control for control in sheet_spec.SURFACE_FINISHES}
    assert set(controls) == {"top_slide", "front_slide"}
    assert {control.roughness_um for control in controls.values()} == {MACHINED_UM}
    top, front = controls["top_slide"].face, controls["front_slide"].face
    assert (top.normal, top.offset_mm) == ((0, 1, 0), spec.BAR_HEIGHT / 2.0)
    assert (front.normal, front.offset_mm) == ((0, 0, -1), BAR_DEPTH / 2.0)
    # The front-face leader lands on the face, clear of every hole.
    x, y = drawing.FRONT_FINISH_MODEL_XY
    assert abs(y) < spec.BAR_HEIGHT / 2.0
    assert all(
        abs(x - hole) > part.CLAMP_CBORE_DIA
        for hole in (*part.CLAMP_HOLE_X, *spec.BRACKET_TAP_X)
    )
    assert (
        drawing.LEFT_END
        < drawing._face_x(drawing.TOP_FINISH_MODEL_X)
        < drawing._face_x(spec.PIVOT_TAP_X)
    )


def test_clamp_callout_picks_the_counterbore_rim(monkeypatch) -> None:
    picks = []

    class _Edges:
        def circle_at(self, center, radius, *, axis, label, radius_tol_mm):
            picks.append((center, radius, axis))

            class _Hit:
                edge = label

            return _Hit()

    monkeypatch.setattr(drawing, "scan_view_edges", lambda view, *, label: _Edges())
    drawing._cbore_rim(object())
    assert picks == [
        (
            (max(part.CLAMP_ROUND_X), spec.CLAMP_TAP_Y, -BAR_DEPTH / 2.0),
            part.CLAMP_CBORE_DIA / 2.0,
            (0.0, 0.0, 1.0),
        ),
    ]


def _printed_cbore_depth_limits() -> tuple[float, float]:
    from _printed_tolerance import printed_deviations

    lower, upper = printed_deviations(
        part.CLAMP_CBORE_DEPTH, sheet_spec.CLAMP_CBORE_DEPTH_PLACES, unit="in"
    )
    return part.CLAMP_CBORE_DEPTH + lower, part.CLAMP_CBORE_DEPTH + upper


def test_clamp_heads_stay_under_the_front_face_at_the_printed_worst_case() -> None:
    shallowest, deepest = _printed_cbore_depth_limits()
    # The depth is a clearance: .XX, its nominal deep enough for the band.
    # The platen slides across the front face: the head never stands proud,
    # even at the depth's printed minimum.
    assert part.CLAMP_HEAD_H < shallowest
    # Rule 17: the floor under the deepest counterbore in the thinnest bar.
    assert (BAR_DEPTH - spec.BAR_DEPTH_BAND) - deepest >= WALL_TARGET_MM


def test_clamp_screws_engage_the_back_arc_and_stop_inside_it() -> None:
    # Head seat -> rest of the bar -> front arc -> the open grip gap (the back
    # arc's mating face stops GRIP_OFFSET short of the column axis) ->
    # threads into the back arc's through tap (build_pd_paper_drive_assembly's
    # clamp stack), over the printed depth and thickness bands; the arcs at
    # their nominals.
    from sh_column_clamp_back_geom import BLOCK_DEPTH as back_block
    from sh_column_clamp_back_geom import GRIP_OFFSET as grip_gap
    from _column_clamp_interface import ARC_DEPTH as front_arc
    from sh_vn_clamp_screw_spec import SHANK_DIA, SHANK_LEN

    shallowest, deepest = _printed_cbore_depth_limits()
    thick = BAR_DEPTH + spec.BAR_DEPTH_BAND
    thin = BAR_DEPTH - spec.BAR_DEPTH_BAND
    least = SHANK_LEN - (thick - shallowest + front_arc + grip_gap)
    most = SHANK_LEN - (thin - deepest + front_arc + grip_gap)
    # Rule 18: 1.5D of thread at the least engagement.
    assert least >= 1.5 * SHANK_DIA
    # The tip never leaves the back arc's tapped block, so nothing behind it
    # is reached.
    assert most < back_block


def test_west_slots_take_up_the_column_pitch() -> None:
    """Owner ruling 2026-10-15, option A (PR #1471 round-3 review, finding 1):
    the column pitch is not the bar's, and the round holes' float did not take
    it up. Recomputed here from the mates' bands, not the builder's helpers:
    the east pair stay round and locate the bar; each west slot's least travel
    each way plus both shanks' slack along the bar must cover the pitch error
    and every band between an east and a west screw."""
    from _printed_tolerance import printed_band_mm
    from sh_column_clamp_fit import (
        BORE_DIAMETRAL_CLEARANCE,
        EAR_HEIGHT_BAND,
        EAR_STATION_BAND,
    )
    from sh_vn_clamp_screw_spec import SHANK_DIA

    # The pitch's sources (mm frame prints): the top frame dimensions its
    # socket pitch at .XX; the base's hole table prints each socket's X at
    # .XX, two bands apart.
    top, base = printed_band_mm(2), 2.0 * printed_band_mm(2)
    assert (top, base) == pytest.approx((0.51, 1.02))
    assert sorted(part.COLUMN_PITCH_DEVIATIONS.values()) == pytest.approx([top, base])
    # A shank's slack along the bar in the least #8 hole (the model's 4.978,
    # the printed .196) at the worst height misalignment.
    radial = (4.978 - SHANK_DIA) / 2.0
    station = part.CLAMP_POSITION_BAND
    assert station == pytest.approx(0.1778)  # ±.007
    height = station + EAR_HEIGHT_BAND
    slack = math.sqrt(radial**2 - height**2)
    assert slack == pytest.approx(0.2964, abs=1e-4)
    # Each slot's least travel each way: its .118 run at .XXX.
    assert part.CLAMP_SLOT_RUN == 2.0 * part.CLAMP_SLOT_TRAVEL == 2.9972
    assert part.CLAMP_SLOT_WIDTH == part.CLAMP_HOLE_DIA == pytest.approx(4.978)
    travel = (part.CLAMP_SLOT_RUN - printed_band_mm(3, unit="in")) / 2.0
    # Between an east and a west screw: both bar stations, both clamps' tap
    # stations and both clamps' shift on their columns.
    between = 2.0 * (station + EAR_STATION_BAND + BORE_DIAMETRAL_CLEARANCE[1] / 2.0)
    assert between == pytest.approx(0.8604)
    for pitch, margin in ((top, 0.6574), (base, 0.1474)):
        left = travel + 2.0 * slack - (pitch + between)
        assert left == pytest.approx(margin, abs=5e-4)
        assert part.clamp_slot_closure_margin(pitch) == pytest.approx(left)
    # Round west holes would not close even the top frame's pitch.
    assert 2.0 * slack - (top + between) < 0.0
    # The east pair share one clamp: only their stations and taps open it.
    east = 2.0 * slack - 2.0 * (station + EAR_STATION_BAND)
    assert east == pytest.approx(0.0371, abs=1e-4)
    assert part.clamp_east_pair_margin() == pytest.approx(east)


def test_slot_heads_bear_and_stay_inside_their_counterbores() -> None:
    """The stock MHA-SH-VN-53 head over a slot: at the shank's full float across
    the widest slot it still overlaps the counterbore floor by the round
    holes' own least (the same Ø.196 +.004/-0), and anywhere the shank reaches
    in the longest slot it stays inside the narrowest, shortest counterbore."""
    from _printed_tolerance import drilled_oversize_mm, printed_band_mm
    from sh_vn_clamp_screw_spec import HEAD_DIA, SHANK_DIA

    head_r = HEAD_DIA / 2.0
    widest = 0.196 * 25.4 + drilled_oversize_mm(unit="in")
    shift = (widest - SHANK_DIA) / 2.0
    bearing = head_r - widest / 2.0 - shift
    assert bearing == pytest.approx(0.4318, abs=1e-4)
    assert part.CLAMP_HEAD_BEARING_MIN == pytest.approx(bearing)
    assert part.clamp_head_bearing(widest) == pytest.approx(bearing)
    band = printed_band_mm(3, unit="in")
    run = part.CLAMP_SLOT_RUN
    overrun = ((run + band) - (run - band)) / 2.0
    reach = head_r + shift + overrun
    lower, upper = sheet_spec.CLAMP_SLOT_CBORE_WIDTH_LIMITS
    room = (part.CLAMP_SLOT_CBORE_WIDTH + lower) / 2.0  # .335 printed exactly
    assert room - reach == pytest.approx(0.1778, abs=1e-4)
    assert part.clamp_slot_head_clearance() == pytest.approx(room - reach)
    # The explicit minimum preserves the proven head envelope; the maximum
    # is relaxed on a clearance feature.
    assert lower == -band
    assert upper >= printed_band_mm(2, unit="in")
    # The slot counterbore is the round one's width, cut as deep.
    assert part.CLAMP_SLOT_CBORE_WIDTH == part.CLAMP_CBORE_DIA == 8.509
    assert part.CLAMP_SLOT_CBORE_RUN == part.CLAMP_SLOT_RUN


def test_slot_counterbores_leave_rule_17_walls() -> None:
    """Worst-case walls round the west counterbores: to the bar's west end
    (the .X length short, the outer station long), between the pair's
    counterbores, and to the top and bottom faces."""
    from _printed_tolerance import printed_band_mm

    band = printed_band_mm(3, unit="in")
    station = part.CLAMP_POSITION_BAND
    cbore_max = part.CLAMP_SLOT_CBORE_WIDTH + sheet_spec.CLAMP_SLOT_CBORE_WIDTH_LIMITS[1]
    cbore_reach = (part.CLAMP_SLOT_CBORE_RUN + band) / 2.0 + cbore_max / 2.0
    inner, outer = sorted(part.CLAMP_STATIONS)[2:]
    shortest = part.BAR_LENGTH - printed_band_mm(1, unit="in")
    end_wall = shortest - (outer + station) - cbore_reach
    assert end_wall == pytest.approx(2.899, abs=5e-3)
    web = (outer - inner) - 2.0 * station - 2.0 * cbore_reach
    assert web == pytest.approx(22.757, abs=5e-3)
    # The clamp line stands CLAMP_ROW_HEIGHT under the top face, so the
    # bottom face (the height's printed minimum) is the nearer one.
    side = (
        spec.BAR_HEIGHT
        - spec.BAR_HEIGHT_BAND
        - part.CLAMP_ROW_HEIGHT
        - station
        - cbore_max / 2.0
    )
    assert side == pytest.approx(6.968, abs=5e-3)
    for wall in (end_wall, web, side):
        assert wall >= WALL_TARGET_MM
    # Nominally 5.807 to the end, 23.494 between.
    reach = part.CLAMP_SLOT_RUN / 2.0 + part.CLAMP_SLOT_CBORE_WIDTH / 2.0
    assert part.BAR_LENGTH / 2.0 - max(part.CLAMP_SLOT_X) - reach == pytest.approx(5.8069)
    assert max(part.CLAMP_SLOT_X) - min(part.CLAMP_SLOT_X) - 2.0 * reach == pytest.approx(
        23.4938
    )


def test_slot_views_frame_the_slots() -> None:
    # Detail C fences the outer slot's whole counterbore inside the bar's
    # height; section B-B cuts the inner slot, its caption under it.
    assert drawing.DETAIL_SLOT_X == max(part.CLAMP_SLOT_X)
    reach = part.CLAMP_SLOT_CBORE_RUN / 2.0 + part.CLAMP_SLOT_CBORE_WIDTH / 2.0
    assert reach < drawing.DETAIL_RADIUS_MM < spec.BAR_HEIGHT / 2.0
    assert drawing.SLOT_SECTION_X == min(part.CLAMP_SLOT_X)
    scale = drawing.SLOT_SECTION_SCALE[0] / drawing.SLOT_SECTION_SCALE[1]
    bottom = drawing.SLOT_SECTION_CENTER[1] - spec.BAR_HEIGHT * scale / 2000.0
    assert drawing.SLOT_SECTION_CAPTION_XY[1] < bottom
    # Detail C's slot-width text stands under the slot's lower edge, right of
    # the crop circle (inside its 4.98 span its own dimension line struck it,
    # r4 review), and the label right of that.
    radius = drawing.DETAIL_RADIUS_MM * drawing.DETAIL_MM
    width_x, width_y = drawing.DETAIL_KEEP["ClampSlotWidth"]
    assert width_x > drawing.DETAIL_CENTER[0] + radius
    edge = drawing.DETAIL_CENTER[1] - part.CLAMP_SLOT_WIDTH * drawing.DETAIL_MM / 2.0
    assert width_y < edge
    assert drawing.DETAIL_LABEL_XY[0] > width_x
    # Its letter stands off the bar, past the end and under the clamp row's
    # extension line, right of the row height's dimension line: over the
    # outer slot it printed on section B-B's upper letter (r4 review).
    letter_x, letter_top = drawing.DETAIL_LETTER_TOP
    assert drawing.BACK_KEEP["ClampRowHeight"][0] < letter_x < drawing.LEFT_END
    assert letter_top < drawing.BACK_CENTER[1]
    # Its counterbore-width callout stays outside the detail, over its upper
    # edge. The final native text/leader guard checks section B-B rather than
    # trusting the old shoulder-length estimate.
    cbore_x, cbore_y = drawing.DETAIL_KEEP["ClampSlotCboreWidth"]
    assert cbore_x < drawing.DETAIL_CENTER[0] - radius
    cbore_edge = (
        drawing.DETAIL_CENTER[1] + part.CLAMP_SLOT_CBORE_WIDTH * drawing.DETAIL_MM / 2.0
    )
    assert cbore_y > cbore_edge
    assert drawing.DETAIL_LABEL_XY[1] > drawing.DETAIL_KEEP["ClampSlotWidth"][1]


@pytest.mark.parametrize("collision", ["clear", "text", "leader", "station"])
def test_slot_callout_refuses_section_or_station_crowding(
    monkeypatch, collision
) -> None:
    from _drawing_annotation_extent import CalloutInk
    from _drawing_layout_check import LeaderSegment

    section_box = (0.0485, 0.034, 0.0575, 0.062)
    text = (0.073, 0.056, 0.107, 0.080)
    if collision == "text":
        text = (0.056, 0.056, 0.090, 0.080)
    line = (0.106, 0.048, 0.106, 0.056)
    if collision == "leader":
        line = (0.053, 0.048, 0.106, 0.056)
    # The native text reaches 3 mm over the shoulder-mirrored estimate (its
    # stacked upper limit). The 17.345 line clears the native text by 3 mm,
    # or clears the estimate by 4.5 mm but the native upper limit by 1.5 mm.
    native = (text[0], text[1], text[2], text[3] + 0.003)
    station_y = 0.0845 if collision == "station" else 0.086
    ink = CalloutInk(
        "slot counterbore width",
        text,
        (LeaderSegment("width", "dim", *line, ""),),
    )
    width = SimpleNamespace(name="ClampSlotCboreWidth")
    station = SimpleNamespace(name="ClampStation4")
    section = SimpleNamespace(GetOutline=lambda: section_box)
    monkeypatch.setattr(
        drawing, "dimension_name", lambda _adapter, annotation: annotation.name
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "callout_ink", lambda *_args, **_kwargs: ink)
    monkeypatch.setattr(drawing, "_native_text_box", lambda *_args, **_kwargs: native)
    monkeypatch.setattr(
        drawing,
        "dimension_segments",
        lambda _annotation: [((0.060, station_y), (0.290, station_y))],
    )
    if collision == "clear":
        drawing._assert_slot_callout_clear(None, [width], section, [station])
    else:
        match = "17.345" if collision == "station" else "section B-B"
        with pytest.raises(RuntimeError, match=match):
            drawing._assert_slot_callout_clear(None, [width], section, [station])


# Section B-B's sheet x's of the bar's front face and the counterbore floor
# under the fixtures' projection (sheet x = 0.053 - model z / 1000).
_FRONT_X = 0.053 + BAR_DEPTH / 2000.0
_FLOOR_X = 0.053 - (part.CLAMP_CBORE_DEPTH - BAR_DEPTH / 2.0) / 1000.0


@pytest.fixture
def slot_depth_native(monkeypatch):
    """b3 native inputs plus explicit offset controls, not native-after proof."""
    outline = (0.042662, 0.028412, 0.063338, 0.067588)
    boxes = {
        "ClampSlotCboreDepth": (0.0592538, 0.0480875, 0.0922462, 0.0682562),
        "ClampSlotCboreWidth": (0.0740076, 0.0579181, 0.107, 0.0770563),
        "ClampStation4": (0.098142, 0.0782219, 0.127858, 0.0817219),
        "ClampRowHeight": (0.019486, 0.095887, 0.047, 0.118097),
        "section-caption": (0.0309857, 0.0154134, 0.0750143, 0.0291391),
    }
    witnesses = [
        ((_FRONT_X, 0.04475), (_FRONT_X, 0.0490875)),
        ((_FLOOR_X, 0.04475), (_FLOOR_X, 0.0490875)),
    ]
    lines = {
        "ClampSlotCboreDepth": [
            *witnesses,
            ((_FRONT_X, 0.0480875), (0.0922462, 0.0480875)),
            ((_FRONT_X, 0.0480875), (_FLOOR_X, 0.0480875)),
            ((_FLOOR_X, 0.0480875), (_FLOOR_X - 0.00635, 0.0480875)),
        ],
        "ClampSlotCboreWidth": [
            ((0.126, 0.0395), (0.106, 0.0395)),
            ((0.126, 0.0565), (0.106, 0.0565)),
            ((0.0740076, 0.0579181), (0.107, 0.0579181)),
            ((0.107, 0.0579181), (0.107, 0.0565)),
            ((0.107, 0.0395), (0.107, 0.0565)),
        ],
        "ClampStation4": _outer_clamp_station_lines(),
        "ClampRowHeight": [],
    }
    position = [0.07575, 0.0592, 0.41865]
    state = {"ignore_seed": False, "activations": [], "seeds": []}

    class Display:
        _offset = False

        @property
        def OffsetText(self):
            return self._offset

        @OffsetText.setter
        def OffsetText(self, value):
            self._offset = value
            if value:
                # Model the documented native creation-point re-dress. An
                # omitted/ignored baseline seed must fail the witness guard.
                state["activations"].append(position[1])
                dy = position[1] - 0.0480875
                lines["ClampSlotCboreDepth"] = [
                    (start, (end[0], end[1] + dy))
                    if start[0] == end[0]
                    else ((start[0], start[1] + dy), (end[0], end[1] + dy))
                    for start, end in lines["ClampSlotCboreDepth"]
                ]

    display = Display()

    def seed(x, y, z):
        assert display.OffsetText is False
        state["seeds"].append((x, y, z))
        if not state["ignore_seed"]:
            position[:] = [x, y, z]
        return True

    annotations = {
        name: SimpleNamespace(
            name=name, GetSpecificAnnotation=lambda: display,
            GetPosition=lambda: tuple(position), SetPosition2=seed,
        )
        for name in boxes
    }
    caption = SimpleNamespace(
        PropertyLinkedText="<VLNAME><VLLABEL><VLSCALEV>",
        GetAnnotation=lambda: annotations["section-caption"],
    )
    section = SimpleNamespace(
        GetOutline=lambda: outline, UpdateViewDisplayGeometry=lambda: None,
        GetNotes=lambda: [caption],
    )
    moves = []

    def move(_adapter, annotation, dx, dy, *, label):
        assert display.OffsetText is True
        box = boxes[annotation.name]
        boxes[annotation.name] = (
            box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy,
        )
        # A positive-control native route leaves the mouth horizontally,
        # then turns outside the actual bar. Unlike the previous fixture,
        # this includes an OffsetText leader that the material guard sees.
        left, bottom = boxes[annotation.name][:2]
        lines[annotation.name].extend([
            ((_FRONT_X, 0.0480875), (left, 0.0480875)),
            ((left, 0.0480875), (left, bottom)),
        ])
        moves.append((dx, dy))

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(
        drawing, "_dimension_annotation",
        lambda _adapter, _annotations, name: annotations[name],
    )
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    monkeypatch.setattr(
        drawing, "_native_text_box",
        lambda _adapter, annotation, *, label: boxes[annotation.name],
    )
    monkeypatch.setattr(drawing, "dimension_segments", lambda annotation: lines[annotation.name])
    monkeypatch.setattr(
        drawing, "_sheet",
        lambda _adapter, _view, point, _label: (
            0.053 - point[2] / 1000.0, 0.048 + point[1] / 1000.0,
        ),
    )
    monkeypatch.setattr(drawing, "move_annotation", move)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        drawing, "sheet_region",
        lambda _adapter: SimpleNamespace(xmin=0.0127, ymin=0.0127, xmax=0.4191, ymax=0.2667),
    )
    return SimpleNamespace(
        section=section, boxes=boxes, lines=lines, witnesses=witnesses,
        display=display, moves=moves, state=state,
        details=[annotations["ClampSlotCboreWidth"]],
        depth=[annotations["ClampSlotCboreDepth"]],
        back=[annotations["ClampStation4"], annotations["ClampRowHeight"]],
    )


def test_slot_depth_offset_uses_native_lane_without_moving_witnesses(slot_depth_native):
    native = slot_depth_native
    original_lines = list(native.lines["ClampSlotCboreDepth"])
    witnesses = drawing._place_slot_depth_callout(
        None, native.section, native.details, native.depth, native.back
    )
    assert witnesses == native.witnesses
    assert all(line in native.lines["ClampSlotCboreDepth"] for line in original_lines)
    assert len(native.lines["ClampSlotCboreDepth"]) == len(original_lines) + 2
    assert native.display.OffsetText is True
    assert native.state["seeds"] == [(0.07575, 0.0480875, 0.41865)]
    assert native.state["activations"] == [0.0480875]
    assert len(native.moves) == 1
    box = native.boxes["ClampSlotCboreDepth"]
    assert box[0] == pytest.approx(0.063338 + drawing.SLOT_CALLOUT_AIR_M)
    assert box[3] == pytest.approx(0.0579181 - drawing.SLOT_CALLOUT_AIR_M)
    assert box[1] > native.boxes["section-caption"][3] + 0.002


def test_slot_depth_ignored_baseline_seed_refuses_native_redress(slot_depth_native):
    native = slot_depth_native
    native.state["ignore_seed"] = True
    with pytest.raises(RuntimeError, match="native witness moved"):
        drawing._place_slot_depth_callout(
            None, native.section, native.details, native.depth, native.back
        )
    assert native.state["activations"] == [0.0592]
    assert native.moves == []


@pytest.mark.parametrize("flip", [-1.0, 1.0])
def test_slot_material_proof_uses_projected_voids_not_padded_outline(monkeypatch, flip):
    # Sheet y 0.048 is the clamp line, CLAMP_TAP_Y off the bar's centre.
    def project(_adapter, _view, point, _label):
        return 0.053 + flip * point[2] / 1000.0, 0.048 + (point[1] - spec.CLAMP_TAP_Y) / 1000.0

    monkeypatch.setattr(drawing, "_sheet", project)
    front = project(None, None, (0.0, spec.CLAMP_TAP_Y, -BAR_DEPTH / 2.0), "")[0]
    floor = project(
        None, None, (0.0, spec.CLAMP_TAP_Y, -BAR_DEPTH / 2.0 + part.CLAMP_CBORE_DEPTH), ""
    )[0]
    witnesses = [
        ((x, 0.04475), (x, 0.0490875)) for x in (front, floor)
    ]
    material = drawing._slot_section_material_boxes(None, None, witnesses)
    xmin, xmax = sorted((front, 0.053 + flip * BAR_DEPTH / 2000.0))
    cbore = part.CLAMP_CBORE_DIA / 2000.0
    assert material["upper bar"] == pytest.approx((xmin, 0.048 + cbore, xmax, 0.062))
    bottom = 0.048 - (spec.BAR_HEIGHT / 2.0 + spec.CLAMP_TAP_Y) / 1000.0
    assert material["lower bar"] == pytest.approx((xmin, bottom, xmax, 0.048 - cbore))
    # The whole through-slot lane is genuinely void, including through the
    # back half of the section; contact with the counterbore wall is allowed.
    drawing._require_slot_depth_ink_outside_material(
        [((0.047, 0.048), (0.059, 0.048)), ((floor, 0.048 + cbore), (front, 0.048 + cbore))],
        material,
    )
    # No millimetre inset hides a thin penetration past the actual wall.
    y = 0.048 + cbore + 1e-8
    with pytest.raises(RuntimeError, match="upper bar"):
        drawing._require_slot_depth_ink_outside_material(
            [((floor, y), (front, y))], material
        )
    rear = material["rear upper step"]
    x = (rear[0] + rear[2]) / 2.0
    with pytest.raises(RuntimeError, match="rear upper step"):
        drawing._require_slot_depth_ink_outside_material(
            [((x, 0.048), (x, (rear[1] + rear[3]) / 2.0))], material
        )


@pytest.mark.parametrize(
    "collision",
    ["text", "width-shelf", "depth-shelf", "crossing", "witness-drift", "offset-off", "front-witness", "outside", "hatch", "caption"],
)
def test_slot_depth_settled_guard_refuses_text_shelf_or_witness_regression(slot_depth_native, collision):
    native = slot_depth_native
    original_box = native.boxes["ClampSlotCboreDepth"]
    witnesses = drawing._place_slot_depth_callout(
        None, native.section, native.details, native.depth, native.back
    )
    if collision == "text":
        native.boxes["ClampSlotCboreDepth"] = original_box
    elif collision == "width-shelf":
        native.lines["ClampSlotCboreWidth"].append(((0.065, 0.042), (0.101, 0.042)))
    elif collision == "depth-shelf":
        native.lines["ClampSlotCboreDepth"].append(((0.074, 0.065), (0.107, 0.065)))
    elif collision == "crossing":
        native.lines["ClampSlotCboreDepth"].append(((0.100, 0.048), (0.105, 0.048)))
        native.lines["ClampSlotCboreWidth"].append(((0.103, 0.044), (0.103, 0.052)))
    elif collision == "witness-drift":
        native.lines["ClampSlotCboreDepth"][0] = (
            (_FRONT_X + 0.0001, 0.04475), (_FRONT_X + 0.0001, 0.0490875),
        )
    elif collision == "offset-off":
        native.display.OffsetText = False
    elif collision == "front-witness":
        native.lines["ClampStation4"].append(((0.070, 0.030), (0.070, 0.060)))
    elif collision == "outside":
        box = native.boxes["ClampSlotCboreDepth"]
        native.boxes["ClampSlotCboreDepth"] = (
            box[0] - 0.100, box[1], box[2] - 0.100, box[3],
        )
    elif collision == "hatch":
        # Predicted bad routing is only an offline negative control. Actual
        # native segments, not that prediction, decide the farm outcome.
        native.lines["ClampSlotCboreDepth"].append(((0.055, 0.048), (0.055, 0.075)))
    elif collision == "caption":
        native.lines["ClampSlotCboreDepth"].append(((0.066, 0.027), (0.080, 0.027)))
    with pytest.raises(RuntimeError, match="section B-B depth"):
        drawing._assert_slot_depth_callout_clear(
            None, native.section, native.details, native.depth, native.back, witnesses
        )


def _outer_clamp_station_lines():
    # Actual 63fad6340 native audit, sheet metres: both witnesses and the
    # 17.345 (was 440.50) dimension line. These are not rendered/PDF estimates.
    return [
        ((0.283, 0.121), (0.283, 0.0772219)),
        ((0.06275, 0.121), (0.06275, 0.0772219)),
        ((0.283, 0.0782219), (0.06275, 0.0782219)),
    ]


def test_front_caption_clears_detail_without_following_its_lower_callout() -> None:
    from _drawing_annotation_extent import boxes_clear

    # Native text positions/widths from the retained 63fad6340 audit. The
    # far-right slot-width text is BELOW the caption, not an x keep-out.
    details = {
        "upper travel": (0.1318882, 0.0662219, 0.1461118, 0.0697219),
        "counterbore width": (0.074008, 0.057918, 0.107, 0.0770563),
        "slot width": (0.150, 0.01614, 0.194076, 0.0408344),
    }
    caption = (0.1455456, 0.0680173, 0.1948421, 0.0715173)
    centre, top = drawing._front_caption_target(
        _outer_clamp_station_lines(), caption, details
    )
    half_width = (caption[2] - caption[0]) / 2.0
    box = (centre - half_width, top - (caption[3] - caption[1]), centre + half_width, top)
    assert top == pytest.approx(0.0772219 - drawing.FRONT_CAPTION_AIR_M)
    span_centre = (0.06275 + 0.283) / 2.0
    assert span_centre <= centre < span_centre + 0.005
    for detail in details.values():
        assert boxes_clear(box, detail, gap=drawing.FRONT_CAPTION_AIR_M - 1e-12)


def test_front_caption_refuses_a_missing_native_dimension_line() -> None:
    with pytest.raises(RuntimeError, match="native dimension line"):
        drawing._front_caption_target([], (0.1, 0.06, 0.15, 0.0635), {})


@pytest.mark.parametrize(
    ("reference", "left", "bottom"),
    [(0, 0.100, 0.0665), (1, 0.100, 0.070), (2, 0.075, 0.06825),
     (3, 0.050, 0.0665), (4, 0.050, 0.070), (5, 0.075, 0.0665)],
)
def test_caption_bounds_use_the_native_text_reference(monkeypatch, reference, left, bottom):
    text = {
        "t": "caption", "pos": (0.100, 0.070, 0.0), "h": 0.0035,
        "w": 0.050, "ang": 0.0, "ref": reference,
    }
    monkeypatch.setattr(
        drawing, "annotation_display", lambda *_: ({"texts": [text]}, {})
    )
    assert drawing._native_text_box(None, object(), label="caption") == pytest.approx(
        (left, bottom, left + 0.050, bottom + 0.0035)
    )
    text["w"] = 0.0
    with pytest.raises(RuntimeError, match="unreadable native text bounds"):
        drawing._native_text_box(None, object(), label="caption")


@pytest.fixture
def slot_marker_native(monkeypatch):
    """Exercise marker placement against stateful native-interface doubles."""
    def make(direction, reversed_cut=False, persist=True):
        line = (-0.1795, 0.020, 0.0, -0.1795, -0.027, 0.0)
        state = {
            "reversed": reversed_cut,
            "direction": direction,
            "events": [],
            "position": (0.041, 0.074),
            "outline": (0.042662, 0.028412, 0.063338, 0.067588),
        }

        def arrows():
            first_tip = 0.06825 if state["direction"] != "right" else 0.09225
            second_tip = 0.09225 if state["direction"] != "left" else 0.06825
            return (
                0.08025, 0.132, 0.0, first_tip, 0.132, 0.0,
                0.08025, 0.1085, 0.0, second_tip, 0.1085, 0.0,
            )

        def read_direction():
            state["events"].append(("read direction", state["reversed"]))
            return state["reversed"]

        def set_direction(value):
            state["events"].append(("write direction", value))
            if persist:
                state["reversed"] = value
                state["direction"] = "right"

        def turn(_adapter, _view, *, label):
            state["events"].append(("turn", label))
            # Projection settles off-centre after the native direction/angle
            # update. Position is deliberately NOT the outline centre.
            state["outline"] = (0.056662, 0.039412, 0.077338, 0.078588)

        def position(values, relative):
            target = tuple(values)
            state["events"].append(("position", target, relative))
            state["position"] = target
            return True

        definition = SimpleNamespace(
            GetLineInfo=lambda: line,
            GetArrowInfo=arrows,
            GetReversedCutDirection=read_direction,
            SetReversedCutDirection=set_direction,
        )
        section = SimpleNamespace(
            GetSection=lambda: definition,
            GetOutline=lambda: state["outline"],
            Position=state["position"],
            SetViewPosition=position,
        )
        monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
        monkeypatch.setattr(drawing, "double_array", tuple)
        monkeypatch.setattr(drawing, "_turn_y_up", turn)
        monkeypatch.setattr(
            drawing, "rebuild_drawing",
            lambda _adapter, *, label: state["events"].append(("rebuild", label)),
        )
        return section, line, state

    return make


@pytest.mark.parametrize("reversed_cut", [False, True])
def test_left_b_arrows_flip_and_read_back_before_recentering(slot_marker_native, reversed_cut):
    section, line, state = slot_marker_native("left", reversed_cut)
    assert drawing._place_slot_section_markers(None, section) == line
    assert state["direction"] == "right"
    assert state["events"][:4] == [
        ("read direction", reversed_cut),
        ("write direction", not reversed_cut),
        ("rebuild", "section B-B arrows right"),
        ("read direction", not reversed_cut),
    ]
    assert state["events"][4] == ("turn", "section B-B")
    event, target, relative = state["events"][5]
    assert event == "position"
    assert target == pytest.approx((0.041 - 0.014, 0.074 - 0.011))
    assert relative is False
    assert state["events"][6] == ("rebuild", "section B-B profile centre")


@pytest.mark.parametrize("reversed_cut", [False, True])
def test_right_b_arrows_need_no_direction_write(slot_marker_native, reversed_cut):
    section, line, state = slot_marker_native("right", reversed_cut)
    assert drawing._place_slot_section_markers(None, section) == line
    assert state["reversed"] is reversed_cut
    assert state["events"][0] == ("turn", "section B-B")
    assert all(event[0] not in ("read direction", "write direction") for event in state["events"])
    event, target, relative = state["events"][1]
    assert event == "position"
    assert target == pytest.approx((0.041 - 0.014, 0.074 - 0.011))
    assert relative is False


def test_mixed_b_arrow_directions_refuse_before_mutation(slot_marker_native):
    section, _line, state = slot_marker_native("mixed")
    with pytest.raises(RuntimeError, match="not horizontal counterparts"):
        drawing._place_slot_section_markers(None, section)
    assert state["events"] == []


@pytest.mark.parametrize("reversed_cut", [False, True])
def test_b_arrow_flip_refuses_ignored_native_direction_write(slot_marker_native, reversed_cut):
    section, _line, state = slot_marker_native("left", reversed_cut, persist=False)
    with pytest.raises(RuntimeError, match="cut-direction write did not persist"):
        drawing._place_slot_section_markers(None, section)
    assert state["events"][-1] == ("read direction", reversed_cut)
    assert all(event[0] not in ("turn", "position") for event in state["events"])


@pytest.mark.parametrize(
    "case", ["clear", "reversed", "letter", "arrow", "plane", "reversed-plane", "centre"]
)
def test_b_marker_refuses_witness_hits_or_section_geometry_drift(monkeypatch, case):
    # The original line is native 63fad6340 data. Right-facing marker
    # coordinates below are an offline positive control, not native-after proof.
    line = (-0.1795, 0.020, 0.0, -0.1795, -0.027, 0.0)
    actual_line = list(line)
    if case in ("reversed", "reversed-plane"):
        actual_line = actual_line[3:] + actual_line[:3]
    arrows = [0.08025, 0.132, 0.0, 0.09225, 0.132, 0.0,
              0.08025, 0.1085, 0.0, 0.09225, 0.1085, 0.0]
    texts = [0.094, 0.137004, 0.0, 0.094, 0.113504, 0.0]
    outline = [0.042662, 0.028412, 0.063338, 0.067588]
    if case == "letter":
        texts[3] = 0.0608632  # original lower B, struck by x=62.75 witness
    elif case == "arrow":
        arrows[9] = 0.06275
    elif case in ("plane", "reversed-plane"):
        actual_line[0] += 1e-6
    elif case == "centre":
        outline[0] += 0.001
    definition = SimpleNamespace(
        GetLineInfo=lambda: actual_line,
        GetArrowInfo=lambda: arrows,
        GetTextInfo=lambda: texts,
    )
    section = SimpleNamespace(
        GetSection=lambda: definition, GetOutline=lambda: outline
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "_dimension_annotation", lambda *_: object())
    monkeypatch.setattr(drawing, "dimension_segments", lambda *_: _outer_clamp_station_lines())
    if case in ("clear", "reversed"):
        drawing._assert_slot_marker_clear(None, section, line, [])
    else:
        with pytest.raises(RuntimeError, match="section B-B"):
            drawing._assert_slot_marker_clear(None, section, line, [])



def test_section_letters_and_slot_caption_have_air() -> None:
    """Rules 13 and 14 (r7 review): the section letters stand off the bar's
    edges and section B-B's caption stands between its cut and the border.
    Offsets are the r7 sheet's: each letter from 1.28 mm under its arrow's
    line to 4.89 over it; the caption 14.6 tall, its top 0.05 under its
    anchor; the inner border's edge at y 12.9."""
    scale = drawing.FACE_SCALE[0] / drawing.FACE_SCALE[1]
    top_line = drawing.SECTION_OVERRUN_TOP * scale
    foot_line = drawing.SECTION_OVERRUN_FOOT * scale
    assert top_line - 1.28 >= 1.5  # upper letter's bottom over the top edge
    assert foot_line - 4.89 >= 1.5  # lower letter's top under the bottom edge
    slot_scale = drawing.SLOT_SECTION_SCALE[0] / drawing.SLOT_SECTION_SCALE[1]
    cut_bottom = (
        drawing.SLOT_SECTION_CENTER[1] - spec.BAR_HEIGHT * slot_scale / 2000.0
    ) * 1000.0
    caption_top = drawing.SLOT_SECTION_CAPTION_XY[1] * 1000.0 - 0.05
    assert cut_bottom - caption_top >= 2.5
    assert caption_top - 14.6 - 12.9 >= 2.5


def test_slot_section_depth_line_runs_through_the_open_slot(monkeypatch) -> None:
    """Section B-B's depth line runs where the counterbore's mouth and the
    through slot are open, so neither extension line crosses the hatch (r6:
    over the top face the floor's ran up through the cut), and its text
    stands outside the front face, whichever way the cut projects."""
    for flip in (1.0, -1.0):
        origin = (0.050, 0.045)

        def sheet(_adapter, _view, point, _label, flip=flip, origin=origin):
            _x, y, z = point
            return (origin[0] + flip * z / 1000.0, origin[1] + y / 1000.0)

        monkeypatch.setattr(drawing, "_sheet", sheet)
        text_x, text_y = drawing._slot_section_keep(None, None)["ClampSlotCboreDepth"]
        front = origin[0] - flip * BAR_DEPTH / 2000.0
        line_y = text_y - drawing.SLOT_DEPTH_SHELF_DROP
        assert abs(line_y - origin[1]) < part.CLAMP_SLOT_WIDTH / 2000.0
        assert (text_x - front) * flip < 0.0
        assert abs(text_x - front) == pytest.approx(drawing.SLOT_DEPTH_TEXT_SIDE)


def test_section_a_a_caption_stands_directly_under_the_cut_bar() -> None:
    """r4 review: 35 mm under the cut bar, the caption read as the
    isometric's. Only the thickness is dimensioned on A-A, above the bar."""
    assert drawing.SECTION_DEPTH_RISE > 0.0
    scale = drawing.SECTION_SCALE[0] / drawing.SECTION_SCALE[1]
    foot = drawing.SECTION_CENTER[1] - spec.BAR_HEIGHT * scale / 2000.0
    gap = foot - drawing.SECTION_CAPTION_TOP_Y
    assert 0.002 <= gap <= 0.006
    # Still above the isometric's centre, which stands under it.
    assert drawing.SECTION_CAPTION_TOP_Y > drawing.ISO_CENTER[1] + 0.040


class _DetailView:
    """A placed model view: its Position moves by SetViewPosition, and a model
    point projects ``offset`` from it."""

    def __init__(self, position, scale, offset):
        self.Position = position
        self.ScaleRatio = scale
        self.offset = offset

    def SetViewPosition(self, xy, _redraw):  # noqa: N802
        self.Position = tuple(float(value) for value in xy)
        return True


def test_slot_detail_centres_the_outer_slot(monkeypatch) -> None:
    """Farm r3 (leaf 20261015T223907.571157Z, drawing:pd_support_bar): a
    native detail of the front-face view imported none of the slot profiles'
    dimensions (available=[]). The detail must centre the outer slot."""

    def place(_adapter, source, orientation, x, y, *, scale):
        return _DetailView((x, y), tuple(float(v) for v in scale), (-0.31, 0.0))

    def sheet(_adapter, view, xyz, _label):
        assert xyz == (max(part.CLAMP_SLOT_X), spec.CLAMP_TAP_Y, -BAR_DEPTH / 2.0)
        return (
            view.Position[0] + view.offset[0],
            view.Position[1] + view.offset[1],
        )

    model = SimpleNamespace(EditRebuild3=lambda: True)
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "_sheet", sheet)
    monkeypatch.setattr(drawing, "double_array", tuple)
    view = drawing._slot_detail(SimpleNamespace(currentModel=model))
    assert sheet(None, view, drawing.DETAIL_FOCUS, "") == pytest.approx(
        drawing.DETAIL_CENTER
    )


@pytest.mark.parametrize("dropped", [(), ("ClampSlotTravel",)])
def test_slot_detail_is_dimensioned_before_its_crop(monkeypatch, dropped) -> None:
    """The dimensions import into the uncropped view; a kept one the crop
    drops fails the sheet."""
    names = {"cropped": False}

    def curate(_adapter, _view, *, keep, view_label, dimensions_by_feature):
        return ["kept"]

    def crop(_adapter, _view):
        names["cropped"] = True

    def held(_adapter, _view):
        kept = sorted(drawing.DETAIL_KEEP)
        if names["cropped"]:
            return [name for name in kept if name not in dropped]
        return kept

    monkeypatch.setattr(drawing.hidden_sketches, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "_crop_slot_detail", crop)
    monkeypatch.setattr(drawing, "_view_dimension_names", held)
    if dropped:
        with pytest.raises(RuntimeError):
            drawing._dimension_then_crop(None, object())
    else:
        drawing._dimension_then_crop(None, object())


def test_round_counterbore_callout_stands_over_the_east_pair() -> None:
    """The native counterbore callout points at a round (east) hole; its
    widest line (2.3 mm a character, measured) stands right of the front
    finish symbol and left of the bar height's text."""
    half = (
        max(len(line) for line in sheet_spec.CLAMP_CBORE_CALLOUT.splitlines())
        * 0.0023
        / 2.0
    )
    x = drawing.CLAMP_CALLOUT_XY[0]
    assert drawing.FRONT_FINISH_SYMBOL_XY[0] + 0.006 < x - half
    assert x + half < drawing.BACK_KEEP["Height"][0] - 0.002
    hole = drawing._back_x(max(part.CLAMP_ROUND_X))
    assert x - half < hole < x + half


_FRONT_Z = -BAR_DEPTH / 2.0
# Sketch frames SOLIDWORKS may hand the front-face plane's sketch: model mm
# to (u, v, w), sketch (u, v) back to model (x, y), and whether the normal
# points out of the front face.
_FRAMES = {
    "u along +X, normal into the bar": (
        lambda p: (p[0], p[1], p[2] - _FRONT_Z),
        lambda u, v: (u, v),
        False,
    ),
    "u along -X, normal out": (
        lambda p: (-p[0], p[1], _FRONT_Z - p[2]),
        lambda u, v: (-u, v),
        True,
    ),
    "u along Y, normal out": (
        lambda p: (p[1], p[0], _FRONT_Z - p[2]),
        lambda u, v: (v, u),
        True,
    ),
}


@pytest.mark.parametrize("frame", list(_FRAMES))
@pytest.mark.parametrize(
    ("feature", "base", "width"),
    [
        ("ClampSlotProfile", "ClampSlot", part.CLAMP_SLOT_WIDTH),
        ("ClampSlotCboreProfile", "ClampSlotCbore", part.CLAMP_SLOT_CBORE_WIDTH),
    ],
)
def test_slot_profiles_run_along_the_bar_in_any_sketch_frame(
    monkeypatch, frame, feature, base, width
) -> None:
    """Whatever axes the front-face sketch gets, each west slot's stadium runs
    along the bar on its station on the clamp line, its width and run carry the
    print's names (the outer slot's bare, the inner's numbered), and the cut
    direction follows the sketch normal."""
    import _sketch

    to_sketch, to_model, normal_out = _FRAMES[frame]
    run = part.CLAMP_SLOT_RUN
    values: list[float] = []
    lines: dict[str, tuple[float, float, float, float]] = {}
    arcs: dict[str, tuple[float, float]] = {}
    anchors: list[tuple[float, float]] = []

    class _Adapter:
        async def create_sketch(self, plane):
            return plane

        async def add_line(self, *points):
            key = f"line{len(lines)}"
            lines[key] = points
            return key

        async def add_arc(self, cu, cv, *_ends):
            key = f"arc{len(arcs)}"
            arcs[key] = (cu, cv)
            return key

        async def add_sketch_constraint(self, *args):
            return args

        async def exit_sketch(self):
            return None

    async def anchor(_adapter, _point, u, v, _label):
        anchors.append((u, v))
        values.extend(abs(c) for c in (u, v) if c != 0.0)

    async def dimension(_adapter, _a, _b, _kind, value, _label):
        values.append(value)

    async def defined(_adapter, _label):
        return None

    monkeypatch.setattr(part, "_sketch_uvw", lambda _adapter, p: to_sketch(p))
    monkeypatch.setattr(part, "check", lambda _label, result: result)
    monkeypatch.setattr(part, "set_sketch_direct_db", lambda *_args: None)
    monkeypatch.setattr(part, "anchor_point_to_origin", anchor)
    monkeypatch.setattr(part, "dimension_between", dimension)
    monkeypatch.setattr(part, "ensure_fully_defined", defined)
    monkeypatch.setattr(part, "name_last_feature", lambda *_args: None)
    monkeypatch.setattr(_sketch, "_feature_by_name", lambda _adapter, name: name)
    monkeypatch.setattr(_sketch, "_display_dimensions", lambda _f, _n: list(values))
    monkeypatch.setattr(
        _sketch,
        "_rename_dimensions",
        lambda _dims, _f, _recorded: None,
    )
    _jobs, out = asyncio.run(
        part._author_clamp_slot_profile(_Adapter(), feature, base, width, run)
    )
    assert out is normal_out
    slots = sorted(part.CLAMP_SLOT_X, reverse=True)
    ends = [to_model(*anchor) for anchor in anchors]
    assert len(ends) == len(slots)
    # Two sides and two ends a slot, the outer slot first.
    assert len(lines) == len(arcs) == 2 * len(slots)
    for index, slot_x in enumerate(slots):
        sides = list(lines.values())[2 * index : 2 * index + 2]
        for u0, v0, u1, v1 in sides:
            (x0, y0), (x1, y1) = to_model(u0, v0), to_model(u1, v1)
            assert y0 == pytest.approx(y1)
            assert abs(y0 - spec.CLAMP_TAP_Y) == pytest.approx(width / 2.0)
            assert sorted((x0, x1)) == pytest.approx(
                [slot_x - run / 2.0, slot_x + run / 2.0]
            )
        centres = sorted(
            to_model(*centre)
            for centre in list(arcs.values())[2 * index : 2 * index + 2]
        )
        assert centres == [
            pytest.approx((slot_x - run / 2.0, spec.CLAMP_TAP_Y)),
            pytest.approx((slot_x + run / 2.0, spec.CLAMP_TAP_Y)),
        ]
        assert ends[index][1] == pytest.approx(spec.CLAMP_TAP_Y)
        assert abs(ends[index][0] - slot_x) == pytest.approx(run / 2.0)
