"""Actual-stock material/3D contact controls; no ideal-profile calibration pins."""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "diagnostics"))
import stock_form_contact_3d as contact
import crossed_mesh_study as cms
from stock_form_cutter import StockFormProfile, template_for_teeth
from diagnostics import stock_form_contact_continuation as continuation


def test_band_removes_only_the_actual_north_tooth_tips() -> None:
    profile = cms.pinion_spec.STOCK_PROFILE
    lookup = cms.GapLookup(profile)
    radius = np.array([(cms.PINION_TURNED_R + profile.blank_radius_mm)/2.0])
    tooth = np.array([0.0])
    assert cms.pinion_material(lookup, tooth, radius, np.array([cms.PINION_SHOULDER/2.0])).all()
    assert not cms.pinion_material(lookup, tooth, radius, np.array([(cms.PINION_SHOULDER+cms.PINION_FACE)/2.0])).any()
    assert cms.pinion_material(lookup, tooth, np.array([cms.PINION_TURNED_R-0.05]), np.array([cms.PINION_FACE-0.05])).all()
    assert not cms.pinion_material(lookup, tooth, radius, np.array([cms.PINION_FACE+0.001])).any()


def test_material_adapter_has_the_native_tooth_zero_not_gap_zero() -> None:
    for profile in (cms.pinion_spec.STOCK_PROFILE, cms.gear64_spec.STOCK_PROFILE):
        lookup = cms.GapLookup(profile)
        angles = np.linspace(-profile.angular_pitch_rad, profile.angular_pitch_rad, 41)
        radii = np.linspace(profile.root_radius_min_mm-0.01, profile.blank_radius_mm+0.01, 43)
        theta, radius = np.meshgrid(angles,radii)
        actual = lookup.material(theta,radius)
        expected = np.array([
            profile.contains_material(float(r*math.cos(a)),float(r*math.sin(a)),rotate_rad=profile.angular_pitch_rad/2.0)
            for a,r in zip(theta.flat,radius.flat)
        ]).reshape(theta.shape)
        assert np.array_equal(actual,expected)
        assert lookup.material(np.array([0.0]),np.array([profile.pitch_radius_mm])).all()
        assert not lookup.material(np.array([profile.angular_pitch_rad/2.0]),np.array([profile.pitch_radius_mm])).any()


def test_wrong_cutter_master_changes_actual_material() -> None:
    profile = cms.pinion_spec.STOCK_PROFILE
    assert profile.template.reference_teeth == 14
    assert cms.gear64_spec.STOCK_PROFILE.template.reference_teeth == 55
    wrong_template = template_for_teeth(12,profile.template.diametral_pitch,profile.template.pressure_angle_deg)
    wrong = StockFormProfile(profile.teeth,wrong_template,profile.blank_radius_mm,
                             profile.radial_translation_mm+profile.template.pitch_radius_mm-wrong_template.pitch_radius_mm)
    assert wrong.pitch_tooth_thickness_mm != pytest.approx(profile.pitch_tooth_thickness_mm,abs=1e-4)
    theta = np.linspace(0.0,profile.angular_pitch_rad,2001)
    radius = np.full_like(theta,profile.pitch_radius_mm)
    assert np.any(cms.GapLookup(wrong).material(theta,radius) != cms.GapLookup(profile).material(theta,radius))


def test_finite_gap_inverse_matches_actual_oracle_on_both_flanks() -> None:
    profile = cms.pinion_spec.STOCK_PROFILE
    inverse = contact.GapAngles(profile)
    for radius in np.linspace(inverse.minimum+0.01,inverse.maximum-0.01,19):
        angle = inverse.angle(float(radius))
        delta = 10.0*inverse.error_rad + 1e-5
        for side in (-1.0,1.0):
            inside_gap = side*(angle-delta)
            in_tooth = side*(angle+delta)
            assert not profile.contains_material(radius*math.cos(inside_gap),radius*math.sin(inside_gap))
            assert profile.contains_material(radius*math.cos(in_tooth),radius*math.sin(in_tooth))


def test_crossed_screw_is_three_dimensional_and_hand_sensitive() -> None:
    profile = cms.gear64_spec.STOCK_PROFILE
    segment = next(s for s in profile.external_boundary_segments() if s.kind == "flank")
    point = segment.point(0.5)
    placement = cms.Placement()
    south = cms.screw_point(profile,point,-2.0,0,0.0,placement)
    north = cms.screw_point(profile,point,2.0,0,0.0,placement)
    local_s = (south-placement.gear_centre) @ cms.FRAME64
    local_n = (north-placement.gear_centre) @ cms.FRAME64
    assert local_n[2]-local_s[2] == pytest.approx(4.0)
    expected = 4.0/profile.lead_per_radian_mm
    actual = math.atan2(local_n[1],local_n[0])-math.atan2(local_s[1],local_s[0])
    assert actual == pytest.approx(expected)
    mirrored = replace(profile,helix_angle_deg=-profile.helix_angle_deg)
    wrong = cms.screw_point(mirrored,point,2.0,0,0.0,placement)
    assert np.linalg.norm(wrong-north) > 0.1


def test_root_gap_and_phase_are_not_assumed_free() -> None:
    profile = cms.pinion_spec.STOCK_PROFILE
    lookup = cms.GapLookup(profile)
    radius = np.array([profile.pitch_radius_mm])
    assert lookup.material(np.array([0.0]),radius).all()
    assert not lookup.material(np.array([profile.angular_pitch_rad/2.0]),radius).any()
    assert lookup.material(np.array([profile.angular_pitch_rad/2.0]),np.array([profile.root_radius_min_mm-0.001])).all()


def test_interval_window_rejects_missing_carrier_and_negative_free_play() -> None:
    missing = contact.Window(0.0,-math.inf,math.inf,0.0001,None,None,(),0,False)
    jammed = contact.Window(0.0,0.02,0.01,0.0001,None,None,(),0,False)
    unresolved = contact.Window(0.0,0.0,0.0001,0.0001,None,None,(),0,False)
    assert not missing.open
    assert not missing.no_overlap
    assert not jammed.no_overlap
    assert not unresolved.no_overlap


@pytest.mark.parametrize("kind", [
    "root_arc","radial/driven_root_corner","flank/driver_root_corner","axial_face",
])
def test_actual_root_and_axial_features_never_count_as_working_branches(kind) -> None:
    evidence = contact.Contact(
        phase_offset_rad=0.0,driven_tooth=0,segment="synthetic predicate control",
        kind="flank/axial_edge",parameter=0.5,station_mm=0.0,
        world_point_mm=(0.0,0.0,0.0),driver_radius_mm=8.0,driver_z_mm=1.0,
        driven_normal_world=(1.0,0.0,0.0),driver_normal_world=(-1.0,0.0,0.0),
        opposed_normal_residual=0.0,driven_per_driver_velocity=-0.25,
        common_normal_supported=True,common_normal_error_bound=1e-10,
    )
    assert contact.grounded_contact(evidence)
    assert not contact.grounded_contact(replace(evidence,kind=kind))
    assert not contact.grounded_contact(replace(evidence,common_normal_supported=False))
    assert not contact.grounded_contact(replace(evidence,driven_per_driver_velocity=0.0))
    assert not contact.grounded_contact(replace(evidence,driven_per_driver_velocity=math.nan))
    assert not contact.grounded_contact(replace(evidence,opposed_normal_residual=1e-8))


def test_positive_flank_width_does_not_replace_paid_root_and_phase_components() -> None:
    nominal = contact.Window(0.0,-0.02,0.02,0.001,None,None,(),0,False)
    assert not nominal.no_overlap
    paid = replace(nominal,free_intervals_rad=((-0.019,0.019),),surface_numerical_resolved=True)
    assert paid.no_overlap
    assert not replace(paid,phase_error_rad=0.02).no_overlap
    assert not replace(paid,root_contact=True).no_overlap
    assert not replace(paid,surface_numerical_resolved=False).no_overlap


def _synthetic_pose_search():
    """Bound-model control only, never a stock-form engineering certificate."""
    search = object.__new__(contact.ContactSearch)
    point = contact.Contact(
        phase_offset_rad=2.0,driven_tooth=0,segment="synthetic finite side",
        kind="flank",parameter=0.5,station_mm=0.5,
        world_point_mm=(1.0,0.0,0.5),driver_radius_mm=1.0,driver_z_mm=0.5,
        driven_normal_world=(1.0,0.0,0.0),driver_normal_world=(-1.0,0.0,0.0),
        opposed_normal_residual=0.0,driven_per_driver_velocity=-0.25,
        common_normal_supported=True,common_normal_error_bound=1e-10,
    )
    search.case = SimpleNamespace(
        name="synthetic pose enclosure",
        driver=SimpleNamespace(pitch_radius_mm=1.0),
        driven=SimpleNamespace(teeth=1,blank_radius_mm=1.0),
    )
    search.placement = SimpleNamespace(driven_face_mm=(0.0,1.0))
    search.driven_teeth = (0,)
    search.segments = (SimpleNamespace(name=point.segment,speed_bound_mm=1.0),)
    search.radial_error_mm = 0.3
    search.axial_error_mm = 0.5
    search.surface_extrema = {}
    search.gap = SimpleNamespace(minimum=1.0,radial_slope_bound=lambda:0.0,error_rad=0.0)
    search.second_speed = lambda _segment:0.0
    search.phase,search.pitch,search.ratio = 0.0,10.0,1.0
    search.support_reserves,search.row_intervals = {},{}
    search.bound = lambda *args: (-1.0,3.0,(2.0,point))
    search.optimise = lambda *args,**kwargs: (2.0,point)
    search.optimise_relaxed = lambda *args: -1.0
    return search,point


def test_irreducible_pose_width_is_not_surface_subdivision_error() -> None:
    search,point = _synthetic_pose_search()
    upper,witness,_,boxes,_ = search.extremum(1,0.001,1)
    enclosure = search.surface_extrema[1]
    assert boxes == 0
    assert upper == 2.0 and witness is point
    assert enclosure["lower_rad"] == -1.0
    assert enclosure["upper_rad"]-enclosure["lower_rad"] == 3.0
    assert enclosure["numerical_tolerance_rad"] == 0.001
    assert enclosure["radial_pose_error_mm"] == 0.3
    assert enclosure["axial_pose_error_mm"] == 0.5
    assert enclosure["relaxed_incumbent_rad"] == -1.0
    assert enclosure["achieved_residual_rad"] == 0.0
    assert enclosure["terminal_boxes"] == 0
    assert enclosure["terminal_lower_rad"] is None


@pytest.mark.parametrize("terminal", [False,True])
def test_every_child_and_terminal_box_retains_its_surface_lower_bound(terminal) -> None:
    search,point = _synthetic_pose_search()
    def bound(_segment,_tooth,box,_direction):
        t0,t1,_,_ = box
        if t1-t0 == 1.0:
            lower = -1.0
        elif t0 == 0.0:
            lower = -0.2
        else:
            lower = -0.4 if terminal else -0.1
        return lower,3.0,(2.0,point)
    search.bound = bound
    search.optimise_relaxed = lambda *args:0.0
    search.relaxed_value = lambda *args:0.0
    _,_,_,boxes,_ = search.extremum(1,0.25,128)
    enclosure = search.surface_extrema[1]
    assert boxes > 0
    assert enclosure["lower_rad"] == (-0.4 if terminal else -0.2)
    assert enclosure["achieved_residual_rad"] == (0.4 if terminal else 0.2)
    assert (enclosure["terminal_boxes"] > 0) is terminal
    assert enclosure["terminal_lower_rad"] == (-0.4 if terminal else None)
    assert enclosure["branch_numerics"][0]["achieved_residual_rad"] == enclosure["achieved_residual_rad"]


def test_window_pays_the_actual_surface_enclosure_not_requested_tolerance(monkeypatch) -> None:
    @dataclass
    class RootControl:
        status: str = "resolved"
        free_inner: tuple = ((-4.0,4.0),)
        boxes: int = 0

    search,_ = _synthetic_pose_search()
    monkeypatch.setattr(contact,"root_free_intervals",lambda *args,**kwargs:RootControl())
    window = search.window(maximum_error_mm=0.001,max_boxes=1)
    assert window.surface_numerical_resolved
    assert window.upper_rad-window.lower_rad == 4.0
    assert window.error_rad == 3.0
    assert not window.no_overlap
    assert not window.free_intervals_rad


def test_relaxed_envelope_point_is_not_a_physical_contact_witness() -> None:
    profile = cms.pinion_spec.STOCK_PROFILE
    pair = contact.ContactPair("expanded domain",profile,profile,contact.Placement(
        (0.0,0.0,0.0),(0.0,0.0,0.0),np.eye(3),np.eye(3),(0.0,1.0),(0.0,1.0),
    ))
    search = contact.ContactSearch(pair,0.0,radial_error_mm=0.02,axial_error_mm=0.02)
    # This actual surface point can reach the physical face under the paid
    # domain, but is outside the nominal face and has no guaranteed witness.
    radius = (search.gap.minimum+search.gap.maximum)/2
    local = np.array([radius,0.0,-0.01])
    search.point = lambda *args: (local,local)
    search.surface_member = lambda *args: True
    segment = search.segments[0]
    assert not search.feasible(local)
    assert math.isfinite(search.relaxed_value(segment,0,0.5,0.5,1))


def test_end_cap_cull_refines_below_a_fixed_polygon_error() -> None:
    """Synthetic closed circular boundary with an independently removed fan."""
    circle = SimpleNamespace(
        name="synthetic circular material boundary",kind="tip_arc",
        point=lambda t:(math.cos(2*math.pi*t),math.sin(2*math.pi*t)),
        speed_bound_mm=2*math.pi,second_derivative_bound_mm=(2*math.pi)**2,
    )
    search = object.__new__(contact.ContactSearch)
    search.case = SimpleNamespace(driven=SimpleNamespace(
        angular_pitch_rad=2*math.pi,geometry_error_bound_mm=1e-12,
    ))
    search.perimeter = (circle,)
    search.surface_member = lambda *args: False
    patch = contact.EndFacePatch(circle,0.0,1)
    separation = 1e-5
    assert separation < circle.second_derivative_bound_mm/(8*32**2)
    assert search.cap_removed(patch,0.0,1-separation,separation/4)
    assert not search.cap_removed(patch,0.0,1-separation,separation*2)


@pytest.mark.parametrize("clock_sign", [-1,1])
def test_end_cap_cull_keeps_balls_reaching_either_periodic_neighbor(clock_sign) -> None:
    """Synthetic curve-distance inventory isolates each periodic-copy term."""
    pitch = math.pi/2
    epsilon = 1e-4
    query = (epsilon,clock_sign*1.5)
    radial = SimpleNamespace(
        name="synthetic radial boundary",kind="radial",
        point=lambda t:(1+t,0.0),speed_bound_mm=1.0,second_derivative_bound_mm=0.0,
    )
    fan = SimpleNamespace(
        name="synthetic fan boundary",kind="radial",
        point=lambda _t:(2*query[0],2*query[1]),
        speed_bound_mm=0.0,second_derivative_bound_mm=0.0,
    )
    search = object.__new__(contact.ContactSearch)
    search.case = SimpleNamespace(driven=SimpleNamespace(
        angular_pitch_rad=pitch,geometry_error_bound_mm=1e-12,
    ))
    search.perimeter = (radial,fan)
    search.surface_member = lambda *args:False
    patch = contact.EndFacePatch(fan,0.0,1)
    # The unrotated curves are far away. Only the selected +/- pitch copy
    # of the radial segment lies within this fan box's motion radius.
    assert not search.cap_removed(patch,0.5,0.5,2*epsilon)


def test_correlated_pose_cell_pays_each_rotating_eccentricity_and_axial_sweep() -> None:
    interval = continuation.Interval
    source = contact.source_pose((
        ("driver_ecc_x_mm",(-0.02,0.02)),
        ("driven_ecc_y_mm",(-0.03,0.03)),
        ("driven_dz_mm",(-0.04,0.04)),
    ))
    placement = contact.Placement(
        (0.0,0.0,0.0),(40.0,0.0,0.0),np.eye(3),cms.FRAME64,
        (0.0,11.6),(-3.0,3.0),
    )
    pair = contact.ContactPair("source-cell transform control",
                               cms.pinion_spec.STOCK_PROFILE,cms.gear64_spec.STOCK_PROFILE,placement)
    phi,beta = interval(-0.01,0.01),interval(-0.02,0.02)
    search,driver_motion = contact.pose_cell_search(pair,continuation.PhaseCell(phi,source),beta)
    assert driver_motion >= 0.01
    segment = next(s for s in pair.driven.external_boundary_segments() if s.kind == "flank")
    for actual_phi,actual_beta in ((phi.lower,beta.upper),(phi.upper,beta.lower)):
        for driver_ecc,driven_ecc,axial in ((0.02,-0.03,0.04),(-0.02,0.03,-0.04)):
            origin16 = np.array([driver_ecc*math.cos(actual_phi),driver_ecc*math.sin(actual_phi),0.0])
            origin64 = np.array(placement.driven_origin_mm)+cms.FRAME64@np.array([
                -driven_ecc*math.sin(actual_beta),driven_ecc*math.cos(actual_beta),axial,
            ])
            actual_pose = replace(placement,driver_origin_mm=tuple(origin16),driven_origin_mm=tuple(origin64))
            for tooth,station in ((0,-3.0),(31,3.0)):
                actual = contact.screw_point(pair.driven,segment.point(0.5),station,tooth,actual_beta,actual_pose)-origin16
                _,nominal = search.point(segment,tooth,0.5,station)
                delta = actual-nominal
                assert math.hypot(delta[0],delta[1]) <= search.radial_error_mm
                assert abs(delta[2]) <= search.axial_error_mm


def test_correlated_root_query_preserves_disconnected_free_components(monkeypatch) -> None:
    @dataclass
    class RootControl:
        status: str = "resolved"
        free_inner: tuple = ((-0.2,-0.1),(0.1,0.2))
        boxes: int = 0

    pair = contact.ContactPair("disconnected root control",
        cms.pinion_spec.STOCK_PROFILE,cms.gear64_spec.STOCK_PROFILE,
        contact.Placement((0.0,0.0,0.0),(40.0,0.0,0.0),np.eye(3),cms.FRAME64,
                          (0.0,11.6),(-3.0,3.0)))
    def bounded(search,**_kwargs):
        assert search.driven_teeth == tuple(range(pair.driven.teeth))
        assert any(isinstance(segment,contact.EndFacePatch) for segment in search.segments)
        return RootControl()
    monkeypatch.setattr(contact,"root_free_intervals",bounded)
    interval = continuation.Interval
    cell = continuation.PhaseCell(interval.point(0))
    proof = contact.root_free_pose_cell(pair,cell,interval(-0.01,0.01),
                                       maximum_error_mm=0.001,required_root_air_mm=0.0)
    assert proof["status"] == "UNKNOWN"
    assert proof["root_free_driven_components_rad"] == ()
    assert len(proof["inverse_offset_free_components_rad"]) == 2


@pytest.mark.parametrize("profile_index",range(5))
def test_actual_drum_finite_inverse_endpoints_and_angle_frame(profile_index,monkeypatch) -> None:
    import dt_cylinder_gear_spec as drum

    profile = (drum.STOCK_FORM,*drum.manufacturing_corner_profiles())[profile_index]
    gap = contact.GapAngles(profile)
    lower = min(gap.working_parameter_domains,key=lambda item:item[3])
    upper = max(gap.working_parameter_domains,key=lambda item:item[4])
    for domain,index,sense in ((lower,1,-math.inf),(upper,2,math.inf)):
        kind,parameter = domain[0],domain[index]
        point = profile.radial_point(parameter) if kind == "radial" else profile.flank_point(parameter)
        radius = math.hypot(*point)
        outside = math.nextafter(radius,sense)
        assert gap._working_parameter(outside) == (kind,parameter,True)
        rb,T,k = profile.template.base_radius_mm,profile.radial_translation_mm,profile.template.half_space_base_angle_rad
        S,Q = ((parameter+T*math.cos(k),T*math.sin(k)) if kind == "radial"
               else (rb+T*math.cos(k+parameter),rb*parameter+T*math.sin(k+parameter)))
        # Recreate the actual one-ULP endpoint disagreement in the table/blank,
        # not a brentq exception mock. The same finite endpoint is returned.
        attribute = "branch_minimum" if index == 1 else "maximum"
        with monkeypatch.context() as patch:
            patch.setattr(gap,attribute,outside)
            assert gap.exact_slope(outside) == Q/(radius*S)
            assert gap.exact_angle(outside) == math.atan2(point[1],point[0])
        distant = radius + (-1 if index == 1 else 1)*8*gap.endpoint_radius_error_mm
        with pytest.raises(ValueError,match="beyond arithmetic enclosure"):
            gap._working_parameter(distant)
    assert gap.error_rad >= gap.endpoint_radius_error_mm*gap.radial_slope_bound()
    for kind,lo,hi,_,_ in gap.working_parameter_domains:
        for fraction in (0.2,0.5,0.8):
            parameter = lo+fraction*(hi-lo)
            point = profile.radial_point(parameter) if kind == "radial" else profile.flank_point(parameter)
            radius = math.hypot(*point)
            # Material-tooth table clock must remain the same canonical gap
            # angle after an inverse-endpoint correction.
            assert abs(gap.angle(radius)-math.atan2(point[1],point[0])) <= gap.error_rad


def test_radial_only_finite_inverse_never_roots_an_absent_flank(monkeypatch) -> None:
    cutter = template_for_teeth(14,48,20)
    shift = 0.1*cutter.module_mm
    profile = StockFormProfile(14,cutter,
        shift+(cutter.root_radius_mm+cutter.base_radius_mm)/2,shift)
    def absent_flank(*_args,**_kwargs):
        raise AssertionError("radial-only finite support must not call flank brentq")
    monkeypatch.setattr(contact,"brentq",absent_flank)
    gap = contact.GapAngles(profile)
    assert {item[0] for item in gap.working_parameter_domains} == {"radial"}
    radius = (gap.branch_minimum+gap.maximum)/2
    assert math.isfinite(gap.exact_angle(radius))
    assert gap.exact_slope(radius) > 0
    assert gap.derivatives(radius,gap.branch_minimum) is None


def test_finite_inverse_rejects_a_blank_beyond_real_trimmed_tip() -> None:
    import dt_cylinder_gear_spec as drum

    actual = drum.STOCK_FORM
    gap = contact.GapAngles(actual)
    class InconsistentBlank:
        blank_radius_mm = actual.blank_radius_mm+8*gap.endpoint_radius_error_mm
        def __getattr__(self,name):
            return getattr(actual,name)
    with pytest.raises(ValueError,match="does not span.*arithmetic enclosure"):
        contact.GapAngles(InconsistentBlank())


def test_projected_upper_endpoint_retains_lipschitz_not_taylor(monkeypatch) -> None:
    import dt_cylinder_gear_spec as drum

    gap = contact.GapAngles(drum.STOCK_FORM)
    domain = max(gap.working_parameter_domains,key=lambda item:item[4])
    assert domain[0] == "flank"
    upper = math.nextafter(domain[4],math.inf)
    monkeypatch.setattr(gap,"maximum",upper)
    interior = (domain[3]+domain[4])/2
    assert gap.derivatives((interior+domain[4])/2,interior) is not None
    assert gap._working_parameter(upper)[2]
    assert gap.derivatives(upper,interior) is None
