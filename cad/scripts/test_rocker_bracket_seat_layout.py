"""Offline contracts for the rocker brackets' hold-down seats (#743 PR2)."""

from __future__ import annotations

import pytest

import _interference_contracts
import build_ch_channel_assembly as channel
import build_ch_pivot_bracket as bracket_build
import build_ch_vn_bracket_hold_down_screw as hold_down_build
import ch_vn_bracket_hold_down_screw_spec as hold_down
import dt_arbor_pedestal_spec as pedestal
import dt_vn_pedestal_hold_down_screw_spec as pedestal_screw
import build_fr_rocker_arm_support as support
import ch_pivot_bracket_sides as sides
import ch_pivot_bracket_spec as bracket
import fr_rocker_arm_support_spec as support_spec
import rocker_bracket_seat_layout as seats


def test_layout_screw_is_the_placed_bracket_hold_down() -> None:
    assert hold_down_build.SPEC.skus == ("90280A196",)
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
        and any(name.startswith("ch-channel-1/ch-vn-bracket-hold-down-screw-") for name in pair)
    }
    screws = {
        name
        for pair in pairs
        if "fr-frame-1/fr-rocker-arm-support-1" in pair
        for name in pair
        if name.startswith("ch-channel-1/ch-vn-bracket-hold-down-screw-")
    }
    assert screws == {
        f"ch-channel-1/ch-vn-bracket-hold-down-screw-{n}"
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
    assert seats.ENGAGEMENT_MIN == pytest.approx(7.959, abs=1e-3)
    assert seats.ENGAGEMENT_MIN >= 1.5 * seats.SCREW_MAJOR_DIA
    assert seats.SEAT_THREAD_DEPTH - seats.LINEAR_1PL - seats.SCREW_REACH_MAX == (
        pytest.approx(0.667, abs=1e-3)
    )
    assert (seats.SEAT_THREAD_DEPTH, seats.SEAT_DRILL_DEPTH) == (11.5, 14.7)
    assert seats.SEAT_DRILL_NAME == "#29"
    # The print carries each depth row at .X.
    for value in (seats.SEAT_DRILL_DEPTH, seats.SEAT_THREAD_DEPTH):
        assert round(value, 1) == value


def test_seat_thread_keeps_the_web_wall_at_the_printed_worst_case() -> None:
    """Each seat runs down the 12.70 web column (owner Q13c: thickened
    uniformly, symmetric about its centre plane): the thread's major diameter
    to either web face, the seat at its worst offset toward it (owner Q13d:
    each flat edge at .XX off its nearer web face; the web's .XX thickness
    band enters only toward the far face)."""
    assert support.WEB is seats.WEB
    assert 2.0 * seats.WEB == pytest.approx(12.70)  # 1/2 in
    assert (seats.WEB_PLACES, seats.TOP_FLAT_PLACES) == (2, 2)
    assert seats.TOP_FLAT_EDGE_FROM_WEB == pytest.approx(8.4665 - 6.35)
    # The support's sheet prints its flat edges and web at its .XX.
    assert seats.TOP_FLAT_EDGE_BAND == seats.LINEAR_2PL == pytest.approx(0.51)
    # The hole off the foot's flush side: nearest at .64 - .01 wide and
    # .32 + .01 off the far side, farthest the other way round.
    near_hole = (16.256 - 0.254) - (8.128 + 0.254)
    far_hole = (16.256 + 0.254) - (8.128 - 0.254)
    assert seats.HOLE_FROM_FOOT_SIDE_MIN == pytest.approx(near_hole) == pytest.approx(7.62)
    assert seats.HOLE_FROM_FOOT_SIDE_MAX == pytest.approx(far_hole) == pytest.approx(8.636)
    # An 11/64 transfer punch in the #8 close hole at its +.004 drilled max.
    punch = (4.572 + 0.1016 - 11.0 / 64.0 * 25.4) / 2.0
    assert seats.PUNCH_FLOAT == pytest.approx(punch, abs=1e-3)
    # Toward the near face: the flush edge at 2.12 + 0.51 off it.
    near = near_hole - (2.1165 + 0.51) - punch
    # Toward the far face: the edge at 2.12 - 0.51, the web 12.70 - 0.51.
    far = (12.70 - 0.51) - (far_hole + punch - (2.1165 - 0.51))
    assert seats.SEAT_FROM_NEAR_FACE_MIN == pytest.approx(near, abs=1e-3)
    assert seats.SEAT_FROM_FAR_FACE_MIN == pytest.approx(far, abs=1e-3)
    wall = min(near, far) - seats.SCREW_MAJOR_DIA / 2.0
    assert wall == pytest.approx(seats.WEB_WALL_MIN, abs=1e-3)
    assert wall == pytest.approx(2.76, abs=0.01)
    assert far - seats.SCREW_MAJOR_DIA / 2.0 == pytest.approx(2.92, abs=0.01)
    assert wall >= seats.RULE12_WEB_TARGET


def test_seats_run_in_solid_iron_on_the_support() -> None:
    """Each seat sits outboard of the through cavity (so the web column, or
    the side post past the window's side edge, runs on under its drill point)
    and on the support's top face short of its end-face edge break. The
    south seat now lies wholly in the post; the north one over the window's
    side edge."""
    radius = seats.SEAT_DRILL_DIA / 2.0
    for x in seats.SEAT_LOCAL_X:
        assert abs(x) - radius > support.CAV
        assert abs(x) + radius <= support_spec.SUPPORT_HALF_MACHINE_Z - seats.EDGE_BREAK
    south, north = (abs(x) for x in seats.SEAT_LOCAL_X)
    assert south - radius > support.BIG
    assert north - radius < support.BIG < north + radius
    assert [round(abs(x), 2) for x in seats.SEAT_LOCAL_X] == [84.9, 83.29]


def test_seat_thread_keeps_the_end_wall_at_the_worst_transferred_position() -> None:
    """Codex P2 (2026-10-09 flip): the south seat's thread sat 2.74 from the
    support's end face nominal and 1.32 at the title-block bands. It is
    transferred from the bracket's hole, whose station is given from the
    fit-up-set ear face (user, 2026-10-10, option ii), so only the station's
    band moves it -- not the foot length's -- and the end face moves by half
    the support length's .X band. The end face is the casting's LENGTH end
    (SUPPORT_HALF_MACHINE_Z off its centre), not its height."""
    for x, wall in zip(seats.SEAT_LOCAL_X, seats.END_WALL_MIN, strict=True):
        assert wall == pytest.approx(
            (support_spec.SUPPORT_HALF_MACHINE_Z - abs(x))
            - seats.SCREW_MAJOR_DIA / 2.0
            - bracket.STATION_BAND
            - seats.LINEAR_1PL / 2.0
        )
        assert wall >= seats.RULE12_WEB_TARGET


def test_bracket_hole_clears_the_screw_junction_fillet() -> None:
    """r743-3C: MHA-CH-08's #19 hole (0.025 radial over the #8-32 major) cut the
    fillister's under-head junction fillet, P/10 in diag_mcmaster_fillister's
    recipe, at the hole mouth: 0.0048 mm^3 per screw in assembly:ch_channel."""
    fillet = hold_down._PITCH / 10.0
    radial = (bracket.HOLE_DIA - seats.SCREW_MAJOR_DIA) / 2.0
    assert radial > fillet
    assert channel.BRACKET_HOLE_FILLET_CLEARANCE == pytest.approx(radial - fillet)
    assert bracket.HOLE_DIA < hold_down.HEAD_DIA


def test_bracket_hole_is_mha_004s_hole_for_the_same_thread() -> None:
    """Both carry an #8-32 fillister hold-down of the same head (the bracket's
    5/8, the pedestal's 3/4); their holes must not drift apart."""
    assert hold_down.THREAD == pedestal_screw.THREAD
    assert hold_down.HEAD_DIA == pedestal_screw.HEAD_DIA
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
    # Each term at its own band: along the foot the station's and the foot
    # length's title-block .XX, across it the foot's sides at the .XX band
    # the seat stack carries this foot at, the drilled hole at the title
    # block's +.004/0.
    assert bracket.DRILL_GROWTH == pytest.approx(0.1016)


def test_bracket_lengths_along_the_foot_carry_their_bands_on_the_model() -> None:
    """The S4 fixture plan and the MHA-CH-08 sheet take the +/-0.10 lengths
    from the saved model's dimensions; the tap station and the reamed bore
    carry the drawing contract's bands beside them. The foot length and the
    hold-down station ride the title block's .XX (user ruling 2026-10-14: the
    foot grew instead; #1371 review: the station went the same way)."""
    from _drawing_contract import model_toleranced_dimensions

    assert bracket.EAR_T_BAND == pytest.approx(0.1016)
    assert model_toleranced_dimensions(bracket_build) == {
        ("Ear", "EarThick"): "EAR_T_BAND",
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
    """#1341 option A: one bracket on both sides. Its foot ends at the nearer
    (south) support end face, its length on the printed grid so it never
    overhangs, and 1.62 short of the north one; the free run is too short
    (.320 ears beside the 1/32 thrust washers) to centre the hole, so it sits
    mid-way between the head-to-ear and seat end-wall limits, a window both
    sides share."""
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
    overhang_room = {
        name: sides.OUTBOARD_SIGN[name] * (support_end[name] - foot_end[name])
        for name in sides.SIDES
    }
    assert 0.0 <= overhang_room["S"] < 0.254
    assert round(overhang_room["N"], 2) == 1.62
    assert sides.HOLE_Z_MIN <= sides.HOLE_Z <= sides.HOLE_Z_MAX
    # Mid-window, the printed station on the .XX grid (#1371 review).
    mid = (sides.HOLE_Z_MIN + sides.HOLE_Z_MAX) / 2.0
    assert abs(sides.HOLE_STATION - (mid - bracket.FOOT_Z0)) <= 0.127
    assert (round(sides.FOOT_LEN, 3), round(sides.HOLE_STATION, 3)) == (17.78, 12.446)


def test_the_support_takes_the_foot_with_its_end_wall() -> None:
    """User ruling 2026-10-14 (#954 machinist review): the foot length rides
    the title block and the support is long enough for the foot to keep its
    hole's end wall; the foot never overhangs the support."""
    assert support.BOSS_DEPTH == pytest.approx(2.0 * support_spec.SUPPORT_HALF_MACHINE_Z)
    assert sides._foot_fits(2.0 * support_spec.SUPPORT_HALF_MACHINE_Z)
    assert sides.HOLE_LIGAMENTS_MIN["foot end"] >= bracket.LIGAMENT_TARGET
    assert min(sides.SUPPORT_END_Z.values()) - sides.FOOT_Z1 >= 0.0


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
