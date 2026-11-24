"""measured-cuts.toml: each measured setting's envelope is what its dechatter
report shows, and no plan uses a measured setting outside it."""

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
SETTING = "em-half-carbide-1018-v6-deep"
WIDE_FACE = "em-half-carbide-1018-3439-face"
V5_FACE = "em-half-carbide-1018-v5-face"


def _passes(report: str) -> list[tuple[float, int, float, str, str]]:
    """(depth mm, rpm, width mm, status, verdict) of every test pass in a
    dechatter report's round log."""
    text = re.sub(r"</t[dh]>", "|", report)
    text = html.unescape(re.sub(r"<[^>]+>", "\n", text))
    found = []
    rows = re.split(r"(Round \d+: [\d.]+ mm deep)", text)
    for heading, body in zip(rows[1::2], rows[2::2]):
        depth = float(re.search(r"([\d.]+) mm deep", heading).group(1))
        cells = [cell.strip() for cell in body.split("|")]
        for index, cell in enumerate(cells):
            if cell == "test":
                rpm, width = int(cells[index + 1]), float(cells[index + 2].split()[0])
                found.append((depth, rpm, width, cells[index + 5], cells[index + 6]))
    return found


def _plan(stickout: float, depth: object, width: object) -> dict:
    return {
        "parameters": {"half_mill_projection_mm": stickout, "trim_mm": 2.2},
        "setups": [
            {
                "operations": [
                    {"instruction": "no setting"},
                    {
                        "settings": SETTING,
                        "milling_cuts": [
                            {
                                "name": "trim",
                                "axial_doc_mm": depth,
                                "radial_woc_mm": width,
                            }
                        ],
                    },
                ]
            }
        ],
    }


def test_records_exist() -> None:
    assert set(MEASURED) >= {V5_FACE, SETTING, WIDE_FACE}


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


def test_v5_face_speed_has_chatter_a_dial_step_below() -> None:
    # Why plans moved off the v5 face record: its passes ran near 2377 rpm,
    # and the next session heard its limit width chatter near 2272.
    width = MEASURED[V5_FACE]["radial_woc_max_mm"]
    limit = [rpm for w, rpm, _v, _a in _heard(V5_FACE) if w == width]
    assert limit and all(2370 < rpm < 2385 for rpm in limit)
    below = [v for w, rpm, v, _a in _heard(WIDE_FACE) if w == width and rpm < 2300]
    assert below == ["unstable"]


def test_a_shorter_stickout_passes_only_where_the_record_allows_it() -> None:
    record = MEASURED[WIDE_FACE]
    plan = _plan(27.94, 1.27, 6.4)
    plan["setups"][0]["operations"][1]["settings"] = WIDE_FACE
    assert record["stickout_min_mm"] == MEASURED[SETTING]["stickout_mm"]
    assert _measured_cuts.problems(plan, MEASURED) == []
    plan["parameters"]["half_mill_projection_mm"] = record["stickout_mm"]
    assert _measured_cuts.problems(plan, MEASURED) == []
    for stickout in (25.4, 30.0):
        plan["parameters"]["half_mill_projection_mm"] = stickout
        (problem,) = _measured_cuts.problems(plan, MEASURED)
        assert "measured at 27.94 to 28.448 mm stick-out" in problem
    plan["parameters"]["half_mill_projection_mm"] = 27.94
    plan["setups"][0]["operations"][1]["milling_cuts"][0]["radial_woc_mm"] = 7.1
    (problem,) = _measured_cuts.problems(plan, MEASURED)
    assert "radial_woc_mm 7.1 exceeds the measured 6.4" in problem


@pytest.mark.parametrize("key", sorted(MEASURED))
def test_the_envelope_is_what_the_report_shows(key: str) -> None:
    record = MEASURED[key]
    setting = _process_plans.load_shop()["settings"][key]
    assert setting["tool"] == record["tool"]
    assert record["tool"] in _shop_equipment.load()["tools"]
    report = (REPO_ROOT / record["report"]).read_text(encoding="utf-8")
    # The report keeps the stick-out its setup was given; the record carries
    # the owner's measurement beside it.
    assert f"stickout_mm = {record['report_setup_stickout_mm']}" in html.unescape(
        report
    )
    passes = _passes(report)
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


def test_v6_logs_a_stable_pass_between_two_chattering_ones() -> None:
    # Why the deep record stops at 2.2 mm although the report recommends 2.7.
    record = MEASURED[SETTING]
    passes = _passes((REPO_ROOT / record["report"]).read_text(encoding="utf-8"))
    at_depth = {
        (rpm, width): verdict for d, rpm, width, _s, verdict in passes if d == 6.6
    }
    assert at_depth[(2320, 2.7)] == "stable"
    assert at_depth[(2330, 2.4)] == "chatter"
    assert at_depth[(2400, 2.6)] == "chatter"
    assert record["radial_woc_max_mm"] < 2.4


def test_a_cut_inside_the_envelope_passes() -> None:
    assert (
        _measured_cuts.problems(_plan(27.94, 6.6, "{{process.trim_mm}}"), MEASURED)
        == []
    )


@pytest.mark.parametrize(
    ("stickout", "depth", "width", "message"),
    [
        (25.4, 6.6, 2.2, "half_mill_projection_mm is 25.4"),
        (30.0, 6.6, 2.2, "half_mill_projection_mm is 30.0"),
        (27.94, 10.54, 0.5, "axial_doc_mm 10.54 exceeds the measured 6.6"),
        (27.94, 6.6, 3.173, "radial_woc_mm 3.173 exceeds the measured 2.2"),
        (27.94, 6.6, "{{cad.width_mm}}", "not a number or one process parameter"),
        (27.94, 6.6, "{{process.absent_mm}}", "not a number or one process parameter"),
    ],
)
def test_a_cut_outside_the_envelope_is_refused(stickout, depth, width, message) -> None:
    (problem,) = _measured_cuts.problems(_plan(stickout, depth, width), MEASURED)
    assert message in problem


def test_a_measured_setting_without_declared_cuts_is_refused() -> None:
    plan = _plan(27.94, 6.6, 2.2)
    del plan["setups"][0]["operations"][1]["milling_cuts"]
    (problem,) = _measured_cuts.problems(plan, MEASURED)
    assert "declares no milling_cuts" in problem


def test_no_plan_cuts_outside_a_measured_envelope() -> None:
    plans = sorted(_process_plans.PROCESS_ROOT.glob("*/plan.toml"))
    assert plans
    found = {
        path.parent.name: problems
        for path in plans
        if (
            problems := _measured_cuts.problems(
                tomllib.loads(path.read_text(encoding="utf-8")), MEASURED
            )
        )
    }
    assert found == {}
