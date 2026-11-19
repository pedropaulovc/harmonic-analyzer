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


def test_spotface_band_reaches_the_setter_unchanged() -> None:
    # The band now reads (upper, lower) like every named fit band and goes
    # through deviations(); the setter must still receive (lower, upper) =
    # (0.0, +.020), so the printed limits cannot move.

    from _fit_deviations import deviations

    assert fr_harmonic_base_spec.SPOTFACE_DEPTH_BAND_MM == (0.508, 0.0)
    assert deviations(fr_harmonic_base_spec.SPOTFACE_DEPTH_BAND_MM) == (0.0, 0.508)


E533EF6FD_SPRING_LINES = [
    (0.271602, 0.175848, 0.309959, 0.140112),
    (0.271188, 0.176233, 0.271602, 0.175848),
    (0.309959, 0.140112, 0.229628, 0.140112),
]
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
    ("process_name", "expected_process_rows"),
    [
        ("TRANSFER_BLOCK_CALLOUT", f"TRANSFER FROM MHA-DT-18\nAFTER {step_ref('rig-set')};\n"),
        ("TRANSFER_PEDESTAL_CALLOUT", "TRANSFER FROM MHA-DT-02\nAT ASSEMBLY;\n"),
        ("TRANSFER_SPRING_CALLOUT", f"TRANSFER FROM MHA-DT-24\nAFTER {step_ref('rig-set')};\n"),
        ("CROSS_TAP_PROCESS", "DEPTHS FROM SPOTFACE FLOOR\nFAR WALL ONLY "),
    ],
)
def test_base_callout_prefix_is_the_shared_helpers(
    process_name: str, expected_process_rows: str
) -> None:
    # Main's hb-notes-2 ruling (a): the block and pedestal callouts end their
    # process text with a newline so the 8-32 thread gets its own fourth line;
    # so does the spring's since its step citation outgrew a joined row. The
    # cross-tap's FAR WALL ONLY joins its thread row, as the top frame's does,
    # under the depths' datum row. add_native_hole_callout writes exactly
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
    # compartment (swDimensionTextPrefix = 1) of a hole callout itself. Only
    # _set_dimension_affixes writes it, on named model dimensions (counts and
    # the spotface symbols), never on a hole callout.
    import ast
    import inspect

    import draw_fr_harmonic_base as sheet

    module = ast.parse(inspect.getsource(sheet))
    affix_writer = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_set_dimension_affixes"
    )
    module.body.remove(affix_writer)
    prefix_writes = [
        ast.unparse(node)
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", "") == "SetText"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == 1
    ]
    assert prefix_writes == []
    callers = {
        ast.unparse(node.args[2])
        for node in ast.walk(module)
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_set_dimension_affixes"
    }
    assert callers == {"UNDERSIDE_SECTION_AFFIXES", "HOLE_SIDE_AFFIXES"}


def test_cross_tap_callout_carries_hole_facts_only() -> None:
    # hb-render-4 eye pass: count/drill/depth, the depths' datum and the
    # thread each on a row; the X location is a dimension, not text.

    import draw_fr_harmonic_base as sheet

    assert sheet.CROSS_TAP_PROCESS == "DEPTHS FROM SPOTFACE FLOOR\nFAR WALL ONLY"
    assert "THRU" not in sheet.CROSS_TAP_PROCESS
    # The Hole Wizard seats the taps on the spotface floor, the datum the
    # callout names (two of three machinist reviews asked for it once the
    # near wall became a clearance, run 20261106T172701582Z).
    assert part.BASE_SPOTFACE_PLANE_Z - part.BASE_SPOTFACE_DEPTH == part.BASE_SCREW_SEAT_Z


def test_cross_near_wall_clearance_callout_drills_to_the_socket() -> None:
    # Owner ruling 2026-11-05: the near wall is #10 close clearance drilled
    # into the socket, so the 10-32 is threaded in the far wall only.
    import draw_fr_harmonic_base as sheet
    import fr_harmonic_base_fasteners as fasteners

    spec = fasteners.BASE_CROSS_CLEARANCE_SPEC
    assert (spec.kind, spec.size, spec.fit, spec.end) == (
        "clearance",
        "#10",
        "close",
        "blind",
    )
    # Seat .826 off the socket axis: the drill stops once it opens the socket.
    assert spec.depth_mm == pytest.approx(part.BASE_SCREW_SEAT_Z - 112.014)
    assert sheet.CROSS_TAP_PROCESS.endswith("FAR WALL ONLY")
    native = {
        5: "",
        6: "",
        7: "<NUM_INST>X <MOD-DIAM><hw-diam> <HOLE-DEPTH> <hw-depth>",
        8: "",
    }
    updated = sheet._cross_clearance_callout_definitions(native)
    assert updated[7] == "4X <MOD-DIAM><hw-diam> \nDRILL TO SOCKET"
    with pytest.raises(RuntimeError, match="no single count and blind depth"):
        sheet._cross_clearance_callout_definitions(
            {**native, 7: "<MOD-DIAM><hw-diam> THRU"}
        )


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
    scale = sheet.CROSS_TAP_SHEET_SCALE[0] / sheet.CROSS_TAP_SHEET_SCALE[1]
    view_bottom = sheet.HOLE_SIDE_CENTER[1] - fr_harmonic_base_spec.STACK_HEIGHT * scale / 2000.0
    assert keep["CrossTapFarX"][1] < keep["CrossTapX"][1] < view_bottom
    # 1.244 and 16.756 (flow-through until the column snap: 1.2441 / 16.7559)
    # are also the table's A1/A2 and A3/A4 X LOCs from the same flange edge.
    assert part.BOTTOM_LENGTH / 2.0 - part.COLUMN_X == pytest.approx(1.244 * 25.4, abs=0.003)
    assert part.BOTTOM_LENGTH / 2.0 + part.COLUMN_X == pytest.approx(16.756 * 25.4, abs=0.003)
    # The .XXX baselines print their values only (rule 7): no caption.
    assert not {"CrossTapX", "CrossTapFarX"} & set(sheet.HOLE_SIDE_CALLOUTS)


def test_deck_land_worst_case_is_proven_instead_of_noted() -> None:
    # hb-render-4 eye pass: the MIN land note put a dimension in a note.
    assert not hasattr(fr_harmonic_base_spec, "DRAWING_NOTES")
    # The bore now opens on the green land and reaches the pad's outer edge,
    # whose .06 break (and its general band) is the land's last bite.
    # The nominal follows the column line and the .01-grid pad: 12.4968 / 12.5222
    # once the column snap lands, 12.4992 / 12.5362 before (equal to .005).
    lands = {"x": part.COLUMN_SOCKET_LAND_X, "z": part.COLUMN_SOCKET_LAND_Z}
    assert abs(lands["x"] - lands["z"]) <= 0.0015 * 25.4
    for axis, stack in part.COLUMN_SOCKET_LAND_STACKS.items():
        assert stack["nominal"] == pytest.approx(lands[axis])
        assert stack["nominal"] == pytest.approx(12.5165, abs=0.021)
        assert {name: v for name, v in stack.items() if name != "nominal"} == pytest.approx({
            "flange length": -0.127,
            "pad length": -0.127,
            "bore location": -0.254,
            "matched bore": -0.2492,
            "bore edge break": -0.254,
            "pad edge chamfer": -1.778,
        })
        assert sum(stack.values()) == pytest.approx(stack["nominal"] - 2.7892)
    # The same stack on the rejected 1.6 mm pad land would fail the .040 MIN.
    assert sum(part.column_socket_land_stack(1.6).values()) < part.COLUMN_SOCKET_LAND_MIN
    # Main's rider: the bore ceiling is a functional judgement, so the
    # stack reports how much bore the land could still absorb.
    assert part.COLUMN_SOCKET_BREAK_EVEN_BORE == pytest.approx(43.3832, abs=0.006)
    rejected = part.column_socket_land_stack(1.6)
    assert part.column_socket_break_even_bore(rejected) < part.COLUMN_SOCKET_MATCH_BORE_MAX


def test_review_b2_dimensions_print_xx_and_sit_on_the_01_grid() -> None:
    # Review b2 gated the .XXX widths, pocket width, lug/rib stations and
    # chamfers as over-specification. Each now prints .XX, so its model
    # value must BE the printed .01 value.
    spec = fr_harmonic_base_spec
    places = spec.DRAWING_PRECISION
    for feature, name in (
        ("BottomProfile", "BottomWid"),
        ("TopProfile", "TopWid"),
        ("DeckProfile", "DeckWid"),
        ("PocketProfile", "PocketWid"),
        ("DeckEdgeBreak", "DeckEdgeChamfer"),
        ("TopRimBreaks", "TopRimChamfer"),
        ("BottomEdgeBreak", "BottomEdgeChamfer"),
        ("BaseSpotFaceRearProfile", "SpotFaceDia"),
        ("LongRibProfile", "LongRibY"),
        *(("CrossTapLugProfile", n) for n in ("Lug1X", "Lug3X", "Lug1Y", "Lug0Y")),
    ):
        assert places[feature][name] == 2, name
    printed = {
        "BottomWid": (spec.BOTTOM_WIDTH, 11.31),
        "TopWid": (spec.TOP_WIDTH, 10.81),
        "DeckWid": (spec.DECK_WIDTH, 10.25),
        "PocketWid": (2.0 * spec.POCKET_HALF_Z, 9.87),
        "DeckEdgeChamfer": (spec.DECK_EDGE_BREAK, 0.03),
        "RimChamfer": (part.RIM_CHAMFER, 0.06),
        "SpotFaceDia": (part.SCREW_SPOTFACE_DIAMETER, 0.35),
        "Lug1X": (part.BOTTOM_LENGTH / 2.0 - spec.CROSS_TAP_LUG_INNER_X, 1.56),
        "Lug3X": (part.BOTTOM_LENGTH / 2.0 + spec.CROSS_TAP_LUG_INNER_X, 16.44),
        "Lug1Y": (spec.BOTTOM_WIDTH / 2.0 - spec.CROSS_TAP_LUG_INNER_Z, 2.70),
        "Lug0Y": (spec.BOTTOM_WIDTH / 2.0 + spec.CROSS_TAP_LUG_INNER_Z, 8.61),
        "LongRibY": (spec.BOTTOM_WIDTH / 2.0 - part.LONG_RIB_SHAPE[4], 5.46),
    }
    for name, (model_mm, inches) in printed.items():
        assert model_mm == pytest.approx(inches * 25.4, abs=1e-9), name
    # The pad's equal-land width is 10.808 exactly; the .01 pad leaves the
    # lands within .0015 of each other, under half a .01 step.
    assert abs(part.COLUMN_SOCKET_LAND_X - part.COLUMN_SOCKET_LAND_Z) <= 0.005 * 25.4


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


def test_stamped_id_is_located_from_x0_y0_with_a_character_height() -> None:
    # novice-rubric screen 20261107T081227004Z (blocker): APPROX AS SHOWN on a
    # DO NOT SCALE sheet located the stamp by words only, with no height.
    import draw_fr_harmonic_base as sheet

    # Owner decision 2026-11-19 (#3124, item 1): the note names the set.
    assert sheet.SERIAL_NOTE == 'STAMP "2"\n1/8 FIGURE STAMP'
    rows = sheet.SERIAL_NOTE.split("\n")
    x0, top = sheet.SERIAL_NOTE_XY
    box = (
        x0,
        top - len(rows) * sheet.NOTE_ROW_M,
        x0 + max(map(len, rows)) * sheet.NOTE_CHAR_M,
        top,
    )
    # The note stands off the part (rule 14, run 20261107T121814924Z): below
    # the plan's rear edge, above the X reference row, left of the X
    # dimension's extension line at the serial, its leader reaching it.
    serial = sheet._plan_xy(*part.SERIAL_XZ)
    rear_edge_y = sheet._plan_xy(0.0, fr_harmonic_base_spec.BOTTOM_REAR_Z)[1]
    assert box[3] < rear_edge_y - 0.003
    assert box[1] > sheet.SERIAL_X_TEXT_XY[1] + 0.003
    assert box[2] < serial[0] - 0.004
    assert math.dist((box[2], box[3]), serial) < 0.015
    # X runs on a third baseline row below DeckX, Y right of the plan, its
    # text below the flange's rear edge and left of the moved chamfer text.
    corner = sheet._plan_xy(-part.BOTTOM_LENGTH / 2.0, fr_harmonic_base_spec.BOTTOM_REAR_Z)
    deck_x_row = sheet.GEOMETRY_TOP_KEEP["DeckX"][1]
    assert deck_x_row - 0.0080 < sheet.SERIAL_X_TEXT_XY[1] < deck_x_row - 0.0058
    assert corner[0] < sheet.SERIAL_X_TEXT_XY[0] < serial[0]
    plan_right, _y = sheet._plan_xy(part.BOTTOM_LENGTH / 2.0, 0.0)
    assert plan_right < sheet.SERIAL_Y_LINE_X < sheet.GEOMETRY_TOP_KEEP["DeckWid"][0]
    assert sheet.SERIAL_Y_TEXT_XY[1] < corner[1] - 0.003
    # One row above the chamfer's three-row block, which hangs from its value.
    assert sheet.SERIAL_Y_TEXT_XY[1] - 0.002 > sheet.SIDE_KEEP["DeckEdgeChamfer"][1] + 0.002


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


def test_socket_note_two_is_flagged_from_the_rows_under_note_one() -> None:
    # novice-rubric screen 20261107T081227004Z: the six-line leader note on A2
    # broke rule 7's two lines, named MHA-FR-03 while the rows named MHA-FR-02,
    # and used ASSIGNED / MATCH MARKS. Note 2 names both parts once.
    import draw_fr_harmonic_base as sheet

    note = sheet.socket_note(["A1", "A2", "A3", "A4"])
    rows = note.split("\n")
    assert rows[0].startswith("2. A1-A4: MATCHED FIT TO MHA-FR-03 TUBE: SLIDES IN BY HAND")
    # #2386: the pattern is carried from the top frame, so its X/Y are reference.
    assert "TRANSFER FROM MHA-FR-02" in rows[1]
    assert "X/Y" in rows[1]
    assert len(rows) == 2
    for word in ("ASSIGNED", "MATCH MARKS"):
        assert word not in note
    with pytest.raises(ValueError):
        sheet.socket_note(["A1"])
    assert set(sheet.HOLE_TABLE_ROW_NOTES[station] for station in part.COLUMN_SOCKET_XZ) == {
        "SEE NOTE 2"
    }
    # Under note 1's rows, left of the title block (x 0.215).
    pivot_rows = sheet.pivot_seat_step("D1").count("\n") + 1
    assert sheet.SOCKET_NOTE_XY[0] == sheet.PIVOT_SEAT_NOTE_XY[0]
    assert sheet.SOCKET_NOTE_XY[1] <= sheet.PIVOT_SEAT_NOTE_XY[1] - (pivot_rows + 1) * sheet.NOTE_ROW_M
    width = max(len(row.replace("<MOD-DIAM>", "D")) for row in rows) * sheet.NOTE_CHAR_M
    assert sheet.SOCKET_NOTE_XY[0] + width < 0.215


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
        prefix, suffix = sheet.UNDERSIDE_SECTION_AFFIXES.get(name, ("", ""))
        return [f"{prefix}00.0{suffix}"]

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
    assert set(sheet.UNDERSIDE_SECTION_AFFIXES) <= set(texts)


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
    # The outside texts' widest row includes a count prefix.
    widest = max(
        len(f"{prefix}00.0{suffix}")
        for prefix, suffix in sheet.UNDERSIDE_SECTION_AFFIXES.values()
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
    # The bosses are cut on the sockets' own stations, so the callout ties
    # each boss to its socket rather than leaving the arcs unlocated (PR
    # #2702 proof, machinist review): the coaxiality the sheet states is the
    # model's.
    boss_callout = callouts["SocketBossDia"]
    assert boss_callout.startswith(f"{len(part.SOCKET_BOSS_SHAPES)}X SOCKET BOSSES")
    assert "COAXIAL WITH SOCKETS" in boss_callout
    assert len(boss_callout.splitlines()) <= 2
    assert [(x, z) for _kind, x, z, _r in part.SOCKET_BOSS_SHAPES] == list(spec.COLUMN_SOCKET_XZ)
    boss_x, _boss_y = sheet.UNDERSIDE_BOTTOM_KEEP["SocketBossDia"]
    boss_half_w = max(map(len, boss_callout.splitlines())) * _NOTE_CHAR_MM / 2000.0
    assert boss_x + boss_half_w < sheet._bottom_xy(-spec.BOTTOM_LENGTH / 2.0, 0.0)[0] - 0.003
    assert callouts["PocketFilletRadius"] == f"{part.POCKET_FILLET_COUNT}X POCKET\nCORNERS"
    # Counts, not words, on section B-B's heights (rule 7).
    assert sheet.UNDERSIDE_SECTION_AFFIXES == {"LugBottom": ("4X ", ""), "RibRelief": ("2X ", "")}
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
    label = "BOTTOM VIEW"
    boxes["note"] = (nx, ny - _NOTE_LINE_MM / 1000.0, nx + len(label) * _NOTE_CHAR_MM / 1000.0, ny)
    for a in boxes:
        for b in boxes:
            if a < b:
                assert _box_gap(boxes[a], boxes[b]) > 0.0015, (a, b)
    # The cross rib's text reads west of the rib, clear above the B arrow.
    rib_west = sheet._bottom_xy(part.CROSS_RIB_SHAPE[1], 0.0)[0]
    assert boxes["CrossRibThickness"][2] < rib_west - 0.005


def test_drawing_keeps_partition_the_part_precision_map() -> None:
    # assert_imported_precision proves every printed dimension at the end of
    # the build; the keeps must name each shown map entry exactly once.
    import draw_fr_harmonic_base as sheet

    keeps = (
        sheet.GEOMETRY_TOP_KEEP,
        sheet.SIDE_KEEP,
        sheet.SECTION_KEEP,
        sheet.HOLE_SIDE_KEEP,
        sheet.UNDERSIDE_BOTTOM_KEEP,
        sheet.UNDERSIDE_LUGS_KEEP,
        sheet.UNDERSIDE_SECTION_TEXT_MM,
    )
    names = [name for keep in keeps for name in keep]
    assert len(names) == len(set(names))
    assert set(names) == set(sheet.SHOWN_PRECISION_BY_NAME)
    # Only D1's spec-owned offsets stay off the print (MHA-DT-00 check).
    assert set(fr_harmonic_base_spec.DRAWING_PRECISION_BY_NAME) - set(names) == set(
        fr_harmonic_base_spec.PIVOT_SEAT_DIMENSIONS
    )
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
    # witness lines end 0.5 mm past it, clear above the stamped-ID X
    # reference's text on the next baseline row (~1.8 mm half height).
    assert keep["DeckX"][1] - 0.0028 - 0.0005 > sheet.SERIAL_X_TEXT_XY[1] + 0.0018 + 0.0015
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
    assert sheet.UNDERSIDE_SECTION_AFFIXES["LugBottom"] == ("4X ", "")
    # novice-rubric screen 20261107T081227004Z: sheet 4's LUG BOTTOMS pointer
    # deferred to section B-B, which already defines the level.
    assert not hasattr(sheet, "LUGS_LEVEL_NOTES")
    assert sheet.LUGS_NOTE == "BOTTOM VIEW"


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
    labelled = {"note": note, **boxes}
    for label, box in {"view": view, **labelled}.items():
        assert _BORDER_INNER_M[0] + 0.002 < box[0], label
        assert _BORDER_INNER_M[1] + 0.002 < box[1], label
        assert box[2] < _BORDER_INNER_M[2] - 0.002, label
        assert box[3] < _BORDER_INNER_M[3] - 0.002, label
        assert _box_gap(box, _TITLE_BLOCK_M) > 0.002, label
    for label, box in boxes.items():
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


def test_rig_callouts_cite_the_drive_train_rig_set_step() -> None:
    # User ruling P1-2: the rig seats are spotted only after the rig is set.
    # plate-r1 review (over-specification): the five-line RIG SET procedure
    # was an assembly set-up for other parts, so it lives on MHA-DT-00 and
    # each rig callout cites that step by key, never a typed number. The
    # pedestal seats are not rig seats.

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


# The note's printed character advance and line pitch at the sheet's 3.5 text
# height (read off the pc-p1 render of the old RIG SET note).
_NOTE_CHAR_MM = 2.69
_NOTE_LINE_MM = 4.58


def test_numbered_note_and_wider_flags_predict_clearance_in_the_proven_lanes() -> None:
    import draw_fr_harmonic_base as sheet

    assert sheet.PIVOT_SEAT_NOTE_XY == (0.020, 0.100)
    assert sheet.HOLE_TAG_STATION_POSITIONS[sheet.PIVOT_SCREW_XZ] == (0.2456, 0.1550)
    # The front cross-tap view and its spotface callout now sit on sheet 5,
    # so neither is this sheet-2 note's neighbour any longer.
    assert sheet.HOLE_SIDE_KEEP["SpotFaceDia"] == (0.062, 0.200)

    # Native-r4 embedded-font calibration supplies conservative NEW text-width
    # estimates. This is not a claim that numbered note 1 has printed natively.
    row_widths = (0.0930785, 0.0973665, 0.0665752)
    pitch = 0.0045257
    x, y = sheet.PIVOT_SEAT_NOTE_XY
    note = (x, y - len(row_widths) * pitch, x + max(row_widths), y - pitch + 0.0035)
    neighbors = {
        "table": (0.018, 0.1630628306, 0.1627633865, 0.260),
        "plan": (0.22285, 0.1591, 0.33715, 0.2309),
        "title block": _TITLE_BLOCK_M,
    }
    for label, box in neighbors.items():
        assert _box_gap(note, box) >= 0.0035, label
    assert note[0] - _BORDER_INNER_M[0] >= 0.0035
    assert note[1] - _BORDER_INNER_M[1] >= 0.0035


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
    # D1's banded offsets are an MHA-DT-00 check, not print dimensions.
    assert not any(getattr(node.func, "id", None) == "_flag_pivot_seat_dimensions" for node in calls)
    assert not hasattr(sheet, "HOLE_TOP_KEEP")
    assert not any(getattr(node.func, "attr", None) == "SetText2" for node in calls)


def test_pivot_offsets_are_unbanded_references_off_the_print() -> None:
    import draw_fr_harmonic_base as sheet

    spec = fr_harmonic_base_spec
    near = min(part.PEDESTAL_SCREW_XZ, key=lambda xz: math.dist(xz, part.PIVOT_SCREW_XZ))
    assert part.PIVOT_NEAR_PEDESTAL_XZ == near
    assert part.PIVOT_SEAT_OFFSETS_MM == pytest.approx(
        (part.PIVOT_SCREW_XZ[0] - near[0], near[1] - part.PIVOT_SCREW_XZ[1])
    )
    names = set(spec.PIVOT_SEAT_DIMENSIONS)
    assert names == spec.DRAWING_DIMENSIONS["PivotSeatReference"]
    # Run 20261107T191011860Z: D1 is transferred from the MHA-DT-20 bore at
    # MHA-DT-00 step 23, so the drawing imports neither offset.
    assert not names & set(sheet.SHOWN_PRECISION_BY_NAME)
    assert spec.DRAWING_PRECISION["PivotSeatReference"] == dict.fromkeys(names, 3)


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
    # (1.88 - .01) - (1.50 + .01) - (.350 + .01) / 2 = .180.
    assert land == pytest.approx(
        ((1.88 - 0.01) - (1.50 + 0.01) - (0.350 + 0.01) / 2.0) * 25.4
    )
    assert land >= spec.CROSS_SCREW_TOP_LAND_MIN_MM == WALL_TARGET_MM


def test_base_blanks_its_reference_sketches_through_the_shared_helper() -> None:
    # Main (restricted review of #858): one blanking helper in _sketch, traced
    # like every other per-operation helper, and no local copy in the base.

    import _sketch

    assert set(part.REFERENCE_SKETCHES) == {
        "HeightReference", "CrossTapReference", "PlanReference", "PivotSeatReference"
    }
    assert hasattr(_sketch.blank_reference_sketches, "__wrapped__")


def test_section_rib_relief_counts_both_ribs() -> None:
    # plate-r5 review: B-B cuts only the long rib, so the cross rib's level
    # was in no view. Both ribs' reliefs are driven by "RibRelief", so the
    # one printed height counts both (2X, a count rather than words: rule 7).

    import draw_fr_harmonic_base as sheet

    assert sheet.UNDERSIDE_SECTION_AFFIXES["RibRelief"] == ("2X ", "")


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
    import _ha_harmonic_analyzer_interference as contracts

    assert fr_harmonic_base_fasteners.PEDESTAL_SCREW_ENGAGEMENT == pytest.approx(13.97)
    for xz in part.PEDESTAL_SCREW_XZ:
        assert fr_harmonic_base_fasteners.retained_material_segments_mm(*xz)[0] == pytest.approx((0.0, 12.954))
    allowed = contracts.ALLOWED_PAIRS
    expected = 1.10 * math.pi / 4.0 * (4.1656**2 - 3.454**2) * 12.954
    obsolete = 1.10 * math.pi / 4.0 * (4.1656**2 - 3.454**2) * 14.05
    for number in (1, 2):
        pair = frozenset((
            f"dt-drive-train-1/dt-vn-pedestal-hold-down-screw-{number}",
            "fr-frame-1/fr-harmonic-base-1",
        ))
        assert allowed[pair] == pytest.approx(expected)
        assert allowed[pair] < obsolete


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
    assert cross_volume == pytest.approx(83003.1666)


def test_spotface_depth_is_a_plain_counted_control_under_one_callout() -> None:
    # Run 20261117T111407559Z (2/3): '4X <spot> <depth> .169 +.020/.000' in
    # section A-A read as a second spotface callout without its diameter.
    # Sheet 5 holds the one callout (size, REF depth, mate); A-A keeps only
    # the banded depth and its count, the count above the value so the row
    # stays inside the right border (run 20261107T121814924Z, 3/3).
    import draw_fr_harmonic_base as sheet

    assert sheet.SECTION_ABOVE_CALLOUTS == {"SpotFaceDepth": "4X"}
    prefix, suffix = sheet.HOLE_SIDE_AFFIXES["SpotFaceDia"]
    assert prefix == "4X <HOLE-SPOT> <MOD-DIAM>"
    assert suffix == f" <HOLE-DEPTH> {sheet.SPOTFACE_DEPTH_REF}"
    assert sheet.HOLE_SIDE_CALLOUTS == {"SpotFaceDia": "SEATS MHA-FR-VN-53"}
    assert sheet.SECTION_KEEP["SpotFaceDepth"][0] <= 0.3845
