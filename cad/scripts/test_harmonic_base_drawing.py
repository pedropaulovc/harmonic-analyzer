"""Offline contracts for the harmonic-base drawing."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

import build_harmonic_base as part
import cone_swing_platform_geometry as platform
import cone_pivot_post_installation
import cone_line
import harmonic_base_spec
from cone_pivot_post_installation import (
    MECHANISM_X_SHIFT,
    MECHANISM_Z_SHIFT,
)
from cone_lock_knob_spec import COLLAR_DIA as KNOB_COLLAR_DIA
from swing_stop_screw_spec import SHANK_DIA as STOP_SHANK_DIA


@pytest.mark.parametrize(
    ("seat", "engagement", "kind", "lead_pitches"),
    (
        (
            part.HOLD_DOWN_SEAT_SPEC,
            part.HOLD_DOWN_ENGAGEMENT,
            "tapped",
            5,
        ),
        (part.PIVOT_SEAT_SPEC, part.PIVOT_THREAD_ENGAGEMENT, "tapped_bottoming", 2),
        (part.LOCK_SEAT_SPEC, part.LOCK_STUD_LEN, "tapped", 5),
        (part.STOP_SEAT_SPEC, part.STOP_ENGAGEMENT, "tapped", 5),
        (
            part.BLOCK_SEAT_SPEC,
            part.BLOCK_SCREW_LEN - part.BLOCK_HEIGHT,
            "tapped_bottoming",
            2,
        ),
        (
            part.FOOT_SEAT_SPEC,
            part.FOOT_SCREW_LEN - part.SPRING_THICKNESS,
            "tapped_bottoming",
            2,
        ),
        (
            part.PEDESTAL_SEAT_SPEC,
            part.PEDESTAL_SCREW_ENGAGEMENT,
            "tapped_bottoming",
            2,
        ),
        (
            part.NAMEPLATE_SEAT_SPEC,
            part.NAMEPLATE_SCREW_LEN - part.nameplate_spec.PLATE_THICKNESS,
            "tapped_bottoming",
            2,
        ),
    ),
)
def test_blind_seats_keep_stock_in_full_threads_above_the_tap_lead(
    seat, engagement: float, kind: str, lead_pitches: int
) -> None:
    assert seat.kind == kind
    part.require_blind_seat_fit("stock fit", seat, engagement)
    thread_depth = seat.overrides_mm["ThreadDepth"]
    pitch = 25.4 / float(seat.size.rsplit("-", 1)[1])
    assert thread_depth - engagement >= 0.25 - 1e-9
    assert seat.depth_mm - thread_depth >= lead_pitches * pitch - 1e-9
    # A drill that loses just 0.01 mm of the required tooling lead is invalid
    # even though the unchanged stock screw still clears the full threads.
    short_lead = replace(seat, depth_mm=thread_depth + lead_pitches * pitch - 0.01)
    with pytest.raises(AssertionError, match="tap lead"):
        part.require_blind_seat_fit("short lead", short_lead, engagement)


def test_pivot_rejects_former_full_threads_to_drill_bottom() -> None:
    old_seat = replace(
        part.PIVOT_SEAT_SPEC, kind="tapped", depth_mm=11.525, overrides_mm={}
    )
    with pytest.raises(AssertionError, match="plug-tap lead"):
        part.require_blind_seat_fit(
            "former pivot", old_seat, part.PIVOT_THREAD_ENGAGEMENT
        )


def test_pivot_rejects_stock_bottoming_despite_ample_drill_depth() -> None:
    seat = replace(
        part.PIVOT_SEAT_SPEC,
        overrides_mm={"ThreadDepth": part.PIVOT_THREAD_ENGAGEMENT},
    )
    with pytest.raises(AssertionError, match="bottoms"):
        part.require_blind_seat_fit("pivot", seat, part.PIVOT_THREAD_ENGAGEMENT)


@pytest.mark.parametrize("tip_reserve", (0.0, -0.25, math.nan, math.inf))
def test_base_seat_rejects_nonphysical_tip_reserve(tip_reserve: float) -> None:
    with pytest.raises(AssertionError, match="tip reserve"):
        part.require_blind_seat_fit(
            "pivot",
            part.PIVOT_SEAT_SPEC,
            part.PIVOT_THREAD_ENGAGEMENT,
            tip_reserve=tip_reserve,
        )


def test_pivot_drill_keeps_its_point_inside_the_pad_and_clear_of_cavities() -> None:
    from _holes import DRILL_POINT_H, blind_hole_volume_mm3

    assert part.PIVOT_SEAT_SPEC.overrides_mm["ThreadDepth"] == pytest.approx(9.775)
    assert part.PIVOT_SEAT_SPEC.depth_mm == pytest.approx(12.0)
    radius = part.PIVOT_SCREW_HOLE_DIA / 2.0
    assert part.PIVOT_DRILL_BOTTOM_WALL == pytest.approx(
        part.TOP_THICKNESS - part.PIVOT_SEAT_SPEC.depth_mm - radius * DRILL_POINT_H
    )
    assert part.PIVOT_DRILL_BOTTOM_WALL >= 1.5 * part.PIVOT_SCREW_HOLE_DIA
    assert part.PIVOT_NEAREST_CAVITY_WALL >= part.PIVOT_SCREW_HOLE_DIA
    # Only the pivot cylinder grows: its same-diameter terminal point cancels.
    assert blind_hole_volume_mm3(
        part.PIVOT_SCREW_HOLE_DIA, part.PIVOT_SEAT_SPEC.depth_mm
    ) - blind_hole_volume_mm3(part.PIVOT_SCREW_HOLE_DIA, 11.525) == pytest.approx(
        math.pi * radius**2 * 0.475
    )


def test_cone_lock_seats_on_plate_and_bare_base_with_useful_threads() -> None:
    import cone_lock_knob_spec as knob
    from _holes import DRILL_POINT_H, blind_hole_volume_mm3

    knob.require_seat_fit(part.LOCK_SEAT_SPEC, platform.PLATE_T, knob.STUD_LEN)
    assert knob.STUD_LEN - platform.PLATE_T == pytest.approx(12.7)
    assert knob.STUD_LEN - platform.PLATE_T - knob.TIP_CHAMFER >= 1.5 * knob.STUD_DIA
    assert part.LOCK_SEAT_SPEC.overrides_mm["ThreadDepth"] - knob.STUD_LEN >= 0.25
    assert part.LOCK_SEAT_SPEC.depth_mm == pytest.approx(25.65)
    drill_tip_depth = (
        part.LOCK_SEAT_SPEC.depth_mm + part.LOCK_SCREW_HOLE_DIA / 2.0 * DRILL_POINT_H
    )
    assert part.TOP_THICKNESS - drill_tip_depth >= 1.5 * part.LOCK_SCREW_HOLE_DIA
    assert part.LOCK_NEAREST_CAVITY_WALL >= part.LOCK_SCREW_HOLE_DIA
    # Volume includes the added drilling length AND its terminal point.
    radius = part.LOCK_SCREW_HOLE_DIA / 2.0
    assert blind_hole_volume_mm3(
        part.LOCK_SCREW_HOLE_DIA, part.LOCK_SEAT_SPEC.depth_mm
    ) == pytest.approx(math.pi * radius**2 * (25.65 + radius * DRILL_POINT_H / 3.0))


def test_cone_lock_rejects_short_stock_even_in_a_deep_receiver() -> None:
    import cone_lock_knob_spec as knob

    with pytest.raises(AssertionError, match="useful thread engagement"):
        knob.require_seat_fit(part.LOCK_SEAT_SPEC, platform.PLATE_T, 7.9375)


def test_cone_lock_rejects_a_receiver_that_only_clears_the_plate_pose() -> None:
    import cone_lock_knob_spec as knob
    from dataclasses import replace

    seat = replace(
        part.LOCK_SEAT_SPEC,
        overrides_mm={"ThreadDepth": knob.STUD_LEN - platform.PLATE_T + 0.25},
    )
    with pytest.raises(AssertionError, match="collar seats"):
        knob.require_seat_fit(seat, platform.PLATE_T, knob.STUD_LEN)


def test_cone_lock_requires_plug_tap_lead_beyond_full_thread_depth() -> None:
    import cone_lock_knob_spec as knob
    from dataclasses import replace

    seat = replace(
        part.LOCK_SEAT_SPEC,
        depth_mm=part.LOCK_SEAT_SPEC.overrides_mm["ThreadDepth"] + 0.25,
    )
    with pytest.raises(AssertionError, match="plug-tap lead"):
        knob.require_seat_fit(seat, platform.PLATE_T, knob.STUD_LEN)


def test_shared_stop_preserves_exposed_geometry_with_a_deeper_clear_seat() -> None:
    import swing_stop_screw_spec as stop

    stop.require_seat_fit(part.STOP_SEAT_SPEC, platform.PLATE_T)
    assert stop.PROUD_LEN == pytest.approx(9.875)
    assert stop.EMBED_LEN - stop.TIP_CHAMFER >= stop.SHANK_DIA
    assert stop.PROUD_LEN - platform.PLATE_T - stop.UNDERHEAD_FILLET - 0.51 >= 1.0
    assert part.STOP_SEAT_SPEC.overrides_mm["ThreadDepth"] - stop.EMBED_LEN >= 0.25
    assert part.STOP_DRILL_BOTTOM_WALL >= 1.5 * part.STOP_SCREW_HOLE_DIA
    assert part.STOP_NEAREST_CAVITY_WALL >= part.STOP_SCREW_HOLE_DIA


def test_shared_stop_rejects_the_former_shallow_receiver() -> None:
    from dataclasses import replace
    import swing_stop_screw_spec as stop

    seat = replace(part.STOP_SEAT_SPEC, depth_mm=9.0, overrides_mm={"ThreadDepth": 6.0})
    with pytest.raises(AssertionError, match="bottoms"):
        stop.require_seat_fit(seat, platform.PLATE_T)


def test_nameplate_seats_are_derived_from_the_plate_mount() -> None:
    """The four #4-40 taps sit under the plate's corner holes carried through
    its mount transform (nameplate_spec), cut from the deck the plate lies on."""
    import nameplate_spec
    from fillister_screw_spec import HEAD_DIA, SHANK_DIA, SHANK_LEN, THREAD
    from build_nameplate import SCREW_HOLE_DIA

    assert part.NAMEPLATE_SEAT_SPEC.kind == "tapped_bottoming"
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


def test_pivot_seat_reads_the_cone_line_pivot() -> None:
    """The seat is the cone line's pivot, bit-for-bit the former hand-shifted sum.

    The value reaches the part as a ``set_global`` string, so byte-identical
    geometry needs the exact repr, not a tolerance.
    """
    assert part.PIVOT_SCREW_XZ is cone_line.PIVOT_XZ
    assert repr(part.PIVOT_SCREW_XZ) == repr(
        (-89.16663981674521 + 1.484, 60.60437088764276 + 35.415)
    )
    assert not hasattr(cone_pivot_post_installation, "POST_X_SHIFT")
    assert not hasattr(cone_pivot_post_installation, "POST_Z_SHIFT")


def test_v2_platform_swing_stop_coordinate_is_rederived() -> None:
    """Mirror the drive-train formula without importing its COM-heavy graph."""
    pivot_x, pivot_z = part.PIVOT_SCREW_XZ
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
        platform.NOTCH_EXIT_TRAVEL + KNOB_COLLAR_DIA / 2.0 + platform.DISENGAGE_COLLAR_MARGIN
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
    # The 32T coherent-placement cutover shifts the block screws and spring
    # foot with the pinion rig while the arbor-pedestal seats stay on the
    # unchanged cylinder-drum axis.  U28 (2026-09-23): 2.2425 park-out, screws
    # +-8.5 about the pivot bore, block mid-depth 5.125 in from each outer face.
    # Ruling (c) (user, 2026-09-24): the block and spring-foot z stations come
    # from pinion_rig_layout -- the back block keeps its released seat, the
    # front block stands one feeler off the front strap, the spring rides with
    # the back strap.  The spring foot's seat is 20.0 east of the pivot bore
    # (the 2026-09-24 re-derive: outboard of the back strap, not west of it).
    import pinion_rig_layout as rig

    former_block_x = (-17.226441649810653, -0.22644164981065273)
    former_pivot_x = former_block_x[0] + 8.5
    former_feet = ((former_pivot_x - 20.0, rig.SPRING_Z - MECHANISM_Z_SHIFT),)
    assert part.BLOCK_SCREW_XZ == tuple(
        (x + MECHANISM_X_SHIFT, z) for z in rig.BLOCK_SEAT_Z for x in former_block_x
    )
    assert rig.BLOCK_SEAT_Z[1] == pytest.approx(82.875 + MECHANISM_Z_SHIFT)
    assert part.FOOT_SCREW_XZ == tuple(
        (x + MECHANISM_X_SHIFT, z + MECHANISM_Z_SHIFT) for x, z in former_feet
    )
    # U34c: the arbor pedestals left the #4-40 foot group for their own #8-32
    # seats, 19.0 outboard of each strap inner face on the unshifted drum axis.
    expected = ((-54.7 + MECHANISM_X_SHIFT, -91.652), (-54.7 + MECHANISM_X_SHIFT, 94.202))
    for actual, wanted in zip(part.PEDESTAL_SCREW_XZ, expected, strict=True):
        assert actual == pytest.approx(wanted)


def _socket_bore_geometry(x_mm: float, z_mm: float):
    """The bore wall's COM geometry signature, as measured on the built part.

    Faces read back one Ø25.50 cylinder per station whose bounding box spans
    the bore's own radius in X and Z and the socket depth in Y, so the specs
    can be resolved offline without a SolidWorks session.
    """
    from _part_pmi import _SURFACE_CYLINDER, _FaceGeometry

    radius = part.COLUMN_SOCKET_DIAMETER / 2000.0
    return _FaceGeometry(
        face=None,
        identity=_SURFACE_CYLINDER,
        parameters=(x_mm / 1000.0, 0.0, z_mm / 1000.0, 0.0, 1.0, 0.0, radius),
        outward_normal=None,
        box=(
            x_mm / 1000.0 - radius,
            (part.STACK_HEIGHT - part.COLUMN_SOCKET_DEPTH) / 1000.0,
            z_mm / 1000.0 - radius,
            x_mm / 1000.0 + radius,
            part.STACK_HEIGHT / 1000.0,
            z_mm / 1000.0 + radius,
        ),
    )


def test_each_socket_bore_finish_qualifies_exactly_one_station() -> None:
    """The four sockets differ only in X and Z, so a bore control that names
    less than both would qualify two faces (or all four) and abort the part
    build after ten minutes of cutting -- or, worse, print the seat grade
    against the wrong bore. Require a 1:1 station/control match, and hold the
    ambiguity the Z station exists to resolve."""
    from _gtol_spec import CylinderFace
    from _part_pmi import _face_matches

    spec = harmonic_base_spec
    geometries = {
        station: _socket_bore_geometry(*station) for station in spec.COLUMN_SOCKET_XZ
    }
    assert len(spec.SOCKET_BORE_FINISHES) == len(spec.COLUMN_SOCKET_XZ)
    for control in spec.SOCKET_BORE_FINISHES:
        matched = [
            station
            for station, geometry in geometries.items()
            if _face_matches(geometry, control.face)
        ]
        assert matched == [
            station
            for station in spec.COLUMN_SOCKET_XZ
            if spec.socket_bore_finish_key(*station) == control.key
        ]
        assert control.roughness_um == spec.SEAT_UM
        assert control.production_method == spec.SOCKET_BORE_TARGET
    x_only = CylinderFace(part.COLUMN_SOCKET_DIAMETER, contains_x_mm=part.COLUMN_X)
    size_only = CylinderFace(part.COLUMN_SOCKET_DIAMETER)
    assert sum(_face_matches(g, x_only) for g in geometries.values()) == 2
    assert sum(_face_matches(g, size_only) for g in geometries.values()) == 4


def test_socket_bore_leader_lands_on_bore_clear_of_the_cross_tap() -> None:
    """The sheet's one socket symbol leads to the INNER wall of the socket that
    section A-A puts in the upper half of the sheet, at a height that keeps the
    arrowhead inside the bore and clear of both the window the cross tap opens
    through that wall and the deck outline -- the first placement sat 1 mm (on
    paper) from the cross tap's cosmetic thread and read as the tap's."""
    import draw_harmonic_base as sheet

    x_mm, y_mm, z_mm = sheet.SOCKET_LEADER_POINT_MM
    station_x, station_z = sheet.SECTION_SOCKET_XZ
    assert (station_x, station_z) in part.COLUMN_SOCKET_XZ
    assert station_x == part.COLUMN_X
    assert station_z == min(z for x, z in part.COLUMN_SOCKET_XZ if x > 0.0)
    assert x_mm == part.COLUMN_X
    assert math.isclose(
        abs(z_mm - station_z), part.COLUMN_SOCKET_DIAMETER / 2.0, abs_tol=1e-9
    )
    assert abs(z_mm) < abs(station_z)
    tap_clearance = abs(y_mm - part.BASE_SCREW_Y) - part.BASE_CROSS_TAP_DRILL_DIA / 2.0
    deck_clearance = part.STACK_HEIGHT - y_mm
    assert min(tap_clearance, deck_clearance) > 4.0
    assert y_mm > part.STACK_HEIGHT - part.COLUMN_SOCKET_DEPTH


def test_transferred_pinion_block_seats_print_no_station() -> None:
    # Codex #855 P1: BLOCK_SEAT_Z is a model-pose station, and the pose's two
    # STRAP_AIR gaps stand the front block 2 x STRAP_AIR south of its
    # manufactured station -- more than a #8 floats in its clearance hole.
    # That is harmless only because the print never carries the station: the
    # four block seats are spotted THROUGH MHA-061 at assembly (U28 corollary;
    # MHA-061's note "SPOT BASE SEATS THROUGH BLOCK HOLES AT ASSEMBLY."), so
    # they leave the hole table and their one callout names the transfer.
    import draw_harmonic_base as sheet
    import pinion_rig_layout as rig
    from pinion_pivot_block_geometry import BLOCK_DEPTH

    block_seats = {(x, z, part.BLOCK_SCREW_HOLE_DIA) for x, z in part.BLOCK_SCREW_XZ}
    assert set(sheet.TRANSFER_BLOCK_HOLES) == block_seats
    assert not block_seats & set(sheet.TABLE_HOLES)
    assert sheet.TRANSFER_BLOCK_CALLOUT.startswith("TRANSFER FROM MHA-061")
    assert "AT ASSEMBLY" in sheet.TRANSFER_BLOCK_CALLOUT
    # The front pair's pose-vs-hardware offset the transfer absorbs.
    physical_front_seat = rig.PHYSICAL_FRONT_BLOCK_OUTER_Z + BLOCK_DEPTH / 2.0
    assert physical_front_seat - rig.BLOCK_SEAT_Z[0] == pytest.approx(
        2.0 * rig.STRAP_AIR
    )


def test_transferred_pedestal_and_spring_seats_print_no_station() -> None:
    # U34c (I27): each arbor pedestal is stood on the base with the arbor in
    # both straps and its #8-32 seat is spotted through the MHA-004 ledge
    # hole, so the pair leaves the hole table like the pinion-block seats. The
    # spring-foot seat, now alone on its #4-40 feature, takes a native callout
    # instead of a note naming a table row that no longer exists.
    import draw_harmonic_base as sheet

    pedestal_seats = {
        (x, z, part.PEDESTAL_SCREW_HOLE_DIA) for x, z in part.PEDESTAL_SCREW_XZ
    }
    assert set(sheet.TRANSFER_PEDESTAL_HOLES) == pedestal_seats
    assert sheet.TRANSFER_SPRING_HOLE[:2] == part.FOOT_SCREW_XZ[0]
    assert not (pedestal_seats | {sheet.TRANSFER_SPRING_HOLE}) & set(sheet.TABLE_HOLES)
    assert sheet.TRANSFER_PEDESTAL_CALLOUT == "TRANSFER FROM MHA-004\nAT ASSEMBLY;"
    assert sheet.TRANSFER_SPRING_CALLOUT == "TRANSFER FROM MHA-114\nAT ASSEMBLY;"
    assert not any(tag.startswith("G") for tag in sheet.HOLE_TAG_POSITIONS)
