"""Deterministic pure geometry regressions; no CAD or config-side verification."""
import math
import itertools
from dataclasses import replace

from types import SimpleNamespace
import numpy as np
import pytest

import diagnostics.oblique_cone_mesh_study as cone_study
from diagnostics.oblique_cone_mesh_study import (
    PoseDomain, cone_frame, cylinder_native_rows, exact_smooth_ff_exclusion,
    cutter_q_domain, json_safe, placement_from_geometry, pose_corner_records, root_domain_probe,
    complete_pose_errors, finite_circular_band_radial_lower,
)
from diagnostics.stock_form_contact_3d import ContactPair, ContactSearch, EndFacePatch, GapAngles, Placement
from diagnostics.stock_form_root_angles import RootAngularDomain
from stock_form_cutter import CutterTemplate, CustomSixCutter, StockFormProfile


def _geometry():
    incline = math.radians(13.0011)
    return {"cone_axis":(math.sin(incline),0.0,math.cos(incline)),
            "cone_centre_mm":(0.0,0.0,0.0),"cone_face_width_mm":7.0,
            "drum_axis_xy_mm":(40.0,0.0),"drum_z_limits_mm":(-1.5,1.5),
            "native_gap_clocks_rad":(math.pi/32,math.pi-math.radians(15)-math.pi/120)}


def _pair():
    tool = CutterTemplate(26,48.0,20.0)
    a = StockFormProfile(32,tool,8.8,1.5875)
    btool = CutterTemplate(55,48.0,20.0)
    b = StockFormProfile(120,btool,32.2,17.197916666666668)
    pose = placement_from_geometry(_geometry())
    return ContactPair("actual explicit oblique fixture",a,b,pose)


def test_row_vector_pose_is_transposed_not_scalar_centre():
    tilt = math.radians(13.0011)
    frame = cone_frame(tilt)
    assert frame[:,2] == pytest.approx((math.sin(tilt),0,math.cos(tilt)))
    assert frame[:,0] == pytest.approx((math.cos(tilt),0,-math.sin(tilt)))
    assert frame.T@frame == pytest.approx(np.eye(3),abs=2e-15)
    p = np.array((2.0,1.0,3.0))
    world = frame@p
    assert world[0] == pytest.approx(math.cos(tilt)*2+math.sin(tilt)*3)
    assert world[2] == pytest.approx(-math.sin(tilt)*2+math.cos(tilt)*3)
    assert world[0] != pytest.approx(p[0])


def test_native_cylinder_flip_retains_clock_and_reverses_phase():
    lock = math.radians(15.0)
    rows = cylinder_native_rows(lock)
    assert rows[0] == pytest.approx((-math.cos(lock),math.sin(lock),0.0))
    assert rows[2] == pytest.approx((0.0,0.0,-1.0))
    assert np.linalg.det(rows) == pytest.approx(1.0)
    pose = placement_from_geometry(_geometry())
    assert pose.driven_clocking_rad == pytest.approx(math.pi-lock-math.pi/120)
    assert pose.driver_clocking_rad == pytest.approx(math.pi/32)
    assert pose.driver_face_mm == (-3.5,3.5)
    assert pose.driven_face_mm == (-1.5,1.5)


def test_pose_ball_records_do_not_masquerade_as_full_circle_certificate():
    tilt = math.radians(13.0011)
    domain = PoseDomain((0.0,0.8),(-0.55,0.2),(6.975,7.025),(2.95,3.05),
                        0.07,(tilt,tilt),("actual source-owned fixture",))
    rows = pose_corner_records(_geometry(),domain)
    assert len(rows) == 80
    assert {tuple(row["corner"]["radial_offset_mm"]) for row in rows} == {
        (0.0,0.0),(-0.07,0.0),(0.07,0.0),(0.0,-0.07),(0.0,0.07)}
    assert domain.relative_radial_ball_mm == 0.07
    with pytest.raises(ValueError,match="provenance"):
        PoseDomain((0,0),(0,0),(7,7),(3,3),0,(tilt,tilt),())


def test_gap_inverse_negative_translation_uses_supported_actual_bound():
    tool = CutterTemplate(12,48.0,20.0)
    profile = StockFormProfile(12,tool,3.3,-0.1)
    inverse = GapAngles(profile)
    slope = inverse.radial_slope_bound()
    assert math.isfinite(slope) and slope > 0
    lo,hi = inverse.branch_range(inverse.minimum,inverse.maximum)
    assert lo <= min(inverse.angle(float(r)) for r in np.linspace(inverse.minimum,inverse.maximum,201))
    assert hi >= max(inverse.angle(float(r)) for r in np.linspace(inverse.minimum,inverse.maximum,201))
    # A real negative-T radial connector may make angle nonmonotone. No
    # positive-T tangent-limit surrogate or ideal-N continuation is allowed.
    for u in np.linspace(profile.flank_parameter_min,profile.flank_parameter_max,31):
        x,y = profile.flank_point(float(u))
        r = math.hypot(x,y)
        if r < inverse.minimum:
            continue
        z = tool.half_space_base_angle_rad+u
        exact = abs((tool.base_radius_mm*u+profile.radial_translation_mm*math.sin(z)) /
                    (r*(tool.base_radius_mm+profile.radial_translation_mm*math.cos(z))))
        assert exact <= slope


def test_custom_six_requires_provenance_and_has_general_slope_bound():
    tool = CustomSixCutter(48,20,1.173,4*25.4/48,0.818,
                          "DT6-FORM1","approved finite fixture")
    profile = StockFormProfile(6,tool,1.9,0.1)
    inverse = GapAngles(profile)
    assert math.isfinite(inverse.radial_slope_bound())
    assert inverse.branch_range(inverse.minimum,inverse.maximum)[0] <= inverse.branch_range(inverse.minimum,inverse.maximum)[1]


def test_smooth_common_normal_is_not_edge_union_coverage():
    result = exact_smooth_ff_exclusion(_pair())
    assert result["excluded"]
    assert result["opposed_normal_position_residual_lower_mm"] > 0
    assert result["common_normal_world"] == [0.0,1.0,0.0]
    assert result["branch"] == "all four smooth flank-side arrangements"
    assert "coverage" not in result


def test_endfaces_are_actual_two_parameter_patches_not_perimeter_only():
    pair = _pair()
    search = ContactSearch(pair,0.0)
    caps = [segment for segment in search.segments if isinstance(segment,EndFacePatch)]
    assert caps
    assert {segment.station_mm for segment in caps} == set(pair.placement.driven_face_mm)
    patch = next(segment for segment in caps if segment.boundary.kind == "tip_arc")
    world,local = search.point(patch,0,0.5,0.5)
    perimeter_world,_ = search.point(patch,0,0.5,1.0)
    origin = np.asarray(pair.placement.driven_origin_mm)
    assert np.linalg.norm((world-origin)[:2]) == pytest.approx(pair.driven.blank_radius_mm/2)
    assert np.linalg.norm((perimeter_world-origin)[:2]) == pytest.approx(pair.driven.blank_radius_mm)
    assert world[2] == pytest.approx(origin[2]+patch.station_mm)
    assert local == pytest.approx((world-np.asarray(pair.placement.driver_origin_mm))@pair.placement.driver_frame)
    assert search.surface_member(patch,0.5,0.5)


def test_position_uncertainty_is_irreducible_not_faked_zero():
    pair = _pair()
    exact = ContactSearch(pair,0.0)
    moved = ContactSearch(pair,0.0,position_error_mm=0.07)
    assert exact.position_angle_error_rad == 0
    assert moved.position_angle_error_rad > 0
    assert moved.position_angle_error_rad == pytest.approx(
        .07*(1/moved.gap.minimum+moved.gap.radial_slope_bound()))
    with pytest.raises(ValueError,match="nonnegative"):
        ContactSearch(pair,0.0,position_error_mm=-0.01)


def test_nonfinite_refusals_are_named_not_json_nan():
    value = json_safe({"bound":None,"root_gap":-math.inf,"phases":(0.0,math.inf)})
    assert value == {"bound":None,"root_gap":"-inf","phases":[0.0,"inf"]}
    scalars = json_safe({"qualified":np.bool_(True),"count":np.int64(20),"bound":np.float64(.002)})
    assert scalars == {"qualified":True,"count":20,"bound":.002}
    assert type(scalars["qualified"]) is bool


def test_shared_engine_requires_actual_frames_and_faces():
    with pytest.raises(ValueError,match="right-handed"):
        Placement((0,0,0),(40,0,0),np.eye(3),np.diag((1,1,-1)),(-3,3),(-1.5,1.5))
    with pytest.raises(ValueError,match="nonempty"):
        Placement((0,0,0),(40,0,0),np.eye(3),np.eye(3),(0,0),(-1.5,1.5))


def test_actual_oblique_side_endface_normal_cone_is_not_cap_only():
    pair = _pair()
    driver,driven = pair.driver,pair.driven
    tilt = math.radians(13.0011)
    frame = cone_frame(tilt)
    u = (driver.flank_parameter_min+driver.flank_parameter_max)/2
    v = (driven.flank_parameter_min+driven.flank_parameter_max)/2
    # Mate upper flank faces left after a pi rotation. Choose the genuine
    # driver flank normal whose XY projection opposes it; its oblique Z
    # component is supplied by the mate's actual NORTH endface normal.
    n_b = -np.asarray(driven.flank_normal(v))
    desired_xy = -n_b
    alpha = math.atan2(desired_xy[1],desired_xy[0]/math.cos(tilt))
    original = driver.flank_normal(u)
    driver_gap_clock = alpha-math.atan2(original[1],original[0])
    def rotate(point,clock):
        c,s = math.cos(clock),math.sin(clock)
        return np.array((c*point[0]-s*point[1],s*point[0]+c*point[1]))
    a_point = rotate(driver.flank_point(u),driver_gap_clock)
    b_point = rotate(driven.flank_point(v),math.pi)
    world = np.array((b_point[0],b_point[1],1.5))
    origin = world-frame@np.r_[a_point,0.0]
    pose = Placement(tuple(origin),(0.0,0.0,0.0),frame,np.eye(3),(-3.5,3.5),(-1.5,1.5),
                     driver_clocking_rad=driver_gap_clock+driver.angular_pitch_rad/2,
                     driven_clocking_rad=math.pi+driven.angular_pitch_rad/2)
    case = ContactPair("exact local axial-edge normal fixture",driver,driven,pose)
    search = ContactSearch(case,0.0)
    segment = next(s for s in search.segments if not isinstance(s,EndFacePatch)
                   and s.kind == "flank" and s.point(.5)[1] < 0)
    parameter = (v-driven.flank_parameter_min)/(driven.flank_parameter_max-driven.flank_parameter_min)
    contact = search.contact(segment,0,parameter,1.5,1)
    assert "driven_axial_edge" in contact.kind
    assert contact.common_normal_supported
    assert contact.opposed_normal_residual <= contact.common_normal_error_bound
    assert math.isfinite(contact.driven_per_driver_velocity)
    assert contact.driven_per_driver_velocity < 0
    # The mate normal is a positive combination of the REAL flank and cap,
    # not an invented assignment of the negative driver normal.
    actual = np.asarray(contact.driven_normal_world)
    assert actual[2] > 0
    assert actual[0]*n_b[1]-actual[1]*n_b[0] == pytest.approx(0.0,abs=1e-11)


def test_supported_Q_domain_covers_negative_translation_stationary_points():
    cutter = CutterTemplate(12,48,20)
    shifts = (-2*cutter.base_radius_mm,-cutter.base_radius_mm)
    lo,hi = cutter_q_domain(cutter,shifts)
    values = [
        cutter.base_radius_mm*u+shift*math.sin(cutter.half_space_base_angle_rad+u)
        for shift in shifts
        for u in np.linspace(cutter.flank_parameter_min,cutter.flank_parameter_max,1001)
    ]
    assert lo <= min(values) <= max(values) <= hi
    assert cutter_q_domain(cutter,(1.0,0.0)) is None


def test_root_domain_witness_is_actual_material_not_a_physical_no_solution_claim():
    source = _pair()
    pose = Placement((0,0,0),(0,0,0),np.eye(3),np.eye(3),(-1,1),(-1,1))
    witness = root_domain_probe(ContactPair("coincident finite profile witness",
                                           source.driver,source.driven,pose))
    assert witness is not None
    assert witness["driven_actual_material_member"]
    assert witness["point_below_root_max"]
    assert witness["driver_radius_mm"] < witness["driver_root_max_mm"]
    assert witness["position_ball_mm"] == 0
    assert "no_solution_certificate" not in witness


def test_pose_ball_root_touch_is_distinguished_from_an_actual_point():
    source = _pair()
    pose = Placement((0,0,0),(45,0,0),np.eye(3),np.eye(3),(-1,1),(-1,1))
    pair = ContactPair("separated finite profile domain",source.driver,source.driven,pose)
    assert root_domain_probe(pair) is None
    witness = root_domain_probe(pair,position_error_mm=6.0)
    assert witness is not None
    assert not witness["point_below_root_max"]
    assert not witness["profile_solid_interference_certified"]
    assert witness["driver_radius_mm"]-6.0 < witness["driver_root_max_mm"]


@pytest.mark.parametrize("translation",(-0.1,0.1))
def test_exact_root_strip_encloses_core_material_not_root_max_disk(translation):
    tool = CutterTemplate(26,48,20)
    profile = StockFormProfile(26,tool,7.1,translation)
    root = RootAngularDomain(profile,GapAngles(profile))
    radius = (profile.root_radius_min_mm+profile.root_radius_max_mm)/2
    intervals = root.bounds(radius,radius)
    assert not intervals.root_is_carrying
    assert intervals.reaches_root_strip
    assert len(intervals.inner) == (2 if translation>0 else 1)
    assert profile.contains_material(radius,0) == (translation>0)
    for lo,hi in intervals.inner:
        angle = (lo+hi)/2
        assert not profile.contains_material(radius*math.cos(angle),radius*math.sin(angle))
    for angle in np.linspace(-profile.angular_pitch_rad/2,profile.angular_pitch_rad/2,81):
        if not profile.contains_material(radius*math.cos(angle),radius*math.sin(angle)):
            assert any(lo <= angle <= hi for lo,hi in intervals.outer)


def test_root_tangency_and_zero_translation_have_paid_material_transitions():
    tool = CutterTemplate(26,48,20)
    profile = StockFormProfile(26,tool,7.1,0.0)
    root = RootAngularDomain(profile,GapAngles(profile))
    radius = profile.root_radius_min_mm
    assert root.bounds(radius-0.01,radius-0.01).outer == ()
    assert root.bounds(radius,radius).inner == ()
    assert len(root.bounds(radius+0.01,radius+0.01).inner) == 1
    shifted = StockFormProfile(26,tool,7.1,0.1)
    authority = RootAngularDomain(shifted,GapAngles(shifted))
    across = authority.bounds(shifted.root_radius_min_mm-1e-9,
                              shifted.root_radius_max_mm+1e-9)
    assert across.inner == ()
    assert across.outer
    assert all(math.isfinite(value) for interval in across.outer for value in interval)


def test_root_offsets_preserve_disconnected_components_and_periodic_phase():
    tool = CutterTemplate(26,48,20)
    profile = StockFormProfile(26,tool,7.1,0.1)
    root = RootAngularDomain(profile,GapAngles(profile))
    radius = (profile.root_radius_min_mm+profile.root_radius_max_mm)/2
    direct = root.offset_bounds(radius,radius,0.0,0.0)
    repeated = root.offset_bounds(radius,radius,profile.angular_pitch_rad,0.0)
    assert np.asarray(repeated.inner) == pytest.approx(np.asarray(direct.inner))
    assert np.asarray(repeated.outer) == pytest.approx(np.asarray(direct.outer))
    at_seam = root.offset_bounds(radius,radius,profile.angular_pitch_rad/2,1e-5,root_only=True)
    assert any(lo < 0 < hi for lo,hi in at_seam.inner)
    assert len(at_seam.inner) == 1


def test_cone_axial_float_is_not_radial_runout():
    pair = _pair()
    tilt = math.radians(13.0011)
    base = PoseDomain((0,0),(0,0),(7,7),(3,3),0,(tilt,tilt),("fixed source fixture",))
    nominal = complete_pose_errors(pair,base)
    floating = complete_pose_errors(pair,replace(base,cone_axial_shift_mm=(0,0.8)))
    assert nominal == pytest.approx((0,0),abs=1e-14)
    assert floating == pytest.approx((0,0.8),abs=1e-14)
    shifted = complete_pose_errors(pair,replace(base,drum_axial_shift_mm=(0,0.55)))
    assert shifted == pytest.approx((0.55*math.sin(tilt),0.55*math.cos(tilt)))


def test_bore_cock_projection_encloses_every_azimuth_not_cardinals_only():
    pair = _pair()
    tilt,beta = math.radians(13.0011),0.012
    domain = PoseDomain((0,0),(0,0),(7,7),(3,3),0,(tilt,tilt),
                        ("arbitrary source bore-cock axis and full-bore pivot",),
                        drum_axis_angle_rad=beta,drum_cock_pivot_lever_mm=5.6)
    radial,axial = complete_pose_errors(pair,domain)
    for yaw,phase,station,pivot_station in itertools.product(np.linspace(0,2*math.pi,9),
            np.linspace(0,2*math.pi,11),(-1.5,1.5),np.linspace(-5.6,1.5,5)):
        axis = np.array((math.cos(yaw),math.sin(yaw),0))
        point = np.array((pair.driven.blank_radius_mm*math.cos(phase),
                          pair.driven.blank_radius_mm*math.sin(phase),station))
        pivot = np.array((0,0,pivot_station))
        relative = point-pivot
        actual = (relative*math.cos(beta)+np.cross(axis,relative)*math.sin(beta)
                  +axis*(axis@relative)*(1-math.cos(beta))+pivot)
        local = (actual-point)@pair.placement.driver_frame
        assert math.hypot(local[0],local[1]) <= radial+1e-13
        assert abs(local[2]) <= axial+1e-13


def test_integral_cam_disk_axial_projection_is_not_scalar_centre_clearance():
    pair = _pair()
    radius,z_band = 20.0,(-6.0,-1.0)
    lower = finite_circular_band_radial_lower(pair,radius,z_band)
    assert lower>0
    assert lower != pytest.approx(40-radius)
    for phase,z,radial in itertools.product(np.linspace(0,2*math.pi,51),z_band,(0,radius)):
        point = (np.asarray(pair.placement.driven_origin_mm)
                 +np.array((radial*math.cos(phase),radial*math.sin(phase),z)))
        local = (point-np.asarray(pair.placement.driver_origin_mm))@pair.placement.driver_frame
        assert math.hypot(local[0],local[1]) >= lower-1e-13
    intersecting = replace(pair,placement=replace(pair.placement,driven_origin_mm=(10,0,0)))
    assert finite_circular_band_radial_lower(intersecting,20,(-1,1)) == 0


def test_root_air_forward_oblique_mate_rotation_pays_driver_axial_chord(monkeypatch):
    pair = _pair()
    radius = pair.driven.blank_radius_mm
    point = np.array((-radius*math.cos(.05),-radius*math.sin(.05),pair.placement.driven_face_mm[1]))
    normal = pair.placement.driver_frame[:,2]
    origin = np.asarray(pair.placement.driven_origin_mm).copy()
    local_z = float((origin+point-np.asarray(pair.placement.driver_origin_mm))@normal)
    origin[2] += (pair.placement.driver_face_mm[1]-1e-8-local_z)/normal[2]
    pair = replace(pair,placement=replace(pair.placement,driven_origin_mm=tuple(origin)))
    searches = []
    def bounded_free(search, **kwargs):
        searches.append(search)
        half = search.case.driver.angular_pitch_rad/2
        return SimpleNamespace(status="resolved",free_inner=((-half,half),),
                               free_outer=((-half,half),),
                               root_air_lower_bound_mm=kwargs["required_root_air_mm"])
    monkeypatch.setattr(cone_study,"root_free_intervals",bounded_free)
    monkeypatch.setattr(cone_study,"asdict",lambda value:vars(value))
    half_width = .001
    cone_study.loaded_root_air_bounds(pair,0.0,(-half_width,half_width),
        radial_error_mm=.003,axial_error_mm=.004)
    chord = 2*pair.driven.blank_radius_mm*math.sin(half_width/2)
    assert searches[0].radial_error_mm >= .003+chord
    axial_factor = math.sqrt(1-float(pair.placement.driver_frame[:,2]@pair.placement.driven_frame[:,2])**2)
    assert searches[0].axial_error_mm >= .004+chord*axial_factor
    moved = np.array((point[0]*math.cos(half_width)-point[1]*math.sin(half_width),
                      point[0]*math.sin(half_width)+point[1]*math.cos(half_width),point[2]))
    axial_motion = float((moved-point)@normal)
    before_z = float((origin+point-np.asarray(pair.placement.driver_origin_mm))@normal)
    assert before_z < pair.placement.driver_face_mm[1] < before_z+axial_motion
    assert 0 < axial_motion <= chord*axial_factor


def test_complete_support_projection_is_not_paid_again_as_independent_cone_tilt():
    pair = _pair()
    nominal = math.atan2(pair.placement.driver_frame[0,2],pair.placement.driver_frame[2,2])
    domain = PoseDomain((0,0),(0,0),(7,7),(3,3),0,
        (nominal-.01,nominal+.01),("exact complete support envelope",),
        cone_support_projection_mm=(.003,.004,.006),
        cone_support_projection_terms=((("all correlated source motions",.003),),
                                       (("all correlated source motions",.004),),
                                       (("all correlated source motions",.006),)))
    radial,axial = complete_pose_errors(pair,domain)
    assert radial == pytest.approx(.005)
    assert axial == pytest.approx(.006)


def test_registry_wording_does_not_enter_geometric_config_identity():
    row = {"title":"CONE","stock":"C36000","process":"48DP PA20",
           "installation_notes":"indicate the retained axis","notes":["shop acceptance"],
           "fit_class":"gear_mesh","face_width_mm":6.8756,"unknown_field":{"limit":.02}}
    def partition(actual):
        geometry,metadata = {},{}
        recorded = cone_study.RegistryFieldReads(actual,lambda key,value,caller:
            (metadata if key in cone_study._PART_METADATA_KEYS else geometry).__setitem__(key,value))
        recorded.copy()
        return geometry,metadata
    geometry,metadata = partition(row)
    assert geometry == {"fit_class":"gear_mesh","face_width_mm":6.8756,"unknown_field":{"limit":.02}}
    assert set(metadata) == {"title","stock","process","installation_notes","notes"}
    changed = {**row,"title":"REVISED TITLE","stock":"REVISED STOCK WORDING",
               "process":"REVISED PROCESS WORDING","installation_notes":"REVISED SETUP WORDING"}
    assert partition(changed)[0] == geometry
    assert partition({**row,"face_width_mm":6.9})[0] != geometry


def test_printed_profile_matrix_is_every_distinct_four_by_four_pair():
    pair = _pair()
    def corners(profile):
        return tuple(StockFormProfile(profile.teeth,profile.template,
            profile.blank_radius_mm+radius,profile.radial_translation_mm+translation)
            for radius,translation in itertools.product((-.001,.001),(-.001,.001)))
    cones,drums = corners(pair.driver),corners(pair.driven)
    cases = tuple(cone_study.printed_profile_cases(cones,drums))
    assert len(cases) == 16
    assert {(ci,di) for ci,di,_,_ in cases} == set(itertools.product(range(4),repeat=2))
    assert {(id(cone),id(drum)) for _,_,cone,drum in cases} == set(
        itertools.product(map(id,cones),map(id,drums)))
    with pytest.raises(ValueError,match="four distinct"):
        tuple(cone_study.printed_profile_cases(cones[:3],drums))
    with pytest.raises(ValueError,match="four distinct"):
        tuple(cone_study.printed_profile_cases(cones,(drums[0],)*4))


def test_full_source_refusal_preserves_actual_reads_without_stationary_fallback(monkeypatch):
    import stock_form_contact_certificate
    pair = _pair()
    domain = {"fixture":"explicit whole source"}
    received = {}
    reads = [{"actual_driver_phase_rad":0.0,
              "signed_running_te_interval_rad":[-.004,-.003]}]
    def unresolved(actual,**kwargs):
        received.update(kwargs)
        return {"qualified":False,"source_domain_proved":True,"actual_read_phases":reads,
                "continuous_contact_certificate":{"status":"UNRESOLVED"}}
    def forbidden(*args,**kwargs):
        pytest.fail("full source must not fall back to a stationary/scalar-ball read")
    monkeypatch.setattr(cone_study,"analyse_3d_mesh",unresolved)
    monkeypatch.setattr(cone_study,"signed_read_matrix",forbidden)
    monkeypatch.setattr(stock_form_contact_certificate,"require_continuous_certificate",
        lambda *args,**kwargs:(_ for _ in ()).throw(ValueError("unresolved union fixture")))
    result = cone_study.qualify_actual_pair(pair,continuous_source_domain=domain,phases=3,
        maximum_error_mm=.0002,read_phases_rad=(0.0,),planar_centre_mm=40,
        selected_nominal_te_rad=(-.005,-.002),nominal_pose_report={})
    assert received["continuous_source_domain"] is domain
    assert received["read_driver_phases_rad"] == (0.0,)
    assert received["coverage_min"] == 1.1
    assert received["row_min"] == 0.0
    assert received["driver_sense"] == -1
    assert not {"position_error_mm","radial_error_mm","axial_error_mm","required_root_air_mm"} & received.keys()
    assert result["qualification"] == "refused"
    assert result["oblique_phase_bound_rad"] is None
    assert result["actual_signed_read_phases"] is reads
    assert result["all_corner_actual3d"]["certificate_replay_error"] == "unresolved union fixture"
    assert "whole retained physical source" in result["reason"]


def test_cli_preimport_identity_compiles_captured_bytes_not_cached_code(tmp_path,monkeypatch):
    import hashlib
    from importlib.machinery import SourceFileLoader
    path = tmp_path/"captured_geometry.py"
    payload = b"captured_value = 17\n"
    path.write_bytes(payload)
    monkeypatch.setattr(cone_study,"SCRIPTS",tmp_path)
    identities = {}
    monkeypatch.setattr(cone_study,"_LOADED_PROJECT_SHA",identities)
    loader = SourceFileLoader("captured_geometry",str(path))
    code = cone_study._captured_project_code(loader,"captured_geometry")
    namespace = {}
    exec(code,namespace)
    assert namespace["captured_value"] == 17
    assert identities == {str(path.resolve()):hashlib.sha256(payload).hexdigest().upper()}
    path.write_bytes(b"captured_value = 19\n")
    with pytest.raises(RuntimeError,match="changed across imports"):
        cone_study._captured_project_code(loader,"captured_geometry")


def test_cli_import_capture_does_not_replace_external_package_loader(tmp_path,monkeypatch):
    from importlib.machinery import SourceFileLoader
    monkeypatch.setattr(cone_study,"SCRIPTS",tmp_path/"project")
    expected = object()
    monkeypatch.setattr(cone_study,"_ORIGINAL_GET_CODE",lambda loader,name:expected)
    loader = SourceFileLoader("external",str(tmp_path/"external.py"))
    assert cone_study._captured_project_code(loader,"external") is expected


def test_cli_capture_stays_cold_before_deferred_part_helpers():
    """Exercise the actual capture class without importing numeric engines."""
    import ast
    import builtins
    from pathlib import Path

    path = Path(cone_study.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    eager = [
        node for node in tree.body
        if (isinstance(node, ast.ImportFrom) and node.module == "dt_cone_gear_spec")
        or (isinstance(node, ast.Import)
            and any(alias.name == "dt_cone_gear_spec" for alias in node.names))
    ]
    capture = next(node for node in tree.body
                   if isinstance(node, ast.ClassDef) and node.name == "InputReadIdentity")
    cache = SimpleNamespace(currsize=0)
    config = SimpleNamespace(
        __name__="cold_capture_config_fixture",
        _doc=SimpleNamespace(cache_info=lambda: cache),
        _parts_registry=SimpleNamespace(cache_info=lambda: cache),
        _load=lambda path: {},
    )
    early_reads = []
    original_import = builtins.__import__

    def cold_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "_config":
            return config
        if name == "dt_cone_gear_spec":
            early_reads.append(name)
            cache.currsize = 1
            return SimpleNamespace(nominal_source_subdomain=lambda *args: None,
                                   budget_clock_subdomain=lambda *args: None)
        return original_import(name, globals, locals, fromlist, level)

    namespace = dict(vars(cone_study))
    namespace["__builtins__"] = {**vars(builtins), "__import__": cold_import}
    isolated = ast.Module(body=[*eager, capture], type_ignores=[])
    exec(compile(isolated, str(path), "exec"), namespace)
    with namespace["InputReadIdentity"]() as reads:
        assert reads.config is config and reads.values == {}
    assert early_reads == []
    cache.currsize = 1
    with pytest.raises(ValueError, match="requires a fresh CLI process"):
        with namespace["InputReadIdentity"]():
            pass


def test_registry_capture_records_only_fields_consumed_by_geometry_or_wording():
    fetched = []
    row = cone_study.RegistryFieldReads(
        {"material_specification":"C36000","description":"CONE","unused_limit_mm":.02},
        lambda key,value,caller:fetched.append((key,value,caller.f_code.co_name)))
    assert row["material_specification"] == "C36000"
    assert row.get("description") == "CONE"
    assert row.get("not_provided","fallback wording") == "fallback wording"
    assert [(key,value) for key,value,_ in fetched] == [
        ("material_specification","C36000"),("description","CONE")]
    assert all(name=="test_registry_capture_records_only_fields_consumed_by_geometry_or_wording"
               for _,_,name in fetched)
    assert "material_specification" in cone_study._PART_METADATA_KEYS
    assert "description" in cone_study._PART_METADATA_KEYS
    assert "unused_limit_mm" not in cone_study._PART_METADATA_KEYS
    fetched.clear()
    assert row.copy()["unused_limit_mm"] == .02
    assert {key for key,_,_ in fetched} == set(row)


def test_extra_air_capacity_search_uses_actual_distinct_inflated_sweeps(monkeypatch):
    pair = _pair()
    cells = [{"driver_interval_rad":[i,i+1],"actual_driven_lower_interval_rad":[.01,.02],
              "root_air":{"qualified":True}} for i in range(2)]
    requested = []
    def swept(actual,phase,loaded,**kwargs):
        extra = kwargs["extra_root_air_mm"]
        requested.append((phase,extra,kwargs["driver_phase_half_width_rad"]))
        return {"qualified":extra <= (.005 if phase<1 else .0035),
                "requested_extra_air_mm":extra}
    monkeypatch.setattr(cone_study,"loaded_root_air_bounds",swept)
    capacity = cone_study.maximum_certified_root_air_capacity(pair,cells,maximum_error_mm=.0002)
    lower,upper = capacity["certification_search_bracket_mm"]
    assert 0 < lower <= .0035 < upper
    assert upper-lower <= .0002
    assert capacity["cone_root_air_lower_mm"] == pytest.approx(.02+lower)
    assert capacity["drum_root_air_lower_mm"] == pytest.approx(.10+lower)
    assert capacity["finite_physical_extra_air_upper_mm"] > upper
    assert len(capacity["last_certified_phase_proofs"]) == 2
    assert all(proof["requested_extra_air_mm"]==lower for proof in capacity["last_certified_phase_proofs"])
    assert all(half==.5 for _,_,half in requested)
    assert len({extra for _,extra,_ in requested}) > 1
    assert not capacity["physical_infeasibility_certified"]


def test_zero_requested_floor_margin_is_not_extra_capacity(monkeypatch):
    pair = _pair()
    cells = [{"driver_interval_rad":[0,1],"actual_driven_lower_interval_rad":[.01,.02],
              "root_air":{"qualified":True,"cone_root_air_lower_mm":.02,"drum_root_air_lower_mm":.10}}]
    monkeypatch.setattr(cone_study,"loaded_root_air_bounds",
        lambda *args,**kwargs:{"qualified":False})
    capacity = cone_study.maximum_certified_root_air_capacity(pair,cells,maximum_error_mm=.0002)
    assert capacity["certified_extra_air_lower_mm"] == 0
    assert capacity["status"] == "no positive reserve certified"
    assert not capacity["physical_infeasibility_certified"]


def test_stationary_design_matrix_never_calls_full_analysis_or_handover(monkeypatch):
    import stock_form_mesh
    pair = _pair()
    def forbidden(*args,**kwargs):
        pytest.fail("stationary DESIGN must not call full analysis or handovers")
    monkeypatch.setattr(cone_study,"analyse_3d_mesh",forbidden)
    monkeypatch.setattr(cone_study,"qualify_actual_pair",forbidden)
    monkeypatch.setattr(stock_form_mesh,"analyse_planar_mesh",forbidden)
    monkeypatch.setattr(stock_form_mesh,"supported_flank_coverage",
        lambda *args,**kwargs:SimpleNamespace(screen_only=True))
    monkeypatch.setattr(cone_study,"asdict",vars)
    monkeypatch.setattr(cone_study,"configured_cam_exclusion",
        lambda *args,**kwargs:{"qualified":True})
    monkeypatch.setattr(cone_study,"signed_read_matrix",
        lambda *args,**kwargs:{"all_reads_bounded":True,"rows":[{"signed_running_te_rad":-.003}]})
    monkeypatch.setattr(cone_study,"ContactSearch",
        lambda *args,**kwargs:SimpleNamespace(window=lambda *args,**kwargs:
            SimpleNamespace(no_overlap=True,root_contact=False)))
    senses = []
    def rooted(actual,phase,**kwargs):
        sense = kwargs["driver_sense"]
        senses.append(sense)
        return {"driven_phase_interval_rad":[.01,.011] if sense<0 else [.013,.014],
                "signed_running_te_interval_rad":[-.004,-.003]}
    monkeypatch.setattr(cone_study,"loaded_phase_at",rooted)
    monkeypatch.setattr(cone_study,"loaded_root_air_bounds",
        lambda *args,**kwargs:{"qualified":True,"cone_root_air_lower_mm":.02,"drum_root_air_lower_mm":.10})
    monkeypatch.setattr(cone_study,"maximum_certified_root_air_capacity",
        lambda *args,**kwargs:{"certified_extra_air_lower_mm":.004})
    measured = cone_study.measure_nominal_for_inspection(pair,phases=3,
        maximum_error_mm=.0002,read_phases_rad=(0,),planar_centre_mm=40)
    assert senses == [-1,1,-1,1]
    assert measured["engineering_complete"]
    assert not measured["production_qualified"]
    assert measured["union_qualification"] is None
    assert measured["handover_qualification"] is None
    assert measured["signed_read_matrix"]["rows"][0]["signed_running_te_rad"] == -.003
    assert measured["source_inspection_radius_mm"] == pytest.approx(40*120/152)
    assert measured["physical_driven_pitch_radius_mm"] == pair.driven.pitch_radius_mm
    assert measured["margins"]["cone_root_air_mm"] == .004


def _six_compiled_receipt():
    files = {
        "C:/actual/captured/"+path:"AB"*32
        for path in cone_study._MEASUREMENT_ENGINE_PATHS
    }
    return {
        "source_bytes_stable":True,
        **{name:dict(files) for name in (
            "before_design_sha256","actual_preimport_project_sha256",
            "after_design_sha256","loaded_algorithm_sha256",
        )},
    }


def test_factory_engine_identity_uses_real_receipt_not_live_file_hashes(monkeypatch):
    monkeypatch.setattr(cone_study,"_byte_sha",
        lambda *args:pytest.fail("factory transport must not rebind current source"))
    identity = cone_study.compiled_measurement_identity(_six_compiled_receipt())
    measured = identity["measurement_engine_sources_sha256"]
    assert set(measured) == {path.rsplit("/",1)[1]
                            for path in cone_study._MEASUREMENT_ENGINE_PATHS}
    assert len(measured) == 6
    assert identity["measurement_engine_sha256"] == cone_study._canonical_sha256(measured)


@pytest.mark.parametrize("field",(
    "before_design_sha256","actual_preimport_project_sha256",
    "after_design_sha256","loaded_algorithm_sha256",
))
def test_factory_engine_identity_refuses_missing_actual_sixth_source(field):
    source = _six_compiled_receipt()
    missing = cone_study._MEASUREMENT_ENGINE_PATHS[-1]
    source[field].pop("C:/actual/captured/"+missing)
    with pytest.raises(ValueError,match="stock_form_contact_continuation"):
        cone_study.compiled_measurement_identity(source)


def test_changed_after_source_never_releases_factory_measurement_identity():
    source = _six_compiled_receipt()
    source["source_bytes_stable"] = False
    with pytest.raises(ValueError,match="changed live source"):
        cone_study.compiled_measurement_identity(source)
    source["source_bytes_stable"] = True
    changed = "C:/actual/captured/"+cone_study._MEASUREMENT_ENGINE_PATHS[0]
    source["after_design_sha256"][changed] = "CD"*32
    with pytest.raises(ValueError,match="compiled/before/after/loaded"):
        cone_study.compiled_measurement_identity(source)


def test_ambiguous_raw_source_suffix_is_not_an_authentic_factory_identity():
    source = _six_compiled_receipt()
    source["before_design_sha256"][
        "C:/second/captured/"+cone_study._MEASUREMENT_ENGINE_PATHS[0]
    ] = "AB"*32
    with pytest.raises(ValueError,match="exactly one"):
        cone_study.compiled_measurement_identity(source)


def _full_transport_case(ci=None,di=None):
    side = {
        "same_source_pose":{"fixture":["bounded source"]},
        "phase_domain_rad":[0.0,1.0],"phase_cells":[{"fixture":"full cell"}],
        "row_branch_spans":[{"fixture":"supported row"}],"handovers":[],
        "periodic_seam":{"status":"PROVED","continuous":True},
    }
    return {
        "case_id":"nominal" if ci is None else f"C{ci:02d}-D{di:02d}",
        "cone_corner_index":ci,"drum_corner_index":di,
        "cone":{"fixture":"cone"},"drum":{"fixture":"drum"},
        "calculation":{
            "qualification":"qualified",
            "all_corner_actual3d":{
                "production_source_qualified":True,"source_domain_proved":True,
                "continuous_contact_certificate":{
                    "proof_schema":"finite-stock-continuous-envelope/1",
                    "status":"PROVED","native_certificate":False,
                    "sides":{"lower":side,"upper":side},
                },
            },
        },
    }


def test_full_profile_transport_preserves_distinct_all_sixteen_real_case_reports():
    corners = [_full_transport_case(ci,di) for ci in range(4) for di in range(4)]
    nominal = _full_transport_case()
    records = cone_study.full_profile_case_records(nominal,list(reversed(corners)))
    assert records[0] is nominal
    assert records[1:] == corners
    assert records[-1]["calculation"] is corners[-1]["calculation"]
    with pytest.raises(ValueError,match="each distinct"):
        cone_study.full_profile_case_records(nominal,[*corners[:-1],corners[0]])


def test_full_profile_transport_refuses_held_nominal_or_old_sample_flags():
    nominal = _full_transport_case()
    corners = [_full_transport_case(ci,di) for ci in range(4) for di in range(4)]
    corners[0]["actual_source_nominal_pose"] = True
    with pytest.raises(ValueError,match="held-nominal"):
        cone_study.full_profile_case_records(nominal,corners)
    corners[0].pop("actual_source_nominal_pose")
    corners[0]["calculation"]["all_corner_actual3d"] = {
        "qualified":True,"continuous_carrying_contact":True,
    }
    with pytest.raises(ValueError,match="continuous-contact proof"):
        cone_study.full_profile_case_records(nominal,corners)


def test_actual_four_root_envelope_is_radius_not_maximum_as_floor():
    profiles = [
        SimpleNamespace(blank_radius_mm=radius,radial_translation_mm=shift,
                        root_radius_min_mm=1.0+shift,root_radius_max_mm=1.1+shift)
        for radius,shift in itertools.product((1.8,1.79),(0.0,-.02))
    ]
    assert cone_study.printed_root_radius_envelope(profiles) == pytest.approx([.98,1.1])
    with pytest.raises(ValueError,match="four distinct"):
        cone_study.printed_root_radius_envelope([profiles[0]]*4)


def test_factory_transport_never_turns_refused_or_engineering_data_green():
    refused = {
        "qualified":False,"rows":[],"source_inputs_only":False,
        "nominal_engineering_only":False,
    }
    cone_study.attach_factory_transport(refused,{"fixture":"retained independent inputs"})
    assert not refused["qualified"]
    assert refused["selected_geometry_sha256"] is None
    assert "measurement_engine_sources_sha256" not in refused
    assert "factory_transport_refusal" in refused
    with pytest.raises(ValueError,match="engineering/source-prep"):
        cone_study.attach_factory_transport({"nominal_engineering_only":True},{})


def test_cone_transport_does_not_invent_a_positive_axial_row_floor():
    nominal = _full_transport_case()
    corners = [_full_transport_case(ci, di) for ci in range(4) for di in range(4)]
    for record in (nominal, *corners):
        for side in record["calculation"]["all_corner_actual3d"]["continuous_contact_certificate"]["sides"].values():
            side["row_branch_spans"] = []
    assert len(cone_study.full_profile_case_records(nominal, corners)) == 17


def test_pure_cone_source_placement_retains_original_physical_gauge():
    import dt_cone_mesh_domain as source
    from diagnostics.solve_stock_form_cones import oblique_section_geometry
    for teeth in range(6, 121, 6):
        expected = placement_from_geometry(oblique_section_geometry(teeth)).record()
        actual = source.nominal_placement_record(teeth)
        for name in ("driver_origin_mm", "driven_origin_mm", "driver_frame", "driven_frame"):
            assert np.asarray(actual[name]) == pytest.approx(np.asarray(expected[name]))
        for name in ("driver_face_mm", "driven_face_mm", "driver_clocking_rad", "driven_clocking_rad"):
            assert actual[name] == pytest.approx(expected[name])
        assert actual["driver_shoulder_z_mm"] is None
        assert actual["driver_turned_radius_mm"] is None


def test_manufactured_gap_and_notch_mapping_matches_native_reflection():
    import _config
    import dt_cone_mesh_domain as source
    import dt_cylinder_gear_spec as drum
    lock = math.radians(_config.machine("gear_train", "cylinder_lock_phase_deg"))
    rows = cylinder_native_rows(lock)
    native_gap = math.pi / drum.TEETH
    native_notch = math.pi / 2 + math.radians(drum.NOTCH_PHASE_DEG)
    world_gap = rows.T @ np.array((math.cos(native_gap), math.sin(native_gap), 0.0))
    world_notch = rows.T @ np.array((math.cos(native_notch), math.sin(native_notch), 0.0))
    for teeth in range(6, 121, 6):
        datum = source.manufactured_datum_mapping(teeth)
        gap = datum["saved_cad_driven_canonical_gap_clock_rad"]
        notch = datum["saved_cad_world_cam_notch_ray_rad"]
        assert (math.cos(gap), math.sin(gap)) == pytest.approx(world_gap[:2])
        assert (math.cos(notch), math.sin(notch)) == pytest.approx(world_notch[:2])
        assert datum["driver_canonical_gap_clock_rad"] == pytest.approx(math.pi / teeth)
        assert datum["mechanical_zero_rad"]["driver"] == 0.0
        assert datum["mechanical_zero_rad"]["driven"] == pytest.approx(math.pi)
        assert datum["saved_cad_driven_mechanical_phase_rad"] == pytest.approx(-lock-native_gap)
        assert datum["nominal_driven_mechanical_phase_rad"] == 0.0
        assert datum["operating_source_state"] == "OPERATING_NOTCH_UP"
        assert datum["physical_driven_setup_rotation_rad"] == pytest.approx(lock+native_gap)
        assert datum["driven_canonical_gap_clock_rad"] == pytest.approx(math.pi)
        assert datum["nominal_world_cam_notch_ray_rad"] == pytest.approx(math.pi/2)
        assert datum["datum_tare_rad"] is None
        assert "physical drum rotation" in datum["alignment_zero_operation"]
        assert datum["mechanical_zero_rad"]["driven"] != pytest.approx(gap)


@pytest.mark.parametrize("body", ("cone", "drum"))
def test_missing_own_tooth_runout_is_unknown_not_unrelated_crank_grade(monkeypatch, body):
    import _config
    import _fit_limits as source
    calls = []
    def missing(section, key):
        calls.append((section, key))
        raise KeyError(key)
    monkeypatch.setattr(_config, "fit", missing)
    with pytest.raises(source.SourceDomainUnknown, match="missing actual"):
        source.tooth_cutting_runout_tir_mm(body)
    assert calls == [("cone_drum_oblique_mesh", f"{body}_tooth_cutting_runout_tir_mm")]


@pytest.mark.parametrize("value", (0.0, -.01, math.nan, math.inf, True, ".02"))
def test_own_tooth_runout_needs_actual_positive_source_authority(monkeypatch, value):
    import _config
    import _fit_limits as source
    monkeypatch.setattr(_config, "fit", lambda *args: value)
    with pytest.raises(source.SourceDomainUnknown, match="finite positive"):
        source.tooth_cutting_runout_tir_mm("drum")


def test_body_disks_pay_printed_running_clearance_and_own_tir_once(monkeypatch):
    import dt_cone_mesh_domain as source
    import _fit_limits
    import dt_cone_gear_spec as cone
    import dt_cylinder_gear_spec as drum
    import cone_shaft_land_bands as lands
    monkeypatch.setattr(_fit_limits, "tooth_cutting_runout_tir_mm",
                        lambda body: {"cone": .024, "drum": .028}[body])
    for teeth in range(6, 121, 6):
        disks = source.source_eccentricity_disks(teeth)
        shaft_low, _ = lands.land_finished_dia_limits_mm(cone.bore_dia_mm(teeth), cone.land_section(teeth))
        printed_bore_high = round(cone.bore_dia_mm(teeth), cone.DRAWING_PRECISION_BY_NAME["BoreCutDia"]) + cone.BORE_DIA_BAND[0]
        expected = {"driver": ((printed_bore_high - shaft_low) / 2, .012),
                    "driven": (drum.BORE_DIAMETRAL_CLEARANCE_MM[1] / 2, .014)}
        for body, (fit, runout) in expected.items():
            assert disks[body]["shape"] == "closed_disk"
            assert disks[body]["centre_mm"] == [0.0, 0.0]
            assert disks[body]["source_terms_mm"] == {
                "gear_bore_radial_clearance_upper": fit, "tooth_runout_radius_upper": runout}
            assert disks[body]["radius_mm"] >= fit + runout
            assert disks[body]["radius_mm"] == pytest.approx(fit + runout, abs=1e-14)


def test_nominal_subdomain_is_explicit_mathematics_not_a_production_grade():
    import dt_cone_gear_spec as source
    pair = _pair()
    parent = {
        "scope":"FULL_PRODUCTION_SOURCE_DOMAIN","production_source_domain":True,
        "correlated_pose_parameters":[["driver_clock_rad",[-.2,.2]],["driver_dx_mm",[-.01,.03]],
                                      ["driven_clock_rad",[-.001,.001]]],
        "source_eccentricity_disks":{"driver":{"radius_mm":.02},"driven":{"radius_mm":.03}},
        "finite_face_width_limits_mm":{"driver":[6.9,7.1],"driven":[2.95,3.05]},
        "finite_face_anchor_fraction":{"driver":.5,"driven":.5},
    }
    nominal = source.nominal_source_subdomain(pair.placement.record(),parent)
    assert nominal["scope"] == "DESIGN_NOMINAL_SUBDOMAIN"
    assert nominal["production_source_domain"] is False
    assert nominal["physical_parent_domain"] is parent
    assert all(bounds == [0.0,0.0] for _,bounds in nominal["correlated_pose_parameters"])
    assert nominal["source_eccentricity_disks"]["driver"]["source_terms_mm"] == {
        "nominal_subdomain_radius_upper_mm":0.0}
    assert parent["source_eccentricity_disks"]["driver"]["radius_mm"] == .02
    assert nominal["finite_face_anchor_fraction"] == parent["finite_face_anchor_fraction"]
    assert nominal["finite_face_width_limits_mm"] == {
        body:[width,width] for body,width in (
            ("driver",pair.placement.driver_face_mm[1]-pair.placement.driver_face_mm[0]),
            ("driven",pair.placement.driven_face_mm[1]-pair.placement.driven_face_mm[0]))}
    budget = source.budget_clock_subdomain(parent)
    assert budget["scope"] == "BUDGET_CLOCK_NOMINAL_SUBDOMAIN"
    assert budget["production_source_domain"] is False
    assert budget["physical_parent_domain"] is parent
    assert dict(budget["correlated_pose_parameters"]) == {
        "driver_clock_rad":[0.0,0.0],"driver_dx_mm":[-.01,.03],"driven_clock_rad":[0.0,0.0]}
    assert budget["source_eccentricity_disks"] == parent["source_eccentricity_disks"]
    assert budget["finite_face_width_limits_mm"] == parent["finite_face_width_limits_mm"]
    assert budget["finite_face_anchor_fraction"] == parent["finite_face_anchor_fraction"]
    assert budget["oblique_phase_bound_excluded_terms"] == [
        "cone_flat_free_clock","BoreFlatClock","drum_tooth_to_cam_notch_clock"]


def test_operating_setup_rotates_native_marker_and_keeps_saved_bias():
    import dt_cone_mesh_domain as source
    import dt_cylinder_gear_spec as drum
    for teeth in range(6,121,6):
        datum = source.manufactured_datum_mapping(teeth)
        native = datum["native_cam_notch_ray_rad"]
        saved_lock = math.pi-datum["saved_cad_driven_canonical_gap_clock_rad"]-math.pi/drum.TEETH
        saved = cylinder_native_rows(saved_lock).T @ np.array((math.cos(native),math.sin(native),0.0))
        active = cylinder_native_rows(saved_lock-datum["physical_driven_setup_rotation_rad"]).T @ np.array(
            (math.cos(native),math.sin(native),0.0))
        assert active == pytest.approx((0.0,1.0,0.0),abs=2e-15)
        assert tuple(saved) != pytest.approx(tuple(active))
        assert datum["saved_cad_driven_mechanical_phase_rad"] != 0.0
        assert datum["datum_tare_rad"] is None


def test_current_lattice_alternatives_are_lazy_and_never_repeat_inputs(monkeypatch):
    from diagnostics import solve_stock_form_cones as solve
    chosen = {"outside_dia_mm":10.0,"pitch_thickness_mm":1.0}
    alternative = {"outside_dia_mm":10.01,"pitch_thickness_mm":1.01}
    calls = []
    def current(teeth,inputs,**kwargs):
        calls.append((teeth,inputs,kwargs))
        return {"geometry_candidates":[dict(chosen),alternative],"finite_lattice_exhausted":True}
    monkeypatch.setattr(solve,"solve_count",current)
    ledger = {}
    settings = cone_study.actual_candidate_settings(32,{"geometry_candidates":[chosen,dict(chosen)]},"inputs",
        six_pitch_thickness_mm=1.05,allow_fresh_lattice=True,lattice_record=ledger)
    assert next(settings) is chosen
    assert calls == []
    assert next(settings) is alternative
    assert calls == [(32,"inputs",{"six_pitch_thickness_mm":1.05,"analyse_mesh":False})]
    assert list(settings) == []
    assert "current_dimensional_lattice" in ledger
    assert "physical all-family" in ledger["scope"]


def _stock_phase_reports_fixture():
    phases = tuple(-k*math.pi for k in range(21))
    def report(delta,*,reference=False):
        rows = []
        for phase in phases:
            value = -.003+phase*.0001+delta
            row = {"actual_driver_phase_rad":phase,
                   "signed_running_te_interval_rad":[value-.0002,value+.0003]}
            if reference:
                row.update(reference_signed_running_te_rad=value,
                           reference_error_bound_rad=.0004)
            rows.append(row)
        return {"source_domain_proved":True,"actual_read_phases":rows,
                "full_period_cells":[{"signed_running_te_interval_rad":[-.02+delta,.01+delta]}],
                "whole_period_signed_running_te_interval_rad":[-.02+delta,.01+delta]}
    reference = report(0.0,reference=True)
    cases = [_full_transport_case(),*(_full_transport_case(ci,di) for ci in range(4) for di in range(4))]
    for index,case in enumerate(cases):
        case["calculation"]["budget_actual3d"] = report(index*.0001)
        case["calculation"]["nominal_actual3d"] = reference if index==0 else report(index*.00005)
    return phases,reference,cases


def test_actual_stock_phase_uses_true_point_reference_not_source_range_mean():
    phases,reference,cases = _stock_phase_reports_fixture()
    result = cone_study.stock_phase_3d_packet(cases,reference,
        driver_read_phases_rad=phases,ratio=32/120,datum={"fixture":"physical notch"})
    assert result["schema"] == "dt-cone-operating-stock-phase/1"
    assert result["nominal_signed_running_te_rad"][0] == -.003
    assert result["nominal_signed_running_te_rad"][0] != pytest.approx((-.0032-.0027)/2)
    assert result["nominal_driven_advance_rad"][1] == pytest.approx(
        reference["actual_read_phases"][1]["reference_signed_running_te_rad"]-(32/120)*phases[1])
    assert result["nominal_reference_numerical_bound_rad"] == [.0004]*21
    assert result["robust_half_width_rad"][0] >= .0019
    assert result["nominal_pose_half_width_rad"][0] >= .0011
    assert result["robust_signed_te_interval_rad"] == pytest.approx([-.02,.0116])
    assert result["nominal_pose_signed_te_interval_rad"] == pytest.approx([-.02,.0108])
    assert result["shaft_advance_included"] is False
    assert result["excluded_terms"] == [
        "cone_flat_free_clock","BoreFlatClock","drum_tooth_to_cam_notch_clock"]
    assert result["datum_tare_rad"] is None


@pytest.mark.parametrize("change",("reference","numerical","read_order","corner","whole_period"))
def test_actual_stock_phase_refuses_missing_real_reference_or_full_matrix(change):
    phases,reference,cases = _stock_phase_reports_fixture()
    if change=="reference":
        reference["actual_read_phases"][0].pop("reference_signed_running_te_rad")
    elif change=="numerical":
        reference["actual_read_phases"][0]["reference_error_bound_rad"] = 0.0
    elif change=="read_order":
        reference["actual_read_phases"].reverse()
    elif change=="whole_period":
        cases[1]["calculation"]["budget_actual3d"].pop("whole_period_signed_running_te_interval_rad")
    else:
        cases.pop()
    with pytest.raises((KeyError,ValueError)):
        cone_study.stock_phase_3d_packet(cases,reference,
            driver_read_phases_rad=phases,ratio=32/120,datum={"fixture":"physical notch"})


def test_centre_ledger_books_whole_operating_sources_once_and_never_clips(monkeypatch):
    import dt_cone_mesh_domain as source
    import cone_line
    pose = {
        "translation_intervals_mm":[[-.12,.12],[0.0,0.0],[0.0,0.0]],
        "shortest_transport_euler_intervals_rad":[[0.0,0.0]]*3,
        "source_projection_ledgers_mm":[{"post running journal radial fit":.12},{},{}],
    }
    disks = {
        body:{"radius_mm":radius,"source_terms_mm":{
            "gear_bore_radial_clearance_upper":radius,
            "tooth_runout_radius_upper":0.0}}
        for body,radius in (("driver",.0375),("driven",.035))}
    monkeypatch.setattr(source,"nominal_placement_record",
        lambda teeth:{"driver_origin_mm":[0.0,0.0,0.0],"driven_origin_mm":[1.0,0.0,0.0]})
    ledger = source._centre_source_ledger(6,pose,disks,(0.0,0.0),(0.0,0.0),0.0,0.0,.20)
    assert ledger["booked_closing_total"] == pytest.approx(.0875)
    assert ledger["known_bore_radial_total_before_other_sources"] == pytest.approx(.0725)
    assert ledger["closing_book_remainder_before_other_sources"] == pytest.approx(.015)
    assert not ledger["closing_remainder_is_tolerance_grant"]
    assert not ledger["post_running_fit_added_again"]
    assert "bearing" not in " ".join(ledger["directed_source_terms_mm"])
    assert ledger["derived_closing_total"] >= .12/cone_line.COS_I
    assert ledger["derived_opening_total"] > .20
    assert ledger["positive_opening_axis"] == 0.0
    assert ledger["selected_total"] == ledger["derived_opening_total"]
    assert ledger["required_closing_total"] == ledger["derived_closing_total"]
    pose["translation_intervals_mm"] = [[0.0,0.0]]*3
    pose["source_projection_ledgers_mm"] = [{},{},{}]
    zero_disks = {body:{**disk,"radius_mm":0.0} for body,disk in disks.items()}
    small = source._centre_source_ledger(6,pose,zero_disks,(0.0,0.0),(0.0,0.0),0.0,0.0,.20)
    assert small["positive_opening_axis"] > 0
    assert small["derived_opening_total"]+small["positive_opening_axis"] >= .20
    assert small["selected_total"] == .20


@pytest.mark.parametrize("closing_factor,opening_factor",((.3,.25),(1.0,1.0),(1.5,1.25)))
def test_radial_book_remainder_below_equal_above_each_total(monkeypatch,closing_factor,opening_factor):
    """The tested bounds are source-ledger inputs, not measured stock/geometry."""
    import dt_cone_mesh_domain as source
    import dt_cone_gear_spec as cone
    import dt_cylinder_gear_spec as drum
    import cone_shaft_land_bands as lands
    expected_close = math.fsum(((cone.BORE_DIA_BAND[0]-lands.GEAR_SEAT_BAND[1])/2,
                               drum.BORE_DIAMETRAL_CLEARANCE_MM[1]/2))
    closing,opening = closing_factor*expected_close,opening_factor*.20
    real_sum = source._interval_sum
    calls = []
    def source_or_completed_sum(rows):
        calls.append(tuple(rows))
        return (-closing,opening) if len(calls)==1 else real_sum(calls[-1])
    monkeypatch.setattr(source,"_interval_sum",source_or_completed_sum)
    monkeypatch.setattr(source,"nominal_placement_record",
        lambda teeth:{"driver_origin_mm":[0.0,0.0,0.0],"driven_origin_mm":[1.0,0.0,0.0]})
    pose = {"translation_intervals_mm":[[0.0,0.0]]*3,
        "shortest_transport_euler_intervals_rad":[[0.0,0.0]]*3,
        "source_projection_ledgers_mm":[{},{},{}]}
    disks = {body:{"radius_mm":0.0,"source_terms_mm":{
        "gear_bore_radial_clearance_upper":0.0,"tooth_runout_radius_upper":0.0}}
        for body in ("driver","driven")}
    ledger = source._centre_source_ledger(6,pose,disks,(0.0,0.0),(0.0,0.0),0.0,0.0,.20)
    booked_close = ledger["booked_closing_total"]
    assert booked_close == expected_close
    residual = ledger["booked_centre_radial_remainder_mm"]
    assert residual[0] == pytest.approx(-max(0.0,booked_close-closing),abs=1e-15)
    assert residual[1] == pytest.approx(max(0.0,.20-opening),abs=1e-15)
    assert residual[0] <= 0.0 <= residual[1]
    assert ledger["required_closing_total"] == max(booked_close,closing)
    assert ledger["selected_total"] == max(.20,opening)
    completed = ledger["actual_source_plus_remainder_enclosure_mm"]
    assert completed[0] <= -ledger["required_closing_total"]
    assert completed[1] >= ledger["selected_total"]
    assert "existing driven_dx_mm" in ledger["remainder_coordinate"]
    assert "no physical attainment" in ledger["radial_booking_scope"]
    if closing>=booked_close:
        assert residual[0] == 0.0
    if opening>=.20:
        assert residual[1] == 0.0


def test_raw_compiled_snapshot_retains_captured_bytes_without_live_reread(tmp_path):
    from pathlib import Path
    original = str(cone_study.SCRIPTS/"captured-receipt-fixture.py")
    captured = {original:b"# exact imported bytes\nvalue = 1\n"}
    root = tmp_path/"source.capture"
    compiled = cone_study.retain_raw_source_snapshot(root,"compiled",captured)
    after = cone_study.retain_raw_source_snapshot(root,"after",{original:b"value = 2\n"})
    assert Path(compiled[original]).read_bytes() == captured[original]
    assert Path(after[original]).read_bytes() != captured[original]
    assert Path(compiled[original]) != Path(after[original])
    with pytest.raises(ValueError,match="outside the repository"):
        cone_study.retain_raw_source_snapshot(cone_study.SCRIPTS/"forbidden-capture","compiled",captured)


def test_source_identity_retains_the_same_hashed_payload_not_later_bytes(tmp_path):
    import hashlib
    original = tmp_path/"fit-source.yaml"
    original.write_bytes(b"grade: old\n")
    captured = {}
    identity = cone_study.source_identity((original,),captured_payloads=captured)
    before = captured[str(original)]
    original.write_bytes(b"grade: changed\n")
    assert before == b"grade: old\n"
    assert identity[str(original)] == hashlib.sha256(before).hexdigest().upper()
    assert identity[str(original)] != cone_study.source_identity((original,))[str(original)]


def test_actual_parsed_config_bytes_are_retained_and_changed_reparse_refuses(tmp_path):
    import json
    reads = cone_study.InputReadIdentity()
    empty_cache = SimpleNamespace(cache_info=lambda:SimpleNamespace(currsize=0))
    original_load = lambda path:{"unconsumed":True}
    reads.config = SimpleNamespace(
        __name__="capture_fixture",_doc=empty_cache,_parts_registry=empty_cache,
        _load=original_load,yaml=SimpleNamespace(safe_load=json.loads))
    path = tmp_path/"actual-config.yaml"
    payload = b'{"grade_mm":0.015}\n'
    path.write_bytes(payload)
    with reads:
        assert reads.config._load(path) == {"grade_mm":.015}
        assert reads.loaded_config_payloads[str(path.resolve())] == payload
        path.write_bytes(b'{"grade_mm":0.020}\n')
        with pytest.raises(RuntimeError,match="changed across actual parses"):
            reads.config._load(path)
        assert reads.loaded_config_payloads[str(path.resolve())] == payload
    assert reads.config._load is original_load


def test_consumed_config_capture_keeps_metadata_but_excludes_unread_cache_rows():
    reads = cone_study.InputReadIdentity()
    reads.loaded_config_payloads = {
        "geometric.yaml":b"fit: actual\n",
        "metadata.yaml":b"title: actual\n",
        "unread-registry-row.yaml":b"unused: parsed-by-shared-cache\n",
    }
    reads.before = {"geometric.yaml":"geometric-sha"}
    reads.non_geometry_before = {"metadata.yaml":"metadata-sha"}
    assert reads.consumed_config_payloads() == {
        "geometric.yaml":b"fit: actual\n",
        "metadata.yaml":b"title: actual\n",
    }


def test_missing_drum_tooth_to_cam_notch_clock_is_unknown_not_lobe_grade(monkeypatch):
    import _config
    import _fit_limits as source
    calls = []
    def missing(group,key):
        calls.append((group,key))
        raise KeyError(key)
    monkeypatch.setattr(_config,"fit",missing)
    with pytest.raises(source.SourceDomainUnknown,match="missing actual drum tooth-to-CAM-NOTCH"):
        source.drum_tooth_to_cam_notch_clock_deg()
    assert calls == [("cone_drum_oblique_mesh","drum_tooth_to_cam_notch_clock_deg")]


@pytest.mark.parametrize("value",(0.0,-.05,math.nan,math.inf,True,".05"))
def test_drum_pattern_clock_requires_actual_positive_source_grade(monkeypatch,value):
    import _config
    import _fit_limits as source
    monkeypatch.setattr(_config,"fit",lambda *args:value)
    with pytest.raises(source.SourceDomainUnknown,match="finite positive"):
        source.drum_tooth_to_cam_notch_clock_deg()


def test_drum_pattern_clock_positive_reader_does_not_invent_a_band(monkeypatch):
    import _config
    import _fit_limits as source
    monkeypatch.setattr(_config,"fit",lambda *args:.037)
    assert source.drum_tooth_to_cam_notch_clock_deg() == .037


def test_full_pair_preserves_raw_same_q_rows_and_calibrates_only_actual_difference(monkeypatch):
    pair = _pair()
    rop = 40*pair.driven.teeth/(pair.driver.teeth+pair.driven.teeth)
    angle = [.10/rop,.15/rop]
    domain = {
        "scope":"FULL_PRODUCTION_SOURCE_DOMAIN","production_source_domain":True,
        "correlated_pose_parameters":[["driver_clock_rad",[-.01,.01]]],
        "root_air_requirements_mm":{"driver":.02,"driven":.10},
        "manufactured_datum_mapping":{"fixture":"independent physical datum"},
    }
    root = {
        "qualified":True,"root_is_carrying":False,
        "root_air_requirements_mm":domain["root_air_requirements_mm"],
        "driver_root_air_lower_mm":.03,"driven_root_air_lower_mm":.11,
    }
    cell = {
        "actual_driver_interval_rad":[0.0,pair.driver.angular_pitch_rad],
        "signed_running_te_interval_rad":[-.004,-.003],
        # Marginal beta intervals deliberately lose the common source and
        # would refuse if independently subtracted. They are not backlash.
        "actual_driven_lower_interval_rad":[-100.0,100.0],
        "actual_driven_upper_interval_rad":[-99.999,100.001],
        "correlated_backlash":{"backlash_interval_rad":angle},
        "correlated_backlash_interval_mm":[value*pair.driven.pitch_radius_mm for value in angle],
        "root_air":root,
    }
    read = {"actual_driver_phase_rad":-math.pi,
            "signed_running_te_interval_rad":[-.004,-.003]}
    robust = {
        "production_source_qualified":True,"source_domain_proved":True,
        "full_period_cells":[cell],"actual_read_phases":[read],
        "stock_form_coverage_lower":1.2,"handovers":[{"pitch_displacement_jump_upper_mm":.003}],
    }
    budget = {"source_domain_proved":True,"full_period_cells":[cell]}
    monkeypatch.setattr(cone_study,"_continuous_analysis",
        lambda actual,source,**kwargs:robust if source is domain else budget)
    monkeypatch.setattr(cone_study,"exact_smooth_ff_exclusion",lambda actual:{"fixture":True})
    monkeypatch.setattr(cone_study,"full_source_cam_exclusion",lambda *args:{"qualified":True})
    result = cone_study.qualify_actual_pair(pair,continuous_source_domain=domain,phases=3,
        maximum_error_mm=.0002,read_phases_rad=(-math.pi,),planar_centre_mm=40,
        selected_nominal_te_rad=(-.004,-.003),nominal_pose_report=budget)
    assert result["qualification"] == "qualified"
    assert result["full_period_cells"][0] is cell
    inspection = result["source_inspection_backlash_cells"][0]
    assert inspection["source_calibrated_backlash_interval_mm"] == pytest.approx([.10,.15])
    assert inspection["physical_pitch_arc_backlash_interval_mm"] == cell["correlated_backlash_interval_mm"]
    assert result["actual_driven_backlash"]["tight_lower_mm"] == pytest.approx(.10)
    assert result["actual_driven_backlash"]["loose_upper_mm"] == pytest.approx(.15)
    assert result["signed_read_matrix"]["rows"][0]["read_phase_interval_rad"] == [-math.pi,-math.pi]
