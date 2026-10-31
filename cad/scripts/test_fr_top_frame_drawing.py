"""Offline contracts for the top-frame geometry and drawing."""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path

import pytest

import _config
from _printed_tolerance import printed_band_mm
import ch_fulcrum_keeper_spec as keeper
import rocker_bank_layout as rocker_bank
import ch_vn_frame_side_screw_spec as keeper_screw
from _mcmaster_91794a080 import FILLISTER_SIZE
import build_fr_top_frame as part
import draw_fr_top_frame as drawing
from fr_frame_attachment_spec import (
    CAP_MOUTH_Y,
    CAP_RECESS_DEPTH,
    CAP_RECESS_DIAMETER,
    CASTING_FULL_THREAD_DEPTH,
    TOP_CASTING_TAP_DRILL_DEPTH,
    COLUMN_SOCKET_DIAMETER,
    TOP_SCREW_SEAT_Z,
    TOP_SCREW_Y,
    TUBE_CROSS_HOLE_DIAMETER,
)
from fr_vn_tube_frame_cap_spec import MAX_OUTER_DIAMETER
from _surface_finish import SEAT_UM
import fr_top_frame_spec as spec
import fr_tube_frame_spec


def test_nominal_corner_bores_and_cap_recesses_clear_the_installed_stack() -> None:
    assert part.BORE_DIA == COLUMN_SOCKET_DIAMETER == pytest.approx(25.5016)  # 1.004
    assert part.CAP_RECESS_DIAMETER == CAP_RECESS_DIAMETER
    assert part.CAP_RECESS_DEPTH == CAP_RECESS_DEPTH
    assert CAP_RECESS_DIAMETER > MAX_OUTER_DIAMETER
    assert math.isclose(
        part.CAP_RECESS_DIAMETRAL_CLEARANCE,
        CAP_RECESS_DIAMETER - MAX_OUTER_DIAMETER,
        abs_tol=1e-12,
    )
    assert math.isclose(part.CAP_RECESS_DIAMETRAL_CLEARANCE, 0.444432, abs_tol=1e-6)
    assert math.isclose(
        part.CAP_RECESS_DIAMETRAL_CLEARANCE + part.CAP_RECESS_DIAMETER_BAND[0],
        0.647632,
        abs_tol=1e-6,
    )
    # CAD reference clearance is unchanged; actual sockets are matched to
    # their assigned tubes rather than accepted against a fixed bore band.
    assert math.isclose(
        part.BORE_DIA - fr_tube_frame_spec.OUTER_DIA,
        0.1016,
        abs_tol=1e-9,
    )
    assert part.CAP_RECESS_FLOOR_Y - part.SIDE_TAP_DRILL_DIA / 2.0 > 0.0
    assert part.CAP_RECESS_DIAMETER_BAND == pytest.approx((0.2032, 0.0))
    assert part.CAP_RECESS_DEPTH_BAND == pytest.approx((0.3048, 0.0))
    recess_floor_world = TOP_SCREW_Y + part.CAP_RECESS_FLOOR_Y
    assert math.isclose(CAP_MOUTH_Y - recess_floor_world, 1.51765, abs_tol=1e-6)
    assert math.isclose(
        recess_floor_world - (TOP_SCREW_Y + TUBE_CROSS_HOLE_DIAMETER / 2.0),
        3.937,
        abs_tol=1e-6,
    )


def test_four_cross_taps_are_bottoming_10_32_with_tooling_lead() -> None:
    assert len(part.SIDE_SCREW_XS) * len(part.SIDE_SCREW_FACES) == 4
    assert part.SIDE_TAP_SPEC.kind == "tapped_bottoming"
    assert part.SIDE_TAP_SPEC.size == "#10-32"
    assert part.SIDE_TAP_SPEC.thread_class == "2B"
    assert part.SIDE_TAP_SPEC.depth_mm == TOP_CASTING_TAP_DRILL_DEPTH
    assert part.SIDE_TAP_SPEC.overrides_mm["ThreadDepth"] == CASTING_FULL_THREAD_DEPTH
    pitch = 25.4 / 32.0
    assert TOP_CASTING_TAP_DRILL_DEPTH - CASTING_FULL_THREAD_DEPTH >= 2.0 * pitch
    depth_tolerance = printed_band_mm(1)
    assert (
        TOP_CASTING_TAP_DRILL_DEPTH - CASTING_FULL_THREAD_DEPTH - 2.0 * depth_tolerance
        >= 2.0 * pitch
    )
    assert part.COUNTERBORE_FLOOR == TOP_SCREW_SEAT_Z
    # The stock head's top must sit below the mouth's lowest point on the
    # boss barrel, which is at the counterbore's widest |x|.
    mouth_low = abs(part.FRONT_COLUMN_Z) + math.sqrt(
        (part.BOSS_DIA / 2.0) ** 2 - (part.COUNTERBORE_DIA / 2.0) ** 2
    )
    assert part.COUNTERBORE_FLOOR + part.CROSS_SCREW_HEAD_H < mouth_low
    assert part.COUNTERBORE_PLANE > abs(part.FRONT_COLUMN_Z) + part.BOSS_DIA / 2.0
    places = spec.DRAWING_PRECISION["CounterboreRearProfile"]["CB1Dia"]
    smallest_counterbore = (
        round(part.COUNTERBORE_DIA, places) - spec.PRINTED_LINEAR_BAND_MM[places]
    )
    assert smallest_counterbore > part.CROSS_SCREW_HEAD_DIA


@pytest.mark.parametrize("boss_direction", (-1, 1))
@pytest.mark.parametrize("seat_direction", (-1, 1))
@pytest.mark.parametrize("floor_direction", (-1, 1))
def test_cross_screw_head_stays_below_the_counterbore_mouth_at_every_printed_band_corner(
    boss_direction: int, seat_direction: int, floor_direction: int
) -> None:
    boss_places = spec.DRAWING_PRECISION["BossUpProfile"]["C0Dia"]
    seat_places = spec.DRAWING_PRECISION["CounterboreRearProfile"]["CB1Dia"]
    floor_places = spec.DRAWING_REFERENCE_PRECISION[
        "counterbore floor from socket axis"
    ]
    boss_radius = spec.printed_limit(part.BOSS_DIA, boss_places, boss_direction) / 2.0
    counterbore_radius = (
        spec.printed_limit(part.COUNTERBORE_DIA, seat_places, seat_direction) / 2.0
    )
    floor_offset = spec.printed_limit(
        part.COUNTERBORE_FLOOR - abs(part.FRONT_COLUMN_Z), floor_places, floor_direction
    )
    # The mouth's lowest point on a Y-axis barrel is at the counterbore's
    # widest |X|; the head is flush when its top stays below it.
    mouth_low = math.sqrt(boss_radius**2 - counterbore_radius**2)
    recess = mouth_low - (floor_offset + part.CROSS_SCREW_HEAD_H)
    assert recess > 0.0
    assert counterbore_radius > part.CROSS_SCREW_HEAD_DIA / 2.0
    if (boss_direction, seat_direction, floor_direction) == (-1, 1, 1):
        assert recess == pytest.approx(part.COUNTERBORE_PRINTED_HEAD_RECESS)


def test_counterbore_floor_keeps_rule_12_target_to_the_cap_recess() -> None:
    # Codex reviews of 67d8b2c6 and 080fda97 (sheet 4, A-A): with the floor
    # at 16.1 its outboard limit left 1.518 (.X) / 1.80 (.XX) to the cap
    # recess's deepest, widest corner, and .XXX read as over-precision
    # (63d4b5d6).  drawing-guidelines.md rule 17 (walls and webs) fixes it with geometry: the floor stands at 16.35
    # and prints .XX; every printed corner keeps 2.0.
    floor_places = spec.DRAWING_REFERENCE_PRECISION["counterbore floor from socket axis"]
    axis_places = spec.DRAWING_REFERENCE_PRECISION["cross screw axis from boss top"]
    seat_places = spec.DRAWING_PRECISION["CounterboreRearProfile"]["CB1Dia"]
    assert floor_places == 2
    assert TOP_SCREW_SEAT_Z == pytest.approx(128.524)  # .65 off 4.410
    floor_offset = spec.printed_limit(
        part.COUNTERBORE_FLOOR - abs(part.FRONT_COLUMN_Z), floor_places, -1.0
    )
    recess_radius = (part.CAP_RECESS_DIAMETER + part.CAP_RECESS_DIAMETER_BAND[0]) / 2.0
    recess_floor = part.CAP_RECESS_FLOOR_Y - part.CAP_RECESS_DEPTH_BAND[0]
    rim = spec.PRINTED_LINEAR_BAND_MM[axis_places] + spec.printed_limit(
        part.COUNTERBORE_DIA, seat_places, 1.0
    ) / 2.0
    ligament = math.hypot(floor_offset - recess_radius, recess_floor - rim)
    assert ligament == pytest.approx(part.COUNTERBORE_PRINTED_CAP_LIGAMENT)
    assert ligament == pytest.approx(2.803, abs=5e-4)
    assert ligament >= 2.032
    assert part.COUNTERBORE_PRINTED_NEAR_WALL >= 2.032
    assert part.COUNTERBORE_PRINTED_HEAD_RECESS > 0.0


def test_cross_tap_ends_stay_in_the_real_boss_and_side_web_union() -> None:
    # The inward boss edge is not a free wall: the full-height side-rail
    # web continues past it and contains the whole far thread/drill envelope.
    major_dia = 4.826
    thread_end_z = part.COUNTERBORE_FLOOR - CASTING_FULL_THREAD_DEPTH
    drill_point_z = (
        part.COUNTERBORE_FLOOR
        - TOP_CASTING_TAP_DRILL_DEPTH
        - part.SIDE_TAP_DRILL_DIA / 2.0 * part.DRILL_POINT_H
    )
    assert part.SIDE_TAP_THREAD_MAJOR_DIA == major_dia
    assert part.SIDE_TAP_THREAD_END_Z == pytest.approx(thread_end_z)
    assert part.SIDE_TAP_DRILL_POINT_Z == pytest.approx(drill_point_z)
    assert 0.0 < drill_point_z < thread_end_z < part.WEB_IN_Z
    assert part.SIDE_TAP_THREAD_WALL_MARGIN == pytest.approx(4.0894)
    assert part.SIDE_TAP_DRILL_WALL_MARGIN == pytest.approx(4.4831)
    assert major_dia / 2.0 < part.HALF_H


def test_smaller_bosses_leave_real_plan_corners_and_the_outward_foot_seat() -> None:
    assert part.BOSS_DIA == spec.BOSS_DIA == pytest.approx(44.958)  # 1.77
    assert part.BORE_DIA == pytest.approx(25.5016)
    assert part.CAP_RECESS_DIAMETER == pytest.approx(27.5082)
    assert (part.BOSS_DIA - part.CAP_RECESS_DIAMETER) / 2.0 == pytest.approx(8.7249)
    assert (
        math.hypot(part.RAIL_W_SIDE / 2.0, part.RAIL_W_FR / 2.0) > part.BOSS_DIA / 2.0
    )
    assert drawing.PLAN_HALF_X - part.OUTER_X == pytest.approx(5.3848)
    assert drawing.PLAN_HALF_Z - part.OUTER_Z == pytest.approx(3.429)
    assert (
        drawing.BOSS_ABOVE_RAIL_LINE_XY[0]
        - drawing.DETAIL_SECTION_CENTER[0]
        - drawing.DETAIL_PLAN_HALF_D
    ) == pytest.approx(0.00745)
    assert part.FULCRUM_KEEPER_CENTRE_Z == pytest.approx(rocker_bank.STACK_MID_Z)
    assert part.KEEPER_TAP_Z_FRONT == pytest.approx(
        keeper.FULCRUM_KEEPER_CENTRE_Z - keeper.KEEPER_SCREW_Z_OFF
    )
    assert part.KEEPER_TAP_Z_REAR == pytest.approx(
        keeper.FULCRUM_KEEPER_CENTRE_Z + keeper.KEEPER_SCREW_Z_OFF
    )
    # Contract stations are displayed to three places; do not round the bank.
    assert part.KEEPER_TAP_Z_FRONT == pytest.approx(-83.504, abs=0.0005)
    assert part.KEEPER_TAP_Z_REAR == pytest.approx(82.496, abs=0.0005)
    assert part.KEEPER_FOOT_TIP_Z_FRONT == pytest.approx(-88.004, abs=0.0005)
    assert part.KEEPER_FOOT_TIP_Z_REAR == pytest.approx(86.996, abs=0.0005)
    # The keeper stations are ch's; the bosses move with the frame's column Z.
    dz = abs(part.FRONT_COLUMN_Z) - 112.0
    assert part.KEEPER_FOOT_BOSS_MARGINS == pytest.approx(
        (1.517 + dz, 2.525 + dz), abs=0.0005
    )
    assert min(part.KEEPER_FOOT_BOSS_MARGINS) >= 1.016
    assert min(part.KEEPER_FOOT_PRINTED_BOSS_MARGINS) > 0.0
    assert part.KEEPER_FOOT_RAIL_MARGINS == pytest.approx(
        (4.946 + dz, 5.954 + dz), abs=0.0005
    )
    stock_major = FILLISTER_SIZE[0]
    assert part.KEEPER_TAP_BOSS_MARGINS == pytest.approx(
        tuple(
            math.hypot(part.KEEPER_TAP_X - part.COLUMN_X, boss_z - tap_z)
            - part.BOSS_DIA / 2.0
            - stock_major / 2.0
            for boss_z, tap_z in (
                (part.FRONT_COLUMN_Z, part.KEEPER_TAP_Z_FRONT),
                (part.REAR_COLUMN_Z, part.KEEPER_TAP_Z_REAR),
            )
        )
    )


@pytest.mark.parametrize("front_station_direction", (-1, 1))
@pytest.mark.parametrize("rear_station_direction", (-1, 1))
@pytest.mark.parametrize("pitch_direction", (-1, 1))
@pytest.mark.parametrize("overall_direction", (-1, 1))
@pytest.mark.parametrize("boss_direction", (-1, 1))
def test_complete_keeper_foot_clears_boss_at_every_printed_fitup_corner(
    front_station_direction: int,
    rear_station_direction: int,
    pitch_direction: int,
    overall_direction: int,
    boss_direction: int,
) -> None:
    # Actual fit-up locates the lug INNER faces before transferring the
    # frame taps. This is not a stack of model-nominal tap/hole positions.
    # The keeper prints its overall length off the inner lug face (owner
    # ruling 2026-10-28), so that one band reaches the foot tip.
    overall_places = keeper.DRAWING_PRECISION["OverallLengthReference"]["OverallLength"]
    boss_places = spec.DRAWING_PRECISION["BossUpProfile"]["C0Dia"]
    pitch_places = spec.DRAWING_REFERENCE_PRECISION["socket vertical pitch"]
    # The keeper prints on its own sheet's unit; the frame on this sheet's.
    overall_length = part._keeper_printed(
        keeper.OVERALL_LENGTH, overall_places, overall_direction
    )
    boss_radius = spec.printed_limit(part.BOSS_DIA, boss_places, boss_direction) / 2.0
    socket_pitch = spec.printed_limit(
        part.REAR_COLUMN_Z - part.FRONT_COLUMN_Z, pitch_places, pitch_direction
    )
    front_inner = (
        part._keeper_printed(
            keeper.KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM[0],
            keeper.KEEPER_FITUP_PLACES,
        )
        + front_station_direction * keeper.KEEPER_FITUP_LOCATION_BAND_MM
    )
    rear_inner = (
        part._keeper_printed(
            keeper.KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM[1],
            keeper.KEEPER_FITUP_PLACES,
        )
        + rear_station_direction * keeper.KEEPER_FITUP_LOCATION_BAND_MM
    )
    margins = (
        front_inner - overall_length - boss_radius,
        socket_pitch - rear_inner - overall_length - boss_radius,
    )
    assert min(margins) > 0.0
    if (
        front_station_direction,
        rear_station_direction,
        pitch_direction,
        overall_direction,
        boss_direction,
    ) == (-1, 1, -1, 1, 1):
        assert margins == pytest.approx(part.KEEPER_FOOT_PRINTED_BOSS_MARGINS)


def _in_corner_crop(dx: float, dz: float, triangle=part.CORNER_CROP_TRIANGLE) -> bool:
    """Whether the plan point (dx, dz) lies inside ``triangle``: by default
    the sketched flange corner crop, as offsets outward from a boss axis."""
    (x0, z0), (x1, z1), (x2, z2) = triangle

    def side(ax: float, az: float, bx: float, bz: float) -> float:
        return (bx - ax) * (dz - az) - (bz - az) * (dx - ax)

    signs = (side(x0, z0, x1, z1), side(x1, z1, x2, z2), side(x2, z2, x0, z0))
    return all(sign > 0.0 for sign in signs) or all(sign < 0.0 for sign in signs)


def test_boss_additions_match_an_independent_t_section_area_integral() -> None:
    # Sample the actual two rectangle rings, not the circle-cap formula.
    step = 0.05
    radius = part.BOSS_DIA / 2.0
    upper = lower = 0.0
    for i in range(round(2.0 * radius / step)):
        x = part.COLUMN_X - radius + (i + 0.5) * step
        for j in range(round(2.0 * radius / step)):
            z = abs(part.FRONT_COLUMN_Z) - radius + (j + 0.5) * step
            if (x - part.COLUMN_X) ** 2 + (
                z - abs(part.FRONT_COLUMN_Z)
            ) ** 2 > radius**2:
                continue
            in_web = (
                x <= part.WEB_OUT_X
                and z <= part.WEB_OUT_Z
                and not (x < part.WEB_IN_X and z < part.WEB_IN_Z)
            )
            in_flange = (
                x <= part.OUTER_X
                and z <= part.OUTER_Z
                and not (x < part.INNER_X and z < part.INNER_Z)
                and not _in_corner_crop(x - part.COLUMN_X, z - abs(part.FRONT_COLUMN_Z))
            )
            upper += (
                part.HALF_H
                + part.BOSS_ABOVE
                - (part.HALF_H if in_web else part.FLANGE if in_flange else 0.0)
            ) * step**2
            lower += (
                part.BOSS_BELOW if in_web else part.HALF_H + part.BOSS_BELOW
            ) * step**2
    actual_upper, actual_lower = part._boss_add_volumes()
    assert actual_upper == pytest.approx(upper, abs=10.0)
    assert actual_lower == pytest.approx(lower, abs=10.0)
    assert actual_upper == pytest.approx(18825.018769296887)
    assert actual_lower == pytest.approx(28532.016293968834)


def test_counterbore_and_cross_tap_volumes_match_smooth_integrals() -> None:
    # Substitute x=r*sin(theta) so the disk-chord endpoints are smooth.
    # This is independent of the builder's linear-X integration grids.
    boss_radius = part.BOSS_DIA / 2.0
    counterbore_radius = part.COUNTERBORE_DIA / 2.0
    tap_radius = part.SIDE_TAP_DRILL_DIA / 2.0
    bore_radius = part.BORE_DIA / 2.0
    floor_offset = part.COUNTERBORE_FLOOR - abs(part.FRONT_COLUMN_Z)
    assert part.COUNTERBORE_PLANE > abs(part.FRONT_COLUMN_Z) + boss_radius
    steps = 4096
    theta_step = math.pi / steps
    counterbore_volume = tap_volume = 0.0
    for index in range(steps):
        theta = -math.pi / 2.0 + (index + 0.5) * theta_step
        sine, cosine = math.sin(theta), math.cos(theta)
        counterbore_volume += (
            2.0
            * counterbore_radius**2
            * cosine**2
            * (
                math.sqrt(boss_radius**2 - (counterbore_radius * sine) ** 2)
                - floor_offset
            )
            * theta_step
        )
        tap_volume += (
            2.0
            * tap_radius**2
            * cosine**2
            * (
                TOP_CASTING_TAP_DRILL_DEPTH
                - 2.0 * math.sqrt(bore_radius**2 - (tap_radius * sine) ** 2)
            )
            * theta_step
        )
    tap_volume += math.pi / 3.0 * tap_radius**3 * part.DRILL_POINT_H
    assert part._counterbore_removal() == pytest.approx(counterbore_volume, abs=0.01)
    assert part._side_tap_removal() == pytest.approx(tap_volume, abs=0.01)


def test_top_rim_chamfers_cover_new_corners_and_window_mitres() -> None:
    outer, window = part._top_rim_removal()
    assert outer == pytest.approx(1439.5822504528257, rel=2e-4)
    # The 25-wide bar shortens the two window rims by another 2 mm of break
    # compared with the former 24-wide section (c^2 / 2 mm^2 per mm).
    assert window == pytest.approx(1765.4378511371153, rel=2e-4)
    assert part.WEB_T == pytest.approx(13.0048)  # .512
    root_chord = math.sqrt((part.BOSS_DIA / 2.0) ** 2 - (part.WEB_T / 2.0) ** 2)
    side_run = 2.0 * (abs(part.FRONT_COLUMN_Z) - root_chord)
    front_rear_run = 2.0 * (part.COLUMN_X - root_chord)
    outer_run = 2.0 * side_run - part.HUB_RIB_W + 2.0 * front_rear_run
    window_run = outer_run - 2.0 * (part.LAND_X1 - part.LAND_X0)
    assert root_chord == pytest.approx(21.517997937540564)
    fillet_area = (1.0 - math.pi / 4.0) * part.ROOT_FILLET_R**2
    crossbar_run = 2.0 * 2.0 * part.BAR_POCKET_Z
    assert part._t_root_add() == pytest.approx(
        fillet_area * (outer_run + window_run + crossbar_run)
    )
    assert not hasattr(part, "_outer_corner_top_edges")


def test_flange_corner_crops_remove_all_four_nibs_outside_the_barrels() -> None:
    """User ruling 2026-10-14: R22.5 stops short of the rectangular flange's
    plan corner, which left a flange nib outside each barrel just under the
    crown.  One sketched triangle per corner, cut before the bosses, removes
    it; the boss union restores the barrel segment inside the chord."""
    radius = part.BOSS_DIA / 2.0
    a, b = part.RAIL_W_SIDE / 2.0, part.RAIL_W_FR / 2.0
    assert math.hypot(a, b) > radius
    apex, side_leg, fr_leg = part.CORNER_CROP_TRIANGLE
    # Every vertex stands outside the plan rectangle: no sketch edge lies on
    # a face, and the chord crosses both outer faces ...
    assert apex[0] > a and apex[1] > b
    assert side_leg[0] > a and fr_leg[1] > b
    slope = (fr_leg[1] - side_leg[1]) / (fr_leg[0] - side_leg[0])
    side_cross = (a, side_leg[1] + (a - side_leg[0]) * slope)
    fr_cross = (side_leg[0] + (b - side_leg[1]) / slope, b)
    # ... inside the barrel, so the union leaves no flange outside it and the
    # cut never nicks the barrel; the triangle stays off the web ring. (A
    # printed-limit test below holds it inside the smallest printed barrel.)
    assert math.hypot(*side_cross) < radius and math.hypot(*fr_cross) < radius
    assert min(min(point) for point in part.CORNER_CROP_TRIANGLE) > part.WEB_T / 2.0
    # Exact areas against a 0.01 mm grid over the corner: the flange the cut
    # removes, the nib outside the barrel, and the part the boss refills.
    # The flange stops at the outer faces x = a, z = b, which fall between
    # grid lines, so the last cell of each run is clipped to the flange.
    step = 0.01

    def cells(start: float, stop: float):
        """Midpoints and widths of step cells tiling [start, stop] exactly."""
        for index in range(math.ceil((stop - start) / step - 1e-9)):
            low = start + index * step
            high = min(low + step, stop)
            yield (low + high) / 2.0, high - low

    x0 = min(point[0] for point in part.CORNER_CROP_TRIANGLE)
    z0 = min(point[1] for point in part.CORNER_CROP_TRIANGLE)
    crop = nib = refilled = 0.0
    for dx, width in cells(x0, a):
        for dz, depth in cells(z0, b):
            area = width * depth
            in_barrel = math.hypot(dx, dz) <= radius
            cropped = _in_corner_crop(dx, dz)
            crop += area * cropped
            nib += area * (not in_barrel)
            refilled += area * (cropped and in_barrel)
            assert cropped or in_barrel, (dx, dz)
    assert crop == pytest.approx(part.CORNER_CROP_AREA, abs=0.02)
    assert nib == pytest.approx(part.CORNER_NIB_AREA, abs=0.02)
    assert refilled == pytest.approx(part.CORNER_CROP_IN_BOSS, abs=0.02)
    assert part.CORNER_NIB_AREA == pytest.approx(10.307, abs=1e-3)
    assert part.CORNER_CROP_AREA == pytest.approx(12.969, abs=1e-3)
    # The casting model is empty in all four nibs at mid-flange, solid on the
    # barrels and on the flange beside them.
    y = (part.FLANGE_BOT_Y + part.HALF_H) / 2.0
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            def at(dx: float, dz: float) -> bool:
                return part._casting_occupies(
                    sx * (part.COLUMN_X + dx), y, sz * (abs(part.FRONT_COLUMN_Z) + dz)
                )

            assert not at(a - 0.5, b - 0.5)
            assert not at(a - 0.05, (part.CORNER_SIDE_CUT + b) / 2.0)
            assert not at((part.CORNER_FR_CUT + a) / 2.0, b - 0.05)
            assert at(0.95 * radius / math.sqrt(2.0), 0.95 * radius / math.sqrt(2.0))
            assert at(a - 0.5, -16.0) and at(-16.0, b - 0.5)
    # No edge-break pick stands in a corner quadrant outside its barrel.
    for feature, (picks, _removal, _shared) in part.EXTERNAL_EDGE_BREAKS.items():
        for x, _y, z in picks:
            dx, dz = abs(x) - part.COLUMN_X, abs(z) - abs(part.FRONT_COLUMN_Z)
            assert not (dx > 0.0 and dz > 0.0 and math.hypot(dx, dz) > radius + 1e-6), (
                feature, x, z,
            )
    # One sketch of four triangles, cut through the band before the bosses
    # and charged at its exact flange volume.
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build("):]
    assert (
        "for k, (sx, sz) in enumerate(((1.0, 1.0), (1.0, -1.0), (-1.0, -1.0), (-1.0, 1.0))):"
        in body
    )
    assert "for px, pz in CORNER_CROP_TRIANGLE" in body
    assert "v_crops = 4.0 * CORNER_CROP_AREA * FLANGE" in body
    assert 'volume_check(adapter, "flange corner crops", volume - v_crops, 1.0)' in body
    assert (
        body.index('name_last_feature(adapter, "Crossbar")')
        < body.index('name_last_feature(adapter, "CornerCrop")')
        < body.index("v_boss_up, v_boss_down = _boss_add_volumes()")
    )


def _flange_left_outside_barrel(
    triangle,
    axis: tuple[float, float],
    sign: tuple[float, float],
    radius: float,
    side: float,
    front_rear: float,
) -> int:
    """Sampled plan points of one corner's flange, its outer faces ``side``
    and ``front_rear`` off the boss ``axis`` toward ``sign``, that stand
    outside a ``radius`` barrel and outside the plan ``triangle``."""
    step = 0.05
    left = 0
    for i in range(math.ceil(side / step)):
        dx = (i + 0.5) * step
        if dx >= side:
            continue
        j0 = int(math.sqrt(max(radius**2 - dx**2, 0.0)) / step)
        for j in range(j0, math.ceil(front_rear / step)):
            dz = (j + 0.5) * step
            if dz >= front_rear or math.hypot(dx, dz) <= radius + 1e-6:
                continue
            point = (axis[0] + sign[0] * dx, axis[1] + sign[1] * dz)
            left += not _in_corner_crop(*point, triangle)
    return left


def _t_flange_overhang(width: float, width_label: str, web_label: str) -> float:
    """A T flange's least printed overhang past its centred web, each side:
    the narrowest printed flange less the thickest printed web, halved."""
    band = spec.PRINTED_LINEAR_BAND_MM
    reference = spec.DRAWING_REFERENCE_PRECISION
    width_places, web_places = reference[width_label], reference[web_label]
    return (
        part._printed_nominal(width, width_places)
        - band[width_places]
        - part._printed_nominal(part.WEB_T, web_places)
        - band[web_places]
    ) / 2.0


def test_flange_corner_crop_chord_holds_at_every_printed_limit() -> None:
    # A conforming part may pair the smallest or largest .X barrel with each
    # outer face anywhere in its printed band: half the .X flange extent less
    # half the .XX socket pitch, both centred on the socket pattern (a wider
    # band than the local flange width's). At all four corners the crop
    # leaves no flange outside the barrel and stays clear of the printed web.
    band = spec.PRINTED_LINEAR_BAND_MM
    outer = spec.DRAWING_PRECISION["OuterProfile"]
    reference = spec.DRAWING_REFERENCE_PRECISION

    def face_band(
        extent: float, extent_places: int, pitch: float, pitch_places: int
    ) -> tuple[float, float]:
        offset = (
            part._printed_nominal(extent, extent_places)
            - part._printed_nominal(pitch, pitch_places)
        ) / 2.0
        half = (band[extent_places] + band[pitch_places]) / 2.0
        return offset - half, offset + half

    z_col = abs(part.FRONT_COLUMN_Z)
    side = face_band(
        2.0 * part.OUTER_X,
        outer["Width"],
        2.0 * part.COLUMN_X,
        reference["socket horizontal pitch"],
    )
    front_rear = face_band(
        2.0 * part.OUTER_Z,
        outer["Depth"],
        2.0 * z_col,
        reference["socket vertical pitch"],
    )
    assert side == pytest.approx((16.967, 17.221), abs=5e-4)
    assert front_rear == pytest.approx((18.796, 19.304), abs=5e-4)
    assert part.CORNER_CROP_FACE_OFFSETS["side"] == pytest.approx(side)
    assert part.CORNER_CROP_FACE_OFFSETS["front/rear"] == pytest.approx(front_rear)
    for (low, high), width, label in (
        (side, part.RAIL_W_SIDE, "side flange width"),
        (front_rear, part.RAIL_W_FR, "front rear flange width"),
    ):
        half_band = band[reference[label]] / 2.0
        assert low < width / 2.0 - half_band and width / 2.0 + half_band < high
    boss_places = spec.DRAWING_PRECISION["BossUpProfile"]["C0Dia"]
    radii = tuple(
        spec.printed_limit(part.BOSS_DIA, boss_places, sign) / 2.0
        for sign in (-1.0, 1.0)
    )
    assert radii == pytest.approx((22.352, 22.606))
    assert part.CORNER_CROP_BOSS_R_MIN == pytest.approx(radii[0])
    apex, side_leg, fr_leg = part.CORNER_CROP_TRIANGLE
    # No sketch edge lies on any printed outer face.
    assert apex[0] > side[1] and apex[1] > front_rear[1]
    assert side_leg[0] > side[1] and fr_leg[1] > front_rear[1]
    for sx, sz in ((1.0, 1.0), (1.0, -1.0), (-1.0, -1.0), (-1.0, 1.0)):
        axis = (sx * part.COLUMN_X, sz * z_col)
        triangle = [
            (sx * (part.COLUMN_X + px), sz * (z_col + pz))
            for px, pz in part.CORNER_CROP_TRIANGLE
        ]
        for radius in radii:
            for a in side:
                for b in front_rear:
                    left = _flange_left_outside_barrel(
                        triangle, axis, (sx, sz), radius, a, b
                    )
                    assert left == 0, (sx, sz, radius, a, b)
    # Each web prints centred under its flange: its outer face stands at
    # most 6.947 off the axis, short of every triangle vertex.
    side_overhang = _t_flange_overhang(
        part.RAIL_W_SIDE, "side flange width", "side rail web thickness"
    )
    fr_overhang = _t_flange_overhang(
        part.RAIL_W_FR, "front rear flange width", "rail web thickness"
    )
    web_faces = [side[1] - side_overhang, front_rear[1] - fr_overhang]
    assert web_faces == pytest.approx([6.7564, 6.9469], abs=5e-5)
    assert part.CORNER_CROP_WEB_FACE_MAX == pytest.approx(max(web_faces))
    assert min(min(point) for point in part.CORNER_CROP_TRIANGLE) > max(web_faces)


def test_flange_corner_guard_requires_every_diagonal_to_end_on_its_barrel() -> None:
    support = part.CORNER_BOSS_SUPPORT
    assert support == pytest.approx(
        part.COLUMN_X + abs(part.FRONT_COLUMN_Z) + part.BOSS_DIA / 2.0 * math.sqrt(2.0)
    )
    # The old nib's plan corner, edge-broken, reached past the barrels.
    assert part.OUTER_X + part.OUTER_Z - part.EDGE_CHAMFER > support

    def extreme(sx: float, sz: float, reach_mm: float) -> tuple:
        half_m = reach_mm / 2.0 / 1000.0
        return (True, sx * half_m, 0.0, sz * half_m)

    corners = [(sx, sz) for sx in (-1.0, 1.0) for sz in (-1.0, 1.0)]
    finished = {corner: extreme(*corner, support) for corner in corners}
    assert part._corner_support_problems(finished) == []
    # Every corner, against the same all-barrel positive control: a nib or a
    # failed native query at any one diagonal is named, and only that one.
    for corner in corners:
        prefix = "(" + ", ".join("+1" if sign > 0.0 else "-1" for sign in corner) + ")"
        nib = dict(finished)
        nib[corner] = extreme(*corner, 343.5125)
        assert part._corner_support_problems(nib) == [
            f"{prefix}: reaches 343.5125 mm, the boss barrel {support:.4f} mm"
        ]
        failed = dict(finished)
        failed[corner] = (False, 0.0, 0.0, 0.0)
        assert part._corner_support_problems(failed) == [
            f"{prefix}: GetExtremePoint failed"
        ]
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build("):]
    assert body.count("_assert_flange_corners_cropped(adapter)") == 1
    assert (
        body.index('"HangerPinHole3Dia",\n    ):\n        set_dimension_bilateral_tolerance(')
        < body.index("_assert_flange_corners_cropped(adapter)")
        < body.index("save_part_and_images(")
    )


def test_crossbar_t_keeps_the_hanger_holes_in_the_full_depth_junctions() -> None:
    # The T stops short of the gusset legs, leaving a full-depth bar side
    # long enough to take its own printed-worst break; the web is centred on
    # the knife line and every hanger hole stays beyond the pocket ends.
    assert part.INNER_Z - part.GUSSET - part.BAR_POCKET_Z > 2.0 * part.EDGE_BREAK_PRINTED_MAX
    assert (part.BAR_WEB_X0 + part.BAR_WEB_X1) / 2.0 == part.HANGER_X
    assert part.BAR_WEB_X1 - part.BAR_WEB_X0 == pytest.approx(part.WEB_T)
    assert part.BAR_X0 < part.BAR_WEB_X0 - part.ROOT_FILLET_R
    assert part.BAR_WEB_X1 + part.ROOT_FILLET_R < part.BAR_X1
    band = spec.PRINTED_LINEAR_BAND_MM[1]
    pocket_end = part.BAR_POCKET_Z + 2.0 * band
    for station in (part.STUD_Z_FRONT, part.STUD_Z_REAR):
        largest_hole_r = spec.HANGER_CLEARANCE_DIA_MAX / 2.0
        wall = abs(station) - band - largest_hole_r - pocket_end
        assert wall >= 2.032
    assert min(part.BAR_POCKET_HOLE_WALLS.values()) >= 2.032


def _t_flange_shelf(width: float, width_label: str, web_label: str) -> float:
    """A T flange underside's flat at the printed limits: its least printed
    overhang less the largest printed root radius."""
    band = spec.PRINTED_LINEAR_BAND_MM
    root_places = spec.DRAWING_REFERENCE_PRECISION["T rail root radius"]
    root_max = part._printed_nominal(part.ROOT_FILLET_R, root_places) + band[root_places]
    return _t_flange_overhang(width, width_label, web_label) - root_max


def test_t_flange_underside_breaks_need_a_printed_shelf() -> None:
    # Each web prints centred under its flange. Every printed flat, the
    # crossbar's 2.565 among them, holds the printed worst leg and the
    # sliver land, so every T flange underside keeps its break.
    expected = {
        "side rail": _t_flange_shelf(
            part.RAIL_W_SIDE, "side flange width", "side rail web thickness"
        ),
        "front/rear rail": _t_flange_shelf(
            part.RAIL_W_FR, "front rear flange width", "rail web thickness"
        ),
        "crossbar": _t_flange_shelf(
            part.BAR_X1 - part.BAR_X0,
            "crossbar flange width",
            "crossbar web thickness",
        ),
    }
    assert expected == pytest.approx(
        {"side rail": 7.1628, "front/rear rail": 9.0551, "crossbar": 2.5654}
    )
    assert part.T_FLANGE_SHELF_PRINTED_MIN == pytest.approx(expected)
    needed = part.EDGE_BREAK_PRINTED_MAX + part.EDGE_BREAK_SLIVER_MIN
    assert needed == pytest.approx(1.8272)
    assert needed <= min(expected.values())
    points = _external_break_points()
    for x_bar in (part.BAR_X0, part.BAR_X1):
        assert [x_bar, part.FLANGE_BOT_Y, 0.0] in points
    # Every rail flange underside keeps its break: the west outer and window
    # runs, both front/rear outer runs, and the hub side's runs either side
    # of the rib.
    rib_lo = part.GOOSENECK_Z - part.HUB_RIB_W / 2.0
    z_col = abs(part.FRONT_COLUMN_Z)
    for point in (
        [part.OUTER_X, part.FLANGE_BOT_Y, 0.0],
        [part.INNER_X, part.FLANGE_BOT_Y, 0.0],
        [0.0, part.FLANGE_BOT_Y, part.OUTER_Z],
        [0.0, part.FLANGE_BOT_Y, -part.OUTER_Z],
        [
            -part.OUTER_X,
            part.FLANGE_BOT_Y,
            (-(z_col - part.CORNER_SIDE_CUT) + rib_lo) / 2.0,
        ],
        [-part.INNER_X, part.FLANGE_BOT_Y, (-part.INNER_Z + rib_lo) / 2.0],
    ):
        assert point in points


def test_a_crossbar_shelf_too_narrow_for_the_break_stays_sharp(monkeypatch) -> None:
    # A printed flat short of one leg and the sliver drops the crossbar
    # flange's two underside edges from its chain, and their four meetings
    # with the pocket ends' vertical corners; every other chain is unchanged.
    narrow = part.EDGE_BREAK_PRINTED_MAX + part.EDGE_BREAK_SLIVER_MIN - 0.01
    monkeypatch.setattr(
        part,
        "T_FLANGE_SHELF_PRINTED_MIN",
        {**part.T_FLANGE_SHELF_PRINTED_MIN, "crossbar": narrow},
    )
    groups, _clearance = part._external_edge_breaks()
    picks, removal, shared = groups["CrossbarBreaks"]
    base_picks, base_removal, base_shared = part.EXTERNAL_EDGE_BREAKS["CrossbarBreaks"]
    for x_bar in (part.BAR_X0, part.BAR_X1):
        assert [x_bar, part.FLANGE_BOT_Y, 0.0] not in picks
    assert picks == [point for point in base_picks if point[1] != part.FLANGE_BOT_Y]
    assert len(picks) == len(base_picks) - 2
    assert removal == pytest.approx(
        base_removal - 2.0 * 0.5 * part.EDGE_CHAMFER**2 * 2.0 * part.BAR_POCKET_Z
    )
    assert shared == base_shared - 4
    assert list(groups) == list(part.EXTERNAL_EDGE_BREAKS)
    for name, chain in part.EXTERNAL_EDGE_BREAKS.items():
        if name != "CrossbarBreaks":
            assert groups[name] == chain, name


def test_knife_seat_footprints_cover_every_printed_extreme() -> None:
    # Each print-worst hull holds the nominal block and reaches at least the
    # unskewed stack: D's location band, half the dowel slip and the worse
    # row-to-face reach.
    import sm_knife_mount_spec as mount
    import sm_vn_knife_mount_dowel_spec as dowel

    reach = max(
        mount.HOLE_ROW_FACE_DISTANCE + mount.HOLE_ROW_FACE_TOL,
        mount.SUPPORT_Z_THICK
        + mount.BLOCK_SIZE_TOL
        - (mount.HOLE_ROW_FACE_DISTANCE - mount.HOLE_ROW_FACE_TOL),
    )
    slip = dowel.SLIP_CLEARANCE_MAX / 2.0
    for mount_name, station, z_label in (
        ("front", part.STUD_Z_FRONT, "front hanger z from upper sockets"),
        ("rear", part.STUD_Z_REAR, "rear hanger z from upper sockets"),
    ):
        band = spec.PRINTED_LINEAR_BAND_MM[spec.DRAWING_REFERENCE_PRECISION[z_label]]
        hull = part.KNIFE_SEAT_FOOTPRINTS[mount_name]
        nominal = [
            (
                part.HANGER_X + sx * mount.BLK_HALF_X,
                station + sz * mount.SUPPORT_Z_THICK / 2.0,
            )
            for sx in (-1.0, 1.0)
            for sz in (-1.0, 1.0)
        ]
        assert part._plan_gap(hull, nominal) == 0.0
        zs = [abs(z) for _x, z in hull]
        assert min(zs) <= abs(station) - band - slip - reach
        assert max(zs) >= abs(station) + band + slip + reach


def test_knife_seat_footprint_charges_axis_centring_from_d(monkeypatch) -> None:
    original = part._knife_seat_footprint(
        part.STUD_Z_FRONT, "front hanger z from upper sockets"
    )
    monkeypatch.setattr(
        part, "HANGER_CROSSBAR_CENTER_TOL", spec.HANGER_CROSSBAR_CENTER_TOL + 0.01
    )
    expanded = part._knife_seat_footprint(
        part.STUD_Z_FRONT, "front hanger z from upper sockets"
    )
    assert min(x for x, _z in expanded) == pytest.approx(
        min(x for x, _z in original) - 0.01
    )
    assert max(x for x, _z in expanded) == pytest.approx(
        max(x for x, _z in original) + 0.01
    )


def test_knife_seat_footprints_cover_both_ways_round() -> None:
    """codjiflo (PR #1978): the knife mount fits either way round, its round
    hole (datum B) on the +X pin or turned 180 deg onto the -X pin, whose
    station band adds the -X ream's zone radius.  Round 2: the pin's
    envelope is the same across the dowel line, where the +X ream's .XXX
    "SAME Z" station is an implied zero (plus, on the -X pin, the zone
    radius), each with the round hole's slip.  Each hull holds both blocks'
    unturned print-worst corners at the along- and across-line extremes,
    and the edge-break check certifies those hulls."""
    import sm_knife_mount_spec as mount
    import sm_vn_knife_mount_dowel_spec as dowel

    slip = dowel.SLIP_CLEARANCE_MAX / 2.0
    hanger_band = (
        spec.PRINTED_LINEAR_BAND_MM[spec.DRAWING_REFERENCE_PRECISION["hanger x from left sockets"]]
        + spec.HANGER_CROSSBAR_CENTER_TOL
        + slip
    )
    side = mount.PIN_HOLE_SIDE_DISTANCE + mount.PIN_HOLE_SIDE_TOL
    width = 2.0 * mount.BLK_HALF_X + mount.BLOCK_SIZE_TOL
    reach = max(
        mount.HOLE_ROW_FACE_DISTANCE + mount.HOLE_ROW_FACE_TOL,
        mount.SUPPORT_Z_THICK + mount.BLOCK_SIZE_TOL
        - (mount.HOLE_ROW_FACE_DISTANCE - mount.HOLE_ROW_FACE_TOL),
    )
    for mount_name, station, z_label in (
        ("front", part.STUD_Z_FRONT, "front hanger z from upper sockets"),
        ("rear", part.STUD_Z_REAR, "rear hanger z from upper sockets"),
    ):
        hull = part.KNIFE_SEAT_FOOTPRINTS[mount_name]
        xs = [x for x, _z in hull]
        zs = [z for _x, z in hull]
        station_band = spec.PRINTED_LINEAR_BAND_MM[spec.DRAWING_REFERENCE_PRECISION[z_label]] + slip
        # The +X face (side off the round hole) reaches +X on the +X pin and
        # -X, past the -X pin's wider band, turned onto it.
        plus = spec.PIN_HOLE_X + hanger_band + spec.HANGER_PIN_X_TOL + side
        minus = spec.PIN_HOLE_NEG_X - hanger_band - spec.HANGER_NEG_PIN_X_TOL - side
        assert max(xs) >= plus - 1e-9, mount_name
        assert min(xs) <= minus + 1e-9, mount_name
        # Across the line the -X pin's wider envelope binds both sides.
        across = station_band + spec.HANGER_NEG_PIN_X_TOL + reach
        assert max(zs) >= station + across - 1e-9, mount_name
        assert min(zs) <= station - across + 1e-9, mount_name
        # Both blocks' corners, unturned, at every along/across extreme.
        for sx, pin, band in (
            (1.0, spec.PIN_HOLE_X, spec.HANGER_PIN_X_TOL),
            (-1.0, spec.PIN_HOLE_NEG_X, spec.HANGER_NEG_PIN_X_TOL),
        ):
            corners = [
                (pin + dx + sx * u, station + dz + sx * v)
                for dx in (-(hanger_band + band), hanger_band + band)
                for dz in (-(station_band + band), station_band + band)
                for u in (side, side - width)
                for v in (-reach, reach)
            ]
            assert part._plan_gap(hull, corners) == 0.0, (mount_name, sx)
    # The seat's edge-break clearance is certified on the union, in code.
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "(PIN_HOLE_NEG_X, HANGER_NEG_PIN_X_TOL, -1.0)," in source
    assert "for mount, footprint in KNIFE_SEAT_FOOTPRINTS.items():" in source
    assert min(part.KNIFE_SEAT_EDGE_BREAK_CLEARANCE.values()) >= 0.5


def test_edge_breaks_stay_clear_of_both_print_worst_knife_seats() -> None:
    # Every finished underside break band keeps 0.5 off both seats; the
    # pocket ends bind the front seat.  Every gusset hypotenuse beyond the
    # pockets is an edge a break would put under a seat; the rear bar sides
    # stop short of the rear seat.
    _groups, clearance = part._external_edge_breaks()
    assert clearance == part.KNIFE_SEAT_EDGE_BREAK_CLEARANCE
    assert min(clearance.values()) >= part.KNIFE_SEAT_EDGE_BREAK_MIN_CLEARANCE == 0.5
    dz = abs(part.FRONT_COLUMN_Z) - 112.0
    assert clearance == pytest.approx(
        {"front": 4.8497153757757445, "rear": 6.670090936628824 - dz}
    )
    # The printed worst leg, .063 + .005, never the model's 1.6002.
    assert part.EDGE_BREAK_PRINTED == pytest.approx(1.6002)
    assert part.EDGE_BREAK_PRINTED_MAX == pytest.approx(1.7272)
    reach = part.EDGE_BREAK_PRINTED_MAX + part._EDGE_LOCATION_BAND
    gusset_z = part.INNER_Z - part.GUSSET
    rear = part.KNIFE_SEAT_FOOTPRINTS["rear"]
    for x_bar, inward in ((part.BAR_X0, 1.0), (part.BAR_X1, -1.0)):
        bar_side_band = [
            (x_bar - inward * part._EDGE_LOCATION_BAND, part.BAR_POCKET_Z),
            (x_bar + inward * reach, part.BAR_POCKET_Z),
            (x_bar + inward * reach, gusset_z),
            (x_bar - inward * part._EDGE_LOCATION_BAND, gusset_z),
        ]
        assert part._plan_gap(bar_side_band, rear) >= 0.5
    front = part.KNIFE_SEAT_FOOTPRINTS["front"]
    hypotenuse_band = [
        (part.BAR_X0, -gusset_z),
        (part.BAR_X0 - part.GUSSET, -part.INNER_Z),
        (part.BAR_X0 - part.GUSSET + reach * math.sqrt(2.0), -part.INNER_Z),
        (part.BAR_X0 + reach * math.sqrt(2.0), -gusset_z),
    ]
    assert part._plan_gap(hypotenuse_band, front) < 0.5


def test_edge_break_picks_are_convex_and_the_gusset_junctions_are_not() -> None:
    # The solid-angle probe reads the plan's turns: the bar-side to gusset
    # junction is re-entrant, a pocket-end outer corner and a bar-side
    # bottom are right-angled and convex.
    gusset_z = part.INNER_Z - part.GUSSET
    for x_bar in (part.BAR_X0, part.BAR_X1):
        for sz in (-1.0, 1.0):
            assert (
                part._interior_angle((x_bar, 0.0, sz * gusset_z), (0.0, 1.0, 0.0))
                == 225.0
            )
            assert (
                part._interior_angle(
                    (x_bar, -part.HALF_H / 2.0, sz * part.BAR_POCKET_Z), (0.0, 1.0, 0.0)
                )
                == 90.0
            )
    for x, y, z in _external_break_points():
        assert not (abs(abs(z) - gusset_z) < 1e-9 and x in (part.BAR_X0, part.BAR_X1))


def _external_break_points() -> list[list[float]]:
    return [
        point for picks, _, _ in part.EXTERNAL_EDGE_BREAKS.values() for point in picks
    ]


def test_edge_breaks_split_into_connected_chains_in_build_order() -> None:
    groups, _clearance = part._external_edge_breaks()
    assert groups == part.EXTERNAL_EDGE_BREAKS
    # Derived from the eligible breaks: the crossbar T flange's underside and
    # the hub rib's outer bottom either side of the set-screw boss hold their
    # breaks at the printed limits, so the boss's breaks join the rib's.
    expected = {
        "RailRunBreaks": (7, 2559.3989899243807, 0),
        "CrossbarBreaks": (14, 897.2953857927357, 16),
        "WestWindowBreaks": (11, 1158.0376844270322, 12),
        "HubRailBreaks": (36, 1931.8704600617032, 42),
        "BossRimBreaks": (9, 1528.59268233898, 0),
    }
    assert list(groups) == list(expected)
    for feature, (picks, removal, shared) in groups.items():
        count, volume, meetings = expected[feature]
        assert (len(picks), shared) == (count, meetings), feature
        assert removal == pytest.approx(volume, rel=2e-4), feature
    # The boss rims are closed circles and the rail runs die into boss
    # barrels at both ends: neither shares a vertex.
    assert groups["RailRunBreaks"][2] == groups["BossRimBreaks"][2] == 0
    # Each rib-side bottom ends on the web face, at its web bottom's end, in
    # the same feature.
    hub = groups["HubRailBreaks"][0]
    rib_lo = part.GOOSENECK_Z - part.HUB_RIB_W / 2.0
    rib_hi = part.GOOSENECK_Z + part.HUB_RIB_W / 2.0
    for z_rib in (rib_lo, rib_hi):
        assert [(-part.OUTER_X - part.WEB_OUT_X) / 2.0, -part.HALF_H, z_rib] in hub
    # The crossbar: two web bottoms, two flange underside edges, four
    # pocket-end bottoms, four full-depth vertical corners and two rear side
    # bottoms, meeting at the pocket ends' corners.
    half_c2 = 0.5 * part.EDGE_CHAMFER**2
    full_depth = part.HALF_H + part.FLANGE_BOT_Y
    bar_lengths = (
        2.0 * 2.0 * part.BAR_POCKET_Z
        + 2.0 * 2.0 * part.BAR_POCKET_Z
        + 2.0 * (part.BAR_WEB_X0 - part.BAR_X0 + part.BAR_X1 - part.BAR_WEB_X1)
        + 4.0 * full_depth
        + 2.0 * (part.INNER_Z - part.GUSSET - part.BAR_POCKET_Z)
    )
    assert groups["CrossbarBreaks"][1] == pytest.approx(half_c2 * bar_lengths)


def test_hub_rib_stubs_beside_the_set_boss_take_their_breaks(monkeypatch) -> None:
    # Either side of the set-screw boss the rib's outer bottom runs 4.953
    # nominal and 4.699 at the printed limits (the narrowest rib less the
    # widest boss, halved): over the 3.454 that printed worst legs at both
    # its ends take, so it is broken and joins the boss's breaks to the rib's.
    band = spec.PRINTED_LINEAR_BAND_MM
    rib_places = spec.DRAWING_PRECISION["RibProfile"]["RibWidth"]
    boss_places = spec.DRAWING_PRECISION["SetBossProfile"]["SetBossWidth"]
    stub = (
        part._printed_nominal(part.HUB_RIB_W, rib_places)
        - band[rib_places]
        - part._printed_nominal(part.HUB_SET_BOSS_W, boss_places)
        - band[boss_places]
    ) / 2.0
    nominal = (part.HUB_RIB_W - part.HUB_SET_BOSS_W) / 2.0
    assert (nominal, stub) == pytest.approx((4.953, 4.699))
    assert part.HUB_RIB_STUB_PRINTED_MIN == pytest.approx(stub)
    assert nominal > stub > 2.0 * part.EDGE_BREAK_PRINTED_MAX
    # A stub too short for both legs would stay sharp, leaving the boss's
    # breaks a chain of their own: two vertical corners, two face runs and
    # four side runs back to the rib, three meeting at each face corner.
    monkeypatch.setattr(
        part, "HUB_RIB_STUB_PRINTED_MIN", 2.0 * part.EDGE_BREAK_PRINTED_MAX - 0.01
    )
    groups, _clearance = part._external_edge_breaks()
    base = part.EXTERNAL_EDGE_BREAKS
    assert list(groups) == [
        "RailRunBreaks",
        "CrossbarBreaks",
        "WestWindowBreaks",
        "HubRailBreaks",
        "HubSetBossBreaks",
        "BossRimBreaks",
    ]
    for name in base:
        if name != "HubRailBreaks":
            assert groups[name] == base[name], name
    rib_lo = part.GOOSENECK_Z - part.HUB_RIB_W / 2.0
    rib_hi = part.GOOSENECK_Z + part.HUB_RIB_W / 2.0
    boss_lo = part.GOOSENECK_Z - part.HUB_SET_BOSS_W / 2.0
    boss_hi = part.GOOSENECK_Z + part.HUB_SET_BOSS_W / 2.0
    stubs = [
        [-part.OUTER_X, -part.HALF_H, (rib_lo + boss_lo) / 2.0],
        [-part.OUTER_X, -part.HALF_H, (boss_hi + rib_hi) / 2.0],
    ]
    hub, removal, shared = groups["HubRailBreaks"]
    boss_picks, boss_removal, boss_shared = groups["HubSetBossBreaks"]
    assert base["HubRailBreaks"][0] == hub + stubs + boss_picks
    stubs_removal = 0.5 * part.EDGE_CHAMFER**2 * 2.0 * nominal
    assert base["HubRailBreaks"][1] == pytest.approx(
        removal + stubs_removal + boss_removal
    )
    assert base["HubRailBreaks"][2] == shared + boss_shared + 6
    full_depth = part.HALF_H + part.FLANGE_BOT_Y
    boss_lengths = (
        2.0 * full_depth
        + 2.0 * part.HUB_SET_BOSS_W
        + 4.0 * (-part.OUTER_X - part.SET_BOSS_FACE_X)
    )
    assert boss_removal == pytest.approx(0.5 * part.EDGE_CHAMFER**2 * boss_lengths)
    assert all(x <= -part.OUTER_X for x, _y, _z in boss_picks)


def test_edge_break_chains_leave_no_sliver_between_features(monkeypatch) -> None:
    assert part._segment_gap((0, 0, 0), (1, 0, 0), (1, 0, 0), (1, 1, 0)) == 0.0
    assert part._segment_gap((0, 0, 0), (2, 0, 0), (1, 1, 1), (1, 1, 3)) == (
        pytest.approx(math.sqrt(2.0))
    )
    assert part._segment_gap((0, 0, 0), (1, 0, 0), (3, 0, 0), (4, 0, 0)) == 2.0
    # The nearest two breaks that do not meet stand 4.953 apart, two printed
    # worst legs and a 1.499 land: the hub rail's outer flange underside run
    # and the set-screw boss's top side run beside it; demanding a land over
    # 1.499 trips the guard there.
    assert 2.0 * part.EDGE_BREAK_PRINTED_MAX + part.EDGE_BREAK_SLIVER_MIN == (
        pytest.approx(3.5544)
    )
    monkeypatch.setattr(part, "EDGE_BREAK_SLIVER_MIN", 1.49)
    part._external_edge_breaks()
    monkeypatch.setattr(part, "EDGE_BREAK_SLIVER_MIN", 1.50)
    with pytest.raises(AssertionError, match=r"stop 4\.953 mm apart.*sliver"):
        part._external_edge_breaks()


def test_hub_boss_chord_stays_inside_the_web_at_the_rib_sides() -> None:
    def margin(rib_w: float) -> float:
        chord = math.sqrt(max((part.HUB_BOSS_DIA / 2.0) ** 2 - (rib_w / 2.0) ** 2, 0.0))
        return part.WEB_T / 2.0 - chord

    assert part.HUB_BOSS_RIB_CHORD_MARGIN == pytest.approx(margin(part.HUB_RIB_W))
    assert part.HUB_BOSS_RIB_CHORD_MARGIN >= part.HUB_BOSS_RIB_CHORD_MIN_MARGIN == 0.5
    # The old 27-wide rib let the boss poke 0.038 past the web there.
    assert margin(27.0) < 0.0


def test_external_edge_breaks_select_distinct_edges_and_skip_the_noted_ones() -> None:
    points = _external_break_points()
    assert len(points) == 77
    assert len({tuple(round(value, 6) for value in point) for point in points}) == len(
        points
    )
    # No two picks share an edge's 0.5 mm selection radius.
    for i, a in enumerate(points):
        for b in points[i + 1 :]:
            assert math.dist(a, b) > 0.5
    # Picked: the rear full-depth bar-side bottoms.
    for x_bar in (part.BAR_X0, part.BAR_X1):
        assert [
            x_bar, -part.HALF_H, (part.BAR_POCKET_Z + part.INNER_Z - part.GUSSET) / 2.0
        ] in points
    # Picked: the crossbar T flange's underside edges on their 2.565 printed
    # shelf and the hub rib's outer bottom either side of the set-screw boss.
    for x_bar in (part.BAR_X0, part.BAR_X1):
        assert [x_bar, part.FLANGE_BOT_Y, 0.0] in points
    # Sharp: the front bar-side bottoms, every gusset hypotenuse bottom beyond
    # the pockets and the hub rib's inner bottom edge: none is picked.
    rib_lo = part.GOOSENECK_Z - part.HUB_RIB_W / 2.0
    rib_hi = part.GOOSENECK_Z + part.HUB_RIB_W / 2.0
    for x, y, z in points:
        assert not (y == -part.HALF_H and x == -part.INNER_X and rib_lo < z < rib_hi)
        if y == -part.HALF_H and part.BAR_POCKET_Z < abs(z) < part.INNER_Z:
            if z > 0.0 and x in (part.BAR_X0, part.BAR_X1):
                continue  # a rear bar-side bottom
            # No front bar-side bottom; no hypotenuse bottom (x off the bar).
            assert not part.BAR_X0 - part.GUSSET <= x <= part.BAR_X0
            assert not part.BAR_X1 <= x <= part.BAR_X1 + part.GUSSET


def test_keeper_tap_holds_stock_screw_above_a_plug_tap_lead() -> None:
    major, length, _, _, pitch = FILLISTER_SIZE
    tap_spec = part.KEEPER_TAP_SPEC
    full_thread = tap_spec.overrides_mm["ThreadDepth"]
    depth_tolerance = spec.PRINTED_LINEAR_BAND_MM[
        spec.KEEPER_TAP_CALLOUT_PRECISION["hw-threaddepth"]
    ]
    foot_places = keeper.DRAWING_PRECISION["FootProfile"]["FootRise"]
    cb_places = keeper.FOOT_COUNTERBORE_DEPTH_PLACES
    # The keeper's foot and counterbore print on its own sheet's unit.
    minimum_entry = length - (
        part._keeper_printed(keeper.FOOT_H, foot_places, 1.0)
        - part._keeper_printed(keeper.CBORE_DEPTH_MM, cb_places, -1.0)
    )
    maximum_entry = length - (
        part._keeper_printed(keeper.FOOT_H, foot_places, -1.0)
        - part._keeper_printed(keeper.CBORE_DEPTH_MM, cb_places, 1.0)
    )
    assert tap_spec is keeper.KEEPER_TAP_SPEC
    assert tap_spec.size == keeper_screw.THREAD == "#2-56"
    assert full_thread == keeper.KEEPER_TAP_THREAD_DEPTH_MM == 7.6
    assert minimum_entry >= 1.5 * major
    assert maximum_entry == pytest.approx(6.5325)
    assert part.KEEPER_MAX_STOCK_ENTRY == pytest.approx(maximum_entry)
    thread_places = spec.KEEPER_TAP_CALLOUT_PRECISION["hw-threaddepth"]
    reserve = spec.printed_limit(full_thread, thread_places, -1.0) - maximum_entry
    assert reserve == pytest.approx(part.KEEPER_MIN_THREAD_TIP_RESERVE)
    assert reserve == pytest.approx(0.9351)
    assert reserve >= 0.25
    assert tap_spec.depth_mm - full_thread - 2.0 * depth_tolerance >= 5.0 * pitch
    drill_point = part.TAP_DRILL_MM[tap_spec.size] / 2.0 * part.DRILL_POINT_H
    assert tap_spec.depth_mm + depth_tolerance + drill_point < part.RING_HEIGHT


def test_transferred_keeper_receiver_keeps_real_normal_wall_at_printed_bands() -> None:
    assert part.KEEPER_TAP_X == part.COLUMN_X + keeper.KEEPER_FITUP_X_FROM_WEB_MM
    assert part.KEEPER_MAX_TRANSVERSE_OFFSET == pytest.approx(0.53)
    assert part.KEEPER_MAX_WEB_CENTRE_OFFSET == pytest.approx(3.53)
    assert part.KEEPER_MIN_WEB_HALF_WIDTH == pytest.approx(6.4389)
    assert part.KEEPER_MIN_ROOT_RADIUS == pytest.approx(2.794)
    assert part.KEEPER_MIN_FLANGE_THICKNESS == pytest.approx(7.874)
    assert part.KEEPER_MAX_FULL_THREAD_DEPTH == pytest.approx(7.7216)
    assert part.KEEPER_TAP_THREAD_WALL_MARGIN_NO_WANDER == pytest.approx(
        2.6777298407359256
    )
    assert part.KEEPER_TAP_DRILL_WALL_MARGIN_NO_WANDER == pytest.approx(1.9691)
    assert part.KEEPER_TAP_THREAD_WALL_MARGIN == pytest.approx(2.6168179913276948)
    assert part.KEEPER_TAP_DRILL_WALL_MARGIN == pytest.approx(1.9081881505917684)
    assert (
        min(part.KEEPER_TAP_THREAD_WALL_MARGIN, part.KEEPER_TAP_DRILL_WALL_MARGIN)
        >= 1.524
    )
    # Independently sample the actual quarter-circle surface. The threaded
    # cylinder's deepest/outboard corner, not its horizontal section, is
    # nearest this concave surface. All other thread points are farther in.
    corner_x = (
        part.KEEPER_MAX_WEB_CENTRE_OFFSET
        + max(
            part.THREAD_MAJOR_MM[part.KEEPER_TAP_SPEC.size],
            FILLISTER_SIZE[0],
        )
        / 2.0
    )
    corner_depth = part.KEEPER_MAX_FULL_THREAD_DEPTH
    radius = part.KEEPER_MIN_ROOT_RADIUS
    centre_x = part.KEEPER_MIN_WEB_HALF_WIDTH + radius
    centre_depth = part.KEEPER_MIN_FLANGE_THICKNESS + radius
    sampled = min(
        math.hypot(
            centre_x - radius * math.cos(index * math.pi / 8192.0) - corner_x,
            centre_depth - radius * math.sin(index * math.pi / 8192.0) - corner_depth,
        )
        for index in range(4097)
    )
    assert sampled == pytest.approx(
        part.KEEPER_TAP_THREAD_WALL_MARGIN_NO_WANDER, abs=1e-6
    )
    # The cylindrical pilot extends below the root and therefore reaches
    # the bare-web wall. Its .070 diameter also carries DRILLED HOLES +.004.
    assert part.KEEPER_MAX_TAP_DRILL_RADIUS == pytest.approx(0.9398)
    assert (
        part.KEEPER_MIN_WEB_HALF_WIDTH
        - part.KEEPER_MAX_WEB_CENTRE_OFFSET
        - part.KEEPER_MAX_TAP_DRILL_RADIUS
    ) == pytest.approx(part.KEEPER_TAP_DRILL_WALL_MARGIN_NO_WANDER)


def _printed_receiver_stack():
    """Independently reconstruct the worst printed root, transferred axis,
    full-thread corner and .3 degree full-depth wander, in model mm:
    (root radius, axis offset from the web centre, thread corner offset,
    full-thread depth, full printed pilot depth, wander, pilot radius).
    The keeper's own dimensions print on its sheet's unit."""
    root_places = spec.DRAWING_REFERENCE_PRECISION["T rail root radius"]
    root_radius = spec.printed_limit(part.ROOT_FILLET_R, root_places, -1.0)
    foot_places = keeper.DRAWING_PRECISION["Foot"]["Depth"]
    station_places = keeper.DRAWING_PRECISION["FootScrewSideReference"]["ScrewFromSide"]
    transverse_offset = max(
        abs(
            part._keeper_printed(keeper.SCREW_FROM_SIDE, station_places, station_direction)
            - part._keeper_printed(keeper.KEEPER_WIDTH, foot_places, foot_direction)
            / 2.0
        )
        for station_direction in (-1.0, 1.0)
        for foot_direction in (-1.0, 1.0)
    )
    axis_offset = (
        abs(
            part._keeper_printed(
                keeper.KEEPER_FITUP_X_FROM_WEB_MM, keeper.KEEPER_FITUP_PLACES
            )
        )
        + keeper.KEEPER_FITUP_X_BAND_MM
        + transverse_offset
    )
    thread_places = spec.KEEPER_TAP_CALLOUT_PRECISION["hw-threaddepth"]
    thread_depth = spec.printed_limit(
        keeper.KEEPER_TAP_SPEC.overrides_mm["ThreadDepth"], thread_places, 1.0
    )
    drill_places = spec.KEEPER_TAP_CALLOUT_PRECISION["hw-tapdrldepth"]
    cylinder_depth = spec.printed_limit(
        keeper.KEEPER_TAP_SPEC.depth_mm, drill_places, 1.0
    )
    assert cylinder_depth == pytest.approx(11.6332)
    assert spec.KEEPER_TAP_DRILL_WANDER_DEG == 0.3
    displacement = cylinder_depth * math.tan(math.radians(0.3))
    assert displacement == pytest.approx(0.060911849408230724)
    assert part.KEEPER_MAX_TAP_DRILL_DEPTH == pytest.approx(cylinder_depth)
    assert part.KEEPER_TAP_AXIS_WANDER_MM == pytest.approx(displacement)

    major_radius = (
        max(
            part.THREAD_MAJOR_MM[keeper.KEEPER_TAP_SPEC.size],
            FILLISTER_SIZE[0],
        )
        / 2.0
    )
    assert 2.0 * major_radius == pytest.approx(2.1844)
    diameter_places = spec.KEEPER_TAP_CALLOUT_PRECISION["hw-tapdrldia"]
    drilled_band = spec.PRINTED_DRILLED_HOLE_PLUS_MM
    assert drilled_band == pytest.approx(0.1016)
    pilot_radius = (
        part._printed_nominal(
            part.TAP_DRILL_MM[keeper.KEEPER_TAP_SPEC.size], diameter_places
        )
        + drilled_band
    ) / 2.0
    assert pilot_radius == pytest.approx(0.9398)
    return (
        root_radius,
        axis_offset,
        axis_offset + major_radius,
        thread_depth,
        cylinder_depth,
        displacement,
        pilot_radius,
    )


def _printed_web_half_width(web_thickness: float) -> float:
    web_places = spec.DRAWING_REFERENCE_PRECISION["side rail web thickness"]
    return spec.printed_limit(web_thickness, web_places, -1.0) / 2.0


def _worst_thread_wall(half_width, root_radius, flange_depth, corner_x, depth, wander):
    """Shortest normal distance from the full-thread corner to the T-root
    boundary -- the quarter-circle root and, below its centre, the bare web
    face -- less the full-depth wander, which may move the corner straight
    toward the nearest boundary point."""
    centre_x = half_width + root_radius
    centre_depth = flange_depth + root_radius
    arc = min(
        math.hypot(
            centre_x - root_radius * math.cos(index * math.pi / 8192.0) - corner_x,
            centre_depth - root_radius * math.sin(index * math.pi / 8192.0) - depth,
        )
        for index in range(4097)
    )
    web = half_width - corner_x if depth >= centre_depth else math.inf
    return min(arc, web) - wander


def test_printed_typ_top_flange_minimum_keeps_the_receiver_wall() -> None:
    """Facing may lower the keeper-rail top; only a directly printed FINAL
    flange that covers it bounds what the receiver's T-root keeps at the
    worst case.  H-H prints the top flange TYP, so its minimum binds the
    faced keeper rail too, with no second facing allowance."""
    top_places = spec.DRAWING_REFERENCE_PRECISION["top flange thickness"]
    assert top_places == spec.FLANGE_THICKNESS_PLACES
    assert spec.FLANGE_THICKNESS_MM == part.FLANGE == pytest.approx(8.001)  # .315
    flange_depth = spec.printed_limit(spec.FLANGE_THICKNESS_MM, top_places, -1.0)
    assert flange_depth == pytest.approx(7.874)
    # The very minimum the part's receiver-wall guard is built on.
    assert flange_depth == pytest.approx(part.KEEPER_MIN_FLANGE_THICKNESS)
    (
        root_radius,
        axis_offset,
        corner_x,
        thread_depth,
        cylinder_depth,
        displacement,
        pilot_radius,
    ) = _printed_receiver_stack()
    half_width = _printed_web_half_width(part.WEB_T)
    assert half_width == pytest.approx(part.KEEPER_MIN_WEB_HALF_WIDTH)
    thread_wall = _worst_thread_wall(
        half_width, root_radius, flange_depth, corner_x, thread_depth, displacement
    )
    # The pilot reaches the bare web below the root whatever the flange.
    assert cylinder_depth > flange_depth + root_radius
    pilot_wall = half_width - (axis_offset + displacement + pilot_radius)
    assert thread_wall == pytest.approx(part.KEEPER_TAP_THREAD_WALL_MARGIN, abs=1e-6)
    assert pilot_wall == pytest.approx(part.KEEPER_TAP_DRILL_WALL_MARGIN)
    # Owner ruling B7: the pilot wall stays the accepted shortfall under the
    # .080 target; the .060 floor binds.
    assert min(thread_wall, pilot_wall) >= 1.524


def test_every_imported_drawing_dimension_has_part_authored_places() -> None:
    # drawing-simplicity-policy.md `How the repository implements the guidelines`: the part owns the decimal places, so a kept model dimension
    # nobody authored places for prints SolidWorks' template default and the
    # sheet has nowhere left to say otherwise.
    kept = set().union(
        drawing.GEOMETRY_TOP_KEEP,
        drawing.GEOMETRY_FRONT_KEEP,
        drawing.DETAIL_TOP_KEEP,
        drawing.DETAIL_FRONT_KEEP,
        drawing.DETAIL_SECTION_KEEP,
        drawing.HUB_TOP_KEEP,
        drawing.HUB_LEFT_KEEP,
        drawing.HUB_BOTTOM_KEEP,
        drawing.HANGER_SECTION_KEEP,
    )
    assert kept, "the top-frame sheets import no model dimensions"
    assert not kept - set(spec.DRAWING_PRECISION_BY_NAME)


# --- #946 leader-over-part: RD4 -------------------------------------------
#
# The sheets are projected here from the model constants, as the build reads
# them through each view's ModelToViewTransform: the half-size plan (+X right,
# +Z down the sheet).  #946's measure: the
# run over the part from the leader's first model-edge crossing to its tip,
# minus the tip's shortest approach (its distance to the nearest side of the
# view's outline).  Main's brief is ~4 mm (swing's RD2 fix, 4dda16fd5, 3.8).
LEADER_DETOUR_TARGET = 0.004
# The frame's title block (layoutcal2-a dump: x >= 216 mm, y <= 66 mm).
TITLE_BLOCK = (0.216, 0.0, 0.4318, 0.066)
_S = drawing.DETAIL_VIEW_SCALE / 1000.0


def _plan(x: float, z: float) -> tuple[float, float]:
    cx, cy = drawing.DETAIL_TOP_CENTER
    return (cx + x * _S, cy - z * _S)


def _keeper_geometry():
    hole = _plan(part.KEEPER_TAP_X, part.KEEPER_TAP_Z_REAR)
    hole_r = part.TAP_DRILL_MM[part.KEEPER_TAP_SPEC.size] / 2.0 * _S
    boss = _plan(part.COLUMN_X, part.REAR_COLUMN_Z)
    boss_r = part.BOSS_DIA / 2.0 * _S
    return hole, hole_r, boss, boss_r


def _segment_circle_entry(start, end, centre, radius):
    """Where the segment start -> end first enters the circle, else None."""
    (x0, y0), (x1, y1) = start, end
    dx, dy = x1 - x0, y1 - y0
    fx, fy = x0 - centre[0], y0 - centre[1]
    a, b, c = dx * dx + dy * dy, 2 * (fx * dx + fy * dy), fx * fx + fy * fy - radius**2
    disc = b * b - 4 * a * c
    if disc < 0:
        return None
    t = (-b - math.sqrt(disc)) / (2 * a)
    return (x0 + t * dx, y0 + t * dy) if 0.0 <= t <= 1.0 else None


def _plan_detour(start, tip):
    """#946's detour of a plan leader reaching the right rail's keeper taps:
    it enters the part through a corner boss or the rail's outer face."""
    face_x = _plan(part.OUTER_X, 0.0)[0]
    entries = [
        _segment_circle_entry(start, tip, _plan(part.COLUMN_X, z), part.BOSS_DIA / 2.0 * _S)
        for z in (part.FRONT_COLUMN_Z, part.REAR_COLUMN_Z)
    ]
    if start[0] > face_x > tip[0]:
        t = (start[0] - face_x) / (start[0] - tip[0])
        entries.append((face_x, start[1] + t * (tip[1] - start[1])))
    entry = min((e for e in entries if e), key=lambda e: math.dist(start, e))
    left, top = _plan(-drawing.PLAN_HALF_X, -drawing.PLAN_HALF_Z)
    right, bottom = _plan(drawing.PLAN_HALF_X, drawing.PLAN_HALF_Z)
    approach = min(tip[0] - left, right - tip[0], tip[1] - bottom, top - tip[1])
    over = math.dist(entry, tip)
    return over, approach, over - approach


def _shoulder_end(callout, tip):
    left, down, right, _up = drawing.KEEPER_CALLOUT_EXTENT
    x = callout[0] - left if tip[0] < callout[0] else callout[0] + right
    return (x, callout[1] - down)


def test_keeper_callout_leader_takes_the_short_way_to_its_tap() -> None:
    """#946 / b49e1: RD4 stood above the front keeper tap's boss and its
    leader crossed the boss and bore rings: 29.6 mm over the part, 18.3 mm
    past the tap's approach.  It now reads off the rear tap from the rail's
    outer side, under REAR KEEPER Z's extension line, clear of the boss."""
    hole, hole_r, boss, boss_r = _keeper_geometry()
    callout, tip = drawing.keeper_callout_placement(hole, hole_r, boss, boss_r)
    assert math.dist(tip, hole) == pytest.approx(hole_r)
    start = _shoulder_end(callout, tip)
    over, approach, detour = _plan_detour(start, tip)
    assert detour <= LEADER_DETOUR_TARGET, (over, approach, detour)
    # The leader passes the rear boss an ink clearance off, and lands under
    # the tap's centre, so it never crosses the extension line through it.
    (x0, y0), (x1, y1) = start, tip
    run = ((boss[0] - x0) * (x1 - x0) + (boss[1] - y0) * (y1 - y0)) / math.dist(start, tip) ** 2
    t = max(0.0, min(1.0, run))
    nearest = (x0 + t * (x1 - x0), y0 + t * (y1 - y0))
    assert math.dist(nearest, boss) >= boss_r + drawing.INK_CLEARANCE
    assert tip[1] < hole[1]
    # The callout stands clear under that extension line, inside the frame
    # and off the title block.
    left, down, right, up = drawing.KEEPER_CALLOUT_EXTENT
    box = (callout[0] - left, callout[1] - down, callout[0] + right, callout[1] + up)
    assert hole[1] - box[3] >= drawing.INK_CLEARANCE + drawing.ARROW_HALF_WIDTH
    frame = drawing.SHEET_FRAME
    assert frame[0] <= box[0] and box[2] <= frame[2] - drawing.INK_CLEARANCE
    assert box[1] > TITLE_BLOCK[3]
    assert box[0] > boss[0] + boss_r


def test_b49e1_keeper_callout_is_what_ran_over_the_boss() -> None:
    """Replay b49e1's RD4, not today's transferred tap and shifted view."""
    # b49e13940aa0a3e2c22d2909b6d82f4481d13630: build_top_frame.py,
    # top_frame_spec.py and cone_pivot_post_installation.py own these model
    # coordinates; _hole_spec.py gives the old #8-32 tap drill diameter.
    column_x, column_z = 197.0, 112.0
    outer_x = column_x + 34.2 / 2.0
    boss_radius = _B49E1_BOSS_DIA / 2.0
    summing_z = 3.0875877804265315
    # draw_top_frame.py: HOLES-SOCKETS was 1:2, centred at (0.215, 0.160).
    scale = 0.5 / 1000.0

    def historical_plan(x, z):
        return (0.215 + x * scale, 0.160 - z * scale)

    front_rim = historical_plan(199.9, summing_z - 74.0 + 3.454 / 2.0)
    # Captured b49e1 native RD4 shoulder: left/down = 38.4/5.6 mm.
    # The later TRANSFER FROM / AT ASSEMBLY prefix is not part of this ink.
    start = (0.366 - 0.0384, 0.247 - 0.0056)
    entries = [
        _segment_circle_entry(
            start, front_rim, historical_plan(column_x, z), boss_radius * scale
        )
        for z in (-column_z, column_z)
    ]
    face_x = historical_plan(outer_x, 0.0)[0]
    if start[0] > face_x > front_rim[0]:
        t = (start[0] - face_x) / (start[0] - front_rim[0])
        entries.append((face_x, start[1] + t * (front_rim[1] - start[1])))
    entry = min((e for e in entries if e), key=lambda e: math.dist(start, e))
    left, top = historical_plan(-column_x - boss_radius, -column_z - boss_radius)
    right, bottom = historical_plan(column_x + boss_radius, column_z + boss_radius)
    approach = min(
        front_rim[0] - left,
        right - front_rim[0],
        front_rim[1] - bottom,
        top - front_rim[1],
    )
    detour = math.dist(entry, front_rim) - approach
    assert detour > 0.010


def test_build_places_the_keeper_leader_from_its_projected_feature() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    for placed in (
        "keeper_callout_placement(",
        "callout_xy=keeper_callout_xy,",
        "rear_keeper = (KEEPER_TAP_X, HALF_H, KEEPER_TAP_Z_REAR)",
    ):
        assert placed in body, placed


# #955 section letters.  layoutcheck's replay of b49e1 found three cutting-
# plane letters printed on ink (B 3.65 mm on the rail edge and the 183.9,
# E 0.99 on the corner boss, D 6.17 on the hub rail's inner face) and two more
# under 1 mm off it.  This is historical B/E/D calibration evidence, not
# H/K glyph measurements.  The two 1:3 plans project +X right and +Z down.
_PLAN_S = drawing.GEOMETRY_VIEW_SCALE / 1000.0
_SECTION_PLAN = {
    "B": drawing.GEOMETRY_TOP_CENTER,
    "E": drawing.GEOMETRY_TOP_CENTER,
    "D": drawing.HUB_TOP_CENTER,
}
_LETTER_ENDS = ("B-outer", "B-inner", "E-inner", "E-outer", "D-outer", "D-inner")
# b49e1's cutting-line ends, as the build then typed them, start first.
_B49E1_BOSS_DIA = 52.2
_B49E1_BAR_X1 = -4.0  # the 22-wide crossbar's +X face
_B49E1_CUT_ENDS = {
    "B": (
        (part.COLUMN_X / 2.0, abs(part.FRONT_COLUMN_Z) + _B49E1_BOSS_DIA / 2.0 + 6.0),
        (part.COLUMN_X / 2.0, part.INNER_Z - 6.0),
    ),
    "E": (
        (_B49E1_BAR_X1 + 6.0, drawing.SIDE_SECTION_Z),
        (-part.COLUMN_X - _B49E1_BOSS_DIA / 2.0 - 6.0, drawing.SIDE_SECTION_Z),
    ),
    "D": (
        (-part.COLUMN_X - _B49E1_BOSS_DIA / 2.0 - 6.0, part.GOOSENECK_Z),
        (-part.INNER_X + 5.0, part.GOOSENECK_Z),
    ),
}
# The letters' ink on the b49e1 render (mm).
_B49E1_LETTERS = {
    "B-outer": (193.21, 119.26, 196.86, 125.44),
    "B-inner": (193.21, 138.30, 196.86, 144.47),
    "E-inner": (144.18, 202.99, 147.66, 209.17),
    "E-outer": (67.14, 202.99, 70.63, 209.17),
    "D-outer": (66.28, 214.80, 71.40, 220.97),
    "D-inner": (84.34, 214.80, 89.46, 220.97),
}
# Dimension ink beside the letters, which #955 leaves where b49e1 printed it
# (mm): the "183.9" and its line, the 18.0 gusset run's text and witness
# lines, and the witness lines running off the rear-left corner boss.
_WINDOW_WIDTH_TEXT = (184.84, 116.16, 195.52, 119.72)
_WINDOW_WIDTH_LINE = ((143.67, 115.22), (204.97, 115.22))
_GUSSET_RUN_TEXT = (124.72, 215.88, 165.32, 219.44)
_GUSSET_RUN_WITNESSES = (((143.67, 194.5), (143.67, 215.94)), ((149.67, 200.5), (149.67, 215.94)))
_CORNER_WITNESSES = (
    ((70.63, 206.83), (70.63, 251.94)),  # (446.2)
    ((72.63, 212.17), (45.0, 212.17)),  # 262.0
    ((84.03, 199.5), (58.0, 199.5)),  # 186.0
)
# SolidWorks' cutting-plane arrowhead is 1/8 in across (cone_tip_block's
# SECTION_ARROW_HEAD, measured on its renders) on a 12 mm shaft.
_SECTION_ARROW_LENGTH = 0.012
_SECTION_ARROW_HALF_WIDTH = 0.003175 / 2.0


def _mm(box):
    return tuple(value / 1000.0 for value in box)


def _mm_segment(segment):
    return tuple(tuple(value / 1000.0 for value in point) for point in segment)


def _plan_point(key, x, z):
    cx, cy = _SECTION_PLAN[key]
    return (cx + x * _PLAN_S, cy - z * _PLAN_S)


def _letter_tails(ends):
    """Each letter's arrow tail, keyed '<section>-<outer|inner>'; E's cut
    starts at its inner end, B's and D's at their outer ends."""
    order = {"B": ("outer", "inner"), "E": ("inner", "outer"), "D": ("outer", "inner")}
    return {
        f"{key}-{name}": _plan_point(key, *point)
        for key, pair in ends.items()
        for name, point in zip(order[key], pair)
    }


def _letter_boxes(ends):
    boxes = {}
    for name, (x, y) in _letter_tails(ends).items():
        dx0, dy0, dx1, dy1 = drawing.SECTION_CUT_BASELINE_LETTER_EXTENTS[name[0]]
        boxes[name] = (x + dx0, y + dy0, x + dx1, y + dy1)
    return boxes


def _box_point_gap(box, point):
    x, y = point
    return math.hypot(max(box[0] - x, 0.0, x - box[2]), max(box[1] - y, 0.0, y - box[3]))


def _segment_point_gap(start, end, point):
    (x0, y0), (x1, y1) = start, end
    run = ((point[0] - x0) * (x1 - x0) + (point[1] - y0) * (y1 - y0)) / math.dist(start, end) ** 2
    t = max(0.0, min(1.0, run))
    return math.dist(point, (x0 + t * (x1 - x0), y0 + t * (y1 - y0)))


def _box_segment_gap(box, segment):
    start, end = segment
    # A segment through the box is clipped to it (Liang-Barsky).
    (x0, y0), (x1, y1) = start, end
    low, high = 0.0, 1.0
    for p, q in (
        (x0 - x1, x0 - box[0]), (x1 - x0, box[2] - x0),
        (y0 - y1, y0 - box[1]), (y1 - y0, box[3] - y0),
    ):
        if p == 0.0:
            if q < 0.0:
                low, high = 1.0, 0.0
            continue
        t = q / p
        if p < 0.0:
            low = max(low, t)
            continue
        high = min(high, t)
    if low <= high:
        return 0.0
    corners = ((box[0], box[1]), (box[0], box[3]), (box[2], box[1]), (box[2], box[3]))
    return min(
        _box_point_gap(box, start),
        _box_point_gap(box, end),
        *(_segment_point_gap(start, end, corner) for corner in corners),
    )


def _box_box_gap(a, b):
    return math.hypot(max(b[0] - a[2], 0.0, a[0] - b[2]), max(b[1] - a[3], 0.0, a[1] - b[3]))


def _plan_line(key, a, b):
    return (_plan_point(key, *a), _plan_point(key, *b))


def _segment_ink(what, segment, clearance):
    return (what, lambda box: _box_segment_gap(box, segment), clearance)


def _corner_witnesses(boss_dia):
    """Only the overall-width witness follows the boss's X extreme.

    Rail depth and window-edge witnesses stay on their unchanged faces.
    Carry the measured witness gap forward, not the old Ø52.2 station.
    """
    shift_mm = (_B49E1_BOSS_DIA - boss_dia) / 2.0 * drawing.GEOMETRY_VIEW_SCALE
    return (
        tuple((x + shift_mm, y) for x, y in _CORNER_WITNESSES[0]),
        *_CORNER_WITNESSES[1:],
    )


def _letter_ink(name, *, boss_dia):
    """(what, gap function, clearance) for the ink round one letter: the
    plan's own edges, projected from the model, and the dimension ink b49e1
    printed beside it."""
    ink = drawing.INK_CLEARANCE
    if name == "B-outer":
        edge = _plan_line("B", (-part.COLUMN_X, part.OUTER_Z), (part.COLUMN_X, part.OUTER_Z))
        return (
            _segment_ink("rail outer edge", edge, drawing.TEXT_CLEARANCE),
            _segment_ink("183.9 line", _mm_segment(_WINDOW_WIDTH_LINE), drawing.TEXT_CLEARANCE),
            # Beside the value on its line: a letter's width of air, so the
            # letter does not read as the value's prefix ("B183.9").
            ("183.9", lambda box: _box_box_gap(box, _mm(_WINDOW_WIDTH_TEXT)),
             drawing.SECTION_CUT_BASELINE_TEXT_GAP),
        )
    if name == "B-inner":
        face = _plan_line("B", (part.BAR_X1, part.INNER_Z), (part.INNER_X, part.INNER_Z))
        return (_segment_ink("rail inner face", face, ink),)
    if name == "E-inner":
        near = -(part.INNER_Z + part.EDGE_CHAMFER)
        far = -(part.OUTER_Z - part.EDGE_CHAMFER)
        return (
            _segment_ink("rail inner edge", _plan_line("E", (part.BAR_X1, near), (part.INNER_X, near)), ink),
            _segment_ink("rail outer edge", _plan_line("E", (part.BAR_X1, far), (part.INNER_X, far)), ink),
            *(
                _segment_ink(f"18.0 witness {i}", _mm_segment(w), ink)
                for i, w in enumerate(_GUSSET_RUN_WITNESSES)
            ),
            ("18.0", lambda box: _box_box_gap(box, _mm(_GUSSET_RUN_TEXT)), ink),
        )
    if name == "E-outer":
        boss = _plan_point("E", -part.COLUMN_X, part.FRONT_COLUMN_Z)
        boss_r = boss_dia / 2.0 * _PLAN_S
        return (
            ("corner boss", lambda box: max(0.0, _box_point_gap(box, boss) - boss_r), ink),
            *(
                _segment_ink(f"corner witness {i}", _mm_segment(w), ink)
                for i, w in enumerate(_corner_witnesses(boss_dia))
            ),
        )
    face_x = {"D-outer": -part.OUTER_X, "D-inner": -part.INNER_X}[name]
    face = _plan_line("D", (face_x, -part.INNER_Z), (face_x, part.INNER_Z))
    return (_segment_ink("hub rail face", face, ink),)


def _letter_shortfalls(ends, name, *, boss_dia):
    """The ink a letter stands too close to, with its gap in mm."""
    box = _letter_boxes(ends)[name]
    return {
        what: round(gap(box) * 1000.0, 2)
        for what, gap, clearance in _letter_ink(name, boss_dia=boss_dia)
        if gap(box) < clearance
    }


def test_section_letter_model_reproduces_b49e1() -> None:
    """At b49e1's ends the letter model covers the letters b49e1 printed,
    within its 0.1 mm outward rounding, and reproduces the overprints."""
    boxes = _letter_boxes(_B49E1_CUT_ENDS)
    for name, printed in _B49E1_LETTERS.items():
        model, printed = boxes[name], _mm(printed)
        assert model[0] <= printed[0] and model[1] <= printed[1], name
        assert model[2] >= printed[2] and model[3] >= printed[3], name
        assert max(abs(m - p) for m, p in zip(model, printed)) < 0.00015, name
    shortfalls = {
        name: _letter_shortfalls(_B49E1_CUT_ENDS, name, boss_dia=_B49E1_BOSS_DIA)
        for name in _LETTER_ENDS
    }
    assert shortfalls["B-outer"]["rail outer edge"] == 0.0
    assert shortfalls["B-outer"]["183.9"] == 0.0
    assert shortfalls["E-outer"]["corner boss"] == 0.0
    assert shortfalls["E-outer"]["corner witness 0"] == 0.0
    assert shortfalls["D-inner"]["hub rail face"] == 0.0


@pytest.mark.parametrize("name", _LETTER_ENDS)
def test_section_cut_calibration_keeps_historical_letter_clearance(name: str) -> None:
    """Replay the measured B/E/D glyphs at the preserved cutting endpoints.

    This guards the historical placement calibration only.  It cannot prove
    live H/K glyph clearance, which requires native inspection.
    """
    live_ends = drawing.section_cut_ends()
    baseline_ends = {"B": live_ends["H"], "E": live_ends["E"], "D": live_ends["K"]}
    assert (
        _letter_shortfalls(baseline_ends, name, boss_dia=part.BOSS_DIA)
        == {}
    )


@pytest.mark.parametrize("name", ("B-outer", "B-inner", "E-inner", "E-outer", "D-inner"))
def test_b49e1_section_letter_is_what_sat_on_ink(name: str) -> None:
    """The same check on b49e1's ends fails for every letter #955 moves off
    ink.  D's outer letter was already 2.2 mm clear; its end only re-derives."""
    assert _letter_shortfalls(_B49E1_CUT_ENDS, name, boss_dia=_B49E1_BOSS_DIA)


def test_h_outer_arrow_keeps_off_the_window_width() -> None:
    """H's unchanged outer arrow clears the historical width-dimension ink;
    this checks its arrow, not the renamed letter's glyph bounds."""
    tail = _plan_point("B", *drawing.section_cut_ends()["H"][0])
    line_y = _WINDOW_WIDTH_LINE[0][1] / 1000.0
    assert tail[1] - _SECTION_ARROW_HALF_WIDTH - line_y >= 0.001
    assert tail[0] + _SECTION_ARROW_LENGTH <= _WINDOW_WIDTH_TEXT[0] / 1000.0 - drawing.INK_CLEARANCE


# Sheet-2 ink about the two short plan widths, measured on the ca7edf4d
# render (sheet m): each width's left arrow tail, the plan's top edge, the
# 359.8 line, its left extension, the 152.9 line and the front view's top.
# The crossbar flange's tail is that render's 0.13275 moved with the
# crossbar's -X face, 1.5 further out since (25.0 wide, was 22.0), at 1:3.
_CROSSBAR_FLANGE_ARROW_TAIL_X = 0.13275 - 1.5 * _PLAN_S
_GUSSET_RUN_ARROW_TAIL_X = 0.14009
_PLAN_TOP_Y = 0.21216
_WIN_WIDTH_LINE_Y = 0.22772
_WIN_WIDTH_LEFT_EXTENSION_X = 0.08502
_WINDOW_WIDTH_LINE_Y = 0.11522
_FRONT_VIEW_TOP_Y = 0.09666


@pytest.mark.parametrize(
    ("xy", "lines", "left", "below", "above", "right"),
    (
        (
            drawing.CROSSBAR_FLANGE_TEXT_OFFSET_XY, ("25.0", "CROSSBAR FLANGE"),
            drawing.SHEET_FRAME[0], _FRONT_VIEW_TOP_Y, _WINDOW_WIDTH_LINE_Y,
            _CROSSBAR_FLANGE_ARROW_TAIL_X,
        ),
        (
            drawing.GUSSET_RUN_TEXT_OFFSET_XY, ("18.0", "4X 45 DEG GUSSET"),
            _WIN_WIDTH_LEFT_EXTENSION_X, _PLAN_TOP_Y, _WIN_WIDTH_LINE_Y,
            _GUSSET_RUN_ARROW_TAIL_X,
        ),
    ),
    ids=("crossbar-flange-25.0", "gusset-run-18.0"),
)
def test_short_plan_width_text_parks_clear_of_its_extension_lines(
    xy, lines, left, below, above, right
) -> None:
    """ca7edf4d review: both widths are shorter on paper than their text, so
    centred text stood across their extension lines.  Parked left on a
    leader, each text block (2.9 mm a glyph, 4.6 mm a row, both rounded up
    from that render) keeps an ink clearance to every neighbour."""
    half_w = 0.0029 * max(len(line) for line in lines) / 2.0
    half_h = 0.0046 * len(lines) / 2.0
    ink = drawing.INK_CLEARANCE
    assert xy[0] + half_w + ink <= right
    assert xy[0] - half_w - ink >= left
    assert xy[1] - half_h - ink >= below
    assert xy[1] + half_h + ink <= above


def test_section_cuts_cross_the_same_stock() -> None:
    """The preserved ends keep what each removed section shows: H cuts the
    rail's plain T between the junction land and the corner boss, E runs
    from outside the left rail past the crossbar T, K from outside the
    set-screw boss past the hub rail's inner face, each at its own station."""
    ends = drawing.section_cut_ends()
    (hx, h_outer), (hx_inner, h_inner) = ends["H"]
    assert hx == hx_inner and part.LAND_X1 < hx < part.COLUMN_X - part.BOSS_DIA / 2.0
    assert h_inner < part.INNER_Z and h_outer > drawing.PLAN_HALF_Z
    (e_inner, ez), (e_outer, ez_outer) = ends["E"]
    assert ez == ez_outer == drawing.SIDE_SECTION_Z
    assert e_inner > part.BAR_X1 and e_outer < -drawing.PLAN_HALF_X
    (k_outer, kz), (k_inner, kz_inner) = ends["K"]
    assert kz == kz_inner == part.GOOSENECK_Z
    assert k_outer < part.SET_BOSS_FACE_X and -part.INNER_X < k_inner < part.BAR_X0


# Each removed section's profile ink on b49e1 (mm, x only): B-B's T, E-E's
# left side rail (its web to the right), D-D's hub rail.
_B49E1_PROFILES = {
    "B-B": (350.10, 362.76),
    "E-E": (292.38, 344.91),
    "D-D": (314.89, 349.07),
}


def test_section_profiles_pin_where_b49e1_printed_them() -> None:
    """leaders955-f542: the longer cuts slid D-D's profile 4.27 mm, E-E's
    2.84 and B-B's 0.67 under their typed text, so each is pinned by the
    rail centreline it cuts, at b49e1's print."""
    b0, b1 = _B49E1_PROFILES["B-B"]
    assert drawing.RAIL_SECTION_PROFILE_X * 1000.0 == pytest.approx((b0 + b1) / 2.0, abs=0.01)
    e0, _e1 = _B49E1_PROFILES["E-E"]
    side_rail_centre = e0 + (part.OUTER_X - part.COLUMN_X) / 4.0
    assert drawing.SIDE_SECTION_PROFILE_X * 1000.0 == pytest.approx(side_rail_centre, abs=0.01)
    d0, d1 = _B49E1_PROFILES["D-D"]
    assert d1 - d0 == pytest.approx(part.RAIL_W_SIDE, abs=0.05)
    assert drawing.HUB_SECTION_PROFILE_X * 1000.0 == pytest.approx((d0 + d1) / 2.0, abs=0.01)


# --- The set-screw boss (user ruling 2026-10-12, Q5) ------------------------


def test_hub_set_screw_keeps_one_and_a_half_diameters_of_full_thread() -> None:
    """The set tap starts from a spot face .83 (.XX) from the bore axis on a
    boss cast onto the hub pad, and keeps >= 1.5D of full thread at the
    printed worst case (the ch_pivot_bracket_spec idiom)."""
    terms = spec.SET_SCREW_THREAD_TERMS
    assert list(terms) == [
        "spot face from bore axis at its minimum",
        "bore radius at its maximum",
        "bore sag across the thread",
        "one-pitch entry chamfer",
    ]
    assert terms["spot face from bore axis at its minimum"] == pytest.approx(20.828)
    assert all(v < 0.0 for k, v in terms.items() if k != "spot face from bore axis at its minimum")
    assert spec.SET_SCREW_FULL_THREAD_MIN == pytest.approx(10.317, abs=1e-3)
    assert spec.SET_SCREW_FULL_THREAD_NOMINAL == pytest.approx(10.688, abs=1e-3)
    assert spec.SET_SCREW_MAJOR_DIA == pytest.approx(6.35)
    assert spec.SET_SCREW_ENGAGEMENT_D >= spec.SET_SCREW_MIN_ENGAGEMENT_D == 1.5


def test_set_screw_boss_carries_the_spot_face_proud_of_the_rail() -> None:
    """The boss face stands .04 of stock over the spot face, both outboard
    of the rail's outer face; the spot clears the 1/4 square head's
    diagonal (91410A540, Head Wd 1/4 in) at its minimum, and keeps a land
    inside the boss face's edge breaks at the print-worst corner (local codex
    review of 4faacfab: the O12 spot broke 0.4 into them)."""
    assert part.SET_SPOT_FACE_X == part.GOOSENECK_X - spec.HUB_SET_SPOT_FROM_AXIS
    assert part.SET_BOSS_FACE_X == part.GOOSENECK_X - spec.HUB_SET_BOSS_FROM_AXIS
    assert part.SET_BOSS_FACE_X < part.SET_SPOT_FACE_X < -part.OUTER_X
    spot_places = spec.HUB_SET_SPOT_PLACES
    assert spot_places == spec.DRAWING_REFERENCE_PRECISION[
        "set-screw spot face from bore axis"
    ]
    assert spec.printed_limit(spec.HUB_SET_SPOT_DIA, 2, -1.0) > 6.35 * math.sqrt(2.0)
    assert part.SET_SPOT_LAND_MIN == pytest.approx(
        {"across the boss": 2.8448, "under the flange": 3.9497}
    )
    assert min(part.SET_SPOT_LAND_MIN.values()) >= part.EDGE_BREAK_SLIVER_MIN
    assert spec.HUB_SET_BOSS_W < part.HUB_RIB_W


def test_set_screw_pocket_is_retired_for_the_boss() -> None:
    sources = [
        Path(module.__file__).read_text(encoding="utf-8") for module in (spec, part, drawing)
    ]
    for retired in ("SET_POCKET", "_hub_pocket_section", "PocketRise", "POCKET_RISE", "POCKET RIM"):
        assert not any(retired in source for source in sources), retired
    assert "hub_section = _hub_boss_section(adapter, hub_top)" in sources[2]
    assert drawing.HUB_LEFT_CALLOUTS == {
        "SetBossWidth": "BOSS WIDTH CENTRED ON TAP\nTOP AT FLANGE UNDERSIDE",
        "SetSpotDia": "SPOT FACE",
    }
    # drawing-guidelines.md rule 7 (notes: few, flagged, never a method): short callouts that state the feature, not the process.
    for text in drawing.HUB_LEFT_CALLOUTS.values():
        assert len(text.splitlines()) <= 4
        assert not {"CAST", "MILL", "MACHINE"} & set(text.replace("\n", " ").split())


# Sheet-5 ink as the 40d9d030e and run-6 renders print it: a dimension row
# stands on a 5.55 mm pitch with 3.6 mm glyphs, so an n-row block is
# n x 5.55 - 1.95 tall about its text point; the widest rows on the sheet
# advance 2.82 mm a character (SQ POCKET, 25.4 for nine); an offset value's
# underline runs 1.0 under its block and 0.1 past each side; an extension
# line overshoots its dimension line 1.03; a bent leader's native shoulder
# is 6.35 (HANGER_REAM_FRAME_SHOULDER's).
_ROW_PITCH = 0.00555
_ROW_SLACK = 0.00195
_ROW_CHAR = 0.00282
_UNDERLINE_DROP = 0.001
_UNDERLINE_PAST = 0.0001
_EXTENSION_OVERSHOOT = 0.00103
_BENT_SHOULDER = 0.00635
# Historical D-D's tap axis (rail mid-height) prints at y 211.8 mm; its
# SECTION D-D / SCALE 1 : 1 caption printed 307.3..352.6 x 163.3..178.0 mm
# about HUB_SECTION_CAPTION_XY (run 6).  This is not a K-K caption measurement.
_DD_AXIS_Y = 0.2118
_HISTORICAL_DD_CAPTION_EXTENT = (0.0227, 0.0147, 0.0226, 0.0)
# A finish symbol's ink from its point: "Ra 3.2" ends 14.8 right of it and
# tops out 6.8 over it (the hub bore symbol on the 40d9d030e render).
_FINISH_INK = (0.0, 0.0, 0.0148, 0.0068)
# The hub side view's tap centre prints at (146.5, 95.9) mm.  The unchanged
# tap callout elbows 30.0 left of and 5.6 under its text point, its two rows
# printing -28.3..+28.0 x -5.0..+4.4 about it; HUB LOCATION printed
# 107.4..140.8 x 139.9..143.5 (run 6).
_HUB_LEFT_TAP = (0.1465, 0.0959)
_TAP_CALLOUT_ELBOW = (-0.0300, -0.0056)
_TAP_CALLOUT_EXTENT = (0.0283, 0.0050, 0.0280, 0.0044)
_HUB_LOCATION_NOTE = (0.1074, 0.1399, 0.1408, 0.1435)


def _dimension_block(xy, rows):
    """An offset dimension's text block about its text point, underline included."""
    lines = rows.splitlines()
    half_w = max(map(len, lines)) * _ROW_CHAR / 2.0 + _UNDERLINE_PAST
    half_h = (len(lines) * _ROW_PITCH - _ROW_SLACK) / 2.0
    return (xy[0] - half_w, xy[1] - half_h - _UNDERLINE_DROP, xy[0] + half_w, xy[1] + half_h)


def _offset_leader(line_xy, block):
    """An offset value's leader: from its dimension line's midpoint to the
    near end of its underline."""
    from _layout_geometry import Segment

    end_x = block[2] if block[2] < line_xy[0] else block[0]
    return Segment(line_xy[0], line_xy[1], end_x, block[1])


def _dd(x: float, y: float) -> tuple[float, float]:
    """Historical D-D layout at 1:1; K-K retains its geometry, not its glyphs."""
    return (
        drawing.HUB_SECTION_PROFILE_X + (x - part.GOOSENECK_X) / 1000.0,
        _DD_AXIS_Y + y / 1000.0,
    )


def test_hub_boss_section_layout_replays_historical_ink() -> None:
    """Q5 layout with its measured historical D-D caption envelope.

    The current K-K view keeps the thread, spot-face and boss-face geometry
    and text placement.  Replaying the old caption is baseline evidence
    only; native inspection must establish the new caption's clearance.
    """
    from _layout_geometry import Segment, segment_box_distance

    ink = drawing.INK_CLEARANCE
    spot_r = spec.HUB_SET_SPOT_DIA / 2.0
    bore_x = part.GOOSENECK_X - part.GOOSENECK_BORE_DIA / 2.0
    spot_x, boss_x, axis_x = part.SET_SPOT_FACE_X, part.SET_BOSS_FACE_X, part.GOOSENECK_X
    chamfer = part.EDGE_CHAMFER
    thread_y = drawing.HUB_SET_THREAD_LINE_XY[1]
    spot_y = drawing.HUB_SET_SPOT_LINE_XY[1]
    boss_y = drawing.HUB_SET_BOSS_LINE_XY[1]
    lines = {
        "thread": Segment(_dd(spot_x, 0.0)[0], thread_y, _dd(bore_x, 0.0)[0], thread_y),
        "21.0": Segment(_dd(axis_x, 0.0)[0], spot_y, _dd(spot_x, 0.0)[0], spot_y),
        "22.0": Segment(_dd(axis_x, 0.0)[0], boss_y, _dd(boss_x, 0.0)[0], boss_y),
    }
    # Each offset leader leaves its own line's midpoint.
    for name, xy in {
        "thread": drawing.HUB_SET_THREAD_LINE_XY,
        "21.0": drawing.HUB_SET_SPOT_LINE_XY,
        "22.0": drawing.HUB_SET_BOSS_LINE_XY,
    }.items():
        line = lines[name]
        assert xy[0] == pytest.approx((line.x0 + line.x1) / 2.0, abs=1e-4), name
    blocks = {
        "thread": _dimension_block(drawing.HUB_SET_THREAD_OFFSET_XY, "(10.5)\nTHREAD LENGTH"),
        "21.0": _dimension_block(drawing.HUB_SET_SPOT_OFFSET_XY, "21.0\nSPOT FACE\nFROM BORE AXIS"),
        "22.0": _dimension_block(drawing.HUB_SET_BOSS_OFFSET_XY, "(22.0)\nBOSS FACE\nFROM BORE AXIS"),
    }
    leaders = {
        "thread": _offset_leader(drawing.HUB_SET_THREAD_LINE_XY, blocks["thread"]),
        "21.0": _offset_leader(drawing.HUB_SET_SPOT_LINE_XY, blocks["21.0"]),
        "22.0": _offset_leader(drawing.HUB_SET_BOSS_LINE_XY, blocks["22.0"]),
    }
    over = _EXTENSION_OVERSHOOT
    extensions = {
        # The spot face's line carries both the thread length and the 21.0.
        "spot face": ("thread", "21.0", Segment(*_dd(spot_x, spot_r), _dd(spot_x, 0.0)[0], spot_y + over)),
        "bore wall": ("thread", Segment(*_dd(bore_x, part.HALF_H), _dd(bore_x, 0.0)[0], thread_y + over)),
        "upper axis": ("21.0", Segment(*_dd(axis_x, part.HALF_H + 2.0), _dd(axis_x, 0.0)[0], spot_y + over)),
        "boss face": ("22.0", Segment(*_dd(boss_x, -part.HALF_H + chamfer), _dd(boss_x, 0.0)[0], boss_y - over)),
        "lower axis": (
            "22.0",
            Segment(*_dd(axis_x, -part.HALF_H - part.HUB_BOSS_DROP - 2.0), _dd(axis_x, 0.0)[0], boss_y - over),
        ),
    }
    left, bottom = _dd(boss_x, -part.HALF_H - part.HUB_BOSS_DROP)
    right, top = _dd(-part.INNER_X, part.HALF_H)
    outline = (left, bottom, right, top)
    cx, cy = drawing.HUB_SECTION_CAPTION_XY
    dx0, dy0, dx1, dy1 = _HISTORICAL_DD_CAPTION_EXTENT
    caption = (cx - dx0, cy - dy0, cx + dx1, cy + dy1)
    frame = drawing.SHEET_FRAME
    for name, block in blocks.items():
        assert frame[0] + ink <= block[0] and block[2] <= frame[2] - ink, name
        assert frame[1] + ink <= block[1] and block[3] <= frame[3] - ink, name
        assert _box_box_gap(block, outline) >= ink, name
        assert _box_box_gap(block, caption) >= ink, name
        for other, other_block in blocks.items():
            if other != name:
                assert _box_box_gap(block, other_block) >= ink, (name, other)
        for other, leader in leaders.items():
            if other != name:
                assert segment_box_distance(leader, _layout_box(block)) >= ink, (name, other)
        for other, line in lines.items():
            assert segment_box_distance(line, _layout_box(block)) >= ink, (name, other)
        for other, (*_owners, extension) in extensions.items():
            assert segment_box_distance(extension, _layout_box(block)) >= ink, (name, other)
    for name, leader in leaders.items():
        for other, other_leader in leaders.items():
            if other != name:
                assert _segment_gap(leader, other_leader) >= ink, (name, other)
        for other, (*owners, extension) in extensions.items():
            if name not in owners:
                assert _segment_gap(leader, extension) >= ink, (name, other)
        for other, line in lines.items():
            if other != name:
                assert _segment_gap(leader, line) >= ink, (name, other)
        assert segment_box_distance(leader, _layout_box(caption)) >= ink, name
    # The 22.0 hangs under the view over the caption: its line, arrowheads
    # and extension ends all stay an ink clearance above it.
    assert boss_y - drawing.ARROW_HALF_WIDTH - caption[3] >= ink
    assert boss_y - over - caption[3] >= ink


def _layout_box(box):
    from _layout_geometry import Box

    return Box(*box)


def test_hub_side_boss_width_and_spot_face_stand_clear_of_their_ink() -> None:
    """Q5: the 1:2 side view sees the boss face on.  The 18.0 width's rows
    stand straight over it; the tap callout's leader leaves under the right
    extension line's foot and the Ø10.0 spot face's under the left one, each
    an ink clearance off, and the spot leader's run over the part stays
    inside the leader-over-part detour gate."""
    from _layout_audit import LEADER_DETOUR_PROVISIONAL_M
    from _layout_geometry import Segment, segment_box_distance

    ink = drawing.INK_CLEARANCE
    s = drawing.HUB_LEFT_SCALE[0] / drawing.HUB_LEFT_SCALE[1] / 1000.0
    tap = _HUB_LEFT_TAP
    half_w = spec.HUB_SET_BOSS_W / 2.0 * s
    boss_top = tap[1] + part.FLANGE_BOT_Y * s
    assert (tap[0] - half_w, tap[0] + half_w, boss_top) == pytest.approx((0.1420, 0.1510, 0.1010), abs=1e-4)
    line_x, line_y = drawing.SET_BOSS_WIDTH_LINE_XY
    assert line_x == pytest.approx(tap[0])
    feet = {"left": (tap[0] - half_w, boss_top), "right": (tap[0] + half_w, boss_top)}
    extensions = {
        side: Segment(x, y, x, line_y + _EXTENSION_OVERSHOOT) for side, (x, y) in feet.items()
    }
    width = _dimension_block(
        drawing.SET_BOSS_WIDTH_TEXT_XY, "18.0\n" + drawing.HUB_LEFT_CALLOUTS["SetBossWidth"]
    )
    width_line = Segment(tap[0] - half_w, line_y, tap[0] + half_w, line_y)
    # The tap callout: unchanged, its leader dropping from the elbow
    # through the tap centre to the tap circle.
    callout_xy = (drawing.HUB_LEFT_CENTER[0] + 0.0844, drawing.HUB_LEFT_CENTER[1] + 0.0356)
    callout = (
        callout_xy[0] - _TAP_CALLOUT_EXTENT[0],
        callout_xy[1] - _TAP_CALLOUT_EXTENT[1],
        callout_xy[0] + _TAP_CALLOUT_EXTENT[2],
        callout_xy[1] + _TAP_CALLOUT_EXTENT[3],
    )
    elbow = (callout_xy[0] + _TAP_CALLOUT_ELBOW[0], callout_xy[1] + _TAP_CALLOUT_ELBOW[1])
    tap_r = part.TAP_DRILL_MM[part.SET_SCREW_THREAD] / 2.0 * s
    run = math.dist(tap, elbow)
    tap_tip = tuple(c + (e - c) * tap_r / run for c, e in zip(tap, elbow))
    tap_leader = Segment(*elbow, *tap_tip)
    # The Ø10.0: a bent leader from its underline's right end, radial from
    # the shoulder's bend to the spot circle.
    spot = _dimension_block(drawing.SET_SPOT_DIA_TEXT_XY, "Ø10.0\nSPOT FACE")
    bend = (spot[2] + _BENT_SHOULDER, spot[1])
    spot_r = spec.HUB_SET_SPOT_DIA / 2.0 * s
    run = math.dist(tap, bend)
    spot_tip = tuple(c + (b - c) * spot_r / run for c, b in zip(tap, bend))
    spot_leader = Segment(*bend, *spot_tip)
    spot_shoulder = Segment(spot[2], spot[1], *bend)
    leaders = {"tap": tap_leader, "spot": spot_leader, "spot shoulder": spot_shoulder}
    # Each leader passes UNDER its own side's foot, an ink clearance off,
    # and crosses neither extension line.
    for side, extension in extensions.items():
        for name, leader in leaders.items():
            assert _segment_gap(leader, extension) >= ink, (name, side)
    for name, x in {"tap": feet["right"][0], "spot": feet["left"][0]}.items():
        leader = leaders[name]
        t = (x - leader.x0) / (leader.x1 - leader.x0)
        assert leader.y0 + t * (leader.y1 - leader.y0) < boss_top, name
    texts = {"18.0": width, "Ø10.0": spot, "tap callout": callout, "HUB LOCATION": _HUB_LOCATION_NOTE}
    for name, box in texts.items():
        for other, other_box in texts.items():
            if other != name:
                assert _box_box_gap(box, other_box) >= ink, (name, other)
        own = {"Ø10.0": {"spot shoulder"}, "tap callout": {"tap"}}.get(name, set())
        for leader_name, leader in leaders.items():
            if leader_name not in own:
                assert segment_box_distance(leader, _layout_box(box)) >= ink, (name, leader_name)
        if name != "18.0":
            assert segment_box_distance(width_line, _layout_box(box)) >= ink, name
            for side, extension in extensions.items():
                assert segment_box_distance(extension, _layout_box(box)) >= ink, (name, side)
    # The Ø10.0's rows stand over the left barrel's top, the view's top.
    view_top = tap[1] + (part.HALF_H + part.BOSS_ABOVE) * s
    assert spot[1] - view_top >= ink
    frame = drawing.SHEET_FRAME
    for name, box in {"18.0": width, "Ø10.0": spot}.items():
        assert frame[0] + ink <= box[0] and box[2] <= frame[2] - ink, name
        assert box[3] <= frame[3] - ink, name
    # Leader over the part: from its rail-top crossing to the spot rim,
    # against the rim's approach from the view's top.
    rail_top = tap[1] + part.HALF_H * s
    t = (rail_top - spot_tip[1]) / (bend[1] - spot_tip[1])
    crossing = (spot_tip[0] + t * (bend[0] - spot_tip[0]), rail_top)
    detour = math.dist(crossing, spot_tip) - (view_top - spot_tip[1])
    assert detour <= LEADER_DETOUR_PROVISIONAL_M, detour


class _FakeView:
    def __init__(self, position, persists=True):
        self.Position = position
        self.persists = persists

    def SetViewPosition(self, xy, _move_children):
        if self.persists:
            self.Position = tuple(xy)
        return True


def _pin(monkeypatch, view, offset):
    """Pin with the model point printing at the view's position + offset."""
    monkeypatch.setattr(
        drawing, "model_point_in_view",
        lambda _adapter, v, _xyz, *, label: (v.Position[0] + offset[0], v.Position[1] + offset[1]),
    )
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda _adapter, *, label: None)
    monkeypatch.setattr(drawing, "double_array", lambda values: tuple(values))
    drawing._pin_section_profile(None, view, (0.0, 0.0, 0.0), 0.3320, label="K-K")


def test_pin_section_profile_moves_the_view_by_the_miss(monkeypatch) -> None:
    view = _FakeView((0.3300, 0.2100))
    _pin(monkeypatch, view, (-0.0043, 0.0))
    assert view.Position == pytest.approx((0.3363, 0.2100))


def test_pin_section_profile_fails_loud_when_the_move_does_not_hold(monkeypatch) -> None:
    with pytest.raises(RuntimeError, match="K-K section profile prints at"):
        _pin(monkeypatch, _FakeView((0.3300, 0.2100), persists=False), (-0.0043, 0.0))


# --- Knife hanger: #10 loose plain clearance and dowels --------------------


def test_knife_hanger_is_a_plain_10_loose_drilled_hole() -> None:
    import spring_mount_geom
    from _hole_spec import blind_cut_dia_mm

    hole = spec.HANGER_HOLE_SPEC
    assert (hole.kind, hole.size, hole.fit, hole.end) == (
        "clearance", "#10", "loose", "through_all",
    )
    assert hole.overrides_mm == {}
    assert blind_cut_dia_mm(hole) == spec.HANGER_CLEARANCE_DIA
    assert spec.HANGER_CLEARANCE_DIA == pytest.approx(6.045)
    # The washer spotfaces are gone, not aliased (user ruling 2026-10-14).
    assert not [name for name in dir(spec) if name.startswith("HANGER_SPOTFACE")]
    # The 1/2 hanger-stud clearance is gone, not aliased.
    assert not hasattr(part, "STUD_HOLE_SPEC") and not hasattr(part, "STUD_HOLE_DIA")
    # Both stations sit on the knife line, centred on the crossbar.
    assert part.HANGER_X == spring_mount_geom.KNIFE[0] == (part.BAR_X0 + part.BAR_X1) / 2.0
    assert drawing.HANGER_X == part.HANGER_X
    assert (part.BAR_X0, part.BAR_X1) == pytest.approx((-27.4968, -2.5032))
    assert spec.HANGER_CROSSBAR_WIDTH == part.BAR_X1 - part.BAR_X0
    assert spec.HANGER_CROSSBAR_WIDTH == pytest.approx(24.9936)  # .984
    # Washer bounds are parent-verified ASME Table 11 exports, not head guesses.
    assert (spec.HANGER_WASHER.OD_MIN, spec.HANGER_WASHER.OD_MAX) == (12.573, 13.081)
    assert spec.HANGER_WASHER.OD_ID_RUNOUT_MAX == pytest.approx(0.3302)
    assert spec.HANGER_WASHER_CONCENTRIC_ANNULUS_MIN == pytest.approx(3.2132)
    assert part.STUD_Z_REAR + spec.HANGER_WASHER.OD_MAX/2 < part.INNER_Z+part.GUSSET


def test_knife_hanger_wizard_is_a_plain_clearance_row_from_the_underside() -> None:
    """A plain native Hole Wizard clearance row. A plain hole ignores
    HoleFit, so _holes writes the pinned 6.045 over any seeded size and the
    build reads the cut diameter back; no depth is driven."""
    import _holes

    hole = spec.HANGER_HOLE_SPEC
    # swWzdHole, swStandardAnsiInchScrewClearances.
    assert _holes._KINDS[hole.kind] == (2, 22)
    source = Path(part.__file__).read_text(encoding="utf-8")
    call = source[source.index("hanger_wizard = wizard_holes(") :]
    call = call[: call.index("\n    )\n")]
    assert "HANGER_HOLE_SPEC," in call
    assert "expect_dia_mm=HANGER_CLEARANCE_DIA" in call
    assert "HoleSpec(" not in call
    # Entered at the faced underside (outward normal -Y), drilled to the top.
    assert "[[HANGER_X, -HALF_H, STUD_Z_FRONT], [HANGER_X, -HALF_H, STUD_Z_REAR]]," in call
    assert "(0.0, -1.0, 0.0)," in call
    assert 'name="StudHoles"' in call
    # The hole runs the full grip; nothing drives a wizard depth.
    assert (
        "v_hangers = 2.0 * math.pi * (HANGER_CLEARANCE_DIA / 2.0) ** 2 * RING_HEIGHT"
        in source
    )
    assert "hanger_depth" not in source and "HANGER_SPOTFACE" not in source


def test_hanger_through_diameter_has_a_native_unilateral_band(monkeypatch) -> None:
    from types import SimpleNamespace

    assert spec.HANGER_CLEARANCE_DIA_BAND == pytest.approx((0.1016, 0.0))  # +.004/0
    assert spec.HANGER_CLEARANCE_DIA_MIN == pytest.approx(6.045)
    assert spec.HANGER_CLEARANCE_DIA_MAX == pytest.approx(6.1466)
    monkeypatch.setattr(part, "_early_bound", lambda entity, _kind: entity)
    monkeypatch.setattr(drawing, "_early_bound", lambda entity, _kind: entity)
    precisions = []
    monkeypatch.setattr(
        part, "_set_tolerance_precision",
        lambda *_args, **kwargs: precisions.append(kwargs),
    )

    class Tolerance:
        Type = 0
        minimum = maximum = 0.0

        def SetValues(self, minimum, maximum):
            self.minimum, self.maximum = minimum, maximum
            return True

        def GetMinValue(self):
            return self.minimum

        def GetMaxValue(self):
            return self.maximum

    def display(name, value):
        dimension = SimpleNamespace(FullName=name, SystemValue=value, Tolerance=Tolerance())
        return SimpleNamespace(GetDimension2=lambda _index: dimension)

    # Deliberately put the plain wizard's through depth before its diameter.
    displays = [
        display("Thru Hole Depth@StudHoles", part.RING_HEIGHT / 1000.0),
        display("Thru Hole Dia.@StudHoles", 0.006045),
    ]
    feature = SimpleNamespace(
        GetFirstDisplayDimension=lambda: displays[0],
        GetNextDisplayDimension=lambda value: (
            displays[displays.index(value)+1] if value is not displays[-1] else None
        ),
    )
    part._tolerance_hanger_clearance(feature)
    native = displays[-1].GetDimension2(0).Tolerance
    assert native.Type == 2
    assert (native.GetMinValue(), native.GetMaxValue()) == pytest.approx(
        (0.0, 0.0001016), abs=1e-12,
    )
    assert displays[0].GetDimension2(0).Tolerance.Type == 0
    assert precisions[-1]["places"] == 3

    from win32com.client import dynamic

    def length_interface(raw, kind):
        assert kind == "ICalloutLengthVariable"
        return raw

    monkeypatch.setattr(drawing, "_early_bound", length_interface)
    monkeypatch.setattr(dynamic, "Dispatch", lambda pointer: pointer)
    # A plain HOLE-THRU callout's diameter variable is hw-diam; the
    # counterbore format's hw-thruholedia must not be mistaken for it.
    clearance = SimpleNamespace(VariableName="hw-diam")
    spot = SimpleNamespace(VariableName="hw-thruholedia", ToleranceType=0)
    # Only the late object exposes metadata; the concrete interface exposes
    # length precision. Binding it as generic ICalloutVariable must fail.
    raw_clearance = SimpleNamespace(_oleobj_=clearance, TolerancePrecision=0)
    raw_spot = SimpleNamespace(_oleobj_=spot, TolerancePrecision=0)
    callout = SimpleNamespace(
        GetHoleCalloutVariables=lambda: (raw_spot, raw_clearance)
    )
    drawing._tolerance_hanger_callout_clearance(callout)
    assert clearance.ToleranceType == 2
    assert (clearance.ToleranceMin, clearance.ToleranceMax) == pytest.approx(
        (0.0, 0.0001016), abs=1e-12,
    )
    assert raw_clearance.TolerancePrecision == 3
    assert spot.ToleranceType == 0 and raw_spot.TolerancePrecision == 0
    with pytest.raises(RuntimeError, match="through-diameter variable"):
        drawing._tolerance_hanger_callout_clearance(
            SimpleNamespace(GetHoleCalloutVariables=lambda: (raw_spot,)),
        )


def test_crossbar_median_control_cancels_the_socket_station_chain() -> None:
    assert spec.HANGER_CROSSBAR_CENTER_ZONE == pytest.approx(0.1016)  # .004
    assert spec.HANGER_CROSSBAR_CENTER_TOL == pytest.approx(0.0508)
    assert part.HANGER_BAR_HALF_WIDTH_MIN == pytest.approx(12.4333)


def test_hanger_x_locates_datum_d_not_a_hole() -> None:
    """182.0 runs from the upper-left socket axis to D's trace -- the native
    centreline between the crossbar's two side-face edges -- a plain .X
    locator; no competing hole-axis X dimension survives."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    block = source[source.index("# D's own station"):source.index("# #946:")]
    assert "crossbar_median_x = (BAR_X0 + BAR_X1) / 2.0" in block
    assert "_insert_crossbar_median(" in block and "_add_view_centerlines(" not in block
    # Sheet 2's proven flange-width picks: the two side faces' top edges.
    assert (
        "((BAR_X0, HALF_H-EDGE_CHAMFER, 0.0), (BAR_X1, HALF_H-EDGE_CHAMFER, 0.0))"
        in block
    )
    assert 'label="hanger x from left sockets"' in block
    assert "expected_mm=COLUMN_X + crossbar_median_x" in block
    # Typed coordinate pick (the documented CENTERLINE select type) at the
    # mid-bar point, clear of both holes; no entity re-key of the helper.
    assert 'entity_types=("EDGE", "CENTERLINE")' in block
    assert "p1=(crossbar_median_x, HALF_H, 0.0)" in block
    assert "entities=" not in block[block.index("_checked_dimension("):]
    assert (
        part.STUD_Z_FRONT + spec.HANGER_WASHER.OD_MAX
        < 0.0
        < part.STUD_Z_REAR - spec.HANGER_WASHER.OD_MAX
    )
    assert "center=True" in block
    assert "reference=" not in block and "set_basic_dimension" not in block
    assert drawing.CROSSBAR_MEDIAN_SUFFIX.endswith(", D")
    assert (part.BAR_X0 + part.BAR_X1) / 2.0 == pytest.approx(part.HANGER_X)


def test_crossbar_median_is_the_native_centreline_of_both_sides(monkeypatch) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(drawing, "_early_bound", lambda entity, _kind: entity)
    monkeypatch.setattr(drawing, "view_name", lambda *_args: "DETAIL TOP")
    state: dict = {}
    calls: list = []

    def side(name):
        def select4(append, data):
            calls.append(("Select4", name, append, data.View))
            state["count"] += state["per_pick"]
            return state["selected"]

        return SimpleNamespace(Select4=select4)

    sides = (side("left"), side("right"))
    annotation = SimpleNamespace(IsDangling=lambda: state["dangling"])
    centerline = SimpleNamespace(GetAnnotation=lambda: annotation)

    def insert():
        calls.append("InsertCenterLine2")
        state["centrelines"] += state["added"]
        return state["centerline"]

    model = SimpleNamespace(
        ActivateView=lambda _name: True,
        ClearSelection2=lambda _all: None,
        InsertCenterLine2=insert,
        SelectionManager=SimpleNamespace(
            CreateSelectData=lambda: SimpleNamespace(),
            GetSelectedObjectCount2=lambda _mark: state["count"],
        ),
    )
    adapter = SimpleNamespace(currentModel=model)
    view = SimpleNamespace(GetCenterLineCount=lambda: state["centrelines"])

    def reset(**changes) -> None:
        state.update(
            count=0, per_pick=1, selected=True, centrelines=3, added=1,
            centerline=centerline, dangling=False,
        )
        state.update(changes)
        calls.clear()

    reset()
    assert drawing._insert_crossbar_median(adapter, view, sides) is None
    assert calls == [
        ("Select4", "left", False, view),
        ("Select4", "right", True, view),
        "InsertCenterLine2",
    ]
    assert state["centrelines"] == 4
    for changes, message in (
        ({"selected": False}, "failed to select crossbar side 0"),
        ({"per_pick": 2}, "holds 4 entities, not 2"),
        ({"centerline": None}, "failed to insert"),
        ({"added": 0}, "with 3 centrelines, expected 4"),
        ({"added": 2}, "with 5 centrelines, expected 4"),
        ({"dangling": True}, "centreline is dangling"),
    ):
        reset(**changes)
        with pytest.raises(RuntimeError, match=message):
            drawing._insert_crossbar_median(adapter, view, sides)


def test_hanger_callout_and_frame_clear_the_border_and_each_other() -> None:
    """R4: the callout's +0.130 stack struck the 266.7 border and the frame
    sat on the upper-right boss.  Both now stand in the top band right of
    the 182.0 extension line, the frame's top under the border."""
    frame_x, frame_y = drawing.HANGER_CENTER_FRAME_XY
    callout_x, callout_y = drawing.HANGER_CALLOUT_XY
    assert frame_y < drawing.SHEET_FRAME[3] - 0.002
    # Frame box (5.5 mm) and qualifier row stand above the callout block.
    assert frame_y - 0.011 > callout_y + 0.009
    # The frame's leader leaves from its left end, left of the callout.
    assert frame_x < callout_x - 0.031 - 0.005
    # Right of the 182.0 (x 162 mm text) row's end at the hanger axis.
    assert frame_x > 0.190
    # The qualifier stays on the sheet (about 2.75 mm per glyph).
    assert frame_x + 0.00275 * len(drawing.HANGER_CENTER_QUALIFIER) < drawing.SHEET_FRAME[2]


# R5's native HOLES-SOCKETS leader runs (sheet m) behind its one enforced
# leader-crosses-leader: the then-Ø17 spotface callout's diameter run and
# the centring frame's run to its default clearance-rim landing.  R5 drew the
# plan centred at R5_PLAN_CENTER; the diameter run and the rim landing ride
# with the view, the frame (HANGER_CENTER_FRAME_XY) is placed on the sheet.
R5_PLAN_CENTER = (0.1910853, 0.160)
R5_HANGER_CALLOUT_RUN = ((0.1800, 0.1997), (0.1872, 0.2042))
R5_HANGER_FRAME_RUN = ((0.1936, 0.2605), (0.1826, 0.2009))


def _segment_crossing(a, b):
    (x1, y1), (x2, y2) = a
    (x3, y3), (x4, y4) = b
    det = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
    if det == 0.0:
        return None
    t = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / det
    u = ((x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1)) / det
    if not (0.0 <= t <= 1.0 and 0.0 <= u <= 1.0):
        return None
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def _point_to_segment(p, segment):
    (x1, y1), (x2, y2) = segment
    dx, dy = x2 - x1, y2 - y1
    t = max(0.0, min(1.0, ((p[0] - x1) * dx + (p[1] - y1) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (x1 + t * dx, y1 + t * dy))


def test_hanger_frame_lands_on_the_rim_clear_of_the_callout_leader() -> None:
    """R5: the frame's default landing on the clearance rim put its leader
    across the callout's diameter run at (182.7,201.4) mm.  It now lands on
    the same rim up-right of the axis, the frame's side of the callout's
    diameter, and right of D's trace (the 182.0 extension line)."""
    radius = spec.HANGER_CLEARANCE_DIA / 2.0 * _S
    frame_start, r5_landing = R5_HANGER_FRAME_RUN
    # The logged runs, in R5's view: the Ø17 rim's diameter through the axis,
    # and a run to the clearance rim, crossing where R5 reported.
    r5_centre = (
        R5_PLAN_CENTER[0] + part.HANGER_X * _S,
        R5_PLAN_CENTER[1] - part.STUD_Z_FRONT * _S,
    )
    r5_a, r5_b = R5_HANGER_CALLOUT_RUN
    assert math.dist(((r5_a[0] + r5_b[0]) / 2.0, (r5_a[1] + r5_b[1]) / 2.0), r5_centre) < 0.0002
    assert math.dist(r5_a, r5_b) == pytest.approx(17.0 * _S, abs=0.0002)
    assert math.dist(r5_landing, r5_centre) == pytest.approx(radius, abs=0.0002)
    assert _segment_crossing(R5_HANGER_CALLOUT_RUN, R5_HANGER_FRAME_RUN) == pytest.approx(
        (0.1827, 0.2014), abs=1e-4,
    )
    # The same view-attached ink where the plan now stands (it follows the
    # keeper transfer shift); the frame stays where it is placed.
    centre = _plan(part.HANGER_X, part.STUD_Z_FRONT)
    dx, dy = centre[0] - r5_centre[0], centre[1] - r5_centre[1]
    callout_a, callout_b = ((x + dx, y + dy) for x, y in R5_HANGER_CALLOUT_RUN)
    callout_run = (callout_a, callout_b)
    old_landing = (r5_landing[0] + dx, r5_landing[1] + dy)
    # The landing: a real point on the selected clearance rim at the finished
    # top, at the declared bearing, between the callout's run and D's trace.
    x, y, z = drawing.hanger_center_landing()
    assert y == part.HALF_H
    assert math.hypot(x - part.HANGER_X, z - part.STUD_Z_FRONT) == pytest.approx(
        spec.HANGER_CLEARANCE_DIA / 2.0
    )
    landing = _plan(x, z)
    assert math.dist(landing, centre) == pytest.approx(radius)
    bearing = math.degrees(math.atan2(landing[1] - centre[1], landing[0] - centre[0]))
    assert bearing == pytest.approx(drawing.HANGER_CENTER_LANDING_DEG)
    callout_bearing = math.degrees(
        math.atan2(callout_b[1] - callout_a[1], callout_b[0] - callout_a[0])
    )
    assert callout_bearing + 15.0 < bearing < 90.0
    # A different rim point from R5's default, not a nudge of it.
    assert math.dist(landing, old_landing) > radius

    def side(p):
        return (callout_b[0] - callout_a[0]) * (p[1] - callout_a[1]) - (
            callout_b[1] - callout_a[1]
        ) * (p[0] - callout_a[0])

    # R5's landing sat across the callout's diameter from the frame; the new
    # one shares the frame's side, so the run cannot cross it.
    assert side(old_landing) < 0.0 < side(frame_start)
    assert side(landing) > 0.0
    rerouted = (frame_start, landing)
    assert _segment_crossing(callout_run, rerouted) is None
    gap = min(
        *(_point_to_segment(p, callout_run) for p in rerouted),
        *(_point_to_segment(p, rerouted) for p in callout_run),
    )
    assert gap > 0.0005 > drawing.ARROW_HALF_WIDTH
    # Wholly right of D's trace: the 182.0 extension line is never reached.
    assert min(landing[0], frame_start[0]) - centre[0] > drawing.ARROW_HALF_WIDTH


def test_hanger_frame_keeps_its_exact_edge_and_lands_by_selection_point() -> None:
    import ast

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    (frame,) = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "add_feature_control_frame"
        and any(
            keyword.arg == "label"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "hanger axes on crossbar median plane"
            for keyword in node.keywords
        )
    ]
    keywords = {k.arg: k.value for k in frame.keywords}
    names = {
        arg: keywords[arg].id
        for arg in ("edge_entity", "leader_attach_xy", "frame_xy", "quantity")
        if isinstance(keywords[arg], ast.Name)
    }
    assert names == {
        "edge_entity": "hanger_hole_edge",
        "leader_attach_xy": "hanger_center_landing_xy",
        "frame_xy": "HANGER_CENTER_FRAME_XY",
        "quantity": "HANGER_CENTER_QUALIFIER",
    }
    assert ast.literal_eval(keywords["datums"]) == ("D",)
    assert "diameter" not in keywords and "edge_xy" not in keywords
    (landing,) = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and [getattr(t, "id", None) for t in node.targets] == ["hanger_center_landing_xy"]
    ]
    assert isinstance(landing, ast.Call) and landing.func.id == "model_point_in_view"
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "hanger_center_landing"
        for node in ast.walk(landing)
    )


def test_crossbar_datum_requires_the_exact_native_width_attachment(monkeypatch) -> None:
    import inspect
    from types import SimpleNamespace

    monkeypatch.setattr(drawing, "_early_bound", lambda entity, _kind: entity)
    monkeypatch.setattr(drawing, "view_name", lambda *_args: "GEOMETRY")
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    callout = object()
    monkeypatch.setattr(drawing, "null_callout", lambda: callout)
    monkeypatch.setattr(drawing, "dispatch_array", list)
    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        drawing._telemetry, "event", lambda name, **attrs: events.append((name, attrs)),
    )
    name, full_name = "RD1@Drawing View1", "CrossbarWidth@Drawing"

    def stale_select(*_args):
        raise AssertionError("pre-rebuild width: IAnnotation.Select3 server fault")

    # _checked_dimension's handle, captured before offset_dimension_text's
    # rebuild: it supplies identity only; selecting through it is R3's fault.
    width = SimpleNamespace(
        GetNameForSelection=lambda: name,
        GetDimension2=lambda _index: SimpleNamespace(FullName=full_name),
        GetAnnotation=lambda: SimpleNamespace(Select3=stale_select),
    )

    def display(selection_name=name, dimension_name=full_name, annotation_type=4):
        # One IAnnotation per display: the clearance guard reads it by identity.
        annotation = SimpleNamespace(GetType=lambda: annotation_type, GetName=lambda: "RD1")
        return SimpleNamespace(
            GetNameForSelection=lambda: selection_name,
            GetDimension2=lambda _index: SimpleNamespace(FullName=dimension_name),
            GetAnnotation=lambda: annotation,
        )

    fresh = display()
    state: dict = {}
    calls: list = []

    def reset(**changes) -> None:
        state.update(
            displays=(display("RD2@Drawing View1", "OtherWidth@Drawing"), fresh),
            selected=True, count=1, kind=14, picked=fresh, types=(14,), attached=fresh,
            attached_count=1, accepts=(),
        )
        state.update(changes)
        calls.clear()
        events.clear()

    def set_attached(entities) -> bool:
        (target,) = entities
        calls.append(("SetAttachedEntities", target))
        if target in state["accepts"]:
            state["attached_count"] = 1
            return True
        return False

    annotation = SimpleNamespace(
        SetPosition2=lambda *_args: True,
        GetAttachedEntityTypes=lambda: state["types"],
        GetAttachedEntities3=lambda: (state["attached"],),
        GetAttachedEntityCount3=lambda: state["attached_count"],
        SetAttachedEntities=set_attached,
        IsDangling=lambda: False,
    )
    tag = SimpleNamespace(
        SetLabel=lambda text: text == "D", GetLabel=lambda: "D",
        GetAnnotation=lambda: annotation,
    )

    def select(*args):
        calls.append(("SelectByID2", args))
        return state["selected"]

    def insert():
        calls.append("InsertDatumTag2")
        return tag

    model = SimpleNamespace(
        ActivateView=lambda _name: True,
        ClearSelection2=lambda _all: calls.append("ClearSelection2"),
        InsertDatumTag2=insert,
        Extension=SimpleNamespace(SelectByID2=select),
        SelectionManager=SimpleNamespace(
            # A real ISelectionMgr member: the old path reaches the stale Select3.
            CreateSelectData=lambda: SimpleNamespace(),
            GetSelectedObjectCount2=lambda _mark: state["count"],
            GetSelectedObjectType3=lambda _index, _mark: state["kind"],
            GetSelectedObject6=lambda _index, _mark: state["picked"],
        ),
    )
    adapter = SimpleNamespace(
        currentModel=model, swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)),
    )
    view = SimpleNamespace(GetDisplayDimensions=lambda: state["displays"])

    tag_display, width_display = _r6_crossbar_datum_display_data()

    def read_display(_adapter, entity):
        if entity is annotation:
            calls.append(("annotation_display", "D"))
            return tag_display, {}
        assert entity is fresh.GetAnnotation()
        calls.append(("annotation_display", "crossbar width"))
        return width_display, {}

    monkeypatch.setattr(drawing, "annotation_display", read_display)

    reset()
    drawing._crossbar_median_datum(adapter, view, width)
    assert calls == [
        "ClearSelection2",
        ("SelectByID2", (name, "DIMENSION", 0.0, 0.0, 0.0, False, 0, callout, 0)),
        "InsertDatumTag2",
        "ClearSelection2",
        ("annotation_display", "D"),
        ("annotation_display", "crossbar width"),
    ]
    assert events == [
        ("drawing.crossbar_width.target", {
            "selection_name": name, "matches": 1, "annotation_type": 4,
            "annotation_name": "RD1", "full_name": full_name,
            "expected_full_name": full_name,
        }),
        ("drawing.crossbar_width.selection", {
            "count": 1, "type": 14, "selection_name": name, "full_name": full_name,
        }),
        ("drawing.crossbar_width.attach_attempts", {"inserted_count": 1, "attempts": ""}),
        ("drawing.crossbar_width.attachment", {
            "count": 1, "types": "(14,)", "objects": "('SimpleNamespace',)",
        }),
        ("drawing.crossbar_width.datum_clearance", {
            "datum_box": "122.67/106.00/135.83/113.00",
            "rows": "crossbar width row 0 '25.0' 103.97/104.60/113.03/108.10; "
            "crossbar width row 1 'CROSSBAR FLANGE' 86.76/99.04/130.24/102.54",
        }),
    ]
    body = inspect.getsource(drawing._crossbar_median_datum)
    assert "Select3" not in body and "CreateSelectData" not in body and ".View =" not in body

    # Fresh re-resolution refuses before anything is selected.
    for changes, matches, message in (
        ({"displays": ()}, 0, "found 0"),
        ({"displays": (fresh, display())}, 2, "found 2"),
        ({"displays": (display(annotation_type=1),)}, 1, "annotation type 1"),
        ({"displays": (display(dimension_name="OtherWidth@Drawing"),)}, 1, "re-resolved"),
    ):
        reset(**changes)
        with pytest.raises(RuntimeError, match=message):
            drawing._crossbar_median_datum(adapter, view, width)
        assert calls == ["ClearSelection2"]
        assert [event[1]["matches"] for event in events] == [matches]

    reset(selected=False)
    with pytest.raises(RuntimeError, match="failed to select crossbar width"):
        drawing._crossbar_median_datum(adapter, view, width)
    assert "InsertDatumTag2" not in calls

    # The read-back must be the ONE width, by name AND FullName, before D.
    for changes in (
        {"count": 0},
        {"count": 2},
        {"kind": 13},
        {"picked": display("RD2@Drawing View1")},
        {"picked": display(dimension_name="OtherWidth@Drawing")},
    ):
        reset(**changes)
        with pytest.raises(RuntimeError, match="selecting crossbar width selected"):
            drawing._crossbar_median_datum(adapter, view, width)
        assert "InsertDatumTag2" not in calls and calls[-1] == "ClearSelection2"

    reset(types=(1,))
    with pytest.raises(RuntimeError, match="not attached to the width"):
        drawing._crossbar_median_datum(adapter, view, width)
    # An unattached tag is offered the display dimension, then its annotation;
    # the first accepted attachment stops the attempts.
    reset(attached_count=0, accepts=(fresh,))
    drawing._crossbar_median_datum(adapter, view, width)
    assert [call for call in calls if call[0] == "SetAttachedEntities"] == [
        ("SetAttachedEntities", fresh),
    ]
    assert ("drawing.crossbar_width.attach_attempts", {
        "inserted_count": 0, "attempts": "display_dimension:True:1",
    }) in events
    # Both rejected: both are tried, and the readback still refuses.
    reset(attached_count=0, types=())
    with pytest.raises(RuntimeError, match="not attached to the width"):
        drawing._crossbar_median_datum(adapter, view, width)
    assert len([call for call in calls if call[0] == "SetAttachedEntities"]) == 2
    assert ("drawing.crossbar_width.attach_attempts", {
        "inserted_count": 0, "attempts": "display_dimension:False:0,annotation:False:0",
    }) in events
    # Equal FullName is not enough: D must sit on the re-resolved display.
    for attached in (display(dimension_name="DifferentWidth@Drawing"), width):
        reset(attached=attached)
        with pytest.raises(RuntimeError, match="exact crossbar width attachment"):
            drawing._crossbar_median_datum(adapter, view, width)


def _r6_crossbar_datum_display_data(*, text_y=None):
    # Native IDisplayData from R6, 20261014T055244900Z, GEOMETRY sheet RD6
    # and DetailItem389.  Move only the two width-text rows, not D's default
    # drop or attachment.  Coordinates are sheet metres, not PNG estimates.
    if text_y is None:
        text_y = drawing.CROSSBAR_FLANGE_TEXT_OFFSET_XY[1]
    shift = text_y - 0.108
    datum = {
        "lines": [
            [0, 0, 0, 0, 0.1358333, 0.1095, 0, 0.1296667, 0.1095, 0],
            [0, 0, 0, 0, 0.1296667, 0.106, 0, 0.1226667, 0.106, 0],
            [0, 0, 0, 0, 0.1226667, 0.106, 0, 0.1226667, 0.113, 0],
            [0, 0, 0, 0, 0.1226667, 0.113, 0, 0.1296667, 0.113, 0],
            [0, 0, 0, 0, 0.1296667, 0.113, 0, 0.1296667, 0.106, 0],
        ],
        "triangles": [[
            0.1358333, 0.1081, 0, 0.1358333, 0.1109, 0,
            0.1333833, 0.1095, 0, 1, 0,
        ]],
        "texts": [{
            "t": "D", "pos": [0.1244312, 0.1067219, 0],
            "h": 0.0035, "w": 0.0034708, "ang": 0.0, "ref": 1,
        }],
    }
    width = {"texts": [
        {
            "t": "25.0", "pos": [0.1039743, 0.108 + shift, 0],
            "h": 0.0035, "w": 0.0090514, "ang": 0.0, "ref": 1,
        },
        {
            "t": "CROSSBAR FLANGE", "pos": [0.0867635, 0.1024437 + shift, 0],
            "h": 0.0035, "w": 0.0434729, "ang": 0.0, "ref": 1,
        },
    ]}
    return datum, width


def _check_crossbar_datum_ink(monkeypatch, datum_display, width_display, *, refused=None):
    datum, width = object(), object()

    def read_display(_adapter, annotation):
        index = 0 if annotation is datum else 1
        assert annotation is datum or annotation is width
        return (datum_display, width_display)[index], (refused or ({}, {}))[index]

    monkeypatch.setattr(drawing, "annotation_display", read_display)
    drawing._require_datum_d_clear_of_width_text(object(), datum, width)


def test_crossbar_datum_ink_refuses_the_native_r6_overprint(monkeypatch) -> None:
    datum, width = _r6_crossbar_datum_display_data(text_y=0.108)
    with pytest.raises(RuntimeError, match="datum D ink.*CROSSBAR FLANGE"):
        _check_crossbar_datum_ink(monkeypatch, datum, width)


def test_crossbar_datum_ink_clears_each_moved_width_row_not_the_block(monkeypatch) -> None:
    from _drawing_annotation_extent import boxes_clear
    from _layout_audit import display_box

    assert drawing.CROSSBAR_FLANGE_TEXT_OFFSET_XY == (0.1085, 0.1046)
    datum, width = _r6_crossbar_datum_display_data()
    tag_box, block_box = display_box(datum), display_box(width)
    assert tag_box is not None and block_box is not None
    # The 25.0 row remains level with D but safely to its left; the wide
    # suffix is below D.  Their union box falsely reports a collision.
    assert not boxes_clear(
        (tag_box.xmin, tag_box.ymin, tag_box.xmax, tag_box.ymax),
        (block_box.xmin, block_box.ymin, block_box.xmax, block_box.ymax),
    )
    suffix = display_box({"texts": [width["texts"][1]]})
    assert suffix is not None
    assert tag_box.ymin - suffix.ymax == pytest.approx(0.0034563)
    _check_crossbar_datum_ink(monkeypatch, datum, width)


@pytest.mark.parametrize("gap", (0.002, 0.002001, 0.001999))
def test_crossbar_datum_ink_keeps_the_two_mm_clearance(monkeypatch, gap) -> None:
    datum, width = _r6_crossbar_datum_display_data()
    width["texts"][1]["pos"][1] = 0.106 - 0.0035 - gap
    if gap < 0.002:
        with pytest.raises(RuntimeError, match="datum D ink.*CROSSBAR FLANGE"):
            _check_crossbar_datum_ink(monkeypatch, datum, width)
    else:
        _check_crossbar_datum_ink(monkeypatch, datum, width)


@pytest.mark.parametrize("index", (0, 1), ids=("datum-D", "crossbar-width"))
def test_crossbar_datum_ink_refuses_unreadable_native_data(monkeypatch, index) -> None:
    displays = list(_r6_crossbar_datum_display_data())
    refused = [{}, {}]
    refused[index] = {"GetDisplayData": 1}
    with pytest.raises(RuntimeError, match="both native display reads.*refused"):
        _check_crossbar_datum_ink(monkeypatch, *displays, refused=refused)
    displays[index] = {}
    with pytest.raises(RuntimeError, match="both native display reads.*empty"):
        _check_crossbar_datum_ink(monkeypatch, *displays)


@pytest.mark.parametrize("index", (0, 1), ids=("datum-D", "crossbar-width"))
@pytest.mark.parametrize("reported_width", (None, 0.0, -0.001))
def test_crossbar_datum_ink_refuses_estimated_native_widths(
    monkeypatch, index, reported_width
) -> None:
    displays = list(_r6_crossbar_datum_display_data())
    displays[index]["texts"][0]["w"] = reported_width
    with pytest.raises(RuntimeError, match="reported no width"):
        _check_crossbar_datum_ink(monkeypatch, *displays)


def test_crossbar_datum_ink_requires_the_D_label(monkeypatch) -> None:
    datum, width = _r6_crossbar_datum_display_data()
    datum["texts"][0]["t"] = "B"
    with pytest.raises(RuntimeError, match="prints no 'D'"):
        _check_crossbar_datum_ink(monkeypatch, datum, width)


@pytest.mark.parametrize(("field", "value"), (("h", 0.0), ("pos", [])))
def test_crossbar_datum_ink_requires_visible_D_text(monkeypatch, field, value) -> None:
    datum, width = _r6_crossbar_datum_display_data()
    datum["texts"][0][field] = value
    with pytest.raises(RuntimeError, match="prints no 'D'"):
        _check_crossbar_datum_ink(monkeypatch, datum, width)


@pytest.mark.parametrize("invalid", ("no-rows", "empty-row", "no-height", "no-position"))
def test_crossbar_datum_ink_refuses_missing_width_text(monkeypatch, invalid) -> None:
    datum, width = _r6_crossbar_datum_display_data()
    if invalid == "no-rows":
        width["texts"] = []
        message = "prints no text"
    else:
        row = width["texts"][1]
        if invalid == "empty-row":
            row["t"] = ""
        elif invalid == "no-height":
            row["h"] = 0.0
        else:
            row["pos"] = []
        message = "text run 1 draws nothing"
    with pytest.raises(RuntimeError, match=message):
        _check_crossbar_datum_ink(monkeypatch, datum, width)


def test_finished_grip_is_the_crossbars_own_driving_depth() -> None:
    """User ruling 2026-10-14: the whole top is faced on the plane the model
    carries, so the grip is the crossbar's full-height extrude depth,
    finished top to finished underside, driven by RingHeight.  Owner ruling
    2026-10-18: it takes the title block's general band (.XXX on the inch
    sheet), no model band, and each MHA-SM-VN-52 is cut to the measured grip
    at MHA-SM-00."""
    assert spec.HANGER_GRIP == part.RING_HEIGHT == pytest.approx(36.4998)  # 1.437
    assert spec.HANGER_GRIP_PLACES == 3
    assert spec.HANGER_GRIP_TOL == spec.PRINTED_LINEAR_BAND_MM[3] == pytest.approx(0.127)
    assert not hasattr(spec, "HANGER_GRIP_CALLOUT")
    # The model owns the grip and its places; the sheet imports it.
    assert spec.DRAWING_DIMENSIONS["Crossbar"] == {"HangerGrip"}
    assert spec.DRAWING_PRECISION_BY_NAME["HangerGrip"] == spec.HANGER_GRIP_PLACES
    # The rail height is that same thickness, the web ring's own driving
    # depth, marked at the grip's places for its reference in the front view.
    assert spec.DRAWING_DIMENSIONS["WebRing"] == {"RingHeight"}
    assert spec.DRAWING_PRECISION_BY_NAME["RingHeight"] == spec.HANGER_GRIP_PLACES
    # The hidden reference sketch and its depth equation are gone, not aliased.
    for name in ("HANGER_GRIP_SKETCH", "REFERENCE_SKETCHES"):
        assert not hasattr(spec, name)
    for name in (
        "HANGER_GRIP_DIMENSION",
        "HANGER_SPOTFACE_DEPTH_DRIVE",
        "_assert_hanger_grip_drives_spotface",
        "_hanger_spotface_depth_name",
    ):
        assert not hasattr(part, name)
    build = Path(part.__file__).read_text(encoding="utf-8")
    compact = "".join(build.split())
    assert "HangerGripReference" not in build and "blank_reference_sketches" not in build
    assert 'set_global(adapter,"HangerGrip"' not in compact
    body = compact[compact.index("asyncdefbuild("):]
    steps = [
        'name_last_feature(adapter,"Crossbar")',
        'grip_dim=name_dimensions(adapter,"Crossbar",["HangerGrip"])',
        "drive_jobs.append((grip_dim[0],'\"RingHeight\"'))",
        "fordim_name,exprindrive_jobs:awaitdrive_dimension(adapter,dim_name,expr)",
        "save_part_and_images(adapter,PART_NAME)",
    ]
    assert all(body.count(step) == 1 for step in steps)
    assert [body.index(step) for step in steps] == sorted(
        body.index(step) for step in steps
    )
    assert '"Crossbar","HangerGrip"' not in compact[compact.index("asyncdefbuild("):]
    # The sheet only reads the model's grip back: no drawing-owned band.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_tolerance_hanger_grip" not in source
    start = source.index("def _hanger_section(")
    section = source[start:source.index("\ndef ", start+1)]
    helper_start = source.index("def _require_model_hanger_grip(")
    helper = source[helper_start:source.index("\ndef ", helper_start+1)]
    for text in (section, helper):
        assert ".Type =" not in text
        assert "SetValues" not in text
        assert "_set_tolerance_precision" not in text
    assert "floor_edge" not in section
    assert "underside_edge" not in section
    assert "keep=HANGER_SECTION_KEEP," in section
    assert section.count("curate_view_dimensions(") == 1
    assert "_require_model_hanger_grip(adapter, dimensions)" in section
    assert 'owner != ["HangerGrip", "Crossbar"]' in helper
    # No hidden sketch is shown for F-F: it cuts the crossbar extrude itself.
    for name in ("part_sketches_shown", "curate_hidden_sketch_dimensions", "source_model"):
        assert name not in source
    underside = source[source.index('ddoc.ActivateSheet("UNDERSIDE")') :]
    assert (
        "\n    hanger_section, hanger_dimensions = _hanger_section(adapter, hub_bottom_parent)\n"
        in underside
    )


class _ReadOnlyTolerance:
    """A model band the sheet may read but never write."""

    def __init__(self, kind, low_m, high_m):
        object.__setattr__(self, "_band", (kind, low_m, high_m))

    @property
    def Type(self):
        return self._band[0]

    def GetMinValue(self):
        return self._band[1]

    def GetMaxValue(self):
        return self._band[2]

    def SetValues(self, *_args):
        raise AssertionError("the sheet re-toleranced the model's grip")

    def __setattr__(self, name, _value):
        raise AssertionError(f"the sheet wrote the model grip's {name}")


def _imported_grip(
    *, full_name="HangerGrip@Crossbar@fr-top-frame.Part",
    mm=spec.HANGER_GRIP, kind=0, band_mm=0.0, name="HangerGrip",
):
    from types import SimpleNamespace

    dimension = SimpleNamespace(
        FullName=full_name, SystemValue=mm / 1000.0,
        Tolerance=_ReadOnlyTolerance(kind, -band_mm / 1000.0, band_mm / 1000.0),
    )
    display = SimpleNamespace(GetDimension2=lambda _index: dimension)
    return SimpleNamespace(name=name, GetSpecificAnnotation=lambda: display)


def test_section_reads_the_model_grip_back_without_writing_it(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, item: item.name)
    other = _imported_grip(name="HangerPinHoleDepth")
    grip = _imported_grip()
    assert drawing._require_model_hanger_grip(None, [other, grip]) is grip
    for dimensions, match in (
        ([other], "imported 0 HangerGrip"),
        ([grip, _imported_grip()], "imported 2 HangerGrip"),
        ([_imported_grip(full_name="HangerGrip@Drawing View7@x")], "not the model's"),
        ([_imported_grip(full_name="HangerGrip@HangerGripReference@x")], "not the model's"),
        ([_imported_grip(full_name="RingHeight@WebRing@x")], "not the model's"),
        ([_imported_grip(mm=36.45)], "reads"),
        ([_imported_grip(kind=4, band_mm=0.05)], "carries a band"),
        ([_imported_grip(kind=2, band_mm=0.05)], "carries a band"),
    ):
        with pytest.raises(RuntimeError, match=match):
            drawing._require_model_hanger_grip(None, dimensions)


def test_geometry_front_prints_the_models_rail_height_as_a_reference() -> None:
    """fd0350a85 dropped the geometry front view's only dimension, leaving
    the rail web's depth undefined on sheet 2.  It is back as the model's own
    RingHeight -- the web ring's driving extrude depth, the same finished
    thickness F-F prints as the grip -- printed as a reference at the grip's
    places, so the grip alone carries the .XX band."""
    import ast

    from _drawing_dimension_import import _features_owning

    assert drawing.GEOMETRY_FRONT_KEEP == {"RingHeight": (0.238, 0.091)}
    assert drawing.GEOMETRY_CALLOUTS["RingHeight"] == "RAIL HEIGHT"
    assert _features_owning(
        spec.DRAWING_DIMENSIONS, drawing.GEOMETRY_FRONT_KEEP, view_label="geometry front"
    ) == ("WebRing",)
    assert spec.DRAWING_DIMENSIONS["WebRing"] == {"RingHeight"}
    assert spec.DRAWING_PRECISION_BY_NAME["RingHeight"] == spec.HANGER_GRIP_PLACES == 3
    assert part.RING_HEIGHT == spec.HANGER_GRIP == pytest.approx(36.4998)
    # The model drives the depth and authors no band on it: no tolerance call
    # in the build names the web ring or its dimension.
    build = Path(part.__file__).read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(build)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        called = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if "tolerance" in called.lower():
            literals = {arg.value for arg in node.args if isinstance(arg, ast.Constant)}
            assert not literals & {"WebRing", "RingHeight"}, called
    compact = "".join(build.split())
    assert compact.count('ring_height_dim=name_dimensions(adapter,"WebRing",["RingHeight"])') == 1
    assert compact.count("drive_jobs.append((ring_height_dim[0],'\"RingHeight\"'))") == 1
    # The sheet imports it once, callouts it, marks it after the callout and
    # reads its places back with every other import.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build("):]
    steps = [
        "keep=GEOMETRY_FRONT_KEEP,",
        "geometry_annotations = [*geometry_top_dimensions, *geometry_front_dimensions]",
        "set_dimension_callouts(adapter, geometry_annotations, geometry_callouts)",
        "_reference_model_rail_height(adapter, geometry_front_dimensions)",
        "imported_annotations = [*geometry_annotations]",
    ]
    assert all(body.count(step) == 1 for step in steps)
    assert [body.index(step) for step in steps] == sorted(
        body.index(step) for step in steps
    )
    # Never a free-text thickness: no string the print's modules author
    # spells it, so the only 1.437s on paper are the model's dimensions.
    for module in (spec, drawing):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        assert not [
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "1.437" in node.value
        ], module.__name__


def _imported_rail(**overrides):
    fields = {
        "full_name": "RingHeight@WebRing@fr-top-frame.Part",
        "mm": part.RING_HEIGHT, "kind": 0, "band_mm": 0.0, "name": "RingHeight",
    }
    fields.update(overrides)
    return _imported_grip(**fields)


def test_front_view_reads_the_model_rail_height_before_marking_it(monkeypatch) -> None:
    marked = []
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, item: item.name)
    monkeypatch.setattr(
        drawing, "set_reference_dimension",
        lambda _adapter, annotation, *, label: marked.append((annotation, label)),
    )
    other = _imported_rail(name="Width", full_name="Width@OuterProfile@fr-top-frame.Part")
    rail = _imported_rail()
    assert drawing._reference_model_rail_height(None, [other, rail]) is rail
    assert marked == [(rail, "rail height")]
    marked.clear()
    for dimensions, match in (
        ([other], "imported 0 RingHeight"),
        ([rail, _imported_rail()], "imported 2 RingHeight"),
        ([_imported_rail(full_name="RingHeight@Drawing View4@x")], "not the model's"),
        ([_imported_rail(full_name="HangerGrip@Crossbar@x")], "not the model's"),
        ([_imported_rail(mm=36.45)], "reads"),
        ([_imported_rail(kind=4, band_mm=0.05)], "competes"),
    ):
        with pytest.raises(RuntimeError, match=match):
            drawing._reference_model_rail_height(None, dimensions)
    assert not marked


# Sheet 2's Section E-E outline starts at x 285.4 mm (c674 run
# 20261015T003137335Z layout audit).
_EE_OUTLINE_XMIN = 0.2854


def test_rail_height_stands_between_its_arrows_right_of_the_front_view() -> None:
    """The value row prints on its text point and RAIL HEIGHT one row pitch
    under it (r6 run 20261014T055244900Z), both between the rail's top and
    bottom, right of the corner-boss barrel, clear of E-E and the frame."""
    ink = drawing.INK_CLEARANCE
    s = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1] / 1000.0
    x, y = drawing.GEOMETRY_FRONT_KEEP["RingHeight"]
    rows = ("(1.437)", drawing.GEOMETRY_CALLOUTS["RingHeight"])
    half_w = max(map(len, rows)) * _ROW_CHAR / 2.0
    block = (x - half_w, y - _ROW_PITCH, x + half_w, y + _ROW_PITCH - _ROW_SLACK)
    rail_bottom = _FRONT_VIEW_TOP_Y - part.RING_HEIGHT * s
    assert block[1] > rail_bottom
    assert _FRONT_VIEW_TOP_Y - block[3] >= ink
    barrel_right = drawing.GEOMETRY_FRONT_CENTER[0] + drawing.PLAN_HALF_X * s
    assert block[0] - barrel_right >= ink
    assert _EE_OUTLINE_XMIN - block[2] >= ink
    frame = drawing.SHEET_FRAME
    assert frame[0] + ink <= block[0] and block[2] <= frame[2] - ink
    assert _box_box_gap(block, TITLE_BLOCK) >= ink


def test_section_imports_the_grip_and_depth_and_the_locator_the_ream_size() -> None:
    """d8fac576 leaf 20261014T212023Z-1-90af84a0: since the faced top, F-F
    receives no HangerPinHoleDia even imported apart from the grip.  F-F
    imports the grip and the depth in one targeted pass (fd0350a85746 leaf
    20261014T203505Z-1-494a6e80 delivered both from one selection); the
    ream size prints once, face-on in the underside locator, on the rear +X
    circle that owns it, and the knockouts take a native callout there."""
    from _drawing_dimension_import import _features_owning

    assert set(drawing.HANGER_SECTION_KEEP) == set(drawing.HANGER_SECTION_CALLOUTS) == {
        "HangerGrip", "HangerPinHoleDepth",
    }
    assert _features_owning(
        spec.DRAWING_DIMENSIONS, drawing.HANGER_SECTION_KEEP, view_label="F-F"
    ) == ("Crossbar", "HangerPinHoles")
    assert _features_owning(
        spec.DRAWING_DIMENSIONS, ("HangerPinHoleDia",),
        view_label="underside locator",
    ) == ("HangerPinProfile",)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for retired in (
        "HANGER_SECTION_IMPORTS", "HANGER_PIN_DIA_OFFSET_XY", "_hanger_slot_detail",
        "SLOT_DETAIL", "HangerSlot", "HANGER_SLOT",
    ):
        assert retired not in source, retired
    underside = source[source.index('ddoc.ActivateSheet("UNDERSIDE")') :]
    locator = underside[: underside.index("_hanger_section(adapter, hub_bottom_parent)")]
    assert source.count('keep={"HangerPinHoleDia": HANGER_PIN_DIA_TEXT_XY},') == 1
    assert 'keep={"HangerPinHoleDia": HANGER_PIN_DIA_TEXT_XY},' in locator
    assert '{"HangerPinHoleDia": HANGER_PIN_HOLE_CALLOUT},' in locator
    assert locator.count("imported_annotations += locator_dimensions") == 1
    # The face-on diameter keeps its own leader: no locator text is offset.
    assert "offset_dimension_text(\n        adapter, locator_dimensions" not in locator
    # The knockouts: native callout on the front -X ream's knockout floor,
    # the ream's coaxial step cleared, the drill above and purpose below.
    knockout = locator[locator.index("knockouts = add_native_hole_callout(") :]
    assert "callout_xy=HANGER_KNOCKOUT_CALLOUT_XY," in knockout
    assert (
        "(PIN_HOLE_NEG_X, -HALF_H + HANGER_PIN_HOLE_DEPTH, STUD_Z_FRONT),\n"
        "            HANGER_KNOCKOUT_DIA/2,"
    ) in knockout
    assert "_drop_coaxial_step(knockouts, HANGER_PIN_HOLE_DIA," in knockout
    assert "knockouts, 3, HANGER_KNOCKOUT_CALLOUT_ABOVE," in knockout
    assert "knockouts, 4, HANGER_KNOCKOUT_CALLOUT_BELOW," in knockout
    # codjiflo round 4: the native size prints the drill's three places
    # (Ø1.702, not Ø1.78 beside a #50 row), set per variable and read back.
    assert (
        "    set_hole_callout_precision(\n"
        "        knockouts,\n"
        '        {"hw-diam": HANGER_KNOCKOUT_DIA_PLACES},\n'
    ) in knockout
    assert knockout.index("HANGER_KNOCKOUT_CALLOUT_BELOW,") < knockout.index(
        "HANGER_KNOCKOUT_DIA_PLACES"
    )


def test_coaxial_step_guard_clears_only_a_step_alone() -> None:
    """codjiflo round 3: the knockout callout's coaxial-step guard counted
    only the ream-diameter matches, so a part holding the step AND the
    knockout's own size passed and was wiped whole.  A part naming the
    step clears only when it holds the step alone (with its own depth);
    any other hole content raises before anything is cleared."""
    ream = spec.HANGER_PIN_HOLE_DIA
    holders = drawing._coaxial_step_holders
    # The step alone, at either place count, with or without its depth.
    assert holders(
        {5: "<MOD-DIAM>.124<HOLE-DEPTH>.470", 6: "<MOD-DIAM><hw-diam> THRU ALL", 7: "", 8: ""},
        ream, "knockouts",
    ) == [5]
    assert holders({5: "", 6: "<MOD-DIAM>.1240 \r\n", 7: "", 8: ""}, ream, "knockouts") == [6]
    # codjiflo round 5: SolidWorks may print the step behind the
    # counterbore symbol, all in one part; the part still holds only the step.
    assert holders(
        {5: "<HOLE-SPOT><MOD-DIAM>.124<HOLE-DEPTH>.47", 6: "<MOD-DIAM><hw-diam> THRU ALL",
         7: "", 8: ""},
        ream, "knockouts",
    ) == [5]
    assert holders(
        {5: "<MOD-DIAM>.067 THRU ALL", 6: "", 7: "", 8: ""}, ream, "knockouts"
    ) == []
    # The step mixed with the knockout's size, a THRU, a token, a second
    # depth, a symbol after the size or twice, or not first: raise.
    for mixed in (
        "<MOD-DIAM>.124<HOLE-DEPTH>.470\n<MOD-DIAM>.078<HOLE-DEPTH>.965",
        "<MOD-DIAM>.124\n<MOD-DIAM>.067",
        "<MOD-DIAM>.124 THRU ALL",
        "<MOD-DIAM>.124<HOLE-DEPTH>.470<HOLE-DEPTH>.965",
        "<MOD-DIAM>.124 <hw-diam>",
        "<MOD-DIAM>.067\n<MOD-DIAM>.124",
        "<HOLE-SPOT><MOD-DIAM>.124<HOLE-DEPTH>.47\n<MOD-DIAM>.067 THRU ALL",
        "<HOLE-SPOT><HOLE-SPOT><MOD-DIAM>.124",
        "<HOLE-SINK><MOD-DIAM>.124",
        "<MOD-DIAM>.124<HOLE-SPOT>",
    ):
        with pytest.raises(RuntimeError, match="coaxial step mixed into part 5"):
            holders({5: mixed, 6: "", 7: "", 8: ""}, ream, "knockouts")
    # The COM wrapper validates every part before its first SetText.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("def _drop_coaxial_step(") :]
    body = body[: body.index("\ndef ")]
    assert body.index("_coaxial_step_holders(") < body.index("display.SetText(")


def test_dowel_press_ream_contract() -> None:
    """Owner ruling 2026-10-24 (T+H3): both MHA-SM-VN-53 dowels press into
    blind flat-floor reams at the dowel spec's press band, each +X ream .XXX
    .300 from its own screw axis, each -X ream BASIC .600 from it under
    a Ø.002 position zone (the knife mount fits either way round)."""
    import sm_vn_knife_mount_dowel_spec as dowel

    # The stations are the spec's (AGENTS.md: the drawing reads pure
    # providers, not the builder; codjiflo, PR #1978); the builder reads
    # them too.
    assert (spec.PIN_HOLE_NEG_X, spec.PIN_HOLE_X) == pytest.approx((-22.62, -7.38))
    assert (spec.STUD_Z_FRONT, spec.STUD_Z_REAR) == pytest.approx((-83.972, 90.148), abs=5e-4)
    stations = ("HANGER_X", "PIN_HOLE_NEG_X", "PIN_HOLE_X", "STUD_Z_FRONT", "STUD_Z_REAR")
    for module in (part, drawing):
        for name in stations:
            assert getattr(module, name) is getattr(spec, name), (module.__name__, name)

    def imported_from(path: str, source_module: str) -> set[str]:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        return {
            alias.asname or alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == source_module
            for alias in node.names
        }

    def module_assigned(path: str) -> set[str]:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        names = set()
        for node in tree.body:
            targets = (
                node.targets if isinstance(node, ast.Assign)
                else [node.target] if isinstance(node, (ast.AnnAssign, ast.AugAssign))
                else []
            )
            for target in targets:
                names.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
        return names

    assert not set(stations) & imported_from(drawing.__file__, "build_fr_top_frame")
    for module in (part, drawing):
        assert set(stations) <= imported_from(module.__file__, "fr_top_frame_spec"), module.__name__
        assert not set(stations) & module_assigned(module.__file__), module.__name__
    assert spec.HANGER_PIN_XS == (-spec.HANGER_PIN_X, spec.HANGER_PIN_X)
    assert spec.HANGER_PIN_X == dowel.HANGER_OFFSET == pytest.approx(7.62)  # .300
    assert (spec.HANGER_PIN_X_PLACES, spec.HANGER_PIN_X_TOL) == pytest.approx((3, 0.127))
    # The span's band is the zone's radius; the -X ream's worst station from
    # its screw axis adds it to the +X band.
    assert dowel.SPAN == pytest.approx(part.PIN_HOLE_X - part.PIN_HOLE_NEG_X)
    assert spec.HANGER_PRESS_HOLE_POSITION_TOL / 2.0 == dowel.SPAN_TOL
    assert dowel.SPAN_TOL == pytest.approx(0.0254)
    assert spec.HANGER_NEG_PIN_X_TOL == pytest.approx(0.1524)
    assert spec.DRAWING_REFERENCE_PRECISION["dowel hole from hanger axis"] == 3
    assert spec.DRAWING_REFERENCE_PRECISION["-X dowel ream from +X dowel ream"] == 3
    assert "-X dowel ream from hanger axis" not in spec.DRAWING_REFERENCE_PRECISION
    # The press band is the dowel spec's: .1240 +.0005/-.0000 (F2).
    assert (spec.HANGER_PIN_HOLE_DIA, spec.HANGER_PIN_HOLE_DIA_BAND) == (
        dowel.PRESS_HOLE_DIA, dowel.PRESS_HOLE_DIA_BAND
    )
    assert spec.HANGER_PIN_HOLE_DIA == pytest.approx(3.1496)
    assert spec.HANGER_PIN_HOLE_DIA_BAND == pytest.approx((0.0127, 0.0))
    assert spec.HANGER_PIN_HOLE_DIA_PLACES == dowel.PRESS_HOLE_DIA_PLACES
    assert (spec.HANGER_PIN_HOLE_DIA_MIN, spec.HANGER_PIN_HOLE_DIA_MAX) == pytest.approx(
        (3.1496, 3.1623)
    )
    assert min(dowel.PRESS_INTERFERENCE_PRINTED) > 0.0
    assert (spec.HANGER_PIN_HOLE_DEPTH, spec.HANGER_PIN_HOLE_DEPTH_TOL) == (
        dowel.PRESS_DEPTH, dowel.PRESS_DEPTH_TOL
    )
    assert (spec.HANGER_PIN_HOLE_DEPTH, spec.HANGER_PIN_HOLE_DEPTH_TOL) == pytest.approx(
        (11.938, 0.254)
    )
    assert spec.HANGER_PIN_HOLE_DEPTH < spec.HANGER_GRIP
    # Rule 4: the ream callout names its count, process, mate and fit.
    assert spec.HANGER_PIN_HOLE_CALLOUT == "4X REAM, PRESS MHA-SM-VN-53 DOWEL TO FLOOR"
    assert spec.HANGER_PIN_DEPTH_CALLOUT == "4X FLAT BOTTOM,\nCORNER\nR.003 MAX"
    # The model owns the size, band and depth; the drawing imports them.
    assert spec.DRAWING_DIMENSIONS["HangerPinProfile"] == {"HangerPinHoleDia"}
    assert spec.DRAWING_DIMENSIONS["HangerPinHoles"] == {"HangerPinHoleDepth"}
    assert "HangerSlotProfile" not in spec.DRAWING_DIMENSIONS
    assert (
        spec.DRAWING_PRECISION_BY_NAME["HangerPinHoleDia"]
        == spec.HANGER_PIN_HOLE_DIA_PLACES
    )
    for retired in (
        "HANGER_SLOT_WIDTH", "HANGER_SLOT_LENGTH", "HANGER_SLOT_X", "HANGER_ROUND_X",
        "HANGER_PIN_SLIP_CLEARANCE_MIN", "HANGER_PIN_SLIP_CLEARANCE_MAX",
        "HANGER_PIN_NEG_STATION_TOL", "HANGER_PIN_SPAN",
    ):
        assert not hasattr(spec, retired), retired
    for retired in (
        "SLOT_X", "SLOT_FLAT", "SLOT_BAR_WALL", "SLOT_SCREW_WALL",
        "slot_stadium_points", "HANGER_SLOT_CONTOURS", "NEG_PIN_HOLE_BAR_WALL",
    ):
        assert not hasattr(part, retired), retired
    # F-F dimensions the +X ream from the screw axis and the -X ream BASIC
    # from the +X ream, with no callout row; its prefix counts both stations.
    section = Path(drawing.__file__).read_text(encoding="utf-8")
    section = section[section.index("def _hanger_section(") :]
    section = section[: section.index("\ndef ")]
    assert section.count("expected_mm=HANGER_PIN_X,") == 1
    assert "p0=(HANGER_X, -HALF_H-2.0, z), p1=(PIN_HOLE_X," in section
    assert "p0=(PIN_HOLE_NEG_X, -HALF_H-2.0, z), p1=(PIN_HOLE_X," in section
    assert "expected_mm=PIN_HOLE_X - PIN_HOLE_NEG_X," in section
    span = section[section.index("    span = _checked_dimension(") :]
    span = span[: span.index("    dimensions = curate_view_dimensions(")]
    assert "suffix=" not in span
    assert 'set_basic_dimension(adapter, span, label="-X dowel ream from +X dowel ream")' in span
    # Its count reads above the BASIC frame, not as a prefix inside it (farm
    # run 20261027T133857303Z: the frame's side ran through "2X ").
    assert '_set_callout_text(span, 3, HANGER_PIN_SPAN_ABOVE, "-X dowel ream span")' in span
    assert "SetText(1, " not in span
    assert drawing.HANGER_PIN_SPAN_ABOVE == "2X"
    assert "15.264" not in section


def test_ream_sketch_holds_four_driven_circles_and_the_press_band() -> None:
    # Four circles in one underside sketch, all driven by the HangerPinHoleDia
    # global; the rear +X one owns the marked name.  Each prints the dowel
    # spec's stacked +.0005/-.0000; no symmetric band left.
    from _fit_deviations import deviations

    assert len(part.HANGER_PIN_CONTOURS) == 4
    assert part.swept_contours_disjoint(part.HANGER_PIN_CONTOURS)
    assert deviations(spec.HANGER_PIN_HOLE_DIA_BAND) == pytest.approx((0.0, 0.0127))
    source = Path(part.__file__).read_text(encoding="utf-8")
    step = source[source.index("    # 12b. Dowel press reams") : source.index("    # 13. Cross-screw")]
    assert '("Rear", ""): "HangerPinHoleDia",' in step
    for name in ("HangerPinHole1Dia", "HangerPinHole2Dia", "HangerPinHole3Dia"):
        assert f'"{name}"' in step
        assert source.count(f'"{name}"') == 2  # the sketch and the band
    assert "drives=(None, None, '\"HangerPinHoleDia\"')," in step
    assert "depth=HANGER_PIN_HOLE_DEPTH, reverse_direction=not normal_out" in step
    assert "len(HANGER_PIN_CONTOURS)" in step
    assert "set_dimension_symmetric_tolerance" not in source
    assert "HangerSlot" not in source
    # The knockouts: one native #51 wizard feature on the ream axes (placed
    # on the faced top, the same cylinder the shop drills up from the ream
    # floor), its cut checked against its own volume.
    assert "HANGER_KNOCKOUT_SPEC,\n        [[x, HALF_H, z] for" in step
    assert '(0.0, 1.0, 0.0),\n        "dowel ream knockouts (#51 drill)",' in step
    assert 'name="HangerKnockouts",' in step
    assert "expect_dia_mm=HANGER_KNOCKOUT_DIA," in step
    assert "* HANGER_KNOCKOUT_LENGTH" in step


def test_a_a_witnesses_start_past_the_rear_boss_off_the_cut_face() -> None:
    """Machinist review, farm run 20261027T175429300Z (sheet 4, A-A): the
    16.30 recess depth's witnesses left the -Z boss's recess at x 235.0 mm
    and ran the whole section to its line at 382, its floor witness (y
    138.7) through the rail's hatch; the 4.5's rail-top witness (y 144.6,
    from 335.8) crossed the +Z boss.  Both dimensions' gaps widen so every
    witness starts 1.2 mm past the +Z boss's outer face, beside the stack."""
    widen = drawing._witness_widening
    # The 16.30 as measured: both witnesses from 235.0, its leader shoulder
    # (y 145.1) and line stubs are not witnesses.
    recess = [
        ((0.2350, 0.1468), (0.3830, 0.1468)), ((0.2350, 0.1387), (0.3830, 0.1387)),
        ((0.4146, 0.1451), (0.3820, 0.1451)), ((0.3820, 0.1451), (0.3820, 0.1468)),
        ((0.3820, 0.1387), (0.3820, 0.1323)),
    ]
    face = 0.34650 + 0.0225 / 2.0  # the +Z boss's axis + Ø45 at 1:2
    start = face + drawing.A_A_WITNESS_STANDOFF
    amount, starts = widen(recess, (0.1468, 0.1387), start, label="t")
    assert starts == (0.2350, 0.2350)
    assert amount == pytest.approx(start - 0.2350)
    # The 4.5: witnesses from 339.6 (boss top) and 335.8 (rail top); one
    # widening, from the farther-left start, clears both whichever gap draws
    # which, and both still end at the line's 365.7 overrun.
    above = [
        ((0.3396, 0.1468), (0.3657, 0.1468)), ((0.3358, 0.1446), (0.3657, 0.1446)),
        ((0.3647, 0.1468), (0.3647, 0.1532)), ((0.3598, 0.1677), (0.3966, 0.1677)),
    ]
    amount, starts = widen(above, (0.1468, 0.1446), start, label="t")
    assert amount == pytest.approx(start - 0.3358)
    assert min(starts) + amount == pytest.approx(start)
    assert max(starts) + amount < 0.3657
    # Already clear: no change; a missing or doubled witness fails loud.
    assert widen(above, (0.1468, 0.1446), 0.30, label="t")[0] == 0.0
    with pytest.raises(RuntimeError, match="witness at sheet y"):
        widen(above, (0.1468, 0.1400), start, label="t")
    with pytest.raises(RuntimeError, match="witness at sheet y"):
        widen([*recess, recess[0]], (0.1468, 0.1387), start, label="t")
    # The recipe widens both A-A dimensions past the +Z boss's outer face.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    recipe = source[source.index("boss_above = _checked_dimension("):]
    recipe = recipe[: recipe.index("top bore mouth chamfer")]
    assert "REAR_COLUMN_Z + BOSS_DIA / 2.0" in recipe
    assert "boss_face_x + A_A_WITNESS_STANDOFF" in recipe
    assert 'dimension_name(adapter, annotation) == "CapRecessDepth"' in recipe
    assert "HALF_H + BOSS_ABOVE - CAP_RECESS_DEPTH" in recipe
    assert recipe.count("_start_witnesses_past(") == 2


def test_knockouts_leave_a_floor_land_and_their_walls() -> None:
    """Rule 16: each blind press ream gets a #51 knockout drilled up from
    its floor, drawn on the ream's axis (codjiflo, PR #1978: drilled from
    the top, the two holes' opposing wander left a #43 0.200 of floor).  The
    dowel still bottoms on the floor land the knockout leaves; it is pressed
    chamfer end first, so the land it bears on is its end flat's, not the
    ream's (codjiflo round 3), at ASME B18.8.2's smallest point and inside
    the floor's corner limit (round 4).  Owner ruling 2026-10-27 (option c):
    no "REAM SETUP" and no frame, so the knockout is off its ream by the
    drawn coaxiality's implied ±0.13 per axis, and the land, 0.313, falls
    under the 0.4 target, accepted as machinist exception RV-06 (minor).
    The knockout prints two places, Ø1.70, under the DRILLED HOLES row
    (machinist review, run 20261027T175429300Z).  It keeps its walls where
    its shift is greatest, at the top, a land inside the top break and a
    continuous washer bearing ring inside it, and a 1/16 in punch passes
    it."""
    from pathlib import Path as _Path

    from _hole_spec import HoleSpec, NUMBER_DRILL_MM
    import machinist_exceptions

    import sm_vn_knife_mount_dowel_spec as dowel

    assert spec.HANGER_KNOCKOUT_SPEC == HoleSpec("drilled_number", "#51")
    assert spec.HANGER_KNOCKOUT_DIA == pytest.approx(NUMBER_DRILL_MM["#51"])
    assert NUMBER_DRILL_MM["#51"] == pytest.approx(0.0670 * 25.4, abs=5e-4)
    # Three places: the printed .067 under +.004/0, the #51's .0670 on it.
    assert spec.HANGER_KNOCKOUT_DIA_PLACES == 3
    assert spec.HANGER_KNOCKOUT_DIA_PRINTED == pytest.approx(1.7018)
    assert spec.HANGER_KNOCKOUT_DIA_MAX == pytest.approx(
        spec.HANGER_KNOCKOUT_DIA_PRINTED + spec.PRINTED_DRILLED_HOLE_PLUS_MM
    )
    assert spec.HANGER_KNOCKOUT_DIA_MAX == pytest.approx(1.8034)
    assert (
        spec.HANGER_KNOCKOUT_DIA_PRINTED
        <= spec.HANGER_KNOCKOUT_DIA
        <= spec.HANGER_KNOCKOUT_DIA_MAX
    )
    assert spec.HANGER_KNOCKOUT_PUNCH_DIA == pytest.approx(25.4 / 16.0)
    assert spec.HANGER_KNOCKOUT_PUNCH_DIA < spec.HANGER_KNOCKOUT_DIA_PRINTED
    assert spec.HANGER_KNOCKOUT_LENGTH == pytest.approx(
        spec.RING_HEIGHT - spec.HANGER_PIN_HOLE_DEPTH
    )
    assert spec.HANGER_KNOCKOUT_LENGTH_MAX == pytest.approx(
        spec.HANGER_GRIP + spec.HANGER_GRIP_TOL
        - (spec.HANGER_PIN_HOLE_DEPTH - spec.HANGER_PIN_HOLE_DEPTH_TOL)
    )
    # Codjiflo round 6: the ~15 D knockout takes a taper-length #51 (2 in
    # flute, MSC 63725519) reaching the top from the underside, and the
    # punch reaches from the faced top through the knockout and the ream
    # to the underside, the full grip at its far limit, whatever the floor.
    reach = spec.HANGER_GRIP + spec.HANGER_GRIP_TOL
    assert spec.HANGER_KNOCKOUT_DRILL_REACH == pytest.approx(reach)
    assert spec.HANGER_KNOCKOUT_PUNCH_REACH_MIN == pytest.approx(reach)
    assert spec.HANGER_KNOCKOUT_PUNCH_REACH_MIN == pytest.approx(36.6268)
    # The knockout's longest run plus the push-out from the shallowest floor
    # sum to the same reach: the ream's depth cancels.
    assert spec.HANGER_KNOCKOUT_LENGTH_MAX + (
        spec.HANGER_PIN_HOLE_DEPTH - spec.HANGER_PIN_HOLE_DEPTH_TOL
    ) == pytest.approx(spec.HANGER_KNOCKOUT_PUNCH_REACH_MIN)
    assert spec.HANGER_KNOCKOUT_DEPTH_D == pytest.approx(
        spec.HANGER_KNOCKOUT_LENGTH_MAX / spec.HANGER_KNOCKOUT_DIA_PRINTED
    )
    assert spec.HANGER_KNOCKOUT_DEPTH_D == pytest.approx(14.657, abs=5e-4)
    assert spec.HANGER_KNOCKOUT_DRILL_FLUTE_LEN == pytest.approx(2.0 * 25.4)
    assert spec.HANGER_KNOCKOUT_DRILL_FLUTE_LEN > spec.HANGER_KNOCKOUT_DRILL_REACH
    per_mm = spec.DRILL_DRIFT_PER_MM
    # The drawn coaxiality's real worst case: the title block's .XXX ±.005
    # on the implied zero, along both axes at once.  The ream's own drift
    # moves its floor centre and the pressed dowel together, so it adds
    # nothing at the floor.
    assert spec.HANGER_KNOCKOUT_COAXIAL_TOL == pytest.approx(0.127)
    eccentricity = math.hypot(0.127, 0.127)
    assert spec.HANGER_KNOCKOUT_FLOOR_ECCENTRICITY == pytest.approx(eccentricity)
    concentric = (spec.HANGER_PIN_HOLE_DIA_MIN - spec.HANGER_KNOCKOUT_DIA_MAX) / 2.0
    land = concentric - eccentricity
    assert spec.HANGER_PIN_FLOOR_LAND_MIN == pytest.approx(land)
    assert land == pytest.approx(0.493494877578617)
    # The contacted land: the dowel's pressed end flat (inside the chamfer
    # that touches nothing) at B18.8.2's smallest point, 0.110 in (the
    # vendor model's 0.115 is the band's middle), or the floor's flat inside
    # its largest corner if smaller, less the largest knockout, off centre
    # by the drawn coaxiality.
    assert (dowel.POINT_DIA_MIN, dowel.POINT_DIA_MAX) == pytest.approx(
        (0.110 * 25.4, 0.120 * 25.4)
    )
    assert dowel.POINT_DIA_MIN < dowel.ENDS.point_dia < dowel.POINT_DIA_MAX
    # The dowel's spec owns the corner limit and its lift with the ream
    # (codjiflo round 5); the crossbar reads them.
    assert spec.HANGER_PIN_FLOOR_CORNER_R_MAX is dowel.PRESS_FLOOR_CORNER_R_MAX
    assert spec.HANGER_PIN_FLOOR_FILLET_LIFT_MAX is dowel.PRESS_FLOOR_LIFT_MAX
    corner = spec.HANGER_PIN_FLOOR_CORNER_R_MAX
    assert corner == pytest.approx(0.0762)  # .003
    floor_flat_r = spec.HANGER_PIN_HOLE_DIA_MIN / 2.0 - corner
    flat = 2.0 * min(dowel.POINT_DIA_MIN / 2.0, floor_flat_r)
    assert flat == pytest.approx(dowel.POINT_DIA_MIN)
    assert spec.HANGER_PIN_FLOOR_BEARING_R == pytest.approx(flat / 2.0)
    bearing = (flat - spec.HANGER_KNOCKOUT_DIA_MAX) / 2.0 - eccentricity
    assert spec.HANGER_PIN_FLOOR_BEARING_LAND_MIN == pytest.approx(bearing)
    assert bearing == pytest.approx(0.31569487757861703)
    # Owner ruling 2026-10-27 accepts the sub-0.4 land: the target stays
    # named, the spec only demands a positive land, and RV-06 (minor)
    # quotes the land the proof computes.
    assert spec.HANGER_PIN_FLOOR_BEARING_LAND_TARGET == 0.4
    assert 0.0 < bearing < spec.HANGER_PIN_FLOOR_BEARING_LAND_TARGET
    spec_source = Path(spec.__file__).read_text(encoding="utf-8")
    assert "owner ruling 2026-10-27 accepts the sub-0.4 land" in spec_source.replace("\n# ", " ")
    exceptions = {
        entry.id: entry
        for entry in machinist_exceptions.load_exceptions(
            _Path(spec.__file__).resolve().parents[1] / "config", "fr_top_frame", "part"
        )
    }
    rv06 = exceptions["RV-06"]
    assert rv06.kind == "minor"
    assert "knockout floor land" in rv06.where
    assert f"{bearing / 25.4:.4f}".lstrip("0") in rv06.finding
    assert ".016" in rv06.finding
    assert "owner ruling 2026-10-27" in rv06.reason
    # B18.8.2's largest point overhangs the floor's flat at the smallest
    # ream and largest corner, so its edge stands on the fillet: the end
    # sits off the floor by the fillet's height under that edge (the
    # chamfer cone at 16 deg to the axis climbs far faster than the fillet
    # beyond it), a sliver of the press depth's .010 band.
    overhang = dowel.POINT_DIA_MAX / 2.0 - floor_flat_r
    assert overhang == pytest.approx(0.0254)
    edge_rise = corner - (corner**2 - overhang**2) ** 0.5
    assert spec.HANGER_PIN_FLOOR_FILLET_LIFT_MAX >= edge_rise - 5e-6
    assert spec.HANGER_PIN_FLOOR_FILLET_LIFT_MAX == pytest.approx(edge_rise, abs=5e-5)
    assert spec.HANGER_PIN_FLOOR_FILLET_LIFT_MAX < 0.02 * spec.HANGER_PIN_HOLE_DEPTH_TOL
    # The lifted pin stands that much longer below the underside.
    assert dowel.PROUD_MAX == pytest.approx(
        dowel.proud_length(
            spec.HANGER_PIN_HOLE_DEPTH - spec.HANGER_PIN_HOLE_DEPTH_TOL, dowel.LENGTH_GRADE
        )
        + spec.HANGER_PIN_FLOOR_FILLET_LIFT_MAX
    )
    # Negative controls: the 0.4 target held only with the knockout started
    # in the ream's setup (the ream's floor drift, 0.067), which the print
    # no longer states; at the drawn coaxiality every larger drill leaves
    # less, a #50 (codjiflo round 4) 0.278.
    setup_drift = per_mm * (spec.HANGER_PIN_HOLE_DEPTH + spec.HANGER_PIN_HOLE_DEPTH_TOL)
    assert setup_drift == pytest.approx(part.HANGER_DRIFT_AT_REAM_FLOOR)
    assert (flat - spec.HANGER_KNOCKOUT_DIA_MAX) / 2.0 - setup_drift >= 0.4
    assert bearing < 0.4
    lands = {
        larger: (flat - larger - spec.PRINTED_DRILLED_HOLE_PLUS_MM) / 2.0 - eccentricity
        for larger in (0.0700 * 25.4, NUMBER_DRILL_MM["#47"], NUMBER_DRILL_MM["#43"])
    }
    assert all(value < bearing for value in lands.values()), lands
    assert lands[0.0700 * 25.4] == pytest.approx(0.2776, abs=5e-5)
    # The process row names the drill only (machinist review: "REAM SETUP"
    # was a method; owner ruling 2026-10-27), the row under the native size
    # the start: the floor.
    assert spec.HANGER_KNOCKOUT_CALLOUT_ABOVE == "#51 DRILL"
    assert "SETUP" not in spec.HANGER_KNOCKOUT_CALLOUT_BELOW
    assert spec.HANGER_KNOCKOUT_CALLOUT_BELOW == "FROM REAM FLOOR;\nMHA-SM-VN-53 KNOCKOUT"
    drift = per_mm * spec.HANGER_KNOCKOUT_LENGTH_MAX
    assert part.HANGER_KNOCKOUT_DRIFT == pytest.approx(drift)
    # At the top: the ream's floor drift, the coaxiality's .005 along the
    # wall's axis, and the knockout's own drift up its run.
    shift = setup_drift + spec.HANGER_KNOCKOUT_COAXIAL_TOL + drift
    assert part.HANGER_KNOCKOUT_SHIFT_AT_TOP == pytest.approx(shift)
    assert shift == pytest.approx(0.3214391350105531)
    knockout_r = spec.HANGER_KNOCKOUT_DIA_MAX / 2.0
    clearance_r = spec.HANGER_CLEARANCE_DIA_MAX / 2.0
    # The -X knockout, on its ream's axis, stands farthest from nominal: the
    # +X ream's .XXX band plus the -X ream's zone radius, and its shift at
    # the top.
    near = spec.HANGER_PIN_X - spec.HANGER_NEG_PIN_X_TOL - shift
    reach = part.HANGER_BAR_HALF_WIDTH_MIN - spec.HANGER_CROSSBAR_CENTER_TOL
    assert part.KNOCKOUT_BAR_WALL == pytest.approx(
        reach - spec.HANGER_PIN_X - spec.HANGER_NEG_PIN_X_TOL - knockout_r - shift
    )
    assert part.KNOCKOUT_SCREW_WALL == pytest.approx(
        near - knockout_r - clearance_r - part.HANGER_DRIFT_AT_TOP
    )
    assert part.KNOCKOUT_BAR_WALL == pytest.approx(3.386960864989447)
    assert part.KNOCKOUT_SCREW_WALL == pytest.approx(2.9793816360665897)
    assert min(part.KNOCKOUT_BAR_WALL, part.KNOCKOUT_SCREW_WALL) >= 2.032
    assert part.KNOCKOUT_TOP_BREAK_LAND == pytest.approx(
        reach - part.EDGE_BREAK_PRINTED_MAX - spec.HANGER_PIN_X
        - spec.HANGER_NEG_PIN_X_TOL - knockout_r - shift
    )
    assert part.KNOCKOUT_TOP_BREAK_LAND == pytest.approx(1.659760864989447)
    # The knockout exits under the washer: the washer still bears on a
    # continuous ring inside the knockouts at every printed limit.
    washer = part.HANGER_WASHER
    offset = part.HANGER_WASHER_OFFSET_MAX
    assert near - knockout_r < washer.OD_MAX / 2.0 + offset
    ring = min(washer.OD_MIN / 2.0, near - knockout_r - offset) - max(
        washer.ID_MAX / 2.0, clearance_r + offset
    )
    assert part.HANGER_WASHER_KNOCKOUT_RING_MIN == pytest.approx(ring)
    assert part.HANGER_WASHER_KNOCKOUT_RING_MIN == pytest.approx(0.1832031421624567)
    assert ring > 0.0


def test_hanger_walls_meet_the_target_after_drift() -> None:
    """Q7 option C: the #10 holes are drilled from the faced underside and
    the dowel reams cut from it, each located from the #10 hole's axis
    there, so each hole's 0.3 deg drift is nil at the seat and largest at
    the blind floors.  Every wall round a ream, at the print-worst bands
    and the deepest printed floor, less the drift of each hole either side
    of it, meets rule 17's .080 target.  The -X ream, BASIC from the +X one
    inside its Ø.002 zone, stands farthest along the line, so one pair of
    walls at its limit holds for each."""
    per_mm = math.tan(math.radians(spec.KEEPER_TAP_DRILL_WANDER_DEG))
    assert spec.DRILL_DRIFT_PER_MM == pytest.approx(per_mm)
    drift = per_mm * (spec.HANGER_PIN_HOLE_DEPTH + spec.HANGER_PIN_HOLE_DEPTH_TOL)
    assert part.HANGER_DRIFT_AT_REAM_FLOOR == pytest.approx(drift)
    assert drift == pytest.approx(0.0638, abs=1e-4)
    ream_r = spec.HANGER_PIN_HOLE_DIA_MAX / 2.0
    clearance_r = spec.HANGER_CLEARANCE_DIA_MAX/2
    off = spec.HANGER_PIN_X_TOL
    # Along the line the -X ream, BASIC from the +X one inside its Ø.002
    # zone, stands farthest from nominal; one pair of walls at that limit.
    along = spec.HANGER_NEG_PIN_X_TOL
    assert along == pytest.approx(off + spec.HANGER_PRESS_HOLE_POSITION_TOL / 2.0)
    outer_loss = spec.PRINTED_LINEAR_BAND_MM[spec.HANGER_CROSSBAR_WIDTH_PLACES]/2
    outer_loss += spec.HANGER_CROSSBAR_CENTER_TOL
    walls = {
        "-X ream | screw hole": (
            spec.HANGER_PIN_X - along - ream_r - clearance_r,
            2.0 * drift,
            part.PIN_HOLE_SCREW_WALL,
        ),
        "-X ream | bar -X face": (
            (part.PIN_HOLE_NEG_X - along) - ream_r - part.BAR_X0 - outer_loss,
            drift,
            part.PIN_HOLE_BAR_WALL,
        ),
    }
    for label, (print_worst, charged, wall) in walls.items():
        assert wall == pytest.approx(print_worst - charged), label
        assert wall >= 2.032, label
    # The +X ream, at its own .XXX band, keeps more.
    assert part.BAR_X1 - (part.PIN_HOLE_X + off) - ream_r - outer_loss - drift > (
        part.PIN_HOLE_BAR_WALL
    )
    assert part.PIN_HOLE_BAR_WALL == pytest.approx(2.9651122538953043)
    assert part.PIN_HOLE_SCREW_WALL == pytest.approx(2.685474507790608)
    assert part.PIN_HOLE_FLOOR_MARGIN == pytest.approx(
        spec.HANGER_GRIP - spec.HANGER_GRIP_TOL - spec.HANGER_PIN_HOLE_DEPTH
        - spec.HANGER_PIN_HOLE_DEPTH_TOL
    )
    assert part.PIN_HOLE_FLOOR_MARGIN == pytest.approx(24.1808)
    # Entry wander at the deepest pocket roof and the finished top.  The
    # -X ream sits across the line within half its Ø.002 zone of the +X one.
    pocket = part.BAR_POCKET_HOLE_WALLS
    station = part._POCKET_STATION - part._POCKET_END
    assert set(pocket) == {
        "hanger clearance hole", "+X dowel ream", "-X dowel ream", "dowel knockout",
    }
    assert pocket["hanger clearance hole"] == pytest.approx(
        station
        - clearance_r
        - per_mm
        * (
            spec.HANGER_GRIP
            + spec.HANGER_GRIP_TOL
            - (part.FLANGE - spec.PRINTED_LINEAR_BAND_MM[spec.FLANGE_THICKNESS_PLACES])
        )
    )
    zone = spec.HANGER_PRESS_HOLE_POSITION_TOL / 2.0
    assert pocket["+X dowel ream"] == pytest.approx(station - off - ream_r - drift)
    assert pocket["-X dowel ream"] == pytest.approx(
        station - off - zone - ream_r - drift
    )
    assert pocket["dowel knockout"] == pytest.approx(
        station - off - zone - spec.HANGER_KNOCKOUT_DIA_MAX / 2.0
        - part.HANGER_KNOCKOUT_SHIFT_AT_TOP
    )
    assert pocket["hanger clearance hole"] == pytest.approx(11.279561535009918)
    assert pocket["+X dowel ream"] == pytest.approx(12.731424473468806)
    assert pocket["-X dowel ream"] == pytest.approx(12.706024473468801)
    assert pocket["dowel knockout"] == pytest.approx(13.127873084562935)


def test_washer_support_on_the_faced_top_charges_all_printed_limits() -> None:
    """The washers bear on the faced top itself (user ruling 2026-10-14: no
    spotfaces): each print-worst washer stays inside the crossbar's top break
    and clear of the outer rail ends, and keeps a full bearing annulus."""
    per_mm = spec.DRILL_DRIFT_PER_MM
    assert part.HANGER_DRIFT_AT_TOP == pytest.approx(
        per_mm * (spec.HANGER_GRIP + spec.HANGER_GRIP_TOL)
    )
    assert part.HANGER_DRIFT_AT_TOP == pytest.approx(0.19177922892285743)
    # The knife mount fitted either way round (the T+H3 contract's
    # governing case): X .005 + .001 + .0025 + slip/2 (the round-hole pin
    # on the -X ream, BASIC from the +X one inside its Ø.002 zone) + t/2
    # (B's datum simulator off its hole's centre at the pin root, ⊥.0006 to
    # A; codjiflo round 5), Z .005 + .001 + .0025 + half the pair shift
    # (both slips' halves, half the Ø.002 zone, and B's and C's simulators,
    # t) + the B-C datum line's yaw carried .300 to the tap: the +X reams'
    # .005 stations at opposite limits over their spacing (codjiflo round 4).
    import sm_knife_mount_spec as knife_mount
    import sm_vn_knife_mount_dowel_spec as dowel

    assert (
        knife_mount.STUD_TAP_POSITION_TOL,
        knife_mount.DOWEL_HOLE_PERPENDICULARITY_TOL,
        knife_mount.DOWEL_SLOT_PERPENDICULARITY_TOL,
    ) == pytest.approx((0.127, 0.01524, 0.01524))
    slip = dowel.SLIP_CLEARANCE_MAX
    assert slip == pytest.approx(0.09144)  # .0036
    off = spec.HANGER_PIN_X_TOL
    zone = dowel.SPAN_TOL
    tap = knife_mount.STUD_TAP_POSITION_TOL / 2.0
    perp = knife_mount.DOWEL_HOLE_PERPENDICULARITY_TOL  # B's round hole
    slot_perp = knife_mount.DOWEL_SLOT_PERPENDICULARITY_TOL  # C's slot
    pair_shift = slip / 2.0 + slip / 2.0 + zone + perp / 2.0 + slot_perp / 2.0
    yaw_shift = spec.HANGER_PIN_X * 2.0 * off / (spec.STUD_Z_REAR - spec.STUD_Z_FRONT)
    assert spec.HANGER_DATUM_LINE_YAW_SHIFT == pytest.approx(yaw_shift)
    assert yaw_shift == pytest.approx(0.0111, abs=5e-5)
    assert part.HANGER_SEAT_BOLT_MISMATCH == pytest.approx(
        math.hypot(
            off + zone + tap + slip / 2.0 + perp / 2.0,
            off + zone + tap + pair_shift / 2.0 + yaw_shift,
        )
    )
    assert part.HANGER_SEAT_BOLT_MISMATCH == pytest.approx(0.39795963249063754)
    assert spec.HANGER_WASHER_FLOAT_MAX == pytest.approx(
        (spec.HANGER_WASHER.ID_MAX-spec.HANGER_SCREW.SHANK_DIA_MIN)/2,
    )
    assert spec.HANGER_WASHER_FLOAT_MAX == pytest.approx(0.57404)
    assert spec.HANGER_WASHER_FLOAT_MAX > (
        spec.HANGER_WASHER.ID_MAX-spec.HANGER_SCREW.SHANK_DIA
    )/2
    assert part.HANGER_WASHER_OFFSET_MAX == pytest.approx(
        spec.HANGER_WASHER_FLOAT_MAX
        + part.HANGER_SEAT_BOLT_MISMATCH
        + part.HANGER_DRIFT_AT_TOP
        + spec.HANGER_WASHER.OD_ID_RUNOUT_MAX
    )
    assert part.HANGER_WASHER_OFFSET_MAX == pytest.approx(1.4939788614134952)
    reach = spec.HANGER_WASHER.OD_MAX / 2.0 + part.HANGER_WASHER_OFFSET_MAX
    # Inside the top break's printed worst leg at the narrowest printed bar
    # half width, centred on D.
    band = spec.PRINTED_LINEAR_BAND_MM
    assert part.HANGER_WASHER_BAR_TOP_MARGIN == pytest.approx(
        (part.BAR_X1 - part.BAR_X0 - band[spec.HANGER_CROSSBAR_WIDTH_PLACES]) / 2.0
        - spec.HANGER_CROSSBAR_CENTER_TOL
        - part.EDGE_BREAK_PRINTED_MAX
        - reach
    )
    assert part.HANGER_WASHER_BAR_TOP_MARGIN == pytest.approx(2.6208211385865052)
    # Clear of the outer front/rear rail ends: each washer's Z reach is its
    # station band plus the print-worst reach; the rail's outer face is the
    # narrowest printed half flange past its socket axis. The rear end binds,
    # because it also spends the .XX socket-pitch band.
    places = spec.DRAWING_REFERENCE_PRECISION
    half_flange = (part.RAIL_W_FR - band[places["front rear flange width"]]) / 2.0
    z_reach = band[places["rear hanger z from upper sockets"]] + reach
    front_end_wall = part.STUD_Z_FRONT - part.FRONT_COLUMN_Z + half_flange - z_reach
    rear_end_wall = (
        part.REAR_COLUMN_Z - part.STUD_Z_REAR + half_flange
        - band[places["socket vertical pitch"]] - z_reach
    )
    assert rear_end_wall < front_end_wall
    assert part.HANGER_WASHER_OUTER_END_WALL == pytest.approx(rear_end_wall)
    assert part.HANGER_WASHER_OUTER_END_WALL == pytest.approx(
        32.35993335815998 + abs(part.FRONT_COLUMN_Z) - 112.0
    )
    assert part.HANGER_WASHER_BEARING_MIN == pytest.approx(
        spec.HANGER_WASHER_CONCENTRIC_ANNULUS_MIN - part.HANGER_WASHER_OFFSET_MAX
    )
    assert part.HANGER_WASHER_BEARING_MIN == pytest.approx(1.7192211385865048)
    assert part.HANGER_WASHER_BAR_TOP_MARGIN > 0.0 and part.HANGER_WASHER_BEARING_MIN > 0.0
    assert part.HANGER_WASHER_OUTER_END_WALL >= 2.032
    # The spotface guards are gone, not aliased.
    for name in (
        "HANGER_SPOTFACE_BAR_WALL",
        "HANGER_SPOTFACE_POCKET_ROOF_WEB",
        "HANGER_SPOTFACE_WASHER_OFFSET_MAX",
        "HANGER_SPOTFACE_WASHER_SUPPORT_MIN",
        "HANGER_SPOTFACE_OUTER_END_WALL",
    ):
        assert not hasattr(part, name)


def test_dowel_ream_sketch_contours_never_cross() -> None:
    # 48ad988c6 cut overlapping circles in one sketch and the farm leaf's cut
    # failed (FeatureCut3 "Type mismatch"): the four ream circles stand apart.
    r = spec.HANGER_PIN_HOLE_DIA / 2.0
    assert part.HANGER_PIN_CONTOURS == tuple(
        ((x, z), (x, z), r)
        for z in (part.STUD_Z_FRONT, part.STUD_Z_REAR)
        for x in (part.PIN_HOLE_NEG_X, part.PIN_HOLE_X)
    )
    assert part.swept_contours_disjoint(part.HANGER_PIN_CONTOURS)
    # The checker separates by the swept radii, so touching is a failure.
    assert not part.swept_contours_disjoint((((0, 0), (1, 0), 1.0), ((1, 2), (3, 2), 1.0)))
    assert part.swept_contours_disjoint((((0, 0), (1, 0), 1.0), ((1, 2.001), (3, 2.001), 1.0)))
    source = Path(part.__file__).read_text(encoding="utf-8")
    step = source[source.index("    # 12b. Dowel press reams") : source.index("    # 12c.")]
    assert step.count("await define_circle(") == 1  # once per station, in a loop
    assert step.count("create_cut_extrude(") == 1
    assert "add_arc(" not in step
    # No starred adapter call is left for the slot-stadium guard to follow.
    assert not re.search(r"adapter\.[a-z_]+\(\*", source)


def test_neg_reams_are_positioned_to_the_datum_reams_with_translation() -> None:
    # drawing-guidelines.md rule 5 (avoid excessive GD&T) (knife-edge system): datum B the front +X ream, C the
    # rear; each -X ream in a Ø.002 cylinder about its true position, BASIC
    # from its own station's +X ream (F-F), the other station's +X ream
    # translated (the stations' spacing is toleranced, not BASIC), with no
    # direction name (machinist review, farm run 4).
    assert spec.GEOMETRIC_TOLERANCES_IN["knife-hanger press ream position"] == ".002"
    assert spec.HANGER_PRESS_HOLE_POSITION_TOL == pytest.approx(0.0508)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    underside = source[source.index('ddoc.ActivateSheet("UNDERSIDE")') :]
    assert underside.count("add_datum_feature(") == 1
    assert '(("B", STUD_Z_FRONT), ("C", STUD_Z_REAR))' in underside
    assert underside.count("add_feature_control_frame(") == 1
    assert '("front", STUD_Z_FRONT, ("B", "C"))' in underside
    assert '("rear", STUD_Z_REAR, ("C", "B"))' in underside
    assert "translated=datums[1:]" in underside
    assert "HANGER_REAM_FRAME_QUANTITY" not in source
    assert 'GEOMETRIC_TOLERANCES_IN["knife-hanger press ream position"]' in underside
    frames = underside[underside.index("add_feature_control_frame(") :]
    frames = frames[: frames.index("locator_dimensions")]
    assert "translated=datums[1:],\n            diameter=True,\n" in frames
    assert "(PIN_HOLE_NEG_X, -HALF_H, station_z), HANGER_PIN_HOLE_DIA/2," in frames
    assert "leader_attach_xy=hanger_ream_rim(ream_centre, knee)," in frames
    assert '"HangerPinHoleDia": HANGER_PIN_DIA_TEXT_XY' in underside
    for name, (x, y) in {
        **drawing.HANGER_DATUM_SYMBOL_XY,
        **drawing.HANGER_REAM_FRAME_XY,
        "knockout callout": drawing.HANGER_KNOCKOUT_CALLOUT_XY,
    }.items():
        assert 0.013 < x < TITLE_BLOCK[0] and 0.125 < y < 0.270, name


def test_overall_plan_extremes_pick_the_barrel_circles_as_entities() -> None:
    # Farm a03283b49: a sheet-point pick on the boss barrel's R22.5 plan
    # outline resolved to the top edge break's inner circle (then the C2's
    # R20.5, width 435 for 439).  Both overall dimensions select the scanned
    # R22.5 circles, on the upper boss's break's lower circle plane.
    import ast

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    calls = {
        ast.literal_eval(keyword.value): call
        for call in ast.walk(tree)
        if isinstance(call, ast.Call) and _called_name(call) == "_checked_dimension"
        for keyword in call.keywords
        if keyword.arg == "label" and isinstance(keyword.value, ast.Constant)
    }
    for label in ("overall casting width", "overall casting depth"):
        keywords = {keyword.arg: keyword.value for keyword in calls[label].keywords}
        entities = keywords["entities"]
        assert isinstance(entities, ast.Tuple) and len(entities.elts) == 2
        assert all(_called_name(item) == "plan_barrel" for item in entities.elts)
        assert ast.literal_eval(keywords["maximum"]) is True
    barrel = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "plan_barrel"
    )
    text = ast.unparse(barrel)
    assert "geometry_top_edges.circle_at(" in text
    assert "HALF_H + BOSS_ABOVE - EDGE_CHAMFER" in text
    assert "BOSS_DIA / 2" in text
    assert drawing.PLAN_HALF_X == part.COLUMN_X + part.BOSS_DIA / 2.0


def test_no_datum_tag_is_attached_to_a_circle_by_edge_object() -> None:
    # Farm run 20261009T164113078Z: datum B, attached to the scanned round
    # dowel-hole circle as an edge object, ignored SetPosition2 and stayed at
    # its default drop 37.6 mm from its request (as crank_pinion datum A and
    # the vm2 probe's rod/rack bores did: layout-tuning lesson h).  A circle
    # is attached by a sheet-point pick, proved by expected_entity.
    import ast

    offenders = []
    for path in sorted(Path(drawing.__file__).parent.glob("draw_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in ast.walk(tree):
            if not (
                isinstance(call, ast.Call)
                and getattr(call.func, "id", getattr(call.func, "attr", "")) == "add_datum_feature"
            ):
                continue
            for keyword in call.keywords:
                if keyword.arg in {"edge_entity", "entity"} and "circle_at(" in ast.unparse(
                    keyword.value
                ):
                    offenders.append(f"{path.name}:{call.lineno}")
    assert offenders == []


def test_hanger_datums_are_picked_on_their_rims_toward_their_tags() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    underside = source[source.index('ddoc.ActivateSheet("UNDERSIDE")') :]
    loop = underside[: underside.index("add_feature_control_frame(")]
    assert "with _zoomed_on(adapter, datum_pick, HANGER_DATUM_PICK_ZOOM_HALF):" in loop
    assert "edge_xy=datum_pick, expected_entity=datum_ream," in loop
    assert "edge_entity" not in loop
    # The zoom window holds the whole rim and the pick is ON it, facing the tag.
    radius = drawing.HANGER_PIN_HOLE_DIA / 2.0 * drawing._HUB_BOTTOM_M_PER_MM
    assert radius < drawing.HANGER_DATUM_PICK_ZOOM_HALF / 2.0
    for datum, (x, y) in drawing.HANGER_DATUM_SYMBOL_XY.items():
        centre = (0.107, 0.172 if datum == "B" else 0.230)
        pick = drawing.hanger_ream_rim(centre, (x, y))
        assert math.dist(pick, centre) == pytest.approx(radius), datum
        to_pick = (pick[0] - centre[0], pick[1] - centre[1])
        to_tag = (x - centre[0], y - centre[1])
        assert to_pick[0] * to_tag[1] - to_pick[1] * to_tag[0] == pytest.approx(0.0, abs=1e-12)
        assert to_pick[0] * to_tag[0] + to_pick[1] * to_tag[1] > 0.0, datum


def test_hanger_datum_leaders_run_clear_of_the_ream_frames() -> None:
    # Farm run 20261009T171439353Z: datum B's leader, rim (107.5, 172.4) to
    # its tag at (122.0, 185.0) mm, ran 7.88 mm through the front frame's
    # text [78.9, 179.1]..[128.6, 184.2] mm (leader-through-text).
    from _layout_geometry import Box, Segment, segment_box_overlap_length

    x0, y0, x1, y1 = drawing.HANGER_REAM_FRAME_TEXT_BOX
    frames = {
        station: Box(fx + x0, fy + y0, fx + x1, fy + y1)
        for station, (fx, fy) in drawing.HANGER_REAM_FRAME_XY.items()
    }
    front = frames["front"]
    assert (front.xmin, front.ymin, front.xmax, front.ymax) == pytest.approx(
        (0.1928, 0.2305, 0.2275, 0.2350)
    )
    centre = drawing.HUB_BOTTOM_CENTER
    m_per_mm = drawing._HUB_BOTTOM_M_PER_MM
    for datum, station_z in (("B", part.STUD_Z_FRONT), ("C", part.STUD_Z_REAR)):
        hole = (
            centre[0] + part.PIN_HOLE_X * m_per_mm,
            centre[1] + station_z * m_per_mm,
        )
        tag = drawing.HANGER_DATUM_SYMBOL_XY[datum]
        leader = Segment(*drawing.hanger_ream_rim(hole, tag), *tag)
        for station, box in frames.items():
            assert segment_box_overlap_length(leader, box) == 0.0, (datum, station)
            # The 7 mm letter box above the tag point keeps 3 mm off the frame.
            letter = Box(tag[0] - 0.0035, tag[1], tag[0] + 0.0035, tag[1] + 0.007)
            assert (
                letter.xmin - box.xmax >= 0.003
                or box.xmin - letter.xmax >= 0.003
                or letter.ymin - box.ymax >= 0.003
                or box.ymin - letter.ymax >= 0.003
            ), (datum, station)
    # Datum C's tag stays in the window right of the crossbar, between the
    # rails' inner faces; datum B's, whose rightward leader would cross the
    # land-end dimension's bar-face extension line (_land_end_ink), stands
    # under the plan, below the front rail's outer face and its edge break,
    # left of the bar face, its leader running down from the ream.
    cx, cy = drawing.HANGER_DATUM_SYMBOL_XY["C"]
    assert cx > centre[0] + part.BAR_X1 * m_per_mm
    assert centre[1] - part.INNER_Z * m_per_mm < cy < centre[1] + part.INNER_Z * m_per_mm
    bx, by = drawing.HANGER_DATUM_SYMBOL_XY["B"]
    assert bx < centre[0] + part.BAR_X1 * m_per_mm
    assert by + 0.0035 < centre[1] - part.OUTER_Z * m_per_mm - 0.004


def test_datum_c_leaves_the_rear_ream_opposite_its_size_leader() -> None:
    """Farm run 20261027T030041319Z (machinist review): the ream size's open
    arrow and datum C's triangle both reached the rear +X ream from
    up-right and overlapped.  Datum C's leader now leaves that ream
    downward, into the window, clear of F-F's right arrow and letter, the
    size's leader rising from the same ream on the other side."""
    from _layout_geometry import Box, Segment, segment_box_distance

    ink = drawing.INK_CLEARANCE
    centre, m_per_mm = drawing.HUB_BOTTOM_CENTER, drawing._HUB_BOTTOM_M_PER_MM
    ream = (centre[0] + part.PIN_HOLE_X * m_per_mm, centre[1] + part.STUD_Z_REAR * m_per_mm)
    tag = drawing.HANGER_DATUM_SYMBOL_XY["C"]
    pick = drawing.hanger_ream_rim(ream, tag)
    leader = Segment(*pick, *tag)
    x, y = drawing.HANGER_PIN_DIA_TEXT_XY
    foot = (x - drawing.HANGER_PIN_DIA_TEXT_WIDTH / 2.0, y - drawing.HANGER_PIN_DIA_TEXT_HALF_HEIGHT)
    landing = drawing.hanger_ream_rim(ream, foot)
    to_tag = (pick[0] - ream[0], pick[1] - ream[1])
    to_size = (landing[0] - ream[0], landing[1] - ream[1])
    cosine = (to_tag[0] * to_size[0] + to_tag[1] * to_size[1]) / (
        math.hypot(*to_tag) * math.hypot(*to_size)
    )
    assert cosine < -0.5  # more than 120 deg apart
    # The leader leaves the rim below F-F's cutting line, never crossing it,
    # and clears F-F's right arrow and letter.
    lines, boxes, _picks, cut_y = _underside_locator_ink()
    assert pick[1] < cut_y and tag[1] < pick[1]
    letter = boxes["F-F right letter"]
    assert _segment_gap(leader, lines["F-F right arrow"]) >= 0.004
    assert segment_box_distance(leader, letter) >= 0.003
    # The tag's shoulder and letter box (6.35 mm right of the point, 7 mm
    # square, as datum C printed on 40d9d030e) stand clear of the letter,
    # datum B's tag and leader, and the front frame's leader.
    box = Box(tag[0] + 0.00635, tag[1] - 0.0035, tag[0] + 0.01335, tag[1] + 0.0035)
    shoulder = Segment(*tag, tag[0] + 0.00635, tag[1])
    assert _box_box_gap(
        (box.xmin, box.ymin, box.xmax, box.ymax),
        (letter.xmin, letter.ymin, letter.xmax, letter.ymax),
    ) >= 0.004
    b_tag = drawing.HANGER_DATUM_SYMBOL_XY["B"]
    b_ream = (ream[0], centre[1] + part.STUD_Z_FRONT * m_per_mm)
    b_leader = Segment(*drawing.hanger_ream_rim(b_ream, b_tag), *b_tag)
    b_box = (b_tag[0] + 0.00635, b_tag[1] - 0.0035, b_tag[0] + 0.01335, b_tag[1] + 0.0035)
    assert _box_box_gap((box.xmin, box.ymin, box.xmax, box.ymax), b_box) >= 0.004
    assert segment_box_distance(b_leader, box) >= 0.004
    front = _ream_frame_layout()["front"]
    for run in front[3]:
        assert segment_box_distance(run, box) >= ink
        assert _segment_gap(run, leader) >= ink
        assert _segment_gap(run, shoulder) >= ink


def _ream_frame_layout():
    """Each -X ream frame's (outline, ream centre, landing, leader runs)."""
    from _layout_geometry import Box, Segment

    centre, m_per_mm = drawing.HUB_BOTTOM_CENTER, drawing._HUB_BOTTOM_M_PER_MM
    ox0, oy0, ox1, oy1 = drawing.HANGER_REAM_FRAME_OUTLINE
    layout = {}
    for station, station_z in (("front", part.STUD_Z_FRONT), ("rear", part.STUD_Z_REAR)):
        fx, fy = drawing.HANGER_REAM_FRAME_XY[station]
        outline = Box(fx + ox0, fy + oy0, fx + ox1, fy + oy1)
        ream = (
            centre[0] + part.PIN_HOLE_NEG_X * m_per_mm,
            centre[1] + station_z * m_per_mm,
        )
        knee = drawing.hanger_ream_frame_knee((fx, fy), ream)
        landing = drawing.hanger_ream_rim(ream, knee)
        shoulder_x = outline.xmin if knee[0] < outline.xmin else outline.xmax
        runs = [Segment(shoulder_x, knee[1], *knee), Segment(*knee, *landing)]
        layout[station] = (outline, ream, landing, runs)
    return layout


def _segment_gap(a, b) -> float:
    """Distance between two segments; 0 when they cross or touch."""
    from _layout_geometry import point_segment_distance

    gap = min(
        point_segment_distance((a.x0, a.y0), b),
        point_segment_distance((a.x1, a.y1), b),
        point_segment_distance((b.x0, b.y0), a),
        point_segment_distance((b.x1, b.y1), a),
    )
    # Collinear runs (two shoulders on one row) neither cross nor separate
    # each other's ends; their endpoint distance is the gap.
    collinear = all(
        abs((a.x1 - a.x0) * (y - a.y0) - (a.y1 - a.y0) * (x - a.x0)) < 1e-12
        for x, y in ((b.x0, b.y0), (b.x1, b.y1))
    )
    return gap if collinear or _segments_apart(a, b) else 0.0


def _underside_locator_ink():
    """The underside locator's fixed lines and text boxes (sheet m) that the
    -X ream frames, the ream size, the knockout callout and their leaders keep
    clear of, the datum rim picks and F-F's cutting-line height."""
    from _layout_geometry import Box, Segment

    centre, m_per_mm = drawing.HUB_BOTTOM_CENTER, drawing._HUB_BOTTOM_M_PER_MM
    # F-F as run 20261009T174542021Z printed it: arrows x 91.33 / 118.67 from
    # the cutting line at y 230.05 mm, each running 12 mm sheet-down, its
    # letter [-1.2, +1.8] x [-20.25, -14.15] mm about the line's end.  The
    # The 25-wide crossbar moves each end 1.5 out (0.50 mm at 1:3).
    cut_y = centre[1] + drawing.HANGER_SECTION_Z * m_per_mm
    arrows = [centre[0] + x * m_per_mm for x in drawing.HANGER_SECTION_CUT_X]
    assert arrows == pytest.approx([0.0908333, 0.1191667], abs=5e-5)
    assert cut_y == pytest.approx(0.23005, abs=5e-5)
    lines = {"F-F cutting line": Segment(arrows[0], cut_y, arrows[1], cut_y)}
    boxes = {}
    for side, x in zip(("left", "right"), arrows):
        lines[f"F-F {side} arrow"] = Segment(x, cut_y, x, cut_y - 0.012)
        boxes[f"F-F {side} letter"] = Box(x - 0.0012, cut_y - 0.02025, x + 0.0018, cut_y - 0.01415)
    # The pocket length's extension lines, from its line to the pocket ends'
    # pick, and its block (see test_pocket_length_dimension_stands_outside_the_plan).
    line_x, _ = drawing.POCKET_LENGTH_TEXT_XY
    pick_x = centre[0] + (part.BAR_X0 + part.EDGE_CHAMFER + part.BAR_WEB_X0) / 2.0 * m_per_mm
    for sz in (-1.0, 1.0):
        y = centre[1] + sz * part.BAR_POCKET_Z * m_per_mm
        lines[f"138.0 extension {sz:+.0f}"] = Segment(line_x - 0.001, y, pick_x, y)
    tx, ty = drawing.POCKET_LENGTH_OFFSET_XY
    boxes["138.0 text"] = Box(tx - 0.0170, ty - 0.00875, tx + 0.0170, ty + 0.00875)
    # The land-end dimension (_land_end_ink): its extension lines, line,
    # text jog and block.
    land_lines, land_text = _land_end_ink()
    lines.update(land_lines)
    boxes["land-end text"] = land_text
    # The knockouts' callout block (see
    # test_knockout_callout_leader_passes_left_of_the_land_dimension).
    boxes["knockout callout"] = _knockout_callout_box()
    # Datum tags: each leader from its rim pick to the tag point, then a 6.35
    # mm shoulder right to the letter box (C printed [136.35, 253.47]..[143.33,
    # 260.49] mm about its point (130, 257) on the 40d9d030e render), with the
    # 7 mm letter box above the point the frame test allows for as well.
    picks = {}
    for datum, station_z in (("B", part.STUD_Z_FRONT), ("C", part.STUD_Z_REAR)):
        hole = (centre[0] + part.PIN_HOLE_X * m_per_mm, centre[1] + station_z * m_per_mm)
        tag = drawing.HANGER_DATUM_SYMBOL_XY[datum]
        picks[datum] = drawing.hanger_ream_rim(hole, tag)
        lines[f"datum {datum} leader"] = Segment(*picks[datum], *tag)
        boxes[f"datum {datum} tag"] = Box(tag[0] - 0.0035, tag[1] - 0.0036, tag[0] + 0.0134, tag[1] + 0.007)
    return lines, boxes, picks, cut_y


def _locator_circles():
    """The four corner bosses' and both datum (+X) reams' printed circles
    (x, y, r) in the underside locator, sheet m."""
    centre, m_per_mm = drawing.HUB_BOTTOM_CENTER, drawing._HUB_BOTTOM_M_PER_MM
    circles = {
        f"boss {sx:+d},{z:+.0f}": (
            centre[0] + sx * part.COLUMN_X * m_per_mm,
            centre[1] + z * m_per_mm,
            part.BOSS_DIA / 2.0 * m_per_mm,
        )
        for sx in (-1, 1)
        for z in (part.FRONT_COLUMN_Z, part.REAR_COLUMN_Z)
    }
    for datum, station_z in (("B", part.STUD_Z_FRONT), ("C", part.STUD_Z_REAR)):
        circles[f"+X ream {datum}"] = (
            centre[0] + part.PIN_HOLE_X * m_per_mm,
            centre[1] + station_z * m_per_mm,
            drawing.HANGER_PIN_HOLE_DIA / 2.0 * m_per_mm,
        )
    return circles


def _land_end_ink():
    """The land-end dimension's ink (sheet m): extension lines from the
    front crossbar's sharp +X side bottom (its gusset end, |z| 75) and the
    land end's edge (|z| 105.5), each 1 mm short of its edge as the 73.0's
    printed (from y 163.83 for an edge ending at 164.83), down to 1 mm past
    the dimension line at y 145; that line between them, arrows inside; and
    the text, parked on a jog at LAND_TEXT_OFFSET_XY, as the 73.0's
    three-row block printed there (farm run 20261027T133857303Z: x 124.18
    from y 136.67 to 151.0, 2.8 mm a glyph), its widest row now 24 glyphs."""
    from _layout_geometry import Box, Segment

    centre, m_per_mm = drawing.HUB_BOTTOM_CENTER, drawing._HUB_BOTTOM_M_PER_MM
    bar_x = centre[0] + part.BAR_X1 * m_per_mm
    land_x = centre[0] + part.LAND_X1 * m_per_mm
    bar_top = centre[1] - (part.INNER_Z - part.GUSSET) * m_per_mm - 0.001
    land_top = centre[1] - part.WEB_IN_Z * m_per_mm - 0.001
    line_y = drawing.LAND_END_TEXT_XY[1]
    rows = drawing.LAND_END_CALLOUT.splitlines()
    text = Box(0.12418, 0.13667, 0.12418 + 0.0028 * max(map(len, rows)), 0.1510)
    lines = {
        "land-end bar-face extension": Segment(bar_x, line_y - 0.001, bar_x, bar_top),
        "land-end land extension": Segment(land_x, line_y - 0.001, land_x, land_top),
        "land-end line": Segment(bar_x, line_y, land_x, line_y),
        "land-end jog": Segment(drawing.LAND_END_TEXT_XY[0], line_y, text.xmin, text.ymin),
    }
    return lines, text


def test_land_end_dimension_is_crossed_by_no_leader() -> None:
    """Farm run 20261027T133857303Z (layout audit, leader-crosses-line): the
    knockout callout's leader crossed the land's -X extension line.  The
    land is located end by end from the crossbar's +X face instead: .95 =
    (2.884 - .984)/2, four ends, symmetric, so the full
    land stays defined.  No leader on the sheet crosses its lines, and no
    text or tag box sits on them."""
    from _layout_geometry import Box, Segment, segment_box_distance

    assert part.LAND_X1 - part.BAR_X1 == pytest.approx(24.13)  # .95
    assert (part.LAND_X1 - part.LAND_X0) == pytest.approx(24.9936 + 2.0 * 24.13)
    assert part.BAR_X1 - part.HANGER_X == pytest.approx(part.HANGER_X - part.BAR_X0)
    assert part.LAND_X1 - part.HANGER_X == pytest.approx(part.HANGER_X - part.LAND_X0)
    assert "crossbar junction land" not in spec.DRAWING_REFERENCE_PRECISION
    assert drawing.LAND_END_CALLOUT.splitlines() == [
        "4X LAND END FROM", "CROSSBAR FACE, EACH SIDE",
    ]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    land = source[source.index("    land = _checked_dimension(") :][:1400]
    assert "p0=(BAR_X1, -HALF_H, -(BAR_POCKET_Z + INNER_Z - GUSSET)/2)," in land
    assert "p1=(LAND_X1, -HALF_H+EDGE_CHAMFER, -(INNER_Z+WEB_IN_Z)/2)," in land
    assert 'label="land end from crossbar face"' in land
    assert "expected_mm=LAND_X1-BAR_X1," in land
    assert "suffix=LAND_END_CALLOUT," in land
    assert "    land.ArrowSide = _DIM_ARROWS_INSIDE\n" in land
    assert "LAND_X0" not in land
    centre, m_per_mm = drawing.HUB_BOTTOM_CENTER, drawing._HUB_BOTTOM_M_PER_MM
    assert drawing.LAND_END_TEXT_XY[0] == pytest.approx(
        centre[0] + (part.BAR_X1 + part.LAND_X1) / 2.0 * m_per_mm, abs=1e-5
    )
    land_lines, text = _land_end_ink()
    # The arrows (3.556 mm each) fit inside the 8 mm run.
    run = land_lines["land-end line"]
    assert run.x1 - run.x0 >= 2.0 * 0.003556 + 0.0005
    # Every leader on the locator: the knockout callout's, both datums',
    # both frames', the ream size's.
    ink = drawing.INK_CLEARANCE
    leaders = {}
    block = _knockout_callout_box()
    floor = (
        centre[0] + part.PIN_HOLE_NEG_X * m_per_mm,
        centre[1] + part.STUD_Z_FRONT * m_per_mm,
    )
    leaders["knockout"] = Segment(block.xmax, block.ymin, *floor)
    reams = {}
    for datum, station_z in (("B", part.STUD_Z_FRONT), ("C", part.STUD_Z_REAR)):
        ream = (centre[0] + part.PIN_HOLE_X * m_per_mm, centre[1] + station_z * m_per_mm)
        reams[datum] = ream
        tag = drawing.HANGER_DATUM_SYMBOL_XY[datum]
        leaders[f"datum {datum}"] = Segment(*drawing.hanger_ream_rim(ream, tag), *tag)
        leaders[f"datum {datum} shoulder"] = Segment(*tag, tag[0] + 0.00635, tag[1])
    for station, (_outline, _ream, _landing, runs) in _ream_frame_layout().items():
        for index, frame_run in enumerate(runs):
            leaders[f"{station} frame {index}"] = frame_run
    x, y = drawing.HANGER_PIN_DIA_TEXT_XY
    foot = (x - drawing.HANGER_PIN_DIA_TEXT_WIDTH / 2.0, y - drawing.HANGER_PIN_DIA_TEXT_HALF_HEIGHT)
    leaders["size"] = Segment(*drawing.hanger_ream_rim(reams["C"], foot), *foot)
    # The bar-face extension line runs 1.1 mm from the front +X ream's rim
    # (the ream's own wall to the face at 1:3): datum B's leader leaves that
    # rim, so it keeps the rim's own distance there and draws away below.
    rim_gap = (
        land_lines["land-end bar-face extension"].x0
        - reams["B"][0]
        - drawing.HANGER_PIN_HOLE_DIA / 2.0 * m_per_mm
    )
    assert rim_gap == pytest.approx(0.0011, abs=1e-4)
    for name, line in land_lines.items():
        for leader_name, leader in leaders.items():
            needed = rim_gap if leader_name == "datum B" else ink
            assert _segment_gap(leader, line) >= needed, (name, leader_name)
    # Datum B's leader draws away from the face: 2.8 mm off it at the
    # dimension line, its knockout neighbour 3.5 mm off.
    b_leader = leaders["datum B"]
    at_line = b_leader.x0 + (b_leader.x1 - b_leader.x0) * (
        (drawing.LAND_END_TEXT_XY[1] - b_leader.y0) / (b_leader.y1 - b_leader.y0)
    )
    assert land_lines["land-end bar-face extension"].x0 - at_line >= 0.0045
    assert _segment_gap(b_leader, leaders["knockout"]) >= 0.0035
    # Datum B's tag box and the land-end text clear every land-end line and
    # each other; the text clears detail J and the +X station rows.
    b_tag = drawing.HANGER_DATUM_SYMBOL_XY["B"]
    b_box = Box(b_tag[0] + 0.00635, b_tag[1] - 0.0035, b_tag[0] + 0.01335, b_tag[1] + 0.0035)
    for name, line in land_lines.items():
        assert segment_box_distance(line, b_box) >= ink, name
    for name, line in land_lines.items():
        if name != "land-end jog":
            assert segment_box_distance(line, text) >= ink, name
    assert _box_box_gap(
        (b_box.xmin, b_box.ymin, b_box.xmax, b_box.ymax), (text.xmin, text.ymin, text.xmax, text.ymax)
    ) >= 0.004
    cx, cy = drawing.HUB_DETAIL_CENTER
    near = (min(max(cx, text.xmin), text.xmax), min(max(cy, text.ymin), text.ymax))
    assert math.dist(near, (cx, cy)) - 0.076 >= 0.010
    for name, row in _station_rows(drawing.PIN_STATION_OFFSET_XY).items():
        assert _box_box_gap(row, (text.xmin, text.ymin, text.xmax, text.ymax)) >= 0.004, name
    # The tag box clears the knockout block and the span's frame and count.
    assert _box_box_gap(
        (b_box.xmin, b_box.ymin, b_box.xmax, b_box.ymax),
        (block.xmin, block.ymin, block.xmax, block.ymax),
    ) >= 0.004
    for box in _span_text_boxes().values():
        assert _box_box_gap((b_box.xmin, b_box.ymin, b_box.xmax, b_box.ymax), box) >= 0.004


def _knockout_callout_box():
    """The knockouts' callout block, sheet m, as farm run
    20261027T030041319Z printed it about its point: underline to cap line,
    left text edge to the underline's right end (where the leader leaves)."""
    from _layout_geometry import Box

    kx, ky = drawing.HANGER_KNOCKOUT_CALLOUT_XY
    x0, y0, x1, y1 = drawing.HANGER_KNOCKOUT_CALLOUT_INK
    return Box(kx + x0, ky + y0, kx + x1, ky + y1)


def test_ream_frames_stand_outside_the_plan_clear_of_every_line() -> None:
    # Machinist review of 11783475: inside the plan the frames and their
    # leaders crossed F-F, the datum leaders and the land's dimension.  Both
    # stand outside the plan, the rear above it and the front right of it,
    # each leader running from its outline's end to its -X ream's rim facing
    # it, clear of the corner bosses and the datum reams.
    from _layout_geometry import segment_box_distance, segment_circle_distance

    ink = drawing.INK_CLEARANCE
    centre, m_per_mm = drawing.HUB_BOTTOM_CENTER, drawing._HUB_BOTTOM_M_PER_MM
    layout = _ream_frame_layout()
    lines, boxes, picks, cut_y = _underside_locator_ink()
    plan_top = centre[1] + drawing.PLAN_HALF_Z * m_per_mm
    plan_right = centre[0] + drawing.PLAN_HALF_X * m_per_mm
    circles = _locator_circles()
    sheet = drawing.SHEET_FRAME
    radius = drawing.HANGER_PIN_HOLE_DIA / 2.0 * m_per_mm
    for station, (outline, ream, landing, runs) in layout.items():
        # Outside the plan, inside the sheet frame: the rear frame above it,
        # the front frame and its shoulder right of it, where they leave the
        # band over the plan to the rear ream's size.
        if station == "rear":
            assert outline.ymin >= plan_top + ink, station
        else:
            assert min(outline.xmin, runs[0].x1) >= plan_right + ink, station
        for run in runs:
            for name, circle in circles.items():
                assert segment_circle_distance(run, circle) >= ink, (station, name)
        assert sheet[0] + ink <= outline.xmin and outline.xmax <= sheet[2] - ink, station
        assert outline.ymax <= sheet[3] - ink, station
        # Clear of detail J's unchanged 76 mm fence beside the plan.
        cx, cy = drawing.HUB_DETAIL_CENTER
        near = (min(max(cx, outline.xmin), outline.xmax), min(max(cy, outline.ymin), outline.ymax))
        assert math.dist(near, (cx, cy)) - 0.076 >= ink, station
        for other, (_outline, _ream, _landing, other_runs) in layout.items():
            if other != station:
                for run in other_runs:
                    assert segment_box_distance(run, outline) >= ink, (station, other)
        # On the -X ream's rim, facing the knee.
        assert math.dist(landing, ream) == pytest.approx(radius), station
        for datum, pick in picks.items():
            assert math.dist(landing, pick) >= ink, (station, datum)
        for name, box in boxes.items():
            gap = max(
                box.xmin - outline.xmax, outline.xmin - box.xmax,
                box.ymin - outline.ymax, outline.ymin - box.ymax,
            )
            assert gap >= ink, (station, name)
            for run in runs:
                assert segment_box_distance(run, box) >= ink, (station, name)
        for name, line in lines.items():
            assert segment_box_distance(line, outline) >= ink, (station, name)
            for run in runs:
                if name == "F-F cutting line":
                    # The rear leader lands on the ream F-F cuts: it must
                    # not cross the line.
                    assert _segments_apart(run, line), (station, name)
                else:
                    assert _segment_gap(run, line) >= ink, (station, name)
    front, rear = layout["front"], layout["rear"]
    assert _box_box_gap(
        (front[0].xmin, front[0].ymin, front[0].xmax, front[0].ymax),
        (rear[0].xmin, rear[0].ymin, rear[0].xmax, rear[0].ymax),
    ) >= ink
    for a in front[3]:
        for b in rear[3]:
            assert _segment_gap(a, b) >= ink
    # The rear leader lands above F-F's cutting line, not on it.
    assert rear[2][1] > cut_y


def test_knockout_callout_leader_passes_left_of_the_land_dimension() -> None:
    # The knockouts' native callout parks under the front rail where the
    # old slot width's block stood (machinist review of 11783475 and codex
    # review of fe1a7611: that leader must clear the 73.0's line).  Farm run
    # 20261027T030041319Z: the underline began 0.34 mm inside the inner
    # border (machinist review, rule 13), so the block stands with visible
    # air inside it; the leader leaves the underline's right end for the
    # front -X ream's knockout floor circle.
    from _layout_geometry import Box, Segment, segment_box_distance, segment_circle_distance

    ink = drawing.INK_CLEARANCE
    centre, m_per_mm = drawing.HUB_BOTTOM_CENTER, drawing._HUB_BOTTOM_M_PER_MM
    block = _knockout_callout_box()
    # The measured block about its point: centred rows, 62.9 mm from the
    # text's left edge to the underline's end; four rows 5.56 mm apart, 20.2
    # mm underline to cap line (three printed 14.7), none wider than 21.
    x0, y0, x1, y1 = drawing.HANGER_KNOCKOUT_CALLOUT_INK
    assert (x1 - x0, y1 - y0) == pytest.approx((0.06288, 0.01466 + 0.00556))
    rows = [
        spec.HANGER_KNOCKOUT_CALLOUT_ABOVE,
        f"4X \u00d8{spec.HANGER_KNOCKOUT_DIA:.{spec.HANGER_KNOCKOUT_DIA_PLACES}f} THRU ALL",
        *spec.HANGER_KNOCKOUT_CALLOUT_BELOW.splitlines(),
    ]
    assert len(rows) == 4 and max(map(len, rows)) <= len("MHA-SM-VN-53 KNOCKOUT")
    sheet = drawing.SHEET_FRAME
    assert block.xmin - sheet[0] >= 0.0035
    # The land's ends are dimensioned from the crossbar's +X face
    # (_land_end_ink): every one of that dimension's lines stands right of
    # the leader and clear of the block (farm run 20261027T133857303Z: the
    # 73.0's -X extension line crossed the leader).
    land_lines, _text = _land_end_ink()
    for name, line in land_lines.items():
        assert segment_box_distance(line, block) >= 2.0 * ink, name
    # UNDERSIDE LOCATOR note as printed (rows 4.52 mm apart below its
    # top-left point, the widest 56.7 mm).
    nx, ny = drawing.HUB_BOTTOM_NOTE_XY
    note = Box(nx, ny - 0.0136, nx + 0.0567, ny)
    assert _box_box_gap(
        (block.xmin, block.ymin, block.xmax, block.ymax),
        (note.xmin, note.ymin, note.xmax, note.ymax),
    ) >= 0.004
    circles = _locator_circles()
    for name, circle in circles.items():
        x, y, r = circle
        near = (min(max(x, block.xmin), block.xmax), min(max(y, block.ymin), block.ymax))
        assert math.dist(near, (x, y)) - r >= ink, name
    # The front rail's outer face and the 43.0's lower arrow tail (x 24.67,
    # down to y 156.32 mm) stay above the block.
    rail_y = centre[1] - part.OUTER_Z * m_per_mm
    assert min(rail_y, 0.15632) - block.ymax >= 0.003
    floor = (
        centre[0] + part.PIN_HOLE_NEG_X * m_per_mm,
        centre[1] + part.STUD_Z_FRONT * m_per_mm,
    )
    leader = Segment(block.xmax, block.ymin, *floor)
    assert segment_box_distance(leader, note) >= ink
    for name, circle in circles.items():
        assert segment_circle_distance(leader, circle) >= ink, name
    # It crosses no line of the land-end dimension: it lands left of them all.
    for name, line in land_lines.items():
        assert _segment_gap(leader, line) >= 2.0 * ink, name
    assert floor[0] < min(min(line.x0, line.x1) for line in land_lines.values()) - 2.0 * ink
    # Clear of F-F's BASIC span text.
    for name, span in _span_text_boxes().items():
        assert _box_box_gap((block.xmin, block.ymin, block.xmax, block.ymax), span) >= 0.004, name
        assert segment_box_distance(leader, Box(*span)) >= 0.004, name
    # The block stands left of the crossbar's outer face.
    assert block.xmax < centre[0] + part.BAR_X0 * m_per_mm - ink


# Farm run 20261027T030041319Z: the +X F-F station block's rows, centred on
# its offset point's x, baselines 5.56 mm apart from one row above the
# point, 3.5 mm cap height, each row's printed width.
_STATION_ROW_WIDTHS = (0.0116, 0.0345, 0.0469, 0.0486)


def _station_rows(offset_xy):
    """The +X F-F station block's printed rows (x0, y0, x1, y1), sheet m."""
    ox, oy = offset_xy
    rows = drawing.PIN_STATION_CALLOUT.splitlines()
    assert len(rows) + 1 == len(_STATION_ROW_WIDTHS)
    return {
        name: (ox - width / 2.0, base, ox + width / 2.0, base + 0.0035)
        for index, (name, width) in enumerate(zip(("value", *rows), _STATION_ROW_WIDTHS))
        for base in (oy + 0.00556 * (1 - index),)
    }


def _span_text_boxes():
    """F-F's BASIC span text (sheet m), about its offset point: farm run
    20261027T133857303Z printed "2X 15.264" centred on it, x 88.2..110.3, y
    119.3..122.8 mm, its BASIC frame round the value alone, 1.2 mm out and
    y 118.33..123.89.  The value alone, centred, then frames x 91.85..108.15;
    the count row "2X" stands one 5.56 mm row above the value's baseline, 2
    glyphs at 2.6 mm (estimated)."""
    ox, oy = drawing.HANGER_PIN_SPAN_OFFSET_XY
    value = len(f"{2.0 * spec.HANGER_PIN_X:.3f}") * 0.00232
    count = len(drawing.HANGER_PIN_SPAN_ABOVE) * 0.0026
    base = oy - 0.0007
    return {
        "frame": (ox - value / 2.0 - 0.0012, oy - 0.00167, ox + value / 2.0 + 0.0012, oy + 0.00389),
        "count": (ox - count / 2.0, base + 0.00556, ox + count / 2.0, base + 0.00556 + 0.0035),
    }


def test_pocket_length_dimension_stands_outside_the_plan() -> None:
    # The 138.0 line, its extension lines and its text stay out of the plan
    # silhouette and detail J's fence; the text box is the three-row block
    # farm c75ac06 printed (17.5 mm tall, widest row 33.9 mm by the 40d9d030e
    # render's glyphs), which the two-row value + "2X POCKET, E-E" fits in.
    from _layout_geometry import Box, Segment, segment_box_distance

    centre, m_per_mm = drawing.HUB_BOTTOM_CENTER, drawing._HUB_BOTTOM_M_PER_MM
    line_x, _ = drawing.POCKET_LENGTH_TEXT_XY
    text_x, text_y = drawing.POCKET_LENGTH_OFFSET_XY
    text = Box(text_x - 0.0170, text_y - 0.00875, text_x + 0.0170, text_y + 0.00875)
    clearance = 0.00178
    plan_left = centre[0] - drawing.PLAN_HALF_X * m_per_mm
    plan_top = centre[1] + drawing.PLAN_HALF_Z * m_per_mm
    fence_x = centre[0] + part.GOOSENECK_X * m_per_mm
    fence_y = centre[1] + part.GOOSENECK_Z * m_per_mm
    fence_r = (part.HUB_GUSSET_HALF_OUT + part.HUB_BOSS_DROP) * m_per_mm
    pocket = [centre[1] + sz * part.BAR_POCKET_Z * m_per_mm for sz in (-1.0, 1.0)]
    sheet_x0, _, _, sheet_y1 = drawing.SHEET_FRAME
    # The line runs left of the barrels and the fence, inside the sheet.
    assert sheet_x0 + drawing.INK_CLEARANCE < line_x < fence_x - fence_r - clearance
    assert line_x < plan_left - clearance
    # The extension lines pass under and over the fence, between the bosses.
    boss_r = part.BOSS_DIA / 2.0 * m_per_mm
    for y in pocket:
        assert abs(y - fence_y) > fence_r + clearance
        for boss_z in (part.FRONT_COLUMN_Z, part.REAR_COLUMN_Z):
            assert abs(y - (centre[1] + boss_z * m_per_mm)) > boss_r + clearance
    # The text sits above the plan's top-left corner, inside the sheet frame.
    assert text.xmin > sheet_x0 + drawing.INK_CLEARANCE
    assert text.ymax < sheet_y1 - drawing.INK_CLEARANCE
    assert text.ymin > plan_top + clearance
    boss_x = centre[0] - part.COLUMN_X * m_per_mm
    boss_y = centre[1] + part.REAR_COLUMN_Z * m_per_mm
    nearest = (
        min(max(boss_x, text.xmin), text.xmax),
        min(max(boss_y, text.ymin), text.ymax),
    )
    assert math.dist(nearest, (boss_x, boss_y)) > boss_r + clearance
    assert (
        segment_box_distance(Segment(line_x, pocket[0], line_x, pocket[1]), text) > 0.0
    )


def test_far_wall_print_worst_engagement_meets_thread_rule() -> None:
    import build_fr_frame_assembly as assembly
    from _mcmaster_90280a837 import SHANK_DIA

    engagement = drawing.CROSS_SCREW_FAR_WALL_MIN_ENGAGEMENT
    # Rule 18 (thread engagement): the printed bands only shorten the far-wall engagement, and
    # the shortest still holds 1.5D.
    assert 1.5 * SHANK_DIA <= engagement < assembly.TOP_FAR_CASTING_ENGAGEMENT


def _segments_apart(a, b) -> bool:
    """True when two segments neither cross nor touch."""

    def side(p, q, r) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    a0, a1, b0, b1 = (a.x0, a.y0), (a.x1, a.y1), (b.x0, b.y0), (b.x1, b.y1)
    return side(a0, a1, b0) * side(a0, a1, b1) > 0 or side(b0, b1, a0) * side(b0, b1, a1) > 0


def test_finished_grip_prints_bare_at_the_title_block_band() -> None:
    """Owner ruling 2026-10-18: the 1.437 grip takes the title block's .XXX
    band with no callout; MHA-SM-VN-52 is cut to the measured grip at
    MHA-SM-00, so the grip no longer sets thread engagement."""
    assert (spec.HANGER_GRIP, spec.HANGER_GRIP_TOL) == pytest.approx((36.4998, 0.127))
    assert drawing.HANGER_SECTION_CALLOUTS["HangerGrip"] == ""


def test_hanger_section_cuts_the_crossbar_from_window_to_window() -> None:
    """F-F cuts the rear station across the crossbar and its gussets only:
    both ends stand in open window, past the gussets' reach at that z and
    short of the side rails, and the cut stays below the window rim break."""
    x0, x1 = drawing.HANGER_SECTION_CUT_X
    reach = drawing.HANGER_SECTION_GUSSET_REACH
    assert drawing.HANGER_SECTION_Z == part.STUD_Z_REAR
    assert reach == pytest.approx(part.GUSSET - (part.INNER_Z - part.STUD_Z_REAR))
    assert -part.INNER_X < x0 < part.BAR_X0 - reach
    assert part.BAR_X1 + reach < x1 < part.INNER_X
    assert part.STUD_Z_REAR < part.INNER_Z - part.EDGE_CHAMFER


def test_hanger_section_text_stays_on_the_sheet_off_the_title_block() -> None:
    from _layout_geometry import Box, Segment, segment_box_distance

    points = {
        "grip": drawing.HANGER_GRIP_TEXT_XY,
        "station": drawing.PIN_STATION_TEXT_XY,
        "station offset": drawing.PIN_STATION_OFFSET_XY,
        "span": drawing.HANGER_PIN_SPAN_TEXT_XY,
        "span offset": drawing.HANGER_PIN_SPAN_OFFSET_XY,
        "caption": drawing.HANGER_SECTION_CAPTION_XY,
        "depth offset": drawing.HANGER_PIN_DEPTH_OFFSET_XY,
        **drawing.HANGER_SECTION_KEEP,
    }
    for name, (x, y) in points.items():
        assert 0.013 < x < TITLE_BLOCK[0] and 0.013 < y < 0.150, name
    # The +X station reads above the profile on one row; the BASIC span's
    # line runs 6 mm over it between the two ream axes, clear of the +X
    # block's printed rows (_station_rows), its text parked above-left.
    ink = drawing.INK_CLEARANCE
    top = drawing._hanger_section_xy(part.HANGER_X, part.HALF_H)[1]
    station_y = drawing.PIN_STATION_TEXT_XY[1]
    span_y = drawing.HANGER_PIN_SPAN_TEXT_XY[1]
    assert top < station_y and span_y - station_y >= 0.005
    span_x = [
        drawing._hanger_section_xy(x, 0.0)[0] for x in (part.PIN_HOLE_NEG_X, part.PIN_HOLE_X)
    ]
    assert drawing.HANGER_PIN_SPAN_TEXT_XY[0] == pytest.approx(sum(span_x) / 2.0)
    span_line = Segment(span_x[0], span_y, span_x[1], span_y)
    rows = _station_rows(drawing.PIN_STATION_OFFSET_XY)
    boxes = _span_text_boxes()
    span = boxes["frame"]
    leader = Segment(span_x[0], span_y, min(max(span_x[0], span[0]), span[2]), span[1])
    # The count row stands wholly above the BASIC frame, so neither of the
    # frame's sides runs through it (extension-through-own-text).
    assert boxes["count"][1] - span[3] >= 0.0005
    assert span[0] < boxes["count"][0] and boxes["count"][2] < span[2]
    for name, row in rows.items():
        assert _box_box_gap(row, TITLE_BLOCK) >= ink, name
        assert row[1] >= top + ink, name
        assert segment_box_distance(span_line, Box(*row)) >= 0.004, name
        assert segment_box_distance(leader, Box(*row)) >= 0.004, name
        assert _box_box_gap(row, span) >= 0.004, name
    # The span's frame and count stand over its line, under the locator's
    # land-end line, clear of the +X station's rows, the knockouts' callout
    # and the bottom view's note.
    assert span[1] - span_y >= ink
    count = boxes["count"]
    assert count[3] <= drawing.LAND_END_TEXT_XY[1] - ink
    assert segment_box_distance(span_line, Box(*count)) >= 0.004
    for name, row in rows.items():
        assert _box_box_gap(row, count) >= 0.004, name
    knockout = _knockout_callout_box()
    nx, ny = drawing.HUB_BOTTOM_NOTE_XY
    for name, box in boxes.items():
        assert _box_box_gap(
            box, (knockout.xmin, knockout.ymin, knockout.xmax, knockout.ymax)
        ) >= 0.004, name
        assert _box_box_gap(box, (nx, ny - 0.0136, nx + 0.0567, ny)) >= 0.004, name


def test_hanger_station_and_span_lines_end_inside_short_of_the_station_rows() -> None:
    """Farm run 20261027T195317391Z (machinist review r1): with SolidWorks'
    outside arrows, the span's right tail ran 6.35 mm past the +X ream's
    axis into the "S" of "SCREW" and the station's into the foot of
    "MATCHES".  Both arrows now stand inside, so each line ends on the +X
    ream's axis, an ink clearance and more short of every station row; the
    tails would not (negative control)."""
    import inspect

    source = inspect.getsource(drawing._hanger_section)
    assert "    station = _checked_dimension(\n" in source
    assert (
        '    for dimension, name in ((station, "dowel hole from hanger axis"), '
        '(span, "-X dowel ream span")):\n'
        "        dimension.ArrowSide = _DIM_ARROWS_INSIDE\n"
    ) in source
    ink = drawing.INK_CLEARANCE
    tail = 0.00635
    axis = drawing._hanger_section_xy(part.PIN_HOLE_X, 0.0)[0]
    lines = {
        "station": drawing.PIN_STATION_TEXT_XY[1],
        "span": drawing.HANGER_PIN_SPAN_TEXT_XY[1],
    }
    rows = _station_rows(drawing.PIN_STATION_OFFSET_XY)
    struck = []
    for line_name, y in lines.items():
        for row_name, (x0, y0, _x1, y1) in rows.items():
            if not y0 - ink < y < y1 + ink:
                continue
            assert x0 - axis >= ink, (line_name, row_name)
            if x0 - (axis + tail) < ink:
                struck.append((line_name, row_name))
    assert len(struck) == 2, struck


def _hanger_section_ink():
    """F-F's profile and annotation ink (sheet m), from the model and farm
    run 20261027T143609236Z's measured F-F: the grip's extension lines leave
    its attachment at x 149.5 mm and run 1 mm past its line; the depth's
    leave the +X ream's +X wall 1 mm off (x 130.22 mm) at the underside and
    the floor; extension and dimension lines 1 mm past, the depth's arrows
    outside to 6.35 mm tails; texts 3.5 mm tall, " 36.50 " 14.22 mm wide and
    centred on its line; the caption to 141.59 mm, its top at 29.14 mm.
    The depth's rows in farm run 20261027T175429300Z's measured form
    (offset 209.0, 77.56 mm: the depth from y 80.34, "4X FLAT BOTTOM," from
    74.78, the next row from 69.23, the stub from the line's 62.75 mm mid to
    the underline's near end): each row centred on the offset x, from 2.78
    mm above the offset y, then 5.56 mm apart under it from 2.78 mm, the
    last on the underline; the inch rows' widths estimated at the measured
    "CORNER R0.1 MAX" row's pitch."""
    from _layout_geometry import Box, Segment

    s = drawing._hanger_section_xy
    z_low, z_high = -part.HALF_H, part.HALF_H
    bottom, top = s(0.0, z_low)[1], s(0.0, z_high)[1]
    reach = drawing.HANGER_SECTION_GUSSET_REACH
    left, right = s(part.BAR_X0 - reach, 0.0)[0], s(part.BAR_X1 + reach, 0.0)[0]
    r = spec.HANGER_PIN_HOLE_DIA / 2.0
    hole_r = spec.HANGER_CLEARANCE_DIA / 2.0
    floor = s(0.0, z_low + spec.HANGER_PIN_HOLE_DEPTH)[1]
    walls = {
        "-X ream -X wall": s(part.PIN_HOLE_NEG_X - r, 0.0)[0],
        "-X ream +X wall": s(part.PIN_HOLE_NEG_X + r, 0.0)[0],
        "+X ream -X wall": s(part.PIN_HOLE_X - r, 0.0)[0],
        "+X ream +X wall": s(part.PIN_HOLE_X + r, 0.0)[0],
    }
    gaps = [
        (walls["-X ream -X wall"], walls["-X ream +X wall"]),
        (s(part.HANGER_X - hole_r, 0.0)[0], s(part.HANGER_X + hole_r, 0.0)[0]),
        (walls["+X ream -X wall"], walls["+X ream +X wall"]),
    ]
    edges = {"left end": Segment(left, bottom, left, top), "right end": Segment(right, bottom, right, top)}
    x = left
    for index, (g0, g1) in enumerate(gaps):
        edges[f"underside {index}"] = Segment(x, bottom, g0, bottom)
        x = g1
    edges[f"underside {len(gaps)}"] = Segment(x, bottom, right, bottom)
    for name, wall in walls.items():
        edges[name] = Segment(wall, bottom, wall, floor)
    gx = drawing.HANGER_GRIP_TEXT_XY[0]
    dx, dy = drawing.HANGER_SECTION_KEEP["HangerPinHoleDepth"]
    ox, oy = drawing.HANGER_PIN_DEPTH_OFFSET_XY
    height = 0.0035
    rows = [".470", *spec.HANGER_PIN_DEPTH_CALLOUT.splitlines()]
    glyph = 0.0419368 / 15.0  # the measured "CORNER R0.1 MAX" row's pitch
    widths = {
        ".470": 0.0090514,
        "4X FLAT BOTTOM,": 0.0382132,
        "CORNER": 6 * glyph,
        "R.003 MAX": 9 * glyph,
    }
    assert set(rows) == set(widths)
    bases = (oy + 0.0027781, oy - 0.0027781, oy - 0.0083344, oy - 0.0138907)
    underline_y = bases[-1]
    underline_half = max(widths.values()) / 2.0
    lines = {
        "grip line": Segment(gx, bottom, gx, top),
        "grip extension underside": Segment(0.1495, bottom, gx + 0.001, bottom),
        "grip extension top": Segment(0.1495, top, gx + 0.001, top),
        "depth extension underside": Segment(walls["+X ream +X wall"] + 0.001, bottom, dx + 0.001, bottom),
        "depth extension floor": Segment(walls["+X ream +X wall"] + 0.001, floor, dx + 0.001, floor),
        "depth line": Segment(dx, bottom, dx, floor),
        "depth tail low": Segment(dx, bottom, dx, bottom - 0.00635),
        "depth tail high": Segment(dx, floor, dx, floor + 0.00635),
        "depth jog": Segment(dx, dy, ox - underline_half, underline_y),
        "depth underline": Segment(ox - underline_half, underline_y, ox + underline_half, underline_y),
    }
    gy = drawing.HANGER_GRIP_TEXT_XY[1]
    texts = {
        "grip": Box(gx - 0.00711, gy - 0.00175, gx + 0.00711, gy + 0.00175),
        **{
            f"depth row {index}": Box(
                ox - widths[row] / 2.0, base, ox + widths[row] / 2.0, base + height
            )
            for index, (row, base) in enumerate(zip(rows, bases))
        },
        "caption": Box(0.0984, 0.01541, 0.14159, 0.02914),
    }
    return edges, lines, texts


def test_pad_width_leaves_the_plan_for_detail_j() -> None:
    """The plan's only import is the Ø17.00 bore: under the top flange that
    hidden-lines-removed plan shows no pad (farm run 20261027T195317391Z,
    machinist review r2+r3), and the 28.0's line there ran through the
    Ø17.00 leader (run 20261027T190435153Z, rule 14), so it cannot cross it
    again.  DETAIL J, where the pad's faces are drawn, carries it."""
    import inspect

    assert drawing.HUB_TOP_KEEP == {"GnDia": (0.040, 0.185)}
    assert set(drawing.HUB_TOP_CALLOUTS) == {"GnDia"}
    assert drawing.HUB_BOTTOM_KEEP["RibWidth"] == drawing.RIB_WIDTH_LINE_XY
    assert drawing.HUB_BOTTOM_KEEP["HubDia"] == drawing.HUB_BOSS_DIA_TEXT_XY
    assert set(drawing.HUB_BOTTOM_CALLOUTS) == set(drawing.HUB_BOTTOM_KEEP)
    assert drawing.HUB_BOTTOM_CALLOUTS["HubDia"] == "CYLINDRICAL BOSS"
    source = inspect.getsource(drawing)
    assert source.count('"RibWidth": RIB_WIDTH_TEXT_XY') == 1
    assert (
        "offset_dimension_text(adapter, bottom_dimensions, "
        '{"RibWidth": RIB_WIDTH_TEXT_XY})'
    ) in source
    assert "    rib_width_display.ArrowSide = _DIM_ARROWS_INSIDE\n" in source
    assert "keep=HUB_BOTTOM_KEEP," in source


def test_pad_width_on_detail_j_names_the_drawn_faces_and_reads_outside_it() -> None:
    """The 28.0 pad width on DETAIL J, measured against farm run
    20261027T195317391Z's J (sheet m): the pad's faces at y 146.0 and 202.0,
    the rail's inner face at x 334.2, the detail circle centred (300, 174),
    radius 76; the 7.0's leader (300, 212)->(368.65, 234.67) and its last
    row from y 234.2 at x 368.6..411.4; the underside note's top at 99.4.
    Its witnesses leave 1 mm off the inner face and run 1 mm past the line;
    its rows in the native D1 form sheet 5 measured (value from 5.14 mm over
    the offset y, rows from 0.42, 5.98 and 11.53 under, centred), at the
    measured "FULL-HEIGHT" 27.2 and "CENTRED ON BORE" 42.8 mm (the 7.0's
    row), "PAD WIDTH," estimated at 2.85 mm a glyph."""
    import math

    from _layout_geometry import Box, Segment, segment_box_distance

    ink = drawing.INK_CLEARANCE
    s = drawing.HUB_DETAIL_SCALE[0] / drawing.HUB_DETAIL_SCALE[1] / 1000.0
    cx, cy = drawing.HUB_DETAIL_CENTER
    radius = 0.076
    low, high = cy - part.HUB_RIB_W / 2.0 * s, cy + part.HUB_RIB_W / 2.0 * s
    assert (low, high) == pytest.approx((0.14606, 0.20194))
    face = cx + (part.OUTER_X - part.INNER_X) / 2.0 * s
    assert face == pytest.approx(0.3341884)
    lx, ly = drawing.RIB_WIDTH_LINE_XY
    ox, oy = drawing.RIB_WIDTH_TEXT_XY
    assert ly == pytest.approx(cy)
    rows = drawing.HUB_BOTTOM_CALLOUTS["RibWidth"].splitlines()
    assert rows == ["FULL-HEIGHT", "PAD WIDTH,", "CENTRED ON BORE"]
    widths = {
        "28.0": 0.0091, "FULL-HEIGHT": 0.0272, "PAD WIDTH,": 10 * 0.00285,
        "CENTRED ON BORE": 0.0428,
    }
    bases = (oy + 0.00514, oy - 0.00042, oy - 0.00598, oy - 0.01153)
    boxes = {
        row: Box(ox - widths[row] / 2.0, base, ox + widths[row] / 2.0, base + 0.0064)
        for row, base in zip(["28.0", *rows], bases)
    }
    half = max(widths.values()) / 2.0
    stub = Segment(lx, ly, ox - half, bases[-1])
    witnesses = [Segment(face + 0.001, y, lx + 0.001, y) for y in (low, high)]
    line = Segment(lx, low, lx, high)

    def outside_circle(box: Box) -> float:
        """The box's nearest point's distance outside the detail circle."""
        nx = min(max(cx, box.xmin), box.xmax)
        ny = min(max(cy, box.ymin), box.ymax)
        return math.dist((nx, ny), (cx, cy)) - radius

    # Line and witnesses in the window inside the circle, off the rail.
    assert lx - face >= 0.010
    for y in (low, high):
        assert math.dist((lx + 0.001, y), (cx, cy)) <= radius - ink
    # Every row outside the detail circle, inside the border, under the
    # 7.0's leader and two rows clear of its last row, over the note.
    border = drawing.SHEET_FRAME[2]
    seven_leader = Segment(0.300, 0.212, 0.36865, 0.23467)
    for name, box in boxes.items():
        assert outside_circle(box) >= ink, name
        assert border - box.xmax >= ink, name
        assert segment_box_distance(seven_leader, box) >= ink, name
        assert 0.2342 - box.ymax >= 0.010, name
        assert box.ymin - 0.0994 >= 0.050, name
        for other in (line, *witnesses):
            assert segment_box_distance(other, box) >= ink, name
    # The stub climbs from the line's mid across the window, clear of the
    # witness ends and of the 7.0's leader.
    assert stub.y1 > stub.y0
    for witness in witnesses:
        assert _segment_gap(stub, witness) >= ink
    assert _segments_apart(stub, seven_leader)


def test_hanger_section_nests_the_grip_and_depth_right_of_the_profile() -> None:
    """The grip and the depth both stand right of F-F's profile, the depth
    outside: the grip's extension lines no longer run across the underside
    under the reams' mouths (farm run 20261027T143609236Z: x 83.35..149.5
    mm), where datum A's frame leader enters.  The depth's four rows (its
    corner limit, codjiflo round 4) overfill its 12 mm, so they stand beside
    its line on a level stub.  Farm run 20261027T175429300Z: with its line
    34.5 mm right of the gussets the block ran to x 230, into the title
    block (keep-out); the line stands 19.6 mm right of them, just past the
    grip's text.  Every text clears the profile, the other dimension's
    lines and the title block."""
    from _layout_geometry import Box, segment_box_distance

    ink = drawing.INK_CLEARANCE
    edges, lines, texts = _hanger_section_ink()
    right = edges["right end"].x0
    assert "HANGER_GRIP_OFFSET_XY" not in dir(drawing)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    section = source[source.index("def _hanger_section(") : source.index("def _hub_underside_detail(")]
    assert section.count("offset_dimension_text(") == 1
    assert (
        "offset_dimension_text(\n"
        '        adapter, dimensions, {"HangerPinHoleDepth": HANGER_PIN_DEPTH_OFFSET_XY}\n'
        "    )"
    ) in section
    depth_texts = {name: box for name, box in texts.items() if name.startswith("depth")}
    assert len(depth_texts) == 4
    # Nested: grip line, then the depth's line, then its text.
    assert right + ink < texts["grip"].xmin
    assert lines["grip line"].x0 + ink <= lines["depth line"].x0
    for name, box in depth_texts.items():
        assert lines["depth line"].x0 + ink <= box.xmin, name
    for name, box in texts.items():
        for line_name, line in lines.items():
            if name.startswith("depth") and line_name in ("depth jog", "depth underline"):
                continue
            if name == "grip" and line_name.startswith("grip"):
                continue
            assert segment_box_distance(line, box) >= ink, (name, line_name)
        for edge_name, edge in edges.items():
            assert segment_box_distance(edge, box) >= ink, (name, edge_name)
        assert _box_box_gap((box.xmin, box.ymin, box.xmax, box.ymax), TITLE_BLOCK) >= ink, name
    # The stub clears its own floor extension line's end and every other
    # line; no other text sits on it.
    jog = lines["depth jog"]
    assert abs(jog.y1 - jog.y0) < 0.0001
    assert _segment_gap(jog, lines["depth extension floor"]) >= ink
    for line_name in ("grip line", "grip extension top", "depth tail high"):
        assert _segments_apart(jog, lines[line_name]), line_name
    for name in ("grip", "caption"):
        assert segment_box_distance(jog, texts[name]) >= ink, name
    # The upper tail passes right of the 36.50's text.
    assert lines["depth tail high"].x0 - texts["grip"].xmax >= ink
    # The whole dimension (the layout audit's keep-out box: its lines down
    # to the floor witness and its text) ends 4 mm short of the title block,
    # under detail J's boss callout ("CYLINDRICAL BOSS" underline at y 94.42
    # mm from x 188.68 mm).
    block = Box(
        min(box.xmin for box in depth_texts.values()),
        min(box.ymin for box in depth_texts.values()),
        max(box.xmax for box in depth_texts.values()),
        max(box.ymax for box in depth_texts.values()),
    )
    depth_right = max(
        block.xmax,
        *(max(line.x0, line.x1) for name, line in lines.items() if name.startswith("depth")),
    )
    assert TITLE_BLOCK[0] - depth_right >= 0.004
    assert 0.09442 - block.ymax >= 0.004
    # No grip extension line runs under a ream's mouth.
    for name in ("-X ream +X wall", "+X ream +X wall"):
        assert lines["grip extension underside"].x0 > edges[name].x0 + 0.010, name


def test_cut_face_edge_through_keeps_only_a_line_spanning_its_landing() -> None:
    """Farm run 9: datum A's landing is set on the selected cut-face line,
    so ``through`` keeps only a line running past the landing by its margin
    both ways, even when a longer pinned line lies elsewhere."""
    from types import SimpleNamespace

    def line(x0, x1, name):
        start, end = (x0, -5.0, 90.0), (x1, -5.0, 90.0)
        return SimpleNamespace(
            line=(start, end), edge=name, length_mm=abs(x1 - x0),
            midpoint_mm=((x0 + x1) / 2.0, -5.0, 90.0),
        )

    edges = SimpleNamespace(lines=[line(-30.0, -21.0, "gusset"), line(-8.0, 6.0, "middle")])
    pinned = {1: -5.0, 2: 90.0}
    assert drawing._cut_face_edge(edges, fixed=pinned, label="t")[0] == "middle"
    assert drawing._cut_face_edge(
        edges, fixed=pinned, through=(0, -25.0, 1.0), label="t"
    )[0] == "gusset"
    with pytest.raises(RuntimeError, match="through="):
        drawing._cut_face_edge(edges, fixed=pinned, through=(0, -21.5, 1.0), label="t")


def test_faced_underside_is_datum_a_and_every_ream_is_square_to_it() -> None:
    """Owner ruling 2026-10-27 (#2016), option A: the crossbar's dowel reams
    are perpendicular, Ø.0008, to the faced underside the knife mounts seat
    on.  The underside becomes datum A (B, C and D are the reams and the
    crossbar median plane), tagged on its edge in F-F, and one native "4X"
    ⊥ Ø.0008 | A frame covers all four reams, datums B and C included; its
    leader enters the +X ream's mouth from below and lands on its wall.  The
    locator's position frames keep B|C."""
    from _layout_geometry import Box, Segment, segment_box_distance

    assert (
        spec.GEOMETRIC_TOLERANCES_IN["knife-hanger press ream perpendicularity"]
        == ".0008"
    )
    assert spec.HANGER_PRESS_HOLE_PERPENDICULARITY_TOL == pytest.approx(0.02032)
    assert spec.HANGER_PRESS_HOLE_PERPENDICULARITY_TOL < spec.HANGER_PRESS_HOLE_POSITION_TOL
    assert "owner ruling 2026-10-27 (#2016)" in Path(spec.__file__).read_text(encoding="utf-8")
    # A is free among this part's datums.
    assert drawing.HANGER_FLOOR_DATUM == "A"
    assert set(drawing.HANGER_DATUM_SYMBOL_XY) == {"B", "C"}
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'tag.SetLabel("D")' in source
    section = source[source.index("def _hanger_section(") : source.index("def _hub_underside_detail(")]
    assert "datum=HANGER_FLOOR_DATUM," in section
    # Farm run 9 (ae879db86): the hit-test at A's sheet point found no EDGE
    # on F-F.  A and the ⊥ frame both attach by the scanned cut-face line,
    # each landing set on it and proved inside that line's span.
    assert "edge_xy=" not in section
    assert "edge_entity=underside,\n" in section
    assert (
        "leader_attach_xy=_hanger_section_xy(HANGER_FLOOR_DATUM_PICK_X, -HALF_H),"
    ) in section
    assert "edge_entity=ream_wall,\n" in section
    assert "fixed={1: -HALF_H, 2: z},\n        through=(0, HANGER_FLOOR_DATUM_PICK_X, 1.0)," in section
    assert (
        "fixed={0: HANGER_PERP_LANDING[0], 2: z},\n"
        "        through=(1, HANGER_PERP_LANDING[1], 1.0),"
    ) in section
    assert 'characteristic="perpendicularity",' in section
    assert 'tolerance=GEOMETRIC_TOLERANCES_IN["knife-hanger press ream perpendicularity"],' in section
    assert "datums=(HANGER_FLOOR_DATUM,)," in section
    assert "diameter=True," in section
    assert "quantity=HANGER_PERP_FRAME_QUANTITY," in section
    assert drawing.HANGER_PERP_FRAME_QUANTITY == "4X"
    assert "datums=datums," in source and '("front", STUD_Z_FRONT, ("B", "C")),' in source
    ink = drawing.INK_CLEARANCE
    s = drawing._hanger_section_xy
    edges, lines, texts = _hanger_section_ink()
    bottom = edges["underside 0"].y0
    # Datum A: picked on the underside between the gussets' cut end and the
    # -X ream's mouth, outside the crossbar; its leader drops straight to the
    # tag point, the 7 mm box 6.35 mm right of it (B and C's measured form).
    pick = s(drawing.HANGER_FLOOR_DATUM_PICK_X, -part.HALF_H)
    first = edges["underside 0"]
    assert first.x0 + 0.005 < pick[0] < first.x1 - 0.005
    assert drawing.HANGER_FLOOR_DATUM_PICK_X < part.BAR_X0
    tx, ty = drawing.HANGER_FLOOR_DATUM_SYMBOL_XY
    assert tx == pytest.approx(pick[0])
    a_leader = Segment(pick[0], bottom - 0.0025, tx, ty)
    a_shoulder = Segment(tx, ty, tx + 0.00635, ty)
    a_box = Box(tx + 0.00635, ty - 0.0035, tx + 0.01335, ty + 0.0035)
    axis_end = (s(part.PIN_HOLE_NEG_X, 0.0)[0], s(0.0, -part.HALF_H - 2.0)[1])
    assert axis_end[1] - a_box.ymax >= 0.004
    assert a_box.xmin <= axis_end[0] <= a_box.xmax
    # The frame: its leader from its left end's shoulder enters the +X
    # ream's mouth from below and lands 3 mm up its -X wall.
    fx, fy = drawing.HANGER_PERP_FRAME_XY
    x0, y0, x1, y1 = drawing.HANGER_PERP_FRAME_OUTLINE
    frame = Box(fx + x0, fy + y0, fx + x1, fy + y1)
    assert x1 - x0 == pytest.approx(0.0070 + 0.01612 + 0.00663)
    tip = s(*drawing.HANGER_PERP_LANDING)
    wall = edges["+X ream -X wall"]
    assert tip[0] == pytest.approx(wall.x0, abs=1e-5) and wall.y0 < tip[1] < wall.y1
    assert drawing.HANGER_PERP_LANDING[0] == part.PIN_HOLE_X - spec.HANGER_PIN_HOLE_DIA / 2.0
    mid = fy + (y0 + y1) / 2.0
    knee = (frame.xmin - 0.00635, mid)
    assert drawing.hanger_ream_frame_knee(drawing.HANGER_PERP_FRAME_XY, tip) == pytest.approx(knee)
    leader = Segment(*knee, *tip)
    shoulder = Segment(*knee, frame.xmin, mid)
    count = Box(frame.xmin, frame.ymin - 0.00556, frame.xmin + 0.0055, frame.ymin - 0.00206)
    # Through the mouth: where it meets the underside it is inside the mouth
    # with air to both walls, it meets the +X wall below the underside, and
    # its only model crossing is its landing.
    at_bottom = knee[0] + (tip[0] - knee[0]) * (bottom - knee[1]) / (tip[1] - knee[1])
    mouth = (edges["+X ream -X wall"].x0, edges["+X ream +X wall"].x0)
    assert mouth[0] + 0.0015 < at_bottom < mouth[1] - 0.001
    for name, edge in edges.items():
        if name == "+X ream -X wall":
            continue
        assert _segments_apart(leader, edge), name
    # 2.0 mm off the depth's extension line, which starts 1 mm off the wall.
    assert _segment_gap(leader, lines["depth extension underside"]) >= 0.0019
    for name, line in lines.items():
        assert _segments_apart(leader, line), name
        for piece_name, piece in (("shoulder", shoulder), ("A leader", a_leader), ("A shoulder", a_shoulder)):
            assert _segment_gap(piece, line) >= ink, (piece_name, name)
        for box_name, box in (("frame", frame), ("4X", count), ("A box", a_box)):
            assert segment_box_distance(line, box) >= ink, (box_name, name)
    for name, box in texts.items():
        for piece_name, piece in (("leader", leader), ("shoulder", shoulder), ("A leader", a_leader)):
            assert segment_box_distance(piece, box) >= ink, (piece_name, name)
        for other_name, other in (("frame", frame), ("4X", count), ("A box", a_box)):
            assert _box_box_gap(
                (box.xmin, box.ymin, box.xmax, box.ymax), (other.xmin, other.ymin, other.xmax, other.ymax)
            ) >= 0.003, (other_name, name)
    # Frame, count and tag stand under the profile, apart from each other
    # and the other's leader, on the sheet, off the title block.
    for box_name, box in (("frame", frame), ("4X", count), ("A box", a_box)):
        assert box.ymax <= bottom - 0.006, box_name
        assert segment_box_distance(leader, box) >= (0.0 if box_name == "frame" else ink), box_name
        assert segment_box_distance(a_leader, box) >= ink, box_name
        assert _box_box_gap((box.xmin, box.ymin, box.xmax, box.ymax), TITLE_BLOCK) >= ink, box_name
    assert _box_box_gap(
        (frame.xmin, frame.ymin, frame.xmax, frame.ymax), (a_box.xmin, a_box.ymin, a_box.xmax, a_box.ymax)
    ) >= 0.020
    assert _segment_gap(leader, a_leader) >= 0.020



def test_plus_x_station_is_xxx_and_minus_x_ream_basic_from_it() -> None:
    # Each +X ream (datum B or C) is an ordinary .XXX 7.632 from its own
    # screw axis.  The -X ream is BASIC 15.264 from it (machinist review,
    # farm run 4: the position frame's feature had no BASIC), held by the
    # Ø0.05 frame on the plan; the knife mount fitted either way round puts
    # the round-hole pin on it, which the stacks charge as the +X band plus
    # the zone's radius.  No note restates either.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    section = source[source.index("def _hanger_section(") : source.index("def _hub_underside_detail(")]
    assert "p0=(HANGER_X, -HALF_H-2.0, z), p1=(PIN_HOLE_X, -HALF_H-2.0, z)" in section
    assert "p0=(PIN_HOLE_NEG_X, -HALF_H-2.0, z), p1=(PIN_HOLE_X, -HALF_H-2.0, z)" in section
    assert "entities=(axes[0], axes[1])" in section
    assert "entities=(axes[2], axes[1])" in section
    assert "entities=(axes[0], axes[2])" not in section
    assert section.count("suffix=PIN_STATION_CALLOUT,") == 1
    assert section.count("set_basic_dimension(") == 1
    assert "SetText(1, " not in section
    assert 'location="above"' not in section
    # The 7.632 names the reams it locates, their transverse station (the
    # screw axis's own Z) and, as a three-place size, the mate it matches:
    # MHA-SM-02's dowel holes at the same dowel-spec offset (machinist
    # review r4).
    assert drawing.PIN_STATION_CALLOUT.splitlines() == [
        "2X REAM FROM",
        "SCREW AXIS, SAME Z;",
        "MATCHES MHA-SM-02",
    ]
    import sm_knife_mount_spec as knife_mount

    assert spec.HANGER_PIN_X == knife_mount.PIN_HOLE_X


def test_boss_and_socket_diameters_take_one_near_side_arrow() -> None:
    # Machinist review r3 (sheet 3): as full diameters through the shared
    # axis the socket's match-fit leader crossed the Ø45.0 BOSS leader at
    # the socket centre, and the Ø45.0 grazed the 28.0's upper arrow.  Each
    # now reads off one arrow on its nearest rim; the boss text stands 4 mm
    # higher, still under the socket block.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert set(drawing.DETAIL_TOP_KEEP) == {"C0Dia", "B0Dia"}
    assert 'set_near_side_diameter(annotation, f"holes/sockets top {name}")' in source
    styled = source.index('set_near_side_diameter(annotation, f"holes/sockets top {name}")')
    assert source.index("for name in DETAIL_TOP_KEEP:", styled - 400) < styled
    assert drawing.DETAIL_TOP_KEEP["C0Dia"] == (0.035, 0.236)
    assert drawing.DETAIL_TOP_KEEP["B0Dia"][1] - drawing.DETAIL_TOP_KEEP["C0Dia"][1] >= 0.019


def test_cap_recess_bands_preserve_the_counterbore_ligament() -> None:
    assert part.CAP_RECESS_DIAMETER_BAND == pytest.approx((0.2032, 0.0))
    assert part.CAP_RECESS_DEPTH_BAND == pytest.approx((0.3048, 0.0))
    assert part.COUNTERBORE_PRINTED_CAP_LIGAMENT == pytest.approx(2.8031348397820595)


def test_ream_size_parks_above_the_plan_right_of_the_rear_frame() -> None:
    # The rear +X ream's size, its stacked +0.000/-0.010 band and its one
    # callout row print face-on in the underside locator.  Farm run
    # 20261027T030041319Z measured the block (the row 112.5 mm, 15.1 mm in
    # all); the leader lands on the underline's end facing the ream.  The
    # block parks over the plan, inside the sheet frame, right of the rear
    # frame and short of detail J; it and its leader keep ink clear of every
    # locator line, box and circle and of both frames, and the leader,
    # leaving the rim above F-F's cutting line and opposite datum C's
    # leader, crosses neither.
    from _layout_geometry import Box, Segment, segment_box_distance, segment_circle_distance

    assert len(spec.HANGER_PIN_HOLE_CALLOUT.splitlines()) == 1
    half_w = drawing.HANGER_PIN_DIA_TEXT_WIDTH / 2.0
    half_h = drawing.HANGER_PIN_DIA_TEXT_HALF_HEIGHT
    assert 2.0 * half_w == pytest.approx(0.1125, abs=0.0005)
    # The stacked band (two half rows) and one callout row.
    assert 2.0 * half_h >= 0.0151
    x, y = drawing.HANGER_PIN_DIA_TEXT_XY
    block = Box(x - half_w, y - half_h, x + half_w, y + half_h)
    ink = drawing.INK_CLEARANCE
    assert (block.xmin, block.ymin) == pytest.approx((0.120, 0.2472))
    # The layout audit read detail J's view from x 255.95, y 249.34 mm, and
    # the old block's row (to x 258.1) over it.
    assert block.xmax <= 0.25595 - 0.010
    centre, m_per_mm = drawing.HUB_BOTTOM_CENTER, drawing._HUB_BOTTOM_M_PER_MM
    sheet = drawing.SHEET_FRAME
    assert sheet[0] + ink <= block.xmin and block.xmax <= sheet[2] - ink
    assert block.ymax <= sheet[3] - ink and block.ymin > TITLE_BLOCK[3]
    assert block.ymin >= centre[1] + drawing.PLAN_HALF_Z * m_per_mm + ink

    def block_gap(point):
        near = (min(max(point[0], block.xmin), block.xmax), min(max(point[1], block.ymin), block.ymax))
        return math.dist(near, point)

    # Detail J's unchanged 76 mm fence.
    assert block_gap(drawing.HUB_DETAIL_CENTER) - 0.076 >= ink
    circles = _locator_circles()
    hole_x, hole_y, hole_r = circles.pop("+X ream C")
    for station, station_z in (("front", part.STUD_Z_FRONT), ("rear", part.STUD_Z_REAR)):
        circles[f"{station} -X ream"] = (
            centre[0] + part.PIN_HOLE_NEG_X * m_per_mm,
            centre[1] + station_z * m_per_mm,
            hole_r,
        )
    foot = (block.xmin, block.ymin)
    reach = math.dist(foot, (hole_x, hole_y))
    rim = (hole_x + hole_r * (foot[0] - hole_x) / reach, hole_y + hole_r * (foot[1] - hole_y) / reach)
    leader = Segment(*rim, *foot)
    assert block_gap((hole_x, hole_y)) - hole_r >= ink
    for name, circle in circles.items():
        assert block_gap(circle[:2]) - circle[2] >= ink, name
        assert segment_circle_distance(leader, circle) >= ink, name
    lines, boxes, _picks, _cut_y = _underside_locator_ink()
    for station, (outline, _ream, _landing, runs) in _ream_frame_layout().items():
        boxes[f"{station} frame"] = outline
        for index, run in enumerate(runs):
            lines[f"{station} frame leader {index}"] = run
    for name, box in boxes.items():
        assert _box_box_gap(
            (block.xmin, block.ymin, block.xmax, block.ymax),
            (box.xmin, box.ymin, box.xmax, box.ymax),
        ) >= ink, name
        assert segment_box_distance(leader, box) >= ink, name
    for name, line in lines.items():
        assert segment_box_distance(line, block) >= ink, name
        if name in ("F-F cutting line", "datum C leader"):
            # Both run from the rear +X ream: the leader crosses neither.
            assert _segments_apart(leader, line), name
        else:
            assert _segment_gap(leader, line) >= ink, name


def test_build_places_the_hanger_section_on_the_underside_sheet() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    underside = source[source.index('ddoc.ActivateSheet("UNDERSIDE")') :]
    assert "_hanger_section(adapter, hub_bottom_parent)" in underside
    assert "imported_annotations += hanger_dimensions" in underside


def test_datum_c_and_the_ream_size_meet_the_rear_ream_apart() -> None:
    # Machinist review of 3de09b959 (sheet 6, #2045) and farm run
    # 20261027T030041319Z: with datum C's tag above the plan, the size's open
    # arrowhead ended inside datum C's filled triangle on the ~1.1 mm rear
    # circle.  The triangle's 2.9 mm base overhangs the rim on both sides, so
    # the two must leave the rim at least a right angle apart: datum C drops
    # to the lower rim, under F-F's cutting line, into the window clear of
    # F-F's right arrow and letter; the size leaves the upper.
    from _layout_geometry import segment_box_distance

    ink = drawing.INK_CLEARANCE
    lines, boxes, picks, cut_y = _underside_locator_ink()
    hole_x, hole_y, _hole_r = _locator_circles()["+X ream C"]
    x, y = drawing.HANGER_PIN_DIA_TEXT_XY
    foot = (x - drawing.HANGER_PIN_DIA_TEXT_WIDTH / 2.0, y - drawing.HANGER_PIN_DIA_TEXT_HALF_HEIGHT)
    datum = (picks["C"][0] - hole_x, picks["C"][1] - hole_y)
    size = (foot[0] - hole_x, foot[1] - hole_y)
    assert datum[0] * size[0] + datum[1] * size[1] <= 0.0
    assert picks["C"][1] < cut_y < foot[1]
    leader, tag = lines["datum C leader"], boxes["datum C tag"]
    arrow, letter = lines["F-F right arrow"], boxes["F-F right letter"]
    assert _segment_gap(leader, arrow) >= ink
    assert segment_box_distance(arrow, tag) >= ink
    assert segment_box_distance(leader, letter) >= ink
    assert _box_box_gap(
        (tag.xmin, tag.ymin, tag.xmax, tag.ymax),
        (letter.xmin, letter.ymin, letter.xmax, letter.ymax),
    ) >= ink


def test_hanger_callout_states_drill_thru_on_the_native_rows(monkeypatch) -> None:
    """The plain wizard's native callout keeps its variable-driven diameter
    and states DRILL THRU in place of its one extent token (user ruling
    2026-10-14); no spotface row, method note or depth survives."""
    import ast

    # The installed R2026x calloutformat.txt, [ANSI INCH] line 93:
    # HOLE-THRU=;<MOD-DIAM> <hw-diam> <hw-thru>
    native = "<MOD-DIAM> <hw-diam> <hw-thru>"
    assert drawing._hanger_hole_callout_definitions({5: native, 6: "", 7: "", 8: ""}) == {
        5: "<MOD-DIAM> <hw-diam> DRILL THRU", 6: "", 7: "", 8: "",
    }
    counterbore = (
        "<MOD-DIAM> <hw-thruholedia> <hw-thru>\n"
        "<HOLE-SPOT><MOD-DIAM> <hw-cbdia> <HOLE-DEPTH> <hw-cbdepth>"
    )
    for stale in (
        # The old spotface (COUNTERBORE-THRU) and its through row alone.
        {5: counterbore, 6: "", 7: "", 8: ""},
        {5: "<MOD-DIAM> <hw-thruholedia> <hw-thru>", 6: "", 7: "", 8: ""},
        # A plain hole with a farside countersink row.
        {5: native + "\n<HOLE-SINK><MOD-DIAM> <hw-fscsdia> X <hw-fscsang>", 6: "", 7: "", 8: ""},
        {5: "<MOD-DIAM> <hw-diam>", 6: "", 7: "", 8: ""},
        {5: native, 6: native, 7: "", 8: ""},
        {5: native, 6: "", 7: ""},
    ):
        with pytest.raises(RuntimeError, match="unexpected native hanger hole callout"):
            drawing._hanger_hole_callout_definitions(stale)

    resolved_tokens = {
        "<MOD-DIAM>": "\u00d8", "<hw-diam>": "6.045", "<hw-thru>": "THRU ALL",
    }

    class Display:
        def __init__(self, *, persist=True):
            self.definitions = {5: native, 6: "", 7: "", 8: ""}
            self.persist = persist

        def GetText(self, part):
            if part >= 5:
                return self.definitions[part]
            text = self.definitions[part + 4]
            for token, value in resolved_tokens.items():
                text = text.replace(token, value)
            return text

        def SetText(self, part, text):
            if self.persist:
                self.definitions[part + 4] = text

    calls = []
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(
        drawing, "set_hole_callout_precision",
        lambda _display, precision, *, label: calls.append(("places", precision)),
    )
    monkeypatch.setattr(
        drawing, "_tolerance_hanger_callout_clearance", lambda _display: calls.append("band"),
    )
    display = Display()
    drawing._set_hanger_hole_callout(display)
    assert display.GetText(1) == "\u00d8 6.045 DRILL THRU"
    assert calls == [
        ("places", {"hw-diam": spec.HANGER_CLEARANCE_DIA_PLACES}), "band",
    ]
    with pytest.raises(RuntimeError, match="did not persist"):
        drawing._set_hanger_hole_callout(Display(persist=False))
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "DRILL FROM UNDERSIDE" not in source and "TOP SPOTFACE" not in source
    assert not hasattr(drawing, "HANGER_DRILL_CALLOUT")
    assert "_set_hanger_hole_callout(hanger_callout)" in source
    tree = ast.parse(source)
    (callout,) = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "add_native_hole_callout"
        and any(
            keyword.arg == "label"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "2X #10 loose hanger clearance holes"
            for keyword in node.keywords
        )
    ]
    keywords = {k.arg: k.value for k in callout.keywords}
    assert "process" not in keywords
    assert isinstance(keywords["callout_xy"], ast.Name)
    assert keywords["callout_xy"].id == "HANGER_CALLOUT_XY"


def test_keeper_transfer_prefix_preserves_the_native_hole_definition() -> None:
    import ast

    import _drawing_hole_callout

    native = "<hw-threaddesc>\n<hw-threaddepth>\n<hw-tapdrldia> <hw-tapdrldepth>"
    assert (
        _drawing_hole_callout.compose_hole_callout_prefix(
            drawing.TRANSFER_KEEPER_CALLOUT,
            native,
        )
        == "TRANSFER FROM MHA-CH-07\nAT ASSEMBLY;\n" + native
    )
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    callouts = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "add_native_hole_callout"
        and any(
            keyword.arg == "label"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "2X fulcrum-keeper blind taps"
            for keyword in node.keywords
        )
    ]
    assert len(callouts) == 1
    process = next(
        keyword.value for keyword in callouts[0].keywords if keyword.arg == "process"
    )
    assert isinstance(process, ast.Name) and process.id == "TRANSFER_KEEPER_CALLOUT"
    helper_tree = ast.parse(Path(_drawing_hole_callout.__file__).read_text(encoding="utf-8"))
    helper = next(
        node
        for node in helper_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "add_native_hole_callout"
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "compose_hole_callout_prefix"
        for node in ast.walk(helper)
    )
    precision_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "set_hole_callout_precision"
        and node.args
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "keeper_callout"
    ]
    assert len(precision_calls) == 1
    precision = precision_calls[0].args[1]
    assert isinstance(precision, ast.Name)
    assert precision.id == "KEEPER_TAP_CALLOUT_PRECISION"


def test_keeper_locations_are_reference_but_hanger_locations_remain_manufacturing() -> (
    None
):
    import ast

    source = Path(drawing.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    loops = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.For)
        and isinstance(node.target, ast.Tuple)
        and [item.id for item in node.target.elts if isinstance(item, ast.Name)]
        == ["p0", "p1", "expected", "xy", "orientation", "label", "suffix", "reference"]
    ]
    assert len(loops) == 1
    captured = []
    environment = dict(vars(drawing))
    environment.update(
        adapter=None,
        detail_top=None,
        upper_left_rim=(
            -part.COLUMN_X,
            part.HALF_H + part.BOSS_ABOVE,
            part.FRONT_COLUMN_Z + part.BORE_DIA / 2,
        ),
        upper_right_rim=(
            part.COLUMN_X,
            part.HALF_H + part.BOSS_ABOVE,
            part.FRONT_COLUMN_Z + part.BORE_DIA / 2,
        ),
        hanger_x=(part.BAR_X0 + part.BAR_X1) / 2,
        keeper_drill_r=part.TAP_DRILL_MM[part.KEEPER_TAP_SPEC.size] / 2,
        _checked_dimension=lambda *_args, **kwargs: captured.append(kwargs),
    )
    exec(
        compile(ast.Module(body=loops, type_ignores=[]), "<station-contract>", "exec"),
        environment,
    )
    # Hanger X is D's own station (test_hanger_x_locates_datum_d_not_a_hole).
    assert len(captured) == 5
    assert "hanger x from left sockets" not in {entry["label"] for entry in captured}
    by_label = {entry["label"]: entry for entry in captured}
    for label in (
        "keeper x from left sockets",
        "front keeper z from upper sockets",
        "rear keeper z from upper sockets",
    ):
        assert by_label[label]["reference"] is True
        assert by_label[label]["center"] is True
        assert label in spec.DRAWING_REFERENCE_PRECISION
    hanger_expectations = (
        (
            "front hanger z from upper sockets",
            "FRONT HANGER Z",
            (0.062, 0.209),
            part.STUD_Z_FRONT - part.FRONT_COLUMN_Z,
        ),
        (
            "rear hanger z from upper sockets",
            "REAR\nHANGER Z",
            drawing.REAR_HANGER_Z_TEXT_XY,
            part.STUD_Z_REAR - part.FRONT_COLUMN_Z,
        ),
    )
    for label, suffix, position, expected in hanger_expectations:
        entry = by_label[label]
        assert entry["reference"] is False
        assert entry["suffix"] == suffix
        assert entry["text_xy"] == position
        assert entry["expected_mm"] == pytest.approx(expected)
    # The existing helper applies parentheses, excluding the nominal from
    # general location inspection rather than typing a separate nominal note.
    helper = source[
        source.index("def _checked_dimension(") : source.index(
            "def _orient_cut_section("
        )
    ]
    assert (
        "if reference:\n        set_reference_dimension(adapter, annotation, label=label)"
        in helper
    )
    assert "_set_derived_precision(native, label=label)" in helper


def test_transfer_rows_rederive_the_keeper_envelope_and_plan_clearance() -> None:
    old_left, old_down, old_right, old_up = drawing._KEEPER_NATIVE_CALLOUT_EXTENT
    left, down, right, up = drawing.KEEPER_CALLOUT_EXTENT
    extra = (
        drawing.TRANSFER_KEEPER_CALLOUT.count("\n") * drawing.KEEPER_TRANSFER_ROW_PITCH
    )
    assert extra > 0.0
    assert (left, down) == (old_left, old_down)
    assert right == pytest.approx(old_right + drawing.KEEPER_TRANSFER_EXTRA_WIDTH)
    assert up == pytest.approx(old_up + extra)
    hole, hole_r, boss, boss_r = _keeper_geometry()
    angle = drawing._keeper_leader_angle(hole, boss, boss_r)
    assert drawing.KEEPER_TRANSFER_PLAN_SHIFT == pytest.approx(
        extra / math.tan(angle) + drawing.KEEPER_TRANSFER_EXTRA_WIDTH
    )
    callout, tip = drawing.keeper_callout_placement(hole, hole_r, boss, boss_r)
    box = (callout[0] - left, callout[1] - down, callout[0] + right, callout[1] + up)
    assert box[2] <= drawing.SHEET_FRAME[2] - drawing.INK_CLEARANCE
    assert box[1] > TITLE_BLOCK[3]
    assert hole[1] - box[3] >= drawing.INK_CLEARANCE + drawing.ARROW_HALF_WIDTH
    assert box[0] > boss[0] + boss_r
    # Shifting the plan cancels the extra height's horizontal advance along
    # the tangent, retaining the historical right-frame allowance.
    old_hole = (hole[0] + drawing.KEEPER_TRANSFER_PLAN_SHIFT, hole[1])
    old_shoulder_y = old_hole[1] - (
        drawing.INK_CLEARANCE
        + drawing.ARROW_HALF_WIDTH
        + drawing.ROUND_OUT
        + old_up
        + old_down
    )
    old_shoulder_x = old_hole[0] + (old_hole[1] - old_shoulder_y) / math.tan(angle)
    assert box[2] == pytest.approx(old_shoulder_x + old_left + old_right)
    assert math.dist(tip, hole) == pytest.approx(hole_r)


def _hole_sheet_stations():
    """HOLES-SOCKETS' six station dimensions, evaluated from the build's loop."""
    import ast

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    loop = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.For)
        and isinstance(node.target, ast.Tuple)
        and any(
            isinstance(item, ast.Name) and item.id == "reference"
            for item in node.target.elts
        )
    )
    environment = dict(vars(drawing))
    environment.update(
        upper_left_rim=(
            -part.COLUMN_X,
            part.HALF_H + part.BOSS_ABOVE,
            part.FRONT_COLUMN_Z + part.BORE_DIA / 2,
        ),
        upper_right_rim=(
            part.COLUMN_X,
            part.HALF_H + part.BOSS_ABOVE,
            part.FRONT_COLUMN_Z + part.BORE_DIA / 2,
        ),
        hanger_x=(part.BAR_X0 + part.BAR_X1) / 2,
        keeper_drill_r=part.TAP_DRILL_MM[part.KEEPER_TAP_SPEC.size] / 2,
    )
    return eval(
        compile(ast.Expression(loop.iter), "<station-fields>", "eval"), environment
    )


def _keeper_callout_placed():
    """RD4's (callout point, sheet box) as the build places it."""
    hole, hole_r, boss, boss_r = _keeper_geometry()
    callout, _tip = drawing.keeper_callout_placement(hole, hole_r, boss, boss_r)
    left, down, right, up = drawing.KEEPER_CALLOUT_EXTENT
    return callout, (
        callout[0] - left,
        callout[1] - down,
        callout[0] + right,
        callout[1] + up,
    )


def test_transfer_plan_and_station_fields_remain_inside_the_hole_sheet() -> None:
    left, bottom = _plan(-drawing.PLAN_HALF_X, drawing.PLAN_HALF_Z)
    right, top = _plan(drawing.PLAN_HALF_X, -drawing.PLAN_HALF_Z)
    frame = drawing.SHEET_FRAME
    assert (
        frame[0] + drawing.INK_CLEARANCE
        < left
        < right
        < frame[2] - drawing.INK_CLEARANCE
    )
    assert (
        TITLE_BLOCK[3] + drawing.INK_CLEARANCE
        < bottom
        < top
        < frame[3] - drawing.INK_CLEARANCE
    )
    stations = _hole_sheet_stations()
    # Hanger X is D's own station, outside the loop.
    assert len(stations) == 5
    _callout, callout_box = _keeper_callout_placed()
    left, _down, right, _up = drawing.KEEPER_CALLOUT_EXTENT
    # Estimated field allowances, not measured render ink: 2 mm per qualifier
    # character and the historical 10.2 mm value/qualifier height. Farm ink
    # validation remains authoritative for actual font metrics and witnesses.
    for p0, p1, _expected, (x, y), _orientation, label, suffix, _reference in stations:
        for point in (p0, p1):
            px, py = _plan(point[0], point[2])
            assert frame[0] < px < frame[2] and frame[1] < py < frame[3], label
        half_width = len(suffix) * 0.002 / 2
        field = (x - half_width, y - 0.0051, x + half_width, y + 0.0051)
        assert frame[0] < field[0] < field[2] < frame[2], label
        assert frame[1] < field[1] < field[3] < frame[3], label
        assert _box_box_gap(field, TITLE_BLOCK) >= drawing.INK_CLEARANCE, label
        assert _box_box_gap(field, callout_box) >= drawing.INK_CLEARANCE, label
    # The expanded width covers a conservative full-em prefix allowance.
    # It is a derived envelope, not a new observed native measurement.
    assert (
        max(map(len, drawing.TRANSFER_KEEPER_CALLOUT.splitlines()))
        * drawing.KEEPER_TRANSFER_CHARACTER_WIDTH
        <= left + right + 1e-12
    )


def test_socket_pitch_parks_outside_the_plan_between_the_hanger_lanes() -> None:
    # Machinist review of 11783475: centred on its line at x 83 mm, 224.00
    # MATCHES MHA-FR-01 ran across the left rail and the extension lines.
    # Text as the 40d9d030e render's glyphs measure it: 28.0 FRONT HANGER Z
    # printed [42.9, 204.4]..[81.3, 213.5] mm about (62, 209); three rows
    # stand 14.7 mm tall, MHA-FR-01 25.6 wide and HANGER Z 22.4; an offset
    # value's underline runs 1.0 under its block and 0.1 past each side.
    from _layout_geometry import Box, Segment, segment_box_distance, segment_box_overlap_length

    ink = drawing.INK_CLEARANCE
    stations = {label: xy for _p0, _p1, _e, xy, _o, label, _s, _r in _hole_sheet_stations()}
    front_xy = stations["front hanger z from upper sockets"]
    rear_xy = stations["rear hanger z from upper sockets"]
    assert rear_xy == drawing.REAR_HANGER_Z_TEXT_XY
    front_text = Box(front_xy[0] - 0.0192, front_xy[1] - 0.00455, front_xy[0] + 0.0192, front_xy[1] + 0.00455)
    rear_text = Box(rear_xy[0] - 0.01122, rear_xy[1] - 0.00735, rear_xy[0] + 0.01122, rear_xy[1] + 0.00735)
    line_x, mid_y = drawing.SOCKET_VERTICAL_PITCH_LINE_XY
    upper = _plan(0.0, part.FRONT_COLUMN_Z)[1]
    lower = _plan(0.0, part.REAR_COLUMN_Z)[1]
    assert mid_y == pytest.approx((upper + lower) / 2.0)
    tx, ty = drawing.SOCKET_VERTICAL_PITCH_TEXT_XY
    text = Box(tx - 0.0128, ty - 0.00735, tx + 0.0128, ty + 0.00735)
    leader = Segment(line_x, mid_y, text.xmin - 0.0001, text.ymin - 0.001)
    hanger_x = _plan((part.BAR_X0 + part.BAR_X1) / 2, 0.0)[0]
    socket_x = _plan(-part.COLUMN_X, 0.0)[0]
    front_y = _plan(0.0, part.STUD_Z_FRONT)[1]
    rear_y = _plan(0.0, part.STUD_Z_REAR)[1]
    # Lanes outside in: 202.1, the pitch, 28.0, each line clear of the next
    # lane's text; 28.0's extension line stops short of the pitch line.
    assert drawing.SHEET_FRAME[0] + ink <= rear_text.xmin
    assert rear_text.xmax + ink <= line_x <= front_text.xmin - ink
    assert front_xy[0] - 0.001 > line_x
    # The parked value and qualifier stand outside the plan, clear of every
    # line and text round them; the leader runs clear of the hanger texts.
    assert text.xmax + ink <= _plan(-drawing.PLAN_HALF_X, 0.0)[0]
    for name, segment in {
        "pitch line": Segment(line_x, lower, line_x, upper),
        "pitch upper extension": Segment(line_x - 0.001, upper, socket_x, upper),
        "pitch lower extension": Segment(line_x - 0.001, lower, socket_x, lower),
        "28.0 line": Segment(front_xy[0], front_y, front_xy[0], upper),
        "28.0 extension": Segment(front_xy[0] - 0.001, front_y, hanger_x, front_y),
        "202.1 line": Segment(rear_xy[0], rear_y, rear_xy[0], upper),
        "202.1 extension": Segment(rear_xy[0] - 0.001, rear_y, hanger_x, rear_y),
    }.items():
        assert segment_box_distance(segment, text) >= ink, name
    for name, box in {"28.0": front_text, "202.1": rear_text}.items():
        assert _box_box_gap(
            (text.xmin, text.ymin, text.xmax, text.ymax), (box.xmin, box.ymin, box.xmax, box.ymax)
        ) >= ink, name
        assert segment_box_distance(leader, box) >= ink, name
    assert segment_box_overlap_length(leader, text) == 0.0


def test_front_keeper_z_text_stands_between_its_extension_lines() -> None:
    # Machinist review of 11783475: at y 205 mm the keeper's extension line
    # ran through (29.2) FRONT KEEPER Z, 34.8 x 9.2 mm as the 40d9d030e
    # render printed it.
    ink = drawing.INK_CLEARANCE
    stations = {label: xy for _p0, _p1, _e, xy, _o, label, _s, _r in _hole_sheet_stations()}
    x, y = stations["front keeper z from upper sockets"]
    assert (x, y) == drawing.FRONT_KEEPER_Z_TEXT_XY
    text = (x - 0.0174, y - 0.0046, x + 0.0174, y + 0.0046)
    assert _plan(0.0, part.FRONT_COLUMN_Z)[1] - text[3] >= ink
    assert text[1] - _plan(0.0, part.KEEPER_TAP_Z_FRONT)[1] >= ink
    assert text[0] - _plan(drawing.PLAN_HALF_X, 0.0)[0] >= ink
    assert stations["rear keeper z from upper sockets"][0] - text[2] >= ink
    _callout, callout_box = _keeper_callout_placed()
    assert _box_box_gap(text, callout_box) >= ink


def test_crossbar_pocket_depth_stands_between_the_side_rail_and_the_t() -> None:
    # The underside's 138.0 names the pockets and the section through them;
    # E-E prints their depth, flange underside to the T's underside, arrows
    # inside.  Its two rows print 24.4 x 9.2 mm (2X POCKET by the 40d9d030e
    # render's glyphs), the underline 1.0 under the block and 0.1 past each
    # side; extension lines overshoot their line 1.03 mm (the 8.0's there).
    from _layout_geometry import Box, Segment, segment_box_distance, segment_box_overlap_length

    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'suffix="2X POCKET", offset_text=CROSSBAR_POCKET_DEPTH_TEXT_XY' in source
    # Machinist review r1: the 138.0 no longer claims a mid-air "CENTRED ON
    # T"; its front end is located from the front-left socket axis.
    assert 'suffix="2X POCKET, E-E", offset_text=POCKET_LENGTH_OFFSET_XY' in source
    assert '\\nCENTRED ON T"' not in source
    assert 'label="crossbar pocket from front socket"' in source
    assert drawing.BAR_POCKET_FROM_SOCKET == pytest.approx(
        abs(part.FRONT_COLUMN_Z) - part.BAR_POCKET_Z
    )
    # Machinist review r3/r4: the 43.0 drew 24 mm left of its text point, off
    # the sheet frame, after a rebuild later than its placement readback; a
    # settled check reads its line back onto the 138.0's x after the
    # finalizer's settling rebuild and proves it inside the zone frame.
    assert (
        "_pin_vertical_dimension_line(\n"
        "            adapter, pocket_from_socket, POCKET_FROM_SOCKET_LINE_XY[0],"
    ) in source
    assert source.count("_pin_vertical_dimension_line(") == 2  # def + the one call
    assert "settled_checks=(_pocket_from_socket_settled,)," in source
    assert drawing.POCKET_FROM_SOCKET_LINE_XY[0] == drawing.POCKET_LENGTH_TEXT_XY[0]
    assert drawing.SHEET_FRAME[0] < drawing.POCKET_FROM_SOCKET_LINE_XY[0]
    assert 'label="crossbar pocket depth"' in source
    assert "pocket_depth.ArrowSide = _DIM_ARROWS_INSIDE" in source
    assert "crossbar pocket depth" in spec.DRAWING_REFERENCE_PRECISION
    ink = drawing.INK_CLEARANCE
    xy = drawing._side_section_xy
    line_x = drawing.CROSSBAR_POCKET_DEPTH_LINE_XY[0]
    top_y = xy(0.0, part.FLANGE_BOT_Y)[1]
    bottom_y = xy(0.0, -part.HALF_H)[1]
    t_left = xy(part.BAR_X0, 0.0)[0]
    assert t_left - line_x >= ink
    tx, ty = drawing.CROSSBAR_POCKET_DEPTH_TEXT_XY
    text = Box(tx - 0.01225, ty - 0.0046, tx + 0.01225, ty + 0.0046)
    leader = Segment(line_x, (top_y + bottom_y) / 2.0, text.xmax + 0.0001, text.ymin - 0.001)
    extensions = {
        "upper extension": Segment(line_x - 0.00103, top_y, t_left, top_y),
        "lower extension": Segment(line_x - 0.00103, bottom_y, xy(part.HANGER_X, 0.0)[0], bottom_y),
    }
    # The 13.0 crossbar web's left arrow tail, 6.35 mm out from its extension line.
    web_x0 = xy(part.BAR_WEB_X0, 0.0)[0]
    web_y = drawing.CROSSBAR_WEB_LINE_XY[1]
    extensions["13.0 left tail"] = Segment(web_x0 - 0.00635, web_y, web_x0, web_y)
    for name, segment in extensions.items():
        assert _segment_gap(leader, segment) >= ink, name
        assert segment_box_distance(segment, text) >= ink, name
    assert segment_box_overlap_length(leader, text) == 0.0
    # Between the side rail's inner face and the T, under the side web's line
    # (printed 5.56 mm under its text point) and over E-E's caption.
    assert text.xmin - xy(-part.INNER_X, 0.0)[0] >= ink
    assert drawing.SIDE_WEB_TEXT_XY[1] - 0.00556 - text.ymax >= ink
    assert leader.y1 - drawing.SIDE_SECTION_CAPTION_XY[1] >= ink


# --- The faced keeper-rail top (user ruling 2026-10-11) ---------------------


def test_keeper_facing_note_is_the_part_property_and_the_seats_carry_no_frame() -> None:
    import ast

    # Rule 5 names flatness on a clamp face over-specification and no user
    # ruling accepts a keeper-seat frame (codex review of 06d0bbc59): the
    # faced top carries the seats, with no flatness value of its own.
    assert set(spec.GEOMETRIC_TOLERANCES_MM) == {
        "knife-hanger press ream position",
        "knife-hanger crossbar centring",
        "knife-hanger press ream perpendicularity",
    }
    assert "fr_top_frame_spec" not in Path(keeper.__file__).read_text(encoding="utf-8")
    # One facing requirement on the whole top except the four corner bosses
    # (user ruling 2026-10-14).  No region size, no edge margin, no setup
    # method, no new dimension (machinist review r13).
    assert spec.DRAWING_NOTES_B.splitlines() == [
        "WHOLE TOP EXCEPT 4 BOSSES:",
        "Ra 125 µIN.",
    ]
    for name in ("KEEPER_FLATNESS_NOTE", "KEEPER_FLATNESS_QUALIFIER", "KEEPER_FLATNESS_FRAME_XY"):
        assert not hasattr(drawing, name), name
    tree = ast.parse(Path(spec.__file__).read_text(encoding="utf-8"))
    (notes,) = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and [ast.unparse(target) for target in node.targets] == ["DRAWING_NOTES_B"]
    ]
    sourced = {
        name.id
        for value in ast.walk(notes)
        if isinstance(value, ast.FormattedValue)
        for name in ast.walk(value.value)
        if isinstance(name, ast.Name)
    }
    assert "SEAT_UM" in sourced
    assert SEAT_UM == 3.2 and spec.SEAT_UM is SEAT_UM
    builder = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Manufacturing Notes B": DRAWING_NOTES_B' in builder
    # The sheet links the property; its executable strings never retype it
    # (docstrings about other sheets' Ra leaders are not a requirement).
    drawing_tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    docstrings = {
        id(node.value)
        for node in ast.walk(drawing_tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    }
    strings = [
        node.value
        for node in ast.walk(drawing_tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]
    for forbidden in ("EXCEPT 4 BOSSES", "RAIL FLAT", "BORES ALIGN", "Ra 3.2"):
        assert not any(forbidden in value for value in strings), forbidden
    build = next(
        node
        for node in drawing_tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    (properties,) = _named_calls(build, "read_required_properties")
    assert "Manufacturing Notes B" in ast.literal_eval(properties.args[1])
    assert "Manufacturing Notes B" in ast.literal_eval(_keyword(properties, "required"))
    linked = [
        call
        for call in _named_calls(drawing_tree, "add_property_linked_note")
        if ast.literal_eval(call.args[1]) == "Manufacturing Notes B"
    ]
    assert len(linked) == 1
    assert ast.unparse(linked[0].args[2]) == "*keeper_facing_note_xy(keeper_callout_xy)"
    assert _keyword(linked[0], "char_height").id == "FACING_NOTE_HEIGHT"
    assert not [
        call
        for call in _named_calls(drawing_tree, "add_feature_control_frame")
        if "flatness" in ast.unparse(call)
    ]


def test_keeper_feet_stay_on_the_faced_rail_top_and_keep_their_ligaments() -> None:
    assert part.WEB_T == pytest.approx(13.0048)
    assert part.WEB_OUT_X - part.WEB_IN_X == pytest.approx(part.WEB_T)
    assert (part.HALF_H, part.FLANGE, part.FLANGE_BOT_Y) == pytest.approx(
        (18.2499, 8.001, 10.2489)
    )
    assert part.KEEPER_TAP_THREAD_WALL_MARGIN == pytest.approx(2.6168179913276948)
    assert part.KEEPER_TAP_DRILL_WALL_MARGIN == pytest.approx(1.9081881505917684)
    assert min(part.KEEPER_FOOT_BOSS_MARGINS) >= 1.016
    # Along the rail the faced top runs boss to boss, so the fitted foot
    # stays on it exactly when it clears the bosses at the printed bands.
    assert min(part.KEEPER_FOOT_PRINTED_BOSS_MARGINS) > 0.0
    assert min(part.KEEPER_FOOT_RAIL_MARGINS) > 0.0
    # Across it the widest printed foot (on the keeper's own sheet), at the
    # farthest printed fit-up offset from the web, stays inside the narrowest
    # printed flange less the largest printed top-rim break leg (.063 + .005).
    places = spec.DRAWING_REFERENCE_PRECISION
    width_places = places["side flange width"]
    chamfer_places = places["top rim chamfer"]
    foot_places = keeper.DRAWING_PRECISION["Foot"]["Depth"]
    half_flange = spec.printed_limit(part.RAIL_W_SIDE, width_places, -1.0) / 2.0
    offset = (
        abs(part._keeper_printed(keeper.KEEPER_FITUP_X_FROM_WEB_MM, keeper.KEEPER_FITUP_PLACES))
        + keeper.KEEPER_FITUP_X_BAND_MM
    )
    half_foot = part._keeper_printed(keeper.KEEPER_WIDTH, foot_places, 1.0) / 2.0
    max_chamfer = spec.printed_limit(part.EDGE_CHAMFER, chamfer_places, 1.0)
    assert (half_flange, offset, half_foot, max_chamfer) == pytest.approx(
        (17.0307, 3.0, 7.4, 1.7272)
    )
    assert max_chamfer == pytest.approx(part.EDGE_BREAK_PRINTED_MAX)
    margin = half_flange - offset - half_foot - max_chamfer
    assert part.KEEPER_FOOT_PRINTED_FLAT_TOP_SIDE_MARGIN == pytest.approx(margin)
    assert margin == pytest.approx(4.9035)
    # Faced in place: the rail-top plane stays put.
    assert part.HALF_H - part.FLANGE_BOT_Y == pytest.approx(spec.FLANGE_THICKNESS_MM)
    # Native socket finishes only.  The faced top plane's SEAT_UM, washer
    # seats included, rides on linked note B; the cap-recess floors carry
    # none because caps seat on the tube ends, clear of the floors; the hub
    # bore and set-screw spot face carry none (machinist review r1: a
    # clearance bore and a clamp face neither run nor locate).
    assert [c.key for c in spec.SURFACE_FINISHES] == [
        f"socket_{rail}_{end}" for rail in ("east", "west") for end in ("front", "rear")
    ]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "washer spotface seat finish" not in source
    assert not hasattr(spec, "HANGER_SPOTFACE_TARGET")


def test_top_frame_drawing_is_six_sheets() -> None:
    assert drawing.SHEET_NAMES == (
        "PICTORIAL",
        "GEOMETRY",
        "HOLES-SOCKETS",
        "CROSS-TAPS",
        "HUB-SET-SCREW",
        "UNDERSIDE",
    )
    assert set(drawing.SHEET_SCALES) == set(drawing.SHEET_NAMES)
    # No split-line seat regions remain to dimension, qualify or section.
    assert not [key for key in spec.DRAWING_REFERENCE_PRECISION if "keeper seat" in key]
    for module in (spec, part, drawing):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for retired in (
            "KEEPER_SEAT_BOUNDS_XZ",
            "KEEPER_SEAT_CENTRES_XZ",
            "KEEPER_SEAT_EDGE_MARGIN_MM",
            "KeeperSeatFaces",
            "_split_keeper_seats",
            "KEEPER-SEATS",
            '"G-G"',
        ):
            assert retired not in source, (module.__name__, retired)


# The facing note's rows render about 2.6 mm per character at its 3.5 mm
# height (the then 70-character edge-break line on farm 30394c1da: 30 -> 208 mm),
# on the transfer callout's 5.1 mm row pitch.  An estimate, not render ink:
# farm validation measures the regenerated sheet.
_FACING_NOTE_CHAR = 0.0026


def test_keeper_facing_note_hangs_under_the_keeper_callout_clear_of_all_ink() -> None:
    callout, callout_box = _keeper_callout_placed()
    x, y = drawing.keeper_facing_note_xy(callout)
    rows = spec.DRAWING_NOTES_B.splitlines()
    note = (
        x,
        y - len(rows) * drawing.KEEPER_TRANSFER_ROW_PITCH,
        x + max(map(len, rows)) * _FACING_NOTE_CHAR,
        y,
    )
    ink = drawing.INK_CLEARANCE
    # Flush with RD4's left edge, more than a row pitch under the native
    # leader shoulder (runs 20261027T175429300Z/T190435153Z: an ink
    # clearance under it read as the callout's fifth row).
    assert note[0] == pytest.approx(callout_box[0])
    shoulder = callout[1] - drawing.KEEPER_CALLOUT_SHOULDER_DROP
    assert shoulder <= callout_box[1]
    assert shoulder - note[3] == pytest.approx(drawing.KEEPER_FACING_NOTE_GAP)
    assert drawing.KEEPER_FACING_NOTE_GAP > drawing.KEEPER_TRANSFER_ROW_PITCH
    frame = drawing.SHEET_FRAME
    assert frame[0] + ink <= note[0] < note[2] <= frame[2] - ink
    assert frame[1] + ink <= note[1] < note[3] <= frame[3] - ink
    assert _box_box_gap(note, TITLE_BLOCK) >= ink
    left, bottom = _plan(-drawing.PLAN_HALF_X, drawing.PLAN_HALF_Z)
    right, top = _plan(drawing.PLAN_HALF_X, -drawing.PLAN_HALF_Z)
    assert _box_box_gap(note, (left, bottom, right, top)) >= ink
    for _p0, _p1, _expected, (sx, sy), _o, label, suffix, _r in _hole_sheet_stations():
        half_width = len(suffix) * 0.002 / 2
        field = (sx - half_width, sy - 0.0051, sx + half_width, sy + 0.0051)
        assert _box_box_gap(note, field) >= ink, label


# --- The faced underside plane (user ruling 2026-10-12) ---------------------


def test_underside_facing_note_is_the_part_property_carrying_the_seat_finish() -> None:
    import ast

    # Every face on the underside plane between the bosses, named by the
    # mating seats that need it; the bosses and hub gussets below the plane
    # are named out of it.  No flatness zone, no setup method; drawing-guidelines.md rule 7 (notes: few, flagged, never a method)'s four
    # rows at most.
    assert spec.DRAWING_NOTES_C.splitlines() == [
        "UNDERSIDE PLANE BETWEEN BOSSES",
        "(MHA-SM-02 KNIFE-MOUNT SEATS):",
        "Ra 125 µIN; BOSS BOTTOMS AND",
        "HUB GUSSETS EXCLUDED.",
    ]
    assert _config.parts("sm-knife-mount")["number"] == "MHA-SM-02"
    tree = ast.parse(Path(spec.__file__).read_text(encoding="utf-8"))
    (notes,) = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and [ast.unparse(target) for target in node.targets] == ["DRAWING_NOTES_C"]
    ]
    sourced = {
        name.id
        for value in ast.walk(notes)
        if isinstance(value, ast.FormattedValue)
        for name in ast.walk(value.value)
        if isinstance(name, ast.Name)
    }
    assert "SEAT_UM" in sourced
    builder = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Manufacturing Notes C": DRAWING_NOTES_C' in builder
    # The sheet links the property and never retypes it.
    drawing_tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    strings = [
        node.value
        for node in ast.walk(drawing_tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    for forbidden in ("UNDERSIDE PLANE", "KNIFE-MOUNT SEATS", "BOSS BOTTOMS", "EXCLUDED"):
        assert not any(forbidden in value for value in strings), forbidden
    build = next(
        node
        for node in drawing_tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    (properties,) = _named_calls(build, "read_required_properties")
    assert "Manufacturing Notes C" in ast.literal_eval(properties.args[1])
    assert "Manufacturing Notes C" in ast.literal_eval(_keyword(properties, "required"))
    linked = [
        call
        for call in _named_calls(drawing_tree, "add_property_linked_note")
        if ast.literal_eval(call.args[1]) == "Manufacturing Notes C"
    ]
    assert len(linked) == 1
    assert ast.unparse(linked[0].args[2]) == "*UNDERSIDE_FACING_NOTE_XY"
    assert _keyword(linked[0], "char_height").id == "FACING_NOTE_HEIGHT"


def test_underside_facing_note_layout_replays_historical_ink() -> None:
    """Retain the measured DETAIL C baseline, not a live J glyph-clearance claim."""
    x, y = drawing.UNDERSIDE_FACING_NOTE_XY
    rows = spec.DRAWING_NOTES_C.splitlines()
    note = (
        x,
        y - len(rows) * drawing.KEEPER_TRANSFER_ROW_PITCH,
        x + max(map(len, rows)) * _FACING_NOTE_CHAR,
        y,
    )
    ink = drawing.INK_CLEARANCE
    frame = drawing.SHEET_FRAME
    assert frame[0] + ink <= note[0] < note[2] <= frame[2] - ink
    assert frame[1] + ink <= note[1] < note[3] <= frame[3] - ink
    assert _box_box_gap(note, TITLE_BLOCK) >= ink
    # The underside locator's silhouette.
    centre, m_per_mm = drawing.HUB_BOTTOM_CENTER, drawing._HUB_BOTTOM_M_PER_MM
    plan = (
        centre[0] - drawing.PLAN_HALF_X * m_per_mm,
        centre[1] - drawing.PLAN_HALF_Z * m_per_mm,
        centre[0] + drawing.PLAN_HALF_X * m_per_mm,
        centre[1] + drawing.PLAN_HALF_Z * m_per_mm,
    )
    assert _box_box_gap(note, plan) >= ink
    # Detail J's unchanged circular fence: parent's radius at the detail scale.
    parent_r = (part.HUB_GUSSET_HALF_OUT + part.HUB_BOSS_DROP) * m_per_mm
    detail_r = parent_r * (
        drawing.HUB_DETAIL_SCALE[0] / drawing.HUB_DETAIL_SCALE[1]
    ) / (drawing.HUB_BOTTOM_SCALE[0] / drawing.HUB_BOTTOM_SCALE[1])
    cx, cy = drawing.HUB_DETAIL_CENTER
    nearest = (min(max(cx, note[0]), note[2]), min(max(cy, note[1]), note[3]))
    assert math.dist(nearest, (cx, cy)) >= detail_r + ink
    # Historical text on 40d9d030e (sheet mm), including the old DETAIL C /
    # SCALE 2:1 caption.  This replays that caption only, not J's new glyphs.
    # Other blocks: Ø30.0 boss, 7.0 gusset, land, depth and locator label.
    for label, box in {
        "historical detail C caption": (0.2844, 0.0753, 0.3161, 0.0898),
        "boss diameter": (0.1889, 0.0954, 0.2310, 0.1045),
        "gusset thickness": (0.3689, 0.2356, 0.4112, 0.2503),
        "land": (0.1243, 0.1376, 0.1856, 0.1523),
        "historical slot depth": (0.1396, 0.0986, 0.1805, 0.1133),
        "locator label": (0.0604, 0.1115, 0.1461, 0.1200),
    }.items():
        assert _box_box_gap(note, box) >= ink, label


def test_socket_bore_circle_pick_is_exact_about_the_axis() -> None:
    from _drawing_edges import ViewEdge, ViewEdges

    def circle(x, y, z, radius, tag, axis=(0.0, 1.0, 0.0)):
        return ViewEdge(
            edge=tag, line=None, circle=(x, y, z, *axis, radius), vertices=None
        )

    x, z, r = part.COLUMN_X, part.REAR_COLUMN_Z, part.BORE_DIA / 2.0
    edges = ViewEdges(
        "plan",
        (
            circle(x, part.HALF_H + part.BOSS_ABOVE, z, part.BOSS_DIA / 2.0, "boss"),
            circle(x, part.CAP_RECESS_FLOOR_Y, z, r, "bore top"),
            circle(
                x, -part.HALF_H - part.BOSS_BELOW, z, r, "bore bottom", (0.0, -1.0, 0.0)
            ),
            circle(-x, part.CAP_RECESS_FLOOR_Y, z, r, "east bore"),
        ),
    )
    assert drawing._socket_bore_circle(edges, x, z, label="rear") == "bore bottom"
    with pytest.raises(RuntimeError, match="no exact socket bore circle"):
        drawing._socket_bore_circle(edges, x, -z, label="front")


def _called_name(call):
    import ast

    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def _named_calls(node, name):
    import ast

    return [
        call
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == name
    ]


def _keyword(call, name):
    return next((item.value for item in call.keywords if item.arg == name), None)


# --- Drawing-local curve tessellation (offline, not exported-ink proof) ------


class _CurveQualityExtension:
    """ModelDocExtension preference signatures, with real stored readback."""

    def __init__(self, *, rejected=None, unpersisted=None):
        self.values = {
            drawing._IMAGE_QUALITY_WIREFRAME: 0,
            drawing._IMAGE_QUALITY_WIREFRAME_VALUE: 17,
            drawing._IMAGE_QUALITY_HIGH_CURVES: False,
        }
        self.rejected = rejected
        self.unpersisted = unpersisted
        self.sets = []
        self.gets = []

    def _set(self, kind, preference, option, value):
        self.sets.append((kind, preference, option, value))
        assert option == drawing._NO_PREFERENCE_OPTION == 0
        assert preference in self.values
        assert type(value) is (bool if kind == "toggle" else int)
        if preference == self.rejected:
            return False
        if preference != self.unpersisted:
            self.values[preference] = value
        return True

    def SetUserPreferenceInteger(self, preference, option, value):
        return self._set("integer", preference, option, value)

    def SetUserPreferenceToggle(self, preference, option, value):
        return self._set("toggle", preference, option, value)

    def GetUserPreferenceInteger(self, preference, option):
        assert option == drawing._NO_PREFERENCE_OPTION
        assert type(self.values[preference]) is int
        self.gets.append(preference)
        return self.values[preference]

    def GetUserPreferenceToggle(self, preference, option):
        assert option == drawing._NO_PREFERENCE_OPTION
        assert type(self.values[preference]) is bool
        self.gets.append(preference)
        return self.values[preference]


def _curve_quality_adapter(monkeypatch, extension):
    from types import SimpleNamespace

    def early_bound(entity, interface):
        assert entity is extension
        assert interface == "IModelDocExtension"
        return entity

    monkeypatch.setattr(drawing, "_early_bound", early_bound)
    # Deliberately no swApp or source-model receiver: preferences belong only
    # to the new drawing, not the application or its referenced part.
    return SimpleNamespace(currentModel=SimpleNamespace(Extension=extension))


def test_precise_curves_set_and_read_back_only_drawing_preferences(monkeypatch) -> None:
    extension = _CurveQualityExtension()
    drawing._set_precise_curve_quality(_curve_quality_adapter(monkeypatch, extension))
    expected = {
        drawing._IMAGE_QUALITY_WIREFRAME: drawing._WIREFRAME_CUSTOM,
        drawing._IMAGE_QUALITY_WIREFRAME_VALUE: drawing._CURVE_RESOLUTION,
        drawing._IMAGE_QUALITY_HIGH_CURVES: True,
    }
    assert drawing._WIREFRAME_CUSTOM == 2
    assert drawing._CURVE_RESOLUTION == 100
    assert len(expected) == 3
    assert extension.values == expected
    assert len(extension.sets) == 3
    assert set(extension.sets) == {
        ("integer", drawing._IMAGE_QUALITY_WIREFRAME, 0, 2),
        ("integer", drawing._IMAGE_QUALITY_WIREFRAME_VALUE, 0, 100),
        ("toggle", drawing._IMAGE_QUALITY_HIGH_CURVES, 0, True),
    }
    # Both the initial telemetry snapshot and the post-write check read every
    # preference, without prescribing an irrelevant order among preferences.
    assert {preference: extension.gets.count(preference) for preference in expected} == {
        preference: 2 for preference in expected
    }


@pytest.mark.parametrize("preference", (
    "_IMAGE_QUALITY_WIREFRAME",
    "_IMAGE_QUALITY_WIREFRAME_VALUE",
    "_IMAGE_QUALITY_HIGH_CURVES",
))
@pytest.mark.parametrize("failure", ("rejected", "unpersisted"))
def test_precise_curves_refuse_failed_or_unpersisted_preferences(
    monkeypatch, preference, failure
) -> None:
    extension = _CurveQualityExtension(**{failure: getattr(drawing, preference)})
    with pytest.raises(RuntimeError):
        drawing._set_precise_curve_quality(_curve_quality_adapter(monkeypatch, extension))
    assert any(write[1] == getattr(drawing, preference) for write in extension.sets)


def test_precise_curves_are_configured_immediately_after_new_drawing() -> None:
    import ast

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    (new_drawing,) = _named_calls(build, "new_project_drawing")
    (quality,) = _named_calls(build, "_set_precise_curve_quality")
    setup_index = next(
        index for index, statement in enumerate(build.body)
        if new_drawing in ast.walk(statement)
    )
    assert isinstance(build.body[setup_index + 1], ast.Expr)
    assert build.body[setup_index + 1].value is quality
    assert [ast.unparse(arg) for arg in quality.args] == ["adapter"]


def test_precise_curve_native_members_match_generated_extension_contract() -> None:
    import ast
    from test_native_bank_retention_contract import _bind, _dispatch, _members

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    helper = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_set_precise_curve_quality"
    )
    (binding,) = _named_calls(helper, "_early_bound")
    assert ast.unparse(binding.args[0]) == "adapter.currentModel.Extension"
    assert ast.literal_eval(binding.args[1]) == "IModelDocExtension"
    methods, _getters, _setters = _members("IModelDocExtension")
    expected_returns = {
        "SetUserPreferenceInteger": 11,  # VT_BOOL, not an integer preference value
        "SetUserPreferenceToggle": 11,
        "GetUserPreferenceInteger": 3,  # VT_I4
        "GetUserPreferenceToggle": 11,
    }
    calls = [
        node for node in ast.walk(helper)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "extension"
    ]
    assert {call.func.attr for call in calls} == set(expected_returns)
    for call in calls:
        method = methods[call.func.attr]
        _bind(method, call, native=True)
        retval, _arguments = _dispatch(method)
        assert retval[0] == expected_returns[call.func.attr]
