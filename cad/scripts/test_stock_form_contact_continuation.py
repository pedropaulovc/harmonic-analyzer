"""Authored bounded-geometry controls; no native CAD or qualification claim.

Real finite StockFormProfile/NativeSegment surfaces exercise the adapter.
The independent finite parabolic solids exercise the proof kernel: a plane
approaches their lower surfaces, whose strictly convex gap has an analytically
known minimum. Root caps/sidewalls and an extra competing solid have real
separation bounds. Their source translation is shared, not a desired-answer
mock of a root or of a continuation result. No test substitutes for the actual
oblique/crossed manufacturing-source studies.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math

import numpy as np
import pytest

from diagnostics.stock_form_contact_3d import (
    ContactPair,
    Placement,
    _relative_surface_derivatives,
    _working_angle_derivatives,
    root_free_pose_cell,
    screw_point,
)
from diagnostics.stock_form_contact_continuation import (
    BoundarySeparation,
    ChartEvaluation,
    ChartMinimumBound,
    FirstContactCover,
    Interval,
    PatchRemainderBound,
    PhaseCell,
    ProofNeighbourhood,
    SourcePose,
    StockContactChart,
    _squared_norm,
    _variables,
    body_pose_bounds,
    boundary_inward_gap_derivative,
    branch_geometry_error_rad,
    chart_candidates,
    constraint_covector_scales,
    contact_strata,
    correlated_root_difference,
    correlated_periodic_branch_difference,
    periodicity_displacement_bound_mm,
    _periodicity_displacement_evidence,
    prove_periodic_seam,
    _periodic_source_relabel,
    cos_bounds,
    driven_station_bounds,
    frame_inverse_bounds,
    lagrangian_approach_derivative,
    objective_kkt_multipliers,
    prove_branch_cell,
    prove_paid_handover,
    retained_phase_coverage,
    segment_bounds,
    segment_second_derivative_bounds,
    sin_bounds,
    sqrt_bounds,
)
from stock_form_cutter import CutterTemplate, CustomSixCutter, StockFormProfile


_I = np.eye(3)
_FREE = (Interval(-1, 1),)


def _stock(teeth=16, reference=14, *, helix=0.0, dp=24.0):
    template = CutterTemplate(reference, dp, 20.0)
    pitch = teeth * template.module_mm / (2 * math.cos(math.radians(helix)))
    # A genuinely finite trimmed blank, strictly below full master support.
    return StockFormProfile(teeth, template, pitch + 0.3 * template.module_mm,
                            pitch - template.pitch_radius_mm, helix)


def _pair(driver=None, driven=None, *, frame=None, origin=(30.0, 0.0, 0.0)):
    return ContactPair("bounded-contact-control", driver or _stock(),
                       driven or _stock(64, 55, helix=13.0011),
                       Placement((0.0, 0.0, 0.0), origin, _I, _I if frame is None else frame,
                                 (-1.0, 1.0), (-1.0, 1.0)))


@pytest.mark.parametrize("helix", [0.0, 13.0011, -13.0011])
def test_interval_adapter_encloses_actual_native_points_tangents_and_screw(helix):
    profile = _stock(64, 55, helix=helix)
    pair = _pair(driven=profile)
    for segment in profile.external_boundary_segments():
        point, tangent = segment_bounds(segment, Interval(0.31, 0.32))
        second = segment_second_derivative_bounds(segment, Interval(0.31, 0.32))
        for t in (0.31, 0.315, 0.32):
            for box, actual in zip(point, segment.point(t)):
                assert box.contains(actual)
            for box, actual in zip(tangent, segment.derivative(t)):
                assert box.contains(actual)
        assert all(v.magnitude <= segment.second_derivative_bound_mm + 1e-7 for v in second)
        # Independently reconstruct the public physical screw surface.
        t, z, beta, tooth = 0.315, 0.4, 0.23, 3
        x, y = segment.point(t)
        angle = tooth * profile.angular_pitch_rad + beta + z / profile.lead_per_radian_mm
        expected = np.asarray(pair.placement.driven_origin_mm) + np.array(
            [x * math.cos(angle) - y * math.sin(angle), x * math.sin(angle) + y * math.cos(angle), z])
        assert screw_point(profile, segment.point(t), z, tooth, beta, pair.placement) == pytest.approx(expected)


def test_custom_negative_translation_uses_actual_finite_master_not_ideal_count():
    template = CustomSixCutter(48.0, 20.0, 1.173, 2.0,
                              math.pi * (25.4 / 48) / 2, "finite-six-control", "bounded control")
    profile = StockFormProfile(6, template, 1.8, -0.04)
    for segment in profile.external_boundary_segments():
        point, tangent = segment_bounds(segment, Interval(0.2, 0.21))
        assert all(b.contains(v) for b, v in zip(point, segment.point(0.205)))
        assert all(b.contains(v) for b, v in zip(tangent, segment.derivative(0.205)))
    with pytest.raises(ValueError, match="finite segment"):
        segment_bounds(profile.external_boundary_segments()[0], Interval(-0.01, 0.1))


@pytest.mark.parametrize("interval", [Interval(-0.1, 0.2), Interval(1.5, 1.7),
                                      Interval(3.1, 3.2), Interval(30.0, 30.1), Interval(-10, 10)])
def test_trigonometric_enclosures_pay_extrema_and_argument_reduction(interval):
    sine, cosine = sin_bounds(interval), cos_bounds(interval)
    for angle in (interval.lower, interval.midpoint, interval.upper):
        assert sine.contains(math.sin(angle))
        assert cosine.contains(math.cos(angle))
    if interval.contains(math.pi / 2):
        assert sine.contains(1)
    if interval.contains(math.pi):
        assert cosine.contains(-1)


def test_body_fixed_runout_is_not_a_static_or_shared_translation():
    pair = _pair()
    source = SourcePose((("driver_ecc_x_mm", Interval.point(0.025)),
                         ("driven_ecc_x_mm", Interval.point(-0.018)),
                         ("driven_ry_rad", Interval(-0.002, 0.002))))
    a = body_pose_bounds(pair, source, Interval.point(0), Interval.point(0), body="driver")
    b = body_pose_bounds(pair, source, Interval.point(math.pi / 2), Interval.point(0), body="driver")
    assert a.origin_mm[0].contains(0.025)
    assert b.origin_mm[1].contains(0.025)
    assert not b.origin_mm[0].contains(0.025)
    driven = body_pose_bounds(pair, source, Interval.point(0), Interval(0.1, 0.11), body="driven")
    assert driven.origin_mm[0].upper < pair.placement.driven_origin_mm[0]
    assert driven.axis[0].lower < 0 < driven.axis[0].upper
    assert source.axes[0][0] != source.axes[1][0]


def _normal(segment, t, profile):
    x, y = segment.point(t)
    dx, dy = segment.derivative(t)
    twist = 0 if math.isinf(profile.lead_per_radian_mm) else 1 / profile.lead_per_radian_mm
    return np.cross((dx, dy, 0.0), (-twist * y, twist * x, 1.0))


def _unit(vector):
    return vector / np.linalg.norm(vector)


def _matched_stock_chart(*, stratum="smooth", co_rotation=False, driver_tip=False,
                         driver_band=None, axis_cross_rad=0.2):
    """Construct a genuine common point/normal from two finite stock surfaces.

    The frames map the ACTUAL driven normal (or positive edge normal cone)
    onto the opposite actual driver normal. Rotation about that common normal
    crosses the axes; no normal is assigned in place of a manufactured surface.
    """
    driver, driven = _stock(), _stock(64, 55, helix=13.0011)
    if driver_tip:
        # A finite near-base tip makes the active radial constraint genuinely
        # decisive: raw side-gap beta velocity can have the OPPOSITE sign.
        radius = math.hypot(*driver.flank_point(0.08))
        driver = StockFormProfile(driver.teeth, driver.template, radius,
                                  driver.radial_translation_mm, driver.helix_angle_deg)
    physical = _pair(driver, driven)
    if driver_band is not None:
        native = next(s for s in driver.external_boundary_segments() if s.kind == "flank")
        radius = math.hypot(*native.point(0.45))
        cut = replace(physical.placement, driver_shoulder_z_mm=0.0 if driver_band == "shoulder" else -0.5,
                      driver_turned_radius_mm=radius - 0.02 if driver_band == "shoulder" else radius)
        physical = replace(physical, placement=cut)
    a = next(s for s in contact_strata(physical, "driver", 0)
             if s.segment.kind == "flank" and (
                 (driver_band == "shoulder" and s.axial_cap_source == "driver_shoulder" and not s.implicit_tip)
                 or (driver_band == "turned_tip" and s.radial_cap_radius_mm is not None and s.z_fixed is None)
                 or (driver_band == "turned_corner" and s.radial_cap_radius_mm is not None and s.z_fixed == 1.0)
                 or (driver_band is None and s.z_fixed is None and
                     (s.implicit_tip if driver_tip else s.t_fixed is None))))
    b = next(s for s in contact_strata(_pair(driver, driven), "driven", 0)
             if s.segment.kind == "flank" and s.segment._side == (
                 -a.segment._side if co_rotation else a.segment._side) and (
                 (stratum == "smooth" and s.t_fixed is None and s.z_fixed is None)
                 or (stratum == "tip" and s.implicit_tip and s.z_fixed is None)
                 or (stratum == "edge" and s.t_fixed is None and s.z_fixed == 1.0)))
    ta, za = (a.t_fixed if driver_tip else 0.45), a.z_fixed or 0.0
    tb = b.t_fixed if b.t_fixed is not None else (0.8 if driver_tip else 0.45)
    zb = b.z_fixed or 0.0
    main_a = _normal(a.segment, ta, driver)
    normal_a = (0.05 * main_a + 0.95 * np.array((*a.segment.point(ta), 0.0))) if driver_tip else main_a
    if driver_band == "shoulder":
        normal_a = 0.5 * main_a + 0.5 * np.array((0.0, 0.0, 1.0))
    elif driver_band == "turned_tip":
        normal_a = 0.5 * main_a + 0.5 * np.array((*a.segment.point(ta), 0.0))
    elif driver_band == "turned_corner":
        normal_a = (0.35 * main_a + 0.35 * np.array((*a.segment.point(ta), 0.0))
                    + 0.30 * np.array((0.0, 0.0, 1.0)))
    na = _unit(normal_a)
    nb = _normal(b.segment, tb, driven)
    if stratum == "tip":
        nb = 0.5 * nb + 0.5 * np.array((*b.segment.point(tb), 0.0))
    elif stratum == "edge":
        nb = 0.5 * nb + 0.5 * np.array((0.0, 0.0, 1.0))
    nb = _unit(nb)
    if driver_tip:
        # Map the real driven circumferential velocity's tangent component
        # opposite the raw driver's side-gradient tangent component. This is
        # a physical orthonormal frame construction, not an assigned normal.
        velocity_b = np.cross((0.0, 0.0, 1.0), np.array((*b.segment.point(tb), 0.0)))
        local_tangent = _unit(velocity_b - (velocity_b @ nb) * nb)
        target_tangent = -_unit(main_a - (main_a @ na) * na)
    else:
        local_tangent = _unit(np.cross(nb, np.array((0.0, 0.0, 1.0))))
        tangent_a = _unit(np.cross(na, np.array((0.0, 0.0, 1.0))))
        target_tangent = (1 if co_rotation else -1) * tangent_a
        target_tangent = (math.cos(axis_cross_rad) * target_tangent
                          + math.sin(axis_cross_rad) * np.cross(-na, target_tangent))
    local_basis = np.column_stack((local_tangent, np.cross(nb, local_tangent), nb))
    world_basis = np.column_stack((target_tangent, np.cross(-na, target_tangent), -na))
    frame = world_basis @ local_basis.T
    qa = np.array((*a.segment.point(ta), za))
    qb = np.array((*b.segment.point(tb), zb))
    # Physical screw angle at an edge station is NOT discarded.
    twist = 0 if math.isinf(driven.lead_per_radian_mm) else 1 / driven.lead_per_radian_mm
    c, s = math.cos(zb * twist), math.sin(zb * twist)
    screw_rotation = np.array(((c, -s, 0), (s, c, 0), (0, 0, 1)))
    frame = frame @ screw_rotation.T
    pair = _pair(driver, driven, frame=frame, origin=tuple(qa - frame @ screw_rotation @ qb))
    if driver_band is not None:
        pair = replace(pair, placement=replace(pair.placement,
                       driver_shoulder_z_mm=physical.placement.driver_shoulder_z_mm,
                       driver_turned_radius_mm=physical.placement.driver_turned_radius_mm))
    half_t, half_z, half_beta = 2e-5, 0.002, 2e-5
    values = [(ta, half_t)]
    if a.z_fixed is None:
        values.append((za, half_z))
    if b.t_fixed is None or b.implicit_tip:
        values.append((tb, half_t))
    if b.z_fixed is None:
        values.append((zb, half_z))
    values.append((0.0, half_beta))
    if driver_tip:
        values.append((0.05, 0.002))
    if driver_band in ("shoulder", "turned_tip"):
        values.append((0.5, 0.002))
    elif driver_band == "turned_corner":
        values.extend(((0.35, 0.002), (0.35, 0.002)))
    if stratum != "smooth":
        values.append((0.5, 0.002))
    box = tuple(Interval(value - half, value + half) for value, half in values)
    return StockContactChart(pair, a, b, box, int(np.argmax(np.abs(na))))


@pytest.mark.parametrize("stratum", ["smooth", "tip", "edge"])
def test_actual_stock_charts_prove_small_closed_phase_cell(stratum):
    chart = _matched_stock_chart(stratum=stratum)
    cell = PhaseCell(Interval(-1e-8, 1e-8))
    proof = prove_branch_cell(chart, cell, root_free_driven_components_rad=_FREE)
    assert proof.status == "PROVED", proof.reason
    assert proof.driven_phase_rad.magnitude < 2e-7
    data = chart.evaluate(cell, proof.root_box)
    assert (data.driver_moment * data.driven_moment).upper < 0
    assert all(v.lower > 0 for _, v in data.margins)
    station = driven_station_bounds(chart, proof)
    if chart.driven_stratum.z_fixed is None:
        assert station.magnitude < 2e-6
    else:
        assert station == Interval.point(chart.driven_stratum.z_fixed)
    # This is an OUTER enclosure; it is deliberately NOT a row certificate.
    assert "row_available_fraction_lower" not in proof.record()


def test_common_normal_velocity_sign_rejects_declared_co_rotation():
    chart = _matched_stock_chart(co_rotation=True)
    proof = prove_branch_cell(chart, PhaseCell(Interval(-1e-9, 1e-9)), root_free_driven_components_rad=_FREE)
    assert proof.status == "UNKNOWN"
    assert "torque" in proof.reason


def test_root_component_membership_uses_entire_root_interval_not_component_hull():
    chart = _matched_stock_chart()
    proof = prove_branch_cell(chart, PhaseCell(Interval(-1e-8, 1e-8)),
                              root_free_driven_components_rad=(Interval(-0.1, -1e-4), Interval(1e-4, 0.1)))
    assert proof.status == "UNKNOWN"
    assert "INNER component" in proof.reason


def test_deep_surface_mismatch_is_proof_refusal_not_physical_infeasibility():
    chart = _matched_stock_chart()
    placement = replace(chart.pair.placement,
                        driven_origin_mm=tuple(np.asarray(chart.pair.placement.driven_origin_mm) + np.array((0.2, 0, 0))))
    moved = replace(chart, pair=replace(chart.pair, placement=placement))
    proof = prove_branch_cell(moved, PhaseCell(Interval(-1e-8, 1e-8)), root_free_driven_components_rad=_FREE)
    assert proof.status == "UNKNOWN"
    assert "no_solution" not in proof.record()


def test_actual_tip_normals_use_implicit_blank_intersection_and_real_generators():
    chart = _matched_stock_chart(stratum="tip")
    assert chart.driven_stratum.implicit_tip
    assert len(chart.unknown_box) == 6
    cell = PhaseCell(Interval(-1e-9, 1e-9))
    proof = prove_branch_cell(chart, cell, root_free_driven_components_rad=_FREE)
    assert proof.status == "PROVED", proof.reason
    data = chart.evaluate(cell, proof.root_box)
    assert len(data.residual) == 6
    assert data.residual[-1].contains(0)
    assert len(data.cone_generators_world[1]) == 2
    # Real positive tip multiplier is not an optimizer's residual normal.
    main = data.cone_generators_world[0][0]
    multipliers = objective_kkt_multipliers(chart, proof, main)
    assert multipliers["driver"] == ()
    assert multipliers["driven"][0].lower > 0
    with pytest.raises(ArithmeticError, match="positive actual working-side"):
        objective_kkt_multipliers(chart, proof, tuple(-v for v in main))


def test_chart_initializer_is_only_a_seed_and_root_junctions_are_not_charts():
    chart = _matched_stock_chart()
    a, b = chart.driver_stratum, chart.driven_stratum
    ta, tb = chart.unknown_box[0].midpoint, chart.unknown_box[2].midpoint
    qa = np.array((*a.segment.point(ta), 0.0))
    na = _unit(_normal(a.segment, ta, chart.pair.driver))
    nb = chart.pair.placement.driven_frame @ _unit(_normal(b.segment, tb, chart.pair.driven))
    contact = {"world_point_mm": tuple(qa), "driver_normal_world": tuple(na),
               "driven_normal_world": tuple(nb), "driven_tooth": 0}
    candidates = chart_candidates(chart.pair, contact, 0, 0)
    assert candidates
    assert all(isinstance(c, StockContactChart) for c in candidates)
    assert all(s.carrying and all("root" not in incident.kind for incident, _ in s.incident_segments)
               for s in contact_strata(chart.pair, "driven", 0))
    assert all(not hasattr(c, "continuous") for c in candidates)


@dataclass(frozen=True)
class _FiniteParabolicSurface:
    """Independent exact finite solid: h(u,v)<=z<=h(u,v)+1.

    u,v lie in [-1,1]. An edge control cuts u off at zero. The approaching
    plane is z=beta; h=q+slope*phi+(u-c*phi)^2+v^2+offset. A body-fixed screw
    lift supplies the negative slope, and q is the SAME installation height
    at both contact patches. Equations are gap and tangential stationarity,
    not fabricated root intervals/support booleans. Strict convexity and
    finite sidewall/cap heights supply the local/global minimum controls.
    """
    # Distinct tooth pads have world x=3*tooth+u, so their physical finite
    # domains do not overlap. Grouped search patches may contain their union.
    name: str
    driven_tooth: int
    slope: float = -1.0
    source_scale: float = 1.0
    edge: bool = False
    offset: float = 0.0
    offset_index: int = 2
    unknown_box: tuple[Interval, ...] = (Interval(-0.1, 0.1), Interval(-0.1, 0.1), Interval(-0.3, 0.3))

    def evaluate(self, cell, unknowns):
        jets = _variables((*unknowns, *cell.parameter_bounds))
        n = len(unknowns)
        phi, q = jets[n], jets[n + 1]
        if self.edge:
            v, beta, multiplier = jets[:n]
            u = v * 0  # actual fixed upper edge u=0 of the finite solid
            height = self.source_scale * q + self.slope * phi + phi * phi + v * v + self.offset
            equations = (2 * v, beta - height, multiplier - 2 * phi)
            margins = (("edge_v_lower", (v + 1).value), ("edge_v_upper", (1 - v).value),
                       ("physical_upper_edge_multiplier", multiplier.value))
            moment = (self.slope + 2 * phi).value
        else:
            u, v, beta = jets[:n]
            height = self.source_scale * q + self.slope * phi + u * u + v * v + self.offset
            equations = (2 * u, 2 * v, beta - height)
            margins = (("finite_u_lower", (u + 1).value), ("finite_u_upper", (1 - u).value),
                       ("finite_v_lower", (v + 1).value), ("finite_v_upper", (1 - v).value))
            moment = Interval.point(self.slope)
        return ChartEvaluation(tuple(v.value for v in equations),
                               tuple(v.derivative[:n] for v in equations),
                               tuple(v.derivative[n:] for v in equations), margins, moment, Interval.point(1),
                               driven_surface_coordinates=((u * 0.5 + 0.5).value, v.value))


def _source():
    return SourcePose((("driver_dz_mm", Interval(-0.1, 0.1)),))


def _cover(cell, surfaces):
    # Full Cartesian approach beta in [-.2,.2], not a secretly correlated
    # beta=q slice. At the finite walls/caps the added height is >=1.
    # Outside the actual radius-.75 neighbourhood it is >=.75².
    # Pay all source translation, all booked phase lift and the entire beta
    # interval before asserting a positive physical remainder bound.
    travel = max(abs(s.source_scale) for s in surfaces) * 0.1
    lift = max(abs(s.slope) for s in surfaces) * 0.002
    payment = travel + lift + 0.2 + 0.0001
    remainder_air = Interval(0.75 ** 2 - payment, 2.0)
    patches = tuple(f"{surface.name}:lower" for surface in surfaces)
    roots = tuple(f"{surface.name}:{kind}" for surface in surfaces for kind in ("cap", "wall"))
    return FirstContactCover(cell, _FREE, 0.5, Interval(-0.2, 0.2), patches + roots,
                             tuple((surface.name, (patch,)) for surface, patch in zip(surfaces, patches)),
                             tuple((root, Interval(1 - payment, 2.0)) for root in roots), roots, 0.01,
                             tuple(ChartMinimumBound(surface.name, 2, 2.0, remainder_air, 1.0,
                                                     Interval.point(-1), -1,
                                                     ProofNeighbourhood(cell, (Interval(-0.75, 0.75),) * 3,
                                                                        Interval(-0.2, 0.2),
                                                                        (Interval(0.125, 0.5 if surface.edge else 0.875),
                                                                         Interval(-0.75, 0.75))), 3.0)
                                   for surface in surfaces),
                             root_patch_ids=roots, free_reference_driven_phase_rad=Interval.point(-0.2),
                             free_reference_air_mm=Interval(0.4 - payment, 2.0), closing_driven_sense=1,
                             additional_geometry_error_mm=0.0)


def test_same_source_translation_cancels_only_through_proved_difference_derivatives():
    a, b = _FiniteParabolicSurface("a", 0), _FiniteParabolicSurface("b", 1, slope=-1.1)
    cell = PhaseCell(Interval(-0.001, 0.001), _source())
    difference, proofs, _ = correlated_root_difference(a, b, cell, root_free_driven_components_rad=_FREE)
    assert all(p.status == "PROVED" for p in proofs)
    assert difference.contains(-0.0001) and difference.contains(0.0001)
    assert difference.magnitude < 0.00011
    # Independent physical root intervals would pay the shared .2 source width.
    independent = proofs[1].driven_phase_rad - proofs[0].driven_phase_rad
    assert independent.magnitude > 0.19
    result = prove_paid_handover(a, b, cell, _cover(cell, (a, b)), driven_pitch_radius_mm=10)
    assert result["status"] == "PROVED", result["reason"]
    assert 0 < result["pitch_displacement_jump_upper_mm"] <= 0.005


def test_same_named_source_with_different_site_sensitivity_does_not_cancel():
    a = _FiniteParabolicSurface("a", 0)
    b = _FiniteParabolicSurface("b", 1, slope=-1.1, source_scale=1.1)
    cell = PhaseCell(Interval(-0.001, 0.001), _source())
    difference, _, _ = correlated_root_difference(a, b, cell, root_free_driven_components_rad=_FREE)
    assert difference.magnitude >= 0.01
    result = prove_paid_handover(a, b, cell, _cover(cell, (a, b)), driven_pitch_radius_mm=10)
    assert result["status"] == "UNKNOWN"
    assert not result["physical_no_solution"]


def test_real_finite_tip_edge_handover_pays_common_pose_and_kkt_support():
    centre = 0.001
    a = _FiniteParabolicSurface("side", 0)
    b = _FiniteParabolicSurface("edge", 1, slope=-1.1, edge=True,
                                offset=0.1 * centre - centre ** 2, offset_index=1,
                                unknown_box=(Interval(-0.1, 0.1), Interval(-0.3, 0.3), Interval(0.001, 0.003)))
    cell = PhaseCell(Interval(0.0009, 0.0011), _source())
    result = prove_paid_handover(a, b, cell, _cover(cell, (a, b)), driven_pitch_radius_mm=10)
    assert result["status"] == "PROVED", result["reason"]
    assert result["pitch_displacement_jump_upper_mm"] < 0.005
    # Across phi=0 the fixed edge chart loses its real one-sided multiplier.
    invalid = prove_branch_cell(b, PhaseCell(Interval(-0.0001, 0.0001), _source()), root_free_driven_components_rad=_FREE)
    assert invalid.status == "UNKNOWN"


@pytest.mark.parametrize("defect", ["missing_patch", "competitor", "noncarrying", "minimum", "transversality", "backlash"])
def test_supported_roots_do_not_proclaim_first_contact_or_zero_jump(defect):
    a, b = _FiniteParabolicSurface("a", 0), _FiniteParabolicSurface("b", 1, slope=-1.1)
    cell = PhaseCell(Interval(-0.001, 0.001), _source())
    cover = _cover(cell, (a, b))
    if defect == "missing_patch":
        cover = replace(cover, physical_patch_inventory=(*cover.physical_patch_inventory, "third_solid"))
    elif defect == "competitor":
        cover = replace(cover, physical_patch_inventory=(*cover.physical_patch_inventory, "third_solid"),
                        excluded_patch_air_mm=(*cover.excluded_patch_air_mm, ("third_solid", Interval(-0.01, 0.01))))
    elif defect == "noncarrying":
        cover = replace(cover, excluded_patch_air_mm=((cover.noncarrying_patch_ids[0], Interval(-0.01, 0.01)),
                                                     *cover.excluded_patch_air_mm[1:]))
    elif defect == "minimum":
        cover = replace(cover, chart_minimum_bounds=())
    elif defect == "transversality":
        cover = replace(cover, chart_minimum_bounds=(replace(cover.chart_minimum_bounds[0], approach_derivative_magnitude_lower=0),
                                                    cover.chart_minimum_bounds[1]))
    else:
        cover = replace(cover, backlash_lower_mm=0)
    result = prove_paid_handover(a, b, cell, cover, driven_pitch_radius_mm=10)
    assert result["status"] == "UNKNOWN"
    assert not result["continuous"] and not result["physical_no_solution"]
    assert "pitch_displacement_jump_upper_mm" not in result


def _proved_cell(lo, hi, surfaces, source=None):
    cell = PhaseCell(Interval(lo, hi), _source() if source is None else source)
    proofs = tuple(prove_branch_cell(s, cell, root_free_driven_components_rad=_FREE) for s in surfaces)
    assert all(p.status == "PROVED" for p in proofs)
    return cell, proofs, _cover(cell, surfaces)


def test_coverage_integrates_distinct_supported_teeth_and_closed_phase_seams():
    a, b = _FiniteParabolicSurface("a", 0), _FiniteParabolicSurface("b", 1, slope=-1.1)
    items = (_proved_cell(0, 0.001, (a, b)), _proved_cell(0.001, 0.002, (a, b)))
    summary = retained_phase_coverage(items, driver_pitch_rad=0.002, driven_pitch_radius_mm=10)
    assert summary["status"] == "PROVED" and summary["supported_no_gap"]
    assert 1.99 < summary["stock_form_coverage_lower"] <= 2
    assert not summary["continuous_carrying_contact"]  # paid exchanges are still separate
    gap = retained_phase_coverage((_proved_cell(0.00001, 0.001, (a,)),
                                   _proved_cell(0.0011, 0.00199, (a,))), driver_pitch_rad=0.002, driven_pitch_radius_mm=10)
    assert gap["status"] == "UNKNOWN" and gap["uncovered_phase_rad"] > 0
    mixed_source = (_proved_cell(0, 0.001, (a,)),
                    _proved_cell(0.001, 0.002, (a,), SourcePose((("driver_dz_mm", Interval(-0.01, 0.01)),))))
    assert retained_phase_coverage(mixed_source, driver_pitch_rad=0.002, driven_pitch_radius_mm=10)["status"] == "UNKNOWN"


def test_two_charts_of_the_same_tooth_are_not_extra_union_coverage():
    a = _FiniteParabolicSurface("side", 0)
    duplicate = replace(a, name="another_chart_same_tooth")
    summary = retained_phase_coverage((_proved_cell(0, 0.002, (a, duplicate)),),
                                      driver_pitch_rad=0.002, driven_pitch_radius_mm=10)
    assert 0.99 < summary["stock_form_coverage_lower"] <= 1


def test_finite_trimmed_tip_derivative_extension_never_extends_the_tool_master():
    chart = _matched_stock_chart(stratum="tip")
    segment = chart.driven_stratum.segment
    parameter = Interval(0.99999, 1.00001)
    with pytest.raises(ValueError, match="finite segment"):
        segment_bounds(segment, parameter)
    point, _ = segment_bounds(segment, parameter, finite_master_extension=True)
    assert all(v.contains(p) for v, p in zip(point, segment.point(1)))
    assert len(segment_second_derivative_bounds(segment, parameter, finite_master_extension=True)) == 2
    with pytest.raises(ValueError, match="finite cutter master"):
        segment_bounds(segment, Interval(1, 10), finite_master_extension=True)
    assert sqrt_bounds(Interval.point(0)) == Interval.point(0)


def test_actual_eccentric_moments_include_rotating_material_origin_velocity():
    chart = _matched_stock_chart()
    source = SourcePose((("driver_ecc_y_mm", Interval.point(0.03)),
                         ("driven_ecc_x_mm", Interval.point(0.04))))
    cell = PhaseCell(Interval.point(0.015), source)
    unknowns = tuple(Interval.point(v.midpoint) for v in chart.unknown_box)
    data = chart.evaluate(cell, unknowns)
    beta = unknowns[chart.offset_index]
    driven_normal = np.array([v.midpoint for v in data.cone_generators_world[1][0]])
    expected = []
    omitted_origin_velocities = []
    for body, stratum, t, z in (
            ("driver", chart.driver_stratum, unknowns[0].midpoint, unknowns[1].midpoint),
            ("driven", chart.driven_stratum, unknowns[2].midpoint, unknowns[3].midpoint)):
        pose = body_pose_bounds(chart.pair, source, cell.driver_phase_rad, beta, body=body)
        frame = np.array([[v.midpoint for v in row] for row in pose.frame])
        origin = np.array([v.midpoint for v in pose.origin_mm])
        profile = getattr(chart.pair, body)
        phase = cell.driver_phase_rad.midpoint if body == "driver" else beta.midpoint
        twist = 0 if math.isinf(profile.lead_per_radian_mm) else 1 / profile.lead_per_radian_mm
        x, y = stratum.segment.point(t)
        angle = phase + stratum.tooth * profile.angular_pitch_rad + z * twist
        point = origin + frame @ np.array((x * math.cos(angle) - y * math.sin(angle),
                                          x * math.sin(angle) + y * math.cos(angle), z))
        static_axis_origin = np.asarray(getattr(chart.pair.placement, f"{body}_origin_mm"))
        expected.append(float(np.cross(frame[:, 2], point - static_axis_origin) @ driven_normal))
        omitted_origin_velocities.append(float(np.cross(frame[:, 2], point - origin) @ driven_normal))
    assert data.driver_moment.contains(expected[0])
    assert data.driven_moment.contains(expected[1])
    assert abs(expected[1] - omitted_origin_velocities[1]) > 0.001


@pytest.mark.parametrize("shift_kind", ["positive_stock", "negative_custom"])
def test_shared_working_flank_curvature_uses_actual_translated_dr_du(shift_kind):
    if shift_kind == "positive_stock":
        profile = _stock()
    else:
        template = CustomSixCutter(48.0, 20.0, 1.173, 2.0,
                                  math.pi * (25.4 / 48) / 2, "curvature-six", "bounded control")
        profile = StockFormProfile(6, template, 1.8, -0.04)
    u = (profile.flank_parameter_min + profile.flank_parameter_max) / 2
    radius = math.hypot(*profile.flank_point(u))
    slope, curvature = _working_angle_derivatives(profile, "flank", Interval(radius - 1e-8, radius + 1e-8))
    rb, translation = profile.template.base_radius_mm, profile.radial_translation_mm
    k = profile.template.half_space_base_angle_rad
    S = rb + translation * math.cos(k + u)
    Q = rb * u + translation * math.sin(k + u)
    expected_slope = Q / (radius * S)
    expected_second = (1 / (rb * u * S) - Q / (radius ** 2 * S)
                       + Q * translation * math.sin(k + u) / (rb * u * S ** 3))
    assert slope.contains(expected_slope)
    assert curvature.contains(expected_second)
    # The untranslated ideal dr/du would miss the actual S/r factor.
    actual_dr_du = rb * u * S / radius
    assert actual_dr_du != pytest.approx(rb * u, abs=1e-6)


def test_shared_actual_radial_curvature_and_crossed_surface_beta_velocity():
    profile = _stock()
    reference = (profile.template.root_radius_mm + profile.template.base_radius_mm) / 2
    radius = math.hypot(*profile.radial_point(reference))
    slope, curvature = _working_angle_derivatives(profile, "radial", Interval(radius - 1e-8, radius + 1e-8))
    k, translation = profile.template.half_space_base_angle_rad, profile.radial_translation_mm
    Q, S = translation * math.sin(k), reference + translation * math.cos(k)
    assert slope.contains(Q / (radius * S))
    assert curvature.contains(-Q / (radius ** 2 * S) - Q / S ** 3)
    chart = _matched_stock_chart()
    source = SourcePose((("driver_ecc_y_mm", Interval.point(0.03)),
                         ("driven_ecc_x_mm", Interval.point(0.04))))
    cell, beta = PhaseCell(Interval.point(0.02), source), Interval.point(0.01)
    segment = chart.driven_stratum.segment
    q, _, _, velocity, _, _, _, _ = _relative_surface_derivatives(
        chart.pair, cell, beta, segment, 0, Interval.point(0.45), Interval.point(0.3))
    driven = body_pose_bounds(chart.pair, source, cell.driver_phase_rad, beta, body="driven")
    driver = body_pose_bounds(chart.pair, source, cell.driver_phase_rad, beta, body="driver")
    frame = np.array([[v.midpoint for v in row] for row in driver.frame])
    axis = np.array([v.midpoint for v in driven.axis])
    world = np.array([v.midpoint for v in driver.origin_mm]) + frame @ np.array([v.midpoint for v in q])
    shaft = np.asarray(chart.pair.placement.driven_origin_mm)
    expected = frame.T @ np.cross(axis, world - shaft)
    assert all(v.contains(p) for v, p in zip(velocity, expected))


def test_all_tooth_root_free_pose_is_not_a_supported_first_contact_certificate():
    chart = _matched_stock_chart()
    placement = replace(chart.pair.placement, driven_origin_mm=(1000.0, 0.0, 0.0))
    pair = replace(chart.pair, placement=placement)
    cell, beta = PhaseCell(Interval(-1e-5, 1e-5)), Interval(-1e-5, 1e-5)
    root = root_free_pose_cell(pair, cell, beta, maximum_error_mm=0.001, required_root_air_mm=0.01)
    assert root["status"] == "PROVED"  # genuine far-separated finite roots/caps
    absent = prove_branch_cell(replace(chart, pair=pair), cell,
                               root_free_driven_components_rad=root["root_free_driven_components_rad"])
    assert absent.status == "UNKNOWN"  # no common normal just because roots are clear


def test_actual_edge_inward_derivative_uses_real_cone_and_rejects_outward_direction():
    chart = _matched_stock_chart(stratum="edge")
    proof = prove_branch_cell(chart, PhaseCell(Interval(-1e-9, 1e-9)), root_free_driven_components_rad=_FREE)
    assert proof.status == "PROVED", proof.reason
    data = chart.evaluate(proof.cell, proof.root_box)
    gradient = data.cone_generators_world[0][0]
    t = proof.root_box[chart.driver_stratum.algebra_coordinates]
    point, _ = segment_bounds(chart.driven_stratum.segment, t)
    pose = body_pose_bounds(chart.pair, proof.cell.source_pose, proof.cell.driver_phase_rad,
                            proof.driven_phase_rad, body="driven")
    angle = proof.driven_phase_rad + chart.driven_stratum.z_fixed / chart.pair.driven.lead_per_radian_mm
    c, s = cos_bounds(angle), sin_bounds(angle)
    radial = (c * point[0] - s * point[1], s * point[0] + c * point[1], Interval.point(0))
    inward = tuple(-sum(row[k] * radial[k] for k in range(3)) for row in pose.frame)
    derivative = boundary_inward_gap_derivative(chart, proof, gradient, inward, ())
    assert derivative.lower > 0
    with pytest.raises(ArithmeticError, match="inward separation"):
        boundary_inward_gap_derivative(chart, proof, gradient, tuple(-v for v in inward), ())


def test_open_cap_at_real_edge_uses_one_sided_separation_not_fake_positive_infimum():
    centre = 0.001
    a = _FiniteParabolicSurface("side", 0)
    b = _FiniteParabolicSurface("edge", 1, slope=-1.1, edge=True,
                                offset=0.1 * centre - centre ** 2, offset_index=1,
                                unknown_box=(Interval(-0.1, 0.1), Interval(-0.3, 0.3), Interval(0.001, 0.003)))
    cell = PhaseCell(Interval(0.0009, 0.0011), _source())
    base = _cover(cell, (a, b))
    patch = "edge:vertical_cap"
    # Actual u=0 face is z=h(0,v)+tau, 0<tau<=1. At its edge
    # tau->0 the gap infimum is ZERO, but dg/dtau=1 everywhere.
    # Outside the radius-.75/tau-.75 local neighbourhood, the same full
    # beta/source payment as _cover leaves positive gap >.25.
    assignments = tuple((name, (*ids, patch) if name == b.name else ids)
                        for name, ids in base.chart_patch_ids)
    cover = replace(base, physical_patch_inventory=(*base.physical_patch_inventory, patch),
                    chart_patch_ids=assignments, noncarrying_patch_ids=(*base.noncarrying_patch_ids, patch),
                    boundary_separations=(BoundarySeparation(patch, b.name, 1.0, Interval(0.25, 3.0),
                                                            base.chart_minimum_bounds[1].neighbourhood),))
    result = prove_paid_handover(a, b, cell, cover, driven_pitch_radius_mm=10)
    assert result["status"] == "PROVED", result["reason"]
    assert patch not in dict(cover.excluded_patch_air_mm)
    unsupported = replace(cover, boundary_separations=())
    assert prove_paid_handover(a, b, cell, unsupported, driven_pitch_radius_mm=10)["status"] == "UNKNOWN"
    reversed_normal = replace(cover, boundary_separations=(replace(cover.boundary_separations[0], inward_gap_derivative_lower=-1),))
    assert prove_paid_handover(a, b, cell, reversed_normal, driven_pitch_radius_mm=10)["status"] == "UNKNOWN"
    root_exception = replace(cover, root_patch_ids=(*cover.root_patch_ids, patch))
    refused = prove_paid_handover(a, b, cell, root_exception, driven_pitch_radius_mm=10)
    assert refused["status"] == "UNKNOWN"
    assert "root/floor/junction" in refused["reason"]


def test_real_active_driver_tip_can_reverse_raw_vs_lagrangian_approach_sign():
    chart = _matched_stock_chart(driver_tip=True)
    proof = prove_branch_cell(chart, PhaseCell(Interval(-1e-10, 1e-10)), root_free_driven_components_rad=_FREE)
    assert proof.status == "PROVED", proof.reason
    data = chart.evaluate(proof.cell, proof.root_box)
    gradient = data.cone_generators_world[0][0]
    tip_normal = data.cone_generators_world[0][1]
    inward_tip_gradient = tuple(-v / chart.pair.driver.blank_radius_mm for v in tip_normal)
    t_index = chart.driver_stratum.algebra_coordinates
    t, z = proof.root_box[t_index], proof.root_box[chart.driven_z_index]
    _, _, _, velocity, frame, _, _, _ = _relative_surface_derivatives(
        chart.pair, proof.cell, proof.driven_phase_rad, chart.driven_stratum.segment,
        chart.driven_tooth, t, z)
    world_velocity = tuple(sum(frame[i][j] * velocity[j] for j in range(3)) for i in range(3))
    raw = sum(g * v for g, v in zip(gradient, world_velocity))
    constrained = lagrangian_approach_derivative(chart, proof, gradient, world_velocity, (inward_tip_gradient,))
    assert raw.upper < 0  # raw h_beta would choose the WRONG closing side
    assert constrained.lower > 0  # actual positive cone/radial constraint paid
    with pytest.raises(ValueError, match="constraint gradients"):
        lagrangian_approach_derivative(chart, proof, gradient, world_velocity, ())


def test_actual_record_retains_reader_strata_indices_and_interval_evidence():
    chart = _matched_stock_chart(stratum="edge")
    proof = prove_branch_cell(chart, PhaseCell(Interval(-1e-9, 1e-9)), root_free_driven_components_rad=_FREE)
    assert proof.status == "PROVED", proof.reason
    record = proof.record()
    assert record["physical_strata"]["driven"]["z_fixed"] == 1.0
    assert record["physical_strata"]["driven"]["t_fixed"] is None
    assert record["driven_station_unknown_index"] is None
    assert record["driven_angle_unknown_index"] == chart.offset_index
    assert record["root_box"] and record["unknown_domain"]
    assert record["normal_cone_weights"] and record["common_normal_moments"]
    assert set(record["required_support_margin_names"]) == set(record["support_margins"])
    assert not record["native_certificate"]


def test_actual_axial_edge_domain_binds_physical_z_absent_from_chart_unknowns():
    chart = _matched_stock_chart(stratum="edge")
    cell = PhaseCell(Interval(-1e-9, 1e-9))
    proof = prove_branch_cell(chart, cell, root_free_driven_components_rad=_FREE)
    assert proof.status == "PROVED", proof.reason
    assert chart.driven_z_index is None
    t_root, z_root = proof.driven_surface_root_box
    assert t_root == proof.root_box[chart.driver_stratum.algebra_coordinates]
    assert z_root == Interval.point(chart.driven_stratum.z_fixed) == Interval.point(1)
    approach = Interval(-0.05, 0.05)
    domain = ProofNeighbourhood(cell, chart.unknown_box, approach,
                               (Interval(0, 1), Interval(0.9, 1)))
    assert domain.refusal(proof, approach, "physical") is None  # binding, not first-contact proof
    assert domain.record()["driven_surface_domain"] == [[0, 1], [0.9, 1]]
    assert proof.record()["driven_surface_root_box"] == [t_root.record(), z_root.record()]
    # All algebra/phase/source/approach bounds are unchanged: only a fixed
    # physical coordinate absent from those algebra unknowns is omitted.
    outside_face = replace(domain, driven_surface_domain=(Interval(0, 1), Interval(-0.002, 0.002)))
    assert "free/fixed" in outside_face.refusal(proof, approach, "physical")
    ghost_face_point = replace(domain, driven_surface_domain=(Interval(0, 1), Interval.point(1)))
    assert "two-coordinate" in ghost_face_point.refusal(proof, approach, "physical")
    wrong_free_t = replace(domain, driven_surface_domain=(Interval(0, 0.1), Interval(0.9, 1)))
    assert "free/fixed" in wrong_free_t.refusal(proof, approach, "physical")


def test_real_finite_edge_domain_binds_fixed_profile_parameter_and_surface_receipts():
    edge = _FiniteParabolicSurface("edge", 0, edge=True, offset_index=1,
                                  unknown_box=(Interval(-0.1, 0.1), Interval(-0.3, 0.3),
                                               Interval(0.001, 0.003)))
    cell = PhaseCell(Interval(0.0009, 0.0011), _source())
    proof = prove_branch_cell(edge, cell, root_free_driven_components_rad=_FREE)
    assert proof.status == "PROVED", proof.reason
    assert proof.driven_surface_root_box[0] == Interval.point(0.5)  # real u=0, t=(u+1)/2
    cover = _cover(cell, (edge,))
    domain = cover.chart_minimum_bounds[0].neighbourhood
    assert domain.refusal(proof, cover.approach_driven_phase_rad, "physical") is None
    wrong_fixed_t = replace(domain, driven_surface_domain=(Interval(0.1, 0.4), Interval(-0.75, 0.75)))
    assert "free/fixed" in wrong_fixed_t.refusal(proof, cover.approach_driven_phase_rad, "physical")
    # Bind an actual open vertical cap's derivative receipt to the same
    # working-side neighbourhood. A different rectangle cannot be reused.
    cap = "edge:vertical_cap"
    valid = replace(cover, physical_patch_inventory=(*cover.physical_patch_inventory, cap),
                    chart_patch_ids=((edge.name, ("edge:lower", cap)),),
                    noncarrying_patch_ids=(*cover.noncarrying_patch_ids, cap),
                    boundary_separations=(BoundarySeparation(cap, edge.name, 1, Interval(0.25, 3), domain),))
    assert valid.refusal((proof,)) is None
    different = replace(domain, driven_surface_domain=(Interval(0.1, 0.5), Interval(-0.75, 0.75)))
    broken = replace(valid, boundary_separations=(replace(valid.boundary_separations[0], neighbourhood=different),))
    assert "different physical neighbourhoods" in broken.refusal((proof,))


def test_shared_physical_patch_requires_outside_union_exclusion_without_extra_tooth():
    a, b = _FiniteParabolicSurface("a", 0), _FiniteParabolicSurface("b", 1, slope=-1.1)
    cell = PhaseCell(Interval(-0.001, 0.001), _source())
    base = _cover(cell, (a, b))
    patch = "both_bounded_parabolic_patches"
    roots = base.root_patch_ids
    shared = replace(base, physical_patch_inventory=(patch, *roots),
                     chart_patch_ids=((a.name, (patch,)), (b.name, (patch,))))
    assert prove_paid_handover(a, b, cell, shared, driven_pitch_radius_mm=10)["status"] == "UNKNOWN"
    # Their two finite surfaces form one indexed physical search patch. Its
    # remainder is outside the UNION of the two radius-.75 neighborhoods;
    # both share the exact same conservative quadratic-gap lower bound.
    air = base.chart_minimum_bounds[0].outside_neighbourhood_air_mm
    shared = replace(shared, patch_remainder_bounds=(PatchRemainderBound(
        patch, (a.name, b.name), air,
        tuple((m.chart_name, m.neighbourhood) for m in base.chart_minimum_bounds)),))
    result = prove_paid_handover(a, b, cell, shared, driven_pitch_radius_mm=10)
    assert result["status"] == "PROVED", result["reason"]
    proofs = tuple(prove_branch_cell(s, cell, root_free_driven_components_rad=_FREE) for s in (a, b))
    domain = base.chart_minimum_bounds[0].neighbourhood
    different = replace(domain, driven_surface_domain=(Interval(0.25, 0.875), Interval(-0.75, 0.75)))
    assert different.refusal(proofs[0], shared.approach_driven_phase_rad, "physical") is None
    remainder = shared.patch_remainder_bounds[0]
    wrong_union = replace(shared, patch_remainder_bounds=(replace(
        remainder, neighbourhoods=((a.name, different), remainder.neighbourhoods[1])),))
    assert "different physical neighbourhoods" in wrong_union.refusal(proofs)
    duplicate = replace(shared, chart_patch_ids=((a.name, (patch, patch)), (b.name, (patch,))))
    assert prove_paid_handover(a, b, cell, duplicate, driven_pitch_radius_mm=10)["status"] == "UNKNOWN"


@pytest.mark.parametrize("defect", ["missing_anchor", "zero_air", "wrong_sense", "reference_after_root", "root_component_gap"])
def test_first_contact_needs_genuine_free_reference_and_full_root_free_approach(defect):
    a, b = _FiniteParabolicSurface("a", 0), _FiniteParabolicSurface("b", 1, slope=-1.1)
    cell = PhaseCell(Interval(-0.001, 0.001), _source())
    cover = _cover(cell, (a, b))
    if defect == "missing_anchor":
        cover = replace(cover, free_reference_driven_phase_rad=None)
    elif defect == "zero_air":
        cover = replace(cover, free_reference_air_mm=Interval(0, 0.01))
    elif defect == "wrong_sense":
        cover = replace(cover, closing_driven_sense=-1)
    elif defect == "reference_after_root":
        cover = replace(cover, free_reference_driven_phase_rad=Interval.point(0.19))
    else:
        cover = replace(cover, root_free_driven_components_rad=(Interval(-0.3, -0.15), Interval(-0.14, 0.3)))
    result = prove_paid_handover(a, b, cell, cover, driven_pitch_radius_mm=10)
    assert result["status"] == "UNKNOWN"
    assert not result["physical_no_solution"] and not result["continuous"]


def test_handover_record_recomputes_paid_same_source_difference_from_center_proofs():
    a, b = _FiniteParabolicSurface("a", 0), _FiniteParabolicSurface("b", 1, slope=-1.1)
    cell = PhaseCell(Interval(-0.001, 0.001), _source())
    result = prove_paid_handover(a, b, cell, _cover(cell, (a, b)), driven_pitch_radius_mm=10)
    assert result["status"] == "PROVED", result["reason"]
    centers = result["center_branch_proofs"]
    reconstructed = (Interval(*centers[1]["driven_phase_enclosure_rad"])
                     - Interval(*centers[0]["driven_phase_enclosure_rad"]))
    for bound, derivative in zip(result["difference_parameter_bounds"], result["difference_parameter_derivatives"]):
        parameter = Interval(*bound)
        reconstructed += Interval(*derivative) * (parameter - Interval.point(parameter.midpoint))
    assert reconstructed == Interval(*result["same_pose_driven_root_difference_rad"])
    assert (Interval.point(10) * reconstructed.magnitude).upper == result["pitch_displacement_jump_upper_mm"]
    assert len(result["endpoint_difference_proofs"]) == 2
    for endpoint in result["endpoint_difference_proofs"]:
        assert len(endpoint["center_branch_proofs"]) == len(endpoint["branch_proofs"]) == 2
        assert endpoint["difference_parameter_names"] == list(cell.parameter_names)


def test_signed_lagrangian_transversality_cannot_be_replaced_by_absolute_raw_gap_rate():
    a, b = _FiniteParabolicSurface("a", 0), _FiniteParabolicSurface("b", 1, slope=-1.1)
    cell = PhaseCell(Interval(-0.001, 0.001), _source())
    cover = _cover(cell, (a, b))
    # Magnitude remains one, but the actual signed derivative is opening, not
    # closing. An abs(raw h_beta) shortcut would falsely accept this control.
    minimum = replace(cover.chart_minimum_bounds[0], lagrangian_beta_derivative=Interval.point(1))
    bad = replace(cover, chart_minimum_bounds=(minimum, cover.chart_minimum_bounds[1]))
    result = prove_paid_handover(a, b, cell, bad, driven_pitch_radius_mm=10)
    assert result["status"] == "UNKNOWN" and not result["continuous"]


@pytest.mark.parametrize("axis_cross", [0.2, math.pi / 2])
def test_actual_supported_source_box_pays_physical_clock_and_screw_translation(axis_cross):
    chart = _matched_stock_chart(axis_cross_rad=axis_cross)
    source = SourcePose((("driver_clock_rad", Interval(-1e-9, 1e-9)),
                         ("driven_clock_rad", Interval(-0.02, 0.02)),
                         ("driven_dz_mm", Interval(-1e-8, 1e-8))))
    cell = PhaseCell(Interval(-1e-10, 1e-10), source)
    proof = prove_branch_cell(chart, cell, root_free_driven_components_rad=_FREE)
    assert proof.status == "PROVED", proof.reason
    phase, driver_clock, driven_clock, driven_dz = proof.source_gradient_rad
    assert driver_clock == phase  # they enter the SAME actual material angle
    assert driven_clock == Interval.point(-1)  # exact stock-coordinate symmetry
    assert driven_dz.contains(1 / chart.pair.driven.lead_per_radian_mm)
    assert proof.driven_phase_rad.width > 0.039  # physical clock is NOT hidden
    assert proof.driven_material_phase_rad.width < 1e-6
    assert all(row[2] == Interval.point(0) for row in chart.evaluate(cell, proof.root_box).parameter_jacobian)
    if axis_cross == math.pi / 2:
        assert abs(chart.pair.placement.driven_frame[2, 2]) < 1e-14
    delta, proofs, _ = correlated_root_difference(chart, chart, cell, root_free_driven_components_rad=_FREE)
    assert all(p.status == "PROVED" for p in proofs)
    assert delta.magnitude < 1e-6  # same source, not .04+.04 independent widths
    assert proof.record()["proof_schema"] == "finite-stock-common-normal-continuation/1"


def test_actual_chart_world_residual_matches_public_screw_with_material_clock_mapping():
    chart = _matched_stock_chart()
    p = chart.pair.placement
    cell = PhaseCell(Interval.point(0.012),
                     SourcePose((("driver_clock_rad", Interval.point(0.001)),
                                 ("driven_clock_rad", Interval.point(0.019)))))
    values = (0.46, 0.1, 0.44, -0.1, 0.016)  # actual t/z, then beta*
    data = chart.evaluate(cell, tuple(Interval.point(v) for v in values))
    driver_placement = replace(p, driven_origin_mm=p.driver_origin_mm, driven_frame=p.driver_frame)
    driver = screw_point(chart.pair.driver, chart.driver_stratum.segment.point(values[0]),
                         values[1], chart.driver_stratum.tooth, 0.012 + p.driver_clocking_rad + 0.001,
                         driver_placement)
    driven = screw_point(chart.pair.driven, chart.driven_stratum.segment.point(values[2]),
                         values[3], chart.driven_stratum.tooth, values[4], p)
    assert all(bound.contains(actual) for bound, actual in zip(data.residual[:3], driver - driven))
    # Omitting physical->material clock mapping is a genuinely different
    # screw realization, not an alternative accepted normal mapper.
    wrong = screw_point(chart.pair.driven, chart.driven_stratum.segment.point(values[2]),
                        values[3], chart.driven_stratum.tooth, values[4] - 0.019, p)
    assert not all(bound.contains(actual) for bound, actual in zip(data.residual[:3], driver - wrong))


def test_material_component_mapping_does_not_fill_a_real_component_gap():
    chart = _matched_stock_chart()
    cell = PhaseCell(Interval(-1e-10, 1e-10),
                     SourcePose((("driven_clock_rad", Interval(-0.02, 0.02)),)))
    narrow = (Interval(-1e-4, 1e-4),)
    physical = prove_branch_cell(chart, cell, root_free_driven_components_rad=narrow)
    assert physical.status == "UNKNOWN"  # no independent marginal physical INNER
    material = prove_branch_cell(chart, cell, root_free_driven_components_rad=narrow,
                                 root_free_coordinate="driven_material")
    assert material.status == "PROVED", material.reason
    assert material.root_component_coordinate == "driven_material"
    gap = prove_branch_cell(chart, cell, root_free_coordinate="driven_material",
                            root_free_driven_components_rad=(Interval(-0.1, -1e-4), Interval(1e-4, 0.1)))
    assert gap.status == "UNKNOWN"


@pytest.mark.parametrize("band", ["shoulder", "turned_tip", "turned_corner"])
def test_actual_placement_cut_law_has_supported_shoulder_and_turned_tip_cones(band):
    chart = _matched_stock_chart(driver_band=band)
    proof = prove_branch_cell(chart, PhaseCell(Interval(-1e-10, 1e-10)),
                              root_free_driven_components_rad=_FREE)
    assert proof.status == "PROVED", proof.reason
    data = chart.evaluate(proof.cell, proof.root_box)
    expected = 3 if band == "turned_corner" else 2
    assert len(data.cone_generators_world[0]) == expected
    assert all(w.lower > 0 for w in data.cone_weights[0])
    record = proof.record()["physical_strata"]["driver"]
    if band == "shoulder":
        assert record["axial_cap_source"] == "driver_shoulder"
        assert record["z_fixed"] == chart.pair.placement.driver_shoulder_z_mm
        assert "driver_shoulder_edge_outside_actual_turned_radius" in dict(data.margins)
    else:
        assert record["radial_cap_radius_mm"] == chart.pair.placement.driver_turned_radius_mm
        assert record["radial_cap_source"] == "Placement.driver_turned_radius_mm"
        assert data.residual[-1].contains(0)
        assert "driver_turned_cap_above_actual_shoulder" in dict(data.margins)
    assert not any(s.radial_cap_radius_mm is not None and s.axial_cap_source == "driver_shoulder"
                   for s in contact_strata(chart.pair, "driver", 0))  # reentrant, not convex


def test_shoulder_edge_inside_turn_and_cylinder_tip_below_shoulder_are_not_material_boundaries():
    shoulder = _matched_stock_chart(driver_band="shoulder")
    t = shoulder.unknown_box[0].midpoint
    radius = math.hypot(*shoulder.driver_stratum.segment.point(t))
    wrong_cut = replace(shoulder.pair.placement, driver_turned_radius_mm=radius + 0.02)
    moved = replace(shoulder, pair=replace(shoulder.pair, placement=wrong_cut))
    proof = prove_branch_cell(moved, PhaseCell(Interval(-1e-10, 1e-10)), root_free_driven_components_rad=_FREE)
    assert proof.status == "UNKNOWN" and "shoulder_edge" in proof.reason
    tip = _matched_stock_chart(driver_band="turned_tip")
    raised = replace(tip.pair.placement, driver_shoulder_z_mm=0.5)  # point remains at z=0
    moved = replace(tip, pair=replace(tip.pair, placement=raised))
    proof = prove_branch_cell(moved, PhaseCell(Interval(-1e-10, 1e-10)), root_free_driven_components_rad=_FREE)
    assert proof.status == "UNKNOWN" and "above_actual_shoulder" in proof.reason


def test_authoritative_incident_segment_cannot_be_swapped_for_another_profile_or_endpoint():
    chart = _matched_stock_chart(driver_tip=True)
    a = chart.driver_stratum
    foreign = next(s for s in chart.pair.driven.external_boundary_segments() if s.kind == "tip_arc")
    with pytest.raises(ValueError, match="incident"):
        replace(chart, driver_stratum=replace(a, incident_segments=((foreign, 0.0),)))
    incident, coordinate = a.incident_segments[0]
    with pytest.raises(ValueError, match="incident"):
        replace(chart, driver_stratum=replace(a, incident_segments=((incident, 1 - coordinate),)))


def test_coverage_refuses_a_relabelled_cell_and_does_not_count_a_deeper_tooth():
    a = _FiniteParabolicSurface("first", 0)
    b = _FiniteParabolicSurface("deeper", 1, offset=0.001)
    item = _proved_cell(0, 0.002, (a, b))
    summary = retained_phase_coverage((item,), driver_pitch_rad=0.002, driven_pitch_radius_mm=10)
    assert summary["status"] == "PROVED"
    assert 0.99 < summary["stock_form_coverage_lower"] <= 1
    record = summary["carrier_cells"][0]
    assert record["counted_teeth"] == [0]
    deeper = next(v for v in record["carrier_comparisons"] if v["driven_tooth"] == 1)
    assert not deeper["eligible"]
    assert deeper["same_pose_comparisons"][0]["pitch_excess_upper_mm"] > 0.005
    short, proofs, cover = _proved_cell(0, 0.001, (a,))
    mislabeled = (PhaseCell(Interval(0, 0.002), short.source_pose), proofs, cover)
    assert retained_phase_coverage((mislabeled,), driver_pitch_rad=0.002,
                                    driven_pitch_radius_mm=10)["status"] == "UNKNOWN"


@pytest.mark.parametrize("defect", ["absent", "other_cell", "wrong_coordinate", "smaller_chart",
                                  "short_approach", "zero_dimension", "surface_absent",
                                  "surface_point", "surface_wrong_t", "surface_wrong_z"])
def test_minimum_certificate_is_bound_to_real_chart_cell_neighbourhood_and_approach(defect):
    a, b = _FiniteParabolicSurface("a", 0), _FiniteParabolicSurface("b", 1, slope=-1.1)
    cell = PhaseCell(Interval(-0.001, 0.001), _source())
    cover = _cover(cell, (a, b))
    minimum = cover.chart_minimum_bounds[0]
    domain = minimum.neighbourhood
    if defect == "absent":
        minimum = replace(minimum, neighbourhood=None)
    elif defect == "other_cell":
        minimum = replace(minimum, neighbourhood=replace(domain, cell=PhaseCell(Interval(-0.0005, 0.0005), _source())))
    elif defect == "wrong_coordinate":
        minimum = replace(minimum, neighbourhood=replace(domain, angle_coordinate="driven_material"))
    elif defect == "smaller_chart":
        minimum = replace(minimum, neighbourhood=replace(domain, unknown_domain=(Interval(-0.01, 0.01),) * 3))
    elif defect == "short_approach":
        minimum = replace(minimum, neighbourhood=replace(domain, approach_driven_phase_rad=Interval(-0.1, 0.1)))
    elif defect == "surface_absent":
        minimum = replace(minimum, neighbourhood=replace(domain, driven_surface_domain=None))
    elif defect == "surface_point":
        minimum = replace(minimum, neighbourhood=replace(
            domain, driven_surface_domain=(Interval.point(0.5), Interval(-0.75, 0.75))))
    elif defect == "surface_wrong_t":
        minimum = replace(minimum, neighbourhood=replace(
            domain, driven_surface_domain=(Interval(0.1, 0.2), Interval(-0.75, 0.75))))
    elif defect == "surface_wrong_z":
        minimum = replace(minimum, neighbourhood=replace(
            domain, driven_surface_domain=(Interval(0.125, 0.875), Interval(0.2, 0.3))))
    else:
        minimum = replace(minimum, tangent_dimension=0, tangent_hessian_lower=-1)
    refused = prove_paid_handover(a, b, cell, replace(cover, chart_minimum_bounds=(minimum, cover.chart_minimum_bounds[1])),
                                  driven_pitch_radius_mm=10)
    assert refused["status"] == "UNKNOWN" and not refused["physical_no_solution"]


def test_profile_error_payment_has_real_stock_provenance_and_is_present_in_handover_formula():
    chart = _matched_stock_chart()
    proof = prove_branch_cell(chart, PhaseCell(Interval(-1e-10, 1e-10)), root_free_driven_components_rad=_FREE)
    assert proof.status == "PROVED", proof.reason
    assert proof.geometry_error_bound_mm >= chart.pair.driver.geometry_error_bound_mm + chart.pair.driven.geometry_error_bound_mm
    # This isolates the payment algebra, NOT a fabricated whole-stock
    # first-contact cover. Its positive scalar slope/gradient are units for
    # the independently tested error converter; no continuity is asserted.
    minimum = ChartMinimumBound(chart.name, 2, 1, Interval(1, 2), 0.5,
                                Interval(0.5, 1), 1, objective_gradient_magnitude_upper_per_mm=2)
    assert branch_geometry_error_rad(proof, minimum, additional_geometry_error_mm=0.0) >= 4 * proof.geometry_error_bound_mm
    a, b = _FiniteParabolicSurface("a", 0), _FiniteParabolicSurface("b", 1, slope=-1.1)
    cell = PhaseCell(Interval(-0.001, 0.001), _source())
    result = prove_paid_handover(a, b, cell, _cover(cell, (a, b)), driven_pitch_radius_mm=10)
    assert result["status"] == "PROVED", result["reason"]
    difference = Interval(*result["same_pose_driven_root_difference_rad"])
    payment = Interval(*result["physical_geometry_error_payment_rad"])
    assert (Interval.point(10) * (Interval.point(difference.magnitude) + payment)).upper == result["pitch_displacement_jump_upper_mm"]
    generic = prove_branch_cell(a, cell, root_free_driven_components_rad=_FREE).record()
    assert generic["proof_schema"] == "finite-analytic-contact-continuation/1"
    assert generic["physical_strata"] == {} and not generic["native_certificate"]


def _cover_with_additional_geometry(cell,surfaces,extra):
    cover = _cover(cell,surfaces)
    return replace(
        cover, additional_geometry_error_mm=extra,
        excluded_patch_air_mm=tuple((name,air-extra) for name,air in cover.excluded_patch_air_mm),
        free_reference_air_mm=cover.free_reference_air_mm-extra,
        chart_minimum_bounds=tuple(replace(
            minimum, outside_neighbourhood_air_mm=minimum.outside_neighbourhood_air_mm-extra,
            objective_gradient_padding_mm=math.nextafter(extra,math.inf))
            for minimum in cover.chart_minimum_bounds))


def test_joint_period_geometry_is_paid_once_in_actual_handover_and_neighbourhood():
    a,b = _FiniteParabolicSurface("a",0),_FiniteParabolicSurface("b",1,slope=-1.1)
    cell = PhaseCell(Interval(-0.001,0.001),_source())
    extra = 1e-6
    cover = _cover_with_additional_geometry(cell,(a,b),extra)
    result = prove_paid_handover(a,b,cell,cover,driven_pitch_radius_mm=10)
    assert result["status"] == "PROVED",result["reason"]
    # Both actual branch converters have |gradient|<=3 and |dF/dbeta|>=1.
    # This would fail if the extra error were omitted OR charged twice.
    payment = Interval(*result["physical_geometry_error_payment_rad"])
    assert 6*extra <= payment.upper < 6.01*extra
    missing_pad = replace(cover,chart_minimum_bounds=tuple(
        replace(minimum,objective_gradient_padding_mm=0.0) for minimum in cover.chart_minimum_bounds))
    refused = prove_paid_handover(a,b,cell,missing_pad,driven_pitch_radius_mm=10)
    assert refused["status"] == "UNKNOWN" and "additional geometry" in refused["reason"]
    too_wide = prove_paid_handover(a,b,cell,_cover_with_additional_geometry(cell,(a,b),1e-4),
                                  driven_pitch_radius_mm=10)
    assert too_wide["status"] == "UNKNOWN" and "geometry payment" in too_wide["reason"]


def test_joint_period_payment_changes_same_pose_first_carrier_coverage():
    a,b = _FiniteParabolicSurface("a",0),_FiniteParabolicSurface("b",1,slope=-1.1)
    cell = PhaseCell(Interval(0,0.002),_source())
    _,proofs,_ = correlated_root_difference(a,b,cell,root_free_driven_components_rad=_FREE)
    assert all(proof.status == "PROVED" for proof in proofs)
    narrow = retained_phase_coverage(((cell,proofs,_cover_with_additional_geometry(cell,(a,b),1e-6)),),
                                     driver_pitch_rad=0.002,driven_pitch_radius_mm=10)
    wide = retained_phase_coverage(((cell,proofs,_cover_with_additional_geometry(cell,(a,b),1e-4)),),
                                   driver_pitch_rad=0.002,driven_pitch_radius_mm=10)
    assert narrow["status"] == "PROVED" and narrow["stock_form_coverage_lower"] > 1.99
    assert wide["status"] == "UNKNOWN" and wide["stock_form_coverage_lower"] == 0
    assert not wide["native_certificate"]


@pytest.mark.parametrize("extra",[-1.0,math.inf,math.nan,True])
def test_additional_geometry_is_a_required_finite_nonnegative_physical_bound(extra):
    surface = _FiniteParabolicSurface("a",0)
    cell = PhaseCell(Interval(-0.001,0.001),_source())
    proof = prove_branch_cell(surface,cell,root_free_driven_components_rad=_FREE)
    cover = _cover(cell,(surface,))
    assert "additional geometry" in replace(cover,additional_geometry_error_mm=extra).refusal((proof,))
    with pytest.raises(ValueError):
        branch_geometry_error_rad(proof,cover.chart_minimum_bounds[0],additional_geometry_error_mm=extra)
    with pytest.raises(TypeError):
        branch_geometry_error_rad(proof,cover.chart_minimum_bounds[0])


def test_a_supported_native_point_does_not_reserve_a_wide_phase_cell():
    chart = _matched_stock_chart()
    point = prove_branch_cell(chart, PhaseCell(Interval.point(0)), root_free_driven_components_rad=_FREE)
    assert point.status == "PROVED", point.reason
    wide = prove_branch_cell(chart, PhaseCell(Interval(-0.01, 0.01)), root_free_driven_components_rad=_FREE)
    assert wide.status == "UNKNOWN"  # the genuine root cannot fit the point's chart box


def test_center_numerical_root_and_carrier_payment_records_are_reader_recomputable():
    a, b = _FiniteParabolicSurface("a", 0), _FiniteParabolicSurface("b", 1, offset=0.001)
    item = _proved_cell(0, 0.002, (a, b))
    result = retained_phase_coverage((item,), driver_pitch_rad=0.002, driven_pitch_radius_mm=10)
    carrier = result["carrier_cells"][0]
    records = {p["chart"]: p for p in carrier["branch_proofs"]}
    for proof in records.values():
        assert 0 <= proof["center_contraction_upper"] < 1
        index = proof["driven_angle_unknown_index"]
        assert proof["center_root_box"][index] == proof["center_driven_phase_enclosure_rad"]
        assert proof["center_phase_cell_rad"] == [0.001, 0.001]
        assert proof["center_source_pose"] == {"driver_dz_mm": [0.0, 0.0]}
    for candidate in carrier["carrier_comparisons"]:
        c = records[candidate["chart"]]
        for comparison in candidate["same_pose_comparisons"]:
            d = records[comparison["competitor_chart"]]
            excess = (Interval(*c["center_driven_phase_enclosure_rad"])
                      - Interval(*d["center_driven_phase_enclosure_rad"]))
            for name, bounds, derivative in zip(item[0].parameter_names, item[0].parameter_bounds,
                                                comparison["difference_parameter_derivatives"]):
                assert name in comparison["difference_parameter_names"]
                excess += Interval(*derivative) * (bounds - Interval.point(bounds.midpoint))
            assert excess == Interval(*comparison["closing_root_excess_rad"])
            paid = Interval(*comparison["physical_geometry_error_payment_rad"])
            assert (Interval.point(10) * (Interval.point(excess.upper) + paid)).upper == comparison["pitch_excess_upper_mm"]


def test_tip_arc_main_is_not_a_working_flank_lagrangian_and_g1_join_is_not_a_corner():
    pair = _pair()
    perimeter = pair.driver.external_boundary_segments()
    assert {"radial", "flank"} <= {s.kind for s in perimeter}  # control is not vacuous
    strata = contact_strata(pair, "driver", 0)
    assert not any({s.segment.kind, *(v.kind for v, _ in s.incident_segments)} == {"radial", "flank"}
                   for s in strata)
    circle = next(s for s in strata if s.segment.kind == "tip_arc" and s.free_coordinates == 2)
    driven = next(s for s in contact_strata(pair, "driven", 0)
                  if s.segment.kind == "flank" and s.free_coordinates == 2)
    box = (Interval(0.4, 0.6), Interval(-0.1, 0.1),
           Interval(0.4, 0.6), Interval(-0.1, 0.1), Interval(-0.01, 0.01))
    chart = StockContactChart(pair, circle, driven, box, 0)
    proof = prove_branch_cell(chart, PhaseCell(Interval.point(0)), root_free_driven_components_rad=_FREE)
    # A real finite tip land is not the driver working-side angular level set,
    # whether or not its separate common-normal branch has been proved.
    with pytest.raises(ArithmeticError, match="flank/radial main"):
        objective_kkt_multipliers(chart, proof, (Interval.point(1), Interval.point(0), Interval.point(0)))


def test_stored_nonorthogonal_frame_uses_true_inverse_and_rotated_covectors():
    pair = _pair()
    # This is INSIDE Placement's genuine tolerance but NOT an isometry.
    # Its inverse z factor is <1, while the tempting transpose factor is >1.
    nominal = np.diag((1.0, 1.0, 1.0 + 4e-13))
    pair = replace(pair, placement=replace(pair.placement, driver_frame=nominal))
    inverse = frame_inverse_bounds(nominal)
    assert inverse[2][2].upper < 1 < nominal.T[2, 2]
    point_pose = body_pose_bounds(pair, SourcePose(), Interval.point(0), Interval.point(0), body="driver")
    assert point_pose.inverse_frame[2][2].upper < 1  # pose API itself cannot use F.T
    point_covector = tuple(-row[2] for row in zip(*point_pose.inverse_frame))
    point_direction = tuple(row[2] for row in point_pose.frame)
    point_rate = sum(g * v for g, v in zip(point_covector, point_direction))
    assert point_rate.contains(-1) and point_rate.lower > -1 - 1e-13
    with pytest.raises(ArithmeticError, match="positive determinant"):
        frame_inverse_bounds(np.diag((1.0, 1.0, -1.0)))
    source = SourcePose((("driver_rx_rad", Interval(-0.001, 0.001)),
                         ("driver_ry_rad", Interval(-0.002, 0.002)),
                         ("driver_rz_rad", Interval(-0.001, 0.001))))
    pose = body_pose_bounds(pair, source, Interval.point(0), Interval.point(0), body="driver")
    for i in range(3):
        for j in range(3):
            identity = sum(pose.inverse_frame[i][k] * pose.frame[k][j] for k in range(3))
            assert identity.contains(int(i == j))
    assert pose.frame_determinant.lower > 1
    # Whole-box consistency enclosures for the true c=z_face-z covector.
    # The point control above, not these wider boxes, discriminates F.T.
    covector = tuple(-row[2] for row in zip(*pose.inverse_frame))
    direction = tuple(row[2] for row in pose.frame)
    assert sum(g * v for g, v in zip(covector, direction)).contains(-1)


def test_actual_local_cap_face_multiplier_scales_do_not_use_world_generator_norms():
    shoulder = _matched_stock_chart(driver_band="shoulder")
    stretched = np.diag((1.0, 1.0, 1.0 + 4e-13))
    shoulder = replace(shoulder, pair=replace(shoulder.pair, placement=replace(
        shoulder.pair.placement, driver_frame=stretched)))
    face_factor, = constraint_covector_scales(shoulder, "driver")
    world_face_norm = np.linalg.norm(np.cross(stretched[:, 0], stretched[:, 1]))
    assert world_face_norm == 1
    assert face_factor.lower > world_face_norm  # old unit-world formula fails
    proof = prove_branch_cell(shoulder, PhaseCell(Interval(-1e-10, 1e-10)),
                              root_free_driven_components_rad=_FREE)
    assert proof.status == "PROVED", proof.reason
    data = shoulder.evaluate(proof.cell, proof.root_box)
    main = data.cone_generators_world[0][0]
    alpha = sum(g * n for g, n in zip(main, main)) / _squared_norm(main)
    scale = alpha / data.cone_weights[0][0]
    actual = objective_kkt_multipliers(shoulder, proof, main)["driver"][0]
    assert actual == scale * data.cone_weights[0][1] * face_factor
    cap = _matched_stock_chart(driver_band="turned_tip")
    radial_stretch = np.diag((1.0 + 4e-13, 1.0, 1.0))
    cap = replace(cap, pair=replace(cap.pair, placement=replace(
        cap.pair.placement, driver_frame=radial_stretch)))
    cap_factor, = constraint_covector_scales(cap, "driver")
    radius = cap.driver_stratum.radial_cap_radius_mm
    assert cap_factor.lower > radius  # det(F)*Rt, not a raw local R
    # The true radius cap's point along local +X has world generator length R,
    # yet its LOCAL c=Rt-r covector conversion factor is det(F)*Rt > R.
    world_cap = np.cross(radial_stretch @ np.array((0.0, radius, 0.0)),
                         radial_stretch @ np.array((0.0, 0.0, 1.0)))
    assert cap_factor.lower > np.linalg.norm(world_cap)
    driven_tip = _matched_stock_chart(stratum="tip")
    old = driven_tip.pair.placement.driven_frame
    driven_tip = replace(driven_tip, pair=replace(driven_tip.pair, placement=replace(
        driven_tip.pair.placement, driven_frame=old @ radial_stretch)))
    driven_factor, = constraint_covector_scales(driven_tip, "driven")
    driver_factors = constraint_covector_scales(driven_tip, "driver")
    assert driver_factors == ()
    assert driven_factor.lower > driven_tip.pair.driven.blank_radius_mm


def _actual_periodic_endpoints():
    start = _matched_stock_chart()
    p, m = start.pair.driver.angular_pitch_rad, start.pair.driven.angular_pitch_rad
    box = list(start.unknown_box)
    box[start.offset_index] -= m
    end = replace(start, driver_stratum=replace(start.driver_stratum, tooth=start.pair.driver.teeth - 1),
                  driven_stratum=replace(start.driven_stratum, tooth=1), unknown_box=tuple(box))
    # Physical bore/runout grades, not manufactured branch intervals.
    term = 1e-9
    radius = (Interval.point(term) + Interval.point(term)).upper
    disks = {body: {"shape": "closed_disk", "centre_mm": [0.0, 0.0], "radius_mm": radius,
                    "source_terms_mm": {"bore_radial_upper": term, "tooth_runout_radius_upper": term}}
             for body in ("driver", "driven")}
    source = SourcePose(tuple((f"{body}_ecc_{axis}_mm", Interval(-radius, radius))
                              for body in ("driver", "driven") for axis in ("x", "y")) +
                        (("driver_clock_rad", Interval(-1e-8, 1e-8)),
                         ("driven_clock_rad", Interval(-1e-8, 1e-8))))
    cells = (PhaseCell(Interval.point(0), source), PhaseCell(Interval.point(p), source))
    proofs = tuple(prove_branch_cell(c, cell, root_free_driven_components_rad=_FREE,
                                     root_free_coordinate="driven_material")
                   for c, cell in zip((start, end), cells))
    assert all(proof.status == "PROVED" for proof in proofs), [proof.reason for proof in proofs]
    return start, end, cells, proofs, disks


def test_actual_periodic_branch_difference_uses_rotated_same_source_disk_and_paid_arc():
    start, end, cells, proofs, disks = _actual_periodic_endpoints()
    record = correlated_periodic_branch_difference(*proofs, start.pair, source_eccentricity_disks=disks)
    difference = Interval(*record["same_pose_driven_root_difference_rad"])
    assert difference.contains(0) and difference.magnitude < 1e-5
    independent = proofs[0].driven_phase_rad - start.pair.driven.angular_pitch_rad - proofs[1].driven_phase_rad
    assert independent.width > difference.width
    assert record["difference_parameter_names"] == [name for name, _ in cells[0].source_pose.axes]
    assert record["difference_parameter_derivatives"][-1] == [0.0, 0.0]  # same physical driven clock
    # Floating tooth pitches are not the real mathematical turn. The helper
    # pays finite relabel/product error, rather than declaring an exact zero.
    assert 0 < periodicity_displacement_bound_mm(start.pair, cells[0].source_pose) < 1e-8
    assert not record["native_certificate"]


def test_actual_periodic_source_rotation_matches_material_origin_not_unrotated_pose():
    start, end, cells, proofs, disks = _actual_periodic_endpoints()
    rotations = _periodic_source_relabel(start.pair, cells[0].source_pose, disks)
    q = {name: Interval.point(0) for name, _ in cells[0].source_pose.axes}
    radius = disks["driver"]["radius_mm"]
    for body in ("driver", "driven"):
        q[f"{body}_ecc_x_mm"] = Interval.point(radius)
    transformed = dict(q)
    for body, rotation in rotations.items():
        x, y = (f"{body}_ecc_{axis}_mm" for axis in ("x", "y"))
        transformed[x] = rotation[0][0] * q[x] + rotation[0][1] * q[y]
        transformed[y] = rotation[1][0] * q[x] + rotation[1][1] * q[y]
    original = SourcePose(tuple(q.items()))
    mapped = SourcePose(tuple(transformed.items()))
    p, m = start.pair.driver.angular_pitch_rad, start.pair.driven.angular_pitch_rad
    for body in ("driver", "driven"):
        a = body_pose_bounds(start.pair, mapped, Interval.point(0), Interval.point(0), body=body)
        b = body_pose_bounds(start.pair, original, Interval.point(p), Interval.point(-m), body=body)
        assert all((left - right).contains(0) for left, right in zip(a.origin_mm, b.origin_mm))
        wrong = body_pose_bounds(start.pair, original, Interval.point(0), Interval.point(0), body=body)
        assert any((left - right).magnitude > radius * 0.01 for left, right in zip(wrong.origin_mm, b.origin_mm))


@pytest.mark.parametrize("defect", ["rectangle", "offcentre", "negative_term", "too_small_radius", "asymmetric_axes"])
def test_periodic_source_refuses_unproved_rotated_rectangle_or_invented_disk(defect):
    start, end, cells, proofs, disks = _actual_periodic_endpoints()
    altered = {body: {**disk, "source_terms_mm": dict(disk["source_terms_mm"])} for body, disk in disks.items()}
    source = cells[0].source_pose
    if defect == "rectangle":
        altered["driver"]["shape"] = "rectangle"
    elif defect == "offcentre":
        altered["driver"]["centre_mm"] = [1e-9, 0.0]
    elif defect == "negative_term":
        altered["driver"]["source_terms_mm"]["bore_radial_upper"] = -1e-9
    elif defect == "too_small_radius":
        altered["driver"]["radius_mm"] *= 0.9
    else:
        source = SourcePose(tuple((name, Interval(-value.upper, value.upper * 1.1))
                                  if name == "driver_ecc_x_mm" else (name, value)
                                  for name, value in source.axes))
    with pytest.raises(ValueError):
        _periodic_source_relabel(start.pair, source, altered)


def test_real_periodic_roots_cannot_replace_actual_first_contact_or_root_receipts():
    start, end, cells, proofs, disks = _actual_periodic_endpoints()
    # The two actual supported endpoint roots above say nothing about the
    # other real teeth, caps or root air. An empty physical cover must refuse.
    covers = tuple(FirstContactCover(cell, _FREE, 0.1, Interval(-0.3, 0.3), (),
                                    (), (), (), 0.01, angle_coordinate="driven_material",
                                    additional_geometry_error_mm=0.0)
                   for cell in cells)
    result = prove_periodic_seam((start,), cells[0], covers[0], (end,), cells[1], covers[1],
                                start_branch_proofs=(proofs[0],), end_branch_proofs=(proofs[1],),
                                source_eccentricity_disks=disks, root_receipt={},
                                driven_root_material_receipt={},
                                root_air_requirements_mm={"driver": 0.01, "driven": 0.01},
                                driven_pitch_radius_mm=start.pair.driven.pitch_radius_mm)
    assert result["status"] == "UNKNOWN" and not result["physical_no_solution"]
    assert not result["native_certificate"] and "pitch_displacement_jump_upper_mm" not in result


def test_periodic_gradient_uses_transposed_source_chain_rule_not_forward_rotation():
    start, _, cells, proofs, disks = _actual_periodic_endpoints()
    receipt = correlated_periodic_branch_difference(*proofs,start.pair,source_eccentricity_disks=disks)
    rotations = _periodic_source_relabel(start.pair,cells[0].source_pose,disks)
    names = receipt["difference_parameter_names"]
    a = dict(zip(names,proofs[0].source_gradient_rad[1:]))
    b = dict(zip(names,proofs[1].source_gradient_rad[1:]))
    discriminators = 0
    for body,matrix in rotations.items():
        x,y = (f"{body}_ecc_{axis}_mm" for axis in ("x","y"))
        expected = (a[x]*matrix[0][0]+a[y]*matrix[1][0]-b[x],
                    a[x]*matrix[0][1]+a[y]*matrix[1][1]-b[y])
        wrong = (a[x]*matrix[0][0]+a[y]*matrix[0][1]-b[x],
                 a[x]*matrix[1][0]+a[y]*matrix[1][1]-b[y])
        for name,correct,transposed in zip((x,y),expected,wrong):
            actual = Interval(*receipt["difference_parameter_derivatives"][names.index(name)])
            assert actual == correct
            discriminators += actual.intersection(transposed) is None
    assert discriminators, "actual anisotropic stock sensitivities must distinguish R.T from R"


def test_periodic_rounding_payment_composes_through_both_tooth_label_cycles():
    start, _, cells, _, _ = _actual_periodic_endpoints()
    total,bodies = _periodicity_displacement_evidence(start.pair,cells[0].source_pose)
    steps = math.lcm(start.pair.driver.teeth,start.pair.driven.teeth)
    assert steps > 1
    accumulated = Interval.point(0)
    for receipt in bodies.values():
        assert receipt["joint_period_tooth_steps"] == steps
        one = receipt["one_step_displacement_upper_mm"]
        assert one > 0
        assert receipt["displacement_upper_mm"] >= (Interval.point(steps)*one).upper
        assert receipt["displacement_upper_mm"] > one
        accumulated += receipt["displacement_upper_mm"]
    assert total >= accumulated.upper


@pytest.mark.parametrize("competitor_offset,expected",[(0.01,"PROVED"),(-0.01,"UNKNOWN")])
def test_paid_handover_binds_all_real_competitors_not_only_its_pair(competitor_offset,expected):
    a,b = _FiniteParabolicSurface("a",0),_FiniteParabolicSurface("b",1,slope=-1.1)
    competitor = _FiniteParabolicSurface("third",2,slope=-1.05,offset=competitor_offset)
    surfaces = a,b,competitor
    cell = PhaseCell(Interval(-0.001,0.001),_source())
    proofs = tuple(prove_branch_cell(s,cell,root_free_driven_components_rad=_FREE) for s in surfaces)
    assert all(p.status == "PROVED" for p in proofs)
    result = prove_paid_handover(a,b,cell,_cover(cell,surfaces),driven_pitch_radius_mm=10,
                                first_contact_branch_proofs=proofs)
    assert result["status"] == expected
    assert len(result["first_contact_branch_proofs"]) == 3
    assert len(result["full_cell_competitor_exclusions"]) == 1
    if expected == "UNKNOWN":
        assert "another physical root may intervene" in result["reason"]
    else:
        assert result["continuous"] and result["pitch_displacement_jump_upper_mm"] <= 0.005


@pytest.mark.parametrize("scale",[1.0,1e-12])
def test_sum_of_nonnegative_squares_retains_its_domain_after_outward_addition(scale):
    components = tuple(Interval(-factor*scale,factor*scale) for factor in (1,2,3))
    squared = _squared_norm(components)
    assert squared.lower == 0.0
    assert squared.upper > 0.0
    norm = sqrt_bounds(squared)
    assert norm.lower == 0.0
    assert norm.contains(math.hypot(scale,2*scale,3*scale))
    assert norm.contains(0.0)
    positive = _squared_norm((Interval.point(3),Interval.point(4)))
    assert 0 < positive.lower <= 25 <= positive.upper
    assert sqrt_bounds(positive).contains(5)
    mixed = _squared_norm((Interval(-1,1),Interval(3,4),Interval(-2,2)))
    assert mixed.lower > 0 and mixed.contains(9) and mixed.contains(21)
    assert sqrt_bounds(mixed).contains(3) and sqrt_bounds(mixed).contains(math.sqrt(21))


def test_generic_square_root_still_refuses_genuinely_negative_domain():
    with pytest.raises(ArithmeticError,match="not nonnegative"):
        sqrt_bounds(Interval(-math.ulp(0.0),1.0))
    from stock_form_contact_certificate import _bound_sqrt
    with pytest.raises(ValueError,match="negative"):
        _bound_sqrt((-math.ulp(0.0),1.0))


def test_underflowing_sum_of_squares_keeps_positive_upper_enclosure():
    squared = _squared_norm((Interval(-1e-200,1e-200),Interval(-2e-200,2e-200)))
    assert squared.lower == 0.0
    assert squared.upper > 0.0
    assert sqrt_bounds(squared).contains(math.hypot(1e-200,2e-200))


def _assert_exact_sqrt_endpoint_squares(bounds, result):
    low, high = result
    low_n, low_d = low.as_integer_ratio()
    high_n, high_d = high.as_integer_ratio()
    input_low_n, input_low_d = bounds[0].as_integer_ratio()
    input_high_n, input_high_d = bounds[1].as_integer_ratio()
    assert low >= 0
    assert low_n*low_n*input_low_d <= input_low_n*low_d*low_d
    assert high_n*high_n*input_high_d >= input_high_n*high_d*high_d


@pytest.mark.parametrize("bounds",[
    (0.0,0.0), (0.0,5e-324), (5e-324,5e-324),
    (5e-324,3e-323), (5e-324,1.0), (4.0,9.0),
    (1.7976931348623157e308,1.7976931348623157e308),
])
def test_square_root_certifies_exact_dyadic_squares_without_underflow_walk(bounds,monkeypatch):
    from stock_form_contact_certificate import _bound_sqrt
    original_nextafter = math.nextafter
    calls = 0

    def bounded_nextafter(value,direction):
        nonlocal calls
        calls += 1
        # A dropped repair fails promptly instead of hanging this regression.
        assert calls <= 16, "sqrt endpoint correction walks a rounded subnormal square bin"
        return original_nextafter(value,direction)

    monkeypatch.setattr(math,"nextafter",bounded_nextafter)
    measured = sqrt_bounds(Interval(*bounds))
    _assert_exact_sqrt_endpoint_squares(bounds,measured.record())
    calls = 0
    replay = _bound_sqrt(bounds)
    _assert_exact_sqrt_endpoint_squares(bounds,replay)
    assert replay == (measured.lower,measured.upper)


@pytest.mark.parametrize("bounds",[(0.0,math.inf),(math.nan,1.0),(2.0,1.0)])
def test_square_root_endpoints_remain_finite_and_ordered(bounds):
    from stock_form_contact_certificate import _bound_sqrt
    with pytest.raises(ValueError,match="finite and ordered"):
        Interval(*bounds)
    with pytest.raises(ValueError,match="finite and ordered"):
        _bound_sqrt(bounds)


def test_real_root_sample_inverse_error_has_a_nonnegative_norm_domain(monkeypatch):
    from diagnostics import stock_form_root_sweep as roots
    from diagnostics.stock_form_contact_3d import ContactSearch
    angle = .2
    frame = np.array(((math.cos(angle),-math.sin(angle),0.0),
                      (math.sin(angle),math.cos(angle),0.0),(0.0,0.0,1.0)))
    pair = _pair(origin=(60.0,2.0,3.0))
    pair = replace(pair,placement=replace(pair.placement,driver_frame=frame))
    seen = []
    original = roots.sqrt_bounds

    def observed(value):
        seen.append(value)
        return original(value)

    monkeypatch.setattr(roots,"sqrt_bounds",observed)
    result = roots.root_free_intervals(ContactSearch(pair,0.0),max_boxes=1)
    assert result.status == "budget_exhausted"
    assert result.boxes == 1
    assert any(value.lower == 0.0 and 0 < value.upper < 1e-12 for value in seen)


def test_periodic_eccentricity_norm_keeps_whole_vector_nonnegative_domain():
    from stock_form_contact_certificate import _bound_squared_norm, _periodic_source_evidence, same_numeric_tree
    pair = _pair()
    pose = SourcePose(tuple(
        (f"{body}_ecc_{axis}_mm",Interval(-radius,radius))
        for body,radius in (("driver",.03),("driven",.05)) for axis in ("x","y")))
    total,evidence = _periodicity_displacement_evidence(pair,pose)
    replay,replayed,_ = _periodic_source_evidence(
        pair.driver,pair.driven,pair.placement.record(),pose.record())
    assert total > 0 and total == replay
    assert same_numeric_tree(evidence,replayed)
    for body,radius in (("driver",.03),("driven",.05)):
        assert evidence[body]["displacement_upper_mm"] > 0
        vector = (Interval(-radius,radius),Interval(-radius,radius),Interval(-radius,radius))
        assert _bound_squared_norm(tuple(value.record() for value in vector)) == tuple(_squared_norm(vector).record())


@pytest.mark.parametrize("radius",[0.0,1e-200])
def test_actual_nominal_and_tiny_eccentricity_norm_callers_replay_exact_squares(radius,monkeypatch):
    from diagnostics import stock_form_contact_continuation as continuation
    import stock_form_contact_certificate as reader
    pair = _pair()
    pose = SourcePose(tuple(
        (f"{body}_ecc_{axis}_mm",Interval(-radius,radius))
        for body in ("driver","driven") for axis in ("x","y")))
    measured_inputs, replay_inputs = [], []
    original_measure, original_replay = continuation.sqrt_bounds,reader._bound_sqrt

    def measured(value):
        result = original_measure(value)
        measured_inputs.append(tuple(value.record()))
        _assert_exact_sqrt_endpoint_squares(value.record(),result.record())
        return result

    def replayed(value):
        result = original_replay(value)
        replay_inputs.append(tuple(value))
        _assert_exact_sqrt_endpoint_squares(value,result)
        return result

    monkeypatch.setattr(continuation,"sqrt_bounds",measured)
    monkeypatch.setattr(reader,"_bound_sqrt",replayed)
    total,evidence = _periodicity_displacement_evidence(pair,pose)
    replay,replay_evidence,_ = reader._periodic_source_evidence(
        pair.driver,pair.driven,pair.placement.record(),pose.record())
    assert total == replay and reader.same_numeric_tree(evidence,replay_evidence)
    assert measured_inputs == replay_inputs
    if radius == 0:
        assert measured_inputs.count((0.0,0.0)) == 2
    else:
        assert sum(0 < upper < 1e-320 for _,upper in measured_inputs) == 2
