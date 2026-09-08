"""Offline contracts for the harmonic-base drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import build_harmonic_base as part
import build_cone_swing_platform as platform
import draw_harmonic_base as drawing
import harmonic_base_spec
from cone_pivot_post_installation import (
    MECHANISM_X_SHIFT,
    MECHANISM_Z_SHIFT,
    POST_X_SHIFT,
    POST_Z_SHIFT,
)
from build_cone_lock_knob import COLLAR_DIA as KNOB_COLLAR_DIA
from _drawing_registry import DRAWINGS_BY_NAME
from build_swing_stop_screw import SHANK_DIA as STOP_SHANK_DIA


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/harmonic-base.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/harmonic-base.pdf")
    assert drawing.PNG.as_posix().endswith("/png/harmonic-base_drawing.png")
    assert DRAWINGS_BY_NAME["harmonic_base"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is harmonic_base_spec.DRAWING_DIMENSIONS
    marked = set().union(*harmonic_base_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.TOP_KEEP)
    assert kept == marked
    assert (drawing.BOTTOM_LENGTH, drawing.BOTTOM_WIDTH) == (
        harmonic_base_spec.BOTTOM_LENGTH,
        harmonic_base_spec.BOTTOM_WIDTH,
    )


def test_plate_geometry_is_single_sourced() -> None:
    # The build imports its plate nominals from the spec, so the drawing's view
    # math and the part geometry cannot drift.
    assert part.BOTTOM_LENGTH is harmonic_base_spec.BOTTOM_LENGTH
    assert part.TOP_THICKNESS is harmonic_base_spec.TOP_THICKNESS
    assert harmonic_base_spec.BOTTOM_LENGTH == 18.0 * 25.4
    assert harmonic_base_spec.TOP_LENGTH == 17.5 * 25.4
    assert harmonic_base_spec.BOTTOM_FRONT_Z == -(11.0 * 25.4) / 2.0
    assert harmonic_base_spec.BOTTOM_REAR_Z == (11.0 * 25.4) / 2.0
    assert math.isclose(harmonic_base_spec.BOTTOM_WIDTH, 11.0 * 25.4)
    assert math.isclose(harmonic_base_spec.TOP_WIDTH, 10.5 * 25.4)


def test_hole_table_covers_mounting_holes_and_every_hardware_seat() -> None:
    expected_holes = {
        *((x, z, part.HOLE_DIA) for x, z in part.HOLE_XZ),
        (*part.PIVOT_SCREW_XZ, part.PIVOT_SCREW_HOLE_DIA),
        (*part.LOCK_KNOB_XZ, part.LOCK_SCREW_HOLE_DIA),
        (*part.STOP_SCREW_XZ, part.STOP_SCREW_HOLE_DIA),
        *((x, z, part.BLOCK_SCREW_HOLE_DIA) for x, z in part.BLOCK_SCREW_XZ),
        *((x, z, part.FOOT_SCREW_HOLE_DIA) for x, z in part.FOOT_SCREW_XZ),
        *((x, z, part.NAMEPLATE_SCREW_HOLE_DIA) for x, z in part.NAMEPLATE_SCREW_XZ),
    }
    # Four lag counterbores and all six tapped groups, with no duplicate picks.
    assert len(drawing.ALL_HOLES) == len(expected_holes) == 18
    assert set(drawing.ALL_HOLES) == expected_holes
    assert drawing._plan_xy(0.0, 10.0)[1] < drawing.TOP_CENTER[1]
    assert drawing.HOLE_TABLE_ANCHOR[0] >= 0.274


def test_plan_view_clears_top_border_and_lower_notes() -> None:
    assert drawing.TOP_CENTER == (0.130, 0.163)


def test_blind_taps_have_drill_and_tap_runout_clearance() -> None:
    for spec in (
        part.LOCK_SEAT_SPEC,
        part.STOP_SEAT_SPEC,
        part.BLOCK_SEAT_SPEC,
        part.FOOT_SEAT_SPEC,
        part.NAMEPLATE_SEAT_SPEC,
    ):
        thread_depth = spec.overrides_mm["ThreadDepth"]
        assert spec.depth_mm - thread_depth >= 0.25


def test_nameplate_seats_are_derived_from_the_plate_mount() -> None:
    """The four #4-40 taps sit under the plate's corner holes carried through
    its mount transform (nameplate_spec), cut from the deck the plate lies on."""
    import nameplate_spec
    from build_fillister_screw import HEAD_DIA, SHANK_DIA, SHANK_LEN, THREAD
    from build_nameplate import SCREW_HOLE_DIA

    assert part.NAMEPLATE_SEAT_SPEC.kind == "tapped"
    assert part.NAMEPLATE_SEAT_SPEC.size == THREAD == "#4-40"
    assert part.NAMEPLATE_SEAT_SPEC.end == "blind"
    assert part.NAMEPLATE_SEAT_SPEC.thread_class == "2B"
    assert part.NAMEPLATE_SCREW_HOLE_DIA == pytest.approx(2.261)
    # Stock external threads engage the tap; only the plate is a clearance fit.
    assert SHANK_DIA == pytest.approx(2.8448)
    assert part.NAMEPLATE_SCREW_HOLE_DIA < SHANK_DIA < SCREW_HOLE_DIA < HEAD_DIA
    # Plate back face ON the deck (gap 0) and cut from the deck's +Y face.
    assert nameplate_spec.MOUNT_BACK_Y == pytest.approx(harmonic_base_spec.STACK_HEIGHT)
    assert nameplate_spec.MOUNT_NORMAL == (0.0, 1.0, 0.0)
    assert part.NAMEPLATE_SCREW_XZ == nameplate_spec.MOUNT_HOLE_XZ
    assert set(part.NAMEPLATE_SCREW_XZ) == {
        (209.75, 45.5),
        (209.75, -45.5),
        (163.75, 45.5),
        (163.75, -45.5),
    }
    # No mechanism shift applies (the plate anchors to the pad edge): the
    # stations are the pure mount-transform image of the plate holes.
    assert part.NAMEPLATE_SCREW_XZ == tuple(
        (nameplate_spec.MOUNT_POS[0] - y, nameplate_spec.MOUNT_POS[2] - x)
        for x, y in nameplate_spec.SCREW_XY
    )
    # Inside the raised rim's inner wall by >= 1.0.
    assert part.NAMEPLATE_RIM_CLEARANCE == pytest.approx(1.0)
    # The purchased 1/4-inch screw passes through the plate without bottoming
    # in the usable thread, independently of the deeper tap-drill runout.
    engagement = SHANK_LEN - nameplate_spec.PLATE_THICKNESS
    assert engagement == pytest.approx(4.85)
    assert engagement >= SHANK_DIA
    thread_depth = part.NAMEPLATE_SEAT_SPEC.overrides_mm["ThreadDepth"]
    assert thread_depth - engagement >= 0.5
    assert part.NAMEPLATE_SEAT_SPEC.depth_mm - engagement >= 0.75


def test_v2_platform_swing_stop_coordinate_is_rederived() -> None:
    """Mirror the drive-train formula without importing its COM-heavy graph."""
    pivot_x, pivot_z = part.PIVOT_SCREW_XZ
    assert part.PIVOT_SCREW_XZ == (
        -89.16663981674521 + POST_X_SHIFT,
        60.60437088764276 + POST_Z_SHIFT,
    )
    assert part.STOP_SCREW_XZ == part.SWING_HARDWARE_GEOMETRY.stop_xz
    east_slope = (platform.EAST_HALF_S - platform.HALF_WIDTH_N) / platform.PLATE_LEN
    stop_local_z = -105.0
    stop_local_x = -(
        platform.HALF_WIDTH_N + east_slope * (platform.NORTH_OVERHANG - stop_local_z)
    )

    edge_x, edge_z = -1.0, east_slope
    edge_norm = math.hypot(edge_x, edge_z)
    edge_x, edge_z = edge_x / edge_norm, edge_z / edge_norm
    disengage_rad = (
        platform.NOTCH_EXIT_TRAVEL + KNOB_COLLAR_DIA / 2.0 + 2.0
    ) / platform.SLOT_R
    angle = math.radians(platform.INCLINE_DEG) + disengage_rad
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    contact_x = pivot_x + stop_local_x * cos_a + stop_local_z * sin_a
    contact_z = pivot_z - stop_local_x * sin_a + stop_local_z * cos_a
    normal_x = edge_x * cos_a + edge_z * sin_a
    normal_z = -edge_x * sin_a + edge_z * cos_a
    derived = (
        contact_x + normal_x * STOP_SHANK_DIA / 2.0,
        contact_z + normal_z * STOP_SHANK_DIA / 2.0,
    )

    assert math.isclose(
        math.degrees(disengage_rad), part.SWING_HARDWARE_GEOMETRY.disengage_deg
    )
    assert math.isclose(derived[0], part.STOP_SCREW_XZ[0], abs_tol=1e-12)
    assert math.isclose(derived[1], part.STOP_SCREW_XZ[1], abs_tol=1e-12)

    engaged = math.radians(platform.INCLINE_DEG)
    cos_e, sin_e = math.cos(engaged), math.sin(engaged)
    edge_point_x = pivot_x + stop_local_x * cos_e + stop_local_z * sin_e
    edge_point_z = pivot_z - stop_local_x * sin_e + stop_local_z * cos_e
    engaged_normal = (
        edge_x * cos_e + edge_z * sin_e,
        -edge_x * sin_e + edge_z * cos_e,
    )
    stop_delta = (
        derived[0] - edge_point_x,
        derived[1] - edge_point_z,
    )
    engaged_gap = (
        stop_delta[0] * engaged_normal[0]
        + stop_delta[1] * engaged_normal[1]
        - STOP_SHANK_DIA / 2.0
    )
    assert engaged_gap >= 2.0
    assert math.isclose(engaged_gap, part.SWING_HARDWARE_GEOMETRY.stop_engaged_gap)


def test_v2_structural_holes_follow_the_same_installation_delta() -> None:
    # 2026-09 short-strap pinion rig: blocks at machine x -5.863 +/- 13.5,
    # spring foot screw at 7.486 (build_drive_train_assembly derives both).
    former_blocks = (
        (-13.669764612476252, -98.0),
        (13.33023538752375, -98.0),
        (-13.669764612476252, 82.0),
        (13.33023538752375, 82.0),
    )
    former_feet = (
        (13.179270253802283, 70.95),
        (-54.7, -95.5),
        (-54.7, 102.5),
    )
    assert part.BLOCK_SCREW_XZ == tuple(
        (x + MECHANISM_X_SHIFT, z + MECHANISM_Z_SHIFT) for x, z in former_blocks
    )
    assert part.FOOT_SCREW_XZ == tuple(
        (x + MECHANISM_X_SHIFT, z + MECHANISM_Z_SHIFT) for x, z in former_feet
    )
