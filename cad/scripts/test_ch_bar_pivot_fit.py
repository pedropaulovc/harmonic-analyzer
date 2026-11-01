"""Offline contract: the amplitude bar's top notch straddles its channel lever,
and the MHA-CH-11 pin is pressed into both notch cheeks and runs in the
lever, with every fit held at the worst case of its printed bands (policy
drawing-guidelines.md rule 17 (walls and webs)).

``ch_bar_pivot_pin_spec`` reads only the two parts it joins; the restated
floors and bands are pinned to their sources here.
"""

from __future__ import annotations

import math

import pytest

import _config
import ch_amplitude_bar_spec as bar
import ch_bar_pivot_pin_spec as pin
import ch_channel_lever_spec as lever
import rocker_bank_layout as bank
from _hole_spec import NUMBER_DRILL_MM


def test_restated_floors_are_their_sources() -> None:
    drilled = _config.title_block("drilled_hole", unit=lever.UNIT)
    assert drilled["minus_in"] == 0.0
    assert drilled["plus_in"] * 25.4 == pytest.approx(pin.DRILLED_PLUS)
    assert pin.RUNNING_FLOOR == bank.RUNNING_FLOOR
    # The levers' hubs set the pitch the neighbour stack is judged at.
    assert lever.HUB_LENGTH == bank.PITCH
    assert pin.BAR_HOLE_DIA is bar.TOP_PIN_HOLE_DIA
    assert pin.BAR_HOLE_BAND is bar.TOP_PIN_HOLE_BAND
    # ANSI B4.1 FN2, 0-0.12 in: 0.85 thousandths of an inch at most.
    assert pin.PRESS_INTERFERENCE_MAX == pytest.approx(0.02159, abs=1e-6)
    # The hole's offset prints at three places on the bar sheet: .XXX.
    from _printed_tolerance import printed_band_mm
    import ch_amplitude_bar_notes as bar_notes

    places = bar_notes.DRAWING_PRECISION["TopPinProfile"]["TopPinX"]
    assert pin.HOLE_LOCATION_TOLERANCE == printed_band_mm(places) == 0.13
    assert pin.BAR_STOCK_UNDERSIZE is bar.BAR_STOCK_UNDERSIZE
    # The roof budget's bands: the lever's height and the notch's depth and
    # the pin's drop, each at its own sheet's two places.
    import ch_channel_lever_notes as lever_notes

    lever_places = lever_notes.DRAWING_PRECISION["LeverOutline"]["BarHeight"]
    assert pin.LEVER_LINEAR_2PL == printed_band_mm(lever_places, unit=lever.UNIT)
    assert bar_notes.DRAWING_PRECISION["BarProfile"]["TopNotchHeight"] == 2
    assert bar_notes.DRAWING_PRECISION["TopPinProfile"]["TopPinDrop"] == 2
    assert pin.BAR_LINEAR_2PL == printed_band_mm(2)


def test_the_pin_is_flush_with_the_bar_and_runs_in_the_lever() -> None:
    assert pin.PIN_INSTALLED_LENGTH == bar.BAR_WIDTH
    assert pin.PIN_END_PROUD_MAX == 0.0
    assert pin.PIN_DIA == pytest.approx(5.0 / 64.0 * 25.4)
    assert lever.BAR_PIN_HOLE_SPEC.size == "#47"
    assert NUMBER_DRILL_MM["#47"] == 1.994


def test_worst_case_joint_budget() -> None:
    b = pin.BUDGET
    # Press in the reamed cheeks: real at both band extremes, inside FN2.
    assert b["interference_min"] == pytest.approx(0.000635, abs=1e-6)
    assert b["interference_max"] == pytest.approx(0.020955, abs=1e-6)
    assert 0.0 < b["interference_min"] < b["interference_max"]
    assert b["interference_max"] <= pin.PRESS_INTERFERENCE_MAX
    # Running fit in the lever's #47 hole.
    assert b["running_clearance_min"] == pytest.approx(0.004545, abs=1e-6)
    assert b["running_clearance_max"] == pytest.approx(0.116305, abs=1e-6)
    # Flush ends leave the #1038 top-notch gap untouched.
    assert b["neighbour_clearance_min"] == pytest.approx(0.1013, abs=1e-6)
    assert b["neighbour_clearance_min"] >= pin.RUNNING_FLOOR
    # The 14.0 roof under the .43 lever turned the full relative swing.
    assert b["notch_roof_clearance_min"] == pytest.approx(0.5062, abs=1e-4)
    assert b["notch_roof_clearance_min"] >= pin.RUNNING_FLOOR
    # The far face, the offset at its long limit on the narrowest stock.
    assert b["hole_face_wall_min"] == pytest.approx(2.00487, abs=1e-6)
    assert b["hole_face_wall_min"] >= pin.RULE12_WALL_TARGET
    # The .30 blank under the title block's .XX band.
    assert b["blank_excess_min"] == pytest.approx(1.016, abs=1e-6)
    assert b["blank_excess_max"] == pytest.approx(1.5748, abs=1e-6)


def test_the_cheeks_the_pin_presses_into_hold_the_approved_exception() -> None:
    """The printed ledge cheek holds the drawing-guidelines.md rule 17 (walls and webs) floor; the far cheek, derived
    from the widest notch on the narrowest stock, is the #1038 shortfall the
    owner approved at 1.17 MIN (2026-10-15). The pin fills the hole it presses
    into and changes neither."""
    import ch_amplitude_bar_notes as bar_notes

    b = pin.BUDGET
    assert b["tine_min_printed"] == pytest.approx(1.55, abs=1e-6)
    assert b["tine_min_printed"] >= pin.RULE12_WALL_FLOOR
    assert b["tine_min_derived"] == pytest.approx(1.2992, abs=1e-6)
    assert b["tine_min_derived"] < pin.RULE12_WALL_FLOOR  # #1038, not this pin
    assert b["tine_min_derived"] >= bar_notes.CHEEK_WALL_APPROVED_MIN["top"]


def test_neighbour_stack_closes_the_inter_bar_gap_exactly() -> None:
    """The gap (pitch less the widest bar) holds the bar's float on its lever,
    both ledges' and both plate offsets' bands, both dressed pin ends and the
    neighbour clearance: nothing left out (#1038 option 2)."""
    b = pin.BUDGET
    notch_max = bar.TOP_NOTCH_WIDTH + bar.TOP_NOTCH_WIDTH_BAND[0]
    lever_min = lever.LEVER_THICKNESS - lever.LEVER_THICKNESS_TOLERANCE
    assert bank.PITCH - (
        bar.BAR_WIDTH
        + (notch_max - lever_min)
        + 2.0 * bar.NOTCH_OFFSET_TOLERANCE_MM
        + 2.0 * lever.PLATE_OFFSET_TOLERANCE
        + 2.0 * pin.PIN_END_PROUD_MAX
    ) == pytest.approx(b["neighbour_clearance_min"])
    # 7.0565 - 6.35 - (3.35 - 2.9464) - 0.10 - 0.1016.
    assert (notch_max, lever_min) == pytest.approx((3.35, 2.9464))


def _lever_bar_swing_deg() -> float:
    """|lever tilt - bar tilt| over one cam turn at bar stations 0..80 mm,
    the rocker's solved swing applied to its R800 arc in either sense."""
    import ch_connecting_rod_spec as rod
    import channel_frame_geom as frame
    import channel_kinematics as ck
    import dt_cylinder_gear_spec as gear

    ox, oy = frame.ROCKER_PIVOT_XY
    arm, c2c = ck._ARM_ROD_LEVER, rod.CENTER_DISTANCE
    tilts = []
    for k in range(0, 360, 2):
        phase = math.radians(k)
        cx = frame.CAM_SHAFT_XY[0] + gear.ECCENTRICITY * math.sin(phase)
        cy = frame.CAM_SHAFT_XY[1] + gear.ECCENTRICITY * math.cos(phase)
        dx, dy = cx - ox, cy - oy
        d = math.hypot(dx, dy)
        a = (arm**2 - c2c**2 + d * d) / (2.0 * d)
        h = math.sqrt(arm**2 - a * a)
        px, py = ox + a * dx / d + h * dy / d, oy + a * dy / d - h * dx / d
        tilts.append(math.degrees(math.atan2(py - oy, ox - px)) - ck._ARM_LEVER_BETA_DEG)
    acx0, acy0 = ck.ARC["acx"], ck.ARC["acy"]
    worst = 0.0
    try:
        for delta in {min(tilts), max(tilts), -min(tilts), -max(tilts), 0.0}:
            t = math.radians(delta)
            rx, ry = acx0 - ox, acy0 - oy
            ck.ARC["acx"] = ox + rx * math.cos(t) - ry * math.sin(t)
            ck.ARC["acy"] = oy + rx * math.sin(t) + ry * math.cos(t)
            for station in range(0, 81, 10):
                state = ck.solve_state(float(station))
                worst = max(worst, abs(state["lever_tilt"] - state["bar_tilt"]))
    finally:
        ck.ARC["acx"], ck.ARC["acy"] = acx0, acy0
    return worst


def test_restated_lever_bar_swing_brackets_the_solved_loop() -> None:
    worst = _lever_bar_swing_deg()
    assert worst <= pin.LEVER_BAR_SWING_DEG <= worst + 0.05


def test_the_assembly_press_allowance_is_this_joint() -> None:
    """_interference_contracts restates the modelled press as literals (every
    assembly imports it); they must be the nominal pin, the reamed hole and
    the two cheeks, and name channel j's pin with channel j's bar only."""
    import _interference_contracts as ic

    pin_dia, hole_dia, engaged = ic.BAR_PIVOT_PIN_PRESS
    assert pin_dia == pytest.approx(pin.PIN_DIA, abs=1e-9)
    assert hole_dia == bar.TOP_PIN_HOLE_DIA
    assert engaged == pytest.approx(bar.BAR_WIDTH - bar.TOP_NOTCH_WIDTH, abs=1e-9)
    # The rod pins' press pairs share the table (test_ch_rod_pivot_fit holds
    # the union to exactly the two pin joints).
    pairs = {
        pair: limit
        for pair, limit in ic.allowed_interference_pairs("ch-channel").items()
        if any(name.startswith("ch-bar-pivot-pin-") for name in pair)
    }
    assert set(pairs) == {
        frozenset((f"ch-bar-pivot-pin-{n}", f"ch-amplitude-bar-{n}"))
        for n in range(1, 21)
    }
    nominal = math.pi / 4.0 * (pin_dia**2 - hole_dia**2) * engaged
    assert all(limit == pytest.approx(1.10 * nominal) for limit in pairs.values())
