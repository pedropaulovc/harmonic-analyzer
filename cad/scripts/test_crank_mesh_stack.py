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
    assert stack.pinion.FACE_WIDTH == 11.4
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


def test_platform_axis_maps_to_the_restored_crank_axis() -> None:
    import cone_line as line
    import cone_swing_platform_crank_axis as platform

    x, z = platform.CRANK_SEAT_ANCHOR
    machine_x = line.PIVOT_XZ[0] + x * line.COS_I + z * line.SIN_I
    assert machine_x == pytest.approx(line.X_CRANK, abs=1e-6)
    assert line.Y_BASE_TOP + platform.CRANK_AXIS_Y == pytest.approx(line.Y_CRANK)
    assert math.hypot(x, z) == pytest.approx(platform.CRANK_AXIS_OFF)


def test_open_corner_carries_the_cone_stack_north_float() -> None:
    # Codex P2 on #1154: at the stack's north float the 64T slides up the
    # inclined cone axis and the centres open further; the printed worst-case
    # contact ratio must count it.
    import build_drive_train_assembly as bdt
    import crank_drive_gear_notes
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
    printed = crank_drive_gear_notes.WORST_CONTACT_RATIO
    assert worst(stack.OPEN_CENTRE_DISTANCE_MM) == pytest.approx(
        bdt.CRANK_MESH_CONTACT_RATIO_WORST
    )
    # Without the float the sheets would print a figure the floated mesh
    # does not reach; with it (booked or exact) the print holds.
    assert math.floor(unfloated * 100.0) / 100.0 > worst(
        stack.OPEN_CENTRE_DISTANCE_MM - float_term + exact
    )
    assert printed == math.floor(bdt.CRANK_MESH_CONTACT_RATIO_WORST * 100.0) / 100.0
    assert worst(stack.OPEN_CENTRE_DISTANCE_MM - float_term + exact) >= printed
