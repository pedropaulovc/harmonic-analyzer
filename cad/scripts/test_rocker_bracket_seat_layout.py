"""Offline contracts for the rocker brackets' hold-down seats (#743 PR2)."""

from __future__ import annotations

import pytest

import _config
import _interference_contracts
import build_ch_channel_assembly as channel
import build_ch_pivot_bracket as bracket_build
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
    assert len(seats.SEAT_MACHINE_XZ) == len(sides.SIDES) == 2
    assert [z for _x, z in seats.SEAT_MACHINE_XZ] == [
        sides.HOLE_MACHINE_Z[name] for name in sides.SIDES
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
    assert [round(abs(x), 2) for x in seats.SEAT_LOCAL_X] == [84.2, 82.59]


def test_seat_thread_keeps_the_end_wall_at_the_worst_transferred_position() -> None:
    """Codex P2 (2026-10-09 flip): the south seat's thread sat 2.74 from the
    support's end face nominal and 1.32 at the title-block bands. It is
    transferred from the bracket's hole, whose station is given from the
    fit-up-set ear face (user, 2026-10-10, option ii), so only the station's
    band moves it -- not the foot length's -- and the end face moves by half
    the 177.8's .X band."""
    for x, wall in zip(seats.SEAT_LOCAL_X, seats.END_WALL_MIN, strict=True):
        assert wall == pytest.approx(
            (support.HALF_Y - abs(x))
            - seats.SCREW_MAJOR_DIA / 2.0
            - bracket.STATION_BAND
            - seats.LINEAR_1PL / 2.0
        )
        assert wall >= seats.RULE12_WEB_TARGET


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
    ligaments = sides.HOLE_LIGAMENTS_MIN
    for ligament in ligaments.values():
        assert ligament >= bracket.LIGAMENT_FLOOR
    # The foot end loses the foot length's and the station's bands (both
    # from the inboard ear face) and half the drill growth.
    assert ligaments["foot end"] == pytest.approx(
        sides.FOOT_Z1
        - sides.HOLE_Z
        - bracket.HOLE_DIA / 2.0
        - bracket.FOOT_LEN_BAND
        - bracket.STATION_BAND
        - bracket.DRILL_GROWTH / 2.0
    )
    # Each term at its own band: along the foot the three +/-0.10 lengths,
    # across it the foot's sides at the .XX band the seat stack carries this
    # foot at, the drilled hole at the title block's +0.10/0.
    assert bracket.EDGE_BAND == bracket.HOLE_X_BAND == seats.LINEAR_2PL
    drilled = _config.title_block("drilled_hole")
    assert (drilled["minus_mm"], drilled["plus_mm"]) == (0.0, bracket.DRILL_GROWTH)


def test_bracket_lengths_along_the_foot_carry_their_bands_on_the_model() -> None:
    """The S4 fixture plan and the MHA-CH-008 sheet take the +/-0.10 lengths
    from the saved model's dimensions; the tap station and the reamed bore
    carry the drawing contract's bands beside them."""
    from _drawing_contract import model_toleranced_dimensions

    assert (bracket.FOOT_LEN_BAND, bracket.EAR_T_BAND, bracket.STATION_BAND) == (
        0.10,
        0.10,
        0.10,
    )
    assert model_toleranced_dimensions(bracket_build) == {
        ("FootProfile", "FootLen"): "FOOT_LEN_BAND",
        ("Ear", "EarThick"): "EAR_T_BAND",
        ("HoleProfile", "HoleStation"): "STATION_BAND",
        ("SetScrewReference", "SetScrewLocation"): "SET_SCREW_STATION_BAND",
        ("ShaftBoreProfile", "ShaftBoreDia"): "*deviations(BORE_DIA_BAND)",
    }


def test_hold_down_station_is_given_from_the_ears_inboard_face() -> None:
    """User, 2026-10-10 (option ii): the station runs from the face fit-up
    sets, the S4 hold's Z0, so the model's HoleStation measures from it."""
    assert sides.HOLE_STATION == pytest.approx(sides.HOLE_Z - bracket.FOOT_Z0)
    assert sides.HOLE_STATION == pytest.approx(sides.HOLE_Z + bracket.EAR_T / 2.0)
    source = open(bracket_build.__file__, encoding="utf-8").read()
    assert 'hole.record("HoleDatum", \'"EarT" / 2\')' in source
    assert 'hole.record("HoleStation", \'"HoleZ" + "EarT" / 2\')' in source


def test_one_foot_fits_both_ends_of_the_support_and_places_its_hole() -> None:
    """#1341 option A: one bracket on both sides. Its foot ends flush with
    the nearer (south) support end face and 1.61 short of the north one; the
    free run is too short (8-thick ears beside the 1/32 thrust washers) to
    centre the hole, so it sits mid-way between the head-to-ear and seat
    end-wall limits, a window both sides share."""
    assert sides.OUTBOARD_SIGN == {"S": -1.0, "N": 1.0}
    support_end = {
        name: support_spec.SUPPORT_WORLD_Z
        + sides.OUTBOARD_SIGN[name] * support_spec.SUPPORT_HALF_MACHINE_Z
        for name in sides.SIDES
    }
    foot_end = {
        name: sides.MOUNT_Z[name] + sides.OUTBOARD_SIGN[name] * sides.FOOT_Z1
        for name in sides.SIDES
    }
    assert foot_end["S"] == pytest.approx(support_end["S"])
    assert round(support_end["N"] - foot_end["N"], 2) == 1.61
    assert sides.HOLE_Z_MIN <= sides.HOLE_Z <= sides.HOLE_Z_MAX
    assert sides.HOLE_Z == pytest.approx((sides.HOLE_Z_MIN + sides.HOLE_Z_MAX) / 2.0)
    assert (round(sides.FOOT_LEN, 2), round(sides.HOLE_STATION, 2)) == (16.44, 11.74)


def test_screw_heads_keep_air_to_the_ear_and_the_foot_end() -> None:
    head_r = hold_down.HEAD_DIA / 2.0
    assert sides.HEAD_TO_EAR_FACE_MIN > 0.0
    assert sides.HEAD_TO_EAR_FACE_MIN == pytest.approx(
        sides.HOLE_Z
        - head_r
        - bracket.EAR_T / 2.0
        - bracket.EAR_T_BAND
        - bracket.STATION_BAND
    )
    assert sides.HOLE_Z + head_r < sides.FOOT_Z1
