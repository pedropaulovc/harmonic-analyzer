"""Offline contracts for the cylinder-bank retention stack (issue #743)."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import connecting_rod_spec as rod
import cylinder_bank_layout as bank
import cylinder_gear_spec as gear
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


def test_a_stack_can_only_come_out_long() -> None:
    upper, lower = gear.OVERALL_THICKNESS_BAND
    assert lower == 0.0 < upper
    assert bank.STACK_L20_ACCEPT[0] == pytest.approx(bank.COUNT * gear.OVERALL_THICKNESS)


def test_end_play_uses_the_rig_feeler_rule() -> None:
    assert bank.BANK_END_FEELER == pytest.approx(0.45)
    assert bank.BANK_END_PLAY == pytest.approx((0.35, 0.55))
    # The tightest setting keeps the floor plus the novice spare ...
    assert bank.BANK_END_PLAY[0] >= bank.MIN_END_PLAY + bank.MARGIN_SPARE - 1e-9
    # ... and one blade thinner would not.
    thinner = bank.BANK_END_FEELER - bank.FEELER_STEP - bank.BANK_END_FEELER_BAND
    assert thinner < bank.MIN_END_PLAY + bank.MARGIN_SPARE
    assert bank.THERMAL_END_PLAY_DRIFT < bank.MARGIN_SPARE


def test_g0_to_g19_band_is_capped_by_the_stack_acceptance() -> None:
    assert bank.G0_FRONT_FROM_G19_BACK == pytest.approx(
        -(19 * bank.BANK_PITCH + gear.FACE_WIDTH)
    )
    assert bank.G0_G19_BAND == pytest.approx((-0.25, 0.10))
    assert sum(bank.G0_FRONT_SOUTH_STACK.values()) == pytest.approx(0.80)
    assert sum(bank.G0_FRONT_NORTH_STACK.values()) == pytest.approx(0.10)
    assert bank.STATION_STACK_BAND == pytest.approx((-0.225, 0.025))


def test_g19_never_moves_north_of_the_datum() -> None:
    assert sum(bank.G19_BACK_NORTH_STACK.values()) == 0.0
    assert sum(bank.G19_BACK_SOUTH_STACK.values()) == pytest.approx(bank.BANK_END_PLAY[1])


def test_a_closed_slot_always_holds_the_whole_ring() -> None:
    # The rod print does not dimension the ring thickness; judge it at the
    # loosest routine class a shop would read into it.
    ring_max = rod.RING_THICKNESS + _config.title_block("linear_2pl")["value_in"] * MM_PER_IN
    assert bank.SLOT_MIN - ring_max >= 0.25
    assert bank.RING_OVERHANG_MAX == bank.BANK_END_PLAY[1]


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
        bank.BANK_END_FEELER
    )
    assert bank.CAM_MID_DZ == pytest.approx(-gear.OVERALL_THICKNESS / 2.0)


def test_layout_stays_geometry_only() -> None:
    deps = {Path(p).name for p in module_deps_of(Path(bank.__file__))}
    assert deps.isdisjoint(
        {"cylinder_gear_notes.py", "build_cylinder_gear.py", "draw_cylinder_gear.py"}
    )
    source = Path(bank.__file__).read_text(encoding="utf-8")
    assert "title_block" not in source.split('"""', 2)[2]


def test_arbor_spans_both_straps_and_domes_proud_of_each() -> None:
    """#743 supersedes U34b's "span less 6.0": the arbor fills both strap
    bores, where the apex set screws bear on it, and each end is domed
    ARBOR_DOME_HEIGHT proud of its strap's outer face."""
    import arbor_pedestal_spec as ped

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
    import cylinder_gear_shaft_spec as arbor

    assert 0.0 < bank.ARBOR_DOME_HEIGHT <= arbor.SHAFT_DIA / 2.0


def test_pedestals_anchor_on_the_bank_strap_faces() -> None:
    """The drive train stands each MHA-004 on its strap inner face (U34 row 5),
    and the #743 stack is what fixes those faces."""
    import arbor_pedestal_spec as ped

    assert bank.FRONT_PEDESTAL_ORIGIN_Z == pytest.approx(
        bank.FRONT_STRAP_INNER_Z - ped.STRAP_INNER_Z
    )
    assert bank.BACK_PEDESTAL_ORIGIN_Z == pytest.approx(
        bank.BACK_STRAP_INNER_Z + ped.STRAP_INNER_Z
    )
    assert bank.FRONT_STRAP_INNER_Z == pytest.approx(-71.519, abs=5e-4)
    assert bank.BACK_STRAP_INNER_Z == pytest.approx(73.062, abs=5e-4)
    # The apex set screws sit at each strap's mid-depth.
    assert bank.FRONT_SET_SCREW_Z == pytest.approx(
        bank.FRONT_PEDESTAL_ORIGIN_Z + ped.SET_SCREW_Z
    )
    assert bank.BACK_SET_SCREW_Z == pytest.approx(
        bank.BACK_PEDESTAL_ORIGIN_Z - ped.SET_SCREW_Z
    )
