"""Offline contracts for the top-frame geometry and drawing."""

from __future__ import annotations

import math

import _config
import fulcrum_keeper_spec as keeper
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES
import build_top_frame as part
from frame_attachment_spec import (
    CAP_MOUTH_Y,
    CAP_RECESS_DEPTH,
    CAP_RECESS_DIAMETER,
    CASTING_FULL_THREAD_DEPTH,
    CASTING_TAP_DRILL_DEPTH,
    COLUMN_SOCKET_DIAMETER,
    TOP_SCREW_SEAT_Z,
    TOP_SCREW_Y,
    TUBE_CROSS_HOLE_DIAMETER,
)
from tube_frame_cap_spec import MAX_OUTER_DIAMETER
import tube_frame_spec


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
        part.BORE_DIA - tube_frame_spec.OUTER_DIA,
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
    assert part.SIDE_TAP_SPEC.depth_mm == CASTING_TAP_DRILL_DEPTH
    assert part.SIDE_TAP_SPEC.overrides_mm["ThreadDepth"] == CASTING_FULL_THREAD_DEPTH
    pitch = 25.4 / 32.0
    assert CASTING_TAP_DRILL_DEPTH - CASTING_FULL_THREAD_DEPTH >= 2.0 * pitch
    assert part.SPOTFACE_FLOOR == TOP_SCREW_SEAT_Z
    full_seat_limit = abs(part.FRONT_COLUMN_Z) + math.sqrt(
        (part.BOSS_DIA / 2.0) ** 2 - (part.SPOTFACE_DIA / 2.0) ** 2
    )
    assert part.SPOTFACE_FLOOR < full_seat_limit


def test_cross_tap_major_thread_and_drill_point_clear_the_far_wall() -> None:
    # The major-thread envelope, not the tap-drill cylinder, is the finished
    # thread breakout check.  The drill point has its own positive-wall guard.
    major_dia = 4.826
    major_far_wall_z = abs(part.FRONT_COLUMN_Z) - math.sqrt(
        (part.BOSS_DIA / 2.0) ** 2 - (major_dia / 2.0) ** 2
    )
    thread_end_z = part.SPOTFACE_FLOOR - CASTING_FULL_THREAD_DEPTH
    drill_point_z = (
        part.SPOTFACE_FLOOR
        - CASTING_TAP_DRILL_DEPTH
        - part.SIDE_TAP_DRILL_DIA / 2.0 * part.DRILL_POINT_H
    )
    drill_far_wall_z = abs(part.FRONT_COLUMN_Z) - part.BOSS_DIA / 2.0
    assert part.SIDE_TAP_THREAD_MAJOR_DIA == major_dia
    assert part.SIDE_TAP_MAJOR_FAR_WALL_Z == major_far_wall_z
    assert part.SIDE_TAP_THREAD_END_Z == thread_end_z
    assert part.SIDE_TAP_DRILL_POINT_Z == drill_point_z
    assert part.SIDE_TAP_DRILL_FAR_WALL_Z == drill_far_wall_z
    assert part.SIDE_TAP_THREAD_WALL_MARGIN > 0.0
    assert part.SIDE_TAP_DRILL_WALL_MARGIN > 0.0


def test_keeper_tap_holds_stock_screw_above_a_plug_tap_lead() -> None:
    major, length, _, _, pitch = FILLISTER_SIZES["90280A194"]
    insertion = length - (keeper.FOOT_H - keeper.CBORE_DEPTH_MM)
    spec = part.KEEPER_TAP_SPEC
    full_thread = spec.overrides_mm.get("ThreadDepth", spec.depth_mm)
    depth_tolerance = float(_config.title_block("linear_2pl")["value_in"]) * 25.4

    assert insertion >= major
    assert full_thread - insertion >= 0.25
    assert spec.depth_mm - full_thread - 2.0 * depth_tolerance >= 5.0 * pitch
    drill_point = part.TAP_DRILL_MM[spec.size] / 2.0 * part.DRILL_POINT_H
    assert spec.depth_mm + depth_tolerance + drill_point < part.RING_HEIGHT
    assert abs(part.KEEPER_TAP_X - part.COLUMN_X) + major / 2.0 < part.WEB_T / 2.0
