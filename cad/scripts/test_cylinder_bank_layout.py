"""Offline contracts for the cylinder-bank retention stack (issue #743)."""

from __future__ import annotations

from pathlib import Path

import pytest

import dt_arbor_pedestal_spec

import _config
import ch_connecting_rod_spec as rod
import cylinder_bank_layout as bank
import dt_cylinder_gear_spec as gear
from _buildgraph import module_deps_of

MM_PER_IN = 25.4


def test_gear_overall_thickness_is_the_station_pitch() -> None:
    # Free 6.5 mm gears on a 7.06 mm pitch left 0.56 mm of air per station:
    # nothing but the CAD ladder held the stations apart.
    assert gear.OVERALL_THICKNESS == pytest.approx(
        _config.machine("channels", "station_pitch_mm"), abs=1e-9
    )
    assert gear.CAM_THICKNESS == pytest.approx(gear.OVERALL_THICKNESS - gear.FACE_WIDTH)
    assert 0.0 <= bank.BANK_PITCH - gear.OVERALL_THICKNESS <= 0.001


def test_gear_and_stack_bands_are_centred() -> None:
    # User ruling L20 d' (#743) retired the one-sided +0.05/0: the same 0.05
    # wide band, centred, stacks 20 gears about nominal, and the acceptance
    # holds a long stack (re-face) and a short one (remake a gear) alike.
    upper, lower = gear.OVERALL_THICKNESS_BAND
    assert upper - lower == pytest.approx(0.05)
    assert upper == pytest.approx(-lower)
    # #948 ruling R tightened the acceptance to +/-0.10 (a fit-up re-face).
    assert bank.STACK_L20_ACCEPT == pytest.approx(
        (bank.STACK_L20 - 0.10, bank.STACK_L20 + 0.10)
    )


def _extreme_stacks(per_gear: float, accept: float):
    """Every accepted stack with each gear at a band limit, up to order."""
    for long_gears in range(bank.COUNT + 1):
        stack = [per_gear] * long_gears + [-per_gear] * (bank.COUNT - long_gears)
        if abs(sum(stack)) <= accept + 1e-12:
            yield stack


@pytest.mark.parametrize("n", range(bank.COUNT + 1))
def test_partial_stack_band_is_the_worst_accepted_split(n: int) -> None:
    # Any n gears of an accepted stack: the bound is reached by an accepted
    # stack whose n gears all lean one way, and no accepted stack exceeds it.
    per_gear = gear.OVERALL_THICKNESS_BAND[0]
    accept = bank.STACK_L20_ACCEPT_BAND[0]
    upper, lower = bank.partial_stack_band(n)
    sums = []
    for stack in _extreme_stacks(per_gear, accept):
        ordered = sorted(stack, reverse=True)
        sums += [sum(ordered[:n]), sum(sorted(stack)[:n])]
    assert max(sums) == pytest.approx(upper)
    assert min(sums) == pytest.approx(lower)


def test_the_bank_is_preloaded_by_its_spring() -> None:
    # #948 ruling R: the 0.45 leaf became a 9714K392 wave spring set on a
    # 0.95 blade; its whole set band stays in the spring's working range at a
    # light, single-digit-newton preload, and the bank has no end play.
    assert bank.BANK_SPRING_SET == pytest.approx(0.95)
    assert bank.BANK_SPRING_HEIGHT == pytest.approx((0.85, 1.05))
    assert bank.BANK_PRELOAD == pytest.approx((2.22, 4.24), abs=0.01)
    assert bank.BANK_SPRING_Z == (bank.FRONT_STRAP_INNER_Z, bank.FRONT_WASHER_Z[0])
    assert not hasattr(bank, "BANK_END_PLAY")
    assert not hasattr(bank, "RING_OVERHANG_MAX")
    # The spring takes up the brass stack's thermal growth inside its set band.
    assert bank.THERMAL_STACK_DRIFT < bank.BANK_SPRING_SET_BAND


def test_the_bank_spring_fits_its_arbor_and_faces() -> None:
    import dt_arbor_pedestal_spec as ped
    import dt_cylinder_end_disc_spec as washer
    import dt_cylinder_gear_shaft_spec as arbor
    import vn_cylinder_bank_spring_spec as spring

    # Catalogue worst case: the tightest spring still passes the largest arbor
    # (with no clearance to spare: the DT-000 step checks it slides free).
    id_min = spring.ID + spring.ID_BAND[1]
    assert id_min >= arbor.SHAFT_DIA + arbor.SHAFT_DIA_BAND[0] - 1e-9
    # Its whole width lands on the washer's face and on the strap's.
    od_min = spring.OD + spring.OD_BAND[1]
    od_max = spring.OD + spring.OD_BAND[0]
    assert od_min > washer.WASHER_BORE + washer.WASHER_BORE_BAND[0]
    assert od_min > ped.BORE_DIA + ped.BORE_DIA_BAND[0]
    assert od_max < washer.WASHER_OD


def test_g0_to_g19_band_is_capped_by_the_stack_acceptance() -> None:
    assert bank.G0_FRONT_FROM_G19_BACK == pytest.approx(
        -(19 * bank.BANK_PITCH + gear.FACE_WIDTH)
    )
    # Gears 1-19 against L20 +/-0.10: 19 x 0.025 is capped at 0.10 + 0.025.
    assert bank.G0_G19_BAND == pytest.approx((-0.175, 0.175))
    # Preloaded: no end-play term south.
    assert sum(bank.G0_FRONT_SOUTH_STACK.values()) == pytest.approx(0.175)
    assert sum(bank.G0_FRONT_NORTH_STACK.values()) == pytest.approx(0.175)


def test_the_worst_station_is_gear_7_not_gear_0() -> None:
    # 12 gears north of gear 7 may all lean one way (0.30) while the other 8
    # lean back (0.20), and the stack still passes L20 +/-0.10.
    assert bank.partial_stack_band(12) == pytest.approx((0.30, -0.30))
    assert bank.STATION_STACK_BAND == pytest.approx((-0.325, 0.325))


def test_the_datum_chain_is_mic_compensated() -> None:
    # #948 ruling R: the back strap's DRO target is offset by the measured
    # back washer's (W - 1.500), so only the micrometer's residual stays.
    assert bank.DATUM_CHAIN_STACK == pytest.approx(
        {"back strap DRO locate": 0.10, "back washer, mic-compensated": 0.013}
    )


def test_a_closed_slot_always_holds_the_whole_ring() -> None:
    # #948 ruling R: ring and shank 2.200 at three places, the title block's
    # 3-place class.
    three_place = _config.title_block("linear_3pl")["value_in"] * MM_PER_IN
    assert rod.RING_THICKNESS_BAND == pytest.approx((three_place, -three_place))
    ring_max = rod.RING_THICKNESS + three_place
    assert bank.RING_MAX == pytest.approx(ring_max)
    assert bank.SHANK_MAX == pytest.approx(ring_max)
    # d': the thinnest in-band gear, 7.0565 - 0.025, less FW + 0.05.
    assert bank.SLOT_MIN == pytest.approx(3.9815)
    assert bank.RING_SLOT_MARGIN == pytest.approx(bank.SLOT_MIN - ring_max)
    assert bank.RING_SLOT_MARGIN >= bank.MARGIN_SPARE


def test_each_gear_is_accepted_on_its_print_band() -> None:
    upper, lower = gear.OVERALL_THICKNESS_BAND
    assert bank.GEAR_THICKNESS_ACCEPT == pytest.approx(
        (gear.OVERALL_THICKNESS + lower, gear.OVERALL_THICKNESS + upper)
    )
    # Four places print the band exactly; three would move a limit inward.
    places = gear.DRAWING_PRECISION_BY_NAME["OverallThickness"]
    for limit in bank.GEAR_THICKNESS_ACCEPT:
        assert round(limit, places) == pytest.approx(limit, abs=1e-12)


def test_ring_faces_stay_on_flat_web_through_the_whole_stroke() -> None:
    ring_reach = rod.RING_OUTER_RADIUS + gear.ECCENTRICITY
    root_radius = gear.TIP_RADIUS - gear.WHOLE_DEPTH
    assert root_radius - ring_reach >= 0.5


def test_stations_close_up_against_the_datum() -> None:
    assert bank.BACK_STRAP_INNER_Z - bank.G19_BACK_FACE_Z == pytest.approx(1.5)
    assert bank.G0_CAM_FACE_Z == pytest.approx(
        bank.station_z(0) - gear.FACE_WIDTH / 2.0 - gear.CAM_THICKNESS
    )
    assert bank.FRONT_WASHER_Z[0] - bank.FRONT_STRAP_INNER_Z == pytest.approx(
        bank.BANK_SPRING_SET
    )
    assert bank.CAM_MID_DZ == pytest.approx(-gear.OVERALL_THICKNESS / 2.0)


def test_layout_stays_geometry_only() -> None:
    deps = {Path(p).name for p in module_deps_of(Path(bank.__file__))}
    assert deps.isdisjoint(
        {"dt_cylinder_gear_notes.py", "build_dt_cylinder_gear.py", "draw_dt_cylinder_gear.py"}
    )
    source = Path(bank.__file__).read_text(encoding="utf-8")
    assert "title_block" not in source.split('"""', 2)[2]


def test_arbor_spans_both_straps_and_domes_proud_of_each() -> None:
    """#743 supersedes U34b's "span less 6.0": the arbor fills both strap
    bores, where the apex set screws bear on it, and each end is domed
    ARBOR_DOME_HEIGHT proud of its strap's outer face."""
    import dt_arbor_pedestal_spec as ped

    assert bank.STRAP_OUTER_SPAN == pytest.approx(bank.STRAP_INNER_SPAN + 2 * ped.STRAP_T)
    assert bank.ARBOR_LENGTH == pytest.approx(bank.STRAP_OUTER_SPAN)
    assert bank.ARBOR_SOUTH_Z == pytest.approx(bank.FRONT_STRAP_INNER_Z - ped.STRAP_T)
    assert bank.ARBOR_SOUTH_Z + bank.ARBOR_LENGTH == pytest.approx(
        bank.BACK_STRAP_INNER_Z + ped.STRAP_T
    )
    assert bank.ARBOR_OVERALL_LENGTH == pytest.approx(
        bank.ARBOR_LENGTH + 2 * bank.ARBOR_DOME_HEIGHT
    )
    # A true dome over the whole end (SR about 8.3 on the 3/8 rod), never
    # more than a hemisphere.
    import dt_cylinder_gear_shaft_spec as arbor

    assert 0.0 < bank.ARBOR_DOME_HEIGHT <= arbor.SHAFT_DIA / 2.0


def test_pedestals_anchor_on_the_bank_strap_faces() -> None:
    """The drive train stands each MHA-DT-002 on its strap inner face (U34 row 5),
    and the #743 stack is what fixes those faces."""
    import dt_arbor_pedestal_spec as ped

    assert bank.FRONT_PEDESTAL_ORIGIN_Z == pytest.approx(
        bank.FRONT_STRAP_INNER_Z - ped.STRAP_INNER_Z
    )
    assert bank.BACK_PEDESTAL_ORIGIN_Z == pytest.approx(
        bank.BACK_STRAP_INNER_Z + ped.STRAP_INNER_Z
    )
    assert bank.FRONT_STRAP_INNER_Z == pytest.approx(-72.019, abs=5e-4)
    assert bank.BACK_STRAP_INNER_Z == pytest.approx(73.062, abs=5e-4)
    # The apex set screws sit at each strap's mid-depth.
    assert bank.FRONT_SET_SCREW_Z == pytest.approx(
        bank.FRONT_PEDESTAL_ORIGIN_Z + ped.SET_SCREW_Z
    )
    assert bank.BACK_SET_SCREW_Z == pytest.approx(
        bank.BACK_PEDESTAL_ORIGIN_Z - ped.SET_SCREW_Z
    )


def test_apex_set_screw_socket_and_cup_point_are_named() -> None:
    """Main rider 1 on #743 PR1: the socket's height over the crown apex is a
    named layout constant (the drive train places it exactly), and the cup
    point, not the thread, spans the running clearance with the arbor pushed
    to the bottom of a largest bore on a smallest arbor."""
    import vn_arbor_set_screw_spec as screw
    import dt_cylinder_gear_shaft_spec as shaft

    assert bank.SET_SCREW_SOCKET_PROUD == pytest.approx(
        screw.LENGTH + shaft.SHAFT_DIA / 2.0 - dt_arbor_pedestal_spec.TOP_RADIUS
    )
    assert 0.0 < bank.SET_SCREW_SOCKET_PROUD < 0.25
    bore_max_r = (
        dt_arbor_pedestal_spec.BORE_DIA + dt_arbor_pedestal_spec.BORE_DIA_BAND[0]
    ) / 2.0
    shaft_min_r = (shaft.SHAFT_DIA + shaft.SHAFT_DIA_BAND[1]) / 2.0
    lowest_tip_r = 2.0 * shaft_min_r - bore_max_r
    assert bank.SET_SCREW_POINT_MARGIN == pytest.approx(
        lowest_tip_r + screw.POINT_LENGTH - bore_max_r
    )
    assert bank.SET_SCREW_POINT_MARGIN >= bank.SET_SCREW_POINT_MARGIN_MIN == 0.25
