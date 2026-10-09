"""Source-only regressions for the seated, correlated cone support enclosure."""
from __future__ import annotations

import itertools
import math

import pytest

import cone_line
import dt_cone_support_pose as pose


def test_nominal_pose_uses_machine_pivot_and_live_axis():
    origin, unit = pose.collar_pose_frame(0.0)
    assert origin == pytest.approx(cone_line.CONE_ORIGIN)
    assert unit == pytest.approx((cone_line.SIN_I, 0.0, cone_line.COS_I))
    for angle in pose.P1_SWEEP_DEG:
        origin, unit = pose.collar_pose_frame(angle)
        pivot_axis_point = tuple(origin[i] + cone_line.PIVOT_STATION * unit[i] for i in range(3))
        assert pivot_axis_point == pytest.approx((pose.PIVOT_xyz[0], cone_line.Y_DRIVE, pose.PIVOT_xyz[2]))


def test_common_translation_never_becomes_independent_tilt(monkeypatch):
    movement = pose._Motion("shared fixture shift", 0.7, (0.0, 0.0, 1.0))
    monkeypatch.setattr(pose, "_support_motions", lambda _angle: ([movement], [], []))
    short = pose.collar_z_closure_terms_mm(10.0, 11.0, 1.0)
    long = pose.collar_z_closure_terms_mm(100.0, 180.0, 19.0)
    assert sum(short.values()) == pytest.approx(0.7)
    assert sum(long.values()) == pytest.approx(0.7)
    assert long["two-support normalization remainder"] == 0.0


def test_normalization_bound_encloses_exact_two_support_corners(monkeypatch):
    axes = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    p_terms = [pose._Motion(f"P{i}", 0.1, axis) for i, axis in enumerate(axes)]
    t_terms = [pose._Motion(f"T{i}", 0.2, axis) for i, axis in enumerate(axes)]
    monkeypatch.setattr(pose, "_support_motions", lambda _angle: ([], p_terms, t_terms))
    _, u = pose.collar_pose_frame(0.0)
    station = cone_line.POST_STATION + 0.9 * pose._SUPPORT_SPAN
    lever, radius = station - cone_line.POST_STATION, 8.0
    for normal in (*axes, (1.0 / math.sqrt(3.0),) * 3):
        budget = sum(pose.collar_projection_closure_terms_mm(station, station, radius, normal).values())
        nominal_radial = radius * math.sqrt(max(0.0, 1.0 - pose._dot(normal, u) ** 2))
        for signs in itertools.product((-1.0, 1.0), repeat=6):
            p = tuple(0.1 * value for value in signs[:3])
            t = tuple(0.2 * value for value in signs[3:])
            chord = tuple(pose._SUPPORT_SPAN * u[i] + t[i] - p[i] for i in range(3))
            actual_u = tuple(value / pose._norm(chord) for value in chord)
            centre_delta = tuple(p[i] + lever * (actual_u[i] - u[i]) for i in range(3))
            actual_radial = radius * math.sqrt(max(0.0, 1.0 - pose._dot(normal, actual_u) ** 2))
            exact_change = abs(pose._dot(normal, centre_delta)) + max(0.0, actual_radial - nominal_radial)
            assert exact_change <= budget + 1e-12


def test_endplay_is_geometric_outer_bound_not_a_new_fit_grade():
    lower, upper = pose.platform_geometric_endplay_interval_mm()
    assert lower == 0.0
    assert upper == pytest.approx(pose.pivot.SHOULDER_LEN + pose.pivot.SHOULDER_LEN_BAND[0])
    assert upper > pose.plate.PIVOT_BEARING_RELIEF_DEPTH


def test_global_crank_requires_the_consumers_actual_z_station():
    post_z = cone_line.cone_station(cone_line.POST_STATION)[2]
    at_post = pose.crank_axis_global_xy_bounds(post_z)
    far = pose.crank_axis_global_xy_bounds(post_z - 100.0)
    assert at_post["nominal_xy_mm"] == pytest.approx((cone_line.X_CRANK, cone_line.Y_CRANK))
    assert far["nominal_xy_mm"] == pytest.approx(at_post["nominal_xy_mm"])
    assert far["upper_xy_mm"][0] > at_post["upper_xy_mm"][0]
    base_relative = pose.crank_axis_global_xy_bounds(post_z, relative_to_base=True)
    assert base_relative["upper_xy_mm"][1] < at_post["upper_xy_mm"][1]
    assert base_relative["centre_xyz_half_width_mm"][1] > pose.post.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM


def test_projection_rejects_nonunit_normal():
    with pytest.raises(ValueError, match="unit normal"):
        pose.collar_projection_closure_terms_mm(10.0, 20.0, 1.0, (0.0, 0.0, 2.0))


def test_global_cock_uses_actual_crank_lands_and_its_own_fit(monkeypatch):
    z = cone_line.cone_station(cone_line.POST_STATION)[2] - 60.0
    original = pose.crank_axis_global_xy_bounds(z)
    assert pose._CRANK_FLOAT == pytest.approx(pose.crankshaft.JOURNAL_DIAMETRAL_CLEARANCE_MM[1] / 2.0)
    assert original["foot_anchor_displacement_mm"] > 0.0
    assert original["seated_face_premise"] == pose.SEATED_FACE_PREMISE
    monkeypatch.setattr(pose.crankshaft, "JOURNAL_SUPPORT_SPAN_MIN_MM",
                        pose.crankshaft.JOURNAL_SUPPORT_SPAN_MIN_MM / 2.0)
    shorter_contact = pose.crank_axis_global_xy_bounds(z)
    assert shorter_contact["direction_angle_bound_rad"] > original["direction_angle_bound_rad"]
    assert shorter_contact["upper_xy_mm"][0] > original["upper_xy_mm"][0]


def test_actual_shaft_inspection_intersects_complete_source_domains():
    acceptance = pose.InstalledAxisAcceptance((0.10, 0.23, 0.10), 0.001)
    station = acceptance.station_mm
    for normal in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
        source = pose.collar_projection_closure_terms_mm(station, station + 3.0, 4.0, normal)
        inspected = pose.installed_axis_projection_terms_mm(
            acceptance, station, station + 3.0, 4.0, normal,
        )
        intersection = pose.collar_projection_closure_terms_mm(
            station, station + 3.0, 4.0, normal, installed=acceptance,
        )
        assert intersection in (source, inspected)
        assert sum(intersection.values()) == pytest.approx(min(sum(source.values()), sum(inspected.values())))
        assert inspected["actual pivot transport remainder"] == 0.0
    assert pose.cone_axis_angle_bound_rad(installed=acceptance) <= acceptance.direction_angle_rad


def test_inspection_does_not_double_charge_engaged_hardware(monkeypatch):
    acceptance = pose.InstalledAxisAcceptance((0.10, 0.23, 0.10), 0.001)
    arguments = (acceptance, acceptance.station_mm, acceptance.station_mm + 3.0, 4.0, (0.0, 0.0, 1.0))
    original = pose.installed_axis_projection_terms_mm(*arguments)
    monkeypatch.setattr(pose, "seated_pivot_axis_offset_terms_mm", lambda: {"large unknown coaxiality": 20.0})
    assert pose.installed_axis_projection_terms_mm(*arguments) == original
    moved = pose.installed_axis_projection_terms_mm(*arguments, angle_deg=3.0)
    assert moved["actual pivot transport remainder"] > 0.0


def test_installed_direction_bounds_exact_finite_material_rotation():
    acceptance = pose.InstalledAxisAcceptance((0.10, 0.23, 0.10), 0.001)
    _, u = pose.collar_pose_frame(0.0)
    theta = acceptance.direction_angle_rad
    c, s = math.cos(theta), math.sin(theta)
    actual_u = (c * u[0] + s * u[2], 0.0, -s * u[0] + c * u[2])
    for normal in ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)):
        lever, radius = 100.0, 9.0
        terms = pose.installed_axis_projection_terms_mm(
            acceptance, acceptance.station_mm, acceptance.station_mm + lever,
            radius, normal,
        )
        delta = lever * abs(pose._dot(normal, tuple(a - b for a, b in zip(actual_u, u))))
        delta += radius * max(
            0.0,
            math.sqrt(max(0.0, 1.0 - pose._dot(normal, actual_u) ** 2))
            - math.sqrt(max(0.0, 1.0 - pose._dot(normal, u) ** 2)),
        )
        assert delta <= (
            terms["installed shaft direction at material lever"]
            + terms["installed shaft directional radial growth"] + 1e-12
        )


@pytest.mark.parametrize("widths,angle", [
    ((0.0, 0.1, 0.1), 0.001),
    ((0.1, 0.1, 0.1), 0.0),
    ((math.nan, 0.1, 0.1), 0.001),
    ((0.1, 0.1), 0.001),
])
def test_inspection_refuses_zero_or_missing_physical_limits(widths, angle):
    with pytest.raises(ValueError, match="finite positive"):
        pose.InstalledAxisAcceptance(widths, angle)


def test_global_crank_is_not_a_mesh_station_release():
    bounds = pose.crank_axis_global_xy_bounds(-155.7, relative_to_base=True)
    assert bounds["crank_mesh_qualified"] is False
    assert "not an actual3D mesh qualification" in bounds["qualification"]
    assert "not stock inspection evidence" in bounds["installed_joint_scope"]


def test_source_support_uses_real_cone_journal_contact_span():
    assert pose._CONE_BORE_LENGTH_MIN == pose.shaft.JOURNAL_SUPPORT_SPAN_MIN_MM
    assert pose._CONE_BORE_LENGTH_MIN < pose.post.CONE_BOSS_LENGTH
    assert pose._SHAFT_IN_POST_ANGLE_RAD == pytest.approx(
        math.atan(pose.shaft.JOURNAL_DIAMETRAL_CLEARANCE_MM[1] / pose.shaft.JOURNAL_SUPPORT_SPAN_MIN_MM)
    )


def test_manufactured_p1_requires_positive_stock_and_unbroken_fence():
    import dt_cone_swing_platform_geometry as geometry

    result = geometry.manufactured_p1_stop_enclosure()
    assert result["angle_interval_deg"][1] > result["nominal_disengage_deg"]
    assert result["positive_head_core_radius_mm"] > 0.0
    assert min(result["unbroken_fence_margins_mm"].values()) > 0.0
    assert result["source_offset_terms_mm"]["connected head/thread offset"] > 0.0
    assert result["source_offset_terms_mm"]["connected shoulder/thread offset"] > 0.0
    assert {"lock notch", "pivot/relief", "tip hold-down", "west post tap", "east post tap"} <= set(result["unbroken_fence_margins_mm"])
    assert pose.P1_SWEEP_DEG == result["angle_interval_deg"]


def test_manufactured_p1_refuses_zero_height_stop(monkeypatch):
    import dt_cone_swing_platform_geometry as geometry

    monkeypatch.setattr(geometry.stop_stock, "UNSLOTTED_HEAD_HEIGHT_MIN_MM", 0.0)
    with pytest.raises(ValueError, match="positive unbroken"):
        geometry.manufactured_p1_stop_enclosure()


def test_manufactured_p1_books_real_hole_coordinate_grades(monkeypatch):
    import dt_cone_swing_platform_geometry as geometry

    initial = geometry.manufactured_p1_stop_enclosure()
    monkeypatch.setattr(geometry, "_GENERAL_2PL_MM", geometry._GENERAL_2PL_MM + 0.05)
    looser = geometry.manufactured_p1_stop_enclosure()
    assert looser["angle_interval_deg"][1] >= initial["angle_interval_deg"][1]
    assert looser["source_offset_terms_mm"]["base stop and pivot coordinate errors"] > initial["source_offset_terms_mm"]["base stop and pivot coordinate errors"]


def test_bank_thrust_grade_requires_actual_indicated_span():
    acceptance = pose.BankThrustAcceptance(0.05, 24.2)
    assert acceptance.direction_angle_rad == pytest.approx(math.atan(0.05 / 24.2))
    with pytest.raises(ValueError, match="positive TIR"):
        pose.BankThrustAcceptance(0.0, 24.2)
    with pytest.raises(ValueError, match="positive TIR"):
        pose.BankThrustAcceptance(0.05, math.nan)
    with pytest.raises(ValueError, match="positive TIR"):
        pose.BankThrustAcceptance(0.05, 0.01)


def test_crank_relative_fcf_does_not_become_a_cone_angle_grade(monkeypatch):
    initial = pose.cone_axis_angle_bound_rad()
    monkeypatch.setattr(pose.post, "CRANK_BORE_ANGULARITY_MM", 100.0)
    monkeypatch.setattr(pose.post, "CRANK_BORE_ANGLE_LIMIT_DEG", 45.0)
    assert pose.cone_axis_angle_bound_rad() == initial


def test_two_support_inspection_derives_actual_running_axis_not_post_axis():
    widths = (0.04, 0.04, 0.04)
    terminal_station = cone_line.POST_STATION + 180.0
    result = pose.installed_axis_from_support_inspections(widths, widths, terminal_station)
    error = 2.0 * math.sqrt(sum(value**2 for value in widths)) + pose._JOURNAL_FLOAT
    assert result.direction_angle_rad == pytest.approx(math.atan(error / (180.0 - error)))
    assert result.station_mm == pose.shaft.TIP_COLLAR_START_STATION
    assert all(width > 0.0 for width in result.xyz_half_width_mm)
    _, u = pose.collar_pose_frame(0.0)
    lever = result.station_mm - cone_line.POST_STATION
    for signs in itertools.product((-1.0, 1.0), repeat=6):
        for radial_axis in range(3):
            p = [widths[i] * signs[i] for i in range(3)]
            p[radial_axis] += pose._JOURNAL_FLOAT
            t = tuple(widths[i] * signs[i + 3] for i in range(3))
            chord = tuple(180.0 * u[i] + t[i] - p[i] for i in range(3))
            actual_u = tuple(value / pose._norm(chord) for value in chord)
            delta = tuple(p[i] + lever * (actual_u[i] - u[i]) for i in range(3))
            assert all(abs(value) <= limit + 1e-12 for value, limit in zip(delta, result.xyz_half_width_mm))


def test_support_observations_include_metrology_and_resolve_two_points():
    with pytest.raises(ValueError, match="finite positive XYZ"):
        pose.installed_axis_from_support_inspections((0.0, 0.04, 0.04), (0.04,) * 3, 140.0)
    with pytest.raises(ValueError, match="resolve the shaft direction"):
        pose.installed_axis_from_support_inspections((0.04,) * 3, (0.04,) * 3, cone_line.POST_STATION)


def test_global_crank_direction_follows_both_retained_supports(monkeypatch):
    initial = pose.crank_axis_global_xy_bounds(-155.7, relative_to_base=True)
    original = pose._support_motions

    def larger_tip_motion(angle):
        common, post_terms, tip_terms = original(angle)
        tip_terms.append(pose._Motion("larger actual tip support uncertainty", 0.1))
        return common, post_terms, tip_terms

    monkeypatch.setattr(pose, "_support_motions", larger_tip_motion)
    larger = pose.crank_axis_global_xy_bounds(-155.7, relative_to_base=True)
    assert larger["direction_angle_bound_rad"] > initial["direction_angle_bound_rad"]
    assert larger["upper_xy_mm"][0] > initial["upper_xy_mm"][0]


def test_nominal_crank_reader_is_not_blocked_by_uncertainty_refusal(monkeypatch):
    def refusing_outer(_angle):
        raise ValueError("deliberately unresolved uncertainty outer")

    monkeypatch.setattr(pose, "_support_motions", refusing_outer)
    at_chain = pose.crank_axis_nominal_xy_mm(-155.7)
    assert at_chain == pytest.approx((cone_line.X_CRANK, cone_line.Y_CRANK))
    swung = pose.crank_axis_nominal_xy_mm(-155.7, 3.0)
    farther = pose.crank_axis_nominal_xy_mm(-175.7, 3.0)
    assert farther[0] - swung[0] == pytest.approx(-20.0 * math.tan(math.radians(3.0)))
    assert farther[1] == swung[1]
    with pytest.raises(ValueError, match="parallel"):
        pose.crank_axis_nominal_xy_mm(-155.7, 90.0)


def test_local_pose_export_charges_origin_translation_without_material_rotation(monkeypatch):
    acceptance = pose.InstalledAxisAcceptance((0.10, 0.23, 0.10), 0.001)
    frame = (
        (cone_line.COS_I, 0.0, cone_line.SIN_I),
        (0.0, 1.0, 0.0),
        (-cone_line.SIN_I, 0.0, cone_line.COS_I),
    )
    calls = []

    def projected(south, north, radius, normal, *, installed):
        calls.append((south, north, radius, normal, installed))
        return {"complete selected intersection": float(len(calls))}

    monkeypatch.setattr(pose, "collar_projection_closure_terms_mm", projected)
    result = pose.cone_axis_local_pose_enclosure(100.0, frame, installed=acceptance)
    assert result["translation_intervals_mm"] == ((-1.0, 1.0), (-2.0, 2.0), (-3.0, 3.0))
    assert all(call[:3] == (100.0, 100.0, 0.0) for call in calls)
    assert tuple(call[3] for call in calls) == tuple(tuple(row[i] for row in frame) for i in range(3))
    assert all(call[4] is acceptance for call in calls)
    assert result["installed_axis_acceptance"]["xyz_half_width_mm"] == acceptance.xyz_half_width_mm
    assert result["material_clock_observed"] is False
    assert result["shortest_transport_euler_intervals_rad"] == ((-0.001, 0.001),) * 3


def test_local_pose_export_rejects_wrong_axis_or_nonorthogonal_frame():
    with pytest.raises(ValueError, match="north shaft axis"):
        pose.cone_axis_local_pose_enclosure(100.0, ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
    with pytest.raises(ValueError, match="orthonormal"):
        pose.cone_axis_local_pose_enclosure(100.0, ((2.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))


def test_radial_projection_uses_direction_not_isotropic_radius_angle():
    axis = (0.0, 0.0, 1.0)
    radius, angle = 8.0, 0.01
    assert pose.radial_projection_growth_mm(radius, (1.0, 0.0, 0.0), axis, angle) == 0.0
    assert pose.radial_projection_growth_mm(radius, axis, axis, angle) == pytest.approx(radius * math.sin(angle))
    normal = (math.sin(0.4), 0.0, math.cos(0.4))
    assert pose.radial_projection_growth_mm(radius, normal, axis, angle) == pytest.approx(
        radius * (math.sin(0.4 + angle) - math.sin(0.4))
    )


def test_full_north_motion_observation_is_not_a_tight_axis_box():
    observation = pose.InstalledSupportMotionAcceptance(
        (0.025, 0.23, 0.025), (0.025, 0.23, 0.025),
        0.55, cone_line.POST_STATION + 180.0, 0.25,
    )
    transverse = (cone_line.COS_I, 0.0, -cone_line.SIN_I)
    terms = pose.installed_support_projection_terms_mm(
        observation, observation.north_station_mm, observation.north_station_mm,
        8.0, transverse,
    )
    assert terms["correlated north motion and axial material travel"] == pytest.approx(0.55)
    assert terms["two-support radial-frame rotation"] == pytest.approx(0.0, abs=1e-12)
    assert terms["two-support normalization remainder"] > 0.0
    assert terms["actual pivot transport remainder"] == 0.0
    post_terms = pose.installed_support_projection_terms_mm(
        observation, cone_line.POST_STATION, cone_line.POST_STATION,
        0.0, (0.0, 1.0, 0.0),
    )
    assert post_terms["actual post running radial fit"] == pytest.approx(pose._JOURNAL_FLOAT)
    assert post_terms["correlated north motion and axial material travel"] == 0.0
    assert observation.direction_angle_rad == pytest.approx(
        math.atan(observation.relative_error_mm / (180.0 - observation.relative_error_mm))
    )


def test_motion_observation_intersects_whole_source_and_survives_local_export():
    observation = pose.InstalledSupportMotionAcceptance(
        (0.025, 0.23, 0.025), (0.025, 0.23, 0.025),
        0.55, cone_line.POST_STATION + 180.0, 0.25,
    )
    arguments = (100.0, 105.0, 8.0, (0.0, 0.0, 1.0))
    source = pose.collar_projection_closure_terms_mm(*arguments)
    observed = pose.installed_support_projection_terms_mm(observation, *arguments)
    selected = pose.collar_projection_closure_terms_mm(*arguments, installed=observation)
    assert selected in (source, observed)
    assert sum(selected.values()) == pytest.approx(min(sum(source.values()), sum(observed.values())))
    frame = (
        (cone_line.COS_I, 0.0, cone_line.SIN_I),
        (0.0, 1.0, 0.0),
        (-cone_line.SIN_I, 0.0, cone_line.COS_I),
    )
    exported = pose.cone_axis_local_pose_enclosure(100.0, frame, installed=observation)
    assert exported["installed_axis_acceptance"]["north_radial_motion_max_mm"] == 0.55
    assert exported["material_clock_observed"] is False


def test_motion_observation_rejects_zero_motion_or_unresolved_span():
    with pytest.raises(ValueError, match="positive resolved span"):
        pose.InstalledSupportMotionAcceptance((0.025,) * 3, (0.025,) * 3, 0.0, 140.0, 0.25)
    with pytest.raises(ValueError, match="positive resolved span"):
        pose.InstalledSupportMotionAcceptance((0.025,) * 3, (0.025,) * 3, 0.55, cone_line.POST_STATION, 0.25)


@pytest.mark.parametrize("radial,coefficient,travel", [
    (0.55, 1.0, 0.25), (0.10, 1.0, 0.25),
    (0.10, -1.0, 0.25), (0.0, 1.0, 0.25),
])
def test_correlated_motion_support_encloses_stroke_without_max_adding(radial, coefficient, travel):
    bound = pose.correlated_north_motion_support_mm(radial, coefficient, travel)
    for fraction in (0.0, 0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0):
        actual = coefficient * travel * fraction + radial * math.sqrt(1.0 - fraction)
        assert actual <= bound + 1e-12
    assert bound <= radial + max(0.0, coefficient * travel)
    if radial > 0.0 and coefficient > 0.0:
        assert bound < radial + coefficient * travel


def test_correlated_motion_support_exact_interior_maximum():
    radial, coefficient, travel = 0.1, 1.0, 0.25
    q = travel * (1.0 - (radial / (2.0 * coefficient * travel)) ** 2)
    assert pose.correlated_north_motion_support_mm(radial, coefficient, travel) == pytest.approx(
        coefficient * q + radial * math.sqrt(1.0 - q / travel)
    )


def test_correlated_material_travel_enters_both_complete_enclosures():
    observation = pose.InstalledSupportMotionAcceptance(
        (0.025,) * 3, (0.025,) * 3, 0.55,
        cone_line.POST_STATION + 180.0, 0.25,
    )
    arguments = (100.0, 105.0, 8.0, (0.0, 0.0, 1.0))
    coefficient = 1.0
    source = pose.collar_projection_closure_terms_mm(*arguments)
    source["axial material travel outer bound"] = coefficient * observation.axial_travel_max_mm
    observed = pose.installed_support_projection_terms_mm(
        observation, *arguments, axial_closing_coefficient=coefficient,
    )
    selected = pose.collar_projection_closure_terms_mm(
        *arguments, installed=observation, axial_closing_coefficient=coefficient,
    )
    assert selected in (source, observed)
    assert sum(selected.values()) == pytest.approx(min(sum(source.values()), sum(observed.values())))
    with pytest.raises(ValueError, match="support motion acceptance"):
        pose.collar_projection_closure_terms_mm(*arguments, axial_closing_coefficient=coefficient)
