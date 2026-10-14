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
    assert TOP_SCREW_SEAT_Z == 128.35
    floor_offset = (
        round(part.COUNTERBORE_FLOOR - abs(part.FRONT_COLUMN_Z), floor_places)
        - spec.PRINTED_LINEAR_BAND_MM[floor_places]
    )
    recess_radius = (part.CAP_RECESS_DIAMETER + part.CAP_RECESS_DIAMETER_BAND[0]) / 2.0
    recess_floor = part.CAP_RECESS_FLOOR_Y - part.CAP_RECESS_DEPTH_BAND[0]
    rim = spec.PRINTED_LINEAR_BAND_MM[axis_places] + (
        round(part.COUNTERBORE_DIA, seat_places) + spec.PRINTED_LINEAR_BAND_MM[seat_places]
    ) / 2.0
    ligament = math.hypot(floor_offset - recess_radius, recess_floor - rim)
    assert ligament == pytest.approx(part.COUNTERBORE_PRINTED_CAP_LIGAMENT)
    assert ligament == pytest.approx(2.040, abs=5e-4)
    assert ligament >= 2.0
    assert part.COUNTERBORE_PRINTED_NEAR_WALL >= 2.0
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
    # The 25-wide bar shortens the two window rims by another 2 mm of C2
    # compared with the former 24-wide section (2 mm^2 per mm).
    assert window == pytest.approx(2762.3499756456845)
    assert part.WEB_T == 13.0
    root_chord = math.sqrt((part.BOSS_DIA / 2.0) ** 2 - (part.WEB_T / 2.0) ** 2)
    side_run = 2.0 * (abs(part.FRONT_COLUMN_Z) - root_chord)
    front_rear_run = 2.0 * (part.COLUMN_X - root_chord)
    outer_run = 2.0 * side_run - part.HUB_RIB_W + 2.0 * front_rear_run
    window_run = outer_run - 2.0 * (part.LAND_X1 - part.LAND_X0)
    assert root_chord == pytest.approx(21.540659228538015)
    assert side_run == pytest.approx(180.91868154292396)
    assert front_rear_run == pytest.approx(350.918681542924)
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
        largest_hole_r = spec.HANGER_SPOTFACE_DIA_MAX / 2.0
        wall = abs(station) - band - largest_hole_r - pocket_end
        assert wall >= 2.0
    assert min(part.BAR_POCKET_HOLE_WALLS.values()) >= 2.0


def test_knife_seat_footprints_cover_every_printed_extreme() -> None:
    # Each print-worst hull holds the nominal block and reaches at least the
    # unskewed stack: D's .X location band, the hanger's centring zone, half
    # the dowel slip and the worse .X row-to-face reach.
    import sm_knife_mount_spec as mount

    reach = max(
        mount.HOLE_ROW_FACE_DISTANCE + mount.HOLE_ROW_FACE_TOL,
        mount.SUPPORT_Z_THICK
        + mount.BLOCK_SIZE_TOL
        - (mount.HOLE_ROW_FACE_DISTANCE - mount.HOLE_ROW_FACE_TOL),
    )
    band = spec.PRINTED_LINEAR_BAND_MM[1]
    slip = spec.HANGER_PIN_SLIP_CLEARANCE_MAX / 2.0
    for mount_name, station in (
        ("front", part.STUD_Z_FRONT),
        ("rear", part.STUD_Z_REAR),
    ):
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


def test_c2_breaks_stay_clear_of_both_print_worst_knife_seats() -> None:
    # Every finished underside C2 band keeps 0.5 off both seats; the pocket
    # ends bind the front seat.  The sharp bar sides and gusset hypotenuses
    # beyond the pockets are exactly the edges a C2 would put under it.
    _groups, clearance = part._external_edge_breaks()
    assert clearance == part.KNIFE_SEAT_C2_CLEARANCE
    assert min(clearance.values()) >= part.KNIFE_SEAT_C2_MIN_CLEARANCE == 0.5
    reach = part.EDGE_CHAMFER + part._C2_LEG_BAND + part._EDGE_LOCATION_BAND
    gusset_z = part.INNER_Z - part.GUSSET
    front = part.KNIFE_SEAT_FOOTPRINTS["front"]
    bar_side_band = [
        (part.BAR_X0 - part._EDGE_LOCATION_BAND, -part.BAR_POCKET_Z),
        (part.BAR_X0 + reach, -part.BAR_POCKET_Z),
        (part.BAR_X0 + reach, -gusset_z),
        (part.BAR_X0 - part._EDGE_LOCATION_BAND, -gusset_z),
    ]
    assert part._plan_gap(bar_side_band, front) < 0.5
    hypotenuse_band = [
        (part.BAR_X0, -gusset_z),
        (part.BAR_X0 - part.GUSSET, -part.INNER_Z),
        (part.BAR_X0 - part.GUSSET + reach * math.sqrt(2.0), -part.INNER_Z),
        (part.BAR_X0 + reach * math.sqrt(2.0), -gusset_z),
    ]
    assert part._plan_gap(hypotenuse_band, front) < 0.5


def test_c2_picks_are_convex_and_the_gusset_junctions_are_not() -> None:
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


def test_c2_breaks_split_into_connected_chains_in_build_order() -> None:
    groups, _clearance = part._external_edge_breaks()
    assert groups == part.EXTERNAL_EDGE_BREAKS
    assert list(groups) == [
        "RailRunBreaks",
        "CrossbarBreaks",
        "WestWindowBreaks",
        "HubRailBreaks",
        "HubSetBossBreaks",
        "OuterCornerBreaks",
        "BossRimBreaks",
    ]
    for feature, (picks, removal, shared) in groups.items():
        assert picks and removal > 0.0, feature
    # The boss rims are closed circles and the rail runs die into boss
    # barrels at both ends: neither shares a vertex.
    assert groups["RailRunBreaks"][2] == groups["BossRimBreaks"][2] == 0
    # Each rib-side bottom ends on the web face, at its web bottom's end, in
    # the same feature.
    hub = groups["HubRailBreaks"][0]
    for z_rib in (
        part.GOOSENECK_Z - part.HUB_RIB_W / 2.0,
        part.GOOSENECK_Z + part.HUB_RIB_W / 2.0,
    ):
        assert [(-part.OUTER_X - part.WEB_OUT_X) / 2.0, -part.HALF_H, z_rib] in hub


def test_c2_chains_leave_no_sliver_between_features(monkeypatch) -> None:
    assert part._segment_gap((0, 0, 0), (1, 0, 0), (1, 0, 0), (1, 1, 0)) == 0.0
    assert part._segment_gap((0, 0, 0), (2, 0, 0), (1, 1, 1), (1, 1, 3)) == (
        pytest.approx(math.sqrt(2.0))
    )
    assert part._segment_gap((0, 0, 0), (1, 0, 0), (3, 0, 0), (4, 0, 0)) == 2.0
    # The nearest two breaks that do not meet stand 5.0 apart (the hub rail's
    # flange-underside run and the set-screw boss's; the pocket ends, 4.5
    # apart on the 22-wide crossbar, are 6.0 on the 25); demanding a land
    # that wide trips the guard.
    monkeypatch.setattr(part, "C2_SLIVER_MIN", 1.1)
    with pytest.raises(AssertionError, match="sliver"):
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
    assert len(points) == 83
    assert len({tuple(round(value, 6) for value in point) for point in points}) == len(
        points
    )
    # No two picks share an edge's 0.5 mm selection radius.
    for i, a in enumerate(points):
        for b in points[i + 1 :]:
            assert math.dist(a, b) > 0.5
    # The crossbar flange's underside edges, the bar-side and gusset
    # hypotenuse bottoms beyond the pockets and the hub rib's outer and inner
    # bottom edges stay sharp: none is picked.
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
        if y == -part.HALF_H and part.BAR_POCKET_Z < abs(z) < part.INNER_Z:
            # No bar-side bottom; no hypotenuse bottom (x off the bar).
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
    flange_places = spec.DRAWING_REFERENCE_PRECISION["top flange thickness"]
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


@pytest.mark.parametrize("stack", ("cap floor height", "typ top flange thickness"))
def test_printed_typ_top_flange_minimum_keeps_the_receiver_wall(stack) -> None:
    """Facing may lower the keeper-rail top; only a directly printed FINAL
    flange that covers it bounds what the receiver's T-root keeps at the
    worst case.  B-B prints the top flange TYP, so its .X minimum binds the
    faced keeper rail too, with no second facing allowance."""
    band = spec.PRINTED_LINEAR_BAND_MM
    top_places = spec.DRAWING_REFERENCE_PRECISION["top flange thickness"]
    assert top_places == spec.FLANGE_THICKNESS_PLACES == 1
    assert spec.FLANGE_THICKNESS_MM == part.FLANGE == 8.0
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"top flange thickness", "TYP TOP FLANGE"' in source
    if stack == "typ top flange thickness":
        flange_depth = round(spec.FLANGE_THICKNESS_MM, top_places) - band[top_places]
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
    if stack == "typ top flange thickness":
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
    """The moved ends keep what each removed section shows: B cuts the
    rail's plain T between the junction land and the corner boss, E runs
    from outside the left rail past the crossbar T, D from outside the
    set-screw boss past the hub rail's inner face, each at its own station."""
    ends = drawing.section_cut_ends()
    (bx, b_outer), (bx_inner, b_inner) = ends["B"]
    assert bx == bx_inner and part.LAND_X1 < bx < part.COLUMN_X - part.BOSS_DIA / 2.0
    assert b_inner < part.INNER_Z and b_outer > drawing.PLAN_HALF_Z
    (e_inner, ez), (e_outer, ez_outer) = ends["E"]
    assert ez == ez_outer == drawing.SIDE_SECTION_Z
    assert e_inner > part.BAR_X1 and e_outer < -drawing.PLAN_HALF_X
    (d_outer, dz), (d_inner, dz_inner) = ends["D"]
    assert dz == dz_inner == part.GOOSENECK_Z
    assert d_outer < part.SET_BOSS_FACE_X and -part.INNER_X < d_inner < part.BAR_X0


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
    """The set tap starts from a spot face 21.0 (.X) from the bore axis on a
    boss cast onto the hub pad, and keeps >= 1.5D of full thread at the
    printed worst case (the ch_pivot_bracket_spec idiom)."""
    terms = spec.SET_SCREW_THREAD_TERMS
    assert list(terms) == [
        "spot face from bore axis at its minimum",
        "bore radius at its maximum",
        "bore sag across the thread",
        "one-pitch entry chamfer",
    ]
    assert terms["spot face from bore axis at its minimum"] == pytest.approx(20.2)
    assert all(v < 0.0 for k, v in terms.items() if k != "spot face from bore axis at its minimum")
    assert spec.SET_SCREW_FULL_THREAD_MIN == pytest.approx(9.579, abs=1e-3)
    assert spec.SET_SCREW_FULL_THREAD_NOMINAL == pytest.approx(10.615, abs=1e-3)
    assert spec.SET_SCREW_MAJOR_DIA == pytest.approx(6.35)
    assert spec.SET_SCREW_ENGAGEMENT_D >= spec.SET_SCREW_MIN_ENGAGEMENT_D == 1.5


def test_set_screw_boss_carries_the_spot_face_proud_of_the_rail() -> None:
    """The boss face stands 1.0 of stock over the spot face, both outboard
    of the rail's outer face; the spot clears the 1/4 square head's
    diagonal (91410A540, Head Wd 1/4 in) at its .X minimum, and keeps a land
    inside the boss face's C2 breaks at the print-worst corner (local codex
    review of 4faacfab: the O12 spot broke 0.4 into them)."""
    assert part.SET_SPOT_FACE_X == part.GOOSENECK_X - spec.HUB_SET_SPOT_FROM_AXIS == -218.0
    assert part.SET_BOSS_FACE_X == part.GOOSENECK_X - spec.HUB_SET_BOSS_FROM_AXIS == -219.0
    assert part.SET_BOSS_FACE_X < part.SET_SPOT_FACE_X < -part.OUTER_X
    assert spec.HUB_SET_SPOT_PLACES == spec.DRAWING_REFERENCE_PRECISION[
        "set-screw spot face from bore axis"
    ] == 1
    assert spec.HUB_SET_SPOT_DIA - part.PRINTED_LINEAR_BAND_MM[1] > 6.35 * math.sqrt(2.0)
    assert part.SET_SPOT_LAND_MIN == pytest.approx(
        {"across the boss": 0.6, "under the flange": 0.65}
    )
    assert min(part.SET_SPOT_LAND_MIN.values()) >= part.C2_SLIVER_MIN
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
# is 6.35 (HANGER_SLOT_FRAME_SHOULDER's).
_ROW_PITCH = 0.00555
_ROW_SLACK = 0.00195
_ROW_CHAR = 0.00282
_UNDERLINE_DROP = 0.001
_UNDERLINE_PAST = 0.0001
_EXTENSION_OVERSHOOT = 0.00103
_BENT_SHOULDER = 0.00635
# D-D's tap axis (rail mid-height) prints at y 211.8 mm; its caption,
# SECTION D-D over SCALE 1 : 1, printed 307.3..352.6 x 163.3..178.0 mm about
# HUB_SECTION_CAPTION_XY (run 6).
_DD_AXIS_Y = 0.2118
_DD_CAPTION_EXTENT = (0.0227, 0.0147, 0.0226, 0.0)
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
    """D-D at 1:1, model X right of the pinned bore axis, model Y up."""
    return (
        drawing.HUB_SECTION_PROFILE_X + (x - part.GOOSENECK_X) / 1000.0,
        _DD_AXIS_Y + y / 1000.0,
    )


def test_hub_boss_section_texts_and_leaders_stand_clear_of_their_ink() -> None:
    """Q5 (user, 2026-10-12): D-D dimensions the thread length, the 21.0 to
    the spot face and the boss face's 22.0, and finishes the spot face.  The
    thread length's text goes out left, the 21.0's right and the 22.0's left
    under the view, so no leader crosses another dimension's extension line
    and every text, leader and the finish symbol keep INK_CLEARANCE."""
    from _layout_geometry import Segment, segment_box_distance

    ink = drawing.INK_CLEARANCE
    tap_r = part.TAP_DRILL_MM[part.SET_SCREW_THREAD] / 2.0
    spot_r = spec.HUB_SET_SPOT_DIA / 2.0
    bore_x = part.GOOSENECK_X - part.GOOSENECK_BORE_DIA / 2.0
    spot_x, boss_x, axis_x = part.SET_SPOT_FACE_X, part.SET_BOSS_FACE_X, part.GOOSENECK_X
    chamfer = part.EDGE_CHAMFER
    # The faces the build picks, each the midpoint of its cut line.
    spot_point = _dd(spot_x, (tap_r + spot_r) / 2.0)
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
    dx0, dy0, dx1, dy1 = _DD_CAPTION_EXTENT
    caption = (cx - dx0, cy - dy0, cx + dx1, cy + dy1)
    # The finish symbol stands on the spot's own row, left of the boss; its
    # leader runs straight in through the spot's open mouth.
    symbol = (spot_point[0] - drawing.HUB_SPOT_FINISH_REACH, spot_point[1])
    finish = tuple(value + offset for value, offset in zip(symbol * 2, _FINISH_INK))
    finish_leader = Segment(*symbol, *spot_point)
    assert abs(spot_point[1] - _DD_AXIS_Y) * 1000.0 < spot_r
    assert symbol[0] + drawing.HUB_SPOT_FINISH_TAIL < _dd(boss_x, 0.0)[0]
    assert _dd(boss_x, 0.0)[0] - finish[2] >= ink
    frame = drawing.SHEET_FRAME
    for name, block in blocks.items():
        assert frame[0] + ink <= block[0] and block[2] <= frame[2] - ink, name
        assert frame[1] + ink <= block[1] and block[3] <= frame[3] - ink, name
        assert _box_box_gap(block, outline) >= ink, name
        assert _box_box_gap(block, caption) >= ink, name
        assert _box_box_gap(block, finish) >= ink, name
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
        assert segment_box_distance(finish_leader, _layout_box(block)) >= ink, name
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
        assert segment_box_distance(leader, _layout_box(finish)) >= ink, name
    # The 22.0 hangs under the view over the caption: its line, arrowheads
    # and extension ends all stay an ink clearance above it.
    assert boss_y - drawing.ARROW_HALF_WIDTH - caption[3] >= ink
    assert boss_y - over - caption[3] >= ink
    for name, line in lines.items():
        assert segment_box_distance(line, _layout_box(finish)) >= ink, name
    for name, (*_owners, extension) in extensions.items():
        assert segment_box_distance(extension, _layout_box(finish)) >= ink, name


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


# --- Knife hanger: #10 loose clearance / washer spotface and dowels --------


def test_knife_hanger_is_a_10_loose_hole_and_washer_spotface() -> None:
    import spring_mount_geom

    hole = spec.HANGER_HOLE_SPEC
    assert (hole.kind, hole.size, hole.fit, hole.end) == (
        "counterbore_socket", "#10", "loose", "through_all",
    )
    assert hole.overrides_mm == {
        "HoleDiameter": spec.HANGER_CLEARANCE_DIA,
        "CounterBoreDiameter": spec.HANGER_SPOTFACE_DIA,
        "CounterBoreDepth": spec.HANGER_SPOTFACE_DEPTH,
    }
    assert spec.HANGER_CLEARANCE_DIA == pytest.approx(6.045)
    assert spec.HANGER_SCREW_FLOAT == pytest.approx(0.6095)
    assert (spec.HANGER_SPOTFACE_DIA, spec.HANGER_SPOTFACE_DEPTH) == (17.0, 1.0)
    # The 1/2 hanger-stud clearance is gone, not aliased.
    assert not hasattr(part, "STUD_HOLE_SPEC") and not hasattr(part, "STUD_HOLE_DIA")
    # Both stations sit on the knife line, centred on the crossbar.
    assert part.HANGER_X == spring_mount_geom.KNIFE[0] == (part.BAR_X0 + part.BAR_X1) / 2.0
    assert drawing.HANGER_X == part.HANGER_X
    assert (part.BAR_X0, part.BAR_X1) == (-27.5, -2.5)
    assert spec.HANGER_CROSSBAR_WIDTH == part.BAR_X1-part.BAR_X0 == 25.0
    # Washer bounds are parent-verified ASME Table 11 exports, not head guesses.
    assert (spec.HANGER_WASHER.OD_MIN, spec.HANGER_WASHER.OD_MAX) == (12.573, 13.081)
    assert spec.HANGER_WASHER.OD_ID_RUNOUT_MAX == pytest.approx(0.3302)
    assert spec.HANGER_WASHER_CONCENTRIC_ANNULUS_MIN == pytest.approx(3.199)
    assert part.STUD_Z_REAR + spec.HANGER_SPOTFACE_DIA_MAX/2 < part.INNER_Z+part.GUSSET


def test_knife_hanger_wizard_seed_is_a_native_numbered_counterbore_row() -> None:
    """Farm c673e62: InitializeHole(counterbore, ANSI Inch, HexBolt, "#10")
    made CreateFeature return None. The installed ANSI Inch Hex Bolt
    counterbore table (AI_DATA_HBOLT) starts at 1/4; the socket-head one
    carries #10. The seed takes the main-built numbered socket counterbore
    pattern and stays a pure table identity: every cut is overridden."""
    import _holes
    import ch_rocker_arm_tl_c_stop_bar_spec as stop_bar
    import dt_cone_swing_platform_spec as platform

    hole = spec.HANGER_HOLE_SPEC
    assert hole.kind != "counterbore_hex"
    # swWzdCounterBore, swStandardAnsiInchSocketCapScrew.
    assert _holes._KINDS[hole.kind] == (0, 9)
    for precedent, size in (
        (stop_bar.SCREW_HOLE_SPEC, "#8"),
        (platform.HOLDDOWN_HOLE_SPEC, "#4"),
    ):
        assert (precedent.kind, precedent.size, precedent.end) == (
            hole.kind, size, hole.end,
        )
        assert set(precedent.overrides_mm) == set(hole.overrides_mm)
    # One feature, one spec: the build passes the shared spec, pins the
    # through diameter, and binds the overridden depth to HangerGrip.
    source = Path(part.__file__).read_text(encoding="utf-8")
    call = source[source.index("hanger_wizard = wizard_holes(") :]
    call = call[: call.index("\n    )\n")]
    assert "HANGER_HOLE_SPEC," in call
    assert "expect_dia_mm=HANGER_CLEARANCE_DIA" in call
    assert "HoleSpec(" not in call
    assert part.HANGER_SPOTFACE_DEPTH_DRIVE == '"RingHeight" - "HangerGrip@HangerGripReference"'
    assert "drive_jobs.append((hanger_depth, HANGER_SPOTFACE_DEPTH_DRIVE))" in source


def test_hanger_through_diameter_has_a_native_unilateral_band(monkeypatch) -> None:
    from types import SimpleNamespace

    assert spec.HANGER_CLEARANCE_DIA_BAND == (0.13, 0.0)
    assert spec.HANGER_CLEARANCE_DIA_MIN == pytest.approx(6.045)
    assert spec.HANGER_CLEARANCE_DIA_MAX == pytest.approx(6.175)
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

    # Deliberately put spot diameter and axial depth before the through dia.
    displays = [
        display("CounterBore Dia.@StudHoles", 0.017),
        display("CounterBore Depth@StudHoles", 0.001),
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
        (0.0, 0.00013), abs=1e-12,
    )
    assert displays[0].GetDimension2(0).Tolerance.Type == 0
    assert displays[1].GetDimension2(0).Tolerance.Type == 0
    assert precisions[-1]["places"] == 3

    from win32com.client import dynamic

    def length_interface(raw, kind):
        assert kind == "ICalloutLengthVariable"
        return raw

    monkeypatch.setattr(drawing, "_early_bound", length_interface)
    monkeypatch.setattr(dynamic, "Dispatch", lambda pointer: pointer)
    clearance = SimpleNamespace(VariableName="hw-thruholedia")
    spot = SimpleNamespace(VariableName="hw-cbdia", ToleranceType=0)
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
        (0.0, 0.00013), abs=1e-12,
    )
    assert raw_clearance.TolerancePrecision == 3
    assert spot.ToleranceType == 0 and raw_spot.TolerancePrecision == 0
    with pytest.raises(RuntimeError, match="through-diameter variable"):
        drawing._tolerance_hanger_callout_clearance(
            SimpleNamespace(GetHoleCalloutVariables=lambda: (raw_spot,)),
        )


def test_crossbar_median_control_cancels_the_socket_station_chain() -> None:
    assert spec.HANGER_CROSSBAR_CENTER_ZONE == 0.10
    assert spec.HANGER_CROSSBAR_CENTER_TOL == 0.05
    assert part.HANGER_BAR_HALF_WIDTH_MIN == pytest.approx(12.1)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_crossbar_median_datum(adapter, geometry_top, crossbar_width)" in source
    assert 'kinds != (14,)' in source
    assert "attached_dimension.FullName" in source and "adapter.swApp.IsSame(attached, display)" in source
    assert 'datums=("D",), quantity=HANGER_CENTER_QUALIFIER' in source
    assert 'tolerance=GEOMETRIC_TOLERANCES_MM["knife-hanger crossbar centring"]' in source
    assert "characteristic=\"position\"" in source
    # The native zone is linear, no diameter prefix; X only, Z unchanged.
    frame = source[source.index('hanger_hole_edge ='):source.index('# #946:', source.index('hanger_hole_edge ='))]
    assert "diameter=True" not in frame
    assert "HANGER_CLEARANCE_DIA / 2.0" in frame and "HANGER_SPOTFACE_FLOOR_Y" in frame
    # The axes' BASIC zero on D is stated by the frame's own qualifier, with
    # the hardware it serves; no numeric note or zero-length dimension.
    assert "BASIC ZERO ON D" in drawing.HANGER_CENTER_QUALIFIER
    assert "MHA-VN-024" in drawing.HANGER_CENTER_QUALIFIER
    assert "set_basic_dimension" not in frame


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
    assert part.STUD_Z_FRONT + spec.HANGER_SPOTFACE_DIA < 0.0 < part.STUD_Z_REAR - spec.HANGER_SPOTFACE_DIA
    assert "center=True" in block
    assert "reference=" not in block and "set_basic_dimension" not in block
    assert drawing.CROSSBAR_MEDIAN_SUFFIX.endswith(", D")
    assert (part.BAR_X0 + part.BAR_X1) / 2.0 == pytest.approx(part.HANGER_X)
    # The general .X band the seat-footprint stack charges.
    assert spec.DRAWING_REFERENCE_PRECISION["hanger x from left sockets"] == 1


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
# leader-crosses-leader: the spotface callout's diameter run and the
# centring frame's run to its default clearance-rim landing.
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
    across the spotface callout's diameter run at (182.7,201.4) mm.  It now
    lands on the same rim up-right of the axis, the frame's side of that run,
    and right of D's trace (the 182.0 extension line)."""
    centre = _plan(part.HANGER_X, part.STUD_Z_FRONT)
    radius = spec.HANGER_CLEARANCE_DIA / 2.0 * _S
    callout_a, callout_b = R5_HANGER_CALLOUT_RUN
    frame_start, old_landing = R5_HANGER_FRAME_RUN
    # The logged runs: a spotface diameter through the axis, and a run to the
    # clearance rim, crossing where R5 reported.
    assert math.dist(
        ((callout_a[0] + callout_b[0]) / 2.0, (callout_a[1] + callout_b[1]) / 2.0), centre
    ) < 0.0002
    assert math.dist(callout_a, callout_b) == pytest.approx(spec.HANGER_SPOTFACE_DIA * _S, abs=0.0002)
    assert math.dist(old_landing, centre) == pytest.approx(radius, abs=0.0002)
    assert _segment_crossing(R5_HANGER_CALLOUT_RUN, R5_HANGER_FRAME_RUN) == pytest.approx(
        (0.1827, 0.2014), abs=1e-4,
    )
    # The landing: a real point on the selected clearance rim at the spotface
    # floor, at the declared bearing, between the callout's run and D's trace.
    x, y, z = drawing.hanger_center_landing()
    assert y == spec.HANGER_SPOTFACE_FLOOR_Y
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
    assert _segment_crossing(R5_HANGER_CALLOUT_RUN, rerouted) is None
    gap = min(
        *(_point_to_segment(p, R5_HANGER_CALLOUT_RUN) for p in rerouted),
        *(_point_to_segment(p, rerouted) for p in R5_HANGER_CALLOUT_RUN),
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


def test_spotface_floor_grip_is_the_models_driving_dimension() -> None:
    assert spec.HANGER_GRIP == 35.50 == part.RING_HEIGHT-spec.HANGER_SPOTFACE_DEPTH
    assert spec.HANGER_GRIP_PLACES == 2
    assert spec.HANGER_GRIP_TOL == 0.05
    assert spec.HANGER_SPOTFACE_FLOOR_Y == pytest.approx(17.25)
    assert spec.HANGER_SPOTFACE_CLEANUP_MIN == pytest.approx(0.15)
    # The model owns the grip, its places and its band; the sheet imports it.
    assert spec.HANGER_GRIP_SKETCH == "HangerGripReference"
    assert spec.REFERENCE_SKETCHES == (spec.HANGER_GRIP_SKETCH,)
    assert spec.DRAWING_DIMENSIONS[spec.HANGER_GRIP_SKETCH] == {"HangerGrip"}
    assert spec.DRAWING_PRECISION_BY_NAME["HangerGrip"] == spec.HANGER_GRIP_PLACES
    assert (
        "hanger spotface floor from finished underside"
        not in spec.DRAWING_REFERENCE_PRECISION
    )
    # The grip drives the wizard's own spotface depth: not a witness.
    assert part.HANGER_GRIP_DIMENSION == "HangerGrip@HangerGripReference"
    assert part.HANGER_SPOTFACE_DEPTH_DRIVE == (
        '"RingHeight" - "HangerGrip@HangerGripReference"'
    )
    build = Path(part.__file__).read_text(encoding="utf-8")
    compact = "".join(build.split())
    assert 'set_global(adapter,"HangerGrip",f"{HANGER_GRIP}mm")' in compact
    assert 'grip.record("HangerGripUnderside",\'"RingHeight"/2\')' in compact
    assert 'grip.record("HangerGrip",\'"HangerGrip"\')' in compact
    assert "name_last_feature(adapter,HANGER_GRIP_SKETCH)" in compact
    body = compact[compact.index("asyncdefbuild("):]
    steps = [
        "drive_jobs+=await_author_hanger_grip_reference(adapter,grip_plane_name)",
        "drive_jobs.append((hanger_depth,HANGER_SPOTFACE_DEPTH_DRIVE))",
        "fordim_name,exprindrive_jobs:awaitdrive_dimension(adapter,dim_name,expr)",
        'set_dimension_symmetric_tolerance(adapter,HANGER_GRIP_SKETCH,"HangerGrip",HANGER_GRIP_TOL)',
        "await_assert_hanger_grip_drives_spotface(adapter,hanger_depth,volume)",
        "blank_reference_sketches(adapter,REFERENCE_SKETCHES)",
        "save_part_and_images(adapter,PART_NAME)",
    ]
    assert all(body.count(step) == 1 for step in steps)
    assert [body.index(step) for step in steps] == sorted(
        body.index(step) for step in steps
    )
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
    assert "dimensions = curate_hidden_sketch_dimensions(" in section
    assert "_require_model_hanger_grip(adapter, dimensions)" in section
    assert "source_model = adapter.currentModel" in source
    import ast

    wrappers = [
        (node, item.context_expr)
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.With)
        for item in node.items
        if isinstance(item.context_expr, ast.Call)
        and isinstance(item.context_expr.func, ast.Name)
        and item.context_expr.func.id == "part_sketches_shown"
    ]
    assert len(wrappers) == 1
    block, context = wrappers[0]
    assert [ast.unparse(argument) for argument in context.args] == [
        "adapter", "source_model", "REFERENCE_SKETCHES",
    ]
    keywords = {keyword.arg: keyword.value for keyword in context.keywords}
    assert ast.literal_eval(keywords["label"]) == "knife-hanger grip"
    assert ast.unparse(keywords["base_view"]) == "hub_bottom_parent"
    section_calls = [
        node for statement in block.body for node in ast.walk(statement)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_hanger_section"
    ]
    assert len(section_calls) == 1
    assert [ast.unparse(argument) for argument in section_calls[0].args] == [
        "adapter", "hub_bottom_parent",
    ]


def _fake_wizard(*dimensions, name="StudHoles", subs=()):
    from types import SimpleNamespace

    displays = [SimpleNamespace(GetDimension2=lambda _i, d=d: d) for d in dimensions]

    def following(display):
        index = next(i for i, item in enumerate(displays) if item is display) + 1
        return displays[index] if index < len(displays) else None

    children = list(subs)
    for index, child in enumerate(children):
        child.GetNextSubFeature = (
            lambda after=index: children[after + 1] if after + 1 < len(children) else None
        )
    return SimpleNamespace(
        Name=name,
        GetFirstDisplayDimension=lambda: displays[0] if displays else None,
        GetNextDisplayDimension=following,
        GetFirstSubFeature=lambda: children[0] if children else None,
    )


def test_spotface_depth_resolves_the_one_native_wizard_depth(monkeypatch) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(part, "_early_bound", lambda obj, _interface: obj)

    def dim(full_name, mm):
        return SimpleNamespace(FullName=full_name, SystemValue=mm / 1000.0)

    through = dim("Hole Dia@StudHoles@fr-top-frame.Part", spec.HANGER_CLEARANCE_DIA)
    spot = dim("CBORE Dia@StudHoles@fr-top-frame.Part", spec.HANGER_SPOTFACE_DIA)
    depth = dim("CBORE Depth@StudHoles@fr-top-frame.Part", spec.HANGER_SPOTFACE_DEPTH)
    wizard = _fake_wizard(through, spot, depth)
    assert part._hanger_spotface_depth_name(wizard) == "CBORE Depth@StudHoles"
    with pytest.raises(RuntimeError, match="0 spotface-depth"):
        part._hanger_spotface_depth_name(_fake_wizard(through, spot))
    with pytest.raises(RuntimeError, match="2 spotface-depth"):
        part._hanger_spotface_depth_name(_fake_wizard(depth, through, depth))
    foreign = dim("CBORE Depth@OtherHoles@fr-top-frame.Part", spec.HANGER_SPOTFACE_DEPTH)
    with pytest.raises(RuntimeError, match="not owned by StudHoles"):
        part._hanger_spotface_depth_name(_fake_wizard(foreign))


def test_spotface_depth_may_live_in_the_wizards_own_profile_sketch(monkeypatch) -> None:
    """Farm e5ad7dcd: the wizard reported its depth as
    ["C'Bore Depth", "Sketch18", ...] -- the internal profile sketch made
    between GooseneckProfile (Sketch17) and the placement Sketch19. The SDK
    feature walk includes sub-feature dimensions, so a sub-feature of
    StudHoles whose own walk holds the dimension is the genuine owner; any
    other sketch is still foreign."""
    from types import SimpleNamespace

    monkeypatch.setattr(part, "_early_bound", lambda obj, _interface: obj)

    def dim(full_name, mm):
        return SimpleNamespace(FullName=full_name, SystemValue=mm / 1000.0)

    through = dim("Thru Hole Dia.@Sketch18@Part39.Part", spec.HANGER_CLEARANCE_DIA)
    depth = dim("C'Bore Depth@Sketch18@Part39.Part", spec.HANGER_SPOTFACE_DEPTH)
    profile = _fake_wizard(through, depth, name="Sketch18")
    placement = _fake_wizard(name="Sketch19")
    wizard = _fake_wizard(through, depth, subs=(placement, profile))
    assert part._hanger_spotface_depth_name(wizard) == "C'Bore Depth@Sketch18"
    # A sketch outside StudHoles' sub-features is not its owner.
    with pytest.raises(RuntimeError, match="not owned by StudHoles"):
        part._hanger_spotface_depth_name(_fake_wizard(through, depth, subs=(placement,)))
    # Nor is a same-named sub-feature whose own walk lacks the dimension.
    empty = _fake_wizard(through, name="Sketch18")
    with pytest.raises(RuntimeError, match="not owned by StudHoles"):
        part._hanger_spotface_depth_name(
            _fake_wizard(through, depth, subs=(placement, empty))
        )
    # The builder binds the RESOLVED name, never a literal sketch.
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "Sketch18" not in source.replace(
        source[source.index("def _hanger_spotface_depth_name("):source.index(
            "\nasync def _author_hanger_grip_reference("
        )], ""
    )


_DEPTH = "CBORE Depth@StudHoles"


class _GripModel:
    """A part whose wizard depth follows HangerGrip only while ``linked``."""

    def __init__(self, *, linked=True, reference=False, equations=None):
        self.grip = part.HANGER_GRIP
        self.depth = part.RING_HEIGHT - self.grip
        self.linked = linked
        self.reference = reference
        self.equations = equations if equations is not None else {
            f'"{part.HANGER_GRIP_DIMENSION}"': [
                f'"{part.HANGER_GRIP_DIMENSION}" = "HangerGrip"'
            ],
            f'"{_DEPTH}"': [f'"{_DEPTH}"= {part.HANGER_SPOTFACE_DEPTH_DRIVE}'],
        }

    def rebuild(self):
        if self.linked:
            self.depth = part.RING_HEIGHT - self.grip

    def volume(self):
        deeper = self.depth - spec.HANGER_SPOTFACE_DEPTH
        return 1.0e6 - deeper / part.HANGER_GRIP_PROBE_MM * part.HANGER_GRIP_PROBE_VOLUME

    def Parameter(self, name):
        from types import SimpleNamespace

        value = {part.HANGER_GRIP_DIMENSION: self.grip, _DEPTH: self.depth}.get(name)
        if value is None:
            return None
        return SimpleNamespace(
            IsReference=lambda: self.reference, SystemValue=value / 1000.0
        )


def _prove_grip(monkeypatch, model):
    import asyncio
    from types import SimpleNamespace

    async def set_global(_adapter, name, expr):
        assert name == "HangerGrip"
        model.grip = float(expr.removesuffix("mm"))

    async def force_rebuild(_adapter):
        model.rebuild()

    async def volume_check(_adapter, label, expected, tol):
        if abs(model.volume() - expected) > tol:
            raise RuntimeError(f"volume {label}")
        return model.volume()

    monkeypatch.setattr(part, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(part, "set_global", set_global)
    monkeypatch.setattr(part, "force_rebuild", force_rebuild)
    monkeypatch.setattr(part, "volume_check", volume_check)
    monkeypatch.setattr(
        part, "_equations_naming", lambda _adapter, lhs: model.equations.get(lhs, [])
    )
    adapter = SimpleNamespace(currentModel=model)
    asyncio.run(part._assert_hanger_grip_drives_spotface(adapter, _DEPTH, model.volume()))


def test_hanger_grip_proof_accepts_the_live_driving_link(monkeypatch) -> None:
    model = _GripModel()
    _prove_grip(monkeypatch, model)
    # The probe restored the as-built grip.
    assert (model.grip, model.depth) == (part.HANGER_GRIP, spec.HANGER_SPOTFACE_DEPTH)


def test_hanger_grip_proof_rejects_a_witness_that_drives_nothing(monkeypatch) -> None:
    with pytest.raises(RuntimeError, match="live link"):
        _prove_grip(monkeypatch, _GripModel(linked=False))


def test_hanger_grip_proof_rejects_a_reference_grip(monkeypatch) -> None:
    with pytest.raises(RuntimeError, match="is a reference dimension"):
        _prove_grip(monkeypatch, _GripModel(reference=True))


@pytest.mark.parametrize(
    ("lhs", "equations", "match"),
    [
        (f'"{_DEPTH}"', [], "expected one equation"),
        (f'"{_DEPTH}"', [f'"{_DEPTH}" = 1.0mm'], "owned by"),
        (f'"{_DEPTH}"', [f'"{_DEPTH}" = "RingHeight" - "HangerGrip"'], "owned by"),
        (
            f'"{part.HANGER_GRIP_DIMENSION}"',
            [f'"{part.HANGER_GRIP_DIMENSION}" = 35.5mm'],
            "owned by",
        ),
        (
            f'"{part.HANGER_GRIP_DIMENSION}"',
            [f'"{part.HANGER_GRIP_DIMENSION}" = "HangerGrip"'] * 2,
            "expected one equation",
        ),
    ],
)
def test_hanger_grip_proof_rejects_a_wrong_equation(monkeypatch, lhs, equations, match) -> None:
    model = _GripModel()
    model.equations[lhs] = equations
    with pytest.raises(RuntimeError, match=match):
        _prove_grip(monkeypatch, model)


def test_hanger_grip_proof_rejects_an_off_nominal_grip(monkeypatch) -> None:
    model = _GripModel()
    model.grip = part.HANGER_GRIP - 0.01
    with pytest.raises(RuntimeError, match="reads"):
        _prove_grip(monkeypatch, model)


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
    *, full_name="HangerGrip@HangerGripReference@fr-top-frame.Part",
    mm=35.50, kind=4, band_mm=0.05, name="HangerGrip",
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
    other = _imported_grip(name="HangerPinHoleDia")
    grip = _imported_grip()
    assert drawing._require_model_hanger_grip(None, [other, grip]) is grip
    for dimensions, match in (
        ([other], "imported 0 HangerGrip"),
        ([grip, _imported_grip()], "imported 2 HangerGrip"),
        ([_imported_grip(full_name="HangerGrip@Drawing View7@x")], "not the model's"),
        ([_imported_grip(full_name="D1@HangerGripReference@x")], "not the model's"),
        ([_imported_grip(mm=35.45)], "reads"),
        ([_imported_grip(kind=2)], "symmetric band"),
        ([_imported_grip(band_mm=0.04)], "symmetric band"),
    ):
        with pytest.raises(RuntimeError, match=match):
            drawing._require_model_hanger_grip(None, dimensions)


def test_dowel_slip_hole_contract() -> None:
    assert part.PIN_HOLE_X == pytest.approx(-7.368)
    assert part.PIN_HOLE_X - part.HANGER_X == pytest.approx(spec.HANGER_PIN_X)
    assert spec.HANGER_PIN_X == 7.632
    assert spec.HANGER_PIN_X_PLACES == 3
    assert spec.DRAWING_REFERENCE_PRECISION["dowel hole from hanger axis"] == 3
    assert (spec.HANGER_PIN_HOLE_DIA, spec.HANGER_PIN_HOLE_DIA_BAND) == (3.24, (0.03, -0.03))
    assert spec.HANGER_PIN_HOLE_DEPTH == 12.0
    assert spec.HANGER_PIN_SLIP_CLEARANCE_MIN == pytest.approx(0.02738)
    assert spec.HANGER_PIN_SLIP_CLEARANCE_MAX == pytest.approx(0.09246)
    assert 0.02 <= spec.HANGER_PIN_SLIP_CLEARANCE_MIN < spec.HANGER_PIN_SLIP_CLEARANCE_MAX <= 0.10
    # drawing-guidelines.md rule 17 (walls and webs) walls and floor, print-worst (the station at its .XXX limit)
    # and after drill drift (test_hanger_walls_meet_the_target_after_drift).
    assert part.PIN_HOLE_BAR_WALL == pytest.approx(2.585978744247038)
    assert part.PIN_HOLE_SCREW_WALL == pytest.approx(2.645457488494077)
    assert part.PIN_HOLE_FLOOR_MARGIN == pytest.approx(22.65)
    assert spec.HANGER_PIN_HOLE_DEPTH < spec.HANGER_GRIP
    # The model owns the size, band and depth; the drawing imports them.
    assert spec.DRAWING_DIMENSIONS["HangerPinProfile"] == {"HangerPinHoleDia"}
    assert spec.DRAWING_DIMENSIONS["HangerPinHoles"] == {"HangerPinHoleDepth"}
    assert spec.DRAWING_PRECISION_BY_NAME["HangerPinHoleDia"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["HangerPinHoleDepth"] == 1
    assert set(drawing.HANGER_SECTION_KEEP) == {
        "HangerPinHoleDia", "HangerPinHoleDepth", "HangerGrip",
    }


def test_dowel_slot_contract() -> None:
    # The slot stands -X of each screw axis, the round hole +X: the knife
    # mount's two unchanged-SKU dowels now at +/-7.632.
    assert part.SLOT_X == pytest.approx(-22.632)
    assert part.SLOT_X - part.HANGER_X == pytest.approx(spec.HANGER_SLOT_X)
    assert spec.HANGER_SLOT_X == -7.632
    assert spec.HANGER_PIN_XS == (spec.HANGER_SLOT_X, spec.HANGER_ROUND_X)
    # Slip width = the round hole's ream; length .XXX; floor = the hole's.
    assert (spec.HANGER_SLOT_WIDTH, spec.HANGER_SLOT_WIDTH_BAND) == (3.24, (0.03, -0.03))
    assert (spec.HANGER_SLOT_LENGTH, spec.HANGER_SLOT_LENGTH_TOL) == (3.95, 0.13)
    assert spec.HANGER_SLOT_LENGTH - spec.HANGER_SLOT_LENGTH_TOL > spec.HANGER_SLOT_LENGTH_REQUIRED
    assert spec.HANGER_SLOT_DEPTH == spec.HANGER_PIN_HOLE_DEPTH
    assert part.SLOT_FLAT == pytest.approx(0.71)
    # BASIC 15.264 span, centre +/-0.13 along slot; from the bolt axis
    # the slot carries both .XXX bands.
    assert spec.HANGER_SLOT_FROM_ROUND == pytest.approx(15.264)
    assert spec.HANGER_SLOT_STATION_TOL == pytest.approx(0.26)
    # drawing-guidelines.md rule 17 (walls and webs) walls and floor, print-worst and after drill drift: both meet
    # the 2.0 target.
    assert part.SLOT_BAR_WALL == pytest.approx(2.050978744247038)
    assert part.SLOT_SCREW_WALL == pytest.approx(2.1104574884940767)
    assert part.SLOT_SCREW_WALL >= 2.0
    assert part.SLOT_FLOOR_MARGIN == pytest.approx(22.65)
    # The model owns the width and its band (front slot, on the underside
    # locator); F-F derives the station and the length.
    assert spec.DRAWING_DIMENSIONS["HangerSlotProfile"] == {"HangerSlotWidth"}
    assert spec.DRAWING_PRECISION_BY_NAME["HangerSlotWidth"] == 3
    assert "dowel slot from hanger axis" not in spec.DRAWING_REFERENCE_PRECISION
    assert spec.DRAWING_REFERENCE_PRECISION["dowel slot from dowel hole"] == 3
    assert spec.DRAWING_REFERENCE_PRECISION["dowel slot length"] == 3
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'for slot_width_name in ("HangerSlotWidth", "HangerSlot1Width"):' in source
    assert 'prefix = "HangerSlot" if station == "Front" else "HangerSlot1"' in source


def test_hanger_walls_meet_the_target_after_drift() -> None:
    """Q7 option C: the #10 holes are drilled from the faced underside and
    the slip holes and slots cut from it, located from the #10 hole's axis
    there, so each hole's
    0.3 deg drift is nil at the seat and largest at the blind floors.  Every
    wall round a slip hole or slot, at the print-worst bands and the deepest
    printed floor, less the drift of each hole either side of it, meets rule
    12's 2.0 target."""
    per_mm = math.tan(math.radians(spec.KEEPER_TAP_DRILL_WANDER_DEG))
    assert spec.DRILL_DRIFT_PER_MM == pytest.approx(per_mm)
    drift = per_mm * (spec.HANGER_PIN_HOLE_DEPTH + spec.PRINTED_LINEAR_BAND_MM[1])
    assert part.HANGER_DRIFT_AT_SLIP_FLOOR == pytest.approx(drift)
    assert drift == pytest.approx(0.0670, abs=1e-4)
    hole_r = (spec.HANGER_PIN_HOLE_DIA + max(spec.HANGER_PIN_HOLE_DIA_BAND)) / 2.0
    clearance_r = spec.HANGER_CLEARANCE_DIA_MAX/2
    slot_half = (spec.HANGER_SLOT_LENGTH + spec.HANGER_SLOT_LENGTH_TOL) / 2.0
    hole_off = spec.HANGER_PIN_X_TOL
    slot_off = hole_off + spec.HANGER_SLOT_ALONG_TOL
    outer_loss = spec.PRINTED_LINEAR_BAND_MM[spec.HANGER_CROSSBAR_WIDTH_PLACES]/2
    outer_loss += spec.HANGER_CROSSBAR_CENTER_TOL
    walls = {
        "round hole | screw hole": (
            spec.HANGER_PIN_X - hole_off - hole_r - clearance_r,
            2.0 * drift,
            part.PIN_HOLE_SCREW_WALL,
        ),
        "round hole | bar +X face": (
            part.BAR_X1 - (part.PIN_HOLE_X+hole_off) - hole_r - outer_loss,
            drift,
            part.PIN_HOLE_BAR_WALL,
        ),
        "slot | screw hole": (
            spec.HANGER_PIN_X - slot_off - slot_half - clearance_r,
            2.0 * drift,
            part.SLOT_SCREW_WALL,
        ),
        "slot | bar -X face": (
            part.SLOT_X - slot_off - slot_half - part.BAR_X0 - outer_loss,
            drift,
            part.SLOT_BAR_WALL,
        ),
    }
    for label, (print_worst, charged, wall) in walls.items():
        assert wall == pytest.approx(print_worst - charged), label
        assert wall >= 2.0, label
    # Entry wander at the deepest pocket roof and highest as-cast top.
    pocket = part.BAR_POCKET_HOLE_WALLS
    station = part._POCKET_STATION - part._POCKET_END
    assert pocket["hanger clearance hole"] == pytest.approx(
        station-clearance_r-per_mm*(part.RING_HEIGHT+0.8-(part.FLANGE-0.8))
    )
    assert pocket["hanger spotface"] == pytest.approx(
        station-spec.HANGER_SPOTFACE_DIA_MAX/2-per_mm*(part.RING_HEIGHT+0.8)
    )
    assert pocket["hanger spotface"] == pytest.approx(3.6221080914808637)
    assert pocket["hanger clearance hole"] == pytest.approx(9.327307547841905)
    assert pocket["dowel slip hole"] == pytest.approx(10.740390963820517)
    assert pocket["dowel slot"] == pytest.approx(10.715390963820517)


def test_spotface_support_and_floor_webs_charge_all_printed_limits() -> None:
    assert (spec.HANGER_SPOTFACE_DIA_MIN, spec.HANGER_SPOTFACE_DIA_MAX) == (16.49, 17.51)
    assert part.HANGER_SPOTFACE_BAR_WALL == pytest.approx(3.0996958719073833)
    assert part.HANGER_SPOTFACE_POCKET_ROOF_WEB == pytest.approx(5.35)
    assert part.HANGER_SEAT_BOLT_MISMATCH == pytest.approx(0.4117704770864468)
    assert spec.HANGER_WASHER_FLOAT_MAX == pytest.approx(
        (spec.HANGER_WASHER.ID_MAX-spec.HANGER_SCREW.SHANK_DIA_MIN)/2,
    )
    assert spec.HANGER_WASHER_FLOAT_MAX == pytest.approx(0.57404)
    assert spec.HANGER_WASHER_FLOAT_MAX > (
        spec.HANGER_WASHER.ID_MAX-spec.HANGER_SCREW.SHANK_DIA
    )/2
    assert part.HANGER_SPOTFACE_WASHER_OFFSET_MAX == pytest.approx(1.5113146051790616)
    assert part.HANGER_SPOTFACE_WASHER_SUPPORT_MIN == pytest.approx(0.1931853948209379)
    assert part.HANGER_WASHER_BEARING_MIN == pytest.approx(1.6876853948209381)
    assert part.HANGER_WASHER_BEARING_MIN > 0
    assert part.HANGER_SPOTFACE_OUTER_END_WALL == pytest.approx(30.19210809148086)
    # The largest spot fits; the smallest supports the eccentric largest washer.
    assert min(part.HANGER_SPOTFACE_BAR_WALL, part.HANGER_SPOTFACE_POCKET_ROOF_WEB) >= 2
    assert part.HANGER_SPOTFACE_WASHER_SUPPORT_MIN > 0


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
    # drawing-guidelines.md rule 5 (avoid excessive GD&T) (knife-edge system): datum B the front round hole, C the
    # rear; each slot 0.05 to its own station's hole, the other translated.
    assert spec.GEOMETRIC_TOLERANCES_MM["knife-hanger slot position"] == "0.05"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    underside = source[source.index('ddoc.ActivateSheet("UNDERSIDE")') :]
    assert underside.count("add_datum_feature(") == 1
    assert '(("B", STUD_Z_FRONT), ("C", STUD_Z_REAR))' in underside
    assert underside.count("add_feature_control_frame(") == 1
    assert '("front", STUD_Z_FRONT, ("B", "C"))' in underside
    assert '("rear", STUD_Z_REAR, ("C", "B"))' in underside
    assert "translated=datums[1:]" in underside
    assert "quantity=HANGER_SLOT_FRAME_QUANTITY," in underside
    assert drawing.HANGER_SLOT_FRAME_QUANTITY == "DOWEL SLOT"
    assert 'GEOMETRIC_TOLERANCES_MM["knife-hanger slot position"]' in underside
    assert '"HangerSlotWidth": HANGER_SLOT_WIDTH_TEXT_XY' in underside
    for name, (x, y) in {
        **drawing.HANGER_DATUM_SYMBOL_XY,
        **drawing.HANGER_SLOT_FRAME_XY,
        "slot width": drawing.HANGER_SLOT_WIDTH_TEXT_XY,
        "slot width offset": drawing.HANGER_SLOT_WIDTH_OFFSET_XY,
    }.items():
        assert 0.013 < x < TITLE_BLOCK[0] and 0.125 < y < 0.270, name


def test_overall_plan_extremes_pick_the_barrel_circles_as_entities() -> None:
    # Farm a03283b49: a sheet-point pick on the boss barrel's R22.5 plan
    # outline resolved to the top C2 break's R20.5 circle 2.0 inside it
    # (width 435 for 439).  Both overall dimensions select the scanned
    # R22.5 circles, on the upper boss's C2 lower circle plane.
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
        (0.1609, 0.2557, 0.1925, 0.2602)
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


def _slot_frame_layout():
    """Each slot frame's (outline, end, end centre, landing, leader runs)."""
    from _layout_geometry import Box, Segment

    centre, m_per_mm = drawing.HUB_BOTTOM_CENTER, drawing._HUB_BOTTOM_M_PER_MM
    ox0, oy0, ox1, oy1 = drawing.HANGER_SLOT_FRAME_OUTLINE
    layout = {}
    for station, station_z in (("front", part.STUD_Z_FRONT), ("rear", part.STUD_Z_REAR)):
        fx, fy = drawing.HANGER_SLOT_FRAME_XY[station]
        outline = Box(fx + ox0, fy + oy0, fx + ox1, fy + oy1)
        slot = (centre[0] + part.SLOT_X * m_per_mm, centre[1] + station_z * m_per_mm)
        knee = drawing.hanger_slot_frame_knee((fx, fy), slot)
        end = 1.0 if knee[0] > slot[0] else -1.0
        end_centre = (slot[0] + end * part.SLOT_FLAT / 2.0 * m_per_mm, slot[1])
        landing = drawing.hanger_slot_landing(end_centre, knee)
        shoulder_x = outline.xmin if knee[0] < outline.xmin else outline.xmax
        runs = [Segment(shoulder_x, knee[1], *knee), Segment(*knee, *landing)]
        layout[station] = (outline, end, end_centre, landing, runs)
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


def test_slot_frames_stand_above_the_plan_clear_of_every_line() -> None:
    # Machinist review of 11783475: inside the plan the frames and their
    # leaders crossed F-F, the datum leaders and the land's dimension.  Both
    # now stand above the plan, each leader running from its outline's end
    # to the slot's end arc facing it.
    from _layout_geometry import Box, Segment, segment_box_distance

    ink = drawing.INK_CLEARANCE
    centre, m_per_mm = drawing.HUB_BOTTOM_CENTER, drawing._HUB_BOTTOM_M_PER_MM
    layout = _slot_frame_layout()
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
    # The land's 72.0: extension lines from y 143.97 to 163.83 mm and its line
    # at y 145 with 6.35 mm arrow tails outside them (40d9d030e render, when
    # it was 70.0; its ends follow the lands).
    land = [centre[0] + x * m_per_mm for x in (part.LAND_X0, part.LAND_X1)]
    lines["72.0 line"] = Segment(land[0] - 0.00635, 0.145, land[1] + 0.00635, 0.145)
    for x in land:
        lines[f"72.0 extension {x:.4f}"] = Segment(x, 0.14397, x, 0.16383)
    # The slot width's extension lines, from the front slot's flats to its line.
    width_x, width_y = drawing.HANGER_SLOT_WIDTH_TEXT_XY
    half_w = drawing.HANGER_SLOT_WIDTH / 2.0 * m_per_mm
    inner_end = centre[0] + (part.SLOT_X + part.SLOT_FLAT / 2.0) * m_per_mm
    for sy in (-1.0, 1.0):
        lines[f"3.240 extension {sy:+.0f}"] = Segment(
            width_x - 0.001, width_y + sy * half_w, inner_end, width_y + sy * half_w
        )
    lines["3.240 line"] = Segment(width_x, width_y - half_w - 0.00635, width_x, width_y + half_w + 0.00635)
    # Datum tags: each leader from its rim pick to the tag point, then a 6.35
    # mm shoulder right to the letter box (C printed [136.35, 253.47]..[143.33,
    # 260.49] mm about its point (130, 257) on the 40d9d030e render), with the
    # 7 mm letter box above the point the frame test allows for as well.
    picks = {}
    for datum, station_z in (("B", part.STUD_Z_FRONT), ("C", part.STUD_Z_REAR)):
        hole = (centre[0] + part.PIN_HOLE_X * m_per_mm, centre[1] + station_z * m_per_mm)
        tag = drawing.HANGER_DATUM_SYMBOL_XY[datum]
        picks[datum] = drawing.hanger_datum_pick(hole, tag)
        lines[f"datum {datum} leader"] = Segment(*picks[datum], *tag)
        boxes[f"datum {datum} tag"] = Box(tag[0] - 0.0035, tag[1] - 0.0036, tag[0] + 0.0134, tag[1] + 0.007)
    plan_top = centre[1] + drawing.PLAN_HALF_Z * m_per_mm
    sheet = drawing.SHEET_FRAME
    radius = drawing.HANGER_SLOT_WIDTH / 2.0 * m_per_mm
    # The front leader lands on its slot's inner end, the rear on its outer.
    assert {station: entry[1] for station, entry in layout.items()} == {"front": 1.0, "rear": -1.0}
    qx0, qy0, qx1, qy1 = drawing.HANGER_SLOT_FRAME_QUANTITY_BOX
    for station, (outline, end, end_centre, landing, runs) in layout.items():
        # Codex review of 0d75ada1: each frame names its slot below it.
        fx, fy = drawing.HANGER_SLOT_FRAME_XY[station]
        name_box = Box(fx + qx0, fy + qy0, fx + qx1, fy + qy1)
        assert name_box.ymax < outline.ymin and name_box.xmax < outline.xmax, station
        # Above the plan, inside the sheet frame.
        assert name_box.ymin >= plan_top + ink, station
        assert sheet[0] + ink <= outline.xmin and outline.xmax <= sheet[2] - ink, station
        assert outline.ymax <= sheet[3] - ink, station
        for name, box in boxes.items():
            assert _box_box_gap(
                (name_box.xmin, name_box.ymin, name_box.xmax, name_box.ymax),
                (box.xmin, box.ymin, box.xmax, box.ymax),
            ) >= ink, (station, name)
        for name, line in lines.items():
            assert segment_box_distance(line, name_box) >= ink, (station, name)
        for other in layout.values():
            for run in other[4]:
                assert segment_box_distance(run, name_box) >= ink, station
        # On the end arc's half facing away from the slot's flats.
        assert math.dist(landing, end_centre) == pytest.approx(radius), station
        assert (landing[0] - end_centre[0]) * end > 0.0, station
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
                if name == "F-F cutting line" or name.startswith("3.240 extension"):
                    # The leader lands on a slot that F-F cuts, or whose
                    # width's extension lines start on it: it must not cross.
                    assert _segments_apart(run, line), (station, name)
                else:
                    assert _segment_gap(run, line) >= ink, (station, name)
    front, rear = layout["front"], layout["rear"]
    assert _box_box_gap(
        (front[0].xmin, front[0].ymin, front[0].xmax, front[0].ymax),
        (rear[0].xmin, rear[0].ymin, rear[0].xmax, rear[0].ymax),
    ) >= ink
    for a in front[4]:
        for b in rear[4]:
            assert _segment_gap(a, b) >= ink
    # The rear leader lands above F-F's cutting line, not on it.
    assert rear[3][1] > cut_y


def test_slot_width_leader_passes_left_of_the_land_dimension() -> None:
    # Machinist review of 11783475: the 3.240's leader crossed 70.0
    # FULL-THICKNESS LAND; codex review of fe1a7611: it still met the 72.0
    # line's left arrow tail.  The fe1a7611 render's leader runs from the
    # width's lower arrow tail (6.35 mm under the width's line midpoint, less
    # half the 1.09 mm line spacing) to its block's underline right end,
    # (+26.0, -12.89) mm off the offset point.
    from _layout_geometry import Box, Segment, segment_box_distance

    ink = drawing.INK_CLEARANCE
    centre, m_per_mm = drawing.HUB_BOTTOM_CENTER, drawing._HUB_BOTTOM_M_PER_MM
    tx, ty = drawing.HANGER_SLOT_WIDTH_OFFSET_XY
    wx, wy = drawing.HANGER_SLOT_WIDTH_TEXT_XY
    leader = Segment(wx, wy - 0.00055 - 0.00635, tx + 0.0260, ty - 0.01289)
    land = [centre[0] + x * m_per_mm for x in (part.LAND_X0, part.LAND_X1)]
    land_line = Segment(land[0] - 0.00635, 0.14499, land[1] + 0.00635, 0.14499)
    assert _segment_gap(leader, land_line) >= 2.0 * ink
    for x in land:
        assert _segment_gap(leader, Segment(x, 0.14397, x, 0.16383)) >= ink
    # UNDERSIDE LOCATOR: its one 33-glyph row printed 85.7 mm wide, 2.6 mm a
    # glyph; rows 4.6 mm apart and 3.6 tall below the note's top-left point.
    rows = drawing.HUB_BOTTOM_NOTE.splitlines()
    nx, ny = drawing.HUB_BOTTOM_NOTE_XY
    note = Box(
        nx, ny - 0.0046 * (len(rows) - 1) - 0.0036,
        nx + 0.0026 * max(len(row) for row in rows), ny,
    )
    assert segment_box_distance(leader, note) >= ink
    # The width's line stays left of the slot and the crossbar's outer face.
    assert drawing.HANGER_SLOT_WIDTH_TEXT_XY[0] < centre[0] + part.BAR_X0 * m_per_mm - ink


def test_pocket_length_dimension_stands_outside_the_plan() -> None:
    # The 138.0 line, its extension lines and its text stay out of the plan
    # silhouette and detail C's fence; the text block is 17.5 mm tall as farm
    # c75ac06 printed it, its widest row (CENTRED ON T) 33.9 mm by the
    # 40d9d030e render's glyphs.
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


def test_section_note_states_the_far_wall_print_worst_engagement() -> None:
    import build_fr_frame_assembly as assembly
    from _mcmaster_90280a837 import SHANK_DIA

    engagement = drawing.CROSS_SCREW_FAR_WALL_MIN_ENGAGEMENT
    # drawing-guidelines.md rule 17 (walls and webs): the printed bands only shorten the far-wall engagement, and
    # the shortest still holds 1.5D.
    assert 1.5 * SHANK_DIA <= engagement < assembly.TOP_FAR_CASTING_ENGAGEMENT
    note = drawing.CROSS_TAP_SECTION_NOTE
    assert f"{engagement:.1f} FULL THREAD" in note
    # drawing-guidelines.md rule 7 (notes: few, flagged, never a method): short notes, short of the title block and inside the frame.
    lines = note.splitlines()
    x, y = drawing.CROSS_TAP_SECTION_NOTE_XY
    assert len(lines) <= 4
    assert x + 0.0027 * max(len(line) for line in lines) < TITLE_BLOCK[0]
    # Rows print 5.56 mm apart (farm c75ac06, sheet 6 callout rows).
    bottom = y - 0.00556 * len(lines)
    assert bottom > drawing.SHEET_FRAME[1] + drawing.INK_CLEARANCE


def test_plan_note_centres_the_rail_outlines_on_the_socket_pattern() -> None:
    # The note's claim is the model's: every plan outline is +/- about the
    # socket pattern centre, which sits on the part origin.
    assert part.FRONT_COLUMN_Z == -part.REAR_COLUMN_Z
    assert part.OUTER_X - part.COLUMN_X == pytest.approx(part.COLUMN_X - part.INNER_X)
    assert part.OUTER_Z - abs(part.FRONT_COLUMN_Z) == pytest.approx(
        abs(part.FRONT_COLUMN_Z) - part.INNER_Z
    )
    note = drawing.PLAN_CENTRING_NOTE
    assert "CENTRED" in note and "4X SOCKET" in note
    lines = note.splitlines()
    x, y = drawing.PLAN_CENTRING_NOTE_XY
    # drawing-guidelines.md rule 7 (notes: few, flagged, never a method): a short note.  drawing-guidelines.md rule 14 (keep text off the part): clear of the sheet-2 ink round it
    # (4d11a94e render, metres): the frame's left edge, the 269.0 extension
    # line at y 0.12365, the 152.9 extension line at x 0.08502 and the front
    # view, whose top is y 0.09747.  Characters print 2.87 mm wide ("CROSSBAR
    # FLANGE", 15 of them over 43.1 mm), rows 5.56 mm apart.
    assert len(lines) <= 4
    right = x + 0.00287 * max(len(line) for line in lines)
    bottom = y - 0.00556 * len(lines)
    assert x > drawing.SHEET_FRAME[0] + drawing.INK_CLEARANCE
    assert y + drawing.INK_CLEARANCE < 0.12365
    assert right + drawing.INK_CLEARANCE < 0.08502
    assert bottom > 0.09747 + drawing.INK_CLEARANCE


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
    # drawing-guidelines.md rule 7 (notes: few, flagged, never a method): short notes.
    assert len(text.splitlines()) <= 2
    assert max(len(line) for line in text.splitlines()) <= 26
    assert drawing.HANGER_SECTION_CALLOUTS["HangerPinHoleDia"] == text


def test_spotfloor_grip_band_names_its_function_and_mate() -> None:
    """Rule 4 (tighten only for function, and name the mate): the 35.50
    +/-0.05 grip sets the MHA-VN-024 bolt's reach into the knife mount's
    tap; the callout says so at the dimension, in four short rows."""
    text = spec.HANGER_GRIP_CALLOUT
    assert (spec.HANGER_GRIP, spec.HANGER_GRIP_TOL) == (35.50, 0.05)
    assert "MHA-VN-024" in text and "THREAD ENGAGEMENT" in text
    assert "FINISHED UNDERSIDE" in text and text.startswith("2X SPOTFACE FLOOR")
    assert len(text.splitlines()) <= 4
    assert max(len(line) for line in text.splitlines()) <= 23
    assert drawing.HANGER_SECTION_CALLOUTS["HangerGrip"] == text


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
    # location.  The slot now stands BASIC 14.200 from the round hole beside
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


def test_slot_basic_note_completes_both_stations_frames() -> None:
    # Codex review of a3735691 (sheet 6): F-F's bare box located the rear
    # slot only and left the frames' orientation to the B-C line implied.
    # Codex review of 87d93d70: a slot's plain position frame holds only its
    # width's median plane, leaving the basic along the slot untoleranced;
    # codex review of 0bb6ba81: a note saying the frames' zone held both ways
    # gave that direction no control; codex review of 080fda97: the frames
    # need the basic.  The note states both stations' basic, the 90 degrees
    # and the slot centre's tolerance along the slot, the title block's .XXX
    # band the spec's slot-to-screw wall stack charges (+-0.025 read as
    # over-specification, 50fe7633); the 7.100 names the round holes it
    # locates.
    note = drawing.SLOT_BASIC_NOTE
    assert f"BASIC {spec.HANGER_SLOT_FROM_ROUND:.3f} FROM" in note
    assert "B (FRONT), C (REAR)" in note and "90 DEG TO B-C LINE" in note
    assert note.splitlines()[-1] == spec.HANGER_SLOT_ALONG_CALLOUT == "CENTRE \u00b10.13 ALONG SLOT"
    assert "POSITION" not in note
    assert spec.HANGER_SLOT_ALONG_TOL == spec.PRINTED_LINEAR_BAND_MM[3]
    assert spec.HANGER_SLOT_STATION_TOL == pytest.approx(
        spec.HANGER_PIN_X_TOL + spec.HANGER_SLOT_ALONG_TOL
    )
    # The 7.100 names the round holes it locates and, codex review of
    # 07527cf4, their transverse station: the screw axis's own Z.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'suffix="2X ROUND HOLE FROM\\nSCREW AXIS, SAME Z"' in source
    # drawing-guidelines.md rule 7 (notes: few, flagged, never a method), and drawing-guidelines.md rule 14 (keep text off the part) against the a3735691 sheet-6 ink (metres): F-F's
    # 7.100 block top 0.1133, the 72.0 block's underline 0.13663, detail C's
    # fence (r 0.076 about its centre) at its nearest over the note's rows.
    # Rows print 4.6 mm apart and 3.6 tall, 2.45 mm a glyph (87d93d70).
    lines = note.splitlines()
    x, y = drawing.SLOT_BASIC_NOTE_XY
    assert len(lines) <= 4
    right = x + 0.00245 * max(len(line) for line in lines)
    bottom = y - 0.0046 * (len(lines) - 1) - 0.0036
    ink = drawing.INK_CLEARANCE
    assert y + ink < 0.13663
    assert bottom > 0.1133 + ink
    cx, cy = drawing.HUB_DETAIL_CENTER
    fence_x = cx - math.sqrt(0.076**2 - (cy - y) ** 2)
    assert right + ink < fence_x


def test_slip_hole_callout_is_parked_clear_of_the_section() -> None:
    # drawing-guidelines.md rule 14 (keep text off the part) (dda9a33a8 render): the four-line callout stood across the hole's
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
    assert '{"HangerPinHoleDia": HANGER_PIN_DIA_OFFSET_XY, "HangerGrip": ' in source, (
        "the slip-hole size must be offset onto its leader"
    )


def test_build_places_the_hanger_section_on_the_underside_sheet() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    underside = source[source.index('ddoc.ActivateSheet("UNDERSIDE")') :]
    assert "_hanger_section(adapter, hub_bottom_parent)" in underside
    assert "imported_annotations += hanger_dimensions" in underside


def test_hanger_callout_names_the_spotface_side_without_a_method() -> None:
    """The native callout keeps its variable-driven diameter/extent rows,
    names the spotface side as geometry (TOP SPOTFACE) and carries no
    drilling method (drawing-guidelines.md rule 7 (notes: few, flagged,
    never a method)) and no cast-top depth."""
    import ast

    native = (
        "<MOD-DIAM> <hw-thruholedia> <hw-thru>\n"
        "<HOLE-SPOT><MOD-DIAM> <hw-cbdia> <HOLE-DEPTH> <hw-cbdepth>"
    )
    definitions = {5: native, 6: "", 7: "", 8: ""}
    rewritten = drawing._hanger_spotface_callout_definitions(definitions)
    assert rewritten[5] == (
        "<MOD-DIAM> <hw-thruholedia> <hw-thru>\nTOP SPOTFACE <MOD-DIAM> <hw-cbdia>"
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "DRILL FROM UNDERSIDE" not in source
    assert not hasattr(drawing, "HANGER_DRILL_CALLOUT")
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
            and keyword.value.value == "2X #10 loose hanger washer spotfaces"
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
    # MATCHES MHA-FR-001 ran across the left rail and the extension lines.
    # Text as the 40d9d030e render's glyphs measure it: 28.0 FRONT HANGER Z
    # printed [42.9, 204.4]..[81.3, 213.5] mm about (62, 209); three rows
    # stand 14.7 mm tall, MHA-FR-001 25.6 wide and HANGER Z 22.4; an offset
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
    assert 'suffix="2X POCKET, E-E\\nCENTRED ON T"' in source
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


def test_keeper_facing_note_is_the_part_property_carrying_the_keeper_budget() -> None:
    import ast

    budget = keeper.KEEPER_SEAT_FLATNESS_BUDGET_MM
    assert budget == 0.04
    # The frame imports the keeper's budget; the keeper never imports the frame.
    assert spec.KEEPER_SEAT_FLATNESS_BUDGET_MM is budget
    assert "fr_top_frame_spec" not in Path(keeper.__file__).read_text(encoding="utf-8")
    # One requirement on one face: the whole keeper-rail top between its
    # bosses, named as the print names that rail, with the function that
    # needs it.  No region size, no edge margin, no setup method (machinist
    # review r13); drawing-guidelines.md rule 7 (notes: few, flagged, never a method)'s four rows at most.
    assert spec.DRAWING_NOTES_B.splitlines() == [
        "RIGHT RAIL TOP BETWEEN BOSSES",
        "(MHA-CH-007 KEEPER SEATS):",
        "FLAT WITHIN 0.04, Ra 3.2 UM,",
        "SO BOTH KEEPER BORES ALIGN.",
    ]
    tree = ast.parse(Path(spec.__file__).read_text(encoding="utf-8"))
    (notes,) = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and [ast.unparse(target) for target in node.targets] == ["DRAWING_NOTES_B"]
    ]
    sourced = {
        value.value.id
        for value in ast.walk(notes)
        if isinstance(value, ast.FormattedValue) and isinstance(value.value, ast.Name)
    }
    assert sourced == {"KEEPER_SEAT_FLATNESS_BUDGET_MM", "SEAT_UM"}
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
    for forbidden in ("BETWEEN BOSSES", "FLAT WITHIN", "KEEPER SEATS", "Ra 3.2"):
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


def test_keeper_feet_stay_on_the_faced_rail_top_and_keep_their_ligaments() -> None:
    assert part.WEB_T == 13.0
    assert (part.WEB_IN_X, part.WEB_OUT_X) == pytest.approx((190.5, 203.5))
    assert (part.HALF_H, part.FLANGE, part.FLANGE_BOT_Y) == pytest.approx(
        (18.25, 8.0, 10.25)
    )
    assert part.KEEPER_TAP_THREAD_WALL_MARGIN == pytest.approx(1.6241775880068343)
    assert part.KEEPER_TAP_DRILL_WALL_MARGIN == pytest.approx(1.645596762049888)
    assert part.KEEPER_FOOT_BOSS_MARGINS == pytest.approx((1.496, 2.504), abs=0.0005)
    # Along the rail the faced top runs boss to boss, so the fitted foot
    # stays on it exactly when it clears the bosses at the printed bands.
    assert part.KEEPER_FOOT_PRINTED_BOSS_MARGINS == pytest.approx((0.150, 0.640))
    assert part.KEEPER_FOOT_RAIL_MARGINS == pytest.approx((4.996, 6.004), abs=0.0005)
    # Across it the widest printed foot, at the farthest printed fit-up
    # offset from the web, stays inside the narrowest printed flange less
    # the largest printed C2 top-rim leg.
    places = spec.DRAWING_REFERENCE_PRECISION
    band = spec.PRINTED_LINEAR_BAND_MM
    width_places = places["side flange width"]
    chamfer_places = places["top rim chamfer"]
    foot_places = keeper.DRAWING_PRECISION["Foot"]["Depth"]
    half_flange = (round(part.RAIL_W_SIDE, width_places) - band[width_places]) / 2.0
    offset = (
        abs(round(keeper.KEEPER_FITUP_X_FROM_WEB_MM, keeper.KEEPER_FITUP_PLACES))
        + keeper.KEEPER_FITUP_LOCATION_BAND_MM
    )
    half_foot = (round(keeper.KEEPER_WIDTH, foot_places) + band[foot_places]) / 2.0
    max_chamfer = round(part.EDGE_CHAMFER, chamfer_places) + band[chamfer_places]
    assert (half_flange, offset, half_foot, max_chamfer) == pytest.approx(
        (16.7, 2.92, 7.4, 2.8)
    )
    margin = half_flange - offset - half_foot - max_chamfer
    assert part.KEEPER_FOOT_PRINTED_FLAT_TOP_SIDE_MARGIN == pytest.approx(margin)
    assert margin == pytest.approx(3.58)
    # Faced in place: the rail-top plane stays put.
    assert part.HALF_H - part.FLANGE_BOT_Y == pytest.approx(spec.FLANGE_THICKNESS_MM)
    # Native socket and hub-bore/set-screw spotface finishes. The faced rail
    # top's SEAT_UM rides on linked note B; the cap-recess floors carry none
    # because caps seat on the tube ends, clear of the floors; the washer
    # spotfloors carry none because a clamp face neither runs nor locates.
    assert [c.key for c in spec.SURFACE_FINISHES] == [
        f"socket_{rail}_{end}" for rail in ("east", "west") for end in ("front", "rear")
    ] + ["hub_bore", "hub_set_spot_face"]
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
# height (the C2 line on farm 30394c1da: 70 characters over 30 -> 208 mm),
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
    # Flush with RD4's left edge, a clearance under the native leader
    # shoulder, which sits below the estimated box: all leader ink is above.
    assert note[0] == pytest.approx(callout_box[0])
    shoulder = callout[1] - drawing.KEEPER_CALLOUT_SHOULDER_DROP
    assert shoulder <= callout_box[1]
    assert shoulder - note[3] == pytest.approx(ink + drawing.ROUND_OUT)
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
        "(MHA-SM-002 KNIFE-MOUNT SEATS):",
        "Ra 3.2 UM; BOSS BOTTOMS AND",
        "HUB GUSSETS EXCLUDED.",
    ]
    assert _config.parts("sm-knife-mount")["number"] == "MHA-SM-002"
    tree = ast.parse(Path(spec.__file__).read_text(encoding="utf-8"))
    (notes,) = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and [ast.unparse(target) for target in node.targets] == ["DRAWING_NOTES_C"]
    ]
    sourced = {
        value.value.id
        for value in ast.walk(notes)
        if isinstance(value, ast.FormattedValue) and isinstance(value.value, ast.Name)
    }
    assert sourced == {"SEAT_UM"}
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


def test_underside_facing_note_stands_beside_detail_c_clear_of_all_ink() -> None:
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
    # Detail C's circular fence: the parent's fence radius at the detail scale.
    parent_r = (part.HUB_GUSSET_HALF_OUT + part.HUB_BOSS_DROP) * m_per_mm
    detail_r = parent_r * (
        drawing.HUB_DETAIL_SCALE[0] / drawing.HUB_DETAIL_SCALE[1]
    ) / (drawing.HUB_BOTTOM_SCALE[0] / drawing.HUB_BOTTOM_SCALE[1])
    cx, cy = drawing.HUB_DETAIL_CENTER
    nearest = (min(max(cx, note[0]), note[2]), min(max(cy, note[1]), note[3]))
    assert math.dist(nearest, (cx, cy)) >= detail_r + ink
    # Printed text on the 40d9d030e render (sheet mm): the DETAIL C / SCALE
    # 2:1 caption, the Ø30.0 CYLINDRICAL BOSS text, the 7.0 gusset block,
    # the 72.0 land block, F-F's 7.100 block and the locator's label.
    for label, box in {
        "detail caption": (0.2844, 0.0753, 0.3161, 0.0898),
        "boss diameter": (0.1889, 0.0954, 0.2310, 0.1045),
        "gusset thickness": (0.3689, 0.2356, 0.4112, 0.2503),
        "land": (0.1243, 0.1376, 0.1856, 0.1523),
        "slot depth": (0.1396, 0.0986, 0.1805, 0.1133),
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
