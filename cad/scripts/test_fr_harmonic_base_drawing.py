"""Offline contracts for the harmonic-base drawing."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

import _drawing_common
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
            "nameplate",
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
    # The seat is cut from the deck into the shallow boss hung under it.
    assert part.PIVOT_DRILL_BOTTOM_WALL == pytest.approx(
        part.STACK_HEIGHT
        - part.PIVOT_SEAT_SPEC.depth_mm
        - radius * DRILL_POINT_H
        - part.SHALLOW_BOSS_BOTTOM_Y
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
    assert part.LOCK_DRILL_BOTTOM_WALL == pytest.approx(
        part.STACK_HEIGHT - drill_tip_depth - part.DEEP_BOSS_BOTTOM_Y
    )
    assert part.LOCK_DRILL_BOTTOM_WALL >= 1.5 * part.LOCK_SCREW_HOLE_DIA
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
    # No mechanism shift applies (the plate anchors to the deck's west edge):
    # the stations are the pure mount-transform image of the plate holes.
    assert part.NAMEPLATE_SCREW_XZ == tuple(
        (fr_nameplate_spec.MOUNT_POS[0] - y, fr_nameplate_spec.MOUNT_POS[2] - x)
        for x, y in fr_nameplate_spec.SCREW_XY
    )
    # The plate's west edge sits 4.0 inside the deck's west edge (user ruling
    # 2026-10-09), the binding side of its footprint.
    assert part.NAMEPLATE_DECK_CLEARANCE == pytest.approx(
        fr_harmonic_base_spec.DECK_HALF_X - fr_nameplate_spec.MOUNT_POS[0]
    )
    assert part.NAMEPLATE_DECK_CLEARANCE == pytest.approx(4.0)
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
    # #743's solid bank puts those faces at -72.019 / +73.062 (the front one
    # 0.95 off the front washer for the #948 ruling R bank spring).
    expected = ((-54.7 + MECHANISM_X_SHIFT, -91.019), (-54.7 + MECHANISM_X_SHIFT, 92.062))
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
            (fr_harmonic_base_spec.GREEN_TOP - part.COLUMN_SOCKET_DEPTH) / 1000.0,
            z_mm / 1000.0 - radius,
            x_mm / 1000.0 + radius,
            fr_harmonic_base_spec.GREEN_TOP / 1000.0,
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
    through that wall and the socket's mouth on the green land -- the first
    placement sat 1 mm (on paper) from the cross tap's cosmetic thread and read
    as the tap's."""
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
    mouth_clearance = fr_harmonic_base_spec.GREEN_TOP - y_mm
    # The 2026-10-09 deck redesign opened the socket on the green land, 3.0
    # below the deck the old 4 mm margins measured to, leaving 7.68 mm of
    # wall between the window and the mouth: the point splits it evenly.
    assert tap_clearance == pytest.approx(mouth_clearance)
    assert min(tap_clearance, mouth_clearance) > 3.8
    assert y_mm > fr_harmonic_base_spec.GREEN_TOP - part.COLUMN_SOCKET_DEPTH


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
    # User ruling P1-2: nothing in the frame fixes the rig along the bank
    # until the fitter sets it, so both rig callouts name the RIG SET note that
    # states it (the drum's back end on leaf D off the north gear).
    assert sheet.TRANSFER_BLOCK_CALLOUT == "TRANSFER FROM MHA-DT-018\nAFTER RIG SET;\n"
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
    assert sheet.TRANSFER_PEDESTAL_CALLOUT == "TRANSFER FROM MHA-DT-002\nAT ASSEMBLY;\n"
    assert sheet.TRANSFER_SPRING_CALLOUT == "TRANSFER FROM MHA-DT-024\nAFTER RIG SET;"
    assert not any(tag.startswith("G") for tag in sheet.HOLE_TAG_POSITIONS)


def _deck_seat_features_in_build() -> dict[str, object]:
    """Each deck Hole Wizard seat feature build_harmonic_base cuts, name ->
    its stations: the named SupportHoldDownSeats call plus every row of the
    ``for tag, spec, xz, label in (...)`` seat-group loop."""
    import ast
    from pathlib import Path

    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    features: dict[str, object] = {"SupportHoldDownSeats": part.HOLE_XZ}
    named_cuts = {
        kw.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "wizard_holes"
        for kw in node.keywords
        if kw.arg == "name" and isinstance(kw.value, ast.Constant)
    }
    assert "SupportHoldDownSeats" in named_cuts
    loops = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.For, ast.AsyncFor))
        and isinstance(node.target, ast.Tuple)
        and [getattr(elt, "id", None) for elt in node.target.elts]
        == ["tag", "spec", "xz", "label"]
    ]
    assert len(loops) == 1
    for row in loops[0].iter.elts:
        tag, _spec, xz, _label = row.elts
        features[tag.value] = eval(ast.unparse(xz), vars(part))  # noqa: S307
    return features


def test_tapped_hole_note_count_is_derived_from_the_deck_seat_features() -> None:
    # warm-c486: the sheet removed 16 descriptive "Tapped Hole" notes against a
    # literal 14, because U34c split the two pedestal seats out of
    # FootScrewHoles into their own PedestalSeats feature. SolidWorks drops one
    # such note per deck seat FEATURE into each plan view, so the count is
    # derived from the same per-feature table that feeds the hole table.
    import ast
    from pathlib import Path

    import draw_fr_harmonic_base as sheet

    build_features = _deck_seat_features_in_build()
    names = [name for name, _stations, _dia in sheet.DECK_TAPPED_SEAT_FEATURES]
    assert len(names) == len(set(names))
    assert {name for name, _stations, _dia in sheet.DECK_TAPPED_SEAT_FEATURES} == set(
        build_features
    )
    for name, stations, _dia in sheet.DECK_TAPPED_SEAT_FEATURES:
        assert tuple(stations) == tuple(build_features[name]), name

    source = Path(sheet.__file__).read_text(encoding="utf-8")
    calls = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call)]
    plan_views = [
        call
        for call in calls
        if getattr(call.func, "id", None) == "place_view"
        and any(
            isinstance(arg, ast.Constant) and arg.value in ("*Top", "*Bottom")
            for arg in call.args
        )
    ]
    assert len(plan_views) == len(sheet.PLAN_VIEWS)
    assert sheet.TAPPED_HOLE_NOTES == len(build_features) * len(sheet.PLAN_VIEWS)
    assert sheet.TAPPED_HOLE_NOTES == 32

    finalize = [call for call in calls if getattr(call.func, "id", None) == "finalize_drawing"]
    assert len(finalize) == 1
    keywords = {kw.arg: kw.value for kw in finalize[0].keywords}
    # A literal count is what went stale; the call must name the derivation.
    assert ast.unparse(keywords["expected_redundant_notes"]) == "TAPPED_HOLE_NOTES"
    assert ast.unparse(keywords["redundant_note_substrings"]) == "FINAL_SHEET_REMOVED_NOTES"
    assert sheet.FINAL_SHEET_REMOVED_NOTES == (sheet.TAPPED_HOLE_NOTE,)
    assert sheet.TAPPED_HOLE_NOTE == "Tapped Hole"


def test_spotface_band_reaches_the_setter_unchanged() -> None:
    # The band now reads (upper, lower) like every _fit_limits band and goes
    # through deviations(); the setter must still receive (lower, upper) =
    # (0.0, +0.5), so the printed limits cannot move.
    import ast
    from pathlib import Path

    from _fit_limits import deviations

    assert fr_harmonic_base_spec.SPOTFACE_DEPTH_BAND_MM == (0.5, 0.0)
    assert deviations(fr_harmonic_base_spec.SPOTFACE_DEPTH_BAND_MM) == (0.0, 0.5)
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    setter_band_args = [
        ast.unparse(arg)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "set_dimension_bilateral_tolerance"
        for arg in node.args
        if isinstance(arg, ast.Starred)
    ]
    assert setter_band_args == ["*deviations(SPOTFACE_DEPTH_BAND_MM)"]


def test_isometric_render_hides_model_annotations_only_after_the_save(
    monkeypatch, tmp_path
) -> None:
    # warm-c486 eye pass: the part-owned surface-finish PMI rendered as
    # floating "A1-A4 BORES Ra 3.2" / "FLANGE EDGES, 4 SIDES" symbols. The
    # part must be saved (annotations shown) before the display toggle drops.
    import asyncio
    from types import SimpleNamespace

    events: list[tuple] = []

    async def fake_save(adapter, part_name, views=("isometric",)):
        events.append(("save", part_name, tuple(views)))
        return {"part": "p.SLDPRT", "stl": "p.STL"}

    class Extension:
        shown = True

        def SetUserPreferenceToggle(self, pref, option, value):
            events.append(("toggle", pref, option, value))
            self.shown = value
            return True

        def GetUserPreferenceToggle(self, pref, option):
            return self.shown

    extension = Extension()

    class Adapter:
        currentModel = SimpleNamespace(Extension=extension)

        async def export_image(self, request):
            events.append(("export", request["view_orientation"], extension.shown))
            return SimpleNamespace(is_success=True, data=None, error=None)

    monkeypatch.setattr(part, "save_part_and_images", fake_save)
    monkeypatch.setattr(part, "OUT_PNG", tmp_path)
    artefacts = asyncio.run(part._save_with_annotation_free_render(Adapter()))

    assert events == [
        ("save", part.PART_NAME, ()),
        ("toggle", 31, 0, False),  # swDisplayAnnotations, swDetailingNoOptionSpecified
        ("export", "isometric", False),
    ]
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
    import inspect
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
    source = inspect.getsource(sheet._check_hole_sheet_callouts)
    assert "obstacles = _sheet_frame_obstacles(adapter, ddoc)" in source


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
    assert sheet.FINAL_SHEET_REMOVED_NOTES == (sheet.TAPPED_HOLE_NOTE,)
    import ast
    import inspect
    from pathlib import Path

    tree = ast.parse(Path(sheet.__file__).read_text(encoding="utf-8"))
    finalize = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "finalize_drawing"
    )
    keywords = {kw.arg: ast.unparse(kw.value) for kw in finalize.keywords}
    assert keywords["redundant_note_substrings"] == "FINAL_SHEET_REMOVED_NOTES"
    source = inspect.getsource(sheet._check_hole_sheet_callouts)
    assert "text = _note_text(adapter, annotation)" in source
    assert "if not note_reaches_final_sheet(text):" in source


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


def test_hole_sheet_callout_check_skips_display_dimensions(monkeypatch) -> None:
    # layoutcal2 (harmonic_base-task.log:280): with #902 the dimension row
    # raised AttributeError on None.kind before any clash was measured.
    _drive_hole_sheet_callout_check(monkeypatch, (0.200, 0.200, 0.220, 0.210))


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


def test_hole_sheet_callout_check_runs_on_every_callout_before_finalize() -> None:
    import ast
    from pathlib import Path

    import draw_fr_harmonic_base as sheet

    tree = ast.parse(Path(sheet.__file__).read_text(encoding="utf-8"))
    build = next(
        node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    calls = [node for node in ast.walk(build) if isinstance(node, ast.Call)]
    check = [call for call in calls if getattr(call.func, "id", None) == "_check_hole_sheet_callouts"]
    assert len(check) == 1
    keywords = {kw.arg: kw.value for kw in check[0].keywords}
    assert ast.unparse(keywords["callouts"]) == "hole_sheet_callouts"
    assert ast.unparse(keywords["datum_origin"]) == "hole_feature.DatumOrigin"
    table = next(
        node
        for node in ast.walk(build)
        if isinstance(node, ast.Assign)
        and [ast.unparse(target) for target in node.targets] == ["hole_sheet_callouts"]
    )
    callout_names = {ast.unparse(value) for value in table.value.values}
    # Every callout's leader is moved to its nearer shoulder end before the check.
    side_loop = next(
        node
        for node in ast.walk(build)
        if isinstance(node, ast.For) and ast.unparse(node.iter) == "hole_sheet_callouts.items()"
    )
    assert "_attach_leader_nearest_hole(adapter, display, label)" in ast.unparse(side_loop)
    assert side_loop.lineno < check[0].lineno
    placed = {
        target.id
        for node in ast.walk(build)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "id", None) == "add_native_hole_callout"
        for target in node.targets
    }
    unassigned = [
        node
        for node in ast.walk(build)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "id", None) == "add_native_hole_callout"
    ]
    assert not unassigned  # every callout is kept, so every one is checked
    assert callout_names == placed == {
        "block_callout", "pedestal_callout", "spring_callout", "tap_callout"
    }
    assert {ast.unparse(value) for value in keywords["views"].values} == {
        "hole_top", "hole_side", "section"
    }
    finalize = next(call for call in calls if getattr(call.func, "id", None) == "finalize_drawing")
    assert check[0].lineno < finalize.lineno


@pytest.mark.parametrize(
    ("process_name", "expected_process_rows"),
    [
        ("TRANSFER_BLOCK_CALLOUT", "TRANSFER FROM MHA-DT-018\nAFTER RIG SET;\n"),
        ("TRANSFER_PEDESTAL_CALLOUT", "TRANSFER FROM MHA-DT-002\nAT ASSEMBLY;\n"),
        ("TRANSFER_SPRING_CALLOUT", "TRANSFER FROM MHA-DT-024\nAFTER RIG SET; "),
        ("CROSS_TAP_PROCESS", "THRU BOTH WALLS, SINGLE CONTINUOUS THREAD\n"),
    ],
)
def test_base_callout_prefix_is_the_shared_helpers(
    process_name: str, expected_process_rows: str
) -> None:
    # Main's hb-notes-2 ruling (a): the block and pedestal callouts end their
    # process text with a newline so the 8-32 thread gets its own fourth line;
    # the cross-tap thread gets its own row the same way. The spring callout
    # joins its thread with one space. add_native_hole_callout writes exactly
    # compose_hole_callout_prefix's result into the prefix DEFINITION.
    import draw_fr_harmonic_base as sheet

    native = "<hw-threaddesc> <hw-threadclass> <HOLE-DEPTH> <hw-threaddepth>"
    process = getattr(sheet, process_name)
    assert _drawing_common.compose_hole_callout_prefix(process, native) == (
        expected_process_rows + native
    )


def test_base_sheet_leaves_the_callout_prefix_to_the_shared_helper() -> None:
    # #877 cold build (drawing:harmonic_base, 2026-09-27): #937's sheet-local
    # line-break rewrite expected the old "process.rstrip() + ' '" joint and
    # raised on the "\n" joint compose_hole_callout_prefix now writes. The
    # prefix is composed in one place: this sheet never writes the prefix
    # compartment (swDimensionTextPrefix = 1) itself.
    import ast
    import inspect

    import draw_fr_harmonic_base as sheet

    prefix_writes = [
        ast.unparse(node)
        for node in ast.walk(ast.parse(inspect.getsource(sheet)))
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", "") == "SetText"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == 1
    ]
    assert prefix_writes == []


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


def test_cross_tap_callout_carries_hole_facts_only() -> None:
    # hb-render-4 eye pass: count/drill/depth, the thru instruction and the
    # thread each on a row; the depth datum is the model's (the tap starts on
    # the spotface floor) and the X location is a dimension, not text.
    import inspect

    import draw_fr_harmonic_base as sheet

    assert sheet.CROSS_TAP_PROCESS == "THRU BOTH WALLS, SINGLE CONTINUOUS THREAD\n"
    source = inspect.getsource(sheet)
    for gone in ("DEPTHS FROM SPOTFACE FLOOR\n", "ON A1-A4 X CENTRES\n", "2 EACH FRONT/REAR FACE"):
        assert gone not in source
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
    assert not hasattr(fr_harmonic_base_spec, "DRAWING_NOTES")
    # The bore now opens on the green land and reaches the pad's outer edge,
    # whose 1/16 in break (and its general band) is the land's last bite.
    for stack in part.COLUMN_SOCKET_LAND_STACKS.values():
        assert stack == pytest.approx({
            "nominal": 12.5,
            "flange length": -0.4,
            "pad length": -0.4,
            "bore location": -0.8,
            "matched bore": -0.25,
            "bore edge break": -0.25,
            "pad edge chamfer": -2.3875,
        })
        assert sum(stack.values()) == pytest.approx(8.0125)
    # The same stack on the rejected 1.6 mm pad land would fail the 1.0 MIN.
    assert sum(part.column_socket_land_stack(1.6).values()) < part.COLUMN_SOCKET_LAND_MIN
    # Main's rider: the Ø26.0 ceiling is a functional judgement, so the
    # stack reports how much bore the land could still absorb.
    assert part.COLUMN_SOCKET_BREAK_EVEN_BORE == pytest.approx(40.025)
    rejected = part.column_socket_land_stack(1.6)
    assert part.column_socket_break_even_bore(rejected) < part.COLUMN_SOCKET_MATCH_BORE_MAX


def test_underside_pocket_backs_every_deck_seat_at_the_worst_case() -> None:
    """User ruling 2026-10-09: the base is cored from below. Every blind deck
    seat ends in a boss hung from the pocket ceiling, on the shallow level
    unless that level cannot back it, and every wall holds policy rule 12."""
    spec = fr_harmonic_base_spec
    assert spec.POCKET_HALF_X == pytest.approx(spec.TOP_LENGTH / 2.0 - spec.POCKET_WALL)
    assert spec.POCKET_HALF_Z == pytest.approx(spec.TOP_WIDTH / 2.0 - spec.POCKET_WALL)
    assert spec.STACK_HEIGHT - spec.POCKET_CEILING_Y == pytest.approx(spec.POCKET_SKIN)
    labels = {seat.label for seat in part.HANGING_SEATS}
    assert labels == {
        "rocker support",
        "cone pivot",
        "cone lock",
        "swing stop",
        "pinion block",
        "spring foot",
        "pedestal hold-down",
        "nameplate",
    }
    for seat in part.HANGING_SEATS:
        part.require_hanging_boss(seat)
    # The deep seats really need the deep level (the spring foot sits deep
    # only because its boss would cross the north pinion-block pad).
    for label in ("rocker support", "cone lock", "pedestal hold-down"):
        seat = next(s for s in part.HANGING_SEATS if s.label == label)
        with pytest.raises(AssertionError):
            part.require_hanging_boss(
                replace(seat, boss_bottom_y=spec.SHALLOW_BOSS_BOTTOM_Y)
            )
    band = part._general_band_mm()
    assert min(part.CROSS_TAP_LUG_WALLS.values()) - 1.5 * band >= 2.0
    assert (
        part.CROSS_TAP_LUG_WALLS["past tip"]
        >= 1.5 * part.THREAD_MAJOR_MM[part.BASE_CROSS_TAP_SPEC.size]
    )
    assert part.SOCKET_BOSS_WALL == pytest.approx(8.0)


def test_hanging_volume_refuses_overlapping_shapes_in_one_sketch() -> None:
    disc = ("disc", 0.0, 50.0, 8.0)
    with pytest.raises(AssertionError, match="overlap"):
        part.hanging_volume((disc, ("disc", 10.0, 50.0, 8.0)), (), 28.0)
    # A shape on an earlier, deeper rib adds only its own plan area.
    on_rib = ("disc", 100.0, 0.0, 8.0)
    alone = part.hanging_volume((on_rib,), (), 28.0)
    assert alone == pytest.approx(
        math.pi * 64.0 * (part.POCKET_CEILING_Y - 28.0), rel=1e-6
    )
    shared = part.hanging_volume((on_rib,), (part.LONG_RIB_SHAPE,), 28.0)
    assert alone - shared == pytest.approx(
        part._disc_rect_area((100.0, 0.0), 8.0, (-216.25, 216.25), (-5.0, 5.0))
        * (part.POCKET_CEILING_Y - 28.0)
    )


def test_stamped_id_leader_clears_the_socket_bores() -> None:
    # 2026-09-25 Codex machinist review (hb-render-5, clarity): the stamped-ID
    # leader ran through the A3 socket bore. The leader starts where SolidWorks
    # put it on hb-render-5 (the last line's right end) and ends on the serial.
    import draw_fr_harmonic_base as sheet

    def leader(anchor: tuple[float, float], serial_xz: tuple[float, float]):
        start = (
            anchor[0] + sheet.SERIAL_LEADER_START_OFFSET_M[0],
            anchor[1] + sheet.SERIAL_LEADER_START_OFFSET_M[1],
        )
        return start, sheet._plan_xy(*serial_xz)

    def clearance(anchor: tuple[float, float], serial_xz: tuple[float, float]) -> float:
        start, tip = leader(anchor, serial_xz)
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

    # The reviewed sheet: through A3, to the serial on the old +X rim.
    assert clearance((0.125, 0.130), (218.75, 62.0)) < 0.0
    assert sheet.SERIAL_NOTE_XY == (0.100, 0.135)
    assert clearance(sheet.SERIAL_NOTE_XY, part.SERIAL_XZ) >= 0.004
    # The serial sits in the deck's NW corner, so the leader climbs across the
    # flange, pad and deck lower edges. Each width dimension right of the plan
    # starts its lower witness line where that edge's straight run ends at its
    # corner radius; the leader crosses every edge at least 1.5 mm left of it.
    start, tip = leader(sheet.SERIAL_NOTE_XY, part.SERIAL_XZ)
    for half_x, half_z, corner in (
        (part.DECK_HALF_X, part.DECK_HALF_Z, part.DECK_CORNER_R),
        (part.TOP_LENGTH / 2.0, part.TOP_WIDTH / 2.0, part.PAD_CORNER_R),
        (part.BOTTOM_LENGTH / 2.0, part.BOTTOM_WIDTH / 2.0, part.FLANGE_CORNER_R),
    ):
        witness_x, edge_y = sheet._plan_xy(half_x - corner, half_z)
        assert start[1] < edge_y < tip[1]
        rise = (edge_y - start[1]) / (tip[1] - start[1])
        crossing_x = start[0] + (tip[0] - start[0]) * rise
        assert crossing_x <= witness_x - 0.0015, (half_x, crossing_x, witness_x)


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
    # The deeper drill still leaves the deep boss under the deck 1.5 drill
    # diameters of wall under its point at the printed high limit.
    tap_drill = part.HOLD_DOWN_TAP_DRILL_DIA
    floor = (
        part.STACK_HEIGHT
        - (drill + part.SEAT_DEPTH_BAND)
        - tap_drill / 2.0 * part.DRILL_POINT_H
        - part.DEEP_BOSS_BOTTOM_Y
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

    # The note hangs off the A2 rim between the table and plan.
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

    assert fr_harmonic_base_spec.FLANGE_PERIMETER_TARGET == "FLANGE EDGES, 4 SIDES (TABLE ORIGIN)"
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
        # The stamped-ID note below the plan now starts right of this row.
        "stamped-ID note": sheet.SERIAL_NOTE_XY[0] - box[2],
    }
    assert {name: gap for name, gap in margins.items() if gap < FLANGE_FINISH_MIN_MARGIN_M} == {}
    # The leader lands on the straight west edge (inside its R22.2 corners),
    # below the text row, so its run to the edge descends clear of the text.
    attach = sheet._plan_xy(-fr_harmonic_base_spec.BOTTOM_LENGTH / 2.0, sheet.FLANGE_FINISH_ATTACH_Z_MM)
    straight = fr_harmonic_base_spec.BOTTOM_WIDTH / 2.0 - part.FLANGE_CORNER_R
    assert abs(sheet.FLANGE_FINISH_ATTACH_Z_MM) < straight
    assert attach[1] < y


def _pocket_shape_covers(shape: tuple, x: float, z: float) -> bool:
    if shape[0] == "disc":
        return math.hypot(x - shape[1], z - shape[2]) <= shape[3]
    return shape[1] <= x <= shape[2] and shape[3] <= z <= shape[4]


def test_underside_section_cuts_both_boss_heights_clear_of_every_bore() -> None:
    # B-B shows DeepBossBottom and ShallowBossBottom on bosses it actually
    # cuts, so its line must cross one of each -- and no hole, whose thread
    # would clutter the cut, and no socket boss, which fills the pocket.
    import draw_fr_harmonic_base as sheet

    x = sheet.UNDERSIDE_CUT_X
    assert x == pytest.approx(-28.67, abs=0.01)
    assert sheet._CUT_BAND[0] < x < sheet._CUT_BAND[1]
    for shapes in (part.DEEP_BOSS_SHAPES, part.SHALLOW_BOSS_SHAPES):
        assert any(sheet._x_span(s)[0] < x < sheet._x_span(s)[1] for s in shapes)
    assert all(abs(x - hx) > d / 2.0 for hx, _z, d in sheet.ALL_HOLES)
    assert all(abs(x - s[1]) > s[3] for s in part.SOCKET_BOSS_SHAPES)
    rib_x0, rib_x1 = sheet._x_span(part.LONG_RIB_SHAPE)
    assert rib_x0 < x < rib_x1


def test_underside_section_texts_sit_in_open_air() -> None:
    # Rule 8: dimension text outside silhouettes. The ceiling height sits in
    # the pocket's open air at the cut; the others left of the underside,
    # each level caption (DEEP/SHALLOW LEVEL) clear of the bench face.
    import draw_fr_harmonic_base as sheet

    x = sheet.UNDERSIDE_CUT_X
    spec = fr_harmonic_base_spec
    bottoms = (
        *((s, 0.0) for s in part.SOCKET_BOSS_SHAPES),
        (part.LONG_RIB_SHAPE, spec.RIB_RELIEF),
        (part.CROSS_RIB_SHAPE, spec.RIB_RELIEF),
        *((s, spec.DEEP_BOSS_BOTTOM_Y) for s in part.DEEP_BOSS_SHAPES),
        *((s, spec.SHALLOW_BOSS_BOTTOM_Y) for s in part.SHALLOW_BOSS_SHAPES),
        *((s, spec.SHALLOW_BOSS_BOTTOM_Y) for s in part.CROSS_TAP_LUG_SHAPES),
    )
    for name in ("PocketDepth",):
        y, z = sheet.UNDERSIDE_SECTION_TEXT_MM[name]
        assert 0.0 < y < fr_harmonic_base_spec.POCKET_CEILING_Y, name
        # A 2.5 mm text row is 5 mm of model at 1:2; keep 3 mm either side.
        assert abs(z) + 3.0 < fr_harmonic_base_spec.POCKET_HALF_Z, name
        for dz in (-3.0, 0.0, 3.0):
            covering = [b for s, b in bottoms if _pocket_shape_covers(s, x, z + dz)]
            assert all(y + 3.0 < b for b in covering), (name, dz, covering)
    num, den = sheet.UNDERSIDE_SECTION_SCALE
    for name in ("DeepBossBottom", "RibRelief", "ShallowBossBottom"):
        y = sheet.UNDERSIDE_SECTION_TEXT_MM[name][0]
        rows = ["00.0", *sheet.UNDERSIDE_SECTION_CALLOUTS.get(name, "").split("\n")]
        half_w_mm = max(map(len, rows)) * _DIM_CHAR_M * 1000.0 / 2.0
        assert half_w_mm + 2.0 < -y * num / den, name
    assert set(sheet.UNDERSIDE_SECTION_CALLOUTS) <= set(sheet.UNDERSIDE_SECTION_TEXT_MM)


def test_underside_sheet_views_fit_the_border_clear_of_each_other() -> None:
    import draw_fr_harmonic_base as sheet

    assert sheet.SHEET_NAMES[2] == "UNDERSIDE"
    bottom = (
        *sheet._bottom_xy(
            -fr_harmonic_base_spec.BOTTOM_LENGTH / 2.0,
            fr_harmonic_base_spec.BOTTOM_FRONT_Z,
        ),
        *sheet._bottom_xy(
            fr_harmonic_base_spec.BOTTOM_LENGTH / 2.0,
            fr_harmonic_base_spec.BOTTOM_REAR_Z,
        ),
    )
    cut_x = sheet._bottom_xy(sheet.UNDERSIDE_CUT_X, 0.0)[0]
    assert bottom[0] < cut_x < bottom[2]
    # B-B turned clockwise: machine +Y right, Z along the sheet's height, at
    # its scale, with the outside texts at UNDERSIDE_OUTSIDE_Y_MM left of it.
    num, den = sheet.UNDERSIDE_SECTION_SCALE
    s = num / den / 1000.0
    cx, cy = sheet.UNDERSIDE_SECTION_CENTER
    half_h = fr_harmonic_base_spec.STACK_HEIGHT * s / 2.0
    half_z = fr_harmonic_base_spec.BOTTOM_REAR_Z * s
    # The outside texts' widest row: the level captions under 12.0 and 28.0.
    widest = max(
        len(row)
        for text in sheet.UNDERSIDE_SECTION_CALLOUTS.values()
        for row in text.split("\n")
    )
    section = (
        cx - half_h + sheet.UNDERSIDE_OUTSIDE_Y_MM * s - widest * _DIM_CHAR_M / 2.0,
        cy - half_z,
        cx + half_h,
        cy + half_z,
    )
    assert section[0] - bottom[2] > 0.020
    assert section[0] > SHEET_FRAME_INNER_X_M
    assert section[3] < 0.2794 - 0.0127
    # bp3 render: "SECTION B-B / ROTATED 90 DEG CW SCALE 1:2" hangs 31.2 mm
    # under the cut's lowest edge; at y 0.160 it ran into the title block.
    caption_drop = 0.0312
    assert section[1] - caption_drop > 0.066 + 0.002  # title block top


def test_underside_round_boss_diameters_name_their_level_and_holes() -> None:
    # bp3 machinist review: one "11X ROUND BOSSES" callout read every boss as
    # shallow (28.0) and found 2.2 mm under E1-E4's drills. One diameter per
    # cast level names the holes it backs and the level, which section B-B
    # prints under the model's own DeepBossBottom and ShallowBossBottom.
    import draw_fr_harmonic_base as sheet

    spec = fr_harmonic_base_spec
    seats = {seat.label: seat for seat in part.HANGING_SEATS}
    for label in ("rocker support", "spring foot"):
        assert seats[label].boss_bottom_y == spec.DEEP_BOSS_BOTTOM_Y, label
    for label in ("cone pivot", "swing stop", "nameplate"):
        assert seats[label].boss_bottom_y == spec.SHALLOW_BOSS_BOTTOM_Y, label
    assert part.DEEP_BOSS_CENTRES == (*part.HOLE_XZ, *part.FOOT_SCREW_XZ)
    assert part.SHALLOW_BOSS_CENTRES == (
        part.PIVOT_SCREW_XZ,
        part.STOP_SCREW_XZ,
        *part.NAMEPLATE_SCREW_XZ,
    )
    callouts = sheet.UNDERSIDE_BOTTOM_CALLOUTS
    assert callouts["HangingBossDia"] == "5X BOSSES UNDER\nE1-E4, MHA-DT-024\nTO DEEP LEVEL"
    assert callouts["ShallowBoss4Dia"] == "6X BOSSES UNDER\nB1, D1, F1-F4\nTO SHALLOW LEVEL"
    assert sheet.UNDERSIDE_SECTION_CALLOUTS == {
        "DeepBossBottom": "DEEP\nLEVEL",
        "ShallowBossBottom": "SHALLOW\nLEVEL",
    }
    # The leaders land on E1's boss and the rear-west nameplate tap's, both
    # in the view's top-right quarter (+Z up), so they drop from the texts.
    e1 = part.HOLE_XZ[0]
    rear_west_plate = part.SHALLOW_BOSS_CENTRES[4]
    assert e1[1] > 0.0 and rear_west_plate[1] > 0.0
    assert rear_west_plate == min(
        (xz for xz in part.NAMEPLATE_SCREW_XZ if xz[1] > 0.0), key=lambda xz: xz[0]
    )
    # Sheet-3 texts above the view: inside the border, clear of the view, of
    # each other and of the view's note.
    keep = sheet.UNDERSIDE_BOTTOM_KEEP
    view_top = sheet._bottom_xy(0.0, spec.BOTTOM_REAR_Z)[1]
    boxes = {}
    for name, value in (
        ("CrossRibThickness", "10.0"),
        ("HangingBossDia", "D16.0"),
        ("ShallowBoss4Dia", "D16.0"),
    ):
        rows = [value, *callouts[name].split("\n")]
        x, y = keep[name]
        half_w = max(map(len, rows)) * _NOTE_CHAR_MM / 2000.0
        half_h = len(rows) * _NOTE_LINE_MM / 2000.0
        boxes[name] = (x - half_w, y - half_h, x + half_w, y + half_h)
        assert boxes[name][1] > view_top + 0.010, name
        assert boxes[name][3] < _BORDER_INNER_M[3] - 0.002, name
    nx, ny = sheet.UNDERSIDE_BOTTOM_NOTE_XY
    boxes["note"] = (nx, ny - _NOTE_LINE_MM / 1000.0, nx + 21 * _NOTE_CHAR_MM / 1000.0, ny)
    for a in boxes:
        for b in boxes:
            if a < b:
                assert _box_gap(boxes[a], boxes[b]) > 0.0015, (a, b)
    # The cross rib's text reads west of the rib, clear above the B arrow.
    rib_west = sheet._bottom_xy(part.CROSS_RIB_SHAPE[1], 0.0)[0]
    assert boxes["CrossRibThickness"][2] < rib_west - 0.005


def test_drawing_keeps_partition_the_part_precision_map() -> None:
    # assert_imported_precision proves every printed dimension at the end of
    # the build; the seven keeps must name each map entry exactly once.
    import draw_fr_harmonic_base as sheet

    keeps = (
        sheet.GEOMETRY_TOP_KEEP,
        sheet.SIDE_KEEP,
        sheet.HOLE_TOP_KEEP,
        sheet.SECTION_KEEP,
        sheet.HOLE_SIDE_KEEP,
        sheet.UNDERSIDE_BOTTOM_KEEP,
        sheet.UNDERSIDE_PADS_KEEP,
        sheet.UNDERSIDE_SECTION_TEXT_MM,
    )
    names = [name for keep in keeps for name in keep]
    assert len(names) == len(set(names))
    assert set(names) == set(fr_harmonic_base_spec.DRAWING_PRECISION_BY_NAME)
    assert set(sheet.UNDERSIDE_BOTTOM_CALLOUTS) <= set(sheet.UNDERSIDE_BOTTOM_KEEP)


# Sheet text as boxes: 3.5 mm rows, and a generous 2.5 mm a character.
_DIM_TEXT_H_M = 0.0035
_DIM_CHAR_M = 0.0025
_BORDER_INNER_M = (0.0127, 0.0127, 0.4191, 0.2667)
_TITLE_BLOCK_M = (0.216, 0.0, 0.4318, 0.066)


def _box_gap(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """Clear distance between two (x0, y0, x1, y1) boxes; 0 when they touch."""
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return math.hypot(dx, dy)


def _segment_box_gap(segment: tuple[tuple[float, float], ...], box: tuple[float, ...]) -> float:
    (x0, y0), (x1, y1) = segment
    return min(
        _box_gap((x, y, x, y), box)
        for t in (i / 400.0 for i in range(401))
        for x, y in [(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)]
    )


def _pads_vertices() -> dict[str, tuple[float, float]]:
    """Machine (X, Z) of the point each sheet-4 baseline dimension reaches."""
    lock = part.LOCK_PAD_SHAPE
    ped0, ped1 = part.PEDESTAL_PAD_SHAPES
    block0, block1 = part.BLOCK_PAD_SHAPES
    lug0, lug1, _lug2, lug3 = part.CROSS_TAP_LUG_SHAPES
    long_rib, cross_rib = part.LONG_RIB_SHAPE, part.CROSS_RIB_SHAPE
    (foot,) = part.FOOT_SCREW_XZ
    return {
        "Lug1X": (lug1[2], lug1[3]),
        "LockPadX": (lock[1], lock[4]),
        "PedestalPad1X": (ped1[1], ped1[4]),
        "BlockPad1X": (block1[1], block1[4]),
        "CrossRibX": (cross_rib[1], cross_rib[4]),
        "Lug3X": (lug3[1], lug3[3]),
        "PedestalPad1Y": (ped1[1], ped1[4]),
        "BlockPad1Y": (block1[1], block1[4]),
        "Lug1Y": (lug1[2], lug1[3]),
        "LongRibY": (long_rib[1], long_rib[4]),
        "Lug0Y": (lug0[2], lug0[4]),
        "PedestalPad0Y": (ped0[1], ped0[4]),
        "BlockPad0Y": (block0[1], block0[3]),
        "LockPadY": (lock[1], lock[4]),
        "FootBossX": foot,
        "FootBossY": foot,
    }


def _pads_printed() -> dict[str, float]:
    spec = fr_harmonic_base_spec
    lock = part.LOCK_PAD_SHAPE
    ped0 = part.PEDESTAL_PAD_SHAPES[0]
    block0 = part.BLOCK_PAD_SHAPES[0]
    printed = {
        name: (x + spec.BOTTOM_LENGTH / 2.0) if name.endswith("X") else (spec.BOTTOM_REAR_Z - z)
        for name, (x, z) in _pads_vertices().items()
    }
    printed |= {
        "LockPadWidth": lock[2] - lock[1],
        "PedestalPadLength": ped0[4] - ped0[3],
        "PedestalPad0Width": ped0[2] - ped0[1],
        "BlockPad0Width": block0[4] - block0[3],
    }
    return printed


def test_underside_pads_sheet_prints_each_pad_and_lug_from_x0_y0() -> None:
    # Codex P2 on #1310: the 33 mm block pads, 26 mm pedestal pads, cone-lock
    # pad and 27 x 37 mm lugs printed no size or place; the bp3 machinist
    # review: nor did the ribs or the MHA-DT-024 foot boss. Sheet 4 prints
    # them from the hole table's X0 Y0, shortest baseline innermost.
    import draw_fr_harmonic_base as sheet

    spec = fr_harmonic_base_spec
    assert sheet.SHEET_NAMES[3] == "UNDERSIDE-PADS"
    marked = {name for names in spec.UNDERSIDE_PAD_DIMENSIONS.values() for name in names}
    assert set(sheet.UNDERSIDE_PADS_KEEP) == marked
    for feature, names in spec.UNDERSIDE_PAD_DIMENSIONS.items():
        assert set(names) <= spec.DRAWING_DIMENSIONS[feature]
    assert {feature for feature, _name in spec.UNDERSIDE_PAD_PREFIXES} <= set(
        spec.UNDERSIDE_PAD_DIMENSIONS
    )
    assert {name for _feature, name in spec.UNDERSIDE_PAD_PREFIXES} <= marked
    printed = {name: round(value, 1) for name, value in _pads_printed().items()}
    assert printed == {
        "Lug1X": 39.6,
        "LockPadX": 120.5,
        "PedestalPad1X": 160.2,
        "BlockPad1X": 197.7,
        "CrossRibX": 223.6,
        "Lug3X": 417.6,
        "PedestalPad1Y": 38.5,
        "BlockPad1Y": 48.3,
        "Lug1Y": 68.6,
        "LongRibY": 138.6,
        "Lug0Y": 218.6,
        "PedestalPad0Y": 221.6,
        "BlockPad0Y": 237.2,
        "LockPadY": 247.6,
        "FootBossX": 194.2,
        "FootBossY": 67.2,
        "LockPadWidth": 16.0,
        "PedestalPadLength": 26.0,
        "PedestalPad0Width": 16.0,
        "BlockPad0Width": 16.0,
    }
    # The table's X0 Y0 is the flange's rear-west corner, top left here.
    assert sheet.PADS_DATUM == pytest.approx(
        sheet._pads_xy(-spec.BOTTOM_LENGTH / 2.0, spec.BOTTOM_REAR_Z)
    )
    for baselines in (sheet.PADS_X_ROWS, sheet.PADS_Y_COLUMNS):
        values = [printed[name] for name, *_ in baselines]
        assert values == sorted(values)


def test_underside_pads_texts_fit_the_border_clear_of_each_other_and_every_line() -> None:
    import draw_fr_harmonic_base as sheet

    spec = fr_harmonic_base_spec
    prefixes = {name: prefix for (_f, name), prefix in spec.UNDERSIDE_PAD_PREFIXES.items()}
    printed = _pads_printed()
    # A vertical size whose text reads beyond its span hangs the text WEST of
    # its dimension line (at the keep X) over a shoulder line, as measured on
    # the 13f1ca261 sheet-4 render: 1.3 mm from the line, 2.3 mm a glyph
    # ("2X 26.0" 15.9 mm, "2X 16.0" 15.6 mm), the shoulder 0.8 mm under the
    # text and 1.3 mm past its far end.
    hanging = ("PedestalPadLength", "BlockPad0Width")
    hang_gap, glyph, shoulder_drop = 0.0013, 0.0023, 0.0008
    boxes = {}
    for name, (x, y) in sheet.UNDERSIDE_PADS_KEEP.items():
        chars = len(f"{prefixes.get(name, '')}{printed[name]:.1f}")
        if name in hanging:
            right = x - hang_gap
            boxes[name] = (right - chars * glyph, y - _DIM_TEXT_H_M / 2.0, right, y + _DIM_TEXT_H_M / 2.0)
            continue
        half_w = chars * _DIM_CHAR_M / 2.0
        boxes[name] = (x - half_w, y - _DIM_TEXT_H_M / 2.0, x + half_w, y + _DIM_TEXT_H_M / 2.0)
    view = (
        *sheet._pads_xy(-spec.BOTTOM_LENGTH / 2.0, spec.BOTTOM_FRONT_Z),
        *sheet._pads_xy(spec.BOTTOM_LENGTH / 2.0, spec.BOTTOM_REAR_Z),
    )
    # Sheet 4 notes: one view, its texts and the caption all inside the
    # border, off the title block.
    rows = sheet.PADS_NOTE.split("\n")
    note = (
        sheet.PADS_NOTE_XY[0],
        sheet.PADS_NOTE_XY[1] - len(rows) * _NOTE_LINE_MM / 1000.0,
        sheet.PADS_NOTE_XY[0] + max(map(len, rows)) * _NOTE_CHAR_MM / 1000.0,
        sheet.PADS_NOTE_XY[1],
    )
    for label, box in {"view": view, "note": note, **boxes}.items():
        assert _BORDER_INNER_M[0] + 0.002 < box[0], label
        assert _BORDER_INNER_M[1] + 0.002 < box[1], label
        assert box[2] < _BORDER_INNER_M[2] - 0.002, label
        assert box[3] < _BORDER_INNER_M[3] - 0.002, label
        assert _box_gap(box, _TITLE_BLOCK_M) > 0.002, label
    baselines = {name for name, *_ in (*sheet.PADS_X_ROWS, *sheet.PADS_Y_COLUMNS)}
    for name in baselines:
        assert _box_gap(boxes[name], view) > 0.002, name
    labelled = {"note": note, **boxes}
    for a in labelled:
        for b in labelled:
            if a < b:
                assert _box_gap(labelled[a], labelled[b]) > 0.0015, (a, b)

    # Every printed line: the baselines' extension and dimension lines, and
    # the sizes' (extension lines run 2 mm past their dimension line).
    over = 0.002
    datum = sheet.PADS_DATUM
    vertices = {name: sheet._pads_xy(*xz) for name, xz in _pads_vertices().items()}
    lines: dict[str, list[tuple[tuple[float, float], tuple[float, float]]]] = {}
    for name, _x in sheet.PADS_X_ROWS:
        (vx, vy), (tx, ty) = vertices[name], sheet.UNDERSIDE_PADS_KEEP[name]
        lines[name] = [((vx, vy), (vx, ty + over)), ((datum[0], ty), (max(vx, tx), ty))]
    for name, *_ in sheet.PADS_Y_COLUMNS:
        (vx, vy), (tx, ty) = vertices[name], sheet.UNDERSIDE_PADS_KEEP[name]
        # Inside its own span, between X0 and the station.
        assert vy + _DIM_TEXT_H_M < ty < datum[1] - _DIM_TEXT_H_M, name
        lines[name] = [((vx, vy), (tx - over, vy)), ((tx, datum[1]), (tx, vy))]
    # The foot boss's baselines run inside the view: the X one's extension
    # lines drop from X0 Y0 (along the flange's west edge) and from the boss
    # centre to its dimension line; the Y one's run east from X0 Y0 (along the
    # rear edge) and west from the centre to its dimension line.
    (fx, fy) = vertices["FootBossX"]
    tx, ty = sheet.UNDERSIDE_PADS_KEEP["FootBossX"]
    assert datum[0] < tx < fx and ty < fy, "FootBossX"
    lines["FootBossX"] = [
        (datum, (datum[0], ty - over)),
        ((fx, fy), (fx, ty - over)),
        ((datum[0], ty), (fx, ty)),
    ]
    tx, ty = sheet.UNDERSIDE_PADS_KEEP["FootBossY"]
    assert datum[0] < tx < fx and fy < ty < datum[1], "FootBossY"
    lines["FootBossY"] = [
        (datum, (tx + over, datum[1])),
        ((fx, fy), (tx - over, fy)),
        ((tx, fy), (tx, datum[1])),
    ]
    assert set(sheet.PADS_INLINE_TEXT_MM) == {"FootBossX", "FootBossY"}
    lock = part.LOCK_PAD_SHAPE
    ped0 = part.PEDESTAL_PAD_SHAPES[0]
    block0 = part.BLOCK_PAD_SHAPES[0]
    # bp3 machinist review: the horizontal sizes read outside the silhouette.
    for name in sheet.PADS_SIZE_BELOW_MM:
        assert boxes[name][3] < view[1] - 0.002, name
    for name, (x0, x1, z, side) in {
        "LockPadWidth": (lock[1], lock[2], lock[4], "across"),
        "PedestalPad0Width": (ped0[1], ped0[2], ped0[3], "across"),
    }.items():
        tx, ty = sheet.UNDERSIDE_PADS_KEEP[name]
        (ax, ay), (bx, _by) = sheet._pads_xy(x0, z), sheet._pads_xy(x1, z)
        reach = ty + math.copysign(over, ty - ay)
        lines[name] = [
            ((ax, ay), (ax, reach)),
            ((bx, ay), (bx, reach)),
            ((min(ax, tx), ty), (max(bx, tx), ty)),
        ]
    for name, (x, z0, z1) in {
        "PedestalPadLength": (ped0[1], ped0[3], ped0[4]),
        "BlockPad0Width": (block0[1], block0[3], block0[4]),
    }.items():
        tx, ty = sheet.UNDERSIDE_PADS_KEEP[name]
        (ax, ay), (_bx, by) = sheet._pads_xy(x, z0), sheet._pads_xy(x, z1)
        # Beyond the span (so hung), west of the measured side.
        assert ty - _DIM_TEXT_H_M / 2.0 - shoulder_drop > max(ay, by), name
        assert tx < ax, name
        shoulder_y = ty - _DIM_TEXT_H_M / 2.0 - shoulder_drop
        reach = tx + math.copysign(over, tx - ax)
        lines[name] = [
            ((ax, ay), (reach, ay)),
            ((ax, by), (reach, by)),
            ((tx, min(ay, shoulder_y)), (tx, max(by, shoulder_y))),
            ((boxes[name][0] - hang_gap, shoulder_y), (tx, shoulder_y)),
        ]
    assert set(lines) == set(boxes)
    for name, box in boxes.items():
        for other, segments in lines.items():
            if other == name:
                continue
            for segment in segments:
                assert _segment_box_gap(segment, box) > 0.001, (name, other, segment)

    # The in-view texts read in the pocket's open air, clear of every boss,
    # pad, lug and rib by 2 mm of model.
    solids = (
        *part.DEEP_BOSS_SHAPES,
        *part.SHALLOW_BOSS_SHAPES,
        *part.CROSS_TAP_LUG_SHAPES,
        *part.SOCKET_BOSS_SHAPES,
        part.LONG_RIB_SHAPE,
        part.CROSS_RIB_SHAPE,
    )
    scale = sheet._PADS_M_PER_MM
    for name in (*sheet.PADS_SIZE_TEXT_MM, *sheet.PADS_INLINE_TEXT_MM):
        x0, z0, x1, z1 = (
            (boxes[name][0] - sheet.PADS_CENTER[0]) / scale - 2.0,
            (boxes[name][1] - sheet.PADS_CENTER[1]) / scale - 2.0,
            (boxes[name][2] - sheet.PADS_CENTER[0]) / scale + 2.0,
            (boxes[name][3] - sheet.PADS_CENTER[1]) / scale + 2.0,
        )
        assert -spec.POCKET_HALF_X < x0 and x1 < spec.POCKET_HALF_X, name
        assert -spec.POCKET_HALF_Z < z0 and z1 < spec.POCKET_HALF_Z, name
        for shape in solids:
            if shape[0] == "disc":
                nearest = (min(max(shape[1], x0), x1), min(max(shape[2], z0), z1))
                assert math.dist(nearest, shape[1:3]) > shape[3], (name, shape)
            else:
                assert x1 < shape[1] or shape[2] < x0 or z1 < shape[3] or shape[4] < z0, (
                    name,
                    shape,
                )


def test_nameplate_tags_read_clear_of_section_a_and_of_every_other_tag() -> None:
    # ec323b4eb leaf: F3's and F4's leaders crossed section line A and each
    # other; ab1f78504 leaf: the tags stacked in one column within a row pitch
    # of each other and of E4 (enforced merged-blocks). The west tags read in
    # the four-tap quad, the east tags between the deck's east edge and
    # section line A; any two tags whose columns overlap stand a row pitch
    # (1.543 text heights, 5.4 mm at 3.5 mm) apart.
    import draw_fr_harmonic_base as sheet

    spec = fr_harmonic_base_spec
    half_h = sheet._HOLE_TAG_HALF_HEIGHT_M
    tag_w = 2 * _DIM_CHAR_M
    row_pitch = 5.556 / 3.5 * 2 * half_h
    section_x = sheet._plan_xy(spec.COLUMN_X, 0.0, center=sheet.HOLE_TOP_CENTER)[0]
    deck_east = sheet._plan_xy(part.DECK_HALF_X, 0.0, center=sheet.HOLE_TOP_CENTER)[0]
    centre_x = sum(x for x, _ in part.NAMEPLATE_SCREW_XZ) / len(part.NAMEPLATE_SCREW_XZ)
    taps = [
        sheet._plan_xy(x, z, center=sheet.HOLE_TOP_CENTER) for x, z in part.NAMEPLATE_SCREW_XZ
    ]
    tags = []
    for (x, z), tap in zip(part.NAMEPLATE_SCREW_XZ, taps, strict=True):
        table = (x + spec.BOTTOM_LENGTH / 2.0, spec.BOTTOM_REAR_Z - z)
        left, top = sheet._nameplate_tag_position(table)
        box = (left, top - 2 * half_h, left + tag_w, top)
        if x > centre_x:
            assert deck_east + 0.001 < box[0] and box[2] < section_x - 0.001
        else:
            assert tap[0] < box[0] and box[2] < deck_east - 0.001
        # The leader leaves the box's west side and ends on its tap; judged
        # to 1 mm short of the centre, where the arrowhead lands on the tap.
        start = (box[0], top - half_h)
        length = math.dist(start, tap)
        end = tuple(s + (t - s) * (length - 0.001) / length for s, t in zip(start, tap))
        tags.append((box, (start, end)))
    assert sheet._nameplate_tag_position((0.0, 0.0)) is None
    others = [
        (x, y - 2 * half_h, x + tag_w, y) for x, y in sheet.HOLE_TAG_POSITIONS.values()
    ]
    radius = part.NAMEPLATE_SCREW_HOLE_DIA * sheet.VIEW_SCALE / 2000.0
    boxes = [box for box, _ in tags] + others
    for other in others:
        for hole in taps:
            assert _box_gap(other, (hole[0], hole[1], hole[0], hole[1])) > radius + 0.0008, other
    for i, (box, leader) in enumerate(tags):
        for hole in taps:
            assert _box_gap(box, (hole[0], hole[1], hole[0], hole[1])) > radius + 0.0008
        for j, other in enumerate(boxes):
            if j == i:
                continue
            assert _segment_box_gap(leader, other) > 0.0003, (i, other)
            if min(box[2], other[2]) > max(box[0], other[0]):  # one column
                gap = max(box[1] - other[3], other[1] - box[3])
                assert gap > row_pitch + 0.0003, (i, other, gap)
        for _other_box, other_leader in tags[i + 1 :]:
            (ax, ay), (bx, by) = leader
            (cx, cy), (dx, dy) = other_leader
            cross = lambda px, py, qx, qy, rx, ry: (qx - px) * (ry - py) - (qy - py) * (rx - px)  # noqa: E731
            assert not (
                cross(ax, ay, bx, by, cx, cy) * cross(ax, ay, bx, by, dx, dy) < 0
                and cross(cx, cy, dx, dy, ax, ay) * cross(cx, cy, dx, dy, bx, by) < 0
            )


def test_rig_callouts_name_the_rig_set_note() -> None:
    # User ruling P1-2 (pc-p1 eye pass): printed on the callouts, the RIG SET
    # step ran the block callout through the top border and over the TOP VIEW
    # caption. Each rig callout keeps its first line and swaps "AT ASSEMBLY;"
    # for the note's name; the pedestal seats are not rig seats. Where the note
    # lands is proved by the test below and measured at build time.
    import draw_fr_harmonic_base as sheet
    import pinion_rig_fitup as fitup

    for text in (sheet.TRANSFER_BLOCK_CALLOUT, sheet.TRANSFER_SPRING_CALLOUT):
        lines = text.rstrip("\n").split("\n")
        assert len(lines) == 2, text
        assert lines[1] == sheet.TRANSFER_AFTER_RIG_SET
        assert fitup.RIG_SET_NAME in lines[1]
    assert sheet.TRANSFER_AFTER_RIG_SET == "AFTER RIG SET;"
    assert "RIG SET" not in sheet.TRANSFER_PEDESTAL_CALLOUT
    note = fitup.RIG_SET_STEP.split("\n")
    assert note[0].startswith(fitup.RIG_SET_NAME + ",")
    # The note carries every setting the transfers need, the front block's
    # feeler included: it fixes FRONT_BLOCK_Z0, so the front seats with it
    # (Codex #858, PRRT_kwDOPHDy386mUjhS).
    feeler = f"FRONT MHA-DT-018 {fitup.FRONT_BLOCK_FEELER:.2f} LEAF OFF FRONT MHA-DT-014;"
    assert feeler in note
    assert note.index(feeler) == 1
    assert "1.00 + 0.25 LEAVES OFF" in fitup.RIG_SET_STEP
    assert "BANK PUSHED NORTH" in fitup.RIG_SET_STEP
    assert "MHA-DT-024 PAD 0.65 LEAF OFF MHA-DT-018." in fitup.RIG_SET_STEP


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
    import inspect

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
    source = inspect.getsource(sheet._check_hole_sheet_callouts)
    assert "boxes[RIG_SET_NOTE_LABEL] = element.box" in source


def test_base_blanks_its_reference_sketches_through_the_shared_helper() -> None:
    # Main (restricted review of #858): one blanking helper in _common, traced
    # like every other per-operation helper, and no local copy in the base.
    import inspect

    import _common

    source = inspect.getsource(part)
    blank = "blank_reference_sketches(adapter, REFERENCE_SKETCHES)"
    assert "def _hide_reference_sketches" not in source
    assert source.count(blank) == 1
    assert part.REFERENCE_SKETCHES == ("HeightReference", "CrossTapReference")
    assert hasattr(_common.blank_reference_sketches, "__wrapped__")
