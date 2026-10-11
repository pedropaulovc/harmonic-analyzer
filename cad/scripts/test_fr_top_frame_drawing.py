"""Offline contracts for the top-frame geometry and drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import ch_fulcrum_keeper_spec as keeper
import rocker_bank_layout as rocker_bank
import vn_frame_side_screw_spec as keeper_screw
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
from vn_tube_frame_cap_spec import MAX_OUTER_DIAMETER
from _surface_finish import SEAT_UM
import fr_top_frame_spec as spec
import fr_tube_frame_spec


def test_nominal_corner_bores_and_cap_recesses_clear_the_installed_stack() -> None:
    assert part.BORE_DIA == COLUMN_SOCKET_DIAMETER == 25.5
    assert part.CAP_RECESS_DIAMETER == CAP_RECESS_DIAMETER
    assert part.CAP_RECESS_DEPTH == CAP_RECESS_DEPTH
    assert CAP_RECESS_DIAMETER > MAX_OUTER_DIAMETER
    assert math.isclose(
        part.CAP_RECESS_DIAMETRAL_CLEARANCE,
        CAP_RECESS_DIAMETER - MAX_OUTER_DIAMETER,
        abs_tol=1e-12,
    )
    assert math.isclose(part.CAP_RECESS_DIAMETRAL_CLEARANCE, 0.436232, abs_tol=1e-6)
    assert math.isclose(
        part.CAP_RECESS_DIAMETRAL_CLEARANCE + part.CAP_RECESS_DIAMETER_BAND[0],
        0.636232,
        abs_tol=1e-6,
    )
    # CAD reference clearance is unchanged; actual sockets are matched to
    # their assigned tubes rather than accepted against a fixed bore band.
    assert math.isclose(
        part.BORE_DIA - fr_tube_frame_spec.OUTER_DIA,
        0.10,
        abs_tol=1e-12,
    )
    assert part.CAP_RECESS_FLOOR_Y - part.SIDE_TAP_DRILL_DIA / 2.0 > 0.0
    assert part.CAP_RECESS_DIAMETER_BAND == (0.20, 0.0)
    assert part.CAP_RECESS_DEPTH_BAND == (0.30, 0.0)
    recess_floor_world = TOP_SCREW_Y + part.CAP_RECESS_FLOOR_Y
    assert math.isclose(CAP_MOUTH_Y - recess_floor_world, 1.50875, abs_tol=1e-9)
    assert math.isclose(
        recess_floor_world - (TOP_SCREW_Y + TUBE_CROSS_HOLE_DIAMETER / 2.0),
        3.95,
        abs_tol=1e-9,
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
    depth_tolerance = float(
        str(_config.title_block("linear_1pl")["display"]).lstrip("±")
    )
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
    boss_radius = (
        round(part.BOSS_DIA, boss_places)
        + boss_direction * spec.PRINTED_LINEAR_BAND_MM[boss_places]
    ) / 2.0
    counterbore_radius = (
        round(part.COUNTERBORE_DIA, seat_places)
        + seat_direction * spec.PRINTED_LINEAR_BAND_MM[seat_places]
    ) / 2.0
    floor_offset = (
        round(part.COUNTERBORE_FLOOR - abs(part.FRONT_COLUMN_Z), floor_places)
        + floor_direction * spec.PRINTED_LINEAR_BAND_MM[floor_places]
    )
    # The mouth's lowest point on a Y-axis barrel is at the counterbore's
    # widest |X|; the head is flush when its top stays below it.
    mouth_low = math.sqrt(boss_radius**2 - counterbore_radius**2)
    recess = mouth_low - (floor_offset + part.CROSS_SCREW_HEAD_H)
    assert recess > 0.0
    assert counterbore_radius > part.CROSS_SCREW_HEAD_DIA / 2.0
    if (boss_direction, seat_direction, floor_direction) == (-1, 1, 1):
        assert recess == pytest.approx(part.COUNTERBORE_PRINTED_HEAD_RECESS)


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
    assert part.SIDE_TAP_THREAD_WALL_MARGIN == pytest.approx(4.087)
    assert part.SIDE_TAP_DRILL_WALL_MARGIN == pytest.approx(4.4807)
    assert major_dia / 2.0 < part.HALF_H


def test_smaller_bosses_leave_real_plan_corners_and_the_outward_foot_seat() -> None:
    assert part.BOSS_DIA == spec.BOSS_DIA == 45.0
    assert part.BORE_DIA == 25.5
    assert part.CAP_RECESS_DIAMETER == 27.5
    assert (part.BOSS_DIA - part.CAP_RECESS_DIAMETER) / 2.0 == 8.75
    assert (
        math.hypot(part.RAIL_W_SIDE / 2.0, part.RAIL_W_FR / 2.0) > part.BOSS_DIA / 2.0
    )
    assert drawing.PLAN_HALF_X == 219.5
    assert drawing.PLAN_HALF_Z == 134.5
    assert drawing.PLAN_HALF_X - part.OUTER_X == pytest.approx(5.4)
    assert drawing.PLAN_HALF_Z - part.OUTER_Z == pytest.approx(3.5)
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
    assert part.KEEPER_TAP_Z_FRONT == pytest.approx(-82.754, abs=0.0005)
    assert part.KEEPER_TAP_Z_REAR == pytest.approx(81.746, abs=0.0005)
    assert part.KEEPER_FOOT_TIP_Z_FRONT == pytest.approx(-88.004, abs=0.0005)
    assert part.KEEPER_FOOT_TIP_Z_REAR == pytest.approx(86.996, abs=0.0005)
    assert part.KEEPER_FOOT_BOSS_MARGINS == pytest.approx((1.496, 2.504), abs=0.0005)
    assert min(part.KEEPER_FOOT_BOSS_MARGINS) >= 1.0
    assert part.KEEPER_FOOT_PRINTED_BOSS_MARGINS == pytest.approx((0.150, 0.640))
    assert min(part.KEEPER_FOOT_PRINTED_BOSS_MARGINS) > 0.0
    assert part.KEEPER_FOOT_RAIL_MARGINS == pytest.approx((4.996, 6.004), abs=0.0005)
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
@pytest.mark.parametrize("lug_direction", (-1, 1))
@pytest.mark.parametrize("foot_direction", (-1, 1))
@pytest.mark.parametrize("boss_direction", (-1, 1))
def test_complete_keeper_foot_clears_boss_at_every_printed_fitup_corner(
    front_station_direction: int,
    rear_station_direction: int,
    pitch_direction: int,
    lug_direction: int,
    foot_direction: int,
    boss_direction: int,
) -> None:
    # Actual fit-up locates the lug INNER faces before transferring the
    # frame taps. This is not a stack of model-nominal tap/hole positions.
    lug_places = keeper.DRAWING_PRECISION["LugBody"]["LugThickness"]
    foot_places = keeper.DRAWING_PRECISION["FootProfile"]["FootLength"]
    boss_places = spec.DRAWING_PRECISION["BossUpProfile"]["C0Dia"]
    pitch_places = spec.DRAWING_REFERENCE_PRECISION["socket vertical pitch"]
    lug_thickness = (
        round(2.0 * keeper.LUG_HALF_T, lug_places)
        + lug_direction * spec.PRINTED_LINEAR_BAND_MM[lug_places]
    )
    foot_length = (
        round(keeper.FOOT_L, foot_places)
        + foot_direction * spec.PRINTED_LINEAR_BAND_MM[foot_places]
    )
    boss_radius = (
        round(part.BOSS_DIA, boss_places)
        + boss_direction * spec.PRINTED_LINEAR_BAND_MM[boss_places]
    ) / 2.0
    socket_pitch = (
        round(part.REAR_COLUMN_Z - part.FRONT_COLUMN_Z, pitch_places)
        + pitch_direction * spec.PRINTED_LINEAR_BAND_MM[pitch_places]
    )
    front_inner = (
        round(
            keeper.KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM[0],
            keeper.KEEPER_FITUP_PLACES,
        )
        + front_station_direction * keeper.KEEPER_FITUP_LOCATION_BAND_MM
    )
    rear_inner = (
        round(
            keeper.KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM[1],
            keeper.KEEPER_FITUP_PLACES,
        )
        + rear_station_direction * keeper.KEEPER_FITUP_LOCATION_BAND_MM
    )
    margins = (
        front_inner - lug_thickness - foot_length - boss_radius,
        socket_pitch - rear_inner - lug_thickness - foot_length - boss_radius,
    )
    assert min(margins) > 0.0
    if (
        front_station_direction,
        rear_station_direction,
        pitch_direction,
        lug_direction,
        foot_direction,
        boss_direction,
    ) == (-1, 1, -1, 1, 1, 1):
        assert margins == pytest.approx(part.KEEPER_FOOT_PRINTED_BOSS_MARGINS)


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
    assert actual_upper == pytest.approx(18869.376997453055)
    assert actual_lower == pytest.approx(28519.255654222216)


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
    assert outer == pytest.approx(2296.176445206839)
    assert window == pytest.approx(2774.3499756456845)
    assert part.WEB_T == 13.0
    root_chord = math.sqrt((part.BOSS_DIA / 2.0) ** 2 - (part.WEB_T / 2.0) ** 2)
    side_run = 2.0 * (abs(part.FRONT_COLUMN_Z) - root_chord)
    front_rear_run = 2.0 * (part.COLUMN_X - root_chord)
    outer_run = 2.0 * side_run - part.HUB_RIB_W + 2.0 * front_rear_run
    window_run = outer_run - 2.0 * (part.LAND_X1 - part.LAND_X0)
    assert root_chord == pytest.approx(21.540659228538015)
    assert side_run == pytest.approx(180.91868154292396)
    assert front_rear_run == pytest.approx(350.918681542924)
    assert outer_run == pytest.approx(1036.674726171696)
    assert window_run == pytest.approx(896.674726171696)
    fillet_area = (1.0 - math.pi / 4.0) * part.ROOT_FILLET_R**2
    crossbar_run = 2.0 * 2.0 * part.BAR_POCKET_Z
    assert part._t_root_add() == pytest.approx(
        fillet_area * (outer_run + window_run + crossbar_run)
    )
    points = part._outer_corner_top_edges()
    assert len(points) == 8
    for x, y, z in points:
        assert y == part.HALF_H
        assert abs(x) == part.OUTER_X or abs(z) == part.OUTER_Z
        assert (
            math.hypot(abs(x) - part.COLUMN_X, abs(z) - abs(part.FRONT_COLUMN_Z))
            > part.BOSS_DIA / 2.0
        )
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "outer_corner_edges = _outer_corner_top_edges()" in source
    assert "] + outer_corner_edges" in " ".join(source.split())


def test_crossbar_t_keeps_the_hanger_holes_in_the_full_depth_junctions() -> None:
    # The T stops short of the gusset legs, leaving a full-depth bar side
    # long enough to take its own C2; the web is centred on the knife line
    # and every hanger hole stays beyond the pocket ends.
    assert part.INNER_Z - part.GUSSET - part.BAR_POCKET_Z > 2.0 * part.EDGE_CHAMFER
    assert (part.BAR_WEB_X0 + part.BAR_WEB_X1) / 2.0 == part.HANGER_X
    assert part.BAR_WEB_X1 - part.BAR_WEB_X0 == part.WEB_T
    assert part.BAR_X0 < part.BAR_WEB_X0 - part.ROOT_FILLET_R
    assert part.BAR_WEB_X1 + part.ROOT_FILLET_R < part.BAR_X1
    band = spec.PRINTED_LINEAR_BAND_MM[1]
    pocket_end = part.BAR_POCKET_Z + 2.0 * band
    for station in (part.STUD_Z_FRONT, part.STUD_Z_REAR):
        largest_hole_r = (part.HANGER_CBORE_DIA + spec.PRINTED_LINEAR_BAND_MM[2]) / 2.0
        wall = abs(station) - band - largest_hole_r - pocket_end
        assert wall >= 2.0
    assert min(part.BAR_POCKET_HOLE_WALLS.values()) >= 2.0


def test_crossbar_pocket_end_breaks_clear_the_knife_mount_seat() -> None:
    # Print-worst: the mount's seat face nearest the pocket, from the dowel
    # row at the near station's .X band and half the slip, by the worse
    # .X row-to-face stack and the block's width skewed by the title-block
    # angle, stays 0.5 beyond the pocket end's C2 band even with both ends
    # of the pocket a full .X band long.
    import sm_knife_mount_spec as mount
    from _printed_tolerance import angular_band_deg

    band = spec.PRINTED_LINEAR_BAND_MM[1]
    reach = max(
        mount.HOLE_ROW_FACE_DISTANCE + mount.HOLE_ROW_FACE_TOL,
        mount.SUPPORT_Z_THICK
        + mount.BLOCK_SIZE_TOL
        - (mount.HOLE_ROW_FACE_DISTANCE - mount.HOLE_ROW_FACE_TOL),
    ) + (2.0 * mount.BLK_HALF_X + mount.BLOCK_SIZE_TOL) * math.tan(
        math.radians(angular_band_deg())
    )
    near_station = min(abs(part.STUD_Z_FRONT), abs(part.STUD_Z_REAR))
    seat_edge = near_station - band - spec.HANGER_PIN_SLIP_CLEARANCE_MAX / 2.0 - reach
    pocket_band = part.BAR_POCKET_Z + 2.0 * band + part.EDGE_CHAMFER
    assert seat_edge - pocket_band >= 0.5
    assert part.BAR_POCKET_SEAT_CLEARANCE >= seat_edge - pocket_band
    assert part.BAR_POCKET_SEAT_CLEARANCE >= 0.5


def test_external_edge_breaks_select_distinct_edges_and_skip_the_noted_ones() -> None:
    points, removal = part._external_edge_breaks()
    assert len({tuple(round(value, 6) for value in point) for point in points}) == len(
        points
    )
    assert removal > 0.0
    # No two picks share an edge's 0.5 mm selection radius.
    for i, a in enumerate(points):
        for b in points[i + 1 :]:
            assert math.dist(a, b) > 0.5
    # The crossbar flange's underside edges and the hub rib's outer and inner
    # bottom edges stay sharp: none is picked.  Between each pocket end and
    # its gusset leg the full-depth bar side bottoms are broken.
    for sz in (-1.0, 1.0):
        for x_bar in (part.BAR_X0, part.BAR_X1):
            assert [
                x_bar,
                -part.HALF_H,
                sz * (part.BAR_POCKET_Z + part.INNER_Z - part.GUSSET) / 2.0,
            ] in points
    for x, y, z in points:
        assert not (
            y == part.FLANGE_BOT_Y
            and x in (part.BAR_X0, part.BAR_X1)
            and abs(z) < part.BAR_POCKET_Z
        )
        assert not (
            y == -part.HALF_H
            and x in (-part.OUTER_X, -part.INNER_X)
            and part.GOOSENECK_Z - part.HUB_RIB_W / 2.0
            < z
            < part.GOOSENECK_Z + part.HUB_RIB_W / 2.0
        )


def test_keeper_tap_holds_stock_screw_above_a_plug_tap_lead() -> None:
    major, length, _, _, pitch = FILLISTER_SIZE
    tap_spec = part.KEEPER_TAP_SPEC
    full_thread = tap_spec.overrides_mm["ThreadDepth"]
    depth_tolerance = spec.PRINTED_LINEAR_BAND_MM[
        spec.KEEPER_TAP_CALLOUT_PRECISION["hw-threaddepth"]
    ]
    foot_places = keeper.DRAWING_PRECISION["FootProfile"]["FootRise"]
    foot_band = spec.PRINTED_LINEAR_BAND_MM[foot_places]
    cb_places = keeper.FOOT_COUNTERBORE_DEPTH_PLACES
    cb_band = spec.PRINTED_LINEAR_BAND_MM[cb_places]
    minimum_entry = length - (
        (round(keeper.FOOT_H, foot_places) + foot_band)
        - (round(keeper.CBORE_DEPTH_MM, cb_places) - cb_band)
    )
    maximum_entry = length - (
        (round(keeper.FOOT_H, foot_places) - foot_band)
        - (round(keeper.CBORE_DEPTH_MM, cb_places) + cb_band)
    )
    assert tap_spec is keeper.KEEPER_TAP_SPEC
    assert tap_spec.size == keeper_screw.THREAD == "#2-56"
    assert full_thread == keeper.KEEPER_TAP_THREAD_DEPTH_MM == 7.6
    assert minimum_entry >= 1.5 * major
    assert maximum_entry == pytest.approx(6.5325)
    assert part.KEEPER_MAX_STOCK_ENTRY == pytest.approx(maximum_entry)
    assert full_thread - depth_tolerance - maximum_entry >= 0.25
    assert part.KEEPER_MIN_THREAD_TIP_RESERVE == pytest.approx(0.2675)
    assert tap_spec.depth_mm - full_thread - 2.0 * depth_tolerance >= 5.0 * pitch
    drill_point = part.TAP_DRILL_MM[tap_spec.size] / 2.0 * part.DRILL_POINT_H
    assert tap_spec.depth_mm + depth_tolerance + drill_point < part.RING_HEIGHT


def test_transferred_keeper_receiver_keeps_real_normal_wall_at_printed_bands() -> None:
    assert part.KEEPER_TAP_X == part.COLUMN_X + keeper.KEEPER_FITUP_X_FROM_WEB_MM
    assert part.KEEPER_MAX_TRANSVERSE_OFFSET == pytest.approx(0.53)
    assert part.KEEPER_MAX_WEB_CENTRE_OFFSET == pytest.approx(3.45)
    assert part.KEEPER_MIN_WEB_HALF_WIDTH == pytest.approx(6.1)
    assert part.KEEPER_MIN_ROOT_RADIUS == pytest.approx(2.2)
    assert part.KEEPER_MIN_FLANGE_THICKNESS == pytest.approx(7.2)
    assert part.KEEPER_MAX_FULL_THREAD_DEPTH == pytest.approx(8.4)
    assert part.KEEPER_TAP_THREAD_WALL_MARGIN_NO_WANDER == pytest.approx(
        1.688580825956946
    )
    assert part.KEEPER_TAP_DRILL_WALL_MARGIN_NO_WANDER == pytest.approx(1.710)
    assert part.KEEPER_TAP_THREAD_WALL_MARGIN == pytest.approx(1.6241775880068343)
    assert part.KEEPER_TAP_DRILL_WALL_MARGIN == pytest.approx(1.645596762049888)
    assert (
        min(part.KEEPER_TAP_THREAD_WALL_MARGIN, part.KEEPER_TAP_DRILL_WALL_MARGIN)
        >= 1.5
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
    # the bare-web wall. Its .XX diameter also carries DRILLED HOLES +0.10.
    assert part.KEEPER_MAX_TAP_DRILL_RADIUS == pytest.approx(0.94)
    assert (
        part.KEEPER_MIN_WEB_HALF_WIDTH
        - part.KEEPER_MAX_WEB_CENTRE_OFFSET
        - part.KEEPER_MAX_TAP_DRILL_RADIUS
    ) == pytest.approx(part.KEEPER_TAP_DRILL_WALL_MARGIN_NO_WANDER)


def _printed_receiver_stack():
    """Independently reconstruct the worst printed root, transferred axis,
    full-thread corner and .3 degree full-depth wander, in model mm:
    (root radius, axis offset from the web centre, thread corner offset,
    full-thread depth, full printed pilot depth, wander, pilot radius)."""
    root_places = spec.DRAWING_REFERENCE_PRECISION["T rail root radius"]
    root_radius = (
        round(part.ROOT_FILLET_R, root_places)
        - spec.PRINTED_LINEAR_BAND_MM[root_places]
    )
    foot_places = keeper.DRAWING_PRECISION["Foot"]["Depth"]
    station_places = keeper.DRAWING_PRECISION["FootScrewSideReference"]["ScrewFromSide"]
    transverse_offset = max(
        abs(
            round(keeper.SCREW_FROM_SIDE, station_places)
            + station_direction * spec.PRINTED_LINEAR_BAND_MM[station_places]
            - (
                round(keeper.KEEPER_WIDTH, foot_places)
                + foot_direction * spec.PRINTED_LINEAR_BAND_MM[foot_places]
            )
            / 2.0
        )
        for station_direction in (-1, 1)
        for foot_direction in (-1, 1)
    )
    axis_offset = (
        abs(round(keeper.KEEPER_FITUP_X_FROM_WEB_MM, keeper.KEEPER_FITUP_PLACES))
        + keeper.KEEPER_FITUP_LOCATION_BAND_MM
        + transverse_offset
    )
    thread_places = spec.KEEPER_TAP_CALLOUT_PRECISION["hw-threaddepth"]
    thread_depth = (
        round(keeper.KEEPER_TAP_SPEC.overrides_mm["ThreadDepth"], thread_places)
        + spec.PRINTED_LINEAR_BAND_MM[thread_places]
    )
    drill_places = spec.KEEPER_TAP_CALLOUT_PRECISION["hw-tapdrldepth"]
    cylinder_depth = (
        round(keeper.KEEPER_TAP_SPEC.depth_mm, drill_places)
        + spec.PRINTED_LINEAR_BAND_MM[drill_places]
    )
    assert cylinder_depth == pytest.approx(12.3)
    assert spec.KEEPER_TAP_DRILL_WANDER_DEG == 0.3
    displacement = cylinder_depth * math.tan(math.radians(0.3))
    assert displacement == pytest.approx(0.06440323795011157)
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
    assert drilled_band == 0.10
    pilot_radius = (
        round(part.TAP_DRILL_MM[keeper.KEEPER_TAP_SPEC.size], diameter_places)
        + drilled_band
    ) / 2.0
    assert pilot_radius == pytest.approx(0.94)
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
    assert web_places == 1
    assert spec.PRINTED_LINEAR_BAND_MM[web_places] == 0.8
    return (
        round(web_thickness, web_places) - spec.PRINTED_LINEAR_BAND_MM[web_places]
    ) / 2.0


@pytest.mark.parametrize(
    ("web_thickness", "expected_thread_wall", "expected_pilot_wall"),
    (
        (12.7, 1.4794211222462903, 1.4955967620498885),
        (13.0, 1.6241775880068343, 1.645596762049888),
    ),
)
def test_keeper_receiver_full_depth_displaced_axis_proves_web_change(
    web_thickness: float, expected_thread_wall: float, expected_pilot_wall: float
) -> None:
    # Independently reconstruct the worst printed sizes and transferred axis.
    # The .X band stays loose; widening the web, not tightening it, buys wall.
    half_width = _printed_web_half_width(web_thickness)
    flange_places = spec.DRAWING_REFERENCE_PRECISION["keeper seat flange thickness"]
    flange_depth = (
        round(spec.FLANGE_THICKNESS_MM, flange_places)
        - spec.PRINTED_LINEAR_BAND_MM[flange_places]
    )
    (
        root_radius,
        axis_offset,
        corner_x,
        thread_depth,
        cylinder_depth,
        displacement,
        pilot_radius,
    ) = _printed_receiver_stack()
    centre_x = half_width + root_radius
    centre_depth = flange_depth + root_radius
    normal_length = math.hypot(centre_x - corner_x, centre_depth - thread_depth)
    # Move the worst thread corner toward its nearest point on the arc by
    # the FULL-depth displacement disk. This assumes no guiding operation
    # and deliberately does not scale the allowance down to thread depth.
    displaced_x = corner_x + displacement * (centre_x - corner_x) / normal_length
    displaced_depth = (
        thread_depth + displacement * (centre_depth - thread_depth) / normal_length
    )
    thread_wall = min(
        math.hypot(
            centre_x - root_radius * math.cos(index * math.pi / 8192.0) - displaced_x,
            centre_depth
            - root_radius * math.sin(index * math.pi / 8192.0)
            - displaced_depth,
        )
        for index in range(4097)
    )
    # The pilot cylinder reaches below the root into the bare web; shift
    # its axis toward that face instead of toward the quarter-circle.
    assert cylinder_depth > centre_depth
    displaced_pilot_axis = axis_offset + displacement
    pilot_wall = half_width - (displaced_pilot_axis + pilot_radius)
    assert thread_wall == pytest.approx(expected_thread_wall, abs=1e-6)
    assert pilot_wall == pytest.approx(expected_pilot_wall)
    if web_thickness == 12.7:
        # Both former no-wander guards passed, yet .3 degrees over the
        # full printed drill depth supplies a counterexample to both.
        assert thread_wall + displacement >= 1.5
        assert pilot_wall + displacement >= 1.5
        assert thread_wall < 1.5
        assert pilot_wall < 1.5
    else:
        assert thread_wall >= 1.5
        assert pilot_wall >= 1.5
        assert thread_wall == pytest.approx(
            part.KEEPER_TAP_THREAD_WALL_MARGIN, abs=1e-6
        )
        assert pilot_wall == pytest.approx(part.KEEPER_TAP_DRILL_WALL_MARGIN)


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


@pytest.mark.parametrize("stack", ("cap floor height", "keeper seat flange thickness"))
def test_printed_keeper_seat_flange_minimum_keeps_the_receiver_wall(stack) -> None:
    """Facing may lower each seat; only a directly printed FINAL flange
    under it bounds what the receiver's T-root keeps at the worst case."""
    band = spec.PRINTED_LINEAR_BAND_MM
    seat_places = spec.DRAWING_REFERENCE_PRECISION["keeper seat flange thickness"]
    top_places = spec.DRAWING_REFERENCE_PRECISION["top flange thickness"]
    assert seat_places == top_places == spec.FLANGE_THICKNESS_PLACES == 1
    assert spec.FLANGE_THICKNESS_MM == part.FLANGE == 8.0
    if stack == "keeper seat flange thickness":
        flange_depth = round(spec.FLANGE_THICKNESS_MM, seat_places) - band[seat_places]
        assert flange_depth == pytest.approx(7.2)
        # The very minimum the part's receiver-wall guard is built on.
        assert flange_depth == pytest.approx(part.KEEPER_MIN_FLANGE_THICKNESS)
    else:
        # Round 3's print: the cast flange at its own .X minimum, with each
        # seat held 11.80 (.XX) over cap floors that a .X boss top and a
        # +0.30 / 0 recess depth may already have lowered.  Nothing printed
        # bounded the flange left under the faced seat.
        height_places = spec.DRAWING_PRECISION["CapRecesses"]["CapRecessDepth"]
        height = part.HALF_H - part.CAP_RECESS_FLOOR_Y
        assert f"{height:.{height_places}f}" == "11.80"
        boss_places = spec.DRAWING_REFERENCE_PRECISION["boss top above rail top"]
        depression = (
            band[height_places] + part.CAP_RECESS_DEPTH_BAND[0] + band[boss_places]
        )
        assert depression == pytest.approx(1.61)
        flange_depth = round(part.FLANGE, top_places) - band[top_places] - depression
        assert flange_depth == pytest.approx(5.59)
    (
        root_radius,
        axis_offset,
        corner_x,
        thread_depth,
        _cylinder_depth,
        displacement,
        pilot_radius,
    ) = _printed_receiver_stack()
    half_width = _printed_web_half_width(part.WEB_T)
    thread_wall = _worst_thread_wall(
        half_width, root_radius, flange_depth, corner_x, thread_depth, displacement
    )
    # The pilot reaches the bare web below the root whatever the flange.
    pilot_wall = half_width - (axis_offset + displacement + pilot_radius)
    assert pilot_wall == pytest.approx(1.645596762049888)
    assert pilot_wall == pytest.approx(part.KEEPER_TAP_DRILL_WALL_MARGIN)
    if stack == "keeper seat flange thickness":
        assert thread_wall == pytest.approx(1.6241775880068343, abs=1e-6)
        assert thread_wall == pytest.approx(
            part.KEEPER_TAP_THREAD_WALL_MARGIN, abs=1e-6
        )
        assert min(thread_wall, pilot_wall) >= 1.5
    else:
        # The faced-down seat lifts the root above the thread corner, which
        # then faces bare web: the counterexample to the old print.
        assert thread_wall == pytest.approx(1.4933967620498887, abs=1e-6)
        assert thread_wall < 1.5


def test_every_imported_drawing_dimension_has_part_authored_places() -> None:
    # Rule 2: the part owns the decimal places, so a kept model dimension
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
        drawing.HANGER_SECTION_KEEP,
    )
    assert kept, "the top-frame sheets import no model dimensions"
    assert not kept - set(spec.DRAWING_PRECISION_BY_NAME)


# --- #946 leader-over-part: RD4 and the cap seat Ra 3.2 -------------------
#
# The sheets are projected here from the model constants, as the build reads
# them through each view's ModelToViewTransform: the half-size plan (+X right,
# +Z down the sheet) and section A-A (+Z right, +Y up).  #946's measure: the
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


def _section(z: float, y: float) -> tuple[float, float]:
    cx, cy = drawing.DETAIL_SECTION_CENTER
    return (cx + z * _S, cy + y * _S)


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


def _cap_seat_geometry():
    tip = _section(
        part.FRONT_COLUMN_Z - (part.BORE_DIA + part.CAP_RECESS_DIAMETER) / 4.0,
        part.CAP_RECESS_FLOOR_Y,
    )
    face_z = part.FRONT_COLUMN_Z - part.BOSS_DIA / 2.0
    top = part.HALF_H + part.BOSS_ABOVE
    entry = _section(face_z, (part.COUNTERBORE_DIA / 2.0 + top) / 2.0)
    return (
        tip,
        entry,
        _section(face_z, top),
        _section(face_z, part.COUNTERBORE_DIA / 2.0),
    )


def _section_detour(start, tip):
    """#946's detour of a leader into A-A's front boss, whose outer face is
    the section's left edge: it enters through that face or the underside."""
    face_x, top_y = _section(
        part.FRONT_COLUMN_Z - part.BOSS_DIA / 2.0, part.HALF_H + part.BOSS_ABOVE
    )
    bottom_y = _section(0.0, -part.HALF_H - part.BOSS_BELOW)[1]
    (x0, y0), (x1, y1) = start, tip
    entry = None
    for step in range(20001):
        t = step / 20000.0
        x, y = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        if x >= face_x and bottom_y <= y <= top_y:
            entry = (x, y)
            break
    approach = min(tip[0] - face_x, top_y - tip[1])
    over = math.dist(entry, tip)
    return over, approach, over - approach


def test_cap_seat_finish_leader_takes_the_short_way_to_its_ledge() -> None:
    """#946 / b49e1: the cap seat Ra 3.2 stood below-left of A-A and its
    leader climbed 24.7 mm through the hatching to the far ledge, 16.6 mm
    past the approach.  It now lands on the near ledge through the boss's
    outer face, between the cross tap's counterbore and the boss top."""
    tip, entry, top, counterbore_top = _cap_seat_geometry()
    symbol = drawing.cap_seat_finish_placement(tip, entry)
    bend = (symbol[0] + drawing.FINISH_LEADER_TAIL, symbol[1])
    # The bend, the entry and the tip are one straight leader.
    cross = (entry[0] - tip[0]) * (bend[1] - tip[1]) - (entry[1] - tip[1]) * (bend[0] - tip[0])
    assert cross == pytest.approx(0.0, abs=1e-12)
    over, approach, detour = _section_detour(bend, tip)
    assert detour <= LEADER_DETOUR_TARGET, (over, approach, detour)
    assert counterbore_top[1] < entry[1] < top[1]
    # The symbol's ink stays off the part.
    assert bend[0] + drawing.CAP_SEAT_FINISH_INK_PAST_BEND <= entry[0] - drawing.INK_CLEARANCE


def test_b49e1_cap_seat_finish_is_what_ran_through_the_hatching() -> None:
    """b49e1's symbol at (0.175, 0.114) with its leader to the far ledge,
    (240.625, 138.675) mm on that render, gates by the same measure."""
    far_ledge = _section(
        part.FRONT_COLUMN_Z + (part.BORE_DIA + part.CAP_RECESS_DIAMETER) / 4.0,
        part.CAP_RECESS_FLOOR_Y,
    )
    shift = (far_ledge[0] - 0.240625, far_ledge[1] - 0.138675)
    bend = (0.175 + drawing.FINISH_LEADER_TAIL + shift[0], 0.114 + shift[1])
    _over, _approach, detour = _section_detour(bend, far_ledge)
    assert detour > 0.010


def test_build_places_both_leaders_from_their_projected_features() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    for placed in (
        "keeper_callout_placement(",
        "callout_xy=keeper_callout_xy,",
        "rear_keeper = (KEEPER_TAP_X, HALF_H, KEEPER_TAP_Z_REAR)",
        "symbol_xy=cap_seat_finish_placement(cap_seat_tip, cap_seat_entry),",
        "leader_attach_xy=cap_seat_tip,",
    ):
        assert placed in body, placed


# #955 section letters.  layoutcheck's replay of b49e1 found three cutting-
# plane letters printed on ink (B 3.65 mm on the rail edge and the 183.9,
# E 0.99 on the corner boss, D 6.17 on the hub rail's inner face) and two more
# under 1 mm off it.  The two 1:3 plans are projected as above (+X right, +Z
# down the sheet); each letter's box stands about its arrow's tail.
_PLAN_S = drawing.GEOMETRY_VIEW_SCALE / 1000.0
_SECTION_PLAN = {
    "B": drawing.GEOMETRY_TOP_CENTER,
    "E": drawing.GEOMETRY_TOP_CENTER,
    "D": drawing.HUB_TOP_CENTER,
}
_LETTER_ENDS = ("B-outer", "B-inner", "E-inner", "E-outer", "D-outer", "D-inner")
# b49e1's cutting-line ends, as the build then typed them, start first.
_B49E1_BOSS_DIA = 52.2
_B49E1_CUT_ENDS = {
    "B": (
        (part.COLUMN_X / 2.0, abs(part.FRONT_COLUMN_Z) + _B49E1_BOSS_DIA / 2.0 + 6.0),
        (part.COLUMN_X / 2.0, part.INNER_Z - 6.0),
    ),
    "E": (
        (part.BAR_X1 + 6.0, drawing.SIDE_SECTION_Z),
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
        dx0, dy0, dx1, dy1 = drawing.SECTION_LETTER_EXTENTS[name[0]]
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
             drawing.SECTION_LETTER_TEXT_GAP),
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
def test_section_letter_stands_clear_of_its_ink(name: str) -> None:
    """#955: each cutting-plane letter clears the ink round it by
    INK_CLEARANCE; B's outer letter, centred in its 9.6 mm band, clears the
    rail edge and the 183.9's line by TEXT_CLEARANCE."""
    assert (
        _letter_shortfalls(drawing.section_cut_ends(), name, boss_dia=part.BOSS_DIA)
        == {}
    )


@pytest.mark.parametrize("name", ("B-outer", "B-inner", "E-inner", "E-outer", "D-inner"))
def test_b49e1_section_letter_is_what_sat_on_ink(name: str) -> None:
    """The same check on b49e1's ends fails for every letter #955 moves off
    ink.  D's outer letter was already 2.2 mm clear; its end only re-derives."""
    assert _letter_shortfalls(_B49E1_CUT_ENDS, name, boss_dia=_B49E1_BOSS_DIA)


def test_b_outer_arrow_keeps_off_the_window_width() -> None:
    """B's outer arrow runs in the same band: its head clears the 183.9's
    line and ends an ink clearance short of the value."""
    tail = _letter_tails(drawing.section_cut_ends())["B-outer"]
    line_y = _WINDOW_WIDTH_LINE[0][1] / 1000.0
    assert tail[1] - _SECTION_ARROW_HALF_WIDTH - line_y >= 0.001
    assert tail[0] + _SECTION_ARROW_LENGTH <= _WINDOW_WIDTH_TEXT[0] / 1000.0 - drawing.INK_CLEARANCE


def test_section_cuts_cross_the_same_stock() -> None:
    """The moved ends keep what each removed section shows: B cuts the
    rail's plain T between the junction land and the corner boss, E runs
    from outside the left rail past the crossbar T, D from outside the hub
    rail past its inner face, each at its own station."""
    ends = drawing.section_cut_ends()
    (bx, b_outer), (bx_inner, b_inner) = ends["B"]
    assert bx == bx_inner and part.LAND_X1 < bx < part.COLUMN_X - part.BOSS_DIA / 2.0
    assert b_inner < part.INNER_Z and b_outer > drawing.PLAN_HALF_Z
    (e_inner, ez), (e_outer, ez_outer) = ends["E"]
    assert ez == ez_outer == drawing.SIDE_SECTION_Z
    assert e_inner > part.BAR_X1 and e_outer < -drawing.PLAN_HALF_X
    (d_outer, dz), (d_inner, dz_inner) = ends["D"]
    assert dz == dz_inner == part.GOOSENECK_Z
    assert d_outer < -part.OUTER_X and -part.INNER_X < d_inner < part.BAR_X0


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
    drawing._pin_section_profile(None, view, (0.0, 0.0, 0.0), 0.3320, label="D-D")


def test_pin_section_profile_moves_the_view_by_the_miss(monkeypatch) -> None:
    view = _FakeView((0.3300, 0.2100))
    _pin(monkeypatch, view, (-0.0043, 0.0))
    assert view.Position == pytest.approx((0.3363, 0.2100))


def test_pin_section_profile_fails_loud_when_the_move_does_not_hold(monkeypatch) -> None:
    with pytest.raises(RuntimeError, match="D-D section profile prints at"):
        _pin(monkeypatch, _FakeView((0.3300, 0.2100), persists=False), (-0.0043, 0.0))


def test_build_pins_every_removed_section_and_writes_centrelines_direct() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for pinned in ("RAIL_SECTION_PROFILE_X, label=\"B-B\"", "SIDE_SECTION_PROFILE_X, label=\"E-E\"",
                   "HUB_SECTION_PROFILE_X, label=\"D-D\"",
                   "HANGER_SECTION_PROFILE_X, label=\"F-F\""):
        assert pinned in source, pinned
    body = source[source.index("def _add_view_centerlines(") :]
    body = body[: body.index("\ndef ")]
    assert "manager.AddToDB = True" in body
    assert "_assert_centreline_placed(adapter, segment, points)" in body


def test_build_cuts_each_section_at_its_derived_ends() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for placed in (
        'for x, z in cut_ends["B"]',
        'for x, z in cut_ends["E"]',
        'for x, z in section_cut_ends()["D"]',
    ):
        assert placed in source, placed


# --- Knife hanger: #6 SHCS counterbore + MHA-VN-051 dowel slip hole --------


def test_knife_hanger_is_a_6_shcs_counterbore_on_the_knife_line() -> None:
    import spring_mount_geom

    hole = spec.HANGER_HOLE_SPEC
    assert (hole.kind, hole.size, hole.end) == ("counterbore_socket", "#6", "through_all")
    assert hole.overrides_mm == {
        "HoleDiameter": spec.HANGER_CLEARANCE_DIA,
        "CounterBoreDiameter": spec.HANGER_CBORE_DIA,
        "CounterBoreDepth": spec.HANGER_CBORE_DEPTH,
    }
    assert spec.HANGER_CLEARANCE_DIA == pytest.approx(4.318)
    assert (spec.HANGER_CBORE_DIA, spec.HANGER_CBORE_DEPTH) == (7.0, 6.5)
    # The 1/2 hanger-stud clearance is gone, not aliased.
    assert not hasattr(part, "STUD_HOLE_SPEC") and not hasattr(part, "STUD_HOLE_DIA")
    # Both stations sit on the knife line, centred on the crossbar.
    assert part.HANGER_X == spring_mount_geom.KNIFE[0] == (part.BAR_X0 + part.BAR_X1) / 2.0
    assert drawing.HANGER_X == part.HANGER_X
    # The counterbore stays inside the junction material at the rear station.
    assert part.STUD_Z_REAR + spec.HANGER_CBORE_DIA / 2.0 < part.INNER_Z + part.GUSSET
    # Print-worst head checks (rule 12).
    assert spec.HANGER_CBORE_HEAD_CLEARANCE == pytest.approx(0.7496)
    assert spec.HANGER_HEAD_RECESS == pytest.approx(2.4848)
    assert spec.HANGER_HEAD_BEARING == pytest.approx(0.6612)


def test_counterbore_floor_is_the_screw_grip_at_one_place() -> None:
    assert spec.HANGER_GRIP == 30.0 == part.RING_HEIGHT - spec.HANGER_CBORE_DEPTH
    assert spec.HANGER_GRIP_PLACES == 1
    assert spec.HANGER_GRIP_TOL == float(
        str(_config.title_block("linear_1pl")["display"]).lstrip("\u00b1")
    )
    assert (
        spec.DRAWING_REFERENCE_PRECISION["hanger counterbore floor from underside"]
        == spec.HANGER_GRIP_PLACES
    )


def test_dowel_slip_hole_contract() -> None:
    assert part.PIN_HOLE_X == pytest.approx(-8.65)
    assert part.PIN_HOLE_X - part.HANGER_X == spec.HANGER_PIN_X == 6.35
    assert spec.HANGER_PIN_X_PLACES == 3
    assert spec.DRAWING_REFERENCE_PRECISION["dowel hole from hanger axis"] == 3
    assert (spec.HANGER_PIN_HOLE_DIA, spec.HANGER_PIN_HOLE_DIA_BAND) == (3.24, (0.03, -0.03))
    assert spec.HANGER_PIN_HOLE_DEPTH == 12.0
    assert spec.HANGER_PIN_SLIP_CLEARANCE_MIN == pytest.approx(0.02738)
    assert spec.HANGER_PIN_SLIP_CLEARANCE_MAX == pytest.approx(0.09246)
    assert 0.02 <= spec.HANGER_PIN_SLIP_CLEARANCE_MIN < spec.HANGER_PIN_SLIP_CLEARANCE_MAX <= 0.10
    # Rule 12 walls and floor, print-worst (the station at its .XXX limit).
    assert part.PIN_HOLE_BAR_WALL == pytest.approx(2.885)
    assert part.PIN_HOLE_SCREW_WALL == pytest.approx(2.376)
    assert part.PIN_HOLE_FLOOR_MARGIN == pytest.approx(18.0)
    assert spec.HANGER_PIN_HOLE_DEPTH < spec.HANGER_GRIP
    # The model owns the size, band and depth; the drawing imports them.
    assert spec.DRAWING_DIMENSIONS["HangerPinProfile"] == {"HangerPinHoleDia"}
    assert spec.DRAWING_DIMENSIONS["HangerPinHoles"] == {"HangerPinHoleDepth"}
    assert spec.DRAWING_PRECISION_BY_NAME["HangerPinHoleDia"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["HangerPinHoleDepth"] == 1
    assert set(drawing.HANGER_SECTION_KEEP) == {"HangerPinHoleDia", "HangerPinHoleDepth"}


def test_dowel_slot_contract() -> None:
    # The slot stands -X of each screw axis, the round hole +X: the knife
    # mount's two dowels at +/-6.350.
    assert part.SLOT_X == pytest.approx(-21.35)
    assert part.SLOT_X - part.HANGER_X == pytest.approx(spec.HANGER_SLOT_X)
    assert spec.HANGER_SLOT_X == -6.35
    assert spec.HANGER_PIN_XS == (spec.HANGER_SLOT_X, spec.HANGER_ROUND_X)
    # Slip width = the round hole's ream; length .XX; floor = the hole's.
    assert (spec.HANGER_SLOT_WIDTH, spec.HANGER_SLOT_WIDTH_BAND) == (3.24, (0.03, -0.03))
    assert (spec.HANGER_SLOT_LENGTH, spec.HANGER_SLOT_LENGTH_TOL) == (4.30, 0.51)
    assert spec.HANGER_SLOT_DEPTH == spec.HANGER_PIN_HOLE_DEPTH
    assert part.SLOT_FLAT == pytest.approx(1.06)
    # The slot stands BASIC 12.700 from its round hole; from the screw axis
    # it carries the round hole's .XXX band plus its zone radius.
    assert spec.HANGER_SLOT_FROM_ROUND == pytest.approx(12.7)
    assert spec.HANGER_SLOT_STATION_TOL == pytest.approx(0.155)
    # Rule 12 walls and floor, print-worst: the screw-side wall under the
    # 2.0 target, over the 1.5 floor.
    assert part.SLOT_BAR_WALL == pytest.approx(2.09)
    assert part.SLOT_SCREW_WALL == pytest.approx(1.581)
    assert part.SLOT_SCREW_WALL >= 1.5
    assert part.SLOT_FLOOR_MARGIN == pytest.approx(18.0)
    # The model owns the width and its band (front slot, on the underside
    # locator); F-F derives the station and the length.
    assert spec.DRAWING_DIMENSIONS["HangerSlotProfile"] == {"HangerSlotWidth"}
    assert spec.DRAWING_PRECISION_BY_NAME["HangerSlotWidth"] == 3
    assert "dowel slot from hanger axis" not in spec.DRAWING_REFERENCE_PRECISION
    assert spec.DRAWING_REFERENCE_PRECISION["dowel slot from dowel hole"] == 3
    assert spec.DRAWING_REFERENCE_PRECISION["dowel slot length"] == 2
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'for slot_width_name in ("HangerSlotWidth", "HangerSlot1Width"):' in source
    assert 'prefix = "HangerSlot" if station == "Front" else "HangerSlot1"' in source


def test_dowel_slot_sketch_contours_never_cross() -> None:
    # 48ad988c6 cut each slot's ends as two Ø3.24 circles 1.36 apart in one
    # sketch; they cross, and the farm leaf's cut failed (FeatureCut3 "Type
    # mismatch").  Each slot is now one closed stadium, the two apart.
    w, flat = spec.HANGER_SLOT_WIDTH, part.SLOT_FLAT
    end_circles = tuple(
        ((part.SLOT_X + side * flat / 2, z), (part.SLOT_X + side * flat / 2, z), w / 2)
        for z in (part.STUD_Z_FRONT, part.STUD_Z_REAR)
        for side in (-1.0, 1.0)
    )
    assert not part.swept_contours_disjoint(end_circles)
    assert len(part.HANGER_SLOT_CONTOURS) == 2
    assert part.swept_contours_disjoint(part.HANGER_SLOT_CONTOURS)
    assert part.swept_contours_disjoint(part.HANGER_PIN_CONTOURS)
    # The checker separates by the swept radii, so touching is a failure.
    assert not part.swept_contours_disjoint((((0, 0), (1, 0), 1.0), ((1, 2), (3, 2), 1.0)))
    assert part.swept_contours_disjoint((((0, 0), (1, 0), 1.0), ((1, 2.001), (3, 2.001), 1.0)))
    assert part.HANGER_SLOT_AREA == pytest.approx(flat * w + math.pi * (w / 2) ** 2)
    source = Path(part.__file__).read_text(encoding="utf-8")
    step = source[source.index("    # 12c. Dowel slots") : source.index("    # 13. Cross-screw")]
    assert "define_circle" not in step
    assert step.count("create_cut_extrude(") == 1
    assert step.count("await adapter.add_arc(") == 2
    assert step.count("await adapter.add_line(") == 2


@pytest.mark.parametrize("along_u", [True, False])
def test_dowel_slot_stadium_closes_counter_clockwise(along_u: bool) -> None:
    centre, half_flat, half_w = (5.0, -7.0), part.SLOT_FLAT / 2, spec.HANGER_SLOT_WIDTH / 2
    p1, p2, p3, p4, c_b, c_a = part.slot_stadium_points(
        centre, along_u=along_u, half_flat=half_flat, half_w=half_w
    )
    # Straight sides of the flat run, each end a half round about its centre.
    assert math.dist(p1, p2) == pytest.approx(2 * half_flat)
    assert math.dist(p3, p4) == pytest.approx(2 * half_flat)
    assert math.dist(c_a, c_b) == pytest.approx(2 * half_flat)
    for c, a, b in ((c_b, p2, p3), (c_a, p4, p1)):
        assert math.dist(c, a) == pytest.approx(half_w)
        assert math.dist(c, b) == pytest.approx(half_w)
        # add_arc sweeps counter-clockwise from a to b: the half round
        # bulges away from the slot's centre.
        sweep_mid = (c[0] + (b[1] - a[1]) / 2, c[1] - (b[0] - a[0]) / 2)
        assert math.dist(sweep_mid, centre) == pytest.approx(half_flat + half_w)
    # The sides run along the slot (u when along_u), counter-clockwise.
    axis = 0 if along_u else 1
    assert p1[1 - axis] == pytest.approx(p2[1 - axis])
    area2 = sum(
        x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip((p1, p2, p3, p4), (p2, p3, p4, p1))
    )
    assert area2 > 0


def test_slots_are_positioned_to_the_round_holes_with_translation() -> None:
    # Policy rule 3 (knife-edge system): datum B the front round hole, C the
    # rear; each slot 0.05 to its own station's hole, the other translated.
    assert spec.GEOMETRIC_TOLERANCES_MM == {"knife-hanger slot position": "0.05"}
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    underside = source[source.index('ddoc.ActivateSheet("UNDERSIDE")') :]
    assert underside.count("add_datum_feature(") == 1
    assert '(("B", STUD_Z_FRONT), ("C", STUD_Z_REAR))' in underside
    assert underside.count("add_feature_control_frame(") == 1
    assert '("front", STUD_Z_FRONT, ("B", "C"))' in underside
    assert '("rear", STUD_Z_REAR, ("C", "B"))' in underside
    assert "translated=datums[1:]" in underside
    assert 'GEOMETRIC_TOLERANCES_MM["knife-hanger slot position"]' in underside
    assert '"HangerSlotWidth": HANGER_SLOT_WIDTH_TEXT_XY' in underside
    for name, (x, y) in {
        **drawing.HANGER_DATUM_SYMBOL_XY,
        **drawing.HANGER_SLOT_FRAME_XY,
        "slot width": drawing.HANGER_SLOT_WIDTH_TEXT_XY,
        "slot width offset": drawing.HANGER_SLOT_WIDTH_OFFSET_XY,
    }.items():
        assert 0.013 < x < TITLE_BLOCK[0] and 0.125 < y < 0.270, name


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
    assert "edge_xy=datum_pick, expected_entity=round_hole," in loop
    assert "edge_entity" not in loop
    # The zoom window holds the whole rim and the pick is ON it, facing the tag.
    radius = drawing.HANGER_PIN_HOLE_DIA / 2.0 * drawing._HUB_BOTTOM_M_PER_MM
    assert radius < drawing.HANGER_DATUM_PICK_ZOOM_HALF / 2.0
    for datum, (x, y) in drawing.HANGER_DATUM_SYMBOL_XY.items():
        centre = (0.107, 0.172 if datum == "B" else 0.230)
        pick = drawing.hanger_datum_pick(centre, (x, y))
        assert math.dist(pick, centre) == pytest.approx(radius), datum
        to_pick = (pick[0] - centre[0], pick[1] - centre[1])
        to_tag = (x - centre[0], y - centre[1])
        assert to_pick[0] * to_tag[1] - to_pick[1] * to_tag[0] == pytest.approx(0.0, abs=1e-12)
        assert to_pick[0] * to_tag[0] + to_pick[1] * to_tag[1] > 0.0, datum


def test_hanger_datum_leaders_run_clear_of_the_slot_frames() -> None:
    # Farm run 20261009T171439353Z: datum B's leader, rim (107.5, 172.4) to
    # its tag at (122.0, 185.0) mm, ran 7.88 mm through the front slot
    # frame's text [78.9, 179.1]..[128.6, 184.2] mm (leader-through-text).
    from _layout_geometry import Box, Segment, segment_box_overlap_length

    x0, y0, x1, y1 = drawing.HANGER_SLOT_FRAME_TEXT_BOX
    frames = {
        station: Box(fx + x0, fy + y0, fx + x1, fy + y1)
        for station, (fx, fy) in drawing.HANGER_SLOT_FRAME_XY.items()
    }
    front = frames["front"]
    assert (front.xmin, front.ymin, front.xmax, front.ymax) == pytest.approx(
        (0.0789, 0.1797, 0.1105, 0.1842)
    )
    centre = drawing.HUB_BOTTOM_CENTER
    m_per_mm = drawing._HUB_BOTTOM_M_PER_MM
    for datum, station_z in (("B", part.STUD_Z_FRONT), ("C", part.STUD_Z_REAR)):
        hole = (
            centre[0] + part.PIN_HOLE_X * m_per_mm,
            centre[1] + station_z * m_per_mm,
        )
        tag = drawing.HANGER_DATUM_SYMBOL_XY[datum]
        leader = Segment(*drawing.hanger_datum_pick(hole, tag), *tag)
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
    # The tag stays in the window right of the crossbar, above the front
    # rail's inner face.
    bx, by = drawing.HANGER_DATUM_SYMBOL_XY["B"]
    assert bx > centre[0] + part.BAR_X1 * m_per_mm
    assert by > centre[1] - part.INNER_Z * m_per_mm


def test_rear_slot_frame_stands_clear_of_section_f_f() -> None:
    # Farm run 20261009T174542021Z: the rear frame at (78, 218) mm printed
    # its text [78.9, 212.1]..[128.6, 217.2] under both F labels and F-F's
    # left arrow (text-clearance 3.87 mm short of 1.78 mm air; text-on-line
    # 3.05 mm), which REPORT mode on fr-top-frame does not enforce.
    from _layout_geometry import Box, Segment, segment_box_distance

    centre, m_per_mm = drawing.HUB_BOTTOM_CENTER, drawing._HUB_BOTTOM_M_PER_MM
    cut_y = centre[1] + drawing.HANGER_SECTION_Z * m_per_mm
    arrows = [centre[0] + x * m_per_mm for x in drawing.HANGER_SECTION_CUT_X]
    # Each F-F arrow runs 12 mm sheet-down from the cutting line; its letter
    # prints [-1.2, +1.8] x [-20.25, -14.15] mm about the line's end (run
    # 20261009T174542021Z: arrows x 91.33 / 118.67 from y 230.05, letters
    # [90.1, 209.8]..[93.1, 215.9] and [117.4, 209.8]..[120.4, 215.9]).
    assert arrows == pytest.approx([0.09133, 0.11867], abs=5e-5)
    assert cut_y == pytest.approx(0.23005, abs=5e-5)
    section_ink: dict[str, Box | Segment] = {
        "cutting line": Segment(arrows[0], cut_y, arrows[1], cut_y),
    }
    for side, x in zip(("left", "right"), arrows):
        section_ink[f"{side} arrow"] = Segment(x, cut_y, x, cut_y - 0.012)
        section_ink[f"{side} F"] = Box(
            x - 0.0012, cut_y - 0.02025, x + 0.0018, cut_y - 0.01415
        )
    fx, fy = drawing.HANGER_SLOT_FRAME_XY["rear"]
    ox0, oy0, ox1, oy1 = drawing.HANGER_SLOT_FRAME_OUTLINE
    outline = Box(fx + ox0, fy + oy0, fx + ox1, fy + oy1)
    # The leader: the shoulder off the outline's left end at mid height, then
    # to the outer end of the rear slot (its arc's bottom, under the line).
    knee = (outline.xmin - drawing.HANGER_SLOT_FRAME_SHOULDER, (outline.ymin + outline.ymax) / 2)
    slot_end = (
        centre[0] + (part.SLOT_X - part.SLOT_FLAT / 2) * m_per_mm,
        centre[1] + (part.STUD_Z_REAR - drawing.HANGER_SLOT_WIDTH / 2) * m_per_mm,
    )
    leader = [
        Segment(outline.xmin, knee[1], *knee),
        Segment(*knee, *slot_end),
    ]
    for name, ink in section_ink.items():
        if isinstance(ink, Box):
            gap = max(
                ink.ymin - outline.ymax, outline.ymin - ink.ymax,
                ink.xmin - outline.xmax, outline.xmin - ink.xmax,
            )
            # The audit asked for 1.78 mm of air between the two texts.
            assert gap >= 0.00178, name
            for run in leader:
                assert segment_box_distance(run, ink) >= 0.00178, name
        else:
            assert segment_box_distance(ink, outline) >= 0.00178, name
            for run in leader:
                assert _segments_apart(run, ink), name
    # The frame stays in the window right of the crossbar, its leader's knee
    # right of the crossbar's edge, and its print inside the rail.
    bar_right = centre[0] + part.BAR_X1 * m_per_mm
    assert knee[0] > bar_right
    assert outline.xmax < centre[0] + part.INNER_X * m_per_mm
    assert outline.ymin > max(drawing.HANGER_SLOT_FRAME_XY["front"][1], drawing.HANGER_DATUM_SYMBOL_XY["B"][1] + 0.007)


def _segments_apart(a, b) -> bool:
    """True when two segments neither cross nor touch."""

    def side(p, q, r) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    a0, a1, b0, b1 = (a.x0, a.y0), (a.x1, a.y1), (b.x0, b.y0), (b.x1, b.y1)
    return side(a0, a1, b0) * side(a0, a1, b1) > 0 or side(b0, b1, a0) * side(b0, b1, a1) > 0


def test_slip_hole_callout_states_process_and_purpose_briefly() -> None:
    text = spec.HANGER_PIN_HOLE_CALLOUT
    assert text.startswith("2X ") and "REAM" in text and "MHA-VN-051" in text
    assert "BLIND" in text and "FLAT-BOTTOM" in text
    # Rule 6: short notes.
    assert len(text.splitlines()) <= 2
    assert max(len(line) for line in text.splitlines()) <= 26
    assert drawing.HANGER_SECTION_CALLOUTS["HangerPinHoleDia"] == text


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
    points = {
        "floor": drawing.HANGER_FLOOR_TEXT_XY,
        "floor offset": drawing.HANGER_FLOOR_OFFSET_XY,
        "station": drawing.PIN_STATION_TEXT_XY,
        "station offset": drawing.PIN_STATION_OFFSET_XY,
        "slot station": drawing.SLOT_STATION_TEXT_XY,
        "slot station offset": drawing.SLOT_STATION_OFFSET_XY,
        "slot length": drawing.SLOT_LENGTH_TEXT_XY,
        "slot length offset": drawing.SLOT_LENGTH_OFFSET_XY,
        "caption": drawing.HANGER_SECTION_CAPTION_XY,
        "slip-hole callout": drawing.HANGER_PIN_DIA_OFFSET_XY,
        **drawing.HANGER_SECTION_KEEP,
    }
    for name, (x, y) in points.items():
        assert 0.013 < x < TITLE_BLOCK[0] and 0.013 < y < 0.150, name
    # The station reads above the profile, the slip-hole size below it.
    top = drawing._hanger_section_xy(part.HANGER_X, part.HALF_H)[1]
    bottom = drawing._hanger_section_xy(part.HANGER_X, -part.HALF_H)[1]
    assert drawing.PIN_STATION_TEXT_XY[1] > top
    assert drawing.HANGER_SECTION_KEEP["HangerPinHoleDia"][1] < bottom
    # The slot's BASIC row stands above the hole's station row, so the two
    # dimension lines never meet on the round hole's extension line.
    assert drawing.SLOT_STATION_TEXT_XY[1] > drawing.PIN_STATION_TEXT_XY[1] + 0.004


def test_slot_station_is_basic_from_its_round_hole() -> None:
    # Machinist review (sheet 6): the slot position frames lacked a basic
    # location.  The slot now stands BASIC 12.700 from the round hole beside
    # it (datum B front, C rear), a bare box: its above-text did not print
    # (20261010T001553082Z layout audit, text-unmatched).
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    section = source[source.index("def _hanger_section(") : source.index("def _hub_underside_detail(")]
    assert "2X DOWEL SLOT\\nFROM SCREW AXIS" not in section
    assert "p0=(SLOT_X, -HALF_H-2.0, z), p1=(PIN_HOLE_X, -HALF_H-2.0, z)" in section
    assert "entities=(axes[2], axes[1])" in section
    assert "expected_mm=HANGER_SLOT_FROM_ROUND" in section
    assert 'set_basic_dimension(adapter, slot_station, label="dowel slot from dowel hole")' in section
    assert "FROM DOWEL HOLE" not in section
    assert 'location="above"' not in section
    assert spec.HANGER_SLOT_FROM_ROUND == pytest.approx(spec.HANGER_ROUND_X - spec.HANGER_SLOT_X)


def test_slip_hole_callout_is_parked_clear_of_the_section() -> None:
    # Rule 8 (dda9a33a8 render): the four-line callout stood across the hole's
    # own extension lines and the underside edge.  It now rides a leader to a
    # block wholly below the section, right of the size's extension lines and
    # left of the title block.
    half_w, half_h = 0.0325, 0.0095  # 65 x 19 mm block on that render
    x, y = drawing.HANGER_PIN_DIA_OFFSET_XY
    bottom = drawing._hanger_section_xy(part.HANGER_X, -part.HALF_H)[1]
    hole_right = drawing._hanger_section_xy(
        part.PIN_HOLE_X + spec.HANGER_PIN_HOLE_DIA / 2.0, 0.0
    )[0]
    assert y + half_h < bottom - 0.010
    assert x - half_w > hole_right + 0.010
    assert x + half_w < TITLE_BLOCK[0] - 0.005
    assert y - half_h > 0.0127 + 0.005
    # Clear of the caption, which stands left of the section.
    assert x - half_w > drawing.HANGER_SECTION_CAPTION_XY[0] + 0.025
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '{"HangerPinHoleDia": HANGER_PIN_DIA_OFFSET_XY}' in source, (
        "the slip-hole size must be offset onto its leader"
    )


def test_build_places_the_hanger_section_on_the_underside_sheet() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    underside = source[source.index('ddoc.ActivateSheet("UNDERSIDE")') :]
    assert "_hanger_section(adapter, hub_bottom_parent)" in underside
    assert "imported_annotations += hanger_dimensions" in underside


def test_keeper_transfer_prefix_preserves_the_native_hole_definition() -> None:
    import ast
    import _drawing_common

    native = "<hw-threaddesc>\n<hw-threaddepth>\n<hw-tapdrldia> <hw-tapdrldepth>"
    assert (
        _drawing_common.compose_hole_callout_prefix(
            drawing.TRANSFER_KEEPER_CALLOUT,
            native,
        )
        == "TRANSFER FROM MHA-CH-007\nAT ASSEMBLY;\n" + native
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
    helper_tree = ast.parse(Path(_drawing_common.__file__).read_text(encoding="utf-8"))
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
    assert spec.KEEPER_TAP_CALLOUT_PRECISION == {
        "hw-tapdrldia": 2,
        "hw-tapdrldepth": 1,
        "hw-threaddepth": 1,
    }


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
    assert len(captured) == 6
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
            "hanger x from left sockets",
            "2X HANGER X",
            (0.162, 0.240),
            part.COLUMN_X + environment["hanger_x"],
        ),
        (
            "front hanger z from upper sockets",
            "FRONT HANGER Z",
            (0.062, 0.209),
            part.STUD_Z_FRONT - part.FRONT_COLUMN_Z,
        ),
        (
            "rear hanger z from upper sockets",
            "REAR HANGER Z",
            (0.040, 0.165),
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


def test_transfer_plan_and_station_fields_remain_inside_the_hole_sheet() -> None:
    import ast

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
    stations = eval(
        compile(ast.Expression(loop.iter), "<station-fields>", "eval"), environment
    )
    assert len(stations) == 6
    hole, hole_r, boss, boss_r = _keeper_geometry()
    callout, _tip = drawing.keeper_callout_placement(hole, hole_r, boss, boss_r)
    left, down, right, up = drawing.KEEPER_CALLOUT_EXTENT
    callout_box = (
        callout[0] - left,
        callout[1] - down,
        callout[0] + right,
        callout[1] + up,
    )
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


# --- Round 3: two machined keeper foot seats on the west top flange --------


def test_keeper_seat_note_is_the_part_property_carrying_the_keeper_budget() -> None:
    import ast

    budget = keeper.KEEPER_SEAT_FLATNESS_BUDGET_MM
    assert budget == 0.04
    # The frame imports the keeper's budget; the keeper never imports the frame.
    assert spec.KEEPER_SEAT_FLATNESS_BUDGET_MM is budget
    assert "fr_top_frame_spec" not in Path(keeper.__file__).read_text(encoding="utf-8")
    lines = spec.DRAWING_NOTES_B.splitlines()
    assert len(lines) == 4
    assert lines[0] == "FACE BOTH KEEPER SEATS IN ONE SETUP."
    assert f"WITHIN ONE COMMON {budget:.2f} FLATNESS ZONE" in lines[1]
    assert "SIZE TO ACTUAL KEEPER CONTACT" in lines[2]
    assert f"PLUS {spec.KEEPER_SEAT_EDGE_MARGIN_MM:.2f} EACH EDGE" in lines[2]
    assert lines[3] == "KEEPER LOCATING SEATS: Ra 3.2 UM."
    builder = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Manufacturing Notes B": DRAWING_NOTES_B' in builder
    # The keeper sheet links the property; its own executable strings never
    # retype it. Historical comments about other sheets' Ra leaders are not
    # another keeper-seat requirement.
    sheet, _build = _keeper_sheet_tree()
    strings = [
        node.value
        for node in ast.walk(sheet)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    assert "Manufacturing Notes B" in strings
    for forbidden in ("FLATNESS ZONE", "IN ONE SETUP", "LOCATING SEATS", "Ra 3.2"):
        assert not any(forbidden in value for value in strings)


def test_keeper_seats_are_the_nominal_contacts_plus_their_edge_margin() -> None:
    margin = spec.KEEPER_SEAT_EDGE_MARGIN_MM
    assert margin == 0.10
    assert keeper.KEEPER_SEAT_LENGTH_MM == pytest.approx(16.5)
    assert keeper.KEEPER_SEAT_LENGTH_MM == pytest.approx(
        2.0 * keeper.LUG_HALF_T + keeper.FOOT_L
    )
    assert spec.KEEPER_SEAT_WIDTH_MM == pytest.approx(
        keeper.KEEPER_WIDTH + 2.0 * margin
    )
    assert spec.KEEPER_SEAT_WIDTH_MM == pytest.approx(14.2)
    assert spec.KEEPER_SEAT_LENGTH_MM == pytest.approx(
        keeper.KEEPER_SEAT_LENGTH_MM + 2.0 * margin
    )
    assert spec.KEEPER_SEAT_LENGTH_MM == pytest.approx(16.7)
    assert [value for centre in spec.KEEPER_SEAT_CENTRES_XZ for value in centre] == (
        pytest.approx([199.9, -79.75391221957346, 199.9, 78.74608778042654])
    )
    drill_r = part.TAP_DRILL_MM[part.KEEPER_TAP_SPEC.size] / 2.0
    for (x, z), (x0, x1, z0, z1), tap_z, tip_z, side in zip(
        spec.KEEPER_SEAT_CENTRES_XZ,
        spec.KEEPER_SEAT_BOUNDS_XZ,
        (part.KEEPER_TAP_Z_FRONT, part.KEEPER_TAP_Z_REAR),
        (part.KEEPER_FOOT_TIP_Z_FRONT, part.KEEPER_FOOT_TIP_Z_REAR),
        (-1.0, 1.0),
    ):
        assert x == pytest.approx(part.KEEPER_TAP_X)
        assert x == pytest.approx(part.COLUMN_X + keeper.KEEPER_FITUP_X_FROM_WEB_MM)
        assert (x1 - x0, z1 - z0) == pytest.approx(
            (spec.KEEPER_SEAT_WIDTH_MM, spec.KEEPER_SEAT_LENGTH_MM)
        )
        assert ((x0 + x1) / 2.0, (z0 + z1) / 2.0) == pytest.approx((x, z))
        # The contact runs from the foot tip outboard to the lug's inner face
        # inboard; each split line stands one margin outside it.
        inner_face = keeper.FULCRUM_KEEPER_CENTRE_Z + side * (
            keeper.KEEPER_Z_OFF - keeper.LUG_HALF_T
        )
        outboard, inboard = (z0, z1) if side < 0 else (z1, z0)
        assert outboard == pytest.approx(tip_z + side * margin)
        assert inboard == pytest.approx(inner_face - side * margin)
        # The keeper tap opens wholly inside its seat.
        assert x0 + drill_r < part.KEEPER_TAP_X < x1 - drill_r
        assert z0 + drill_r < tap_z < z1 - drill_r
        # On the flat flange top: inside both chamfered rims, off the boss.
        assert part.INNER_X + part.EDGE_CHAMFER < x0
        assert x1 < part.OUTER_X - part.EDGE_CHAMFER
        boss_z = part.FRONT_COLUMN_Z if side < 0 else part.REAR_COLUMN_Z
        nearest = (min(max(part.COLUMN_X, x0), x1), min(max(boss_z, z0), z1))
        assert math.dist(nearest, (part.COLUMN_X, boss_z)) > part.BOSS_DIA / 2.0


def test_keeper_seat_flange_thickness_is_the_final_top_flange_under_each_seat() -> None:
    places = spec.DRAWING_REFERENCE_PRECISION
    # One places constant: the seat's controlling dimension is the top
    # flange's own .X, not a second tolerance stacked from the cap floors.
    assert places["keeper seat flange thickness"] == places["top flange thickness"]
    assert places["keeper seat flange thickness"] == spec.FLANGE_THICKNESS_PLACES == 1
    assert spec.FLANGE_THICKNESS_MM == part.FLANGE == 8.0
    assert part.HALF_H - part.FLANGE_BOT_Y == pytest.approx(spec.FLANGE_THICKNESS_MM)
    flange_places = places["keeper seat flange thickness"]
    assert f"{spec.FLANGE_THICKNESS_MM:.{flange_places}f}" == "8.0"
    assert places["keeper seat width"] == places["keeper seat length"] == 1
    # The cap-floor height is gone from the contract and the sheet alike.
    assert "keeper seat height above cap floors" not in places
    assert not hasattr(spec, "KEEPER_SEAT_HEIGHT_MM")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for retired in (
        "KEEPER_SEAT_HEIGHT_MM",
        "keeper seat height above cap floors",
        "ABOVE CAP SEAT FLOOR",
        "KEEPER_HEIGHT_",
        "KEEPER_BORE_HALF_CHORD",
        "KEEPER_RECESS_HALF_CHORD",
        "KEEPER_SECTION_SOCKET_XY",
    ):
        assert retired not in source, retired


def test_keeper_seats_leave_the_web_ligaments_and_boss_clearances_unchanged() -> None:
    import ast

    assert part.WEB_T == 13.0
    assert (part.WEB_IN_X, part.WEB_OUT_X) == pytest.approx((190.5, 203.5))
    assert (part.HALF_H, part.FLANGE, part.FLANGE_BOT_Y) == pytest.approx(
        (18.25, 8.0, 10.25)
    )
    assert part.KEEPER_TAP_THREAD_WALL_MARGIN == pytest.approx(1.6241775880068343)
    assert part.KEEPER_TAP_DRILL_WALL_MARGIN == pytest.approx(1.645596762049888)
    assert part.KEEPER_FOOT_BOSS_MARGINS == pytest.approx((1.496, 2.504), abs=0.0005)
    assert part.KEEPER_FOOT_PRINTED_BOSS_MARGINS == pytest.approx((0.150, 0.640))
    assert part.KEEPER_FOOT_RAIL_MARGINS == pytest.approx((4.996, 6.004), abs=0.0005)
    assert part.KEEPER_SEAT_PRINTED_BOSS_MARGINS == pytest.approx(
        (0.05, 0.54), abs=0.0005
    )
    assert part.KEEPER_SEAT_PRINTED_FLANGE_SIDE_MARGIN == pytest.approx(6.28, abs=0.005)
    chamfer_places = spec.DRAWING_REFERENCE_PRECISION["top rim chamfer"]
    max_chamfer = (
        round(part.EDGE_CHAMFER, chamfer_places)
        + spec.PRINTED_LINEAR_BAND_MM[chamfer_places]
    )
    assert max_chamfer == pytest.approx(2.8)
    assert part.KEEPER_SEAT_PRINTED_FLAT_TOP_SIDE_MARGIN == pytest.approx(
        part.KEEPER_SEAT_PRINTED_FLANGE_SIDE_MARGIN - max_chamfer
    )
    assert part.KEEPER_SEAT_PRINTED_FLAT_TOP_SIDE_MARGIN == pytest.approx(3.48)
    # Faced in place: the rail-top plane stays put, and the print bounds the
    # final flange left under each seat instead of a height over cap floors.
    assert part.HALF_H - part.FLANGE_BOT_Y == pytest.approx(spec.FLANGE_THICKNESS_MM)
    # The nine native socket, cap and hub finishes stand unchanged.
    assert [c.key for c in spec.SURFACE_FINISHES] == [
        f"{kind}_{rail}_{end}"
        for rail in ("east", "west")
        for end in ("front", "rear")
        for kind in ("socket", "cap_seat")
    ] + ["hub_bore"]
    # The seats' locating finish is SEAT_UM, carried by the part's linked
    # note B (no native symbol can pick a split region of a shared plane).
    assert SEAT_UM == 3.2
    assert spec.SEAT_UM is SEAT_UM
    assert (
        spec.DRAWING_NOTES_B.splitlines().count(
            f"KEEPER LOCATING SEATS: Ra {SEAT_UM:.1f} UM."
        )
        == 1
    )
    tree = ast.parse(Path(spec.__file__).read_text(encoding="utf-8"))
    (notes,) = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and [ast.unparse(target) for target in node.targets] == ["DRAWING_NOTES_B"]
    ]
    sourced = [
        value.value.id
        for value in ast.walk(notes)
        if isinstance(value, ast.FormattedValue) and isinstance(value.value, ast.Name)
    ]
    assert "SEAT_UM" in sourced


def test_keeper_seats_get_their_own_half_size_sheet() -> None:
    assert drawing.SHEET_NAMES == (
        "PICTORIAL",
        "GEOMETRY",
        "HOLES-SOCKETS",
        "CROSS-TAPS",
        "HUB-SET-SCREW",
        "UNDERSIDE",
        "KEEPER-SEATS",
    )
    assert set(drawing.SHEET_SCALES) == set(drawing.SHEET_NAMES)
    assert drawing.KEEPER_PLAN_SCALE == drawing.SHEET_SCALES["KEEPER-SEATS"]
    assert drawing.KEEPER_PLAN_SCALE == drawing.SHEET_SCALES["HOLES-SOCKETS"]
    assert drawing.KEEPER_PLAN_SCALE == (1.0, 2.0)
    assert drawing.KEEPER_SECTION_SCALE == drawing.HUB_SECTION_SCALE == (1, 1)


# Estimated text allowances, not measured render ink: 2 mm per character as
# the station fields, 5.1 mm rows as the transfer rows, and a dimension field
# one row deeper than its text (its position is its text's bottom centre).
# Notes and the caption use the conservative 3.5 mm full-em width; both are
# anchored at their upper-left.  Farm validation measures the actual ink.
_KEEPER_CHAR = 0.002
_KEEPER_ROW = drawing.KEEPER_TRANSFER_ROW_PITCH
_KEEPER_NOTE_CHAR = drawing.KEEPER_TRANSFER_CHARACTER_WIDTH


def _keeper_plan(x, z):
    cx, cy = drawing.KEEPER_PLAN_CENTER
    s = drawing.KEEPER_PLAN_VIEW_SCALE / 1000.0
    return (cx + x * s, cy - z * s)


def _keeper_section(z, y):
    """G-G: +Z right and +Y up, the front seat's faced centre at its pinned point."""
    sx, sy = drawing.KEEPER_SECTION_SEAT_XY
    s = drawing.KEEPER_SECTION_VIEW_SCALE / 1000.0
    seat_z = spec.KEEPER_SEAT_CENTRES_XZ[0][1]
    return (sx + (z - seat_z) * s, sy + (y - part.HALF_H) * s)


def _dimension_field(xy, value, qualifier):
    rows = [value, *qualifier.splitlines()]
    half = max(map(len, rows)) * _KEEPER_CHAR / 2.0
    return (
        xy[0] - half,
        xy[1] - _KEEPER_ROW,
        xy[0] + half,
        xy[1] + len(rows) * _KEEPER_ROW,
    )


def _note_box(xy, text):
    rows = text.splitlines()
    width = max(map(len, rows)) * _KEEPER_NOTE_CHAR
    return (xy[0], xy[1] - len(rows) * _KEEPER_ROW, xy[0] + width, xy[1])


def _keeper_cut_half_chord(diameter):
    offset = drawing.KEEPER_SECTION_X - part.COLUMN_X
    return math.sqrt((diameter / 2.0) ** 2 - offset**2)


def _keeper_sheet_boxes():
    left, bottom = _keeper_plan(-drawing.PLAN_HALF_X, drawing.PLAN_HALF_Z)
    right, top = _keeper_plan(drawing.PLAN_HALF_X, -drawing.PLAN_HALF_Z)
    boss_half = _keeper_cut_half_chord(part.BOSS_DIA)
    end_z = drawing.keeper_section_cut_ends()[1][1]
    section_low = _keeper_section(
        part.FRONT_COLUMN_Z - boss_half, -(part.HALF_H + part.BOSS_BELOW)
    )
    section_high = _keeper_section(end_z, part.HALF_H + part.BOSS_ABOVE)
    boxes = {
        "plan": (left, bottom, right, top),
        "G-G": (*section_low, *section_high),
        "length text": _dimension_field(
            drawing.KEEPER_LENGTH_TEXT_XY, "(16.7)", drawing.KEEPER_SEAT_QUALIFIER
        ),
        "width text": _dimension_field(
            drawing.KEEPER_WIDTH_TEXT_XY, "(14.2)", drawing.KEEPER_SEAT_QUALIFIER
        ),
        "end text": _dimension_field(
            drawing.KEEPER_END_TEXT_XY, "(24.9)", drawing.KEEPER_SOCKET_QUALIFIER
        ),
        "inner text": _dimension_field(
            drawing.KEEPER_INNER_TEXT_XY, "(4.2)", drawing.KEEPER_SOCKET_QUALIFIER
        ),
        "flange text": _dimension_field(
            drawing.KEEPER_FLANGE_TEXT_XY, "8.0", drawing.KEEPER_FLANGE_QUALIFIER
        ),
        "caption": _note_box(
            drawing.KEEPER_SECTION_CAPTION_XY, "SECTION G-G\nSCALE 1:1"
        ),
        "notes B": _note_box(drawing.KEEPER_SEAT_NOTE_XY, spec.DRAWING_NOTES_B),
    }
    e0, e_down, e1, e_up = drawing.KEEPER_SECTION_LETTER_EXTENT
    for end, (x, z) in zip(("start", "end"), drawing.keeper_section_cut_ends()):
        tx, ty = _keeper_plan(x, z)
        boxes[f"G {end} letter"] = (tx + e0, ty + e_down, tx + e1, ty + e_up)
    return boxes


def test_keeper_seat_sheet_fits_inside_the_border_clear_of_the_title_block() -> None:
    boxes = _keeper_sheet_boxes()
    frame = drawing.SHEET_FRAME
    ink = drawing.INK_CLEARANCE
    for name, box in boxes.items():
        assert frame[0] + ink <= box[0] < box[2] <= frame[2] - ink, name
        assert frame[1] + ink <= box[1] < box[3] <= frame[3] - ink, name
        assert _box_box_gap(box, TITLE_BLOCK) >= ink, name
    names = sorted(boxes)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            assert _box_box_gap(boxes[a], boxes[b]) >= ink, (a, b)


def test_keeper_footprint_dimension_lines_stand_off_their_ink() -> None:
    boxes = _keeper_sheet_boxes()
    ink = drawing.INK_CLEARANCE
    x0, x1, z0, z1 = spec.KEEPER_SEAT_BOUNDS_XZ[1]
    # Length: a vertical line past the plan's right edge, between the seat's
    # two Z split lines, its witnesses running right off them.
    line_x, line_y = drawing.KEEPER_LENGTH_LINE_XY
    assert line_x - boxes["plan"][2] >= ink
    assert _keeper_plan(x0, z1)[1] < line_y < _keeper_plan(x0, z0)[1]
    length_line = ((line_x, _keeper_plan(x0, z1)[1]), (line_x, _keeper_plan(x0, z0)[1]))
    # Width: a horizontal line inside the rail band over the near split line.
    width_x, width_y = drawing.KEEPER_WIDTH_LINE_XY
    assert _keeper_plan(x0, 0.0)[0] < width_x < _keeper_plan(x1, 0.0)[0]
    assert width_y - _keeper_plan(x0, z0)[1] == pytest.approx(
        drawing.KEEPER_DIM_LINE_GAP
    )
    rim_x = (part.INNER_X + part.EDGE_CHAMFER, part.OUTER_X - part.EDGE_CHAMFER)
    assert rim_x[0] < x0 and x1 < rim_x[1]
    width_line = (_keeper_plan(x0, z0), _keeper_plan(x1, z0))
    width_line = tuple((x, width_y) for x, _y in width_line)
    for name in ("length text", "width text", "G start letter", "G end letter"):
        for line in (length_line, width_line):
            assert _box_segment_gap(boxes[name], line) >= ink, name
    # Each value sits right of its line, outside the plan, a gap off it.
    assert boxes["length text"][0] - line_x >= ink


def _keeper_dimension_lines():
    """Every plan dimension line on the sheet, as sheet segments."""
    x0, x1, z0, z1 = spec.KEEPER_SEAT_BOUNDS_XZ[1]
    length_x = drawing.KEEPER_LENGTH_LINE_XY[0]
    width_y = drawing.KEEPER_WIDTH_LINE_XY[1]
    inner_y = drawing.KEEPER_INNER_LINE_XY[1]
    socket = _keeper_plan(part.COLUMN_X, part.REAR_COLUMN_Z)
    seat_end_y = _keeper_plan(x0, z1)[1]
    return {
        "length": ((length_x, seat_end_y), (length_x, _keeper_plan(x0, z0)[1])),
        "width": (
            (_keeper_plan(x0, z0)[0], width_y),
            (_keeper_plan(x1, z0)[0], width_y),
        ),
        "end": ((length_x, socket[1]), (length_x, seat_end_y)),
        "inner": ((_keeper_plan(x0, z0)[0], inner_y), (socket[0], inner_y)),
    }


def test_keeper_seat_location_chains_off_the_rear_socket_axis() -> None:
    x0, _x1, _z0, z1 = spec.KEEPER_SEAT_BOUNDS_XZ[1]
    # Nominal location of the split lines, reference only: the seat is sized
    # and placed to the fitted keeper, not to fixed tooling.
    assert part.COLUMN_X - x0 == pytest.approx(4.2)
    assert part.REAR_COLUMN_Z - z1 == pytest.approx(24.903912, abs=1e-6)
    places = spec.DRAWING_REFERENCE_PRECISION
    assert places["keeper seat inner edge from socket"] == 1
    assert places["keeper seat end from socket"] == 1
    socket = _keeper_plan(part.COLUMN_X, part.REAR_COLUMN_Z)
    # The end location chains in line with the length: one shared witness.
    end_x, end_y = drawing.KEEPER_END_LINE_XY
    assert end_x == drawing.KEEPER_LENGTH_LINE_XY[0]
    assert socket[1] < end_y < _keeper_plan(x0, z1)[1]
    # The inner-edge location runs just below the plan, between its witnesses.
    boxes = _keeper_sheet_boxes()
    inner_x, inner_y = drawing.KEEPER_INNER_LINE_XY
    assert boxes["plan"][1] - inner_y == pytest.approx(drawing.KEEPER_DIM_LINE_GAP)
    assert _keeper_plan(x0, 0.0)[0] < inner_x < socket[0]


def test_keeper_plan_leaders_cross_no_foreign_ink() -> None:
    boxes = _keeper_sheet_boxes()
    lines = _keeper_dimension_lines()
    ink = drawing.INK_CLEARANCE
    leaders = {
        "length": (drawing.KEEPER_LENGTH_LINE_XY, drawing.KEEPER_LENGTH_TEXT_XY),
        "width": (drawing.KEEPER_WIDTH_LINE_XY, drawing.KEEPER_WIDTH_TEXT_XY),
        "end": (drawing.KEEPER_END_LINE_XY, drawing.KEEPER_END_TEXT_XY),
        "inner": (drawing.KEEPER_INNER_LINE_XY, drawing.KEEPER_INNER_TEXT_XY),
    }
    for name, leader in leaders.items():
        own = f"{name} text"
        for other, box in boxes.items():
            # The width line itself stands inside the plan's rail band.
            if other == own or (name == "width" and other == "plan"):
                continue
            assert _box_segment_gap(box, leader) >= ink, (name, other)
        for other, line in lines.items():
            if other == name or {name, other} == {"end", "length"}:
                continue  # its own line; the chained pair share a witness end
            assert _box_segment_gap((*line[0], *line[1]), leader) >= ink, (name, other)
    # Every value parks right of the plan, clear of it.
    for name in ("length", "width", "end", "inner"):
        assert boxes[f"{name} text"][0] - boxes["plan"][2] >= ink, name
    # Each dimension line clears every text field but its own.
    for name, line in lines.items():
        for other, box in boxes.items():
            if other in ("plan", f"{name} text"):
                continue
            assert _box_segment_gap(box, line) >= ink, (name, other)


def test_keeper_flange_dimension_stands_in_the_air_past_the_cut() -> None:
    boxes = _keeper_sheet_boxes()
    lines = _keeper_dimension_lines()
    ink = drawing.INK_CLEARANCE
    _x0, _x1, _z0, z1 = spec.KEEPER_SEAT_BOUNDS_XZ[0]
    end_z = drawing.keeper_section_cut_ends()[1][1]
    end_x = _keeper_section(end_z, part.HALF_H)[0]
    seat_y = _keeper_section(z1, part.HALF_H)[1]
    underside_y = _keeper_section(z1, part.FLANGE_BOT_Y)[1]
    line_x, line_y = drawing.KEEPER_FLANGE_LINE_XY
    # One line gap past the cut's far end, so the line lies on no hatching,
    # and level with the flange it measures.
    assert line_x - end_x == pytest.approx(drawing.KEEPER_DIM_LINE_GAP)
    assert line_x - boxes["G-G"][2] >= ink
    assert underside_y < line_y < seat_y
    assert line_y == pytest.approx((underside_y + seat_y) / 2.0)
    line = ((line_x, underside_y), (line_x, seat_y))
    # Witnesses run out along their own faces: the seat line's continuation
    # over the residual top, and the underside through the cut's far end.
    witnesses = (
        (_keeper_section(z1, part.HALF_H), (line_x, seat_y)),
        ((end_x, underside_y), (line_x, underside_y)),
    )
    # The value parks right of its line, outside the section.
    text = boxes["flange text"]
    assert text[0] - line_x >= ink
    leader = (drawing.KEEPER_FLANGE_LINE_XY, drawing.KEEPER_FLANGE_TEXT_XY)
    for other, box in boxes.items():
        if other == "flange text":
            continue
        assert _box_segment_gap(box, line) >= ink, other
        assert _box_segment_gap(box, leader) >= ink, other
        if other != "G-G":
            for witness in witnesses:
                assert _box_segment_gap(box, witness) >= ink, other
    for other, plan_line in lines.items():
        for segment in (line, leader, *witnesses):
            plan_box = (*plan_line[0], *plan_line[1])
            assert _box_segment_gap(plan_box, segment) >= ink, other


def test_keeper_section_cuts_each_seat_over_its_flat_flange_underside() -> None:
    (x_start, z_start), (x_end, z_end) = drawing.keeper_section_cut_ends()
    assert x_start == x_end == drawing.KEEPER_SECTION_X
    # Midway between the west web's nominal root-fillet toe, where the
    # underside turns flat, and the seats' outer split line.
    root_toe = part.WEB_OUT_X + part.ROOT_FILLET_R
    assert root_toe == pytest.approx(206.5)
    for x0, x1, _z0, _z1 in spec.KEEPER_SEAT_BOUNDS_XZ:
        assert x1 == pytest.approx(207.0)
        assert x0 < root_toe < drawing.KEEPER_SECTION_X < x1
        assert drawing.KEEPER_SECTION_X == pytest.approx((root_toe + x1) / 2.0)
    assert drawing.KEEPER_SECTION_X == pytest.approx(206.75)
    assert drawing.KEEPER_SECTION_X < part.OUTER_X - part.EDGE_CHAMFER
    # Outboard of the keeper tap's drill and thread: G-G cuts no thread.
    drill_r = part.TAP_DRILL_MM[part.KEEPER_TAP_SPEC.size] / 2.0
    major_r = part.THREAD_MAJOR_MM[part.KEEPER_TAP_SPEC.size] / 2.0
    assert part.KEEPER_TAP_X + max(drill_r, major_r) < drawing.KEEPER_SECTION_X
    boss_half = _keeper_cut_half_chord(part.BOSS_DIA)
    assert drawing.KEEPER_BOSS_HALF_CHORD == pytest.approx(boss_half)
    assert boss_half == pytest.approx(math.sqrt(22.5**2 - 9.75**2))
    # From beyond the front boss, past the front seat's far split line.
    assert z_start < -drawing.PLAN_HALF_Z < part.FRONT_COLUMN_Z - boss_half
    _x0, _x1, z0, z1 = spec.KEEPER_SEAT_BOUNDS_XZ[0]
    assert part.FRONT_COLUMN_Z + boss_half < z0 < z1 < z_end
    assert z_end == pytest.approx(z1 + drawing.KEEPER_SECTION_RUNOUT)
    assert z_end == pytest.approx(drawing.KEEPER_SECTION_END_Z)
    assert z_end < spec.KEEPER_SEAT_BOUNDS_XZ[1][2]
    # Every G-G row derives from the front seat's centre.
    assert drawing.KEEPER_SECTION_SEAT_Z == pytest.approx(
        spec.KEEPER_SEAT_CENTRES_XZ[0][1]
    )


def _keeper_line(start, end, tag):
    from _drawing_common import ViewEdge

    return ViewEdge(edge=tag, line=(start, end), circle=None, vertices=None)


def test_keeper_split_edge_pick_needs_the_whole_boundary() -> None:
    from _drawing_common import ViewEdges

    x0, x1, z0, _z1 = spec.KEEPER_SEAT_BOUNDS_XZ[1]
    y = part.HALF_H
    split = ViewEdges("plan", (_keeper_line((x1, y, z0), (x0, y, z0), "split"),))
    assert (
        drawing._keeper_seat_split_edge(split, (x0, y, z0), (x1, y, z0), label="split")
        == "split"
    )
    rim = (part.INNER_X + part.EDGE_CHAMFER, part.OUTER_X - part.EDGE_CHAMFER)
    merged = ViewEdges("plan", (_keeper_line((rim[0], y, z0), (rim[1], y, z0), "rim"),))
    with pytest.raises(RuntimeError, match="not the split line"):
        drawing._keeper_seat_split_edge(
            merged, (x0, y, z0), (x1, y, z0), label="merged"
        )


def test_keeper_section_seat_line_runs_split_to_split() -> None:
    from _drawing_common import ViewEdges

    x, y = drawing.KEEPER_SECTION_X, part.HALF_H
    _x0, _x1, z0, z1 = spec.KEEPER_SEAT_BOUNDS_XZ[0]
    centre = spec.KEEPER_SEAT_CENTRES_XZ[0][1]
    boss_z = part.FRONT_COLUMN_Z + _keeper_cut_half_chord(part.BOSS_DIA)
    end_z = drawing.keeper_section_cut_ends()[1][1]
    residual = _keeper_line((x, y, boss_z), (x, y, z0), "residual")
    seat = _keeper_line((x, y, z1), (x, y, z0), "seat")
    beyond = _keeper_line((x, y, z1), (x, y, end_z), "beyond")
    underside = _keeper_line(
        (x, part.FLANGE_BOT_Y, boss_z), (x, part.FLANGE_BOT_Y, end_z), "underside"
    )
    edge, point = drawing._keeper_seat_cut_edge(
        ViewEdges("G-G", (residual, seat, beyond, underside)), label="seat"
    )
    assert edge == "seat"
    assert point == pytest.approx((x, y, centre))
    # A split that failed at either end merges the seat into the residual top.
    for merged in (
        _keeper_line((x, y, boss_z), (x, y, z1), "merged near"),
        _keeper_line((x, y, z0), (x, y, end_z), "merged far"),
    ):
        with pytest.raises(RuntimeError, match="expected one seat line"):
            drawing._keeper_seat_cut_edge(
                ViewEdges("G-G", (residual, merged, beyond)), label="seat"
            )
    # A seat line broken part-way (say by a tap the plane should miss).
    broken = (
        _keeper_line((x, y, z0), (x, y, centre - 1.0), "broken near"),
        _keeper_line((x, y, centre + 1.0), (x, y, z1), "broken far"),
    )
    with pytest.raises(RuntimeError, match="expected one seat line"):
        drawing._keeper_seat_cut_edge(ViewEdges("G-G", broken), label="seat")
    with pytest.raises(RuntimeError, match="expected one seat line"):
        drawing._keeper_seat_cut_edge(ViewEdges("G-G", (underside,)), label="seat")


def test_keeper_section_underside_line_spans_the_whole_seat() -> None:
    from _drawing_common import ViewEdges

    x, y = drawing.KEEPER_SECTION_X, part.FLANGE_BOT_Y
    _x0, _x1, z0, z1 = spec.KEEPER_SEAT_BOUNDS_XZ[0]
    centre = spec.KEEPER_SEAT_CENTRES_XZ[0][1]
    boss_z = part.FRONT_COLUMN_Z + _keeper_cut_half_chord(part.BOSS_DIA)
    end_z = drawing.keeper_section_cut_ends()[1][1]
    seat = _keeper_line((x, part.HALF_H, z0), (x, part.HALF_H, z1), "seat")
    underside = _keeper_line((x, y, end_z), (x, y, boss_z), "underside")
    edge, point = drawing._keeper_flange_underside_edge(
        ViewEdges("G-G", (seat, underside)), label="underside"
    )
    assert edge == "underside"
    assert point == pytest.approx((x, y, centre))
    # A blend or break that leaves part of the seat without flat underside
    # below it, a line at another level, or one off the plane is refused.
    for wrong in (
        _keeper_line((x, y, z0 + 1.0), (x, y, end_z), "short"),
        _keeper_line((x, y, boss_z), (x, y, z1 - 1.0), "short far"),
        _keeper_line((x, y - 0.5, boss_z), (x, y - 0.5, end_z), "low"),
        _keeper_line((x - 0.5, y, boss_z), (x - 0.5, y, end_z), "off plane"),
    ):
        with pytest.raises(RuntimeError, match="expected one flange underside line"):
            drawing._keeper_flange_underside_edge(
                ViewEdges("G-G", (seat, wrong)), label="underside"
            )


def test_socket_bore_circle_pick_is_exact_about_the_axis() -> None:
    from _drawing_common import ViewEdge, ViewEdges

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


def test_pin_section_profile_can_hold_its_row_as_well(monkeypatch) -> None:
    view = _FakeView((0.3300, 0.2100))
    monkeypatch.setattr(
        drawing,
        "model_point_in_view",
        lambda _adapter, v, _xyz, *, label: (
            v.Position[0] - 0.0043,
            v.Position[1] + 0.0020,
        ),
    )
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda _adapter, *, label: None)
    monkeypatch.setattr(drawing, "double_array", lambda values: tuple(values))
    drawing._pin_section_profile(
        None, view, (0.0, 0.0, 0.0), 0.3320, target_y=0.1800, label="G-G"
    )
    assert view.Position == pytest.approx((0.3363, 0.1780))


def _keeper_sheet_tree():
    import ast

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    sheet = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_keeper_seat_sheet"
    )
    build = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    return sheet, build


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


def test_keeper_dimensions_hang_on_split_lines_and_the_flange_underside() -> None:
    import ast

    sheet, _build = _keeper_sheet_tree()
    dimensions = {
        ast.literal_eval(_keyword(call, "label")): call
        for call in _named_calls(sheet, "_checked_dimension")
    }
    assert set(dimensions) == {
        "keeper seat width",
        "keeper seat length",
        "keeper seat inner edge from socket",
        "keeper seat end from socket",
        "keeper seat flange thickness",
    }
    assigned = {}
    for node in ast.walk(sheet):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            names = target.elts if isinstance(target, ast.Tuple) else (target,)
            for item in names:
                if isinstance(item, ast.Name):
                    assigned[item.id] = node.value
    for label, entities_name, expected in (
        ("keeper seat width", "width_edges", "KEEPER_SEAT_WIDTH_MM"),
        ("keeper seat length", "length_edges", "KEEPER_SEAT_LENGTH_MM"),
    ):
        call = dimensions[label]
        assert ast.literal_eval(_keyword(call, "reference")) is True, label
        assert _keyword(call, "expected_mm").id == expected, label
        entities = _keyword(call, "entities")
        assert isinstance(entities, ast.Name) and entities.id == entities_name
        picks = assigned[entities_name]
        assert isinstance(picks, ast.Tuple) and len(picks.elts) == 2
        assert all(
            isinstance(pick, ast.Call) and pick.func.id == "_keeper_seat_split_edge"
            for pick in picks.elts
        ), label
    # Location: the rear socket's bore circle, centred, to the same split
    # edges the footprint hangs on -- a nominal reference, like the size.
    socket = assigned["rear_socket_edge"]
    assert socket.func.id == "_socket_bore_circle"
    assert [arg.id for arg in socket.args] == [
        "keeper_plan_edges",
        "COLUMN_X",
        "REAR_COLUMN_Z",
    ]
    for label, orientation, expected, split in (
        (
            "keeper seat inner edge from socket",
            "horizontal",
            "COLUMN_X - xmin",
            "width_edges[0]",
        ),
        (
            "keeper seat end from socket",
            "vertical",
            "REAR_COLUMN_Z - zmax",
            "length_edges[1]",
        ),
    ):
        call = dimensions[label]
        assert ast.literal_eval(_keyword(call, "reference")) is True, label
        assert ast.literal_eval(_keyword(call, "center")) is True, label
        assert ast.literal_eval(_keyword(call, "orientation")) == orientation, label
        assert ast.unparse(_keyword(call, "expected_mm")) == expected, label
        assert [ast.unparse(item) for item in _keyword(call, "entities").elts] == [
            "rear_socket_edge",
            split,
        ], label
    # Those indices name the inner (x = xmin) and socket-side (z = zmax) edges.
    width_inner = assigned["width_edges"].elts[0]
    assert [ast.unparse(arg) for arg in width_inner.args[1:]] == [
        "(xmin, HALF_H, zmin)",
        "(xmin, HALF_H, zmax)",
    ]
    length_end = assigned["length_edges"].elts[1]
    assert [ast.unparse(arg) for arg in length_end.args[1:]] == [
        "(xmin, HALF_H, zmax)",
        "(xmax, HALF_H, zmax)",
    ]
    assert _keyword(dimensions["keeper seat width"], "center") is None
    # Controlling, not reference: the final flange left under the faced seat,
    # from G-G's own flat-underside and seat cut lines.
    flange = dimensions["keeper seat flange thickness"]
    assert _keyword(flange, "reference") is None
    assert _keyword(flange, "expected_mm").id == "FLANGE_THICKNESS_MM"
    assert ast.literal_eval(_keyword(flange, "orientation")) == "vertical"
    assert [item.id for item in _keyword(flange, "entities").elts] == [
        "underside_edge",
        "seat_edge",
    ]
    assert [ast.unparse(_keyword(flange, key)) for key in ("p0", "p1")] == [
        "underside_point",
        "seat_point",
    ]
    assert _keyword(flange, "text_xy").id == "KEEPER_FLANGE_LINE_XY"
    assert _keyword(flange, "offset_text").id == "KEEPER_FLANGE_TEXT_XY"
    assert _keyword(flange, "suffix").id == "KEEPER_FLANGE_QUALIFIER"
    assert assigned["underside_edge"].func.id == "_keeper_flange_underside_edge"
    assert assigned["underside_point"] is assigned["underside_edge"]
    assert assigned["seat_edge"].func.id == "_keeper_seat_cut_edge"
    assert assigned["seat_point"] is assigned["seat_edge"]
    for name in ("underside_edge", "seat_edge"):
        assert [ast.unparse(arg) for arg in assigned[name].args] == [
            "seat_section_edges"
        ], name
    # No cap-floor pick and no construction proxy remain on the sheet.
    assert not _named_calls(sheet, "_cut_face_edge")
    # No native Ra here: a plane-and-box face pick would take the residual
    # top too; the seats' SEAT_UM rides on the linked note B.
    assert not _named_calls(sheet, "add_surface_finish")


def test_keeper_section_is_a_native_removed_cut_of_the_plan() -> None:
    import ast

    sheet, build = _keeper_sheet_tree()
    (section,) = _named_calls(sheet, "create_section_view")
    assert ast.literal_eval(_keyword(section, "section_label")) == "G"
    assert ast.literal_eval(_keyword(section, "partial")) is True
    assert _keyword(section, "scale").id == "KEEPER_SECTION_SCALE"
    assert _keyword(section, "view_xy").id == "KEEPER_SECTION_SEAT_XY"
    assert _named_calls(sheet, "keeper_section_cut_ends")
    (orient,) = _named_calls(sheet, "_orient_cut_section")
    assert ast.literal_eval(orient.args[2]) == (0.0, 0.0, 1.0)
    (pin,) = _named_calls(sheet, "_pin_section_profile")
    assert ast.unparse(pin.args[2]) == (
        "(KEEPER_SECTION_X, HALF_H, KEEPER_SECTION_SEAT_Z)"
    )
    assert ast.unparse(_keyword(pin, "target_y")) == "KEEPER_SECTION_SEAT_XY[1]"
    # The plane stands outboard of the keeper tap: there is no thread to hide,
    # and the helper refuses a view without one.
    assert not _named_calls(sheet, "_hide_cosmetic_threads")
    (display,) = _named_calls(sheet, "_assert_section_display")
    assert ast.literal_eval(_keyword(display, "cut_surface_only")) is True
    assert ast.literal_eval(_keyword(display, "removed")) is True
    assert len(_named_calls(sheet, "set_hidden_lines_removed")) == 2
    (note,) = _named_calls(sheet, "add_property_linked_note")
    assert ast.literal_eval(note.args[1]) == "Manufacturing Notes B"
    (properties,) = _named_calls(build, "read_required_properties")
    assert "Manufacturing Notes B" in ast.literal_eval(properties.args[1])
    assert "Manufacturing Notes B" in ast.literal_eval(_keyword(properties, "required"))
    source = ast.unparse(build)
    assert source.index("_keeper_seat_sheet(adapter, ddoc)") < source.index(
        "_auto_tapped_hole_notes(adapter)"
    )


class _FakeSeatFace:
    """A split face as GetBox (m, coarse) and GetArea (m^2) report it."""

    def __init__(self, box_mm, area_mm2):
        self._box = tuple(value / 1000.0 for value in box_mm)
        self._area = area_mm2 / 1e6

    def GetBox(self):
        return self._box

    def GetArea(self):
        return self._area


class _FakeSeatFeature:
    def __init__(self, faces):
        self._faces = tuple(faces)

    def GetFaces(self):
        return self._faces


def _keeper_seat_area_mm2():
    drill = part.TAP_DRILL_MM[part.KEEPER_TAP_SPEC.size]
    return (
        spec.KEEPER_SEAT_WIDTH_MM * spec.KEEPER_SEAT_LENGTH_MM
        - math.pi * (drill / 2.0) ** 2
    )


def _keeper_seat_face(index):
    x0, x1, z0, z1 = spec.KEEPER_SEAT_BOUNDS_XZ[index]
    y = part.HALF_H
    # GetBox is only approximate: pad it as SolidWorks may.
    return _FakeSeatFace(
        (x0 - 0.05, y, z0 - 0.05, x1 + 0.05, y, z1 + 0.05), _keeper_seat_area_mm2()
    )


def _residual_rail_top():
    """The rest of the west flange top: same plane, box spans both seats."""
    y = part.HALF_H
    box = (part.INNER_X, y, -drawing.PLAN_HALF_Z, part.OUTER_X, y, drawing.PLAN_HALF_Z)
    seats = 2.0 * spec.KEEPER_SEAT_WIDTH_MM * spec.KEEPER_SEAT_LENGTH_MM
    area = (part.OUTER_X - part.INNER_X) * 2.0 * drawing.PLAN_HALF_Z - seats
    return _FakeSeatFace(box, area)


def _qualify_keeper_faces(monkeypatch, faces) -> None:
    feature = _FakeSeatFeature(faces)

    def by_name(_adapter, name):
        assert name == "KeeperSeatFaces"
        return feature

    monkeypatch.setattr(part, "_feature_by_name", by_name)
    monkeypatch.setattr(part, "_early_bound", lambda obj, _interface: obj)
    part._qualify_keeper_seat_faces(None)


def test_keeper_seat_qualifier_takes_the_two_bounded_seats_past_the_residual_top(
    monkeypatch,
) -> None:
    # The residual flange top shares the plane and its box covers both seat
    # centres; only its area keeps it out of the count.
    _qualify_keeper_faces(
        monkeypatch, (_residual_rail_top(), _keeper_seat_face(0), _keeper_seat_face(1))
    )


@pytest.mark.parametrize(
    ("faces", "counts"),
    [
        ((0, 0, 1), "[2, 1]"),
        ((0,), "[1, 0]"),
        ((1,), "[0, 1]"),
        ((), "[0, 0]"),
    ],
    ids=["duplicate front", "missing rear", "missing front", "no split"],
)
def test_keeper_seat_qualifier_rejects_a_duplicate_or_missing_region(
    monkeypatch, faces, counts
) -> None:
    import re

    seats = [_residual_rail_top(), *(_keeper_seat_face(index) for index in faces)]
    with pytest.raises(RuntimeError, match=re.escape(f"face per seat; got {counts}")):
        _qualify_keeper_faces(monkeypatch, seats)


def test_keeper_seat_qualifier_rejects_a_residual_merged_into_a_seat(
    monkeypatch,
) -> None:
    # A split that failed on one station leaves that seat's area inside a
    # residual face, which the 1% area filter refuses to count.
    front = _keeper_seat_face(0)
    merged = _FakeSeatFace(
        (
            part.INNER_X,
            part.HALF_H,
            0.0,
            part.OUTER_X,
            part.HALF_H,
            drawing.PLAN_HALF_Z,
        ),
        1.02 * _keeper_seat_area_mm2(),
    )
    with pytest.raises(RuntimeError, match=r"got \[1, 0\]"):
        _qualify_keeper_faces(monkeypatch, (_residual_rail_top(), front, merged))


def _builder_tree():
    import ast

    return ast.parse(Path(part.__file__).read_text(encoding="utf-8"))


def _called_name(call):
    import ast

    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def test_keeper_seat_split_only_projects_lines_on_the_existing_rail_top() -> None:
    import ast
    import re

    tree = _builder_tree()
    split = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_split_keeper_seats"
    )
    calls = [node for node in ast.walk(split) if isinstance(node, ast.Call)]
    names = [_called_name(call) for call in calls]
    # Split boundaries only: no pad, cut, extrude or edge break moves stock.
    assert not [
        name
        for name in names
        if re.search(r"(?i)extru|cut|boss|pad|chamfer|fillet|offset", name)
    ]
    assert names.count("InsertSplitLineProject") == 1
    (face,) = [call for call in calls if _called_name(call) == "PlanarFace"]
    assert ast.literal_eval(face.args[0]) == (0.0, 1.0, 0.0)
    assert face.args[1].id == "HALF_H"
    (sketch,) = [call for call in calls if _called_name(call) == "create_sketch"]
    assert ast.literal_eval(sketch.args[0]) == "Top"
    (select,) = [call for call in calls if _called_name(call) == "SelectByID2"]
    assert ast.literal_eval(select.args[0]) == "KeeperSeatProfile"
    assert ast.literal_eval(select.args[6]) == 4
    marks = [
        node.value
        for node in ast.walk(split)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == "Mark" for t in node.targets)
    ]
    assert [ast.literal_eval(mark) for mark in marks] == [1]
    loops = [node for node in ast.walk(split) if isinstance(node, ast.For)]
    assert [ast.unparse(loop.iter) for loop in loops] == [
        "enumerate(KEEPER_SEAT_BOUNDS_XZ)"
    ]
    named = [
        ast.literal_eval(call.args[1])
        for call in calls
        if _called_name(call) == "name_last_feature"
    ]
    assert named == ["KeeperSeatProfile", "KeeperSeatFaces"]


def test_keeper_seats_split_after_the_solid_and_qualify_once_before_pmi() -> None:
    import ast

    tree = _builder_tree()
    build = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    statements = [ast.unparse(node) for node in build.body]

    def index(text):
        (found,) = [i for i, statement in enumerate(statements) if statement == text]
        return found

    split = index("await _split_keeper_seats(adapter)")
    gate = split + 1
    (gate_call,) = [
        node
        for node in ast.walk(build.body[gate])
        if isinstance(node, ast.Call) and _called_name(node) == "volume_check"
    ]
    # The zero-volume gate: expected volume is the running volume untouched.
    assert (
        ast.literal_eval(gate_call.args[1]) == "keeper seat split (no material change)"
    )
    assert isinstance(gate_call.args[2], ast.Name) and gate_call.args[2].id == "volume"
    assert 0.0 < ast.literal_eval(gate_call.args[3]) <= 0.05
    # Every material feature precedes the split.
    last_material = max(
        i
        for i, node in enumerate(build.body[:split])
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and _called_name(call) == "volume_check"
    )
    assert "'external edge breaks'" in statements[last_material]
    rebuilds = [
        i for i, s in enumerate(statements) if s == "await force_rebuild(adapter)"
    ]
    driven = next(
        i
        for i, s in enumerate(statements)
        if "'driven casting (equations neutral)'" in s
    )
    machined = index("_qualify_machined_faces(adapter)")
    seats = index("_qualify_keeper_seat_faces(adapter)")
    pmi = next(i for i, s in enumerate(statements) if s.startswith("author_part_pmi("))
    assert gate < max(rebuilds) < driven < machined < seats < pmi
    module_calls = [
        _called_name(node) for node in ast.walk(tree) if isinstance(node, ast.Call)
    ]
    assert module_calls.count("_split_keeper_seats") == 1
    assert module_calls.count("_qualify_keeper_seat_faces") == 1
