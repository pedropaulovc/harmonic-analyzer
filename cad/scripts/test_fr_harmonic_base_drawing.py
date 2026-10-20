"""Offline contracts for the harmonic-base drawing."""

from __future__ import annotations

from dataclasses import replace
import math

import pytest

import _drawing_hole_callout
import build_fr_harmonic_base as part
import cone_line
import dt_cone_pivot_post_installation
import dt_cone_swing_platform_geometry as platform
from dt_drive_train_steps import step_ref
import fr_harmonic_base_fasteners
import fr_harmonic_base_spec
from dt_vn_cone_lock_knob_spec import HEAD_DIA as KNOB_HEAD_DIA
from dt_vn_swing_stop_screw_spec import CONTACT_DIA as STOP_CONTACT_DIA


def test_all_eighteen_deck_seats_are_native_through_taps_at_the_retained_stations() -> None:
    from _hole_spec import TAP_DRILL_MM

    expected = {
        "SupportHoldDownSeats": (part.HOLD_DOWN_SEAT_SPEC, part.HOLE_XZ, "1/4-20", 4),
        "PivotSeat": (part.PIVOT_SEAT_SPEC, (part.PIVOT_SCREW_XZ,), "#10-24", 1),
        "LockSeat": (part.LOCK_SEAT_SPEC, (part.LOCK_KNOB_XZ,), "1/4-20", 1),
        "StopSeat": (part.STOP_SEAT_SPEC, (part.STOP_SCREW_XZ,), "#4-40", 1),
        "BlockScrewHoles": (part.BLOCK_SEAT_SPEC, part.BLOCK_SCREW_XZ, "#8-32", 4),
        "FootScrewHoles": (part.FOOT_SEAT_SPEC, part.FOOT_SCREW_XZ, "#4-40", 1),
        "PedestalSeats": (part.PEDESTAL_SEAT_SPEC, part.PEDESTAL_SCREW_XZ, "#8-32", 2),
        "NameplateSeats": (part.NAMEPLATE_SEAT_SPEC, part.NAMEPLATE_SCREW_XZ, "#4-40", 4),
    }
    assert len(part.THROUGH_SEAT_GROUPS) == len(expected)
    assert sum(len(stations) for _tag, _seat, stations, _bounds in part.THROUGH_SEAT_GROUPS) == 18
    for tag, seat, stations, bounds in part.THROUGH_SEAT_GROUPS:
        wanted, wanted_stations, thread, count = expected[tag]
        assert seat is wanted
        assert stations == wanted_stations
        assert len(stations) == count
        assert (seat.size, seat.thread_class, seat.end) == (thread, "2B", "through_all")
        assert seat.kind in ("tapped", "tapped_bottoming")
        assert seat.depth_mm == 0.0
        assert seat.overrides_mm == {}
        assert TAP_DRILL_MM[thread] < part.THREAD_MAJOR_MM[thread]
        assert bounds == (part.PEDESTAL_TRANSFER_XZ if tag == "PedestalSeats" else (0.0, 0.0))


def test_retained_skin_books_the_three_loose_heights_and_both_edge_breaks() -> None:
    fasteners = fr_harmonic_base_fasteners
    spec = fr_harmonic_base_spec
    assert spec.POCKET_SKIN == 13.0
    assert spec.POCKET_CEILING_Y == pytest.approx(37.8)
    assert spec.STACK_HEIGHT - spec.POCKET_CEILING_Y == pytest.approx(spec.POCKET_SKIN)
    assert fasteners.DECK_HEIGHT_BAND_MM == pytest.approx(1.6)
    assert fasteners.POCKET_CEILING_BAND_MM == pytest.approx(0.8)
    assert fasteners.EDGE_BREAK_MAX_MM == pytest.approx(0.25)
    for tag, seat, stations, bounds in part.THROUGH_SEAT_GROUPS:
        materials = part.THROUGH_SEAT_MATERIAL[tag]
        assert len(materials) == len(stations)
        for xz, material in zip(stations, materials, strict=True):
            assert material == fasteners.through_seat_material(seat, xz, envelope_xz=bounds)
            assert material.station_xz == xz
            assert material.nominal_segments_mm == fasteners.retained_material_segments_mm(*xz)
            capacity = sum(end - start for start, end in material.guaranteed_segments_mm)
            assert capacity >= 1.5 * part.THREAD_MAJOR_MM[seat.size]
            assert material.exit_depth_min_mm >= 13.0 - 3.0 * 0.8 - 1e-9
            assert material.guaranteed_segments_mm[0][0] == pytest.approx(0.25)
    support = part.THROUGH_SEAT_MATERIAL["SupportHoldDownSeats"][0]
    assert support.nominal_segments_mm == ((0.0, 13.0),)
    assert sum(end - start for start, end in support.guaranteed_segments_mm) == pytest.approx(10.10)
    # The old 12 mm skin would miss the unchanged 1.5D female-capacity floor.
    assert 12.0 - 3.0 * 0.8 - 2.0 * 0.25 < 1.5 * 6.35 < 10.10


def test_material_queries_distinguish_skin_ribs_walls_fillets_and_transfer_bounds() -> None:
    fasteners = fr_harmonic_base_fasteners
    spec = fr_harmonic_base_spec
    assert fasteners.retained_material_segments_mm(100.0, 50.0) == ((0.0, 13.0),)
    assert fasteners.retained_material_segments_mm(100.0, 0.0) == (
        (0.0, spec.STACK_HEIGHT - spec.RIB_RELIEF),
    )
    assert fasteners.retained_material_segments_mm(100.0, spec.POCKET_HALF_Z + 1.0) == (
        (0.0, spec.STACK_HEIGHT),
    )
    assert fasteners.retained_material_segments_mm(6.0, 6.0, fillet_radius_mm=0.0)[0] == pytest.approx((0.0, 13.0))
    assert fasteners.retained_material_segments_mm(6.0, 6.0)[0][1] > 13.0
    for xz in part.PEDESTAL_SCREW_XZ:
        material = fasteners.through_seat_material(
            part.PEDESTAL_SEAT_SPEC, xz, envelope_xz=part.PEDESTAL_TRANSFER_XZ,
        )
        assert material.envelope_xz == (2.0, 5.0)
        assert len(material.guaranteed_segments_mm) == 1
        assert material.guaranteed_segments_mm[0] == pytest.approx((0.25, 10.35))
    # A thread straddling a rib edge cannot credit the axis's entire rib.
    straddling = fasteners.through_seat_material(part.STOP_SEAT_SPEC, (100.0, 4.9))
    assert straddling.nominal_segments_mm[0][1] > 13.0
    assert straddling.guaranteed_segments_mm[0][1] == pytest.approx(10.35)


@pytest.mark.parametrize("xz", ((math.nan, 0.0), (0.0, math.inf), (1000.0, 0.0)))
def test_material_query_rejects_nonfinite_or_outside_deck_stations(xz) -> None:
    with pytest.raises(ValueError):
        fr_harmonic_base_fasteners.retained_material_segments_mm(*xz)


@pytest.mark.parametrize("radius", (-0.01, 6.01, math.nan, math.inf))
def test_material_query_rejects_radius_outside_the_printed_max(radius) -> None:
    with pytest.raises(ValueError):
        fr_harmonic_base_fasteners.retained_material_segments_mm(100.0, 50.0, fillet_radius_mm=radius)


@pytest.mark.parametrize("bounds", ((-0.01, 0.0), (0.0, math.inf), (math.nan, 0.0), (200.0, 0.0)))
def test_through_material_rejects_invalid_or_overhanging_transfer_envelopes(bounds) -> None:
    with pytest.raises((ValueError, AssertionError)):
        fr_harmonic_base_fasteners.through_seat_material(
            part.PEDESTAL_SEAT_SPEC, part.PEDESTAL_SCREW_XZ[0], envelope_xz=bounds,
        )


@pytest.mark.parametrize(
    "changes",
    ({"end": "blind", "depth_mm": 12.0}, {"depth_mm": 12.0},
     {"overrides_mm": {"ThreadDepth": 12.0}}),
)
def test_through_material_refuses_obsolete_blind_manufacturing_depths(changes) -> None:
    with pytest.raises(AssertionError):
        fr_harmonic_base_fasteners.through_seat_material(
            replace(part.PIVOT_SEAT_SPEC, **changes), part.PIVOT_SCREW_XZ,
        )


def test_through_fit_measures_female_external_overlap_protrusion_and_floor() -> None:
    fasteners = fr_harmonic_base_fasteners
    material = fasteners.ThroughSeatMaterial(
        (100.0, 50.0), (0.0, 0.0), ((0.0, 13.0),),
        ((0.25, 4.0), (6.0, 12.0)), 10.6, 15.4, 49.2,
    )
    fit = fasteners.require_through_seat_fit(
        "segmented fixture", part.FOOT_SEAT_SPEC, material,
        insertion_min_mm=10.0, insertion_max_mm=15.0,
        tip_loss_mm=0.5, full_thread_start_mm=2.0,
    )
    assert fit.full_thread_engagement_min_mm == pytest.approx(5.5)
    assert fit.protrusion_max_mm == pytest.approx(4.4)
    assert fit.clearance_min_mm == pytest.approx(34.2)


def test_through_fit_accepts_exact_engagement_but_refuses_short_overlap_and_floor_contact() -> None:
    fasteners = fr_harmonic_base_fasteners
    material = fasteners.through_seat_material(part.FOOT_SEAT_SPEC, part.FOOT_SCREW_XZ[0])
    needed = 1.5 * part.THREAD_MAJOR_MM["#4-40"]
    insertion = material.guaranteed_segments_mm[0][0] + needed
    fit = fasteners.require_through_seat_fit(
        "boundary", part.FOOT_SEAT_SPEC, material,
        insertion_min_mm=insertion, insertion_max_mm=insertion,
    )
    assert fit.full_thread_engagement_min_mm == pytest.approx(needed)
    for delta, tip, start in ((-0.001, 0.0, 0.0), (0.0, 0.001, 0.0), (0.0, 0.0, 0.251)):
        with pytest.raises(AssertionError, match="full-form overlap"):
            fasteners.require_through_seat_fit(
                "boundary", part.FOOT_SEAT_SPEC, material,
                insertion_min_mm=insertion + delta, insertion_max_mm=insertion,
                tip_loss_mm=tip, full_thread_start_mm=start,
            )
    for maximum in (material.deck_height_min_mm, material.deck_height_min_mm + 0.001):
        with pytest.raises(AssertionError, match="clearance floor"):
            fasteners.require_through_seat_fit(
                "boundary", part.FOOT_SEAT_SPEC, material,
                insertion_min_mm=10.0, insertion_max_mm=maximum,
            )


@pytest.mark.parametrize(
    "changes",
    ({"insertion_min_mm": 0.0}, {"insertion_min_mm": 11.0},
     {"insertion_max_mm": math.inf}, {"tip_loss_mm": -0.1},
     {"full_thread_start_mm": math.nan}, {"minimum_engagement_diameters": 0.0},
     {"clearance_floor_y_mm": math.inf}),
)
def test_through_fit_refuses_nonphysical_bounds(changes) -> None:
    fasteners = fr_harmonic_base_fasteners
    bounds = {"insertion_min_mm": 9.0, "insertion_max_mm": 10.0, **changes}
    material = part.THROUGH_SEAT_MATERIAL["FootScrewHoles"][0]
    with pytest.raises(ValueError, match="bounds"):
        fasteners.require_through_seat_fit("invalid", part.FOOT_SEAT_SPEC, material, **bounds)


def test_cone_lock_preserves_both_stock_poses_in_the_finite_receiver() -> None:
    import dt_vn_cone_lock_knob_spec as knob

    material = part.THROUGH_SEAT_MATERIAL["LockSeat"][0]
    knob.require_seat_fit(part.LOCK_SEAT_SPEC, platform.PLATE_T, knob.STUD_LEN, material=material)
    assert knob.STUD_LEN - platform.PLATE_T == pytest.approx(12.7)
    assert material.deck_height_min_mm > knob.STUD_LEN
    with pytest.raises(AssertionError, match="full-form overlap"):
        knob.require_seat_fit(part.LOCK_SEAT_SPEC, platform.PLATE_T, 7.9375, material=material)
    thin = replace(material, guaranteed_segments_mm=((0.25, 9.774),))
    with pytest.raises(AssertionError, match="full-form overlap"):
        knob.require_seat_fit(part.LOCK_SEAT_SPEC, platform.PLATE_T, knob.STUD_LEN, material=thin)


def test_stop_head_seats_on_the_base_inside_the_platform_edge() -> None:
    import dt_vn_foot_screw_spec as foot
    import dt_vn_swing_stop_screw_spec as stop

    material = part.THROUGH_SEAT_MATERIAL["StopSeat"][0]
    stop.require_seat_fit(part.STOP_SEAT_SPEC, platform.PLATE_T, material=material)
    assert (stop.THREAD, stop.SHANK_LEN) == (foot.THREAD, foot.SHANK_LEN)
    assert stop.PROUD_LEN == 0.0
    assert stop.CONTACT_DIA == stop.HEAD_DIA
    assert stop.HEAD_H <= platform.PLATE_T - 0.508
    # A short full-thread receiver still fails even if the tip has free air.
    thin = replace(material, guaranteed_segments_mm=((0.25, 4.0),))
    with pytest.raises(AssertionError, match="full-form overlap"):
        stop.require_seat_fit(part.STOP_SEAT_SPEC, platform.PLATE_T, material=thin)


def test_nameplate_seats_are_derived_from_the_plate_mount() -> None:
    """The four #4-40 taps sit under the plate's corner holes carried through
    its mount transform (nameplate_spec), cut from the deck the plate lies on."""
    import fr_nameplate_spec
    from _mcmaster_90114a511 import HEAD_DIA, SHANK_DIA, SHANK_LEN, THREAD
    from build_fr_nameplate import SCREW_HOLE_DIA

    assert part.NAMEPLATE_SEAT_SPEC.kind == "tapped_bottoming"
    assert part.NAMEPLATE_SEAT_SPEC.size == THREAD == "#4-40"
    assert part.NAMEPLATE_SEAT_SPEC.end == "through_all"
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
    # RV-03 already accepts the purchased screw's limited useful full form.
    # Through-tapping preserves that hardware and ruling, not a new 1.5D claim.
    engagement = SHANK_LEN - fr_nameplate_spec.PLATE_THICKNESS
    assert engagement == pytest.approx(4.85)
    material = part.THROUGH_SEAT_MATERIAL["NameplateSeats"][0]
    from _printed_tolerance import printed_deviations

    plate_band = printed_deviations(
        fr_nameplate_spec.PLATE_THICKNESS, fr_nameplate_spec.PLATE_THICKNESS_PRECISION,
    )[1]
    # RV-03 states the external projection; the finite receiver additionally
    # loses its entrance break, just as the unchanged joint did before.
    useful_overlap = fr_nameplate_spec.SCREW_FULL_THREAD_MIN - material.guaranteed_segments_mm[0][0]
    fit = fr_harmonic_base_fasteners.require_through_seat_fit(
        "nameplate existing RV-03", part.NAMEPLATE_SEAT_SPEC, material,
        insertion_min_mm=SHANK_LEN - fr_nameplate_spec.SCREW_LENGTH_SHORT_ALLOWANCE
        - fr_nameplate_spec.PLATE_THICKNESS - plate_band,
        insertion_max_mm=engagement + plate_band,
        tip_loss_mm=fr_nameplate_spec.SCREW_TIP_INCOMPLETE,
        minimum_engagement_diameters=useful_overlap / part.THREAD_MAJOR_MM["#4-40"],
    )
    assert fit.full_thread_engagement_min_mm == pytest.approx(useful_overlap)
    assert fit.protrusion_max_mm == 0.0


def test_pivot_seat_reads_the_cone_line_pivot() -> None:
    """The native seat follows the live configured cone line, without a
    frozen former-world station or a separately applied installation shift."""
    assert part.PIVOT_SCREW_XZ is cone_line.PIVOT_XZ
    pivot = cone_line.cone_station(cone_line.PIVOT_STATION)
    assert part.PIVOT_SCREW_XZ == (pivot[0], pivot[2])
    assert not hasattr(dt_cone_pivot_post_installation, "POST_X_SHIFT")
    assert not hasattr(dt_cone_pivot_post_installation, "POST_Z_SHIFT")


def test_v2_platform_swing_stop_coordinate_is_rederived() -> None:
    """Mirror the drive-train formula without importing its COM-heavy graph."""
    pivot_x, pivot_z = part.PIVOT_SCREW_XZ
    assert part.STOP_SCREW_XZ == part.SWING_HARDWARE_GEOMETRY.stop_xz
    east_slope = (platform.EAST_HALF_S - platform.HALF_WIDTH_N) / platform.PLATE_LEN
    stop_local_z = platform.STOP_LOCAL_Z
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


def test_structural_holes_follow_the_live_parked_rig_and_bank() -> None:
    """Native base seats are the real parked block/foot and fitted pedestal
    stations, not a translated copy of the former gear-train geometry."""
    import cylinder_bank_layout as bank
    import dt_arbor_pedestal_spec as pedestal
    import pinion_rig_layout as rig
    import pinion_rig_park_geometry as park
    from dt_pinion_pivot_block_geometry import SCREW_HALF_SPACING
    from dt_pinion_spring_section import SCREW_EAST_OF_PIVOT

    expected_blocks = tuple(
        (park.PIVOT_X + dx, z)
        for z in rig.BLOCK_SEAT_Z
        for dx in (-SCREW_HALF_SPACING, SCREW_HALF_SPACING)
    )
    assert part.BLOCK_SCREW_XZ == expected_blocks
    assert rig.BLOCK_SEAT_Z[1] == pytest.approx(
        rig.BACK_BLOCK_Z0 + pinion_pivot_block_depth() / 2.0, abs=1e-9
    )
    assert rig.BLOCK_SEAT_Z[1] - rig.BLOCK_SEAT_Z[0] == pytest.approx(
        pinion_pivot_block_depth() + rig.INNER_SPAN, abs=1e-9
    )
    assert part.FOOT_SCREW_XZ == (
        (park.PIVOT_X - SCREW_EAST_OF_PIVOT, rig.SPRING_PAD_Z),
    )
    ledge_offset = pedestal.STRAP_INNER_Z - pedestal.SCREW_Z
    assert part.PEDESTAL_SCREW_XZ == (
        (cone_line.X_DRUM, bank.FRONT_STRAP_INNER_Z - ledge_offset),
        (cone_line.X_DRUM, bank.BACK_STRAP_INNER_Z + ledge_offset),
    )


def _socket_bore_geometry(x_mm: float, z_mm: float):
    """The bore wall's COM geometry signature, as measured on the built part.

    Faces read back one Ø25.50 cylinder per station whose bounding box spans
    the bore's own radius in X and Z and the socket depth in Y, so the specs
    can be resolved offline without a SolidWorks session.
    """
    from _gtol_face import SURFACE_CYLINDER, FaceGeometry

    radius = part.COLUMN_SOCKET_DIAMETER / 2000.0
    return FaceGeometry(
        face=None,
        identity=SURFACE_CYLINDER,
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
    from _gtol_cylinder import CylinderFace

    spec = fr_harmonic_base_spec
    geometries = {
        station: _socket_bore_geometry(*station) for station in spec.COLUMN_SOCKET_XZ
    }
    assert len(spec.SOCKET_BORE_FINISHES) == len(spec.COLUMN_SOCKET_XZ)
    for control in spec.SOCKET_BORE_FINISHES:
        matched = [
            station
            for station, geometry in geometries.items()
            if control.face.matches(geometry)
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
    assert sum(x_only.matches(g) for g in geometries.values()) == 2
    assert sum(size_only.matches(g) for g in geometries.values()) == 4


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
    # Codex #855 P1: the four block seats are spotted THROUGH MHA-DT-18 at
    # assembly (U28 corollary; the drive-train rig-set step, "BEFORE SPOTTING
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
    # until the fitter sets it, so both rig callouts cite the drive-train step
    # that sets it (the drum's back end on leaf D off the north gear).
    assert sheet.TRANSFER_BLOCK_CALLOUT == (
        f"TRANSFER FROM MHA-DT-18\nAFTER {step_ref('rig-set')};\n"
    )
    # The front pair sits one feeler off the fit-up stack, with no pose air.
    front_seat = rig.BACK_BLOCK_Z0 - rig.INNER_SPAN - BLOCK_DEPTH / 2.0
    assert rig.BLOCK_SEAT_Z[0] == pytest.approx(front_seat, abs=1e-9)


def test_transferred_pedestal_and_spring_seats_print_no_station() -> None:
    # U34c (I27): each arbor pedestal is stood on the base with the arbor in
    # both straps and its #8-32 seat is spotted through the MHA-DT-02 ledge
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
    assert sheet.TRANSFER_PEDESTAL_CALLOUT == "TRANSFER FROM MHA-DT-02\nAT ASSEMBLY;\n"
    assert sheet.TRANSFER_SPRING_CALLOUT == (
        f"TRANSFER FROM MHA-DT-24\nAFTER {step_ref('rig-set')};\n"
    )
    assert not any(tag.startswith("G") for tag in sheet.HOLE_TAG_POSITIONS)


def test_nameplate_transfer_is_the_declared_fit_up() -> None:
    # Owner ruling 2026-10-15 (#1468): the nameplate taps are spotted through
    # the actual MHA-FR-04 plate at assembly, declared as RV-01. Its `where`
    # must quote the callout the sheet prints, and the taps must stay out of
    # the hole table (a printed station would reopen the stack).
    import draw_fr_harmonic_base as sheet
    from _paths import CAD_ROOT
    from machinist_exceptions import load_exceptions

    declared = {
        entry.id: entry
        for entry in load_exceptions(CAD_ROOT / "config", "fr_harmonic_base", "part")
    }
    fit_up = declared["RV-01"]
    assert fit_up.kind == "accept"
    assert fit_up.finding == "fit-up at assembly (rule 19)"
    assert fit_up.reason.endswith("(owner-accepted)")
    assert " ".join(sheet.TRANSFER_NAMEPLATE_CALLOUT.split()) in fit_up.where
    assert sheet.TRANSFER_NAMEPLATE_CALLOUT.startswith("TRANSFER FROM MHA-FR-04\n")
    nameplate_seats = {
        (x, z, part.NAMEPLATE_SCREW_HOLE_DIA) for x, z in part.NAMEPLATE_SCREW_XZ
    }
    assert set(sheet.TRANSFER_NAMEPLATE_HOLES) == nameplate_seats
    assert not nameplate_seats & set(sheet.TABLE_HOLES)
    # The reason's numbers, from literals: #4 close hole 0.120 in over the
    # #4-40 basic major 0.112 in; .X and .XX title-block rows +-0.8, +-0.51.
    float_diametral = (0.120 - 0.112) * 25.4
    demand = 2.0 * math.sqrt(2.0) * (0.8 + 0.51)
    assert f"{float_diametral:.3f}" == "0.203"
    assert f"{demand:.1f}" == "3.7"
    assert "0.203" in fit_up.reason and "3.7" in fit_up.reason


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
    # The band now reads (upper, lower) like every named fit band and goes
    # through deviations(); the setter must still receive (lower, upper) =
    # (0.0, +0.5), so the printed limits cannot move.
    import ast
    from pathlib import Path

    from _fit_deviations import deviations

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
    "MHA-DT-18 block transfer": (
        [0.262, 0.252],
        [(0.278818, 0.216872, 0.304252, 0.243612), (0.278222, 0.216247, 0.278818, 0.216872),
         (0.304252, 0.243612, 0.221335, 0.243612)],
        [("4X ", [0.241215, 0.254832], 0.0035), ("<MOD-DIAM>", [0.247938, 0.254778], 0.0035),
         (" 3.45 ", [0.253216, 0.254832], 0.0035), ("<HOLE-DEPTH>", [0.264854, 0.254778], 0.0035),
         (" 15.00", [0.269854, 0.254832], 0.0035), ("TRANSFER FROM MHA-DT-18", [0.233047, 0.249222], 0.0035),
         ("AT ASSEMBLY; 8-32 UNC - 2B ", [0.221335, 0.243666], 0.0035),
         ("<HOLE-DEPTH>", [0.284734, 0.243612], 0.0035), (" 12.75", [0.289734, 0.243666], 0.0035)],
    ),
    "MHA-DT-02 pedestal transfer": (
        [0.2, 0.252],
        [(0.264616, 0.218237, 0.242252, 0.243612), (0.265187, 0.217589, 0.264616, 0.218237),
         (0.242252, 0.243612, 0.159335, 0.243612)],
        [("2X ", [0.179215, 0.254832], 0.0035), ("<MOD-DIAM>", [0.185938, 0.254778], 0.0035),
         (" 3.45 ", [0.191216, 0.254832], 0.0035), ("<HOLE-DEPTH>", [0.202854, 0.254778], 0.0035),
         (" 19.50", [0.207854, 0.254832], 0.0035), ("TRANSFER FROM MHA-DT-02", [0.171047, 0.249222], 0.0035),
         ("AT ASSEMBLY; 8-32 UNC - 2B ", [0.159335, 0.243666], 0.0035),
         ("<HOLE-DEPTH>", [0.222734, 0.243612], 0.0035), (" 16.00", [0.227734, 0.243666], 0.0035)],
    ),
    "MHA-DT-24 spring transfer": (
        [0.269, 0.1575],
        [(0.271627, 0.175879, 0.309959, 0.149112), (0.271163, 0.176202, 0.271627, 0.175879),
         (0.309959, 0.149112, 0.229628, 0.149112)],
        [("<MOD-DIAM>", [0.251576, 0.160278], 0.0035), (" 2.26 ", [0.256855, 0.160332], 0.0035),
         ("<HOLE-DEPTH>", [0.268492, 0.160278], 0.0035), (" 11.30", [0.273493, 0.160332], 0.0035),
         ("TRANSFER FROM MHA-DT-24", [0.240047, 0.154722], 0.0035),
         ("AT ASSEMBLY; 4-40 UNC - 2B ", [0.229628, 0.149166], 0.0035),
         ("<HOLE-DEPTH>", [0.293027, 0.149112], 0.0035), (" 9.28", [0.298027, 0.149166], 0.0035)],
    ),
    "MHA-FR-VN-53 cross-tap": (
        [0.285, 0.13],
        [(0.329577, 0.098247, 0.342356, 0.113278), (0.328923, 0.097478, 0.329577, 0.098247),
         (0.342356, 0.113278, 0.229232, 0.113278)],
        [("4X ", [0.262404, 0.141166], 0.0035), ("<MOD-DIAM>", [0.269127, 0.141113], 0.0035),
         (" 4.04 ", [0.274406, 0.141166], 0.0035), ("<HOLE-DEPTH>", [0.286043, 0.141113], 0.0035),
         (" 48 MIN", [0.291044, 0.141166], 0.0035), ("MHA-FR-VN-53 TUBE CROSS-SCREWS", [0.250907, 0.135556], 0.0035),
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
    assert callouts["MHA-DT-24 spring transfer"] == pytest.approx((0.229628, 0.149112, 0.309959, 0.163832))
    assert sheet.find_callout_clashes(callouts, E0E287C83_OBSTACLES) == [
        "callout MHA-DT-02 pedestal transfer vs callout MHA-DT-18 block transfer: clearance -14.7 mm",
        "callout MHA-DT-02 pedestal transfer vs table DetailItem460: clearance -3.4 mm",
        "callout MHA-DT-24 spring transfer vs view holes top: clearance -4.7 mm",
    ]


def test_full_id_transfer_lane_budget_replays_1231_and_preserves_table_gap() -> None:
    import draw_fr_harmonic_base as sheet

    # #1231 / 5e14485511: actual qualified-ID ink, including the complete
    # mate identity and native thread/depth rows. Each lane needs 66.503 mm,
    # not the former legacy-ID anchor separation of 62 mm.
    recorded = {
        "pedestal": (
            0.16754236146807672,
            0.24083402720093727,
            0.23404513853192324,
            0.26110972263338045,
        ),
        "block": (
            0.22954236146807666,
            0.24083402720093727,
            0.2960451385319233,
            0.26110972263338045,
        ),
    }
    table = {"hole table": E0E287C83_OBSTACLES["table DetailItem460"]}
    assert sheet.find_callout_clashes(recorded, table) == [
        "callout block vs callout pedestal: clearance -4.5 mm"
    ]
    current = {}
    for name, old_anchor, new_anchor in (
        ("pedestal", (0.200, 0.252), sheet.PEDESTAL_CALLOUT_XY),
        ("block", (0.262, 0.252), sheet.BLOCK_CALLOUT_XY),
    ):
        dx, dy = (new_anchor[i] - old_anchor[i] for i in (0, 1))
        x0, y0, x1, y1 = recorded[name]
        current[name] = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
    assert sheet.find_callout_clashes(current, table) == []
    assert sheet.box_gap(current["pedestal"], current["block"]) >= 0.005
    assert sheet.box_gap(current["pedestal"], table["hole table"]) >= 0.004
    # Moving the pedestal left to make room is not a valid repair: the
    # neighboring hole table occupies this same row.
    x0, y0, x1, y1 = current["pedestal"]
    assert sheet.find_callout_clashes(
        {"pedestal": (x0 - 0.010, y0, x1 - 0.010, y1)}, table
    )


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
        {"MHA-DT-02 pedestal transfer": E533EF6FD_PEDESTAL_BOX},
        {"label": texts["label 'TOP VIEW SCALE 1:4'"]},
    ) == []


def test_leader_check_skips_its_own_callout_box_among_foreign_texts() -> None:
    import draw_fr_harmonic_base as sheet

    # Among foreign texts a callout's own whole box is skipped (its rows are
    # checked separately, below); a foreign note on the leader's path is not.
    leaders = {"MHA-DT-24 spring transfer": sheet.leader_segments(E533EF6FD_SPRING_LINES)}
    texts = {
        "callout MHA-DT-24 spring transfer": E533EF6FD_SPRING_BOX,
        "note on the path": (0.285, 0.160, 0.295, 0.165),
        "note beside it": (0.300, 0.170, 0.310, 0.175),
    }
    assert sheet.find_leader_crossings(leaders, texts) == [
        "leader of callout MHA-DT-24 spring transfer crosses note on the path"
    ]


E533EF6FD_SPRING_TEXTS = [
    ("<MOD-DIAM>", [0.251576, 0.151278], 0.0035),
    (" 2.26 ", [0.256855, 0.151332], 0.0035),
    ("<HOLE-DEPTH>", [0.268492, 0.151278], 0.0035),
    (" 11.30", [0.273493, 0.151332], 0.0035),
    ("TRANSFER FROM MHA-DT-24", [0.240047, 0.145722], 0.0035),
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
        "TRANSFER FROM MHA-DT-24",
        "AT ASSEMBLY; 4-40 UNC - 2B <HOLE-DEPTH> 9.28",
    ]
    assert rows["TRANSFER FROM MHA-DT-24"] == pytest.approx(
        (0.240047, 0.145722, 2.0 * centre - 0.240047, 0.149222)
    )
    # The widest row spans the shoulder.
    assert rows["AT ASSEMBLY; 4-40 UNC - 2B <HOLE-DEPTH> 9.28"][2] == pytest.approx(0.309959)


def test_leader_check_flags_a_leader_through_its_own_rows() -> None:
    """e533ef6fd's spring leader left the shoulder's right end and rose
    through "9.28" of its own thread row (hb-render-2 eye pass)."""
    import draw_fr_harmonic_base as sheet

    leaders = {"MHA-DT-24 spring transfer": sheet.leader_segments(E533EF6FD_SPRING_LINES)}
    own = {
        "MHA-DT-24 spring transfer": sheet.callout_text_rows(
            E533EF6FD_SPRING_LINES, E533EF6FD_SPRING_TEXTS, "spring"
        )
    }
    assert sheet.find_leader_crossings(leaders, {}, own) == [
        "leader of callout MHA-DT-24 spring transfer crosses its own row "
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
    leaders = {"MHA-DT-24 spring transfer": sheet.leader_segments(moved_lines)}
    own = {"MHA-DT-24 spring transfer": sheet.callout_text_rows(moved_lines, moved_texts, "spring")}
    assert sheet.find_leader_crossings(leaders, {}, own) == []
    # A transfer leader drops away from its rows: no finding.
    pedestal = {"MHA-DT-02 pedestal transfer": sheet.leader_segments(E533EF6FD_PEDESTAL_LINES)}
    assert sheet.find_leader_crossings(pedestal, {}, {"MHA-DT-02 pedestal transfer": {
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


def _drive_hole_sheet_callout_check(
    monkeypatch,
    note_box,
    *,
    numbered_note_box=(0.150, 0.020, 0.180, 0.040),
    numbered_note_copies=1,
    leaders=(),
) -> None:
    """Exercise ordinary note obstacles without COM; boxes are unit controls."""
    from types import SimpleNamespace

    import draw_fr_harmonic_base as sheet

    def annotations(_adapter, view):
        if view != "sheet":
            return iter(())
        rows = [(None, "display dimension")]
        if note_box is not None:
            rows.append((SimpleNamespace(kind="note", label="D1", box=note_box), "note"))
        rows.extend([
            (SimpleNamespace(kind="note", label="1", box=numbered_note_box), "numbered note")
        ] * numbered_note_copies)
        return iter(rows)

    for name, value in {
        "_callout_display_data": lambda display, label: (None, (), ()),
        "callout_text_box": lambda anchor, lines, texts, label: (0.100, 0.100, 0.130, 0.110),
        "leader_segments": lambda lines: list(leaders),
        "callout_text_rows": lambda lines, texts, label: {},
        "_sheet_frame_obstacles": lambda adapter, ddoc: {},
        "_view_geometry_box": lambda adapter, view, label: (0.300, 0.150, 0.400, 0.250),
        "_early_bound": lambda obj, interface: obj,
        "datum_origin_boxes": lambda points: {},
        "_section_line_obstacles": lambda views: {},
        "_iter_view_annotations": annotations,
        "_note_text": lambda adapter, annotation: (
            sheet.PIVOT_SEAT_STEP.replace("\n", "\r\n") + "\r\n"
            if annotation == "numbered note" else "D1"
        ),
        "_iter_tables": lambda adapter, view: (
            [SimpleNamespace(label="holes", box=(0.020, 0.020, 0.090, 0.060))]
            if view == "sheet" else []
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


def test_numbered_pivot_note_keeps_ordinary_actual_note_collision_measurement(monkeypatch) -> None:
    with pytest.raises(RuntimeError, match="callout pedestal vs note 1"):
        _drive_hole_sheet_callout_check(
            monkeypatch, (0.200, 0.200, 0.220, 0.210),
            numbered_note_box=(0.110, 0.102, 0.120, 0.108),
        )
    with pytest.raises(RuntimeError, match="leader of callout pedestal crosses note 1"):
        _drive_hole_sheet_callout_check(
            monkeypatch, (0.200, 0.200, 0.220, 0.210),
            leaders=((0.130, 0.105, 0.165, 0.030),),
        )


@pytest.mark.parametrize("copies", (0, 2))
def test_hole_sheet_requires_exactly_one_numbered_pivot_note(monkeypatch, copies) -> None:
    with pytest.raises(RuntimeError, match="exactly one numbered pivot seat note"):
        _drive_hole_sheet_callout_check(
            monkeypatch, (0.200, 0.200, 0.220, 0.210), numbered_note_copies=copies,
        )


def test_hole_sheet_has_no_special_d1_tag_measurement_requirement(monkeypatch) -> None:
    _drive_hole_sheet_callout_check(monkeypatch, None)


def test_general_leader_guard_rejects_the_recorded_origin_x_crossing() -> None:
    import draw_fr_harmonic_base as sheet

    # Recorded native failure, retained only as a general crossing regression.
    leader = (0.212226510324, 0.129615170535, 0.257966478570, 0.168792566697)
    origin = (0.21935, 0.142105, 0.242401, 0.149105)
    assert sheet.find_leader_crossings(
        {"historic note": [leader]}, {"origin X axis": origin},
    ) == ["leader of callout historic note crosses origin X axis"]


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
    assert sheet.find_callout_clashes({"MHA-DT-24 spring transfer": E533EF6FD_SPRING_BOX}, boxes) == [
        "callout MHA-DT-24 spring transfer vs origin X axis: clearance -9.4 mm"
    ]
    with pytest.raises(RuntimeError, match="not 4"):
        sheet.datum_origin_boxes([0.0] * 6)


def test_green_top_caption_clears_the_native_height_stack() -> None:
    import draw_fr_harmonic_base as sheet

    # r2b raw display extents include the underlining shelf, not just the
    # narrower ink boxes. Both height witnesses crossed the old lower row.
    old_box = (0.0231007, 0.1036656, 0.0625, 0.1182781)
    rd1_arrow = (0.0425, 0.10635, 0.0425, 0.1127)
    own_witness = (0.0884, 0.1056, 0.0615, 0.1056)
    rd1_witness = (0.0415, 0.10635, 0.10384, 0.10635)
    assert sheet.segment_crosses_box(rd1_arrow, old_box)
    assert sheet.segment_crosses_box(own_witness, old_box)
    assert sheet.segment_crosses_box(rd1_witness, old_box)
    x, y = sheet.SIDE_KEEP["GreenTopHeight"]
    assert sheet.SIDE_KEEP["BottomThickness"][0] > x == 0.0625 > rd1_arrow[0]
    dy = y - 0.112
    box = (old_box[0], old_box[1] + dy, old_box[2], old_box[3] + dy)
    for line_y in (0.1127, 0.10635, 0.1056):
        assert box[1] - line_y >= 0.0035
    assert 0.143512 - box[3] >= 0.0035
    neighbors = (
        (0.098, 0.1184229, 0.1425667, 0.1309743),
        (0.0349604, 0.0962219, 0.0500396, 0.0997219),
    )
    assert all(sheet.box_gap(box, neighbor) >= 0.0035 for neighbor in neighbors)


# Sheet-2 native extents from r2b, run
# 20261019T211244551Z-fb69447dfb4048419fd6b021e4f5c124, in sheet metres.
# Translations and the two offset-anchor readings below are offline controls,
# not a claim that the proposed placement has already drawn on a native seat.
_R2B_PIVOT_X_KEEP = (0.257, 0.145)
_R2B_PIVOT_X_TEXT = (0.2448681, 0.1431558, 0.2690665, 0.1467211)
_R2B_PIVOT_X_LINE_Y = 0.1422219
_R2B_PIVOT_X_WITNESS_STARTS = (
    (0.2583636, 0.1711521),
    (0.2649016, 0.1740415),
)
_R2B_DATUM_X_TEXT = (0.2425598, 0.1438616, 0.2450907, 0.1472636)
_R2B_DATUM_X_AXIS = (0.22285, 0.145605, 0.238901, 0.145605)
_R2B_HOLE_PLAN = (0.22285, 0.1591, 0.33715, 0.2309)
_R2B_D1_TEXT = (0.247406, 0.1834876, 0.251993, 0.1868896)
_R2B_D1_Y = 0.1690524
_R2B_PEDESTAL_Y = 0.1719847


def _r2b_pivot_x_text_at(keep):
    dx, dy = keep[0] - _R2B_PIVOT_X_KEEP[0], keep[1] - _R2B_PIVOT_X_KEEP[1]
    return tuple(
        value + (dx if index % 2 == 0 else dy)
        for index, value in enumerate(_R2B_PIVOT_X_TEXT)
    )


def test_pivot_x_keep_replays_clearance_from_both_native_witnesses_and_datum() -> None:
    import draw_fr_harmonic_base as sheet

    for x, start_y in _R2B_PIVOT_X_WITNESS_STARTS:
        witness = (x, start_y, x, _R2B_PIVOT_X_LINE_Y - 0.001)
        assert sheet.segment_crosses_box(witness, _R2B_PIVOT_X_TEXT)
    assert sheet.box_gap(_R2B_PIVOT_X_TEXT, _R2B_DATUM_X_TEXT) < 0.0

    keep = sheet.HOLE_TOP_KEEP["PivotSeatX"]
    box = _r2b_pivot_x_text_at(keep)
    line_y = _R2B_PIVOT_X_LINE_Y + keep[1] - _R2B_PIVOT_X_KEEP[1]
    assert _R2B_PIVOT_X_WITNESS_STARTS[0][0] - box[2] >= 0.0035
    neighbors = {
        "datum X letter": _R2B_DATUM_X_TEXT,
        "datum zero": (0.2187063, 0.1437608, 0.2209937, 0.1473261),
        "datum X axis": _R2B_DATUM_X_AXIS,
        "datum vertical drop": (0.22285, 0.143605, 0.22285, 0.1581),
        "plan": _R2B_HOLE_PLAN,
    }
    for label, neighbor in neighbors.items():
        assert sheet.box_gap(box, neighbor) >= 0.0035, label
    cross_tap_count = (0.2625209, 0.1208449, 0.2676798, 0.1243309)
    for x, start_y in _R2B_PIVOT_X_WITNESS_STARTS:
        witness = (x, line_y - 0.001, x, start_y)
        assert not sheet.segment_crosses_box(witness, box)
        assert sheet.box_gap(witness, cross_tap_count) >= 0.0035
    tail = (0.2649016, line_y, 0.2712516, line_y)
    spring_leader = (0.2717697, 0.1756206, 0.2809549, 0.131634)
    assert not sheet.segment_crosses_box(spring_leader, tail)
    # The restored flags-safe X line stays below the finite spring leader's
    # native endpoint; extending that leader would invent an intersection.
    assert min(spring_leader[1], spring_leader[3]) - line_y >= 0.002


def test_pivot_y_line_replays_the_narrow_native_between_hole_window() -> None:
    import draw_fr_harmonic_base as sheet

    a1_text = (0.2345301, 0.1671557, 0.2393918, 0.1705577)
    old_d1_witness = (0.256264, _R2B_D1_Y, 0.191, _R2B_D1_Y)
    assert sheet.segment_crosses_box(old_d1_witness, a1_text)
    x, y = sheet.HOLE_TOP_KEEP["PivotSeatY"]
    # Native centre-mark arms plus their 1 mm witness gaps leave only this
    # 2.38 mm window. A fully right-sided line would run through other ink.
    assert 0.2604633 < x < 0.2628448
    assert _R2B_D1_Y < y < _R2B_PEDESTAL_Y
    # Replay either plausible D1 arm after moving the line across its hole.
    # The pedestal's measured inner-arm start is 262.8448 mm, not 262.7 mm.
    witnesses = (
        (0.2604633, _R2B_D1_Y, x + 0.001, _R2B_D1_Y),
        (0.256264, _R2B_D1_Y, x + 0.001, _R2B_D1_Y),
        (x - 0.001, _R2B_PEDESTAL_Y, 0.2628448, _R2B_PEDESTAL_Y),
    )
    for witness in witnesses:
        assert 0.256 < witness[0] <= witness[2] <= 0.2628448
        assert not sheet.segment_crosses_box(witness, a1_text)
        assert not sheet.segment_crosses_box(witness, _R2B_DATUM_X_TEXT)
        assert not sheet.segment_crosses_box(witness, _R2B_DATUM_X_AXIS)
    # The lower outside-arrow tail remains parallel between the X witnesses.
    # This is line-to-line air, not the 3.5 mm text-clearance requirement.
    assert x - _R2B_PIVOT_X_WITNESS_STARTS[0][0] >= 0.003
    assert _R2B_PIVOT_X_WITNESS_STARTS[1][0] - x >= 0.003


@pytest.mark.parametrize("anchor_is_top", (False, True), ids=("centred", "top-centre"))
def test_pivot_y_offset_text_replays_clearance_from_native_neighboring_ink(
    anchor_is_top,
) -> None:
    import draw_fr_harmonic_base as sheet

    # r2b's actual Y text was left of its line, not centred on its keep.
    old_text = (0.166826, 0.1621558, 0.1905016, 0.1657212)
    width, height = old_text[2] - old_text[0], old_text[3] - old_text[1]
    x, y = sheet.PIVOT_SEAT_Y_TEXT_XY
    top = y if anchor_is_top else y + height / 2.0
    box = (x - width / 2.0, top - height, x + width / 2.0, top)
    assert box[0] >= sheet.HOLE_TOP_KEEP["PivotSeatY"][0]
    # Deliberately inboard on blank printed pocket floor: reject nearby ink,
    # not the whole plan outline, which is not an occupied rectangular box.
    assert _R2B_HOLE_PLAN[0] < box[0] < box[2] < _R2B_HOLE_PLAN[2]
    assert _R2B_HOLE_PLAN[1] < box[1] < box[3] < _R2B_HOLE_PLAN[3]
    neighbors = {
        "spring centre mark": (0.2708043, 0.1749896, 0.2726196, 0.1768049),
        "pedestal centre mark": (0.2638448, 0.170928, 0.2659583, 0.1730415),
        "centre mark 391": (0.2925969, 0.1786569, 0.2951231, 0.1811831),
        "E1 leader": (0.2943345, 0.1794933, 0.2964761, 0.1879897),
        "B1 tag": (0.2471988, 0.1904933, 0.2509839, 0.1938953),
        "former D1 tag": _R2B_D1_TEXT,
        "X pedestal witness": (
            0.2649016,
            _R2B_PIVOT_X_LINE_Y
            + sheet.HOLE_TOP_KEEP["PivotSeatX"][1]
            - _R2B_PIVOT_X_KEEP[1]
            - 0.001,
            0.2649016,
            0.1740415,
        ),
    }
    for label, neighbor in neighbors.items():
        assert sheet.box_gap(box, neighbor) >= 0.0035, label


def _pivot_y_placement_fakes(monkeypatch, failure=None):
    """Unit-only collaborators; they do not establish native layout success."""
    from types import SimpleNamespace

    import draw_fr_harmonic_base as sheet

    events = []

    class Display:
        def __init__(self):
            self.offset = True  # Prove the helper resets an inherited offset.

        @property
        def OffsetText(self):  # noqa: N802 - the COM member name
            events.append(("offset-read", self.offset))
            return self.offset

        @OffsetText.setter
        def OffsetText(self, value):  # noqa: N802 - the COM member name
            events.append(("offset-set", value))
            if not (failure == "reset" and not value):
                self.offset = value

    class Annotation:
        name = "PivotSeatY"

        def __init__(self):
            self.display = Display()
            self.stage = "line"
            self.position = (0.192, 0.164, 0.0)

        def GetSpecificAnnotation(self):  # noqa: N802 - the COM member name
            return self.display

        def SetPosition2(self, x, y, z):  # noqa: N802 - the COM member name
            events.append(("line-set", (x, y, z)))
            assert not self.display.offset
            if failure == "line-set":
                return False
            self.position = (x, y, z)
            return True

        def GetPosition(self):  # noqa: N802 - the COM member name
            position = self.position
            if failure == f"{self.stage}-missing":
                position = None
            elif failure == f"{self.stage}-drift":
                position = (position[0] + 0.001, position[1], position[2])
            elif failure == f"{self.stage}-nan":
                position = (math.nan, position[1], position[2])
            events.append(("position-read", position))
            return position

    adapter = object()
    annotation = Annotation()

    def offset(adapter_arg, annotations, positions):
        events.append(("offset-call", adapter_arg, annotations, positions))
        assert adapter_arg is adapter
        assert annotations == [annotation]
        assert positions == {"PivotSeatY": sheet.PIVOT_SEAT_Y_TEXT_XY}
        if failure == "offset-helper":
            raise RuntimeError("offset helper refused")
        annotation.display.OffsetText = True
        if failure == "offset-state":
            annotation.display.offset = False
        annotation.stage = "text"
        annotation.position = (*positions["PivotSeatY"], 0.0)

    monkeypatch.setattr(sheet, "_early_bound", lambda obj, interface: obj)
    monkeypatch.setattr(sheet, "dimension_name", lambda adapter, item: item.name)
    monkeypatch.setattr(sheet, "offset_dimension_text", offset)
    other = SimpleNamespace(name="PivotSeatX")
    return adapter, annotation, other, events


def test_pivot_y_placement_resets_then_places_line_offsets_and_reads_back(monkeypatch) -> None:
    import draw_fr_harmonic_base as sheet

    adapter, annotation, other, events = _pivot_y_placement_fakes(monkeypatch)
    sheet._place_pivot_seat_y(adapter, [other, annotation])
    assert events == [
        ("offset-set", False),
        ("offset-read", False),
        ("line-set", (*sheet.HOLE_TOP_KEEP["PivotSeatY"], 0.0)),
        ("position-read", (*sheet.HOLE_TOP_KEEP["PivotSeatY"], 0.0)),
        ("offset-call", adapter, [annotation], {"PivotSeatY": sheet.PIVOT_SEAT_Y_TEXT_XY}),
        ("offset-set", True),
        ("offset-read", True),
        ("position-read", (*sheet.PIVOT_SEAT_Y_TEXT_XY, 0.0)),
    ]


@pytest.mark.parametrize("count", (0, 2))
def test_pivot_y_placement_requires_one_native_named_annotation(monkeypatch, count) -> None:
    import draw_fr_harmonic_base as sheet

    adapter, annotation, other, events = _pivot_y_placement_fakes(monkeypatch)
    with pytest.raises(RuntimeError, match=f"one native PivotSeatY, got {count}"):
        sheet._place_pivot_seat_y(adapter, [other, *([annotation] * count)])
    assert events == []


@pytest.mark.parametrize(
    ("failure", "message", "last_event", "offset_called"),
    (
        ("reset", "offset could not be reset", "offset-read", False),
        ("line-set", "failed to position .* line", "line-set", False),
        ("line-missing", "line did not persist", "position-read", False),
        ("line-drift", "line did not persist", "position-read", False),
        ("line-nan", "line did not persist", "position-read", False),
        ("offset-helper", "offset helper refused", "offset-call", True),
        ("offset-state", "text did not stay offset", "offset-read", True),
        ("text-missing", "text did not persist", "position-read", True),
        ("text-drift", "text did not persist", "position-read", True),
        ("text-nan", "text did not persist", "position-read", True),
    ),
)
def test_pivot_y_placement_refuses_failed_state_without_com(
    monkeypatch, failure, message, last_event, offset_called,
) -> None:
    import draw_fr_harmonic_base as sheet

    adapter, annotation, other, events = _pivot_y_placement_fakes(monkeypatch, failure)
    with pytest.raises(RuntimeError, match=message):
        sheet._place_pivot_seat_y(adapter, [other, annotation])
    assert events[-1][0] == last_event
    assert any(event[0] == "offset-call" for event in events) is offset_called


def _pivot_flag_fakes(monkeypatch, *, failed_name=None, readback=None):
    from types import SimpleNamespace

    import draw_fr_harmonic_base as sheet

    events = []
    adapter = object()
    displays = {}

    class Display:
        def __init__(self, name):
            self.name = name
            self.text = ""

        def GetText(self, part):  # noqa: N802 - the COM member name
            events.append(("read", self.name, part))
            assert part == 3
            return readback if self.name == failed_name else self.text

    annotations = []
    for name in ("PivotSeatY", "Other", "PivotSeatX"):
        display = Display(name)
        displays[name] = display
        annotations.append(SimpleNamespace(
            name=name, GetSpecificAnnotation=lambda display=display: display
        ))

    def set_flags(actual_adapter, actual_annotations, callouts, *, location):
        assert actual_adapter is adapter
        assert actual_annotations is annotations
        events.append(("set", dict(callouts), location))
        for name, text in callouts.items():
            displays[name].text = text

    monkeypatch.setattr(sheet, "_early_bound", lambda obj, interface: obj)
    monkeypatch.setattr(sheet, "dimension_name", lambda adapter, annotation: annotation.name)
    monkeypatch.setattr(sheet, "set_dimension_callouts", set_flags)
    return adapter, annotations, events


def test_pivot_offsets_flag_exactly_both_native_above_compartments(monkeypatch) -> None:
    import draw_fr_harmonic_base as sheet

    adapter, annotations, events = _pivot_flag_fakes(monkeypatch)
    sheet._flag_pivot_seat_dimensions(adapter, annotations)
    assert sheet.PIVOT_SEAT_CALLOUTS == {"PivotSeatX": "SEE NOTE 1", "PivotSeatY": "SEE NOTE 1"}
    assert events == [
        ("set", sheet.PIVOT_SEAT_CALLOUTS, "above"),
        ("read", "PivotSeatY", 3),
        ("read", "PivotSeatX", 3),
    ]


@pytest.mark.parametrize("name", ("PivotSeatX", "PivotSeatY"))
@pytest.mark.parametrize("actual", (None, "", "SEE D1", "SEE NOTE 2", "SEE NOTE 1\n", "SEE NOTE 1\r\n"))
def test_pivot_flags_refuse_silent_or_multiline_native_readback(
    monkeypatch, name, actual,
) -> None:
    import draw_fr_harmonic_base as sheet

    adapter, annotations, events = _pivot_flag_fakes(
        monkeypatch, failed_name=name, readback=actual
    )
    with pytest.raises(RuntimeError, match=f"native {name} ABOVE flag did not persist"):
        sheet._flag_pivot_seat_dimensions(adapter, annotations)
    assert events[-1] == ("read", name, 3)


@pytest.mark.parametrize("name", ("PivotSeatX", "PivotSeatY"))
@pytest.mark.parametrize("count", (0, 2))
def test_pivot_flags_require_exactly_one_of_each_native_offset(monkeypatch, name, count) -> None:
    import draw_fr_harmonic_base as sheet

    adapter, annotations, events = _pivot_flag_fakes(monkeypatch)
    selected = next(annotation for annotation in annotations if annotation.name == name)
    annotations[:] = [annotation for annotation in annotations if annotation is not selected]
    annotations.extend([selected] * count)
    with pytest.raises(RuntimeError, match="missing native D1 offsets|duplicate native D1 offset"):
        sheet._flag_pivot_seat_dimensions(adapter, annotations)
    assert events == []


@pytest.mark.parametrize(
    "callouts",
    (
        {"PivotSeatX": "SEE NOTE 1"},
        {"PivotSeatX": "SEE NOTE 1", "PivotSeatY": "SEE\nNOTE 1"},
        {"PivotSeatX": "SEE\rNOTE 1", "PivotSeatY": "SEE NOTE 1"},
        {"PivotSeatX": "", "PivotSeatY": "SEE NOTE 1"},
    ),
)
def test_pivot_flags_refuse_missing_keys_or_nonprintable_caption_rows(monkeypatch, callouts) -> None:
    import draw_fr_harmonic_base as sheet

    adapter, annotations, events = _pivot_flag_fakes(monkeypatch)
    monkeypatch.setattr(sheet, "PIVOT_SEAT_CALLOUTS", callouts)
    with pytest.raises(RuntimeError, match="both one-line ABOVE flags"):
        sheet._flag_pivot_seat_dimensions(adapter, annotations)
    assert events == []


class _NativeHoleTable:
    """ITableAnnotation surface for the D1 row flag; generated cells are locked."""

    def __init__(self, *, refuse=None, widths=(0.0198, 0.0303, 0.0317, 0.0628), d1_rows=1):
        self.refuse = refuse
        self.cells = [
            ["TAG", "X LOC", "Y LOC", "SIZE"],
            # CombineSameSize: merged SIZE cells read back on every row.
            ["A1", "31.60", "31.60", "Ø25.50"],
            ["A2", "31.60", "255.60", "Ø25.50"],
            *[["D1", "142.05", "39.81", "Ø3.80 ↧ 13.45"]] * d1_rows,
            ["E1", "284.04", "83.28", "Ø5.11"],
        ]
        self.cells = [list(row) for row in self.cells]
        self.widths = list(widths)

    @property
    def RowCount(self):  # noqa: N802 - the COM member name
        return len(self.cells)

    @property
    def ColumnCount(self):  # noqa: N802 - the COM member name
        return len(self.cells[0])

    def DisplayedText2(self, row, column, include_hidden):  # noqa: N802
        assert include_hidden is False
        return self.cells[row][column]

    def GetColumnWidth(self, column):  # noqa: N802
        return self.widths[column]

    def GetColumnType2(self, column, include_hidden):  # noqa: N802
        return 0

    def InsertColumn2(self, where, index, name, width_style):  # noqa: N802
        if self.refuse == "insert":
            return False
        for row in self.cells:
            row.insert(index + 1, "")
        self.widths.insert(index + 1, 0.020)
        return True

    def SetColumnTitle2(self, index, title, include_hidden):  # noqa: N802
        assert include_hidden is False
        if self.refuse == "title":
            return False
        self.cells[0][index] = title
        return True

    def IsCellTextEditable(self, row, column):  # noqa: N802
        # Hole tables: only the header row and custom columns are editable.
        return self.refuse != "editable" and (row == 0 or column == 4)

    def SetText2(self, row, column, include_hidden, text):  # noqa: N802
        assert include_hidden is False
        assert self.IsCellTextEditable(row, column), "wrote a generated hole-table cell"
        if self.refuse != "text":
            self.cells[row][column] = text

    def SetColumnWidth(self, column, width, options):  # noqa: N802
        assert options == 0  # swTableRowColChange_TableSizeCanChange
        if self.refuse != "width":
            self.widths[column] = width
        return self.widths[column]


def test_d1_table_row_carries_note_flag_in_custom_column_only() -> None:
    import draw_fr_harmonic_base as sheet

    table = _NativeHoleTable()
    native = [list(row) for row in table.cells]
    native_width = sum(table.widths)
    generated, width = sheet._flag_pivot_seat_table_row(table)

    assert generated == tuple(tuple(row) for row in native)
    assert width == pytest.approx(native_width)
    assert set(sheet.PIVOT_SEAT_CALLOUTS.values()) == {sheet.PIVOT_SEAT_FLAG}
    assert [row[:4] for row in table.cells] == native
    assert [row[4] for row in table.cells] == [
        sheet.PIVOT_SEAT_TABLE_COLUMN, "", "", sheet.PIVOT_SEAT_FLAG, "",
    ]
    assert table.widths[0] == sheet.HOLE_TABLE_TAG_WIDTH
    assert table.widths[1] == table.widths[2] >= sheet.HOLE_TABLE_MIN_LOCATION_WIDTH
    assert table.widths[3] == 0.0628
    assert table.widths[4] == sheet.PIVOT_SEAT_TABLE_COLUMN_WIDTH
    assert sum(table.widths) == pytest.approx(native_width, abs=1e-9)
    sheet._check_pivot_seat_table_row(table, generated, width)


@pytest.mark.parametrize(
    ("refuse", "message"),
    (
        ("insert", "refused the D1 NOTE column"),
        ("title", "NOTE column title did not set"),
        ("editable", "D1 NOTE cell is not editable"),
        ("text", "NOTE column did not persist"),
        ("width", "width did not persist"),
    ),
)
def test_d1_table_flag_refuses_unconfirmed_native_state(refuse, message) -> None:
    import draw_fr_harmonic_base as sheet

    with pytest.raises(RuntimeError, match=message):
        sheet._flag_pivot_seat_table_row(_NativeHoleTable(refuse=refuse))


@pytest.mark.parametrize(
    ("table", "message"),
    (
        (_NativeHoleTable(d1_rows=0), "needs one D1 row"),
        (_NativeHoleTable(d1_rows=2), "needs one D1 row"),
        (_NativeHoleTable(widths=(0.012, 0.022, 0.022, 0.0628)), "slack cannot hold"),
    ),
)
def test_d1_table_flag_refuses_before_inserting_a_column(table, message) -> None:
    import draw_fr_harmonic_base as sheet

    with pytest.raises(RuntimeError, match=message):
        sheet._flag_pivot_seat_table_row(table)
    assert table.ColumnCount == 4


@pytest.mark.parametrize(
    ("mutate", "message"),
    (
        (lambda table: table.cells[3].__setitem__(1, "(142.05)"), "changed generated"),
        (lambda table: table.cells[2].__setitem__(3, ""), "changed generated"),
        (lambda table: table.cells[3].__setitem__(4, ""), "did not persist"),
        (lambda table: table.cells[1].__setitem__(4, "SEE NOTE 1"), "did not persist"),
        (lambda table: table.widths.__setitem__(3, 0.070), "changed the hole-table width"),
        (lambda table: [row.pop() for row in table.cells], "lost or duplicated"),
    ),
)
def test_d1_table_flag_rebuild_readback_refuses_drift(mutate, message) -> None:
    import draw_fr_harmonic_base as sheet

    table = _NativeHoleTable()
    generated, width = sheet._flag_pivot_seat_table_row(table)
    mutate(table)
    with pytest.raises(RuntimeError, match=message):
        sheet._check_pivot_seat_table_row(table, generated, width)


@pytest.mark.parametrize(
    ("tag", "old_anchor", "old_box"),
    [
        ("A3", (0.325, 0.176), (0.3251, 0.1724, 0.3309, 0.1760)),
        ("A4", (0.326, 0.215), (0.3261, 0.2115, 0.3319, 0.2150)),
    ],
)
def test_socket_tags_clear_the_native_section_cut_line(tag, old_anchor, old_box) -> None:
    import draw_fr_harmonic_base as sheet

    # r2b native ink, not an estimated label width. The former tags were
    # both struck by the A-A line through the right-hand socket axes.
    cut_line = (0.3292, 0.155, 0.3292, 0.235)
    assert sheet.segment_crosses_box(cut_line, old_box)
    x, y = sheet.HOLE_TAG_POSITIONS[tag]
    dx, dy = x - old_anchor[0], y - old_anchor[1]
    box = tuple(
        value + (dx if index % 2 == 0 else dy)
        for index, value in enumerate(old_box)
    )
    assert _segment_box_gap((cut_line[:2], cut_line[2:]), box) >= 0.0035
    neighbors = (
        (0.22285, 0.1591, 0.33715, 0.2309),
        (0.363437, 0.093512, 0.386563, 0.176488),
    )
    assert all(sheet.box_gap(box, neighbor) >= 0.0035 for neighbor in neighbors)


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
        "block_callout", "pedestal_callout", "spring_callout", "nameplate_callout",
        "tap_callout",
    }
    assert {ast.unparse(value) for value in keywords["views"].values} == {
        "hole_top", "hole_side", "section"
    }
    finalize = next(call for call in calls if getattr(call.func, "id", None) == "finalize_drawing")
    assert check[0].lineno < finalize.lineno


@pytest.mark.parametrize(
    ("process_name", "expected_process_rows"),
    [
        ("TRANSFER_BLOCK_CALLOUT", f"TRANSFER FROM MHA-DT-18\nAFTER {step_ref('rig-set')};\n"),
        ("TRANSFER_PEDESTAL_CALLOUT", "TRANSFER FROM MHA-DT-02\nAT ASSEMBLY;\n"),
        ("TRANSFER_SPRING_CALLOUT", f"TRANSFER FROM MHA-DT-24\nAFTER {step_ref('rig-set')};\n"),
        ("CROSS_TAP_PROCESS", "COMMON THREAD LEAD IN BOTH WALLS\n"),
    ],
)
def test_base_callout_prefix_is_the_shared_helpers(
    process_name: str, expected_process_rows: str
) -> None:
    # Main's hb-notes-2 ruling (a): the block and pedestal callouts end their
    # process text with a newline so the 8-32 thread gets its own fourth line;
    # the cross-tap thread gets its own row the same way, and so does the
    # spring's since its step citation outgrew a joined row. add_native_hole_callout writes exactly
    # compose_hole_callout_prefix's result into the prefix DEFINITION.
    import draw_fr_harmonic_base as sheet

    native = "<hw-threaddesc> <hw-threadclass> <HOLE-DEPTH> <hw-threaddepth>"
    process = getattr(sheet, process_name)
    assert _drawing_hole_callout.compose_hole_callout_prefix(process, native) == (
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
     (" 48 MIN", [0.291044, 0.131166], 0.0035), ("MHA-FR-VN-53 TUBE CROSS-SCREWS", [0.250907, 0.125556], 0.0035),
     ("THRU BOTH WALLS, SINGLE CONTINUOUS THREAD", [0.230711, 0.12], 0.0035),
     ("DEPTHS FROM SPOTFACE FLOOR", [0.248979, 0.114444], 0.0035),
     ("ON A1-A4 X CENTRES", [0.261375, 0.108888], 0.0035),
     ("2 EACH FRONT/REAR FACE 10-32 UNF - 2B ", [0.229232, 0.103331], 0.0035),
     ("<HOLE-DEPTH>", [0.322837, 0.103278], 0.0035), (" 46.00", [0.327838, 0.103331], 0.0035)],
)
HB_RENDER_4_BOXES = {
    "MHA-DT-18 block transfer": (0.233047, 0.240834, 0.292540, 0.261110),
    "MHA-DT-02 pedestal transfer": (0.171047, 0.240834, 0.230540, 0.261110),
    "MHA-DT-24 spring transfer": (0.274041, 0.136412, 0.354372, 0.151132),
    "MHA-FR-VN-53 cross-tap": (0.229232, 0.103278, 0.342356, 0.134666),
}


def test_callout_rules_fail_the_hb_render_4_cross_tap_block() -> None:
    """Fail-first on real data: Main's hb-render-4 eye pass read the spring
    block 1.7 mm over the cross-tap block as its fourth row, and the cross-tap
    ran six rows. The side-by-side transfer pair is not one column."""
    import draw_fr_harmonic_base as sheet

    anchor, lines, texts = HB_RENDER_4_CROSS_TAP
    rows = sheet.callout_text_rows(lines, texts, "MHA-FR-VN-53 cross-tap")
    assert sheet.find_tall_callouts({"MHA-FR-VN-53 cross-tap": rows}) == [
        "callout MHA-FR-VN-53 cross-tap runs 6 rows, over the 4-row note rule"
    ]
    assert sheet.find_merged_blocks(HB_RENDER_4_BOXES) == [
        "callout MHA-DT-24 spring transfer over callout MHA-FR-VN-53 cross-tap: "
        "1.7 mm apart, under the 5.6 mm row pitch"
    ]
    assert sheet.find_tall_callouts({"four rows": dict(list(rows.items())[:4])}) == []


def test_cross_tap_callout_carries_hole_facts_only() -> None:
    # hb-render-4 eye pass: count/drill/depth, the thru instruction and the
    # thread each on a row; the depth datum is the model's (the tap starts on
    # the spotface floor) and the X location is a dimension, not text.
    import inspect

    import draw_fr_harmonic_base as sheet

    assert sheet.CROSS_TAP_PROCESS == "COMMON THREAD LEAD IN BOTH WALLS\n"
    assert "THRU" not in sheet.CROSS_TAP_PROCESS
    source = inspect.getsource(sheet)
    for gone in ("DEPTHS FROM SPOTFACE FLOOR\n", "ON A1-A4 X CENTRES\n", "2 EACH FRONT/REAR FACE"):
        assert gone not in source
    # The Hole Wizard seats the taps on the spotface floor, so its depths
    # already run from there.
    assert part.BASE_SPOTFACE_PLANE_Z - part.BASE_SPOTFACE_DEPTH == part.BASE_SCREW_SEAT_Z


def test_cross_tap_xs_are_baselines_from_the_flange_edge_on_the_front_view() -> None:
    # plate-r1 review (rule 10): the far pair was chained from the near one;
    # both now run from the table's X0 edge, the far one on the outer row.
    import draw_fr_harmonic_base as sheet

    assert fr_harmonic_base_spec.DRAWING_DIMENSIONS["CrossTapReference"] == {
        "CrossTapX", "CrossTapFarX"
    }
    assert "CrossTapReference" in part.REFERENCE_SKETCHES
    keep = sheet.HOLE_SIDE_KEEP
    assert {"CrossTapX", "CrossTapFarX"} <= set(keep)
    assert "CrossTapPitch" not in keep
    # Shortest innermost: the near tap's row sits between the view and the
    # far tap's.
    view_bottom = sheet.HOLE_SIDE_CENTER[1] - fr_harmonic_base_spec.STACK_HEIGHT * sheet.VIEW_SCALE / 2000.0
    assert keep["CrossTapFarX"][1] < keep["CrossTapX"][1] < view_bottom
    # 31.6 and 425.6 are also the table's A1/A2 and A3/A4 X LOCs from the same
    # flange edge.
    assert part.BOTTOM_LENGTH / 2.0 - part.COLUMN_X == pytest.approx(31.6)
    assert part.BOTTOM_LENGTH / 2.0 + part.COLUMN_X == pytest.approx(425.6)


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


def test_retained_pocket_walls_socket_bosses_and_cross_tap_lugs_keep_their_contracts() -> None:
    spec = fr_harmonic_base_spec
    assert spec.POCKET_HALF_X == pytest.approx(spec.TOP_LENGTH / 2.0 - spec.POCKET_WALL)
    assert spec.POCKET_HALF_Z == pytest.approx(spec.TOP_WIDTH / 2.0 - spec.POCKET_WALL)
    assert spec.STACK_HEIGHT - spec.POCKET_CEILING_Y == pytest.approx(spec.POCKET_SKIN)
    assert len(part.SOCKET_BOSS_SHAPES) == len(part.CROSS_TAP_LUG_SHAPES) == 4
    assert spec.CROSS_TAP_LUG_BOTTOM_Y == 26.5
    band = part._general_band_mm()
    assert min(part.CROSS_TAP_LUG_WALLS.values()) - 1.5 * band >= 2.0
    assert (
        part.CROSS_TAP_LUG_WALLS["past tip"]
        >= 1.5 * part.THREAD_MAJOR_MM[part.BASE_CROSS_TAP_SPEC.size]
    )
    assert part.SOCKET_BOSS_WALL == pytest.approx(8.0)


def test_cross_tap_remains_backed_when_the_pocket_ceiling_is_below_its_axis() -> None:
    spec = fr_harmonic_base_spec
    radius = part.THREAD_MAJOR_MM[part.BASE_CROSS_TAP_SPEC.size] / 2.0
    thread_bottom = part.BASE_SCREW_Y - radius
    thread_top = part.BASE_SCREW_Y + radius
    lug_interval = (spec.CROSS_TAP_LUG_BOTTOM_Y, spec.POCKET_CEILING_Y)
    skin_interval = (spec.POCKET_CEILING_Y, spec.GREEN_TOP)
    assert part.BASE_SCREW_Y - spec.POCKET_CEILING_Y == pytest.approx(0.3)
    # The bore crosses the shared boundary; lug below plus skin above is
    # continuous metal even though the ceiling is lower than the axis.
    assert lug_interval[0] < thread_bottom < lug_interval[1]
    assert lug_interval[1] == skin_interval[0]
    assert skin_interval[0] < thread_top < skin_interval[1]
    margins = part.cross_tap_backing_margins_mm(part._general_band_mm())
    assert margins["lug/skin join"] == pytest.approx(9.7)
    assert margins["green skin"] == pytest.approx(6.4)
    assert min(margins.values()) > 0.0
    # A looser stack loses finite lateral backing; the check cannot pass
    # simply because the nominal axis still lies above the lug bottom.
    assert min(part.cross_tap_backing_margins_mm(2.0).values()) < 0.0


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
    assert sheet.SERIAL_NOTE_XY == (0.098, 0.132)
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


def test_deck_finish_leader_takes_the_nearest_face_edge() -> None:
    import inspect

    import draw_fr_harmonic_base as sheet

    # Keep a real native-face attachment, just inside the nearest west edge.
    source = inspect.getsource(sheet)
    assert "deck_box[0] + DECK_FINISH_FACE_INSET_M" in source
    assert "(deck_box[2] + deck_box[5]) / 2.0" in source
    assert "deck_face.GetClosestPointOn(" in source
    attach = sheet._plan_xy(
        -part.DECK_HALF_X + sheet.DECK_FINISH_FACE_INSET_M * 1000.0, 0.0
    )
    nearest = sheet._plan_xy(-part.DECK_HALF_X, 0.0)
    # The attachment is one paper millimetre onto the deck, rather than the
    # old quarter-face point's 33 mm diagonal run across the plate (#1054).
    assert 0.0005 <= attach[0] - nearest[0] <= 0.0015
    assert abs(attach[1] - sheet.DECK_FINISH_XY[1]) <= 0.001


def test_hold_down_is_the_specified_screw() -> None:
    import build_fr_vn_lag_screw as screw

    assert screw.SKU == screw.SPECIFIED_SKU


def test_specified_hold_down_retains_engagement_and_reports_underside_protrusion() -> None:
    from fr_vn_lag_screw_spec import LENGTH_MM

    assert LENGTH_MM == 19.05
    insertion = LENGTH_MM - fr_harmonic_base_fasteners.SUPPORT_FOOT_THICKNESS - fr_harmonic_base_fasteners.HOLD_DOWN_BEARING_OFFSET
    material = part.THROUGH_SEAT_MATERIAL["SupportHoldDownSeats"][0]
    fit = fr_harmonic_base_fasteners.require_through_seat_fit(
        "specified rocker support", part.HOLD_DOWN_SEAT_SPEC, material,
        insertion_min_mm=insertion, insertion_max_mm=insertion,
    )
    assert fit.full_thread_engagement_min_mm == pytest.approx(10.10)
    assert fit.full_thread_engagement_min_mm >= 1.5 * 6.35
    assert fit.protrusion_max_mm == pytest.approx(insertion - material.exit_depth_min_mm)
    assert fit.protrusion_max_mm > 0.0
    assert fit.clearance_min_mm > 0.0


def test_cross_tap_drill_keeps_the_bottoming_lead_past_the_deepest_thread() -> None:
    from fr_frame_attachment_spec import CASTING_FULL_THREAD_DEPTH, CASTING_TAP_DRILL_DEPTH

    lead = 2.0 * 25.4 / 32.0
    # 48 MIN left 1.49 past 46.00 + 0.51, under two #10-32 pitches.
    band = fr_harmonic_base_fasteners.title_block_band_mm("linear_2pl")
    assert 48.0 - (CASTING_FULL_THREAD_DEPTH + band) < lead
    assert CASTING_TAP_DRILL_DEPTH - (CASTING_FULL_THREAD_DEPTH + band) >= lead


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
        # The deck Ra symbol above it carries no target text; its own
        # symbol box stands between this row and the R22.2 callout.
        "deck Ra symbol": sheet.DECK_FINISH_XY[1] - box[3],
        "deck Ra symbol to flange corner radius callout": 0.2104
        - (sheet.DECK_FINISH_XY[1] + sheet.FINISH_SYMBOL_TOP_M),
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


def test_underside_section_cuts_retained_lugs_and_rib_clear_of_taps() -> None:
    import draw_fr_harmonic_base as sheet

    x = sheet.UNDERSIDE_CUT_X
    assert part.COLUMN_X + sheet.SCREW_SPOTFACE_DIAMETER / 2.0 < x < part.POCKET_HALF_X
    assert any(s[1] < x < s[2] for s in part.CROSS_TAP_LUG_SHAPES)
    assert part.LONG_RIB_SHAPE[1] < x < part.LONG_RIB_SHAPE[2]
    assert all(
        abs(x - hx) > diameter / 2.0
        for _feature, stations, diameter in sheet.DECK_TAPPED_SEAT_FEATURES
        for hx, _z in stations
    )
    assert all(abs(x - hx) > sheet.SCREW_SPOTFACE_DIAMETER / 2.0 for hx, _z in part.COLUMN_SOCKET_XZ)
    # The unavoidable socket section is retained structure, not an old pad.
    assert any(abs(x - hx) < part.COLUMN_SOCKET_DIAMETER / 2.0 for hx, _z in part.COLUMN_SOCKET_XZ)
    assert _pocket_shape_covers(
        next(s for s in part.CROSS_TAP_LUG_SHAPES if s[1] < x < s[2] and s[4] > 0),
        x, sheet.UNDERSIDE_SECTION_TEXT_MM["LugBottom"][1],
    )


def test_underside_section_texts_sit_in_open_air() -> None:
    # Heights and lug-bottom captions stay outside the underside silhouette.
    import draw_fr_harmonic_base as sheet

    num, den = sheet.UNDERSIDE_SECTION_SCALE
    texts = sheet.UNDERSIDE_SECTION_TEXT_MM
    assert set(texts) == {"PocketDepth", "LugBottom", "RibRelief"}

    def rows(name: str) -> list[str]:
        return ["00.0", *sheet.UNDERSIDE_SECTION_CALLOUTS.get(name, "").split("\n")]

    for name, (y, _z) in texts.items():
        half_w_mm = max(map(len, rows(name))) * _DIM_CHAR_M * 1000.0 / 2.0
        assert half_w_mm + 2.0 < -y * num / den, name
    # SolidWorks centres a callout's rows on the keep (5.8 mm a row on paper),
    # its line under the last; the ceiling's text keeps a 3.5 mm row, 2 mm of
    # air and that line's half-row clear of every other block.
    z = texts["PocketDepth"][1]
    assert abs(z) + 3.0 < fr_harmonic_base_spec.POCKET_HALF_Z
    # PocketDepth's dimension line crosses open air, not retained structure.
    retained = (
        *part.SOCKET_BOSS_SHAPES,
        part.LONG_RIB_SHAPE,
        part.CROSS_RIB_SHAPE,
        *part.CROSS_TAP_LUG_SHAPES,
    )
    for dz in (-3.0, 0.0, 3.0):
        covering = [s for s in retained if _pocket_shape_covers(s, sheet.UNDERSIDE_CUT_X, z + dz)]
        assert covering == [], (dz, covering)
    for name, (_y, other_z) in texts.items():
        if name == "PocketDepth":
            continue
        reach_mm = len(rows(name)) * 5.8 / 2.0 + 0.6 + 2.0 + 3.5 / 2.0
        assert abs(z - other_z) * num / den > reach_mm, name
    assert set(sheet.UNDERSIDE_SECTION_CALLOUTS) <= set(texts)


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
    # The outside texts' widest row includes the lug-bottom caption.
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


def test_retained_underside_callouts_define_socket_bosses_ribs_and_lug_bottoms() -> None:
    import draw_fr_harmonic_base as sheet

    spec = fr_harmonic_base_spec
    callouts = sheet.UNDERSIDE_BOTTOM_CALLOUTS
    assert set(sheet.UNDERSIDE_BOTTOM_KEEP) == {
        "PocketLen", "PocketWid", "PocketX", "PocketY", "SocketBossDia",
        "PocketFilletRadius", "LongRibThickness", "CrossRibThickness",
    }
    assert callouts["SocketBossDia"] == "4X SOCKET\nBOSSES"
    assert callouts["PocketFilletRadius"] == f"{part.POCKET_FILLET_COUNT}X POCKET\nCORNERS"
    assert sheet.UNDERSIDE_SECTION_CALLOUTS == {
        "LugBottom": "4X LUG\nBOTTOMS",
        "RibRelief": "BOTH\nRIBS",
    }
    # Sheet-3 texts above the view: inside the border, clear of the view, of
    # each other and of the view's note.
    keep = sheet.UNDERSIDE_BOTTOM_KEEP
    view_top = sheet._bottom_xy(0.0, spec.BOTTOM_REAR_Z)[1]
    boxes = {}
    for name, value in (("CrossRibThickness", "10.0"),):
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
        sheet.UNDERSIDE_LUGS_KEEP,
        sheet.UNDERSIDE_SECTION_TEXT_MM,
    )
    names = [name for keep in keeps for name in keep]
    assert len(names) == len(set(names))
    assert set(names) == set(fr_harmonic_base_spec.DRAWING_PRECISION_BY_NAME)
    assert set(sheet.UNDERSIDE_BOTTOM_CALLOUTS) <= set(sheet.UNDERSIDE_BOTTOM_KEEP)


def test_pad_deck_and_pocket_are_placed_from_x0_y0_as_baselines() -> None:
    # plate-r1 review (rule 10): the pad, deck and pocket were located only by
    # the word CENTERED. PlanReference places each from X0 Y0, the flange's
    # outer sharp corner: pad and deck on sheet 1's plan, pocket on sheet 3's
    # bottom view, each pair shortest innermost.
    import draw_fr_harmonic_base as sheet

    spec = fr_harmonic_base_spec
    assert "PlanReference" in part.REFERENCE_SKETCHES
    assert spec.DRAWING_DIMENSIONS["PlanReference"] == {"PadX", "PadY", "DeckX", "DeckY", "PocketX", "PocketY"}
    words = " ".join((*sheet.GEOMETRY_CALLOUTS.values(), *sheet.UNDERSIDE_BOTTOM_CALLOUTS.values()))
    assert "CENTERED" not in words

    def box(xy: tuple[float, float], value: str) -> tuple[float, float, float, float]:
        half_w = len(value) * _DIM_CHAR_M / 2.0
        return (xy[0] - half_w, xy[1] - _DIM_TEXT_H_M / 2.0, xy[0] + half_w, xy[1] + _DIM_TEXT_H_M / 2.0)

    # Sheet 1: X0 Y0 is the plan's bottom-left (rear-west) corner.
    x0, y0 = sheet._plan_xy(-spec.BOTTOM_LENGTH / 2.0, spec.BOTTOM_REAR_Z)
    keep = sheet.GEOMETRY_TOP_KEEP
    texts = {
        name: box(keep[name], value)
        for name, value in (("PadX", "6.35"), ("DeckX", "61.6"), ("PadY", "6.35"), ("DeckY", "13.35"))
    }
    assert y0 > keep["PadX"][1] > keep["DeckX"][1]
    assert x0 > keep["PadY"][0] > keep["DeckY"][0]
    deck_witness_x = sheet._plan_xy(-spec.DECK_HALF_X, 0.0)[0]
    pad_witness_x = sheet._plan_xy(-spec.TOP_LENGTH / 2.0, 0.0)[0]
    # Both X texts read right of X0's witness line; the 6.35 past its own
    # span and short of DeckX's witness line, the 61.6 inside its span.
    assert pad_witness_x + 0.0015 < texts["PadX"][0] and texts["PadX"][2] < deck_witness_x - 0.0015
    assert x0 + 0.0015 < texts["DeckX"][0] and texts["DeckX"][2] < deck_witness_x
    # Both Y texts read left of X0's witness line: the inner one below the
    # corner, the outer one above its span.
    deck_y = sheet._plan_xy(0.0, spec.DECK_HALF_Z)[1]
    assert texts["PadY"][2] < x0 - 0.0015 and texts["PadY"][3] < y0 - 0.001
    assert texts["DeckY"][1] > deck_y + 0.001
    # PR #1468 r4 review: DeckY's lower arrow runs below X0 Y0 through the
    # PadY text's rows, and that text prints left of its own line, ending
    # ~1.6 mm short of it. DeckY's line must stand clear left of the text.
    pad_y_text_left = keep["PadY"][0] - 0.0016 - len("6.35") * _DIM_CHAR_M
    assert keep["DeckY"][0] < pad_y_text_left - 0.0015
    for a in texts:
        for b in texts:
            if a < b:
                assert _box_gap(texts[a], texts[b]) > 0.0015, (a, b)
    # The DeckX line runs ~2.8 mm under its text (plate-r1 render); its
    # witness lines end 0.5 mm past it, clear above the stamped-ID note's top
    # row (which reads ~0.6 mm above the note's anchor).
    assert keep["DeckX"][1] - 0.0028 - 0.0005 > sheet.SERIAL_NOTE_XY[1] + 0.0006 + 0.0015
    # The deck Ra symbol and its leader stay above the corner group.
    assert sheet.DECK_FINISH_XY[1] > max(text[3] for text in texts.values()) + 0.020

    # Sheet 3: X0 Y0 is the bottom view's top-left corner.
    x0, y0 = sheet._bottom_xy(-spec.BOTTOM_LENGTH / 2.0, spec.BOTTOM_REAR_Z)
    keep = sheet.UNDERSIDE_BOTTOM_KEEP
    pocket_x = box(keep["PocketX"], "18.35")
    pocket_y = box(keep["PocketY"], "18.35")
    wall_x = sheet._bottom_xy(-spec.POCKET_HALF_X, 0.0)[0]
    wall_y = sheet._bottom_xy(0.0, spec.POCKET_HALF_Z)[1]
    # Above the rear edge, right of its span; the dimension line ~2.8 mm under
    # the text still clears the outline.
    assert pocket_x[1] - 0.0028 + _DIM_TEXT_H_M / 2.0 > y0 + 0.002
    assert pocket_x[0] > wall_x + 0.0015
    # Section arrow B and its letter reach 19 mm west of the cut line
    # (plate-r1 render).
    cut_x = sheet._bottom_xy(sheet.UNDERSIDE_CUT_X, 0.0)[0]
    assert pocket_x[2] < cut_x - 0.019 - 0.005
    # Left of the west edge, below its span.
    assert pocket_y[2] < x0 - 0.0015 and pocket_y[3] < wall_y - 0.001
    assert _box_gap(pocket_x, pocket_y) > 0.0015


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


def _lug_vertices() -> dict[str, tuple[float, float]]:
    """Machine (X, Z) of each retained sheet-4 baseline's endpoint."""
    lug0, lug1, _lug2, lug3 = part.CROSS_TAP_LUG_SHAPES
    long_rib, cross_rib = part.LONG_RIB_SHAPE, part.CROSS_RIB_SHAPE
    return {
        "Lug1X": (lug1[2], lug1[3]),
        "CrossRibX": (cross_rib[1], cross_rib[4]),
        "Lug3X": (lug3[1], lug3[3]),
        "Lug1Y": (lug1[2], lug1[3]),
        "LongRibY": (long_rib[1], long_rib[4]),
        "Lug0Y": (lug0[2], lug0[4]),
    }


def _lug_printed() -> dict[str, float]:
    spec = fr_harmonic_base_spec
    return {
        name: (x + spec.BOTTOM_LENGTH / 2.0) if name.endswith("X") else (spec.BOTTOM_REAR_Z - z)
        for name, (x, z) in _lug_vertices().items()
    }


def test_underside_lug_sheet_preserves_retained_locations_from_x0_y0() -> None:
    import draw_fr_harmonic_base as sheet

    spec = fr_harmonic_base_spec
    assert sheet.SHEET_NAMES[3] == "UNDERSIDE-LUGS"
    marked = {name for names in spec.UNDERSIDE_LOCATION_DIMENSIONS.values() for name in names}
    assert set(sheet.UNDERSIDE_LUGS_KEEP) == marked == set(_lug_vertices())
    for feature, names in spec.UNDERSIDE_LOCATION_DIMENSIONS.items():
        assert set(names) <= spec.DRAWING_DIMENSIONS[feature]
    assert {feature for feature, _name in spec.UNDERSIDE_LOCATION_PREFIXES} <= set(
        spec.UNDERSIDE_LOCATION_DIMENSIONS
    )
    assert {name for _feature, name in spec.UNDERSIDE_LOCATION_PREFIXES} <= marked
    printed = {name: round(value, 1) for name, value in _lug_printed().items()}
    assert printed == {
        "Lug1X": 39.6,
        "CrossRibX": 223.6,
        "Lug3X": 417.6,
        "Lug1Y": 68.6,
        "LongRibY": 138.6,
        "Lug0Y": 218.6,
    }
    assert sheet.LUGS_DATUM == pytest.approx(
        sheet._lugs_xy(-spec.BOTTOM_LENGTH / 2.0, spec.BOTTOM_REAR_Z)
    )
    for baselines in (sheet.LUGS_X_ROWS, sheet.LUGS_Y_COLUMNS):
        values = [printed[name] for name, *_ in baselines]
        assert values == sorted(values)


def test_retained_lug_bottom_is_a_native_model_dimension_not_a_removed_cast_level() -> None:
    import draw_fr_harmonic_base as sheet

    assert fr_harmonic_base_spec.DRAWING_DIMENSIONS["CrossTapLugs"] == {"LugBottom"}
    assert fr_harmonic_base_spec.DRAWING_PRECISION_BY_NAME["LugBottom"] == 1
    assert sheet.UNDERSIDE_SECTION_CALLOUTS["LugBottom"] == "4X LUG\nBOTTOMS"
    assert set(sheet.LUGS_LEVEL_NOTES) == {"cross-tap lug bottoms"}
    text, _xy, (x, z) = sheet.LUGS_LEVEL_NOTES["cross-tap lug bottoms"]
    assert text == "LUG BOTTOMS:\nSECTION B-B, SHEET 3"
    assert any(
        s[1] + 1.0 < x < s[2] - 1.0 and s[3] + 1.0 < z < s[4] - 1.0
        for s in part.CROSS_TAP_LUG_SHAPES
    )


def test_underside_lug_texts_fit_the_border_and_clear_every_retained_baseline() -> None:
    import draw_fr_harmonic_base as sheet

    spec = fr_harmonic_base_spec
    prefixes = {name: prefix for (_f, name), prefix in spec.UNDERSIDE_LOCATION_PREFIXES.items()}
    printed = _lug_printed()
    boxes = {}
    for name, (x, y) in sheet.UNDERSIDE_LUGS_KEEP.items():
        half_w = len(f"{prefixes.get(name, '')}{printed[name]:.1f}") * _DIM_CHAR_M / 2.0
        boxes[name] = (x - half_w, y - _DIM_TEXT_H_M / 2.0, x + half_w, y + _DIM_TEXT_H_M / 2.0)
    view = (
        *sheet._lugs_xy(-spec.BOTTOM_LENGTH / 2.0, spec.BOTTOM_FRONT_Z),
        *sheet._lugs_xy(spec.BOTTOM_LENGTH / 2.0, spec.BOTTOM_REAR_Z),
    )
    rows = sheet.LUGS_NOTE.split("\n")
    note = (
        sheet.LUGS_NOTE_XY[0],
        sheet.LUGS_NOTE_XY[1] - len(rows) * _NOTE_LINE_MM / 1000.0,
        sheet.LUGS_NOTE_XY[0] + max(map(len, rows)) * _NOTE_CHAR_MM / 1000.0,
        sheet.LUGS_NOTE_XY[1],
    )
    level_notes, leaders = {}, {}
    for label, (text, (x, y), tip_mm) in sheet.LUGS_LEVEL_NOTES.items():
        rows = text.split("\n")
        box = (x, y - len(rows) * _NOTE_LINE_MM / 1000.0, x + max(map(len, rows)) * _NOTE_CHAR_MM / 1000.0, y)
        level_notes[label] = box
        tip = sheet._lugs_xy(*tip_mm)
        side = box[0] if abs(tip[0] - box[0]) < abs(tip[0] - box[2]) else box[2]
        assert not box[0] < tip[0] < box[2], label
        leaders[label] = [((side, (box[1] + box[3]) / 2.0), tip)]
        assert view[0] < tip[0] < view[2] and view[1] < tip[1] < view[3], label
    labelled = {"note": note, **boxes, **level_notes}
    for label, box in {"view": view, **labelled}.items():
        assert _BORDER_INNER_M[0] + 0.002 < box[0], label
        assert _BORDER_INNER_M[1] + 0.002 < box[1], label
        assert box[2] < _BORDER_INNER_M[2] - 0.002, label
        assert box[3] < _BORDER_INNER_M[3] - 0.002, label
        assert _box_gap(box, _TITLE_BLOCK_M) > 0.002, label
    for label, box in {**boxes, **level_notes}.items():
        assert _box_gap(box, view) > 0.002, label
    for a in labelled:
        for b in labelled:
            if a < b:
                assert _box_gap(labelled[a], labelled[b]) > 0.0015, (a, b)
    over = 0.002
    datum = sheet.LUGS_DATUM
    vertices = {name: sheet._lugs_xy(*xz) for name, xz in _lug_vertices().items()}
    lines = {}
    for name, _x in sheet.LUGS_X_ROWS:
        (vx, vy), (tx, ty) = vertices[name], sheet.UNDERSIDE_LUGS_KEEP[name]
        lines[name] = [((vx, vy), (vx, ty + over)), ((datum[0], ty), (max(vx, tx), ty))]
    for name, *_ in sheet.LUGS_Y_COLUMNS:
        (vx, vy), (tx, ty) = vertices[name], sheet.UNDERSIDE_LUGS_KEEP[name]
        assert vy + _DIM_TEXT_H_M < ty < datum[1] - _DIM_TEXT_H_M, name
        lines[name] = [((vx, vy), (tx - over, vy)), ((tx, datum[1]), (tx, vy))]
    assert set(lines) == set(boxes)
    for name, box in boxes.items():
        for other, segments in lines.items():
            if other != name:
                for segment in segments:
                    assert _segment_box_gap(segment, box) > 0.001, (name, other, segment)
    for name, box in level_notes.items():
        for other, segments in {**lines, **leaders}.items():
            if other != name:
                for segment in segments:
                    assert _segment_box_gap(segment, box) > 0.001, (name, other, segment)
    for label, (leader,) in leaders.items():
        for name, box in {"note": note, **boxes}.items():
            assert _segment_box_gap(leader, box) > 0.001, (label, name)
        for other, segments in lines.items():
            for (x0, y0), (x1, y1) in segments:
                line_box = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
                assert _segment_box_gap(leader, line_box) > 0.0005, (label, other)


def test_nameplate_seats_are_transferred_through_the_plate() -> None:
    # #628 (Main ruling, option A): the four #4-40 taps are spotted through
    # the finished MHA-FR-04 plate at assembly, so they leave the hole table
    # (the former F rows) and their one callout names the plate.
    import draw_fr_harmonic_base as sheet

    seats = {(x, z, part.NAMEPLATE_SCREW_HOLE_DIA) for x, z in part.NAMEPLATE_SCREW_XZ}
    assert set(sheet.TRANSFER_NAMEPLATE_HOLES) == seats
    assert seats <= set(sheet.TRANSFER_HOLES)
    assert not seats & set(sheet.TABLE_HOLES)
    assert sheet.TRANSFER_NAMEPLATE_CALLOUT == "TRANSFER FROM MHA-FR-04\nAT ASSEMBLY;"
    assert not any(tag.startswith("F") for tag in sheet.HOLE_TAG_POSITIONS)
    # The leader lands on the plan's right, upper (rear-east) tap.
    taps = [sheet._plan_xy(x, z, center=sheet.HOLE_TOP_CENTER) for x, z, _ in seats]
    leader_tap = sheet._plan_xy(
        *sheet.TRANSFER_NAMEPLATE_LEADER_HOLE[:2], center=sheet.HOLE_TOP_CENTER
    )
    assert leader_tap[0] == pytest.approx(max(x for x, _ in taps), abs=1e-5)
    assert leader_tap[1] == pytest.approx(max(y for _, y in taps), abs=1e-5)


def test_nameplate_callout_reads_in_the_top_band_its_leader_clear_of_the_tags() -> None:
    # Box from the hb-callout-cal display data of a three-row "TRANSFER FROM
    # ... / AT ASSEMBLY; 4-40 UNC - 2B" block (E0E287C83's spring callout):
    # 80.3 mm by 14.7 mm, centred 1 mm under its anchor. Its leader leaves the
    # near (left) shoulder end, the box's lower-left corner.
    import draw_fr_harmonic_base as sheet

    spring = sheet.callout_text_box(
        *E0E287C83_CALLOUTS["MHA-DT-24 spring transfer"], "spring"
    )
    half_w = (spring[2] - spring[0]) / 2.0
    half_h = (spring[3] - spring[1]) / 2.0
    x, y = sheet.NAMEPLATE_CALLOUT_XY
    box = (x - half_w, y - 0.001 - half_h, x + half_w, y - 0.001 + half_h)
    assert box[3] < _BORDER_INNER_M[3] - 0.003
    assert box[2] < _BORDER_INNER_M[2] - 0.005
    # Its top row level with the four-row block callout's beside it, 10 mm
    # or more clear of that block's widest prefix row.
    block_chars = max(map(len, sheet.TRANSFER_BLOCK_CALLOUT.rstrip("\n").split("\n")))
    block_half_w = block_chars * _DIM_CHAR_M * 1.08 / 2.0
    assert box[0] - (sheet.BLOCK_CALLOUT_XY[0] + block_half_w) > 0.010
    block_top = sheet.BLOCK_CALLOUT_XY[1] - 0.001 + 2 * half_h * 4 / 3 / 2.0
    assert abs(box[3] - block_top) < 0.0015
    tap = sheet._plan_xy(
        *sheet.TRANSFER_NAMEPLATE_LEADER_HOLE[:2], center=sheet.HOLE_TOP_CENTER
    )
    leader = ((box[0], box[1]), tap)
    tag_boxes = {
        tag: (tx, ty - _DIM_TEXT_H_M, tx + 2 * _DIM_CHAR_M, ty)
        for tag, (tx, ty) in sheet.HOLE_TAG_POSITIONS.items()
    }
    for tag, tag_box in tag_boxes.items():
        assert _segment_box_gap(leader, tag_box) > 0.0015, tag
    # West of section line A, which rises over the plan to its arrow.
    section_x = sheet._plan_xy(
        fr_harmonic_base_spec.COLUMN_X, 0.0, center=sheet.HOLE_TOP_CENTER
    )[0]
    assert max(leader[0][0], leader[1][0]) < section_x - 0.004


def test_rig_callouts_cite_the_drive_train_rig_set_step() -> None:
    # User ruling P1-2: the rig seats are spotted only after the rig is set.
    # plate-r1 review (over-specification): the five-line RIG SET procedure
    # was an assembly set-up for other parts, so it lives on MHA-DT-00 and
    # each rig callout cites that step by key, never a typed number. The
    # pedestal seats are not rig seats.
    import inspect

    import draw_fr_harmonic_base as sheet
    import dt_drive_train_steps as steps

    cite = f"AFTER {step_ref('rig-set')};"
    assert cite == f"AFTER MHA-DT-00 STEP {steps.step_number('rig-set')};"
    assert steps.step_number("rig-set") < steps.step_number("rig-seats-transferred")
    for text in (sheet.TRANSFER_BLOCK_CALLOUT, sheet.TRANSFER_SPRING_CALLOUT):
        lines = text.rstrip("\n").split("\n")
        assert len(lines) == 2, text
        assert lines[1] == cite
    assert "STEP" not in sheet.TRANSFER_PEDESTAL_CALLOUT
    # The sheet carries no copy of the procedure.
    source = inspect.getsource(sheet)
    assert "RIG_SET_STEP" not in source and "pinion_rig_fitup" not in source


# The note's printed character advance and line pitch at the sheet's 3.5 text
# height (read off the pc-p1 render of the old RIG SET note).
_NOTE_CHAR_MM = 2.69
_NOTE_LINE_MM = 4.58


def test_numbered_note_and_wider_flags_predict_clearance_in_the_proven_lanes() -> None:
    import draw_fr_harmonic_base as sheet

    assert sheet.PIVOT_SEAT_NOTE_XY == (0.020, 0.100)
    assert sheet.HOLE_TOP_KEEP["PivotSeatX"] == (0.2427, 0.1320)
    assert sheet.HOLE_TOP_KEEP["PivotSeatY"] == (0.2616, 0.1705)
    assert sheet.PIVOT_SEAT_Y_TEXT_XY == (0.2735, 0.1850)
    assert sheet.HOLE_TAG_POSITIONS["D1"] == (0.2456, 0.1550)
    assert sheet.HOLE_SIDE_KEEP["SpotFaceDia"] == (0.193, 0.135)

    # Native-r4 embedded-font calibration supplies conservative NEW text-width
    # estimates. This is not a claim that numbered note 1 has printed natively.
    row_widths = (0.0930785, 0.0973665, 0.0665752)
    pitch = 0.0045257
    x, y = sheet.PIVOT_SEAT_NOTE_XY
    note = (x, y - len(row_widths) * pitch, x + max(row_widths), y - pitch + 0.0035)
    neighbors = {
        "table": (0.018, 0.1630628306, 0.1627633865, 0.260),
        "plan": (0.22285, 0.1591, 0.33715, 0.2309),
        "front": (0.22285, 0.08865, 0.33715, 0.10135),
        "spotface": (0.168835, 0.123861, 0.218752, 0.144083),
        "title block": _TITLE_BLOCK_M,
    }
    for label, box in neighbors.items():
        assert _box_gap(note, box) >= 0.0035, label
    assert note[0] - _BORDER_INNER_M[0] >= 0.0035
    assert note[1] - _BORDER_INNER_M[1] >= 0.0035

    # Values retain their native r4 size. SEE NOTE 1 is conservatively 24.7 mm
    # wide, not the smaller SEE D1 or the initial 22 mm estimate.
    x_value = (0.2291351, 0.1292219, 0.2562650, 0.1327219)
    y_value = (0.2599351, 0.1822219, 0.2870650, 0.1857219)
    x_flag = (0.2427 - 0.01235, 0.1347819, 0.2427 + 0.01235, 0.1382819)
    y_flag = (0.2735 - 0.01235, 0.18778, 0.2735 + 0.01235, 0.19128)
    letters = {
        "X": (0.242401, 0.142429, 0.245245, 0.148808),
        "X zero": (0.218557, 0.142407, 0.221143, 0.148787),
        "Y": (0.207974, 0.175453, 0.210736, 0.181833),
        "Y zero": (0.208062, 0.152902, 0.210648, 0.159282),
    }
    witnesses = [
        ((wx, x_value[1] - 0.001), (wx, end_y))
        for wx, end_y in _R2B_PIVOT_X_WITNESS_STARTS
    ]
    for label, box in {"X value": x_value, "Y value": y_value, "X flag": x_flag, "Y flag": y_flag}.items():
        for name, letter in letters.items():
            assert _box_gap(box, letter) >= 0.0035, (label, name)
        for witness in witnesses:
            assert _segment_box_gap(witness, box) >= 0.002, label
    tags = {
        "D1": (0.2456, 0.1504743, 0.252004, 0.1539743),
        "E1": (0.297, 0.1849743, 0.30209, 0.1884743),
        "E2": (0.289, 0.2014743, 0.29409, 0.2049743),
        "B1": (0.2467835, 0.1894801, 0.2520481, 0.1929801),
    }
    for box in (x_flag, y_value, y_flag):
        for label, tag in tags.items():
            assert _box_gap(box, tag) >= 0.0035, label
    y_offset_leader = ((0.2616, 0.1705186), (0.2599351, 0.1822219))
    assert _segment_box_gap(y_offset_leader, y_flag) >= 0.0035
    assert _segment_box_gap(y_offset_leader, tags["B1"]) >= 0.0035


def test_pivot_seat_setup_identifies_its_mate_without_numeric_offsets() -> None:
    """Setup identification stays on the note; dimensions own the location
    and band. The table's D1 identity still resolves to the actual pivot."""
    import re

    import cone_set_stack
    import draw_fr_harmonic_base as sheet
    import fr_harmonic_base_spec as base_spec

    assert sheet.PIVOT_SEAT_STEP is base_spec.PIVOT_SEAT_STEP
    assert base_spec.PIVOT_SEAT_TAG == "D1"
    assert base_spec.PIVOT_SEAT_POSITION_BAND_MM == cone_set_stack.PIVOT_SEAT_POSITION_MM
    assert sheet.PIVOT_SEAT_STEP.split("\n") == [
        "1. D1 IS LOCATED TO THE MHA-DT-02 SEAT;",
        "DRILL AND TAP AT ASSEMBLY IN ONE SETUP.",
        "D1 TABLE X/Y ARE REFERENCE.",
    ]
    # Only the note number and part/table identities may contain digits;
    # the native dimensions remain the sole owners of offsets and bands.
    identification = sheet.PIVOT_SEAT_STEP.removeprefix("1. ")
    for identity in (base_spec.PIVOT_SEAT_TAG, "MHA-DT-02"):
        assert identity in identification
        identification = identification.replace(identity, "")
    assert not re.search(r"\d|<MOD-PM>|±", identification)
    # D1 remains the table's only 10-24 row and resolves to the pivot station.
    pivot_size = [h for h in sheet.TABLE_HOLES if h[2] == sheet.PIVOT_SCREW_HOLE_DIA]
    assert pivot_size == [(*sheet.PIVOT_SCREW_XZ, sheet.PIVOT_SCREW_HOLE_DIA)]


def test_numbered_d1_note_is_created_once_as_an_ordinary_free_note() -> None:
    import ast
    import inspect

    import draw_fr_harmonic_base as sheet

    tree = ast.parse(inspect.getsource(sheet.build))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    notes = [
        node for node in calls
        if any(isinstance(arg, ast.Name) and arg.id == "PIVOT_SEAT_STEP" for arg in node.args)
    ]
    assert len(notes) == 1
    assert notes[0].func.id == "add_note"
    assert [ast.unparse(arg) for arg in notes[0].args] == [
        "adapter", "PIVOT_SEAT_STEP", "*PIVOT_SEAT_NOTE_XY",
    ]
    assert notes[0].keywords == []
    hole_sheet = [
        node for node in calls
        if getattr(node.func, "attr", None) == "ActivateSheet"
        and ast.unparse(node.args[0]) == "SHEET_NAMES[1]"
        and node.lineno < notes[0].lineno
    ]
    assert hole_sheet
    underside_sheet = next(
        node for node in calls
        if getattr(node.func, "attr", None) == "ActivateSheet"
        and ast.unparse(node.args[0]) == "SHEET_NAMES[2]"
    )
    assert notes[0].lineno < underside_sheet.lineno
    assert "pivot_seat_rim" not in inspect.getsource(sheet.build)
    assert not hasattr(sheet, "_route_pivot_seat_note")
    check = next(node for node in calls if getattr(node.func, "id", None) == "_check_hole_sheet_callouts")
    assert {keyword.arg for keyword in check.keywords} == {"callouts", "views", "datum_origin"}
    flags = [node for node in calls if getattr(node.func, "id", None) == "_flag_pivot_seat_dimensions"]
    assert len(flags) == 1
    assert [ast.unparse(arg) for arg in flags[0].args] == ["adapter", "hole_top_dimensions"]
    assert not any(getattr(node.func, "attr", None) == "SetText2" for node in calls)


def test_pivot_offsets_share_native_marks_precision_and_authoritative_band() -> None:
    import ast
    import inspect

    import draw_fr_harmonic_base as sheet

    spec = fr_harmonic_base_spec
    near = min(part.PEDESTAL_SCREW_XZ, key=lambda xz: math.dist(xz, part.PIVOT_SCREW_XZ))
    assert part.PIVOT_NEAR_PEDESTAL_XZ == near
    assert part.PIVOT_SEAT_OFFSETS_MM == pytest.approx(
        (part.PIVOT_SCREW_XZ[0] - near[0], near[1] - part.PIVOT_SCREW_XZ[1])
    )
    names = set(spec.PIVOT_SEAT_DIMENSIONS)
    assert names == spec.DRAWING_DIMENSIONS["PivotSeatReference"]
    assert names == set(sheet.HOLE_TOP_KEEP)
    assert spec.DRAWING_PRECISION["PivotSeatReference"] == dict.fromkeys(names, 2)
    # Both offsets, not their unprinted origin anchors, receive the unchanged
    # functional band. This checks bindings rather than a setter's formatting.
    tree = ast.parse(inspect.getsource(part.build))
    loops = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Name)
        and node.iter.id == "PIVOT_SEAT_DIMENSIONS"
    ]
    assert len(loops) == 1
    setters = [
        node for node in ast.walk(loops[0])
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "set_dimension_symmetric_tolerance"
    ]
    assert len(setters) == 1
    assert ast.literal_eval(setters[0].args[1]) == "PivotSeatReference"
    assert isinstance(setters[0].args[2], ast.Name)
    assert setters[0].args[2].id == loops[0].target.id
    assert isinstance(setters[0].args[3], ast.Name)
    assert getattr(part, setters[0].args[3].id) == spec.PIVOT_SEAT_POSITION_BAND_MM
    # A blanked owner needs the opt-in importer in this specific top view,
    # and its result participates in the existing final precision readback.
    drawing = ast.parse(inspect.getsource(sheet.build))
    imports = [
        node for node in ast.walk(drawing)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
        and any(
            keyword.arg == "keep" and isinstance(keyword.value, ast.Name)
            and keyword.value.id == "HOLE_TOP_KEEP"
            for keyword in node.value.keywords
        )
    ]
    assert len(imports) == 1
    assert imports[0].value.func.id == "curate_hidden_owner_dimensions"
    imported_name = imports[0].targets[0].id
    body = drawing.body[0].body
    placement = body[body.index(imports[0]) + 1]
    assert isinstance(placement, ast.Expr) and isinstance(placement.value, ast.Call)
    assert placement.value.func.id == "_place_pivot_seat_y"
    assert [ast.unparse(argument) for argument in placement.value.args] == [
        "adapter", imported_name,
    ]
    precision = [
        node for node in ast.walk(drawing)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "assert_imported_precision"
    ]
    assert len(precision) == 1
    assert any(
        isinstance(node, ast.Starred) and isinstance(node.value, ast.Name)
        and node.value.id == imported_name
        for node in ast.walk(precision[0])
    )


def test_height_baselines_preserve_the_spotface_top_land_at_loose_limits() -> None:
    import draw_fr_harmonic_base as sheet

    spec = fr_harmonic_base_spec
    assert part.HEIGHT_REFERENCE_ORIGIN == (-spec.BOTTOM_LENGTH / 2.0, 0.0)
    stations = {name: (x, height) for name, x, height, _dx, _dy in part.HEIGHT_REFERENCE_STATIONS}
    assert stations == {
        "GreenTopHeight": (-spec.TOP_LENGTH / 2.0, spec.GREEN_TOP),
        "CrossScrewAxisHeight": (-part.COLUMN_X, part.BASE_SCREW_Y),
    }
    assert spec.DRAWING_DIMENSIONS["HeightReference"] == set(stations)
    assert spec.DRAWING_PRECISION["HeightReference"] == dict.fromkeys(stations, 1)
    assert "GreenTopHeight" in sheet.SIDE_KEEP
    assert "CrossScrewAxisHeight" in sheet.HOLE_SIDE_KEEP
    assert {"BottomThickness", "DeckRise"} <= set(sheet.SIDE_KEEP)
    kept = set(spec.DRAWING_PRECISION_BY_NAME)
    assert not {"FlangeToDeck", "Spot0Y"} & kept
    assert spec.GREEN_TOP + spec.DECK_RISE == pytest.approx(spec.STACK_HEIGHT)
    band = part._general_band_mm()
    assert band == pytest.approx(0.8)
    land = spec.cross_screw_top_land_worst_case_mm(
        part.BASE_SCREW_Y, part.SCREW_SPOTFACE_DIAMETER, band
    )
    assert land == pytest.approx(
        (47.8 - 0.8) - (38.1 + 0.8) - (9.0 + 0.8) / 2.0
    )
    assert land == pytest.approx(3.2)
    assert land >= spec.CROSS_SCREW_TOP_LAND_MIN_MM == 2.0
    # The former chain had another independent .X term and left only 1.6:
    # the unchanged solid was not protected by the old printed dimensions.
    chained_green_min = (
        spec.BOTTOM_THICKNESS - band + spec.TOP_THICKNESS - band
        - (spec.DECK_RISE + band)
    )
    chained_land = (
        chained_green_min - (part.BASE_SCREW_Y + band)
        - (part.SCREW_SPOTFACE_DIAMETER + band) / 2.0
    )
    assert chained_land < spec.CROSS_SCREW_TOP_LAND_MIN_MM


@pytest.mark.parametrize("reference", ("pivot", "height"))
def test_reference_dimensions_measure_actual_points_without_solid_features(
    monkeypatch, reference,
) -> None:
    import ast
    import asyncio
    import operator
    from types import SimpleNamespace

    from _sketch import SketchDims

    expected_plane = "Top" if reference == "pivot" else "Front"

    def result(data=None):
        return SimpleNamespace(is_success=True, data=data, error=None)

    class Manager:
        AddToDB = False

        def CreatePoint(self, x, y, z):
            assert self.AddToDB
            return (x, y, z)

    class Adapter:
        # Deliberately no extrusion, cut, line or circle operation: the
        # reference must not touch the physical solid or add a printed wire.
        currentSketchManager = Manager()

        def __init__(self):
            self.points = {}
            self.dimensions = []
            self.named = {}
            self.globals = {
                "BottomLength": part.BOTTOM_LENGTH,
                "TopLength": part.TOP_LENGTH,
                "BottomThickness": part.BOTTOM_THICKNESS,
                "TopThickness": part.TOP_THICKNESS,
                "DeckRise": part.DECK_RISE,
                "ColumnX": part.COLUMN_X,
                "BaseScrewY": part.BASE_SCREW_Y,
            }
            self.currentModel = SimpleNamespace(Parameter=self.named.get)

        async def set_global_variable(self, request):
            assert request.expression.endswith("mm")
            self.globals[request.name] = float(request.expression[:-2])
            return result({"value": self.globals[request.name]})

        async def create_sketch(self, plane):
            assert plane == expected_plane
            return result()

        def _register_sketch_entity(self, kind, raw):
            assert kind == "Point"
            identity = f"Point{len(self.points)}"
            self.points[identity] = raw
            return identity

        async def add_sketch_dimension(self, first, second, kind, value):
            axis = {"horizontal_distance": 0, "vertical_distance": 1}[kind]
            start = self.points[first]
            end = (0.0, 0.0, 0.0) if second == "origin" else self.points[second]
            assert value == pytest.approx(abs(end[axis] - start[axis]) * 1000.0)
            dimension = SimpleNamespace(SystemValue=value / 1000.0, pair=(first, second))
            self.dimensions.append(dimension)
            return result(str(len(self.dimensions)))

        async def add_sketch_constraint(self, first, second, kind):
            assert kind == "horizontal_points"
            assert self.points[first][1] == 0.0
            assert second == "origin"
            return result()

        async def exit_sketch(self):
            return result()

        async def create_equation(self, request):
            full_name, expression = request.equation.split(" = ")
            operations = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Div: operator.truediv}

            def evaluate(node):
                if isinstance(node, ast.Constant):
                    return self.globals[node.value] if isinstance(node.value, str) else node.value
                if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
                    return -evaluate(node.operand)
                if isinstance(node, ast.BinOp):
                    return operations[type(node.op)](evaluate(node.left), evaluate(node.right))
                raise AssertionError(f"unsupported dimension expression: {ast.dump(node)}")

            value = evaluate(ast.parse(expression, mode="eval").body)
            assert self.named[full_name.strip('"')].SystemValue * 1000.0 == pytest.approx(value)
            return result()

    class RecordedDimensions(SketchDims):
        def apply(self, adapter, feature):
            assert len(self._rows) == len(adapter.dimensions)
            for (name, _drive), dimension in zip(self._rows, adapter.dimensions, strict=True):
                adapter.named[f"{name}@{feature}"] = dimension
            return [(f"{name}@{feature}", drive) for name, drive in self._rows]

    async def native_state_check(_adapter, *_args):
        return None

    monkeypatch.setattr(part, "SketchDims", RecordedDimensions)
    monkeypatch.setattr(part, "name_last_feature", lambda _adapter, _name: None)
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(part, "ensure_fully_defined", native_state_check)
    monkeypatch.setattr(part, "force_rebuild", native_state_check)
    adapter = Adapter()
    if reference == "pivot":
        asyncio.run(part._build_pivot_seat_reference(adapter))
        expected_points = [
            (x / 1000.0, -z / 1000.0, 0.0)
            for x, z in (part.PIVOT_NEAR_PEDESTAL_XZ, part.PIVOT_SCREW_XZ)
        ]
        expected = {
            name: (abs(value), ("Point0", "Point1"))
            for name, value in zip(
                fr_harmonic_base_spec.PIVOT_SEAT_DIMENSIONS,
                part.PIVOT_SEAT_OFFSETS_MM, strict=True,
            )
        }
        feature = "PivotSeatReference"
    else:
        asyncio.run(part._build_height_reference(adapter))
        expected_points = [
            (part.HEIGHT_REFERENCE_ORIGIN[0] / 1000.0, 0.0, 0.0),
            *((x / 1000.0, height / 1000.0, 0.0)
              for _name, x, height, _dx, _dy in part.HEIGHT_REFERENCE_STATIONS),
        ]
        expected = {
            name: (height, ("Point0", f"Point{index}"))
            for index, (name, _x, height, _dx, _dy)
            in enumerate(part.HEIGHT_REFERENCE_STATIONS, 1)
        }
        feature = "HeightReference"
    assert list(adapter.points.values()) == expected_points
    assert not adapter.currentSketchManager.AddToDB
    for name, (value, pair) in expected.items():
        dimension = adapter.named[f"{name}@{feature}"]
        assert dimension.SystemValue * 1000.0 == pytest.approx(value)
        assert dimension.pair == pair


def test_base_blanks_its_reference_sketches_through_the_shared_helper() -> None:
    # Main (restricted review of #858): one blanking helper in _sketch, traced
    # like every other per-operation helper, and no local copy in the base.
    import inspect

    import _sketch

    source = inspect.getsource(part)
    blank = "blank_reference_sketches(adapter, REFERENCE_SKETCHES)"
    assert "def _hide_reference_sketches" not in source
    assert source.count(blank) == 1
    assert set(part.REFERENCE_SKETCHES) == {
        "HeightReference", "CrossTapReference", "PlanReference", "PivotSeatReference"
    }
    assert hasattr(_sketch.blank_reference_sketches, "__wrapped__")


def test_section_rib_relief_names_both_ribs() -> None:
    # plate-r5 review: B-B cuts only the long rib, so the cross rib's level
    # was in no view. Both ribs' reliefs are driven by "RibRelief", so the
    # one printed height says it governs both.
    import inspect

    import draw_fr_harmonic_base as sheet

    assert sheet.UNDERSIDE_SECTION_CALLOUTS["RibRelief"] == "BOTH\nRIBS"
    # One loop builds both ribs: each relief is equated to "RibRelief".
    source = inspect.getsource(part)
    assert "(rib_dims[1], '\"RibRelief\"')" in source
    extrude = "extrude_at_offset(adapter, POCKET_CEILING_Y - RIB_RELIEF, RIB_RELIEF)"
    assert source.count(extrude) == 1


def test_pivot_source_model_fit_preserves_the_inherited_full_form_window() -> None:
    import dt_vn_cone_pivot_screw_spec as pivot

    material = part.THROUGH_SEAT_MATERIAL["PivotSeat"][0]
    capacity = sum(end - start for start, end in material.guaranteed_segments_mm)
    assert capacity >= 1.5 * part.THREAD_MAJOR_MM[pivot.THREAD]
    fit = part.THROUGH_SEAT_SOURCE_MODEL_FITS["PivotSeat"][0]
    assert pivot.FULL_THREAD_START == pytest.approx(2.3368)
    expected = pivot.THREAD_TAIL_LEN - pivot.TIP_CHAMFER - pivot.FULL_THREAD_START
    assert fit.full_thread_engagement_min_mm == pytest.approx(expected)
    assert fit.full_thread_engagement_min_mm == pytest.approx(6.75386, abs=1e-5)
    assert pivot.MIN_USEFUL_ENGAGEMENT_MM == 4.83
    assert pivot.MIN_USEFUL_ENGAGEMENT_MM < expected < 1.5 * part.THREAD_MAJOR_MM[pivot.THREAD]
    assert fit.protrusion_max_mm == 0.0
    assert fit.clearance_min_mm > 0.0


def test_nameplate_frame_distinguishes_existing_external_projection_and_female_overlap() -> None:
    import build_fr_frame_assembly as frame
    import fr_nameplate_spec as plate

    assert plate.SCREW_FULL_THREAD_MIN == pytest.approx(3.73575)
    assert frame.NAMEPLATE_BASE_FULL_FORM_MIN == pytest.approx(3.48575)
    assert len(frame.NAMEPLATE_BASE_MATERIALS) == 4
    assert frame.NAMEPLATE_SCREW_MAX_INSERTION == pytest.approx(4.98)
    assert frame.NAMEPLATE_TIP_CLEARANCE_MIN > 0.0
    for material in frame.NAMEPLATE_BASE_MATERIALS:
        start, end = material.guaranteed_segments_mm[0]
        assert start == pytest.approx(0.25)
        assert end > frame.NAMEPLATE_SCREW_MAX_INSERTION


def test_retained_volume_refuses_overlaps_and_subtracts_earlier_rib_metal() -> None:
    disc = ("disc", 0.0, 50.0, 8.0)
    bottom = fr_harmonic_base_spec.CROSS_TAP_LUG_BOTTOM_Y
    with pytest.raises(AssertionError, match="overlap"):
        part.hanging_volume((disc, ("disc", 10.0, 50.0, 8.0)), (), bottom)
    on_rib = ("disc", 100.0, 0.0, 8.0)
    alone = part.hanging_volume((on_rib,), (), bottom)
    shared = part.hanging_volume((on_rib,), (part.LONG_RIB_SHAPE,), bottom)
    assert alone == pytest.approx(math.pi * 64.0 * (part.POCKET_CEILING_Y - bottom), rel=1e-6)
    chord = 2.0 * (5.0 * math.sqrt(64.0 - 25.0) + 64.0 * math.asin(5.0 / 8.0))
    assert alone - shared == pytest.approx(chord * (part.POCKET_CEILING_Y - bottom), rel=1e-6)


def test_through_cut_volume_integrates_skin_full_rib_and_half_rib_without_drill_point() -> None:
    seat = part.FOOT_SEAT_SPEC
    area = math.pi * (part.FOOT_SCREW_HOLE_DIA / 2.0) ** 2
    skin = part.STACK_HEIGHT - part.POCKET_CEILING_Y
    rib = part.STACK_HEIGHT - part.RIB_RELIEF
    for xz, depth in (((100.0, 50.0), skin), ((100.0, 0.0), rib), ((100.0, 5.0), (skin + rib) / 2.0)):
        assert part._through_holes_volume_mm3(seat, (xz,)) == pytest.approx(area * depth, rel=2e-4)
    combined = part._through_holes_volume_mm3(seat, ((100.0, 50.0), (100.0, 5.0)))
    assert combined == pytest.approx(area * (skin + (skin + rib) / 2.0), rel=2e-4)


def test_pedestal_thread_interference_budget_stops_at_actual_retained_skin() -> None:
    import _interference_contracts as contracts

    assert part.PEDESTAL_SCREW_ENGAGEMENT == pytest.approx(14.05)
    for xz in part.PEDESTAL_SCREW_XZ:
        assert fr_harmonic_base_fasteners.retained_material_segments_mm(*xz)[0] == pytest.approx((0.0, 13.0))
    allowed = contracts.allowed_interference_pairs("ha-harmonic-analyzer")
    expected = 1.10 * math.pi / 4.0 * (4.1656**2 - 3.454**2) * 13.0
    obsolete = 1.10 * math.pi / 4.0 * (4.1656**2 - 3.454**2) * 14.05
    for number in (1, 2):
        pair = frozenset((
            f"dt-drive-train-1/dt-vn-pedestal-hold-down-screw-{number}",
            "fr-frame-1/fr-harmonic-base-1",
        ))
        assert allowed[pair] == pytest.approx(expected)
        assert allowed[pair] < obsolete


def _native_ray_hit(ray: int, depth: float, flags: float, *, x=100.0, z=50.0):
    """Documented six-field hit record; dimensions are SI in native arrays."""
    return (0.0, float(ray), flags, x / 1000.0, (50.8 - depth) / 1000.0, z / 1000.0)


def _native_ray_adapter(monkeypatch, raw, *, count=None, bodies=None):
    from types import SimpleNamespace
    from solidworks_mcp.adapters import com_variant

    body_list = (object(),) if bodies is None else bodies
    calls = []

    def intersect(*args):
        calls.append(args)
        return len(raw) // 6 if count is None else count

    model = SimpleNamespace(
        Extension=SimpleNamespace(RayIntersections=intersect),
        GetBodies2=lambda *_args: body_list,
        GetRayIntersectionsPoints=lambda: raw,
    )
    monkeypatch.setattr(part, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(com_variant, "dispatch_array", lambda values: values)
    monkeypatch.setattr(com_variant, "double_array", lambda values: values)
    return SimpleNamespace(currentModel=model), calls


@pytest.mark.parametrize(("enter", "exit"), ((16, 32), (17, 33)))
def test_native_rays_sort_entries_and_keep_each_nonuniform_interval(monkeypatch, enter, exit) -> None:
    raw = (
        *_native_ray_hit(1, 47.8, exit, x=100.0, z=0.0),
        *_native_ray_hit(0, 13.0, exit),
        *_native_ray_hit(1, 0.0, enter, x=100.0, z=0.0),
        *_native_ray_hit(0, 0.0, enter),
    )
    adapter, calls = _native_ray_adapter(monkeypatch, raw)
    result = part._native_vertical_segments(adapter, ((100.0, 50.0), (100.0, 0.0)), "rays")
    assert len(result) == 2
    assert result[0][0] == pytest.approx((0.0, 13.0))
    assert result[1][0] == pytest.approx((0.0, 47.8))
    assert calls[0][1] == pytest.approx((0.100, 0.0558, 0.050, 0.100, 0.0558, 0.0))
    assert calls[0][2] == [0.0, -1.0, 0.0, 0.0, -1.0, 0.0]


@pytest.mark.parametrize(
    ("raw", "count", "message"),
    (
        ((0.0,), 1, "malformed"),
        ((), -1, "malformed"),
        ((), 0.5, "nonintegral"),
        (_native_ray_hit(0, math.nan, 16), 1, "non-finite"),
        ((1.0, 0.0, 16.0, 0.100, 0.0508, 0.050), 1, "index"),
        ((0.0, 0.5, 16.0, 0.100, 0.0508, 0.050), 1, "index"),
        (_native_ray_hit(0, 0.0, 16, x=101.0), 1, "off its requested axis"),
        (_native_ray_hit(0, 0.0, 16 | 2), 1, "grazing"),
        (_native_ray_hit(0, 0.0, 16.5), 1, "grazing"),
        (_native_ray_hit(0, 0.0, 16 | 64), 1, "grazing"),
        (_native_ray_hit(0, 0.0, 16 | 32), 1, "grazing"),
        (_native_ray_hit(0, 0.0, 16), 1, "unpaired"),
        ((*_native_ray_hit(0, 0.0, 32), *_native_ray_hit(0, 13.0, 16)), 2, "unpaired"),
        ((*_native_ray_hit(0, 0.0, 16), *_native_ray_hit(0, 0.0, 32)), 2, "empty/reversed"),
    ),
)
def test_native_rays_refuse_malformed_or_ambiguous_boundaries(monkeypatch, raw, count, message) -> None:
    adapter, _calls = _native_ray_adapter(monkeypatch, raw, count=count)
    with pytest.raises(RuntimeError, match=message):
        part._native_vertical_segments(adapter, ((100.0, 50.0),), "bad ray")


@pytest.mark.parametrize("bodies", ((), (object(), object()), "not a body array"))
def test_native_rays_refuse_missing_or_multiple_solids(monkeypatch, bodies) -> None:
    adapter, calls = _native_ray_adapter(monkeypatch, (), bodies=bodies)
    with pytest.raises(RuntimeError, match="one actual solid body"):
        part._native_vertical_segments(adapter, ((100.0, 50.0),), "body control")
    assert calls == []


@pytest.mark.parametrize("actual", ((), ((0.0, 12.0),), ((0.0, 13.0), (14.0, 15.0))))
def test_uncut_material_control_rejects_missing_short_or_extra_metal(monkeypatch, actual) -> None:
    monkeypatch.setattr(part, "_native_vertical_segments", lambda _a, points, _label: tuple(actual for _p in points))
    with pytest.raises(RuntimeError, match="actual material"):
        part._verify_uncut_material(
            object(), "FootScrewHoles", part.FOOT_SEAT_SPEC, part.FOOT_SCREW_XZ,
        )


def _breakthrough_adapter(monkeypatch, *, cylinder=None, closest=None, faces=True):
    from types import SimpleNamespace

    x, z = part.FOOT_SCREW_XZ[0]
    radius = part.FOOT_SCREW_HOLE_DIA / 2.0
    params = (x / 1000.0, 0.0, z / 1000.0, 0.0, 1.0, 0.0, radius / 1000.0)
    surface = SimpleNamespace(IsCylinder=lambda: True, CylinderParams=params if cylinder is None else cylinder)
    face = SimpleNamespace(
        GetSurface=lambda: surface,
        GetClosestPointOn=lambda *point: (*point, 0.0, 0.0) if closest is None else closest,
    )
    body = SimpleNamespace(GetFaces=lambda: (face,) if faces else ())
    model = SimpleNamespace(GetBodies2=lambda *_args: (body,))
    monkeypatch.setattr(part, "_early_bound", lambda obj, _interface: obj)
    return SimpleNamespace(currentModel=model)


def test_native_through_proof_requires_open_bore_and_real_wall_positive_controls(monkeypatch) -> None:
    adapter = _breakthrough_adapter(monkeypatch)
    seen = []

    def rays(_adapter, points, label):
        seen.append((label, len(points)))
        if label.endswith("breakthrough"):
            return tuple(() for _point in points)
        return tuple(((0.0, 13.0),) for _point in points)

    monkeypatch.setattr(part, "_native_vertical_segments", rays)
    part._verify_through_breakthrough(adapter, "FootScrewHoles", part.FOOT_SEAT_SPEC, part.FOOT_SCREW_XZ)
    assert seen == [("FootScrewHoles breakthrough", 16), ("FootScrewHoles wall control", 16)]
    monkeypatch.setattr(part, "_native_vertical_segments", lambda _a, points, _label: tuple(() for _point in points))
    with pytest.raises(RuntimeError, match="actual material"):
        part._verify_through_breakthrough(adapter, "FootScrewHoles", part.FOOT_SEAT_SPEC, part.FOOT_SCREW_XZ)


def test_native_through_proof_refuses_even_an_off_axis_closed_floor(monkeypatch) -> None:
    adapter = _breakthrough_adapter(monkeypatch)

    def floor(_adapter, points, _label):
        return (*(() for _point in points[:-1]), ((12.0, 13.0),))

    monkeypatch.setattr(part, "_native_vertical_segments", floor)
    with pytest.raises(RuntimeError, match="not through"):
        part._verify_through_breakthrough(adapter, "FootScrewHoles", part.FOOT_SEAT_SPEC, part.FOOT_SCREW_XZ)


@pytest.mark.parametrize("defect", ("missing", "radius", "axis", "short", "nonfinite", "closest"))
def test_native_through_proof_refuses_missing_or_bad_finite_cylinder(monkeypatch, defect) -> None:
    x, z = part.FOOT_SCREW_XZ[0]
    params = [x / 1000.0, 0.0, z / 1000.0, 0.0, 1.0, 0.0, part.FOOT_SCREW_HOLE_DIA / 2000.0]
    if defect == "radius":
        params[6] += 0.001
    elif defect == "axis":
        params[3:6] = [1.0, 0.0, 0.0]
    elif defect == "short":
        params.pop()
    elif defect == "nonfinite":
        params[0] = math.nan
    adapter = _breakthrough_adapter(
        monkeypatch, cylinder=params,
        closest=(0.0, 0.0, 0.0, 0.0, 0.0) if defect == "closest" else None,
        faces=defect != "missing",
    )
    monkeypatch.setattr(
        part, "_native_vertical_segments",
        lambda _a, points, label: tuple(() if label.endswith("breakthrough") else ((0.0, 13.0),) for _point in points),
    )
    with pytest.raises(RuntimeError, match="cylinder"):
        part._verify_through_breakthrough(adapter, "FootScrewHoles", part.FOOT_SEAT_SPEC, part.FOOT_SCREW_XZ)
