"""Offline contracts for the top-frame geometry and drawing."""

from __future__ import annotations

import ast
import functools
import inspect
import math
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
    TOP_FRAME_MID_Y,
    TOP_SCREW_Y,
    TUBE_CROSS_HOLE_DIAMETER,
)
from fr_vn_tube_frame_cap_spec import MAX_OUTER_DIAMETER
import fr_top_frame_spec as spec
import fr_tube_frame_spec
from _inch_wall_limits import WALL_TARGET_MM
from _paths import CAD_ROOT
from machinist_exceptions import load_exceptions
from test_pd_transgear_adapter_contract import SDK, _tree

GENERATED = SDK / "adapters" / "_generated" / "sldworks_2026.py"


@functools.cache
def _interfaces() -> dict[str, ast.ClassDef]:
    return {
        node.name: node for node in _tree(GENERATED).body
        if isinstance(node, ast.ClassDef)
    }


def _property_map(cls: ast.ClassDef, name: str) -> dict[str, ast.expr]:
    assignments = [
        node for node in cls.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
    ]
    assert len(assignments) == 1, f"{cls.name}: missing/ambiguous {name}"
    value = assignments[0].value
    assert isinstance(value, ast.Dict)
    return {ast.literal_eval(key): entry for key, entry in zip(value.keys, value.values, strict=True)}


@functools.cache
def _members(interface: str):
    """(methods, getters, setters) of a generated SolidWorks interface."""
    cls = _interfaces()[interface]
    methods = {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}
    return methods, _property_map(cls, "_prop_map_get_"), _property_map(cls, "_prop_map_put_")


def test_nominal_corner_bores_and_cap_recesses_clear_the_installed_stack() -> None:
    assert part.BORE_DIA == COLUMN_SOCKET_DIAMETER == pytest.approx(25.5016)  # 1.004
    assert part.CAP_RECESS_DIAMETER == CAP_RECESS_DIAMETER
    assert part.CAP_RECESS_DEPTH == CAP_RECESS_DEPTH
    assert CAP_RECESS_DIAMETER > MAX_OUTER_DIAMETER
    # Owner ruling 2026-11-06: the recess diameter prints 1.083 under the
    # title block's .XXX, no explicit band; its smallest printed recess
    # still clears the largest MHA-FR-VN-54 skirt by .0125.
    assert not hasattr(part, "CAP_RECESS_DIAMETER_BAND")
    places = spec.DRAWING_PRECISION["CapRecessProfile"]["CapRecessDia"]
    assert places == 3
    assert part.CAP_RECESS_DIAMETER_MIN == pytest.approx(
        spec.printed_limit(CAP_RECESS_DIAMETER, places, -1.0)
    )
    assert part.CAP_RECESS_DIAMETER_MIN == pytest.approx(1.078 * 25.4)
    assert part.CAP_RECESS_DIAMETER_MAX == pytest.approx(1.088 * 25.4)
    assert math.isclose(
        part.CAP_RECESS_DIAMETRAL_CLEARANCE,
        part.CAP_RECESS_DIAMETER_MIN - MAX_OUTER_DIAMETER,
        abs_tol=1e-12,
    )
    assert math.isclose(part.CAP_RECESS_DIAMETRAL_CLEARANCE, 0.317432, abs_tol=1e-6)
    assert math.isclose(
        CAP_RECESS_DIAMETER - MAX_OUTER_DIAMETER, 0.444432, abs_tol=1e-6
    )
    # CAD reference clearance is unchanged; actual sockets are matched to
    # their assigned tubes rather than accepted against a fixed bore band.
    assert math.isclose(
        part.BORE_DIA - fr_tube_frame_spec.OUTER_DIA,
        0.1016,
        abs_tol=1e-9,
    )
    assert part.CAP_RECESS_FLOOR_Y - (spec.SCREW_AXIS_Y + part.SIDE_TAP_DRILL_DIA / 2.0) > 0.0
    assert part.CAP_RECESS_DEPTH_BAND == pytest.approx((0.254, 0.0))
    recess_floor_world = TOP_FRAME_MID_Y + part.CAP_RECESS_FLOOR_Y
    assert math.isclose(CAP_MOUTH_Y - recess_floor_world, 1.45415, abs_tol=1e-6)
    assert math.isclose(
        recess_floor_world - (TOP_SCREW_Y + TUBE_CROSS_HOLE_DIAMETER / 2.0),
        4.0513,
        abs_tol=1e-6,
    )
    # The taps' plane is the attachment's TOP_SCREW_Y in the casting's frame:
    # .72 below the rail top, .90 below the .18 boss top.
    assert spec.SCREW_AXIS_Y == pytest.approx(TOP_SCREW_Y - TOP_FRAME_MID_Y)
    assert spec.SCREW_AXIS_BELOW_RAIL_TOP == pytest.approx(0.72 * 25.4)
    assert part.HALF_H + part.BOSS_ABOVE - spec.SCREW_AXIS_Y == pytest.approx(0.90 * 25.4)


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
    seat_places = spec.DRAWING_PRECISION["CounterboreRearProfile"]["CB1Dia"]
    floor_places = spec.DRAWING_REFERENCE_PRECISION[
        "counterbore floor from socket axis"
    ]
    axis_places = spec.DRAWING_REFERENCE_PRECISION["cross screw axis from boss top"]
    # Owner rulings B1, B2 and D4 (#2333): the barrel prints Ø1.77 ±.03 on
    # the faced top and is taken out below it at 2° ±1°, so its small limit
    # goes with the steepest draft and the lowest tap axis.
    boss_radius = (part.BOSS_DIA + boss_direction * spec.AS_CAST_BAND) / 2.0
    draft = math.tan(math.radians(spec.DRAFT_DEG - boss_direction * 1.0))
    axis_y = spec.SCREW_AXIS_Y + boss_direction * spec.PRINTED_LINEAR_BAND_MM[axis_places]
    counterbore_radius = (
        spec.printed_limit(part.COUNTERBORE_DIA, seat_places, seat_direction) / 2.0
    )
    floor_offset = spec.printed_limit(
        part.COUNTERBORE_FLOOR - abs(part.FRONT_COLUMN_Z), floor_places, floor_direction
    )
    # The barrel narrows below the faced top, so the mouth's lowest point is
    # searched round the counterbore's rim; the head is flush when its top
    # stays below it.
    mouth_low = min(
        math.sqrt(
            (
                boss_radius
                - (part.HALF_H - (axis_y + counterbore_radius * math.sin(theta))) * draft
            )
            ** 2
            - (counterbore_radius * math.cos(theta)) ** 2
        )
        for theta in (2.0 * math.pi * k / 720.0 for k in range(720))
    )
    recess = mouth_low - (floor_offset + part.CROSS_SCREW_HEAD_H)
    assert recess > 0.0
    assert counterbore_radius > part.CROSS_SCREW_HEAD_DIA / 2.0
    # That is with the barrel on its socket's axis.  The barrel is cast and
    # the socket machined: the bosses' ⌖Ø.06|A|B (Main's delegated ruling
    # 2026-11-11, #2333) lets the barrel stand .03 off it, which comes
    # straight off the recess.  No corner stands prouder than the product's
    # stated residual (#2516), and nominal sizes keep the head under.
    offset = spec.BOSS_POSITION_ZONE / 2.0
    assert offset == pytest.approx(0.03 * 25.4)
    assert offset - recess <= part.COUNTERBORE_PRINTED_HEAD_STANDOUT_MAX + 1e-9
    assert part.COUNTERBORE_HEAD_RECESS - offset == pytest.approx(0.2877, abs=5e-4)
    if (boss_direction, seat_direction, floor_direction) == (-1, 1, 1):
        assert recess == pytest.approx(part.COUNTERBORE_PRINTED_HEAD_RECESS)
        assert recess == pytest.approx(0.0219, abs=5e-4)
        assert offset - recess == pytest.approx(part.COUNTERBORE_PRINTED_HEAD_STANDOUT_MAX)
        assert offset - recess == pytest.approx(0.7401, abs=5e-4)  # .029


def test_counterbore_floor_keeps_rule_12_target_to_the_cap_recess() -> None:
    # Codex reviews of 67d8b2c6 and 080fda97 (sheet 4, A-A): with the floor
    # at 16.1 its outboard limit left 1.518 (.X) / 1.80 (.XX) to the cap
    # recess's deepest, widest corner, and .XXX read as over-precision
    # (63d4b5d6).  drawing-guidelines.md rule 17 (walls and webs) fixes it with
    # geometry: the floor prints .XX and every printed corner keeps .080.
    # Owner ruling 2026-11-10 (#2333, D5): the floor stands .62 from the
    # socket axis, so the head stays under the taken-out barrel's mouth at 3°.
    floor_places = spec.DRAWING_REFERENCE_PRECISION["counterbore floor from socket axis"]
    axis_places = spec.DRAWING_REFERENCE_PRECISION["cross screw axis from boss top"]
    seat_places = spec.DRAWING_PRECISION["CounterboreRearProfile"]["CB1Dia"]
    assert floor_places == 2
    assert TOP_SCREW_SEAT_Z == pytest.approx(127.762)  # .62 off 4.410
    floor_offset = spec.printed_limit(
        part.COUNTERBORE_FLOOR - abs(part.FRONT_COLUMN_Z), floor_places, -1.0
    )
    recess_radius = part.CAP_RECESS_DIAMETER_MAX / 2.0
    recess_floor = part.CAP_RECESS_FLOOR_Y - part.CAP_RECESS_DEPTH_BAND[0]
    rim = (
        spec.SCREW_AXIS_Y
        + spec.PRINTED_LINEAR_BAND_MM[axis_places]
        + spec.printed_limit(part.COUNTERBORE_DIA, seat_places, 1.0) / 2.0
    )
    ligament = math.hypot(floor_offset - recess_radius, recess_floor - rim)
    assert ligament == pytest.approx(part.COUNTERBORE_PRINTED_CAP_LIGAMENT)
    assert ligament == pytest.approx(2.2317, abs=5e-4)  # .0879
    assert ligament >= 2.032
    assert part.COUNTERBORE_PRINTED_NEAR_WALL >= 2.032
    assert part.COUNTERBORE_PRINTED_NEAR_WALL == pytest.approx(2.6797, abs=5e-4)  # .1055
    assert part.COUNTERBORE_PRINTED_HEAD_RECESS > 0.0
    # The floor may go this much deeper before that ligament reaches .080:
    # less than the head's worst printed standout with the barrel .03 off its
    # socket, so no floor closes it (the residual is the owner's, #2516).
    spare = (floor_offset - recess_radius) - math.sqrt(2.032**2 - (recess_floor - rim) ** 2)
    assert spare == pytest.approx(0.2769, abs=5e-4)
    assert spare < part.COUNTERBORE_PRINTED_HEAD_STANDOUT_MAX


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
    # Owner rulings B2 and D3 (#2333): the thinnest printed web, .51 -.03,
    # with its centre plane the half of its ⌖.06|A|B off the socket axes the
    # tap stands on, still holds the wall target about the thread and drill.
    web_half = (spec.WEB_T - spec.AS_CAST_BAND) / 2.0 - spec.RAIL_WEB_POSITION_ZONE / 2.0
    assert web_half == pytest.approx(5.334)  # .210
    assert part.SIDE_TAP_THREAD_WALL_MARGIN == pytest.approx(web_half - major_dia / 2.0)
    assert part.SIDE_TAP_DRILL_WALL_MARGIN == pytest.approx(
        web_half - part.SIDE_TAP_DRILL_DIA / 2.0
    )
    assert part.SIDE_TAP_THREAD_WALL_MARGIN == pytest.approx(2.921)  # .115
    assert part.SIDE_TAP_DRILL_WALL_MARGIN == pytest.approx(3.3147)  # .1305
    assert part.SIDE_TAP_THREAD_WALL_MARGIN >= WALL_TARGET_MM
    assert major_dia / 2.0 < part.HALF_H - abs(spec.SCREW_AXIS_Y)


def test_smaller_bosses_leave_real_plan_corners_and_the_outward_foot_seat() -> None:
    assert part.BOSS_DIA == spec.BOSS_DIA == pytest.approx(44.958)  # 1.77
    assert part.BORE_DIA == pytest.approx(25.5016)
    assert part.CAP_RECESS_DIAMETER == pytest.approx(27.5082)
    assert (part.BOSS_DIA - part.CAP_RECESS_DIAMETER) / 2.0 == pytest.approx(8.7249)
    assert (
        math.hypot(part.RAIL_W_SIDE / 2.0, part.RAIL_W_FR / 2.0) > part.BOSS_DIA / 2.0
    )
    assert drawing.PLAN_HALF_X - part.OUTER_X == pytest.approx(5.334)
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
    # #1038: the .300 pitch stands each keeper 5.715 further out.
    assert part.KEEPER_TAP_Z_FRONT == pytest.approx(-89.1499, abs=0.0005)
    assert part.KEEPER_TAP_Z_REAR == pytest.approx(88.1421, abs=0.0005)
    assert part.KEEPER_FOOT_TIP_Z_FRONT == pytest.approx(-93.7219, abs=0.0005)
    assert part.KEEPER_FOOT_TIP_Z_REAR == pytest.approx(92.7141, abs=0.0005)
    # Owner ruling K5 (#1038): the feet end past the unrelieved barrels'
    # inboard edges, on the faced top the two west reliefs carry into them;
    # each margin runs to its relief's step, a chord off the socket axis.
    unrelieved = (
        part.KEEPER_FOOT_TIP_Z_FRONT - (part.FRONT_COLUMN_Z + part.BOSS_DIA / 2.0),
        (part.REAR_COLUMN_Z - part.BOSS_DIA / 2.0) - part.KEEPER_FOOT_TIP_Z_REAR,
    )
    assert max(unrelieved) < 0.0
    assert part.KEEPER_FOOT_BOSS_MARGINS == pytest.approx(
        tuple(margin + spec.KEEPER_BOSS_RELIEF_DEPTH for margin in unrelieved)
    )
    assert min(part.KEEPER_FOOT_BOSS_MARGINS) >= 1.016
    assert min(part.KEEPER_FOOT_PRINTED_BOSS_MARGINS) > 0.0
    stock_major = FILLISTER_SIZE[0]
    half_major = stock_major / 2.0
    assert part.KEEPER_TAP_BOSS_MARGINS == pytest.approx(
        (
            part.KEEPER_TAP_Z_FRONT - part.KEEPER_RELIEF_STEP_Z_FRONT - half_major,
            part.KEEPER_RELIEF_STEP_Z_REAR - part.KEEPER_TAP_Z_REAR - half_major,
        )
    )
    assert min(part.KEEPER_TAP_BOSS_MARGINS) > 0.0


def test_keeper_relief_is_a_chord_step_that_leaves_the_cap_recess_its_wall() -> None:
    """Owner ruling 2026-11-11 (#1038, K5): the two west barrels' proud .18
    is machined off inboard of a chord .67 from the socket axis.  The step
    lies inside every printed barrel, outside the cap recess by the wall
    target at the print's limits, and the cut stays over the faced top."""
    chord = spec.KEEPER_BOSS_RELIEF_FROM_SOCKET
    assert chord / spec.IN == pytest.approx(0.67)
    assert spec.KEEPER_BOSS_RELIEF_DEPTH == pytest.approx(part.BOSS_DIA / 2.0 - chord)
    assert 5.0 <= spec.KEEPER_BOSS_RELIEF_DEPTH <= 6.0  # the owner's "about 5 mm"
    assert math.hypot(chord, spec.KEEPER_BOSS_RELIEF_HALF_CHORD) == pytest.approx(
        part.BOSS_DIA / 2.0
    )
    assert (part.KEEPER_RELIEF_STEP_Z_FRONT, part.KEEPER_RELIEF_STEP_Z_REAR) == (
        pytest.approx(part.FRONT_COLUMN_Z + chord),
        pytest.approx(part.REAR_COLUMN_Z - chord),
    )
    band = spec.PRINTED_LINEAR_BAND_MM[spec.KEEPER_BOSS_RELIEF_PLACES]
    # The smallest barrel, off its socket by the bosses' position, still
    # reaches past the farthest printed chord.
    least_barrel = (part.BOSS_DIA - spec.AS_CAST_BAND - spec.BOSS_POSITION_ZONE) / 2.0
    assert part.KEEPER_RELIEF_BARREL_OVERLAP == pytest.approx(
        least_barrel - chord - band
    )
    assert part.KEEPER_RELIEF_BARREL_OVERLAP > 0.0
    # The nearest printed chord against the largest printed recess, its axis
    # the title block's .XXX off the socket's.
    wall = (
        chord
        - band
        - part.CAP_RECESS_DIAMETER_MAX / 2.0
        - spec.PRINTED_LINEAR_BAND_MM[3]
    )
    assert part.KEEPER_RELIEF_CAP_RECESS_WALL == pytest.approx(wall)
    assert wall >= part.WALL_TARGET_MM
    # On the boss top the recess's mouth lead-in, at its largest printed
    # leg, and the step's own title-block .010 break come off that wall.
    # The land left, .071, is over the .060 floor and under the .080
    # target: owner ruling 2026-11-20 (Pedro), #2626 option (a), accepts it
    # as an advisory shortfall (RV-13).  The former .03 lead-in left 1.803
    # before that break was charged (codjiflo, PR #2599).
    assert part.BORE_CHAMFER / spec.IN == pytest.approx(0.02)
    mouth_places = spec.DRAWING_REFERENCE_PRECISION["top bore mouth chamfer"]
    mouth_max = part.BORE_CHAMFER + spec.PRINTED_LINEAR_BAND_MM[mouth_places]
    assert part.KEEPER_RELIEF_RECESS_MOUTH_LAND == pytest.approx(
        wall - mouth_max - part.TITLE_BLOCK_EDGE_BREAK_MAX
    )
    assert part.KEEPER_RELIEF_RECESS_MOUTH_LAND == pytest.approx(1.8034, abs=5e-4)
    assert part.WALL_FLOOR_MM <= part.KEEPER_RELIEF_RECESS_MOUTH_LAND
    assert part.KEEPER_RELIEF_RECESS_MOUTH_LAND < part.WALL_TARGET_MM
    (exception,) = [
        entry
        for entry in _config.parts("fr-top-frame")["machinist_exceptions"]
        if entry["id"] == "RV-13"
    ]
    assert exception["kind"] == "minor"
    assert "#2626" in exception["reason"] and ".071" in exception["reason"]
    assert wall - (0.03 * spec.IN + spec.PRINTED_LINEAR_BAND_MM[mouth_places]) < (
        part.WALL_TARGET_MM
    )
    assert chord - part.CAP_RECESS_DIAMETER / 2.0 == pytest.approx(3.2639)
    # The relief removes only the band over the faced top: the cross screws
    # and the cast datum targets lie under it.
    assert part.SCREW_AXIS_Y + part.COUNTERBORE_MAX_RADIUS < part.HALF_H
    assert part.DATUM_TARGET_Y < -part.HALF_H
    # Two caps of the proud band, less its taken-out draft and rim break.
    prism = 2.0 * part._circle_cap_area(part.BOSS_DIA / 2.0, chord) * part.BOSS_ABOVE
    assert 0.85 * prism < part._keeper_relief_removal() < prism
    # Each foot's outboard end rests on the relief's floor, inside the
    # barrel's cast footprint, so the floor is the faced top and the step's
    # root is held under the foot tip's stand-off at the printed limits (the
    # title block's R.040 would not be: codjiflo, PR #2599).
    assert part.KEEPER_FOOT_TIP_Z_FRONT < part.FRONT_COLUMN_Z + part.BOSS_DIA / 2.0
    assert part.KEEPER_FOOT_TIP_Z_REAR > part.REAR_COLUMN_Z - part.BOSS_DIA / 2.0
    root = spec.KEEPER_BOSS_RELIEF_ROOT_R_MAX
    assert root / spec.IN == pytest.approx(0.02)
    assert part.KEEPER_FOOT_RELIEF_ROOT_MARGIN == pytest.approx(
        min(part.KEEPER_FOOT_PRINTED_BOSS_MARGINS) - root
    )
    assert part.KEEPER_FOOT_RELIEF_ROOT_MARGIN == pytest.approx(0.127, abs=5e-4)
    assert part.KEEPER_FOOT_RELIEF_ROOT_MARGIN > 0.0
    title_block_inside_corner = 0.040 * spec.IN
    assert title_block_inside_corner > min(part.KEEPER_FOOT_PRINTED_BOSS_MARGINS)


def test_section_a_a_locates_the_keeper_relief_step_from_its_socket_axis() -> None:
    """The step prints .67, 2X, on A-A (the cut through the two west
    bosses), native between the rear socket's axis and the step's cut-face
    line, and nothing else rides on that location; the step's mate, floor
    and root limit are its own leader callout on the front boss's step,
    over the rail and under the mouth chamfer's parked text."""
    label = "keeper relief step from socket axis"
    places = spec.DRAWING_REFERENCE_PRECISION[label]
    assert places == spec.KEEPER_BOSS_RELIEF_PLACES == 2
    assert f"{spec.KEEPER_BOSS_RELIEF_FROM_SOCKET / spec.IN:.{places}f}" == "0.67"
    # The printed band is the one the keeper foot's margin charges.
    assert part.KEEPER_PRINTED_MAX_RELIEF_FROM_SOCKET == pytest.approx(
        spec.KEEPER_BOSS_RELIEF_FROM_SOCKET + spec.PRINTED_LINEAR_BAND_MM[places]
    )
    # The step's callout: the mate by its drawing number (rule 4), the
    # faced top it runs down to (the feet's outboard ends rest on it), the
    # root's limit.  A leader note, so the location carries no requirement
    # (machinist review, farm run 20261112T014216327Z), of two rows of
    # words (rule 7; farm run 20261112T030307472Z).
    assert drawing.KEEPER_RELIEF_CALLOUT == (
        "2X MHA-CH-07 FOOT STEP TO\nFACED TOP, ROOT R.02 MAX"
    )
    scale = drawing.DETAIL_SECTION_SCALE[0] / drawing.DETAIL_SECTION_SCALE[1] / 1000.0
    axis_x = drawing.DETAIL_SECTION_CENTER[0] + part.REAR_COLUMN_Z * scale
    step_x = axis_x - spec.KEEPER_BOSS_RELIEF_FROM_SOCKET * scale
    line_x, line_y = drawing.KEEPER_RELIEF_LINE_XY
    assert line_x == pytest.approx((axis_x + step_x) / 2.0)
    # Over the boss top by at least 5 mm of paper, 5 under the chamfer's
    # dimension line (y 162) and its parked text.
    boss_top_y = (
        drawing.DETAIL_SECTION_CENTER[1] + (part.HALF_H + part.BOSS_ABOVE) * scale
    )
    assert line_y - boss_top_y > 0.005
    assert 0.162 - line_y > 0.005
    text_x, text_y = drawing.KEEPER_RELIEF_TEXT_XY
    rail_top_y = drawing.DETAIL_SECTION_CENTER[1] + part.HALF_H * scale
    chamfer_rows_bottom = drawing.BORE_CHAMFER_TEXT_OFFSET_XY[1] - 0.008
    # Printed .12 text measures 2.7 mm a character, rows 5.3 mm apart (farm
    # run 20261112T014216327Z).  The station's two rows (".67", "2X") stand
    # about their centre just left of the step, under the chamfer's rows.
    char_w, row_h = 0.0027, 0.0053
    half_w = 3 * char_w / 2.0
    assert text_x + half_w < step_x - 0.002
    assert text_y - row_h > boss_top_y + 0.003
    assert text_y + row_h < chamfer_rows_bottom
    # The callout's two rows hang from its upper-left corner: clear of the
    # station's text on the right and the front boss's recess witnesses on
    # the left, over the rail top, under the chamfer's rows.
    note_x, note_y = drawing.KEEPER_RELIEF_NOTE_XY
    rows = drawing.KEEPER_RELIEF_CALLOUT.split("\n")
    assert len(rows) == 2
    note_w = max(map(len, rows)) * char_w
    assert note_x + note_w < text_x - half_w - 0.003
    front_axis_x = drawing.DETAIL_SECTION_CENTER[0] + part.FRONT_COLUMN_Z * scale
    front_step_x = front_axis_x + spec.KEEPER_BOSS_RELIEF_FROM_SOCKET * scale
    assert front_step_x - front_axis_x > part.CAP_RECESS_DIAMETER / 2.0 * scale
    # The leader runs down-left to the front step's root from past it.
    assert note_x - front_step_x > 0.005
    assert note_y - len(rows) * row_h > rail_top_y + 0.002
    assert note_y < chamfer_rows_bottom - 0.002


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
    # The keeper prints on its own sheet's unit; the frame on this sheet's.
    overall_length = part._keeper_printed(
        keeper.OVERALL_LENGTH, overall_places, overall_direction
    )
    # Owner ruling K5 (#1038): the foot's limit is the relief step, machined
    # .67 from its own socket axis at the title block's .XX; the as-cast
    # barrel's size, position and draft no longer reach it.  The sockets
    # hold Ø.010 to each other, so the pitch the feet are located across
    # closes by that much.
    boss_radius = spec.KEEPER_BOSS_RELIEF_FROM_SOCKET + (
        boss_direction * spec.PRINTED_LINEAR_BAND_MM[spec.KEEPER_BOSS_RELIEF_PLACES]
    )
    socket_pitch = (
        part.REAR_COLUMN_Z - part.FRONT_COLUMN_Z
    ) + pitch_direction * spec.SOCKET_PATTERN_REFINEMENT_ZONE
    # C10 (ch_keeper_fitup): the front face by DRO, the rear pushed up to the
    # lever stack over a leaf; each face's deviation from the model.
    from ch_keeper_fitup import FACE_DEVIATIONS_MM

    front_inner = keeper.KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM[0] + (
        FACE_DEVIATIONS_MM["front"][(front_station_direction + 1) // 2]
    )
    rear_inner = keeper.KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM[1] + (
        FACE_DEVIATIONS_MM["rear"][(rear_station_direction + 1) // 2]
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
        assert margins == pytest.approx((0.6350, 1.3716), abs=5e-4)


def _in_corner_crop(dx: float, dz: float, triangle=part.CORNER_CROP_TRIANGLE) -> bool:
    """Whether the plan point (dx, dz) lies inside ``triangle``: by default
    the sketched flange corner crop, as offsets outward from a boss axis."""
    (x0, z0), (x1, z1), (x2, z2) = triangle

    def side(ax: float, az: float, bx: float, bz: float) -> float:
        return (bx - ax) * (dz - az) - (bz - az) * (dx - ax)

    signs = (side(x0, z0, x1, z1), side(x1, z1, x2, z2), side(x2, z2, x0, z0))
    return all(sign > 0.0 for sign in signs) or all(sign < 0.0 for sign in signs)


def test_boss_additions_match_an_independent_t_section_area_integral() -> None:
    # Owner rulings B1 and D1 (#2333): the barrel is taken out from the faced
    # top both ways, the flange rims are taken out below it and the webs are
    # added above the underside.  Count plan cells of each drafted slice, not
    # the builder's chord integrals.
    import numpy as np

    step = 0.05
    draft = math.tan(math.radians(2.0))
    radius = part.BOSS_DIA / 2.0
    count = round(2.0 * radius / step)
    offsets = (np.arange(count) + 0.5) * step - radius
    u, v = np.meshgrid(offsets, offsets, indexing="ij")  # outward from the axis
    (x0, z0), (x1, z1), (x2, z2) = part.CORNER_CROP_TRIANGLE

    def side(ax: float, az: float, bx: float, bz: float):
        return (bx - ax) * (v - az) - (bz - az) * (u - ax)

    signs = (side(x0, z0, x1, z1), side(x1, z1, x2, z2), side(x2, z2, x0, z0))
    crop = np.logical_and.reduce([sign > 0.0 for sign in signs]) | (
        np.logical_and.reduce([sign < 0.0 for sign in signs])
    )

    def flange(y: float):
        recede = (part.HALF_H - y) * draft
        ox, oz = part.RAIL_W_SIDE / 2.0 - recede, part.RAIL_W_FR / 2.0 - recede
        return (u <= ox) & (v <= oz) & ~((u < -ox) & (v < -oz)) & ~crop

    def web(y: float):
        half = part.WEB_T / 2.0 + (y + part.HALF_H) * draft
        return (u <= half) & (v <= half) & ~((u < -half) & (v < -half))

    def added(y_low: float, y_high: float, rail, slices: int = 24) -> float:
        height = (y_high - y_low) / slices
        total = 0.0
        for index in range(slices):
            y = y_low + (index + 0.5) * height
            barrel = u * u + v * v <= (radius - (part.HALF_H - y) * draft) ** 2
            total += np.count_nonzero(barrel & ~rail(y)) * step**2 * height
        return total

    def frustum(r0: float, r1: float, height: float) -> float:
        return math.pi * height / 3.0 * (r0 * r0 + r0 * r1 + r1 * r1)

    upper = frustum(radius, radius - part.BOSS_ABOVE * draft, part.BOSS_ABOVE)
    underside_radius = radius - part.RING_HEIGHT * draft
    lower = (
        added(part.FLANGE_BOT_Y, part.HALF_H, flange)
        + added(-part.HALF_H, part.FLANGE_BOT_Y, web)
        + frustum(
            underside_radius,
            underside_radius - part.BOSS_BELOW * draft,
            part.BOSS_BELOW,
        )
    )
    actual_upper, actual_lower = part._boss_add_volumes()
    assert actual_upper == pytest.approx(upper, abs=1e-6)
    assert actual_lower == pytest.approx(lower, abs=10.0)
    assert actual_upper == pytest.approx(7206.457477367682)
    assert actual_lower == pytest.approx(35474.51692689762)
    # The barrel holds Ø1.77 on the faced top and narrows either way from it.
    assert 2.0 * part._boss_radius(part.HALF_H) == pytest.approx(44.958)
    assert 2.0 * part._boss_radius(part.HALF_H + part.BOSS_ABOVE) == pytest.approx(
        44.6387, abs=5e-4
    )
    assert 2.0 * part._boss_radius(-part.HALF_H - part.BOSS_BELOW) == pytest.approx(
        41.9600, abs=5e-4
    )


def test_counterbore_and_cross_tap_volumes_match_smooth_integrals() -> None:
    # Substitute x=r*sin(theta) so the disk-chord endpoints are smooth.
    # This is independent of the builder's polar rings and linear-X grid:
    # at each height of the counterbore's disc the taken-out barrel has its
    # own radius, and the length from the floor to it integrates in closed
    # form along the barrel's chord.
    boss_radius = part.BOSS_DIA / 2.0
    counterbore_radius = part.COUNTERBORE_DIA / 2.0
    tap_radius = part.SIDE_TAP_DRILL_DIA / 2.0
    bore_radius = part.BORE_DIA / 2.0
    floor_offset = part.COUNTERBORE_FLOOR - abs(part.FRONT_COLUMN_Z)
    assert part.COUNTERBORE_PLANE > abs(part.FRONT_COLUMN_Z) + boss_radius
    draft = math.tan(math.radians(2.0))
    steps = 4096
    theta_step = math.pi / steps
    counterbore_volume = tap_volume = 0.0
    for index in range(steps):
        theta = -math.pi / 2.0 + (index + 0.5) * theta_step
        sine, cosine = math.sin(theta), math.cos(theta)
        height = part.SCREW_AXIS_Y + counterbore_radius * sine
        barrel = boss_radius - (part.HALF_H - height) * draft
        half = counterbore_radius * cosine
        counterbore_volume += (
            (
                half * math.sqrt(barrel**2 - half**2)
                + barrel**2 * math.asin(half / barrel)
                - 2.0 * half * floor_offset
            )
            * half
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
    assert counterbore_volume == pytest.approx(371.1074, abs=0.01)
    assert part._side_tap_removal() == pytest.approx(tap_volume, abs=0.01)


def test_top_rim_chamfers_cover_new_corners_and_window_mitres() -> None:
    # Every face meeting the faced top leans 2° out toward it, so each rim
    # break is the .06 leg on the top and 45° to it across an 88° edge: its
    # other leg is 1.4735 down the leaning face.
    chamfer = part.EDGE_CHAMFER
    other_leg = chamfer * math.sin(math.radians(45.0)) / math.sin(math.radians(47.0))
    assert other_leg == pytest.approx(1.4735, abs=5e-5)
    assert part._chamfer_section_area(chamfer, 88.0) == pytest.approx(
        chamfer * other_leg * math.sin(math.radians(88.0)) / 2.0
    )
    outer, window = part._top_rim_removal()
    assert outer == pytest.approx(1239.118587516318, rel=2e-4)
    # The wider bar shortens the two window rims by its extra width of break
    # (c^2 / 2 mm^2 per mm).
    assert window == pytest.approx(1542.8186551437038, rel=2e-4)
    assert part.WEB_T == pytest.approx(12.954)  # .51
    # The T roots run on the flange underside, where every web face has
    # leaned out over the pocket height and each root fills a 92° corner.
    draft = math.tan(math.radians(2.0))
    lean = part.POCKET_H * draft
    barrel = part.BOSS_DIA / 2.0 - part.FLANGE * draft
    root_chord = math.sqrt(barrel**2 - (part.WEB_T / 2.0 + lean) ** 2)
    side_run = 2.0 * (abs(part.FRONT_COLUMN_Z) - root_chord)
    front_rear_run = 2.0 * (part.COLUMN_X - root_chord)
    rib = part.HUB_RIB_W + 2.0 * lean
    land = part.LAND_X1 - part.LAND_X0 + 2.0 * lean
    outer_run = 2.0 * side_run - rib + 2.0 * front_rear_run
    window_run = outer_run - 2.0 * land
    assert root_chord == pytest.approx(20.9011, abs=5e-4)
    corner = math.radians(92.0)
    fillet_area = part.ROOT_FILLET_R**2 * (
        1.0 / math.tan(corner / 2.0) - (math.pi - corner) / 2.0
    )
    crossbar_run = 2.0 * 2.0 * (part.BAR_POCKET_Z - lean)
    assert part._t_root_add() == pytest.approx(
        fillet_area * (outer_run + window_run + crossbar_run)
    )
    assert part._t_root_add() == pytest.approx(4038.807219456511)
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
    # Exact volume against a 0.02 mm grid over the corner at three depths of
    # the taken-out flange band: its outer faces recede 2° below the faced
    # top, so the cropped right triangle's legs shrink linearly with depth
    # and Simpson's rule over the band is exact.  At every depth the flange
    # the cut leaves stands inside that level's barrel.  The faces fall
    # between grid lines, so the last cell of each run is clipped to them.
    step = 0.02
    draft = math.tan(math.radians(2.0))

    def cells(start: float, stop: float):
        """Midpoints and widths of step cells tiling [start, stop] exactly."""
        for index in range(math.ceil((stop - start) / step - 1e-9)):
            low = start + index * step
            high = min(low + step, stop)
            yield (low + high) / 2.0, high - low

    x0 = min(point[0] for point in part.CORNER_CROP_TRIANGLE)
    z0 = min(point[1] for point in part.CORNER_CROP_TRIANGLE)
    areas = []
    for depth in (0.0, part.FLANGE / 2.0, part.FLANGE):
        recede = depth * draft
        crop = 0.0
        for dx, width in cells(x0, a - recede):
            for dz, deep in cells(z0, b - recede):
                cropped = _in_corner_crop(dx, dz)
                crop += width * deep * cropped
                assert cropped or math.hypot(dx, dz) <= radius - recede, (depth, dx, dz)
        areas.append(crop)
    volume = 4.0 * part.FLANGE * (areas[0] + 4.0 * areas[1] + areas[2]) / 6.0
    assert part._corner_crop_removal() == pytest.approx(volume, abs=0.5)
    assert part._corner_crop_removal() == pytest.approx(666.5224, abs=1e-3)
    # The casting model is empty in all four nibs at mid-flange (its faces
    # 0.14 inside their faced-top stations there), solid on the barrels and
    # on the flange beside them.
    y = (part.FLANGE_BOT_Y + part.HALF_H) / 2.0
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            def at(dx: float, dz: float) -> bool:
                return part._casting_occupies(
                    sx * (part.COLUMN_X + dx), y, sz * (abs(part.FRONT_COLUMN_Z) + dz)
                )

            assert not at(a - 0.5, b - 0.5)
            assert not at(a - 0.3, (part.CORNER_SIDE_CUT + b) / 2.0)
            assert not at((part.CORNER_FR_CUT + a) / 2.0, b - 0.3)
            assert at(0.95 * radius / math.sqrt(2.0), 0.95 * radius / math.sqrt(2.0))
            assert at(a - 0.5, -16.0) and at(-16.0, b - 0.5)
    # No edge-break pick stands in a corner quadrant outside its barrel.
    for feature, (picks, _removal, _shared) in part.EXTERNAL_EDGE_BREAKS.items():
        for x, _y, z in picks:
            dx, dz = abs(x) - part.COLUMN_X, abs(z) - abs(part.FRONT_COLUMN_Z)
            assert not (dx > 0.0 and dz > 0.0 and math.hypot(dx, dz) > radius + 1e-6), (
                feature, x, z,
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


def test_flange_corner_crop_chord_holds_at_every_printed_limit() -> None:
    # Owner rulings B1/B2 (#2333): a conforming casting may pair the smallest
    # or largest Ø1.77 ±.03 barrel with each outer face anywhere in its
    # as-cast band on the faced top -- half the flange extent less half the
    # socket pitch, one pattern's -- and, on the flange underside, either
    # taken-out draft limit on the barrel and on the faces.  At all four
    # corners the crop leaves no flange outside the barrel and stays clear
    # of the printed web.
    band = spec.AS_CAST_BAND
    z_col = abs(part.FRONT_COLUMN_Z)
    side_offset = part.OUTER_X - part.COLUMN_X
    fr_offset = part.OUTER_Z - z_col
    side = (side_offset - band, side_offset + band)
    front_rear = (fr_offset - band, fr_offset + band)
    assert side == pytest.approx((16.383, 17.907), abs=5e-4)
    assert front_rear == pytest.approx((18.288, 19.812), abs=5e-4)
    assert part.CORNER_CROP_FACE_OFFSETS["side"] == pytest.approx(side)
    assert part.CORNER_CROP_FACE_OFFSETS["front/rear"] == pytest.approx(front_rear)
    for (low, high), width in ((side, part.RAIL_W_SIDE), (front_rear, part.RAIL_W_FR)):
        assert low == pytest.approx(width / 2.0 - band)
        assert high == pytest.approx(width / 2.0 + band)
    radii = ((part.BOSS_DIA - band) / 2.0, (part.BOSS_DIA + band) / 2.0)
    assert radii == pytest.approx((22.098, 22.860))
    shallow, steep = (math.tan(math.radians(degrees)) for degrees in (1.0, 3.0))
    assert part.CORNER_CROP_BOSS_R_TOP_MIN == pytest.approx(radii[0])
    assert part.CORNER_CROP_BOSS_R_MIN == pytest.approx(radii[0] - part.FLANGE * steep)
    assert part.CORNER_CROP_BOSS_R_MIN == pytest.approx(21.6720, abs=5e-5)
    apex, side_leg, fr_leg = part.CORNER_CROP_TRIANGLE
    assert apex == pytest.approx((18.907, 20.812))
    # No sketch edge lies on any printed outer face.
    assert apex[0] > side[1] and apex[1] > front_rear[1]
    assert side_leg[0] > side[1] and fr_leg[1] > front_rear[1]
    # (barrel narrowing, face recession): none on the faced top, then every
    # pair of taken-out draft limits on the flange underside.
    levels = [(0.0, 0.0)] + [
        (part.FLANGE * barrel_draft, part.FLANGE * face_draft)
        for barrel_draft in (shallow, steep)
        for face_draft in (shallow, steep)
    ]
    for sx, sz in ((1.0, 1.0), (1.0, -1.0), (-1.0, -1.0), (-1.0, 1.0)):
        axis = (sx * part.COLUMN_X, sz * z_col)
        triangle = [
            (sx * (part.COLUMN_X + px), sz * (z_col + pz))
            for px, pz in part.CORNER_CROP_TRIANGLE
        ]
        for narrowing, recession in levels:
            for radius in radii:
                for a in side:
                    for b in front_rear:
                        left = _flange_left_outside_barrel(
                            triangle,
                            axis,
                            (sx, sz),
                            radius - narrowing,
                            a - recession,
                            b - recession,
                        )
                        assert left == 0, (sx, sz, narrowing, recession, radius, a, b)
    # The printed web stays clear of the triangle at every height: half the
    # thickest web, half its median's ⌖.06 zone and its steepest added lean
    # at the flange underside put its outer face at most 9.107 off the boss
    # axis, and the chord passes outside that web corner.
    assert part.RAIL_WEB_POSITION_ZONE == pytest.approx(1.524)
    web_face = (
        (part.WEB_T + band) / 2.0
        + part.RAIL_WEB_POSITION_ZONE / 2.0
        + part.POCKET_H * steep
    )
    assert web_face == pytest.approx(9.1069, abs=5e-5)
    assert part.CORNER_CROP_WEB_FACE_MAX == pytest.approx(web_face)
    slope = (fr_leg[1] - side_leg[1]) / (fr_leg[0] - side_leg[0])
    assert side_leg[1] + (web_face - side_leg[0]) * slope > web_face


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


def _t_flange_shelf(width: float, median_offset: float) -> float:
    """A T flange underside's flat at the print's limits (owner rulings
    B1/B2): half the narrowest flange with its rims taken out at the steepest
    3°, less half the thickest web at its steepest added lean, the web
    median's offset from the flange's and the largest root radius."""
    band = spec.AS_CAST_BAND
    steep = math.tan(math.radians(3.0))
    flange_half = (width - band) / 2.0 - part.FLANGE * steep
    web_half = (part.WEB_T + band) / 2.0 + part.POCKET_H * steep
    return flange_half - web_half - median_offset - (part.ROOT_FILLET_R + band)


def test_t_flange_underside_breaks_need_a_printed_shelf() -> None:
    # A rail's web median stands within half its ⌖.06|A|B zone of the
    # socket-axis line and its flange's faces within half their ±.03 of it;
    # the crossbar's web stands a full as-cast band off its flange's median.
    # The rails' printed flats hold the printed worst leg and the sliver
    # land, so their flange undersides keep their breaks; the .99-wide
    # crossbar's does not, so its two stay unbroken at .06.
    band = spec.AS_CAST_BAND
    rail_median = part.RAIL_WEB_POSITION_ZONE / 2.0 + band / 2.0
    expected = {
        "side rail": _t_flange_shelf(part.RAIL_W_SIDE, rail_median),
        "front/rear rail": _t_flange_shelf(part.RAIL_W_FR, rail_median),
        "crossbar": _t_flange_shelf(part.BAR_X1 - part.BAR_X0, band),
    }
    assert expected == pytest.approx(
        {"side rail": 3.0401, "front/rear rail": 4.9451, "crossbar": -1.1509},
        abs=5e-5,
    )
    assert part.T_FLANGE_SHELF_PRINTED_MIN == pytest.approx(expected)
    needed = part.EDGE_BREAK_PRINTED_MAX + part.EDGE_BREAK_SLIVER_MIN
    assert needed == pytest.approx(1.878)
    assert expected["crossbar"] < needed
    assert needed <= min(expected["side rail"], expected["front/rear rail"])
    points = _external_break_points()
    draft = math.tan(math.radians(2.0))
    lean, recede = part.POCKET_H * draft, part.FLANGE * draft
    y_under = part.FLANGE_BOT_Y
    for x_bar, out in ((part.BAR_X0, -1.0), (part.BAR_X1, 1.0)):
        assert not _has_point(points, [x_bar + out * lean, y_under, 0.0])
    # Every rail flange underside keeps its break where the taken-out rims
    # stand there: the west outer and window runs, both front/rear outer
    # runs, and the hub side's runs either side of the rib.
    out_x, in_x = part.OUTER_X - recede, part.INNER_X + recede
    out_z, in_z = part.OUTER_Z - recede, part.INNER_Z + recede
    barrel = part.BOSS_DIA / 2.0 - recede
    side_cut = math.sqrt(barrel**2 - (part.RAIL_W_SIDE / 2.0 - recede) ** 2)
    rib_lo = part.GOOSENECK_Z - part.HUB_RIB_W / 2.0 - lean
    z_col = abs(part.FRONT_COLUMN_Z)
    for point in (
        [out_x, y_under, 0.0],
        [in_x, y_under, 0.0],
        [0.0, y_under, out_z],
        [0.0, y_under, -out_z],
        [-out_x, y_under, (-(z_col - side_cut) + rib_lo) / 2.0],
        [-in_x, y_under, (-in_z + rib_lo) / 2.0],
    ):
        assert _has_point(points, point), point


def test_a_crossbar_shelf_too_narrow_for_the_break_stays_sharp(monkeypatch) -> None:
    # The crossbar flange's printed flat is short of one leg and the sliver,
    # so its two underside edges stay out of its chain.  A flat that held
    # the break would add both, and their four meetings with the pocket
    # ends' leaning corners; every other chain is unchanged.
    needed = part.EDGE_BREAK_PRINTED_MAX + part.EDGE_BREAK_SLIVER_MIN
    assert part.T_FLANGE_SHELF_PRINTED_MIN["crossbar"] < needed
    base_picks, base_removal, base_shared = part.EXTERNAL_EDGE_BREAKS["CrossbarBreaks"]
    assert all(point[1] != part.FLANGE_BOT_Y for point in base_picks)
    monkeypatch.setattr(
        part,
        "T_FLANGE_SHELF_PRINTED_MIN",
        {**part.T_FLANGE_SHELF_PRINTED_MIN, "crossbar": needed},
    )
    groups, _clearance = part._external_edge_breaks()
    picks, removal, shared = groups["CrossbarBreaks"]
    lean = part.POCKET_H * math.tan(math.radians(2.0))
    for x_bar, out in ((part.BAR_X0, -1.0), (part.BAR_X1, 1.0)):
        assert _has_point(picks, [x_bar + out * lean, part.FLANGE_BOT_Y, 0.0])
    assert [point for point in picks if point[1] != part.FLANGE_BOT_Y] == base_picks
    assert len(picks) == len(base_picks) + 2
    assert removal == pytest.approx(
        base_removal
        + 2.0
        * part._chamfer_section_area(part.EDGE_CHAMFER, 92.0)
        * 2.0
        * (part.BAR_POCKET_Z - lean)
    )
    assert shared == base_shared + 4
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
        ("front", part.STUD_Z_FRONT, "front hanger z from lower sockets"),
        ("rear", part.STUD_Z_REAR, "rear hanger z from lower sockets"),
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


def test_knife_seat_footprint_charges_the_centring_on_d(monkeypatch) -> None:
    # Owner ruling 2026-11-08 (Pedro), #2144 item 11.3: the ream stands its
    # .XXX station off the #10 axis, which stands on D within ⌖.010|D (owner
    # ruling 2026-11-06), so the footprint's along-line band is D's as-cast
    # station from the west bosses' tangent (owner ruling D2) plus that
    # centring plus the station; the centring does not enter across the line.
    original = part._knife_seat_footprint(part.STUD_Z_FRONT)
    monkeypatch.setattr(
        part, "HANGER_CROSSBAR_CENTER_TOL", spec.HANGER_CROSSBAR_CENTER_TOL + 0.01
    )
    expanded = part._knife_seat_footprint(part.STUD_Z_FRONT)
    assert min(x for x, _z in expanded) == pytest.approx(
        min(x for x, _z in original) - 0.01
    )
    assert max(x for x, _z in expanded) == pytest.approx(
        max(x for x, _z in original) + 0.01
    )
    assert min(z for _x, z in expanded) == pytest.approx(min(z for _x, z in original))
    assert max(z for _x, z in expanded) == pytest.approx(max(z for _x, z in original))


def test_knife_seat_footprints_cover_the_one_pin_and_its_yaw() -> None:
    """Owner ruling 2026-11-08 (Pedro), #2144 item 11.3 (scheme S1): each
    knife mount hangs on one +X pin (its round hole, datum B), so it fits one
    way round only, and may turn about that pin until the MHA-SM-00 gauge bar
    sets it.  Along the line D's as-cast band from the west bosses' tangent, the #10
    axis's ⌖.010|D centring and the ream's .XXX station; across it the screw
    axis's band and the ream's implied-zero .XXX; each with the round hole's
    slip.  The hull holds the block's print-worst corners at the along- and
    across-line extremes, turned the title block's angular band either way,
    and the edge-break check certifies those hulls."""
    import sm_knife_mount_spec as mount
    import sm_vn_knife_mount_dowel_spec as dowel
    from _printed_tolerance import angular_band_deg

    slip = dowel.SLIP_CLEARANCE_MAX / 2.0
    x_band = (
        spec.AS_CAST_BAND
        + spec.HANGER_CROSSBAR_CENTER_TOL
        + spec.HANGER_PIN_X_TOL
        + slip
    )
    width = 2.0 * mount.BLK_HALF_X + mount.BLOCK_SIZE_TOL
    reach = max(
        mount.HOLE_ROW_FACE_DISTANCE + mount.HOLE_ROW_FACE_TOL,
        mount.SUPPORT_Z_THICK + mount.BLOCK_SIZE_TOL
        - (mount.HOLE_ROW_FACE_DISTANCE - mount.HOLE_ROW_FACE_TOL),
    )
    turn = math.radians(angular_band_deg())
    assert spec.HANGER_PIN_XS == (spec.HANGER_PIN_X,)
    for mount_name, station, z_label in (
        ("front", part.STUD_Z_FRONT, "front hanger z from lower sockets"),
        ("rear", part.STUD_Z_REAR, "rear hanger z from lower sockets"),
    ):
        hull = part.KNIFE_SEAT_FOOTPRINTS[mount_name]
        # The stations stand from the rear socket axis, the edges from the
        # front socket: the pattern's Ø.010 lies between them (#2628 (d)).
        z_band = (
            spec.PRINTED_LINEAR_BAND_MM[spec.DRAWING_REFERENCE_PRECISION[z_label]]
            + part.SOCKET_PATTERN_REFINEMENT_ZONE
            + spec.HANGER_PIN_X_TOL
            + slip
        )
        corners = [
            (
                spec.PIN_HOLE_X + dx + u * math.cos(t) - v * math.sin(t),
                station + dz + u * math.sin(t) + v * math.cos(t),
            )
            for dx in (-x_band, x_band)
            for dz in (-z_band, z_band)
            for side in (
                mount.PIN_HOLE_SIDE_DISTANCE - mount.PIN_HOLE_SIDE_TOL,
                mount.PIN_HOLE_SIDE_DISTANCE + mount.PIN_HOLE_SIDE_TOL,
            )
            for u in (side, side - width)
            for v in (-reach, reach)
            for t in (-turn, turn)
        ]
        assert part._plan_gap(hull, corners) == 0.0, mount_name
        # The block never reaches the retired -X station's turned-round
        # envelope: its -X face stays within one block width of the pin.
        assert min(x for x, _z in hull) > spec.PIN_HOLE_X - x_band - width - reach
    assert min(part.KNIFE_SEAT_EDGE_BREAK_CLEARANCE.values()) >= 0.5


def test_edge_breaks_stay_clear_of_both_print_worst_knife_seats() -> None:
    # Every finished underside break band keeps 0.5 off both seats.  The
    # front seat stands 6.35 further out since #1038 (owner ruling 4, the
    # summing plate's front extension), clear of the pocket ends that bound
    # it; the rear seat now binds.  Every gusset hypotenuse beyond the
    # pockets is an edge a break would put under a seat; the rear bar sides
    # stop short of the rear seat.
    _groups, clearance = part._external_edge_breaks()
    assert clearance == part.KNIFE_SEAT_EDGE_BREAK_CLEARANCE
    assert min(clearance.values()) >= part.KNIFE_SEAT_EDGE_BREAK_MIN_CLEARANCE == 0.5
    # The #30 slip's 0.188 maximum (owner ruling 2026-11-24, fit audit OQ19)
    # swings each hull 0.048 further than the former reamed slip's 0.091.
    assert clearance == pytest.approx(
        {"front": 3.379074718490893 + 6.35, "rear": 3.961649177049054}
    )
    # The printed worst leg, .06 + .01, never the model's 1.524.
    assert part.EDGE_BREAK_PRINTED == pytest.approx(1.524)
    assert part.EDGE_BREAK_PRINTED_MAX == pytest.approx(1.778)
    reach = part.EDGE_BREAK_PRINTED_MAX + part._EDGE_LOCATION_BAND
    gusset_z = part.LAND_FACE_Z0 - part.GUSSET
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
        (part.BAR_X0 - part.GUSSET, -part.LAND_FACE_Z0),
        (part.BAR_X0 - part.GUSSET + reach * math.sqrt(2.0), -part.LAND_FACE_Z0),
        (part.BAR_X0 + reach * math.sqrt(2.0), -gusset_z),
    ]
    assert part._plan_gap(hypotenuse_band, front) < 0.5


def test_edge_break_picks_are_convex_and_the_gusset_junctions_are_not() -> None:
    # The solid-angle probe reads the plan's turns on the underside, where
    # the added-draft faces stand at their nominals: the bar-side to gusset
    # junction is re-entrant, a pocket-end outer corner is right-angled and
    # convex.
    gusset_z = part.LAND_FACE_Z0 - part.GUSSET
    for x_bar in (part.BAR_X0, part.BAR_X1):
        for sz in (-1.0, 1.0):
            assert (
                part._interior_angle(
                    (x_bar, -part.HALF_H, sz * gusset_z), (0.0, 1.0, 0.0)
                )
                == 225.0
            )
            assert (
                part._interior_angle(
                    (x_bar, -part.HALF_H, sz * part.BAR_POCKET_Z), (0.0, 1.0, 0.0)
                )
                == 90.0
            )
    for x, y, z in _external_break_points():
        assert not (abs(abs(z) - gusset_z) < 1e-9 and x in (part.BAR_X0, part.BAR_X1))


def _external_break_points() -> list[list[float]]:
    return [
        point for picks, _, _ in part.EXTERNAL_EDGE_BREAKS.values() for point in picks
    ]


def _has_point(points: list[list[float]], point: list[float]) -> bool:
    return any(candidate == pytest.approx(point, abs=1e-9) for candidate in points)


def test_edge_breaks_split_into_connected_chains_in_build_order() -> None:
    groups, _clearance = part._external_edge_breaks()
    assert groups == part.EXTERNAL_EDGE_BREAKS
    # Derived from the eligible breaks: the crossbar T flange's underside has
    # no printed shelf for a break; the hub rib's outer bottom either side of
    # the set-screw boss holds its breaks at the as-cast limits, so the
    # boss's breaks join the rib's.
    expected = {
        "RailRunBreaks": (7, 2419.0142836326213, 0),
        "CrossbarBreaks": (12, 510.3457640007208, 12),
        "WestWindowBreaks": (11, 1084.4517777074375, 12),
        "HubRailBreaks": (33, 1790.0809063406873, 36),
        "BossRimBreaks": (9, 1386.1347733087518, 0),
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
        assert _has_point(
            hub, [(-part.RIB_OUT_X0 - part.WEB_OUT_X) / 2.0, -part.HALF_H, z_rib]
        )
    # The crossbar: two web bottoms, four pocket-end bottoms and two rear
    # side bottoms on the underside (92° edges), and four full-depth pocket
    # corners leaning 2° on both their faces (90°), meeting at the pocket
    # ends' corners.
    under = part._chamfer_section_area(part.EDGE_CHAMFER, 92.0)
    square = 0.5 * part.EDGE_CHAMFER**2
    lean = part.POCKET_H * math.tan(math.radians(2.0))
    corner = math.sqrt(part.POCKET_H**2 + 2.0 * lean**2)
    bottom_lengths = (
        2.0 * 2.0 * part.BAR_POCKET_Z
        + 2.0 * (part.BAR_WEB_X0 - part.BAR_X0 + part.BAR_X1 - part.BAR_WEB_X1)
        + 2.0 * (part.LAND_FACE_Z0 - part.GUSSET - part.BAR_POCKET_Z)
    )
    assert groups["CrossbarBreaks"][1] == pytest.approx(
        under * bottom_lengths + square * 4.0 * corner
    )


def test_hub_rib_stubs_beside_the_set_boss_take_their_breaks(monkeypatch) -> None:
    # Either side of the set-screw boss the rib's outer bottom runs 4.953
    # nominal and 4.191 at the as-cast limits (the narrowest rib less the
    # widest boss, halved): over the 3.556 that printed worst legs at both
    # its ends take, so it is broken and joins the boss's breaks to the rib's.
    band = spec.AS_CAST_BAND
    stub = ((part.HUB_RIB_W - band) - (part.HUB_SET_BOSS_W + band)) / 2.0
    nominal = (part.HUB_RIB_W - part.HUB_SET_BOSS_W) / 2.0
    assert (nominal, stub) == pytest.approx((4.953, 4.191))
    assert part.HUB_RIB_STUB_PRINTED_MIN == pytest.approx(stub)
    assert nominal > stub > 2.0 * part.EDGE_BREAK_PRINTED_MAX == pytest.approx(3.556)
    # A stub too short for both legs would stay sharp, leaving the boss's
    # breaks a chain of their own: the cast face's two leaning corners up to
    # the faced top, its bottom run and the two side bottoms back to the rib,
    # three meeting at each face corner.
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
        [-part.RIB_OUT_X0, -part.HALF_H, (rib_lo + boss_lo) / 2.0],
        [-part.RIB_OUT_X0, -part.HALF_H, (boss_hi + rib_hi) / 2.0],
    ]
    hub, removal, shared = groups["HubRailBreaks"]
    boss_picks, boss_removal, boss_shared = groups["HubSetBossBreaks"]
    assert base["HubRailBreaks"][0] == hub + stubs + boss_picks
    under = part._chamfer_section_area(part.EDGE_CHAMFER, 92.0)
    assert base["HubRailBreaks"][1] == pytest.approx(
        removal + under * 2.0 * nominal + boss_removal
    )
    assert base["HubRailBreaks"][2] == shared + boss_shared + 6
    assert len(boss_picks) == 5
    corner = math.sqrt(
        part.RING_HEIGHT**2
        + (part.SET_BOSS_FACE_X - part.SET_BOSS_FACE_X0) ** 2
        + part.RIM_RECEDE**2
    )
    assert boss_removal == pytest.approx(
        0.5 * part.EDGE_CHAMFER**2 * 2.0 * corner
        + under * (part.HUB_SET_BOSS_W + 2.0 * part.SET_BOSS_PROUD)
    )
    assert all(x <= -part.RIB_OUT_X0 for x, _y, _z in boss_picks)


def test_edge_break_chains_leave_no_sliver_between_features(monkeypatch) -> None:
    assert part._segment_gap((0, 0, 0), (1, 0, 0), (1, 0, 0), (1, 1, 0)) == 0.0
    assert part._segment_gap((0, 0, 0), (2, 0, 0), (1, 1, 1), (1, 1, 3)) == (
        pytest.approx(math.sqrt(2.0))
    )
    assert part._segment_gap((0, 0, 0), (1, 0, 0), (3, 0, 0), (4, 0, 0)) == 2.0
    # The nearest two breaks that do not meet stand 4.953 apart, two printed
    # worst legs and a 1.397 land: the hub rail's outer flange underside run
    # and the set-screw boss's top side run beside it; demanding a land over
    # 1.397 trips the guard there.
    assert 2.0 * part.EDGE_BREAK_PRINTED_MAX + part.EDGE_BREAK_SLIVER_MIN == (
        pytest.approx(3.656)
    )
    monkeypatch.setattr(part, "EDGE_BREAK_SLIVER_MIN", 1.39)
    part._external_edge_breaks()
    monkeypatch.setattr(part, "EDGE_BREAK_SLIVER_MIN", 1.40)
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
    assert len(points) == 72
    assert len({tuple(round(value, 6) for value in point) for point in points}) == len(
        points
    )
    # No two picks share an edge's 0.5 mm selection radius.
    for i, a in enumerate(points):
        for b in points[i + 1 :]:
            assert math.dist(a, b) > 0.5
    # Picked: the rear full-depth bar-side bottoms.
    for x_bar in (part.BAR_X0, part.BAR_X1):
        assert _has_point(
            points,
            [
                x_bar,
                -part.HALF_H,
                (part.BAR_POCKET_Z + part.LAND_FACE_Z0 - part.GUSSET) / 2.0,
            ],
        )
    # Sharp: the crossbar T flange's underside edges (no printed shelf), the
    # front bar-side bottoms, every gusset hypotenuse bottom beyond the
    # pockets and the hub rib's inner bottom edge: none is picked.
    crossbar = part.EXTERNAL_EDGE_BREAKS["CrossbarBreaks"][0]
    assert all(y != part.FLANGE_BOT_Y for _x, y, _z in crossbar)
    rib_lo = part.GOOSENECK_Z - part.HUB_RIB_W / 2.0
    rib_hi = part.GOOSENECK_Z + part.HUB_RIB_W / 2.0
    for x, y, z in points:
        assert not (
            y == -part.HALF_H
            and x == pytest.approx(-part.RIB_IN_X0)
            and rib_lo < z < rib_hi
        )
        if y == -part.HALF_H and part.BAR_POCKET_Z < abs(z) < part.LAND_FACE_Z0:
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
    assert part.KEEPER_MAX_STOCK_ENTRY == pytest.approx(maximum_entry)
    thread_places = spec.KEEPER_TAP_CALLOUT_PRECISION["hw-threaddepth"]
    reserve = spec.printed_limit(full_thread, thread_places, -1.0) - maximum_entry
    assert reserve == pytest.approx(part.KEEPER_MIN_THREAD_TIP_RESERVE)
    assert reserve == pytest.approx(1.6383)
    assert reserve >= 0.25
    assert tap_spec.depth_mm - full_thread - 2.0 * depth_tolerance >= 5.0 * pitch
    drill_point = part.TAP_DRILL_MM[tap_spec.size] / 2.0 * part.DRILL_POINT_H
    assert tap_spec.depth_mm + depth_tolerance + drill_point < part.RING_HEIGHT


def test_transferred_keeper_receiver_keeps_real_normal_wall_at_printed_bands() -> None:
    # Owner rulings B1/B2 and D3/D4 (#2333): the receiver web is as cast --
    # its thickness, root radius and flange ±.03, its median within half the
    # ⌖.06 zone of the socket-axis line the keeper is set from, its faces
    # leaning at least the 2° an added family may print.
    assert part.KEEPER_TAP_X == part.COLUMN_X + keeper.KEEPER_FITUP_X_FROM_WEB_MM
    assert part.KEEPER_MAX_TRANSVERSE_OFFSET == pytest.approx(0.254)
    # The lug centre at MHA-CH-00's printed .114 ±.004 (delegated ruling
    # 2026-11-24 (Main), precedent: owner ruling 2026-11-01, #2144
    # (rulings.md D15)).
    assert part.KEEPER_MAX_WEB_CENTRE_OFFSET == pytest.approx(4.0132)
    assert part.KEEPER_MIN_WEB_HALF_WIDTH == pytest.approx(6.962586831553313)
    assert part.KEEPER_MIN_ROOT_RADIUS == pytest.approx(2.286)
    assert part.KEEPER_MIN_FLANGE_THICKNESS == pytest.approx(7.366)
    assert part.KEEPER_MAX_FULL_THREAD_DEPTH == pytest.approx(7.874)
    assert part.KEEPER_TAP_THREAD_WALL_MARGIN_NO_WANDER == pytest.approx(
        2.263367373611047
    )
    assert part.KEEPER_TAP_DRILL_WALL_MARGIN_NO_WANDER == pytest.approx(
        2.009586831553314
    )
    assert part.KEEPER_TAP_THREAD_WALL_MARGIN == pytest.approx(2.202189533594047)
    assert part.KEEPER_TAP_DRILL_WALL_MARGIN == pytest.approx(1.9484089915363136)
    # Delegated ruling 2026-11-24 (Main), precedent: owner ruling 2026-11-01,
    # #2144 (rulings.md D15): .0767 accepted under the .080 target at .076
    # (RV-14), over the .060 floor.
    held = min(part.KEEPER_TAP_THREAD_WALL_MARGIN, part.KEEPER_TAP_DRILL_WALL_MARGIN)
    assert spec.KEEPER_TAP_WALL_ACCEPTED_MM <= held < WALL_TARGET_MM
    assert spec.KEEPER_TAP_WALL_ACCEPTED_MM > part.WALL_FLOOR_MM
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
    centre_x = _cast_web_half_width(part.FLANGE_BOT_Y - radius) + radius
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
    The keeper's own dimensions print on its sheet's unit; the root is the
    casting's, at its as-cast minimum, and the web's median stands half its
    ⌖.06 zone off the socket-axis line the keeper is set from."""
    root_radius = part.ROOT_FILLET_R - spec.AS_CAST_BAND
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
        + part.RAIL_WEB_POSITION_ZONE / 2.0
    )
    thread_places = spec.KEEPER_TAP_CALLOUT_PRECISION["hw-threaddepth"]
    thread_depth = spec.printed_limit(
        keeper.KEEPER_TAP_SPEC.overrides_mm["ThreadDepth"], thread_places, 1.0
    )
    drill_places = spec.KEEPER_TAP_CALLOUT_PRECISION["hw-tapdrldepth"]
    cylinder_depth = spec.printed_limit(
        keeper.KEEPER_TAP_SPEC.depth_mm, drill_places, 1.0
    )
    assert cylinder_depth == pytest.approx(11.684)
    assert spec.KEEPER_TAP_DRILL_WANDER_DEG == 0.3
    displacement = cylinder_depth * math.tan(math.radians(0.3))
    assert displacement == pytest.approx(0.06117784001700028)
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


def _cast_web_half_width(y: float) -> float:
    """Half the thinnest as-cast web at height ``y``: its ±.03 minimum on the
    underside, thickened upward by the least (2°) added draft."""
    return (part.WEB_T - spec.AS_CAST_BAND) / 2.0 + (
        y + part.HALF_H
    ) * math.tan(math.radians(2.0))


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
    worst case.  H-H prints the top flange TYP with its as-cast band, so its
    minimum binds the faced keeper rail too, with no second facing
    allowance."""
    assert spec.DRAWING_PRECISION["TopFlange"]["FlangeT"] == spec.FLANGE_THICKNESS_PLACES
    assert "FlangeT" in spec.AS_CAST_DIMENSIONS["TopFlange"]
    assert spec.FLANGE_THICKNESS_MM == part.FLANGE == pytest.approx(8.128)  # .32
    flange_depth = spec.FLANGE_THICKNESS_MM - spec.AS_CAST_BAND
    assert flange_depth == pytest.approx(7.366)
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
    # The thread's limiting corner sits beside the root; the pilot's wall is
    # thinnest at its bottom, where the leaning web is narrowest.
    root_half_width = _cast_web_half_width(part.FLANGE_BOT_Y - root_radius)
    half_width = _cast_web_half_width(part.HALF_H - cylinder_depth)
    assert half_width == pytest.approx(part.KEEPER_MIN_WEB_HALF_WIDTH)
    thread_wall = _worst_thread_wall(
        root_half_width, root_radius, flange_depth, corner_x, thread_depth, displacement
    )
    # The pilot reaches the bare web below the root whatever the flange.
    assert cylinder_depth > flange_depth + root_radius
    pilot_wall = half_width - (axis_offset + displacement + pilot_radius)
    assert thread_wall == pytest.approx(part.KEEPER_TAP_THREAD_WALL_MARGIN, abs=1e-6)
    assert pilot_wall == pytest.approx(part.KEEPER_TAP_DRILL_WALL_MARGIN)
    # With the lug centre at MHA-CH-00's printed .114 ±.004, the pilot wall
    # at the 2° minimum added draft is .0767, under the .080 target and held
    # at D15's accepted .076 (RV-14).
    assert pilot_wall == pytest.approx(1.9484, abs=5e-5)
    assert min(thread_wall, pilot_wall) >= spec.KEEPER_TAP_WALL_ACCEPTED_MM


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
    """The native leader shoulder's end nearest the tap: the underline
    KEEPER_CALLOUT_SHOULDER_DROP under the block's point."""
    left, _down, right, _up = drawing.KEEPER_CALLOUT_EXTENT
    x = callout[0] - left if tip[0] < callout[0] else callout[0] + right
    return (x, callout[1] - drawing.KEEPER_CALLOUT_SHOULDER_DROP)


def _relieved_boss_gap(start, end, boss, boss_r) -> float:
    """Least sheet distance from the segment to the rear-west barrel as the
    plan draws it: the disc below its relief chord (owner ruling K5)."""
    chord_y = boss[1] + spec.KEEPER_BOSS_RELIEF_FROM_SOCKET * _S
    gap = math.inf
    for i in range(181):
        t = i / 180.0
        x, y = start[0] + t * (end[0] - start[0]), start[1] + t * (end[1] - start[1])
        for j in range(0, 361, 2):
            a = math.radians(j)
            px, py = boss[0] + boss_r * math.cos(a), boss[1] + boss_r * math.sin(a)
            gap = min(gap, math.hypot(x - px, y - min(py, chord_y)))
    return gap


def test_keeper_callout_leader_takes_the_short_way_to_its_tap() -> None:
    """#946 / b49e1: RD4 stood above the front keeper tap's boss and its
    leader crossed the boss and bore rings: 29.6 mm over the part, 18.3 mm
    past the tap's approach.  It reads off the rear tap from the rail's
    outer side.  #1038: the tap now stands 3.4 mm of paper over the rear
    barrel's relief step, so the callout stands over the tap's level and
    its leader climbs to it clear of the relieved barrel."""
    hole, hole_r, boss, boss_r = _keeper_geometry()
    callout, tip = drawing.keeper_callout_placement(hole, hole_r)
    assert math.dist(tip, hole) == pytest.approx(hole_r)
    start = _shoulder_end(callout, tip)
    assert start == pytest.approx(
        (hole[0] + drawing.KEEPER_LEADER_RUN[0], hole[1] + drawing.KEEPER_LEADER_RUN[1])
    )
    over, approach, detour = _plan_detour(start, tip)
    assert detour <= LEADER_DETOUR_TARGET, (over, approach, detour)
    # The tap stands inside an ink clearance of where the unrelieved barrel
    # was drawn; no leader from below reaches it.  The leader from above
    # passes the relieved barrel well clear, wherever the native block lands
    # within 3 mm of its estimate.
    assert math.dist(hole, boss) - boss_r < drawing.INK_CLEARANCE
    for dx in (-0.003, 0.0, 0.003):
        for dy in (-0.003, 0.0, 0.003):
            moved = (start[0] + dx, start[1] + dy)
            assert _relieved_boss_gap(moved, tip, boss, boss_r) >= drawing.INK_CLEARANCE
            assert moved[1] > hole[1] + drawing.INK_CLEARANCE
    assert tip[0] > hole[0] and tip[1] > hole[1]
    # The callout stands right of the rail and the barrel, inside the frame.
    left, _down, right, up = drawing.KEEPER_CALLOUT_EXTENT
    box = (callout[0] - left, start[1], callout[0] + right, callout[1] + up)
    frame = drawing.SHEET_FRAME
    assert frame[0] <= box[0] and box[2] <= frame[2] - drawing.INK_CLEARANCE
    assert box[3] <= frame[3] - drawing.INK_CLEARANCE
    assert box[1] > TITLE_BLOCK[3]
    assert box[0] > boss[0] + boss_r + drawing.INK_CLEARANCE
    assert box[0] > _plan(part.OUTER_X, 0.0)[0] + drawing.INK_CLEARANCE


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


# #955 section letters.  layoutcheck's replay of b49e1 found three cutting-
# plane letters printed on ink (B 3.65 mm on the rail edge and the 183.9,
# E 0.99 on the corner boss, D 6.17 on the hub rail's inner face) and two more
# under 1 mm off it.  This is historical B/E/D calibration evidence, not
# H/K glyph measurements.  The two 1:3 plans project +X right and +Z down.
_PLAN_S = drawing.GEOMETRY_VIEW_SCALE / 1000.0
_SECTION_PLAN = {
    "B": drawing.GEOMETRY_TOP_CENTER,
    "E": drawing.GEOMETRY_TOP_CENTER,
    "M": drawing.GEOMETRY_TOP_CENTER,
    "D": drawing.HUB_TOP_CENTER,
}
_LETTER_ENDS = ("B-outer", "B-inner", "E-inner", "E-outer", "D-outer", "D-inner")
# The live letters: H and K at B's and D's calibrated stations; E's outer
# letter at its old station, its inner one beside the front-left boss since
# E-E stopped at the side rail (owner 2026-11-07); M's at the crossbar.
_LIVE_LETTER_ENDS = (
    "H-outer", "H-inner", "E-inner", "E-outer", "K-outer", "K-inner", "M-inner", "M-outer",
)
_LIVE_AS_BASELINE = {"H": "B", "K": "D"}
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
    """Each letter's arrow tail, keyed '<section>-<outer|inner>'; E's and
    M's cuts start at their inner (+X) ends, B's and D's at their outer."""
    order = {"E": ("inner", "outer"), "M": ("inner", "outer")}
    return {
        f"{key}-{name}": _plan_point(_LIVE_AS_BASELINE.get(key, key), *point)
        for key, pair in ends.items()
        for name, point in zip(order.get(key, ("outer", "inner")), pair)
    }


def _letter_extents(letter):
    if letter == drawing.CROSSBAR_SECTION_LETTER:
        return drawing.CROSSBAR_SECTION_LETTER_EXTENTS
    return drawing.SECTION_CUT_BASELINE_LETTER_EXTENTS[_LIVE_AS_BASELINE.get(letter, letter)]


def _letter_boxes(ends):
    boxes = {}
    for name, (x, y) in _letter_tails(ends).items():
        dx0, dy0, dx1, dy1 = _letter_extents(name[0])
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


def _front_rail_edges(key, x0, x1):
    """The -Z (front) rail's inner and outer plan edges from x0 to x1."""
    near = -(part.INNER_Z + part.EDGE_CHAMFER)
    far = -(part.OUTER_Z - part.EDGE_CHAMFER)
    return (
        _segment_ink("rail inner edge", _plan_line(key, (x0, near), (x1, near)), drawing.INK_CLEARANCE),
        _segment_ink("rail outer edge", _plan_line(key, (x0, far), (x1, far)), drawing.INK_CLEARANCE),
    )


def _boss_ink(key, boss_dia):
    boss = _plan_point(key, -part.COLUMN_X, part.FRONT_COLUMN_Z)
    boss_r = boss_dia / 2.0 * _PLAN_S
    return ("corner boss", lambda box: max(0.0, _box_point_gap(box, boss) - boss_r), drawing.INK_CLEARANCE)


def _letter_ink(name, *, boss_dia, live=False):
    """(what, gap function, clearance) for the ink round one letter: the
    plan's own edges, projected from the model, and the dimension ink b49e1
    printed beside it.  ``live`` reads E's inner letter at its live station
    (beside the front-left boss) rather than b49e1's (by the crossbar)."""
    ink = drawing.INK_CLEARANCE
    name = _LIVE_AS_BASELINE.get(name[0], name[0]) + name[1:]
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
    if (name == "E-inner" and not live) or name == "M-inner":
        return (
            *_front_rail_edges("E", part.BAR_X1, part.INNER_X),
            *(
                _segment_ink(f"18.0 witness {i}", _mm_segment(w), ink)
                for i, w in enumerate(_GUSSET_RUN_WITNESSES)
            ),
            ("18.0", lambda box: _box_box_gap(box, _mm(_GUSSET_RUN_TEXT)), ink),
        )
    if name == "E-inner":
        return (
            *_front_rail_edges("E", -part.INNER_X, part.BAR_X0),
            _boss_ink("E", boss_dia),
            _segment_ink(
                "window width left witness",
                ((_WIN_WIDTH_LEFT_EXTENSION_X, _PLAN_TOP_Y), (_WIN_WIDTH_LEFT_EXTENSION_X, _WIN_WIDTH_LINE_Y)),
                ink,
            ),
        )
    if name == "M-outer":
        leg = _plan_line(
            "E",
            (part.BAR_X0 - part.GUSSET, -part.INNER_Z),
            (part.BAR_X0, -part.INNER_Z + part.GUSSET),
        )
        return (
            *_front_rail_edges("E", -part.INNER_X, part.BAR_X0),
            _segment_ink("-X gusset leg", leg, ink),
            ("18.0", lambda box: _box_box_gap(box, _mm(_GUSSET_RUN_TEXT)), ink),
        )
    if name == "E-outer":
        return (
            _boss_ink("E", boss_dia),
            *(
                _segment_ink(f"corner witness {i}", _mm_segment(w), ink)
                for i, w in enumerate(_corner_witnesses(boss_dia))
            ),
        )
    face_x = {"D-outer": -part.OUTER_X, "D-inner": -part.INNER_X}[name]
    face = _plan_line("D", (face_x, -part.INNER_Z), (face_x, part.INNER_Z))
    return (_segment_ink("hub rail face", face, ink),)


def _letter_shortfalls(ends, name, *, boss_dia, live=False):
    """The ink a letter stands too close to, with its gap in mm."""
    box = _letter_boxes(ends)[name]
    return {
        what: round(gap(box) * 1000.0, 2)
        for what, gap, clearance in _letter_ink(name, boss_dia=boss_dia, live=live)
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


@pytest.mark.parametrize("name", _LIVE_LETTER_ENDS)
def test_section_cut_letters_keep_their_ink_clearance(name: str) -> None:
    """Replay the measured B/E/D glyphs (and M's estimate) at the live
    cutting endpoints: H and K at B's and D's calibrated stations, E's outer
    letter at its old one, E's inner letter beside the front-left boss on
    the front rail, M's either side of the crossbar.

    This guards the placement calibration only.  It cannot prove live
    H/K/M glyph clearance, which requires native inspection.
    """
    assert (
        _letter_shortfalls(drawing.section_cut_ends(), name, boss_dia=part.BOSS_DIA, live=True)
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


# Sheet-2 ink measured on the ca7edf4d render (sheet m): the plan's top
# edge, the 359.8 line, its left extension, the 152.9 line and the front
# view's top.
_PLAN_TOP_Y = 0.21216
_WIN_WIDTH_LINE_Y = 0.22772
_WIN_WIDTH_LEFT_EXTENSION_X = 0.08502
_FRONT_VIEW_TOP_Y = 0.09666


def test_section_cuts_cross_the_same_stock() -> None:
    """The preserved ends keep what each removed section shows: H cuts the
    rail's plain T between the junction land and the corner boss; E runs
    from outside the left rail into the window past its inner face, M across
    the crossbar T between the window's gusset legs -- each a short whole
    plane across its own piece (owner 2026-11-07: a plane that leaves pieces
    floating becomes separate sections) -- and K from outside the set-screw
    boss past the hub rail's inner face, each at its own station."""
    ends = drawing.section_cut_ends()
    (hx, h_outer), (hx_inner, h_inner) = ends["H"]
    assert hx == hx_inner and part.LAND_X1 < hx < part.COLUMN_X - part.BOSS_DIA / 2.0
    assert h_inner < part.INNER_Z and h_outer > drawing.PLAN_HALF_Z
    (e_inner, ez), (e_outer, ez_outer) = ends["E"]
    assert ez == ez_outer == drawing.SIDE_SECTION_Z
    assert e_outer < -drawing.PLAN_HALF_X
    assert -part.INNER_X < e_inner < part.BAR_X0 - part.GUSSET
    (m_inner, mz), (m_outer, mz_outer) = ends[drawing.CROSSBAR_SECTION_LETTER]
    assert mz == mz_outer == drawing.SIDE_SECTION_Z
    assert e_inner < m_outer < part.BAR_X0 - part.GUSSET
    assert part.BAR_X1 + part.GUSSET < m_inner < part.INNER_X
    (k_outer, kz), (k_inner, kz_inner) = ends["K"]
    assert kz == kz_inner == part.GOOSENECK_Z
    assert k_outer < part.SET_BOSS_FACE_X and -part.INNER_X < k_inner < part.BAR_X0


def test_side_rail_and_crossbar_print_as_two_sections_without_a_sheet_scale() -> None:
    """Owner 2026-11-07: E-E's one plane left the side rail and the crossbar
    floating apart, so each is its own removed section with its own letter,
    the crossbar's dimensions on M-M; H-H prints at the sheet's 1:3, so no
    note restates that scale."""
    import inspect

    source = inspect.getsource(drawing.build)
    assert 'section_label="E"' in source
    assert "section_label=CROSSBAR_SECTION_LETTER" in source
    assert drawing.CROSSBAR_SECTION_LETTER not in {"A", "B", "D", "E", "F", "G", "H", "J", "K", "L"}
    assert not hasattr(drawing, "RAIL_SECTION_SCALE_LABEL")
    assert "SCALE 1 : 3" not in Path(drawing.__file__).read_text(encoding="utf-8")
    # Each section imports the model's own as-cast dimensions (owner ruling
    # B2, #2333): E-E the side web under its 2X WEB, M-M the crossbar's web
    # and its pockets' depth, with the rails' flange a reference beside them.
    tree = _drawing_tree()
    imported = {
        ast.unparse(call.args[1]): ast.unparse(_keyword(call, "keep"))
        for call in _named_calls(tree, "curate_view_dimensions")
    }
    assert imported["side_section"] == "SIDE_SECTION_KEEP"
    assert imported["crossbar_section"] == "CROSSBAR_SECTION_KEEP"
    callouts = {
        ast.unparse(call.args[1]): ast.unparse(call.args[2])
        for call in _named_calls(tree, "set_dimension_callouts")
    }
    assert callouts["side_section_dimensions"] == "{'SideWebT': SIDE_WEB_QUALIFIER}"
    assert callouts["crossbar_section_dimensions"] == "CROSSBAR_SECTION_CALLOUTS"
    assert set(drawing.SIDE_SECTION_KEEP) == {"SideWebT"}
    assert drawing.CROSSBAR_SECTION_CALLOUTS == {
        "CrossbarWebT": "CROSSBAR WEB",
        "PocketDepth": "2X POCKET",
    }
    assert set(drawing.CROSSBAR_SECTION_KEEP) == set(drawing.CROSSBAR_SECTION_CALLOUTS)
    for name in ("SideWebT", "CrossbarWebT", "PocketDepth"):
        assert name in set().union(*spec.AS_CAST_DIMENSIONS.values()), name
    flange = _labelled_call(tree, "_checked_dimension", "crossbar flange thickness")
    assert ast.unparse(flange.args[1]) == "crossbar_section"
    assert ast.literal_eval(_keyword(flange, "suffix")) == "CROSSBAR FLANGE"
    assert ast.literal_eval(_keyword(flange, "reference")) is True
    assert ast.unparse(_keyword(flange, "expected_mm")) == "FLANGE"
    side = source[source.index('section_label="E"'):source.index("crossbar_cut = [")]
    assert all(
        q not in side
        for q in ("CROSSBAR_SECTION_CALLOUTS", "CROSSBAR_SECTION_KEEP", '"CROSSBAR FLANGE"')
    )
    # Both print at the sheet's 1:3 (no scale row), their one-row captions
    # (44 mm) side by side, each centred under its own section.
    assert drawing.SIDE_SECTION_SCALE == (1, 3)
    assert drawing.CROSSBAR_SECTION_CAPTION_XY[1] == drawing.SIDE_SECTION_CAPTION_XY[1]
    assert drawing.SIDE_SECTION_CAPTION_XY[0] == pytest.approx(drawing.SIDE_SECTION_PROFILE_X, abs=0.0002)
    assert drawing.CROSSBAR_SECTION_CAPTION_XY[0] - drawing.SIDE_SECTION_CAPTION_XY[0] >= 0.044 + 0.003
    assert drawing.CROSSBAR_SECTION_PROFILE_X == pytest.approx(
        drawing._side_section_xy(part.HANGER_X, 0.0)[0]
    )


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
    assert d1 > d0
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
    assert spec.SET_SCREW_FULL_THREAD_MIN == pytest.approx(12.145, abs=1e-3)
    assert spec.SET_SCREW_FULL_THREAD_NOMINAL == pytest.approx(12.442, abs=1e-3)
    assert spec.SET_SCREW_MAJOR_DIA == pytest.approx(6.35)
    assert spec.SET_SCREW_ENGAGEMENT_D == pytest.approx(1.913, abs=1e-3)
    assert spec.SET_SCREW_ENGAGEMENT_D >= spec.SET_SCREW_MIN_ENGAGEMENT_D == 1.5


def test_gooseneck_bore_slides_on_the_bare_leg_and_the_set_screw_reaches_it() -> None:
    """Owner ruling 2026-11-08 (Pedro), #2315: the hub bore takes the
    gooseneck's bare 1/2 in leg.  Owner decision 2026-11-19 (#3124, item 2):
    a 33/64 drill printed .5156 under DRILLED HOLES (.5156-.5196), .0086-.0216
    diametral slip over the tube's mill OD; the 3/4 in MHA-FR-VN-52 still
    reaches the leg (15.29 of 19.05) and tightens snug, 9 in-lb (1 N·m)
    max."""
    assert spec.GOOSENECK_DRILL == "33/64"
    assert spec.GOOSENECK_BORE_DIA == pytest.approx(33.0 / 64.0 * 25.4)
    assert spec.GOOSENECK_BORE_DIA_MAX == pytest.approx(
        spec.GOOSENECK_BORE_DIA + spec.DRILL_OVERSIZE
    )
    assert spec.DRAWING_PRECISION["GooseneckProfile"] == {"GnDia": 4}
    assert spec.GOOSENECK_SLIP_MIN / 25.4 == pytest.approx(0.008625, abs=1e-6)
    assert spec.GOOSENECK_SLIP_MAX / 25.4 == pytest.approx(0.021625, abs=1e-6)
    assert drawing.HUB_TOP_CALLOUTS["GnDia"].startswith("33/64 DRILL THRU\n")
    assert spec.SET_SCREW_REACH_MAX == pytest.approx(15.286, abs=1e-3)
    assert spec.SET_SCREW_REACH_MAX < spec.SET_SCREW_LENGTH - spec.SET_SCREW_PITCH
    assert spec.SET_SCREW_LENGTH == pytest.approx(19.05)
    assert (spec.SET_SCREW_TORQUE_MAX_IN_LB, spec.SET_SCREW_TORQUE_MAX_NM) == (9.0, 1.0)
    assert spec.SET_SCREW_TORQUE_MAX_NM == pytest.approx(
        spec.SET_SCREW_TORQUE_MAX_IN_LB * 0.112984829, abs=0.02
    )


def test_set_screw_boss_carries_the_spot_face_proud_of_the_rail() -> None:
    """Owner ruling B4 (#2333): the full-height boss's cast face stands .95
    from the bore axis on the faced top (±.03) and recedes below it at its
    taken-out draft; the machined spot face prints .83.  At the print's
    worst -- the nearest face at the steepest 3°, the axis low in its band
    under the widest spot, the farthest spot face -- .031 of stock is left
    over the spot's floor.  The spot clears the 1/4 square head's diagonal
    (91410A540, Head Wd 1/4 in) at its minimum, and keeps a land inside the
    boss face's edge breaks across the narrowest boss and from the faced
    top and underside."""
    assert part.SET_SPOT_FACE_X == part.GOOSENECK_X - spec.HUB_SET_SPOT_FROM_AXIS
    assert part.SET_BOSS_FACE_X == part.GOOSENECK_X - spec.HUB_SET_BOSS_FROM_AXIS
    assert part.SET_BOSS_FACE_X < part.SET_SPOT_FACE_X < -part.OUTER_X
    spot_places = spec.HUB_SET_SPOT_PLACES
    assert spot_places == spec.DRAWING_REFERENCE_PRECISION[
        "set-screw spot face from bore axis"
    ]
    assert spec.printed_limit(spec.HUB_SET_SPOT_DIA, 2, -1.0) > 6.35 * math.sqrt(2.0)
    band = spec.PRINTED_LINEAR_BAND_MM
    cast = spec.AS_CAST_BAND
    spot_r = (
        spec.HUB_SET_SPOT_DIA
        + band[spec.DRAWING_PRECISION["SetSpotProfile"]["SetSpotDia"]]
    ) / 2.0
    axis_band = band[spec.DRAWING_REFERENCE_PRECISION["set screw axis from rail top"]]
    axis_drop = part.SCREW_AXIS_BELOW_RAIL_TOP
    stock = (
        spec.HUB_SET_BOSS_FROM_AXIS
        - cast
        - (axis_drop + axis_band + spot_r) * math.tan(math.radians(3.0))
        - (spec.HUB_SET_SPOT_FROM_AXIS + band[spot_places])
    )
    assert stock == pytest.approx(0.7940, abs=5e-5)  # .031
    assert part.SET_SPOT_STOCK_MIN == pytest.approx(stock)
    leg = part.EDGE_BREAK_PRINTED_MAX
    lands = {
        "across the boss": (spec.HUB_SET_BOSS_W - cast) / 2.0 - (leg - stock) - spot_r,
        "under the faced top": axis_drop - axis_band - leg - spot_r,
        "over the faced underside": part.RING_HEIGHT
        - axis_drop
        - axis_band
        - leg
        - spot_r,
    }
    assert lands == pytest.approx(
        {
            "across the boss": 2.5720,
            "under the faced top": 11.176,
            "over the faced underside": 11.0998,
        },
        abs=5e-5,
    )
    assert part.SET_SPOT_LAND_MIN == pytest.approx(lands)
    assert min(part.SET_SPOT_LAND_MIN.values()) >= part.EDGE_BREAK_SLIVER_MIN
    assert spec.HUB_SET_BOSS_W < part.HUB_RIB_W


def test_set_screw_pocket_is_retired_for_the_boss() -> None:
    # VIEW G also carries the hub gussets' span and the hub boss's drop.
    # Its width is the boss's on the underside, where the drafted side walls
    # start, so its last row says so.
    assert drawing.HUB_LEFT_CALLOUTS == {
        "SetBossWidth": "SET-SCREW BOSS\nAT UNDERSIDE",
        "SetSpotDia": "",
        "GussetSpan": "GUSSET SPAN",
        "HubBossDrop": "",
    }
    assert set(drawing.HUB_LEFT_CALLOUTS) == set(drawing.HUB_LEFT_KEEP)
    # rule 26: the spot face prints in the symbol form, its depth a reference
    # on the tap axis.  The boss face stands .95 from the bore axis on the
    # faced top only (owner ruling B4, #2333) and its taken-out draft (D1)
    # has receded .025 by the axis, so the spot is .095 deep there, not the
    # .12 the two printed stations differ by.
    lean = part.SCREW_AXIS_BELOW_RAIL_TOP * math.tan(math.radians(spec.DRAFT_DEG))
    depth = spec.HUB_SET_BOSS_FROM_AXIS - lean - spec.HUB_SET_SPOT_FROM_AXIS
    assert (lean, depth) == pytest.approx((0.6386, 2.4094), abs=5e-5)
    assert f"{depth / 25.4:.{spec.HUB_SET_SPOT_PLACES}f}" == "0.09"
    assert drawing.SET_SPOT_DEPTH_TEXT == "(.09)"
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
# is 6.35.
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
# The hub side view's tap centre prints at (146.5, 95.9) mm.  The unchanged
# tap callout elbows 30.0 left of and 5.6 under its text point, its two rows
# printing -28.3..+28.0 x -5.0..+4.4 about it (run 6).
_HUB_LEFT_TAP = (0.1465, 0.0959)
_TAP_CALLOUT_ELBOW = (-0.0300, -0.0056)
_TAP_CALLOUT_EXTENT = (0.0283, 0.0050, 0.0280, 0.0044)


def _dimension_block(xy, rows):
    """An offset dimension's text block about its text point, underline included."""
    lines = rows.splitlines()
    half_w = max(map(len, lines)) * _ROW_CHAR / 2.0 + _UNDERLINE_PAST
    half_h = (len(lines) * _ROW_PITCH - _ROW_SLACK) / 2.0
    return (xy[0] - half_w, xy[1] - half_h - _UNDERLINE_DROP, xy[0] + half_w, xy[1] + half_h)


def _imported_dimension_block(xy, rows):
    """An imported model dimension's text block about its text point,
    underline included, as farm run 20261111T023438415Z's native rows read
    on every sheet: the rows stand on a 5.56 mm pitch, their middle 2.78 mm
    under the point (two rows on it and 5.56 under it; three 2.78 over it
    and 2.78 and 8.33 under), glyphs to 4.5 mm over a row's line and the
    underline on the last row's."""
    lines = rows.splitlines()
    half_w = max(map(len, lines)) * _ROW_CHAR / 2.0 + _UNDERLINE_PAST
    top_row = xy[1] + (len(lines) - 2) * 0.00278
    return (xy[0] - half_w, top_row - (len(lines) - 1) * 0.00556, xy[0] + half_w, top_row + 0.0045)


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

    The current K-K view keeps the thread and spot-face geometry and text
    placement; the cast boss face's .95 left it for DETAIL J (owner ruling
    B4, #2333).  Replaying the old caption is baseline evidence only; native
    inspection must establish the new caption's clearance.
    """
    from _layout_geometry import Segment, segment_box_distance

    ink = drawing.INK_CLEARANCE
    spot_r = spec.HUB_SET_SPOT_DIA / 2.0
    bore_x = part.GOOSENECK_X - part.GOOSENECK_BORE_DIA / 2.0
    spot_x, boss_x, axis_x = part.SET_SPOT_FACE_X, part.SET_BOSS_FACE_X, part.GOOSENECK_X
    thread_y = drawing.HUB_SET_THREAD_LINE_XY[1]
    spot_y = drawing.HUB_SET_SPOT_LINE_XY[1]
    lines = {
        "thread": Segment(_dd(spot_x, 0.0)[0], thread_y, _dd(bore_x, 0.0)[0], thread_y),
        "21.0": Segment(_dd(axis_x, 0.0)[0], spot_y, _dd(spot_x, 0.0)[0], spot_y),
    }
    # Each offset leader leaves its own line's midpoint.
    for name, xy in {
        "thread": drawing.HUB_SET_THREAD_LINE_XY,
        "21.0": drawing.HUB_SET_SPOT_LINE_XY,
    }.items():
        line = lines[name]
        assert xy[0] == pytest.approx((line.x0 + line.x1) / 2.0, abs=1e-4), name
    blocks = {
        "thread": _dimension_block(drawing.HUB_SET_THREAD_OFFSET_XY, "(10.5)\nTHREAD LENGTH"),
        "21.0": _dimension_block(drawing.HUB_SET_SPOT_OFFSET_XY, "21.0\nSPOT FACE\nFROM BORE AXIS"),
    }
    leaders = {
        "thread": _offset_leader(drawing.HUB_SET_THREAD_LINE_XY, blocks["thread"]),
        "21.0": _offset_leader(drawing.HUB_SET_SPOT_LINE_XY, blocks["21.0"]),
    }
    over = _EXTENSION_OVERSHOOT
    extensions = {
        # The spot face's line carries both the thread length and the 21.0.
        "spot face": ("thread", "21.0", Segment(*_dd(spot_x, spot_r), _dd(spot_x, 0.0)[0], spot_y + over)),
        "bore wall": ("thread", Segment(*_dd(bore_x, part.HALF_H), _dd(bore_x, 0.0)[0], thread_y + over)),
        "upper axis": ("21.0", Segment(*_dd(axis_x, part.HALF_H + 2.0), _dd(axis_x, 0.0)[0], spot_y + over)),
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
    for name in ("HUB_SET_BOSS_LINE_XY", "HUB_SET_BOSS_OFFSET_XY"):
        assert not hasattr(drawing, name), name


def _layout_box(box):
    from _layout_geometry import Box

    return Box(*box)


def test_hub_side_boss_width_and_spot_face_stand_clear_of_their_ink() -> None:
    """Q5: the 1:2 side view sees the boss face on.  The width's rows stand
    straight over it -- the model's own .71 ±.03 with SET-SCREW BOSS and,
    the side walls being drafted from there, AT UNDERSIDE; the tap callout's
    leader leaves under the right extension line's foot and the Ø10.0 spot
    face's under the left one, each an ink clearance off, and the spot
    leader's run over the part stays inside the leader-over-part detour
    gate."""
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
    width_rows = drawing.HUB_LEFT_CALLOUTS["SetBossWidth"].splitlines()
    assert width_rows == ["SET-SCREW BOSS", "AT UNDERSIDE"]
    assert "SetBossWidth" in spec.AS_CAST_DIMENSIONS["SetBossProfile"]
    assert spec.HUB_SET_BOSS_W / 25.4 == pytest.approx(0.71)
    width = _imported_dimension_block(
        drawing.SET_BOSS_WIDTH_TEXT_XY, "\n".join([".71 ±.03", *width_rows])
    )
    # Three rows stand 2.78 mm over where two stood: over their own line,
    # under the plan above (its outline starts at y 149.6 on that farm run;
    # the HUB LOCATION note that once stood between them left the sheet
    # with the machinist-review answer c852399891).
    assert width[1] - line_y >= ink
    assert 0.1496 - width[3] >= ink
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
    texts = {"18.0": width, "Ø10.0": spot, "tap callout": callout}
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


# --- Knife hanger: #10 loose plain clearance and dowels --------------------


def test_knife_hanger_is_a_plain_10_clearance_e_drill_hole() -> None:
    import spring_mount_geom
    from _hole_spec import CLEARANCE_MM, blind_cut_dia_mm

    # Owner ruling 2026-11-24, fit audit OQ19: the native #10 loose clearance
    # row cuts the letter E drill, .250, through its diameter override.
    hole = spec.HANGER_HOLE_SPEC
    assert (hole.kind, hole.size, hole.fit, hole.end) == (
        "clearance", "#10", "loose", "through_all",
    )
    assert hole.overrides_mm == {"HoleDiameter": spec.HANGER_CLEARANCE_DIA}
    assert blind_cut_dia_mm(hole) == CLEARANCE_MM[("#10", "loose")] == 6.045
    assert spec.HANGER_HOLE_DRILL == "E"
    assert spec.HANGER_CLEARANCE_DIA == pytest.approx(0.250 * 25.4)
    assert spec.HANGER_CLEARANCE_DIA == pytest.approx(6.35)
    assert spec.HANGER_CLEARANCE_DIA_PLACES == 3
    # The washer spotfaces are gone, not aliased (user ruling 2026-10-14).
    assert not [name for name in dir(spec) if name.startswith("HANGER_SPOTFACE")]
    # The 1/2 hanger-stud clearance is gone, not aliased.
    assert not hasattr(part, "STUD_HOLE_SPEC") and not hasattr(part, "STUD_HOLE_DIA")
    # Both stations sit on the knife line, centred on the crossbar.
    assert part.HANGER_X == spring_mount_geom.KNIFE[0] == (part.BAR_X0 + part.BAR_X1) / 2.0
    assert drawing.HANGER_X == part.HANGER_X
    assert (part.BAR_X0, part.BAR_X1) == pytest.approx((-27.573, -2.427))
    assert spec.HANGER_CROSSBAR_WIDTH == part.BAR_X1 - part.BAR_X0
    assert spec.HANGER_CROSSBAR_WIDTH == pytest.approx(25.146)  # .99
    # Washer bounds are parent-verified ASME Table 11 exports, not head guesses.
    assert (spec.HANGER_WASHER.OD_MIN, spec.HANGER_WASHER.OD_MAX) == (12.573, 13.081)
    assert spec.HANGER_WASHER.OD_ID_RUNOUT_MAX == pytest.approx(0.3302)
    assert spec.HANGER_WASHER_CONCENTRIC_ANNULUS_MIN == pytest.approx(3.0607)
    assert part.STUD_Z_REAR + spec.HANGER_WASHER.OD_MAX/2 < part.INNER_Z+part.GUSSET


def test_crossbar_median_control_cancels_the_socket_station_chain() -> None:
    # Owner ruling 2026-11-06: the #10 axes on D within ⌖.010|D, the drilled
    # row's ±.005.  D is the median plane of both as-cast crossbar sides
    # (owner ruling B5), so a side stands half the least .99 -.03 from it.
    assert spec.HANGER_CROSSBAR_CENTER_ZONE == pytest.approx(0.254)  # .010
    assert spec.HANGER_CROSSBAR_CENTER_TOL == pytest.approx(0.127)
    assert part.HANGER_BAR_HALF_WIDTH_MIN == pytest.approx(
        (part.BAR_X1 - part.BAR_X0 - spec.AS_CAST_BAND) / 2.0
    )
    assert part.HANGER_BAR_HALF_WIDTH_MIN == pytest.approx(12.192)


def test_hanger_x_locates_datum_d_not_a_hole() -> None:
    """Owner rulings B5 and D2 (#2333): the hanger axes stand BASIC zero on
    D, the median plane of the crossbar's two as-cast sides, held by
    ⌖.010|D; no hole-axis X dimension competes with it (farm run
    20261107T105312645Z: a 7.165 from a socket axis read as a second
    origin).  Sheet 3 keeps D's trace only, the native centreline between
    the two side faces; D's width, its tag and its 9.18 ±.03 station from
    datum G -- the model's own DStation -- stand on sheet 7."""
    tree = _drawing_tree()
    for owner, view in (("build", "detail_top"), ("_cast_datum_sheet", "bottom")):
        function = _function(tree, owner)
        (trace,) = _named_calls(function, "_insert_crossbar_median")
        assert ast.unparse(trace.args[1]) == view
        (sides,) = _named_calls(trace, "_exact_linear_entities")
        (x0, y0, z0), (x1, y1, z1) = _build_value(function, sides.args[1])
        # Both picks ride the bar's drafted side faces (owner ruling B1) at
        # one height, between the hanger holes, and D is their median.
        assert (y0, z0) == (y1, z1) == (pytest.approx(part.HALF_H - drawing.TOP_BREAK_DROP), 0.0)
        for x, outward in ((x0, -1.0), (x1, 1.0)):
            assert part._casting_occupies(x - outward * 1e-6, y0, 0.0), (view, x)
            assert not part._casting_occupies(x + outward * 1e-6, y0, 0.0), (view, x)
        assert x1 - x0 > part.BAR_X1 - part.BAR_X0
        assert (x0 + x1) / 2.0 == pytest.approx(part.HANGER_X), view
    assert (
        part.STUD_Z_FRONT + spec.HANGER_WASHER.OD_MAX
        < 0.0
        < part.STUD_Z_REAR - spec.HANGER_WASHER.OD_MAX
    )
    assert (part.BAR_X0 + part.BAR_X1) / 2.0 == pytest.approx(part.HANGER_X)
    # The frame is the hanger holes' only X control on the plan.
    frame = _labelled_call(
        tree, "add_feature_control_frame", "hanger axes on crossbar median plane"
    )
    assert ast.unparse(frame.args[1]) == "detail_top"
    assert ast.unparse(_keyword(frame, "datums")) == "('D',)"
    assert _keyword(frame, "diameter") is None
    assert ast.unparse(_keyword(frame, "tolerance")) == (
        "GEOMETRIC_TOLERANCES_IN['knife-hanger crossbar centring']"
    )
    assert spec.GEOMETRIC_TOLERANCES_IN["knife-hanger crossbar centring"] == ".010"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for retired in (
        "D_STATION_TEXT_XY",
        "crossbar median D from left boss tangent",
        "crossbar_median_x",
    ):
        assert retired not in source, retired
    # D's station is the model's own dimension from the G plane, as cast, and
    # only sheet 7's underside imports it.
    assert part.D_STATION == pytest.approx(part.CAST_DATUM_ORIGIN_XZ[0] - part.HANGER_X)
    assert part.D_STATION == pytest.approx(233.0977, abs=5e-5)
    assert f"{part.D_STATION / 25.4:.2f}" == "9.18"
    assert "DStation" in spec.DRAWING_DIMENSIONS["BarProfile"]
    assert "DStation" in spec.AS_CAST_DIMENSIONS["BarProfile"]
    assert spec.DRAWING_PRECISION_BY_NAME["DStation"] == 2
    assert [
        name
        for name, keep in vars(drawing).items()
        if name.endswith("_KEEP") and isinstance(keep, dict) and "DStation" in keep
    ] == ["DATUM_BOTTOM_KEEP"]
    assert '"horizontal_distance", D_STATION, "DStation"' in Path(part.__file__).read_text(
        encoding="utf-8"
    )


def test_datum_plane_traces_make_the_table_corner() -> None:
    """Owner rulings B6 and D2 (#2333): the hole-table origin is the corner
    of the cast datum planes F and G -- F through the two rear barrels' rear
    generators at the datum targets' height, G through the rear-west
    barrel's west generator -- drawn on the plan as thin phantom traces from
    that corner: F under both rear bosses to the rear-east one's tangent
    point, G up the rear-west boss past G1's."""
    x0, z0 = drawing.TABLE_ORIGIN_XZ
    assert (x0, z0) == part.CAST_DATUM_ORIGIN_XZ
    # The barrel's taken-out draft (owner ruling B1) has narrowed it by the
    # targets' height: the planes stand .8305 off the rear-west socket's
    # axis, .054 inside the Ø1.77 the faced top holds.
    drop = part.HALF_H - part.DATUM_TARGET_Y
    r = part.BOSS_DIA / 2.0 - drop * math.tan(math.radians(spec.DRAFT_DEG))
    assert (drop, r) == pytest.approx((39.624, 21.0953), abs=5e-5)
    assert r == pytest.approx(part._boss_radius(part.DATUM_TARGET_Y))
    assert (x0, z0) == pytest.approx((part.COLUMN_X + r, part.REAR_COLUMN_Z + r))
    assert (part.BOSS_DIA / 2.0 - r) / 25.4 == pytest.approx(0.0545, abs=5e-5)
    targets = part.CAST_DATUM_TARGETS
    assert targets["F1"][2] == targets["F2"][2] == pytest.approx(z0)
    assert targets["G1"][0] == pytest.approx(x0)
    assert (drawing.TABLE_TANGENT_LINE_STYLE, drawing.TABLE_TANGENT_LINE_WEIGHT) == (2, 0)
    # G's trace runs forward past G1's tangent point and ends on the boss.
    assert targets["G1"][2] - part.BOSS_DIA / 2.0 < drawing.TABLE_G_LINE_FRONT_Z < targets["G1"][2]
    for retired in ("TABLE_TANGENT_TOP_Y", "_draw_boss_tangents"):
        assert not hasattr(drawing, retired), retired


def _cast_datum_symbols():
    """Sheet 7's six target symbols, {name: (target point, symbol centre)} in
    sheet m.  The underside (rear up) and the elevation over it both centre
    on the casting's own extremes, set-screw boss face to west barrels
    (_datum_elevation_xy); farm run 20261111T023438415Z's native symbols
    read E1's point at (215.94, 172.00) and F1's at (215.94, 215.43) so."""
    scale = drawing.GEOMETRY_VIEW_SCALE / 1000.0
    cx, cy = drawing.DATUM_BOTTOM_CENTER
    middle = (drawing.PLAN_HALF_X + part.SET_BOSS_FACE_X) / 2.0
    placed = {}
    for name, (x, y, z) in part.CAST_DATUM_TARGETS.items():
        if name in drawing.DATUM_TARGETS_ON_ELEVATION:
            point = drawing._datum_elevation_xy(x, y)
        else:
            point = (cx + (x - middle) * scale, cy + z * scale)
        dx, dy = drawing.DATUM_TARGET_SYMBOL_OFFSETS[name]
        placed[name] = (point, (point[0] + dx, point[1] + dy))
    return placed


def test_cast_datum_target_symbols_stand_clear_on_sheet_seven() -> None:
    """Each native target symbol is a 14 mm circle on a leader from its
    point (farm run 20261111T023438415Z's natives: radius 7.0).  The six
    stand apart inside the frame, each a full arrow off its point: F1 and F2
    straight under their points in the band between the elevation and the
    underside, either side of datum D's width rows, E1 in the west window,
    the other three outside the underside's outline."""
    radius, arrow, ink = 0.007, 0.003556, drawing.INK_CLEARANCE
    placed = _cast_datum_symbols()
    assert set(placed) == set(drawing.DATUM_TARGET_SYMBOL_OFFSETS)
    assert drawing.SHEET_SCALES["CAST-DATUMS"] == drawing.SHEET_SCALE
    frame = drawing.SHEET_FRAME
    for name, (point, centre) in placed.items():
        assert math.dist(point, centre) - radius >= arrow + ink, name
        box = (centre[0] - radius, centre[1] - radius, centre[0] + radius, centre[1] + radius)
        assert frame[0] + ink <= box[0] and box[2] <= frame[2] - ink, name
        assert frame[1] + ink <= box[1] and box[3] <= frame[3] - ink, name
        assert _box_box_gap(box, TITLE_BLOCK) >= ink, name
    names = sorted(placed)
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            apart = math.dist(placed[first][1], placed[second][1]) - 2.0 * radius
            assert apart >= ink, (first, second)
    scale = drawing.GEOMETRY_VIEW_SCALE / 1000.0
    cx, cy = drawing.DATUM_BOTTOM_CENTER
    middle = (drawing.PLAN_HALF_X + part.SET_BOSS_FACE_X) / 2.0
    half_x = (drawing.PLAN_HALF_X - part.SET_BOSS_FACE_X) / 2.0 * scale
    half_z = drawing.PLAN_HALF_Z * scale
    underside = (cx - half_x, cy - half_z, cx + half_x, cy + half_z)
    for name in sorted(drawing.DATUM_TARGETS_ON_ELEVATION):
        point, centre = placed[name]
        assert centre[0] == point[0], name
        assert point[1] - centre[1] > radius, name
        assert centre[1] - radius - underside[3] >= ink, name
    for name in ("E2", "E3", "G1"):
        assert _box_point_gap(underside, placed[name][1]) - radius >= ink, name
    _point, (ex, ey) = placed["E1"]
    window = (
        cx + (part.BAR_X1 + part.GUSSET - middle) * scale,
        cy - part.INNER_Z * scale,
        cx + (part.INNER_X - middle) * scale,
        cy + part.INNER_Z * scale,
    )
    assert window[0] + ink <= ex - radius and ex + radius <= window[2] - ink
    assert ey + radius <= window[3] - ink
    # Datum D's width rows stand in the band over the underside, between the
    # two F symbols and under the elevation's rail, not in a window (rule
    # 14, machinist review of fad41f8525).
    # The callout stays one row (farm run 20261111T074741252Z printed nothing
    # of two rows above a value), at the width farm run 20261111T023438415Z
    # measured for it.
    rows = (*drawing.DATUM_BOTTOM_CALLOUTS_ABOVE["BarWidth"].splitlines(), ".99 ±.03")
    assert rows == ("CROSSBAR AT UNDERSIDE", ".99 ±.03")
    wx, wy = drawing.DATUM_BOTTOM_TEXT_OFFSETS["BarWidth"]
    half_w = 0.0569868 / 2.0
    half_h = len(rows) * _ROW_PITCH / 2.0
    block = (wx - half_w, wy - half_h, wx + half_w, wy + half_h - _ROW_SLACK)
    assert block[1] - underside[3] >= ink
    for name in sorted(drawing.DATUM_TARGETS_ON_ELEVATION):
        assert _box_point_gap(block, placed[name][1]) - radius >= ink, name
    assert drawing._datum_elevation_xy(0.0, -part.HALF_H)[1] - block[3] >= ink


@pytest.mark.parametrize("dashed", (False, True))
def test_datum_target_leaders_are_solid_for_points_their_view_shows(monkeypatch, dashed) -> None:
    """Farm run 20261111T023438415Z printed all six target leaders dashed,
    which Y14.5 reads as targets on the far side.  Every target stands on a
    face its own view shows (the boss bottoms and G1's generator from below,
    F's generators from the rear), so the symbol is inserted with a solid
    leader and a dashed readback fails the build."""
    from types import SimpleNamespace

    import _drawing_datum_target as datum_target

    target_xy, symbol_xy = (0.100, 0.050), (0.080, 0.040)
    inserted = []
    annotation = SimpleNamespace(
        SetPosition2=lambda *_xyz: True,
        GetPosition=lambda: (*symbol_xy, 0.0),
        GetLeaderCount=lambda: 1,
        GetLeaderPointsAtIndex=lambda _index: (*symbol_xy, 0.0, *target_xy, 0.0),
        GetAttachedEntityCount3=lambda: 1,
        GetAttachedEntityTypes=lambda: (datum_target._ATTACHED_TARGET_POINT,),
        IsDangling=lambda: False,
        GetDashedLeader=lambda: dashed,
    )
    symbol = SimpleNamespace(
        GetAnnotation=lambda: annotation,
        SetDatumTargetNotMoveable=lambda: True,
        GetDatumReferenceLabel=lambda _index: "E1",
        GetTargetShape=lambda: datum_target._SHAPE_POINT,
        GetDisplaySymbol=lambda: True,
        GetDisplayTargetArea=lambda: True,
        GetTextCount=lambda: 0,
        GetTextAtIndex=lambda _index: "",
    )

    def insert(*arguments):
        inserted.append(arguments)
        return symbol

    model = SimpleNamespace(
        SelectionManager=SimpleNamespace(SetSelectionPoint2=lambda *_arguments: True),
        Extension=SimpleNamespace(InsertDatumTargetSymbol3=insert),
        ClearSelection2=lambda _all: None,
    )
    monkeypatch.setattr(datum_target, "_select_annotation_entity", lambda *_a, **_k: None)
    monkeypatch.setattr(datum_target, "_early_bound", lambda entity, _interface: entity)
    monkeypatch.setattr(datum_target, "rebuild_drawing", lambda *_a, **_k: None)
    monkeypatch.setattr(
        datum_target._sw_type_info, "early_bound_or_flag", lambda entity, *_members: entity
    )

    def add():
        return datum_target.add_datum_target(
            SimpleNamespace(currentModel=model),
            object(),
            target="E1",
            target_xy=target_xy,
            symbol_xy=symbol_xy,
            entity=object(),
            entity_type="FACE",
            label="cast datum target E1",
        )

    if dashed:
        with pytest.raises(RuntimeError, match="leader is dashed, a far-side target"):
            add()
    else:
        assert add() is symbol
    # The arguments by the generated type library's own parameter names.
    methods, _getters, _setters = _members("IModelDocExtension")
    names = [argument.arg for argument in methods["InsertDatumTargetSymbol3"].args.args[1:]]
    (arguments,) = inserted
    sent = dict(zip(names, arguments, strict=True))
    assert (sent["Datum1"], sent["AreaStyle"], sent["ShowArea"], sent["ShowSymbol"]) == (
        "E1", 0, True, True,
    )
    assert (sent["LeaderLineStyle"], sent["LeaderBent"]) == (0, False)
    assert "GetDashedLeader" in _members("IAnnotation")[0]


def test_sockets_hold_position_to_the_cast_frame_then_to_the_faced_underside() -> None:
    """Owner rulings D2 and D6 (#2333): the 4X socket pattern stands
    ⌖Ø.06|E|F|G, the casting's own frame, and ⌖Ø.010|A, square to the faced
    underside.  A is not one of the upper frame's datums, so the two are
    stacked single-segment frames and never a Y14.5 composite; datum B (D3),
    the pattern the rail webs are held to, hangs on them."""
    import _drawing_gdt

    assert spec.GEOMETRIC_TOLERANCES_IN["tube socket pattern location"] == ".06"
    assert spec.GEOMETRIC_TOLERANCES_IN["tube socket pattern refinement"] == ".010"
    assert spec.SOCKET_PATTERN_LOCATION_ZONE == pytest.approx(0.06 * 25.4)
    assert spec.SOCKET_PATTERN_REFINEMENT_ZONE == pytest.approx(0.010 * 25.4)
    assert drawing.SOCKET_POSITION_QUANTITY == "4X"
    assert "A" not in drawing.CAST_DATUM_FRAME
    signature = inspect.signature(_drawing_gdt.add_feature_control_frame)
    assert signature.parameters["composite"].default is False
    assert (part.COLUMN_X, part.FRONT_COLUMN_Z) in {hole[:2] for hole in drawing.TABLE_HOLES}
    assert drawing.SOCKET_DATUM == "B"


# A native feature-control frame hangs from its position's top-left corner,
# 7.0 mm tall.  Farm run 20261111T023438415Z's cells: the symbol 7.00, a
# ".06" tolerance 9.31 (13.53 with its Ø), datum A 6.29 and datum B 5.53; a
# count row's line stands 12.56 under the top, its glyphs 4.5 over that.
_FRAME_HEIGHT = 0.007
_FRAME_CELLS = {"symbol": 0.00700, ".06": 0.00931, "Ø.06": 0.01353, "A": 0.00629, "B": 0.00553}
_FRAME_COUNT_DROP = 0.01256


def test_web_position_frames_stand_under_their_width_rows() -> None:
    """Each web's width is the model's own .51 ±.03, its three rows saying
    whose it is and that it holds on the underside (the web is drafted from
    there): the last row's line is the dimension line, 8.33 mm under the
    text point (farm run 20261111T023438415Z's three-row blocks), and the
    leaderless ⌖.06|A|B box hangs directly under it, flush with the rows'
    left end, over its section's caption.  Widths are that run's native
    rows: "2X WEB WIDTH" 31.86 mm, "AT UNDERSIDE" 31.40."""
    ink = drawing.INK_CLEARANCE
    frame = drawing.SHEET_FRAME
    width = sum(_FRAME_CELLS[cell] for cell in ("symbol", ".06", "A", "B"))
    sections = {
        "H-H": (
            drawing.RAIL_SECTION_KEEP["FrWebT"],
            drawing.RAIL_SECTION_CALLOUTS["FrWebT"],
            0.03186,
            drawing.RAIL_WEB_POSITION_FRAME_XY,
            drawing.RAIL_SECTION_CAPTION_XY,
        ),
        "E-E": (
            drawing.SIDE_SECTION_KEEP["SideWebT"],
            drawing.SIDE_WEB_QUALIFIER,
            0.03140,
            drawing.SIDE_WEB_POSITION_FRAME_XY,
            drawing.SIDE_SECTION_CAPTION_XY,
        ),
    }
    assert sections["H-H"][1].splitlines() == ["2X WEB WIDTH", "AT UNDERSIDE"]
    assert sections["E-E"][1].splitlines() == ["2X WEB", "AT UNDERSIDE"]
    for name, ((tx, ty), _callout, widest, (fx, fy), caption) in sections.items():
        line_y = ty - 0.00833
        left, right = tx - widest / 2.0, tx + widest / 2.0
        box = (fx, fy - _FRAME_HEIGHT, fx + width, fy)
        assert ink <= line_y - box[3] <= _ROW_PITCH, name
        assert left - 0.001 <= box[0] and box[2] <= right + 0.001, name
        assert box[1] - caption[1] >= ink, name
        assert frame[0] + ink <= box[0] and right <= frame[2] - ink, name
        assert _box_box_gap(box, TITLE_BLOCK) >= ink, name
    # H-H's rows stand right of the rail, by the flange thickness's lower
    # arrow tail (6.35 mm down its dimension line from the flange's
    # underside): the value row (16.79 mm) starts right of that line, the
    # two wider rows pass under the tail's end.
    (tx, ty), _callout, _widest, _frame_xy, _caption = sections["H-H"]
    assert (tx - 0.01679 / 2.0) - drawing.RAIL_SECTION_KEEP["FlangeT"][0] >= ink
    tail_end = (
        drawing.RAIL_SECTION_CENTER[1]
        + part.FLANGE_BOT_Y * drawing.GEOMETRY_VIEW_SCALE / 1000.0
        - 0.00635
    )
    assert tail_end - (ty - 0.00278 + 0.0045) >= ink


def test_boss_position_frame_stands_under_the_boss_and_socket_callouts() -> None:
    """The bosses' frame block -- the ⌖|Ø.06|A|B box and its 4X row -- stands
    in the left margin under the Ø1.77 callout's rows, on a level leader to
    the front-east barrel's outboard rim, under that callout's own leader.
    The socket callout stands over the boss callout (#2628 (d): under it,
    its leader crossed the front hanger station's line), its leader landing
    on the bore rim over the boss callout's.  Farm run 20261111T023438415Z's
    natives: each callout's leader leaves its underline's end (8.36 mm under
    the text point; 17.74 mm right of the boss callout's, 29.57 of the
    socket callout's) radially to its circle."""
    from _layout_geometry import Segment

    ink = drawing.INK_CLEARANCE
    fx, fy = drawing.BOSS_POSITION_FRAME_XY
    width = sum(_FRAME_CELLS[cell] for cell in ("symbol", "Ø.06", "A", "B"))
    block = (fx, fy - _FRAME_COUNT_DROP, fx + width, fy)
    assert drawing.SHEET_FRAME[0] + ink <= block[0]
    boss_x, boss_y = drawing.DETAIL_TOP_KEEP["C0Dia"]
    socket_x, socket_y = drawing.DETAIL_TOP_KEEP["B0Dia"]
    assert len(drawing.DETAIL_CALLOUTS["C0Dia"].splitlines()) == 2
    assert len(drawing.DETAIL_CALLOUTS["B0Dia"].splitlines()) == 2
    assert (boss_y - 0.00836) - block[3] >= ink
    assert (socket_y - 0.00836) - (boss_y + 0.0028 + 0.0045) >= ink
    assert socket_y + 0.0028 + 0.0045 <= drawing.SHEET_FRAME[3] - ink
    centre = _plan(-part.COLUMN_X, part.FRONT_COLUMN_Z)
    radius = part.BOSS_DIA / 2.0 * _S
    angle = math.radians(drawing.BOSS_POSITION_LANDING_DEG)
    landing = (centre[0] + radius * math.cos(angle), centre[1] + radius * math.sin(angle))
    # Outboard, a little under the socket's axis, and level with the box.
    assert 180.0 < drawing.BOSS_POSITION_LANDING_DEG <= 200.0
    assert block[2] + _BENT_SHOULDER + ink <= landing[0]
    assert abs(landing[1] - (fy - _FRAME_HEIGHT / 2.0)) <= 0.0015
    leader = Segment(block[2], landing[1], *landing)

    def callout_leader(shoulder, circle_r):
        run = math.dist(shoulder, centre)
        tip = tuple(c + (s - c) * circle_r / run for c, s in zip(centre, shoulder))
        return tip, Segment(*shoulder, *tip)

    # The boss callout's leader lands higher on that rim than the level
    # one, the socket callout's on the bore rim higher still; none comes
    # near another, and none reaches down to the front hanger station's
    # dimension line, whose top end is the front hole's level.
    boss_tip, boss_leader = callout_leader((boss_x + 0.01774, boss_y - 0.00836), radius)
    socket_tip, socket_leader = callout_leader(
        (socket_x + 0.02957, socket_y - 0.00836), part.BORE_DIA / 2.0 * _S
    )
    assert boss_tip[1] - landing[1] >= ink
    assert socket_tip[1] - boss_tip[1] >= ink
    assert _segment_gap(boss_leader, socket_leader) >= ink
    front_hole_y = _plan(part.HANGER_X, part.STUD_Z_FRONT)[1]
    for name, other in {"boss callout": boss_leader, "socket callout": socket_leader}.items():
        assert _segment_gap(leader, other) >= ink, name
        assert _box_segment_gap(block, ((other.x0, other.y0), (other.x1, other.y1))) >= ink, name
        assert min(other.y0, other.y1) - front_hole_y >= ink, name


def test_one_draft_angle_prints_for_each_band_on_sheet_sevens_elevation() -> None:
    """Owner ruling D4 (#2333): the print states each band once, as the
    model's own angle with the faces it governs -- the web ring's for the
    added draft, the upper boss barrels' for the taken-out draft -- on the
    cast-datum elevation's west end.  Each 2° wedge stands on the Top
    plane's trace, its arc raised over the boss tops, its rows parked on its
    own side of the view inside the frame."""
    keep = drawing.DATUM_FRONT_KEEP
    printed = {
        name: feature
        for feature, (name, _band) in spec.DRAFT_ANGLE_DIMENSIONS.items()
        if name in keep
    }
    assert printed == {"WebRingDraft": "WebRing", "BossesUpperDraft": "BossesUpper"}
    assert set(keep) == set(printed)
    assert {spec.DRAFT_ANGLE_DIMENSIONS[feature][1] for feature in printed.values()} == {
        spec.DRAFT_ADDED_DEVIATIONS_DEG,
        spec.DRAFT_TAKEN_OUT_DEVIATIONS_DEG,
    }
    marked = {
        name
        for names in spec.DRAWING_DIMENSIONS.values()
        for name in names
        if name.endswith("Draft")
    }
    assert marked == set(keep)
    for name, feature in printed.items():
        assert name in spec.DRAWING_DIMENSIONS[feature], name
        assert spec.DRAWING_PRECISION_BY_NAME[name] == spec.DRAFT_ANGLE_PLACES, name
    assert [
        table
        for table, kept in vars(drawing).items()
        if table.endswith("_KEEP")
        and isinstance(kept, dict)
        and any(str(name).endswith("Draft") for name in kept)
    ] == ["DATUM_FRONT_KEEP"]
    # Each callout names its own band's faces and none of the other's.
    callouts = drawing.DATUM_FRONT_CALLOUTS
    assert set(callouts) == set(drawing.DATUM_FRONT_TEXT_OFFSETS) == set(keep)
    faces = {
        "WebRingDraft": ("WEBS", "CROSSBAR", "POCKETS", "GUSSETS", "PADS", "SET-BOSS SIDES"),
        "BossesUpperDraft": ("FLANGE RIMS", "SET-BOSS FACE", "4X BOSS", "HUB BARRELS"),
    }
    # The added draft's band is the tighter one (the title block's angle row
    # is ±1°), so rule 4 has its callout say what the 2° minimum holds, and
    # rule 3 gives the form: the wall, with its value.  Rule 7 allows a
    # callout two lines of words, so the faces share the first (machinist
    # reviews of 518e3d01e1 and 7dfc6b6c5f).  The taken-out band is the title
    # block's own and gives no reason.  The wall's text is the wall accepted
    # under the package's thin-wall target (delegated ruling 2026-11-24
    # (Main), precedent: owner ruling 2026-11-01, #2144 (rulings.md D15);
    # RV-14), composed in a module only the
    # drawing imports (the drawing itself owns no stated limit,
    # test_drawing_specification_purity; a library module reads no builder,
    # test_buildgraph), and the builder
    # proves both of the tap's walls hold it.
    import fr_top_frame_callouts as stated_walls

    assert stated_walls.ADDED_DRAFT_WALL_CALLOUT == "HOLDS 2-56 TAP WALL .076 MIN"
    held = min(part.KEEPER_TAP_DRILL_WALL_MARGIN, part.KEEPER_TAP_THREAD_WALL_MARGIN)
    assert math.floor(round(held / spec.IN * 1000.0, 6)) / 1000.0 == pytest.approx(
        spec.KEEPER_TAP_WALL_ACCEPTED_MM / spec.IN
    )
    reason = {
        "WebRingDraft": [stated_walls.ADDED_DRAFT_WALL_CALLOUT],
        "BossesUpperDraft": [],
    }
    for name, own in faces.items():
        rows = callouts[name].splitlines()
        assert len(rows) == 2 and rows[0].startswith("DRAFT, "), name
        listed = rows[: len(rows) - len(reason[name])]
        assert rows[len(listed) :] == reason[name], name
        assert all(len(row.split()) <= 6 for row in reason[name]), name
        assert all(face in " ".join(listed) for face in own), name
        (other,) = set(faces) - {name}
        assert not [face for face in faces[other] if face in callouts[name]], name
    assert sum(spec.DRAFT_ADDED_DEVIATIONS_DEG) < sum(
        spec.DRAFT_TAKEN_OUT_DEVIATIONS_DEG
    )
    (stated,) = reason["WebRingDraft"]
    assert keeper_screw.THREAD.lstrip("#") in stated
    # The stated wall is D15's accepted .076, which the keeper drill's wall
    # holds at the 2° minimum (.0767) and loses a degree lower (.0596, under
    # the .060 floor).
    assert f"{spec.KEEPER_TAP_WALL_ACCEPTED_MM / 25.4:.3f}".lstrip("0") in stated.split()
    drill_rise = part._KEEPER_DRILL_BOTTOM_Y + part.HALF_H
    thinner = part.KEEPER_TAP_DRILL_WALL_MARGIN - drill_rise * (
        part.DRAFT_T_ADDED_MIN - math.tan(math.radians(spec.DRAFT_DEG - 1.0))
    )
    assert (
        WALL_TARGET_MM
        > part.KEEPER_TAP_DRILL_WALL_MARGIN
        >= spec.KEEPER_TAP_WALL_ACCEPTED_MM
        > part.WALL_FLOOR_MM
        > thinner
    )
    assert part.KEEPER_TAP_THREAD_WALL_MARGIN >= part.KEEPER_TAP_DRILL_WALL_MARGIN
    assert thinner / 25.4 == pytest.approx(0.0596, abs=5e-5)
    # One band covers every added-draft face by owner ruling D4, though the
    # wall it holds stands in the rail web alone: RV-12 records the ruling
    # for a reviewer who would loosen the other faces (machinist review of
    # fad41f8525, r3).
    (rv12,) = [
        entry
        for entry in load_exceptions(CAD_ROOT / "config", "fr_top_frame", "part")
        if entry.id == "RV-12"
    ]
    assert rv12.kind == "accept"
    assert "owner ruling 2026-11-10 (#2333, D4)" in rv12.reason
    for row in callouts["WebRingDraft"].splitlines():
        assert row in rv12.where, row
    # The wedges: the web's outer face opens outward going up (added draft),
    # the upper barrel closes inward (taken out above the faced top).
    wedges = drawing.DATUM_DRAFT_WEDGES
    assert set(wedges) == set(keep)
    web_x, web_lean, web_rise = wedges["WebRingDraft"]
    barrel_x, barrel_lean, barrel_rise = wedges["BossesUpperDraft"]
    assert (web_x, barrel_x) == (part.WEB_OUT_X, drawing.PLAN_HALF_X)
    y = part.FLANGE_BOT_Y - part.ROOT_FILLET_R - 1.0
    z = spec.SIDE_SECTION_Z
    lean = math.tan(math.radians(spec.DRAFT_DEG))
    for at_y in (-part.HALF_H + 1.0, y):
        face = part.WEB_OUT_X + (at_y + part.HALF_H) * lean
        assert part._casting_occupies(face - 1e-3, at_y, z) and not part._casting_occupies(
            face + 1e-3, at_y, z
        )
    assert web_lean == 1.0
    top = part.HALF_H + part.BOSS_ABOVE
    assert part._boss_radius(top) < part._boss_radius(part.HALF_H) == part.BOSS_DIA / 2.0
    assert barrel_lean == -1.0
    trace = drawing._datum_elevation_xy(0.0, 0.0)[1]
    boss_top = drawing._datum_elevation_xy(0.0, top)[1]
    ink = drawing.INK_CLEARANCE
    frame = drawing.SHEET_FRAME
    blocks = {}
    for name, (x, lean_sign, rise) in wedges.items():
        vertex = drawing._datum_elevation_xy(x, 0.0)[0]
        kx, ky = keep[name]
        # The value's point stands on the arc, inside its 2° wedge.
        assert ky == pytest.approx(trace + rise, abs=1e-5), name
        assert 0.0 < (kx - vertex) * lean_sign < rise * lean, name
        assert ky - boss_top >= ink, name
        # Its rows as farm run 20261111T023438415Z printed these callouts
        # (then on sheet 2) about their points: the added band's stacked
        # +1°/0° stands its upper limit 5.56 mm over the point and its second
        # callout row 10.08 under it; the taken-out band's ±1° is the plain
        # three rows, 2.78 over and 8.33 under.  A further row moves both
        # ends half a row pitch (2.78 mm).  Glyphs stand 4.5 over a row's
        # line and ran 2.63 mm each at the widest (the rows' wording has
        # changed since: their widths are that estimate until a farm run
        # prints them).
        tx, ty = drawing.DATUM_FRONT_TEXT_OFFSETS[name]
        rows = callouts[name].splitlines()
        half = max(map(len, rows)) * 0.00263 / 2.0
        band = spec.DRAFT_ANGLE_DIMENSIONS[printed[name]][1]
        stacked = band == spec.DRAFT_ADDED_DEVIATIONS_DEG
        over, under = (0.00556, 0.01008) if stacked else (0.00278, 0.00833)
        more = (len(rows) - 2) * 0.00278
        block = (tx - half, ty - under - more, tx + half, ty + over + more + 0.0045)
        blocks[name] = block
        assert frame[0] + ink <= block[0] and block[2] <= frame[2] - ink, name
        assert block[3] <= frame[3] - ink, name
        assert block[1] - boss_top >= ink, name
    assert abs(web_rise - barrel_rise) >= 0.005
    assert _box_box_gap(blocks["WebRingDraft"], blocks["BossesUpperDraft"]) >= ink
    # The added draft's rows stand left over the view, the taken-out
    # draft's right of it: neither block covers the other's arc point.
    assert blocks["WebRingDraft"][2] < keep["WebRingDraft"][0] < keep["BossesUpperDraft"][0]
    assert keep["BossesUpperDraft"][0] < blocks["BossesUpperDraft"][0]
    for name, block in blocks.items():
        (other,) = set(blocks) - {name}
        assert _box_point_gap(block, keep[other]) >= ink, name


def test_drawing_script_leaves_the_layout_audits_gate_as_declared() -> None:
    """The layout audit's enforced kinds are the repository's gate.  A
    drawing script that rebinds them at import turns its own REPORT run soft,
    and every later test of the session with it; the script may read the
    audit module and never assign into it."""
    import _layout_audit

    assert _layout_audit.ENFORCED_KINDS, "the audit module's gate reads empty"
    assert _layout_audit.ENFORCED_KINDS <= _layout_audit.GATING_KINDS


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
    # and a run to the clearance rim, crossing where R5 reported.  R5's front
    # hanger stood 87.06 off the summing axis (before #1038's 93.41).
    r5_centre = (
        R5_PLAN_CENTER[0] + part.HANGER_X * _S,
        R5_PLAN_CENTER[1] - (spec.SUMMING_Z - 87.06) * _S,
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


def test_gusset_run_and_d_station_stand_under_the_underside_view() -> None:
    """Machinist review of fad41f8525 (rule 14): the gusset run's rows stood
    in the west window beside half an empty sheet.  Its line now stands
    under the view with its rows right of it, and D's station under those,
    over the title block."""
    ink = drawing.INK_CLEARANCE
    scale = drawing.GEOMETRY_VIEW_SCALE / 1000.0
    view_bottom = drawing.DATUM_BOTTOM_CENTER[1] - drawing.PLAN_HALF_Z * scale
    run_line = drawing.DATUM_BOTTOM_KEEP["GussetRunE"][1]
    assert view_bottom - run_line >= 0.006
    gx, gy = drawing.DATUM_BOTTOM_TEXT_OFFSETS["GussetRunE"]
    rows = (".71 ±.03", drawing.DATUM_BOTTOM_CALLOUTS["GussetRunE"])
    half_w = max(map(len, rows)) * _ROW_CHAR / 2.0
    run = (gx - half_w, gy - _ROW_PITCH, gx + half_w, gy + _ROW_PITCH - _ROW_SLACK)
    assert view_bottom - run[3] >= ink
    # The run's 6 mm line and its 6.35 mm arrow tail end left of the value,
    # which stands on the line's height; the callout's row is a row lower.
    bar_side = (
        drawing.DATUM_BOTTOM_CENTER[0]
        + (part.BAR_X1 - (drawing.PLAN_HALF_X + part.SET_BOSS_FACE_X) / 2.0) * scale
    )
    value_left = gx - len(rows[0]) * _ROW_CHAR / 2.0
    assert value_left - (bar_side + part.GUSSET * scale + 0.00635) >= ink
    assert run_line - (gy - _ROW_PITCH + 0.0035) >= ink
    # A value alone prints over its line (farm run 20261111T070346684Z: the
    # station's line 2.8 mm under its text point, its caps 1.7 over it).
    sx, sy = drawing.DATUM_BOTTOM_KEEP["DStation"]
    station = (sx - 0.011, sy - 0.0028, sx + 0.011, sy + 0.0017)
    assert run[1] - station[3] >= ink
    assert station[1] - TITLE_BLOCK[3] >= ink
    assert drawing.SHEET_FRAME[1] + ink <= station[1]


def test_geometry_front_prints_the_models_rail_height_as_a_reference() -> None:
    """fd0350a85 dropped the geometry front view's only dimension, leaving
    the rail web's depth undefined on sheet 2.  It is back as the model's own
    RingHeight -- the web ring's driving extrude depth, the same finished
    thickness F-F prints as the grip -- printed as a reference at the grip's
    places, so the grip alone carries the .XX band."""
    import ast

    from _drawing_dimension_import import _features_owning

    # The elevation carries the rail height alone: the web root radius
    # stands on section H-H's own root (RAIL_SECTION_KEEP).
    assert set(drawing.GEOMETRY_FRONT_KEEP) == {"RingHeight"}
    assert drawing.GEOMETRY_CALLOUTS["RingHeight"] == "RAIL HEIGHT"
    assert _features_owning(
        spec.DRAWING_DIMENSIONS, drawing.GEOMETRY_FRONT_KEEP, view_label="geometry front"
    ) == ("WebRing",)
    assert spec.DRAWING_DIMENSIONS["WebRing"] == {"RingHeight", "WebRingDraft"}
    assert "WebRingDraft" not in drawing.GEOMETRY_FRONT_KEEP
    assert spec.DRAWING_PRECISION_BY_NAME["RingHeight"] == spec.HANGER_GRIP_PLACES == 3
    assert part.RING_HEIGHT == spec.HANGER_GRIP == pytest.approx(36.4998)
    # The model drives the depth and authors no band on it: it is not an
    # as-cast dimension (owner ruling B2's ±.03 table) and no tolerance call
    # in the build names the web ring or its dimension.
    assert "WebRing" not in spec.AS_CAST_DIMENSIONS
    assert "RingHeight" not in set().union(*spec.AS_CAST_DIMENSIONS.values())
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
    assert compact.count('"WebRing","webring",depth=RING_HEIGHT,depth_name="RingHeight",') == 1
    assert compact.count("drive_jobs.append((\"RingHeight@WebRing\",'\"RingHeight\"'))") == 1
    # The sheet imports it once, callouts it, marks it after the callout and
    # reads its places back with every other import.
    body = _function(_drawing_tree(), "build")
    (imported,) = [
        call
        for call in _named_calls(body, "curate_view_dimensions")
        if ast.unparse(_keyword(call, "keep")) == "GEOMETRY_FRONT_KEEP"
    ]
    (callouts,) = [
        call
        for call in _named_calls(body, "set_dimension_callouts")
        if ast.unparse(call.args[1]) == "geometry_annotations"
    ]
    (reference,) = _named_calls(body, "_reference_model_rail_height")
    assert [ast.unparse(arg) for arg in reference.args] == [
        "adapter",
        "geometry_front_dimensions",
    ]
    assigned = {
        ast.unparse(node.targets[0]): node
        for node in ast.walk(body)
        if isinstance(node, ast.Assign)
    }
    assert assigned["geometry_front_dimensions"].value is imported
    assert ast.unparse(assigned["geometry_annotations"].value) == (
        "[*geometry_top_dimensions, *geometry_front_dimensions]"
    )
    collected = assigned["imported_annotations"]
    assert "*geometry_annotations" in ast.unparse(collected.value)
    assert imported.lineno < callouts.lineno < reference.lineno < collected.lineno
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


def test_web_root_radius_stands_on_the_rail_sections_left_root() -> None:
    """Owner ruling B2 (#2333): the T's cast root radius is the model's own
    RootR, R.12 ±.03, the fillet feature's dimension.  SolidWorks hangs it
    on the feature's first edge and shows it where a view sees that edge
    end-on (farm run 20261111T004615500Z: with a side rail's root first only
    the elevation took it, and its leader ended on a corner boss's face,
    machinist review of fad41f8525).  So the build lists the +Z rail's
    window root first, picked on H-H's station, and H-H keeps the radius:
    its rows stand under the T's left, and their leader climbs to the left
    root clear of the flange width's extension line and the web width's
    arrow tail."""
    assert spec.DRAWING_DIMENSIONS["TRootFillets"] == {"RootR"}
    assert "RootR" in spec.AS_CAST_DIMENSIONS["TRootFillets"]
    assert spec.DRAWING_PRECISION_BY_NAME["RootR"] == 2
    assert part.ROOT_FILLET_R / 25.4 == pytest.approx(0.12)
    assert "RootR" not in drawing.GEOMETRY_FRONT_KEEP
    assert "RootR" not in drawing.GEOMETRY_CALLOUTS
    assert drawing.RAIL_SECTION_CALLOUTS["RootR"] == "TYP WEB ROOT"
    assert part.LAND_X1 < spec.RAIL_SECTION_X < part.COLUMN_X - part.BOSS_DIA / 2.0
    # H-H stands +Z right (its _orient_cut_section axis), so the window-side
    # root is the T's left one.  The section's ink as farm run
    # 20261111T070346684Z printed it: the flange's top at y 211.392, the
    # widths' extension lines from 1.0 mm over the Top plane's trace, the
    # web width's 6.35 mm arrow tail; a radius's underline ends 17.933 mm
    # right of its text point, one row under it.
    ink = drawing.INK_CLEARANCE
    s = drawing.GEOMETRY_VIEW_SCALE / 1000.0
    rail_x = drawing.RAIL_SECTION_PROFILE_X
    top_plane_y = 0.211392 - part.HALF_H * s
    radius = part.ROOT_FILLET_R
    centre_y = part.FLANGE_BOT_Y - radius
    face_z = part.WEB_IN_Z - (centre_y + part.HALF_H) * part.DRAFT_T
    centre_z = face_z - radius / math.cos(math.atan(part.DRAFT_T))
    centre = (
        rail_x + (centre_z - abs(part.FRONT_COLUMN_Z)) * s,
        top_plane_y + centre_y * s,
    )
    flange_left = rail_x - part.RAIL_W_FR / 2.0 * s
    web_left = rail_x - part.WEB_T / 2.0 * s
    assert flange_left < centre[0] < web_left
    x, y = drawing.RAIL_SECTION_KEEP["RootR"]
    rows = ("R.12 ±.03", drawing.RAIL_SECTION_CALLOUTS["RootR"])
    half_w = max(map(len, rows)) * _ROW_CHAR / 2.0
    block = (x - half_w, y - _ROW_PITCH, x + half_w, y + _ROW_PITCH - _ROW_SLACK)
    assert flange_left - block[2] >= ink
    assert centre[1] - block[3] >= ink
    caption_top = drawing.RAIL_SECTION_CAPTION_XY[1] + 0.0035
    assert block[1] - caption_top >= ink
    start = (x + 0.017933, y - 0.005556)
    reach = math.dist(start, centre)
    along = ((centre[0] - start[0]) / reach, (centre[1] - start[1]) / reach)

    def off_leader(point: tuple[float, float]) -> float:
        return abs((point[0] - start[0]) * along[1] - (point[1] - start[1]) * along[0])

    extension_foot = (flange_left, top_plane_y + 0.001)
    assert (
        extension_foot[1]
        > start[1] + (extension_foot[0] - start[0]) * along[1] / along[0]
    )
    assert off_leader(extension_foot) >= ink
    web_line_y = drawing.RAIL_SECTION_KEEP["FrWebT"][1] - 0.00833
    tail_end = (web_left - 0.00635, web_line_y)
    assert start[1] < tail_end[1] < centre[1]
    assert off_leader(tail_end) >= ink
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


def test_ream_sketch_holds_two_driven_circles_and_the_press_band() -> None:
    # Two circles in one underside sketch (one per station, owner ruling
    # 2026-11-08 (Pedro), #2144 item 11.3), both driven by the
    # HangerPinHoleDia global; the rear one owns the marked name.  Each
    # prints the dowel spec's stacked +.0005/-.0000; the symmetric band is
    # the as-cast dimensions' alone.
    from _fit_deviations import deviations

    assert len(part.HANGER_PIN_CONTOURS) == 2
    assert part.swept_contours_disjoint(part.HANGER_PIN_CONTOURS)
    assert deviations(spec.HANGER_PIN_HOLE_DIA_BAND) == pytest.approx((0.0, 0.0127))
    assert "HangerPinProfile" not in spec.AS_CAST_DIMENSIONS


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


def test_knockouts_land_the_punch_and_keep_their_walls() -> None:
    """Rule 16: each blind press ream gets a #51 knockout drilled up on the
    ream's axis (codjiflo, PR #1978: drilled from the top, the two holes'
    opposing wander left a #43 0.200 of floor).  Owner decision 2026-11-19
    (#3124, item 3): the ream ends in a 118° drill point and the dowel is
    pressed to its proud, not to a floor, so the knockout starts from the
    point and the floor land (RV-06) is gone; THRU was rejected, its exit
    under the washer's rim.  Owner ruling 2026-10-27 (option c): no "REAM
    SETUP" and no frame, so the knockout is off its ream by the drawn
    coaxiality's implied ±0.13 per axis; a 1/16 in punch anywhere in the
    largest knockout still lands on the pressed end's flat.  The knockout
    prints two places, Ø1.70, under the DRILLED HOLES row (machinist review,
    run 20261027T175429300Z).  It keeps its walls where its shift is
    greatest, at the top, and a land inside the top break; the washer over
    it bears on its width round the hole (owner ruling 2026-11-24, fit
    audit C12, option A), not on an unbroken ring inside it."""
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
        spec.HANGER_GRIP + spec.HANGER_GRIP_TOL - spec.HANGER_PIN_HOLE_DEPTH
    )
    # The model's knockout circle where it breaks into the ream's point.
    assert spec.HANGER_KNOCKOUT_ENTRY_DEPTH == pytest.approx(
        spec.HANGER_PIN_HOLE_DEPTH
        + (spec.HANGER_PIN_HOLE_DIA - spec.HANGER_KNOCKOUT_DIA)
        / 2.0
        / math.tan(math.radians(59.0))
    )
    assert spec.HANGER_PIN_HOLE_POINT_H == pytest.approx(
        spec.HANGER_PIN_HOLE_DIA / 2.0 / math.tan(math.radians(59.0)), abs=1e-5
    )
    # Codjiflo round 6: the ~14 D knockout takes a taper-length #51 (2 in
    # flute, MSC 63725519) reaching the top from the underside, and the
    # punch reaches from the faced top through the knockout and the ream
    # to the underside, the full grip at its far limit, whatever the depth.
    reach = spec.HANGER_GRIP + spec.HANGER_GRIP_TOL
    assert spec.HANGER_KNOCKOUT_DRILL_REACH == pytest.approx(reach)
    assert spec.HANGER_KNOCKOUT_PUNCH_REACH_MIN == pytest.approx(reach)
    assert spec.HANGER_KNOCKOUT_PUNCH_REACH_MIN == pytest.approx(36.6268)
    # The knockout's longest run plus the push-out from the shallowest ream
    # sum to the same reach: the ream's depth cancels.
    assert spec.HANGER_KNOCKOUT_LENGTH_MAX + spec.HANGER_PIN_HOLE_DEPTH == pytest.approx(
        spec.HANGER_KNOCKOUT_PUNCH_REACH_MIN
    )
    assert spec.HANGER_KNOCKOUT_DEPTH_D == pytest.approx(
        spec.HANGER_KNOCKOUT_LENGTH_MAX / spec.HANGER_KNOCKOUT_DIA_PRINTED
    )
    assert spec.HANGER_KNOCKOUT_DEPTH_D == pytest.approx(14.060, abs=5e-4)
    assert spec.HANGER_KNOCKOUT_DRILL_FLUTE_LEN == pytest.approx(2.0 * 25.4)
    assert spec.HANGER_KNOCKOUT_DRILL_FLUTE_LEN > spec.HANGER_KNOCKOUT_DRILL_REACH
    per_mm = spec.DRILL_DRIFT_PER_MM
    # The drawn coaxiality's real worst case: the title block's .XXX ±.005
    # on the implied zero, along both axes at once.  The ream's own drift
    # moves the pressed dowel with it, so it adds nothing at the dowel.
    assert spec.HANGER_KNOCKOUT_COAXIAL_TOL == pytest.approx(0.127)
    eccentricity = math.hypot(0.127, 0.127)
    assert spec.HANGER_KNOCKOUT_ECCENTRICITY == pytest.approx(eccentricity)
    # The punch lands on the dowel's pressed end flat (inside the chamfer)
    # at B18.8.2's smallest point, 0.110 in (the vendor model's 0.115 is the
    # band's middle), less the largest knockout off centre by the drawn
    # coaxiality.
    assert (dowel.POINT_DIA_MIN, dowel.POINT_DIA_MAX) == pytest.approx(
        (0.110 * 25.4, 0.120 * 25.4)
    )
    assert dowel.POINT_DIA_MIN < dowel.ENDS.point_dia < dowel.POINT_DIA_MAX
    land = (dowel.POINT_DIA_MIN - spec.HANGER_KNOCKOUT_DIA_MAX) / 2.0 - eccentricity
    assert spec.HANGER_KNOCKOUT_PUNCH_LAND_MIN == pytest.approx(land)
    assert land == pytest.approx(0.31569487757861703)
    # The flat floor, its corner limit, its land and its exception are gone.
    for retired in (
        "HANGER_KNOCKOUT_FLOOR_ECCENTRICITY",
        "HANGER_PIN_FLOOR_LAND_MIN",
        "HANGER_PIN_FLOOR_CORNER_R_MAX",
        "HANGER_PIN_FLOOR_FILLET_LIFT_MAX",
        "HANGER_PIN_FLOOR_BEARING_R",
        "HANGER_PIN_FLOOR_BEARING_LAND_MIN",
        "HANGER_PIN_FLOOR_BEARING_LAND_TARGET",
        "HANGER_PIN_HOLE_DEPTH_TOL",
    ):
        assert not hasattr(spec, retired), retired
    exceptions = {
        entry.id
        for entry in machinist_exceptions.load_exceptions(
            _Path(spec.__file__).resolve().parents[1] / "config", "fr_top_frame", "part"
        )
    }
    assert "RV-06" not in exceptions
    # THRU rejected: at the .300 station the ream's exit edge would stand
    # under the washer even at its smallest OD.
    washer = part.HANGER_WASHER
    assert spec.HANGER_PIN_X - spec.HANGER_PIN_HOLE_DIA_MAX / 2.0 < washer.OD_MIN / 2.0
    # The process row names the drill only (machinist review: "REAM SETUP"
    # was a method; owner ruling 2026-10-27), the row under the native size
    # the start: the ream's drill point.
    assert spec.HANGER_KNOCKOUT_CALLOUT_ABOVE == "#51 DRILL"
    assert "SETUP" not in spec.HANGER_KNOCKOUT_CALLOUT_BELOW
    assert spec.HANGER_KNOCKOUT_CALLOUT_BELOW == "FROM REAM POINT;\nMHA-SM-VN-53 KNOCKOUT"
    drift = per_mm * spec.HANGER_KNOCKOUT_LENGTH_MAX
    assert part.HANGER_KNOCKOUT_DRIFT == pytest.approx(drift)
    setup_drift = per_mm * spec.HANGER_PIN_HOLE_DEPTH
    # At the top: the ream's drift at its full diameter's MIN depth, where
    # the knockout starts, the coaxiality's .005 along the wall's axis, and
    # the knockout's own drift up its run.
    shift = setup_drift + spec.HANGER_KNOCKOUT_COAXIAL_TOL + drift
    assert part.HANGER_KNOCKOUT_SHIFT_AT_TOP == pytest.approx(shift)
    assert shift == pytest.approx(0.318779, abs=5e-6)
    knockout_r = spec.HANGER_KNOCKOUT_DIA_MAX / 2.0
    clearance_r = spec.HANGER_CLEARANCE_DIA_MAX / 2.0
    # The knockout, on its ream's axis, stands at the ream's .XXX band from
    # nominal (the one +X ream since owner ruling 2026-11-08 (Pedro), #2144
    # item 11.3), plus its shift at the top.
    near = spec.HANGER_PIN_X - spec.HANGER_PIN_X_TOL - shift
    reach = part.HANGER_BAR_HALF_WIDTH_MIN - spec.HANGER_CROSSBAR_CENTER_TOL
    assert part.KNOCKOUT_BAR_WALL == pytest.approx(
        reach - spec.HANGER_PIN_X - spec.HANGER_PIN_X_TOL - knockout_r - shift
    )
    assert part.KNOCKOUT_SCREW_WALL == pytest.approx(
        near - knockout_r - clearance_r - part.HANGER_DRIFT_AT_TOP
    )
    assert part.KNOCKOUT_BAR_WALL == pytest.approx(3.097521, abs=5e-6)
    assert part.KNOCKOUT_SCREW_WALL == pytest.approx(2.854942, abs=5e-6)
    assert min(part.KNOCKOUT_BAR_WALL, part.KNOCKOUT_SCREW_WALL) >= 2.032
    assert part.KNOCKOUT_TOP_BREAK_LAND == pytest.approx(
        reach - part.EDGE_BREAK_PRINTED_MAX - spec.HANGER_PIN_X
        - spec.HANGER_PIN_X_TOL - knockout_r - shift
    )
    assert part.KNOCKOUT_TOP_BREAK_LAND == pytest.approx(1.319521, abs=5e-6)
    # The knockout exits under the washer; the former unbroken-ring guard is
    # gone (owner ruling 2026-11-24, fit audit C12, option A): the washer's
    # seat is its bearing width round the hole
    # (test_hanger_walls_meet_the_target_after_drift).
    assert not hasattr(part, "HANGER_WASHER_KNOCKOUT_RING_MIN")


def test_hanger_walls_meet_the_target_after_drift() -> None:
    """Q7 option C: the #10 holes are drilled from the faced underside and
    the dowel reams cut from it, each located from the #10 hole's axis
    there, so each hole's 0.3 deg drift is nil at the seat.  The ream's
    full diameter is .50 MIN, open above (owner decision 2026-11-19, #3124
    item 3), so its drift is charged over the whole grip.  Every wall round
    a ream, at the print-worst bands, less the drift of each hole either
    side of it, meets rule 17's .080 target.  Owner ruling 2026-11-08
    (Pedro), #2144 item 11.3: one ream per station, +X of its screw at its
    .XXX band."""
    per_mm = math.tan(math.radians(spec.KEEPER_TAP_DRILL_WANDER_DEG))
    assert spec.DRILL_DRIFT_PER_MM == pytest.approx(per_mm)
    drift = per_mm * (spec.HANGER_GRIP + spec.HANGER_GRIP_TOL)
    assert part.HANGER_REAM_DRIFT_MAX == pytest.approx(drift)
    assert drift == pytest.approx(0.1918, abs=1e-4)
    ream_r = spec.HANGER_PIN_HOLE_DIA_MAX / 2.0
    clearance_r = spec.HANGER_CLEARANCE_DIA_MAX/2
    off = spec.HANGER_PIN_X_TOL

    # D is the median of both as-cast sides: each stands half the least
    # .99 -.03 from it (owner ruling B5).
    outer_loss = spec.AS_CAST_BAND / 2.0
    walls = {
        "ream | screw hole": (
            spec.HANGER_PIN_X - off - ream_r - clearance_r,
            2.0 * drift,
            part.PIN_HOLE_SCREW_WALL,
        ),
        "ream | bar +X face": (
            part.BAR_X1 - (part.PIN_HOLE_X + off) - ream_r - outer_loss
            - spec.HANGER_CROSSBAR_CENTER_TOL,
            drift,
            part.PIN_HOLE_BAR_WALL,
        ),
    }
    for label, (print_worst, charged, wall) in walls.items():
        assert wall == pytest.approx(print_worst - charged), label
        assert wall >= 2.032, label
    assert part.PIN_HOLE_BAR_WALL == pytest.approx(2.545071, abs=5e-6)
    assert part.PIN_HOLE_SCREW_WALL == pytest.approx(2.302492, abs=5e-6)
    # The band's upper deviation is the deepest hole whose tallest point
    # keeps the wall target under the faced top: a THRU ream is out of band.
    # The tallest point is the sharpest the title block's ±1° accepts, 117°,
    # on the ream band's largest diameter; the #31 pilot's at its DRILLED
    # HOLES limit is shorter (#3130).
    sharpest = math.radians((118.0 - 1.0) / 2.0)
    ream_point = spec.HANGER_PIN_HOLE_DIA_MAX / 2.0 / math.tan(sharpest)
    pilot_point = (0.120 * 25.4 + spec.DRILL_OVERSIZE) / 2.0 / math.tan(sharpest)
    assert pilot_point < ream_point
    assert spec.HANGER_PIN_HOLE_POINT_H_MAX == pytest.approx(ream_point)
    assert spec.HANGER_PIN_HOLE_POINT_H_MAX == pytest.approx(0.969, abs=5e-4)
    depth_max = spec.HANGER_PIN_HOLE_DEPTH + max(spec.HANGER_PIN_HOLE_DEPTH_BAND)
    assert spec.HANGER_PIN_HOLE_DEPTH_MAX == pytest.approx(depth_max)
    assert part.PIN_HOLE_POINT_MARGIN == pytest.approx(
        spec.HANGER_GRIP - spec.HANGER_GRIP_TOL - depth_max
        - spec.HANGER_PIN_HOLE_POINT_H_MAX
    )
    assert 2.032 <= part.PIN_HOLE_POINT_MARGIN < 2.032 + 1e-5
    assert (
        depth_max + spec.HANGER_PIN_HOLE_POINT_H_MAX
        < spec.HANGER_GRIP - spec.HANGER_GRIP_TOL
    )
    # Entry wander at the deepest pocket roof and the finished top.  Every
    # ream sits across the line at its implied-zero .XXX off the screw axis.
    # The nearer station (the rear one since #1038 moved the front one .25
    # out) stands at its .XXX from the rear sockets' axis (#2628 (d)); a
    # pocket end stands two as-cast bands out (its station from the front
    # socket and the chained length), and the rear axis stands the socket
    # pattern's Ø.010 refinement off the front one.
    pocket = part.BAR_POCKET_HOLE_WALLS
    cast = spec.AS_CAST_BAND
    assert part._POCKET_STATION == pytest.approx(
        min(abs(part.STUD_Z_FRONT), abs(part.STUD_Z_REAR))
        - spec.PRINTED_LINEAR_BAND_MM[3]
        - spec.SOCKET_PATTERN_REFINEMENT_ZONE
    )
    assert part._POCKET_END == pytest.approx(part.BAR_POCKET_Z + 2.0 * cast)
    station = part._POCKET_STATION - part._POCKET_END
    assert set(pocket) == {"hanger clearance hole", "dowel ream", "dowel knockout"}
    assert pocket["hanger clearance hole"] == pytest.approx(
        station
        - clearance_r
        - per_mm * (spec.HANGER_GRIP + spec.HANGER_GRIP_TOL - (part.FLANGE - cast))
    )
    assert pocket["dowel ream"] == pytest.approx(station - off - ream_r - drift)
    assert pocket["dowel knockout"] == pytest.approx(
        station - off - spec.HANGER_KNOCKOUT_DIA_MAX / 2.0
        - part.HANGER_KNOCKOUT_SHIFT_AT_TOP
    )
    assert pocket["hanger clearance hole"] == pytest.approx(16.029577189775253)
    assert pocket["dowel ream"] == pytest.approx(17.508659, abs=5e-6)
    assert pocket["dowel knockout"] == pytest.approx(18.061109, abs=5e-6)


def test_washer_support_on_the_faced_top_charges_all_printed_limits() -> None:
    """The washers bear on the faced top itself (user ruling 2026-10-14: no
    spotfaces): each print-worst washer stays inside the crossbar's top break
    and clear of the outer rail ends, and keeps a full bearing annulus."""
    per_mm = spec.DRILL_DRIFT_PER_MM
    assert part.HANGER_DRIFT_AT_TOP == pytest.approx(
        per_mm * (spec.HANGER_GRIP + spec.HANGER_GRIP_TOL)
    )
    assert part.HANGER_DRIFT_AT_TOP == pytest.approx(0.19177922892285743)
    # Owner ruling 2026-11-08 (Pedro), #2144 item 11.3 (scheme S1): one
    # dowel hangs each knife mount.  X .005 (the ream's .XXX) + .0025 (the
    # tap's ⌖Ø.005|A|B|C▷ radius, owner ruling 2026-11-10 (Pedro), #2334)
    # + slip/2 + t/2 (B's datum simulator off its
    # hole's centre at the pin root, ⊥Ø.001|A; codjiflo round 5); Z the same
    # plus the tap's shift as the gauge bar turns the block about its dowel:
    # the bar line runs through both bores, each off its station across the
    # line by the #10 hole's ⌖.010|D centring (owner ruling 2026-11-06), the
    # ream's .XXX, B's slip/2 and simulator and the bore's ⌖Ø.008 radius, at
    # opposite limits over the stations' spacing, the tap .300 from B.
    import sm_knife_mount_spec as knife_mount
    import sm_vn_knife_mount_dowel_spec as dowel

    assert (
        knife_mount.STUD_TAP_POSITION_TOL,
        knife_mount.DOWEL_HOLE_PERPENDICULARITY_TOL,
        knife_mount.KNIFE_BORE_POSITION_TOL,
    ) == pytest.approx((0.127, 0.0254, 0.2032))
    slip = dowel.SLIP_CLEARANCE_MAX
    assert slip == pytest.approx(0.18796)  # .0074, the #30 drill (fit audit OQ19)
    off = spec.HANGER_PIN_X_TOL
    tap = knife_mount.STUD_TAP_POSITION_TOL / 2.0
    perp = knife_mount.DOWEL_HOLE_PERPENDICULARITY_TOL  # B's round hole
    block = off + tap + slip / 2.0 + perp / 2.0
    line = (
        spec.HANGER_CROSSBAR_CENTER_TOL
        + off
        + slip / 2.0
        + perp / 2.0
        + knife_mount.KNIFE_BORE_POSITION_TOL / 2.0
    )
    # The bar line's turn plus the bar's own play in each bore (owner review
    # of #2334): its maximum diametral clearance over the shortest bore, the
    # gauge bar's .0041 (owner ruling 2026-11-20 (Pedro), #2499).
    play = math.atan(
        (2.0 * knife_mount.BORE_R_MAX - knife_mount.KNIFE_GAUGE_BAR_DIA_MIN)
        / (knife_mount.SUPPORT_Z_THICK - knife_mount.BLOCK_SIZE_TOL)
    )
    assert math.degrees(play) == pytest.approx(0.43501515207, abs=1e-9)
    yaw_shift = spec.HANGER_PIN_X * math.tan(
        math.atan(2.0 * line / (spec.STUD_Z_REAR - spec.STUD_Z_FRONT)) + play
    )
    assert part.HANGER_BAR_YAW_SHIFT == pytest.approx(yaw_shift)
    assert yaw_shift == pytest.approx(0.09690, abs=5e-5)
    assert part.HANGER_SEAT_BOLT_MISMATCH == pytest.approx(
        math.hypot(block, block + yaw_shift)
    )
    assert part.HANGER_SEAT_BOLT_MISMATCH == pytest.approx(0.4935713855058345)
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
    assert part.HANGER_WASHER_OFFSET_MAX == pytest.approx(1.5895906144286922)
    reach = spec.HANGER_WASHER.OD_MAX / 2.0 + part.HANGER_WASHER_OFFSET_MAX
    # Inside the top break's printed worst leg at the narrowest printed bar
    # half width, centred on D.
    band = spec.PRINTED_LINEAR_BAND_MM
    assert part.HANGER_WASHER_BAR_TOP_MARGIN == pytest.approx(
        (part.BAR_X1 - part.BAR_X0 - spec.AS_CAST_BAND) / 2.0
        - spec.HANGER_CROSSBAR_CENTER_TOL
        - part.EDGE_BREAK_PRINTED_MAX
        - reach
    )
    assert part.HANGER_WASHER_BAR_TOP_MARGIN == pytest.approx(2.156909385571307)
    # Clear of the outer front/rear rail ends: each washer's Z reach is its
    # station band plus the print-worst reach; the rail's outer face is the
    # narrowest printed half flange past its socket axis. The stations stand
    # from the rear sockets' axis (#2628 (d)), so the front end, measured
    # from the other socket row, also spends the pattern's Ø.010 and binds.
    places = spec.DRAWING_REFERENCE_PRECISION
    half_flange = (part.RAIL_W_FR - spec.AS_CAST_BAND) / 2.0 - spec.AS_CAST_BAND / 2.0
    z_reach = band[places["front hanger z from lower sockets"]] + reach
    front_end_wall = (
        part.STUD_Z_FRONT - part.FRONT_COLUMN_Z + half_flange
        - part.SOCKET_PATTERN_REFINEMENT_ZONE - z_reach
    )
    rear_end_wall = part.REAR_COLUMN_Z - part.STUD_Z_REAR + half_flange - z_reach
    assert front_end_wall < rear_end_wall
    assert part.HANGER_WASHER_OUTER_END_WALL == pytest.approx(front_end_wall)
    assert part.HANGER_WASHER_OUTER_END_WALL == pytest.approx(31.46849716599784)
    assert part.HANGER_WASHER_BEARING_MIN == pytest.approx(
        spec.HANGER_WASHER_CONCENTRIC_ANNULUS_MIN - part.HANGER_WASHER_OFFSET_MAX
    )
    assert part.HANGER_WASHER_BEARING_MIN == pytest.approx(1.471109385571308)
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
    # failed (FeatureCut3 "Type mismatch"): the two ream circles stand apart.
    r = spec.HANGER_PIN_HOLE_DIA / 2.0
    assert part.HANGER_PIN_CONTOURS == tuple(
        ((part.PIN_HOLE_X, z), (part.PIN_HOLE_X, z), r)
        for z in (part.STUD_Z_FRONT, part.STUD_Z_REAR)
    )
    assert part.swept_contours_disjoint(part.HANGER_PIN_CONTOURS)
    # The checker separates by the swept radii, so touching is a failure.
    assert not part.swept_contours_disjoint((((0, 0), (1, 0), 1.0), ((1, 2), (3, 2), 1.0)))
    assert part.swept_contours_disjoint((((0, 0), (1, 0), 1.0), ((1, 2.001), (3, 2.001), 1.0)))


def test_reams_are_no_datums_and_carry_no_position_frame() -> None:
    # Owner ruling 2026-11-08 (Pedro), #2144 item 11.3: the -X reams and
    # their position frames to the +X reams (datums B front, C rear) are
    # deleted, so the +X reams are no datums and the underside locator
    # carries no frame or tag; each ream is located by F-F's .XXX station
    # from its screw axis and held square by F-F's 2X ⊥ frame.  Owner ruling
    # 2026-11-06's per-pair 2X ⌖Ø.004|A|D, SEP REQT goes with them.
    assert "knife-hanger press ream position" not in spec.GEOMETRIC_TOLERANCES_IN
    for retired in (
        "HANGER_DATUM_SYMBOL_XY",
        "HANGER_DATUM_PICK_ZOOM_HALF",
        "hanger_ream_rim",
        "hanger_ream_frame_knee",
        "HANGER_REAM_FRAME_XY",
        "HANGER_REAM_FRAME_TEXT_BOX",
        "HANGER_REAM_FRAME_OUTLINE",
        "HANGER_REAM_FRAME_SHOULDER",
        "HANGER_REAM_FRAME_QUANTITY",
        "HANGER_PIN_SPAN_TEXT_XY",
        "HANGER_PIN_SPAN_OFFSET_XY",
        "HANGER_PIN_SPAN_ABOVE",
    ):
        assert not hasattr(drawing, retired), retired
    x, y = drawing.HANGER_KNOCKOUT_CALLOUT_XY
    assert 0.013 < x < TITLE_BLOCK[0] and 0.125 < y < 0.270


def test_overall_plan_extremes_pick_the_scanned_edges_as_entities() -> None:
    # Farm a03283b49: a sheet-point pick on the boss barrel's R22.5 plan
    # outline resolved to the top edge break's inner circle (then the C2's
    # R20.5, width 435 for 439).  Both overall dimensions select scanned
    # edges: the barrels' R.885 circles on the faced top's plane, where the
    # taken-out draft holds the Ø1.77 (owner ruling B1, #2333), and for the
    # width's east end the set-screw boss's face, .065 past the east
    # barrels' tangent (owner ruling B4).


    # The faced top holds each barrel's largest circle and the boss face's
    # farthest edge, so those are the plan's extremes.
    assert drawing.PLAN_HALF_X == part.COLUMN_X + part.BOSS_DIA / 2.0
    assert part._boss_radius(part.HALF_H) == pytest.approx(part.BOSS_DIA / 2.0)
    for y in (part.HALF_H + part.BOSS_ABOVE, -part.HALF_H - part.BOSS_BELOW):
        assert part._boss_radius(y) < part.BOSS_DIA / 2.0
    assert part.SET_BOSS_FACE_X < -drawing.PLAN_HALF_X
    assert part._casting_occupies(part.SET_BOSS_FACE_X + 1e-6, part.HALF_H, part.GOOSENECK_Z)
    assert not part._casting_occupies(part.SET_BOSS_FACE_X - 1e-6, part.HALF_H, part.GOOSENECK_Z)
    below = (part.HALF_H - 5.0, part.GOOSENECK_Z)  # receded 5 x tan 2° = .175 mm
    assert not part._casting_occupies(part.SET_BOSS_FACE_X + 0.1, *below)
    assert part._casting_occupies(part.SET_BOSS_FACE_X + 0.25, *below)
    places = spec.DRAWING_REFERENCE_PRECISION
    overall_width = (drawing.PLAN_HALF_X - part.SET_BOSS_FACE_X) / 25.4
    assert f"{overall_width:.{places['overall casting width']}f}" == "17.35"
    overall_depth = 2.0 * drawing.PLAN_HALF_Z / 25.4
    assert f"{overall_depth:.{places['overall casting depth']}f}" == "10.59"


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
    ream size, the knockout callout and their leaders keep clear of, and
    F-F's cutting-line height (the datum tags and -X ream frames are gone,
    owner ruling 2026-11-08 (Pedro), #2144 item 11.3)."""
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
    return lines, boxes, cut_y


def _rim_toward(centre, target, radius):
    """The point on a circle's rim facing ``target`` (sheet m)."""
    dx, dy = target[0] - centre[0], target[1] - centre[1]
    length = math.hypot(dx, dy)
    return (centre[0] + radius * dx / length, centre[1] + radius * dy / length)


def _locator_circles():
    """The four corner bosses' and both reams' printed circles (x, y, r) in
    the underside locator, sheet m."""
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
    for station, station_z in (("front", part.STUD_Z_FRONT), ("rear", part.STUD_Z_REAR)):
        circles[f"ream {station}"] = (
            centre[0] + part.PIN_HOLE_X * m_per_mm,
            centre[1] + station_z * m_per_mm,
            drawing.HANGER_PIN_HOLE_DIA / 2.0 * m_per_mm,
        )
    return circles


# The crossbar sketch's two land-end dimensions (build_fr_top_frame's bar
# polygon), each from a bar side's front-gusset vertex to the front land's
# end on that side: model x of (crossbar face, land end).
_LAND_END_DIMENSIONS = {
    "LandEnd": (part.BAR_X0, part.LAND_X0),
    "LandEndW": (part.BAR_X1, part.LAND_X1),
}


def _land_end_kept():
    """The land-end dimension VIEW L imports: its name and its model x pair."""
    (name,) = set(drawing.UNDERSIDE_KEEP) & set(_LAND_END_DIMENSIONS)
    return name, _LAND_END_DIMENSIONS[name]


def _land_end_ink():
    """The imported land-end dimension's ink (sheet m), as farm run
    20261111T023438415Z printed the model's own: extension lines from the
    bar side's front-gusset vertex and the front land's end, each starting
    1 mm short of its vertex (y 173.60 and 167.59), down to 1 mm past the
    dimension line; that line between them, arrows inside; the value row
    (16.8 mm wide, its glyphs to 4.5 mm over the point) centred on
    LAND_TEXT_OFFSET_XY with its count row and its underline 5.56 mm under
    it; and the jog from the line's middle to the underline's near end."""
    from _layout_geometry import Box, Segment

    centre, m_per_mm = drawing.HUB_BOTTOM_CENTER, drawing._HUB_BOTTOM_M_PER_MM
    name, (bar_face, land_end) = _land_end_kept()
    bar_x = centre[0] + bar_face * m_per_mm
    land_x = centre[0] + land_end * m_per_mm
    bar_top = centre[1] - (part.LAND_FACE_Z0 - part.GUSSET) * m_per_mm - 0.001
    land_top = centre[1] - part.LAND_FACE_Z0 * m_per_mm - 0.001
    line_y = drawing.UNDERSIDE_KEEP[name][1]
    tx, ty = drawing.LAND_TEXT_OFFSET_XY
    text = Box(tx - 0.0084, ty - 0.00556, tx + 0.0084, ty + 0.0045)
    lines = {
        "land-end bar-face extension": Segment(bar_x, line_y - 0.001, bar_x, bar_top),
        "land-end land extension": Segment(land_x, line_y - 0.001, land_x, land_top),
        "land-end line": Segment(bar_x, line_y, land_x, line_y),
        "land-end jog": Segment((bar_x + land_x) / 2.0, line_y, text.xmin, text.ymin),
    }
    return lines, text


def _knockout_callout_box():
    """The knockouts' callout block, sheet m, as farm run
    20261027T030041319Z printed it about its point: underline to cap line,
    left text edge to the underline's right end (where the leader leaves)."""
    from _layout_geometry import Box

    kx, ky = drawing.HANGER_KNOCKOUT_CALLOUT_XY
    x0, y0, x1, y1 = drawing.HANGER_KNOCKOUT_CALLOUT_INK
    return Box(kx + x0, ky + y0, kx + x1, ky + y1)


def _underside_title_box():
    """The locator's one-row "VIEW L" label, sheet m, below its top-left
    point: farm run 20261106T222724559Z printed that row at x 20.15..34.64,
    y 118.49..121.89 mm for the point (20, 122); 1 mm and 0.6 mm spare."""
    from _layout_geometry import Box

    nx, ny = drawing.HUB_BOTTOM_TITLE_XY
    return Box(nx, ny - 0.0045, nx + 0.0160, ny)


def test_knockout_callout_leader_passes_left_of_the_land_dimension() -> None:
    # The knockouts' native callout parks under the front rail where the
    # old slot width's block stood (machinist review of 11783475 and codex
    # review of fe1a7611: that leader must clear the 73.0's line).  Farm run
    # 20261027T030041319Z: the underline began 0.34 mm inside the inner
    # border (machinist review, rule 13), so the block stands with visible
    # air inside it; the leader leaves the underline's right end for the
    # front ream's knockout floor circle (the one +X ream per station since
    # owner ruling 2026-11-08 (Pedro), #2144 item 11.3).
    from _layout_geometry import Segment, segment_box_distance, segment_circle_distance

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
        f"2X \u00d8{spec.HANGER_KNOCKOUT_DIA:.{spec.HANGER_KNOCKOUT_DIA_PLACES}f} THRU ALL",
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
    # The locator's one-row label (_underside_title_box).
    note = _underside_title_box()
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
        centre[0] + part.PIN_HOLE_X * m_per_mm,
        centre[1] + part.STUD_Z_FRONT * m_per_mm,
    )
    leader = Segment(block.xmax, block.ymin, *floor)
    assert segment_box_distance(leader, note) >= ink
    for name, circle in circles.items():
        if name != "ream front":  # the ream it lands in
            assert segment_circle_distance(leader, circle) >= ink, name
    # It crosses no line of the land-end dimension: it lands left of them
    # all, inside the front ream, whose rim stands 1.1 mm off the bar-face
    # extension line.
    ream_r = drawing.HANGER_PIN_HOLE_DIA / 2.0 * m_per_mm
    rim_gap = land_lines["land-end bar-face extension"].x0 - floor[0] - ream_r
    for name, line in land_lines.items():
        assert _segment_gap(leader, line) >= rim_gap, name
    assert floor[0] < min(min(line.x0, line.x1) for line in land_lines.values())
    # The block stands left of the crossbar's outer face.
    assert block.xmax < centre[0] + part.BAR_X0 * m_per_mm - ink


# Farm run 20261027T030041319Z: the F-F station block's rows, centred on
# its offset point's x, baselines 5.56 mm apart from one row above the
# point, 3.5 mm cap height: the value's printed width, then the count row
# (drawing-guidelines.md rule 7: value and count only), "2X" estimated at
# 2.6 mm a glyph.
_STATION_ROW_WIDTHS = (0.0116, 2 * 0.0026)


def _station_rows(offset_xy):
    """The F-F station block's printed rows (x0, y0, x1, y1), sheet m."""
    ox, oy = offset_xy
    rows = drawing.PIN_STATION_CALLOUT.splitlines()
    assert len(rows) + 1 == len(_STATION_ROW_WIDTHS)
    return {
        name: (ox - width / 2.0, base, ox + width / 2.0, base + 0.0035)
        for index, (name, width) in enumerate(zip(("value", *rows), _STATION_ROW_WIDTHS))
        for base in (oy + 0.00556 * (1 - index),)
    }


def test_pocket_length_dimension_stands_outside_the_plan() -> None:
    # The 138.0 line, its extension lines and its text stay out of the plan
    # silhouette and detail J's fence; the text box is the three-row block
    # farm c75ac06 printed (17.5 mm tall, widest row 33.9 mm by the 40d9d030e
    # render's glyphs), which the two-row value + "2X POCKET" fits in.
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
    from fr_frame_cross_screw import FAR_WALL_ENGAGEMENT_FLOOR_MM

    engagement = part.TOP_CROSS_SCREW_FAR_WALL_MIN_ENGAGEMENT
    # Rule 18 (thread engagement): the printed bands, the shortest stock
    # screw and its tip only shorten the far-wall engagement, and the
    # shortest still holds 1.5D.
    assert (
        FAR_WALL_ENGAGEMENT_FLOOR_MM <= engagement < assembly.TOP_FAR_CASTING_ENGAGEMENT
    )
    assert not hasattr(drawing, "CROSS_SCREW_FAR_WALL_MIN_ENGAGEMENT")


def test_near_wall_clearance_opens_the_near_wall_from_the_counterbore_floor() -> None:
    # Owner ruling 2026-11-05: the near casting wall is #10 close clearance
    # drilled into the socket, so the 10-32 is threaded in the far wall only.
    spec = part.SIDE_CLEARANCE_SPEC
    assert (spec.kind, spec.size, spec.fit, spec.end) == (
        "clearance",
        "#10",
        "close",
        "blind",
    )
    # Owner ruling 2026-11-10 (#2333, D5): the floor stands .62 off the
    # socket axis; the drill stops in the socket.
    assert spec.depth_mm == pytest.approx(TOP_SCREW_SEAT_Z - abs(part.FRONT_COLUMN_Z))
    assert spec.depth_mm == pytest.approx(15.748)
    # Print-worst it stays inside the floor and under the cap recess.
    assert part.SIDE_CLEARANCE_FLOOR_LAND > 0.0
    assert part.SIDE_CLEARANCE_CAP_LIGAMENT >= 2.032


def test_cross_tap_callout_states_far_wall_only() -> None:
    assert drawing.CROSS_TAP_MATE_LINE == (
        "FOR MHA-FR-VN-53, FAR WALL ONLY,\nDEPTHS FROM COUNTERBORE FLOOR"
    )
    assert "PHASE" not in drawing.CROSS_TAP_MATE_LINE
    assert not hasattr(drawing, "CROSS_CLEARANCE_TOTAL_TEXT")
    assert drawing.CROSS_TAP_FEATURES == ("SideTapsFront", "SideTapsRear")


def test_cross_clearance_callout_drills_to_the_socket() -> None:
    native = {
        5: "",
        6: "",
        7: "<NUM_INST>X <MOD-DIAM><hw-diam> <HOLE-DEPTH> <hw-depth>",
        8: "",
    }
    updated = drawing._cross_clearance_callout_definitions(native)
    assert updated[7] == "4X <MOD-DIAM><hw-diam> \nDRILL TO SOCKET"
    assert all(updated[part_no] == "" for part_no in (5, 6, 8))
    with pytest.raises(RuntimeError, match="no single count and blind depth"):
        drawing._cross_clearance_callout_definitions(
            {**native, 7: "<MOD-DIAM><hw-diam> THRU"}
        )
    assert drawing.CROSS_CLEARANCE_PRECISION == {"hw-diam": 3}


def _segments_apart(a, b) -> bool:
    """True when two segments neither cross nor touch."""

    def side(p, q, r) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    a0, a1, b0, b1 = (a.x0, a.y0), (a.x1, a.y1), (b.x0, b.y0), (b.x1, b.y1)
    return side(a0, a1, b0) * side(a0, a1, b1) > 0 or side(b0, b1, a0) * side(b0, b1, a1) > 0


def test_finished_grip_takes_the_title_block_band() -> None:
    """Owner ruling 2026-10-18: the 1.437 grip takes the title block's .XXX
    band; MHA-SM-VN-52 is cut to the measured grip at MHA-SM-00, so the grip
    no longer sets thread engagement."""
    assert (spec.HANGER_GRIP, spec.HANGER_GRIP_TOL) == pytest.approx((36.4998, 0.127))


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
        "caption": drawing.HANGER_SECTION_CAPTION_XY,
        "depth offset": drawing.HANGER_PIN_DEPTH_OFFSET_XY,
        **drawing.HANGER_SECTION_KEEP,
    }
    for name, (x, y) in points.items():
        assert 0.013 < x < TITLE_BLOCK[0] and 0.013 < y < 0.150, name
    # The station reads above the profile, its line between the hanger axis
    # and the ream axis clear of its own printed rows (_station_rows), which
    # stand off the title block, the knockouts' callout and the bottom
    # view's label.  The -X ream's BASIC span and owner ruling 2026-11-06's
    # BASIC .300 either side of D are gone (owner ruling 2026-11-08 (Pedro),
    # #2144 item 11.3).
    ink = drawing.INK_CLEARANCE
    top = drawing._hanger_section_xy(part.HANGER_X, part.HALF_H)[1]
    station_y = drawing.PIN_STATION_TEXT_XY[1]
    assert top < station_y
    station_x = [
        drawing._hanger_section_xy(x, 0.0)[0] for x in (part.HANGER_X, part.PIN_HOLE_X)
    ]
    station_line = Segment(station_x[0], station_y, station_x[1], station_y)
    knockout = _knockout_callout_box()
    title = _underside_title_box()
    for name, row in _station_rows(drawing.PIN_STATION_OFFSET_XY).items():
        assert _box_box_gap(row, TITLE_BLOCK) >= ink, name
        assert row[1] >= top + ink, name
        assert segment_box_distance(station_line, Box(*row)) >= ink, name
        assert _box_box_gap(
            row, (knockout.xmin, knockout.ymin, knockout.xmax, knockout.ymax)
        ) >= 0.004, name
        assert _box_box_gap(
            row, (title.xmin, title.ymin, title.xmax, title.ymax)
        ) >= 0.004, name


def test_hanger_station_line_ends_inside_short_of_the_station_rows() -> None:
    """Farm run 20261027T195317391Z (machinist review r1): with SolidWorks'
    outside arrows, the station's right tail ran 6.35 mm past the +X ream's
    axis into the foot of then-"MATCHES".  Its arrows now stand inside, so
    the line ends on the ream's axis, an ink clearance and more short of
    every station row.  The -X ream span that shared this rule is gone
    (owner ruling 2026-11-08 (Pedro), #2144 item 11.3), and the block is
    its value and count only (rule 7)."""

    ink = drawing.INK_CLEARANCE
    tail = 0.00635
    axis = drawing._hanger_section_xy(part.PIN_HOLE_X, 0.0)[0]
    y = drawing.PIN_STATION_TEXT_XY[1]
    struck = []
    for row_name, (x0, y0, _x1, y1) in _station_rows(drawing.PIN_STATION_OFFSET_XY).items():
        if not y0 - ink < y < y1 + ink:
            continue
        assert x0 - axis >= ink, row_name
        if x0 - (axis + tail) < ink:
            struck.append(row_name)
    assert struck == []


def test_boss_diameter_reads_apart_from_the_f_f_stacks() -> None:
    """Machinist review at rubric 848e03f (rule 15, 2 of 3 runs): at
    (0.215, 0.100) the Ø1.18's first row shared a line with F-F's "1.437"
    and read as one callout.  The Ø1.18 rows (value 3 mm over, first callout
    row 3 mm under the point, ~2.6 mm a glyph) stand a row-and-more over the
    grip's value row, left of detail J's circle and right of F-F's station
    block.  Owner ruling D1 (#2333) takes the barrel's draft out below the
    underside, so a second row, one 5.56 mm pitch lower, says where the
    Ø1.18 holds (farm run 20261111T023438415Z: rows from 126.8, 121.2 and
    115.6 about y 124.0), and the first names it the hub barrel, as sheet
    7's draft callout does: a drafted barrel is no cylinder (Codjiflo round
    2 of 518e3d01e1)."""
    x, y = drawing.HUB_BOSS_DIA_TEXT_XY
    rows = drawing.HUB_BOTTOM_CALLOUTS["HubDia"].splitlines()
    assert rows == ["HUB BARREL", "AT UNDERSIDE"]
    assert "HUB BARRELS" in drawing.DATUM_FRONT_CALLOUTS["BossesUpperDraft"]
    half_w = max(map(len, rows)) * 0.0026 / 2.0
    box = (x - half_w, y - 0.006 - (len(rows) - 1) * _ROW_PITCH, x + half_w, y + 0.006)
    grip_value_y = drawing.HANGER_GRIP_OFFSET_XY[1] + 0.00278
    assert box[1] - grip_value_y >= 0.015
    cx, cy = drawing.HUB_DETAIL_CENTER
    corner = (box[2], box[3])
    assert math.dist(corner, (cx, cy)) - 0.076 >= 0.005
    station_right = max(
        row[2] for row in _station_rows(drawing.PIN_STATION_OFFSET_XY).values()
    )
    assert box[0] - station_right >= 0.010


def test_counterbore_callout_drops_to_its_near_rim_off_the_tap_leader() -> None:
    """Machinist review at rubric 848e03f (rule 14, 2 of 3 runs): the
    counterbore's diametric leader ran from (0.045, 0.256) across the view
    and on through the hole, crossing the cross tap's leader.  Its text now
    stands up-left of the right boss and left of A-A's upper arrow, and the
    dimension keeps one arrow on the near rim."""

    x, y = drawing.DETAIL_FRONT_KEEP["CB1Dia"]
    assert (x, y) == (0.205, 0.256)
    # "4X ⌴ Ø.35 ↧ (.235)" measured 46.8 mm on sheet 4 (round 8 render).
    assert x + 0.0234 <= 0.2438 - 0.010


def test_pad_width_leaves_the_plan_for_detail_j() -> None:
    """The plan's only import is the Ø17.00 bore: under the top flange that
    hidden-lines-removed plan shows no pad (farm run 20261027T195317391Z,
    machinist review r2+r3), and the 28.0's line there ran through the
    Ø17.00 leader (run 20261027T190435153Z, rule 14), so it cannot cross it
    again.  DETAIL J, where the pad's faces are drawn, carries it."""

    assert drawing.HUB_TOP_KEEP == {"GnDia": (0.040, 0.185)}
    assert set(drawing.HUB_TOP_CALLOUTS) == {"GnDia"}
    assert drawing.HUB_BOTTOM_KEEP["RibWidth"] == drawing.RIB_WIDTH_LINE_XY
    assert drawing.HUB_BOTTOM_KEEP["HubDia"] == drawing.HUB_BOSS_DIA_TEXT_XY
    assert set(drawing.HUB_BOTTOM_CALLOUTS) == set(drawing.HUB_BOTTOM_KEEP)
    # Owner ruling D1 (#2333): the hub barrel's draft is taken out from the
    # faced underside, so its Ø1.18 says where it holds: 1 mm under it the
    # barrel has narrowed 1 x tan 2° = .035 mm a side.
    assert drawing.HUB_BOTTOM_CALLOUTS["HubDia"] == "HUB BARREL\nAT UNDERSIDE"
    assert part.HUB_BOSS_DIA / 25.4 == pytest.approx(1.18, abs=5e-3)
    rim = (part.GOOSENECK_X + part.HUB_BOSS_DIA / 2.0, -part.HALF_H - 1.0, part.GOOSENECK_Z)
    assert part._casting_occupies(rim[0] - 0.05, *rim[1:])
    assert not part._casting_occupies(rim[0] - 0.02, *rim[1:])


def test_set_screw_boss_face_prints_on_detail_j_where_it_holds() -> None:
    """Owner rulings B4 and D1 (#2333): the full-height boss's cast face
    stands .95 ±.03 from the gooseneck bore axis on the faced top's plane and
    leans in under it, so the print says where the .95 holds.  It is the
    model's own SetBossFace, a Top-plane sketch dimension a section along
    the tap axis does not import (farm run 20261111T015941119Z), so DETAIL J
    carries it: its line from the bore axis to the face's top edge, through
    the boss, and its rows parked outside the detail's fence (farm run
    20261111T023438415Z: at x 212 "AT FACED TOP" touched the fence)."""
    assert spec.HUB_SET_BOSS_FROM_AXIS / 25.4 == pytest.approx(0.95)
    assert "SetBossFace" in spec.DRAWING_DIMENSIONS["SetBossProfile"]
    assert "SetBossFace" in spec.AS_CAST_DIMENSIONS["SetBossProfile"]
    assert spec.DRAWING_PRECISION_BY_NAME["SetBossFace"] == 2
    assert [
        name
        for name, keep in vars(drawing).items()
        if name.endswith("_KEEP") and isinstance(keep, dict) and "SetBossFace" in keep
    ] == ["HUB_BOTTOM_KEEP"]
    assert drawing.HUB_BOTTOM_KEEP["SetBossFace"] == drawing.SET_BOSS_FACE_LINE_XY
    assert drawing.HUB_BOTTOM_CALLOUTS["SetBossFace"] == "AT FACED TOP"
    ink = drawing.INK_CLEARANCE
    s = drawing.HUB_DETAIL_SCALE[0] / drawing.HUB_DETAIL_SCALE[1] / 1000.0
    cx, cy = drawing.HUB_DETAIL_CENTER
    fence = (part.HUB_GUSSET_HALF_OUT + part.HUB_BOSS_DROP) * s
    # From below the east face stands left of the bore axis the detail
    # centres on; that run printed its line's ends at x 251.74 and 300.00.
    face_x = cx - spec.HUB_SET_BOSS_FROM_AXIS * s
    assert (face_x, cx) == pytest.approx((0.25174, 0.300))
    line_x, line_y = drawing.SET_BOSS_FACE_LINE_XY
    assert face_x < line_x < cx
    assert abs(line_y - cy) <= spec.HUB_SET_BOSS_W / 2.0 * s - ink
    assert math.dist((face_x, line_y), (cx, cy)) <= fence - ink
    # The value row stands on the offset point with the callout row one
    # 5.56 mm pitch under it, 32.3 mm wide (that run's native rows).
    tx, ty = drawing.SET_BOSS_FACE_TEXT_XY
    half_w = 0.0323069 / 2.0
    block = (tx - half_w, ty - 0.00556, tx + half_w, ty + 0.0045)
    nearest = (min(max(cx, block[0]), block[2]), min(max(cy, block[1]), block[3]))
    assert math.dist(nearest, (cx, cy)) - fence >= ink
    locator_right = drawing.HUB_BOTTOM_CENTER[0] + (
        drawing.PLAN_HALF_X - part.SET_BOSS_FACE_X
    ) / 2.0 * drawing._HUB_BOTTOM_M_PER_MM
    assert block[0] - locator_right >= ink
    frame = drawing.SHEET_FRAME
    assert frame[1] + ink <= block[1] and block[3] <= frame[3] - ink


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
    assert face == pytest.approx(0.33429)
    lx, ly = drawing.RIB_WIDTH_LINE_XY
    ox, oy = drawing.RIB_WIDTH_TEXT_XY
    assert ly == pytest.approx(cy)
    rows = drawing.HUB_BOTTOM_CALLOUTS["RibWidth"].splitlines()
    # rule 10: the drawn bore centrelines show the pad's symmetry, so the
    # callout says no "CENTRED ON".
    assert rows == ["FULL-HEIGHT", "PAD WIDTH"]
    widths = {"28.0": 0.0091, "FULL-HEIGHT": 0.0272, "PAD WIDTH": 9 * 0.00285}
    bases = (oy + 0.00514, oy - 0.00042, oy - 0.00598)
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


def test_faced_underside_is_datum_a_and_every_ream_is_square_to_it() -> None:
    """Owner rulings 2026-10-27 (#2016) option A and 2026-11-06: the
    crossbar's dowel reams are perpendicular, Ø.001, to the faced underside
    the knife mounts seat on.  The underside is datum A (D is the crossbar
    median plane), tagged on its edge in F-F, and one native "2X" ⊥ Ø.001 | A
    frame covers both reams, one per station since owner ruling 2026-11-08
    (Pedro), #2144 item 11.3 (the -X reams, their position frames and
    datums B and C are gone); its leader enters the ream's mouth from below
    and lands on its wall."""
    assert (
        spec.GEOMETRIC_TOLERANCES_IN["knife-hanger press ream perpendicularity"]
        == ".001"
    )
    assert spec.HANGER_PRESS_HOLE_PERPENDICULARITY_TOL == pytest.approx(0.0254)
    assert "knife-hanger press ream position" not in spec.GEOMETRIC_TOLERANCES_IN
    # A is free among this part's datums.
    assert drawing.HANGER_FLOOR_DATUM == "A"
    assert not hasattr(drawing, "HANGER_DATUM_SYMBOL_XY")
    assert drawing.HANGER_PERP_FRAME_QUANTITY == "2X"


def test_plus_x_station_is_xxx_from_the_screw_axis() -> None:
    # Each station's one ream is an ordinary .XXX 7.632 from its own screw
    # axis, its Z the screw axis's own; no frame or BASIC locates it (owner
    # ruling 2026-11-08 (Pedro), #2144 item 11.3: the -X ream, its BASIC
    # span and its position frame, and owner ruling 2026-11-06's BASIC .300
    # either side of D, are deleted).  The bolt-float stack charges that
    # band; no note restates it.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    section = source[source.index("def _hanger_section(") : source.index("def _hub_underside_detail(")]
    assert "p0=(HANGER_X, -HALF_H-2.0, z), p1=(PIN_HOLE_X, -HALF_H-2.0, z)" in section
    assert "PIN_HOLE_NEG_X" not in section
    assert "entities=(axes[0], axes[1])" in section
    assert "axes[2]" not in section
    assert section.count("suffix=PIN_STATION_CALLOUT,") == 1
    assert section.count("set_basic_dimension(") == 0
    assert "SetText(1, " not in section
    assert 'location="above"' not in section
    # rule 7: the location carries its value and count only; F-F's plane
    # holds the screw axis and the ream (their implied-zero SAME Z), and the
    # ream's own size callout names its mate.
    assert drawing.PIN_STATION_CALLOUT == "2X"
    assert 'label="dowel hole from hanger axis"' in section
    assert (
        spec.DRAWING_REFERENCE_PRECISION["dowel hole from hanger axis"]
        == spec.HANGER_PIN_X_PLACES
    )
    import sm_knife_mount_spec as knife_mount

    assert spec.HANGER_PIN_X == knife_mount.PIN_HOLE_X


def test_boss_and_socket_diameters_take_one_near_side_arrow() -> None:
    # Machinist review r3 (sheet 3): as full diameters through the shared
    # axis the socket's match-fit leader crossed the Ø45.0 BOSS leader at
    # the socket centre, and the Ø45.0 grazed the 28.0's upper arrow.  Each
    # now reads off one arrow on its nearest rim.
    assert set(drawing.DETAIL_TOP_KEEP) == {"C0Dia", "B0Dia"}
    assert drawing.DETAIL_TOP_KEEP["C0Dia"] == (0.035, 0.236)
    # The socket's three rows stand over the boss's callout, left of the
    # rail (#2628 (d)).
    assert drawing.DETAIL_TOP_KEEP["B0Dia"][1] - drawing.DETAIL_TOP_KEEP["C0Dia"][1] >= 0.015


def test_cap_recess_bands_preserve_the_counterbore_ligament() -> None:
    # Owner ruling 2026-11-06: the diameter takes the title block's .XXX
    # ±.005; the ligament is proved at its largest printed recess, from the
    # counterbore floor .62 off the socket axis (owner ruling D5).
    assert not hasattr(part, "CAP_RECESS_DIAMETER_BAND")
    assert part.CAP_RECESS_DIAMETER_MAX == pytest.approx(
        part.CAP_RECESS_DIAMETER + spec.PRINTED_LINEAR_BAND_MM[3]
    )
    assert part.CAP_RECESS_DEPTH_BAND == pytest.approx((0.254, 0.0))
    assert part.COUNTERBORE_PRINTED_CAP_LIGAMENT == pytest.approx(2.2317336758672544)
    assert part.COUNTERBORE_PRINTED_CAP_LIGAMENT >= WALL_TARGET_MM


def test_ream_size_parks_above_the_plan() -> None:
    # The rear ream's size, its stacked +0.000/-0.010 band and its one
    # callout row print face-on in the underside locator.  Farm run
    # 20261027T030041319Z measured the block (the row 112.5 mm, 15.1 mm in
    # all); the leader lands on the underline's end facing the ream.  The
    # block parks over the plan, inside the sheet frame and short of detail
    # J; it and its leader keep ink clear of every locator line, box and
    # circle, and the leader, leaving the rim above F-F's cutting line,
    # does not cross it.
    from _layout_geometry import Box, Segment, segment_box_distance, segment_circle_distance

    assert len(drawing.HANGER_PIN_DIA_CALLOUT.splitlines()) == 1
    half_w = drawing.HANGER_PIN_DIA_TEXT_WIDTH / 2.0
    half_h = drawing.HANGER_PIN_DIA_TEXT_HALF_HEIGHT
    # Farm run 20261027T030041319Z: 67 mm per 25 glyphs of the callout row.
    assert 2.0 * half_w == pytest.approx(
        0.067 * len(drawing.HANGER_PIN_DIA_CALLOUT_PRINTED) / 25, abs=0.0005
    )
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
    hole_x, hole_y, hole_r = circles.pop("ream rear")
    foot = (block.xmin, block.ymin)
    leader = Segment(*_rim_toward((hole_x, hole_y), foot, hole_r), *foot)
    assert block_gap((hole_x, hole_y)) - hole_r >= ink
    for name, circle in circles.items():
        assert block_gap(circle[:2]) - circle[2] >= ink, name
        assert segment_circle_distance(leader, circle) >= ink, name
    lines, boxes, _cut_y = _underside_locator_ink()

    for name, box in boxes.items():
        assert _box_box_gap(
            (block.xmin, block.ymin, block.xmax, block.ymax),
            (box.xmin, box.ymin, box.xmax, box.ymax),
        ) >= ink, name
        assert segment_box_distance(leader, box) >= ink, name
    for name, line in lines.items():
        assert segment_box_distance(line, block) >= ink, name
        if name == "F-F cutting line":
            # It runs through the rear ream: the leader does not cross it.
            assert _segments_apart(leader, line), name
        else:
            assert _segment_gap(leader, line) >= ink, name


def test_hanger_callout_states_e_drill_thru_on_the_native_rows(monkeypatch) -> None:
    """The plain wizard's native callout keeps its variable-driven diameter,
    leads with the letter drill and reads THRU for its one extent token
    (owner ruling 2026-11-24, fit audit OQ19: 2X E DRILL Ø.250 THRU); no
    spotface row,
    method note or depth survives."""
    import ast

    assert spec.HANGER_HOLE_DRILL == "E"
    assert drawing.HANGER_HOLE_PROCESS_TEXT == "E DRILL "
    assert drawing.HANGER_HOLE_EXTENT_TEXT == "THRU"
    # The installed R2026x calloutformat.txt, [ANSI INCH] line 93:
    # HOLE-THRU=;<MOD-DIAM> <hw-diam> <hw-thru>
    native = "<MOD-DIAM> <hw-diam> <hw-thru>"
    assert drawing._hanger_hole_callout_definitions({5: native, 6: "", 7: "", 8: ""}) == {
        5: "E DRILL <MOD-DIAM> <hw-diam> THRU", 6: "", 7: "", 8: "",
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
        "<MOD-DIAM>": "\u00d8", "<hw-diam>": "6.350", "<hw-thru>": "THRU ALL",
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
        drawing, "_clear_hanger_callout_band", lambda _display: calls.append("band"),
    )
    display = Display()
    drawing._set_hanger_hole_callout(display)
    assert display.GetText(1) == "E DRILL \u00d8 6.350 THRU"
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
            and keyword.value.value == "2X E drill hanger clearance holes"
            for keyword in node.keywords
        )
    ]
    keywords = {k.arg: k.value for k in callout.keywords}
    assert "process" not in keywords
    assert isinstance(keywords["callout_xy"], ast.Name)
    assert keywords["callout_xy"].id == "HANGER_CALLOUT_XY"


def test_keeper_transfer_prefix_preserves_the_native_hole_definition() -> None:
    import _drawing_hole_callout

    native = "<hw-threaddesc>\n<hw-threaddepth>\n<hw-tapdrldia> <hw-tapdrldepth>"
    assert (
        _drawing_hole_callout.compose_hole_callout_prefix(
            drawing.TRANSFER_KEEPER_CALLOUT,
            native,
        )
        == "TRANSFER FROM MHA-CH-07\nAT ASSEMBLY;\n" + native
    )


def _table_origin_mark() -> tuple[tuple[float, float], dict[str, tuple[float, float, float, float]]]:
    """The table origin's sheet point (the F|G corner, the plan's lower
    right) and its two arrows with their labels as boxes.  The X arrow runs
    left on a line under the corner and the Y arrow up on a line right of it
    (TABLE_ORIGIN_*_ARROW's length and offset).  The labels' reach about them
    is the native mark's on farm run 20261111T023438415Z's sheet: "X" to
    6.35 mm past the X tip and that arrow's "0" to 5.3 mm right of the
    corner, both from 2.8 mm under to 1.5 mm over the X line; the Y arrow's
    "0" from 5.8 mm under the corner and "Y" to 5.1 mm past the Y tip, both
    within 1.4 mm of the Y line."""
    ox, oy = _plan(*drawing.TABLE_ORIGIN_XZ)
    (x_length, x_offset), (y_length, y_offset) = (
        drawing.TABLE_ORIGIN_X_ARROW,
        drawing.TABLE_ORIGIN_Y_ARROW,
    )
    x_line, y_line = oy - x_offset, ox + y_offset
    return (ox, oy), {
        "X arrow": (ox - x_length - 0.00635, x_line - 0.0028, ox + 0.0053, x_line + 0.0015),
        "Y arrow": (y_line - 0.0014, oy - 0.0058, y_line + 0.0014, oy + y_length + 0.0051),
    }


def test_sheet_three_tabulates_its_sockets_basic_from_the_cast_datum_corner() -> None:
    """drawing-guidelines.md rule 10: the four sockets carry a mate, so one
    tagged table locates them, a MATE column naming it; the keeper taps are
    transferred from MHA-CH-07 at assembly, so their callout places them and
    no station dimension survives on the sheet.  Owner 2026-11-07: the origin
    is a corner the shop picks up, never a hole centre.  Owner ruling D2
    (#2333): on the casting that corner is its own datum frame's F|G corner
    -- the rear barrels' datum-target tangent and the rear-west barrel's, the
    plan's lower right -- the coordinates BASIC under the sockets' position
    frames and every one positive; the hanger holes leave the table for
    datum D's frame and their .XXX stations from the front sockets' axis."""
    x0, z0 = drawing.TABLE_ORIGIN_XZ
    assert (x0, z0) == part.CAST_DATUM_ORIGIN_XZ
    holes = {(x, z): (diameter, mate) for x, z, diameter, mate in drawing.TABLE_HOLES}
    assert len(holes) == len(drawing.TABLE_HOLES) == 4
    for x in (-part.COLUMN_X, part.COLUMN_X):
        for z in (part.FRONT_COLUMN_Z, part.REAR_COLUMN_Z):
            assert holes[(x, z)] == (part.BORE_DIA, "MHA-FR-03, MHA-FR-01")
    # Counted left and up from the corner, as that farm run's native cells
    # read A1 to A4: .831 is the barrel's radius at the datum targets' height.
    printed = {
        hole: tuple(
            f"{(origin - at) / 25.4:.3f}".lstrip("0") for origin, at in zip((x0, z0), hole)
        )
        for hole in holes
    }
    assert printed == {
        (-part.COLUMN_X, part.REAR_COLUMN_Z): ("16.343", ".831"),
        (-part.COLUMN_X, part.FRONT_COLUMN_Z): ("16.343", "9.651"),
        (part.COLUMN_X, part.REAR_COLUMN_Z): (".831", ".831"),
        (part.COLUMN_X, part.FRONT_COLUMN_Z): (".831", "9.651"),
    }
    assert x0 - part.COLUMN_X == pytest.approx(part._boss_radius(part.DATUM_TARGET_Y))
    assert drawing.negative_locations((("A1", ".673", ".750", ""), ("B1", "-1.0", "2.0", ""))) == ["-1.0"]
    # Each hanger hole's station: its own vertical dimension from the rear
    # sockets' drawn axis to the hole (#2628 (d)), machined to machined, so
    # it prints at the title block's .XXX with nothing added.
    stations = {
        "front hanger z from lower sockets": part.STUD_Z_FRONT,
        "rear hanger z from lower sockets": part.STUD_Z_REAR,
    }
    assert set(drawing.HANGER_Z_TEXT_XY) == set(stations)
    assert not {(part.HANGER_X, z) for z in stations.values()} & set(holes)
    assert [
        (f"{(part.REAR_COLUMN_Z - z) / 25.4:.{spec.DRAWING_REFERENCE_PRECISION[label]}f}")
        for label, z in stations.items()
    ] == ["7.966", "0.861"]
    # The band left of the title block, under the plan's rear bosses and
    # over the edge-break note, holds the table.
    table = _hole_table_box()
    assert table[2] < TITLE_BLOCK[0]
    plan_bottom = _plan(0.0, part.REAR_COLUMN_Z + part.BOSS_DIA / 2.0)[1]
    assert table[3] < plan_bottom - 0.001
    assert table[1] > drawing.EDGE_NOTE_XY[1] + 0.001
    # The origin mark's arrows and labels stand clear of the table, the
    # rear-west boss beside the corner, the keeper callout and the title
    # block: the X arrow under the corner, the Y arrow right of it.
    (ox, oy), arrows = _table_origin_mark()
    boss, boss_r = _plan(part.COLUMN_X, part.REAR_COLUMN_Z), part.BOSS_DIA / 2.0 * _S
    _callout, callout_box = _keeper_callout_placed()
    frame = drawing.SHEET_FRAME
    for name, box in arrows.items():
        assert _box_box_gap(box, table) >= drawing.INK_CLEARANCE, name
        assert _box_point_gap(box, boss) - boss_r >= drawing.INK_CLEARANCE, name
        assert _box_box_gap(box, callout_box) >= drawing.INK_CLEARANCE, name
        assert _box_box_gap(box, TITLE_BLOCK) >= drawing.INK_CLEARANCE, name
        assert frame[0] < box[0] and box[2] < frame[2] - drawing.INK_CLEARANCE, name
    assert arrows["X arrow"][3] < oy and arrows["Y arrow"][0] > ox


def test_keeper_callout_leader_stands_clear_of_the_table_origin_mark() -> None:
    """Farm run 20261111T023438415Z: with the table's origin on the F|G
    corner (owner ruling D2, #2333) the keeper callout's leader, then
    climbing from under the rear tap over that corner, ran through the
    origin mark's "Y".  #1038: the callout stands over the tap's level, so
    its leader and the whole block stand above the mark and the G trace."""
    from _layout_geometry import Segment

    hole, hole_r, _boss, _boss_r = _keeper_geometry()
    callout, tip = drawing.keeper_callout_placement(hole, hole_r)
    leader = (_shoulder_end(callout, tip), tip)
    (ox, oy), arrows = _table_origin_mark()
    ink = drawing.INK_CLEARANCE
    for name, box in arrows.items():
        assert _box_segment_gap(box, leader) >= ink, name
        assert box[3] < tip[1] - ink, name
    # The G trace climbs the corner's own x to TABLE_G_LINE_FRONT_Z.
    g_end = _plan(drawing.TABLE_ORIGIN_XZ[0], drawing.TABLE_G_LINE_FRONT_Z)
    assert g_end[0] == ox and oy < g_end[1] < leader[1][1]
    assert _segment_gap(Segment(ox, oy, *g_end), Segment(*leader[0], *leader[1])) >= ink
    # The facing note hangs under the shoulder, right of the mark's column.
    note_x, note_y = drawing.keeper_facing_note_xy(callout)
    assert note_x == pytest.approx(leader[0][0])
    assert note_x > max(box[2] for box in arrows.values()) + ink


def test_hole_table_locations_drop_the_leading_zero() -> None:
    """Farm run 20261107T000550920Z: the native table printed the origin's
    "0.000"; an inch sheet prints ".000".  The native LOC cells refuse a
    text override (run 20261107T003254101Z), so the document's hole-table
    leading-zero option is set before the table is inserted, and the table
    is read back."""

    assert drawing.HOLE_TABLE_LEADING_ZERO == "swLeadingZero_DoNotShow"
    assert drawing.leading_zero_locations(
        (("A1", "0.000", "-8.820", ""), ("A2", "-0.512", ".000", ""))
    ) == ["0.000", "-0.512"]
    assert drawing.leading_zero_locations(
        (("A1", ".000", "-8.820", ""), ("B2", "7.165", "-1.104", "0.5"))
    ) == []


def test_socket_finish_leader_stays_clear_of_the_table_origin_mark() -> None:
    """Farm run 20261107T084432155Z (leader-crosses-leader): the socket Ra
    leader, level with the A1 axis, ran through the origin mark's Y arrow,
    then at the plan's lower-left corner.  Owner ruling D2 (#2333) moved the
    origin to the F|G corner at the plan's lower right, so the whole mark
    stands right of the leader.  Since #2628 (d) the leader rises from its
    tail (the symbol point plus FINISH_LEADER_TAIL) to the rear-east bore's
    lower-left rim, under the rear sockets' axis line the hanger stations
    stand from, over the hole table, its row under that axis too."""
    angle = math.radians(drawing.SOCKET_FINISH_LANDING_DEG)
    r = part.BORE_DIA / 2.0 * _S
    bore = _plan(-part.COLUMN_X, part.REAR_COLUMN_Z)
    rim = (bore[0] + r * math.cos(angle), bore[1] + r * math.sin(angle))
    sx, sy = drawing.SOCKET_FINISH_SYMBOL_XY
    leader = ((sx + drawing.FINISH_LEADER_TAIL, sy), rim)
    ink = drawing.INK_CLEARANCE
    _origin, arrows = _table_origin_mark()
    for name, box in arrows.items():
        assert _box_segment_gap(box, leader) >= ink, name
        assert box[0] - max(leader[0][0], rim[0]) >= ink, name
    assert bore[1] - max(leader[0][1], rim[1]) >= ink
    # The "TUBE SOCKET BORES, 4X" row, 9 mm over the symbol point and
    # about 2.5 mm tall, stays under the axis line's extension too.
    assert bore[1] - (sy + 0.009 + 0.0025) >= ink
    assert sy - _hole_table_box()[3] >= ink


def test_hole_tags_stand_in_the_windows_beside_their_holes() -> None:
    """Farm run 20261106T204855971Z: the native tags, parked up-right of
    their holes, sat under the hanger and keeper callouts' leaders.  Each
    now stands in the open window next to its hole, an ink clearance inside
    the rails and the crossbar, clear of the D centreline, of the keeper
    callout and of the table's origin mark (farm run 20261106T210746725Z:
    the mark's X arrow ran through a tag).  Owner ruling D2 (#2333) leaves
    the table the four sockets only, each right tag diagonally inside its
    own; the left ones stand outboard (#2628 (d))."""
    s = drawing.DETAIL_VIEW_SCALE / 1000.0
    cx, cy = drawing.DETAIL_TOP_CENTER
    ink = drawing.INK_CLEARANCE
    windows = {
        "left": (cx - part.INNER_X * s, cx + part.BAR_X0 * s),
        "right": (cx + part.BAR_X1 * s, cx + part.INNER_X * s),
    }
    bottom, top = cy - part.INNER_Z * s, cy + part.INNER_Z * s
    _callout, callout_box = _keeper_callout_placed()
    half_w, half_h = drawing._HOLE_TAG_HALF
    _origin, arrows = _table_origin_mark()
    assert len(drawing.TABLE_HOLES) == 4
    for x, z, diameter, _mate in drawing.TABLE_HOLES:
        assert diameter == part.BORE_DIA, (x, z)
        x0, y1 = drawing.hole_tag_position(x, z)
        box = (x0, y1 - 2 * half_h, x0 + 2 * half_w, y1)
        assert _box_box_gap(box, callout_box) >= ink, (x, z)
        for arrow in arrows.values():
            assert _box_box_gap(box, arrow) >= ink, (x, z)
        hx, hy = cx + x * s, cy - z * s
        assert math.dist((x0 + half_w, y1 - half_h), (hx, hy)) < 0.023
        if x < 0:
            # #2628 (d): a left socket's tag stands outboard, down-left of
            # it, its upper-right corner an ink clearance off the boss.
            assert x0 + half_w < hx and y1 - half_h < hy, (x, z)
            corner = math.dist((box[2], box[3]), (hx, hy))
            assert corner - part.BOSS_DIA / 2.0 * s >= ink, (x, z)
            continue
        # Inward of its socket on both sheet axes.
        assert x0 + half_w < hx and (y1 - half_h > hy) == (z > 0), (x, z)
        d_x = cx + part.HANGER_X * s
        left, right = windows["right"]
        assert left + ink <= box[0] and box[2] <= right - ink, (x, z)
        assert bottom + ink <= box[1] and box[3] <= top - ink, (x, z)
        assert box[2] <= d_x - ink or box[0] >= d_x + ink, (x, z)


def test_socket_callout_leaves_its_leader_a_clear_corridor_to_a2() -> None:
    """Farm run 20261106T212431241Z (row past the frame); the machinist
    reviews of farm run 20261107T170344738Z's PDF (above A2 the leader
    crossed datum D's dimension line at its left arrowhead).  The block's
    widest row, 2.58 mm a glyph, stays inside the frame and ends left of the
    left boss tangent; its radial leader to A2's near rim stays over the
    boss leader's landing.  D's station stands on sheet 7 now (owner ruling
    D2, #2333), so no dimension line runs over A2 on this sheet."""
    x, y = drawing.DETAIL_TOP_KEEP["B0Dia"]
    rows = drawing.DETAIL_CALLOUTS["B0Dia"].splitlines()
    assert len(rows) <= 2
    half = max(map(len, rows)) * 0.00258 / 2.0
    ink = drawing.INK_CLEARANCE
    assert x - half >= drawing.SHEET_FRAME[0] + ink
    tangent_x = _plan(-drawing.PLAN_HALF_X, 0.0)[0]
    assert x + half <= tangent_x - 0.004
    cx, cy = _plan(-part.COLUMN_X, part.FRONT_COLUMN_Z)

    def landing(text_xy, radius):
        run = math.dist(text_xy, (cx, cy))
        return (
            cx - (cx - text_xy[0]) * radius / run,
            cy - (cy - text_xy[1]) * radius / run,
        )

    rim = landing((x + half, y), part.BORE_DIA / 2.0 * _S)
    assert not hasattr(drawing, "D_STATION_TEXT_XY")
    assert "DStation" not in drawing.DETAIL_TOP_KEEP
    boss_x, boss_y = drawing.DETAIL_TOP_KEEP["C0Dia"]
    boss_landing = landing((boss_x, boss_y), part.BOSS_DIA / 2.0 * _S)
    assert rim[1] - boss_landing[1] >= ink
    # Over the Ø1.77 boss callout's three rows (#2628 (d)).
    assert y - boss_y >= 0.015


def test_hanger_stations_stand_in_the_left_margin_from_the_rear_axis() -> None:
    """Owner ruling 2026-11-20 (Pedro), #2628 option (d): both hanger-hole
    stations stand from the rear sockets' axis with their values in the
    left margin, off the part (rule 14).  The rear (shorter) station is the
    inner line, its value left of it over the rear-left boss; the front
    station's line stands left of that value, its value centred on it; no
    extension line crosses the other station's dimension line."""
    ink = drawing.INK_CLEARANCE
    tangent_x = _plan(-drawing.PLAN_HALF_X, 0.0)[0]
    axis_y = _plan(-part.COLUMN_X, part.REAR_COLUMN_Z)[1]
    front_x, front_y = drawing.HANGER_Z_TEXT_XY["front hanger z from lower sockets"]
    rear_x, rear_y = drawing.HANGER_Z_TEXT_XY["rear hanger z from lower sockets"]
    front_hole_y = _plan(part.HANGER_X, part.STUD_Z_FRONT)[1]
    rear_hole_y = _plan(part.HANGER_X, part.STUD_Z_REAR)[1]
    glyph, half_h = 0.00258, 0.00175
    # The rear value, four glyphs left of its line, over the rear hole and
    # the rear-left boss (its top at the axis plus the boss radius).
    rear_box = (rear_x - 0.001 - 4 * glyph, rear_y - half_h, rear_x - 0.001, rear_y + half_h)
    assert rear_x <= tangent_x - ink
    assert rear_box[1] - rear_hole_y >= ink
    assert rear_box[1] - (axis_y + part.BOSS_DIA / 2.0 * _S) >= ink
    # The front line stands left of the rear value; its value, centred on
    # it, between the rear value and the front hole, clear of the boss.
    front_box = (front_x - 2.5 * glyph, front_y - half_h, front_x + 2.5 * glyph, front_y + half_h)
    assert rear_box[0] - front_x >= ink
    assert front_box[2] <= tangent_x - ink
    assert rear_y + half_h + ink <= front_box[1] and front_box[3] + ink <= front_hole_y
    # The rear station's extension from its hole ends right of the front
    # line, so neither crosses the other's dimension line.
    assert front_x < rear_x - ink and rear_hole_y < front_hole_y
    assert axis_y < rear_hole_y
    # The left sockets' tags stand outboard, each leader landing on its
    # bore's lower-left rim (farm run 20261120T205313453Z: SolidWorks's fixed
    # attachment), so no leader crosses an extension line: A1's under the
    # rear axis line, A2's over the front station's extension line; both
    # boxes clear of every station line and the socket finish's leader.
    half_w, half_h = drawing._HOLE_TAG_HALF
    r = part.BORE_DIA / 2.0 * _S
    angle = math.radians(drawing.SOCKET_FINISH_LANDING_DEG)
    a1 = _plan(-part.COLUMN_X, part.REAR_COLUMN_Z)
    finish = (
        (drawing.SOCKET_FINISH_SYMBOL_XY[0] + drawing.FINISH_LEADER_TAIL,
         drawing.SOCKET_FINISH_SYMBOL_XY[1]),
        (a1[0] + r * math.cos(angle), a1[1] + r * math.sin(angle)),
    )
    for z, ext_y, above in (
        (part.REAR_COLUMN_Z, axis_y, False),
        (part.FRONT_COLUMN_Z, front_hole_y, True),
    ):
        hx, hy = _plan(-part.COLUMN_X, z)
        x0, y1 = drawing.hole_tag_position(-part.COLUMN_X, z)
        box = (x0, y1 - 2 * half_h, x0 + 2 * half_w, y1)
        tip = (hx + r * math.cos(math.radians(225.0)), hy + r * math.sin(math.radians(225.0)))
        leader = ((box[2], y1 - half_h), tip)
        if above:
            assert box[1] - ext_y >= ink and min(leader[0][1], tip[1]) - ext_y >= ink, z
        else:
            assert ext_y - box[3] >= ink and ext_y - max(leader[0][1], tip[1]) >= ink, z
        for line_x, low, high in ((front_x, axis_y, front_hole_y), (rear_x, axis_y, rear_hole_y)):
            assert _box_segment_gap(box, ((line_x, low), (line_x, high))) >= ink, z
        assert _box_segment_gap(box, finish) >= ink, z
        assert _box_box_gap(box, rear_box) >= ink and _box_box_gap(box, front_box) >= ink, z
    tip = (a1[0] + r * math.cos(math.radians(225.0)), a1[1] + r * math.sin(math.radians(225.0)))
    assert math.dist(tip, finish[1]) >= 0.004


def test_side_rail_web_text_stands_beside_its_own_section() -> None:
    """Local machinist reviews: parked right of E-E the 2X SIDE RAIL WEB
    rows ran out over M-M (farm run 20261107T170344738Z's PDF); centred over
    E-E the web's extension lines ran up through "RAIL" (farm run
    20261107T204437943Z).  The web is drafted from the underside, so its
    .51 holds there: the three rows stand left of the rail UNDER the web,
    off both extension lines, under the plan's 1.35 SIDE FLANGE rows and
    right of the front view's RAIL HEIGHT.  Farm run 20261111T023438415Z's
    native rows: a three-row block's value line 2.78 mm over its text
    point, glyphs 4.5 over a line, the last row's line -- the dimension
    line -- 8.33 under the point; ".51 ±.03" 16.79 mm wide, "AT UNDERSIDE"
    31.40, "RAIL HEIGHT" 26.78."""
    x, y = drawing.SIDE_WEB_TEXT_XY
    assert drawing.SIDE_SECTION_KEEP == {"SideWebT": drawing.SIDE_WEB_TEXT_XY}
    assert drawing.SIDE_WEB_QUALIFIER.splitlines() == ["2X WEB", "AT UNDERSIDE"]
    half = 0.03140 / 2.0
    top, line_y = y + 0.00278 + 0.0045, y - 0.00833
    ink = drawing.INK_CLEARANCE
    web_left = drawing._side_section_xy(-part.WEB_OUT_X, 0.0)[0]
    assert x + half <= web_left - ink
    # The value row is level with the flange, whose outer face stands left
    # of the web's.
    assert x + 0.01679 / 2.0 <= drawing._side_section_xy(-part.OUTER_X, 0.0)[0] - ink
    # The dimension line stands under the underside the width is taken on.
    assert drawing._side_section_xy(0.0, -part.HALF_H)[1] - line_y >= ink
    assert drawing.GEOMETRY_TOP_KEEP["SideFlangeWidth"][1] - 0.00833 - top >= ink
    rail_height_right = drawing.GEOMETRY_FRONT_KEEP["RingHeight"][0] + 0.02678 / 2.0
    assert (x - half) - rail_height_right >= ink


def test_flange_widths_say_the_faced_top_they_hold_at() -> None:
    """Owner ruling D1 (#2333) takes the flange rims' draft out, so the 1.50
    and 1.35 flange widths are nominal on the faced top and narrow under it:
    each says AT FACED TOP, as a web width says AT UNDERSIDE (Codjiflo round
    2 of 518e3d01e1: a drafted size with no station).  The third row lifts
    each text point half a row pitch, which leaves the dimension line, 8.33
    mm under the point, where farm run 20261111T043554104Z printed it."""
    callouts = {
        "FrFlangeWidth": drawing.RAIL_SECTION_CALLOUTS["FrFlangeWidth"],
        "SideFlangeWidth": drawing.GEOMETRY_CALLOUTS["SideFlangeWidth"],
    }
    assert callouts["FrFlangeWidth"].splitlines() == ["2X FLANGE", "AT FACED TOP"]
    assert callouts["SideFlangeWidth"].splitlines() == [
        "2X SIDE FLANGE",
        "AT FACED TOP",
    ]
    assert set(callouts) <= set(spec.AS_CAST_DIMENSIONS["OuterProfile"])
    # A rim stands at its nominal on the faced top and has receded at the
    # flange's underside, on the side rails and on the front and rear ones.
    top, bottom = part.HALF_H - 1e-3, part.FLANGE_BOT_Y + 1e-3
    for at in (
        (part.OUTER_X - 0.05, spec.SIDE_SECTION_Z),
        (spec.RAIL_SECTION_X, part.OUTER_Z - 0.05),
    ):
        assert part._casting_occupies(at[0], top, at[1])
        assert not part._casting_occupies(at[0], bottom, at[1])
    assert drawing.RAIL_SECTION_KEEP["FrFlangeWidth"][1] - 0.00833 == pytest.approx(
        0.22445, abs=1e-5
    )
    assert drawing.GEOMETRY_TOP_KEEP["SideFlangeWidth"][1] - 0.00833 == pytest.approx(
        0.11445, abs=1e-5
    )


def test_cross_tap_callout_counts_all_four_taps_then_names_its_mate() -> None:
    """Farm run 20261106T212431241Z: "2X ... SAME AT OPPOSITE END, 4X
    TOTAL" read as a private phrase (rule 26).  The native count becomes
    one 4X, the Hole Wizard variables stay, and the mate line follows the
    thread row."""
    native = {
        5: "<hw-thread> <HOLE-DEPTH><hw-threaddepth>",
        6: "",
        7: "<NUM_INST>X <MOD-DIAM><hw-tapdrldia> <HOLE-DEPTH><hw-tapdrldepth>",
        8: "",
    }
    updated = drawing.cross_tap_definitions(native)
    assert updated[7] == "4X <MOD-DIAM><hw-tapdrldia> <HOLE-DEPTH><hw-tapdrldepth>"
    assert updated[5] == native[5] and updated[6] == native[6]
    assert updated[8] == "FOR MHA-FR-VN-53, FAR WALL ONLY,\nDEPTHS FROM COUNTERBORE FLOOR"
    assert drawing.cross_tap_definitions({**native, 8: "X"})[8] == (
        "X\nFOR MHA-FR-VN-53, FAR WALL ONLY,\nDEPTHS FROM COUNTERBORE FLOOR"
    )
    with pytest.raises(RuntimeError, match="one instance count"):
        drawing.cross_tap_definitions({**native, 7: native[7].replace("<NUM_INST>X ", "")})


def test_hole_table_rows_bind_by_magnitude_with_one_sign_per_axis() -> None:
    def cells(sx: float, sy: float) -> tuple[tuple[str, ...], ...]:
        return tuple(
            ("A", f"{sx * (x - drawing.TABLE_ORIGIN_XZ[0]) / 25.4:.3f}",
             f"{sy * (z - drawing.TABLE_ORIGIN_XZ[1]) / 25.4:.3f}", "Ø")
            for x, z, _d, _m in drawing.TABLE_HOLES
        )

    for sx, sy in ((1.0, -1.0), (1.0, 1.0), (-1.0, -1.0)):
        rows = cells(sx, sy)[::-1]
        bound = drawing.bind_hole_table_rows(rows, 25.4)
        assert sorted(bound.values()) == list(range(len(drawing.TABLE_HOLES)))
        assert bound[1] == len(drawing.TABLE_HOLES) - 1
    mixed = list(cells(1.0, 1.0))  # every Y below the rear corner reads negative
    mixed[-1] = (mixed[-1][0], mixed[-1][1], mixed[-1][2].lstrip("-"), mixed[-1][3])
    with pytest.raises(RuntimeError, match="mixes signs"):
        drawing.bind_hole_table_rows(tuple(mixed), 25.4)
    with pytest.raises(RuntimeError, match="rows for"):
        drawing.bind_hole_table_rows(cells(1.0, -1.0)[:-1], 25.4)


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
    callout, tip = drawing.keeper_callout_placement(hole, hole_r)
    shoulder_y = callout[1] - drawing.KEEPER_CALLOUT_SHOULDER_DROP
    box = (callout[0] - left, shoulder_y, callout[0] + right, callout[1] + up)
    assert box[2] <= drawing.SHEET_FRAME[2] - drawing.INK_CLEARANCE
    assert box[1] > TITLE_BLOCK[3]
    # #1038: the block stands over the tap's level, right of the barrel.
    assert shoulder_y - hole[1] == pytest.approx(drawing.KEEPER_LEADER_RUN[1])
    assert box[0] - hole[0] == pytest.approx(drawing.KEEPER_LEADER_RUN[0])
    assert box[0] > boss[0] + boss_r
    assert math.dist(tip, hole) == pytest.approx(hole_r)
    # The plan keeps the centre the former lower-right callout gave it.
    assert drawing.DETAIL_TOP_CENTER == pytest.approx((0.19323, 0.1605))


def _hole_table_box():
    """Sheet 3's hole table (x0, y0, x1, y1), hung from its top-left anchor:
    the drawn TAG, X/Y LOC and MATE widths (the native SIZE column hidden),
    32.9 mm tall as farm run 20261111T023438415Z's native table read with
    its header and four socket rows (y 48.59 to 81.50)."""
    x, y = drawing.HOLE_TABLE_ANCHOR
    width = (
        drawing.HOLE_TABLE_TAG_WIDTH + 2 * drawing.HOLE_TABLE_LOC_WIDTH
        + drawing.HOLE_TABLE_MATE_WIDTH
    )
    return (x, y - 0.0329, x + width, y)


def _keeper_callout_placed():
    """RD4's (callout point, sheet box) as the build places it."""
    hole, hole_r, _boss, _boss_r = _keeper_geometry()
    callout, _tip = drawing.keeper_callout_placement(hole, hole_r)
    left, _down, right, up = drawing.KEEPER_CALLOUT_EXTENT
    return callout, (
        callout[0] - left,
        callout[1] - drawing.KEEPER_CALLOUT_SHOULDER_DROP,
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
    # The hole table hangs inside the frame, clear of the title block, the
    # plan and the keeper callout.
    table = _hole_table_box()
    _callout, callout_box = _keeper_callout_placed()
    left_x, _down, right_x, _up = drawing.KEEPER_CALLOUT_EXTENT
    assert frame[0] < table[0] < table[2] < frame[2]
    assert frame[1] < table[1] < table[3] < frame[3]
    assert _box_box_gap(table, TITLE_BLOCK) >= drawing.INK_CLEARANCE
    assert _box_box_gap(table, callout_box) >= drawing.INK_CLEARANCE
    assert table[3] < bottom
    # The expanded width covers a conservative full-em prefix allowance.
    # It is a derived envelope, not a new observed native measurement.
    assert (
        max(map(len, drawing.TRANSFER_KEEPER_CALLOUT.splitlines()))
        * drawing.KEEPER_TRANSFER_CHARACTER_WIDTH
        <= left_x + right_x + 1e-12
    )


def test_crossbar_pocket_depth_stands_between_the_side_rail_and_the_t() -> None:
    # The underside's 138.0 names the pockets; M-M, the crossbar's own
    # section, prints their depth, flange underside to the T's underside, arrows
    # inside.  Its two rows print 24.6 x 9.2 mm (farm run
    # 20261111T023438415Z's native "1.117 ±.030" over "2X POCKET"), the
    # underline 1.0 under the block; extension lines overshoot their line
    # 1.0 mm.
    from _layout_geometry import Box, Segment, segment_box_distance, segment_box_overlap_length

    # Owner ruling B2 (#2333): the depth, the length and the front end's
    # station are the model's own as-cast dimensions, each with its ±.03.
    assert drawing.CROSSBAR_SECTION_KEEP["PocketDepth"] == drawing.CROSSBAR_POCKET_DEPTH_LINE_XY
    assert drawing.CROSSBAR_SECTION_CALLOUTS["PocketDepth"] == "2X POCKET"
    assert drawing.UNDERSIDE_KEEP["PocketLength"] == drawing.POCKET_LENGTH_TEXT_XY
    assert drawing.UNDERSIDE_CALLOUTS["PocketLength"] == "2X POCKET"
    assert drawing.UNDERSIDE_KEEP["PocketFromSocket"] == drawing.POCKET_FROM_SOCKET_LINE_XY
    assert drawing.UNDERSIDE_CALLOUTS["PocketFromSocket"] == ""
    for feature, name in (
        ("BarPockets", "PocketDepth"),
        ("BarPocketProfile", "PocketLength"),
        ("BarPocketProfile", "PocketFromSocket"),
    ):
        assert name in spec.DRAWING_DIMENSIONS[feature], name
        assert name in spec.AS_CAST_DIMENSIONS[feature], name
    assert drawing.BAR_POCKET_FROM_SOCKET == pytest.approx(
        abs(part.FRONT_COLUMN_Z) - part.BAR_POCKET_Z
    )
    assert drawing.POCKET_FROM_SOCKET_LINE_XY[0] == drawing.POCKET_LENGTH_TEXT_XY[0]
    assert drawing.SHEET_FRAME[0] < drawing.POCKET_FROM_SOCKET_LINE_XY[0]
    # The pocket is the .XXX grip less the flange, so its as-cast band prints
    # at the grip's places; no sheet-derived reference states it any more.
    assert spec.DRAWING_PRECISION["BarPockets"] == {"PocketDepth": spec.HANGER_GRIP_PLACES}
    assert "crossbar pocket depth" not in spec.DRAWING_REFERENCE_PRECISION
    assert part.POCKET_H == pytest.approx(part.RING_HEIGHT - part.FLANGE)
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
    # Between the side rail's inner face and the T, clear of E-E's web
    # dimension line (its three rows' last line, 8.33 mm under the text
    # point, out to its right arrow's tail 6.35 mm past the web's inner face)
    # and over the sections' captions.
    assert text.xmin - xy(-part.INNER_X, 0.0)[0] >= ink
    web_line_y = drawing.SIDE_WEB_TEXT_XY[1] - 0.00833
    web_line = Segment(
        drawing.SIDE_WEB_TEXT_XY[0], web_line_y, xy(-part.WEB_IN_X, 0.0)[0] + 0.00635, web_line_y
    )
    assert segment_box_distance(web_line, text) >= ink
    assert _segment_gap(leader, web_line) >= ink
    assert leader.y1 - drawing.SIDE_SECTION_CAPTION_XY[1] >= ink


# --- The faced keeper-rail top (user ruling 2026-10-11) ---------------------


def test_keeper_feet_stay_on_the_faced_rail_top_and_keep_their_ligaments() -> None:
    assert part.WEB_T == pytest.approx(12.954)
    assert part.WEB_OUT_X - part.WEB_IN_X == pytest.approx(part.WEB_T)
    assert (part.HALF_H, part.FLANGE, part.FLANGE_BOT_Y) == pytest.approx(
        (18.2499, 8.128, 10.1219)
    )
    assert part.KEEPER_TAP_THREAD_WALL_MARGIN == pytest.approx(2.202189533594047)
    assert part.KEEPER_TAP_DRILL_WALL_MARGIN == pytest.approx(1.9484089915363136)
    assert min(part.KEEPER_FOOT_BOSS_MARGINS) >= 1.016
    # Along the rail the faced top runs boss to boss, so the fitted foot
    # stays on it exactly when it clears the bosses at the printed bands.
    assert min(part.KEEPER_FOOT_PRINTED_BOSS_MARGINS) > 0.0
    # Owner ruling K5 (#1038): the feet end past the end rails' window
    # faces.  No edge of the faced top lies there: each foot stands on the
    # west rail's own flange, which runs on under the barrel to the corner,
    # its two sides inside that rail's rims (below).
    assert abs(part.KEEPER_FOOT_TIP_Z_FRONT) > part.INNER_Z
    assert not hasattr(part, "KEEPER_FOOT_CORNER_FLANGE_MARGIN")
    assert part.KEEPER_TAP_X - 7.0 > part.INNER_X
    # Across it the widest printed foot (on the keeper's own sheet), at the
    # farthest printed fit-up offset from the web's median, stays inside the
    # narrowest as-cast flange less the largest printed top-rim break leg
    # (.06 + .01).  The flange's faces and the web's median each stand off
    # the rail's socket-axis line: half the flange's ±.03 and half the web's
    # ⌖.06 zone.
    cast = spec.AS_CAST_BAND
    chamfer_places = spec.DRAWING_REFERENCE_PRECISION["top rim chamfer"]
    foot_places = keeper.DRAWING_PRECISION["Foot"]["Depth"]
    half_flange = (part.RAIL_W_SIDE - cast) / 2.0
    median = part.RAIL_WEB_POSITION_ZONE / 2.0 + cast / 2.0
    offset = (
        abs(part._keeper_printed(keeper.KEEPER_FITUP_X_FROM_WEB_MM, keeper.KEEPER_FITUP_PLACES))
        + keeper.KEEPER_FITUP_X_BAND_MM
    )
    half_foot = part._keeper_printed(keeper.KEEPER_WIDTH, foot_places, 1.0) / 2.0
    max_chamfer = spec.printed_limit(part.EDGE_CHAMFER, chamfer_places, 1.0)
    # The lug centre at MHA-CH-00's printed .114 ±.004 (delegated ruling
    # 2026-11-24 (Main), precedent: owner ruling 2026-11-01, #2144
    # (rulings.md D15)).
    assert (half_flange, median, offset, half_foot, max_chamfer) == pytest.approx(
        (16.764, 1.143, 2.9972, 7.112, 1.778)
    )
    assert max_chamfer == pytest.approx(part.EDGE_BREAK_PRINTED_MAX)
    margin = half_flange - median - offset - half_foot - max_chamfer
    assert part.KEEPER_FOOT_PRINTED_FLAT_TOP_SIDE_MARGIN == pytest.approx(margin)
    assert margin == pytest.approx(3.7338)
    # Faced in place: the rail-top plane stays put.
    assert part.HALF_H - part.FLANGE_BOT_Y == pytest.approx(spec.FLANGE_THICKNESS_MM)
    # Native finishes: the four sockets, and the four boss tops (owner
    # ruling B3, #2333).  The faced top plane's SEAT_UM, washer seats
    # included, rides on linked note B; the cap-recess floors carry none
    # because caps seat on the tube ends, clear of the floors; the hub bore
    # and set-screw spot face carry none (machinist review r1: a clearance
    # bore and a clamp face neither run nor locate).
    corners = [(rail, end) for rail in ("east", "west") for end in ("front", "rear")]
    assert [c.key for c in spec.SURFACE_FINISHES] == [
        f"{feature}_{rail}_{end}"
        for feature in ("socket", "boss_top")
        for rail, end in corners
    ]
    assert not hasattr(spec, "HANGER_SPOTFACE_TARGET")


def test_keeper_tap_drill_wall_is_accepted_under_the_target_as_rv14() -> None:
    # Owner rulings D3/D4 (#2333): with the web's median ±.03 to the socket
    # axes and its faces at the 2° minimum an added family may print, and the
    # lug centre at MHA-CH-00's printed .114 ±.004, the keeper taps' drill
    # wall is .0767, under the .080 target. Delegated ruling 2026-11-24
    # (Main), precedent: owner ruling 2026-11-01, #2144 (rulings.md D15),
    # accepts it at .076 as the minor entry RV-14; RV-08 stays retired and no
    # sheet note returns.
    assert 0.076 * spec.IN <= part.KEEPER_TAP_DRILL_WALL_MARGIN < 0.077 * spec.IN
    assert spec.KEEPER_TAP_WALL_ACCEPTED_MM == pytest.approx(0.076 * spec.IN)
    assert (
        part.WALL_FLOOR_MM
        < spec.KEEPER_TAP_WALL_ACCEPTED_MM
        <= part.KEEPER_TAP_DRILL_WALL_MARGIN
        < WALL_TARGET_MM
    )
    assert not hasattr(part, "KEEPER_WALL_NOTE")
    entries = {
        entry.id: entry
        for entry in load_exceptions(CAD_ROOT / "config", "fr_top_frame", "part")
    }
    assert "RV-08" not in entries
    rv14 = entries["RV-14"]
    assert rv14.kind == "minor"
    assert "rulings.md D15" in rv14.reason
    assert ".0767" in rv14.finding and ".076 MIN" in rv14.where


def test_top_frame_drawing_is_seven_sheets() -> None:
    # Owner rulings B6 and D2 (#2333): the casting's own datum frame takes a
    # seventh sheet, its two views at the title block's scale.
    assert drawing.SHEET_NAMES == (
        "PICTORIAL",
        "GEOMETRY",
        "HOLES-SOCKETS",
        "CROSS-TAPS",
        "HUB-SET-SCREW",
        "UNDERSIDE",
        "CAST-DATUMS",
    )
    assert set(drawing.SHEET_SCALES) == set(drawing.SHEET_NAMES)
    assert drawing.SHEET_SCALES["CAST-DATUMS"] == drawing.SHEET_SCALE
    # No split-line seat regions remain to dimension, qualify or section.
    assert not [key for key in spec.DRAWING_REFERENCE_PRECISION if "keeper seat" in key]


def test_pictorials_are_named_in_words_not_face_arrows() -> None:
    """Owner 2026-11-07 (rule 26): several isometric views are labelled
    ISOMETRIC VIEW FROM TOP / FROM BOTTOM, not with arrows to face names.
    Each caption stands under its view (v48: views at y 126..205 mm), over
    the title block (top 64.7 mm), and carries no scale: both views print at
    the sheet's 1:4."""

    assert all(view.labels == () for view in drawing.PICTORIAL_VIEWS)
    assert drawing.PICTORIAL_SCALE == drawing.SHEET_SCALES["PICTORIAL"]
    tops = {view.octant[1] for view in drawing.PICTORIAL_VIEWS}
    assert tops == {1, -1}
    captions = dict(drawing.PICTORIAL_CAPTIONS)
    assert set(captions) == {"ISOMETRIC VIEW FROM TOP", "ISOMETRIC VIEW FROM BOTTOM"}
    for view in drawing.PICTORIAL_VIEWS:
        text = "ISOMETRIC VIEW FROM " + ("TOP" if view.octant[1] > 0 else "BOTTOM")
        x, y = captions[text]
        assert x == view.center_xy[0]
        assert 0.0647 + 0.010 <= y <= 0.126 - 0.010
        assert "SCALE" not in text


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
    assert _box_box_gap(note, _hole_table_box()) >= ink


# --- The faced underside plane (user ruling 2026-10-12) ---------------------


def test_underside_facing_note_is_the_part_property_carrying_the_seat_finish() -> None:
    # Every face on the underside plane between the bosses, named by the
    # mating seats that need it; the bosses and hub gussets below the plane
    # are named out of it.  No flatness zone, no setup method; drawing-guidelines.md rule 7 (notes: few, flagged, never a method)'s four
    # rows at most.
    assert spec.DRAWING_NOTES_C.splitlines() == [
        "UNDERSIDE PLANE BETWEEN BOSSES",
        "(MHA-SM-02 KNIFE-MOUNT SEATS):",
        "Ra 125; BOSS BOTTOMS AND",
        "HUB GUSSETS EXCLUDED.",
    ]
    assert _config.parts("sm-knife-mount")["number"] == "MHA-SM-02"


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


@functools.cache
def _drawing_tree():
    """The drawing script's syntax tree (read-only: one parse a session)."""
    return ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))


def _labelled_call(node, name, label):
    """The one ``name(...)`` call under ``node`` whose ``label=`` is ``label``."""
    (call,) = [
        call
        for call in _named_calls(node, name)
        if isinstance(_keyword(call, "label"), ast.Constant)
        and _keyword(call, "label").value == label
    ]
    return call


def _function(node, name):
    """The one function ``name`` defined anywhere under ``node``."""
    (function,) = [
        item
        for item in ast.walk(node)
        if isinstance(item, (ast.FunctionDef,)) and item.name == name
    ]
    return function


def _build_value(function, expression):
    """``expression``, a syntax node inside ``function``, evaluated against
    the drawing module and the function's own plain ``name = ...`` locals it
    reads (each assigned once from module names)."""
    import builtins

    scope = dict(vars(drawing))
    local = {
        node.id for node in ast.walk(expression) if isinstance(node, ast.Name)
    } - set(scope) - set(vars(builtins))
    assigned = [
        statement
        for statement in ast.walk(function)
        if isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
        and statement.targets[0].id in local
    ]
    assert sorted(statement.targets[0].id for statement in assigned) == sorted(local)
    for statement in assigned:
        scope[statement.targets[0].id] = eval(
            compile(ast.Expression(statement.value), drawing.__file__, "eval"), scope
        )
    return eval(compile(ast.Expression(expression), drawing.__file__, "eval"), scope)


# --- Drawing-local curve tessellation (offline, not exported-ink proof) ------


# --- Edge breaks: .06 where it fits, the title block's elsewhere -----------


def test_no_edge_reads_sharp_and_note_one_covers_only_the_drawn_breaks() -> None:
    """Owner ruling 2026-11-07: the SHARP leaders are gone and note 1 covers
    only the convex cast edges the views show chamfered; every edge the model
    leaves unbroken at .06 takes the title block's .010 break, so no note,
    flag or leader names one."""
    rows = spec.DRAWING_NOTES.splitlines()
    assert [row.split(".", 1)[0] for row in rows] == ["1", "2"]
    assert rows[0] == "1. CONVEX CAST EDGES .06 X 45° WHERE SHOWN."
    assert not hasattr(spec, "DRAWING_NOTE_FLAG")
    assert spec.EDGE_CHAMFER == pytest.approx(0.06 * 25.4)
    for text in ("UNLESS NOTED; NOT", "FLAGGED", "SLOT MOUTHS"):
        assert text not in spec.DRAWING_NOTES
    assert max(map(len, rows)) <= 64
    assert drawing.HUB_BOTTOM_TITLE == "VIEW L"
    # The rail pad's 28.0 line back where it stood before the rib's SHARP.
    assert drawing.RIB_WIDTH_LINE_XY == (0.350, 0.174)


def test_title_block_break_on_the_unbroken_edges_keeps_the_seats_and_reams() -> None:
    """The .010 break the title block puts on the edges the model leaves
    unbroken at .06 (the crossbar's front side bottoms and the gusset
    hypotenuses under the knife seats) stays inside the knife seats' 0.5
    edge-break clearance, and the reams' underside mouths keep their wall
    to the crossbar side inside it."""
    from _printed_tolerance import edge_break_chamfer_mm, edge_break_radius_mm

    worst = max(edge_break_radius_mm(unit="in"), edge_break_chamfer_mm(unit="in"))
    assert worst == pytest.approx(0.254)
    assert part.TITLE_BLOCK_EDGE_BREAK_MAX == pytest.approx(worst)
    assert part.TITLE_BLOCK_EDGE_BREAK_MAX < part.KNIFE_SEAT_EDGE_BREAK_MIN_CLEARANCE
    assert part.PIN_HOLE_MOUTH_BAR_WALL == pytest.approx(
        part._REAM_BAR_FACE_REACH - part.HANGER_PIN_HOLE_DIA_MAX / 2.0 - worst
    )
    assert part.PIN_HOLE_MOUTH_BAR_WALL >= part.WALL_TARGET_MM


def test_set_screw_boss_face_projects_past_the_east_boss_tangent() -> None:
    """Owner ruling B4 (#2333): the full-height set-screw boss's cast face
    stands .95 from the gooseneck axis on the faced top, .065 past the east
    corner bosses' tangent (Ø1.77 / 2 = .885).  Owner ruling D2 put datum G
    and the hole-table origin on the west barrel, so nothing locates on the
    east tangent."""
    assert part.GOOSENECK_X == pytest.approx(-part.COLUMN_X)
    assert part.SET_BOSS_FACE_TANGENT_MARGIN == pytest.approx(
        part.BOSS_DIA / 2.0 - part.HUB_SET_BOSS_FROM_AXIS
    )
    assert part.SET_BOSS_FACE_TANGENT_MARGIN / 25.4 == pytest.approx(-0.065)
    assert part.CAST_DATUM_TARGETS["G1"][0] > part.COLUMN_X
    assert drawing.TABLE_ORIGIN_XZ == part.CAST_DATUM_ORIGIN_XZ
    assert drawing.TABLE_ORIGIN_XZ[0] > part.COLUMN_X


def test_registry_row_records_the_casting_route():
    # Owner ruling 2026-11-10 (#2333, option a): gray-iron casting from a
    # printed pattern, machined on the seats; the steel alternative is gone.
    row = _config.parts("fr-top-frame")
    assert row["material"] == row["material_specification"] == (
        "GRAY IRON, ASTM A48 CLASS 25B"
    )
    assert "STEEL" not in row["material"]
    assert row["process"].startswith("gray iron casting from a 3D-printed pattern")
    assert part.MATERIAL == "Gray Cast Iron"
