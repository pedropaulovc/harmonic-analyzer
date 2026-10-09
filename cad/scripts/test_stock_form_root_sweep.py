"""Collision-only root sweep controls; no native CAD or configuration imports.

The bounded cylinder/annulus controls are actual closed solids with exact arc
speed and removed-cap-distance authorities. Real stock profiles independently
exercise ContactSearch's complete physical inventory and actual screw pose.
Finite point checks below are controls, never the production certificate.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import SimpleNamespace

import numpy as np
import pytest

from diagnostics.stock_form_contact_3d import ContactPair, ContactSearch, GapAngles, Placement
from diagnostics.stock_form_root_angles import RootAngularDomain
from diagnostics.stock_form_root_sweep import (
    _difference,
    _merge_forbidden,
    root_free_intervals,
)
from stock_form_cutter import CutterTemplate, CustomSixCutter, StockFormProfile


_IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


class _UnusedFlank:
    error_rad = 0.0

    def branch_range(self, lower_radius, upper_radius):
        raise AssertionError("collision-only root sweep must not query a carrying flank")


@dataclass(frozen=True)
class _CirclePiece:
    radius: float
    name: str
    kind: str = "tip_land"

    @property
    def speed_bound_mm(self):
        return self.radius * 2 * math.pi / 3

    @property
    def second_derivative_bound_mm(self):
        return self.radius * (2 * math.pi / 3) ** 2

    def point(self, t):
        angle = (t - 0.5) * 2 * math.pi / 3
        return self.radius * math.cos(angle), self.radius * math.sin(angle)


@dataclass(frozen=True)
class _Cylinder:
    blank_radius_mm: float
    inner_radius_mm: float = 0.0
    teeth: int = 3
    geometry_error_bound_mm: float = 0.0
    angular_pitch_rad: float = 2 * math.pi / 3
    lead_per_radian_mm: float = math.inf

    @property
    def root_radius_min_mm(self):
        return self.blank_radius_mm if self.inner_radius_mm == 0 else 0.0

    def external_boundary_segments(self):
        outer = _CirclePiece(self.blank_radius_mm, "outer")
        return (outer,) if self.inner_radius_mm == 0 else (
            outer, _CirclePiece(self.inner_radius_mm, "inner", "inner_wall"))

    def contains_material(self, x, y, rotate_rad=0.0):
        radius = math.hypot(x, y)
        return self.inner_radius_mm <= radius <= self.blank_radius_mm + 1e-14


@dataclass(frozen=True)
class _Cap:
    boundary: _CirclePiece
    station_mm: float
    kind: str = "axial_face"

    @property
    def name(self):
        return f"{self.boundary.name}:cap:{self.station_mm}"

    @property
    def speed_bound_mm(self):
        return self.boundary.speed_bound_mm

    def point(self, t):
        return self.boundary.point(t)


def _rotate(point, angle):
    c, s = math.cos(angle), math.sin(angle)
    return c * point[0] - s * point[1], s * point[0] + c * point[1]


class _BoundedCylinderSearch:
    """Faithful ContactSearch duck interface for an exact cylinder or annulus."""

    def __init__(self, driver, driven, origin, *, half_face=None):
        self.case = SimpleNamespace(driver=driver, driven=driven)
        self.placement = SimpleNamespace(
            driver_origin_mm=(0.0, 0.0, 0.0), driven_origin_mm=origin,
            driver_frame=_IDENTITY, driven_frame=_IDENTITY,
            driver_face_mm=(-1.0, 1.0),
            driven_face_mm=(-(half_face or driven.blank_radius_mm), half_face or driven.blank_radius_mm),
            driver_shoulder_z_mm=math.inf, driver_turned_radius_mm=math.inf,
        )
        self.pitch = driver.angular_pitch_rad
        self.phase = self.seed = self.gear_phase = 0.0
        self.radial_error_mm = self.axial_error_mm = 0.0
        self.gap = _UnusedFlank()
        self.driven_teeth = tuple(range(driven.teeth))
        perimeter = driven.external_boundary_segments()
        self.segments = (*perimeter, *(
            _Cap(piece, station) for station in self.placement.driven_face_mm for piece in perimeter))
        self.visited = set()
        self.cap_nonmembers = 0
        self.cap_culls = 0
        self.cull_radii = []

    def point(self, segment, tooth, t, s):
        self.visited.add((segment.name, tooth))
        cap = segment.kind == "axial_face"
        station = segment.station_mm if cap else s
        point = segment.point(t)
        fraction = s if cap else 1.0
        xy = _rotate((fraction * point[0], fraction * point[1]),
                     tooth * self.case.driven.angular_pitch_rad + self.gear_phase
                     + station / self.case.driven.lead_per_radian_mm)
        section = (xy[0], xy[1], station)
        world = tuple(self.placement.driven_origin_mm[j]
                      + sum(self.placement.driven_frame[j][k] * section[k] for k in range(3))
                      for j in range(3))
        local = tuple(sum((world[j] - self.placement.driver_origin_mm[j])
                          * self.placement.driver_frame[j][k] for j in range(3))
                      for k in range(3))
        return world, local

    def second_speed(self, segment):
        if segment.kind == "axial_face":
            return self.case.driven.blank_radius_mm
        return math.hypot(1.0, self.case.driven.blank_radius_mm / self.case.driven.lead_per_radian_mm)

    def surface_member(self, segment, t, s):
        if segment.kind != "axial_face":
            return True
        point = segment.point(t)
        member = self.case.driven.contains_material(s * point[0], s * point[1])
        if not member:
            self.cap_nonmembers += 1
        return member

    def cap_removed(self, segment, t, s, rho):
        if segment.kind != "axial_face" or self.surface_member(segment, t, s):
            return False
        self.cull_radii.append(rho)
        radius = s * segment.boundary.radius
        # Exact distance to the actual circular material boundary, not a
        # midpoint membership guess. Only parameter uncertainty enters here.
        removed = self.case.driven.inner_radius_mm - radius > rho
        if removed:
            self.cap_culls += 1
        return removed


def _stock(teeth=16, reference=14, *, dp=24.0, beta=0.0, shift=None):
    tool = CutterTemplate(reference, dp, 20.0)
    pitch_radius = teeth * tool.module_mm / (2 * math.cos(math.radians(beta)))
    translation = pitch_radius - tool.pitch_radius_mm if shift is None else shift
    return StockFormProfile(teeth, tool, pitch_radius, translation, beta)


def _custom_six():
    tool = CustomSixCutter(48.0, 20.0, 1.173, 2.0,
                           math.pi * (25.4 / 48) / 2, "finite-six-control", "bounded pure control")
    return StockFormProfile(6, tool, 1.8, -0.04)


def _root_disk(driver, *, centre_radius=None, disk_radius=None, theta=0.0, z=0.0):
    strip = driver.root_radius_max_mm - driver.root_radius_min_mm
    radius = disk_radius if disk_radius is not None else strip / 64
    centre = centre_radius if centre_radius is not None else (
        driver.root_radius_min_mm + driver.root_radius_max_mm) / 2
    angle = theta + driver.angular_pitch_rad / 2
    return _BoundedCylinderSearch(driver, _Cylinder(radius),
                                  (centre * math.cos(angle), centre * math.sin(angle), z))


def _member(intervals, value):
    return any(lo < value < hi for lo, hi in intervals)


def _width(intervals):
    return math.fsum(hi - lo for lo, hi in intervals)


def _assert_point_controls_free(search, bounds):
    driver = search.case.driver
    root = RootAngularDomain(driver, search.gap)
    for lo, hi in bounds.free_inner:
        for j in range(64):
            offset = lo + (hi - lo) * (j + 0.5) / 64
            for segment in search.segments:
                stations = (0.0, 0.25, 0.75, 1.0) if segment.kind == "axial_face" else search.placement.driven_face_mm
                for tooth in search.driven_teeth:
                    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
                        for s in stations:
                            if not search.surface_member(segment, t, s):
                                continue
                            _, q = search.point(segment, tooth, t, s)
                            if not search.placement.driver_face_mm[0] <= q[2] <= search.placement.driver_face_mm[1]:
                                continue
                            radius = math.hypot(q[0], q[1])
                            theta = math.atan2(q[1], q[0]) + search.seed - search.phase - search.pitch / 2
                            exact = root.offset_bounds(radius, radius, theta, 0.0, root_only=True)
                            assert _member(exact.outer, offset)
                            # Independent source oracle within the actual root
                            # strip; root-only FREE permits supported flank
                            # material, and above rootMAX it permits tooth body.
                            if radius <= driver.root_radius_max_mm:
                                rotation = -search.seed + search.phase + search.pitch / 2 - offset
                                wrapped = (math.atan2(q[1], q[0]) - rotation + search.pitch / 2) % search.pitch - search.pitch / 2
                                normal = driver.transverse_to_normal(radius * math.cos(wrapped), radius * math.sin(wrapped))
                                if math.hypot(*normal) <= driver.template.root_radius_mm:
                                    assert not driver.contains_material(q[0], q[1], rotate_rad=rotation)


def test_actual_positive_translation_retains_two_free_root_strips():
    search = _root_disk(_stock())
    bounds = root_free_intervals(search, maximum_error_mm=0.002)
    assert bounds.status == "resolved", bounds.reason
    assert len(bounds.free_inner) == len(bounds.free_outer) == 2
    assert not _member(bounds.free_inner, 0.0)
    assert bounds.root_max_radial_clearance_screen_mm < 0.0
    assert bounds.root_air_lower_bound_mm == 0.0
    assert not bounds.root_is_carrying
    assert bounds.boxes >= len(search.segments) * search.case.driven.teeth
    assert search.visited == {(s.name, tooth) for s in search.segments for tooth in search.driven_teeth}
    assert bounds.witnesses and all(w.driven_actual_material_member for w in bounds.witnesses)
    _assert_point_controls_free(search, bounds)


def test_actual_negative_translation_custom_six_retains_central_root_gap():
    search = _root_disk(_custom_six())
    bounds = root_free_intervals(search, maximum_error_mm=0.002)
    assert bounds.status == "resolved", bounds.reason
    assert len(bounds.free_inner) == len(bounds.free_outer) == 1
    assert _member(bounds.free_inner, 0.0)
    assert bounds.free_inner[0][0] < 0 < bounds.free_inner[0][1]
    assert not any(w.collision_at_declared_phase for w in bounds.witnesses)
    _assert_point_controls_free(search, bounds)


@pytest.mark.parametrize("kind", ["above", "below", "tangent"])
def test_zero_translation_floor_and_root_tangency_fail_closed(kind):
    driver = _stock(14, 14)
    radius = 0.0001
    centre = driver.root_radius_min_mm + {"above": 4, "below": -4, "tangent": 1}[kind] * radius
    bounds = root_free_intervals(_root_disk(driver, centre_radius=centre, disk_radius=radius),
                                 maximum_error_mm=0.001)
    assert bounds.status == "resolved", bounds.reason
    if kind == "above":
        assert bounds.free_inner == ((-driver.angular_pitch_rad / 2, driver.angular_pitch_rad / 2),)
    else:
        assert bounds.free_inner == ()
        if kind == "below":
            assert bounds.free_outer == ()
            assert any(w.collision_at_declared_phase for w in bounds.witnesses)


def test_interval_spanning_both_actual_root_extrema_finds_real_material():
    driver = _stock()
    strip = driver.root_radius_max_mm - driver.root_radius_min_mm
    search = _root_disk(driver, disk_radius=2 * strip)
    bounds = root_free_intervals(search)
    assert bounds.status == "resolved", bounds.reason
    assert bounds.free_inner == bounds.free_outer == ()
    assert any(w.collision_at_declared_phase for w in bounds.witnesses)
    assert all(search.surface_member(next(s for s in search.segments if s.name == w.segment),
                                     w.parameter, w.second_parameter) for w in bounds.witnesses)


@pytest.mark.parametrize("axial_miss", [False, True])
def test_actual_material_radial_and_axial_misses_leave_whole_pitch(axial_miss):
    driver = _stock()
    centre = driver.root_radius_min_mm - 0.1 if axial_miss else driver.root_radius_max_mm + 1
    search = _root_disk(driver, centre_radius=centre, disk_radius=0.005, z=2.0 if axial_miss else 0.0)
    bounds = root_free_intervals(search)
    full = ((-driver.angular_pitch_rad / 2, driver.angular_pitch_rad / 2),)
    assert bounds.status == "resolved", bounds.reason
    assert bounds.free_inner == bounds.free_outer == full
    assert bounds.witnesses == ()


def test_uncertain_axial_overlap_is_not_an_actual_collision_witness():
    driver = _stock()
    search = _root_disk(driver, centre_radius=driver.root_radius_min_mm - 0.1,
                        disk_radius=0.001, z=1.1)
    search.axial_error_mm = 0.2
    bounds = root_free_intervals(search)
    assert bounds.status == "resolved", bounds.reason
    assert bounds.free_inner == () and bounds.free_outer
    assert bounds.witnesses == ()
    assert bounds.enclosure_uncertainty
    assert bounds.angular_uncertainty_rad == pytest.approx(search.pitch)
    assert bounds.axial_error_mm == 0.2 and bounds.radial_error_mm == 0.0


def test_actual_nominal_material_collision_is_distinct_from_paid_pose_refusal():
    driver = _stock()
    search = _root_disk(driver, centre_radius=driver.root_radius_min_mm - 0.05,
                        disk_radius=0.001)
    search.radial_error_mm = 0.2
    bounds = root_free_intervals(search)
    assert bounds.status == "resolved", bounds.reason
    assert bounds.free_inner == () and bounds.free_outer
    actual = [w for w in bounds.witnesses if w.collision_at_declared_phase]
    assert actual and actual[0].driven_actual_material_member
    assert actual[0].forbidden_offsets == ()
    assert "paid pose-domain collision not certified" in actual[0].proof
    assert bounds.enclosure_uncertainty


def test_radial_and_axial_source_uncertainty_are_not_conflated():
    driver = _stock()
    axial = _root_disk(driver)
    axial.axial_error_mm = 0.1
    radial = _root_disk(driver)
    radial.radial_error_mm = 0.1
    a, r = root_free_intervals(axial, maximum_error_mm=0.002), root_free_intervals(radial)
    assert a.status == r.status == "resolved"
    assert len(a.free_inner) == 2
    assert r.free_inner == ()
    assert r.driver_pitch_displacement_uncertainty_mm > a.driver_pitch_displacement_uncertainty_mm


def test_actual_cap_interior_detects_overlap_when_side_wall_does_not_cross():
    driver = _stock()
    search = _BoundedCylinderSearch(driver, _Cylinder(2 * driver.blank_radius_mm), (0.0, 0.0, 0.0), half_face=0.25)
    # Driver extends outside the finite driven cylinder, so this is not full
    # containment. Its overlap is reached only by the driven material caps.
    bounds = root_free_intervals(search)
    assert bounds.status == "resolved", bounds.reason
    assert bounds.free_inner == bounds.free_outer == ()
    assert bounds.witnesses
    assert all(":cap:" in w.segment for w in bounds.witnesses)
    assert any(w.collision_at_declared_phase for w in bounds.witnesses)


def test_removed_annular_fans_are_culled_only_by_paid_source_distance():
    driver = _stock()
    source = _Cylinder(2 * driver.blank_radius_mm, 1.1 * driver.blank_radius_mm)
    search = _BoundedCylinderSearch(driver, source, (0.0, 0.0, 0.0), half_face=0.25)
    bounds = root_free_intervals(search, max_boxes=100000)
    assert bounds.status == "resolved", bounds.reason
    assert bounds.free_inner == bounds.free_outer == ((-search.pitch / 2, search.pitch / 2),)
    assert search.cap_nonmembers > 0 and search.cap_culls > 0
    assert bounds.witnesses == ()


def test_cap_removed_receives_parameter_radius_not_pose_or_clearance_ball():
    driver = _stock()
    source = _Cylinder(2 * driver.blank_radius_mm, 1.1 * driver.blank_radius_mm)
    search = _BoundedCylinderSearch(driver, source, (0.0, 0.0, 0.0), half_face=0.25)
    search.radial_error_mm = 0.1
    search.axial_error_mm = 0.2
    authority = search.cap_removed
    calls = []

    def checked(segment, t, s, rho):
        if segment.kind == "axial_face":
            calls.append(rho)
        return authority(segment, t, s, rho)

    search.cap_removed = checked
    bounds = root_free_intervals(search, required_root_air_mm=0.05)
    assert bounds.status == "resolved", bounds.reason
    initial = source.external_boundary_segments()[0].speed_bound_mm / 2 + source.blank_radius_mm / 2
    assert max(calls) == pytest.approx(initial)
    assert search.cap_culls > 0 and bounds.witnesses == ()


def test_unculled_nonmaterial_fan_enclosure_cannot_become_collision_witness():
    driver = _stock()
    source = _Cylinder(2 * driver.blank_radius_mm, 1.1 * driver.blank_radius_mm)
    search = _BoundedCylinderSearch(driver, source, (0.0, 0.0, 0.0), half_face=0.25)
    search.cap_removed = lambda segment, t, s, rho: False
    bounds = root_free_intervals(search, max_boxes=100)
    assert bounds.status == "budget_exhausted"
    assert bounds.free_inner == ()
    assert bounds.witnesses == ()
    assert any(not box.midpoint_is_actual_material for box in bounds.enclosure_uncertainty)


@pytest.mark.parametrize("positive", [True, False])
def test_periodic_pitch_seam_keeps_all_components(positive):
    driver = _stock() if positive else _custom_six()
    search = _root_disk(driver, theta=driver.angular_pitch_rad / 2)
    shifted = _root_disk(driver, theta=3 * driver.angular_pitch_rad / 2)
    a = root_free_intervals(search, maximum_error_mm=0.002)
    b = root_free_intervals(shifted, maximum_error_mm=0.002)
    assert a.status == b.status == "resolved"
    assert len(a.free_inner) == (1 if positive else 2)
    assert np.asarray(a.free_inner) == pytest.approx(np.asarray(b.free_inner), abs=1e-10)
    _assert_point_controls_free(search, a)


def test_full_containment_without_boundary_crossing_has_interior_witness():
    driver = _stock()
    search = _BoundedCylinderSearch(driver, _Cylinder(2 * driver.blank_radius_mm), (0.0, 0.0, 0.0), half_face=2.0)
    bounds = root_free_intervals(search)
    assert bounds.status == "contained_collision"
    assert not bounds.native_solid_certificate
    assert bounds.free_inner == bounds.free_outer == ()
    assert bounds.witnesses[0].driven_tooth is None
    assert bounds.witnesses[0].collision_at_declared_phase
    assert "interior" in bounds.witnesses[0].proof


def test_unproved_containment_refuses_instead_of_accepting_surface_noncrossing():
    driver = _stock()
    source = _Cylinder(2 * driver.blank_radius_mm, 1.1 * driver.blank_radius_mm)
    search = _BoundedCylinderSearch(driver, source, (0.0, 0.0, 0.0), half_face=2.0)
    bounds = root_free_intervals(search)
    assert bounds.status == "containment_refused"
    assert bounds.free_inner == () and bounds.free_outer
    assert bounds.witnesses == ()
    assert "interior root overlap" in bounds.reason


def test_refinement_pays_width_without_turning_a_point_sample_into_certificate():
    driver = _stock()
    coarse = root_free_intervals(_root_disk(driver), maximum_error_mm=0.008)
    fine = root_free_intervals(_root_disk(driver), maximum_error_mm=0.0005)
    assert coarse.status == fine.status == "resolved"
    assert coarse.geometric_uncertainty_mm <= 0.008
    assert fine.geometric_uncertainty_mm <= 0.0005
    assert fine.boxes >= coarse.boxes
    assert fine.driver_pitch_displacement_uncertainty_mm <= coarse.driver_pitch_displacement_uncertainty_mm + 1e-10
    assert fine.driver_pitch_displacement_uncertainty_mm == pytest.approx(
        driver.pitch_radius_mm * fine.angular_uncertainty_rad)
    assert fine.angular_uncertainty_rad == pytest.approx(_width(fine.free_outer) - _width(fine.free_inner))


@pytest.mark.parametrize("positive", [True, False])
@pytest.mark.parametrize("extremum", ["min", "max"])
def test_actual_translated_root_extremum_tangencies_use_paid_enclosures(positive, extremum):
    driver = _stock() if positive else _custom_six()
    disk_radius = (driver.root_radius_max_mm - driver.root_radius_min_mm) / 64
    root_radius = driver.root_radius_min_mm if extremum == "min" else driver.root_radius_max_mm
    search = _root_disk(driver, centre_radius=root_radius + disk_radius, disk_radius=disk_radius)
    bounds = root_free_intervals(search, maximum_error_mm=0.002)
    assert bounds.status == "resolved", bounds.reason
    assert bounds.geometric_uncertainty_mm <= 0.002
    assert math.isfinite(bounds.angular_uncertainty_rad)
    assert not bounds.root_is_carrying
    if extremum == "min":
        # The geometry guard straddles the true minimum at the actual tangent.
        # Do not waive that paid enclosure just because sample centres are air.
        assert bounds.free_inner == ()
    _assert_point_controls_free(search, bounds)


def test_required_root_air_is_paid_to_actual_root_not_a_filled_root_max_disk():
    driver = _stock()
    search = _root_disk(driver)
    baseline = root_free_intervals(search, maximum_error_mm=0.002)
    requested = (driver.root_radius_max_mm - driver.root_radius_min_mm) / 16
    cleared = root_free_intervals(search, maximum_error_mm=0.002, required_root_air_mm=requested)
    assert baseline.status == cleared.status == "resolved"
    assert len(cleared.free_inner) == 2
    assert _width(cleared.free_inner) < _width(baseline.free_inner)
    assert cleared.root_air_lower_bound_mm == requested
    assert cleared.required_root_air_mm == requested
    assert cleared.root_max_radial_clearance_screen_mm < 0.0


def test_turned_shoulder_domain_and_crossing_are_continuously_paid():
    driver = _stock()
    search = _root_disk(driver, centre_radius=driver.root_radius_min_mm - 0.1,
                        disk_radius=0.001, z=0.5)
    search.placement.driver_shoulder_z_mm = 0.0
    search.placement.driver_turned_radius_mm = driver.root_radius_min_mm - 0.2
    miss = root_free_intervals(search)
    assert miss.status == "resolved" and miss.free_inner == miss.free_outer
    assert miss.free_inner == ((-search.pitch / 2, search.pitch / 2),)
    crossing = _root_disk(driver, centre_radius=driver.root_radius_min_mm - 0.1,
                          disk_radius=0.001)
    crossing.placement.driver_shoulder_z_mm = 0.0
    crossing.placement.driver_turned_radius_mm = driver.root_radius_min_mm - 0.2
    hit = root_free_intervals(crossing)
    assert hit.status == "resolved" and hit.free_inner == hit.free_outer == ()


@pytest.mark.parametrize("bad", ["teeth", "caps", "speed", "radial", "axial", "phase", "frame"])
def test_invalid_source_inventories_and_enclosures_fail_closed(bad):
    search = _root_disk(_stock())
    if bad == "teeth":
        search.driven_teeth = (0,)
    elif bad == "caps":
        search.segments = search.segments[:-1]
    elif bad == "speed":
        search.second_speed = lambda segment: math.inf
    elif bad == "radial":
        search.radial_error_mm = -1.0
    elif bad == "axial":
        search.axial_error_mm = math.nan
    elif bad == "phase":
        search.phase = math.nan
    else:
        search.placement.driver_frame = ((2.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    bounds = root_free_intervals(search)
    assert bounds.status == "invalid" and bounds.free_inner == ()
    assert bounds.reason


@pytest.mark.parametrize("kwargs", [
    {"maximum_error_mm": 0.0}, {"maximum_error_mm": math.nan},
    {"max_boxes": 0}, {"max_boxes": 1.5}, {"required_root_air_mm": -0.1},
])
def test_invalid_solver_allowances_fail_closed(kwargs):
    bounds = root_free_intervals(_root_disk(_stock()), **kwargs)
    assert bounds.status == "invalid" and bounds.free_inner == ()


def test_insufficient_initial_inventory_budget_fails_closed():
    bounds = root_free_intervals(_root_disk(_stock()), max_boxes=1)
    assert bounds.status == "budget_exhausted" and bounds.free_inner == ()
    assert "complete initial" in bounds.reason


def test_real_helical_source_uses_all_physical_teeth_and_oblique_screw_pose():
    driver, driven = _stock(), _stock(64, 55, beta=13.0)
    angle = math.radians(13.0)
    frame = np.array(((1.0, 0.0, 0.0), (0.0, math.cos(angle), -math.sin(angle)),
                      (0.0, math.sin(angle), math.cos(angle))))
    placement = Placement(
        (0.0, 0.0, 0.0), (driver.pitch_radius_mm + driven.pitch_radius_mm + 4.0, 0.0, 0.0),
        np.eye(3), frame, (-0.5, 0.5), (-0.2, 0.2), driven_clocking_rad=0.13,
    )
    search = ContactSearch(ContactPair("real-screw-root-miss", driver, driven, placement), 0.17)
    bounds = root_free_intervals(search)
    assert bounds.status == "resolved", bounds.reason
    assert bounds.free_inner == bounds.free_outer == ((-search.pitch / 2, search.pitch / 2),)
    assert bounds.boxes >= len(search.segments) * 64
    assert bounds.witnesses == ()
    # The real search point includes BOTH finite-section helix and station twist.
    segment = next(s for s in search.segments if s.kind == "flank")
    world, local = search.point(segment, 63, 0.3, 0.1)
    xy = _rotate(segment.point(0.3), 63 * driven.angular_pitch_rad + search.gear_phase
                 + 0.1 / driven.lead_per_radian_mm)
    assert world == pytest.approx(np.asarray(placement.driven_origin_mm) + frame @ np.array((*xy, 0.1)))
    assert local == pytest.approx(world)
    incomplete = ContactSearch(search.case, search.phase, driven_teeth=(0, 1))
    assert root_free_intervals(incomplete).status == "invalid"


def test_nonzero_driver_phase_and_clocking_reach_actual_clear_root_strip():
    driver = _stock()
    strip = driver.root_radius_max_mm - driver.root_radius_min_mm
    angle = 0.7 * driver.root_half_angle_rad
    tool_radius = driver.template.root_radius_mm + strip / 32
    gap_point = driver.normal_to_transverse(tool_radius * math.cos(angle), tool_radius * math.sin(angle))
    clock, phase = 0.137, 0.083
    search = _root_disk(driver, centre_radius=math.hypot(*gap_point), disk_radius=strip / 1024,
                        theta=math.atan2(gap_point[1], gap_point[0]) + clock + phase)
    search.seed, search.phase = -clock, phase
    bounds = root_free_intervals(search, maximum_error_mm=0.001)
    assert bounds.status == "resolved", bounds.reason
    assert _member(bounds.free_inner, 0.0)
    assert bounds.root_max_radial_clearance_screen_mm < 0
    rotation = clock + phase + search.pitch / 2
    omega_hit = -math.atan2(gap_point[1], gap_point[0])
    assert math.hypot(*gap_point) + strip / 1024 < driver.root_radius_max_mm
    centre = search.placement.driven_origin_mm
    assert driver.contains_material(centre[0], centre[1], rotate_rad=rotation - omega_hit)
    assert not _member(bounds.free_inner, omega_hit)
    assert not _member(bounds.free_outer, omega_hit)
    for segment in search.segments:
        for tooth in search.driven_teeth:
            for t in (0.0, 0.5, 1.0):
                for s in ((0.0, 0.5, 1.0) if segment.kind == "axial_face" else (-0.5 * strip / 1024, 0.0, 0.5 * strip / 1024)):
                    if search.surface_member(segment, t, s):
                        _, q = search.point(segment, tooth, t, s)
                        assert not driver.contains_material(q[0], q[1], rotate_rad=rotation)
    _assert_point_controls_free(search, bounds)


def test_touching_open_forbidden_sets_preserve_outer_endpoint_with_positive_width():
    forbidden = _merge_forbidden(((-0.2, 0.0), (0.0, 0.2)))
    assert forbidden == ((-0.2, 0.0), (0.0, 0.2))
    outer = _difference(((-0.2, 0.2),), forbidden, preserve_touching_points=True)
    assert len(outer) == 1 and outer[0][0] < 0.0 < outer[0][1]
    assert all(a < b for a, b in outer)


def test_containment_rotates_driver_axial_uncertainty_into_driven_radius():
    driver = _stock()
    search = _BoundedCylinderSearch(driver, _Cylinder(0.95), (0.0, 0.0, 0.0), half_face=2.0)
    search.placement.driven_frame = ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0))
    search.axial_error_mm = 0.2
    bounds = root_free_intervals(search)
    # Endpoint radius 1.0 is outside nominal .95 but not the paid radius 1.15.
    # An actual central interior witness exists instead of a false outside proof.
    assert bounds.status == "contained_collision"
    assert bounds.root_max_radial_clearance_screen_mm is None
    assert "outside" not in bounds.containment_proof


def test_containment_rotates_driver_radial_uncertainty_into_driven_axial_pay():
    driver = _stock()
    search = _BoundedCylinderSearch(driver, _Cylinder(2.0), (0.0, 0.0, 0.0), half_face=0.05)
    search.placement.driver_face_mm = (-0.5, 0.5)
    search.placement.driven_frame = ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0))
    search.radial_error_mm = 0.2
    bounds = root_free_intervals(search)
    assert bounds.status == "containment_refused"
    assert bounds.witnesses == () and bounds.free_inner == ()
    assert bounds.root_max_radial_clearance_screen_mm is None


def test_mid_refinement_budget_refuses_after_complete_initial_inventory():
    search = _root_disk(_stock())
    initial = len(search.segments) * len(search.driven_teeth)
    bounds = root_free_intervals(search, maximum_error_mm=1e-12, max_boxes=initial + 2)
    assert bounds.status == "budget_exhausted"
    assert bounds.boxes == initial + 2 and bounds.free_inner == ()
    assert bounds.witnesses
    assert not _member(bounds.free_outer, 0.0)
    assert "continuous" in bounds.reason


def test_invalid_source_after_material_witness_discards_outer_exclusion_proof():
    search = _root_disk(_stock())
    original = search.point
    calls = 0

    def failing(segment, tooth, t, s):
        nonlocal calls
        calls += 1
        if calls > 10:
            return (math.nan, 0.0, 0.0), (math.nan, 0.0, 0.0)
        return original(segment, tooth, t, s)

    search.point = failing
    bounds = root_free_intervals(search)
    assert bounds.status == "invalid" and bounds.free_inner == ()
    assert calls > 10 and bounds.boxes > 1
    assert bounds.witnesses == ()
    assert bounds.free_outer == ((-search.pitch / 2, search.pitch / 2),)


@pytest.mark.parametrize("shoulder", [False, True])
def test_required_root_air_is_paid_at_actual_face_and_shoulder(shoulder):
    driver = _stock()
    search = _root_disk(driver, centre_radius=driver.root_radius_min_mm - 0.1,
                        disk_radius=0.001, z=0.02 if shoulder else 1.02)
    if shoulder:
        search.placement.driver_shoulder_z_mm = 0.0
        search.placement.driver_turned_radius_mm = driver.root_radius_min_mm - 0.2
    nominal = root_free_intervals(search)
    air = root_free_intervals(search, required_root_air_mm=0.05)
    assert nominal.status == air.status == "resolved"
    assert nominal.free_inner == ((-search.pitch / 2, search.pitch / 2),)
    assert air.free_inner == () and air.free_outer
    assert air.root_air_lower_bound_mm is None
    assert not any(w.collision_at_declared_phase for w in air.witnesses)


def test_turned_radius_clips_inside_actual_positive_translation_root_strip():
    driver = _stock()
    strip = driver.root_radius_max_mm - driver.root_radius_min_mm
    search = _root_disk(driver, centre_radius=driver.root_radius_min_mm + 3 * strip / 4,
                        disk_radius=strip / 64, z=0.5)
    search.placement.driver_shoulder_z_mm = 0.0
    search.placement.driver_turned_radius_mm = driver.root_radius_min_mm + strip / 2
    bounds = root_free_intervals(search)
    assert bounds.status == "resolved" and bounds.free_inner == bounds.free_outer
    assert bounds.free_inner == ((-search.pitch / 2, search.pitch / 2),)
    assert bounds.witnesses == ()


def test_turned_radius_straddling_root_strip_preserves_below_turned_lobe():
    driver = _stock()
    strip = driver.root_radius_max_mm - driver.root_radius_min_mm
    turned = driver.root_radius_min_mm + strip / 2
    search = _root_disk(driver, centre_radius=turned, disk_radius=strip / 64, z=0.5)
    search.placement.driver_shoulder_z_mm = 0.0
    search.placement.driver_turned_radius_mm = turned
    original = search.point
    midpoint_radii = []

    def recorded(segment, tooth, t, s):
        world, local = original(segment, tooth, t, s)
        if t == 0.5 and segment.kind != "axial_face":
            midpoint_radii.append(math.hypot(local[0], local[1]))
        return world, local

    search.point = recorded
    bounds = root_free_intervals(search, maximum_error_mm=0.002)
    assert bounds.status == "resolved", bounds.reason
    assert len(bounds.free_inner) == len(bounds.free_outer) == 2
    assert not _member(bounds.free_inner, 0.0) and not _member(bounds.free_outer, 0.0)
    assert any(r < turned for r in midpoint_radii) and any(r > turned for r in midpoint_radii)
    assert any(w.collision_at_declared_phase for w in bounds.witnesses)
    assert all(math.hypot(w.driver_local_point_mm[0], w.driver_local_point_mm[1]) < turned
               for w in bounds.witnesses if w.forbidden_offsets)
    _assert_point_controls_free(search, bounds)


def test_default_root_scope_remains_distinct_from_complete_working_material():
    driver = _stock()
    radial_room = driver.blank_radius_mm-driver.root_radius_max_mm
    assert radial_room > 0
    search = _root_disk(driver,centre_radius=(driver.blank_radius_mm+driver.root_radius_max_mm)/2,
                        disk_radius=min(0.001,radial_room/16),theta=driver.angular_pitch_rad/2)
    search.gap = GapAngles(driver)
    default = root_free_intervals(search,maximum_error_mm=0.005)
    explicit = root_free_intervals(search,maximum_error_mm=0.005,root_only=True)
    complete = root_free_intervals(search,maximum_error_mm=0.005,root_only=False)
    assert default == explicit
    assert default.status == complete.status == "resolved"
    assert default.material_scope == "driver_root_material"
    assert complete.material_scope == "driver_full_material"
    assert default.free_inner == ((-search.pitch/2,search.pitch/2),)
    assert not _member(complete.free_outer,0)
    assert any(w.collision_at_declared_phase for w in complete.witnesses)
    assert any("full-material" in w.proof for w in complete.witnesses)
    assert complete.physical_driver_teeth == tuple(range(driver.teeth))
    assert complete.physical_driven_teeth == search.driven_teeth
    assert set(complete.physical_patch_inventory) == {
        f"{tooth}:{segment.name}" for tooth in search.driven_teeth for segment in search.segments}
    assert len(complete.physical_patch_inventory) == len(search.driven_teeth)*len(search.segments)


@pytest.mark.parametrize("selector",[0,1,None,"full"])
def test_material_scope_selector_is_not_a_truthy_alias(selector):
    result = root_free_intervals(_root_disk(_stock()),root_only=selector)
    assert result.status == "invalid" and not result.free_inner
    assert "root_only" in result.reason
    assert result.material_scope == "invalid_selector"


@pytest.mark.parametrize("stretch",[4e-13,-4e-13])
def test_containment_uses_true_inverse_of_accepted_near_orthogonal_frame(stretch):
    radius = 1000.0
    search = _BoundedCylinderSearch(_stock(),_Cylinder(radius),(radius,0.0,0.0),half_face=10.0)
    search.placement.driven_frame = ((1+stretch,0.0,0.0),(0.0,1.0,0.0),(0.0,0.0,1.0))
    # These distinguish opposite containment classifications, not merely two
    # numerically unequal matrices. The one-box cap avoids surface traversal.
    assert (radius/(1+stretch) < radius) != (radius*(1+stretch) < radius)
    result = root_free_intervals(search,max_boxes=1)
    if stretch > 0:
        assert result.status == "contained_collision"
        assert result.containment_proof == "offset-invariant interior material witness"
        assert result.witnesses[0].collision_at_declared_phase
    else:
        assert result.status == "budget_exhausted"
        assert result.containment_proof == "driver-root axis point outside paid driven finite cylinder"


@pytest.mark.parametrize("payment",["radial_pose","required_clearance"])
def test_containment_pays_near_orthogonal_directional_metric(payment):
    contraction,allowance = 4e-13,10.0
    local_radius = 1+allowance+contraction*allowance/2
    search = _BoundedCylinderSearch(_stock(),_Cylinder(1.0),
                                   ((1-contraction)*local_radius,0.0,0.0),half_face=100.0)
    search.placement.driven_frame = ((1-contraction,0.0,0.0),(0.0,1.0,0.0),(0.0,0.0,1.0))
    required = allowance if payment == "required_clearance" else 0.0
    search.radial_error_mm = allowance if payment == "radial_pose" else 0.0
    assert 1+allowance < local_radius < 1+allowance/(1-contraction)
    result = root_free_intervals(search,required_root_air_mm=required,max_boxes=1)
    assert result.status == "containment_refused"
    assert "outside" not in result.containment_proof


def test_root_material_witness_uses_true_driver_inverse_not_source_transpose():
    driver = _stock()
    search = _root_disk(driver,centre_radius=driver.root_radius_min_mm-.1,disk_radius=.001)
    stretch = 4e-13
    search.placement.driver_frame = ((1+stretch,0.0,0.0),(0.0,1.0,0.0),(0.0,0.0,1.0))
    result = root_free_intervals(search)
    assert result.status == "resolved"
    witnesses = [value for value in result.witnesses if value.driven_tooth is not None]
    assert witnesses and any(value.collision_at_declared_phase for value in witnesses)
    for witness in witnesses:
        x = witness.world_point_mm[0]-search.placement.driver_origin_mm[0]
        true_local,transposed = x/(1+stretch),x*(1+stretch)
        assert abs(true_local-transposed) > 1e-12
        assert witness.driver_local_point_mm[0] == pytest.approx(true_local,rel=0,abs=2e-14)


def test_full_material_containment_refusal_has_no_root_scope_alias():
    driver = _stock()
    source = _Cylinder(2*driver.blank_radius_mm,1.1*driver.blank_radius_mm)
    search = _BoundedCylinderSearch(driver,source,(0.0,0.0,0.0),half_face=2.0)
    result = root_free_intervals(search,root_only=False)
    assert result.status == "containment_refused"
    assert result.material_scope == "driver_full_material"
    assert "interior material overlap" in result.reason and "root" not in result.reason
    assert result.free_inner == () and result.free_outer and not result.witnesses


@pytest.mark.parametrize("payment",["parameter_radius","primitive_error"])
def test_relative_metric_changes_actual_initial_root_box_classification(payment):
    # Large but finite exact cylinder controls separate a ~4e-13 accepted
    # frame defect from arithmetic rounding. The DRIVER frame is contracted:
    # ||F_driver^-1 F_driven|| > 1 (contracting the driven frame would not do).
    # Exactly one initial inventory is allowed. With the paid metric the
    # closest boxes reach genuine ROOT material and need subdivision; dropping
    # the named scaling falsely prunes every box and reports the pitch FREE.
    driver = _stock()
    radius,contraction,half_face = 1e5,4e-13,1e-12
    source_error = 1e6 if payment == "primitive_error" else 0.0
    driven = _Cylinder(radius,geometry_error_bound_mm=source_error)
    native_rho = driven.external_boundary_segments()[0].speed_bound_mm/2+half_face
    gain = contraction/(1-contraction)
    base = driver.root_radius_max_mm+native_rho+source_error
    arithmetic_reserve = 512*np.finfo(float).eps*(1+base+radius)
    margin = (gain*(native_rho+source_error/2) if payment == "primitive_error"
              else gain*native_rho/2)
    local_midpoint = base+arithmetic_reserve+margin

    def placed(scale):
        search = _BoundedCylinderSearch(
            driver,driven,(scale*local_midpoint+radius,0.0,0.0),half_face=half_face)
        search.placement.driver_frame = ((scale,0.0,0.0),(0.0,scale,0.0),(0.0,0.0,scale))
        search.gear_phase = math.pi
        return search

    identity = placed(1.0)
    initial_boxes = len(identity.driven_teeth)*len(identity.segments)
    reference = root_free_intervals(identity,max_boxes=initial_boxes)
    contracted = root_free_intervals(placed(1-contraction),max_boxes=initial_boxes)
    assert reference.status == "resolved"
    assert reference.free_inner == ((-identity.pitch/2,identity.pitch/2),)
    assert contracted.parameter_radius_metric_upper > 1+contraction/2
    assert contracted.status == "budget_exhausted"
    assert contracted.boxes == initial_boxes
    assert contracted.free_inner == ()
