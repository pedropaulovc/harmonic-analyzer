"""Behavioral proof for the restored fixed-centre crank mesh."""

import math

import pytest

import crank_mesh_stack as stack


def test_print_worst_closing_corner_cannot_bind() -> None:
    assert stack.TIGHT_BACKLASH_MM > 0.0
    assert stack.TIGHT_BACKLASH_MM < stack.NOMINAL_TIGHT_BACKLASH_MM

def test_gear_seat_runout_and_shortened_pinion_face_reach_the_stack() -> None:
    from gear_seat_fit import GEAR_SEAT_CLEARANCE

    terms = {term.name: term.tight for term in stack.TERMS}
    assert terms["gear bore runout"] == pytest.approx(
        -stack.KC
        * (stack.pinion.BORE_DIAMETRAL_CLEARANCE[1] + GEAR_SEAT_CLEARANCE[1])
        / 2.0
    )
    face_deviation = stack.pinion.printed_deviations(
        stack.pinion.FACE_WIDTH,
        stack.pinion.FACE_WIDTH_PLACES,
        stack.pinion.FACE_WIDTH_LIMITS,
    )[1]
    assert stack.pinion.FACE_WIDTH == 11.6
    assert stack.PINION_HALF_FACE_MAX == pytest.approx(
        (stack.pinion.FACE_WIDTH + face_deviation) / 2.0
    )
    assert stack.MESH_LEVER > stack.post.CRANK_BOSS_NORTH_FACE


def test_closing_bore_spacing_consumes_backlash() -> None:
    def tight(spacing: float) -> float:
        terms = stack.stack_terms(
            spacing_printed=spacing,
            plan_limit_deg=stack.POST_ANGLE_DEG,
            crank_angle_deg=stack.POST_ANGLE_DEG,
            crank_bearing_length=stack.CRANK_BEARING_LENGTH,
        )
        return stack.NOMINAL_TIGHT_BACKLASH_MM + sum(t.tight for t in terms)

    # A sufficiently misplaced fixed bore must not masquerade as a usable mesh.
    assert tight(stack.SPACING_PRINTED - 0.2) < 0.0
    assert tight(stack.SPACING_PRINTED + 0.2) > stack.TIGHT_BACKLASH_MM


def test_bore_angularity_matters_at_the_mesh() -> None:
    def loss(angle: float) -> float:
        return sum(t.tight for t in stack.stack_terms(
            spacing_printed=stack.SPACING_PRINTED,
            plan_limit_deg=angle,
            crank_angle_deg=angle,
            crank_bearing_length=stack.CRANK_BEARING_LENGTH,
        ))

    assert loss(0.0) > loss(stack.POST_ANGLE_DEG)
    assert loss(stack.POST_ANGLE_DEG) > loss(stack.POST_ANGLE_DEG * 2.0)


def test_pose_loss_checks_interior_quadratic_minimum() -> None:
    # y(t) = t² - t has its worst angle at +0.5, not at either limit.
    nominal = stack.NOMINAL_TIGHT_BACKLASH_MM
    assert stack._pose_loss({1.0: nominal, -1.0: nominal + 2.0}, 1.0) == pytest.approx(-0.25)


def test_resting_shaft_tilt_increases_with_overhang() -> None:
    near = stack._float_at_rest(0.05, 70.0, 0.0)
    far = stack._float_at_rest(0.05, 70.0, 10.0)
    assert near == pytest.approx(0.025)
    assert far > near
    assert stack._float_at_rest(0.05, 35.0, 10.0) > far


def test_physical_station_and_plan_bounds_follow_the_inch_stack() -> None:
    import dt_cone_gear_shaft_spec as cone_shaft
    from cone_line import POST_STATION
    from dt_cone_pivot_post_installation import GEAR_AXIS_SHIFT

    offset = (
        stack.gear64.LAYOUT_CENTRE_STATION + GEAR_AXIS_SHIFT
        + stack.gear64.CENTRE_SHIFT_NORTH - POST_STATION
    )
    assert stack.GEAR64_POST_OFFSET == pytest.approx(offset)
    assert stack.CONE_OVERHANG == pytest.approx(
        offset - stack.post.CONE_BOSS_LENGTH / 2.0
    )
    boss = stack.pinion.printed_deviations(
        stack.post.CONE_BOSS_LENGTH,
        stack.post.DRAWING_PRECISION_BY_NAME["ConeBossLen"],
    )
    collar = stack.pinion.printed_deviations(
        cone_shaft.COLLAR_THICKNESS,
        cone_shaft.DRAWING_PRECISION_BY_NAME["CollarWidth"],
    )
    station_travel = (
        max(abs(value) for value in boss) / 2.0
        + max(abs(value) for value in collar)
        + max(abs(value) for value in stack.gear64.FACE_WIDTH_BAND) / 2.0
    )
    for direction in (-1.0, 1.0):
        delta_x = direction * station_travel * stack.SIN_I * stack.COS_I
        delta_c = math.hypot(
            stack.FRAME_DX + delta_x, stack.FRAME_DY
        ) - stack.FRAME_C2C
        assert 0.0 < abs(delta_c) < stack.STATION_64T_DC
    north_contact = stack.R64 * stack.DC_PER_DX * stack.SIN_I
    required_plan = math.radians(1.0) * stack.COS_I**2 * (
        offset + station_travel + north_contact
    )
    assert stack.PLAN_DX_PER_DEG >= required_plan > 0.444


def test_normal_pitch_and_physical_centre_are_shared() -> None:
    import build_dt_drive_train_assembly as bdt
    import cone_line as line

    assert stack.gear64.HELIX_ANGLE_DEG == line.INCLINE_DEG
    assert stack.gear64.NORMAL_MODULE_MM == pytest.approx(25.4 / 24.0)
    assert stack.pinion.MODULE_MM == pytest.approx(stack.gear64.NORMAL_MODULE_MM)
    assert stack.pinion.PRESSURE_ANGLE_DEG == stack.gear64.CUTTER_PRESSURE_ANGLE_DEG == 20.0
    assert stack.gear64.DEDENDUM_FACTOR == stack.pinion.DEDENDUM_FACTOR == 1.25
    assert stack.gear64.LONG_ADDENDUM_MM == 0.0
    assert stack.gear64.FACE_WIDTH == 7.2244
    assert stack.R16 == stack.pinion.PITCH_DIA / 2.0
    assert stack.FRAME_C2C == pytest.approx(43.52432087845904, abs=1e-9)
    assert bdt.CRANK_ACTUAL_C2C == pytest.approx(stack.FRAME_C2C, abs=1e-9)
    assert bdt.MESH16_C2C == pytest.approx(stack.FRAME_C2C, abs=1e-9)
    assert stack.pinion.PIN_CLOCKING_DEG == pytest.approx(bdt.PINION_SEED_DEG, abs=1e-9)


def test_north_band_retains_real_standard_profile_and_fitup_range() -> None:
    assert stack.pinion.OUTSIDE_DIA == pytest.approx(19.05)
    assert stack.pinion.ROOT_DIA == pytest.approx(14.2875)
    assert stack.pinion.SHOULDER_LENGTH == 8.5
    assert stack.pinion.TURNED_DIA == 18.55
    assert stack.pinion.TURNED_DIA_FITUP_MIN == 18.25
    assert stack.pinion.PITCH_DIA < stack.pinion.TURNED_DIA_FITUP_MIN
    assert stack.pinion.TURNED_DIA_FITUP_MIN < (
        stack.pinion.TURNED_DIA - stack.pinion.TURNED_DIA_TOLERANCE_MM
    )


def test_platform_relief_clears_bottom_and_uncut_side_top() -> None:
    import dt_cone_swing_platform_spec as platform
    import dt_cone_swing_platform_geometry as geometry

    assert (
        platform.CRANK_GEAR_RELIEF_WIDTH,
        platform.CRANK_GEAR_RELIEF_LENGTH,
        platform.CRANK_GEAR_RELIEF_DEPTH,
    ) == (29.0, 12.0, 3.0)
    assert platform.CRANK_GEAR_RELIEF_REMAINING_STOCK == pytest.approx(3.35)
    assert platform.CRANK_GEAR_RELIEF_REMAINING_STOCK_WORST >= 1.5
    assert min(platform.CRANK_GEAR_PLATFORM_AIR.values()) >= 0.5
    # Merely deepening the metric 18-mm pocket leaves tip metal outside it.
    assert math.hypot(18.0 / 2.0, platform.POST_CONE_BORE_HEIGHT) < (
        stack.gear64.OUTSIDE_DIA / 2.0
    )
    assert min(
        geometry.CRANK_GEAR_RELIEF_EDGE_AIR,
        geometry.CRANK_GEAR_RELIEF_POST_AIR,
    ) >= 0.25


def test_chain_uses_a_feasible_even_count_without_changing_pitch() -> None:
    import _chain as chain
    import cone_line as line

    assert chain.CRANK_CENTRE == (-line.X_CRANK, line.Y_CRANK)
    assert chain.LINK_PITCH == 6.35
    assert chain.LINK_COUNT % 2 == 0
    assert chain.CENTRELINE_LEN > chain._loop_length(0.5)
    assert chain.LINK_COUNT == max(
        2 * round(chain._loop_length(chain.SAG_NOMINAL) / (2.0 * chain.LINK_PITCH)),
        2 * math.ceil(chain._loop_length(0.5) / (2.0 * chain.LINK_PITCH)),
    )
    assert chain._loop_length(chain.SAG) == pytest.approx(chain.CENTRELINE_LEN, abs=1e-6)


def test_platform_axis_maps_to_the_restored_crank_axis() -> None:
    import cone_line as line
    import dt_cone_swing_platform_crank_axis as platform

    x, z = platform.CRANK_SEAT_ANCHOR
    machine_x = line.PIVOT_XZ[0] + x * line.COS_I + z * line.SIN_I
    assert machine_x == pytest.approx(line.X_CRANK, abs=1e-6)
    assert line.Y_BASE_TOP + platform.CRANK_AXIS_Y == pytest.approx(line.Y_CRANK)
    assert math.hypot(x, z) == pytest.approx(platform.CRANK_AXIS_OFF)


def test_open_corner_carries_the_cone_stack_north_float() -> None:
    # Codex P2 on #1154: at the stack's north float the 64T slides up the
    # inclined cone axis and the centres open further; the printed worst-case
    # contact ratio must count it.
    import build_dt_drive_train_assembly as bdt
    # Drawings and their historic rounded equality stay outside this experiment.
    from cone_line import COS_I, SIN_I
    from cone_stack_end_play import CONE_FLOAT_NORTH, SHAFT_END_PLAY, STACK_FLOAT

    assert CONE_FLOAT_NORTH == SHAFT_END_PLAY[1] + STACK_FLOAT[1]
    float_term = stack.OPEN_TERMS["cone stack north float"]
    assert float_term == pytest.approx(
        CONE_FLOAT_NORTH * SIN_I * COS_I * stack.DC_PER_DX
    )
    # The exact opening at the physical centres: the 64T's in-plane leg grows
    # by the float's projection; the booked linear term stays within 0.002.
    exact = (
        math.hypot(bdt._DX16 + CONE_FLOAT_NORTH * SIN_I * COS_I, bdt._DY16)
        - bdt.CRANK_ACTUAL_C2C
    )
    assert exact == pytest.approx(bdt.CRANK_MESH_FLOAT_OPENING_EXACT)
    assert 0.0 < exact - float_term < 0.002

    def worst(opening: float) -> float:
        return stack.contact_ratio(
            centre_distance=bdt.CRANK_ACTUAL_C2C + opening,
            tip_dia_16=stack.TIP_DIA_LOW_16,
            tip_dia_64=stack.TIP_DIA_LOW_64,
        )

    unfloated = worst(stack.OPEN_CENTRE_DISTANCE_MM - float_term)
    baseline_floor = 0.62
    assert worst(stack.OPEN_CENTRE_DISTANCE_MM) == pytest.approx(
        bdt.CRANK_MESH_CONTACT_RATIO_WORST
    )
    # Both booked and exact north-float openings retain the accepted physical
    # floor without requiring equality to unchanged historic drawing text.
    assert unfloated > worst(stack.OPEN_CENTRE_DISTANCE_MM)
    assert bdt.CRANK_MESH_CONTACT_RATIO_WORST >= baseline_floor
    assert worst(stack.OPEN_CENTRE_DISTANCE_MM - float_term + exact) >= baseline_floor
