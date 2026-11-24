"""The MHA-PD-23 transgear pin's lathe traveler agrees with its model.

``pd_transgear_pin`` is turned from 1/4 in bar on ``turned_shaft``: the tip end
out on a tailstock centre in a stub beyond the tip plane, the one-diameter
journal finish-turned, polished and tried in its mates and in the MHA-PD-18
arm it is bonded in, then turned round twice to face and dome each end. The
adapter binds the drawing module's bands; these tests hold the plan's own
numbers to them: the head's facing window, the stub and the stub cut, the
polish allowance and the regrip stickouts.
"""

from __future__ import annotations

import math
import tomllib

import pytest

import _process_plans
import export_features

STEM = "pd_transgear_pin"
IN = 25.4


@pytest.fixture(scope="module")
def plan() -> dict:
    return tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def parameters(plan: dict) -> dict:
    return plan["parameters"]


@pytest.fixture(scope="module")
def features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


@pytest.fixture(scope="module")
def shop() -> dict:
    return _process_plans.load_shop()


def _cap(radius_in: float, dia_in: float) -> float:
    """A dome's height at its radius, ending full on a diameter."""
    return radius_in - math.sqrt(radius_in**2 - (dia_in / 2) ** 2)


def test_the_pin_is_enrolled_on_turned_shaft(plan: dict) -> None:
    assert STEM in _process_plans.TRAVELER_STEMS
    assert plan["cad"]["adapter"] == "turned_shaft"
    # The 1018 bar is the pin's; the brass is the split bush's (#3500).
    assert plan["stock_refs"] == ["1018-round-1-4", "c360-round-1-2"]


def test_the_arm_is_tried_on_the_shank_and_nothing_is_turned_to_a_reading(
    plan: dict, parameters: dict, features: dict
) -> None:
    """Owner ruling 2026-11-24, fit audit question 4: the pin is one
    diameter, bonded in the arm. No land, no ream reading, no Class X plugs:
    the arm's one limit is its .127 set pin, and the arm slides on by hand."""
    assert "step_land" not in features
    assert not [name for name in parameters if name.startswith("land_")]
    assert {tool["ref"] for tool in plan["tools"]} & {
        "plug-gauges-1260-1265",
        "plug-gauges-1261-1264",
    } == set()
    ops = [op for setup in plan["setups"] for op in setup["operations"]]
    text = " ".join(op["instruction"] + " " + op.get("inspection", "") for op in ops)
    assert "step_land" not in text and "plug" not in text.lower()
    assert "the .127 pin does not enter" in ops[1]["inspection"]
    trials = [
        op
        for op in ops
        if "the arm slides on by hand up to the seat" in op.get("inspection", "")
    ]
    assert len(trials) == 2


def test_the_head_window_holds_the_head_land_for_any_head_dia(
    parameters: dict, features: dict
) -> None:
    head = [d / IN for d in features["step_head"]["dia"]]
    # Filed between the radius gauges' two leaves: any radius they pass on any
    # head Ø in its band.
    leaves = [
        parameters[f"dome_datum_leaf_radius_{side}_in"] for side in ("min", "max")
    ]
    caps = [_cap(radius, d) for radius in leaves for d in head]
    land = [s / IN for s in features["shoulder"]["station"]]
    # Faced to the window, then domed: the head land lies in its band for a
    # head anywhere in its Ø band.
    assert parameters["head_face_min_in"] - max(caps) >= land[0] - 1e-9
    assert parameters["head_face_max_in"] - min(caps) <= land[1] + 1e-9
    assert parameters["head_face_min_in"] < parameters["head_face_max_in"]
    for end in ("min", "max"):
        assert parameters[f"head_face_{end}_mm"] == pytest.approx(
            parameters[f"head_face_{end}_in"] * IN
        )


def test_the_stub_carries_the_centre_and_is_cut_short_of_the_tip_station(
    parameters: dict, features: dict
) -> None:
    stub = parameters["centre_stub_in"]
    assert parameters["centre_stub_mm"] == pytest.approx(stub * IN)
    # The bar end faced .02 beyond the stub.
    assert parameters["face_allowance_in"] == pytest.approx(stub + 0.02)
    # The passes start in the stub, short of the centre's point.
    assert 0 < parameters["turn_start_z_mm"] < parameters["centre_stub_mm"]
    # The stub is cut a facing skim beyond the tip's station from the seat,
    # inside the station's band.
    station = features["far_end"]["station"]
    nominal = features["far_end"]["station_nominal"]
    assert nominal < parameters["tip_cut_in"] * IN <= station[1]
    # The land is roughed short of the seat, which the sharp-nose tool faces.
    assert parameters["seat_rough_z_mm"] == pytest.approx(-(nominal - 0.005 * IN))


def test_the_head_is_turned_past_the_part_off_kerf(
    parameters: dict, features: dict
) -> None:
    length = features["far_end"]["length_ref"]
    part_off = length + parameters["regrip_allowance_in"] * IN
    kerf_end = part_off + parameters["part_kerf_in"] * IN
    assert parameters["head_turn_end_z_mm"] < -kerf_end


def test_the_journal_is_polished_to_the_shims_bore_and_accepted_on_its_mates(
    plan: dict, parameters: dict, features: dict
) -> None:
    """Fit audit 2026-11-23: the journal is made to fit. The micrometer only
    steers the polish (never over the bought shims' bore); the mates tried on
    the journal accept it, and no step quotes the drawing module's analysis
    band or clearance."""
    low, high = (d / IN for d in features["outer"]["dia"])
    assert parameters["polish_stop_in"] == pytest.approx(high)
    assert parameters["polish_dia_min_in"] > parameters["polish_stop_in"]
    # The polish takes off no more than .0004: the finish-turned window's top
    # over the stop (it was checked against the analysis band's bottom, which
    # fit audit owner question 5 moves from .1248 to .1245 without changing
    # the turning).
    assert (
        parameters["polish_dia_max_in"] - parameters["polish_stop_in"] <= 0.0004 + 1e-9
    )
    assert low < parameters["polish_stop_in"]
    for end in ("min", "max"):
        assert parameters[f"polish_dia_{end}_mm"] == pytest.approx(
            parameters[f"polish_dia_{end}_in"] * IN
        )
    text = _process_plans.plan_path(STEM).read_text(encoding="utf-8")
    for token in ("cad.outer_dia_min", "cad.outer_dia_max", "cad.outer_clearance_m"):
        assert token not in text, token
    steps = [
        op
        for setup in plan["setups"]
        for op in setup["operations"]
        if "turns free" in op.get("inspection", "")
    ]
    # On the lathe once the stub is cut off, and again at the bench.
    assert len(steps) == 2
    for step in steps:
        assert "no shake" in step["inspection"]
        assert "{{cad.outer_mates}}" in step["instruction"]


def test_each_regrip_stands_within_the_shops_stickout(
    parameters: dict, features: dict, shop: dict
) -> None:
    ratio = shop["limits"]["stickout_ld_max"]
    head_dia = features["step_head"]["dia"][1] / IN
    radius = parameters["dome_datum_leaf_radius_min_in"]
    assert "step_land" not in features
    shank_dia = features["outer"]["dia"]
    # Head out: the bush's front on the shank under the head, past the faced
    # head.
    out = parameters["regrip_stickout_datum_in"]
    assert parameters["head_face_max_in"] < out
    assert out <= ratio * shank_dia[0] / IN
    assert _cap(radius, head_dia) < parameters["head_face_max_in"]
    # Tip out: the bush's front on the journal past the groove.
    groove = features["groove"]
    tip = features["far_end"]["station"][1] - groove["station"][0]
    out = parameters["regrip_stickout_far_in"]
    assert out * IN > tip + groove["width"][1]
    assert out <= ratio * groove["dia"][0] / IN


def test_the_jaws_never_grip_the_shank(plan: dict, parameters: dict) -> None:
    """#3500: the 3-jaw closes no smaller than Ø.175 (owner's measurement
    2026-11-24, #3489), over the pin's Ø.125 shank. The jaws grip the 1/4 in
    bar, then a split bush of 1/2 in brass that closes on the shank."""
    least_grip_in = 0.175
    grips = [setup["lathe_hold"]["grip_diameter_mm"] for setup in plan["setups"][:4]]
    assert grips == [
        "{{cad.stock_dia_mm}}",
        "{{process.bush_dia_mm}}",
        "{{process.bush_dia_mm}}",
        "{{process.bush_dia_mm}}",
    ]
    assert "lathe_hold" not in plan["setups"][4]
    assert parameters["stock_dia_in"] > least_grip_in
    assert parameters["bush_dia_in"] > least_grip_in
    assert parameters["bush_dia_mm"] == pytest.approx(parameters["bush_dia_in"] * IN)
    assert parameters["bush_length_mm"] == pytest.approx(
        parameters["bush_length_in"] * IN
    )
    # Held on bush_grip_in, the rest out of the jaws.
    assert parameters["bush_stickout_mm"] == pytest.approx(
        (parameters["bush_length_in"] - parameters["bush_grip_in"]) * IN
    )
    text = _process_plans.plan_path(STEM).read_text(encoding="utf-8")
    assert "shim wrap" not in text
