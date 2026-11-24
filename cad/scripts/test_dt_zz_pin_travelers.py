"""The drive train's reamed bands are gauged with Class ZZ pins.

Owner ruling 2026-11-23 (tool audit Q1, re-answered on the corrected facts):
"ZZ singles per the record: 29 pins (17 plus GO, 12 minus NO-GO), about $130.
Accept that good holes near a limit may be refused; the traveler mikes each
pin so the real window is known per pin." Each plan here names its band's
``zz-pins-<low>-<high>`` record (no Class X ``plug-gauges-*`` pair), carries
the largest GO pin and the smallest NO-GO pin the sheet may use (the band less
one pin's ZZ tolerance at each end: the sure-pass window it prints), and mikes
both pins on the micrometer before any op reams or gauges with them.
"""

from __future__ import annotations

import tomllib

import pytest

import _process_plans

IN = 25.4

# stem: (the band's record, the [parameters] keys of the band's limits and of
# the two pin limits; None where the band is bound from the drawing).
# MHA-DT-38's bore left the list (fit audit 2026-11-23 F10): the MHA-DT-37
# pivot is turned to it, so no pin gauges it.
PLANS = {
    "dt_cone_tip_end_screw": ("zz-pins-0630-0635", None, "go_pin_max_in", "nogo_pin_min_in"),
    "dt_crank_hub": ("zz-pins-3760-3765", None, "go_pin_max_in", "nogo_pin_min_in"),
    "dt_pinion_arbor": (
        "zz-pins-3135-3140",
        ("strap_bore_min_in", "strap_bore_max_in"),
        "strap_go_pin_max_in",
        "strap_nogo_pin_min_in",
    ),
    "dt_pinion_cam": ("zz-pins-2510-2515", None, "go_pin_max_in", "nogo_pin_min_in"),
    "dt_pinion_pivot_block": ("zz-pins-2510-2515", None, "go_pin_max_in", "nogo_pin_min_in"),
    "dt_cone_swing_platform": ("zz-pins-2500-2505", None, "go_pin_max_in", "nogo_pin_min_in"),
    "dt_arbor_pedestal": ("zz-pins-3760-3765", None, "go_pin_max_in", "nogo_pin_min_in"),
}

# Plans that gauge a mating part's bores with the pins and ream none of the
# band themselves (their reamer cuts another hole).
REGAUGE_ONLY = {"dt_pinion_arbor"}


def _plan(stem: str) -> dict:
    return tomllib.loads(_process_plans.plan_path(stem).read_text(encoding="utf-8"))


def _ops(plan: dict) -> list[dict]:
    return [op for setup in plan["setups"] for op in setup.get("operations", [])]


def _gauges(op: dict) -> list[str]:
    checks = op.get("gauge_checks")
    return [c["gauge"] for c in checks] if isinstance(checks, list) else []


@pytest.mark.parametrize("stem", sorted(PLANS))
def test_the_plan_lists_the_bands_zz_pins_and_no_class_x_pair(stem):
    plan = _plan(stem)
    record = PLANS[stem][0]
    shop = _process_plans.load_shop()
    assert record in shop["gauges"] and record in shop["tools"]
    refs = {t["ref"]: t for t in plan["tools"]}
    assert refs[record].get("status") == "to_order"
    named = set(refs) | {g for op in _ops(plan) for g in _gauges(op)}
    assert not {r for r in named if r.startswith("plug-gauges-")}


@pytest.mark.parametrize("stem", sorted(PLANS))
def test_the_printed_window_is_the_band_less_one_zz_tolerance(stem):
    record, band_keys, go_key, nogo_key = PLANS[stem]
    p = _plan(stem)["parameters"]
    gauge = _process_plans.load_shop()["gauges"][record]
    low, high = (v / IN for v in gauge["range_mm"])
    tol = gauge["resolution_mm"] / IN
    assert tol == pytest.approx(0.0002, abs=1e-6)
    if band_keys:
        assert p[band_keys[0]] == pytest.approx(low, abs=1e-5)
        assert p[band_keys[1]] == pytest.approx(high, abs=1e-5)
    assert p[go_key] == pytest.approx(low + tol, abs=1e-5)
    assert p[nogo_key] == pytest.approx(high - tol, abs=1e-5)


@pytest.mark.parametrize("stem", sorted(PLANS))
def test_the_pins_are_miked_before_they_gauge_or_the_reamer_cuts(stem):
    record = PLANS[stem][0]
    ops = _ops(_plan(stem))
    miked = next(
        i
        for i, op in enumerate(ops)
        if "micrometers" in _gauges(op) and "GO pin" in op["instruction"] and "mike" in op["instruction"]
    )
    gauged = min(i for i, op in enumerate(ops) if record in _gauges(op))
    reamed = [i for i, op in enumerate(ops) if op.get("tool") == "reamer"]
    assert miked < gauged
    assert stem in REGAUGE_ONLY or not reamed or miked < min(reamed)
