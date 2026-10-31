"""Offline contracts for the harmonic-base drawing."""

from __future__ import annotations

from dataclasses import replace
import math

import pytest

import _drawing_hole_callout
from _inch_wall_limits import WALL_TARGET_MM
import build_fr_harmonic_base as part
import cone_line
import dt_cone_pivot_post_installation
import dt_cone_swing_platform_geometry as platform
from dt_drive_train_steps import step_ref
import fr_harmonic_base_fasteners
import fr_harmonic_base_spec
from dt_vn_cone_lock_knob_spec import HEAD_DIA as KNOB_HEAD_DIA
from dt_swing_stop_screw_spec import CONTACT_DIA as STOP_CONTACT_DIA


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
    assert spec.POCKET_SKIN == 12.954  # .51
    assert spec.POCKET_CEILING_Y == pytest.approx(37.846)
    assert spec.STACK_HEIGHT - spec.POCKET_CEILING_Y == pytest.approx(spec.POCKET_SKIN)
    assert fasteners.DECK_HEIGHT_BAND_MM == pytest.approx(0.508)
    assert fasteners.POCKET_CEILING_BAND_MM == pytest.approx(0.254)
    assert fasteners.EDGE_BREAK_MAX_MM == pytest.approx(0.254)
    for tag, seat, stations, bounds in part.THROUGH_SEAT_GROUPS:
        materials = part.THROUGH_SEAT_MATERIAL[tag]
        assert len(materials) == len(stations)
        for xz, material in zip(stations, materials, strict=True):
            assert material == fasteners.through_seat_material(seat, xz, envelope_xz=bounds)
            assert material.station_xz == xz
            assert material.nominal_segments_mm == fasteners.retained_material_segments_mm(*xz)
            assert material.nominal_segments_mm == ((0.0, spec.POCKET_SKIN),), (tag, xz)
            assert material.exit_depth_max_mm == pytest.approx(13.716), (tag, xz)
            capacity = sum(end - start for start, end in material.guaranteed_segments_mm)
            assert capacity >= 1.5 * part.THREAD_MAJOR_MM[seat.size]
            assert material.exit_depth_min_mm >= 12.954 - 3.0 * 0.254 - 1e-9
            assert material.guaranteed_segments_mm[0][0] == pytest.approx(0.254)
    support = part.THROUGH_SEAT_MATERIAL["SupportHoldDownSeats"][0]
    assert support.nominal_segments_mm == ((0.0, 12.954),)
    assert sum(end - start for start, end in support.guaranteed_segments_mm) == pytest.approx(11.684)
    # The .51 skin keeps the unchanged 1.5D female-capacity floor at its loose limits.
    assert 12.954 - 3.0 * 0.254 - 2.0 * 0.254 > 1.5 * 6.35


def test_material_queries_distinguish_skin_ribs_walls_fillets_and_transfer_bounds() -> None:
    fasteners = fr_harmonic_base_fasteners
    spec = fr_harmonic_base_spec
    assert fasteners.retained_material_segments_mm(100.0, 50.0) == ((0.0, 12.954),)
    assert fasteners.retained_material_segments_mm(100.0, 0.0) == (
        (0.0, spec.STACK_HEIGHT - spec.RIB_RELIEF),
    )
    assert fasteners.retained_material_segments_mm(100.0, spec.POCKET_HALF_Z + 1.0) == (
        (0.0, spec.STACK_HEIGHT),
    )
    left_face = spec.CROSS_RIB_CENTER_X - spec.RIB_THICKNESS / 2.0
    beside_junction = (left_face - 1.0, spec.RIB_THICKNESS / 2.0 + 1.0)
    assert fasteners.retained_material_segments_mm(
        *beside_junction, fillet_radius_mm=0.0,
    ) == ((0.0, spec.POCKET_SKIN),)
    assert fasteners.retained_material_segments_mm(*beside_junction)[0][1] > spec.POCKET_SKIN
    assert fasteners.retained_material_segments_mm(0.0, 50.0) == ((0.0, spec.POCKET_SKIN),)
    assert fasteners.retained_material_segments_mm(spec.CROSS_RIB_CENTER_X, 50.0) == (
        (0.0, spec.STACK_HEIGHT - spec.RIB_RELIEF),
    )
    for xz in part.PEDESTAL_SCREW_XZ:
        material = fasteners.through_seat_material(
            part.PEDESTAL_SEAT_SPEC, xz, envelope_xz=part.PEDESTAL_TRANSFER_XZ,
        )
        assert material.envelope_xz == (2.0, 5.0)
        assert len(material.guaranteed_segments_mm) == 1
        assert material.guaranteed_segments_mm[0] == pytest.approx((0.254, 11.938))
    # A thread straddling a rib edge cannot credit the axis's entire rib.
    straddling = fasteners.through_seat_material(part.STOP_SEAT_SPEC, (100.0, 4.9))
    assert straddling.nominal_segments_mm[0][1] > 12.954
    assert straddling.guaranteed_segments_mm[0][1] == pytest.approx(11.938)


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
    late_start = fasteners.EDGE_BREAK_MAX_MM + 0.001
    for delta, tip, start in ((-0.001, 0.0, 0.0), (0.0, 0.001, 0.0), (0.0, 0.0, late_start)):
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
    import sh_vn_fillister_screw_90280a108_spec as foot
    import dt_swing_stop_screw_spec as stop

    material = part.THROUGH_SEAT_MATERIAL["StopSeat"][0]
    fr_harmonic_base_fasteners.require_stop_seat_fit(
        part.STOP_SEAT_SPEC, platform.PLATE_T, material=material
    )
    assert (stop.THREAD, stop.SHANK_LEN) == (foot.THREAD, foot.SHANK_LEN)
    assert stop.PROUD_LEN == 0.0
    assert stop.CONTACT_DIA == stop.HEAD_DIA
    assert stop.HEAD_H <= platform.PLATE_T - 0.508
    # A short full-thread receiver still fails even if the tip has free air.
    thin = replace(material, guaranteed_segments_mm=((0.25, 4.0),))
    with pytest.raises(AssertionError, match="full-form overlap"):
        fr_harmonic_base_fasteners.require_stop_seat_fit(
            part.STOP_SEAT_SPEC, platform.PLATE_T, material=thin
        )


def test_nameplate_seats_are_derived_from_the_plate_mount() -> None:
    """The four #4-40 taps sit under the plate's corner holes carried through
    its mount transform (nameplate_spec), cut from the deck the plate lies on."""
    import fr_nameplate_spec
    from sh_vn_brass_fillister_screw_spec import HEAD_DIA, SHANK_DIA, SHANK_LEN, THREAD
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
    # The plate's west edge sits .160 inside the deck's west edge (user ruling
    # 2026-10-09), the binding side of its footprint.
    assert part.NAMEPLATE_DECK_CLEARANCE == pytest.approx(
        fr_harmonic_base_spec.DECK_HALF_X - fr_nameplate_spec.MOUNT_POS[0]
    )
    assert part.NAMEPLATE_DECK_CLEARANCE == pytest.approx(4.064)
    # RV-03 already accepts the purchased screw's limited useful full form.
    # Through-tapping preserves that hardware and ruling, not a new 1.5D claim.
    engagement = SHANK_LEN - fr_nameplate_spec.PLATE_THICKNESS
    assert engagement == pytest.approx(0.250 * 25.4 - 1.6002)
    material = part.THROUGH_SEAT_MATERIAL["NameplateSeats"][0]
    from _printed_tolerance import printed_deviations

    plate_band = printed_deviations(
        fr_nameplate_spec.PLATE_THICKNESS, fr_nameplate_spec.PLATE_THICKNESS_PRECISION,
        unit=fr_nameplate_spec.UNIT,
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
    assert not {hole[:2] for hole in (*pedestal_seats, sheet.TRANSFER_SPRING_HOLE)} & set(
        sheet.HOLE_TAG_STATION_POSITIONS
    )


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
    # The reason's numbers, from literals: #4 close hole .120 over the #4-40
    # basic major .112; the plate's .XX stations (+-.010) and this .XXX tap
    # station (+-.005).
    float_diametral = 0.120 - 0.112
    demand = 2.0 * math.sqrt(2.0) * (0.010 + 0.005)
    assert f"{float_diametral:.3f}"[1:] == ".008"
    assert f"{demand:.3f}"[1:] == ".042"
    assert ".008 diametral" in fit_up.reason and "about .042" in fit_up.reason


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
    # (0.0, +.020), so the printed limits cannot move.
    import ast
    from pathlib import Path

    from _fit_deviations import deviations

    assert fr_harmonic_base_spec.SPOTFACE_DEPTH_BAND_MM == (0.508, 0.0)
    assert deviations(fr_harmonic_base_spec.SPOTFACE_DEPTH_BAND_MM) == (0.0, 0.508)
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


# Native R5 at af0b5d14744d, artifact 150 (2026-10-20T22:30:25Z), sheet metres.
# Keep every display segment, including each tip stub and horizontal shoulder,
# and every logged obstacle. This is the observed failure, not an after-fix dump.
NATIVE_R5_CALLOUTS = {
    "MHA-DT-18 block transfer": (
        [0.272, 0.252],
        [
            (0.27915094466515766, 0.2166936360781131, 0.3047520828187466, 0.24086076360940933),
            (0.2785229525512869, 0.21610082003167358, 0.27915094466515766, 0.2166936360781131),
            (0.3047520828187466, 0.24086076360940933, 0.24083541718125345, 0.24086076360940933),
        ],
        [
            ("4X ", [0.25012050208449366, 0.2575829862249084, -0.00635], 0.0035),
            ("<MOD-DIAM>", [0.2568434189334512, 0.25752951404824853, -0.00635], 0.0035),
            (" 3.45 THRU ALL", [0.2621218563318253, 0.2575829862249084, -0.00635], 0.0035),
            ("TRANSFER FROM MHA-DT-18", [0.24083541718125345, 0.25197326388256625, -0.00635], 0.0035),
            ("AFTER MHA-DT-00 STEP 19;", [0.24319062393903734, 0.24641701389150694, -0.00635], 0.0035),
            (" 8-32 UNC - 2B THRU ALL", [0.245494790494442, 0.24086076390044764, -0.00635], 0.0035),
        ],
    ),
    "MHA-DT-02 pedestal transfer": (
        [0.2, 0.252],
        [
            (0.26455096384012916, 0.21800673182009217, 0.23275208281874657, 0.24086076360940933),
            (0.2652522350924292, 0.21750272428969447, 0.26455096384012916, 0.21800673182009217),
            (0.23275208281874657, 0.24086076360940933, 0.16883541718125344, 0.24086076360940933),
        ],
        [
            ("2X ", [0.17812050208449365, 0.2575829862249084, -0.00635], 0.0035),
            ("<MOD-DIAM>", [0.1848434189334512, 0.25752951404824853, -0.00635], 0.0035),
            (" 3.45 THRU ALL", [0.19012185633182527, 0.2575829862249084, -0.00635], 0.0035),
            ("TRANSFER FROM MHA-DT-02", [0.16883541718125344, 0.25197326388256625, -0.00635], 0.0035),
            ("AT ASSEMBLY;", [0.1847458340227604, 0.24641701389150694, -0.00635], 0.0035),
            (" 8-32 UNC - 2B THRU ALL", [0.173494790494442, 0.24086076390044764, -0.00635], 0.0035),
        ],
    ),
    "MHA-DT-24 spring transfer": (
        [0.315, 0.1428],
        [
            (0.27177741922575815, 0.17562234220792322, 0.2822479171812534, 0.13166076360940931),
            (0.2716464779906864, 0.17617211390186344, 0.27177741922575815, 0.17562234220792322),
            (0.2822479171812534, 0.13166076360940931, 0.3461645828187465, 0.13166076360940931),
        ],
        [
            ("<MOD-DIAM>", [0.29648196190595627, 0.14832951404824854, -0.00635], 0.0035),
            (" 2.26 THRU ALL", [0.30176039930433035, 0.1483829862249084, -0.00635], 0.0035),
            ("TRANSFER FROM MHA-DT-24", [0.28383541718125344, 0.14277326388256625, -0.00635], 0.0035),
            ("AFTER MHA-DT-00 STEP 19;", [0.2861906239390373, 0.13721701389150695, -0.00635], 0.0035),
            (" 4-40 UNC - 2B THRU ALL", [0.288494790494442, 0.13166076390044765, -0.00635], 0.0035),
        ],
    ),
    "MHA-FR-04 nameplate transfer": (
        [0.362, 0.255],
        [
            (0.3197042937236577, 0.20674424134689828, 0.3186531282424926, 0.246638888604939),
            (0.3197191794315407, 0.2061792874211656, 0.3197042937236577, 0.20674424134689828),
            (0.3186531282424926, 0.246638888604939, 0.4037593717575072, 0.246638888604939),
        ],
        [
            ("4X ", [0.3401205020844935, 0.25780486122937873, -0.00635], 0.0035),
            ("<MOD-DIAM>", [0.34684341893345105, 0.2577513890527189, -0.00635], 0.0035),
            (" 2.26 THRU ALL", [0.35212185633182513, 0.25780486122937873, -0.00635], 0.0035),
            ("TRANSFER FROM MHA-FR-04", [0.3310177086740731, 0.2521951388870366, -0.00635], 0.0035),
            ("AT ASSEMBLY; 4-40 UNC - 2B THRU ALL", [0.32024062824249255, 0.2466388888959773, -0.00635], 0.0035),
        ],
    ),
    "MHA-FR-VN-53 cross-tap": (
        [0.285, 0.117],
        [
            (0.32936898242057217, 0.09866560316368712, 0.33178124668598175, 0.10861215219646692),
            (0.3291310175794279, 0.0976843968363129, 0.32936898242057217, 0.09866560316368712),
            (0.33178124668598175, 0.10861215219646692, 0.23980625331401823, 0.10861215219646692),
        ],
        [
            ("4X ", [0.26240421816706655, 0.11983159763785078, 0.0], 0.0035),
            ("<MOD-DIAM>", [0.2691271350160241, 0.11977812546119093, 0.0], 0.0035),
            (" 4.04 ", [0.27440557241439817, 0.11983159763785078, 0.0], 0.0035),
            ("<HOLE-DEPTH>", [0.28604307197034357, 0.11977812546119093, 0.0], 0.0035),
            (" 49 MIN", [0.2910436967760324, 0.11983159763785078, 0.0], 0.0035),
            ("COMMON THREAD LEAD IN BOTH WALLS", [0.23980625331401823, 0.11422187529550865, 0.0], 0.0035),
            (" 10-32 UNF - 2B ", [0.25906183928251264, 0.10866562530444934, 0.0], 0.0035),
            ("<HOLE-DEPTH>", [0.2930069787800312, 0.10861215312778949, 0.0], 0.0035),
            (" 46.00", [0.29800760358572004, 0.10866562530444934, 0.0], 0.0035),
        ],
    ),
}
NATIVE_R5_CALLOUT_BOXES = {
    "MHA-DT-18 block transfer": (0.24083541718125345, 0.24086076360940933, 0.3047520828187466, 0.2610829862249084),
    "MHA-DT-02 pedestal transfer": (0.16883541718125344, 0.24086076360940933, 0.23275208281874657, 0.2610829862249084),
    "MHA-DT-24 spring transfer": (0.2822479171812534, 0.13166076360940931, 0.3461645828187465, 0.1518829862249084),
    "MHA-FR-04 nameplate transfer": (0.3186531282424926, 0.246638888604939, 0.4037593717575072, 0.26130486122937874),
    "MHA-FR-VN-53 cross-tap": (0.23980625331401823, 0.10861215219646692, 0.33178124668598175, 0.12333159763785079),
}
NATIVE_R5_OBSTACLES = {
    "frame left": (0.0, 0.0, 0.0127, 0.2794),
    "frame right": (0.41910000000000003, 0.0, 0.4318, 0.2794),
    "frame bottom": (0.0, 0.0, 0.4318, 0.0127),
    "frame top": (0.0, 0.2667, 0.4318, 0.2794),
    "title block": (0.216, 0.0, 0.4318, 0.066),
    "view holes top": (0.22285000000000002, 0.1591, 0.33715, 0.23090000000000005),
    "view holes front": (0.22285000000000002, 0.08865, 0.33715, 0.10135000000000001),
    "view section A-A": (0.3690249999999998, 0.0991, 0.3817250000000005, 0.17090000000000005),
    "origin X axis": (0.21935000000000002, 0.142105, 0.24240100000000003, 0.14910500000000002),
    "origin Y axis": (0.205855, 0.15560000000000002, 0.21285500000000002, 0.17865100000000003),
    "section A arrow 1": (0.32725000000000004, 0.153, 0.34325000000000006, 0.157),
    "section A arrow 2": (0.32725000000000004, 0.233, 0.34325000000000006, 0.23700000000000002),
    "label section A 1": (0.3431562742474917, 0.15365396989966557, 0.3495062742474917, 0.16000396989966556),
    "label section A 2": (0.3431562742474917, 0.23365396989966558, 0.3495062742474917, 0.24000396989966558),
    "note DetailItem244 'LOW-CARBON STEEL OR GRAY IRON'": (0.2178062742474916, 0.0267532508361204, 0.2711819531772575, 0.030089230769230757),
    "note DetailItem245 'fr-harmonic-base'": (0.3102605752508361, 0.03771432775919731, 0.353151745819398, 0.042956581939799315),
    "note DetailItem246 'v44'": (0.37316762541806026, 0.022464133779264206, 0.3836521337792642, 0.028659525083612025),
    "label DetailItem247 'DO NOT SCALE DRAWING\\r\\nBUILD '": (0.23257989966555181, 0.013885899665551815, 0.258314602006689, 0.01817501672240801),
    "note DetailItem248 'MHA-FR-01'": (0.3102605752508361, 0.022940702341137098, 0.3421906688963211, 0.029136093645484917),
    "note DetailItem260 'UNLESS OTHERWISE SPECIFIED, TOLERANCES'": (0.2178062742474916, 0.0615427558528428, 0.2654631304347826, 0.06440216722408026),
    "label DetailItem261 'SCALE: 1:5'": (0.39699605351170575, 0.03056579933110365, 0.41319938461538464, 0.03390177926421403),
    "note DetailItem263 'REV'": (0.37316762541806026, 0.03151893645484949, 0.379363016722408, 0.03485491638795987),
    "note DetailItem264 'DWG.  NO.'": (0.3102605752508361, 0.03056579933110365, 0.3278936120401338, 0.03390177926421403),
    "note DetailItem267 'PART'": (0.3102605752508361, 0.043909719063545155, 0.31788567224080266, 0.04724569899665551),
    "note DetailItem277 'ALKYD PRIME/ENAMEL: RAL6000 BODY; BLACK DECK/UNDERSIDE; MASK+OIL BORES/THREADS/ID'": (0.2178062742474916, 0.03485491638795987, 0.28976812709030103, 0.04105030769230769),
    "note DetailItem278 'FINISH'": (0.2178062742474916, 0.0420034448160535, 0.22304852842809364, 0.04438628762541805),
    "note DetailItem279 'MATERIAL'": (0.2178062742474916, 0.03056579933110365, 0.22733764548494984, 0.03342521070234114),
    "note DetailItem280 'DRAWN PER ASME Y14.100\\r\\nDIMENSIONING AND TOLERANCING PER ASME Y14.5-2018'": (0.21828284280936455, 0.020081290969899634, 0.27261165886287625, 0.02532354515050167),
    "note DetailItem312 'SHEET 2 OF 4'": (0.39508977926421407, 0.014839036789297655, 0.4151056588628763, 0.01817501672240801),
    "note DetailItem314 '.XXX\\r\\n±0.13'": (0.24449411371237456, 0.05391765886287625, 0.2502129364548495, 0.05963648160535118),
    "note DetailItem315 '.XX\\r\\n±0.51'": (0.23210333110367892, 0.05391765886287625, 0.23782215384615385, 0.05963648160535118),
    "note DetailItem316 '<GGTOL-ANGULAR>\\r\\n±1°'": (0.2754710702341137, 0.05391765886287625, 0.2802367558528428, 0.05963648160535118),
    "note DetailItem319 'REMOVE BURRS AND BREAK SHARP EDGES R0.25 OR CHAMFER 0.25 MAX\\r\\nTHREADS UNC/UNF CLASS 2A/2B'": (0.2173297056856187, 0.04581599331103678, 0.2888149899665552, 0.049628541806020054),
    "note DetailItem320 '© 2026 Pedro Paulo Vezza Campos'": (0.3102605752508361, 0.014839036789297655, 0.36315968561872913, 0.01817501672240801),
    'note DetailItem321 "Albert Michelson\'s Harmonic Analyzer\\r\\nA Project For Hobby Machinists\\r\\nharmonic-analyzer.vza.net"': (0.32026851505016724, 0.04819883612040132, 0.4074805618729097, 0.06440216722408026),
    "note DetailItem323 'CAST/MACHINED'": (0.28547901003344484, 0.057730207357859525, 0.3059714581939799, 0.06011305016722407),
    "note DetailItem326 'A'": (0.0028738528428093046, 0.03056579933110365, 0.009069244147157124, 0.03819089632107023),
    "note DetailItem327 'A'": (0.42225418729097, 0.03056579933110365, 0.42844957859531774, 0.03819089632107023),
    "note DetailItem328 'B'": (0.0038269899665551166, 0.1001448093645485, 0.008592675585284204, 0.10824647491638797),
    "note DetailItem329 'B'": (0.4227307558528428, 0.1001448093645485, 0.42749644147157195, 0.10824647491638797),
    "note DetailItem330 'C'": (0.0028738528428093046, 0.17020038795986625, 0.009545812709030044, 0.1778254849498328),
    "note DetailItem331 'C'": (0.421777618729097, 0.17020038795986625, 0.42844957859531774, 0.1778254849498328),
    "note DetailItem332 'D'": (0.0028738528428093046, 0.23977939799331108, 0.009069244147157124, 0.24788106354515055),
    "note DetailItem333 'D'": (0.42225418729097, 0.23977939799331108, 0.42844957859531774, 0.24788106354515055),
    "note DetailItem334 '4'": (0.0514838461538461, 0.0019716856187290688, 0.0557729632107023, 0.00959678260869562),
    "note DetailItem335 '4'": (0.0514838461538461, 0.2683735117056857, 0.0557729632107023, 0.27647517725752513),
    "note DetailItem336 '3'": (0.1596649096989966, 0.0019716856187290688, 0.1639540267558528, 0.00959678260869562),
    "note DetailItem337 '3'": (0.1596649096989966, 0.2683735117056857, 0.1639540267558528, 0.27647517725752513),
    "note DetailItem338 '2'": (0.26736940468227427, 0.0019716856187290688, 0.27165852173913047, 0.00959678260869562),
    "note DetailItem339 '2'": (0.26736940468227427, 0.2683735117056857, 0.27165852173913047, 0.27647517725752513),
    "note DetailItem340 '1'": (0.37555046822742477, 0.0019716856187290688, 0.37983958528428097, 0.00959678260869562),
    "note DetailItem341 '1'": (0.37555046822742477, 0.2683735117056857, 0.37983958528428097, 0.27647517725752513),
    "note DetailItem342 'DRILLED HOLES\\r\\n+0.10 / 0'": (0.2554551906354515, 0.05391765886287625, 0.27213509030100336, 0.05963648160535118),
    "note DetailItem345 '.X\\r\\n±0.8'": (0.22018911705685618, 0.05391765886287625, 0.22495480267558526, 0.05963648160535118),
    "note DetailItem346 'UNIT: mm'": (0.39794919063545153, 0.021987565217391314, 0.4127228160535118, 0.02532354515050167),
    "note DetailItem446 'A1'": (0.23400960535117055, 0.16638783946488298, 0.24020499665551837, 0.17067695652173914),
    "note DetailItem447 'A2'": (0.23400960535117055, 0.22214636120401343, 0.24020499665551837, 0.22691204682274252),
    "note DetailItem455 'A3'": (0.3317061605351171, 0.16543470234113716, 0.34981576588628766, 0.17639577926421407),
    "note DetailItem456 'A4'": (0.3317061605351171, 0.21070871571906358, 0.34981576588628766, 0.2211932240802676),
    "note DetailItem448 'B1'": (0.2449706822742475, 0.19212254180602012, 0.2521192107023411, 0.2164275384615385),
    "note DetailItem449 'C1'": (0.2559317591973244, 0.2207166555183947, 0.2626037190635451, 0.22500577257525087),
    "note DetailItem451 'C2'": (0.2940572441471572, 0.17973175919732443, 0.3031120468227425, 0.18973969899665555),
    "note DetailItem452 'C3'": (0.2888149899665552, 0.2016539130434783, 0.2954869498327759, 0.20975557859531777),
    "note DetailItem453 'C4'": (0.30263547826086956, 0.16877068227424752, 0.3183622408026756, 0.17973175919732443),
    "note DetailItem454 'C5'": (0.30263547826086956, 0.20975557859531777, 0.3183622408026756, 0.21404469565217393),
    "note DetailItem450 'D1'": (0.2454472508361204, 0.15066107692307695, 0.258314602006689, 0.16877068227424752),
    "note DetailItem458 '1. D1 IS LOCATED TO THE MHA-DT-02 SEAT;\\r\\nDRILL AND TAP AT ASSEMBLY IN ONE SETUP.\\r\\nD1 TABLE X/Y ARE REFERENCE.'": (0.01955375250836114, 0.08680088963210703, 0.11534403344481603, 0.1001448093645485),
    "note DetailItem459 '4X: FIT TO ASSIGNED\\r\\nMHA-FR-03 TUBE:\\r\\nCLOSE HAND-SLIP, NO\\r\\nPERCEPTIBLE ROCK.\\r\\nTABLE <MOD-DIAM> REF.\\r\\nRETAIN MATCH MARKS.'": (0.16871971237458194, 0.19927107023411375, 0.22829078260869562, 0.2264354782608696),
    "label DetailItem465 'TOP VIEW SCALE 1:4'": (0.16967284949832773, 0.23263086956521745, 0.21447029431438125, 0.23739655518394653),
    "label DetailItem466 'FRONT CROSS-TAP VIEW SCALE 1:4'": (0.2449706822742475, 0.06869128428093646, 0.32169822073578597, 0.07345696989966555),
    "note DetailItem467 'ORIGIN: FLANGE\\r\\nOUTER SHARP\\r\\nCORNER (X0 Y0)'": (0.16490716387959864, 0.1725832307692308, 0.20160294314381272, 0.1864037190635452),
    "table DetailItem457": (0.018, 0.16737522039776861, 0.16276338643434313, 0.26),
}

# Native R6 at d17443bdb526, artifact 157:98, 105-115 (2026-10-20).
# All five callouts and every other obstacle are identical to R5. Only the
# lock tag's full GetBox changed; keep the observed stop attachment extent.
NATIVE_R6_OBSTACLES = {
    **NATIVE_R5_OBSTACLES,
    "note DetailItem449 'C1'": (
        0.24211127090301005, 0.21881038127090305,
        0.2540254849498328, 0.22309949832775924,
    ),
}
NATIVE_R6_STOP_TAG_XY = (0.247, 0.216)
# PDF ink, NOT the leader-inclusive GetBox above. The audit log rounds each
# edge to 0.1 mm; replay with half a quantum outward on every edge.
NATIVE_R6_TAG_INK = {
    "note DetailItem448 'B1'": (0.2474, 0.2125, 0.2512, 0.2159),
    "note DetailItem449 'C1'": (0.2428, 0.2194, 0.2478, 0.2230),
}
NATIVE_R6_INK_PAD_M = 0.00005
# The logged 5.40 mm pitch is rounded to 0.01 mm. This is its conservative
# upper bound, not a captured native font height or a different audit threshold.
NATIVE_R6_PITCH_UPPER_M = 0.005405


def _native_r5_r6_callout_layout():
    """Reconstruct all five unchanged callouts from their actual display data."""
    import draw_fr_harmonic_base as sheet

    anchors = {
        "MHA-DT-18 block transfer": sheet.BLOCK_CALLOUT_XY,
        "MHA-DT-02 pedestal transfer": sheet.PEDESTAL_CALLOUT_XY,
        "MHA-DT-24 spring transfer": sheet.SPRING_CALLOUT_XY,
        "MHA-FR-04 nameplate transfer": sheet.NAMEPLATE_CALLOUT_XY,
        "MHA-FR-VN-53 cross-tap": sheet.CROSS_TAP_CALLOUT_XY,
    }
    assert set(anchors) == set(NATIVE_R5_CALLOUTS) == set(NATIVE_R5_CALLOUT_BOXES)
    callouts, leaders, own_rows = {}, {}, {}
    for label, (anchor, lines, texts) in NATIVE_R5_CALLOUTS.items():
        assert tuple(anchor) == anchors[label]  # no callout moves to make this pass
        callouts[label] = sheet.callout_text_box(anchor, lines, texts, label)
        assert callouts[label] == pytest.approx(NATIVE_R5_CALLOUT_BOXES[label])
        leaders[label] = sheet.leader_segments(lines)
        own_rows[label] = sheet.callout_text_rows(lines, texts, label)
    return callouts, leaders, own_rows


def test_native_r5_r6_tag_layout_replays_all_callouts_with_attached_extents() -> None:
    """Observed R5/R6, then a conditional stop placement, not native after-fix proof."""
    import draw_fr_harmonic_base as sheet

    callouts, leaders, own_rows = _native_r5_r6_callout_layout()
    text_obstacles = {
        name: box for name, box in NATIVE_R5_OBSTACLES.items()
        if name.startswith(sheet._TEXT_OBSTACLE_KINDS)
    }
    foreign_texts = {f"callout {label}": box for label, box in callouts.items()}
    assert sheet.find_callout_clashes(callouts, NATIVE_R5_OBSTACLES) == []
    assert sheet.find_merged_blocks(callouts) == []
    assert sheet.find_tall_callouts(own_rows) == []
    lock_tag = "note DetailItem449 'C1'"  # captured native identity only
    assert sheet.find_leader_crossings(
        leaders, {**foreign_texts, **text_obstacles}, own_rows,
    ) == [
        f"leader of callout MHA-DT-02 pedestal transfer crosses {lock_tag}"
    ]

    # Do NOT translate the old whole GetBox: B1/D1's measured boxes include
    # their attached leaders. Move only the printed-text estimate, with the
    # full measured C1 width/height plus 0.5 mm on every side, while retaining
    # the physical lock rim. The proposed envelope also reserves a right-side
    # shoulder up to half that measured width (3.336 mm), at any text-row Y.
    # Its convex hull covers the tip/stub and a monotone straight/bent route
    # between that shoulder and ANY point on the original rim. Native rebuild
    # must prove the actual text and complete leader stay within this envelope;
    # no synthetic leader here is represented as an observed after-fix route.
    old = NATIVE_R5_OBSTACLES[lock_tag]
    width, height = old[2] - old[0], old[3] - old[1]
    x, y = sheet.HOLE_TAG_STATION_POSITIONS[sheet.LOCK_KNOB_XZ]
    assert (x, y) == (0.2425, 0.2230)
    text_box = (x - 0.0005, y - height - 0.0005, x + width + 0.0005, y + 0.0005)
    centre = sheet._plan_xy(*sheet.LOCK_KNOB_XZ, center=sheet.HOLE_TOP_CENTER)
    assert centre == pytest.approx((0.25439117028799675, 0.22292914718948796), abs=1e-12)
    # Native table's rounded-up 5.11 mm drill encloses the source drill.
    assert sheet.LOCK_SCREW_HOLE_DIA <= 5.11
    radius = 5.11 * sheet.VIEW_SCALE / 2000.0
    rim_box = (centre[0] - radius, centre[1] - radius, centre[0] + radius, centre[1] + radius)
    shoulder_box = (text_box[2], text_box[1], text_box[2] + width / 2.0, text_box[3])
    extent = (
        min(text_box[0], rim_box[0], shoulder_box[0]),
        min(text_box[1], rim_box[1], shoulder_box[1]),
        max(text_box[2], rim_box[2], shoulder_box[2]),
        max(text_box[3], rim_box[3], shoulder_box[3]),
    )
    assert extent == pytest.approx(
        (0.242, 0.21821088294314384, 0.25502992028799676, 0.22356789718948794),
        abs=1e-12,
    )
    # Guard the attached extent, not just the letter, against the neighbors.
    neighbors = {name: box for name, box in text_obstacles.items() if name != lock_tag}
    assert sheet.find_callout_clashes({"lock tag": extent}, neighbors) == []
    assert sheet.box_gap(extent, NATIVE_R5_OBSTACLES["note DetailItem447 'A2'"]) == pytest.approx(
        0.0017950033444816271,
    )
    assert sheet.box_gap(extent, NATIVE_R5_OBSTACLES["note DetailItem448 'B1'"]) == pytest.approx(
        0.0017833444816053312,
    )
    socket_fit = next(box for name, box in NATIVE_R5_OBSTACLES.items() if name.startswith("note DetailItem459 "))
    assert sheet.box_gap(extent, socket_fit) >= sheet.CALLOUT_CLEARANCE_M
    assert sheet.box_gap(
        extent, NATIVE_R5_OBSTACLES["label DetailItem465 'TOP VIEW SCALE 1:4'"],
    ) >= sheet.CALLOUT_CLEARANCE_M
    # Exact signed distance to the infinite pedestal diagonal; its NE corner
    # is the nearest corner of the whole west-side envelope. An infinite line
    # is conservative for the finite native segment, including its tip stub.
    x0, y0, x1, y1 = NATIVE_R5_CALLOUTS["MHA-DT-02 pedestal transfer"][1][0]
    dx, dy = x1 - x0, y1 - y0
    gap = (dy * (x0 - extent[2]) - dx * (y0 - extent[3])) / math.hypot(dx, dy)
    assert gap == pytest.approx(0.0010407506307039711, abs=1e-12)
    assert gap >= sheet.CALLOUT_CLEARANCE_M
    proposed = {**NATIVE_R5_OBSTACLES, lock_tag: extent}
    proposed_texts = {**text_obstacles, lock_tag: extent}
    assert sheet.find_callout_clashes(callouts, proposed) == []
    assert sheet.find_leader_crossings(
        leaders, {**foreign_texts, **proposed_texts}, own_rows,
    ) == []
    # Horizontal shoulders are retained too, even though the runtime's leader
    # predicate separates them from the sloped lines and tip stubs.
    assert sheet.find_leader_crossings(
        {label: lines for label, (_anchor, lines, _texts) in NATIVE_R5_CALLOUTS.items()},
        {lock_tag: extent},
    ) == []

    # R6 confirmed the lock placement without moving any callout. Reuse every
    # logged obstacle, replacing only the captured C1 GetBox, before proposing
    # the stop move. No R5 obstacle is silently discarded.
    r6_texts = {
        name: box for name, box in NATIVE_R6_OBSTACLES.items()
        if name.startswith(sheet._TEXT_OBSTACLE_KINDS)
    }
    assert set(NATIVE_R6_OBSTACLES) == set(NATIVE_R5_OBSTACLES)
    assert sheet.find_callout_clashes(callouts, NATIVE_R6_OBSTACLES) == []
    assert sheet.find_leader_crossings(
        leaders, {**foreign_texts, **r6_texts}, own_rows,
    ) == []

    stop_tag = "note DetailItem448 'B1'"  # captured identity, not a layout key
    new_anchor = sheet.HOLE_TAG_STATION_POSITIONS[sheet.STOP_SCREW_XZ]
    assert new_anchor == (0.247, 0.212)
    dy = new_anchor[1] - NATIVE_R6_STOP_TAG_XY[1]
    assert dy == pytest.approx(-0.004)
    old_stop = NATIVE_R6_OBSTACLES[stop_tag]
    ink = NATIVE_R6_TAG_INK[stop_tag]
    moved_ink = (
        ink[0] - NATIVE_R6_INK_PAD_M, ink[1] + dy - NATIVE_R6_INK_PAD_M,
        ink[2] + NATIVE_R6_INK_PAD_M, ink[3] + dy + NATIVE_R6_INK_PAD_M,
    )
    centre = sheet._plan_xy(*sheet.STOP_SCREW_XZ, center=sheet.HOLE_TOP_CENTER)
    radius = sheet.STOP_SCREW_HOLE_DIA * sheet.VIEW_SCALE / 2000.0
    stop_rim = (
        centre[0] - radius, centre[1] - radius,
        centre[0] + radius, centre[1] + radius,
    )
    # Preserve the complete physical rim and old tip/stub footprint. Only the
    # text/shoulder end drops: the hull bounds a shortened straight/monotone
    # bent leader to ANY unchanged rim point. Translating the whole GetBox
    # would falsely move its hole end down 4 mm. This is a conditional envelope;
    # the rebuilt native text, shoulder, stub and route must remain inside it.
    stop_extent = (
        min(old_stop[0], stop_rim[0], moved_ink[0]),
        min(old_stop[1], stop_rim[1], moved_ink[1]),
        max(old_stop[2], stop_rim[2], moved_ink[2]),
        max(old_stop[3] + dy, stop_rim[3], moved_ink[3]),
    )
    assert stop_extent[1] <= old_stop[1]
    assert stop_extent[1] > old_stop[1] + dy
    assert stop_extent[3] == pytest.approx(0.2124275384615385)
    for x, y in ((stop_rim[0], stop_rim[1]), (stop_rim[2], stop_rim[3])):
        assert stop_extent[0] <= x <= stop_extent[2]
        assert stop_extent[1] <= y <= stop_extent[3]
    assert abs(new_anchor[1] - centre[1]) < abs(NATIVE_R6_STOP_TAG_XY[1] - centre[1])
    assert sheet.box_gap(extent, stop_extent) == pytest.approx(0.005783344481605331)
    assert sheet.box_gap(NATIVE_R6_OBSTACLES[lock_tag], stop_extent) == pytest.approx(
        0.00638284280936455,
    )
    pedestal_start_y = NATIVE_R5_CALLOUTS["MHA-DT-02 pedestal transfer"][1][0][1]
    assert pedestal_start_y - stop_extent[3] == pytest.approx(0.00557919335855367)
    # Even the pedestal's lower tip stub remains above this full stop envelope.
    assert min(
        value for line in leaders["MHA-DT-02 pedestal transfer"] for value in (line[1], line[3])
    ) - stop_extent[3] > sheet.CALLOUT_CLEARANCE_M

    proposed = {**NATIVE_R6_OBSTACLES, stop_tag: stop_extent}
    assert proposed[lock_tag] == NATIVE_R6_OBSTACLES[lock_tag]
    proposed_texts = {
        name: box for name, box in proposed.items()
        if name.startswith(sheet._TEXT_OBSTACLE_KINDS)
    }
    assert set(proposed) == set(NATIVE_R5_OBSTACLES)
    assert sheet.find_callout_clashes(
        {"stop tag": stop_extent},
        {name: box for name, box in proposed_texts.items() if name != stop_tag},
    ) == []
    assert sheet.find_callout_clashes(callouts, proposed) == []
    assert sheet.find_merged_blocks(callouts) == []
    assert sheet.find_tall_callouts(own_rows) == []
    assert sheet.find_leader_crossings(
        leaders, {**foreign_texts, **proposed_texts}, own_rows,
    ) == []
    assert sheet.find_leader_crossings(
        {label: lines for label, (_anchor, lines, _texts) in NATIVE_R5_CALLOUTS.items()},
        {stop_tag: stop_extent, lock_tag: proposed[lock_tag]},
    ) == []


def test_native_r6_stop_lock_ink_blocks_require_stop_station_shift() -> None:
    """Replay the enforced shared predicate, not the recipe's callout-only rule."""
    import draw_fr_harmonic_base as sheet
    from _layout_audit import AuditAnnotation, ROW_PITCH_HEIGHTS, find_merged_blocks
    from _layout_geometry import Box, DrawableRegion, Segment, SheetGeometry

    _callouts, _leaders, own_rows = _native_r5_r6_callout_layout()
    callout_annotations = tuple(
        AuditAnnotation(
            label=f"hole-callout {label}", kind="hole-callout", owner="callout replay",
            text_boxes=tuple(Box(*box) for box in own_rows[label].values()),
            segments=tuple(
                Segment(*line, "shoulder" if sheet._is_shoulder(line) else "leader")
                for line in lines
            ),
            text_height=max(height for _text, _position, height in texts),
        )
        for label, (_anchor, lines, texts) in NATIVE_R5_CALLOUTS.items()
    )
    stop_tag, lock_tag = NATIVE_R6_TAG_INK
    tags = []
    for station, label, anchor, diameter in (
        (sheet.STOP_SCREW_XZ, stop_tag, NATIVE_R6_STOP_TAG_XY, sheet.STOP_SCREW_HOLE_DIA),
        (sheet.LOCK_KNOB_XZ, lock_tag, (0.2425, 0.2230), sheet.LOCK_SCREW_HOLE_DIA),
    ):
        x0, y0, x1, y1 = NATIVE_R6_TAG_INK[label]
        rim = sheet._hole_rim(*station, diameter)
        # The captured annotations are native leadered notes, not hole-callout
        # dimensions or free notes. Their actual leader arrays/font heights
        # were NOT logged. The source anchor-to-rim segment is only an explicit
        # nonempty-leader fixture contract for _callout_blocks, NOT a captured
        # native vector. Recover a conservative text-height bound from the
        # logged audit pitch using its unchanged ROW_PITCH_HEIGHTS constant.
        tags.append(AuditAnnotation(
            label=label, kind="note", owner="holes top",
            text_boxes=(Box(
                x0 - NATIVE_R6_INK_PAD_M, y0 - NATIVE_R6_INK_PAD_M,
                x1 + NATIVE_R6_INK_PAD_M, y1 + NATIVE_R6_INK_PAD_M,
            ),),
            segments=(Segment(*anchor, *rim, "leader"),),
            position=anchor,
            text_height=NATIVE_R6_PITCH_UPPER_M / ROW_PITCH_HEIGHTS,
        ))
    observed = SheetGeometry(
        name="HOLES-SOCKETS", width=0.4318, height=0.2794,
        region=DrawableRegion(0.0127, 0.0127, 0.4191, 0.2667),
        annotations=(*callout_annotations, *tags),
    )
    assert len(observed.annotations) == 7  # all five callouts plus both tag notes
    before = find_merged_blocks(observed)
    assert [(finding.kind, finding.a, finding.b) for finding in before] == [
        ("merged-blocks", stop_tag, lock_tag),
    ]
    assert before[0].extra["gap_mm"] == pytest.approx(3.40)
    assert before[0].extra["limit_mm"] == pytest.approx(5.405)

    stop, lock = tags
    new_anchor = sheet.HOLE_TAG_STATION_POSITIONS[sheet.STOP_SCREW_XZ]
    assert new_anchor == (0.247, 0.212)
    assert sheet.HOLE_TAG_STATION_POSITIONS[sheet.LOCK_KNOB_XZ] == lock.position
    dy = new_anchor[1] - stop.position[1]
    ink = stop.text_boxes[0]
    shifted_stop = replace(
        stop, position=new_anchor,
        text_boxes=(Box(ink.xmin, ink.ymin + dy, ink.xmax, ink.ymax + dy),),
        # Move only the text end of the conditional leader, never its rim.
        segments=tuple(replace(line, y0=line.y0 + dy) for line in stop.segments),
    )
    assert shifted_stop.segments[0].x1 == stop.segments[0].x1
    assert shifted_stop.segments[0].y1 == stop.segments[0].y1
    proposed = replace(observed, annotations=(*callout_annotations, shifted_stop, lock))
    assert find_merged_blocks(proposed) == []
    # The actual R6 finding was 3.52 + 4 = 7.52 mm versus 5.40 mm. The rounded,
    # outward-padded replay is stricter: 3.40 + 4 = 7.40 versus 5.405 mm, leaving
    # 1.995 mm. This translated-ink control is NOT a native after-fix audit.
    padded_gap_mm = before[0].extra["gap_mm"] - dy * 1000.0
    assert padded_gap_mm == pytest.approx(7.40)
    assert padded_gap_mm - before[0].extra["limit_mm"] == pytest.approx(1.995)



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
    pivot_tag="Q7",
    numbered_note_tag=None,
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
            sheet.pivot_seat_step(numbered_note_tag or pivot_tag).replace("\n", "\r\n") + "\r\n"
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
        hole_table=_NativeHoleTable(pivot_tag=pivot_tag),
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


@pytest.mark.parametrize("tag", ("D1", "Q7", "B12"))
def test_hole_sheet_numbered_note_matches_the_physical_pivot_tag(monkeypatch, tag) -> None:
    _drive_hole_sheet_callout_check(monkeypatch, None, pivot_tag=tag)
    with pytest.raises(RuntimeError, match="exactly one numbered pivot seat note"):
        _drive_hole_sheet_callout_check(
            monkeypatch, None, pivot_tag=tag, numbered_note_tag="Z99",
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
    with pytest.raises(RuntimeError, match="missing native pivot offsets|duplicate native pivot offset"):
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
    """Synthetic through-table at all real stations, not a captured native census."""

    def __init__(
        self, *, refuse=None, widths=(0.0198, 0.0303, 0.0317, 0.0628),
        pivot_tag="Q7", merged=True,
    ):
        import draw_fr_harmonic_base as sheet

        self.refuse = refuse
        self.station_tags = {}
        rows = []
        supports = sorted(sheet.HOLE_XZ, key=lambda xz: (xz[0], -xz[1]))
        sockets = sorted(sheet.COLUMN_SOCKET_XZ)
        for x, z, diameter in sheet.TABLE_HOLES:
            station = (x, z)
            if station in supports:
                tag = f"B{supports.index(station) + 1}" if merged else f"F{supports.index(station) + 1}"
                size = "1/4-20 UNC - 2B THRU"
            elif station == sheet.LOCK_KNOB_XZ:
                tag = "B5" if merged else "L1"
                size = "1/4-20 UNC - 2B THRU"
            elif station == sheet.PIVOT_SCREW_XZ:
                tag, size = pivot_tag, "#10-24 UNC - 2B THRU"
            elif station == sheet.STOP_SCREW_XZ:
                # Put the old pivot letter on another station deliberately.
                tag, size = ("N1" if pivot_tag == "D1" else "D1"), "#4-40 UNC - 2B THRU"
            else:
                assert station in sockets
                tag, size = f"A{sockets.index(station) + 1}", f"Ø{diameter / 25.4:.3f} THRU"
            self.station_tags[station] = tag
            # The inch sheet's LOC cells: inches at the table's three places.
            rows.append([
                tag, f"{(x + sheet.BOTTOM_LENGTH / 2.0) / 25.4:.3f}",
                f"{(sheet.BOTTOM_WIDTH / 2.0 - z) / 25.4:.3f}", size,
            ])
        # Native row order is not model selection order. Keep every fixture shuffled.
        rows = (rows[::2] + rows[1::2])[::-1]
        self.cells = [["TAG", "X LOC", "Y LOC", "SIZE"], *rows]
        self.pivot_row = next(index for index, row in enumerate(self.cells) if row[0] == pivot_tag)
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


@pytest.mark.parametrize("pivot_tag", ("D1", "Q7", "B12"))
@pytest.mark.parametrize("merged", (False, True))
def test_pivot_table_row_carries_note_flag_in_custom_column_only(pivot_tag, merged) -> None:
    import draw_fr_harmonic_base as sheet

    table = _NativeHoleTable(pivot_tag=pivot_tag, merged=merged)
    native = [list(row) for row in table.cells]
    native_width = sum(table.widths)
    generated, width = sheet._flag_pivot_seat_table_row(table)

    assert len(generated) == len(sheet.TABLE_HOLES) + 1 == 12
    assert generated == tuple(tuple(row) for row in native)
    assert width == pytest.approx(native_width)
    assert set(sheet.PIVOT_SEAT_CALLOUTS.values()) == {sheet.PIVOT_SEAT_FLAG}
    assert [row[:4] for row in table.cells] == native
    assert [row[4] for row in table.cells] == [
        sheet.PIVOT_SEAT_TABLE_COLUMN if index == 0 else
        sheet.PIVOT_SEAT_FLAG if index == table.pivot_row else ""
        for index in range(table.RowCount)
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
        ("insert", "refused the pivot NOTE column"),
        ("title", "NOTE column title did not set"),
        ("editable", "pivot NOTE cell is not editable"),
        ("text", "NOTE column did not persist"),
        ("width", "width did not persist"),
    ),
)
def test_pivot_table_flag_refuses_unconfirmed_native_state(refuse, message) -> None:
    import draw_fr_harmonic_base as sheet

    with pytest.raises(RuntimeError, match=message):
        sheet._flag_pivot_seat_table_row(_NativeHoleTable(refuse=refuse))


@pytest.mark.parametrize("pivot_rows", (0, 2))
def test_pivot_table_flag_requires_unique_physical_pivot_before_insertion(pivot_rows) -> None:
    import draw_fr_harmonic_base as sheet

    table = _NativeHoleTable()
    pivot = list(table.cells[table.pivot_row])
    table.cells[table.pivot_row:table.pivot_row + 1] = [pivot] * pivot_rows
    with pytest.raises(RuntimeError, match="station/row bijection"):
        sheet._flag_pivot_seat_table_row(table)
    assert table.ColumnCount == 4


def test_pivot_table_flag_refuses_insufficient_column_slack() -> None:
    import draw_fr_harmonic_base as sheet

    table = _NativeHoleTable(widths=(0.012, 0.022, 0.022, 0.0628))
    with pytest.raises(RuntimeError, match="slack cannot hold"):
        sheet._flag_pivot_seat_table_row(table)
    assert table.ColumnCount == 4


@pytest.mark.parametrize(
    ("mutate", "message"),
    (
        (lambda table: table.cells[table.pivot_row].__setitem__(1, "(142.05)"), "changed generated"),
        (lambda table: table.cells[2].__setitem__(3, ""), "changed generated"),
        (lambda table: table.cells[table.pivot_row].__setitem__(0, "Z99"), "changed generated"),
        (lambda table: table.cells[table.pivot_row].__setitem__(4, ""), "did not persist"),
        (lambda table: table.cells[0].__setitem__(4, "NOTES"), "did not persist"),
        (lambda table: table.cells[1 if table.pivot_row != 1 else 2].__setitem__(4, "SEE NOTE 1"), "did not persist"),
        (lambda table: table.widths.__setitem__(3, 0.070), "changed the hole-table width"),
        (lambda table: [row.pop() for row in table.cells], "lost or duplicated"),
    ),
)
def test_pivot_table_flag_rebuild_readback_refuses_drift(mutate, message) -> None:
    import draw_fr_harmonic_base as sheet

    table = _NativeHoleTable()
    generated, width = sheet._flag_pivot_seat_table_row(table)
    mutate(table)
    with pytest.raises(RuntimeError, match=message):
        sheet._check_pivot_seat_table_row(table, generated, width)


@pytest.mark.parametrize("merged", (False, True))
def test_native_table_station_resolver_uses_coordinates_not_family_or_row_order(merged) -> None:
    import draw_fr_harmonic_base as sheet

    table = _NativeHoleTable(merged=merged)
    bindings = sheet._hole_table_station_rows(table)
    assert set(bindings) == {hole[:2] for hole in sheet.TABLE_HOLES}
    assert len(bindings) == len({row.tag for row in bindings.values()}) == 11
    for station, row in bindings.items():
        assert row.tag == table.station_tags[station]
        assert table.cells[row.index][0] == row.tag
        x, z = station
        assert row.location_mm == pytest.approx(
            (x + sheet.BOTTOM_LENGTH / 2.0, sheet.BOTTOM_WIDTH / 2.0 - z), abs=0.0127,
        )


@pytest.mark.parametrize(
    ("fault", "message"),
    (
        ("missing", "station/row bijection"),
        ("extra", "station/row bijection"),
        ("duplicate-tag", "duplicate or empty"),
        ("empty-tag", "duplicate or empty"),
        ("duplicate-station", "duplicate native hole-table station"),
        ("unknown-station", "needs one model station"),
        ("nonnumeric", "invalid native hole-table coordinates"),
        ("nan", "nonfinite native hole-table coordinates"),
        ("infinity", "nonfinite native hole-table coordinates"),
    ),
)
def test_native_table_station_resolver_refuses_corrupt_or_incomplete_rows(fault, message) -> None:
    import draw_fr_harmonic_base as sheet

    table = _NativeHoleTable()
    if fault == "missing":
        table.cells.pop()
    elif fault == "extra":
        table.cells.append(["Z99", "0", "0", "extra"])
    elif fault == "duplicate-tag":
        table.cells[2][0] = table.cells[1][0]
    elif fault == "empty-tag":
        table.cells[2][0] = " "
    elif fault == "duplicate-station":
        table.cells[2][1:3] = table.cells[1][1:3]
    else:
        table.cells[1][1] = {
            "unknown-station": "-999", "nonnumeric": "(31.60)",
            "nan": "nan", "infinity": "inf",
        }[fault]
    with pytest.raises(RuntimeError, match=message):
        sheet._hole_table_station_rows(table)


def test_native_table_station_resolver_refuses_ambiguous_matches(monkeypatch) -> None:
    import draw_fr_harmonic_base as sheet

    table = _NativeHoleTable()
    x, z, diameter = sheet.TABLE_HOLES[0]
    tag = table.station_tags[(x, z)]
    index = next(index for index, row in enumerate(table.cells) if row[0] == tag)
    table.cells.insert(1, table.cells.pop(index))
    monkeypatch.setattr(sheet, "TABLE_HOLES", (
        sheet.TABLE_HOLES[0], (x + 0.01, z + 0.01, diameter), *sheet.TABLE_HOLES[2:],
    ))
    with pytest.raises(RuntimeError, match="needs one model station") as error:
        sheet._hole_table_station_rows(table)
    assert repr((x, z)) in str(error.value)
    assert repr((x + 0.01, z + 0.01)) in str(error.value)


def test_native_table_station_resolver_keeps_insert_helper_coordinate_tolerance() -> None:
    import draw_fr_harmonic_base as sheet

    table = _NativeHoleTable()
    row = table.cells[1]
    x, _z = next(station for station, tag in table.station_tags.items() if tag == row[0])
    exact = (x + sheet.BOTTOM_LENGTH / 2.0) / 25.4
    row[1] = str(exact + 0.019 / 25.4)
    sheet._hole_table_station_rows(table)
    row[1] = str(exact + 0.03 / 25.4)
    with pytest.raises(RuntimeError, match="needs one model station"):
        sheet._hole_table_station_rows(table)


def _native_tag_view(monkeypatch, table):
    from types import SimpleNamespace

    import draw_fr_harmonic_base as sheet

    class Annotation:
        def __init__(self, tag, endpoint, kind=6):
            self.text = tag
            self.endpoint = endpoint
            self.kind = kind
            self.position = None
            self.leader_reads = 0
            self.failure = None

        def GetType(self):  # noqa: N802
            return self.kind

        def GetSpecificAnnotation(self):  # noqa: N802
            return self

        def GetText(self):  # noqa: N802
            return self.text

        def SetLeader3(self, *args):  # noqa: N802
            assert args == (1, 0, True, False, False, False)
            return -1 if self.failure == "leader" else 0

        def SetPosition2(self, x, y, z):  # noqa: N802
            self.position = (x, y, z)
            if self.failure == "text":
                self.text = "CHANGED"
            return self.failure != "position"

        def GetLeaderPointsAtIndex(self, index):  # noqa: N802
            assert index == 0
            self.leader_reads += 1
            return (*self.position, *self.endpoint, 0.0)

    by_station = {}
    for station, tag in table.station_tags.items():
        x, z = station
        by_station[station] = Annotation(
            tag, sheet._plan_xy(x, z, center=sheet.HOLE_TOP_CENTER),
        )
    annotations = list(reversed(tuple(by_station.values())))
    annotations.extend((
        Annotation("1/4-20 Tapped Hole", (0.0, 0.0)),
        Annotation("not a tag", (0.0, 0.0), kind=4),
    ))
    monkeypatch.setattr(sheet, "_early_bound", lambda obj, interface: obj)
    return SimpleNamespace(GetAnnotations=lambda: annotations), by_station, annotations


@pytest.mark.parametrize("merged", (False, True))
@pytest.mark.parametrize("pivot_tag", ("D1", "Q7", "B12"))
def test_native_tag_layout_follows_physical_stations_with_shuffled_families(
    monkeypatch, merged, pivot_tag,
) -> None:
    import draw_fr_harmonic_base as sheet

    table = _NativeHoleTable(merged=merged, pivot_tag=pivot_tag)
    generated, width = sheet._flag_pivot_seat_table_row(table)
    view, by_station, _annotations = _native_tag_view(monkeypatch, table)
    before = [list(row) for row in table.cells]
    sheet._spread_hole_tags(view, table)
    assert table.cells == before
    assert len(by_station) == len(sheet.TABLE_HOLES) == 11
    assert len(sheet.HOLE_TAG_STATION_POSITIONS) == len(sheet.TABLE_HOLES) == 11
    assert by_station[sheet.LOCK_KNOB_XZ].position == (0.2425, 0.2230, 0.0)
    assert by_station[sheet.STOP_SCREW_XZ].position == (0.247, 0.212, 0.0)
    for station, annotation in by_station.items():
        assert annotation.text == table.station_tags[station]
        position = sheet.HOLE_TAG_STATION_POSITIONS.get(station)
        assert annotation.position == ((*position, 0.0) if position else None)
        assert annotation.leader_reads == int(station in sheet._CRITICAL_HOLE_TAG_STATIONS)
    sheet._check_pivot_seat_table_row(table, generated, width)


def test_native_tag_layout_and_pivot_flag_follow_all_eleven_renamed_tags(monkeypatch) -> None:
    import draw_fr_harmonic_base as sheet

    table = _NativeHoleTable()
    renamed = {tag: f"R{index}" for index, tag in enumerate(table.station_tags.values(), 1)}
    for row in table.cells[1:]:
        row[0] = renamed[row[0]]
    table.station_tags = {station: renamed[tag] for station, tag in table.station_tags.items()}
    generated, width = sheet._flag_pivot_seat_table_row(table)
    view, by_station, _annotations = _native_tag_view(monkeypatch, table)
    sheet._spread_hole_tags(view, table)
    for station, position in sheet.HOLE_TAG_STATION_POSITIONS.items():
        assert by_station[station].position == (*position, 0.0)
    pivot = sheet._hole_table_station_rows(table)[sheet.PIVOT_SCREW_XZ]
    assert table.cells[pivot.index][4] == sheet.PIVOT_SEAT_FLAG
    assert pivot.tag in sheet.pivot_seat_step(pivot.tag)
    sheet._check_pivot_seat_table_row(table, generated, width)


@pytest.mark.parametrize("fault", ("missing", "duplicate", "extra", "wrong-type"))
def test_native_tag_layout_requires_exact_table_view_bijection(monkeypatch, fault) -> None:
    import draw_fr_harmonic_base as sheet

    table = _NativeHoleTable()
    view, by_station, annotations = _native_tag_view(monkeypatch, table)
    # An uncurated west socket must also exist exactly once.
    station = min(sheet.COLUMN_SOCKET_XZ)
    selected = by_station[station]
    if fault == "missing":
        annotations.remove(selected)
    elif fault == "duplicate":
        annotations.append(selected)
    elif fault == "extra":
        orphan = type(selected)("Z99", (0.0, 0.0))
        annotations.append(orphan)
    else:
        selected.kind = 4
    with pytest.raises(RuntimeError, match="table/view tag bijection failed"):
        sheet._spread_hole_tags(view, table)
    assert all(annotation.position is None for annotation in by_station.values())


@pytest.mark.parametrize("critical_index", (0, 1, 2))
@pytest.mark.parametrize("endpoint", ((0.0, 0.0), (math.nan, 0.0), (), "other-hole"))
def test_native_tag_layout_checks_physical_critical_leader_endpoints(
    monkeypatch, critical_index, endpoint,
) -> None:
    import draw_fr_harmonic_base as sheet

    table = _NativeHoleTable()
    view, by_station, _annotations = _native_tag_view(monkeypatch, table)
    station = sheet._CRITICAL_HOLE_TAG_STATIONS[critical_index]
    if endpoint == "other-hole":
        other = next(xz for xz in table.station_tags if xz != station)
        endpoint = by_station[other].endpoint
    by_station[station].endpoint = endpoint
    with pytest.raises(RuntimeError, match="does not reach its table hole|no complete finite leader"):
        sheet._spread_hole_tags(view, table)


@pytest.mark.parametrize(
    ("failure", "message"),
    (("leader", "give native hole tag"), ("position", "reposition native hole tag"),
     ("text", "changed its text")),
)
def test_native_tag_layout_refuses_failed_native_movement(monkeypatch, failure, message) -> None:
    import draw_fr_harmonic_base as sheet

    table = _NativeHoleTable()
    view, by_station, _annotations = _native_tag_view(monkeypatch, table)
    by_station[sheet.PIVOT_SCREW_XZ].failure = failure
    with pytest.raises(RuntimeError, match=message):
        sheet._spread_hole_tags(view, table)


@pytest.mark.parametrize("missing", (False, True))
def test_native_tag_diagnostics_include_bounded_rows_view_inventory_and_station_binding(
    monkeypatch, missing,
) -> None:
    import draw_fr_harmonic_base as sheet

    table = _NativeHoleTable()
    view, by_station, annotations = _native_tag_view(monkeypatch, table)
    logs = []
    monkeypatch.setattr(sheet._telemetry, "info", logs.append)
    ordinary = annotations[-2]
    ordinary.text = "ordinary " + "x" * 2000
    if missing:
        annotations.remove(by_station[sheet.PIVOT_SCREW_XZ])
        with pytest.raises(RuntimeError, match="table/view tag bijection failed"):
            sheet._spread_hole_tags(view, table)
    else:
        sheet._spread_hole_tags(view, table)
    assert any("native base hole-table rows: shape=12x4" in line for line in logs)
    assert any("native base hole-view inventory:" in line and "Q7" in line for line in logs) is not missing
    assert any("native base hole-table station binding:" in line and "Q7" in line for line in logs)
    assert not any("x" * 161 in line for line in logs)


def test_station_layout_retains_support_pairing_without_crossing_neighbors() -> None:
    import draw_fr_harmonic_base as sheet

    supports = sorted(sheet.HOLE_XZ, key=lambda xz: (xz[0], -xz[1]))
    assert [sheet.HOLE_TAG_STATION_POSITIONS[xz] for xz in supports] == [
        (0.297, 0.1895), (0.289, 0.206), (0.312, 0.173), (0.312, 0.214),
    ]
    assert set(sheet._CRITICAL_HOLE_TAG_STATIONS) == {
        sheet.PIVOT_SCREW_XZ, supports[0], supports[2],
    }
    # Each pair stays on its own side of the pattern midpoint in plan Y.
    middle_y = sum(sheet._plan_xy(*xz, center=sheet.HOLE_TOP_CENTER)[1] for xz in supports) / 4
    for station in supports:
        tip = sheet._plan_xy(*station, center=sheet.HOLE_TOP_CENTER)
        anchor = sheet.HOLE_TAG_STATION_POSITIONS[station]
        assert (tip[1] - middle_y) * (anchor[1] - middle_y) > 0.0
    assert sheet.HOLE_TAG_STATION_POSITIONS[supports[0]][0] < sheet.HOLE_TAG_STATION_POSITIONS[supports[2]][0]
    assert sheet.HOLE_TAG_STATION_POSITIONS[supports[1]][0] < sheet.HOLE_TAG_STATION_POSITIONS[supports[3]][0]


@pytest.mark.parametrize(
    ("larger_z", "old_anchor", "old_box"),
    [
        (True, (0.325, 0.176), (0.3251, 0.1724, 0.3309, 0.1760)),
        (False, (0.326, 0.215), (0.3261, 0.2115, 0.3319, 0.2150)),
    ],
)
def test_socket_tags_clear_the_native_section_cut_line(larger_z, old_anchor, old_box) -> None:
    import draw_fr_harmonic_base as sheet

    # r2b native ink, not an estimated label width. The former tags were
    # both struck by the A-A line through the right-hand socket axes.
    cut_line = (0.3292, 0.155, 0.3292, 0.235)
    assert sheet.segment_crosses_box(cut_line, old_box)
    east = sorted((xz for xz in sheet.COLUMN_SOCKET_XZ if xz[0] > 0.0), key=lambda xz: xz[1])
    station = east[-1] if larger_z else east[0]
    x, y = sheet.HOLE_TAG_STATION_POSITIONS[station]
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
    # 1.244 and 16.756 (flow-through until the column snap: 1.2441 / 16.7559)
    # are also the table's A1/A2 and A3/A4 X LOCs from the same flange edge.
    assert part.BOTTOM_LENGTH / 2.0 - part.COLUMN_X == pytest.approx(1.244 * 25.4, abs=0.003)
    assert part.BOTTOM_LENGTH / 2.0 + part.COLUMN_X == pytest.approx(16.756 * 25.4, abs=0.003)


def test_deck_land_worst_case_is_proven_instead_of_noted() -> None:
    # hb-render-4 eye pass: the MIN land note put a dimension in a note.
    assert not hasattr(fr_harmonic_base_spec, "DRAWING_NOTES")
    # The bore now opens on the green land and reaches the pad's outer edge,
    # whose 1/16 in break (and its general band) is the land's last bite.
    # The nominal follows the column line: 12.4968 on both axes once the column
    # snap lands, 12.4992 / 12.5108 (inside the .0005 equal-land grid) before.
    lands = {"x": part.COLUMN_SOCKET_LAND_X, "z": part.COLUMN_SOCKET_LAND_Z}
    for axis, stack in part.COLUMN_SOCKET_LAND_STACKS.items():
        assert stack["nominal"] == pytest.approx(lands[axis])
        assert stack["nominal"] == pytest.approx(12.4968, abs=0.015)
        assert {name: v for name, v in stack.items() if name != "nominal"} == pytest.approx({
            "flange length": -0.127,
            "pad length": -0.127,
            "bore location": -0.254,
            "matched bore": -0.2492,
            "bore edge break": -0.254,
            "pad edge chamfer": -1.8542,
        })
        assert sum(stack.values()) == pytest.approx(stack["nominal"] - 2.8654)
    # The same stack on the rejected 1.6 mm pad land would fail the .040 MIN.
    assert sum(part.column_socket_land_stack(1.6).values()) < part.COLUMN_SOCKET_LAND_MIN
    # Main's rider: the bore ceiling is a functional judgement, so the
    # stack reports how much bore the land could still absorb.
    assert part.COLUMN_SOCKET_BREAK_EVEN_BORE == pytest.approx(43.2308, abs=0.006)
    rejected = part.column_socket_land_stack(1.6)
    assert part.column_socket_break_even_bore(rejected) < part.COLUMN_SOCKET_MATCH_BORE_MAX


def test_retained_pocket_walls_socket_bosses_and_cross_tap_lugs_keep_their_contracts() -> None:
    spec = fr_harmonic_base_spec
    assert spec.POCKET_HALF_X == pytest.approx(spec.TOP_LENGTH / 2.0 - spec.POCKET_WALL)
    assert spec.POCKET_HALF_Z == pytest.approx(spec.TOP_WIDTH / 2.0 - spec.POCKET_WALL)
    assert spec.STACK_HEIGHT - spec.POCKET_CEILING_Y == pytest.approx(spec.POCKET_SKIN)
    assert len(part.SOCKET_BOSS_SHAPES) == len(part.CROSS_TAP_LUG_SHAPES) == 4
    assert spec.CROSS_TAP_LUG_BOTTOM_Y == 26.416  # 1.04
    band = part._general_band_mm()
    assert min(part.CROSS_TAP_LUG_WALLS.values()) - 1.5 * band >= WALL_TARGET_MM
    assert (
        part.CROSS_TAP_LUG_WALLS["past tip"]
        >= 1.5 * part.THREAD_MAJOR_MM[part.BASE_CROSS_TAP_SPEC.size]
    )
    assert part.SOCKET_BOSS_WALL == pytest.approx(7.9502)


def test_cross_tap_remains_backed_when_the_pocket_ceiling_is_below_its_axis() -> None:
    spec = fr_harmonic_base_spec
    radius = part.THREAD_MAJOR_MM[part.BASE_CROSS_TAP_SPEC.size] / 2.0
    thread_bottom = part.BASE_SCREW_Y - radius
    thread_top = part.BASE_SCREW_Y + radius
    lug_interval = (spec.CROSS_TAP_LUG_BOTTOM_Y, spec.POCKET_CEILING_Y)
    skin_interval = (spec.POCKET_CEILING_Y, spec.GREEN_TOP)
    assert part.BASE_SCREW_Y - spec.POCKET_CEILING_Y == pytest.approx(0.254)
    # The bore crosses the shared boundary; lug below plus skin above is
    # continuous metal even though the ceiling is lower than the axis.
    assert lug_interval[0] < thread_bottom < lug_interval[1]
    assert lug_interval[1] == skin_interval[0]
    assert skin_interval[0] < thread_top < skin_interval[1]
    margins = part.cross_tap_backing_margins_mm(part._general_band_mm())
    assert margins["lug/skin join"] == pytest.approx(10.922)
    assert margins["green skin"] == pytest.approx(7.366)
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
    from fr_vn_lag_screw_spec import LENGTH_MM, TIP_CHAMFER

    fasteners = fr_harmonic_base_fasteners
    assert LENGTH_MM == 19.05
    material = part.THROUGH_SEAT_MATERIAL["SupportHoldDownSeats"][0]
    fit = fr_harmonic_base_fasteners.require_through_seat_fit(
        "specified rocker support", part.HOLD_DOWN_SEAT_SPEC, material,
        insertion_min_mm=fasteners.HOLD_DOWN_INSERTION_MIN_MM,
        insertion_max_mm=fasteners.HOLD_DOWN_INSERTION_MAX_MM,
        tip_loss_mm=TIP_CHAMFER,
    )
    assert fit.full_thread_engagement_min_mm == pytest.approx(10.1996875)
    assert fit.full_thread_engagement_min_mm >= 1.5 * 6.35
    assert fit.protrusion_max_mm == pytest.approx(
        fasteners.HOLD_DOWN_INSERTION_MAX_MM - material.exit_depth_min_mm,
    )
    assert fit.protrusion_max_mm > 0.0
    assert fit.clearance_min_mm > 0.0


def test_cross_tap_drill_keeps_the_bottoming_lead_past_the_deepest_thread() -> None:
    from _printed_tolerance import printed_band_mm
    from fr_frame_attachment_spec import CASTING_FULL_THREAD_DEPTH, CASTING_TAP_DRILL_DEPTH

    lead = 2.0 * 25.4 / 32.0
    # 48 MIN left 1.49 past 46.00 + 0.51, under two #10-32 pitches.
    band = printed_band_mm(2)
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
    assert sheet.SOCKET_FIT_STATION == (-part.COLUMN_X, part.FRAME_FRONT_COLUMN_Z)

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


def test_only_actual_mating_faces_keep_their_native_finish_controls() -> None:
    from _gtol_planar import PlanarFace

    spec = fr_harmonic_base_spec
    controls = {control.key: control for control in spec.PART_SURFACE_FINISHES}
    assert set(controls) == {"deck", "underside"} | {
        spec.socket_bore_finish_key(x, z) for x, z in spec.COLUMN_SOCKET_XZ
    }
    assert controls["deck"].face == PlanarFace((0, 1, 0), spec.STACK_HEIGHT)
    assert controls["underside"].face == PlanarFace((0, -1, 0), 0.0)
    assert all(control.roughness_um == spec.SEAT_UM for control in controls.values())
    # Coordinate references are still real flange edges, not finish controls.
    import draw_fr_harmonic_base as sheet

    assert sheet._TABLE_ORIGIN_XY == pytest.approx(
        sheet._plan_xy(-spec.BOTTOM_LENGTH / 2.0, spec.BOTTOM_REAR_Z, center=sheet.HOLE_TOP_CENTER),
    )


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


def test_underside_lug_baselines_increase_outward_from_the_rear_west_datum() -> None:
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
    printed = _lug_printed()
    assert printed["CrossRibX"] == pytest.approx(
        spec.BOTTOM_LENGTH / 2.0 + spec.CROSS_RIB_CENTER_X - spec.RIB_THICKNESS / 2.0,
    )
    assert dict(sheet.LUGS_X_ROWS)["CrossRibX"] == spec.CROSS_RIB_CENTER_X - 90.0
    assert sheet.LUGS_DATUM == pytest.approx(
        sheet._lugs_xy(-spec.BOTTOM_LENGTH / 2.0, spec.BOTTOM_REAR_Z)
    )
    for baselines in (sheet.LUGS_X_ROWS, sheet.LUGS_Y_COLUMNS):
        values = [printed[name] for name, *_ in baselines]
        assert values == sorted(values)


def test_retained_lug_bottom_is_a_native_model_dimension_not_a_removed_cast_level() -> None:
    import draw_fr_harmonic_base as sheet

    assert fr_harmonic_base_spec.DRAWING_DIMENSIONS["CrossTapLugs"] == {"LugBottom"}
    assert fr_harmonic_base_spec.DRAWING_PRECISION_BY_NAME["LugBottom"] == 2
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
    assert not {hole[:2] for hole in seats} & set(sheet.HOLE_TAG_STATION_POSITIONS)
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
        for tag, (tx, ty) in sheet.HOLE_TAG_STATION_POSITIONS.items()
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
    assert sheet.PIVOT_SEAT_Y_TEXT_XY == (0.2080, 0.1895)
    assert sheet.HOLE_TAG_STATION_POSITIONS[sheet.PIVOT_SCREW_XZ] == (0.2456, 0.1550)
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

    # The native R7 coupled replay below owns the Y value/flag and its route.
    # Keep this older X control as a separate precision/layout regression.
    x_flag = (0.2427 - 0.01235, 0.1347819, 0.2427 + 0.01235, 0.1382819)
    x_value = (0.2291351, 0.1292219, 0.2562650, 0.1327219)
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
    for label, box in {"X value": x_value, "X flag": x_flag}.items():
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
    for box in (x_flag,):
        for label, tag in tags.items():
            assert _box_gap(box, tag) >= 0.0035, label


@pytest.mark.parametrize("tag", ("D1", "Q7", "B12"))
def test_pivot_seat_setup_identifies_its_mate_without_numeric_offsets(tag) -> None:
    """Native tag presentation changes without moving ownership of offsets/bands."""
    import re

    import cone_set_stack
    import draw_fr_harmonic_base as sheet
    import fr_harmonic_base_spec as base_spec

    assert sheet.pivot_seat_step is base_spec.pivot_seat_step
    assert base_spec.PIVOT_SEAT_POSITION_BAND_MM == cone_set_stack.PIVOT_SEAT_POSITION_MM
    text = sheet.pivot_seat_step(tag)
    assert text.split("\n") == [
        f"1. {tag} IS LOCATED TO THE MHA-DT-02 SEAT;",
        "DRILL AND TAP AT ASSEMBLY.",
        f"{tag} TABLE X/Y ARE REFERENCE.",
    ]
    # Only the note number and part/table identities may contain digits;
    # the native dimensions remain the sole owners of offsets and bands.
    identification = text.removeprefix("1. ")
    for identity in (tag, "MHA-DT-02"):
        assert identity in identification
        identification = identification.replace(identity, "")
    assert not re.search(r"\d|<MOD-PM>|±", identification)
    table = _NativeHoleTable(pivot_tag=tag)
    assert sheet._hole_table_station_rows(table)[sheet.PIVOT_SCREW_XZ].tag == tag


def test_numbered_pivot_note_is_created_once_as_an_ordinary_free_note() -> None:
    import ast
    import inspect

    import draw_fr_harmonic_base as sheet

    tree = ast.parse(inspect.getsource(sheet.build))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    notes = [
        node for node in calls
        if any(isinstance(arg, ast.Call) and getattr(arg.func, "id", None) == "pivot_seat_step" for arg in node.args)
    ]
    assert len(notes) == 1
    assert notes[0].func.id == "add_note"
    assert [ast.unparse(arg) for arg in notes[0].args] == [
        "adapter", "pivot_seat_step(pivot_tag)", "*PIVOT_SEAT_NOTE_XY",
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
    assert {keyword.arg for keyword in check.keywords} == {"callouts", "views", "datum_origin", "hole_table"}
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
    assert spec.DRAWING_PRECISION["PivotSeatReference"] == dict.fromkeys(names, 3)
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
    assert spec.DRAWING_PRECISION["HeightReference"] == dict.fromkeys(stations, 2)
    assert "GreenTopHeight" in sheet.SIDE_KEEP
    assert "CrossScrewAxisHeight" in sheet.HOLE_SIDE_KEEP
    assert {"BottomThickness", "DeckRise"} <= set(sheet.SIDE_KEEP)
    kept = set(spec.DRAWING_PRECISION_BY_NAME)
    assert not {"FlangeToDeck", "Spot0Y"} & kept
    assert spec.GREEN_TOP + spec.DECK_RISE == pytest.approx(spec.STACK_HEIGHT)
    band = part._general_band_mm()
    assert band == pytest.approx(0.254)
    land = spec.cross_screw_top_land_worst_case_mm(
        part.BASE_SCREW_Y, part.SCREW_SPOTFACE_DIAMETER, band
    )
    # (1.88 - .01) - (1.50 + .01) - (.354 + .01) / 2 = .178.
    assert land == pytest.approx(
        ((1.88 - 0.01) - (1.50 + 0.01) - (0.354 + 0.01) / 2.0) * 25.4
    )
    assert land >= spec.CROSS_SCREW_TOP_LAND_MIN_MM == WALL_TARGET_MM


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

    assert plate.SCREW_FULL_THREAD_MIN == pytest.approx(3.63855)
    assert frame.NAMEPLATE_BASE_FULL_FORM_MIN == pytest.approx(3.38455)
    assert len(frame.NAMEPLATE_BASE_MATERIALS) == 4
    assert frame.NAMEPLATE_SCREW_MAX_INSERTION == pytest.approx(4.8768)
    assert frame.NAMEPLATE_TIP_CLEARANCE_MIN > 0.0
    for material in frame.NAMEPLATE_BASE_MATERIALS:
        start, end = material.guaranteed_segments_mm[0]
        assert start == pytest.approx(0.254)
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
    half_rib = fr_harmonic_base_spec.RIB_THICKNESS / 2.0
    chord = 2.0 * (half_rib * math.sqrt(64.0 - half_rib**2) + 64.0 * math.asin(half_rib / 8.0))
    assert alone - shared == pytest.approx(chord * (part.POCKET_CEILING_Y - bottom), rel=1e-6)


def test_through_cut_volume_integrates_skin_full_rib_and_half_rib_without_drill_point() -> None:
    seat = part.FOOT_SEAT_SPEC
    area = math.pi * (part.FOOT_SCREW_HOLE_DIA / 2.0) ** 2
    skin = part.STACK_HEIGHT - part.POCKET_CEILING_Y
    rib = part.STACK_HEIGHT - part.RIB_RELIEF
    edge = fr_harmonic_base_spec.RIB_THICKNESS / 2.0
    for xz, depth in (((100.0, 50.0), skin), ((100.0, 0.0), rib), ((100.0, edge), (skin + rib) / 2.0)):
        assert part._through_holes_volume_mm3(seat, (xz,)) == pytest.approx(area * depth, rel=2e-4)
    combined = part._through_holes_volume_mm3(seat, ((100.0, 50.0), (100.0, edge)))
    assert combined == pytest.approx(area * (skin + (skin + rib) / 2.0), rel=2e-4)


def test_pedestal_thread_interference_budget_stops_at_actual_retained_skin() -> None:
    import _interference_contracts as contracts

    assert fr_harmonic_base_fasteners.PEDESTAL_SCREW_ENGAGEMENT == pytest.approx(14.05)
    for xz in part.PEDESTAL_SCREW_XZ:
        assert fr_harmonic_base_fasteners.retained_material_segments_mm(*xz)[0] == pytest.approx((0.0, 12.954))
    allowed = contracts.allowed_interference_pairs("ha-harmonic-analyzer")
    expected = 1.10 * math.pi / 4.0 * (4.1656**2 - 3.454**2) * 12.954
    obsolete = 1.10 * math.pi / 4.0 * (4.1656**2 - 3.454**2) * 14.05
    for number in (1, 2):
        pair = frozenset((
            f"dt-drive-train-1/dt-vn-pedestal-hold-down-screw-{number}",
            "fr-frame-1/fr-harmonic-base-1",
        ))
        assert allowed[pair] == pytest.approx(expected)
        assert allowed[pair] < obsolete


def _native_ray_hit(
    ray: int, depth: float, flags: float, *, x=100.0, z=50.0, normal=(0.0, 1.0, 0.0),
):
    """Documented nine-double ENTRY_EXIT | NORMALS record; lengths are SI."""
    return (
        0.0, float(ray), flags,
        x / 1000.0, (50.8 - depth) / 1000.0, z / 1000.0, *normal,
    )


def _native_ray_adapter(monkeypatch, raw, *, count=..., bodies=None):
    """Model the integer intersection-count retval, not a ray/scalar count."""
    from types import SimpleNamespace
    from solidworks_mcp.adapters import com_variant

    body_list = (object(),) if bodies is None else bodies
    calls = []

    def intersect(*args):
        calls.append(args)
        return (0 if raw is None else len(raw) // 9) if count is ... else count

    model = SimpleNamespace(
        Extension=SimpleNamespace(RayIntersections=intersect),
        GetBodies2=lambda *_args: body_list,
        GetRayIntersectionsPoints=lambda: raw,
    )
    monkeypatch.setattr(part, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(com_variant, "dispatch_array", lambda values: values)
    monkeypatch.setattr(com_variant, "double_array", lambda values: values)
    return SimpleNamespace(currentModel=model), calls


def _native_ray_diagnostics(error):
    from ast import literal_eval

    return literal_eval(str(error.value).split("; native_ray_readback=", 1)[1])


@pytest.fixture
def native_flat_nine_field_ray_records():
    """Two documented face hits on one ray: indices, flags, point, normal."""
    return (
        0.0, 0.0, 17.0, 0.100, 0.0508, 0.050, 0.0, 1.0, 0.0,
        0.0, 0.0, 33.0, 0.100, 0.0378, 0.050, 0.0, -1.0, 0.0,
    )


@pytest.mark.parametrize("container", (tuple, list))
def test_native_rays_decode_documented_flat_nine_field_records_and_hit_count(
    monkeypatch, native_flat_nine_field_ray_records, container,
) -> None:
    raw = container(native_flat_nine_field_ray_records)
    assert len(raw) == 18  # Two intersections on one ray, not eighteen hits.
    adapter, calls = _native_ray_adapter(monkeypatch, raw, count=2)
    result = part._native_vertical_segments(adapter, ((100.0, 50.0),), "documented rays")
    assert len(result) == 1
    assert len(result[0]) == 1
    assert result[0][0] == pytest.approx((0.0, 13.0))
    assert len(calls) == 1
    assert len(calls[0]) == 7
    assert len(calls[0][0]) == 1
    assert calls[0][3:6] == (5, 1e-9, 1e-8)
    assert calls[0][6] is True


@pytest.mark.parametrize("count", (1, 18))
def test_native_rays_refuse_ray_or_scalar_count_instead_of_intersection_count(
    monkeypatch, native_flat_nine_field_ray_records, count,
) -> None:
    adapter, _calls = _native_ray_adapter(monkeypatch, native_flat_nine_field_ray_records, count=count)
    with pytest.raises(RuntimeError, match="malformed") as error:
        part._native_vertical_segments(adapter, ((100.0, 50.0),), "wrong count")
    diagnostics = _native_ray_diagnostics(error)
    assert diagnostics["reported_count"] == repr(count)
    assert diagnostics["raw_length"] == 18
    assert diagnostics["expected_record_width"] == 9


@pytest.mark.parametrize("raw", (None, (), []))
def test_native_rays_allow_zero_hits_only_with_integral_zero_count(monkeypatch, raw) -> None:
    adapter, calls = _native_ray_adapter(monkeypatch, raw, count=0)
    assert part._native_vertical_segments(
        adapter, ((100.0, 50.0), (100.0, 0.0)), "empty rays",
    ) == ((), ())
    assert calls[0][3] == 5


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
    assert calls[0][3:6] == (5, 1e-9, 1e-8)
    assert calls[0][6] is True


@pytest.mark.parametrize(
    ("raw", "count", "message"),
    (
        ((0.0,), 1, "malformed"),
        (_native_ray_hit(0, 0.0, 16, normal=()), 1, "malformed"),
        (_native_ray_hit(0, 0.0, 16, normal=(0.0, 1.0)), 1, "malformed"),
        (_native_ray_hit(0, 0.0, 16, normal=(0.0, 1.0, 0.0, 0.0)), 1, "malformed"),
        (None, 1, "malformed"),
        ("not a native array", 0, "malformed"),
        (42, 0, "malformed"),
        ((), -1, "malformed"),
        ((), 0.5, "nonintegral"),
        (_native_ray_hit(0, math.nan, 16), 1, "non-finite"),
        ((1.0, *_native_ray_hit(0, 0.0, 16)[1:]), 1, "index"),
        ((0.5, *_native_ray_hit(0, 0.0, 16)[1:]), 1, "index"),
        (_native_ray_hit(0.5, 0.0, 16), 1, "index"),
        (_native_ray_hit(-1, 0.0, 16), 1, "index"),
        (_native_ray_hit(1, 0.0, 16), 1, "index"),
        (_native_ray_hit(0, 0.0, 16, x=101.0), 1, "off its requested axis"),
        (_native_ray_hit(0, 0.0, 16 | 2), 1, "grazing"),
        (_native_ray_hit(0, 0.0, 16 | 4), 1, "grazing"),
        (_native_ray_hit(0, 0.0, 16 | 8), 1, "grazing"),
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
    with pytest.raises(RuntimeError, match=message) as error:
        part._native_vertical_segments(adapter, ((100.0, 50.0),), "bad ray")
    assert _native_ray_diagnostics(error).items() >= {
        "raw_type": type(raw).__name__,
        "reported_count": repr(count),
        "reported_count_type": type(count).__name__,
        "raw_length": len(raw) if isinstance(raw, (tuple, list, str)) else None,
        "expected_record_width": 9,
        "options": 5,
        "ray_count": 1,
    }.items()


@pytest.mark.parametrize("field_index", range(9))
@pytest.mark.parametrize("value", (math.nan, math.inf, -math.inf))
def test_native_rays_refuse_every_nonfinite_record_field(monkeypatch, field_index, value) -> None:
    raw = list(_native_ray_hit(0, 0.0, 16))
    raw[field_index] = value
    adapter, _calls = _native_ray_adapter(monkeypatch, raw, count=1)
    with pytest.raises(RuntimeError, match="non-finite") as error:
        part._native_vertical_segments(adapter, ((100.0, 50.0),), "nonfinite ray")
    diagnostics = _native_ray_diagnostics(error)
    assert diagnostics["nonfinite_fields"] == (field_index,)
    assert diagnostics["record_index"] == 0
    assert diagnostics["expected_record_width"] == 9
    assert diagnostics["raw_length"] == 9


@pytest.mark.parametrize("field_index", (6, 7, 8))
@pytest.mark.parametrize(
    ("value", "conversion_error_type"),
    ((None, "TypeError"), ("not a normal", "ValueError"), ((), "TypeError"), (10**400, "OverflowError")),
)
def test_native_rays_refuse_malformed_normals_with_conversion_diagnostics(
    monkeypatch, field_index, value, conversion_error_type,
) -> None:
    raw = list(_native_ray_hit(0, 0.0, 16))
    raw[field_index] = value
    adapter, _calls = _native_ray_adapter(monkeypatch, raw, count=1)
    with pytest.raises(RuntimeError, match="malformed native ray-intersection record") as error:
        part._native_vertical_segments(adapter, ((100.0, 50.0),), "malformed normal")
    assert _native_ray_diagnostics(error).items() >= {
        "raw_type": "list",
        "reported_count": "1",
        "reported_count_type": "int",
        "raw_length": 9,
        "expected_record_width": 9,
        "options": 5,
        "ray_count": 1,
        "record_index": 0,
        "field_index": field_index,
        "field_type": type(value).__name__,
        "conversion_error_type": conversion_error_type,
    }.items()
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__ is True


@pytest.mark.parametrize(
    ("count", "count_value", "conversion_error_type"),
    (
        (None, "None", None),
        (True, "True", None),
        (False, "False", None),
        ("2", "'2'", None),
        ((), "<tuple>", None),
        (0.5, "0.5", None),
        (math.nan, "nan", "ValueError"),
        (math.inf, "inf", "OverflowError"),
        (-math.inf, "-inf", "OverflowError"),
    ),
)
def test_native_rays_keep_structured_diagnostics_for_invalid_counts(
    monkeypatch, count, count_value, conversion_error_type,
) -> None:
    adapter, _calls = _native_ray_adapter(monkeypatch, None, count=count)
    with pytest.raises(RuntimeError, match="nonintegral native intersection count") as error:
        part._native_vertical_segments(adapter, ((100.0, 50.0),), "bad count")
    diagnostics = _native_ray_diagnostics(error)
    assert diagnostics.items() >= {
        "raw_type": "NoneType",
        "reported_count": count_value,
        "reported_count_type": type(count).__name__,
        "raw_length": None,
        "expected_record_width": 9,
        "options": 5,
        "ray_count": 1,
    }.items()
    if conversion_error_type is not None:
        assert diagnostics["conversion_error_type"] == conversion_error_type
        assert type(error.value.__cause__).__name__ == conversion_error_type


def test_native_rays_bound_diagnostics_without_repr_or_conversion_of_unknown_count(monkeypatch) -> None:
    class UnprintableCount:
        def __repr__(self):
            raise AssertionError("unknown count must not be repr-ed")

        def __int__(self):
            raise AssertionError("unknown count must not be coerced")

    raw = tuple(range(10000))
    adapter, _calls = _native_ray_adapter(monkeypatch, raw, count=UnprintableCount())
    with pytest.raises(RuntimeError, match="nonintegral native intersection count") as error:
        part._native_vertical_segments(adapter, ((100.0, 50.0),), "unknown count")
    diagnostics = _native_ray_diagnostics(error)
    assert diagnostics["reported_count"] == "<UnprintableCount>"
    assert diagnostics["reported_count_type"] == "UnprintableCount"
    assert diagnostics["raw_type"] == "tuple"
    assert diagnostics["raw_length"] == 10000
    assert len(str(error.value)) < 1000


def test_native_rays_bound_conversion_diagnostics_without_dumping_native_values(monkeypatch) -> None:
    from traceback import format_exception

    native_value = "unbounded native normal " * 10000
    raw = _native_ray_hit(0, 0.0, 16, normal=(0.0, native_value, 0.0))
    adapter, _calls = _native_ray_adapter(monkeypatch, raw, count=1)
    with pytest.raises(RuntimeError, match="malformed native ray-intersection record") as error:
        part._native_vertical_segments(adapter, ((100.0, 50.0),), "large native value")
    diagnostics = _native_ray_diagnostics(error)
    assert diagnostics["field_index"] == 7
    assert diagnostics["field_type"] == "str"
    assert diagnostics["conversion_error_type"] == "ValueError"
    formatted = "".join(format_exception(error.value))
    assert "unbounded native normal" not in formatted
    assert len(formatted) < 5000


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


def _breakthrough_adapter(
    monkeypatch, *, tag="FootScrewHoles", cylinder=None, closest=None, faces=True,
):
    """Behavioral native-interface doubles, never a claim of a native build."""
    from types import SimpleNamespace

    _tag, seat, stations, _envelope = next(group for group in part.THROUGH_SEAT_GROUPS if group[0] == tag)
    radius = part.blind_cut_dia_mm(seat) / 2.0
    cylinder_faces = []
    cylinder_points = []

    def closest_point(*point):
        cylinder_points.append(point)
        return (*point, 0.0, 0.0) if closest is None else closest

    for x, z in stations:
        params = (x / 1000.0, 0.0, z / 1000.0, 0.0, 1.0, 0.0, radius / 1000.0)
        surface = SimpleNamespace(IsCylinder=lambda: True, CylinderParams=params if cylinder is None else cylinder)
        cylinder_faces.append(SimpleNamespace(
            GetSurface=lambda surface=surface: surface,
            GetClosestPointOn=closest_point,
        ))
    body = SimpleNamespace(GetFaces=lambda: tuple(cylinder_faces) if faces else ())
    model = SimpleNamespace(GetBodies2=lambda *_args: (body,))
    monkeypatch.setattr(part, "_early_bound", lambda obj, _interface: obj)
    return SimpleNamespace(currentModel=model, cylinder_points=cylinder_points)


def test_native_through_proof_requires_open_bore_and_real_wall_positive_controls(monkeypatch) -> None:
    adapter = _breakthrough_adapter(monkeypatch)
    seen = []

    def rays(_adapter, points, label):
        seen.append((label, len(points)))
        if label.endswith("breakthrough"):
            return tuple(() for _point in points)
        return tuple(((0.0, fr_harmonic_base_spec.POCKET_SKIN),) for _point in points)

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
        lambda _a, points, label: tuple(
            () if label.endswith("breakthrough") else ((0.0, fr_harmonic_base_spec.POCKET_SKIN),)
            for _point in points
        ),
    )
    with pytest.raises(RuntimeError, match="cylinder"):
        part._verify_through_breakthrough(adapter, "FootScrewHoles", part.FOOT_SEAT_SPEC, part.FOOT_SCREW_XZ)


@pytest.mark.parametrize(
    ("tag", "seat", "stations", "envelope"), part.THROUGH_SEAT_GROUPS,
    ids=[group[0] for group in part.THROUGH_SEAT_GROUPS],
)
def test_native_contract_proves_all_eighteen_skin_only_exits_and_transfer_probes(
    monkeypatch, tag, seat, stations, envelope,
) -> None:
    adapter = _breakthrough_adapter(monkeypatch, tag=tag)
    seen = {}

    def rays(_adapter, points, label):
        seen[label] = points
        return tuple(
            () if label.endswith("breakthrough") else ((0.0, fr_harmonic_base_spec.POCKET_SKIN),)
            for _point in points
        )

    monkeypatch.setattr(part, "_native_vertical_segments", rays)
    part._verify_uncut_material(adapter, tag, seat, stations)
    part._verify_through_breakthrough(adapter, tag, seat, stations)
    assert seen[tag] == tuple(stations) + part._material_probe_points(seat, stations, envelope)
    assert len(seen[tag]) == len(stations) * (81 if envelope != (0.0, 0.0) else 17)
    assert len(seen[f"{tag} breakthrough"]) == len(stations) * 16
    assert seen[f"{tag} wall control"] == part._material_probe_points(seat, stations)
    assert len(adapter.cylinder_points) == 48 * len(stations)
    skin = fr_harmonic_base_spec.POCKET_SKIN
    assert {round(part.STACK_HEIGHT - 1000.0 * point[1], 6) for point in adapter.cylinder_points} == {
        0.05, round(skin / 2.0, 6), round(skin - 0.05, 6),
    }
    radius = part.THREAD_MAJOR_MM[seat.size] / 2.0
    for x, z in stations:
        for ex in (-envelope[0], envelope[0]):
            for ez in (-envelope[1], envelope[1]):
                assert any(
                    radius < math.dist((x + ex, z + ez), point) < radius + 0.051
                    for point in seen[tag]
                )


@pytest.mark.parametrize(
    ("tag", "seat", "stations", "envelope", "station_index"),
    [(tag, seat, stations, envelope, index)
     for tag, seat, stations, envelope in part.THROUGH_SEAT_GROUPS
     for index in range(len(stations))],
    ids=[f"{tag}-{index}" for tag, _seat, stations, _envelope in part.THROUGH_SEAT_GROUPS
         for index in range(len(stations))],
)
@pytest.mark.parametrize("stage", ("uncut", "wall"))
def test_native_contract_rejects_off_axis_rib_or_fillet_metal_at_every_seat(
    monkeypatch, tag, seat, stations, envelope, station_index, stage,
) -> None:
    adapter = _breakthrough_adapter(monkeypatch, tag=tag)

    def interrupted(_adapter, points, label):
        if label.endswith("breakthrough"):
            return tuple(() for _point in points)
        result = [((0.0, fr_harmonic_base_spec.POCKET_SKIN),) for _point in points]
        # Keep every axis correct; put extra retained metal on the first
        # circumference probe for the selected station, including transfers.
        stride = 80 if envelope != (0.0, 0.0) and stage == "uncut" else 16
        start = len(stations) if stage == "uncut" else 0
        result[start + station_index * stride] = (
            (0.0, fr_harmonic_base_spec.STACK_HEIGHT - fr_harmonic_base_spec.RIB_RELIEF),
        )
        return tuple(result)

    monkeypatch.setattr(part, "_native_vertical_segments", interrupted)
    with pytest.raises(RuntimeError, match="actual material"):
        if stage == "uncut":
            part._verify_uncut_material(adapter, tag, seat, stations)
        else:
            part._verify_through_breakthrough(adapter, tag, seat, stations)


def test_native_rib_sketch_and_equations_place_the_actual_shifted_cross_rib() -> None:
    """Run only the real local sketch helpers and rib loop against recorders.

    This proves the emitted profile, native dimension measurements, equation
    dependencies and offset extrusion, not a SolidWorks rebuild or print.
    """
    import ast
    import asyncio
    import inspect
    import operator
    from types import SimpleNamespace

    build = ast.parse(inspect.getsource(part.build)).body[0]
    helper_names = {"_table_origin", "_from_origin", "_pad"}
    helpers = [node for node in build.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name in helper_names]
    assert {node.name for node in helpers} == helper_names
    loops = [node for node in build.body if isinstance(node, ast.For)
             and isinstance(node.target, ast.Tuple)
             and [getattr(item, "id", None) for item in node.target.elts]
             == ["tag", "rib_shape", "label", "names", "drives", "location_drives"]]
    assert len(loops) == 1
    initializers = [node for node in build.body
                    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Await)
                    and isinstance(node.value.value, ast.Call)
                    and getattr(node.value.value.func, "id", None) == "set_global"
                    and len(node.value.value.args) >= 2
                    and isinstance(node.value.value.args[1], ast.Constant)
                    and node.value.value.args[1].value == "CrossRibCenterX"]
    assert len(initializers) == 1
    module = ast.parse(
        "async def record(adapter):\n"
        "    drive_jobs = []\n"
        "    hung = ()\n"
        "    after = 0.0\n"
        "    return drive_jobs\n"
    )
    wrapper = module.body[0]
    wrapper.body = [*wrapper.body[:3], *helpers, *initializers, loops[0], wrapper.body[-1]]
    ast.fix_missing_locations(module)
    profiles, anchors, extrusions, verified, dimensions = [], [], [], [], {}
    globals_mm = {
        "BottomLength": part.BOTTOM_LENGTH, "BottomWidth": part.BOTTOM_WIDTH,
        "TopLength": part.TOP_LENGTH, "TopWidth": part.TOP_WIDTH,
        "PocketWall": part.POCKET_WALL, "RibThickness": part.RIB_THICKNESS,
        "RibRelief": part.RIB_RELIEF, "PocketDepth": part.POCKET_CEILING_Y,
    }

    def result(data=None):
        return SimpleNamespace(is_success=True, data=data, error=None)

    class Manager:
        AddToDB = False

        def CreatePoint(self, x, y, z):
            assert self.AddToDB
            assert (x, y, z) == pytest.approx(
                (-part.BOTTOM_LENGTH / 2000.0, -part.BOTTOM_WIDTH / 2000.0, 0.0),
            )
            return (x, y, z)

    class Adapter:
        currentSketchManager = Manager()

        def _register_sketch_entity(self, kind, raw):
            assert kind == "Point" and raw is not None
            return "table-origin"

        async def create_sketch(self, plane):
            assert plane == "Top"
            return result()

        async def add_sketch_constraint(self, _first, second, kind):
            assert second is None and kind in ("horizontal", "vertical")
            return result()

        async def exit_sketch(self):
            return result()

    class RecordedDimensions:
        def __init__(self):
            self.rows = []

        def record(self, name, drive):
            self.rows.append((name, drive))

        def apply(self, _adapter, feature):
            dimensions[feature] = dict(self.rows)
            return [(f"{name}@{feature}", drive) for name, drive in self.rows]

    async def set_global(_adapter, name, expression):
        assert expression.endswith("mm")
        globals_mm[name] = float(expression[:-2])

    async def chain(_adapter, points):
        profiles.append(points)
        return [f"line{len(profiles)}-{index}" for index in range(4)]

    async def dimension(_adapter, first, second, kind, span, _label):
        points = profiles[-1]
        index = int(first.split("-")[-1].split(".")[0])
        assert second == first.removesuffix(".start") + ".end"
        axis = 0 if kind == "horizontal_distance" else 1
        assert span == pytest.approx(abs(points[(index + 1) % 4][axis] - points[index][axis]))

    async def anchor_origin(_adapter, _point, x, y, _label):
        assert (x, y) == (-part.BOTTOM_LENGTH / 2.0, -part.BOTTOM_WIDTH / 2.0)

    async def anchor(_adapter, first, second, x, y, _label):
        assert first == "table-origin" and second.endswith("-0.start")
        assert (x, y) == pytest.approx(
            (profiles[-1][0][0] + part.BOTTOM_LENGTH / 2.0,
             profiles[-1][0][1] + part.BOTTOM_WIDTH / 2.0),
        )
        anchors.append((x, y))

    async def fully_defined(_adapter, _label):
        return None

    async def volume(_adapter, _label, expected, _tolerance):
        return expected

    namespace = {
        **vars(part), "SketchDims": RecordedDimensions, "set_global": set_global,
        "add_line_chain": chain, "dimension_between": dimension,
        "anchor_point_to_origin": anchor_origin, "anchor_point_to_point": anchor,
        "ensure_fully_defined": fully_defined, "volume_check": volume,
        "name_last_feature": lambda *_args: None,
        "name_dimensions": lambda _adapter, feature, names: [f"{name}@{feature}" for name in names],
        "_verify_named_dimension": lambda _adapter, name, value: verified.append((name, value)),
        "extrude_at_offset": lambda _adapter, height, offset: extrusions.append((height, offset)),
    }
    exec(compile(module, "<native rib sketch contract>", "exec"), namespace)
    jobs = dict(asyncio.run(namespace["record"](Adapter())))
    spec = fr_harmonic_base_spec
    left, right = (spec.CROSS_RIB_CENTER_X + sign * spec.RIB_THICKNESS / 2.0 for sign in (-1.0, 1.0))
    assert profiles[1] == [
        (left, -part.RIB_HALF_LENGTH_Z), (right, -part.RIB_HALF_LENGTH_Z),
        (right, part.RIB_HALF_LENGTH_Z), (left, part.RIB_HALF_LENGTH_Z),
    ]
    assert globals_mm["CrossRibCenterX"] == spec.CROSS_RIB_CENTER_X == 11.049
    assert anchors[1] == pytest.approx((234.696, part.BOTTOM_WIDTH / 2.0 - part.RIB_HALF_LENGTH_Z))
    expected = {
        "CrossRibOriginX": part.BOTTOM_LENGTH / 2.0,
        "CrossRibOriginY": part.BOTTOM_WIDTH / 2.0,
        "CrossRibThickness": right - left,
        "CrossRibLength": 2.0 * part.RIB_HALF_LENGTH_Z,
        "CrossRibX": anchors[1][0], "CrossRibY": anchors[1][1],
    }
    operations = {ast.Add: operator.add, ast.Sub: operator.sub,
                  ast.Mult: operator.mul, ast.Div: operator.truediv}

    def evaluate(node):
        if isinstance(node, ast.Constant):
            return globals_mm[node.value] if isinstance(node.value, str) else node.value
        if isinstance(node, ast.BinOp):
            return operations[type(node.op)](evaluate(node.left), evaluate(node.right))
        raise AssertionError(f"unsupported native equation: {ast.dump(node)}")

    assert set(dimensions["CrossRibProfile"]) == set(expected)
    for name, value in expected.items():
        expression = jobs[f"{name}@CrossRibProfile"]
        assert evaluate(ast.parse(expression, mode="eval").body) == pytest.approx(value)
    globals_mm["CrossRibCenterX"] += 3.0
    assert evaluate(ast.parse(jobs["CrossRibX@CrossRibProfile"], mode="eval").body) == pytest.approx(237.696)
    assert extrusions == [(spec.POCKET_CEILING_Y - spec.RIB_RELIEF, spec.RIB_RELIEF)] * 2
    assert dict(verified)["CrossRibHeight@CrossRib"] == pytest.approx(34.798)
    assert dict(verified)["CrossRibRelief@CrossRib"] == spec.RIB_RELIEF


def test_shifted_cross_rib_volume_and_all_eighteen_skin_only_cut_footprints() -> None:
    spec = fr_harmonic_base_spec
    skin = spec.STACK_HEIGHT - spec.POCKET_CEILING_Y
    rib = spec.STACK_HEIGHT - spec.RIB_RELIEF
    seat = part.FOOT_SEAT_SPEC
    area = math.pi * (part.FOOT_SCREW_HOLE_DIA / 2.0) ** 2
    for x, depth in (
        (0.0, skin), (spec.CROSS_RIB_CENTER_X, rib),
        (spec.CROSS_RIB_CENTER_X - spec.RIB_THICKNESS / 2.0, (skin + rib) / 2.0),
        (spec.CROSS_RIB_CENTER_X + spec.RIB_THICKNESS / 2.0, (skin + rib) / 2.0),
    ):
        assert part._through_holes_volume_mm3(seat, ((x, 50.0),)) == pytest.approx(
            area * depth, rel=2e-4,
        )
    counted = 0
    for tag, seat, stations, _envelope in part.THROUGH_SEAT_GROUPS:
        expected = len(stations) * math.pi * (part.blind_cut_dia_mm(seat) / 2.0) ** 2 * skin
        assert part._through_holes_volume_mm3(seat, stations) == pytest.approx(
            expected, rel=2e-4,
        ), tag
        counted += len(stations)
    assert counted == 18
    # The moved rectangle still crosses the long rib and reaches both walls;
    # only the shared 10x10 patch is subtracted from its hanging volume.
    cross_volume = part.hanging_volume(
        (part.CROSS_RIB_SHAPE,), (part.LONG_RIB_SHAPE,), spec.RIB_RELIEF,
    )
    expected_cross = (
        2.0 * spec.POCKET_HALF_Z * spec.RIB_THICKNESS - spec.RIB_THICKNESS**2
    ) * (spec.POCKET_CEILING_Y - spec.RIB_RELIEF)
    assert cross_volume == pytest.approx(expected_cross)
    assert cross_volume == pytest.approx(82985.6554)


@pytest.mark.parametrize(
    ("tag", "seat", "stations", "station_index"),
    [pytest.param(tag, seat, stations, index, id=f"{tag}-{index}")
     for tag, seat, stations, _envelope in part.THROUGH_SEAT_GROUPS
     for index in range(len(stations))],
)
def test_native_cylinder_proof_rejects_a_single_missing_exit_wall_sector_at_every_seat(
    monkeypatch, tag, seat, stations, station_index,
) -> None:
    adapter = _breakthrough_adapter(monkeypatch, tag=tag)
    x, z = stations[station_index]
    radius = part.blind_cut_dia_mm(seat) / 2.0
    angle = 0.071 + 15.0 * math.tau / 16.0
    target = (
        (x + radius * math.cos(angle)) / 1000.0,
        (fr_harmonic_base_spec.POCKET_CEILING_Y + 0.05) / 1000.0,
        (z + radius * math.sin(angle)) / 1000.0,
    )

    def trimmed(*point):
        if math.dist(point, target) < 1e-10:
            return (point[0], point[1] + 0.001, point[2], 0.0, 0.0)
        return (*point, 0.0, 0.0)

    body = adapter.currentModel.GetBodies2(0, False)[0]
    for face in body.GetFaces():
        face.GetClosestPointOn = trimmed
    monkeypatch.setattr(
        part, "_native_vertical_segments",
        lambda _adapter, points, label: tuple(
            () if label.endswith("breakthrough") else ((0.0, fr_harmonic_base_spec.POCKET_SKIN),)
            for _point in points
        ),
    )
    with pytest.raises(RuntimeError, match="missing retained tap-drill cylinder"):
        part._verify_through_breakthrough(adapter, tag, seat, stations)


@pytest.mark.parametrize("bad_control", (None, *range(9)))
def test_native_rib_controls_require_full_height_crossing_end_joins_and_open_old_footprint(
    monkeypatch, bad_control,
) -> None:
    spec = fr_harmonic_base_spec
    expected = (
        (11.049, -62.6618, 47.752), (11.049, 62.6618, 47.752),
        (-105.156, 0.0, 47.752), (105.156, 0.0, 47.752),
        (11.049, 0.0, 47.752),
        (11.049, -128.3081, 50.8), (11.049, 128.3081, 50.8),
        (1.143, -62.6618, 12.954), (1.143, 62.6618, 12.954),
    )
    dimensions = {}
    monkeypatch.setattr(
        part, "_verify_named_dimension",
        lambda _adapter, name, value: dimensions.__setitem__(name, value),
    )

    def rays(_adapter, points, label):
        assert label == "retained rib controls"
        assert [v for point in points for v in point] == pytest.approx(
            [v for x, z, _depth in expected for v in (x, z)], abs=1e-4,
        )
        depths = [depth for _x, _z, depth in expected]
        if bad_control is not None:
            depths[bad_control] = spec.POCKET_SKIN if depths[bad_control] > 13.0 else 47.752
        return tuple(((0.0, depth),) for depth in depths)

    monkeypatch.setattr(part, "_native_vertical_segments", rays)
    if bad_control is None:
        part._verify_rib_material(object())
    else:
        with pytest.raises(RuntimeError, match="actual material"):
            part._verify_rib_material(object())
    assert dimensions == pytest.approx({
        "CrossRibX@CrossRibProfile": 234.696,
        "CrossRibThickness@CrossRibProfile": 9.906,
        "CrossRibLength@CrossRibProfile": 262.5852,
        "CrossRibHeight@CrossRib": 34.798,
        "CrossRibRelief@CrossRib": 3.048,
    })


def _native_r7_sheet(index=0):
    """Unmodified native audit/PDF ink, not an invented after-fix drawing."""
    import json
    from pathlib import Path

    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "fr_harmonic_base_r7.json").read_text(encoding="utf-8"),
    )
    assert fixture["source_head"] == "17c7cf25ff5201c53f1a2a7d8bc12924d1b0f208"
    assert fixture["coordinate_quantum_m"] == 1e-7
    return fixture["sheets"][index]


def _native_r7_annotation(dump, name, view_index=0):
    matches = [item for item in dump["views"][view_index]["annotations"] if item["name"] == name]
    assert len(matches) == 1
    return matches[0]


def _native_r7_geometry():
    from _layout_audit import sheet_model

    return sheet_model(_native_r7_sheet()).geometry


def _native_r7_named(geometry, prefix):
    matches = [item for item in geometry.annotations if item.label.startswith(prefix)]
    assert len(matches) == 1, prefix
    return matches[0]


def _native_r7_callouts():
    """All five complete native display arrays; no R5 coordinates substituted."""
    import draw_fr_harmonic_base as sheet

    dump = _native_r7_sheet()
    identities = (
        ("MHA-DT-18 block transfer", 0, "RD1"),
        ("MHA-DT-02 pedestal transfer", 0, "RD2"),
        ("MHA-DT-24 spring transfer", 0, "RD3"),
        ("MHA-FR-04 nameplate transfer", 0, "RD4"),
        ("MHA-FR-VN-53 cross-tap", 1, "RD1"),
    )
    boxes, lines, rows = {}, {}, {}
    for label, view_index, name in identities:
        item = _native_r7_annotation(dump, name, view_index)
        data = item["display"]
        lines[label] = [tuple(row[4:6] + row[7:9]) for row in data["lines"]]
        texts = [(row["t"], row["pos"], row["h"]) for row in data["texts"]]
        boxes[label] = sheet.callout_text_box(item["pos"], lines[label], texts, label)
        rows[label] = sheet.callout_text_rows(lines[label], texts, label)
    assert len(boxes) == 5
    return boxes, lines, rows


def test_native_r7_records_both_west_tag_strikes_and_the_interior_y_block() -> None:
    from _layout_geometry import Box
    import draw_fr_harmonic_base as sheet

    geometry = _native_r7_geometry()
    # This is the projected DECK west straight edge, not GetOutline padding.
    deck_x = sheet.HOLE_TOP_CENTER[0] - fr_harmonic_base_spec.DECK_HALF_X * sheet.VIEW_SCALE / 1000.0
    assert deck_x == pytest.approx(0.238217)
    deck_edge = (deck_x, 0.164, deck_x, 0.226)
    for prefix in ("note DetailItem446 ", "note DetailItem447 "):
        tag = _native_r7_named(geometry, prefix)
        assert len(tag.text_boxes) == 1
        box = tag.text_boxes[0]
        assert sheet.segment_crosses_box(deck_edge, (box.xmin, box.ymin, box.xmax, box.ymax))
    y = _native_r7_named(geometry, "dim PivotSeatY ")
    assert len(y.text_boxes) == 2  # value AND the native ABOVE flag
    part_box = Box(0.22285, 0.1591, 0.33715, 0.2309)
    for box in y.text_boxes:
        assert part_box.xmin < box.xmin < box.xmax < part_box.xmax
        assert part_box.ymin < box.ymin < box.ymax < part_box.ymax
    assert sheet.find_callout_clashes(
        {"native R7 PivotSeatY row " + str(i): (box.xmin, box.ymin, box.xmax, box.ymax)
         for i, box in enumerate(y.text_boxes)},
        {"actual part": (part_box.xmin, part_box.ymin, part_box.xmax, part_box.ymax)},
    )


def _conditional_r7_exterior_layout():
    """Conditional envelopes only: the next native audit must prove the routes.

    Text envelopes union R7 PDF ink with its native unleadered extent and add
    0.1 mm on each edge (larger than the dump's 0.1 um coordinate quantum).
    A socket route is bounded by the hull of the ENTIRE unchanged bore rim and
    that text envelope: never translate a leader's physical hole end.
    """
    from dataclasses import replace
    from _layout_geometry import Box, Segment
    import draw_fr_harmonic_base as sheet

    dump = _native_r7_sheet()
    geometry = _native_r7_geometry()
    replacements, tag_envelopes = {}, {}
    west = sorted(
        (xz for xz in sheet.COLUMN_SOCKET_XZ if xz[0] < 0.0),
        key=lambda xz: -xz[1],
    )
    for station, name in zip(west, ("DetailItem446", "DetailItem447"), strict=True):
        raw = _native_r7_annotation(dump, name)
        annotation = _native_r7_named(geometry, f"note {name} ")
        x, y = sheet.HOLE_TAG_STATION_POSITIONS[station]
        dx, dy = x - raw["pos"][0], y - raw["pos"][1]
        moved = tuple(
            Box(box.xmin + dx, box.ymin + dy, box.xmax + dx, box.ymax + dy)
            for box in annotation.text_boxes
        )
        extent = raw["note"]["extent"]
        assert not raw.get("leaders")  # only these R7 extents may be translated
        text = Box(extent[0] + dx, extent[1] + dy, extent[3] + dx, extent[4] + dy)
        for box in moved:
            text = text.union(box)
        text = Box(text.xmin - 0.0001, text.ymin - 0.0001, text.xmax + 0.0001, text.ymax + 0.0001)
        cx, cy = sheet._plan_xy(*station, center=sheet.HOLE_TOP_CENTER)
        radius = sheet.COLUMN_SOCKET_DIAMETER * sheet.VIEW_SCALE / 2000.0
        rim = Box(cx - radius, cy - radius, cx + radius, cy + radius)
        route = text.union(rim)
        tag_envelopes[annotation.label] = (text, route)
        # This candidate is only a control inside that envelope. The envelope
        # checks below also cover either shoulder side and every rim endpoint.
        leader = Segment(
            text.xmax, text.ymax if y < cy else text.ymin,
            cx, cy + (radius if y > cy else -radius), "leader",
        )
        replacements[annotation.label] = replace(
            annotation, text_boxes=moved, segments=(leader,), position=(x, y),
        )

    origin = _native_r7_named(geometry, "note DetailItem467 ")
    dx, dy = sheet.HOLE_ORIGIN_NOTE_XY[0] - 0.165, sheet.HOLE_ORIGIN_NOTE_XY[1] - 0.186
    replacements[origin.label] = replace(
        origin,
        text_boxes=tuple(Box(b.xmin + dx, b.ymin + dy, b.xmax + dx, b.ymax + dy) for b in origin.text_boxes),
        position=sheet.HOLE_ORIGIN_NOTE_XY,
    )
    original_y = _native_r7_named(geometry, "dim PivotSeatY ")
    raw_y = _native_r7_annotation(dump, "PivotSeatY")
    x, y = sheet.PIVOT_SEAT_Y_TEXT_XY
    dx, dy = x - raw_y["pos"][0], y - raw_y["pos"][1]
    texts = tuple(Box(b.xmin + dx, b.ymin + dy, b.xmax + dx, b.ymax + dy) for b in original_y.text_boxes)
    # R7 establishes the two-row text/shoulder alignment: width 24.5438 mm,
    # lower shoulder 5.5562 mm below the top-centre annotation anchor.
    assert raw_y["display"]["lines"][-1][4:9] == [
        0.2612281, 0.1794438, 0.0, 0.2857719, 0.1794438,
    ]
    native_lines = raw_y["display"]["lines"]
    fixed = tuple(Segment(*row[4:6], *row[7:9]) for row in native_lines[:4])
    shoulder_y = native_lines[-1][5] + dy
    # Text is now WEST of the line. The nearest native shoulder end must be
    # its RIGHT end, not the LEFT end used by the observed east-side text.
    shoulder_right = native_lines[-1][7] + dx
    leader = Segment(0.2616, 0.1705186, shoulder_right, shoulder_y, "leader")
    shoulder = Segment(native_lines[-1][4] + dx, shoulder_y, shoulder_right, shoulder_y, "shoulder")
    replacements[original_y.label] = replace(
        original_y, text_boxes=texts, segments=(*fixed, leader, shoulder), position=(x, y),
    )
    proposed = replace(
        geometry,
        annotations=tuple(replacements.get(a.label, a) for a in geometry.annotations),
    )
    assert len(proposed.annotations) == len(geometry.annotations)
    return geometry, proposed, replacements, tag_envelopes, leader


def test_conditional_r7_layout_couples_all_five_callouts_every_obstacle_and_new_routes() -> None:
    from _layout_audit import (
        find_text_clearance, find_text_separation, find_merged_blocks,
        find_leader_through_text, find_leader_across_lines, find_lines_through_own_text,
    )
    from _layout_geometry import find_leader_crossings, find_text_on_line
    import draw_fr_harmonic_base as sheet

    observed, proposed, changed, envelopes, y_leader = _conditional_r7_exterior_layout()
    callouts, callout_lines, rows = _native_r7_callouts()
    # Keep all native annotations: dimensions/centre marks, all eleven tags,
    # both axes and labels, section arrows/letters, free notes and every table.
    assert len(observed.annotations) == len(proposed.annotations)
    texts = {
        f"{annotation.label} row {index}": (box.xmin, box.ymin, box.xmax, box.ymax)
        for annotation in proposed.annotations
        for index, box in enumerate(annotation.text_boxes)
    }
    obstacles = {
        **sheet.frame_obstacles((proposed.width, proposed.height), proposed.region, (0.216, 0.066)),
        **texts,
        "view holes top": (0.22285, 0.1591, 0.33715, 0.2309),
        "view holes front": (0.22285, 0.08865, 0.33715, 0.10135),
        "view section A-A": (0.369025, 0.0991, 0.381725, 0.1709),
    }
    dump = _native_r7_sheet()
    native_origin = _native_r7_annotation(dump, "DetailItem445")
    obstacles.update(sheet.datum_origin_boxes(native_origin["datum_origin"]["axis"]))
    for view in dump["views"]:
        for section in view.get("sections") or ():
            obstacles.update(sheet.section_line_boxes(
                section["label"], section["arrows"], section["texts"], section["text_height"],
                section["label"], (dump["width"], dump["height"]),
            ))
    # The R7 callout boxes are conservative after dropping only the class
    # token: retain their full original widths/rows/shoulders and all segments.
    callout_prefixes = ("hole-callout RD1 ", "hole-callout RD2 ", "hole-callout RD3 ", "hole-callout RD4 ")
    foreign = {
        name: box for name, box in obstacles.items()
        if not name.startswith(callout_prefixes)
    }
    assert sheet.find_callout_clashes(callouts, foreign) == []
    assert sheet.find_tall_callouts(rows) == []
    assert sheet.find_merged_blocks(callouts) == []
    # Every callout leader and shoulder is checked against the moved rows.
    changed_texts = {
        name: box for name, box in texts.items()
        if any(name.startswith(label + " row ") for label in changed)
    }
    assert sheet.find_leader_crossings(callout_lines, changed_texts) == []
    for label, (text, route) in envelopes.items():
        # Whole-rim/whole-text route envelope against ALL foreign text, table,
        # frame and title-block obstacles. Its own part/landing is not text.
        neighbors = {
            name: box for name, box in obstacles.items()
            if not name.startswith(label + " row ") and not name.startswith("view ")
        }
        assert sheet.find_callout_clashes(
            {label: (route.xmin, route.ymin, route.xmax, route.ymax)}, neighbors,
        ) == []
        if text.ymax < obstacles["view holes top"][1]:
            assert obstacles["view holes top"][1] - text.ymax >= sheet.CALLOUT_CLEARANCE_M
        else:
            # Tags may identify a bore inside the silhouette, but neither
            # nested west outline may strike their complete text.
            pad_west = sheet.HOLE_TOP_CENTER[0] - fr_harmonic_base_spec.TOP_LENGTH * sheet.VIEW_SCALE / 2000.0
            deck_west = sheet.HOLE_TOP_CENTER[0] - fr_harmonic_base_spec.DECK_HALF_X * sheet.VIEW_SCALE / 1000.0
            assert text.xmin - pad_west >= 0.0035
            assert deck_west - text.xmax >= 0.003
    y = next(a for a in proposed.annotations if a.label.startswith("dim PivotSeatY "))
    for box in y.text_boxes:
        assert sheet.box_gap((box.xmin, box.ymin, box.xmax, box.ymax), obstacles["view holes top"]) > 0.002
    foreign_texts = {name: box for name, box in texts.items() if not name.startswith(y.label + " row ")}
    assert sheet.find_leader_crossings(
        {"exterior PivotSeatY": [(y_leader.x0, y_leader.y0, y_leader.x1, y_leader.y1)]}, foreign_texts,
    ) == []
    # All native leaders remain in the shared, unchanged coupled predicates.
    # Do not demand unrelated pre-existing R7 findings disappear.
    for predicate in (
        find_text_clearance, find_text_separation, find_merged_blocks,
        find_leader_through_text, find_leader_across_lines, find_lines_through_own_text,
        find_leader_crossings, find_text_on_line,
    ):
        affected = [
            finding for finding in predicate(proposed)
            if finding.a in changed or finding.b in changed
        ]
        assert affected == []


def test_native_r7_lower_b_failure_and_conditional_real_cut_endpoint_clearance() -> None:
    from dataclasses import replace
    from _layout_audit import sheet_model, find_text_clearance
    from _layout_geometry import Box, Segment, find_text_on_line
    import draw_fr_harmonic_base as sheet

    dump = _native_r7_sheet(1)
    model = sheet_model(dump).geometry
    marker = _native_r7_named(model, "section-line B")
    assert len(marker.text_boxes) == 2
    lower = min(marker.text_boxes, key=lambda box: box.ymin)
    flange_edge = (0.09, 0.1491, 0.20, 0.1491)
    assert sheet.segment_crosses_box(flange_edge, (lower.xmin, lower.ymin, lower.xmax, lower.ymax))
    assert sheet.UNDERSIDE_CUT_X == pytest.approx(
        (part.COLUMN_X + part.SCREW_SPOTFACE_DIAMETER / 2.0 + part.POCKET_HALF_X) / 2.0
    )
    assert sheet.UNDERSIDE_CUT_X == pytest.approx(205.90, abs=0.01)
    dy = sheet.UNDERSIDE_CUT_START_Y - 0.145
    assert dy == pytest.approx(-0.010)
    assert sheet.UNDERSIDE_CUT_END_Y == pytest.approx(0.225)
    moved_lower = Box(lower.xmin, lower.ymin + dy, lower.xmax, lower.ymax + dy)
    assert 0.1491 - moved_lower.ymax > 0.009
    # Every other native sheet-3 row is retained, including PocketLen's value
    # and POCKET caption immediately below the new marker.
    # Move the real lower arrow AND the lower end of the native cutting
    # stroke, keeping the upper arrow/text fixed. This remains conditional
    # on the next native CreateLine/CreateSectionViewAt5 readback.
    lower_y = dump["views"][0]["sections"][0]["arrows"][1]
    segments = tuple(
        Segment(s.x0, s.y0 + (dy if abs(s.y0 - lower_y) < 1e-7 else 0.0),
                s.x1, s.y1 + (dy if abs(s.y1 - lower_y) < 1e-7 else 0.0), s.role)
        for s in marker.segments
    )
    moved = replace(
        marker, text_boxes=tuple(moved_lower if box is lower else box for box in marker.text_boxes),
        segments=segments,
    )
    conditional = replace(model, annotations=tuple(moved if a is marker else a for a in model.annotations))
    for predicate in (find_text_clearance, find_text_on_line):
        assert not [f for f in predicate(conditional) if marker.label in (f.a, f.b)]
    # The actual lower B ink clears PocketLen's value by 2.2268 mm in X
    # despite their overlapping Y intervals. Keep the stricter 2 mm control,
    # not only the shared small-text half-height rule.
    pocket = _native_r7_named(model, "dim PocketLen ")
    value = max(pocket.text_boxes, key=lambda box: box.ymin)
    assert moved_lower.xmin - value.xmax == pytest.approx(0.0022268)
    foreign_text = {
        f"{annotation.label} row {i}": (box.xmin, box.ymin, box.xmax, box.ymax)
        for annotation in model.annotations if annotation.label != moved.label
        for i, box in enumerate(annotation.text_boxes)
    }
    complete_marker = {
        f"B whole ink {i}": (box.xmin, box.ymin, box.xmax, box.ymax)
        for i, box in enumerate(moved.text_boxes)
    }
    complete_marker.update({
        f"B native {segment.role} {i}": (
            min(segment.x0, segment.x1), min(segment.y0, segment.y1),
            max(segment.x0, segment.x1), max(segment.y0, segment.y1),
        )
        for i, segment in enumerate(moved.segments)
    })
    # All these pieces belong to the SAME native section annotation. Its
    # arrows necessarily meet its cutting stroke; they are not independent
    # callouts. Check every constituent against every foreign annotation,
    # excluded by that native owner identity, without testing intentional
    # connections within the marker assembly as callout-to-callout clashes.
    assert moved.label == marker.label
    for part_name, part_box in complete_marker.items():
        assert sheet.find_callout_clashes(
            {f"{moved.label}: {part_name}": part_box}, foreign_text, clearance=0.002,
        ) == []
    # All witnesses, socket, fillet, rib, tables, border and title-block ink
    # remain in the full sheet model above; native annotation strokes are not
    # translated with the section marker.
    for name in ("PocketLen", "PocketFilletRadius", "SocketBossDia", "CrossRibThickness"):
        native = _native_r7_named(model, f"dim {name} ")
        assert any(a is native for a in conditional.annotations)
    # Retain the real helper/API path: move the CUTTING SKETCH endpoint, not
    # a note masquerading as the lower B. Existing orientation proof remains.
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(sheet.build))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    section = next(
        node for node in calls
        if getattr(node.func, "id", None) == "create_section_view"
        and any(k.arg == "section_label" and isinstance(k.value, ast.Constant) and k.value.value == "B" for k in node.keywords)
    )
    keywords = {k.arg: ast.unparse(k.value) for k in section.keywords}
    assert keywords["line_start"] == "(cut_line_x, UNDERSIDE_CUT_START_Y)"
    assert keywords["line_end"] == "(cut_line_x, UNDERSIDE_CUT_END_Y)"
    assert keywords["scale"] == "UNDERSIDE_SECTION_SCALE"
    assert any(getattr(node.func, "id", None) == "_turn_underside_section_clockwise" for node in calls)


def _native_base_tap_class_display(monkeypatch, *, drop_unused_class=False):
    """Exercise the existing native-definition helper without invoking COM."""
    from types import SimpleNamespace
    import _hole_callout_thread_class
    import draw_fr_harmonic_base as sheet

    variables = []
    for name, value in (
        ("hw-threaddesc", "10-32 UNF"),
        ("hw-threadclass", "2B"),
        ("hw-tapdrldia", sheet.BASE_CROSS_TAP_DRILL_DIA),
        ("hw-tapdrldepth", sheet.BASE_CROSS_TAP_SPEC.depth_mm),
        ("hw-threaddepth", sheet.BASE_CROSS_TAP_SPEC.overrides_mm["ThreadDepth"]),
    ):
        variable = SimpleNamespace(VariableName=name, Type=3 if isinstance(value, str) else 1)
        if variable.Type == 3:
            variable.String = value
        else:
            variable.Length = value / 1000.0
            variable.Precision = sheet.CROSS_TAP_CALLOUT_PRECISION[name]
        variable._oleobj_ = variable
        variables.append(variable)

    class NativeDisplay:
        def __init__(self):
            self.definitions = {
                5: "<hw-threaddesc> - <hw-threadclass>",
                6: " <HOLE-DEPTH><hw-threaddepth>",
                7: "<NUM_INST>X <MOD-DIAM><hw-tapdrldia> <HOLE-DEPTH><hw-tapdrldepth>",
                8: "",
            }
            self.variables = variables

        def IsHoleCallout(self):
            return True

        def GetText(self, part):
            if part in self.definitions:
                return self.definitions[part]
            text = self.definitions[part + 4].replace("<NUM_INST>", "2")
            for variable in self.variables:
                value = (
                    variable.String if variable.Type == 3
                    else f"{variable.Length * 1000.0:.{variable.Precision}f}"
                )
                text = text.replace(f"<{variable.VariableName}>", value)
            return text

        def SetText(self, part, text):
            self.definitions[part + 4] = text

        def GetHoleCalloutVariables(self):
            return tuple(
                variable for variable in self.variables
                if not (
                    drop_unused_class
                    and variable.VariableName == "hw-threadclass"
                    and "<hw-threadclass>" not in self.definitions[5]
                )
            )

    monkeypatch.setattr(sheet, "dynamic_dispatch", lambda raw: raw)
    monkeypatch.setattr(sheet, "_early_bound", lambda raw, interface: raw)
    monkeypatch.setattr(_hole_callout_thread_class, "_early_bound", lambda raw, interface: raw)
    return NativeDisplay()


@pytest.mark.parametrize("drop_unused_class", (False, True))
def test_default_class_omission_preserves_quantity_min_depth_native_tokens_and_precision(
    monkeypatch, drop_unused_class,
) -> None:
    import draw_fr_harmonic_base as sheet

    display = _native_base_tap_class_display(monkeypatch, drop_unused_class=drop_unused_class)
    native_values = [
        (v.VariableName, getattr(v, "String", None), getattr(v, "Length", None), getattr(v, "Precision", None))
        for v in display.variables
    ]
    original = dict(display.definitions)
    sheet._set_cross_tap_callout_text(display)
    assert display.GetText(3).startswith("4X ")
    assert display.GetText(7).count("<hw-tapdrldepth> MIN") == 1
    assert all(display.GetText(part) == original[part] for part in (5, 6, 8))
    aggregated = dict(display.definitions)
    sheet._omit_base_callout_thread_class(display, label="actual native tap")
    assert display.GetText(5) == "<hw-threaddesc>"
    assert all(display.GetText(part) == aggregated[part] for part in (6, 7, 8))
    assert not any("2B" in display.GetText(part) for part in (1, 2, 3, 4))
    assert native_values == [
        (v.VariableName, getattr(v, "String", None), getattr(v, "Length", None), getattr(v, "Precision", None))
        for v in display.variables
    ]
    assert all(
        display.GetText(7).count(token) == 1
        for token in ("<hw-tapdrldia>", "<hw-tapdrldepth>", "<MOD-DIAM>", "<HOLE-DEPTH>")
    )
    assert "<hw-threaddepth>" in display.GetText(6)
    sheet._check_cross_tap_callout(display)
    depth = next(v for v in display.variables if v.VariableName == "hw-tapdrldepth")
    depth.Precision = 2
    with pytest.raises(RuntimeError, match="prints 2 decimals, not 3"):
        sheet._check_cross_tap_callout(display)


@pytest.mark.parametrize("native_class", ("2A", "3B", ""))
def test_nondefault_native_class_is_not_silently_erased(monkeypatch, native_class) -> None:
    import draw_fr_harmonic_base as sheet

    display = _native_base_tap_class_display(monkeypatch)
    next(v for v in display.variables if v.VariableName == "hw-threadclass").String = native_class
    before = dict(display.definitions)
    with pytest.raises(RuntimeError, match="title-block-default native class"):
        sheet._omit_base_callout_thread_class(display, label="nondefault tap")
    assert display.definitions == before


def test_class_omission_rejects_a_ghost_literal_and_retained_wrong_model_class(monkeypatch) -> None:
    import draw_fr_harmonic_base as sheet

    display = _native_base_tap_class_display(monkeypatch)
    display.definitions[6] += " 2B"
    with pytest.raises(RuntimeError, match="still prints its class"):
        sheet._omit_base_callout_thread_class(display, label="ghost class")
    display.definitions[6] = display.definitions[6].removesuffix(" 2B")
    next(v for v in display.variables if v.VariableName == "hw-threadclass").String = "2A"
    with pytest.raises(RuntimeError, match="hw-threadclass"):
        sheet._check_cross_tap_callout(display)


def test_all_five_native_callouts_omit_only_after_quantity_and_precision_edits() -> None:
    import ast
    import inspect
    import draw_fr_harmonic_base as sheet

    tree = ast.parse(inspect.getsource(sheet.build))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    omission = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.For)
        and any(
            isinstance(call, ast.Call)
            and getattr(call.func, "id", None) == "_omit_base_callout_thread_class"
            for statement in node.body for call in ast.walk(statement)
        )
    )
    assert [element.elts[1].id for element in omission.iter.elts] == [
        "block_callout", "pedestal_callout", "spring_callout", "nameplate_callout", "tap_callout",
    ]
    aggregate = next(c for c in calls if getattr(c.func, "id", None) == "_set_cross_tap_callout_text")
    precision = next(
        c for c in calls if getattr(c.func, "id", None) == "set_hole_callout_precision"
        and c.args and isinstance(c.args[0], ast.Name) and c.args[0].id == "tap_callout"
    )
    readback = next(c for c in calls if getattr(c.func, "id", None) == "_check_cross_tap_callout")
    assert aggregate.lineno < precision.lineno < omission.lineno < readback.lineno
