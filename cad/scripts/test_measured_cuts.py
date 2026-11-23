"""measured-cuts.toml: each measured setting's envelope is what its dechatter
report shows, and no plan uses a measured setting outside it."""

from __future__ import annotations

import html
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
    assert set(MEASURED) >= {"em-half-carbide-1018-v5-face", SETTING}


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
    # Nothing deeper was cut stable, and no stable pass at the limit's depth
    # was wider unless a narrower pass at that depth chattered below it.
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
