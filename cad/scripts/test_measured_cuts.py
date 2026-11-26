"""measured-cuts.toml: each measured setting's envelope is what its dechatter
report shows, its cutter's stick-out band is the plans' own, and no plan cuts
outside a record where one must hold."""

from __future__ import annotations

import html
import json
import re
import tomllib

import pytest

import _measured_cuts
import _process_plans
import _shop_equipment
from _paths import CAD_ROOT

REPO_ROOT = CAD_ROOT.parent

MEASURED = _measured_cuts.records()
CUTTERS = _measured_cuts.cutters()
SHOP = _process_plans.load_shop()
HALF = "endmill-carbide-3fl-1-2"
SETTING = "em-half-carbide-1018-v6-deep"
WIDE_FACE = "em-half-carbide-1018-3439-face"
V5_FACE = "em-half-carbide-1018-v5-face"
WALL = "em-half-carbide-1018-3427-wall"
CLIMB_WALL = "em-half-carbide-1018-3627-wall-climb"
CHART = "endmill-carbide-3fl-1-2-1018-cf"


def _passes(report: str) -> list[tuple[float, int, float, str, str, str]]:
    """(depth mm, rpm asked, width mm, status, verdict, direction) of every
    test pass in a dechatter report's round log. The log's columns are read
    from its header (dechatter 0.8 added the heard speed and the chip load
    cut); a round is climb in a climb session or a climb check."""
    text = re.sub(r"</t[dh]>", "|", report)
    text = html.unescape(re.sub(r"<[^>]+>", "\n", text))
    session = re.search(r'direction = "(\w+)"', text).group(1)
    found = []
    rows = re.split(r"(Round \d+: [\d.]+ mm deep[^\n|]*)", text)
    for heading, body in zip(rows[1::2], rows[2::2]):
        depth = float(re.search(r"([\d.]+) mm deep", heading).group(1))
        direction = "climb" if "climb check" in heading else session
        cells = [cell.strip() for cell in body.split("|")]
        header = cells[: cells.index("Verdict set") + 1]
        column = {name: header.index(name) - header.index("Kind") for name in header}
        asked = column.get("rpm", column.get("Asked (rpm)"))
        for index, cell in enumerate(cells):
            if cell == "test" and index > len(header):
                found.append(
                    (
                        depth,
                        int(cells[index + asked]),
                        float(cells[index + column["Width"]].split()[0]),
                        cells[index + column["Status"]],
                        cells[index + column["Verdict"]],
                        direction,
                    )
                )
    return found


def _plan(stickout: float, depth: object, width: object) -> dict:
    return {
        "material_key": "rocker-1018-cold-finished",
        "tools": [{"id": "em-half", "ref": HALF}],
        "parameters": {"half_mill_projection_mm": stickout, "trim_mm": 2.2},
        "setups": [
            {
                "operations": [
                    {"instruction": "no setting"},
                    {
                        "tool": "em-half",
                        "settings": SETTING,
                        "milling_cuts": [
                            {
                                "name": "trim",
                                "kind": "side",
                                "axial_doc_mm": depth,
                                "radial_woc_mm": width,
                            }
                        ],
                    },
                ]
            }
        ],
    }


def _problems(plan: dict) -> list[str]:
    return _measured_cuts.problems(plan, MEASURED, CUTTERS)


def _unmeasured(plan: dict) -> list[str]:
    return _measured_cuts.unmeasured(plan, MEASURED, CUTTERS, SHOP["settings"])


def test_records_exist() -> None:
    assert set(MEASURED) >= {V5_FACE, SETTING, WIDE_FACE, WALL, CLIMB_WALL}


def _heard(key: str) -> list[tuple[float, float, str, int]]:
    """(width mm, rpm heard, verdict, rpm asked) of every analysed test pass in
    a record's results file: the spindle is set by hand, and ``spindle_hz`` is
    the speed dechatter heard it run."""
    session = json.loads(
        (REPO_ROOT / MEASURED[key]["results"]).read_text(encoding="utf-8")
    )
    return [
        (p["width_mm"], p["spindle_hz"] * 60, p["verdict"], p["rpm"])
        for r in session["rounds"]
        for p in r["passes"]
        if p["kind"] == "test" and p["status"] == "analysed"
    ]


def test_the_wide_face_speed_band_is_what_was_heard() -> None:
    record = MEASURED[WIDE_FACE]
    setting = _process_plans.load_shop()["settings"][WIDE_FACE]
    low, high = record["speed_in_cut_rpm"]
    width = record["radial_woc_max_mm"]
    heard = _heard(WIDE_FACE)
    # The limit pass ran inside the band, at the speed the setting asks for.
    assert [
        v for w, rpm, v, asked in heard if w == width and asked == setting["rpm"]
    ] == ["stable"]
    inside = [(w, v) for w, rpm, v, _a in heard if low <= rpm <= high]
    assert all(v == "stable" for w, v in inside)
    # The band is no wider than the stable speeds heard at the limit's width
    # and wider, to the next 10 rpm.
    wide = [rpm for w, rpm, v, _a in heard if w >= width and v == "stable"]
    assert low <= min(wide) < low + 10
    widest_inside = max(w for w, _v in inside)
    top = max(rpm for w, rpm, v, _a in heard if v == "stable")
    assert top <= high < top + 10
    # Chatter was heard below and above the band, and wider than the limit.
    assert any(v == "unstable" and rpm < low for w, rpm, v, _a in heard if w <= width)
    assert any(v == "unstable" and rpm > high for w, rpm, v, _a in heard if w <= width)
    chatter_width = min(w for w, rpm, v, _a in heard if w > width and v == "unstable")
    assert width < widest_inside < chatter_width
    # What to set before the cut lies in the band: the spindle slows in the cut.
    no_load_low, no_load_high = record["speed_no_load_rpm"]
    assert low <= no_load_low <= setting["rpm"] <= no_load_high <= high


MILL = _shop_equipment.load()["machines"]["pm-30mv"]
# A resting spindle is heard from 3 rpm under to 25 rpm over a stop.
REST_BAND_RPM = (-3.0, 25.0)
# The widest pass that still left the spindle on its stop; wider ones pulled
# it down (6.4 mm: 2455 on the 2485 stop).
LIGHT_WIDTH_MM = 3.4
# The face sessions' depth: the deepest whose narrow passes left the
# spindle resting on its stop.
LIGHT_DEPTH_MM = 1.27


def _over_a_stop(rpm: float) -> float:
    """How far ``rpm`` is above the nearest spindle speed stop."""
    step = MILL["spindle_speed_step_rpm"]
    return rpm - round(rpm / step) * step


def test_the_spindle_was_heard_only_on_its_stops() -> None:
    step, steps = MILL["spindle_speed_step_rpm"], MILL["spindle_speed_steps"]
    (rpm_range,) = _process_plans.load_shop()["machines"]["pm-30mv"]["rpm_ranges"]
    top = rpm_range[1]
    assert step == round(top / steps, 1)
    # The face sessions' results files (all 1.27 mm deep or shallower). The
    # deep-wall sessions' passes pull the spindle down even when narrow (13.5
    # mm deep: 0.8 mm wide ran 2416 on the 2483 stop), and their lane-end
    # overload (dechatter#63) slows it further, so they are loaded cuts.
    deep = {
        REPO_ROOT / record["results"]
        for record in MEASURED.values()
        if "results" in record and record["axial_doc_max_mm"] > LIGHT_DEPTH_MM
    }
    assert len(deep) == 2
    results = [
        path
        for path in sorted((REPO_ROOT / "cad/process/dechatter").glob("*-results.json"))
        if path not in deep
    ]
    assert len(results) >= 3
    # Every analysed pass no wider than LIGHT_WIDTH_MM in those files. Not the
    # passes asked at the top stop: there the spindle fell 13 to 59 rpm in
    # cuts 0.5 to 1.8 mm wide (v5), so they are loaded cuts, not resting speeds.
    low, high = REST_BAND_RPM
    heard = [
        (path.name, p["id"], p["spindle_hz"] * 60)
        for path in results
        for r in json.loads(path.read_text(encoding="utf-8"))["rounds"]
        for p in r["passes"]
        if p["status"] == "analysed"
        and p["width_mm"] <= LIGHT_WIDTH_MM
        and p["rpm"] < top
    ]
    assert len(heard) >= 30
    assert [h for h in heard if not low <= _over_a_stop(h[2]) <= high] == []
    # The stops the record lists are the ones heard, and each is on the grid.
    bands = MILL["spindle_rest_observed_rpm"]
    assert all(
        any(a - 1 <= rpm <= b + 1 for a, b in bands) for _name, _id, rpm in heard
    )
    assert all(low <= _over_a_stop(b) <= high for _a, b in bands)


@pytest.mark.parametrize("key", [WALL, CLIMB_WALL, CHART])
def test_the_deep_wall_and_chart_speeds_are_dial_stops(key: str) -> None:
    # Owner ruling 2026-11-25: the chart moves to the dial's stop 23; the
    # walls run on the stops their limit passes were heard on.
    rpm = SHOP["settings"][key]["rpm"]
    assert any(a <= rpm <= b for a, b in MILL["spindle_rest_observed_rpm"])
    if key in MEASURED:
        width = MEASURED[key]["radial_woc_max_mm"]
        limit = [h for w, h, v, asked in _heard(key) if w == width and asked == rpm]
        assert limit and all(abs(h - rpm) <= 10 for h in limit)


def test_the_chart_speed_left_the_band_where_every_width_chattered() -> None:
    # 2650 lay where both deep sessions chattered (heard 2654-2750); 2483 is
    # where the deep-wall widths held (#3427 conventional 0.2 mm, #3627 climb
    # to 0.5 mm).
    chart = SHOP["settings"][CHART]["rpm"]
    for key in (WALL, CLIMB_WALL):
        heard = _heard(key)
        assert [v for w, h, v, _a in heard if 2600 < h < 2800 and w > 0.3] == [
            "unstable"
        ] * len([1 for w, h, _v, _a in heard if 2600 < h < 2800 and w > 0.3])
        assert any(v == "stable" for w, h, v, asked in heard if asked == chart)
    assert chart < 2600


def test_the_wide_face_names_the_stop_to_rest_the_display_on() -> None:
    record = MEASURED[WIDE_FACE]
    rest = record["display_rest_rpm"]
    no_load_low, no_load_high = record["speed_no_load_rpm"]
    assert no_load_low <= rest <= no_load_high
    assert 0 <= _over_a_stop(rest) <= REST_BAND_RPM[1]
    # It is the stop the limit pass's light pass was heard on, plus what the
    # display reads over the heard speed.
    over_low, over_high = MILL["spindle_display_over_heard_rpm"]
    free = [
        rpm
        for session in [json.loads((REPO_ROOT / record["results"]).read_text("utf-8"))]
        for r in session["rounds"]
        for p in r["passes"]
        if p["kind"] == "truing" and p["status"] == "analysed"
        for rpm in [p["spindle_hz"] * 60]
        if no_load_low <= rpm <= no_load_high
    ]
    assert free
    assert min(free) + over_low - 5 <= rest <= max(free) + over_high
    # One stop below it is the speed v5 ran at: not measured wider than 4.6.
    step = MILL["spindle_speed_step_rpm"]
    assert rest - step < record["speed_in_cut_rpm"][0]


def test_v5_face_speed_has_chatter_a_dial_step_below() -> None:
    # Why plans moved off the v5 face record: its passes ran near 2377 rpm,
    # and the next session heard its limit width chatter near 2272.
    width = MEASURED[V5_FACE]["radial_woc_max_mm"]
    limit = [rpm for w, rpm, _v, _a in _heard(V5_FACE) if w == width]
    assert limit and all(2370 < rpm < 2385 for rpm in limit)
    below = [v for w, rpm, v, _a in _heard(WIDE_FACE) if w == width and rpm < 2300]
    assert below == ["unstable"]


def test_each_record_was_cut_inside_its_cutters_band() -> None:
    assert {record["tool"] for record in MEASURED.values()} <= set(CUTTERS)
    for record in MEASURED.values():
        cutter = CUTTERS[record["tool"]]
        assert record["holder"] == cutter["holder"]
        assert (
            cutter["stickout_min_mm"]
            <= record["stickout_mm"]
            <= cutter["stickout_max_mm"]
        )


def test_the_half_inch_band_runs_from_flute_length_plus_ten_percent() -> None:
    # Owner ruling 2026-11-25 (#3386): "min stickout based on flute length
    # then add 10pct on top of it".
    cutter = CUTTERS[HALF]
    flutes = SHOP["tools"][HALF]["flute_length_mm"]
    assert cutter["stickout_min_mm"] == round(flutes * 1.1, 2)
    assert any("2026-11-25" in line and "2 mm" in line for line in cutter["cite"])


def test_the_half_inch_band_ends_at_the_longest_stickout_a_record_runs_at() -> None:
    # Owner ruling 2026-11-25: the records hold to the longest stick-out the
    # plans use for the cutter (the column clamp's bore today).
    cutter = CUTTERS[HALF]
    half_settings = {k for k, r in MEASURED.items() if r["tool"] == HALF}
    pinned = [
        value
        for _stem, plan in _plans()
        for _at, operation, parameters, names in _measured_cuts._operations(plan)
        if operation.get("settings") in half_settings
        for value in _measured_cuts._pinned(parameters, cutter, names).values()
    ]
    assert max(pinned) == cutter["stickout_max_mm"]


def test_a_setup_runs_at_the_stickout_it_names() -> None:
    # The magnifying bracket's neck runs nearly 2 in out, the rest of the
    # part at 28.45: a setup that names the long stick-out is outside the
    # band, so it may not name a record and its side cuts may stay off one.
    plan = _plan(28.45, 6.6, 2.2)
    plan["parameters"]["neck_mill_projection_min_mm"] = 46.99
    # Naming neither, the setup reads both: the neck's is outside the band.
    (problem,) = _problems(plan)
    assert "parameters.neck_mill_projection_min_mm is 46.99" in problem
    plan["setups"][0]["envelope"] = {
        "longest_tool_mm": ["{{process.half_mill_projection_mm:in.2f}}"]
    }
    assert _problems(plan) == []
    plan["setups"][0]["envelope"] = {
        "longest_tool_mm": ["{{process.neck_mill_projection_min_mm}}"]
    }
    (problem,) = _problems(plan)
    assert "parameters.neck_mill_projection_min_mm is 46.99" in problem
    plan["setups"][0]["operations"][1]["settings"] = CHART
    assert _unmeasured(plan) == []
    plan["setups"][0]["envelope"] = {
        "longest_tool_mm": ["{{process.half_mill_projection_mm:in.2f}}"]
    }
    assert len(_unmeasured(plan)) == 1


@pytest.mark.parametrize("key", sorted(MEASURED))
def test_every_record_holds_across_its_cutters_band(key: str) -> None:
    record = MEASURED[key]
    cutter = CUTTERS[record["tool"]]
    low, high = cutter["stickout_min_mm"], cutter["stickout_max_mm"]
    plan = _plan(low, record["axial_doc_max_mm"], record["radial_woc_max_mm"])
    plan["setups"][0]["operations"][1]["settings"] = key
    for stickout in (low, record["stickout_mm"], high):
        plan["parameters"]["half_mill_projection_mm"] = stickout
        assert _problems(plan) == []
    for stickout in (25.4, low - 0.01, high + 0.01, 50.8):
        plan["parameters"]["half_mill_projection_mm"] = stickout
        (problem,) = _problems(plan)
        assert f"records hold from {low:g} to {high:g} mm stick-out" in problem


def test_every_stickout_parameter_a_plan_pins_is_bounded() -> None:
    # The column clamp pins the faces' stick-out and the bore's: both are
    # read, and a plan that pins none is refused.
    plan = _plan(28.45, 6.6, 2.2)
    plan["parameters"]["bore_mill_projection_min_mm"] = 31.75
    assert _problems(plan) == []
    plan["parameters"]["bore_mill_projection_min_mm"] = 31.76
    (problem,) = _problems(plan)
    assert "parameters.bore_mill_projection_min_mm is 31.76" in problem
    del plan["parameters"]["bore_mill_projection_min_mm"]
    del plan["parameters"]["half_mill_projection_mm"]
    (problem,) = _problems(plan)
    assert "pins no stick-out" in problem


def test_the_wide_face_stickout_is_the_session_reading_to_the_hundredth() -> None:
    record = MEASURED[WIDE_FACE]
    assert record["stickout_mm"] == round(record["report_setup_stickout_mm"], 2)


@pytest.mark.parametrize("key", sorted(MEASURED))
def test_the_envelope_is_what_the_report_shows(key: str) -> None:
    record = MEASURED[key]
    setting = _process_plans.load_shop()["settings"][key]
    assert setting["tool"] == record["tool"]
    assert record["tool"] in _shop_equipment.load()["tools"]
    raw = (REPO_ROOT / record["report"]).read_text(encoding="utf-8")
    report = html.unescape(raw)
    # The report keeps the stick-out its setup was given; the record carries
    # the owner's measurement beside it where the two differ.
    setup = record.get("report_setup_stickout_mm", record["stickout_mm"])
    assert f"stickout_mm = {setup}" in report
    assert f'direction = "{record["direction"]}"' in report
    # The record's passes are the ones cut in its direction.
    passes = [p[:5] for p in _passes(raw) if p[5] == record["direction"]]
    assert passes
    depth, width = record["axial_doc_max_mm"], record["radial_woc_max_mm"]
    # The limit itself was cut, at the setting's speed, and was stable.
    assert (depth, setting["rpm"], width, "analysed", "stable") in passes
    # Nothing deeper was cut stable; and at the limit's depth and the setting's
    # speed, every pass no wider than the limit was stable.
    deepest = max(p[0] for p in passes if p[4] == "stable")
    assert deepest == depth
    at_speed = [p for p in passes if p[1] == setting["rpm"] and p[0] == depth]
    assert all(p[4] == "stable" for p in at_speed if p[2] <= width)


def test_the_conventional_wall_keeps_a_width_step_under_chatter() -> None:
    # #3427: 0.4 mm held at 1839 and 0.8 chattered there and at 1513; at the
    # chart's 2483 only 0.2 held conventional.
    record = MEASURED[WALL]
    passes = _passes((REPO_ROOT / record["report"]).read_text(encoding="utf-8"))
    conventional = {
        (rpm, w): v for _d, rpm, w, _s, v, way in passes if way == "conventional"
    }
    assert conventional[(1839, 0.4)] == conventional[(1513, 0.4)] == "stable"
    assert conventional[(1839, 0.8)] == conventional[(1513, 0.8)] == "chatter"
    assert conventional[(2483, 0.2)] == "stable"
    assert conventional[(2483, 0.4)] == "chatter"
    assert record["radial_woc_max_mm"] == 0.4


def test_the_climb_wall_keeps_a_width_step_under_the_borderline_one() -> None:
    # #3627: 0.5 mm held at 2046 and 2483 but chattered at 1400; the limit
    # takes 0.3. #3427's climb check at 13.5 mm deep agrees at 2483.
    record = MEASURED[CLIMB_WALL]
    passes = _passes((REPO_ROOT / record["report"]).read_text(encoding="utf-8"))
    climb = {(rpm, w): v for _d, rpm, w, _s, v, way in passes if way == "climb"}
    assert climb[(2483, 0.5)] == climb[(2046, 0.5)] == "stable"
    assert climb[(1400, 0.5)] == "chatter"
    check = _passes((REPO_ROOT / MEASURED[WALL]["report"]).read_text(encoding="utf-8"))
    at_check = {(rpm, w): v for _d, rpm, w, _s, v, way in check if way == "climb"}
    assert at_check[(2483, 0.4)] == at_check[(2483, 0.6)] == "stable"
    assert at_check[(2483, 0.8)] == "chatter"
    assert record["radial_woc_max_mm"] == 0.3


def test_v6_logs_a_stable_pass_between_two_chattering_ones() -> None:
    # Why the deep record stops at 2.2 mm although the report recommends 2.7.
    record = MEASURED[SETTING]
    passes = _passes((REPO_ROOT / record["report"]).read_text(encoding="utf-8"))
    at_depth = {
        (rpm, width): verdict
        for d, rpm, width, _s, verdict, _way in passes
        if d == 6.6
    }
    assert at_depth[(2320, 2.7)] == "stable"
    assert at_depth[(2330, 2.4)] == "chatter"
    assert at_depth[(2400, 2.6)] == "chatter"
    assert record["radial_woc_max_mm"] < 2.4


@pytest.mark.parametrize("stickout", [27.94, 28.45, 31.75])
def test_a_cut_inside_the_envelope_passes(stickout: float) -> None:
    assert _problems(_plan(stickout, 6.6, "{{process.trim_mm}}")) == []


@pytest.mark.parametrize(
    ("stickout", "depth", "width", "message"),
    [
        (25.4, 6.6, 2.2, "half_mill_projection_mm is 25.4"),
        (31.8, 6.6, 2.2, "half_mill_projection_mm is 31.8"),
        (27.94, 10.54, 0.5, "axial_doc_mm 10.54 exceeds the measured 6.6"),
        (27.94, 6.6, 3.173, "radial_woc_mm 3.173 exceeds the measured 2.2"),
        (27.94, 6.6, "{{cad.width_mm}}", "not a number or one process parameter"),
        (27.94, 6.6, "{{process.absent_mm}}", "not a number or one process parameter"),
    ],
)
def test_a_cut_outside_the_envelope_is_refused(stickout, depth, width, message) -> None:
    (problem,) = _problems(_plan(stickout, depth, width))
    assert message in problem


@pytest.mark.parametrize(
    ("key", "depth", "width", "message"),
    [
        (WALL, 13.5, 0.4, None),
        (WALL, 13.6, 0.4, "axial_doc_mm 13.6 exceeds the measured 13.5"),
        (WALL, 10.54, 0.76, "radial_woc_mm 0.76 exceeds the measured 0.4"),
        (CLIMB_WALL, 17.0, 0.3, None),
        (CLIMB_WALL, 17.0, 0.31, "radial_woc_mm 0.31 exceeds the measured 0.3"),
        (CLIMB_WALL, 17.1, 0.254, "axial_doc_mm 17.1 exceeds the measured 17"),
    ],
)
def test_a_deep_wall_is_bounded_by_its_record(key, depth, width, message) -> None:
    plan = _plan(31.75, depth, width)
    plan["setups"][0]["operations"][1]["settings"] = key
    found = _problems(plan)
    if message is None:
        assert found == []
    else:
        (problem,) = found
        assert message in problem


def test_a_family_operation_reads_its_own_parts_parameters() -> None:
    # A family plan (cad/process/README.md, Family plans): a part's own
    # parameter bounds the cuts of the setups and operations that name it.
    plan = _plan(27.94, "{{process.skim_mm}}", 2.2)
    plan["parts"] = [
        {"id": "thin", "parameters": {"skim_mm": 0.5}},
        {"id": "thick", "parameters": {"skim_mm": 7.0}},
    ]
    (problem,) = _problems(plan)
    assert "not a number or one process parameter" in problem
    plan["setups"][0]["part"] = "thin"
    assert _problems(plan) == []
    plan["setups"][0]["operations"][1]["part"] = "thick"
    (problem,) = _problems(plan)
    assert "axial_doc_mm 7 exceeds the measured 6.6" in problem


def test_a_measured_setting_without_declared_cuts_is_refused() -> None:
    plan = _plan(27.94, 6.6, 2.2)
    del plan["setups"][0]["operations"][1]["milling_cuts"]
    (problem,) = _problems(plan)
    assert "declares no milling_cuts" in problem


def test_a_side_or_end_cut_off_every_record_is_refused() -> None:
    # On the chart setting (or with no setting, the tool alone), a side or
    # end cut by the measured cutter in its records' material is refused at a
    # stick-out inside the band; a slot is not (no record is full width).
    plan = _plan(28.45, 10.54, 0.76)
    operation = plan["setups"][0]["operations"][1]
    operation["settings"] = CHART
    (problem,) = _unmeasured(plan)
    assert "side cut 'trim'" in problem and CHART in problem
    del operation["settings"]
    (problem,) = _unmeasured(plan)
    assert "no setting" in problem
    operation["milling_cuts"][0]["kind"] = "end"
    assert len(_unmeasured(plan)) == 1
    operation["milling_cuts"][0]["kind"] = "slot"
    assert _unmeasured(plan) == []
    operation["milling_cuts"][0]["kind"] = "side"
    # Outside the band no record holds (the amplitude bar's 2 in): the chart.
    plan["parameters"] = {"half_mill_projection_min_mm": 50.8}
    assert _unmeasured(plan) == []
    # Another material: no record was cut in it.
    plan["parameters"] = {"half_mill_projection_mm": 28.45}
    plan["material_key"] = "c360-brass"
    assert _unmeasured(plan) == []
    plan["material_key"] = "rocker-1018-cold-finished"
    operation["settings"] = WALL
    assert _unmeasured(plan) == []


def test_only_a_stickout_known_to_be_outside_the_band_exempts_a_cut() -> None:
    # An unresolvable stick-out proves nothing, so the cut stays checked; a
    # stick-out within problems()'s tolerance of the band's end is inside it.
    plan = _plan(28.45, 10.54, 0.76)
    plan["setups"][0]["operations"][1]["settings"] = CHART
    plan["parameters"] = {"half_mill_projection_min_mm": "{{cad.unknown_mm}}"}
    assert len(_unmeasured(plan)) == 1
    plan["parameters"] = {"half_mill_projection_min_mm": 31.75 + 1e-12}
    assert len(_unmeasured(plan)) == 1
    plan["parameters"] = {
        "half_mill_projection_min_mm": 50.8,
        "half_mill_projection_mm": "{{cad.unknown_mm}}",
    }
    assert len(_unmeasured(plan)) == 1


def test_a_cutter_with_no_records_yet_is_not_checked() -> None:
    plan = _plan(28.45, 10.54, 0.76)
    plan["setups"][0]["operations"][1]["settings"] = CHART
    cutters = {**CUTTERS, "endmill-carbide-3fl-1-4": CUTTERS[HALF]}
    plan["tools"].append({"id": "T9", "ref": "endmill-carbide-3fl-1-4"})
    plan["setups"][0]["operations"].append(
        {"tool": "T9", "milling_cuts": [{"kind": "side", "name": "x"}]}
    )
    found = _measured_cuts.unmeasured(plan, MEASURED, cutters, SHOP["settings"])
    assert len(found) == 1


def _plans() -> list[tuple[str, dict]]:
    paths = sorted(_process_plans.PROCESS_ROOT.glob("*/plan.toml"))
    assert paths
    return [
        (path.parent.name, tomllib.loads(path.read_text(encoding="utf-8")))
        for path in paths
    ]


def test_no_plan_cuts_outside_a_measured_envelope() -> None:
    found = {stem: problems for stem, plan in _plans() if (problems := _problems(plan))}
    assert found == {}


def test_every_side_and_end_cut_a_record_can_hold_names_one() -> None:
    # Owner ruling 2026-11-25: every 1/2 in side cut in 1018 fits a measured
    # record; full-width slots and the clamp bore's helix stay on the chart
    # until #3428, and the amplitude bar's 2 in stick-out is outside the band.
    found = {
        stem: problems for stem, plan in _plans() if (problems := _unmeasured(plan))
    }
    assert found == {}
