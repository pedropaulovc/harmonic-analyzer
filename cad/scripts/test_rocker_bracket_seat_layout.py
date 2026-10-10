"""Offline contracts for the rocker brackets' hold-down seats (#743 PR2)."""

from __future__ import annotations

import pytest

import _config
import _interference_contracts
import build_ch_channel_assembly as channel
import build_vn_pedestal_hold_down_screw as hold_down_build
import vn_pedestal_hold_down_screw_spec as hold_down
import dt_arbor_pedestal_spec as pedestal
import build_fr_rocker_arm_support as support
import ch_pivot_bracket_sides as sides
import ch_pivot_bracket_spec as bracket
import fr_rocker_arm_support_spec as support_spec
import rocker_bracket_seat_layout as seats


def test_layout_screw_is_the_placed_mha_143() -> None:
    assert hold_down_build.SPEC.skus == ("90280A197",)
    assert seats.SCREW_THREAD == hold_down.THREAD
    assert seats.SCREW_LENGTH == hold_down.SHANK_LEN
    assert seats.SCREW_MAJOR_DIA == pytest.approx(hold_down.SHANK_DIA, abs=1e-3)
    assert seats.SCREW_TIP_CHAMFER == pytest.approx(0.7 * hold_down._PITCH)


def test_channel_places_one_screw_per_seat() -> None:
    assert channel.BRACKET_SCREW_XZ == seats.SEAT_MACHINE_XZ
    assert len(seats.SEAT_MACHINE_XZ) == len(sides.CONFIGURATIONS) == 2
    assert [z for _x, z in seats.SEAT_MACHINE_XZ] == [
        sides.HOLE_MACHINE_Z[name] for name in sides.CONFIGURATIONS
    ]


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
    assert seats.SEAT_DRILL_NAME == "#29"
    # The print carries each depth row at .X.
    for value in (seats.SEAT_DRILL_DEPTH, seats.SEAT_THREAD_DEPTH):
        assert round(value, 1) == value


def test_seat_thread_keeps_the_web_wall_at_the_printed_worst_case() -> None:
    """Each seat runs down the web column, so the web's thickness bounds it:
    the thread's major diameter to either web face, the web at the low end of
    its printed .XX band."""
    assert support.WEB is seats.WEB
    assert 2.0 * seats.WEB == pytest.approx(9.525)  # 3/8 in
    assert seats.WEB_PLACES == 2
    wall = (2.0 * seats.WEB - seats.LINEAR_2PL) / 2.0 - seats.SCREW_MAJOR_DIA / 2.0
    assert wall == pytest.approx(seats.WEB_WALL_MIN)
    assert wall >= seats.RULE12_WEB_TARGET


def test_seats_run_in_solid_iron_on_the_support() -> None:
    """Each seat sits over the window's side edge, clear of the through cavity
    (so the web column runs on under its drill point) and on the support's top
    face short of its end-face edge break."""
    radius = seats.SEAT_DRILL_DIA / 2.0
    for x in seats.SEAT_LOCAL_X:
        assert abs(x) - radius > support.CAV
        assert abs(x) - radius < support.BIG < abs(x) + radius
        assert abs(x) + radius <= support.HALF_Y - seats.EDGE_BREAK
    assert [round(abs(x), 2) for x in seats.SEAT_LOCAL_X] == [84.08, 83.23]


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


def test_bracket_hole_ligaments_keep_their_floors_at_worst_case() -> None:
    for name in sides.CONFIGURATIONS:
        for where, ligament in sides.HOLE_LIGAMENTS_MIN[name].items():
            assert ligament >= sides.LIGAMENT_FLOOR[name, where]
    # The one named exception: the south foot's end, 1.4 (user, 2026-10-09).
    lowered = {
        key
        for key, floor in sides.LIGAMENT_FLOOR.items()
        if floor < bracket.LIGAMENT_FLOOR
    }
    assert lowered == {("S", "foot end")}
    assert sides.LIGAMENT_FLOOR["S", "foot end"] == 1.4
    # Each term at its own printed band: the foot's edges at the .XX band the
    # seat stack carries this foot at, the station at .XX, the drilled hole
    # at the title block's +0.10/0.
    assert bracket.EDGE_BAND == seats.LINEAR_2PL
    assert bracket.STATION_BAND == seats.LINEAR_2PL
    drilled = _config.title_block("drilled_hole")
    assert (drilled["minus_mm"], drilled["plus_mm"]) == (0.0, bracket.DRILL_GROWTH)


def test_each_foot_ends_flush_with_the_support_and_centres_its_hole() -> None:
    for name in sides.CONFIGURATIONS:
        foot_end = sides.MOUNT_Z[name] + sides.OUTBOARD_SIGN[name] * sides.FOOT_Z1[name]
        support_end = support_spec.SUPPORT_WORLD_Z + sides.OUTBOARD_SIGN[name] * (
            support_spec.SUPPORT_HALF_MACHINE_Z
        )
        assert foot_end == pytest.approx(support_end)
        assert sides.HOLE_Z[name] - bracket.EAR_T / 2.0 == pytest.approx(
            sides.FOOT_Z1[name] - sides.HOLE_Z[name]
        )
    assert sides.OUTBOARD_SIGN == {"S": -1.0, "N": 1.0}
    assert {name: round(value, 2) for name, value in sides.FOOT_LEN.items()} == {
        "S": 15.64,
        "N": 17.34,
    }


def test_screw_heads_keep_air_to_the_ear_and_the_foot_end() -> None:
    head_r = hold_down.HEAD_DIA / 2.0
    for name in sides.CONFIGURATIONS:
        assert sides.HEAD_TO_EAR_FACE_MIN[name] > 0.0
        assert sides.HEAD_TO_EAR_FACE_MIN[name] == pytest.approx(
            sides.HOLE_Z[name]
            - head_r
            - bracket.EAR_T / 2.0
            - bracket.EDGE_BAND
            - bracket.STATION_BAND
        )
        assert sides.HOLE_Z[name] + head_r < sides.FOOT_Z1[name]
