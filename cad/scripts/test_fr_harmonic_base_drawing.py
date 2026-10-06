"""Offline contracts for the harmonic-base drawing."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

import build_fr_harmonic_base as part
import dt_cone_swing_platform_geometry as platform
import dt_cone_pivot_post_installation
import cone_line
import fr_harmonic_base_spec
from dt_cone_pivot_post_installation import (
    MECHANISM_X_SHIFT,
    MECHANISM_Z_SHIFT,
)
from vn_cone_lock_knob_spec import HEAD_DIA as KNOB_HEAD_DIA
from vn_swing_stop_screw_spec import CONTACT_DIA as STOP_CONTACT_DIA


@pytest.mark.parametrize(
    ("label", "seat", "engagement", "kind", "lead_pitches"),
    (
        (
            "rocker support",
            part.HOLD_DOWN_SEAT_SPEC,
            part.HOLD_DOWN_ENGAGEMENT,
            "tapped",
            5,
        ),
        ("cone pivot", part.PIVOT_SEAT_SPEC, part.PIVOT_THREAD_ENGAGEMENT, "tapped_bottoming", 2),
        ("cone lock", part.LOCK_SEAT_SPEC, part.LOCK_STUD_LEN, "tapped", 5),
        ("swing stop", part.STOP_SEAT_SPEC, part.STOP_ENGAGEMENT, "tapped", 5),
        (
            "pinion block",
            part.BLOCK_SEAT_SPEC,
            part.BLOCK_SCREW_LEN - part.BLOCK_HEIGHT,
            "tapped_bottoming",
            2,
        ),
        (
            "spring foot",
            part.FOOT_SEAT_SPEC,
            part.FOOT_SCREW_LEN - part.SPRING_THICKNESS_MIN,
            "tapped_bottoming",
            2,
        ),
        (
            "pedestal hold-down",
            part.PEDESTAL_SEAT_SPEC,
            part.PEDESTAL_SCREW_ENGAGEMENT,
            "tapped_bottoming",
            2,
        ),
        (
            "fr-nameplate",
            part.NAMEPLATE_SEAT_SPEC,
            part.NAMEPLATE_SCREW_LEN - part.fr_nameplate_spec.PLATE_THICKNESS,
            "tapped_bottoming",
            2,
        ),
    ),
)
def test_blind_seats_keep_stock_in_full_threads_above_the_tap_lead(
    label: str, seat, engagement: float, kind: str, lead_pitches: int
) -> None:
    assert seat.kind == kind
    part.require_blind_seat_fit(label, seat, engagement)
    band = part.SEAT_DEPTH_BAND
    thread_depth = seat.overrides_mm["ThreadDepth"]
    pitch = 25.4 / float(seat.size.rsplit("-", 1)[1])
    # Both printed depths at the worst case of their .XX band.
    assert thread_depth - band - engagement >= 0.25 - 1e-9
    assert seat.depth_mm - band - (thread_depth + band) >= lead_pitches * pitch - 1e-9
    # A drill that loses just 0.01 mm of the required tooling lead is invalid
    # even though the unchanged stock screw still clears the full threads.
    short_lead = replace(
        seat, depth_mm=thread_depth + 2.0 * band + lead_pitches * pitch - 0.01
    )
    with pytest.raises(AssertionError, match="tap lead"):
        part.require_blind_seat_fit(label, short_lead, engagement)


def test_foot_seat_names_its_bottoming_tap_runout() -> None:
    # Main (#859 restricted review, change 6): the foot seat's drill runs a
    # bottoming-tap runout past its full threads, at least two pitches.  On
    # integ every base seat sizes that runout through the shared
    # harmonic_base_fasteners.seat_drill_depth, which also books both depths'
    # printed band; the foot seat must take it from there.
    pitch = 25.4 / 40.0  # #4-40
    runout = part.FOOT_SCREW_DRILL_DEPTH - part.FOOT_SCREW_HOLE_DEPTH
    assert runout >= 2.0 * pitch + 2.0 * part.SEAT_DEPTH_BAND - 1e-9
    assert part.FOOT_SCREW_DRILL_DEPTH == pytest.approx(
        part.seat_drill_depth(part.FOOT_SCREW_HOLE_DEPTH, "#4-40", "tapped_bottoming")
    )


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

    assert part.PIVOT_SEAT_SPEC.overrides_mm["ThreadDepth"] == pytest.approx(10.30)
    assert part.PIVOT_SEAT_SPEC.depth_mm == pytest.approx(13.45)
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
        math.pi * radius**2 * (13.45 - 11.525)
    )


def test_cone_lock_seats_on_plate_and_bare_base_with_useful_threads() -> None:
    import vn_cone_lock_knob_spec as knob
    from _holes import DRILL_POINT_H, blind_hole_volume_mm3

    knob.require_seat_fit(part.LOCK_SEAT_SPEC, platform.PLATE_T, knob.STUD_LEN)
    assert knob.STUD_LEN - platform.PLATE_T == pytest.approx(12.7)
    assert knob.STUD_LEN - platform.PLATE_T - knob.TIP_CHAMFER >= 1.5 * knob.STUD_DIA
    assert part.LOCK_SEAT_SPEC.overrides_mm["ThreadDepth"] - knob.STUD_LEN >= 0.25
    assert part.LOCK_SEAT_SPEC.depth_mm == pytest.approx(27.25)
    drill_tip_depth = (
        part.LOCK_SEAT_SPEC.depth_mm + part.LOCK_SCREW_HOLE_DIA / 2.0 * DRILL_POINT_H
    )
    assert part.TOP_THICKNESS - drill_tip_depth >= 1.5 * part.LOCK_SCREW_HOLE_DIA
    assert part.LOCK_NEAREST_CAVITY_WALL >= part.LOCK_SCREW_HOLE_DIA
    # Volume includes the added drilling length AND its terminal point.
    radius = part.LOCK_SCREW_HOLE_DIA / 2.0
    assert blind_hole_volume_mm3(
        part.LOCK_SCREW_HOLE_DIA, part.LOCK_SEAT_SPEC.depth_mm
    ) == pytest.approx(math.pi * radius**2 * (27.25 + radius * DRILL_POINT_H / 3.0))


def test_cone_lock_rejects_short_stock_even_in_a_deep_receiver() -> None:
    import vn_cone_lock_knob_spec as knob

    with pytest.raises(AssertionError, match="useful thread engagement"):
        knob.require_seat_fit(part.LOCK_SEAT_SPEC, platform.PLATE_T, 7.9375)


def test_cone_lock_rejects_a_receiver_that_only_clears_the_plate_pose() -> None:
    import vn_cone_lock_knob_spec as knob
    from dataclasses import replace

    seat = replace(
        part.LOCK_SEAT_SPEC,
        overrides_mm={"ThreadDepth": knob.STUD_LEN - platform.PLATE_T + 0.25},
    )
    with pytest.raises(AssertionError, match="head seats"):
        knob.require_seat_fit(seat, platform.PLATE_T, knob.STUD_LEN)


def test_cone_lock_requires_plug_tap_lead_beyond_full_thread_depth() -> None:
    import vn_cone_lock_knob_spec as knob
    from dataclasses import replace

    seat = replace(
        part.LOCK_SEAT_SPEC,
        depth_mm=part.LOCK_SEAT_SPEC.overrides_mm["ThreadDepth"] + 0.25,
    )
    with pytest.raises(AssertionError, match="plug-tap lead"):
        knob.require_seat_fit(seat, platform.PLATE_T, knob.STUD_LEN)


def test_stop_head_seats_on_the_base_inside_the_platform_edge() -> None:
    import vn_foot_screw_spec as foot
    import vn_swing_stop_screw_spec as stop

    stop.require_seat_fit(part.STOP_SEAT_SPEC, platform.PLATE_T)
    # One SKU with the foot screw, screwed fully home so the head is the stop
    # (user, 2026-09-29).
    assert (stop.THREAD, stop.SHANK_LEN) == (foot.THREAD, foot.SHANK_LEN)
    assert stop.PROUD_LEN == 0.0
    assert stop.CONTACT_DIA == stop.HEAD_DIA
    assert stop.EMBED_LEN - stop.TIP_CHAMFER >= stop.SHANK_DIA
    assert stop.HEAD_H <= platform.PLATE_T - 0.508
    assert part.STOP_SEAT_SPEC.overrides_mm["ThreadDepth"] - stop.EMBED_LEN >= 0.25
    assert part.STOP_DRILL_BOTTOM_WALL >= 1.5 * part.STOP_SCREW_HOLE_DIA
    assert part.STOP_NEAREST_CAVITY_WALL >= part.STOP_SCREW_HOLE_DIA


def test_shared_stop_rejects_the_former_shallow_receiver() -> None:
    from dataclasses import replace
    import vn_swing_stop_screw_spec as stop

    seat = replace(part.STOP_SEAT_SPEC, depth_mm=13.0, overrides_mm={"ThreadDepth": 9.6})
    with pytest.raises(AssertionError, match="bottoms"):
        stop.require_seat_fit(seat, platform.PLATE_T)


def test_nameplate_seats_are_derived_from_the_plate_mount() -> None:
    """The four #4-40 taps sit under the plate's corner holes carried through
    its mount transform (nameplate_spec), cut from the deck the plate lies on."""
    import fr_nameplate_spec
    from vn_fillister_screw_spec import HEAD_DIA, SHANK_DIA, SHANK_LEN, THREAD
    from build_fr_nameplate import SCREW_HOLE_DIA

    assert part.NAMEPLATE_SEAT_SPEC.kind == "tapped_bottoming"
    assert part.NAMEPLATE_SEAT_SPEC.size == THREAD == "#4-40"
    assert part.NAMEPLATE_SEAT_SPEC.end == "blind"
    assert part.NAMEPLATE_SEAT_SPEC.thread_class == "2B"
    assert part.NAMEPLATE_SCREW_HOLE_DIA == pytest.approx(2.261)
    # Stock external threads engage the tap; only the plate is a clearance fit.
    assert SHANK_DIA == pytest.approx(2.8448)
    assert part.NAMEPLATE_SCREW_HOLE_DIA < SHANK_DIA < SCREW_HOLE_DIA < HEAD_DIA
    # Plate back face ON the deck (gap 0) and cut from the deck's +Y face.
    assert fr_nameplate_spec.MOUNT_BACK_Y == pytest.approx(fr_harmonic_base_spec.STACK_HEIGHT)
    assert fr_nameplate_spec.MOUNT_NORMAL == (0.0, 1.0, 0.0)
    assert part.NAMEPLATE_SCREW_XZ == fr_nameplate_spec.MOUNT_HOLE_XZ
    assert set(part.NAMEPLATE_SCREW_XZ) == {
        (209.75, 45.5),
        (209.75, -45.5),
        (163.75, 45.5),
        (163.75, -45.5),
    }
    # No mechanism shift applies (the plate anchors to the pad edge): the
    # stations are the pure mount-transform image of the plate holes.
    assert part.NAMEPLATE_SCREW_XZ == tuple(
        (fr_nameplate_spec.MOUNT_POS[0] - y, fr_nameplate_spec.MOUNT_POS[2] - x)
        for x, y in fr_nameplate_spec.SCREW_XY
    )
    # Inside the raised rim's inner wall by >= 1.0.
    assert part.NAMEPLATE_RIM_CLEARANCE == pytest.approx(1.0)
    # The purchased 1/4-inch screw passes through the plate without bottoming
    # in the usable thread, independently of the deeper tap-drill runout.
    engagement = SHANK_LEN - fr_nameplate_spec.PLATE_THICKNESS
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
    assert not hasattr(dt_cone_pivot_post_installation, "POST_X_SHIFT")
    assert not hasattr(dt_cone_pivot_post_installation, "POST_Z_SHIFT")


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
        platform.NOTCH_EXIT_TRAVEL + KNOB_HEAD_DIA / 2.0 + platform.DISENGAGE_HEAD_MARGIN
    ) / platform.SLOT_R
    angle = math.radians(platform.INCLINE_DEG) + disengage_rad
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    contact_x = pivot_x + stop_local_x * cos_a + stop_local_z * sin_a
    contact_z = pivot_z - stop_local_x * sin_a + stop_local_z * cos_a
    normal_x = edge_x * cos_a + edge_z * sin_a
    normal_z = -edge_x * sin_a + edge_z * cos_a
    derived = (
        contact_x + normal_x * STOP_CONTACT_DIA / 2.0,
        contact_z + normal_z * STOP_CONTACT_DIA / 2.0,
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
        - STOP_CONTACT_DIA / 2.0
    )
    assert engaged_gap >= 2.0
    assert math.isclose(engaged_gap, part.SWING_HARDWARE_GEOMETRY.stop_engaged_gap)


def pinion_pivot_block_depth() -> float:
    from dt_pinion_pivot_block_geometry import BLOCK_DEPTH

    return BLOCK_DEPTH


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
    former_feet = ((former_pivot_x - 20.0, rig.SPRING_PAD_Z - MECHANISM_Z_SHIFT),)
    assert part.BLOCK_SCREW_XZ == tuple(
        (x + MECHANISM_X_SHIFT, z) for z in rig.BLOCK_SEAT_Z for x in former_block_x
    )
    # Option E-a deepened the blocks outward from the back stop (10.25 ->
    # 10.5 -> 11.0), so the back seats moved 0.375 aft of the released
    # 82.875, and RIG_AFT_SHIFT (Main, #858: j = 19's full face) moved the
    # rig 1.25 aft.
    assert rig.BLOCK_SEAT_Z[1] == pytest.approx(
        83.25 + rig.RIG_AFT_SHIFT + MECHANISM_Z_SHIFT
    )
    # Codex #854 P1: the front seats are cut at the fit-up station -- one
    # block, the solid stack and one feeler off the back seats -- not at a
    # pose carrying extra air (-86.237 before the fix).
    assert rig.BLOCK_SEAT_Z[1] - rig.BLOCK_SEAT_Z[0] == pytest.approx(
        pinion_pivot_block_depth() + rig.INNER_SPAN, abs=1e-9
    )
    # Ruling 3's 0.45 drum shim puts the front seats that much forward, and
    # the 11.0 block half its extra depth.
    assert rig.BLOCK_SEAT_Z[0] == pytest.approx(
        -89.65 + rig.RIG_AFT_SHIFT + MECHANISM_Z_SHIFT
    )
    assert part.FOOT_SCREW_XZ == tuple(
        (x + MECHANISM_X_SHIFT, z + MECHANISM_Z_SHIFT) for x, z in former_feet
    )
    # U34c: the arbor pedestals left the #4-40 foot group for their own #8-32
    # seats, 19.0 outboard of each strap inner face on the unshifted drum axis;
    # #743's solid bank puts those faces at -71.519 / +73.062.
    expected = ((-54.7 + MECHANISM_X_SHIFT, -90.519), (-54.7 + MECHANISM_X_SHIFT, 92.062))
    for actual, wanted in zip(part.PEDESTAL_SCREW_XZ, expected, strict=True):
        assert actual == pytest.approx(wanted, abs=5e-4)


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

    spec = fr_harmonic_base_spec
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
    import draw_fr_harmonic_base as sheet

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
    # Codex #855 P1: the four block seats are spotted THROUGH MHA-DT-018 at
    # assembly (U28 corollary; the drive-train RIG_SET_STEP, "BEFORE SPOTTING
    # THE TRANSFER SEATS"), so they leave the hole table and their one callout
    # names the transfer.  Codex #854 P1: the model seats themselves sit at the
    # fit-up stations, so the modelled holes match the transferred ones.
    import draw_fr_harmonic_base as sheet
    import pinion_rig_layout as rig
    from dt_pinion_pivot_block_geometry import BLOCK_DEPTH

    block_seats = {(x, z, part.BLOCK_SCREW_HOLE_DIA) for x, z in part.BLOCK_SCREW_XZ}
    assert set(sheet.TRANSFER_BLOCK_HOLES) == block_seats
    assert not block_seats & set(sheet.TABLE_HOLES)
    # The front pair sits one feeler off the fit-up stack, with no pose air.
    front_seat = rig.BACK_BLOCK_Z0 - rig.INNER_SPAN - BLOCK_DEPTH / 2.0
    assert rig.BLOCK_SEAT_Z[0] == pytest.approx(front_seat, abs=1e-9)


def test_transferred_pedestal_and_spring_seats_print_no_station() -> None:
    # U34c (I27): each arbor pedestal is stood on the base with the arbor in
    # both straps and its #8-32 seat is spotted through the MHA-DT-002 ledge
    # hole, so the pair leaves the hole table like the pinion-block seats. The
    # spring-foot seat, now alone on its #4-40 feature, takes a native callout
    # instead of a note naming a table row that no longer exists.
    import draw_fr_harmonic_base as sheet

    pedestal_seats = {
        (x, z, part.PEDESTAL_SCREW_HOLE_DIA) for x, z in part.PEDESTAL_SCREW_XZ
    }
    assert set(sheet.TRANSFER_PEDESTAL_HOLES) == pedestal_seats
    assert sheet.TRANSFER_SPRING_HOLE[:2] == part.FOOT_SCREW_XZ[0]
    assert not (pedestal_seats | {sheet.TRANSFER_SPRING_HOLE}) & set(sheet.TABLE_HOLES)


def test_isometric_render_hides_model_annotations_only_after_the_save(
    monkeypatch, tmp_path
) -> None:
    # warm-c486 eye pass: the part-owned surface-finish PMI rendered as
    # floating "A1-A4 BORES Ra 3.2" / "FLANGE EDGES, 4 SIDES" symbols. The
    # part must be saved (annotations shown) before the display toggle drops.
    import asyncio
    from types import SimpleNamespace

    visibility: dict[str, bool] = {}

    async def fake_save(adapter, part_name, views=("isometric",)):
        visibility["saved"] = adapter.currentModel.Extension.shown
        return {"part": "p.SLDPRT", "stl": "p.STL"}

    class Extension:
        shown = True

        def SetUserPreferenceToggle(self, pref, option, value):
            self.shown = value
            return True

        def GetUserPreferenceToggle(self, pref, option):
            return self.shown

    extension = Extension()

    class Adapter:
        currentModel = SimpleNamespace(Extension=extension)

        async def export_image(self, request):
            visibility["rendered"] = extension.shown
            return SimpleNamespace(is_success=True, data=None, error=None)

    monkeypatch.setattr(part, "save_part_and_images", fake_save)
    monkeypatch.setattr(part, "OUT_PNG", tmp_path)
    artefacts = asyncio.run(part._save_with_annotation_free_render(Adapter()))

    assert visibility == {"saved": True, "rendered": False}
    assert artefacts["isometric"] == str(
        (tmp_path / part.PART_NAME / f"{part.PART_NAME}_isometric.png").resolve()
    )


def test_callout_clash_check_names_overlaps_and_crowding() -> None:
    import draw_fr_harmonic_base as sheet

    callouts = {
        "left": (0.160, 0.245, 0.240, 0.265),
        "right": (0.228, 0.245, 0.310, 0.265),  # overlaps "left" by 12 mm
        "clear": (0.320, 0.100, 0.330, 0.110),
    }
    obstacles = {
        "view holes top": (0.225, 0.160, 0.345, 0.240),
        "table": (0.010, 0.130, 0.1595, 0.270),  # 0.5 mm from "left"
    }
    findings = sheet.find_callout_clashes(callouts, obstacles)
    assert findings == [
        "callout left vs callout right: clearance -12.0 mm",
        "callout left vs table: clearance 0.5 mm",
    ]
    assert sheet.box_gap((0.0, 0.0, 1.0, 1.0), (1.5, 0.0, 2.0, 1.0)) == pytest.approx(0.5)
    assert sheet.find_callout_clashes({"a": (0.0, 0.0, 0.01, 0.01)}, {"b": (0.0115, 0.0, 0.02, 0.01)}) == []


# The display data the hb-callout-cal leaf logged for e0e287c83's sheet 2:
# (anchor, [shoulder/leader lines], [(text, lower-left, height)]), sheet metres.
E0E287C83_CALLOUTS = {
    "MHA-DT-018 block transfer": (
        [0.262, 0.252],
        [(0.278818, 0.216872, 0.304252, 0.243612), (0.278222, 0.216247, 0.278818, 0.216872),
         (0.304252, 0.243612, 0.221335, 0.243612)],
        [("4X ", [0.241215, 0.254832], 0.0035), ("<MOD-DIAM>", [0.247938, 0.254778], 0.0035),
         (" 3.45 ", [0.253216, 0.254832], 0.0035), ("<HOLE-DEPTH>", [0.264854, 0.254778], 0.0035),
         (" 15.00", [0.269854, 0.254832], 0.0035), ("TRANSFER FROM MHA-DT-018", [0.233047, 0.249222], 0.0035),
         ("AT ASSEMBLY; 8-32 UNC - 2B ", [0.221335, 0.243666], 0.0035),
         ("<HOLE-DEPTH>", [0.284734, 0.243612], 0.0035), (" 12.75", [0.289734, 0.243666], 0.0035)],
    ),
    "MHA-DT-002 pedestal transfer": (
        [0.2, 0.252],
        [(0.264616, 0.218237, 0.242252, 0.243612), (0.265187, 0.217589, 0.264616, 0.218237),
         (0.242252, 0.243612, 0.159335, 0.243612)],
        [("2X ", [0.179215, 0.254832], 0.0035), ("<MOD-DIAM>", [0.185938, 0.254778], 0.0035),
         (" 3.45 ", [0.191216, 0.254832], 0.0035), ("<HOLE-DEPTH>", [0.202854, 0.254778], 0.0035),
         (" 19.50", [0.207854, 0.254832], 0.0035), ("TRANSFER FROM MHA-DT-002", [0.171047, 0.249222], 0.0035),
         ("AT ASSEMBLY; 8-32 UNC - 2B ", [0.159335, 0.243666], 0.0035),
         ("<HOLE-DEPTH>", [0.222734, 0.243612], 0.0035), (" 16.00", [0.227734, 0.243666], 0.0035)],
    ),
    "MHA-DT-024 spring transfer": (
        [0.269, 0.1575],
        [(0.271627, 0.175879, 0.309959, 0.149112), (0.271163, 0.176202, 0.271627, 0.175879),
         (0.309959, 0.149112, 0.229628, 0.149112)],
        [("<MOD-DIAM>", [0.251576, 0.160278], 0.0035), (" 2.26 ", [0.256855, 0.160332], 0.0035),
         ("<HOLE-DEPTH>", [0.268492, 0.160278], 0.0035), (" 11.30", [0.273493, 0.160332], 0.0035),
         ("TRANSFER FROM MHA-DT-024", [0.240047, 0.154722], 0.0035),
         ("AT ASSEMBLY; 4-40 UNC - 2B ", [0.229628, 0.149166], 0.0035),
         ("<HOLE-DEPTH>", [0.293027, 0.149112], 0.0035), (" 9.28", [0.298027, 0.149166], 0.0035)],
    ),
    "MHA-VN-027 cross-tap": (
        [0.285, 0.13],
        [(0.329577, 0.098247, 0.342356, 0.113278), (0.328923, 0.097478, 0.329577, 0.098247),
         (0.342356, 0.113278, 0.229232, 0.113278)],
        [("4X ", [0.262404, 0.141166], 0.0035), ("<MOD-DIAM>", [0.269127, 0.141113], 0.0035),
         (" 4.04 ", [0.274406, 0.141166], 0.0035), ("<HOLE-DEPTH>", [0.286043, 0.141113], 0.0035),
         (" 48 MIN", [0.291044, 0.141166], 0.0035), ("MHA-VN-027 TUBE CROSS-SCREWS", [0.250907, 0.135556], 0.0035),
         ("THRU BOTH WALLS, SINGLE CONTINUOUS THREAD", [0.230711, 0.13], 0.0035),
         ("DEPTHS FROM SPOTFACE FLOOR", [0.248979, 0.124444], 0.0035),
         ("ON A1-A4 X CENTRES", [0.261375, 0.118888], 0.0035),
         ("2 EACH FRONT/REAR FACE 10-32 UNF - 2B ", [0.229232, 0.113331], 0.0035),
         ("<HOLE-DEPTH>", [0.322837, 0.113278], 0.0035), (" 46.00", [0.327838, 0.113331], 0.0035)],
    ),
}
E0E287C83_OBSTACLES = {
    "view holes top": (0.22285, 0.1591, 0.33715, 0.2309),
    "view holes front": (0.22285, 0.0883375, 0.33715, 0.1016625),
    "view section A-A": (0.3683375, 0.0991, 0.3816625, 0.1709),
    "label 'TOP VIEW SCALE 1:4'": (0.234753, 0.23265, 0.279474, 0.237034),
    "label 'FRONT CROSS-TAP VIEW SCALE 1:4'": (0.244837, 0.070864, 0.321565, 0.075249),
    "table DetailItem460": (0.018, 0.135058, 0.162763, 0.26),
}


def test_callout_box_rule_fails_e0e287c83_sheet_on_its_real_display_data() -> None:
    """Fail-first on real data: e0e287c83's two eye-pass defects, plus the
    pedestal underline touching the hole table. A box of shoulder plus anchor
    alone missed the spring text rising into the plan (hb-callout-cal)."""
    import draw_fr_harmonic_base as sheet

    callouts = {
        label: sheet.callout_text_box(anchor, lines, texts, label)
        for label, (anchor, lines, texts) in E0E287C83_CALLOUTS.items()
    }
    # The block spans the shoulder and rises to the top row's lower-left plus height.
    assert callouts["MHA-DT-024 spring transfer"] == pytest.approx((0.229628, 0.149112, 0.309959, 0.163832))
    assert sheet.find_callout_clashes(callouts, E0E287C83_OBSTACLES) == [
        "callout MHA-DT-002 pedestal transfer vs callout MHA-DT-018 block transfer: clearance -14.7 mm",
        "callout MHA-DT-002 pedestal transfer vs table DetailItem460: clearance -3.4 mm",
        "callout MHA-DT-024 spring transfer vs view holes top: clearance -4.7 mm",
    ]


def test_callout_check_treats_the_sheet_frame_and_title_block_as_obstacles() -> None:
    from types import SimpleNamespace

    import draw_fr_harmonic_base as sheet
    from _drawing_layout_check import DrawableRegion
    from _drawing_registry import DRAWING_TEMPLATES

    template = DRAWING_TEMPLATES[sheet.SPEC.layout]
    margin = 0.0127  # the template's ISheet::GetZoneMargin, 0.5 in each side
    drawable = DrawableRegion.from_margins(
        template.width_m, template.height_m, left=margin, right=margin, bottom=margin, top=margin
    )
    frame = sheet.frame_obstacles(
        (template.width_m, template.height_m),
        drawable,
        (template.title_block_left_m, template.title_block_top_m),
    )
    assert frame["frame top"] == pytest.approx((0.0, 0.2667, 0.4318, 0.2794))
    assert frame["title block"] == pytest.approx((0.216, 0.0, 0.4318, 0.066))

    # The live path: the real sheet_drawable_region reads the zone margins off
    # the current sheet and hands back a real DrawableRegion (hb-render-1 died
    # on region.box, which a stubbed region never exercised).
    class Adapter:
        def _attempt(self, operation, default=None):
            return operation()

    live_sheet = SimpleNamespace(GetZoneMargin=lambda code: margin)
    ddoc = SimpleNamespace(GetCurrentSheet=lambda: live_sheet)
    assert sheet._sheet_frame_obstacles(Adapter(), ddoc) == frame

    callouts = {
        # A transfer block nudged up until its top row reaches 0.5 mm off the frame.
        "against the frame": (0.233, 0.2455, 0.293, 0.2662),
        # A cross-tap block dropped into the title block's top edge.
        "into the title block": (0.229, 0.060, 0.342, 0.090),
        "clear": (0.171, 0.2409, 0.2306, 0.2610),
    }
    assert sheet.find_callout_clashes(callouts, frame) == [
        "callout against the frame vs frame top: clearance 0.5 mm",
        "callout into the title block vs title block: clearance -6.0 mm",
    ]


# hb-render-2 (e533ef6fd) logged these, sheet metres: the MHA-DT-002 and MHA-DT-024
# callouts' display lines and boxes, and the plan's view label the MHA-DT-002
# leader ran through.
E533EF6FD_PEDESTAL_LINES = [
    (0.264542, 0.218153, 0.230540, 0.240834),
    (0.265261, 0.217673, 0.264542, 0.218153),
    (0.230540, 0.240834, 0.171047, 0.240834),
]
E533EF6FD_PEDESTAL_BOX = (0.171047, 0.240834, 0.230540, 0.261110)
E533EF6FD_SPRING_LINES = [
    (0.271602, 0.175848, 0.309959, 0.140112),
    (0.271188, 0.176233, 0.271602, 0.175848),
    (0.309959, 0.140112, 0.229628, 0.140112),
]
E533EF6FD_SPRING_BOX = (0.229628, 0.140112, 0.309959, 0.154832)
E533EF6FD_TOP_VIEW_LABEL = (0.234753, 0.232650, 0.279474, 0.237034)


def test_leader_check_fails_e533ef6fd_leader_through_the_top_view_label() -> None:
    """Fail-first on e533ef6fd's layout: its MHA-DT-002 leader struck through
    "TOP" of the plan's view label (hb-render-2 eye pass)."""
    import draw_fr_harmonic_base as sheet

    leaders = {"MHA-DT-002 pedestal transfer": sheet.leader_segments(E533EF6FD_PEDESTAL_LINES)}
    texts = {
        "callout MHA-DT-002 pedestal transfer": E533EF6FD_PEDESTAL_BOX,
        "label 'TOP VIEW SCALE 1:4'": E533EF6FD_TOP_VIEW_LABEL,
    }
    assert sheet.find_leader_crossings(leaders, texts) == [
        "leader of callout MHA-DT-002 pedestal transfer crosses label 'TOP VIEW SCALE 1:4'"
    ]
    # Beside the plan's top-left corner, the same label is off that leader.
    x, y = sheet.HOLES_TOP_LABEL_XY
    width = E533EF6FD_TOP_VIEW_LABEL[2] - E533EF6FD_TOP_VIEW_LABEL[0]
    height = E533EF6FD_TOP_VIEW_LABEL[3] - E533EF6FD_TOP_VIEW_LABEL[1]
    texts["label 'TOP VIEW SCALE 1:4'"] = (x, y - height, x + width, y)
    assert sheet.find_leader_crossings(leaders, texts) == []
    assert sheet.find_callout_clashes(
        {"MHA-DT-002 pedestal transfer": E533EF6FD_PEDESTAL_BOX},
        {"label": texts["label 'TOP VIEW SCALE 1:4'"]},
    ) == []


def test_leader_check_skips_its_own_callout_box_among_foreign_texts() -> None:
    import draw_fr_harmonic_base as sheet

    # Among foreign texts a callout's own whole box is skipped (its rows are
    # checked separately, below); a foreign note on the leader's path is not.
    leaders = {"MHA-DT-024 spring transfer": sheet.leader_segments(E533EF6FD_SPRING_LINES)}
    texts = {
        "callout MHA-DT-024 spring transfer": E533EF6FD_SPRING_BOX,
        "note on the path": (0.285, 0.160, 0.295, 0.165),
        "note beside it": (0.300, 0.170, 0.310, 0.175),
    }
    assert sheet.find_leader_crossings(leaders, texts) == [
        "leader of callout MHA-DT-024 spring transfer crosses note on the path"
    ]


E533EF6FD_SPRING_TEXTS = [
    ("<MOD-DIAM>", [0.251576, 0.151278], 0.0035),
    (" 2.26 ", [0.256855, 0.151332], 0.0035),
    ("<HOLE-DEPTH>", [0.268492, 0.151278], 0.0035),
    (" 11.30", [0.273493, 0.151332], 0.0035),
    ("TRANSFER FROM MHA-DT-024", [0.240047, 0.145722], 0.0035),
    ("AT ASSEMBLY; 4-40 UNC - 2B ", [0.229628, 0.140166], 0.0035),
    ("<HOLE-DEPTH>", [0.293027, 0.140112], 0.0035),
    (" 9.28", [0.298027, 0.140166], 0.0035),
]


def test_callout_text_rows_centre_each_row_on_the_shoulder() -> None:
    import draw_fr_harmonic_base as sheet

    rows = sheet.callout_text_rows(E533EF6FD_SPRING_LINES, E533EF6FD_SPRING_TEXTS, "spring")
    centre = (0.229628 + 0.309959) / 2.0
    assert list(rows) == [
        "<MOD-DIAM> 2.26 <HOLE-DEPTH> 11.30",
        "TRANSFER FROM MHA-DT-024",
        "AT ASSEMBLY; 4-40 UNC - 2B <HOLE-DEPTH> 9.28",
    ]
    assert rows["TRANSFER FROM MHA-DT-024"] == pytest.approx(
        (0.240047, 0.145722, 2.0 * centre - 0.240047, 0.149222)
    )
    # The widest row spans the shoulder.
    assert rows["AT ASSEMBLY; 4-40 UNC - 2B <HOLE-DEPTH> 9.28"][2] == pytest.approx(0.309959)


def test_leader_check_flags_a_leader_through_its_own_rows() -> None:
    """e533ef6fd's spring leader left the shoulder's right end and rose
    through "9.28" of its own thread row (hb-render-2 eye pass)."""
    import draw_fr_harmonic_base as sheet

    leaders = {"MHA-DT-024 spring transfer": sheet.leader_segments(E533EF6FD_SPRING_LINES)}
    own = {
        "MHA-DT-024 spring transfer": sheet.callout_text_rows(
            E533EF6FD_SPRING_LINES, E533EF6FD_SPRING_TEXTS, "spring"
        )
    }
    assert sheet.find_leader_crossings(leaders, {}, own) == [
        "leader of callout MHA-DT-024 spring transfer crosses its own row "
        "'AT ASSEMBLY; 4-40 UNC - 2B <HOLE-DEPTH> 9.28'"
    ]
    # The same block right of the hole, its leader leaving the near (left)
    # end up and away from the text: the joint corner does not count.
    shift = 0.2712 + 0.002 - 0.229628
    moved_lines = [
        (0.271602, 0.175848, 0.229628 + shift, 0.140112),
        (0.271188, 0.176233, 0.271602, 0.175848),
        (0.309959 + shift, 0.140112, 0.229628 + shift, 0.140112),
    ]
    moved_texts = [(text, [x + shift, y], h) for text, (x, y), h in E533EF6FD_SPRING_TEXTS]
    leaders = {"MHA-DT-024 spring transfer": sheet.leader_segments(moved_lines)}
    own = {"MHA-DT-024 spring transfer": sheet.callout_text_rows(moved_lines, moved_texts, "spring")}
    assert sheet.find_leader_crossings(leaders, {}, own) == []
    # A transfer leader drops away from its rows: no finding.
    pedestal = {"MHA-DT-002 pedestal transfer": sheet.leader_segments(E533EF6FD_PEDESTAL_LINES)}
    assert sheet.find_leader_crossings(pedestal, {}, {"MHA-DT-002 pedestal transfer": {
        "8-32 UNC - 2B <HOLE-DEPTH> 16.00": (0.174589, 0.240888, 0.227000, 0.244388),
    }}) == []


# hb-render-3 (12259de3a) logged the spring at (0.286, 0.1485): box, and the
# hole its leader tip reaches. The block spans anchor -40.96/+39.37 mm in x.
HB_RENDER_3_SPRING_BOX = (0.245040, 0.140112, 0.325372, 0.154832)
HB_RENDER_3_SPRING_TIP_X = 0.271562


def test_spring_text_sits_wholly_right_of_its_hole() -> None:
    import draw_fr_harmonic_base as sheet

    left = sheet.SPRING_CALLOUT_XY[0] - (0.286 - HB_RENDER_3_SPRING_BOX[0])
    right = sheet.SPRING_CALLOUT_XY[0] + (HB_RENDER_3_SPRING_BOX[2] - 0.286)
    assert HB_RENDER_3_SPRING_BOX[0] < HB_RENDER_3_SPRING_TIP_X  # 12259de3a: under the text
    assert left > HB_RENDER_3_SPRING_TIP_X + 0.002  # now clear of it, near end left
    assert right < 0.368340 - 0.010  # the section view's left edge


def test_only_notes_that_reach_the_final_sheet_are_obstacles() -> None:
    import draw_fr_harmonic_base as sheet

    # hb-render-3 flagged leaders over these; finalize deletes them.
    assert not sheet.note_reaches_final_sheet("1/4-20 Tapped Hole")
    assert not sheet.note_reaches_final_sheet("#8-32 tapped hole")
    assert not sheet.note_reaches_final_sheet(" \r\n ")  # DetailItem420: no ink
    assert sheet.note_reaches_final_sheet("TOP VIEW SCALE 1:4")
    assert sheet.note_reaches_final_sheet("D1")


# The fake sheet's RIG SET note, clear of its table, view and callout.
_FAKE_RIG_SET_BOX = (0.150, 0.020, 0.180, 0.040)


def _drive_hole_sheet_callout_check(
    monkeypatch, note_box, rig_set_box: tuple[float, float, float, float] | None = _FAKE_RIG_SET_BOX
) -> None:
    """Run _check_hole_sheet_callouts on fakes: one callout, one sheet note at
    ``note_box``, the RIG SET note at ``rig_set_box`` (None: absent) and a
    display dimension, which _iter_view_annotations yields as
    ``(None, annotation)`` since #902 (a5563c7a0)."""
    from types import SimpleNamespace

    import draw_fr_harmonic_base as sheet

    texts = {"note": "D1", "rig set": sheet.RIG_SET_STEP.replace("\n", "\r\n")}

    def annotations(_adapter, view):
        if view != "sheet":
            return iter(())
        rows = [
            (None, "display dimension"),
            (SimpleNamespace(kind="note", label="D1", box=note_box), "note"),
        ]
        if rig_set_box is not None:
            rows.append((SimpleNamespace(kind="note", label="RS", box=rig_set_box), "rig set"))
        return iter(rows)

    for name, value in {
        "_callout_display_data": lambda display, label: (None, (), ()),
        "callout_text_box": lambda anchor, lines, texts, label: (0.100, 0.100, 0.130, 0.110),
        "leader_segments": lambda lines: [],
        "callout_text_rows": lambda lines, texts, label: {},
        "_sheet_frame_obstacles": lambda adapter, ddoc: {},
        "_view_geometry_box": lambda adapter, view, label: (0.300, 0.150, 0.400, 0.250),
        "_early_bound": lambda obj, interface: obj,
        "datum_origin_boxes": lambda points: {},
        "_section_line_obstacles": lambda views: {},
        "_iter_view_annotations": annotations,
        "_note_text": lambda adapter, annotation: texts[annotation],
        "_iter_tables": lambda adapter, view: (
            [SimpleNamespace(label="holes", box=(0.020, 0.020, 0.090, 0.060))]
            if view == "sheet"
            else []
        ),
    }.items():
        monkeypatch.setattr(sheet, name, value)
    ddoc = SimpleNamespace(ActivateSheet=lambda name: True, GetFirstView=lambda: "sheet")
    sheet._check_hole_sheet_callouts(
        object(),
        ddoc,
        callouts={"pedestal": object()},
        views={"top": "top view"},
        datum_origin=SimpleNamespace(GetAxisPoints2=lambda: ()),
    )


def test_hole_sheet_callout_check_still_measures_notes_beside_dimensions(
    monkeypatch,
) -> None:
    with pytest.raises(RuntimeError, match="callout pedestal vs note D1"):
        _drive_hole_sheet_callout_check(monkeypatch, (0.110, 0.102, 0.120, 0.108))


def test_hole_sheet_callout_check_measures_the_rig_set_note_against_obstacles(
    monkeypatch,
) -> None:
    """Fail-first: the RIG SET note is measured like a callout, so the note
    landing on the hole table fails the build -- a plain note obstacle is
    never compared with the table -- and a sheet without it fails too."""
    clear = (0.200, 0.200, 0.220, 0.210)
    with pytest.raises(RuntimeError, match="callout RIG SET note vs table holes"):
        _drive_hole_sheet_callout_check(monkeypatch, clear, rig_set_box=(0.030, 0.030, 0.060, 0.050))
    with pytest.raises(RuntimeError, match="no RIG SET note"):
        _drive_hole_sheet_callout_check(monkeypatch, clear, rig_set_box=None)


def test_section_line_boxes_cover_arrows_and_labels_in_sheet_space() -> None:
    import draw_fr_harmonic_base as sheet

    size = (0.4318, 0.2794)
    arrows = [0.3293, 0.1563, 0.0, 0.3411, 0.1563, 0.0, 0.3293, 0.2351, 0.0, 0.3411, 0.2351, 0.0]
    labels = [0.3433, 0.1596, 0.0, 0.3433, 0.2384, 0.0]
    boxes = sheet.section_line_boxes("A", arrows, labels, 0.005, "A", size)
    assert boxes["section A arrow 1"] == pytest.approx((0.3273, 0.1543, 0.3431, 0.1583))
    assert boxes["label section A 1"] == pytest.approx((0.3433, 0.1546, 0.3483, 0.1596))
    # A spring block right of its hole but at the old height runs into the "A".
    high = (0.274, 0.1400, 0.3544, 0.1548)
    low = (0.274, 0.1364, 0.3544, 0.1511)
    assert sheet.find_callout_clashes({"spring": high}, boxes) == [
        "callout spring vs label section A 1: clearance -0.2 mm",
        "callout spring vs section A arrow 1: clearance -0.5 mm",
    ]
    assert sheet.find_callout_clashes({"spring": low}, boxes) == []
    with pytest.raises(RuntimeError, match="not in sheet space"):
        sheet.section_line_boxes("A", [v * 10 for v in arrows], labels, 0.005, "A", size)
    with pytest.raises(RuntimeError, match="expected 12 arrow"):
        sheet.section_line_boxes("A", arrows[:9], labels, 0.005, "A", size)


def test_segment_crossing_covers_inside_through_and_near_misses() -> None:
    import draw_fr_harmonic_base as sheet

    box = (0.0, 0.0, 1.0, 1.0)
    assert sheet.segment_crosses_box((-1.0, 0.5, 2.0, 0.5), box)  # straight through
    assert sheet.segment_crosses_box((0.2, 0.2, 0.3, 0.3), box)  # wholly inside
    assert sheet.segment_crosses_box((0.5, 0.5, 3.0, 3.0), box)  # leaves it
    assert not sheet.segment_crosses_box((1.1, -1.0, 1.1, 2.0), box)  # passes beside
    assert not sheet.segment_crosses_box((1.5, 0.0, 3.0, 1.0), box)  # diagonal miss
    assert not sheet.segment_crosses_box((-0.5, 1.2, 1.5, 1.2), box)  # parallel above


def test_leader_sides_name_the_attached_end_and_the_end_nearest_the_hole() -> None:
    import draw_fr_harmonic_base as sheet

    # e533ef6fd: the leader left the right end, and the hole (x 0.2712) was
    # nearer that end (0.3100) than the left one (0.2296).
    assert sheet.leader_sides(E533EF6FD_SPRING_LINES, "spring") == (2, 2)
    assert sheet.leader_segments(E533EF6FD_SPRING_LINES) == E533EF6FD_SPRING_LINES[:2]
    # 0.017 further right, a right-end leader would leave the farther end.
    shifted = [
        (0.271602, 0.175848, 0.326959, 0.140112),
        (0.271188, 0.176233, 0.271602, 0.175848),
        (0.326959, 0.140112, 0.246628, 0.140112),
    ]
    assert sheet.leader_sides(shifted, "spring") == (2, 1)
    with pytest.raises(RuntimeError, match="no shoulder or no leader"):
        sheet.leader_sides(shifted[2:], "spring")


def test_datum_origin_boxes_pad_each_axis_for_its_labels() -> None:
    import draw_fr_harmonic_base as sheet

    # Axis points read off hb-render-2's sheet PNG (the seat reads the real ones
    # from IDatumOrigin.GetAxisPoints2): X from the flange corner right, Y up.
    boxes = sheet.datum_origin_boxes([0.2224, 0.146, 0.2418, 0.146, 0.209, 0.159, 0.209, 0.174])
    assert boxes["origin X axis"] == pytest.approx((0.2189, 0.1425, 0.2453, 0.1495))
    assert boxes["origin Y axis"] == pytest.approx((0.2055, 0.1555, 0.2125, 0.1775))
    # e533ef6fd's spring callout sat on the X axis and its "X" label.
    assert sheet.find_callout_clashes({"MHA-DT-024 spring transfer": E533EF6FD_SPRING_BOX}, boxes) == [
        "callout MHA-DT-024 spring transfer vs origin X axis: clearance -9.4 mm"
    ]
    with pytest.raises(RuntimeError, match="not 4"):
        sheet.datum_origin_boxes([0.0] * 6)


def test_callout_box_rule_refuses_display_data_it_cannot_box() -> None:
    import draw_fr_harmonic_base as sheet

    with pytest.raises(RuntimeError, match="no horizontal shoulder"):
        sheet.callout_text_box([0.0, 0.0], [(0.0, 0.0, 0.01, 0.01)], [("X", [0.0, 0.0], 0.0035)], "x")
    with pytest.raises(RuntimeError, match="no text rows"):
        sheet.callout_text_box([0.0, 0.0], [(0.0, 0.0, 0.01, 0.0)], [], "x")


# Native 7e2e66e8a3e1 worker display data, 2026-10-06 identity base task:
# (anchor, lines, [(full text, sheet XY, cap height)]), in sheet metres.
# Both full-Number transfer shoulders are 66.503 mm wide. Older calibration
# fixtures above stay frozen; their narrower shoulders missed this collision.
IDENTITY_7E2E66E8_CALLOUTS = {
    "MHA-DT-018 block transfer": (
        [0.262, 0.252],
        [
            (0.27877160510394766, 0.2167478803502756, 0.2960451385319233, 0.24083402720093727),
            (0.2782683730037054, 0.21604617549545002, 0.27877160510394766, 0.2167478803502756),
            (0.2960451385319233, 0.24083402720093727, 0.22954236146807666, 0.24083402720093727),
        ],
        [
            ("4X ", [0.2412149811983108, 0.25760972263338044], 0.0035),
            ("<MOD-DIAM>", [0.24793789804726835, 0.2575562504567206], 0.0035),
            (" 3.45 ", [0.2532163354456424, 0.25760972263338044], 0.0035),
            ("<HOLE-DEPTH>", [0.2648538350015878, 0.2575562504567206], 0.0035),
            (" 15.40", [0.2698544598072767, 0.25760972263338044], 0.0035),
            ("TRANSFER FROM MHA-DT-018", [0.22954236146807666, 0.2520000002910383], 0.0035),
            ("AFTER RIG SET;", [0.2461552078723907, 0.246443750299979], 0.0035),
            (" 8-32 UNC - 2B ", [0.23658926960825916, 0.2408875003089197], 0.0035),
            ("<HOLE-DEPTH>", [0.2694795484542846, 0.24083402813225985], 0.0035),
            (" 12.75", [0.2744801732599735, 0.2408875003089197], 0.0035),
        ],
    ),
    "MHA-DT-002 pedestal transfer": (
        [0.200, 0.252],
        [
            (0.2645565321885683, 0.21788924303719595, 0.23404513853192324, 0.24083402720093727),
            (0.26524666674399006, 0.21737025696280396, 0.2645565321885683, 0.21788924303719595),
            (0.23404513853192324, 0.24083402720093727, 0.16754236146807672, 0.24083402720093727),
        ],
        [
            ("2X ", [0.17921498119831086, 0.25760972263338044], 0.0035),
            ("<MOD-DIAM>", [0.1859378980472684, 0.2575562504567206], 0.0035),
            (" 3.45 ", [0.19121633544564248, 0.25760972263338044], 0.0035),
            ("<HOLE-DEPTH>", [0.20285383500158788, 0.2575562504567206], 0.0035),
            (" 19.50", [0.20785445980727674, 0.25760972263338044], 0.0035),
            ("TRANSFER FROM MHA-DT-002", [0.16754236146807672, 0.2520000002910383], 0.0035),
            ("AT ASSEMBLY;", [0.1847458340227604, 0.246443750299979], 0.0035),
            (" 8-32 UNC - 2B ", [0.1745892696082592, 0.2408875003089197], 0.0035),
            ("<HOLE-DEPTH>", [0.20747954845428468, 0.24083402813225985], 0.0035),
            (" 16.00", [0.21248017325997354, 0.2408875003089197], 0.0035),
        ],
    ),
    "MHA-DT-024 spring transfer": (
        [0.315, 0.1448],
        [
            (0.27140967880099826, 0.17561478493897656, 0.2734500369191169, 0.1364121521964669),
            (0.2713802993066548, 0.1761792709067491, 0.27140967880099826, 0.17561478493897656),
            (0.2734500369191169, 0.1364121521964669, 0.35496246308088303, 0.1364121521964669),
        ],
        [
            ("<MOD-DIAM>", [0.2975764410197734, 0.1475781254611909], 0.0035),
            (" 2.26 ", [0.30285487841814746, 0.14763159763785075], 0.0035),
            ("<HOLE-DEPTH>", [0.3144923789054154, 0.1475781254611909], 0.0035),
            (" 12.25", [0.3194930037111043, 0.14763159763785075], 0.0035),
            ("TRANSFER FROM MHA-DT-024", [0.2825423614680766, 0.1420218752955086], 0.0035),
            ("AFTER RIG SET; 4-40 UNC - 2B ", [0.27503753691911687, 0.1364656253044493], 0.0035),
            ("<HOLE-DEPTH>", [0.33961739629507054, 0.13641215312778945], 0.0035),
            (" 9.95", [0.3446180248260497, 0.1364656253044493], 0.0035),
        ],
    ),
    "MHA-VN-027 cross-tap": (
        [0.285, 0.120],
        [
            (0.3295759581969177, 0.09824798610154861, 0.3408763902127742, 0.11161215219646689),
            (0.3289240418030824, 0.09747701389845131, 0.3295759581969177, 0.09824798610154861),
            (0.3408763902127742, 0.11161215219646689, 0.2307111097872257, 0.11161215219646689),
        ],
        [
            ("4X ", [0.26240421816706655, 0.12283159763785073], 0.0035),
            ("<MOD-DIAM>", [0.2691271350160241, 0.12277812546119088], 0.0035),
            (" 4.04 ", [0.27440557241439817, 0.12283159763785073], 0.0035),
            ("<HOLE-DEPTH>", [0.28604307197034357, 0.12277812546119088], 0.0035),
            (" 49 MIN", [0.2910436967760324, 0.12283159763785073], 0.0035),
            ("THRU BOTH WALLS, SINGLE CONTINUOUS THREAD", [0.2307111097872257, 0.11722187529550859], 0.0035),
            (" 10-32 UNF - 2B ", [0.25906183928251264, 0.11166562530444929], 0.0035),
            ("<HOLE-DEPTH>", [0.2930069787800312, 0.11161215312778944], 0.0035),
            (" 46.00", [0.29800760358572004, 0.11166562530444929], 0.0035),
        ],
    ),
}
IDENTITY_7E2E66E8_RIG_NOTE_BOX = (
    0.01955375250836114, 0.08584775250836121, 0.14250844147157188, 0.10824647491638797
)
# Exact native obstacles. Template and zone-label ink is already contained
# by the title/frame keep-outs; include every remaining note and hole tag.
# The native socket-note box predates fb8's preserved narrower reflow.
IDENTITY_7E2E66E8_OBSTACLES = {
    "frame left": (0.0, 0.0, 0.0127, 0.2794),
    "frame right": (0.41910000000000003, 0.0, 0.4318, 0.2794),
    "frame bottom": (0.0, 0.0, 0.4318, 0.0127),
    "frame top": (0.0, 0.2667, 0.4318, 0.2794),
    "title block": (0.216, 0.0, 0.4318, 0.066),
    "view holes top": (0.22285000000000002, 0.1591, 0.33715, 0.23090000000000005),
    "view holes front": (0.22285000000000002, 0.0883375, 0.33715, 0.1016625),
    "view section A-A": (0.3683374999999999, 0.0991, 0.3816625000000005, 0.17090000000000005),
    "origin X axis": (0.21935000000000002, 0.142105, 0.24240100000000003, 0.14910500000000002),
    "origin Y axis": (0.205855, 0.15560000000000002, 0.21285500000000002, 0.17865100000000003),
    "section A arrow 1": (0.32725000000000004, 0.153, 0.34325000000000006, 0.157),
    "section A arrow 2": (0.32725000000000004, 0.233, 0.34325000000000006, 0.23700000000000002),
    "label section A 1": (0.3431562742474917, 0.15365396989966557, 0.3495062742474917, 0.16000396989966556),
    "label section A 2": (0.3431562742474917, 0.23365396989966558, 0.3495062742474917, 0.24000396989966558),
    "note sheet count": (0.34981576588628766, 0.25884214046822746, 0.37745674247491645, 0.26313125752508365),
    "note A1": (0.23400960535117055, 0.16638783946488298, 0.24020499665551837, 0.17067695652173914),
    "note A2": (0.23400960535117055, 0.22214636120401343, 0.24020499665551837, 0.22691204682274252),
    "note A3": (0.32455763210702343, 0.16543470234113716, 0.3317061605351171, 0.17639577926421407),
    "note A4": (0.32598733779264216, 0.21070871571906358, 0.33218272909699, 0.2211932240802676),
    "note B1": (0.24640038795986624, 0.19164597324414717, 0.2516426421404682, 0.1964116588628763),
    "note C1": (0.24687695652173913, 0.21166185284280942, 0.2549786220735786, 0.22262292976588632),
    "note D1": (0.24687695652173913, 0.17067695652173914, 0.25783803344481604, 0.187356856187291),
    "note E1": (0.2940572441471572, 0.17973175919732443, 0.31073714381270906, 0.187356856187291),
    "note E2": (0.2888149899665552, 0.2016539130434783, 0.2945338127090301, 0.20975557859531777),
    "note E3": (0.30263547826086956, 0.16877068227424752, 0.3169325351170569, 0.17973175919732443),
    "note E4": (0.30263547826086956, 0.20975557859531777, 0.3169325351170569, 0.21404469565217393),
    "note F1": (0.32217478929765886, 0.18116146488294316, 0.326940474916388, 0.18545058193979935),
    "note F2": (0.32217478929765886, 0.20356018729096992, 0.326940474916388, 0.20832587290969903),
    "note F3": (0.3326592976588629, 0.176872347826087, 0.3474329230769231, 0.18354430769230773),
    "note F4": (0.3326592976588629, 0.20641959866220738, 0.3474329230769231, 0.21404469565217393),
    "note socket fit": (0.16633686956521737, 0.19927107023411375, 0.22829078260869562, 0.2264354782608696),
    "label top view": (0.16967284949832773, 0.23263086956521745, 0.21447029431438125, 0.23739655518394653),
    "label cross-tap view": (0.2449706822742475, 0.07059755852842808, 0.32169822073578597, 0.0753632441471572),
    "note origin": (0.16490716387959864, 0.1725832307692308, 0.20160294314381272, 0.1864037190635452),
    "table holes": (0.018, 0.13506283059665292, 0.1627633864343431, 0.26),
}


def test_hole_sheet_callouts_clear_full_number_native_text_and_leaders() -> None:
    """The old 62 mm spacing passed the narrower historical shoulders but
    overlaps native full-Number text by 4.503 mm. Translate its measured text
    and shoulder joints to current anchors, retaining each original hole tip."""
    from itertools import combinations

    import draw_fr_harmonic_base as sheet

    old_boxes = {
        label: sheet.callout_text_box(anchor, lines, texts, label)
        for label, (anchor, lines, texts) in IDENTITY_7E2E66E8_CALLOUTS.items()
    }
    pedestal_label = "MHA-DT-002 pedestal transfer"
    block_label = "MHA-DT-018 block transfer"
    assert sheet.box_gap(old_boxes[pedestal_label], old_boxes[block_label]) == pytest.approx(
        -0.00450277706384658
    )
    old_pedestal_lines = IDENTITY_7E2E66E8_CALLOUTS[pedestal_label][1]
    assert any(
        sheet.segment_crosses_box(segment, old_boxes[block_label])
        for segment in sheet.leader_segments(old_pedestal_lines)
    )

    anchors = {
        pedestal_label: sheet.PEDESTAL_CALLOUT_XY,
        block_label: sheet.BLOCK_CALLOUT_XY,
        "MHA-DT-024 spring transfer": sheet.SPRING_CALLOUT_XY,
        "MHA-VN-027 cross-tap": sheet.CROSS_TAP_CALLOUT_XY,
    }
    boxes, leaders, rows = {}, {}, {}
    for label, (old_anchor, old_lines, old_texts) in IDENTITY_7E2E66E8_CALLOUTS.items():
        anchor = anchors[label]
        dx, dy = anchor[0] - old_anchor[0], anchor[1] - old_anchor[1]
        shoulder_y = next(y0 for _x0, y0, _x1, y1 in old_lines if y0 == y1)

        lines = []
        for x0, y0, x1, y1 in old_lines:
            start = (x0 + dx, y0 + dy) if y0 == shoulder_y else (x0, y0)
            end = (x1 + dx, y1 + dy) if y1 == shoulder_y else (x1, y1)
            lines.append((*start, *end))
        texts = [(text, [x + dx, y + dy], height) for text, (x, y), height in old_texts]
        boxes[label] = sheet.callout_text_box(list(anchor), lines, texts, label)
        rows[label] = sheet.callout_text_rows(lines, texts, label)
        leaders[label] = sheet.leader_segments(lines)
        attached, nearest = sheet.leader_sides(lines, label)
        assert attached == nearest, label

    boxes[sheet.RIG_SET_NOTE_LABEL] = IDENTITY_7E2E66E8_RIG_NOTE_BOX
    obstacles = dict(IDENTITY_7E2E66E8_OBSTACLES)
    # The fit-note regression below uses current reflow text. Include that
    # envelope as well as the wider historical native box retained above.
    note_lines = sheet.SOCKET_FIT_NOTE.replace("<MOD-DIAM>", "D").split("\n")
    x, y = sheet.SOCKET_FIT_NOTE_XY
    obstacles["note current socket fit"] = (
        x, y - len(note_lines) * sheet.NOTE_ROW_M,
        x + max(map(len, note_lines)) * sheet.NOTE_CHAR_M, y,
    )
    label_box = obstacles["label top view"]
    dx = sheet.HOLES_TOP_LABEL_XY[0] - 0.170
    dy = sheet.HOLES_TOP_LABEL_XY[1] - 0.237
    obstacles["label top view"] = (
        label_box[0] + dx, label_box[1] + dy, label_box[2] + dx, label_box[3] + dy
    )
    assert sheet.find_callout_clashes(boxes, obstacles) == []
    assert sheet.find_merged_blocks(boxes) == []
    assert sheet.find_tall_callouts(rows) == []
    texts = {f"callout {label}": box for label, box in boxes.items()}
    texts.update(
        (name, box) for name, box in obstacles.items()
        if name.startswith(("note ", "label ", "table ", "origin ", "section "))
    )
    assert sheet.find_leader_crossings(leaders, texts, rows) == []
    # Disjoint leader envelopes prove no callout leader crosses another.
    leader_boxes = {}
    for label, segments in leaders.items():
        xs = [x for x0, _y0, x1, _y1 in segments for x in (x0, x1)]
        ys = [y for _x0, y0, _x1, y1 in segments for y in (y0, y1)]
        leader_boxes[label] = (min(xs), min(ys), max(xs), max(ys))
    for a, b in combinations(leader_boxes, 2):
        assert sheet.box_gap(leader_boxes[a], leader_boxes[b]) >= sheet.CALLOUT_CLEARANCE_M, (a, b)


# hb-render-4 (28d06157b) sheet-2 display data: the cross-tap block's six rows
# and the two callout boxes the eye pass read as one block.
HB_RENDER_4_CROSS_TAP = (
    [0.285, 0.12],
    [(0.329717, 0.098055, 0.342356, 0.103278), (0.328783, 0.097670, 0.329717, 0.098055),
     (0.342356, 0.103278, 0.229232, 0.103278)],
    [("4X ", [0.262404, 0.131166], 0.0035), ("<MOD-DIAM>", [0.269127, 0.131113], 0.0035),
     (" 4.04 ", [0.274406, 0.131166], 0.0035), ("<HOLE-DEPTH>", [0.286043, 0.131113], 0.0035),
     (" 48 MIN", [0.291044, 0.131166], 0.0035), ("MHA-VN-027 TUBE CROSS-SCREWS", [0.250907, 0.125556], 0.0035),
     ("THRU BOTH WALLS, SINGLE CONTINUOUS THREAD", [0.230711, 0.12], 0.0035),
     ("DEPTHS FROM SPOTFACE FLOOR", [0.248979, 0.114444], 0.0035),
     ("ON A1-A4 X CENTRES", [0.261375, 0.108888], 0.0035),
     ("2 EACH FRONT/REAR FACE 10-32 UNF - 2B ", [0.229232, 0.103331], 0.0035),
     ("<HOLE-DEPTH>", [0.322837, 0.103278], 0.0035), (" 46.00", [0.327838, 0.103331], 0.0035)],
)
HB_RENDER_4_BOXES = {
    "MHA-DT-018 block transfer": (0.233047, 0.240834, 0.292540, 0.261110),
    "MHA-DT-002 pedestal transfer": (0.171047, 0.240834, 0.230540, 0.261110),
    "MHA-DT-024 spring transfer": (0.274041, 0.136412, 0.354372, 0.151132),
    "MHA-VN-027 cross-tap": (0.229232, 0.103278, 0.342356, 0.134666),
}


def test_callout_rules_fail_the_hb_render_4_cross_tap_block() -> None:
    """Fail-first on real data: Main's hb-render-4 eye pass read the spring
    block 1.7 mm over the cross-tap block as its fourth row, and the cross-tap
    ran six rows. The side-by-side transfer pair is not one column."""
    import draw_fr_harmonic_base as sheet

    anchor, lines, texts = HB_RENDER_4_CROSS_TAP
    rows = sheet.callout_text_rows(lines, texts, "MHA-VN-027 cross-tap")
    assert sheet.find_tall_callouts({"MHA-VN-027 cross-tap": rows}) == [
        "callout MHA-VN-027 cross-tap runs 6 rows, over the 4-row note rule"
    ]
    assert sheet.find_merged_blocks(HB_RENDER_4_BOXES) == [
        "callout MHA-DT-024 spring transfer over callout MHA-VN-027 cross-tap: "
        "1.7 mm apart, under the 5.6 mm row pitch"
    ]
    assert sheet.find_tall_callouts({"four rows": dict(list(rows.items())[:4])}) == []


def test_cross_tap_depth_origin_is_the_spotface_floor() -> None:
    # The Hole Wizard seats the taps on the spotface floor, so its depths
    # already run from there.
    assert part.BASE_SPOTFACE_PLANE_Z - part.BASE_SPOTFACE_DEPTH == part.BASE_SCREW_SEAT_Z


def test_cross_tap_x_is_a_chained_model_dimension_on_the_front_view() -> None:
    import draw_fr_harmonic_base as sheet

    assert fr_harmonic_base_spec.DRAWING_DIMENSIONS["CrossTapReference"] == {
        "CrossTapX", "CrossTapPitch"
    }
    assert fr_harmonic_base_spec.DRAWING_PRECISION["CrossTapReference"] == {
        "CrossTapX": 1, "CrossTapPitch": 1
    }
    assert "CrossTapReference" in part.REFERENCE_SKETCHES
    assert {"CrossTapX", "CrossTapPitch"} <= set(sheet.HOLE_SIDE_KEEP)
    # 31.6 is also the table's A1/A2 X LOC from the same flange edge.
    assert part.BOTTOM_LENGTH / 2.0 - part.COLUMN_X == pytest.approx(31.6)


def test_deck_land_worst_case_is_proven_instead_of_noted() -> None:
    # hb-render-4 eye pass: the 1.0 MIN land note put a dimension in a note.
    for stack in part.COLUMN_SOCKET_LAND_STACKS.values():
        assert stack == pytest.approx({
            "nominal": 5.5,
            "flange length": -0.4,
            "pad length": -0.4,
            "rim width": -0.8,
            "bore location": -0.8,
            "matched bore": -0.25,
            "bore edge break": -0.25,
            "rim edge break": -0.25,
        })
        assert sum(stack.values()) == pytest.approx(2.35)
    # The same stack on the rejected 1.6 mm pad land would fail the 1.0 MIN.
    assert sum(part.column_socket_land_stack(1.6).values()) < part.COLUMN_SOCKET_LAND_MIN
    # Main's rider: the Ø26.0 ceiling is a functional judgement, so the
    # stack reports how much bore the land could still absorb.
    assert part.COLUMN_SOCKET_BREAK_EVEN_BORE == pytest.approx(28.7)
    rejected = part.column_socket_land_stack(1.6)
    assert part.column_socket_break_even_bore(rejected) < part.COLUMN_SOCKET_MATCH_BORE_MAX


def test_stamped_id_leader_clears_the_socket_bores() -> None:
    # 2026-09-25 Codex machinist review (hb-render-5, clarity): the stamped-ID
    # leader ran through the A3 socket bore. The leader starts where SolidWorks
    # put it on hb-render-5 (the last line's right end) and ends on the serial.
    import draw_fr_harmonic_base as sheet

    def clearance(anchor: tuple[float, float]) -> float:
        start = (
            anchor[0] + sheet.SERIAL_LEADER_START_OFFSET_M[0],
            anchor[1] + sheet.SERIAL_LEADER_START_OFFSET_M[1],
        )
        tip = sheet._plan_xy(*part.SERIAL_XZ)
        dx, dy = tip[0] - start[0], tip[1] - start[1]
        gaps = []
        for x, z in part.COLUMN_SOCKET_XZ:
            cx, cy = sheet._plan_xy(x, z)
            t = ((cx - start[0]) * dx + (cy - start[1]) * dy) / (dx * dx + dy * dy)
            t = max(0.0, min(1.0, t))
            gaps.append(
                math.hypot(cx - start[0] - t * dx, cy - start[1] - t * dy)
                - part.COLUMN_SOCKET_DIAMETER * sheet.VIEW_SCALE / 2000.0
            )
        return min(gaps)

    assert clearance((0.125, 0.130)) < 0.0  # the reviewed sheet: through A3
    assert sheet.SERIAL_NOTE_XY == (0.080, 0.130)
    assert clearance(sheet.SERIAL_NOTE_XY) >= 0.004


# The depths each seat printed before the 2026-09-25 machinist review sized
# them at the .XX band's worst case: (label, seat, engagement, thread, drill).
_PRE_BAND_SEATS = (
    (
        "rocker support",
        part.HOLD_DOWN_SEAT_SPEC,
        part.HOLD_DOWN_ENGAGEMENT,
        part.HOLD_DOWN_ENGAGEMENT + 0.25,
        part.HOLD_DOWN_ENGAGEMENT + 0.25 + 5.0 * part.HOLD_DOWN_PITCH,
    ),
    ("cone pivot", part.PIVOT_SEAT_SPEC, part.PIVOT_THREAD_ENGAGEMENT, 9.775, 12.0),
    ("cone lock", part.LOCK_SEAT_SPEC, part.LOCK_STUD_LEN, 19.3, 25.65),
    # The seated #4-40 stop at the pre-band rule: thread = embed + 0.25,
    # drill = thread + five pitches.
    (
        "swing stop",
        part.STOP_SEAT_SPEC,
        part.STOP_ENGAGEMENT,
        part.STOP_ENGAGEMENT + 0.25,
        part.STOP_ENGAGEMENT + 0.25 + 5.0 * 25.4 / 40.0,
    ),
    ("spring foot", part.FOOT_SEAT_SPEC, part.FOOT_SCREW_LEN - part.SPRING_THICKNESS, 9.275, 11.3),
    ("pinion block", part.BLOCK_SEAT_SPEC, part.BLOCK_SCREW_LEN - part.BLOCK_HEIGHT, 12.75, 15.0),
)


@pytest.mark.parametrize(
    ("label", "seat", "engagement", "thread", "drill"),
    _PRE_BAND_SEATS,
    ids=[row[0] for row in _PRE_BAND_SEATS],
)
def test_pre_band_seat_depths_fail_at_the_printed_low_limit(
    label: str, seat, engagement: float, thread: float, drill: float
) -> None:
    # The 2026-09-25 Codex machinist review (hb-render-5): at the low limit of
    # its printed .XX band the E seats' thread let the screw tip into the
    # incomplete threads, as did four other seats; the pinion-block drill lost
    # its bottoming-tap lead at the worst case. Each old seat now fails.
    old = replace(seat, depth_mm=drill, overrides_mm={"ThreadDepth": thread})
    with pytest.raises(AssertionError, match="bottoms|tap lead|under 1.5D"):
        part.require_blind_seat_fit(label, old, engagement)


def test_seat_depths_derive_from_engagement_band_and_tap_lead() -> None:
    band = part.SEAT_DEPTH_BAND
    assert band == pytest.approx(0.51)  # the title block's .XX row
    assert part.HOLD_DOWN_THREAD_DEPTH == pytest.approx(13.20)
    assert part.HOLD_DOWN_DRILL_DEPTH == pytest.approx(20.60)
    for engagement, thread in (
        (part.HOLD_DOWN_ENGAGEMENT, part.HOLD_DOWN_THREAD_DEPTH),
        (part.PIVOT_THREAD_ENGAGEMENT, part.PIVOT_SCREW_HOLE_DEPTH),
        (part.LOCK_STUD_LEN, part.LOCK_SCREW_HOLE_DEPTH),
        (part.STOP_ENGAGEMENT, part.STOP_SCREW_HOLE_DEPTH),
        (part.FOOT_SCREW_LEN - part.SPRING_THICKNESS, part.FOOT_SCREW_HOLE_DEPTH),
    ):
        needed = engagement + part.SEAT_TIP_RESERVE + band
        assert needed <= thread < needed + part.SEAT_DEPTH_STEP


def test_no_seat_engages_under_one_and_a_half_d() -> None:
    # The retired 5/8 hold-down (1.456D) fails loud in its own seat.
    with pytest.raises(AssertionError, match="under 1.5D"):
        part.require_blind_seat_fit(
            "rocker support", part.HOLD_DOWN_SEAT_SPEC, 1.456 * 6.35
        )


def test_hold_down_is_the_specified_screw() -> None:
    import build_vn_lag_screw as screw

    assert screw.SKU == screw.SPECIFIED_SKU


def test_specified_hold_down_screw_fits_a_derived_seat_without_the_blocker() -> None:
    import build_vn_lag_screw as screw

    length, _replay = screw.REPLAYS[screw.SPECIFIED_SKU]
    assert length == 19.05  # 3/4 in under the head
    engagement = length - part.SUPPORT_FOOT_THICKNESS - part.HOLD_DOWN_BEARING_OFFSET
    diameter = part.THREAD_MAJOR_MM[part.HOLD_DOWN_THREAD]
    assert engagement >= 1.5 * diameter
    thread = part.seat_thread_depth(engagement)
    drill = part.seat_drill_depth(thread, part.HOLD_DOWN_THREAD, "tapped")
    seat = replace(
        part.HOLD_DOWN_SEAT_SPEC, depth_mm=drill, overrides_mm={"ThreadDepth": thread}
    )
    part.require_blind_seat_fit("specified rocker support", seat, engagement)
    # The deeper drill still leaves the upper pad 1.5 drill diameters of wall
    # under its point at the printed high limit.
    tap_drill = part.HOLD_DOWN_TAP_DRILL_DIA
    floor = (
        part.TOP_THICKNESS
        - (drill + part.SEAT_DEPTH_BAND)
        - tap_drill / 2.0 * part.DRILL_POINT_H
    )
    assert floor >= 1.5 * tap_drill


def test_cross_tap_drill_keeps_the_bottoming_lead_past_the_deepest_thread() -> None:
    from fr_frame_attachment_spec import CASTING_FULL_THREAD_DEPTH, CASTING_TAP_DRILL_DEPTH

    lead = 2.0 * 25.4 / 32.0
    # 48 MIN left 1.49 past 46.00 + 0.51, under two #10-32 pitches.
    assert 48.0 - (CASTING_FULL_THREAD_DEPTH + part.SEAT_DEPTH_BAND) < lead
    assert CASTING_TAP_DRILL_DEPTH - (CASTING_FULL_THREAD_DEPTH + part.SEAT_DEPTH_BAND) >= lead


# hb-render-6 sheet 2: the hole table's right edge, the TOP VIEW caption's
# bottom and the ORIGIN note's top, the neighbours of the socket-fit note.
HB_RENDER_6_TABLE_RIGHT_X_M = 0.1626
HB_RENDER_6_TOP_CAPTION_BOTTOM_Y_M = 0.2329
HB_RENDER_6_ORIGIN_NOTE_TOP_Y_M = 0.1866
SOCKET_FIT_MIN_MARGIN_M = 0.003


def test_socket_fit_note_sits_on_a2_between_the_table_and_the_plan() -> None:
    import draw_fr_harmonic_base as sheet

    # The note hangs off the A2 rim and keeps the acceptance criterion.
    assert sheet.SOCKET_FIT_STATION == (-197.0, -112.0)

    rows = [row.replace("<MOD-DIAM>", "D") for row in sheet.SOCKET_FIT_NOTE.split("\n")]
    x, y = sheet.SOCKET_FIT_NOTE_XY
    box = (
        x,
        y - len(rows) * sheet.NOTE_ROW_M,
        x + max(len(row) for row in rows) * sheet.NOTE_CHAR_M,
        y,
    )
    plan_left = sheet._plan_xy(
        -fr_harmonic_base_spec.BOTTOM_LENGTH / 2.0, 0.0, center=sheet.HOLE_TOP_CENTER
    )[0]
    margins = {
        "hole table": box[0] - HB_RENDER_6_TABLE_RIGHT_X_M,
        "plan west edge": plan_left - box[2],
        "TOP VIEW caption": HB_RENDER_6_TOP_CAPTION_BOTTOM_Y_M - box[3],
        "ORIGIN note": box[1] - HB_RENDER_6_ORIGIN_NOTE_TOP_Y_M,
    }
    assert {name: gap for name, gap in margins.items() if gap < SOCKET_FIT_MIN_MARGIN_M} == {}
    # The A2 rim sits level with the note's top rows, so the leader runs
    # nearly flat across the gap instead of down through the ORIGIN note.
    a2 = sheet._plan_xy(*sheet.SOCKET_FIT_STATION, center=sheet.HOLE_TOP_CENTER)
    assert box[1] < a2[1] < box[3]


# hb-render-5's sheet frame: the drawable region starts 12.7 mm in from the
# sheet's left edge (the frame obstacle the callout check logs).
SHEET_FRAME_INNER_X_M = 0.0127
FLANGE_FINISH_MIN_MARGIN_M = 0.0015


def test_flange_finish_fits_sheet_1_left_of_the_plan_with_named_margins() -> None:
    # Main's option A (2026-09-25): "FLANGE EDGES, 4 SIDES (TABLE ORIGIN)" is
    # too long for sheet 2's 50 mm strip, so the symbol sits in sheet 1's open
    # field left of the plan, leader on the west flange edge.
    import draw_fr_harmonic_base as sheet

    x, y = sheet.FLANGE_FINISH_XY

    def symbol_box(anchor, text):
        return (
            anchor[0] - sheet.FINISH_SYMBOL_VEE_LEFT_M,
            anchor[1],
            anchor[0] + sheet.FINISH_TARGET_OFFSET_M + len(text) * sheet.FINISH_TARGET_CHAR_M,
            anchor[1] + sheet.FINISH_SYMBOL_TOP_M,
        )

    box = symbol_box(sheet.FLANGE_FINISH_XY, fr_harmonic_base_spec.FLANGE_PERIMETER_TARGET)
    west_edge_x = sheet._plan_xy(-fr_harmonic_base_spec.BOTTOM_LENGTH / 2.0, 0.0)[0]
    margins = {
        "sheet frame": box[0] - SHEET_FRAME_INNER_X_M,
        "plan west flange edge": west_edge_x - box[2],
        # The deck Ra symbol below it at (0.040, 0.138) carries no target text.
        "deck Ra symbol": box[1] - (0.138 + sheet.FINISH_SYMBOL_TOP_M),
        # R22.2 FLANGE corner callout above it: its two-row block hangs from
        # (0.040, 0.215) down to ~0.2104 (hb-render-5 sheet 1).
        "flange corner radius callout": 0.2104 - box[3],
        # The stamped-ID note below the plan starts at x 0.080, y 0.130.
        "stamped-ID note": box[1] - sheet.SERIAL_NOTE_XY[1],
    }
    assert {name: gap for name, gap in margins.items() if gap < FLANGE_FINISH_MIN_MARGIN_M} == {}
    # The leader lands on the straight west edge (inside its R22.2 corners),
    # below the text row, so its run to the edge descends clear of the text.
    attach = sheet._plan_xy(-fr_harmonic_base_spec.BOTTOM_LENGTH / 2.0, sheet.FLANGE_FINISH_ATTACH_Z_MM)
    straight = fr_harmonic_base_spec.BOTTOM_WIDTH / 2.0 - part.FLANGE_CORNER_R
    assert abs(sheet.FLANGE_FINISH_ATTACH_Z_MM) < straight
    assert attach[1] < y


# The note's printed character advance and line pitch at the sheet's 3.5 text
# height (read off the pc-p1 render of the same note).
_NOTE_CHAR_MM = 2.69
_NOTE_LINE_MM = 4.58


def _rig_set_note_box(xy: tuple[float, float]) -> tuple[float, float, float, float]:
    import pinion_rig_fitup as fitup

    lines = fitup.RIG_SET_STEP.split("\n")
    width = max(len(line) for line in lines) * _NOTE_CHAR_MM / 1000.0
    height = len(lines) * _NOTE_LINE_MM / 1000.0
    return (xy[0], xy[1] - height, xy[0] + width, xy[1])


def test_rig_set_note_clears_the_sheet_2_callouts_table_and_views() -> None:
    """The pc-p1 eye pass read the RIG SET text over the hole table's column,
    the cross-tap callout and section arrow A.  The note's estimated box at
    RIG_SET_NOTE_XY clears hb-render-4's callouts and e0e287c83's table,
    views and labels; fail-first, the same box collides once moved onto the
    table or across to the cross-tap callout.  The build measures the note's
    read-back ink against every callout and obstacle the same way."""
    import draw_fr_harmonic_base as sheet

    obstacles = dict(E0E287C83_OBSTACLES)
    obstacles.update((f"callout {name}", box) for name, box in HB_RENDER_4_BOXES.items())

    def clashes(xy: tuple[float, float]) -> list[str]:
        return sheet.find_callout_clashes({sheet.RIG_SET_NOTE_LABEL: _rig_set_note_box(xy)}, obstacles)

    assert clashes(sheet.RIG_SET_NOTE_XY) == []
    on_table = clashes((sheet.RIG_SET_NOTE_XY[0], 0.140))
    assert any("table DetailItem460" in finding for finding in on_table), on_table
    on_cross_tap = clashes((0.120, sheet.RIG_SET_NOTE_XY[1]))
    assert any("MHA-VN-027 cross-tap" in finding for finding in on_cross_tap), on_cross_tap
    # The build check boxes the note's own ink, found by its text as read back.
    assert sheet.is_rig_set_note(sheet.RIG_SET_STEP.replace("\n", "\r\n") + "\r\n")
    assert not sheet.is_rig_set_note(sheet.TRANSFER_SPRING_CALLOUT)


