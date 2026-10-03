"""Offline contracts for the rocker brackets' hold-down seats (#743 PR2)."""

from __future__ import annotations

import pytest

import _config
import _interference_contracts
import build_ch_channel_assembly as channel
import build_vn_pedestal_hold_down_screw as hold_down_build
import vn_pedestal_hold_down_screw_spec as hold_down
import dt_arbor_pedestal_spec as pedestal
import ch_pivot_bracket_spec as bracket
import rocker_bracket_seat_layout as seats
from _hole_spec import DRILL_POINT_H


def test_layout_screw_is_the_placed_mha_143() -> None:
    assert hold_down_build.SPEC.skus == ("90280A197",)
    assert seats.SCREW_THREAD == hold_down.THREAD
    assert seats.SCREW_LENGTH == hold_down.SHANK_LEN
    assert seats.SCREW_MAJOR_DIA == pytest.approx(hold_down.SHANK_DIA, abs=1e-3)
    assert seats.SCREW_TIP_CHAMFER == pytest.approx(0.7 * hold_down._PITCH)


def test_channel_places_one_screw_per_seat() -> None:
    assert channel.BRACKET_SCREW_XZ == seats.SEAT_MACHINE_XZ
    assert len(seats.SEAT_MACHINE_XZ) == 2 * len(bracket.HOLE_Z) == 4


def test_top_level_contract_literals_match_the_layout() -> None:
    pairs = _interference_contracts.allowed_interference_pairs("ha-harmonic-analyzer")
    limits = {
        limit
        for pair, limit in pairs.items()
        if "fr-frame-1/fr-rocker-arm-support-1" in pair
        and any(name.startswith("ch-channel-1/vn-pedestal-hold-down-screw-") for name in pair)
    }
    screws = {
        name
        for pair in pairs
        if "fr-frame-1/fr-rocker-arm-support-1" in pair
        for name in pair
        if name.startswith("ch-channel-1/vn-pedestal-hold-down-screw-")
    }
    assert screws == {
        f"ch-channel-1/vn-pedestal-hold-down-screw-{n}"
        for n in range(1, len(seats.SEAT_MACHINE_XZ) + 1)
    }
    (limit,) = limits
    assert limit == pytest.approx(
        _interference_contracts._smooth_annulus_limit_mm3(
            hold_down.SHANK_DIA,
            seats.SEAT_DRILL_DIA,
            seats.SCREW_LENGTH - bracket.FOOT_H,
        )
    )


def test_seat_stack_margins() -> None:
    # The printed worst case, restated: every margin the layout asserts.
    assert seats.ENGAGEMENT_MIN == pytest.approx(10.976, abs=1e-3)
    assert seats.SEAT_THREAD_DEPTH - seats.LINEAR_1PL - seats.SCREW_REACH_MAX == (
        pytest.approx(0.342, abs=1e-3)
    )
    assert seats.RAIL_DEPTH - seats.LINEAR_1PL - seats.SEAT_DRILL_BOTTOM_MAX == (
        pytest.approx(2.062, abs=1e-3)
    )
    assert seats.SEAT_DRILL_NAME == "#29"


def test_seat_drill_point_keeps_the_rail_floor_at_the_printed_worst_case() -> None:
    """Codex #936 PRRT_kwDOPHDy386mS91G: the rail at its .X low limit over
    the #29 drill at its .X high limit plus its 118-deg point. The old check
    only kept the point out of the window; the floor it left was 0.36."""
    rail_min = seats.RAIL_DEPTH - seats.LINEAR_1PL
    drill_shoulder_max = seats.SEAT_DRILL_DEPTH + seats.LINEAR_1PL
    point = seats.SEAT_DRILL_DIA / 2.0 * DRILL_POINT_H
    floor = rail_min - (drill_shoulder_max + point)
    assert floor == pytest.approx(seats.SEAT_FLOOR_MIN)
    assert floor >= seats.RULE12_WEB_TARGET
    # The print carries each row at its own precision.
    for value in (seats.RAIL_DEPTH, seats.SEAT_DRILL_DEPTH, seats.SEAT_THREAD_DEPTH):
        assert round(value, 1) == value


def test_bracket_hole_clears_the_screw_junction_fillet() -> None:
    """r743-3C: MHA-CH-008's #19 hole (0.025 radial over the #8-32 major) cut the
    fillister's under-head junction fillet, P/10 in diag_mcmaster_fillister's
    recipe, at the hole mouth: 0.0048 mm^3 per screw in assembly:ch_channel."""
    fillet = hold_down._PITCH / 10.0
    radial = (bracket.HOLE_DIA - seats.SCREW_MAJOR_DIA) / 2.0
    assert radial > fillet
    assert channel.BRACKET_HOLE_FILLET_CLEARANCE == pytest.approx(radial - fillet)
    assert bracket.HOLE_DIA < hold_down.HEAD_DIA


def test_bracket_hole_is_mha_004s_hole_for_the_same_screw() -> None:
    """Both carry the MHA-VN-032 hold-down; their holes must not drift apart."""
    assert bracket.HOLD_DOWN_HOLE_SPEC == pedestal.SCREW_HOLE_SPEC


def test_bracket_hole_ligaments_keep_the_floor_at_worst_case() -> None:
    assert min(bracket.HOLE_LIGAMENTS_MIN.values()) >= bracket.LIGAMENT_FLOOR
    # Centred on the free run: neither foot end is the weak one.
    assert bracket.HOLE_LIGAMENTS_MIN["ear face"] == pytest.approx(
        bracket.HOLE_LIGAMENTS_MIN["foot end"]
    )
    edge_loss = bracket.EDGE_BAND + bracket.STATION_BAND + bracket.DRILL_GROWTH / 2.0
    assert bracket.HOLE_LIGAMENTS_MIN["ear face"] + edge_loss >= bracket.LIGAMENT_TARGET
    # Each term at its own printed band: the foot's edges at the .XX band the
    # seat stack carries this foot at, the stations at .X, the drilled hole
    # at the title block's +0.10/0.
    assert bracket.EDGE_BAND == seats.LINEAR_2PL
    assert bracket.STATION_BAND == seats.LINEAR_1PL
    drilled = _config.title_block("drilled_hole")
    assert (drilled["minus_mm"], drilled["plus_mm"]) == (0.0, bracket.DRILL_GROWTH)
    # The stations print at .X.
    assert all(round(z, 1) == z for z in bracket.HOLE_Z)
    assert bracket.HOLE_Z == (8.2, 16.0)
    assert bracket.FOOT_LEN == pytest.approx(24.2)


def test_the_24_foot_failed_the_floor_at_the_printed_station_band() -> None:
    """Fail-first, Codex #936 PRRT_kwDOPHDy386mV3AN: booking the .X stations
    at the .XX band hid it -- on the 24.0 foot, (8.1, 15.9) left 1.456 to
    each end at the printed bands. The foot grew; the print did not tighten."""
    old = bracket.hole_ligaments_min((8.1, 15.9), (bracket.FREE_RUN[0], 21.0))
    assert old["foot end"] == pytest.approx(1.456)
    assert old["ear face"] < bracket.LIGAMENT_FLOOR


def test_old_stations_fail_the_ligament_floor_with_the_close_hole() -> None:
    """Fail-first: the #19 stations (9, 17) with the 4.572 hole leave 0.44
    to the foot end at worst case."""
    old = bracket.hole_ligaments_min((9.0, 17.0))
    assert old["foot end"] < bracket.LIGAMENT_FLOOR


def test_derived_stations_are_the_best_print_step_rounding() -> None:
    """No .X station pair centred on the run keeps a larger least ligament."""
    mid = sum(bracket.FREE_RUN) / 2.0
    best = min(bracket.HOLE_LIGAMENTS_MIN.values())
    for tenths in range(20, 90):
        half = tenths / 10.0
        candidate = bracket.hole_ligaments_min((mid - half, mid + half))
        assert min(candidate.values()) <= best + 1e-9


def test_screw_heads_keep_air_to_the_ear_and_the_foot_end() -> None:
    head_r = hold_down.HEAD_DIA / 2.0
    assert min(bracket.HOLE_Z) - head_r > bracket.FREE_RUN[0]
    assert max(bracket.HOLE_Z) + head_r < bracket.FREE_RUN[1]
