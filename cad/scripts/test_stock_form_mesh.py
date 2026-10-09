"""Independent geometric controls for finite-form contact (no CAD/config imports).

The square control uses the elementary separating-axis answer, not the mesh
engine's event finder.  The conjugate control uses the textbook line-of-action
length ONLY for gears whose actual masters equal their physical counts.  Stock
fixtures deliberately cannot satisfy that condition.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import acos, cos, hypot, pi, sin, sqrt
from types import SimpleNamespace

import numpy as np
import pytest

from stock_form_cutter import CutterTemplate, StockFormProfile
from stock_form_mesh import (
    MeshCertificationError,
    _Boundary,
    _MaterialEngine,
    _NormalFeature,
    _finite_segment_distances,
    _handover_displacement,
    _polygon_overlap,
    _support_primitives,
    _vertex_name,
    _working,
    analyse_planar_mesh,
    planar_contact,
    supported_branch_coverage,
    supported_flank_coverage,
)


@pytest.fixture(scope="module")
def stock_pair():
    return (
        StockFormProfile(32, CutterTemplate(26, 48, 20), 8.815, 1.5875),
        StockFormProfile(120, CutterTemplate(55, 48, 20), 32.22, 17.197916666666668),
        (32 + 120) * (25.4 / 48) / 2 + 0.35,
    )


def _rotate(point, angle):
    x, y = point
    return np.array((cos(angle) * x - sin(angle) * y,
                     sin(angle) * x + cos(angle) * y))


def test_exact_conjugate_control_has_true_contact_ratio_and_zero_te():
    module = 25.4 / 48
    ta, tb = CutterTemplate(26, 48, 20), CutterTemplate(55, 48, 20)
    a = StockFormProfile(26, ta, ta.tip_radius_mm, 0.0)
    b = StockFormProfile(55, tb, tb.tip_radius_mm, 0.0)
    centre = a.pitch_radius_mm + b.pitch_radius_mm
    report = analyse_planar_mesh(a, b, centre)
    # Independent involute line-of-action construction, valid for this control.
    pa = 20 * pi / 180
    expected = (sqrt(a.blank_radius_mm**2 - ta.base_radius_mm**2)
                + sqrt(b.blank_radius_mm**2 - tb.base_radius_mm**2)
                - centre * sin(pa)) / (pi * module * cos(pa))
    assert report.is_conjugate
    assert abs(report.coverage - expected) <= report.numerical_error_bounds["coverage"]
    assert max(map(abs, report.transmission_error_driven_rad)) < 1e-12
    assert report.uncovered_phase_rad == 0
    assert report.numerical_error_bounds["uncovered_phase_rad"] == 0
    assert report.support_uncertain_phase_rad == 0
    assert report.unsupported_contact_samples_rad == ()
    assert report.qualified_continuous_contact
    assert report.handover_jump_mm == 0


def test_general_material_engine_recovers_positive_backlash_conjugate_control():
    ta, tb = CutterTemplate(26, 48, 20), CutterTemplate(55, 48, 20)
    a = StockFormProfile(26, ta, ta.tip_radius_mm, 0.0)
    b = StockFormProfile(55, tb, tb.tip_radius_mm, 0.0)
    centre = a.pitch_radius_mm + b.pitch_radius_mm + 0.1
    working = acos((ta.base_radius_mm + tb.base_radius_mm) / centre)
    nominal = 20 * pi / 180
    inv_working = sin(working) / cos(working) - working
    inv_nominal = sin(nominal) / cos(nominal) - nominal
    expected_backlash = 2 * centre * (inv_working - inv_nominal)
    engine = _MaterialEngine(a, b, centre, 0.0, 0.0, 0.001)
    rows = [engine.contact_at(j * a.angular_pitch_rad / 9) for j in range(9)]
    for row in rows:
        assert abs(row.backlash_mm - expected_backlash) <= 2 * row.phase_error_rad * engine.operating_radius
    signed_te = [row.driven_phase_rad - engine.datum(row.driver_phase_rad) for row in rows]
    assert max(signed_te) - min(signed_te) <= 2 * max(row.phase_error_rad for row in rows)


def test_common_normal_is_external_same_upper_gap_side(stock_pair):
    a, b, _ = stock_pair
    # This contact pose is reconstructed independently from the two outward
    # normals.  Opposite-side/internal-pair mistakes fail position AND normal.
    u = (a.flank_parameter_min + a.flank_parameter_max) / 2
    v = (b.flank_parameter_min + b.flank_parameter_max) / 2
    pa, pb = np.array(a.flank_point(u)), np.array(b.flank_point(v))
    na, nb = np.array(a.flank_normal(u)), np.array(b.flank_normal(v))
    aa, ab = np.arctan2(na[1], na[0]), np.arctan2(nb[1], nb[0])
    q = _rotate(pa, -aa) + _rotate(pb, -ab)
    theta_a = -np.arctan2(q[1], q[0]) - aa
    theta_b = theta_a + aa - ab + pi
    assert np.allclose(_rotate(pa, theta_a), (hypot(*q), 0) + _rotate(pb, theta_b), atol=1e-12)
    assert np.allclose(_rotate(na, theta_a), -_rotate(nb, theta_b), atol=1e-12)
    feature = _NormalFeature(a, "flank")
    t = (u - a.flank_parameter_min) / (a.flank_parameter_max - a.flank_parameter_min)
    assert np.allclose(feature.state(t)[0], _rotate(pa, -aa), atol=1e-12)


def test_stock_branch_existence_is_not_forced_to_unit_carrier_duty(stock_pair):
    a, b, centre = stock_pair
    coverage = supported_branch_coverage(a, b, centre)
    assert coverage.lower_bound > 1.1
    assert coverage.lower_bound <= coverage.value <= coverage.upper_bound
    assert coverage.upper_bound - coverage.lower_bound < 0.001 / a.pitch_radius_mm
    assert a.template.reference_teeth != a.teeth
    assert b.template.reference_teeth != b.teeth
    smooth = supported_flank_coverage(a, b, centre)
    # The corner union must never silently masquerade as the old smooth CR.
    assert smooth.lower_bound > 1
    assert smooth.upper_bound < 1.1
    assert coverage.lower_bound > smooth.upper_bound


def test_occluded_secondary_branch_is_preserved_not_simultaneous_contact(stock_pair):
    a, b, centre = stock_pair
    branch = supported_branch_coverage(a, b, centre)
    engine = planar_contact(a, b, centre)
    contacts = [engine.contact_at(a.angular_pitch_rad * k / 8) for k in range(8)]
    assert branch.lower_bound > 1
    assert all(row.supported for row in contacts)
    assert any(row.other_pair_normal_gap_mm > 0 for row in contacts)
    # Independent positive free-space test: the mate half-way between the two
    # actual first-contact endpoints must have separated complete materials.
    for row in contacts:
        middle = (row.driven_phase_rad + row.reverse_driven_phase_rad) / 2
        assert engine.pose_margin(row.driver_phase_rad, middle) > 0


def test_finite_tip_truncation_refuses_no_contact_not_an_ideal_fallback(stock_pair):
    a, b, centre = stock_pair
    short = replace(a, blank_radius_mm=8.2)
    assert short.blank_radius_mm + b.blank_radius_mm < centre
    branch = supported_branch_coverage(short, b, centre)
    assert branch.upper_bound == 0
    with pytest.raises(MeshCertificationError, match="no carrying engagement"):
        analyse_planar_mesh(short, b, centre)


def test_root_corner_is_refused_but_genuine_below_base_flank_is_working():
    corner = _vertex_name(("tooth0:rootarc", "tooth0:upperfiniteflank"), 1)
    assert "root_corner" in corner
    assert not _working(corner)
    assert _working("tooth0:radial_upperbelowbase")
    assert _working(_vertex_name(("tooth0:radial_upperbelowbase", "tooth0:upperfiniteflank"), 1))
    assert not _working(_vertex_name(("tooth0:rootarc", "tooth0:radial_upperbelowbase"), 1))
    assert _working(_vertex_name(("tooth0:upperfiniteflank", "tip_land"), 1))


def test_radial_normal_feature_uses_the_real_finite_ground_segment():
    template = CutterTemplate(26, 48, 20)
    blank = (template.root_radius_mm + template.base_radius_mm) / 2
    profile = StockFormProfile(26, template, blank, 0.0)
    feature = _NormalFeature(profile, "radial")
    k = template.half_space_base_angle_rad
    for t in (0.0, 0.31, 1.0):
        radius = template.root_radius_mm + t * (blank - template.root_radius_mm)
        expected = (radius * cos(k), radius * sin(k))
        q, angle, derivative = feature.state(t)
        assert np.allclose(_rotate(q, angle), expected, atol=1e-12)
        assert angle == pytest.approx(k - pi / 2)
        assert np.allclose(derivative, (0, blank - template.root_radius_mm), atol=1e-12)
    assert feature.second_bound == 0
    corner = _NormalFeature(profile, "tip_corner")
    for t in (0, 0.5, 1):
        q, angle, _ = corner.state(t)
        assert hypot(*q) == pytest.approx(blank)
        assert np.allclose(_rotate(q, angle), (blank * cos(k), blank * sin(k)), atol=1e-12)
    # The old involute-only diagnostic remains empty for this truly radial tip.
    mate_template = CutterTemplate(55, 48, 20)
    mate = StockFormProfile(55, mate_template, mate_template.tip_radius_mm, 0.0)
    centre = profile.pitch_radius_mm + mate.pitch_radius_mm
    assert supported_flank_coverage(profile, mate, centre).upper_bound == 0


def test_handover_jump_and_period_seam_pay_the_error_bound():
    radius = 20.0
    # Independent 6-micron phase step: a plausible-looking sampled duty cycle
    # must not convert it into a passing 5-micron handover.
    jump, error = _handover_displacement((0.0, 0.006 / radius, 0.006 / radius), radius, 0.00001)
    assert jump == pytest.approx(0.006)
    assert jump + error > 0.005
    # The seam is included even when no explicit final-period sample is stored.
    jump, error = _handover_displacement((0.0, 0.002 / radius, 0.004 / radius), radius, 0.0)
    assert jump == pytest.approx(0.004)
    assert error == 0


@dataclass(frozen=True)
class _SquareEdge:
    """One exact edge of an independent fourfold polygon, normalized t."""
    name: str = "polygon_flank"
    kind: str = "flank"
    second_derivative_bound_mm: float = 0.0

    def point(self, t):
        return 1.0, -1.0 + 2 * t

    def derivative(self, t):
        return 0.0, 2.0


@dataclass(frozen=True)
class _Square:
    teeth: int = 4
    angular_pitch_rad: float = pi / 2
    pitch_radius_mm: float = 1.0
    blank_radius_mm: float = sqrt(2)
    root_radius_max_mm: float = 0.5
    radial_translation_mm: float = 1.0  # excludes the involute theorem path
    geometry_error_bound_mm: float = 0.0
    helix_angle_deg: float = 0.0

    @property
    def template(self):
        return SimpleNamespace(reference_teeth=3)

    def external_boundary_segments(self, unit_scale=1.0, rotate_rad=0.0):
        # The production caller asks for canonical-gap +X at pi/N.  This
        # independent fixture's canonical material is the axis-aligned square.
        assert unit_scale == 1
        assert rotate_rad == pi / 4
        return (_SquareEdge(),)

    def contains_material(self, x_mm, y_mm, rotate_rad=0.0):
        x, y = _rotate((x_mm, y_mm), -rotate_rad)
        return abs(x) <= 1 and abs(y) <= 1


def test_first_contact_backlash_matches_independent_square_separating_axis():
    square = _Square()
    centre = 2.2
    engine = planar_contact(square, square, centre, maximum_error_mm=1e-5)
    contact = engine.contact_at(0.0)
    # At the first collision a rotated square corner reaches x=1:
    # C - cos(beta) - sin(beta) = 1, its y still within [-1,1].
    beta = pi / 4 - acos((centre - 1) / sqrt(2))
    expected = 2 * beta * (centre / 2)
    error = 2 * contact.phase_error_rad * (centre / 2)
    assert abs(contact.backlash_mm - expected) <= error
    assert contact.phase_error_rad * square.blank_radius_mm <= 1e-5 / 2
    assert engine.bracket_margin(0.0, contact, contact.phase_error_rad) > 0


def test_material_first_contact_rejects_a_root_feature_even_with_free_backlash():
    class RootSquare(_Square):
        def external_boundary_segments(self, unit_scale=1.0, rotate_rad=0.0):
            return (_SquareEdge(name="root_corner", kind="root_arc"),)

    engine = planar_contact(RootSquare(), _Square(), 2.2, maximum_error_mm=1e-5)
    row = engine.contact_at(0.0)
    assert row.backlash_mm > 0
    assert not row.supported
    assert "root" in row.feature_ids[0]
    assert engine.unsupported_possible(0.0, row.driven_phase_rad,
                                       0.0, row.phase_error_rad)


def test_support_cones_are_directed_and_located_only_at_their_endpoint():
    points = np.array(((0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)))
    boundary = _Boundary(points, ("root_floor", "flank", "flank", "flank"),
                         0.0, np.zeros(4))
    start, end, angle, width, bad = _support_primitives(boundary, points, np.array((0,)))
    # Smooth horizontal root floor: its normal cannot borrow either corner's
    # ninety-degree cone. Each corner is separately an exact zero-length point.
    assert np.array_equal(start[0], points[0])
    assert np.array_equal(end[0], points[1])
    assert angle[0] == 0
    assert width[0] == 0
    assert np.array_equal(start[1:], points[:2])
    assert np.array_equal(start[1:], end[1:])
    assert np.all(bad)  # Actual root junctions remain unsupported.
    assert angle[2] == pytest.approx(pi / 4)
    assert width[2] == pytest.approx(pi / 4)
    assert abs(-pi / 4 - angle[2]) > width[2]  # Wrong directed cone refused.
    assert abs(pi / 4 - angle[2]) <= width[2]


def test_finite_contact_distance_rejects_overlapping_boxes_and_remote_cones():
    # Parallel sloping segments have overlapping boxes but a known positive
    # finite distance. The other rows exercise point/edge, remote endpoint and
    # proper crossing, so a distance exclusion cannot silently drop corners.
    start_a = np.array(((0., 0.), (1., 0.), (3., 0.), (0., 0.)))
    end_a = np.array(((2., 2.), (1., 0.), (3., 0.), (2., 2.)))
    start_b = np.array(((0., .5), (0., 0.), (0., 0.), (0., 2.)))
    end_b = np.array(((1.5, 2.), (2., 0.), (2., 0.), (2., 0.)))
    distances = _finite_segment_distances(start_a, end_a, start_b, end_b)
    assert distances == pytest.approx((.5 / sqrt(2), 0., 1., 0.))


def test_reported_paper_tight_cell_has_supported_finite_contact_not_remote_cone():
    # Grounded PDCutterMesh observation, core 96649196 / old mesh 72ECE3EB:
    # whole-period enclosure was UNKNOWN despite supported first contacts.
    # This bounded cell regression is NOT a replacement family qualification.
    driver = StockFormProfile(12, CutterTemplate(12, 48, 20), 3.7, .010)
    driven = StockFormProfile(120, CutterTemplate(55, 48, 20),
                              32.220000000000006, 17.220000000000002)
    engine = _MaterialEngine(driver, driven, 34.989115412214574, 0.0, 0.0, .002)
    phi = .5235312144659636
    row = engine._polygon_contact_at(phi)
    assert row.driven_phase_rad == pytest.approx(3.063407608748951, abs=1e-12, rel=0)
    assert row.supported
    assert row.feature_ids == ("tooth11:tip_corner", "tooth0:lowerfiniteflank")
    half = driver.angular_pitch_rad / (2 * 3875)
    delta = .002 / (2 * max(driven.blank_radius_mm, engine.operating_radius))
    assert engine.bracket_margin(phi, row, delta) > driver.blank_radius_mm * half
    # Exercise the production support narrow phase with the ORIGINAL paid
    # pose cell, then strict subsets. No sampled-label waiver or ideal curve.
    for factor in (1.0, .5, 0.0):
        assert not engine.unsupported_possible(phi, row.driven_phase_rad,
                                               half * factor, delta)


def test_polygon_overlap_detects_crossings_without_contained_vertices():
    horizontal = np.array(((-2, -0.2), (2, -0.2), (2, 0.2), (-2, 0.2)))
    vertical = np.array(((-0.2, -2), (0.2, -2), (0.2, 2), (-0.2, 2)))
    assert _polygon_overlap(horizontal, vertical)
    assert not _polygon_overlap(horizontal, vertical + (5, 0))


def test_actual_phase_wrap_and_clocking_keep_signed_physical_datum(stock_pair):
    a, b, centre = stock_pair
    engine = planar_contact(a, b, centre)
    phi = 0.037
    initial = engine.contact_at(phi)
    for turns in (-3, -1, 1, 4):
        row = engine.contact_at(phi + turns * a.angular_pitch_rad)
        assert abs(row.driven_phase_rad - initial.driven_phase_rad + turns * b.angular_pitch_rad) < 1e-11
    driver_clock, driven_clock = 0.007, 0.001
    clocked = planar_contact(a, b, centre, driver_clocking_rad=driver_clock,
                             driven_clocking_rad=driven_clock)
    actual = clocked.contact_at(phi)
    reference = engine.contact_at(phi + driver_clock)
    assert abs(actual.driven_phase_rad - reference.driven_phase_rad) < actual.phase_error_rad + reference.phase_error_rad
    expected_te = reference.driven_phase_rad - engine.datum(phi) - driven_clock
    assert abs(clocked.transmission_error_at(phi) - expected_te) < 1e-11
    # The nonzero constant drive-flank offset is not secretly median-tared.
    assert abs(engine.transmission_error_at(0)) > initial.phase_error_rad


def test_point_uncertainty_encloses_geometry_and_rejects_invalid_budget(stock_pair):
    a, b, centre = stock_pair
    for tolerance in (0.001, 0.0005):
        engine = planar_contact(a, b, centre, maximum_error_mm=tolerance)
        row = engine.contact_at(0.041)
        assert 0 < row.phase_error_rad * b.blank_radius_mm <= tolerance / 2
        assert engine.bracket_margin(0.041, row, row.phase_error_rad) > 0
    with pytest.raises(ValueError, match="Positive finite"):
        planar_contact(a, b, centre, maximum_error_mm=0)
    with pytest.raises(ValueError, match="Clocking"):
        planar_contact(a, b, centre, driver_clocking_rad=float("nan"))
    with pytest.raises(ValueError, match="external|External"):
        planar_contact(a, b, b.blank_radius_mm / 2)
